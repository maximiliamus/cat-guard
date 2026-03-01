# Research: Audio Recording & Playback Controls

**Feature**: `004-add-record-sound`
**Date**: 2026-03-01

---

## 1. Microphone Capture Library

**Decision**: `sounddevice` + `soundfile`

**Rationale**:
- `sounddevice.rec(frames=10 * samplerate, ...)` accepts an explicit frame count, so
  the 10-second cap is handled by the API itself — no polling or separate timer needed.
- `sounddevice.wait()` blocks the background thread until capture completes; early stop
  via `sounddevice.stop()` from the UI thread causes `wait()` to return cleanly, unifying
  the "auto-stop at cap" and "user clicked Stop" paths into one return point.
- Returns a NumPy array directly; NumPy is already a transitive dependency (via
  `opencv-python` / `ultralytics`), so no new heavy dependency is introduced.
- Binary wheels on PyPI for CPython 3.11+ on Windows x64, macOS arm64/x64, and
  Linux x64. `pip install sounddevice` is reliable without a compiler.
- `soundfile` writes NumPy arrays to WAV via bundled `libsndfile`:
  `soundfile.write(path, data, samplerate)` — one call.
- Actively maintained (last release 2024).

**Alternatives considered**:
- **`pyaudio` + `wave`**: Windows wheels absent from PyPI for Python 3.12+; requires
  `pipwin`, conda, or manual compilation. Rejected: install unreliability on Windows.
- **`soundcard`**: Uses native OS audio APIs (no PortAudio). Smaller user base,
  less documentation, no blocking `rec(duration)` equivalent — manual ring-buffer loop
  required. Rejected: complexity outweighs the PortAudio saving.

---

## 2. 10-Second Recording Cap

**Decision**: `sounddevice.rec(frames=10 * SAMPLERATE)` + `sounddevice.wait()` in a
daemon background thread, followed by `root.after(0, callback)` to hand the result
to the tkinter main thread.

**Rationale**:
- `sounddevice.rec()` records exactly `frames` samples then returns; both the
  user-click-Stop path (`sounddevice.stop()`) and the auto-cap path terminate in the
  same `wait()` return, simplifying control flow.
- `root.after(0, callback)` matches the existing pattern in `settings_window.py`
  (`_load_cameras_bg` → `root.after(0, _update)`) for safe main-thread dispatch.
- Zero additional synchronisation: no `threading.Timer`, no polling, no timeout loop.

**Alternatives considered**:
- **`threading.Timer`**: Correctly fires after 10 s but requires managing the timer
  object lifecycle (cancellation on early stop) and a separate data-passing mechanism.
  More moving parts. Rejected.
- **Polling loop**: Burns CPU, has ±1-chunk jitter on the cutoff, requires manual WAV
  assembly. Rejected.
- **`root.after(10000, stop_fn)`**: Fires on main thread — correct for UI, but
  `sounddevice.stop()` would need to be called from the main thread while the UI is
  live; the tkinter event loop must be unblocked for the timer to fire. Fragile during
  detection bursts. Rejected.

---

## 3. Silence / Zero-Length Detection

**Decision**: Zero-length guard first; then NumPy RMS on `int16` samples with a fixed
threshold of 100 (out of 32 767).

```python
if data is None or len(data) == 0:
    return True  # zero-length → silent
rms = np.sqrt(np.mean(data.astype(np.float32) ** 2))
return rms < 100
```

**Rationale**:
- NumPy is already present; no new dependency.
- RMS correctly weights sustained low-level noise. Genuine microphone silence:
  RMS ≈ 5–30 (thermal noise + quantisation). Any intentional sound: RMS ≥ 200.
  Threshold of 100 gives a safe gap.
- `float32` cast before squaring prevents `int16` overflow.

**Alternatives considered**:
- **Peak amplitude**: A single transient (click, buffer artifact) can pass a silent
  recording. Rejected: too easily fooled.
- **Zero-crossing rate**: Measures tonal content, not energy. Inappropriate for a
  simple silence gate. Rejected.
- **`audioop.rms()`**: Deprecated in Python 3.11, removed in Python 3.13. Rejected.

---

## 4. Open Folder in OS File Explorer

**Decision**: Platform-branched dispatch — `os.startfile` on Windows, `subprocess`
`["open", ...]` on macOS, `subprocess` `["xdg-open", ...]` on Linux.

```python
import os, platform, subprocess

def open_folder(path: str) -> None:
    system = platform.system()
    if system == "Windows":
        os.startfile(path)
    elif system == "Darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)
```

**Rationale**:
- `os.startfile` is the canonical Windows Shell API; handles Unicode paths correctly.
  `pywin32` is already a declared dependency for Windows.
- `open` and `xdg-open` are the standard OS launchers; they delegate to whatever file
  manager the user has configured. `check=False` prevents an exception if `xdg-open`
  is absent on a minimal Linux system.
- Zero new dependencies.

**Alternatives considered**:
- **`subprocess.run(["explorer", path])`**: Mishandles paths with trailing slashes and
  certain Unicode on Windows. Rejected.
- **`webbrowser.open(uri)`**: May open in a web browser if `BROWSER` env var is set or
  no desktop environment is detected. Rejected: unreliable.

---

## 5. Filename Sanitisation

**Decision**: `re.sub` whitelist + `Path.name` for path-traversal prevention.

```python
import re
from pathlib import Path

def sanitise_filename(raw: str) -> str:
    name = re.sub(r"[^\w\s\-.]", "", raw, flags=re.UNICODE)
    name = re.sub(r"\s+", "_", name).strip("_.")
    name = Path(name).name          # strip any directory component
    return (name or "recording") + ".wav"
```

**Rationale**:
- No new dependency; `re` and `pathlib` are stdlib.
- Whitelist is safer than a blacklist: illegal characters differ per OS
  (Windows has 10 additional reserved chars; Linux only `/` and NUL).
- `Path.name` strips any `../`, absolute path prefix, or embedded separator typed
  by the user — prevents all path-traversal attacks with one call.
- `.strip("_.")` prevents leading-dot hidden files on Linux/macOS and Windows
  reserved names (`.` and `..`).
- `or "recording"` handles the edge case where the entire input is stripped.

**Alternatives considered**:
- **`pathvalidate` library**: Correct and thorough (handles `CON`, `NUL`, etc.),
  but introduces a new dependency for a single function. Overkill here. Rejected.

---

## 6. Recording-Suppression Signal (Thread Safety)

**Decision**: `threading.Event` stored as an attribute on the tkinter `root` object
(e.g. `root._recording_event = threading.Event()`).

**Rationale**:
- `threading.Event` is purpose-built for this pattern: a boolean flag shared between
  threads with internally lock-protected `set()`, `clear()`, and `is_set()` methods.
  Safe to call from any thread without additional synchronisation.
- Storing it on `root` follows the existing convention
  (`_main_window_visible`, `_settings_window_open`, `_tray_icon`) — all cross-thread
  shared state is co-located on the root object and discoverable.
- In `on_cat_detected`, adding `if root._recording_event.is_set(): return` requires
  one line with no new imports.
- When the Settings window closes mid-recording (`_on_close`), `clear()` is called
  from the main thread — thread-safe by `threading.Event`'s own implementation.
- When the 10-second cap fires (background thread), `set()` is also called from the
  background thread before `root.after(0, ...)` — safe because `Event` is explicitly
  designed for cross-thread writes.

**Alternatives considered**:
- **Plain `bool` attribute on `root`** (matching `_main_window_visible`):
  `_main_window_visible` is only written from the main thread; the recording flag
  is written from a background thread (cap expiry). Relying on the CPython GIL for
  atomicity of attribute writes from a background thread is an implementation detail,
  not a language guarantee. Rejected: prefer the explicitly thread-safe primitive for
  a write-from-background-thread case.
- **`threading.Lock`-protected `bool`**: Correct but verbose — `acquire()`/`release()`
  wrapping every read and write. `threading.Event` is a lock-protected bool with a
  cleaner API. No advantage. Rejected.
