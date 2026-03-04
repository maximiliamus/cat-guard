# Data Model: Miscellaneous UI and Behavior Improvements

**Feature**: 007-misc-improvements  
**Date**: March 4, 2026

---

## Existing Entities (Modified)

### `Settings` (extended)

**Location**: `src/catguard/config.py` — `class Settings(BaseModel)`

Three new fields added to support the tracking time window (FR-001 through FR-005b):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tracking_window_enabled` | `bool` | `False` | When `True`, the camera is active only during the window defined by `tracking_window_start` and `tracking_window_end`. When `False`, existing always-on behavior is unchanged. |
| `tracking_window_start` | `str` | `"08:00"` | Start of the daily active monitoring period in `HH:MM` (local 24-hour time). |
| `tracking_window_end` | `str` | `"18:00"` | End of the daily active monitoring period in `HH:MM` (local 24-hour time). May precede `tracking_window_start` to span midnight (e.g., `"22:00"` → `"06:00"`). |

**Validation rules**:
- `tracking_window_start` and `tracking_window_end` must match `HH:MM` format (regex `^\d{2}:\d{2}$`).
- If `tracking_window_start == tracking_window_end`, the window is treated as zero-length and effectively disabled at runtime.

**Backward compatibility**: All new fields have safe defaults. Existing settings files without these keys silently receive the defaults on next load (pydantic `model_config = ConfigDict(validate_assignment=True)`).

### `SoundLibraryEntry` (logical — no code type)

No new Python type is introduced. The sound library remains a `List[str]` of absolute file paths in `settings.sound_library_paths`. The Rename operation preserves this contract: the old path string is replaced in-list with the new path string after the file is renamed on disk.

---

## New Entities

### `SleepWatcher`

**Location**: `src/catguard/sleep_watcher.py`

| Attribute | Type | Description |
|-----------|------|-------------|
| `_on_wake` | `Callable[[], None]` | Callback invoked on wake detection; called from the watcher daemon thread |
| `_stop_event` | `threading.Event` | Signals the daemon thread to exit cleanly |
| `_thread` | `Optional[Thread]` | Daemon thread reference |

**Methods**:

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(on_wake: Callable[[], None])` | Store callback; do not start yet |
| `start` | `() → None` | Spawn daemon thread; idempotent if already running |
| `stop` | `() → None` | Set stop event; join thread with 3 s timeout |

**Internal logic** (`_run` daemon):
```
last_check = time.monotonic()
loop:
  stop_event.wait(timeout=10)       # sleep 10 s (or until stop)
  now = time.monotonic()
  elapsed = now - last_check
  if elapsed > 30:                  # >30 s wall gap → wake from sleep
    log.info("Wake from sleep detected (elapsed=%.1f s)", elapsed)
    on_wake()
  last_check = now
```

### `TimeWindowMonitor`

**Location**: `src/catguard/time_window.py`

| Attribute | Type | Description |
|-----------|------|-------------|
| `_detection_loop` | `DetectionLoop` | The loop to pause/resume |
| `_settings` | `Settings` | Read-only reference; `tracking_window_*` fields read on each poll |
| `_on_state_changed` | `Callable[[bool], None]` | Called with `is_tracking` after any state change; used to update tray icon/menu |
| `_stop_event` | `threading.Event` | Signals daemon thread to exit |
| `_monitor_paused` | `bool` | `True` when *this monitor* caused the current pause (not a manual pause) |
| `_user_override` | `bool` | `True` when user pressed Resume while outside the window (FR-004b) |

**Methods**:

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(detection_loop, settings, on_state_changed)` | Store references; do not start |
| `start` | `() → None` | Spawn daemon thread; evaluate window immediately on start |
| `stop` | `() → None` | Set stop event; join with 3 s timeout |
| `notify_user_resume` | `() → None` | Called by tray Resume handler; sets `_user_override = True` if currently outside window |

**State machine** (`_check` method):

```
window_configured = settings.tracking_window_enabled

if not window_configured:
    return  # passthrough — do not touch detection_loop

in_window = _is_in_window(datetime.now().time(), start, end)
is_tracking = detection_loop.is_tracking()

CASE 1: in_window and not is_tracking and _monitor_paused:
    # Window just opened → resume (only if we caused the pause)
    _monitor_paused = False
    _user_override = False
    detection_loop.resume()
    on_state_changed(True)

CASE 2: not in_window and is_tracking and not _user_override:
    # Window just closed and no user override → auto-pause
    _monitor_paused = True
    detection_loop.pause()
    on_state_changed(False)

CASE 3: not in_window and is_tracking and _user_override:
    # User override is active — do nothing (let user keep camera on)

CASE 4: not in_window and not is_tracking:
    # Already paused — but was it by us or manually?
    # If _monitor_paused is False, it was manual — do nothing.

CASE 5: Window boundary re-entered after user override:
    # in_window becomes True again → clear override; resume if monitor-paused
    _user_override = False   (housekeeping)
```

**`_is_in_window` cross-midnight logic**:

```python
def _is_in_window(now_time, start_str, end_str):
    start = time.fromisoformat(start_str)  # "HH:MM"
    end   = time.fromisoformat(end_str)
    if start <= end:
        return start <= now_time < end      # normal window
    else:
        return now_time >= start or now_time < end   # spans midnight
```

---

## State Interaction Diagram

```
               ┌─────────────────────────────────────────────────┐
               │                 App Running                      │
               │                                                  │
  Manual       │  TimeWindowMonitor.pause()  TimeWindowMonitor    │
  tray Pause ──┤─────────────────────────▶  _monitor_paused=True  │
               │                                                  │
  Manual Tray  │  TimeWindowMonitor.notify_user_resume()          │
  Resume  ─────┤────────────────────────▶  _user_override=True    │
  (outside     │  detection_loop.resume()                         │
   window)     │                                                  │
               │  On window re-entry:  clear _user_override       │
               │  On window exit:      pause unless _user_override│
               └─────────────────────────────────────────────────┘

               ┌─────────────────────────────────────────────────┐
               │                SleepWatcher                      │
               │                                                  │
  System Wake ─┤─▶ on_wake() ──▶ (main.py callback)              │
               │      if detection_loop active before sleep:      │
               │        evaluate time window                      │
               │        if in_window (or no window):              │
               │            detection_loop.resume()               │
               │            update_tray_icon/menu                 │
               └─────────────────────────────────────────────────┘
```
