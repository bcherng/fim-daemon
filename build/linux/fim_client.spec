# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all

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
]

# Collect all submodules from core, gui, daemon, platform_specific
hidden_imports.extend(collect_submodules('core'))
hidden_imports.extend(collect_submodules('gui'))
hidden_imports.extend(collect_submodules('daemon'))
hidden_imports.extend(collect_submodules('platform_specific'))

# collect_all properly bundles C extension binaries for cryptography, bcrypt, cffi
# NOTE: collect_all returns (datas, binaries, hiddenimports)
crypto_datas, crypto_binaries, crypto_hiddenimports = collect_all('cryptography')
bcrypt_datas, bcrypt_binaries, bcrypt_hiddenimports = collect_all('bcrypt')
cffi_datas, cffi_binaries, cffi_hiddenimports = collect_all('cffi')
hidden_imports.extend(crypto_hiddenimports)
hidden_imports.extend(bcrypt_hiddenimports)
hidden_imports.extend(cffi_hiddenimports)

# Data files to include
datas = crypto_datas + bcrypt_datas + cffi_datas
binaries = crypto_binaries + bcrypt_binaries + cffi_binaries

a_client = Analysis(
    ['../../fim_client.py'],
    pathex=['../../src'],
    binaries=binaries,
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
    name='fim_client',
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

a_admin = Analysis(
    ['../../src/daemon/admin_daemon.py'],
    pathex=['../../src'],
    binaries=binaries,
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
    name='fim_admin',
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
    name='fim_client',
)