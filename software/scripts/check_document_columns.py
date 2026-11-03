"""Check document-column state on frozen evidence and compare a separate local Paddle assignment.

No model is loaded here. Use assign-structures first if a new Paddle prompt run is
desired. Reference values are opened only after extraction and layout decisions.
"""

import argparse
import csv
import shutil
import time
from pathlib import Path

from PIL import Image

from participant_bench.excel_reference import ReferencePerson
from participant_bench.io import file_hash, read_json, read_jsonl, write_json, write_jsonl
from participant_bench.ocr_layout import with_table_columns
from participant_bench.report import refresh_report
from participant_bench.roster_benchmark.config import BenchmarkConfig
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.roster_benchmark.references import ReferenceData
from participant_bench.structured_mapping import VERSION, extract_structured


def run(source_report, output, paddle_run=None):
    source_report, output = source_report.resolve(), output.resolve()
    identity = read_json(source_report / "identity.json")
    source = Path(identity["source_run"])
    if output.exists() or output.is_relative_to(source) or output.is_relative_to(source_report):
        raise ValueError("Neuer Ausgabeordner außerhalb der historischen Läufe erforderlich")
    protected = {p: file_hash(p) for root in (source, source_report) for p in root.rglob("*") if p.is_file()}
    if paddle_run:
        provenance = read_json(paddle_run / "assignment_recheck.json")
        if Path(provenance["source_run"]).resolve() != source.resolve():
            raise ValueError("Paddle-Vergleich muss dieselben eingefrorenen OCR-Belege verwenden")
        protected.update({p: file_hash(p) for p in paddle_run.rglob("*") if p.is_file()})
    working = output / "source"
    shutil.copytree(source, working)
    summary = read_json(working / "summary.json")
    measurements = []
    for method in ("ocr_llm", "docling"):
        context = {}
        pages = read_jsonl(working / method / "extractions.jsonl")
        for page in sorted(pages, key=lambda p: (p["document_id"], p["page_number"])):
            path = working / method / ("raw-" + page["page_id"] + ".json")
            raw = read_json(path)
            started = time.perf_counter()
            before = len(page["participants"])
            if method == "docling":
                people, proofs, notes, state = extract_structured(raw["structure"], context.get(page["document_id"]),
                    document_id=page["document_id"], page_number=page["page_number"])
                context[page["document_id"]] = state
                page["participants"] = [p.model_dump() for p in people]
                page.update(review_notes=notes, text_fallback=not people)
                raw["structure"].update(row_evidence=proofs, table_mapping_context=state, mapping_version=VERSION)
                traces = raw["structure"]["mapping_diagnostics"]
            else:
                with Image.open(working / "pages" / (page["page_id"] + ".png")) as image:
                    layout = with_table_columns(raw["ocr"], image, context.get(page["document_id"]),
                        document_id=page["document_id"], page_number=page["page_number"])
                # A changed prompt requires new inference, never reinterpret an old answer silently.
                if layout["column_mapping"]:
                    raise ValueError("Tesseract has usable headers; run its new prompt separately before comparing")
                context[page["document_id"]] = layout
                raw["ocr_layout_analysis"] = {key: layout[key] for key in ("physical_columns", "text_rows",
                    "name_column_hint", "inherited_name_column", "context_rows", "column_mapping",
                    "column_mapping_context", "mapping_provenance")}
                traces = [layout["mapping_provenance"]]
            measurements.append(dict(method=method, page_number=page["page_number"], before_participants=before,
                after_participants=len(page["participants"]), mapping=traces, seconds=time.perf_counter()-started))
            write_json(path, raw)
        write_jsonl(working / method / "extractions.jsonl", pages)
        write_jsonl(working / method / "raw.jsonl", [read_json(working / method / ("raw-"+p["page_id"]+".json")) for p in pages])
        summary[method]["column_layout_recheck_seconds"] = sum(m["seconds"] for m in measurements if m["method"] == method)
    if paddle_run:
        # Copy into a fresh sibling to avoid any deletion of source/historical artifacts.
        destination = working / "paddle_llm_new"
        shutil.copytree(paddle_run / "paddle_llm", destination)
        original = working / "paddle_llm"
        archived = working / "paddle_llm_historical"
        if not all(p.resolve().is_relative_to(working.resolve()) for p in (destination, original, archived)):
            raise ValueError("Arbeitskopien müssen innerhalb des neuen Ausgabeordners bleiben")
        original.rename(archived)
        destination.rename(original)
        new_summary = read_json(paddle_run / "summary.json")["paddle_llm"]
        summary["paddle_llm"] = dict(new_summary, actual_method_wall_seconds=new_summary["assignment_wall_seconds"],
            timing_scope="new_assignment_only_not_full_pipeline", original_pipeline_seconds=summary["paddle_llm"].get("actual_method_wall_seconds"))
        for page in read_jsonl(original / "extractions.jsonl"):
            raw = read_json(original / ("raw-"+page["page_id"]+".json"))
            measurements.append(dict(method="paddle_llm", page_number=page["page_number"],
                after_participants=len(page["participants"]), mapping=raw["assignment"].get("document_column_mapping"),
                seconds=page.get("timings", {}).get("assignment_seconds")))
    write_json(working / "summary.json", summary)
    run_identity = read_json(working / "identity.json")
    run_identity["document_column_recheck"] = dict(source_run=str(source), new_ocr_inference=False,
        new_llm_inference=bool(paddle_run), script_sha256=file_hash(Path(__file__)))
    write_json(working / "identity.json", run_identity)
    refresh_report(working)
    # Reference access begins here, after every extraction decision above.
    snapshot = read_json(source_report / "reference_snapshot.json")
    reference = ReferenceData([ReferencePerson(**row) for row in snapshot["people"]], identity.get("reference_sheet"),
        snapshot.get("duplicate_rows", []), True, snapshot.get("columns", {}))
    config = BenchmarkConfig.model_validate(read_json(source_report / "config.json"))
    comparison, metrics = evaluate_run(working, Path(identity["reference_file"]), config, output,
        output=output / "comparison", frozen_reference=(reference, identity["reference_sha256"]))
    def exact_fields(folder):
        with (folder / "fields.csv").open(encoding="utf-8-sig", newline="") as stream:
            return {(r["method"], r["class_id"], r["reference_row"], r["field"]): r["exact"] == "True"
                    for r in csv.DictReader(stream) if r["reference_contribution"] == "1"}
    old, new = exact_fields(source_report), exact_fields(comparison)
    changes = {}
    for method in summary:
        keys = [k for k in old if k[0] == method]
        changes[method] = dict(retained_correct=sum(old[k] and new.get(k, False) for k in keys),
            newly_correct=sum(not old[k] and new.get(k, False) for k in keys),
            lost_correct=sum(old[k] and not new.get(k, False) for k in keys))
    assert all(file_hash(path) == value for path, value in protected.items())
    write_json(output / "check.json", dict(original_files_unchanged=True, measurements=measurements,
        before=read_json(source_report / "metrics.json")["methods"], after=metrics, changes=changes,
        source=str(source), original_report=str(source_report), new_ocr_inference=False,
        new_llm_inference=bool(paddle_run), script_sha256=file_hash(Path(__file__))))
    return comparison


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--paddle-run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(run(args.source_report, args.output, args.paddle_run))
