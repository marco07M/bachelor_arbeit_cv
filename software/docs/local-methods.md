# Sechs lokale Vergleichsverfahren

Alle Befehle aus software/ ausführen. Das verbindliche Hauptprofil ist
[configs/benchmark.yaml](../configs/benchmark.yaml). Beide lokalen Modellstarter
und das Testframework verwenden dieses Profil. benchmark-unlimited.yaml ist
ein kompatibler Verweis auf das neue Hauptprofil.

## Verfahren

| Verfahren | Erkennung / Eingabe | Strukturierte Zuordnung |
| --- | --- | --- |
| ocr_raw | Tesseract, deu+eng, CPU | Keine: Rohtext, Wörter, Positionen, Engine-Konfidenzen |
| ocr_llm | Derselbe Tesseract-Text mit Zeilen und Positionen | Qwen3-4B-Instruct-2507, ausschließlich Text |
| paddle_llm | PP-StructureV3: eigene Texte, Tabellen und Positionen | Dasselbe Qwen3-4B-Instruct-2507 |
| docling | Native PDF-Verarbeitung bzw. lokale OCR, TableFormer accurate | Deterministisch anhand gedruckter Überschriften, ohne LLM |
| vlm | Ausschließlich das gemeinsame Seitenbild | Qwen3-VL-4B-Instruct |
| ocr_vlm | Dasselbe Bild plus Paddle-OCR-Belege | Dasselbe Qwen3-VL-4B-Instruct |

Damit werden OCR, textgestützte Extraktion, strukturorientiertes Parsing und
visuelle Extraktion getrennt verglichen. ocr_vlm untersucht gezielt den
Zusatznutzen von OCR-Hinweisen. Es ist ein eigener Versuch und kein Fallback.
ocr_raw erhält keine Teilnehmer-/Feldgenauigkeit, weil es keine Datensätze erzeugt.

Es gibt genau zwei generative Basismodelle im Hauptvergleich:

| Aufgabe | Repository | Revision | Lokaler Ordner |
| --- | --- | --- | --- |
| Text | [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) | cdbee75f17c01a7cc42f958dc650907174af0554 | models/qwen3-4b-instruct-2507 |
| Bild / Hybrid | [Qwen/Qwen3-VL-4B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct) | ebb281ec70b05090aa6165b016eac8ec08e71b17 | models/qwen3-vl-4b |

Das ältere models/qwen3-4b ist ein anderes Modell und wird nicht als
Instruct-2507 verwendet. Alte 1.7B-/8B-Gewichte bleiben erhalten, werden aber
vom Hauptprofil nicht geladen. Fehlende Gewichte bedeuten unavailable;
es gibt keinen automatischen Modellwechsel.

## Einmalig einrichten

~~~powershell
uv sync --locked --extra models
uv sync --locked --project paddle_structure_runtime
uv sync --locked --project docling_runtime
.\.venv\Scripts\participant-bench.exe download-models --config configs/benchmark.yaml --transport range
.\.venv\Scripts\participant-bench.exe setup-structures --config configs/benchmark.yaml --download
~~~

Downloads sind ausdrücklich getrennte Einrichtungsschritte. Während run werden
keine Modelle heruntergeladen und keine Dokumente an Dienste übertragen.
Paddle und Docling nutzen eigene uv.lock-Dateien und Umgebungen.
Hauptumgebung: PyTorch 2.8.0/CUDA 12.6, Transformers 4.57.6. Quellen und Revisionen
der Strukturmodelle: structure_runtime/*_sources.json. Modell-Manifeste enthalten
vor dem Laden geprüfte SHA256-Prüfsummen. Tesseract mit deu/eng muss vorhanden sein.

~~~powershell
.\.venv\Scripts\participant-bench.exe doctor --config configs/benchmark.yaml
~~~

Auf diesem Laptop wurden die exakten Textgewichte am **02.11.2026** eingerichtet,
anhand des Download-Manifests geprüft und mit echter CUDA-Inferenz ausgeführt.
Auf einem neuen Rechner dieses Modell bewusst einrichten:

~~~powershell
.\.venv\Scripts\participant-bench.exe download-models --config configs/benchmark.yaml --method ocr_llm --transport range
~~~

Ohne --download prüft setup-structures nur vorhandene Dateien. Es werden keine
Schlüssel benötigt. Der Firmen-API-Einstieg bleibt ein separates Projekt und
gehört nicht zum lokalen Hauptvergleich.

## Starten

~~~powershell
.\start_alle_lokalen_modelle.cmd
~~~

Der Starter liest alle PDFs unter data/cv-test-20261020-093337/ rekursiv.
Andere Eingabe oder nur ein Verfahren:

~~~powershell
.\.venv\Scripts\participant-bench.exe run --input "data/pdfs_eingabe" --config configs/benchmark.yaml --offline
.\.venv\Scripts\participant-bench.exe run --input "data/pdfs_eingabe" --config configs/benchmark.yaml --method ocr_vlm --offline
~~~

Einzelprofile: ocr-raw.yaml, paddle-llm.yaml, docling.yaml, ocr-vlm.yaml.
Mit Excel-/CSV-Referenz: PDFs nach testframework/eingabe_pdfs/, Referenz nach
testframework/referenz/, anschließend start_testframework.cmd ausführen.
Die Class ID im PDF-Dateinamen begrenzt alle Vergleichskandidaten.
Referenzdaten gelangen niemals in Modell-Prompts.

Alle Seiten werden ohne Dokumentart-Klassifikation verarbeitet. Eine Auswahl
erfolgt vorab manuell bzw. über das bestehende Manifest. Rendering, Orientierung
und konfiguriertes Deskew werden gemeinsam ausgeführt. Originale bleiben
unverändert. Tesseracts eigene Linienentfernung betrifft nur dessen OCR-Bild.
VLM und Strukturmodelle erhalten das gemeinsame Bild; Docling kann vorhandenen
PDF-Text nativ nutzen.

## Kontrollierter Hybridversuch

vlm und ocr_vlm verwenden dieselben Gewichte, Revision, Quantisierung,
Bildauflösung, Ausgabegrenze, Sampling-Parameter, Grundanweisungen und dasselbe
Antwortschema. Die Hybridkonfiguration wird aus models.vlm übernommen;
abweichende Parameter werden abgelehnt. Nur der Hybrid erhält zusätzlich
kompakte OCR-Texte, Tabellenzellen, Koordinaten und verfügbare Engine-Konfidenzen.
Die ursprünglichen Paddle-Daten bleiben vollständig in den Rohdateien erhalten.
Wenn Paddle fehlt, wird der Hybrid unavailable statt unbemerkt bildbasiert.

## Feldzuordnung und Rollen

Die gedruckte Spalte **„Benutzer“** bezeichnet die **User ID** (`personnel_number`),
auch wenn „ID“ nicht dabeisteht. **„Benutzername“** ist die Namensspalte. Eine
Zeilennummer gehört ausschließlich in `row_ref`. Seit Promptversion
`participant-json-v21-visible-benutzer-headings` unterscheiden beide
Bildverfahren diese Überschriften ausdrücklich, einschließlich einer numerischen
ersten Benutzer-Spalte. Ein Modell darf sie nicht allein wegen der Zahlenwerte
als „Nr“ umbenennen. Fehlen eindeutige Spaltenbelege weiterhin, bleibt der Wert
unklar; die Nachverarbeitung deutet ihn nicht anhand seines Zahlenformats um.
Auf Seiten ohne sichtbare Überschriften bleiben die entsprechenden Überschriften
unbekannt; ein Kurzzeichen darf keine erfundene Benutzer-Spalte begründen.

Aktiv sind Doclings native Tabellenzellen mit ACCURATE, deaktiviertem Cell Matching
und Standard-OCR. Paddle behält `legacy_v13`: Die erweiterte Übergabe
`positioned_v14` mit Positionen, Konfidenzen, Zellbeziehungen und Überschriftenrollen
ist über `configs/paddle-positioned.yaml` prüfbar, zeigte aber keinen Vorteil und
eine Regression im Entwicklungstest. Die frühere Docling-Konfiguration ist als
`configs/structures-baseline.yaml` verfügbar. Full-Page-OCR und Tesseract PSM 11
bleiben getrennte Experimente. Befunde, Grenzen und reproduzierbare Befehle:
[Docling-/Paddle-Abschlussbericht](structure-optimization.md).

Tesseract-LLM und Paddle-LLM verwenden ausschließlich die eigenen OCR-Belege;
ein VLM ergänzt keine Namen. Das LLM erhält lesbare Zeilen, Spalten,
Quellkennungen und vorhandene Positionen. Ausgegebene Werte werden gegen diese
Belege geprüft. Rohantworten und exakte Modelleingaben werden gespeichert.
Führende Nullen bleiben im Export erhalten; der Referenzabgleich kann sie
gemäß seiner Konfiguration ignorieren. Konfidenzen sind nicht kalibriert.

Docling ordnet anhand **gedruckter Überschriften** zu, auch bei geänderter
Spaltenreihenfolge, verbundenen Zellen oder mehrzeiligen Überschriften.
Bekannte Aliase: Benutzer/User ID, Kurzzeichen/Organization, Vorname, Nachname.
Für kombinierte Namenszellen gilt auf Nutzerwunsch standardmäßig **Nachname
zuerst, danach alle Vornamen**. `Muster-Schmidt, Anna Maria Luise` wird als
Nachname `Muster-Schmidt` und Vorname `Anna Maria Luise` übernommen. Alles vor
dem Komma bleibt zusammen, einschließlich mehrteiliger Nachnamen wie
`von der Wiese`. Ein Bindestrich trennt keine Namensgruppe. Klare getrennte
Vor-/Nachnamensspalten haben Vorrang vor dieser Standardannahme.

Docling kann außerdem eine unmarkierte Zelle mit genau zwei Namensgruppen
gemäß dem Standard zuordnen. Bei drei oder mehr ungetrennten Wörtern kann
ein doppelter Nachname mit zusätzlichen Vornamen verwechselt werden. Ohne
weitere Belege bleiben solche Aufteilungen prüfpflichtig; bereits beobachtete
Modellgruppen und der vollständige Quelltext bleiben erhalten. Unvollständige
Personen werden wegen dieser Mehrdeutigkeit nicht entfernt.

Seit `participant-json-v22-family-first-name-groups` erhalten OCR-LLM, VLM
und Hybrid dieselbe Namensregel. `name_order.basis=document/default/unknown`
unterscheidet Dokumentbeleg und Standardannahme. Spätere eindeutige Überschriften
können die Standardannahme ersetzen. Kommagrenzen korrigieren belegbare falsche
Teilungen vor der Zellprüfung; Rohantworten bleiben unverändert. HTML und
`document_name_orders.csv` zeigen Quelle, Neuaufteilungen und Prüffälle.
Es gibt keine Namenswörterbücher oder fest codierten Pixelgrenzen.
Auf Folgeseiten dürfen ausschließlich passende Spaltenüberschriften
übernommen werden, keine Personenwerte. Widersprüchliche Zellbreiten und
fehlende Überschriften werden nicht geraten. Native TableFormer-Zellen liefern
Positionsbelege, soweit verfügbar.

Eine leere Benutzer-ID verschiebt das Kurzzeichen nicht in die ID-Spalte.
Fehlender OCR-Text allein beweist keine leere Zelle. Kursleiter/Trainer werden
nur bei belegter Rolle ausgeschlossen; unsichere Rollen bleiben zur Prüfung.
Ausschlüsse stehen separat in excluded_instructors.csv.

## Unterschriften getrennt behandeln

Im Hauptprofil ist signature.backend: opencv aktiv. Diese gemeinsame Prüfung
entscheidet nur sicher leere, lokalisierte Felder negativ. Nicht lokalisierte
oder unklare Felder bleiben null/uncertain. OCR-Text beweist keine Unterschrift.
Direkte VLM-Befunde sind als vlm_page von der gemeinsamen Prüfung getrennt.

Optional aktiviert signature.backend: vlm dieselbe zusätzliche visuelle
Detailprüfung für strukturierte Verfahren. Aufrufe, Laufzeiten und Ergebnisse
werden separat protokolliert. Das Testframework besitzt keine Signaturreferenz
und schaltet diesen Zusatz standardmäßig aus. Präsenz ist kein Echtheitsnachweis.

## Ergebnisse und Hybridanalyse

Jeder neue Lauf schreibt runs/<Lauf-ID>/report.html, config.yaml,
Modellidentitäten, Versionen, Ressourcen sowie Rohdaten und Teilnehmer je Methode.
Der Bericht unterscheidet benötigte und tatsächlich verwendete Modelle.
Status: success, partial (Prüffälle), failed oder unavailable. Fehlendes
Zuordnungs-LLM bedeutet keine erfundenen Teilnehmer; OCR-Rohdaten bleiben erhalten.

- raw-*.json: Erkennung, Positionsbelege und Zuordnungen.
- ocr_text/, ocr_words/, model_input/ bzw. assignment/: Klartext und Modelleingaben.
- participants.xlsx, methods.csv, resources.json, timings.csv: Export und Messwerte.
- hybrid_analysis.html, hybrid_fields.csv, hybrid_analysis.json: VLM/Hybrid-Vergleich.
- Testframework: details.html und Namenszuordnungsbericht mit CSV-Details.

Die Hybridanalyse vergleicht pro derselben Referenzperson und demselben Feld:
corrected, regressed, both_correct, both_incorrect, Exact Match, Zeichendistanzen,
gepaarte CER, Datensatzgenauigkeit und Laufzeitdifferenz. Sie kontrolliert die
eingefrorenen VLM-Einstellungen, Bild-Hashes und die gemeinsame Promptversion.
Die bestehenden dokument-/klassenbezogenen Matching-Regeln gelten weiter.
Eine um ein Zeichen falsche ID bleibt beim Exact Match falsch.
Die gepaarte CER betrachtet Referenzfelder; Zusatzvorhersagen werden weiterhin
in den normalen Einzelmetriken bestraft. Maskierte Referenzfelder sind ausgeschlossen.

Ohne Ground Truth steht not_measured; es wird keine Verbesserung behauptet.
Synthetische Tests prüfen Softwareverhalten, nicht reale Erkennungsqualität.
Qualitätsaussagen benötigen manuell gelabelte, dokumentweise getrennte
Entwicklungs-, Validierungs- und Testdaten.

## GPU, Cache und Laufzeiten

Die Hardware wird beim Start erfasst. Dieser Laptop besitzt 16 GiB VRAM.
Modelle laufen nacheinander. Hauptprofil: CUDA, BF16, keine Quantisierung,
kein CPU-Offload. Ohne BF16-Unterstützung wird FP16 verwendet und protokolliert.
Int8 bleibt eine ausdrücklich konfigurierte Option für das Textmodell.

attention: sdpa_repeated_kv verwendet mathematisch gleichwertige Attention mit
wiederholten Key-/Value-Köpfen. So kann der Windows-PyTorch-Build ohne
Flash Attention seinen speichersparenden GPU-Kernel nutzen. Beide VLM-Verfahren
verwenden dieselbe Einstellung. attention: sdpa ist für getrennte Versuche möglich.

Paddle-Belege für den Hybrid können aus dem vorherigen paddle_llm-Schritt oder
dem lokalen Cache stammen. Ein warmer Cache benötigt keinen weiteren GPU-Worker.
Tatsächliche Laufzeit und zugerechnete vollständige Pipelinezeit werden getrennt
ausgewiesen: OCR-Kosten verschwinden bei Cache-Nutzung nicht.
Bei alten Cache-Dateien ohne Laufzeitmessung bleibt die vollständige Zeit unbekannt.
Tokenzahlen, Modellaufrufe, Warm-up, Ladezeit und Speicherwerte stehen separat
im Report; Limits werden nicht durch stille Promptkürzung umgangen.

Fortsetzen: --resume runs/<Lauf-ID>, nur bei unveränderter Konfiguration,
Software- und Eingabeidentität. Nach Änderungen einen neuen Lauf starten.
Bestehende Ergebnisse bleiben erhalten. Unlimited-OCR, ocr_rules und
paddle_structure bleiben als Legacy-Verfahren nutzbar, außerhalb des Hauptvergleichs.

## Synthetischer Funktionstest

~~~powershell
.\.venv\Scripts\python.exe scripts/make_benchmark_smoke.py --output data/benchmark-smoke-neu
.\.venv\Scripts\participant-bench.exe run --input data/benchmark-smoke-neu/pdfs --config configs/benchmark.yaml --ground-truth data/benchmark-smoke-neu/ground_truth.jsonl --offline
.\.venv\Scripts\python.exe -m pytest -q
~~~

Der Generator überschreibt keinen bestehenden Ordner. Die Referenz bleibt
getrennt von den Modelleingaben. Fehlende Modelle werden ehrlich ausgewiesen.
