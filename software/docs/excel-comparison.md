# Extraktion mit der Excel-Kursliste vergleichen

Der Befehl `compare-excel` vergleicht einen vorhandenen Extraktionslauf mit einer
lokalen `.xlsx`-Datei. Die Excel-Datei wird ausschließlich nach der Extraktion
gelesen. Sie verändert keine Vorhersagen und wird nicht an OCR oder Modelle gegeben.
Originale, Excel-Datei und vorhandene Ergebnisse bleiben erhalten.

Die Ausgabe folgt der Anwesenheitsliste: Eingabe-PDF, numerische PDF-Seite und
ursprünglicher Eintragsindex. Die Referenz dient der Paarung und Bewertung;
ihre Zeilenreihenfolge verändert die ausgegebenen Teilnehmer nicht. Reine
Referenzfälle ohne zugeordnete Ausgabe stehen anschließend. In Excel enthalten
die Modellblätter nur die Extraktionen; das Blatt „Referenz“ bleibt separat.

## Installation und Start

Alle Befehle aus `software/` ausführen. Die Excel-Bibliothek `openpyxl` ist in
`pyproject.toml` und `uv.lock` aufgenommen. Die bestehende Umgebung aktualisieren:

```powershell
uv sync --locked --extra models
```

Die Referenz beispielsweise unter `data/referenz/kurse.xlsx` ablegen. Dieser
Ordner ist gitignoriert. Den bereits ausgeführten Modelllauf vergleichen:

```powershell
.venv/Scripts/participant-bench.exe compare-excel --run runs/DEINE_RUN_ID --excel data/referenz/kurse.xlsx
```

Alternativ über uv:

```powershell
uv run --offline --locked --extra models participant-bench compare-excel --run runs/DEINE_RUN_ID --excel data/referenz/kurse.xlsx
```

Standardmäßig werden alle Verfahren des gewählten Laufs getrennt bewertet.
Ein einzelnes Verfahren und ein bestimmtes Excel-Blatt auswählen:

```powershell
.venv/Scripts/participant-bench.exe compare-excel --run runs/DEINE_RUN_ID --excel data/referenz/kurse.xlsx --method vlm --sheet Tabelle1
```

Fehlgeschlagene Extraktionen bleiben als fehlende Personen in der Auswertung,
statt aus dem Nenner zu verschwinden. Pro Aufruf entsteht ein neuer Bericht
unter `runs/DEINE_RUN_ID/excel-comparison/<Lauf-ID>/`. Ein eigener leerer
Ausgabeordner kann mit `--output` angegeben werden.

## Spalten und Kurszuordnung

Die Zuordnung steht zentral in [`configs/excel.yaml`](../configs/excel.yaml):

| Excel-Spalte | Bedeutung | Extraktionsfeld |
| --- | --- | --- |
| `Class ID` | Kurs-ID für alle Personen dieses Kurses | sechsstellige ID im PDF-Dateinamen |
| `User ID` | Personalnummer, soweit lesbar | `personnel_number` |
| `First Name` | Vorname | `first_name` |
| `Last Name` | Nachname | `last_name` |
| `Organization` | Kurzzeichen | `department` |

Andere Spalten wie E-Mail, Item Title, Completion Status und Stunden werden nicht
zur Bewertung herangezogen. Spaltennamen lassen sich in der Konfiguration ändern;
Groß-/Kleinschreibung und Rand-Leerzeichen der Überschriften sind unerheblich.
`header_row` wählt die Kopfzeile, `sheet: null` das aktive Excel-Blatt.

Der Bericht und der Teilnehmerexport übernehmen die tatsächliche Schreibweise
der zugeordneten Überschriften direkt aus der XLSX. `participants.xlsx` enthält
die fünf verwendeten Spalten in ihrer ursprünglichen Reihenfolge: je ein Blatt
pro Verfahren, ein Blatt `Referenz` mit den verglichenen Kursen und `Quellen`
mit PDF-Seiten und ursprünglichen Referenzzeilen. Leere IDs bleiben leer;
führende Nullen und als Text erkannte Werte werden unverändert gespeichert.
Für Zuordnung und Bewertung werden führende Nullen numerischer User IDs jedoch
ignoriert: `0047285` und `47285` gelten als gleich. Die Normalisierung betrifft
ausschließlich den Vergleich, keine Originalwerte und keine Class IDs.
Die Referenzdatei selbst wird nur gelesen. Technische Feldkennungen in JSON/CSV
bleiben erhalten; `field_label` enthält zusätzlich die Originalüberschrift.

Das bestehende Extraktionsschema speichert das Kurzzeichen im Feld `department`.
`configs/local.yaml` erkennt dafür zusätzlich die Überschriften Kurzzeichen,
Kürzel und Organization. Bei abweichenden Formularen die Spaltenzuordnung bzw.
Regeln auf Entwicklungsdaten passend einstellen. Das Excel-Mapping ersetzt
keine fehlende Erkennung dieser Spalte.

`174563.pdf` wird dem Kurs `Class ID = 174563` zugeordnet. Auch die unterstützten
ursprünglichen Dateinamen, etwa `101158 - 174563 - 09.09.2026 MUC.pdf`, werden
erkannt. Die Zuordnung erfolgt über das Manifest des Laufs, nicht über die
Namen der erzeugten Vorschaubilder.

Für anders benannte PDFs kann eine CSV mit expliziten Zuordnungen dienen:

```csv
document_id,class_id
SHA256_AUS_DEM_MANIFEST,174563
```

```powershell
.venv/Scripts/participant-bench.exe compare-excel --run runs/DEINE_RUN_ID --excel data/referenz/kurse.xlsx --course-map data/referenz/kurszuordnung.csv
```

Pro Dokument ist genau ein Kurs möglich. Mehrere Dokumente desselben Kurses
werden gemeinsam verglichen. Nur in diesem Lauf enthaltene Kurse mit Excel-
Referenz gehen in die Kennzahlen ein. Andere Excel-Kurse werden separat gezählt.
Eine Stichprobe von drei PDFs wird somit nicht gegen alle Kurse der Excel-Datei
als vermeintlich fehlende Teilnehmer bewertet. Für die bewerteten Kurse wird
jeweils die vollständige Excel-Kursliste erwartet. Bei einzelnen ausgewählten
Seiten oder unvollständigen Kursunterlagen können fehlende Teilnehmer auch durch
die eingeschränkte Eingabe entstehen.

## Eindeutige Personen und verdeckte IDs

Der Abgleich sucht innerhalb eines Kurses zunächst die exakte Kombination aus
**Vorname + Nachname + Organization**. Bei Namen/Kurzzeichen werden Unicode,
Leerraum und Groß-/Kleinschreibung vereinheitlicht. Schreibfehler werden nicht
automatisch korrigiert; es gibt kein unscharfes Matching.

Eine vollständig lesbare, eindeutige User ID kann ebenfalls zuordnen, etwa wenn
der Name einen Erkennungsfehler enthält. Widersprechen sich ID und Namens-
Kurzzeichen-Kombination, bleibt die Zuordnung ungeklärt. Gleichnamige Personen
mit demselben Kurzzeichen und ohne unterscheidbare ID werden nicht willkürlich
zusammengeführt. Doppelte Referenzeinträge werden nicht automatisch entfernt.

Leere oder maskierte Excel-IDs, etwa `***`, `12***45` oder `XXXXX`, werden nicht
als lesbare IDs bewertet. Dagegen bleiben `illegible`, maskierte, als Platzhalter
ausgegebene oder fehlende Modell-IDs bei lesbarer Referenz Erkennungsfehler.
Nur Referenzbelege begründen den Ausschluss. Maskierungen sind über
`masked_user_id_pattern` und `missing_user_ids` konfigurierbar. Eine schwarze
Abdeckung im PDF kann der Excel-Abgleich selbst nicht erkennen; unklare Fälle
müssen am Seitenbild kontrolliert werden.

IDs werden als Strings verglichen; `00007` und `7` sind verschieden. Excel-Zahlen
mit reinem Nullformat wie `00000` werden entsprechend formatiert eingelesen.
Bereits verlorene führende Nullen werden nicht geraten. IDs am besten als Text
speichern. Formeln und ungeeignete ID-Zahlenformate führen zu einer verständlichen
Fehlermeldung; die Referenz als feste Werte exportieren.

## Ergebnisse prüfen

| Datei | Inhalt |
| --- | --- |
| `report.html` | Lokaler Bericht mit Zusammenfassung, ungeklärten Einträgen und Feldabweichungen |
| `participants.xlsx` | Teilnehmer je Verfahren und Referenz mit Original-Spaltennamen; Quellenblatt mit Seitenzuordnung |
| `summary.csv` | Kennzahlen je Verfahren, einschließlich Precision, Recall und F1 der Personenzuordnung |
| `matches.csv` | Gefundene, fehlende, zusätzliche, doppelte oder mehrdeutige Personen; Excel-Zeile und PDF-Seite |
| `field_comparison.csv` | Soll-/Ist-Werte je Referenzfeld, Lesbarkeit, Ausschlussgrund und Zuordnungsquelle |
| `course_mapping.csv` | Zuordnung der Dokumente zu Class IDs und ungeklärte Dokumente |
| `metrics.json` | Zähler und Nenner der Feldmetriken, ausgeschlossene IDs und Definitionen |
| `identity.json` | Referenz-, Manifest- und Extraktions-Prüfsummen sowie verwendete Konfiguration |

Die Felder werden einzeln per Exact Match und Precision/Recall/F1 bewertet.
Fehlende Referenzpersonen bleiben im Nenner; zusätzliche Vorhersagen beeinflussen
die Precision. Nicht bewertbare IDs werden separat ausgewiesen. Ungeklärte
Zuordnungen zählen konservativ als zusätzliche Vorhersagen und nicht zugeordnete
Referenzen als fehlend. Die entsprechenden Fälle stehen zur Kontrolle im Bericht.

**Zuordnung und Erkennungsqualität sind abhängig:** Wenn eine Person anhand der
User ID zugeordnet wurde, ist der ID-Treffer kein unabhängiger Qualitätsnachweis.
`independent_user_id_exact_match` bewertet die ID deshalb separat nur bei
Zuordnung über Namen und Kurzzeichen. Bei den Namen/Kurzzeichen gilt dieselbe
Abhängigkeit; `used_for_matching` im Feldprotokoll kennzeichnet solche Felder.

Der Excel-Abgleich misst die Übereinstimmung mit der Kursliste. Buchung oder
Completion in Excel beweist keine sichtbare Anwesenheit auf dem PDF. Eine
Abweichung kann daher auch ein Unterschied zwischen Kursliste und Dokument sein.
Für eine wissenschaftliche Extraktionsevaluation zusätzlich menschlich geprüfte
Seitentranskriptionen und getrennte Development-/Testdaten verwenden. Dieser
Excel-Export enthält keine Signatur-Ground-Truth; Unterschriften werden damit
nicht bewertet.

Technik: `openpyxl` liest die Arbeitsmappe im speichersparenden Read-only-Modus;
Formeln werden nicht ausgeführt und externe Workbook-Verknüpfungen nicht geladen.
Siehe die [offizielle Dokumentation](https://openpyxl.readthedocs.io/en/stable/tutorial.html)
und [Read-only-Modus](https://openpyxl.readthedocs.io/en/stable/optimized.html).
