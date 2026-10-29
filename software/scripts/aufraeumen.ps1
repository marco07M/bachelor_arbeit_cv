param(
    [switch]$Ausfuehren,
    [ValidateRange(1, 100)][int]$LetzteLaeufe = 2,
    [ValidateRange(1, 100)][int]$LetzteVergleiche = 3
)

# Default: show the plan. Only -Ausfuehren deletes generated results and caches.
$ErrorActionPreference = 'Stop'
$softwareRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$workspaceRoot = Split-Path -Parent $softwareRoot
$runRoot = Join-Path $softwareRoot 'runs'
$comparisonRoot = Join-Path $softwareRoot 'testframework/ergebnisse'
$roots = @($runRoot, $comparisonRoot)
$all = @{}
$keep = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$queue = [System.Collections.Generic.Queue[string]]::new()

function Add-Kept([string]$path) {
    if ($keep.Add($path)) { $queue.Enqueue($path) }
}

foreach ($root in $roots) {
    $all[$root] = @(if (Test-Path -LiteralPath $root) {
        if ((Get-Item -LiteralPath $root).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Linked result directory is not supported: $root"
        }
        Get-ChildItem -LiteralPath $root -Directory -Force
    })
    if (@($all[$root] | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) {
        throw "Linked result entry is not supported: $root"
    }
    $count = if ($root -eq $runRoot) { $LetzteLaeufe } else { $LetzteVergleiche }
    $complete = @($all[$root] | Where-Object {
        $_.Name -match '^\d{8}T\d{6}Z-[0-9a-f]{8}$' -and
        (Test-Path -LiteralPath (Join-Path $_.FullName 'report.html') -PathType Leaf)
    } | Sort-Object Name -Descending | Select-Object -First $count)
    foreach ($folder in $complete) { Add-Kept $folder.FullName }
}

# Preserve the source runs needed by kept reports, prepared images and resume manifests.
while ($queue.Count -gt 0) {
    $folder = $queue.Dequeue()
    foreach ($name in @('identity.json', 'assignment_recheck.json', 'manifest.json')) {
        $file = Join-Path $folder $name
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { continue }
        if ((Get-Item -LiteralPath $file).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Linked metadata file is not supported: $file"
        }
        $data = Get-Content -LiteralPath $file -Raw -Encoding UTF8 | ConvertFrom-Json
        $references = @($data.source_run, $data.source_manifest)
        if ($name -eq 'manifest.json') {
            $references += @($data.pages | ForEach-Object { $_.image })
        }
        foreach ($value in $references) {
            if ($value -isnot [string] -or -not $value) { continue }
            $path = if ([IO.Path]::IsPathRooted($value)) { $value } else { Join-Path $folder $value }
            $resolved = [IO.Path]::GetFullPath($path)
            foreach ($root in $roots) {
                $prefix = $root + [IO.Path]::DirectorySeparatorChar
                if ($resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
                    $namePart = $resolved.Substring($prefix.Length).Split([IO.Path]::DirectorySeparatorChar)[0]
                    $dependency = Join-Path $root $namePart
                    if ($all[$root].FullName -contains $dependency) { Add-Kept $dependency }
                }
            }
        }
    }
}

$targets = @($roots | ForEach-Object { $all[$_] } | Where-Object { -not $keep.Contains($_.FullName) })
$cachePaths = @('.pytest_cache', '.ruff_cache', 'api_firmen_pc/.pytest_cache', 'api_firmen_pc/.ruff_cache')
$cachePaths = @($cachePaths | ForEach-Object { Join-Path $softwareRoot $_ }) + @(Join-Path $workspaceRoot '.ruff_cache')
foreach ($relative in @('verarbeitung/src', 'tests', 'scripts', 'structure_runtime', 'api_firmen_pc/src',
                        'api_firmen_pc/tests', 'api_firmen_pc/scripts')) {
    $codeRoot = Join-Path $softwareRoot $relative
    if (Test-Path -LiteralPath $codeRoot) {
        $cachePaths += @(Get-ChildItem -LiteralPath $codeRoot -Directory -Filter '__pycache__' -Recurse -Force |
            ForEach-Object { $_.FullName })
    }
}
$cachePaths += Join-Path $softwareRoot 'vorverarbeitung/__pycache__'
foreach ($path in ($cachePaths | Select-Object -Unique)) {
    if (Test-Path -LiteralPath $path -PathType Container) { $targets += Get-Item -LiteralPath $path -Force }
}
$obsolete = Join-Path $softwareRoot 'test_url'
if ((Test-Path -LiteralPath $obsolete -PathType Container) -and
    @(Get-ChildItem -LiteralPath $obsolete -Force).Count -eq 0) {
    $targets += Get-Item -LiteralPath $obsolete
}

# Validate every absolute target before deleting anything. Never follow junctions or links.
$entries = @()
foreach ($target in $targets) {
    $absolute = [IO.Path]::GetFullPath($target.FullName)
    if (-not $absolute.StartsWith($workspaceRoot + [IO.Path]::DirectorySeparatorChar,
                                 [StringComparison]::OrdinalIgnoreCase)) {
        throw "Target outside this workspace: $absolute"
    }
    if ($keep.Contains($absolute)) { throw "Retained result selected for deletion: $absolute" }
    $ancestor = $absolute
    while ($ancestor -and $ancestor -ne $workspaceRoot) {
        if ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Linked ancestor of cleanup target: $ancestor"
        }
        $ancestor = Split-Path -Parent $ancestor
    }
    if (($target.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        @(Get-ChildItem -LiteralPath $absolute -Recurse -Force | Where-Object {
            $_.Attributes -band [IO.FileAttributes]::ReparsePoint
        }).Count) { throw "Linked entry in cleanup target: $absolute" }
    $bytes = (Get-ChildItem -LiteralPath $absolute -File -Recurse -Force | Measure-Object Length -Sum).Sum
    $entries += [PSCustomObject]@{ path = $absolute; bytes = [long]$bytes }
}

Write-Host ('Kept result folders: ' + $keep.Count)
Write-Host ('Cleanup targets: ' + $entries.Count)
Write-Host ('Size: {0:N1} MiB' -f (($entries | Measure-Object bytes -Sum).Sum / 1MB))
$entries | ForEach-Object { Write-Host ('  ' + $_.path.Substring($workspaceRoot.Length + 1)) }
if (-not $Ausfuehren) {
    Write-Host 'Preview only. Apply with -Ausfuehren.'
    return
}
if (@(Get-Process -Name python, pythonw, participant-bench -ErrorAction SilentlyContinue).Count) {
    throw 'Close active Python/model/test processes before deleting generated results.'
}
foreach ($entry in $entries) { Remove-Item -LiteralPath $entry.path -Recurse -Force }
foreach ($root in $roots) {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $lines = @('# Behaltene Ergebnisse', '', 'Aktuelle Berichte und ihre benoetigten Quelllaeufe:', '')
    foreach ($folder in @($all[$root] | Where-Object { $keep.Contains($_.FullName) } | Sort-Object Name -Descending)) {
        $lines += ('- [' + $folder.Name + '](' + $folder.Name + '/report.html)')
    }
    $lines += @('', 'Neue Laeufe werden daneben gespeichert. Bereinigung: `scripts/aufraeumen.ps1` aus `software/`.')
    $lines | Set-Content -LiteralPath (Join-Path $root 'README.md') -Encoding UTF8
}
$auditRoot = Join-Path $softwareRoot '.cache/cleanup'
New-Item -ItemType Directory -Path $auditRoot -Force | Out-Null
[PSCustomObject]@{
    timestamp_utc = [DateTime]::UtcNow.ToString('o')
    retained = @($keep | Sort-Object)
    deleted = $entries
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $auditRoot 'latest.json') -Encoding UTF8
Write-Host 'Cleanup complete. Local indexes: runs/README.md and testframework/ergebnisse/README.md'
