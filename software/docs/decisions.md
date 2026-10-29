# Technische und wissenschaftliche Entscheidungen

## Verbindlicher Hauptvergleich vom 29.10.2026

Das aktuelle Protokoll steht in [local-methods.md](local-methods.md) und
`configs/benchmark.yaml`: Tesseract-Rohtext, Tesseract/Qwen3-4B-Instruct-2507,
Paddle/Qwen3-4B-Instruct-2507, Docling/TableFormer ohne LLM, direktes
Qwen3-VL-4B-Instruct und dasselbe VLM mit Paddle-OCR-Hinweisen.
Die sechs Verfahren trennen Erkennung, semantische Zuordnung und den Zusatznutzen
von OCR für das VLM. Der Hybrid wird ausdrücklich gegen das identische direkte
VLM verglichen. Ohne Referenzdaten wird keine Qualitätsverbesserung behauptet.

Der Textmodell-Pin ist `cdbee75f17c01a7cc42f958dc650907174af0554`.
Neue Gewichte liegen separat unter `models/qwen3-4b-instruct-2507`.
Die Hardware wurde mit 16 GiB VRAM erkannt; sequenzielles Laden und BF16
vermeiden gleichzeitig geladene generative Modelle. Die gemeinsame
SDPA-Variante und Bildparameter stehen in der eingefrorenen Konfiguration.
Details: [GPU-Ausführung](gpu-inference.md).

## Historische Entscheidungen vor der Vereinheitlichung

Die folgenden Angaben dokumentieren frühere Versuche. Genannte 1.7B-/8B-Modelle,
Regelverfahren und frühere Standardprofile gelten nicht für den Hauptvergleich.

Stand der GPU-Konfiguration: 29.10.2026 (ursprüngliche Entscheidungen: 14.10.2026).
Es wurden aktuelle offizielle Einstiegsseiten
und die versionierten Modellkarten geprüft. Laufende Paketauflösungen stehen im
uv.lock; Modellrevisionen in configs/local.yaml. Keine Modellkarte ersetzt den
lokalen Smoke-Test oder die Evaluation auf echten Teilnehmerlisten.

| Komponente | Entscheidung | Quelle / Lizenz |
| --- | --- | --- |
| Python | uv-verwaltetes 3.12, lokale .venv | [uv Projekte](https://docs.astral.sh/uv/concepts/projects/sync/), MIT/Apache-2.0 |
| Backend | PyTorch 2.8.0, torchvision 0.23.0, expliziter cu126-Index | [Offizielle Versionspaare](https://pytorch.org/get-started/previous-versions/), BSD-3-Clause |
| Paketquellen | Nur torch/torchvision verwenden expliziten PyTorch-Index | [uv/PyTorch](https://docs.astral.sh/uv/guides/integration/pytorch/) |
| OCR | Tesseract 5.4.0 Windows, deu+eng, OSD, tessdata_fast | [Tesseract Installation](https://tesseract-ocr.github.io/tessdoc/Installation.html), Apache-2.0 |
| OCR-Verteilung | UB Mannheim Windows-Build, portabel entpackt | [Windows-Build](https://github.com/UB-Mannheim/tesseract/releases/tag/v5.4.0.20240606) |
| A | Liniengeometrie + OCR-Wortpositionen + konfigurierbare Spalten | Eigenimplementierung, keine externe Strukturierungs-API |
| B | Qwen3-1.7B, Thinking deaktiviert, BF16, vollständig auf CUDA-Gerät 0 | [Modellkarte](https://huggingface.co/Qwen/Qwen3-1.7B), Apache-2.0 |
| C | Qwen3-VL-4B-Instruct, BF16, lokaler Processor + PIL-Bild | [Modellkarte](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct), Apache-2.0 |
| Inferenz | Transformers 4.57.6, Accelerate, SDPA, batch 1 | [Qwen3-VL Dokumentation](https://huggingface.co/docs/transformers/model_doc/qwen3_vl), [Accelerate](https://huggingface.co/docs/accelerate/en/usage_guides/big_modeling), Apache-2.0 |
| PDF | PyMuPDF 1.26.7, Rendering ohne Textebenen-Baseline | [Lizenz](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright), AGPL-3.0 / kommerziell |
| Bildverarbeitung | OpenCV, Pillow | Apache-2.0 / HPND |
| Validierung | Pydantic, strikt, zusätzliche Felder verboten | MIT |

Revisionen:

- B: `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`
- C: `ebb281ec70b05090aa6165b016eac8ec08e71b17`
- Sprachdaten: `87416418657359cb625c412a48b6e1d6d41c29bd`

Der zunächst vorgeschlagene [Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)
hat ebenfalls Apache-2.0-Lizenz, benötigt bei BF16 aber bereits grob 16 GB allein
für 8 Milliarden Parameter. Dies ist eine Gewichtsabschätzung (2 Bytes/Parameter),
keine gemessene Spitzenbelegung. Die tatsächlich erkannte einzelne Laptop-GPU
hat 16376 MiB VRAM, nicht 47 GB. Deshalb ist C mit 4B gewählt. B wurde auf Wunsch
vom 28.10.2026 zunächst auf 4B und am 29.10.2026 auf 1.7B verkleinert und läuft
direkt in BF16. Die zuvor verwendete 8B-Revision
`b968826d9c46dd6066d109eabc6255188de91218` bleibt im separaten
Modellordner und in alten Laufkonfigurationen erhalten. Historisch ließ die
zunächst verwendete 8B-BF16-Aufteilung mit 10 GiB GPU plus
32 GiB CPU ließ im gemessenen Lauf 15 von 36 Schichten auf der CPU und führte zu
langen Laufzeiten. Am 27.10.2026 wurde dieser 8B-Checkpoint mit LLM.int8
vollständig auf GPU 0 geladen; am 28.10.2026 ersetzte ihn Qwen3-4B,
am 29.10.2026 folgte Qwen3-1.7B mit eigener fester Revision und eigenem Modellordner.
Die tatsächliche Verteilung und Quantisierung werden protokolliert. Speicher
mehrerer GPUs wird nicht zusammengerechnet.

Für LLM.int8 ist bitsandbytes 0.48.1 im optionalen Extra `models` festgelegt;
die öffentliche Windows-/CUDA-12.6-Unterstützung wurde geprüft und die echte
Inferenz lokal getestet. Die geringere Genauigkeit kann Ergebnisse verändern;
gleiche Extraktionsqualität wird nicht vorausgesetzt. VLM bleibt bei BF16/SDPA;
ein zusätzliches FlashAttention-Paket ist nicht erforderlich. Die 2 GiB GPU-Reserve ist eine
konservative Startregel, keine Garantie gegen OOM. Es gibt keine automatischen
OOM-Retries oder stillen Auflösungsänderungen. `max_pixels`, Tokenbudget, dtype,
Decodierung und optionale Kachelung sind explizite konfigurierte Varianten.
Details und eine explizite BF16-/CPU-Offload-Referenzkonfiguration:
[GPU-Ausführung](gpu-inference.md).

Die Modellkarte zum ursprünglichen Qwen3-VL-Release enthält noch den historischen
Hinweis auf damals unveröffentlichtes Transformers 4.57.0. Das Projekt nutzt
eine veröffentlichte 4.57.6-Version; die konkrete Qwen3VL-Klasse und CUDA wurden
lokal importiert und geprüft. Paketkombinationen werden über uv.lock festgehalten.

Modell-Downloads benötigen einen expliziten Befehl. Der normale Transport verwendet
`snapshot_download`; `--transport range` verwendet begrenzte, wiederaufnehmbare
HTTP-Bereichsanfragen, wenn große Antworten durch das Netzwerk gepuffert werden.
Die Dateien werden nach dem Download gehasht; LFS-SHA256 wird beim Bereichstransport
zusätzlich gegen die Repositorymetadaten geprüft. Beide Transporte sind ausschließlich
Setup, keine Inferenz. Unvollständige Downloads gelten niemals als verfügbare Modelle.

Bei Anwendung oder Verteilung sind die jeweiligen Lizenzbedingungen der Werkzeuge,
insbesondere von PyMuPDF, zu berücksichtigen. Exakte Paketversionen und lokale
Modell-Dateihashes werden zusätzlich je Run gespeichert.

Weitere geprüfte Implementierungsdokumentation: [PyMuPDF Rendering und Rotation](https://pymupdf.readthedocs.io/en/latest/page.html#Page.get_pixmap),
[pytesseract TSV/OSD](https://github.com/madmaze/pytesseract),
[Pydantic Strict Mode](https://docs.pydantic.dev/latest/concepts/strict_mode/),
[SciPy Assignment](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html).
