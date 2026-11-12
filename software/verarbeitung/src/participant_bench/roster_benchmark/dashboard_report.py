"""Offline six-panel view of existing scientific counters; no metric calculation here."""

import json
from collections import Counter
from urllib.parse import urlencode

from .detail_report import document, esc, table
from .report import percent

VERSION = "roster-dashboard-v1"
LABELS = {
    "first_name": "Vorname",
    "last_name": "Nachname",
    "user_id": "Personalnummer",
    "short_code": "Organisation",
}
CAUSES = {
    "field_assignment": "Feldzuordnung",
    "validation": "Validierung",
    "input_selection": "Eingabeauswahl",
    "assignment_or_postprocessing": "Antwort / Nachverarbeitung",
    "recognition_or_assignment": "OCR oder Zuordnung (Hypothese)",
    "extra_output": "Zusatzfeld",
    "unknown": "Unbekannt",
}
STYLE = """
:root{--ink:#142d45;--muted:#587084;--blue:#15629b;--line:#d6e2ec;--bg:#f3f7fa}
body{margin:0;padding:0;max-width:none;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,sans-serif}
.dash{max-width:1480px;margin:auto;padding:24px}h1{font-size:27px;margin:0 0 6px}h2{font-size:22px;margin:0 0 12px}
.subtitle,.muted{color:var(--muted)}.hero,.panel,.cards>div{background:white;border:1px solid var(--line);border-radius:13px}
.hero,.panel{padding:23px}.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:17px 0}
.cards>div{padding:12px 17px}.cards strong{display:block;font-size:23px}.tabs{display:flex;gap:7px;flex-wrap:wrap;position:sticky;top:0;background:var(--bg);z-index:5;padding:12px 0}
button,select{font:inherit}button{cursor:pointer}.tabs button{border:1px solid var(--line);padding:9px 13px;border-radius:8px;background:white;color:var(--ink)}
.tabs button[aria-selected=true]{background:var(--ink);color:white;border-color:var(--ink)}.panel[hidden]{display:none!important}
.note{border-left:4px solid #d99928;background:#fff8e9;padding:10px 14px;margin:14px 0}.good-note{border-left:4px solid var(--blue);background:#edf5fb;padding:10px 14px}
.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px;margin:10px 0 18px}th,td{border-bottom:1px solid var(--line);padding:9px 10px;text-align:left;vertical-align:top}th{background:#eff4f8;white-space:normal}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}th button{border:0;background:none;text-align:left;font-weight:bold;color:inherit;padding:0;width:100%}
.badge{display:inline-block;border-radius:10px;background:#edf2f6;color:#466176;font-size:11px;padding:2px 7px;margin:3px 0}
details{border:1px solid var(--line);padding:10px 13px;border-radius:8px;margin:14px 0}summary{font-weight:650;cursor:pointer}pre{white-space:pre-wrap;word-break:break-word;background:#f6f8fa;padding:12px;font-size:12px}
.filters{display:flex;gap:12px;flex-wrap:wrap;margin:15px 0}.filters label{font-size:13px}.filters select{display:block;max-width:260px;padding:6px;border:1px solid var(--line);border-radius:6px}
.figure{max-width:100%;max-height:640px;object-fit:contain}.heat td{min-width:140px}.heat small{display:block}.links{display:flex;gap:14px;flex-wrap:wrap}a{color:var(--blue)}.empty{color:var(--muted)}
@media(max-width:700px){.dash{padding:10px}.hero,.panel{padding:14px}.cards{grid-template-columns:repeat(2,minmax(0,1fr))}.tabs{position:static}h1{font-size:23px}}
@media print{.tabs{display:none}.panel[hidden]{display:block!important}.panel{break-before:page}.dash{max-width:none}}
"""

SCRIPT = """(() => {
const tabs=[...document.querySelectorAll('[data-panel]')];
function show(id){
 if(!document.getElementById(id)?.classList.contains('panel'))id='overall';
 for(const panel of document.querySelectorAll('.panel'))panel.hidden=panel.id!==id;
 for(const tab of tabs)tab.setAttribute('aria-selected',String(tab.dataset.panel===id));
}
for(const tab of tabs)tab.addEventListener('click',()=>{location.hash=tab.dataset.panel;show(tab.dataset.panel);});
window.addEventListener('hashchange',()=>show(location.hash.slice(1)));show(location.hash.slice(1));
for(const button of document.querySelectorAll('[data-sort]'))button.addEventListener('click',()=>{
 const table=button.closest('table'),body=table.tBodies[0],col=Number(button.dataset.sort);
 const direction=button.dataset.direction==='asc'?-1:1;button.dataset.direction=direction===1?'asc':'desc';
 const rows=[...body.rows];rows.sort((a,b)=>{
  const av=a.cells[col].dataset.value,bv=b.cells[col].dataset.value;
  if(av==='')return bv===''?0:1;if(bv==='')return -1;
  const x=Number(av),y=Number(bv);
  return direction*(Number.isFinite(x)&&Number.isFinite(y)?x-y:av.localeCompare(bv,'de'));
 });for(const row of rows)body.appendChild(row);
 for(const head of table.tHead.rows[0].cells)head.removeAttribute('aria-sort');
 button.closest('th').setAttribute('aria-sort',direction===1?'ascending':'descending');
});
function filterErrors(){
 const ids=['error-method','error-document','error-class','error-field','error-cause','error-certainty'];let n=0;
 for(const row of document.querySelectorAll('#error-table tbody tr')){
  const ok=ids.every(id=>{const c=document.getElementById(id);return !c.value||row.dataset[id.slice(6)]===c.value;});
  row.hidden=!ok;if(ok)n++;
 }document.getElementById('error-visible').textContent=String(n);
}
for(const select of document.querySelectorAll('.error-filter'))select.addEventListener('change',filterErrors);
filterErrors();
const feature=document.getElementById('robustness-feature');
feature.addEventListener('change',()=>{for(const row of document.querySelectorAll('#strata-table tbody tr'))row.hidden=row.dataset.feature!==feature.value;});
feature.dispatchEvent(new Event('change'));
})();"""


def number(value, digits=2):
    return "—" if value is None else f"{value:.{digits}f}".replace(".", ",")


def metric_cell(value, text=None, detail=None):
    hint = f'<small class="muted" style="display:block">{esc(detail)}</small>' if detail is not None else ""
    return f'<td class="num" data-value="{esc("" if value is None else value)}">{esc(text if text is not None else number(value))}{hint}</td>'


def sortable(headers, rows):
    head = "".join(
        f'<th><button type="button" data-sort="{i}">{esc(label)} ↕</button></th>'
        for i, label in enumerate(headers)
    )
    return (
        '<div class="scroll"><table class="sortable"><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def filter_select(key, label, values):
    options = '<option value="">Alle</option>' + "".join(
        f'<option value="{esc(v)}">{esc(v)}</option>' for v in sorted(set(values))
    )
    return f'<label>{esc(label)}<select class="error-filter" id="error-{key}">{options}</select></label>'


def panel(id, title, content):
    return (
        f'<section class="panel" id="{id}"'
        + (" hidden" if id != "overall" else "")
        + f"><h2>{title}</h2>{content}</section>"
    )


def render(output, payload):
    primary = [r for r in payload["overview"] if r.get("mode") == "original_roles"]
    target = output / "report.html"
    legacy = output / "standard_report.html"
    if not legacy.exists():
        previous = target.read_text(encoding="utf-8")
        if "data-dashboard-version=" not in previous:
            legacy.write_text(previous, encoding="utf-8")
    text = f'<style>{STYLE}</style><main class="dash" id="scientific-analysis" data-dashboard-version="{VERSION}">'
    text += '<noscript><style>.panel[hidden]{display:block!important}.tabs{display:none}</style><p>JavaScript ist deaktiviert; alle Bereiche stehen untereinander.</p></noscript>'
    text += '<header class="hero"><h1>Modellvergleich · Teilnehmerlisten</h1><p class="subtitle">Wissenschaftliche Analyse: Qualität, Vollständigkeit, Fehler und Aufwand auf derselben eingefrorenen Referenz.</p>'
    text += '<div class="good-note"><strong>Primär: unveränderte Namensrollen.</strong> Die Personenpaare bleiben referenzgestützt; dies ist keine referenzunabhängige Identitätsprüfung. Exakter Feld-F1 und Levenshtein-F1 werden getrennt ausgewiesen.</div></header>'
    text += (
        '<div class="cards">'
        + "".join(
            f"<div><strong>{esc(value)}</strong>{esc(label)}</div>"
            for value, label in (
                (len(primary), "Verfahren"),
                (payload["documents"], "PDFs"),
                (payload["courses"], "Schulungen"),
                (payload["groups"], "Abhängigkeitsgruppen"),
            )
        )
        + "</div>"
    )
    titles = [
        ("overall", "A · Gesamtvergleich"),
        ("fields", "B · Feldanalyse"),
        ("errors", "C · Fehleranalyse"),
        ("robustness", "D · Dokumenttypen"),
        ("efficiency", "E · Effizienz & Kosten"),
        ("statistics", "F · Statistik"),
    ]
    text += (
        '<nav class="tabs" aria-label="Analysebereiche" role="tablist">'
        + "".join(
            f'<button type="button" role="tab" aria-controls="{id}" aria-selected="{str(id == "overall").lower()}" data-panel="{id}">{label}</button>'
            for id, label in titles
        )
        + "</nav>"
    )

    rows = []
    for r in primary:
        method = r["candidate"]
        e = payload["effort"][method]
        q = r["participant_quality"]
        calls = e.get("selected_actual_calls")
        detail = f"{calls} gesamt" if calls is not None else "nicht verfügbar"
        if e.get("selected_llm_calls") is not None and e.get("selected_vlm_calls") is not None:
            detail = f"LLM {e['selected_llm_calls']} · VLM {e['selected_vlm_calls']}"
        row = f'<tr><td data-value="{esc(method)}"><strong>{esc(method)}</strong><br><span class="badge">Datenbasis: {esc(r["status"])}</span></td>'
        row += metric_cell(
            r["exact_recall"], percent(r["exact_recall"]), f"{r['exact_fields']} / {r['reference_fields']}"
        ) + metric_cell(r["exact_f1"], percent(r["exact_f1"]))
        row += metric_cell(
            q.get("complete_participant_accuracy"),
            percent(q.get("complete_participant_accuracy")),
            f"{q['fully_correct_complete_participants']} / {q['complete_reference_participants']} · {q['partial_reference_participants']} Teilref.",
        )
        row += metric_cell(
            q.get("participant_recall"),
            percent(q.get("participant_recall")),
            f"{q['identity_exact_participants']} / {q['identity_assessable_participants']}",
        )
        row += metric_cell(r["field_coverage"], percent(r["field_coverage"]))
        row += metric_cell(e["page_time"]["median"], number(e["page_time"]["median"]) + " s · Median")
        row += metric_cell(calls, detail) + metric_cell(
            e["costs"]["measured_eur_per_1000"],
            "nicht gemessen"
            if e["costs"]["measured_eur_per_1000"] is None
            else number(e["costs"]["measured_eur_per_1000"]) + " €",
        )
        rows.append(row + "</tr>")
    a = '<p class="muted">Spaltenköpfe sortieren. Höhere Qualitätswerte sind besser; geringerer Aufwand ist günstiger. Fehlende Werte bleiben offen.</p>'
    a += sortable(
        [
            "Verfahren",
            "Exakter Recall",
            "Exakter F1",
            "Vollständige Teilnehmer",
            "Teilnehmer-Recall",
            "Field Coverage",
            "Laufzeit / Seite",
            "LLM-/VLM-Aufrufe",
            "Kosten / 1.000 PDFs",
        ],
        rows,
    )
    a += "<p>„Vollständig“ bezieht sich auf Referenzen mit vier bestimmbaren Pflichtfeldern einschließlich ausdrücklich leerer Zellen. Teilnehmer-Recall verlangt eine eindeutige Referenz-ID oder eindeutige vollständige Namenskombination sowie exakte Übereinstimmung aller bestimmbaren Identitätsfelder. Eine Best-Fit-Paarung allein genügt nicht.</p>"
    a += "<details><summary>Zähler, Nenner, Ausschlüsse und technische Vollständigkeit</summary>"
    a += (
        table(
            [
                "Verfahren",
                "Exakt E / R",
                "Ausgabefelder P",
                "Vollständig korrekt / vollständige GT",
                "Teilreferenzen korrekt / GT",
                "Nicht bewertbare GT",
                "Identität exakt / bewertbar",
                "Identität nicht bewertbar",
                "Nicht zugeordnet / Zusatzpersonen",
                "Seiten gültig / erwartet",
            ],
            [
                [
                    r["candidate"],
                    f"{r['exact_fields']} / {r['reference_fields']}",
                    r["predicted_fields"],
                    f"{r['participant_quality']['fully_correct_complete_participants']} / {r['participant_quality']['complete_reference_participants']}",
                    f"{r['participant_quality']['fully_correct_partial_participants']} / {r['participant_quality']['partial_reference_participants']} ({percent(r['participant_quality']['partial_participant_accuracy'])})",
                    r["participant_quality"]["unassessable_reference_participants"],
                    f"{r['participant_quality']['identity_exact_participants']} / {r['participant_quality']['identity_assessable_participants']}",
                    r["participant_quality"]["identity_unassessable_participants"],
                    f"{r['missing_participants']} / {r['extra_participants']}",
                    f"{r['successful_pages']} / {r['expected_pages']}",
                ]
                for r in primary
            ],
        )
        + "</details>"
    )
    a += "<details><summary>Metrikdefinitionen und Aggregation</summary>" + table(
        ["Metrik", "Formel", "Zaehler", "Nenner", "Einheit / Richtung"],
        [
            [r["label"], r["formula"], r["numerator"], r["denominator"], r["unit"] + " / " + r["direction"]]
            for r in payload["definitions"]
        ],
    )
    a += "<p>Gesamtqualität ist Micro-Aggregation aus Zählern, kein Mittelwert der Schulungs-F1. Schulungsquantile sind deskriptiv. Maskierte/unlesbare Referenzen werden nach dem bestehenden Protokoll ausgeschlossen; Leerzellenerkennung bleibt getrennt. Unsichere Ausgaben werden nur gemäß der gespeicherten Bewertungskonfiguration berücksichtigt.</p>"
    a += "<p>" + esc(payload["normalization_rule"]) + "</p></details>"
    a += "<details><summary>Matching-Sensitivität und ursprünglicher Bewertungsbericht</summary>" + table(
        ["Verfahren", "Ansicht", "E / R", "Exakter F1", "Levenshtein-F1"],
        [
            [
                r["candidate"],
                r["mode"],
                f"{r['exact_fields']} / {r['reference_fields']}",
                percent(r["exact_f1"]),
                percent(r["soft_f1"]),
            ]
            for r in payload["overview"]
            if r.get("mode")
        ],
    )
    a += "<p>F1 bei konservativer Zuordnung wird in den Ansichten conservative_no_swap und conservative_swap getrennt ausgewiesen. Best-Fit-Paarzahlen bestätigen keine Identitäten.</p>"
    a += table(
        ["Verfahren", "Reiner Bewertungseffekt", "Δ exakter F1 (pp)"],
        [
            [r["candidate"], r["explanation"], number(r["estimates"]["exact_f1"])]
            for r in payload["matching_effects"]
        ],
    )
    a += '<p>original_roles hält die Best-Fit-Paare fest und bewertet Originalrollen. Andere Ansichten berechnen die globale Paarung neu. Diese Unterschiede verändern keine Extraktion. Die alten fully_exact-Zähler für alle lesbaren Teilreferenzen werden weiterhin unverändert exportiert und nicht als die neue Vollständigkeitsmetrik umbenannt.</p><a href="standard_report.html">Gespeicherter Standardbericht und bisherige Metriken</a></details>'
    text += panel("overall", "A · Gesamtvergleich", a)

    fields = [r for r in payload["field_summary"] if r["mode"] == "original_roles"]
    lookup = {(r["candidate"], r["field"]): r for r in fields}
    b = (
        '<p>Exakter Feld-Recall je Zielfeld, in Prozent. Jede Zelle nennt Treffer und Referenznenner. Grau bedeutet nicht bestimmbar.</p><div class="scroll"><table class="heat"><thead><tr><th>Verfahren</th>'
        + "".join(f"<th>{v}</th>" for v in LABELS.values())
        + "</tr></thead><tbody>"
    )
    for r in primary:
        b += f"<tr><th>{esc(r['candidate'])}</th>"
        for field in LABELS:
            f = lookup[r["candidate"], field]
            v = f["exact_recall"]
            color = "#eff2f5" if v is None else f"hsl(207 65% {96 - 65 * v:.1f}%)"
            b += f'<td style="background:{color};color:{"white" if v is not None and v > 0.65 else "#142d45"}"><strong>{esc(percent(v))}</strong><small>{f["exact_fields"]} / {f["reference_fields"]} · {f["missing_fields"]} fehlend · {f["incorrect_fields"]} falsch</small></td>'
        b += "</tr>"
    b += "</tbody></table></div>" + table(
        [
            "Verfahren",
            "Feld",
            "Exakt / R",
            "P",
            "Exakter F1",
            "Fehlende Felder / R",
            "Falsche Felder / R",
            "Zusätzlich",
            "Maskiert/unlesbar ausgeschlossen",
            "Explizit leere Referenzfelder",
        ],
        [
            [
                r["candidate"],
                LABELS[r["field"]],
                f"{r['exact_fields']} / {r['reference_fields']}",
                r["predicted_fields"],
                percent(r["exact_f1"]),
                f"{r['missing_fields']} ({percent(r['missing_rate'])})",
                f"{r['incorrect_fields']} ({percent(r['incorrect_rate'])})",
                r["extra_fields"],
                r["excluded_reference_fields"],
                r["reference_empty_fields"],
            ]
            for r in fields
        ],
    )
    b += '<p><a href="scientific/fields.csv">Feldzähler je Schulung und Ansicht</a> · <a href="scientific/strata_fields.csv">Felder nach Merkmalen</a> · <a href="details.html">Bestehende Soll-/Ist-Berechnung im Standardmodus</a></p>'
    text += panel("fields", "B · Feldanalyse", b)

    errors = payload["errors"]["fields"]
    totals = Counter()
    for r in errors:
        totals[r["method"]] += r["count"]
    c = "<p>Dieselbe Originalrollenbewertung wie in A/B. Jeder falsche, fehlende oder zusätzliche Feldfall erhält genau einen konservativen Ursachenbereich und Evidenzgrad. Mehrere Hypothesen werden nicht mehrfach gezählt.</p>"
    c += table(
        ["Verfahren", "Feldfehler gesamt", *[CAUSES[k] for k in CAUSES]],
        [
            [
                r["candidate"],
                totals[r["candidate"]],
                *[
                    sum(e["count"] for e in errors if e["method"] == r["candidate"] and e["cause"] == cause)
                    for cause in CAUSES
                ],
            ]
            for r in primary
        ],
    )
    c += '<p class="note">Nachgewiesen bezeichnet einen gespeicherten Übergang, nicht zwingend die ursprüngliche Ursache. OCR und Zuordnung sind oft nicht trennbar. Zusätzliche Ausgabe ist kein automatischer Halluzinationsnachweis. Tabellen-/Antwortereignisse werden separat gezählt und nicht zu Feldfehlern addiert.</p><div class="filters">'
    for key, label, field in [
        ("method", "Verfahren", "method"),
        ("document", "Dokument", "document_id"),
        ("class", "Schulung", "class_id"),
        ("field", "Feld", "field"),
        ("cause", "Ursachenbereich", "cause"),
        ("certainty", "Evidenzgrad", "certainty"),
    ]:
        c += filter_select(key, label, [r[field] for r in errors])
    c += (
        '</div><p><span id="error-visible"></span> aggregierte Gruppen sichtbar.</p><div class="scroll"><table id="error-table"><thead><tr>'
        + "".join(
            f"<th>{s}</th>"
            for s in [
                "Verfahren",
                "Dokument",
                "Schulung",
                "Feld",
                "Ergebnis",
                "Ursache / Stufe",
                "Beleglage",
                "Fälle / Methodenfehler",
                "Details",
            ]
        )
        + "</tr></thead><tbody>"
    )
    for r in errors:
        attrs = dict(
            method=r["method"],
            document=r["document_id"],
            field=r["field"],
            cause=r["cause"],
            certainty=r["certainty"],
            **{"class": r["class_id"]},
        )
        query = urlencode(
            dict(
                method=r["method"],
                document=r["document_id"],
                field=r["field"],
                cause=r["cause"],
                certainty=r["certainty"],
                **{"class": r["class_id"]},
            )
        )
        c += (
            "<tr "
            + " ".join(f'data-{k}="{esc(v)}"' for k, v in attrs.items())
            + ">"
            + "".join(
                f"<td>{esc(v)}</td>"
                for v in [
                    r["method"],
                    r["document_id"][:12] if r["document_id"] != "unknown" else "nicht lokalisiert",
                    r["class_id"],
                    LABELS[r["field"]],
                    r["result"],
                    CAUSES[r["cause"]] + " / " + r["stage"],
                    r["certainty"],
                    f"{r['count']} ({percent(r['share_of_method_errors'])})",
                ]
            )
            + f'<td><a href="extraction_errors.html?{esc(query)}">Soll / Ist / Original / Belege</a></td></tr>'
        )
    c += (
        "</tbody></table></div><details><summary>Separat: gespeicherte Seiten-/Tabellenereignisse</summary>"
        + table(
            ["Verfahren", "Dokument", "Seite", "Ereignis", "Stufe", "Anzahl"],
            [
                [r[k] for k in ("method", "document_id", "page_number", "event", "stage", "count")]
                for r in payload["errors"]["page_events"]
            ],
        )
        + "</details>"
    )
    c += '<a href="extraction_errors.html">Vorhandene Einzelfallanalyse mit Ground Truth, verglichenem und originalem Wert</a>'
    text += panel("errors", "C · Fehleranalyse", c)

    d = (
        '<p>Manuell dokumentierte Merkmale; unbekannte Werte werden nicht geraten. Bei mehreren PDFs einer Schulung wird die Referenz nicht künstlich auf Seiten verteilt. heterogeneous_course ist keine einzelne gemischt geschriebene PDF.</p><label>Merkmal <select id="robustness-feature">'
        + "".join(
            f"<option>{f}</option>"
            for f in (
                "stratum",
                "headerless",
                "variable_layout",
                "image_quality",
                "multipage_pdf",
                "partition",
            )
        )
        + "</select></label>"
    )
    d += (
        '<div class="scroll"><table id="strata-table"><thead><tr>'
        + "".join(
            f"<th>{s}</th>"
            for s in [
                "Verfahren",
                "Merkmal",
                "Kategorie",
                "Schulungen / Gruppen",
                "R",
                "Exakter Recall",
                "Exakter F1",
                "Field Coverage",
                "Fallzahlhinweis",
            ]
        )
        + "</tr></thead><tbody>"
    )
    for r in payload["strata"]:
        if r["mode"] != "original_roles":
            continue
        d += (
            f'<tr data-feature="{esc(r["feature"])}">'
            + "".join(
                f"<td>{esc(v)}</td>"
                for v in [
                    r["candidate"],
                    r["feature"],
                    r["level"],
                    f"{r['courses']} / {r['groups']}",
                    r["reference_fields"],
                    percent(r["exact_recall"]),
                    percent(r["exact_f1"]),
                    percent(r["field_coverage"]),
                    "kleine Stichprobe"
                    if r["groups"] < payload["bootstrap"]["minimum_groups"]
                    else "deskriptiv",
                ]
            )
            + "</tr>"
        )
    d += "</tbody></table></div>"
    for name, label in [
        ("heatmap", "Exakter Recall je Schulung"),
        ("distribution", "Verteilung des exakten Schulungs-F1"),
    ]:
        if (output / "scientific" / f"{name}.svg").exists():
            d += f'<details><summary>{label}</summary><img class="figure" src="scientific/{name}.svg" alt="{label}"></details>'
    d += '<p><a href="scientific/metadata_template.csv">Optionale Metadatenvorlage</a> · <a href="scientific/courses.csv">Schulungszähler und deskriptive Ergebnisse</a> · <a href="scientific/strata.csv">Merkmalsgruppen</a></p><p>Handschrift-CER/WER und Seitenqualität sind ohne unabhängige lokalisierte Transkripte nicht verfügbar.</p>'
    text += panel("robustness", "D · Dokumenttypen und Robustheit", d)

    e = "<p>Gemessene Seitenkomponenten, komplette Methodenzeit und zugerechnete Zeiten sind unterschiedliche Größen. Der Median enthält keine anteilig erfundenen Ladezeiten.</p>"
    if (output / "scientific/quality_runtime.svg").exists():
        e += '<img class="figure" src="scientific/quality_runtime.svg" alt="Exakter Feld-F1 und beobachtete Methodenzeit nach Cache-Regime">'
    e += table(
        [
            "Verfahren",
            "Seiten mit Zeit",
            "Median (s)",
            "Q25 / Q75 (s)",
            "Min / Max (s)",
            "Volle Methodenzeit (s)",
            "Laden / Warm-up (s)",
            "Warm-up-Aufrufe (Quelllauf)",
            "Zugerechnete Extraktion (s)",
            "Cache-Seiten / Regime",
        ],
        [
            [
                m,
                v["page_time"]["n"],
                number(v["page_time"]["median"]),
                f"{number(v['page_time']['q25'])} / {number(v['page_time']['q75'])}",
                f"{number(v['page_time']['minimum'])} / {number(v['page_time']['maximum'])}",
                number(v["actual_method_wall_seconds"]),
                f"{number(v['load_seconds'])} / {number(v['warmup_seconds'])}",
                v["warmup_calls"],
                number(v["extraction_charged_seconds"]),
                f"{v['cache_pages']} / {v['cache_regime']}",
            ]
            for m, v in payload["effort"].items()
        ],
    )
    e += '<p class="note">Quartile und Min–Max beschreiben beobachtete Zeiten, keine Konfidenzintervalle. Cache-Regime sind grob und keine identischen Messbedingungen. Bei einer Teilmenge gelten vollständige Quelllaufzeiten nur für den Quelllauf; Pareto wird dann nicht bestimmt. Gespeicherte Antwortzeiten können aus wiederverwendeten Ergebnissen stammen.</p>'
    e += table(
        ["Verfahren", "PDF-Kennung", "Ausgewertete Seiten", "Tatsächliche Aufrufe gesamt", "LLM", "VLM"],
        [
            [m, r["document_id"][:12], r["pages"], r["actual_calls"], r["llm_calls"], r["vlm_calls"]]
            for m, v in payload["effort"].items()
            for r in v["document_calls"]
        ],
    )
    e += "<p>Aufrufe enthalten protokollierte Namenshilfsschritte; Warm-up wird separat erfasst. Ein Cache-Treffer erzeugt keinen neuen Zuordnungsaufruf. Legacy-Zähler, widersprüchliche Summen und nicht trennbare Text-/Bildaufrufe bleiben offen.</p>"
    e += table(
        [
            "Verfahren",
            "Gemessen EUR / 1.000 PDFs",
            "Szenario EUR / 1.000 PDFs",
            "Status",
            "RAM-Spitze (Bytes)",
            "GPU-Spitze (Bytes)",
            "Beobachtete Paretofront",
        ],
        [
            [
                m,
                number(v["costs"]["measured_eur_per_1000"]),
                number(v["costs"]["scenario_eur_per_1000"]),
                v["costs"]["status"],
                v["peak_ram_rss_bytes"],
                v["peak_gpu_allocated_bytes"],
                next((r.get("pareto") for r in payload["pareto"] if r["candidate"] == m), "not_assessed"),
            ]
            for m, v in payload["effort"].items()
        ],
    )
    e += (
        "<details><summary>Kostenannahmen und Messgrenzen</summary><p>Es liegen keine unabhängig belegten monetären Messartefakte vor. Konfigurierte Kosten sind kein automatisch validierter Messnachweis. Szenarien nutzen das vorhandene Kostenmodell und beobachtete Seiten pro PDF; Review, Entwicklung und manueller Zeitwert sind getrennt. Fehlende Werte sind nicht null Euro. Die globalen Profilannahmen belegen keine methodenspezifischen Kosten.</p><pre>"
        + esc(json.dumps({m: v["costs"] for m, v in payload["effort"].items()}, ensure_ascii=False, indent=2))
        + '</pre></details><p><a href="scientific/page_timings.csv">Alle Seitenzeiten</a> · <a href="scientific/document_calls.csv">Aufrufe je PDF</a> · <a href="scientific/costs.csv">Kostenannahmen</a> · <a href="scientific/pareto.csv">Pareto-Kriterien</a></p>'
    )
    text += panel("efficiency", "E · Effizienz und Kosten", e)

    f = f"<p>95-%-Cluster-Perzentilbootstrap, {payload['bootstrap']['resamples']} Wiederholungen, Seed {payload['bootstrap']['seed']}. Ganze Abhängigkeitsgruppen werden gezogen, Zähler gepoolt und Metriken neu berechnet; keine Feldstichproben und kein Mittelwert von Kurs-F1. Für Paare gelten identische gezogene Gruppen.</p>"
    f += f'<div class="note">Mindestens {payload["bootstrap"]["minimum_groups"]} geprüfte Gruppen und eine einheitliche bekannte Phase sind nötig. Die Schranke ist keine Poweranalyse. Aktuell: {payload["groups"]} Gruppen; dokumentierte Phasen {esc(payload["observed_phases"])}. Intervalle sind keine pauschalen Signifikanz- oder Kausalitätsnachweise.</div>'
    f += table(
        ["Verfahren", "Status", "Gruppen", "Exakter F1", "95-%-Intervall"],
        [
            [
                r["candidate"],
                r["status"],
                r["groups"],
                percent(r["estimates"]["exact_f1"]),
                "nicht bestimmbar"
                if r["intervals"]["exact_f1"]["low"] is None
                else percent(r["intervals"]["exact_f1"]["low"])
                + " bis "
                + percent(r["intervals"]["exact_f1"]["high"]),
            ]
            for r in payload["intervals"]
            if r["mode"] == "original_roles"
        ],
    )
    f += table(
        ["Basis", "Vergleich", "Gruppen", "Status", "Δ exakter F1 (pp)", "95-%-Intervall (pp)"],
        [
            [
                r["baseline"],
                r["comparison"],
                r["groups"],
                r["status"],
                number(r.get("estimates", {}).get("exact_f1")),
                "nicht bestimmbar"
                if r.get("intervals", {}).get("exact_f1", {}).get("low") is None
                else number(r["intervals"]["exact_f1"]["low"])
                + " bis "
                + number(r["intervals"]["exact_f1"]["high"]),
            ]
            for r in payload["paired"]
        ],
    )
    f += "<p>Δ ist Vergleich minus Basis. Fehlende Seiten behalten ihre Referenznenner; vollständig fehlende Kandidaten werden markiert. Identische PDF-Hashes sind kein Nachweis gleicher Prompts/Hardware. Teilnehmermetriken sind zusätzliche deskriptive Größen; die bestehenden Bootstrap-Intervalle beziehen sich auf Feld-Recall, exakten F1 und Levenshtein-F1.</p>"
    f += (
        "<details><summary>Vorhandene Hybrid-/Pipelinegegenproben</summary>"
        + table(
            [
                "Basis",
                "Vergleich",
                "Status",
                "Korrigierte Felder",
                "Regressionen",
                "Neu gepaarte Referenzen",
                "Δ volle Zeit (s)",
            ],
            [
                [
                    r["baseline"],
                    r["comparison"],
                    r["status"],
                    r.get("counts", {}).get("corrected"),
                    r.get("counts", {}).get("regressed"),
                    r.get("formerly_unpaired_references_matched"),
                    number(r.get("method_wall_delta_seconds")),
                ]
                for r in payload["ablations"]
            ],
        )
        + "<p>Rein beschreibend, keine Kausalitätsbehauptung. Neu gepaart ist keine unabhängig bestätigte Person.</p></details>"
    )
    f += '<p><a href="scientific/intervals.csv">Alle Intervalle</a> · <a href="scientific/paired.csv">Alle gepaarten Effekte</a> · <a href="scientific/matching_effects.csv">Matchingeffekte</a> · <a href="scientific/ablations.csv">Pipelinegegenproben</a></p>'
    text += panel("statistics", "F · Statistischer Vergleich", f)
    text += (
        '<footer><details><summary>Daten, Bewertungsprotokoll und Reproduzierbarkeit</summary><div class="links">'
        + "".join(
            f'<a href="{path}">{label}</a>'
            for path, label in [
                ("scientific/analysis.json", "Zentrale Analyse JSON"),
                ("scientific/dashboard.csv", "Dashboard CSV"),
                ("scientific/metric_definitions.csv", "Metrikdefinitionen"),
                ("scientific/participant_scores.csv", "Teilnehmerzähler"),
                ("scientific/participant_cases.csv", "Teilnehmerfälle"),
                ("identity.json", "Laufidentität"),
                ("config.json", "Bewertungskonfiguration"),
                ("standard_report.html", "Unveränderter Standardbericht"),
                ("zuordnungen.html", "Zuordnungsprotokoll"),
                ("error_analysis/summary.json", "Fehlerzähler JSON"),
            ]
        )
        + "</div><p>Die Referenz ist schulungsbezogen und muss die tatsächlich gemeinten PDF-Personen abbilden. Eine Buchungs-/Abschlussliste beweist keine Anwesenheit. Historische Extraktionen werden weder korrigiert noch erneut ausgeführt.</p></details></footer>"
    )
    text += "</main>"
    target.write_text(
        document("Modellvergleich – wissenschaftliche Analyse", text, script_source=SCRIPT), encoding="utf-8"
    )
    return target
