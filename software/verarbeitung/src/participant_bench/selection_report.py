"""Small static addition to existing local HTML reports; no participant values in the overview."""

import html

from .io import write_csv
from .roster_benchmark.report import percent


def table(headers, rows):
    def escape(value):
        return html.escape("offen" if value is None else str(value))
    return "<table><thead><tr>" + "".join(f"<th>{escape(h)}</th>" for h in headers) + "</tr></thead><tbody>" + "".join(
        "<tr>" + "".join(f"<td>{escape(v)}</td>" for v in row) + "</tr>" for row in rows) + "</tbody></table>"


def render(output, result):
    def escape(value):
        return html.escape(str(value))
    policy = result["policy"]
    candidates, gates, criteria = [], [], []
    for key, candidate in policy["candidates"].items():
        candidates.append(dict(candidate=key, role=candidate["role"], description=candidate["description"],
                               profile=candidate["profile"], sources=" | ".join(candidate["sources"])))
        for name, gate in candidate["gates"].items():
            gates.append(dict(candidate=key, gate=name, passed=gate["passed"], reason=gate["reason"],
                              sources=" | ".join(gate["sources"])))
    for key, c in policy["criteria"].items():
        criteria.append((key, c["weight"], c["definition"], c["rubric"]))
    write_csv(output / "candidates.csv", candidates)
    write_csv(output / "gates.csv", gates)
    overview = table(
        ["Kandidat", "Rolle", "Status", "Dokumente vorhanden/erwartet", "Seiten gültig/erwartet", "Exakt ohne Swap",
         "Referenzfelder", "Exakter Feld-F1 originale Rollen (feste Paare)", "Feld-F1 ohne Swap (neue Paarung)", "F1 mit Referenz-Swap",
         "Fehlende Personen", "Zusätzliche Personen", "Fehlende Felder", "Zusätzliche Felder"],
        [(r["candidate"], r["role"], r["status"], f'{r["documents_processed"]}/{r["documents_expected"]}',
          f'{r["pages_successful"]}/{r["pages_expected"]}', r.get("exact_fields"), r.get("reference_fields"),
          percent(r.get("original_exact_f1")), percent(r.get("strict_exact_f1")), percent(r.get("assisted_exact_f1")),
          r.get("missing_participants"), r.get("extra_participants"), r.get("missing_fields"), r.get("extra_fields"))
         for r in result["candidates"]])
    evidence = table(["Kandidat", "Eignung", "Evidenzabdeckung", "Gewichteter Gesamtwert", "Offene Ausschlusskriterien"],
        [(key, m["eligibility"], percent(m["evidence_coverage"]), percent(m["weighted_score"]),
          ", ".join(m["open_gates"])) for key, m in result["matrix"].items()])
    ratings = table(["Kandidat", "Kriterium", "Wert", "Begründung", "Belege"],
        [(key, name, rating["value"], rating["reason"], " | ".join(rating["sources"]))
         for key, c in policy["candidates"].items() for name, rating in c["ratings"].items()])
    decision = result["recommendation"]
    files = ("selection.json", "candidates.csv", "gates.csv", "matrix.csv", "pilot.csv", "field_scores.csv",
             "document_timings.csv")
    details = []
    for row in result["candidates"]:
        for mode in ("strict", "reference_assisted"):
            target = output / "evaluations" / row["candidate"] / mode / "report.html"
            if target.is_file():
                link = target.relative_to(output).as_posix()
                details.append(f'<li><a href="{escape(link)}">{escape(row["candidate"])}: {mode}</a></li>')
    body = f"""<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'">
<title>Verfahrensauswahl</title><style>body{{font:16px system-ui;margin:2rem;color:#172536;background:#f7f9fb}}
table{{border-collapse:collapse;background:white;margin:1rem 0;font-size:.9rem}}td,th{{border:1px solid #ccd5df;padding:.5rem;text-align:left}}
.scroll{{overflow:auto}}p,li{{max-width:85rem;line-height:1.5}}code{{overflow-wrap:anywhere}}</style>
<h1>Verfahrensauswahl: {escape(result['scope'])}</h1>
<p><strong>Status: {escape(decision['status'])}.</strong> Vorschlag: {escape(', '.join(decision['main_methods']))}.
Optional: {escape(decision['optional_experiment'])}. Es wurde keine Hauptkonfiguration verändert.</p>
<p>{result['documents_evaluated']} Dokumente, {result['groups_evaluated']} Gruppen in dieser Gegenprobe.
Pilotplan: {result['sample']['pilot_lists']} Listen, {result['sample']['pilot_groups']} Gruppen.
Strata dieser Gegenprobe: {escape(result['strata_evaluated'])}.</p>
<p>Entwicklungs-Replays sind keine unabhängige Pilotstudie. Ohne mindestens
{policy['minimum_pilot_lists']} Pilotlisten, {policy['minimum_pilot_groups']} Gruppen, alle erforderlichen Strata,
vollständige vergleichbare Hauptkandidaten und geklärte harte Kriterien bleibt die Empfehlung vorläufig.</p>
<p>{escape(decision['rule'])}</p><ul>""" + "".join(f"<li>{escape(r)}</li>" for r in decision["reasons"]) + "</ul>"
    body += "<h2>Stufe A: Eignung und Evidenz</h2>" + evidence
    body += "<p>Unbekannt ist weder null Punkte noch bestanden. Bei unvollständiger Evidenz wird kein gewichteter "
    body += "Gesamtscore gebildet. Die JSON-Datei enthält lediglich mögliche Scoreintervalle, keine Schätzwerte.</p>"
    body += table(["Kandidat", "Rolle", "Eigenschaften", "Profil", "Primärquellen"], [list(c.values()) for c in candidates])
    body += table(["Kriterium", "Gewicht (vor Normalisierung)", "Definition", "Skala"], criteria)
    body += table(["Kandidat", "Harte Bedingung", "Bestanden", "Begründung", "Belege"], [list(g.values()) for g in gates])
    body += ratings + '<h2>Stufe B: bestehende Feldbewertung</h2><div class="scroll">' + overview + "</div>"
    body += "<p>Beide Auswertungen benutzen dieselben Originalextraktionen und den bestehenden globalen Kursabgleich. "
    body += "Primär werden originale Namensrollen auf denselben Paaren wie bei der Referenz-Swap-Auswertung bewertet "
    body += "(original_roles in JSON/CSV). Zusätzlich wird ohne Swap die globale Paarung neu berechnet (strict). "
    body += "Auch dieser Vergleich verwendet Referenzwerte zur Paarung und ist keine unabhängige Identitätsprüfung. "
    body += "Exact Match ist normalisiert; unveränderte Zeichenfolgen stehen zusätzlich unter raw_exact_fields in JSON. "
    body += "OCR-Rohtext wird nicht nach Teilnehmerfeldern gerankt. Technisch gültige partial-Seiten können fachlich "
    body += "falsch sein; fehlende/failed/unavailable Seiten werden nicht als technisch erfolgreich gezählt.</p>"
    body += "<p>Feldfehler je Feldtyp: field_scores.csv. Seiten-/Dokumentzeiten und ursprüngliche Timing-Komponenten: "
    body += "document_timings.csv. Lade-/Warm-up-Zeiten und Ressourcen in selection.json betreffen den vollen Quelllauf. "
    body += "GPU-Allokation ist keine Messung des gesamten Gerätespeichers; Energie, Eurokosten und Nacharbeit bleiben "
    body += "ohne Messung offen. Warm-/Kaltcachewerte sind nicht austauschbar.</p><ul>" + "".join(details) + "</ul>"
    body += "<h2>Reduktion und Grenzen</h2><p>" + escape(decision["hybrid_reason"]) + "</p>"
    body += table(["Nicht im Hauptvergleich", "Begründung"], list(decision["excluded_from_main"].items()))
    body += "<p>Verglichen werden vollständige Pipelines. OCR-Engine, Tabellenrekonstruktion, Parameter, Bildaufbereitung, "
    body += "Prompts, Literalprüfungen, Namensheuristiken und Assist-Merging können Effekte verursachen. "
    body += "Gleiche 4B-Bezeichnung bedeutet weder gleiche Architektur noch gleiche Rechenkosten. "
    body += "Die Kursliste ist ohne manuelle Prüfung keine bestätigte Seiten-/Handschriftreferenz. "
    body += "Keine Signifikanz- oder allgemeinen Gewinneraussagen aus kleinen oder vorbenutzten Stichproben.</p>"
    body += "<p>Plan-Siegel: <code>" + escape(result["plan_seal"]) + "</code></p><p>"
    body += " · ".join(f'<a href="{name}">{name}</a>' for name in files) + "</p></html>"
    (output / "report.html").write_text(body, encoding="utf-8")
