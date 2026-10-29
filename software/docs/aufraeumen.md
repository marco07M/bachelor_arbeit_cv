# Projekt aufräumen

Aus `software/` zunächst nur anzeigen lassen, was entfernt würde:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/aufraeumen.ps1
```

Die Bereinigung ausführen:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/aufraeumen.ps1 -Ausfuehren
```

Standardmäßig bleiben die letzten **zwei vollständigen Modellläufe** und die
letzten **drei vollständigen Excel-/CSV-Vergleiche** erhalten. Weitere Quellläufe,
auf die deren Berichte, Seitenbilder oder vorbereitete Manifeste verweisen,
werden automatisch mitbehalten. Ein vollständiger Lauf hat einen HTML-Bericht.
Alte Zwischenläufe, abgebrochene Versuche und synthetische Ergebnisläufe werden
entfernt, sofern sie dafür nicht benötigt werden.

Andere Anzahl behalten:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/aufraeumen.ps1 -LetzteLaeufe 5 -LetzteVergleiche 5
```

Ohne `-Ausfuehren` ist dies weiterhin eine Vorschau. Vor dem Löschen müssen
laufende Python-/Modell-/Testprozesse beendet sein. Das Skript prüft alle absoluten
Zielpfade vorab und bricht bei Verzeichnisverknüpfungen ab.

Zusätzlich entfernt werden Python-Bytecode und Pytest-/Ruff-Caches aus den
Quell- und Testordnern sowie der leere frühere Ordner `test_url/`, falls vorhanden.
Original-PDFs, Eingabeordner, Referenzlisten, Vorverarbeitungsausgaben, virtuelle
Umgebungen, Modellgewichte und OCR-/Modellcaches werden beibehalten.
Der private Firmen-PC-Ordner wird nicht durchsucht.

Nach dem Aufräumen zeigen diese lokalen Übersichten die behaltenen Berichte:

- [`runs/README.md`](../runs/README.md)
- [`testframework/ergebnisse/README.md`](../testframework/ergebnisse/README.md)

Das Löschprotokoll liegt unter `.cache/cleanup/latest.json`. Frühere Testnotizen
können noch Namen inzwischen entfernter Läufe enthalten; sie dokumentieren den
damaligen Stand.
