# API-Verarbeitung wurde ausgelagert

API-Code, Konfigurationen, Starthelfer und Tests liegen jetzt im eigenen Projekt
[`software/api_firmen_pc/`](../api_firmen_pc/README.md). Dort befindet sich die
vollständige aktuelle Anleitung für den Firmen-PC mit eigener `.venv` und `uv.lock`.

Das lokale Programm unter `software/` liest keine API-Zugangsdaten. Bisherige
`api-check`-Befehle werden durch `python main.py check` im Firmen-PC-Ordner ersetzt.
Das frühere Testskript bleibt unverändert unter `api_firmen_pc/privat/test_url/`.
