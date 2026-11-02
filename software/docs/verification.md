# Verifikationsprotokoll

## Nachtrag: Originalreihenfolge der Anwesenheitsliste, 02.11.2026

Darstellung und Exporte verwenden Eingabe-PDF, numerische Seite und den
ursprünglichen Ausgabeindex. Referenzzeilen und Namen sind keine Sortierschlüssel.
Dies gilt für Hauptbericht, Teilnehmer-Excel, neuen und älteren Referenzabgleich,
CSV, Detail-/Namenszuordnung und Hybrid-Feldvergleich. Reine Referenzfälle
folgen den tatsächlichen Ausgaben und erhalten in den Details einen eigenen Abschnitt.

Die Ende-zu-Ende-Tests kehren die Referenzliste um und speichern PDF-Seiten
absichtlich durcheinander. Sie prüfen mehrere PDFs mit übergreifenden Kursen,
zusätzliche Ausgaben, fehlende Referenzpersonen, HTML, CSV und Excel. Kennzahlen
und Quellvorhersagen bleiben unverändert. Abgeschlossen: **571 lokale Volltests**
in 93,03 Sekunden, **48 API-Tests** in 9,81 Sekunden; Ruff ohne Befund.

Zusätzlich wurden vorhandene reale Ausgaben gegen ihre eingefrorenen Referenzen
neu dargestellt, ohne Modellaufrufe. Neue Berichte:
`testframework/ergebnisse/source-order-20261102/opened-report/report.html` und
`testframework/ergebnisse/source-order-20261102/latest-userids/report.html`.
`validation.json` im übergeordneten Ordner bestätigt identische Kennzahlen,
unveränderte Originalartefakte und exakte Quellenreihenfolge aller ausgegebenen
Teilnehmer. Die historische Auswertung und die Referenzdateien bleiben erhalten.

## Nachtrag: Nachname zuerst und vollständige Namensgruppen, 02.11.2026

Auf Nutzerwunsch gilt für kombinierte Namenszellen Nachname → sämtliche
Vornamen als Standard. Eindeutige separate Namensüberschriften haben Vorrang.
Ein Komma trennt vollständige Gruppen; Bindestriche und mehrteilige Nachnamen
werden erhalten. Falsch aufgeteilte Kommazellen können vor der strikten
Zellprüfung anhand ihrer unveränderten Quelle neu zugeordnet werden.

Neue Entscheidungsgrundlage `name_order.basis` und `decision_source` im Audit
unterscheiden Beleg und Annahme. Spätere eindeutige Überschriften ersetzen
eine Annahme ohne falschen Konflikt. Unklare unmarkierte Mehrfachnamen bleiben
Prüffälle; die ganze Quelle und unvollständige Personen bleiben erhalten.
Die dokumentweiten Namens- und Zellpromptversionen wurden erhöht. Es entstehen
keine zusätzlichen Modellaufrufe oder Zugriffe auf Referenznamen.

Abschließend bestanden **567 lokale Volltests** in 155,44 Sekunden und
**48 API-Tests** in 14,69 Sekunden; Ruff und `git diff --check` ohne Befund.
Der praktische Lauf `runs/20261102T092453Z-ffe0c48d/` enthält drei unabhängig
vorab verfasste synthetische Personen: Doppelnachname mit drei Vornamen,
mehrteiliges Nachnamenspräfix mit zwei Vornamen sowie einfacher Name ohne Komma.
OCR-LLM und VLM geben alle drei Namensgruppen vollständig richtig aus.
Doclings OCR-Belege enthalten den ersten Namen einschließlich Komma korrekt;
die native Namenszelle enthält stattdessen einen Organisationscode. Damit ist
ein Fehler der Zellzuordnung belegt (`cell_assignment_failed`); die Namensgruppe
bleibt unklar. Eine vorläufige Komma-/Punkt-Vermutung wurde anhand der Rohdaten
verworfen.

Die ursprüngliche Positionsauswertung bleibt unverändert. OCR-Textzeilenboxen
unterschreiten gegenüber ganzen GT-Tabellenzeilen die vertikale IoU-Schwelle;
hier entstehen trotz richtiger Namensstrings keine Zuordnungen. Die ergänzende
Inhaltsprüfung unter `runs/name-groups-20261102/report.html` verwendet dieselben
vorab verfassten Feldwerte ohne GT-Positionslabels und den bestehenden
approximativen Namens-/Organisationsabgleich. Namensfelder exakt: OCR-LLM 6/6,
VLM 6/6, Docling 4/6. Es wurden keine Referenzfelder anhand von Modellantworten
geändert. Dies ist ein Funktionstest, kein allgemeiner Genauigkeitsnachweis auf
realen Teilnehmerlisten und keine unabhängige Identitätsprüfung.

## Nachtrag: Benutzer-Spalte und User IDs, 02.11.2026

Der vom Nutzer geöffnete Vergleich
`testframework/ergebnisse/20261102T074721Z-1c30943c/` basiert auf dem älteren
Lauf `runs/20261102T074109Z-328a26c1/`. „Benutzer“ wird im Header-Mapping bereits
als User ID erkannt. Die VLM-/Hybrid-Antworten nennen diese Spalte jedoch „Nr“;
neun gelesene Zellwerte auf Seite 1 werden deshalb nicht als IDs übernommen.
Die damaligen Textverfahren sind zudem wegen fehlender Gewichte unavailable.
Im späteren praktisch geprüften Paddle-Lauf sind neun IDs vorhanden und alle
neun im konfigurierten, führende Nullen ignorierenden Kursvergleich exakt.

Promptversion `participant-json-v21-visible-benutzer-headings` verlangt von
beiden Bildverfahren die wörtliche Unterscheidung zwischen „Benutzer“,
„Benutzername“ und „Nr“. OCR-LLM erhält dieselbe explizite Feldbedeutung.
Eine Spalte ohne sichtbare Überschrift darf keine erfundene Benutzer-Spalte
ergeben. Der Parser deutet keine unbekannten Spalten anhand ihres Zahlenformats
um und erhält weiterhin führende Nullen.

Die erste Gegenprobe v20 wurde verworfen: Sie liest zwar auf Seite 1 neun IDs,
ordnet auf der Folgeseite aber Kurzzeichen als IDs zu. Ihr gezielt beendeter
Lauf `runs/20261102T084044Z-e1089296/` bleibt erhalten. Der neue v21-Lauf unter
`runs/user-id-validation-20261102-v21/` verwendet nachweislich identische
Laufbild-Hashes und visuelle Modellparameter wie die alte Vergleichsgrundlage.
Beim direkten VLM werden auf Seite 1 neun IDs und auf Seite 2 keine IDs
ausgegeben; dort bleiben die ID-Felder unklar und Kurzzeichen separat erhalten.
Auch der Hybrid-Lauf ist vollständig abgeschlossen. Der Kursreferenzabgleich
ergibt bei neun ausgegebenen IDs **8 korrekte IDs beim VLM und 9 beim Hybrid**,
jeweils gegenüber zuvor null. Der Vergleich ignoriert konfigurationsgemäß
führende Nullen; die Rohwerte bleiben erhalten. Bezogen auf alle 18 Kursreferenzen
sind das 8/18 beziehungsweise 9/18, nicht 100 % dokumentweiter ID-Recall.
Auf Seite 2 bleiben bei beiden Verfahren neun ID-Felder unklar; kein Kurzzeichen
wird als ID ausgegeben. Vorname-, Nachname- und Organisationstreffer bleiben
jeweils gegenüber der alten Auswertung unverändert.

Einstieg mit Zählern/Nennern und geprüften Vergleichsbedingungen:
`runs/user-id-validation-20261102-v21/report.html`. Neuer Modelllauf:
`runs/20261102T084927Z-483e59b1/`. Das ist ein dokumentbezogener Entwicklungsbefund;
der verbleibende VLM-Lesefehler wird nicht anhand der Referenz korrigiert.

Abschließende Regression auf v21: **546 lokale Volltests bestanden** in
165,99 Sekunden, **48 API-Tests bestanden** in 25,06 Sekunden. Die zwei neuen
Integrationstests prüfen gefüllte Benutzer-Spalten für VLM und Hybrid bis zum
Excel-Export, einschließlich führender Nullen und fehlender Zeilennummer.

## Docling/Paddle: praktische Abnahme, 02.11.2026

Die exakten Qwen3-4B-Instruct-2507-Gewichte sind installiert, SHA256-geprüft und
mit echter lokaler CUDA-Inferenz ausgeführt. Vollständig abgeschlossen sind
fünf Docling-Konfigurationsvarianten und vier A/B-Läufe auf synthetischen und
realen Dokumenten. Zusätzlich wurden zwei reale Docling-OCR-Varianten geprüft.
Die Vergleichsbedingungen, Feldmetriken, Ursachen, Laufzeiten und Grenzen stehen
im [Abschlussbericht](structure-optimization.md).

Aktiv ist Docling mit nativen Zellen, ACCURATE und deaktiviertem Cell Matching.
Paddles erweiterte Übergabe bleibt nach gemessener Regression eine gesonderte
Versuchsvariante; das Hauptprofil behält dafür `legacy_v13`. Ein Qualitätsgewinn
auf der realen PDF wurde nicht nachgewiesen. Die vorhandenen 18 Kursreferenzen
ersetzen keine manuell geprüften Seitentranskripte für Handschriftmetriken.

Abschließender Prüfstand: **544 lokale Volltests bestanden** in 163,52 Sekunden;
**48 API-Tests bestanden** auf dem geänderten Kerncode. Ruff, Markdown-Dateiverweise
und `git diff --check` ohne Befund. 22 lokale Pipelineprofile sowie die Excel- und
Testframework-Konfiguration erfolgreich mit den jeweiligen Schemas geladen.
Die tatsächlichen Laufbilder und endgültigen Methodeneinstellungen wurden gegen
die eingefrorenen Ergebnisse geprüft. Die Original-PDF blieb hashgleich erhalten.

Alle folgenden Abschnitte sind historische, datierte Prüfstände. Insbesondere
die dort dokumentierten fehlenden Textgewichte sind seit 02.11.2026 behoben.

## Hauptvergleich: sechs Verfahren, 29.10.2026

Implementiert sind `ocr_raw`, `ocr_llm`, `paddle_llm`, `docling`, `vlm` und
`ocr_vlm` im vorhandenen Runner. Hauptprofil: `configs/benchmark.yaml`.
Installation, Modellrevisionen, Architektur und bekannte Grenzen:
[local-methods.md](local-methods.md).

Automatisierte Prüfung nach der Vereinheitlichung: **509 lokale Tests und
48 Tests des getrennten API-Projekts bestanden**. Ruff und `git diff --check`
sind ohne Befund. Alle 20 YAML-Profile wurden mit ihrem jeweiligen
Konfigurationsschema eingelesen, außerdem das lokale Testframework-Profil.
Geprüft werden unter anderem wechselnde Spalten, verbundene und mehrzeilige
Zellen, unbekannte Namen, fehlende Modelle, identische VLM-Parameter und Bilder,
OCR-Cache-Kosten, Hybrid-Feldübergänge sowie die numerische Gleichwertigkeit der
SDPA-Variante einschließlich kausaler Masken und Ein-Token-Decoding.

Ein tatsächlicher lokaler GPU-Lauf mit unabhängig erzeugter synthetischer PDF
und Referenz liegt unter `runs/20261029T140802Z-2246a68b/`. Die Seite enthält zwei
Personen mit acht Textfeldern. Automatische Ausrichtung wurde für diesen
aufrechten Funktionstest ausgeschaltet; die Ausgabegrenze war bei beiden
VLM-Varianten identisch auf 2048 Token gesetzt. Das reguläre Hauptprofil hat
8192 Token. Es gab keine Modell-Downloads oder externen Inferenzaufrufe.

| Verfahren | Ergebnis dieses Funktionstests |
| --- | --- |
| ocr_raw | OCR erfolgreich; keine Teilnehmerfeldmetrik |
| ocr_llm | unavailable: exakte Instruct-2507-Gewichte fehlen |
| paddle_llm | Paddle tatsächlich ausgeführt; LLM-Zuordnung unavailable wegen derselben fehlenden Gewichte |
| docling | Zwei Teilnehmer, 8/8 Textfelder exakt, ohne Qwen; weiterhin Prüffälle |
| vlm | Zwei Teilnehmer, 8/8 Textfelder exakt |
| ocr_vlm | Zwei Teilnehmer, 4/8 Textfelder exakt; Vor-/Nachnamensrollen vertauscht |

Der Hybrid verbessert dieses Beispiel nicht: vier Namensfelder verschlechtern
sich, kein Feld wird korrigiert. Die Fehler werden ausdrücklich erhalten und
feldweise ausgewiesen. Beide Varianten verwenden nach geprüfter eingefrorener
Konfiguration dieselben Gewichte, Parameter, Seitenbild-Hashes und die gleiche
Grundpromptversion. Gemessene PyTorch-Spitzenbelegung: etwa 8,99 GiB beim VLM
und 9,16 GiB beim Hybrid. Ein vorausgegangener Versuch mit normalem SDPA und
umfangreicher OCR-Serialisierung scheiterte am Speicherlimit; dessen Ergebnisse
bleiben getrennt erhalten. Die kompakte Serialisierung und Repeated-KV-SDPA
wurden anschließend erfolgreich auf der GPU ausgeführt.

Ein zusätzlicher, unabhängig protokollierter CSV-Abgleich desselben Quelllaufs
liegt unter `testframework/ergebnisse/unified-smoke-20261029-2246a68b/`.
Er enthält `hybrid_analysis.html`, acht Feldvergleiche, vier Verschlechterungen
und bestätigte Vergleichsbedingungen. Seine `identity.json` enthält die tatsächlich
verwendeten gemeinsamen Evaluationsmodule mit Dateihashes. Dieser separate
Abgleich wurde nach Abschluss der Implementierung ausgeführt.

Ein lokaler Funktionstest mit der vorhandenen realen PDF (zwei Seiten) liegt
unter `runs/20261029T142016Z-3b7d7722/`: Tesseract erfolgreich, Docling technisch
lesbar, aber **keine zuverlässig zuordenbaren Teilnehmer**. Die Seiten bleiben
`partial`; Rohtext und Tabellen sind erhalten. Das ist keine Qualitätsmessung,
da hierfür keine manuell geprüfte Ground Truth übergeben wurde. Insbesondere
Doclings konservatives Mapping benötigt ausreichend erkannte Überschriften.

Die neuen Text-LLM-Wege konnten wegen fehlender Modellgewichte noch nicht mit
echter Instruct-2507-Inferenz abgenommen werden. Direkter VLM und Hybrid wurden
bei dieser Überarbeitung tatsächlich auf synthetischen Daten ausgeführt; ein
neuer VLM-/Hybrid-Lauf auf den realen Dokumenten steht noch aus. Frühere
Echtläufe bleiben historische Ergebnisse ihrer damaligen Konfiguration.

Während des GPU-Tests war der Laptop im Akkubetrieb, bei ungefähr 140 MHz und
14 W GPU-Leistung unter Last. Die rund 652 Sekunden Gesamtlaufzeit sind deshalb
kein allgemeiner Durchsatznachweis und keine Hochrechnung für 6000 PDFs.
Der kleine synthetische Datensatz belegt ausschließlich Softwarefunktion;
Prompt-/Parameteroptimierung und finale Bewertung benötigen getrennte,
manuell gelabelte Entwicklungs-, Validierungs- und Testdaten.

## Frühere Prüfschritte

Dokumentweite Zuordnung der Vor-/Nachnamensrollen, 29.10.2026:
Die Modellantwort enthält `name_order` mit `given_family`, `family_given` oder
`unknown` und einer dokumentbezogenen Begründung. `generation_schema` verlangt
diese Angabe bei neuen OCR-/VLM-/Zellantworten; die Leseschemas akzeptieren ältere
Antworten ohne sie. Promptversionen: `participant-json-v14-required-document-name-order`
und `ocr-cell-assignment-v9-document-name-order`. Die API verwendet dasselbe
Generationsschema und denselben Nachverarbeitungspfad.

Die erste belegbare Entscheidung wird pro PDF und Verfahren gespeichert und auf
Folgeantworten übertragen. Die Zuordnung vertauscht ausschließlich bereits
beobachtete komplette Namensfelder anhand von OCR-Positionen oder physischen
Zellen; sie erhält Schreibweise, Feldstatus und Bounding-Boxes. Für Zellverfahren
erfolgt die Namenszuordnung schon vor der strikten Feld-/Spaltenprüfung. Spätere
Überschriften können frühere Seiten ohne weitere Inferenz auflösen. Widersprüche
markieren das gesamte Dokument zur Kontrolle. Resume stellt den Kontext wieder
her. Andere PDFs, andere Verfahren und Referenzdaten liefern keine Namenswerte.

Provenienz: `document_name_order` in den Seitenrohdaten, ursprüngliche Modellantwort,
Vorvalidierungsänderungen bei Zellverfahren sowie `document_name_orders.csv`
und eine eigene Tabelle im HTML-Report. Ursprungsseite, Begründung, korrigierte
Namenspaare und Prüffälle sind sichtbar. Es gibt keine zusätzlichen Modellaufrufe.

Automatisierte Abnahme: **434 lokale Volltests und 48 API-Tests bestanden**.
Die insgesamt 18 neuen Fälle prüfen vertauschte und bereits richtige Zeilen, PDF-Grenzen,
zusammengesetzte Namen, leere IDs, Feldpositionen, widersprüchliche Seiten,
spätere Überschriften, alte Antworten, Resume, alle drei Zellwege, den
vollständigen Parser-/Exportablauf und das verpflichtende Generationsschema.
Fehlt die Pflichtangabe in einer neuen Modellantwort trotzdem, bleiben die
gelesenen Namen als Prüffall erhalten. Alte gespeicherte Antworten werden bei
reinen Vergleichen nicht nachträglich umgeordnet.
Der API-Test bestätigt richtig zugeordnete Namen aus absichtlich vertauschten
Modellfeldern bei unverändert zwei Seitenanfragen für zwei PDFs.

Echter lokaler VLM-Funktionstest mit zwei selbst erstellten PDF-Seiten:
`runs/20261029T094637Z-5f57d043/report.html`. Vier Teilnehmer mit 8/8 richtigen
Vor-/Nachnamensfeldern, einschließlich zusammengesetzter Namen. Seite 2 besitzt
keine Spaltenüberschriften und übernimmt `family_given` von Seite 1. Genau zwei
reguläre Modellaufrufe, Laufzeit rund 49,5 Sekunden. Die manuelle Referenz wurde
vor dem Modelllauf erstellt; sie war kein Modelleingang. Audit:
`document_names_validation.json`. Dies ist ein Funktionsnachweis, kein
unabhängiger Qualitätsnachweis auf Unternehmensdaten. Der vorherige Versuch
`20261029T094305Z-c4cdfc42` ist erhalten: Das Modell ließ die damals optionale
Namensentscheidung weg. Deshalb ist die Angabe jetzt im Generationsschema und
im Prompt ausdrücklich verpflichtend.

Kursleiter aus Teilnehmerdaten ausgeschlossen, 29.10.2026:
Alle strukturierten lokalen Verfahren und der gemeinsame API-Runner verwenden
die explizite Rollenangabe `person_role` mit wörtlichem `role_evidence`.
Promptversionen sind `participant-json-v12-attendees-only` und
`ocr-cell-assignment-v8-attendees-only`; bestehende Cacheantworten werden damit
nicht als neue Rollenentscheidungen wiederverwendet. Kursleiter/Trainer/Dozenten
werden vor Teilnehmerexport, Namenszuordnung und anschließender VLM-Signaturprüfung
ausgeschlossen. OCR- und Zellverfahren verlangen einen Rollenbeleg in der eigenen
Quellzeile; getrennte Zeilen, bloße Berufs-/Namenswerte und ungesicherte
Modellvermutungen führen nicht zum Ausschluss. Unbestätigte Kursleiterangaben
werden als unbekannt mit Prüfhinweis erhalten. Der Prüfhinweis `role_unconfirmed`
bleibt auch bei vollständiger Excel-Übereinstimmung im Namensvergleich sichtbar.

Die Seite speichert `excluded_instructors`, die Rohdaten `person_role_filter`
einschließlich ursprünglicher Ausgabeindizes. Der Extraktionsbericht enthält
`excluded_instructors.csv` und einen getrennten Abschnitt. Der Vergleichsreport
weist die Ausschlussanzahl separat aus. Referenzdateien und alte Ergebnisse
werden nicht automatisch angepasst. Reiner OCR-Text bleibt vollständig erhalten.

**414 lokale Tests und 48 Firmen-PC-Tests bestanden.** Insgesamt 21 neue lokale
Fälle prüfen Rollenlabels, leere IDs, Personen mit Nachnamen „Trainer“, fehlende
Belege, Negation, gleiche Namen in unterschiedlichen Zeilen, beide OCR-Parser,
VLM-Zellantworten, die drei Zell-/Layoutverfahren, Legacy-Regeln sowie Ausschluss
vor Signaturprüfung, Export und Excel-Bewertung. Die API-Integration prüft
Kursleiterausschlüsse auf mehreren PDFs bei unveränderter Anzahl API-Anfragen.
Nach Ergänzung der Vergleichsanzeige und der Weitergabe unklarer Rollen sind
weitere 93 lokale und 34 API-Tests erfolgreich. Zwei zusätzliche Fälle prüfen
den Rollen-Prüfhinweis im konservativen und im Best-Fit-Modus bei exaktem
Referenztreffer. Der Firmen-PC-Export enthält das neue gemeinsame Rollenmodul;
alle sechs Export-/Starttests sind ebenfalls erfolgreich.

Echter lokaler CUDA-Test mit selbst erstellter PDF und manuell vorab festgelegter
Referenz: `runs/20261029T091750Z-d68f927a/report.html`. Das VLM erhält beide
Teilnehmer mit 8/8 richtigen Textfeldern und schließt den explizit gekennzeichneten
Kursleiter aus. Das OCR-LLM schließt diesen ebenfalls anhand des Quellbelegs aus,
verliert aber beide Teilnehmer bereits bei der OCR-Feldprüfung wegen falscher
Modell-Zeilenreferenzen. Dieser Fehler bleibt separat in `rejected_rows` sichtbar;
der gelesene Seitentext bleibt als Fallback erhalten. Die Rollenprüfung repariert
keine Feld- oder Zeilenfehler. Der Funktionslauf mit Qwen3-1.7B und Qwen3-VL-4B
dauerte zusammen rund 60 Sekunden; dies ist kein unabhängiger Qualitäts- oder
Geschwindigkeitsvergleich. Audit: `instructor_filter_validation.json` im Laufordner.

Text-LLM weiter auf Qwen3-1.7B verkleinert, 29.10.2026:
Auf Benutzerwunsch verwenden `local.yaml` und `benchmark-unlimited.yaml` jetzt
`Qwen/Qwen3-1.7B` statt Qwen3-4B, fest auf Revision
`70d244cc86ccca08cf5af4e1e306ecf908b1ad5e` und `models/qwen3-1.7b`.
Die abgeleiteten Profile übernehmen diese Einstellung für Tesseract/LLM,
Unlimited-OCR/LLM, Paddle und Docling. BF16, vollständig auf CUDA, keine
Quantisierung, deaktiviertes Thinking sowie 12000 Eingabe- und 8192 Ausgabetokens
bleiben explizit konfiguriert. Das VLM und die visuellen Signaturmodelle behalten
ihre bisherige Revision. Remote-API-Modellnamen werden nicht verändert.

Die zwei öffentlichen Gewichtedateien wurden heruntergeladen: zusammen
4063515592 Bytes. Alle elf Manifestdateien wurden per SHA-256 geprüft;
keine Teildownloads sind übrig. Tokenizer und Modellarchitektur lassen sich
offline ohne Remote-Code laden. Die Architektur wurde ohne Gewichtsspeicher
aufgebaut und nach konfigurierter Gewichtsteilung mit 1720574976 Parametern
geprüft. **395 lokale Tests bestanden**, einschließlich der Prüfung aller acht
betroffenen Profile und unveränderter VLM-Identität. Ruff und `git diff --check`
sind ohne Befund.

Die GPU war durch einen vorhandenen Benutzerlauf belegt. Deshalb wurden für
diese Änderung keine zusätzliche GPU-Inferenz, Laufzeitmessung oder
Qualitätsmessung durchgeführt. Weniger Modellparameter allein belegen keine
gleichbleibende Genauigkeit oder bestimmte Beschleunigung. Neue Modellläufe
erhalten die neue Identität; vorhandene Ergebnisse und 4B-/8B-Gewichte bleiben
erhalten. Einrichtungsnachweis: `data/model-validation/qwen3-1.7b-20261029.json`.

Feste Klassen-ID-Grenze beim Referenzvergleich, 29.10.2026:
Die bestehende Gruppierung nach Klassen-ID wurde gezielt für beide Zuordnungsmodi
geprüft. PDF-Dateinamen bestimmen die Schulung; nur Referenzzeilen mit derselben
`Class ID` werden an die Zuordnung übergeben. Auch eine exakt passende ID oder
ein identischer Name in einer anderen aktiven Schulung wird nicht herangezogen.
PDFs ohne passende Referenzklasse bleiben separat unbewertet. Führende Nullen
der Klassen-ID bleiben erhalten. Die vorhandene Schutzprüfung in `course_metrics`
weist gemischte Referenzklassen ab.

Der Namensreport nennt jetzt pro Zeile die Klassen-ID und die Anzahl passender
Referenzeinträge. Auch die Kandidatentabellen zeigen den Filter ausdrücklich.
Sieben zusätzliche Testfälle prüfen Best-Fit und konservative Zuordnung,
CSV-/XLSX-Eingaben, exakte Gegenkandidaten in einer anderen aktiven Klasse und
fehlende Referenzklassen. **60 gezielte lokale Tests und 40 Firmen-PC-Tests
bestanden**, einschließlich des gemeinsamen Report- und API-Einstiegs. Ruff und
`git diff --check` sind ohne Befund.

Die vier zuvor ergänzten Vergleiche wurden erneut geprüft und ihre Darstellung
aktualisiert. Alle 2573 Referenzzeilenprüfungen in Teilnehmer-, Feld- und
Kandidatenexporten bestätigen dieselbe Klassen-ID wie die jeweilige PDF-Zuordnung.
Root-CSV-/JSON-/XLSX-Artefakte und Quellvorhersagen blieben per Hashvergleich
unverändert. Es gab keine erneute Inferenz oder echte API-Anfrage.

Separater Namenszuordnungsreport, 29.10.2026:
`zuordnungen.html` zeigt gespeicherte erkannte Namen und Referenznamen direkt
nebeneinander, einschließlich Quelle, tatsächlicher Paarung, Entscheidungsgrund,
Feldbelegen, Levenshtein-Distanzen, Kandidatenrang und globalem Alternativabstand.
Die vollständige Kandidatenliste weist aus, welche Referenz bereits einer anderen
Ausgabe gehört. Fehlende und zusätzliche Namen bleiben getrennt sichtbar. Die
lokalen Browserfilter führen keine Anfragen aus. Namen werden als Text maskiert;
der feste Filterscript ist durch einen CSP-Hash freigegeben.

Neue Vergleiche erzeugen den Report automatisch. `assignments --report ...`
ergänzt vorhandene Vergleiche lokal; auf dem Firmen-PC lautet der Einstieg
`main.py benchmark assignments --report ...`. Weder aktuelle Referenzdateien,
Zugangsdaten noch Modellaufrufe werden dafür benötigt. Es werden keine Paarungen
neu berechnet oder Werte korrigiert. Gespeicherte Rohvorhersagen werden nur bei
passender Quellprüfsumme zur Darstellung herangezogen.

Abnahme: **388 lokale Tests und 48 Firmen-PC-Tests bestanden**. Sechs neue Fälle
prüfen die direkte Namensdarstellung, ein globales Optimum mit lokal zweitbester
Namenspaarung, unsichere Namen, fehlende/veränderte Quellen, unveränderte Daten,
den unabhängigen CLI-Einstieg sowie HTML-Maskierung und CSP. Die API-Integration
prüft den zusätzlichen Report und dessen Aufruf ohne Zugangsdaten. Vier vorhandene
Vergleiche wurden ergänzt: `20261029T074406Z-197ec7bd`,
`20261028T124935Z-14c7ff83`, `20261028T112226Z-05f9323c` und
`20261028T091240Z-22b73d6a`. HTML-Zeilenzahlen stimmen mit `participants.csv`
überein; sämtliche Nicht-HTML-Artefakte und Quellvorhersagen blieben per Hashvergleich
unverändert. Es gab keine erneute Inferenz und keine API-Aufrufe.

OCR-Ausgabelimit und globale Best-Fit-Bewertung, 29.10.2026:
Die lokalen OCR-LLM-Profile und das Remote-OCR-LLM verwenden 8192 statt 2048 bzw.
4096 Ausgabetokens. Die Eingabegrenze, Modellrevision und VLM-Parameter bleiben
unverändert. Schematisch ungültige einzelne OCR-Teilnehmerzeilen werden separat
protokolliert; andere Zeilen durchlaufen weiter die strikte Prüfung gegen echte
OCR-Wortbelege. JSON-Syntaxfehler werden nicht repariert, numerische IDs nicht
stillschweigend in Strings umgewandelt und fehlende Personen nicht erfunden.

Die ausgelieferten Testframework-Profile verwenden `matching.mode: best_fit`.
Der ungarische Algorithmus maximiert zuerst die Anzahl lesbarer Eins-zu-eins-
Paarungen innerhalb eines Kurses und dann die Summe bewertbarer Feldähnlichkeiten.
Lesbare ungefähre IDs zählen mit. Die bisherigen Mindestgrenzen markieren jetzt
schwache Paarungen; Mehrdeutigkeit, Duplikate und Identitätswidersprüche werden
explizit ausgewiesen. Eine Paarung ist keine bestätigte Identität. Der alte
konservative Modus und sein Score stehen separat zur Verfügung. Historische
Konfigurationen ohne Modus behalten konservative Semantik. Metrikversion v2
und Konfiguration dokumentieren die geänderte Auswertungsregel.

Abnahme: **382 Hauptprojekttests und 48 Firmen-PC-Tests bestanden**. Neue Tests
prüfen das globale Optimum gegen vollständiges Durchprobieren kleiner echter
Levenshtein-Matrizen, Permutationen, niedrige/Nullähnlichkeiten, ungefähre IDs,
fehlende/maskierte Werte, Mengenunterschiede, Duplikate, Mehrdeutigkeit,
Identitätskonflikte, unveränderte Feldrollen und die konservative Vergleichszahl.
Weitere Fälle prüfen zeilenweise Schemafehler und weiterhin abgewiesene ungültige
JSON-/Umschlagstrukturen. Ruff und `git diff --check` sind ohne Befund.

Neue Bewertung derselben unveränderten Vorhersagen wie im Vergleich
`20261028T124935Z-14c7ff83`: `20261029T074406Z-197ec7bd`. OCR/LLM erhält
10 Paarungen statt 0, VLM 18 statt 2. Der VLM-Best-Fit-Score beträgt
52,131646131646136 %, die konservative Vergleichszahl unverändert
7,707231040564374 %. Die höheren Werte entstehen durch die Zuordnungsregel,
nicht durch bessere oder korrigierte Modellwerte. Alte Berichte und
Quellvorhersagen blieben per Hashvergleich unverändert.

Lokaler GPU-Nachtest des 8192-Limits: `runs/20261029T074005Z-793451f1/`.
Die Antworten endeten nach 4063 bzw. 835 Tokens ohne Tokenabschneidung.
Die erste Antwort enthält jedoch drei Schemafehler und 92 weitere nicht
hinreichend mit OCR-Zeilen belegbare Ausgaben; auch die neue zeilenweise Prüfung
findet dort keinen belastbaren Teilnehmerdatensatz. Der höhere Grenzwert behebt
den Budgetabbruch, nicht diese verbleibende Erkennungs-/Belegschwäche des Modells.
Die zweite Seite enthält zehn akzeptierte Zeilen mit 25 Feldprüfhinweisen.
Original-PDF, ursprüngliche Vorhersagen und Rohantworten wurden nicht verändert.
Diese Einzelprüfung ist keine unabhängige Qualitätskalibrierung.

HTML-Detailvergleich und Fehlerdiagnose, 28.10.2026:
Neue Vergleiche enthalten `details.html` mit Unterseiten pro Verfahren/Schulung.
Die Ansicht zeigt tatsächliche Referenz-/Ausgabepaare, Originalwerte, normalisierte
Werte, Status, Levenshtein-Distanzen, Nennerbeiträge und sämtliche Referenzkandidaten
mit Zulassungsgrenzen. Einzelbeiträge werden gegen gespeicherte Gesamtscores geprüft.
Suche und Filter verwenden ein festes lokales Skript mit CSP-SHA256-Freigabe; alle
Dokumentwerte werden HTML-escaped. Ein Herkunftsexport trennt Darstellungs- von
Bewertungsimplementierung. `details --report ...` funktioniert ohne Modell-/API-
Aufrufe, ohne aktuelle Excel-Datei und ohne erneute Bewertung. Die mathematisch
unveränderten Kandidatengrenzen werden für Zuordnung und Erklärung gemeinsam genutzt.

Abnahme: **363 Hauptprojekttests und 48 Firmen-PC-Tests bestanden**, Ruff und
`git diff --check` ohne Befund. Neun neue Fälle prüfen fehlende/zusätzliche Personen,
maskierte Referenzwerte, Bruchteile, eingefrorene Referenzen, unveränderte Scores,
unsichere Originalwerte, verschobene/fehlende Quellen, Manipulationserkennung,
Namensreihenfolge als reine Diagnose, HTML-Injektionen/CSP und abgeschnittene
Modellantworten. API-Integrationstests prüfen die automatische Detailausgabe und
deren Aktualisierung ohne Zugangsdaten oder zusätzliche Requests.

Die Vergleiche `20261028T124935Z-14c7ff83` und `20261028T112226Z-05f9323c`
wurden um die Detailansicht ergänzt. Sämtliche bisherigen JSON-/CSV-/XLSX-Dateien
und Quellvorhersagen blieben per Hashvergleich unverändert. Eine Berechnung im
Speicher aus den eingefrorenen Referenzen bestätigt für beide Vergleiche dieselben
Paarungsanzahlen und Scores nach dem Refactoring der Kandidatenprüfung.
Im aktuellen Vergleich werden von 18 VLM-Ausgaben nur 2 zugeordnet; der Feld-F1
beträgt 7,707231040564374 %. Es bestehen zehn Diagnosehinweise auf vertauschte
Vor-/Nachnamen, ohne automatische Korrektur oder Zusatzpunkte. OCR/LLM-Seite 1
ist bei 2048 Ausgabetokens abgeschnitten. Paddle liefert auf Seite 2 nach einem
Zuordnungsfehler keine Teilnehmer. Diese konkreten Befunde erklären niedrige
Werte; sie belegen keine allgemeine Modellqualität und ersetzen keine unabhängig
gelabelte Evaluation. Keine Modellgewichte, Schwellenwerte oder Extraktionsregeln
wurden zur Verbesserung dieser gespeicherten Scores verändert.

Vollständiges API-Testframework, 28.10.2026:
`api_firmen_pc/start_api_testframework.cmd` verarbeitet PDFs über den API-Adapter
und führt anschließend dieselbe lokale, kursbezogene Levenshtein-/Exact-Match-
Bewertung wie das GPU-Testframework aus. Eigene Eingabe-, Referenz- und
Ergebnisordner liegen unter `api_firmen_pc/testframework/`. Referenzen bleiben
vor der Inferenz eingefroren und werden nicht an die Extraktion weitergegeben.
Der lokale Einstieg bleibt standardmäßig offline; nur der explizite Firmen-PC-
Einstieg setzt die interne API-Freigabe. `benchmark check` und `benchmark compare`
benötigen keine Zugangsdaten und keine Modellaufrufe. Das vorhandene OCR/API-Profil
enthält nun sowohl die Remote-LLM- als auch die Remote-VLM-Konfiguration.

Abnahme: **354 Hauptprojekttests und 48 Firmen-PC-Tests bestanden**. Die neuen
Integrationstests verarbeiten jeweils zwei synthetische PDFs über einen lokalen
OAuth-/Chat-Testserver, vergleichen CSV und XLSX ohne identische Zeilenreihenfolge
und ergeben den erwarteten Levenshtein-Feld-F1 von 93,75 %. Ein zusätzlicher Kurs
bleibt außerhalb des Nenners; exklusive Referenzwerte fehlen in allen Requests.
Originaldateien bleiben per Hashvergleich unverändert. Erneuter Abgleich ohne
Zugangsdaten erzeugt keine Requests. PowerShell-Syntax, CLI-Einstiege, Ruff und
`git diff --check` sind geprüft.

Transferpaket: `api_firmen_pc/dist/firmen-pc-20261028-api-testframework.zip`,
94 ausgewählte Dateien ohne Dokumente, Referenzdaten, Schlüssel, Gewichte oder
virtuelle Umgebungen. Nach dem Entpacken wurden die enthaltenen Python-Quellen
explizit importiert; alle 40 API-Integrations- und Starttests bestanden mit diesen
Paketquellen in der bestehenden Umgebung ohne PyTorch/Transformers. Die acht
Tests für private PowerShell-Starts bestanden im installierten Firmen-PC-Projekt.
Kein echter Unternehmensdienst wurde kontaktiert. Onboarding, freigeschaltete
Modelle und die tatsächliche Anmeldung müssen auf dem Firmen-PC geprüft werden.

VLM-Spaltenzuordnung bei leeren Benutzerfeldern, 28.10.2026:
Prompt v11 gibt die vollständigen physischen Tabellenüberschriften und pro Person
eine gleich lange Zellenliste aus. Der Parser leitet Benutzer und Kurzzeichen aus
eindeutigen gedruckten Überschriften ab; Namens-, Nummern- und leere Zellen bleiben
an ihrer Position. Fehlende oder mehrdeutige Spalten sowie nicht passende
Zellenanzahlen erzeugen unbekannte Felder und Prüfhinweise. Kein Vertauschen allein
anhand eines vermeintlichen Unternehmensformats. Normale und API-VLMs verwenden
dasselbe neue Schema; alte Antworten bleiben lesbar und unverändert gespeichert.

Abnahme: **352 Hauptprojekttests und 42 Firmen-PC-Tests bestanden**, Ruff und
`git diff --check` ohne Befund. Die zusätzlichen Fälle prüfen komplette und
umgekehrte Spaltenreihenfolgen, durchgehend leere IDs, fehlende ID-Spalten,
Benutzername gegenüber Benutzer, numerische Kurzzeichen/alphanumerische IDs,
mehrdeutige Überschriften, kompaktierte Zellen, Legacy-Prüfhinweise, den
Excel-Export und den unveränderten Seitentext-Fallback.

Lokaler GPU-Nachtest: `runs/20261028T122806Z-b9d65921/report.html` liest dieselben
zwei Seiten wie `20261028T110616Z-ffb47309`. Weiterhin 9 + 9 = 18 Teilnehmer.
Auf Seite 2 stehen jetzt 9 Benutzerfelder auf `empty` und alle 9 Kurzzeichen auf
`read` in der richtigen Zielspalte; zuvor standen sechs Kurzzeichen in Benutzer.
Die erste reduzierte Zellvariante las dagegen Vornamen als IDs und wurde verworfen;
deshalb enthält das endgültige Schema auch die Namens- und übrigen Tabellenspalten.
Der erfolgreiche Nachtest benötigt zwei Seitenaufrufe und einen Warm-up-Aufruf,
keine zusätzliche OCR-/VLM-Stufe. Modellrevision und Bildauflösung blieben gleich.
Quell-PDF, Originalmanifest, Quellvorhersagen und Rohantworten wurden vor/nach dem
Lauf per Hash auf Unverändertheit geprüft. Der Export enthält dieselbe korrekte
Spaltenzuordnung. Dies prüft den gemeldeten Einzelfall und ist keine unabhängige
Evaluation der Namensgenauigkeit oder sämtlicher Vorlagen.

Kleineres Textmodell, 28.10.2026:
`local.yaml` und `benchmark-unlimited.yaml` verwenden jetzt Qwen3-4B mit Revision
`1cfa9a7208912126459214e8b04321603b3df60c`, eigenem Pfad `models/qwen3-4b`,
BF16 und `quantization: none`. Davon erben auch die Profile für Import, Tesseract,
Unlimited-Zuordnung, Paddle, Docling und das separate Testframework. Tokenbudgets,
Feldbelege und das Qwen3-VL-4B bleiben unverändert. Alte 8B-Gewichte und Ergebnisse
wurden erhalten; laufende Prozesse behalten ihre eingelesene Konfiguration.

Abnahme: **334 Hauptprojekttests bestanden**, Ruff und `git diff --check` ohne
Befund. Die Profilprüfung deckt acht Einstiegskonfigurationen ab und bestätigt
das unveränderte VLM. Die drei neuen Gewichtedateien (8.044.982.000 Bytes) wurden
explizit heruntergeladen und per SHA256 geprüft. Offline-Tokenizer, deaktiviertes
Thinking sowie die native Transformers-Architektur mit 4.022.468.096 Parametern
wurden lokal geprüft; die Architekturerstellung verwendete ausschließlich
Meta-Tensoren. Keine zusätzlichen Dokumente verarbeitet und keine GPU-Inferenz
parallel zum bereits laufenden Benutzerprozess gestartet. Ein kontrollierter
Laufzeit- und Qualitätsvergleich zwischen 8B und 4B steht noch aus.

Excel-Spaltennamen, 28.10.2026:
Die Referenzleser erhalten die tatsächlichen Überschriften einschließlich ihrer
Schreibweise und Reihenfolge. HTML-Berichte zeigen diese Bezeichnungen;
`participants.xlsx` enthält je Verfahren ein Blatt sowie ein Quellenblatt und
beim Referenzvergleich die verglichenen Referenzzeilen. Die internen Feldkennungen
bleiben kompatibel. Leere Benutzerfelder, führende Nullen und als Text erkannte
Formelzeichen bleiben im Excel-Export erhalten.

Abnahme: **329 Hauptprojekttests und 42 Firmen-PC-Tests bestanden**; Ruff und
`git diff --check` ohne Befund. Elf neue synthetische Fälle prüfen Überschriften,
mehrdeutige Zuordnungen, beide Referenzleser, Zelltypen, fehlende Kurs-IDs,
Berichtserneuerung und beide Vergleichsverfahren. Die fertigen Läufe
`20261028T103543Z-60f2dd65` und `20261028T101534Z-099e06b9` wurden ohne OCR-/
Modellaufrufe aktualisiert. Referenzdatei, Manifeste, Konfigurationen,
Zusammenfassungen und modellseitige `extractions.jsonl` blieben per Hashvergleich
unverändert. Keine neue Abhängigkeit und keine Änderung von Modellvorhersagen.

Teilnehmerzuordnung für Paddle und Docling, 28.10.2026:
Das Standardprofil verwendet jetzt nach Entladen des jeweiligen OCR-Workers das
vorhandene lokale Qwen3-8B für die Feldzuordnung. Native OCR-/Textpositionen bleiben
auch bei verbundenen Zellen oder fehlender Tabellenerkennung erhalten. Werte müssen
wortgetreu in aktuellen Zeilen belegt sein; eindeutig erkannte Spalten verhindern
eine Verschiebung von Kurzzeichen in Benutzerfelder. Komma-Namen werden nach der
expliziten Konvention `Nachname, Vorname` getrennt. Fortsetzungsseiten erhalten nur
Überschriften/Positionen derselben PDF, keine vorherigen Teilnehmerwerte.

Docling erhält textlose, gekachelte Scans als verlustfreies Seitenbild; digitale
Text-PDFs bleiben nativ. Die Boxen vor dem Zusammenführen durch TableFormer werden
zusätzlich gespeichert. Tesseract-Zeilenmodus und konfigurierte Linienentfernung
gelten auch innerhalb Doclings OCR-Komponente; das Layoutbild behält seine Linien.
Die bereits vorhandenen Bildfunktionen werden gemeinsam verwendet. Eine Änderung
der OCR-Konfiguration ist keine kalibrierte Qualitätsaussage auf unabhängigen Daten.

Abnahme: **318 Tests im Hauptprojekt und 42 im Firmen-PC-Projekt bestanden**,
Ruff und `git diff --check` ohne Befund. Die zusätzlichen synthetischen Fälle prüfen
verbundene/fehlende Tabellen, native Einzelboxen, leere IDs, Kurzzeichenverschiebung,
mehrteilige Namen und Textoffsets, Kontextgrenzen, Fortsetzung, GPU-Modellreihenfolge,
unveränderte Quellläufe, verlustfreie Scan-Pixel und die ausschließlich temporäre
OCR-Linienentfernung. Keine neuen Paketabhängigkeiten oder Modellgewichte.

Lokale GPU-Nachtests auf den gespeicherten Unternehmensbelegen:

- Paddle: `runs/20261028T093935Z-ba08a554/report.html`, 9 + 9 = 18 zugeordnete
  Teilnehmerzeilen gegenüber zuvor 0. Auf Seite 2 bleiben die neun Benutzer-IDs
  unbekannt; Kurzzeichen werden nicht als Ersatz übernommen.
- Docling mit aktualisierter OCR-Eingabe und Positionskontext:
  `runs/20261028T100721Z-3e1d2b31/report.html`, 9 + 7 = 16 zugeordnete
  Teilnehmerzeilen gegenüber zuvor 0. Grundlage des OCR-Nachlaufs ist
  `runs/20261028T100047Z-b34e4856/`; dessen reiner Strukturdiagnoselauf verwendet
  ausdrücklich `extraction: table` und zeigt selbst noch keine LLM-Teilnehmer.

Die Anzahlen sind **keine bestätigten richtigen Treffer**. Es gibt keine manuell
gelabelte Referenz für diese Dokumente; OCR-Fehler, unbekannte Felder, nicht zugeordnete
Zeilen und mögliche zusätzliche/falsch zugeordnete Personen erfordern Prüfung mit
dem separaten Excel-/CSV-Testframework. Beide Nachberichte tragen `partial`, führen
keine neue Unterschriftenbewertung durch und verändern ihre Quellläufe nicht.
`assignment_recheck.json` enthält die Quellprüfsummen und die verwendete Code-/
Promptversion. Für die Scan-Korrektur ist ein neuer `run` notwendig; `assign-structures`
kann nur vorhandene OCR-Belege neu zuordnen. Nur beide Verfahren starten:
`run --input data/cv-test-20261020-093337 --config configs/structure-models.yaml --offline`.

Separates Testframework für Schulungsreferenzen, 28.10.2026:
`testframework/main.py` mit eigenen PDF-/Referenzordnern, YAML-Konfiguration und
`start_testframework.cmd` ergänzt die bestehende Extraktion. XLSX-/CSV-Leser nutzen
die vorhandenen Regeln für String-IDs, Maskierungen und Excel-Zellenformate.
Der Vergleich gruppiert nach Schulungs-ID aus PDF-Dateinamen über alle Seiten und
Dateien hinweg. Globale optimale Eins-zu-eins-Zuordnung mit Levenshtein-Namen/
Kurzzeichen, eindeutigen exakten ID-Ankern, Dummy-Zuordnungen und globaler
Alternativenprüfung verhindert Mehrfachgutschriften und beliebige Paarungen.
Konflikte und mehrdeutige Identitäten erhalten konservativ keine automatische
Zuordnung. Die Werte werden nicht zur Reparatur von Modelltexten verwendet.

Der Hauptscore ist ein Levenshtein-Feld-F1 mit dokumentierten Zählern/Nennern;
exakter Feld-F1, exakte Referenztrefferquote und Originalschreibweise stehen
daneben. Fehlende Felder zählen null, zusätzliche/duplizierte vorhergesagte Werte
vergrößern den Nenner. Referenzausschlüsse und explizite Maskierungsprüffälle
bleiben sichtbar. Unbekannte Modellwerte bei lesbarer Referenz zählen als Fehler.
Reiner OCR-Text wird nicht als strukturierte Teilnehmerextraktion bewertet.
Die Referenzdaten werden vor der Inferenz eingefroren und niemals an den Runner
übergeben; ein Editieren der Quelldatei während der Inferenz wird im Vergleich
sichtbar. Nur fünf relevante Referenzspalten werden im Audit-Snapshot gespeichert.

Abnahme: **300 lokale Tests und 42 Tests des getrennten Firmen-PC-Projekts
bestanden**, Ruff ohne Befund. Darin 35 neue Prüfungen für Edit-Distanz,
Teilpunkte, alle Reihenfolgepermutationen, globale gegenüber gieriger Zuordnung,
Duplikate, Fehlstellen, leere/maskierte IDs, unsichere Literalwerte, führende
Nullen, CSV-Trennzeichen/BOM, Excel-Formate/Formeln, Schulungsgrenzen, mehrere
PDFs/Seiten pro Kurs, widersprüchliche Hash-/Kurszuordnung, Referenzfreeze,
Read-only-Quellläufe, Offline-Auswertung und CLI. Es kamen keine neuen
Paketabhängigkeiten hinzu. Nur Referenzübereinstimmung wird gemessen;
Zuordnungsfelder sind keine unabhängige Identitätsprüfung.

Echter lokaler GPU-Integrationslauf mit zwei synthetischen PDFs und bewusst anders
sortierter Referenz: `runs/20261028T085805Z-610f3ceb/report.html`, Qwen3-VL-4B,
drei Personen, zwei Schulungen, 11/11 bewertbare Textfelder exakt; der leere
Referenzbenutzer ist ausgeschlossen. Keine zusätzlichen Signaturdetailaufrufe,
weil die Referenz keine Signaturlabels enthält. Extraktion etwa 28,5 s.
Aktueller Post-hoc-Vergleich ohne neue Inferenz:
`testframework/ergebnisse/20261028T091240Z-22b73d6a/report.html`.
Ein zusätzlicher CSV-Kurs ohne Eingabe-PDF bleibt außerhalb des Nenners.

Die davon getrennte, ausdrücklich künstliche Vorhersagefixture enthält einen
Schreibfehler und eine Doppelzeile. Ihr erwarteter Levenshtein-Feld-F1 ist
82,69 %, exakter Feld-F1 76,92 %, zehn von elf Referenzfeldern exakt, eine
zusätzliche Person. Aktueller Demobericht:
`testframework/ergebnisse/20261028T091241Z-757eb697/report.html`.
Dies prüft ausschließlich die Bewertungslogik und wird im Bericht als synthetisch
markiert; es ist kein Nachweis einer Modellqualität auf Unternehmensdaten.

Sechs lokale Verfahren, 28.10.2026: Der Standardvergleich enthält jetzt
`ocr_raw`, `ocr_llm`, `unlimited_ocr`, `vlm`, `paddle_structure` und `docling`.
`ocr_raw` erzeugt ausschließlich Tesseract-Rohtext; keine Teilnehmer-, Feld-,
Excel- oder Unterschriftenbewertung. Historische `ocr_rules` und eingefrorene
Kalibrierungen bleiben verfügbar. PaddleOCR 3.7.0/PaddleX 3.7.2/Paddle CUDA 3.3.1
und Docling 2.143.1/TableFormer laufen in getrennten uv-Umgebungen. Die neuen
Worker blockieren Netzwerkzugriffe und verwenden ausschließlich vorab geladene,
festgeschriebene Modellartefakte mit SHA-256-Manifesten. Tatsächliche
Laufzeit-Paketversionen gehen zusätzlich zu Lockdateien in die Laufidentität ein.

Abnahme: **265 lokale Tests und 42 Firmen-PC-Tests bestanden**, Ruff ohne Befund.
Alle fünf uv-Lockdateien offline geprüft: Hauptprojekt 71, Firmen-PC 54,
Unlimited 55, Paddle 117 und Docling 121 aufgelöste Pakete. Der neue Starter
`start_alle_lokalen_modelle.cmd --pruefen` findet den vorhandenen CV-Eingabeordner,
ohne Modelle zu starten oder Zugangsdaten zu lesen. Zusätzliche Tests prüfen
Rohtext ohne Feld-/Signaturmodell, native Seitenauswahl, zusätzliche Rotation,
Originalerhalt, leere IDs und führende Nullen, Netzwerksperre, Paket-/Modell-
Provenienz, Cache, beschädigte Cacheeinträge, Cachebegrenzung, Einzel-Seitenfehler
und inerte Tabellenexporte. Die Adapter-Testdoubles sind kein Qualitätsnachweis.

Echter lokaler GPU-Test mit synthetischen Daten:
`runs/20261028T080613Z-6ff616dc/report.html`, drei Seiten (Deckblatt, digitale
Teilnehmertabelle, Scan mit PDF-Rotation 90° und zusätzlicher Analysekorrektur
270°). SHA-256 der synthetischen Original-PDF:
`266c352cbc58a4679a7ad0d5961f061aa27e694c9bc95e98e2a1276ea330793f`.
Beide Strukturverfahren liefern 0/3/3 Teilnehmende und jeweils 24/24 exakt
übereinstimmende Textfelder gegenüber den bekannten Konstruktionswerten,
einschließlich leerem Benutzerfeld, führenden Nullen, Umlauten und Bindestrich.
Paddle-Peak etwa 3,26 GiB, Docling etwa 0,56 GiB GPU-Allocator-Speicher;
gesamter Dreierlauf etwa 31,7 s. Reine Tesseract-Ausgabe hat erwartungsgemäß
keine Teilnehmer und wird nicht als fehlgeschlagene Feldextraktion bewertet.
Die Original-PDF blieb unverändert. Die spätere Ergänzung der installierten
Paketversionen betrifft die Identität, nicht die Inferenz dieser Modelle.

Separater Paddle-Lauf `runs/20261028T080234Z-defb9174/report.html` prüft zusätzlich
das vollständige Entladen des Paddle-Workers vor der lokalen Qwen-VLM-
Unterschriftenstufe. Die Windows-DLL-Suche wurde dafür im Worker auf die
vorhandenen CUDA-/cuDNN-Dateien des Hauptprojekts eingestellt; kein systemweiter
PATH-Eingriff und kein PyTorch-Import im Paddle-Worker. Keine externen Anfragen
mit Dokumentinhalten. Ergebnisse bleiben `partial`, weil OCR und gedruckte
Spaltenüberschriften die korrekte Semantik nicht beweisen. Auf echten PDFs
und Handschrift ist die Zuverlässigkeit der neuen Baselines noch nicht evaluiert.

Die folgenden Abschnitte dokumentieren ältere Entwicklungsstände.

Unlimited-OCR-Zellzuordnung, 27.10.2026: Der bisherige CV-Lauf lieferte OCR,
aber keine Teilnehmer: verbundene Tabellenzellen auf der ersten Seite und
fehlende Spaltenüberschriften auf der zweiten Seite verhinderten die bisherige
regelbasierte Zuordnung. Neue Option `extraction: llm` ergänzt eine lokale
Zuordnung mit dem vorhandenen Qwen3-8B nach vollständigem Entladen des
Unlimited-Workers. Explizite Zellnummern, Spaltenpositionen, leere Zellen und
HTML-Spans bleiben erhalten. Gedruckte eindeutige Überschriften gestatten direkte
Zellübernahme; `Benutzername` wird als Namensfeld behandelt. Andere Werte müssen
als vollständige Wörter/Phrasen in derselben Quellzeile belegt sein. Falsche
Zellnummern werden nur bei eindeutigem Beleg innerhalb dieser Zeile berichtigt.
Maskierte IDs bleiben unbekannt; die semantische Zuordnung bleibt prüfpflichtig.

`configs/unlimited-ocr-llm.yaml`, Vierervergleich und Unlimited-Starter verwenden
die Kombination. Reine OCR und Tabellenbaseline bleiben separat konfigurierbar.
`assign-unlimited --run ... --offline` ordnet gespeicherte OCR zu, ohne die OCR
zu wiederholen oder den Quelllauf zu verändern. Neue Ergebnisse stehen in einem
separaten Lauf mit Quellhashes. Antworten werden mit Quell-, Modell-, Parameter-,
Systemprompt- und Schemafingerprints lokal gecacht und beim Wiederlesen erneut
gegen die Quellzellen geprüft. Keine API-Übertragung von Dokumentdaten.

**250 lokale Tests und 38 getrennte API-Tests bestanden**; Ruff, Lockprüfung und
`git diff --check` erfolgreich. 21 neue Testfälle decken zusammengeführte Zellen,
Namensaufteilung, führende Nullen, leere Benutzerzellen, teilweise maskierte IDs,
vollständige Wortbelege, falsche/zeilenfremde Referenzen, Kontexttrennung zwischen
PDFs, leere Markdown-Randzellen, Fehler/Tokenlimit, Cache, Quellimmutabilität,
Export und GPU-Modellreihenfolge ab. Modell-Doubles prüfen Verträge und messen
keine OCR-/LLM-Erkennungsqualität. Nach den letzten Provenienz-/Exportergänzungen
sind 31 gezielte Tests erneut erfolgreich.

**Vollständiger realer lokaler Lauf ausgeführt:**
`runs/20261027T092255Z-21c3aed0/report.html` auf der bestehenden Test-PDF mit zwei
Seiten. Unlimited-OCR, danach 8B-LLM (int8, sämtliche Parameter auf cuda:0),
danach BF16-VLM zur Unterschriftenprüfung; keine gleichzeitige Modellbelegung.
Ca. 325 Sekunden Gesamtzeit einschließlich Laden, OCR und Signaturprüfung.
Neun beziehungsweise acht Teilnehmerdatensätze, zusammen 17 statt zuvor null,
68 buchstäblich durch Zellen belegte Textfelder. Das bestätigt Textvorkommen,
keine unabhängige semantische Feldgenauigkeit. Eine weitere OCR-Zeile auf Seite 2
(`t0r0`) bleibt als nicht zugeordnet markiert. 17 visuelle Signatur-Detailprüfungen
ausgeführt; ohne manuelle Labels kein Qualitätsnachweis. Status bewusst `partial`.
Die früheren Zuordnungsversuche `090939Z-f590ef0a` und `091706Z-e2ac0160` sind
Entwicklungsdiagnosen, nicht der abschließend geprüfte Stand. Die Ausgangs-PDF,
ältere Berichte und Ground Truth wurden nicht verändert.

Bedienung, Grenzen und neue Exporte: [Unlimited-Zuordnung](unlimited-assignment.md).

GPU-Anpassung, 27.10.2026: Qwen3-8B bleibt bei Revision
`b968826d9c46dd6066d109eabc6255188de91218`. In `local.yaml` (auch über
`imported.yaml`) und `benchmark-unlimited.yaml` werden seine linearen Schichten
beim Laden mit bitsandbytes 0.48.1 / LLM.int8 quantisiert. Originalgewichte,
Parameterzahl, OCR, Prompts und Tokenbudgets bleiben erhalten. `device: cuda`
erzwingt und prüft vollständige GPU-Zuordnung; CPU-Offload ist nur noch im
ausdrücklich gewählten `auto`-Modus erlaubt. VLM bleibt in BF16. Modell-
speicher, Quantisierung und tatsächliche Parametergeräte werden protokolliert.

Abschließend **229 lokale Tests und 38 getrennte API-Tests bestanden**, Ruff und beide
Lockprüfungen erfolgreich. Fünfzehn zusätzliche Fälle prüfen GPU-/CPU-Zuordnung,
fehlende CUDA-/8-Bit-Unterstützung, Kompatibilitätsgrenzen und unveränderte
8B-Checkpointauswahl. Hauptumgebung weiterhin PyTorch 2.8.0+cu126 / Transformers
4.57.6; die API-Lockdatei wurde ohne Installation von GPU-Paketen aktualisiert.

Echte int8-GPU-Inferenz auf zwei synthetischen Seiten:
`runs/20261027T082419Z-49a39d0a/report.html`. Alle 8.190.735.360 Parameter auf
`cuda:0`, Modellbelegung 9.435.703.552 Bytes (8,79 GiB), Peak allocated ca.
9,85 GiB / reserved ca. 9,92 GiB. Zwei gültige Seitenausgaben mit sechs Zeilen,
keine technischen Seitenfehler, rund 35–39 Sekunden Generierung je Seite und
103 Sekunden Gesamtlaufzeit einschließlich Laden. Die separat bewertete
Textfeldqualität beträgt auf dieser Tesseract-/LLM-Konstruktion nur 12/24
buchstäblich korrekte Felder; dies belegt die Funktionsfähigkeit des GPU-Pfads,
keine ausreichende Extraktionsqualität und keinen verlustfreien Ersatz für
BF16. Ein kontrollierter BF16-Vergleich auf dieser Konstruktion fehlt.

Bei einem anschließenden Versuch auf der bestehenden CV-Test-PDF zeigte sich
trotz korrekter CUDA-Parameterzuordnung Windows-Speicherauslagerung: 15.477.776.384
Bytes dedizierter GPU-Speicher und 4.984.930.304 Bytes Shared GPU Memory
(Windows-GPU-Prozesszähler, nur Prozess-/Speichermetadaten). Dieser eigene
Diagnoselauf `20261027T082651Z-6eae8b8e` wurde unterbrochen und ist kein
abgeschlossener Benchmark. Daraufhin die CUDA-Allocator-Grenze mit 2 GiB freier
Reserve und native Promptaufteilung in 1024-Token-Abschnitte ergänzt. Der Text
wird nicht gekürzt; KV-Cache und vollständige Eingabetokens bleiben erhalten.
Drei weitere Tests prüfen vollständige Tokenübergabe und Wiederherstellung der
vorherigen Speichergrenze nach einem Fehler beim Laden.

Erneuter CV-Lauf `runs/20261027T083827Z-158083d5/report.html`: zwei Seiten ohne
technischen Extraktionsfehler, vollständige OCR-Eingaben aus demselben Cache
(5485 beziehungsweise 2396 Eingabetokens). Reine Modellberechnung ca. 160,3 und
133,6 Sekunden; im früheren Lauf `20261027T074837Z-9a137c33` ca. 916,6 und 541,0
Sekunden. Die Tokenausgaben unterscheiden sich (828/838 gegenüber 918/838),
ebenso die übernommenen Einträge (17 gegenüber 19, eine neue Modellzeile ohne
OCR-Beleg verworfen). Das ist ein beobachteter Laufzeitgewinn, kein kontrollierter
Nachweis gleicher Feldqualität. Es fehlen manuell geprüfte Referenzen für diese
PDF. Status bleibt wegen Feld-/Signaturunsicherheit `partial`.

Windows-Zähler im neuen Lauf: ca. 11,62 GB dediziert und 85,98 MB gemeinsam
genutzter GPU-Speicher; die frühere Auslagerung mehrerer GiB tritt nicht mehr auf.
CUDA-Peak allocated ca. 10,01 GiB, reserved ca. 10,53 GiB. Beim anschließenden
Modellwechsel blieb zunächst zusätzlich cuBLAS-Arbeitsspeicher reserviert, sodass
die Signaturprüfung in diesem Diagnoselauf nicht starten konnte. `close()` gibt
nun nach Synchronisation auch den Workspace-Cache frei. Dafür wird der in der
festgelegten PyTorch-2.8-Version vorhandene interne Hook defensiv abgefragt.

**Modellwechsel auf echter GPU erneut erfolgreich geprüft:** 5246 synthetische
Eingabetokens mit Chunking, danach LLM entladen und VLM im selben Prozess geladen.
Nach dem LLM sowohl `memory_allocated` als auch `memory_reserved` null; ca. 14,6 GiB
frei. Alle 4.437.815.808 VLM-Parameter auf `cuda:0`, Warm-up erfolgreich, nach
VLM-Entladen wieder keine CUDA-Allokationen. Die vorherige Allocator-Grenze wurde
wiederhergestellt. Messung unter `.cache/gpu-switch-check.json`; reine technische
Speicherprüfung ohne Dokumentdaten. Signaturnachprüfung der vorhandenen
Teilnehmerergebnisse anschließend erfolgreich in ca. 38 Sekunden unter
`runs/20261027T083827Z-158083d5/signature-review/20261027T085402Z-7bac329a/report.html`.
Die ursprünglichen Textextraktionen bleiben unverändert.

Unlimited-OCR, 22.10.2026: Native lokale Integration mit festgelegter Modellrevision
`8249d20b2822a7d8a4c22c8d8c9069b5ac36bda3`, ohne Ausführung von Checkpoint-Python-Code.
Eine referenzierte Safetensors-Datei (6672212480 Gewichtbytes) samt Tokenizer und
Konfiguration explizit heruntergeladen und per SHA256 inventarisiert. Separates
uv-Projekt `unlimited_ocr_runtime/`: Transformers 5.20.2, PyTorch 2.8.0+cu126,
Torchvision 0.23.0+cu126, HF Hub 2.2.0 und Safetensors 0.8.0. Die bestehende
Hauptumgebung bleibt bei Transformers 4.57.6; die API-Umgebung bleibt getrennt.
`trust_remote_code=False`, `local_files_only=True`, Offline-/Telemetriesperren
und reine CUDA-Zuordnung sind im Worker gesetzt.

**214 lokale Tests und 38 API-Tests bestanden.** Zehn neue lokale Testfälle
prüfen Zellzuordnung, Umlaute/Eigennamen, führende Nullen, leere Benutzerfelder,
fehlende/verbundene Zellen, Rohtext, PDF-/PNG-/JPEG-Eingaben, Resume, Weiterlauf
nach Seitenfehlern, Textbewertung und die Abgrenzung reiner OCR von Feldmetriken.
Zusätzlich trennt `raw_exact_match` buchstäbliche Schreibweise von der bisherigen
normalisierten Feldbewertung. Nach abschließenden Berichts-/Provenienzänderungen
sind 39 gezielte OCR-/Evaluierungstests und erneut alle 38 API-Tests erfolgreich.
Ruff, beide lokalen Lockprüfungen und `git diff --check` sind erfolgreich.

**Echte GPU-Inferenz durchgeführt:** `runs/20261022T122134Z-405f63e7/report.html`.
Zwei synthetische PDF-Seiten mit je denselben drei vorab festgelegten Personen;
die zweite Seite hat PDF-Rotation 90 Grad und wurde durch OSD zusätzlich um
270 Grad korrigiert. Beide Seiten wurden einzeln auf der RTX 4090 Laptop GPU
verarbeitet: Batch 1, BF16, SDPA, dynamische Bildausschnitte, maximal 4096 neue
Tokens, ein Warm-up, ein Modellladen und zwei produktive Modellaufrufe.
Ergebnis: sechs korrekt zugeordnete Zeilen, **24/24 Textfelder sowohl buchstäblich
als auch normalisiert korrekt**, darunter leere Benutzer und Personalnummern
mit führenden Nullen. CER/WER auf unabhängig aus der Konstruktion erstellten
Seitentranskripten: normalisiert 0 auf 364 Zeichen beziehungsweise 50 Wörtern.
Textmetriken mit Referenz- und Vorhersagehashes unter `unlimited_ocr/text_evaluation/`.
Signaturreferenzen bleiben unbekannt; keine Signaturqualität wird daraus behauptet.

Gemessene CUDA-Peaks: ca. 7,90 GiB allocated, 9,00 GiB reserved. Im letzten Lauf
ca. 51 Sekunden produktive Seitenverarbeitung und ca. 81 Sekunden Gesamtlaufzeit
einschließlich Vorbereitung, Prüfsummen, Initialisierung und Berichten.
Ein früherer Funktionslauf (`20261022T121441Z-5b53c550`) war schneller; dies waren
keine kontrollierten Performance-Wiederholungen und begründet keinen Laufzeitvergleich.
Die Tesseract-/Regelbaseline lieferte auf derselben Konstruktion 16/24 Felder,
unter anderem wegen fehlender Benutzer-Headerzuordnung. Das ist ein Vergleich
ganzer Pipelines auf einem kleinen technischen Beispiel, kein unabhängiger
Nachweis besserer OCR für reale Vorlagen.

Separater echter PNG-/OCR-only-Lauf: `runs/20261022T121545Z-7237ac00/report.html`,
lokal und erfolgreich, ohne künstliche Teilnehmerdatensätze. Normalisierte CER/WER
jeweils 0 auf 182 Zeichen/25 Wörtern. Die ursprüngliche Zeichen-CER beträgt wegen
unterschiedlicher Tabs und Zeilenumbrüche 26/184; diese Differenz wird nicht versteckt.
JPEG ist in der automatisierten Bildverarbeitung getestet, nicht zusätzlich als
echte Modellinferenz. Handschrift und reale Unternehmensdokumente wurden mit dem
neuen Modell nicht evaluiert. Keine Dokumentinhalte an externe Dienste übertragen.

Anleitung, Grenzen und Einzel-/Benchmarkbefehle: [Unlimited-OCR](unlimited-ocr.md).
Der neue Starter `start_unlimited_cv_test.cmd` verwendet ausschließlich den
vorhandenen CV-Testordner; bisherige Starter und Standardmodelle bleiben erhalten.

Ergänzung zum CV-Teststart am 22.10.2026: `start_lokal_cv_test.cmd` verarbeitet
nur `data/cv-test-20261020-093337/` mit lokaler Konfiguration und `--offline`.
Die Eingabeprüfung wurde aus dem Repository-Hauptordner gestartet und findet
genau eine PDF, ohne diese zu analysieren. Die API-Startdatei liegt separat unter
`api_firmen_pc/start_api_cv_test.cmd` und verwendet den gleich benannten Ordner
im API-Projekt. Bei leerem API-Ordner stoppt sie vor dem Laden von Zugangsdaten.
Vier gezielte Start-/Exporttests und Ruff sind erfolgreich. Das aktualisierte
Quellpaket mit API-Startdatei heißt `api_firmen_pc/dist/firmen-pc-cv-test.zip`;
es enthält weiterhin keine Dokumente, privaten Beispiele oder Modellgewichte.

Stand nach der Trennung am 22.10.2026: Der API-Betrieb liegt vollständig im
eigenen uv-Projekt `api_firmen_pc/`. API-Adapter, Verbindungskonfiguration,
Starthelfer und Tests sind aus dem lokalen Einstieg entfernt. Gemeinsame
Analysefunktionen besitzen nur explizit registrierbare, backendneutrale
Erweiterungspunkte. Der lokale CLI-Import funktioniert bei gesperrtem Import des
Firmen-PC-Pakets; unbekannte externe Backends scheitern vor dem Lesen der PDFs.
Die lokalen Modellpakete wurden beim Synchronisieren mit `--extra models` erhalten.

**204 lokale Tests und 38 separate API-Tests erfolgreich.** Die API-Tests prüfen
unter anderem OAuth-Basic/Formular-Anmeldung, Tokenwiederverwendung, Gateway-Key,
PDF-Extraktion, Signaturprüfung, Resume, Exporte und den neuen `main.py smoke`-
Ablauf gegen einen lokalen Loopback-Server. Zugangsdaten und Dokumente sind
ausschließlich synthetisch. Keine interne Firmen-API wurde kontaktiert.
Die neue API-Umgebung enthält weder PyTorch noch Transformers. Ruff-Prüfungen,
`git diff --check` und beide Lockdateiprüfungen sind erfolgreich.

`api_firmen_pc/dist/firmen-pc.zip` wurde aus einer expliziten Quellenauswahl
erzeugt und separat unter `.cache/fc-bundle-check/` entpackt. Installation mit
`uv sync --locked --offline --no-dev` und Start von `main.py --help` in einer
neuen Umgebung sind erfolgreich; auch dort fehlen GPU-Modellpakete. Der Export
enthält keine PDFs, Modellgewichte, Zugangsdaten-Dateien, Runs oder privaten
Testskripte. Die bisherigen `test_url`-Dateien liegen unverändert unter
`api_firmen_pc/privat/test_url/` und sind von Git, Tests und Export ausgeschlossen.
Die echte OAuth-Registrierung und deren Netzwerkvoraussetzungen bleiben auf
dem Firmen-PC zu prüfen. Aktuelle Anleitung: [Firmen-PC-Projekt](../api_firmen_pc/README.md).

Ergänzung 22.10.2026: Das separate API-Testskript `test_url/main.py` prüft
Client-ID, Client-Secret und Modellkennung vor dem Verbindungsaufbau. Es akzeptiert
`CLIENT_ID`/`CLIENT_SECRET` und alternativ `BMW_AI_CLIENT_ID`/`BMW_AI_CLIENT_SECRET`;
der Header verwendet die geprüfte ID. Fehlende Werte erzeugen eine Meldung mit
Variablennamen statt des HTTPX-Fehlers über einen `None`-Header. **44 gezielte Tests
erfolgreich**, davon zwölf neue Startprüfungen ausschließlich mit synthetischen
Werten und ersetzten Clients/Tokenhelfern. Keine realen Zugangsdaten gelesen und
keine interne API aufgerufen. Die bestehenden API-/Starthelfertests bleiben erfolgreich.

Stand 22.10.2026: Lokale OCR-Kalibrierung unter
`verarbeitung/src/participant_bench/calibration/` integriert. **233 Tests erfolgreich**,
darunter 19 neue Fälle für Referenzzuordnung, gruppierte Aufteilung, CER/WER,
ECE/Brier, Sigmoid/Isotonic, Audit-Sperren, Koordinatentransformationen,
PDF-Text und hybride PDFs, Exporte, Resume und Anwendung ohne Ground Truth.
Vorhandene 214 Regressionstests bleiben erfolgreich. `ruff check` und
`git diff --check` sind ebenfalls erfolgreich.

Vollständiger synthetischer CLI-Lauf: `runs/c-smoke22/report.html`. 20 einseitige
PDFs in zehn unterschiedlichen Layoutfamilien, je zwei verwandte Kopien in
derselben Gruppe. Aufteilung: zwölf Entwicklungsdokumente, zwei für die
Schwellenwertsuche, zwei für das unabhängige Audit und vier für den finalen Test.
Baseline mit echtem lokalem Tesseract und Variante mit direktem PDF-Text wurden
verglichen. Entwicklung: jeweils 96/96 Textfelder, Audit: jeweils 16/16.
Die schnellere PDF-Text-Variante wurde vorgeschlagen, wegen unzureichender
unabhängiger Auditgruppen jedoch nicht übernommen. Alle vier Feldregeln blieben
`review_only`; es wurde keine Kalibrierungsqualität aus der kleinen fehlerfreien
Stichprobe abgeleitet.

Der anschließend getrennt gestartete finale Test liegt unter
`runs/c-smoke22/test/report.html`: vier Dokumente, acht Teilnehmer, 32/32 Textfelder,
keine fehlenden/zusätzlichen Personen, normalisierte Text-CER/WER jeweils 0 auf
616 Referenzzeichen bzw. 88 Wörtern. Selbstständige SVG-/PNG-Reliability-Diagramme
und CSV-/JSON-Ausgaben sind erzeugt. Der komplette Entwicklungslauf dauerte etwa
15 Sekunden; der finale Benchmark-Unterlauf etwa 3,6 Sekunden, ohne manuelle
Annotation und ohne externe Inferenz. Kein Beleg für Qualität echter Scans oder
Handschrift. Echte geprüfte Referenzen stehen für diesen Kalibrierungslauf nicht
zur Verfügung; Standardparameter wurden nicht automatisch geändert.

Neue Befehle: `ocr-reference`, `ocr-split`, `ocr-calibrate`, `ocr-final`, `ocr-apply`.
Anleitung und wissenschaftliche Grenzen: [OCR-Kalibrierung](ocr-calibration.md).
Matplotlib wurde über uv installiert und in `uv.lock` festgelegt; die bestehende
lokale Modellumgebung wurde erhalten. Dokumente, Referenzen und OCR-Ergebnisse
wurden an keine externen Dienste übertragen.

Stand 21.10.2026, `participant-json-v10-empty-user-cells`: VLM-Anweisung und
Feldbeschreibungen trennen Benutzer/User ID von Kurzzeichen nach Spaltenposition.
Sichtbar leere Benutzer bleiben `""/empty`; die Person und ihr Kurzzeichen bleiben
erhalten. Nur aus Leerzeichen bestehende Antworten werden ebenfalls als leere
Zelle normalisiert; unbekannte/geschwärzte Werte bleiben `null/uncertain`.
Die gemeinsamen Prompts werden lokal und im API-Adapter verwendet. Bestehende
Läufe werden nicht verändert; die neue Promptidentität verhindert eine Mischung
mit früheren Ergebnissen beim Resume.

**214 Tests erfolgreich**, einschließlich neuer Fälle für leere Benutzer,
unbekannte IDs, Leerraum, alphanumerische IDs und korrekten CSV-Export. Zusätzlich
ein echter lokaler Lauf mit Qwen3-VL-4B-Instruct auf einer eigens erstellten
zweiseitigen PDF: `runs/20261021T081431Z-48ddf9f6/report.html`. Zwei unterschiedliche
Spaltenreihenfolgen, zehn Teilnehmer, sechs leere Benutzerfelder, Kurzzeichen mit
Ziffern/Trennzeichen und vier leere Kurzzeichenfelder. Ergebnis: **40/40 Textfelder
korrekt**, alle zehn Teilnehmer erhalten; Benutzer und Kurzzeichen je 10/10.
Beide Seiten erfolgreich; etwa 41 Sekunden insgesamt. Keine API-Anfrage, keine
realen Daten und keine zusätzliche OCR-/Signaturinferenz im Testlauf. Generator:
`scripts/make_empty_user_smoke.py`; Konfiguration: `configs/empty-user-smoke.yaml`.
Dies ist ein synthetischer Funktionstest, keine Qualitätsgarantie für echte Scans.

Ergänzung 21.10.2026: Privater manueller API-Start über
`scripts/run-private-api.ps1`. Die Option `-Persist` wurde entfernt;
Zugangsdaten werden nur im gestarteten Prozess gesetzt und nach dem Lauf
entfernt. Eine externe `NAME=WERT`-Datei wird ausschließlich über den expliziten
Parameter `-EnvFile` eingelesen, ohne Codeausführung oder Variablenexpansion.
Repository-interne Pfade und ungültige/mehrfach belegte Einträge werden abgewiesen.
**32 API- und Starthelfer-Tests erfolgreich**, darunter sieben neue Fälle mit
separaten PowerShell-Testprozessen und ausschließlich synthetischen Schlüsseln.
Geprüft wurden die Übergabe an Python, das Ausbleiben von Schlüsselwerten in
der Konsolenausgabe und das Entfernen nach Erfolg bzw. Importfehler. Beim Test
des Starthelfers wurde `-CheckOnly` verwendet; es fand kein API-Aufruf statt.
Dies ist keine technisch erzwungene Zugriffssperre gegenüber Prozessen mit
gleichen Dateirechten; die Trennung und ihre Grenzen stehen in der API-Anleitung.

Stand 21.10.2026: Optionale API-Backends für OCR/LLM und VLM ergänzt, einschließlich
OAuth-Client-Credentials und API-Key aus Umgebungsvariablen. **201 Tests erfolgreich**,
darunter 25 neue API-Fälle mit einem Loopback-HTTP-Server und ausschließlich
synthetischen Namen/PDFs. Geprüft wurden Key-/OAuth-Anmeldung (Body und Basic),
Tokenwiederverwendung und Erneuerung, Timeout-/HTTP-Fehler, Redirect-Sperre,
OCR-Feldbelege, Bildübertragung, JSON-Verträge, abgeschnittene Ausgaben sowie
PDF → Teilnehmer → Signaturdetails → Bericht, Resume und Signatur-Cache.
Die erzeugten Konfigurationen, Berichte, Rohdaten und Caches wurden auf die
synthetischen Zugangsdaten geprüft; diese werden dort nicht gespeichert.

`ruff check` für Quellcode/Tests/Skripte/Vorverarbeitung und PowerShell-Syntaxprüfung
des Einrichtungshelfer-Skripts sind erfolgreich. `api-check` ohne Verbindungsoption
meldet erwartungsgemäß fehlende BMW-Variablen (Exitcode 1, kein Netzwerkzugriff).
Ein API-Lauf mit `--offline` wird vor dem Einlesen der PDFs abgewiesen.
Es wurden keine realen PDFs an einen Dienst übertragen und keine BMW-Zugangsdaten
verwendet. Der echte interne Endpunkt und sein Protokoll sind weiterhin nicht
verifiziert; die Vorlage ist kein Nachweis für eine bereits funktionierende
BMW-Verbindung. Einrichtung und Grenzen: [API-Anleitung](api.md).

Stand 20.10.2026: Die automatische Seitenklassifikation wurde entfernt. Alle
Seiten der manuell ausgewählten Eingabe-PDFs werden nun an die Extraktion
übergeben. Ältere Manifeste müssen neu vorbereitet werden. Die folgenden
historischen Messungen beziehen sich auf ihren damaligen Code- und
Konfigurationsstand.

Seit `participant-json-v9-signature-details` verwendet die lokale Konfiguration
eine zusätzliche gemeinsame Signaturstufe mit Qwen3-VL-4B-Instruct. Sie arbeitet
auf vergrößerten Zeilenbildern mit getrenntem Spaltenkontext. Die konservative
OpenCV-Baseline bleibt in den Smoke-Konfigurationen erhalten und kann weiterhin
keine positiven Unterschriftenentscheidungen treffen. A/B entladen vor dem
Signatur-VLM ihr Extraktionsmodell; C nutzt sein geladenes VLM weiter. Diese
Zusatzstufe macht die Signaturauswertung von A/B ausdrücklich zu einer Kombination
mit VLM. Die ursprünglichen VLM-Anweisungen und das Antwortschema für
Teilnehmerfelder stimmen mit dem Stand des Quelllaufs `20261020T101106Z-e12943df`
überein. Die getrennte Positionssuche ändert keine Personenfelder.

Fehlende Positionen stammen bevorzugt aus eindeutigen vorhandenen OCR-Wortbelegen;
widersprüchliche Namens-/ID-Zuordnungen werden dabei abgelehnt. Sonst erfolgt eine
separate lokale VLM-Lokalisierung auf einer expliziten 0–1000-Skala. Nicht
lokalisierbare Zeilen bleiben offen. Der CLI-Befehl `signatures` prüft vorhandene
Personen ohne neue Teilnehmerinferenz nach, erhält den Quelllauf und schreibt
Quellprüfsummen, Ausschnitte, Rohantworten und neue Signaturmessungen separat.
Alte Qualitätsmetriken werden nicht als neue Evaluation übernommen.

Echte lokale Nachprüfung von B:
`runs/20261020T102932Z-895bb966/signature-review/20261020T111004Z-7dd2d1ab/`.
Auf Seite 1 neun positive Detailbefunde statt neun unbekannter Signaturen;
auf Seite 2 vier positive Befunde und sechs offene Fälle. Die ursprünglichen
Personenfelder und Quelldateien blieben erhalten.

Echte lokale Nachprüfung der 18 gespeicherten VLM-Personen des Laufs
`20261020T101106Z-e12943df`: Auf Seite 1 neun positive Detailbefunde statt zuvor
zwei positiven Gesamtbildentscheidungen. Auf Seite 2 fünf positive Detailbefunde
und vier nicht lokalisierte Signaturfelder. Die neun vorhandenen positiven
Gesamtbildentscheidungen bleiben dort erhalten; die vier unklaren Detailbefunde
werden separat ausgewiesen und sind keine zusätzlichen bestätigten Treffer.
Insgesamt stammen elf Zeilenpositionen aus OCR-Wortbelegen und sieben aus der
separaten VLM-Lokalisierung. Ohne manuelle Referenzlabels sind das keine
validierten Precision-/Recall-Werte.
Aktueller Bericht mit getrennten Gesamtbild- und Detailentscheidungen:
`runs/20261020T101106Z-e12943df/signature-review/20261020T113027Z-8967691a/report.html`.
Dieser abschließende Durchlauf verwendet 18 Cachetreffer und keine neue
Dokumentinferenz. Ein Vergleich bestätigt unveränderte Personenfelder und
Zeilenreferenzen für beide Seiten. Die ursprünglichen echten Detailaufrufe
stehen im Lauf `20261020T112415Z-8fb77fb8` unter derselben `signature-review/`-Wurzel.

Ein zusätzlicher echter lokaler VLM-Test mit einer synthetischen PDF prüft ein
leeres Feld, eine gezeichnete Unterschriftsmarkierung und gedruckten Text:
Erwartet und erhalten wurde `[false, true, null]`, drei Detailaufrufe in 3,31 s
ohne Modellsetup. Artefakte: `runs/signature-synthetic-1a1ef482/verification.json`.
Dies prüft diese drei künstlichen Fälle, keine echte Handschriftverteilung.
176 automatisierte Tests bestanden, einschließlich Signaturzuständen,
Quellerhalt, Cachewiederverwendung, Positionskonflikten, unveränderten
Personenfeldern sowie getrennten Aufrufen und der Modell-Entladereihenfolge.

Seit `participant-json-v8-ocr-lines` erhält das OCR-Sprachmodell zusätzlich zur
Worttabelle den lesbaren Zeilentext mit Zeilen- und Wortkennungen. Die Feldprüfung
verwendet diese OCR-Zeilen vor dem geometrischen Vergleich. Äußere Satzzeichen
werden nur beim Vergleich toleriert; die Ausgabe behält die OCR-Schreibweise.
Echte Zuordnungen zu einer anderen OCR-Zeile bleiben gesperrt und bekommen einen
eigenen Hinweis. Der pauschale Hinweis auf geschätzte Modell-Bounding-Boxes wird
für OCR-basierte Positionen nicht mehr ausgegeben. Ein unbekannter Signaturstatus
bleibt unabhängig von den gelesenen Textfeldern sichtbar.

Auf den beiden Entwicklungsseiten des Laufs `20261020T101106Z-e12943df` umfasst
der neue Prompt 5485 bzw. 2396 Token (Limit 12000), ohne OCR-Wörter abzuschneiden.
Eine lokale Nachprüfung der gespeicherten Antworten reduziert fehlende Textfelder
von zwölf auf acht bei unverändert fünf teilweise belegten Zeilen. Dabei wurde
keine neue Inferenz ausgeführt und der alte Bericht nicht verändert. Dies belegt
die korrigierte Wortprüfung, nicht die Richtigkeit oder Vollständigkeit der OCR.
158 automatisierte Tests bestanden. Neue Regressionen prüfen abweichende
Wortkastenhöhen derselben OCR-Zeile, überlappende Kästen verschiedener Zeilen,
getrennte OCR-Blöcke, äußere Satzzeichen, zusätzliche gültige Wortreferenzen und
die Disambiguierung wiederholter Namen über explizite OCR-Zeilenkennungen sowie
die unveränderte gedruckte Schreibweise von Zeilennummern mit Satzzeichen.

Im echten lokalen Lauf `20261020T102932Z-895bb966` liefert B auf der ersten
Entwicklungsseite neun statt fünf Zeilen. 34 von 36 Textfeldern haben einen
OCR-Beleg (im bisherigen Lauf acht von 20); die zuvor festgestellten
zeilenübergreifenden Feldkombinationen treten in dieser Antwort nicht mehr auf.
Niedrige OCR-Confidence, abweichende Modell-Wortreferenzen und zwei nicht belegte
Felder bleiben als Prüfhinweise sichtbar. Die reine Modellgenerierung dieser
Seite dauerte 1013,9 Sekunden bei 918 Ausgabe-Token. Der größere Textumfang und
das CPU-Offloading machen dieses Verfahren hier langsam; dies ist keine
kontrollierte Laufzeitstudie oder validierte Genauigkeitsmessung.
Der Lauf ist mit beiden Seiten abgeschlossen. Auf Seite 2 liefert B zehn
Zeilen mit 37 von 40 belegten Textfeldern; 13 Felder haben niedrige OCR-Confidence.
Eine Mehrdeutigkeit und ein nicht beobachteter Wert bleiben gesperrt. Die reine
Generierung dauerte dort 575,6 Sekunden bei 838 Ausgabe-Token. Es gab keine
technisch fehlgeschlagenen Seiten. Beide Seiten bleiben `partial` und erfordern
Kontrolle; insbesondere die zusätzliche Ausgabe auf Seite 2 ist ohne manuelle
Referenzlabels kein Nachweis zusätzlicher richtiger Teilnehmender. A liefert auf
dieser Vorlage weiterhin OCR-Klartext als Fallback, aber keine strukturierten
Felder. Der Ergebnisbericht liegt unter
`runs/20261020T102932Z-895bb966/report.html`.
Der abschließende Randfall-Fix für gedruckte Zeilennummern wurde nachprüfbar auf
beide gespeicherten Antworten angewendet: Feldwerte und Zeilenreferenzen stimmen
mit den gespeicherten Ergebnissen überein, es gab keine neue Inferenz.

Seit `participant-json-v7-partial-ocr-fields` sind vollständige OCR-Klartexte und
die per Hash verifizierte LLM-Eingabe unabhängig vom Extraktionserfolg im Bericht
verfügbar. Die Feldprüfung erhält teilweise belegte Zeilen, maskiert unbelegte
oder fremden OCR-Zeilen zugeordnete Felder und übernimmt vollständige beobachtete
Wörter statt Teilzeichenfolgen. Der gespeicherte Lauf
`20261020T093657Z-294ed368` wurde ohne neue Modellinferenz nachgeprüft:
`runs/20261020T093657Z-294ed368/revalidated/report.html`.
Vier teilweise belegte Datensätze mit acht fehlenden Textfeldern bleiben erhalten;
das sind keine vier vollständig oder nachweislich richtig erkannten Teilnehmer.
Originale Modellantworten und Messwerte sind unverändert vorhanden.
150 automatisierte Tests bestanden, einschließlich zeilenübergreifender
Fehlzuordnungen, Teilzeichenfolgen, Originalschreibweisen, niedriger OCR-Confidence,
unabhängiger Klartextexporte, Prompt-Hashes und Aktualisierung alter Berichte.

Tesseract PSM 11 wurde auf denselben Entwicklungsseiten getrennt ausprobiert.
Erkannt wurden 122/46 statt 138/51 Wörter, davon 94/22 statt 85/18 mit Confidence
von mindestens 60. Diese Confidence-Werte sind keine Richtigkeitsmessung; der
Standardmodus PSM 6 bleibt erhalten. Versuchsdaten liegen lokal unter
`runs/20261020T093657Z-294ed368/ocr_experiments/`, eine optionale Konfiguration unter
`configs/ocr-sparse.yaml`. Für den realen Datensatz fehlen weiterhin manuelle
Referenzlabels als Grundlage belastbarer Qualitätsaussagen.

Seit Prompt `participant-json-v6-compact-ocr` erhält das OCR-Sprachmodell eine
kompakte Worttabelle und liefert Feldwerte mit beobachteten Wort-IDs. Auf der
betroffenen Entwicklungsseite sinkt die Eingabe von 19701 auf 4194 Token,
auf der zweiten Seite auf 1867 Token (Limit jeweils 12000). Alle OCR-Wörter
bleiben erhalten. Auch die beiden OCR-Verfahren sichern Text-Fallbacks.
Mehrteilige Überschriften und Vorlagen mit zwei eindeutigen Teilnehmerfeldern
werden unterstützt; unbekannte Tabellen werden nicht durch erfundene Zuordnungen ersetzt.
143 automatisierte Tests bestanden. Neue Tests prüfen den Erhalt aller Wörter,
strikte Wortreferenzen, führende Nullen, mehrteilige Überschriften, explizite
Vorlagen sowie OCR-Fallbacks bei leeren und fehlgeschlagenen Modellantworten.
Die Fallback-Integration verwendet echte lokale Tesseract-Erkennung; die
Sprachmodell-Doubles prüfen nur den Ablauf und sind kein Qualitätsnachweis.

Echter lokaler OCR-Lauf: `runs/20261020T092258Z-dc9ad021/`, zwei Entwicklungsseiten.
Kein Eingabelimit überschritten; die OCR-Texte bleiben auf beiden Seiten erhalten.
Das Sprachmodell lieferte vier Zeilen auf Seite 1, davon zwei mit ausreichendem
OCR-Beleg; Seite 2 blieb ohne Teilnehmer. Die zunächst angewendete strikte
Seitenprüfung verwarf auf Seite 1 auch die belegbaren Zeilen. Die aktuelle
Zeilenprüfung behält diese zwei Zeilen und protokolliert die anderen separat.
Die gespeicherten Antworten wurden ohne neue Inferenz nachgeprüft:
`runs/20261020T092258Z-dc9ad021/revalidated/report.html`.
Dieser Bericht enthält keine neue Laufzeitmessung. Originaler Run und originale
Modellantworten bleiben erhalten; Quelle und Prüfcodes stehen in `revalidation.json`.
Es liegen keine manuellen Referenzlabels für einen Qualitätsnachweis vor.

Der VLM-Prompt `participant-json-v5-text-fallback` extrahiert vorrangig
Teilnehmerdaten. Nur bei fehlenden Teilnehmern wird der lesbare Seitentext als
Fallback ausgegeben und zur manuellen Prüfung markiert. Die folgenden Messungen
mit Prompt v4 dokumentieren die zuvor verwendete vollständige Transkription.

Für Prompt v5 wurden 127 automatisierte Tests bestanden. Zusätzlich bestätigt
ein echter lokaler VLM-Lauf mit drei synthetischen Seiten das bedingte Verhalten:
zwei Teilnehmende ohne Listenüberschrift erkannt, dabei kein Volltext ausgegeben;
ein Informationsblatt als Text-Fallback erhalten; eine Leerseite ohne erfundene
Inhalte verarbeitet. Laufzeit rund 27,5 Sekunden, keine Reparaturaufrufe:
`runs/20261020T085034Z-0ff646a0/report.html`. Das ist ein Funktionstest anhand
synthetischer Daten, keine Zuverlässigkeitsaussage für den gesamten Datensatz.

Der VLM-Prompt `participant-json-v4-page-text` las zusätzlich den gesamten
lesbaren Seitentext aus und verwendet ein kompaktes Teilnehmerformat. Das
konfigurierte Ausgabelimit beträgt 8192 Token. Abgeschnittene Antworten sind
als Ausgabeprobleme ausgewiesen und bleiben unverändert einsehbar.
125 automatisierte Tests bestanden, einschließlich Antwortformat, Fehlerweitergabe,
Seitentextexport und HTML-Escaping. Die Antwort-Doubles dieser Tests prüfen
Datenverträge und Ablauf, keine Erkennungsqualität.

Ein erneuter echter lokaler VLM-Lauf auf den zwei vom Nutzer ausgewählten Seiten
lieferte zwei gültige Antworten und 18 Teilnehmereinträge in rund 87,5 Sekunden:
`runs/20261020T084404Z-0a0fc90f/report.html`. Beide Seiten wurden verarbeitet;
keine automatische Seitenauswahl und keine Reparaturaufrufe. Dies bestätigt die
technische Ausführbarkeit, nicht die inhaltliche Richtigkeit oder Vollständigkeit:
Für diesen Lauf liegen keine manuell annotierten Referenzwerte vor.

Umgebung und Datum: Windows 11, 14.10.2026. Exakte Umgebungsdaten liegen lokal in
`runs/doctor.json` und zusätzlich pro Run in `environment.json`.

- uv 0.13.1; Python 3.12.15 projektlokal durch uv eingerichtet.
- `uv sync --locked --extra models --offline` erfolgreich nach dem Setup.
- PyTorch 2.8.0+cu126: `cuda.is_available() == True`, RTX 4090 Laptop GPU.
- Transformers 4.57.6: `Qwen3VLForConditionalGeneration` importiert.
- Tesseract 5.4.0: deutsche/englische Sprachdaten und OSD geprüft.
- 23 Tests bestanden, inklusive echter Tesseract-Inferenz und Offline-Integration,
  manueller 180°-Korrektur und separater Erfassung von technischen/Schemafehlern.
- Pipeline A auf sechs synthetischen Seiten: 24/24 Textfelder korrekt, sechs
  Teilnehmende auf drei befüllten Seiten; Blank/Deckblatt/leere Liste enthalten.
  Physische Rotation und PDF-Metadatenrotation geprüft. Kein Ergebnis auf realen Daten.
- Mit kuratiertem Manifest und ohne Ground Truth echte CLI-Läufe durchgeführt.
- Lokale HTML-, JSONL- und CSV-Berichte erzeugt. Die frühen Run-Ordner dokumentieren
  ihren jeweiligen Code-/Konfigurationsstand; endgültige Abnahmeläufe folgen unten.

Beide festgelegten Modellrevisionen wurden tatsächlich heruntergeladen und ihre
Dateien gehasht. `download-models --transport range` verifiziert die LFS-SHA256
gegen Repositorymetadaten. Die spätere Inferenz wurde mit Netzwerkzugriff gesperrt
(`uv run --offline ... --offline`) ausgeführt.

Ein echter einzelner VLM-Smoke-Test mit Promptversion v3 war erfolgreich:
`runs/20261014T104453Z-88223e3b/report.html`. Zwei Teilnehmende, 8/8 Textfelder
korrekt; Modellinferenz rund 40,4 s; Peak-GPU-Allokation 10610332672 Bytes
(etwa 9,9 GiB). Die leere Unterschriftszelle wurde unbekannt beantwortet, sodass
die Signaturabdeckung für die bekannte negative GT 0/1 beträgt. Die synthetische
Strichmarke ist unbekannte GT und kein positiver Signatur-Qualitätsbeleg.

Die vorherigen echten VLM-Läufe wurden korrekt als failed protokolliert:
v1 widersprüchliche Signaturzustände, v2 Bounding-Box-Arrays statt Schemaobjekten.
Rohantworten bleiben in den jeweiligen Run-Ordnern. Keine automatische Reparatur
oder nachträgliche Umdeutung als erfolgreiche Extraktion. Die Promptpräzisierung
erfolgte ausschließlich anhand synthetischer Development-Daten, nicht auf Testdaten.

## Abschließender gemeinsamer realer Modelllauf

Verifizierter Befehl:

```powershell
uv run --offline --locked --extra models participant-bench run --input data/model-smoke/raw --ground-truth data/model-smoke/ground_truth.jsonl --config configs/local.yaml --offline
```

Ergebnis: **alle drei Verfahren success**, je eine tatsächlich verarbeitete Seite,
zwei Teilnehmende, 8/8 Textfelder Exact Match, keine zusätzlichen/fehlenden Einträge,
keine Schemafehler oder technischen Ausfälle. Dies ist ausschließlich ein
synthetischer Development-Smoke-Test, keine Qualitätsaussage über echte Formulare.

Run: `runs/20261014T105542Z-489dddee/`.

| Verfahren | Extraktion inkl. zugerechneter OCR/Signatur | Modell laden | Warm-up | GPU-Peak alloziert |
| --- | ---: | ---: | ---: | ---: |
| A OCR/Regeln | 0,295 s | – | – | – |
| B OCR/Qwen3-8B | 959,103 s | 3,961 s | 8,070 s | 13,69 GiB |
| C Qwen3-VL-4B | 40,910 s | 4,209 s | 0,931 s | 9,88 GiB |

Prüfsummen/Processor-Setup und gemeinsame Vorverarbeitung sind zusätzlich
in `full_pipeline_charged_seconds` erfasst (A 0,857 s, B 989,711 s, C 53,536 s).
Die reale gesamte Verfahrenszeit steht separat in `actual_method_wall_seconds`.
Die Werte stammen aus genau diesem Run, nicht aus einem Vergleich unabhängiger
Populationen oder kontrollierten Wiederholungsmessungen. Beim B-Laden liefen
abschließende CPU-Regressionstests parallel; die lange eigentliche B-Generierung
lief danach ohne weitere Modellinferenz. CPU-Offloading ist hier eine deutliche
praktische Einschränkung. Die dedizierte CUDA-GPU hat 16 GB, nicht 47 GB.
Zusätzlich ist Intel UHD Graphics als Displaytreibereintrag vorhanden; deren
gemeinsamer RAM ist kein zusätzlicher CUDA-VRAM.

Signaturen: Für die bekannte leere Zelle erreichen A/B Abdeckung 1/1; C antwortet
unknown, Abdeckung 0/1. Die Strichmarke ist unbekannte GT. Es gibt keinen positiven
Signatur-GT-Fall, daher sind positive Precision/Recall/F1 hier nicht bestimmbar.
Die Konfusionsmatrix und Unknown-Nenner bleiben sichtbar. Kein Beleg für die
Erkennung echter Unterschriften und keine Echtheitsprüfung.

Wichtige Ergebnisdateien:

- `report.html`: vollständig lokaler, lesbarer Vergleich.
- `summary.json`, `methods.csv`: Status und tatsächlich gemessener Aufwand.
- `metrics.json`, `quality.csv`: deskriptive Qualität mit Zählern/Nennern.
- `extractions.csv`, `<method>/extractions.jsonl`: normalisierte Ergebnisse.
- `<method>/raw.jsonl`, `<method>/attempts/`: echte Originalantworten und Versuche.
- `manifest.json`, `effective_pages.json`, `prompts.json`, `identity.json`,
  `environment.json`, `config.yaml`: Provenienz und reproduzierbare Einstellungen.

Die verifizierten A-Integrationsfälle umfassen zusätzlich sechs synthetische
Seiten mit Blank/Deckblatt/leerer Liste sowie 0/90/180/270-Grad-Behandlung.
Abschließender kuratierter A-Run mit `--split development`:
`runs/20261014T111517Z-d9f1ad49/report.html`, 24/24 Textfelder, vier ausgewählte
Seiten einschließlich leerer Liste und sechs Teilnehmende auf drei befüllten Seiten.
Die OCR-Wörter und Cacheidentität von A und B im gemeinsamen Modellrun wurden
zusätzlich auf Gleichheit geprüft. Der HTML-Bericht enthält keine externen
Bildquellen oder Skripte. Der abschließende `doctor` meldet beide Modelle verfügbar,
ein CUDA-Gerät, beide Windows-Displaytreibereinträge und keine Warnungen.
`uv sync --locked --offline` ohne Modell-Extra und ein realer A-Lauf funktionierten;
anschließend wurde das Modell-Extra wieder mit `uv sync --locked --extra models --offline`
hergestellt. `ruff check`, `ruff format --check`, Offline-Verhalten, unveränderte
Originale, Resume und Schemagenerierung sind geprüft.

Offene Grenzen: reale Vorlagen/Scans fehlen; Regeln und Grenzwerte müssen auf
Development-Daten angepasst werden. Kein validierter positiver Signaturklassifikator,
keine Evaluation echter Handschrift, keine statistisch belastbaren Qualitäts-
oder Einsparungsbehauptungen. PaddleOCR/HTR, Quantisierung und produktiver Import
sind nicht implementiert. Große Bestände wurden nicht verarbeitet.
