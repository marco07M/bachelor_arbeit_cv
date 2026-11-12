@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1
if /I "%~1"=="--pruefen" (
    call "start_testframework.cmd" --pruefen
) else (
    call "start_testframework.cmd" --extraction-config "configs\benchmark-five.yaml" %*
)
set "BENCHMARK_EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %BENCHMARK_EXIT_CODE%
