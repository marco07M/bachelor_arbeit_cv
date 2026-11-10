# Projektstand und Übergabe für folgende Agenten

Zuletzt aktualisiert: **2026-11-10** (Europe/Berlin).

Diese Datei auf Wunsch des Nutzers bei Änderungen fortschreiben. Einstieg und
Pflegepflicht stehen in [AGENTS.md](AGENTS.md). Sie ist die zentrale Übergabe,
auch wenn frühere Chatnachrichten oder ein vorheriges Kontextfenster fehlen.

## Aktueller Stand

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
