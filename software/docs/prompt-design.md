# Literaturbasierte Gestaltung der Extraktionsprompts

Technische Präzisierung vom 11.11.2026: aktive Familie
`participant-json-v26-roster-header-scope`. Nach belegten Metadaten-/Datenheadern
in Antworten beziehen sich VLM-Prompt und Schemabeschreibung ausdrücklich nur
auf die Teilnehmertabelle. Typen und Schnittstellen bleiben bestehen; v25 ist in
`prompt-history/pre-field-loss-20261111.json` mit Hashes erhalten.
[Ursachen, Tests und Grenzen](field-loss-20261111.md) dokumentieren den Anlass.
Keine zusätzliche Promptvariante oder empirisch belegte Verbesserung.

Stand: 11.11.2026. Status: **einmalig literaturbasiert konstruiert und technisch
geprüft**, nicht empirisch optimal. Es gibt keine Promptsuche, keine zusätzlichen
Modelle, keine Auswahl anhand mehrerer Kandidaten und keinen Vorher-Nachher-
Qualitätsvergleich. Reparaturen von Schema-/Schnittstellenfehlern sind technische
Validierung, keine Optimierung anhand eines Feldscores.

## Auswahl der Literatur und Grenzen ihrer Übertragung

Gezielte, nicht erschöpfende Literaturrecherche mit Suchbegriffen wie structured
information extraction, annotation guidelines, instruction schema und prompting
survey. Berücksichtigt wurden nachvollziehbare Originalarbeiten und Übersichten
mit öffentlich prüfbarem Volltext und direktem Bezug zu Instruktionen, Felddefinitionen,
Quellenbindung oder Ausgabeformaten. Ausgeschlossen wurden nicht überprüfbare
Promptrezepte, Produktwerbung, automatische Suchverfahren und reine Ranglisten.
Recherche und Quellenprüfung erfolgten am 11.11.2026; es wurden keine Dokumente
oder personenbezogenen Inhalte an externe Dienste übertragen.

| Geprüfte Quelle | Verwendeter Befund und Übertragungsgrenze |
|---|---|
| Schulhoff et al., *The Prompt Report*, arXiv:2406.06608v6, 2025, [Volltext](https://arxiv.org/html/2406.06608v6), Abschnitte 1.1/1.2.1 | Die Übersicht unterscheidet Vorlage, konkrete Eingabe, Direktive, Kontext und Ausgabeformat. Das begründet die explizite Beschreibung dieser Bestandteile. Sie belegt weder unsere sechs Abschnitte als Optimum noch eine sichere Wirkung kürzerer Prompts. |
| Sainz et al., *GoLLIE: Annotation Guidelines improve Zero-Shot Information-Extraction*, ICLR 2024, [Volltext](https://arxiv.org/html/2310.03668v5), Abschnitte 3.2/5/6 | Feld-/Annotationsdefinitionen sind mehr als bloße Labelnamen; die Arbeit untersucht ihren Nutzen mit einem dafür feinabgestimmten Modell. Unsere Qwen-Modelle werden weder so trainiert noch durch diese Befunde validiert. |
| Wang et al., *InstructUIE*, arXiv:2304.08085v1, 2023, [Volltext](https://arxiv.org/html/2304.08085v1), Abschnitt 2.2.1 | Aufgabe, zulässige Labels, Quelltext und Ausgabe werden explizit beschrieben. Das ist eine Orientierung für die Schnittstelle; Ergebnisse des dortigen Instruction Tunings werden nicht auf unsere Verarbeitung übertragen. |
| Geng et al., *Grammar-Constrained Decoding for Structured NLP Tasks without Finetuning*, EMNLP 2023, [Originalpublikation](https://aclanthology.org/2023.emnlp-main.674/), DOI 10.18653/v1/2023.emnlp-main.674 | Die Arbeit untersucht formale Beschränkung der Generierung. Unser JSON-Schema steht dagegen im Prompt; es gibt keine neu eingeführte Grammardecodierung und keine Formatgarantie. Die vorhandene Validierung bleibt erforderlich. |
| Huang et al., *A Survey on Hallucination in Large Language Models*, arXiv:2311.05232v2, 2024, [Volltext](https://arxiv.org/html/2311.05232v2), Abschnitt 2.3.2 | Die Übersicht unterscheidet unter anderem Abweichungen von Instruktionen und gegebenem Kontext. Unsere Quellenbindungsregeln operationalisieren Kontexttreue als Projektanforderung; ihre Wirksamkeit ist damit nicht nachgewiesen. |

Die konkrete Gliederung, englische Sprache, Nullkonventionen, Standardreihenfolge
von Namen, Quellenprioritäten und Verzicht auf zusätzliche Demonstrationen oder
ausgegebenes Chain-of-Thought sind **eigene Designentscheidungen** anhand der
vorhandenen Aufgabe und Schnittstellen. Kein Paper liefert dafür ein allgemein
optimales Rezept. Das einzige JSON-Beispiel illustriert den bestehenden
Namensmetadatenvertrag und enthält keine Referenzperson oder Lösung einer Testliste.
Die geprüften Einträge stehen im bestehenden Literaturworkflow in
`bachelorarbeit/verified_sources.bib`; der Zotero-Export bleibt unberührt.

## Audit des bisherigen Aufbaus

Vor der Änderung bestanden zwei getrennt formulierte OCR-Promptfamilien,
VLM-Anweisungen, nachträglich mit `+=` angehängte Namens-/Rollenregeln und eine
eigene OCR-Hinweisergänzung. RECORD-Systemtexte wurden vor dem Anhängen der
dokumentweiten Namensmeldung gebildet. Diese Unterscheidung ist fachlich richtig,
weil `OCRRecordResponse` kein `name_order` enthält, war aber schwer erkennbar.
Wiederholte Vollständigkeits-, Spalten- und Nicht-Erfindungsregeln sowie historische
Hinweise auf Zellen, Positionen und Legacy-Protokolle waren auf mehrere Module verteilt.

Ein konkreter Konsistenzfehler war die Namensmetadatenangabe `basis`: Im Text
verlangt, im Beispiel ausgelassen und im Generierungsschema nicht verpflichtend;
der historische Parser ergänzt bei Fehlen `document`. Der neue Generierungsvertrag
fordert `basis`. Neue Antworten ohne explizite Basis gelten nur als unbekannte
Namensentscheidung; belegte Personenfelder bleiben erhalten. Historische Parser
und gespeicherte Antworten werden weiterhin gelesen. Die fehlende Basis kann damit
bei neuen Antworten nicht stillschweigend zu einem Dokumentbeleg werden.

## Eine finale Struktur pro notwendiger Schnittstelle

Die finale Promptfamilie wird in
`verarbeitung/src/participant_bench/extraction_prompts.py` definiert. Der reine
Builder setzt dieselben sechs Abschnitte zusammen:

1. **Aufgabe:** Teilnehmer aus den ausgewählten Seiten extrahieren, einschließlich
   gedruckter, handschriftlicher und gemischter sowie unvollständiger Zeilen.
2. **Teilnehmer und Zielfelder:** Ausschluss von Kontext, explizite Kursleiterrollen,
   vollständige Namensbestandteile und genaue Bedeutung der vier Zielfelder.
3. **Extraktion und Zuordnung:** Belegart, physische Spalten/Zeilen und Namen.
4. **Leere, unleserliche und unsichere Werte:** literal, `""` oder JSON `null`.
5. **Mehrseitigkeit:** Strukturkontext derselben PDF, keine früheren Personenwerte.
6. **Ausgabe:** ausschließlich das bestehende JSON-Format, danach das konkrete Schema.

Gemeinsame Texte sind semantisch gleich. Unterschiede werden über feste Adapter
für OCR-Zeilen, OCR-/Tabellenzellen, Bild und die erhaltene Legacy-Schnittstelle
beschrieben. Es gibt keinen zusätzlichen konfigurierbaren Promptvariantenraum.
Die bereits vorhandenen Page-/Record-Antwortverträge bleiben bestehen:

| Aktiver Pfad / Schnittstelle | Fachlich notwendige Besonderheit |
|---|---|
| Tesseract+LLM (`ocr_rows`) | Werte müssen wörtlich in der aktuellen `source_row` vorkommen; OCR-Schreibweisen werden nicht repariert. Spaltenmapping und unzugeordnete Beobachtungen bleiben Eingabekontext. |
| PaddleOCR+LLM (`ocr_cells`) | Bestehende Zell-/Tabellen-/Positionsbelege und ihre Kennungen werden beschrieben. Rückgabe sind Feldtexte; Indizes, Koordinaten und Arrays sind keine Feldwerte. |
| Page-Antwort | Dokumentweite `name_order`-Metadaten mit explizitem `basis` werden verlangt, sofern im Schema enthalten. |
| Record-Antwort | Keine nicht vorhandenen Top-Level-Felder verlangen. Der bestehende kurze Namensaufruf und `DOCUMENT_NAME_ORDER_CONTEXT` liefern die Grundreihenfolge. |
| VLM und OCR-VLM | Identische vollständige Systemnachricht, identisches Schema und gleicher Grundauftrag. Beide lesen Überschriften und `identity_cells` in physischer Reihenfolge. Nur der Hybrid erhält die vorhandenen OCR-Belege plus eine kurze Regel zur Bildprüfung. |
| Legacy-/All-row-/Positionseingabe | Bestehende technische Verträge bleiben unterstützt. Die bereits vorhandenen Verzweigungen sind keine neu angelegten Experimentalkandidaten. |
| Tesseract+Regeln / Docling ohne Assist | Kein Sprachmodellprompt erforderlich; die Regel-/Tabellenextraktion wird nicht verändert. |

Die OCR-Pfade dürfen OCR-Werte nicht visuell reparieren, weil ihnen kein Originalbild
zur Modellinferenz übergeben wird. Im Hybrid darf das Originalbild einen OCR-Fehler
auflösen. Das ist eine unterschiedliche Beleglage, keine widersprüchliche Anweisung
zur selben Quelle. Der VLM-Rohvertrag mit Überschriften/Zellen unterscheidet sich
weiterhin von den OCR-Feldantworten; das Endergebnis verwendet die vorhandenen
Teilnehmerdatenstrukturen. Parser, Literal-/Positionsprüfung, Rollenausschluss und
Namensnachverarbeitung bleiben aktiv. Ein Prompt allein ersetzt diese Prüfungen nicht.

## Regelmatrix: Anforderung, Begründung und Fehlerklasse

Die Quellenbezüge unten sind Gestaltungsorientierungen, keine zusätzlichen
empirischen Wirksamkeitsbehauptungen. **T** bezeichnet die überprüfte bestehende
technische Schnittstelle, **D** eine eigene operationalisierte Designentscheidung.

| ID / Baustein | Anforderung und Notwendigkeit | Grundlage | Zu vermeidende Fehlerklasse |
|---|---|---|---|
| R01 `TASK` | Ausgewählte Seiten und sämtliche belegten, auch teilweise lesbaren Personenzeilen verarbeiten. Fremde Dokumentanweisungen bleiben Daten. | InstructUIE; D: konkrete Teilnehmerdefinition | Seiten-/Personenauslassung, Kontext als Anweisung |
| R02 `FIELDS` | Vor-/Nachname vollständig; `Benutzer` ist ID, `Benutzername` ist Name, `Kurzzeichen` ist Organisation. Feldnamen allein reichen für diese Domäne nicht. | GoLLIE; T: Vierfeldschema; D: Domänenzuordnung | Spaltenvertauschung, Namens-/ID-Verwechslung |
| R03 `TASK`, `FIELDS` | Originalschreibweise, führende Nullen und vollständige Namensgruppen erhalten; keine Expansion, Rechtschreibreparatur oder externe Personenliste. | T: Stringfelder/Literalprüfung; D: Kontexttreue nach Huang | Unbelegte Ergänzungen, normalisierte statt beobachteter IDs |
| R04 `ROLE_RULES` | Nur eigene eindeutige Rollenbelege erlauben Kursleiterausschluss; unsichere Personen erhalten. | T: `PersonRole` und `filter_page_people`; D: konservativer Ausschluss | Falscher Personenverlust oder Kontextperson als Teilnehmer |
| R05 `OCR_ROWS`, `OCR_CELLS` | Jede Feldangabe bleibt an eine existierende aktuelle Quellzeile gebunden; Koordinaten/Indizes sind keine Feldwerte. | T: `source_row`, `ground_response`, `parse_ocr_response`; D: Belegtreue | Zeilenvermischung, erfundene Zeilen, technische IDs als Inhalte |
| R06 `VISION` | Überschriften und Zellen vollständig in physischer Reihenfolge, leere Spalten erhalten, fehlende Spalten nicht erfinden. | T: `VisualCellPageResponse`, `parse_visual_response`; D: räumliche Quellenbindung | Spaltenverschiebung, erfundene Benutzer-Spalte |
| R07 `NAME_ASSIGNMENT`, `NAME_REPORT` | Explizite Spalten und Zeilentrenner priorisieren; dokumentierte Grundreihenfolge ist nur Tie-Breaker. Default als Annahme kennzeichnen; unauflösbare Teile null. | T: vorhandene Namensverarbeitung; D: Mehrdeutigkeitskonvention | Namensdreher, zerschnittene Nachnamen, Annahme als Beleg |
| R08 `UNKNOWN` | Sichtbar/explizit leer wird `""`, unbekannt/fehlend/maskiert/unleserlich wird `null`; fehlender OCR-Text beweist keine leere Bildzelle. | T: bestehende Zustände/Parser; D: Annotationskonvention | Halluzinierte Werte, falsche Leerheitsbehauptung, Nachbarwertverschiebung |
| R09 `MULTIPAGE` | Nur Strukturkontext derselben PDF weitergeben; aktuelle Überschriften haben Vorrang. | T: Dokumentkontext und Fortsetzungsprüfungen; D: Prioritätsregel | Übernahme früherer Personen oder fremder Dokumentstruktur |
| R10 `OUTPUT`, Generierungsschema | Nur schemagemäße JSON-Werte und Pflichtfelder; keine Kommentare oder ausgegebenen Gedankengänge. | Prompt Report; Geng als Abgrenzung zu harter Decodierung; T: Pydantic | Ungültiges JSON, fehlende Pflichtfelder, Zusatzschlüssel |
| R11 `NAME_REPORT`, `current_name_order` | `basis` im Beispiel und Generierungsschema explizit; fehlende neue Basis wird unbekannt. Legacy-Parser bleibt lesbar. | T: alter optionaler Default; D: konservative Belegklassifikation | Unbelegte Dokumentautorität ohne Personendatenverlust |
| R12 `HYBRID_RULES` | OCR-Hinweise sind Zusatzbelege, das Bild bleibt maßgeblich; übrige Aufgabe/Schema identisch. | T: bestehender kontrollierter Hybridpfad; D: Quellenpriorität | Übernahme falscher OCR-Werte, unbeabsichtigt anderer VLM-Auftrag |
| R13 `VISION` | Keine Personen aus leeren Zeilen; bei leerer Teilnehmerantwort bestehenden `page_text`-Fallback erhalten. Signatur nur als sichtbare Anwesenheit des Zeichens bewerten. | T: Fallback-/Signaturvertrag; D: keine Identitäts-/Anwesenheitsbehauptung | Stiller Textverlust, erfundene Personen, unzulässige Signaturinterpretation |

## Versions- und Laufnachweis

- Extraktionsfamilie: `participant-json-v25-literature-guidelines`.
- Zellzuordnung: `ocr-cell-assignment-v23-literature-guidelines`; bestehender
  Positionseingabevertrag: `ocr-cell-assignment-v24-literature-guidelines-positioned`.
- Namensregeln: `document-name-order-v4-literature-guidelines`;
  Rollenregeln: `participant-roles-v2-literature-guidelines`.
- Vorherige Texte, sechs vollständig zusammengesetzte Systemnachrichten, Schemas,
  frühere Versionskennungen und Quellhashes:
  [`prompt-history/pre-20261111.json`](prompt-history/pre-20261111.json).
  Das Archiv ist ausschließlich Nachweis, kein auswählbarer Runtimepfad.

`models.extraction_prompt_snapshot()` liefert dieselbe vollständige, datenfreie
Vorlagenidentität für `runner`, `unlimited_reassign` und den eingefrorenen
Auswahlplan. `prompts.json` enthält Texte, Schemas, kompilierte Systemnachrichten
und Komponentenhashes. Einzelaufrufe speichern zusätzlich die tatsächliche
Systemnachricht **einschließlich Schema**, den dynamischen Benutzertext und deren
Hashes sowie den Schemahash; dies umfasst Zusatzanweisungen, OCR-Hinweise und
Namenskontext. Der kurze Namensaufruf wird ebenfalls protokolliert. Bilddaten werden
durch vorhandene Laufbilder/-hashes nachgewiesen; modellabhängige Chat-Templates
und Tokenisierung bleiben über die gespeicherte Modell-/Tokenizerrevision bestimmt.
Hashwerte verwenden die bestehende SHA256-JSON-Digestfunktion `io.digest`,
Dateiprüfsummen dagegen `file_hash` über Dateibytes. Diese Verfahren nicht verwechseln.
Die Protokolle bleiben lokal; dynamische Eingaben können personenbezogene Inhalte enthalten.

Geänderte Promptversionen, Texte und Schemas gehen in die vorhandenen
Lauf-/Cacheidentitäten ein. Historische Läufe werden nicht umgeschrieben oder mit
neuen Prompts fortgesetzt. OCR-Erkennungsbelege können weiterhin gecacht werden;
das ist von einer wiederverwendeten LLM-Antwort zu unterscheiden. Vor Pilot/Finaltest
wird diese Promptfamilie mit Profil, Schema und Code eingefroren. Keine Anpassung
an einzelne Modelle oder finale Referenzantworten. Es bleibt ein Pipelinevergleich
mit dokumentierten Eingabe-, Layout- und Nachverarbeitungsunterschieden.

## Begrenzte Validierung

Neue Vertragsprüfungen erfassen sechs Abschnitte ohne doppelte gemeinsame Blöcke,
Schema-/Record-Kompatibilität, Namensbeispiele, neue Pflichtbasis und historische
Lesbarkeit, vollständige System-/Benutzer-/Schemahashes, Gleichheit zwischen
Laufsnapshot und Auswahlplan sowie den gemeinsamen VLM-/Hybrid-Systemprompt.
Bestehende Tests prüfen unter anderem führende Nullen, zusammengesetzte Namen,
leere/maskierte Werte, Kontextausschluss, mehrseitige Fortsetzungen, fremde Zeilen,
Layoutwechsel und abgelehnte Antworten. Synthetische neue Mock-Antworten wurden
bei Bedarf um das explizit verlangte `basis` ergänzt; historische Fixtures bleiben
als Kompatibilitätsfälle erhalten.

Die komplette lokale Regression mit **728 Tests** und die separate API-Suite mit
**48 Tests** bestehen. Die zusätzliche reale Offline-Funktionsprüfung verwendete
ausschließlich eine bereits vorhandene synthetische PDF mit einer Seite und zwei
Referenzpersonen für `ocr_llm`, `paddle_llm`, `vlm`, `ocr_vlm`. Alle vier Pfade:
gültiges JSON, zwei Personen, sieben von sieben bewertbaren Referenzfeldern exakt.
Paddle-LLM und OCR-VLM blieben mit Prüfhinweisen `partial`, die anderen `success`;
gültiges JSON bedeutet keine generelle Fehlerfreiheit. Lauf
`runs/20261111T075852Z-c0b6b30b`, Bericht
`data/prompt-revision-20261111/reports/20261111T080047Z-a8f88de0/report.html`.
Vier tatsächliche Extraktionsnachrichten und vorhandene Namensaufrufe wurden auf
korrekte System-/Benutzerhashes geprüft; 30 geschützte Profil-/Historienartefakte
sind unverändert. Nachweis: `data/prompt-revision-20261111/functional.json`.
Ein Fehler des nachgelagerten Zusammenfassungsskripts wurde aus den gespeicherten
Ergebnissen korrigiert, ohne erneute Inferenz. Keine Mehrvariantenstudie, keine
Messung eines Promptverbesserungseffekts.
Handschrift und gemischte reale Layouts sind durch diese gedruckte Funktionsliste
nicht empirisch abgedeckt. Technische Tests beweisen keine Befolgung sämtlicher
Instruktionen. Die Promptfamilie ist nicht empirisch optimal und kein Nachweis
höherer Genauigkeit, geringerer Halluzinationen oder allgemeiner Überlegenheit.
