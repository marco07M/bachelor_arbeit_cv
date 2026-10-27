@echo off
setlocal
title Teilnehmerlisten - API auf dem Firmen-PC
set "CV_EXIT_CODE=1"
pushd "%~dp0"
if errorlevel 1 goto :finish_without_directory

echo Eingabe: data\cv-test-20261020-093337
echo Es werden nur die PDFs in diesem Ordner und seinen Unterordnern verarbeitet.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Die Firmen-PC-Umgebung fehlt.
    echo Bitte im Ordner software\api_firmen_pc einmal uv sync --locked ausfuehren.
    goto :finish
)

".venv\Scripts\python.exe" -c "from pathlib import Path; p=Path('data/cv-test-20261020-093337'); n=sum(1 for f in p.rglob('*') if f.is_file() and f.suffix.lower()=='.pdf') if p.is_dir() else 0; print('Gefundene PDFs:',n); raise SystemExit(0 if n else 1)"
if errorlevel 1 (
    echo Bitte mindestens eine PDF auf dem Firmen-PC im angegebenen Eingabeordner ablegen.
    goto :finish
)

if /I "%~1"=="--pruefen" (
    echo Eingabepruefung erfolgreich. Es wurden keine Zugangsdaten geladen und keine API kontaktiert.
    set "CV_EXIT_CODE=0"
    goto :finish
)

echo.
echo Starte die API-Verarbeitung. Zugangsdaten werden bei Bedarf verdeckt abgefragt.
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File "scripts\run-private-api.ps1" -InputFolder "data\cv-test-20261020-093337"
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
