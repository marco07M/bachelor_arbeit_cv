"""Regrade frozen results and isolate a repaired Docling run; never change historical artifacts."""

import argparse
import shutil
from pathlib import Path

from participant_bench.excel_reference import ReferencePerson
from participant_bench.io import file_hash, read_json, read_jsonl, write_json
from participant_bench.report import report
from participant_bench.roster_benchmark.config import BenchmarkConfig
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.roster_benchmark.references import ReferenceData
from participant_bench.schema import PageResult


def audit(source_report, docling_run, output):
    source_report, docling_run, output = (p.resolve() for p in (source_report, docling_run, output))
    if output.exists():
        raise ValueError("Audit benötigt einen neuen Ausgabeordner")
    identity = read_json(source_report / "identity.json")
    source = Path(identity["source_run"])
    if output.is_relative_to(source) or output.is_relative_to(docling_run):
        raise ValueError("Audit darf nicht im historischen Quelllauf liegen")
    protected = [p for root in (source_report, source, docling_run) for p in root.rglob("*") if p.is_file()]
    hashes = {p: file_hash(p) for p in protected}
    prepared = [read_json(p / "effective_pages.json") for p in (source, docling_run)]
    def pixels(pages):
        return {(p["document_id"], p["page_number"]): p["run_image_sha256"] for p in pages if p["include"]}
    if pixels(prepared[0]) != pixels(prepared[1]):
        raise ValueError("Docling-Gegenprobe hat andere Laufbilder")
    for root, pages in zip((source, docling_run), prepared):
        for page in pages:
            if page["include"] and file_hash(root / "pages" / f"{page['page_id']}.png") != page["run_image_sha256"]:
                raise ValueError("Ein tatsächliches Laufbild wurde verändert")
    snapshot = read_json(source_report / "reference_snapshot.json")
    frozen = ReferenceData([ReferencePerson(**p) for p in snapshot["people"]], identity.get("reference_sheet"),
                           snapshot.get("duplicate_rows", []), True, snapshot.get("columns", {}))
    config = BenchmarkConfig.model_validate(read_json(source_report / "config.json"))
    reference = Path(identity["reference_file"])
    output.mkdir(parents=True)
    results = {}
    for label, compare_names in (("corrected-rules", False), ("both-name-orders", True)):
        candidate = config.model_copy(deep=True)
        candidate.matching.compare_name_orientations = compare_names
        folder, metrics = evaluate_run(source, reference, candidate, output, output=output / label,
                                      frozen_reference=(frozen, identity["reference_sha256"]))
        results[label] = dict(report=str(folder / "report.html"), methods=metrics)
    combined = output / "combined-source"
    shutil.copytree(source, combined)
    # These are new working copies, not edits of historical extractions.
    shutil.copytree(docling_run / "docling", combined / "docling", dirs_exist_ok=True)
    summary = read_json(source / "summary.json")
    summary["docling"] = read_json(docling_run / "summary.json")["docling"]
    write_json(combined / "summary.json", summary)
    write_json(combined / "audit_sources.json", dict(original=str(source), docling=str(docling_run),
               same_run_images=True, other_methods_reinferred=False))
    combined_identity = read_json(combined / "identity.json")
    combined_identity["audit_provenance"] = dict(kind="composite_fixed_predictions", original=str(source),
                                               docling=str(docling_run), other_methods_reinferred=False)
    write_json(combined / "identity.json", combined_identity)
    by_method = {method: [PageResult.model_validate(item) for item in read_jsonl(combined / method / "extractions.jsonl")]
                 for method in summary if (combined / method / "extractions.jsonl").is_file()}
    report(combined, summary, by_method, {}, read_json(combined / "manifest.json"), read_json(combined / "costs.json"))
    recognition_calls = sum(page.calls for page in by_method.get("docling", []))
    candidate = config.model_copy(deep=True)
    candidate.matching.compare_name_orientations = True
    folder, metrics = evaluate_run(combined, reference, candidate, output, output=output / "repaired-docling",
                                  frozen_reference=(frozen, identity["reference_sha256"]))
    results["repaired-docling"] = dict(report=str(folder / "report.html"), methods=metrics)
    unchanged = all(file_hash(p) == fingerprint for p, fingerprint in hashes.items())
    if not unchanged:
        raise ValueError("Historische Artefakte wurden während des Audits verändert")
    write_json(output / "audit.json", dict(source_report=str(source_report), docling_run=str(docling_run),
        historical_artifacts_unchanged=unchanged, reference_sha256=identity["reference_sha256"],
        same_run_images=True, new_inference=bool(recognition_calls), docling_recognition_calls=recognition_calls,
        docling_pipeline_reexecuted=True, results=results))
    links = "".join(f'<li><a href="{label}/report.html">{label}</a></li>' for label in results)
    (output / "report.html").write_text('<!doctype html><html lang="de"><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
        '<title>Evaluationsaudit</title><h1>Kontrollierter Evaluationsvergleich</h1>'
        '<p>Dieselben eingefrorenen Referenzen und Laufbilder. Erst nur Bewertungsregeln korrigiert, '
        'dann beide Namensrollen geprüft, anschließend neue Docling-Ausgabe. Andere Modelle unverändert.</p>'
        f'<ul>{links}</ul><p><a href="audit.json">Prüfprotokoll und Kennzahlen</a></p></html>', encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--docling-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(audit(arguments.source_report, arguments.docling_run, arguments.output))
