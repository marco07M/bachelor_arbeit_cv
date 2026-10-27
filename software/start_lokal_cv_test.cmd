@echo off
setlocal
title Teilnehmerlisten - lokaler CV-Test
set "CV_EXIT_CODE=1"
pushd "%~dp0"
if errorlevel 1 goto :finish_without_directory

echo Eingabe: data\cv-test-20261020-093337
echo Es werden nur die PDFs in diesem Ordner und seinen Unterordnern verarbeitet.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Die lokale Python-Umgebung fehlt.
    echo Bitte im Ordner software einmal uv sync --locked --extra models ausfuehren.
    goto :finish
)
if not exist ".venv\Scripts\participant-bench.exe" (
    echo Der lokale Programmeinstieg fehlt. Bitte uv sync --locked --extra models ausfuehren.
    goto :finish
)

".venv\Scripts\python.exe" -c "from pathlib import Path; p=Path('data/cv-test-20261020-093337'); n=sum(1 for f in p.rglob('*') if f.is_file() and f.suffix.lower()=='.pdf') if p.is_dir() else 0; print('Gefundene PDFs:',n); raise SystemExit(0 if n else 1)"
if errorlevel 1 (
    echo Bitte mindestens eine PDF im angegebenen Eingabeordner ablegen.
    goto :finish
)

if /I "%~1"=="--pruefen" (
    echo Eingabepruefung erfolgreich. Es wurde keine Analyse gestartet.
    set "CV_EXIT_CODE=0"
    goto :finish
)

echo.
echo Starte lokale OCR-, LLM- und VLM-Analyse. Der erste Modellstart kann dauern.
".venv\Scripts\participant-bench.exe" run --input "data\cv-test-20261020-093337" --config "configs\imported.yaml" --offline
set "CV_EXIT_CODE=%ERRORLEVEL%"
echo.
if "%CV_EXIT_CODE%"=="0" (
    echo Verarbeitung abgeschlossen. Ergebnisse: runs\LAUF_ID\report.html
) else (
    echo Der Lauf meldet einen Fehler. Bitte die Ausgabe und das progress.log im Laufordner pruefen.
)

:finish
popd
:finish_without_directory
if /I not "%~1"=="--pruefen" pause
exit /b %CV_EXIT_CODE%
