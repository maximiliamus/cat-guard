# Quickstart: Testing Miscellaneous UI and Behavior Improvements

**Feature**: 007-misc-improvements  
**Date**: March 4, 2026

---

## Prerequisites

```bash
cd d:\Users\maxs\Maxs\Projects\CG\source
.venv\Scripts\activate          # Windows
# or: source .venv/bin/activate  # macOS / Linux
pip install -e ".[dev]"
```

---

## 1. Time Window Enforcement (FR-001 to FR-005b)

### Via unit tests

```bash
pytest tests/unit/test_time_window.py -v
```

Key scenarios covered:
- Window fully in future → auto-pause on start
- Clock crosses window end → auto-pause
- Clock crosses window start → auto-resume
- User Resume during auto-pause → override active
- Override cleared at next window-end crossing

### Manual smoke test

1. Open **Settings** → locate the new "Active Monitoring Window" section.
2. Check **Enable time window**, set **Start** to 1 minute from now and **End** to 2 minutes from now.
3. Save settings. Camera should remain off (current time outside window).
4. Wait for the window to open. Within 60 seconds the camera should activate (tray goes green).
5. Wait for the window to close. Within 60 seconds the camera should deactivate (tray goes grey/default).

---

## 2. Camera Recovery After Sleep (FR-006 to FR-009)

### Via unit tests

```bash
pytest tests/unit/test_sleep_watcher.py -v
```

### Integration test

```bash
pytest tests/integration/test_sleep_resume.py -v
```

### Manual smoke test

1. Start the app with camera active (tray green).
2. Put the computer to sleep: **Start → Power → Sleep**.
3. Wake the computer.
4. Within 10 seconds the tray should return to green and the camera LED should activate.

**Verify time-window interaction**: configure a time window that ends before wake time. On wake, tray should remain in paused state (grey/default).

---

## 3. Sound Library Rename (FR-010 to FR-015b)

### Via unit tests

```bash
pytest tests/unit/test_settings_window.py -v -k rename
```

### Manual smoke test

1. Open **Settings** → **Sound library paths**.
2. Record or import a sound (Add…). Confirm it appears in the list.
3. Select the entry. Click **Rename**.
4. A dialog appears pre-filled with the current filename (without extension).
5. Change the name to `test-renamed`. Click OK.
6. Verify the listbox entry updates immediately.
7. Navigate to `%APPDATA%\CatGuard\alerts\` (Windows). Confirm the file on disk has the new name.

**Rename during playback**: click **▶ Play**, then immediately click **Rename** while playing. Verify playback stops and the rename dialog opens without error.

**Invalid name**: leave the name field empty and click OK. Verify an error is shown and the file is unchanged.

---

## 4. Annotation Label Placement Fallback (FR-016 to FR-019)

### Via unit tests

```bash
pytest tests/unit/test_annotation.py -v -k labelled_box
```

### Manual smoke test (requires cat detection or mock)

The simplest way to trigger an edge-box scenario is to place a cat at the very top of the camera frame:

1. Start the app and open the main window (Open).
2. Hold a cat toy at the very top edge of the camera view; trigger a detection.
3. Verify the confidence label is rendered **below** the bounding box, not clipped at the top.

Alternatively, run the annotation unit tests which inject synthetic frames with boxes at all four edges.

---

## 5. Locale-Aware Date/Time (FR-020 to FR-021)

### Via unit tests

```bash
pytest tests/unit/test_annotation.py -v -k timestamp
```

### Manual smoke test (Windows)

1. Open **Control Panel → Region → Format** and switch to a non-US locale (e.g., **English (United Kingdom)**).
2. Restart CatGuard.
3. Trigger a detection event (or use the test page Record function to save a screenshot).
4. Open the saved screenshot. Verify the timestamp in the top-right reads in day-first format (e.g., `04/03/2026  14:35:10`).
5. Restore your preferred locale.

---

## Running the Full Test Suite

```bash
pytest tests/unit/ -v
pytest tests/integration/ -v -m integration
```

All tests must pass with exit code 0 before the implementation is considered complete.
