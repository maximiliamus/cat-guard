# Overview

CatGuard is an application that uses a webcam to monitor your table for your cat. If a cat is detected on the table, the app plays a sound to scare it away. So, it protects your work table from your cat and protects your cat from you - your punishment if it accidentally breaks something on your table :-)

# Quickstart

## Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd catguard

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install the package and dependencies
pip install -e .
```

## First Run

```bash
python -m catguard
```

On first run, CatGuard will:
1. Download the YOLO11n model weights (~6 MB) to the following locations (internet required once only):
   - **Linux/macOS**: `~/.ultralytics/assets/`
   - **Windows**: `%USERPROFILE%\.ultralytics\assets\`
2. Create a default config file at the platform config directory.
3. Start monitoring using camera index `0` with default settings.
4. Appear in the system tray.

# Development

- AI-driven
- Spec-driven with [Spec Kit](https://github.com/github/spec-kit)
- Cross-platform

# Interesting Facts

- Default sound is cut from "Tom spells CAT" from https://www.tomandjerryonline.com/sounds.cfm
- This app doesn't help me with my cat :-)
