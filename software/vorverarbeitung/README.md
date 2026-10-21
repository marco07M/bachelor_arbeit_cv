# 1. Dokumentenvorverarbeitung

`vorbereiten.py` durchsucht standardmäßig `../../dateien/` einschließlich aller
Unterordner. Die Standardpfade sind relativ zur Skriptdatei und funktionieren
auch beim Aufruf aus einem anderen Arbeitsverzeichnis. Die Vorverarbeitung
benötigt Python ab Version 3.12 und das bereits im Projekt enthaltene PyMuPDF.
Die CLI entfernt standardmäßig PDF-Anmerkungen und archiviert die Originale.

Aus dem Ordner `software/`:

```powershell
.venv/Scripts/python.exe vorverarbeitung/vorbereiten.py --dry-run
.venv/Scripts/python.exe vorverarbeitung/vorbereiten.py
```

Nach `uv sync --locked --extra models` steht auch der Befehl zur Verfügung:

```powershell
uv run --offline --locked --extra models pdf-vorverarbeiten
```

Eigene Pfade werden relativ zum aktuellen Arbeitsverzeichnis interpretiert:

```powershell
.venv/Scripts/python.exe vorverarbeitung/vorbereiten.py --input ../dateien --output vorverarbeitung/ausgabe
```

## Zuordnung

```text
dateien/                                      vorverarbeitung/ausgabe/
  München/2026/                                 pdfs/
    12473.123456_12.23.1456_Muc.pdf      ->         123456.pdf
    12473.000007_12.23.1456_Muc.PDF      ->         000007.pdf
    12473.654321 12.23.1456_Muc.pdf      ->         654321.pdf
    12473.12345_12.23.1456_Muc.pdf       ->       nicht_erfuellt/
                                                  12473.12345_12.23.1456_Muc.pdf
    notizen.docx                       ->       (übersprungen)
                                                protokolle/<Lauf-ID>.json
                                                protokolle/<Lauf-ID>.csv
                                                vergleich/123456_<Kennung>/
                                                  12473.123456_12.23.1456_Muc.pdf
                                                  123456_bearbeitet.pdf
```

Der Zielname besteht aus der **genau sechsstelligen ID** hinter der Stammnummer,
gefolgt von `.pdf`. Zwischen Stammnummer und ID darf ein Punkt, Unterstrich oder
Bindestrich stehen, auch mit umgebendem Leerraum. Ein vorangestelltes zweistelliges
Präfix wie `01.` wird berücksichtigt. Die ID endet vor einem Unterstrich,
Leerzeichen, Bindestrich, dem nächsten Punkt oder dem Ende des Dateinamens ohne Erweiterung.
Führende Nullen zählen mit. Beispiele, die alle `123456.pdf` ergeben:

```text
12473_123456_12.23.1456_Muc.pdf
01.12473.123456_12.23.1456_Muc.pdf
12473.123456_12.23.1456_Muc.pdf
12473. 123456_12.23.1456_Muc.pdf
12473.123456 12.23.1456_Muc.pdf
```

Bei `101158 - 174563 - 09.09.2026 MUC.pdf` ist die **zweite** Zahl die ID:
Das Ziel heißt `174563.pdf`. Die erste Zahl gehört zur Stammnummer, auch wenn
sie ebenfalls sechsstellig ist. Bindestriche funktionieren auch ohne Leerzeichen.

PDFs mit einer kürzeren, längeren, fehlenden oder ungültigen ID werden mit ihrem
**ursprünglichen Dateinamen** unter `ausgabe/nicht_erfuellt/` abgelegt.
Sie landen direkt in diesem Ordner. Das Protokoll nennt den Ablehnungsgrund.
Nur die PDFs unter `ausgabe/pdfs/` werden anschließend verarbeitet.

Die Eingabeunterordner werden weiterhin vollständig durchsucht. Im Ziel landen
alle gültigen PDFs direkt unter `pdfs/`, alle aussortierten direkt unter
`nicht_erfuellt/`. Das Protokoll bewahrt die ursprünglichen relativen Quellpfade.
Originale bleiben unverändert. Andere Dateitypen werden übersprungen. Die CLI
prüft beim Entfernen der Anmerkungen auch, ob die Datei als PDF lesbar ist.
Verknüpfungen/Junctions werden nicht verfolgt.

## PDF-Anmerkungen und Originalsicherung

Bei jedem normalen CLI-Lauf werden PDF-Anmerkungen wie Textmarker, Kommentare,
Unterstreichungen, Stempel und gezeichnete Anmerkungen aus den Arbeitskopien
entfernt. Gültige IDs landen unter `ausgabe/pdfs/`, nicht erfüllte IDs unter
`ausgabe/nicht_erfuellt/`. Das funktioniert auch mit bereits benannten PDFs wie
`174563.pdf`, beispielsweise aus `data/pdfs_eingabe/`:

```powershell
.venv/Scripts/python.exe vorverarbeitung/vorbereiten.py --input data/pdfs_eingabe
```

Jede Quelldatei erhält einen eigenen Ordner unter `ausgabe/vergleich/`,
beispielsweise:

```text
vergleich/
  123456_a1b2c3d4e5f6/
    12473.123456_12.23.1456_Muc.pdf   # Original mit echtem Namen, bytegenau unverändert
    123456_bearbeitet.pdf             # umbenannte und bereinigte Version
```

Die Kennung im Ordnernamen hängt von Quellpfad und Originalinhalt ab. So bekommt
auch jede Datei mit derselben Kurs-ID oder demselben Dateinamen einen eigenen
Vergleichsordner. Vor der Bereinigung wird zuerst das Original gesichert.
Bei ungültigen IDs beginnt der Ordnername mit `ohne_id_` und die bearbeitete
Version heißt `dokument_bearbeitet.pdf` (bei Namensgleichheit mit einem Zusatz).
Bei defekten oder verschlüsselten PDFs liegt dort die gesicherte Originaldatei;
der fehlgeschlagene Bereinigungsschritt wird protokolliert.

Die gesammelten Modelleingaben liegen zusätzlich flach unter `ausgabe/pdfs/`
bzw. `ausgabe/nicht_erfuellt/`. Ein Namenskonflikt in dieser gemeinsamen Ablage
verhindert die Erstellung des jeweiligen Vergleichspaars nicht. Modelle nur
auf `pdfs/` anwenden, damit die Originale nicht ebenfalls verarbeitet werden.

Im JSON-/CSV-Protokoll stehen ursprünglicher Name, Originalpfad,
`comparison_destination` für die bearbeitete Vergleichsdatei, Modellziel,
Quell- und Zielhash sowie die Anzahl entfernter Anmerkungen. Ein erneuter Lauf
legt die neuen Vergleichspaare auch für bereits vorhandene Modelleingaben an.
Frühere Sicherungen im alten Ordner `originale/` bleiben erhalten.

Seiteninhalt, eingescannte Markierungen, Formularfelder, Links und Schwärzungen
bleiben erhalten. Auch noch nicht angewendete PDF-Schwärzungsanmerkungen werden
beibehalten. Es erfolgt keine Bildretusche oder Wiederherstellung verdeckter Daten.

Eine bereits vorhandene Arbeitskopie wird nur dann nachträglich bereinigt,
wenn sie noch exakt der Eingabe entspricht und das Original zuvor gesichert
wurde. Abweichende Dateien bleiben als Konflikte erhalten. Wiederholungen
erkennen identische bereinigte Ergebnisse und überspringen sie. Nach einer
Bereinigung geänderter PDFs neue Extraktionsläufe und Seitenmanifeste erzeugen.

`--dry-run` zeigt auch die geplanten Bereinigungen und Sicherungen, ohne Dateien
anzulegen. Mit `--keep-annotations` lässt sich ausdrücklich der frühere reine
Kopiermodus verwenden; dabei findet keine zusätzliche Originalsicherung statt.

Technische Grundlage: [PyMuPDF-Anmerkungen](https://pymupdf.readthedocs.io/en/latest/page.html#Page.delete_annot).

Jeder echte Lauf erzeugt ein JSON- und ein in Excel lesbares CSV-Protokoll mit
Quellpfad, Zielpfad, Nummer, SHA256, Originalsicherung, Bereinigung und Status. Ein Probelauf mit `--dry-run`
zeigt die geplanten Aktionen und erzeugt keine Dateien oder Verzeichnisse.

Am Ende der Konsolenausgabe steht eine Zusammenfassung mit der Anzahl gefundener
Dateien und PDFs, gültiger bzw. nicht erfüllter IDs, neuer Kopien, aussortierter
PDFs, bereits vorhandener Dateien, Duplikate, Namenskonflikte und Fehler. Beim
Probelauf werden geplante Kopien ausgewiesen. Verknüpfungen werden separat
gezählt. Zusätzlich erscheinen die Anzahl neu gesicherter Originale, bereits
vorhandener bereinigter Arbeitskopien und entfernter Anmerkungen. Die Ergebniszeile
zeigt, ob der Lauf erfolgreich war oder Probleme hatte.

## Wiederholungen und Konflikte

- Bereits vorhandene identische Ziele werden per SHA256 erkannt und übersprungen.
- Gleiche Nummer und gleicher Inhalt im selben Zielordner werden einmal kopiert.
- Gleiche Nummer mit anderem Inhalt im selben Zielordner wird als `conflict`
  protokolliert; die zuerst kopierte bzw. vorhandene Datei bleibt erhalten.
  Bei mehreren Quellen bestimmt die alphabetische Durchsuchung die Reihenfolge.
- Aussortierte PDFs erhalten den Status `copied_rejected`, im Probelauf
  `would_copy_rejected`. Für sie gelten dieselben Prüfungen auf vorhandene
  Dateien und Konflikte.
- Kopierfehler werden pro Datei protokolliert; andere Dateien werden weiterbearbeitet.

Bei Konflikten, technischen Fehlern oder fehlenden PDFs liefert das Skript
Exitcode 1, sonst 0. Erfolgreiches Aussortieren ist kein Fehler. Betroffene Quellen korrigieren bzw.
mit eindeutigen IDs bzw. Dateinamen versehen und erneut ausführen. Bei gleicher
ID mit unterschiedlichem Inhalt wird eine manuelle Entscheidung benötigt.
Ausgabeordner
gehören außerhalb des Eingabeordners; überlappende Pfade werden abgelehnt.

Danach folgt die [eigentliche Verarbeitung](../verarbeitung/README.md).
