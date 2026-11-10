@echo off
setlocal
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo Bitte zuerst im Ordner software uv sync --locked --extra models ausfuehren.
    set "BENCHMARK_EXIT_CODE=1"
    goto :finish
)
if /I "%~1"=="--pruefen" (
    ".venv\Scripts\python.exe" "testframework\main.py" check
) else (
    ".venv\Scripts\python.exe" "testframework\main.py" run %*
)
set "BENCHMARK_EXIT_CODE=%ERRORLEVEL%"
:finish
popd
if /I not "%~1"=="--pruefen" pause
exit /b %BENCHMARK_EXIT_CODE%
