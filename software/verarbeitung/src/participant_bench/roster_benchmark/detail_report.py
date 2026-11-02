"""Explain saved grading decisions without inference, reference reloads or score changes."""

import base64
import csv
import hashlib
import html
import math
import os
from collections import Counter, defaultdict
from pathlib import Path

from ..config import METHODS
from ..excel_columns import field_labels
from ..identifiers import user_id_rule
from ..io import digest, file_hash, read_json, read_jsonl, write_json
from ..schema import PageResult
from .config import BenchmarkConfig
from .matching import FIELDS, normalize, pair_evidence, similarity

STATUS = {"matched": "Zugeordnet", "missing": "Referenzperson ohne Zuordnung", "extra": "Ausgabe ohne Zuordnung",
          "ambiguous": "Mehrdeutige Zuordnung", "identity_conflict": "Widerspruch zwischen ID und Namen",
          "duplicate_prediction": "Doppelte Modellausgabe", "empty_prediction": "Keine lesbaren Ausgabefelder"}
REASONS = {"reference_missing_or_masked": "Referenzwert fehlt oder ist maskiert: aus der Bewertung ausgeschlossen",
           "prediction_explicitly_masked_or_placeholder_confirm_in_pdf": "Ausgabe ausdrücklich maskiert/Platzhalter: ausgeschlossen, am PDF bestätigen",
           "not_comparable_extra_field": "Zusätzliches Feld hier nicht bewertbar",
           "fewer_than_two_observed_fields": "Weniger als zwei vergleichbare Namens-/Kurzzeichenfelder",
           "below_minimum_similarity": "Gewichtete Namens-/Kurzzeichenähnlichkeit unter Mindestwert",
           "below_minimum_name_similarity": "Auch das ähnlichste Namensfeld liegt unter dem Mindestwert",
           "no_readable_fields": "Keine lesbaren Felder für eine Paarung",
           "low_similarity": "Schwache Paarung: Best-Fit bleibt erhalten, manuelle Prüfung nötig",
           "ambiguous": "Nahezu gleichwertige globale Alternative: Paarung ist prüfpflichtig",
           "identity_conflict": "ID und Namensangaben widersprechen sich",
           "role_unconfirmed": "Kursleiterrolle nicht eindeutig belegt; Person und Rolle manuell prüfen",
           "duplicate_prediction": "Inhaltlich doppelte Ausgabe: Paarung/Ausgabe prüfen"}
STYLE = """body{font:16px system-ui,sans-serif;max-width:1600px;margin:24px auto;padding:0 20px;background:#f5f7fa;color:#193346}
h1,h2,h3{color:#163e56}a{color:#095f87}table{border-collapse:collapse;width:100%;background:white;margin:12px 0 24px}
th,td{padding:9px;border:1px solid #d9e2e9;text-align:left;vertical-align:top;white-space:pre-wrap;overflow-wrap:anywhere}
th{background:#e9eff5}code{background:#e7edf2;padding:2px 4px;white-space:pre-wrap}.box,article{padding:16px;background:white;border:1px solid #d9e2e9;border-radius:8px;margin:16px 0}
.scroll{overflow-x:auto}.formula{font-family:monospace;background:#e6f0f7;padding:12px}.bad{background:#fff0eb}.ok{background:#eef8ef}.muted{color:#536a7c}
details{margin:14px 0}summary{cursor:pointer;font-weight:600}.filters{position:sticky;top:0;padding:12px;background:#e8eff5;z-index:2}
input,select{padding:7px;margin:4px;max-width:95%}[hidden]{display:none!important}@media print{.filters{display:none}details{display:block}article{break-inside:avoid}}
"""
SCRIPT = """(() => {
const search=document.getElementById('search'), status=document.getElementById('status'), field=document.getElementById('field');
if(!search) return;
const apply=()=>{let count=0;for(const item of document.querySelectorAll('article.case')){
const show=(!status.value||item.dataset.status===status.value)&&item.dataset.search.toLocaleLowerCase().includes(search.value.toLocaleLowerCase());
item.hidden=!show;if(show) count++;for(const row of item.querySelectorAll('tr[data-field]'))row.hidden=!!field.value&&row.dataset.field!==field.value;}
document.getElementById('visible-count').textContent=String(count);};
for(const control of [search,status,field])control.addEventListener('input',apply);apply();
})();"""


def esc(value):
    return html.escape(str(value) if value is not None else "—", quote=True)


def number(value):
    return "—" if value is None else format(float(value), ".12g").replace(".", ",")


def truth(value):
    return value is True or str(value).lower() == "true"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def document(title, content, *, interactive=False, script_source=None):
    policy = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; connect-src 'none'"
    script = ""
    if interactive or script_source is not None:
        code = SCRIPT if script_source is None else script_source
        fingerprint = base64.b64encode(hashlib.sha256(code.encode()).digest()).decode()
        policy += f"; script-src 'sha256-{fingerprint}'"
        script = f"<script>{code}</script>"
    return (f'<!doctype html><html lang="de"><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="Content-Security-Policy" content="{esc(policy)}">'
            f"<title>{esc(title)}</title><style>{STYLE}</style><body>{content}{script}</body></html>")


def table(headings, rows):
    return '<div class="scroll"><table><thead><tr>' + "".join(f"<th>{esc(h)}</th>" for h in headings) + (
        "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>"
                                        for row in rows) + "</tbody></table></div>")


def contribution(row, config):
    eligible = truth(row["assessable"])
    return dict(reference_fields=int(eligible and bool(row["reference_row"])),
                predicted_fields=int(eligible and bool(normalize(row["prediction_value"], row["field"], config))),
                similarity_credit=float(row["similarity"] or 0) if eligible else 0.0,
                exact_fields=int(eligible and truth(row["exact"])))


def totals(rows, config):
    result = dict(reference_fields=0, predicted_fields=0, similarity_credit=0.0, exact_fields=0)
    for row in rows:
        for key, value in contribution(row, config).items():
            result[key] += value
    return result


def formula(count):
    r, p, credit, exact = (count[key] for key in (
        "reference_fields", "predicted_fields", "similarity_credit", "exact_fields"))
    soft = 100 * 2 * credit / (r + p) if r and r + p else None
    strict = 100 * 2 * exact / (r + p) if r and r + p else None
    if not r:
        return (f'<div class="formula">R = {r}; P = {p}; C = {number(credit)}; E = {exact}<br>'
                'Nur Nenner-/Ausschlussbeitrag, kein eigener F1 ohne bewertbare Referenzfelder.</div>')
    return (f'<div class="formula">R = {r}; P = {p}; C = {number(credit)}; E = {exact}<br>'
            f"Levenshtein-Feld-F1 = 100 × 2 × {number(credit)} / ({r} + {p}) = {number(soft)} %<br>"
            f"Exakter Feld-F1 = 100 × 2 × {exact} / ({r} + {p}) = {number(strict)} %</div>")


def prediction_key(row):
    return row["method"], row["document_id"], row["page_number"], row["output_index"]


def normalized_reference(reference, config):
    return {field: normalize(reference[field], field, config) for field in FIELDS}


def name_order_hint(observed, references, config):
    if not observed["first_name"] or not observed["last_name"] or not references:
        return False
    direct, swapped = [], []
    for reference in references:
        expected = normalized_reference(reference, config)
        direct.append((similarity(observed["first_name"], expected["first_name"]) +
                       similarity(observed["last_name"], expected["last_name"])) / 2)
        swapped.append((similarity(observed["last_name"], expected["first_name"]) +
                        similarity(observed["first_name"], expected["last_name"])) / 2)
    return max(swapped) >= 0.8 and max(swapped) - max(direct) >= 0.25


def candidate_table(case, fields, references, config, reference_config, labels):
    observed = {row["field"]: normalize(row["prediction_value"], row["field"], config) for row in fields}
    ids = Counter(normalize(ref["user_id"], "user_id", config) for ref in references
                  if reference_config.usable_id(ref["user_id"]))
    results = []
    for reference in references:
        expected = normalized_reference(reference, config)
        evidence = pair_evidence(observed, expected, config, reference_config, ids[expected["user_id"]])
        selected = str(reference["row_number"]) == case["reference_row"] and case["status"] == "matched"
        reasons = [REASONS[reason] for reason in evidence["rejection_reasons"]]
        if config.mode == "best_fit" and (evidence["weighted_similarity"] < config.minimum_similarity or
                                         not evidence["conservative_qualifies"]):
            reasons.append(REASONS["low_similarity"])
        if case["status"] in ("duplicate_prediction", "identity_conflict"):
            reasons.append(STATUS[case["status"]] + ": automatische Zuordnung gesperrt")
        elif case["status"] == "ambiguous":
            reasons.append("Globale Alternativzuordnung liegt innerhalb der Mehrdeutigkeitsgrenze")
        elif evidence["qualifies"] and not selected:
            reasons.append("Grundsätzlich zugelassen; nicht das tatsächlich bewertete globale Paar")
        components = evidence["observations"]
        results.append((evidence["anchor"], evidence["weighted_similarity"], selected, [
            reference["row_number"], "TATSÄCHLICH ZUGEORDNET" if selected else "nur Kandidat; keine Punkte hier",
            *(reference[field] for field in FIELDS),
            *(number(components.get(field)) for field in FIELDS),
            number(evidence["weighted_similarity"]), "ja" if evidence["anchor"] else "nein",
            "ja" if evidence["qualifies"] else "nein", "; ".join(reasons) or "Eindeutige globale Zuordnung",
        ]))
    results.sort(key=lambda item: (item[2], item[0], item[1]), reverse=True)
    content = table(["Referenzzeile", "Verwendung", *(labels[field] for field in FIELDS),
                     "Ähnlichkeit Vorname", "Ähnlichkeit Nachname", "Ähnlichkeit User ID", "Ähnlichkeit Kurzzeichen",
                     "Feldähnlichkeit im Mittel" if config.mode == "best_fit" else "Gewichtete Ähnlichkeit",
                     "Eindeutige exakte ID", "Zulassung", "Begründung"],
                    [item[3] for item in results])
    hint = name_order_hint(observed, references, config)
    warning = ('<p class="bad">Diagnosehinweis: Vertauschte Vor-/Nachnamensfelder passen deutlich besser zu einer '
               'Referenz. Dieser Hinweis ändert keine Zuordnung und vergibt keine Punkte.</p>' if hint else "")
    explanation = ("Best-Fit maximiert zuerst die Paaranzahl, dann die Summe aller bewertbaren Feldähnlichkeiten "
                   "mit gleichem Gewicht, einschließlich lesbarer IDs. Fehlende Werte geben keine Teilpunkte. "
                   "Die Mittelwerte dienen der Anzeige; optimiert wird die Summe. Die bisherigen Mindestwerte "
                   "markieren schwache Paarungen und sperren sie nicht." if config.mode == "best_fit" else
                   "Die Gewichtung für die Zuordnung lautet: (Vorname × 1 + Nachname × 1 + Kurzzeichen × 0,5) / "
                   "Summe der Gewichte vorhandener Felder. Eine eindeutige exakte ID hat Vorrang. "
                   "ID-Ähnlichkeiten vergeben ohne exakte ID keine Zuordnungspriorität.")
    return warning + f"<details><summary>Alle {len(references)} Referenzkandidaten dieser Schulung</summary>" + (
        f"<p><strong>Klassenfilter:</strong> Nur {esc(labels['class_id'])} = {esc(case['class_id'])}. "
        "Einträge anderer Klassen sind vor dem Vergleich ausgeschlossen.</p>" +
        "<p>Nur das tatsächlich zugeordnete Paar wird bewertet. Ähnliche Alternativen erhalten keine zusätzlichen Punkte. " +
        explanation + "</p>" + content + "</details>"), hint


def case_html(case, fields, references, config, labels, raw_people, source, destination):
    status = case["status"]
    terms = " ".join(str(value or "") for row in fields for key, value in row.items()
                     if key in ("reference_value", "prediction_value", "reference_row", "source_file", "page_number"))
    title = (f"{STATUS.get(status, status)} · Referenzzeile {case['reference_row'] or '—'} · "
             f"PDF-Seite {case['page_number'] or '—'} · Ausgabeindex {case['output_index'] or '—'}")
    content = (f'<article class="case" data-status="{esc(status)}" data-search="{esc(terms)}" '
               f'data-document="{esc(case.get("document_id") or "")}" '
               f'data-page="{esc(case.get("page_number") or "")}" '
               f'data-output-index="{esc(case.get("output_index", ""))}"><h3>{esc(title)}</h3>')
    content += f"<p>Datei: {esc(case.get('source_file'))} · Zuordnungsquelle: {esc(case.get('matching_source') or 'keine')} · "
    content += f"Zuordnungsähnlichkeit: {esc(case.get('identity_similarity') or '—')} · "
    content += f"Abstand zur globalen Alternative: {esc(case.get('alternative_gap') or '—')}</p>"
    if case.get("matching_review_reasons"):
        content += '<p class="bad">Zuordnungsprüfung: ' + esc("; ".join(
            REASONS.get(reason, reason) for reason in case["matching_review_reasons"].split(" | "))) + "</p>"
    if case["document_id"] and case["page_number"] and source:
        image = source / "pages" / f"{case['document_id']}-p{int(case['page_number']):04d}.png"
        if image.resolve().is_relative_to(source.resolve()) and image.is_file():
            try:
                link = os.path.relpath(image, destination).replace(os.sep, "/")
                content += f'<p><a href="{esc(link)}">Originale gerenderte PDF-Seite öffnen</a></p>'
            except ValueError:
                content += f"<p>PDF-Seitenbild auf anderem Laufwerk: {esc(image)}</p>"
    raw = raw_people.get(prediction_key(case))
    if raw:
        content += f"<p>Gedruckte Zeilennummer laut Modell: {esc(raw.row_ref)}. Der Ausgabeindex beginnt bei 0.</p>"
    elif case["document_id"]:
        content += "<p>Rohvorhersage nicht verfügbar; die Modellspalte zeigt den gespeicherten bewerteten CSV-Wert.</p>"
    if status != "matched":
        content += ('<p class="bad">Keine gewertete Paarung. Referenzzeilen erhöhen R; nicht zugeordnete Ausgaben '
                    'erhöhen P. Hier werden keine ähnlichen Wörter aus anderen Personenzeilen gutgeschrieben.</p>')
    content += '<div class="scroll"><table><thead><tr>' + "".join(f"<th>{esc(label)}</th>" for label in (
        "Feld", "Referenz: Original", "Modell: Original (wenn verfügbar)", "Bewerteter Wert", "Feldstatus", "Referenz normalisiert",
        "Ausgabe normalisiert", "Distanz d", "Max. Länge L", "Teilpunkte", "Beitrag R", "Beitrag P", "Exakt", "Begründung"))
    content += "</tr></thead><tbody>"
    for row in fields:
        field = row["field"]
        left, right = normalize(row["reference_value"], field, config.matching), normalize(row["prediction_value"], field, config.matching)
        count = contribution(row, config.matching)
        eligible = truth(row["assessable"])
        reason = REASONS.get(row["exclusion_reason"], row["exclusion_reason"])
        if not reason:
            reason = "Tatsächlich zugeordnetes Paar" if status == "matched" else "Keine bewertete Personenpaarung"
            if status == "matched" and not right:
                reason += "; Referenz lesbar, Ausgabe fehlt: null Punkte, R bleibt im Nenner"
        raw_value = getattr(raw, FIELDS[field]).value if raw else row["prediction_value"]
        credit = (f"1 − {row['levenshtein_distance']} / {max(len(left), len(right))} = {number(count['similarity_credit'])}"
                  if eligible and status == "matched" and right else number(count["similarity_credit"]) if eligible else "ausgeschlossen")
        cells = [labels[field], row["reference_value"], raw_value, row["prediction_value"], row["prediction_state"],
                 left, right, row["levenshtein_distance"] or "—", max(len(left), len(right)), credit,
                 count["reference_fields"], count["predicted_fields"], "ja" if truth(row["exact"]) else "nein" if eligible else "—", reason]
        css = "ok" if truth(row["exact"]) else "bad" if eligible else "muted"
        content += f'<tr data-field="{field}" class="{css}">' + "".join(f"<td>{esc(cell)}</td>" for cell in cells) + "</tr>"
    content += "</tbody></table></div>" + formula(totals(fields, config.matching))
    hint = False
    if case["output_index"] != "" and case["document_id"]:
        candidates, hint = candidate_table(case, fields, references, config.matching, config.reference, labels)
        content += candidates
    return content + "</article>", hint


def render_details(output: Path, *, source_run: Path | None = None) -> Path:
    """Refresh presentation only; frozen reference, predictions and numeric result files remain untouched."""
    output = output.resolve()
    metrics, identity = read_json(output / "metrics.json"), read_json(output / "identity.json")
    config = BenchmarkConfig.model_validate(read_json(output / "config.json"))
    labels = field_labels(metrics.get("columns"))
    fields, cases = read_csv(output / "fields.csv"), read_csv(output / "participants.csv")
    references = read_json(output / "reference_snapshot.json")["people"]
    source_names = {row["document_id"]: " | ".join(Path(path).name for path in row["source_files"].split(" | "))
                    for row in read_csv(output / "documents.csv")}
    source = Path(source_run or identity["source_run"])
    raw_people, source_pages = {}, defaultdict(list)
    for method in metrics["methods"]:
        if method not in {*METHODS, "ocr_rules"}:
            raise ValueError("Unbekanntes Verfahren im gespeicherten Vergleich")
        path = source / method / "extractions.jsonl"
        if path.is_file() and method in identity["extraction_sha256"]:
            if file_hash(path) != identity["extraction_sha256"][method]:
                raise ValueError("Quellvorhersagen wurden seit dem gespeicherten Vergleich verändert")
            for record in read_jsonl(path):
                page = PageResult.model_validate(record)
                source_pages[method].append(dict(source_file=source_names.get(page.document_id, ""),
                                                 page_number=page.page_number, rows=len(page.participants), status=page.status,
                                                 parse_status=page.parse_status, error=page.error))
                for index, person in enumerate(page.participants):
                    raw_people[method, page.document_id, str(page.page_number), str(index)] = person
    from ..output_order import ordered_rows

    documents = {row["document_id"]: i for i, row in enumerate(read_csv(output / "documents.csv"))}
    cases = ordered_rows(cases, documents, {method: i for i, method in enumerate(metrics["methods"])})
    grouped_fields, grouped_cases, course_field_rows, course_references = (defaultdict(list) for _ in range(4))
    for reference in references:
        course_references[reference["class_id"]].append(reference)
    for row in fields:
        key = row["method"], row["class_id"], row["reference_row"], row["document_id"], row["page_number"], row["output_index"]
        grouped_fields[key].append(row)
        course_field_rows[row["method"], row["class_id"]].append(row)
    for row in cases:
        grouped_cases[row["method"], row["class_id"]].append(row)
    pages_dir = output / "details"
    pages_dir.mkdir(exist_ok=True)
    overview, checks = [], {}
    introduction = ("<p>Dieser Bericht erklärt die gespeicherten Ergebnisse. Keine Modellaufrufe, keine neue "
                    "Referenzdatei, keine automatische Korrektur und keine Änderung der Kennzahlen.</p>"
                    "<p>Ausgaben folgen der Anwesenheitsliste: PDF, Seite und ursprünglicher Eintragsindex. "
                    "Die Referenzzuordnung verändert diese Reihenfolge nicht. Nur in der Referenz vorhandene "
                    "Personen stehen anschließend in einem eigenen Abschnitt.</p>"
                    "<p>R = bewertbare Referenzfelder, P = ausgegebene bewertbare Felder, C = Summe der "
                    "Levenshtein-Teilpunkte tatsächlicher Paarungen, E = Anzahl exakter Feldtreffer. "
                    "Fehlende Personen und zusätzliche Ausgaben behalten ihre Beiträge im Nenner.</p>"
                    "<p>Der Gesamtwert wird aus den summierten Beiträgen aller Felder berechnet; Einzelfall-F1-Werte "
                    "werden nicht gemittelt. Die angezeigten Nachkommastellen sind gerundet.</p>"
                    "<p>Eine Personenpaarung wird innerhalb derselben Class ID global und höchstens einmal "
                    "verwendet. Erst danach werden ihre Felder bewertet. Wörter aus verschiedenen Personen "
                    "werden nicht für einen günstigeren Feldscore kombiniert. Eine fehlgeschlagene Zuordnung "
                    "kann gleichzeitig eine fehlende Referenzperson und eine nicht zugeordnete Modellausgabe "
                    "erzeugen. Die Anzahl ausgegebener Personen allein ist daher kein Erkennungsqualitätsnachweis.</p>")
    introduction += ("<p><strong>Modus: globales Best-Fit.</strong> Möglichst viele lesbare Ausgaben werden mit "
                     "verschiedenen Referenzzeilen gepaart; unter diesen vollständigen Zuteilungen wird die Summe "
                     "der Feldähnlichkeiten maximiert. Schwache/mehrdeutige Paarungen bleiben prüfpflichtig und "
                     "sind keine bestätigten Identitäten. Werte und Feldrollen werden nicht korrigiert.</p>"
                     if config.matching.mode == "best_fit" else
                     "<p><strong>Modus: konservativ.</strong> Mindestähnlichkeiten können eine Paarung verhindern; "
                     "mehrdeutige und widersprüchliche Kandidaten erhalten keine automatische Zuordnung.</p>")
    for method, score in metrics["methods"].items():
        if "overall" not in score:
            overview.append(f"<h2>{esc(method)}</h2><p>Kein Teilnehmerfeldscore: {esc(score.get('reason'))}</p>")
            continue
        method_fields = [row for row in fields if row["method"] == method]
        count = totals(method_fields, config.matching)
        calculated = 100 * 2 * count["similarity_credit"] / (count["reference_fields"] + count["predicted_fields"]) if count["reference_fields"] else None
        consistent = (all(math.isclose(count[key], score["overall"][key], abs_tol=1e-9) for key in count) and
                      ((calculated is None and score["score_percent"] is None) or
                       (calculated is not None and score["score_percent"] is not None and
                        math.isclose(calculated, score["score_percent"], abs_tol=1e-9))))
        checks[method] = dict(count, saved_score_percent=score["score_percent"], contributions_match_saved_metrics=consistent,
                              name_order_hints=0, source_pages=source_pages[method])
        overview.append(f"<section><h2>{esc(method)}: {number(score['score_percent'])} %</h2>" + formula(count))
        if score.get("conservative_score_percent") is not None:
            overview.append(f"<p>Konservativer Vergleich auf denselben unveränderten Ausgaben: "
                            f"{number(score['conservative_score_percent'])} % bei "
                            f"{score['conservative_assigned_participants']} Paarungen. "
                            "Ein höherer Best-Fit-Score belegt keine verbesserte OCR.</p>")
        overview.append(f"<p>{score['assigned_participants']} / {score['reference_participants']} Referenzpersonen zugeordnet · "
                        f"{score['predicted_participants']} Ausgaben · {score['missing_participants']} nicht zugeordnete Referenzpersonen · "
                        f"{score['extra_participants']} nicht zugeordnete Ausgaben. "
                        f"Summenprüfung der Einzelbeiträge: {'stimmt mit metrics.json überein' if consistent else 'ABWEICHUNG – prüfen'}.</p>")
        overview.append(table(["Status", "R", "P", "C", "E"], [
            [STATUS.get(status, status), *(totals([row for row in method_fields if row["status"] == status], config.matching)[key]
                                          for key in ("reference_fields", "predicted_fields", "similarity_credit", "exact_fields"))]
            for status in dict.fromkeys(row["status"] for row in method_fields)]))
        overview.append(table(["Feld", "R", "P", "C", "E"], [
            [labels[field], *(totals([row for row in method_fields if row["field"] == field], config.matching)[key]
                              for key in ("reference_fields", "predicted_fields", "similarity_credit", "exact_fields"))]
            for field in FIELDS]))
        if source_pages[method]:
            overview.append(table(["Datei", "PDF-Seite", "Ausgegebene Personen", "Verarbeitungsstatus", "Antwortformat", "Verarbeitungshinweis"],
                                  [[row["source_file"], row["page_number"], row["rows"], row["status"], row["parse_status"],
                                    row["error"] or "—"] for row in source_pages[method]]))
        for (selected, course), records in grouped_cases.items():
            if selected != method:
                continue
            reference_rows = course_references[course]
            filename = f"{digest(method)[:10]}-{digest(course)[:12]}.html"
            course_fields = course_field_rows[method, course]
            cards, hints = [], 0
            missing_heading = False
            for case in records:
                if not case["document_id"] and not missing_heading:
                    cards.append("<h2>Nur in der Referenz vorhanden</h2><p>Diese Personen haben keine "
                                 "zugeordnete Position in der Anwesenheitsliste.</p>")
                    missing_heading = True
                key = method, course, case["reference_row"], case["document_id"], case["page_number"], case["output_index"]
                card, hint = case_html(case, grouped_fields[key], reference_rows, config, labels, raw_people,
                                       source if source.is_dir() else None, pages_dir)
                cards.append(card)
                hints += hint
            checks[method]["name_order_hints"] += hints
            controls = ('<div class="filters"><label>Suche <input id="search" type="search" placeholder="Name, ID, Referenzzeile …"></label>'
                        '<label>Status <select id="status"><option value="">alle</option>' +
                        "".join(f'<option value="{key}">{esc(value)}</option>' for key, value in STATUS.items()) +
                        '</select></label><label>Feld <select id="field"><option value="">alle</option>' +
                        "".join(f'<option value="{key}">{esc(labels[key])}</option>' for key in FIELDS) +
                        '</select></label><span id="visible-count"></span> Fälle sichtbar. Filter ändern keine Kennzahlen.</div>')
            content = (f'<p><a href="../details.html">Zur Gesamtberechnung</a> · <a href="../report.html">Zur Übersicht</a></p>'
                       f"<h1>{esc(method)} · {esc(labels['class_id'])} {esc(course)}</h1>" + introduction +
                       formula(totals(course_fields, config.matching)) +
                       f"<p>{'Prüfgrenzen (keine Sperre)' if config.matching.mode == 'best_fit' else 'Mindestähnlichkeit'}: "
                       f"{number(config.matching.minimum_similarity)}; Namensfeld-Grenze: "
                       f"{number(config.matching.minimum_name_similarity)}; globale Mehrdeutigkeitsgrenze: "
                       f"{number(config.matching.ambiguity_margin)}. Unterschriften und Datum werden nicht bewertet.</p>" +
                       controls + "".join(cards))
            (pages_dir / filename).write_text(document(f"Detailvergleich {method}", content, interactive=True), encoding="utf-8")
            overview.append(f'<p><a href="details/{filename}"><strong>Alle Einzelvergleiche für {esc(labels["class_id"])} '
                            f'{esc(course)} öffnen</strong></a> · {len(records)} Fälle · {hints} Hinweise auf Namensreihenfolge</p>')
        overview.append("</section>")
    scope = metrics["scope"]
    content = ('<p><a href="report.html">Zur bisherigen Übersicht</a></p><h1>Detailvergleich und vollständige Berechnung</h1>' +
               introduction + f"<p>{scope['input_pdfs']} PDFs · {scope['reference_rows_in_scope']} Referenzpersonen im Vergleich. "
               f"{scope['reference_rows_outside_input']} Referenzzeilen anderer Schulungen werden nicht bewertet.</p>" +
               f"<p>Quelllauf: {esc(source.name)} · Referenz: {esc(Path(identity['reference_file']).name)} · "
               f"Tabellenblatt: {esc(identity.get('reference_sheet'))}. Verwendet wird ausschließlich der gespeicherte "
               "Referenz-Snapshot dieses Vergleichs.</p>" +
               "<div class='box'><strong>Normalisierung:</strong> Unicode NFC und vereinheitlichte Leerzeichen bei Namen/" 
               "Kurzzeichen; Groß-/Kleinschreibung gemäß gespeicherter Konfiguration. "
               + esc(user_id_rule(config.matching.ignore_leading_user_id_zeros)) +
               " Bindestriche, Akzente und andere Zeichen werden nicht entfernt. "
               f"Unsichere ausgegebene Textwerte werden {'bewertet' if config.matching.score_uncertain_values else 'nicht bewertet'}. "
               "Levenshtein-Ähnlichkeit = 1 − Distanz / maximale Zeichenlänge. Leere/maskierte Referenzwerte sind "
               "ausgeschlossen. Ein fehlender Modellwert bei lesbarer Referenz ist weiterhin ein Fehler. "
               "Ein leeres Benutzerfeld allein beweist keine Schwärzung.</div>" + "".join(overview) +
               '<p><a href="fields.csv">Alle Feldbeiträge als CSV</a> · <a href="identity.json">Herkunft und Prüfsummen</a> · '
               '<a href="reference_snapshot.json">Eingefrorene Referenz</a></p>')
    path = output / "details.html"
    path.write_text(document("Detailvergleich", content), encoding="utf-8")
    write_json(pages_dir / "calculation_checks.json", checks)
    write_json(pages_dir / "presentation_identity.json", dict(
        result_artifacts={name: file_hash(output / name) for name in (
            "metrics.json", "identity.json", "reference_snapshot.json", "config.json", "fields.csv", "participants.csv")},
        rendering_implementation={name: file_hash(Path(__file__).parent / name) for name in ("detail_report.py", "matching.py")},
        output_order_sha256=file_hash(Path(__file__).parent.parent / "output_order.py"),
        grading_implementation=identity.get("implementation"), new_inference=False, modified_scores=False))
    main = output / "report.html"
    if main.is_file():
        existing = main.read_text(encoding="utf-8")
        if 'href="details.html"' not in existing:
            main.write_text(existing.replace("</h1>", '</h1><p><a href="details.html"><strong>Detailvergleich: '
                            'Teilnehmer, Feldwerte und Berechnung öffnen</strong></a></p>', 1), encoding="utf-8")
    from .assignment_report import render_assignments

    render_assignments(output, source_run=source)
    return path
