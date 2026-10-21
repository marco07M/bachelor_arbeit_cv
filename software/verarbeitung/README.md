# 2. Eigentliche Dokumentenverarbeitung

Der vorhandene Benchmark liegt jetzt unter `src/participant_bench/` in diesem
Ordner. Er rendert PDF-Seiten, bereitet die Seiten auf und führt OCR/Regeln,
OCR mit lokalem Sprachmodell oder ein lokales Vision-Language-Modell aus.
Alternativ können LLM und VLM getrennt über eine konfigurierte API laufen;
Einrichtung mit Zugangsdaten in Umgebungsvariablen: [API-Anbindung](../docs/api.md).
Die Dokumentnummer im Dateinamen ist unabhängig von den Personalnummern,
die anschließend aus den Teilnehmerlisten extrahiert werden.

PDFs bzw. Seiten vorher manuell auswählen. Die Verarbeitung prüft nicht mehr,
ob eine Seite eine Anwesenheitsliste enthält: Alle eingegebenen Seiten werden
an die Teilnehmerextraktion übergeben. Rendering und optionale Ausrichtung
bleiben als technische Vorbereitung erhalten.

Das VLM gibt vorrangig Teilnehmerdaten aus. Nur wenn keine Teilnehmer erkannt
werden, wird der gesamte lesbare Seitentext als Fallback zur manuellen Prüfung
ausgegeben. Eine bestimmte Überschrift oder Listenform ist keine Voraussetzung.
Im Bericht stehen Teilnehmerdaten zuerst. „Gültiges Antwortformat“
betrifft die strukturierte Modellausgabe; es ist keine Prüfung auf Anwesenheitslisten.
Bei einem Ausgabeabbruch bleibt die Rohantwort unter `vlm/raw_text/` erhalten.
Fallback-Texte liegen unter `vlm/texts/` und in `page_text.jsonl`.

Leere Benutzerfelder werden als leere Einzelzelle behandelt. Die Person bleibt
erhalten, und das Kurzzeichen gehört weiterhin in `department`, auch wenn es
Ziffern, Bindestriche oder Schrägstriche enthält. Benutzer/Personalnummer und
Kurzzeichen werden nach Spaltenüberschriften und Position zugeordnet, nicht nach
der Reihenfolge der nichtleeren Wörter. Ein geschwärzter oder unlesbarer Benutzer
bleibt unbekannt (`null`); ein sichtbar leerer Benutzer wird `""/empty`.
Die gemeinsame VLM-Anweisung gilt lokal und über die API. Für bestehende
Berichte ist ein neuer Extraktionslauf erforderlich.

Auch `ocr_rules` und `ocr_llm` geben bei fehlenden strukturierten Teilnehmern
den vorhandenen OCR-Text als Fallback aus. Die Texte liegen entsprechend unter
`ocr_rules/texts/` und `ocr_llm/texts/`. Gründe für fehlende Zuordnungen und
Links zu den OCR-Rohdaten stehen im Bericht. Das Sprachmodell erhält kompakte
Worttabellen sowie die lesbare OCR-Zeilenaufteilung mit Zeilenkennungen und Wort-IDs.
Bei unbekannter Tabellenstruktur können für das Regelverfahren die Spalten und
der Tabellenbeginn konfiguriert werden; Beispiele stehen in der
[Software-Anleitung](../README.md#konfiguration-und-grenzen).

Im Abschnitt **OCR-Klartext und Modelleingabe** zeigt der Bericht alle OCR-Wörter
auch bei erfolgreicher Extraktion. Der Klartext liegt zusätzlich unter
`<Verfahren>/ocr_text/`, die exakte Worttabelle unter `ocr_llm/model_input/`.
Mit `participant-bench report --run runs/DEINE_RUN_ID` lässt sich die Darstellung
eines abgeschlossenen Laufs ohne neue Inferenz aktualisieren.

Das OCR-Sprachmodell erhält standardmäßig teilweise belegte Zeilen. Nur mit
vollständigen Wortbelegen in derselben OCR-Zeile werden Felder übernommen;
unsichere oder fremd zugeordnete Felder bleiben leer und bekommen Prüfhinweise.
Dies kann zusätzliche unvollständige Datensätze erhalten, ersetzt aber keine
Überprüfung ihrer Zuordnung und Vollständigkeit.

Die Feldprüfung nutzt die OCR-Zeilenkennung vor dem geometrischen Vergleich.
Unterschiedlich hohe Wortkästen derselben Zeile sind deshalb kein Ausschlussgrund.
Äußere Satzzeichen werden beim Vergleich toleriert, die beobachtete Schreibweise
bleibt erhalten. Der Hinweis „Wortbeleg gehört zu einer anderen OCR-Zeile“ bedeutet,
dass das Modell Angaben verschiedener Personenzeilen kombiniert hat.
„Wert nicht als vollständiges OCR-Wort oder Wortfolge vorhanden“ bedeutet dagegen,
dass der angegebene Wert im OCR-Text fehlt. `word_ids`-Hinweise betreffen die
Wortreferenzen des Modells; belegbare Felder werden dann aus den OCR-Wörtern lokalisiert.
„Unterschriftsfeld nicht zugeordnet“ betrifft nur den unbekannten Signaturstatus,
nicht die bereits extrahierten Namen oder Personalnummern.

Für die nächste OCR-Verbesserung empfiehlt sich zuerst die Layoutzuordnung:
Im Lauf `20261021T071358Z-2dcbf19f` liefert A auf beiden Seiten keine Teilnehmer,
weil die Spaltenüberschriften nicht ausreichend erkannt wurden. B liefert 19
Einträge mit Prüfhinweisen; ohne manuelle Referenz lässt sich daraus keine
Erkennungsqualität ableiten. Bei Vorlagen ohne erkannten Spaltenkopf können
bereits jetzt `rules.columns` und `rules.body_top` festgelegt werden.

Als weiterer Schritt wäre eine OCR pro Tabellenzelle sinnvoll: Die Anwendung
würde Zeilen und Spalten zuerst lokalisieren und leere Zellen ausdrücklich
erhalten. Dieser zusätzliche OCR-Modus ist noch nicht implementiert. Das ist
ein gezielter Ansatz für Tabellen; auch die [Tesseract-Dokumentation](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html#tables-recognition)
weist auf den Bedarf an eigener Segmentierung hin. Auf einer manuell
geprüften Stichprobe sollten außerdem 300 DPI gegenüber den bisherigen
220 DPI und die Linienentfernung an/aus verglichen werden, bevor Einstellungen
für den gesamten Datensatz geändert werden.

Für Unterschriften verwendet die lokale Standardkonfiguration zusätzlich das
vorhandene Qwen3-VL-4B-Instruct auf vergrößerten Zeilenausschnitten. Diese
gemeinsame Zusatzstufe gilt für A/B/C und wird getrennt protokolliert. Sie kann
sichtbare Unterschriftsmarkierungen positiv erkennen; die reine OpenCV-Baseline
konnte bisher nur leere Felder negativ entscheiden. Unklare Felder bleiben offen.
Die Teilnehmerfelder werden durch die Signaturprüfung nicht geändert.

Bereits vorhandene Ergebnisse nur auf Unterschriften nachprüfen:

```powershell
.venv/Scripts/participant-bench.exe signatures --run runs/DEINE_RUN_ID --method vlm
```

Für OCR+LLM `--method ocr_llm` verwenden. Ein neuer Bericht entsteht unter
`signature-review/` im Quelllauf. Im Abschnitt **Unterschriften im Detail**
lassen sich die tatsächlichen Zeilenbilder prüfen. Originalergebnisse bleiben
erhalten. Mit `signature.backend: opencv` ist weiterhin die reine, konservative
Baseline verfügbar. Eine Unterschriftsmarkierung belegt weder Identität noch Echtheit.

Alle folgenden Befehle werden weiterhin aus `software/` ausgeführt. Nach einer
Aktualisierung des Repositorys die lokale Paketinstallation einmal anpassen:

```powershell
uv sync --locked --extra models
```

Die Ausgabe der [Vorverarbeitung](../vorverarbeitung/README.md) direkt verwenden:

```powershell
uv run --offline --locked --extra models participant-bench prepare --input vorverarbeitung/ausgabe/pdfs --config configs/imported.yaml --output prepared/meine-listen
uv run --offline --locked --extra models participant-bench run --input vorverarbeitung/ausgabe/pdfs --config configs/imported.yaml --offline
```

`configs/imported.yaml` aktiviert alle drei Verfahren. Die Vorverarbeitung legt
alle gültigen PDFs direkt im Eingabeordner ab; auch rekursive Suche wird von der
Konfiguration unterstützt. Modelle und OCR müssen vorher eingerichtet
sein. Für neue Seitenvorbereitungen jeweils einen neuen `--output`-Ordner wählen.
`prepare` erzeugt Seitenbilder zur Kontrolle; `run` ohne Manifest bereitet alle
Eingabeseiten selbst auf und extrahiert daraus die Teilnehmenden. Ältere
Manifeste mit automatischer Seitenauswahl mit `prepare` neu erzeugen.
Für die Arbeit mit einem kontrollierten Manifest sowie
Ground Truth siehe die [Software-Anleitung](../README.md).

Während `run` siehst du automatisch die aktuelle Datei und PDF-Seite sowie
die Schritte der Vorbereitung, Gewichtsprüfung, Modellladen, Warm-up und Inferenz.
Längere Schritte melden alle zehn Sekunden ihren Status. Pro Seite werden
technischer Status, Anzahl ausgegebener Einträge und Laufzeit angezeigt.
Die Meldungen stehen zusätzlich im Laufordner unter `progress.log`.

Konfigurationen, Tests, virtuelle Umgebung und Modellgewichte werden von den
beiden Softwarebereichen im übergeordneten `software/`-Projekt verwaltet.

## Mit einer Excel-Kursliste abgleichen

Nach einem Extraktionslauf kann die Ausgabe ohne neue Modellinferenz mit der
Excel-Liste verglichen werden:

```powershell
.venv/Scripts/participant-bench.exe compare-excel --run runs/DEINE_RUN_ID --excel data/referenz/kurse.xlsx
```

Die PDF-ID bestimmt die `Class ID`. `Organization` enthält das Kurzzeichen.
Verdeckte User IDs werden nicht als lesbare IDs bewertet; Namen und Kurzzeichen
ermöglichen die Zuordnung. Ausgaben und Bedienung:
[Excel-Abgleich](../docs/excel-comparison.md).
