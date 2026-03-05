# quickstart.md

## Local dev steps (summary)

1. Create and switch to feature branch: `git checkout -b 008-add-photo-action-panel`
2. Run tests: `pytest -q`
3. Implement UI: modify `src/catguard/main.py` and `src/catguard/ui/*` to add panel and photo window.
4. Wire saving: reuse `src/catguard/screenshots.build_filepath` and `cv2.imencode` for encoding.
5. Run integration tests: `pytest tests/integration -q`

## Minimal manual QA

- Start app, open main window, click `Take photo` → photo window opens with `Save` and `Save As...`.
- Click `Save` → file saved to `images/CatGuard/photos/<YYYY-MM-DD>/HH-MM-SS.jpg`.
- Click `Take photo with delay` → countdown visible, then photo saved.
