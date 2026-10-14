# Technische und wissenschaftliche Entscheidungen

Stand der Implementierung: 14.10.2026. Es wurden aktuelle offizielle Einstiegsseiten
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
| B | Qwen3-8B, Thinking deaktiviert, BF16, CPU-Offloading ausdrücklich konfiguriert | [Modellkarte](https://huggingface.co/Qwen/Qwen3-8B), Apache-2.0 |
| C | Qwen3-VL-4B-Instruct, BF16, lokaler Processor + PIL-Bild | [Modellkarte](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct), Apache-2.0 |
| Inferenz | Transformers 4.57.6, Accelerate, SDPA, batch 1 | [Qwen3-VL Dokumentation](https://huggingface.co/docs/transformers/model_doc/qwen3_vl), [Accelerate](https://huggingface.co/docs/accelerate/en/usage_guides/big_modeling), Apache-2.0 |
| PDF | PyMuPDF 1.26.7, Rendering ohne Textebenen-Baseline | [Lizenz](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright), AGPL-3.0 / kommerziell |
| Bildverarbeitung | OpenCV, Pillow | Apache-2.0 / HPND |
| Validierung | Pydantic, strikt, zusätzliche Felder verboten | MIT |

Revisionen:

- B: `b968826d9c46dd6066d109eabc6255188de91218`
- C: `ebb281ec70b05090aa6165b016eac8ec08e71b17`
- Sprachdaten: `87416418657359cb625c412a48b6e1d6d41c29bd`

Der zunächst vorgeschlagene [Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)
hat ebenfalls Apache-2.0-Lizenz, benötigt bei BF16 aber bereits grob 16 GB allein
für 8 Milliarden Parameter. Dies ist eine Gewichtsabschätzung (2 Bytes/Parameter),
keine gemessene Spitzenbelegung. Die tatsächlich erkannte einzelne Laptop-GPU
hat 16376 MiB VRAM, nicht 47 GB. Deshalb ist C mit 4B gewählt. B behält die gewünschte
8B-Größenordnung und verwendet eine explizite Obergrenze von 10 GiB GPU plus
32 GiB CPU. Die tatsächliche Verteilung wird protokolliert. Speicher mehrerer GPUs
wird nicht zusammengerechnet; der Adapter budgetiert ausschließlich GPU 0.

Keine Quantisierung und kein FlashAttention-Paket im Kern: BF16/SDPA vermeiden
zusätzliche native Windows-Abhängigkeiten. Die 2 GiB GPU-Reserve ist eine
konservative Startregel, keine Garantie gegen OOM. Es gibt keine automatischen
OOM-Retries oder stillen Auflösungsänderungen. `max_pixels`, Tokenbudget, dtype,
Decodierung und optionale Kachelung sind explizite konfigurierte Varianten.

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
