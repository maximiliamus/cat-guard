# Data Model: Immediate Cat Session Frame Saving

**Feature**: 014-improve-cat-session-tracking  
**Date**: 2026-03-23

---

## Entities

### CatSession (runtime state in `EffectivenessTracker`)

Represents one continuous cat visit that has already produced its first saved frame.

| Field | Type | Description |
|---|---|---|
| `session_start` | `datetime` | Timestamp of the first alert in the session. Used as the session identifier and filename prefix. |
| `cycle_count` | `int` | Number of alert cycles that have started in the current session. Starts at `1` on first detection and increments on each later alerting detection. |
| `frame_index` | `int` | Number of saved frames already emitted for the session. Starts at `1` for the neutral start frame and increments for each later saved evaluation frame. |
| `active_sound_label` | `str \| None` | Sound label associated with the current alert cycle. Used in the top bar of the next saved frame. |

**Validation rules**:

- `session_start is None` if and only if no session is active.
- `cycle_count >= 1` whenever a session is active.
- `frame_index >= 1` whenever a session is active.
- `frame_index` increments exactly once per saved session file.

---

### VerificationPending (runtime state in `DetectionLoop`)

Represents whether a post-alert verification callback is still due. This replaces the old long-lived image buffer in the loop.

| Field | Type | Description |
|---|---|---|
| `verification_pending` | `bool` | `True` after an alerting detection fires and before the corresponding verification callback runs or the loop is paused/reset. |

**Validation rules**:

- The pending flag is cleared before invoking the verification callback.
- Pausing the detection loop clears the pending flag.
- No image payload is retained in this state across the cooldown interval.

---

### SessionFrame (on-disk artifact)

One JPEG saved to the tracking directory as part of a cat session timeline.

| Attribute | Description |
|---|---|
| `path` | `<tracking_directory>/<yyyy-mm-dd>/<YYYYMMDD-HHmmss>-<NNN>.jpg` |
| `prefix` | `session_start.strftime("%Y%m%d-%H%M%S")` |
| `suffix NNN` | 1-based saved-frame index within the session |
| `kind` | `detected`, `remained`, or `disappeared` |
| `duration_text` | Absent for `detected`; human-readable duration for `remained` / `disappeared` |
| `top bar` | Existing sound label and save timestamp |
| `bottom strip` | Neutral dark gray, red, or green message strip depending on `kind` |

**Example session timeline**:

```text
20260323-101500-001.jpg   # Cat detected
20260323-101500-002.jpg   # Cat remained after alert: 30s
20260323-101500-003.jpg   # Cat disappeared after alert: 1m 0s
```

---

## State Transitions

```text
[idle]
  |
  | on_detection(first alert)
  | -> create CatSession
  | -> cycle_count = 1
  | -> frame_index = 1
  | -> save SessionFrame 001 (kind=detected)
  v
[session active, verification pending]
  |
  | on_verification(has_cat=True, live frame)
  | -> frame_index += 1
  | -> save SessionFrame N (kind=remained)
  v
[session active, between cycles]
  |
  | on_detection(next alert)
  | -> cycle_count += 1
  | -> update active_sound_label
  v
[session active, verification pending]
  |
  | on_verification(has_cat=False, live frame)
  | -> frame_index += 1
  | -> save SessionFrame N (kind=disappeared)
  | -> reset session metadata
  v
[idle]
```

Interrupt path:

```text
[any active session]
  |
  | abandon() / pause / camera error / stop
  | -> clear CatSession metadata
  | -> clear VerificationPending flag
  | -> save no synthetic final frame
  v
[idle]
```

---

## Affected Source Modules

| Module | Planned change |
|---|---|
| `src/catguard/detection.py` | Replace long-lived pending frame buffer with a verification-pending flag and pass the live verification frame into the callback |
| `src/catguard/annotation.py` | Add neutral `detected` strip, human-readable duration formatter, and metadata-only session tracker flow |
| `src/catguard/screenshots.py` | Keep `build_session_filepath()` but change suffix semantics to sequential session frame index |

---

## No Config Schema Changes

No new `Settings` fields. No migration is required for the JSON settings file. The tracking root and date-folder layout remain unchanged.
