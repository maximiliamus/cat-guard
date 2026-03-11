# -*- mode: python ; coding: utf-8 -*-
#
# CatGuard PyInstaller spec file
# Build: pyinstaller catguard.spec --clean --noconfirm
# Output: dist/catguard/  (--onedir bundle)
#
import sys
import tomllib

# Read version from pyproject.toml (single source of truth)
with open('pyproject.toml', 'rb') as _f:
    _meta = tomllib.load(_f)
_version_str = _meta['project']['version']          # e.g. "0.5.0"
_v = tuple(int(x) for x in _version_str.split('.'))
_vt = _v + (0,) * (4 - len(_v))                    # pad to 4-tuple

# Windows version info resource — only available/needed on Windows
if sys.platform == 'win32':
    from PyInstaller.utils.win32.versioninfo import (
        VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable,
        StringStruct, VarFileInfo, VarStruct,
    )
    _version_info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=_vt, prodvers=_vt),
        kids=[
            StringFileInfo([StringTable('040904B0', [
                StringStruct('CompanyName',      'CatGuard'),
                StringStruct('FileDescription',  'CatGuard'),
                StringStruct('FileVersion',      _version_str),
                StringStruct('InternalName',     'CatGuard'),
                StringStruct('OriginalFilename', 'catguard.exe'),
                StringStruct('ProductName',      'CatGuard'),
                StringStruct('ProductVersion',   _version_str),
            ])]),
            VarFileInfo([VarStruct('Translation', [0x0409, 1200])]),
        ],
    )
else:
    _version_info = None

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
        # yolo11n.onnx is downloaded at runtime; not bundled here
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
    version=_version_info,
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
