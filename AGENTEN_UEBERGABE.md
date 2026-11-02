# Projektstand und Übergabe für folgende Agenten

Zuletzt aktualisiert: **2026-11-02** (Europe/Berlin).

Diese Datei auf Wunsch des Nutzers bei Änderungen fortschreiben. Einstieg und
Pflegepflicht stehen in [AGENTS.md](AGENTS.md). Sie ist die zentrale Übergabe,
auch wenn frühere Chatnachrichten oder ein vorheriges Kontextfenster fehlen.

## Aktueller Stand

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

Am 2026-11-02 bestanden nach dem Benutzer-ID-Nachtrag **546 vollständige lokale
Tests** in 165,99 Sekunden sowie **48 Tests des getrennten API-Projekts** in
25,06 Sekunden auf dem endgültigen geänderten Kerncode. Fünf Vergleichsskripttests prüfen unter anderem
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
