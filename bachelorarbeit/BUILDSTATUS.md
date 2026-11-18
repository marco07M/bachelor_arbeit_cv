# Technischer Buildstand

## Wissenschaftliche Validität vom 17.11.2026

- Kapitel 2–6, Abkürzungsverzeichnis und verifizierte Literatur gezielt ergänzt:
  optionale ANLS-Feldadaption, Zeilenkonsistenz, unabhängige Originalprüfung,
  GT-Seitenstrata, mehrere Ursachenachsen und Messgrenzen.
- Fünf neue Primärquellen; **41 zitierte Einträge**, keine doppelten Schlüssel.
  Bestehender IEEE-Stil und Zotero-Export unverändert.
- Lokaler Build mit vorhandener TinyTeX-Toolchain erfolgreich, **81 Seiten**.
  0 unaufgelöste Zitate/Verweise, 0 Overfull-/Underfull-Boxen, 0 BibTeX-Warnungen;
  bekannter epstopdf-Hinweis zu deaktiviertem Shell-Escape. Relevante neue Seiten
  gerendert und visuell geprüft. Keine neuen Pakete oder Downloads.
- TinyTeX benötigt erweiterten Dateisystemzugriff für die Windows-Auflösung des
  übergeordneten Documents-Pfads; derselbe Build scheitert in der Dateisystem-Sandbox
  bereits vor dem eigentlichen LaTeX-Aufruf. Keine Toolchainänderung.
- 1.053 lokale Tests und 48 API-Tests erfolgreich; 27 neue Regressionen.
  Entwicklungsausgaben bleiben explorativ; manuelle Zweitannotation und
  kontrollierte Studien weiterhin offen. Historische Buildstände unten erhalten.

## Vollständige wissenschaftliche und technische Überarbeitung vom 16.11.2026

- Vollständige Ausarbeitung und Synchronisierung aller Kapitel (`01_einleitung.tex`
  bis `07_fazit.tex`), des Frontmatters (`erklaerung.tex`, `kurzfassung.tex`,
  `abstract.tex`, `abkuerzungsverzeichnis.tex`), des Anhangs (`appendices/anhang.tex`)
  sowie der Hauptdatei `thesis.tex` und `config/preamble.tex` auf Basis des
  aktuellen Repository-Stands vom 16.11.2026 mit Fokus auf die fünf
  Vergleichsverfahren `ocr_rules`, `ocr_llm`, `paddle_llm`, `vlm` und `ocr_vlm`
  (`configs/benchmark-five.yaml`). Abkürzungen sind auch in Kurzfassung und
  Abstract über das `acronym`-Paket (ohne doppelte Klammern) mit dem
  Abkürzungsverzeichnis verlinkt und werden zu Beginn des Hauptteils
  (`\acresetall` bei `\mainmatter`) für die Erstnennung im Haupttext zurückgesetzt.
- Neun weitere verifizierte wissenschaftliche Originalarbeiten in
  `verified_sources.bib` ergänzt (insgesamt **35 zitierte Quellen** im
  numerischen IEEE-Stil `IEEEtran`, 0 BibTeX-Warnungen, 0 Dubletten);
  `references.bib` bleibt als Zotero-Exportziel unverändert.
- Lokaler LaTeX-/BibTeX-Build über `bachelorarbeit/build.ps1` im Standard-Sandbox-Modus
  erfolgreich: Exitcode 0, **77 Seiten** (`bachelorarbeit/build/thesis.pdf` sowie
  Kopie unter `bachelorarbeit/thesis.pdf`).
- **0 unaufgelöste Zitate oder Querverweise**, **0 LaTeX-Warnungen** (lediglich
  der bekannte Paket-Hinweis von `epstopdf` zu deaktiviertem Shell-Escape) und
  **0 über- oder untervolle Boxen (`Overfull`/`Underfull \hbox`)**.
- Alle in `05_ergebnisse.tex` berichteten Zahlen entstammen ausschließlich
  reproduzierbar im Repository dokumentierten Entwicklungs- und Fehleranalyseläufen;
  noch ausstehende Pilot-/Finaltestläufe und Prozesskostenmessungen sind transparent
  als `\TODO{...}`-Platzhalter ausgewiesen. Keine personenbezogenen oder
  vertraulichen Unternehmensdaten im LaTeX-Quelltext.

## Dashboard und Evaluationsmetriken vom 11.11.2026

- Abschnitte 3.7/3.8 um vollständige/partielle Teilnehmerquotienten, striktes
  Referenz-Identitätskriterium, Coverage und Fehleranteile, Aufruf-/Zeitnachweis,
  getrennte Kostenszenarien und Dashboard-Reproduzierbarkeit ergänzt.
  Zwei verifizierte methodische Quellen in `verified_sources.bib` hinzugefügt;
  der Zotero-Export bleibt unverändert.
- Lokaler LaTeX-/BibTeX-Build erfolgreich, Exitcode 0, **36 Seiten**. Ergänzte
  Methodikseiten gerendert und visuell geprüft. Keine fehlenden Zitate oder
  Querverweise und keine über-/untervollen Boxen. Der bekannte epstopdf-Hinweis
  zu deaktiviertem Shell-Escape bleibt; keine EPS-Konvertierung erforderlich.
- Bestehender TinyTeX-Build mit genehmigtem Zugriff zur Windows-Pfadauflösung,
  ohne Downloads, neue Pakete oder Änderungen an der Toolchain.
- Technischer Nachweis: 741 lokale und 48 API-Tests bestanden; 94 gezielte
  Nachtests nach Abschluss der Darstellung. Dies belegt keine unabhängige
  Modellstudie. Die visuelle HTML-Browserabnahme bleibt wegen der nicht
  unterstützten Windows-Browsersteuerung offen; die tatsächliche
  JavaScript-Bedienlogik wurde separat automatisiert geprüft.

## Ergänzung vom 11.11.2026

- Abschnitt 3.6 beschreibt die einmalige literaturbasierte Promptgestaltung,
  sechs Instruktionsabschnitte, Quellenbindung, Schema-/Versionsnachweis und
  Konstanthaltung im späteren Vergleich. Fünf geprüfte Original-/Übersichtsarbeiten
  in `verified_sources.bib` ergänzt; Zotero-Export unverändert.
- Implementierung, zwölf neue Vertragsprüfungen und eine begrenzte reale Prüfung
  der finalen Familie auf einer vorhandenen synthetischen Seite sind von einer
  empirischen Promptoptimierung und unabhängiger Qualitätsstudie getrennt.
- Vorhandener lokaler LaTeX-/BibTeX-Build: Exitcode 0, **34 Seiten**. Keine
  LaTeX-Warnungen, fehlenden Zitate oder übervollen Boxen; neue Methodikseiten
  als PNG geprüft. TinyTeX erforderte die bereits genehmigte lokale Ausführung
  außerhalb der Sandbox; keine Downloads oder Toolchainänderungen.

## Ergänzung vom 10.11.2026

- Wissenschaftliche Evaluation in Kapitel 3 weiter ausgearbeitet: Feldzähler und
  Nenner, Originalrollen/Matching, manuelle Schriftgruppen, Cluster-Bootstrap,
  gepaarte Effekte, Fehlerstufen, Hybridkontrollen und Effizienzgrenzen. Getrennt
  dokumentiert: Implementierung, Gegenprobe auf einer Entwicklungsgruppe und
  noch offene unabhängige Studie. Nutzer-Fünferprofil gegenüber Auswahlvorschlag
  klargestellt; Kosten-/Prozessdaten ausdrücklich als geplante Erhebung markiert.
- Abschließender lokaler Build nach dieser Erweiterung: Exitcode 0,
  **32 Seiten**, keine LaTeX-Warnungen, fehlenden Zitate/Querverweise oder übervollen
  Boxen. Ergänzte Methodikseiten gerendert und visuell geprüft. Offizielle
  SciPy-Bootstrap-Dokumentation als weiterer Primärbeleg ergänzt. Der bekannte
  epstopdf-Shell-Escape-Pakethinweis bleibt; keine EPS-Konvertierung erforderlich.

Vorheriger Stand desselben Tages:

- Datengrundlage und Abschnitt zur Verfahrensauswahl in Kapitel 3 aktualisiert;
  fünf geprüfte Primärbelege in `verified_sources.bib` ergänzt.
- Vorhandener Build mit pdfLaTeX/BibTeX erfolgreich, Exitcode 0,
  `build/thesis.pdf` mit **29 Seiten**. Keine fehlenden Zitate/Querverweise oder
  übervollen Boxen im abschließenden Log. Der epstopdf-Hinweis zu deaktiviertem
  Shell-Escape besteht weiterhin.
- Geänderte Methodikseiten als PNG gerendert und visuell auf Lesbarkeit,
  Umbrüche und Überlappungen geprüft.
- TinyTeX benötigte in dieser Agentenumgebung den genehmigten lokalen Build
  außerhalb der Sandbox, um den übergeordneten Windows-Dokumentpfad aufzulösen.
  Keine Downloads und keine Änderung der Buildskripte/Toolchain.
- Die übergeordnete Forschungsfrage, übrige Entwurfskapitel und TODOs wurden
  nicht redaktionell geändert. Eine unabhängige Pilotstudie ist weiterhin offen.

## Historische Einrichtung

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
