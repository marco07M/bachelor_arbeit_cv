# Umstellung auf zwei Projektordner

Seit 14.10.2026 liegen Software und schriftliche Arbeit getrennt unter
`software/` und `bachelorarbeit/`. Alle bisherigen Softwarebefehle werden nun
aus `software/` ausgeführt. `pyproject.toml`, `uv.lock`, `.python-version`,
Quelltext, Konfigurationen und Tests bilden dort dasselbe uv-Projekt.

Modellgewichte, Daten, vorbereitete Seiten und vorhandene Runs wurden nach
`software/models`, `software/data`, `software/prepared`, `software/runs`
verschoben. Sie bleiben gitignoriert. Es wurden keine Gewichte erneut geladen.
Die virtuelle Umgebung wurde am neuen Pfad neu aufgebaut; eine verschobene
venv mit alten absoluten Interpreter-/Editable-Pfaden wird nicht weiterverwendet.

Historische Runs behalten ihre damaligen Konfigurationen, Hashes und absoluten
Quellpfade. Sie werden als Forschungsprotokolle nicht nachträglich umgeschrieben.
Die HTML-Berichte funktionieren weiterhin, weil ihre Vorschaubilder relativ
im jeweiligen Run liegen. Alte Resume-/Prepared-Manifeste enthalten noch
Pfade vor der Umstellung und sind für neue Runs nicht wiederzuverwenden.
Neue Seitenmanifeste mit `participant-bench prepare` erzeugen; neue Runs
verwenden die neue Verzeichnisstruktur.
