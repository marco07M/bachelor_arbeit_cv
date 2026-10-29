@echo off
setlocal
title Teilnehmerlisten - API-Testframework
set "FRAMEWORK_EXIT_CODE=1"
pushd "%~dp0"
if errorlevel 1 goto :finish_without_directory
if not exist ".venv\Scripts\python.exe" (
    echo Bitte zuerst in software\api_firmen_pc uv sync --locked ausfuehren.
    goto :finish
)
".venv\Scripts\python.exe" "testframework\main.py" check
set "FRAMEWORK_EXIT_CODE=%ERRORLEVEL%"
if not "%FRAMEWORK_EXIT_CODE%"=="0" goto :finish
if /I "%~1"=="--pruefen" goto :finish
echo PDFs: testframework\eingabe_pdfs
echo Excel oder CSV: testframework\referenz
echo Die Referenz bleibt lokal. PDF-Seiten gehen an die konfigurierte API.
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File "scripts\run-private-api.ps1" -Testframework
set "FRAMEWORK_EXIT_CODE=%ERRORLEVEL%"
:finish
popd
:finish_without_directory
if /I not "%~1"=="--pruefen" pause
exit /b %FRAMEWORK_EXIT_CODE%
