"""Render supplementary scientific diagnostics using evaluated counters only."""

import json

from ..io import read_json, write_csv
from .dashboard_report import STYLE, number
from .detail_report import document, esc, table
from .document_availability import context
from .field_assessment import LABELS
from .report import percent
from .scientific_validity import build

SCRIPT = """(() => {
const filters=[...document.querySelectorAll('[data-validity-filter]')];
function apply(){for(const row of document.querySelectorAll('[data-validity-row]')){
 row.hidden=!filters.every(f=>!f.value||row.dataset[f.dataset.validityFilter]===f.value);
}}
for(const f of filters)f.addEventListener('change',apply);apply();
})();"""

LEVELS = {
    "first": "Erste Teilnehmerseite",
    "continuation_headerless": "Folgeseite ohne Überschrift",
    "continuation_header": "Folgeseite mit Überschrift",
    "continuation_unknown": "Folgeseite, Überschrift ungeprüft",
    "unknown": "Nicht klassifiziert / nicht lokalisiert",
    "clean": "Als gut geprüft",
    "degraded": "Als beeinträchtigt geprüft",
}


def overview(payload):
    return table(
        [
            "Verfahren",
            "Exact Recall E/R",
            "Exact F1",
            "Field Coverage",
            "Ø Ähnlichkeit erkannter Felder",
            "Legacy-Soft-F1",
            "ANLS-Feldähnlichkeit τ=0,5",
            "Zeilenkonsistenz C₃/N₃",
        ],
        [
            [
                r["candidate"],
                percent(r["overall"]["exact_recall"])
                + f" ({r['overall']['exact_fields']}/{r['overall']['reference_fields']})",
                percent(r["overall"]["exact_f1"]),
                percent(r["overall"]["field_coverage"]),
                percent(r["overall"]["detected_similarity"]),
                percent(r["overall"]["soft_f1"]),
                percent(r["overall"]["anls"]) if payload["anls_enabled"] else "Nicht aktiviert",
                percent(r["rows"]["row_consistency"])
                + f" ({r['rows']['correct_rows']}/{r['rows']['eligible_rows']})",
            ]
            for r in payload["methods"]
        ],
    )


def select(key, label, values):
    return (
        f'<label>{esc(label)} <select data-validity-filter="{key}"><option value="">Alle</option>'
        + "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in sorted(set(values)))
        + "</select></label>"
    )


def render(output, scientific, *, anls=False, page_annotations=None):
    availability = read_json(output / "missing_fields/analysis.json")
    snapshot = read_json(output / "missing_fields/annotations.snapshot.json")
    ctx = context(output, snapshot.get("original_documents"))
    payload = build(output, scientific, availability, ctx, anls=anls, page_annotations=page_annotations)
    content = f'<style>{STYLE}</style><main class="dash"><header class="hero"><h1>Wissenschaftliche Validität und Zusatzdiagnostik</h1>'
    content += '<p><a href="report.html">Gesamtvergleich</a> · <a href="missing_fields.html">Ursachen fehlender Felder / Originalprüfung</a> · <a href="extraction_errors.html">Pipeline-Belege</a></p>'
    content += "<p>Alle Zusatzwerte verwenden die gespeicherten Paarungen und Feldentscheidungen. Exactwerte, Coverage, Teilnehmermetriken, Signaturausschlüsse und Legacy-Soft-F1 bleiben erhalten.</p></header>"
    content += '<section class="hero"><h2>Getrennte Qualitätsdimensionen</h2>' + overview(payload)
    content += "<p>ANLS-Feldähnlichkeit: Σ[s, falls 1−s &lt; 0,5; sonst 0]/R. Fehlende und ungültige Werte erhalten 0; bei R=0 nicht definiert. Bei genau 0,5 Ähnlichkeit gilt 0. Projektadaption auf feste Feldpaare mit bestehender Normalisierung, kein unveränderter DocVQA-Benchmark und kein F1. Zusätze bleiben im globalen Exact-/Soft-F1.</p>"
    content += "<p>Ø erkannte Ähnlichkeit ignoriert fehlende Werte; ANLS berücksichtigt sie. Zeilenkonsistenz verlangt Vorname, Nachname und Personalnummer gemeinsam exakt in den Originalrollen auf einem zuverlässigen Paar. N₃ umfasst alle Referenzpersonen mit drei lesbaren Identitätsfeldern, einschließlich fehlender Personen; unklare Paarungen liefern keinen Treffer.</p>"
    content += (
        "<details><summary>Normalisierung und Reproduktion</summary><pre>"
        + esc(json.dumps(payload["normalization"], ensure_ascii=False, indent=2))
        + "</pre>"
    )
    content += '<p><a href="scientific/validity.json">Zusatzdiagnostik JSON</a> · <a href="scientific/validity_fields.csv">Feldbeiträge CSV</a> · <a href="scientific/validity_rows.csv">Zeilenentscheidungen CSV</a></p></details></section>'
    content += '<section class="hero"><h2>Matching-Sensitivität</h2><p>Referenzgestütztes Matching ist keine unabhängige Identifikation. original_roles und best_fit_swap verwenden dieselben Personenpaare; die anderen Gegenproben können Paarungen und P ändern. Namensswaps werden separat sichtbar und verbessern die Originalrollenbewertung nicht.</p>'
    content += (
        table(
            [
                "Verfahren",
                "Ansicht",
                "Recall",
                "Exact F1",
                "Legacy-Soft-F1",
                "P",
                "Gepaart",
                "Namensswaps",
                "Strikter Teilnehmer-Recall",
            ],
            [
                [
                    r["candidate"],
                    r["mode"],
                    percent(r["exact_recall"]),
                    percent(r["exact_f1"]),
                    percent(r["soft_f1"]),
                    r["predicted_fields"],
                    r["assigned"],
                    r["name_swaps"],
                    percent(r["participant_recall"]),
                ]
                for r in payload["matching"]
            ],
        )
        + "</section>"
    )
    content += '<section class="hero"><h2>Seitenposition und Dokumentqualität</h2>'
    content += f"<p>{payload['localized_reference_participants']} Referenzpersonen unabhängig auf einer Originalseite lokalisiert. Fehlende Teilnehmer bleiben auf ihrer annotierten Seite; nicht lokalisierte Personen bleiben in der unbekannten Gruppe. Eine Ausgabeseite bestimmt keinen Referenznenner. Dokumentgruppen aus manuellen Metadaten und h/m/g-Schriftartgruppen stehen weiterhin im Gesamtbericht.</p>"
    content += "<p>Gruppen-F1 ist auf zugehörige GT-Paare bedingt. Ungepaarte Zusatzwerte sind keiner GT-Seitengruppe zuweisbar und bleiben vollständig im globalen F1 sowie separat in validity.json. Keine Signaturtexte, keine automatische Schätzung von Scanqualität.</p>"
    rows = []
    field_rows = []
    for method in payload["methods"]:
        for r in method["strata"]:
            o, q = r["overall"], r["participant_quality"]
            rows.append(
                [
                    esc(method["candidate"]),
                    esc(r["feature"]),
                    esc(LEVELS[r["level"]]),
                    r["documents"],
                    r["pages"],
                    r["participants"],
                    o["reference_fields"],
                    percent(o["exact_recall"]),
                    percent(o["exact_f1"]),
                    percent(o["field_coverage"]),
                    percent(o["detected_similarity"]),
                    percent(o["anls"]) if anls else "Nicht aktiviert",
                    percent(q["participant_recall"]),
                    percent(q["complete_participant_accuracy"]),
                ]
            )
            for f, v in r["fields"].items():
                field_rows.append(
                    [
                        esc(method["candidate"]),
                        esc(r["feature"]),
                        esc(LEVELS[r["level"]]),
                        esc(f),
                        v["reference_fields"],
                        v["exact_fields"],
                        v["incorrect_fields"],
                        v["missing_fields"],
                        percent(v["exact_recall"]),
                        percent(v["field_coverage"]),
                    ]
                )
    content += table(
        [
            "Verfahren",
            "Dimension",
            "Gruppe",
            "PDFs",
            "Seiten",
            "Personen",
            "R",
            "Recall",
            "F1 bedingt",
            "Coverage",
            "Ø erkannt",
            "ANLS",
            "Teilnehmer-Recall",
            "Vollständig korrekt",
        ],
        rows,
    )
    content += (
        "<details><summary>Feldtypen innerhalb der Seitenstrata</summary>"
        + table(
            ["Verfahren", "Dimension", "Gruppe", "Feld", "R", "E", "W", "M", "Recall", "Coverage"], field_rows
        )
        + "</details>"
    )
    content += '<p><a href="scientific/page_annotations.template.json">Vorlage für unabhängige Seitenannotation</a>. Rollen first/continuation beziehen sich auf Teilnehmerseiten, nicht automatisch auf PDF-Seite 1. Für bekannte Kategorien sind Originalprüfung und Prüfprotokoll erforderlich. Übernahme ausschließlich in neuem Bericht mit <code>analyze --page-annotations DATEI --output NEU</code>.</p></section>'
    content += '<section class="hero"><h2>Fehlerursachen auf mehreren Belegachsen</h2><p>Ein Feld kann mehrere Stufenbefunde haben. Die nachfolgenden Befundzahlen sind überlappend und dürfen nicht als Zahl unabhängiger Feldfehler addiert werden. „Zusatzwert“ beweist keine Halluzination; „lesbar, aber Endwert fehlt“ trennt Wahrnehmung und Zuordnung noch nicht. Nicht lokalisierte Fehler stehen mit Seite unknown.</p>'
    from collections import Counter

    totals = Counter(r["candidate"] for r in payload["errors"])
    content += (
        "<p>Eindeutige Feldfehler: "
        + " · ".join(f"{esc(k)}: {v}" for k, v in sorted(totals.items()))
        + "</p>"
    )
    content += '<div class="filters">' + select(
        "candidate", "Verfahren", [r["candidate"] for r in payload["error_groups"]]
    )
    content += select("cause", "Ursachenbereich", [r["cause"] for r in payload["error_groups"]]) + "</div>"
    content += (
        '<div class="filters">'
        + "".join(
            select(attr, label, [str(r[key]) for r in payload["error_groups"]])
            for attr, key, label in (
                ("document", "document_id", "Dokument"),
                ("page", "page_number", "Seite"),
                ("field", "field", "Feld"),
            )
        )
        + "</div>"
    )
    content += (
        '<div class="scroll"><table><thead><tr>'
        + "".join(
            f"<th>{h}</th>"
            for h in ["Verfahren", "Dokument-ID", "Seite", "Feld", "Ursache", "Beleglage", "Stufe", "Befunde"]
        )
        + "</tr></thead><tbody>"
    )
    for r in payload["error_groups"]:
        content += (
            f'<tr data-validity-row data-candidate="{esc(r["candidate"])}" data-cause="{esc(r["cause"])}" '
            f'data-document="{esc(r["document_id"])}" data-page="{esc(r["page_number"])}" data-field="{esc(r["field"])}">'
            + "".join(
                f"<td>{esc(v)}</td>"
                for v in [
                    r["candidate"],
                    r["document_id"],
                    r["page_number"],
                    r["field"],
                    payload["causes"][r["cause"]],
                    r["certainty"],
                    r["stage"],
                    r["count"],
                ]
            )
            + "</tr>"
        )
    content += (
        '</tbody></table></div></section><section class="hero"><h2>Effizienz und technische Stabilität</h2>'
    )
    content += "<p>Zeitwerte sind beobachtete Einzelmessungen. Volllauf-Ladezeit/VRAM werden keinem Teilumfang anteilig zugerechnet. Gespeicherte Generierungszeit ist keine vollständige Inferenzzeit. JSON-Syntax und gespeicherte Schemaentscheidung beziehen sich auf letzte protokollierte Antwortdatensätze; Cacheantworten sind keine neuen Aufrufe. Fehlende Werte: nicht definiert.</p>"
    tech_rows, document_times = [], []
    for c, e in scientific["effort"].items():
        t = e["technical"]
        tech_rows.append(
            [
                esc(c),
                number(e.get("load_seconds")),
                number(e.get("warmup_seconds")),
                number(e.get("page_wall_sum")),
                number(t.get("saved_generation_seconds_sum")),
                number(
                    e.get("peak_gpu_allocated_bytes") / 1024**3
                    if e.get("peak_gpu_allocated_bytes") is not None
                    else None
                ),
                percent(t["page_parse_rate"]),
                f"{t['json_syntax']['valid']}/{t['json_syntax']['evaluated']}: "
                + percent(t["json_syntax"]["rate"]),
                f"{t['saved_schema_validation']['valid']}/{t['saved_schema_validation']['evaluated']}: "
                + percent(t["saved_schema_validation"]["rate"]),
                t["failed_pages"],
                number(t["repeated_page_attempts"], 0),
                "Nicht verfügbar",
                esc(e["cache_regime"]),
                "Nicht protokolliert",
            ]
        )
        document_times.extend(
            [
                [esc(c), esc(r["document_id"]), r["observed_pages"], number(r["page_wall_sum"])]
                for r in t["document_times"]
            ]
        )
    content += table(
        [
            "Verfahren",
            "Laden s (Quelllauf)",
            "Warm-up s",
            "Seitenzeit Σ s",
            "Protokollierte Generierung Σ s",
            "Peak GPU GiB (Quelllauf)",
            "Gültige Seiten / erwartete",
            "JSON gültig / geprüft",
            "Schema gültig / geprüft",
            "Fehlseiten",
            "Wiederholte Seitenversuche",
            "Modell-Retries",
            "Cache",
            "Cold/Warm",
        ],
        tech_rows,
    )
    content += (
        "<details><summary>Beobachtete Laufzeit je Dokument</summary>"
        + table(["Verfahren", "Dokument", "Beobachtete Seiten", "Σ Seitenzeit s, ohne Laden"], document_times)
        + "</details>"
    )
    content += "<details><summary>Technische Bildeigenschaften aus dem Manifest</summary><p>Pixelabmessungen und protokollierte Rotation sind keine Annotation der Lesbarkeit. Render-DPI ist keine verlässliche ursprüngliche Scanauflösung; Scan-DPI bleibt unbekannt.</p>"
    content += (
        table(
            [
                "Dokument",
                "Seite",
                "Breite px",
                "Höhe px",
                "PDF-Rotation",
                "Zusätzliche Rotation",
                "Manuelle Rotation",
                "Orientierung",
            ],
            [
                [
                    r.get(k)
                    for k in (
                        "document_id",
                        "page_number",
                        "width",
                        "height",
                        "pdf_rotation_metadata",
                        "additional_rotation_clockwise",
                        "curation_rotation_clockwise",
                        "orientation_status",
                    )
                ]
                for r in payload["image_observations"]
            ],
        )
        + "</details></section>"
    )
    content += '<section class="hero"><h2>Rohtext-OCR separat</h2><p>ocr_raw erhält keinen strukturierten Feld-F1. Ohne vollständige unabhängige Seitentranskripte ist keine belastbare CER/WER verfügbar. Optional diagnostiziert Textauffindbarkeit ausschließlich unabhängig lesbare Originalwerte auf ihrer Originalseite, mit derselben Normalisierung und Wortgrenzen. Sie bestätigt weder Teilnehmerzuordnung noch Präzision und enthält keine Unterschriften.</p>'
    content += (
        table(
            ["Verfahren", "Geprüfte Felder", "Im Text auffindbar", "Anteil", "Fehlende OCR-Seiten"],
            [
                [
                    r["candidate"],
                    r["fields"],
                    r["found"],
                    percent(r["text_findability"]),
                    r["missing_pages"],
                ]
                for r in payload["raw_text"]
            ],
        )
        if payload["raw_text"]
        else "<p>Kein ocr_raw-Ergebnis im ausgewählten Vergleich vorhanden; keine OCR-Qualität geschätzt.</p>"
    )
    content += '</section><section class="hero"><h2>Einzelne Feldbeiträge</h2><p>Originalwerte erscheinen einmal. Die strikte Entscheidung bleibt im <a href="report.html#audit">bestehenden Feld-Audit</a> nachvollziehbar. Zusatzwerte haben keinen ANLS-Referenzbeitrag.</p>'
    content += (
        table(
            [
                "Verfahren",
                "Kurs",
                "Referenzzeile",
                "Feld",
                "Ground Truth",
                "Extrahierter Originalwert",
                "Status",
                "Ähnlichkeit",
                "ANLS-Beitrag",
                "R-Beitrag",
            ],
            [
                [
                    r["candidate"],
                    r["class_id"],
                    r["reference_row"],
                    r["field"],
                    r["ground_truth"],
                    r["prediction"],
                    LABELS.get(r["evaluation_status"], r["evaluation_status"]),
                    percent(r["similarity"]),
                    percent(r["anls_credit"]) if anls else "Nicht aktiviert",
                    r["reference_contribution"],
                ]
                for r in payload["fields"]
            ],
        )
        + "</section></main>"
    )
    target = output / "validity.html"
    target.write_text(
        document("Wissenschaftliche Validität", content, script_source=SCRIPT), encoding="utf-8"
    )
    for name, records, columns in (
        ("validity_fields", payload["fields"], ["candidate", "field"]),
        (
            "validity_rows",
            [dict(candidate=m["candidate"], **r) for m in payload["methods"] for r in m["rows"]["cases"]],
            ["candidate", "reference_row"],
        ),
        ("validity_errors", payload["error_groups"], ["candidate", "cause"]),
    ):
        write_csv(output / "scientific" / (name + ".csv"), records, fields=None if records else columns)
    for name in ("report.html", "missing_fields.html", "extraction_errors.html", "standard_report.html"):
        path = output / name
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if 'href="validity.html"' not in text:
                extra = '<p><a href="validity.html"><strong>Wissenschaftliche Validität · ANLS · Zeilenkonsistenz · Seitenstrata · Stabilität</strong></a></p>'
                if name == "report.html":
                    supplement = (
                        "<details><summary>Zusätzliche Qualitätsdimensionen (unveränderte Primärwertung)</summary>"
                        + overview(payload)
                        + "</details>"
                    )
                    marker = text.find('<section class="panel" id="fields"')
                    position = text.rfind('</section>', 0, marker)
                    if position >= 0:
                        text = text[:position] + supplement + text[position:]
                path.write_text(text.replace("</h1>", "</h1>" + extra, 1), encoding="utf-8")
    return target
