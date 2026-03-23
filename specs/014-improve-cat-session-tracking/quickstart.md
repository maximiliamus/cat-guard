# Quickstart: Immediate Cat Session Frame Saving

**Feature**: 014-improve-cat-session-tracking  
**Date**: 2026-03-23

## Automated Validation

Run the focused test slices for this feature:

```powershell
pytest tests/unit/test_annotation.py -k "session or duration or detected"
pytest tests/unit/test_detection.py -k verification
pytest tests/unit/test_screenshots.py -k session
pytest tests/integration/test_detection_integration.py -k verification
pytest tests/integration/test_effectiveness_integration.py
```

## Manual Smoke Test

1. Launch CatGuard with a writable tracking directory and a short cooldown such as `30` seconds.
2. Trigger a cat detection.
3. Verify that a new JPEG appears immediately under the current date folder and ends with `-001.jpg`.
4. Open that file and confirm:
   - the bottom strip is dark gray
   - the text is `Cat detected`
   - the top bar still shows the alert sound label and save timestamp
5. Keep the cat in frame until the first verification fires.
6. Verify that `-002.jpg` appears and shows a red strip with `Cat remained after alert: 30s`.
7. Keep the cat in frame for one more cycle or adjust cooldown so a minute-scale example is practical.
8. Verify that the next saved frame uses the same session prefix, the suffix increments sequentially, and the duration text is human-readable, for example `1m 0s` or `2m 15s`.
9. Remove the cat before the next verification.
10. Verify that the next saved frame is green and says `Cat disappeared after alert: <duration>`.
11. Pause tracking during an active session and confirm that:
    - no synthetic final frame is created
    - already-saved session files remain on disk
12. Review the application log and confirm session-related entries use the same human-readable duration format as the overlays.

## Expected Output Pattern

Example for one session:

```text
tracking/
└── 2026-03-23/
    ├── 20260323-101500-001.jpg   # Cat detected
    ├── 20260323-101500-002.jpg   # Cat remained after alert: 30s
    └── 20260323-101500-003.jpg   # Cat disappeared after alert: 1m 0s
```
