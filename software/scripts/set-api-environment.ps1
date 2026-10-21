# Run manually in a separate PowerShell opened outside the IDE/Codex.
# Only this process and its children receive the values. Never persist them globally.
[CmdletBinding()]
param([string]$EnvFile, [switch]$NoPrompt)

$apiVariableNames = @(
    'BMW_AI_API_KEY', 'BMW_AI_CLIENT_ID', 'BMW_AI_CLIENT_SECRET',
    'BMW_AI_BASE_URL', 'BMW_AI_TOKEN_URL', 'BMW_AI_API_KEY_HEADER',
    'BMW_LLM_MODEL', 'BMW_VLM_MODEL', 'BMW_AI_CHAT_PATH', 'BMW_AI_SCOPE', 'BMW_AI_RESOURCE',
    'LLM_API_BASE_URL', 'LLM_API_MODEL', 'LLM_API_KEY', 'VLM_API_BASE_URL', 'VLM_API_MODEL', 'VLM_API_KEY'
)

function Import-BenchmarkApiEnvironment {
    param([string]$Path)
    $apiFilePath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    $repositoryDirectory = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')).TrimEnd('\', '/')
    if ($apiFilePath.Equals($repositoryDirectory, [StringComparison]::OrdinalIgnoreCase) -or
        $apiFilePath.StartsWith($repositoryDirectory + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Die Zugangsdaten-Datei muss ausserhalb des gesamten Repositories liegen.'
    }
    if (-not [IO.File]::Exists($apiFilePath)) {
        throw 'Die explizit angegebene externe Zugangsdaten-Datei wurde nicht gefunden.'
    }
    $apiEntries = @{}
    try {
        $apiLineNumber = 0
        foreach ($apiLine in [IO.File]::ReadLines($apiFilePath)) {
            $apiLineNumber++
            $apiEntry = $apiLine.Trim()
            if (-not $apiEntry -or $apiEntry.StartsWith('#')) { continue }
            if ($apiEntry -notmatch '^([A-Z][A-Z0-9_]*)\s*=\s*(.*)$') {
                throw "Ungueltiges NAME=WERT-Format in Zeile $apiLineNumber; Inhalt wird nicht ausgegeben."
            }
            $apiName, $apiValue = $Matches[1], $Matches[2].Trim()
            if ($apiName -notin $apiVariableNames -or $apiEntries.ContainsKey($apiName)) {
                throw "Unbekannte oder doppelte Variable in Zeile $apiLineNumber; Inhalt wird nicht ausgegeben."
            }
            if ($apiValue.Length -ge 2 -and (
                ($apiValue.StartsWith('"') -and $apiValue.EndsWith('"')) -or
                ($apiValue.StartsWith("'") -and $apiValue.EndsWith("'")))) {
                $apiValue = $apiValue.Substring(1, $apiValue.Length - 2)
            }
            # Data only: never evaluate file contents, expand variables, or execute commands.
            $apiEntries[$apiName] = $apiValue
        }
        foreach ($apiName in $apiEntries.Keys) {
            [Environment]::SetEnvironmentVariable($apiName, $apiEntries[$apiName], 'Process')
        }
    } finally {
        $apiEntries.Clear()
        $apiValue = $apiLine = $apiEntry = $null
        $Matches = $null
    }
    Write-Host 'Externe Zugangsdaten-Datei nur fuer diesen Prozess geladen; keine Werte ausgegeben.'
}

if ($EnvFile) {
    Import-BenchmarkApiEnvironment -Path $EnvFile
}

function Set-BenchmarkApiVariable {
    param([string]$Name, [string]$Label, [switch]$Secret)
    if ([Environment]::GetEnvironmentVariable($Name, 'Process')) {
        Write-Host "$Name ist bereits gesetzt."
        return
    }
    if ($NoPrompt) { return }
    if ($Secret) {
        $secureApiInput = Read-Host "$Label (Eingabe verborgen, Enter zum Ueberspringen)" -AsSecureString
        $apiInputValue = [System.Net.NetworkCredential]::new('', $secureApiInput).Password
        $secureApiInput.Dispose()
    } else {
        $apiInputValue = Read-Host "$Label (Enter zum Ueberspringen)"
    }
    if ($apiInputValue) {
        [Environment]::SetEnvironmentVariable($Name, $apiInputValue, 'Process')
        Write-Host "$Name gesetzt."
    }
    $apiInputValue = $null
}

Set-BenchmarkApiVariable 'BMW_AI_API_KEY' 'API-Key' -Secret
Set-BenchmarkApiVariable 'BMW_AI_CLIENT_ID' 'Client-ID' -Secret
Set-BenchmarkApiVariable 'BMW_AI_CLIENT_SECRET' 'Client-Secret' -Secret
Set-BenchmarkApiVariable 'BMW_AI_BASE_URL' 'Interne API-Basisadresse, ohne /chat/completions'
Set-BenchmarkApiVariable 'BMW_AI_TOKEN_URL' 'OAuth-Token-URL'
Set-BenchmarkApiVariable 'BMW_AI_API_KEY_HEADER' 'Headername fuer den API-Key laut interner Dokumentation'
Set-BenchmarkApiVariable 'BMW_LLM_MODEL' 'LLM-Modellname'
Set-BenchmarkApiVariable 'BMW_VLM_MODEL' 'VLM-Modellname mit Bildunterstuetzung'
Set-BenchmarkApiVariable 'BMW_AI_CHAT_PATH' 'Optionaler Anfragepfad, Standard chat/completions'
Set-BenchmarkApiVariable 'BMW_AI_SCOPE' 'Optionaler OAuth-Scope'
Set-BenchmarkApiVariable 'BMW_AI_RESOURCE' 'Optionale OAuth-Resource'
Write-Host 'Pruefen: .venv/Scripts/participant-bench.exe api-check --config configs/api-bmw.yaml'
