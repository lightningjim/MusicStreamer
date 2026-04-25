# -*- mode: python ; coding: utf-8 -*-
#
# Phase 44: MusicStreamer Windows Installer — PyInstaller .spec
# Target: Windows 11 x86_64, GStreamer 1.28.2 MSVC runtime (single-installer)
# Run from: packaging/windows/ on the VM
#
# Usage: pyinstaller MusicStreamer.spec --noconfirm
#
# This file is copied verbatim from .planning/phases/43-gstreamer-windows-spike/43-spike.spec
# with the documented diff per .planning/phases/44-windows-packaging-installer/44-RESEARCH.md
# §Pattern 4 (lines 677-749).
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
    r"C:\spike-gst\runtime",
))
assert GST_ROOT.is_dir(), f"GStreamer root not found: {GST_ROOT}"

# Scanner: 1.28.x MSVC ships it under libexec/gstreamer-1.0/; support legacy bin/ fallback for 1.24/1.26.
_scanner_libexec = GST_ROOT / "libexec" / "gstreamer-1.0" / "gst-plugin-scanner.exe"
_scanner_bin = GST_ROOT / "bin" / "gst-plugin-scanner.exe"
assert _scanner_libexec.is_file() or _scanner_bin.is_file(), \
    "gst-plugin-scanner.exe missing — reinstall with Complete feature set"
SCANNER_SRC = _scanner_libexec if _scanner_libexec.is_file() else _scanner_bin

# TLS backend: 1.28.x ships OpenSSL (gioopenssl.dll); 1.24/1.26 shipped GnuTLS (libgiognutls.dll). Accept either.
_tls_openssl = GST_ROOT / "lib" / "gio" / "modules" / "gioopenssl.dll"
_tls_gnutls = GST_ROOT / "lib" / "gio" / "modules" / "libgiognutls.dll"
assert _tls_openssl.is_file() or _tls_gnutls.is_file(), \
    "No GIO TLS backend found — expected gioopenssl.dll (1.28+) or libgiognutls.dll (1.26-); reinstall with Complete feature set"

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

# Scanner binary + typelibs — placed next to the bundle root.
# SCANNER_SRC resolved above: libexec/gstreamer-1.0/ (1.28.x) or bin/ (legacy).
extra_binaries = [
    (str(SCANNER_SRC), "."),
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
    ["../../musicstreamer/__main__.py"],
    pathex=[str(Path(".").resolve())],
    binaries=extra_binaries,
    datas=[
        ("../../musicstreamer/ui_qt/icons", "musicstreamer/ui_qt/icons"),  # SVG source
        ("icons/MusicStreamer.ico", "icons"),                              # installed icon
    ],
    hiddenimports=[
        "gi",
        "gi.repository.Gst",
        "gi.repository.GLib",
        "gi.repository.GObject",
        "gi.repository.Gio",
        # PySide6 extras that hooks-contrib sometimes misses:
        "PySide6.QtNetwork",      # QLocalServer/QLocalSocket (single-instance)
        "PySide6.QtSvg",          # SVG icon rendering
        # Windows media keys (43.1 already declared optional-dependencies.windows):
        "winrt.windows.media",
        "winrt.windows.media.playback",
        "winrt.windows.storage.streams",
        "winrt.windows.foundation",
    ],
    hookspath=[],
    hooksconfig={
        "gstreamer": {
            # ITERATION 1: broad — let the hook collect everything. Per D-16.
            # After UAT passes, revise with exclude_plugins to prune:
            # "exclude_plugins": [
            #     "opencv", "vulkan", "gtk*", "qt5*", "qt6*",
            #     "dash", "rtsp*", "rtmp*", "srt", "sctp",
            #     "*vaapi*", "d3d11*", "nv*", "webrtc*",
            # ],
        },
        "gi": {
            # Qt renders our own SVG icons; no GTK icon theme bundling needed.
            "icons": [],
            "themes": [],
            "languages": [],
        },
    },
    runtime_hooks=["runtime_hook.py"],
    excludes=[
        # Cut obvious unused Qt/GUI deps
        "tkinter", "matplotlib", "PIL", "numpy",
        # Ensure no mpv/GTK remnants sneak in (defensive — 35-06 retired these):
        "mpv", "gi.repository.Gtk", "gi.repository.Adw",
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
    name="MusicStreamer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # Do NOT UPX-compress GStreamer DLLs; breaks loading
    console=False,        # D-04/PKG-03: GUI app, no console window flash
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icons/MusicStreamer.ico",   # Windows EXE icon
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
    name="MusicStreamer",
)
