"""Offline HTML/CSV overview. Personal values remain in local audit exports, never console logs."""

import html
import os
from pathlib import Path

from ..excel_columns import field_labels
from ..identifiers import user_id_rule
from ..io import write_csv
from .config import MatchingConfig
from .matching import FIELDS


def percent(value):
    return "—" if value is None else f"{100 * value:.2f} %"


def render(output, metrics, scope, courses, source, *, columns=None, matching=None):
    summary, field_rows, model_html, field_html = [], [], [], []
    labels = field_labels(columns)
    matching = matching or MatchingConfig()
    def escape(value):
        return html.escape(str(value))
    for method, score in metrics.items():
        overall = score.get("overall", {})
        row = dict(method=method, status=score["status"], extraction_status=score["extraction_status"],
                   score_percent=score.get("score_percent"),
                   matching_mode=score.get("matching_mode", "conservative"),
                   conservative_score_percent=score.get("conservative_score_percent"),
                   assigned_participants=score.get("assigned_participants"),
                   low_similarity_assignments=score.get("low_similarity_assignments", 0),
                   excluded_instructors=score.get("excluded_instructors"),
                   ambiguous_assignments=score.get("ambiguous_assignments", 0),
                   exact_field_f1_percent=100 * overall["exact_f1"] if overall.get("exact_f1") is not None else None,
                   exact_reference_percent=100 * overall["exact_reference_accuracy"]
                       if overall.get("exact_reference_accuracy") is not None else None,
                   raw_exact_reference_percent=100 * overall["raw_exact_reference_accuracy"]
                       if overall.get("raw_exact_reference_accuracy") is not None else None,
                   exact_fields=overall.get("exact_fields"), reference_fields=overall.get("reference_fields"),
                   predicted_fields=overall.get("predicted_fields"),
                   missing_participants=score.get("missing_participants"), extra_participants=score.get("extra_participants"),
                   ambiguous_participants=score.get("ambiguous_participants"), identity_conflicts=score.get("identity_conflicts"),
                   duplicate_predictions=score.get("duplicate_predictions"),
                   review_rows=score.get("review_rows"),
                   excluded_masked_ids=overall.get("excluded_masked_predictions"),
                   fully_exact_participants=score.get("fully_exact_participants"),
                   reference_participants=score.get("reference_participants"), runtime_seconds=score.get("runtime_seconds"))
        summary.append(row)
        value = score.get("score_percent")
        display = "nicht anwendbar" if value is None else f"{value:.2f} %"
        bar = f'<span class="bar" style="width:{value:.3f}%"></span>' if value is not None else ""
        model_html.append(f"<tr><td>{escape(method)}</td><td><strong>{display}</strong><div class='track'>{bar}</div></td>"
                          f"<td>{'—' if score.get('conservative_score_percent') is None else format(score['conservative_score_percent'], '.2f') + ' %'}</td>"
                          f"<td>{score.get('assigned_participants', '—')}</td>"
                          f"<td>{score.get('excluded_instructors', '—')}</td>"
                          f"<td>{percent(overall.get('exact_f1'))}</td>"
                          f"<td>{overall.get('exact_fields', '—')} / {overall.get('reference_fields', '—')}</td>"
                          f"<td>{score.get('missing_participants', '—')}</td><td>{score.get('extra_participants', '—')}</td>"
                          f"<td>{score.get('review_rows', '—')}</td>"
                          f"<td>{escape(score['extraction_status'])}</td></tr>")
        for name in FIELDS:
            if name not in score.get("fields", {}):
                continue
            values = score["fields"][name]
            field_rows.append(dict(method=method, field=name, field_label=labels[name], **values))
            field_html.append(f"<tr><td>{escape(method)}</td><td>{escape(labels[name])}</td>"
                              f"<td>{percent(values['soft_f1'])}</td><td>{percent(values['exact_reference_accuracy'])}</td>"
                              f"<td>{percent(values['raw_exact_reference_accuracy'])}</td>"
                              f"<td>{values['exact_fields']} / {values['reference_fields']}</td>"
                              f"<td>{values['excluded_reference_fields'] + values['excluded_masked_predictions']}</td></tr>")
    write_csv(output / "summary.csv", summary)
    write_csv(output / "field_scores.csv", field_rows,
              fields=None if field_rows else ["method", "field", "soft_f1", "exact_reference_accuracy"])
    course_html = "".join(f"<tr><td>{escape(row['method'])}</td><td>{escape(row['class_id'])}</td>"
                          f"<td>{percent(row['soft_f1'])}</td><td>{percent(row['exact_reference_accuracy'])}</td>"
                          f"<td>{row['reference_participants']}</td><td>{row['predicted_participants']}</td>"
                          f"<td>{row['missing_participants']}</td><td>{row['extra_participants']}</td></tr>"
                          for row in courses[:200])
    source_report = Path(source) / "report.html"
    try:
        relative = os.path.relpath(source_report, output).replace(os.sep, "/")
        source_link = f'<a href="{html.escape(relative, quote=True)}">Extraktionsbericht mit PDF-Seiten und Rohtext</a>' if source_report.is_file() else ""
    except ValueError:  # Windows paths on different drives cannot be made relative.
        source_link = "Quellreport: " + escape(source_report)
    synthetic_notice = ("<div class='box'><strong>Synthetische Demonstration mit künstlichen Vorhersagen. "
                        "Dieser Bericht belegt keine Modellleistung.</strong></div>"
                        if any(score["extraction_status"] == "synthetic_fixture" for score in metrics.values()) else "")
    reference_notice = ("<div class='box'><strong>Die Referenzdatei wurde nach dem Einlesen verändert oder entfernt. "
                        "Bewertet wurde die eingefrorene Referenz in reference_snapshot.json.</strong></div>"
                        if scope.get("reference_changed_after_snapshot") else "")
    best_fit = any(score.get("matching_mode") == "best_fit" for score in metrics.values())
    alignment_notice = (
        "<div class='box'><strong>Zuordnungsmodus: globales Best-Fit.</strong> Innerhalb jeder Schulung werden zuerst "
        "möglichst viele lesbare Ausgaben mit verschiedenen Referenzzeilen gepaart. Danach wird die Summe der "
        "Levenshtein-Ähnlichkeiten über alle bewertbaren Felder maximiert, einschließlich lesbarer User IDs. "
        "Schwache und nahezu gleichwertige Paarungen bleiben für die Bewertung erhalten und werden zur Prüfung markiert. "
        "Diese Paarungen bestätigen keine Identitäten. Höhere Scores gegenüber dem konservativen Modus können allein "
        "durch die Zuordnungsregel entstehen; die Modellausgaben werden nicht korrigiert. Die konservative Vergleichszahl "
        "steht separat in der Tabelle.</div>" if best_fit else
        "<div class='box'><strong>Zuordnungsmodus: konservativ.</strong> Eindeutige exakte IDs haben Vorrang; "
        "sonst gelten die konfigurierten Mindestähnlichkeiten. Mehrdeutige oder widersprüchliche Paarungen "
        "erhalten keine Zuordnungspunkte.</div>")
    page = f"""<!doctype html><html lang="de"><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'self'">
<title>Teilnehmerlisten – Referenzvergleich</title><style>
body{{font:16px system-ui,sans-serif;max-width:1400px;margin:32px auto;padding:0 20px;color:#172b3a;background:#f6f8fb}}
h1,h2{{color:#12384d}} table{{border-collapse:collapse;width:100%;background:white;margin:16px 0 30px}}
th,td{{text-align:left;padding:10px;border-bottom:1px solid #dce4eb;vertical-align:top}}th{{background:#e7eff5}}
.box{{padding:16px;background:white;border-left:4px solid #237a9a;margin:16px 0}}a{{color:#126181}}
.track{{height:6px;background:#e1e9f0;margin-top:6px;width:160px}}.bar{{height:6px;background:#227d9e;display:block}}
code{{background:#e7eff5;padding:2px 4px}}.scroll{{overflow-x:auto}}
</style><h1>Teilnehmerlisten: Modellvergleich mit Referenz</h1>{synthetic_notice}{reference_notice}{alignment_notice}
{('<p><a href="hybrid_analysis.html">Hybridanalyse: Welche VLM-Felder wurden durch OCR besser oder schlechter?</a></p>' if (output / 'hybrid_analysis.html').is_file() else '')}
<p>{scope['input_pdfs']} PDF-Dateien · {scope['courses_compared']} Schulungen mit Referenz ·
{scope['reference_rows_in_scope']} Referenzteilnehmer im Vergleich</p>
<div class="box"><strong>Hauptzahl: Levenshtein-Feld-F1.</strong> Fast richtige Wörter erhalten Teilpunkte.
Fehlende Werte geben null Punkte; zusätzliche Werte vergrößern den Nenner.
<code>Score = 100 × 2 × Ähnlichkeitssumme / (Referenzfelder + vorhergesagte Felder)</code>.
Daneben steht derselbe F1 mit ausschließlich exakten Treffern. Beide berücksichtigen fehlende und zusätzliche Werte.
Die Zähler zeigen zusätzlich, wie viele Referenzfelder exakt erkannt wurden. Keine Kennzahl ist eine Wahrscheinlichkeit.</div>
<div class="scroll"><table><tr><th>Verfahren</th><th>Levenshtein-Feld-F1</th><th>Konservativer Vergleich</th><th>Paarungen</th><th>Ausgeschlossene Kursleiter</th><th>Exakter Feld-F1</th>
<th>Exakt / bewertbar</th><th>Fehlende Personen</th><th>Zusätzliche Personen</th><th>Prüfzeilen</th><th>Extraktion</th></tr>
{''.join(model_html)}</table></div>
<p>Die Zuordnung erfolgt unabhängig von der Zeilenreihenfolge innerhalb derselben Schulungs-ID.
Jede Vorhersage und jede Referenzperson können höchstens einmal Punkte erhalten. Nahezu gleichwertige
Zuordnungen und widersprüchliche Angaben erfordern manuelle Prüfung; der Umgang damit hängt vom ausgewiesenen Modus ab.
Die Zuordnung verwendet Referenzwerte; die Ergebnisse messen Referenzübereinstimmung, keine unabhängige Identitätsprüfung.</p>
<h2>Felder getrennt</h2><div class="scroll"><table><tr><th>Verfahren</th><th>Feld</th><th>Levenshtein-F1</th>
<th>Exakt normalisiert</th><th>Exakt Originalschreibweise</th><th>Exakt / bewertbar</th><th>Ausgeschlossen</th></tr>{''.join(field_html)}</table></div>
<p>NFC und vereinheitlichte Leerzeichen; Namen/Kurzzeichen laut Konfiguration ohne Beachtung der Groß-/Kleinschreibung.
{escape(user_id_rule(matching.ignore_leading_user_id_zeros))} Leere/maskierte Referenz-IDs werden ausgeschlossen.
Explizit maskierte Modell-IDs sind ebenfalls ausgeschlossen und müssen am PDF bestätigt werden;
fehlende oder unbekannte Modell-IDs bei lesbarer Referenz zählen dagegen als Fehler.
Unsichere, aber ausgegebene Feldwerte werden gemäß Konfiguration inhaltlich verglichen und bleiben prüfpflichtig.</p>
<h2>Schulungen</h2><p>Anzeige maximal 200 Zeilen; vollständige Daten unter <a href="courses.csv">courses.csv</a>.</p>
<div class="scroll"><table><tr><th>Verfahren</th><th>{escape(labels['class_id'])}</th><th>Levenshtein-F1</th><th>Exakt</th>
<th>Referenzpersonen</th><th>Vorhersagen</th><th>Fehlend</th><th>Zusätzlich</th></tr>{course_html}</table></div>
<h2>Umfang und Prüfpunkte</h2><ul>
<li>{scope['reference_rows_outside_input']} Referenzzeilen gehören zu Schulungen ohne Eingabe-PDF und sind nicht im Nenner.</li>
<li>{len(scope['courses_without_reference'])} Schulungen ohne Referenz und {scope['ambiguous_documents']} Dokumente mit widersprüchlicher Kurszuordnung.</li>
<li>{scope['merged_identical_reference_rows']} identische Referenzkopien explizit zusammengeführt.</li>
<li><code>ocr_raw</code> ist Rohtext und bekommt gegen eine Teilnehmer-CSV keinen Feldscore. CER/WER benötigen separate Seitentranskripte.</li>
<li>Eine Buchungs-/Abschlussliste belegt keine Anwesenheit. Referenzen müssen die tatsächlich gemeinten PDF-Teilnehmer abbilden. Unterschriften werden hier nicht bewertet.</li></ul>
<h2>Nachvollziehen</h2><p>{source_link}</p><ul>
<li><a href="zuordnungen.html"><strong>Namenszuordnung: erkannter Name → Referenzname mit Entscheidungsgrund</strong></a></li>
<li><a href="details.html"><strong>Detailvergleich: Teilnehmer, Soll-/Ist-Werte, alle Kandidaten und vollständige Berechnung</strong></a></li>
<li><a href="participants.xlsx">Teilnehmer und Referenz als Excel-Datei mit den Original-Spaltennamen</a></li>
<li><a href="summary.csv">Modellübersicht</a> · <a href="field_scores.csv">Feldmetriken</a> · <a href="metrics.json">Metriken und Definitionen</a></li>
<li><a href="participants.csv">Teilnehmerzuordnung, fehlende und zusätzliche Einträge</a></li>
<li><a href="fields.csv">Einzelwerte, Zustände, Edit-Distanzen und Teilpunkte</a></li>
<li><a href="matching_candidates.csv">Geprüfte Zuordnungskandidaten</a> · <a href="documents.csv">PDF-/Schulungszuordnung</a> · <a href="unassessed_pages.csv">Nicht bewertete Seiten</a></li>
<li><a href="identity.json">Dateiprüfsummen und Version</a> · <a href="config.json">Konfiguration</a></li></ul>
</html>"""
    (output / "report.html").write_text(page, encoding="utf-8")
