# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all hidden imports
hidden_imports = [
    'tkinter',
    'tkinter.ttk',
    'tkinter.scrolledtext',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'watchdog',
    'watchdog.observers',
    'watchdog.events',
    'requests',
    'bcrypt',
    'cffi',
    '_cffi_backend',
    'daemon.background',
    'cryptography',
    'cryptography.hazmat',
    'cryptography.hazmat.primitives',
    'cryptography.hazmat.primitives.asymmetric',
    'cryptography.hazmat.primitives.asymmetric.rsa',
    'cryptography.hazmat.primitives.asymmetric.padding',
    'cryptography.hazmat.primitives.hashes',
    'cryptography.hazmat.primitives.serialization',
    'cryptography.hazmat.backends',
    'cryptography.hazmat.backends.openssl',
]

# Collect all submodules from core, gui, daemon, platform_specific
hidden_imports.extend(collect_submodules('core'))
hidden_imports.extend(collect_submodules('gui'))
hidden_imports.extend(collect_submodules('daemon'))
hidden_imports.extend(collect_submodules('platform_specific'))

# Data files to include
datas = []

a_client = Analysis(
    ['../../fim_client.py'],
    pathex=['../../src'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_client = PYZ(a_client.pure, a_client.zipped_data, cipher=block_cipher)

exe_client = EXE(
    pyz_client,
    a_client.scripts,
    [],
    exclude_binaries=True,
    name='FIMClient',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None
)

a_admin = Analysis(
    ['../../src/daemon/admin_daemon.py'],
    pathex=['../../src'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_admin = PYZ(a_admin.pure, a_admin.zipped_data, cipher=block_cipher)

exe_admin = EXE(
    pyz_admin,
    a_admin.scripts,
    [],
    exclude_binaries=True,
    name='FIMAdmin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None
)


coll = COLLECT(
    exe_client,
    a_client.binaries,
    a_client.zipfiles,
    a_client.datas,
    exe_admin,
    a_admin.binaries,
    a_admin.zipfiles,
    a_admin.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FIMClient',
)