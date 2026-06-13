# -*- mode: python ; coding: utf-8 -*-
#
# Phase 88.3-04 / B1 — freeze the REAL musicstreamer/oauth_helper.py as its own
# standalone exe (the B1 artifact), built from an ISOLATED pip venv.
# Promoted from spike 001 (.planning/spikes/001-isolated-webengine-helper/
# oauth_helper_standalone.spec) with one structural change: REPO_ROOT is
# computed via parents[1] because packaging/windows/ is exactly 2 directories
# below the repo root. The spike spec was 3 levels deep; this spec is 2 levels.
#
# Run from packaging/windows/ inside the isolated helper venv:
#   <venv>\Scripts\python.exe -m PyInstaller oauth_helper_standalone.spec --noconfirm
#
# build.ps1 does this automatically via its HELPER BUILD step (step 4e).
#
# Faithfulness note: this freezes the actual production oauth_helper.py
# (stdlib + PySide6 only, no other musicstreamer imports), so a PASS here means
# the real login windows (gbs/twitch/google) open from the isolated bundle.
# The entry runs oauth_helper as __main__ -> main(), driven by --mode.
#
# console=True preserves the stderr JSON-event observability that spike 001
# Stage B/C validated. The helper is a child process; no taskbar window flash
# concern (88.2 already accepts this for the --oauth-helper dispatch).
import os
from pathlib import Path

# SPECPATH is the dir holding this spec: .../MusicStreamer/packaging/windows/
# Repo root is two levels up (parents[1]).
# Path depth: packaging/windows/oauth_helper_standalone.spec => go up 2 levels.
REPO_ROOT = Path(SPECPATH).resolve().parents[1]
HELPER_SRC = REPO_ROOT / "musicstreamer" / "oauth_helper.py"
assert HELPER_SRC.is_file(), f"oauth_helper.py not found at {HELPER_SRC}"

block_cipher = None

a = Analysis(
    [str(HELPER_SRC)],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # These hook triggers fire against pip PySide6-Addons (isolated venv),
        # whose Qt6WebEngineCore matches pip Qt6Core (ABI-consistent; no conda
        # shadowing). This is the opposite of the conda MusicStreamer.spec's B1
        # invariant (which must NOT have WebEngine hiddenimports -- conda-forge
        # ships no PySide6 WebEngine bindings).
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
    # console=True preserves stderr JSON-event observability (spike 001 Stage B/C).
    # The helper is a child process; no taskbar flash concern beyond 88.2 baseline.
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
