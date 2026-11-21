# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import customtkinter

ctk_path = os.path.dirname(customtkinter.__file__)

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('binaries/adb.exe', 'binaries'),
        ('binaries/AdbWinApi.dll', 'binaries'),
        ('assets', 'assets'),
        ('assets.py', '.'),
        ('config.py', '.'),
        (ctk_path, 'customtkinter/'),
    ],
    hiddenimports=[
        'customtkinter',
        'darkdetect',
        'PIL',
        'PIL._tkinter_finder',
        'cv2',
        'numpy',
        'mss',
        'pygetwindow',
        'keyboard',
        'modules.rally',
        'modules.fishing',
        'modules.adventure',
        'assets',
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
    a.binaries,
    a.datas,
    [],
    name='COC_AutoMaster',
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
)
