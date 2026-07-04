# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['scanner_v3.py'],  # Change this to your main script's filename
    pathex=[],
    binaries=[],
    datas=[
        ('three.min.js', '.'),
        ('OrbitControls.js', '.'),
        ('GLTFLoader.js', '.'),
    ],
    hiddenimports=[
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebEngineCore',
        'serial',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='3D_Scanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, # Set to True if you want a debug console window behind the GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='scanner_icon.ico' # Optional: Add a path to an .ico file if you have one
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='3D_Scanner_App',
)