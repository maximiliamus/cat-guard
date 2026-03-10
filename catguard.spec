# -*- mode: python ; coding: utf-8 -*-
#
# CatGuard PyInstaller spec file
# Build: pyinstaller catguard.spec --clean --noconfirm
# Output: dist/catguard/  (--onedir bundle)
#
import sys

# pywin32 ships win32timezone only on Windows
_win32_imports = ['win32timezone'] if sys.platform == 'win32' else []

# .ico icon is Windows-only; macOS/Linux use no icon
_icon = 'assets/icon.ico' if sys.platform == 'win32' else None

a = Analysis(
    ['src/catguard/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),           # bundle sounds/ and icon.ico
        ('yolo11n.onnx', '.'),          # bundle ONNX model
    ],
    hiddenimports=[
        # pystray backends — selected at runtime; static analysis misses them
        'pystray._win32',
        'pystray._darwin',
        'pystray._xorg',
        'pystray._appindicator',
        # pywin32 — Windows only
        *_win32_imports,
        # tkinter — not always auto-included (especially on Linux builds)
        'tkinter',
        'tkinter.ttk',
        '_tkinter',
        # platformdirs — dynamic submodule selection
        'platformdirs.unix',
        'platformdirs.windows',
        'platformdirs.macos',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio', 'ultralytics'],
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
    icon=_icon,
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
