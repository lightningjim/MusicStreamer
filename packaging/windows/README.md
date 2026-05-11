# MusicStreamer — Windows Packaging

This directory contains the Windows build pipeline: a PyInstaller `.spec`,
a runtime hook for GStreamer, an Inno Setup installer script, and a
PowerShell driver (`build.ps1`) that ties them together. Running
`.\build.ps1` on a configured Win11 box produces a single
`MusicStreamer-<version>-win64-setup.exe` under `dist\installer\`.

The pipeline is the implementation of the patterns proven in Phase 43's
GStreamer Windows spike. See `.planning/phases/43-gstreamer-windows-spike/`
for the canonical findings (DLL/typelib/scanner bundling, TLS module
search path, MSVC-vs-MinGW gotchas).

## Build prerequisites

1. **Miniforge / conda-forge environment** — create once on the build VM:
   ```powershell
   conda create -n musicstreamer-build -c conda-forge `
       python=3.12 pygobject gstreamer=1.28 `
       gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly `
       gst-libav `
       pyinstaller "pyinstaller-hooks-contrib>=2026.2"
   conda activate musicstreamer-build
   # AAC playback requires gst-libav (Phase 69 — provides avdec_aac in gstlibav.dll).
   # aacparse ships with gst-plugins-good's audioparsers plugin (gstaudioparsers.dll).
   ```
   The conda-forge GStreamer package ships the MSVC build with
   `gst-plugin-scanner.exe`, the GIO TLS module (`gioopenssl.dll`), and
   typelibs in the layout the `runtime_hook.py` expects (D-18, D-19).
   PyInstaller >= 6.19 + hooks-contrib >= 2026.2 are required for the
   `gi`/`gstreamer` hooks; older versions miss the `girepository-1.0`
   discovery on Windows.

2. **Inno Setup 6.3+** — download the installer from
   <https://jrsoftware.org/isdl.php> and run it. The build script looks
   for `iscc.exe` at the default path
   `C:\Program Files (x86)\Inno Setup 6\iscc.exe`. If you installed
   somewhere else, point the script at it via the `INNO_SETUP_PATH`
   environment variable:
   ```powershell
   $env:INNO_SETUP_PATH = "D:\Apps\InnoSetup\iscc.exe"
   ```

3. **Windows 10/11 x64.** No admin rights required at build time or at
   install time (the installer is per-user; see "Install behavior" below).

## Build command

From this directory:
```powershell
cd packaging\windows
.\build.ps1
```

What each step produces:

| Step                        | Output                                                   |
| --------------------------- | -------------------------------------------------------- |
| Pre-flight (GStreamer DLLs) | Verifies `gstreamer-1.0-0.dll`, TLS module, scanner exist |
| PKG-03 guard                | Runs `tools/check_subprocess_guard.py` (single source of truth) |
| Spec entry guard            | Runs `tools/check_spec_entry.py`                         |
| PyInstaller                 | `dist\MusicStreamer\` — onedir bundle + `MusicStreamer.exe` |
| Inno Setup compile          | `dist\installer\MusicStreamer-<version>-win64-setup.exe` |
| Diagnostic                  | `BUILD_DIAG bundle_size_mb=… dll_count=… installer_size_mb=…` |

Logs are tee'd to `packaging\windows\artifacts\build.log` and
`artifacts\iscc.log` (gitignored).

## Output

- `dist\MusicStreamer\` — PyInstaller onedir bundle. Run
  `dist\MusicStreamer\MusicStreamer.exe` to test the bundle directly
  before producing the installer.
- `dist\installer\MusicStreamer-2.0.0-win64-setup.exe` — final
  distributable installer (file name reflects `[project].version`
  from `pyproject.toml`).

## Install behavior

The installer is **per-user**: it requests no admin elevation, installs
to `%LOCALAPPDATA%\MusicStreamer`, and adds a single Start Menu shortcut.
No Desktop shortcut, no Pin-to-Taskbar (per D-04 / D-23). User data
(SQLite database, cookies, tokens, accent CSS, EQ profiles, logo cache)
lives in `%APPDATA%\musicstreamer` and is **preserved across uninstall
and upgrade** by design (D-03).

## Node.js prerequisite (RUNTIME-01)

MusicStreamer requires Node.js for **YouTube playback only**. Other
stream types (ShoutCast, HLS, Twitch, AudioAddict / DI.fm) work
without it. Install Node.js LTS from <https://nodejs.org>. The app
detects the absence of Node at startup and surfaces a non-blocking
warning + persistent hamburger-menu indicator. There is no
mid-session re-detection — restart the app after installing Node.

## Launching MusicStreamer (SMTC overlay binding)

**Always launch MusicStreamer via the Start Menu shortcut** (Start → type
"MusicStreamer" → Enter), NOT via `python -m musicstreamer` from a terminal.

Why: the Start Menu shortcut carries the `AppUserModelID` property
(`org.lightningjim.MusicStreamer`) that Windows uses to bind the SMTC media
overlay (Win+K) to the app's display name. Launching via `python -m
musicstreamer` bypasses this binding — Windows shows "Unknown app" in SMTC
instead of "MusicStreamer". This is documented Microsoft behaviour for
desktop apps without an MSIX manifest.

During installation, leave the "Run MusicStreamer" checkbox **unchecked**
at the end of the installer wizard. The installer's Run flag launches the
app via the installer process tree, which also bypasses the AUMID binding.
After install, launch normally via the Start Menu shortcut and SMTC will
read "MusicStreamer".

The AUMID literal must stay in lockstep across `musicstreamer/__main__.py`
(`_set_windows_aumid` default arg) and `packaging/windows/MusicStreamer.iss`
(`AppUserModelID:` clause). Drift between the two silently breaks SMTC
binding with no build error. `tests/test_aumid_string_parity.py` enforces
this on every Linux-CI run — do not delete it.

*(Phase 56 / WIN-02 — see `.planning/phases/56-windows-di-fm-smtc-start-menu/`
for the full diagnostic procedure if the SMTC overlay still shows
"Unknown app" after installation.)*

## Known limitations

- **DI.fm HTTPS rejected server-side (D-15):** AudioAddict / DI.fm
  premium streams must be loaded over **HTTP**, not HTTPS. The
  AudioAddict server returns TLS handshake errors for direct HTTPS
  connections from GStreamer's `souphttpsrc`. Use the HTTP form of
  the URL when adding DI.fm streams. ShoutCast and HLS streams work
  with HTTPS as expected.
- **SmartScreen friction:** The installer is not code-signed (deferred
  to a future phase). On first run Windows SmartScreen will warn
  "Windows protected your PC"; click "More info" → "Run anyway".
  This is one-time per machine.
- **AUMID requires Start Menu shortcut:** the SMTC overlay (Now Playing
  flyout) only shows the friendly "MusicStreamer" name when launched
  via the installed Start Menu shortcut, which carries the
  `org.lightningjim.MusicStreamer` AppUserModelID. Bare
  `python -m musicstreamer` from a dev env shows "Unknown app" —
  expected behavior, not a bug. (Phase 43.1 finding.)

## File map

| File                       | Role                                                 |
| -------------------------- | ---------------------------------------------------- |
| `MusicStreamer.spec`       | PyInstaller bundle definition (onedir, Qt+GStreamer) |
| `runtime_hook.py`          | Sets `GIO_EXTRA_MODULES`, `GI_TYPELIB_PATH`, `GST_PLUGIN_SCANNER` |
| `build.ps1`                | Top-level driver: pre-flight → guards → PyInstaller → Inno Setup → diag |
| `MusicStreamer.iss`        | Inno Setup installer script (per-user, AUMID shortcut) |
| `EULA.txt`                 | Short notice + third-party attributions              |
| `icons/MusicStreamer.ico`  | Multi-resolution Windows icon (16/32/48/64/128/256)  |
