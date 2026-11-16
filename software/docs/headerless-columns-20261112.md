# Feldverluste auf Folgeseiten ohne Tabellenüberschriften

Stand: 12.11.2026. Maßgeblich sind der tatsächliche Quelllauf
`runs/20261112T075916Z-2ed08591` und Vergleich
`testframework/ergebnisse/20261112T082436Z-ffc71ce9`.
Untersucht wurden drei bereits verwendete Entwicklungs-PDFs mit sechs Seiten;
keine unabhängigen Finaltestdaten. Originale, Referenz und Bewertungsregeln
bleiben erhalten. Die Ursache betrifft kopflose Folgeseiten, nicht grundsätzlich
Handschrift oder eine leere Personalnummer.

## Nachgewiesene Verluststellen

| Stufe | Befund | Folge |
|---|---|---|
| Gemeinsames Seitenbild | Alle sechs Bilder entsprechen der zuvor geprüften automatischen Ausrichtung. | In diesem Lauf keine erneute Erklärung allein durch seitliche Bilder. |
| Gemessene Geometrie → VLM-Kontext | Der gemeinsame Detektor ergänzte Seitenränder als virtuelle OCR-Spalten. Die VLM-Antwort zählt dagegen physische Tabellenzellen. | Eine tatsächlich achtspaltige Tabelle erschien als zehnspaltig; gespeicherter VLM-Kontext hatte deshalb keine verwendbare Geometrie. |
| Kontext → VLM-Eingabe | Der Parser verwaltete frühere Spaltenrollen, übergab sie dem Modell aber noch nicht vor der Generierung. | Eine kopflose Seite musste ihre Struktur erneut erkennen. |
| Modellantwort → Feldzuordnung | Auf Folgeseiten wurden Zellen der ersten Person als `identity_headers` ausgegeben. | Trotz vorhandener Rohzellen wurden ID und Organisation nicht zugeordnet. |
| Rohzellen → tatsächlicher Beleg | Einige angebliche Organisationszellen enthalten tatsächlich Signaturtext; andere Codes sind falsch gelesen. | Bloßes Wiederzuordnen aller Zellen wäre keine sichere Reparatur. |
| Direktes VLM → gültige Antwort | Beide historischen Folgeseiten erreichten 8.192 Ausgabetokens. | Ganze Seiten gingen wegen ungültigem JSON verloren, unabhängig von einzelnen Spalten. |
| OCR+LLM | Im untersuchten Beispiel besteht bereits ein geerbtes Mapping; manche Werte fehlen schon im OCR-/Modellinput oder in der Modellantwort. Bei einer anderen Seite fehlt eine erforderliche Rastergrenze. | Kein pauschaler nachgelagerter Feldverlust allein wegen leerer ID nachgewiesen; keine unsichere Ergänzungsregel aktiviert. |

Eine leere ID-Zelle deaktiviert die Organisationsspalte nicht. Diese Unabhängigkeit
war bereits implementiert und wird weiterhin getestet. Auf der gemischten
Folgeseite bleiben drei vom Modell als leer gelesene ID-Zellen ausdrücklich leer.

## Implementierte Reparatur

- `column_context.image_boundaries` kann ausdrücklich **nur gemessene**
  Tabellenlinien liefern. Die bisherige OCR-Ansicht mit Seitenrändern bleibt
  der Standard; nur die visuelle Zuordnung verwendet die physische Ansicht.
- VLM-Kontext prüft das gemessene Präfix aller Zielspalten. Eine kombinierte
  Namensspalte bleibt eine physische Zelle. Abweichend gezählte hintere
  Signaturspalten dürfen nicht allein die Textspalten sperren; fehlende innere
  Grenzen, unbekannte Zusatzspalten und widersprüchliche Textspalten bleiben
  Sperrgründe. Die bestehende Kantentoleranz von 0,035 bleibt unverändert.
- Die vorhandene generische Überschriftennormalisierung wird auch für die
  visuellen Rollen genutzt, einschließlich eindeutiger OCR-Schreibvarianten.
  Teilnehmerwerte werden nicht korrigiert oder anhand ihres Formats klassifiziert.
- Ein geometrisch bestätigter vorheriger Kontext wird vor dem VLM-Aufruf als
  `DOCUMENT_COLUMN_CONTEXT` übergeben: eine Liste physischer Spalten mit
  gruppierten Feldrollen, Positionen, tatsächlicher Spaltenzahl und null-Platzhaltern
  für fehlende Überschriften. Keine früheren Teilnehmerwerte oder Referenzdaten.
  Echte aktuelle Überschriften haben weiterhin Vorrang.
- Ein exaktes Echo der ersten aktuellen benannten Person kann als falscher
  Überschriftenblock erkannt werden. **Die automatische Feldreparatur dieses
  Vertragsfehlers braucht zusätzlich eine eindeutige aktuelle native OCR-Zeile**:
  literaler vollständiger Name oder ID, keine Organisation als Identitätsanker.
  Mehrdeutige Anker werden verworfen. Eine aktuelle eindeutige OCR-Zelle muss
  vollständig in der gemessenen Zielspalte liegen. Dafür wird die bestehende
  `complete_observed_cells`-Funktion wiederverwendet. Werte bleiben prüfpflichtig.
- Diese Zusatzbelege liegen im Hybridverfahren bereits vor. Das direkte VLM
  erhält keine neue separate OCR-Extraktion; ein falscher Datenheader begründet
  dort allein keine automatische Feldfreigabe. Korrekte null-Header können
  dagegen weiterhin den geprüften Strukturkontext nutzen.
- `echo_corroboration` speichert aktuelle Zeilen-/Zellbelege. Die Feldkette zeigt
  ursprüngliche Modellzelle und `observed_cell_completion` getrennt. Ablehnungen
  und deren Gründe bleiben sichtbar. Keine Signatur wird allein aus ihrer
  Position in einer fehlerhaften Modellliste zur Organisation erklärt.

Kontextkennung: `document-column-context-v3-visual-text-prefix`. Die feste
Promptfamilie v26 und JSON-Schemas bleiben unverändert. Geändert wird der
dynamische Strukturinput; tatsächliche Nachrichten, Hashes und Kontextversion
werden gespeichert. Der normale Runner berücksichtigt Codeänderungen in seiner
Laufidentität und lehnt ein unverändertes Resume alter Codezustände ab.

## Gegenchecks, verworfene Schritte und Grenzen

1. **Ungeprüfter Replay verworfen:** 17 wiederzugeordnete Hybridfelder ergaben
   fünf zusätzliche exakte, aber zwölf zusätzliche falsche Werte. Darunter waren
   Signaturtranskripte in vermeintlichen Organisationszellen. Diese Freigabe ist
   nicht die aktive Endfassung.
2. **OCR+LLM-Ergänzungsprobe zurückgenommen:** eine zusätzliche ID war schon als
   OCR-Text vorhanden, aber gegenüber der Referenz falsch. Kein exakter Gewinn,
   ein zusätzlicher Fehler. Tesseract-Zuordnung und bestehender Paddle-Pfad
   bleiben deshalb gegenüber dem Ausgangsstand unverändert.
3. **Erste VLM-Funktionsprobe verworfen:** ein gültiges JSON erfand getrennte
   Vor-/Nachnamensspalten. Die Strukturübergabe wurde physisch gruppiert und eine
   Sperre gegen widersprechende gemessene Raster ergänzt. Dieser Zwischenstand
   ist kein Qualitätsnachweis.
4. **Finale VLM-Funktionsprobe:** gleiche Seite, Gewichte, Systemprompt samt Schema,
   Bild und Grenzen; 3.971 Input- und 101 Outputtokens. Gültiges JSON nach etwa
   4,4 Sekunden, aber **keine Teilnehmer**. Die Erkennungsqualität verbessert sich
   auf dieser Seite damit nicht. Es gibt keine weitere Optimierungsserie.

Insgesamt zwei neue lokale VLM-Seitenaufrufe und zwei unveränderte Warm-ups;
keine neue OCR, Textmodellinferenz, API-Aufrufe oder Downloads. Die nachfolgende
native Belegprüfung wurde auf eingefrorenen Antworten geprüft. Generierungs-
und Validierungscodehashes sind getrennt gespeichert; der tatsächlich gesendete
finale Strukturinput wird gegen die aktuelle Konstruktion auf Gleichheit geprüft.

## Gemessene Endfassung

Gleiche 46 Kursreferenzpersonen und 184 Felder je Verfahren. Gleicher Matcher
und gleicher eingefrorener Referenzsnapshot. Standardzähler können
referenzgestützte Namenstausche enthalten; beim Hybrid bleiben es vier.

| Verfahren | Exakt vorher → nachher | Falsch vorher → nachher | Fehlend vorher → nachher | Zusätzliche Felder |
|---|---:|---:|---:|---:|
| Regeln | 0 → 0 | 0 → 0 | 184 → 184 | 0 → 0 |
| Tesseract + LLM | 74 → 74 | 17 → 17 | 93 → 93 | 4 → 4 |
| Paddle + LLM | 96 → 96 | 30 → 30 | 58 → 58 | 0 → 0 |
| Direktes VLM | 67 → 67 | 29 → 29 | 88 → 88 | 0 → 0 |
| OCR + VLM | **92 → 96** | **28 → 29** | **64 → 59** | **4 → 4** |

Der finale Hybridpfad gewinnt vier exakte Felder, enthält aber auch einen
zusätzlichen falschen Wert. Fünf Felder werden anhand aktueller nativer Zellen
wiederhergestellt; andere unsichere Modellzellen bleiben unbekannt. Die Zahl
der ausgegebenen Teilnehmer bleibt unverändert. Keine Behauptung allgemeiner
Halluzinationsfreiheit oder bestätigter Personenidentität.

Beim direkten VLM sinkt die Zahl formal fehlgeschlagener Seiten von zwei auf eins,
ohne zusätzliche Teilnehmer oder korrekte Felder. Ein gültiges Ausgabeformat ist
kein Erkennungserfolg. Auf der anderen kopflosen Folgeseite fehlt eine benötigte
Rasterlinie; dort bleibt die Strukturübernahme aus gutem Grund gesperrt.

## Tests und Artefakte

Endgültig **881 lokale Tests bestanden (100,75 s)** und **48 API-Tests (10,00 s)**;
Ruff ohne Befund. Neue Regressionen in `test_headerless_visual_context.py`,
ein bestehender Geometriemock an die zusätzliche Option angepasst. Geprüft sind
unter anderem Seitenränder, wiederholte Signaturspalten, gruppierte Namen,
überschriftslose Fortsetzung, leere IDs, echte neue Überschriften, falsche PDFs/
Seitenfolge/Geometrie, native Zeilenanker, fehlende Belege und die HTML-Feldkette.

Maßgeblicher lokaler Bericht:
`testframework/ergebnisse/headerless-columns-20261112-verified/report.html`.
Darunter getrennt `frozen-response-replay/` und `after/`. Dies sind ausdrücklich
begrenzte Gegenchecks, keine neuen vollständigen Fünferläufe und keine
Laufzeitstudie. Private Rohbelege und `quality_comparison_verified.json` liegen
unter `data/handwritten-fields-20261112/`. Unsichere Zwischenberichte ohne
`-verified` sind als verworfen gekennzeichnet. 783 historische Dateien bleiben
unverändert. Für andere Layouts und API-Modelle ist kein realer Qualitätsgewinn
nachgewiesen; gemeinsame Implementierung und synthetische API-Tests sind davon
zu unterscheiden.
