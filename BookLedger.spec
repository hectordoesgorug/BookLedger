# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

ROOT = Path(SPECPATH).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from bookledger import __version__
from scripts.windows_version_info import build_version_info

version_info = build_version_info(__version__)

a = Analysis(
    [str(ROOT / "src" / "bookledger" / "app.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[(str(ROOT / "assets"), "assets")],
    hiddenimports=["asyncio", "ifaddr"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "scripts" / "zeroconf_path.py")],
    excludes=["zeroconf"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BookLedger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    icon=str(ROOT / "assets" / "icon.ico"),
    version=version_info,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory="_internal",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="BookLedger",
)
