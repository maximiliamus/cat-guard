# Quickstart: Screenshot on Cat Detection

Step-by-step guide to manually verify the *Screenshot on Cat Detection* feature.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | `python --version` |
| Webcam / capture device | Any device recognised by OpenCV |
| CatGuard installed | `pip install -e .` from repo root |
| YOLO model present | `yolo11n.pt` in repo root |

---

## 1 — Start the application

```bash
# from the repo root
python -m catguard
```

The app starts with only the **system tray icon** visible.

---

## 2 — Verify default screenshot folder

Right-click the tray icon → **Settings…** → scroll to the **Screenshots** section.

Expected:

- The root folder field shows the OS default path:  
  **Windows**: `C:\Users\<you>\Pictures\CatGuard`  
  **macOS**: `/Users/<you>/Pictures/CatGuard`  
  **Linux**: `/home/<you>/Pictures/CatGuard`
- The "Restrict to time window" checkbox is **unchecked**.
- Start / end time fields are disabled (greyed out) while the checkbox is unchecked.

---

## 3 — Trigger a detection (screenshots on)

Make sure the main window is **closed** (no "CatGuard — Live View" window open).

Hold a photo of a cat in front of the camera, or point the camera at a real cat.

Expected:
1. Alert sound plays.
2. A new folder `<today's date in yyyy-mm-dd>` appears inside the configured root folder.
3. A JPEG file named `HH-MM-SS.jpg` (current time) appears inside that folder.

```
Pictures/
└── CatGuard/
    └── 2026-03-01/
        └── 14-35-22.jpg
```

---

## 4 — Verify main-window suppression

1. Open the main window: right-click tray → **Open**.
2. While the window is open, trigger a detection again.

Expected:
- Alert sound plays as normal.
- **No** new screenshot file is created.

3. Close the main window.
4. Trigger a detection again.

Expected:
- Screenshot is saved again.

---

## 5 — Change the root folder

1. Open **Settings…** → Screenshots section → click **Browse…**.
2. Select a different folder (e.g., your Desktop).
3. Click **Save**.
4. Trigger a detection.

Expected:
- The screenshot appears in `<Desktop>/<today>/<HH-MM-SS.jpg>` — not in the original folder.

---

## 6 — Test the time window

1. Open **Settings…** → Screenshots section.
2. Check **Restrict to time window**.
3. Set start and end times to a range that **excludes** the current time  
   (e.g., if it is 14:30, set 22:00 → 06:00).
4. Click **Save**.
5. Trigger a detection.

Expected:
- Alert sound plays.
- **No** screenshot is created.

6. Set start and end times to a range that **includes** the current time  
   (e.g., 00:00 → 23:59, or just uncheck the checkbox).
7. Click **Save** and trigger another detection.

Expected:
- Screenshot is created normally.

---

## 7 — Test graceful failure (optional)

1. Set the root folder to a **read-only** path (e.g., `C:\Windows` on Windows or `/root` on Linux without sudo).
2. Click **Save**.
3. Trigger a detection.

Expected:
- Alert sound plays.
- A tray balloon / OS notification appears with a message describing the save failure (e.g., "Permission denied").
- No crash; the app continues monitoring.

---

## Running Tests

```bash
# All tests
pytest

# Unit tests only (no camera required)
pytest tests/unit/

# Screenshot-specific unit tests
pytest tests/unit/test_screenshots.py -v

# Integration tests (requires a camera or mock)
pytest tests/integration/test_screenshot_integration.py -v
```
