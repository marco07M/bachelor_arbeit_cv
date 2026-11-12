# Wissenschaftliche Analyse gespeicherter Vergleiche

Stand: 11.11.2026. Implementiert in `roster_benchmark/scientific*.py`,
`metrics.py`, `error_report.py` und `dashboard_report.py`, integriert in den
vorhandenen `report.html`. Keine neue Extraktion, Modell- oder Profiländerung.
Die bisherige Feldbewertung bleibt erhalten. Die neue Hauptansicht verwendet
ausdrücklich `original_roles`; der bisherige Standardbericht bleibt in neuen
Ausgaben zusätzlich als `standard_report.html` erreichbar. Dieser Wechsel der
sichtbaren Primäransicht ist keine Änderung historischer Extraktionen.

## Start aus `software/`

Neue reguläre Vergleiche enthalten automatisch eine wissenschaftliche Ansicht.
Ohne manuelle Metadaten bleiben Schriftmerkmale und Evaluationsphase `unknown`;
es werden keine Konfidenzintervalle aus ungeprüften Gruppen berechnet.
Einen vorhandenen Bericht mit geprüften Metadaten neu auswerten:

```powershell
.\.venv\Scripts\python.exe testframework/main.py metadata-template --report testframework/ergebnisse/LAUF --output data/analysis/documents.csv
# CSV manuell prüfen und ausfüllen.
.\.venv\Scripts\python.exe testframework/main.py analyze --report testframework/ergebnisse/LAUF --output testframework/ergebnisse/NEUE_ANALYSE --metadata data/analysis/documents.csv --phase development
```

`--output` muss neu sein. Originalbericht und Extraktionslauf bleiben erhalten.
Die aktuelle Excel-/CSV-Referenz wird nicht erneut eingelesen: Grundlage ist der
gespeicherte `reference_snapshot.json`. Manifest, Zusammenfassung und eingefrorene
Extraktionen werden gegen die historischen Prüfsummen geprüft; neue Berichte
sichern zusätzlich den Referenzsnapshot. Alte Berichte besitzen diesen zusätzlichen
Snapshot-Hash teilweise noch nicht. `--source-run` erlaubt einen verschobenen,
inhaltlich identischen Quelllauf. Analysedateien enthalten lokale Referenzwerte;
sie gehören wie bestehende Detailberichte nicht in öffentliche Repositories.

Zusätzliche gespeicherte Kandidaten können aus separaten Vergleichsordnern kommen:

```powershell
.\.venv\Scripts\python.exe testframework/main.py analyze --report testframework/ergebnisse/LAUF --output testframework/ergebnisse/NEUE_ANALYSE --metadata data/analysis/documents.csv --phase development --additional-report docling=testframework/ergebnisse/DOCLING --additional-report docling_vlm=testframework/ergebnisse/ASSIST
```

Die Kandidaten müssen in den jeweiligen Berichten vorkommen und auf allen
ausgewählten PDF-SHA256-IDs ausgeführt worden sein. Referenzpersonen, Feldzustände
und Referenzkonfiguration müssen übereinstimmen. `docling_vlm` bezeichnet den
vorhandenen Docling-Pfad mit `structures.docling.vlm_assist: true`; im Quelllauf
heißt seine Methode weiterhin `docling`. Die Konfiguration wird geprüft.
Fehlende Kandidaten werden ausgewiesen, keine günstige Dokumentschnittmenge gebildet.

## Manuelle Metadaten und Trennung der Daten

Die UTF-8-CSV verwendet dieselben Kernspalten wie das Auswahlinventar:

| Spalte | Zulässige Werte / Bedeutung |
|---|---|
| `document_id`, `class_id` | SHA256 der PDF und durch vorhandene Dateinamenregeln ermittelte Schulung; nicht umbenennen |
| `dependency_group` | Manuell geprüfte gemeinsame Gruppe abhängiger Schulungen/PDFs |
| `grouping_reviewed` | `true` nur nach Prüfung, sonst `false`; geprüfte Gruppe braucht eine Kennung |
| `prior_use` | `development`, `unused`, `unknown`; Vorbenutzung zur Entwicklung erzwingt `partition=development` |
| `partition` | `development`, `pilot`, `test`, `unknown`; `--phase` wählt eine Phase |
| `stratum` | `printed`, `handwritten`, `mixed`, `unknown`; Schrift des Dokuments, keine Feldtranskription |
| `quality_flags` | Semikolongetrennt: `clean`, `low_contrast`, `skew`, `shadow`, `cropped`, `wrapped_text`, `headerless_continuation`, `multiple_pages`, `variable_layout` |

Vorlage und Lader beziehen sich auf das vollständige Quellmanifest. Fehlende Zeilen
bleiben unbekannt; fremde/doppelte Dokumentkennungen, widersprüchliche Schulungen
und unbekannte Codes werden abgelehnt. PDFs derselben Schulung müssen in derselben
Abhängigkeitsgruppe und Phase liegen; eine Gruppe darf keine Phasengrenze
überschreiten. Identische PDF-Hashes werden bereits durch die bestehende Zuordnung
zusammengeführt; mehrdeutige Schulungsnamen bleiben unbewertet. Das ersetzt keine
manuelle Prüfung ähnlicher Listen, wiederkehrender Personen oder anderer Abhängigkeiten
über den gesamten Bestand. Bei getrennten Quellläufen muss diese Prüfung vorab in
einem gemeinsamen Inventar erfolgen; der Analyselader prüft jeweils sein Quellmanifest.
Es gibt keine automatische Garantie statistischer Unabhängigkeit oder einen
nachträglichen Nachweis, dass als `unused` deklarierte Daten nie zur Entwicklung
verwendet wurden. Finale Daten erst nach Abschluss der Auswahl öffnen.

Referenz und Matching bleiben schulungsbezogen. Bei einer PDF pro Schulung ist
dies zugleich eine Dokumentauswertung. Mehrere PDFs einer Schulung werden nicht
mit erfundener Seiten-/Personenzuordnung getrennt bewertet. Unterschiedliche
Schriftannotationen derselben Schulung heißen `heterogeneous_course`, nicht `mixed`.
`unknown` bedeutet fehlende Annotation, `not_marked` keine dokumentierte Markierung,
nicht nachgewiesene Abwesenheit. Mehrseitigkeit ist aus dem Manifest messbar.
Für Handschrift-CER/WER, Seiten- oder Feldschriftauswertungen fehlen lokalisierte,
unabhängig geprüfte Transkripte; die neue Schriftanalyse bewertet ganze Schulungen.

## Feldqualität und fünf Matchingansichten

Alle Ansichten verwenden `course_metrics`, `aggregate` und die bestehenden
Normalisierungen/Feldzustände. Exakte Treffer nach Normalisierung und unverändert
exakte Rohwerte werden getrennt exportiert. Mit Referenzfeldern R,
bewerteten Ausgabefeldern P, exakten Treffern E und aufsummierter
Levenshtein-Gutschrift S gilt: Recall=E/R, exakter F1=2E/(R+P), weicher F1=2S/(R+P).
Fehlende bewertbare Werte bleiben Fehler im Nenner; zusätzliche Werte werden über
P bestraft. Maskierte/unlesbare Referenzen und Platzhalter behalten das bestehende
Ausschlussprotokoll. Nenner, Ausschlüsse, fehlende/falsche/zusätzliche Werte werden
je Feld und Merkmal exportiert. Undefinierte Quotienten bleiben `null`, nicht null Prozent.

| Ansicht | Paarung / Feldbewertung |
|---|---|
| `original_roles` (primär) | Best-Fit mit Namensorientierungen bestimmt feste Personenpaare; danach unveränderte Originalrollen bewerten |
| `best_fit_no_swap` | Globale Best-Fit-Paarung vollständig ohne Namensswap neu berechnen |
| `best_fit_swap` | Bestehende Best-Fit-Paarung und tolerierte Namensorientierungen |
| `conservative_no_swap` | Bestehender konservativer Matcher ohne Swap |
| `conservative_swap` | Bestehender konservativer Matcher mit Swap |

Auch `original_roles` und `best_fit_no_swap` nutzen die Referenz zur Identität.
Sie sind **keine referenzunabhängigen Teilnehmerzuordnungen**. Die erste Gegenprobe
`original_roles` → `best_fit_swap` isoliert die Rollenbewertung auf festen Paaren.
Andere Gegenproben können zusätzlich die globale Paarung und Ausgabenenner ändern.
Alle ausgewiesenen Differenzen entstehen ausschließlich durch Bewertungsregeln;
kein extrahierter Wert wird verbessert. Schulungsquantile/Boxplots sind deskriptiv,
der Gesamtscore bleibt aus gepoolten Zählern berechnet. Die Heatmap zeigt bis zu
200 Schulungen; CSV/JSON behalten alle Schulungen.

## Unsicherheit und gepaarte Vergleiche

Implementiert ist ein reproduzierbarer 95-%-Cluster-Perzentilbootstrap mit NumPy,
standardmäßig 2.000 Wiederholungen und Seed 42. Innerhalb einer geprüften
Abhängigkeitsgruppe werden Schulungszähler zuerst summiert. Jeder Durchlauf zieht
gleich viele Gruppen mit Zurücklegen, summiert deren Zähler und berechnet Recall,
exakten F1 und weichen F1 erneut. Es werden weder einzelne Felder unabhängig gezogen
noch Schulungs-F1 ungewichtet gemittelt. Gepaarte Effekte verwenden exakt dieselben
gezogenen Gruppen für beide Verfahren; die Differenz ist Vergleich minus Basis
in Prozentpunkten. Die [SciPy-Dokumentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)
beschreibt Perzentilintervalle und identische Indizes für gepaarte Stichproben;
der gruppierte Zählerbootstrap ist hier eine eigene Implementierung.

Eine fehlgeschlagene/fehlende Seite behält die vollständige Kursreferenz; die
Differenz darf den Ausfall beschreiben. Ganz fehlende Kandidatenergebnisse bekommen
keine Unsicherheitsintervalle. Gruppenmengen und Referenznenner müssen gepaart
übereinstimmen. Es gibt keine automatische Schnittmengenreduktion.
Intervalle setzen geprüfte Gruppierung/Vorbenutzung und genau eine bekannte Phase
voraus. Unter standardmäßig zehn Gruppen bleiben Grenzen offen (`insufficient_groups`).
`--minimum-groups` ist eine dokumentierte pragmatische Schranke, **keine Poweranalyse**.
`--resamples` erlaubt 200–20.000 Wiederholungen; weniger als 95 % definierte
Resamples führen zu `undefined_resamples`. Konstante Intervalle werden als
`degenerate` gekennzeichnet. Perzentilintervalle sind bei kleinen/heterogenen
Stichproben beschränkt, nicht bias-korrigiert und keine pauschalen Signifikanz-
oder Kausalitätsnachweise. Viele Paarvergleiche bleiben explorativ; eine
konfirmatorische Hypothese und gegebenenfalls Multiplizitätsbehandlung sind vorab festzulegen.

## Teilnehmerqualität und Nenner

Die bisherigen Zähler `assigned_participants`, `missing_participants` und
`extra_participants` beschreiben Paarungen beziehungsweise ungepaarte Zeilen.
Best-Fit-Paarungen bestätigen keine Identitäten. Auch der historische Zähler
`fully_exact_participants` bleibt unverändert: Er kann bereits bei einer vollständig
korrekten **Teilreferenz** erfüllt sein. Er wird nicht in die neue Metrik umbenannt.

Neu berechnet `metrics.participant_quality` auf denselben Paaren und denselben
Feldentscheidungen zusätzliche, anschließend gepoolte Zähler:

| Kennzahl | Zähler / Nenner | Einheit / Richtung |
|---|---|---|
| Vollständige Teilnehmer | Personen mit sämtlichen vier Pflichtfeldern korrekt / Referenzpersonen mit vier bestimmbaren Feldern | Anteil, höher besser |
| Korrekte Teilreferenzen | Personen mit allen bestimmbaren Feldern korrekt / Referenzpersonen mit 1–3 bestimmbaren Feldern | Anteil, separat, höher besser |
| Teilnehmer-Recall | streng identitätskorrekte Personen / Personen mit bewertbarem eindeutigen Referenzanker | Anteil, höher besser |
| Fehlende Felder | fehlende oder ungültige Ausgabe für bewertbare Referenzfelder / R | Anteil, niedriger besser |
| Falsche Felder | vorhandene, nicht exakte Ausgabe für bewertbare Referenzfelder / R | Anteil, niedriger besser |

`read` und ausdrücklich `empty` sind bestimmbare Feldzustände. Vier solche Felder
ergeben eine vollständige Referenz; maskierte, unbekannte oder unlesbare Felder
machen sie unvollständig. Bei null bestimmbaren Feldern ist die Person nicht
bewertbar. Ein ausdrücklich leeres Referenzfeld verlangt eine explizit leere
Vorhersage gemäß bestehender Leerzellenauswertung; `null` belegt keine Leerzelle.
Das Feld-Recall-R enthält weiterhin nur die bewertbaren **nichtleeren** Referenzen.
Die Unterschiede der Feld- und Personen-Nenner sind beabsichtigt.

Das strikte Identitätskriterium verlangt innerhalb derselben Schulung entweder
eine eindeutige lesbare, nutzbare Personalnummer oder eine eindeutige lesbare
Kombination aus Vor- und Nachname. Zusätzlich müssen **alle** bestimmbaren
Identitätsfelder (Vorname, Nachname, Personalnummer einschließlich expliziter
Leerwerte) exakt nach der gespeicherten Normalisierung übereinstimmen. Eine
richtige ID mit falsch erkanntem lesbarem Namen genügt nicht. Organisation gehört
zur vollständigen Vierfeldkorrektheit, aber nicht zum Identitätskriterium.
Mehrdeutige Referenzen ohne eindeutigen Anker werden mit eigener Zahl aus dem
Identitätsnenner ausgeschlossen. Daher ist dies ein Recall **auf dem bewertbaren
Referenzteil**, kein Nachweis über sämtliche unbekannten Identitäten. Originalrollen
bleiben in der Hauptansicht strikt. Die referenzgestützte Paarung bleibt eine
Einschränkung; konservative und Swap-Ansichten stehen daneben.

Die konkrete Vierfeld-/Ankerregel ist eine offengelegte Projektentscheidung,
keine extern validierte Identitätsmethode. Qualitätsquotienten liegen in [0,1]
und werden in HTML als Prozent angezeigt; undefinierte Nenner bleiben `null`.
Gesamtwerte verwenden summierte Zähler und Nenner, keine Mittelwerte von
Schulungsquotienten. Teilnehmerquotienten sind zunächst deskriptiv; die vorhandenen
Bootstrapintervalle beziehen sich auf Feld-Recall und die beiden Feld-F1-Metriken.

## Dashboard und Effizienznachweis

`report.html` enthält sechs offline bedienbare Bereiche:

- **A Gesamtvergleich:** sortierbare Haupttabelle, sichtbare Hauptnenner,
  technische Vollständigkeit und aufklappbare Definitionen/Matchinggegenproben.
- **B Feldanalyse:** Vierfeld-Heatmap mit E/R, fehlenden und falschen Werten;
  zusätzliche und ausgeschlossene Felder bleiben getrennt.
- **C Fehleranalyse:** aggregierte Fälle mit Dokument-, Schulungs-, Feld-,
  Ursachen- und Evidenzfilter; Links öffnen die bestehende Einzelfallansicht
  mit Ground Truth, verglichenem Wert, Originalwert und gespeicherten Belegen.
- **D Dokumenttypen:** manuelle Kategorien, deren Fallzahlen und kleine Gruppen;
  vorhandene Schulungsdiagramme in aufklappbaren Bereichen.
- **E Effizienz/Kosten:** vorhandenes Qualitäts-Zeit-Diagramm, Seitenmedian,
  Quartile und Min–Max, Quellenzeit, Laden, Warm-up sowie tatsächliche Aufrufe.
- **F Statistik:** vorhandene gepaarte Differenzen und 95-%-Intervalle, Gruppen,
  Seed, Wiederholungen und explizite Ausschlussgründe.

Jeder fehlende, falsche oder zusätzliche Feldfall erhält genau einen konservativen
Ursachenbereich und Evidenzgrad. Anteile verwenden alle Feldfehler des Verfahrens,
auch nach Filterung bleibt der Bezugsnenner unverändert. Die Kategorien folgen
den gespeicherten Übergängen; OCR versus Zuordnung und Modellantwort versus
Nachverarbeitung sind häufig nicht beweisbar trennbar. Tabellen-/Antwort- und
Validierungsereignisse ohne eindeutige Feldzuordnung werden **separat** ausgewiesen.
Sie werden weder zu Feldfehlern addiert noch nachträglich zu bewiesenen Ursachen
erklärt. Eine fehlende Feldursache wird nicht aus dem verwendeten Modell geraten.
Die Einzelfallanalyse verwendet dafür dieselbe Originalrollenbewertung wie A/B;
die alte Standardbewertung bleibt im separaten erhaltenen Bericht nachvollziehbar.

Seitenzeiten verwenden vorhandene `page_wall_seconds` ohne anteilige Ladezeiten.
Median, Q25/Q75 und Min–Max beschreiben eine beobachtete Verteilung, keine
Unsicherheit der Qualität oder kontrollierte Wiederholungsmessung.
`PageResult.calls` wird nur bei dokumentiertem, widerspruchsfreiem Quellzähler
als tatsächlich protokollierter Aufruf übernommen. `model_calls` hat Vorrang vor
`generation_calls`, weil vorhandene Namenshilfsschritte ebenfalls zählen.
LLM/VLM werden nur bei eindeutigem Pfad getrennt; alte oder gemischte Zähler
bleiben offen. CSV/JSON enthalten Seite und aggregierte PDF; Warm-up-Aufrufe
stehen separat für den vollständigen Quelllauf. Cache-Aufrufe von null beziehen
sich auf den beobachteten Wiederverwendungslauf, nicht auf die ursprüngliche Inferenz.

Unabhängig belegte Euro-Messartefakte liegen im aktuellen Datenvertrag nicht vor;
`measured_eur_per_1000` bleibt deshalb `null`. Ein Profilflag `kind=measured`
allein ist kein geprüfter Kostennachweis. Vollständig parametrierte bestehende
Kostenszenarien können getrennt ausgewiesen werden: laufende Betriebs- und
gegebenenfalls Energiekosten pro Seite × beobachtete Seiten/PDF × 1.000.
Manuelle Erfassung, Kontrolle und Entwicklung gehören nicht zu diesem
Inferenz-/Betriebskostenvergleich; sie bleiben im bestehenden Prozessszenario.
Nicht angegebene Energie bleibt eine nicht enthaltene Annahme, keine gemessene
Null. Die dokumentierten Beispieldaten liefern keine Eurokosten.

Definitionen, Zähler, Nenner, Einheit und Interpretationsrichtung werden zentral
aus `metrics.QUALITY_DEFINITIONS` nach HTML, CSV und JSON übernommen. Die
Darstellung berechnet die neuen Qualitätsmetriken nicht erneut.

## Geprüfte methodische Literatur

- Sokolova & Lapalme (2009), *A systematic analysis of performance measures for
  classification tasks*, Information Processing & Management 45(4), 427–437,
  [DOI/Verlag](https://doi.org/10.1016/j.ipm.2009.03.002). Die Analyse der
  Eigenschaften verschiedener Klassifikationsmaße motiviert die getrennte
  Darstellung mehrerer Qualitätsdimensionen; die Teilnehmerregeln sind eigene
  Operationalisierungen. Verlagsmetadaten und Abstract am 11.11.2026 geprüft.
- Field & Welsh (2007), *Bootstrapping clustered data*, JRSS B 69(3), 369–390,
  [DOI/Verlag](https://doi.org/10.1111/j.1467-9868.2007.00593.x),
  [geprüfter Volltext](https://bemlar.ism.ac.jp/zhuang/Refs/Refs/field2007jrssb.pdf).
  Die Arbeit untersucht Bootstrapverfahren für abhängige Daten und deren
  modellabhängige Konsistenz. Sie liefert keine allgemeine Garantie für unsere
  kleinen Stichproben oder die konkrete Quotientenstatistik.
- Die bereits verwendete offizielle SciPy-Dokumentation stützt die technische
  Definition von Perzentilintervallen und gepaarten Indizes; sie ersetzt keine
  Prüfung der Gruppierung. Verifizierte Belege ergänzen `verified_sources.bib`;
  `references.bib` bleibt das unveränderte Zotero-Exportziel.

## Fehler, Hybridbeiträge und Effizienz

Die vorhandene `extraction_errors.html` erhält Dokument-/Stufenfilter und eine
Aggregation nach Verfahren, Dokument, Feld, Ergebnis, Stufe und Evidenzgrad.
Belegte lokale Stufenübergänge, Hypothesen und unbekannte Ursachen bleiben getrennt.
Ein erkannter, übergebener Wert ohne finale Feldübernahme beweist den Verlust
zwischen Zuordnung und Nachverarbeitung, nicht dessen internen Modellmechanismus.
Zusatzwerte sind keine automatisch bewiesenen Halluzinationen. Ungepaarte
Referenzpersonen werden weiterhin keiner geratenen PDF-Seite zugewiesen.
Separate Seitenereignisse (z.B. leere/gültige oder ungültige Antworten,
abgelehnte Zeilen, unzugeordnete native Zeilen, Rollenausschlüsse) werden nicht
zu Feldfehlerzahlen addiert. Abgelehnte Werte sind nicht automatisch korrekt.

Für `vlm` → `ocr_vlm`, `docling` → `docling_vlm` und `ocr_llm` → `paddle_llm`
wird der vorhandene Feldübergangsvergleich wiederverwendet: korrigierte und
verschlechterte Referenzfelder, ergänzte/erneut fehlende Werte, neu gepaarte
Referenzpersonen, Typgruppen und zusätzliche Felder. Zuordnung bleibt
referenzgestützt; ein neuer Match ist kein unabhängiger Identitätsnachweis.
Tatsächliche Laufbilder und vorhandene VLM-/Promptkontrollen werden geprüft.
Die Auswertung setzt `causal_claim=false`: gleiche Bilder allein kontrollieren
weder unterschiedliche Layoutpfade/Prompts noch Laufzustand oder Hardwareeffekte.

Volle Methodenzeit, zugerechnete Pipeline-/Extraktionszeit, Laden, Warm-up,
Aufrufzähler, Cache-Seiten, Assist-Zeit sowie RAM-/GPU-Spitzen bleiben getrennt.
Seiten-Zeitkomponenten werden unverändert exportiert. `model_extraction_seconds`
und gespeicherte Antwortzeiten sind bei wiederverwendeten Antworten kein sicherer
Nachweis frischer Inferenz. Aufrufzahl null bedeutet bei Cache-Nutzung keinen
inferenzfreien ursprünglichen Erkennungsprozess. Energie, Geld und manuelle
Nacharbeit werden bei fehlenden Messungen nicht geschätzt.
Volle Quelllaufzeiten werden nicht anteilig auf Phasenteilmengen verteilt.
Eine deskriptive Paretofront verlangt vollständige Ergebnisse, denselben
Dokumentumfang und wird nur innerhalb eines ausgewiesenen Cache-Regimes gebildet.
Diese groben Regime sind keine kontrollierten Geschwindigkeitsbedingungen.

## Exporte und tatsächlich durchgeführte Prüfung

Unter `scientific/`: `analysis.json`, `courses.csv`, `fields.csv`, `strata.csv`,
`strata_fields.csv`, `intervals.csv`, `paired.csv`, `matching_effects.csv`,
`ablations.csv`, `ablation_strata.csv`, `transitions.csv`, `page_timings.csv`,
`pareto.csv`, `metadata_template.csv` sowie Heatmap, Verteilung und Qualitäts-
Laufzeit-Diagramm als PNG/SVG. Verschachtelte Zusammenfassungen sind in JSON
strukturiert; entsprechende CSV-Zellen enthalten JSON.
Unter `error_analysis/`: zusätzlich `summary.json`, `summary.csv`, `page_events.csv`.
Neu unter `scientific/`: `dashboard.csv`, `metric_definitions.csv`,
`participant_scores.csv`, `participant_cases.csv`, `document_calls.csv`,
`costs.csv` und `error_grading.json`. Letztere und Personenfallexporte enthalten
lokale Detailwerte und bleiben wie bisher außerhalb von Git.

Die Dashboard-Funktionsprüfung vom 11.11.2026 verwendet zwei getrennte Replays:
`testframework/ergebnisse/dashboard-20261111-v1/report.html` mit den fünf Verfahren
des bestehenden Entwicklungsfalls und `data/dashboard-20261111/synthetic/report.html`
mit vier gespeicherten neuronalen Ergebnissen einer synthetischen Druckseite.
Es wurde **keine neue Modellinferenz** ausgelöst. Keine Phasen werden vermischt.
In der realen Entwicklungsgruppe liegt der strikte Teilnehmer-Recall zwischen
0/18 und 8/18, obwohl Best-Fit-Paarungen allein deutlich mehr Personen verbinden.
Alle Referenzen dieses Falls sind vierfeldig bestimmbar; vollständige Korrektheit
liegt je nach Verfahren zwischen 0/18 und 3/18. Die synthetische Seite hat zwei
Personen, sieben bewertbare Felder und eine Teilreferenz; alle vier gespeicherten
neuronalen Ausgaben erhalten 7/7 Feldtreffer. Es gibt jeweils nur eine unabhängige
Gruppe, daher keine belastbaren Bootstrapintervalle oder allgemeine Rangfolge.
Die konkreten Läufe verwenden unterschiedliche historische Promptstände und
werden ausdrücklich nicht als gemeinsames Promptvergleichsexperiment gepoolt.

Automatisierte Unit-/Regressionstests prüfen fehlende und zusätzliche Personen,
Namensswap, gleiche ID mit falschem Namen, Teil-/Leerreferenzen, mehrdeutige
Identitätsanker, gepoolte Nenner, fehlende Zeiten, tatsächliche Aufrufzähler,
Seitenskalen bei Kostenszenarien sowie konsistente Feldfehler ohne Doppelzählung.
Ein Node-Test führt den tatsächlichen Dashboardcode für Tabs, beide
Sortierrichtungen mit fehlenden Werten, kombinierte Fehlerfilter und
Merkmalswechsel aus. Eine visuelle Browserabnahme blieb wegen der nicht
unterstützten lokalen Windows-Browsersteuerung offen; HTML-/Skriptprüfung
ersetzt keine Sichtprüfung sämtlicher Bildschirmgrößen.

Die lokale Gegenprobe `testframework/ergebnisse/scientific-20261110-v2/report.html`
verwendet ausschließlich die Quellen der Berichte `20261110T124858Z-35a9b605`,
`20261110T123112Z-b454d615` und `20261110T111751Z-9b5da18c`.
Eine bereits vorbenutzte Entwicklungs-PDF, zwei Seiten, eine Gruppe, 18 Personen,
72 bewertbare Referenzfelder. Manuelle Merkmale wurden aus der bestehenden
Entwicklungsannotation nur für dieselbe PDF-SHA256 übernommen (Provenienzdatei
unter `data/scientific-20261110/`). Keine neue Modellinferenz, keine externe Übertragung.

| Vergleich (Originalrollen, feste referenzgestützte Paarung je Verfahren) | Korrigiert | Verschlechtert | Exakte Felder vorher → nachher |
|---|---:|---:|---:|
| VLM → OCR-VLM | 9 | 5 | 38 → 42 |
| Docling → vorhandener Assist | 7 | 0 | 28 → 35 |
| Tesseract-LLM → Paddle-LLM | 13 | 2 | 29 → 40 |

Beim OCR-VLM ergibt allein die tolerierte Rollenbewertung auf denselben Paaren
einen weiteren exakten Treffer (42 → 43), ohne Extraktionsänderung. Der Assist
verwendet einen gespeicherten zusätzlichen VLM-Aufruf; zwei zuvor ungepaarte
Referenzpersonen erhalten einen Match. Diese Beobachtungen gelten nur für diese
Entwicklungsliste. Keine unabhängige Pilot-/Finalstudie, keine belastbaren CIs,
keine allgemeine Rangfolge oder kausale Überlegenheit. Druck-/Handschrift-
Unterschiede sind erst mit mehreren unabhängig klassifizierten Gruppen prüfbar.
