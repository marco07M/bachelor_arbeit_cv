param()

$ErrorActionPreference = 'Stop'
$config = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'toolchain.json') -Raw | ConvertFrom-Json
$toolDirectory = Join-Path $PSScriptRoot '.tools'
$texBin = Join-Path $toolDirectory 'TinyTeX\bin\windows'
$archive = Join-Path $toolDirectory ('TinyTeX-' + $config.version + '.zip')
New-Item -ItemType Directory -Force -Path $toolDirectory | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $texBin 'pdflatex.exe'))) {
    if (-not (Test-Path -LiteralPath $archive)) {
        Write-Host 'Portable TinyTeX-Distribution herunterladen...'
        Invoke-WebRequest -Uri $config.windows_archive -OutFile $archive
    }
    $actualHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $config.archive_sha256) { throw 'TinyTeX-Archiv hat eine abweichende SHA256-Pruefsumme.' }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::ExtractToDirectory($archive, $toolDirectory)
}
$previousPath = $env:PATH
$previousLocale = $env:LC_ALL
$env:PATH = $texBin + ';' + $env:PATH
$env:LC_ALL = 'C'
try {
    $tlmgr = Join-Path $texBin 'tlmgr.bat'
    & $tlmgr option repository $config.repository
    if ($LASTEXITCODE -ne 0) { throw 'TeX-Live-Paketquelle konnte nicht gesetzt werden.' }
    & $tlmgr update --self
    if ($LASTEXITCODE -ne 0) { throw 'TeX-Live-Paketmanager konnte nicht aktualisiert werden.' }
    & $tlmgr install @($config.packages)
    if ($LASTEXITCODE -ne 0) { throw 'LaTeX-Pakete konnten nicht vollstaendig installiert werden.' }
    # Die lokale tlpdb ist das tatsaechliche Installationsinventar, ohne weitere Netzabfrage.
    $packageDatabase = Join-Path $toolDirectory 'TinyTeX\tlpkg\texlive.tlpdb'
    $inventory = Get-Content -LiteralPath $packageDatabase | Where-Object { $_ -match '^(name|revision|cat-version) ' }
    $inventory | Set-Content -LiteralPath (Join-Path $toolDirectory 'texlive-packages.txt') -Encoding UTF8
    Copy-Item -LiteralPath $packageDatabase -Destination (Join-Path $toolDirectory 'texlive-installed.tlpdb') -Force
    foreach ($requiredFile in @('scrbook.cls','ngerman.ldf','acronym.sty','suffix.sty','relsize.sty','IEEEtran.bst')) {
        $found = & kpsewhich $requiredFile
        if (-not $found) { throw "Einrichtung unvollstaendig: $requiredFile fehlt." }
    }
    Write-Host 'TinyTeX lokal eingerichtet. Es wurde kein globaler PATH veraendert.'
    Write-Host 'PDF bauen: powershell -NoProfile -ExecutionPolicy Bypass -File bachelorarbeit/build.ps1'
}
finally {
    $env:PATH = $previousPath
    $env:LC_ALL = $previousLocale
}
