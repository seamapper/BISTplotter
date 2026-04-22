# -*- mode: python ; coding: utf-8 -*-
# Exe name is derived from version.py (same string as bist_plotter window title).

import os
import sys

try:
    _spec_dir = os.path.dirname(os.path.abspath(SPECPATH))
except NameError:
    _spec_dir = os.getcwd()
if _spec_dir not in sys.path:
    sys.path.insert(0, _spec_dir)

from version import __version__

EXE_NAME = f'BIST_Plotter_V{__version__}'


a = Analysis(
    ['bist_plotter.py'],
    pathex=[],
    binaries=[],
    datas=[('media', 'media')],
    hiddenimports=['cmcrameri', 'cmcrameri.cm', 'version'],
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
    a.binaries,
    a.datas,
    [],
    name=EXE_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['media\\mac.ico'],
)
