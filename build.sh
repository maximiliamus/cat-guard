#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
pyinstaller catguard.spec --clean --noconfirm
