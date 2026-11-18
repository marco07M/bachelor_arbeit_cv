# Ursachen fehlender Felder und unabhängige Dokumentprüfung

Stand: 17.11.2026. Neue wissenschaftliche Vergleiche enthalten
`missing_fields.html` („Ursachen fehlender Felder“). Die Seite ergänzt die
vorhandene Fehleranalyse. Extraktion, Matching, ursprüngliche Ground Truth und
bisherige Metrikformeln bleiben unverändert.

## Zwei getrennte Nachweise

**Dokumentverfügbarkeit** benötigt eine explizite manuelle oder assistierte
Sichtprüfung des unveränderten Original-PDFs mit unabhängig zugeordneter Person.
Fehlende Modellwerte, fehlende OCR-Beobachtungen oder Signaturentscheidungen
erzeugen niemals automatisch ein Verfügbarkeitslabel. Zulässig sind `unchecked`,
`readable`, `unreadable`, `absent` und `uncertain`.

**Verarbeitungskette:** Die bestehenden Funktionen `diagnose_field`, `field_trace`
und das Feld-Audit liefern OCR-/Modellvorschläge, Mappingentscheidungen,
Validierungsverluste und Zuordnungshinweise. Ein belegter Übergang beweist weder
Lesbarkeit des Referenzinhalts noch Richtigkeit eines Modellvorschlags.

Die sieben Ursachenkategorien sind nicht vorhanden, unleserlich, lesbar aber
nicht extrahiert, Vorschlag nicht übernommen, Zuordnungshinweis,
Referenz-/Matchingproblem und unbekannt. Die Beleglage unterscheidet
Originalprüfung, belegten Verarbeitungsschritt, Vermutung und unbekannt.
Gleiche häufige Organisationswerte beweisen keine Zeilenverwechslung.
Niedrige Matchingähnlichkeit allein ist keine unabhängige Fehlerursache; sie
kann selbst durch fehlende Felder entstehen.

Beim direkten `vlm` existiert kein vorgeschaltetes OCR. Zusätzliche Positions-OCR
ist nur ein Hilfsbeleg. Docling, Paddle-OCR/LLM, Tesseract/LLM und hybride
Verfahren behalten ihre jeweils gespeicherte Verarbeitungskette.

## Annotation und Übernahme

Die Seite filtert nach Verfahren, Dokument, Feldtyp, GT-Schriftart, Verfügbarkeit
und Ursache. Standardmäßig sind nur fehlende Feldbeiträge sichtbar; der Schalter
erlaubt alle erwarteten Felder einschließlich korrekter Werte.
„Original prüfen / annotieren“ öffnet die getrennte Originalprüfung.

Geprüfte Labels benötigen verifizierte Originaldatei und Seite, unabhängige
Personenzuordnung, Bestätigung der Unabhängigkeit von Modellausgaben, Prüfer,
ISO-Prüfdatum, Prüfmethode, Personenanker und Befundnotiz. `readable` benötigt
eine unabhängige Transkription. `absent` benötigt die bestätigte Prüfung aller
Originalseiten sämtlicher PDFs des Referenzkurses, nicht nur der Modellseiten.
Optionale Ausschnitte verwenden normierte Originalkoordinaten `x0,y0,x1,y1`.
Modellkoordinaten werden nicht als unabhängige Feldlokalisierung ausgegeben.

Entwürfe bleiben lokal im Browser und können als JSON exportiert/importiert
werden. Sie verändern **keine** gespeicherten Scores. Nach Export aus `software/`:

```powershell
.\.venv\Scripts\python.exe testframework/main.py analyze `
  --report "testframework/ergebnisse/DEIN_VERGLEICH" `
  --output "testframework/ergebnisse/NEUE_DOKUMENTPRUEFUNG" `
  --document-annotations "data/dokumentpruefung.json"
```

Python validiert die Annotation verbindlich und erzeugt einen neuen Bericht.
Vorlage, aktive Annotation, Feldprotokoll, CSV und Prüfungen stehen unter
`missing_fields/`. Referenzsnapshot und PDF-Prüfsummen binden die Annotation;
fremde Datenbasen und doppelte/ungültige Schlüssel werden abgewiesen.
Ein Feld wird einmal annotiert und für alle Verfahren wiederverwendet.
Wiederholte Methodenzeilen sind keine unabhängigen Stichproben.

`original_documents` im JSON ordnet PDF-SHA-256 einem lokalen Pfad zu. Das
unterstützt verschobene Archivdateien; die Byte-Prüfsumme muss weiterhin stimmen.
Ein gleicher Dateiname genügt nicht. Netzwerkpfade werden nicht geöffnet.
Alte Laufbilder ersetzen kein Original. Die vollständige Datenstruktur steht in
`missing_fields/annotations.template.json`. Prüfmethoden sind
`manual_pdf_review`, `assistant_visual_pdf_review` und `independent_document_gt`.

## Zusätzliche Qualitätswerte und Nenner

Die bisherigen globalen Werte bleiben erhalten. Ungeprüfte und unklare Felder
bleiben darin vollständig enthalten. Die zusätzliche **bedingte Dokumentteilmenge**
enthält nur unabhängig lesbar bestätigte Werte, die nach der vorhandenen
Normalisierung mit der Referenz übereinstimmen. Bestehende `field_counts` werden
summiert und mit `scores` ausgewertet: keine zweite Feldbewertung, kein Matching.

- `R_doc` wird sichtbar ausgewiesen; exakt + falsch + fehlend partitioniert ihn.
- Exact Recall/F1 und Coverage verwenden diese vorhandenen Teilmengenzähler.
- Levenshtein bleibt der Mittelwert der nichtleeren zugeordneten Werte mit
  separatem Nenner `D`. Fehlende Werte reduzieren die Ähnlichkeit nicht.
- Ohne geeignete Felder sind die bedingten Kennzahlen nicht definiert.
- Zusätzliche Ausgaben bleiben im globalen P/FP/F1. Teilmengen-Precision/F1
  gilt ausschließlich für GT-Paare und ist keine neue Gesamtnote.
- Lesbare abweichende Originalwerte sind separat als Referenzabweichungen
  markiert. Auch gewählte Normalisierung, etwa führende ID-Nullen, kann relevant
  sein. Eine sachlich falsche Referenz wird daraus nicht automatisch abgeleitet.
- Für belegte Abwesenheit/Unleserlichkeit werden die bisherigen erwarteten,
  exakten, falschen und fehlenden Beiträge zusätzlich ausgewiesen.

Eine gezielt ausgewählte Teilprüfung ist nicht repräsentativ. Höhere
Teilbereichsscores sind keine „korrigierte Gesamtqualität“ und kein Kausaleffekt
für ungeprüfte Felder. Einzelne assistierte Sichturteile sind keine unabhängig
doppelt annotierte Dokument-Ground-Truth. Autor und Prüfmethode sind sichtbar.

## Nachweis am vorhandenen Datenbestand

Ausgangsbasis `20261117T083640Z-316aced8`: fünf Verfahren, zehn Original-PDFs /
zwanzig Seiten, 155 Referenzpersonen und 620 erwartete Felder je Verfahren.
Zwei PDFs wurden teilweise unabhängig von Feldvorhersagen visuell geprüft:
99 lesbare Felder, davon 13 abweichend von der Referenz, sowie 9 leere
Personalnummernfelder. Ein Zeichenfolgenabschluss bleibt unklar, 511 Felder
ungeprüft. Die geeignete lesbare Referenzteilmenge enthält damit 86 Felder.

Der ältere Docling-Lauf umfasst nur ein PDF. Die exakt passende Archivkopie
liegt unter `software/data/structure-real-20261102/pdfs/140829.pdf`.
Beide Archivseiten wurden zusätzlich geprüft. Der alte Referenzsnapshot hat
eine andere Zeilenreihenfolge: 16 von 18 Zeilenpositionen unterscheiden sich.
Die unabhängigen Sichtbefunde wurden deshalb nach eindeutiger Kombination aus
Kurs, Vollname und ID separat an die alten Referenzzeilen und die Archivprüfsumme
gebunden, nicht anhand derselben Zeilennummer kopiert. Die Originalreferenzen
wurden nicht geändert. Der alte Stand enthält keine Schriftartkennzeichnung;
fehlende Labels bleiben nicht klassifiziert.

Ausgaben:

- `testframework/ergebnisse/ursachen-fehlender-felder-20261117-v4/`
- `testframework/ergebnisse/ursachen-fehlender-felder-docling-20261117-v3/`

Docling wird nicht mit dem Zehn-Dokument-Vergleich gepoolt. Bisherige globale
Werte bleiben unverändert; beim alten v5-Bericht kommen lediglich bereits im
Framework vorhandene v9-Diagnosekennzahlen hinzu. Aggregierte Nachweise und
Sichtprotokolle stehen privat unter `data/document-causes-20261117/`.
