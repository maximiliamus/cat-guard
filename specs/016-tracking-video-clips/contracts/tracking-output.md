# Contract: Tracking Output

**Feature**: 016-tracking-video-clips  
**Date**: 2026-03-29

## 1. Settings Contract

Persisted settings:

```python
tracking_mode: Literal["screenshots", "videoclips"]
videoclip_fps: int  # positive whole number
videoclip_format: Literal["MJPG", "XVID", "MP4V"]
```

Rules:

- Default `tracking_mode` is `"screenshots"`.
- Default `videoclip_fps` is `1`.
- Default `videoclip_format` is `"MJPG"`.
- Unknown `tracking_mode` values are sanitized to `"screenshots"`.
- Invalid or non-positive `videoclip_fps` values are sanitized to `1`.
- Unknown `videoclip_format` values are sanitized to `"MJPG"`.
- The `Videoclip FPS` control is disabled in the UI when `tracking_mode == "screenshots"`.
- The UI must not impose an additional undocumented upper bound that is stricter than the specification.

## 2. Screenshot-Mode Output Contract

When `tracking_mode == "screenshots"`, the existing session timeline remains unchanged:

```text
<tracking_directory>/<YYYY-MM-DD>/<YYYYMMDD-HHmmss>-<NNN>.jpg
```

Rules:

- `001` is the session-start frame.
- Later JPEGs increment in save order.
- No `.avi` or `.mp4` clip is created for that session.

## 3. Video-Mode Output Contract

When `tracking_mode == "videoclips"`, one session produces one final clip:

```text
MJPG/XVID final: <tracking_directory>/<YYYY-MM-DD>/<YYYYMMDD-HHmmss>[-NN].avi
MJPG/XVID temp:  <tracking_directory>/<YYYY-MM-DD>/<YYYYMMDD-HHmmss>[-NN].partial.avi
MP4V final:      <tracking_directory>/<YYYY-MM-DD>/<YYYYMMDD-HHmmss>[-NN].mp4
MP4V temp:       <tracking_directory>/<YYYY-MM-DD>/<YYYYMMDD-HHmmss>[-NN].partial.mp4
```

Rules:

- Exactly one reserved path pair belongs to one session.
- Same-second collisions append `-01`, `-02`, ... before the extension.
- No standalone tracking `*.jpg` files are emitted for that same session.
- The writer streams frames into the temp path while the session is active.
- The final `.avi` or `.mp4` appears only after successful finalize.
- If final rename fails after readable frames were written, the matching readable `.partial.avi` or `.partial.mp4` remains as the recovery artifact.

## 4. Clip Frame Contract

Each written clip frame includes:

- the existing bounding-box overlays for the sampled detection snapshot
- the top information bar with the active alert sound label and the frame's local capture time
- a bottom strip whose state comes from the current session state

Bottom-strip states:

| State | Text |
|---|---|
| `detected` | `Cat detected` |
| `remained` | `Cat remained after alert: <duration>` |
| `deterred` | `Cat disappeared after alert: <duration>` |

Rules:

- The session-start frame is appended immediately with `Cat detected`.
- Verification frames are appended immediately when remained/disappeared outcomes are computed.
- Between those explicit event frames, the sampler keeps writing frames with the current overlay state until that state changes.
- If a new processed frame is not available on a sampler tick, the tracker may intentionally repeat the latest processed snapshot and its capture timestamp to preserve the configured clip cadence.
- If sampled frames change source resolution mid-session, `tracking_video.py` normalizes them to the clip's original output size before encode.

## 5. Interruption and Failure Invariants

- Manual pause, schedule stop, camera error, and app shutdown finalize the active temp clip as a partial clip if at least one readable frame was written.
- Interruption never fabricates a final green outcome.
- Clip-writer failures are logged and surfaced through the existing non-blocking error path.
- A clip-writer failure disables recording only for the current session; the next session retries fresh.
- Monitoring continues even if clip creation or finalize fails for one session.
- For automated validation, a partial clip is considered reviewable when the artifact exists and OpenCV can read at least one frame from it. Packaged OS-player compatibility remains a manual verification boundary.
