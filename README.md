# Download

Pre-built executables are available on the [Releases](../../releases) page — no Python installation required.

1. Go to **Releases** and download the zip for your platform:
   - `catguard-{version}-windows.zip`
   - `catguard-{version}-macos.zip`
   - `catguard-{version}-linux.zip`
2. Extract the zip.
3. Run the executable inside the `catguard/` folder:
   - **Windows**: `catguard\catguard.exe`
   - **macOS / Linux**: `./catguard/catguard`

On first run, CatGuard downloads the YOLO model (~6 MB) — internet access required once.

## OS Security Warnings

**Windows — SmartScreen**

Because the executable is not code-signed, Windows may show a SmartScreen warning.
To allow it: right-click the `.exe` → **Properties** → check **Unblock** → **OK**, then run again.
Alternatively, click **More info** → **Run anyway** in the SmartScreen dialog.

**macOS — Gatekeeper**

macOS blocks unsigned apps by default.
To allow it: open **System Settings** → **Privacy & Security** → scroll to the blocked app → click **Open Anyway**.

---

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

- The default sound is "Tom spells CAT" from [Tom and Jerry Online](https://www.tomandjerryonline.com/sounds.cfm).
- Not a single line of Python code was written by a human.
- Despite its features, this app still doesn't help me with my cat :-)
