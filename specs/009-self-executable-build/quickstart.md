# Quickstart: Building CatGuard Executable Locally

**Branch**: `009-self-executable-build` | **Date**: 2026-03-08

---

## Prerequisites

- Python 3.14+ with virtual environment activated
- All CatGuard dependencies installed (`pip install -e .`)
- PyInstaller and hooks: `pip install pyinstaller pyinstaller-hooks-contrib`
- **Linux only**: `sudo apt-get install -y python3-tk`

---

## Build

```bash
# From the repository root
pyinstaller catguard.spec --clean --noconfirm
```

The output is placed in `dist/catguard/` (directory bundle).

---

## Run the Built Executable

```bash
# Windows
dist\catguard\catguard.exe

# macOS / Linux
./dist/catguard/catguard
```

On first run, CatGuard will download the YOLO model (~6 MB) as usual.

---

## Package for Distribution

```bash
# Windows (PowerShell)
Compress-Archive -Path dist/catguard -DestinationPath catguard-windows.zip

# macOS / Linux
zip -r catguard-macos.zip dist/catguard     # or catguard-linux.zip
```

---

## Triggering the CI Build

- **Push to `main`**: triggers build only (no release). Artifacts retained 7 days.
- **Push a version tag**: triggers build + GitHub Release.

```bash
git tag v0.4.0
git push origin v0.4.0
```

GitHub Release will be created automatically with executables for all three platforms attached.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: pystray._win32` | Ensure `catguard.spec` includes pystray hidden imports |
| `FileNotFoundError: cfg/default.yaml` | Ensure `collect_all('ultralytics')` is in spec |
| App launches but no tray icon (Linux) | Install `python3-tk` and `libappindicator3` on target machine |
| Windows SmartScreen blocks executable | Right-click → Properties → Unblock, or run from terminal |
| macOS Gatekeeper blocks executable | System Settings → Privacy & Security → Open Anyway |
