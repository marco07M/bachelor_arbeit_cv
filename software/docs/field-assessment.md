# Feldstatus und Textähnlichkeit

Stand: 16.11.2026. Neuer Bericht aus eingefrorenen Ergebnissen:
`testframework/ergebnisse/field-states-20261116/report.html`.
Der historische Dreidokumentbericht und sein Extraktionslauf wurden nicht
überschrieben. Keine neue OCR-/Modellinferenz und keine Extraktionsreparatur.

## Fünf Status neben den unveränderten Feldbeiträgen

`roster_benchmark/field_assessment.py` ist die gemeinsame Entscheidung für
Feldmetriken, Standarddetailbericht, Fehlerbericht und Auditbereich G.

| Status | Bedeutung |
|---|---|
| Korrekt | Bewerteter Wert nach gespeicherter Normalisierung exakt; bestätigte Leerzellen werden separat behandelt. |
| Erkannt, aber abweichend | Nutzbarer zugeordneter Wert vorhanden, aber nicht exakt. Auch null Prozent Textähnlichkeit bedeutet nicht „fehlend“. |
| Nicht erkannt | Kein verwertbarer finaler Feldwert, einschließlich leerer/fehlender Ausgabe und ungültiger ID-Platzhalter. Daraus folgt kein belegter OCR-Fehler. |
| Zuordnung unklar | Vorhandener Text ohne gesicherte Personen-/Feldzuordnung, explizit mehrdeutige/widersprüchliche/duplizierte Paarung oder durch das Bewertungsprofil ausgeschlossener unsicherer Originalwert. Auch eindeutig belegte Textübergaben ohne Strukturübernahme beziehungsweise blockierte Zellzuordnungen werden so angezeigt. |
| Nicht bewertbar | Keine verlässliche Feldreferenz, etwa unbekannte oder maskierte Ground Truth. |

Die Status partitionieren **alle Feldfälle**, einschließlich zusätzlicher
Ausgabezeilen und ausgeschlossener Referenzfelder. Sie sind keine weitere
Feldfehlersumme. `metric_status` bewahrt die bisherige exakte Zählerpartition
`correct/incorrect/missing/extra/unassessed`. Beispielsweise erzeugt eine
ungepaarte Ausgabe mit Text den Anzeigestatus „Zuordnung unklar“ und weiterhin
einen Zusatzbeitrag P. Ihre ungepaarte Referenzperson bleibt mit ihren fehlenden
Referenzfeldern im Nenner R. Ein vorhandener, gemäß Profil nicht nutzbarer
unsicherer Rohwert wird sichtbar, ohne nachträglich gültig zu werden.

`Müller` gegenüber `Muller` ist bei gesicherter Paarung **abweichend**, trägt
weiterhin P=1, R=1 und E=0 bei und erhöht nicht M. Die existierende normalisierte
Levenshtein-Funktion liefert 5/6 beziehungsweise **83,33 %** Textähnlichkeit.
Es wird keine Umlauttoleranz oder neue Ähnlichkeitsmetrik eingeführt.

## Metriken und Identität

Unverändert bleiben Exact Recall = E/R, Exact F1 = 2E/(R+P), Coverage = (R−M)/R
sowie der getrennte Soft-Score aus Levenshtein-Teilpunkten. Falsch transkribierte
zugeordnete Werte erhöhen die Abdeckung, nicht E. Ganz fehlende Referenzpersonen
behalten sämtliche bewertbaren Feldstrafen. Ein unstrukturierter OCR-/Zelltext
erhöht die Feldabdeckung nicht automatisch.

Die strengen Identitäts-/Vollständigkeitszähler verlangen zusätzlich, dass die
Paarung nicht ausdrücklich als `ambiguous`, `identity_conflict` oder
`duplicate_prediction` markiert ist. Der historische Feldscore und historische
`fully_exact`-Zähler bleiben unverändert. Eine Best-Fit-Paarung allein bestätigt
keine Identität. Eine niedrige Feldähnlichkeit allein beweist dagegen weder eine
mehrdeutige Paarung noch fehlenden Text; `low_similarity` bleibt prüfpflichtig.
Die konservativen und Namensswap-Sensitivitäten bleiben separat verfügbar.

Die bewerteten Texte stammen aus derselben gespeicherten Paarung und
Normalisierung. In der historischen Standard-Swapansicht beziehen sich Treffer
und Ähnlichkeit auf die für diese Sensitivität vertauschten Namensrollen; der
Originalwert bleibt sichtbar und der Tausch wird erläutert. Die primäre
Dashboardansicht bewertet weiterhin Originalrollen.

## Darstellung und Ursachen

Bereich C/G und der Fehlerbericht zeigen aggregierte Statuszahlen. G und die
Standard-/Fehlerdetails zeigen Ground Truth, **einen extrahierten Originalwert**,
Status und Levenshtein-Ähnlichkeit in Prozent. Die zusätzliche Normalisiert-Spalte
entfällt; Normalwerte bleiben für Reproduktion in CSV/JSON erhalten.
Ohne nutzbaren gepaarten Vergleich ist die Ähnlichkeit „—“, keine gemessene null.
Null Prozent wird nur für einen vorhandenen tatsächlich verglichenen Wert
angezeigt. Textähnlichkeit ist keine Konfidenz oder Identitätswahrscheinlichkeit.

Die vorhandenen `diagnose_field`- und `field_trace`-Funktionen liefern die
Ursachenstufe; ihre Logik wird nicht neu implementiert. Das Audit übernimmt deren
gespeicherte Kategorie, Evidenzgrad, Stufe und Begründung. Unterschieden werden:

- Lokalisierter OCR-Text nachweislich nicht an die Zuordnung übergeben.
- Lokalisierter Text übergeben, aber nicht im strukturierten Endfeld enthalten.
- Modellzellen vorhanden, aber physische Feldzuordnung blockiert.
- Gespeicherte Ablehnung in Literal-/Positionsvalidierung.
- Keine eindeutigen Belege: Ursache **unbekannt**.

Eine Mappingdiagnose allein ohne vorhandene Zell-/Textbelege erzeugt keine
behauptete Erkennung. Zelltexte einer Zeile beweisen nicht, welcher davon zum
fehlenden Feld gehört oder ob der Referenzwert im Bild sichtbar ist.
Ein fehlender GT-Text im OCR-Volltext beweist keinen OCR-Fehler. Ohne unabhängige
lokalisierte Bildreferenz bleibt diese Ursache offen. Die bestehenden Hinweise
auf OCR-Lesefehler bleiben Hypothesen. Ausgabeindex 0 wird in der Diagnose nun
auch als Integer korrekt lokalisiert; bisher funktionierte dort nur CSV-Text.

## Nachweis auf eingefrorenen Daten

Der neue Bericht enthält dieselben 46 Kursreferenzen/184 erwarteten Felder je
Verfahren. Alle bisherigen Feld- und Teilnehmerkennzahlen sind identisch:

| Verfahren | Korrekt | Abweichend | Nicht erkannt | Zuordnung unklar | Nicht bewertbar |
|---|---:|---:|---:|---:|---:|
| ocr_rules | 0 | 0 | 184 | 0 | 0 |
| ocr_llm | 74 | 17 | 93 | 4 | 0 |
| paddle_llm | 94 | 32 | 58 | 0 | 0 |
| vlm | 67 | 29 | 56 | 32 | 0 |
| ocr_vlm | 88 | 32 | 2 | 66 | 0 |

Beim VLM erklären 32 blockierte Zellfälle weiterhin fehlende finale Feldbeiträge;
beim Hybrid 62. Die übrigen vier unklaren Hybridfälle sind ungepaarte Zusatzwerte.
**Die Metrik M bleibt VLM 88 und Hybrid 64**; ihre Abdeckung steigt nicht durch
diese neue Erklärung. Die vier unklaren OCR+LLM-Fälle sind ebenfalls Zusatzwerte.
Kein Anzeigestatus darf als nachträgliche Texterkennung ausgegeben werden.

928 Feldfälle und 232 Teilnehmerfälle werden weiterhin gegen die vorhandenen
Aggregationen geprüft. Die 787 Dateien des historischen Vergleichs und seines
Quelllaufs sind durch Hashinventar geschützt. Private Nachweise liegen unter
`data/field-states-20261116/`. Die Kursreferenz ersetzt weiterhin keine unabhängig
geprüfte Anwesenheits-/Leerzellenannotation.

## Reproduktion

Aus `software/`, mit einem noch nicht vorhandenen Ausgabeordner:

```powershell
.\.venv\Scripts\python.exe testframework/main.py analyze --report testframework/ergebnisse/20261112T082436Z-ffc71ce9 --output testframework/ergebnisse/NEUE_FELDANALYSE
```

Regressionen: `tests/test_field_assessment.py` prüft exakte/abweichende/null-
ähnliche/fehlende Werte, unbekannte GT, unklare Paarung, gesperrte unsichere
Originalwerte, Diagnosegrenzen, Integerindex 0 und unveränderte historische
Dateien beim Replay. Die bestehenden Filter-/Export-/Zählerprüfungen bleiben
aktiv. HTML/CSV/JSON enthalten lokale Einzelwerte und bleiben privat.

Geänderte Programmdateien unter `verarbeitung/src/participant_bench/roster_benchmark/`:
`field_assessment.py` (neu), `metrics.py`, `evaluation.py`, `scientific.py`,
`detail_report.py`, `error_report.py`, `metric_audit.py`, `metric_audit_report.py`
und `dashboard_report.py`. Neue Regressionen in `tests/test_field_assessment.py`;
die Darstellungsassertion in `tests/test_benchmark_details.py` prüft jetzt Prozent
statt ausgeschriebener Edit-Distanz-Formel. Dokumentation: diese Anleitung,
`docs/scientific-evaluation.md`, `testframework/README.md` und zentrale Übergabe.

Abgeschlossen: **904 lokale Tests (95,64 s)**, 90 gezielte Tests (10,12 s), 48 API-Tests (9,15 s),
3.449 lokale Dateilinks, beide Skriptsyntaxen/CSP-Hashes und vollständige
Status-/Metrikreconciliation. Visuelle Browserabnahme bleibt in dieser Sitzung
wegen fehlender Browser-/Desktopanbindung offen. Ohne unabhängig lokalisierte
Bildreferenz bleiben nicht belegbare OCR-/Zuordnungsursachen unbekannt.
