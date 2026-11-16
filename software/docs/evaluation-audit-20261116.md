# Evaluationsaudit vom 16.11.2026

Untersuchter Bericht: `testframework/ergebnisse/20261112T082436Z-ffc71ce9/report.html`,
Quelllauf `runs/20261112T075916Z-2ed08591`. Der bestehende Hauptbericht wurde mit
den eingefrorenen Ausgaben aktualisiert, ohne neue Modellinferenz. Vorherkopie,
Dateihashes und aggregierte Prüfnachweise liegen privat unter
`data/evaluation-review-20261116/`. Bestehende spätere Extraktionsreparaturen
vom 12.11. werden hier **nicht** rückwirkend auf die Ausgaben angewandt.

## Befunde und Datengrundlage

Alle fünf Verfahren beziehen sich auf dieselben drei PDF-Inhalte, dieselben
sechs vorbereiteten Seiten und denselben eingefrorenen Referenzsnapshot.
Die Referenz enthält insgesamt 170 Personen aus elf Kursen. Im Eingabeumfang
liegen `146074` mit zwölf, `146079` mit 18 und `162575` mit 16 Personen:
46 Personen × vier lesbare Referenzfelder = **184 erwartete Felder je Verfahren**.
124 Personen anderer Kurse sind korrekt außerhalb des Umfangs; keine
mehrdeutige Dokument-Kurszuordnung, keine zusammengeführten Referenzduplikate,
keine nachträgliche Referenzänderung. Eine fehlgeschlagene Methode oder Seite
verkleinert diesen Nenner nicht.

Das beweist die rechnerische Vollständigkeit im gewählten Umfang. Die
Referenz ist eine Kursliste, keine unabhängig annotierte Seitenreferenz.
Ob jede Kursreferenz tatsächlich sichtbar ist und ob ID/Organisation im PDF
ausgefüllt sind, ist damit nicht unabhängig nachgewiesen. Für Publikationen
sind PDF-Anwesenheit, Sichtbarkeit und ausdrücklich leere Zellen unabhängig
zu annotieren. Fehlende Referenzpersonen erhalten keine erfundene PDF-Seite.
Die drei Dokumente wurden bereits zur Entwicklung verwendet.

Primäre Originalrollenbewertung (vor und nach dem Audit gleich):

| Verfahren | R | P | Exakt E | Falsch W | Fehlend M | Zusatzfelder | Ausgabezeilen | Identität exakt | Vier Pflichtfelder korrekt |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ocr_rules | 184 | 0 | 0 | 0 | 184 | 0 | 0 | 0 | 0 |
| ocr_llm | 184 | 95 | 74 | 17 | 93 | 4 | 26 | 18 | 8 |
| paddle_llm | 184 | 126 | 94 | 32 | 58 | 0 | 40 | 22 | 10 |
| vlm | 184 | 96 | 67 | 29 | 88 | 0 | 32 | 12 | 8 |
| ocr_vlm | 184 | 124 | 88 | 32 | 64 | 4 | 47 | 15 | 9 |

### Warum die Regelbaseline null erreicht

Alle sechs gespeicherten Ergebnisse enthalten **null strukturierte Personen**,
aber insgesamt 1.174 OCR-Beobachtungen. Damit ist null Feldqualität gegen die
Teilnehmerliste korrekt; null OCR-Erkennung wäre eine falsche Interpretation.
`rules.find_headers` mit der gespeicherten Konfiguration reproduziert:

| Dokument | Seite 1: erkannte Headerrollen | Seite 2: erkannte Headerrollen |
|---|---|---|
| 146074 | department | keine |
| 146079 | department, signature | keine |
| 162575 | row_ref, signature | first_name, row_ref, signature |

Auf fünf Seiten sperrt `rules.layout` wegen unzureichender Header den Tabellenbody.
Auf der sechsten Seite genügen zwar drei Rollen für die bestehende Headerprüfung,
aber es bleibt nur eine Textfeldspalte; auch dort entstehen keine Personen.
Insbesondere fehlen Benutzer-/kombinierte Namensspalten im erkannten Mapping.
Das Profil hat weder feste `rules.columns` noch `rules.body_top`. Die Baseline
nutzt anders als die Modellpfade keinen dokumentweiten Spaltenkontext.
Das ist eine Extraktions-/Vorlagenbegrenzung, kein Recall-Rechenfehler.
Headerregeln wurden in diesem Audit nicht anhand dieser Testwerte erweitert.

### Paddle: Abdeckung, Exact Recall und Teilnehmer

Field Coverage = (94 exakte + 32 falsche) / 184 = **68,48 %**.
Exact Recall = 94 / 184 = **51,09 %**.
Die Differenz entspricht 32 vorhandenen, aber falschen Feldern (17,39 Prozentpunkte).
Exact F1 = 2 × 94 / (184 + 126) = **60,65 %**.

| Feld | Exakt | Falsch | Fehlend |
|---|---:|---:|---:|
| Vorname | 31 | 4 | 11 |
| Nachname | 26 | 9 | 11 |
| ID | 25 | 2 | 19 |
| Organisation | 12 | 17 | 17 |

**40 Ausgabezeilen** wurden gepaart, sechs Referenzpersonen blieben ungepaart.
**22** ist der strenge Identitätszähler, nicht die Zahl extrahierter Zeilen.
Er verlangt einen eindeutigen Referenzanker und alle bestimmbaren Identitätsfelder
exakt. Bei zwölf dieser 22 Personen scheitert nur die Organisation: elf falsche
Werte und ein fehlender Wert. Daher bleiben **zehn vollständig korrekte Personen**.
Vier der elf falschen Organisationswerte entsprechen anderen Referenzzeilen;
das ist ein Zuordnungshinweis, kein Beweis einer Zeilenverwechslung.

Das Standardprotokoll erlaubt bei einem Paddle-Datensatz einen referenzgestützten
Tausch von Vor- und Nachname: 96 statt 94 exakte Felder, Recall 52,17 % und
F1 61,94 %. Das Dashboard bewertet die Originalrollen auf denselben Paaren.
Auch beim Hybrid liefert der Standardmodus 92 statt primär 88 exakte Felder.
Diese getrennten Ansichten sind Bewertungssensitivitäten, keine neu verbesserten
Extraktionen. Die bisherigen Definitionen bleiben erhalten.

Der historische Standardzähler `fully_exact_participants` verlangt nur, dass
alle **lesbaren nichtleeren** Referenzfelder einer gepaarten Person exakt sind;
Teilreferenzen und ausdrücklich leere Felder begrenzen diesen Zähler nicht wie
die neue Vollständigkeitsmetrik. Im Dashboard verlangt dagegen
`fully_correct_complete_participants` vier bestimmbare Pflichtfelder und deren
korrekten Inhalt beziehungsweise ausdrücklich leeren Zustand. Teilreferenzen
werden separat ausgewiesen. Bei diesen 46 vollständigen Referenzen erklärt
dies keine weitere Abweichung, bleibt für künftige Daten aber wesentlich.

### VLM und Laufzeiten

VLM besitzt sechs Seitenergebnisse, aber nur vier gültige Antworten. Auf Seite 2
von 146074 und 146079 werden jeweils 8.192 Ausgabetokens erreicht; beide Antworten
sind abgeschnitten und ungültig. Die Datenbasis wird deshalb als unvollständig
markiert, ohne Referenzen zu entfernen. Die zwei Fehlerseiten benötigen zusammen
rund 810,04 Sekunden von 958,47 Sekunden voller Methodenzeit.

| Verfahren | Volle Methodenzeit (s) | Median je Seite (s) | Cache-Seiten | Tatsächliche gespeicherte Modellaufrufe |
|---|---:|---:|---:|---:|
| ocr_rules | 0,59 | 0,069 | 6 | 0 |
| ocr_llm | 131,68 | 22,10 | 6 | 8 |
| paddle_llm | 101,41 | 0,104 | 6 | 2 |
| vlm | 958,47 | 37,60 | 0 | 6 |
| ocr_vlm | 289,54 | 47,94 | 6 | 6 |

Paddle verwendet auf allen Seiten den Strukturcache, auf vier Seiten zusätzlich
den Zuordnungscache. Zwei Seiten kosten rund 48,54 beziehungsweise 21,11 Sekunden,
vier nur 0,08–0,10 Sekunden. Der kleine Median ist mathematisch korrekt, aber
kein Maß für frische OCR-/LLM-Inferenz. Ladezeiten, Warm-up und dokumentweite
Nachverarbeitung gehören nicht in jeden einzelnen Seitenwert. „Charged“-Zeiten
können frühere Cache-Erkennungszeiten enthalten und sogar die aktuelle reale
Methodenzeit überschreiten. Das Dashboard trennt diese Größen bereits in E;
G ergänzt die tatsächlichen Cache-/Antwortbefunde pro Seite. Kein kontrollierter
Geschwindigkeitsvergleich oder neuer Laufzeitbenchmark wurde durchgeführt.

### Kopflose Folgeseiten

Die gespeicherten Entscheidungen belegen bei OCR+LLM und Paddle+LLM für 146079,
Seite 2, eine Übernahme von Seite 1 bei passender Geometrie. Für 146074, Seite 2,
wird wegen anderer gemessener Spaltenzahl abgelehnt. Hybrid hat dort mehrdeutige
Überschriften; direktes VLM scheitert vor erfolgreichem Mapping an der Antwort.
Aktuelle eindeutige Header haben Vorrang. Native Rohzellen, Validierung und
Spaltenquellen bleiben in `extraction_errors.html` nachvollziehbar.
Die aktuelle Extraktionsimplementierung ist inzwischen weiterentwickelt;
ihre Reparaturen sind separat dokumentiert in `headerless-columns-20261112.md`.
Eine neue Auswertung historischer Antworten führt diese Reparaturen nicht aus.

## Bewertungsregeln und Grenzen

`roster_benchmark/metrics.py` liefert weiterhin die einzigen Qualitätszähler:

```text
R = bewertbare nichtleere Referenzfelder
P = bewertbare nichtleere Ausgabefelder einschließlich Fehlwerten/Extras
E = exakte normalisierte Feldtreffer; S = summierte Levenshtein-Teilpunkte
R = E + W + M
Precision = E/P; Recall = E/R; F1 = 2E/(R+P)
Coverage = (R-M)/R
Soft-Recall = S/R; Soft-F1 = 2S/(R+P), separat
TP = E; FP = P-E; FN = R-E
```

Ein falscher Wert erzeugt FP und FN; das ist die PRF-Definition. Eine fehlende
Person erzeugt die fehlenden bewertbaren Referenzfelder. Teilnehmer-/Seitenfehler
werden nicht zusätzlich zu Feldfehlern addiert. Die Eins-zu-eins-Zuordnung
verhindert doppelte Gutschrift einer Ausgabe oder Referenzperson. Ungepaarte
Ausgaben liefern Zusatzfelder. ID-Platzhalter bleiben im Referenznenner und
zählen nichtleer zu P, aber als fehlende **nutzbare** Information zu M.

NFC, Text-Whitespace und Textkleinschreibung werden bereits normalisiert.
IDs werden außen getrimmt, numerische führende Nullen gemäß gespeicherter Option
entfernt. Innere ID-Leerzeichen und alphanumerischer ID-Buchstabenfall bleiben
verschieden. Akzente, Umlautumschreibungen, ß/ss und Bindestriche werden nicht
still repariert. Roh-Exaktheit, normalisierte Exaktheit, Namens-Swap-Sensitivität
und Levenshtein-Bewertung sind getrennte Größen.

Best-Fit maximiert zuerst lesbare Paarzahl, dann Feldähnlichkeit innerhalb einer
Schulung über alle Seiten/PDFs. Schwache und mehrdeutige Paare bleiben erhalten
und prüfpflichtig. Organisation beeinflusst die Paarung ebenfalls. Damit kann
eine falsche Organisationsangabe auch die Referenzpaarung beeinflussen.
Originalrollen sind **keine** referenzunabhängige Identitätsprüfung. Konservative
Zuordnung und Varianten ohne Namensswap bleiben als Sensitivitäten erhalten.
Eine zusätzlich gewünschte ankerbasierte unabhängige Identitätsvalidierung
benötigt ein vorab festgelegtes separates Protokoll und unabhängige Referenzen.

Die neuen Kategorien trennen fehlende Person, fehlenden Wert, ungültigen
Platzhalter, abweichenden Wert, Übereinstimmung in anderem Feld derselben Person,
Übereinstimmung mit anderer Referenzzeile und Zusatzwerte. Letztere sind ohne
Bildreferenz **keine nachgewiesenen Halluzinationen**. Nur gegen eine ausdrücklich
leere Referenz wird `hallucinated_empty` separat ausgewiesen. Unbekannte oder
maskierte Referenzen bleiben unbewertbar. Keine automatischen Korrekturen anhand
von Ground Truth und keine neuen Fehlertoleranzen wurden eingeführt.

## Korrekturen und Umsetzung

Zwei belegte Randfehler wurden behoben:

1. `TextField(state="empty", value=None)` ist laut gemeinsamem Schema genauso
   ausdrücklich leer wie `value=""`. Bisher zählten nur Leerstrings als korrekt
   leere Felder und vollständig korrekte Teilnehmer. Jetzt entscheidet derselbe
   gemeinsame Leerzustandsprüfer in Feld- und Teilnehmermetrik. Unbekannte
   `uncertain`-Nullwerte gelten weiterhin nicht als bestätigte Leerzellen.
   Fehlende Leerzellenerkennung wird außerdem als prüfpflichtig markiert.
2. Bei ungepaarten Ausgaben konnte reiner Whitespace aufgrund von `bool(value)`
   als Zusatzfeld P zählen. Jetzt entscheidet wie bei gepaarten Feldern die
   vorhandene Normalisierungsfunktion. Kein zusätzlicher normalisierter Wert,
   kein Zusatzfeldbeitrag.

Diese Fälle kommen im untersuchten gespeicherten Vergleich nicht vor. **Alle
Qualitätswerte bleiben unverändert**, ebenso `metrics.json`, Referenzsnapshot
und sämtliche Quelllaufdateien. Die neue Ansicht G enthält Feld- und
Teilnehmertabellen mit kombinierten Filtern, Suche, Gründen, Original-/Normalwerten,
R/P/E-Beiträgen sowie PDF- und Pipelinebeleglinks. Vorhandene Feldursachenanalyse
wird verlinkt und nicht neu implementiert. Neue private Exporte:

- `scientific/metric_audit.json`, `field_cases.csv`, `participant_audit.csv`
- `scientific/metric_audit_checks.json`: Abgleich jedes Feldzählers sowie
  strikter Identitäts-/Vollständigkeitszähler mit bestehenden Aggregaten

Neue Vergleiche und `testframework/main.py analyze --report … --output NEU`
enthalten die Ansicht automatisch. Der Originalreport wurde auf ausdrücklichen
Auftrag direkt aktualisiert; die ursprüngliche HTML-Fassung ist privat gesichert.
Implementierungshashes erfassen jetzt auch Matcher, Metriken und Auditdarstellung.
Ausgaben mit Einzelwerten bleiben lokal und gehören nicht in öffentliche Repos.

Regressionen decken Leerzustände, Whitespace-Extras, Fehlerkategorien,
Originalrollen, Roh-/Normalvergleich, Nenner, Quellenintegrität, reproduzierbaren
Replay und kombinierte JavaScript-Filter ab. Zahlen-/Link-/CSP-Prüfung wird
lokal protokolliert. Visuelle Browserabnahme bleibt offen: native Windows-Pipe
und Browserhost sind in dieser Sitzung nicht verfügbar.

Abgeschlossen: **888 Gesamttests bestanden (100,55 s)**; anschließend
**44 gezielte Tests (3,90 s)** einschließlich zusätzlicher Escaping-Regression,
**48 API-Tests (10,09 s)**, Ruff und regulärer Diff-Check bestanden.
928 Feldfälle und 232 Teilnehmerfälle stimmen mit den Aggregaten überein;
3.449 lokale Dateilinks ohne fehlendes Ziel. Alle 287 Quelllaufdateien unverändert.
Frühe Testläufe scheiterten an einem gesperrten alten Tempordner beziehungsweise
Windows-Pfadlängen; kürzere Testpfade beheben das. API-Starttests benötigen ihre
synthetischen Umgebungsdateien außerhalb des Repositories; mit geeignetem
temporärem Testverzeichnis bestehen sie ohne echte Zugangsdaten oder API-Aufrufe.
