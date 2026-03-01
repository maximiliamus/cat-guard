# Data Model: Screenshot on Cat Detection

**Phase**: 1 — Design  
**Date**: 2026-03-01  
**Source**: [spec.md](spec.md), [plan.md](plan.md)

---

## Changed Entities

### 1. Settings *(extended)*

Extends the base `Settings` model in `src/catguard/config.py`. Four new optional fields are added; all have defaults so existing `settings.json` files continue to work without migration (non-breaking change).

| Field | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `camera_index` | `int` | `0` | ≥ 0 | *(existing)* Index of the webcam to use |
| `confidence_threshold` | `float` | `0.25` | [0.0, 1.0] | *(existing)* YOLO detection confidence |
| `cooldown_seconds` | `float` | `15.0` | > 0 | *(existing)* Minimum seconds between consecutive alerts |
| `sound_library_paths` | `list[str]` | `[]` | Existing files only | *(existing)* Absolute paths to alert sound files |
| `autostart` | `bool` | `False` | — | *(existing)* Start on user login |
| `screenshots_root_folder` | `str` | `""` | — | **NEW** Absolute path to the screenshots root folder. Empty string means "use default" (`Pictures/CatGuard`). |
| `screenshot_window_enabled` | `bool` | `False` | — | **NEW** When `True`, screenshots are only saved within the configured time window. |
| `screenshot_window_start` | `str` | `"22:00"` | `HH:MM` format, 00:00–23:59 | **NEW** Start of the daily screenshot window (wall-clock, local time). |
| `screenshot_window_end` | `str` | `"06:00"` | `HH:MM` format, 00:00–23:59 | **NEW** End of the daily screenshot window. May be earlier than start (midnight-spanning). |

**Validation rules (new fields)**:
- `screenshots_root_folder`: no filesystem validation on load — the path is accepted as-is; non-existent folders are created on first save.
- `screenshot_window_start` / `screenshot_window_end`: must match `HH:MM` pattern; invalid values reset to defaults with a log warning.
- When `screenshot_window_start == screenshot_window_end` and `screenshot_window_enabled == True`, the window is treated as disabled (screenshots taken at any hour) and a warning is logged.

---

### 2. DetectionEvent *(extended)*

In-memory only. One new optional field carries the raw camera frame to the alert callback so it can be saved without a second capture.

| Field | Type | Description |
|---|---|---|
| `timestamp` | `datetime` | *(existing)* UTC timestamp of the detection |
| `confidence` | `float` | *(existing)* YOLO confidence score (0.0–1.0) |
| `action` | `DetectionAction` | *(existing)* `SOUND_PLAYED` or `COOLDOWN_SUPPRESSED` |
| `sound_file` | `str \| None` | *(existing)* Filename of the sound played |
| `frame_bgr` | `np.ndarray \| None` | **NEW** Raw BGR camera frame at the moment of detection. `None` for `COOLDOWN_SUPPRESSED` events (no frame needed). Never written to disk; lives only for the duration of the callback. |

---

## New Entities

### 3. Screenshot *(filesystem artefact)*

Not represented as a Python class — it is a plain JPEG file on disk. Included here to document naming and layout conventions.

| Property | Value |
|---|---|
| **Format** | JPEG (`cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 1])`) |
| **Quality** | 1 (maximum compression / minimum quality) — fixed, not user-configurable |
| **Location** | `<root>/<yyyy-mm-dd>/<HH-MM-SS[-N]>.jpg` |
| **Root** | Value of `settings.screenshots_root_folder` if non-empty, otherwise `platformdirs.user_pictures_dir() / "CatGuard"` |
| **Date folder** | Local wall-clock date at save time, format `yyyy-mm-dd` |
| **File name** | Local wall-clock time at save time, format `HH-MM-SS`. If a file with the same name already exists (same-second collision), a counter suffix is appended: `HH-MM-SS-1.jpg`, `HH-MM-SS-2.jpg`, … |
| **Folder creation** | All missing intermediate folders are created on-demand via `Path.mkdir(parents=True, exist_ok=True)` at save time, never at startup |
| **Retention** | Indefinite — no automatic cleanup; user manages the folder |

---

### 4. ScreenshotTimeWindow *(logical concept — represented as Settings fields)*

Not a standalone class; modelled as three fields on `Settings`. Documented here for clarity.

| Attribute | Source field | Description |
|---|---|---|
| `enabled` | `screenshot_window_enabled` | Whether the time window restriction is active |
| `start` | `screenshot_window_start` | Window open time (`HH:MM`, local) |
| `end` | `screenshot_window_end` | Window close time (`HH:MM`, local). Can precede `start` to span midnight. |

**Window logic** (`screenshots.is_within_time_window`):

- If `enabled == False` → always within window.
- Parse `start` and `end` as `datetime.time` objects.
- If `start == end` → treat as always within window (degenerate case, log warning).
- If `start < end` (same-day window, e.g., 08:00–18:00):  
  → within window if `start ≤ now < end`
- If `start > end` (midnight-spanning, e.g., 22:00–06:00):  
  → within window if `now ≥ start OR now < end`

---

## State: Screenshot Save Decision

```
on_cat_detected(event) [DetectionLoop thread]
       │
       ▼
  event.action == SOUND_PLAYED?
  ├─ No  → skip (cooldown-suppressed, FR-011)
  └─ Yes
       │
       ▼
  is_main_window_open()?
  ├─ Yes → skip (FR-012)
  └─ No
       │
       ▼
  is_within_time_window(settings)?
  ├─ No  → skip (FR-015)
  └─ Yes
       │
       ▼
  resolve_root(settings) + build_filepath(root, now)
       │
       ▼
  mkdir(parents=True, exist_ok=True)  (FR-005)
       │
       ▼
  cv2.imencode → write bytes to file
  ├─ Success → logger.info
  └─ Exception → logger.error + tray_notify (FR-010)
```
