# Schriftliche Bachelorarbeit

Die Arbeit wurde aus `Downloads/studienarbeiten/studienarbeiten/thesis` übernommen.
Die ursprüngliche Übernahme ließ `.tex`- und `.bib`-Dateien sowie das THD-Logo
inhaltlich unverändert. Seit 10.11.2026 beschreibt `chapters/03_methodik.tex`
die implementierte zweistufige Verfahrensauswahl und den tatsächlich noch
vorläufigen empirischen Stand. Ergänzt sind Feldnenner, Matching-Sensitivität,
Cluster-Bootstrap, manuelle Schriftgruppen, Hybridbeiträge und Effizienzgrenzen;
die Gegenprobe auf einer Entwicklungsliste bleibt von der geplanten Finalstudie
getrennt. Geprüfte Primärbelege dazu stehen in
`verified_sources.bib`; `references.bib` bleibt das Zotero-Exportziel.
Seit 11.11.2026 dokumentiert Abschnitt 3.6 zusätzlich die einmalige literaturbasierte
Promptgestaltung mit Regelstruktur, Schema-/Laufnachweis und begrenzter technischer
Validierung; es wurde keine Promptoptimierungsstudie durchgeführt.
Abschnitt 3.7 definiert außerdem die ergänzten vollständigen/partiellen
Teilnehmerquotienten, das strikte Referenz-Identitätskriterium, Feldabdeckung,
Fehleranteile und den Umgang mit Seitenzeiten, Aufrufzählern und Kostenszenarien.
Die Dashboarddarstellung und ihre Referenz-/Stichprobengrenzen sind dokumentiert;
zwei weitere geprüfte methodische Quellen ergänzen die Literaturdatei.
Die ursprüngliche Dokumentation liegt in `VORLAGE_README.md`, die ursprünglichen
Dateien im Downloadordner bleiben erhalten. Angepasst wurden die Build-Infrastruktur
und die Dokumentation für die neue Repositorystruktur.

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

Das Dokument enthält noch sichtbare TODOs und außerhalb der aktualisierten
Datengrundlage/Verfahrensauswahl den bisherigen Handschrift-Schwerpunkt.
Die übergeordnete Forschungsfrage wurde nicht verändert. Der aktuelle Code- und
Auswahlstand steht unter [Verfahrensauswahl](../software/docs/method-selection.md).
Ein erfolgreicher Build bedeutet keine inhaltliche
oder formale Abnahme der Arbeit. Der konkrete technische Buildstand steht in
[BUILDSTATUS.md](BUILDSTATUS.md).
