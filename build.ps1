$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot
& .venv\Scripts\Activate.ps1
pyinstaller catguard.spec --clean --noconfirm

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
