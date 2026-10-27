# GATE-Zugang und Endpunkte

Aus dem Remote-Commit `89a895f` übernommene Verbindungs- und Onboarding-Hinweise.
Die Angaben müssen zu eurer Freischaltung passen; ein echter Zugang wurde hier nicht geprüft.
Alle Befehle aus `software/api_firmen_pc/` ausführen. Zur Verbindungsprüfung
`python main.py check --connect` im separat geöffneten Firmen-Terminal verwenden.


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
`python main.py check --connect` in einem von BMW freigegebenen Netzwerk. Keine
Sicherheitskontrollen umgehen und Zugangsdaten nicht an nicht freigegebene
Geräte oder Netze übertragen.


Die aktuelle Bedienung steht in der [API-Anleitung](../README.md).
