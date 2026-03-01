# Quickstart: CatGuard App

## Prerequisites

- Python 3.11 or newer
- A webcam connected and accessible
- (Linux only) For Wayland system tray support:  
  `sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1`

---

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

---

## First Run

```bash
python -m catguard
```

On first run, CatGuard will:
1. Download the YOLO11n model weights (~6 MB) to `~/.ultralytics/assets/` (internet required once only).
2. Create a default config file at the platform config directory.
3. Start monitoring using camera index `0` with default settings.
4. Appear in the system tray.

---

## Configuration

Right-click the tray icon → **Settings...** to open the Settings window.

| Setting | Default | Description |
|---|---|---|
| Camera | `0` | Select which webcam to use |
| Detection sensitivity | `0.40` | YOLO confidence threshold (0 = more detections, 1 = fewer) |
| Alert cooldown | `15 s` | Minimum time between consecutive alerts |
| Sound library | *(empty — uses built-in)* | Upload MP3/WAV files for alert sounds |
| Autostart on login | Off | Start CatGuard automatically when you log in |

---

## Adding Alert Sounds

1. Open **Settings...** from the tray menu.
2. Click **Add Sound** and select one or more MP3 or WAV files.
3. Sounds are played in random order on each detection.
4. If no sounds are added, the built-in default sound is used.

---

## Exiting

Right-click the tray icon → **Exit** to fully quit the app.  
Closing the Settings window does **not** stop monitoring.

---

## Running Tests

```bash
# Unit tests
pytest tests/unit/

# Integration tests (requires webcam + audio)
pytest tests/integration/

# All tests
pytest
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| No tray icon on Linux Wayland | Install `gir1.2-ayatanaappindicator3-0.1` and restart |
| Camera not found | Check camera index in Settings; try index `1` or `2` |
| Sound not playing when screen is locked | Ensure audio session is not suspended; check OS audio settings |
| High CPU usage | Reduce camera resolution or switch to ONNX export (`yolo11n.onnx`) |
| YOLO model not downloading | Check internet connection on first run; model is cached after that |
