# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

root = Path(SPECPATH)
datas = [
    (str(root / 'tools'), 'tools'),
    (str(root / 'README.md'), '.'),
    (str(root / 'LICENSE'), '.'),
    (str(root / 'docs' / 'INSTALL.md'), '.'),
    (str(root / 'THIRD_PARTY_NOTICES.md'), '.'),
    (str(root / 'licenses'), 'licenses'),
]
datas += collect_data_files('qoder_agent_sdk')
datas += collect_data_files('yt_dlp_ejs')
datas += collect_data_files('playwright')
for package in ('yt-dlp', 'yt-dlp-ejs', 'qoder-agent-sdk', 'requests', 'certifi', 'PySide6', 'shiboken6', 'anyio', 'mcp'):
    try:
        datas += copy_metadata(package)
    except Exception:
        pass

hiddenimports = collect_submodules('yt_dlp') + collect_submodules('qoder_agent_sdk')
a = Analysis(
    ['main.py'], pathex=[str(root)], binaries=[], datas=datas,
    hiddenimports=hiddenimports,
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'IPython', 'notebook', 'pytest',
              'zmq', 'jupyter_client', 'jupyter_core', 'torch', 'tensorflow', 'PyQt5', 'PyQt6', 'PySide2'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='Shiying', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    icon=str(root / 'assets' / 'app.ico'),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Shiying')
