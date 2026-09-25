param([switch]$Full, [string]$Output)
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    if (-not (Test-Path -LiteralPath '.\.conda\python.exe' -PathType Leaf)) {
        throw 'Project Python is missing. In Anaconda Prompt / Miniconda Prompt, open the Qprint folder and run: conda env create -p .\.conda -f environment.yml'
    }
    $qprintArguments = @('tools/build_release.py')
    if ($Full) { $qprintArguments += '--full' }
    if ($Output) { $qprintArguments += @('--output', $Output) }
    & .\.conda\python.exe @qprintArguments
    $qprintExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $qprintExitCode
