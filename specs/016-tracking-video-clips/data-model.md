# Data Model: Tracking Mode with Video Clips

**Feature**: 016-tracking-video-clips  
**Date**: 2026-03-29

---

## Entities

### TrackingPreferences (persisted settings)

User-configured tracking output choices stored in `Settings`.

| Field | Type | Description |
|---|---|---|
| `tracking_mode` | `Literal["screenshots", "videoclips"]` | Chooses whether tracked cat sessions are emitted as JPEG sequences or one session clip. |
| `videoclip_fps` | `int` | Positive whole-number target encode cadence used only when `tracking_mode == "videoclips"`. |
| `tracking_directory` | `str` | Existing root directory for date-organized tracking artifacts. |

**Validation rules**:

- `tracking_mode` falls back to `"screenshots"` when a saved value is unknown.
- `videoclip_fps` falls back to `1` when a saved value is invalid or not a positive whole number.
- `videoclip_fps` has no effect when `tracking_mode == "screenshots"`.

---

### TrackingSessionConfig (runtime snapshot)

Session-start snapshot owned by `EffectivenessTracker`.

| Field | Type | Description |
|---|---|---|
| `session_start` | `datetime` | Timestamp of the first alert in the session. Determines the date folder and filename prefix for the entire artifact, even if the session crosses midnight. |
| `mode` | `Literal["screenshots", "videoclips"]` | Output mode locked for the lifetime of the session. |
| `videoclip_fps` | `int` | Session-locked target clip cadence used only when `mode == "videoclips"`. |
| `tracking_root` | `Path` | Resolved tracking directory used for all session artifacts. |
| `clip_paths` | `TrackingClipPaths \| None` | Reserved temp/final clip paths for video mode, including any same-second collision suffix. |

**Validation rules**:

- Created exactly once at the first alert of a session.
- Not mutated by later settings saves.
- Cleared when the session closes or is abandoned.

---

### SessionOverlayState (runtime tracker state)

Current annotation state applied to saved JPEGs or sampled clip frames.

| Field | Type | Description |
|---|---|---|
| `sound_label` | `str` | Active alert sound label shown in the top bar. |
| `outcome` | `str \| None` | `detected`, `remained`, `deterred`, or `None`. |
| `outcome_message` | `str \| None` | Bottom-strip message corresponding to the current session state. |

**Rules**:

- A new session starts with `outcome="detected"` and `outcome_message="Cat detected"`.
- A remained/disappeared verification updates the overlay state immediately.
- Repeated sampled frames keep the current overlay state but do not imply a new outcome event.
- Interruption never invents a new overlay state.

---

### DetectionSnapshot (runtime detection-loop export)

Latest processed frame state exposed by `DetectionLoop` for active video sessions.

| Field | Type | Description |
|---|---|---|
| `frame_bgr` | `np.ndarray` | Latest captured frame copy. |
| `boxes` | `list[BoundingBox]` | Detection boxes computed for that same frame. |
| `captured_at` | `datetime` | Timezone-aware capture timestamp for that processed frame; rendered in local time on the clip top bar. |
| `sequence_number` | `int` | Monotonically increasing snapshot id used by the sampler to detect whether a new processed frame has arrived. |

**Validation rules**:

- `frame_bgr`, `boxes`, `captured_at`, and `sequence_number` are produced by the same inference iteration.
- Snapshot getter returns copies so recorder-side annotation cannot mutate loop-owned state.
- The tracker may intentionally write multiple clip frames from the same `DetectionSnapshot` when `videoclip_fps` exceeds sustainable processed-frame throughput.

---

### TrackingClipPaths (reserved on-disk names for `Videoclips` mode)

Reserved file paths for one session-scoped video artifact.

| Field | Type | Description |
|---|---|---|
| `final_path` | `Path` | `<tracking_directory>/<YYYY-MM-DD>/<YYYYMMDD-HHmmss>[-NN].avi` |
| `temp_path` | `Path` | Sibling temp file using the same stem with `.partial.avi` suffix while the session is active |
| `collision_index` | `int` | `0` for the base timestamp stem, otherwise `1`, `2`, ... for same-second collision suffixes |

**Rules**:

- Paths are reserved from `session_start`, not from later verification times.
- Same-second collisions append `-01`, `-02`, ... before the extension.
- The final `.avi` appears only after successful finalize; during recording, only the `.partial.avi` may be user-visible.

---

### TrackingClipArtifact (runtime/on-disk artifact in `Videoclips` mode)

One session-scoped video file produced when `tracking_mode == "videoclips"`.

| Attribute | Description |
|---|---|
| `paths` | Reserved `TrackingClipPaths` for the session |
| `fps` | Session snapshot `videoclip_fps` |
| `output_size` | Dimensions locked from the first successfully written frame |
| `frame_count` | Number of frames successfully written so far |
| `status` | `recording`, `finalized`, `finalized_partial`, `failed_current_session`, or `failed_unreadable` |
| `last_written_captured_at` | Capture time shown on the most recently written frame |

**Rules**:

- Exactly one final clip path belongs to one session.
- No standalone `*.jpg` tracking files are created for that same session.
- `finalize()` preserves a partial clip if at least one readable frame was written.
- Later frames with a different source resolution are normalized to `output_size` inside the clip writer before encode.
- If final rename fails after readable frames exist, the `.partial.avi` remains as the recovery artifact for that session.

---

### TrackingScreenshotArtifact (existing on-disk artifact in `Screenshots` mode)

Unchanged JPEG output path for the existing session timeline.

| Attribute | Description |
|---|---|
| `path` | `<tracking_directory>/<YYYY-MM-DD>/<YYYYMMDD-HHmmss>-<NNN>.jpg` |
| `suffix NNN` | 1-based saved-frame index within the session |

**Rule**:

- This artifact type is emitted only when the session snapshot mode is `screenshots`.

---

## State Transitions

### Screenshot mode

```text
[idle]
  |
  | on_detection(first alert)
  | -> snapshot mode=screenshots
  | -> save -001.jpg ("Cat detected")
  v
[session active]
  |
  | on_verification(has_cat=True)
  | -> save next .jpg with red outcome
  v
[session active]
  |
  | on_verification(has_cat=False)
  | -> save next .jpg with green outcome
  | -> reset session
  v
[idle]
```

### Video mode

```text
[idle]
  |
  | on_detection(first alert)
  | -> snapshot mode=videoclips + videoclip_fps
  | -> reserve unique temp/final clip paths
  | -> append immediate "Cat detected" frame
  | -> start sampler thread
  v
[clip recording]
  |
  | periodic sampler ticks at videoclip_fps
  | -> fetch latest DetectionSnapshot
  | -> append annotated live frame using current overlay state
  | -> if no newer snapshot is available, reuse the latest snapshot
  |    and the same capture timestamp to preserve clip cadence
  |
  | on_verification(has_cat=True)
  | -> update overlay to "Cat remained after alert: <duration>"
  | -> append verification frame immediately
  v
[clip recording]
  |
  | on_verification(has_cat=False)
  | -> update overlay to "Cat disappeared after alert: <duration>"
  | -> append verification frame immediately
  | -> stop sampler
  | -> finalize temp clip to final .avi
  | -> reset session
  v
[idle]
```

Interruption path:

```text
[clip recording]
  |
  | abandon() / manual pause / schedule stop / camera error / app shutdown
  | -> stop sampler under bounded timeout
  | -> finalize temp clip as partial output if readable
  | -> do not fabricate green outcome
  | -> reset session
  v
[idle]
```

---

## Affected Source Modules

| Module | Planned change |
|---|---|
| `src/catguard/config.py` | Add persisted `tracking_mode` / `videoclip_fps` with sanitizing validators |
| `src/catguard/ui/settings_window.py` | Add Storage-tab mode controls and model round-trip for new fields |
| `src/catguard/detection.py` | Expose latest processed detection snapshot plus capture timestamps for detection/verification callbacks |
| `src/catguard/annotation.py` | Snapshot session config, branch artifact strategy, manage clip sampler lifecycle, and pass capture times into annotation |
| `src/catguard/tracking_video.py` | New clip path reservation, size normalization, readability checks, and streamed writer implementation |
| `src/catguard/main.py` | Ensure pause/shutdown entry points finalize partial clips from tray-driven exit too |

---

## No Migration Required

- Existing settings files merge the new fields from defaults.
- Existing screenshot-mode output layout stays unchanged.
- Users must opt into `Videoclips`; nothing silently switches modes on upgrade.
