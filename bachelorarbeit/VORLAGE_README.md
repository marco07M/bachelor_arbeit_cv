# Bachelorarbeit mit LaTeX

Dieses Repository enthält ein vorbereitetes LaTeX-Gerüst für eine Bachelorarbeit
an der Technischen Hochschule Deggendorf. Die zentrale Hauptdatei ist
`thesis/thesis.tex`; persönliche Angaben werden ausschließlich in
`thesis/config/metadata.tex` gepflegt.

## Schnellstart

1. Eine aktuelle TeX-Distribution installieren, unter Windows beispielsweise
   MiKTeX, unter Linux TeX Live.
2. In den Ordner `thesis` wechseln.
3. `config/metadata.tex` vollständig anpassen.
4. Zotero mit Better BibTeX nach der Anleitung in `ZOTERO.md` verbinden.
5. Die Kapitel unter `chapters/` bearbeiten.
6. Das Dokument bauen:

   ```powershell
   .\build.ps1
   ```

   Wenn das Terminal stattdessen im Workspace-Ordner `bachelorarbeit_latex`
   geöffnet ist, funktioniert derselbe Build mit:

   ```powershell
   .\studienarbeiten\thesis\build.ps1
   ```

   Alternativ plattformunabhängig:

   ```text
   latexmk -pdf -interaction=nonstopmode -halt-on-error thesis.tex
   ```

Das fertige Dokument liegt danach unter `thesis/build/thesis.pdf`. `latexmk`
führt LaTeX und BibTeX automatisch so oft aus, wie es für Verweise,
Inhaltsverzeichnis und Literaturverzeichnis erforderlich ist.
Eine bereits vorhandene ältere PDF unter `../output/pdf/thesis.pdf` wird beim
Build ebenfalls aktualisiert.

## Projektstruktur

```text
thesis/
├── thesis.tex                 Hauptdatei und Reihenfolge der Bestandteile
├── config/                    Metadaten, Pakete und Layout
├── assets/                    Vorlagen-Assets wie das THD-Logo
├── frontmatter/               Titelseite, Kurzfassung und Verzeichnisse
├── chapters/                  Inhaltliche Kapitel
├── appendices/                Anhänge
├── figures/                   Eigene Abbildungen
└── references.bib             Literaturdatenbank
```

Die Datei `ZOTERO.md` im Repository enthält die vollständige Einrichtung für
Zotero, Better BibTeX und den automatischen Export nach `references.bib`.

## Schreiben und Zitieren

- Quellen in Zotero pflegen. Better BibTeX aktualisiert `references.bib`
  automatisch; die Datei nicht manuell bearbeiten.
- Bereits geprüfte Primärquellen des Entwurfs stehen in `verified_sources.bib`.
  Bei einer Übernahme nach Zotero doppelte Einträge in beiden Dateien vermeiden.
- Quellen im Text mit `\cite{schluessel}` zitieren. LaTeX Workshop bietet
  dafür die Citekeys aus `references.bib` als Autovervollständigung an.
- Abbildungen in `figures/` ablegen. Vorlagen für Abbildungen und Tabellen stehen
  auskommentiert in den Kapiteldateien.
- Neue Kapitel als eigene `.tex`-Datei unter `chapters/` anlegen und in `thesis.tex`
  mit `\input{...}` einbinden.
- Das Projekt verwendet den numerischen IEEE-Stil über
  `\bibliographystyle{IEEEtran}`. Änderungen am Zitierstil mit der Betreuung
  abstimmen.
- Formale Anforderungen der Fakultät und der aktuellen Prüfungsordnung vor der
  Abgabe nochmals prüfen; diese Projektvorlage ersetzt diese Prüfung nicht.

## Checkliste vor der Abgabe

- Alle Platzhalter in `config/metadata.tex` ersetzt.
- Kurzfassung, Abstract und Schlagwörter ergänzt.
- Im gesamten Projekt nach `TODO` gesucht und alle Fundstellen bearbeitet.
- In `config/metadata.tex` `\showtodosfalse` aktiviert.
- Abkürzungsverzeichnis bereinigt und alphabetisch sortiert.
- Jede Abbildung und Tabelle im Text erläutert und referenziert.
- Automatischen Zotero-Export geprüft und Citekeys in Zotero fixiert.
- Quellen vollständig und einheitlich erfasst.
- Literatur-, Abbildungs- und Tabellenverzeichnis kontrolliert.
- Seitenlayout (`twoside` oder `oneside`) mit der Betreuung abgestimmt.
- Finale PDF-Datei vollständig visuell geprüft.

## Aufräumen

Temporäre Dateien lassen sich mit `./build.ps1 Clean` beziehungsweise
`latexmk -c thesis.tex` entfernen. `DistClean` entfernt zusätzlich die erzeugte
PDF-Datei.

Die ursprüngliche Vorlage wurde von Andreas Fischer veröffentlicht und steht
unter der Creative-Commons-Lizenz BY-SA 4.0; siehe `LICENSE`.
