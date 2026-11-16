"""Filterable primary grading ledger embedded in the existing dashboard."""

import json
from urllib.parse import urlencode

from .detail_report import esc, table
from .field_assessment import LABELS as FIELD_LABELS
from .field_assessment import percent as similarity_percent
from .matching import FIELDS
from .metric_audit import CATEGORIES

SCRIPT = """(() => {
for(const kind of ['fields','participants']){
 const root=document.getElementById('audit-'+kind);if(!root)continue;
 const controls=[...root.querySelectorAll('[data-filter]')],search=root.querySelector('[type=search]');
 const apply=()=>{let n=0;for(const row of root.querySelectorAll('tbody tr')){
  const show=controls.every(c=>!c.value||row.dataset[c.dataset.filter]===c.value)&&
   row.textContent.toLocaleLowerCase().includes(search.value.toLocaleLowerCase());
  row.hidden=!show;if(show)n++;
 }root.querySelector('[data-visible]').textContent=String(n);};
 for(const control of [...controls,search])control.addEventListener('input',apply);
 root.querySelector('[data-reset]').addEventListener('click',()=>{for(const c of [...controls,search])c.value='';apply();});
 apply();
}
})();"""

PARTICIPANTS = {"complete": "Alle Pflichtfelder korrekt", "identity_only": "Identität exakt, Pflichtfelder fehlerhaft",
                "identity_error": "Identitätskriterium nicht erfüllt", "missing": "Referenzperson ungepaart",
                "unclear": "Zuordnung unklar; Identifikation nicht bestätigt",
                "extra": "Zusätzliche Ausgabeperson"}


def value(text):
    return '<code>' + esc(json.dumps(text, ensure_ascii=False)) + '</code>'


def links(row):
    query = dict(method=row["candidate"], **{"class": row["class_id"]})
    if row.get("page_number"):
        query["page"] = row["document_id"] + ":" + str(row["page_number"])
    if row.get("field"):
        query["field"] = row["field"]
    return " · ".join(f'<a href="{esc(r["href"])}">{esc(r["label"])}</a>' for r in row["original_links"]) + (
        f'<br><a href="extraction_errors.html?{esc(urlencode(query))}">Gespeicherte Pipelinebelege</a>')


def ledger(kind, rows, columns, filters):
    content = f'<section id="audit-{kind}"><div class="filters">'
    for key, label, choices in filters:
        content += f'<label>{esc(label)}<select data-filter="{key}"><option value="">Alle</option>'
        content += ''.join(f'<option value="{esc(k)}">{esc(v)}</option>' for k, v in choices)
        content += '</select></label>'
    content += '<label>Suche (auch Teilnehmer / Werte)<input type="search"></label><button type="button" data-reset>Zurücksetzen</button></div>'
    content += '<p><span data-visible></span> Einzelbewertungen sichtbar.</p><div class="scroll"><table><thead><tr>'
    content += ''.join(f'<th>{esc(label)}</th>' for label, _ in columns) + '</tr></thead><tbody>'
    for row in rows:
        attrs = dict(method=row['candidate'], document=row['document_label'], page=str(row.get('page_number') or 'unknown'),
                     field=row.get('field', ''), category=row.get('category', row.get('participant_result', '')),
                     assessment=row.get('evaluation_status', ''))
        content += '<tr ' + ' '.join(f'data-{k}="{esc(v)}"' for k, v in attrs.items()) + '>'
        content += ''.join('<td>' + fn(row) + '</td>' for _, fn in columns) + '</tr>'
    return content + '</tbody></table></div></section>'


def render(payload):
    data = payload.get('metric_audit')
    if not data:
        return ''
    text = '<p>Einzelbewertungen derselben Originalrollenansicht wie A/B. Anführungszeichen machen Leerzeichen und leere Zeichenfolgen sichtbar; null bedeutet unbekannt. Die Rohwerte werden nicht verändert.</p>'
    text += table(['Verfahren', 'Erwartet R', 'Vorhanden bei Referenz', 'Ausgegeben P inkl. Extras', 'Exakt E', 'Falsch', 'Fehlend', 'Zusätzlich',
                   'Ausgabedatensätze', 'Gepaart', 'Identität exakt', 'Alle Pflichtfelder korrekt'],
                  [[r[k] for k in ('candidate', 'reference_fields', 'available_reference_fields', 'predicted_fields', 'exact_fields',
                                  'incorrect_fields', 'missing_fields', 'extra_fields', 'predicted_participants', 'assigned_participants',
                                  'identity_exact_participants', 'fully_correct_complete_participants')] for r in data['summaries']])
    text += '<p class="note">R = exakt + falsch + fehlend. Ein falscher Wert zählt als FP und FN; dies ist die Definition von Precision/Recall. Teilnehmerfehler und technische Seitenfehler werden nicht zusätzlich auf Feldfehler addiert. Zusatzwerte ohne Referenzpaar sind keine bewiesenen Halluzinationen. Feld-/Zeilenverwechslungen werden als eigene Hinweise ausgewiesen, ohne Werte umzupaaren oder Punkte zu korrigieren.</p>'
    text += table(['Verfahren', *FIELD_LABELS.values()], [
        [r['candidate'], *r['evaluation_status_counts'].values()] for r in data['summaries']])
    text += '<p>Die Anzeigestatus zählen jeden Feldfall genau einmal, auch ungepaarte Ausgaben und unbekannte Referenzen. Sie sind keine zusätzliche R/P/E-Fehlersumme. Vorhandene abweichende Werte zählen zur Abdeckung. Unklare Zuordnung bestätigt keine Identität; eine niedrige Textähnlichkeit allein macht einen zugeordneten Wert nicht fehlend. Die Prozentzahl ist Textähnlichkeit, keine Konfidenz oder Richtigkeitswahrscheinlichkeit.</p>'
    text += '<details><summary>Normalisierung, Nenner und Matching kritisch einordnen</summary>'
    text += table(['Gespeicherte Bewertungsoption', 'Wert'], list(payload.get('normalization_config', {}).items()))
    text += '<p>NFC-Unicode, äußere und mehrfache innere Leerzeichen sowie Groß-/Kleinschreibung bei Texten gemäß gespeicherter Konfiguration. IDs werden außen getrimmt; innere Leerzeichen und Buchstabenfall bleiben bestehen. Führende ID-Nullen gemäß Konfiguration. Umlaute, ß/ss, Bindestriche, Akzente und Schreibfehler bleiben verschieden. Roh-Exaktheit ist separat exportiert; Levenshtein vergibt nur im getrennten Soft-Score Teilpunkte.</p>'
    text += '<p>Alle Ausgaben einer Schulung konkurrieren global 1:1, über PDFs und Seiten hinweg. Best-Fit maximiert zuerst die Anzahl lesbarer Paare, dann Feldähnlichkeit. Schwache oder mehrdeutige Paare bleiben prüfpflichtig. Auch Organisation geht ins Matching ein; das ist eine referenzgestützte Übereinstimmungsbewertung und keine unabhängige Identitätsprüfung. Originalrollen bewertet dieselben Paare ohne Namenstausch; Matching-Sensitivitäten in A rechnen die Paarung getrennt neu.</p>'
    text += '<p>Eine Kursreferenz lokalisiert ungepaarte Personen nicht auf Seiten. Bei „Seite unbekannt“ verlinken die PDFs nur mögliche Kursdokumente. Ob alle Kursmitglieder tatsächlich im PDF stehen und ob dort leere Zellen statt lesbarer Stammdaten vorliegen, verlangt eine unabhängige Bildannotation. Ein gleicher Nenner beweist diese inhaltliche Referenzgültigkeit nicht.</p></details>'
    text += '<details><summary>Seitenbefunde: leere Baseline, ungültige Antworten und Cache-Nutzung</summary>'
    text += table(['Verfahren', 'Dokument', 'Seite', 'Datensätze', 'Status / JSON', 'OCR-Beobachtungen', 'Ausgabetokens',
                   'Seitenzeit (s)', 'Cache-Komponenten / Zuordnung', 'Gespeicherte Prüfhinweise / Fehler'],
                  [[r['candidate'], r['document_label'], r['page_number'], r['participants'], r['status'] + ' / ' + r['parse_status'],
                    r['ocr_observations'], r['output_tokens'], r['page_wall_seconds'],
                    str(r['cached_components']) + ' / ' + str(r['assignment_cache']),
                    '\n'.join(r['review_notes']) + '\n' + (r['error'] or '')] for r in data['pages']])
    text += '<p>„Datenbasis vollständig“ bezeichnet vorhandene, gültige Seitenergebnisse, auch bei null Teilnehmern. OCR-Rohtext ist keine strukturierte Feldausgabe. Cache-Zeiten, reale Seitenzeit und zugerechnete frühere Erkennungszeit sind verschiedene Größen. Details zu Laufzeit, Ladezeit und Aufrufen stehen in E. Kopflosen Seiten darf nur belegte Spaltenstruktur derselben PDF vorausgehen; die gespeicherten Entscheidungen sind über „Pipelinebelege“ einsehbar. Hier werden keine Überschriften oder Teilnehmerwerte nachträglich repariert.</p></details>'
    choices = [(m, m) for m in sorted({r['candidate'] for r in data['fields']})]
    documents = [(d, d) for d in sorted({r['document_label'] for r in data['fields']})]
    pages = [('unknown', 'Seite unbekannt')] + [(str(p), str(p)) for p in sorted({r['page_number'] for r in data['fields'] if r.get('page_number')})]
    common = [('method', 'Verfahren', choices), ('document', 'Dokument(e)', documents), ('page', 'PDF-Seite', pages)]
    text += '<h3>Teilnehmer: Zuordnung, Identität und Vollständigkeit</h3>'
    text += ledger('participants', data['participants'], [
        ('Verfahren', lambda r: esc(r['candidate'])), ('Dokument / Seite', lambda r: esc(r['document_label']) + '<br>' + esc(r.get('page_number') or 'Seite unbekannt')),
        ('Teilnehmer / Referenz / Ausgabe', lambda r: esc(r['participant_label']) + f'<br>GT {esc(r["reference_row"])} · Ausgabe {esc(r.get("output_index"))} (Index ab 0)'),
        ('Bewertung', lambda r: esc(PARTICIPANTS[r['participant_result']])),
        ('Referenzanker / Prüfhinweise', lambda r: esc(r.get('identity_basis')) + '<br>' + esc(r.get('matching_review_reasons'))),
        ('Begründung', lambda r: esc(r['reason'])), ('Original / Belege', links),
    ], common + [('category', 'Bewertung', list(PARTICIPANTS.items()))])
    text += '<h3>Felder: vollständiges Soll-/Ist-Protokoll</h3>'
    text += ledger('fields', data['fields'], [
        ('Verfahren', lambda r: esc(r['candidate'])), ('Dokument / Seite', lambda r: esc(r['document_label']) + '<br>' + esc(r.get('page_number') or 'Seite unbekannt')),
        ('Teilnehmer / Referenz / Ausgabe', lambda r: esc(r['participant_label']) + f'<br>GT {esc(r["reference_row"])} · Ausgabe {esc(r.get("output_index"))}'),
        ('Feld', lambda r: esc(r['field'])), ('Ground Truth', lambda r: value(r['reference_value'])),
        ('Extrahierter Originalwert', lambda r: value(r.get('original_prediction_value', r['prediction_value']))),
        ('Bewertungsstatus', lambda r: '<strong>' + esc(r['evaluation_label']) + '</strong><br>' + esc(r['evaluation_reason'])),
        ('Levenshtein-Ähnlichkeit', lambda r: esc(similarity_percent(r['similarity_percent']))),
        ('Fehlerkategorie / Grund', lambda r: '<strong>' + esc(CATEGORIES[r['category']]) + '</strong><br>' + esc(r['reason'])),
        ('Belegte Fehlerstufe', lambda r: esc(r['cause']['stage']) + ' · ' + esc(r['cause']['certainty']) + '<br>' + esc(r['cause']['reason'])),
        ('Beiträge R / P / E', lambda r: f'{r["reference_contribution"]} / {r["prediction_contribution"]} / {int(r["exact"] is True)}'),
        ('Original / Belege', links),
    ], common + [('field', 'Feld', [(f, f) for f in FIELDS]), ('category', 'Kategorie', list(CATEGORIES.items())),
                 ('assessment', 'Bewertungsstatus', list(FIELD_LABELS.items()))])
    text += '<p><a href="scientific/metric_audit.json">Gesamtes Prüfprotokoll JSON</a> · <a href="scientific/field_cases.csv">Feldfälle CSV</a> · <a href="scientific/participant_audit.csv">Teilnehmer CSV</a> · <a href="scientific/metric_audit_checks.json">Abgleich mit Metrikzählern</a></p>'
    return text
