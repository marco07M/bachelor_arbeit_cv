# Wissenschaftliche Validität: ergänzende Diagnostik

Stand: 17.11.2026. Keine Änderung von Extraktion, Matching, Ground Truth oder
bisherigen Qualitätsdefinitionen. `scientific_validity.py` projiziert vorhandene
Feld-/Teilnehmerentscheidungen; `scientific_validity_report.py` stellt sie dar.
Neue Analysen erzeugen `validity.html`, JSON und CSV neben dem vorhandenen Report.

## Ist-Zustand und Entscheidungen

| Anforderung | Vorhanden / Ergänzung |
|---|---|
| Gemeinsame Referenz und Datenumfang | Eingefrorene Snapshots, Prüfsummen, Kurszuordnung und Prüfung zusätzlicher Kandidaten beibehalten. Zusatzdiagnostik prüft gleiche Referenzfelder/Normalisierungen nochmals; keine günstige Schnittmenge. |
| Exact Recall/F1, Coverage, Ø erkannt, Legacy-Soft-F1 | Vorhandenes `metrics.scores` unverändert verwendet. |
| Fünf Feldstatus und Signaturausschlüsse | Vorhandene Regeln erhalten; Signaturen keine Textfelder. Referenzpersonen bleiben im Nenner. |
| Dokumentbasierte Teilmenge | Unabhängige Originalprüfung in `missing_fields.html` vorhanden; Gesamtbewertung unverändert. |
| h/m/g | Vorhandene GT-only Gruppen; g disjunkt, fehlende Labels unklassifiziert. |
| Matching | Vorhandene fünf Ansichten; zusätzliche kompakte Gegenüberstellung mit P-/Paarungs-/Swap-Zahlen. |
| ANLS und Dreifeldkonsistenz | Neu, separat; kein Austausch des bestehenden Ähnlichkeitsmittels. |
| Seitenstrata | Neu mit unabhängigem, an Snapshot/PDFs gebundenem Seiten-/Personenprotokoll; Ausgabeseiten erzeugen keinen Referenznenner. |
| Dokumentqualität | Vorhandene manuelle Dokumentflags plus optionale Seitenkategorie; Pixelgröße/Rotation separat, Scan-DPI nicht geraten. |
| Effizienz | Vorhandene Lade-/Warm-up-/Seiten-/VRAM-/Cachewerte ergänzt um Syntax, gespeicherte Schemaentscheidungen und Seitenversuchshistorie. |
| Rohtext-OCR | Separate Textauffindbarkeit möglich; kein strukturiertes F1 und ohne Seitentranskript keine CER/WER. |

## ANLS-Feldähnlichkeit und Zeilenkonsistenz

Aktivierung mit `analyze --anls`. Projektadaption auf feste `original_roles`-Paare:

`A = sum(s_i if 1-s_i < 0.5 else 0 for i in R) / R`.

`s_i` ist die vorhandene normalisierte Levenshtein-Gutschrift. Fehlende/ungültige
Ausgaben erhalten 0; leere/unbekannte/maskierte Referenzen sind wie bisher nicht
in R. R=0 ist undefiniert. Bei genau s=0,5 gilt 0, entsprechend der geprüften
[Pix2Struct-Implementierung](https://github.com/google-research/pix2struct/blob/main/pix2struct/metrics.py).
Der Formelsatz der Originalpublikation lässt den Gleichheitsfall offen; unsere
Grenzregel ist daher ausdrücklich dokumentiert und getestet.

Normalisierung unverändert: NFC für Text, Whitespace zusammenziehen, Kleinschreibung
sofern `case_sensitive=false`; IDs mit `normalized_user_id` und Entfernung führender
Nullen nur gemäß eingefrorener Konfiguration. Keine Umlautersetzung, phonetische
Korrektur oder neue Namenssortierung. Unsichere Ausgaben folgen weiterhin dem
vorhandenen `score_uncertain_values`.

Zusätze verändern A nicht, ihre P-/FP-Beiträge bleiben im globalen Exact-/Soft-F1.
A ist kein F1 und keine alleinige Gesamtnote. `detected_similarity` ignoriert
Fehlwerte und hat D als Nenner: Vier Referenzfelder, zwei richtige Ausgaben ergeben
Coverage=50 %, Ø erkannt=100 %, A=50 %. Legacy-Soft-F1 bleibt unverändert verfügbar.

N₃ zählt alle Referenzpersonen mit drei lesbaren Identitätsfeldern Vorname,
Nachname, Personalnummer, einschließlich nicht erkannter Personen. C₃ verlangt
das vorhandene strikte `identity_exact` und exakte normalisierte Originalrollen
aller drei Felder auf einem zuverlässigen festen Paar. Mehrdeutige Zuordnungen
zählen nicht als Treffer. C₃/N₃ bei N₃=0 undefiniert. Teilreferenzen und mehrdeutige
Referenzanker separat ausgewiesen. Organisation bleibt der Vierfeldkorrektheit vorbehalten.

## Unabhängige Seitenstrata

`scientific/page_annotations.template.json` als neue Datei bearbeiten:

- `pages`: `role=first|continuation|non_participant|unknown`,
  `header=present|absent|unknown`, `scan_quality=clean|degraded|unknown`.
- `participants`: eine Originalseite je Referenzperson, sonst beide Positionsfelder
  null; keine automatische Übernahme von Modellpositionen.
- Bekannte Angaben brauchen `independent_of_predictions=true`, `reviewer`,
  ISO-`reviewed_at`, `note` beziehungsweise `anchor_note` und das hashgeprüfte Original.
- Falsche Kurse/Seiten, Dubletten und widersprüchliche Rollen werden abgelehnt.
  First meint die erste Teilnehmerseite, nicht automatisch PDF-Seite 1.

Ohne Lokalisierung bleiben sämtliche Beiträge in unknown. Annotierte fehlende
Personen bleiben in ihrer Gruppe. `scores`/`aggregate_participants` poolen vorhandene
Zähler ohne neue Paarung. Gruppenspezifisches F1 ist auf GT-Paare bedingt;
ungepaarte Zusätze bleiben separat und global erhalten. h/m/g weiterhin GT-only.

```powershell
.\.venv\Scripts\python.exe testframework/main.py analyze `
  --report testframework/ergebnisse/BESTEHEND --output testframework/ergebnisse/NEU `
  --anls --document-annotations data/PRUEFUNG/document-reviews.json `
  --page-annotations data/PRUEFUNG/page-annotations.json
```

Alle Zusatzoptionen unabhängig optional. Lokale Artefakte enthalten Referenzwerte
und gehören nicht in öffentliche Repositories. Ungeprüfte Fälle bleiben global bewertet.

## Ursachen und Stabilität

Mehrere Belegachsen je Fehler: Dokument, Wahrnehmung, Zuordnung, Validierung/
Filter/Übergabe, Zusatzwert, Referenz/Matching, unbekannt. Befunde überlappen;
ihre Summe ist keine Zahl unabhängiger Fehler. Eindeutige Fehlerzahlen separat.
Gleiche Werte anderswo sind Hinweise, Zusatzwerte keine bewiesenen Halluzinationen.
Direkte VLM-Verfahren erben keine Schuld aus fehlender Hilfs-OCR.

JSON-Syntax am gespeicherten Literal; Schemaquote aus explizitem `parse_status`,
keine unabhängige Revalidierung alter Schemas. Native Tabellen-JSONs zählen nicht
als generative Antworten; doppelte Assignment-Ablage zählt einmal. Letzte
gespeicherte Antworten, keine vollständige Inferenzhistorie; Cacheantworten keine
neuen Aufrufe. Gültige Seiten / erwartete Seiten umfasst auch Ausfälle.

`attempts.jsonl` belegt wiederholte Seitenverarbeitungen, keine Modell-Retryzahl.
Modell-Retries und Cold-/Warm-Start bleiben ohne Belege unbekannt. GPU-Peak ist
der gespeicherte Allocator-Wert des Quelllaufs, keine globale Gerätespitze oder
Teilumfangsmessung. Dokumentzeit summiert vorhandene Seitenzeiten ohne Laden.
Render-DPI ist keine ursprüngliche Scanauflösung; Scanqualität wird nicht geraten.

`ocr_raw`: Nur unabhängig lesbare Originaltranskripte mit einer Originalseite.
Die vollständige normalisierte Feldzeichenfolge muss an Wortgrenzen im Seitentext
stehen; „2“ in „2020“ genügt nicht. Wiederholte Namen/Organisationen bestätigen
keine Identität. Lesbare Referenzabweichungen werden mit ihrem Originalwert geprüft.
Keine Precision-/CER-/WER-Aussage; keine Signaturtranskription.

## Geprüfte Primärquellen und Übertragbarkeit

Prüfdatum 17.11.2026; neue BibTeX-Einträge in `bachelorarbeit/verified_sources.bib`,
bestehende Donut-/Docling-/FUNSD-Einträge weiterverwendet, Zotero-Export unverändert:

- [DUE, NeurIPS 2021](https://datasets-benchmarks-proceedings.neurips.cc/paper_files/paper/2021/hash/069059b7ef840f0c74a814ec9237b6ec-Abstract-round2.html):
  aufgabengerechte Metriken und diagnostische Teilmengen, kein dimensionsübergreifender Gesamtscore übernommen.
- [DocVQA](https://openaccess.thecvf.com/content/WACV2021/papers/Mathew_DocVQA_A_Dataset_for_VQA_on_Document_Images_WACV_2021_paper.pdf)
  und [ST-VQA](https://arxiv.org/pdf/1905.13648): ANLS als Feldadaption bezeichnet,
  kein direkt vergleichbarer VQA-Benchmarkscore und keine Identitätsbestätigung.
- [OCRBench](https://link.springer.com/article/10.1007/s11432-024-4235-6):
  textbezogene Aufgaben unterscheiden; QA-Treffer ersetzen keine Feld-Precision.
- [FUNSD](https://arxiv.org/abs/1905.13538): Inhalt, Entität und Verknüpfung trennen;
  keine Beziehungskanten-F1 ohne entsprechende GT.
- [PubTabNet](https://link.springer.com/chapter/10.1007/978-3-030-58589-1_34):
  TEDS benötigt Tabellenbäume; flache Kursreferenzen reichen nicht.
- [Donut](https://www.ecva.net/papers/eccv_2022/papers_ECCV/html/8042_ECCV_2022_paper.php)
  und [Docling](https://arxiv.org/abs/2408.09869): Architekturbezug, keine
  Korrektheitsgarantie oder nachgewiesene Leistungsrangfolge für unsere Daten.

## Reale Prüfung und Grenzen

Neue Analyse auf zehn PDFs / 20 Seiten / 155 Personen / 620 Feldern je Verfahren.
Bestehende Scores und 4.492 geschützte Dateien unverändert, keine neue Inferenz.
34 Personen auf vier Originalseiten zweier PDFs unabhängig lokalisiert; einzelne
assistierte Sichtprüfung, keine Doppelannotation. 121 Personen unlokalisiert,
Scanqualität nicht klassifiziert. Dokumentverfügbarkeitslabels unverändert
weiterverwendet. Teilgruppen explorativ, nicht repräsentativ. Weitere Lokalisierung,
h/m/g-Annotation, unabhängige Zweitprüfung, kontrollierte Zeitwiederholungen und
unberührte Testdaten bleiben nötig.
