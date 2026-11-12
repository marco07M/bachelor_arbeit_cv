# Systematische Fehleranalyse und begrenzter Gegencheck, 11.11.2026

## Grundlage und Datenstatus

Neuester tatsächlich vollständiger Fünfervergleich zu Beginn des Auftrags:
`testframework/ergebnisse/20261111T110330Z-09f5d83e/`, Quelllauf
`runs/20261111T091101Z-59c4b71d/`. Später angelegte Fehler-/Dashboardberichte
verwenden dieselben Extraktionen und sind keine neuen Modellläufe. Es gibt
zehn PDFs, zwanzig Seiten, fünf Verfahren, 155 berücksichtigte Kursreferenzpersonen
und **620 Referenzfelder je Verfahren**. Eine weitere Referenzschulung liegt
außerhalb der zehn Eingabe-PDFs und wird unverändert ausgeschlossen.

Der historische Manifest-Split ist nicht beschriftet; die zehn Dokumente sind
nachweislich bereits zur Entwicklung und Fehleranalyse verwendet worden. Dieser
Auftrag behandelt sie deshalb ausschließlich als **Entwicklungsdaten**, nicht
als unabhängige finale Teststichprobe. Keine anderen/finalen Dokumente wurden
für Optimierung herangezogen. CSV-/Excel-Referenzen, Bewertungsregeln, Zuordnung,
Normalisierung und Tokenlimits wurden nicht verändert.

Geprüft wurden alle hundert Methode-/Seiten-Rohdatensätze und zugehörigen
Extraktionen, 297 JSON- und 23 JSONL-Dateien des Quelllaufs sowie sein vollständiges
2.147-zeiliges Laufprotokoll. Die strukturierten Dateien sind lesbar, ohne
festgestellte JSON-Korruption. Die gespeicherten Bildhashes verbinden die
Modellantworten mit ihren tatsächlichen Laufbildern. Ausgewählte lesbare und
handschriftliche Seiten wurden zusätzlich visuell kontrolliert. Nicht jeder
Fehler besitzt eine unabhängig annotierte PDF-Zeilen-/Feldposition.

## Häufigste und schwerwiegendste Ursachen

| Priorität / Befund | Nachweis | Maßnahme und Grenze |
|---|---|---|
| Sehr hoch: zwölf seitliche Seiten in der gemeinsamen Vorbereitung | Historische Laufbilder/Manifest und zuvor visuell geprüfte Rotationen; derselbe Fehler wirkt auf mehrere Verfahren. | Bereits vor diesem Auftrag automatisch repariert und an 20/20 Entwicklungsseiten technisch geprüft. Der untersuchte Modelllauf entstand noch davor. Hier keine neue vollständige Modellmessung mit neu ausgerichteten Bildern. |
| Hoch: zwei Paddle-Seiten überschreiten das Eingabelimit vor der Generierung | `assignment.error`: 13.298 bzw. 12.575 Tokens bei unverändertem Limit 12.000; keine Antwort gespeichert. | **Neu behoben:** exakt redundante Zeilenrahmen aus dem Input entfernt. Zelltexte, Reihenfolge, Zellrahmen, Präzision und sonstige Angaben bleiben erhalten. Danach 11.170 bzw. 10.384 Tokens. |
| Hoch: neun VLM-/Hybridseiten brechen am Ausgabelimit ab | Vier direkte und fünf hybride Antworten erreichen das gespeicherte Limit; JSON ist unvollständig. | Offen. Keine unsichere Teil-JSON-Reparatur und keine pauschale Erhöhung des Limits. Die frühere Promptpräzisierung ist in diesen alten Antworten noch nicht wirksam. |
| Hoch: vierzehn leere Tesseract+LLM-Antworten | `participants=[]` trotz jeweils nichtleerer übergebener OCR-Zeilen; damit kein späterer Exportverlust. | Leere Antwort ist nachgewiesen; Orientierung, OCR-Fehler und Modellzuordnung sind nicht für jedes Feld einzeln trennbar. Gespeicherte Antworten enthalten keine nachträglich wiederherstellbaren Teilnehmer. |
| Hoch: Regelbaseline bleibt auf allen zwanzig Seiten ohne Teilnehmer | Ausrichtung und konfigurierte Header unterscheiden sich; der gemeinsame Headerparser versteht z. B. User/User Name bereits, die Vorlagenlogik nicht ausreichend. | Eine naheliegende Erweiterung wurde mit unveränderter OCR geprüft, wegen zusätzlicher falscher Felder jedoch **nicht aktiviert**. Vorlagen-/OCR-/Rastergrenzen bleiben offen. |
| Mittel: erste Datenzeile kann bei Regeln verloren gehen | Bei `body_top` auf/kurz unter der ersten Rasterlinie begann die Bildung der Zeilenbänder erst an der nächsten Linie. | **Neu behoben:** erstes Teilband ab `body_top` erhalten. Zwei Regressionen prüfen die Grenzlagen. Auf dem realen eingefrorenen Bestand weiterhin 0→0 Teilnehmer; kein realer Qualitätsgewinn durch diese Einzelkorrektur. |
| Mittel: ungeeignete oder mehrdeutige Spaltenbelege | Modellheader enthalten teilweise Metadaten/Teilnehmerwerte, Zellzahlen stimmen nicht immer. Namens-/ID-/Organisationsrollen sind dann nicht sicher. | Bereits vorhandene geometrisch abgesicherte Fortsetzungslogik und scoped Headerregeln beibehalten. Keine Datenheader geraten korrigiert und keine Werte aus Nachbarzeilen/-seiten übernommen. |
| Grundsätzliche Grenze: Referenzfelder sind nicht immer im Dokument vorhanden | Das handschriftliche Formular hat Namen, Geburtstag und Unterschrift, aber keine individuellen ID-/Organisationsspalten. | ID/Organisation bleiben unbekannt; Firmenname, Geburtsdatum oder Unterschrift dürfen diese Felder nicht ersetzen. Referenz bleibt trotzdem unverändert: diese fehlenden Felder verschwinden nicht aus der Bewertung. |

Im ursprünglichen Standardvergleich fehlen insgesamt 2.400 von 3.100 Feldwerten
über fünf Verfahren. Es gibt 549 exakte und 151 falsche Werte. Namen sind deutlich
häufiger verfügbar als ID/Organisation. Diese gepoolten Zahlen sind nur eine
Bestandsbeschreibung, keine zusätzliche gemeinsame Siegerkennzahl.

## Verluststellen entlang der Pipeline

1. **PDF/Bild → Vorbereitung:** Originale und gespeicherte tatsächliche Laufbilder
   bleiben unverändert. Die Orientierungsreparatur ist ein früherer, separat
   dokumentierter Schritt; alte OCR wird hier nicht als OCR neuer Bilder ausgegeben.
2. **OCR/Struktur → Modelleingabe:** Die zwei neuen Paddle-Fälle besitzen bereits
   native OCR, Zeilentranskripte und Zellpositionen. Ihre zusätzlich übergebenen
   Zeilenrahmen sind jeweils exakt die Vereinigung der Zellrahmen. Dieser doppelte
   Geometrieanteil war ausschlaggebend für die technische Budgetüberschreitung.
3. **Modelleingabe → Antwort:** Neue `compact_assignment_rows` lässt ausschließlich
   exakt rekonstruierbare äußere Rahmen weg. Fehlende, abweichende oder anders
   präzise Rahmen bleiben erhalten. Rückrekonstruktion reproduziert auf **20/20
   Seiten aus zehn PDFs** den ursprünglichen JSON-Inhalt exakt; danach liegt
   keine dieser zwanzig Eingaben mehr über 12.000 Tokens. Kein Text wird gekürzt,
   gerundet oder als angeblich unwichtig verworfen. Das ist Datenkompaktierung,
   keine Promptformulierungsstudie. Die festen Promptvorlagen und Schemas bleiben gleich.
4. **Antwort → Validierung:** Für genau die zwei vorher blockierten Seiten wurden
   zwei lokale Textmodellaufrufe plus ein unveränderter Warm-up durchgeführt.
   Modell/Revision/Gewichte, Systemprompt einschließlich Schema, Generierungs-
   einstellungen und Grenzen entsprechen den gespeicherten Originalen. Die
   tatsächlichen neuen Nachrichten/Hashes, Antworten und Laufzeiten sind gespeichert.
   Die übrigen 18 Paddle-Seiten und alle anderen Verfahren behalten ihre ursprünglichen
   Vorhersagen. Es gab keine neue OCR, VLM-Inferenz, Downloads oder API-Übertragung.
5. **Validierung → Ausgabe:** Tatsächlich übergebene Zeilen-IDs/Texte werden gegen
   die gespeicherten Originalzeilen verifiziert. Literal-/Positionsprüfung verwendet
   die **im tatsächlichen Modellinput gespeicherten Feldbänder**, auch wenn der
   früh abgebrochene historische Assignment-Datensatz diese noch nicht separat
   gespeichert hatte. Datums-/Signaturbeobachtungen werden nicht durch gelockerte
   Regeln zu Namen erklärt. Zehn belegbare Teilpersonen verbleiben zusätzlich;
   ID und Organisation werden in diesen Formularen nicht erfunden.

Die zunächst separat erstellte Zwischenvalidierung ohne korrekt rekonstruierte
Feldbänder ist **kein gültiger Wirksamkeitsnachweis** und wurde verworfen. Sie
überzeichnete die Ausgabe (22 statt zehn neue Teilpersonen) und erzeugte zusätzliche
Zuordnungen aus Nachbarspalten. Maßgeblich sind ausschließlich die Pfade mit
`-final` und `quality_comparison.json`. Dieses Beispiel unterstreicht, warum die
vorhandene Positionsprüfung erhalten bleiben muss.

## Gemessener Vorher-/Nachher-Vergleich

Unveränderte eingefrorene Ground Truth, gleicher Matcher und gleiche Feldbewertung.
Die Kontrollneuberechnung reproduziert die ursprünglichen Standardzähler.
Paddle hat davor und danach null referenzgestützte Namenstausche; sein gezeigter
Unterschied entsteht nicht durch einen Wechsel der Namensbewertung.

| Verfahren | Exakt vorher → nachher | Falsch vorher → nachher | Fehlend vorher → nachher | Zusätzliche Felder | Datensätze vorher → nachher |
|---|---:|---:|---:|---:|---:|
| Tesseract + Regeln | 0 → 0 | 0 → 0 | 620 → 620 | 0 → 0 | 0 → 0 |
| Tesseract + LLM | 128 → 128 | 36 → 36 | 456 → 456 | 0 → 0 | 49 → 49 |
| Paddle + LLM | **122 → 133** | **36 → 44** | **462 → 443** | **0 → 0** | **45 → 55** |
| Direktes VLM | 135 → 135 | 56 → 56 | 429 → 429 | 0 → 0 | 73 → 73 |
| OCR + VLM | 164 → 164 | 23 → 23 | 433 → 433 | 0 → 0 | 80 → 80 |

Bei Paddle kommen acht exakte Vornamen und drei exakte Nachnamen hinzu, außerdem
ein falscher Vorname und sieben falsche Nachnamen. ID-/Organisationswerte bleiben
unverändert. Exakter Feld-Recall steigt **19,68→21,45 %**, exakter F1 **31,36→33,38 %**;
die Precision fällt **77,22→75,14 %**. Der technische Abbruch ist behoben, das Ziel
einer Verbesserung ohne zusätzliche falsche Werte ist hier **nicht vollständig
erreicht**. Keine zusätzlichen Teilnehmer gegenüber der Kursreferenz ist kein
unabhängiger Beweis fehlerfreier Identitäten oder allgemeiner Halluzinationsfreiheit.
Viele verbliebene Schreibfehler sind bereits in den wörtlich verwendeten
OCR-Beobachtungen vorhanden; ein Kursreferenzunterschied allein beweist aber
keinen OCR-Fehler an einer unabhängig lokalisierten Dokumentstelle.

Die Generierungen benötigten beobachtet rund 67,9 und 68,8 Sekunden. Parallel
liefen Tests. Dies ist weder ein kontrollierter Laufzeitbenchmark noch ein neuer
vollständiger Fünferlauf; alte End-to-End-Zeiten dürfen nicht als Zeiten eines
vollständig neu ausgeführten korrigierten Systems interpretiert werden.

## Gegenprüfungen ohne neue Inferenz

- Bereits vor diesem Auftrag implementierte User-/Spaltenparser-Reparaturen wurden
  auf eingefrorenen VLM-/Hybridantworten nachgeprüft: direktes VLM gewinnt sechs
  exakte IDs, erhält aber drei zusätzliche falsche ID-Lesungen; Hybrid gewinnt
  neun exakte IDs ohne zusätzliche falsche Felder. Das sind **frühere
  Implementierungen**, kein neuer Erfolg der Inputkompaktierung. Ziffern wurden
  nicht anhand der Referenz korrigiert. Diese getrennte Nachprüfung ersetzt keinen
  vollständigen neuen Modelllauf mit aktueller Prompt-/Bildvorbereitung.
- Die nicht aktivierte Erweiterung der Regelbaseline über gemeinsame englische
  Überschriften gewann in ihrer Vorabprobe 64 exakte Felder, aber auch 40 falsche.
  Beschädigte/missing Rasterlinien und zusammengezogene OCR-Zeilen verhindern
  eine sichere Übernahme allein anhand dieser Überschriften. Deshalb keine neue
  Heuristik zur vermeintlichen Qualitätssteigerung und keine Konfiguration geändert.
- Beleg-/Positionsablehnungen werden als technische Übergänge und nicht automatisch
  als entfernte korrekte Werte behandelt. Niedrige Confidence rechtfertigt weder
  das Löschen aller Beobachtungen noch das Erfinden unbekannter Felder.

## Änderungen, Prüfungen und Wiederaufnahme

Aktiver Code: `unlimited_assignment.py` (verlustfreie Inputkompaktierung mit
Versions-/Nachweisfeld; explizite Eingabebudget-Fehlerstufe), `rules.py` (erstes
Zeilenband erhalten), `roster_benchmark/error_report.py` (v6: Eingabeabbruch
korrekt als `model_input`, nicht als vom Modell erzeugtes ungültiges JSON).
Neue Regressionen: `tests/test_assignment_input_compaction.py`. Die bestehende
Speicherung tatsächlicher Inputs, Prompts und Hashes bleibt erhalten.

Abschließend **864 lokale Tests bestanden (94,81 s)**, **48 API-Tests bestanden
(11,02 s)**; Ruff und regulärer Diff-Check ohne Befund. Die neue Testdatei enthält
14 Fälle einschließlich echter Inputkonstruktion, exakter Rekonstruktion,
Negativfällen mit fehlenden/abweichenden Rahmen, korrekter Fehlerstufe vor
Generierung sowie der beiden ersten-Zeile-Grenzlagen. Ein zuvor ausgeführter
Gesamtlauf mit 863 Tests und ein gezielter Nachtest mit 53 Tests bestanden ebenfalls.

Lokale Nachweise unter `data/systematic-audit-20261111/`: vollständige Inventur,
Hashschutz, `all_layout_compaction.json`, unveränderte Kontrollbewertung,
`new-text-answers/`, tatsächlicher lokaler Generierungslog und Ressourcen,
`validated-source-final/`, `validated-comparison-final/` und
`quality_comparison.json`. Personenbezogene Artefakte bleiben lokal ignoriert;
diese Dokumentation enthält keine Teilnehmerinhalte. Der HTML-Analysebericht
liegt unter `testframework/ergebnisse/systematic-audit-20261111/report.html`.

Die automatische Orientierung und der Spaltenkontext sind bereits aktiv, aber
auf allen fünf Verfahren gemeinsam noch nicht neu gemessen. Ein anschließender
normaler Fünferlauf auf denselben Entwicklungs-PDFs prüft diese Gesamtwirkung.
Ausgabetokenabbrüche, fehlerhafte Handschrifterkennung, unzuverlässige Tabellen-
geometrie und die dokumentbezogene Eignung der Kursreferenz bleiben offen.
Finale unabhängige Daten müssen davon getrennt bleiben.
