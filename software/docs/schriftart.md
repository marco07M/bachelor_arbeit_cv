# Teilnehmerbezogene Schriftart in Ground Truth und Evaluation

Stand: 18.11.2026. Die optionale Annotation `schriftart` beschreibt eine ganze
Referenzperson beziehungsweise Teilnehmerzeile:

| Wert | Kategorie |
|---|---|
| `h` | Handschrift |
| `m` | Maschinenschrift |
| `g` | Gemischt |
| leer / JSON `null` / nicht vorhanden | Nicht klassifiziert |

`g` ist eine eigene, disjunkte Teilnehmerkategorie. Eine gemischte Zeile wird
nicht zusätzlich unter h oder m gezählt. Die Annotation erlaubt **keine Aussage,
welche einzelnen Felder** handschriftlich sind. Eine Feldtypanalyse innerhalb g
ist weiterhin eine Auswertung gemischter Teilnehmer, keine feldgenaue HTR-Studie.
Die Kennzeichnung kommt ausschließlich aus manuell gepflegter Ground Truth.
Seitenmerkmale wie `content_type=typed` oder Dokument-`stratum` und Modellausgaben
liefern keinen automatischen Standardwert. Fehlende Annotation ist niemals m.

## Analyseseite „Handschrift vs. Maschinenschrift“

Neue wissenschaftliche Berichte enthalten die verlinkte Datei
`handschrift_maschinenschrift.html`. Sie ergänzt Bereich H, verwendet die
gespeicherten `original_roles`-Feldentscheidungen und ruft bestehende
`document_availability.project`, `scores` und `sum_counts` auf. Keine erneute
Zuordnung, neue Normalisierung oder Levenshteinimplementierung.

Die Kennzeichnung liegt weiterhin **pro Teilnehmer** vor. „Vorname in Gruppe h“
bedeutet Vorname einer mit h annotierten Teilnehmerzeile; es ist kein unabhängig
feldgenau annotiertes Handschriftlabel. Insbesondere werden g-Zeilen weder nach
h/m aufgeteilt noch anhand der Modellausgabe nachklassifiziert. Unterschriften
bleiben reine Präsenzbefunde und sind kein fünftes Textfeld.

### Verteilung, Qualität und Fehleranteile

- Referenzverteilung: Anzahl/Anteil der bewertbaren nichtleeren Referenzfelder R
  pro h/m/g/unklassifiziert und je Vorname, Nachname, Personalnummer, Organisation.
  Die gemeinsame Ground Truth wird einmal gezählt, nicht einmal je Verfahren.
- Qualität: bestehender Exact Recall E/R, Coverage (R−M)/R, E korrekt, W vorhanden
  und abweichend, M ohne nutzbaren Endwert. R=E+W+M bleibt unverändert.
- M wird zusätzlich getrennt in vollständig fehlende/leere Original-Endwerte
  und vorhandene, aber nicht nutzbare Endwerte (beispielsweise ID-Platzhalter).
  Das ist eine Diagnose der vorhandenen Fehlwertzählung und kein neuer Score.
  Unklare Zuordnungen werden zusätzlich als bestehender Anzeigestatus ausgewiesen;
  solche Statuszahlen überlappen mit den E/W/M-Beiträgen.
- Ähnlichkeit: bestehende Summe normalisierter Ähnlichkeiten / D auf vorhandenen
  Feldpaaren. Falsche ausgefüllte Werte werden nicht herausgefiltert; D=0 undefiniert.
- Fehlerrate: W/R, M/R beziehungsweise (W+M)/R innerhalb derselben Gruppe.
- Fehleranteil: W_gruppe/ΣW, M_gruppe/ΣM beziehungsweise
  (W+M)_gruppe/Σ(W+M) desselben Verfahrens im aktuellen Dokument-/Feldumfang.
  Die Summen enthalten auch g und unklassifiziert. Bei null Gesamtfehlern ist
  der Anteil undefiniert, nicht 0 %. Gruppen ohne R haben keine gemessene Qualität.

Diagramme trennen erwartete Feldanteile, relative E/W/M-Raten und Anteile an allen
Referenzfeldfehlern. Absolute Zähler und Nenner stehen daneben. So wird ein größerer
Fehlerumfang einer größeren Gruppe nicht mit einer höheren Fehlerrate verwechselt.

Filter: Verfahren, Feldtyp, Dokument/Referenzumfang, Teilnehmer-Schriftart und
Bewertungsgrundlage. Der Schriftartfilter blendet Kategorien aus, renormalisiert
deren Anteile aber **nicht** auf die sichtbare Kategorie. Verfahrenfilter ändern
die gemeinsame Referenzverteilung nicht. Alle Qualitätswerte werden mit vorhandenen
Python-Funktionen vorab berechnet; JavaScript stellt Tabellen/Diagramme dar und
berechnet keine zweite Metrikdefinition. Einzelfelder zeigen GT, unveränderten
Originalwert, bestehenden Status, Ähnlichkeit und vorhandene PDF-Links.

### Referenzumfang und unabhängiger Dokumentinhalt

Die Standardansicht behält sämtliche Referenzfelder, auch ungeprüfte. Daneben steht
die bereits vorhandene Zusatzbewertung ausschließlich auf unabhängig lesbaren,
referenzgleichen Originalfeldern (R_doc). Leere/unleserliche Originale, lesbare
Referenzkonflikte, ungeprüfte und unklare Fälle bleiben getrennt sichtbar. Ohne
geprüfte lesbare Basis ist die Zusatzqualität nicht definiert. Eine selektive,
assistierte Einzelprüfung einfacher Druckwerte erlaubt keine repräsentative
Handschrift-Rangfolge; Prüfprovenienz bleibt im verlinkten Originalprotokoll.

Dokumentfilter verwenden Referenzumfang oder vorhandene unabhängige
Teilnehmerlokalisierung aus `--page-annotations`, niemals die Ausgabeposition.
Bei genau einem PDF pro Kurs wird dessen vollständige Kursreferenz zugeordnet,
einschließlich fehlender Teilnehmer. Das beweist nicht die Anwesenheit jeder
Person im Original. Bei mehreren PDFs ohne unabhängige Lokalisierung bleiben
Referenzfelder unter „PDF-Zuordnung ungeprüft“; sie werden weder auf alle PDFs
dupliziert noch beim Filtern aus dem Gesamtumfang entfernt.

Ungepaarte Zusätze haben keine GT-Schriftart. Ihre globalen FP-/P-/F1-Beiträge
bleiben unverändert und sind separat im JSON sowie im bestehenden Audit erhalten.
Auch ausdrücklich leere/maskierte/unbekannte GT folgt weiterhin bestehenden Regeln.

Neue Exporte: `scientific/schriftart_analysis.json` (alle Filterkombinationen,
Nenner, Einzelbelege, Prüfbindungen) und `schriftart_analysis.csv` (Tabellen).
Alte Berichte werden nicht überschrieben. Ohne neue Inferenz neu auswerten:

```powershell
.\.venv\Scripts\python.exe testframework/main.py analyze `
  --report testframework/ergebnisse/BESTEHEND --output testframework/ergebnisse/NEU
```

Vorhandene Originalprüfungen und unabhängige Lokalisierungen bei Bedarf explizit
mit `--document-annotations` und `--page-annotations` wiederverwenden; sie müssen
zu den eingefrorenen PDF-/Referenzbindungen passen. `analyze` liest spätere
Änderungen einer Excel-Datei nicht als Ersatz für seinen Snapshot ein.

### Nachweis an vorhandenen Läufen (18.11.2026)

Ohne neue Modellinferenz wurden drei neue Berichte erzeugt; ihre bisherigen
`metrics.json` und alle fünf Matchingübersichten stimmen exakt mit den jeweiligen
Quellen überein. 4.077 geschützte historische Dateien sind hashgleich geblieben.

- [Neuester Dreidokumentlauf](../testframework/ergebnisse/handschrift-maschinenschrift-20261118-aktuell/handschrift_maschinenschrift.html):
  47 Referenzpersonen, 188 Felder; h 16/64 Felder (34,04 %), m 31/124 Felder
  (65,96 %). g/unklassifiziert im ausgewerteten Umfang jeweils null. Sämtliche
  Originalfelder bisher ungeprüft; dokumentbasierte Qualität nicht definiert.
- [Vergleich auf zehn PDFs](../testframework/ergebnisse/handschrift-maschinenschrift-20261118-zehn-pdfs/handschrift_maschinenschrift.html):
  155 Referenzpersonen, 620 Felder; h 44/176 Felder (28,39 %), m 111/444 Felder
  (71,61 %). Pro Feldtyp R_h=44 und R_m=111. Die 15 weiteren unklassifizierten
  Personen im Snapshot liegen außerhalb dieses PDF-/Kursumfangs. Keine g-Zeilen
  im bewerteten Umfang. Nur 86 unabhängig lesbare, referenzgleiche Felder,
  sämtlich Gruppe m; 13 lesbare Referenzkonflikte bleiben separat. Daher kein
  dokumentgeprüfter h/m-Vergleich und keine kausale Aussage über reine HTR-Leistung.
- [Separater älterer Docling-Lauf](../testframework/ergebnisse/handschrift-maschinenschrift-20261118-docling/handschrift_maschinenschrift.html):
  18 Referenzpersonen/72 Felder, alle im eingefrorenen Snapshot unklassifiziert;
  30 unabhängig lesbare, referenzgleiche Felder. h/m-Vergleich nicht definiert.
  Aktuelle Labels werden nicht nachträglich in andere Referenzstände übertragen;
  diese andere Datenbasis wird nicht in den Zehn-PDF-Vergleich eingemischt.

Exakter Feld-Recall auf der unveränderten **Referenzbasis des Zehn-PDF-Laufs**:

| Verfahren | h: E/R | m: E/R |
|---|---:|---:|
| `ocr_llm` | 6/176 = 3,41 % | 355/444 = 79,95 % |
| `paddle_llm` | 42/176 = 23,86 % | 355/444 = 79,95 % |
| `vlm` | 17/176 = 9,66 % | 327/444 = 73,65 % |
| `ocr_vlm` | 29/176 = 16,48 % | 360/444 = 81,08 % |

Bei `paddle_llm`, `vlm` und `ocr_vlm` zeigt die Personalnummer den größten
h/m-Abstand im exakten Feld-Recall (78,30 / 78,38 / 82,41 Prozentpunkte), bei
`ocr_llm` der Vorname (91,85 Prozentpunkte). Dies beschreibt Teilnehmergruppen
unter Referenzbewertung, keine unabhängig pro Feld annotierte Schrifterkennung.
Unterschiedliche Dokumentverfügbarkeit, Dokumente und Zuordnungsfehler können
mitwirken. Vollständige E/W/M-Zahlen, Coverage, bedingte Ähnlichkeit und
Fehleranteile stehen in den verlinkten Seiten und maschinenlesbaren Exporten.

## Erfassen, bearbeiten, importieren und exportieren

**Kursreferenz XLSX/CSV:** optionale Spaltenüberschrift `schriftart`. Die
vorhandenen fünf Inhalts-/Identitätsspalten bleiben unverändert. Leere Zellen
werden `None`; h/m/g werden außen getrimmt und kleingeschrieben. Andere Werte,
Zahl-/Boolwerte oder doppelte Schriftartspalten werden abgewiesen. Bei ausdrücklich
aktivierter Dublettenverschmelzung werden widersprüchliche Schriftarten nicht
willkürlich ausgewählt. Annotation beeinflusst keine Matchingfelder oder
Dublettenidentität. Fehlende optionale Zellen am Ende gestreamter XLSX-Zeilen
bleiben unklassifiziert.

Eine bearbeitbare **Kopie** der eingefrorenen Referenz erzeugen, aus `software/`:

```powershell
.\.venv\Scripts\python.exe testframework/main.py reference-template --report testframework/ergebnisse/20261116T105322Z-37e601f2 --output data/meine-referenz-schriftart.xlsx
```

Alternativ ist `.csv` zulässig. Der Befehl verweigert vorhandene Zieldateien und
kopiert nur die eingefrorene GT, keine Modellausgaben. Der XLSX-Export besitzt
im Blatt `Referenz` eine h/m/g-Auswahlliste mit erlaubten Leerzellen; CSV kann in
einem Text-/Tabelleneditor bearbeitet werden. Feldstatusspalten bleiben erhalten,
IDs bleiben Text und formelähnliche Inhalte werden nicht als Formeln geschrieben.
Die Kopie kann weitere Kurse enthalten, die nicht im gewählten PDF-Umfang liegen;
die normale Kursabgrenzung bleibt wirksam.

Die normale `participants.xlsx` enthält `schriftart` im GT-Blatt `Referenz`.
Modellblätter erhalten kein Schriftartfeld. Das GT-Blatt ausdrücklich auswählen,
wenn eine solche Mehrblattdatei als Referenz verwendet wird. Die separate Vorlage
oben hat `Referenz` als erstes Blatt und benötigt diese Auswahl nicht.

Nach der **manuellen** Annotation die gespeicherten Extraktionen erneut gegen
diese Kopie vergleichen, ohne neue Inferenz:

```powershell
.\.venv\Scripts\python.exe testframework/main.py compare --run runs/QUELLLAUF --reference data/meine-referenz-schriftart.xlsx --output testframework/ergebnisse/NEUER_SCHRIFTARTVERGLEICH
```

Der Quelllauf steht in `identity.json` des bisherigen Reports. Ein neuer
Ausgabeordner ist erforderlich. `analyze --report …` verwendet dagegen weiterhin
die **eingefrorene** Referenz des alten Reports; später geänderte Excel-Zellen
werden dabei absichtlich nicht erneut eingelesen.

**Manuelle Seiten-GT in JSONL:** `participants[i].schriftart` ergänzen. Schema
`GroundTruthParticipant` erweitert nur die Referenzstruktur. Modell-`Participant`,
Antwortschemas, Prompts und Extraktion bleiben unverändert. Alte JSONL-Daten und
bestehende Python-Participant-Objekte werden ohne Annotation weiter akzeptiert.
`examples/ground_truth.template.jsonl` und das GT-JSON-Schema sind aktualisiert.

**Manueller CSV-Referenzdatensatz/Kalibrierung:** `participants.csv` enthält bei
neuer Erstellung die zusätzliche Spalte `schriftart`; der Loader unterstützt
auch alte Dateien ohne diese Spalte. JSONL-Speicherung und erneutes Laden erhalten
die Annotation. Die bestehende Seitenevaluation gruppiert ihre bisherigen
Seitenmetriken zusätzlich nach Schriftart auf einmalig vollständig berechneten
Seitenpaaren; `split` und `content_type` bleiben eigenständige Dimensionen.

## Gruppenbewertung auf unveränderten Paaren

Der Kurs-/HTML-Vergleich berechnet die geforderten sechs Dimensionen für h, m,
g und Nicht klassifiziert: Exact Recall, Exact F1, Field Coverage,
mittlere Levenshtein-Ähnlichkeit erkannter Felder, strikten Teilnehmer-Recall und
vollständig korrekte Teilnehmer. Es gelten dieselben Formeln und
Normalisierungsregeln wie [bisher](detected-similarity.md).

Das Matching wird **vor** der Gruppierung über die gesamte Schulung ausgeführt.
Jeder Feldvergleich speichert seine bestehenden additiven Zähler, jede
Referenzperson ihre bestehenden Teilnehmerzähler. Die Gruppe summiert diese
Vektoren und verwendet `scores`, `participant_scores` und dieselbe Aggregation.
Keine zweite Feldbewertung und keine Neuzuordnung anhand der Gruppen.
Insbesondere wird Identitätseindeutigkeit nicht innerhalb kleinerer Teilgruppen
neu hergestellt. Fehlende Referenzpersonen behalten ihre GT-Schriftart,
sämtliche fehlenden Felder und ihre Teilnehmernenner.

Bekannt leere oder nicht bewertbare GT, unsichere Paarungen, Namenstausch-
Sensitivitäten und D=0 folgen unverändert den vorhandenen Regeln. Bei fehlendem
Referenznenner, fehlendem Identitätsanker oder D=0 bleibt die jeweilige Kennzahl
**nicht definiert**. Bei vorhandener Referenz und fehlender Extraktion sind
Recall/Coverage dagegen korrekt null. `g` beeinflusst keine Feldrollen.

### Zusätzliche Ausgaben und gruppenspezifischer F1

Ungepaarte Modellausgaben besitzen keine verlässlich zuordenbare GT-Schriftart.
Sie werden weder einer beliebigen h/m/g-Gruppe noch der GT-Gruppe „Nicht
klassifiziert“ zugeschlagen. Ihre vollständigen P-/FP- und Zusatzpersonenbeiträge
bleiben in der **Gesamtbewertung** und werden separat ausgewiesen:

```text
R_global = Σ_t R_t
E_global = Σ_t E_t
P_global = Σ_t P_t + P_ungepaart
```

Eine Halluzination in einem gepaarten ausdrücklich leeren Referenzfeld hat dagegen
eine bekannte GT-Gruppe und belastet deren P/F1. Gruppen-Precision und -F1 sind
damit **bedingt auf die jeweilige GT-Teilmenge**, keine vollständigen Pipeline-
metriken. Sie dürfen nicht zum globalen F1 gemittelt werden. Zusätze verschwinden
global nicht, auch wenn eine Gruppenzahl dadurch höher als der globale F1 ist.
Alle Feldzähler und strengen Teilnehmerzähler werden auf Summenkonsistenz geprüft.

## HTML, Dokumentzahlen und Exporte

Neuer Bereich **H · Schriftart**: Vergleichstabelle aller Verfahren, Filter
Gesamt/Handschrift/Maschinenschrift/Gemischt/Nicht klassifiziert, Teilnehmer-
und Feldzahlen, alle sechs Qualitätsdimensionen und Feldtypaufschlüsselung.
„Gesamt“ zeigt Gesamtzeilen und alle Teilgruppen; die globale Bewertung in A
enthält weiterhin sämtliche Teilnehmer und Zusatzfehler. Der Filter betrifft
H, ändert keine Kennzahlen und rechnet keine Gruppe neu aus. Bereich G bietet
zusätzlich einen GT-Schriftartfilter auf den einzelnen Feld-/Teilnehmerfällen.

Die Dokumentzahl ist als **PDFs im Kursumfang der GT-Gruppe** ausgewiesen und
unabhängig vom Erkennungserfolg. Die Kursreferenz lokalisiert Personen nicht auf
einzelne PDF-Seiten. Deshalb wird keine präzise Personenanwesenheit auf bestimmten
PDFs erfunden. PDFs können mehrere Gruppen enthalten; Dokumentzahlen sind nicht
additiv. Seiten-GT besitzt dagegen explizite Dokument-/Seitenlokalisierung.

Neue Exporte: `scientific/schriftart.csv`, `schriftart_fields.csv` und
`schriftart_unassigned.csv` für alle vorhandenen Matchingansichten; zusammen
mit `scientific/analysis.json`. Referenzsnapshot, Feld-/Teilnehmerexporte und
Auditfälle erhalten `schriftart`; zusätzliche Ausgaben bleiben ohne GT-Annotation.
Verschachtelte Zählervektoren werden im CSV als JSON gespeichert.

## Implementierung und Nachweis

Gemeinsame Annotation/Validierung: `writing_style.py`, `schema.py`,
`excel_reference.py`, `roster_benchmark/references.py`; GT-Export in
`excel_columns.py` und CLI `reference-template`; manuelle Datensätze in
`calibration/dataset.py` und `evaluation.py`. Gruppen-/Mikroaggregation in
`roster_benchmark/metrics.py`; Dashboard, Export und Filter in `scientific.py`,
`schriftart_report.py`, `dashboard_report.py`, `metric_audit_report.py` und
`detail_report.py`. Der ältere strikte Excel-Abgleich erhält die GT-Metadaten,
behält seine eigene historische Matching-/Bewertungsdefinition.

Neuer realer Report: `testframework/ergebnisse/schriftart-20261116/report.html`.
Quelle ist der im IDE geöffnete Vergleich `20261116T105322Z-37e601f2`. Alle
bisherigen Methoden-/Feld-/Coverage-/Exact-/Teilnehmerwerte sind unverändert.
Alle 46 Referenzpersonen/184 Felder bleiben bei allen fünf Verfahren **nicht
klassifiziert**. h/m/g enthalten bis zur manuellen Annotation keine empirische
Datenbasis. Keine neuen Modellaufrufe und keine geratenen Schriftartlabels.

Bearbeitbare Kopie: `data/schriftart-20261116/referenz-schriftart.xlsx` mit
170 eingefrorenen Referenzpersonen über alle vorhandenen Kurse. Historischer
Report und Quelllauf (749 Dateien) sind hashgleich erhalten. Private Prüfnachweise
unter `data/schriftart-20261116/`; Originalreferenzen nicht überschrieben.

`tests/test_schriftart.py` deckt 23 Fälle ab: alle Kategorien/Leerwerte,
Validierungsfehler, unveränderte Modellschemas, CSV/XLSX-Roundtrip/Bearbeitung,
gestreamte XLSX-Leerzellen, Dublettenkonflikte, fehlende Personen, unveränderte
Paarung, kursweite Identitätseindeutigkeit, globale Zusatzstrafen, manuelle CSV-
Datensätze, einmaliges Seitenmatching, eingefrorene Referenzen und HTML-Filter.
Ohne unabhängige Seitenannotation ist weiterhin keine feldgenaue
Handschrifterkennungsqualität oder kausale Methodenüberlegenheit belegt.

Abgeschlossen: **945 lokale Tests (102,85 s)**, **148 gezielte Tests (20,43 s)**
und **48 API-Tests (10,22 s)** bestanden, ohne echte API-Aufrufe. Ruff und
Diff-Check ohne Befund; 3.399 lokale Links, beide Skriptsyntaxen und CSP-Hashes,
Gruppen-/Globalzähler sowie Referenzexport geprüft. Visuelle Browserabnahme bleibt
in dieser Sitzung mangels Browser-/Desktopanbindung offen.
