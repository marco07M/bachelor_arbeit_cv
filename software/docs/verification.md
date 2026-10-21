# Verifikationsprotokoll

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
