"""Compare two existing runs against one frozen roster; never perform inference."""

import argparse
import csv
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from participant_bench.io import file_hash, read_json, write_csv, write_json
from participant_bench.roster_benchmark.config import load_config
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.roster_benchmark.matching import normalize
from participant_bench.roster_benchmark.references import read_reference


def paired_fields(before, after):
    def indexed(rows):
        return {
            (r["method"], r["class_id"], r["reference_row"], r["field"]): r
            for r in rows
            if r.get("reference_row") not in (None, "", "None")
        }

    a, b = indexed(before), indexed(after)
    counters, rows = defaultdict(Counter), []
    for key in sorted(a.keys() | b.keys()):
        left, right = a.get(key, {}), b.get(key, {})
        if left and right and left["reference_value"] != right["reference_value"]:
            raise ValueError("Vergleiche benötigen dieselbe unveränderte Referenz")
        x, y = left.get("exact") == "True", right.get("exact") == "True"
        transition = (
            "not_comparable"
            if left.get("assessable") != "True" or right.get("assessable") != "True"
            else "both_correct"
            if x and y
            else "corrected"
            if y
            else "regressed"
            if x
            else "both_incorrect"
        )
        counters[key[0]].update({transition: 1})
        rows.append(
            dict(
                zip(("method", "class_id", "reference_row", "field"), key),
                reference_value=(left or right)["reference_value"],
                baseline_value=left.get("prediction_value"),
                optimized_value=right.get("prediction_value"),
                baseline_page=left.get("page_number"),
                optimized_page=right.get("page_number"),
                transition=transition,
            )
        )
    return {method: dict(c) for method, c in counters.items()}, rows


def compare(baseline, optimized, reference, output, config_path=Path("testframework/config.yaml")):
    if output.exists():
        raise FileExistsError("Vergleich benötigt einen neuen Ausgabeordner")
    manifests = [read_json(source / "manifest.json") for source in (baseline, optimized)]

    def scope(manifest):
        return {
            (p["document_id"], p["page_number"], p["image_sha256"], p["include"]) for p in manifest["pages"]
        }

    if scope(manifests[0]) != scope(manifests[1]):
        raise ValueError("Eingabeseiten, Bild-Hashes oder Auswahl unterscheiden sich")
    effective = [read_json(source / "effective_pages.json") for source in (baseline, optimized)]

    def prepared_scope(pages):
        return {
            (p["document_id"], p["page_number"], p["include"], p.get("run_image_sha256"))
            for p in pages
        }

    if any(p["include"] and not p.get("run_image_sha256") for pages in effective for p in pages):
        raise ValueError("Tatsächliche Laufbilder sind nicht vollständig durch Hashes belegt")
    if prepared_scope(effective[0]) != prepared_scope(effective[1]):
        raise ValueError("Tatsächlich verwendete Laufbilder unterscheiden sich")
    for source, pages in zip((baseline, optimized), effective):
        for page in pages:
            if page["include"] and file_hash(source / "pages" / f"{page['page_id']}.png") != page["run_image_sha256"]:
                raise ValueError("Ein gespeichertes Laufbild wurde verändert")
    frozen_configs = [
        yaml.safe_load((source / "config.yaml").read_text(encoding="utf-8"))
        for source in (baseline, optimized)
    ]
    for section in ("pdf", "ocr"):
        if frozen_configs[0].get(section) != frozen_configs[1].get(section):
            raise ValueError(f"Gemeinsame Vorverarbeitung unterscheidet sich: {section}")
    model_configs = [c.get("models", {}).get("ocr_llm") for c in frozen_configs]
    if not model_configs[0] or model_configs[0] != model_configs[1]:
        raise ValueError("LLM-Modell oder Inferenzparameter unterscheiden sich")
    config = load_config(config_path)
    reference_hash = file_hash(reference)
    frozen = (read_reference(reference, config.reference), reference_hash)
    if file_hash(reference) != reference_hash:
        raise ValueError("Referenz wurde während des Einlesens verändert")
    output.mkdir(parents=True)
    methods = [
        m
        for m in ("docling", "paddle_llm")
        if all((s / m / "extractions.jsonl").is_file() for s in (baseline, optimized))
    ]
    if not methods:
        raise ValueError("Keine gemeinsamen Docling-/Paddle-Ergebnisse")
    comparisons, metrics, fields = [], [], []
    for label, source in (("baseline", baseline), ("optimized", optimized)):
        report, scores = evaluate_run(
            source, reference, config, output / label, methods, frozen_reference=frozen
        )
        comparisons.append(report)
        metrics.append(scores)
        with (report / "fields.csv").open(encoding="utf-8-sig", newline="") as stream:
            fields.append(list(csv.DictReader(stream)))
    changes, details = paired_fields(*fields)
    write_csv(output / "field_changes.csv", details)
    rows = []
    for label, source, scores, values in zip(
        ("baseline", "optimized"), (baseline, optimized), metrics, fields
    ):
        timing = read_json(source / "summary.json")
        for method in methods:
            score = scores[method]
            selected = [r for r in values if r["method"] == method and r["assessable"] == "True"]
            distance = sum(int(r["levenshtein_distance"]) for r in selected if r["levenshtein_distance"])
            lengths = [
                (
                    len(normalize(r["reference_value"], r["field"], config.matching)),
                    len(normalize(r["prediction_value"], r["field"], config.matching)),
                )
                for r in selected
                if r["reference_row"]
            ]
            reference_chars = sum(a for a, _ in lengths)
            max_chars = sum(max(a, b) for a, b in lengths)
            rows.append(
                dict(
                    variant=label,
                    method=method,
                    reference_rows=score["reference_participants"],
                    assigned_rows=score["assigned_participants"],
                    missing_rows=score["missing_participants"],
                    extra_rows=score["extra_participants"],
                    field_exact=score["overall"]["exact_reference_accuracy"],
                    organization_exact=score["fields"]["short_code"]["exact_reference_accuracy"],
                    record_exact=score["fully_exact_participant_recall"],
                    soft_f1=score["overall"]["soft_f1"],
                    paired_cer=distance / reference_chars if reference_chars else None,
                    normalized_edit_distance=distance / max_chars if max_chars else None,
                    seconds=timing[method]["actual_method_wall_seconds"],
                    charged_seconds=timing[method]["full_pipeline_charged_seconds"],
                )
            )
    write_csv(output / "quality_comparison.csv", rows)
    page_groups = defaultdict(Counter)
    for label, values in zip(("baseline", "optimized"), fields):
        for row in values:
            if row["assessable"] == "True" and row.get("reference_row"):
                page_groups[(label, row["method"], row["page_number"] or "unassigned_reference")].update(
                    assessed_fields=1, exact_fields=int(row["exact"] == "True")
                )
    write_csv(
        output / "page_diagnostics.csv",
        [
            dict(
                variant=key[0],
                method=key[1],
                prediction_page=key[2],
                **counts,
                conditional_field_exact=counts["exact_fields"] / counts["assessed_fields"],
                limitation="Page of the matched prediction only; missing reference persons have no verified page",
            )
            for key, counts in page_groups.items()
        ],
    )
    write_json(
        output / "comparison.json",
        dict(
            rows=rows,
            changes=changes,
            identical_input_pages=True,
            identical_text_model_and_inference=True,
            reference_sha256=frozen[1],
            baseline=str(baseline),
            optimized=str(optimized),
            implementation_sha256=file_hash(Path(__file__)),
            scope="Whole course across all pages; no independent page-level handwriting recall without page labels. "
            "Best-fit roster alignment uses reference values; not independent identity authentication. "
            "Paired CER/NLD exclude extras; ordinary soft/exact F1 retains extra-prediction penalties.",
        ),
    )

    def show(value):
        return f"{100 * value:.1f}%" if value is not None else "nicht messbar"

    content = "".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(str(r[k]))}</td>"
            for k in ("variant", "method", "reference_rows", "assigned_rows")
        )
        + "".join(
            f"<td>{show(r[k])}</td>"
            for k in ("field_exact", "organization_exact", "record_exact", "soft_f1", "paired_cer")
        )
        + f"<td>{r['seconds']:.1f}</td></tr>"
        for r in rows
    )
    links = " · ".join(
        f'<a href="{Path(os.path.relpath(p, output)).as_posix()}/report.html">{label}</a>'
        for label, p in zip(("Vorher mit Felddetails", "Nachher mit Felddetails"), comparisons)
    )
    (output / "report.html").write_text(
        '<!doctype html><html lang="de"><meta charset="utf-8">'
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'\">"
        "<title>Strukturverfahren Vorher/Nachher</title><style>body{font:15px system-ui;margin:2rem}"
        "td,th{border:1px solid #ccc;padding:.5rem}table{border-collapse:collapse}</style>"
        "<h1>Docling und Paddle/LLM: Vorher/Nachher</h1><p>Identische PDF-Seiten und Bild-Hashes, dieselbe eingefrorene Kursreferenz. "
        "Bewertung auf Kursebene. Ohne manuell zugeordnete Seitentranskripte kein separater Handschrift-Recall. "
        "Best-Fit-Zuordnung ist keine Identitätsbestätigung. Gepaarte CER ohne Extra-Ausgaben; F1 bestraft diese separat.</p>"
        f'<p>{links}</p><p><a href="field_changes.csv">Jeder Feldwechsel als CSV</a> · '
        '<a href="quality_comparison.csv">Kennzahlen als CSV</a> · <a href="page_diagnostics.csv">Bedingte Seitendiagnose</a> · '
        '<a href="comparison.json">Definitionen und Identität</a></p>'
        "<table><tr><th>Variante</th><th>Verfahren</th><th>Referenz</th><th>Zugeordnet</th><th>Felder exakt</th>"
        "<th>Organisation exakt</th><th>Datensatz exakt</th><th>Levenshtein-F1</th><th>CER gepaart</th><th>Sekunden</th></tr>"
        + content
        + "</table>"
        f"<p>Feldübergänge: {html.escape(json.dumps(changes))}</p>",
        encoding="utf-8",
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "optimized", "reference", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("testframework/config.yaml"))
    args = parser.parse_args()
    print(compare(args.baseline, args.optimized, args.reference, args.output, args.config) / "report.html")
