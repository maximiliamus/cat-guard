# Development

## Local Setup

CatGuard requires Python 3.14 or newer.

```bash
# 1. Clone the repository
git clone <repo-url>
cd <repo-folder>

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install the package and dependencies
pip install -e .
```

## Run From Source

```bash
python -m catguard
```

On first run, CatGuard will:

1. Create a default config file in the platform config directory.
2. Download the YOLO ONNX model (`~6 MB`) into the configured models directory if it is missing.
3. Start monitoring using camera index `0` with default settings.
4. Appear in the system tray.

## Running Tests

Install development dependencies first:

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

Integration tests marked with `@pytest.mark.integration` require real package installs (`cv2`, `onnxruntime`) and network access if the model has not already been downloaded locally.

## Building the Executable

Install build dependencies:

```bash
pip install -e ".[dev,build]"
```

### Prerequisites

- **Linux**: install system libraries before building:

```bash
sudo apt-get install -y python3-tk libportaudio2 libsndfile1
```

### Build

```bash
pyinstaller catguard.spec --clean --noconfirm
```

Output is placed in `dist/catguard/`. The entry point is:

| Platform | Executable |
|---|---|
| Windows | `dist\catguard\catguard.exe` |
| macOS | `dist/catguard/catguard` |
| Linux | `dist/catguard/catguard` |

### Package Into a Zip

```bash
# Windows (PowerShell)
Compress-Archive -Path dist\catguard -DestinationPath catguard-windows.zip

# macOS / Linux
cd dist && zip -r ../catguard-linux.zip catguard
```

The CI workflow (`.github/workflows/build.yml`) runs the full build, test, and package cycle automatically on every push to `master` and on version tags (`v*`).

## Development Notes

- AI-driven
- Spec-driven with [Spec Kit](https://github.com/github/spec-kit)
- Cross-platform
