# Research: Miscellaneous UI and Behavior Improvements

**Feature**: 007-misc-improvements  
**Date**: March 4, 2026

---

## R-001: Sleep/Wake Detection — Cross-Platform Strategy

**Question**: How to reliably detect system sleep/wake events on Windows, macOS, and Linux without introducing new dependencies?

**Decision**: Time-jump polling in a daemon thread (universal fallback) combined with a Windows-native WM_POWERBROADCAST listener using `pywin32` (already in deps).

**Rationale**:
- `pywin32` is already declared in `requirements.txt` for Windows builds. The `WM_POWERBROADCAST`/`PBT_APMRESUMEAUTOMATIC` message is the correct Windows mechanism. However, receiving it requires a Win32 message loop attached to a hidden window, which is non-trivial.
- Simplest correct cross-platform approach: a daemon thread sleeps for N seconds, then checks if the actual wall-clock delta was significantly larger than N. If `actual_elapsed > 2 × expected_interval`, a sleep/wake cycle occurred. Works on all platforms with zero new dependencies and is reliable in practice for intervals > 30 seconds.
- Time-jump polling threshold: sleep 10 s, flag wake if elapsed > 30 s. This tolerates OS scheduling jitter and gives sub-30-second wake detection latency.

**Alternatives considered**:
- `win32gui.CreateWindowEx` + message pump for `WM_POWERBROADCAST`: Correct on Windows but requires a dedicated message-loop thread and is hard to test; rejected for simplicity.
- `dbus-python` (Linux `PrepareForSleep`): Only for Linux, adds a dependency; rejected.
- Third-party `wakepy` library: Not in current deps, extra install overhead; rejected.

**Implementation target**: New module `src/catguard/sleep_watcher.py` — `SleepWatcher(on_wake: Callable)` with `start()` / `stop()`.

---

## R-002: Locale-Aware Date/Time Formatting in Python

**Question**: How to format `datetime.now()` according to the OS user locale without adding new dependencies?

**Decision**: Call `locale.setlocale(locale.LC_TIME, '')` once at application startup (in `main()`) to activate the system locale, then use `datetime.strftime('%x  %X')` — `%x` is locale's short date, `%X` is locale's time — throughout the annotation code.

**Rationale**:
- `locale` is a Python standard library module; no new dependency.
- `locale.setlocale(locale.LC_TIME, '')` with an empty string selects "whatever the OS prefers." This is the documented way to activate the system default locale in Python.
- `%x` and `%X` are POSIX/C locale strftime codes meaning "locale's appropriate date/time representation." Python's `datetime.strftime` honours `LC_TIME` for these format codes on Windows, macOS, and Linux.
- `locale.setlocale` is global and must be called before any formatting happens. It is NOT thread-safe to call concurrently, but is safe when called once before threads start.
- On Windows, Python internally calls `setlocale` via CRT and maps the Windows locale to POSIX codes; `%x`/`%X` propagate correctly.

**Alternatives considered**:
- `babel.dates.format_datetime()`: Full ICU-quality locale support but requires `babel` (not in current deps); rejected for simplicity.
- Hardcoded `"%Y-%m-%d  %H:%M:%S"`: Current implementation; does not respect locale; replaced.
- `win32api.GetLocaleInfoEx()` + manual format parsing: Windows-only and complex; rejected.

**Implementation target**: `main()` in `src/catguard/main.py` — add `locale.setlocale(locale.LC_TIME, '')` near top. `_draw_top_bar()` in `src/catguard/annotation.py` — replace hardcoded format string with `'%x  %X'`.

---

## R-003: Off-Screen Annotation Label Placement

**Question**: How to ensure a bounding-box label stays within frame boundaries when the box is near the top/sides of the frame?

**Decision**: Refactor `_draw_labelled_box()` to compute label pixel dimensions first, then test four candidate anchor positions in order (above-box → below-box → left-of-box → right-of-box → center-of-box) and render at the first one that fits entirely within the frame's pixel bounds.

**Rationale**:
- "Screen" in the user request means the OpenCV frame (NumPy array), not the monitor. The frame's `(h, w) = frame.shape[:2]` defines the bounds.
- Current code uses `label_y = max(y1 - LABEL_PAD, th + LABEL_PAD)` which partially prevents going off the top, but does NOT correctly fall through to bottom/left/right/center.
- Each candidate position is defined by its background rectangle corners `(bx1, by1, bx2, by2)`. A position is "valid" if `bx1 >= 0 and by1 >= 0 and bx2 <= w and by2 <= h`.
- Order matches the spec exactly: top → bottom → left → right → center.

**Candidate positions**:

| Position | Label anchor `(label_x, label_y)` | Background `bg_y1` |
|---|---|---|
| Above box (default) | `(x1, y1 - LABEL_PAD)` | `y1 - th - 2*LABEL_PAD` |
| Below box | `(x1, y2 + th + LABEL_PAD)` | `y2` |
| Left of box | `(x1 - tw - 2*LABEL_PAD, (y1+y2)//2)` | mid-height |
| Right of box | `(x2 + LABEL_PAD, (y1+y2)//2)` | mid-height |
| Center of box | `((x1+x2)//2 - tw//2, (y1+y2)//2)` | center |

**Alternatives considered**:
- Clamp label position to frame interior: may overlap the box or other annotations; rejected.
- Always draw inside the box: occludes the subject; rejected.

**Implementation target**: `_draw_labelled_box()` in `src/catguard/annotation.py`.

---

## R-004: Sound Rename — Concurrent Playback Handling

**Question**: Is `pygame.mixer.stop()` sufficient to stop playback before renaming, and can the file be safely renamed on Windows while it is open by pygame?

**Decision**: Call `pygame.mixer.stop()` to stop all playback before opening the rename dialog. On Windows, pygame unloads the audio file from the mixer buffer after `stop()` (it does not hold an open file descriptor after the clip finishes loading to memory), so the `Path.rename()` will succeed.

**Rationale**:
- `pygame.mixer` (pygame-ce) loads WAV/MP3 into memory before playback. After `stop()` the file is not held open.
- MP3 files loaded via `pygame.mixer.music` do stream from disk; `pygame.mixer.music.stop()` closes the stream. Since `play_alert` uses `_play_async` which calls `pygame.mixer.Sound` for WAV and optionally `music` for MP3, stopping all channels and music covers both cases.
- `Path.rename()` on the same filesystem is atomic on Windows (unlike cross-device moves). No temporary copy is needed.
- If pygame raises during stop (e.g., not initialised), the rename still proceeds — the error is logged and swallowed.

**Implementation target**: `_rename_path()` added to `src/catguard/ui/settings_window.py`.

---

## R-005: Time Window Clock Monitoring

**Question**: How often should the time window monitor poll, and what is the right interaction with the existing `pause()` / `resume()` / `is_tracking()` API on `DetectionLoop`?

**Decision**: Poll every 30 seconds using a daemon thread. Maintain an internal flag `_user_override: bool` that is set when the user explicitly resumes while outside the window (FR-004b), cleared at the next window-end boundary.

**State transitions**:

```
State machine:
  outside window + not tracking + no override → WINDOW_PAUSE (auto-pause)
  outside window + user presses Resume → set _user_override; resume camera
  enters window → clear _user_override; camera already on (or resume)
  exits window → if _user_override: pause; clear _user_override
  no window configured → do nothing (passthrough)
```

**Manual pause co-existence** (FR-004):  
The monitor calls `detection_loop.pause()` / `detection_loop.resume()` but must not override a *manual* pause. Solution: track whether the monitor itself caused the pause (`_monitor_paused: bool`). Only call `resume()` from the monitor if the monitor previously called `pause()`. A manual pause clears this flag (the monitor observes `is_tracking()` returns False but `_monitor_paused` is False — so it does not try to resume).

**Tray update**: the monitor calls a provided `on_state_changed(is_tracking)` callback so `main.py` can update the tray icon and menu.

**Implementation target**: New module `src/catguard/time_window.py` — `TimeWindowMonitor` class. `main.py` instantiates and wires it.

---

## R-006: New Config Fields for Tracking Time Window

**Question**: Should we reuse the existing `screenshot_window_*` settings or add separate tracking time window fields?

**Decision**: Add three new `Settings` fields: `tracking_window_enabled`, `tracking_window_start`, `tracking_window_end`. Do not repurpose or alias the screenshot window fields.

**Rationale**:
- The screenshot time window and the tracking time window serve different purposes. A user may want screenshots only at night but have the camera active all day, or vice versa. Coupling them would lose this flexibility.
- Field naming mirrors the existing `screenshot_window_*` pattern for consistency.
- Defaults: `tracking_window_enabled=False`, `tracking_window_start="08:00"`, `tracking_window_end="18:00"` (sensible workday defaults, disabled by default).

**Implementation target**: `src/catguard/config.py`, `Settings` class.
