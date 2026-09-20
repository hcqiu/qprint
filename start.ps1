param(
    [string]$Workspace = "$PSScriptRoot/examples/demo",
    [int]$Port = 8765
)
$ErrorActionPreference = 'Stop'
$qprintCondaCommand = Get-Command conda -ErrorAction SilentlyContinue
if ($qprintCondaCommand) {
    $qprintConda = $qprintCondaCommand.Source
} else {
    $qprintConda = @(
        "$env:USERPROFILE/anaconda3/Scripts/conda.exe",
        "$env:USERPROFILE/miniconda3/Scripts/conda.exe"
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $qprintConda) { throw 'Conda not found. Run from Anaconda PowerShell Prompt.' }
$env:PYTHONIOENCODING = 'utf-8'
Push-Location $PSScriptRoot
try {
    & $qprintConda run --no-capture-output -n qprint python -m qprint serve --workspace $Workspace --port $Port
} finally {
    Pop-Location
}
