# Technischer Buildstand

Geprüft am 14.10.2026 unter Windows 11:

- Portable TinyTeX v2026.10 im Projekt, pdfTeX 1.40.29 / TeX Live 2026,
  latexmk 4.88 und mitgeliefertes Perl.
- Vollständiger Build mit pdfLaTeX und BibTeX erfolgreich, Exitcode 0.
- Ergebnis: `build/thesis.pdf`, **26 Seiten**; Literaturverzeichnis vorhanden.
- Deutsche Silbentrennung installiert und LaTeX-Formate neu erzeugt.
- Keine fehlenden Zitate/Querverweise oder übervollen Boxen im letzten LaTeX-Log.
- Verbleibender Hinweis von `epstopdf`: Shell-Escape ist deaktiviert. Die vorhandenen
  Abbildungen sind PDFs; ihr Einbinden funktioniert ohne EPS-Konvertierung.
- Titelseite mit THD-Logo und Titel lokal als Vorschau geprüft.
- Alle 18 übernommenen `.tex`-, `.bib`- und Logo-Dateien sind bytegenau gleich
  zu den Originalen. SHA256-Liste: `uebernahme.json`.
- Software nach dem Umzug: `uv sync --locked --extra models --offline`,
  `doctor`, ein echter Offline-OCR-Lauf mit Ground Truth sowie **23 Tests**
  erfolgreich; `ruff check` ebenfalls erfolgreich. Keine erneute große
  Modellinferenz für eine reine Verzeichnisumstellung durchgeführt.

Build aus dem Repository-Hauptordner:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File bachelorarbeit/build.ps1
```

Diagnose:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File bachelorarbeit/build.ps1 Doctor
```

Die installierten Paketrevisionen liegen in `.tools/texlive-packages.txt`, die
vollständige lokale Paketdatenbank in `.tools/texlive-installed.tlpdb`.
`build/thesis.log`, `build/thesis.blg` und `build/toolchain.txt` enthalten die
LaTeX-, BibTeX- und Compilerprotokolle. Diese erzeugten Dateien bleiben außerhalb
von Git. Der Quelltext enthält weiterhin die übernommenen TODOs und den früheren
Handschrift-Schwerpunkt; eine redaktionelle Überarbeitung war nicht Teil dieses
technischen Umbaus.
