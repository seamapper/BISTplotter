# -*- mode: python ; coding: utf-8 -*-
# Generic spec for BIST Plotter. Update name= in EXE() to match __version__ in bist_plotter.py (e.g. BIST_Plotter_V2026.4).


a = Analysis(
    ['bist_plotter.py'],
    pathex=[],
    binaries=[],
    datas=[('media', 'media')],
    hiddenimports=[],
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
    name='BIST_Plotter_V2026.4',
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
