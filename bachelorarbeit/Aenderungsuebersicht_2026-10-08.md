# Änderungsübersicht zur Bachelorarbeit

Stand: 08.10.2026  
Grundlage: die übergebene Datei „Überarbeitung Kapitel 1, Bereinigung Kapitel 2 (2.1 & 2.2) und Abkürzungsverzeichnis“.

Dieses Dokument zeigt die Änderungen zum Gegenlesen. Maßgeblich für den Satz der Arbeit sind weiterhin die LaTeX-Dateien.

## 1. Änderungen auf einen Blick

| Datei | Änderung |
| --- | --- |
| `chapters/01_einleitung.tex` | Einen Satz zur noch ausstehenden Datensichtung entfernt; TrOCR und VLM im Text als Abkürzungen markiert. |
| `chapters/02_grundlagen.tex`, Abschnitt 2.1 | Beschreibung der Dokumentbildanalyse, Layoutanalyse und Informationsextraktion gestrafft; die mengentheoretische Extraktionsformel entfernt. |
| `chapters/02_grundlagen.tex`, Abschnitt 2.2 | OCR und HTR präzisiert; Vorverarbeitung und Architekturvergleich als Fließtext formuliert; die Sauvola-Formel entfernt. |
| `frontmatter/abkuerzungsverzeichnis.tex` | CER, DIA, DLA, TrOCR und VLM ergänzt. OCR und HTR waren bereits vorhanden. |
| `chapters/03_methodik.tex` | Character Error Rate als `\ac{cer}` markiert. |

Die vorhandenen Literaturquellen wurden weiterverwendet. Es wurden keine doppelten BibTeX-Einträge aus der Übergabe angelegt.

## 2. Kapitel 1: konkrete Änderung

Am Ende des Absatzes über den GNHK-Datensatz wurde dieser Satz entfernt:

> Welche Eigenschaften im vorhandenen Bestand tatsächlich auftreten und wie häufig sie vorkommen, ist im Rahmen der Datensichtung zu erfassen.

Der Absatz endet nun mit der Folgerung, dass die Eigenschaften des betrieblichen Anwendungsfalls bei der Zusammenstellung und Auswertung der Testdaten berücksichtigt werden müssen. Die Datengrundlage und ihre spätere Beschreibung bleiben in Kapitel 3 behandelt.

Die zusätzlich vorgeschlagene Behauptung über den betrieblichen Bestand wurde nicht übernommen, weil er laut aktuellem Stand noch gesichtet und vorverarbeitet werden muss. Kapitel 1 beschreibt weiterhin die bereits bekannten möglichen Varianten und ihren Einfluss auf die Verarbeitung.

Die Erstnennung von TrOCR ist nun mit `\ac{trocr}` markiert. In der Übersicht über den Aufbau der Arbeit steht „Vision-Language-Modelle (VLM)“ mit einem LaTeX-Verweis auf das Abkürzungsverzeichnis. Sonst wurde Kapitel 1 inhaltlich nicht umgebaut.

## 3. Kapitel 2.1: Neufassung zum Gegenlesen

### Automatisierte Dokumentenverarbeitung und Informationsextraktion

Unter **Document Image Analysis (DIA)** werden Verfahren zur Erkennung und Auswertung visueller Bestandteile digitalisierter Dokumente zusammengefasst [O'Gorman und Kasturi, 1997]. Bei den hier betrachteten PDF-Dateien beginnt die Verarbeitung mit der Auswahl und Ausrichtung relevanter Seiten. Anschließend werden Bereiche lokalisiert, Texte erkannt und die Angaben den vorgesehenen Feldern zugeordnet. Diese Schritte können getrennt oder gemeinsam durch ein Modell umgesetzt werden.

Ein Teilbereich ist die **Document Layout Analysis (DLA)**. O'Gorman und Kasturi unterscheiden dabei eine geometrische Ebene, auf der beispielsweise Textzeilen und Blöcke abgegrenzt werden, und eine funktionale Ebene, auf der die Bereiche eine Bedeutung erhalten. Bei Teilnehmerlisten betrifft dies die Erkennung von Zeilen und Spalten sowie die Zuordnung zu Feldern wie Vorname, Personalnummer oder Unterschrift. Eine richtig transkribierte Zeichenfolge im falschen Feld ist deshalb kein korrektes Extraktionsergebnis. Für die Fehleranalyse ist diese Unterscheidung hilfreich, auch wenn ein Verfahren beide Aufgaben in einem Schritt bearbeitet.

Die Informationsextraktion überführt erkannte Inhalte in ein vorgegebenes Zielschema. Das Ergebnis soll für jede erfasste Teilnehmerzeile Vorname, Nachname, Personalnummer, Abteilung und das Vorhandensein einer Unterschrift enthalten. Dafür müssen zusammengehörige Angaben derselben Zeile zugeordnet werden. Skalický et al. unterscheiden die Extraktion einzelner Schlüsselinformationen von der Erkennung zusammengehöriger Einträge innerhalb eines Dokuments. Fehlende und nicht lesbare Werte sind dabei gesondert zu kennzeichnen. In der späteren Bewertung werden Transkriptionsfehler, falsche Zeilen- oder Feldzuordnungen und unbegründete Ergänzungen getrennt betrachtet.

Bekannte Formularpositionen können die Lokalisierung bei vorlagenbasierten Verfahren vereinfachen. Bei festen Koordinaten müssen jedoch Verschiebungen, Skalierung und Drehung berücksichtigt werden. Layoutorientierte Modelle wie LayoutLM zeigen einen anderen Ansatz, indem sie Text und räumliche Position gemeinsam für Aufgaben des Dokumentenverständnisses modellieren. Ob solche Ansätze für die vorliegenden handschriftlichen Listen geeignet sind, ist Gegenstand der Untersuchung.

**Gegenüber der vorigen Fassung:** Die Formel für Zeilen-Feld-Wert-Tupel samt Variablendefinitionen ist entfallen. Das Ziel der Extraktion und die möglichen Fehlerarten werden direkt im Text beschrieben. Auch der Satz „Welche Varianten im untersuchten Bestand tatsächlich auftreten und ob eine solche Strategie geeignet ist, lässt sich erst nach der Datensichtung beurteilen“ wurde durch die knappere Einordnung der Modelleignung ersetzt.

## 4. Kapitel 2.2: Neufassung zum Gegenlesen

### Optical Character Recognition und Handwritten Text Recognition

**Optical Character Recognition (OCR)** bezeichnet die Überführung von Textbildern in maschinenlesbaren Text. Der Begriff umfasst auch die Erkennung handschriftlicher Eingaben; TrOCR wird beispielsweise als OCR-Verfahren vorgestellt und auf gedruckten sowie handschriftlichen Textbildern untersucht [Li et al., 2023]. **Handwritten Text Recognition (HTR)** bezeichnet in dieser Arbeit die speziell auf Handschrift bezogene Erkennungsaufgabe. Diese Arbeitsdefinition unterstützt die spätere Auswertung, ohne beide Begriffe als grundsätzlich getrennte Verfahrensklassen zu behandeln.

Handschriftliche Einträge können zwischen Schreibenden und innerhalb eines Dokuments in Form, Größe und Verbindung der Zeichen variieren. Besonders bei verbundener Schrift ist die Segmentierung in einzelne Zeichen schwierig; Erkennungsverfahren können daher auf Wort- oder Zeilenbildern ansetzen [Plötz und Fink, 2009]. **Connectionist Temporal Classification (CTC)** ermöglicht es Sequenzmodellen, Ausgabefolgen ohne vorgegebene Ausrichtung jedes Zeichens zum Eingabesignal zu lernen [Graves et al., 2006]. Die Originalarbeit belegt damit keine konkrete Erkennungsleistung auf den hier untersuchten Teilnehmerlisten.

Je nach Dokument und Modell können vor der Erkennung Bildbereiche ausgerichtet, entrauscht, binarisiert oder segmentiert werden. Bei einer globalen Binarisierung gilt ein Schwellenwert für das gesamte Bild; Otsus Verfahren ermittelt ihn aus dem Grauwert-Histogramm [Otsu, 1979]. Lokale Verfahren wie das von Sauvola und Pietikäinen beschriebene berücksichtigen die Umgebung einzelner Bildbereiche und können dadurch auf wechselnde Bildbedingungen reagieren [Sauvola und Pietikäinen, 2000]. Ob eine Binarisierung hilfreich ist, muss für die eingesetzten Modelle geprüft werden.

Zur Korrektur einer Seitenschräglage beschreiben O'Gorman und Kasturi unter anderem Projektionsprofile und die Hough-Transformation. Anschließend können Textzeilen oder Formularbereiche segmentiert werden. Bei handschriftlich ausgefüllten Teilnehmerlisten ist zu prüfen, wie sich berührte oder überschrittene Zellgrenzen auf diese Schritte auswirken. Auch nach einer korrekten Transkription müssen erkannte Angaben noch der richtigen Zeile und dem richtigen Feld zugeordnet werden.

Mehrstufige Systeme können Fehler früher Verarbeitungsschritte an spätere Schritte weitergeben. Daneben gibt es Ansätze, die Aufgaben zusammenfassen: TrOCR konzentriert sich auf die Erkennung eines Textbilds [Li et al., 2023], während Donut ein Dokumentbild ohne vorgeschaltetes externes OCR-System direkt in eine aufgabenspezifische Ausgabe überführt [Kim et al., 2022]. Die Verfahren lösen damit unterschiedliche Teilaufgaben; ihre Leistung für die vorliegenden Listen muss unter vergleichbaren Bedingungen ermittelt werden.

**Gegenüber der vorigen Fassung:** Die Sauvola-Gleichung und die Erläuterung ihrer Variablen sind entfallen. Otsu und Sauvola bleiben als Beispiele für globale und lokale Schwellenwertverfahren mit Quellenangaben erhalten. Die Vorverarbeitung wird ausdrücklich als abhängig von Dokument und Modell beschrieben.

## 5. Fachliche Abweichungen von der Übergabe

- Die Vorlage trennte OCR strikt von Handschrifterkennung. Das wurde nicht übernommen, weil OCR auch auf handschriftliche Textbilder angewandt wird; TrOCR ist dafür ein Beispiel.
- Die Vorlage stellte eine weitgehende Verdrängung klassischer Verfahren durch End-to-End-Modelle fest. Dieser allgemeine Trend wurde ohne belastbare Abgrenzung und Quelle nicht als Befund übernommen. Stattdessen werden unterschiedliche Architekturen und ihre jeweiligen Aufgaben beschrieben.
- Aussagen über die tatsächliche Häufigkeit von Dokumentvarianten, über die Eignung vorlagenbasierter Verfahren und über die Leistung auf den betrieblichen Listen bleiben Gegenstand der geplanten Datensichtung und Evaluation.
- Die numerischen Literaturverweise der Übergabe wurden in den LaTeX-Dateien durch die vorhandenen BibTeX-Schlüssel ersetzt. Die Nummern im fertigen Literaturverzeichnis vergibt BibTeX.

## 6. Prüfung

Der Build wurde nach den Änderungen ausgeführt. Die PDF liegt unter `studienarbeiten/thesis/build/thesis.pdf`; die vorhandene Kopie unter `output/pdf/thesis.pdf` wird durch das Build-Skript ebenfalls aktualisiert.

## 7. Nachtrag: Abschnitte 2.4 und 2.5

Die am 08.10.2026 nachgereichte Vorlage für **Vision-Language-Modelle** und **hybride Verfahren** ist in `chapters/02_grundlagen.tex` eingearbeitet. Der folgende Überblick zeigt die inhaltlichen Änderungen und die Stellen, an denen die Formulierungen der Vorlage präzisiert wurden.

### Abschnitt 2.4: Vision-Language-Modelle

Der Abschnitt unterscheidet jetzt dokumentenspezifische Modelle wie Donut von allgemeinen, per Bild-Text-Instruktion gesteuerten Modellen wie LLaVA. Donut wird als Verfahren ohne **vorgeschaltetes eigenständiges OCR-Modul bei der Anwendung** erklärt. Beschrieben sind visueller Encoder, Textdecoder, aufgabenspezifischer Prompt und die Umwandlung der Tokenfolge in eine strukturierte Ausgabe. Die Gleichung zur autoregressiven Generierung berücksichtigt ausdrücklich sowohl das Dokumentbild als auch den Aufgabenprompt:

`P(Y | I, q) = Produkt über t von P(y_t | y_<t, I, q)`

Im zweiten Teil werden die für Teilnehmerlisten relevanten Grenzen aus OCRBench v2 eingeordnet: Textlokalisierung, handschriftliche Inhalte und Layoutverständnis. Mögliche unbegründete Feldwerte, Laufzeit, Speicherbedarf und Kosten sind als **zu prüfende Kriterien** formuliert. Die Ergebnisse der veröffentlichten Arbeiten werden nicht als Messergebnis für die betrieblichen Listen ausgegeben.

Die pauschale Aussage der Vorlage, multimodale Modelle seien grundsätzlich OCR-frei, wurde nicht übernommen. Ebenso wurden keine allgemeinen Aussagen über eine bestimmte Halluzinationsrate oder einen generellen Kosten- und Geschwindigkeitsnachteil großer Modelle eingefügt.

### Abschnitt 2.5: Hybride Verfahren

Der Abschnitt beschreibt eine mögliche mehrstufige Pipeline: Bildbereiche lokalisieren, ausgeschnittene Bereiche transkribieren und die erkannten Werte den Teilnehmerzeilen und Zielfeldern zuordnen. Ein Sprachmodell kann die Strukturierung übernehmen; es ist keine zwingende Komponente jedes hybriden Verfahrens.

**Wichtige Korrektur zur Vorlage:** TrOCR transkribiert ein vorgegebenes Textbild. Es liefert nicht selbst die Feldkoordinaten; diese müssten von einer gesonderten Lokalisierung oder Segmentierung kommen. Eine Bildstelle bleibt für die spätere Kontrolle nur dann nachvollziehbar, wenn Koordinaten und Feldzuordnung korrekt gespeichert werden. Der Vorteil entsteht also durch die konkrete Systemgestaltung, nicht automatisch durch die Bezeichnung „hybrid“.

Fehlerfortpflanzung und Nachprüfbarkeit werden mit Quellen und Grenzen erläutert. Es wird keine generelle Überlegenheit bei Genauigkeit, Geschwindigkeit oder Kosten behauptet. Der Vergleich soll mit denselben Dokumenten und einem vergleichbaren Bearbeitungsstand erfolgen.

### Abkürzungen und Quellen

`LLM` war bereits im Abkürzungsverzeichnis enthalten; die erste ausgeschriebene Verwendung in Kapitel 2 ist nun mit `\ac{llm}` markiert. LLaVA wurde als weiterer Eintrag ergänzt. OCR, HTR, VLM und JSON verwenden ebenfalls die vorhandenen LaTeX-Abkürzungseinträge. Es wurden zwei geprüfte Quellen ergänzt:

- [Liu et al. (2023), Visual Instruction Tuning](https://proceedings.neurips.cc/paper_files/paper/2023/hash/6dcf277ea32ce3288914faf369fe6de0-Abstract-Conference.html), als Beispiel für ein allgemeines instruktionsgesteuertes Bild-Sprach-Modell.
- [van Strien et al. (2020), Assessing the Impact of OCR Quality on Downstream NLP Tasks](https://www.scitepress.org/Papers/2020/91690/), zum Einfluss von OCR-Fehlern auf nachgelagerte Aufgaben. **Korrektur:** Die Vorlage ordnete diese Arbeit LREC mit den Seiten 4846–4855 zu. Laut Verlag erschien sie bei ICAART, Band 1, Seiten 484–496, DOI 10.5220/0009169004840496.

Die Donut- und OCRBench-v2-Quellen standen bereits in `verified_sources.bib` und wurden nicht doppelt angelegt.
