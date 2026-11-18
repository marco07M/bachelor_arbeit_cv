"""Observed effort and explicit cost assumptions; no inference or invented measurements."""

import json
import math
from collections import Counter, defaultdict
from types import SimpleNamespace

import numpy as np

from ..config import CostsConfig
from ..io import read_jsonl
from ..report import cost_scenario


def distribution(values):
    clean = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(v) and v >= 0]
    return dict(
        n=len(clean),
        median=float(np.median(clean)) if clean else None,
        q25=float(np.quantile(clean, 0.25)) if clean else None,
        q75=float(np.quantile(clean, 0.75)) if clean else None,
        minimum=min(clean) if clean else None,
        maximum=max(clean) if clean else None,
        values=clean,
        unit="seconds",
    )


def enrich_effort(values, rows, pages, summary, method, extraction_config):
    counter = summary.get("model_calls", summary.get("generation_calls"))
    measured = isinstance(counter, int) and not isinstance(counter, bool) and counter >= 0
    if values["scope_matches"] and measured and sum(p.calls for p in pages) != counter:
        measured = False  # A full-run counter cannot be distributed to pages by assumption.
    signature = extraction_config.get("signature", {}).get("backend", "unknown")
    textual = method in ("ocr_llm", "paddle_llm", "unlimited_ocr", "paddle_structure")
    mixed = (textual and signature in ("local_vlm", "vlm", "unknown")) or (
        method in ("ocr_rules", "ocr_raw") and signature == "unknown"
    )
    by_document = defaultdict(list)
    for row, page in zip(rows, pages, strict=True):
        known = measured and "calls" in page.model_fields_set
        calls = page.calls if known else None
        row.update(
            actual_calls=calls,
            llm_calls=calls if textual and not mixed else 0 if known and not mixed else None,
            vlm_calls=calls
            if not textual and method not in ("ocr_rules", "ocr_raw") and not mixed
            else 0
            if known and not mixed
            else None,
            calls_status="recorded_counter" if known else "unavailable_or_inconsistent_counter",
        )
        by_document[page.document_id].append(row)
    documents = []
    for document, items in by_document.items():

        def total(key):
            v = [r[key] for r in items]
            return sum(v) if all(n is not None for n in v) else None

        documents.append(
            dict(
                document_id=document,
                pages=len(items),
                actual_calls=total("actual_calls"),
                llm_calls=total("llm_calls"),
                vlm_calls=total("vlm_calls"),
            )
        )
    values.update(
        page_time=distribution(r["page_wall_seconds"] for r in rows),
        document_calls=documents,
        selected_actual_calls=sum(r["actual_calls"] for r in rows)
        if rows and all(r["actual_calls"] is not None for r in rows)
        else None,
        call_counter_note="Stored actual invocations include name helpers, exclude separately reported warm-up; cached answers incur no fresh assignment call. Legacy/mixed counters can remain unknown.",
    )
    for name in ("llm_calls", "vlm_calls"):
        values["selected_" + name] = (
            sum(r[name] for r in rows) if rows and all(r[name] is not None for r in rows) else None
        )
    return values


def technical_observations(source, method, pages, raw_pages, expected_pages):
    """Only recorded final-response records; retries/history are a separate unit."""
    generative = method in {"ocr_llm", "paddle_llm", "vlm", "ocr_vlm", "docling_vlm"} or any(
        raw.get("docling_vlm_assist", {}).get("vlm_called") is True for raw in raw_pages)
    responses, seen = [], set()
    for page, raw in zip(pages, raw_pages, strict=True):
        records = list(raw.get("responses", []))
        assignment = raw.get("assignment", {})
        if assignment.get("raw_response") is not None:
            # Structure pipelines also store the same answer in responses: count it once.
            records = [r for r in records if r.get("raw_response") != assignment["raw_response"]]
            records.append(assignment)
        for index, r in enumerate(records):
            key = (page.page_id, index)
            if key in seen:
                continue
            seen.add(key)
            if not generative or not (r.get("prompt_version") or r.get("generation_schema_sha256")
                                      or r is assignment):
                continue  # A native table converted to JSON is not a generative response.
            literal = r.get("raw_response")
            syntax = None
            if isinstance(literal, str):
                try:
                    json.loads(literal)
                    syntax = True
                except ValueError:
                    syntax = False
            status = r.get("parse_status")
            responses.append(dict(page_id=page.page_id, json_valid=syntax,
                                  schema_valid=True if status == "valid" else False if status == "invalid" else None,
                                  output_budget_reached=r.get("output_budget_reached")))
    def validity(key):
        observed = [r[key] for r in responses if r[key] is not None]
        return dict(valid=sum(observed), evaluated=len(observed), unavailable=len(responses) - len(observed),
                    rate=sum(observed) / len(observed) if observed else None)
    history_path = source / method / "attempts.jsonl"
    history = read_jsonl(history_path) if history_path.is_file() else None
    selected = {p.page_id for p in pages}
    histories = Counter(r["page_id"] for r in history if r.get("page_id") in selected) if history is not None else None
    documents = defaultdict(list)
    for p in pages:
        documents[p.document_id].append(p.timings.get("page_wall_seconds"))
    return dict(
        expected_pages=expected_pages, observed_pages=len(pages),
        page_parse_valid=sum(p.parse_status == "valid" for p in pages) if generative else None,
        page_parse_rate=sum(p.parse_status == "valid" for p in pages) / expected_pages if generative and expected_pages else None,
        failed_pages=sum(p.status in ("failed", "unavailable") for p in pages),
        invalid_pages=sum(p.parse_status == "invalid" for p in pages),
        json_syntax=validity("json_valid"), saved_schema_validation=validity("schema_valid"),
        response_records=responses,
        repeated_page_attempts=sum(max(0, v - 1) for v in histories.values()) if histories is not None else None,
        model_retries=None,  # Tile, helper and resumed page calls are not necessarily retries.
        document_times=[dict(document_id=d, observed_pages=len(v),
                             page_wall_sum=sum(v) if all(x is not None for x in v) else None)
                        for d, v in documents.items()],
        start_regime="not_recorded",  # Loading and warm-up alone do not establish a controlled warm start.
        note="Letzte gespeicherte Antworten, keine vollständige Inferenzhistorie. JSON-Syntax strikt; Schema gemäß gespeichertem parse_status, keine unabhängige Revalidierung. Seitenwiederholungen sind keine Modell-Retries.",
    )


def costs_per_1000(extraction_config, *, documents, pages):
    config = CostsConfig.model_validate(extraction_config.get("costs") or {})
    scenario = cost_scenario(SimpleNamespace(costs=config))
    result = dict(
        measured_eur_per_1000=None,
        scenario_eur_per_1000=None,
        declared_measurement_eur_per_1000=None,
        status="unavailable",
        assumptions=scenario["assumptions"],
        source_status=scenario.get("status"),
        documents=documents,
        pages=pages,
        unit="EUR / 1000 documents",
        note="No independently traceable monetary measurement artifact; a configured kind is not verification.",
    )
    if (
        scenario.get("status") not in ("scenario", "measured")
        or not config.volume
        or not documents
        or not pages
    ):
        return result
    # Existing volume-based amounts refer to pages. Convert using observed pages/PDF,
    # never reinterpret page volume as number of documents. Review/development remain separate.
    amount = scenario["local_operating_eur"] + (scenario.get("energy_eur") or 0)
    normalized = amount / config.volume * (pages / documents) * 1000
    result.update(
        status="scenario" if config.kind == "scenario" else "declared_measurement_unverified",
        scenario_eur_per_1000=normalized if config.kind == "scenario" else None,
        declared_measurement_eur_per_1000=normalized if config.kind == "measured" else None,
        pages_per_document=pages / documents,
        excludes="review, development, manual time; no double-use as a measured inference cost",
    )
    return result
