# Wissenschaftliche Auswahl der Extraktionsverfahren

Stand: 10.11.2026. Das Auswahlmodul erweitert das bestehende Framework. Extraktion,
Zuordnung, Nenner und Feldmetriken stammen weiterhin aus `runner.py` und
`roster_benchmark/`. `benchmark.yaml` bleibt unverändert. Es gibt keine neuen Modelle.

## Fragestellung und Kandidatenidentifikation

Die Untersuchung vergleicht vollständige Extraktionsarchitekturen auf überwiegend
maschinenschriftlichen und gemischten Teilnehmerlisten. Die Kandidaten werden aus
den bereits implementierten, lokal ausführbaren Verfahren identifiziert; dies ist
eine begründete Beschränkung auf verfügbare Architekturen, keine systematische
Vollständigkeitsbehauptung über alle veröffentlichten Modelle. Die Forschungsfrage
der Arbeit wird dadurch nicht eigenständig geändert.

| Kandidat | Rolle und Eigenschaften | Primärbelege |
|---|---|---|
| `ocr_raw` | Tesseract-Rohtext, CPU, keine strukturierten Teilnehmerfelder; Diagnose statt Feldranking | [Tesseract-Projekt](https://github.com/tesseract-ocr/tesseract) |
| `ocr_llm` | Tesseract + Qwen3-4B-Instruct-2507; Text- und Positionsbelege | [Modellkarte und festgeschriebene Revision](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/tree/cdbee75f17c01a7cc42f958dc650907174af0554) |
| `paddle_llm` | PP-StructureV3/Latin-PP-OCRv5 + dasselbe Textmodell | [PP-StructureV3](https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-StructureV3/PP-StructureV3.html), isolierte Paketpins im Repository |
| `docling` | Layout/TableFormer + native PDF-Texte bzw. Tesseract; deterministische Zuordnung | [Docling-Bericht v5](https://arxiv.org/abs/2408.09869v5), [Projekt](https://github.com/docling-project/docling) |
| `vlm` | Direkte Seitenbildextraktion, Qwen3-VL-4B-Instruct | [Modellkarte und festgeschriebene Revision](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct/tree/ebb281ec70b05090aa6165b016eac8ec08e71b17) |
| `ocr_vlm` | Dasselbe VLM und Bild plus Paddle-Belege; gezieltes Zusatzhinweisexperiment | bestehendes `hybrid.py`, Gleichheitsprüfungen in `config.py` und Tests |
| `docling_vlm` | Bestehendes Assist-Profil, intern Methode `docling`; selektiver Aufruf und heuristisches Merge | `configs/docling-vlm.yaml`, `hybrid.py` |

Die Primärquellen wurden am 10.11.2026 geöffnet. Modellkarten beschreiben die
Modelle, belegen jedoch keine Qualität auf diesem Korpus. Der Docling-Bericht
beschreibt die Architekturhistorie; die tatsächlich verwendete v2-Implementierung
ist durch die lokale Lockdatei und die gespeicherten Laufidentitäten festgelegt.
Herstellerbenchmarks werden nicht als eigene Messwerte übernommen.

Tesseract und die beiden Qwen-Modellkarten weisen Apache-2.0 aus, das
Docling-Projekt MIT. Daraus folgt keine pauschale Freigabe der gesamten Pipeline:
Modellgewichte und alle Abhängigkeiten sind einzeln zu berücksichtigen, insbesondere
[PyMuPDFs Lizenz](https://github.com/pymupdf/PyMuPDF/blob/main/COPYING).
`permitted_use` bleibt bis zur dokumentierten Prüfung der konkreten Nutzung und
Datenfreigabe offen. Lokale Ausführung allein bestätigt keine vollständige
datenschutzrechtliche Zulässigkeit.

## Stufe A: harte Bedingungen und gewichtete Evidenz

Das ausführbare Protokoll steht in [`configs/selection.yaml`](../configs/selection.yaml).
Harte Bedingungen: ausschließlich lokale Verarbeitung, festgeschriebene Versionen,
strukturierte Vierfeld-Ausgabe, nachgewiesene Eignung für die 16-GiB-Umgebung und
zulässige konkrete Nutzung. Ein belegtes Nein schließt einen Kandidaten aus;
unbekannt bleibt offen und erlaubt nur eine vorläufige Empfehlung. `ocr_raw` bleibt
unabhängig davon diagnostisch erhalten.

Gewichte sind vor Einsicht in Pilotresultate zu begründen und einzufrieren:

| Kriterium | Gewicht | Aktuelle Evidenz |
|---|---:|---|
| Eignung für den realen Schriftmix | 25 % | unabhängig noch nicht gemessen |
| Layoutrobustheit | 15 % | repräsentative Prüfung offen |
| Implementierte Vierfeld-Schnittstelle | 15 % | binär im Code belegt; keine Qualitätswertung |
| Versionierung und Wiederverwendung | 10 % | binär im Code belegt; keine Bitgleichheitsgarantie |
| Laufzeit | 15 % | kontrollierte vergleichbare Messreihe offen |
| Ressourcen/Kosten | 10 % | vollständige Messbasis offen |
| Implementierungsaufwand | 5 % | Zeitprotokoll fehlt |
| Wissenschaftlicher Zusatznutzen | 5 % | qualitativ über Rollen begründet; keine belastbare Punktzahl |

Diese Gewichte sind eine offen deklarierte Forschungsentscheidung, kein empirisch
bestimmtes Optimum. Sie lassen sich in YAML ändern; dafür wird ein neuer Plan
eingefroren. Zahlen sind nur auf einer dokumentierten Skala mit überprüfbarem
Beleg zulässig. Fehlende Evidenz wird als `null`, niemals als geschätzter Mittelwert
oder null Punkte gespeichert. Bei Lücken gibt es keinen gewichteten Gesamtscore
und kein Stage-A-Ranking. Evidenzabdeckung und mögliche Scoreintervalle sind
lediglich Transparenzangaben. Vollständige Bewertungen verwenden normalisierte
Gewichte und eine gewichtete Summe. Die Gewichte beeinflussen keine Feldmetriken.

## Stufe B: Stichprobe und Trennung

Eine Liste ist eine eindeutige PDF, keine Teilnehmerzeile oder Seite. Ziel sind
zunächst 40 Pilotlisten (konfigurierbar 30–50), mindestens 30 Listen und fünf
unabhängige Gruppen für eine pilotgestützte Empfehlung. Diese Mindestzahlen sind
pragmatische Explorationsgrenzen, keine statistische Powerberechnung oder
Signifikanzgarantie. Gruppen können die Zielzahl überschreiten und werden niemals
geteilt. Gruppen- und Stratazahlen werden zusätzlich berichtet.

Zuerst ein lokales, gitignoriertes Inventar erzeugen, aus `software/`:

```powershell
.\.venv\Scripts\participant-bench.exe selection inventory --input data/mein_korpus --output data/selection/inventory.csv
```

Vor dem Einfrieren **manuell** prüfen und ergänzen:

- `dependency_group`: alle PDFs derselben Schulung zusammenhalten; darüber hinaus
  verwandte Vorlagen, Duplikate und wiederkehrende Personen gegebenenfalls zu
  einer größeren Abhängigkeitsgruppe zusammenfassen. Namen gehören nicht in die
  Metadaten. `grouping_reviewed=true` bestätigt diese Prüfung.
- `prior_use`: `development`, sobald das Dokument oder seine Gruppe schon für
  Prompt-/Regel-/Parameteroptimierung verwendet wurde; sonst nach Prüfung `unused`.
  Der technische Standard `unknown` ist absichtlich nicht einfrierbar.
- `stratum`: `printed`, `mixed` oder `handwritten`. Erwartet werden mindestens
  `printed` und `mixed`; rein handschriftliche Listen nur bei passendem Zielbestand.
- `quality_flags`: semikolongetrennte Kategorien wie `clean`, `low_contrast`,
  `skew`, `shadow`, `cropped`, `wrapped_text`, `headerless_continuation`,
  `multiple_pages`, `variable_layout`. Keine Modellvorhersagen als Labels verwenden.
- `partition`: explizit `development`, `pilot`, `test` oder für bislang unbenutzte
  Gruppen leer. Frühere Entwicklungsnutzung erzwingt die Entwicklungsgruppe.

```powershell
.\.venv\Scripts\participant-bench.exe selection freeze --inventory data/selection/inventory.csv --policy configs/selection.yaml --output data/selection/plan.json
```

Unbenutzte, nicht explizit zugeteilte Gruppen werden über den bestehenden
gruppierten, stratifizierten Splitter mit Seed 42 in Entwicklung/Pilot/Test
(20/60/20) aufgeteilt; hierfür sind mindestens fünf solche Gruppen nötig.
Innerhalb des Pilotpools erfolgt die Auswahl stratifiziert und in stabiler
Hashreihenfolge. Kleine explizite Entwicklungs-Gegenproben sind möglich, werden
aber nicht zu Pilotdaten umetikettiert. Eine unbekannte Vorbenutzung kann der
Code nicht erkennen; die manuelle Erklärung ist eine methodische Voraussetzung.

Der Plan speichert SHA256-IDs, Metadaten, Gruppen, Teilmengen, Seed, Auswahlregeln,
Konfigurationen und ein Integritätssiegel. Nachträgliche Änderungen erfordern eine
neue Planversion. Ein Siegel verhindert unbemerkte Änderungen, keine absichtliche
Manipulation. Die Auswahlbefehle akzeptieren keinen Testmodus. Quellläufe, deren
Manifest finale Testdokumente enthält, werden für die Auswahl zurückgewiesen.
Finale Test-PDFs werden nach dem Inventar-/Hashschritt im Auswahlpfad nicht geöffnet
oder gerendert. Eine finale Evaluation erfolgt erst nach eingefrorener Auswahl
über das reguläre Testframework, ohne erneute Verfahrensauswahl.

## Vorhandene Ergebnisse wiederverwenden oder lokal ausführen

Für bestehende Vergleichsordner wird deren eingefrorene Referenz verwendet:

```powershell
.\.venv\Scripts\participant-bench.exe selection compare --plan data/selection/plan.json --comparison docling=testframework/ergebnisse/VERGLEICH --comparison paddle_llm=testframework/ergebnisse/VERGLEICH --comparison vlm=testframework/ergebnisse/VERGLEICH --output runs/selection-pilot-v1
```

Jeder Kandidat wird ausdrücklich an einen Quelllauf gebunden. `docling_vlm` darf
nur an einen Lauf mit aktivem Assist gebunden werden. Fehlende Kandidaten bleiben
sichtbar `missing`; fehlgeschlagene und nicht verfügbare Seiten werden separat
gezählt. Es wird keine günstigere gemeinsame Schnittmenge der vorhandenen
Ergebnisse gebildet: Quellmanifeste müssen alle ausgewählten Dokumente enthalten.
Gleiche tatsächliche Laufbilder werden per Hash geprüft. Abweichungen vom
eingefrorenen Profil verhindern eine abschließende Empfehlung.

Optionale neue Inferenz, ohne Referenzübergabe, mit den eingefrorenen vorhandenen
Profilen und explizit gewählten Kandidaten:

```powershell
.\.venv\Scripts\participant-bench.exe selection run --plan data/selection/plan.json --candidate docling --candidate paddle_llm --candidate vlm --output runs/selection-inference-v1
.\.venv\Scripts\participant-bench.exe selection compare --plan data/selection/plan.json --sources runs/selection-inference-v1/sources.json --reference testframework/referenz/DEINE_REFERENZ.xlsx --benchmark-config testframework/config.yaml --output runs/selection-pilot-v2
```

Kopiert werden ausschließlich die ausgewählten PDFs; historische Eingaben und
Ergebnisse bleiben erhalten. Keine Downloads, API-Aufrufe oder neuen Modelle.
Für eine vorbenutzte Entwicklungs-Gegenprobe ausdrücklich `--scope development`
angeben. Eine spätere Änderung von Auswahlkriterien nach Einsicht in Pilotdaten
ist als neue explorative Entscheidung zu dokumentieren; finale Testdaten bleiben
unberührt. Das Risiko der Überanpassung von Auswahlentscheidungen ist unabhängig
vom Training eines Modells relevant ([Cawley und Talbot, 2010](https://www.jmlr.org/papers/v11/cawley10a.html)).

## Metriken und Entscheidung

`evaluate_run` wird auf denselben Dokumenten und Referenzkursen mit denselben
Originalextraktionen ausgeführt: einmal `compare_name_orientations=false`, einmal
`true`. Die globale Paarung wird jeweils neu berechnet. Zusätzlich bewertet
`course_metrics(..., score_original_roles=True)` die unveränderten Originalrollen
auf **denselben Paaren wie der referenzgestützte Swap-Vergleich**. So wird sichtbar,
wenn eine andere Personenpaarung Namensrollenfehler überdeckt. Diese dritte Ansicht
(`original_roles`) ist primär; `strict` mit neu berechneter Paarung ist eine
Sensitivitätsansicht. Alle Paarungen bleiben referenzgestützt und sind keine
unabhängige Identitätsprüfung. Normalisierte exakte Treffer und unveränderte
Zeichenfolgen (`raw_exact_fields`) bleiben getrennt.

Berichtet werden Exact Match/Recall, exakter und Levenshtein-Feld-F1, Feldabdeckung,
fehlende/zusätzliche Personen und Felder, Fehler je Feldtyp, Dokument- und Seitenzahl,
Referenznenner, technische Statuszahlen, Seiten-/Dokumentlaufzeiten und vorhandene
Ressourcen. Nicht verfügbare Messungen bleiben leer. `partial` mit gültigem Schema
ist technisch verarbeitbar, aber keine Aussage über richtige Feldwerte. Alle
Referenzfelder behalten auch bei Ausfällen ihren Nenner. `ocr_raw` benötigt für
CER/WER unabhängige Transkripte und erhält keinen Feldrang.

Seitenzeiten enthalten nicht sämtliche gemeinsamen Lade-/Warm-up-Kosten. Volle
Methodenlaufzeit und Ressourcen betreffen ausdrücklich den ganzen Quelllauf;
sie werden nicht einer Teilstichprobe anteilig zugeschätzt. Cachetreffer und
ursprünglich zugerechnete Erkennungszeiten bleiben separat erhalten. GPU-Allokation
eines Frameworks ist keine vollständige VRAM-Messung. Energie, Eurokosten und
manuelle Nacharbeit werden ohne Messung nicht geschätzt.

Maximal drei Hauptrollen bleiben erhalten: Struktur, OCR+LLM, direktes VLM.
Innerhalb der OCR+LLM-Rolle entscheidet bei vollständigen, vergleichbaren
Pilotdaten der **exakte Feld-F1 der Originalrollen bei festen Referenzpaaren**, bei Gleichstand Feldabdeckung und
schließlich stabile Kandidaten-ID. Eine fehlende Gegenmessung gilt nicht als
Unterlegenheit. Eine vorläufige Rolle ohne vollständige Messung wird lediglich
anhand der stabilen ID belegt und ausdrücklich als unbelegt gekennzeichnet.
Der Stage-A-Gesamtscore ist bei fehlenden Kriterien absichtlich nicht entscheidbar;
er wird nicht durch implizite Gewichtsänderung zur künstlichen Rangliste gemacht.

Optional wird `ocr_vlm` gegen `vlm` empfohlen: gleiche VLM-Gewichte, Revision,
Bildparameter und Grundschema, zusätzlicher Paddle-Hinweis. Für diesen Versuch
müssen auch die gespeicherten Inferenzparameter und Prompts kontrolliert werden.
Docling-VLM bleibt eine alternative, breitere Ablation, weil zusätzlich selektive
Aufruf- und Merge-Regeln wirken. Beide Varianten werden nicht als zusätzliche
Hauptarchitekturen gezählt. Historische Verfahren und Ergebnisse werden nicht gelöscht.

## Artefakte und Grenzen

Der Ausgabeordner enthält `report.html`, `selection.json`, `candidates.csv`,
`gates.csv`, `matrix.csv`, `pilot.csv`, `field_scores.csv`, `document_timings.csv`
und die regulären, vollständig nachvollziehbaren Vergleichsberichte unter
`evaluations/<Kandidat>/{strict,reference_assisted}/`. Alle personenbezogenen
Detailartefakte verbleiben in gitignorierten lokalen Daten-/Ergebnisordnern.

Verglichen werden ganze Pipelines, nicht isolierte Basismodelle: OCR-Engine,
Tabellenstruktur, native Textebenen, Vorverarbeitung, Prompts, Literal-/Positions-
prüfungen, Namensheuristiken und Assist-Merging sind mögliche Confounder.
Eine gemeinsame 4B-Bezeichnung bedeutet keine gleiche Architektur oder Rechenlast.
Die Kursreferenz belegt ohne manuelle Prüfung weder tatsächliche Anwesenheit noch
die Seitenlokalisierung und erlaubt keine eigenständige Handschrift-CER/WER.
Stichprobenumfang, fehlende Strata, Abhängigkeiten und Vorbenutzung begrenzen jede
Verallgemeinerung. Ein endgültiges wissenschaftlich ausgewähltes Hauptprofil ist
damit noch nicht begründet. Auf ausdrücklichen Nutzerwunsch steht
`configs/benchmark-four.yaml` als vorläufiges Laufprofil für `ocr_rules`,
`paddle_llm`, `vlm` und `ocr_vlm` bereit; Start aus `software/` über
`.\start_testframework_4.cmd`. Dies aktiviert nicht automatisch eine endgültige
Auswahl oder ein anderes Standardprofil. Auf Nutzerentscheidung ersetzt die
klassische Tesseract-/Regelbaseline in diesem Laufprofil Docling. `ocr_rules`
liefert strukturierte Teilnehmerfelder und ist gegenüber `ocr_raw` ausdrücklich
ein anderer Kandidat. PP-OCRv6, Qwen3-8B und PaddleOCR-VL-1.6 sind damit noch nicht
integriert; das vorhandene Paddle-Verfahren verwendet weiterhin PP-OCRv5 und
Qwen3-4B-Instruct-2507. Der aktuelle tatsächliche Gegenprobenstand steht in
[method-selection-status.md](method-selection-status.md).

Nach ausdrücklicher Nutzerklärung ist `ocr_llm` zusätzlich gewünscht. Das Profil
`configs/benchmark-five.yaml` erbt das Viererprofil und wählt `ocr_rules`,
`ocr_llm`, `paddle_llm`, `vlm`, `ocr_vlm`; Start mit
`.\start_testframework_5.cmd` aus `software/`. Tesseract+LLM und Paddle+LLM
verwenden weiterhin dasselbe Qwen3-4B-Instruct-2507. Docling gehört zu keinem
dieser beiden separaten Laufprofile. Die neue Fünferauswahl ist eine
Nutzerentscheidung; die historischen Auswahlberichte werden nicht umgeschrieben.
