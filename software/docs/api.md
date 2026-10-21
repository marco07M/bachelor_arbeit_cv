# LLM und VLM über eine API verwenden

Alle Befehle aus `software/` ausführen. Die lokale Standardkonfiguration
`configs/local.yaml` bleibt verwendbar. Mit `backend: api` laufen LLM und/oder
VLM beim konfigurierten Dienst; Rendering, Tesseract, Exporte und Excel-Abgleich
laufen weiterhin auf deinem Rechner.

## Stand des internen BMW-Zugangs

`configs/api-bmw.yaml` ist eine vorbereitete **Vorlage**, keine verifizierte
BMW-Schnittstellenbeschreibung. Eine öffentliche Recherche hat keine belastbare
API-/Token-Adresse oder Modellnamen für diesen internen GenAI-Zugang ergeben.
Client-ID, API-Key und Client-Secret allein enthalten diese Informationen nicht.
Die Software probiert deshalb keine geratene Adresse aus.

Implementiert sind Chat-Completions-kompatible Modellanfragen und optional
OAuth-Client-Credentials. Ob euer Zugang genau diese Kombination verwendet,
muss anhand interner Dokumentation oder einer bereinigten Beispielanfrage
geprüft werden. Ein anderes Anfrageformat benötigt eine Anpassung im Adapter
`verarbeitung/src/participant_bench/api_models.py`.

## Installation und Zugangsdaten

Für die API-Modelle genügen die Basisabhängigkeiten, keine Gewichte und kein
PyTorch/Transformers. In einer neuen Umgebung: `uv sync --locked` und für OCR
`uv run --locked python scripts/setup_ocr.py`. In einer bestehenden lokalen
Modellumgebung weiter `--extra models` verwenden, wenn diese Pakete erhalten
bleiben sollen.

**Öffne eine neue PowerShell über das Windows-Startmenü, unabhängig von
VS Code und Codex.** Wechsle dort in den Ordner `software`. Lade die
Zugangsdaten erst in dieser PowerShell und starte keine IDE oder Codex aus
dieser Sitzung. Lass den folgenden Aufruf selbst laufen:

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\run-private-api.ps1 -InputFolder vorverarbeitung/ausgabe/pdfs
```

Der Starthelfer fragt API-Key, Client-ID und Client-Secret verdeckt ab und
setzt ausschließlich Prozess-Umgebungsvariablen. Anschließend startet er die
Python-Anwendung. Nach dem Lauf entfernt er die Zugangsdaten aus seiner
Umgebung, auch bei einem Fehler. Er speichert keine Schlüsseldatei und keine
Benutzer- oder Systemumgebungsvariablen. Die verdeckten Antworten stehen nicht
als Befehle in der PowerShell-Historie. `RemoteSigned` gilt nur für diesen
PowerShell-Prozess; es wird keine dauerhafte Ausführungsrichtlinie geändert.

Mit `-CheckOnly` statt `-InputFolder ...` nur die Konfiguration prüfen, ohne
API-Verbindung oder Dokumentverarbeitung. Für eine Stichprobe
`-InputFolder data/pdfs_eingabe` angeben. Unbekannte Angaben kannst du beim
Einrichten mit Enter überspringen; die Prüfung zeigt fehlende Variablennamen.
Die internen Adressen und Modellkennungen werden weiterhin benötigt.

Die frühere Option `-Persist` wurde entfernt. Falls du sie vorher verwendet
hast, entferne die betreffenden Zugangsdaten selbst aus den Windows-
Benutzerumgebungsvariablen und starte IDE/Codex vollständig neu. Der Starthelfer
ändert bestehende Benutzer- oder Systemvariablen nicht.

### Optional: Zugangsdaten-Datei außerhalb des Projekts

Du kannst selbst eine Datei wie
`C:\Users\DEIN_BENUTZER\.participant-bench-private\bmw.env` anlegen und
mit einem separaten Editor befüllen. Lege sie außerhalb des gesamten
Repositories ab und öffne sie nicht als Projektdatei in Codex. Beispielinhalt
mit Platzhaltern, die du ausschließlich dort ersetzt:

```dotenv
BMW_AI_API_KEY=DEIN_API_KEY
BMW_AI_CLIENT_ID=DEINE_CLIENT_ID
BMW_AI_CLIENT_SECRET=DEIN_CLIENT_SECRET
BMW_AI_BASE_URL=DEINE_INTERNE_API_BASISADRESSE
BMW_AI_TOKEN_URL=DEINE_INTERNE_TOKEN_ADRESSE
BMW_AI_API_KEY_HEADER=DEIN_API_KEY_HEADERNAME
BMW_LLM_MODEL=DEIN_LLM_MODELL
BMW_VLM_MODEL=DEIN_VLM_MODELL
```

In deiner separat geöffneten PowerShell starten:

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\run-private-api.ps1 -EnvFile "$env:USERPROFILE\.participant-bench-private\bmw.env" -NoPrompt -InputFolder vorverarbeitung/ausgabe/pdfs
```

Nur mit ausdrücklich angegebenem `-EnvFile` liest der Starthelfer diese Datei.
Er sucht nicht automatisch nach Schlüsseldateien. Pfade innerhalb des
Repositories werden abgewiesen. Unterstützt werden die unten genannten
BMW-Variablen sowie `LLM_API_BASE_URL`, `LLM_API_MODEL`, `LLM_API_KEY`,
`VLM_API_BASE_URL`, `VLM_API_MODEL`, `VLM_API_KEY` aus `configs/api.yaml`.
Das Format ist `NAME=WERT`, ein Eintrag pro Zeile; Leerzeilen und ganze
Kommentarzeilen mit `#` sind erlaubt. Ein Paar äußerer Anführungszeichen
wird entfernt. Variablen, Escapezeichen und Befehle im Wert werden nicht
ausgewertet. Unbekannte oder doppelte Namen führen vor dem Laden zum Fehler;
Dateiinhalte werden dabei nicht ausgegeben. `-NoPrompt` unterdrückt Nachfragen,
fehlende Pflichtangaben meldet anschließend die Anwendung.

### Was diese Trennung schützt

Die Python-Anwendung liest weiterhin `os.environ`; in ihrem Quellcode stehen
nur Variablennamen. Die erst im separaten Prozess geladenen Werte werden nicht
an eine bereits laufende IDE oder Codex-Sitzung zurückvererbt.
**Eine Umgebungsvariable oder `.gitignore` ist aber keine Zugriffssperre:**
Ein Agent-Prozess kann Zugangsdaten lesen, die seiner eigenen Umgebung zugänglich
sind. Darauf weist auch die [OpenAI-Dokumentation zur Abschirmung von Zugangsdaten](https://developers.openai.com/api/docs/guides/agents-api/environments/security)
hin.

Auch eine externe Datei ist bei gleichen Dateizugriffsrechten grundsätzlich
lesbar. Für eine technisch erzwungene Sperre braucht es getrennte
Betriebssystemrechte bzw. eine isolierte Laufzeit; das Einrichten einer Datei
außerhalb des Projekts allein garantiert das nicht. Der Ablauf hier vermeidet
Schlüssel im Projekt und die Übergabe an Codex. Reale Schlüssel werden für
die Entwicklung und Tests nicht benötigt; dafür werden synthetische Werte benutzt.

| Variable | Inhalt |
| --- | --- |
| `BMW_AI_BASE_URL` | Basisadresse der Modell-API, einschließlich erforderlichem Präfix wie `/v1`, ohne Anfragepfad |
| `BMW_AI_TOKEN_URL` | Vollständiger OAuth-Token-Endpunkt |
| `BMW_AI_CLIENT_ID` | Client-ID |
| `BMW_AI_CLIENT_SECRET` | Client-Secret |
| `BMW_AI_API_KEY` | API-Key für das Gateway |
| `BMW_AI_API_KEY_HEADER` | Exakter Headername für diesen Key laut interner Dokumentation |
| `BMW_LLM_MODEL` | Modellkennung für OCR-Textauswertung |
| `BMW_VLM_MODEL` | Modellkennung mit Bildunterstützung |
| `BMW_AI_CHAT_PATH` | Optionaler Anfragepfad; Standard `chat/completions` |
| `BMW_AI_SCOPE` | Optionaler OAuth-Scope, falls vorgeschrieben |
| `BMW_AI_RESOURCE` | Optionale OAuth-Resource, falls vorgeschrieben |

Im YAML stehen nur Variablennamen. API-Key, Client-ID, Client-Secret und Tokens
werden nicht in Konfigurationskopien, Cacheidentitäten oder Berichte übernommen.
HTTP-Fehlerantworten werden nicht ausgegeben, da sie Zugangsdaten spiegeln könnten.
Zugangsdaten nicht in Modellprompts, PDFs, Excel-Dateien oder YAML-Felder eintragen.
Python lädt keine `.env`-Dateien automatisch. Nur der manuell gestartete
PowerShell-Helfer unterstützt den expliziten externen Pfad. `.env`-Dateien
sind zusätzlich in Git ausgeschlossen; dies schützt nur vor dem Committen.

## Prüfen und starten

Die folgenden direkten CLI-Befehle ebenfalls nur in deiner separaten PowerShell
ausführen. Wenn du sie einzeln verwenden möchtest, kannst du dort vorher
`. .\scripts\set-api-environment.ps1` aufrufen (optional mit `-EnvFile ...`).
Diese Variante hält die Werte bis zum Schließen der Sitzung; der Starthelfer
oben entfernt Zugangsdaten nach jedem Lauf.

`api-check` prüft lokal, welche erforderlichen Angaben fehlen. Dieser Aufruf
sendet weder Zugangsdaten noch Dokumente. Mit vollständigen Adressen und
Anmeldedaten kannst du anschließend die Verbindung testen:

```powershell
.venv/Scripts/participant-bench.exe api-check --config configs/api-bmw.yaml --connect
```

Dabei werden ein OAuth-Token angefordert und `GET <Basisadresse>/models`
aufgerufen. Es werden keine Dokumente und keine Inferenzanfrage gesendet.
Die zurückgegebenen Modellkennungen können beim Ausfüllen der beiden
Modellvariablen helfen; Bildunterstützung ist anhand der internen Modellbeschreibung
zu prüfen. Der Aufruf ist auch ohne gesetzte Modellvariablen möglich; der
Konfigurationsstatus bleibt dann unvollständig (Exitcode 1). Manche Gateways
unterstützen keine Modellliste. Ein HTTP 404 dort beweist deshalb nicht, dass
die eigentliche Extraktion ebenfalls nicht unterstützt wird.

PDF-Stichprobe ausführen:

```powershell
.venv/Scripts/participant-bench.exe run --input data/pdfs_eingabe --config configs/api-bmw.yaml
```

Alle vorher geordneten PDFs ausführen:

```powershell
.venv/Scripts/participant-bench.exe run --input vorverarbeitung/ausgabe/pdfs --config configs/api-bmw.yaml
```

Dabei `--offline` weglassen: Dieser Schalter sperrt API-Inferenz einschließlich
einer API für die zusätzliche Signaturprüfung. `uv --offline` ist davon getrennt
und betrifft Paketdownloads. Die direkte `.exe` verwendet die bestehende Umgebung.

Nur das VLM ausführen: In einer Kopie der Vorlage `methods: [vlm]` setzen.
Mit `pdf: {auto_orient: false}` entfällt die OCR-basierte Ausrichtung. Alle
eingegebenen Seiten gehen direkt in die Extraktion, ohne Seitentypprüfung.

Bestehende Teilnehmerdaten nur auf Unterschriften nachprüfen:

```powershell
.venv/Scripts/participant-bench.exe signatures --run runs/DEINE_RUN_ID --method vlm --config configs/api-bmw.yaml
```

Die zusätzliche Signaturprüfung verwendet immer das Backend unter `models.vlm`.
Sie kann weitere Anfragen für Zeilenpositionen und einzelne Bildausschnitte
auslösen. Das gilt auch beim Regelverfahren A und beim OCR-Sprachmodell B, wenn
`signature.backend: vlm` gesetzt ist. Mit `signature.backend: opencv` lässt sich
diese zusätzliche Modellstufe abschalten. `local_vlm` bleibt als früherer Name
für dieselbe VLM-Stufe unterstützt; das tatsächlich konfigurierte Modellbackend
entscheidet über den Ausführungsort.

## Schnittstellenoptionen

Einstellungen unter `models.ocr_llm.api` bzw. `models.vlm.api` anpassen:

| Einstellung | Wirkung |
| --- | --- |
| `auth: oauth2` | Client-Credentials-Token, anschließend Bearer-Token an die Modell-API |
| `token_auth_method: body` / `basic` | Client-Daten im Token-Formular bzw. HTTP-Basic-Header |
| `token_send_api_key: true` | API-Key zusätzlich an den expliziten Token-Endpunkt senden; Standard aus |
| `api_key_env: null` | Ohne zusätzlichen Gateway-Key, z. B. nur OAuth |
| `auth: api_key` | API-Key ohne OAuth; Beispiel `configs/api.yaml` |
| `api_key_header` / `api_key_header_env` | Header festlegen; OAuth belegt bereits `Authorization` |
| `api_key_prefix` | Präfix vor dem Key, z. B. `"Bearer "` oder `""` |
| `chat_path` / `chat_path_env` | Relativer Pfad; bei Bedarf Platzhalter `{model}` |
| `api_version` | Optionaler `api-version`-Queryparameter |
| `response_format` | `json_object` (Standard), `json_schema` oder `none` |
| `max_tokens_parameter` | `max_tokens` oder `max_completion_tokens` |
| `send_temperature: true` | Temperatur mitsenden, falls das Modell dies unterstützt |
| `ca_bundle_env` | Name einer Umgebungsvariable mit Pfad zum vertrauenswürdigen Firmen-CA-PEM |
| `timeout_seconds` | Anfragezeitlimit, Standard 120 Sekunden |

Die OAuth-Anmeldung folgt [RFC 6749, Abschnitt 4.4](https://www.rfc-editor.org/rfc/rfc6749#section-4.4),
der Token-Header [RFC 6750, Abschnitt 2.1](https://www.rfc-editor.org/rfc/rfc6750#section-2.1).
Tokens werden im Speicher bis kurz vor Ablauf wiederverwendet und anschließend
neu angefordert. Der Zugriff benötigt HTTPS und gültige Zertifikate. HTTP ist
ausschließlich für Loopback-Tests zugelassen. HTTP-Umleitungen werden nicht verfolgt.

LLM und VLM können unterschiedliche Dienste oder lokale/API-Backends verwenden.
Bei `extends` werden ganze oberste YAML-Abschnitte ersetzt: Bei einer eigenen
gemischten Konfiguration deshalb beide Einträge unter `models` vollständig angeben.

## Ergebnisse, Laufzeit und Grenzen

Die Ausgabe liegt wie bisher unter `runs/<ID>/report.html`. Der Überblick zeigt
das Modellbackend. Rohantworten, Text-Fallback, OCR-Feldbelege und manuelle
Prüfhinweise bleiben verfügbar. Die gemeinsame JSON- und OCR-Belegprüfung gilt
auch für API-Antworten. Modellnamen und Serveradresse werden als Provenienz
gespeichert; Zugangsdaten bleiben außerhalb der Ergebnisdateien.

Beim LLM wird der OCR-Text einschließlich Wortpositionen übertragen, beim VLM
das Seitenbild, bei der Signaturstufe zusätzlich Bildausschnitte. Es gibt keinen
automatischen Wechsel zu einem anderen Anbieter. Ein API-Ausfall bleibt als
Fehler sichtbar. Es erfolgen keine automatischen Wiederholungsanfragen; mit
`run --resume runs/ID` lassen sich offene/fehlgeschlagene Seiten erneut versuchen.
Erfolgreiche Seiten und vorhandene Signatur-Caches werden wiederverwendet.

Anfragezeiten und vom Dienst bereitgestellte Tokenzahlen stehen in den Rohdaten,
Anfragezähler in `resources.json`. Fehlende Tokenzahlen bleiben `null`. GPU- und
Energieverbrauch des Servers werden nicht gemessen; API-Preise und Kosten sind
nicht hinterlegt. Lokale Kostenszenarien sind keine Abrechnung des API-Betriebs.
Ein unbekannter Servertokenizer wird nicht lokal nachgebildet: Kontextüberschreitungen
werden vom Dienst gemeldet, Eingaben werden nicht still gekürzt. Abgeschnittene
Ausgaben (`finish_reason: length`) werden als Fehler mit Rohantwort gespeichert.

Die Anbindung wurde mit einem lokalen Testserver und synthetischen PDF-Daten
geprüft. Es fand kein Live-Test des internen BMW-Dienstes statt. Endpunkte,
Zugriffsrechte, Bildunterstützung, JSON-Modus, Limits und die Erkennungsqualität
auf echten Dokumenten müssen mit eurem tatsächlichen Dienst überprüft werden.
Für eine reproduzierbare Modellevaluation eine feste Modellversion beim Dienst
wählen, falls verfügbar. Ein unveränderter Alias garantiert keine unveränderten
Servergewichte.
