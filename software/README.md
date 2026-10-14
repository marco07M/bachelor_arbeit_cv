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

Alle Dokumente, Vorschauen und Ergebnisse bleiben lokal. **Ohne Ground Truth
wird keine Extraktionsqualität behauptet.** Die Ausgaben dienen menschlicher
Kontrolle und Korrektur. Reale Formulare müssen noch auf Development-Daten
angepasst und unabhängig auf Testdaten evaluiert werden.

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

## Hardware und Modelle

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
| `ocr_llm` | identische OCR mit Layout → lokale JSON-Extraktion → Signaturfeldprüfung | Qwen3-8B, BF16, Thinking aus |
| `vlm` | dieselben orientierten Seitenbilder → lokale visuelle JSON-Extraktion inklusive Signatur | Qwen3-VL-4B-Instruct, BF16 |

B verwendet explizites CPU-Offloading, weil 8B-Gewichte plus Aktivierungen
nicht vollständig in das sichere GPU-Budget passen. C ist wegen der tatsächlichen
16-GB-GPU die 4B-Variante. Beide starten mit Batch 1, 10 GiB GPU-Budget, 32 GiB
CPU-Budget, 2 GiB GPU- und 4 GiB RAM-Reserve; tatsächliche Gerätezuordnung und
Speicherbelegung werden gespeichert. Nur GPU 0 wird budgetiert. Keine Addition
von VRAM mehrerer GPUs. Modelle werden nacheinander geladen und entladen.

PyTorch 2.8.0/torchvision 0.23.0 werden reproduzierbar vom expliziten CUDA-12.6-
Index bezogen, Transformers ist 4.57.6. CUDA wurde auf dieser GPU verifiziert.
Diese Paketquelle ist eine bewusste Auswahl für das vorgefundene NVIDIA-System.
Andere GPU-Backends werden nicht als unterstützt ausgegeben. CPU-Inferenz kann
ausdrücklich mit `device: cpu` konfiguriert werden; sie kann sehr langsam sein.
Modelle, Revisionen, Lizenzen und offizielle Quellen: [Entscheidungen](docs/decisions.md).

## Einmal vorbereiten, anschließend offline vergleichen

Eigene PDFs nach `data/raw` legen. Andere Dateitypen werden mit Grund protokolliert.
Optional `pdf.recursive: true`. Ein erster kleiner Lauf:

```powershell
uv run --offline --locked --extra models participant-bench prepare --input data/raw --config configs/local.yaml --output prepared/meine-listen
uv run --offline --locked --extra models participant-bench run --input data/raw --config configs/local.yaml --offline
```

`--offline` vor `--locked` unterbindet auch Paketdownloads durch **uv**.
`--offline` nach `run` kennzeichnet zusätzlich den Benchmark-Aufruf. Die Inferenz
verwendet unabhängig davon immer lokale Pfade und `local_files_only=True`;
HF-/Transformers-Offlinemodus und optionale Telemetrieabschaltung sind aktiv.
Es gibt keine Inference-Endpunkte, externen Bild-URLs oder Remote-Code-Ausführung.
Pakete/Gewichte/Sprachdaten müssen vorher installiert sein.

`prepare` erzeugt PNGs und `manifest.json`. PyMuPDF berücksichtigt PDF-
Rotationsmetadaten bereits beim Rendern. Nur zusätzlich erkannte physische
Scanrotation wird angewendet. OSD mit geringer Evidenz markiert Prüfbedarf.
Handschrift und Unterschriften sind keine Seitenrelevanzkriterien. Mehrere
unabhängige Feldüberschriften kennzeichnen Listen; unklare Seiten, einschließlich
Deckblättern, bleiben konservativ enthalten. Nur nahezu weiße Seiten werden
automatisch ausgeschlossen. Leere Tabellen bleiben erhalten.

Für den primären Vergleich die Bilder **vor** der Evaluation kontrollieren und
eine Kopie des Manifests im selben Ordner als `curated.json` festschreiben:

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
Scans sind Grenzen von A. Ohne belastbare Kopfzeile keine erfundene Zuordnung;
`partial` mit Prüfhinweisen. Niedrige OCR-Confidence markiert unsichere Felder,
ist keine kalibrierte Wahrscheinlichkeit. Gedruckte Zeilennummern bleiben Strings;
Ausgabeindizes sind ausdrücklich keine sicheren Zeilenreferenzen.

A/B lokalisieren Unterschriftsfelder anhand begrenzter Tabellenzeilen, entfernen
Formularlinien und Randreste und erkennen konservativ nur leere Felder als negativ.
Tinte, Drucktext oder synthetische Striche bleiben `null/uncertain`. Ohne sicher
lokalisiertes Feld ebenfalls unbekannt. Es gibt noch keinen auf echten
Unterschriften validierten positiven Klassifikator. Bei B wird die Modellposition
nur einer eindeutig überlappenden vollständigen Tabellenzeile zugeordnet. C urteilt
visuell; dessen Signaturlaufzeit ist in der gemeinsamen Modellinferenz enthalten.

VLM-Auflösung (`min_pixels`/`max_pixels`), Tokenbudget, dtype und Decodierung sind
konfigurierbar. Optionale vertikale Kachelung über `tile_height` in Pixeln und
`tile_overlap`; jede Kachel und jeder Aufruf wird protokolliert. Ohne Kachelung
wird die ganze Seite innerhalb des Processor-Pixelbudgets skaliert. Überlappende
oder an Kachelgrenzen angeschnittene Zeilen müssen kontrolliert werden; mögliche
Duplikate werden nicht durch ungeprüfte Inhaltsgleichheit versteckt. Keine
automatischen OOM-Retries, Reparaturaufrufe oder stillen Auflösungsänderungen.
Zu lange Eingaben und ungültiges/abgeschnittenes JSON sind explizite Fehler.

## Schema und Ground Truth

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

Jeder Lauf erhält `runs/<UTC-Zeit>-<ID>/`:

```text
config.yaml, environment.json, identity.json, prompts.json
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
Klassifikations-OCR wird dabei auf eingeschlossenen Seiten nicht doppelt gezählt.
Bei C gehört OCR-basierte automatische Seitenauswahl nur im End-to-end-Scope zum
gemeinsamen Vorverarbeitungsaufwand. Kuratierte Evaluation rechnet die vorherige
manuelle Seitenauswahl nicht zur Extraktion.

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
uv run --offline --locked --extra models ruff check src tests scripts
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
