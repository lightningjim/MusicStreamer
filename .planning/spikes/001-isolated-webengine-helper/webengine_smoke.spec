# -*- mode: python ; coding: utf-8 -*-
#
# Spike 001 Stage A — standalone WebEngine smoke bundle.
# Run from this spike directory, inside the ISOLATED pip venv (.venv-helper):
#   pyinstaller webengine_smoke.spec --noconfirm
#
# The hiddenimport on PySide6.QtWebEngineCore triggers
# hook-PySide6.QtWebEngineCore -> get_qt_webengine_binaries_and_data_files(),
# which bundles QtWebEngineProcess.exe, resources/*.pak, locales, and the
# qt.conf the subprocess needs. (Recipe locked in 88.3-RESEARCH.md; here it
# runs against a pip-PySide6 env instead of conda.)
block_cipher = None

a = Analysis(
    ["webengine_smoke.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineCore",
        "PySide6.QtNetwork",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # No GStreamer / GTK / scientific stack in the isolated helper world.
        "tkinter", "matplotlib", "PIL", "numpy", "gi", "gst",
        # WebEngine pulls QtQuick/Qml as deps; keep everything else lean but do
        # NOT exclude Qml/Quick/Positioning/WebChannel/Pdf — WebEngine needs them.
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
    name="webengine_smoke",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,          # spike: keep the console so JSON-line stderr is visible
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
    name="webengine_smoke",
)
