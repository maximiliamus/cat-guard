# Quickstart: Tray → Open → Main Window

Step-by-step guide to manually verify the *Tray Open → Main Window* feature.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | `python --version` |
| Webcam / capture device | Any device recognised by OpenCV (`/dev/video0`, USB) |
| CatGuard installed | `pip install -e .` from repo root |
| YOLO model present | `yolo11n.pt` in repo root |

---

## 1 — Start the application

```bash
# from the repo root
python -m catguard
```

The application starts without a visible window; only the **system tray icon** appears.

---

## 2 — Locate the tray icon

| Platform | Location |
|---|---|
| Windows | System tray (bottom-right taskbar, click ▲ to expand) |
| macOS | Menu bar (top-right) |
| Linux (X11) | System tray / notification area |

---

## 3 — Open the context menu

**Right-click** (Windows/Linux) or **click** (macOS) the CatGuard tray icon.

Expected menu:

```
Settings…
Open
Exit
```

> Verify the order: **Settings…** first, **Open** second, **Exit** last.

---

## 4 — Click "Open"

Click **Open** in the context menu.

Expected result:

- A new window titled **"CatGuard — Live View"** appears.
- The window is sized to the **exact pixel dimensions** of the captured video frame  
  (e.g. 640 × 480 for a typical webcam, or clamped to your screen resolution if the frame is larger).
- The window shows the **live camera feed** immediately.

---

## 5 — Verify detection overlays

Point the camera at a **cat** (or use a photo of a cat on your phone).

Expected result:

| Element | Description |
|---|---|
| **Green rectangle** | Bounding box drawn around the cat |
| **"cat" label** | Text label above the top-left corner of the bounding box |
| **No "No detections" text** | The overlay message disappears when a cat is detected |

When **no cat** is visible:

- The window still shows the live feed.
- The text **"No detections"** is displayed in the top-left corner of the canvas.

---

## 6 — Re-open the window

Close the main window (click the ✕ close button).  
Right-click the tray icon again and select **Open**.

Expected result: A **new** main window opens (not a duplicate).

---

## 7 — Verify Exit still works

Right-click the tray icon and select **Exit**.

Expected result: The application quits, the tray icon disappears, the main window (if open) also closes.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "Open" not in menu | Old pystray cached; stale `.pyc` | `find . -name "*.pyc" -delete && python -m catguard` |
| Window does not appear | `tkinter` not installed | `sudo apt-get install python3-tk` (Linux) |
| Black / frozen frame | Webcam index wrong | Check `settings.camera_index` in Settings… |
| Window too small / large | Frame clamped to screen | Expected behaviour for frames > screen size |
| No bounding boxes | Model not loaded | Confirm `yolo11n.pt` exists in repo root |
