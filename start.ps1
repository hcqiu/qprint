param(
    [string]$Workspace = 'examples/demo',
    [int]$Port = 8765,
    [switch]$AllowVerification,
    [string]$ToolchainHome = '.',
    [switch]$AllowSystemToolchains
)
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath '.\.conda\python.exe' -PathType Leaf)) {
        throw 'Project Python is missing. In Anaconda Prompt / Miniconda Prompt, open the Qprint folder and run: conda env create -p .\.conda -f environment.yml'
    }
    if ($Workspace -eq 'examples/demo' -and -not (Test-Path -LiteralPath $Workspace)) {
        $Workspace = 'examples/verification'
    }
    $qprintServeArguments = @('-m', 'qprint', 'serve',
        '--workspace', $Workspace, '--port', $Port, '--toolchain-home', $ToolchainHome)
    if ($AllowVerification) { $qprintServeArguments += '--allow-verification' }
    if ($AllowSystemToolchains) { $qprintServeArguments += '--allow-system-toolchains' }
    & .\.conda\python.exe @qprintServeArguments
    $qprintExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $qprintExitCode
