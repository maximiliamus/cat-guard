# Quickstart: Tracking Mode with Video Clips

**Feature**: 016-tracking-video-clips  
**Date**: 2026-03-29

## Automated Validation

Run the focused test slices for this feature:

```powershell
pytest tests/unit/test_config.py -k "tracking_mode or videoclip"
pytest tests/unit/test_settings_window.py -k "tracking_mode or videoclip"
pytest tests/unit/test_detection.py -k "snapshot or capture_time"
pytest tests/unit/test_annotation.py -k "tracking mode or videoclip or capture time"
pytest tests/unit/test_tracking_video.py
pytest tests/integration/test_effectiveness_integration.py -k screenshots
pytest tests/integration/test_tracking_video_integration.py
pytest tests/integration/test_main_shutdown.py -k tracking_video
```

## Manual Smoke Test

1. Launch CatGuard with a writable `Tracking directory`.
2. Open `Settings`.
3. Confirm `Tracking mode` defaults to `Screenshots` and `Videoclip FPS` is disabled.
4. Switch `Tracking mode` to `Videoclips`.
5. Confirm `Videoclip FPS` becomes editable and starts at `1`.
6. Save the settings and restart the app.
7. Re-open `Settings` and confirm `Videoclips` mode plus the chosen fps are still selected.
8. Trigger a cat detection and let a session complete normally.
9. Verify exactly one `.avi` file appears under the session-start date folder in the tracking directory within 10 seconds of session completion.
10. Verify there are no session `*.jpg` files for that same session prefix.
11. Open the clip and confirm:
    - the earliest frames show the neutral `Cat detected` strip
    - the top bar shows the alert sound label and the actual frame capture time
    - a multi-cycle session visibly reaches `Cat remained after alert: <duration>`
    - the final visible outcome is `Cat disappeared after alert: <duration>`
12. Start another session in `Videoclips` mode, change `Tracking mode` or `Videoclip FPS`, save, and confirm the active clip keeps its original behavior while the next session uses the new setting.
13. Start a short video-mode session and interrupt it immediately after the first detection by using `Pause`.
14. Verify a readable partial clip still exists for that interrupted session, even if it contains only the opening frames.
15. Start another short video-mode session and exit through the tray menu.
16. Verify the real app-exit path also leaves a readable partial clip rather than deleting the active temp clip.
17. Inspect the log output for the runs above and confirm it records clip path reservation, sampler start/stop, finalize success, and interruption finalization/recovery events.
18. In a packaged build smoke test, confirm the generated `MJPG` + `.avi` clip opens on Windows, macOS, and Linux using the default player or document any platform exception before release.
19. Switch `Tracking mode` back to `Screenshots`.
20. Run another session and confirm the existing `-001.jpg`, `-002.jpg`, ... timeline returns and no `.avi` is created.

## Expected Output Pattern

### Video mode

```text
tracking/
└── 2026-03-29/
    └── 20260329-091500.avi
```

### Screenshot mode

```text
tracking/
└── 2026-03-29/
    ├── 20260329-093000-001.jpg
    ├── 20260329-093000-002.jpg
    └── 20260329-093000-003.jpg
```

## Notes

- The clip path uses the same session timestamp prefix and date-folder organization as the current JPEG timeline so both tracking modes remain easy to browse.
- A same-second collision is resolved by appending `-01`, `-02`, ... to the clip stem.
- `Videoclip FPS` is a session-start setting: changing it while a clip is already recording affects only the next session.
- If clip finalization cannot rename the file into place but the temp clip is still readable, the `.partial.avi` is intentionally preserved as the recovery artifact.
