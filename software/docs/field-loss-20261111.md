# Ursachenprüfung fehlender Personalnummern und Organisation

Nachfolgende Reparatur desselben Tages: Die automatische Vorbereitung besitzt
jetzt einen OCR-Vierlagen-Fallback und richtet die zwanzig Entwicklungsseiten
korrekt aus. Dafür genügt der normale Fünferstarter ohne manuelles Manifest.
[Aktueller Ablauf und Nachweise](automatic-orientation.md). Die untenstehende
Ursachenprüfung und das manuelle Korrekturmanifest bleiben historische Nachweise.

Stand: 11.11.2026. Grundlage ist der gespeicherte Fünferlauf
`runs/20261111T091101Z-59c4b71d`, Vergleich
`testframework/ergebnisse/20261111T110330Z-09f5d83e`: zehn PDFs, zwanzig Seiten,
155 Schulungsreferenzpersonen und 620 bewertbare Referenzfelder je Verfahren.
Docling war in diesem Lauf nicht ausgewählt; dafür wurde der historische Vergleich
`20261110T123112Z-b454d615` separat geprüft. Er ist kein Docling-Nachweis über die
neuen zehn PDFs. Referenzwerte werden ausschließlich nach der Extraktion verwendet.

## Nachgewiesene Befunde

| Befund | Beleg | Aussage und Grenze |
|---|---|---|
| Seitliche gemeinsame Laufbilder | Visuelle Kontrolle aller zwanzig tatsächlichen Laufbilder: zwölf seitlich. Neunzehn OSD-Prüfhinweise, sieben OSD-Fehler, nur eine Entscheidung über der aktiven Konfidenzschwelle. | Die gemeinsame Vorbereitung garantiert hier keine richtige Orientierung. Eine dadurch verursachte einzelne falsche OCR-Zeichenfolge ist damit noch nicht bewiesen. |
| Gemeinsame Eingangsbilder | Alle hundert Methode-/Seitenkombinationen haben denselben gespeicherten Bildhash wie die jeweilige Laufseite; zwanzig gemeinsame Seitenidentitäten. | Kein Nachweis einer zusätzlichen abweichenden Eingangsrotation nur eines der fünf Verfahren. Interne Skalierung und OCR-Vorverarbeitung bleiben verschieden. |
| Englische ID-Überschrift nicht erkannt | `header_fields('User')` lieferte keine Rolle, `User Name` nur Nachname. Im Dokument `4fb46b5e…`, Seite 1, steht sichtbar User/User Name/Department. Beide Bildverfahren hatten jeweils neun gelesene ID-Zellen, aber keine zugeordnete ID-Spalte. | Konkreter Parserfehler. Nach Korrektur werden dieselben 18 wörtlichen ID-Zellen einschließlich führender Nullen erhalten, ohne neue Modellinferenz. Kein neu gemessener Gesamtqualitätsgewinn. |
| Falscher Umfang der VLM-Überschriften | Antworten enthalten Kursmetadaten wie Standort/Kontakt und Formularanweisungen im selben Headerarray wie Teilnehmerfelder; andere Antworten verwenden Teilnehmerwerte als Überschriften. | Der bisherige Auftrag „alle Tabellenüberschriften“ grenzte die Teilnehmertabelle gegenüber weiteren Tabellen nicht eindeutig ab. Teilnehmerwerte als Überschriften verletzen bereits den bisherigen Vertrag. |
| Nicht ausgerichtete Antwortzellen | Beispielsweise `0e9bc146…`, Seite 1, OCR-VLM: Zahl der Zellen passt nicht zur gespeicherten Headerliste. | Die Zuordnung blockiert Werte bewusst, statt benachbarte Zellen zu verschieben. Rohzellen bleiben erhalten. Die richtige Zuordnung aller Zellen ist dadurch nicht nachgewiesen. |
| Kopflose Folgeseiten | VLM-Aufrufe erhielten bislang keinen Identitätsspaltenzustand. Auf mehreren Folgeseiten werden Datenzeilen als Header zurückgegeben. OCR-/Paddle-/Docling-Pfade besitzen bereits eigene Strukturkontexte. | Fehlender VLM-Kontext und falsche Modellstruktur sind getrennte Probleme. Ein Kontext darf eine falsche oder widersprüchliche Antwortstruktur nicht stillschweigend reparieren. |
| Ausgabebegrenzung | Vier direkte VLM- und fünf OCR-VLM-Seiten erreichen die gespeicherte Grenze von 8.192 Tokens; Antworten sind abgeschnitten. | Neun vollständige Seitenausfälle an der Antwort-/Formatstufe. Keine eindeutige einzelne Teilnehmerlokalisierung aus ungepaarten Kursreferenzen. Budget wurde nicht pauschal erhöht. |
| Verworfenes Modellmaterial | Sieben ID- und dreizehn Organisationsvorschläge bei Tesseract-LLM, neun ID-Vorschläge bei Paddle-LLM werden bei der Belegprüfung entfernt. | Keiner dieser 29 verknüpften Vorschläge stimmt mit der eingefrorenen Referenz nach ihrer Normalisierung überein. Kein Nachweis, dass hier korrekte Referenzwerte durch zu strenge Regeln verloren gehen. |
| Angaben fehlen im Formular selbst | Das gesichtete Formular `904e5b2f…` hat Name/Vorname, Geburtstag und Unterschrift, aber keine Teilnehmer-ID-/Organisationsspalte. | Bekannte Werte einer Schulungs-/Stammdatenreferenz sind damit nicht automatisch sichtbare PDF-Ground-Truth. Referenzprüfung erforderlich; keine automatische Referenzänderung. |
| Regelbaseline ohne Personen | Der Lauf liefert null strukturierte Regelpersonen. Die Baseline verlangt ausreichende passende Überschriften; die aktuellen Vorlagen verwenden insbesondere kombinierte Namensspalten und abweichende Bezeichnungen. | Eine fehlende Zuordnung ist kein Beweis fehlender OCR-Beobachtungen. Keine neue namensratende Regel eingeführt. |

Die tatsächlichen OCR-Ledger bewahren auch niedrige oder unbekannte Engine-Scores.
Es wurde kein globaler Confidence-Filter nachgewiesen, der alle ID-/Organisationswerte
löscht. Modellvorschläge können als Teilstring irgendwo in einer Quellzeile vorkommen
und trotzdem weder vollständiger Zelltext noch der richtigen Spalte zugeordnet sein.
Deshalb wurde die vorhandene Literal-/Positionsprüfung nicht gelockert.

Die visuellen Namen-/Referenzpaarungen bleiben referenzgestützt. Ein lokal
nachgewiesener Verarbeitungsschritt bestätigt weder die unabhängige Identität
noch automatisch die Richtigkeit der OCR oder der Schulungsreferenz.

## Nachvollziehbare Feldfälle

Lokale Fallauswahl mit tatsächlichen Referenz-, Modell- und Endwerten:
`data/field-loss-20261111/cases.json` und `cases.csv`. Sie enthält acht Fälle:

| Fall | Lokalisierung | Belegter Übergang |
|---|---|---|
| `english_user` | `4fb46b5e…`, Seite 1, VLM, Personalnummer | Gelesene physische Zelle → gespeicherte ID-Spalte unbekannt → finale ID null |
| `hybrid_alignment` | `0e9bc146…`, Seite 1, OCR-VLM, Organisation | Modellzellen → ungleiche Zellen-/Headerzahl → keine Feldzuordnung |
| `headerless_data_as_headers` | `6b49bb50…`, Seite 2, OCR-VLM, Personalnummer | Modell liefert Teilnehmerdaten im Headerarray → keine belegte Headerrolle → ID null |
| `literal_id_rejection` | `a535d8f3…`, Seite 2, Paddle-LLM, Personalnummer | Modellvorschlag → gespeicherte Literalvalidierung entfernt ihn → Feld failed |
| `literal_org_rejection` | `a535d8f3…`, Seite 2, Tesseract-LLM, Organisation | Modellvorschlag → belegte Feldablehnung → Feld failed; nicht alle Parserzwischenstände historisch gespeichert |
| `no_document_id_column` | `904e5b2f…`, Seite 1, VLM | Im Original keine Teilnehmer-ID-Spalte; aus externer Referenz keine Bildinformation ergänzen |
| `no_document_org_column` | dasselbe Formular, Organisation | Im Original keine entsprechende Teilnehmer-Organisationsspalte |
| `historical_docling` | gespeicherter früherer Docling-Fall | Native Zell-/Mapperbelege bleiben getrennt von einem Modellaufruf; fehlende unabhängige Lokalisierung wird als unbekannt markiert |

Alle weiteren Feldfälle bleiben ebenfalls im vorhandenen Fehlerbericht enthalten.
Ungepaarte Schulungsreferenzen werden keiner geratenen Seite zugeordnet.
Lokale Personen-/Bild-/Modellartefakte bleiben ignoriert; diese Dokumentation und
die Übergabe enthalten ausschließlich interne Kennungen und aggregierte Zahlen.

## Gezielte Änderungen

1. **Headerrollen:** exakt User als Personalnummer, User Name/Username als
   kombinierte Namensspalte; Benutzer/Benutzername/Kurzzeichen bleiben getrennt.
   Keine Erkennung der Feldrolle aus dem Format eines Teilnehmerwerts.
2. **Kontextfehler:** der reproduzierte `NoneType.get`-Absturz in `column_context`
   bei fehlender alter und vorhandener neuer Geometrie ist abgefangen. Dieser
   Codefehler ist reproduziert, aber nicht als Ursache eines konkreten historischen
   Feldverlusts nachgewiesen.
3. **VLM-Fortsetzung:** vorhandenes `column_context.resolve` auch für VLM verwenden.
   Übernahme nur innerhalb derselben PDF, von früherer Seite, bei kompatiblem
   gemessenem Raster und gleicher vollständiger Spaltenzahl. Neue sichtbare Header
   gelten vorrangig. Falsche Datenheader, ungleiche Zellzahlen, fehlende Geometrie,
   geänderte Struktur, andere PDFs und rückwärts laufende Seiten bleiben gesperrt.
   Der Zustand enthält nur Rollen/Positionen, keine Teilnehmerwerte; Resume kann
   passende gespeicherte Strukturzustände wiederherstellen. Tiling erbt keinen
   ungeprüften Gesamtseitenkontext.
4. **Prompt-/Schemavertrag:** Familie `participant-json-v26-roster-header-scope`
   präzisiert ausschließlich die Teilnehmertabelle und null-Header auf kopflosen
   Fortsetzungen; Metadaten, Fußzeilen und Teilnehmerwerte gehören nicht in die
   Headerliste. Die Feldtypen und Schnittstellen bleiben unverändert. VLM und
   OCR-VLM teilen weiterhin Systemprompt und Schema. v25 ist vorab vollständig
   mit Hashes in `docs/prompt-history/pre-field-loss-20261111.json` archiviert.
   Keine Promptvariantenstudie und keine behauptete Leistungssteigerung.
5. **Ausrichtungsprotokoll:** neue Vorbereitungen speichern OSD-Vorschlag,
   Schwelle, Entscheidung und tatsächliche Zusatzrotation getrennt. Ein alter
   nicht gespeicherter Vorschlag wird nicht aus einer Neumessung zurückdatiert.
   Schwelle und automatische Rotationslogik bleiben unverändert.
6. **Bestehender Starter:** `--manifest` reicht ein geprüftes Seitenmanifest an
   den vorhandenen Extraktionsrunner weiter. Bestehende Eingabe-/Bildhash- und
   Konfigurationsprüfungen bleiben aktiv. Referenzwerte gelangen nicht hinein.
7. **Fehlerbericht:** Feldketten, gespeicherte Modellinputs/Hashes, Vor-/Nach-
   Validierungsstände, originale PDF-Verknüpfung, Ausrichtung, Bildhashabgleich,
   Spaltenkontext und Tokenlimit-Ereignisse ergänzt. Gespeicherte VLM-Zuordnungs-
   ablehnungen werden ausdrücklich diagnostiziert, auch nach dem Headerfix anhand
   ihrer historischen Entscheidung. Fehlende Felder verwenden die vollständig
   belegte Quellzeile statt nur der engeren Namensbox. Unbekannte Übergaben bleiben
   unbekannt. Reine deterministische Mapper werden nicht als LLM ausgegeben.

## Ausrichtungsprüfung und erneuter Start

Der reale CPU-OSD-Probelauf bestätigt sieben Fehler und nur eine ausreichend
sichere Entscheidung. Ein dichter synthetischer Drucktext wird in allen vier
Orientierungen korrekt erkannt (Konfidenzen 12,36–18,47). Dies prüft den technischen
Rotationspfad, belegt aber keine zuverlässige OSD-Erkennung kleiner, gemischter
oder seitlicher realer Tabellen. Keine zusätzliche LLM-/VLM-Inferenz im Audit.

Für **genau die gesichteten zehn PDFs** ist ein manuell geprüftes Manifest
erstellt, gegen unveränderte Eingaben/Bilder validiert und als korrigierte
Kontaktansicht visuell geprüft. Originale und gespeicherte Laufbilder bleiben erhalten.
Ein neuer vollständiger Modelllauf wurde damit noch nicht ausgeführt.

Aus `software/`, falls diese Dokumente erneut als Entwicklungsdaten verarbeitet werden:

```powershell
.\start_testframework_5.cmd --manifest data/field-loss-20261111/curated-manifest.json
```

Dieser Befehl führt Modelle neu aus; er wurde im Audit nicht gestartet. Bei
veränderten Eingaben muss ein neues passendes Manifest erstellt und geprüft werden.
Die Seitenkorrekturen stehen in `manual_orientation_review.csv`; für andere PDFs
werden keine Winkel geraten. Die hier zur Fehleranalyse gesichteten zehn PDFs
sind beim späteren unabhängigen Studienaufbau als vorbenutzte Entwicklungsdaten
zu berücksichtigen.

## Prüfung und offene Grenzen

Neue Berichte ohne neue Inferenz:

- `testframework/ergebnisse/field-loss-20261111-v2/extraction_errors.html`
- `data/field-loss-20261111/docling-report-v2/extraction_errors.html`

Die Berichte bewerten weiterhin die historischen Extraktionen. Neue Diagnosen
ändern die Ursachenklassifizierung, nicht die Feldscores. Aggregierter Nachweis
unter `data/field-loss-20261111/validation.json`; 1.762 historische Dateien sind
unverändert, ebenso 4.434 numerische Standardwerte. Abschließend bestanden
772 lokale Tests in 77,06 s und 48 API-Tests in 9,85 s; Ruff ohne Befund.
31 neue Unit-/Regressionstests prüfen Headerrollen, sichere/gesperrte
Fortsetzungen, fehlende Geometrie, Resume, 0/90/180/270-Grad-Weitergabe, explizite
Korrekturmanifeste, Feldketten, Rollenfilterindizes, unbekannte Zwischenbelege,
HTML-Escaping und unveränderte Feldmetriken.

Die neue VLM-Fortsetzung bleibt bei den untersuchten Rohantworten vielfach bewusst
gesperrt: gemessenes Gesamtraster und Modell-Headerliste passen nicht zusammen.
Die Promptpräzisierung ist technisch geprüft, nicht anhand neuer neuronaler
Ausgaben als besser belegt. Zellen werden nicht geraten oder aus Referenzen ergänzt.
Unzureichende OSD-Sicherheit, beschädigte Antwortstrukturen, abgeschnittene
Generierungen, die Vorlagenbindung der Regelbaseline und die Eignung der Referenz
bleiben eigenständige Aufgaben. Vor einem unabhängigen Modellvergleich sind sie
mit eingefrorenen Entwicklungsregeln und danach getrennten Daten zu behandeln.
