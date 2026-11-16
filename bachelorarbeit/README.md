# Schriftliche Bachelorarbeit

Die Arbeit wurde ursprünglich aus `Downloads/studienarbeiten/studienarbeiten/thesis` übernommen.
Seit dem **16.11.2026** sind sämtliche Kapitel (`chapters/01_einleitung.tex` bis
`chapters/07_fazit.tex`), die Kurzfassung (`frontmatter/kurzfassung.tex`), das
englische Abstract (`frontmatter/abstract.tex`), das Abkürzungsverzeichnis
(`frontmatter/abkuerzungsverzeichnis.tex`) sowie der Anhang
(`appendices/anhang.tex`) vollständig auf den aktuellen technischen Stand des
Evaluationsframeworks in `software/` (einschließlich zweistufiger automatischer
Seitenorientierung, verlustfreiem OCR-Beobachtungsregister, dokumentweiter
Spaltenvererbung v3 mit nativer Anker-Absicherung, zeilenindividueller
Namensaufteilung, verlustfreier Input-Kompaktierung, fünfstufigem Feldstatus,
bedingter Levenshtein-Ähnlichkeit erkannter Felder v7, kausaler Fehleranalyse
und Dashboard A–G) synchronisiert. Geprüfte wissenschaftliche Originalquellen im
IEEE-Zitierstil stehen in `verified_sources.bib` (35 zitierte Einträge);
`references.bib` bleibt das Zotero-Exportziel.
Die ursprüngliche Vorlagendokumentation liegt in `VORLAGE_README.md`.

## PDF erstellen

Aus dem Repository-Hauptordner:

```powershell
# Einmalig: lokale Distribution und benoetigte Pakete herunterladen
powershell -NoProfile -ExecutionPolicy Bypass -File bachelorarbeit/setup.ps1

# Danach: vorhandene lokale Werkzeuge verwenden, keine Paketdownloads im Build
powershell -NoProfile -ExecutionPolicy Bypass -File bachelorarbeit/build.ps1
```

Ergebnis: **`bachelorarbeit/build/thesis.pdf`**.

Das Buildskript funktioniert auch aus anderen Arbeitsverzeichnissen; die Eingabe-
und Ausgabepfade werden relativ zum Skript ermittelt. Es verwendet `latexmk`,
pdfLaTeX und klassisches BibTeX mit dem bereits vorhandenen IEEEtran-Stil. LaTeX
und BibTeX laufen automatisch so oft wie nötig. Quellen und Literatur werden
lokal verarbeitet. Shell-Escape ist deaktiviert.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File bachelorarbeit/build.ps1 Doctor
powershell -NoProfile -ExecutionPolicy Bypass -File bachelorarbeit/build.ps1 Clean
```

`Doctor` prüft Compiler, BibTeX, latexmk/Perl und die benötigten Paketdateien.
`Clean` entfernt generierte Hilfsdateien; `DistClean` entfernt zusätzlich die
erzeugte PDF. Quelldateien und das Logo bleiben erhalten.

## Toolchain

`setup.ps1` richtet TinyTeX v2026.10 nur unter `bachelorarbeit/.tools/` ein.
Die Archivversion, SHA256 und benötigten Pakete stehen in `toolchain.json`.
TinyTeX liefert auch das für latexmk erforderliche Perl mit. Es sind weder eine
globale Installation noch eine Änderung des System-PATH nötig.

Zusätzliche Pakete und das notwendige Paketmanager-Update werden im expliziten
Setup-Schritt aus der angegebenen TeX-Live-Paketquelle geladen. Diese Zusatzpakete
sind damit nicht vollständig durch die ursprüngliche Archiv-Prüfsumme eingefroren;
ihre tatsächlich installierten Revisionen werden in `.tools/texlive-packages.txt`
protokolliert. Der Build protokolliert Compiler/BibTeX in `build/toolchain.txt`.
Der eigentliche PDF-Build installiert keine Pakete nach.

Alternativ ist eine vorhandene vollständige TeX-Live- oder MiKTeX-Installation
nutzbar. Ohne lokale TinyTeX-Installation verwendet das Buildskript `latexmk`
aus dem PATH; bei MiKTeX muss Perl für latexmk verfügbar sein. Unter Linux/macOS
mit entsprechend installierter TeX-Distribution direkt im Ordner `bachelorarbeit`:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error thesis.tex
```

Offizielle Quellen: [TinyTeX](https://yihui.org/tinytex/),
[Distributionsarchiv](https://github.com/rstudio/tinytex-releases),
[latexmk](https://www.cantab.net/users/johncollins/latexmk/),
[LaTeX Workshop](https://github.com/James-Yu/LaTeX-Workshop/wiki/Compile).

## Dateien bearbeiten

- `thesis.tex`: Hauptdatei und Reihenfolge der Bestandteile.
- `config/metadata.tex`: Titel, Personendaten, Betreuung und Abgabedatum.
- `config/preamble.tex`: Pakete, Sprache und Layout.
- `chapters/`: Kapitel der Arbeit.
- `frontmatter/`: Titelblatt, Kurzfassung, Abstract und Abkürzungen.
- `appendices/`: Anhang.
- `figures/`: eigene Abbildungen; `assets/`: mitgeliefertes Logo.
- `references.bib`: Zotero-/Better-BibTeX-Export.
- `verified_sources.bib`: mitgelieferte zusätzliche Literaturdatei.

Für Zotero den Exportpfad auf **`bachelorarbeit/references.bib`** ändern;
siehe [Zotero-Anleitung](ZOTERO.md). Die BibTeX-Dateien bleiben versionierbar,
sodass LaTeX ohne laufendes Zotero kompiliert werden kann.

In `chapters/05_ergebnisse.tex` sind ausschließlich real gemessene und durch
Prüfartefakte belegte Ergebnisse der Entwicklungsläufe dokumentiert; die noch
ausstehenden konfirmatorischen Pilot-/Testläufe sowie die empirische
Prozesskostenerhebung sind durch explizite `\TODO{...}`-Platzhalter markiert.
Ein erfolgreicher Build bedeutet keine inhaltliche
oder formale Abnahme der Arbeit. Der konkrete technische Buildstand steht in
[BUILDSTATUS.md](BUILDSTATUS.md).
