# Extraktionsqualität und Fehleranalyse, 06.11.2026

Aktueller systematischer Auftrag vom 11.11.2026 mit kontrolliertem Gegencheck:
[Eingabebudget, verbleibende Fehler und gemessene Vor-/Nachteile](systematic-error-analysis-20261111.md).

Neuere Ursachenprüfung vom 11.11.2026 auf zehn PDFs und zwanzig Seiten:
[Feldverluste, Ausrichtung und gezielte Korrekturen](field-loss-20261111.md).
Der folgende Abschnitt bleibt der historische Nachweis vom 06.11.

Ausgangspunkt ist der lokale Vergleich
`testframework/ergebnisse/20261106T081128Z-0011a735/`, Quelllauf
`runs/20261106T080030Z-f1e4fa77/`. Die zwei Seitenbilder, OCR-Ausgaben,
historischen Antworten und eingefrorenen Kursreferenzen wurden erhalten.
Referenzdaten werden erst nach abgeschlossener Extraktion geladen.

## Nachgewiesene Verluststellen

| Verfahren | Seite 1 | Seite 2 | Belegte Verarbeitungslücke |
|---|---|---|---|
| OCR-LLM | 138 Wörter, 9 Personen; 9 Organisationsfelder fehlen | Alle 51 OCR-Wörter in allen 10 Zeilen an das LLM übergeben, keine Person in dessen Antwort | Auf Seite 2 kein nachträglicher Zeilenverlust: Modellantwort bereits leer. Für die fehlenden Organisationsfelder fehlt eine verlässliche Überschriftenzuordnung. |
| Paddle-LLM | 63 Beobachtungen, 9 Personen | 26 Beobachtungen, 9 Personen; Modell lässt Organisation leer | Aktuelle Organisationszellen existieren in denselben Quellzeilen; die kompatible Überschriftenübernahme wurde bisher nur zur Validierung benutzt. Anders als beim HTML-Zellpfad gab es keine Übernahme einer eindeutigen beobachteten Zelle. |
| Docling | 153 Beobachtungen, native Tabelle 19×7, 9 unsichere Teilpersonen | 66 Beobachtungen, native Tabelle 6×3, keine Personen | Keine eindeutigen erkannten Überschriften. Der native Teilpersonenpfad übernimmt Namen/IDs bei wiederholtem Strukturbeleg, aber keine unbewiesene Organisationsspalte. Die beschädigte Fortsetzungsstruktur ist keine belegte Spaltenfortsetzung. |

Bei Docling bleiben vor und nach der SDK-Zusammenführung dieselben 153 bzw.
66 Beobachtungen erhalten. In dieser PDF ist kein SDK-Verlust nachgewiesen.
Eine niedrige oder fehlende Confidence löscht in den geprüften Pfaden keinen
OCR-Text. Das unabhängige Beobachtungsregister erhält auch nicht zugeordnete
Texte. Text im Register zählt weiterhin nicht automatisch als Teilnehmerfeld.

Die Paddle-Prüfung verwirft außerdem neun unbelegte Felder auf Seite 2
(acht ID-Vorschläge und ein Namensfeld). Das ist eine nachgewiesene Ablehnung;
es beweist nicht, dass der verworfene Vorschlag korrekt gewesen wäre.

## Technische Änderung

`structure_assignment.observed_cell_bands` begrenzt skalare Feldrollen durch
erkannte Überschriften **und gemessene physische Rasterlinien**. Die bisherige
letzte Textrolle konnte bis zum rechten Seitenrand reichen; dieser breite
Validierungsbereich wäre zur Übernahme einer Zelle einschließlich benachbarter
Signaturspalten ungeeignet.

`complete_observed_cells` ergänzt nur fehlende ID-/Organisationsfelder bereits
belegter Teilnehmer. Es muss genau eine nicht leere aktuelle OCR-Zelle vollständig
innerhalb der belegten physischen Spalte liegen. Mehrere Fragmente, übergreifende
Zellen, fehlendes Raster, neue mehrdeutige Überschriften, eine andere PDF oder
inkompatible Folgegeometrie erlauben keine Ergänzung. Fehlende OCR beweist keine
leere Zelle. Vorhandene Werte einschließlich expliziter Leerantworten bleiben
erhalten. Maskierte IDs werden nicht als lesbare IDs ergänzt.

Alle Ergänzungen werden als `uncertain` gespeichert, unabhängig vom Engine-Score.
Belege enthalten ursprünglichen Feldzustand, aktuelle OCR-Zelle, Score, Position,
Quellreferenz und Überschriftenherkunft. Reihenfolge und Teilnehmerzahl ändern
sich durch diesen Schritt nicht. Namen werden nicht aus Referenzdaten repariert.
Im räumlichen Paddle-Zuordnungspfad ist der Schritt aktiv; der native Docling-
Mapper und der Tesseract-Zuordnungspfad bleiben hinsichtlich ihrer Aufnahmebedingungen
unverändert. Prompt-/Cache-Versionen wurden erhöht.

## Kontrollierter Vergleich

Reproduzierbarer Vergleich ohne neue Inferenz:

```powershell
.\.venv\Scripts\python.exe scripts/check_extraction_quality.py `
  --source-report testframework/ergebnisse/20261106T081128Z-0011a735 `
  --output runs/extraction-quality-NEUER-ORDNER
```

Der Ausgabeordner muss neu sein. Das Skript kopiert den Quelllauf, ergänzt
ausschließlich aktuelle Zellbelege und liest erst danach die eingefrorene Referenz.
Vorher und nachher werden mit derselben Bewertungsimplementierung ausgewertet.
Die Originaldateien werden über Prüfsummen auf Unverändertheit geprüft.

Lokale Ergebnisse: `runs/extraction-quality-20261106-final/report.html`,
`comparison.json` und `qa.json`; Analyseseiten in `before/` und `after/`.

| Verfahren | Personen vorher → nachher | Korrekt | Falsch | Fehlend | Exakter Feld-Recall | Exakter Feld-F1 |
|---|---:|---:|---:|---:|---:|---:|
| OCR-LLM | 9 → 9 | 23 → 23 | 4 → 4 | 45 → 45 | 31,94 → 31,94 % | 46,46 → 46,46 % |
| Paddle-LLM | 18 → 18 | 38 → 40 | 15 → 20 | 19 → 12 | 52,78 → 55,56 % | 60,80 → 60,61 % |
| Docling | 9 → 9 | 19 → 19 | 6 → 6 | 47 → 47 | 26,39 → 26,39 % | 39,18 → 39,18 % |

Je Verfahren bleiben 18 Referenzpersonen und 72 bewertbare Referenzfelder im
Nenner. Keine zusätzlichen Personen oder zusätzlichen Referenzfelder; fünf
weitere falsche Werte entstehen innerhalb vorhandener Felder. Alle bisherigen
korrekten Felder und alle Teilnehmerpaarungen bleiben erhalten. Die zwei neuen
Treffer sind Organisationsfelder von zugeordneten Personen auf Seite 2.
Paddles Levenshtein-Feld-F1 steigt von 78,23 auf 82,74 %.

**Zielkonflikt:** Sieben zusätzliche beobachtete Zellen liefern zwei exakte Treffer
und fünf falsche Werte. Der Recall steigt, die exakte Precision sinkt von 71,70
auf 66,67 %, der exakte F1 fällt geringfügig. Das ist kein umfassender
Qualitätsgewinn und keine Freigabe zur ungeprüften Übernahme. Die Werte bleiben
als unsicher sichtbar. Der Vergleich eignet sich nicht zur Signifikanzbewertung
oder zur Verallgemeinerung auf andere Listen.

Zusätzliche praktische Prüfung: `runs/extraction-quality-20261106-live/`
verwendet dieselben nativen OCR-Belege und zwei neue lokale LLM-Antworten.
Die reale Pipeline ergänzt null Zellen auf Seite 1 und sieben auf Seite 2;
`runs/extraction-quality-20261106-live-comparison/report.html` bestätigt dieselben
40 korrekten, 20 falschen und 12 fehlenden Felder. Die neue Zuordnung dauert
88,29 s inklusive lokaler Modellvorbereitung; es wurde keine erneute OCR ausgeführt.

Der eingefrorene Replay benötigt zusätzlich rund 0,0045 s für die geprüfte
Nachverarbeitung beider Seiten. Das ist keine neue End-to-End-Laufzeit.
Historische volle Methodenlaufzeiten: OCR-LLM 339,07 s, Paddle 104,59 s,
Docling 19,39 s. Diese Zeiten sind mit der neuen reinen Zuordnungszeit nicht
als gleichartige Geschwindigkeitsmessung vergleichbar. Die Replay-Auswertung
weist deshalb keine neue vollständige Methodenlaufzeit aus.

## Separate Analyseseite

Jeder neue Kursreferenzvergleich und jede Detailansicht-Aktualisierung erzeugen
`extraction_errors.html`, verlinkt im Hauptbericht und Detailvergleich.
`error_analysis/fields.json` enthält alle Feldfälle,
`error_analysis/checks.json` deren aggregierte Zähler und Rohdaten-Prüfsummen.

Die Seite enthält:

- Originales Extraktionsfeld, Referenzwert und tatsächlich bewerteten Wert
  nebeneinander, einschließlich ausschließlich im Vergleich vertauschter Namen.
- Bewertung korrekt/falsch/fehlend/zusätzlich/nicht bewertbar, unverändert aus
  den gespeicherten Feldbeiträgen; Ausgabeordnung gemäß PDF/Seite/Modellzeile.
- Filter für Verfahren, PDF-Seite, Feldtyp, Fehlerkategorie, Beleglage und
  Feldbewertung sowie Textsuche.
- Alle OCR-Beobachtungen inklusive niedriger/fehlender Scores, native Zellen,
  Tabellenmarkup, vollständige Modellantworten und Links zu Eingaben/Zwischenständen.
- Lokale Bildausschnitte aus gespeicherten Extraktionspositionen, sofern vorhanden;
  diese Ausschnitte sind ausdrücklich keine manuell verifizierten Referenzpositionen.
- Nachgewiesene Ablehnungen, Übergabelücken und fehlende Mapperrollen; Vermutungen
  über Lesefehler getrennt von unbekannten Ursachen.

Die Excel-Referenz ist kursbezogen und hat keine Seiten-/Zeilenkoordinaten.
Nicht zugeordnete Referenzpersonen erscheinen deshalb unter **Seite unbekannt**.
Auch wenn Seite 2 offensichtlich Handschrift enthält, werden fehlende Excel-Zeilen
keiner erfundenen PDF-Position zugewiesen. Ohne geprüfte Feldlokalisierung kann
die Diagnose OCR-Nichterkennung und falsche Lesung/Spalten-/Personenzuordnung
nicht für jedes einzelne Referenzfeld unterscheiden. Ein global fehlender
Referenzstring ist kein Beweis eines OCR-Fehlers.

Die Seite führt keine Inferenz und keine neue Bewertung aus, lädt die aktuelle
Excel-Datei nicht nach und verändert keine Scores. HTML-Inhalte sind escaped;
Filter arbeiten lokal mit einem per CSP-Hash erlaubten festen Skript. Es gibt
keine externen Skripte, Telemetrie oder Netzwerkabfragen.

## Prüfungen und verbleibende Grenzen

Gezielte Tests decken niedrige Scores, maskierte IDs, geteilte/übergreifende
Zellen, explizite Leerantworten, fehlende Personenanker, Dokument-/Seitenwechsel,
Geometrieinkompatibilität, Nachweisgrenzen, Cross-Row-Isolation, HTML-Escaping,
unveränderte Bewertungsdateien, Crops und kombinierte Filter ab. Die konkreten
Testzahlen stehen im aktuellen Eintrag der `AGENTEN_UEBERGABE.md`.
Die lokalen Analyseseiten wurden gegen JSON-/CSV-Metriken abgeglichen;
korrekt + falsch + fehlend bleibt jeweils 72. Historische Dateien und Referenz
sind unverändert. Ein grafischer Screenshot konnte wegen eines fehlenden
Computer-Use-Node-Laufzeitpfads nicht erstellt werden; keine grafische
Sichtabnahme behauptet. Die Filterlogik wurde mit lokalem Node ausgeführt.

Handschrift-Transkription und belastbare Zeilen-/Spaltenrekonstruktion bleiben
die wesentlichen Grenzen. Doclings native Fortsetzungstabelle und Tesseracts
stark abweichende Handschriftlesungen werden hier nicht durch erfundene Rollen
oder Referenzkorrekturen ersetzt. Mehr korrekte Handschriftinformationen für
OCR-LLM/Docling sind mit diesen Änderungen **nicht nachgewiesen**. Nächste
sinnvolle Untersuchung: unabhängige Referenzlokalisierung und weitere reale,
separat gehaltene Entwicklungs-/Testdokumente für Erkennungsvarianten.
