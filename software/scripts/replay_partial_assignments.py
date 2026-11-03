"""Replay only validation of frozen Paddle responses, isolating retained information from OCR improvements."""

import argparse
import shutil
import time
from pathlib import Path

from participant_bench.document_names import DocumentNameOrders
from participant_bench.excel_reference import ReferencePerson
from participant_bench.io import file_hash, read_json, read_jsonl, write_json, write_jsonl
from participant_bench.person_roles import filter_page_people
from participant_bench.report import report
from participant_bench.roster_benchmark.config import BenchmarkConfig
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.roster_benchmark.references import ReferenceData
from participant_bench.schema import TEXT_FIELDS, NameOrderDecision, PageResult
from participant_bench.structure_assignment import (
    comma_names,
    ground_positions,
    position_matches,
    prepare_rows,
    source_boxes,
)
from participant_bench.structure_diagnostics import diagnose_run
from participant_bench.unlimited_assignment import ground_response, parse_assignment_response


def run(source_report, output):
    source_report, output = source_report.resolve(), output.resolve()
    if output.exists():
        raise ValueError("Neuen Ausgabeordner wählen")
    identity = read_json(source_report / "identity.json")
    source = Path(identity["source_run"])
    if output.is_relative_to(source):
        raise ValueError("Ausgabe außerhalb der Originale wählen")
    protected = {p: file_hash(p) for root in (source, source_report) for p in root.rglob("*") if p.is_file()}
    working = output / "source"
    shutil.copytree(source, working)
    pages = [PageResult.model_validate(row) for row in read_jsonl(working / "paddle_llm/extractions.jsonl")]
    orders, measurements = DocumentNameOrders(), []
    for page in pages:
        path = working / "paddle_llm" / f"raw-{page.page_id}.json"
        raw = read_json(path)
        assignment = raw["assignment"]
        rows, _, _ = prepare_rows(raw["structure"], "paddle_structure")
        started = time.perf_counter()
        rejected = []
        parsed = parse_assignment_response(assignment["raw_response"], rejected, rows)
        historical = {
            key: assignment.get(key)
            for key in (
                "rejected_rows",
                "participants_before_validation",
                "participants_after_literal_grounding",
                "participants_after_position_validation",
            )
        }
        assignment["participants_before_validation"] = [p.model_dump() for p in parsed.participants]
        if parsed.name_order is None and assignment.get("name_order"):
            parsed.name_order = NameOrderDecision.model_validate(assignment["name_order"])
        orders.prepare_assignment(parsed, rows, page.document_id, page.page_number)
        bands = assignment.get("current_field_bands") or assignment.get("previous_field_bands") or {}
        if (
            not assignment.get("current_field_bands")
            and assignment.get("position_context_origin") == "grounded_positions"
        ):
            bands = {field: band for field, band in bands.items() if field == "personnel_number"}
        if parsed.name_order is None:
            comma_names(parsed, rows, bands)
        ambiguous = assignment.get("ambiguous_fields", [])
        bounds = assignment.get("name_column_bounds")

        def validator(field, cell, match):
            if field in ambiguous or not position_matches(field, cell, match, bands):
                return False
            if bounds and field in ("first_name", "last_name") and match:
                return all(
                    bounds[0] <= (box["x0"] + box["x1"]) / 2 < bounds[1]
                    for box in source_boxes(cell, match.span())
                )
            return True

        people, proofs, notes = ground_response(
            parsed,
            rows,
            trusted_headers=False,
            source_label="paddle_llm",
            field_validator=validator,
            require_name=assignment.get("name_column_hint") is not None,
        )
        assignment["participants_after_literal_grounding"] = [p.model_dump() for p in people]
        ground_positions(people, proofs, rows, bands)
        assignment["participants_after_position_validation"] = [p.model_dump() for p in people]
        before = len(page.participants)
        page.participants, page.status, page.parse_status = people, "partial", "valid"
        page.text_fallback, page.review_notes = (
            not people,
            notes + ["Frozen response validation replay; no new OCR or LLM inference"],
        )
        orders.apply(page, raw, parsed.name_order)
        filter_page_people(page, raw)
        raw["structure"]["row_evidence"] = proofs
        assignment["historical_validation"] = historical
        assignment.update(
            rejected_rows=rejected,
            row_evidence=proofs,
            replay_kind="partial-field-validation-only",
            schema_policy="Omitted fields remain unknown; literal, type and position checks unchanged",
            new_inference=False,
        )
        write_json(path, raw)
        measurements.append(
            dict(
                page_number=page.page_number,
                before=before,
                after=len(page.participants),
                seconds=time.perf_counter() - started,
                schema_rejections=len(rejected),
            )
        )
    write_jsonl(working / "paddle_llm/extractions.jsonl", [page.model_dump() for page in pages])
    summary = read_json(working / "summary.json")
    summary["paddle_llm"]["validation_replay_seconds"] = sum(row["seconds"] for row in measurements)
    summary["paddle_llm"].update(
        text_fallback_pages=sum(p.text_fallback for p in pages),
        output_text_fields=sum(len(p.participants) * len(TEXT_FIELDS) for p in pages),
        output_unknown_text_fields=sum(
            getattr(person, field).state not in ("read", "empty")
            for p in pages
            for person in p.participants
            for field in TEXT_FIELDS
        ),
        output_signature_fields=sum(len(p.participants) for p in pages),
        output_unknown_signatures=sum(
            person.signature_present is None for p in pages for person in p.participants
        ),
    )
    write_json(working / "summary.json", summary)
    write_json(
        working / "validation_replay.json",
        dict(original=str(source), new_inference=False, measurements=measurements),
    )
    source_identity = read_json(working / "identity.json")
    source_identity["validation_replay"] = dict(
        original=str(source),
        method="paddle_llm",
        new_inference=False,
        script_sha256=file_hash(Path(__file__)),
    )
    write_json(working / "identity.json", source_identity)
    results = {
        method: [
            PageResult.model_validate(item) for item in read_jsonl(working / method / "extractions.jsonl")
        ]
        for method in summary
        if (working / method / "extractions.jsonl").is_file()
    }
    report(
        working, summary, results, {}, read_json(working / "manifest.json"), read_json(working / "costs.json")
    )
    snapshot = read_json(source_report / "reference_snapshot.json")
    frozen = ReferenceData(
        [ReferencePerson(**row) for row in snapshot["people"]],
        identity.get("reference_sheet"),
        snapshot.get("duplicate_rows", []),
        True,
        snapshot.get("columns", {}),
    )
    config = BenchmarkConfig.model_validate(read_json(source_report / "config.json"))
    comparison, metrics = evaluate_run(
        working,
        Path(identity["reference_file"]),
        config,
        output,
        output=output / "comparison",
        frozen_reference=(frozen, identity["reference_sha256"]),
    )
    diagnose_run(working, output / "diagnosis", methods=["paddle_llm", "docling"])
    assert all(file_hash(path) == expected for path, expected in protected.items())
    write_json(
        output / "replay.json",
        dict(
            original_files_unchanged=True,
            new_inference=False,
            original_report=str(source_report),
            comparison=str(comparison),
            measurements=measurements,
            before=read_json(source_report / "metrics.json")["methods"],
            after=metrics,
        ),
    )
    return comparison


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(run(args.source_report, args.output))
