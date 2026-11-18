# GPU-Ausführung des Hauptvergleichs

## Größeres VLM im Testframework (18.11.2026)

Die lokalen Testframework-Starter verwenden jetzt ein ausdrücklich separates
8B-Profil. `benchmark-vlm8b.yaml` enthält die bisherigen sechs Verfahren;
`benchmark-five-vlm8b.yaml` die Nutzerwahl aus Regeln/Tesseract+LLM/Paddle+LLM/
VLM/OCR+VLM, `benchmark-four-vlm8b.yaml` dieselbe Viererauswahl ohne Tesseract+LLM.
Das feste 4B-Hauptvergleichsprofil `benchmark.yaml` wird nicht umdefiniert.
API-Modelle und andere ausdrücklich gewählte Profile bleiben unverändert.

| Einstellung | Größeres VLM |
|---|---|
| Checkpoint | [Qwen/Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct/tree/0c351dd01ed87e9c1b53cbc748cba10e6187ff3b) |
| Revision | `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b` |
| Lokaler Ordner | `models/qwen3-vl-8b` |
| Gewichte herunterladen | 17.534.339.512 Bytes, vier Safetensors-Dateien, zusätzlich Processor/Tokenizer |
| Speicherformat bei Inferenz | LLM.int8 im Sprachdecoder; `visual` und `lm_head` ausgenommen, sonst BF16 |
| Geräte | explizit vollständig `cuda:0`, kein CPU-Offload |
| GPU-Startbudget | 11 GiB plus vorhandene 2-GiB-Reserve |
| Attention/Budgets | unverändert SDPA repeated KV, 1.048.576 Pixel, 12.000 Eingabe-/8.192 Ausgabetoken |

BF16-Gewichte allein überschreiten den für Aktivierungen verfügbaren Speicher
dieser 16-GiB-Laptop-GPU. Deshalb wird die bereits installierte bitsandbytes-
Integration ausdrücklich auch für die VLM-Sprachschichten verwendet. Der
Bildencoder einschließlich Mergern und der Ausgabekopf werden nicht quantisiert.
Details zur [Transformers-/bitsandbytes-Integration](https://huggingface.co/docs/transformers/v4.57.1/en/quantization/bitsandbytes).
Es gibt keinen automatischen Wechsel von Quantisierung, Modell oder Auflösung.

Die Originalgewichte bleiben im Downloadordner, LLM.int8 wird beim Laden
angewendet. Einrichtung aus `software/`:

```powershell
.\.venv\Scripts\participant-bench.exe download-models --config configs/benchmark-vlm8b.yaml --method vlm --transport range
start_testframework_5.cmd --documents 3
```

Nur öffentliche Modellgewichte werden heruntergeladen; Dokumentinferenz bleibt
lokal. Die bestehende Prüfsummenprüfung und Modellidentität unterscheiden 4B und
8B. Neue Modellparameter erzeugen neue Cachebindungen und müssen in einem neuen
Lauf ausgewertet werden; alte Berichte werden nicht umgeschrieben. Beide
Bildverfahren erhalten dieselbe vollständig identische Konfiguration.

Die Textmodelle, Extraktionsprompts, Bild-/Tokenbudgets, Ground Truth und Metriken
bleiben gleich. Ein Vergleich 4B-BF16 gegen 8B-int8 ändert trotzdem sowohl
Parameterzahl als auch numerisches Gewichtsformat; Verbesserungen sind nicht
allein der Parameterzahl zuzuschreiben und erst durch neue Extraktion belegt.
Speicherreserven sind keine Garantie gegen OOM bei jeder Seite. Ein kleiner
synthetischer Funktionstest ersetzt keinen vollständigen Referenzvergleich.

## Festes 4B-Hauptprofil

Das aktuelle Hauptprofil ist configs/benchmark.yaml. Es nutzt genau
Qwen3-4B-Instruct-2507 für Text und Qwen3-VL-4B-Instruct für Bilder.
Verbindliche Revisionen und Installationsbefehle:
[Sechs lokale Verfahren](local-methods.md).

Die tatsächliche Hardware wird beim Start in environment.json erfasst.
Auf diesem Laptop: RTX 4090 Laptop, rund 16 GiB VRAM. Modelle werden
nacheinander geladen und wieder vollständig entladen. CUDA-Zuordnung und
Parametergeräte werden überprüft. PDF-Rendering, Tesseract und Export bleiben
CPU-Aufgaben; Paddle, TableFormer und Qwen verwenden die konfigurierte GPU.

## Speicher

Hauptprofil: BF16, keine Quantisierung und kein CPU-Offload.
Bei fehlender BF16-Unterstützung wird FP16 verwendet und ausgewiesen.
Int8 bleibt eine bewusst konfigurierte Option ausschließlich für das Textmodell.

Vor dem Laden werden Modellbudget und 2 GiB Reserve geprüft. Der CUDA-Allocator
wird auf den zu Beginn verfügbaren Speicher abzüglich dieser Reserve begrenzt;
eine bereits strengere Prozessgrenze bleibt erhalten. Nach dem Entladen wird
die vorherige Grenze wiederhergestellt. Fehlender Speicher führt zu einem
ausgewiesenen Fehler, nicht zu einem anderen Modell oder verstecktem CPU-Offload.

attention: sdpa_repeated_kv verwendet äquivalente Attention mit explizit
wiederholten Key-/Value-Köpfen und denselben kausalen Masken. Der installierte
Windows-PyTorch-Build besitzt keinen Flash-Attention-Kernel; natives GQA kann
sonst den speicherintensiven mathematischen Kernel wählen. Die neue Variante
ermöglicht den vorhandenen effizienten GPU-Kernel. Numerische Gleichwertigkeit
wird mit Masken, vollständigen Sequenzen und Ein-Token-Decoding getestet.
Es werden keine Dateien installierter Bibliotheken verändert.

Beide VLM-Verfahren müssen identische Modellparameter einschließlich dieser
Option verwenden. attention: sdpa bleibt für ausdrücklich getrennte Versuche
verfügbar. Änderungen des Kernels sind zu dokumentieren; kleine numerische
Unterschiede können trotz gleicher mathematischer Funktion Ausgaben beeinflussen.

Bildauflösung, Eingabe- und Ausgabegrenzen sind konfigurierbar. Das Hauptprofil
verwendet maximal 1.048.576 Bildpixel, 12.000 Eingabetoken und 8.192 Ausgabetoken.
Zu lange Eingaben werden nicht still gekürzt. Ausgabeabbrüche bleiben Fehler
mit gespeicherter Rohantwort. Das Textmodell kann den vollständigen Prompt
in konfigurierten Prefill-Abschnitten verarbeiten.

## Messen und vergleichen

resources.json und timings.csv trennen Laden, Warm-up, Erkennung, Zuordnung,
Generierung und gemeinsame Vorbereitung. Cache-Hits und zugerechnete OCR-Zeiten
stehen separat. Der CUDA-Allocator misst nicht den gesamten Treiberbedarf oder
andere Prozesse. Bei Paddle stammt der GPU-Wert gegebenenfalls vom separaten
Worker; fehlende Werte bleiben unbekannt.

Die Laufzeit hängt auch von Netz-/Akkubetrieb, GPU-Takt und anderen Prozessen ab.
Ein Funktionstest bei stark gedrosseltem GPU-Takt ist kein belastbarer
Durchsatznachweis für 6.000 PDFs. Entwicklung, Validierung und finale Tests
unter dokumentierten, vergleichbaren Betriebsbedingungen ausführen.

## Frühere Modelle

Gespeicherte Läufe und ältere Gewichte werden nicht verändert.
1.7B- und frühere Text-8B-Konfigurationen gehören zu früheren Experimenten und sind keine
Bestandteile des aktuellen Hauptvergleichs. Nach Code-/Modelländerungen einen
neuen Lauf starten; --resume setzt nur identische Konfigurationen fort.
