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

On first launch the app downloads the YOLO model (~6 MB) automatically and caches it locally — internet access is required only once.

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
1. Create a default config file at the platform config directory.
2. Start monitoring using camera index `0` with default settings.
3. Appear in the system tray.

# Development

- AI-driven
- Spec-driven with [Spec Kit](https://github.com/github/spec-kit)
- Cross-platform

## Running Tests

Install dev dependencies first:

```bash
pip install -e ".[dev]"
```

| Command | What it runs |
|---|---|
| `pytest` | All tests |
| `pytest -m "not integration"` | Unit tests only (used in CI) |
| `pytest -m integration` | Integration tests only |
| `pytest tests/unit/` | All unit tests by directory |
| `pytest tests/integration/` | All integration tests by directory |
| `pytest tests/unit/test_main_window.py` | A single test file |
| `pytest tests/unit/test_main_window.py::TestUpdateFrame` | A single test class |

> **Note:** Integration tests marked with `@pytest.mark.integration` require real package installs (cv2, onnxruntime) and a network connection (the model is downloaded on first run). Tests without this marker run in all modes.


## Building the Executable

Requires the build extras and PyInstaller:

```bash
pip install -e ".[dev,build]"
```

**Prerequisites**

- **Linux**: install system libraries before building:
  ```bash
  sudo apt-get install -y python3-tk libportaudio2 libsndfile1
  ```

**Build**

```bash
pyinstaller catguard.spec --clean --noconfirm
```

Output is placed in `dist/catguard/`. The entry point is:

| Platform | Executable |
|----------|-----------|
| Windows | `dist\catguard\catguard.exe` |
| macOS | `dist/catguard/catguard` |
| Linux | `dist/catguard/catguard` |

**Package into a zip**

```bash
# Windows (PowerShell)
Compress-Archive -Path dist\catguard -DestinationPath catguard-windows.zip

# macOS / Linux
cd dist && zip -r ../catguard-linux.zip catguard
```

The CI workflow (`.github/workflows/build.yml`) runs the full build + test + package cycle automatically on every push to `master` and on version tags (`v*`).

---

# Interesting Facts

- The default sound is "Tom spells CAT" from [Tom and Jerry Online](https://www.tomandjerryonline.com/sounds.cfm).
- Not a single line of Python code was written by a human.
- It works! :-)
