# Bachelorarbeit: Text und Software

Für die Wiederaufnahme durch Agenten: zuerst [AGENTS.md](AGENTS.md) und die
zentrale [Projektübergabe mit Änderungsprotokoll](AGENTEN_UEBERGABE.md) lesen.
Die Übergabe enthält bestätigten Stand, offene Aufgaben und durchgeführte Prüfungen
und wird bei Änderungen fortgeschrieben.

Das Repository ist in zwei eigenständige Bereiche aufgeteilt:

| Ordner | Inhalt | Einstieg |
| --- | --- | --- |
| [`software/`](software/README.md) | Lokales Evaluationsframework für Teilnehmerlisten, Python/uv, Tests, Konfigurationen | `cd software`, anschließend `uv sync --locked --extra models` |
| [`bachelorarbeit/`](bachelorarbeit/README.md) | LaTeX-Text, Kapitel, Literatur, Titelseite und Abbildungen | `powershell -NoProfile -ExecutionPolicy Bypass -File bachelorarbeit/build.ps1` |

## Bachelorarbeit als PDF bauen

Die Hauptdatei ist `bachelorarbeit/thesis.tex`. Einmalig LaTeX lokal einrichten
(Downloads von TinyTeX und benötigten LaTeX-Paketen):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File bachelorarbeit/setup.ps1
```

Danach aus diesem Repositoryordner:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File bachelorarbeit/build.ps1
```

Die PDF entsteht unter **`bachelorarbeit/build/thesis.pdf`**. Eine vorhandene
MiKTeX-/TeX-Live-Installation mit `latexmk`, pdfLaTeX und BibTeX kann ebenfalls
verwendet werden. Die projektlokale Toolchain wird bevorzugt, wenn sie eingerichtet ist.

## Software verwenden

Die Software ist in [Dokumentenvorverarbeitung](software/vorverarbeitung/README.md)
und [eigentliche Verarbeitung](software/verarbeitung/README.md) unterteilt.
Eigene Dokumentordner später unter [`dateien/`](dateien/README.md) ablegen.
Die Vorverarbeitung sammelt PDFs aus allen Unterordnern in einem gemeinsamen
Zielordner und benennt z.B.
`12473.123456_12.23.1456_Muc.pdf` in `123456.pdf` um. Aus dem Hauptordner:

```powershell
software/.venv/Scripts/python.exe software/vorverarbeitung/vorbereiten.py --dry-run
software/.venv/Scripts/python.exe software/vorverarbeitung/vorbereiten.py
```

Für Installation und eigentliche Verarbeitung in den Ordner `software/` wechseln:

```powershell
cd software
Set-Alias uv (Join-Path $PWD '.tools\uv.exe')
$env:UV_CACHE_DIR = Join-Path $PWD '.cache\uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PWD '.tools\python'
uv sync --locked --extra models
uv run --offline --locked --extra models participant-bench doctor
```

Die bereits heruntergeladenen Modellgewichte, Daten und Berichte befinden sich
weiterhin lokal, jetzt unter `software/`. Die Python-Umgebung wurde am neuen Pfad
neu erstellt. Details stehen in der [Software-Dokumentation](software/README.md).

## Schreiben in VS Code

Das Repository als Ordner öffnen und die empfohlene Erweiterung **LaTeX Workshop**
installieren. `bachelorarbeit/thesis.tex` öffnen und **Build LaTeX project** wählen.
Die Workspace-Konfiguration verwendet denselben Build wie das PowerShell-Skript.
Unter **Terminal → Run Task** stehen zusätzlich Build und LaTeX-Diagnose bereit.

Die Methodik beschreibt inzwischen die implementierte
[Verfahrensauswahl](software/docs/method-selection.md) für überwiegend
maschinenschriftliche und gemischte Listen. Andere Entwurfsteile und die
übergeordnete Forschungsfrage enthalten noch den früheren Handschrift-Schwerpunkt;
ihre Abstimmung bleibt ein separater inhaltlicher Arbeitsschritt. Persönliche Angaben stehen in
`bachelorarbeit/config/metadata.tex`, Literatur in den beiden `.bib`-Dateien.

Toolchains, Python-Umgebungen, Modelldateien, vertrauliche Daten, Ergebnisse und
LaTeX-Buildprodukte sind gitignoriert. Quelltext, Literaturdateien und benötigte
Abbildungen bleiben versionierbar.
