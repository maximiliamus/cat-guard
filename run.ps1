$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot
& .\.venv\Scripts\Activate.ps1
python -m catguard

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
