# Teilnehmer aus Unlimited-OCR zuordnen

Unlimited-OCR erkennt Text und Tabellenstruktur. Das ist noch keine Zuordnung
zu den Projektfeldern Vorname, Nachname, Benutzer-ID und Kurzzeichen. Im älteren
CV-Lauf `20261027T074837Z-9a137c33` scheiterte der Tabellenparser auf Seite 1 an
verbundenen Zellen und auf Seite 2 an fehlenden Überschriften. Der OCR-Text war
vorhanden, aber es entstanden keine Teilnehmerdatensätze.

Die optionale Einstellung `models.unlimited_ocr.options.extraction: llm` ergänzt
eine lokale Zuordnung mit dem bereits vorhandenen Qwen3-8B. Der reine OCR-Modus
(`none`) und die konservative Tabellenbaseline (`table`) bleiben wählbar.

## Start aus software/

Für die vorhandene CV-Testeingabe genügt:

```powershell
.\start_unlimited_cv_test.cmd
```

Das entspricht:

```powershell
.\.venv\Scripts\participant-bench.exe run --input .\data\cv-test-20261020-093337 --config .\configs\unlimited-ocr-llm.yaml --offline
```

`configs/benchmark-unlimited.yaml` vergleicht Tesseract/Regeln, Tesseract/LLM,
direktes VLM und Unlimited-OCR/LLM. Das 8B-LLM wird im Vergleich für zwei
unterschiedliche OCR-Ausgaben eingesetzt; die Teilnehmerergebnisse der Verfahren
werden nicht untereinander übernommen. Dies benötigt zusätzliche LLM-Rechenzeit.

Für andere Eingaben `--input` ändern. Einmalige Einrichtung, falls Gewichte oder
Umgebungen auf einem anderen Rechner fehlen:

```powershell
uv sync --locked --extra models
uv sync --locked --project unlimited_ocr_runtime
.\.venv\Scripts\participant-bench.exe download-models --config configs/unlimited-ocr-llm.yaml --method unlimited_ocr --method ocr_llm --method vlm --transport range
```

Auf dem eingerichteten Laptop ist kein neuer Modelldownload erforderlich.

## Gespeicherte OCR nachträglich zuordnen

```powershell
.\.venv\Scripts\participant-bench.exe assign-unlimited --run .\runs\20261027T074837Z-9a137c33 --offline
```

Es entsteht ein **neuer Lauf** in `runs/` mit CSV, JSONL und `report.html`.
Die PDF-Verarbeitung und Unlimited-OCR-Inferenz werden dabei nicht wiederholt.
`assignment_recheck.json` enthält Quelllauf und SHA256-Prüfsummen sowie
`new_ocr_inference: false`. Ursprüngliche OCR, Vorhersagen und Referenzdaten
bleiben erhalten. Der Lauf übernimmt keine früheren Qualitätsmetriken und führt
keine neue Unterschriftenprüfung durch. Dafür gegebenenfalls anschließend:

```powershell
.\.venv\Scripts\participant-bench.exe signatures --run .\runs\NEUE_LAUF_ID --method unlimited_ocr --config configs/unlimited-ocr-llm.yaml --offline
```

## Ablauf und Belege

1. Unlimited-OCR erkennt jede Seite lokal in seiner separaten Laufzeit.
2. Der Worker wird vollständig beendet und gibt seine GPU-Belegung frei.
3. Qwen3-8B wird lokal mit der konfigurierten 8-Bit-GPU-Zuordnung geladen.
4. Es erhält physische Tabellenzellen mit expliziten Zellnummern, leeren Zellen,
   Spaltenpositionen, `rowspan` und `colspan`. Verbundener Text wird nicht in
   mehrere Zellen kopiert. Beschädigte/verschachtelte Tabellen bleiben zur Kontrolle.
5. Das Modell liefert pro Person eine Quellzeile und pro Feld Zellnummer plus
   beobachteten Text. Keine erfundenen Wortpositionen oder Konfidenzen.
6. Der Code prüft jede Angabe gegen die referenzierte Zeile. Eindeutige gedruckte
   Überschriften erlauben die direkte Übernahme einzelner vollständiger Zellen.
   `Benutzername` ist dabei eine Namenszelle, getrennt vom Feld `Benutzer`.
   Ein kombiniertes Namensfeld wird anhand belegbarer Teiltexte aufgeteilt.
7. Das LLM wird entladen; beim normalen `run` folgt optional die separate
   visuelle Unterschriftenprüfung mit dem konfigurierten VLM.

Führende Nullen, Unicode und Schreibweisen werden erhalten. HTML-Entitäten
werden dekodiert und Leerraum innerhalb einer Zelle für den Vergleich vereinheitlicht;
der ursprüngliche Zelltext bleibt daneben gespeichert. Leere Benutzerzellen
verschieben keine weiteren Felder. Starke Maskierungen (`**`, `██`, `XXX`)
bleiben unbekannt. Namen werden nicht anhand einer Excel-Referenz ergänzt.
Ein falscher Zellindex kann nur über einen eindeutigen Wort-/Phrasenbeleg in
derselben Quellzeile berichtigt werden; diese Berichtigung wird protokolliert.
Werte anderer Zeilen und unvollständige Wörter werden nicht übernommen.

Überschriften früherer Seiten desselben PDFs können als Kontext dienen. Es werden
keine früheren Teilnehmerdaten in diesen Kontext kopiert; die eigentlichen
Feldbelege müssen auf der aktuellen Seite stehen. Keine automatische
Dokumenttyp-/Seitenklassifikation. Keine API-Anbindung für die Zuordnung.

Im Bericht unter OCR-Klartext sind zusätzlich verlinkt:

- die vollständige Unlimited-OCR-Ausgabe;
- die exakte LLM-Eingabe und LLM-Antwort;
- `raw-<Seiten-ID>.json`, mit `assignment.row_evidence`, Quellzellen und Hinweisen;
- CSV-/JSONL-Teilnehmerdaten zum weiteren Vergleich.

## Grenzen und Wiederholung

Ein Textbeleg beweist **Textvorkommen, nicht die richtige Bedeutung des Feldes**.
Die semantische Zuordnung bleibt prüfpflichtig; `partial` ist deshalb auch bei
formal gültigen Antworten vorgesehen. Nicht zugeordnete OCR-Zeilen und fehlerhafte
Feldbelege werden gesondert markiert. OCR-Fehler, fehlende Zeilen, falsch erkannte
Tabellen und unklare Namensreihenfolge können weiterhin zu Fehlern führen.
Es gibt keine nachgewiesene allgemeine Genauigkeitssteigerung ohne manuell
gelabelte Entwicklungs-/Validierungs-/Testdaten.

Unterschriften werden aus diesem OCR-Text nicht als vorhanden/fehlend abgeleitet.
Bei ungültigem JSON oder Tokenlimit bleibt der vollständige OCR-Text erhalten.
`assignment_max_new_tokens` beträgt 4096, das bestehende LLM-Eingabelimit bleibt
wirksam; keine stille Kürzung. Erfolgreiche Antworten werden lokal anhand von
Quellzellen, Modellidentität, Parametern, Systemprompt und Schema zwischengespeichert.
Bei erneuter identischer Zuordnung wird die Antwort aus dem Cache erneut geprüft.
Ein neuer Lauf kann deshalb weiterhin ein Modell laden, ohne die Inferenz zu wiederholen.
Änderungen an Quelle/Prompt/Schema/Modell erzeugen einen neuen Cache-Schlüssel.

Die reine OCR-Leistung weiterhin getrennt über `evaluate-ocr` messen. Die
Teilnehmerfelder mit manuell geprüften Referenzen vergleichen; Anzahl gefundener
Personen allein ist kein Qualitätsmaß.
