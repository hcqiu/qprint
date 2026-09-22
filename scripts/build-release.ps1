param([switch]$Full, [string]$Output)
$ErrorActionPreference = 'Stop'
$qprintCondaCommand = Get-Command conda -ErrorAction SilentlyContinue
$qprintConda = if ($qprintCondaCommand) { $qprintCondaCommand.Source } else { "$env:USERPROFILE/anaconda3/Scripts/conda.exe" }
if (-not (Test-Path -LiteralPath $qprintConda)) { throw 'Conda not found.' }
$qprintArguments = @('run', '-n', 'qprint', 'python', "$PSScriptRoot/../tools/build_release.py")
if ($Full) { $qprintArguments += '--full' }
if ($Output) { $qprintArguments += @('--output', $Output) }
& $qprintConda @qprintArguments
exit $LASTEXITCODE
