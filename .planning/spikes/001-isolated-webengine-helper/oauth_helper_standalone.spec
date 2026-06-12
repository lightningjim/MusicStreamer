# -*- mode: python ; coding: utf-8 -*-
#
# Spike 001 Stage B — freeze the REAL musicstreamer/oauth_helper.py as its own
# standalone exe (the B1 artifact), built from the ISOLATED pip venv.
# Run from this spike directory, inside .venv-helper:
#   pyinstaller oauth_helper_standalone.spec --noconfirm
#
# Faithfulness note: this freezes the actual production oauth_helper.py
# (stdlib + PySide6 only, no other musicstreamer imports), so a PASS here means
# the real login windows (gbs/twitch/google) open from the isolated bundle.
# The entry runs oauth_helper as __main__ -> main(), driven by --mode.
import os
from pathlib import Path

# SPECPATH is the dir holding this spec: .../MusicStreamer/.planning/spikes/001-...
# Repo root is three levels up.
REPO_ROOT = Path(SPECPATH).resolve().parents[2]
HELPER_SRC = REPO_ROOT / "musicstreamer" / "oauth_helper.py"
assert HELPER_SRC.is_file(), f"oauth_helper.py not found at {HELPER_SRC}"

block_cipher = None

a = Analysis(
    [str(HELPER_SRC)],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Same hook trigger as the conda spec's 88.3-01 lines — here it fires
        # against pip PySide6-Addons, whose Qt6WebEngineCore matches pip Qt6Core
        # (ABI-consistent; no conda shadowing).
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineCore",
        "PySide6.QtNetwork",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "PIL", "numpy", "gi", "gst",
    ],
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
    name="oauth_helper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Spike: console=True so the JSON-line stderr events are visible during VM
    # verification. The production B1 build can flip this to False once wired.
    console=True,
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
    upx=False,
    upx_exclude=[],
    name="oauth_helper",
)
