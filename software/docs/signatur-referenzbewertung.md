# Referenzzuordnung und wahrscheinlich fehlende Unterschriften

Stand: 16.11.2026. Voraussetzung dieser Bewertungsregel ist eine Excel-/CSV-
Kursreferenz, die ausschließlich tatsächlich unterschriebene Teilnehmer enthält.
Die Regel gehört zur Evaluation nach der Extraktion, nicht zum OCR-/Modellprompt.

Alle relevanten Listen besitzen eine Unterschriftenspalte. Ihre **Existenz ist
vorausgesetzt**; geprüft werden ihre Position und die sichtbare Präsenz einer
Markierung je Teilnehmerzeile. Unterschriften werden niemals transkribiert oder
als zusätzliches Textfeld in Exact-/Coverage-/Levenshtein-/CER-/WER-Metriken
aufgenommen. `TEXT_FIELDS` enthält unverändert genau Vorname, Nachname,
Personalnummer und Organisation. Eine gegebenenfalls separat annotierte
Signatur-Konfusionsmatrix bewertet ausschließlich Präsenz, keine Schriftzeichen.

### Zellposition und Folgeseiten

Neue strukturierte Läufe aller Verfahren verwenden dieselbe bildbasierte
Zellprüfung `rules.inspect_signature_cells`, auch ohne zusätzliches VLM.
Sie verwendet die vorhandenen `column_context`-Zuordnungen oder den bestehenden
OCR-Überschriften-/Tabellenabgleich `with_table_columns`. Die Signaturposition
wird aus Überschrift und gemessenen Spaltengrenzen bestimmt. Kompatible spätere
Seiten **derselben PDF** übernehmen den vorhandenen Kontext. Abweichende
Geometrie, fehlende Messungen, andere PDFs und falsche Seitenfolge verhindern
die Übernahme. Die zulässige Übernahme eines reinen Textspaltenpräfixes belegt
keine dahinterliegende Signaturspalte; diese darf dadurch nicht erfunden werden.
Explizit konfigurierte `rules.columns.signature`-Intervalle bleiben als manuell
bekannte Vorlagenpositionen verwendbar.

Die Teilnehmerzeile wird durch gemessene horizontale Zellgrenzen oder eine
explizite vollständige Zeilenbox abgegrenzt. Textspalten und Signaturspalten
müssen von einer verwendeten horizontalen Grenzlinie tatsächlich durchlaufen
werden: Ein langer Signaturstrich allein
darf nicht zur neuen Zellgrenze werden und dadurch aus dem Ausschnitt verschwinden.
Eine bloße interpolierte OCR-Textzeile genügt nicht für eine verlässliche
Leerentscheidung. Fehlende oder
überlappende Zeilenpositionen bleiben unbekannt. Die Zellprüfung verändert keine
Textwerte und keine Teilnehmerboxen und beeinflusst damit das Teilnehmer-
Matching nicht. Alle lokalisierten Signaturzellen einer Zeile müssen leer sein,
bevor ein negativer Befund zulässig ist. Tinte allein bestätigt keine Signatur:
gedruckte Zeichen, Schmutz oder mehrdeutige Striche bleiben prüfpflichtig.

Die vorhandene OpenCV-Prüfung verarbeitet ausschließlich Zellpixel.
OCR-Pseudotext aus einer Signaturzelle entscheidet weder Präsenz noch Abwesenheit.
Optionales VLM erhält nur die ausgewählten Signaturzellen mit Spaltenkontext,
ohne neue Frage nach der grundsätzlichen Existenz einer Unterschriftenspalte.
Fehlt eine verlässliche Position, entfällt der zusätzliche Präsenzaufruf.
Das rückwärtskompatible `field_located`-/`no_field`-Antwortformat bezeichnet dabei
nur die **Lokalisierbarkeit**, niemals das grundsätzliche Vorhandensein einer
Spalte. Die neue Prompt-/Cache-Version lautet
`signature-detail-v4-assumed-column-presence`.

| Referenzabgleich nach bestehendem Matching | Signaturbefund | Entscheidung |
|---|---|---|
| Referenzperson gepaart | beliebig, auch fehlend | Regulär bewerten; alle Referenznenner bleiben bestehen |
| Referenzperson ungepaart | kein Modellergebnis | Fehlende Person und Felder bleiben im Nenner |
| Zusatzperson ohne hinreichend ähnliche Referenzanker | wahrscheinliches Leerfeld mit Zeilenbeleg | Automatisch aus Qualitätsbeiträgen ausschließen |
| Zusatzperson mit ähnlichen Namen, gleicher ID, Mehrdeutigkeit oder Konflikt | beliebig | Regulär als ungepaarte Ausgabe erfassen, manuell prüfen |
| Zusatzperson ohne Referenz | vorhanden, unbekannt oder nicht verlässlich lokalisiert | Regulär als ungepaarte Ausgabe erfassen, manuell prüfen |

## Belege und Unsicherheit

`signature_present`, `signature_state`, `signature_method`, vorhandene
Signaturzellkoordinaten sowie gespeicherte `signature_checks` werden verwendet.
Neue Läufe dokumentieren zusätzlich `signature_column_mapping`,
`signature_column_context` und `signature_cell_checks` mit einzelnen Zellboxen,
Zeilengrenzen, Bildbefunden und Widersprüchen. Der HTML-Report verlinkt die
originalen Signaturzellen und zeigt diese Beleglage bei Ausschlüssen und
Prüffällen. Fehlende historische Zellbelege werden nicht nachträglich erfunden.
Ein boolesches `false` aus dem Gesamtbild allein genügt nicht. Ein fehlender
OCR-Wert, niedriger OCR-Score oder unleserliche Handschrift belegt keine fehlende
Unterschrift.

Zulässige negative Zeilenbelege sind:

- Neu: `opencv_cells` mit konsistentem gespeichertem Zeilenbeleg, zuverlässigen
  Zeilengrenzen, allen Signaturzellen bildbasiert leer und ohne Widerspruch zu
  einer vorhandenen Signatur. Unsichere/überlappende Bereiche verhindern Ausschluss.
- `opencv_conservative`: negativer Zustand `read`/`empty`, nicht überlappende
  Teilnehmerzeile und lokalisierte Signaturzelle in dieser Zeile (historische
  Befunde werden weiter unterstützt).
- Erfolgreiche gespeicherte Detailprüfung: eindeutig derselben Teilnehmerbox
  zugeordneter Ausschnitt, `field_located=true`, `signature_present=false`,
  `evidence=blank_field` und konsistenter finaler Zustand. Das Quellenlabel der
  Lokalisierung muss `ocr_words` oder `participant_prediction` sein.
  Ausschließlich durch VLM geschätzte Zeilenpositionen (`local_vlm`), doppelte
  Indexbelege, fehlerhafte Antworten, überlappende Personenboxen und Widerspruch
  zur vorher erkannten vorhandenen Signatur rechtfertigen keinen Ausschluss.

Die vorhandene Zeilenhöhenprüfung `signature.max_row_height` wird auch hier
verwendet; seitenhohe Personen-/Signaturboxen sind kein brauchbarer Zeilenbeleg.
Enthält die Referenz Personen ohne jeden lesbaren Namen und ohne nutzbare ID,
rechtfertigt eine fehlende Zuordnung ebenfalls keinen automatischen Ausschluss.

Das ist eine **wahrscheinliche fehlende Unterschrift**, keine manuelle visuelle
Bestätigung und kein Nachweis einer biometrischen Identität. Die vorhandene
Signaturschnittstelle enthält **keine kalibrierte Signaturwahrscheinlichkeit**.
Deshalb wird keine neue Wahrscheinlichkeitsschwelle eingeführt und weder OCR-
Confidence noch Tokenwahrscheinlichkeit dafür umgedeutet. Die vorhandene
OpenCV-Leerfeldschwelle `signature.blank_ink_fraction` (Standard `0.0005`) und
`component_min_area` (Standard `8`) bleiben konfigurierbar im Extraktionsprofil;
der Befund wird aus dem gespeicherten Lauf übernommen, nicht neu berechnet.
Die Regressionen prüfen diese Schwelle an synthetischen Entwicklungsbildern mit
Leerzelle und deutlichen Strichen. **Eine Kalibrierung beziehungsweise bestätigte
Fehlerrate auf realen, manuell annotierten Signaturzellen ist damit nicht belegt.**
Für einen solchen Nachweis sind unabhängig geprüfte Personen-/Zellkoordinaten und
Signaturlabels auf Entwicklungsdaten nötig; Testdaten dürfen dafür nicht zur
Schwellenwahl verwendet werden. Ein zukünftiger probabilistischer Klassifikator
braucht eine eigene Entwicklungsvalidierung vor Aktivierung seiner Schwelle.

## Matching und Namensabweichungen

Signaturen verändern weder Kandidaten, Optimierung noch bestehende Paarungen.
Erst anschließend werden ungepaarte Ausgaben betrachtet. Der Schutz vor einem
falschen Ausschluss verwendet dieselben Normalisierungen, `pair_evidence`,
Namensorientierungen und die vorhandene normalisierte Levenshtein-Ähnlichkeit.
Der vorsichtige Ausschlussschutz prüft beide Namensorientierungen auch in einer
strengen Bewertungsansicht; deren eigentliche Matching-/Scoringregeln bleiben
unverändert.
Auch bereits belegte Referenzzeilen werden geprüft: Eine doppelte oder ähnlich
geschriebene Ausgabe soll nicht nachträglich verschwinden.

Ein gleicher nutzbarer ID-Anker, ein konservativ zulässiger Matchingkandidat oder
eine mittlere Ähnlichkeit der beiderseits vorhandenen Namensfelder mindestens
`matching.minimum_name_similarity` (Standard `0.70`) verhindert den Ausschluss.
Bei nur einem vergleichbaren Namensfeld genügt dieses als vorsichtiger
Prüfhinweis. Diese Ähnlichkeit ist keine Identifikationswahrscheinlichkeit und
vergibt keine zusätzlichen Treffer. `Müller` und `Muller` bleiben im Exact Match
verschieden; ein vorhandener gepaarter Wert bleibt abweichend statt fehlend.

## Konfiguration und Zähler

`matching.exclude_probably_unsigned_extras: true` ist in den lokalen und API-
Standardprofilen aktiv. Historische Konfigurationen ohne diesen Schlüssel haben
den rückwärtskompatiblen Wert `false`. Damit verändert ein bloßes erneutes Lesen
einer alten Konfiguration keine frühere Fehlerzählung. Für einen Vergleich mit
neuer Regel `compare` mit aktuellem Profil und **neuem** Ausgabeordner verwenden.
`analyze` übernimmt dagegen die eingefrorene Vergleichskonfiguration.
Zusätzliche VLM-Detailaufrufe bleiben standardmäßig deaktiviert; eine fehlende
Beleglage wird nicht durch erfundene Entscheidungen ersetzt.

- `predicted_participants`: sämtliche unveränderten Roh-Ausgabedatensätze.
- `evaluated_predicted_participants`: Rohdatensätze abzüglich automatischer
  Ausschlüsse.
- `excluded_probably_unsigned_participants`: separat dokumentierte Ausschlüsse.
- `extra_participants`: ausschließlich ungepaarte, weiterhin bewertete Ausgaben.
- `unassigned_manual_review_participants`: ungepaarte Prüffälle; weitere
  gepaarte oder fehlende Referenzfälle können ebenfalls Prüfhinweise haben.

Ausgeschlossene Felder tragen R=P=E=0 bei. Referenzfelder, Exact-Treffer, fehlende
Referenzpersonen, Teilnehmer-Recall, vollständig korrekte Teilnehmer, Coverage
und bedingte Levenshtein-Ähnlichkeit bleiben bei denselben Paaren unverändert.
Precision/F1 können steigen, weil ausschließlich die belegten Zusatzbeiträge
entfallen. Das ist kein neuer Exact-Treffer. `unsigned_exclusion.before_exclusion`
rekonstruiert die bisherigen Beiträge aus denselben Feldzählern mit der
vorhandenen Funktion `scores`; es findet kein zweites Matching statt.
Schriftartgruppen enthalten weiterhin nur die festen GT-Zuordnungen; manuell zu
prüfende Extras verbleiben global, automatische Ausschlüsse stehen separat.

## Bericht und Reproduzierbarkeit

Die bestehende `extraction_errors.html` enthält separate Listen „Automatisch
ausgeschlossen“ und „Manuelle Prüfung erforderlich“, Matchingkandidaten,
Signaturbefund, Zeilenbeleg, Unsicherheit, Gründe und vorhandene Seiten-/Crop-
Links. Verfahrens-/Dokument-/Seitenfilter und Suche gelten auch für diese Listen.
Bereich G des Hauptreports enthält den Ausschlussstatus und Signaturangaben;
Feldvergleiche behalten ihre fünf eindeutigen Bewertungszustände.

`participants.csv`, `scientific/participant_audit.csv`,
`error_analysis/participants.json` und die Feldzähler enthalten die Entscheidungen.
Metrikversion v9, wissenschaftliche Analyse v6 und Dashboard v4 kennzeichnen
die Erweiterung. Neue `identity.json`-Dateien halten zusätzlich die Hashes der
verwendeten Rohartefakte fest. Geänderte oder nachträglich hinzugefügte
Signaturbelege führen beim Öffnen des eingefrorenen Vergleichs zum Abbruch.

Referenznachweis vom 16.11.2026: Der Dreidokumentvergleich mit 46 Referenzpersonen
und 184 erwarteten Feldern pro Verfahren hat keine verwertbaren negativen
Signaturentscheidungen. Alle gespeicherten Signaturwerte sind unbekannt.
Deshalb erfolgt dort kein automatischer Ausschluss und keine Qualitätsänderung.
Dies belegt die konservative Behandlung fehlender Daten, nicht die reale
Treffsicherheit der Ausschlussregel. Die Wirkung des Ausschlusses ist mit
synthetischen Regressionen geprüft: Ein korrektes Vierfeldergebnis plus eine
ausgeschlossene Vierfelder-Zusatzperson hat weiterhin Recall/Coverage/Ähnlichkeit
100 %, während Exact F1 von 2/3 auf 1 steigt. Eine fehlende Referenzperson bleibt
auch bei Ausschluss einer Zusatzperson vollständig negativ bewertet.
