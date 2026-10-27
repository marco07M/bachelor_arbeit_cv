# OCR systematisch kalibrieren

Die Erweiterung verwendet den vorhandenen Benchmark, Tesseract, Tabellenregeln,
lokales OCR/LLM, PDF-Rendering und die bestehende Feld-/Signaturbewertung.
Sie läuft **ausschließlich lokal**. Konfigurierte API-Modelle werden vor der
Verarbeitung abgewiesen; Zugangsdaten sind nicht erforderlich. Die bisherigen
Standardparameter werden durch einen Vergleichslauf nicht geändert.

Alle Befehle aus `software/` ausführen. Neue Abhängigkeit für exportierbare
Reliability-Diagramme ist Matplotlib; SciPy implementiert die kleinen
Kalibrierungsmodelle. Umgebung aktualisieren:

```powershell
uv sync --locked --extra models
```

Für reine Tesseract-/Regelläufe reicht die Basisinstallation ohne `--extra models`.
Das separate Tesseract-Setup bleibt erforderlich. Gewichte werden nicht automatisch
heruntergeladen. Pakete und lokale Modellrevisionen bleiben über `uv.lock` und
die vorhandenen Modellmanifeste nachvollziehbar.

## Referenzen vorbereiten

Zuerst eine überschaubare Stichprobe wählen, z. B. 100 Dokumente:

```powershell
.venv/Scripts/participant-bench.exe ocr-reference --input vorverarbeitung/ausgabe/pdfs --output data/ocr-reference-v1 --sample-documents 100 --seed 42
```

Ohne `--sample-documents` werden alle lesbaren PDFs inventarisiert. Die Auswahl
ist dokumentweise und reproduzierbar, aber eine Zufallsstichprobe allein
garantiert keine Repräsentativität. Fehlende Layouts, Handschrift, schlechte Scans
und Seiten ohne Personen müssen bei der Zusammenstellung berücksichtigt werden.
Defekte/verschlüsselte PDFs stehen als Fehler im Inventar; auf diesen ist keine
Seitenreferenz angelegt. Der Qualitätsnenner umfasst die annotierten lesbaren
Dokumente, nicht automatisch den gesamten ursprünglichen Bestand.

Es entstehen:

| Datei | Manuelle Bearbeitung |
| --- | --- |
| `dataset.json` | Originalpfade, SHA256, Seitenzahlen und exakte Duplikate; nicht bearbeiten |
| `documents.csv` | Abhängigkeitsgruppe, Layout-/Qualitätsstratum, Gruppenprüfung |
| `pages.csv` | Jede Seite einschließlich Deckblatt prüfen; Textart und Prüfstatus setzen |
| `participants.csv` | Genau eine Referenzzeile je tatsächlicher Person; anfangs nur Kopfzeile |
| `text/*.txt` | Optional den vollständigen Seitentext unabhängig transkribieren |

Die Dateien werden **nicht aus Modellvorhersagen vorbefüllt**. Existierende
Referenzordner werden nicht überschrieben. Personalnummern in Tabelleneditoren
als Text behandeln, damit führende Nullen erhalten bleiben.

In `documents.csv`:

- `dependency_group`: Zusammengehörige, nahezu identische Dokumente und mehrfach
  verwendete verwandte Vorlagen zusammenfassen. Exakt gleiche PDF-Bytes werden
  bereits dedupliziert. Inhaltliche Nähe wird nicht automatisch zuverlässig erkannt.
- `stratum`: Beispielsweise `layoutA-typed-clean` oder `layoutB-mixed-scan`.
  `unassigned` muss ersetzt werden. Es ist eine manuell festgelegte Schicht.
- `grouping_reviewed`: Erst nach der Prüfung auf `true` setzen. Keine Personennamen
  als Gruppenkennungen verwenden.

Dann die Aufteilung einfrieren:

```powershell
.venv/Scripts/participant-bench.exe ocr-split --dataset data/ocr-reference-v1 --seed 42
```

Ungefähr 60 % Entwicklung, 20 % Validierung und 20 % Test, geschichtet und nach
Abhängigkeitsgruppen. Ganze Gruppen bleiben zusammen; daher sind die Anteile
bei wenigen/großen Gruppen nur näherungsweise erreichbar. Mindestens fünf Gruppen
sind erforderlich. Die tatsächlichen Dokumentzahlen stehen in `splits.json`.
Ein erneutes Aufteilen oder spätere Änderungen an Gruppen/Inventar werden abgewiesen.
Für eine neue Datensatzversion einen neuen Ordner verwenden.

In `pages.csv` jede Seite mit `reviewed=true` bestätigen. `content_type` ist
`typed`, `handwritten`, `mixed` oder `other`. Seiten ohne Personen haben keine
Zeilen in `participants.csv`, werden aber vollständig bewertet. Es gibt keine
automatische Aussortierung nach Dokumentart.

Für `participants.csv` gelten:

- `document_id` und `page_number` stammen aus dem Inventar; `row_ref` ist nur eine
  sichtbar gedruckte Zeilennummer. Keine künstliche Nummerierung als Quellbeleg.
- `bbox` ist optional `x0,y0,x1,y1`, normiert auf die analysierte aufrechte Seite.
  Gedruckte Zeilennummern oder geprüfte Positionen verbessern die unabhängige
  Zuordnungsbewertung. Sonst verwendet der bestehende Benchmark einen als solchen
  ausgewiesenen Inhaltsvergleich; dieser ist keine unabhängige Identitätsprüfung.
- Für jedes Textfeld ist ein Status nötig: `read`, `empty`, `illegible`, `uncertain`.
  Nur bei `read` steht ein Wert daneben. Bei `empty` ist er leer, bei unbekannten
  Angaben ebenfalls leer mit entsprechendem Status. Fehlende Benutzerfelder
  verschieben keine Kurzzeichen; die Person bleibt als Referenz enthalten.
- `signature_present` ist `true`, `false` oder `unknown`. Das Label beschreibt
  ausschließlich die sichtbare Anwesenheit einer Markierung, keine Identität,
  Echtheit oder verifizierte Teilnahme. Unterschriften werden nicht transkribiert.

Reine CER/WER-Messung benötigt unabhängig erstellten Seitentext in der zugehörigen
TXT-Datei und `text_reviewed=true`. Ohne diesen Text bleiben diese Metriken
unbestimmt; sie werden nicht aus den Personenfeldern als vermeintliche Textreferenz
rekonstruiert. `quality_flags` erlaubt semikolongetrennt `poor_image_quality`,
`skew`, `handwritten`, `shadow`, `low_contrast`, `cropped`, `wrapped_text`,
`duplicate_template`. Keine personenbezogenen Freitexte in diese Kategorien schreiben.

## Baseline und kontrollierte Varianten

```powershell
.venv/Scripts/participant-bench.exe ocr-calibrate --dataset data/ocr-reference-v1 --config configs/calibration.yaml --output runs/ocr-exp01
```

[`configs/calibration.yaml`](../configs/calibration.yaml) beginnt mit der bestehenden
lokalen Baseline. Jede Variante wird durch rekursives Zusammenführen **neu aus
dieser Baseline** erzeugt; Varianten werden nicht aufeinander gestapelt. Enthalten
sind 200/300/400 DPI, PDF-Text bevorzugen, Linien behalten, globale/adaptive
Binarisierung und Deskew. Weitere einzeln prüfbare Optionen unter
`ocr.preprocessing`: `grayscale`, `contrast`, `denoise` (0/3/5/7), `threshold`
(`none`/`otsu`/`adaptive`), `deskew`, `max_skew_degrees`, `crop` und `scale`.
`crop` ist ein **explizit konfiguriertes** normiertes Rechteck, keine automatische
Erkennung relevanter Seiten. Schatten/Schräglagen können weiterhin ungelöst bleiben.

Beispiel für eine zusätzliche einzelne Kontrastvariante:

```yaml
variants:
  - name: contrast
    overrides:
      ocr:
        preprocessing:
          contrast: 1.2
```

Für OCR/LLM kann eine Variante `method: ocr_llm` angeben. Dafür müssen die lokalen
Gewichte aus der Basiskonfiguration bereits installiert sein. Derselbe OCR-Input,
dieselben Referenzen und dieselben Bewertungsregeln bleiben erhalten.
Unterschriften werden getrennt am Bild geprüft; `signature.backend: opencv`
ist die konservative Baseline. Eine konfigurierte lokale VLM-Zusatzstufe ist möglich
und wird in Laufzeit/Ressourcen erfasst. Ihre Selbstauskunft wird nicht zu einer
Signaturwahrscheinlichkeit umgedeutet.

`ocr.source: prefer_pdf` untersucht eingebettete Wörter samt Positionen. Bei
brauchbarem rein digitalem Text entfällt Bild-OCR. Größere Rasterbilder verhindern,
dass nur ein digitaler Kopf über einer eingescannten Tabelle übernommen wird.
Defekte Textzeichen oder zu wenige Wörter lösen den bisherigen OCR-Pfad aus.
Die Prüfung bleibt eine konservative Heuristik und muss mit Referenzen geprüft
werden; PDF-Text wird nicht pauschal als fehlerfrei behandelt. Er hat keinen
erfundenen OCR-Konfidenzwert. Bildvorverarbeitung ist bei direktem PDF-Text nicht
anwendbar. Crop, Skalierung und Deskew bilden OCR-Wortpositionen zurück auf das
ursprüngliche Seitenbild ab; die Signaturstufe sieht weiterhin dieses Bild.

## Auswahl ohne Testdaten

1. Auf Entwicklung werden Varianten verglichen und feldweise Kalibratoren gefittet.
   Es findet zunächst kein Training einer neuen OCR-Engine statt.
2. Der Validierungsanteil wird nochmals nach ganzen Gruppen halbiert:
   `validation_fit` dient der Schwellenwertsuche, `validation_audit` bleibt dafür
   unbenutzt und kontrolliert anschließend die zuvor vorgeschlagene Variante.
3. Die Empfehlung benötigt auf dem Audit eine F1-Verbesserung ohne Rückgang der
   vollständigen Zeilen oder der einzelnen Feld-Recalls. Bei gleicher Qualität
   ist ein vorab konfigurierter Laufzeitvorteil erlaubt. Technische Ausfälle oder
   schlechterer Signatur-Recall verhindern eine Übernahme. Zu wenige unabhängige
   Auditgruppen führen zur Beibehaltung der Baseline.
4. Konfiguration, Kalibratoren und Regeln werden in `frozen.json` versiegelt.
   Testdokumente werden bis dahin nicht gerendert oder extrahiert. Ihre Inventar-
   und Referenzdateien werden zur Integritätsprüfung gehasht und validiert.

Die Schwellenwertsuche maximiert die Zahl akzeptierter Felder bei vorgegebener
empirischer Precision (`target_precision`, Standard 0,98). Zusätzlich gelten
Mindestfallzahlen. Ein Feldkalibrator benötigt standardmäßig 50 beobachtete
Feldwerte, mindestens fünf richtige und fünf falsche Fälle sowie mindestens
drei unabhängige Dokumentgruppen (`min_documents`). Bei ausschließlich richtigen
oder sehr wenigen beobachteten Feldern ist keine belastbare Anpassung möglich.
Leere, unleserliche oder nicht eindeutig lokalisierte Felder haben keinen Score.

Unterstützt sind monotone Sigmoid-/Platt-artige Skalierung und gewichtete
isotone Regression. Der Rohscore ist das Minimum der zugehörigen Tesseract-
Wortkonfidenzen geteilt durch 100: **keine vorab kalibrierte Wahrscheinlichkeit**.
Das Kalibrierungsereignis lautet „gesamter Feldwert mit der dokumentierten
Normalisierung korrekt und der richtigen Personenzeile zugeordnet“.
Eigene Kalibratoren pro Feld und Variante verhindern das Vermischen unterschiedlicher
Engines. Zu wenig Evidenz oder fehlender Score bedeutet Nachkontrolle.

Nach der Schwellenwahl muss die Auditgruppe die Zielprecision und Mindestzahl
unabhängiger Gruppen erfüllen. Brier Score und ECE dürfen gegenüber dem Rohscore-
Vergleich nicht schlechter werden. Andernfalls bleibt der Feldstatus `review_only`.
Die empirischen Zahlen sind keine Garantie für die zukünftige Fehlerquote und
kein statistischer Nachweis bei beliebig kleinen Stichproben. Brier Score misst
auch Diskriminierung und Datenunsicherheit; seine Veränderung allein beweist keine
Kalibrierung. Grundlagen: [Probability calibration](https://scikit-learn.org/stable/modules/calibration.html),
[SciPy PAVA](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.isotonic_regression.html).

## Ausgaben kontrollieren

`runs/ocr-exp01/report.html` zeigt Entwicklung und unabhängiges Audit getrennt.
SVG und PNG der Reliability-Diagramme sind eigenständige exportierbare Dateien.
Fehlende Zähler/Nenner werden als unbestimmt behandelt.

| Datei | Inhalt |
| --- | --- |
| `experiment.json` | Datensatzversion, vollständige Varianten, Paket-/Quellcodeidentität |
| `comparison.json`, `comparison.csv` | Qualität, Status und Ressourcenvergleich |
| `field_metrics.csv` | Exact Match, Precision/Recall/F1, CER und unbekannte Werte je Feld |
| `reliability.csv`, `reliability-*.svg/png` | Bin-Zähler, beobachtete Korrektheit, ECE/Brier in JSON |
| `thresholds.csv` | Precision/Recall, Abdeckung und Prüfaufwand je Schwelle |
| `decisions.csv` | `accepted`, `review`, `failed`, Probability nur bei gefittetem Kalibrator |
| `error_categories.csv` | Interne Dokument-/Seitenkennung und Fehlerkategorie, keine Namen |
| `*-document-times.csv` | Summe gemessener Seitenzeiten je Dokument; gemeinsame Vorbereitung/Ladezeit separat |
| `frozen.json` | Auswahl, Schwellenwerte, Daten-/Engine-/Codefingerabdrücke und Versiegelung |
| `r/*/<Run-ID>/` | Bestehende vollständige Benchmark-Ausgaben samt Originaltext/Modellantworten |

Die Unterläufe enthalten zusätzlich `calibration_metrics.json`,
`field_confidences.csv`, `normalized_fields.csv` und `error_categories.csv`.
`normalized_fields.csv` speichert Rohwert und explizite Bewertungsnormalisierung
nebeneinander; die Extraktion wird nicht umgeschrieben. Namen/Abteilungen werden
für Vergleiche NFC-/Leerraum-normalisiert und ohne Beachtung der Großschreibung
verglichen; Personalnummern bleiben exakt einschließlich führender Nullen.
Raw- und normalisierte Seitentext-CER/WER werden separat ausgewiesen.

Feldzuordnung verwendet die vorhandene gedruckte Zeilennummer/Position oder den
ausgewiesenen Inhaltsfallback. Extra-/fehlende Zeilen bleiben im Nenner.
Allgemeine Feldextraktion hat keine natürliche Anzahl aller True Negatives:
deshalb FDR statt einer erfundenen allgemeinen FPR. Eine FPR wird gesondert
für explizit leere Referenzzellen definiert. Signaturbewertung enthält Precision,
Recall, F1, FP/FN und die bestehende Confusion Matrix mit unbekannten Entscheidungen.
Unsichere positive Signaturen zählen dabei nicht als erfolgreiche Erkennung.

Fehlerkategorien unterscheiden unter anderem OCR-Erkennung, ähnliche Zeichen,
fehlende Zeichen, Feldextraktion/Zuordnung, fehlende/zusätzliche Personen und
Signaturen. Mehrfach gedruckte Zeilennummern markieren mögliche Duplikate;
sie werden nicht ungeprüft gelöscht. Automatische Ursachen sind **heuristische
Hinweise**. Schlechte Bildqualität wird zusätzlich manuell kategorisiert.
Über tatsächliche falsch erkannte Glyphen oder Personenzuordnung entscheidet die
Referenz; ein Wortbeleg allein beweist keine korrekte Zeichenlesung.

Laufzeiten umfassen bestehende Vorbereitungs-, OCR-, Struktur- und Signaturzeiten;
RAM/GPU-Peaks stammen vom vorhandenen Ressourcenmonitor. Cachetreffer und
zugerechnete ursprüngliche OCR-Zeiten werden getrennt gespeichert. Nachkontrollzeit
ist mit `review_seconds_per_field` ausdrücklich ein Szenario, keine gemessene Arbeit.
Vor einer wissenschaftlichen Laufzeitaussage sind kontrollierte Wiederholungen
und getrennte Warm-/Kaltcachemessungen sinnvoll.

## Finale Bewertung und spätere Anwendung

Erst nach Abschluss der Kalibrierung:

```powershell
.venv/Scripts/participant-bench.exe ocr-final --experiment runs/ocr-exp01
```

Das unabhängige Testset wird genau für diese eingefrorene Auswahl ausgewertet,
ohne Fit oder Schwellenwertsuche. Bericht unter `runs/ocr-exp01/test/report.html`.
Ein abgeschlossener Test wird nicht erneut ausgeführt. Ein reiner technischer
Abbruch kann mit `ocr-final --experiment ... --resume` unverändert fortgesetzt
werden. Referenzänderungen, andere OCR-/Modellversionen, geänderte Pakete oder
relevante Quellcodeänderungen werden abgewiesen. Die Versiegelung schützt vor
unbemerkten Änderungen, nicht vor einem absichtlichen Umgehen aller Prüfungen.
Testdaten nach Einsicht nicht erneut zur Optimierung verwenden.

Für neue PDFs ohne Ground Truth:

```powershell
.venv/Scripts/participant-bench.exe ocr-apply --experiment runs/ocr-exp01 --input vorverarbeitung/ausgabe/pdfs
```

Dieser Schritt lädt keine Referenzlabels und fittet nichts. Er exportiert
Feldentscheidungen und den normalen Extraktionsbericht. `review` und `failed`
verlangen Kontrolle. Ohne neue Referenzen wird keine neue Erkennungsqualität
behauptet. Original-PDFs und Ground Truth bleiben unverändert.

Abgebrochene Entwicklungsläufe fortsetzen:

```powershell
.venv/Scripts/participant-bench.exe ocr-calibrate --dataset data/ocr-reference-v1 --config configs/calibration.yaml --output runs/ocr-exp01 --resume
```

Erfolgreiche Läufe werden wiederverwendet; offene Seiten verwenden den bestehenden
Runner-Resume und OCR-Cache. Parameteränderungen benötigen einen neuen Experimentordner.

## Funktionsprüfung ohne Unternehmensdaten

```powershell
.venv/Scripts/python.exe scripts/make_calibration_smoke.py --output data/calibration-smoke
.venv/Scripts/participant-bench.exe ocr-calibrate --dataset data/calibration-smoke/reference --config data/calibration-smoke/experiment.yaml --output runs/c-smoke
.venv/Scripts/participant-bench.exe ocr-final --experiment runs/c-smoke
```

Der Generator erstellt bekannte synthetische Personen, unterschiedliche
Spaltenreihenfolgen und gruppierte Kopien. Referenztext/Felder werden aus der
unabhängig festgelegten Konstruktion geschrieben, nicht aus OCR-Ergebnissen.
Die kleine Stichprobe kann ausdrücklich für eine Konfidenzkalibrierung oder
Übernahmeempfehlung zu klein sein. Das ist ein Funktionstest, kein Qualitätsbeleg
für echte Scans oder Handschrift. Reale Referenzen sind vor produktiven
Schwellenwerten weiterhin erforderlich.
