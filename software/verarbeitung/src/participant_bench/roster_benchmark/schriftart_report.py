"""Reference-only participant strata on frozen pairs and existing additive counters."""

import math
from collections import defaultdict

from ..writing_style import STYLES, validate_schriftart
from .detail_report import esc, table
from .document_availability import field_id, project
from .field_assessment import counts as assessment_counts
from .matching import FIELDS
from .metrics import DETECTED_LABEL, PARTICIPANT_COUNTERS, divide, empty_counts, scores, sum_counts
from .report import detected_basis, detected_percent

SCRIPT = """(() => {
const root=document.getElementById('schriftart'),control=document.getElementById('schriftart-filter');
if(!root||!control)return;
const apply=()=>{for(const row of root.querySelectorAll('[data-schriftart]'))
 row.hidden=!!control.value&&row.dataset.schriftart!==control.value;};
control.addEventListener('change',apply);apply();
})();"""


def prepare(score, candidate, mode, documents):
    """Assemble display/export rows, and prove that no global extra field disappeared."""
    rows, fields = [], []
    for style, group in {"total": score, **score["schriftart_groups"]}.items():
        courses = group.get("class_ids")
        docs = {d["document_id"] for d in documents if d.get("status") == "mapped"
                and (courses is None or d["class_id"] in courses)}
        row = dict(candidate=candidate, mode=mode, schriftart=style, documents=len(docs),
                   document_count_basis="PDFs in courses with this GT category; not localized participant presence",
                   assigned_participants=group["assigned_participants"],
                   **group["overall"], **group["participant_quality"])
        rows.append(row)
        fields.extend(dict(candidate=candidate, mode=mode, schriftart=style, field=f, **c)
                      for f, c in group["fields"].items())
    unassigned = score["schriftart_unassigned"]
    for key in empty_counts():
        total = sum(g["overall"][key] for g in score["schriftart_groups"].values()) + unassigned["fields"][key]
        if not math.isclose(total, score["overall"][key], rel_tol=1e-12, abs_tol=1e-9):
            raise ValueError("Schriftart-Gruppenzähler stimmen nicht mit Gesamtbewertung überein")
    if any(sum(g["participant_quality"][k] for g in score["schriftart_groups"].values()) != score["participant_quality"][k]
           for k in PARTICIPANT_COUNTERS):
        raise ValueError("Schriftart-Teilnehmerzähler stimmen nicht mit Gesamtbewertung überein")
    return rows, fields, dict(candidate=candidate, mode=mode, participants=unassigned["participants"],
                             **unassigned["fields"], counts_reconcile=True)


def render(payload):
    names = {"total": "Gesamt", **STYLES}
    rows = [r for r in payload.get("schriftart", []) if r["mode"] == "original_roles"]
    fields = [r for r in payload.get("schriftart_fields", []) if r["mode"] == "original_roles"]
    text = '<p>Schriftart stammt ausschließlich aus der Teilnehmer-Ground-Truth. Die Gruppen verwenden dieselben vollständigen Matchingentscheidungen wie A; keine Neuzuordnung innerhalb einer Gruppe.</p>'
    text += '<label>Schriftartfilter für diese Auswertung <select id="schriftart-filter"><option value="">Gesamt</option>'
    text += ''.join(f'<option value="{key}">{label}</option>' for key, label in STYLES.items()) + '</select></label>'
    text += '<p class="note">g ist eine teilnehmerbezogene Mischkategorie: Jede Person gehört genau einer Gruppe, keine Aufteilung nach Feldern in h und m. Fehlende Annotation heißt „Nicht klassifiziert“, niemals automatisch Maschinenschrift. Gesamt enthält weiterhin alle Referenzen und Zusatzfehler.</p>'

    def ratio(n, d, value):
        return esc(detected_percent(value)) + f'<br><small>{n} / {d}</small>'

    columns = [
        ("Verfahren", lambda r: esc(r['candidate'])), ("Schriftart", lambda r: esc(names[r['schriftart']])),
        ("Dokumente im Kursumfang", lambda r: str(r['documents'])),
        ("GT-Teilnehmer / gepaart", lambda r: f'{r["reference_participants"]} / {r["assigned_participants"]}'),
        ("Erwartete / ausgegebene Felder", lambda r: f'{r["reference_fields"]} / {r["predicted_fields"]}'),
        ("Exact Recall", lambda r: ratio(r['exact_fields'], r['reference_fields'], r['exact_recall'])),
        ("Exact F1", lambda r: esc(detected_percent(r['exact_f1']))),
        ("Field Coverage", lambda r: ratio(r['reference_fields']-r['missing_fields'], r['reference_fields'], r['field_coverage'])),
        (DETECTED_LABEL, lambda r: esc(detected_percent(r['detected_similarity'])) + '<br><small>' + esc(detected_basis(r)) + '</small>'),
        ("Teilnehmer-Recall", lambda r: ratio(r['identity_exact_participants'], r['identity_assessable_participants'], r['participant_recall'])),
        ("Vollständig korrekte Teilnehmer", lambda r: ratio(r['fully_correct_complete_participants'], r['complete_reference_participants'], r['complete_participant_accuracy'])),
    ]

    def grouped_table(records, cols):
        body = '<div class="scroll"><table><thead><tr>' + ''.join(f'<th>{esc(label)}</th>' for label, _ in cols) + '</tr></thead><tbody>'
        for row in records:
            body += f'<tr data-schriftart="{row["schriftart"]}">' + ''.join('<td>' + fn(row) + '</td>' for _, fn in cols) + '</tr>'
        return body + '</tbody></table></div>'

    text += grouped_table(rows, columns)
    text += '<p>Dokumentzahl: PDFs im Kursumfang der jeweiligen GT-Gruppe, unabhängig vom Erkennungserfolg. Eine Kursreferenz lokalisiert Personen nicht auf einzelne PDFs/Seiten. Ein PDF kann mehrere Schriftartgruppen enthalten; Dokumentzahlen sind nicht additiv. Ohne GT-Nenner bleibt eine Kennzahl „nicht definiert“.</p>'
    text += '<h3>Feldtypen innerhalb der Schriftartgruppen</h3>'
    text += grouped_table(fields, [
        ("Verfahren", lambda r: esc(r['candidate'])), ("Schriftart", lambda r: esc(names[r['schriftart']])),
        ("Feld", lambda r: esc(r['field'])), ("Erwartet / ausgegeben", lambda r: f'{r["reference_fields"]} / {r["predicted_fields"]}'),
        ("Exact Recall", lambda r: esc(detected_percent(r['exact_recall']))),
        ("Exact F1", lambda r: esc(detected_percent(r['exact_f1']))),
        ("Field Coverage", lambda r: esc(detected_percent(r['field_coverage']))),
        (DETECTED_LABEL, lambda r: esc(detected_percent(r['detected_similarity'])) + '<br>' + esc(detected_basis(r))),
    ])
    text += '<h3>Zusätze ohne Referenzzuordnung: nur global zu bewerten</h3>'
    text += table(['Verfahren', 'Zusatzpersonen ohne Schriftartzuordnung', 'Ausgabefelder P'],
                  [[r['candidate'], r['participants'], r['predicted_fields']]
                   for r in payload.get('schriftart_unassigned', []) if r['mode'] == 'original_roles'])
    text += '<p>Gruppen-F1 und Precision beziehen sich auf die jeweilige GT-Teilmenge. Ungepaarte Modellausgaben werden keiner Schriftart zugeteilt und bleiben vollständig in globalem P/FP und globalem F1 erhalten. Es gilt global P = Summe Gruppen-P + ungepaarte P. Zusätze in einer zugeordneten, ausdrücklich leeren GT-Zelle bleiben dagegen in ihrer GT-Gruppe. Gruppen-F1 ist deshalb keine eigenständige End-to-End-Metrik und wird nicht zum globalen F1 gemittelt.</p>'
    text += '<p><a href="scientific/schriftart.csv">Gruppenmetriken CSV</a> · <a href="scientific/schriftart_fields.csv">Feldgruppen CSV</a> · <a href="scientific/schriftart_unassigned.csv">Unzuordenbare Zusätze und Summenprüfung CSV</a></p>'
    return text


def analyse_fields(audit, availability, ctx, locations=None):
    """Project existing field decisions; GT style is participant-level, never model-inferred."""
    locations = locations or {}
    methods = sorted({r["candidate"] for r in audit["fields"]})
    signatures, by_method, extras = {}, defaultdict(list), defaultdict(list)
    documents = {"all": dict(label="Alle Dokumente / Kurse", basis="scope")}
    for doc, record in ctx["documents"].items():
        documents[doc] = dict(label=record["name"], basis="reference_scope", document_ids=[doc])
    for row in audit["fields"]:
        if row["field"] not in FIELDS:
            raise ValueError("Schriftartanalyse bewertet ausschließlich die vier bestehenden Textfelder")
        method = row["candidate"]
        if row.get("reference_row") is None:
            extras[method].append(row)
            continue
        style = validate_schriftart(row.get("schriftart")) or "unclassified"
        key = (row["class_id"], row["reference_row"], row["field"])
        signature = (row.get("reference_state"), row.get("reference_value"), style)
        previous = signatures.setdefault(key, signature)
        if previous != signature:
            raise ValueError("Schriftartanalyse benötigt identische Referenzwerte und Teilnehmerlabels aller Verfahren")
        ids = ctx["courses"].get(row["class_id"], [])
        site = locations.get((row["class_id"], row["reference_row"]))
        if len(ids) == 1:
            document, basis = ids[0], "single_pdf_course_scope"
        elif site and site[0] in ids:
            document, basis = site[0], "independent_reference_location"
        else:
            document, basis = "course:" + row["class_id"], "course_only_unlocalized"
            documents[document] = dict(label="Kurs " + row["class_id"] + " · PDF-Zuordnung ungeprüft",
                                       basis=basis, document_ids=ids)
        by_method[method].append(dict(row, gt_style=style, reference_document_group=document,
                                      document_group_basis=basis))
    sets = [{(r["class_id"], r["reference_row"], r["field"]) for r in by_method[m]} for m in methods]
    if sets and any(s != sets[0] for s in sets):
        raise ValueError("Schriftartanalyse darf keine unterschiedliche Referenzschnittmenge bilden")
    # A participant cannot acquire different labels from the field currently being inspected.
    participant_styles = defaultdict(set)
    for key, (_, _, style) in signatures.items():
        participant_styles[key[:2]].add(style)
    if any(len(styles) > 1 for styles in participant_styles.values()):
        raise ValueError("Widersprüchliche Schriftartfelder innerhalb einer Teilnehmerreferenz")

    reviews = availability["reviews"]
    views = {basis: {} for basis in ("reference", "document")}
    checks = {}
    for method in methods:
        original = [r for r in audit["fields"] if r["candidate"] == method]
        pooled = sum_counts(r["field_counts"] for r in by_method[method] + extras[method])
        if any(not math.isclose(pooled[k], sum(r["field_counts"].get(k, 0) for r in original), abs_tol=1e-9)
               for k in empty_counts()):
            raise ValueError("Schriftartprojektion verliert globale Feldbeiträge")
        checks[method] = dict(global_counts_reconcile=True, global_metrics=scores(pooled))

    for doc in documents:
        for field in ("all", *FIELDS):
            selected = {
                m: [r for r in by_method[m] if (doc == "all" or r["reference_document_group"] == doc)
                    and (field == "all" or r["field"] == field)] for m in methods}
            projections = {(m, style): project([r for r in rs if r["gt_style"] == style], reviews)
                           for m, rs in selected.items() for style in STYLES}
            for basis, metric_key in (("reference", "baseline"), ("document", "readable_reference_subset")):
                canonical_scope = selected[methods[0]] if methods else []
                if basis == "document":
                    canonical_scope = [r for r in canonical_scope if r["reference_contribution"] == 1
                                       and reviews[field_id(r)]["eligible"]]
                expected = sum(r["reference_contribution"] for r in canonical_scope)
                distribution = []
                for style in STYLES:
                    group = [r for r in canonical_scope if r["gt_style"] == style]
                    expected_group = sum(r["reference_contribution"] for r in group)
                    fields = {f: sum(r["reference_contribution"] for r in group if r["field"] == f) for f in FIELDS}
                    distribution.append(dict(schriftart=style, reference_fields=expected_group,
                                             reference_share=divide(expected_group, expected),
                                             reference_share_denominator=expected, field_counts=fields,
                                             participants=len({(r["class_id"], r["reference_row"]) for r in group})))
                    p = projections[methods[0], style] if methods else {}
                    distribution[-1].update(availability_counts=p.get("availability_counts", {}),
                                            reviewed_fields=p.get("reviewed_fields", 0),
                                            eligible_fields=p.get("eligible_fields", 0),
                                            reference_conflicts=p.get("readable_reference_conflicts", 0))
                comparisons = []
                for m in methods:
                    counts = {s: projections[m, s][metric_key] for s in STYLES}
                    missing = sum(r["missing_fields"] for r in counts.values())
                    wrong = sum(r["incorrect_fields"] for r in counts.values())
                    for style, count in counts.items():
                        rs = [r for r in selected[m] if r["gt_style"] == style]
                        if basis == "document":
                            rs = [r for r in rs if r["reference_contribution"] == 1 and reviews[field_id(r)]["eligible"]]
                        p = projections[m, style]
                        raw_missing = sum(r["field_counts"].get("missing_fields", 0) for r in rs
                                          if not str(r.get("original_prediction_value") or "").strip())
                        comparisons.append(dict(candidate=m, schriftart=style, **count,
                            fully_missing_final_values=raw_missing,
                            present_but_unusable_values=count["missing_fields"] - raw_missing,
                            error_fields=count["missing_fields"] + count["incorrect_fields"],
                            error_rate=divide(count["missing_fields"] + count["incorrect_fields"], count["reference_fields"]),
                            missing_error_share=divide(count["missing_fields"], missing),
                            incorrect_error_share=divide(count["incorrect_fields"], wrong),
                            combined_error_share=divide(count["missing_fields"] + count["incorrect_fields"], missing + wrong),
                            missing_error_denominator=missing, incorrect_error_denominator=wrong,
                            combined_error_denominator=missing + wrong,
                            evaluation_status_counts=assessment_counts(rs),
                            availability_counts=p["availability_counts"], eligible_fields=p["eligible_fields"],
                            reference_conflicts=p["readable_reference_conflicts"], reviewed_fields=p["reviewed_fields"]))
                    if sum(r["reference_fields"] for r in counts.values()) != expected:
                        raise ValueError("Schriftartnenner unterscheiden sich zwischen Verfahren")
                views[basis].setdefault(doc, {})[field] = dict(
                    reference_fields=expected, distribution=distribution, comparisons=comparisons)

    details = []
    for m in methods:
        for r in by_method[m]:
            review = reviews.get(field_id(r), {})
            details.append(dict(r, document_eligible=bool(review.get("eligible")),
                                document_availability=review.get("availability", "unassessed")))
    return dict(version="schriftart-analysis-v1", annotation_level="participant",
                methods=methods, missing_requested_methods=sorted(set(("ocr_llm", "paddle_llm", "docling", "vlm", "ocr_vlm")) - set(methods)),
                styles=STYLES, documents=documents, views=views, details=details, checks=checks,
                unassigned=[dict(candidate=m, fields=scores(sum_counts(r["field_counts"] for r in extras[m]))) for m in methods],
                baseline_unchanged=True, matching_unchanged=True)
