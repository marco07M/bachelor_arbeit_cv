# Genauigkeit erkannter Felder getrennt von Vollständigkeit

Stand: 16.11.2026. Die neuen HTML-Berichte zeigen **Ø Levenshtein-Ähnlichkeit
erkannter Felder** statt Levenshtein-Feld-F1. Field Coverage, Exact Recall,
Exact F1, Teilnehmermetriken, Referenznenner und Zuordnungsregeln bleiben erhalten.
Die neue Kennzahl ist kein F1 und keine alleinige Gesamtqualität.

## Definition und Bewertungsumfang

```text
s(g,p) = 1 − d_Levenshtein(g,p) / max(len(g), len(p))
D = bewertbare nichtleere Referenzfelder mit nichtleerer zugeordneter Ausgabe
S_detected = Σ_{i∈D} s(g_i,p_i) / |D|
```

Die beiden neuen additiven Zähler heißen `detected_similarity_credit` (Σs) und
`detected_fields` (|D|). `detected_similarity` ist deren Quotient, intern im
Intervall [0,1]. Die Darstellung multipliziert mit 100. Bei D=0 bleibt der Wert
`None`/leeres CSV-Feld und erscheint als **nicht definiert**, nie als null Prozent.
Über Kurse, Dokumentgruppen und Feldtypen werden beide Zähler gepoolt; ein
ungewichteter Durchschnitt von Kursmitteln würde kleine Kurse übergewichten.

In D gelangen ausschließlich die nach dem bestehenden Matching gepaarten Felder:

- Die Referenz muss `read` sein und nichtleere bewertbare Information enthalten.
- Die für diese Paarung verwendete Ausgabe muss nach vorhandener Normalisierung
  nichtleer sein. Die bestehende `score_uncertain_values`-Policy bleibt erhalten;
  vom Profil verworfene unsichere Rohwerte werden nicht nachträglich freigegeben.
- Falsch transkribierte Werte, Werte in falschen Rollen, schwache/mehrdeutige Paare
  und nichtleere ID-Platzhalter werden **nicht** wegen ihrer Fehler ausgeschlossen.
  Auch null Ähnlichkeit ist ein tatsächlicher Vergleich und bleibt im Mittel.
- Zusätzliche ungepaarte Personen/Felder, leere Ausgaben sowie bekannte leere,
  unbekannte, maskierte oder unlesbare GT gehören nicht zu D. Bekannte Leerzellen
  liefern damit keine künstlichen perfekten Ähnlichkeitsbeiträge.

Nichtleere ID-Platzhalter werden wörtlich verglichen. Sie bleiben nach dem
bisherigen Protokoll fehlende **nutzbare** ID-Information für Coverage und Exact
Recall. Daher kann D bei solchen Fällen größer als R−M sein; diese bereits
vorhandene Unterscheidung zwischen Text und nutzbarer Information wird nicht
verändert. Verfügbare fehlerhafte normale Werte erhöhen dagegen weiterhin die
Abdeckung. Der vollständige Feldfall zeigt Status und einzelne Ähnlichkeit.

## Normalisierung und Zuordnung

Es gibt keine neue Edit-Distanz oder zweite Matchingimplementierung.
`matching.normalize` und `matching.similarity` bleiben unverändert: NFC-Unicode,
vereinheitlichte Textleerzeichen, Groß-/Kleinschreibung gemäß gespeicherter
Konfiguration; IDs außen getrimmt, führende Nullen rein numerischer IDs gemäß
`ignore_leading_user_id_zeros`. Innere ID-Leerzeichen und Buchstabenfall bleiben
erhalten. Keine Umlaut-/ß-/Akzent-/Schreibfehlerreparatur.

`metrics.detected_value` nutzt dieselbe normierte Feldpaarung. Die primäre
Ansicht behält originale Namensrollen auf den bestehenden referenzgestützten
Paaren; Namensswap- und konservative Sensitivitäten bleiben separat.
Die globale Eins-zu-eins-Zuordnung wird weder für einen höheren Mittelwert neu
optimiert noch durch Ähnlichkeitsschwellen nachträglich gefiltert. Sie verwendet
weiterhin Referenzen und bestätigt keine unabhängigen Personenidentitäten.

Zusätzliche oder halluzinierte Datensätze behalten ihre P-/FP- und
Zusatzpersonenbeiträge. Sie senken den neuen bedingten Mittelwert nicht nochmals;
deshalb muss dieser zusammen mit Coverage, Exact Recall, Exact F1 und
Zusatzmetriken gelesen werden. Selektive Extraktion weniger leichter Felder kann
einen hohen Mittelwert liefern. D/R und Σs/D stehen deshalb neben dem Wert.

## Änderungen im Code und Darstellung

Unter `verarbeitung/src/participant_bench/roster_benchmark/`:

- `metrics.py`: `detected_value`, `scores`, `empty_counts`, `course_metrics` und
  `aggregate` ergänzen die zwei Zähler, das Mittel und die Feldbeiträge.
- `evaluation.py`: Metrikversion v7 und Definitionen zum Umfang/Legacy-Export.
- `scientific.py`: neue Zähler/Mittel in vorhandenen Exporten, Analyseversion v4.
  `scientific_stats.py` verwendet das Mittel statt Soft-F1 im bestehenden
  Clusterbootstrap. Exakte Schätzer und Stichprobenlogik bleiben unverändert.
- `dashboard_report.py`: sortierbare Kennzahl neben Coverage und Exact-Metriken,
  Zähler/Nenner, Erklärung und Feldtypaufschlüsselung. `report.py` und
  `detail_report.py` stellen dieselbe Kennzahl/Formel dar. Kein eigener
  Ähnlichkeitsalgorithmus in den Renderern.
- `field_assessment.py`: einzelne Ähnlichkeiten folgen dem neuen gespeicherten
  Feldvergleich, auch bei nichtleeren Platzhaltern. `metric_audit.py` reconciliert
  D und Σs gegen die Aggregate; `cli.py` nennt die neue Kennzahl ausdrücklich.

Die Felder `soft_precision`, `soft_recall`, `soft_f1`, `similarity_credit` und
`score_percent` werden für alte Exporte und gespeicherte Nachweise unverändert
weitergeführt und als **Legacy** dokumentiert. Sie wurden nicht umbenannt oder
mit neuen Zahlen überschrieben. Die aktuelle Anzeige und neue Statistik verwenden
`detected_similarity`; sie dürfen nicht aus `score_percent` abgeleitet werden.
Der neue optionale Methodenschlüssel `detected_similarity_percent` ist bereits
auf 0–100 skaliert. Sonstige neue Metrikwerte bleiben Bruchteile.

Die Einzelansicht G zeigt Original-GT, extrahierten Originalwert und dessen
prozentuale Ähnlichkeit. Die Exporte enthalten `detected_contribution` (0/1) und
`detected_similarity` (Feldähnlichkeit oder undefiniert). Σs und D sind damit bis
auf die Feldentscheidung nachvollziehbar. Für alte Feldexporte kann der
Detailrenderer die neuen Beiträge mit derselben gemeinsamen Funktion erklären;
historische numerische Ergebnisdateien werden dadurch nicht umgeschrieben.

Bootstrap-Differenzen der neuen Kennzahl sind **bedingte** Unterschiede mit
möglicherweise verschiedenen D-Mengen. Sie sind kein kontrollierter isolierter
Lesegenauigkeitsvergleich. Ganze Abhängigkeitsgruppen werden gezogen, Σs und D
gepoolt; D=0-Replikate bleiben undefiniert. Bestehende Mindestgruppen- und
Referenzprüfungen gelten weiter. Im aktuellen Dreidokumentbeispiel fehlen genügend
unabhängige geprüfte Gruppen für belastbare Intervalle.

## Nachweis aus eingefrorenen Entwicklungsdaten

Neuer Bericht: `testframework/ergebnisse/detected-similarity-20261116/report.html`.
Quellen sind unverändert `field-states-20261116/` und dessen vorhandener
Extraktionslauf. Keine neue Inferenz und keine Änderung von Referenz oder Profil.

| Verfahren | Σs / D | D / R | Neue mittlere Ähnlichkeit |
|---|---:|---:|---:|
| ocr_rules | 0 / 0 | 0 / 184 | nicht definiert |
| ocr_llm | 85,3095 / 91 | 91 / 184 | 93,75 % |
| paddle_llm | 110,6039 / 126 | 126 / 184 | 87,78 % |
| vlm | 86,0226 / 96 | 96 / 184 | 89,61 % |
| ocr_vlm | 107,0222 / 120 | 120 / 184 | 89,19 % |

Alle bisherigen Methodenzähler, Exact-/Coverage-/Teilnehmerwerte und historischen
Legacywerte stimmen mit der Ausgangsbewertung überein. Insbesondere bleiben bei
Paddle Coverage 68,48 %, Exact Recall 51,09 % und Exact F1 60,65 % bestehen.
Die höheren bedingten Ähnlichkeiten gegenüber dem früheren Soft-F1 sind ein
**Definitionswechsel**, kein Qualitätsgewinn einer Extraktion.
1.287 historische Vergleichs-/Quelllaufdateien wurden durch Hashinventar geschützt.
Private Prüfnachweise: `data/detected-similarity-20261116/`.

## Tests und Reproduktion

`tests/test_detected_similarity.py` umfasst 18 Regressionen: 2/4 korrekt,
Schreibabweichungen, null Ähnlichkeit bei falschen gefüllten Werten, D=0,
mehrdeutige Paare, zusätzliche/fehlende Personen, GT-Zustände, Platzhalter,
Normalisierung, korrekt gepoolte Mittel, HTML-Sortierwerte/Zähler und unveränderte
historische Dateien. Statistikfixtures in `test_scientific_evaluation.py`
enthalten die neuen additiven Zähler.

Abgeschlossen: **922 lokale Tests (101,83 s)**, **106 abschließende gezielte
Tests (12,01 s)** und **48 API-Tests (10,54 s)** bestanden. Ruff, Diff-Check,
3.449 lokale Dateilinks, beide Skriptsyntaxen und CSP-Hashes sowie alte und neue
Feldbeitragsprüfungen erfolgreich. Keine realen API-Aufrufe. Visuelle Browser-
abnahme bleibt wegen fehlender Anbindung offen.

Reproduktion aus `software/`, mit noch nicht vorhandenem Ausgabeordner:

```powershell
.\.venv\Scripts\python.exe testframework/main.py analyze --report testframework/ergebnisse/field-states-20261116 --output testframework/ergebnisse/NEUE_AEHNLICHKEIT
```

Historische HTML-Berichte bleiben historische Darstellungen ihrer Definitionen.
Für neue Darstellungen ist eine Neuanalyse nötig; alte Reports werden nicht
automatisch überschrieben. Die Kursreferenz bleibt ohne unabhängige
Seitenannotation kein Nachweis der sichtbaren Personen/Leerzellen im PDF.
