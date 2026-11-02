"""Small controlled Docling experiments through the existing runner and evaluator."""

import html
import os
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .config import Config, load_config
from .evaluation import edits, evaluate_groups, normalized, ratio
from .io import file_hash, read_json, read_jsonl, write_csv, write_json
from .runner import run
from .schema import GroundTruthPage, PageResult
from .structure_diagnostics import diagnose_run
from .structured_mapping import extract_structured
from .table_mapping import extract_docling

VERSION = "docling-controlled-options-v2-complete-metrics"


def quality_summary(metrics, details):
    if metrics is None:
        return dict(quality_measured=False)
    aggregate = metrics["aggregate"]
    org = [row for row in details if row["field"] == "department" and normalized(row["truth_raw"], "department")]
    distance, length = 0, 0
    for row in details:
        left, right = (normalized(row[key], row["field"]) for key in ("truth_raw", "prediction_raw"))
        distance += edits(left, right)
        length += max(len(left), len(right))
    counts = aggregate["counts"]
    return dict(quality_measured=True, field_exact=aggregate["overall_exact_match"],
        organization_exact=aggregate["fields"]["department"]["exact_match"],
        organization_cer=aggregate["fields"]["department"]["cer"],
        organization_nonempty_coverage=ratio(sum(bool(row["prediction_raw"]) for row in org), len(org)),
        organization_nonempty_exact=ratio(sum(row["exact"] for row in org), len(org)),
        record_exact=ratio(counts["entry_tp"], counts["entry_tp"]+counts["entry_fn"]),
        match_coverage=aggregate["assignment"]["match_coverage"],
        normalized_edit_distance=ratio(distance, length),
        normalized_edit_distance_scope="Micro edits / max(reference,prediction) lengths over known reference fields; "
            "unmatched extra predictions are penalized separately by ordinary CER/PRF.",
        counts=counts)


def variants(config, include_full_page=False):
    output = []
    for mode in ("accurate", "fast"):
        for matching in (True, False):
            variant = config.model_copy(deep=True)
            variant.methods = ["docling"]
            settings = variant.structures["docling"]
            settings.table_mode, settings.do_cell_matching = mode, matching
            settings.mapping = "structured"
            settings.force_full_page_ocr = False
            output.append((f"{mode}-matching-{'on' if matching else 'off'}", Config.model_validate(variant.model_dump())))
    if include_full_page:
        variant = output[0][1].model_copy(deep=True)
        variant.structures["docling"].force_full_page_ocr = True
        output.append(("accurate-matching-on-full-page-ocr", variant))
    return output


def compare_mapping(source, truth_path=None):
    """Replay old/new deterministic mapping against identical immutable OCR output."""
    truths = [GroundTruthPage.model_validate(p) for p in read_jsonl(truth_path)] if truth_path else None
    rows, predictions = [], {"legacy_html": [], "structured": []}
    contexts = {"legacy_html": {}, "structured": {}}
    pages = {p["page_id"]: p for p in read_jsonl(source / "docling/extractions.jsonl")}
    for raw_path in sorted((source / "docling").glob("raw-*.json")):
        raw = read_json(raw_path)
        recognized = raw.get("structure")
        if not recognized:
            continue
        page = pages[raw["page_id"]]
        for name, converter in (("legacy_html", extract_docling), ("structured", extract_structured)):
            started = time.perf_counter()
            people, _, _, context = converter(deepcopy(recognized), contexts[name].get(page["document_id"]))
            contexts[name][page["document_id"]] = context
            rows.append(dict(page_id=raw["page_id"], mapping=name, participants=len(people),
                organization_fields=sum(bool(p.department.value) for p in people),
                mapping_seconds=time.perf_counter()-started))
            predictions[name].append(PageResult.model_validate(dict(page, participants=[p.model_dump() for p in people])))
    evaluated = {name: evaluate_groups(pages, truths) for name, pages in predictions.items()} if truths else {}
    metrics = {name: result[0] for name, result in evaluated.items()} if truths else None
    return dict(rows=rows, metrics=metrics, quality_measured=truths is not None,
                quality={name: quality_summary(*result) for name, result in evaluated.items()},
                field_details={name: result[1] for name, result in evaluated.items()},
                basis="Same OCR/native grid; mapping-only comparison excludes OCR inference and model loading")


def render_experiment(output, summaries, completed=False):
    def score(row, key):
        value = row.get("quality", {}).get(key, {}).get("value")
        return f"{100*value:.1f}%" if value is not None else "nicht gemessen"
    rows = "".join(f'<tr><td>{html.escape(s["variant"])}</td><td>{s["status"]}</td>'
        f'<td>{s["output_text_fields"]//4}</td><td>{score(s,"field_exact")}</td>'
        f'<td>{score(s,"organization_exact")}</td><td>{score(s,"record_exact")}</td>'
        f'<td>{score(s,"organization_cer")}</td><td>{s["actual_method_wall_seconds"]:.2f}</td>'
        f'<td><a href="{Path(os.path.relpath(s["run"], output)).as_posix()}/report.html">Laufbericht</a> · '
        f'<a href="{Path(s["diagnosis"]).relative_to(output).as_posix()}/report.html">Diagnose</a> · '
        f'<a href="{s["variant"]}/mapping_comparison.json">Vorher/Nachher, CER und Felddetails</a></td></tr>' for s in summaries)
    (output / "report.html").write_text('<!doctype html><html lang="de"><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
        '<title>Docling-Konfigurationen vergleichen</title><style>body{font:15px system-ui;margin:2rem}'
        'table{border-collapse:collapse}th,td{border:1px solid #ccc;padding:.5rem}</style>'
        '<h1>FAST / ACCURATE / Cell Matching</h1>'
        f'<p>Status: {"vollständig" if completed else "Zwischenstand"}; {len(summaries)} Varianten abgeschlossen.</p>'
        '<p>Identische Eingaben; Optionen sind pro Variante eingefroren. Ohne manuell geprüfte Referenz '
        'sind Teilnehmerzahlen keine Genauigkeitsmessung. Kein automatisch gewählter Gewinner. '
        'Full-Page-OCR ist eine getrennte Variante. CER: kleiner ist besser. '
        'Organisations-Exact-Match schließt explizit leere Referenzfelder ein; nichtleere Werte werden zusätzlich separat ausgewiesen.</p>'
        '<p><a href="mapping_comparison.csv">Mappingvergleich pro Seite</a> · '
        '<a href="quality_comparison.csv">Metriken Vorher/Nachher</a></p>'
        '<table><tr><th>Variante</th><th>Status</th><th>Personen</th><th>Feld exakt</th>'
        '<th>Organisation exakt</th><th>Datensatz exakt</th><th>Org.-CER</th><th>Sekunden</th><th>Details</th></tr>'+rows+'</table>', encoding="utf-8")


def experiment(folder, config_path, output, truth_path=None, include_full_page=False):
    output = output.resolve()
    if output.exists() or output.is_relative_to(folder.resolve()):
        raise ValueError("Experiment benötigt einen neuen Ausgabeordner außerhalb der Eingaben")
    if truth_path:
        labels = [GroundTruthPage.model_validate(row) for row in read_jsonl(truth_path)]
        if not labels or any(p.split != "development" for p in labels):
            raise ValueError("Strukturoptimierung akzeptiert ausschließlich development-Referenzen; Testset bleibt gesperrt")
    config = load_config(config_path)
    output.mkdir(parents=True)
    identity = dict(version=VERSION, created_at=datetime.now(timezone.utc).isoformat(), completed=False,
        config_sha256=file_hash(config_path), ground_truth_sha256=file_hash(truth_path) if truth_path else None,
        inputs={str(p.relative_to(folder)): file_hash(p) for p in sorted(folder.rglob("*"))
                if p.is_file() and p.suffix.lower()==".pdf"},
        implementation={p.name: file_hash(p) for p in Path(__file__).parent.glob("*.py")},
        selection="No automatic winner: labeled development data and quality/runtime tradeoffs required")
    write_json(output / "identity.json", identity)
    summaries, mapping_rows, quality_rows = [], [], []
    render_experiment(output, summaries)
    for name, variant in variants(config, include_full_page):
        # Reuse the ordinary flat run directory: nested SHA256 attempt paths
        # otherwise exceed MAX_PATH on Windows. Summary/HTML retain run links.
        variant.output_dir = str(Path(config.output_dir).resolve())
        snapshot = output / name / "variant.yaml"
        snapshot.parent.mkdir(parents=True)
        snapshot.write_text(yaml.safe_dump(variant.model_dump(), allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"Strukturvergleich: {name}; nur lokale Docling-Modelle", flush=True)
        # All supplied labels were checked above. The ordinary runner's --split
        # filters curated manifests, not raw folders, so no synthetic manifest is invented.
        source, summary = run(variant, folder, truth_path=truth_path, split="all", offline=True)
        diagnosis = diagnose_run(source, output / name / "diagnostics", ["docling"])
        comparison = compare_mapping(source, truth_path)
        write_json(output / name / "mapping_comparison.json", comparison)
        for mapping, quality in comparison["quality"].items():
            quality_rows.append(dict(variant=name, mapping=mapping,
                **{key: value.get("value") for key,value in quality.items() if isinstance(value,dict) and "value" in value}))
            write_csv(output / name / f"{mapping}_fields.csv", comparison["field_details"][mapping])
        mapping_rows.extend(dict(variant=name, **row) for row in comparison["rows"])
        summaries.append(dict(variant=name, **summary["docling"], run=str(source), diagnosis=str(diagnosis),
                              quality=comparison["quality"].get("structured", dict(quality_measured=False)),
                              mapping_quality_measured=comparison["quality_measured"]))
        write_json(output / "summary.json", summaries)
        write_csv(output / "mapping_comparison.csv", mapping_rows)
        write_csv(output / "quality_comparison.csv", quality_rows, fields=None if quality_rows else ["variant","mapping"])
        render_experiment(output, summaries)
    write_csv(output / "mapping_comparison.csv", mapping_rows)
    write_json(output / "identity.json", dict(identity, completed=True, completed_at=datetime.now(timezone.utc).isoformat()))
    render_experiment(output, summaries, completed=True)
    return output
