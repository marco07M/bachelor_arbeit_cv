# API-Verarbeitung auf dem Firmen-PC

Dieser Ordner ist ein eigenes uv-Projekt mit eigener `.venv` und `uv.lock`.
Die lokale Verarbeitung im übergeordneten `software/` bleibt unabhängig.
Die gemeinsamen PDF-, Extraktions-, Signatur-, Export- und Excel-Funktionen
werden als Quellpaket eingebunden; hier werden **keine GPU-Modellgewichte**
installiert. Der API-Adapter wird ausschließlich durch diesen Einstieg aktiviert.

Die aktuelle API-Version verwendet dieselbe Spaltenzuordnung wie die lokale
VLM-Auswertung: vollständige Tabellenzeilen einschließlich leerer Benutzerfelder,
getrennte Kurzzeichen und Prüfhinweise bei mehrdeutigen Spalten. Dafür müssen auch
die gemeinsamen Quellen unter `software/verarbeitung/` aktualisiert werden; ältere
ZIP-Pakete enthalten diese Änderung nicht. Der API-Modellname wird über
`BMW_VLM_MODEL` gewählt. Die lokale Umstellung auf Qwen3-4B ändert kein API-Modell.

## Ablauf wie beim bisherigen Testskript

1. Einstellungen und Zugangsdaten aus der Prozessumgebung prüfen.
2. OAuth-Token über `client_credentials` und HTTP Basic anfordern.
3. Bearer-Token und den separaten Gateway-Key (`x-apikey` als Vorlage) an die
   Modell-API senden.
4. LLM mit OCR-Text oder VLM mit Seitenbildern aufrufen.
5. Ergebnisse und Berichte vor Ort speichern und bei Bedarf mit Excel vergleichen.

Der Helfer setzt die nicht-geheimen Verbindungsdaten aus dem früheren Testskript
als EU-QA/INT-Vorgaben: API-Basisadresse, WebEAM-Token-URL, `machine2machine`,
`x-apikey`, Chat-Pfad und das mitgelieferte CA-Bundle. Er fragt nur nach
Client-ID, Client-Secret, API-Key und VLM-Modellname. Diese Vorgaben müssen zu
deiner Freischaltung passen; ein erfolgreicher echter BMW-Zugang wurde hier
nicht verifiziert. Die Umstrukturierung behebt kein serverseitiges
`401 invalid_client`.

Die aus dem Remote-Stand übernommenen Angaben zu EU/US, QA/PROD, Token-Endpunkten
und Onboarding stehen unter [GATE-Zugang](docs/gate-zugang.md).

## Installation

Auf dem Firmen-PC in einer separat geöffneten PowerShell aus diesem Ordner:

```powershell
uv sync --locked
```

Python 3.12 wird über uv verwaltet. Kein `--extra models` verwenden.
Das Standardverfahren `configs/api-bmw.yaml` verarbeitet alle manuell ausgewählten
PDF-Seiten mit dem VLM; es setzt weder Tesseract noch CUDA/PyTorch voraus.
Die zusätzliche Signaturprüfung nutzt ebenfalls die konfigurierte VLM-API.

## Schnellstart von Grund auf (Windows)

Die folgenden Befehle in einer **separaten PowerShell außerhalb der IDE** ausführen.
Zuerst in den Ordner `software\api_firmen_pc` wechseln. Den Pfad gegebenenfalls an
den Speicherort auf deinem Rechner anpassen:

```powershell
Set-Location "C:\PFAD\ZUM\REPOSITORY\software\api_firmen_pc"
uv sync --locked
New-Item -ItemType Directory -Force .\data\pdfs_eingabe | Out-Null
```

`uv sync --locked` richtet die Umgebung beim ersten Start ein und kann nach
Projektupdates erneut ausgeführt werden. Danach:

1. Die zu verarbeitenden PDFs in `data\pdfs_eingabe` oder einen Unterordner kopieren.
2. In derselben PowerShell Zugangsdaten laden. Client-ID, Client-Secret und
   API-Key werden verdeckt abgefragt; der Modellname wird normal abgefragt:

   ```powershell
   . .\scripts\set-api-environment.ps1
   ```

3. Vor dem Modellstart sicherstellen, dass PDFs gefunden werden. `Count` muss
   größer als `0` sein:

   ```powershell
   Get-ChildItem .\data\pdfs_eingabe -Recurse -File -Filter *.pdf | Measure-Object
   ```

4. Konfiguration prüfen und mit einer kleinen Anfrage testen. Der Smoke-Test
   sendet keine PDF-Inhalte:

   ```powershell
   .\.venv\Scripts\python.exe .\main.py check --config configs/api-bmw.yaml
   .\.venv\Scripts\python.exe .\main.py smoke --method vlm --config configs/api-bmw.yaml
   ```

5. Verarbeitung starten:

   ```powershell
   .\.venv\Scripts\python.exe .\main.py run --input data\pdfs_eingabe --config configs/api-bmw.yaml
   ```

Der Bericht und die Ergebnisdateien liegen anschließend unter
`runs\<RUN_ID>\`; den Bericht `report.html` öffnen. Darin sollten „Seiten zur
Extraktion“ und „Antworten mit gültigem Format“ größer als `0` sein. Sind
„Seiten zur Extraktion“ gleich `0`, wurden keine PDFs verarbeitet: Eingabeordner
und PDF-Zählung prüfen. Nach dem Schließen der PowerShell müssen die Zugangsdaten
für die nächste Sitzung erneut geladen werden.

Für einen anderen PDF-Ordner den Pfad bei `--input` ersetzen. Die PDFs bleiben
lokal; ihre Seitenbilder werden für die Inferenz an den konfigurierten API-Dienst
gesendet.

Im Repository braucht das Projekt die gemeinsamen Quellen im übergeordneten
`software/`. Zum Übertragen ohne Gewichte, Dokumente, Ergebnisse und private
Testskripte gibt es einen gezielten ZIP-Export:

```powershell
..\.venv\Scripts\python.exe scripts/export_company_bundle.py --output dist/firmen-pc-cv-test.zip
```

Ergebnis: `dist/firmen-pc-cv-test.zip`. Auf dem Firmen-PC entpacken und in
`software/api_firmen_pc/` installieren. Die ZIP enthält ausschließlich die
ausgewählten Programmquellen, Konfigurationen, Anleitungen und Lockdateien.
Deine PDFs und Zugangsdaten legst du anschließend ausschließlich auf dem
Firmen-PC bereit. Bestehende ZIP-Dateien werden nicht überschrieben.

## Zugangsdaten und Verbindung prüfen

Die Zugangsdaten erst in einer separaten PowerShell auf dem Firmen-PC laden,
außerhalb einer IDE-/Codex-Sitzung:

```powershell
. .\scripts\set-api-environment.ps1
.\.venv\Scripts\python.exe .\main.py check
```

`check` meldet nur fehlende Variablennamen und kontaktiert keinen Server.
`check --connect` fordert ein Token an und ruft die Modellliste ab, ohne PDFs
oder OCR-Ergebnisse zu senden. Unterstützt das Gateway `/models` nicht, kann
die eigentliche Inferenz trotzdem verfügbar sein. Ein bewusst gestarteter
kleiner VLM-Modelltest sendet ausschließlich die Anfrage „Reply with OK.“:

```powershell
.\.venv\Scripts\python.exe .\main.py check --connect
.\.venv\Scripts\python.exe .\main.py smoke --method vlm --config configs/api-bmw.yaml
```

Die zuvor geladenen Variablen gelten für diese Sitzung und ihre Kindprozesse.
Eine `.env` wird nicht automatisch gesucht. Optional ist ein expliziter externer
Pfad möglich: `. .\scripts\set-api-environment.ps1 -EnvFile C:\DEIN_PRIVATER_PFAD\bmw.env -NoPrompt`.
Der Pfad muss außerhalb des gesamten Repositories liegen. Werte werden nicht
als PowerShell-Code ausgeführt. `.gitignore` allein ist keine Zugriffssperre.

| Variable | Verwendung |
| --- | --- |
| `BMW_AI_CLIENT_ID` | OAuth-Client-ID |
| `BMW_AI_CLIENT_SECRET` | Zugehöriges Client-Secret, nicht der Gateway-Key |
| `BMW_AI_API_KEY` | Separater Gateway-Key |
| `BMW_VLM_MODEL` | Modell mit Bildunterstützung |
| `BMW_AI_BASE_URL`, `BMW_AI_TOKEN_URL` | Automatische EU-QA/INT-Defaults; bei Bedarf in der Sitzung überschreibbar |
| `BMW_AI_API_KEY_HEADER`, `BMW_AI_SCOPE`, `BMW_AI_CHAT_PATH` | Automatische Defaults: `x-apikey`, `machine2machine`, `chat/completions` |
| `BMW_AI_CA_BUNDLE` | Standardmäßig das mitgelieferte PEM; ein extern aktualisierter Pfad kann überschreiben |
| `BMW_AI_RESOURCE` | Optional; wird nicht abgefragt |

Die beiden identischen Zertifikatsdateien aus dem Remote-Stand liegen zusammengeführt
unter `certificates/BMW_Trusted_Certificates_Latest.pem`. Das Transferpaket enthält
diese Datei ebenfalls. Der Eingabehelfer verwendet sie automatisch, sofern sie
vorhanden ist. Prüfe auf dem Firmen-PC, ob der Stand noch aktuell und für deinen
Zugang vorgesehen ist; ein neueres Bundle kannst du außerhalb des Repositories
speichern und über `BMW_AI_CA_BUNDLE` oder `BMW_CA_BUNDLE` auswählen.

Es werden keine Zertifikate automatisch heruntergeladen und die TLS-Prüfung wird
nicht abgeschaltet. Ein Firmen-VPN kann erforderlich sein. Bei `invalid_client`
Zugangsdatenpaar, Realm/Umgebung und Anmeldemethode intern prüfen. Falls eure
Registrierung Formularanmeldung verlangt, in beiden Modellkonfigurationen
`options.token_auth_method: body` setzen; Standard hier ist `basic`.

## PDFs verarbeiten

Für einen vollständigen Lauf **mit anschließendem Excel-/CSV-Testframework** gibt
es den eigenen Starthelfer `start_api_testframework.cmd`. PDFs nach
`testframework/eingabe_pdfs/` und genau eine Referenzdatei nach
`testframework/referenz/` legen. Der API-Aufruf und der anschließende lokale
Levenshtein-/Exact-Match-Abgleich laufen automatisch nacheinander. Anleitung:
[API-Testframework](testframework/README.md). `main.py benchmark check` prüft nur
die Eingaben, `main.py benchmark run` startet beides, `benchmark compare --run ...`
bewertet vorhandene Ausgaben ohne neue API-Aufrufe.

Für den CV-Test die PDFs auf dem Firmen-PC unter
`data/cv-test-20261020-093337/` ablegen und
[`start_api_cv_test.cmd`](start_api_cv_test.cmd) doppelt anklicken. Es werden
ausschließlich alle PDFs in diesem Ordner und seinen Unterordnern verarbeitet.
Die Datei nutzt den privaten Starthelfer zur verdeckten Abfrage der Zugangsdaten
und bleibt am Ende offen. `start_api_cv_test.cmd --pruefen` zählt nur die PDFs,
ohne Zugangsdaten zu laden oder eine API zu kontaktieren. Das aktualisierte
Transferpaket einschließlich dieser Startdatei heißt `dist/firmen-pc-cv-test.zip`.

Die für die Analyse ausgewählten PDFs unter `data/pdfs_eingabe/` ablegen. Unterordner
werden durchsucht. Keine automatische Seitentypprüfung und keine Downloads von
Modellgewichten; alle ausgewählten Seiten gehen an die Teilnehmerextraktion.

```powershell
.\.venv\Scripts\python.exe .\main.py run --input data/pdfs_eingabe
```

Mit verdeckter Abfrage und anschließendem Entfernen der Zugangsdaten aus dem
Startprozess alternativ:

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\run-private-api.ps1 -InputFolder data/pdfs_eingabe
```

`-CheckOnly` prüft ohne Serverkontakt. Der Helfer verwendet ausschließlich die
eigene `.venv` dieses Ordners. Inferenzanfragen senden PDF-Bilder beziehungsweise
OCR-Texte an den von dir konfigurierten Dienst. Dateien bleiben unverändert;
Ergebnisse entstehen unter `runs/<RUN_ID>/`, einschließlich `report.html`,
Rohantworten, Statusprotokoll und strukturierten Teilnehmerdaten.
Der Starthelfer entfernt nach dem Lauf auch beide CA-Pfadvariablen aus seinem Prozess.

Weitere Befehle:

```powershell
.\.venv\Scripts\python.exe .\main.py run --input data/pdfs_eingabe --resume runs/DEINE_RUN_ID
.\.venv\Scripts\python.exe .\main.py signatures --run runs/DEINE_RUN_ID --method vlm
.\.venv\Scripts\python.exe .\main.py report --run runs/DEINE_RUN_ID
.\.venv\Scripts\python.exe .\main.py compare-excel --run runs/DEINE_RUN_ID --excel data/referenz.xlsx
```

Für OCR/LLM statt direkter Bildauswertung gibt es `configs/api-ocr.yaml`.
Dafür lokales Tesseract samt `deu`, `eng`, `osd` installieren; unter Windows kann
aus diesem Ordner `uv run --locked python ../scripts/setup_ocr.py` verwendet werden.
Danach `run --config configs/api-ocr.yaml ...`. CPU-OCR ist erforderlich, lokale
LLM-/VLM-Gewichte sind es nicht. `configs/api.yaml` bleibt eine alternative
Key-only-Vorlage mit `LLM_API_*`/`VLM_API_*`-Variablen.

## Lokaler Laptop und fairer Modellvergleich

Für den direkten Vergleich denselben PDF-Ordner auf beide Rechner kopieren und
auf beiden Seiten dieselbe Version des Projekts verwenden. Die Vergleichsprofile
`../configs/vlm-comparison.yaml` (lokal) und `configs/api-bmw.yaml` (API) erben
gemeinsame PDF-Auflösung, DPI, Seitenauswahl, Prompts, Antwortschema und
Signaturparameter. Beide verarbeiten nur `vlm`; OCR-basierte Seitendrehung ist
auf beiden deaktiviert. Der jeweilige Modell-Backend und das Modell selbst sind
der beabsichtigte Unterschied. Das API-Profil sendet die gerenderte PNG-Seite
als Base64-Bild zusammen mit dem Prompt an GATE. Die zusätzliche
Signaturauswertung verwendet ebenfalls das jeweilige VLM.

Die Modellausgaben müssen nicht identisch sein; sie sind das Ergebnis, das
verglichen werden soll. Die Eingabeseiten sollten identisch sein: Vergleiche
`source_sha256` und `image_sha256` in den jeweiligen `manifest.json`-Dateien.
Dateien werden nicht automatisch zwischen Rechnern synchronisiert.

Auf dem leistungsfähigen Laptop aus `software/`:

```powershell
uv sync --locked --extra models
.\.venv\Scripts\participant-bench.exe run --input PFAD_ZUM_GLEICHEN_PDF_ORDNER --config configs/vlm-comparison.yaml --offline
```

Auf dem Firmen-PC mit API-Zugangsdaten:

```powershell
.\.venv\Scripts\python.exe .\main.py run --input PFAD_ZUM_GLEICHEN_PDF_ORDNER --config configs/api-bmw.yaml
```

Berichte und strukturierte Ergebnisse verwenden dasselbe Schema. Die Berichte
halten Backend/Modell getrennt fest; API-Hardwarekosten und GPU-Speicher werden
nicht als lokal gemessen ausgegeben. Die bestehende lokale Mehrmethoden-Auswertung
und OCR-Kalibrierung bleiben separat verfügbar.

## Bisherige Testskripte

Dein früherer Ordner `test_url/` liegt unverändert unter `privat/test_url/`.
Er ist von Git, Tests und ZIP-Export ausgeschlossen. Er wird vom neuen Einstieg
nicht geladen. Vorhandene feste Zugangsdaten wurden nicht angezeigt oder kopiert.
Die neue `main.py` verwendet ausschließlich Umgebungsvariablen. Zum bewussten
Ausführen der alten Beispiele sind zusätzliche Pakete nötig:
`uv sync --locked --extra legacy-test`. Das ist für den neuen Ablauf unnötig.

## Tests

```powershell
uv run --locked pytest -q
```

Tests verwenden synthetische Zugangsdaten und einen lokalen Loopback-Server;
kein echter Firmenendpunkt wird kontaktiert. Das ist kein Nachweis einer
funktionierenden internen Client-Registrierung.
