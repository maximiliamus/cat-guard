# Contract: Configuration Schema

**Feature**: `005-alert-effectiveness`
**Date**: 2026-03-02

---

## settings.json — No Changes

This feature introduces **no new fields** to `settings.json` and **removes no existing
fields**. The full annotation pipeline (bounding boxes, sound label, outcome overlay)
is driven exclusively by:

- `cooldown_seconds` — existing field; reused as the verification wait period (FR-006)
- `screenshots_root_folder` — existing field; annotated JPEGs are saved to the same
  location as before
- `screenshot_window_enabled`, `screenshot_window_start`, `screenshot_window_end` —
  existing fields; time-window check applies to annotated saves unchanged
- `use_default_sound`, `pinned_sound`, `sound_library_paths` — existing fields;
  the sound label displayed on the screenshot is derived from whichever of these
  determines what plays (see `data-model.md` → `play_alert()` return value)

**Backward compatibility**: Existing `settings.json` files load without modification.
No migration step is needed on upgrade.

---

## Internal API Contract: `play_alert()` Return Value

`play_alert(settings, default_path)` in `audio.py` changes its return type from
`None` to `str`. This is a **breaking change to the internal API** but affects only
one caller (`main.py`). All call sites must be updated.

| Caller | Required change |
|--------|-----------------|
| `src/catguard/main.py` — `on_cat_detected()` | Capture return value: `sound_label = play_alert(settings, default_sound)` and pass to `tracker.on_detection()` |

No other modules call `play_alert()` directly.

---

## Internal API Contract: `DetectionLoop.set_verification_callback()`

New public method on `DetectionLoop`. Callers must provide a callback with signature:

```python
def on_verification(has_cat: bool, boxes: list[BoundingBox]) -> None: ...
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `has_cat` | `bool` | `True` if ≥1 cat bounding box detected in the verification frame |
| `boxes` | `list[BoundingBox]` | All cat boxes detected in the verification frame (empty when `has_cat=False`) |

The callback is invoked from the `DetectionLoop` daemon thread. Implementations MUST
NOT perform blocking I/O or UI operations directly; they MUST dispatch such work to a
background thread (see `EffectivenessTracker.on_verification()` which uses
`_save_annotated_async()`).
