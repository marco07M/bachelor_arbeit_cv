@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1
echo Unlimited-OCR: nur data\cv-test-20261020-093337 und dessen Unterordner.
echo Rohtext bleibt erhalten. Das lokale 8B-LLM ordnet die OCR-Zellen den Teilnehmerfeldern zu.
if not exist "unlimited_ocr_runtime\.venv\Scripts\python.exe" (
    echo Zuerst: uv sync --locked --project unlimited_ocr_runtime
    set "MODEL_EXIT_CODE=1"
    goto :finish
)
".venv\Scripts\participant-bench.exe" run --input "data\cv-test-20261020-093337" --config "configs\unlimited-ocr-llm.yaml" --offline
set "MODEL_EXIT_CODE=%ERRORLEVEL%"
:finish
echo.
echo Berichte: runs\LAUF_ID\report.html
pause
popd
exit /b %MODEL_EXIT_CODE%
