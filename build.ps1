$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot
pyinstaller catguard.spec --clean --noconfirm

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
