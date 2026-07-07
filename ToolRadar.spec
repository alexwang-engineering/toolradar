# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

block_cipher = None
base = Path(os.path.abspath('.'))

a = Analysis(
    ['app.py'],
    pathex=[str(base)],
    binaries=[],
    datas=[
        ('web',  'web'),
        ('data', 'data'),
    ],
    hiddenimports=[
        'webview',
        'webview.platforms.cocoa',
        'bottle',
        'requests',
        'bs4',
        'scraper',
        'server',
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
    name='ToolRadar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ToolRadar',
)

app = BUNDLE(
    coll,
    name='ToolRadar.app',
    icon='ToolRadar.icns',
    bundle_identifier='com.toolradar.app',
    info_plist={
        'NSHighResolutionCapable': True,
        'LSUIElement': False,
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleName': 'ToolRadar',
        'NSAppTransportSecurity': {'NSAllowsArbitraryLoads': True},
    },
)
