# GPU-Ausführung des Hauptvergleichs

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
1.7B-/8B-Konfigurationen gehören zu früheren Experimenten und sind keine
Bestandteile des aktuellen Hauptvergleichs. Nach Code-/Modelländerungen einen
neuen Lauf starten; --resume setzt nur identische Konfigurationen fort.
