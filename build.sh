#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
source .venv/bin/activate
pyinstaller catguard.spec --clean --noconfirm
