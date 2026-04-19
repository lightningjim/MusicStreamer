# -*- mode: python ; coding: utf-8 -*-
#
# Phase 43: GStreamer Windows Spike — PyInstaller .spec
# Target: Windows 11 x86_64, GStreamer 1.24.12 MSVC runtime
# Run from: .planning/phases/43-gstreamer-windows-spike/ on the VM
#
# Usage: pyinstaller 43-spike.spec --noconfirm
#
import os
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Paths — the user sets GSTREAMER_ROOT env var before invoking pyinstaller.
# build.ps1 does this automatically; fallback to the default MSI location.
# --------------------------------------------------------------------------
GST_ROOT = Path(os.environ.get(
    "GSTREAMER_ROOT",
    r"C:\spike-gst\runtime\1.0\msvc_x86_64",
))
assert GST_ROOT.is_dir(), f"GStreamer root not found: {GST_ROOT}"
assert (GST_ROOT / "bin" / "gst-plugin-scanner.exe").is_file(), \
    "gst-plugin-scanner.exe missing — reinstall MSI with ADDLOCAL=ALL"
assert (GST_ROOT / "lib" / "gio" / "modules" / "libgiognutls.dll").is_file(), \
    "libgiognutls.dll missing — devel MSI required, or TLS feature deselected"

# --------------------------------------------------------------------------
# Tree() blocks — copy raw directory trees into the bundle.
# The contrib hook covers plugins (lib/gstreamer-1.0/) and most top-level DLLs,
# but DOES NOT cover: gio/modules, gst-plugin-scanner.exe, girepository-1.0,
# or the `share/` data files for glib-networking CA bundling.
# --------------------------------------------------------------------------
gio_modules_tree = Tree(
    str(GST_ROOT / "lib" / "gio" / "modules"),
    prefix="gio/modules",
    excludes=["*.pdb"],
)

# Scanner binary + typelibs — placed next to the bundle root
extra_binaries = [
    (str(GST_ROOT / "libexec" / "gstreamer-1.0" / "gst-plugin-scanner.exe"), "."),
    # fallback for older MSI layouts that put scanner under bin/
    # (str(GST_ROOT / "bin" / "gst-plugin-scanner.exe"), "."),
]

# GI typelibs — the gi hook normally collects these, but on Windows the
# discovered path is sometimes wrong for MSVC-built PyGObject. Bundle
# explicitly as a safety net. Hook will dedup if already present.
typelib_tree = Tree(
    str(GST_ROOT / "lib" / "girepository-1.0"),
    prefix="girepository-1.0",
    excludes=["*.pdb"],
)

# glib-networking share data (CA bundle location hints, schemas)
glib_share_tree = Tree(
    str(GST_ROOT / "share" / "glib-2.0" / "schemas"),
    prefix="share/glib-2.0/schemas",
)

# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------
block_cipher = None

a = Analysis(
    ["smoke_test.py"],
    pathex=[str(Path(".").resolve())],
    binaries=extra_binaries,
    datas=[],
    hiddenimports=[
        "gi",
        "gi.repository.Gst",
        "gi.repository.GLib",
        "gi.repository.GObject",
        "gi.repository.Gio",
    ],
    hookspath=[],
    hooksconfig={
        "gstreamer": {
            # ITERATION 1: broad — let the hook collect everything.
            # After smoke_test passes, revise with exclude_plugins to prune:
            # "exclude_plugins": [
            #     "opencv", "vulkan", "gtk*", "qt5*", "qt6*",
            #     "dash", "rtsp*", "rtmp*", "srt", "sctp",
            #     "*vaapi*", "d3d11*", "nv*", "webrtc*",
            # ],
        },
        "gi": {
            # No icon/theme bundling — spike has no GUI.
            "icons": [],
            "themes": [],
            "languages": [],
        },
    },
    runtime_hooks=["runtime_hook.py"],
    excludes=[
        # Cut obvious unused Qt/GUI deps — the spike is headless-ish (prints to stdout only)
        "tkinter", "matplotlib", "PIL", "numpy",
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
    name="spike",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # Do NOT UPX-compress GStreamer DLLs; breaks loading
    console=True,         # Spike is CLI — keep the console window
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
    gio_modules_tree,
    typelib_tree,
    glib_share_tree,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="spike",
)
