"""A separate name-to-name audit of saved assignments; never infer or change a pairing."""

from collections import Counter, defaultdict
from pathlib import Path

from ..config import METHODS
from ..excel_columns import field_labels
from ..identifiers import user_id_rule
from ..io import digest, file_hash, read_json, read_jsonl
from ..schema import PageResult
from .config import BenchmarkConfig
from .detail_report import (
    REASONS,
    STATUS,
    candidate_table,
    document,
    esc,
    normalized_reference,
    number,
    prediction_key,
    read_csv,
    table,
    truth,
)
from .matching import FIELDS, normalize, pair_evidence

FILTER_SCRIPT = """(() => {
const search=document.getElementById('names-search'),method=document.getElementById('names-method'),
status=document.getElementById('names-status'),review=document.getElementById('names-review');
const apply=()=>{let count=0;for(const row of document.querySelectorAll('tr.name-pair')){
const visible=(!method.value||row.dataset.method===method.value)&&(!status.value||row.dataset.status===status.value)
&&(!review.checked||row.dataset.review==='true')&&row.dataset.search.toLocaleLowerCase().includes(search.value.toLocaleLowerCase());
row.hidden=!visible;if(visible)count++;}document.getElementById('names-count').textContent=String(count);};
for(const control of [search,method,status,review])control.addEventListener('input',apply);apply();
})();"""


def case_key(row):
    return (row["method"], row["class_id"], row["reference_row"], row["document_id"],
            row["page_number"], row["output_index"])


def shown_name(first, last):
    return f"<strong>Vorname:</strong> {esc(first or '—')}<br><strong>Nachname:</strong> {esc(last or '—')}"


def load_originals(source, identity, methods):
    result = {}
    for method in methods:
        if method not in {*METHODS, "ocr_rules"}:
            raise ValueError("Unbekanntes Verfahren im gespeicherten Vergleich")
        path = source / method / "extractions.jsonl"
        expected = identity["extraction_sha256"].get(method)
        if not path.is_file() or expected is None:
            continue
        if file_hash(path) != expected:
            raise ValueError("Quellvorhersagen wurden seit dem gespeicherten Vergleich verändert")
        for item in read_jsonl(path):
            page = PageResult.model_validate(item)
            for index, person in enumerate(page.participants):
                result[method, page.document_id, str(page.page_number), str(index)] = person
    return result


def decision(case, fields, references, config, owners, labels, predicted_count):
    status, mode = case["status"], config.matching.mode
    notes = [f"Kandidatenfilter: {labels['class_id']} = {case['class_id']}. "
             f"Nur die {len(references)} Referenzeinträge mit genau dieser Klassen-ID kommen infrage."]
    if status == "missing":
        return (" ".join(notes) + " Keine Modellausgabe zu dieser Referenzperson zugeordnet. "
                "Sie bleibt als fehlend in der Bewertung.", "")
    if status != "matched":
        descriptions = {
            "extra": "Keine Referenzzeile zugeordnet: zu wenige freie Referenzen oder im konservativen Modus keine zulässige Paarung.",
            "ambiguous": "Keine Paarung gewertet: Es gibt eine nahezu gleichwertige globale Alternative.",
            "identity_conflict": "Keine Paarung gewertet: ID und Namens-/Kurzzeichenkombination zeigen auf verschiedene Personen.",
            "duplicate_prediction": "Nicht zugeordnete doppelte Modellausgabe; keine Referenz wird mehrfach verwendet.",
            "empty_prediction": "Keine lesbaren Felder für eine Paarung vorhanden.",
        }
        notes.append(descriptions.get(status, STATUS.get(status, status)))
    elif case["matching_source"] == "global_best_fit":
        notes.append("Gespeicherte globale Best-Fit-Paarung: zuerst möglichst viele Paare, dann maximale Summe der Feldähnlichkeiten im Kurs.")
    elif case["matching_source"] == "exact_user_id":
        notes.append("Eine eindeutig und exakt passende lesbare User ID hatte im konservativen Modus Vorrang.")
    else:
        notes.append("Namens-/Kurzzeichenähnlichkeit erfüllt die konservativen Mindestgrenzen; die globale Paarung wurde übernommen.")
    review = case.get("matching_review_reasons", "")
    if review:
        notes.append("Prüfhinweise: " + "; ".join(REASONS.get(reason, reason) for reason in review.split(" | ")))
    observed = {row["field"]: normalize(row["prediction_value"], row["field"], config.matching) for row in fields}
    ids = Counter(normalize(ref["user_id"], "user_id", config.matching) for ref in references
                  if config.reference.usable_id(ref["user_id"]))
    candidates = []
    for reference in references:
        expected = normalized_reference(reference, config.matching)
        evidence = pair_evidence(observed, expected, config.matching, config.reference, ids[expected["user_id"]])
        utility = evidence.get("optimization_credit") if mode == "best_fit" else (
            (max(predicted_count, len(references)) + 1 if evidence["anchor"] else 0) + evidence["weighted_similarity"])
        selected = status == "matched" and str(reference["row_number"]) == case["reference_row"]
        candidates.append((reference, evidence, utility, selected))
    chosen = next((candidate for candidate in candidates if candidate[3]), None)
    if chosen:
        notes.append(f"Gespeicherte Zuordnungsähnlichkeit: {number(case.get('identity_similarity'))}; "
                     f"lokaler Optimierungsbeitrag: {number(chosen[2])}.")
        rank = 1 + sum(evidence["qualifies"] and utility > chosen[2] + 1e-10
                       for _, evidence, utility, _ in candidates)
        notes.append(f"Die gewählte Referenz hat lokal Rang {rank} unter den zulässigen Kandidaten.")
        if rank > 1:
            notes.append("Ein anderer Name ist lokal ähnlicher. Die globale Einmalvergabe und die übrigen Ausgaben führen jedoch zu dieser Gesamtzuteilung.")
        gap = case.get("alternative_gap")
        if gap != "" and gap is not None:
            notes.append(f"Ohne dieses Paar sinkt der gespeicherte globale Optimierungswert um {number(gap)} Punkte. "
                         "Das ist keine Wahrscheinlichkeit; im Best-Fit-Modus kann auch der Paaranzahl-Bonus enthalten sein.")
    ownership = []
    for reference, evidence, utility, selected in sorted(candidates, key=lambda item: item[2], reverse=True):
        owner = owners.get(str(reference["row_number"]))
        if selected:
            allocation = "DIESEM NAMEN ZUGEORDNET"
        elif owner:
            allocation = (f"Anderer Ausgabe zugeordnet: Seite {owner['page_number']}, Index {owner['output_index']} "
                          f"({owner.get('source_file', '')})")
        else:
            allocation = "Keine gewertete Paarung dieser Referenz"
        ownership.append([reference["row_number"], reference["first_name"], reference["last_name"],
                          number(utility), "ja" if evidence["qualifies"] else "nein", allocation])
    alternatives, _ = candidate_table(case, fields, references, config.matching, config.reference, labels)
    extra = ("<details><summary>Globale Einmalvergabe und Konkurrenz um Referenznamen</summary>" +
             table(["Referenzzeile", labels["first_name"], labels["last_name"], "Lokaler Optimierungswert", "Zulässig", "Tatsächliche Vergabe"], ownership) + "</details>")
    return " ".join(notes), extra + alternatives


def render_assignments(output: Path, *, source_run: Path | None = None) -> Path:
    output = output.resolve()
    identity, metrics = read_json(output / "identity.json"), read_json(output / "metrics.json")
    config = BenchmarkConfig.model_validate(read_json(output / "config.json"))
    labels = field_labels(metrics.get("columns"))
    cases, fields = read_csv(output / "participants.csv"), read_csv(output / "fields.csv")
    source = Path(source_run or identity["source_run"])
    originals = load_originals(source, identity, metrics["methods"])
    grouped, references, assigned, count = defaultdict(list), defaultdict(list), defaultdict(dict), Counter()
    for field in fields:
        grouped[case_key(field)].append(field)
    for reference in read_json(output / "reference_snapshot.json")["people"]:
        references[reference["class_id"]].append(reference)
    for case in cases:
        if case["document_id"] and case["output_index"] != "":
            count[case["method"], case["class_id"]] += 1
        if case["status"] == "matched":
            assigned[case["method"], case["class_id"]][case["reference_row"]] = case
    result = []
    from ..output_order import ordered_rows

    documents = {row["document_id"]: i for i, row in enumerate(read_csv(output / "documents.csv"))}
    cases = ordered_rows(cases, documents, {method: i for i, method in enumerate(metrics["methods"])})
    for case in cases:
        values = {row["field"]: row for row in grouped[case_key(case)]}
        original = originals.get(prediction_key(case))
        first = original.first_name.value if original else values["first_name"]["prediction_value"]
        last = original.last_name.value if original else values["last_name"]["prediction_value"]
        reference_first, reference_last = values["first_name"]["reference_value"], values["last_name"]["reference_value"]
        why, alternatives = decision(case, grouped[case_key(case)], references[case["class_id"]], config,
                                     assigned[case["method"], case["class_id"]], labels, count[case["method"], case["class_id"]])
        search = " ".join(str(value or "") for value in (first, last, reference_first, reference_last,
                          case["source_file"], case["class_id"], case["reference_row"]))
        review = truth(case["review_required"])
        style = "bad" if review else "ok"
        model = shown_name(first, last) if case["document_id"] else "Keine Modellausgabe zugeordnet"
        reference = shown_name(reference_first, reference_last) if case["reference_row"] else "Keine Referenz zugeordnet"
        details = table(["Feld", "Bewertete Ausgabe", "Referenz", "Ausgabe normalisiert", "Referenz normalisiert",
                         "Edit-Distanz", "Feldähnlichkeit", "Status"], [
            [labels[field], values[field]["prediction_value"], values[field]["reference_value"],
             normalize(values[field]["prediction_value"], field, config.matching),
             normalize(values[field]["reference_value"], field, config.matching),
             values[field]["levenshtein_distance"],
             number(values[field]["similarity"] or None), values[field]["prediction_state"]] for field in FIELDS])
        # The existing detail page has a stable, content-derived name; no personal name becomes a path.
        target = f"details/{digest(case['method'])[:10]}-{digest(case['class_id'])[:12]}.html"
        link = f'<p><a href="{esc(target)}">Vollständige Feldberechnung dieser Schulung</a></p>' if (output / target).is_file() else ""
        result.append(f'<tr class="name-pair {style}" data-method="{esc(case["method"])}" '
                      f'data-document="{esc(case["document_id"] or "")}" data-page="{esc(case["page_number"] or "")}" '
                      f'data-output-index="{esc(case["output_index"])}" '
                      f'data-status="{esc(case["status"])}" data-review="{str(review).lower()}" data-search="{esc(search)}">'
                      f'<td>{esc(case["method"])}<br>{esc(labels["class_id"])}: {esc(case["class_id"])}<br>'
                      f'{esc(case["source_file"])}<br>PDF-Seite {esc(case["page_number"] or "—")}, Index {esc(case["output_index"] or "—")}'
                      f'<br>Gedruckte Zeile: {esc(original.row_ref if original else None)}</td>'
                      f'<td>{model}</td><td>{"→" if case["status"] == "matched" else "keine Paarung"}</td>'
                      f'<td>{reference}<br>Referenzzeile: {esc(case["reference_row"] or "—")}</td>'
                      f'<td><strong>{esc(STATUS.get(case["status"], case["status"]))}</strong><br>{esc(why)}'
                      f'<details><summary>Feldbelege und alternative Namen ansehen</summary>{details}{alternatives}{link}</details></td>'
                      f'<td>{"ja" if review else "nein"}</td></tr>')
    controls = ('<div class="filters"><label>Namenssuche <input id="names-search" type="search"></label>'
                '<label>Verfahren <select id="names-method"><option value="">alle</option>' +
                "".join(f'<option value="{esc(method)}">{esc(method)}</option>' for method in metrics["methods"]) +
                '</select></label><label>Status <select id="names-status"><option value="">alle</option>' +
                "".join(f'<option value="{esc(key)}">{esc(value)}</option>' for key, value in STATUS.items()) +
                '</select></label><label><input id="names-review" type="checkbox">nur prüfpflichtig</label>'
                '<span id="names-count"></span> Zeilen sichtbar. Filter verändern keine Paarungen.</div>')
    rules = (f'<details><summary>Gespeicherte Zuordnungsregeln und Schwellenwerte</summary>'
             '<p>Feldähnlichkeit = 1 − Levenshtein-Distanz / maximale Zeichenlänge nach Normalisierung. '
             'Namen und Kurzzeichen werden Unicode-normalisiert; zusammenhängende Leerzeichen werden vereinheitlicht. '
             f'Groß-/Kleinschreibung beachten: {"ja" if config.matching.case_sensitive else "nein"}. '
             f'{esc(user_id_rule(config.matching.ignore_leading_user_id_zeros))}</p>'
             '<p>Best-Fit: zuerst maximale Paaranzahl, dann maximale Summe bewertbarer Feldähnlichkeiten; '
             'Vorname, Nachname, ID und Kurzzeichen zählen gleich. Konservativ: eindeutige exakte ID hat Vorrang, '
             'sonst gewichtetes Mittel aus Vorname × 1, Nachname × 1 und Kurzzeichen × 0,5 '
             'über die vorhandenen Vergleichsfelder, mindestens zwei beobachtete Felder.</p>'
             f'<p>Mindestähnlichkeit: {number(config.matching.minimum_similarity)}; '
             f'mindestens ein Namensfeld: {number(config.matching.minimum_name_similarity)}; '
             f'globale Mehrdeutigkeitsgrenze: {number(config.matching.ambiguity_margin)}. '
             'Im Best-Fit-Modus markieren diese Grenzen Prüffälle; im konservativen Modus können sie Paarungen sperren. '
             'Maskierte IDs werden nicht zum Namensersatz. Fehlende oder nicht bewertbare Felder erhalten keine Ähnlichkeitspunkte.</p></details>')
    content = ('<p><a href="report.html">Zur Übersicht</a> · <a href="details.html">Zur vollständigen Berechnung</a></p>'
               '<h1>Namenszuordnung: erkannter Name → Referenzname</h1>'
               '<p><strong>Klassenfilter vor dem Namensvergleich:</strong> Die Klassen-ID aus dem PDF-Dateinamen '
               'muss mit der Class ID des Excel-/CSV-Eintrags übereinstimmen. Namen und IDs aus anderen Klassen '
               'sind keine Kandidaten, auch bei vollständiger Übereinstimmung. Ohne passende Referenzklasse '
               'bleibt die PDF unbewertet; es gibt keine Suche in anderen Kursen.</p>'
               '<p>Jede Zeile zeigt eine tatsächlich gespeicherte Paarung oder einen nicht zugeordneten Namen. '
               'Ausgaben folgen PDF, Seite und ursprünglichem Eintragsindex; reine Referenzfälle stehen am Ende. '
               'Es werden keine neuen Paarungen berechnet. Modellnamen und Feldrollen bleiben unverändert. '
               'Die Alternative einer Ausgabe kann wegen der globalen Einmalvergabe schon einer anderen Person gehören.</p>'
               f'<p>Modus: <strong>{esc(config.matching.mode)}</strong>. Best-Fit-Paare sind Bewertungszuordnungen '
               'und keine bestätigten Identitäten. Schwache oder mehrdeutige Entscheidungen bleiben prüfpflichtig. '
               'Die Namensspalten zeigen gespeicherte Extraktionswerte vor der Bewertungsnormalisierung, soweit der geprüfte Quelllauf verfügbar ist; '
               'andernfalls die gespeicherten bewerteten Werte. Rohtexte ohne Teilnehmerfelder haben keine Namenspaarungen.</p>' + rules + controls +
               '<div class="scroll"><table><thead><tr><th>Verfahren und Quelle</th><th>Erkannter Name</th>'
               '<th>Zuordnung</th><th>Name in Excel/CSV</th><th>Wie wurde entschieden?</th><th>Prüfen?</th></tr></thead>'
               '<tbody>' + "".join(result) + '</tbody></table></div>'
               '<p>Die Referenzzeile ist die ursprüngliche Excel-/CSV-Zeile. Der Ausgabeindex beginnt bei 0. '
               'Zuordnungs- und Ähnlichkeitswerte sind keine kalibrierten Wahrscheinlichkeiten.</p>')
    path = output / "zuordnungen.html"
    path.write_text(document("Namenszuordnung", content, script_source=FILTER_SCRIPT), encoding="utf-8")
    for filename in ("report.html", "details.html"):
        main = output / filename
        if main.is_file():
            text = main.read_text(encoding="utf-8")
            if 'href="zuordnungen.html"' not in text:
                main.write_text(text.replace("</h1>", '</h1><p><a href="zuordnungen.html"><strong>Namenszuordnung: '
                                'wer wurde wem zugeordnet?</strong></a></p>', 1), encoding="utf-8")
    return path
