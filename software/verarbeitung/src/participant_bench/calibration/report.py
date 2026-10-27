"""Local comparison tables and standalone Matplotlib reliability diagrams."""

import html
import os
from collections import defaultdict
from pathlib import Path

from ..io import write_csv


def export_report(output: Path, bundle: dict, review_seconds: float) -> None:
    os.environ.setdefault("MPLCONFIGDIR", str((output / "plot-cache").resolve()))
    comparisons, reliability_rows, threshold_rows, decisions, error_rows, field_rows = [], [], [], [], [], []
    for phase in ("development", "validation", "test"):
        for name, result in bundle.get(phase, {}).items():
            if not result.get("structured"):
                continue
            metrics, runtime = result["structured"], result.get("runtime", {})
            comparisons.append(
                dict(
                    phase=phase,
                    variant=name,
                    field_f1=metrics["field_prf"]["f1"]["value"],
                    exact_match=metrics["overall_exact_match"]["value"],
                    complete_rows=metrics["assignment"]["complete_row_coverage"]["value"],
                    missing_rows=metrics["counts"].get("missing_rows", 0),
                    extra_rows=metrics["counts"].get("extra_rows", 0),
                    text_reference_pages=result.get("text", {}).get("pages_with_manual_text", 0),
                    cer=result.get("text", {}).get("normalized", {}).get("cer", {}).get("value"),
                    wer=result.get("text", {}).get("normalized", {}).get("wer", {}).get("value"),
                    charged_seconds=runtime.get("full_pipeline_charged_seconds"),
                    actual_seconds=runtime.get("actual_method_wall_seconds"),
                    peak_ram_bytes=runtime.get("peak_ram_rss_bytes"),
                    peak_gpu_bytes=runtime.get("peak_gpu_allocated_bytes"),
                )
            )
            comparisons[-1].update(
                signature_precision=metrics["signature"]["prf"]["precision"]["value"],
                signature_recall=metrics["signature"]["prf"]["recall"]["value"],
                signature_f1=metrics["signature"]["prf"]["f1"]["value"],
                signature_fp=metrics["signature"]["prf"]["fp"],
                signature_fn=metrics["signature"]["prf"]["fn"],
            )
            for field, scores in metrics["fields"].items():
                field_rows.append(
                    dict(
                        phase=phase,
                        variant=name,
                        field=field,
                        exact_match=scores["exact_match"]["value"],
                        precision=scores["prf"]["precision"]["value"],
                        recall=scores["prf"]["recall"]["value"],
                        f1=scores["prf"]["f1"]["value"],
                        unknown_fraction=scores["unknown_rate"]["value"],
                        cer=scores["cer"]["value"],
                        false_discovery_rate=scores["false_discovery_rate"]["value"],
                        false_negative_rate=scores["false_negative_rate"]["value"],
                        empty_cell_false_positive_rate=scores["empty_cell_false_positive_rate"]["value"],
                    )
                )
            for row in result["errors"]:
                error_rows.append(dict(phase=phase, variant=name, **row))
            by_document = defaultdict(float)
            for row in result.get("page_timings", []):
                by_document[row["document_id"]] += row.get("page_wall_seconds", 0)
            write_csv(
                output / f"{phase}-{name}-document-times.csv",
                [
                    dict(
                        document_id=key,
                        page_processing_seconds=value,
                        scope="Sum of page wall times; shared load/preparation separate in runtime",
                    )
                    for key, value in by_document.items()
                ],
            )
    chart_paths = []
    for name, audit in bundle.get("audit", {}).items():
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure

        figure = Figure(figsize=(9, 7), layout="constrained")
        FigureCanvasAgg(figure)
        for axis, (field, summary) in zip(figure.subplots(2, 2).flat, audit["fields"].items()):
            axis.plot([0, 1], [0, 1], color="gray", linestyle="--", label="Ideal")
            for kind, label in (
                ("raw_score_diagnostics", "Raw score (not probability)"),
                ("calibrated", "Calibrated"),
            ):
                bins = summary[kind]["bins"]
                nonempty = [row for row in bins if row["count"]]
                if nonempty:
                    axis.plot(
                        [row["predicted"] for row in nonempty],
                        [row["observed"] for row in nonempty],
                        marker="o",
                        label=label,
                    )
                reliability_rows.extend(dict(variant=name, field=field, kind=kind, **row) for row in bins)
            axis.set(
                xlim=(0, 1),
                ylim=(0, 1),
                xlabel="Score / fitted probability",
                ylabel="Correct field fraction",
                title=f"{field}: {summary['acceptance_status']}",
            )
            axis.legend(fontsize=6)
        chart = f"reliability-{name}.svg"
        figure.savefig(output / chart)
        figure.savefig(output / f"reliability-{name}.png", dpi=160)
        chart_paths.append(chart)
        decisions.extend(dict(variant=name, **row) for row in audit["decisions"])
    for name, policy in bundle.get("policies", {}).items():
        for field, config in policy.items():
            threshold_rows.extend(
                dict(
                    variant=name,
                    field=field,
                    threshold=row["threshold"],
                    accepted=row["accepted"],
                    review=row["review"],
                    review_fraction=row["review_fraction"],
                    precision=row["precision"]["value"],
                    recall=row["recall"]["value"],
                    f1=row["f1"]["value"],
                )
                for row in config["curve"]
            )
    write_csv(output / "comparison.csv", comparisons)
    write_csv(output / "field_metrics.csv", field_rows)
    write_csv(output / "reliability.csv", reliability_rows)
    write_csv(output / "thresholds.csv", threshold_rows)
    write_csv(output / "decisions.csv", decisions)
    write_csv(output / "error_categories.csv", error_rows)
    review_count = sum(row["decision"] != "accepted" for row in decisions)

    def table(records):
        if not records:
            return "<p>Keine auswertbaren Daten.</p>"
        keys = list(records[0])
        return (
            "<table><thead><tr>"
            + "".join(f"<th>{html.escape(k)}</th>" for k in keys)
            + "</tr></thead><tbody>"
            + "".join(
                "<tr>" + "".join(f"<td>{html.escape(str(row.get(k, '')))}</td>" for k in keys) + "</tr>"
                for row in records
            )
            + "</tbody></table>"
        )

    scope = (
        "Unabhängiger finaler Test mit vorab eingefrorener Auswahl. Es findet kein erneutes Fitten oder Optimieren statt."
        if bundle.get("test")
        else "Entwicklung dient Konfigurationswahl und Kalibratorfit. validation bezeichnet die unabhängige Auditgruppe; Schwellenwerte wurden zuvor auf validation_fit gewählt. Testdaten werden erst separat bewertet."
    )
    content = f"""<!doctype html><html lang="de"><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self'; style-src 'unsafe-inline'">
<title>OCR-Kalibrierung</title><style>body{{font-family:system-ui;margin:2rem}}table{{border-collapse:collapse;font-size:.85rem}}td,th{{border:1px solid #aaa;padding:.4rem}}img{{max-width:100%}}</style>
<h1>OCR-Kalibrierung</h1><p>Ausgewählt: {html.escape(bundle["selected"])}; Vorschlag aus Entwicklung: {html.escape(bundle["proposed"])}.</p>
<p>Entscheidung: {html.escape(bundle["approval_reason"])}.</p>
<p>{scope}</p>
{table(comparisons)}<details><summary>Feldspezifische Qualität</summary>{table(field_rows)}</details><h2>Kalibrierung</h2><p>Ereignis: gesamtes Feld korrekt und der richtigen Referenzzeile zugeordnet,
mit der dokumentierten Feldnormalisierung. Leere/unleserliche Felder und PDF-Text haben keine OCR-Konfidenz.
Bei zu wenigen Fällen bleibt manuelle Prüfung erforderlich. Engine-Konfidenz/100 ist keine kalibrierte Wahrscheinlichkeit.</p>
{"".join(f'<img src="{chart}" alt="Feldweise Zuverlässigkeitsdiagramme">' for chart in chart_paths)}
<p>Nachkontrolle im dargestellten Audit/Test: {review_count} Felder; geschätzt {review_count * review_seconds / 60:.1f} Minuten.
Annahme: {review_seconds} Sekunden je Feld, keine gemessene Zeit.</p>
<p>Fehlerkategorien sind teils heuristische Hinweise, keine sichere Ursachenbestimmung. Details und Zähler in den CSV-/JSON-Dateien.
FPR für Textfelder wird nur auf explizit leeren Referenzzellen definiert; allgemeine Extraktionsfehler berichten FDR und FNR.</p>
<p><a href="comparison.csv">Vergleich</a> · <a href="reliability.csv">Reliability-Bins</a> · <a href="thresholds.csv">Schwellenkurven</a> ·
<a href="decisions.csv">Prüfentscheidungen</a> · <a href="error_categories.csv">Fehlerkategorien</a></p></html>"""
    (output / "report.html").write_text(content, encoding="utf-8")
