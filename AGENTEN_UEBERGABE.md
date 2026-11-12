# Projektstand und Übergabe für folgende Agenten

Zuletzt aktualisiert: **2026-11-12** (Europe/Berlin).

Diese Datei auf Wunsch des Nutzers bei Änderungen fortschreiben. Einstieg und
Pflegepflicht stehen in [AGENTS.md](AGENTS.md). Sie ist die zentrale Übergabe,
auch wenn frühere Chatnachrichten oder ein vorheriges Kontextfenster fehlen.

## Aktueller Stand

### Neuer Dreidokumentlauf (12.11., läuft)

- Auf ausdrücklichen Folgeauftrag neuer normaler Fünferlauf gestartet:
  `software/runs/20261112T071339Z-ca4962b3`, ausschließlich die drei bereits
  verwendeten Entwicklungs-PDFs `146079`, `143890`, `162575`, sechs Seiten.
  Isolierte, hashgleiche Eingabekopien unter
  `software/data/examples-three-20261112/input/`; Auswahl und unveränderte
  Referenzprüfsumme in `request.json`, Konsolenprotokoll in `run.log` daneben.
- Aktives Profil `configs/benchmark-five.yaml`: `ocr_rules`, `ocr_llm`,
  `paddle_llm`, `vlm`, `ocr_vlm`; keine Modelle, Prompts, Limits oder
  Bewertungsregeln für diesen Lauf verändert. Automatische Orientierung aktiv,
  kein manuelles Manifest: beide Seiten von `146079` um 90° korrigiert,
  übrige vier Seiten beibehalten. Alle sechs Seiten bereit, keine offenen
  Orientierungsentscheidungen. Cacheverwendung wird vom normalen Runner erfasst.
- **Noch nicht abgeschlossen:** Modellinferenz und neuer Vergleichsbericht.
  Die abgeschlossene Reportanalyse vom 11.11. und deren begrenzter Gegencheck
  sind hiervon getrennt. Abschlussdaten und Berichtspfad nach Laufende ergänzen.

### Systematischer Fehleraudit und kontrollierter Gegencheck (11.11.)

- **Letzter tatsächlich vollständiger Modelllauf:** weiterhin
  `runs/20261111T091101Z-59c4b71d`, historischer Fünfervergleich
  `testframework/ergebnisse/20261111T110330Z-09f5d83e`. Neuere Fehlerberichte sind
  keine neuen vollständigen Modellläufe. Der neue
  `testframework/ergebnisse/systematic-audit-20261111/after/` ist ein ausdrücklich
  gekennzeichneter **Teilgegenrecheck mit zwei neuen Textmodellaufrufen**, kein
  vollständiger Fünferlauf mit neuer Ausrichtung. Die zehn PDFs bleiben wegen
  ihrer dokumentierten Vorbenutzung Entwicklungsdaten; kein unabhängiger Finaltest.
- **Neu implementiert / aktiv:** `compact_assignment_rows` in
  `unlimited_assignment.py` lässt nur exakt aus unveränderten Zellrahmen
  rekonstruierbare doppelte Zeilenrahmen im LLM-Input weg. Texte, Reihenfolge,
  Positionen/Präzision und Validierungsbelege bleiben vollständig. Eigene
  Inputkompaktierungskennung, tatsächliche Prompts/Hashes und Fehlerstufe
  `input_budget` bleiben gespeichert. Keine Promptvorlagen-/Modell-/Limitänderung.
  Fehlerbericht v6 unterscheidet diesen Eingabeabbruch von ungültiger Modellantwort.
  `rules.layout` erhält außerdem das erste Datenband ab body_top; keine neue
  allgemeine Baseline-Headerheuristik aktiviert.
- **Technisch nachgewiesen:** beide früher vor Generierung blockierten
  Paddle-Seiten von 13.298/12.575 auf 11.170/10.384 Tokens bei unverändertem Limit
  12.000. Alle zwanzig gespeicherten Inputs aus zehn PDFs rückwärts exakt
  rekonstruierbar, danach keiner über Budget. Gesamte JSON-/JSONL-Bestände des
  Quelllaufs und Laufprotokoll geprüft. Reale Regelbaseline trotz Bandkorrektur
  unverändert null Teilnehmer; dort weiterhin Vorlagen-/OCR-Probleme.
- **Begrenzt gemessene Qualität:** zwei lokale Qwen3-4B-Textaufrufe plus ein
  unveränderter Warm-up, gleiches Modell/Gewichte/Systemprompt/Schema und gleiche
  Grenzen wie gespeichert, keine neue OCR/VLM-Inferenz/API/Downloads. Nur zwei
  Paddle-Seiten ersetzt, 18 erfolgreiche Paddle-Seiten und die vier anderen
  Verfahren unverändert. Paddle bei unveränderter Referenz: **exakt 122→133,
  falsch 36→44, fehlend 462→443, zusätzliche Felder 0→0**, Ausgabedatensätze
  45→55. Neue Gewinne ausschließlich Namen; ID/Organisation unverändert und im
  betroffenen Formular nicht vorhanden. Recall 19,68→21,45 %, F1 31,36→33,38 %,
  Precision verschlechtert 77,22→75,14 %. Kein Nachweis allgemeiner
  Halluzinationsfreiheit; zusätzliche falsche Namenswerte ausdrücklich offen.
- **Verworfene Gegenproben:** allgemeiner Baseline-Headerprototyp 64 exakte,
  aber 40 falsche Felder: nicht in Produktivcode/Profilen aktiviert. Eine erste
  Zwischenvalidierung ohne korrekt aus dem tatsächlichen Input rekonstruierte
  Feldbänder überzeichnete die Ausgabe und ist kein Nachweis. Maßgeblich nur
  `data/systematic-audit-20261111/validated-source-final/`, öffentlicher After-
  Bericht und `quality_comparison.json`. Keine Positionsprüfung gelockert.
  Frühere Parserreparaturen getrennt nachgeprüft: VLM +6 exakte/+3 falsche IDs,
  Hybrid +9 exakte ohne neue falsche Felder; keine neuen Erfolge dieser Korrektur.
- **Tests:** 14 neue Regressionen, abschließend **864 lokale Tests (94,81 s)**
  und **48 API-Tests (11,02 s)** bestanden; Ruff ohne Befund. Quellen/Referenz und
  numerische historische Bewertungen bleiben erhalten. Originaler HTML-Bericht
  erhält nur einen Link zur neuen Analyse; exakte Sicherung im lokalen Auditordner.
- **Dokumentiert / nächste Schritte:**
  `software/docs/systematic-error-analysis-20261111.md`, Software-README und
  Fehleranalyse-Einstieg ergänzt. Neue HTML-Übersicht unter
  `software/testframework/ergebnisse/systematic-audit-20261111/report.html`.
  Offen: neun Ausgabetokenabbrüche, vierzehn leere OCR+LLM-Antworten, falsche
  Zeichen/Handschrift und unzuverlässige Tabellenstruktur; vollständiger neuer
  Fünferlauf zur Wirkung der aktiven Orientierungs-/Kontextreparaturen weiterhin
  ausstehend. Unbekannte Felder und Kursreferenzabweichungen nicht geraten reparieren.

### Seitenübergreifende Spaltenzuordnung (11.11., erneut abgesichert)

- **Implementiert / aktiv:** vorhandenes `column_context.resolve` auf Kontext v2
  erweitert; keine neue Pipeline. Dieselbe PDF, frühere zuverlässige Quellseite,
  vergleichbare Spaltenzahl/Geometrie und unverändert höchstens 0,035 normierte
  Kantenabweichung erforderlich. Mehrere kompatible Folgeseiten können denselben
  letzten Überschriftenbeleg nutzen. Aktuelle eindeutige Überschriften haben
  Vorrang; neue unvollständige/mehrdeutige Blöcke sperren den alten Gesamtzustand.
- **Belegte Korrekturen:** frühere Intervalle gelangen nach abgelehnter/fehlender
  Geometrie nicht mehr in den nativen OCR-Fallback. Tesseract/Paddle sammeln
  mehrzeilige Überschriften einschließlich ID/Organisation; Paddle verwendet die
  tatsächlichen physischen Spalten statt der Rangfolge erkannter Überschriften.
  Getrennte eindeutige VLM-Namensspalten haben ebenso wie ID/Organisation Vorrang
  vor semantischen Feldern. Die nachgelagerte dokumentweite Namensprüfung darf
  belegte getrennte Spalten nicht durch die globale Standardreihenfolge ersetzen
  oder allein deswegen unsicher markieren. Kombinierte Namensregeln bleiben bestehen. Gemessene
  Zwei-/Dreispaltenraster sind verwendbar. Keine Werte aus vorherigen Personen.
- **Kontextschutz:** erlaubte Überschriftenlabels/Feldrollen und Positionen statt
  vollständiger OCR-Zellen. Ein echter aufgebauter Test-LLM-Input reproduzierte
  zuvor angehängte Inhalte alter Überschriftenzellen in `previous_headers`;
  dies ist jetzt gezielt behoben. Aktuelle Originalbelege bleiben erhalten.
- **Berichte:** Haupt-/Fehlerbericht und `document_column_mappings.csv` nennen
  Feldspalten, Überschriftenquelle, Quellseite und deutsche Begründung sowie
  gemessene Quell-/Zielgeometrie, größte Abweichung und Grenze. Auch gespeicherte
  VLM-/Hybridentscheidungen sind enthalten. Historisch fehlende Werte bleiben
  unbekannt; keine nachträgliche Rekonstruktion aus Teilnehmerdaten.
- **Prüfung / Nachweise:** 30 neue Regressionen in
  `software/tests/test_column_continuation_audit.py`; **850 lokale Tests
  (98,07 s)** und **48 API-Tests (9,77 s)** bestanden. Abschließende lesende
  Berichtsergänzung zusätzlich mit **99 gezielten Tests (3,56 s)** geprüft.
  Ruff, regulärer Diff-Check und 908 lokale Bericht-Dateilinks ohne Befund.
  Synthetischer Dreiseiten-Replay mit zwei
  Übernahmen unter `software/data/column-context-20261111/synthetic-report/`.
  Realer bestehender Bericht neu gerendert unter
  `software/testframework/ergebnisse/column-context-20261111/`; gespeicherte
  Bewertungsdateien bytegleich, 1.762 historische Dateien unverändert.
  Historische sechs Übernahmen sind keine neuen realen Erkennungsnachweise.
- **Dokumentiert / Grenzen:** `software/docs/document-columns.md` und
  Framework-README aktualisiert. Aktive Kontextpfade: Tesseract+LLM, Paddle+LLM,
  VLM/Hybrid; zusätzlich verfügbares Docling-Mapping. Regelbaseline bleibt bei
  ihrer bestehenden Vorlagenlogik. Keine Modelle, Konfigurationen, Promptvorlagen oder
  Abhängigkeiten ergänzt. Kontext-/räumliche Zuordnung v2/v10, Fehlerbericht v5.
  Keine neue Inferenz auf realen Dokumenten und kein realer Qualitätsgewinn
  behauptet; synthetische OCR-Regressionen sind Teil der bestehenden Gesamtsuite.
  Nächster Schritt: normaler neuer Fünferlauf auf den bereits zur Entwicklung
  verwendeten, automatisch ausgerichteten Dokumenten; geometrisch identische
  semantische Spaltenvertauschung ohne Überschriften bleibt nicht sicher erkennbar.

### Automatische Seitenausrichtung (11.11., repariert, aktiv und geprüft)

- **Auftrag / umgesetzt:** der Folgeauftrag verlangt automatische Korrektur im
  normalen Lauf. Neues `orientation.py` und `OCR.orientation_evidence` ergänzen
  schwaches/fehlgeschlagenes OSD durch vier begrenzte CPU-Textdiagnosen. Keine
  Referenzen, Namen, Feldmuster, Dokumentkennungen, manuellen Winkel oder neuen
  Modelle gehen in die Entscheidung ein. Ausreichender OSD-Befund bleibt bestehen.
  Bei offenem Vergleich bleibt die Seite prüfpflichtig statt geraten gedreht.
- **Aktiv:** direkt in `pdf.prepare`, mit vorhandenem `pdf.auto_orient: true`.
  `start_testframework_5.cmd` genügt wieder ohne manuelles Manifest. Alle Methoden
  nutzen das gemeinsam ausgerichtete Vollbild; PDF-Metadaten werden vorher einmal
  berücksichtigt. Native Docling-PDFs kombinieren Zusatz-/Metadatenrotation passend.
- **Regel:** PSM 11, Diagnose höchstens 2.600 Pixel längste Seite; mindestens
  fünf lesbare Wörter/25 Buchstaben, gewichteter Zeichenscore, Abstand mindestens
  15 und Faktor mindestens 1,5 gegenüber Platz zwei. Konfidenzfilter 50 nur für
  diese Diagnose, keine Änderung der Feld-/OCR-Aufnahmebedingungen. Der Score
  ist keine Wahrscheinlichkeit. Vier Proben müssen vollständig/fehlerfrei sein;
  Timeouts oder unzureichende Evidenz bleiben offen. Je Aufruf maximal 15 Sekunden
  beziehungsweise kleineres OCR-Timeout. Nur gedreht, Extraktionspixel nicht
  zugeschnitten oder verkleinert.
- **Nachvollziehbarkeit:** OSD-Vorschlag/-Konfidenz getrennt von Methode,
  Entscheidung, vier Scores/Zählern und tatsächlicher Rotation im Manifest.
  Vorbereitungs-/Ausrichtungszeit enthält Zusatzaufwand. Haupt-/Fehlerbericht
  ergänzt. Neue Manifestkennung `orientation-v1-osd-ocr-comparison`; alte
  ungeprüfte automatische Manifeste müssen neu vorbereitet werden. Explizit
  kuratierte manuelle Manifeste bleiben hash-/konfigurationsgeprüft verwendbar.
  Kein unverändertes Resume eines alten Modelllaufs mit geändertem Code.
- **Realer technischer Nachweis:** reguläres automatisches prepare auf genau
  zehn vorhandenen Entwicklungs-PDFs/zwanzig Seiten, ohne manuelles Manifest:
  **20/20 passend zur vorherigen Sichtung, zwölf korrigiert, acht beibehalten**.
  Ein OSD- und neunzehn OCR-Vergleichsentscheide, keine offenen Seiten in diesem
  Bestand. Vollständige Pixel aller zwanzig Seiten gleich den zuvor gesichteten
  Rotationen. Original-PDFs und 1.762 geschützte historische Dateien unverändert.
  Beobachtete Vorbereitung 84,64 s; kein kontrollierter Laufzeitbenchmark.
  Lokaler Nachweis: `software/data/auto-orientation-20261111/validation.json`,
  visuell geprüfte Kontaktansicht und `preview.html`. Kein neuer LLM-/VLM-Lauf.
- **Tests:** 48 neue Regressionen einschließlich vier echter OCR-Fallbacktests
  bei kontrolliertem OSD-Ausfall und aller 16 Kombinationen aus PDF-Metadaten-
  und Zusatzrotation samt nativem Docling-Pfad. Blank-/Logo-/Ziffern-Diagnosen
  zusätzlich geprüft. Gesamtsuite **820 bestanden (96,21 s)**,
  **48 API-Tests bestanden (9,77 s)**, Ruff ohne Befund. Normales Diff-/Artefakt-
  und Starter-Check-Ergebnis siehe Protokoll. Keine neuen Abhängigkeiten/Prompts.
- **Dokumentiert / Grenzen:** `software/docs/automatic-orientation.md` und Links
  in README, Framework, local-methods und vorherigem Feldverlust-Audit. Vorab-
  verkleinerung auf 2.000 Pixel ließ eine dünn beschriftete Seite offen; bei der
  endgültigen Auflösung wird sie mit unveränderten Schutzschwellen entschieden.
  Keine allgemeine Zuverlässigkeitsgarantie für beliebige Handschrift/Sprachen.
  Die gemeinsame Vorverarbeitung verwendet jetzt OCR-Textdiagnosen auch für das
  direkte VLM, ohne OCR-Feldtexte weiterzugeben; in Methodik/Effizienz so berichten.
  Unabhängiger Feldqualitätsnachweis nach der Reparatur steht noch aus; übrige
  Header-/Token-/Referenzprobleme bleiben eigenständig. Nächster Schritt: normalen
  Fünferstarter für einen neuen Entwicklungsvergleich verwenden.

### Vorheriger Feldverlust-Audit (11.11., vor der automatischen Reparatur oben)

- **Untersuchter Lauf:** `20261111T091101Z-59c4b71d`, Vergleich
  `20261111T110330Z-09f5d83e`: zehn PDFs, zwanzig Seiten, fünf Verfahren,
  155 Kursreferenzpersonen/620 Referenzfelder je Verfahren. Docling dort nicht
  ausgeführt; separat den historischen Vergleich `20261110T123112Z-b454d615`
  untersucht. Alle zehn gesichteten PDFs künftig als zur Entwicklung vorbenutzt
  berücksichtigen; keine unabhängige Finalstudie behaupten.
- **Nachgewiesen:** zwölf seitliche gemeinsame Laufbilder, neunzehn OSD-
  Unsicherheitsmarkierungen/sieben OSD-Fehler/nur eine sichere Entscheidung.
  Alle hundert Methode-/Seitenbilder stimmen anhand der gespeicherten Hashes
  mit zwanzig gemeinsamen Laufbildern überein. Neun VLM-/Hybridseiten erreichen
  8.192 Ausgabetokens und fallen aus. Modellheader enthalten Metadaten oder
  Teilnehmerdaten; Zell-/Headerlängen passen teilweise nicht. Englische Rollen
  User/User Name fehlen im alten Parser. Ein Formular enthält tatsächlich keine
  ID-/Organisationsspalten, obwohl die externe Kursreferenz diese Werte hat.
  29 untersuchte ID-/Organisationsablehnungen: kein Vorschlag stimmt nach
  Normalisierung mit der Referenz überein; deshalb keine Validierungslockerung.
- **Implementiert / aktiv:** User als ID, User Name/Username als kombinierter
  Name; reproduzierten None-Geometrie-Absturz im vorhandenen Kontextmodul
  abgefangen (nicht als Ursache eines bestimmten historischen Feldfehlers belegt).
  Strukturell abgesicherter VLM-Seitenkontext samt Resume über vorhandenes
  `column_context.resolve`. Keine Übernahme aus Datenheadern, anderer PDF,
  ungemessener/abweichender Geometrie oder ungleichen Zellzahlen. Zustände
  enthalten keine Personenwerte. OSD-Vorschlag/Schwelle/Entscheidung separat
  protokolliert; automatische Rotationsregel und Konfidenzschwelle unverändert.
  Testframework reicht explizites `--manifest` an bestehenden Runner weiter.
- **Aktuelle Promptfamilie:** `participant-json-v26-roster-header-scope` klärt
  Teilnehmertabelle gegenüber Metadatentabellen und null-Header auf Folgeseiten.
  VLM-/Hybrid-System und Schema weiter identisch, Feldtypen/Schnittstellen gleich.
  v25 zuvor mit Hashes archiviert in
  `software/docs/prompt-history/pre-field-loss-20261111.json`. Keine Variantenstudie,
  keine neue neuronale Qualitätsmessung; neuer Code/Schemahash trennt Resume/Cache.
- **Berichte:** vorhandene Fehleranalyse um Feldstufen, gespeicherte Inputs/Hashes,
  Literal-/Positionsstände, Original-PDF, Ausrichtung, Bildhashabgleich und
  Spaltenkontext erweitert. Historische Warnungen bleiben maßgeblich; fehlende
  Übergabebelege bleiben unbekannt. Reine native Mapper als solche ausgewiesen.
  Neue Ausgabe ohne neue LLM-/VLM-Inferenz:
  `software/testframework/ergebnisse/field-loss-20261111-v2/extraction_errors.html`;
  historische Docling-Prüfung separat unter
  `software/data/field-loss-20261111/docling-report-v2/`.
- **Konkrete Prüfung:** acht Feldfälle in lokalem `cases.json`/`cases.csv`,
  aggregierter Nachweis in `software/data/field-loss-20261111/validation.json`.
  1.762 historische Dateien unverändert, 4.434 alte numerische Standardwerte
  identisch. Reines Neuparsen zweier gespeicherter englischer Antworten erhält
  18 wörtliche IDs einschließlich Nullen; kein gemessener Gesamtscoregewinn.
  24 CPU-OSD-Proben: vier synthetische Orientierungen korrekt, real weiterhin
  sieben Fehler/eine sichere Entscheidung. Geprüftes Korrekturmanifest für genau
  diese zehn PDFs und korrigierte Kontaktansicht; kein neuer vollständiger Lauf.
- **Tests:** 31 neue Regressionen; abschließend 772 lokale Tests (77,06 s),
  48 API-Tests (9,85 s) bestanden, Ruff ohne Befund. Normale Diff-Prüfung und
  Artefakt-/Linkprüfungen siehe Protokoll. Keine PDFs/Thesistexte bearbeitet.
- **Nächster Schritt / Grenzen:** für diese gesichteten Entwicklungsdaten aus
  `software/` optional `start_testframework_5.cmd --manifest
  data/field-loss-20261111/curated-manifest.json` verwenden; startet einen neuen
  Modelllauf und wurde im Audit nicht ausgeführt. Dokumente/Bildhashes müssen
  unverändert sein. Die sichere VLM-Fortsetzung bleibt bei inkompatiblen realen
  Header-/Rasterlisten bewusst gesperrt. OSD-Zuverlässigkeit, Tokenabbrüche,
  Vorlagenbindung der Regelbaseline und Referenzeignung bleiben offen. Belegte
  Übergänge nicht mit eindeutiger ursprünglicher Ursache verwechseln.
  Vollständige Dokumentation: `software/docs/field-loss-20261111.md`.

### Wissenschaftliches HTML-Dashboard (11.11., implementiert und technisch geprüft)

- **Implementiert / aktiv für neue Berichte:** bestehende Feldmetriken,
  Normalisierung, Matchingansichten, Metadaten und Cluster-Bootstrap wiederverwendet.
  `metrics.py` ergänzt vollständige Vierfeldreferenzen getrennt von Teilreferenzen
  und nicht bewertbaren Personen sowie strikten Teilnehmer-Recall. Eindeutiger
  Referenzanker und exakte bestimmbare Identitätsfelder sind erforderlich; Best-Fit-
  Paarzahlen allein genügen nicht. Neue Zähler werden gepoolt, historische Zähler
  und Standardbewertungen bleiben unverändert. Keine neuen Modelle oder Abhängigkeiten.
- **Darstellung:** `dashboard_report.py` mit sechs Bereichen, sortierbarer
  Haupttabelle, Feldheatmap, Ursachen-/Schulungs-/Dokument-/Feldfiltern, verlinkter
  vorhandener Einzelfallanalyse, robustheitsbezogenen Fallzahlen sowie Effizienz
  und Statistik. Primär Originalrollen auf festen referenzgestützten Paaren;
  alter Standardbericht in neuen Ausgaben als `standard_report.html` erhalten.
  Fehleraggregation und Einzelfälle verwenden dieselben Originalrollenentscheidungen;
  pro Feldfehler ein konservativer Ursachenbereich, Seitenereignisse getrennt.
- **Effizienz / zentrale Exporte:** `scientific_efficiency.py` ergänzt beobachtete
  Seitenmediane/Quartile, konsistente tatsächliche Aufrufe je Seite/PDF mit
  Namenshilfsschritten und separatem Warm-up. LLM/VLM nur bei eindeutigem Pfad
  trennen. Euro-Messartefakte fehlen; gemessene Kosten bleiben JSON-null und
  als nicht verfügbar markiert. Vollständige bestehende Kostenszenarien werden
  explizit getrennt auf 1.000 PDFs umgerechnet. Neue Definitionen und Teilnehmer-,
  Aufruf-/Kostenexporte in `scientific/analysis.json` und CSV verwenden dieselben Zähler.
- **Getestet:** 741 lokale Tests (73,11 s), 48 API-Tests (10,73 s), danach 94
  gezielte Nachtests (11,07 s) bestanden. 13 neue Dashboard-/Metriktests einschließlich
  tatsächlichem JavaScriptcode für Tabs, Sortierung und kombinierte Filter. Ruff
  und reguläres `git diff --check` bestanden. LaTeX/BibTeX Exitcode 0, 36 Seiten;
  Methodikseiten visuell geprüft, keine fehlenden Zitate/Boxüberläufe. Bekannter
  epstopdf-Shell-Escape-Hinweis bleibt; keine Downloads/Toolchainänderungen.
- **An gespeicherten Referenzen technisch nachgewiesen:** zwei getrennte Replays,
  keine neue Inferenz. `software/testframework/ergebnisse/dashboard-20261111-v1/`
  nutzt fünf Verfahren, eine Entwicklungs-PDF/zwei Seiten/18 Personen/72 Felder;
  `software/data/dashboard-20261111/synthetic/` vier gespeicherte neuronale Pfade,
  eine synthetische Druckseite/zwei Personen/sieben Felder/eine Teilreferenz.
  Jeweils nur eine unabhängige Gruppe. CSV/JSON, CSP-Skripthash und 89 lokale
  Dashboardlinks geprüft; 4.119 historische numerische Standardwerte identisch.
  Alle 863 geschützten Quelldateien unverändert. Lokaler aggregierter Nachweis:
  `software/data/dashboard-20261111/validation.json`.
- **Dokumentiert:** `software/docs/scientific-evaluation.md`, Framework-/Software-
  README und Methodik 3.7/3.8 ergänzt. Sokolova/Lapalme (Verlagsabstract/Metadaten)
  und Field/Welsh (Originalvolltext/Verlagsmetadaten) verifiziert und separat in
  `verified_sources.bib` ergänzt; Zotero-Export unverändert. Konkrete Anker-/GT-Regeln
  sind eigene Operationalisierungen, keine extern validierte Identitätsmethode.
- **Offen / Grenzen / nächster Schritt:** visuelle HTML-Browserabnahme wegen
  nicht unterstützter Windows-Browsersteuerung offen; DOM-/Skriptprüfung ersetzt
  keine Sichtprüfung verschiedener Bildschirmgrößen. Keine belastbaren CIs bei
  einer Gruppe, keine empirischen Eurokosten, unabhängige Handschrift-/Seiten-
  transkripte fehlen. Teilnehmerquotienten zunächst deskriptiv ohne eigene CIs.
  Referenzgestützte Paarung und mehrdeutige Identitäten bleiben transparent;
  feinere PDF-Qualität bei gemeinsamen Kursreferenzen nicht erfunden. Beispiele
  unterschiedlicher Promptstände nicht poolen. Vor unabhängiger Studie Metadaten/
  Gruppen prüfen und Code/Profile/Prompts einfrieren; Hauptbericht lokal sichten.

### Einmalige literaturbasierte Promptüberarbeitung (11.11., abgeschlossen)

- **Implementiert / aktiv:** eine feste Promptfamilie in
  `software/verarbeitung/src/participant_bench/extraction_prompts.py`, sechs
  Abschnitte (Aufgabe, Teilnehmer/Felder, Extraktion/Zuordnung, unbestimmte Werte,
  Mehrseitigkeit, JSON-Vertrag). Gemeinsame Regeln werden explizit zusammengesetzt;
  notwendige OCR-Zeilen-/Zellen-, Bild-, Page-/Record- und Legacy-Verträge bleiben
  erhalten. Keine zusätzlichen Kandidaten, Modelle, Abhängigkeiten oder
  Promptoptimierungsstudie. Fünferprofil unverändert; VLM/OCR-VLM verwenden identische
  Systemnachricht und Schema, Hybrid zusätzlich belegte OCR-Hinweise.
- **Versionen der Erstüberarbeitung:** `participant-json-v25-literature-guidelines`
  (technischer Nachfolger v26 im Feldverlust-Audit oben), Zellzuordnung
  `ocr-cell-assignment-v23-literature-guidelines`, vorhandener Positionseingabepfad
  v24, Namensregeln v4 und Rollenregeln v2. Vorherige Texte, sechs kompilierte
  Systemnachrichten, Schemas und Quellhashes archiviert in
  `software/docs/prompt-history/pre-20261111.json`, ohne Runtime-Auswahl alter Prompts.
- **Technische Konsistenz:** `name_order.basis` im neuen Generierungsschema
  verpflichtend und im Formbeispiel enthalten. Neue Antworten ohne explizite Basis
  erhalten unbekannte Namensentscheidung statt stiller Dokumentautorität; belegte
  Teilnehmerfelder bleiben erhalten. Historische Parser behalten ihre Lesbarkeit.
  Record-Antworten verlangen keine fremden Top-Level-Felder. Bestehende Matching-,
  Referenz-, Feldnenner-, Literal-/Positions- und Nachverarbeitungslogik bleibt bestehen.
- **Nachvollziehbarkeit:** `extraction_prompt_snapshot()` wird für reguläre Läufe,
  Neuzuordnung und Auswahlplan gemeinsam verwendet. `prompts.json` enthält Texte,
  kompilierte Nachrichten, Schemas und Hashes. Tatsächliche Systemnachricht mit
  Schema, dynamischer Benutzertext und beide Hashes sowie Schemahash werden auch
  pro Extraktions-/Namensaufruf gespeichert. Historische Ergebnisse bleiben erhalten;
  geänderte Lauf-/Prompt-/Schemaidentitäten verhindern unbemerkte Cache-/Resume-Mischung.
- **Literatur / Dokumentation:** fünf geprüfte Quellen (Prompt Report, GoLLIE,
  InstructUIE, Geng et al. zu Grammardecodierung, Huang et al. zu Halluzinationen),
  Regelmatrix mit Anforderungen, Herkunft und Fehlerklassen in
  `software/docs/prompt-design.md`. Gestaltungsentscheidungen und Evidenzgrenzen
  ausdrücklich getrennt; keine Übertragung von Fine-Tuning-Ergebnissen auf Qwen.
  Methodikabschnitt 3.6 mit fünf Literaturbelegen ergänzt; Zotero-Export unverändert.
- **Getestet:** zwölf zusätzliche Vertrags-/Provenienzprüfungen; drei synthetische
  Mock-Antworten um die nun verlangte Basis ergänzt. **728 lokale Tests in 81,63 s**,
  **48 API-Tests in 11,55 s**, Ruff und reguläres `git diff --check` bestanden.
  LaTeX/BibTeX Exitcode 0, **34 Seiten**, Methodikseiten visuell geprüft, keine
  LaTeX-Warnungen, fehlenden Zitate oder übervollen Boxen. Erneut genehmigter lokaler
  TinyTeX-Build außerhalb der Sandbox, keine Downloads/Toolchainänderungen.
- **Reale begrenzte Funktion nachgewiesen:** genau eine vorhandene synthetische,
  gedruckte PDF-Seite mit zwei Referenzpersonen, vier neuronale Pfade offline.
  Lauf `software/runs/20261111T075852Z-c0b6b30b`; Bericht
  `software/data/prompt-revision-20261111/reports/20261111T080047Z-a8f88de0/report.html`.
  Alle vier: gültiges JSON, zwei Personen, 7/7 bewertbare Felder exakt.
  Paddle-LLM und OCR-VLM weiterhin `partial` mit Prüfhinweisen, andere `success`.
  Vier tatsächliche Extraktionsnachrichten und vorhandene Namensschritte auf Hashes
  geprüft; aktuelle Promptfamilie stimmt mit Lauf überein, 30 geschützte Profile/
  historische Artefakte unverändert. Ein Fehler im nachgelagerten Zusammenfassungs-
  skript wurde allein aus gespeicherten Ergebnissen korrigiert, ohne neue Inferenz.
  Nachweis: `software/data/prompt-revision-20261111/functional.json`.
- **Offen / Grenze:** literaturbasiert konstruiert und technisch geprüft, nicht
  empirisch optimal oder nachweislich besser. Kein Vergleich mehrerer Promptkandidaten,
  keine unabhängige Pilot-/Finalstudie, keine Live-Validierung realer Handschrift/
  gemischter Dokumente. Vor der späteren Studie diese Familie samt Code/Profil
  einfrieren; finale Daten nicht zur weiteren Anpassung verwenden. Aktuell enthält
  der reguläre Eingabeordner zehn PDFs; für diesen Auftrag wurde ausschließlich
  die getrennte synthetische Ein-Seiten-Funktionsliste verarbeitet.

### Wissenschaftliche Berichtserweiterung (10.11., implementiert und verifiziert)

- **Implementiert und getestet:** `roster_benchmark/scientific*.py` ergänzt den
  vorhandenen Hauptbericht um manuelle Schrift-/Layout-/Qualitätsmerkmale,
  Feld-/Schulungsmetriken, Heatmap/Verteilung, fünf Matchingansichten, gepaarte
  Effekte, Cluster-Perzentilbootstrap aus gepoolten Zählern, die drei angefragten
  Pipelinegegenvergleiche und beobachtete Effizienz/Pareto. Fehlende Ergebnisse
  behalten Referenznenner, vollständig fehlende Gegenmessungen werden nicht als
  gemessene Verbesserung interpretiert. Kursreferenzen werden nicht auf PDFs/Seiten
  aufgeteilt. Bestehende Fehleranalyse erhält aggregierte Ursachen/Evidenzstufen,
  getrennte Seitenereignisse sowie Dokument-/Stufenfilter, keine zweite Analyseseite.
- **Aktiv konfiguriert:** reguläre neue Vergleiche enthalten die wissenschaftliche
  Ansicht automatisch; unbekannte Merkmale bleiben unbekannt. CLI
  `testframework/main.py metadata-template` und `analyze` ermöglichen manuelle
  Metadaten und Neuauswertung in einen neuen Ordner. Geprüfte Gruppen/Vorbenutzung,
  einheitliche bekannte Phase und standardmäßig mindestens zehn Gruppen sind
  Voraussetzungen für Intervalle (keine Poweranalyse). Das Fünferprofil und alle
  Extraktionsprofile bleiben unverändert; keine neuen Modelle integriert.
- **Anhand vorhandener Referenzen nachgewiesen:**
  `software/testframework/ergebnisse/scientific-20261110-v2/report.html`, ohne neue
  Inferenz. Quellen: Fünferbericht `20261110T124858Z-35a9b605`, Docling
  `20261110T123112Z-b454d615`, Assist `20261110T111751Z-9b5da18c`. Eine bekannte
  Entwicklungs-PDF, zwei Seiten, eine Gruppe, 18 Personen, 72 Referenzfelder.
  Vorhandene Schrift-/Layoutannotation ausschließlich über identische SHA256
  übernommen; Herkunft unter `software/data/scientific-20261110/` dokumentiert.
  Originalrollen: VLM→OCR-VLM neun korrigierte/fünf verschlechterte Felder
  (38→42 exakte Felder); Docling→Assist sieben/keine (28→35); OCR-LLM→Paddle-LLM
  13/zwei (29→40). OCR-VLM-Swapbewertung liefert auf denselben Paaren 43 statt 42
  exakte Felder. Dies ist ein Bewertungseffekt, keine Extraktionsverbesserung.
  Assist: ein gespeicherter zusätzlicher VLM-Aufruf und zwei neu gepaarte
  Referenzpersonen, kein unabhängiger Identitätsnachweis. Alle Gegenproben bleiben
  beschreibend (`causal_claim=false`); alle CIs `insufficient_groups`.
- **Verifiziert:** 23 neue Statistik-/Metadaten-/Integrationstests, bestehender
  Filtertest um Dokument/Stufe ergänzt. Gesamtsuite **716 bestanden in 72,78 s**;
  separate API-Suite **48 bestanden in 11,34 s**. Ruff und `git diff --check`
  bestanden. Reale Exportprüfung: 35 Bewertungsansichten, 140 Feldsummenzeilen,
  38 lokale Links; Zähler konsistent, alte Standardmetriken unverändert,
  **863 Originaldateien** aus drei Berichten und Quellläufen unverändert.
  Nachweise: `software/data/scientific-20261110/verification.json`.
  Methodik und Diagramme visuell geprüft, LaTeX/BibTeX erfolgreich, 32 Seiten,
  keine LaTeX-Warnungen/fehlenden Zitate oder übervollen Boxen. TinyTeX benötigte
  wieder den genehmigten lokalen Build außerhalb der Sandbox; keine Downloads.
- **Dokumentiert:** `software/docs/scientific-evaluation.md`, Software-/Framework-
  READMEs und Methodikabschnitte 3.7/3.8; offizielle Bootstrap-Dokumentation als
  geprüfter Primärbeleg ergänzt. Gemeinsame Snapshotprüfung in `references.py`;
  neue Vergleichsidentitäten sichern Referenzsnapshot und beide Konfigurationen
  zusätzlich durch Prüfsummen. Ältere Berichte können diese Zusatzhashes noch
  nicht enthalten. Auswahlpfad verwendet dieselbe Verifikation ohne verschachtelte
  automatische Analyse seiner eigenen Teilberichte.
- **Offen / nächster Schritt:** vollständiges, unabhängig geprüftes Inventar über
  alle Quellläufe und genügend unabhängige Pilot-/Testgruppen erstellen. Lokalisierte
  Seitentranskripte, Handschrift-CER/WER, kontrollierte Zeitmessungen, Energie-/Euro-
  und Nacharbeitskosten fehlen. Grobe Cache-Regime beweisen keine vergleichbaren
  Messbedingungen; CIs sind keine pauschalen Signifikanznachweise. Keine allgemeine
  Rangfolge oder endgültige wissenschaftliche Verfahrensauswahl behaupten.

### Aktuelle Nutzerwahl: fünf Verfahren einschließlich Tesseract+LLM (10.11.)

Die Rückfrage „und ocr llm auch noch“ ist ausdrücklich beantwortet:
**Tesseract+LLM zusätzlich aufnehmen, insgesamt fünf Verfahren.** Implementiert
und aktiv konfiguriert im neuen separaten Profil `software/configs/benchmark-five.yaml`
mit Starter `software/start_testframework_5.cmd`:
`ocr_rules`, `ocr_llm`, `paddle_llm`, `vlm`, `ocr_vlm`. Docling ist nicht ausgewählt.
Das Profil erbt `benchmark-four.yaml`; Vierer- und Sechsverfahren-Starter bleiben
erhalten. Beide Textpfade verwenden derzeit Qwen3-4B-Instruct-2507, Paddle
weiterhin PP-OCRv5/PP-StructureV3. PP-OCRv6 + Qwen3-8B und PaddleOCR-VL-1.6 sind
weiterhin nicht integriert und dürfen nicht als bereits aktiv bezeichnet werden.

Geprüft: Profil mit vorhandenem Lader geladen, genau fünf Methoden, kein Docling,
OpenCV-Signaturbackend und identische VLM-/Hybridparameter bestätigt. Neuer
Starter mit `--pruefen`: Exitcode 0, eine Eingabe-PDF und ein gemeinsamer Kurs,
keine Inferenz und kein Netzwerk. Inzwischen liegt der gespeicherte Nutzerbericht
`20261110T124858Z-35a9b605` mit allen fünf Verfahren auf einer Entwicklungs-PDF
vor; die wissenschaftliche Neuauswertung oben verwendet ihn ohne erneute Inferenz.
Die frühere synthetische Regelbaseline-Prüfung unten bleibt ein separater Funktionstest.
Software-README und Auswahldokumentation sind an die Nutzerentscheidung angepasst.

### Vorläufiger Vierverfahren-Start auf Nutzerwunsch (10.11.)

Implementiert, konfiguriert und ohne Inferenz geprüft: `software/configs/benchmark-four.yaml`
erbt `benchmark.yaml` und wählt nach der aktuellen Nutzerkorrektur genau
`ocr_rules`, `paddle_llm`, `vlm`, `ocr_vlm`. Docling wurde in diesem Laufprofil
durch Tesseract mit deterministischer Feldextraktion ersetzt. `main_comparison`
ist hier `false`, da das unveränderte alte Sechsverfahren-Protokoll `ocr_rules`
als Legacy-Verfahren sperrt. Der Validator und das alte Hauptprofil bleiben erhalten.
`software/start_testframework_4.cmd` nutzt den bestehenden Testframework-Starter
mit diesem Profil, einschließlich `--pruefen` und Arbeitsverzeichniswechsel.
Der bisherige Sechsverfahren-Standard bleibt unverändert. Es handelt sich um
einen ausdrücklich gewünschten vorläufigen Laufmodus, keine abgeschlossene
wissenschaftliche Auswahl. Profil geladen und Invarianten geprüft: Regelbaseline
ohne LLM/VLM, Signaturbackend OpenCV. Start mit `--pruefen`: Exitcode 0,
eine Eingabe-PDF und ein gemeinsamer Referenzkurs; keine Modellinferenz und kein
Netzwerkzugriff. Zusätzlich Tesseract-/Regelbaseline auf zwei vorhandenen
synthetischen Demo-PDFs mit regulärem Testframework vollständig ausgeführt:
Lauf `software/runs/20261110T123455Z-d8e15075`, Auswertung
`software/testframework/ergebnisse/20261110T123459Z-15843059/`; 2/2 Seiten technisch
erfolgreich, 3 Personen, 9/11 Felder exakt, Levenshtein-Feld-F1 90,00 %, Exitcode 0.
Dies ist ein Funktionstest, kein Qualitätsbeleg für reale Listen. Kein neuer
vollständiger Vierverfahren-Lauf. Die zusätzlich genannte Zielkombination
PP-OCRv6 + Qwen3-8B und PaddleOCR-VL-1.6 ist weiterhin nicht integriert.

### Wissenschaftliche Verfahrensauswahl (10.11., implementiert und verifiziert)

- **Implementiert und getestet:** `selection_config.py`, `selection_sample.py`,
  `selection.py`, `selection_report.py`, CLI `participant-bench selection
  {inventory,freeze,run,compare}` und `software/configs/selection.yaml`.
  Evidenzmatrix mit harten Ja/Nein/Offen-Bedingungen, konfigurierbaren Gewichten,
  Quellenpflicht für numerische Bewertungen und keinem Gesamtscore bei Lücken.
  Geprüfte Vorbenutzung/Abhängigkeitsgruppen, SHA256-IDs, Seed 42, feste Stichprobe
  (Ziel 40 Listen), gruppierter vorhandener Splitter und gesperrte finale Testdaten.
  Plan versiegelt Metadaten, Profile, Grundprompts, Code, Locks und relevante Pakete.
- **Aktiv konfiguriert:** ausschließlich neuer, expliziter Auswahlpfad. Die sechs
  Hauptverfahren in `benchmark.yaml` sowie `local.yaml`, Assist-Profil und
  API-Konfigurationen bleiben unverändert. Keine reduzierte Hauptkonfiguration.
  Optionale neue Inferenz verwendet bestehende lokale Profile ohne Referenz.
- **Bestehende Evaluation erweitert, keine zweite Feldpipeline:** optionaler
  Dokumentfilter in `roster_benchmark/evaluation.py` und optionales
  `score_original_roles=True` in `course_metrics`. Primär Original-Namensrollen
  auf unveränderten referenzgestützten Paaren; zusätzlich neue Paarung ohne Swap
  und referenzgestützter Swap-Vergleich. Defaults bestehender Auswertungen bleiben
  erhalten. Fehlende/gescheiterte/nicht verfügbare Ergebnisse bleiben sichtbar;
  keine günstige Schnittmenge mit kleinerem Nenner. `ocr_raw` nur diagnostisch.
- **Anhand vorhandener Referenzartefakte nachgewiesen:** lokale Gegenprobe
  `software/runs/selection-dev-20261110-v3/comparison/report.html`, ohne neue
  OCR-/Modellaufrufe. Quellen `20261110T110642Z-d0abb263` und Assist
  `20261110T111751Z-9b5da18c`. Eine vorbenutzte Entwicklungs-PDF, zwei Seiten,
  eine Gruppe, 18 Referenzpersonen, 72 Referenzfelder; null unabhängige Pilotlisten.
  Gleiche tatsächliche Laufbilder, Profile und Grundprompts geprüft; alle
  CSV-/JSON-Zähler der 18 Kandidaten-/Bewertungsansichten konsistent.
  Vorläufige Rollenbesetzung: `docling`, `paddle_llm`, `vlm`; optional `ocr_vlm`.
  Keine allgemeine Qualitäts-/Geschwindigkeits- oder finale Auswahlbehauptung.
- **Dokumentiert:** `software/docs/method-selection.md` und
  `method-selection-status.md`, relevante READMEs, Methodikabschnitt in
  `bachelorarbeit/chapters/03_methodik.tex`, fünf verifizierte Primärbelege in
  `verified_sources.bib`. Zotero-Export und übergeordnete Forschungsfrage unverändert.
- **Prüfstand:** 18 neue gezielte Tests; 693 lokale Volltests in 55,72 s,
  48 API-Tests in 7,78 s, Ruff bestanden. LaTeX/BibTeX erfolgreich (29 Seiten),
  Methodikseiten visuell geprüft; keine fehlenden Zitate oder übervollen Boxen.
  Wegen Windows-Pfadauflösung benötigte TinyTeX den genehmigten lokalen Build
  außerhalb der Sandbox. Keine Downloads oder Toolchainänderungen.
- **Offen / nächster Schritt:** unabhängiges Inventar mit geprüften Gruppen und
  Vorbenutzung sowie 30–50 Pilotlisten erstellen; Stufe-A-Nachweise für
  Speichergrenzen und konkrete zulässige Nutzung sowie Ressourcen-/Aufwandsdaten
  ergänzen. Korpusreferenz ist ohne Prüfung keine Seiten-/Handschrift-Ground-Truth.
  Das bestehende Assist-Serializerformat enthält derzeit Rollen/Überschriften und
  verankerte Zeilen, keine vollständige TableFormer-Zellgeometrie; ältere Aussagen
  dazu weiter unten sind überholt.

### Optionale Docling-VLM-Hybridstufe (`docling-vlm`, `vlm_assist`) ohne Veränderung der `docling`-Baseline (10.11.)

Implementiert, getestet, als separates Ablationsprofil (`software/configs/docling-vlm.yaml`)
konfiguriert und anhand der gecachten Referenzartefakte nachgewiesen:
1. **Strikte Kapselung der `docling`-Baseline (`config.py`, `structure.py`, `software/configs/docling-vlm.yaml`):**
   - `StructureConfig` in `config.py` besitzt den expliziten Opt-in-Schalter
     `vlm_assist: bool = False` (Standardwert `False`).
   - Im Hauptvergleich (`main_comparison: true`, `software/configs/benchmark.yaml` sowie
     `software/configs/docling.yaml`) bleibt `vlm_assist` auf `False`; ein Einschalten
     von `vlm_assist: true` bei `main_comparison: true` wird durch den Validator in
     `Config.unique_methods` mit einem `ValueError` abgelehnt.
   - `recognition_key` in `structure.py` schließt `vlm_assist` aus dem
     Erkennungs-Cache-Schlüssel aus, sodass `docling` und `docling-vlm` denselben
     warmen TableFormer-Erkennungs-Cache nutzen.
   - Separates Konfigurationsprofil `software/configs/docling-vlm.yaml`
     (`extends: benchmark.yaml`, `main_comparison: false`, `methods: [docling]`,
     `structures.docling.vlm_assist: true`) angelegt.
2. **Ressourcenschonende, selektive Docling+VLM-Hybridstufe (`hybrid.py`, `runner.py`):**
   - Sequenzielle GPU-Ausführung für 16 GiB VRAM: `runner.py` entlädt zunächst den
     `docling`-Subprozess (`model.close()`) vollständig, bevor bei aktivem `vlm_assist`
     das vorhandene lokale VLM (`Qwen/Qwen3-VL-4B-Instruct`, `models.vlm`) geladen wird.
   - `needs_docling_vlm_assist` prüft pro Seite, ob unvollständige/unsichere Namensfelder,
     OCR-Artefakte (`_`, `|`, `…`), Stufe-2-Geometrie-Fallbacks oder nicht zugeordnete
     Tabellenzeilen vorliegen. Vollständig und sicher gelesene Maschinenschrift-Seiten
     (`state == "read"`, `reasons = ["all_docling_rows_complete_and_read"]`) werden ohne
     VLM-Aufruf übersprungen (`status = "skipped_complete_docling"`).
   - `serialize_docling_hints` übergibt die TableFormer-Zellgeometrie, Spaltenzuordnung
     und vorläufigen Docling-Zeilen im Format `docling-vlm-assist-v1` an das VLM und
     nutzt `vlm_cells.py` (`parse_visual_response`) sowie `DocumentNameOrders` und
     `filter_page_people`.
   - `merge_docling_vlm_participants` bewahrt verankerte, hochkonfidente gedruckte
     Docling-Felder (`provenance = "docling"`), ergänzt/korrigiert unsichere, fehlende
     oder handschriftliche Felder (`provenance = "docling_vlm_assist"`,
     `assignment_rule = "docling_vlm_hybrid_cell"`) und fügt vom TableFormer übersehene
     handschriftliche Zeilen (`assignment_rule = "docling_vlm_hybrid_row"`) hinzu.
3. **Provenance-Kennzeichnung in Rohdaten und Berichten (`structured_mapping.py`, `table_mapping.py`, `report.py`, `roster_benchmark/error_report.py`):**
   - Jedes Feld in `row_evidence` trägt `provenance = "docling"` bzw.
     `provenance = "docling_vlm_assist"` (inkl. `original_docling_value` und
     `original_docling_state`).
   - `error_report.py` gibt `provenance` und `original_docling_value` in
     `diagnose_field`, `error_analysis/fields.json` und auf den HTML-Fehlerkarten aus;
     `runner.py` und `report.py` weisen Laufzeiten (`vlm_assist_seconds`), Aufrufzahlen
     und Modellnutzung separat aus.
4. **Nachweis:**
   - **Live-End-to-End-Lauf über das Testframework (`software/runs/20261110T111644Z-aa89a376` -> Auswertung `software/testframework/ergebnisse/20261110T111751Z-9b5da18c/`):**
     Auf `140829.pdf` überspringt `docling-vlm` Seite 1 (Maschinenschrift) in `0,1 s` aus dem warmen TableFormer-Cache mit `0` VLM-Aufrufen (`36` Felder mit `provenance="docling"`) und ruft `Qwen3-VL-4B-Instruct` nur für Seite 2 (Handschrift-Folgeseite, `1` VLM-Aufruf in `34,7 s`, `27` Felder mit `provenance="docling_vlm_assist"`) auf. Gegenüber der reinen `docling`-Baseline (`software/testframework/ergebnisse/20261110T101647Z-c41da01d/`) steigt der Levenshtein-Feld-F1 live von `65,19 %` auf **`77,77 %` (`+12,58 Prozentpunkte`)**, die exakten Felder steigen von `28/72 (38,89 %)` auf **`35/72 (48,61 %)`** (strikt ohne Swap-Toleranz von `22/72` auf **`28/72`**), die zugeordneten Teilnehmer steigen von `16/18` auf **`18/18` (`0` fehlend, `0` überzählig)** und die Vor-/Nachnamen-Dreher sinken von `6` auf **`1`** bei einer Gesamtlaufzeit von **`62,3 s`** (gegenüber `88,1 s` bei `vlm` und `110,7 s` bei `ocr_vlm`).
   - Auf den gecachten Artefakten zu Dokument `140829` (`20261110T085608Z-d06794be` +
     VLM-Ausgabe aus `20261110T100955Z-3cb60325`) steigen die exakten Felder von
     `28/72 (38,89 %)` auf `41/72 (56,94 %)` und der Gesamtscore (Best-Fit-F1) von
     `65,19 %` auf `82,76 %`.
   - Alle 675 lokalen Unit- und Regressionstests (`pytest software/tests`, inkl. 2 neuer
     Tests in `test_unified_pipelines.py`) sowie `ruff check` bestanden.

### Zeilenindividuelle Vorname-/Nachname-Erkennung bei fehlenden Überschriften und wechselnder Reihenfolge (10.11.)

Implementiert, getestet, aktiv konfiguriert und anhand gecachter sowie synthetischer
Referenzdaten nachgewiesen:
1. **Zeilenindividuelle Priorität vor Spalten-Default (`name_parts.py`, `document_names.py`, `structured_mapping.py`, `table_mapping.py`):**
   - `name_parts.py` klassifiziert Namensteile deterministisch (ohne LLM und ohne
     Nutzung der Ground Truth) über explizite Kommatrennung
     (`explicit_surname_comma_given_name`), Adels-/Namenspräfixe (`von`, `van`, `de`,
     `del`, `da`, `von der`, `van der` usw.), deutsche/internationale Vornamen- und
     Nachnamenindikatoren sowie morphologische Nachnamensuffixe (`classify_name_pair`,
     `lexical_given_family`, `lexical_family_given`).
   - Eindeutige Zeilenbelege (`"Max Mustermann"`, `"Schmidt, Anna"`, `"Weber Lukas"`,
     `"Julia Fischer"`) haben sowohl in `split_combined_name`, `structured_mapping.py`
     und `table_mapping.py` als auch in `DocumentNameOrders.prepare_assignment` und
     `DocumentNameOrders.apply` (`document_names.py`) strikten Vorrang vor der globalen
     Spalten-/Dokumentorientierung.
   - Die spaltenweite Mehrheitsorientierung (`infer_column_tiebreaker`,
     `_assignment_tiebreaker`, `_page_tiebreaker`) greift ausschließlich als
     Tie-Breaker bei echten mehrdeutigen Zeilen (z. B. zwei Vornamen als Gesamtname wie
     `"Thomas Martin"` oder zwei unbekannte Tokens) und überschreibt niemals eine
     bereits eindeutig klassifizierte Nachbarzeile.
   - Kopflose Tabellen (`partial_identity_fallback` und `_two_column_headerless_fallback`
     in `structured_mapping.py`) unterstützen nun sowohl kombinierte Namensspalten als
     auch zwei benachbarte unbenannte Namensspalten mit zeilenweise wechselnder
     Reihenfolge (ab mindestens zwei belegten Personen-Zeilen).
2. **Optimierung der bestehenden LLM-/VLM-Verfahren (`document_names.py`, `models.py`, `unlimited_assignment.py`):**
   - Die Systeminstruktionen für `ocr_llm`, `paddle_llm`, `vlm` und `ocr_vlm` weisen
     das Modell explizit an, bei fehlenden Spaltenüberschriften oder zeilenweise
     wechselnder Eintragungsreihenfolge (`"Vorname Nachname"`, `"Nachname Vorname"`,
     `"Nachname, Vorname"`) jede Zeile individuell semantisch zu prüfen und die
     dokumentweite `name_order` als Tie-Breaker für mehrdeutige Zeilen zu verwenden.
   - `DocumentNameOrders.prepare_assignment` und `DocumentNameOrders.apply` überschreiben
     eine zeilenindividuell stimmige LLM-/VLM-Zuordnung nicht mehr durch einen starren
     spaltenweiten Swap; `docling` und `ocr_raw` bleiben unverändert ohne LLM.
3. **Transparente Swap-Diagnose (`roster_benchmark/error_report.py`):**
   - `diagnose_field` weist verbleibende Vor-/Nachname-Vertauschungen ohne aktive
     Swap-Toleranz explizit als eigene Fehlerkategorie `name_swap`
     (`"Vor-/Nachname-Vertauschung (Swap)"`, `certainty="proven"`,
     `stage="name_role_assignment"`) aus und kennzeichnet durch Swap-Toleranz
     aufgefangene Treffer transparent mit `name_swapped=True`.
4. **Nachweis:**
   - Auf dem gecachten Referenzlauf zu Dokument `140829` (`software/runs/20261103T084429Z-e2834b34/docling`)
     sinkt `name_swapped_participants` für `docling` von `6` auf `0`; die Anzahl
     exakter Felder **ohne** Evaluations-Swap-Toleranz (`compare_name_orientations=False`)
     steigt auf diesem Dokument von `7` auf `15` (und im Gesamtlauf über 72
     Referenzfelder von `20/72 (27,78 %)` auf `28/72 (38,89 %)`, identisch zum Wert mit
     aktiver Swap-Toleranz).
   - Alle 673 lokalen Unit- und Regressionstests (`pytest software/tests`, inkl. 3 neuer
     Tests in `test_document_names.py` und `test_extraction_errors.py`) sowie
     `ruff check` bestanden.

### Ausbalancierte Pipeline für gemischte Dokumente in `ocr_llm` und `docling` (10.11.)

Konfiguriert, implementiert, getestet und anhand des gemischten Referenzdokuments
(`140829.pdf`, Seite 1: 8 maschinenschriftliche + 1 handschriftlicher Eintrag,
Seite 2: 9 handschriftliche Einträge ohne eigene Spaltenkopfzeile) nachgewiesen:
1. **Zerstörungsfreie Vorverarbeitung (`image_preprocessing.py`, `ocr.py`, `docling_backend.py`):**
   Lokale Hintergrundnormalisierung (`MORPH_CLOSE` mit `25×25`-Kernel und
   Graustufen-Division `cv2.divide`) vor der Otsu-Schwelle in `remove_grid_lines`
   ersetzt die bisherige globale Binarisierung. Dadurch bleiben grau hinterlegte
   Tabellenkopfzeilen (Median-Grauwert ~169 auf Seite 1) vollständig erhalten,
   während ausschließlich echte Tabellenlinien (`40×1` / `1×40`) auf dem
   hintergrundnormalisierten Graustufenbild geweißt werden. Zudem OCR-Ligaturvarianten
   (`benutzemame`, `teilnehmemame` in `unlimited_assignment.py` sowie `signetur`
   in `column_headers.py`) ergänzt, idempotentes Wrapping in `docling_backend.py`
   abgesichert und `image_preprocessing.py` in die `OCR`-Cache-Identität (`ocr.py`)
   aufgenommen.
2. **Zweistufiges Beobachtungs- und Evidenz-Modell (`ocr_layout.py`, `ocr_evidence.py`, `models.py`, `unlimited_assignment.py`):**
   In `ocr_layout.py` werden unterhalb erkannter Tabellenkopfzeilen auch
   niedrigkonfidente/handschriftliche Zeilen in den Textspalten (`selection_hint="unclassified_observation"`)
   mit zell- und zeilenweiser `ocr_confidence` an `ocr_llm` übergeben, während
   Vor-Tabellen-Metadatenzeilen ausgeschlossen werden. `ALL_ROW_INSTRUCTIONS` in
   `models.py` wird nun auch im Standardmodus `pattern` aktiviert, sobald
   unklassifizierte oder geerbte Zeilen im Prompt enthalten sind. Randartefakte
   (`_`, `|`) an Tokens in `models.py`, `unlimited_assignment.py` und
   `ocr_evidence.py` blockieren den Literalbeleg nicht mehr; niedrigkonfidente
   (`< 30`) oder partielle Belege werden konsistent als `state="uncertain"` markiert.
3. **Selektives Geometrie-Fallback mit festem Spaltenkontext (`column_context.py`, `structured_mapping.py`):**
   `column_context.py` speichert die normierten Spalten-X-Intervalle (`column_intervals`)
   und `text_width` der ersten Teilnehmerseite und erlaubt auf Folgeseiten neben
   exakter Spaltenanzahl auch kompatible Textspalten-Präfixe
   (`same_text_column_prefix_geometry`, wenn auf Folgeseiten nur nachgelagerte
   Signaturspalten entfallen). `structured_mapping.py` führt für `docling`
   (weiterhin strikt ohne LLM) ein zweistufiges Mapping aus: Stufe 1 übernimmt
   reguläre TableFormer-Zellen unverändert; Stufe 2 ergänzt ausschließlich
   leere/nicht zugeordnete Felder sowie verwaiste OCR-Rohbeobachtungen (`ocr_cells`)
   unterhalb der Tabelle über Y-Überlappung und feste Spalten-X-Intervalle als
   `state="uncertain"`.
4. **Nachweis (Validierungslauf `software/runs/20261110T083413Z-10042efe/`, Auswertung `software/runs/validation_balanced_pipeline/20261110T083532Z-dbdf20c4/` ggü. Baseline `20261106T080030Z-f1e4fa77/`):**
   - `ocr_llm`: zugeordnete Teilnehmer `9 → 17` (Seite 1: `9`, Seite 2: `0 → 8`),
     exakte Felder `25/72 (34,72 %) → 29/72 (40,28 %)` (`user_id` `7 → 8`,
     `short_code` `0 → 3`), fehlende Felder `47 → 24`, zusätzliche Felder `0`,
     Levenshtein-Feld-F1 (Best-Fit) `53,15 % → 64,85 %` (konservativ `53,15 % → 56,48 %`).
   - `docling`: zugeordnete Teilnehmer `8 → 16` (Seite 1: `9` über explizite
     Kopfzeile statt Fallback, Seite 2: `0 → 7` über Spaltenvererbung + Stufe-2-Fallback),
     exakte Felder `22/72 (30,56 %) → 28/72 (38,89 %)` (`first_name` `8 → 10`,
     `last_name` `8 → 9`, `short_code` `0 → 3`), fehlende Felder `48 → 17`,
     zusätzliche Felder `0`, Levenshtein-Feld-F1 (Best-Fit) `45,83 % → 65,19 %`
     (konservativ `45,83 % → 55,43 %`).
   - Alle 670 lokalen Unit- und Regressionstests (`pytest software/tests`, inkl.
     neuer synthetischer Tests für graue Kopfzeilen und gemischte Seiten +
     Folgeseite) sowie `ruff check` bestanden.

### Umgebungsprüfung und Verifikation des lokalen Testframeworks (09.11.)

Lokale Umgebung verifiziert: Python 3.12.15, `uv 0.13.1`, CUDA aktiv (NVIDIA
GeForce RTX 4090 Laptop GPU), `uv sync --locked --extra models --offline` ohne
Fehlbestand (71 Pakete aufgelöst, 55 geprüft). Isoliertes Verzeichnis
`software/api_firmen_pc/` unberührt gelassen. Minimal-invasiv behoben:
Berechtigungsfehler (`PermissionError`) auf fremden System-Temp-Ordnern
(`pytest-of-Marco`) und altem `.pytest_cache` sowie relative Pfadauflösung beim
Aufruf von `pytest software/tests` aus dem Repository-Root durch
`cache_dir = ".cache/pytest_cache"` in `software/pyproject.toml` und neues
`software/tests/conftest.py` (setzt Arbeitsverzeichnis `software/` und lokales
`basetemp` unter `.cache/pytest_tmp`). Zusätzlich `PYTHONUTF8=1` und
`PYTHONIOENCODING=utf-8` in `software/start_testframework.cmd` ergänzt.
Alle 668 lokalen Unit-/Regressionstests (`pytest software/tests`, 59,65 s) und
`ruff check` bestanden. Testframework-Vorabprüfung (`--pruefen`), synthetischer
Vergleichslauf (`20261109T120211Z-d892972b`, Levenshtein-Feld-F1 82,69 %),
synthetischer End-to-End-Lauf mit `ocr_raw` und `docling`
(`20261109T120326Z-beeb4b0a`, Docling 100,00 % / 11 von 11 Referenzfeldern exakt)
sowie Standardlauf mit `ocr_raw` (`20261109T120951Z-0d00bc7a`) fehlerfrei mit
Exit-Code 0 und vollständigen HTML-/JSON-/CSV-/XLSX-Artefakten abgeschlossen.

### Extraktionsqualität und separate Fehleranalyse (06.11.)

Ausgangsbericht `software/testframework/ergebnisse/20261106T081128Z-0011a735/`,
Quelllauf `software/runs/20261106T080030Z-f1e4fa77/`. Bestätigt: OCR-LLM auf
Seite 2 übergibt alle 51 Wörter, Modell liefert null Personen; Docling hält
66 Beobachtungen, aber keine verlässliche Spaltenzuordnung und null Personen.
Paddle erkennt Organisationszellen, das LLM lässt deren Zielfeld leer.
Implementiert: konservative Ergänzung fehlender skalarer Felder vorhandener
Personen ausschließlich aus einer einzelnen aktuellen OCR-Zelle innerhalb
gemessener, durch Überschriften belegter Spaltengrenzen; kompatible Übernahme
innerhalb derselben PDF. Unsicherheitsmarkierung statt Confidence-Löschung.
Neue Funktion `complete_observed_cells` in `structure_assignment.py`, Integration
in `unlimited_assignment.py`; sieben ergänzte Zellen auf der zweiten Paddle-Seite.
Kontrollierter Replay und zwei neue lokale LLM-Antworten bestätigen: Paddle
38 → 40 korrekt, 15 → 20 falsch, 19 → 12 fehlend; 18 Personen unverändert.
Alle bisherigen Treffer und Referenzpaarungen bleiben erhalten. Recall steigt
52,78 → 55,56 %, exakter F1 fällt 60,80 → 60,61 %; fünf zusätzliche falsche
Werte sind ein relevanter Zielkonflikt, keine uneingeschränkte Verbesserung.
OCR-LLM bleibt 23/72 exakt, Docling 19/72; dort keine neue Qualität behauptet.
Aktiver Schritt nur im räumlichen Zuordnungspfad; keine unsicheren Docling-
Spaltenrollen ergänzt, keine Modellgewichte oder Referenzen geändert.
Neue `roster_benchmark/error_report.py` wird über `detail_report.py` erzeugt,
mit statischer verlinkter HTML-Seite, sechs Filtern, OCR-Belegen, lokalen Crops
und expliziter Beleglage. Kursreferenzen ohne Paarung bekommen keine erfundene
Seitenzuordnung. Ausgabe folgt der PDF-/Seiten-/Modellreihenfolge.
Lokaler Vergleich: `software/runs/extraction-quality-20261106-final/report.html`,
Analyseseite in `after/extraction_errors.html`, Herkunft/Zähler in `qa.json` und
`comparison.json`. Neuer realer Paddle-Zuordnungslauf:
`software/runs/extraction-quality-20261106-live/`, Auswertung daneben in
`software/runs/extraction-quality-20261106-live-comparison/` (88,29 s nur Zuordnung,
zwei Generierungen, keine erneute OCR; keine neue End-to-End-Zeit behauptet).
668 lokale Volltests (48,80 s), 48 API-Tests (8,07 s) und 41 gezielte Tests
(1,41 s) bestanden; Ruff ohne Befund. Filter mit lokalem
Node ausgeführt; grafische Sichtprüfung wegen fehlendem Computer-Use-Laufzeitpfad
nicht möglich. Zahlen von HTML-Feldfällen, CSV und JSON-Metriken stimmen überein.
Dokumentation: `software/docs/extraction-error-analysis.md`.
Offen bleiben OCR-Handschriftqualität, belastbare native Folgetabellen und
unabhängige Referenzlokalisierung; keine erfundenen OCR-Ursachen bei fehlenden Belegen.

### Vollständige OCR-Beobachtungen und Verlustdiagnose (03.11.)

Neuer Auftrag aus Anhang `b06f9e5e-397e-49b1-a021-d44ca755020f`.
Ausgangspunkt `software/testframework/ergebnisse/20261103T103940Z-910665bc/`,
Quelllauf `software/runs/20261103T101357Z-d77317f7/`.
Nachgewiesen: Tesseract Seite 2 hat 51 Wörter/10 Zeilen; alle zehn sind im
tatsächlichen LLM-Eingang, Modellantwort enthält eine Person, keine spätere
Zeilenverwerfung oder Trainerausschlüsse. Docling hat 66 Zellen auf Seite 2,
native Tabelle 6×3, keine zuverlässigen Überschriften, keine Teilpersonen.
Keine Confidence-Löschung in den geprüften Tesseract-/Docling-CLI-Pfaden.

Implementiert und aktiv: zusätzliche Docling-Erfassung vor
SDK-Zusammenführung (Überlappung mit PDF-Text kann OCR-Zellen sonst verdrängen),
unabhängiges Beobachtungsregister mit Originaltext/Score/Geometrie/Quellbeleg,
Ausgabe nicht zugeordneter Texte und Zuordnungsgründe im Hauptbericht/JSON/CSV.
Fehlende/ungültige Confidence verwirft kein Wort. Hauptprompt v24, OCR-Cache v3,
nativer Mapper v7 mit Zeilenentscheidungen. Das kompakte Zeilenprotokoll umging zuvor
die vorhandene Unsicherheitsmarkierung unter Score 30; auch dort bleiben Werte
jetzt erhalten und werden bei niedrigem Score als unsicher markiert.

Realer Versuch `software/runs/20261103T135955Z-83a79dcb/`: neue OCR-/Docling-
Auslesung derselben zwei Bilder und zwei lokale Text-LLM-Antworten plus eine
Namensentscheidung. Vollständige Zeilenvariante 17 statt 10 Personen, aber nur
24 statt 25 exakte Felder, 19 statt 12 falsche; nicht als Standard übernommen.
`models.ocr_llm.ocr_row_selection` ist deshalb standardmäßig `pattern`, `all`
bleibt eine explizite Versuchsvariante. Rohbeobachtung und Diagnose sind immer aktiv.
Die regulären Eingabe-/Systemtexte sind auf beiden Seiten gegenüber `f90b397`
identisch; Gleichheitsprüfung separat gespeichert. Eine Benutzer-ID allein genügt
bei verlässlich zugeordneter ID-Spalte; ohne diesen Beleg bleibt die Namensprüfung.
Vollständig verworfene Modellzeilen werden mit Evidenzgrund ausgewiesen.
Separater negativer Vergleich der Versuchsvariante:
`software/runs/observation-retention-20261103-all-rows/comparison/report.html`.
Regulärer, konservativer Vergleich mit eingefrorenen bisherigen LLM-Antworten
und neuer Confidence-/Belegprüfung:
`software/runs/observation-retention-20261103-checked/comparison/report.html`.
Standard behält OCR-LLM 25/72 und Docling 19/72 exakt, keine verlorenen Treffer,
keine neuen nachgewiesenen korrekten Felder. Die vollständige Beobachtungsansicht
steht daneben in `source/report.html`. Historische Rohantworten/Referenzen unverändert;
JSON-/CSV-/Excel-Zähler und HTML-Beiträge gegengeprüft, `qa.json` gespeichert.
Docling vor/nach SDK-Zusammenführung 153/153 bzw. 66/66 Zellen; kein tatsächlicher
SDK-Verlust auf dieser bildbasierten PDF. Überlappungsverlust bei PDF-Text ist
als genereller SDK-Pfad nachgewiesen und synthetisch abgesichert.
652 lokale Volltests in 49,23 s, 48 API-Tests in 7,64 s und zuletzt
107 gezielte Tests in 2,57 s bestanden; Ruff ohne Befund.
Abschlussbericht: [software/docs/ocr-observation-retention.md](software/docs/ocr-observation-retention.md).
Weiterhin offen ist die eigentliche Handschriftqualität bzw. sichere Zuordnung
bei fehlenden Überschriften; keine zusätzlichen Modelle, Downloads oder Trainings.

### Dokumentbezogene Überschriften auf Fortsetzungsseiten (03.11.)

Zusatzauftrag aus Anhang `570ba3b0-a3be-432d-a8df-227d0fdda13d`.
Implementiert ist eine gemeinsame Kompatibilitätsprüfung für die bestehenden
Docling- und räumlichen LLM-Mappingkontexte sowie Tesseract-Zeilenanreicherung.
Zustand enthält ausschließlich Überschriften, Feldrollen, Dokument-ID, Quellseite
und normalisierte Geometrie. Übernahme verlangt dieselbe PDF, eine frühere Seite,
gleiche Spaltenzahl und vergleichbare gemessene Geometrie; bloße Seitenformatgleichheit
oder Modellwerte früherer Personen reichen nicht. Neue Überschriften haben Vorrang.
Neue aktuelle Überschriften ersetzen alte Rollen; mehrdeutige Überschriften
blockieren veralteten Kontext. Leere Seiten erhalten den Zustand. Fortsetzungs-
Herkunft steht im Hauptbericht/CSV und in den nativen bzw. LLM-Zuweisungsbeweisen.
Im Hauptprofil über die bestehenden nativen/räumlichen Pfade aktiv; keine neue
Modell- oder OCR-Konfiguration. Frühere Nachbearbeitungszustände werden bei
Neuzuordnung archiviert, nicht auf neue Personenwerte angewendet.

627 lokale Volltests in 166,99 s, 48 API-Tests in 18,99 s und abschließend
61 gezielte Tests in 13,45 s bestanden; Ruff und Berichtszähler geprüft.
Realer Paddle-Lauf mit zwei neuen lokalen LLM-Aufrufen bei identischer nativer
OCR: gegenüber dem reparierten Ausgangsstand 38/72 exakt unverändert,
15 → 19 falsche und 19 → 15 fehlende Felder. Keine zusätzlichen Teilnehmer,
alle früheren Treffer und maschinenschriftlichen Werte erhalten. Vier weitere
Organisationswerte sind falsch; kein realer Qualitätsgewinn behauptet.
Dieselbe neue Antwort ohne geerbte Positionsprüfung liefert 28 statt 19 falsche
Felder. Die Strukturprüfung verhindert damit netto neun falsche Zuordnungen
gegenüber dieser Ablation, ohne mehr exakte Treffer zu liefern. Tesseract/Docling
haben hier keine eindeutigen Überschriften; dort keine neue Übernahme/Treffer.

Abschlussbericht: [software/docs/document-columns.md](software/docs/document-columns.md).
Lokale Schlussauswertung `software/runs/document-columns-20261103-final/comparison/report.html`,
Ablation `software/runs/document-columns-20261103-ablation/comparison/report.html`,
Prüfprovenienz `software/runs/document-columns-20261103-check/check.json`,
Modelllauf `software/runs/document-columns-20261103-paddle/` (719,40 s;
GPU parallel belegt, kein belastbarer Laufzeitgewinn). Keine neuen OCR-Aufrufe.
Unabhängige Handschrifttranskripte und weitere reale Entwicklungsdokumente bleiben
für allgemeine Qualitätsaussagen erforderlich; keine Referenz in der Extraktion.
Neue Versionen: Dokumentkontext v1, native Zuordnung v6, räumliche Zuordnung v8,
LLM-Protokoll v19/v20, Hauptprompt v23. VLM/Hybrid inhaltlich unverändert.

### Handschriftauftrag vom 03.11.: Datenerhalt und kontrollierte OCR-Proben abgeschlossen

Ausgangspunkt `software/testframework/ergebnisse/20261103T092511Z-5be3affb/`,
Quelllauf `software/runs/20261103T091220Z-9a1bd0fb/`. Nutzer bestätigt, dass die
Excel-Kursreferenz auch die handschriftlichen Texte enthält, aber keine
Lokalisierungen. Dokumentweiter Feldvergleich ist möglich; separate OCR-CER/WER
der Handschrift bleiben ohne geprüfte regionale/seitige Zuordnung ungemessen.

Nachgewiesener Verlust: Paddle gibt auf Seite 2 neun Personen in der gespeicherten
LLM-Antwort aus; ein fehlendes Einzelzielfeld ließ bislang alle neun an der
Schema-Prüfung scheitern. Optionale fehlende Felder bleiben jetzt unbekannt;
Literal-, Positions-, Rollen- und Typprüfungen bleiben aktiv. Protokoll v17/v18.
Native Konfidenzen und Textbelege bleiben in Feldbeweisen, niedrige Scores und
sichtbare Teiltextmarker markieren `uncertain`, ohne Werte zu löschen.

Reiner Validierungs-Replay ohne neue OCR/LLM-Aufrufe:
`software/runs/handwriting-retention-20261103-final/comparison/report.html`.
Paddle 9 → 18 Personen, 29 → 38 exakte Felder, 7 → 15 falsche und 36 → 19
fehlende Felder bei identischem Referenznenner 72. Alle 29 bisherigen Treffer
erhalten; maschinenschriftliche Werte der ersten Seite unverändert. Das ist
Datenerhalt, keine verbesserte OCR-Erkennung. Zusätzliche Unsicherheit sichtbar.

OCR-Voruntersuchung `software/runs/handwriting-probe-20261103/`: sieben
Tesseract-Varianten, 24 native Zellausschnitte und kleine Paddle-/Docling-Proben,
insgesamt 44 zusätzliche Erkennungsaufrufe; keine neuen Gewichte oder Trainings.
Zusätzliche Paddle-3200-Probe mit zwei weiteren Aufrufen separat unter
`software/runs/handwriting-paddle-3200-20261103/`; keine Verbesserung belegt.
Ohne lokalisierte Transkripte keine OCR-Siegerwahl. Docling ohne Linienentfernung
mit/ohne FULL_PAGE verliert hier die bisherige Teilzuordnung; nicht übernehmen.
Keine globale Vorverarbeitungsänderung. **72 gezielte, 609 lokale Volltests in
81,90 s und 48 API-Tests in 17,60 s bestanden**, Ruff ohne Befund.
Abschlussbericht: [software/docs/handwriting-optimization.md](software/docs/handwriting-optimization.md).
Replays behalten identische OCR-/LLM-Antworten und maschinenschriftliche Werte;
Validierungsstufen, JSON-/CSV-/Excel-Zähler und HTML-Beiträge konsistent.
Zusätzlich ausgegebene Werte enthalten 13 nichtleere unsichere Felder. Höherer
Recall bei geringerer Precision offen ausgewiesen. Kein neuer LLM/VLM/HTR-Lauf,
kein verstecktes Verfahren und kein Qualitätsversprechen für echte Handschrift.

### Gesamtauftrag vom 03.11.: Docling, Metrikprüfung und vereinheitlichte Berichte

Aktueller Ausgangsvergleich: `software/testframework/ergebnisse/20261103T081036Z-c0340c5a/`,
Quelllauf `software/runs/20261103T075704Z-ae365514/`. Beide Docling-Seiten haben
OCR und native Tabellen, aber keine erkannten verwertbaren Spaltenüberschriften;
der bisherige deterministische Mapper gibt deshalb null Personen aus.
Ein begrenzter nativer Fallback erhält wiederholte Namens-/Nummernzellen als
unsichere Teilpersonen. Keine Organisations-/Signaturspalten geraten; keine Referenz
in der Extraktion. Praktischer regulärer Lauf `software/runs/20261103T084429Z-e2834b34/`:
9 unsichere Teilpersonen auf Seite 1, weiterhin 0 auf Seite 2; 19/72 exakt,
6 falsche, 47 fehlende Felder im Kursvergleich. Die vorhandene isolierte Laufzeit
wurde geladen; beide OCR-/TableFormer-Ergebnisse kamen aus dem validierten Cache.
Keine neuen Erkennungsaufrufe oder Downloads, keine sichere Organisationszuordnung.

Nachgewiesener Bewertungsfehler: maskierte Modell-IDs konnten lesbare Referenz-IDs
aus dem Nenner entfernen. Korrigiert im Kurs- und älteren Excel-Vergleich.
Fehlende Teilnehmer waren bereits berücksichtigt, die Soft-F1-Formel ist korrekt.
Neue Zähler trennen falsch/fehlend/zusätzlich, bekannte Leerzellen und unbekannte
Referenz; optionale Statusspalten dokumentieren explizite Referenzzustände.
Technischer Erfolg und bedingte Auswertung vollständig erfolgreicher Kurse separat.
Namensgruppenvergleich beider Orientierungen im aktiven Testframework eingeschaltet;
Rohwerte und Reihenfolge bleiben erhalten, Tausche werden protokolliert.
Metrikversion `roster-levenshtein-v5-reference-denominators`. Die Seiten-Ground-Truth
erhält getrennte Informations-/Leerzellenmetriken, WER und konsistente CER bei
unklaren Modellwerten. Historische Allfeldmetriken bleiben daneben erhalten.

Abschlussbericht und wissenschaftliche Empfehlungen:
[software/docs/evaluation-audit.md](software/docs/evaluation-audit.md).
Lokale neue Ansichten: `software/runs/evaluation-audit-20261103-final/report.html`
und darunter `repaired-docling/report.html`. Der Audit isoliert Regeländerung,
Namenstausch und neue Docling-Ausgaben; die anderen fünf Verfahren wurden nicht
erneut erkannt. `audit.json` belegt unveränderte historische Dateien und tatsächliche
Laufbild-Hashes. JSON/CSV/Excel/HTML-Zähler und Referenznenner wurden gegengeprüft.
Der Namenstausch erklärt die Scoreänderungen bei VLM/Hybrid; keine verbesserte
Modellerkennung behaupten. Aktuelle Referenz ohne maskierte Modell-IDs:
die reine Korrektur dieser Ausschlussregel ändert dort keine Scores.
Abschließende Prüfung: **591 lokale Tests in 106,49 s**, **48 API-Tests in 10,46 s**,
Ruff und Berichtszähler konsistent. API-Vorlage besitzt dieselben Matchingoptionen;
kein API-Modellaufruf. Offene Grenze bleibt die sichere Erkennung der Folgeseite
und eine unabhängige manuell geprüfte Seiten-/Handschriftreferenz.

### Aufbau und Einstieg

- `software/`: Python-/uv-Projekt. Befehle für die Software aus diesem Ordner
  ausführen. Kernpaket: `software/verarbeitung/src/participant_bench/`.
- `software/vorverarbeitung/`: PDFs sammeln, nach Schulungs-ID benennen und
  Arbeitskopien vorbereiten. Originaldaten liegen in `dateien/`.
- `software/configs/benchmark.yaml`: Hauptprofil mit `ocr_raw`, `ocr_llm`,
  `paddle_llm`, `docling`, `vlm`, `ocr_vlm`.
- Gemeinsame generative Modelle: `Qwen/Qwen3-4B-Instruct-2507` für Text und
  `Qwen/Qwen3-VL-4B-Instruct` für Bild-/Hybridverfahren. Revisionen und lokale
  Pfade stehen in den Konfigurationen.
- `software/testframework/`: nachträglicher Excel-/CSV-Abgleich. Nur gleiche
  Class ID vergleichen; die Referenzspalte `Organization` ist das Kurzzeichen.
  Führende Nullen in User IDs werden im aktiven Referenzvergleich ignoriert,
  bleiben aber in den extrahierten Originalwerten erhalten.
- `software/api_firmen_pc/`: separater API-Einstieg für den Firmen-PC mit eigener
  Umgebung. Lokale Analyse und API-Betrieb getrennt halten.
- `bachelorarbeit/`: LaTeX-Quellen; eigener Bereich mit eigener README.

Weitere Einstiege: [Repository-README](README.md),
[Software-Anleitung](software/README.md),
[Verfahrensbeschreibung](software/docs/local-methods.md),
[bisherige Verifikation](software/docs/verification.md).

### Nachtrag: Ausgabereihenfolge der Anwesenheitsliste

Auf Nutzerwunsch folgen Teilnehmerausgaben der PDF-Eingabereihenfolge, der
PDF-Seite und dem ursprünglichen erkannten Eintragsindex. Die Referenz wird
nur zugeordnet und darf die Modellzeilen nicht sortieren. Reine Referenzfälle
ohne zugeordnete Ausgabe stehen nach den tatsächlichen Ausgaben; in der
Detailansicht haben sie einen eigenen Abschnitt.

Gemeinsame Darstellungsregel in `output_order.py`, verwendet vom Hauptbericht,
neuem und älterem Referenzabgleich, Detail-/Namenszuordnung und Hybrid-Feldexport.
Excel-Modellblätter erhalten die Ausgaben direkt in Quellenreihenfolge statt
einer vorherigen Gruppierung nach Referenzkursen. Matching und Bewertungsregeln
bleiben erhalten. Tests decken umgekehrte Referenzlisten, durcheinander gespeicherte
Seiten, mehrere PDFs/Kurse, zusätzliche Ausgaben und fehlende Referenzpersonen ab.
Historische Berichte und Extraktionen nicht überschreiben.
Abgeschlossen: 571 lokale Volltests und 48 API-Tests bestanden. Zwei vorhandene
reale Vergleiche mit eingefrorenen Referenzen neu dargestellt, ohne Modellaufrufe:
`software/testframework/ergebnisse/source-order-20261102/opened-report/` und
`software/testframework/ergebnisse/source-order-20261102/latest-userids/`.
Die dortige übergeordnete `validation.json` bestätigt identische Kennzahlen,
unveränderte Quelldaten und gleiche Quellenreihenfolge sämtlicher Modellzeilen.

### Nachtrag: Nachname zuerst und vollständige Namensgruppen

Auf ausdrücklichen Nutzerwunsch gilt für neue Läufe standardmäßig
Nachname → sämtliche Vornamen. Klare Spaltenüberschriften haben Vorrang.
Ein Komma trennt vollständige Gruppen; mehrteilige/mit Bindestrich verbundene
Nachnamen werden nicht am zweiten Wort abgeschnitten. `name_order.basis`
unterscheidet Dokumentbeleg und Standardannahme. Spätere klare Überschriften
können die Annahme ohne künstlichen Dokumentwiderspruch ersetzen.
Unmarkierte mehrteilige Namen bleiben bei unklarer Gruppengrenze Prüffälle;
Originaltext und bereits gelesene Gruppen bleiben erhalten.

Implementiert in `name_parts.py`, `document_names.py`, den beiden Docling-
Zuordnungen und den gemeinsamen Modellanweisungen. Promptversionen:
`participant-json-v22-family-first-name-groups`, Zellzuordnung v15/v16.
Abgeschlossen: 69 gezielte Namens-/Strukturtests, 567 lokale Volltests und
48 API-Tests bestanden. Praktischer unabhängiger synthetischer Lauf:
`software/runs/20261102T092453Z-ffe0c48d/`. Die ergänzende Inhaltsprüfung
`software/runs/name-groups-20261102/report.html` zeigt 6/6 richtige Namensfelder
bei OCR-LLM und VLM, 4/6 bei Docling. Die Docling-OCR enthält den ersten Namen
samt Komma korrekt; die native Tabelle enthält in der Namenszelle jedoch einen
Organisationscode. Das ist `cell_assignment_failed`, kein belegter OCR-Lesefehler.
Die Aufteilung bleibt unklar. Die Inhaltsprüfung verwendet dieselben vorab verfassten
Referenzwerte ohne Positionslabels und den üblichen approximativen Namens-/
Organisationsabgleich. Ursprüngliche Positionsmetriken bleiben erhalten: Die
OCR-Textzeilenboxen unterschreiten gegenüber ganzen GT-Tabellenzeilen die strenge
IoU-Schwelle und liefern dort trotz richtiger Namensstrings keine Zuordnung.
Dieser Funktionstest belegt keine allgemeine Qualität auf realen Dokumenten.
Keine historischen Rohantworten
oder Ergebnisse umschreiben; keine Namenswerte aus Referenzen übernehmen.

### Nachtrag: User IDs unter „Benutzer“

„Benutzer“ wird bereits als `personnel_number` erkannt; „Benutzername“ bleibt
eine Namensspalte. Im vom Nutzer geöffneten Vergleich
`software/testframework/ergebnisse/20261102T074721Z-1c30943c/` stammen die
Ausgaben aus `software/runs/20261102T074109Z-328a26c1/`. Damals fehlten die
Textgewichte; VLM/Hybrid lasen auf Seite 1 neun ID-Zellwerte, bezeichneten die
Spalte aber als „Nr“. Der Parser ließ deren ID-Zuordnung deshalb unklar.
Die neueren Paddle-Läufe enthalten bereits neun Benutzer-IDs auf Seite 1.

Die gemeinsame VLM-Anweisung wurde unter Promptversion
`participant-json-v21-visible-benutzer-headings` präzisiert: „Benutzer“ ist
eine ID-Spalte, eine numerische erste Spalte nicht automatisch eine Zeilennummer.
OCR-LLM erhält dieselbe explizite Feldbedeutung. Zwei Integrationstests prüfen
gefüllte Benutzer-Spalten einschließlich führender Nullen bis zum Excel-Export.
65 gezielte Tests sowie anschließend 546 lokale Volltests und 48 API-Tests
auf v21 bestanden. Der erste reale Kandidat v20 übernimmt zwar neun IDs auf Seite 1,
erfindet jedoch auf der Folgeseite eine Benutzer-Spalte über Kurzzeichen.
Dieser Kandidat wird nicht übernommen; sein gezielt beendeter Lauf
`software/runs/20261102T084044Z-e1089296/` bleibt als negativer Befund erhalten.
v21 verlangt für jede Überschrift einen auf der aktuellen Seite sichtbaren Beleg.
Die vollständige v21-Gegenprobe ist abgeschlossen:
`software/runs/user-id-validation-20261102-v21/report.html`.
Modelllauf: `software/runs/20261102T084927Z-483e59b1/`; neuer Kursvergleich:
`software/runs/user-id-validation-20261102-v21/comparison/20261102T085935Z-8c47146d/`.
Beide Bildverfahren geben auf Seite 1 neun IDs aus; davon sind acht beim VLM
und neun beim Hybrid im konfigurierten Kursvergleich exakt (führende Nullen
werden nur beim Vergleich ignoriert). Auf Seite 2 bleiben neun ID-Felder unklar;
keine Kurzzeichen werden als IDs ausgegeben. Die exakten Trefferzahlen der
übrigen Textfelder bleiben gegenüber dem alten Bericht unverändert. Gleiche
tatsächliche Laufbild-Hashes, visuelle Modellparameter und Referenz geprüft.
Keine alten Ausgaben
umschreiben oder unbelegte „Nr“-Spalten nachträglich allein nach Zahlenformat
in Benutzer-IDs umdeuten.

### Docling-/Paddle-Fehleranalyse und Organisationszuordnung

**Status: technische Umsetzung, Vergleichsläufe und Regressionstests abgeschlossen.**
Manuelle Seitentranskripte für separate
Handschriftmetriken fehlen. Die reale PDF wurde gegen die vorhandene Kursliste
bewertet; ein realer Qualitätsgewinn wurde nicht nachgewiesen. Codebasis bei
Anlage dieser Übergabe: Commit `021e763`.

Bereits implementiert:

- `column_headers.py`: zusätzliche Organisationsüberschriften, etwa
  „Org.-Einheit“, „Organisationseinheit“ und „Organizational Unit“.
- `structured_mapping.py`: deterministische Zuordnung aus nativen
  TableFormer-Zellen mit Zellbelegen, statt ausschließlich aus HTML.
- `structure_diagnostics.py`: lokale Stufendiagnose und Bild-Overlays;
  CLI `diagnose-structures`. Unbelegte OCR-Ursachen bleiben unbekannt.
- `structure_experiment.py`: kontrollierter Vergleich von FAST/ACCURATE,
  Cell Matching an/aus und optional Full-Page-OCR; CLI `structure-experiment`.
- `structure_runtime/docling_backend.py`: konfigurierbare OCR-Skalierung,
  Full-Page-OCR, Cell Matching und protokollierte effektive Optionen.
- `unlimited_assignment.py` und `structure_assignment.py`: vorbereitete
  erweiterte Übergabe von OCR-Positionen, Konfidenzen und Überschriftenrollen
  sowie Zwischenstände vor/nach der Feldvalidierung.
- `configs/structures-baseline.yaml` erhält explizite bisherige Einstellungen;
  `configs/docling-full-page.yaml` ist ein gesondertes Experiment.
- `scripts/make_structure_diagnostics.py`: synthetische Entwicklungsfälle.
  Eine simulierte Schreibschrift ist ausdrücklich keine echte Handschrift.

**Im Hauptprofil seit der Wiederaufnahme aktiviert:**

- Docling verwendet `mapping: structured`, ACCURATE und `do_cell_matching: false`.
- Paddle behält nach der praktischen Gegenprobe `assignment_format: legacy_v13`.
  Der Kandidat `positioned_v14` ist in `configs/paddle-positioned.yaml` verfügbar;
  auf Entwicklungsdaten verliert er eine Zuordnung und gewinnt keine Organisation.
  Die frühere Docling-Konfiguration bleibt im Baseline-Profil verfügbar.
- Full-Page-OCR bleibt eine gesonderte Variante. Auf dem synthetischen
  Entwicklungsdatensatz war kein Vorteil gegenüber der Standard-OCR erkennbar.

Nachweisbarer Befund aus dem historischen Lauf
`software/runs/20261029T124104Z-ae17bebb/`:

- In den betrachteten Docling-Tabellen fehlen verwertbare erkannte
  Spaltenüberschriften; eine eindeutige deterministische Zuordnung ist dadurch
  blockiert. Die ursprüngliche OCR-Ursache ist damit noch nicht vollständig erklärt.
- Auf der ersten betrachteten Paddle-Seite sind Organisationswerte in den
  OCR-Belegen vorhanden, die damalige LLM-Antwort liefert aber keine Abteilungen.
  Ein Verlust bei der LLM-Zuordnung ist damit belegt; nicht pauschal die OCR
  als Ursache bezeichnen.

Lokal vorhandene Diagnose-/Vergleichsartefakte (gitignoriert):

- `software/runs/organization-diagnosis-historical-20261029/report.html`
- `software/data/structure-diagnostics-development-20261029/`
- `software/runs/structure-experiment-development-20261029-v3/`
  enthält **zwei abgeschlossene Varianten**: `accurate-matching-on` und
  `accurate-matching-off`. Dieser historische Versuch blieb unvollständig;
  seine vollständige neue Gegenprobe steht unter `structure-20261102/`.
- Neuer Vergleich `software/runs/structure-20261102/`: alle fünf Varianten
  abgeschlossen, einschließlich FAST an/aus und Full-Page-OCR. Identität,
  Vorher-/Nachher-Metriken und vollständiger HTML-Bericht liegen dort.
- Vorangegangene Versuchsausgaben ohne `-v3` blieben erhalten. Bei den frühen
  Versuchen wurden Manifest-Split- und Windows-Pfadlängenprobleme gefunden;
  der Versuchscode verwendet inzwischen reguläre flache Run-Ordner und kurze
  Diagnose-Unterordner.

Zusätzliche abgeschlossene Arbeiten:

- Exakte Textgewichte heruntergeladen, mit `download_manifest.json` verifiziert
  (zwölf Dateien) und tatsächliche Qwen3-4B-Instruct-2507-Inferenz ausgeführt.
- Vier Vorher-/Nachher-Läufe abgeschlossen; Index und Abschlussstatus:
  `software/runs/structure-acceptance-20261102/runs.json` und `state.json`.
- Realer Vergleich gegen dieselben 18 Kursreferenzpersonen:
  `software/runs/structure-acceptance-20261102/real-comparison-v2/report.html`.
  Docling vorher/nachher 0/72 Textfelder; Paddle jeweils 29/72, 3/18 Organisationen.
  Die zusätzliche Übergabe verbessert diesen realen Fall nicht.
- Zwei zusätzliche reale Docling-OCR-Läufe (PSM 11 und Full-Page-OCR ohne Cell
  Matching) abgeschlossen, ebenfalls null sicher zugeordnete Personen.
- Abschlussbericht mit Konfigurationstabelle, allen Kennzahlen, Diagnoseursachen
  und Reproduktionsbefehlen: `software/docs/structure-optimization.md`.

Für eine spätere belastbare Handschriftevaluation offen:

Manuelle Seitentranskripte/Zeilenreferenzen und weitere unabhängig getrennte
Dokumente beschaffen. `software/data/handwriting-review-20261102/` ist eine leere
manuelle Referenzvorlage, keine geprüfte Ground Truth. Vorhersagen nicht als
Referenz übernehmen. Die jetzige Excel-Referenz erlaubt nur die dokumentweite
Kursauswertung; aus bedingten Seitenwerten keinen Handschrift-Recall ableiten.

### Prüfstand

Am 2026-11-03 bestanden nach dem Handschriftnachtrag **609 vollständige lokale
Tests** in 81,90 Sekunden sowie **48 Tests des getrennten API-Projekts** in
17,60 Sekunden auf dem endgültigen geänderten Kerncode. Vergleichsskripttests prüfen unter anderem
veränderte Original-/Laufbilder, Referenzänderungen und maskierte Felder.
Ruff, Markdown-Dateiverweise und `git diff --check` ohne Befund. 22 lokale
Pipelineprofile sowie Excel- und Testframework-Konfiguration erfolgreich geladen.

Erneut ausführbar:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Softwaretests sind kein Nachweis verbesserter Erkennungsqualität auf realen
Teilnehmerlisten. Ältere Zahlen in `software/docs/verification.md` beziehen sich
auf die dort datierten Stände.

### Weiter geltende fachliche Vorgaben

- Dokumente und lokale OCR-/Modellergebnisse bleiben lokal. API-Aufrufe gehören
  ausschließlich zum ausdrücklich getrennten Firmen-PC-Einstieg.
- Keine zusätzlichen LLMs/VLMs oder versteckten VLM-Leseschritte für reine
  OCR-/LLM-Verfahren einführen. Docling bleibt im Hauptvergleich ohne LLM/VLM.
- Gleiche Eingabeseiten und nachvollziehbare Varianten; keine automatische
  Auswahl vermeintlicher Anwesenheitslisten vor der Extraktion.
- Fehlende Werte nicht erfinden; leere Benutzer-IDs dürfen Kurzzeichen nicht
  in die falsche Spalte verschieben. Kursleiter nur bei belegter Rolle ausschließen.
- Ground Truth nicht an die Extraktion übergeben. Kein Tuning auf dem finalen
  Testset und keine Qualitätskennzahlen ohne passende Referenzdaten.
- Historische Ergebnisse erhalten. Zugangsdaten, Originaldokumente, lokale
  Modellgewichte und personenbezogene Diagnoseartefakte gehören nicht in Git.

## Änderungsprotokoll

### 2026-11-10 – Tesseract+LLM zusätzlich: eigener Fünfverfahren-Starter

- **Auftrag / geklärte Präferenz:** Nutzer bestätigt Tesseract+LLM zusätzlich,
  damit insgesamt fünf Verfahren. Die vorherige Rückfrage ist erledigt.
- **Dateien:** neu `software/configs/benchmark-five.yaml`,
  `software/start_testframework_5.cmd`; ergänzt `software/README.md`,
  `software/docs/method-selection.md`, `software/docs/method-selection-status.md`
  sowie diese Übergabe.
- **Implementiert / aktiv:** Fünferprofil mit `ocr_rules`, `ocr_llm`,
  `paddle_llm`, `vlm`, `ocr_vlm` über den vorhandenen Extraktions- und
  Testframework-Einstieg. Docling nicht ausgewählt; Viererprofil erhalten.
  Keine Modellwechsel, keine neue Pipeline und keine Änderung alter Ergebnisse.
- **Prüfungen:** Konfigurationslader erfolgreich; Methodenliste, unverändertes
  Viererprofil, OpenCV-Backend, vorhandenes Textmodell und identische
  VLM-/Hybridparameter geprüft. Fünfer-Starter `--pruefen` mit Exitcode 0,
  einer PDF und einem gemeinsamen Referenzkurs. `git diff --check` ohne Befund.
- **Offen / nächster Schritt:** Nutzer kann `software/start_testframework_5.cmd`
  starten. Kein neuer kompletter Fünfverfahren-Lauf durchgeführt. Die genannten
  neuen Paddle-/8B-Modellvarianten bleiben gesonderte Integrationsaufgaben.

### 2026-11-10 – Klassische Tesseract-/Regelbaseline ersetzt Docling im separaten Laufprofil

- **Auftrag:** Docling aus dem vorläufigen Vergleich herausnehmen und stattdessen
  OCR mit regelbasierter Extraktion als klassische Baseline aufnehmen.
- **Dateien:** `software/configs/benchmark-four.yaml`, `software/README.md`,
  `software/docs/method-selection.md`, `software/docs/method-selection-status.md`
  sowie diese Übergabe.
- **Implementiert / aktiv konfiguriert:** Viererprofil mit `ocr_rules`,
  `paddle_llm`, `vlm`, `ocr_vlm`; vorhandener Vierer-Starter bleibt gültig.
  Separates Profil `main_comparison: false`, weil der unveränderte alte Validator
  Regelverfahren aus seinem eingefrorenen Hauptvergleich ausschließt.
  Docling und alle historischen Ergebnisse bleiben verfügbar.
- **Geprüft:** Profil mit bestehendem Lader und ohne generative Zusatzstufe der
  Regelbaseline erfolgreich geladen. Vorabprüfung mit Exitcode 0. Regulärer
  End-to-End-Funktionstest der Regelbaseline auf zwei vorhandenen synthetischen
  Demo-PDFs: 2/2 Seiten erfolgreich, 3 Teilnehmer, 9/11 exakte Referenzfelder,
  Levenshtein-Feld-F1 90,00 %, keine fehlenden/zusätzlichen Teilnehmer.
  Extraktionslauf `20261110T123455Z-d8e15075`, Vergleich `20261110T123459Z-15843059`.
  Keine LLM-/VLM-Inferenz, keine Downloads und keine historischen Dateien geändert.
- **Offen:** zusätzliche kurze Nutzeräußerung „und ocr llm auch noch“ ist zur
  Klärung gestellt (zusätzliches Tesseract+LLM als fünftes Verfahren, Austausch
  des Paddle-Verfahrens oder ebenfalls entfernen). Keine davon abhängige Änderung
  vor einer Antwort. PP-OCRv6/Qwen3-8B und PaddleOCR-VL-1.6 bleiben gesonderte
  offene Integrationsaufgaben; aktuelles Paddle+LLM ist weiterhin PP-OCRv5 + Qwen3-4B.

### 2026-11-10 – Einfacher Start für die vier vorgeschlagenen Verfahren

- **Auftrag:** Nutzer möchte den angepassten Vergleich mit genau vier Verfahren
  starten können.
- **Dateien:** neu `software/configs/benchmark-four.yaml`,
  `software/start_testframework_4.cmd`; ergänzt `software/README.md`,
  `software/docs/method-selection.md`, `software/docs/method-selection-status.md`
  und diese Übergabe.
- **Zweck:** separater vorläufiger Laufmodus für Docling, Paddle+LLM, direktes VLM
  und OCR+VLM; bestehende Extraktion und Evaluation wiederverwenden.
- **Prüfung:** Profil erfolgreich mit bestehendem Konfigurationslader geladen;
  genau vier Methoden, reine Docling-Baseline und identische VLM-/Hybridparameter
  bestätigt. Neuer Starter mit `--pruefen` erfolgreich (Exitcode 0), eine PDF,
  ein gemeinsamer Kurs. Keine neue Inferenz oder Änderung historischer Ergebnisse.
- **Offen / nächster Schritt:** Nutzer kann `software/start_testframework_4.cmd`
  starten; tatsächlicher Vierverfahren-Lauf ist noch nicht erneut durchgeführt.
  Wissenschaftliche Empfehlung bleibt mangels unabhängiger Pilotstichprobe vorläufig.

### 2026-11-10 – Wissenschaftliche Verfahrensauswahl und reproduzierbare Pilotmethodik

- **Auftrag:** bestehendes Framework um zweistufige Eignungsprüfung und
  gruppierten Pilotvergleich ergänzen, höchstens drei Hauptarchitekturen
  begründen, Methodik/Quellen aktualisieren; keine neue Evaluationspipeline.
- **Dateien:** neue `software/configs/selection.yaml`, vier `selection*.py`-Module
  unter `software/verarbeitung/src/participant_bench/`,
  `software/scripts/replay_method_selection.py`, `software/tests/test_method_selection.py`,
  `software/docs/method-selection.md`, `software/docs/method-selection-status.md`;
  erweitert: `cli.py`, `roster_benchmark/evaluation.py`, `roster_benchmark/metrics.py`,
  Repository-/Software-/Testframework-/Bachelorarbeits-README,
  `software/docs/local-methods.md`, `bachelorarbeit/chapters/03_methodik.tex`,
  `bachelorarbeit/verified_sources.bib`, `bachelorarbeit/BUILDSTATUS.md` und Übergabe.
- **Zweck:** unbekannte Evidenz bleibt unbekannt; keine Umgewichtung zu einem
  künstlichen Gesamtscore. Entwicklung, Pilot und Test gruppiert trennen;
  frühere Entwicklungsnutzung nicht umdeklarieren. Vorhandene Läufe, Grundprompts,
  Referenzsnapshots und tatsächliche Bildidentitäten kontrolliert wiederverwenden.
  Originalrollen auf festen Referenzpaaren zusätzlich zur neu gepaarten strikten
  und zur Swap-Auswertung zeigen. Ausfälle behalten Nenner und Fehlerstatus;
  Laufzeit-/Ressourcenbasis und Cacheeffekte explizit ausweisen.
- **Implementiert / getestet / aktiv / nachgewiesen:** Funktionen und neuer
  Auswahlpfad implementiert; Hauptprofile unverändert. 18 neue gezielte Tests,
  693 vollständige lokale Tests (55,72 s), 48 API-Tests (7,78 s), Ruff bestanden.
  Vorhandene reale Entwicklungsartefakte lokal erneut bewertet, keine neue
  Inferenz. Ergebnis: eine Gruppe, zwei Seiten, 72 Referenzfelder, Status
  `provisional`; dokumentierte Empfehlung `docling`, `paddle_llm`, `vlm` plus
  optional `ocr_vlm`. Keine reduzierte Hauptkonfiguration oder Qualitätsgarantie.
  LaTeX-/BibTeX-Build 29 Seiten erfolgreich, geänderte Seiten visuell geprüft.
  CSV-/JSON-Summen, Plan-Siegel und neue HTML-/Markdown-Verweise geprüft.
- **Offen / nächster Schritt:** unabhängige 30–50 Pilotlisten samt Gruppen- und
  Nutzungsprüfung; finale Testdaten unberührt halten. Harte offene Kriterien,
  passende Referenzen und vergleichbare Ressourcen-/Kosten-/Aufwandsmessungen
  ergänzen. Erst danach Rollenbesetzung abschließend begründen und gegebenenfalls
  bewusst ein reduziertes Profil anlegen. Personenbezogene Unterberichte verbleiben
  lokal unter gitignorierten Laufordnern.

### 2026-11-03 – Handschrift: Datenverlust bei Teilzeilen behoben und OCR-Varianten geprüft

- **Auftrag:** Tesseract/Paddle/Docling auf Handschriftverluste untersuchen,
  beobachtete Teiltexte erhalten, kleine kontrollierte Varianten vergleichen,
  Modelleignung und optionale HTR-Erweiterung wissenschaftlich einordnen.
- **Dateien:** `unlimited_assignment.py`, `structure_assignment.py`,
  `structured_mapping.py`, `structure_diagnostics.py`, `config.py`,
  `structure_runtime/paddle_backend.py`, neue Skripte `handwriting_probe.py`
  und `replay_partial_assignments.py`, `tests/test_handwriting_retention.py`,
  Software-README, `docs/local-methods.md`, `docs/structure-optimization.md`,
  neue `docs/handwriting-optimization.md`, `docs/verification.md`, diese Übergabe.
- **Änderung:** Fehlende einzelne Zielfelder bleiben unbekannt, statt ganze
  belegte Personen abzulehnen. Übrige Typ-/Literal-/Positionsprüfungen bleiben
  aktiv. Originalkonfidenzen/-texte in Beweisen erhalten; niedrige Engine-Scores
  und Teiltextmarker als Unsicherheit markieren. Unreferenzierte OCR-Belege
  separat exportieren. Optionale Paddle-Probeparameter ohne globale Umstellung.
- **Nachweis:** Gefrorene Antwort enthält neun Handschrift-Personen, früher
  wegen eines fehlenden Felds sämtlich Schemaausschlüsse. Replay jetzt neun
  zusätzliche Personen, neun neue exakte und acht zusätzliche falsche Felder.
  Alle bisherigen 29 Treffer erhalten; erste Seite inhaltlich unverändert.
  Neue Precision 71,70 % statt 80,56 %, Recall 52,78 % statt 40,28 %. Das ist
  Datenerhalt, keine neue OCR-Erkennungsleistung; zusätzliche Fehler sichtbar.
- **Versuche:** Sieben Tesseract-Varianten auf beiden Seiten, 24 native
  Zellausschnitte, Paddle mit zwei Detektionsgrößen und Docling ohne Linien-
  entfernung DEFAULT/FULL_PAGE. 46 zusätzliche OCR-/Strukturaufrufe insgesamt.
  Keine Modelle geladen, die nicht schon vorhanden waren, keine Downloads.
  Docling-Kandidaten verlieren die bisherige Teilzuordnung; nicht übernehmen.
  Mehr Zeichen oder nichtleere Ausschnitte nicht als Qualitätsgewinn interpretieren.
- **Prüfung:** 72 gezielte Tests, 609 lokale Volltests, 48 API-Tests, Ruff bestanden.
  Keine API-Modellaufrufe. Historische Artefakte/Referenzen unverändert; gleicher
  Referenznenner, Reihenfolge und Antworttext kontrolliert. Endgültiger Replay
  und Abschlussbericht oben verlinkt; Ressourcen- und Variantenartefakte lokal.
- **Grenzen:** Nutzer nennt Excel-Werte auch für Handschrift, aber keine
  Lokalisierung. Dokumentweite Kursübereinstimmung ist messbar, separate
  Handschrift-CER/WER/Regionserkennung nicht. Seitenreferenz vor solchen Messungen
  manuell prüfen; insbesondere IDs in der Kursliste können auf der PDF leer sein.
  HTR nur als getrennte spätere Option beschrieben; keine Modellgrenze durch
  beliebig komplexe Regeln oder erfundene Teiltexte kompensieren.

### 2026-11-03 – Docling-Teilinformationen, wissenschaftlicher Metrikaudit und Berichte

- **Auftrag:** Fehlende Docling-Ausgaben reparieren, Bewertungsnenner und
  Soft-F1/konservative Zuordnung prüfen, fehlende Felder sichtbar machen,
  redundante Tabellen vereinheitlichen; vorherigen Wunsch nach beiden
  Namensorientierungen im Referenzvergleich umsetzen.
- **Dateien:** `structured_mapping.py`, `structure.py`, `structure_diagnostics.py`,
  `evaluation.py`, `excel_reference.py`, `excel_comparison.py`, `reference_states.py`,
  `hybrid_evaluation.py`, Konfiguration/Referenzen/Matching/Metriken/Evaluation/
  drei Berichte unter `roster_benchmark/`; lokale und API-Testframework-Konfiguration,
  neue `tests/test_metric_audit.py`, betroffene bestehende Tests,
  `scripts/audit_metrics_docling.py`, Testframework-README,
  `docs/evaluation-audit.md`, `docs/excel-comparison.md`, `docs/verification.md`.
- **Änderungen:** Begrenzter nativer Fallback erhält nur wiederholt belegte
  Namens-/Nummernzellen als unsicher, ohne Organisations-/Signaturwerte zu raten.
  Nur Referenzzustände begründen Bewertungs-Ausschlüsse; Modell-Platzhalter
  bleiben Fehler. Neue Informations-/Leerzellenzähler, Recall/Abdeckung,
  technische Zuverlässigkeit und bedingte erfolgreiche Kurse. Gesamte
  Namensgruppen optional in beiden Orientierungen vergleichen und protokollieren;
  Quellen und Rohwerte erhalten. Einheitliche Feldtabellen und Metrikblätter
  in Excel; Formeln zentral, Nenner-/Zähler-Invarianten automatisch prüfen.
- **Prüfung:** 591 lokale Tests und 48 API-Tests bestanden; Ruff ohne Befund.
  Drei lokale Vergleichsberichte gegen eingefrorene Referenz und identische
  tatsächliche Laufbilder; historische Dateien hashgleich. Zähler aus JSON,
  CSV, Excel und HTML sowie Detailbeiträge stimmen überein. Docling-Regulärlauf
  erfolgreich mit 9 unsicheren Teilpersonen aus vorhandenen Erkennungsbelegen,
  keine neuen Erkennungsaufrufe/Downloads. Die API-Gegenprobe deckte eine
  abweichende Matchingoption auf; beide öffentlichen Vorlagen jetzt gleich.
- **Befund/Grenze:** F1-Formel und bisherige Behandlung fehlender Personen waren
  korrekt. Der Modellmaskierungs-Ausschluss und inkonsistente CER-Nutzung
  unbekannter Modelltexte waren Fehler. Reale Entwicklungs-PDF: 19/72 Docling-
  Felder exakt, aber 47 fehlen weiterhin; Folgeseite nicht sicher zugeordnet.
  Kursreferenz nicht als bestätigte Seitentranskription ausgeben. Keine allgemeinen
  Handschrift-/Identitätsaussagen. Primär exakten Feld-Recall plus Precision/F1
  und Vollständigkeit berichten; Softmetriken ergänzend. Details und Artefakte oben.

### 2026-11-02 – Anwesenheitsreihenfolge in allen Ergebnisansichten

- **Auftrag:** Ausgabe in der Reihenfolge der Anwesenheitsliste erhalten;
  Referenzreihenfolge nicht als Ausgabereihenfolge verwenden.
- **Dateien:** `output_order.py`, Hauptbericht, `excel_comparison.py`,
  `hybrid_evaluation.py`, Referenzabgleichsmetriken/-evaluation und die beiden
  Detailansichten, `tests/test_output_order.py`, Testframework-README,
  `docs/excel-comparison.md`, `docs/verification.md`, diese Übergabe.
- **Änderung:** Sortierung nach Eingabe-PDF, numerischer Seite und bestehendem
  Ausgabeindex, ohne Namen/Referenzzeilen als Sortierschlüssel. Reine Referenzfälle
  nachstellen und in Details separat kennzeichnen. Teilnehmer-Excel vor der
  Kursgruppierung aufbauen. Auch alte gespeicherte Detailansichten werden beim
  erneuten Rendern nach Quellenreihenfolge angezeigt, ohne neue Modellaufrufe.
- **Prüfung:** Neue Ende-zu-Ende-Tests prüfen CSV, Excel und HTML bei umgekehrter
  Referenz und unveränderten Kennzahlen/Quellvorhersagen. 119 gezielte Tests,
  571 lokale Volltests (93,03 s), 48 API-Tests (9,81 s) und Ruff bestanden.
  Zwei reale gespeicherte Vergleiche neu ausgegeben; Kennzahlen vollständig
  identisch und alle Quellartefakte unverändert. Keine erneute Modellinferenz.
  Neue Pfade und Quellenreihenfolge sind oben dokumentiert.

### 2026-11-02 – Standard Nachname zuerst, flexible Namensgruppen

- **Auftrag:** Nachname vor Vorname annehmen, mehrere Vornamen und doppelte
  Nachnamen vollständig erhalten.
- **Dateien:** `name_parts.py`, `document_names.py`, `models.py`, `schema.py`,
  `unlimited_assignment.py`, `table_mapping.py`, `structured_mapping.py`,
  `report.py`, Tests für Dokumentnamen und Strukturdiagnose, `docs/local-methods.md`,
  `docs/structure-optimization.md`, `docs/verification.md`, diese Übergabe.
- **Änderung:** Nutzerstandard als eigene Entscheidungsquelle, klare Überschriften
  weiterhin vorrangig. Kommagrenze korrigiert auch falsch abgeschnittene
  Nachnamengruppen vor der strikten Zellvalidierung. Native OCR-Fragmente nutzen
  die belegte Namensspalte. HTML/CSV weisen Standardannahmen und Neuaufteilungen
  getrennt aus. Mehrdeutige unmarkierte Dreier-/Mehrfachnamen werden nicht blind
  am ersten Leerzeichen geteilt; unvollständige Personen bleiben erhalten.
- **Prüfung:** 69 gezielte Tests, 567 lokale Volltests (155,44 s), 48 API-Tests
  (14,69 s) und Ruff bestanden. Praktischer Docling-/OCR-LLM-/VLM-Test abgeschlossen,
  Eingabe und Referenz unabhängig vor der Inferenz erstellt. OCR-LLM/VLM geben
  alle drei Namensgruppen korrekt aus; Docling lässt eine wegen fehlerhafter nativer
  Zellzuordnung unklar. Die OCR-Belege enthalten den vollständigen Namen samt
  Komma korrekt, die native Namenszelle enthält dagegen einen Organisationscode.
  Frühere Komma-/Punkt-Vermutung ausdrücklich verworfen; Ursache anhand Rohdaten
  geprüft. Die obige ergänzende Inhaltsprüfung und ihre Grenzen sind protokolliert.
- **Grenze:** Ohne Komma, Bindestrich oder andere Gruppierungsbelege kann ein
  doppelter Nachname nicht immer von mehreren Vornamen unterschieden werden.
  Dann keine blinde Worttrennung und keine Namen aus Referenzen übernehmen.

### 2026-11-02 – Benutzer-ID und Zeilennummer unterscheiden

- **Auftrag:** Fehlende User IDs bei der PDF-Überschrift „Benutzer“ untersuchen.
- **Dateien:** `models.py`, `tests/test_vlm_cells.py`, `docs/local-methods.md`,
  `docs/verification.md`, diese Übergabe.
- **Befund/Änderung:** Vorhandenes Alias-Mapping ist korrekt. Der ältere
  VLM-/Hybrid-Lauf gibt die Benutzer-Spalte als „Nr“ aus; seine neun Zellwerte
  werden deshalb nicht als IDs exportiert. Gemeinsame Modellanweisung und
  Beispiele für echte Benutzer-Spalten präzisiert, Promptversion erhöht.
- **Prüfung:** 65 gezielte Tests, 546 lokale Volltests, 48 API-Tests und Ruff
  bestanden. Vollständige reale Gegenprobe abgeschlossen: VLM 9 IDs, 8 korrekt;
  Hybrid 9 IDs, 9 korrekt; zuvor beide 0 IDs. Auf der Folgeseite jeweils 0
  ausgegebene IDs und 9 unklare ID-Felder. Andere Textfeld-Treffer unverändert.
  `user_id_audit.json` belegt gleiche Laufbilder, Modellparameter und Referenz;
  Rohwerte bleiben erhalten. Ein einzelner VLM-Lesefehler wird nicht anhand der
  Referenz korrigiert. v20 wurde wegen falscher IDs auf der Folgeseite verworfen.
- **Grenze:** Ein realer Entwicklungsfall; keine allgemeine Genauigkeitsgarantie.
  Auswertung und Bericht sind abgeschlossen. Die üblichen Starter verwenden
  die aktualisierte gemeinsame Modellanweisung für neue Läufe.

### 2026-11-02 – Abgeschlossene Messungen und begründete Profilwahl

- **Dateien:** `configs/benchmark.yaml`, neue `configs/paddle-positioned.yaml`
  und `configs/docling-sparse.yaml`; `scripts/compare_structure_runs.py` und
  dessen Tests; `docs/structure-optimization.md`, `docs/local-methods.md`,
  Software-README und diese Übergabe.
- **Befund:** Alle fünf Docling-Varianten und vier praktische A/B-Läufe sind
  abgeschlossen. Native Docling-Zellen ohne Matching verbessern synthetisch
  12/28 auf 16/28 Textfelder und 0/7 auf 4/7 Organisationsfelder, davon zwei
  korrekt leere Felder. Reale PDF: kein Qualitätsgewinn. Zusätzliche OCR-Modi
  helfen dort ebenfalls nicht. Alle Rohdaten/Overlays bleiben lokal erhalten.
- **Entscheidung:** Docling nativ aktiv. Paddle nach der negativen Gegenprobe
  bei `legacy_v13` belassen; `positioned_v14` bleibt ausdrücklich experimentell.
  Die beiden endgültigen Methodeneinstellungen wurden gegen die eingefrorenen
  tatsächlich geprüften Konfigurationen auf Gleichheit geprüft.
- **Vergleichsskript:** Prüft zusätzlich die tatsächlichen Laufbild-Hashes und
  gespeicherten Bilddateien, nicht nur die ursprünglichen Seiten. Friert die
  Referenz einmal ein. Feldwechsel und bedingte Seitendiagnose stehen separat.
- **Prüfung:** Abschließend 544 lokale Volltests bestanden (163,52 s), 48 API-Tests
  bestanden, Ruff und Dateiverweise ohne Befund. Ein während der Profiländerung
  laufender früherer Test las noch die alte Assertion; die endgültige Fassung
  wurde anschließend vollständig erneut geprüft. Beide finalen Methodeneinstellungen
  entsprechen den separat tatsächlich gemessenen Einstellungen; Beleg unter
  `software/runs/structure-acceptance-20261102/final_profile_selection.json`.
  Die Original-PDF ist hashgleich zur unveränderten Arbeitskopie.
- **Berichte:** Einstieg `software/runs/structure-acceptance-20261102/report.html`;
  Abschlussbericht `software/docs/structure-optimization.md`. Gewichte und
  personenbezogene Einzelartefakte sind gitignoriert und gehören nicht in den Push.
- **Offen:** Wissenschaftlich belastbare separate Handschriftmetriken benötigen
  die oben genannten manuellen Referenzen. Kein realer Qualitätsgewinn behaupten.

### 2026-11-02 – Wiederaufnahme: vollständiger Vergleich und praktische Modellprüfung

- **Auftrag:** Die noch offenen Schritte des Docling-/Paddle-Auftrags durchführen.
- **Dateien bisher:** `structure_experiment.py`, `structure_assignment.py`,
  `unlimited_assignment.py`, `structure_diagnostics.py`, `structured_mapping.py`,
  `tests/test_structure_diagnostics.py` im Softwareprojekt sowie diese Übergabe.
- **Änderung:** Der Variantenvergleich speichert Identität und HTML-Zwischenstand
  bereits vor der Inferenz und nach jeder Variante. Ergänzt sind Feld-/Datensatz-
  Exact-Match, Organisations-CER, nichtleere Organisationswerte, normalisierte
  Zeichendistanz und feldweise Vorher-/Nachher-Dateien. Absichtlich ausgeschlossene
  Trainer gelten in der Diagnose nicht mehr als Normalisierungsfehler;
  widersprüchliche Paddle-Spalten werden in der erweiterten Übergabe zurückgewiesen.
- **Prüfung bisher:** 44 gezielte Tests bestanden, Ruff ohne Befund. Vollständige
  Regressionstests folgen nach der endgültigen Konfiguration.
- **Zwischenstand:** Vollständiger Fünfvariantenvergleich abgeschlossen.
  Auf denselben sieben synthetischen Referenzpersonen erreicht natives
  ACCURATE-Mapping ohne Cell Matching 4/7 exakte Organisationsfelder und
  16/28 exakte Textfelder. Das ist ein kleiner Entwicklungsfunktionstest,
  kein allgemeiner Genauigkeitsnachweis. Modell-Setup ist verifiziert.
  Reale und synthetische Vorher-/Nachher-Läufe laufen sequenziell unter
  `software/runs/structure-acceptance-20261102/`; `runs.json` verlinkt sie.
- **Weitere Dateien:** `configs/benchmark.yaml` aktiviert die begründet gewählten
  Varianten. Der Erkennungscache in `structure.py` trennt jetzt OCR-Einstellungen
  von reiner Feldzuordnung, damit identische Paddle-OCR beim A/B-Vergleich geteilt
  wird; ursprüngliche OCR-Zeiten werden weiterhin zugerechnet.
  `scripts/compare_structure_runs.py` und dessen Tests ergänzen einen lokalen
  Vorher-/Nachher-Kursvergleich mit derselben eingefrorenen Referenz.
- **Prüfung erweitert:** 539 vollständige lokale Tests und 48 API-Tests bestanden;
  zusätzlich vier Tests des neuen Vergleichsskripts bestanden. Nach dessen
  endgültiger Fassung die vollständige Testzahl erneut bestätigen.
- **Reale Referenz:** Nutzer nennt `software/testframework/eingabe_pdfs/140829.pdf`.
  Die vorhandene Datei `software/testframework/referenz/143754Completions.xlsx`
  enthält 18 Referenzpersonen für diese Klassen-ID. Referenzwerte werden nur
  nachträglich zur Evaluation verwendet. Gesonderte manuelle Seitentranskripte
  für echte Handschrift wurden bisher nicht gefunden.
- **Handschrift:** Unter `software/data/handwriting-review-20261102/` ist über
  den vorhandenen `ocr-reference`-Befehl eine leere manuelle Referenzstruktur
  angelegt. Sie enthält keine automatisch übernommenen Modellvorhersagen.
- **Nächster Schritt:** Vergleich abschließen, aktive Konfiguration begründen,
  tatsächliche Paddle-/LLM-Läufe und lokalen Kursreferenzvergleich durchführen;
  danach Dokumentation, Abschlussbericht und Prüfstand aktualisieren.

### 2026-11-02 – Dauerhafte Agentenübergabe eingerichtet

- **Auftrag:** Änderungen fortlaufend in einer auffindbaren Datei dokumentieren,
  damit folgende Agenten den Stand auch ohne frühere Chatnachrichten kennen.
- **Dateien:** `AGENTS.md` neu, `AGENTEN_UEBERGABE.md` neu, `README.md` um
  Verweise auf beide Dateien ergänzt.
- **Änderung:** Repositoryweite Anweisung zum Lesen und Pflegen dieser Übergabe;
  bestätigten Stand und offene Punkte des Docling-/Paddle-Auftrags übernommen.
- **Prüfung:** Alle lokalen Verweise in den drei betroffenen Dateien sind gültig,
  die Dateien sind nicht gitignoriert; `git diff --check` ohne Befund.
  Keine zusätzliche Modellinferenz oder Änderung der Pipeline in diesem Schritt;
  Dokumentationsänderungen benötigen keine neuen Softwaretests.
- **Offen / nächster Schritt:** Den oben beschriebenen Docling-/Paddle-Auftrag
  fortsetzen. Die Einrichtung der Übergabe schließt diesen Auftrag nicht ab.

### 2026-11-03 – Spaltenüberschriften auf Fortsetzungsseiten

- **Auftrag:** eindeutige Überschriften innerhalb einer PDF weiterverwenden,
  aktuelle Überschriften bevorzugen und inkompatible Tabellen sicher ablehnen.
- **Dateien:** neue gemeinsame Prüfung `column_context.py`, Erweiterungen in
  `structured_mapping.py`, `table_mapping.py`, `structure.py`, `structure_assignment.py`,
  `unlimited_assignment.py`, `ocr_layout.py`, `ocr_evidence.py`, `models.py`, `runner.py`;
  Herkunft in `report.py`/`structure_diagnostics.py`, sichere Neuzuordnung in
  `unlimited_reassign.py`. Neue `test_document_columns.py`, ergänzte vorhandene
  Zuordnungs-/Pipeline-Tests. Neues `scripts/check_document_columns.py`, optionale
  Ablation in `scripts/replay_partial_assignments.py`; Software-README,
  `docs/local-methods.md`, `docs/verification.md`, `docs/document-columns.md` und Übergabe.
- **Zweck:** bestehende Mappingkontexte um PDF-/Seitenbindung, generische
  Überschriftenbelege, Spaltenrollen, gemessene Geometrie und Herkunft ergänzen.
  Keine Teilnehmerwerte im vererbten Zustand. Gleiche Spaltenzahl allein genügt nicht;
  normalisierte Kantenabweichung maximal 0,035 der Seitenbreite bei gleicher Basis.
- **Prüfungen:** 627 Volltests, 48 API-Tests, anschließend 61 gezielte Tests
  bestanden. Ruff ohne Befund. Gleichbleibende OCR-/Maschinenschriftwerte,
  historische Dateihashes, JSON-/CSV-/Excel-Zähler geprüft. Neue und alte
  Überschriften, Leer-/Deckblatt, Spans, neue Reihenfolge, geringe Breitenänderung,
  fehlende Geometrie, fremde PDF, Reihenfolge/Resume und Teiltexte abgedeckt.
- **Gemessen:** real keine zusätzlichen korrekten Felder/Personen; Paddle
  38/72 exakt, falsch 15 → 19, fehlend 19 → 15. Identische neue Antwort mit/ohne
  geerbte Positionsprüfung: falsch 19/28 bei gleicher Zahl exakter Treffer.
  Synthetisch 4/8 → 8/8 exakte Felder; kein Beleg realer OCR-Verbesserung.
- **Offen / nächster sinnvoller Schritt:** unabhängige regionale Transkripte
  und mehrere reale Entwicklungs-PDFs mit zuverlässig erkannten Überschriften
  ergänzen. Bessere Handschrifterkennung bleibt unbewiesen; keine Werte aus
  der Referenz auffüllen und keine der untersuchten Bildvarianten als Sieger übernehmen.

### 2026-11-03 – OCR-Beobachtung vor Teilnehmerzulassung erhalten

- **Auftrag:** vollständigen OCR-Text unabhängig von Confidence erhalten,
  konkrete Verluste der Folgeseite analysieren und sichtbar von Feldzuordnung trennen.
- **Dateien:** neues `ocr_observations.py`, Erweiterungen in `ocr.py`, `ocr_layout.py`,
  `ocr_evidence.py`, `models.py`, `runner.py`, `report.py`, `structured_mapping.py`,
  `config.py`, `structure_runtime/docling_backend.py`; `configs/benchmark.yaml`
  mit explizitem `ocr_row_selection: pattern`. Neue `tests/test_observation_retention.py`
  und `scripts/check_observation_retention.py`; Software-README, Methoden-/Verifikations-
  dokumentation und neuer `docs/ocr-observation-retention.md` aktualisiert.
- **Implementiert/aktiv:** Docling-Belege vor SDK-Zusammenführung, vollständige
  Beobachtungsansicht mit lokalen JSON-/CSV-Belegen, Ablehnungs-/Zeilenprotokoll,
  Wortbezüge und Score-30-Unsicherheit auch im kompakten OCR-LLM-Protokoll,
  scoreunabhängiger Erhalt bei fehlender/ungültiger Confidence. ID-Teilperson nur
  bei belegter ID-Spalte auch ohne Namen zulässig. Notwendige Literal-/Positions-/
  Rollenprüfungen bleiben bestehen; keine Referenz in der Extraktion.
- **Nachgewiesen:** Seite 2 hatte schon alle 51 Tesseract-Wörter/zehn Zeilen im
  Prompt, nur eine Modellperson und keine spätere Zeilenverwerfung. Docling hatte
  66 Zellen, aber keine sichere Spaltenzuordnung. Vor/nach SDK hier identisch,
  insgesamt unverändert 189 Tesseract-Wörter und 219 Docling-Zellen. Neuer
  vorgelagerter Messpunkt verhindert generelle Überlappungsverluste mit PDF-Text,
  aber kein solcher Verlust auf dieser bildbasierten PDF.
- **Versuch/Entscheidung:** vollständiger Zeileneingang erhöht die Ausgabe auf
  17 statt zehn Personen, senkt aber exakt 25 → 24 und erhöht falsch 12 → 19;
  deshalb `all` optional, `pattern` weiter aktiv. Standardprüfung erhält alle
  bisherigen Treffer (25/72 OCR-LLM, 19/72 Docling), keine neue Qualität behauptet.
- **Prüfungen:** 652 Volltests, 48 API-Tests, zuletzt 107 gezielte Tests;
  Ruff, originale Hashes, unveränderte OCR-Texte, reguläre Promptgleichheit gegen
  vorherigen Commit und konsistente JSON-/CSV-/Excel-/HTML-Zähler geprüft.
- **Offen / nächster Schritt:** unabhängige Handschriftregionen transkribieren
  und weitere reale Entwicklungsdaten ergänzen; danach gezielte Erkennungs-/
  Zuordnungsvarianten messen. Unzugeordnete Rohtexte nie als richtige Felder zählen.

### 2026-11-06 – Extraktionsqualität und feldweise Fehleranalyse

- **Auftrag:** aktuelle Verluste in OCR-LLM/Paddle/Docling untersuchen, belegte
  Verluste beheben und separate filterbare HTML-Analyseseite ergänzen.
- **Dateien:** `structure_assignment.py`, `unlimited_assignment.py` (eindeutige
  aktuelle skalare OCR-Zellen nach gemessener Überschriftenspalte ergänzen,
  aktuelle/geerbte Herkunft und vorherigen Zustand protokollieren, v9/v21/v22);
  `ocr_observations.py` (Paddle-Eingangsbelege und Vorschlagszahlen);
  `roster_benchmark/error_report.py` und `detail_report.py` (automatisch verlinkte
  Analyseseite, JSON, Prüfzähler, lokale Crops, CSP-Hash, sechs Filter);
  `scripts/check_extraction_quality.py`, zwei neue Testmodule,
  `software/testframework/README.md`, `software/docs/extraction-error-analysis.md`
  und diese Übergabe.
- **Ursachen:** Tesseract Seite 2 vollständig übergeben, aber leere LLM-Antwort;
  Docling ohne eindeutige Überschriften und beschädigter nativer Folgetabelle;
  Paddle liest Organisationszellen, Modell lässt Zielfelder leer. Keine
  nachgewiesene Confidence-Löschung in diesen Läufen. Belegablehnungen werden
  separat von OCR-Lesefehlervermutungen und unbekannten Ursachen angezeigt.
- **Getestet / aktiv / nachgewiesen:** räumliche Zellergänzung ist aktiv, alle
  Ergänzungen unsicher markiert; Originaltexte unabhängig von Scores erhalten.
  Replay bei gleichen Antworten und echter lokaler Paddle-Lauf mit zwei neuen
  Antworten liefern dieselben Feldwerte. Zwei neue exakte Organisationsfelder
  auf Seite 2, keine verlorenen Treffer oder geänderten Paarungen. Fünf weitere
  falsche Werte: Recall verbessert, exakter F1 geringfügig schlechter. Kein
  pauschaler Qualitätsgewinn; OCR-LLM und Docling unverändert.
- **Artefakte:** finaler Vorher-/Nachher-Vergleich unter
  `software/runs/extraction-quality-20261106-final/`, nachher
  `after/extraction_errors.html`; `comparison.json` und `qa.json` belegen
  identische Originaldateien, unveränderte Paarungen, Live-/Replay-Gleichheit
  und Übereinstimmung der HTML-Feldfallzahlen mit CSV-/JSON-Metriken.
- **Prüfungen:** 668 lokale Volltests in 48,80 s, 48 API-Tests in 8,07 s,
  41 gezielte Tests in 1,41 s; Ruff ohne Befund. Kombinierte Filter mit Node
  ausgeführt, HTML-Escaping und CSP geprüft. Grafische Sichtabnahme nicht
  möglich (Computer-Use-Node-Laufzeitpfad fehlt), in Dokumentation ausgewiesen.
  Reale Zuordnung 88,29 s ohne erneute OCR; Replay-Nachbearbeitung rund 0,0045 s,
  ausdrücklich keine neue vollständige Pipeline-Laufzeit.
- **Offen / nächster Schritt:** bessere OCR-Handschriftqualität und native
  Spaltenrekonstruktion an unabhängigen Dokumenten untersuchen. Kursreferenzen
  ohne Paarung bleiben ohne erfundene Seitenlokalisierung; für feldgenaue
  Trennung von Nicht-Erkennung/Lesefehler/Zuordnungsfehlern fehlen geprüfte
  Referenzkoordinaten. Historische Läufe, Referenzen und Modellgewichte bleiben
  unverändert; personenbezogene Ergebnisartefakte werden nicht eingecheckt.

### 2026-11-09 – Projektinitialisierung, Umgebungsprüfung und lokale Testframework-Verifikation

- **Auftrag:** Repository-Struktur und lokale Python-Umgebung (`uv`, Python 3.12)
  prüfen, Abhängigkeiten gegen `software/uv.lock` verifizieren,
  `software/start_testframework.cmd` und `software/testframework/main.py`
  analysieren sowie Unit-Tests und lokale Testframework-Durchläufe ohne externe
  Groß-Downloads und ohne Eingriff in `software/api_firmen_pc/` erfolgreich
  ausführen.
- **Dateien:** `software/pyproject.toml`, `software/tests/conftest.py` (neu),
  `software/start_testframework.cmd` sowie `AGENTEN_UEBERGABE.md`.
- **Zweck / Änderungen:**
  - `software/pyproject.toml`: `cache_dir = ".cache/pytest_cache"` unter
    `[tool.pytest.ini_options]` ergänzt, um `PermissionError` auf dem durch
    einen anderen Benutzer gesperrten `.pytest_cache`-Verzeichnis zu vermeiden.
  - `software/tests/conftest.py`: setzt bei Teststart das Arbeitsverzeichnis auf
    `software/` und `basetemp` standardmäßig auf `software/.cache/pytest_tmp`,
    sodass sowohl `pytest -q` aus `software/` als auch `pytest software/tests`
    aus dem Repository-Root ohne `PermissionError` auf `AppData\Local\Temp\pytest-of-Marco`
    und ohne relative Pfadfehler durchlaufen.
  - `software/start_testframework.cmd`: `PYTHONUTF8=1` und
    `PYTHONIOENCODING=utf-8` für konsistente UTF-8-Konsolenausgabe unter Windows
    gesetzt.
- **Implementiert / getestet / aktiv konfiguriert / nachgewiesen:**
  - *Aktiv konfiguriert & verifiziert:* Python 3.12.15 (`software/.venv`),
    `uv 0.13.1`, CUDA (NVIDIA GeForce RTX 4090 Laptop GPU), `uv sync --locked --extra models --offline`
    konsistent (71 Pakete aufgelöst, 55 geprüft).
  - *Getestet:* 668 lokale Unit- und Regressionstests via
    `.\software\.venv\Scripts\python.exe -m pytest software/tests -q` in 59,65 s
    bestanden (0 Fehler, 0 Warnungen); `ruff check` und `git diff --check` ohne
    Befund.
  - *Anhand von Referenz- und Demodaten nachgewiesen:*
    - `start_testframework.cmd --pruefen`: Exit-Code 0 (1 Eingabe-PDF, 170 Referenzzeilen,
      11 Kurse, 1 gemeinsamer Kurs).
    - `testframework/main.py compare` auf `testframework/beispiele/generiert/`:
      Ergebnisordner `software/testframework/ergebnisse/20261109T120211Z-d892972b/`,
      erwarteter Levenshtein-Feld-F1 von 82,69 % (10/11 Referenzfelder exakt) reproduziert.
    - `start_testframework.cmd --input testframework/beispiele/generiert/pdfs --reference testframework/beispiele/generiert/referenz.csv --method ocr_raw --method docling`:
      Extraktionslauf `software/runs/20261109T120214Z-f8f03d48/` und Vergleich
      `software/testframework/ergebnisse/20261109T120326Z-beeb4b0a/` mit Exit-Code 0
      (Docling: Levenshtein-Feld-F1 100,00 %, 11/11 Referenzfelder exakt).
    - `start_testframework.cmd --method ocr_raw` auf Standard-Eingabeordner:
      Extraktionslauf `software/runs/20261109T120944Z-f2d31016/` und Vergleich
      `software/testframework/ergebnisse/20261109T120951Z-0d00bc7a/` mit Exit-Code 0,
      SHA256-Hashes der Eingabe-PDF und Referenzdatei unverändert.
    - Sämtliche Output-Artefakte (`report.html`, `details.html`, `zuordnungen.html`,
      `extraction_errors.html`, `metrics.json`, `identity.json`, `config.json`,
      `reference_snapshot.json`, `participants.xlsx` sowie CSV-Tabellen) vollständig erzeugt.
- **Offen / nächster sinnvoller Schritt:** Testumgebung ist vollständig
  verifiziert und reproduzierbar; als nächster fachlicher Schritt können weitere
  unabhängige Entwicklungsdokumente und manuell geprüfte Seitenreferenzen für die
  Handschrift- und Folgeseiten-Evaluation herangezogen werden.

### 2026-11-10 – Ausbalancierte Pipeline für gemischte Dokumente in `ocr_llm` und `docling`

- **Auftrag:** Vorverarbeitung, Rohdaten-Durchreichung und Tabellenzuordnung für
  `ocr_llm` und `docling` als ausbalancierten Mittelweg für gemischte
  Teilnehmerlisten (Maschinenschrift + Handschrift + kopflose Folgeseiten)
  optimieren, ohne die Definition der sechs Hauptverfahren zu verändern (`docling`
  bleibt ohne LLM), ohne OCR-Rohbeobachtungen zu löschen und ohne Ground Truth in
  der Extraktion zu verwenden.
- **Dateien:**
  - `software/verarbeitung/src/participant_bench/image_preprocessing.py`
  - `software/verarbeitung/src/participant_bench/ocr.py`
  - `software/structure_runtime/docling_backend.py`
  - `software/verarbeitung/src/participant_bench/column_headers.py`
  - `software/verarbeitung/src/participant_bench/unlimited_assignment.py`
  - `software/verarbeitung/src/participant_bench/ocr_layout.py`
  - `software/verarbeitung/src/participant_bench/ocr_evidence.py`
  - `software/verarbeitung/src/participant_bench/models.py`
  - `software/verarbeitung/src/participant_bench/column_context.py`
  - `software/verarbeitung/src/participant_bench/structured_mapping.py`
  - `software/tests/test_handwriting_retention.py`
  - `AGENTEN_UEBERGABE.md`
- **Zweck / Änderungen:**
  - `image_preprocessing.py`: In `remove_grid_lines(image)` vor der Otsu-Binarisierung
    eine lokale Hintergrundschätzung mittels morphologischem Schließen
    (`cv2.MORPH_CLOSE`, Kernel `25×25`) und Division (`cv2.divide`) eingeführt;
    Linienmasken (`40×1` horizontal, `1×40` vertikal) weißen ausschließlich
    erkannte Gitterlinien auf dem hintergrundnormalisierten Graustufenbild.
    Verhindert das bisherige Auslöschen grau hinterlegter Tabellenkopfzeilen und
    erhält schwache Stiftstriche auf Folgeseiten.
  - `ocr.py` & `docling_backend.py`: `file_hash(image_preprocessing.py)` in
    `OCR.identity` aufgenommen; `configure_ocr_images` in `docling_backend.py`
    idempotent gemacht und `cell.rect`-Guard bei der Serialisierung von `ocr_cells`
    ergänzt.
  - `column_headers.py` & `unlimited_assignment.py`: OCR-Varianten `signetur`,
    `benutzemame` und `teilnehmemame` (`rn`→`m`-Ligatur) in der Header-Erkennung
    ergänzt; Wortgrenzen-Regex in `literal()` auf `(?<![^\W_])(?<!['/’–-])...`
    präzisiert, sodass Scan-Randunterstriche (`_`) an Personalnummern/Namen nicht
    scheitern, Bindestrich-Teilwörter (`Groß` in `Groß-Müller`) aber weiterhin
    strikt abgelehnt werden.
  - `ocr_layout.py`, `models.py` & `ocr_evidence.py`: Zweistufiges
    Beobachtungs-/Evidenzmodell für `ocr_llm`: sichere Maschinenschriftzeilen
    behalten `selection_hint="person_pattern"`; niedrigkonfidente oder
    handschriftliche Tabellenzeilen unterhalb der Kopfzeile bleiben im Modus
    `pattern` als `selection_hint="unclassified_observation"` samt
    `min_ocr_confidence` erhalten, während Vor-Tabellen-Metadatenzeilen
    ausgeschlossen werden. `ALL_ROW_INSTRUCTIONS` wird in `models.py` automatisch
    eingebunden, sobald `unclassified_observation`-Zeilen vorliegen.
    Niedrigkonfidente (`ocr_confidence < 30`) oder partielle Belege werden in
    `ocr_evidence.py` als `state="uncertain"` markiert.
  - `column_context.py` & `structured_mapping.py`: `column_intervals` und
    `text_width` im dokumentweiten Spaltenkontext verankert; Kompatibilitätsprüfung
    akzeptiert auf Folgeseiten auch `same_text_column_prefix_geometry` (innerhalb
    `MAX_EDGE_SHIFT = 0.035`), wenn auf der Folgeseite lediglich nachgelagerte
    Signaturspalten fehlen. Zweistufiges `docling`-Mapping in `structured_mapping.py`
    ergänzt leere/nicht zugeordnete Felder bestehender Zeilen (Stufe 2a) sowie
    verwaiste `ocr_cells`-Zeilen unterhalb der TableFormer-Tabelle (Stufe 2b)
    anhand der fixierten Spalten-X-Intervalle als `state="uncertain"`.
- **Implementiert / getestet / aktiv konfiguriert / nachgewiesen:**
  - *Implementiert & aktiv konfiguriert:* Alle genannten Änderungen sind im
    Standardprofil (`software/configs/benchmark.yaml` und
    `software/testframework/config.yaml`) aktiv; `docling` nutzt weiterhin kein LLM.
  - *Getestet:* 192 gezielte Tests in den 7 Kern-Testmodulen (`2,21 s`) sowie alle
    670 lokalen Unit- und Regressionstests (`pytest software/tests`, inkl. 2 neuer
    synthetischer Tests in `test_handwriting_retention.py` für graue Kopfzeilen und
    gemischte Seiten mit kopfloser Folgeseite) bestanden; `ruff check` ohne Befund.
  - *Anhand von Referenzdaten nachgewiesen:* Validierungslauf
    `software/runs/20261110T083413Z-10042efe/` und Auswertung
    `software/runs/validation_balanced_pipeline/20261110T083532Z-dbdf20c4/`
    gegenüber Baseline `20261106T080030Z-f1e4fa77/` auf Dokument `140829`
    (18 Referenzteilnehmer, 72 Referenzfelder):
    - `ocr_llm`: `predicted_participants` `9 → 17` (`missing_participants` `9 → 1`,
      `extra_participants` `0`), `exact_fields` `25/72 (34,72 %) → 29/72 (40,28 %)`,
      `missing_fields` `47 → 24`, `extra_fields` `0`, `field_coverage` `34,72 % → 66,67 %`,
      `soft_f1` (Best-Fit) `53,15 % → 64,85 %`, `soft_f1` (konservativ) `53,15 % → 56,48 %`.
    - `docling`: `predicted_participants` `8 → 16` (`missing_participants` `10 → 2`,
      `extra_participants` `0`), `exact_fields` `22/72 (30,56 %) → 28/72 (38,89 %)`,
      `missing_fields` `48 → 17`, `extra_fields` `0`, `field_coverage` `33,33 % → 76,39 %`,
      `soft_f1` (Best-Fit) `45,83 % → 65,19 %`, `soft_f1` (konservativ) `45,83 % → 55,43 %`.
    - Verlustfreie Beobachtungsbilanz (`ocr_observations.audit`): 0 verworfene
      SDK-Zellen, alle Rohbeobachtungen auf Seite 1 (`172` bzw. `155`) und Seite 2
      (`78` statt zuvor `51` bzw. `64`) vollständig im Ledger erhalten.
- **Offen / nächster sinnvoller Schritt:** Die verbleibenden Abweichungen auf
  Seite 2 resultieren primär aus der reinen Zeichenerkennungsqualität (Tesseract-OCR)
  bei stark kursiver Handschrift; als nächster Schritt empfiehlt sich die Prüfung
  auf weiteren mehrseitigen Dokumenten des Korpus sowie der Vergleich mit den
  visuellen Verfahren (`vlm`, `ocr_vlm`) und `paddle_llm`.

### 2026-11-10 — Zeilenindividuelle Vorname-/Nachname-Erkennung bei fehlenden Spaltenüberschriften und wechselnder Eintragungsreihenfolge

- **Auftrag:** Untersuchung und Optimierung der zeilenindividuellen
  Vorname-/Nachname-Aufteilung und -Zuordnung (`name_parts.py`, `document_names.py`,
  `structured_mapping.py`, `table_mapping.py`, `models.py`,
  `unlimited_assignment.py`, `roster_benchmark/error_report.py`), sodass bei fehlenden
  Spaltenüberschriften und zeilenweise wechselnder Eintragungsreihenfolge
  (`"Vorname Nachname"`, `"Nachname Vorname"`, `"Nachname, Vorname"`) jede Zeile
  individuell entschieden wird und die Spaltenorientierung ausschließlich als
  Tie-Breaker bei echten Mehrdeutigkeiten (`"Thomas Martin"`) dient, ohne `docling`
  oder `ocr_raw` um ein LLM zu erweitern.
- **Geänderte Dateien:**
  - `software/verarbeitung/src/participant_bench/name_parts.py`
  - `software/verarbeitung/src/participant_bench/document_names.py`
  - `software/verarbeitung/src/participant_bench/structured_mapping.py`
  - `software/verarbeitung/src/participant_bench/table_mapping.py`
  - `software/verarbeitung/src/participant_bench/models.py`
  - `software/verarbeitung/src/participant_bench/unlimited_assignment.py`
  - `software/verarbeitung/src/participant_bench/roster_benchmark/error_report.py`
  - `software/tests/test_document_names.py`
  - `software/tests/test_extraction_errors.py`
  - `AGENTEN_UEBERGABE.md`
- **Zweck / Änderungen:**
  - `name_parts.py`: Deterministische Token- und Paarklassifikation
    (`classify_name_token`, `classify_name_pair`, `has_surname_prefix`) für deutsche
    und internationale Vor-/Nachnamen, Adels-/Namenspartikeln (`SURNAME_PARTICLES`,
    `MULTIWORD_SURNAME_PREFIXES`) und morphologische Nachnamensuffixe
    (`SURNAME_SUFFIXES`) ergänzt. `split_combined_name` priorisiert explizite Kommas
    (`explicit_surname_comma_given_name`) und eindeutige zeilenindividuelle Evidenz
    (`lexical_given_family`, `lexical_family_given`) vor `default_order`. Neue
    Hilfsfunktion `infer_column_tiebreaker` berechnet die Mehrheitsorientierung einer
    Spalte ausschließlich aus eindeutig klassifizierten Zeilen als Tie-Breaker für
    mehrdeutige Zeilen (z. B. zwei Vornamen wie `"Thomas Martin"`).
  - `document_names.py`: In `DocumentNameOrders.prepare_assignment` und
    `DocumentNameOrders.apply` hat eindeutige zeilenindividuelle Evidenz Vorrang vor
    `selected.order`, sodass korrekte Einzelzeilen in gemischten Tabellen nicht mehr
    durch einen globalen Spalten-Swap invertiert werden. Mehrdeutige Zeilen nutzen
    `_assignment_tiebreaker` bzw. `_page_tiebreaker`. `INSTRUCTIONS` und
    `infer_text_order` weisen die bestehenden LLM-/VLM-Verfahren an, jede Zeile
    individuell auf Vor-/Nachname zu prüfen und die Dokumentorientierung als
    Tie-Breaker zu nutzen.
  - `structured_mapping.py` & `table_mapping.py`: Übergabe des spaltenweiten
    Tie-Breakers an `split_combined_name`, Korrektur zeilenindividuell vertauschter
    Einträge in getrennten Vor-/Nachnamenspalten sowie Erweiterung von
    `partial_identity_fallback` (inkl. `_two_column_headerless_fallback`) für kopflose
    Tabellen mit einer kombinierten oder zwei getrennten unbenannten Namensspalten.
  - `models.py` & `unlimited_assignment.py`: Präzisierung der Systemprompts für
    `ocr_llm`, `paddle_llm`, `vlm` und `ocr_vlm` für zeilenweise wechselnde
    Namensreihenfolgen.
  - `roster_benchmark/error_report.py`: Neue Fehlerkategorie `name_swap`
    (`"Vor-/Nachname-Vertauschung (Swap)"`) in `CATEGORIES` und `diagnose_field`
    sowie explizites Flag `name_swapped` zur transparenten Trennung zwischen
    striktem ungeswapptem Feld-Recall und Swap-Toleranz.
- **Implementiert / getestet / aktiv konfiguriert / nachgewiesen:**
  - *Implementiert & aktiv konfiguriert:* Alle Änderungen sind im Standardprofil aktiv;
    `docling` und `ocr_raw` bleiben vollständig ohne LLM, und es erfolgt keinerlei
    Zugriff auf Ground-Truth-Daten während der Extraktion.
  - *Getestet:* Gezielte Suite (`pytest software/tests/test_document_names.py software/tests/test_document_columns.py software/tests/test_evaluation.py software/tests/test_extraction_errors.py`:
    `71 passed`), Gesamttestsuite (`pytest software/tests`: `673 passed`) sowie
    `ruff check` ohne Befund bestanden.
  - *Anhand von Referenzdaten nachgewiesen:* Auf dem gecachten Referenzlauf zu
    Dokument `140829` (`software/runs/20261103T084429Z-e2834b34/docling` gegen
    `reference_snapshot.json`) sinkt `name_swapped_participants` für `docling` von `6`
    auf `0`; die exakten Felder ohne Swap-Toleranz (`compare_name_orientations=False`)
    steigen auf diesem Dokument von `7` auf `15` (bzw. über alle 72 Referenzfelder
    von `20/72` auf `28/72`).
- **Offen / nächster sinnvoller Schritt:** Seltene Namen, bei denen weder Vor- noch
  Nachname lexikalisch/morphologisch bekannt ist und kein Komma vorliegt, folgen
  weiterhin dem Spalten-Tie-Breaker bzw. bei den vier LLM-/VLM-Verfahren der
  semantischen Modellentscheidung; als nächster Schritt empfiehlt sich ein
  End-to-End-Benchmarklauf über alle sechs Verfahren auf dem Gesamtkorpus.

### 2026-11-10 – Konzeption und Implementierung einer optionalen Docling-VLM-Hybridstufe (`docling-vlm`)

- **Auftrag:** Untersuchung und Implementierung einer optional zuschaltbaren
  Kombination aus `docling` (TableFormer + Spaltenkontext) und dem lokalen VLM
  (`Qwen/Qwen3-VL-4B-Instruct`) für handschriftliche Einträge und die
  Vorname-/Nachname-Zuordnung unter strikter Beibehaltung der LLM-/VLM-freien
  `docling`-Baseline in `software/configs/benchmark.yaml`.
- **Geänderte Dateien:**
  - `software/verarbeitung/src/participant_bench/config.py`
  - `software/verarbeitung/src/participant_bench/structure.py`
  - `software/verarbeitung/src/participant_bench/hybrid.py`
  - `software/verarbeitung/src/participant_bench/structured_mapping.py`
  - `software/verarbeitung/src/participant_bench/table_mapping.py`
  - `software/verarbeitung/src/participant_bench/runner.py`
  - `software/verarbeitung/src/participant_bench/report.py`
  - `software/verarbeitung/src/participant_bench/roster_benchmark/error_report.py`
  - `software/configs/docling-vlm.yaml` (neu)
  - `software/tests/test_unified_pipelines.py`
  - `AGENTEN_UEBERGABE.md`
- **Zweck / Änderungen:**
  - `config.py`, `structure.py` & `software/configs/docling-vlm.yaml`: Explizite
    Opt-in-Option `vlm_assist: bool = False` in `StructureConfig` ergänzt, im
    Hauptvergleich (`main_comparison: true`) strikt gesperrt, vom
    TableFormer-Erkennungs-Cache-Schlüssel (`recognition_key`) entkoppelt und im
    separaten Ablationsprofil `software/configs/docling-vlm.yaml` aktiviert.
  - `hybrid.py` & `runner.py`: Funktionen `serialize_docling_hints`,
    `needs_docling_vlm_assist`, `merge_docling_vlm_participants` und
    `assist_docling_pages` implementiert. Nach dem Entladen des `docling`-Workers wird
    `Qwen/Qwen3-VL-4B-Instruct` nur für Seiten mit unvollständigen/unsicheren Feldern,
    Handschrift-Folgeseiten oder nicht zugeordneten Tabellenzeilen aufgerufen; saubere
    Druckseiten (`all_docling_rows_complete_and_read`) werden ohne VLM-Aufruf
    übersprungen. Verankerte gedruckte `docling`-Felder bleiben mit
    `provenance="docling"` erhalten, während unsichere/fehlende/handschriftliche Felder
    mit `provenance="docling_vlm_assist"` und Dokumentation von
    `original_docling_value` ergänzt werden.
  - `structured_mapping.py`, `table_mapping.py`, `report.py` &
    `roster_benchmark/error_report.py`: Durchgängige Provenance-Kennzeichnung
    (`provenance="docling"` vs. `"docling_vlm_assist"`) in `row_evidence`,
    `diagnose_field`, `error_analysis/fields.json` und `extraction_errors.html` sowie
    separate Ausweisung von `vlm_assist_seconds`, `vlm_assist_model` und
    `deterministic_headers_vlm_assist` in `resources.json`, `summary.json` und
    `report.html`.
  - `software/tests/test_unified_pipelines.py`: Zwei neue Unit-Tests
    (`test_docling_standard_profile_never_invokes_vlm_and_main_protocol_rejects_vlm_assist`
    und `test_docling_vlm_assist_merges_incomplete_and_handwritten_rows_with_provenance`)
    ergänzt.
- **Implementiert / getestet / aktiv konfiguriert / nachgewiesen:**
  - *Implementiert & aktiv konfiguriert:* Im Hauptprofil `software/configs/benchmark.yaml`
    und in `software/configs/docling.yaml` bleibt `vlm_assist: false` (100 % LLM-/VLM-frei);
    im neuen Profil `software/configs/docling-vlm.yaml` ist `vlm_assist: true` aktiv
    konfiguriert.
  - *Getestet:* Gezielte Testsuite (`pytest software/tests/test_vlm_cells.py software/tests/test_structure_methods.py software/tests/test_unified_pipelines.py software/tests/test_local_isolation.py`:
    `70 passed`), Gesamttestsuite (`pytest software/tests`: `675 passed in 64.83s`)
    sowie `ruff check` ohne Befund bestanden.
  - *Anhand von Referenzdaten nachgewiesen:*
    - **Live-Testframework-Lauf (`software/runs/20261110T111644Z-aa89a376`, Auswertung `software/testframework/ergebnisse/20261110T111751Z-9b5da18c/`):**
      Auf `140829.pdf` steigt der Levenshtein-Feld-F1 live von `65,19 %` (`docling` ohne VLM) auf **`77,77 %` (`+12,58 pp`)**, die exakten Felder steigen von `28/72` auf **`35/72`** (strikt ohne Swap-Toleranz von `22/72` auf **`28/72`**), alle **`18/18` Teilnehmer** werden zugeordnet (`0` fehlend, `0` überzählig) und die Namensdreher sinken von `6` auf **`1`** bei `62,3 s` Gesamtlaufzeit (`0` VLM-Aufrufe auf Seite 1, `1` VLM-Aufruf auf Seite 2).
    - **Replay auf gecachten Artefakten (`20261110T085608Z-d06794be` + `20261110T100955Z-3cb60325`):**
      Steigerung der exakten Felder von `28/72 (38,89 %)` auf `41/72 (56,94 %)` (bzw. strikt ohne Swap-Toleranz von `22/72` auf `34/72`) und des Best-Fit-Scores von `65,19 %` auf `82,76 %`.
- **Offen / nächster sinnvoller Schritt:** Optionales Einbinden des `docling-vlm`-Profils in `software/start_testframework.cmd` (falls der Nutzer den Ablationslauf bei jedem Standard-Start automatisch mit ausführen möchte) oder Ablationslauf über alle 6 PDFs in `daten/listen/`.

### 2026-11-10 – Wissenschaftliche Evaluation im bestehenden Bericht erweitert

- **Auftrag:** Aktuelles Framework anhand Code und gespeicherter Ergebnisse
  prüfen und um Dokumentmerkmale, strikte/assistierte Bewertungen, Unsicherheit,
  Fehlerstufen, Hybridbeiträge und Effizienz erweitern; keine neuen Modelle.
- **Geänderte Dateien:** Neu `software/verarbeitung/src/participant_bench/
  roster_benchmark/scientific.py`, `scientific_metadata.py`, `scientific_stats.py`,
  `scientific_report.py`; erweitert `roster_benchmark/{cli,evaluation,references,
  error_report}.py` und gemeinsame Snapshotnutzung in `selection.py`. Neu
  `software/tests/test_scientific_evaluation.py`, erweitert
  `tests/test_extraction_errors.py`. Dokumentation: `software/docs/scientific-evaluation.md`,
  `software/README.md`, `software/testframework/README.md`,
  `bachelorarbeit/chapters/03_methodik.tex`, `verified_sources.bib`,
  Bachelorarbeits-README/BUILDSTATUS und diese Übergabe. Frühere Änderungen anderer
  Aufträge erhalten, keine Extraktionsprofile verändert.
- **Zweck / implementiert:** Fünf Ansichten derselben Extraktionen mit bestehenden
  Metrikfunktionen, CSV-Metadaten mit Phasen-/Gruppenkontrollen, Clusterbootstrap
  aus Rohzählern und gepaarten Gruppen, Feld-/Schulungs-/Merkmalsansichten,
  HTML-Integration samt PNG/SVG, vorhandene Fehleranalyse mit Evidenzaggregation
  und zusätzlichen Filtern; drei Pipelinevergleiche und beobachtete Cache-/Zeit-/
  Ressourcen-/Paretoansichten. Fehlende Merkmale/Werte werden nicht geschätzt.
  Snapshotprüfung gemeinsam genutzt; neue Snapshots/Konfigurationen gehasht.
- **Aktiv konfiguriert:** Neue reguläre Vergleiche rendern die Analyse automatisch.
  Separate `metadata-template`-/`analyze`-CLI für gespeicherte Artefakte. Aktive
  Nutzerwahl bleibt das Fünferprofil; Docling/Assist stammen hier ausschließlich
  aus gespeicherten Vergleichsberichten. Auswahl-Teilberichte deaktivieren nur
  die sonst verschachtelte automatische Zusatzanalyse.
- **Getestet:** 23 neue Tests für gepooltes F1, identisches gepaartes Resampling,
  Prozentpunkte, Nullnenner, kleine/ungeprüfte Stichproben, reproduzierbare Seeds,
  Phasentrennung, Maskierung, fehlende Ergebnisse, fehlende Kandidaten, unveränderte
  Quellen und Referenzreplay ohne aktuelle CSV. Filtertest mit Node um Dokument/
  Stufe erweitert. Zwei in der ersten Gesamtprüfung gefundene Legacy-Fälle
  (unvollständige Manifeste und mehrdeutige Dokumentzuordnung) behoben; abschließend
  **716/716 lokale Tests in 72,78 s**, **48/48 API-Tests in 11,34 s**, Ruff und
  `git diff --check` bestanden. LaTeX/BibTeX Exitcode 0, 32 Seiten, ergänzte Seiten
  visuell geprüft; keine LaTeX-Warnungen oder übervollen Boxen. Genehmigter lokaler
  TinyTeX-Build außerhalb der Sandbox, keine Downloads.
- **An Referenzdaten nachgewiesen:** Neue lokale Auswertung
  `software/testframework/ergebnisse/scientific-20261110-v2/` aus den oben genannten
  drei Originalberichten, keine neue Inferenz. Eine Entwicklungsgruppe, 72
  Referenzfelder; Originalrollen VLM 38, OCR-VLM 42, Docling 28, Assist 35,
  OCR-LLM 29, Paddle-LLM 40 exakte Felder. OCR-VLM toleriert 43: ein reiner
  Bewertungstreffer. Neun Korrekturen/fünf Regressionen beim OCR-Hybrid, sieben/
  null beim Assist, 13/zwei beim OCR-Pipelinevergleich. 35 Ansichten und 140
  Feldsummenzeilen konsistent, 38 lokale Links gültig, 863 Originaldateien
  unverändert. Statistische Intervalle korrekt als unbestimmbar markiert.
- **Offen / nächster Schritt:** Unabhängiges Inventar/Klassifikation und genügend
  unabhängige Pilot-/Testgruppen; lokalisierte Transkripte, kontrollierte
  Laufzeitmessungen und tatsächliche Prozess-/Kostenmessungen. Historische
  Legacy-Hashes und manuelle Gruppierung begrenzen den nachträglichen Nachweis;
  keine Kausalitäts-, Signifikanz- oder allgemeine Qualitätsrangfolge ableiten.


### 2026-11-11 ? Einmalige wissenschaftlich begr?ndete ?berarbeitung der Extraktionsprompts

- **Auftrag:** Gepr?fte Literatur ausw?hlen und eine finale, reproduzierbare
  Promptfamilie pro notwendiger Schnittstelle implementieren; ausdr?cklich keine
  Optimierungsstudie, neue Modelle oder unn?tigen Abh?ngigkeiten.
- **Dateien:** neu `software/verarbeitung/src/participant_bench/extraction_prompts.py`,
  `software/tests/test_extraction_prompts.py`, `software/docs/prompt-design.md`,
  `software/docs/prompt-history/pre-20261111.json`. Angepasst: `models.py`,
  `unlimited_assignment.py`, `document_names.py`, `person_roles.py`, `hybrid.py`,
  `runner.py`, `unlimited_reassign.py`, `selection_sample.py`, bestehende Namens-/
  Textzuordnungstestfixtures sowie Software-, Verarbeitungs- und Framework-README.
  Methodik 3.6, `verified_sources.bib`, Bachelorarbeits-README/BUILDSTATUS und ?bergabe
  erg?nzt. Andere uncommittete ?nderungen fr?herer Auftr?ge nicht zur?ckgesetzt.
- **Implementiert / aktiv:** sechs klar getrennte Instruktionsabschnitte, gemeinsame
  semantische Regeln und feste Belegadapter. Benutzer/Benutzername/Kurzzeichen,
  vollst?ndige Personenzeilen, unbekannte/leere Felder und Fortsetzungen erhalten.
  Textmodelle bleiben an aktuelle OCR-Zeilen gebunden; der visuelle Hybrid pr?ft
  Zusatzbelege am Originalbild. Neue Basis-Pflicht im Generierungsschema mit
  konservativer Behandlung unvollst?ndiger neuer Antworten, historische Parser
  kompatibel. Acht kompilierte Systemvertr?ge im gemeinsamen Snapshot bilden
  vorhandene Schnittstellen ab und sind keine experimentellen Kandidaten.
- **Literaturbasis / Zweck:** Prompt Report und Halluzinations?bersicht, GoLLIE,
  InstructUIE und Geng et al. anhand Originalquellen gepr?ft. In der Regelmatrix
  zwischen Forschungsergebnissen, technischen Vertr?gen und eigenen Entscheidungen
  unterschieden. Insbesondere keine Fine-Tuning-Erfolge oder harte Formatgarantie
  f?r unsere unver?ndert eingesetzten Modelle behauptet; keine Grammardecodierung
  neu implementiert. Alte Texte/Schemas gehasht archiviert, neue Lauf- und konkrete
  Aufruftexte mit vollst?ndigem System-/Benutzer-/Schemahash protokolliert.
- **Pr?fungen:** gezielte Regression zun?chst 144 bestanden; nach dem Basis-Guard
  drei neue Mock-Antworten auf den expliziten Vertrag aktualisiert, historische F?lle
  erhalten. Abschlie?end **728/728 lokale Tests (81,63 s)** und **48/48 API-Tests
  (11,55 s)** bestanden, Ruff und regul?res `git diff --check` ohne Befund.
  LaTeX/BibTeX erfolgreich (34 Seiten), neue Methodikseiten visuell gepr?ft,
  keine LaTeX-Warnungen/fehlenden Zitate oder ?bervollen Boxen. Bereits genehmigte
  lokale TinyTeX-Ausf?hrung au?erhalb der Sandbox, keine Downloads.
- **Begrenzter realer Funktionsnachweis:** bestehende synthetische Ein-Seiten-PDF,
  zwei Personen, vier neuronale Pfade, genau eine finale Familie offline ausgef?hrt.
  Quelllauf `20261111T075852Z-c0b6b30b`, regul?rer Vergleich
  `software/data/prompt-revision-20261111/reports/20261111T080047Z-a8f88de0/`.
  Alle vier Pfade g?ltiges JSON mit zwei Personen und 7/7 bewertbaren Feldern exakt;
  Paddle-LLM und OCR-VLM mit Pr?fhinweisen weiterhin partiell. Vier konkrete
  Extraktionsaufrufe plus vorhandene Namensschritte gehasht gepr?ft. 30 gesch?tzte
  Profile/Historienartefakte unver?ndert, keine Neuauswertung finaler Daten.
  Zusammenfassungsskript nach einem KeyError aus gespeicherten Ergebnissen
  korrigiert, keine erneute Modellinferenz. Nachweis `functional.json` unter
  `software/data/prompt-revision-20261111/`.
- **Offen / n?chster Schritt:** gew?hlte Prompts samt Profil, Schema und Code vor
  Pilot/Finaltest einfrieren. Die gedruckte Funktionsliste ist kein Nachweis f?r
  reale Handschrift/gemischte Dokumente, keine Qualit?tssteigerung und kein
  empirisches Optimum. Keine zus?tzliche Varianten-/Suchumgebung erstellt.

### 2026-11-11: Wissenschaftliches Dashboard und additive Teilnehmer-/Effizienzmetriken

- **Auftrag:** bestehenden Modellvergleich wissenschaftlich korrekt in sechs
  HTML-Bereiche gliedern, fehlende Metriken ergänzen, vorhandene Läufe ohne neue
  Inferenz prüfen und Methodik/Softwaredokumentation aktualisieren.
- **Dateien:** neu `roster_benchmark/dashboard_report.py`,
  `roster_benchmark/scientific_efficiency.py` und `tests/test_dashboard_metrics.py`.
  Gezielt angepasst: `roster_benchmark/metrics.py`, `scientific.py`,
  `scientific_report.py`, `error_report.py` und `tests/test_scientific_evaluation.py`.
  Dokumentation: `software/docs/scientific-evaluation.md`, Software-/Framework-
  README, `bachelorarbeit/chapters/03_methodik.tex`, `verified_sources.bib`,
  Bachelorarbeits-README/BUILDSTATUS und diese Übergabe. Bereits vorhandene
  uncommittete Änderungen anderer Aufträge erhalten; keine Modell-/Prompt-/
  Profiländerung und keine zusätzliche Abhängigkeit in diesem Schritt.
- **Zweck / fachliche Entscheidungen:** vollständige Vierfeldreferenzen getrennt
  von Teilreferenzen bewerten; Identität verlangt eindeutigen Referenzanker und
  sämtliche bestimmbaren Identitätsfelder exakt. Nicht allein Best-Fit-Paarzahlen
  zählen. Historische `fully_exact_participants` behalten ihre bisherige Bedeutung.
  Neue Werte micro-aggregiert und mit Definitionen zentral für HTML/CSV/JSON.
  Exakte und weiche Feldmetriken unverändert; Originalrollen nun sichtbar primär,
  alter Standardbericht verlinkt erhalten. Fälle und konservative Ursachen ohne
  Doppelzählung aus denselben Feldentscheidungen, Seitenereignisse separat.
- **Effizienz:** vorhandene Seitenzeiten mit Median/Quartilen und tatsächliche,
  konsistente Aufrufzähler je Seite/PDF; Namenshilfsschritte enthalten, Warm-up
  separat. Fehlende oder gemischte Zähler offen. Kein belegtes Euro-Messartefakt;
  Konfigurationsflag ersetzt keinen Nachweis. Bestehende vollständige Szenarien
  getrennt mit beobachteten Seiten/PDF auf 1.000 Dokumente umgerechnet.
- **Wissenschaftliche Grundlage:** Sokolova/Lapalme 2009 (verifizierter Verlag,
  Metadaten/Abstract) motiviert mehrere Qualitätsdimensionen; Field/Welsh 2007
  (Volltext/Verlagsmetadaten) zu modellabhängigen Bootstrapeigenschaften.
  Konkrete Teilnehmer-/Referenzregeln als eigene Entscheidungen gekennzeichnet.
  Kein allgemeiner Gültigkeits-, Qualitätssteigerungs- oder Kausalitätsnachweis.
  Zotero-Export nicht verändert.
- **Prüfungen / Ergebnis:** 13 neue sinnvolle Metrik-/Provenienz-/Dashboardtests.
  Gesamte lokale Suite 741 bestanden (73,11 s), API-Suite 48 bestanden (10,73 s),
  nach Abschluss der Darstellung 94 gezielte Nachtests bestanden (11,07 s).
  Node führt tatsächlichen Dashboardcode für Tabs, beide Sortierrichtungen mit
  fehlenden Werten, kombinierte Filter und Merkmalswechsel aus. Ruff und
  `git diff --check` ohne Befund. LaTeX/BibTeX erfolgreich, 36 Seiten, ergänzte
  Methodikseiten gerendert und visuell geprüft; keine fehlenden Zitate/Boxüberläufe,
  bekannter epstopdf-Hinweis bleibt. Genehmigter lokaler TinyTeX-Build, keine Downloads.
- **Begrenzter Datenbeleg:** neue Ausgaben
  `software/testframework/ergebnisse/dashboard-20261111-v1/report.html` und
  `software/data/dashboard-20261111/synthetic/report.html`, jeweils ausschließlich
  gespeicherte Entwicklungsergebnisse. Fünf Verfahren im realen Fall, vier im
  synthetischen Fall; unterschiedliche Promptstände getrennt gehalten. Keine neue
  Inferenz und keine Übertragung an externe Dienste. CSV/JSON stimmen überein,
  CSP-Skripthashes und 89 Links geprüft. 4.119 numerische Werte der bisherigen
  Standardbewertung und 863 geschützte historische Dateien unverändert. Nachweis
  unter `software/data/dashboard-20261111/validation.json`; lokale Personen-/
  Fehlerfallexporte bleiben in ignorierten Ergebnisordnern.
- **Offen / nächster sinnvoller Schritt:** HTML visuell lokal prüfen; Browser-
  Computersteuerung endet hier wegen fehlender Unterstützung des Windows-Browsers,
  automatisierte Skriptprüfung ist keine visuelle Browserabnahme. Jeweils nur eine
  unabhängige Gruppe: keine belastbaren Intervalle oder allgemeine Rangfolge.
  Empirische Kosten und lokalisierte unabhängige Handschrifttranskripte fehlen.
  Teilnehmermetriken ohne eigene CIs, unklare Identitätsanker separat ausgeschlossen,
  Paarung weiterhin referenzgestützt. Vor der unabhängigen Studie gemeinsame
  Metadaten/Gruppen/Vorbenutzung prüfen und Code/Profile/Prompts einfrieren.

### 2026-11-11: Ursachenprüfung fehlender ID-/Organisationsfelder und gezielte Korrekturen

- **Auftrag / Vorgehen:** aktuellen Stand und neue Nutzerergebnisse lesen,
  Feldverluste vor Änderungen anhand Original-/Laufbildern, OCR-Ledgern,
  tatsächlichen Eingaben, Antworten und Validierungsständen untersuchen;
  nur belegte technische Fehler korrigieren. Ursachenanalyse und Reproduktion
  von Headerrollen/None-Geometrie erfolgten vor den Implementierungsänderungen.
- **Umfang / Daten:** Lauf `20261111T091101Z-59c4b71d`, Vergleich
  `20261111T110330Z-09f5d83e`, zehn PDFs/zwanzig Seiten/fünf Verfahren,
  155 Kursreferenzpersonen/620 Felder je Methode. Docling separat anhand des
  historischen Vergleichs `20261110T123112Z-b454d615`, kein Docling-Lauf über
  die neuen zehn PDFs. Alle zur Diagnose gesichteten Dokumente sind künftig
  als zur Entwicklung vorbenutzt zu berücksichtigen.
- **Belegte Ursachen / Grenzen:** zwölf gemeinsame Laufbilder seitlich;
  OSD neunzehnmal unsicher, sieben Fehler, eine sichere Entscheidung.
  Fehlende englische User-Rolle verliert ID-Zellen im deterministischen VLM-
  Zuordnungsschritt. Falsche Metadaten-/Datenheader und ungleiche Zellzahlen
  blockieren weitere Felder; neun Seitenantworten am 8.192-Tokenlimit.
  29 untersuchte ID-/Organisationsablehnungen stimmen nicht mit der Referenz
  überein: kein Nachweis korrekt gelesener Referenzwerte, die unberechtigt
  gelöscht würden. Ein Formular besitzt keine ID-/Organisationsspalten.
  Die Regelbaseline liefert mangels passender Vorlagenzuordnung keine Personen;
  dies ist kein Beweis vollständig fehlender OCR. None-Geometrie-Absturz im
  Code reproduziert, aber keinem historischen Feldfehler kausal zugeordnet.
- **Implementiert / Dateien:** `unlimited_tables.py` und
  `unlimited_assignment.py` um exakte englische Rollen ergänzt;
  `column_context.py` gegen gespeicherte None-Geometrie abgesichert;
  `vlm_cells.py`, `models.py`, `runner.py` für sicheren per-PDF-VLM-Kontext
  einschließlich Resume, ohne Teilnehmerwerte und ohne ungemessene Geometrie.
  `pdf.py` protokolliert OSD-Vorschlag/Schwelle/Entscheidung getrennt.
  `roster_benchmark/cli.py` und `runner.py` reichen optional `--manifest`
  an vorhandenen Extraktor weiter. Automatische Rotationsschwelle, fünf
  Verfahren, Modelle und YAML-Profile bleiben unverändert.
- **Promptvertrag:** `extraction_prompts.py` und `schema.py` präzisieren die
  Teilnehmertabelle gegenüber Kursmetadatentabellen, Datenzeilen und Fußzeilen.
  Neue Familie v26-roster-header-scope; Feldtypen und Schnittstellen gleich.
  Vorherige v25 in `docs/prompt-history/pre-field-loss-20261111.json` archiviert;
  kompilierte Hashes stimmen mit dem geschützten tatsächlichen Nutzerlauf überein.
  Keine Promptvariantenstudie und kein empirischer Verbesserungsnachweis.
- **Reporting:** neues `roster_benchmark/pipeline_trace.py`, gezielte Erweiterung
  von `error_report.py`. Anzeige Original-PDF/Ausrichtung/Laufbildhash/Kontext,
  exakter Modellinputs und Hashes sowie Feldketten mit Rohzellen und gespeicherten
  Vor-/Nach-Validierungswerten. Historische Zuordnungswarnungen bleiben maßgeblich;
  Rollenfilterindizes berücksichtigt, fehlende Daten nicht ergänzt. Unbekannte
  Übergaben nicht als gemessen dargestellt; ganze belegte Quellzeile statt nur
  Namensbox bei fehlenden Feldern. Deterministische Mapper explizit ohne LLM.
  Tokenabbrüche als getrennte Seitenereignisse, Feldfehler nicht doppelt gezählt.
- **Dokumentation:** neu `software/docs/field-loss-20261111.md`; Links/Standhinweise
  in `extraction-error-analysis.md`, `prompt-design.md`, Software-/Framework-README.
  Diese Übergabe aktualisiert; Bachelorarbeitstexte/PDF nicht geändert.
- **Tests:** neu `tests/test_field_pipeline_trace.py` mit 31 Regressionen;
  bestehender HTML-Integrationstest in `test_extraction_errors.py` erweitert.
  Abschließend **772 lokale Tests bestanden (77,06 s)**,
  **48 API-Tests bestanden (9,85 s)**, Ruff und normales `git diff --check`
  ohne Befund. Zwischenprüfungen 72/119 gezielte sowie 769/771 Gesamttests
  bestanden; abschließender Stand enthält zusätzlich die robuste Behandlung
  unbekannter Übergaben. Keine neuen Abhängigkeiten.
- **Artefaktprüfung:** neue Fehlerberichte unter
  `software/testframework/ergebnisse/field-loss-20261111-v2/` und
  `software/data/field-loss-20261111/docling-report-v2/`, acht einzelne Feldfälle
  als lokales `cases.json`/`cases.csv`. 1.762 historische Dateien unverändert,
  zehn Original-PDF-Hashes bestätigt, 4.434 alte numerische Standardwerte identisch.
  Hundert Bildhashprüfungen bestätigen zwanzig gemeinsame Seitenbilder;
  2.388 lokale Links/Anker geprüft. Reines Neuparsen zweier englischer Rohantworten
  erhält 18 wörtliche IDs einschließlich Nullen; keine Neuberechnung historischer
  Extraktionen als vermeintlich neuer Modelllauf. Ein zunächst zu eng gewählter
  Docling-Fallexport (keine lokalisierte fehlende Organisation vorhanden) wurde
  aus gespeicherten Daten auf einen vorhandenen ID-Fall korrigiert.
- **Ausrichtung:** 24 CPU-OSD-Proben, davon vier synthetische Rotationen korrekt;
  reale OSD-Grenzen unverändert bestätigt. Geprüftes `curated-manifest.json`
  für genau diese zehn PDFs, zwölf zusätzliche manuelle Seitendrehungen,
  Eingabe-/Bildhash-/Konfigurationsprüfung bestanden. Korrigierte Kontaktansicht
  visuell geprüft; originale Dateien bleiben erhalten. Keine neue LLM-/VLM-
  Inferenz, keine externe Übertragung personenbezogener Daten. Aggregierter
  Nachweis `software/data/field-loss-20261111/validation.json`.
- **Offen / nächster sinnvoller Schritt:** optional den bestehenden Fünferstarter
  mit `--manifest data/field-loss-20261111/curated-manifest.json` auf diesen
  unveränderten Entwicklungsdokumenten neu ausführen. Noch kein neuer neuronaler
  Nachweis für v26 oder Gesamtqualität nach Rotationskorrektur. VLM-Kontext
  bleibt bei real inkompatiblen Rastern/Headerlisten bewusst gesperrt; falsche
  Datenheader werden nicht geraten repariert. OSD-Zuverlässigkeit, Tokenabbrüche,
  Regelbaseline-Vorlagen und Referenzeignung bleiben transparent offen. Eine
  unabhängige Studie braucht danach getrennte Dokumente und eingefrorene Regeln.

### 2026-11-11 – Automatische Seitenausrichtung im normalen Lauf repariert

- **Auftrag:** nach dem Feldverlust-Audit die automatische Ausrichtung selbst
  reparieren; eine ausschließlich manuelle Manifestkorrektur genügt nicht.
  Ausgangsbefund: auf dem untersuchten Bestand blieben seitlich liegende Seiten
  wegen fehlgeschlagenem oder zu schwachem OSD unverändert und prüfpflichtig.
- **Implementiert:** neues `orientation.py`, `OCR.orientation_evidence` in
  `software/verarbeitung/src/participant_bench/ocr.py` und Integration in
  `pdf.py`. Schwaches OSD erhält einen vollständigen Vierlagenvergleich mit
  vorhandener lokaler Tesseract-OCR, begrenzter Auflösung/Laufzeit und expliziten
  Mindestbelegen. Unsichere Ergebnisse bleiben offen. Die tatsächlichen
  Extraktionsbilder behalten vollständige Pixel und werden nur gedreht.
  Originale OSD-Konfidenz, Vergleichsevidenz und angewendeter Winkel sind getrennt;
  native PDF-Metadatenrotation wird genau einmal berücksichtigt. Alte ungeprüfte
  automatische Manifeste werden durch eine Versionskennung abgewiesen;
  ausdrücklich kuratierte bleiben nach bestehenden Hashprüfungen verwendbar.
- **Reporting / Dokumentation:** `report.py`,
  `roster_benchmark/pipeline_trace.py` und `roster_benchmark/error_report.py`
  zeigen Methode/Status und getrennte OSD-/Vergleichsevidenz. Neu
  `software/docs/automatic-orientation.md`; aktualisiert `software/README.md`,
  `software/testframework/README.md`, `software/docs/local-methods.md`,
  `software/docs/field-loss-20261111.md` und diese Übergabe. Keine Änderungen
  an Modellen, Prompts, YAML-Konfigurationen oder Abhängigkeiten in diesem Schritt.
- **Aktiv konfiguriert:** vorhandenes `pdf.auto_orient: true` genügt. Der normale
  `software/start_testframework_5.cmd` verwendet die Reparatur automatisch für
  alle Verfahren. Kein manuelles Manifest und keine Referenzdaten als Input
  der Orientierungsentscheidung. Gemeinsame OCR-Diagnosen liefern keine
  extrahierten Feldtexte an das direkte VLM; die Gesamtvorverarbeitung ist
  gleichwohl nicht vollständig OCR-frei und muss methodisch so berichtet werden.
- **Tests:** neues `software/tests/test_orientation_fallback.py` mit 48 Fällen,
  darunter echte OCR-Proben bei kontrolliertem OSD-Ausfall für alle vier Winkel,
  Unsicherheits-/Timeoutfälle und alle 16 Kombinationen aus PDF-Metadaten- und
  Zusatzrotation einschließlich nativem Docling-Pfad. Gesamtsuite abschließend
  **820 bestanden (96,21 s)**, **48 API-Tests bestanden (9,77 s)**, Ruff und
  normales `git diff --check` ohne Befund. Eine anfänglich zu strenge
  Bytegleichheitsprüfung nativ neu gerenderter Vektorkanten wurde durch eine
  gerichtete Ausrichtungsprüfung ersetzt; Rasterausgaben werden weiter exakt
  geprüft. Starter `--pruefen` erfolgreich, zehn Eingabe-PDFs, keine Inferenz
  oder Netzverbindung. Neues automatisches und bestehendes kuratiertes Manifest
  nochmals mit den produktiven Hash-/Konfigurationsprüfungen validiert.
- **Anhand vorhandener Daten nachgewiesen:** reguläres automatisches `prepare`
  auf zehn Entwicklungs-PDFs/zwanzig Seiten ohne manuelles Manifest:
  **20/20 richtig ausgerichtet, zwölf gedreht, acht beibehalten**, ein OSD- und
  neunzehn Vergleichsentscheide, keine offenen Seiten in diesem Bestand.
  Erst nach der Entscheidung gegen die frühere visuelle Annotation geprüft;
  alle zwanzig vollständigen Raster pixelgleich mit den geprüften Drehungen.
  Original-PDFs und 1.762 geschützte historische Dateien unverändert.
  Beobachtete Vorbereitung 84,64 s, kein kontrollierter Laufzeitbenchmark.
  Vorabprobe bei 2.000 Pixeln ließ eine dünn beschriftete Seite offen; endgültig
  bis 2.600 Pixel ohne Absenkung der Entscheidungsschwellen. Lokale ignorierte
  Nachweise: `software/data/auto-orientation-20261111/validation.json`,
  `prepared/manifest.json`, `synthetic_validation.json`, Kontaktansicht und
  `preview.html`; Kontaktansicht visuell und zwei lokale HTML-Bildlinks geprüft.
- **Offen / nächster Schritt:** neuer vollständiger Fünferlauf zur Messung der
  tatsächlichen Feldqualität nach der Korrektur. Hier keine neue LLM-/VLM-
  Inferenz, kein Nachweis höherer Extraktionsscores und keine allgemeine
  Zuverlässigkeitsgarantie für beliebige Handschrift oder textarme Seiten.
  Frühere Header-, Token- und Referenzprobleme bleiben eigenständige Ursachen.
  Historische Ergebnisse bleiben unverändert; neue Läufe verwenden neue
  Code-/Manifestidentitäten. Die spätere Methodik muss gemeinsame Diagnose
  und Vorbereitungszeit des Vergleichs transparent berücksichtigen.

### 2026-11-11 – Spaltenkontext für headerlose Folgeseiten geprüft und abgesichert

- **Auftrag / vorhandene Grundlage:** die gemeinsame dokumentbezogene
  Spaltenzuordnung prüfen und für Personalnummer, Vorname, Nachname sowie
  Organisation/Abteilung absichern. Aktuelle eindeutige Überschriften sollen
  Vorrang haben, ungemessene/geänderte Layouts keine Übernahme erzwingen und
  vorherige Teilnehmerwerte niemals weitergegeben werden.
- **Ursachen vor Änderung reproduziert:** nativer OCR-Fallback benutzte bei
  fehlender Geometrie, abweichender Spaltenzahl oder ganz fehlender Tabelle
  trotzdem alte Intervalle. Tesseract verlor zweite Überschriftenzeilen;
  neue ID-/Organisationsüberschriften ohne Namensrollen konnten alte komplette
  Layouts nicht zuverlässig sperren. VLM las getrennte Namenszellen, gab aber
  zunächst den semantischen Modellnamen Vorrang. Ein tatsächlicher Test-LLM-
  Input enthielt angehängte Inhalte einer alten Überschriftenzelle. Die spätere
  Namensprüfung konnte belegte getrennte Spalten noch als unsicher behandeln
  beziehungsweise der globalen Standardreihenfolge unterordnen. Die neuen
  Regressionen prüfen genau diese technischen Fälle; kein bestimmter historischer
  Referenzfehler wird allein deshalb nachträglich als ursächlich erklärt.
- **Geänderte Implementierungen:** `column_context.py` (v2, strikte Intervall-
  weitergabe, sichere Überschriftenstruktur, Geometrieaudit, kompakte Begründungen
  und gemeinsame gespeicherte Diagnosequellen), `ocr_layout.py` (mehrzeilige und
  aktuelle partielle Überschriften), `structure_assignment.py` (v10, physische
  Spaltenindizes einschließlich führender Nichtzielfeldspalten, Überschriftenblöcke),
  `structured_mapping.py` (kein Umgehen abgewiesener Geometrie, explizite partielle
  Header und Ablehnungsdiagnose ohne Tabelle), `unlimited_assignment.py` (sichere
  Labels und Positionsattribute in `previous_headers`), `vlm_cells.py` (aktuelle
  getrennte Namenszellen und deren Audit), `document_names.py` (Vorrang belegter
  getrennter Spalten bei der Nachverarbeitung). Alle unter
  `software/verarbeitung/src/participant_bench/`.
- **Geänderte Berichte:** dort `report.py`,
  `roster_benchmark/pipeline_trace.py` und `roster_benchmark/error_report.py` (v5).
  Haupt-/Fehlerbericht und Mapping-CSV zeigen Feldspalten, Überschriftenquelle,
  Quellseite und deutsche Begründung mit Quell-/Zielgeometrie, größter Abweichung
  und bestehender Grenze 0,035. VLM-/Hybridentscheidungen und physisch zugeordnete
  Namensfelder sind vollständig in der gespeicherten Feldkette verwendbar.
  Fehlende historische Belege bleiben unbekannt; keine rückwirkende Extraktion.
- **Dokumentation:** `software/docs/document-columns.md` um aktuellen Stand,
  konkrete Ursachen, Schutzregeln, Nachweise und Grenzen ergänzt; historischen
  Vergleich vom 03.11. erhalten und als solchen gekennzeichnet.
  `software/testframework/README.md` und diese Übergabe aktualisiert. Keine
  Bachelorarbeitstexte oder PDFs geändert. Keine Modelle, Promptvorlagen,
  YAML-Konfigurationen oder Abhängigkeiten ergänzt. Dynamische Kontextinputs
  ändern sich gezielt; unveränderte Schnittstellen und vorhandene Speicherung
  tatsächlicher Prompts/Hashes bleiben bestehen.
- **Tests / Ergebnisse:** neues `software/tests/test_column_continuation_audit.py`
  mit 30 Regressionen. Positive/negative mehrseitige Fälle aller vier Felder,
  neue vollständige/partielle/mehrdeutige Überschriften, unabhängige PDFs,
  geänderte Geometrie, leere/unklare aktuelle Zellen, echte Rasterdetektion,
  reale Codepfade des Textmodellinputs, beide HTML-Berichte und abschließende
  Namensprüfung abgedeckt. Abschließend **850 lokale Tests bestanden (98,07 s)**,
  **48 API-Tests bestanden (9,77 s)**; die abschließende lesende Ergänzung des
  Feldanalyseberichts zusätzlich durch **99 gezielte Tests (3,56 s)** geprüft.
  Ruff und reguläres `git diff --check` bestanden. Frühere Prüfungen mit 845/846
  Gesamttests bestanden vor den zusätzlichen Nachverarbeitungsregressionen;
  ein dabei erfasster kombinierter Namensfall bleibt ausdrücklich von getrennten
  Namensspalten unterschieden. API-Prüfung verwendet deren eigene `.venv`.
- **An vorhandenen Artefakten geprüft:** neuer, rein lesend gerenderter Bericht
  `software/testframework/ergebnisse/column-context-20261111/extraction_errors.html`.
  Bewertungs-/Identitätsdateien bytegleich mit dem vorherigen Vergleich;
  1.762 geschützte historische Dateien unverändert. 908 lokale Dateilinks in
  historischem Analyse- und synthetischem Mappingbericht geprüft, keine fehlenden
  Dateien. Synthetischer Dreiseiten-Replay unter
  `software/data/column-context-20261111/synthetic-report/`: zwei Übernahmen,
  ausschließlich aktuelle Zellwerte. Aggregierte Nachweise in
  `software/data/column-context-20261111/validation.json`; private Artefakte bleiben
  lokal ignoriert. Keine neue Inferenz auf realen Entwicklungsdokumenten;
  vorhandene synthetische OCR-Regressionen gehören zur Gesamtsuite.
- **Aktiv / Grenzen / nächster Schritt:** vorhandene Tesseract+LLM-, Paddle+LLM-,
  VLM-/Hybrid- und optionale Docling-Kontextpfade nutzen den Code automatisch in
  neuen Läufen. Die deterministische Regelbaseline behält ihre Vorlagenlogik.
  Kontextversion v2 verhindert die Übernahme alter v1-Zustände. Kein gemessener
  realer Qualitätsgewinn und keine Behauptung, dass geometrisch identische
  inhaltliche Spaltenvertauschungen ohne neue Überschriften sicher erkennbar sind.
  Für Qualitätswerte einen neuen normalen Fünferlauf auf den bereits bekannten,
  nun automatisch ausgerichteten Entwicklungs-PDFs ausführen. Historische
  Ergebnisse bleiben historische Ergebnisse; unabhängige Finaldaten separat halten.

### 2026-11-11/12 – Systematische Reportanalyse mit begrenztem Gegencheck abgeschlossen

- **Auftrag / Grundlage:** neuesten tatsächlichen vollständigen Fünferlauf
  `20261111T091101Z-59c4b71d` und Vergleich `20261111T110330Z-09f5d83e`
  systematisch analysiert. Zehn bereits vorbenutzte Entwicklungs-PDFs mit
  zwanzig Seiten; keine unabhängigen Finaltestdaten zur Optimierung verwendet.
  Alle 100 Rohseitenergebnisse, 297 JSON-/23 JSONL-Dateien und 2.147 Logzeilen
  inventarisiert. Referenzen und Bewertungsregeln unverändert.
- **Nachgewiesene technische Korrekturen:** `unlimited_assignment.py` entfernt
  im Eingabe-JSON ausschließlich exakt rekonstruierbare doppelte Zeilenrahmen
  und protokolliert vor Generierung auftretende Eingabebudgetfehler separat.
  `rules.py` erhält das erste Datenband am Tabellenbeginn.
  `roster_benchmark/error_report.py` v6 ordnet Eingabebudgetfehler der
  Modelleingabe statt einer angeblich ungültigen Modellantwort zu.
  Keine Promptvorlagen, Modelle, Limits oder zusätzlichen Abhängigkeiten geändert.
- **Validierung / gemischte Qualität:** alle zwanzig gespeicherten Paddle-Inputs
  exakt rückrekonstruierbar, zwei zuvor übergroße Inputs nun unter unverändert
  12.000 Tokens. Genau zwei neue lokale Textmodellgenerierungen mit denselben
  Gewichten, Systemprompt, Schema und Grenzen, außerdem unveränderter Warm-up.
  Korrekte Literal-/Positionsprüfung anhand tatsächlich gespeicherter Feldbänder;
  eine davor unzureichende Zwischenvalidierung ausdrücklich verworfen.
  Paddle exakt 122→133, falsch 36→44, fehlend 462→443, zusätzliche Felder 0→0;
  zehn zusätzliche Teilpersonen. Exakter Recall 19,68→21,45 %, F1 31,36→33,38 %,
  Precision verschlechtert 77,22→75,14 %. ID/Organisation unverändert.
  Kein neuer vollständiger Lauf aller Verfahren und kein allgemeiner
  Halluzinationsfreiheitsnachweis. Andere Verfahren im Gegencheck unverändert.
- **Negative Befunde / Grenzen:** allgemeiner Baseline-Headerprototyp mit
  64 exakten und 40 falschen Feldern nicht aktiviert. Reale Regelbaseline
  trotz Bandkorrektur weiterhin null Teilnehmer. Neun VLM-/Hybridabbrüche am
  Ausgabelimit und vierzehn leere OCR+LLM-Antworten bleiben offen. Früher
  implementierte User-/Spaltenparser getrennt auf gespeicherten Antworten geprüft;
  deren Ergebnisse nicht als Gewinne der neuen Kompaktierung angerechnet.
- **Tests / Berichtsschutz:** 14 neue Regressionen in
  `software/tests/test_assignment_input_compaction.py`; abschließend 864 lokale
  Tests (94,81 s), 48 API-Tests (11,02 s), Ruff und regulärer Diff-Check bestanden.
  Abschließende Publikationsprüfung am 12.11.: 2.421 lokale HTML-Dateilinks
  ohne fehlendes Ziel. Von 1.413 geschützten Dateien 1.412 unverändert;
  historischer HTML-Bericht nur um autorisierten Analyselink ergänzt,
  exakte Sicherung und unveränderter Restinhalt geprüft.
- **Dokumentation / Artefakte:** neue
  `software/docs/systematic-error-analysis-20261111.md`, Einstiegslink in
  `software/docs/extraction-error-analysis.md`, Software-README und Übergabe.
  HTML: `software/testframework/ergebnisse/systematic-audit-20261111/report.html`,
  zugehöriger begrenzter Gegencheck unter `after/`. Lokale private Nachweise
  ausschließlich unter `software/data/systematic-audit-20261111/`, insbesondere
  `quality_comparison.json` und `publication_verification.json`.
- **Folgeauftrag / nächster Schritt:** Nutzer möchte normalen neuen Lauf für
  drei Beispiele einschließlich `146079` mit Berichtlink. Am 12.11. als
  `20261112T071339Z-ca4962b3` gestartet; Abschluss und Qualitätszahlen noch offen.
