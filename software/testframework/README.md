# Separates Testframework für PDF-Teilnehmerlisten

Seit 18.11.2026 verwenden neue lokale Starts **Qwen3-VL-8B-Instruct in LLM.int8**
für `vlm` und `ocr_vlm` (gleicher Checkpoint, keine CPU-Auslagerung; Bildencoder
weiterhin BF16). Basis: `configs/benchmark-vlm8b.yaml`; die Vierer-/Fünferstarter
wählen `benchmark-four-vlm8b.yaml` beziehungsweise `benchmark-five-vlm8b.yaml`.
Textmodell, Bildauflösung, Prompts und Metriken bleiben unverändert. Die bisherigen
4B-Profile bleiben für ausdrückliche Vergleichsläufe erhalten. Einzelheiten zu
Speicher, Download und wissenschaftlicher Vergleichbarkeit:
[größeres VLM](../docs/gpu-inference.md#größeres-vlm-im-testframework-18112026).

Beispiel: `start_testframework_5.cmd --documents 3` startet den nächsten Test mit
dem größeren VLM. Für einen 4B-Vergleich explizit
`start_testframework_5.cmd --extraction-config configs/benchmark-five.yaml --documents 3`
angeben. Alte HTML-Dateien bleiben Ergebnisse ihrer damaligen Modelle; zur
8B-Bewertung ist ein neuer Extraktionslauf erforderlich.

Neue Berichte verlinken [Handschrift vs. Maschinenschrift](../docs/schriftart.md#analyseseite-handschrift-vs-maschinenschrift):
Feldverteilung, Qualität und Fehleranteile nach GT-Teilnehmer-Schriftart, mit
Diagrammen und Filtern für Verfahren, Feld, Dokument und h/m/g/unklassifiziert.
Unabhängig geprüfter Dokumentinhalt bleibt eine separate Bewertungsgrundlage.

## Anzahl der Test-PDFs beim CMD-Start

Die Starter `start_testframework.cmd`, `start_testframework_4.cmd` und
`start_testframework_5.cmd` fragen vor einem neuen Lauf:

```text
Wie viele PDFs testen? [1–10, Enter = alle]:
```

Die Obergrenze richtet sich nach deinem Eingabeordner. **`3` eingeben** wählt
zufällig drei vollständige PDFs; **Enter** verwendet alle. Die Originaldateien
werden nicht verschoben oder gelöscht. Alle Verfahren erhalten dieselbe Auswahl
mit sämtlichen Seiten. Identische Dateikopien zählen als ein PDF-Inhalt.

Ohne Rückfrage starten oder eine Auswahl wiederholen:

```bat
start_testframework_5.cmd --documents 3
start_testframework_5.cmd --documents 3 --sample-seed 42
start_testframework_5.cmd --all-documents
```

Ohne angegebenen Seed wird für jeden neuen begrenzten Lauf ein Seed erzeugt.
Mit gleichem PDF-Bestand und gleichem Seed erhältst du dieselbe Auswahl.
Anzahl, Seed, ausgewählte PDFs und Prüfsummen stehen im Laufmanifest, im
Vergleichsordner unter `document_sample.json` und im HTML-Bericht.
`--pruefen` stellt keine Auswahlfrage. `--resume` und `--manifest` verwenden
ihre gespeicherte Auswahl; eine neue Anzahl oder ein neuer Seed ist dabei
ausgeschlossen. Änderungen am eingefrorenen Eingabepool werden beim Resume
weiterhin abgewiesen.

Die Python-CLI fragt nur mit `--prompt-documents` interaktiv; vorhandene
automatisierte Aufrufe ohne Auswahloptionen verwenden weiterhin alle PDFs.
Das schnelle Zufallssample ersetzt keinen geprüften Studienplan. Bestehen für
eine Schulung mehrere PDFs, bleibt auch bei einer PDF-Teilmenge die vollständige
Kursreferenz dieser Schulung im Bewertungsnenner. Die Metrikregeln bleiben gleich.

[Wissenschaftliche Zusatzdiagnostik](../docs/scientific-validity.md): optionale
ANLS-Feldähnlichkeit (`analyze --anls`), Zeilenkonsistenz, unabhängig annotierte
Seitenstrata (`--page-annotations`) und technische Stabilität in `validity.html`.
Bestehende Metriken, Extraktionen und historische Ergebnisse bleiben erhalten.

Hier legst du Test-PDFs und eine gemeinsame Excel-/CSV-Referenz ab. Das Framework
verwendet die vorhandenen lokalen Extraktionsverfahren und vergleicht anschließend
die erkannten Teilnehmer mit den Referenzzeilen derselben Schulung. Die Referenz
wird **keinem Modell und keinem OCR-Schritt übergeben**. Es gibt keine API-Aufrufe.

Für denselben Testablauf mit API-Modellen auf dem Firmen-PC gibt es einen
separaten [API-Einstieg](../api_firmen_pc/testframework/README.md) samt
`start_api_testframework.cmd`, eigenen Eingabeordnern und identischer Bewertung.
Dieser lokale Einstieg bleibt ausschließlich offline.

Die Seite **„Ursachen fehlender Felder“** trennt gespeicherte Pipelinebelege von
einer unabhängigen Originalprüfung. Sie bietet filterbare Feldvergleiche,
manuelle Dokumentannotation mit JSON-Import/-Export und eine zusätzliche
Auswertung ausschließlich belegter lesbarer Referenzfelder. Ungeprüfte Fälle
bleiben in den bisherigen Nennern. Details und `analyze --document-annotations`
stehen in [Dokumentverfügbarkeit](../docs/document-availability.md).

Für die wissenschaftliche Kandidatenauswahl ergänzt `participant-bench selection`
das bestehende Framework um eine Evidenzmatrix, einen eingefrorenen gruppierten
Stichprobenplan und einen Pilotvergleich. Originale Namensrollen auf festen
Referenzpaaren, neue Zuordnung ohne Swap und referenzgestützte Swap-Metriken werden
getrennt ausgewiesen. Finale Testdaten sind im Auswahlpfad gesperrt.
Anleitung: [Verfahrensauswahl](../docs/method-selection.md). Das vorhandene
Hauptprofil und historische Ergebnisse bleiben erhalten.

Neue Vergleiche zeigen im selben Hauptbericht acht Analysebereiche mit sortierbarer
Vergleichstabelle, striktem Teilnehmer-Recall, vollständigen beziehungsweise partiellen
Referenzen, Feldheatmap, filterbaren Fehlerursachen, Dokumenttypen, Effizienz/Kosten
und Cluster-Bootstrap. Bereich G enthält filterbare Feld-/Teilnehmerbewertungen
mit Soll-/Ist-Werten, Gründen, PDF-Links und prüfbaren R/P/E-Beiträgen.
Die Tabellen zeigen einen Originalwert und die prozentuale Levenshtein-
Ähnlichkeit; Normalwerte bleiben in Exporten. Fünf eindeutige
[Feldstatus](../docs/field-assessment.md) trennen korrekte, abweichende, fehlende,
unklar zugeordnete und nicht bewertbare Werte ohne zusätzliche Exact-Treffer.
Die sortierbare Gesamtübersicht zeigt jetzt die
[Ø Levenshtein-Ähnlichkeit erkannter Felder](../docs/detected-similarity.md)
mit Σs/D und D/R neben Coverage und Exact-Metriken. Fehlende Felder senken die
Ähnlichkeit nicht; ohne vergleichbare Werte bleibt sie nicht definiert.
Der frühere Levenshtein-Feld-F1 wird in der aktuellen Anzeige ersetzt.
Bereich H gruppiert nach der optionalen GT-Spalte `schriftart` (h/m/g), mit
Schriftartfilter, sechs Qualitätsdimensionen, Feldtypen und expliziter Gruppe
„Nicht klassifiziert“. Fehlende Annotation wird nicht als Maschinenschrift
interpretiert. `reference-template` erzeugt eine bearbeitbare GT-Kopie mit
Excel-Auswahlliste. [Annotation, Gruppen-F1 und Beispiele](../docs/schriftart.md).
Ausgabezeilen, exakte Identitäten und vollständig korrekte Teilnehmer werden
getrennt gezählt. [Audit des Dreidokumentreports](../docs/evaluation-audit-20261116.md)
erklärt Abdeckung, Namensrollen, Nullbaseline, VLM-Abbrüche und Cachezeiten.
Die vorhandenen Matching- und Einzelfallansichten bleiben
verlinkt; `standard_report.html` erhält die bisherige Standarddarstellung.
Ohne geprüfte Metadaten bleiben
Merkmale unbekannt und Unsicherheitsintervalle offen. Bestehende Berichte lassen sich
mit `metadata-template` und `analyze` ohne neue Inferenz in einen neuen Ergebnisordner
auswerten: [Anleitung und methodische Grenzen](../docs/scientific-evaluation.md).

Die einmalig literaturbasiert überarbeiteten Extraktionsprompts werden zentral
in `participant_bench/extraction_prompts.py` zusammengesetzt. Fachliche
Eingabe-/Schemapfade bleiben erhalten; VLM und OCR-VLM teilen denselben
Systemprompt. Vorlagen, tatsächliche Textnachrichten und Hashes werden pro Lauf
gesichert. Alte Läufe bleiben historische Ergebnisse ihrer alten Prompts.
[Promptgestaltung und Validierung](../docs/prompt-design.md) dokumentiert die
begründete feste Promptfamilie; es handelt sich um keine Promptoptimierungsstudie.

## Schnellstart

Folgetabellen ohne wiederholte Überschriften können ihre Feldspalten aus derselben
PDF übernehmen, wenn die gemessene Spaltengeometrie weiterhin passt. Aktuelle
eindeutige Überschriften haben Vorrang; Teilnehmerwerte werden nie seitenübergreifend
kopiert. Haupt-/Fehlerbericht dokumentieren Feldspalten, Quellseite und
Kompatibilitätsprüfung, auch für VLM/Hybrid.
[Verhalten, unterstützte Pfade und Grenzen](../docs/document-columns.md).

1. PDFs nach `eingabe_pdfs/` kopieren. Unterordner sind erlaubt.
2. Genau eine `.xlsx` oder `.csv` nach `referenz/` legen. Der Dateiname ist frei wählbar.
3. Aus `software/` starten:

```powershell
.\start_testframework.cmd
```

Die bereits eingerichtete Hauptumgebung wird weiterverwendet. Es ist kein neues
Python-Projekt nötig. Die 8B-Gewichte müssen einmalig wie unter
[GPU-Ausführung](../docs/gpu-inference.md#größeres-vlm-im-testframework-18112026)
eingerichtet werden. Neue Rechner benötigen außerdem die
[sechs lokalen Verfahren](../docs/local-methods.md).

Die Schulungs-ID steht im PDF-Dateinamen: **`123456.pdf` gehört zu `Class ID = 123456`**.
Auch die bisherigen Rohdatei-Namensformen und `123456__2.pdf` werden unterstützt.
Mehrere Seiten und mehrere PDFs derselben Schulung werden gemeinsam bewertet.
Die CSV darf beliebig viele Schulungen enthalten. Schulungen ohne Eingabe-PDF
gehen nicht in den Nenner ein; PDFs ohne passende Referenz werden separat ausgewiesen.
**Die Klassen-ID ist eine feste Grenze vor jeder Namenszuordnung.** Ein Name oder
eine User ID aus einer anderen Klasse darf auch bei exakter Übereinstimmung nicht
als Kandidat verwendet werden. Im Namensreport steht pro Zeile die verwendete
Klassen-ID und die Anzahl der zulässigen Referenzeinträge. Diese Regel gilt für
Best-Fit und den konservativen Modus sowie für lokale und API-Ergebnisse.

Ausdrücklich als Kursleiter, Trainer oder Dozent erkannte Personen werden bereits
bei der Extraktion ausgeschlossen. Sie gelangen nicht in den Teilnehmervergleich.
Der Vergleichsreport zeigt die Anzahl unter „Ausgeschlossene Kursleiter“;
das separate Ausschlussprotokoll liegt im verlinkten Extraktionslauf unter
`excluded_instructors.csv`. Unklare Rollen bleiben zur Prüfung erhalten.
Die Excel-/CSV-Referenz muss tatsächliche Teilnehmer enthalten; sie wird nicht
automatisch anhand von Modellvorhersagen verändert.

Die Extraktion entscheidet Vor-/Nachnamensrollen pro Dokument anhand von
Überschriften, Tabellenzellen und Namensreihenfolge. Diese Modellentscheidung
wird für Folgeseiten wiederverwendet und im verlinkten Extraktionsreport sowie
`document_name_orders.csv` dokumentiert. Die Extraktion entscheidet ohne Referenz.
Im aktiven Vergleich werden anschließend beide Orientierungen vollständiger
Namensgruppen geprüft (`matching.compare_name_orientations: true`). Die höhere
Namensähnlichkeit gewinnt, bei Gleichstand bleiben die ursprünglichen Rollen.
Dies ist eine referenzgestützte Bewertungszuordnung, kein Nachweis korrekt
extrahierter Namensrollen. Tausche und beide Kandidatenähnlichkeiten werden
protokolliert; Originalwerte und Quellenreihenfolge bleiben erhalten.

Vor dem Modelllauf nur Ordner, Spalten und gemeinsame Schulungs-IDs prüfen:

```powershell
.\start_testframework.cmd --pruefen
```

Das startet keine Modelle. Die Eingabeordner und Ergebnisse sind von Git ausgeschlossen.

Die automatische Ausrichtung nutzt bei unsicherem OSD jetzt einen abgesicherten
OCR-Vergleich aller vier Drehlagen. Das ist beim normalen Start bereits aktiv;
auf den vorhandenen zwanzig Entwicklungsseiten wurden alle zwölf seitlichen
Seiten richtig gedreht. [Ablauf, Nachweise und Grenzen](../docs/automatic-orientation.md).
Unentscheidbare Seiten bleiben prüfpflichtig; ein Winkel von 0° allein bestätigt
keine richtige Ausrichtung. Optional lässt sich weiterhin ein bereits manuell
geprüftes Manifest übergeben:

```powershell
.\start_testframework_5.cmd --manifest data/DEINE_PRUEFUNG/curated-manifest.json
```

Dabei bleiben Eingabe-/Bildhash- und Konfigurationsprüfungen aktiv; der Befehl
startet anschließend einen neuen Modelllauf. Die aktuelle
[Ursachenprüfung auf zehn PDFs](../docs/field-loss-20261111.md) dokumentiert ein
konkret geprüftes Manifest und die erweiterten Feld-/Seitenketten im Fehlerbericht.

## Referenzspalten

Der Standardvergleich verwendet `matching.mode: best_fit`: Innerhalb derselben
Schulung werden zuerst möglichst viele lesbare Ausgaben mit verschiedenen
Referenzzeilen gepaart. Anschließend wird die Summe der Levenshtein-Ähnlichkeiten
über alle bewertbaren Felder maximiert, einschließlich lesbarer User IDs.
Die Reihenfolge der Daten spielt dabei keine Rolle. Es handelt sich um ein
globales Maximum, nicht um eine nacheinander ausgeführte Suche nach dem jeweils
nächsten freien Eintrag. Die Optimierung maximiert die Ähnlichkeitssumme,
nicht zwingend den F1-Quotienten bei paarabhängigen Maskierungsausschlüssen.

Schwache und nahezu gleichwertige Paarungen bleiben im Best-Fit-Vergleich erhalten
und werden als prüfpflichtig markiert. Die bisherigen Grenzen von 0,80/0,70
dienen dann als Prüfhinweise. Diese Best-Fit-Paare bestätigen keine Identitäten.
Im Referenzabgleich dürfen ausschließlich vollständige Namensgruppen gemäß der
obigen Option für die Bewertung vertauscht werden. Keine Schreibweise und keine
Originalextraktion wird durch Referenzwerte korrigiert. Bei weniger
Ausgaben als Referenzen bleiben Personen fehlend; bei mehr Ausgaben bleiben
zusätzliche Datensätze übrig. Völlig unlesbare Ausgaben erhalten kein erfundenes Paar.

Der Bericht zeigt zusätzlich den konservativen Score auf denselben unveränderten
Modellausgaben. Höhere Best-Fit-Werte können allein durch die Zuordnungsregel
entstehen. Alte gespeicherte Konfigurationen ohne `mode` behalten ihren bisherigen
konservativen Modus. Für einen einzelnen Lauf bzw. einen neuen Vergleich wählen:

```powershell
.\.venv\Scripts\python.exe testframework/main.py run --matching-mode best_fit
.\.venv\Scripts\python.exe testframework/main.py compare --run runs/DEINE_RUN_ID --matching-mode conservative
```

Standardmäßig werden diese fünf Spalten verwendet; weitere SAP-/Excel-Spalten
werden nicht in die Bewertungsdaten übernommen:

| Spalte | Verwendung |
| --- | --- |
| `Class ID` | Schulungs-ID; gruppiert Referenzzeilen und PDF-Dateien |
| `User ID` | Benutzer-/Personalnummer; optional und möglicherweise maskiert |
| `First Name` | Vorname |
| `Last Name` | Nachname |
| `Organization` | Kurzzeichen/Abteilung |

Eine synthetische Vorlage liegt unter [beispiele/referenz.csv](beispiele/referenz.csv).
Die User-ID-Spalte darf vollständig fehlen. Sichtbar leere oder maskierte IDs
verhindern die Zuordnung über Name und Kurzzeichen nicht.

Die tatsächliche Schreibweise der Überschriften wird direkt aus der Referenz
übernommen. Der Ergebnisexport `participants.xlsx` verwendet auch deren
Spaltenreihenfolge: ein Blatt je Verfahren, `Referenz` für die verglichenen
Schulungen und `Quellen` für PDF-Seiten und ursprüngliche Referenzzeilen.
Eine fehlende User-ID-Spalte wird nicht ergänzt; einzelne leere IDs bleiben leer.
Die Referenzdatei wird nur gelesen. Technische CSV-/JSON-Feldkennungen bleiben
erhalten; `field_label` enthält zusätzlich die ursprüngliche Spaltenbezeichnung.

IDs als **Text** speichern, damit führende Nullen erhalten bleiben. XLSX-Zahlen
mit einem reinen Nullformat wie `000000` werden entsprechend gelesen. Numerische
Excel-IDs mit bereits verlorenen Nullen können nicht automatisch rekonstruiert werden.
Formeln in den verwendeten Referenzzellen werden abgewiesen; als feste Werte exportieren.
CSV wird als Text gelesen und unterstützt Komma, Semikolon oder Tabulator sowie
UTF-8 mit/ohne BOM. Bei älteren Excel-Exporten `reference.encoding: cp1252` setzen.

Spaltennamen, Excel-Blatt, Kopfzeile, Kodierung, Trennzeichen und Zuordnungsschwellen
stehen zentral in [config.yaml](config.yaml). Beispiel für andere Überschriften:

```yaml
reference:
  columns:
    class_id: Schulungsnummer
    user_id: Benutzer
    first_name: Vorname
    last_name: Nachname
    short_code: Kurzzeichen
```

## Startvarianten

Alle folgenden Befehle aus `software/` ausführen. Ohne Optionen verwendet `run`
die sechs Verfahren aus `configs/benchmark-vlm8b.yaml`:

```powershell
.\.venv\Scripts\python.exe testframework/main.py run
```

Einzelne Verfahren testen oder einen anderen PDF-/Referenzpfad wählen:

```powershell
.\.venv\Scripts\python.exe testframework/main.py run --method vlm
.\.venv\Scripts\python.exe testframework/main.py run --method ocr_llm --method paddle_llm
.\.venv\Scripts\python.exe testframework/main.py run --input "data/meine_test_pdfs" --reference "data/referenz.xlsx"
```

Die PDF-Dateien werden pro Verfahren nacheinander verarbeitet; die Modelle bleiben
dabei für die jeweiligen Seiten geladen. Dadurch wird nicht für jede einzelne PDF
die gesamte Modellfolge neu geladen. Fortschritt und technische Zwischenergebnisse
liefert der bestehende Extraktionsrunner. Originale bleiben unverändert.

Wenn `vlm` und `ocr_vlm` enthalten sind, schreibt der Vergleich zusätzlich
`hybrid_analysis.html`, `hybrid_fields.csv` und `hybrid_analysis.json`.
Sie zeigen pro derselben Referenzperson und demselben Feld Korrekturen und
Verschlechterungen, Exact Match, Zeichendistanzen und gepaarte CER. Die
eingefrorenen VLM-Einstellungen und Seitenbild-Hashes werden kontrolliert.
Die üblichen Einzelmetriken bestrafen zusätzliche Ausgaben weiterhin separat.
Die neuen Textgewichte Qwen3-4B-Instruct-2507 müssen vorab eingerichtet sein;
fehlende Modelle werden als `unavailable` ausgewiesen.

Die Referenz enthält ausschließlich Unterzeichner, aber keine einzelnen Signaturlabels. Daher deaktiviert dieses Framework
standardmäßig die zusätzlichen VLM-Signaturdetailaufrufe (`signature_detail_checks: false`).

Die Evaluation kann ungepaarte Zusatzpersonen bei einem gespeicherten,
zeilenbezogenen Leerfeldbefund automatisch ausschließen. Ähnliche Referenznamen,
Signaturunsicherheit und Widersprüche verhindern diesen Ausschluss; alle
Referenzpersonen bleiben im Nenner. In den Standardprofilen ist
`matching.exclude_probably_unsigned_extras: true` aktiv. Historische Profile ohne
diesen Schlüssel behalten ihre bisherigen Beiträge. Details, Beleggrenzen,
Zählerdefinitionen und die manuelle Prüfliste im HTML-Report sind in
[Signatur und Referenzbewertung](../docs/signatur-referenzbewertung.md) dokumentiert.

Die Unterschriftenspalte wird als vorhanden vorausgesetzt. Neue strukturierte
Läufe prüfen ihre Zellen bildbasiert und übernehmen die aus Überschriften
bestimmte Position nur auf kompatible Folgeseiten derselben PDF. Fehlende
Zell-/Zeilenpositionen bleiben unklar; Signaturen sind keine Textfelder und
gehen nicht als Transkriptionen in die Textmetriken ein. Zusätzliche VLM-
Prüfungen benötigen lokalisierte Zellen, keine separate Spaltenexistenzprüfung.
Die bisherigen Startdateien und Standardprofile außerhalb dieses Frameworks behalten
ihre Signaturprüfung. Mit `true` bleibt die im gewählten Extraktionsprofil konfigurierte
Prüfung aktiv; Signaturqualität wird gegen diese fünf Referenzspalten trotzdem nicht bewertet.

## Vorhandene Ergebnisse vergleichen

Für den reinen Vergleich ist kein GPU-/Modelllauf nötig. Das funktioniert auch
mit vorhandenen lokalen oder kopierten API-Ergebnissen im gemeinsamen Run-Format:

```powershell
.\.venv\Scripts\python.exe testframework/main.py compare --run "runs/DEINE_RUN_ID" --reference "testframework/referenz/referenz.xlsx"
```

Optional `--method vlm` bzw. mehrfach `--method ...` angeben. Historische
`ocr_rules`-Ergebnisse sind ebenfalls lesbar. Der Quelllauf wird nicht verändert.
Jeder Vergleich erzeugt einen neuen Ergebnisordner. So kannst du neue Referenzstände
prüfen, ohne OCR oder Modelle erneut aufzurufen.

Ein abgebrochener Extraktionslauf kann mit denselben Eingaben, Methoden und
unveränderter Konfiguration fortgesetzt werden:

```powershell
.\.venv\Scripts\python.exe testframework/main.py run --resume "runs/DEINE_ABGEBROCHENE_RUN_ID"
```

Der bestehende Runner prüft dazu seine vollständige Laufidentität. Bei Änderungen
an Code, Modellen oder Eingaben einen neuen Lauf starten. Ist die Extraktion bereits
abgeschlossen, stattdessen `compare` verwenden. Referenzdateien sinnvoll versionieren.

## Reihenfolgeunabhängige Zuordnung

Die Zeilenposition in Excel/CSV und die Reihenfolge der PDF-Seiten sind keine
Identitätsmerkmale. Das Framework vergleicht innerhalb jeder Schulungs-ID alle
erkannten Teilnehmer mit allen Referenzteilnehmern und bildet eine globale
Eins-zu-eins-Zuordnung. Jede Vorhersage und jede Referenzzeile können höchstens
einmal Punkte liefern. Die Optimierung verwendet
[SciPys optimale Zuordnung](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html).

Im weiterhin verfügbaren **konservativen Modus** hat eine eindeutige exakt passende
lesbare User ID Vorrang. Andernfalls zählen
mindestens zwei beobachtete Angaben aus Vorname, Nachname und Kurzzeichen.
Die Identitätsähnlichkeit gewichtet Namen mit 1 und das Kurzzeichen mit 0,5;
fehlende Angaben werden für die Zuordnung ausgelassen, bleiben bei der späteren
Feldbewertung aber Fehler. Näherungsweise Personalnummern allein identifizieren
keine Person. Wenn eine ID eindeutig auf eine andere Person als die exakte
Namens-/Kurzzeichenkombination zeigt, entsteht ein Prüffall.

Eine lokale Zeile wird nicht einfach gierig dem erstbesten Kandidaten zugeordnet:
Die globale Optimierung kann andere Zeilen zur Auflösung heranziehen. Gibt es
trotzdem eine nahezu gleichwertige globale Alternative, wird die Zuordnung als
mehrdeutig markiert. Im konservativen Modus erhält sie keine automatischen Punkte;
im Standardmodus Best-Fit bleibt die Paarung mit Prüfhinweis erhalten.
Best-Fit-Prüfgründe stehen unter `matching_review_reasons` (`low_similarity`,
`ambiguous`, `identity_conflict`, `duplicate_prediction`) im Auditexport. Im
konservativen Modus bleiben ungepaarte Fälle unter `ambiguous`/`identity_conflict`.
Die Schwellen in `matching` sind nachvollziehbare Defaults, keine validierten
Wahrscheinlichkeiten. Nur auf getrennten Entwicklungsdaten anpassen, nicht anhand
des abschließenden Testdatensatzes optimieren.

Nach der beschriebenen Normalisierung identische Modellkopien werden im
konservativen Modus einmal zugeordnet und zusätzlich als Duplikate gezählt.
Best-Fit erhält die maximal mögliche Eins-zu-eins-Paarung und markiert doppelte
Ausgaben sowie gleichwertige Alternativen; keine Referenz wird mehrfach verwendet.
Identische Referenzkopien sind standardmäßig ein Datenfehler. Wenn sie
nachweislich Exportduplikate sind, erlaubt `reference.merge_identical_duplicates: true`
das explizite Zusammenführen identischer Fünf-Spalten-Zeilen; Anzahl und ursprüngliche
Zeilennummern bleiben protokolliert. Unterschiedliche Personen mit ähnlichen Namen
werden nicht zusammengeführt. Derselbe PDF-Hash unter verschiedenen Schulungsnamen
wird als widersprüchlich markiert und nicht still mehreren Kursen gutgeschrieben.

## Bedeutung der Zahlen

Die Feldähnlichkeit ist:

```text
Ähnlichkeit = 1 - Levenshtein-Distanz / max(Länge der Referenz, Länge der Vorhersage)
```

Einfügungen, Löschungen und Ersetzungen kosten je einen Edit. `Anna` gegen `Anma`
hat Distanz 1 bei Länge 4 und erhält **0,75 Punkte**. Ein vollständig richtiges
Feld erhält 1, ein fehlendes Feld 0 Punkte. Namen und Kurzzeichen werden standardmäßig
mit NFC, vereinheitlichten Leerzeichen und ohne Groß-/Kleinschreibung verglichen.
`ß` wird dabei nicht still zu `ss` korrigiert. IDs bleiben in den Rohdaten und
Exporten Strings mit ihrer Originalschreibweise. Für den Vergleich werden
führende Nullen rein numerischer **User IDs** entfernt: `0047285` und `47285`
haben Distanz 0 und zählen als vollständiger Treffer. Dies gilt sowohl für die
Personenzuordnung als auch für die Feldbewertung, in beiden Richtungen.
Namen, Kurzzeichen und Class IDs verwenden diese ID-Normalisierung nicht.
Maskierte oder fehlende IDs bleiben wie bisher ausgeschlossen bzw. unbekannt.

Die Einstellung `matching.ignore_leading_user_id_zeros: true` ist in den Profilen
für den lokalen Rechner und den Firmen-PC aktiviert. Historische Reports ohne
diese Einstellung behalten beim erneuten Öffnen ihrer Detailansicht die alte
Berechnung. Für eine neue Bewertung gespeicherter Extraktionen genügt `compare`;
eine erneute Modellinferenz ist nicht nötig.
Intern werden Originalschreibweise und normalisierte Exaktheit separat erhalten:
Ein Treffer nach Entfernung der Nullen kann bei `raw_exact` weiterhin falsch und
bei `exact` richtig sein. Alle drei HTML-Berichte erklären die gespeicherte Regel.

Primär zeigt der Bericht den **exakten Feld-Recall**: exakt erkannte nichtleere
Informationswerte geteilt durch alle bewertbaren erwarteten Werte. Ergänzend
stehen Feldabdeckung, exakter Feld-F1 und **Levenshtein-Feld-F1**:

```text
100 × 2 × Summe der Feldähnlichkeiten
──────────────────────────────────────────────────────────────
Anzahl bewertbarer Referenzfelder + Anzahl vorhergesagter bewertbarer Felder
```

Dadurch werden nicht nur fehlende Werte, sondern auch zusätzliche oder doppelte
Extraktionen berücksichtigt. Daneben steht derselbe **exakte Feld-F1**, der nur
volle Treffer gutschreibt. Zusätzlich siehst du die konkreten Zähler, etwa
`87 / 100 Referenzfelder exakt`, sowie Ergebnisse pro Feld und Schulung.
Alle bewertbaren Felder haben beim Endscore gleiches Gewicht; Kurse mit mehr
bewertbaren Feldern tragen entsprechend stärker zum Gesamtwert bei (Mikroaggregation).

Beispiel: Vier ausgegebene und vier lesbare Referenzfelder, davon drei exakt und
ein Vorname mit einem Fehler wie oben: exakter Feld-F1 **75 %**, Levenshtein-Feld-F1
**93,75 %**. Die Referenztrefferquote bestraft zusätzliche Zeilen nicht;
zusätzliche Ausgaben und F1 werden deshalb daneben ausgewiesen.

Leere/maskierte **Referenz-IDs** sind nicht bewertbar und gehen nicht in den ID-Nenner
ein. Maskierte/Platzhalter-Modellwerte bei lesbarer Referenz bleiben Fehler mit null
Teilpunkten; sie dürfen den Referenznenner nicht verkleinern. Nichtleere Platzhalter
zählen auch im Vorhersagenenner. **Maskierungen möglichst bereits in der manuell
geprüften Referenz markieren**: Ein Modell-`null` allein beweist keine Schwärzung.
Ausschlüsse, falsche und fehlende Felder sowie Feldabdeckung werden getrennt
angezeigt. Für alle strukturierten Verfahren wird derselbe Referenznenner geprüft.

Unannotierte leere Referenzzellen gelten als unbekannt. Nachweislich leere Zellen
können optional über `first_name__state`, `last_name__state`, `user_id__state`,
`short_code__state` oder `<Originalspaltenname> – Status` markiert werden.
Erlaubt: `read`, `empty`, `unknown`, `masked`, `illegible`, `uncertain`.
`empty` verlangt einen leeren Wert. Korrekte Leerzellen geben keine positiven
Informationspunkte; erfundene Werte erhöhen den Vorhersagenenner. Die vorhandene
Referenz wird nicht automatisch annotiert oder verändert.

Mathematische Prüfung, Docling-Befunde und Metrikempfehlung:
[Evaluationsaudit](../docs/evaluation-audit.md). Technischer Seitenerfolg,
End-to-End-Auswertung und bedingte Auswertung vollständig erfolgreicher Kurse
werden getrennt gespeichert. Eine Kursliste erlaubt keine bedingte Bewertung
einzelner Seiten ohne manuell geprüfte Seitentranskripte.

Ausgegebene unsichere Textwerte werden standardmäßig inhaltlich bewertet, bleiben
aber als prüfpflichtig markiert. Mit `matching.score_uncertain_values: false` zählen
sie als unbekannt. Ein leerer oder maskierter Referenzwert liefert keine kostenlosen
Punkte. Ganz unbekannte Referenzfelder werden ausgeschlossen, nicht erfunden.

`ocr_raw` gibt nur Rohtext aus und erhält gegen eine Teilnehmerdatei keinen Feldscore
(`nicht anwendbar`, kein künstlicher Nullscore). Für CER/WER benötigst du separat
geprüfte Seitentranskripte und den vorhandenen Befehl `evaluate-ocr`.

Der Score misst **Übereinstimmung mit deiner Referenz nach der Zuordnung**. Die
Zuordnung selbst verwendet Referenzwerte und ist keine unabhängige Identitätsprüfung.
Eine 93-%-Übereinstimmung ist keine 93-%-Wahrscheinlichkeit für korrekte Teilnehmer.
Eine Buchungs-/Abschlussliste kann andere Personen enthalten als die tatsächliche
PDF-Liste; verwende für aussagekräftige Qualität eine manuell geprüfte Referenz.

## Ergebnisse und Nachvollziehbarkeit

`zuordnungen.html` ist der eigene Namensreport: **erkannter Vor-/Nachname →
Vor-/Nachname in Excel/CSV**. Jede gespeicherte Paarung zeigt Quelle, Referenzzeile,
Entscheidungsgrund, Ähnlichkeiten, lokalen Kandidatenrang und den Abstand zur
globalen Alternativzuordnung. Aufklappbare Tabellen zeigen sämtliche Kandidaten,
deren tatsächliche Vergabe an andere Ausgaben sowie die Feldwerte und Edit-Distanzen.
Nicht zugeordnete Namen und Prüffälle bleiben sichtbar. Namenssuche, Modell- und
Statusfilter funktionieren lokal im Browser. Ein Best-Fit-Paar ist keine bestätigte
Identität. Die global beste Verteilung kann einen lokal weniger ähnlichen Namen
wählen, damit jede Referenz höchstens einmal verwendet wird.

Der Namensreport entsteht automatisch bei jedem neuen Vergleich. Für bestehende
Ergebnisse lässt er sich ohne Modelllauf ergänzen:

```powershell
.\.venv\Scripts\python.exe testframework/main.py assignments --report testframework/ergebnisse/DEINE_VERGLEICHS_ID
```

Jeder neue Vergleich enthält zusätzlich `details.html`. Dort lässt sich der
Gesamtwert bis zum einzelnen Feld zurückverfolgen: Referenzzeile, PDF-Datei,
Seite, Ausgabeindex, Originalwerte und eine Bewertung nach Normalisierung, Feldstatus, Levenshtein-
Distanz, maximale Zeichenlänge, Teilpunkte und Beiträge zu Referenz-/Ausgabenenner.
Die Summen werden gegen die gespeicherten Kennzahlen geprüft. Unterseiten pro
Verfahren und Schulung bieten Suche und Filter sowie sämtliche Referenzkandidaten
mit Zuordnungsschwellen und Ablehnungsgründen. Hinweise auf vertauschte Namen
dienen ausschließlich der Diagnose und verändern keine Werte oder Scores.

Zusätzlich verlinkt `extraction_errors.html` die **Extraktionsfehleranalyse**:
Referenz-/Original-/Bewertungswerte, vollständige OCR-Belege und Tabellenzellen,
Ablehnungsstufen und lokale Quellbereiche. Filter stehen für Verfahren,
PDF-Seite, Feldtyp, Fehlerkategorie, Beleglage und Bewertung zur Verfügung.
Nachgewiesene Ursachen, Vermutungen und unbekannte Ursachen bleiben getrennt.
Nicht gepaarte Kursreferenzen haben ohne Referenzkoordinaten ausdrücklich
keine behauptete PDF-Seite. Die Ansicht verändert weder Extraktion noch Scores.
Hintergrund, Grenzen und kontrollierter Vergleich:
[Extraktionsqualität und Fehleranalyse](../docs/extraction-error-analysis.md).

Bei bestehenden Berichten ohne erneute Modellaufrufe ergänzen:

```powershell
.\.venv\Scripts\python.exe testframework/main.py details --report testframework/ergebnisse/DEINE_VERGLEICHS_ID
```

Der Befehl verwendet den eingefrorenen Referenz-Snapshot und die gespeicherten
Vergleichsdateien, nicht die aktuelle Excel-Datei. Bei verschobenem Extraktionslauf
`--source-run runs/DEINE_RUN_ID` ergänzen; die Prüfsummen müssen passen. Fehlt der
Quelllauf, bleiben die gespeicherten Soll-/Ist-Werte und Berechnungen sichtbar.
Es werden keine Modell- oder Messwerte überschrieben. Der Übersichtsbericht
verlinkt die Detailseite; die Kennzahlen bleiben bei der Aktualisierung unverändert.

Der Extraktionslauf bleibt unter `software/runs/<RUN_ID>/`. Der neue Vergleich liegt unter:

```text
software/testframework/ergebnisse/<VERGLEICHS_ID>/
├── report.html                 # Modellvergleich, Teilpunkte, exakte Treffer, Kurse
├── zuordnungen.html            # Erkannter Name → Referenzname, Entscheidung und Alternativen
├── details.html                # Vollständige Erklärung der gespeicherten Berechnung
├── extraction_errors.html      # Filterbare Extraktionsfehleranalyse mit OCR-Belegen
├── error_analysis/             # Feldursachen, Prüfzähler und lokale Bildausschnitte
├── details/                    # Einzelvergleiche je Modell/Kurs und Summen-/Herkunftskontrolle
├── participants.xlsx           # Original-Spaltennamen: Modelle, Referenz und Quellen
├── summary.csv                 # Gesamtzahlen pro Modell
├── field_scores.csv            # Namen, ID und Kurzzeichen einzeln
├── courses.csv                 # Werte pro Schulung
├── participants.csv            # Paarung, fehlend, zusätzlich, Duplikate, Prüffälle
├── fields.csv                  # Referenz/Ergebnis, Distanz, Ähnlichkeit, Feldzustand
├── matching_candidates.csv     # zugelassene Kandidaten mit Ähnlichkeit und Quellen
├── documents.csv               # PDF-Dateinamen, interne Dokument-ID, Schulungs-ID
├── unassessed_pages.csv        # Seiten ohne bewertbare Schulungszuordnung
├── metrics.json                # vollständige Zähler, Nenner und Definitionen
├── reference_snapshot.json     # verwendete Referenzspalten und ursprüngliche Zeilen
├── config.json                 # tatsächlich verwendete Bewertungsregeln
└── identity.json               # Hashes, Python/Paket-/Codeversion, Quelllauf, Zeitpunkt
```

Der HTML-Bericht verlinkt auf den bestehenden Extraktionsbericht mit Seitenbildern
und Rohtext. `participants.csv` zeigt, welcher Teilnehmer welcher Referenzzeile
zugeordnet wurde; `fields.csv` erklärt die Punkte pro Feld. Referenzwerte und
Personennamen werden nicht in der Konsolenzusammenfassung ausgegeben.

**Die Teilnehmerreihenfolge stammt aus der Anwesenheitsliste:** Eingabe-PDF,
PDF-Seite und ursprünglicher erkannter Eintragsindex. Die Referenzliste sortiert
die Ausgaben nicht um. Dies gilt für die Modellblätter in Excel, die Zuordnungs-
und Feld-CSV sowie die HTML-Detail- und Namensansichten. Nur in der Referenz
vorhandene Personen stehen anschließend; die Detailansicht kennzeichnet sie
in einem eigenen Abschnitt. Das separate Excel-Blatt „Referenz“ ist die Vergleichsgrundlage.

Beim Start wird die Referenz im Speicher eingefroren. Wenn du die Quelldatei während
eines längeren Modelllaufs änderst, wird weiter gegen die eingelesene Variante
bewertet; Bericht und Identität weisen auf die Änderung hin. Neue Referenzen lassen
sich später bewusst über `compare` prüfen. Originalreferenzen werden nie durch
Modellvorhersagen überschrieben. Alle Ergebnisdateien mit personenbezogenen Daten
bleiben lokal und sind gitignoriert.

## Ohne Unternehmensdaten ausprobieren

```powershell
.\.venv\Scripts\python.exe testframework/beispiele/demo_erstellen.py
.\.venv\Scripts\python.exe testframework/main.py compare --run testframework/beispiele/generiert/synthetische_vorhersagen --reference testframework/beispiele/generiert/referenz.csv
```

Die Demo erzeugt zwei synthetische PDFs und eine Referenz mit mehreren Schulungen.
Die ausdrücklich künstlichen Vorhersagen sind anders sortiert, enthalten einen
Schreibfehler und ein Duplikat. Der erwartete Levenshtein-Feld-F1 ist **82,69 %**;
das prüft Bewertungslogik, nicht Modellleistung. Der Bericht kennzeichnet dies klar.
Bestehende Demodateien werden nicht überschrieben.

Ein echter kleiner Modelllauf mit diesen synthetischen PDFs:

```powershell
.\.venv\Scripts\python.exe testframework/main.py run --input testframework/beispiele/generiert/pdfs --reference testframework/beispiele/generiert/referenz.csv --method vlm
```
