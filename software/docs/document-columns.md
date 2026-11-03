# Spaltenüberschriften auf Fortsetzungsseiten

Stand: 03.11.2026. Zusatzauftrag zur dokumentbezogenen Seitenlogik.

## 1. Bisheriger Stand und Ursache

Docling besaß bereits `StructureModel.mapping_context`, getrennt nach PDF-ID.
Das native Mapping und das ältere HTML-Mapping übernahmen eine frühere Zuordnung
jedoch allein bei gleicher logischer Spaltenzahl. Quellseite, Geometrie und
Herkunftsstatus fehlten. Gleich viele Spalten können unterschiedliche Rollen haben.

Paddle/LLM besaß in `assign_pages` frühere Überschriften und `spatial_context`.
Die räumliche Übernahme prüfte bisher vor allem das Seitenverhältnis. Auch
Positionen erkannter Modellwerte konnten als spätere Hinweise dienen. Ein gleiches
Papierformat belegt aber keine gleiche Tabelle.

Tesseract/LLM übernahm in `with_table_columns` nur eine Namensspaltennummer bei
nahezu gleichen erkannten Rasterlinien. Die anderen Feldrollen wurden nicht als
dokumentierter struktureller Kontext übergeben oder gegen ihre Spalten geprüft.

Direktes VLM und OCR-VLM-Hybrid besitzen einen dokumentbezogenen Namenskontext.
Der vorhandene reale Vergleich liefert auf beiden Seiten Teilnehmer. Ein eigener
Fortsetzungsfehler durch fehlende Überschriften ist damit nicht nachgewiesen.
Ihre Bild-, OCR-Hinweis- und Zuordnungsverarbeitung wurde nicht geändert.

## 2. Erweiterung bestehender Mechanismen

`column_context.py` enthält die gemeinsame Prüfung für die bestehenden Zustände;
es führt keine neue Extraktionspipeline oder Referenzzuordnung ein.

Der Zustand enthält Version, PDF-ID, Quellseite, Überschriftenbelege, Feldrollen,
Spaltenreihenfolge, Spaltenzahl und verfügbare normalisierte Geometrie. Er enthält
keine Teilnehmerwerte. Die Zustandshaltung bleibt lokal in `StructureModel`,
`assign_pages` beziehungsweise im Tesseract-Lauf. Neue Instanzen/Läufe beginnen leer.
Der aktuelle Runner verarbeitet Seiten sequenziell; unabhängige Dokumentzustände
werden über PDF-IDs getrennt. Eine gleichzeitige Nutzung desselben Workerprozesses
durch mehrere Threads wird nicht eingeführt oder als unterstützt behauptet.

- `structured_mapping.extract_structured`: native Zellen, mehrzeilige Überschriften,
  wiederholte aktuelle Überschriften und geerbte Rollen werden gemeinsam verarbeitet.
- `table_mapping.extract_docling`: auch der ältere HTML-Pfad muss die gemeinsame
  Prüfung bestehen. HTML ohne Geometrie kann aktuelle Überschriften nutzen, aber
  allein keine verlässliche Übernahme begründen.
- `structure_assignment.document_bands` erweitert den bestehenden räumlichen
  Kontext für Paddle/LLM. Geerbte Feldbänder dienen als explizite Modelleingabe
  und Positionsprüfung. Frühere Modellpersonen ersetzen keine Überschriften.
- `ocr_layout.with_table_columns` und `model_input` geben alle erkannten Feldrollen
  weiter. `parse_ocr_response` und `ocr_evidence` prüfen aktuelle Werte gegen diese
  Spalten, einschließlich Benutzer-ID und Organisation.
- `runner` verarbeitet die Seiten einer PDF aufsteigend. Die Dokumentreihenfolge
  und die ursprüngliche Reihenfolge der ausgegebenen Teilnehmer bleiben erhalten.
- Beim nachträglichen Paddle-Abgleich werden Rasterlinien aus den gespeicherten
  Seitenbildern ermittelt. Es findet dafür keine weitere OCR statt.

Aktive Softwareversionen: Dokumentkontext v1, natives Mapping v6, räumliches
Mapping v8, Zuweisungsprompt v19/v20, Hauptprompt v23. Die bestehenden Hauptprofile
nutzen diese Erweiterung ohne neue Modelle oder geänderte OCR-Standardeinstellungen.

## 3. Kompatibilität und Grenzen

Eine Übernahme verlangt denselben Dokumentbezeichner und eine frühere Quellseite.
Anonyme beziehungsweise alte unversionierte Kontexte reichen nicht. Die Spaltenzahl
muss übereinstimmen, und gemessene normalisierte Kanten dürfen höchstens **0,035
der Seitenbreite** abweichen. Das ist eine feste strukturelle Toleranz, keine
Wahrscheinlichkeit. Vergleichbare Belege stammen entweder aus Rasterlinien oder
aus nativen einzelnen Tabellenzellen; unterschiedliche Geometriearten werden nicht
vermischt. Fehlende Geometrie führt zur Ablehnung statt zu geratenen Positionen.

Paddles frühere Feldbänder werden entlang der korrespondierenden Rasterkanten
auf leicht geänderte Breiten abgebildet. Native Docling-Zellen behalten ihre
logischen Spaltenindizes. Fehlende oder über mehrere Spalten verbundene Zellen
werden nicht in Nachbarfelder verschoben. Einzelne unbekannte Felder bleiben
unbekannt; der restliche belegte Datensatz kann erhalten bleiben.

Eindeutige neue Überschriften haben Vorrang und aktualisieren die gespeicherten
Rollen auch bei geänderter Spaltenreihenfolge. Mehrdeutige neue Überschriften
blockieren einen veralteten Kontext. Leere Seiten und Seiten ohne Tabelle löschen
den letzten gültigen Zustand nicht. Eine inkompatible Zwischentabelle überschreibt
ihn ebenfalls nicht; sie darf ihn selbst jedoch nicht verwenden.

Ohne neue Überschriften kann eine **inhaltlich vertauschte, geometrisch identische**
Spaltenanordnung nicht sicher erkannt werden. Eine kompatible Struktur beweist
auch nicht, dass die Seite eine Teilnehmerliste ist. Die vorhandenen Rollen- und
Literalprüfungen bleiben notwendig; es wird kein neuer Seitenklassifikator behauptet.
Schlecht erkannte Handschrift und fehlerhafte native Tabellen bleiben eigene Grenzen.

## 4. Diagnose

Gespeichert werden `detected_on_current_page`, `inherited_from_previous_page`,
`updated_on_current_page`, `incompatible_table_structure` oder `no_reliable_mapping`,
jeweils mit Quellseite und konkretem Grund. Native Feld-/Zeilenbeweise tragen
`mapping_provenance`; LLM-Zuweisungen tragen `document_column_mapping`.
Der Hauptbericht zeigt eine eigene Tabelle zur seitenübergreifenden Zuordnung.
Die bestehende Strukturdiagnose enthält diese Herkunft ebenfalls in `stages.json`.
Diese Angaben sind ausdrücklich keine OCR-Konfidenzen.

## 5. Kontrollierter Vergleich

Ausgangspunkt ist der verlustärmere Validierungsstand aus
`runs/handwriting-retention-20261103-final/comparison/`, nicht der ältere Bericht,
der noch neun Paddle-Zeilen durch einen fehlenden Einzelwert verwirft.
So wird dieser frühere Fehler nicht erneut als Fortschritt der Seitenlogik gezählt.

Die vorhandene zweiseitige Entwicklungs-PDF wird ausschließlich lokal verwendet.
Eine eingefrorene Excel-Kursreferenz wird erst nach den Extraktionsentscheidungen
geöffnet. Sie wird nicht zur Überschriften- oder Spaltenerkennung herangezogen.
Ohne lokalisierte Transkripte entsteht daraus keine separate Handschrift-CER/WER.

Realer Vergleich, jeweils 72 bewertbare Referenzfelder:

| Verfahren | Personen vorher → nachher | Exakt | Falsch | Fehlend | Exakter Recall |
| --- | --- | --- | --- | --- | --- |
| Tesseract/LLM | 10 → 10 | 25 → 25 | 12 → 12 | 35 → 35 | 34,72 → 34,72 % |
| Paddle/LLM | 18 → 18 | 38 → 38 | 15 → 19 | 19 → 15 | 52,78 → 52,78 % |
| Docling | 9 → 9 | 19 → 19 | 6 → 6 | 47 → 47 | 26,39 → 26,39 % |

**Keine zusätzlichen exakten Treffer oder Teilnehmer im realen Vergleich.**
Alle bisherigen exakten Treffer bleiben erhalten, ebenso die maschinenschriftlichen
Paddle-Feldwerte der ersten Seite. Vier zusätzliche Organisationswerte auf Seite 2
stimmen nicht mit der Kursreferenz überein. Paddle-Precision sinkt von 71,70 auf
66,67 %, exakter F1 von 60,80 auf 58,91 %. Es gibt in beiden Varianten keine
zusätzlichen Personen oder zusätzlichen Referenzfelder. Mehr ausgefüllte Felder
sind hier ausdrücklich kein Qualitätsgewinn.

Paddle erkennt Überschriften auf Seite 1; die gemessenen elf Rasterintervalle der
zweiten Seite sind kompatibel, deshalb Herkunft `inherited_from_previous_page`
mit Quellseite 1. Die Intervalle schließen Rand-/Signaturbereiche ein; sie sind
nicht elf Teilnehmerattribute. Tesseract und Docling haben auf Seite 1 keine
eindeutigen Überschriftenbelege. Dort bleibt eine strukturelle Übernahme aus.
Docling bleibt bei neun unsicheren Teilpersonen auf Seite 1 und null auf Seite 2.

Zusätzlich wurde **dieselbe neue gespeicherte Paddle-Antwort** einmal mit und
einmal ohne geerbte Feldbänder validiert. Das isoliert den Einfluss der
Positionsprüfung von einer veränderten generativen Antwort:

| Identische Antwort | Exakt | Falsch | Fehlend | Precision | Exakter F1 |
| --- | --- | --- | --- | --- | --- |
| Ohne geerbte Positionsprüfung | 38 | 28 | 6 | 57,58 % | 55,07 % |
| Mit geerbter Positionsprüfung | 38 | 19 | 15 | 66,67 % | 58,91 % |

Die Prüfung verhindert damit netto **neun falsche Feldzuordnungen** gegenüber
dieser Ablation. Acht betroffene Benutzer-ID-Vorschläge auf Seite 2 werden
außerhalb ihrer belegten Spalte abgelehnt; ein weiterer Namensvorschlag wird
ebenfalls verworfen. Dies ist ein Sicherheitsnutzen der Strukturprüfung, kein
zusätzlicher korrekter Handschriftbefund und kein Gewinn gegenüber dem bisherigen
reparierten Ausgangsstand. Dieser besaß bereits weniger streng abgesicherte Hinweise.

Das unabhängige synthetische Zwei-Seiten-Beispiel in den Regressionstests steigt
ohne/mit Kontext von vier auf acht exakte Felder bei acht erwarteten Feldern
(Recall 50 → 100 %, eine zusätzliche Person, keine falschen Werte). Es belegt
die Funktionsfähigkeit bei geeigneter Struktur, keine reale OCR-Leistung.

Lokale Ergebnisse:

- `runs/document-columns-20261103-paddle/`: zwei neue lokale Text-LLM-Aufrufe,
  identische gespeicherte native OCR, exakte Prompts/Antworten und Modellidentität.
- `runs/document-columns-20261103-check/`: deterministische Layoutprüfung,
  Referenzvergleich und `check.json` mit unveränderten historischen Hashes.
- `runs/document-columns-20261103-final/comparison/report.html`: abschließende
  Auswertung mit geerbten Spalten; frischer Validierungs-Replay derselben Antwort.
- `runs/document-columns-20261103-ablation/comparison/report.html`: dieselbe
  Antwort ohne geerbte Positionsprüfung. Keine neue Inferenz.

Der neue Paddle-Zuweisungslauf benötigt lokal 719,40 s einschließlich Laden,
Warm-up und zwei Generierungen; zusätzlich 0,41 s für die Bildgeometrie.
Zuweisung pro Seite: 495,86 / 97,24 s. Modellladen 68,65 s, Warm-up 21,15 s;
weitere Initialisierung/Prüfsummen sind im Gesamtwert enthalten. PyTorch meldet
8,92 GiB maximale GPU-Allokation, ohne Treiber/andere Prozesse. System-RAM wurde
in diesem isolierten Zuweisungslauf nicht gesondert gemessen. Die GPU war parallel
belegt; dies ist kein belastbarer Geschwindigkeitsvergleich mit einem älteren Lauf.
Es gab **keine neuen OCR-/Strukturmodellaufrufe**, Downloads oder Trainings.
Der reine abschließende Validierungs-Replay benötigt 0,038 s, die Ablation 0,045 s.
Tesseract-Layoutkontrolle 0,418 s, deterministische Docling-Zuordnung 0,035 s.
Diese Stufenzeiten ersetzen keine vollständige OCR-Pipelinelaufzeit.

Beim Replay wurde außerdem ein veralteter Nachbearbeitungszustand sichtbar:
Namenszustände und Ausgabeindizes eines früheren Ergebnisses dürfen nicht auf
eine neue Zuweisung angewendet werden. `unlimited_reassign` und der Replay
archivieren diese Historie jetzt separat und erzeugen die Nachbearbeitung neu.

## 6. Tests und Reproduktion

Die Tests in `tests/test_document_columns.py` prüfen aktuelle Überschriften,
Fortsetzungen, Deckblatt, leere Zwischenseite, geänderte Breiten, neue Reihenfolge,
inkompatible Spaltenzahl/Geometrie, verbundene Zellen, Dokumentgrenzen,
Wiederholbarkeit und unsichere Teiltexte neben leeren Benutzerzellen.
Native- und HTML-Mapping sowie Tesseract-/Paddle-Kontext werden abgedeckt.
Die Beispiele sind synthetische Softwaretests, kein Nachweis realer OCR-Genauigkeit.

**627 lokale Volltests in 166,99 s und 48 API-Tests in 18,99 s bestanden.**
Die abschließende Korrektur alter Replay-Nachbearbeitung ist zusätzlich mit
**61 gezielten Tests in 13,45 s** geprüft. Ruff ohne Befund; JSON-, CSV- und
Excel-Zähler sowie unveränderte native OCR und maschinenschriftliche Werte geprüft.

Aus `software/`, jeweils mit einem **neuen** Ausgabeordner:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\api_firmen_pc\.venv\Scripts\python.exe -m pytest -q api_firmen_pc/tests
.\.venv\Scripts\python.exe -m participant_bench.cli assign-structures --run runs/handwriting-retention-20261103-final/source --config configs/benchmark.yaml --method paddle_llm --output runs/document-columns-paddle-neu --offline
.\.venv\Scripts\python.exe scripts/check_document_columns.py --source-report runs/handwriting-retention-20261103-final/comparison --paddle-run runs/document-columns-paddle-neu --output runs/document-columns-vergleich-neu
.\.venv\Scripts\python.exe scripts/replay_partial_assignments.py --source-report runs/document-columns-vergleich-neu/comparison --output runs/document-columns-final-neu
.\.venv\Scripts\python.exe scripts/replay_partial_assignments.py --source-report runs/document-columns-vergleich-neu/comparison --output runs/document-columns-ablation-neu --without-inherited-columns
```

`check_document_columns.py` lädt kein Modell. Es prüft historische Dateihashes,
verarbeitet Docling deterministisch neu und übernimmt ausschließlich einen separat
protokollierten Paddle-Zuweisungslauf derselben OCR-Belege. Tesseract bleibt in
diesem realen Vergleich unverändert, solange keine zuverlässigen Überschriften
erkannt werden. Neue LLM-Eingaben dürfen nicht stillschweigend als bereits getestet
gelten. Historische Ergebnisse werden nicht überschrieben.
