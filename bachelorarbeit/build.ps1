param(
    [ValidateSet('Build', 'Doctor', 'Clean', 'DistClean')]
    [string]$Action = 'Build'
)

$ErrorActionPreference = 'Stop'
$originalPath = $env:PATH
$originalLocale = $env:LC_ALL
$project = [IO.Path]::GetFullPath($PSScriptRoot)
$buildDirectory = [IO.Path]::GetFullPath((Join-Path $project 'build'))
if (-not $buildDirectory.StartsWith($project + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Buildverzeichnis liegt ausserhalb der Bachelorarbeit.'
}
$localBin = Join-Path $project '.tools\TinyTeX\bin\windows'
if (Test-Path -LiteralPath (Join-Path $localBin 'latexmk.exe')) {
    $env:PATH = $localBin + ';' + $env:PATH
}
$env:LC_ALL = 'C'
$buildExitCode = 0
Push-Location -LiteralPath $project
try {
    $latexmk = Get-Command latexmk -ErrorAction SilentlyContinue
    if (-not $latexmk) {
        throw 'latexmk fehlt. Zuerst bachelorarbeit/setup.ps1 ausfuehren oder TeX Live/MiKTeX samt Perl installieren.'
    }
    switch ($Action) {
        'Doctor' {
            foreach ($program in @('latexmk','pdflatex','bibtex','kpsewhich')) {
                $command = Get-Command $program -ErrorAction Stop
                Write-Host "$program : $($command.Source)"
            }
            & $latexmk.Source -v
            if ($LASTEXITCODE -ne 0) { throw 'latexmk/Perl nicht funktionsfaehig.' }
            foreach ($file in @('scrbook.cls','ngerman.ldf','lmodern.sty','microtype.sty','csquotes.sty','acronym.sty','suffix.sty','relsize.sty','dehyphn.tex','booktabs.sty','tabularx.sty','hyperref.sty','IEEEtran.bst')) {
                $found = & kpsewhich $file
                if ($LASTEXITCODE -ne 0 -or -not $found) { throw "LaTeX-Paketdatei fehlt: $file; setup.ps1 erneut ausfuehren." }
                Write-Host "$file : $found"
            }
        }
        'Build' {
            New-Item -ItemType Directory -Force -Path $buildDirectory | Out-Null
            & $latexmk.Source -pdf -interaction=nonstopmode -halt-on-error -file-line-error thesis.tex
            $buildExitCode = $LASTEXITCODE
            if ($buildExitCode -eq 0) {
                $pdf = Join-Path $buildDirectory 'thesis.pdf'
                if (-not (Test-Path -LiteralPath $pdf)) { throw 'LaTeX meldet Erfolg, aber die PDF fehlt.' }
                Write-Host "PDF erstellt: $pdf"
                $versions = @('Build: pdfLaTeX + BibTeX, ohne Shell-Escape', 'Compiler:', (& pdflatex --version | Select-Object -First 2), 'BibTeX:', (& bibtex --version | Select-Object -First 2))
                $versions | Set-Content -LiteralPath (Join-Path $buildDirectory 'toolchain.txt') -Encoding UTF8
            }
        }
        'Clean' {
            & $latexmk.Source -c thesis.tex
            $buildExitCode = $LASTEXITCODE
        }
        'DistClean' {
            & $latexmk.Source -C thesis.tex
            $buildExitCode = $LASTEXITCODE
        }
    }
}
catch {
    Write-Error -Message $_ -ErrorAction Continue
    $buildExitCode = 1
}
finally {
    Pop-Location
    $env:PATH = $originalPath
    $env:LC_ALL = $originalLocale
}
exit $buildExitCode
