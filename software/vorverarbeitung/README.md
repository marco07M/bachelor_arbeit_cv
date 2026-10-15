# 1. Dokumentenvorverarbeitung

`vorbereiten.py` durchsucht standardmäßig `../../dateien/` einschließlich aller
Unterordner. Die Standardpfade sind relativ zur Skriptdatei und funktionieren
auch beim Aufruf aus einem anderen Arbeitsverzeichnis. Die Vorverarbeitung
verwendet nur die Python-Standardbibliothek (Python ab Version 3.12).

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
**ursprünglichen Dateinamen** unter `ausgabe/nicht_erfuellt/` kopiert.
Sie landen direkt in diesem Ordner. Das Protokoll nennt den Ablehnungsgrund.
Nur die PDFs unter `ausgabe/pdfs/` werden anschließend verarbeitet.

Die Eingabeunterordner werden weiterhin vollständig durchsucht. Im Ziel landen
alle gültigen PDFs direkt unter `pdfs/`, alle aussortierten direkt unter
`nicht_erfuellt/`. Das Protokoll bewahrt die ursprünglichen relativen Quellpfade.
Originale werden kopiert und
bleiben unverändert. Andere Dateitypen werden übersprungen. Die Vorverarbeitung
filtert nach Dateiendung; die technische PDF-Prüfung erfolgt in der Verarbeitung.
Verknüpfungen/Junctions werden nicht verfolgt.

Jeder echte Lauf erzeugt ein JSON- und ein in Excel lesbares CSV-Protokoll mit
Quellpfad, Zielpfad, Nummer, SHA256 und Status. Ein Probelauf mit `--dry-run`
zeigt die geplanten Aktionen und erzeugt keine Dateien oder Verzeichnisse.

Am Ende der Konsolenausgabe steht eine Zusammenfassung mit der Anzahl gefundener
Dateien und PDFs, gültiger bzw. nicht erfüllter IDs, neuer Kopien, aussortierter
PDFs, bereits vorhandener Dateien, Duplikate, Namenskonflikte und Fehler. Beim
Probelauf werden geplante Kopien ausgewiesen. Verknüpfungen werden separat
gezählt. Die Ergebniszeile zeigt, ob der Lauf erfolgreich war oder Probleme hatte.

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
