# Zotero mit der Bachelorarbeit verbinden

Das Projekt verwendet klassisches BibTeX. Zotero verwaltet die Quellen; die
Erweiterung Better BibTeX exportiert sie automatisch nach
`bachelorarbeit/references.bib`. Diese Datei wird von LaTeX eingelesen und soll nach
der Einrichtung nicht mehr manuell bearbeitet werden. Zitate und
Literaturverzeichnis werden mit dem numerischen IEEE-Stil `IEEEtran`
formatiert.

## 1. Zotero und Better BibTeX installieren

1. Zotero von <https://www.zotero.org/download/> installieren.
2. Den Zotero Connector für den verwendeten Browser installieren.
3. Die aktuelle Better-BibTeX-Datei (`.xpi`) von
   <https://retorque.re/zotero-better-bibtex/installation/> herunterladen.
4. In Zotero **Werkzeuge → Plugins** öffnen, über das Zahnrad
   **Plugin aus Datei installieren** auswählen und die `.xpi`-Datei öffnen.
5. Zotero neu starten.

## 2. Sammlung und automatische BibTeX-Datei einrichten

1. In Zotero eine Sammlung namens **Bachelorarbeit** anlegen.
2. Die Sammlung mit der rechten Maustaste anklicken und
   **Sammlung exportieren** wählen.
3. Als Format **Better BibTeX** auswählen. Nicht **Better BibLaTeX** verwenden,
   da dieses Projekt aktuell den klassischen BibTeX-Workflow nutzt.
4. **Keep updated / Aktuell halten** aktivieren.
5. Als Zieldatei die vorhandene Datei
   `bachelorarbeit/references.bib` auswählen und das Überschreiben
   bestätigen.

Ab diesem Zeitpunkt aktualisiert Better BibTeX die Datei automatisch, sobald
sich Quellen in der Sammlung ändern. Die Datei bleibt bewusst in Git, damit ein
Build auch ohne eine lokale Zotero-Installation reproduzierbar ist.

Im Literaturverzeichnis erscheinen nur tatsächlich zitierte Quellen.
Bereits geprüfte Primärquellen des Entwurfs stehen zusätzlich in
`bachelorarbeit/verified_sources.bib`; diese Datei wird nicht von Zotero überschrieben.
Beim späteren Import in Zotero doppelte Einträge in beiden Dateien vermeiden.

## 3. Stabile Zitierschlüssel verwenden

Unter **Einstellungen → Better BibTeX → Citation keys**:

- Citekeys möglichst als ASCII erzeugen, also ohne Leerzeichen und Umlaute.
- Automatisches Fixieren (Pinning) der Citekeys aktivieren, damit sich bereits
  im Text verwendete Schlüssel später nicht unbemerkt ändern.
- Für Quick Copy als Format **LaTeX citation** und als Befehl `cite` wählen.

Ein realer BibTeX-Eintrag sieht beispielsweise so aus:

```bibtex
@inproceedings{Li2023TrOCR,
  author    = {Li, Minghao and Lv, Tengchao and Chen, Jingye and Cui, Lei and Lu, Yijuan and Florencio, Dinei and Zhang, Cha and Li, Zhoujun and Wei, Furu},
  title     = {{TrOCR}: Transformer-Based Optical Character Recognition with Pre-Trained Models},
  booktitle = {Proceedings of the AAAI Conference on Artificial Intelligence},
  year      = {2023},
  doi       = {10.1609/aaai.v37i11.26538}
}
```

Im Kapitel wird er so verwendet:

```latex
Die Methode TrOCR wird von Li et al. beschrieben \cite{Li2023TrOCR}.
```

Mehrere Quellen können gemeinsam zitiert werden:

```latex
Die Ansätze sind in den Originalarbeiten beschrieben
\cite{Li2023TrOCR,Kim2022Donut}.
```

In VS Code schlägt LaTeX Workshop die Schlüssel aus den `.bib`-Dateien
automatisch vor, sobald hinter `\cite{` mit der Eingabe begonnen wird.

## 4. Kompilieren

Im Ordner `bachelorarbeit`:

```powershell
.\build.ps1
```

Alternativ in VS Code die Datei `thesis.tex` öffnen und
**LaTeX Workshop: Build LaTeX project** ausführen. Das Projekt verwendet
`latexmk`; LaTeX und BibTeX werden automatisch in der benötigten Reihenfolge
ausgeführt.

## Fehlerbehebung

- **Zitat erscheint als [?]:** Prüfen, ob der Citekey exakt in
  `references.bib` vorkommt, anschließend erneut kompilieren.
- **Neue Quelle fehlt:** In Zotero unter
  **Einstellungen → Better BibTeX → Automatic export** prüfen, ob der Export
  aktiv ist und auf die richtige Datei zeigt.
- **Zotero überschreibt manuelle Änderungen:** Das ist beabsichtigt.
  Bibliografische Angaben immer in Zotero korrigieren.
- **Literaturverzeichnis ist leer:** Mindestens eine Quelle muss im Text mit
  `\cite{...}` verwendet werden.
- **Citekey hat sich geändert:** Den Schlüssel in Zotero fixieren und den
  Citekey im LaTeX-Text entsprechend korrigieren.
