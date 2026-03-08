# -*- mode: python ; coding: utf-8 -*-
#
# CatGuard PyInstaller spec file
# Build: pyinstaller catguard.spec --clean --noconfirm
# Output: dist/catguard/  (--onedir bundle)
#
from PyInstaller.utils.hooks import collect_all

# Collect all ultralytics data, binaries, and hidden imports
# (resolves the common cfg/default.yaml FileNotFoundError at runtime)
ultralytics_datas, ultralytics_binaries, ultralytics_hiddenimports = collect_all('ultralytics')

a = Analysis(
    ['src/catguard/__main__.py'],
    pathex=[],
    binaries=ultralytics_binaries,
    datas=[
        ('assets', 'assets'),          # bundle sounds/ and icon.ico
        ('yolo11n.pt', '.'),           # bundle YOLO model (avoids download on first run)
        *ultralytics_datas,
    ],
    hiddenimports=[
        # pystray backends — selected at runtime; static analysis misses them
        'pystray._win32',
        'pystray._darwin',
        'pystray._xorg',
        'pystray._appindicator',
        # pywin32 — frequently absent from auto-detection
        'win32timezone',
        # tkinter — not always auto-included (especially on Linux builds)
        'tkinter',
        'tkinter.ttk',
        '_tkinter',
        # platformdirs — dynamic submodule selection
        'platformdirs.unix',
        'platformdirs.windows',
        'platformdirs.macos',
        *ultralytics_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='catguard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # windowed mode — no terminal window on launch
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='catguard',
)
