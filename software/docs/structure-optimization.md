# Docling und PaddleOCR: Fehleranalyse und Vergleich

Stand: 02.11.2026. Die Änderungen betreffen das vorhandene Framework und seine
beiden Strukturverfahren. Es wurde kein zusätzliches LLM/VLM eingeführt.
Dokumente, Gewichte, Rohantworten und Bild-Overlays bleiben lokal und gitignoriert.

## Ursache und Änderung

Bei Docling sind zwei Fehlerbilder zu unterscheiden. In synthetischen Dokumenten
sind Organisationswerte und Überschriften vorhanden, die frühere HTML-Zuordnung
übernimmt sie jedoch nicht: `column_mapping_failed`. Das neue Mapping arbeitet
direkt mit TableFormer-Zellen, ihren Spalten, Zeilen und Spannweiten. Es erhält
explizit leere Zellen und unvollständige Personen. Auf der realen PDF fehlen
dagegen verwertbare erkannte Überschriften. Eine sichere deterministische
Feldzuordnung ist dadurch blockiert. Aus fehlendem OCR-Text lässt sich ohne
regionale Referenz weder `ocr_detection_failed` noch `ocr_recognition_failed`
eindeutig ableiten; diese OCR-Ursache bleibt unbekannt.

Paddles historische erste Seite enthält Organisationswerte in OCR/Zellbelegen,
die damalige LLM-Antwort liefert aber keine Abteilungen: Dort ist ein Verlust
bei der LLM-Zuordnung belegt. Die erweiterte Übergabe enthält Zelltext,
Koordinaten, OCR-Konfidenzen, Überschriftenrollen und Tabellenbeziehungen.
Mehrdeutige Organisationsspalten werden ausdrücklich zurückgewiesen.
Weder ein vorhandener Wert noch eine hohe OCR-Konfidenz beweist eine korrekte
semantische Zuordnung. Vor- und Nachvalidierungsstände bleiben im Roh-JSON.

Das Datenschema besitzt ein Organisationszielfeld (`department`), im
Excel-Vergleich `Organization` beziehungsweise `short_code`. Für diesen
Datensatz meint es das Kurzzeichen. Organisations- und Abteilungsspalten mit
unterschiedlicher Bedeutung werden bei gleichzeitigem Auftreten als mehrdeutig
markiert. Es gibt keine allgemeine fachliche Gleichsetzung dieser Begriffe.

## Aktives Profil und erhaltene Baseline

| Einstellung | Baseline | Hauptprofil seit 02.11.2026 |
| --- | --- | --- |
| Docling-Zuordnung | `legacy_html` | native Zellen, `structured` |
| TableFormer | ACCURATE | ACCURATE |
| Cell Matching | an | aus |
| OCR | Tesseract CLI, PSM 6, deu+eng | gleich |
| Full-Page-OCR | aus | aus |
| OCR-Skalierung | 3,0, effektiv 216 DPI | gleich |
| Paddle-Übergabe | `legacy_v13` | `legacy_v13`; geprüfter Kandidat separat |
| Textmodell für Paddle | Qwen3-4B-Instruct-2507 | identisch |
| Signaturprüfung | konservatives OpenCV | identisch |

Hauptprofil: [benchmark.yaml](../configs/benchmark.yaml). Gegenprobe:
[structures-baseline.yaml](../configs/structures-baseline.yaml).
Organisationstitel sind konfigurierbar, ohne feste Spaltennummern oder Pixelwerte.
Überschrift und Positionsbelege werden protokolliert. Unbekannte Überschriften
führen zu einem Prüffall; der originale Zellinhalt bleibt erhalten.

Paddles erweiterte Übergabe wird über
[paddle-positioned.yaml](../configs/paddle-positioned.yaml) aktiviert. Sie war
während des A/B-Laufs eingeschaltet, wurde nach der gemessenen Regression
jedoch aus dem Hauptprofil zurückgenommen. Dieses enthält je Verfahren exakt
die separat praktisch geprüften Einstellungen: optimiertes Docling und bisherige
Paddle-Übergabe. Die beiden eingefrorenen Laufkonfigurationen bleiben erhalten.

Die exakte Textmodellrevision `cdbee75f17c01a7cc42f958dc650907174af0554`
wurde heruntergeladen und über zwölf SHA256-Dateieinträge verifiziert. Echte
lokale CUDA-Inferenz ist erfolgt. Das ältere `models/qwen3-4b` ist ein anderes
Modell und wurde nicht umbenannt. Modellparameter: BF16 und
`sdpa_repeated_kv`, keine Quantisierung oder CPU-Auslagerung. Inferenz läuft
sequenziell auf der vorhandenen GPU mit 16 GiB VRAM.

## Vollständiger Docling-Variantenvergleich

Identische vier synthetische Entwicklungs-PDFs, vier Seiten, sieben Personen.
Enthalten sind wechselnde Überschriften/Spalten, eine leicht gedrehte Rasterseite,
leere Zellen, ein Organisationswert außerhalb der Tabelle und simulierte
Schreibschrift. Letztere ist **keine echte Handschrift**. Die Referenz wurde
unabhängig von den Vorhersagen erzeugt.

| Native Zuordnung | Textfelder exakt | Organisation exakt | Organisations-CER | Datensätze exakt | Laufzeit gesamt |
| --- | --- | --- | --- | --- | --- |
| ACCURATE, Matching an | 14/28 | 2/7 | 0,50 | 2/7 | 35,2 s |
| ACCURATE, Matching aus | 16/28 | 4/7 | 0,50 | 4/7 | 21,1 s |
| FAST, Matching an | 14/28 | 2/7 | 0,50 | 2/7 | 25,4 s |
| FAST, Matching aus | 16/28 | 4/7 | 0,50 | 4/7 | 31,3 s |
| ACCURATE, Matching an, Full-Page-OCR | 14/28 | 2/7 | 0,50 | 2/7 | 25,2 s |

Jeweils vier von sieben Personen wurden zugeordnet. Native Zuordnung ohne
Matching bewahrt zwei korrekt leere Organisationsfelder zusätzlich. Von den
vier **nichtleeren** Referenzorganisationen werden zwei korrekt gelesen; deren
Erkennungsrate ist 50 %. Die normalisierte Zeichendistanz der Textfelder sinkt
gegenüber dem HTML-Replay von 0,526 auf 0,437. Die HTML-Zuordnung erreicht bei
identischen OCR-Belegen in allen Varianten 12/28 Textfelder und 0/7 Organisationen.

ACCURATE ohne Cell Matching wird anhand dieser Entwicklungsfälle gewählt.
FAST liefert hier dieselbe Qualität, jedoch keinen belegten Laufzeitvorteil.
Einzellaufzeiten einschließlich Laden und Cacheeffekten sind kein belastbarer
Durchsatzvergleich. Full-Page-OCR liefert keinen zusätzlichen Qualitätsgewinn
und bleibt optional, um vorhandenen korrekten PDF-Text zu erhalten.

Alle fünf Varianten sind abgeschlossen. Lokale Ergebnisse:
`runs/structure-20261102/report.html`, `quality_comparison.csv`,
`mapping_comparison.csv`, feldweise CSVs und `identity.json` mit
`completed: true`. Eine vorzeitig beendete ältere Matrix bleibt separat erhalten.

## Praktischer Vorher-/Nachher-Nachweis

Die vier tatsächlichen Läufe stehen in
`runs/structure-acceptance-20261102/runs.json`. Sie verwenden dieselben
Eingabe-PDFs, dieselben gemeinsamen Einstellungen und dasselbe exakte Textmodell.
Die Referenz wird ausschließlich nach der Extraktion verwendet.

Synthetische Entwicklung, sieben Personen:

| Verfahren/Variante | Textfelder exakt | Organisation exakt | Datensätze exakt | Zugeordnet | Zusatzzeilen | tatsächliche Zeit |
| --- | --- | --- | --- | --- | --- | --- |
| Docling bisher | 12/28 | 0/7 | 0/7 | 4/7 | 0 | 17,6 s |
| Docling nativ, Matching aus | 16/28 | 4/7 | 4/7 | 4/7 | 0 | 41,3 s |
| Paddle bisher | 18/28 | 2/7 | 2/7 | 6/7 | 1 | 173,7 s |
| Paddle erweiterte Übergabe | 16/28 | 2/7 | 2/7 | 5/7 | 1 | 165,1 s |

Paddle verliert im gedrehten Entwicklungsfall eine Person, weil das LLM auf
eine nicht personenbezogene Quellzeile verweist. Der Validator weist diese
Zuordnung zurück; die OCR-Zeilen bleiben als nicht zugeordnet erhalten. Die
zusätzlichen Positionsinformationen liefern hier keinen Qualitätsgewinn.
Ein pauschal verbessertes Paddle-Ergebnis wäre durch diese Daten widerlegt.

Reales zweiseitiges Dokument, dieselben 18 Kursreferenzpersonen:

| Verfahren/Variante | Textfelder exakt | Organisation exakt | Datensätze exakt | Zugeordnet | tatsächliche Zeit |
| --- | --- | --- | --- | --- | --- |
| Docling bisher | 0/72 | 0/18 | 0/18 | 0/18 | 46,4 s |
| Docling nativ, Matching aus | 0/72 | 0/18 | 0/18 | 0/18 | 47,5 s |
| Paddle bisher | 29/72 | 3/18 | 3/18 | 9/18 | 269,2 s |
| Paddle erweiterte Übergabe | 29/72 | 3/18 | 3/18 | 9/18 | 265,1 s |

Keine zusätzlichen Personen im realen Vergleich. Beide Paddle-Varianten liefern
dieselben korrekten und inkorrekten Referenzfelder. Gepaarte Text-CER: 0,5033,
normalisierte Zeichendistanz: 0,5022, Levenshtein-Soft-F1: 0,6489. Docling liegt
wegen der fehlenden Zuordnungen bei CER und Zeichendistanz jeweils 1,0. Diese
Zeichendistanzen bewerten extrahierte Teilnehmerfelder gegen die Kursreferenz;
sie sind keine Messung sämtlicher OCR-Wörter auf der PDF-Seite.

Paddle gibt auf Seite 1 neun Personen und auf Seite 2 keine Personen aus.
Auf Seite 2 sind 26 OCR-Belege, aber keine rekonstruierte Tabelle gespeichert.
Das belegt ein Strukturproblem und fehlende Zuordnungen; ohne manuell
markierte Textregionen ist die zusätzliche OCR-Ursache unbekannt.
Auf der realen PDF ist **für beide Verfahren kein Qualitätsgewinn gemessen**.

Auch zwei zusätzliche Docling-Prüfungen bleiben bei null zugeordneten Personen:
PSM 11 bei Standard-OCR (47,1 s) und Full-Page-OCR bei deaktiviertem Cell Matching
(47,7 s). In beiden Varianten fehlen weiterhin erkennbare Spaltenüberschriften.
Sie werden daher nicht zur Standardeinstellung und nicht als Handschriftlösung
ausgegeben. Lauf-/Diagnoseverweise: `docling_followups.json` im Vergleichsordner.

Lokaler detaillierter Kursvergleich:
`runs/structure-acceptance-20261102/real-comparison-v2/report.html`.
Er enthält Feldwechsel, fehlende Personen, Zeichendistanzen und die nachträglichen
Einzelvergleiche. Die ursprüngliche erste Auswertung bleibt zusätzlich erhalten.
`real-baseline-diagnosis/report.html` und `real-optimized-diagnosis/report.html`
zeigen die vollständigen Stufen und Overlays; entsprechende Diagnoseordner
existieren für die synthetischen und zusätzlichen OCR-Läufe.

Tatsächliche und zugerechnete vollständige Zeit stehen getrennt in CSV/JSON.
Paddles reale vollständige zugerechnete Zeit beträgt 271,9 s vorher und 287,8 s
für den Kandidaten. Unterschiedliche Lade-/Cachekosten erlauben keine
Geschwindigkeitsbehauptung aus diesem Einzellauf. Maximale gemessene
GPU-Allokation des realen Paddle-Kandidaten: etwa 9,05 GiB; Docling: 0,56 GiB.

## Handschrift und Grenzen

Der Nutzer hat `testframework/eingabe_pdfs/140829.pdf` benannt. Das Original
bleibt unverändert; eine hashgleiche isolierte Arbeitskopie liegt unter
`data/structure-real-20261102/pdfs/`. Die vorhandene Excel-Kursreferenz enthält
18 Personen für diese Klassen-ID. Sie erlaubt einen Vergleich des gesamten
zweiseitigen Dokuments. Ohne unabhängig geprüfte Seitentranskripte und
Seitenzuordnung erlaubt sie **keinen separaten Handschrift-Recall oder
OCR-CER der Handschriftseite**. Bedingte Trefferwerte einer zugeordneten
Vorhersageseite haben einen anderen Nenner.

Eine leere manuelle Referenzvorlage liegt unter
`data/handwriting-review-20261102/`. Sie wurde mit `ocr-reference` erstellt;
es wurden keine Modellvorhersagen als Ground Truth übernommen. Für belastbare
Handschriftmessungen sind manuelle Transkripte und weitere unabhängig getrennte
Dokumente erforderlich. Unsichere Namen, IDs und Organisationen werden nicht
erraten. Docling erhält keinen versteckten Paddle-/LLM-/VLM-Korrekturschritt.

## Reproduzieren

Aus `software/`, mit eingerichteten bestehenden uv-Umgebungen:

```powershell
.\.venv\Scripts\python.exe scripts/make_structure_diagnostics.py --output data/struktur-entwicklung-neu
.\.venv\Scripts\participant-bench.exe structure-experiment --input data/struktur-entwicklung-neu/pdfs --config configs/benchmark.yaml --output runs/struktur-matrix-neu --ground-truth data/struktur-entwicklung-neu/ground_truth.jsonl --include-full-page-ocr
.\.venv\Scripts\participant-bench.exe run --input data/struktur-entwicklung-neu/pdfs --config configs/structures-baseline.yaml --ground-truth data/struktur-entwicklung-neu/ground_truth.jsonl --offline
.\.venv\Scripts\participant-bench.exe run --input data/struktur-entwicklung-neu/pdfs --config configs/benchmark.yaml --method docling --ground-truth data/struktur-entwicklung-neu/ground_truth.jsonl --offline
.\.venv\Scripts\participant-bench.exe run --input data/struktur-entwicklung-neu/pdfs --config configs/paddle-positioned.yaml --ground-truth data/struktur-entwicklung-neu/ground_truth.jsonl --offline
.\.venv\Scripts\python.exe scripts/compare_structure_runs.py --baseline runs/BEFORE --optimized runs/AFTER --reference testframework/referenz/143754Completions.xlsx --output runs/strukturvergleich-neu
```

`--method` wählt genau ein Verfahren; ohne diese Option gelten die Verfahren
des jeweiligen Profils. Für einen Kursvergleich müssen die PDF-Dateinamen zur Klassen-ID der Referenz
passen. Das Vergleichsskript prüft identische Eingabeseiten/Bild-Hashes,
gemeinsame Vorverarbeitung und Textmodellparameter, friert die Referenz einmal
ein und schreibt Feldübergänge, Exact Match, Datensatztreffer und Zeichendistanzen.
Best-Fit-Zuordnung anhand der Kursreferenz ist keine unabhängige Identitätsprüfung.
Die gepaarte CER schließt zusätzliche Vorhersagen aus; die gewöhnlichen
PRF-Metriken bestrafen diese separat. Überzählige Ausgaben bleiben sichtbar.

```powershell
.\.venv\Scripts\participant-bench.exe diagnose-structures --help
.\.venv\Scripts\participant-bench.exe run --input data/pdfs_eingabe --config configs/docling-full-page.yaml --offline
.\.venv\Scripts\participant-bench.exe run --input data/pdfs_eingabe --config configs/docling-sparse.yaml --offline
```

Die Sparse-Variante ändert ausschließlich Tesseracts Segmentierung auf PSM 11.
Sie bleibt ein gesonderter diagnostischer Versuch. Die Diagnose speichert
Tabellen/OCR mit Koordinaten, erkannte Überschriften, Zuordnungsbelege,
Normalisierungsstände und Overlays. Bei nicht belegbaren Ursachen steht unbekannt.

Die historischen Berichte vom 29.10.2026 verwendeten teils Docling plus LLM.
Sie bilden keine faire numerische Baseline für den heutigen deterministischen
Docling-Vergleich. Der neue Vorher-/Nachher-Nachweis erhält beide Varianten.

Abschließende Softwareprüfung am 02.11.2026: **544 lokale Tests und 48 API-Tests
bestanden**, Ruff und Dateiverweise ohne Befund. Einstiegsbericht für alle
lokalen Ergebnisse: `runs/structure-acceptance-20261102/report.html`.
