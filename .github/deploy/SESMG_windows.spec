# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import copy_metadata

import sys
sys.setrecursionlimit(sys.getrecursionlimit()*5)

datas = [('../../program_files','program_files'),
	     ('../../docs', 'docs'),
         ('../../README.md', '.'),
	     ('../../Lib/site-packages/typing_extensions.py', '.'),
	     ('../../Lib/site-packages/six.py', '.'),
	     ('../../Lib/site-packages/memory_profiler.py', '.'),
         ('../../Lib/site-packages/decorator.py', '.'),
	     ('../../Lib/site-packages/decouple.py', '.')]
datas += copy_metadata('streamlit')

options = [ ('W ignore', None, 'OPTION') ]

block_cipher = None


a = Analysis(
    ['..\\..\\program_files\\start_script.py'],
    pathex=["..\\..\\Lib\\site-packages"],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=["hooks"],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    options,
    name='SESMG',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
app = BUNDLE(
    exe,
    name='SESMG.exe',
    icon='SESMG.ico',
    bundle_identifier=None,
)

