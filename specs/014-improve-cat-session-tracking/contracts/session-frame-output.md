# Contract: Session Frame Output

**Feature**: 014-improve-cat-session-tracking  
**Date**: 2026-03-23

## 1. Verification Callback Contract

`DetectionLoop.set_verification_callback(cb)` registers a callback with this internal signature:

```python
cb(frame_bgr, has_cat, boxes) -> None
```

Rules:

- `frame_bgr` is the current live BGR frame captured at verification time.
- `frame_bgr` must be safe for the callback to use after the loop iteration continues, so the loop passes a deep copy.
- `has_cat` is `True` when at least one cat box is present in `boxes`.
- `boxes` contains the verification frame detections for that same callback.
- The loop clears its verification-pending state before invoking the callback.

## 2. Session File Naming Contract

Each saved session frame uses this path pattern:

```text
<tracking_directory>/<YYYY-MM-DD>/<YYYYMMDD-HHmmss>-<NNN>.jpg
```

Rules:

- `<YYYYMMDD-HHmmss>` is derived from the session start timestamp.
- `<NNN>` is a 1-based saved-frame index within the session.
- `001` is always the neutral session-start frame.
- Later frames increment monotonically in save order.

## 3. Bottom Strip Contract

| Kind | Background | Text |
|---|---|---|
| `detected` | dark gray | `Cat detected` |
| `remained` | red | `Cat remained after alert: <duration>` |
| `disappeared` | green | `Cat disappeared after alert: <duration>` |

Text color is always white.

## 4. Duration Formatting Contract

Duration formatting uses these rules:

- `< 60` seconds -> `Xs`
- `>= 60` and `< 3600` -> `Xm Ys`
- `>= 3600` -> `Xh Ym Zs`

Examples:

- `30s`
- `2m 15s`
- `1h 2m 45s`

## 5. Save Invariants

- The first frame of a session is saved immediately on the alerting detection.
- Each verification result produces exactly one saved frame.
- Saved frames from one session share the same timestamp prefix.
- Pausing or abandoning a session never creates a synthetic closing frame.
