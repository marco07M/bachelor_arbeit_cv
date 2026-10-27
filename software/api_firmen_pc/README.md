# API-Verarbeitung auf dem Firmen-PC

Dieser Ordner ist ein eigenes uv-Projekt mit eigener `.venv` und `uv.lock`.
Die lokale Verarbeitung im übergeordneten `software/` bleibt unabhängig.
Die gemeinsamen PDF-, Extraktions-, Signatur-, Export- und Excel-Funktionen
werden als Quellpaket eingebunden; hier werden **keine GPU-Modellgewichte**
installiert. Der API-Adapter wird ausschließlich durch diesen Einstieg aktiviert.

## Ablauf wie beim bisherigen Testskript

1. Einstellungen und Zugangsdaten aus der Prozessumgebung prüfen.
2. OAuth-Token über `client_credentials` und HTTP Basic anfordern.
3. Bearer-Token und den separaten Gateway-Key (`x-apikey` als Vorlage) an die
   Modell-API senden.
4. LLM mit OCR-Text oder VLM mit Seitenbildern aufrufen.
5. Ergebnisse und Berichte vor Ort speichern und bei Bedarf mit Excel vergleichen.

Die Token-URL, API-Basisadresse, Modellkennungen, der exakte Scope und der
Gateway-Header müssen zu eurem Firmenzugang passen. Ein erfolgreicher echter
BMW-Zugang wurde hier nicht verifiziert. Die Umstrukturierung behebt kein
serverseitiges `401 invalid_client`.

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
kleiner Modelltest sendet ausschließlich die Anfrage „Reply with OK.“:

```powershell
.\.venv\Scripts\python.exe .\main.py check --connect
.\.venv\Scripts\python.exe .\main.py smoke --method ocr_llm
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
| `BMW_AI_BASE_URL` | Modell-API-Basisadresse mit benötigtem Präfix, ohne `/chat/completions` |
| `BMW_AI_TOKEN_URL` | Vollständiger OAuth-Token-Endpunkt |
| `BMW_AI_API_KEY_HEADER` | Exakter Gateway-Header laut Dokumentation; Vorlage: `x-apikey` |
| `BMW_LLM_MODEL` | Textmodell für OCR/LLM und den Standard-Smoke-Test |
| `BMW_VLM_MODEL` | Modell mit Bildunterstützung |
| `BMW_AI_SCOPE` | Exakter Scope aus dem bisherigen Test beziehungsweise der internen Dokumentation |
| `BMW_AI_RESOURCE` | Optionale OAuth-Resource |
| `BMW_AI_CHAT_PATH` | Optionaler relativer Anfragepfad; Standard: `chat/completions` |
| `BMW_AI_CA_BUNDLE` | Optionaler lokaler PEM-Pfad zur Firmen-CA; kein automatischer Download |
| `BMW_CA_BUNDLE` | Alternativer Name aus dem Remote-Starthelfer; `BMW_AI_CA_BUNDLE` hat in der Standardkonfiguration Vorrang |

Die beiden identischen Zertifikatsdateien aus dem Remote-Stand liegen zusammengeführt
unter `certificates/BMW_Trusted_Certificates_Latest.pem`. Das Transferpaket enthält
diese Datei ebenfalls. Sie wird ausschließlich verwendet, wenn du ihren Pfad in
`BMW_AI_CA_BUNDLE` oder `BMW_CA_BUNDLE` setzt. Prüfe auf dem Firmen-PC, ob der
Stand noch aktuell und für deinen Zugang vorgesehen ist; ein neueres Bundle kannst
du außerhalb des Repositories speichern und über dieselbe Variable auswählen.

Es werden keine Zertifikate automatisch heruntergeladen und die TLS-Prüfung wird
nicht abgeschaltet. Ein Firmen-VPN kann erforderlich sein. Bei `invalid_client`
Zugangsdatenpaar, Realm/Umgebung und Anmeldemethode intern prüfen. Falls eure
Registrierung Formularanmeldung verlangt, in beiden Modellkonfigurationen
`options.token_auth_method: body` setzen; Standard hier ist `basic`.

## PDFs verarbeiten

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

## Lokaler Laptop und Vergleich

Auf dem leistungsfähigen Laptop weiterhin aus `software/` arbeiten:

```powershell
uv sync --locked --extra models
.\.venv\Scripts\participant-bench.exe run --input vorverarbeitung/ausgabe/pdfs --config configs/local.yaml --offline
```

Beide Wege verwenden dieselben Antwortschemata und Bewertungsregeln. Reports
kennzeichnen das Modellbackend; API-Hardwarekosten und GPU-Speicher werden nicht
als lokal gemessen ausgegeben. OCR-Kalibrierung mit Referenzdaten bleibt lokal.
Bereits eingefrorene Kalibrierungsläufe behalten ihre ursprünglichen Hashes;
nach dieser Quellcodeänderung ist für neue Kalibrierungen ein neuer Lauf nötig.
Es werden keine Daten automatisch zwischen Rechnern synchronisiert.

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
