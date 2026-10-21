# Eingabe für die Dokumentenvorverarbeitung

Hier später die eigenen Ordner mit Dokumenten ablegen, auch mit weiteren
Unterordnern. Nur Dateien mit Endung `.pdf` (auch `.PDF`) werden kopiert.

Beispiel: `standort-a/2026/12473.123456_12.23.1456_Muc.pdf` wird zu
`software/vorverarbeitung/ausgabe/pdfs/123456.pdf`.
Alle gültigen PDFs landen ohne Eingabeunterordner in diesem gemeinsamen Ordner.
Auch `12473.123456 12.23.1456_Muc.pdf` wird zu `123456.pdf`.
Die Nummer ist eine Zeichenfolge; führende Nullen bleiben erhalten.
Punkt oder Unterstrich vor der ID, Leerraum danach und ein zweistelliges
Präfix wie `01.` werden unterstützt: Auch `12473_123456_…`,
`01.12473.123456_…` und `12473. 123456_…` ergeben `123456.pdf`.
Bei `101158 - 174563 - 09.09.2026 MUC.pdf` wird die zweite Zahl als ID
verwendet, also `174563.pdf`. Auch Bindestriche ohne Leerzeichen sind erlaubt.
Die ID muss genau sechs Ziffern enthalten. PDFs, die das nicht erfüllen
oder keine gültige ID haben, werden mit Originalnamen direkt unter
`software/vorverarbeitung/ausgabe/nicht_erfuellt/` gesammelt.

Aus dem Repository-Hauptordner starten:

```powershell
software/.venv/Scripts/python.exe software/vorverarbeitung/vorbereiten.py --dry-run
software/.venv/Scripts/python.exe software/vorverarbeitung/vorbereiten.py
```

Alternativ mit einem vorhandenen Python ab Version 3.12:
`python software/vorverarbeitung/vorbereiten.py`.
Für die Bereinigung wird das im Projekt enthaltene PyMuPDF benötigt.
PDF-Anmerkungen werden entfernt. Unter `software/vorverarbeitung/ausgabe/vergleich/`
entsteht für jede Datei ein Ordner mit dem unveränderten Original unter seinem
ursprünglichen Namen und der bearbeiteten Version `<ID>_bearbeitet.pdf`.

Die Dokumente unter diesem Ordner werden von Git ignoriert. Diese README
bleibt versioniert. Details: [Vorverarbeitung](../software/vorverarbeitung/README.md).
