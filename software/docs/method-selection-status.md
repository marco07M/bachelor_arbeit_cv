# Tatsächlicher Auswahlstand am 10.11.2026

**Aktuelle Nutzerentscheidung:** `ocr_rules` (Tesseract plus deterministische
Feldextraktion) ersetzt Docling; zusätzlich wird `ocr_llm` (Tesseract plus
Qwen3-4B-Instruct-2507) aufgenommen. Das separate Profil
`configs/benchmark-five.yaml` und `start_testframework_5.cmd` verwenden somit
`ocr_rules`, `ocr_llm`, `paddle_llm`, `vlm`, `ocr_vlm`. Der Vierer-Starter ohne
zusätzliches Tesseract+LLM bleibt verfügbar. Die vorangegangene Entwicklungs-Gegenprobe hatte
noch `docling`, `paddle_llm`, `vlm` plus optional `ocr_vlm` vorgeschlagen; ihre
Ergebnisse unten bleiben als historischer Nachweis erhalten. Das
Sechsverfahren-Standardprofil bleibt unverändert.

Die zusätzlich genannte Zielkombination PP-OCRv6 + Qwen3-8B beziehungsweise
PaddleOCR-VL-1.6 ist noch nicht integriert. Das vorhandene `paddle_llm` verwendet
weiterhin PP-OCRv5/PP-StructureV3 und Qwen3-4B-Instruct-2507. Der Laufmodus ist
vorläufig und keine abgeschlossene wissenschaftliche Auswahl.

Implementiert sind das [zweistufige Auswahlprotokoll](method-selection.md),
konfigurierbare Evidenzmatrix, geprüfte gruppierte Stichprobe, eingefrorene
Konfigurationen und Auswertungsidentitäten, Testdatensperre, lokale optionale
Inferenz und Wiederverwendung vorhandener Vergleiche. Die bestehenden
Extraktions- und Feldbewertungsfunktionen werden verwendet.

## Tatsächlich durchgeführt

Reine lokale Wiederbewertung gespeicherter Ergebnisse, **keine neuen Modell- oder
OCR-Aufrufe**. Hauptquelle: Vergleich `20261110T110642Z-d0abb263`; Assist-Quelle:
`20261110T111751Z-9b5da18c`. Originaldateien und historische Ergebnisse blieben
unverändert. Die neue Gegenprobe liegt lokal unter
`software/runs/selection-dev-20261110-v3/comparison/report.html`.

Die Stichprobe enthält **eine vorbenutzte Entwicklungs-PDF, zwei Seiten, eine
Schulungs-/Dokumentgruppe, 18 Kursreferenzpersonen und 72 bewertbare Textfelder**.
Die Schriftart wurde für diesen bekannten Fall als `mixed` annotiert,
Qualitätsmerkmale als `multiple_pages;headerless_continuation`. Dies ist keine
neue vollständige Seiten- oder Handschriftannotation. Der eingefrorene Plan
enthält null unabhängige Pilotlisten und keine finalen Testdokumente.

| Kandidat | Exakte Originalfelder / 72 | Exakter Feld-F1, Originalrollen | Levenshtein-F1, Originalrollen | Levenshtein-F1 mit Referenz-Swap |
|---|---:|---:|---:|---:|
| `ocr_llm` | 29 | 48,74 % | 64,87 % | 65,11 % |
| `paddle_llm` | 40 | 60,61 % | 82,74 % | 82,74 % |
| `docling` | 28 | 44,09 % | 59,60 % | 65,19 % |
| `vlm` | 38 | 56,30 % | 80,91 % | 81,95 % |
| `ocr_vlm` | 42 | 62,22 % | 84,47 % | 86,25 % |
| `docling_vlm` | 35 | 51,85 % | 76,73 % | 77,77 % |

Originalrollen werden hier ohne Wertetausch auf denselben Paaren wie im
Referenz-Swap-Vergleich bewertet. Die zusätzliche Sensitivitätsauswertung ohne
Swap mit neu berechneten Paaren ist im Bericht getrennt enthalten. Diese
Tabellenwerte gehören ausschließlich zu den genannten Quellläufen; andere
historische Rohantworten können andere strikte Trefferzahlen liefern.
`ocr_raw` bleibt `diagnostic_only` ohne Feldscore.

Die tatsächlichen Laufbilder sind hashgleich. Gegenüber den eingefrorenen
Auswahlprofilen und gespeicherten Grundprompts wurden in dieser Gegenprobe keine
Abweichungen gefunden. Status `complete` bezeichnet vorhandene technisch gültige
Seitenergebnisse einschließlich `partial`, keine vollständige Feldkorrektheit.
Alle strukturierten Kandidaten behalten denselben Referenznenner.

## Begründung der früheren Empfehlung und offene Entscheidungen

- `docling` bleibt als strukturbasierte, nicht generative Zuordnungsbaseline
  erhalten. Seine Auswahl ist architekturbezogen und nicht durch den höchsten
  Feldscore begründet.
- `paddle_llm` repräsentiert vorläufig OCR+LLM: im Entwicklungsfall 40 statt 29
  exakte Originalfelder und 60,61 statt 48,74 % exakter Feld-F1 gegenüber
  `ocr_llm`. Das rechtfertigt eine vorläufige Rollenbesetzung, keinen allgemeinen
  Qualitätsausschluss von Tesseract+LLM. Beide bleiben für den Pilot messbar.
- `vlm` repräsentiert die direkte visuelle Extraktion. Ein stärkerer Hybridscore
  verdrängt diese experimentell notwendige Vergleichsbasis nicht.
- `ocr_vlm` ist die gezielte optionale OCR-Hinweis-Ablation. Docling-VLM bleibt
  verfügbar, verändert zusätzlich Aufrufselektion und Merge und wird deshalb
  nicht als gleichartige zusätzliche Hauptarchitektur aufgenommen.
- `ocr_raw` wird aus dem Feldranking ausgeschlossen, bleibt aber zur OCR-Diagnose
  erhalten. Legacy-Verfahren werden nicht gelöscht; zusätzliche Basismodelle
  wurden mangels notwendigem Architekturbeitrag nicht integriert.

Unabhängige 30–50 Pilotlisten fehlen, ebenso ausreichende Gruppen und die
erforderliche Abdeckung getrennt maschinenschriftlicher und gemischter Listen.
Die manuelle Gruppen-/Vorbenutzungsprüfung muss für den erweiterten Bestand
erfolgen. Kursreferenzen benötigen eine Eignungsprüfung; für Handschrift-CER/WER
und getrennte Seitenfehler fehlen lokalisierte unabhängige Transkripte.

Die Stufe-A-Matrix enthält für die strukturierten Kandidaten derzeit 25 %
numerisch belegte Kriteriengewichte (Schnittstelle und Versionierung), keinen
gewichteten Gesamtwert. Kontrollierte Prüfung innerhalb 16 GiB und konkrete
Lizenz-/Datennutzungsprüfung sind als harte Bedingungen offen; Laufzeit,
Ressourcen/Kosten, Aufwand und repräsentative Eignung erhalten keine geschätzten
Punktzahlen. Historische lokale Inferenz ist vorhanden, ersetzt aber keine
repräsentative Speichergrenzenprüfung. Seitenzeiten, volle Methodenzeit und
Cachekosten werden nicht zu einem scheinbar kontrollierten Laufzeitvergleich
vermischt. Die finale Auswahl bleibt aus diesen Gründen unentschieden.

## Reproduzieren

Aus `software/` mit einem neuen Ausgabeordner:

```powershell
.\.venv\Scripts\python.exe scripts/replay_method_selection.py --comparison testframework/ergebnisse/20261110T110642Z-d0abb263 --assist-comparison testframework/ergebnisse/20261110T111751Z-9b5da18c --stratum mixed --quality-flags "multiple_pages;headerless_continuation" --output runs/selection-dev-neu
```

Der Helfer ist ausdrücklich auf den bekannten einzelnen Entwicklungsfall
beschränkt. Für einen echten erweiterten Pilotbestand den geprüften Inventar-
und Einfrierworkflow aus [method-selection.md](method-selection.md) verwenden.
Die Befehle `selection run` und `selection compare` bieten absichtlich keinen
finalen Testmodus an. Vorbenutzte Daten nicht als unabhängig umdeklarieren.

## Prüfungen

18 neue gezielte Tests prüfen Evidenzlücken, Gewichtungen, deterministische
Gruppenaufteilung, Vorbenutzung, Testdatensperre, Manipulation, feste Namenspaare,
Fehlerstatus, gleiche Dokumentbasis, Profilverwechslung, Bericht und optionale
lokale Inferenz. Die Gesamtsuite umfasst 693 lokale Tests; zusätzlich bestehen
48 Tests des separaten API-Projekts. Ruff ohne Befund. Der bestehende LaTeX-/
BibTeX-Build erzeugt 29 Seiten; die geänderten Methodikseiten wurden als PNG
visuell geprüft. Keine fehlenden Zitate oder übervollen Boxen im finalen Log;
der bestehende epstopdf-Hinweis zu deaktiviertem Shell-Escape bleibt bestehen.
