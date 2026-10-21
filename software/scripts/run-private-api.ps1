# Start this yourself in a new PowerShell from the Windows Start menu, outside the IDE/Codex.
[CmdletBinding()]
param(
    [string]$InputFolder = 'vorverarbeitung/ausgabe/pdfs',
    [string]$Config = 'configs/api-bmw.yaml',
    [string]$EnvFile,
    [switch]$CheckOnly,
    [switch]$NoPrompt
)

$ErrorActionPreference = 'Stop'
$apiExitCode = 1
$softwareDirectory = Split-Path $PSScriptRoot -Parent
$apiCredentialNames = @(
    'BMW_AI_API_KEY', 'BMW_AI_CLIENT_ID', 'BMW_AI_CLIENT_SECRET', 'LLM_API_KEY', 'VLM_API_KEY'
)
Push-Location -LiteralPath $softwareDirectory
try {
    $benchmarkExecutable = Join-Path $softwareDirectory '.venv\Scripts\participant-bench.exe'
    if (-not (Test-Path -LiteralPath $benchmarkExecutable -PathType Leaf)) {
        throw 'Die Projektumgebung fehlt. Bitte zuerst uv sync --locked im Ordner software ausfuehren.'
    }
    & (Join-Path $PSScriptRoot 'set-api-environment.ps1') -EnvFile $EnvFile -NoPrompt:$NoPrompt
    if ($CheckOnly) {
        & $benchmarkExecutable api-check --config $Config
    } else {
        & $benchmarkExecutable run --input $InputFolder --config $Config
    }
    $apiExitCode = $LASTEXITCODE
} finally {
    foreach ($apiCredentialName in $apiCredentialNames) {
        [Environment]::SetEnvironmentVariable($apiCredentialName, $null, 'Process')
    }
    Pop-Location
}
exit $apiExitCode
