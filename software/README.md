# Teilnehmerlisten lokal evaluieren

Dieser Softwareteil liegt unter `software/`. **Alle folgenden Befehle aus diesem
Ordner ausführen** (`cd software` vom Repository-Hauptordner). Die schriftliche
LaTeX-Arbeit liegt unabhängig davon unter `../bachelorarbeit/`.
Vorhandene Berichte sind mit umgezogen; historische absolute Pfade bleiben als
Provenienz erhalten. Hinweise zu neuen Manifesten: [Repository-Umstellung](docs/repository-layout.md).

Ausführbarer Forschungsprototyp für den lokalen Vergleich von strukturierter
Informationsextraktion aus Teilnehmerlisten. Extrahiert Vorname, Nachname,
Personalnummer und Abteilung sowie ausschließlich die Anwesenheit einer
Unterschrift. Kein Datum, keine Unterschriftentranskription, keine Identitäts-
oder Echtheitsprüfung und kein Import in ein Schulungssystem.

Dieser Projektteil führt die Dokumentanalyse lokal aus. Die API-Verarbeitung
für den Firmen-PC liegt separat unter [`api_firmen_pc/`](api_firmen_pc/README.md)
mit eigener Umgebung und eigenem Einstieg. Zugangsdaten sind hier nicht nötig.
**Ohne Ground Truth
wird keine Extraktionsqualität behauptet.** Die Ausgaben dienen menschlicher
Kontrolle und Korrektur. Reale Formulare müssen noch auf Development-Daten
angepasst und unabhängig auf Testdaten evaluiert werden.

## Zwei getrennte Schritte

| Bereich | Aufgabe | Einstieg |
| --- | --- | --- |
| [`vorverarbeitung/`](vorverarbeitung/README.md) | Eingabeordner rekursiv durchsuchen, nur PDFs kopieren und nach Dokumentnummer umbenennen | `vorverarbeitung/vorbereiten.py` |
| [`verarbeitung/`](verarbeitung/README.md) | Seiten aufbereiten, Teilnehmerlisten extrahieren und evaluieren | `participant-bench`, Quellcode unter `verarbeitung/src/participant_bench/` |

Später die Dokumentordner unter **`../dateien/`** im Repository-Hauptordner
ablegen. Beispiel: `../dateien/München/12473.123456_12.23.1456_Muc.pdf` wird
zu `vorverarbeitung/ausgabe/pdfs/123456.pdf`. Alle gültigen PDFs landen direkt
in diesem Zielordner. Führende Nullen und Originaldateien bleiben erhalten.
Die ID muss genau **sechs Ziffern** enthalten. PDFs mit einer kürzeren, längeren,
fehlenden oder ungültigen ID werden mit Originalnamen direkt nach
`vorverarbeitung/ausgabe/nicht_erfuellt/` kopiert.
Auch ein Leerzeichen beendet die ID: `12473.123456 12.23.1456_Muc.pdf`
wird ebenfalls zu `123456.pdf`.
Auch `12473_123456_…`, `01.12473.123456_…` und `12473. 123456_…`
werden als ID `123456` erkannt.
Bei `101158 - 174563 - 09.09.2026 MUC.pdf` wird die zweite Zahl verwendet:
Die Ausgabe heißt `174563.pdf`.

Die Vorverarbeitung benötigt Python ab Version 3.12 und PyMuPDF, keine OCR oder Modelle:

```powershell
.venv/Scripts/python.exe vorverarbeitung/vorbereiten.py --dry-run
.venv/Scripts/python.exe vorverarbeitung/vorbereiten.py
```

`--dry-run` prüft die geplanten Kopien ohne Schreibzugriffe. Echte Läufe erzeugen
JSON-/CSV-Protokolle unter `vorverarbeitung/ausgabe/protokolle/`.
PDF-Anmerkungen wie Textmarker und Kommentare werden aus den Arbeitskopien
entfernt. Jede Quelldatei erhält unter `vorverarbeitung/ausgabe/vergleich/` einen
eigenen Ordner mit dem Original unter seinem echten Namen und der bearbeiteten
Version `<ID>_bearbeitet.pdf`. Die Modelleingaben liegen zusätzlich unter `pdfs/`.
Identische bereinigte Ziele werden übersprungen. Frühere bytegleiche Originalkopien
werden nach der Sicherung bereinigt; abweichende Ziele bleiben erhalten. Aussortierte
PDFs werden mit dem Grund protokolliert. Konflikte und technische Fehler werden
durch Exitcode 1 angezeigt.

Anschließend die gesammelten PDFs verarbeiten (nach der Installation):

```powershell
uv run --offline --locked --extra models participant-bench run --input vorverarbeitung/ausgabe/pdfs --config configs/imported.yaml --offline
```

Die bisherigen Befehle und eigenen Eingaben unter `data/raw` funktionieren
weiterhin. Nach der Quellcode-Umstellung einmal `uv sync --locked --extra models`
ausführen, damit die Paketinstallation den neuen Verarbeitungsordner verwendet.

## Installation mit uv

Im Projektverzeichnis, Windows PowerShell, einmalig mit Internetzugang:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
Set-Alias uv (Join-Path $PWD '.tools\uv.exe')
$env:UV_CACHE_DIR = Join-Path $PWD '.cache\uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PWD '.tools\python'
uv sync --locked --extra models
uv run --locked --extra models python scripts/setup_ocr.py
uv run --locked --extra models participant-bench doctor
uv run --locked --extra models participant-bench download-models --config configs/local.yaml --transport range
```

Bereits installiertes `uv` kann direkt verwendet werden. `bootstrap.ps1` lädt
uv 0.13.1 portabel; Python 3.12.15 und `.venv` werden ausschließlich mit uv
verwaltet. Keine globale pip-Installation. `uv.lock` ist die maßgebliche
Auflösung. `--extra models` installiert die festgelegten Modellabhängigkeiten.
Für A allein genügt `uv sync --locked` plus Tesseract und `configs/smoke.yaml`.
Ein späteres `uv sync --locked` ohne Extra entfernt Modellpakete wieder;
für B/C daher beim Synchronisieren das Extra angeben.

Tesseract ist ein separates Systemwerkzeug. Das Setup entpackt den in der
Tesseract-Dokumentation genannten UB-Mannheim-Build 5.4.0 ausschließlich nach
`.tools/ocr`, ohne den Installer auszuführen. Auch 7-Zip wird nur lokal entpackt.
Deutsch, Englisch und OSD stammen aus einer festgeschriebenen tessdata_fast-
Revision. Herkunft und Hashes stehen in `.tools/ocr/setup_manifest.json`.
Linux: Tesseract samt `deu`, `eng`, `osd` über den Systempaketmanager bereitstellen;
der Python-Kern unterstützt Windows/Linux, das OCR-Setupskript ist für Windows.

Der Modell-Download ist **ein expliziter Setup-Schritt**. Der Standardtransport
ohne `--transport range` verwendet Hugging Face `snapshot_download`. In der
Entwicklungsumgebung hing der große Standarddownload; der Bereichstransport
funktioniert und ist wiederaufnehmbar. Einzelne Modelle: `--method vlm` oder
`--method ocr_llm`. Beide laden feste Revisionen, Konfigurationen und Tokenizer
in `models/`. Unvollständige Gewichte sind `unavailable`. Es wird kein anderes
Modell als Ersatz ausgeführt.

## Getrennte Rechner: lokal und Firmen-API

Für den vorhandenen Testordner genügt ein Doppelklick auf
[`start_lokal_cv_test.cmd`](start_lokal_cv_test.cmd). Die Datei verarbeitet
ausschließlich alle PDFs unter `data/cv-test-20261020-093337/`, einschließlich
Unterordnern, mit den lokalen Verfahren OCR/Regeln, OCR/LLM und VLM. Weitere
PDFs einfach dort hinzufügen. Der Start funktioniert unabhängig vom aktuellen
Terminalordner; das Fenster bleibt am Ende offen. Jeder Start erzeugt einen
neuen Lauf unter `runs/`. `start_lokal_cv_test.cmd --pruefen` zählt lediglich
die PDFs, ohne Modelle zu starten.

| Rechner | Projektordner | Einstieg |
| --- | --- | --- |
| Laptop mit GPU (Vergleichslauf) | `software/` | `.venv/Scripts/participant-bench.exe run --input PFAD_ZUM_GLEICHEN_PDF_ORDNER --config configs/vlm-comparison.yaml --offline` |
| Firmen-PC (Vergleichslauf) | `software/api_firmen_pc/` | `.venv/Scripts/python.exe main.py run --input PFAD_ZUM_GLEICHEN_PDF_ORDNER --config configs/api-bmw.yaml` |

Der [Firmen-PC-Ordner](api_firmen_pc/README.md) enthält API-Code, OAuth-Konfiguration,
Starthelfer, eigene Lockdatei und Tests. Er installiert keine lokalen LLM-/VLM-Gewichte.
Ein gezielter ZIP-Export überträgt die benötigten Quellen ohne Daten und Modelle.
Für Vergleichsläufe verwenden beide Rechner dieselben PDFs und die beiden
VLM-only Profile; `configs/local.yaml` bleibt für den normalen lokalen
Mehrmethodenlauf vorgesehen. Details und Hash-Prüfung der Eingabeseiten stehen
in der Anleitung zum [fairen Modellvergleich](api_firmen_pc/README.md#lokaler-laptop-und-fairer-modellvergleich).
Das frühere `test_url/` liegt unverändert und von Git ausgeschlossen unter
`api_firmen_pc/privat/test_url/`; die neue Startdatei verwendet nur Umgebungsvariablen.
Die Ergebnisformate, Berichte und der Excel-Abgleich sind in beiden Wegen identisch.
API-Kommandos wie `check` gibt es ausschließlich im Firmen-PC-Projekt.

## OCR anhand geprüfter Referenzen optimieren

Als zusätzlicher lokaler Ansatz steht [Unlimited-OCR](docs/unlimited-ocr.md)
mit eigener, versionsgetrennter Laufzeit zur Verfügung. Zum Start im vorhandenen
CV-Testordner `start_unlimited_cv_test.cmd` verwenden. Es bewahrt die rohe
OCR-Antwort und ordnet erkannte Tabellenzellen ohne Namenskorrektur zu.
Reine OCR und strukturierte Extraktion werden separat bewertet. `ocr_rules`
bleibt als transparente Tesseract-/Regel-Baseline im Vergleich erhalten.

Die neue [Kalibrierungsanleitung](docs/ocr-calibration.md) beschreibt eine lokale
CSV-Annotation, gruppierte 60/20/20-Aufteilung, kontrollierte OCR-Varianten,
CER/WER, Feld-/Zeilen-/Signaturmetriken, feldweise Sigmoid-/Isotonic-Kalibrierung
und eine separat gesperrte finale Testbewertung. API-Modelle sind in diesen
Befehlen gesperrt. Grundlegender Ablauf:

```powershell
.venv/Scripts/participant-bench.exe ocr-reference --input vorverarbeitung/ausgabe/pdfs --output data/ocr-reference-v1 --sample-documents 100
# documents.csv, pages.csv, participants.csv und optional Referenztext manuell prüfen.
.venv/Scripts/participant-bench.exe ocr-split --dataset data/ocr-reference-v1
.venv/Scripts/participant-bench.exe ocr-calibrate --dataset data/ocr-reference-v1 --config configs/calibration.yaml --output runs/ocr-exp01
.venv/Scripts/participant-bench.exe ocr-final --experiment runs/ocr-exp01
```

Die finale Testbewertung erst nach abgeschlossener Kalibrierung starten. Ohne
ausreichende unabhängige Evidenz wird keine Variante übernommen und keine
automatische Feldakzeptanz aktiviert. Standardparameter und Originaldaten bleiben
erhalten; Vergleiche und exportierbare Reliability-Diagramme liegen im Experimentordner.

## Hardware und lokale Standardmodelle

Tatsächlich erkannt: Windows 11, **eine NVIDIA RTX 4090 Laptop GPU mit
16376 MiB VRAM**, anfangs etwa 14775 MiB frei, Treiber 572.83; ungefähr
63,7 GiB RAM und anfangs 1,46 TiB freie Platte. Die genannten 47 GB VRAM sind
hier nicht vorhanden. `doctor` ermittelt aktuelle Werte, Sprachdaten,
Paketversionen, CUDA-Verfügbarkeit, fehlende Gewichte und Speicherwarnungen.
Zusätzlich ist Intel UHD Graphics als Windows-Displayadapter registriert.
Es gibt eine nutzbare CUDA-GPU; gemeinsam genutzter System-RAM wird nicht zu
deren dediziertem VRAM addiert. `doctor` trennt Displaytreibereinträge von CUDA-Geräten.

| ID | Vollständige Pipeline | Modell / Komponente |
| --- | --- | --- |
| `ocr_rules` | OCR → Zeilen/Spalten → strukturierte Felder → Signaturfeldprüfung | Tesseract + OpenCV/Regeln |
| `ocr_llm` | identische OCR mit Layout → lokale JSON-Extraktion → Signaturfeldprüfung | Qwen3-8B, LLM.int8 auf GPU, Thinking aus |
| `vlm` | Seitenbilder → Teilnehmerdaten inklusive Signaturpräsenz; Seitentext als Fallback bei fehlenden Teilnehmern | Qwen3-VL-4B-Instruct, BF16 |
| `unlimited_ocr` (optional) | Unlimited-OCR → lokale Zellzuordnung mit LLM → visuelle Signaturprüfung | Unlimited-OCR + Qwen3-8B; [Anleitung](docs/unlimited-assignment.md) |

Bei allen drei Verfahren steht die Teilnehmerextraktion im Vordergrund. Ohne
strukturierte Teilnehmer bleibt gelesener Text als Fallback zur manuellen Prüfung
erhalten. A/B verwenden den vorhandenen Tesseract-Text; dadurch entstehen keine
zusätzlichen Modellaufrufe. Fehler der Strukturierung bleiben als Fehler sichtbar.

Beim VLM bezeichnet `personnel_number` die Spalte **Benutzer / User ID /
Personalnummer**, `department` dagegen **Kurzzeichen / Abteilung / Organisation**.
Die Zuordnung richtet sich nach Überschrift und Zellposition. Ist Benutzer
sichtbar leer, bleibt dieses Feld leer (`""`, Status `empty`); der Teilnehmer
und sein Kurzzeichen bleiben erhalten. Unleserliche oder geschwärzte Angaben
bleiben `null/uncertain`. Leere Zellen dürfen keine nachfolgenden Spalten
verschieben. Diese Anweisung gilt für lokale und API-VLMs. Sie wird mit zwei
synthetischen Tabellen und unterschiedlichen Spaltenreihenfolgen geprüft:

```powershell
.venv/Scripts/python.exe scripts/make_empty_user_smoke.py --output data/empty-user-smoke
.venv/Scripts/participant-bench.exe run --input data/empty-user-smoke/raw --ground-truth data/empty-user-smoke/ground_truth.jsonl --config configs/empty-user-smoke.yaml --offline
```

Nach dieser Änderung einen neuen Lauf starten. Ältere Ergebnisse werden durch
das Öffnen oder Aktualisieren ihres Berichts nicht neu erkannt; alte Läufe
können wegen der geänderten Promptidentität nicht mit `--resume` vermischt werden.

Das OCR-Sprachmodell erhält jedes OCR-Wort in einer kompakten Tabelle:
Wort-ID, Text, Position auf einer Skala von 0 bis 1000 und OCR-Confidence.
Zusätzlich enthält `lines` dieselbe lesbare Zeilenaufteilung wie der OCR-Klartext,
mit `line_id`, Zeilentext und zugehörigen Wort-IDs. Präzise Originalpositionen
bleiben in den Rohdaten erhalten. Die kompakte Antwort enthält Feldwerte,
`ocr_line_id` und referenzierte Wort-IDs. Die Anwendung prüft die Textbelege;
Zeilenpositionen werden aus beobachteten OCR-Wörtern ermittelt. Es werden keine
Wörter abgeschnitten, um das Eingabelimit einzuhalten. Sehr große Seiten können
weiterhin das Limit erreichen; dann bleibt der vorhandene OCR-Text als Fallback.
Nicht belegbare Modellzeilen werden einzeln mit Begründung verworfen. Andere,
belegbare Zeilen derselben Antwort bleiben erhalten; die Seite erhält `partial`
und Prüfhinweise. Wenn keine belegbare Zeile übrig bleibt, greift der Text-Fallback.
Eine solche Nachprüfung ist kein Beleg für die tatsächliche Richtigkeit der
OCR-Zeichen oder die Vollständigkeit aller Teilnehmer.

Standardmäßig erhält B auch teilweise belegte Zeilen
(`models.ocr_llm.preserve_partial_fields: true`). Eine im OCR-Text eindeutig
lokalisierbare Personalnummer oder Namensangabe dient als Zeilenanker.
Felder benötigen vollständige OCR-Wortbelege in derselben Textzeile; Namen aus
anderen Zeilen und bloße Teilzeichenfolgen werden nicht übernommen. Unbelegte
Felder bleiben `null/failed`, belegbare andere Felder derselben Zeile bleiben
erhalten. Niedrige OCR-Confidence führt zu `uncertain`. Die Originalschreibweise
der OCR wird erhalten. Die Prüfung verwendet vorrangig die OCR-Zeilenkennung;
Wörter derselben Zeile benötigen keine überlappenden Zeichenkästen. Bei getrennten
OCR-Blöcken oder fehlenden Zeilenkennungen dienen die Positionen als Ersatz.
Äußere Satzzeichen wie in `Weber,` oder `(MUC)` werden beim Vergleich toleriert,
bleiben in der Ausgabe aber erhalten. Unpassende Modellreferenzen und
unvollständige Felder
werden als Prüfhinweise gespeichert. Mit `false` bleibt die strengere Prüfung
ganzer Modellzeilen verfügbar. Handschrift und wechselnde bzw. mehrzeilige
Tabellen können weiterhin zu fehlenden oder mehrdeutigen Belegen führen.

B lädt denselben Qwen3-8B-Checkpoint mit **LLM.int8** vollständig auf GPU 0.
Die Parameterzahl und Modellrevision bleiben gleich; die linearen Schichten
werden beim Laden mit bitsandbytes 0.48.1 quantisiert. Das spart Speicher, kann
aber einzelne Ergebnisse gegenüber BF16 verändern. C und die gemeinsame
Unterschriftenprüfung verwenden weiterhin Qwen3-VL-4B in BF16 auf GPU 0.
Die Modelle werden nacheinander geladen und entladen. Tesseract, PDF-Aufbereitung
und regelbasierte Nachverarbeitung laufen weiterhin auf der CPU.

`device: cuda` erzwingt jetzt die vollständige GPU-Zuordnung und prüft die
tatsächlichen Parametergeräte. Bei fehlendem Speicher entsteht ein sichtbarer
Fehler; es gibt keinen stillen CPU-Offload. `device: auto` erlaubt weiterhin
eine Aufteilung nach GPU-/CPU-Budget. Die GPU-Prüfung verlangt vor dem Laden das
konfigurierte Budget plus 2 GiB Reserve (LLM: 11 + 2 GiB, VLM: 10 + 2 GiB).
Bei fester GPU-Zuordnung begrenzt der CUDA-Allocator zusätzlich den Speicher auf
den beim Start freien VRAM abzüglich 2 GiB Reserve. Lange OCR-Prompts werden in
1024-Token-Abschnitten eingelesen, ohne Text abzuschneiden. Das vermeidet große
Zwischenergebnisse und die beobachtete langsame Windows-RAM-Auslagerung.
Gerätezuordnung, Quantisierung und
Modellspeicher stehen in `ocr_llm/resources.json` und im `progress.log`.
Einrichtung, Rückkehr zu BF16 und Grenzen: [GPU-Ausführung](docs/gpu-inference.md).

PyTorch 2.8.0/torchvision 0.23.0 werden reproduzierbar vom expliziten CUDA-12.6-
Index bezogen, Transformers ist 4.57.6. CUDA wurde auf dieser GPU verifiziert.
Diese Paketquelle ist eine bewusste Auswahl für das vorgefundene NVIDIA-System.
Andere GPU-Backends werden nicht als unterstützt ausgegeben. CPU-Inferenz kann
ausdrücklich mit `device: cpu` und `quantization: none` konfiguriert werden; sie kann sehr langsam sein.
Modelle, Revisionen, Lizenzen und offizielle Quellen: [Entscheidungen](docs/decisions.md).

## Einmal vorbereiten, anschließend offline vergleichen

Eigene PDFs nach `data/raw` legen. Andere Dateitypen werden mit Grund protokolliert.
Optional `pdf.recursive: true`. Ein erster kleiner Lauf:

```powershell
uv run --offline --locked --extra models participant-bench prepare --input data/raw --config configs/local.yaml --output prepared/meine-listen
uv run --offline --locked --extra models participant-bench run --input data/raw --config configs/local.yaml --offline
```

`--offline` vor `--locked` unterbindet auch Paketdownloads durch **uv**.
`--offline` nach `run` erzwingt lokale Modellverarbeitung vor dem Einlesen der PDFs.
Die lokale Inferenz verwendet lokale Pfade und `local_files_only=True`;
HF-/Transformers-Offlinemodus und optionale Telemetrieabschaltung sind aktiv.
In der lokalen Konfiguration gibt es keine Inference-Endpunkte, externen
Bild-URLs oder Remote-Code-Ausführung.
Pakete/Gewichte/Sprachdaten müssen vorher installiert sein.

Die Eingabe wird vorher manuell ausgewählt. Alle Seiten der angegebenen PDFs
gehen direkt in die Teilnehmerextraktion. Es gibt keine automatische Prüfung
auf Teilnehmerlisten, Schlüsselwortfilterung oder Aussortierung leerer Seiten.
Für eine Stichprobe die ausgewählten PDFs nach `data/pdfs_eingabe/` kopieren und
diesen Ordner als `--input` angeben.

`prepare` erzeugt PNGs und `manifest.json` mit `include: true` für jede Seite.
PyMuPDF berücksichtigt PDF-Rotationsmetadaten bereits beim Rendern. Optional
erkennt OSD zusätzliche physische Scanrotation; geringe Evidenz markiert
Prüfbedarf, schließt aber keine Seite aus. Mit `pdf.auto_orient: false` entfällt
diese OCR-basierte Ausrichtung. Ein reiner VLM-Lauf benötigt dann keine OCR-
Initialisierung; A/B verwenden OCR weiterhin zur eigentlichen Textextraktion.

Neue Manifeste haben Version 2 und `automatic_page_selection: false`.
Ältere Manifeste mit automatischer Seitenauswahl mit `prepare` neu erzeugen,
damit frühere Ausschlüsse nicht unbemerkt übernommen werden.

Optional für einen festgeschriebenen Vergleich die Bilder **vor** der Evaluation
kontrollieren und eine Kopie des Manifests im selben Ordner als `curated.json`
speichern. Nur in diesem ausdrücklich manuell geprüften Manifest sind einzelne
Seitenausschlüsse zulässig:

- `include`: Auswahl je ursprünglicher PDF-Seite.
- `curation_rotation_clockwise`: zusätzliche 0/90/180/270 Grad auf das bereits
  vorbereitete Bild; keine Wiederholung der PDF-Metadatenrotation.
- `curation_note`: menschliche Begründung; `review_required` nach Prüfung setzen.
- `split`: `development` oder `test`, auf Dokumentebene einheitlich.
- `dependency_group`: zusammengehörige/ähnliche Dokumente derselben Gruppe.
- Nach vollständiger Prüfung oben `curated: true` setzen.

```powershell
uv run --offline --locked --extra models participant-bench run --input data/raw --manifest prepared/meine-listen/curated.json --scope curated --config configs/local.yaml --offline
uv run --offline --locked --extra models participant-bench run --input data/raw --manifest prepared/meine-listen/curated.json --scope curated --ground-truth data/ground_truth/test.jsonl --split test --config configs/local.yaml --offline
```

`--scope curated` bewertet ausschließlich die festgeschriebene Seitenauswahl.
`--scope end-to-end` (Standard) bewertet alle annotierten Roh-PDF-Seiten,
einschließlich ausgeschlossener oder fehlgeschlagener Seiten; fehlende Teilnehmer
bleiben im Nenner. Unannotierte Ausgabeseiten erhalten keine Qualitätsaussage.
`--split` erfordert Splitannotation auf allen Manifestseiten und beschränkt auch
die Extraktion unabhängig von der Ground Truth. Ground Truth wird niemals an
OCR, Seitenauswahl, Regeln oder Modelle übergeben.

Original-PDFs werden nicht verändert. SHA256 identifiziert Dokumente, ursprüngliche
Seitennummern identifizieren Seiten. Identische PDFs werden erkannt und einmal
verarbeitet. Beschädigte/verschlüsselte PDFs werden als Fehler protokolliert.
Eine vorhandene PDF-Textebene wird vermerkt, für keines der drei Verfahren benutzt.
Keine Schwärzungsentfernung oder Rekonstruktion verdeckter Inhalte.

## Konfiguration und Grenzen

`configs/local.yaml` aktiviert alle drei Verfahren; `configs/smoke.yaml` nur A.
Regeln nutzen erkannte Kopfzeilen und Tabellenlinien statt einer einzigen festen
Pixelvorlage. Für andere Formulare lassen sich Header-Aliase sowie normalisierte
Spaltenintervalle `rules.columns` und `body_top`/`body_bottom` konfigurieren, z.B.:

```yaml
rules:
  columns:
    first_name: [0.10, 0.29]
    last_name: [0.29, 0.45]
    personnel_number: [0.45, 0.62]
    department: [0.62, 0.80]
    signature: [0.80, 0.96]
  body_top: 0.22
  body_bottom: 0.90
```

Andere Regeln aus `local.yaml` beim Kopieren beibehalten. `extends` ersetzt
angegebene Hauptabschnitte vollständig; es ist kein beliebig tiefes YAML-Merging.
Zeilenumbrüche, verbundene Zellen, wechselnde Spaltenreihenfolgen und schlechte
Scans sind Grenzen von A. Mehrteilige Überschriften wie `Personal Nr.` werden
auch aus benachbarten OCR-Wörtern erkannt. Zwei erkannte Teilnehmerfelder können
für eine Zuordnung ausreichen. Bei fehlenden Überschriften lassen sich
`rules.columns` und `rules.body_top` anhand der Seitenvorschau ausdrücklich
vorgeben. Die Beispielwerte oben müssen zum tatsächlichen Formular passen.
Ohne belastbare Feldzuordnung gibt A `partial`, Prüfhinweise und den OCR-Text
als Fallback aus. Niedrige OCR-Confidence markiert unsichere Felder,
ist keine kalibrierte Wahrscheinlichkeit. Gedruckte Zeilennummern bleiben Strings;
Ausgabeindizes sind ausdrücklich keine sicheren Zeilenreferenzen.

`configs/local.yaml` verwendet für Unterschriften jetzt `signature.backend: local_vlm`.
Diese gemeinsame Zusatzstufe nutzt bei A/B/C das vorhandene lokale
Qwen3-VL-4B-Instruct. Sie betrachtet jede Teilnehmerzeile in einem vergrößerten
Ausschnitt zusammen mit dem Spaltenkontext. Namen und Drucktext gelten nicht
als Unterschrift. Sichtbare Unterschriftsmarkierungen ergeben `true`, eindeutig
leere Felder `false`; unklare Felder bleiben `null`. Widersprechen sich Gesamtbild
und Detailprüfung, wird das Ergebnis zur Prüfung markiert. Es gibt keinen
Echtheits- oder Identitätsnachweis und noch keine validierte Genauigkeit auf realen Signaturen.

Fehlende Zeilenpositionen werden bevorzugt aus vorhandenen OCR-Wortbelegen
bestimmt. Verfügbare OCR kann für diese reine Positionssuche verwendet werden;
sonst lokalisiert das VLM die bereits extrahierten Personen separat. Die
Personenfelder werden dabei nicht geändert oder erneut extrahiert. Ein Fehler
der Zusatzstufe verwirft keine Personen. A/B entladen ihr Extraktionsmodell vor
dem Laden des Signatur-VLM; C verwendet dasselbe geladene VLM. Aufrufe, Rohantworten,
Cachetreffer, Ausschnitte und zusätzliche Laufzeiten werden separat protokolliert.
Die Signaturauswertung ist damit bei diesen Einstellungen ausdrücklich keine reine OCR-Baseline.

Mit `signature.backend: opencv` bleibt die konservative Baseline verfügbar:
Sie entfernt Formularränder und entscheidet nur sicher lokalisierte leere
Felder negativ. Tinte bleibt unbekannt. Die Smoke-Konfigurationen verwenden
diese Baseline. `signature.inspect_known: false` begrenzt die Detailprüfung auf
bisher unbekannte Entscheidungen; standardmäßig werden auch bekannte geprüft.

## Unterschriften vorhandener Ergebnisse nachprüfen

Aus `software/` ohne erneute Teilnehmerextraktion:

```powershell
.venv/Scripts/participant-bench.exe signatures --run runs/DEINE_RUN_ID --method ocr_llm
.venv/Scripts/participant-bench.exe signatures --run runs/DEINE_RUN_ID --method vlm
```

Ohne `--method` werden alle Verfahren des Quelllaufs nachgeprüft. Die Ausgabe
liegt in `runs/DEINE_RUN_ID/signature-review/<Zeitstempel>/`. Der ursprüngliche
Lauf bleibt erhalten. `signature_recheck.json` benennt Quelle und Prüfsummen;
alte Laufzeiten und Qualitätsmetriken werden nicht als neue Messung übernommen.
Das lokale Modell muss bereits installiert sein; der Befehl lädt keine Gewichte herunter.

Im Bericht zeigt **Unterschriften im Detail** die tatsächlichen Ausschnitte.
Nur die Zeile unter dem blauen Trenner wird bewertet; der obere Bereich ist
Spaltenkontext. `signature_checks.csv` enthält die Entscheidungen und Bildpfade,
`<Verfahren>/raw-<Seiten-ID>.json` zusätzlich die Rohantworten. Fehlende oder
widersprüchliche Positionen bleiben zur manuellen Kontrolle offen. Echte
Trefferquoten erfordern manuell gelabelte positive und negative Beispiele.

VLM-Auflösung (`min_pixels`/`max_pixels`), Tokenbudget, dtype und Decodierung sind
konfigurierbar. Optionale vertikale Kachelung über `tile_height` in Pixeln und
`tile_overlap`; jede Kachel und jeder Aufruf wird protokolliert. Ohne Kachelung
wird die ganze Seite innerhalb des Processor-Pixelbudgets skaliert. Überlappende
oder an Kachelgrenzen angeschnittene Zeilen müssen kontrolliert werden; mögliche
Duplikate werden nicht durch ungeprüfte Inhaltsgleichheit versteckt. Keine
automatischen OOM-Retries, Reparaturaufrufe oder stillen Auflösungsänderungen.
Zu lange Eingaben und ungültiges/abgeschnittenes JSON sind explizite Fehler.

Das VLM extrahiert vorrangig Teilnehmerdaten aus jeder eingegebenen Seite.
Eine bestimmte Überschrift oder Tabellenform ist keine Voraussetzung.
`participants` enthält die ausgefüllten Personenzeilen; `page_text` bleibt dabei
`null`. Nur wenn keine Teilnehmer strukturiert erkannt werden, enthält `page_text`
als Fallback den gesamten lesbaren Text einschließlich Überschriften, Datumsangaben
und Notizen. Eine tatsächlich leere Seite ergibt einen leeren String. Es gibt
keine Dokumenttypprüfung. Fallback-Text wird im Bericht zur manuellen Prüfung
markiert und nicht als erkannte Teilnehmer oder als richtige Extraktion gewertet.
Die VLM-Antwort verwendet ein kompaktes Schema ohne Bounding-Box-Metadaten;
intern werden Teilnehmerdaten weiterhin in das gemeinsame Evaluationsschema
überführt. Unbekannte oder verdeckte Werte bleiben `null`, sichtbar leere Felder
werden als leere Strings gespeichert. Unterschriften werden nicht transkribiert.

`models.vlm.max_new_tokens` beträgt standardmäßig 8192. Wird dieses Limit erreicht,
wird die Antwort ausdrücklich als abgeschnitten markiert. Das ist ein Fehler der
Ausgabe, kein Ausschluss der PDF-Seite. Der Bericht zeigt zuerst Teilnehmerdaten,
anschließend Text-Fallbacks und Fehlerursachen. Die unveränderte Modellantwort
ist unter den technischen Details verlinkt, auch wenn
deren JSON unvollständig ist. Neue Ausgaben im Laufordner:

- `page_text.jsonl`: Fallback-Text, Fallback-Markierung und Status pro Seite und Verfahren.
- `pages.csv`: Seitenweise Statuswerte und Fehlerursachen.
- `<Verfahren>/texts/<Seiten-ID>.txt`: Seitentext nur bei Text-Fallback, für alle drei Verfahren.
- `<Verfahren>/raw_text/<Seiten-ID>.txt`: unveränderte Modellantwort bei OCR+LLM und VLM, auch bei Fehlern.
- `<Verfahren>/raw-<Seiten-ID>.json`: vollständige OCR-Daten und Modellantworten, soweit vorhanden.

Vorhandene Läufe behalten ihre Ergebnisse. Für das bedingte Text-Fallback
einen neuen Lauf starten; ältere Antworten werden
nicht nachträglich als erfolgreiche Extraktion umgedeutet.

## OCR-Klartext und Modelleingabe kontrollieren

Der HTML-Bericht enthält den aufklappbaren Abschnitt **OCR-Klartext und
Modelleingabe**, unabhängig davon, ob Teilnehmer erkannt wurden. Die Lesefassung
enthält alle erkannten OCR-Wörter. Das Sprachmodell erhält diese Wörter als
Layouttabelle mit Wort-IDs, Positionen und lesbaren OCR-Zeilen. Diese exakte
Eingabe ist separat verlinkt, sofern der gespeicherte Prompt-Hash übereinstimmt. Die Systemanweisungen
stehen in `prompts.json`. Der Klartext ist keine fehlerfreie Abschrift der PDF.

- `<Verfahren>/ocr_text/<Seiten-ID>.txt`: vollständiger OCR-Klartext, auch ohne Text-Fallback.
- `<Verfahren>/ocr_words/<Seiten-ID>.csv`: OCR-Wörter, Wort-IDs, Positionen und Confidence.
- `ocr_llm/model_input/<Seiten-ID>-<Aufruf>.txt`: exakte Eingabe des Sprachmodells.
- `ocr_text.jsonl`: Klartext und Verweise je Seite und Verfahren.

Einen vorhandenen Bericht ohne neue Inferenz aktualisieren:

```powershell
.venv/Scripts/participant-bench.exe report --run runs/DEINE_RUN_ID
```

Die gespeicherten Vorhersagen und Messwerte bleiben dabei erhalten. Das ist
eine Aktualisierung der Darstellung, keine neue Teilnehmerextraktion.

Als ausdrücklich getrennten OCR-Versuch gibt es `configs/ocr-sparse.yaml`
(Tesseract PSM 11 statt PSM 6, beide OCR-Verfahren). Diese Variante kann bei
verstreut angeordnetem Text andere Wortergebnisse liefern. Höhere OCR-Confidence
ist kein Beleg für höhere Richtigkeit; Varianten auf manuell geprüften
Entwicklungsdaten vergleichen. Der reguläre OCR-Modus bleibt unverändert.

## Schema und Ground Truth

Für eine vorhandene Excel-Kursliste gibt es zusätzlich einen separaten,
kursweisen Abgleich nach der Extraktion:

```powershell
uv run --offline --locked --extra models participant-bench compare-excel --run runs/DEINE_RUN_ID --excel data/referenz/kurse.xlsx
```

`Class ID` entspricht der PDF-ID, `Organization` dem Kurzzeichen. Bei verdeckter
User ID wird anhand von Vorname, Nachname und Kurzzeichen zugeordnet. Die
Ergebnisse enthalten Feldvergleiche sowie gefundene, fehlende und zusätzliche
Personen. Konfiguration, Umgang mit Mehrdeutigkeiten und Grenzen der Kennzahlen:
[Excel-Abgleich](docs/excel-comparison.md).

[JSONL-Vorlage](examples/ground_truth.template.jsonl), [JSON-Schemas](examples/schemas/).
`uv run participant-bench schemas` erzeugt sie aus den implementierten Modellen.
Pro annotierter Seite ein JSON-Objekt mit `document_id` aus dem Manifest,
`page_number` (1-basiert), `split`, `dependency_group`, `content_type`, `relevant`
und `participants`. Auch leere und irrelevante Seiten mit `participants: []`
annotieren. `content_type`: `typed`, `handwritten`, `mixed` oder `other`.

Textfelder haben `{value, state, bbox}`. Zustände: `read`, `empty`, `illegible`,
`uncertain`, `failed`. Nicht erkennbare Referenzfelder als `illegible` kennzeichnen.
Personalnummern sind zwingend Strings (`"00007"`). `signature_present` ist
`true`, `false` oder `null`, mit konsistentem `signature_state`. Bounding Boxes
haben normalisierte `x0,y0,x1,y1` auf der final orientierten vollständigen Seite.
`row_ref` nur bei wirklich gedruckter, lesbarer Referenz setzen, sonst `null`.

Ground Truth muss menschlich geprüft sein. Die synthetische Ground Truth ist
aus der PDF-Konstruktion verfasst, nicht aus Extraktoren übernommen.
Dokumente und Dependency-Gruppen dürfen nicht über Development/Test verteilt
werden; die Validierung lehnt solche Überschneidungen ab. Exakte Duplikate werden
über PDF-Hashes erkannt; Near-Duplicates und andere Abhängigkeiten müssen bei
der Gruppierung menschlich berücksichtigt werden. Regeln/Prompts nur auf
Development entwickeln, vor Testlauf einfrieren.

## Metriken

Alle Metriken speichern Zähler/Nenner, bei Nenner 0 `null`. Keine Qualitätsrangliste
ohne Ground Truth, keine Signifikanztests auf abhängigen Zeilen oder Feldern.

- Matching je Dokument/Seite: eindeutige gedruckte Zeilenreferenz, danach vertikale
  Boxüberschneidung (IoU ≥0,25), erst bei fehlender Geometrie ungarisches Matching
  aus Namen/Abteilung (Ähnlichkeit ≥0,65). Personalnummer **kein** Matchingmerkmal.
  Inhaltsmatching ist eine gekennzeichnete Annäherung, kein unabhängiger Identitätsbeleg.
- Exact Match je Textfeld und mikroaggregiert über alle lesbaren/leeren GT-Felder.
  Fehlende Zeilen bleiben im Nenner; unleserliche GT-Felder werden separat gezählt.
  Namen/Abteilung: NFC, Leerraum vereinheitlichen, casefold. Personalnummer: strikter
  unveränderter Stringvergleich. Rohwerte bleiben erhalten.
- CER: Summe Levenshtein-Edits / Summe GT-Zeichen je Feldtyp. Fehlende Zeile = leerer
  Vorhersagetext, zusätzliche Zeichen = Insertionen; CER kann über 1 liegen.
- Feld-PRF: korrektes bekanntes Feld TP; falsche bekannte Antwort FP+FN;
  fehlend/unbekannt FN; zusätzliche bekannte Felder FP. Leeres Feld ist eine
  bekannte Antwort. Eintrags-PRF verlangt vier bekannte korrekte Textfelder.
- Teilnehmerzuordnung: Matchingquellen, Matchabdeckung, vollständige korrekte
  Zeilen, ausgelassene und zusätzliche Einträge; vertauschte Feldzuordnung wird bestraft.
- Unterschriften: Precision/Recall/F1, 2×3-Konfusionsmatrix mit eigener unknown-
  Spalte. Unknown bei positiver GT zählt FN. Abdeckung und Unknown-Anteil schließen
  fehlende Zeilen ein. Unbekannte GT separat, zusätzliche positive Antworten FP.
- Schemafehler, technische Ausfälle, partial-Seiten, tatsächlich valide verarbeitete
  Seiten; deskriptive Aufteilung nach Split und annotierter Schriftart.

Die vollständigen Definitionen stehen zusätzlich im HTML-Bericht und in
`metrics.json`. Syntaxvalidität bedeutet nicht inhaltliche Richtigkeit.

## Ergebnisdateien, Laufzeiten und Resume

`participant-bench run` zeigt standardmäßig fortlaufende Statusmeldungen mit
Uhrzeit (UTC) und verstrichener Laufzeit. Angezeigt werden Eingabedateien,
PDF-Seitenvorbereitung, Orientierung/OCR, Gewichtsprüfung, Modellladen,
GPU-Speicher, Warm-up, Tokenisierung und die eigentliche Modellantwort.
Je Seite erscheinen Datei, ursprüngliche Seitennummer, Fortschritt, technischer
Status, Anzahl ausgegebener Einträge und Laufzeit. Auch Cachetreffer,
übernommene Resume-Ergebnisse und Fehler werden angezeigt.

Bei länger dauernden Schritten erscheint alle zehn Sekunden eine Meldung zum
aktiven Schritt und dessen bisheriger Dauer. Die Prozentanzeige zählt fertig
verarbeitete Seiten des aktuellen Verfahrens; einzelne Seiten können
unterschiedlich lange dauern. Alle Meldungen werden sofort ausgegeben und
zusätzlich unter `runs/<Lauf-ID>/progress.log` gespeichert. Bei Resume wird
dieses Protokoll ergänzt. Dein bisheriger Startbefehl funktioniert unverändert.

Jeder Lauf erhält `runs/<UTC-Zeit>-<ID>/`:

```text
config.yaml, environment.json, identity.json, prompts.json, progress.log
manifest.json, effective_pages.json, pages/*.png, review_pages.csv
<method>/raw-<page>.json, raw.jsonl, extractions.jsonl, checkpoint.jsonl
<method>/attempts.jsonl, attempts/raw-<page>-<attempt>.json
<method>/timings.csv, resources.json, evaluation_details.csv  (mit GT)
summary.json, methods.csv, extractions.csv, metrics.json, quality.csv (mit GT), errors.jsonl
costs.json, run_timing.json, report.html
```

`report.html` lokal öffnen; keine externen Skripte, Bilder oder CDNs. Inhalte
werden HTML-escaped, CSP sperrt externe Ressourcen. Seiten-/Zeilenreferenzen,
Status, Rohantworten, Parse-Status und validierte Ergebnisse bleiben getrennt.
`success` heißt technisch vollständiger Aufruf, `partial` teilweise verwertbar
oder unklare Regelstruktur, `unavailable` fehlende Voraussetzungen, `failed`
technischer/Parse-Fehler. Der CLI-Exitcode ist 2 bei failed/unavailable-Verfahren,
1 bei Eingabe-/Konfigurationsfehlern, sonst 0; `partial` trotzdem Bericht prüfen.

GPU-Messungen werden synchronisiert. Ladezeit, Warm-up, Vorverarbeitung, OCR,
Strukturierung/Signatur und Modellinferenz sind getrennt. OCR wird für A/B geteilt,
jedem vollständigen Verfahren aber mit der ursprünglich gemessenen OCR-Laufzeit
zugerechnet. Cachezugriff und Originalaufwand stehen nebeneinander. Die
Vorbereitung umfasst Rendering und optional die Ausrichtung; es gibt keine
zusätzliche OCR zur Seitenklassifikation. Kuratierte Evaluation rechnet die
vorherige manuelle Seitenauswahl nicht zur Extraktion.

`full_pipeline_charged_seconds` ist aus gemessenen Komponenten zusammengesetzter
Aufwand für den gewählten Scope, keine zweite reale Stopuhr. `actual_method_wall_seconds`
und `actual_run_wall_seconds` zeigen die tatsächliche Laufzeit einschließlich
Cacheeffekten; Run-Zeit enthält auch Prüfsummen, Inventarisierung und Berichts-I/O.
Diese Größen nicht vermischen. Gewichtsprüfung wird separat in Ressourcen erfasst
und über den gesamten Modell-Setup-Aufwand in der zusammengesetzten Pipelinezeit mitgezählt.
Peak-GPU: PyTorch-Allocator auf GPU 0, ohne Treiber/fremde Prozesse. Peak-RAM:
100-ms-RSS-Sampling von Prozess und Kindern, gemeinsame Speicherseiten ggf. doppelt.

```powershell
uv run --offline --locked --extra models participant-bench run --input data/raw --config configs/local.yaml --offline --resume runs/DEINE_RUN_ID
uv run --offline --locked --extra models participant-bench clean-cache --config configs/local.yaml
uv run --offline --locked --extra models participant-bench clean-cache --config configs/local.yaml --apply
```

Resume übernimmt nur erfolgreiche Seiten und prüft vollständige Eingabe-,
Manifest-, Konfigurations-, Code-, Prompt-, Paket-, OCR-, Modell- und GT-Identität.
Fehlgeschlagene Seiten werden erneut versucht; Rohantworten aller Versuche und
deren Aufwände bleiben erhalten. OCR wird pro Seite/Verfahren einmal zugerechnet,
bei Wiederholungen zusätzlich der tatsächlich gemessene Cachezugriff. Während Download oder Benchmark nicht gleichzeitig `uv sync`
ausführen: Windows sperrt laufende CLI-Executables. OCR-Cache ist größenbegrenzt;
Bereinigung löscht nur erzeugte OCR-JSONs innerhalb des Workspaces, nie Originale.
Gerenderte Bilder bleiben als prüfbare Run-Artefakte bestehen und müssen bei
großen Beständen separat archiviert/entfernt werden.

Kostenannahmen in `costs`: Menge, manueller Aufwand, Kontroll-/Korrekturzeit,
Stundensatz, lokale Betriebskosten sowie getrennte Entwicklungsstunden.
Ohne diese Daten keine Kosten-/Einsparungsbehauptung. Strom nur mit expliziter
gemessener/angenommener Energie und Strompreis; VRAM ist keine Energiekennzahl.
Freie Arbeitsstunden sind keine nachgewiesene Zahlungsersparnis, nicht
implementierte Importschritte werden nicht angerechnet.

## Reproduzierbarer kleiner Smoke-Test

```powershell
uv sync --locked --extra models
uv run --offline --locked --extra models participant-bench synthetic --output data/synthetic
uv run --offline --locked --extra models participant-bench prepare --input data/synthetic/raw --config configs/smoke.yaml --output prepared/synthetic
uv run --offline --locked --extra models python scripts/curate_synthetic.py
uv run --offline --locked --extra models participant-bench run --input data/synthetic/raw --manifest prepared/synthetic/curated.json --scope curated --ground-truth data/synthetic/ground_truth.jsonl --config configs/smoke.yaml --offline
uv run --offline --locked --extra models pytest -q
uv run --offline --locked --extra models ruff check vorverarbeitung verarbeitung/src tests scripts
```

Synthetik enthält maschinenschriftliche Tabellen, leere Seite, Deckblatt, leere
Liste, PDF-Rotationsmetadaten und physisch seitlich eingebetteten Scan. Das
Kuratorskript gilt ausschließlich für diese konstruierte Fixture und verwendet
Konstruktionsnotizen, keine Vorhersagen. Vorhandene Fixtureordner werden nicht
überschrieben. Bei erneutem Erzeugen einen neuen Zielordner verwenden.

Ein realer Modell-Smoke-Test bleibt bewusst klein (eine Seite, zwei Personen):

```powershell
uv run --offline --locked --extra models python scripts/make_model_smoke.py
uv run --offline --locked --extra models participant-bench run --input data/model-smoke/raw --ground-truth data/model-smoke/ground_truth.jsonl --config configs/local.yaml --offline
```

Tests decken echte OCR, führende Nullen, unknown, fehlende/zusätzliche und
vertauschte Zeilen/Felder, bekannte Metriknenner, ungültiges Modell-JSON,
unbelegte OCR-Modellfelder, Rotationen, beschädigte/verschlüsselte PDFs,
Duplikate, Manifeständerungen, Offline-Verhalten, Split-Leakage und Resume ab.
Fehlt Tesseract, werden die entsprechenden Integrationstests ausdrücklich
übersprungen. Modellinferenz wird nicht gemockt oder als ungetesteter Erfolg ausgegeben.
Konkreter Abnahmestand: [Verifikationsprotokoll](docs/verification.md).

`data/`, `models/`, `runs/`, `prepared/`, `.tools/`, `.venv/` und Caches sind
gitignoriert. Quellcode, Konfiguration, Schema und synthetischer Generator sind
versionierbar; personenbezogene Ergebnisse gehören nicht ins Repository.
