# Repository-Struktur

## Isolierte Strukturmodelle seit 28.10.2026

`paddle_structure_runtime/` und `docling_runtime/` besitzen jeweils ein eigenes
uv-Projekt für PaddleOCR beziehungsweise Docling/TableFormer. Die Workerquellen
liegen gemeinsam unter `structure_runtime/`; das Hauptpaket bindet sie lokal
über `participant_bench/structure.py` ein. Die bestehenden Qwen-, Unlimited-
und Firmen-PC-Umgebungen bleiben getrennt. Einrichtung und Start:
[Sechs lokale Verfahren](local-methods.md).

Im Hauptprofil nutzt `paddle_llm` Qwen3-4B-Instruct-2507 nach Entladen des
OCR-Workers. Docling verwendet `table_mapping.py` ohne LLM anhand gedruckter
Überschriften. `structure_assignment.py` bereitet native OCR-/Zellpositionen auf;
`unlimited_assignment.py` prüft die wortgetreue LLM-Zuordnung.
`hybrid.py` bereitet Paddle-Belege für `ocr_vlm` vor; `hybrid_evaluation.py`
vergleicht denselben Referenzteilnehmer zwischen VLM und Hybrid.
`attention.py` stellt die alternative SDPA-Berechnung bereit.
`assign-structures` ist für gespeicherte LLM-Zuordnungen verfügbar, nicht für
Docling im deterministischen Hauptvergleich. `image_preprocessing.py` wird
von Haupt-OCR und Doclings isolierter Tesseract-Komponente gemeinsam verwendet.

## Getrennter API-Betrieb seit 22.10.2026

Das Firmen-PC-Projekt besitzt seit dem 28.10.2026 auch ein eigenes
`testframework/` mit PDF-Eingaben, Excel-/CSV-Referenz und Ergebnissen.
`participant_api/benchmark.py` aktiviert die API für den gemeinsam verwendeten
Benchmark-Runner; die Zuordnung und Bewertung bleiben lokal. Der Starthelfer ist
`start_api_testframework.cmd`. Der ursprüngliche GPU-Einstieg bleibt offline.

`software/` bleibt das lokale uv-Projekt für OCR, LLM, VLM, Kalibrierung und
Evaluation. `software/api_firmen_pc/` ist ein zweites uv-Projekt mit eigener
virtueller Umgebung, Lockdatei, API-Konfiguration und `main.py`. Es bindet die
neutralen Analysefunktionen als lokale Quelldependenz ein, ohne das Extra `models`.
Nur der Firmen-PC-Einstieg aktiviert den separat installierten Adapter.

Der alte Ordner `software/test_url/` wurde unverändert nach
`software/api_firmen_pc/privat/test_url/` verschoben. Private Beispiele werden
weder paketiert noch getestet oder exportiert. Vorhandene Runs, PDFs und
Modellgewichte wurden nicht verschoben. Die Ergebnisformate bleiben gemeinsam.
Details und übertragbares Quellpaket: [Firmen-PC-Anleitung](../api_firmen_pc/README.md).


## Softwarebereiche seit 15.10.2026

`software/vorverarbeitung/` enthält die unabhängige PDF-Sammlung und Umbenennung.
Eingabe ist standardmäßig `dateien/` im Repository-Hauptordner; Ausgabe ist
`software/vorverarbeitung/ausgabe/pdfs/` ohne Unterordnerstruktur. Aussortierte
PDFs landen direkt unter `software/vorverarbeitung/ausgabe/nicht_erfuellt/`.
Eingabedokumente und erzeugte Ausgaben sind gitignoriert.

Der bisherige Quellcode unter `software/src/participant_bench/` liegt nun unter
`software/verarbeitung/src/participant_bench/`. Paketname und `participant-bench`
bleiben erhalten. Hatch paketiert beide Bereiche; nach der Aktualisierung
`uv sync --locked --extra models` aus `software/` ausführen. Gemeinsame
Konfigurationen, Tests, Modelle, Daten und Runs liegen weiterhin dort.
`configs/imported.yaml` aktiviert die rekursive Verarbeitung der importierten PDFs.

## Software und schriftliche Arbeit seit 14.10.2026

Seit 14.10.2026 liegen Software und schriftliche Arbeit getrennt unter
`software/` und `bachelorarbeit/`. Alle bisherigen Softwarebefehle werden nun
aus `software/` ausgeführt. `pyproject.toml`, `uv.lock`, `.python-version`,
Quelltext, Konfigurationen und Tests bilden dort dasselbe uv-Projekt.

Modellgewichte, Daten, vorbereitete Seiten und vorhandene Runs wurden nach
`software/models`, `software/data`, `software/prepared`, `software/runs`
verschoben. Sie bleiben gitignoriert. Es wurden keine Gewichte erneut geladen.
Die virtuelle Umgebung wurde am neuen Pfad neu aufgebaut; eine verschobene
venv mit alten absoluten Interpreter-/Editable-Pfaden wird nicht weiterverwendet.

Historische Runs behalten ihre damaligen Konfigurationen, Hashes und absoluten
Quellpfade. Sie werden als Forschungsprotokolle nicht nachträglich umgeschrieben.
Die HTML-Berichte funktionieren weiterhin, weil ihre Vorschaubilder relativ
im jeweiligen Run liegen. Alte Resume-/Prepared-Manifeste enthalten noch
Pfade vor der Umstellung und sind für neue Runs nicht wiederzuverwenden.
Neue Seitenmanifeste mit `participant-bench prepare` erzeugen; neue Runs
verwenden die neue Verzeichnisstruktur.
