# Handschrift: Ursachenanalyse, Datenerhalt und kontrollierte Versuche

Stand: 03.11.2026. Unveränderte sechs Hauptverfahren; keine zusätzlichen Modelle,
Trainings, Downloads oder Abhängigkeiten. Reale Daten bleiben lokal und gitignoriert.

## A. Ursachenanalyse und Modelleignung

Ausgangspunkt: `testframework/ergebnisse/20261103T092511Z-5be3affb/`, Quelllauf
`runs/20261103T091220Z-9a1bd0fb/`, dieselbe zweiseitige Entwicklungs-PDF.
Seite 1 enthält maschinenschriftliche Teilnehmer und handschriftliche Signaturen;
Seite 2 enthält handschriftliche Teilnehmer. Beide PDF-Seiten haben **keinen
eingebetteten Text**. Eine bevorzugte PDF-Textebene ist in diesem Fall keine Ursache.

| Komponente | Nachgewiesener Befund | Aussagegrenze |
| --- | --- | --- |
| Tesseract | 5.4.0.20240606, `deu+eng`, PSM 6, Linienentfernung aktiv. Nichtleere Wörter werden unabhängig von ihrer Konfidenz gespeichert. | Fehlender Text beweist ohne Regionsreferenz nicht, ob Detektion oder Transkription scheiterte. |
| Paddle | `PP-OCRv5_server_det` und `latin_PP-OCRv5_mobile_rec`, lokale festgeschriebene Gewichte. Auf Seite 2 sind 26 OCR-Belege vorhanden, aber keine Tabelle. | Tabellenverlust und unvollständige Erkennung sind getrennte Probleme. |
| Paddle-Zuordnung | Die gespeicherte Antwort enthält neun Personen auf Seite 2. Alle neun scheiterten bislang am Schema, weil ein einzelnes Zielfeld fehlte. | Das ist ein nachgelagerter Datenverlust, kein fehlendes OCR-Ergebnis. |
| Paddle-Konfidenzen | Effektive Recognition-Schwelle bereits 0,0; auf Seite 2 bleibt auch ein Score unter 0,5 erhalten. | Kein Beleg für einen Konfidenzfilter als Ursache dieses Verlusts. |
| Docling | Tesseract-OCR vorhanden, native Tabelle auf Seite 2 nur 6×3, keine verwertbaren Überschriften. | Drei unterhalb der sichtbaren Tabelle stehende Einträge passen nicht in diese Rekonstruktion. Keine sichere Feldzuordnung daraus erzwingen. |
| Bildvorverarbeitung | Linienentfernung entfernt auch lange Stiftstriche in einem unabhängigen synthetischen Test. | Entfernte reale Tintenpixel sind nicht automatisch beschädigte Handschrift: Viele gehören zum Tabellenraster. |

Tesseract ist laut [offizieller FAQ](https://tesseract-ocr.github.io/tessdoc/FAQ.html#can-i-use-tesseract-for-handwriting-recognition)
für Druckschrift ausgelegt. Segmentierung und bessere Bilder können einzelne
Fehler reduzieren, ersetzen aber kein geeignetes Handschrifttraining.

Paddles [offizielle Mehrsprachenbeschreibung](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.en.md)
nennt Deutsch als unterstützte Sprache des Latin-Modells. Das belegt die
Sprach-/Zeichenabdeckung, keine Genauigkeit für deutsche Schreibschrift oder Namen.
Die allgemeine [mobile PP-OCRv5-Konfiguration](https://github.com/PaddlePaddle/PaddleOCR/blob/main/configs/rec/PP-OCRv5/PP-OCRv5_mobile_rec.yml)
verwendet SVTR_LCNet. Aussagen über verbesserte englische Handschrift im
[englischen Recognizer](https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_recognition.html)
dürfen nicht ohne Prüfung auf die hier festgeschriebenen Latin-Gewichte übertragen werden.
Der Referenzumfang und die Handschriftdomäne erlauben keine pauschale Aussage,
dass dieses Modell Handschrift überhaupt nicht unterstützt oder generell beherrscht.

Docling übernimmt als Parser die Grenzen seines Tesseract-Backends; TableFormer
transkribiert keine zuvor übersehenen Handschriftzeichen. DEFAULT/FULL_PAGE,
OCR-Skalierung und Cell Matching beeinflussen unterschiedliche Verarbeitungsschritte.
Frühere FAST/ACCURATE-/Matching-/Full-Page-Versuche stehen unverändert im
[Strukturbericht](structure-optimization.md). Es wurde kein stiller Paddle-/VLM-
Fallback für Docling eingebaut.

## B. Vorhandene Erkennung und nachgelagerte Verluste

Tesseract speichert im Ausgangslauf 138 Wörter auf Seite 1 und 51 auf Seite 2.
Docling besitzt auf beiden Seiten positionierte OCR-Belege; Paddle ebenfalls.
Diese Texte enthalten teilweise Lesefehler. Die Wort-/Zeichenanzahl ist keine Qualität.

Der konkrete Paddle-Verlust ist reproduziert: `ValueAssignedRow` verlangte bisher
alle vier Feldschlüssel. Die Handschriftantwort ließ ein einzelnes Feld weg;
die neun übrigen Personendatensätze wurden vollständig als Schemafehler verworfen.
Mit unbekanntem fehlendem Feld lassen sich neun Zeilen durch die unveränderte
Literal- und Positionsprüfung führen. Kurzzeichen, die als Benutzer-ID vorgeschlagen
wurden, bleiben außerhalb der ID-Spalte abgelehnt. Nicht beobachtete Namen werden
nicht ergänzt. Nicht zuordenbare OCR-Belege bleiben separat erhalten.

## C. Änderungen

- `unlimited_assignment.py`: fehlende Einzelzielfelder sind optional und werden
  `null`/`uncertain`; falsche Datentypen, unbekannte Quellen, zusätzliche Felder
  und unbelegte Zeichenfolgen bleiben unzulässig. Protokollversionen v17/v18.
- `structure_assignment.py`: Feldbelege enthalten konkrete OCR-Texte, native
  Quellverweise, Positionen und unveränderte Engine-Konfidenzen. Scores unter
  0,5 auf der nativen 0..1-Skala dienen nur als Prüfhinweis: Wert erhalten,
  Feldstatus `uncertain`, keine Korrektheitswahrscheinlichkeit.
- Sichtbare Teiltextmarker wie `...`/`…` werden bei belegten Feldwerten als unsicher
  markiert. `structured_mapping.py` tut dies auch für native Docling-Zellen.
  Es wird kein fehlender Namensrest ergänzt und keine unsichere Gruppe willkürlich geteilt.
- `structure_diagnostics.py`: zusätzliche Feldbeleg- und nicht direkt referenzierte
  OCR-CSV-Dateien, weiter mit vorhandenen Stufenberichten und Overlays. Ein fehlender
  direkter Quellverweis beweist nicht, dass ein Text irrelevant ist; insbesondere
  besitzen OCR- und native Tabellenzellen unterschiedliche Kennungen.
- `config.py`/Paddle-Backend: explizite experimentelle Detektionsgröße,
  Erkennungsschwelle und Zeilenorientierung. Ohne gesetzte Parameter bleibt
  das bisherige Engine-Verhalten erhalten. Das Hauptprofil wurde nicht umgestellt.
- `scripts/handwriting_probe.py`: kleine OCR-/Vorverarbeitungs- und Zellproben.
  `scripts/replay_partial_assignments.py`: isolierter Validierungs-Replay ohne neue
  OCR-/LLM-Inferenz, mit eingefrorener Kursreferenz und Originalschutz.

Die Typ-/Literalprüfung wurde nicht insgesamt abgeschaltet. Ein Datensatz ohne
belegte Identität erzeugt keine Person. Eine fehlende OCR-Beobachtung wird nicht
als bestätigte Leerzelle ausgegeben. Bereits vorhandene Schemata reichen aus;
es wurde kein künstliches Confidence-Feld im Teilnehmerdatensatz eingeführt.

## D. Gemessener Datenerhalt und neue Fehler

Abschließender Replay:
`runs/handwriting-retention-20261103-final/comparison/report.html`.
Die gespeicherten OCR- und LLM-Antworten bleiben inhaltlich gleich. Nur ihre
Validierung wird neu ausgeführt. Historische Dateien und Referenzen sind hashgleich.

| Paddle gegen dieselben 72 erwarteten Kursfelder | Vorher | Nachher |
| --- | ---: | ---: |
| Teilnehmerausgaben | 9 | 18 |
| Exakte Feldwerte | 29 | 38 |
| Falsche ausgegebene Feldwerte | 7 | 15 |
| Fehlende Feldwerte | 36 | 19 |
| Nichtleere unsichere Feldwerte | 0 | 13 |
| Exakter Feld-Recall | 40,28 % | 52,78 % |
| Exakte Precision | 80,56 % | 71,70 % |
| Exakter Feld-F1 | 53,70 % | 60,80 % |
| Levenshtein-Feld-F1 | 64,89 % | 78,23 % |

Alle 29 bisherigen exakten Treffer bleiben erhalten; neun weitere werden korrekt.
Acht weitere ausgegebene Feldwerte passen nicht exakt zur Kursreferenz. Es wurden
keine neuen Zeichenfolgen erfunden: Die zusätzlichen Werte stammen aus vorhandenen
OCR-Belegen. Trotzdem sind mehr Ausgaben nicht pauschal besser; die sinkende Precision
wird ausdrücklich neben höherem Recall gezeigt. Alle Teilnehmerwerte der bisherigen
maschinenschriftlichen ersten Seite sind unverändert. Die anderen fünf Verfahren
wurden für diesen Replay nicht verändert oder neu ausgeführt.

Die zusätzliche CPU-Validierung dauert in diesem Lauf insgesamt rund 0,064 s.
Es gibt dabei keine zusätzlichen OCR-/LLM-Aufrufe und keinen zusätzlichen GPU-Schritt.
Das ist eine Einzelmessung ohne Durchsatzgarantie. Die gespeicherten ursprünglichen
Modelllaufzeiten bleiben erhalten; der Replay-Aufwand wird separat ausgewiesen.

## E. Vorverarbeitung, Ausschnitte und Modellgrenzen

Voruntersuchung: `runs/handwriting-probe-20261103/report.html`.
Identische zwei Ausgangsseiten, dieselben Tesseract-Gewichte. Sieben Varianten,
24 geometrisch aus eingefrorenen TableFormer-Zellen erzeugte PSM-7-Ausschnitte,
kleine Paddle-/Docling-Varianten. Kein Text wird anhand der Referenz ausgewählt.

| Tesseract-Variante | Zeichen Seite 1 | Zeichen Seite 2 |
| --- | ---: | ---: |
| Bisher: PSM 6, Linienentfernung | 935 | 217 |
| Ohne Linienentfernung | 434 | 109 |
| PSM 11 ohne Linienentfernung | 808 | 210 |
| Grau/Kontrast ohne Linienentfernung | 518 | 167 |
| Adaptive Binarisierung | 434 | 201 |
| Median-Rauschfilter | 651 | 197 |
| Echtes neues PDF-Rendering mit 300 DPI | 434 | 188 |

Diese Zahlen betreffen jeweils die ganze Seite einschließlich Logos und Fußzeilen;
sie sind **keine separate Handschriftgenauigkeit**. Die Richtwerte für Auflösung
und Ausschnittsegmentierung stammen aus [Tesseracts Qualitätsdokumentation](https://github.com/tesseract-ocr/tessdoc/blob/main/ImproveQuality.md),
sind aber kein Beleg eines Vorteils auf dieser konkreten Scanvorlage.
Höhere DPI erzeugt bei einem bereits eingescannten Raster außerdem keine neue Information.

21 von 24 Zellausschnitten liefern nichtleeren Text; zusammen rund 4,64 s.
Die Zellgeometrie selbst ist fehleranfällig und deckt freistehende Einträge nicht
vollständig ab. Ohne geprüfte Ausschnitttranskripte ist kein Qualitätsvorteil belegt.
Deshalb wurde kein zusätzlicher produktiver Zellen-OCR-Modus eingeführt.

Die reale Linienentfernung entfernt auf Seite 1 141.803 von 302.648 Tintenpixeln,
auf Seite 2 5.771 von 73.511. Ohne unabhängige Schriftmasken kann dieser Anteil
nicht in Raster und beschädigte Schrift zerlegt werden. Der synthetische Stifttest
zeigt ein mögliches Risiko, keinen gemessenen Schaden an realen Namenszeichen.

Paddle mit Detektionsseitenlänge 1600 gibt dieselben Zeichenmengen wie die Baseline
aus. Die ursprüngliche Grenze ist 736 mit `limit_type=min`; beide Grenzen liegen
unter der kurzen Seite dieser Eingaben. Eine zusätzliche explizite 3200-Probe unter
`runs/handwriting-paddle-3200-20261103/` liefert 275/31 Zeichen statt 888/240.
Das ist kein Qualitätsnachweis und kein Grund zur Übernahme. Der effektive Recognizer
bleibt unverändert; Gewichte wurden nicht ausgetauscht.

Docling ohne Linienentfernung, einmal DEFAULT und einmal FULL_PAGE, liefert im
deterministischen Kursvergleich jeweils 0/72 exakte Felder statt zuvor 19/72.
Die bisherige Teilzuordnung geht dabei verloren. Diese Varianten werden ausdrücklich
nicht übernommen. Rohtext, Tabellen und effektive Optionen sind gespeichert.

Die ersten Proben enthalten 44 echte OCR-/Strukturaufrufe; die zusätzliche
Paddle-3200-Prüfung zwei weitere. Engine-Aufwand, GPU-Allokation/Reservierung,
Ladezeit und Messwerte stehen in den jeweiligen JSON-/Ressourcendateien.
Tesseract-RAM ist eine Prozessmomentaufnahme, kein behaupteter Peak. Ladezeit und
OCR-Zeit werden nicht als vergleichbare Modelllatenzen vermischt.

### Optionale HTR-Erweiterung

Ein separater Linien-HTR-Versuch wäre wissenschaftlich sinnvoll, sobald geprüfte
Handschrift-Zeilentranskripte und passende Segmentierung vorliegen. Er gehört als
zusätzliche experimentelle Variante neben die sechs Hauptverfahren.

[Microsoft TrOCR](https://github.com/microsoft/unilm/blob/master/trocr/README.md)
bietet eine auf IAM angepasste Base-Variante mit 334 Millionen Parametern.
Die [veröffentlichte Modellkarte](https://huggingface.co/microsoft/trocr-base-handwritten)
nennt MIT als Lizenz und einen englischen Handschrift-/Einzeilenkontext.
Deutsche Namen, Umlaute und alphanumerische IDs sind damit nicht separat validiert.
Die Größenordnung der reinen FP32-Parameter wäre rechnerisch etwa 1,34 GB;
Aktivierungen, Decoder, GPU-/RAM-Bedarf und Latenz müssen tatsächlich gemessen werden.
Hierzu wurden keine Gewichte geladen und keine Laufzeiten erfunden.

Ein solcher Versuch benötigt dokumentierte Rechte und Modellrevision, lokale
Inferenz, feste Ausschnittgeometrie und dieselben geprüften Referenzregionen wie
die OCR-Baselines. Erst danach lässt sich Qualität gegen Ressourcenaufwand abwägen.
Für diese Bachelorarbeit hat die Beseitigung nachgewiesener Datenverluste zunächst
geringeren Implementierungsaufwand und besser nachvollziehbaren Nutzen.

## F. Evaluation und Referenzgrenzen

Der Nutzer bestätigt, dass die Excel-Kursreferenz auch die handschriftlichen
Texte enthält, jedoch ohne Koordinaten. Sie wird unverändert für den dokumentweiten
Feldvergleich verwendet. Es gibt keine automatisch aus Vorhersagen erzeugten
Handschriftlabels und keine künstliche Ground Truth.

Ohne unabhängige Seiten-/Regionszuordnung bleiben Handschrift-CER/WER, regionale
Erkennungsabdeckung, regionale Teiltrefferquote und getrennte Handschrift-Precision
**nicht gemessen**. Dies gilt auch für Zellproben, in denen Text vorhanden ist.
Die leere Referenzvorlage `data/handwriting-review-20261102/` wurde nicht automatisch gefüllt.

Die zweite PDF-Seite zeigt leere Benutzerzellen. Eine Kursliste kann entsprechende
User IDs dennoch kennen. Solche Referenzwerte sind keine automatisch belegten
erwarteten OCR-Inhalte der PDF. Die Referenz muss vor einer seitenbezogenen
Extraktionsmessung fachlich geprüft werden; hier wurde sie nicht umgeschrieben.
Kursübereinstimmung ist keine unabhängige Identitäts- oder Handschriftqualitätsprüfung.

Die bestehende normale Teilnehmerbewertung und Reihenfolge bleiben erhalten.
Die OCR-VLM-Hinweise stammen weiterhin aus Paddle-Rohbelegen, nicht aus den nun
zusätzlich erhaltenen Paddle-LLM-Personen. Für den Hybrid wird kein Qualitätsgewinn
aus dieser Parserkorrektur behauptet. Unterschriften werden nicht als Text transkribiert.

## G. Wissenschaftliche Einordnung

Nachgewiesen ist der Erhalt bereits erkannter Texte und eine bessere dokumentweite
Kursübereinstimmung bei gleichzeitig zusätzlichen falschen Feldwerten. Nicht
nachgewiesen ist eine generelle Verbesserung der Handschrifterkennung durch neue
Bildparameter. Es wird deshalb kein globaler OCR-Sieger und keine bessere
Maschinenschriftqualität aus Zeichenmengen abgeleitet.

Die Hauptkonfiguration behält ihre bisherigen OCR-Gewichte und Bildparameter.
Die neue Schema-/Beleglogik ist aktiv; experimentelle Paddle-Parameter sind nur
bei expliziter Konfiguration wirksam. Alle sechs Baselines bleiben getrennt.

## H. Verifikation und Reproduktion

Neue synthetische Tests prüfen ausgelassene Einzelzielfelder, belegte Teiltexte,
niedrige/fehlende Konfidenzen, keine Erkennung, unzugeordnete Beobachtungen,
leere Nachbarzellen, falsche Positionen, erfundene Werte, unveränderte Originalbilder,
Strichverlust bei Linienentfernung, inverse Koordinaten bei Auflösungsänderung
und native Docling-Teilzellen. Sie belegen keine reale Handschriftqualität.

72 gezielte Tests und anschließend **609 vollständige lokale Tests in 81,90 s**
bestanden. **48 Tests des separaten API-Projekts in 17,60 s** bestanden; keine
API-Modellaufrufe. Ruff ohne Befund. JSON-/CSV-/HTML-Feldzähler, Quelle und
Teilnehmerreihenfolge werden zusätzlich im finalen Replay kontrolliert.

Aus dem Softwareordner, neue Ausgabeordner verwenden:

```powershell
.\.venv\Scripts\python.exe scripts/handwriting_probe.py --source-run runs/20261103T091220Z-9a1bd0fb --output runs/handschrift-probe-neu --structures --source-report testframework/ergebnisse/20261103T092511Z-5be3affb
.\.venv\Scripts\python.exe scripts/replay_partial_assignments.py --source-report testframework/ergebnisse/20261103T092511Z-5be3affb --output runs/handschrift-replay-neu
.\.venv\Scripts\python.exe -m pytest -q
```

Der aktuelle Probe-Befehl nutzt die explizite 3200-Variante. Die frühere 1600-Probe
bleibt mit ihrer eingefrorenen Konfiguration erhalten. Der Replay enthält
unveränderte Modellantworten, alte und neue Validierungsstände, neue Diagnosen und
eine eigene Referenzauswertung. Ursprüngliche Forschungsartefakte bleiben erhalten.
