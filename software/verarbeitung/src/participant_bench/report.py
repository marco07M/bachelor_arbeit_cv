import html
import json

from .evaluation import DEFINITIONS
from .io import write_csv, write_json
from .schema import TEXT_FIELDS


def cost_scenario(config):
    assumptions = config.costs.model_dump()
    result = {
        "assumptions": assumptions,
        "note": "Zeitwert ist keine nachgewiesene Zahlungsersparnis; "
        "kein produktiver Import implementiert. Entwicklung getrennt von laufenden Kosten.",
    }
    c = config.costs
    required = (
        c.volume,
        c.hourly_rate_eur,
        c.manual_minutes_per_page,
        c.review_minutes_per_page,
        c.local_operating_eur_per_page,
    )
    if any(v is None for v in required):
        result["status"] = "not_calculated_missing_process_data"
        return result
    energy = None
    if c.energy_kwh_per_page is not None and c.electricity_eur_per_kwh is not None:
        energy = c.energy_kwh_per_page * c.electricity_eur_per_kwh * c.volume
    result.update(
        status=c.kind,
        manual_time_value_eur=c.volume * c.manual_minutes_per_page / 60 * c.hourly_rate_eur,
        review_time_value_eur=c.volume * c.review_minutes_per_page / 60 * c.hourly_rate_eur,
        freed_hours=c.volume * (c.manual_minutes_per_page - c.review_minutes_per_page) / 60,
        local_operating_eur=c.volume * c.local_operating_eur_per_page,
        energy_eur=energy,
        development_time_value_eur=c.development_hours * c.hourly_rate_eur
        if c.development_hours is not None
        else None,
    )
    return result


def report(output, summary, results, metrics, manifest, costs):
    rows = []
    for method, pages in results.items():
        for page in pages:
            for i, participant in enumerate(page.participants):
                rows.append(
                    {
                        "method": method,
                        "document_id": page.document_id,
                        "page_number": page.page_number,
                        "output_index": i,
                        "row_ref": participant.row_ref,
                        **{name: getattr(participant, name).value for name in TEXT_FIELDS},
                        **{name + "_state": getattr(participant, name).state for name in TEXT_FIELDS},
                        "signature_present": participant.signature_present,
                        "signature_state": participant.signature_state,
                        "review_notes": " | ".join(participant.review_notes),
                    }
                )
    write_csv(output / "extractions.csv", rows)
    write_csv(output / "methods.csv", [dict(method=method, **values) for method, values in summary.items()])
    write_json(output / "metrics.json", metrics)
    quality_rows = []
    for method, scores in metrics.items():
        aggregate = scores["aggregate"]
        for field, values in aggregate["fields"].items():
            quality_rows.append(
                {
                    "method": method,
                    "field": field,
                    "exact_correct": values["exact_match"]["numerator"],
                    "exact_total": values["exact_match"]["denominator"],
                    "exact_match": values["exact_match"]["value"],
                    "cer_edits": values["cer"]["numerator"],
                    "cer_characters": values["cer"]["denominator"],
                    "cer": values["cer"]["value"],
                    **{key: values["prf"][key] for key in ("tp", "fp", "fn")},
                    **{key: values["prf"][key]["value"] for key in ("precision", "recall", "f1")},
                    "unknown_count": values["unknown_rate"]["numerator"],
                    "coverage_denominator": values["coverage"]["denominator"],
                    "coverage": values["coverage"]["value"],
                }
            )
    if metrics:
        write_csv(output / "quality.csv", quality_rows)
    write_json(output / "costs.json", costs)

    def esc(value):
        return html.escape(str(value))

    def table(records):
        if not records:
            return "<p>Keine Einträge.</p>"
        keys = list(dict.fromkeys(k for record in records for k in record))
        return (
            "<table><thead><tr>"
            + "".join(f"<th>{esc(k)}</th>" for k in keys)
            + "</tr></thead><tbody>"
            + "".join(
                "<tr>" + "".join(f"<td>{esc(record.get(k, ''))}</td>" for k in keys) + "</tr>"
                for record in records
            )
            + "</tbody></table>"
        )

    quality = (
        "Qualität: nicht gemessen (keine Ground Truth)."
        if not metrics
        else "Qualität: deskriptiv gegen Ground Truth."
    )
    pages = [
        {
            "page_id": p["page_id"],
            "Seite": p["page_number"],
            "Typ": p["page_type"],
            "einschließen": p["include"],
            "Prüfbedarf": p["review_required"],
            "Grund": " | ".join(p["reasons"]),
        }
        for p in manifest["pages"]
    ]
    previews = "".join(
        f'<details><summary>{esc(p["page_id"])}</summary><a href="pages/{esc(p["page_id"])}.png">'
        f'<img loading="lazy" width="500" src="pages/{esc(p["page_id"])}.png" alt="Seitenvorschau"></a></details>'
        for p in manifest["pages"]
        if p["status"] == "ready"
    )
    content = f"""<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'">
<title>Teilnehmerlisten Benchmark</title><style>body{{font:15px system-ui;margin:2rem;background:#fafafa;color:#17212d}}
table{{border-collapse:collapse;display:block;overflow:auto;margin-bottom:2rem}}th,td{{border:1px solid #bcc;padding:.5rem;
text-align:left;vertical-align:top}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}img{{max-width:100%;height:auto}}</style>
<h1>Lokaler Teilnehmerlisten-Benchmark</h1><p>{esc(quality)}</p><p>Personenbezogene Inhalte: Bericht bleibt lokal.
Keine globale Siegerkennzahl. Synthetische Tests belegen keine Qualität auf realen Listen.</p>
<h2>Verfahren und Aufwand</h2>{table([dict(method=m, **s) for m, s in summary.items()])}
<h2>Seitenentscheidungen</h2>{table(pages)}<h2>Extraktionen zur Kontrolle</h2>{table(rows)}
<h2>Metriken mit Zählern und Nennern</h2><pre>{esc(json.dumps(metrics, ensure_ascii=False, indent=2))}</pre>
<h2>Definitionen und Grenzen</h2><pre>{esc(json.dumps(DEFINITIONS, ensure_ascii=False, indent=2))}</pre>
<p>A: Zeilenumbrüche, verschobene Spalten, verbundene Zellen und schlechte Scans können Zuordnungen stören.
A/B: Tinte im Unterschriftsfeld bleibt unbekannt; nur leere lokalisierte Felder werden negativ entschieden.
C: Anwesenheitsurteil des VLM ist kein Echtheitsnachweis. Orientierung und Seitenrelevanz manuell prüfen.</p>
<h2>Kostenannahmen</h2><pre>{esc(json.dumps(costs, ensure_ascii=False, indent=2))}</pre>
<h2>Seitenvorschauen</h2>{previews}</html>"""
    (output / "report.html").write_text(content, encoding="utf-8")
