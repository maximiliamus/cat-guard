# Implementation Plan: Tracking Mode with Video Clips

**Branch**: `016-tracking-video-clips` | **Date**: 2026-03-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/016-tracking-video-clips/spec.md`

## Summary

Add an additive tracking-output choice that keeps the current per-session JPEG timeline as the default `Screenshots` mode and introduces an optional `Videoclips` mode that records one annotated clip per cat session. The implementation reuses the current session tracker, overlays, and tracking directory, adds validated settings for `tracking_mode` and `videoclip_fps`, streams frames into a session-scoped OpenCV clip writer while the session is active, preserves readable partial clips on pause/camera-error/shutdown, and treats unsustainable requested clip fps as a best-effort sampling problem rather than as a hidden product cap.

## Technical Context

**Language/Version**: Python 3.14+  
**Primary Dependencies**: `opencv-python` (`cv2` capture, annotation, `VideoWriter`), `numpy`, `pydantic`, `tkinter`, `pystray`, `platformdirs`  
**Storage**: Existing `tracking_directory` date subfolders; JPEG session frames in `Screenshots` mode; one `.avi` clip per `Videoclips` session plus an in-progress `.partial.avi` temp artifact; optional `-NN` suffix resolves same-second clip-name collisions  
**Testing**: `pytest` unit and integration tests with `tmp_path`, mocks, real JPEG/video writes, OpenCV readback, and explicit tray-exit shutdown coverage; manual packaged-build verification for `MJPG` + `.avi` playback on Windows, macOS, and Linux  
**Target Platform**: Windows, macOS, and Linux desktop environments  
**Project Type**: Single-project desktop application (`tkinter` UI + tray + background detection loop)  
**Performance Goals**: Preserve constitution target of `<200ms` p95 detection latency, keep normal clip finalization within the spec target of 10 seconds after session close, and bound sampler-stop/finalize work so app exit cannot hang beyond that target  
**Constraints**: No new runtime dependency such as ffmpeg; screenshot mode must remain behaviorally unchanged; video-mode sessions must not emit standalone tracking JPEGs; settings changes apply only to the next session; `videoclip_fps` accepts positive whole numbers only; actual unique-frame throughput may be lower than requested because it depends on detection-loop throughput and camera/CPU limits  
**Scale/Scope**: Single-user desktop app, one active tracking session at a time, session length unbounded except by available disk space

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Test-First Development | PASS | The plan starts with failing tests for settings validation, session-mode branching, capture-time overlays, clip finalization, and shutdown-path partial preservation before implementation changes. |
| II. Observability & Logging | PASS | The design logs tracking mode selection, path reservation, sampler start/stop, clip-writer start/finalize/failure events, collision suffixes, and recovery behavior when a `.partial.avi` must be preserved. |
| III. Simplicity & Clarity | PASS | The design reuses `EffectivenessTracker`, `annotate_frame()`, and the existing tracking directory; it adds one focused `tracking_video.py` module and avoids second-camera readers or external encoders. |
| IV. Integration Testing | PASS | Real file integration coverage is planned for screenshot regression, clip creation/readback, low-throughput duplication behavior, rename failure recovery, and tray-exit shutdown. |
| V. Versioning & Breaking Changes | PASS | The change is backward-compatible: default mode remains screenshot tracking, existing settings files merge safely, and no migration is required. |

**Post-design re-check**: PASS. The design keeps the new behavior additive, preserves the current JPEG session flow behind an explicit mode flag, avoids new external runtime dependencies, and makes the manual codec-compatibility boundary explicit instead of assuming it away.
**Merge gate note**: Constitution compliance remains conditional on implementation-phase completion of automated tests and the repository’s required peer review before merge.

## Project Structure

### Documentation (this feature)

```text
specs/016-tracking-video-clips/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── tracking-output.md
└── tasks.md             # Created later by /speckit.tasks
```

### Source Code (repository root)

```text
src/catguard/
├── annotation.py          # Session tracker branches between screenshot and clip artifacts
├── config.py              # Persisted tracking_mode / videoclip_fps fields + validators
├── detection.py           # Latest processed detection snapshots + capture-time callback payloads
├── main.py                # Tracker wiring and unified graceful shutdown finalization
├── tracking_video.py      # New clip path reservation + streamed OpenCV video writer
└── ui/settings_window.py  # Tracking mode controls and videoclip FPS widget state

tests/unit/
├── test_annotation.py       # Screenshot regression, video-mode tracker flow, capture-time overlays
├── test_config.py           # Settings validation / fallback for tracking_mode and videoclip_fps
├── test_detection.py        # Snapshot getter and verification callback timestamp semantics
├── test_settings_window.py  # SettingsFormModel round-trip for new tracking fields
├── test_tracking_video.py   # Clip path reservation, temp-file finalization, resize, failure handling
└── test_main.py             # Optional shutdown helper unit coverage if cleanup is factored out

tests/integration/
├── test_effectiveness_integration.py   # Screenshot-mode regression coverage
├── test_main_shutdown.py               # Real tray/main-loop shutdown path finalizes active clip
└── test_tracking_video_integration.py  # Real clip creation, close, partial finalization, rename recovery
```

**Structure Decision**: Keep the single-project layout. `annotation.py` remains the owner of session state and overlay decisions, `tracking_video.py` owns clip naming/encoding/finalization, and `main.py` owns the application entry points that must finalize an active partial clip.

## Complexity Tracking

*No constitution violations. Section left blank.*

---

## Spec-to-Plan Traceability

| Requirement | Planned design coverage | Validation |
|---|---|---|
| FR-001 | Change 1 adds a `Tracking mode` control with exactly two persisted values: `screenshots` and `videoclips`. | Unit: `test_settings_window.py`; Manual: settings UI smoke test |
| FR-002 | Change 1 keeps `"screenshots"` as the stored default. | Unit: `test_config.py`, `test_settings_window.py` |
| FR-003 | Change 1 adds a persisted `videoclip_fps` setting. | Unit: `test_config.py`, `test_settings_window.py` |
| FR-004 | Change 1 sets the default `videoclip_fps` to `1`. | Unit: `test_config.py`, `test_settings_window.py` |
| FR-005 | Change 1 validates `videoclip_fps` as a positive whole number without adding a tighter undocumented cap. | Unit: `test_config.py`; Manual: settings-entry validation |
| FR-006 | Change 1 disables the `Videoclip FPS` control whenever `Tracking mode` is `Screenshots`. | Unit: `test_settings_window.py`; Manual: settings UI smoke test |
| FR-007 | Change 1 persists both settings across restart via `Settings` round-trip. | Unit: `test_config.py`, `test_settings_window.py`; Manual: restart smoke test |
| FR-008 | Changes 3-4 sample/write clip frames at the session-locked `videoclip_fps`; if unique processed frames arrive more slowly, the sampler repeats the latest snapshot to preserve clip cadence. | Unit: `test_annotation.py`, `test_detection.py`; Integration: low-throughput case in `test_tracking_video_integration.py` |
| FR-009 | Changes 2 and 4 reserve exactly one clip artifact per video-mode session and finalize that one artifact on close/interruption. | Unit: `test_tracking_video.py`, `test_annotation.py`; Integration: `test_tracking_video_integration.py` |
| FR-009a | Change 4 keeps video-mode writes entirely inside the clip-writer branch and never dispatches JPEG tracking saves. | Unit: `test_annotation.py`; Integration: clip exists while session `*.jpg` is absent |
| FR-010 | Change 2 stores clips under the existing date-organized `tracking_directory`, keyed by the session-start date even when the session crosses midnight. | Unit: `test_tracking_video.py`; Integration: `test_tracking_video_integration.py` |
| FR-011 | Changes 2-4 preserve the session’s chronological flow from forced start frame through explicit verification frames and any partial finalization path. | Unit: `test_annotation.py`; Integration: completed and interrupted clip readback |
| FR-012 | Changes 3-4 carry the processed frame’s capture timestamp into annotation so each written frame shows actual local capture time, not encode/finalize time. | Unit: capture-time overlay test in `test_annotation.py`; Integration: delayed-write/readback case |
| FR-013 | Change 4 keeps the existing remained/disappeared message conventions and uses explicit verification writes so the correct cumulative duration is visible even if the sampler tick is misaligned. | Unit: `test_annotation.py`; Integration: multi-cycle readback |
| FR-014 | Change 4 writes the immediate session-start `Cat detected` frame before the periodic sampler starts. | Unit: `test_annotation.py`; Integration: first-frame readback |
| FR-015 | Change 4 updates overlay state and force-writes each remained outcome in sequence with monotonically increasing durations. | Unit: `test_annotation.py`; Integration: multi-cycle readback |
| FR-016 | Change 4 force-writes the disappearance outcome frame, then stops sampling and finalizes the clip. | Unit: `test_annotation.py`; Integration: final-frame readback |
| FR-017 | Change 3 exports atomic frame+boxes snapshots, and Change 4 annotates clip frames from those paired snapshots so detection evidence stays visible. | Unit: `test_detection.py`, `test_annotation.py`; Integration: clip readback with boxes |
| FR-018 | Change 4 preserves the current screenshot path unchanged whenever the session snapshot mode is `screenshots`. | Unit: `test_annotation.py`; Integration: `test_effectiveness_integration.py` |
| FR-019 | Changes 1 and 4 snapshot mode/fps only at session start; later settings saves affect the next session only. | Unit: `test_annotation.py`; Integration: mid-session save + next-session adoption |
| FR-020 | Changes 2, 4, and 5 finalize readable partial clips on pause, schedule stop, camera error, tray exit, and signal shutdown without inventing a final outcome. | Unit: `test_tracking_video.py`, `test_annotation.py`; Integration: interruption and tray-exit shutdown tests |
| FR-021 | Changes 2 and 5 log create/write/finalize failures, surface them non-blockingly, preserve monitoring, and scope writer disablement to the current session only. | Unit: `test_tracking_video.py`, `test_annotation.py`; Integration: rename/write failure tests |
| SC-001 | Changes 2, 4, and 5 guarantee one clip per completed video session, no JPEGs in that session, and bounded finalize/shutdown sequencing under 10 seconds. | Integration: completed-session finalize timing + tray-exit shutdown coverage |
| SC-002 | Changes 3-4 ensure clip frames alone expose sound label, capture time, and final outcome. | Integration: clip readback assertions; Manual: playback smoke test |
| SC-003 | Change 1 plus Change 4’s session snapshot prove settings persist and only affect the next session after save. | Unit: settings round-trip tests; Integration: mid-session save / next-session adoption |
| SC-004 | Change 4 keeps screenshot mode behavior unchanged and clip-free. | Integration: `test_effectiveness_integration.py` |
| SC-005 | Changes 2, 4, and 5 preserve readable partial clips for pause, camera error, schedule stop, and tray exit; automated acceptance is “OpenCV can read at least one frame”, while packaged player compatibility stays manual. | Integration: interruption matrix + shutdown path; Manual: packaged-build smoke test |

---

## Implementation Design

### Change 1 - `config.py` and `ui/settings_window.py`: add persisted tracking output settings

Add two new settings fields:

- `tracking_mode: str = "screenshots"`
- `videoclip_fps: int = 1`

Design details:

- Persist stable lowercase values (`"screenshots"` / `"videoclips"`) while the UI shows `Screenshots` / `Videoclips`.
- Validate `tracking_mode` with a sanitizing `field_validator(..., mode="before")` that falls back to `"screenshots"` on unknown saved values instead of resetting the entire settings file.
- Validate `videoclip_fps` with a sanitizing `mode="before"` validator that accepts only positive whole-number values, logs a warning for invalid input, and falls back to `1` for missing, invalid, or non-positive values.
- The settings UI must not introduce a tighter undocumented maximum. Use a validated numeric entry or equivalent integer-only control rather than a hard-capped slider-style widget.
- Extend `SettingsFormModel.from_settings()` / `.to_settings()` for both new fields.
- Add a `Tracking mode` radio group and `Videoclip FPS` control on the existing Storage tab, directly under `Tracking directory`, because the controls govern how tracking artifacts are emitted and stored.
- Disable the `Videoclip FPS` widget whenever `Tracking mode` is `Screenshots`.
- Saving settings during an active session updates the shared `Settings` object as today, but the active tracker session ignores those new values because Change 4 snapshots mode/fps at session start.

Why this change:

- It fulfills the user-facing configuration surface without introducing a new top-level settings category.
- Sanitizing validators are required because the current `load_settings()` path resets the full file on validation failure, which is too destructive for one bad video-fps value.
- Avoiding a hidden `1-30` cap keeps the plan consistent with the current spec wording.

### Change 2 - `tracking_video.py`: streamed per-session clip writer with collision-safe paths and readable-partial recovery

Add a focused module that owns clip-path generation, frame-size normalization, and streamed OpenCV writing:

- `reserve_tracking_clip_paths(root: Path, session_ts: datetime) -> TrackingClipPaths`
- `TrackingClipWriter(...)`

Chosen output contract:

- Final path: `<tracking_directory>/<YYYY-MM-DD>/<YYYYMMDD-HHmmss>.avi`
- Same-second collision path: `<tracking_directory>/<YYYY-MM-DD>/<YYYYMMDD-HHmmss>-01.avi`, then `-02`, ...
- Active-write temp path: same stem with `.partial.avi`
- Codec/container: OpenCV `VideoWriter` with `MJPG` into `.avi`

Design details:

- Path reservation happens once at session start from the session-start timestamp, not from later verification times. The date folder therefore stays anchored to the session start even if the clip crosses midnight.
- The writer is lazy-opened from the first annotated frame so output dimensions come from the real session input.
- The first `Cat detected` frame is annotated before the writer opens; that annotated frame is then used to open the writer and becomes frame 1 if open succeeds.
- Frames are written incrementally throughout the session; the plan explicitly rejects buffering the full clip in memory because SC-001 and SC-005 require fast finalization and partial-clip preservation.
- The writer locks `output_size` from the first successful write. Later frames with different source dimensions are normalized to that size with aspect-preserving letterbox padding inside `tracking_video.py`, so `annotation.py` does not need duplicate resize logic.
- `write_frame()` returns a success/failure result. On failure, the tracker logs the failure, surfaces a non-blocking error, marks clip recording disabled for the current session only, and continues monitoring without falling back to JPEGs in `Videoclips` mode.
- `finalize(deadline_monotonic)` releases the writer and renames the temp path to the final `.avi`.
- If zero frames were written, `finalize()` deletes any empty temp file and reports that no user-visible clip artifact exists for that session.
- If final rename fails after readable frames were written, the design keeps the `.partial.avi` as the recovery artifact, reports that path in the error/log message, and does not retry indefinitely.
- For automated validation, a partial clip is “reviewable” when the artifact exists and OpenCV can read at least one frame from it. Cross-platform default-player compatibility for packaged builds is explicitly a manual verification boundary, not an implied automated guarantee.
- While a session is still in progress, the only user-visible artifact is the temp `.partial.avi`. The final `.avi` becomes visible only after successful finalize.

Why `.avi` / `MJPG`:

- It avoids introducing `ffmpeg` or another external dependency.
- It keeps the implementation inside already-installed `opencv-python`.
- It provides a stable container OpenCV can create and reopen in automated tests, while the packaged-player compatibility boundary remains explicit in manual verification.

### Change 3 - `detection.py`: expose atomic processed snapshots and capture-time callback payloads

The clip recorder needs current frames plus matching detection boxes and capture timestamps while a video-mode session is active. Extend `DetectionLoop` with:

- latest processed boxes + capture timestamp + snapshot sequence stored under the existing frame lock
- `get_latest_detection_snapshot() -> DetectionSnapshot | None`
- verification callback payload that includes `captured_at` from the same inference iteration as `frame_bgr` and `boxes`

Loop timing design:

- `detection_fps` continues to control how often the app performs inference and produces a new processed snapshot.
- `videoclip_fps` controls how often the clip sampler writes frames into the video artifact.
- When `detection_fps >= videoclip_fps`, the sampler typically writes the latest processed snapshot available on each tick and naturally drops intermediate processed snapshots it does not need.
- When `videoclip_fps > detection_fps` or the camera/CPU cannot sustain unique frames at the requested clip cadence, the sampler writes repeated frames from the latest processed snapshot and preserves that snapshot’s original capture timestamp on the top bar. Those repeated frames are intentional continuity context, not new outcome events.
- No temporary stream-fps floor is introduced. That avoids a hidden CPU-cost escalation path and keeps `videoclip_fps` from silently imposing a second performance cap or floor on the detection loop.

Synchronization details:

- The existing `_frame_lock` becomes the single synchronization point for the latest raw frame, latest processed detection snapshot, and any capture timestamp associated with that snapshot.
- `get_latest_detection_snapshot()` returns copies of the frame and boxes so recorder-side annotation cannot mutate loop-owned state.
- Because frame, boxes, timestamp, and sequence are updated and copied under the same lock, FR-017’s requirement that boxes and frames stay paired does not require a new lock type or cross-module synchronization primitive.

Why this approach:

- It keeps the camera owned by one loop.
- It avoids stealing the single `set_frame_callback()` channel from the Live View window.
- It defines the relationship between `detection_fps` and `videoclip_fps` precisely enough to support low-throughput scenarios without inventing a new undocumented performance limit.

### Change 4 - `annotation.py`: session snapshot and artifact-mode branching in `EffectivenessTracker`

Keep `EffectivenessTracker` as the session-state owner, but add a per-session config snapshot and a clip-recorder branch.

New runtime concepts:

- `TrackingSessionConfig`: session-start snapshot of `tracking_mode`, `videoclip_fps`, `tracking_directory`, reserved clip paths, and session timestamp
- `OverlayState`: current bottom-strip kind/message plus current sound label
- optional `TrackingClipWriter`, sampler thread, last-sampled snapshot sequence, and a small state lock for overlay/session reads during clip writes
- `annotate_frame(..., captured_at=...)` or an equivalent helper path so top-bar timestamps come from the frame’s capture time rather than from annotation time

Ownership boundaries:

- `annotation.py` owns session lifecycle, overlay-state transitions, and the decision of when a frame must be written.
- `tracking_video.py` owns path reservation, size normalization, temp/final file handling, readability checks, and finalize cleanup.
- `main.py` owns wiring of pause/shutdown entry points that must call `tracker.abandon()`.

Flow by mode:

1. `on_detection(frame, boxes, sound_label, captured_at)`
   - Ignore duplicate detection events while verification is already pending, exactly as the current tracker does.
   - Snapshot `tracking_mode` and `videoclip_fps` only when a new session starts.
   - `screenshots` mode: keep current behavior, including immediate `-001.jpg` save.
   - `videoclips` mode:
     - reserve clip paths
     - initialize overlay state to `Cat detected`
     - annotate the immediate detection frame with its capture time and current boxes
     - open the clip writer from that annotated frame and write it as frame 1 before the sampler starts
     - start a sampler thread only after the opening frame is safely written
   - On later detections in an active session, increment cycle count and update only the current sound label; do not create a new artifact.

2. Sampler thread (video mode only)
   - Runs on a monotonic schedule at the session snapshot’s `videoclip_fps`.
   - Reads the latest detection snapshot on each tick.
   - Annotates the sampled frame with the current sound label, the snapshot’s local capture time, latest boxes, and the current overlay state.
   - Writes directly to the active clip writer
   - If the latest snapshot sequence has not changed since the previous tick, the sampler intentionally reuses the most recent processed snapshot so the clip still advances at the requested cadence.
   - Holds a small lock around overlay/session state reads so verification updates cannot race clip writes.
   - Recording continues while Live View is open; clip sampling is not gated by `_main_window_visible`, screenshot suppression logic, or ownership of `set_frame_callback()`.

3. `on_verification(frame_bgr, has_cat, boxes, captured_at)`
   - Compute the existing cooldown-based elapsed time with `int(cycle_count * cooldown_seconds)`, so durations keep the current whole-second truncation behavior.
   - `screenshots` mode: preserve the current JPEG save path
   - `videoclips` mode:
     - update the overlay state to `remained` or `deterred`
     - append the verification frame immediately using the verification callback’s capture timestamp so each outcome is guaranteed to appear in the clip even if the sampler tick is not aligned with the cooldown boundary
     - on `has_cat=False`, stop sampling, finalize the clip, and reset session state
   - If the session ends before the sampler produces its first periodic tick, the clip still contains at least the forced start frame and forced verification frame(s).

4. `abandon(reason)`
   - `screenshots` mode: keep current reset behavior.
   - `videoclips` mode:
     - stop the sampler under a bounded join timeout (target: `<=2s`)
     - finalize the partial clip as-is under the remaining shutdown/finalize budget
     - preserve the clip even if only the opening `Cat detected` frame was written, as long as the artifact is reviewable
     - clear session state without fabricating a final green outcome

Failure and retry scope:

- A `TrackingClipWriter` failure disables clip recording only for the current session. The next video-mode session attempts to reserve paths and open a fresh writer again.
- Repeated sampled frames carrying the same remained outcome are intentionally background context, not duplicate outcome transitions.

Why the session snapshot matters:

- `main.py` mutates the shared `settings` object in place after Save.
- FR-019 requires the session already in progress to keep the mode/fps it started with.
- Reading `settings.tracking_mode` or `settings.videoclip_fps` lazily during the session would violate the spec.

### Change 5 - `main.py`: graceful exit must finalize active partial clips

The current app cleanup path abandons sessions for signal-driven shutdown, but tray-driven exit returns from `root.mainloop()` without guaranteed tracker finalization. Refactor shutdown into an idempotent helper used by all relevant stop paths:

- signal handlers
- the post-`root.mainloop()` exit path
- manual pause / continue transitions
- time-window schedule stop / restart
- camera error handling

Design details:

- `shutdown_app(reason)` becomes the single cleanup helper for process exit. It calls `tracker.abandon(reason)` before stopping monitors, detection, and audio.
- `root.mainloop()` return now routes through the same cleanup helper instead of relying on signal-only shutdown.
- `on_tracking_state_changed(False)` continues to abandon the active session for manual pause and schedule stop, which validates the plan’s “one active session at a time” assumption against real pause/resume entry points.
- `on_camera_error()` continues to notify the user non-blockingly, but now relies on the same abandon/finalize contract used elsewhere.
- Resume paths start a fresh session from the next detection event; no paused video session is resumed in-place.
- The cleanup helper passes a bounded deadline into the tracker’s sampler stop/finalize flow so normal exit cannot hang beyond SC-001’s 10-second target. A practical split is `<=2s` for sampler shutdown and the remaining budget for writer release/rename/cleanup, with timeout exhaustion falling back to logging plus preserving any already-readable `.partial.avi`.

Why this change:

- FR-020 and SC-005 explicitly require partial clips to survive real interruption paths, not just synthetic direct calls to `tracker.abandon()`.
- Validating every stop path against the “one active session at a time” assumption prevents a design that only works for the happy path.

---

## Test Plan

### Unit tests (write first)

**`tests/unit/test_config.py`**

- `tracking_mode` defaults to `"screenshots"`
- `videoclip_fps` defaults to `1`
- invalid `tracking_mode` values fall back to `"screenshots"` with a warning
- invalid / non-integer / non-positive `videoclip_fps` values fall back to `1` without resetting unrelated settings
- large positive integer `videoclip_fps` values remain accepted by the settings model so the plan does not reintroduce an undocumented cap

**`tests/unit/test_settings_window.py`**

- `SettingsFormModel` round-trips `tracking_mode` and `videoclip_fps`
- form defaults reflect the new persisted defaults
- a small pure helper for widget enable-state (if introduced) returns enabled only for `videoclips`
- the chosen input control allows positive integer entry without a hard-coded tighter maximum than the settings model

**`tests/unit/test_detection.py`**

- latest detection snapshot returns copies of the frame, boxes, timestamp, and sequence from one atomic update
- verification callback receives the same capture timestamp as the frame/boxes being verified
- snapshot sequence increments only when a new processed frame is produced

**`tests/unit/test_tracking_video.py`**

- `reserve_tracking_clip_paths()` uses the session start date folder and base timestamp stem
- same-second collisions reserve `-01`, `-02`, ... suffixes without overwriting an existing final or temp path
- temp-path naming stays adjacent to the final `.avi`
- `finalize()` renames the temp clip into the final path
- zero-frame finalize deletes the temp file and yields no user-visible artifact
- writer-open or frame-write failures surface as controlled exceptions/results for the tracker to handle
- resize normalization converts later frames to the locked writer size without distortion
- failed rename preserves a readable `.partial.avi` but removes empty/unreadable temp files
- readability check succeeds only when OpenCV can read at least one frame

**`tests/unit/test_annotation.py`**

- screenshot mode still saves `-001.jpg`, `-002.jpg`, etc. unchanged
- video mode does not dispatch `_save_annotated_async()` for session frames
- the tracker snapshots mode/fps at session start, so later settings changes do not affect the active session
- a later session picks up the newly saved mode/fps after the previous session closes
- `annotate_frame()` uses the supplied capture time rather than `now()`
- `on_detection()` in video mode writes the opening `Cat detected` frame before the sampler starts
- repeated sampler writes using the same snapshot sequence are recorded as continuity frames, not as new outcome transitions
- `on_verification(..., has_cat=False)` in video mode appends the final outcome frame and finalizes the clip
- a session shorter than the first sampler tick still yields a readable clip from forced frames alone
- `abandon()` in video mode finalizes a partial clip, including the “opening frame only” case, and clears session state
- clip-writer failure disables recording only for the current session
- video recording continues while Live View is open

**`tests/unit/test_main.py`** *(if shutdown logic is factored into a helper)*

- `shutdown_app()` is idempotent
- `shutdown_app()` calls `tracker.abandon()` before stopping detection/audio/monitors
- post-`root.mainloop()` cleanup uses the same shutdown helper as signal handlers

### Integration tests

**`tests/integration/test_effectiveness_integration.py`**

- with `tracking_mode="screenshots"`, the current JPEG session timeline is still produced exactly as before
- switching back from `videoclips` to `screenshots` restores JPEG-only output for the next session

**`tests/integration/test_tracking_video_integration.py`**

- a completed video-mode session creates exactly one `.avi` clip under the expected date folder
- the same session creates zero standalone `*.jpg` files
- the clip can be opened with OpenCV and contains more than one readable frame
- the first readable frame shows the neutral `Cat detected` strip
- a later frame shows a red `Cat remained after alert: <duration>` strip in a multi-cycle session
- the final readable frame shows the green `Cat disappeared after alert: <duration>` strip in a completed session
- a delayed write/readback case proves the top-bar time came from the frame capture timestamp, not finalize time
- a same-second second session produces a collision-safe `-01` clip rather than overwriting the first clip
- a low-throughput run where `videoclip_fps` exceeds sustainable processed-frame throughput still yields a readable clip with repeated continuity frames and no fabricated extra outcomes
- a mid-session settings save proves the active clip keeps its original mode/fps while the next session adopts the new values
- an interrupted session (`abandon()`) leaves a readable partial clip on disk
- a finalize-rename failure preserves a readable `.partial.avi`, surfaces a non-blocking error, and leaves monitoring alive for subsequent sessions

**`tests/integration/test_main_shutdown.py`**

- tray-exit / `root.mainloop()` shutdown finalizes an active partial clip through the real app cleanup path
- camera-error cleanup finalizes the active partial clip and still reports the error non-blockingly
- schedule-stop / pause cleanup finalizes the active partial clip and a later resume starts a fresh session

### Manual verification

- Open Settings and verify the `Videoclip FPS` control enables only when `Videoclips` is selected.
- Save `Videoclips` mode, restart the app, and confirm the same selection and fps are restored.
- Run one session in `Videoclips` mode and verify one `.avi` appears with no `*.jpg` session frames.
- Change settings during an active video session and confirm the active clip does not change behavior until the next session.
- Run one short video session, interrupt it with `Pause`, and confirm a readable partial clip exists even if it contains only the opening frames.
- Run another short video session and exit through the tray, confirming the real shutdown path also preserves a readable partial clip.
- Validate packaged `MJPG` + `.avi` playback on Windows, macOS, and Linux before release; if a platform-specific player cannot open the artifact even though OpenCV can, document that boundary or revisit the codec choice before shipping.
- Run one session in `Screenshots` mode and verify the existing JPEG sequence still appears with no clip.

## Delivery Notes

- The plan intentionally keeps the clip-container choice internal; the user-facing feature is “one reviewable clip per session,” not container/codec configuration.
- For automated acceptance, “reviewable partial clip” means OpenCV can open the artifact and read at least one frame. Default-player compatibility in packaged builds is tracked as manual release validation.
- Repeated frames with the same capture timestamp are an explicit and acceptable representation of low-throughput continuity; they are not separate outcome events.
- The plan does not introduce a new upper `Videoclip FPS` limit. If product requirements later need a tighter supported range, that must be added to the spec first so the constraint is user-visible and testable.
