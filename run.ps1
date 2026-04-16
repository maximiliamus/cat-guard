$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot
python -m catguard

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
