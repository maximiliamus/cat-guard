# Research: Immediate Cat Session Frame Saving

**Feature**: 014-improve-cat-session-tracking  
**Date**: 2026-03-23  
**Status**: Complete

---

## R-001: Stop buffering session screenshots across cooldowns

**Decision**: Change the internal verification callback contract so `DetectionLoop` passes the live verification frame to the callback, and replace the loop's long-lived pending image buffer with a metadata-only pending flag.

**Rationale**: The feature request is specifically about eliminating the "only in memory until later" behavior. Saving the current verification frame directly solves the discarded-evaluation-frame problem and removes the need to retain a prior screenshot across the cooldown window.

**Alternatives considered**:

- Keep the old pending frame copy and continue saving it after verification. Rejected because it preserves the stale in-memory artifact the feature is meant to remove.
- Add another tracker-side image buffer. Rejected because it duplicates state and works against the same requirement.

---

## R-002: Reuse the existing overlay pipeline for the first session frame

**Decision**: Extend `annotate_frame()` with a neutral `detected` outcome style that renders a dark gray bottom strip with white text and defaults to `Cat detected`.

**Rationale**: This keeps all session frames on one annotation path, preserves consistent bar geometry, and avoids a special-case drawing function for the first saved frame.

**Alternatives considered**:

- Draw the start-frame strip with a dedicated helper. Rejected because it would duplicate layout logic already centralized in `annotate_frame()`.

---

## R-003: Make the session filename suffix a saved-frame index

**Decision**: Keep `build_session_filepath()` but reinterpret the suffix as a 1-based saved-frame index within the session: `001` for the neutral start frame, `002+` for outcome frames.

**Rationale**: Once the first frame is saved immediately, the old "cycle number equals suffix" scheme no longer reflects the user-visible timeline. Sequential frame numbering produces the clearest review order on disk.

**Alternatives considered**:

- Keep the old cycle suffix and give the start frame `000`. Rejected because it makes the first visible artifact look like a prelude rather than the first session frame.
- Add a textual suffix like `-start`. Rejected because it complicates lexical sorting and filename parsing.

---

## R-004: Preserve cooldown-based elapsed time, change only its presentation

**Decision**: Continue to compute elapsed session time as `int(cycle_count * cooldown_seconds)`, but format that value through a shared human-readable helper.

**Rationale**: The existing session semantics are tied to alert cooldown cycles, not to sub-second wall-clock drift. Keeping the same calculation avoids reinterpreting the meaning of session duration while still satisfying the new readability requirement for overlays and logs.

**Alternatives considered**:

- Use wall-clock time from `datetime.now() - session_start`. Rejected because inference and scheduling jitter would produce inconsistent values that no longer match the alert cadence the user configured.

---

## R-005: Keep session ownership in `EffectivenessTracker`, but only for metadata

**Decision**: `EffectivenessTracker` remains the owner of session sequencing and overlay message generation, but it stores only session metadata (`session_start`, `cycle_count`, `frame_index`, `active_sound_label`) and no deferred image payload.

**Rationale**: The tracker is still the right place for session rules, file ordering, and outcome messages. Removing the image buffers keeps the object aligned with its purpose and simplifies reset behavior on pause or error.

**Alternatives considered**:

- Introduce a new `SessionTracker` class. Rejected because the feature is localized and the existing tracker already owns the right behavior boundary.

---

## R-006: No new settings or storage roots

**Decision**: Reuse the existing `tracking_directory`, session timestamp prefix, async save pipeline, and current date-folder layout.

**Rationale**: The feature changes when and how frames are persisted, not where the user wants them stored. New settings would add complexity without adding control the request actually needs.

**Alternatives considered**:

- Add a dedicated "session tracking mode" setting. Rejected because the behavior is the new default for the existing session-tracking feature, not an optional branch.

---

## R-007: Extend the existing test files instead of creating new suites

**Decision**: Add coverage to `test_annotation.py`, `test_detection.py`, `test_screenshots.py`, `test_detection_integration.py`, and `test_effectiveness_integration.py`.

**Rationale**: These files already own the affected behavior boundaries. Extending them keeps the test surface discoverable and matches the repository's current testing organization.

**Alternatives considered**:

- Create a new `test_cat_session_tracking_v2.py`. Rejected because it would fragment closely related tracker and detection-loop coverage.
