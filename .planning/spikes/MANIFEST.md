# Spike Manifest

## Idea

Resolve the Phase 88.3 G6 blocker — in-app OAuth logins (GBS.FM, Twitch,
Google/YouTube) crash the helper subprocess (exit 2) on the PyInstaller-frozen
Windows build because QtWebEngine cannot live in the conda single-bundle.
Diagnosis (88.3-UAT, 2026-06-11): conda-forge ships **zero** PySide6 WebEngine
bindings at any version, and pip PySide6-Addons' WebEngine is ABI-incompatible
with conda `qt6-main`/GStreamer in one process — conda's `Qt6Core.dll` on PATH
shadows pip's, producing a DLL-load failure. The chosen path is **B1
(isolated-helper-bundle)**: freeze `oauth_helper` as its **own** PyInstaller exe
from a pip-only, Qt-isolated env (no conda, no GStreamer), and have the conda
main exe launch that separate binary. This spike proves B1 is feasible before it
is planned as 88.3 gap closure.

## Requirements

Design decisions locked during spiking (non-negotiable for the real build):

- The isolated helper env is **pip-only** (`PySide6-Essentials` +
  `PySide6-Addons`), never conda — that ABI-consistency is the entire fix.
- Helper PySide6 is **pinned to 6.10.1** to match the conda main app, so the
  `QNetworkCookie` / cookie-Netscape contract that `tests/test_oauth_helper_*`
  assert stays byte-identical across the two independently-frozen artifacts
  (spike decision 2026-06-11).
- The helper exe must load its **own** bundled Qt by adjacency even when conda's
  `Library\bin` is on PATH (Stage C) — otherwise spawning it from the conda
  main exe re-triggers the G6 failure.
- B1 ships **two** PyInstaller artifacts (conda main bundle + pip helper
  bundle); the Inno installer carries both. (Integration is out of spike scope —
  it becomes the 88.3 gap-closure plan.)
- The isolated helper build needs a **conda-free Python 3.12** (python.org, or a
  clean conda-forge `python+pip` env used only as the venv provider) — surfaced
  on the VM, which had only miniforge (spike 001, VM run 1).
- The helper exe must be launched from a **local install path**; Chromium's
  WebEngine sandbox refuses to spawn `QtWebEngineProcess.exe` from a network/UNC
  path. Always true once Inno-installed to `C:\Program Files\...`; never run from
  a VM share (spike 001, VM run 2).

## Spikes

| # | Name | Type | Validates | Verdict | Tags |
|---|------|------|-----------|---------|------|
| 001 | isolated-webengine-helper | standard | Given a pip-only PySide6-Addons env (no conda/GStreamer), when `oauth_helper` is PyInstaller-frozen as its own exe and run on Win11, then WebEngine login windows open with no DLL-load failure, cookie-capture completes, and the bundle's Qt wins over conda-on-PATH | PENDING (VM) | windows, pyinstaller, qtwebengine, oauth, packaging, 88.3-g6 |
