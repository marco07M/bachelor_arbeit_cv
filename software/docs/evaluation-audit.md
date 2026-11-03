# Docling- und Evaluationsaudit vom 03.11.2026

## Umfang und reproduzierbare Artefakte

Ausgangspunkt ist `testframework/ergebnisse/20261103T081036Z-c0340c5a/` mit
Quelllauf `runs/20261103T075704Z-ae365514/`. Die Referenz ist eine vorhandene
Kursliste mit 18 Personen und 72 bewertbaren Informationsfeldern. Sie wurde
nicht verändert und ist keine unabhängig geprüfte Transkription beider PDF-Seiten.

Lokaler Abschlussvergleich: `runs/evaluation-audit-20261103-final/report.html`.
Die drei Unterberichte isolieren Änderungen:

1. `corrected-rules`: vorhandene Ausgaben, korrigierte Metriken, ursprüngliche Namensrollen.
2. `both-name-orders`: dieselben Ausgaben, beide Namensrollen als Referenzvergleich.
3. `repaired-docling`: neue Docling-Ausgabe, alle anderen Ausgaben unverändert.

`audit.json` dokumentiert die gemeinsame eingefrorene Referenz, identische
tatsächliche Laufbilder und unveränderte historische Dateien. Jeder Unterbericht
besitzt eigene Konfiguration, Referenzkopie, Code-/Datenhashes und Metrikversion.
Die Arbeitskopie `combined-source/` enthält einen neu aufgebauten Extraktionsbericht
und ein Herkunftsprotokoll; sie ist ausdrücklich ein zusammengesetzter Vergleich.
Personenbezogene Artefakte bleiben lokal und gitignoriert.

Reproduktion aus dem Softwareordner, jeweils mit neuem Ausgabeordner:

```powershell
.\.venv\Scripts\python.exe -m participant_bench.cli run --config configs/benchmark.yaml --input testframework/eingabe_pdfs --method docling --offline
.\.venv\Scripts\python.exe scripts/audit_metrics_docling.py --source-report testframework/ergebnisse/20261103T081036Z-c0340c5a --docling-run runs/20261103T084429Z-e2834b34 --output runs/evaluation-audit-reproduction
```

Der praktische Docling-Lauf ist `runs/20261103T084429Z-e2834b34/`.
Die isolierte Laufzeit ist vorhanden und wurde geladen. Beide Seiten nutzten
den vorhandenen OCR-/TableFormer-Cache; es gab **keine neuen Erkennungsaufrufe**
und keine Downloads. Das neue Mapping und die reguläre Speicherung liefen erneut.
Das prüft die Datenübergabe auf realen gespeicherten Erkennungsbelegen; es ist
kein neuer OCR-Qualitätsnachweis. Ladezeit dieses Laufs: rund 71,2 Sekunden,
gesamte Methodenlaufzeit rund 74,6 Sekunden. Cachezeiten sind keine Kaltstart-Inferenzzeiten.

## A. Docling: Ursache, Änderung und Grenzen

PDF-Vorbereitung, Rendering, lokale OCR, Layout-/Tabellenanalyse, Worker-Übergabe
und JSON-Speicherung funktionieren im Ausgangslauf. Seite 1 besitzt 153 OCR-Zellen
und eine native Tabelle mit 19 Zeilen/7 Spalten; Seite 2 besitzt 66 OCR-Zellen
und eine Tabelle mit 6 Zeilen/3 Spalten. Es handelt sich weder um einen fehlenden
Worker noch um einen Bericht, der intern vorhandene Teilnehmer versteckt.

In beiden Seiten fehlen verwertbare erkannte Feldüberschriften, sowohl in
OCR-Zellen als auch nativen Tabellenzellen. Der deterministische Mapper setzt
ohne Überschriften keine Feldzuordnung und überspringt deshalb sämtliche Zeilen.
Das ist der nachgewiesene Verlustpunkt. Warum die OCR bestimmte gedruckte
Überschriften nicht liest, ist ohne separat annotierte Regionen nicht weiter
als Detektions- oder Lesefehler belegt.

`structured_mapping.py` erhält jetzt einen begrenzten Fallback: Mindestens zwei
native Zeilen müssen eine kommagetrennte Namenszelle und eine separate numerische
Zelle in derselben eindeutigen Spaltenkombination enthalten. Mehrere konkurrierende
Kombinationen, ein einzelner Metadatensatz und beliebige Textblöcke genügen nicht.
Explizit vorhandene, aber mehrdeutige Überschriften werden nicht umgangen.
Nur diese belegten Identitätszellen werden als **unsichere Teilinformationen**
erhalten. Organisations- und Signaturspalten werden nicht geraten.
Unvollständige Namensgruppen können bei vorhandener ID als Teilperson erhalten
bleiben. Native Zellindizes, leere Zellen, Spans und Originaltext bleiben erhalten;
fehlende Zellen verschieben keine Nachbarwerte.

Nach der Änderung: 9 unsichere Teilpersonen auf Seite 1, weiterhin keine sicher
zuordenbaren Personen auf Seite 2. Im dokumentweiten Kursvergleich: 19/72 Felder
exakt, 6 falsch, 47 fehlend, Abdeckung 25/72, Levenshtein-F1 rund 48,65 %.
Die bekannte Organisationsüberschrift fehlt weiter; Organisation bleibt unbekannt.
Der Fallback behebt den vollständigen Datenverlust, nicht sämtliche OCR- oder
Tabellenfehler. Keine allgemeine Handschriftqualität und keine Identität behaupten.
Die reale PDF ist ein bereits verwendeter Entwicklungsfall, keine unabhängig
zurückgehaltene Testmenge.

`structure.py` speichert zusätzliche Stufenzähler, Mappingdiagnosen und die Zahl
unsicherer Fallbackpersonen; die bestehende Diagnose/Overlay-Funktion zeigt sie.
`table_mapping.py` bleibt der historische HTML-Pfad; er ist im Hauptprofil nicht
aktiv. Es wurden keine Referenzdaten oder zusätzlichen LLM-/VLM-Schritte eingeführt.

## B–D. Mathematische Prüfung und korrigierte Fehler

Die bestehende Mikroaggregation ist mathematisch korrekt:

```text
R = Zahl bewertbarer, erwarteter, nichtleerer Informationsfelder
P = Zahl ausgegebener bewertbarer, nichtleerer Feldwerte einschließlich Fehlwerten/Extras
E = exakte Treffer nach dokumentierter Normalisierung
C = Summe der Feldähnlichkeiten tatsächlich zugeordneter Paare

Exakter Feld-Recall = E/R
Exakte Precision = E/P
Exakter Feld-F1 = 2E/(R+P)
Levenshtein-Recall = C/R
Levenshtein-Precision = C/P
Levenshtein-Feld-F1 = 2C/(R+P)
```

Ein falsch ausgegebener Wert ist gleichzeitig FP und FN, eine fehlende Ausgabe
FN, ein zusätzlicher Wert FP. TP=E, FP=P−E, FN=R−E. Nullnenner bleiben undefiniert.
Die Soft-Metrik ersetzt E durch Teilpunkte C und ist ausdrücklich kein klassischer
binärer F1 und keine Wahrscheinlichkeit. `S=1−d/max(Längen)` bleibt unverändert.

Das verbindliche Beispiel liefert bei R=40, P=E=C=24 genau Recall 0,60,
Precision 1,00 und F1 0,75. Die 16 fehlenden Felder sind bereits im Referenznenner.
Ein höherer F1 als Recall ist daher kein Implementierungsfehler.

**Nachgewiesener Fehler:** Ein maskierter Modell-ID-Wert konnte bisher eine
lesbare Referenz-ID aus dem Nenner ausschließen. Das betraf Kursmetriken,
Best-Fit-Kandidatengutschrift und älteren strikten Excel-Vergleich. Jetzt bleibt
die Referenz bewertbar; die Modellangabe erhält null Punkte. Ein nichtleerer
Platzhalter zählt außerdem als ausgegebener Fehlwert. Unlesbare Modellwerte
begründen keinen Ground-Truth-Ausschluss.

**Weitere Korrektur:** Der seitenbezogene Evaluator konnte unklare, ausdrücklich
nicht als bekannt bewertete Modellwerte für CER dennoch verwenden. Er behandelt
sie jetzt konsistent als fehlende Erkennung. WER wird zusätzlich mit derselben
Edit-Distanz auf Wortfolgen angeboten; Extras sind Einfügungen. CER/WER können
größer als 1 sein und sind bei fehlendem Referenzumfang undefiniert.

Fehlende Teilnehmer waren bereits als fehlende Referenzfelder enthalten. Zusätzliche
Teilnehmer erzeugten bereits Vorhersagebeiträge. Diese funktionierenden Regeln
wurden erhalten. Technische Fehler und fehlende Ergebnisdateien entfernen keine
Kurse aus dem Referenznenner. Fehlende Ergebnisseiten und ungültige Antworten werden
gesondert gezählt. Eine bedingte Kursbewertung verwendet nur Kurse, deren sämtliche
Eingabeseiten technisch erfolgreich verarbeitet wurden, mit eigenem ausgewiesenem
Umfang. Eine konditionale Seitenbewertung gegen eine reine Kursliste wäre unbelegt.

### Ausschlüsse und tatsächliche Leerzellen

Referenzstatus entscheidet unabhängig vom Modell über die Bewertbarkeit.
Optional erlauben `<Feld>__state` oder `<Originalspaltenname> – Status` die Zustände
`read`, `empty`, `unknown`, `masked`, `illegible`, `uncertain`. Ohne Status bleiben
leere Kurslistenzellen unbekannt; sie werden nicht automatisch als bestätigte
Leerzellen interpretiert. Vorhandene Referenzen werden nicht umgeschrieben.

Bestätigte leere Felder werden separat gezählt. Ein korrekt leeres Feld liefert
keinen positiven Informationspunkt; ein erfundener nichtleerer Wert erhöht P.
Unbekannte oder maskierte Referenzfelder sind ausgeschlossen und mit Häufigkeiten
sichtbar. Fehlende Werte bei lesbarer Referenz bleiben Fehler.

Die manuell annotierte Seiten-Ground-Truth besitzt bereits `read/empty/...`.
Dort bleiben historische Allfeldmetriken erhalten; neue `information_prf` und
`information_exact_match` bewerten nichtleere Information, `empty_detection`
erfasst Leerzellen separat. Version: `page-ground-truth-v2-information-and-empty`.
Kursvergleichsversion: `roster-levenshtein-v5-reference-denominators`.

### Matching ist keine Feldmetrik

Best-Fit maximiert erst die Zahl lesbarer Paare, dann deren Feldähnlichkeitssumme.
Konservativ gelten eindeutige exakte ID-Priorität, Namens-/Kurzzeichen-Schwellen
und Ablehnung mehrdeutiger globaler Alternativen. Beide nutzen dieselbe Feldmetrik.
Eine höhere Best-Fit-Zahl kann allein durch andere Paarungen entstehen.
Bei unbekannten Referenzfeldern kann P zwischen Paarungsstrategien variieren;
beide R/P/C-Werte sind deshalb im Bericht gegenübergestellt. R muss gleich bleiben.

Auf früheren Nutzerwunsch kann der Vergleich beide Orientierungen vollständiger
Namensgruppen testen. Die größere Summenähnlichkeit der Namensfelder gewinnt;
bei Gleichstand bleiben Originalrollen. Die globale Einmalvergabe bleibt bestehen.
Tausche stehen in Teilnehmer-/Feldbelegen, beide Kandidatenwerte in
`matching_candidates.csv`. Originalextraktionen bleiben unverändert. Diese Option
misst rollenbereinigte Referenzübereinstimmung und darf nicht als unabhängige
Messung korrekt erkannter Vor-/Nachnamensrollen ausgegeben werden.

Im realen Ausgangsvergleich kommen keine ausgeschlossenen maskierten Modell-IDs
vor. Die reine Korrektur der Ausschlussregel verändert daher dort keine Scores.
Paddle bleibt bei 29/72 exakten Feldern, 36 fehlenden Feldern und F1 64,89 %:
exakter Recall 40,28 %, Abdeckung 50 %. Diese Zahlen sind miteinander vereinbar.
Die Namenoption erhöht VLM-F1 von 71,39 % auf 81,95 % und Hybrid-F1 von 72,31 %
auf 86,25 %, jeweils durch sieben getauschte Namensgruppen; keine neue Erkennung.
Der zusätzliche Docling-Schritt verändert ausschließlich Docling-Ausgaben.

## E. Einheitliche Ergebnisse

HTML-Feldtabellen zeigen Referenz, tatsächlich ausgegebenen Originalwert, eine
Bewertung nach Normalisierung, Ähnlichkeit und Begründung. Parallele Original-/
Normalisiert-Wertspalten und doppelte sichtbare Exaktheitsbewertungen entfallen.
Feldstatus, fehlende Werte und ein verwendeter Namenstausch bleiben sichtbar.
Originalwerte, normalisierte Werte, Distanzen und rohe Exaktheit bleiben in
CSV/JSON und dem eingefrorenen Quelllauf nachvollziehbar.

Die Übersicht trennt Qualität, Vollständigkeit, Zuordnung, technischen Erfolg
und Laufzeit. Korrekt + falsch + fehlend = R. Ungültige Platzhalter sind ein
offengelegter Teil fehlender nutzbarer Information; als nichtleere Vorhersagen
erzeugen sie zusätzlich einen FP, ohne fälschlich als Referenzausschluss zu gelten.
`metric_checks.json` überprüft gemeinsame Referenznenner und die Zähleridentität.
Excel enthält zusätzliche Metrik-/Feldmetrikblätter aus denselben berechneten
Ergebnissen. Die Detailberechnung verwendet dieselbe zentrale F1-Funktion.
Teilnehmer folgen weiterhin Eingabe-PDF, Seite und erkanntem Eintragsindex.

## F. Verifikation

Synthetische Tests prüfen vollständige, fehlende und zusätzliche Personen,
fehlende/fehlerhafte Felder, das 24/40-Kontrollbeispiel, Modell-Platzhalter,
bestätigte Leerzellen und unbekannte Referenzen, technische Ausfälle,
beide Matchingmodi, ganze doppelte Namensgruppen, Gleichstände, Reihenfolge,
HTML-/CSV-/Excel-/JSON-Konsistenz sowie Schutz der tatsächlichen Laufbild-Hashes.
Docling-Fälle umfassen reguläre Überschriften, explizit leere/fehlende Zellen,
mehrdeutige Überschriften, fehlende Überschriften mit wiederholtem Identitätsbeleg
und isolierte Metadaten, die keine Teilnehmer ergeben dürfen.

Erste Gesamtprüfung: 587 bestanden, ein Fehler in der Namensansicht. Der durch
die Tabellenvereinfachung verlorene Feldstatus wurde wieder eingeblendet;
alte Assertions zum ausdrücklich abgeschafften Maskierungs-Ausschluss und zu
alten Überschriften wurden angepasst. Abschließende Testzahlen stehen im
[Verifikationsprotokoll](verification.md) und in der Agentenübergabe:
**591 lokale Tests in 106,49 Sekunden und 48 API-Tests in 10,46 Sekunden bestanden**.
Ruff ohne Befund. Die API-Gegenprobe hatte abweichende Matchingoptionen gefunden;
beide öffentlichen Vorlagen sind jetzt konsistent. Es wurden keine API-Modelle aufgerufen.

## G. Empfehlung für die Bachelorarbeit

- **Primäre Qualität:** exakter Feld-Recall pro Feld und mikroaggregiert, daneben
  exakte Precision/F1 und zusätzliche Ausgaben. Bei IDs ist eine falsche Ziffer
  ein falscher Informationswert, unabhängig von hoher Zeichenähnlichkeit.
- **Ergänzende Qualität:** Levenshtein-Recall/F1 und CER/WER zur Beschreibung von
  Lesefehlern; keine Gleichsetzung mit korrekter Identität. Rollenbereinigte Namen
  zusätzlich mit ausgeschalteter Tauschoption vergleichen.
- **Vollständigkeit:** fehlende/inkorrekte Referenzfelder, Feldabdeckung und fehlende
  Teilnehmer; Zuordnungsabdeckung von vollständig exakten Teilnehmern unterscheiden.
  Die Referenzbasis und alle Ausschlüsse stets angeben.
- **Technik/Wirtschaft:** Seiten-/Dokumenterfolg, Fehlerarten und Laufzeit getrennt
  von Inhaltsqualität. Laden, Cache, Warm-up, OCR/Inferenz und Signaturprüfung
  nicht vermischen. Eine Zahlungsersparnis erfordert reale Prozess- und Kostendaten.

`ocr_raw` bleibt gegen strukturierte Kurslisten `not_applicable`. Seine CER/WER
benötigen unabhängige Seitentranskripte. Signaturpräsenz bleibt eine gesonderte
Aufgabe mit eigener Ground Truth; weder Transkription noch Echtheitsnachweis.
Weitere Dokumente und manuell geprüfte Seitenreferenzen sind für Aussagen über
generelle Modell- oder Handschriftqualität weiterhin notwendig.

## Primärquellen der methodischen Prüfung

- [scikit-learn: F1-Definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.f1_score.html):
  harmonisches Mittel und TP/FP/FN-Formel. Die Soft-Variante dieses Projekts ist
  eine separat definierte Teilpunktmetrik, kein Standard-Klassifikations-F1.
- [Hugging Face Evaluate: CER-Implementierung](https://github.com/huggingface/evaluate/blob/main/metrics/cer/cer.py):
  Edit-Operationen relativ zur Referenzzeichenanzahl.
- [Docling: erweiterte Optionen](https://github.com/docling-project/docling/blob/main/docs/usage/advanced_options.md)
  und [Pipelineoptionen](https://docling-project.github.io/docling/reference/pipeline_options/):
  TableFormer, OCR und Cell Matching sind getrennte Schritte. Die konkrete lokale
  Fehlerdiagnose oben stammt aus den eingefrorenen Laufartefakten, nicht aus einer
  allgemeinen Behauptung über Docling.
