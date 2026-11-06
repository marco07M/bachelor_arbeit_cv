"""Frozen-answer before/after comparison; references are loaded only after completion.

No OCR/model inference, no edited answers, no historical output overwrite.
The measured additional time is postprocessing only, never full-pipeline runtime.
"""

import argparse
import time
from pathlib import Path
from shutil import copytree

from participant_bench.excel_reference import ReferencePerson
from participant_bench.io import file_hash, read_json, read_jsonl, write_json, write_jsonl
from participant_bench.ocr_observations import audit
from participant_bench.report import refresh_report
from participant_bench.roster_benchmark.config import BenchmarkConfig
from participant_bench.roster_benchmark.detail_report import document, read_csv, table
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.roster_benchmark.references import ReferenceData
from participant_bench.schema import PageResult
from participant_bench.structure_assignment import (
    complete_observed_cells,
    document_bands,
    header_bands,
    prepare_rows,
)
from participant_bench.unlimited_assignment import select_person_rows


def run(source_report: Path, output: Path):
    source_report, output = source_report.resolve(), output.resolve()
    identity = read_json(source_report / "identity.json")
    source = Path(identity["source_run"]).resolve()
    if output.exists() or any(output.is_relative_to(p) for p in (source, source_report)):
        raise ValueError("Neuen Ausgabeordner außerhalb historischer Ergebnisse wählen")
    protected = {p: file_hash(p) for root in (source, source_report) for p in root.rglob("*") if p.is_file()}
    working = output / "source"
    copytree(source, working)
    records = []
    for method in ("paddle_llm",):
        context, pages, raws = None, [], []
        for record in read_jsonl(working / method / "extractions.jsonl"):
            page = PageResult.model_validate(record)
            path = working / method / ("raw-"+page.page_id+".json")
            raw = read_json(path)
            if raw.get("person_role_filter", {}).get("excluded"):
                raise ValueError("Dieser Replay erwartet Personen ohne nachträgliche Indexverschiebung")
            started = time.perf_counter()
            recognized = raw["structure"]
            rows, _, _ = prepare_rows(recognized, "paddle_structure")
            _, context, trace = document_bands(recognized, rows, header_bands(rows), context,
                                              document_id=page.document_id, page_number=page.page_number)
            selected, hint = select_person_rows(rows)
            if hint is not None:
                rows = [dict(row, id=f"r{i+1}", original_source_row=row["id"]) for i, row in enumerate(selected)]
            raw["quality_recheck_before_completion"] = dict(participants=[p.model_dump() for p in page.participants],
                document_column_mapping=recognized.get("document_column_mapping"))
            changes = complete_observed_cells(page.participants, recognized["row_evidence"], rows, trace)
            seconds = time.perf_counter()-started
            raw["quality_recheck"] = dict(mapping=trace, completions=changes, postprocessing_seconds=seconds,
                                         frozen_model_answers=True, new_inference=False)
            raw["ocr_observation_audit"] = audit(raw, page)
            write_json(path, raw)
            pages.append(page.model_dump())
            raws.append(raw)
            records.append(dict(method=method, page_number=page.page_number, completed_fields=len(changes),
                                people=len(page.participants), postprocessing_seconds=seconds))
        write_jsonl(working / method / "extractions.jsonl", pages)
        write_jsonl(working / method / "raw.jsonl", raws)
    summary = read_json(working / "summary.json")
    for method in summary:
        summary[method]["historical_method_wall_seconds"] = summary[method].get("actual_method_wall_seconds")
        summary[method]["actual_method_wall_seconds"] = None
        summary[method]["timing_scope"] = "frozen_ocr_and_model_answers_postprocessing_replay"
        summary[method]["additional_postprocessing_seconds"] = sum(r["postprocessing_seconds"] for r in records if r["method"] == method)
    write_json(working / "summary.json", summary)
    provenance_path = working / "identity.json"
    provenance = read_json(provenance_path) if provenance_path.is_file() else {}
    provenance["extraction_quality_replay"] = dict(source_run=str(source), frozen_model_answers=True,
        new_inference=False, script_sha256=file_hash(Path(__file__)), stages=records)
    write_json(provenance_path, provenance)
    refresh_report(working)
    # Extraction is now frozen. Only evaluation reads the unchanged reference snapshot.
    snapshot = read_json(source_report / "reference_snapshot.json")
    reference = ReferenceData([ReferencePerson(**r) for r in snapshot["people"]], identity.get("reference_sheet"),
        snapshot.get("duplicate_rows", []), True, snapshot.get("columns", {}))
    config = BenchmarkConfig.model_validate(read_json(source_report / "config.json"))
    before_path, before = evaluate_run(source, Path(identity["reference_file"]), config, output,
        output=output / "before", frozen_reference=(reference, identity["reference_sha256"]))
    after_path, after = evaluate_run(working, Path(identity["reference_file"]), config, output,
        output=output / "after", frozen_reference=(reference, identity["reference_sha256"]))
    saved = read_json(source_report / "metrics.json")["methods"]
    for method, score in before.items():
        if "overall" in score:
            assert all(score["overall"][key] == saved[method]["overall"][key] for key in (
                "exact_fields", "incorrect_fields", "missing_fields", "reference_fields", "predicted_fields")), (
                "Die unveränderte Ausgangsauswertung muss dieselben Zähler reproduzieren")
    def correct(folder):
        return {(r["method"], r["class_id"], r["reference_row"], r["field"]): r["exact"] == "True"
                for r in read_csv(folder / "fields.csv") if r["reference_contribution"] == "1"}
    old, new = correct(before_path), correct(after_path)
    changes = {method: dict(retained_correct=sum(old[k] and new.get(k, False) for k in old if k[0] == method),
        newly_correct=sum(not old[k] and new.get(k, False) for k in old if k[0] == method),
        lost_correct=sum(old[k] and not new.get(k, False) for k in old if k[0] == method)) for method in before}
    assert all(file_hash(p) == value for p, value in protected.items())
    result = dict(source_report=str(source_report), source_run=str(source), stages=records, changes=changes,
        before=before, after=after, original_files_unchanged=True, new_inference=False,
        runtime_scope="Additional postprocessing measured; historical full-pipeline time is not a new measurement",
        script_sha256=file_hash(Path(__file__)))
    write_json(output / "comparison.json", result)
    content = '<h1>Extraktionsqualität: kontrollierter Vorher-/Nachher-Vergleich</h1><p><a href="before/report.html">Vorher mit Fehleranalyse</a> · <a href="after/report.html">Nachher mit Fehleranalyse</a> · <a href="comparison.json">Messprotokoll</a></p>'
    content += '<p>Identische Seitenbilder, OCR, Modellantworten und eingefrorene Referenz. Neue Verarbeitung ergänzt ausschließlich eindeutig belegte aktuelle Zellen. Keine neue Inferenz; zusätzliche Nachbearbeitungszeit separat ausgewiesen.</p>'
    content += table(["Verfahren", "Vorher exakt", "Nachher exakt", "Neue Treffer", "Verlorene Treffer"],
        [[m, changes[m]["retained_correct"]+changes[m]["lost_correct"], changes[m]["retained_correct"]+changes[m]["newly_correct"],
          changes[m]["newly_correct"], changes[m]["lost_correct"]] for m in changes])
    (output / "report.html").write_text(document("Vorher/Nachher", content), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.source_report, args.output)
    print({"changes": result["changes"], "stages": result["stages"], "historical_files_unchanged": result["original_files_unchanged"]})
