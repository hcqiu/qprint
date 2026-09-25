param(
    [string]$Workspace = 'examples/demo',
    [int]$Port = 8765,
    [switch]$AllowVerification,
    [string]$ToolchainHome = '.',
    [switch]$AllowSystemToolchains
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
    if ($Workspace -eq 'examples/demo' -and -not (Test-Path -LiteralPath $Workspace)) {
        $Workspace = 'examples/verification'
    }
    $qprintServeArguments = @('run', '--no-capture-output', '-n', 'qprint', 'python', '-m', 'qprint', 'serve',
        '--workspace', $Workspace, '--port', $Port, '--toolchain-home', $ToolchainHome)
    if ($AllowVerification) { $qprintServeArguments += '--allow-verification' }
    if ($AllowSystemToolchains) { $qprintServeArguments += '--allow-system-toolchains' }
    & $qprintConda @qprintServeArguments
} finally {
    Pop-Location
}
