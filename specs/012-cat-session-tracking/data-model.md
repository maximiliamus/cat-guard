# Data Model: Cat Session Tracking

**Feature**: 012-cat-session-tracking
**Date**: 2026-03-22

---

## Entities

### CatSession (runtime state, not persisted)

Held in memory inside `EffectivenessTracker`. Represents one continuous cat visit from the first alert through to the cat leaving (green outcome) or the app shutting down.

| Field | Type | Description |
|---|---|---|
| `session_start` | `datetime` | Timestamp when the first alert of this session fired. Used as the session identifier in filenames. |
| `cycle_count` | `int` | Number of evaluation cycles completed (increments with each `on_detection` call for this session). The first detection sets it to 1. |

**State transitions**:

```
[no session]
    │
    on_detection() called (first alert or post-green re-entry)
    │   → session_start = now, cycle_count = 1, pending_frame stored
    ▼
[session active, cycle pending]
    │
    on_detection() called while pending → silently ignored (FR-005a)
    │
    abandon() called (any pause: manual, camera error, time-window)
    │   → _pending_frame = None, _session_start = None, _cycle_count = 0
    │   → no frame written
    ▼  ──────────────────────────────────────────────────────────► [no session]
    │
    on_verification(has_cat=True)
    │   → save red-labeled frame (<YYYYMMDD-HHmmss>-<N>.jpg)
    │   → pending cleared, session remains open
    ▼
[session active, between cycles]
    │
    abandon() called (any pause)
    │   → _session_start = None, _cycle_count = 0
    │   → no frame written
    ▼  ──────────────────────────────────────────────────────────► [no session]
    │
    on_detection() called (next alert from loop)
    │   → cycle_count += 1, pending_frame stored
    ▼
[session active, cycle pending]  ← loop back
    │
    on_verification(has_cat=False)
    │   → save green-labeled frame (<YYYYMMDD-HHmmss>-<N>.jpg)
    │   → pending cleared, session closed (session_start = None, cycle_count = 0)
    ▼
[no session]
```

---

### EvaluationFrame (on-disk artifact)

A JPEG file written to the tracking folder. Each file is one evaluated snapshot from a session cycle.

| Attribute | Value |
|---|---|
| Location | `<tracking_directory>/<yyyy-mm-dd>/<YYYYMMDD-HHmmss>-<NNN>.jpg` |
| Naming | `session_start` timestamp + zero-padded 3-digit cycle number |
| Content | Annotated BGR frame: bounding boxes, top info bar (sound label + save timestamp), bottom outcome strip (colored, timed message) |
| Outcome strip color | Red for "Cat remained after alert: Ns" / Green for "Cat disappeared after alert: Ns" |
| Elapsed time `N` | `cycle_count × settings.cooldown_seconds` (integer seconds) |

**Example filenames for a 3-cycle session (cooldown = 30 s)**:
```
20260322-143000-001.jpg   ← red,   "Cat remained after alert: 30s"
20260322-143000-002.jpg   ← red,   "Cat remained after alert: 60s"
20260322-143000-003.jpg   ← green, "Cat disappeared after alert: 90s"
```

---

## Validation Rules

- `cycle_count` is always ≥ 1 when a session is active.
- `session_start` is `None` if and only if no session is active.
- A new session cannot start while `_pending_frame is not None` (mid-cycle guard).
- A new cycle cannot begin while `_pending_frame is not None` (same guard — no distinction needed between "new session" and "new cycle" from the guard's perspective; the distinction is whether `session_start` is None).
- Elapsed time label is always a whole-second integer: `int(cycle_count * cooldown_seconds)`.

---

## Affected Source Modules

| Module | Change |
|---|---|
| `src/catguard/annotation.py` | `EffectivenessTracker`: add `_session_start`, `_cycle_count`; add `abandon()` method; update `on_detection` + `on_verification` |
| `src/catguard/annotation.py` | `annotate_frame`: add `outcome_message: Optional[str] = None` parameter |
| `src/catguard/annotation.py` | `_save_annotated_async`: add `filepath: Optional[Path] = None` parameter |
| `src/catguard/screenshots.py` | `save_screenshot`: add `filepath: Optional[Path] = None` parameter |
| `src/catguard/screenshots.py` | Add `build_session_filepath(root, session_ts, cycle_num) → Path` |
| `src/catguard/main.py` | `on_camera_error` + `on_tracking_state_changed(False)` wired to `tracker.abandon()` |

---

## No Schema / Config Changes

No new `Settings` fields. No changes to the on-disk config file format. No changes to `DetectionLoop` beyond the defensive `_pending_frame = None` clear in `pause()`. `main.py` receives two wiring additions (`on_camera_error` and `on_tracking_state_changed` call `tracker.abandon()`).
