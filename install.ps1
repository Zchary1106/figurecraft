$ErrorActionPreference = "Stop"
$installer = Join-Path $PSScriptRoot "install.py"
$python = $null
$prefix = @()
$candidates = @("py", "python", "python3")
if ($env:FIGURECRAFT_PYTHON) {
    $candidates = @($env:FIGURECRAFT_PYTHON)
}
foreach ($candidate in $candidates) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue
    if (-not $command) { continue }
    $candidatePrefix = @()
    if ($candidate -eq "py") { $candidatePrefix = @("-3") }
    try {
        & $command.Source @candidatePrefix -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $python = $command.Source
            $prefix = $candidatePrefix
            break
        }
    } catch {
        continue
    }
}
if (-not $python) {
    [Console]::Error.WriteLine("FigureCraft needs Python 3.11+. Install it from python.org, then retry.")
    exit 1
}
& $python @prefix $installer --setup --scope user --agent all @args
exit $LASTEXITCODE
