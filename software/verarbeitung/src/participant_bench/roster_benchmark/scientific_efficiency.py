"""Observed effort and explicit cost assumptions; no inference or invented measurements."""

import math
from collections import defaultdict
from types import SimpleNamespace

import numpy as np

from ..config import CostsConfig
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
