# LLM und VLM über eine API verwenden

Alle Befehle aus `software/` ausführen. Die lokale Standardkonfiguration
`configs/local.yaml` bleibt verwendbar. Mit `backend: api` laufen LLM und/oder
VLM beim konfigurierten Dienst; Rendering, Tesseract, Exporte und Excel-Abgleich
laufen weiterhin auf deinem Rechner.

## GATE-Zugang und Endpunkte

GATE ist ein REST-Dienst mit OpenAI-kompatibler Chat-Completions-Schnittstelle.
Die Projektvorlage `configs/api-bmw.yaml` verwendet WebEAM-OAuth
(Client-Credentials) plus einen APIM-API-Key. Für die Region muss der passende
Endpunkt gewählt werden:

| Region | QA / INT | PROD |
| --- | --- | --- |
| EU | `https://api.int.gcp.cloud.bmw/llmapi/v1` | `https://api.gcp.cloud.bmw/llmapi/v1` |
| US | `https://api.int.gcp.cloud.bmw/llmapi/us/v1` | `https://api.gcp.cloud.bmw/llmapi/us/v1` |

Die Dokumentation nennt außerdem die alternativen API-Hosts
`https://api-int.bmwgroup.net/llmapi` (QA) und
`https://api.bmwgroup.net/llmapi` (PROD). Nutze für dieses Projekt zunächst
die obigen Endpunkte; mische nicht Hosts oder Zugangsdaten verschiedener Stages.
EU-Daten müssen über EU-Endpunkte, US-Daten über US-Endpunkte verarbeitet werden.

Für die Token-Anfrage nennt die Dokumentation diese WebEAM-Endpunkte:

| Stage | Token-Endpunkt |
| --- | --- |
| QA / INT | `https://emea.int.alpha.sso.bmwgroup.com/auth/oauth2/realms/root/realms/alpha/access_token` |
| PROD | `https://emea.prod.alpha.sso.bmwgroup.com/auth/oauth2/realms/root/realms/alpha/access_token` |

Die API-Dokumentation führt diese Token-URLs nach Stage und die Modell-API-URLs
nach Stage **und** Region auf. Für US-Zugänge oder abweichende Anwendungs-
Registrierungen die passende Kombination im Onboarding bestätigen lassen.

### Onboarding und erforderliche Berechtigungen

Vor dem ersten Aufruf brauchst du ein aktives BMW-APP-ID sowie Zugriffsrechte
auf die BMW-Portale:

1. Im WebEAM-Portal mit Rolle **Operations Manager** `New Configuration` →
   `M2M` wählen und den `alpha`-Realm verwenden. Die Konfiguration erstellen
   und `Client ID` (Dashboard) sowie `Client Secret` (registrierte E-Mail)
   sicher übernehmen.
2. Im API-Management-Portal für dieselbe Anwendung das passende Produkt
   abonnieren: Stage `int` → **LLM API QA**, Stage `prod` → **LLM API PROD**.
   In den Zugangsdaten `Source Type: WEN`, `API Key: <WebEAM client_id>`,
   `Client Type: public` und `Client Realm: machine2machine` eintragen.
   Die Anfrage muss den Anwendungsfall und die geplante Umsetzung beschreiben.
3. Nach Freigabe den API-Key im APIM Developer Portal unter den Zugangsdaten
   der Anwendung abrufen. Die Freigabemail enthält den Schlüssel laut Anleitung
   nicht. API-Key und WebEAM-Zugangsdaten müssen zur selben Anwendung gehören.
4. QA und PROD benötigen getrennte WebEAM-Zugangsdaten; API-Keys sind ebenfalls
   stage-spezifisch. QA-Zugangsdaten funktionieren nicht gegen PROD und umgekehrt.
5. Das aktuelle BMW-CA-Zertifikat von
   <https://trustbundle.bmwgroup.net/BMW_Trusted_Certificates_Latest.pem>
   herunterladen und lokal außerhalb des Repositorys speichern.

Details und Voraussetzungen:
[Onboarding](https://pages.atc-github.azure.cloud.bmw/Data-Transformation-AI/llm-api/get_started/onboarding.html),
[Authentifizierung](https://pages.atc-github.azure.cloud.bmw/Data-Transformation-AI/llm-api/api_reference/authentication.html),
[FAQ](https://pages.atc-github.azure.cloud.bmw/Data-Transformation-AI/llm-api/faq.html).

### Netzwerkzugriff außerhalb des BMW-Intranets

Die GATE-Unterlagen nennen keine eindeutige Zusage, ob die API aus dem
öffentlichen Internet erreichbar ist oder zwingend BMW-Intranet/VPN benötigt.
Die `bmw`-Domain und erfolgreiche Anmeldung an den Portalen belegen für sich
allein nicht, ob die API-Netzwerkroute von einem privaten Gerät funktioniert.
Ein Zugriff außerhalb des Intranets ist daher **nicht garantiert**: Er hängt
von BMW-Netzwerkregeln, VPN, Firewall und Proxy-Konfiguration ab. Die FAQ weist
explizit auf mögliche Proxy-Probleme hin.

Frage bei eurem BMW-Netzwerk-/API-Management-Team nach, ob aus dem vorgesehenen
Laufzeitnetz HTTPS-Zugriff (Port 443) auf den ausgewählten API- und
WebEAM-Token-Endpunkt erlaubt ist und ob ein Proxy oder eine No-Proxy-Regel
benötigt wird. Um die Verbindung zu prüfen, nutze den unten beschriebenen
`api-check --connect` in einem von BMW freigegebenen Netzwerk. Keine
Sicherheitskontrollen umgehen und Zugangsdaten nicht an nicht freigegebene
Geräte oder Netze übertragen.

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

Der Starthelfer fragt die Verbindungswerte ab. API-Key, Client-ID und
Client-Secret werden verdeckt eingegeben; übrige Werte wie Endpunkt, Modellname
und Zertifikatpfad sind sichtbar. Er setzt ausschließlich
Prozess-Umgebungsvariablen. Anschließend startet er die Python-Anwendung. Nach
dem Lauf entfernt er Schlüssel, Client-Zugangsdaten und CA-Pfad aus seiner
Umgebung, auch bei einem Fehler. Er speichert keine Schlüsseldatei und keine
Benutzer- oder Systemumgebungsvariablen. Die verdeckten Antworten stehen nicht
als Befehle in der PowerShell-Historie. `RemoteSigned` gilt nur für diesen
PowerShell-Prozess; es wird keine dauerhafte Ausführungsrichtlinie geändert.

Mit `-CheckOnly` statt `-InputFolder ...` nur die Konfiguration prüfen, ohne
API-Verbindung oder Dokumentverarbeitung. Für eine Stichprobe
`-InputFolder data/pdfs_eingabe` angeben. Unbekannte Angaben kannst du beim
Einrichten mit Enter überspringen; die Prüfung zeigt fehlende Variablennamen.
Die Modellkennungen müssen zu eurem freigeschalteten Modellkatalog passen.

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
BMW_AI_BASE_URL=https://api.int.gcp.cloud.bmw/llmapi/v1
BMW_AI_TOKEN_URL=https://emea.int.alpha.sso.bmwgroup.com/auth/oauth2/realms/root/realms/alpha/access_token
BMW_AI_API_KEY_HEADER=x-apikey
BMW_AI_SCOPE=machine2machine
BMW_CA_BUNDLE=C:\Users\DEIN_BENUTZER\.participant-bench-private\BMW_Trusted_Certificates_Latest.pem
BMW_LLM_MODEL=DEIN_LLM_MODELL
BMW_VLM_MODEL=DEIN_VLM_MODELL
```

Das Beispiel ist für **EU QA / INT**. Für PROD müssen die zugehörigen PROD-
Zugangsdaten, der PROD-API-Key sowie die PROD-API- und Token-URLs verwendet
werden. `BMW_AI_API_KEY` kommt aus APIM; `BMW_AI_CLIENT_ID` und
`BMW_AI_CLIENT_SECRET` aus WebEAM. Beim Onboarding muss der API-Key zum
WebEAM-`client_id` und dieselbe Anwendung gehören. Die Modellnamen müssen für
deine Anwendung freigeschaltet und für LLM bzw. VLM geeignet sein. Der
Anfragepfad kann leer bleiben; Standard ist `chat/completions`.

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
| `BMW_CA_BUNDLE` | Optionaler Pfad zum aktuellen BMW-CA-Zertifikat im PEM-Format |
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
