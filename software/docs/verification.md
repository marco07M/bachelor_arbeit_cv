# Verifikationsprotokoll

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
