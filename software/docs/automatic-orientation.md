# Automatische Seitenausrichtung

Stand: 11.11.2026. Repariert ist die gemeinsame automatische Vorbereitung selbst.
Der normale `start_testframework_5.cmd` verwendet die neue Ausrichtung ohne ein
zusätzliches manuelles Manifest. Voraussetzung ist das bereits aktive
`pdf.auto_orient: true`; neue Modelle, Gewichte oder Abhängigkeiten sind nicht nötig.

## Ablauf und Entscheidung

1. PDF-Rotationsmetadaten werden beim Rendern durch PyMuPDF berücksichtigt;
   Bilddateien erhalten wie bisher ihre EXIF-Ausrichtung.
2. Tesseract-OSD schlägt eine zusätzliche Drehung vor. Ein gültiges Ergebnis
   oberhalb der vorhandenen Schwelle `pdf.osd_min_confidence` (Standard 5)
   wird übernommen.
3. Bei schwachem oder fehlgeschlagenem OSD wird dasselbe Bild zusätzlich bei
   0°, 90°, 180° und 270° mit vorhandener Tesseract-OCR untersucht. `--psm 11`
   sucht verstreuten Text ohne eigene automatische Ausrichtung. Diagnosebilder
   sind auf höchstens 2.600 Pixel längste Seite begrenzt; eine übliche 220-DPI-
   A4-Seite bleibt damit in Originalauflösung. Diese Begrenzung verändert nicht
   die späteren Extraktionsbilder. OSD und jeder Zusatzaufruf haben höchstens
   15 Sekunden beziehungsweise das kleinere konfigurierte OCR-Timeout.
4. Der Vergleich zählt Tokens mit mindestens drei Buchstaben, mindestens 60 %
   Buchstabenanteil und endlicher Engine-Konfidenz von 50 bis 100. Der Score ist
   die Summe der Buchstabenanzahl gewichtet mit der Engine-Konfidenz geteilt
   durch 100. Dies ist ein technischer Vergleichsscore, keine Wahrscheinlichkeit.
5. Der Gewinner braucht mindestens fünf solche Wörter und 25 Buchstaben.
   Sein Score muss mindestens 15 über dem zweitbesten liegen und mindestens
   dessen 1,5-Faches erreichen. Fehlende Kandidaten, Timeout/Fehler oder zu
   ähnliche Ergebnisse lassen die Entscheidung offen. Der Vergleich allein
   erzwingt keine Drehung anhand reiner Zahlen, eines einzelnen Logos oder
   fehlender Texte. Ein ausreichend sicherer OSD-Befund bleibt ein eigener Weg.
6. Nur eine akzeptierte Entscheidung dreht die ursprünglichen vollständigen
   Pixel im Uhrzeigersinn. Unklare Seiten bleiben unverändert und prüfpflichtig;
   ein angewendeter Winkel von 0° ist dort keine Bestätigung richtiger Orientierung.

Die Grenzen sind offengelegte technische Schutzregeln, keine empirisch optimalen
oder statistisch kalibrierten Schwellen. Es werden weder Teilnehmerreferenzen
noch Feldformate, Namen, Dokumentkennungen oder frühere manuelle Drehwinkel zur
automatischen Entscheidung herangezogen. Die Diagnose speichert keine erkannten
Wörter und übernimmt sie nicht als Feldwerte.

Die offizielle [Tesseract-Dokumentation](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html#page-segmentation-method)
beschreibt PSM 11 als Suche nach verstreutem Text und unterscheidet es von
PSM 12 mit OSD. Unser Vierlagenvergleich und seine Schutzregeln sind eine eigene
Implementierung, keine von Tesseract garantierte Erkennungsgenauigkeit.

## Integration, Daten und Berichte

`orientation.py` enthält Entscheidung und Score, `OCR.orientation_evidence` die
begrenzten CPU-Aufrufe. `pdf.prepare` übernimmt das Ergebnis genau einmal nach
der PDF-Metadatenrotation. Die bisherigen OCR-Extraktionsparameter, Literal-/
Positionsvalidierung, Prompts, Modelle und Matchingregeln bleiben unverändert.

Alle Verfahren erhalten danach dasselbe vorbereitete Seitenbild. Das gilt für
Tesseract, Paddle und die visuellen Verfahren. Docling verpackt Scans verlustfrei
aus diesem Bild; bei nativem PDF-Text werden Metadaten- und Zusatzrotation im
einseitigen PDF passend kombiniert. Ein nativ neu gerendertes Vektor-PDF kann
an Kanten andere Antialiasing-Pixel besitzen als ein gedrehtes Raster; die
Ausrichtung wird deshalb anhand gerichteter Markierungen geprüft.

OSD-Konfidenz und OCR-Vergleich bleiben getrennt im Manifest:

- `orientation_confidence` und `orientation_proposed_clockwise`: ursprünglicher
  OSD-Befund; bei OSD-Fehler bleibt der Vorschlag unbekannt;
- `orientation_method`, `orientation_status`, `orientation_evidence`:
  Entscheidungsweg, Annahme/Ablehnung, vier Scores, Zähler und Schutzregeln;
- `additional_rotation_clockwise`: tatsächlich angewendete Zusatzdrehung;
- `orientation_seconds`: komplette Ausrichtungszeit einschließlich Zusatzaufrufen.

Hauptbericht und Fehlerbericht zeigen Methode/Status; die Seitenkette enthält
die vollständige Evidenz. Die gemeinsame Vorbereitungszeit wird wie bisher
separat erfasst und in der zugerechneten End-to-End-Zeit berücksichtigt.
Die eigentlichen LLM-/VLM-Aufrufzähler enthalten keine CPU-Orientierungsdiagnosen.

Für wissenschaftliche Vergleiche muss diese gemeinsame Vorverarbeitung eingefroren
und berichtet werden: Auch die direkte VLM-Feldextraktion bekommt jetzt ein
mithilfe von OCR-Textdiagnosen ausgerichtetes Bild. Es erhält daraus keine
OCR-Feldtexte. Eine vollständig OCR-freie Gesamtpipeline darf deshalb nicht
behauptet werden. Die Zusatzzeit gehört zur Vorbereitung aller Vergleichspfade.

Neue Manifeste tragen `orientation_implementation=orientation-v1-osd-ocr-comparison`.
Alte ungeprüfte automatische Manifeste werden bei aktiver automatischer Ausrichtung
nicht stillschweigend wiederverwendet; sie müssen neu vorbereitet werden.
Ausdrücklich kuratierte manuelle Manifeste bleiben bei passenden Eingabe-/Bild-
und Konfigurationsprüfsummen verwendbar. Alte Modellläufe können wegen geänderter
Codeidentität nicht als unverändert fortgesetzt werden. Historische PDFs,
Extraktionen und Ergebnisse werden nicht überschrieben.

## Tatsächlich durchgeführte Prüfung

Die vorhandenen zehn Entwicklungs-PDFs mit zwanzig Seiten wurden durch den neuen
regulären `prepare`-Pfad automatisch vorbereitet, ohne manuelles Manifest und
ohne LLM-/VLM-Inferenz. Erst nach der Entscheidung wurden die Ergebnisse mit
der zuvor visuell geprüften Orientierungsannotation verglichen:

| Nachweis | Ergebnis |
|---|---:|
| Korrekte Ausrichtung auf diesem Entwicklungsbestand | 20/20 Seiten |
| Gedrehte Seiten | 12 |
| Bereits richtig ausgerichtet und beibehalten | 8 |
| Entscheidung durch OSD | 1 |
| Entscheidung durch OCR-Vergleich | 19 |
| Weiterhin prüfpflichtig in diesem Bestand | 0 |
| Vollständige Pixel gleich den zuvor geprüften Rotationen | 20/20 |
| Unveränderte Original-PDFs | 10 |
| Unveränderte geschützte historische Dateien | 1.762 |

Die neue Vorbereitung benötigte hier beobachtet etwa 84,64 Sekunden; dies ist
keine kontrollierte Geschwindigkeitsstudie. Ein Vorabversuch mit auf 2.000 Pixel
verkleinerten Diagnosebildern blieb auf einer dünn beschrifteten Folgeseite
unentschieden. Die endgültige Begrenzung erhält die vorhandene Originalauflösung;
bei unveränderten Entscheidungsschwellen sind dort fünf lesbare Wörter statt
vier belegbar. Keine pauschale Absenkung der OSD-/Entscheidungsschwellen.

Zusätzliche synthetische Drucktexte werden bei allen vier Winkeln richtig
ausgerichtet. Vier Regressionen simulieren gezielt einen OSD-Ausfall und nutzen
danach echte Tesseract-Textdiagnosen, einschließlich der 180°-Lage. Leerseite und
einzelnes Logo bleiben bei fehlendem OSD-Befund unentschieden; eine reine
Ziffernseite bleibt mit hinreichend sicherem OSD bei 0°.

48 neue Regressionen prüfen außerdem geringe/ungültige Scores, Gleichstände,
fehlende Kandidaten, Timeouts, unveränderte Originalpixel, Metadatenrotation und
Zusatzrotation in allen 16 Kombinationen, den nativen Docling-Pfad sowie die
Ablehnung alter ungeprüfter Manifeste. Abschließend bestanden **820 lokale Tests
in 96,21 s** und **48 API-Tests in 9,77 s**; Ruff ohne Befund.

Lokale Nachweise unter `data/auto-orientation-20261111/`:
`prepared/manifest.json`, `real_validation.json`, `validation.json`,
`synthetic_validation.json`, `automatic-contact.png` und `preview.html`.
Personenbezogene Bilder bleiben in ignorierten lokalen Ordnern.

Das ist ein technischer Nachweis auf bekannten Entwicklungsdaten, keine Garantie
für jede künftige Handschrift, Sprache oder textarme Seite. Die früher gefundenen
Tokenabbrüche, fehlerhaften Modellheader und Referenzabweichungen sind davon
unabhängig. Ein neuer vollständiger Modellvergleich mit den korrigierten Bildern
steht noch aus; keine verbesserte Feldqualität behaupten.
