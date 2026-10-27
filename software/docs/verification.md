# Verifikationsprotokoll

Unlimited-OCR-Zellzuordnung, 27.10.2026: Der bisherige CV-Lauf lieferte OCR,
aber keine Teilnehmer: verbundene Tabellenzellen auf der ersten Seite und
fehlende Spaltenüberschriften auf der zweiten Seite verhinderten die bisherige
regelbasierte Zuordnung. Neue Option `extraction: llm` ergänzt eine lokale
Zuordnung mit dem vorhandenen Qwen3-8B nach vollständigem Entladen des
Unlimited-Workers. Explizite Zellnummern, Spaltenpositionen, leere Zellen und
HTML-Spans bleiben erhalten. Gedruckte eindeutige Überschriften gestatten direkte
Zellübernahme; `Benutzername` wird als Namensfeld behandelt. Andere Werte müssen
als vollständige Wörter/Phrasen in derselben Quellzeile belegt sein. Falsche
Zellnummern werden nur bei eindeutigem Beleg innerhalb dieser Zeile berichtigt.
Maskierte IDs bleiben unbekannt; die semantische Zuordnung bleibt prüfpflichtig.

`configs/unlimited-ocr-llm.yaml`, Vierervergleich und Unlimited-Starter verwenden
die Kombination. Reine OCR und Tabellenbaseline bleiben separat konfigurierbar.
`assign-unlimited --run ... --offline` ordnet gespeicherte OCR zu, ohne die OCR
zu wiederholen oder den Quelllauf zu verändern. Neue Ergebnisse stehen in einem
separaten Lauf mit Quellhashes. Antworten werden mit Quell-, Modell-, Parameter-,
Systemprompt- und Schemafingerprints lokal gecacht und beim Wiederlesen erneut
gegen die Quellzellen geprüft. Keine API-Übertragung von Dokumentdaten.

**250 lokale Tests und 38 getrennte API-Tests bestanden**; Ruff, Lockprüfung und
`git diff --check` erfolgreich. 21 neue Testfälle decken zusammengeführte Zellen,
Namensaufteilung, führende Nullen, leere Benutzerzellen, teilweise maskierte IDs,
vollständige Wortbelege, falsche/zeilenfremde Referenzen, Kontexttrennung zwischen
PDFs, leere Markdown-Randzellen, Fehler/Tokenlimit, Cache, Quellimmutabilität,
Export und GPU-Modellreihenfolge ab. Modell-Doubles prüfen Verträge und messen
keine OCR-/LLM-Erkennungsqualität. Nach den letzten Provenienz-/Exportergänzungen
sind 31 gezielte Tests erneut erfolgreich.

**Vollständiger realer lokaler Lauf ausgeführt:**
`runs/20261027T092255Z-21c3aed0/report.html` auf der bestehenden Test-PDF mit zwei
Seiten. Unlimited-OCR, danach 8B-LLM (int8, sämtliche Parameter auf cuda:0),
danach BF16-VLM zur Unterschriftenprüfung; keine gleichzeitige Modellbelegung.
Ca. 325 Sekunden Gesamtzeit einschließlich Laden, OCR und Signaturprüfung.
Neun beziehungsweise acht Teilnehmerdatensätze, zusammen 17 statt zuvor null,
68 buchstäblich durch Zellen belegte Textfelder. Das bestätigt Textvorkommen,
keine unabhängige semantische Feldgenauigkeit. Eine weitere OCR-Zeile auf Seite 2
(`t0r0`) bleibt als nicht zugeordnet markiert. 17 visuelle Signatur-Detailprüfungen
ausgeführt; ohne manuelle Labels kein Qualitätsnachweis. Status bewusst `partial`.
Die früheren Zuordnungsversuche `090939Z-f590ef0a` und `091706Z-e2ac0160` sind
Entwicklungsdiagnosen, nicht der abschließend geprüfte Stand. Die Ausgangs-PDF,
ältere Berichte und Ground Truth wurden nicht verändert.

Bedienung, Grenzen und neue Exporte: [Unlimited-Zuordnung](unlimited-assignment.md).

GPU-Anpassung, 27.10.2026: Qwen3-8B bleibt bei Revision
`b968826d9c46dd6066d109eabc6255188de91218`. In `local.yaml` (auch über
`imported.yaml`) und `benchmark-unlimited.yaml` werden seine linearen Schichten
beim Laden mit bitsandbytes 0.48.1 / LLM.int8 quantisiert. Originalgewichte,
Parameterzahl, OCR, Prompts und Tokenbudgets bleiben erhalten. `device: cuda`
erzwingt und prüft vollständige GPU-Zuordnung; CPU-Offload ist nur noch im
ausdrücklich gewählten `auto`-Modus erlaubt. VLM bleibt in BF16. Modell-
speicher, Quantisierung und tatsächliche Parametergeräte werden protokolliert.

Abschließend **229 lokale Tests und 38 getrennte API-Tests bestanden**, Ruff und beide
Lockprüfungen erfolgreich. Fünfzehn zusätzliche Fälle prüfen GPU-/CPU-Zuordnung,
fehlende CUDA-/8-Bit-Unterstützung, Kompatibilitätsgrenzen und unveränderte
8B-Checkpointauswahl. Hauptumgebung weiterhin PyTorch 2.8.0+cu126 / Transformers
4.57.6; die API-Lockdatei wurde ohne Installation von GPU-Paketen aktualisiert.

Echte int8-GPU-Inferenz auf zwei synthetischen Seiten:
`runs/20261027T082419Z-49a39d0a/report.html`. Alle 8.190.735.360 Parameter auf
`cuda:0`, Modellbelegung 9.435.703.552 Bytes (8,79 GiB), Peak allocated ca.
9,85 GiB / reserved ca. 9,92 GiB. Zwei gültige Seitenausgaben mit sechs Zeilen,
keine technischen Seitenfehler, rund 35–39 Sekunden Generierung je Seite und
103 Sekunden Gesamtlaufzeit einschließlich Laden. Die separat bewertete
Textfeldqualität beträgt auf dieser Tesseract-/LLM-Konstruktion nur 12/24
buchstäblich korrekte Felder; dies belegt die Funktionsfähigkeit des GPU-Pfads,
keine ausreichende Extraktionsqualität und keinen verlustfreien Ersatz für
BF16. Ein kontrollierter BF16-Vergleich auf dieser Konstruktion fehlt.

Bei einem anschließenden Versuch auf der bestehenden CV-Test-PDF zeigte sich
trotz korrekter CUDA-Parameterzuordnung Windows-Speicherauslagerung: 15.477.776.384
Bytes dedizierter GPU-Speicher und 4.984.930.304 Bytes Shared GPU Memory
(Windows-GPU-Prozesszähler, nur Prozess-/Speichermetadaten). Dieser eigene
Diagnoselauf `20261027T082651Z-6eae8b8e` wurde unterbrochen und ist kein
abgeschlossener Benchmark. Daraufhin die CUDA-Allocator-Grenze mit 2 GiB freier
Reserve und native Promptaufteilung in 1024-Token-Abschnitte ergänzt. Der Text
wird nicht gekürzt; KV-Cache und vollständige Eingabetokens bleiben erhalten.
Drei weitere Tests prüfen vollständige Tokenübergabe und Wiederherstellung der
vorherigen Speichergrenze nach einem Fehler beim Laden.

Erneuter CV-Lauf `runs/20261027T083827Z-158083d5/report.html`: zwei Seiten ohne
technischen Extraktionsfehler, vollständige OCR-Eingaben aus demselben Cache
(5485 beziehungsweise 2396 Eingabetokens). Reine Modellberechnung ca. 160,3 und
133,6 Sekunden; im früheren Lauf `20261027T074837Z-9a137c33` ca. 916,6 und 541,0
Sekunden. Die Tokenausgaben unterscheiden sich (828/838 gegenüber 918/838),
ebenso die übernommenen Einträge (17 gegenüber 19, eine neue Modellzeile ohne
OCR-Beleg verworfen). Das ist ein beobachteter Laufzeitgewinn, kein kontrollierter
Nachweis gleicher Feldqualität. Es fehlen manuell geprüfte Referenzen für diese
PDF. Status bleibt wegen Feld-/Signaturunsicherheit `partial`.

Windows-Zähler im neuen Lauf: ca. 11,62 GB dediziert und 85,98 MB gemeinsam
genutzter GPU-Speicher; die frühere Auslagerung mehrerer GiB tritt nicht mehr auf.
CUDA-Peak allocated ca. 10,01 GiB, reserved ca. 10,53 GiB. Beim anschließenden
Modellwechsel blieb zunächst zusätzlich cuBLAS-Arbeitsspeicher reserviert, sodass
die Signaturprüfung in diesem Diagnoselauf nicht starten konnte. `close()` gibt
nun nach Synchronisation auch den Workspace-Cache frei. Dafür wird der in der
festgelegten PyTorch-2.8-Version vorhandene interne Hook defensiv abgefragt.

**Modellwechsel auf echter GPU erneut erfolgreich geprüft:** 5246 synthetische
Eingabetokens mit Chunking, danach LLM entladen und VLM im selben Prozess geladen.
Nach dem LLM sowohl `memory_allocated` als auch `memory_reserved` null; ca. 14,6 GiB
frei. Alle 4.437.815.808 VLM-Parameter auf `cuda:0`, Warm-up erfolgreich, nach
VLM-Entladen wieder keine CUDA-Allokationen. Die vorherige Allocator-Grenze wurde
wiederhergestellt. Messung unter `.cache/gpu-switch-check.json`; reine technische
Speicherprüfung ohne Dokumentdaten. Signaturnachprüfung der vorhandenen
Teilnehmerergebnisse anschließend erfolgreich in ca. 38 Sekunden unter
`runs/20261027T083827Z-158083d5/signature-review/20261027T085402Z-7bac329a/report.html`.
Die ursprünglichen Textextraktionen bleiben unverändert.

Unlimited-OCR, 22.10.2026: Native lokale Integration mit festgelegter Modellrevision
`8249d20b2822a7d8a4c22c8d8c9069b5ac36bda3`, ohne Ausführung von Checkpoint-Python-Code.
Eine referenzierte Safetensors-Datei (6672212480 Gewichtbytes) samt Tokenizer und
Konfiguration explizit heruntergeladen und per SHA256 inventarisiert. Separates
uv-Projekt `unlimited_ocr_runtime/`: Transformers 5.20.2, PyTorch 2.8.0+cu126,
Torchvision 0.23.0+cu126, HF Hub 2.2.0 und Safetensors 0.8.0. Die bestehende
Hauptumgebung bleibt bei Transformers 4.57.6; die API-Umgebung bleibt getrennt.
`trust_remote_code=False`, `local_files_only=True`, Offline-/Telemetriesperren
und reine CUDA-Zuordnung sind im Worker gesetzt.

**214 lokale Tests und 38 API-Tests bestanden.** Zehn neue lokale Testfälle
prüfen Zellzuordnung, Umlaute/Eigennamen, führende Nullen, leere Benutzerfelder,
fehlende/verbundene Zellen, Rohtext, PDF-/PNG-/JPEG-Eingaben, Resume, Weiterlauf
nach Seitenfehlern, Textbewertung und die Abgrenzung reiner OCR von Feldmetriken.
Zusätzlich trennt `raw_exact_match` buchstäbliche Schreibweise von der bisherigen
normalisierten Feldbewertung. Nach abschließenden Berichts-/Provenienzänderungen
sind 39 gezielte OCR-/Evaluierungstests und erneut alle 38 API-Tests erfolgreich.
Ruff, beide lokalen Lockprüfungen und `git diff --check` sind erfolgreich.

**Echte GPU-Inferenz durchgeführt:** `runs/20261022T122134Z-405f63e7/report.html`.
Zwei synthetische PDF-Seiten mit je denselben drei vorab festgelegten Personen;
die zweite Seite hat PDF-Rotation 90 Grad und wurde durch OSD zusätzlich um
270 Grad korrigiert. Beide Seiten wurden einzeln auf der RTX 4090 Laptop GPU
verarbeitet: Batch 1, BF16, SDPA, dynamische Bildausschnitte, maximal 4096 neue
Tokens, ein Warm-up, ein Modellladen und zwei produktive Modellaufrufe.
Ergebnis: sechs korrekt zugeordnete Zeilen, **24/24 Textfelder sowohl buchstäblich
als auch normalisiert korrekt**, darunter leere Benutzer und Personalnummern
mit führenden Nullen. CER/WER auf unabhängig aus der Konstruktion erstellten
Seitentranskripten: normalisiert 0 auf 364 Zeichen beziehungsweise 50 Wörtern.
Textmetriken mit Referenz- und Vorhersagehashes unter `unlimited_ocr/text_evaluation/`.
Signaturreferenzen bleiben unbekannt; keine Signaturqualität wird daraus behauptet.

Gemessene CUDA-Peaks: ca. 7,90 GiB allocated, 9,00 GiB reserved. Im letzten Lauf
ca. 51 Sekunden produktive Seitenverarbeitung und ca. 81 Sekunden Gesamtlaufzeit
einschließlich Vorbereitung, Prüfsummen, Initialisierung und Berichten.
Ein früherer Funktionslauf (`20261022T121441Z-5b53c550`) war schneller; dies waren
keine kontrollierten Performance-Wiederholungen und begründet keinen Laufzeitvergleich.
Die Tesseract-/Regelbaseline lieferte auf derselben Konstruktion 16/24 Felder,
unter anderem wegen fehlender Benutzer-Headerzuordnung. Das ist ein Vergleich
ganzer Pipelines auf einem kleinen technischen Beispiel, kein unabhängiger
Nachweis besserer OCR für reale Vorlagen.

Separater echter PNG-/OCR-only-Lauf: `runs/20261022T121545Z-7237ac00/report.html`,
lokal und erfolgreich, ohne künstliche Teilnehmerdatensätze. Normalisierte CER/WER
jeweils 0 auf 182 Zeichen/25 Wörtern. Die ursprüngliche Zeichen-CER beträgt wegen
unterschiedlicher Tabs und Zeilenumbrüche 26/184; diese Differenz wird nicht versteckt.
JPEG ist in der automatisierten Bildverarbeitung getestet, nicht zusätzlich als
echte Modellinferenz. Handschrift und reale Unternehmensdokumente wurden mit dem
neuen Modell nicht evaluiert. Keine Dokumentinhalte an externe Dienste übertragen.

Anleitung, Grenzen und Einzel-/Benchmarkbefehle: [Unlimited-OCR](unlimited-ocr.md).
Der neue Starter `start_unlimited_cv_test.cmd` verwendet ausschließlich den
vorhandenen CV-Testordner; bisherige Starter und Standardmodelle bleiben erhalten.

Ergänzung zum CV-Teststart am 22.10.2026: `start_lokal_cv_test.cmd` verarbeitet
nur `data/cv-test-20261020-093337/` mit lokaler Konfiguration und `--offline`.
Die Eingabeprüfung wurde aus dem Repository-Hauptordner gestartet und findet
genau eine PDF, ohne diese zu analysieren. Die API-Startdatei liegt separat unter
`api_firmen_pc/start_api_cv_test.cmd` und verwendet den gleich benannten Ordner
im API-Projekt. Bei leerem API-Ordner stoppt sie vor dem Laden von Zugangsdaten.
Vier gezielte Start-/Exporttests und Ruff sind erfolgreich. Das aktualisierte
Quellpaket mit API-Startdatei heißt `api_firmen_pc/dist/firmen-pc-cv-test.zip`;
es enthält weiterhin keine Dokumente, privaten Beispiele oder Modellgewichte.

Stand nach der Trennung am 22.10.2026: Der API-Betrieb liegt vollständig im
eigenen uv-Projekt `api_firmen_pc/`. API-Adapter, Verbindungskonfiguration,
Starthelfer und Tests sind aus dem lokalen Einstieg entfernt. Gemeinsame
Analysefunktionen besitzen nur explizit registrierbare, backendneutrale
Erweiterungspunkte. Der lokale CLI-Import funktioniert bei gesperrtem Import des
Firmen-PC-Pakets; unbekannte externe Backends scheitern vor dem Lesen der PDFs.
Die lokalen Modellpakete wurden beim Synchronisieren mit `--extra models` erhalten.

**204 lokale Tests und 38 separate API-Tests erfolgreich.** Die API-Tests prüfen
unter anderem OAuth-Basic/Formular-Anmeldung, Tokenwiederverwendung, Gateway-Key,
PDF-Extraktion, Signaturprüfung, Resume, Exporte und den neuen `main.py smoke`-
Ablauf gegen einen lokalen Loopback-Server. Zugangsdaten und Dokumente sind
ausschließlich synthetisch. Keine interne Firmen-API wurde kontaktiert.
Die neue API-Umgebung enthält weder PyTorch noch Transformers. Ruff-Prüfungen,
`git diff --check` und beide Lockdateiprüfungen sind erfolgreich.

`api_firmen_pc/dist/firmen-pc.zip` wurde aus einer expliziten Quellenauswahl
erzeugt und separat unter `.cache/fc-bundle-check/` entpackt. Installation mit
`uv sync --locked --offline --no-dev` und Start von `main.py --help` in einer
neuen Umgebung sind erfolgreich; auch dort fehlen GPU-Modellpakete. Der Export
enthält keine PDFs, Modellgewichte, Zugangsdaten-Dateien, Runs oder privaten
Testskripte. Die bisherigen `test_url`-Dateien liegen unverändert unter
`api_firmen_pc/privat/test_url/` und sind von Git, Tests und Export ausgeschlossen.
Die echte OAuth-Registrierung und deren Netzwerkvoraussetzungen bleiben auf
dem Firmen-PC zu prüfen. Aktuelle Anleitung: [Firmen-PC-Projekt](../api_firmen_pc/README.md).

Ergänzung 22.10.2026: Das separate API-Testskript `test_url/main.py` prüft
Client-ID, Client-Secret und Modellkennung vor dem Verbindungsaufbau. Es akzeptiert
`CLIENT_ID`/`CLIENT_SECRET` und alternativ `BMW_AI_CLIENT_ID`/`BMW_AI_CLIENT_SECRET`;
der Header verwendet die geprüfte ID. Fehlende Werte erzeugen eine Meldung mit
Variablennamen statt des HTTPX-Fehlers über einen `None`-Header. **44 gezielte Tests
erfolgreich**, davon zwölf neue Startprüfungen ausschließlich mit synthetischen
Werten und ersetzten Clients/Tokenhelfern. Keine realen Zugangsdaten gelesen und
keine interne API aufgerufen. Die bestehenden API-/Starthelfertests bleiben erfolgreich.

Stand 22.10.2026: Lokale OCR-Kalibrierung unter
`verarbeitung/src/participant_bench/calibration/` integriert. **233 Tests erfolgreich**,
darunter 19 neue Fälle für Referenzzuordnung, gruppierte Aufteilung, CER/WER,
ECE/Brier, Sigmoid/Isotonic, Audit-Sperren, Koordinatentransformationen,
PDF-Text und hybride PDFs, Exporte, Resume und Anwendung ohne Ground Truth.
Vorhandene 214 Regressionstests bleiben erfolgreich. `ruff check` und
`git diff --check` sind ebenfalls erfolgreich.

Vollständiger synthetischer CLI-Lauf: `runs/c-smoke22/report.html`. 20 einseitige
PDFs in zehn unterschiedlichen Layoutfamilien, je zwei verwandte Kopien in
derselben Gruppe. Aufteilung: zwölf Entwicklungsdokumente, zwei für die
Schwellenwertsuche, zwei für das unabhängige Audit und vier für den finalen Test.
Baseline mit echtem lokalem Tesseract und Variante mit direktem PDF-Text wurden
verglichen. Entwicklung: jeweils 96/96 Textfelder, Audit: jeweils 16/16.
Die schnellere PDF-Text-Variante wurde vorgeschlagen, wegen unzureichender
unabhängiger Auditgruppen jedoch nicht übernommen. Alle vier Feldregeln blieben
`review_only`; es wurde keine Kalibrierungsqualität aus der kleinen fehlerfreien
Stichprobe abgeleitet.

Der anschließend getrennt gestartete finale Test liegt unter
`runs/c-smoke22/test/report.html`: vier Dokumente, acht Teilnehmer, 32/32 Textfelder,
keine fehlenden/zusätzlichen Personen, normalisierte Text-CER/WER jeweils 0 auf
616 Referenzzeichen bzw. 88 Wörtern. Selbstständige SVG-/PNG-Reliability-Diagramme
und CSV-/JSON-Ausgaben sind erzeugt. Der komplette Entwicklungslauf dauerte etwa
15 Sekunden; der finale Benchmark-Unterlauf etwa 3,6 Sekunden, ohne manuelle
Annotation und ohne externe Inferenz. Kein Beleg für Qualität echter Scans oder
Handschrift. Echte geprüfte Referenzen stehen für diesen Kalibrierungslauf nicht
zur Verfügung; Standardparameter wurden nicht automatisch geändert.

Neue Befehle: `ocr-reference`, `ocr-split`, `ocr-calibrate`, `ocr-final`, `ocr-apply`.
Anleitung und wissenschaftliche Grenzen: [OCR-Kalibrierung](ocr-calibration.md).
Matplotlib wurde über uv installiert und in `uv.lock` festgelegt; die bestehende
lokale Modellumgebung wurde erhalten. Dokumente, Referenzen und OCR-Ergebnisse
wurden an keine externen Dienste übertragen.

Stand 21.10.2026, `participant-json-v10-empty-user-cells`: VLM-Anweisung und
Feldbeschreibungen trennen Benutzer/User ID von Kurzzeichen nach Spaltenposition.
Sichtbar leere Benutzer bleiben `""/empty`; die Person und ihr Kurzzeichen bleiben
erhalten. Nur aus Leerzeichen bestehende Antworten werden ebenfalls als leere
Zelle normalisiert; unbekannte/geschwärzte Werte bleiben `null/uncertain`.
Die gemeinsamen Prompts werden lokal und im API-Adapter verwendet. Bestehende
Läufe werden nicht verändert; die neue Promptidentität verhindert eine Mischung
mit früheren Ergebnissen beim Resume.

**214 Tests erfolgreich**, einschließlich neuer Fälle für leere Benutzer,
unbekannte IDs, Leerraum, alphanumerische IDs und korrekten CSV-Export. Zusätzlich
ein echter lokaler Lauf mit Qwen3-VL-4B-Instruct auf einer eigens erstellten
zweiseitigen PDF: `runs/20261021T081431Z-48ddf9f6/report.html`. Zwei unterschiedliche
Spaltenreihenfolgen, zehn Teilnehmer, sechs leere Benutzerfelder, Kurzzeichen mit
Ziffern/Trennzeichen und vier leere Kurzzeichenfelder. Ergebnis: **40/40 Textfelder
korrekt**, alle zehn Teilnehmer erhalten; Benutzer und Kurzzeichen je 10/10.
Beide Seiten erfolgreich; etwa 41 Sekunden insgesamt. Keine API-Anfrage, keine
realen Daten und keine zusätzliche OCR-/Signaturinferenz im Testlauf. Generator:
`scripts/make_empty_user_smoke.py`; Konfiguration: `configs/empty-user-smoke.yaml`.
Dies ist ein synthetischer Funktionstest, keine Qualitätsgarantie für echte Scans.

Ergänzung 21.10.2026: Privater manueller API-Start über
`scripts/run-private-api.ps1`. Die Option `-Persist` wurde entfernt;
Zugangsdaten werden nur im gestarteten Prozess gesetzt und nach dem Lauf
entfernt. Eine externe `NAME=WERT`-Datei wird ausschließlich über den expliziten
Parameter `-EnvFile` eingelesen, ohne Codeausführung oder Variablenexpansion.
Repository-interne Pfade und ungültige/mehrfach belegte Einträge werden abgewiesen.
**32 API- und Starthelfer-Tests erfolgreich**, darunter sieben neue Fälle mit
separaten PowerShell-Testprozessen und ausschließlich synthetischen Schlüsseln.
Geprüft wurden die Übergabe an Python, das Ausbleiben von Schlüsselwerten in
der Konsolenausgabe und das Entfernen nach Erfolg bzw. Importfehler. Beim Test
des Starthelfers wurde `-CheckOnly` verwendet; es fand kein API-Aufruf statt.
Dies ist keine technisch erzwungene Zugriffssperre gegenüber Prozessen mit
gleichen Dateirechten; die Trennung und ihre Grenzen stehen in der API-Anleitung.

Stand 21.10.2026: Optionale API-Backends für OCR/LLM und VLM ergänzt, einschließlich
OAuth-Client-Credentials und API-Key aus Umgebungsvariablen. **201 Tests erfolgreich**,
darunter 25 neue API-Fälle mit einem Loopback-HTTP-Server und ausschließlich
synthetischen Namen/PDFs. Geprüft wurden Key-/OAuth-Anmeldung (Body und Basic),
Tokenwiederverwendung und Erneuerung, Timeout-/HTTP-Fehler, Redirect-Sperre,
OCR-Feldbelege, Bildübertragung, JSON-Verträge, abgeschnittene Ausgaben sowie
PDF → Teilnehmer → Signaturdetails → Bericht, Resume und Signatur-Cache.
Die erzeugten Konfigurationen, Berichte, Rohdaten und Caches wurden auf die
synthetischen Zugangsdaten geprüft; diese werden dort nicht gespeichert.

`ruff check` für Quellcode/Tests/Skripte/Vorverarbeitung und PowerShell-Syntaxprüfung
des Einrichtungshelfer-Skripts sind erfolgreich. `api-check` ohne Verbindungsoption
meldet erwartungsgemäß fehlende BMW-Variablen (Exitcode 1, kein Netzwerkzugriff).
Ein API-Lauf mit `--offline` wird vor dem Einlesen der PDFs abgewiesen.
Es wurden keine realen PDFs an einen Dienst übertragen und keine BMW-Zugangsdaten
verwendet. Der echte interne Endpunkt und sein Protokoll sind weiterhin nicht
verifiziert; die Vorlage ist kein Nachweis für eine bereits funktionierende
BMW-Verbindung. Einrichtung und Grenzen: [API-Anleitung](api.md).

Stand 20.10.2026: Die automatische Seitenklassifikation wurde entfernt. Alle
Seiten der manuell ausgewählten Eingabe-PDFs werden nun an die Extraktion
übergeben. Ältere Manifeste müssen neu vorbereitet werden. Die folgenden
historischen Messungen beziehen sich auf ihren damaligen Code- und
Konfigurationsstand.

Seit `participant-json-v9-signature-details` verwendet die lokale Konfiguration
eine zusätzliche gemeinsame Signaturstufe mit Qwen3-VL-4B-Instruct. Sie arbeitet
auf vergrößerten Zeilenbildern mit getrenntem Spaltenkontext. Die konservative
OpenCV-Baseline bleibt in den Smoke-Konfigurationen erhalten und kann weiterhin
keine positiven Unterschriftenentscheidungen treffen. A/B entladen vor dem
Signatur-VLM ihr Extraktionsmodell; C nutzt sein geladenes VLM weiter. Diese
Zusatzstufe macht die Signaturauswertung von A/B ausdrücklich zu einer Kombination
mit VLM. Die ursprünglichen VLM-Anweisungen und das Antwortschema für
Teilnehmerfelder stimmen mit dem Stand des Quelllaufs `20261020T101106Z-e12943df`
überein. Die getrennte Positionssuche ändert keine Personenfelder.

Fehlende Positionen stammen bevorzugt aus eindeutigen vorhandenen OCR-Wortbelegen;
widersprüchliche Namens-/ID-Zuordnungen werden dabei abgelehnt. Sonst erfolgt eine
separate lokale VLM-Lokalisierung auf einer expliziten 0–1000-Skala. Nicht
lokalisierbare Zeilen bleiben offen. Der CLI-Befehl `signatures` prüft vorhandene
Personen ohne neue Teilnehmerinferenz nach, erhält den Quelllauf und schreibt
Quellprüfsummen, Ausschnitte, Rohantworten und neue Signaturmessungen separat.
Alte Qualitätsmetriken werden nicht als neue Evaluation übernommen.

Echte lokale Nachprüfung von B:
`runs/20261020T102932Z-895bb966/signature-review/20261020T111004Z-7dd2d1ab/`.
Auf Seite 1 neun positive Detailbefunde statt neun unbekannter Signaturen;
auf Seite 2 vier positive Befunde und sechs offene Fälle. Die ursprünglichen
Personenfelder und Quelldateien blieben erhalten.

Echte lokale Nachprüfung der 18 gespeicherten VLM-Personen des Laufs
`20261020T101106Z-e12943df`: Auf Seite 1 neun positive Detailbefunde statt zuvor
zwei positiven Gesamtbildentscheidungen. Auf Seite 2 fünf positive Detailbefunde
und vier nicht lokalisierte Signaturfelder. Die neun vorhandenen positiven
Gesamtbildentscheidungen bleiben dort erhalten; die vier unklaren Detailbefunde
werden separat ausgewiesen und sind keine zusätzlichen bestätigten Treffer.
Insgesamt stammen elf Zeilenpositionen aus OCR-Wortbelegen und sieben aus der
separaten VLM-Lokalisierung. Ohne manuelle Referenzlabels sind das keine
validierten Precision-/Recall-Werte.
Aktueller Bericht mit getrennten Gesamtbild- und Detailentscheidungen:
`runs/20261020T101106Z-e12943df/signature-review/20261020T113027Z-8967691a/report.html`.
Dieser abschließende Durchlauf verwendet 18 Cachetreffer und keine neue
Dokumentinferenz. Ein Vergleich bestätigt unveränderte Personenfelder und
Zeilenreferenzen für beide Seiten. Die ursprünglichen echten Detailaufrufe
stehen im Lauf `20261020T112415Z-8fb77fb8` unter derselben `signature-review/`-Wurzel.

Ein zusätzlicher echter lokaler VLM-Test mit einer synthetischen PDF prüft ein
leeres Feld, eine gezeichnete Unterschriftsmarkierung und gedruckten Text:
Erwartet und erhalten wurde `[false, true, null]`, drei Detailaufrufe in 3,31 s
ohne Modellsetup. Artefakte: `runs/signature-synthetic-1a1ef482/verification.json`.
Dies prüft diese drei künstlichen Fälle, keine echte Handschriftverteilung.
176 automatisierte Tests bestanden, einschließlich Signaturzuständen,
Quellerhalt, Cachewiederverwendung, Positionskonflikten, unveränderten
Personenfeldern sowie getrennten Aufrufen und der Modell-Entladereihenfolge.

Seit `participant-json-v8-ocr-lines` erhält das OCR-Sprachmodell zusätzlich zur
Worttabelle den lesbaren Zeilentext mit Zeilen- und Wortkennungen. Die Feldprüfung
verwendet diese OCR-Zeilen vor dem geometrischen Vergleich. Äußere Satzzeichen
werden nur beim Vergleich toleriert; die Ausgabe behält die OCR-Schreibweise.
Echte Zuordnungen zu einer anderen OCR-Zeile bleiben gesperrt und bekommen einen
eigenen Hinweis. Der pauschale Hinweis auf geschätzte Modell-Bounding-Boxes wird
für OCR-basierte Positionen nicht mehr ausgegeben. Ein unbekannter Signaturstatus
bleibt unabhängig von den gelesenen Textfeldern sichtbar.

Auf den beiden Entwicklungsseiten des Laufs `20261020T101106Z-e12943df` umfasst
der neue Prompt 5485 bzw. 2396 Token (Limit 12000), ohne OCR-Wörter abzuschneiden.
Eine lokale Nachprüfung der gespeicherten Antworten reduziert fehlende Textfelder
von zwölf auf acht bei unverändert fünf teilweise belegten Zeilen. Dabei wurde
keine neue Inferenz ausgeführt und der alte Bericht nicht verändert. Dies belegt
die korrigierte Wortprüfung, nicht die Richtigkeit oder Vollständigkeit der OCR.
158 automatisierte Tests bestanden. Neue Regressionen prüfen abweichende
Wortkastenhöhen derselben OCR-Zeile, überlappende Kästen verschiedener Zeilen,
getrennte OCR-Blöcke, äußere Satzzeichen, zusätzliche gültige Wortreferenzen und
die Disambiguierung wiederholter Namen über explizite OCR-Zeilenkennungen sowie
die unveränderte gedruckte Schreibweise von Zeilennummern mit Satzzeichen.

Im echten lokalen Lauf `20261020T102932Z-895bb966` liefert B auf der ersten
Entwicklungsseite neun statt fünf Zeilen. 34 von 36 Textfeldern haben einen
OCR-Beleg (im bisherigen Lauf acht von 20); die zuvor festgestellten
zeilenübergreifenden Feldkombinationen treten in dieser Antwort nicht mehr auf.
Niedrige OCR-Confidence, abweichende Modell-Wortreferenzen und zwei nicht belegte
Felder bleiben als Prüfhinweise sichtbar. Die reine Modellgenerierung dieser
Seite dauerte 1013,9 Sekunden bei 918 Ausgabe-Token. Der größere Textumfang und
das CPU-Offloading machen dieses Verfahren hier langsam; dies ist keine
kontrollierte Laufzeitstudie oder validierte Genauigkeitsmessung.
Der Lauf ist mit beiden Seiten abgeschlossen. Auf Seite 2 liefert B zehn
Zeilen mit 37 von 40 belegten Textfeldern; 13 Felder haben niedrige OCR-Confidence.
Eine Mehrdeutigkeit und ein nicht beobachteter Wert bleiben gesperrt. Die reine
Generierung dauerte dort 575,6 Sekunden bei 838 Ausgabe-Token. Es gab keine
technisch fehlgeschlagenen Seiten. Beide Seiten bleiben `partial` und erfordern
Kontrolle; insbesondere die zusätzliche Ausgabe auf Seite 2 ist ohne manuelle
Referenzlabels kein Nachweis zusätzlicher richtiger Teilnehmender. A liefert auf
dieser Vorlage weiterhin OCR-Klartext als Fallback, aber keine strukturierten
Felder. Der Ergebnisbericht liegt unter
`runs/20261020T102932Z-895bb966/report.html`.
Der abschließende Randfall-Fix für gedruckte Zeilennummern wurde nachprüfbar auf
beide gespeicherten Antworten angewendet: Feldwerte und Zeilenreferenzen stimmen
mit den gespeicherten Ergebnissen überein, es gab keine neue Inferenz.

Seit `participant-json-v7-partial-ocr-fields` sind vollständige OCR-Klartexte und
die per Hash verifizierte LLM-Eingabe unabhängig vom Extraktionserfolg im Bericht
verfügbar. Die Feldprüfung erhält teilweise belegte Zeilen, maskiert unbelegte
oder fremden OCR-Zeilen zugeordnete Felder und übernimmt vollständige beobachtete
Wörter statt Teilzeichenfolgen. Der gespeicherte Lauf
`20261020T093657Z-294ed368` wurde ohne neue Modellinferenz nachgeprüft:
`runs/20261020T093657Z-294ed368/revalidated/report.html`.
Vier teilweise belegte Datensätze mit acht fehlenden Textfeldern bleiben erhalten;
das sind keine vier vollständig oder nachweislich richtig erkannten Teilnehmer.
Originale Modellantworten und Messwerte sind unverändert vorhanden.
150 automatisierte Tests bestanden, einschließlich zeilenübergreifender
Fehlzuordnungen, Teilzeichenfolgen, Originalschreibweisen, niedriger OCR-Confidence,
unabhängiger Klartextexporte, Prompt-Hashes und Aktualisierung alter Berichte.

Tesseract PSM 11 wurde auf denselben Entwicklungsseiten getrennt ausprobiert.
Erkannt wurden 122/46 statt 138/51 Wörter, davon 94/22 statt 85/18 mit Confidence
von mindestens 60. Diese Confidence-Werte sind keine Richtigkeitsmessung; der
Standardmodus PSM 6 bleibt erhalten. Versuchsdaten liegen lokal unter
`runs/20261020T093657Z-294ed368/ocr_experiments/`, eine optionale Konfiguration unter
`configs/ocr-sparse.yaml`. Für den realen Datensatz fehlen weiterhin manuelle
Referenzlabels als Grundlage belastbarer Qualitätsaussagen.

Seit Prompt `participant-json-v6-compact-ocr` erhält das OCR-Sprachmodell eine
kompakte Worttabelle und liefert Feldwerte mit beobachteten Wort-IDs. Auf der
betroffenen Entwicklungsseite sinkt die Eingabe von 19701 auf 4194 Token,
auf der zweiten Seite auf 1867 Token (Limit jeweils 12000). Alle OCR-Wörter
bleiben erhalten. Auch die beiden OCR-Verfahren sichern Text-Fallbacks.
Mehrteilige Überschriften und Vorlagen mit zwei eindeutigen Teilnehmerfeldern
werden unterstützt; unbekannte Tabellen werden nicht durch erfundene Zuordnungen ersetzt.
143 automatisierte Tests bestanden. Neue Tests prüfen den Erhalt aller Wörter,
strikte Wortreferenzen, führende Nullen, mehrteilige Überschriften, explizite
Vorlagen sowie OCR-Fallbacks bei leeren und fehlgeschlagenen Modellantworten.
Die Fallback-Integration verwendet echte lokale Tesseract-Erkennung; die
Sprachmodell-Doubles prüfen nur den Ablauf und sind kein Qualitätsnachweis.

Echter lokaler OCR-Lauf: `runs/20261020T092258Z-dc9ad021/`, zwei Entwicklungsseiten.
Kein Eingabelimit überschritten; die OCR-Texte bleiben auf beiden Seiten erhalten.
Das Sprachmodell lieferte vier Zeilen auf Seite 1, davon zwei mit ausreichendem
OCR-Beleg; Seite 2 blieb ohne Teilnehmer. Die zunächst angewendete strikte
Seitenprüfung verwarf auf Seite 1 auch die belegbaren Zeilen. Die aktuelle
Zeilenprüfung behält diese zwei Zeilen und protokolliert die anderen separat.
Die gespeicherten Antworten wurden ohne neue Inferenz nachgeprüft:
`runs/20261020T092258Z-dc9ad021/revalidated/report.html`.
Dieser Bericht enthält keine neue Laufzeitmessung. Originaler Run und originale
Modellantworten bleiben erhalten; Quelle und Prüfcodes stehen in `revalidation.json`.
Es liegen keine manuellen Referenzlabels für einen Qualitätsnachweis vor.

Der VLM-Prompt `participant-json-v5-text-fallback` extrahiert vorrangig
Teilnehmerdaten. Nur bei fehlenden Teilnehmern wird der lesbare Seitentext als
Fallback ausgegeben und zur manuellen Prüfung markiert. Die folgenden Messungen
mit Prompt v4 dokumentieren die zuvor verwendete vollständige Transkription.

Für Prompt v5 wurden 127 automatisierte Tests bestanden. Zusätzlich bestätigt
ein echter lokaler VLM-Lauf mit drei synthetischen Seiten das bedingte Verhalten:
zwei Teilnehmende ohne Listenüberschrift erkannt, dabei kein Volltext ausgegeben;
ein Informationsblatt als Text-Fallback erhalten; eine Leerseite ohne erfundene
Inhalte verarbeitet. Laufzeit rund 27,5 Sekunden, keine Reparaturaufrufe:
`runs/20261020T085034Z-0ff646a0/report.html`. Das ist ein Funktionstest anhand
synthetischer Daten, keine Zuverlässigkeitsaussage für den gesamten Datensatz.

Der VLM-Prompt `participant-json-v4-page-text` las zusätzlich den gesamten
lesbaren Seitentext aus und verwendet ein kompaktes Teilnehmerformat. Das
konfigurierte Ausgabelimit beträgt 8192 Token. Abgeschnittene Antworten sind
als Ausgabeprobleme ausgewiesen und bleiben unverändert einsehbar.
125 automatisierte Tests bestanden, einschließlich Antwortformat, Fehlerweitergabe,
Seitentextexport und HTML-Escaping. Die Antwort-Doubles dieser Tests prüfen
Datenverträge und Ablauf, keine Erkennungsqualität.

Ein erneuter echter lokaler VLM-Lauf auf den zwei vom Nutzer ausgewählten Seiten
lieferte zwei gültige Antworten und 18 Teilnehmereinträge in rund 87,5 Sekunden:
`runs/20261020T084404Z-0a0fc90f/report.html`. Beide Seiten wurden verarbeitet;
keine automatische Seitenauswahl und keine Reparaturaufrufe. Dies bestätigt die
technische Ausführbarkeit, nicht die inhaltliche Richtigkeit oder Vollständigkeit:
Für diesen Lauf liegen keine manuell annotierten Referenzwerte vor.

Umgebung und Datum: Windows 11, 14.10.2026. Exakte Umgebungsdaten liegen lokal in
`runs/doctor.json` und zusätzlich pro Run in `environment.json`.

- uv 0.13.1; Python 3.12.15 projektlokal durch uv eingerichtet.
- `uv sync --locked --extra models --offline` erfolgreich nach dem Setup.
- PyTorch 2.8.0+cu126: `cuda.is_available() == True`, RTX 4090 Laptop GPU.
- Transformers 4.57.6: `Qwen3VLForConditionalGeneration` importiert.
- Tesseract 5.4.0: deutsche/englische Sprachdaten und OSD geprüft.
- 23 Tests bestanden, inklusive echter Tesseract-Inferenz und Offline-Integration,
  manueller 180°-Korrektur und separater Erfassung von technischen/Schemafehlern.
- Pipeline A auf sechs synthetischen Seiten: 24/24 Textfelder korrekt, sechs
  Teilnehmende auf drei befüllten Seiten; Blank/Deckblatt/leere Liste enthalten.
  Physische Rotation und PDF-Metadatenrotation geprüft. Kein Ergebnis auf realen Daten.
- Mit kuratiertem Manifest und ohne Ground Truth echte CLI-Läufe durchgeführt.
- Lokale HTML-, JSONL- und CSV-Berichte erzeugt. Die frühen Run-Ordner dokumentieren
  ihren jeweiligen Code-/Konfigurationsstand; endgültige Abnahmeläufe folgen unten.

Beide festgelegten Modellrevisionen wurden tatsächlich heruntergeladen und ihre
Dateien gehasht. `download-models --transport range` verifiziert die LFS-SHA256
gegen Repositorymetadaten. Die spätere Inferenz wurde mit Netzwerkzugriff gesperrt
(`uv run --offline ... --offline`) ausgeführt.

Ein echter einzelner VLM-Smoke-Test mit Promptversion v3 war erfolgreich:
`runs/20261014T104453Z-88223e3b/report.html`. Zwei Teilnehmende, 8/8 Textfelder
korrekt; Modellinferenz rund 40,4 s; Peak-GPU-Allokation 10610332672 Bytes
(etwa 9,9 GiB). Die leere Unterschriftszelle wurde unbekannt beantwortet, sodass
die Signaturabdeckung für die bekannte negative GT 0/1 beträgt. Die synthetische
Strichmarke ist unbekannte GT und kein positiver Signatur-Qualitätsbeleg.

Die vorherigen echten VLM-Läufe wurden korrekt als failed protokolliert:
v1 widersprüchliche Signaturzustände, v2 Bounding-Box-Arrays statt Schemaobjekten.
Rohantworten bleiben in den jeweiligen Run-Ordnern. Keine automatische Reparatur
oder nachträgliche Umdeutung als erfolgreiche Extraktion. Die Promptpräzisierung
erfolgte ausschließlich anhand synthetischer Development-Daten, nicht auf Testdaten.

## Abschließender gemeinsamer realer Modelllauf

Verifizierter Befehl:

```powershell
uv run --offline --locked --extra models participant-bench run --input data/model-smoke/raw --ground-truth data/model-smoke/ground_truth.jsonl --config configs/local.yaml --offline
```

Ergebnis: **alle drei Verfahren success**, je eine tatsächlich verarbeitete Seite,
zwei Teilnehmende, 8/8 Textfelder Exact Match, keine zusätzlichen/fehlenden Einträge,
keine Schemafehler oder technischen Ausfälle. Dies ist ausschließlich ein
synthetischer Development-Smoke-Test, keine Qualitätsaussage über echte Formulare.

Run: `runs/20261014T105542Z-489dddee/`.

| Verfahren | Extraktion inkl. zugerechneter OCR/Signatur | Modell laden | Warm-up | GPU-Peak alloziert |
| --- | ---: | ---: | ---: | ---: |
| A OCR/Regeln | 0,295 s | – | – | – |
| B OCR/Qwen3-8B | 959,103 s | 3,961 s | 8,070 s | 13,69 GiB |
| C Qwen3-VL-4B | 40,910 s | 4,209 s | 0,931 s | 9,88 GiB |

Prüfsummen/Processor-Setup und gemeinsame Vorverarbeitung sind zusätzlich
in `full_pipeline_charged_seconds` erfasst (A 0,857 s, B 989,711 s, C 53,536 s).
Die reale gesamte Verfahrenszeit steht separat in `actual_method_wall_seconds`.
Die Werte stammen aus genau diesem Run, nicht aus einem Vergleich unabhängiger
Populationen oder kontrollierten Wiederholungsmessungen. Beim B-Laden liefen
abschließende CPU-Regressionstests parallel; die lange eigentliche B-Generierung
lief danach ohne weitere Modellinferenz. CPU-Offloading ist hier eine deutliche
praktische Einschränkung. Die dedizierte CUDA-GPU hat 16 GB, nicht 47 GB.
Zusätzlich ist Intel UHD Graphics als Displaytreibereintrag vorhanden; deren
gemeinsamer RAM ist kein zusätzlicher CUDA-VRAM.

Signaturen: Für die bekannte leere Zelle erreichen A/B Abdeckung 1/1; C antwortet
unknown, Abdeckung 0/1. Die Strichmarke ist unbekannte GT. Es gibt keinen positiven
Signatur-GT-Fall, daher sind positive Precision/Recall/F1 hier nicht bestimmbar.
Die Konfusionsmatrix und Unknown-Nenner bleiben sichtbar. Kein Beleg für die
Erkennung echter Unterschriften und keine Echtheitsprüfung.

Wichtige Ergebnisdateien:

- `report.html`: vollständig lokaler, lesbarer Vergleich.
- `summary.json`, `methods.csv`: Status und tatsächlich gemessener Aufwand.
- `metrics.json`, `quality.csv`: deskriptive Qualität mit Zählern/Nennern.
- `extractions.csv`, `<method>/extractions.jsonl`: normalisierte Ergebnisse.
- `<method>/raw.jsonl`, `<method>/attempts/`: echte Originalantworten und Versuche.
- `manifest.json`, `effective_pages.json`, `prompts.json`, `identity.json`,
  `environment.json`, `config.yaml`: Provenienz und reproduzierbare Einstellungen.

Die verifizierten A-Integrationsfälle umfassen zusätzlich sechs synthetische
Seiten mit Blank/Deckblatt/leerer Liste sowie 0/90/180/270-Grad-Behandlung.
Abschließender kuratierter A-Run mit `--split development`:
`runs/20261014T111517Z-d9f1ad49/report.html`, 24/24 Textfelder, vier ausgewählte
Seiten einschließlich leerer Liste und sechs Teilnehmende auf drei befüllten Seiten.
Die OCR-Wörter und Cacheidentität von A und B im gemeinsamen Modellrun wurden
zusätzlich auf Gleichheit geprüft. Der HTML-Bericht enthält keine externen
Bildquellen oder Skripte. Der abschließende `doctor` meldet beide Modelle verfügbar,
ein CUDA-Gerät, beide Windows-Displaytreibereinträge und keine Warnungen.
`uv sync --locked --offline` ohne Modell-Extra und ein realer A-Lauf funktionierten;
anschließend wurde das Modell-Extra wieder mit `uv sync --locked --extra models --offline`
hergestellt. `ruff check`, `ruff format --check`, Offline-Verhalten, unveränderte
Originale, Resume und Schemagenerierung sind geprüft.

Offene Grenzen: reale Vorlagen/Scans fehlen; Regeln und Grenzwerte müssen auf
Development-Daten angepasst werden. Kein validierter positiver Signaturklassifikator,
keine Evaluation echter Handschrift, keine statistisch belastbaren Qualitäts-
oder Einsparungsbehauptungen. PaddleOCR/HTR, Quantisierung und produktiver Import
sind nicht implementiert. Große Bestände wurden nicht verarbeitet.
