# Feste Spalten bei der VLM-Extraktion

Der VLM-Prompt allein verhinderte nicht, dass ein Kurzzeichen bei leerer Benutzer-
zelle als `personnel_number` ausgegeben wurde. Die bisherige Antwort wurde nach
der JSON-Validierung ohne weitere Spaltenprüfung übernommen.

Seit Promptversion `participant-json-v11-physical-identity-cells` liest das VLM
zuerst sämtliche Tabellenüberschriften von links nach rechts. Jede Teilnehmerzeile
enthält dieselbe Anzahl physischer Zellen, einschließlich leerer Zellen. Auch
Namens- und Nummernspalten bleiben an ihrer Position. Datum und Unterschrift
erhalten lediglich `null` als Platzhalter; ihre Inhalte werden nicht transkribiert.

Ein Beispiel für die Form der Antwort mit ausschließlich künstlichen Werten:

```json
{
  "identity_headers": ["Nr", "Benutzername", "Benutzer", "Kurzzeichen", "Unterschrift"],
  "participants": [{
    "row_ref": "1",
    "first_name": "Anna",
    "last_name": "Weber",
    "identity_cells": ["1", "Weber, Anna", "", "AB 123", null],
    "signature_present": false
  }],
  "page_text": null
}
```

Die Anwendung erkennt die Rollen anhand generischer gedruckter Überschriften und
übernimmt hier Zelle 2 als leere Benutzer-ID und Zelle 3 als Kurzzeichen. Die
Zählung beginnt bei null. Umgekehrte Spaltenreihenfolgen funktionieren genauso.
`Benutzername` bezeichnet eine Namensspalte und wird nicht als Benutzer-ID gelesen.
Ein Kurzzeichen darf numerisch und eine Benutzer-ID alphanumerisch sein; deren
Schreibweise wird nicht zur automatischen Vertauschung verwendet.

Fehlt die ID-Spalte vollständig, bleibt die ID unbekannt. Bei fehlenden,
zusammengefassten oder doppelten Überschriften wird das betreffende Feld nicht
automatisch zugeordnet. Eine abweichende Zellenanzahl lässt beide Identitätsfelder
unbekannt, statt eine Verschiebung zu raten. Der Teilnehmer und seine Namen bleiben
erhalten; der Lauf erhält `partial` und nachvollziehbare `field_warnings`.

Alte semantische Antworten bleiben lesbar. Ein darin verdächtiges Kurzzeichen
in einer ID bei gleichzeitig leerer Abteilung wird zur Prüfung markiert, ohne
es automatisch in ein anderes Feld zu verschieben. Der ursprüngliche Wert bleibt
in der unveränderten Rohantwort erhalten.

Im Laufordner dokumentieren `vlm/raw-<Seiten-ID>.json` unter
`responses[].identity_column_assignment` die gelesenen Überschriften und
Spaltenindizes. `responses[].field_warnings` sowie die Prüfhinweise im Bericht
erklären nicht eindeutige Zuordnungen. JSONL, CSV und `participants.xlsx` enthalten
die daraus abgeleiteten Teilnehmerfelder. Originaldateien und alte Läufe bleiben
unverändert; für den neuen Prompt einen neuen Lauf starten.

Es entstehen keine zusätzlichen OCR- oder VLM-Aufrufe für diese Prüfung. Der
normale lokale Einstieg und das getrennte API-Projekt verwenden dasselbe Schema.
Die zusätzliche visuelle Unterschriftenprüfung bleibt davon getrennt. Es gibt
weiterhin keine Klassifikation oder Vorauswahl von Seiten; ohne Teilnehmer bleibt
der Seitentext als Fallback erhalten.

Die Spalten und Zelltexte werden weiterhin vom VLM gelesen, nicht unabhängig
bewiesen. Falsch gelesene Überschriften oder Zellinhalte sind damit weiter möglich.
Der Excel-/CSV-Abgleich und manuell geprüfte Seiten bleiben für die Messung der
tatsächlichen Erkennungsqualität erforderlich; Referenzwerte werden dem VLM nicht
übergeben und korrigieren keine Modellwerte.
