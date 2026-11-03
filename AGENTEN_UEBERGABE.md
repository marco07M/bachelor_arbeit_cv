# Projektstand und Übergabe für folgende Agenten

Zuletzt aktualisiert: **2026-11-03** (Europe/Berlin).

Diese Datei auf Wunsch des Nutzers bei Änderungen fortschreiben. Einstieg und
Pflegepflicht stehen in [AGENTS.md](AGENTS.md). Sie ist die zentrale Übergabe,
auch wenn frühere Chatnachrichten oder ein vorheriges Kontextfenster fehlen.

## Aktueller Stand

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
