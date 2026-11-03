# Teilnehmerlisten aus PDFs auslesen und vergleichen

Alle Befehle aus `software/` ausführen. Lokale Modelle laufen auf dem GPU-Laptop;
die API-Verarbeitung hat einen eigenen Einstieg für den Firmen-PC.

Der Hauptvergleich in `configs/benchmark.yaml` enthält `ocr_raw`, `ocr_llm`,
`paddle_llm`, `docling`, `vlm` und `ocr_vlm`. Textzuordnung verwendet
Qwen3-4B-Instruct-2507; Bild und Hybrid verwenden dasselbe Qwen3-VL-4B-Instruct.
Docling ordnet ohne LLM anhand der Tabellenspalten zu. Der Hybridvergleich erhält
einen eigenen Feldbericht. Die neuen Textgewichte müssen einmalig eingerichtet
werden; vorhandene ältere Qwen3-4B-Gewichte ersetzen sie nicht.

## Direkt starten

| Aufgabe | Start | Eingabe |
| --- | --- | --- |
| Modelle ausführen und mit Excel/CSV vergleichen | [`start_testframework.cmd`](start_testframework.cmd) | PDFs in `testframework/eingabe_pdfs/`, Referenz in `testframework/referenz/` |
| Alle lokalen Modelle ohne Referenzvergleich ausführen | [`start_alle_lokalen_modelle.cmd`](start_alle_lokalen_modelle.cmd) | PDFs in `data/cv-test-20261020-093337/` |
| Über die Firmen-API ausführen und vergleichen | [`api_firmen_pc/start_api_testframework.cmd`](api_firmen_pc/start_api_testframework.cmd) | Eigene Eingaben unter `api_firmen_pc/testframework/` |

Die Startdateien lassen sich doppelt anklicken. Mit `--pruefen` wird bei den
lokalen Startdateien nur die Eingabe geprüft, ohne Modellinferenz.

**Aktuelle Ergebnisse:** [Excel-/CSV-Vergleiche](testframework/ergebnisse/README.md)
und [Modellläufe](runs/README.md). Die lokalen Übersichten werden beim Aufräumen
aktualisiert. Jeder neue Modelllauf schreibt seinen Bericht nach
`runs/<Lauf-ID>/report.html`; Vergleiche liegen in
`testframework/ergebnisse/<Vergleichs-ID>/report.html`.

## Wo gehört was hin?

| Ordner | Inhalt |
| --- | --- |
| `../dateien/` | Unveränderte Originaldokumente |
| [`vorverarbeitung/`](vorverarbeitung/README.md) | PDFs sammeln, nach Kurs-ID benennen, Anmerkungen aus Arbeitskopien entfernen |
| [`verarbeitung/`](verarbeitung/README.md) | Python-Paket `participant_bench`: OCR, Extraktion, Export und Evaluation |
| [`testframework/`](testframework/README.md) | PDF-Eingaben, Excel-/CSV-Referenz und Vergleichsberichte |
| [`api_firmen_pc/`](api_firmen_pc/README.md) | Getrennter API-Betrieb mit eigener Umgebung und Startdatei |
| `configs/` | Ausführbare Modell- und Evaluationsprofile |
| `tests/` | Automatisierte Softwaretests |
| `scripts/` | Installation, synthetische Testdaten und Aufräumen |
| `models/`, `.venv/`, `*_runtime/` | Lokale Modelle und benötigte Laufzeiten |

Eigene Dokumente und Referenzlisten sind gitignoriert. Die Unterschriften werden
auf sichtbares Vorhandensein geprüft, nicht transkribiert oder authentifiziert.

## Einmalig einrichten

```powershell
uv sync --locked --extra models
```

Für alle sechs lokalen Verfahren werden zusätzlich die OCR-/Strukturlaufzeiten
und die festgeschriebenen Modellgewichte benötigt. Die vollständigen Befehle
stehen unter [Sechs lokale Verfahren](docs/local-methods.md#einmalig-einrichten).
Für den Firmen-PC gilt die [separate Installation](api_firmen_pc/README.md).

## Anleitungen

- [PDFs und Referenz vorbereiten, Vergleich verstehen](testframework/README.md)
- [Lokale Modelle und ihr Ablauf](docs/local-methods.md)
- [Docling/Paddle: Fehleranalyse und gemessener Vorher-/Nachher-Vergleich](docs/structure-optimization.md)
- [Handschrift: belegte Datenverluste, OCR-Proben und Modellgrenzen](docs/handwriting-optimization.md)
- [Spaltenüberschriften auf Fortsetzungsseiten derselben PDF](docs/document-columns.md)
- [Excel-Spalten und User-ID-Vergleich](docs/excel-comparison.md)
- [OCR-Kalibrierung und unabhängige Evaluation](docs/ocr-calibration.md)
- [GPU-Konfiguration](docs/gpu-inference.md)
- [Ausführliches Handbuch und CLI-Befehle](docs/handbuch.md)
- [Alte Läufe und temporäre Dateien aufräumen](docs/aufraeumen.md)

## Software prüfen

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check --config pyproject.toml verarbeitung/src/participant_bench tests
```

Die Tests für die Firmen-API werden separat aus `api_firmen_pc/` mit dessen
Python-Umgebung gestartet.
