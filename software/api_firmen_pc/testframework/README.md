# Teilnehmerlisten über die API testen und mit Excel/CSV vergleichen

Dieses Testframework verwendet dieselbe Bewertung wie `software/testframework/`.
Auf dem Firmen-PC werden die Teilnehmer über die konfigurierte API ausgelesen;
Schulungszuordnung, Personenabgleich und Kennzahlen werden anschließend lokal
berechnet. Die Referenzdatei wird vor der Inferenz eingefroren und keinem Modell
übergeben. Eingabedateien werden nicht verändert.

## Start auf dem Firmen-PC

Alle Befehle aus `software/api_firmen_pc/` ausführen:

```powershell
uv sync --locked
```

1. PDFs nach `testframework/eingabe_pdfs/` kopieren. Unterordner sind erlaubt.
2. Genau eine XLSX oder CSV nach `testframework/referenz/` legen.
3. Optional ohne Zugangsdaten oder Serverkontakt prüfen:

   ```powershell
   .\start_api_testframework.cmd --pruefen
   ```

4. In einer separat geöffneten PowerShell starten:

   ```powershell
   .\start_api_testframework.cmd
   ```

Der Starthelfer fragt Zugangsdaten verdeckt und den VLM-Modellnamen normal ab.
Die Werte werden nur im Startprozess und dessen Kindprozessen gesetzt und nach
dem Lauf entfernt. Eine externe Zugangsdaten-Datei bleibt über den vorhandenen
PowerShell-Helfer ausdrücklich wählbar; es wird keine `.env` automatisch gesucht.
Die Unternehmensverbindung muss auf dem Firmen-PC freigeschaltet sein. Dafür gelten
dieselben Voraussetzungen wie bei der normalen [API-Verarbeitung](../README.md).

## Eingaben und Bewertung

`123456.pdf` gehört zu `Class ID = 123456`. Die Referenz darf mehrere Schulungen
enthalten. Bewertet werden die Kurse mit Eingabe-PDF; andere Referenzkurse werden
gesondert gezählt. Standardspalten sind `Class ID`, `User ID`, `First Name`,
`Last Name` und `Organization`. Die tatsächlichen Referenzüberschriften und deren
Reihenfolge werden in den Excel-Ergebnisexport übernommen.

Die Zeilenreihenfolge spielt keine Rolle: Innerhalb einer Schulung erfolgt eine
globale Zuordnung, bei der jede Vorhersage und Referenzperson höchstens einmal
Punkte erhalten. Leere oder maskierte IDs verhindern die Zuordnung über Namen
und Kurzzeichen nicht. Standard ist `matching.mode: best_fit`: möglichst viele
lesbare Zeilen werden gepaart und die Summe aller bewertbaren Feldähnlichkeiten
wird maximiert. Schwache und mehrdeutige Paarungen bleiben mit Prüfhinweisen
erhalten. Das ist keine bestätigte Personenidentität. Der konservative Score
mit den bisherigen Mindestgrenzen steht zum Vergleich daneben. Mit
`--matching-mode conservative` lässt sich die bisherige Variante auswählen;
`--matching-mode best_fit` wählt die neue Variante ausdrücklich.

Der Bericht zeigt Levenshtein-Feld-F1 mit Teilpunkten für ähnliche Schreibweisen,
exakte Feldtreffer, fehlende und zusätzliche Teilnehmer sowie Werte je Feld und
Schulung. Ein Score misst Referenzübereinstimmung und keine Wahrscheinlichkeit.
Die Bewertungsregeln und Ausschlüsse entsprechen dem lokalen Testframework.
Die Kursreferenz enthält keine Unterschriften-Ground-Truth; zusätzliche visuelle
Signaturprüfungen sind für den Benchmark standardmäßig deaktiviert.

## Ergebnisse

Vor jedem Namensvergleich wird die Referenz auf dieselbe `Class ID` wie die
Schulungs-ID im PDF-Dateinamen begrenzt. Einträge anderer Klassen sind auch bei
identischen Namen oder IDs ausgeschlossen. Ohne passende Referenzklasse gibt es
keine ersatzweise kursübergreifende Suche. Der Namensreport weist die Klassen-ID
und die Anzahl der zulässigen Kandidaten pro Ausgabe aus.

Der gemeinsame Extraktionsablauf schließt ausdrücklich erkannte Kursleiter,
Trainer und Dozenten vor dem Teilnehmerexport aus. Der Vergleich zählt diese
Ausschlüsse separat; `excluded_instructors.csv` im Extraktionslauf enthält die
Begründungen. Unklare Rollen bleiben zur manuellen Prüfung erhalten. Die
Referenzdatei wird dabei niemals durch Modellvorhersagen geändert.

Auch die Vor-/Nachnamenszuordnung verwendet eine dokumentweite Modellentscheidung
aus den PDF-/OCR-Belegen. Ihr Kontext bleibt auf dieselbe PDF beschränkt;
Folge- und Kopfzeilen anderer Dokumente werden nicht übernommen. Die Entscheidung
steht im Extraktionsreport und in `document_name_orders.csv`. Die Referenz wird
dem API-Modell weiterhin nicht übermittelt. Für die Namensentscheidung entsteht
kein zusätzlicher API-Aufruf; sie gehört zur regulären Seitenantwort.

Die Extraktion liegt unter `runs/<RUN_ID>/`. Der Vergleich entsteht separat unter
`testframework/ergebnisse/<VERGLEICHS_ID>/`, einschließlich `report.html`,
`summary.csv`, `field_scores.csv`, `fields.csv`, `participants.xlsx`,
`reference_snapshot.json` und `identity.json`. Der Bericht verlinkt die Extraktion
mit Seitenbildern und Rohantworten. Alle Referenzen und Ergebnisse bleiben lokal;
API-Anfragen enthalten nur die zu analysierenden PDF-Seiten bzw. OCR-Texte.

`details.html` erklärt jede Paarung, Feldabweichung, Edit-Distanz und Teilpunktzahl
mit sämtlichen Nennerbeiträgen. Unterseiten pro Modell/Schulung zeigen auch die
Referenzkandidaten und abgelehnte Zuordnungen. Suche und Filter laufen im Browser
ohne Netzwerk. Ältere Vergleiche ohne Zugangsdaten oder API-Aufrufe ergänzen:

```powershell
.\.venv\Scripts\python.exe main.py benchmark details --report testframework/ergebnisse/DEINE_VERGLEICHS_ID
```

Der separate Namensreport `zuordnungen.html` stellt erkannte Namen und zugeordnete
Referenznamen direkt gegenüber. Er zeigt den Entscheidungsgrund, lokale
Kandidatenränge, Ähnlichkeiten, globale Alternativen und die tatsächliche Vergabe
aller anderen Referenzkandidaten. Fehlende, zusätzliche und prüfpflichtige Namen
bleiben sichtbar. Suche und Filter benötigen keine Verbindung. Der Report entsteht
automatisch; für vorhandene Vergleiche separat erzeugen, ohne API-Zugangsdaten:

```powershell
.\.venv\Scripts\python.exe main.py benchmark assignments --report testframework/ergebnisse/DEINE_VERGLEICHS_ID
```

Die gespeicherten Kennzahlen und Referenzdateien bleiben unverändert. Eine
Diagnose vertauschter Namensfelder korrigiert keine Modellwerte automatisch.

## CLI und andere Modelle

Nach Laden der Zugangsdaten in einer separaten PowerShell:

```powershell
. .\scripts\set-api-environment.ps1
.\.venv\Scripts\python.exe main.py benchmark run
```

Gleichwertiger Einstieg: `.\.venv\Scripts\python.exe testframework/main.py run`.
Andere Eingaben und Referenz wählen:

```powershell
.\.venv\Scripts\python.exe main.py benchmark run --input "data/meine_pdfs" --reference "data/referenz.xlsx"
```

Standardmäßig läuft nur das API-VLM aus `configs/api-bmw.yaml`; es benötigt keine
lokalen Modelle, Tesseract, PyTorch oder CUDA. Der Modellname steht in
`BMW_VLM_MODEL`. Für OCR mit anschließender API-LLM-Auswertung ist zusätzlich
lokales Tesseract nötig. In derselben separaten PowerShell `BMW_LLM_MODEL` auf
den intern freigeschalteten Textmodellnamen setzen und starten:

```powershell
$env:BMW_LLM_MODEL = 'DEIN_INTERNES_TEXTMODELL'
.\.venv\Scripts\python.exe main.py benchmark run --extraction-config configs/api-ocr.yaml --method ocr_llm --method vlm
```

Den Modellnamen erst auf dem Firmen-PC setzen; API-Keys bleiben weiterhin in den
Umgebungsvariablen. Weitere Modelle durch einen eigenen Extraktionsprofilpfad
und `--extraction-config` auswählen. Es gibt keine automatischen Modellwechsel.

Ein unveränderter abgebrochener Lauf kann mit `benchmark run --resume runs/<RUN_ID>`
fortgesetzt werden. Bereits gespeicherte lokale oder API-Ergebnisse neu bewerten,
ohne Inferenz und ohne Zugangsdaten:

```powershell
.\.venv\Scripts\python.exe main.py benchmark compare --run runs/DEINE_RUN_ID
```

`benchmark check` prüft PDF-/Referenzdaten ohne Zugangsdaten und Netzwerk. Der
ursprüngliche Einstieg `software/testframework/main.py` bleibt auf dem lokalen
GPU-Laptop ausschließlich offline.
