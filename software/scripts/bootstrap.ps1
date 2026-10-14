$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $workspace
$toolDirectory = Join-Path $workspace '.tools'
New-Item -ItemType Directory -Force -Path $toolDirectory | Out-Null
$uvExecutable = Join-Path $toolDirectory 'uv.exe'
if (-not (Test-Path -LiteralPath $uvExecutable)) {
    $archive = Join-Path $toolDirectory 'uv-0.13.1.zip'
    Invoke-WebRequest -Uri 'https://github.com/astral-sh/uv/releases/download/0.13.1/uv-x86_64-pc-windows-msvc.zip' -OutFile $archive
    Expand-Archive -LiteralPath $archive -DestinationPath $toolDirectory -Force
}
$env:UV_CACHE_DIR = Join-Path $workspace '.cache\uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $toolDirectory 'python'
& $uvExecutable sync --locked --extra models
if ($LASTEXITCODE -ne 0) { throw 'uv sync failed' }
Write-Host 'Setup abgeschlossen. Für diese PowerShell-Sitzung:'
Write-Host 'Set-Alias uv (Join-Path $PWD ''.tools\uv.exe'')'
