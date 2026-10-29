"""Small controlled Docling experiments through the existing runner and evaluator."""

import html
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .config import Config, load_config
from .evaluation import evaluate_groups
from .io import file_hash, read_json, read_jsonl, write_csv, write_json
from .runner import run
from .schema import GroundTruthPage, PageResult
from .structure_diagnostics import diagnose_run
from .structured_mapping import extract_structured
from .table_mapping import extract_docling

VERSION = "docling-controlled-options-v1"


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
            people, _, _, context = converter(recognized, contexts[name].get(page["document_id"]))
            contexts[name][page["document_id"]] = context
            rows.append(dict(page_id=raw["page_id"], mapping=name, participants=len(people),
                organization_fields=sum(bool(p.department.value) for p in people),
                mapping_seconds=time.perf_counter()-started))
            predictions[name].append(PageResult.model_validate(dict(page, participants=[p.model_dump() for p in people])))
    metrics = {name: evaluate_groups(pages, truths)[0] for name, pages in predictions.items()} if truths else None
    return dict(rows=rows, metrics=metrics, quality_measured=truths is not None,
                basis="Same OCR/native grid; mapping-only comparison excludes OCR inference and model loading")


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
    summaries, mapping_rows = [], []
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
        mapping_rows.extend(dict(variant=name, **row) for row in comparison["rows"])
        summaries.append(dict(variant=name, **summary["docling"], run=str(source), diagnosis=str(diagnosis),
                              mapping_quality_measured=comparison["quality_measured"]))
        write_json(output / "summary.json", summaries)
    write_csv(output / "mapping_comparison.csv", mapping_rows)
    write_json(output / "identity.json", dict(version=VERSION, created_at=datetime.now(timezone.utc).isoformat(),
        config_sha256=file_hash(config_path), ground_truth_sha256=file_hash(truth_path) if truth_path else None,
        implementation={p.name: file_hash(p) for p in Path(__file__).parent.glob("*.py")},
        selection="No automatic winner: labeled development data and quality/runtime tradeoffs required"))
    rows = "".join(f'<tr><td>{html.escape(s["variant"])}</td><td>{s["status"]}</td>'
        f'<td>{s["output_text_fields"]//4}</td><td>{s["actual_method_wall_seconds"]:.2f}</td>'
        f'<td><a href="{Path(os.path.relpath(s["run"], output)).as_posix()}/report.html">Laufbericht</a> · '
        f'<a href="{Path(s["diagnosis"]).relative_to(output).as_posix()}/report.html">Diagnose</a> · '
        f'<a href="{s["variant"]}/mapping_comparison.json">Mappingvergleich</a></td></tr>' for s in summaries)
    (output / "report.html").write_text('<!doctype html><html lang="de"><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
        '<title>Docling-Konfigurationen vergleichen</title><h1>FAST / ACCURATE / Cell Matching</h1>'
        '<p>Identische Eingaben; OCR-Modus und Parameter sind pro Variante eingefroren. '
        'Ohne manuell geprüfte Referenz sind Teilnehmerzahlen keine Genauigkeitsmessung. '
        'Es wird kein Gewinner automatisch gewählt. Full-Page-OCR ist eine separat ausgewiesene Variante.</p>'
        '<p><a href="mapping_comparison.csv">Mappingvergleich CSV</a></p>'
        '<table><tr><th>Variante</th><th>Status</th><th>Personen</th><th>Sekunden</th><th>Details</th></tr>'+rows+'</table>', encoding="utf-8")
    return output
