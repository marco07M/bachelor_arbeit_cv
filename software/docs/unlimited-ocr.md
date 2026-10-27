# Unlimited-OCR lokal verwenden

Unlimited-OCR ist als optionales Verfahren `unlimited_ocr` in den bestehenden
Benchmark integriert. PDF-Verarbeitung, manuelle Seitenauswahl, Ausrichtung,
Logging, Resume, CSV-/JSON-/HTML-Berichte und strukturierte Bewertung werden
weiterverwendet. Es gibt keinen zusätzlichen Server und keine Cloud-Inferenz.

## Was die Verfahren vergleichen

`ocr_rules` bleibt als transparente Baseline erhalten: Tesseract liest Wörter,
Regeln ordnen sie anhand von Überschriften, Spalten und Zeilen zu. Das ist bei
stabilen Formularen ein sinnvoller Vergleich und benötigt kein großes Textmodell.
Fehlende Überschriften können die Zuordnung verhindern. Das Verfahren ist kein
trainiertes Modell zur freien Interpretation beliebiger Tabellen. Eine schlechte
Erkennung dieser Vorlage ist kein Beleg für eine generell schlechte OCR-Engine.

Unlimited-OCR parst dagegen Seiten mit einem generativen Dokumentmodell.
Bessere Namensqualität ist eine zu prüfende Hypothese, keine Garantie.
Insbesondere Eigennamen und Handschrift brauchen manuell geprüfte Referenzen.

## Geprüfte Umgebung und Abhängigkeiten

Erkannt: Windows 11, NVIDIA RTX 4090 Laptop GPU, 16376 MiB VRAM, CUDA-fähiges
PyTorch 2.8.0+cu126 und BF16-Unterstützung. Die vorhandene Hauptumgebung verwendet
Transformers 4.57.6. Sie bleibt für die bisherigen Qwen-Modelle bestehen.

Die native Unlimited-OCR-Unterstützung wird in einer separaten uv-Umgebung
`unlimited_ocr_runtime/.venv` installiert: Transformers 5.20.2, dasselbe PyTorch
2.8.0/CUDA 12.6 und Torchvision 0.23.0 sowie Pillow, Accelerate und Safetensors.
Die vollständige Auflösung steht in `unlimited_ocr_runtime/uv.lock`. Neuere
Hugging-Face-Hub-/Tokenizer-Versionen gelangen dadurch nicht in die Hauptumgebung.
`einops`, `addict` und `easydict` werden für den gewählten nativen Pfad nicht
benötigt. Die Baidu-Referenzumgebung verwendet andere Versionen; das ist kein
Grund, diese ungeprüft in die vorhandene Umgebung zu installieren.

Aus `software/` installieren:

```powershell
uv sync --locked --extra models
uv sync --locked --project unlimited_ocr_runtime
```

Wenn `uv` nicht im PATH liegt, dieselben Befehle mit `.\.tools\uv.exe` ausführen.
Das Hauptprojekt muss installiert sein; der Worker wird aus dessen Adapter über
lokale Prozesspipes angesprochen und einmal pro Methode geladen. Es werden keine
Dokumente auf einen HTTP-Server geschickt.

## Modellgewichte und Sicherheit

Festgelegt ist `baidu/Unlimited-OCR`, Revision
`8249d20b2822a7d8a4c22c8d8c9069b5ac36bda3` (MIT). Ein expliziter Download:

```powershell
.\.venv\Scripts\participant-bench.exe download-models --config configs/unlimited-ocr.yaml --method unlimited_ocr --transport range
```

Der Download wählt ausschließlich die im Safetensors-Index referenzierte
Gewichtdatei sowie Konfiguration/Tokenizer. Eine zusätzlich angebotene zweite
Gewichtdarstellung wird nicht doppelt heruntergeladen. Etwa 6,2 GiB Gewichte;
das ist eine Downloadgröße und keine Aussage über den gemessenen VRAM-Bedarf.
SHA256-Prüfsummen und die Revision stehen in `models/unlimited-ocr/download_manifest.json`.
Abgebrochene Bereichsdownloads können mit demselben Befehl fortgesetzt werden.

Bei Inferenz gelten `local_files_only=True` und `trust_remote_code=False`.
Der Worker deaktiviert Hub-Zugriffe und Telemetrie. Python-Dateien aus dem
Modellrepository werden nicht heruntergeladen oder ausgeführt. Die native
Transformers-Implementierung unterstützt den gewählten Modelltyp; der ältere
Baidu-Pfad mit `trust_remote_code=True` ist nicht aktiviert und würde eine
ausdrückliche separate Freigabe erfordern. Native Lader prüfen fehlende oder
unerwartete Gewichte, statt unbemerkt zufällig initialisierte Parameter zu nutzen.

## Starten

Nur die PDFs im vorhandenen CV-Testordner, mit lokaler LLM-Zuordnung:

```powershell
.\start_unlimited_cv_test.cmd
```

Oder explizit reine OCR ohne Teilnehmerzuordnung:

```powershell
.\.venv\Scripts\participant-bench.exe run --input data/cv-test-20261020-093337 --config configs/unlimited-ocr.yaml --offline
```

Für die konservative Tabellenbaseline ohne LLM `configs/unlimited-ocr-table.yaml`
verwenden. Die neue Kombination verwendet `configs/unlimited-ocr-llm.yaml`.
Begründung, Quellzellenprüfung und Zuordnung vorhandener OCR ohne Wiederholung:
[Teilnehmer zuordnen](unlimited-assignment.md).
Für einen Vergleich mit allen vorhandenen Ansätzen:

```powershell
.\.venv\Scripts\participant-bench.exe run --input data/cv-test-20261020-093337 --config configs/benchmark-unlimited.yaml --offline
```

Der letzte Befehl führt die Verfahren nacheinander aus. Seit der GPU-Anpassung
lädt OCR/LLM denselben 8B-Checkpoint mit LLM.int8 vollständig auf die GPU;
VLM bleibt bei BF16. Dafür einmal `uv sync --locked --extra models` ausführen.
Details und Qualitätsgrenzen: [GPU-Ausführung](gpu-inference.md). Die bestehenden
Startdateien werden nicht stillschweigend um ein zusätzliches Modell erweitert.
Im Vierervergleich ist Unlimited-OCR ausdrücklich zusammen mit dem lokalen LLM
konfiguriert. Damit sind strukturierte Feldmetriken möglich; die reine OCR-Leistung
wird zusätzlich und getrennt über `evaluate-ocr` bewertet.
Andere Verzeichnisse und Einzelversuche: `--input` auf einen Ordner mit den
gewünschten Dateien setzen. PDF, PNG, JPG und JPEG werden in den Unlimited-
Konfigurationen unterstützt. Bilder behalten ihre Pixelauflösung; EXIF-Ausrichtung
wird berücksichtigt. PDF-Seiten werden mit PyMuPDF gerendert. Die Originale
bleiben unverändert. Die Aufnahme von Bilddateien ist für bisherige Konfigurationen
standardmäßig ausgeschaltet (`pdf.include_images: false`).

## GPU-Einstellungen

Batchgröße 1, jede Seite einzeln (`page_processing: single_page`). BF16 wird bei
Unterstützung bevorzugt; andernfalls wird bei `precision: auto` FP16 gewählt und
die tatsächliche Präzision protokolliert. Es gibt keine automatische CPU-Inferenz.
Standard: dynamische Bildausschnitte (`crop_to_patches: true`), SDPA,
4096 neue Tokens, deterministische Generierung, kleines getrennt gemessenes Warm-up.
Die Bildausschnittverarbeitung des Modells ersetzt keine manuelle Seitenauswahl.

Einstellungen liegen unter `models.unlimited_ocr.options`, die Tokenzahl unter
`models.unlimited_ocr.max_new_tokens`. Speicherfehler führen zu einer klaren
Fehlermeldung; Auflösung, Bildmodus oder Tokenzahl werden nicht heimlich geändert.
Für einen expliziten Vergleich kann `crop_to_patches: false` den globalen
1024-Pixel-Modus aktivieren. Dies kann kleine Namen schlechter lesbar machen und
muss separat bewertet werden. Änderungen benötigen einen neuen Lauf.
Mehrere Seiten gemeinsam werden vorerst nicht angeboten: deren Stabilität auf
16 GB wurde nicht nachgewiesen. Die offiziell beschriebene Funktion allein ist
kein Hardwaretest.

## Ausgabe, Namen und Zuordnung

Alles liegt im üblichen `runs/<RUN_ID>/`:

| Ausgabe | Bedeutung |
| --- | --- |
| `report.html` | Übersicht, vollständiger OCR-Text, Teilnehmer falls zugeordnet |
| `unlimited_ocr/raw_text/<PAGE_ID>.txt` | Unveränderte dekodierte Modellantwort einschließlich Formatmarkern |
| `unlimited_ocr/ocr_text/<PAGE_ID>.txt` | Davon abgeleitete Darstellung mit Tabellenmarkup |
| `unlimited_ocr/raw-<PAGE_ID>.json` | Layoutregionen, Zellbelege, Tokenzahlen, Inferenzzeiten und Ressourcen |
| `unlimited_ocr/extractions.jsonl` | Gemeinsames Ergebnisschema; `output_kind` unterscheidet OCR und strukturierte Ausgabe |
| `unlimited_ocr/timings.csv`, `document_timings.csv` | Zeiten je Seite und Summe je Dokument; gemeinsame Modellinitialisierung separat |
| `unlimited_ocr/resources.json` | Laufzeitversionen, Hardware, Warm-up sowie CUDA-Allocated-/Reserved-Peaks |

Es werden keine Wahrscheinlichkeiten aus Tokenzahlen oder Modellbehauptungen
erfunden. Bounding Boxes des Modells bezeichnen Layoutregionen und sind keine
gemessenen Wortpositionen. Eine Unterschrift wird nicht aus fehlendem Text als
vorhanden oder leer klassifiziert.

Der Tabellenparser akzeptiert HTML- und einfache Markdown-Tabellen. Er liest
Header und feste Zellpositionen. Ein leerer Benutzer bleibt leer; Kurzzeichen
werden nicht nach links verschoben. Führende Nullen, Umlaute, Großschreibung
und Bindestriche bleiben erhalten. Erlaubte syntaktische Bereinigung:
HTML-Entities dekodieren, äußere Leerzeichen entfernen und Zeilenumbrüche innerhalb
einer Zelle zu Leerzeichen zusammenführen. Keine Namenskorrektur, kein Wörterbuch,
keine Ergänzung aus Excel oder Ground Truth. Die ursprünglichen Zellen bleiben
in `row_evidence` einschließlich Tabellen- und Quellzeilenindex erhalten.

Verbundene Zellen, widersprüchliche Überschriften und unterschiedliche Zellzahlen
führen zur Nachkontrolle. Ohne eindeutige Zuordnung bleibt die reine OCR-Ausgabe
erhalten. Es werden keine gleichmäßig verteilten Personenkoordinaten erfunden.
Unterschriften bleiben unbekannt, bis eine eigenständige visuelle Prüfung erfolgt.
Der generative OCR-Text selbst kann Lesefehler oder erfundene Inhalte enthalten;
ein verlustfreier Parser beweist daher noch keine korrekte Erkennung.

## Evaluation

Die reine OCR-Konfiguration wird nicht mit strukturierten Teilnehmermodellen
auf Feld-F1 oder Excel-Treffern verglichen. Die Tabellenkonfiguration ist eine
eigenständige Kombination aus OCR und regelbasierter Nachverarbeitung; dort
bleiben nicht extrahierte Personen im Nenner der normalen Feldbewertung.
Zusätzlich zur bisherigen normalisierten Feldbewertung wird `raw_exact_match`
ausgewiesen: exakter Zeichenkettenvergleich ohne Ausgleich der Großschreibung
oder Leerzeichen. So verschwinden Schreibweisenfehler in Namen nicht hinter
der vorhandenen Vergleichsnormalisierung.

Für CER/WER unabhängige Seitentranskripte über die bestehende Referenzstruktur
anlegen, die TXT-Dateien manuell bearbeiten und in `pages.csv` erst nach Prüfung
`text_reviewed=true` setzen. Anschließend, ohne erneute Inferenz:

```powershell
.\.venv\Scripts\participant-bench.exe evaluate-ocr --run runs/DEINE_RUN_ID --references data/ocr-reference-v1
```

Das vergleicht den abgeleiteten Lesetext ohne Tabellenmarkup mit der manuellen
Transkription, einmal in ursprünglicher Schreibweise und einmal mit expliziter
NFC-/Leerraumnormalisierung. Großschreibung wird dabei nicht ignoriert.
Ergebnisse und Referenzhashes stehen unter `unlimited_ocr/text_evaluation/`.
Seiten ohne Referenz werden ausgewiesen, nicht als fehlerfrei angenommen.
Excel-Abgleich ist nur für die strukturierte Tabellenvariante sinnvoll.
Entwicklungs-, Validierungs- und Testgruppen weiterhin dokumentweise trennen;
die Texterkennung oder Regeln nicht anhand finaler Testreferenzen optimieren.

## Offizielle Quellen

- [Baidu-Repository und Referenzinferenz](https://github.com/baidu/Unlimited-OCR)
- [Festgelegte Modellrevision](https://huggingface.co/baidu/Unlimited-OCR/tree/8249d20b2822a7d8a4c22c8d8c9069b5ac36bda3)
- [Native Transformers-Dokumentation](https://github.com/huggingface/transformers/blob/main/docs/source/en/model_doc/unlimited_ocr.md)
- [Paper](https://arxiv.org/abs/2606.23050)

Technische Tests und tatsächlich gemessene Inferenz stehen im
[Verifikationsprotokoll](verification.md). Ersetzte Modellaufrufe in Unit-Tests
sind kein Nachweis erfolgreicher GPU-Inferenz oder besserer Namensqualität.
