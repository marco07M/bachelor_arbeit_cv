# OCR-Folgeseiten: vollständige Beobachtung vor der Feldzuordnung

Stand: 03.11.2026. Ausgangsbericht:
`testframework/ergebnisse/20261103T103940Z-910665bc/`, Quelllauf
`runs/20261103T101357Z-d77317f7/`. Alle realen Inhalte und Ergebnisdateien bleiben
lokal; hier stehen ausschließlich technische Befunde und aggregierte Zahlen.

## 1. Verwerfen Confidence-Schwellen tatsächlich OCR-Text?

**Im untersuchten Tesseract-/Docling-Pfad nicht aufgrund eines Mindest-Scores.**
`ocr.py` übernimmt jedes nichtleere Tesseract-Wort. Der installierte, festgeschriebene
Docling-CLI-Pfad filtert in `_run_tesseract` lediglich leere TSV-Textzeilen und
übernimmt die übrigen Zeilen unabhängig vom Score. Die genaue Implementierung
wurde lokal in `docling_runtime/.venv/Lib/site-packages/docling/models/stages/ocr/tesseract_ocr_cli_model.py`
geprüft; keine Änderung an installierten Paketen.

Es gibt dennoch andere, notwendige oder diagnostisch relevante Grenzen:

| Stufe / Funktion | Bedingung | Behandlung der ursprünglichen Beobachtung |
| --- | --- | --- |
| Tesseract `recognize` | ausschließlich leerer/Whitespace-Text wird ausgelassen | Nichtleerer Text bleibt exakt erhalten, auch bei negativem/fehlendem Score. |
| Docling `get_ocr_rects` | DEFAULT nutzt Layout-/PDF-Textbereiche; FULL_PAGE erfasst die ganze Seite | Bestimmt, wo OCR läuft; kein Confidence-Filter auf bereits erkannten Text. |
| Docling `post_process_cells` | OCR-/PDF-Zellen werden bei Überlappung nach Priorität zusammengeführt | Kann OCR-Zellen verdrängen; neuer vorgelagerter Messpunkt erhält sie separat. |
| `select_person_rows` | wiederholte Namensmuster mit 2–10 Wörtern und regelmäßigem Zeilenabstand, mindestens vier Zeilen | Auswahl für den primären Prompt; die vollständigen Wörter bleiben unabhängig davon gespeichert und sichtbar. |
| `parse_assignment_response` / Schemata | Typen, Quellzeile, literale Werte, zulässige Rollen | Fehlerhafte Vorhersage wird verworfen, ursprüngliche OCR nicht. Gültige andere Zeilen bleiben erhalten. |
| `ground_response` / `ocr_evidence` | aktueller Zeilenbeleg, Wort-/Phrasengrenzen, Spaltenposition, keine überlappenden Feldbelege | Unbelegte Felder bleiben unbekannt; Ablehnungen werden protokolliert. |
| `structured_mapping` | eindeutige Überschriften oder begrenzter unabhängiger Identitätsbeleg | Nicht zugeordnete Zellen bleiben mit Grund erhalten. |
| `partial_identity_fallback` | mindestens zwei Zeilen mit gleicher eindeutiger Spaltenpaarung: Komma-Namensgruppen von 2–80 Zeichen und separate Ziffernfolge von 4–16 Stellen | Keine pauschale Teilnehmererzeugung aus beliebigen Fragmenten. Bei sicherem Überschriftenmapping gelten diese Fallback-Schwellen nicht. |
| `filter_page_people` | ausdrücklich belegte eigene Kursleiter-/Trainerrolle | Ausschluss nur aus Teilnehmerausgabe; Rohbeobachtung bleibt. Im Ausgangsfall keine solchen Ausschlüsse. |
| Generierung | Kontext-/Ausgabelimit, gültiges Antwortformat | Technische Fehler/Abschneiden werden ausgewiesen; keine still gekürzte oder erfundene Ersatzantwort. |

Diese Filter sind keine Korrektheitswahrscheinlichkeiten und wurden nicht global entfernt.
`pdf.osd_min_confidence` betrifft ausschließlich die Drehungsprüfung und ist kein
Wortfilter oder Klassifikator für Teilnehmerlisten. Signatur-Schwellen verändern
ebenfalls nicht die Erhaltung von Namen, IDs oder Organisationsbeobachtungen.

## 2. Welche Scores kennzeichnen nur Unsicherheit?

Tesseract-Belege unter **30** markieren einen belegten Wert als `uncertain`.
Native Paddle-/Docling-Positionsbelege unter **0,5** haben im vorhandenen räumlichen
Prüfpfad dieselbe reine Hinweisfunktion. Die Skalen sind unterschiedlich und
werden im Beobachtungsregister ausdrücklich benannt. Fehlender Score bleibt `null`;
es wird keine künstliche Confidence erzeugt.

Ein konkreter Integrationsfehler wurde behoben: Das kompakte `OCR_TEXT_ROWS`-
Antwortprotokoll umging bisher die Wort-Confidence-Prüfung des älteren Wortprotokolls.
`attach_record_observations` verbindet jetzt auch diese Felder mit ihren tatsächlichen
Wort-IDs, Originaltexten, Scores und präzisen Boxen. Niedriger Score markiert
Unsicherheit, löscht den Wert aber nicht. Historische Zellbezüge werden nur bei
exakt übereinstimmendem Zelltext aus den gespeicherten Quellzeilen rekonstruiert.

Auch fehlende oder nicht numerisch lesbare Tesseract-Scores verursachen jetzt
keinen Abbruch der gesamten Erkennung. Originalscore und Text bleiben erhalten.

## 3. Wo gehen auf Seite 2 Informationen verloren?

Der Ausgangslauf wurde stufenweise geprüft:

| Seite 2 | Tesseract + LLM | Docling |
| --- | --- | --- |
| Gespeicherte OCR-Beobachtungen | 51 Wörter | 66 Zellen |
| Niedriger Score | 16 Wörter unter 30 | 20 Zellen unter 0,3; 38 unter 0,5 |
| OCR-Zeilen / native Tabelle | 10 OCR-Zeilen | 6×3 native Tabelle mit 18 Zellen |
| Tatsächlicher Zuordnungseingang | alle 10 OCR-Zeilen | native Tabellenzellen; 25 OCR-Beobachtungen wörtlich und geometrisch darin verknüpfbar |
| Nicht an das LLM gesendete OCR-Zeilen | 0 | kein LLM in diesem Verfahren |
| Rohe LLM-Vorschläge | 1 Person | nicht anwendbar |
| Nachträglich verworfene Modellzeilen / Trainer | 0 / 0 | keine Teilnehmer zum Filtern |
| Strukturierte Personen | 1 | 0 |

Bei Tesseract auf Seite 2 ist die Zeilenauswahl somit **nicht** die nachgewiesene
Verlustursache. Das Modell ordnet aus bereits schwachem OCR-Text nur eine Person zu.
Weitere Wörter können Logos, Fußzeile, Signaturfragmente oder fehlerhafte Lesungen
sein; 51 Wörter sind nicht 51 korrekte Teilnehmerfelder.

Bei Docling sind Texte vorhanden. Sie gelangen aber ohne zuverlässige Überschriften
und unabhängige Identitätsbelege nicht in sichere Personenfelder. Die sechs nativen
Zeilen scheitern an der Spaltenzuordnung. Für 41 OCR-Beobachtungen besteht keine
wörtliche und geometrische Verknüpfung zur nativen Tabelle. Das ist eine begrenzte
Beleganalyse, kein Beweis, dass alle 41 im SDK gelöscht wurden.

## 4. Erkennt Tesseract mehr, als die strukturierte Ausgabe zeigt?

Ja: 138 Wörter auf Seite 1 und 51 auf Seite 2 bleiben im Rohtext, obwohl daraus
nur neun beziehungsweise eine Person ausgegeben werden. Auf Seite 1 gingen bislang
neun von 22 OCR-Zeilen an das LLM: 59 Wörter im Prompt, 79 weitere Wörter im Rohtext.
Auf Seite 2 waren bereits alle zehn Zeilen im Prompt.

Die neue Diagnose zeigt jede Beobachtung, ihren Eingangsbezug und die Verknüpfung
mit einem finalen Feld. Nicht ausgewählte Zeilen sind als solche sichtbar.
Dies ersetzt keine manuelle Prüfung der OCR-Schreibweise.

## 5. Erkennt Docling mehr, als der Mapper ausgibt?

Ja: 153 beziehungsweise 66 OCR-Zellen stehen neun beziehungsweise null Personen
gegenüber. Die neue Erfassung **vor** Doclings Zusammenführung liefert auf derselben
bildbasierten PDF ebenfalls 153 und 66 Zellen. Danach bleiben jeweils alle erhalten:
**kein SDK-Zusammenführungsverlust in diesem konkreten Dokument**.

Bei Dokumenten mit überlappendem PDF-Text kann der geprüfte SDK-Pfad hingegen
OCR-Zellen verdrängen. `configure_ocr_capture` speichert vor diesem Schritt
unveränderte Texte, Scores, Boxen, Engine-Seite und Quellreferenz. Das ändert weder
Doclings Prioritätsregel noch TableFormer-Zellen. Ein synthetischer Test simuliert
Löschung und Mutation im SDK und bestätigt den Erhalt der vorherigen Beobachtung.

## 6. Welche Regeln wurden geändert und was ist aktiv?

Immer aktiv:

- `ocr_observations.py` liefert ein von der Teilnehmerzulassung getrenntes Register
  mit Originaltext, Score/Skala, Position, PDF-Seite, Engine und Quellbezug.
  Fehlende Geometrie oder Zeilenmetadaten dürfen keine Beobachtung entfernen.
- Tesseract speichert auch einen unlesbaren/fehlenden Score ohne Wortverlust.
- Das kompakte LLM-Protokoll erhält Wort-Confidence und präzise Feldbelege.
- Eine belegte Benutzer-ID allein genügt bei eindeutig zugeordneter ID-Spalte,
  auch wenn der Namenshinweis gesetzt ist. Ohne diesen Spaltenbeleg bleibt der
  strengere Identitätsfilter bestehen.
- Vollständig abgelehnte Quellzeilen erhalten einen expliziten Evidenzgrund.
  Auch solche Ablehnungen brechen die Antwortberichterstellung nicht ab.
- Der native Docling-Mapper protokolliert jede Zeilenentscheidung, einschließlich
  Überschrift, fehlender Zuordnung, unvollständigem Raster und Teilidentitätsfallback.
- Docling speichert zusätzlich Beobachtungen vor der SDK-Zusammenführung.

Die untersuchte vollständige Zeilenvariante ist **optional**:
`models.ocr_llm.ocr_row_selection: all`. Standard bleibt `pattern`, einschließlich
der bereits vorhandenen Übernahme bei verlässlich kompatiblen Fortsetzungen.
Die Variante kann unregelmäßige Zeilen an das LLM geben, hat hier aber eine reale
Regression verursacht und wird daher nicht global aktiviert.

Die tatsächlichen regulären Eingabetexte und Systemanweisungen wurden auf beiden
Seiten gegen Commit `f90b397` verglichen: identisch. Die Prüfung steht lokal in
`runs/observation-retention-20261103-checked/default-prompt-equivalence.json`.
Neue Protokoll-/Cacheversionen: Hauptprompt v24, OCR-Cache v3, nativer Mapper v7,
Beobachtungsregister v1. Die sechs Hauptverfahren und Modelle bleiben erhalten.

## 7. Werden Überschriften von Seite 1 übernommen?

Die bestehende dokumentbezogene Prüfung aus dem
[Spaltenkontextbericht](document-columns.md) bleibt aktiv: gleiche PDF, frühere
Quellseite, gleiche Spaltenzahl und kompatible gemessene Geometrie; neue eindeutige
Überschriften haben Vorrang. Leere Seiten löschen keinen gültigen Zustand.

**Im konkreten Tesseract-/Docling-Ausgangslauf fehlen auf Seite 1 eindeutige
Überschriftenbelege.** Deshalb gibt es dort keine verlässliche Spaltenrolle zum
Vererben. Die native Docling-Tabelle wechselt zudem von sieben auf drei Spalten.
Eine Referenzliste oder ein einzelner Namensteil wird nicht als Ersatzüberschrift
verwendet. Ein synthetischer Test bestätigt die sichere Übernahme bekannter Spalten
und den Erhalt eines einzelnen Identitätsfelds neben leeren Zellen.

## 8. Wie viele zusätzliche Textbeobachtungen bleiben erhalten?

Die reale OCR liefert unverändert **189 Tesseract-Wörter und 219 Docling-Zellen**.
Die Textfolgen stimmen vor/nach dem Versuch exakt überein. Es gibt keine zusätzliche
Texterkennung und keinen belegten Confidence-bedingten Rohtextverlust auf diesen
Seiten. Neu sind vollständige Herkunfts-/Ablehnungsansichten und der vorgelagerte
Docling-Messpunkt; dessen 219 Momentaufnahmen sind keine 219 neuen Texte.

Die optional vollständige Zeilenvariante gibt auf Seite 1 79 zuvor nur im Rohtext
gespeicherte Wörter zusätzlich an das LLM. Auf Seite 2 kommen keine Eingabewörter
hinzu. Unsichere oder nicht zugeordnete Rohtexte zählen nie als korrekte Feldextraktion.

## 9. Welche zusätzlichen strukturierten Felder sind korrekt?

**Standard: null zusätzliche exakte Felder und null verlorene bisherige Treffer.**
Die Auswertung nutzt die unveränderte eingefrorene Kursreferenz erst nach der
Extraktion. Die bisherigen LLM-Antworten werden nur mit der neuen Beleg-/Confidence-
Prüfung validiert; es wird kein neuer regulärer LLM-Lauf behauptet.

| Verfahren, Standard | Personen | Exakt / 72 | Falsch | Fehlend | Exakter Recall | Levenshtein-Feld-F1 |
| --- | --- | --- | --- | --- | --- | --- |
| OCR-LLM vorher / nachher | 10 / 10 | 25 / 25 | 12 / 12 | 35 / 35 | 34,72 / 34,72 % | 63,29 / 63,29 % |
| Docling vorher / nachher | 9 / 9 | 19 / 19 | 6 / 6 | 47 / 47 | 26,39 / 26,39 % | 48,65 / 48,65 % |

Vier nichtleere OCR-LLM-Felder und 25 Docling-Teilfelder bleiben im Standard unsicher.
Die Beobachtungen und sämtliche bisherigen korrekten Felder bleiben erhalten.

Separater Versuch mit allen OCR-Zeilen, **nicht der Standard**:

| OCR-LLM | Ausgang | Vollständige Zeilenvariante |
| --- | --- | --- |
| Personen gesamt / Seite 2 | 10 / 1 | 17 / 8 |
| Exakte Felder | 25 | 24 |
| Falsche / fehlende Felder | 12 / 35 | 19 / 29 |
| Exakter Recall | 34,72 % | 33,33 % |
| Exakte Precision / F1 | 67,57 / 45,87 % | 55,81 / 41,74 % |
| Levenshtein-Feld-F1 | 63,29 % | 55,62 % |
| Neue korrekte / verlorene korrekte Felder | – | 0 / 1 |

Ein bisher korrekter Treffer der maschinenschriftlichen ersten Seite geht verloren.
Auf Seite 2 bleibt die Anzahl exakter Treffer bei einem. Die Zahl zusätzlicher
Personen gegenüber der Kursreferenz ist weiterhin null; die sieben zusätzlichen
Ausgabezeilen liefern hier jedoch keine zusätzlichen exakten Felder. Es handelt
sich um mehr unsichere/falsche Verarbeitung vorhandenen OCR-Texts, keinen OCR-Gewinn.

Der reale Versuch dauerte 109,5 s: OCR-LLM 70,05 s, Docling 36,63 s, übrige Zeit
Vorbereitung/Prüfung/Bericht. Drei Textgenerierungen einschließlich Namensentscheidung,
ein Textmodell-Warm-up, zwei reguläre Tesseract-Seiten und zwei Docling-Seitenaufrufe;
kein VLM, API-Aufruf, Download oder Training. Nicht als allgemeiner Laufzeitgewinn
interpretieren. Der abschließende Standard verwendet einen CPU-Validierungs-Replay
(OCR-LLM ca. 0,066 s, Docling-Belegprüfung ca. 0,089 s einschließlich der
Methodenarbeitskopie, ohne finale Berichterstellung).
Historische Inferenzzeit wird dabei nicht als neue Messung ausgegeben.

## 10. Welche Modell-/Strukturgrenzen bleiben?

Es wird kein Name transkribiert, den die Engine nicht liefert. Bereits vorhandene
Fehllesungen und unvollständige Wörter bleiben solche; ein hoher Score macht sie
nicht automatisch richtig. Fehlende Überschriften und unvollständige native
Tabellen verhindern weiterhin sichere Docling-Zuordnungen auf dieser Folgeseite.
Ein unbekannter Namensbestandteil oder eine Organisation allein begründet keine
beliebige neue Person. Der begrenzte headerlose Fallback bleibt deshalb streng.

Die Excel-Kursreferenz enthält auch handschriftliche Personen, aber keine geprüften
Regionen oder Seitenkoordinaten. Sie erlaubt den dokumentweiten Feldvergleich,
keine separate Handschrift-CER/WER oder eindeutige Detektions-/Transkriptionsdiagnose
für jede leere Region. Modelleignung und bisherige Bildversuche stehen im
[Handschriftbericht](handwriting-optimization.md).

## 11. Verifikation und lokale Ansichten

Die Tests decken hohe/niedrige/fehlende Scores, Teiltexte, einzelne Identitätsfelder,
unzugeordnete Zeilen, fehlende/geerbte/inkompatible Überschriften, leere Zellen,
LLM-Auslassung, Validierungsablehnung, native Mappingverluste, leere OCR und
unveränderte maschinenschriftliche Werte ab. Synthetische Tests prüfen Softwarelogik,
keine reale Handschriftqualität.

**652 lokale Volltests in 49,23 s**, **48 API-Tests in 7,64 s** und zuletzt
**107 gezielte Tests in 2,57 s** bestanden. Ruff ohne Befund. Standard-Prompts
und Systemanweisungen gegen den bisherigen Commit geprüft; tatsächliche
OCR-Textfolgen und historische Dateihashes unverändert. Berichtszähler zusätzlich
gegen JSON/CSV/Excel sowie die HTML-Beitragsprüfung gegengeprüft.

- Standardauswertung: `runs/observation-retention-20261103-checked/comparison/report.html`.
- Vollständige Roh-/Zuordnungsansicht: im selben Ordner unter `source/report.html`.
- Separater negativer Versuch: `runs/observation-retention-20261103-all-rows/comparison/report.html`.
- Tatsächlicher Erkennungslauf: `runs/20261103T135955Z-83a79dcb/`.
- `check.json` belegt unveränderte historische Dateien und trennt Standard/
  Versuchsvariante. `observations/*.json` und `*.csv` enthalten Originalbelege,
  Zuordnungszustände, Zeilen- und Feldentscheidungen.

## 12. Reproduktion und nächster sinnvoller Schritt

Aus `software/`, jeweils mit neuem Ausgabeordner:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\api_firmen_pc\.venv\Scripts\python.exe -m pytest -q api_firmen_pc/tests
.\.venv\Scripts\python.exe scripts/check_observation_retention.py --source-report testframework/ergebnisse/20261103T103940Z-910665bc --new-run runs/20261103T135955Z-83a79dcb --output runs/observation-check-neu --ocr-variant baseline
.\.venv\Scripts\python.exe scripts/check_observation_retention.py --source-report testframework/ergebnisse/20261103T103940Z-910665bc --new-run runs/20261103T135955Z-83a79dcb --output runs/observation-all-neu --ocr-variant all
```

Der Vergleich lädt keine Modelle; er verwendet unveränderte gespeicherte Antworten
und prüft tatsächliche Bildhashes. Ein neuer Erkennungslauf ist mit der vorhandenen
Benchmark-Konfiguration möglich. `models.ocr_llm.ocr_row_selection: all` verlangt
einen expliziten Versuch und eine neue Qualitätsauswertung; Messwerte dieses
Berichts beziehen sich auf die vollständig gespeicherten tatsächlichen Prompts.
Der nächste sachliche Schritt sind unabhängig transkribierte Entwicklungsregionen
und weitere reale Dokumente. Das Erfinden fehlender Werte oder eine globale
Aktivierung der hier schlechteren Zeilenvariante ersetzt diese Grundlage nicht.
