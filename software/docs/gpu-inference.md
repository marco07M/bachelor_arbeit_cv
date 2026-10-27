# Lokale Ausführung auf der GPU

Die Konfigurationen `local.yaml`, `imported.yaml` und `benchmark-unlimited.yaml`
verwenden weiterhin Qwen3-8B mit derselben festen Revision. Auf der vorhandenen
RTX 4090 Laptop mit 16 GiB VRAM werden dessen lineare Schichten beim Laden mit
bitsandbytes 0.48.1 / LLM.int8 quantisiert. Vorhandene Safetensors bleiben
unverändert; es ist kein anderer Modelldownload erforderlich. Embeddings,
Ausgabekopf und nicht quantisierte Operationen verwenden den konfigurierten
`dtype: bfloat16`; LLM.int8 verarbeitet empfindliche Ausreißer mit höherer
Präzision. Der Hinweis auf die interne Konvertierung von BF16 nach FP16 in
MatMul8bitLt ist erwartbar. Das ist keine Änderung der Parameterzahl, kann aber
Ausgaben verändern; eine unveränderte Erkennungsqualität ist nicht nachgewiesen.

Die ursprünglichen BF16-Gewichte benötigen 16.381.470.720 Bytes, etwa 15,26 GiB.
Damit passen sie zusammen mit KV-Cache, Aktivierungen und Desktop nicht vollständig
auf die vorgefundene GPU. Im früheren Lauf lagen deshalb 15 von 36 Transformer-
Schichten sowie der Ausgabekopf auf der CPU. Ein bloß erhöhtes GPU-Budget löst
diesen Kapazitätsengpass nicht vollständig.

## Start

Aus `software/` einmal die zum Lockfile passende Modellumgebung einrichten:

```powershell
uv sync --locked --extra models
```

Die Umgebung dieses Laptops wurde bereits aktualisiert. Danach wie bisher:

```powershell
.\start_lokal_cv_test.cmd
```

Oder alle vier Verfahren einschließlich Unlimited-OCR vergleichen:

```powershell
.\.venv\Scripts\participant-bench.exe run --input .\data\cv-test-20261020-093337 --config .\configs\benchmark-unlimited.yaml --offline
```

Einen **neuen Lauf** starten. Alte Ergebnisse und Berichte ändern sich nicht;
`--resume` mischt wegen der veränderten Konfiguration/Softwareidentität keine
früheren BF16-/Offload-Ergebnisse mit neuen int8-Ergebnissen.

## Speicherzuordnung

```yaml
models:
  ocr_llm:
    # Weitere Modelleinstellungen aus local.yaml beibehalten.
    dtype: bfloat16
    quantization: int8
    device: cuda
    gpu_memory_gib: 11
    prefill_chunk_size: 1024
```

`device: cuda` bedeutet vollständiges Laden auf CUDA-Gerät 0. CPU-/Platten-
Offload ist dabei ausgeschaltet. Die tatsächlichen Parametergeräte werden nach
dem Laden geprüft. `gpu_memory_gib` plus 2 GiB Reserve wird vorab mit dem freien
VRAM verglichen. Zusätzlich wird der PyTorch-CUDA-Allocator für die Lebensdauer
des Modells auf den zu Beginn freien VRAM abzüglich 2 GiB begrenzt. Eine bereits
strengere Prozessgrenze bleibt erhalten. Beim Entladen oder fehlgeschlagenen
Modellladen wird die vorherige Grenze wiederhergestellt. Das verhindert, dass
PyTorch große Speicheranforderungen unbemerkt in Windows Shared GPU Memory
verlagert. Andere Prozesse oder GPU-Bibliotheken können weiterhin außerhalb
dieser Grenze Speicher belegen. Bei Speichermangel wird ein Fehler protokolliert und
keine langsamere Ersatzberechnung gestartet. Andere GPU-Prozesse gegebenenfalls
vor dem Start schließen. Die maximalen Eingabe-/Ausgabetokens bleiben unverändert.

Beim Modellwechsel werden nach CUDA-Synchronisation auch cuBLAS-Workspaces
freigegeben. Sie hielten auf diesem Windows-System sonst mehrere GiB reserviert,
obwohl die Modelltensoren bereits gelöscht waren. Dafür fragt der Adapter den
internen Workspace-Clear-Hook der festgelegten PyTorch-2.8-Version defensiv ab;
die Kombination aus Entladen und anschließendem VLM-Laden wurde lokal geprüft.

`prefill_chunk_size: 1024` nutzt die native Transformers-Verarbeitung des
vollständigen OCR-Prompts in mehreren Abschnitten mit gemeinsamem KV-Cache.
Alle Wörter, Zeilengruppen und Positionen bleiben erhalten. Damit wird die
Spitzenbelegung beim Einlesen langer Prompts reduziert. Bei kurzen Prompts ist
die Aufteilung unnötig; das VLM verwendet sie nicht. `null` deaktiviert die Option.

Im `progress.log` stehen Quantisierung, Modellspeicher und Parametergeräte.
`ocr_llm/resources.json` enthält zusätzlich `device_map`, `parameter_devices`,
`quantization`, `weight_memory_bytes`, `cuda_allocator_limit_bytes`,
`prefill_chunk_size` und CUDA-Peaks. Der Speicherkonsum der
separaten Unterschriftenprüfung wird dort gesondert erfasst.

Qwen3-VL-4B für Seitenauswertung und Unterschriften bleibt in BF16 und wird
ebenfalls vollständig auf die GPU gelegt. Unlimited-OCR nutzt bereits seine
eigene CUDA-Laufzeit. PDF-Rendering, Tesseract, Tabellenregeln und Export bleiben
CPU-Arbeit; Tesseract erhält durch diese Änderung keinen CUDA-Modus. Es werden
weiterhin keine Dokumentinhalte an externe Dienste übertragen.

## BF16 als Referenz und Qualitätsprüfung

Für einen späteren BF16-Vergleich `quantization: none` setzen. Auf dieser 16-GiB-
GPU zusätzlich `device: auto` und beispielsweise `gpu_memory_gib: 10` verwenden;
dies erlaubt die langsamere CPU-Auslagerung. Auf einer GPU mit ausreichend
freiem Speicher kann BF16 mit `device: cuda` laufen. Auch `device: cpu` benötigt
`quantization: none`. 8-Bit-Laden ist nur für den lokalen OCR-LLM-Adapter freigegeben.

Die Originalgewichte und Referenzdaten werden nicht verändert. Quantisierte
und BF16-Ausgaben auf denselben manuell geprüften Dokumenten vergleichen:
buchstäbliche Feldtreffer (`raw_exact_match`), führende Nullen, leere Benutzer-
zellen, Zeilenzuordnung, fehlende Personen und manuelle Nachkontrolle. Einzelne
synthetische Funktionsprüfungen belegen keine gleichbleibende Qualität auf
echten Scans. Alte Laufzeiten auf anderen Dokumenten sind kein kontrollierter
Geschwindigkeitsvergleich.

Offizielle Grundlagen: [Transformers 4.57 / bitsandbytes](https://huggingface.co/docs/transformers/v4.57.1/quantization/bitsandbytes)
und [bitsandbytes 0.48.1: CUDA-/Windows-Unterstützung](https://huggingface.co/docs/bitsandbytes/v0.48.1/en/installation),
[PyTorch 2.8: Allocator-Grenze](https://docs.pytorch.org/docs/2.8/generated/torch.cuda.memory.set_per_process_memory_fraction.html)
und der native `_prefill_chunking`-Pfad in der lokal installierten Transformers-
Version 4.57.6 (`generation/utils.py`).
