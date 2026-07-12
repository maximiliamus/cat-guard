# Research: Tracking Mode with Video Clips

**Feature**: 016-tracking-video-clips  
**Date**: 2026-03-29  
**Status**: Complete

---

## R-001: Keep screenshot mode as the unchanged baseline

**Decision**: Preserve the current JPEG session timeline as-is behind an explicit `tracking_mode="screenshots"` branch and make `Screenshots` the persisted default.

**Rationale**: The spec is additive, not a replacement. Reusing the existing tracker save path minimizes regression risk and preserves current behavior for all users who never opt into video output.

**Alternatives considered**:

- Replace JPEG tracking globally with clip generation. Rejected because it would violate FR-018 and create an unnecessary migration.
- Add a hidden automatic fallback to screenshots from video mode. Rejected because FR-009a explicitly forbids standalone JPEGs for a video-mode session.

---

## R-002: Do not introduce an undocumented upper bound for `Videoclip FPS`

**Decision**: Keep `videoclip_fps` as a positive whole-number setting with no additional spec-independent maximum. The plan treats the configured value as the target clip cadence, while actual unique frame throughput remains best-effort and may be lower than requested.

**Rationale**: The feature spec requires positive integers but does not define a tighter user-visible range. Adding a hidden or UI-only cap would create an undocumented product constraint. Best-effort sampling keeps the design honest without silently narrowing the requirement.

**Alternatives considered**:

- Reuse the existing `1-30` `detection_fps` range. Rejected because it would add a new user-visible limit that the spec does not document.
- Cap the setting internally but not in the UI. Rejected because it would still be an undocumented constraint, just harder for users to understand.

---

## R-003: Stream frames into a collision-safe temp `.avi` and preserve readable partials

**Decision**: Add a streamed `TrackingClipWriter` that writes annotated frames into a temp `.avi` file using `cv2.VideoWriter` + `MJPG`, then renames it to the final session path on finalize. Same-second collisions use `-NN` suffixes, and a readable `.partial.avi` is preserved when final rename fails after frames were written.

**Implementation extension**: MJPG/AVI remains the default, while the completed settings surface also offers XVID/AVI and MP4V/MP4. The same collision-safe temp/final lifecycle applies to the selected extension.

**Rationale**: Streaming avoids buffering an unbounded session in memory, satisfies the “one clip per session” requirement, and makes partial-clip preservation on pause/error/shutdown straightforward. Reserving unique paths up front avoids timestamp collisions without changing the visible session timestamp prefix.

**Alternatives considered**:

- Buffer all frames in memory and encode at session end. Rejected because clip finalization time and memory usage would grow with session length.
- Introduce an external encoder dependency. Rejected by the simplicity principle and packaging burden.
- Write directly to the final file name from frame one. Rejected because a temp-to-final rename makes finalize semantics, interrupted-session handling, and cleanup rules clearer.

---

## R-004: Export atomic detection snapshots and capture-time timestamps from the detection loop

**Decision**: Extend `DetectionLoop` to retain the latest processed frame, boxes, capture timestamp, and a monotonically increasing snapshot sequence under the existing frame lock. `get_latest_detection_snapshot()` returns copies of that atomic bundle, and the verification callback also carries the capture timestamp of the frame it is evaluating.

**Rationale**: The camera should remain single-owned by the detection loop. Atomic snapshots keep boxes paired with the exact frame they were inferred from, which is required for FR-017 and for per-frame top-bar times to reflect capture time rather than delayed encoding time.

**Alternatives considered**:

- Start a second camera capture thread for video sessions. Rejected because many cameras do not tolerate concurrent readers reliably.
- Reuse `set_frame_callback()` for clip recording. Rejected because Live View already depends on that single callback channel.
- Poll only `get_latest_frame()` without boxes or timestamps. Rejected because FR-012 and FR-017 require capture-time overlays plus matching detection evidence.

---

## R-005: Keep overlay state in the tracker and force-write key event frames

**Decision**: `EffectivenessTracker` remains the owner of session overlay state and writes explicit start/verification frames immediately in video mode, while a background sampler fills the in-between frames using the latest session state. Repeated sampled frames with the same capture timestamp are treated as continuity, not as new outcome events.

**Rationale**: The spec requires the clip to preserve session start context and each remained/disappeared outcome. Forcing writes on those exact transition points guarantees they appear in the clip even if the periodic sampler is between ticks.

**Alternatives considered**:

- Let only the periodic sampler write frames. Rejected because the session-start and final outcome overlays could otherwise be missed or appear late.
- Encode only the explicit start and verification frames into a pseudo-video. Rejected because FR-008 requires tracking frames at the configured clip cadence throughout the session.

---

## R-006: Snapshot tracking mode and clip fps at session start

**Decision**: Store a `TrackingSessionConfig` snapshot inside `EffectivenessTracker` when a session starts and use that snapshot for the entire session.

**Rationale**: `main.py` mutates the shared `settings` object in place after Save. Without a snapshot, a mid-session settings change would alter the artifact already in progress, violating FR-019.

**Alternatives considered**:

- Read `settings.tracking_mode` and `settings.videoclip_fps` lazily for every frame. Rejected because mid-session saves would change recording behavior.

---

## R-007: Normalize mid-session resolution changes in the clip writer

**Decision**: Lock the clip output size from the first successfully written frame and normalize later frames to that size inside `tracking_video.py` using aspect-preserving letterbox padding.

**Rationale**: `cv2.VideoWriter` requires stable frame dimensions for a single clip. Handling resolution normalization inside the writer keeps `annotation.py` focused on session logic and avoids duplicated resize rules between explicit writes and sampler writes.

**Alternatives considered**:

- Abort recording on the first size change. Rejected because it would discard usable evidence for a camera quirk the user may never notice live.
- Stretch frames to fit the writer size. Rejected because distortion would make evidence review less trustworthy.

---

## R-008: Finalize partial clips on every interruption path with a bounded shutdown budget

**Decision**: Treat `abandon()` and app shutdown as valid clip-finalization paths in video mode. The partial clip is preserved with the last real recorded overlay state, and no synthetic green outcome is created. Sampler shutdown and finalize/rename each run under bounded timeouts so app exit cannot hang beyond the 10-second success target.

**Rationale**: The spec explicitly values partial footage when monitoring pauses, the camera fails, or the app stops. Finalizing the existing temp clip preserves that evidence while keeping behavior honest and keeping exit latency predictable.

**Alternatives considered**:

- Delete temp clips on interruption. Rejected because it discards valuable session evidence.
- Append a fake success/failure end card. Rejected because FR-020 forbids fabricating an outcome that never occurred.
- Wait indefinitely for sampler shutdown or file rename. Rejected because it would jeopardize SC-001 and degrade normal app exit.

---

## R-009: Reuse existing test ownership and add an explicit codec-compatibility manual boundary

**Decision**: Reuse the current settings, detection, tracker, and integration test files, add focused clip-writer and shutdown coverage, and treat packaged-player compatibility for `MJPG` + `.avi` as an explicit manual verification boundary for Windows, macOS, and Linux release smoke tests.

**Rationale**: The session-state logic still belongs to the tracker and detection loop, so existing test ownership should remain intact. Automated tests can prove that OpenCV writes and reads valid clips; packaged OS-player compatibility is a broader release concern that should be acknowledged instead of implied.

**Alternatives considered**:

- Create a broad “tracking mode v2” mega-suite. Rejected because it would fragment behavior already covered by the current tests and make regressions harder to localize.
- Assume OpenCV readback alone proves packaged-player compatibility. Rejected because codec support can still vary by platform media stack.
