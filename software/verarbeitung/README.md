# 2. Eigentliche Dokumentenverarbeitung

Der vorhandene Benchmark liegt jetzt unter `src/participant_bench/` in diesem
Ordner. Er rendert PDF-Seiten, bereitet die Seiten auf und führt OCR/Regeln,
OCR mit lokalem Sprachmodell oder ein lokales Vision-Language-Modell aus.
Die Dokumentnummer im Dateinamen ist unabhängig von den Personalnummern,
die anschließend aus den Teilnehmerlisten extrahiert werden.

Alle folgenden Befehle werden weiterhin aus `software/` ausgeführt. Nach einer
Aktualisierung des Repositorys die lokale Paketinstallation einmal anpassen:

```powershell
uv sync --locked --extra models
```

Die Ausgabe der [Vorverarbeitung](../vorverarbeitung/README.md) direkt verwenden:

```powershell
uv run --offline --locked --extra models participant-bench prepare --input vorverarbeitung/ausgabe/pdfs --config configs/imported.yaml --output prepared/meine-listen
uv run --offline --locked --extra models participant-bench run --input vorverarbeitung/ausgabe/pdfs --config configs/imported.yaml --offline
```

`configs/imported.yaml` aktiviert alle drei Verfahren. Die Vorverarbeitung legt
alle gültigen PDFs direkt im Eingabeordner ab; auch rekursive Suche wird von der
Konfiguration unterstützt. Modelle und OCR müssen vorher eingerichtet
sein. Für neue Seitenvorbereitungen jeweils einen neuen `--output`-Ordner wählen.
`prepare` erzeugt Seitenbilder zur Kontrolle; `run` ohne Manifest bereitet die
Seiten selbst auf. Für die Arbeit mit einem kontrollierten Manifest sowie
Ground Truth siehe die [Software-Anleitung](../README.md).

Konfigurationen, Tests, virtuelle Umgebung und Modellgewichte werden von den
beiden Softwarebereichen im übergeordneten `software/`-Projekt verwaltet.
