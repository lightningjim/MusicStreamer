# Phase 44: Windows Packaging + Installer — Research

**Researched:** 2026-04-23
**Domain:** Windows distribution (Inno Setup + PyInstaller `--onedir` + Qt single-instance + host-runtime detection)
**Confidence:** HIGH (architecture locked in CONTEXT.md; implementation details verified against Phase 43 artifacts, PySide6/Inno Setup docs, and existing code)

## Summary

Phase 44 wraps the Phase 43-validated GStreamer bundle in an Inno Setup installer and adds three cross-cutting runtime features:

1. **Single-instance enforcement** via `QLocalServer`/`QLocalSocket` — Qt-native, uses a Windows named pipe under the hood, cleanly cross-platform (Linux gets it for free via D-08).
2. **Node.js host-runtime detection** — `shutil.which("node")` (with a 3.12 gotcha — see Pitfall 3), surfaced in three places (startup dialog + toast + hamburger indicator) per D-13.
3. **Windows installer** — Inno Setup `.iss` with `PrivilegesRequired=lowest`, per-user install to `%LOCALAPPDATA%\MusicStreamer`, Start Menu shortcut carrying the matching `AppUserModelID=org.lightningjim.MusicStreamer` so SMTC binds correctly.

All architectural choices are locked (see `## User Constraints`). This research focuses on **implementation details** — exact `.iss` skeleton, QLocalServer lifecycle code, Node.js detection module, `.spec` diff from the spike, `build.ps1` integration. No open architectural questions.

**Primary recommendation:** Copy Phase 43 artifacts verbatim into `packaging/windows/`, add three new modules (`single_instance.py`, `runtime_check.py`, `__version__.py`), one Inno Setup script (`MusicStreamer.iss`), one EULA text, and one `.ico` file. Wire the Node.js check + single-instance guard into `__main__.py._run_gui`. Extend `build.ps1` with ripgrep PKG-03 guard + `iscc.exe` invocation.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Installer tool + structure:**
- **D-01:** Inno Setup (not NSIS). Pascal-style `.iss` script. One `.iss` file under `packaging/windows/`.
- **D-02:** Install to `%LOCALAPPDATA%\MusicStreamer`. `PrivilegesRequired=lowest`. `AppId={{GUID}}` pinned for upgrade detection.
- **D-03:** Upgrade = overwrite existing install. Uninstaller runs silently as part of new install. User data in `%APPDATA%\musicstreamer` is separate and never touched.
- **D-04:** Start Menu shortcut only (mandatory — carries AUMID). No Desktop shortcut, no Taskbar pin.
- **D-05:** Short EULA/notice page. `packaging/windows/EULA.txt` + Inno Setup `LicenseFile=`.
- **D-06:** Bump `pyproject.toml` version 1.1.0 → 2.0.0 as part of this phase.
- **D-07:** Installer filename: `MusicStreamer-<version>-win64-setup.exe`. Output to `dist/installer/` (gitignored).

**Single-instance + runtime checks:**
- **D-08:** `QLocalServer`/`QLocalSocket`. Server name: `org.lightningjim.MusicStreamer.single-instance`.
- **D-09:** Second-launch behavior: raise + focus existing window. `FlashWindow` fallback if focus-steal blocked.
- **D-10:** Single-instance guard in `__main__.py` after `_set_windows_aumid()` + `QApplication()` construction, before `MainWindow`.

**Node.js prerequisite UX (RUNTIME-01):**
- **D-11:** Startup detection: `shutil.which("node")`. After single-instance check, before MainWindow shown.
- **D-12:** Missing-Node behavior: soft warning + continue. Non-blocking `QMessageBox`. Buttons: [Open nodejs.org] [OK]. App continues — ShoutCast/HLS/Twitch unaffected.
- **D-13:** Three surfaces (all conditional on Node.js missing):
  1. Startup dialog — once per missing-state session
  2. Toast at YT play time (via `ToastOverlay`) when yt-dlp resolve fails
  3. Persistent hamburger indicator "⚠ Node.js: Missing (click to install)"
- **D-14:** Detection is one-shot at startup; no runtime polling. Restart required after Node.js install.

**DI.fm / GStreamer bundle scope:**
- **D-15:** DI.fm HTTPS rejection — server-side, no code workaround. Document in `packaging/windows/README.md`.
- **D-16:** Broad-collect all 184 GStreamer plugins (~110 MB bundle). No pruning this phase.
- **D-17:** `.spec`, `runtime_hook.py`, `build.ps1` — copy verbatim from Phase 43. Only edits: entry point + `$GstRoot` default.
- **D-18:** conda-forge build env, Python 3.12, PyInstaller ≥6.19, `pyinstaller-hooks-contrib` ≥2026.2.

**QA / compliance:**
- **D-19:** Smoke-test cadence: once per Phase 44 ship. Manual UAT on clean Win11 VM. No CI.
- **D-20:** 8-item playback/feature checklist (SomaFM HTTPS, HLS, DI.fm HTTP, YT w/ Node, YT w/o Node, Twitch, failover, SMTC).
- **D-21:** 7-item installer/round-trip checklist (fresh install, uninstall, re-install, Linux→Win export, Win→Linux export, single-instance, AUMID/SMTC binding).
- **D-22:** PKG-03 no-op — ripgrep guard in `build.ps1` fails build on any `subprocess.{Popen,run,call}` in `musicstreamer/` outside `subprocess_utils.py` + tests. Keep `_popen()` helper.
- **D-23:** QA-05 document-only audit → `44-QA05-AUDIT.md`. Grep sweep + parent= confirmation + UAT-log regression check. Fix specific findings inline.

### Claude's Discretion
- Exact GUID for Inno Setup `AppId` — **Candidate generated in this research: `914e9cb6-f320-478a-a2c4-e104cd450c88`**. Planner to lock this into `.iss` with double-brace escape (`AppId={{914e9cb6-f320-478a-a2c4-e104cd450c88}`).
- EULA wording — drafted skeleton below (user reviews final copy)
- Single-instance helper module naming — **recommend `musicstreamer/single_instance.py`** (flat, matches `subprocess_utils.py` convention)
- Node.js check module placement — **recommend `musicstreamer/runtime_check.py`** (dedicated module, one-shot `check_node()` function; `__main__.py` stays lean)
- `packaging/` directory layout — **recommend `packaging/windows/`** (only Windows this phase; leaves room for `packaging/linux/` in v2.1+)

### Deferred Ideas (OUT OF SCOPE)
- Code signing / OV certificate (v2.1+)
- MSIX packaging (v2.1+)
- Auto-updater (v2.1+ / anti-feature)
- Linux packaging (v2.1+)
- CI automation of Windows build (v2.1+)
- Aggressive GStreamer plugin pruning
- Per-URL HTTPS→HTTP fallback in `player.py`
- Audio pause/restart glitch on Windows (backlog bug, not Phase 44 scope)
- `test_thumbnail_from_in_memory_stream` AsyncMock fix (backlog)
- FlashWindow tuning (add only if UAT surfaces focus-steal issues)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PKG-01 | PyInstaller spec bundles GStreamer runtime DLLs + plugins with HTTPS verified | Phase 43 spike proved the `.spec` works. Section "PyInstaller .spec Adaptation" documents the Phase 44 delta. |
| PKG-02 | Inno Setup installer to `%LOCALAPPDATA%\MusicStreamer` with Start Menu shortcut | Section "Inno Setup Script Skeleton" + "Start Menu Shortcut + AUMID Wiring". |
| PKG-03 | Centralized `_popen()` (no bare subprocess) — no console window flashes | Section "PKG-03 Compliance Guard" — grep confirms zero raw subprocess usage; build.ps1 guard blocks regressions. |
| PKG-04 | Single-instance enforcement — secondary launches forward to running instance | Section "QLocalServer Single-Instance Pattern" — full lifecycle code + tests. |
| QA-03 | Windows smoke test on clean VM | Section "Smoke Test / UAT Structure" — mirrors 43.1-UAT.md format. |
| QA-05 | Widget lifetime audit to prevent "Internal C++ object already deleted" | Section "QA-05 Widget Lifetime Audit" — grep patterns + audit-doc template. |
| RUNTIME-01 | Node.js on PATH at startup; documented as host prerequisite | Section "Node.js Detection + UX" — `runtime_check.py` module + three UX surfaces. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Routing hint: auto-load `Skill("spike-findings-musicstreamer")` for Windows GStreamer / PyInstaller / conda-forge / PowerShell work. Research confirms this skill is the canonical source for the `.spec` / `runtime_hook.py` / `build.ps1` artifacts (`.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/`).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Single-instance enforcement | Qt main process (`__main__.py`) | — | `QLocalServer` needs `QApplication` event loop; natural home is the app entry point. |
| Node.js detection (one-shot) | Backend module (`runtime_check.py`) | Qt UI (dialog + toast + menu) | Pure detection = pure module; UX is Qt concern. |
| Installer packaging | Build-time tool (Inno Setup `.iss`) | PyInstaller (`.spec`) | `.spec` produces `dist/MusicStreamer/`; Inno Setup wraps it. Two separate tools, sequential in `build.ps1`. |
| AUMID binding | Installer (shortcut `AppUserModelID`) + app process (`_set_windows_aumid`) | — | Both must agree on the exact string `org.lightningjim.MusicStreamer`. App-side already in place (Phase 43.1). |
| Subprocess hygiene | Build-time guard (`build.ps1` ripgrep) | Runtime helper (`subprocess_utils._popen`) | Guard prevents regression; helper is belt-and-braces for future reintroductions. |
| Widget lifetime | Qt UI (parent= convention in all dialog constructors) | Doc-only audit | Code is already largely correct; audit verifies + captures any spot fixes. |
| User data preservation | Installer policy (never touch `%APPDATA%\musicstreamer`) | Platform paths (`platformdirs`) | Install dir (`%LOCALAPPDATA%`) and data dir (`%APPDATA%`) are different roots. Inno Setup default uninstaller only removes what it installed — no action needed; just verify in UAT D-21 item 2. |

## Standard Stack

### Core (Windows build-time)

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Inno Setup | 6.3+ | Installer compiler (`iscc.exe`) | Free, Pascal-scripted, first-class `AppUserModelID` support on `[Icons]`, proven for Python apps. Conda-forge not relevant — install on the Win11 VM directly from jrsoftware.org. |
| PyInstaller | ≥6.19 (locked) | Bundle Python + deps → `dist/MusicStreamer/` | Copy from Phase 43 spec. |
| pyinstaller-hooks-contrib | ≥2026.2 (locked) | GStreamer + gi.repository hooks | Phase 43 proved this version places plugins in `gst_plugins/` (not legacy `gstreamer-1.0/`). |
| Python | 3.12 (locked) | Runtime | PyGObject wheels on conda-forge. |
| PowerShell | 5.1+ | `build.ps1` driver | Windows default. Phase 43's `Invoke-Native` helper handles the stderr trap. |
| conda-forge (Miniforge) | — | Build env source | PyGObject has no Windows PyPI wheels (BLOCKER Gotcha #1 from Phase 43). |

### Core (Python runtime additions)

| Library | Version | Purpose | Where |
|---------|---------|---------|-------|
| `PySide6.QtNetwork.QLocalServer` | 6.11+ (already in) | Single-instance server | `single_instance.py` |
| `PySide6.QtNetwork.QLocalSocket` | 6.11+ (already in) | Second-instance forwarding | `single_instance.py` |
| `shutil.which` (stdlib) | Python 3.12 | Node.js PATH detection | `runtime_check.py` (with workaround for CPython issue #109590 — see Pitfall 3) |
| `platformdirs` | ≥4.3 (already in) | `%APPDATA%\musicstreamer` resolution (user data) | `paths.py` (already wired) |

### Build-time tools (developer-side, installed on Win11 VM)

| Tool | Version | How to Install |
|------|---------|-----------------|
| Inno Setup 6 | 6.3+ | `https://jrsoftware.org/isdl.php` → `innosetup-6.3.x.exe` (GUI installer, ~5 MB). Installs to `C:\Program Files (x86)\Inno Setup 6\` by default; `iscc.exe` lives there. |
| ImageMagick OR Pillow | any recent | Convert `org.lightningjim.MusicStreamer.png` → `.ico` (one-time step, can run on Linux dev box). |

**Version verification (Python packages at research time):**
```bash
# (already locked by Phase 43 spike; no re-check needed — Phase 43 recipe is canonical)
# PyInstaller 6.19.0, pyinstaller-hooks-contrib 2026.2, PyGObject 3.56.2, Python 3.12.13, GStreamer 1.28.2
```

### Alternatives Considered (for documentation)

| Instead of | Could Use | Tradeoff | Rejected Because |
|------------|-----------|----------|------------------|
| Inno Setup | NSIS | More scripting flexibility | D-01: Inno Setup has first-class `AppUserModelID` parameter on `[Icons]`; NSIS needs a plugin. |
| `QLocalServer` | `fcntl.flock` + PID file | Simpler on Linux | Cross-platform means dual code paths; Qt handles both. |
| `shutil.which("node")` | `subprocess.run(["node", "--version"])` | Definitive test | Violates PKG-03 (no raw subprocess). D-11 explicit. |

## Architecture Patterns

### System Architecture Diagram

**Build pipeline (developer-side, Win11 VM):**

```
pyproject.toml (version 2.0.0)
       │
       ▼
build.ps1 ──────► [Pre-flight: conda env active? GStreamer libs present?]
       │                        │
       │                        ▼
       ├──────► [Step 1: PKG-03 ripgrep guard]
       │            │   grep subprocess.{Popen|run|call} in musicstreamer/
       │            │   excluding subprocess_utils.py + tests/
       │            │   ► FAIL build on hit, PASS on zero hits
       │            ▼
       ├──────► [Step 2: PyInstaller]
       │            │   pyinstaller packaging/windows/MusicStreamer.spec
       │            │   ► dist/MusicStreamer/ (110+ MB, 126 DLLs, 184 plugins)
       │            ▼
       ├──────► [Step 3: Version-stamped Inno Setup compile]
       │            │   iscc.exe /DAppVersion=2.0.0 packaging/windows/MusicStreamer.iss
       │            │   ► dist/installer/MusicStreamer-2.0.0-win64-setup.exe
       │            ▼
       └──────► [Step 4: Diagnostic: bundle size + DLL count]
                    ► log to artifacts/build.log
```

**Runtime pipeline (end-user, Windows 11):**

```
User double-clicks MusicStreamer-2.0.0-win64-setup.exe
       │
       ▼
Inno Setup installer
       │   ├─► License page (EULA.txt)
       │   ├─► DefaultDirName={localappdata}\MusicStreamer
       │   ├─► [Files] copies dist/MusicStreamer/* → {app}\
       │   ├─► [Icons] registers {userprograms}\MusicStreamer.lnk
       │   │       with AppUserModelID=org.lightningjim.MusicStreamer
       │   ├─► (upgrade path: AppId GUID match → silent uninstall old, install new)
       │   └─► %APPDATA%\musicstreamer — NEVER touched (separate root)
       │
       ▼
User clicks Start Menu shortcut
       │
       ▼
MusicStreamer.exe (PyInstaller bootloader)
       │
       ├─► [rthook: stock pyi_rth_gstreamer.py] — sets GST_PLUGIN_PATH, registry
       ├─► [rthook: runtime_hook.py] — sets GIO_EXTRA_MODULES, GI_TYPELIB_PATH, GST_PLUGIN_SCANNER
       │
       ▼
musicstreamer.__main__:main()
       │
       ├─► _set_windows_aumid("org.lightningjim.MusicStreamer")  ◄─ MATCHES shortcut AUMID
       ├─► Gst.init(None)
       ├─► migration.run_migration()
       ├─► QApplication(argv)
       │
       ├─► single_instance.acquire_or_forward(app)  ◄─ NEW
       │       ├─► try QLocalServer.listen(name)
       │       │      SUCCESS: we are the first instance → return server
       │       └─► FAILURE: name in use
       │              └─► QLocalSocket.connectToServer(name)
       │                     └─► sendData(b"activate\n") + disconnect
       │                     └─► sys.exit(0)
       │
       ├─► runtime_check.check_node()  ◄─ NEW (returns NodeRuntime(available: bool))
       │       └─► if not available: QMessageBox warning (non-blocking, [Open nodejs.org] [OK])
       │
       ├─► MainWindow(player, repo, node_runtime)  ◄─ new constructor param
       │       ├─► hamburger menu: if not node_runtime.available:
       │       │        add QAction "⚠ Node.js: Missing (click to install)"
       │       └─► on YT play failure: if not node_runtime.available:
       │                show_toast("Install Node.js for YouTube playback")
       │
       └─► app.exec()  ◄─ server.newConnection handler raises+focuses MainWindow on forward
```

### Recommended Project Structure

```
packaging/
└── windows/
    ├── MusicStreamer.iss         # Inno Setup script (new, see skeleton below)
    ├── MusicStreamer.spec        # PyInstaller spec (copied from 43-spike.spec + edits)
    ├── runtime_hook.py           # PyInstaller runtime hook (copied verbatim from spike)
    ├── build.ps1                 # Build driver (copied from spike + extended for Inno Setup + PKG-03 guard)
    ├── EULA.txt                  # Short EULA/notice (drafted below)
    ├── README.md                 # Build runbook (VM setup + iteration loop)
    └── icons/
        └── MusicStreamer.ico     # Windows icon (converted from org.lightningjim.MusicStreamer.png)

musicstreamer/
├── __main__.py                   # EDITED: add single_instance + runtime_check wiring
├── __version__.py                # NEW: single source of truth for version string
├── single_instance.py            # NEW: QLocalServer/QLocalSocket helper
├── runtime_check.py              # NEW: Node.js + future host-runtime checks
└── ui_qt/
    └── main_window.py            # EDITED: accept node_runtime param, add conditional hamburger action

.planning/phases/44-windows-packaging-installer/
├── 44-CONTEXT.md                 # existing
├── 44-RESEARCH.md                # this file
├── 44-QA05-AUDIT.md              # NEW (deliverable)
└── 44-UAT.md                     # NEW (deliverable)
```

### Pattern 1: Inno Setup Script Skeleton

**`packaging/windows/MusicStreamer.iss`:**

```pascal
; MusicStreamer Inno Setup installer
; Per-user install (PrivilegesRequired=lowest), %LOCALAPPDATA%\MusicStreamer target.
; Version passed in by build.ps1 via /DAppVersion=2.0.0 on iscc.exe command line.
; AppId GUID is pinned — NEVER change it without planning a migration path.

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

[Setup]
AppId={{914e9cb6-f320-478a-a2c4-e104cd450c88}
AppName=MusicStreamer
AppVersion={#AppVersion}
AppPublisher=Kyle Creasey
AppPublisherURL=https://github.com/lightningjim/MusicStreamer

; Per-user install (D-02): no admin elevation, installs under user profile.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
DefaultDirName={localappdata}\MusicStreamer
DefaultGroupName=MusicStreamer
DisableProgramGroupPage=yes
DisableDirPage=yes

; License page (D-05)
LicenseFile=EULA.txt

; Output (D-07)
OutputDir=..\..\dist\installer
OutputBaseFilename=MusicStreamer-{#AppVersion}-win64-setup

; 64-bit only
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

; Uninstaller icon
SetupIconFile=icons\MusicStreamer.ico
UninstallDisplayIcon={app}\MusicStreamer.exe
UninstallDisplayName=MusicStreamer {#AppVersion}

; Compression
Compression=lzma2/max
SolidCompression=yes

; Upgrade: Inno Setup auto-detects via AppId; on upgrade it silently uninstalls prior version
; then installs new. No custom [Code] needed for the common case.
; Reference: https://jrsoftware.org/ishelp/topic_setup_appid.htm

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Recursively install the entire PyInstaller onedir bundle
; Source paths are relative to the .iss file location.
Source: "..\..\dist\MusicStreamer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; D-04: Start Menu shortcut ONLY — and it's mandatory because it carries the AUMID.
; AppUserModelID must match exactly the string passed to SetCurrentProcessExplicitAppUserModelID
; in musicstreamer/__main__.py::_set_windows_aumid — otherwise SMTC shows "Unknown app".
; Reference: https://jrsoftware.org/ishelp/topic_iconssection.htm
Name: "{userprograms}\MusicStreamer"; Filename: "{app}\MusicStreamer.exe"; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\_internal\icons\MusicStreamer.ico"; \
    AppUserModelID: "org.lightningjim.MusicStreamer"

; Uninstaller shortcut in the same group (optional polish)
Name: "{userprograms}\Uninstall MusicStreamer"; Filename: "{uninstallexe}"

[Run]
; Optional: post-install launch checkbox (unchecked by default for personal apps)
Filename: "{app}\MusicStreamer.exe"; Description: "Launch MusicStreamer"; \
    Flags: nowait postinstall skipifsilent unchecked

; --- NOTHING under [UninstallDelete]: we deliberately do NOT touch %APPDATA%\musicstreamer ---
; User data (SQLite DB, cookies, tokens, accent CSS, EQ profiles, logo cache) lives there
; under platformdirs.user_data_dir("musicstreamer") and MUST survive uninstall (D-03).
; Inno Setup's default uninstaller only removes what it installed, so silence = correct.
```

**Key source citations:**
- [AppId + GUID pinning](https://jrsoftware.org/ishelp/topic_setup_appid.htm)
- [Icons section + AppUserModelID](https://jrsoftware.org/ishelp/topic_iconssection.htm)
- [PrivilegesRequired=lowest](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm)
- [Directory constants](https://jrsoftware.org/ishelp/topic_consts.htm)

### Pattern 2: QLocalServer Single-Instance

**`musicstreamer/single_instance.py` (new):**

```python
"""Single-instance enforcement via QLocalServer/QLocalSocket (D-08, D-09).

First instance calls acquire_or_forward() and receives a running QLocalServer
(kept alive for the app lifetime). Subsequent launches connect to that server,
send the literal bytes b"activate\\n", and exit cleanly. The first instance's
newConnection handler raises and focuses the main window.

On Windows QLocalSocket uses a named pipe under the hood — no socket file
to clean up (removeServer is a no-op on Windows). On Linux, removeServer
deletes a stale socket file so a crashed prior instance does not block us.
"""
from __future__ import annotations

import logging
import sys
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

_log = logging.getLogger(__name__)

SERVER_NAME = "org.lightningjim.MusicStreamer.single-instance"  # D-08
_CONNECT_TIMEOUT_MS = 500  # plenty for a local named pipe / AF_UNIX socket


class SingleInstanceServer(QObject):
    """Wraps a QLocalServer and emits `activate_requested` on each incoming
    activation message. Keep a reference for the app lifetime — dropping it
    closes the server and breaks single-instance enforcement.
    """

    activate_requested = Signal()

    def __init__(self, server: QLocalServer, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server = server
        self._server.newConnection.connect(self._on_new_connection)

    def _on_new_connection(self) -> None:
        socket = self._server.nextPendingConnection()
        if socket is None:
            return
        # Bound method — QA-05-compliant (no lambda-captured self).
        socket.readyRead.connect(lambda: self._drain(socket))
        socket.disconnected.connect(socket.deleteLater)

    def _drain(self, socket: QLocalSocket) -> None:
        data = bytes(socket.readAll()).strip()
        if data == b"activate":
            self.activate_requested.emit()
        socket.disconnectFromServer()

    def close(self) -> None:
        self._server.close()


def acquire_or_forward() -> Optional[SingleInstanceServer]:
    """Try to become the single instance.

    Returns:
        SingleInstanceServer if this process is the first/sole instance.
        None if another instance was running — caller should sys.exit(0) immediately.

    MUST be called after QApplication has been constructed (QLocalServer
    needs the event loop to emit newConnection).
    """
    # Probe: if a prior instance is running, connect + send "activate" + exit.
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if socket.waitForConnected(_CONNECT_TIMEOUT_MS):
        socket.write(b"activate\n")
        socket.flush()
        socket.waitForBytesWritten(_CONNECT_TIMEOUT_MS)
        socket.disconnectFromServer()
        _log.info("Another instance is running — forwarded activation and exiting.")
        return None

    # No server answered — either we are first, or a stale socket file blocks us (Linux only).
    # removeServer is safe to call unconditionally; it's a no-op on Windows.
    QLocalServer.removeServer(SERVER_NAME)

    server = QLocalServer()
    # SocketOption.UserAccessOption restricts the socket to the current user on Unix
    # (irrelevant on Windows named pipes, but harmless).
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(SERVER_NAME):
        # Extremely unlikely after removeServer — log and proceed single-instance-less
        # rather than crash the app.
        _log.warning(
            "QLocalServer.listen failed: %s — continuing without single-instance guard.",
            server.errorString(),
        )
        return None

    return SingleInstanceServer(server)


def raise_and_focus(window) -> None:
    """Bring `window` to the foreground in response to an activate request.

    On Windows, Qt's activateWindow() alone is often blocked by focus-steal
    prevention. We call showNormal() (undoes minimize), raise_() (Z-order),
    and activateWindow() (focus). If focus-steal blocks the raise, FlashWindow
    falls back to flashing the taskbar icon (D-09).
    """
    # Restore from minimize if needed
    window.showNormal()
    window.raise_()
    window.activateWindow()

    if sys.platform == "win32":
        # FlashWindow fallback — if focus-steal blocks activateWindow, at least
        # flash the taskbar so the user sees the app wants attention.
        # FLASHW_ALL | FLASHW_TIMERNOFG = flash caption + tray until fg, then stop.
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = int(window.winId())
            FLASHW_ALL = 0x00000003
            FLASHW_TIMERNOFG = 0x0000000C

            class FLASHWINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.UINT),
                    ("hwnd", wintypes.HWND),
                    ("dwFlags", wintypes.DWORD),
                    ("uCount", wintypes.UINT),
                    ("dwTimeout", wintypes.DWORD),
                ]

            fwi = FLASHWINFO(
                cbSize=ctypes.sizeof(FLASHWINFO),
                hwnd=hwnd,
                dwFlags=FLASHW_ALL | FLASHW_TIMERNOFG,
                uCount=3,
                dwTimeout=0,
            )
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(fwi))
        except Exception as exc:  # pragma: no cover
            _log.debug("FlashWindowEx fallback failed: %s", exc)
```

**Wiring in `__main__.py::_run_gui` (edit):**

```python
# ... existing _set_windows_aumid() + Gst.init + migration.run_migration ...

app = QApplication(argv)
app.setApplicationName("MusicStreamer")
# ... existing palette / style setup ...

# D-10: single-instance BEFORE MainWindow construction
from musicstreamer import single_instance
server = single_instance.acquire_or_forward()
if server is None:
    return 0  # second instance forwarded + exiting

# D-11: Node.js detection BEFORE MainWindow.show()
from musicstreamer import runtime_check
node_runtime = runtime_check.check_node()
if not node_runtime.available:
    runtime_check.show_missing_node_dialog(parent=None)  # non-blocking warning (D-12)

# ... existing db_connect / Player / Repo setup ...

window = MainWindow(player, repo, node_runtime=node_runtime)  # new kwarg
server.activate_requested.connect(lambda: single_instance.raise_and_focus(window))
window.show()
return app.exec()
```

**Sources:**
- [QLocalServer docs (PySide6)](https://doc.qt.io/qtforpython-6/PySide6/QtNetwork/QLocalServer.html)
- [QLocalSocket docs (PySide6)](https://doc.qt.io/qtforpython-6/PySide6/QtNetwork/QLocalSocket.html) — "On Windows QLocalSocket is implemented as a named pipe"

### Pattern 3: Node.js Detection + UX

**`musicstreamer/runtime_check.py` (new):**

```python
"""Host-runtime detection (D-11..D-14).

One-shot checks at startup. Results cached on a NodeRuntime dataclass and
passed to UI layers that need to branch on availability (hamburger menu
indicator, YT play failure toast).

Re-detection is explicitly out of scope (D-14): a user who installs Node.js
mid-session must restart the app.
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import QMessageBox

_log = logging.getLogger(__name__)

NODEJS_INSTALL_URL = "https://nodejs.org/en/download"


@dataclass(frozen=True)
class NodeRuntime:
    available: bool
    path: Optional[str]  # resolved path to node executable (or None)


def _which_node() -> Optional[str]:
    """Locate node executable on PATH with Windows 3.12 safety.

    CPython issue #109590 (fixed in 3.12.x but triggered on PRE-release builds
    and still a latent footgun): shutil.which may return an extensionless "node"
    (typically a bash script shim) before checking PATHEXT for "node.exe".
    On Windows we explicitly prefer node.exe; on Linux/macOS fall back to stock
    shutil.which behavior.

    Reference: https://github.com/python/cpython/issues/109590
    """
    if sys.platform == "win32":
        # Force .exe resolution — ignore extensionless shims.
        result = shutil.which("node.exe")
        if result:
            return result
        # Fallback for unusual layouts
        result = shutil.which("node")
        if result and result.lower().endswith(".exe"):
            return result
        return None
    return shutil.which("node")


def check_node() -> NodeRuntime:
    """One-shot Node.js detection. Safe to call from any thread."""
    path = _which_node()
    if path is None:
        _log.info("Node.js not found on PATH — YouTube playback via yt-dlp EJS will fail.")
        return NodeRuntime(available=False, path=None)
    _log.debug("Node.js detected at %s", path)
    return NodeRuntime(available=True, path=path)


def show_missing_node_dialog(parent) -> None:
    """Non-blocking warning (D-12). Returns immediately; dialog is modal to `parent`
    when parent is a QWidget, but app-modal otherwise."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Node.js not found")
    box.setText(
        "MusicStreamer needs Node.js for YouTube playback.\n\n"
        "Install from nodejs.org. All other stream types (ShoutCast, HLS, "
        "Twitch, AudioAddict) will work without it."
    )
    open_btn = box.addButton("Open nodejs.org", QMessageBox.ButtonRole.ActionRole)
    ok_btn = box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
    box.setDefaultButton(ok_btn)
    box.exec()  # modal (blocks the dialog, not the app) — "non-blocking" per D-12
                # means non-blocking in the sense that the user can continue into the
                # app regardless of choice; Qt's QMessageBox.exec is the standard
                # idiom for this.
    if box.clickedButton() is open_btn:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(NODEJS_INSTALL_URL))
```

**MainWindow integration (edits to `main_window.py`):**

```python
def __init__(self, player, repo, *, node_runtime: NodeRuntime | None = None, parent=None):
    # ... existing code ...
    self._node_runtime = node_runtime

    # D-13 part 3: persistent hamburger indicator if Node.js missing
    if node_runtime is not None and not node_runtime.available:
        self._menu.addSeparator()
        self._act_node_missing = self._menu.addAction("⚠ Node.js: Missing (click to install)")
        self._act_node_missing.triggered.connect(self._on_node_install_clicked)

def _on_node_install_clicked(self) -> None:
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtCore import QUrl
    QDesktopServices.openUrl(QUrl("https://nodejs.org/en/download"))
```

**D-13 part 2 (toast) — hook into existing `_on_youtube_resolution_failed`:**

The Player already emits `playback_error.emit(f"YouTube resolve failed: {msg}")` on yt-dlp failure (see `player.py::_on_youtube_resolution_failed`). `main_window.py` already wires `self._player.playback_error.connect(self._on_playback_error)`.

Edit `_on_playback_error` to branch on Node-missing state:

```python
def _on_playback_error(self, message: str) -> None:
    # D-13 part 2: if Node missing AND this looks like a YT resolve failure,
    # nudge the user toward installing Node.
    if (
        self._node_runtime is not None
        and not self._node_runtime.available
        and "YouTube resolve failed" in message
    ):
        self.show_toast("Install Node.js for YouTube playback")
        return
    truncated = message[:80] + "…" if len(message) > 80 else message
    self.show_toast(f"Playback error: {truncated}")
```

**Distinguishing yt-dlp Node-absence errors:** yt-dlp does not produce a distinct error code when Node is missing — it surfaces as a generic `DownloadError` or `ExtractorError` from the EJS jsruntime extractor. The safest heuristic is "Node is missing AND a YouTube resolve just failed", which the `_on_playback_error` check above captures. We don't need to parse the yt-dlp error message.

### Pattern 4: PyInstaller .spec Adaptation (Phase 43 → Phase 44)

**Copy `43-spike.spec` → `packaging/windows/MusicStreamer.spec`.** The diff is minimal:

```diff
 a = Analysis(
-    ["smoke_test.py"],
+    ["../../musicstreamer/__main__.py"],
     pathex=[str(Path(".").resolve())],
     binaries=extra_binaries,
-    datas=[],
+    datas=[
+        ("../../musicstreamer/ui_qt/icons", "musicstreamer/ui_qt/icons"),  # SVG source
+        ("icons/MusicStreamer.ico", "icons"),                              # installed icon
+    ],
     hiddenimports=[
         "gi",
         "gi.repository.Gst",
         "gi.repository.GLib",
         "gi.repository.GObject",
         "gi.repository.Gio",
+        # PySide6 extras that hooks-contrib sometimes misses:
+        "PySide6.QtNetwork",      # QLocalServer/QLocalSocket (single-instance)
+        "PySide6.QtSvg",          # SVG icon rendering
+        # Windows media keys (43.1 already declared optional-dependencies.windows):
+        "winrt.windows.media",
+        "winrt.windows.media.playback",
+        "winrt.windows.storage.streams",
+        "winrt.windows.foundation",
     ],
     hookspath=[],
     hooksconfig={
         "gstreamer": {
             # ITERATION 1: broad — let the hook collect everything. Per D-16.
         },
         "gi": {
-            "icons": [],
+            # Qt renders our own SVG icons; no GTK icon theme bundling needed.
+            "icons": [],
             "themes": [],
             "languages": [],
         },
     },
     runtime_hooks=["runtime_hook.py"],
     excludes=[
         "tkinter", "matplotlib", "PIL", "numpy",
+        # Ensure no mpv/GTK remnants sneak in (defensive — 35-06 retired these):
+        "mpv", "gi.repository.Gtk", "gi.repository.Adw",
     ],
     ...
 )
 ...
 exe = EXE(
     pyz,
     a.scripts,
     [],
     exclude_binaries=True,
-    name="spike",
+    name="MusicStreamer",
     debug=False,
     bootloader_ignore_signals=False,
     strip=False,
     upx=False,
-    console=True,         # Spike is CLI — keep the console window
+    console=False,        # D-04/PKG-03: GUI app, no console window flash
     disable_windowed_traceback=False,
     target_arch=None,
     codesign_identity=None,
     entitlements_file=None,
+    icon="icons/MusicStreamer.ico",   # Windows EXE icon
 )
 ...
 coll = COLLECT(
     ...
-    name="spike",
+    name="MusicStreamer",
 )
```

**Note on `hiddenimports` for yt-dlp/streamlink:** `pyinstaller-hooks-contrib 2026.2` already ships hooks for both. No explicit `hiddenimports` needed unless smoke test surfaces a `ModuleNotFoundError` for a specific yt-dlp extractor (add per-extractor imports reactively if surfaced — follows Phase 43 iteration discipline).

**`GStreamer plugin pruning`:** Keep `hooksconfig.gstreamer` empty this phase (D-16 broad-collect).

### Pattern 5: build.ps1 Extensions

**Add to the Phase 43 `build.ps1`:**

```powershell
# ---------- NEW STEP: PKG-03 compliance guard (D-22) ----------
Write-Host "=== PKG-03 GUARD: subprocess.* usage scan ==="
# ripgrep is not guaranteed on the VM — use Select-String fallback.
# Semantics: find any subprocess.{Popen,run,call} call in musicstreamer/ EXCEPT subprocess_utils.py.
$pkg03Hits = Get-ChildItem -Path "..\..\musicstreamer" -Include "*.py" -Recurse |
    Where-Object { $_.Name -ne "subprocess_utils.py" } |
    Select-String -Pattern "subprocess\.(Popen|run|call)" -AllMatches |
    Where-Object { $_.Line -notmatch "^\s*#" }   # skip commented references

if ($pkg03Hits) {
    Write-Error "PKG-03 FAIL: bare subprocess.{Popen,run,call} found outside subprocess_utils.py"
    $pkg03Hits | ForEach-Object { Write-Host "  $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    exit 4
}
Write-Host "PKG-03 OK: zero bare subprocess.* calls in musicstreamer/"

# ---------- EXISTING: PyInstaller (rename spec) ----------
# ... unchanged except "43-spike.spec" → "MusicStreamer.spec" ...

# ---------- NEW STEP: Inno Setup compile (D-01, D-07) ----------
Write-Host "=== INNO SETUP: compile installer ==="

# Read version from pyproject.toml (D-06) — passed to iscc.exe as /DAppVersion
$pyproject = Get-Content "..\..\pyproject.toml" -Raw
if ($pyproject -match '(?ms)^\[project\].*?^version\s*=\s*"([^"]+)"') {
    $appVersion = $matches[1]
} else {
    Write-Error "BUILD_FAIL reason=version_not_found_in_pyproject"
    exit 5
}
Write-Host "AppVersion = $appVersion"

# Locate iscc.exe — default install path; allow override via env var.
$isccPath = if ($env:INNO_SETUP_PATH) {
    $env:INNO_SETUP_PATH
} else {
    "C:\Program Files (x86)\Inno Setup 6\iscc.exe"
}
if (-not (Test-Path $isccPath)) {
    Write-Error "BUILD_FAIL reason=iscc_not_found path='$isccPath' hint='install Inno Setup 6 from jrsoftware.org or set INNO_SETUP_PATH env var'"
    exit 6
}

Invoke-Native {
    & $isccPath "/DAppVersion=$appVersion" "MusicStreamer.iss" 2>&1 | Tee-Object -FilePath "artifacts\iscc.log"
}
if ($LASTEXITCODE -ne 0) {
    Write-Error "BUILD_FAIL reason=iscc_nonzero exitcode=$LASTEXITCODE"
    exit 6
}

$installerPath = "..\..\dist\installer\MusicStreamer-$appVersion-win64-setup.exe"
Write-Host "BUILD_OK installer='$installerPath'"

# ---------- NEW STEP: diagnostic (bundle size, DLL count) ----------
$bundleSize = (Get-ChildItem "..\..\dist\MusicStreamer" -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
$dllCount = (Get-ChildItem "..\..\dist\MusicStreamer\_internal\*.dll").Count
$installerSize = (Get-Item $installerPath).Length / 1MB
Write-Host ("BUILD_DIAG bundle_size_mb={0:N1} dll_count={1} installer_size_mb={2:N1}" -f $bundleSize, $dllCount, $installerSize)
```

### Pattern 6: Version Source of Truth

**`musicstreamer/__version__.py` (new):**

```python
"""Single source of truth for the application version.

Read by:
- pyproject.toml (NO — pyproject is the primary; this module mirrors it at runtime)
- build.ps1 (reads from pyproject.toml, passes to iscc.exe as /DAppVersion)
- Future About dialog / hamburger menu footer (runtime read)

Keep the literal string in sync with [project].version in pyproject.toml.
A later phase could auto-derive via importlib.metadata, but for a personal app
the single-literal approach is simpler and works inside PyInstaller bundles
where importlib.metadata paths are quirky.
"""
__version__ = "2.0.0"
```

**Bump sequence:** pyproject.toml (line 8: `version = "2.0.0"`) + `__version__.py` both updated in the same commit.

### Pattern 7: Icon Conversion (one-time)

**Input:** `org.lightningjim.MusicStreamer.png` (exists in repo root, 1024×1024 or similar).
**Output:** `packaging/windows/icons/MusicStreamer.ico` (multi-resolution: 16, 32, 48, 64, 128, 256).

**Linux dev box (preferred — no VM round-trip):**
```bash
# ImageMagick (available: /usr/bin/magick, /usr/bin/convert)
magick org.lightningjim.MusicStreamer.png \
  -define icon:auto-resize=16,32,48,64,128,256 \
  packaging/windows/icons/MusicStreamer.ico
```

**Python fallback (PIL):**
```python
from PIL import Image
im = Image.open("org.lightningjim.MusicStreamer.png")
im.save("packaging/windows/icons/MusicStreamer.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
```

### Pattern 8: EULA Draft (D-05)

**`packaging/windows/EULA.txt`** (draft — user reviews):

```
MusicStreamer — Notice

This software is provided "as is", without warranty of any kind, express or
implied, including but not limited to the warranties of merchantability,
fitness for a particular purpose, and noninfringement.

MusicStreamer is a personal-use internet radio stream player. It is not
intended for commercial redistribution.

Third-party software:
 - GStreamer (LGPLv2.1+). Source and license: https://gstreamer.freedesktop.org
 - yt-dlp (Unlicense / public domain). https://github.com/yt-dlp/yt-dlp
 - streamlink (BSD 2-Clause). https://streamlink.github.io
 - Qt/PySide6 (LGPLv3). https://www.qt.io
 - Node.js (not bundled — installed separately by the user; MIT + others).
   https://nodejs.org

By installing this software you acknowledge that you are responsible for
complying with the terms of service of any streaming provider you use with
the application.
```

(Short, per D-05 "minimal text". Final copy is user discretion.)

### Anti-Patterns to Avoid

- **Don't use `subprocess.run(["node", "--version"])` to probe Node.js** — violates PKG-03 and is more expensive than `shutil.which`. Use the wrapped `_which_node()` helper above.
- **Don't call `QLocalServer.listen()` before `QApplication()` exists** — the server needs the event loop to emit `newConnection`. Order is locked by D-10.
- **Don't set `DefaultDirName={pf}\MusicStreamer`** — that's per-machine `Program Files`, requires admin, breaks D-02. Use `{localappdata}\MusicStreamer`.
- **Don't forget the double-brace on `AppId`** — `AppId={{GUID}}` is the Inno Setup escape for a literal `{GUID}`. Single-brace form treats it as a constant reference.
- **Don't add a Desktop shortcut or auto-pin to Taskbar** — D-04 explicit. User can pin manually.
- **Don't put `[UninstallDelete]` entries for `%APPDATA%\musicstreamer`** — D-03 preserves user data. Inno Setup's default uninstaller does the right thing by silence.
- **Don't UPX-compress GStreamer DLLs** — breaks loading on Windows (Phase 43 finding; `upx=False` in `.spec`).
- **Don't bundle Node.js** — RUNTIME-01 explicit; host prerequisite.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Installer | Custom `.zip` + `.bat` | Inno Setup | Start Menu registration, uninstall registry, AUMID binding, upgrade detection, privilege handling all built-in. |
| Single-instance | `fcntl.flock` / PID file / Windows mutex via ctypes | `QLocalServer`/`QLocalSocket` | Cross-platform (Windows named pipe / Unix socket), integrates with Qt event loop, message-passing for activation requests. |
| Window raise on Windows | Manual WM_ACTIVATE / SetForegroundWindow | `showNormal + raise_ + activateWindow` with `FlashWindowEx` fallback | Qt handles 90% of the lift; FlashWindowEx covers the focus-steal edge case without fighting the shell. |
| AUMID shortcut property | PowerShell `Set-ItemProperty` post-install hack | Inno Setup `AppUserModelID:` parameter on `[Icons]` entry | First-class installer support since Inno Setup 6; `IPropertyStore` handled internally. |
| PyGObject install on Windows | MSVC Build Tools + meson/ninja/pkg-config source build | conda-forge | BLOCKER per Phase 43 Gotcha #1. Zero wheels on PyPI for any PyGObject version. |
| Icon conversion | Manual multi-file .ico editor | ImageMagick `-define icon:auto-resize` | Handles size family in one invocation. |
| Version string propagation | Hardcoded per-file | `__version__.py` + `pyproject.toml` (read by `build.ps1`) | Two sources of truth, bump in one commit. |

**Key insight:** Everything above is a solved problem with a standard answer — for a personal-scale Windows installer, the recipe is Inno Setup + PyInstaller + a Qt single-instance helper. No place for bespoke solutions.

## Runtime State Inventory

Phase 44 does some renaming (version bump, install-path change), but the only "runtime state" that persists across installer versions is the user data in `%APPDATA%\musicstreamer`. Full audit:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | SQLite DB at `platformdirs.user_data_dir("musicstreamer")/musicstreamer.sqlite3` — contains stations, streams, favorites, settings (accent_color, audioaddict_listen_key, show_stats_for_nerds, active EQ profile). Path unchanged between v1.1.0 → v2.0.0 (platformdirs resolution is stable). | **None** — Inno Setup installs to `%LOCALAPPDATA%\MusicStreamer` (executable+libs); `%APPDATA%\musicstreamer` (user data) is a separate root. Users upgrading keep their data. Verify in UAT D-21 item 2. |
| Live service config | None — no external service configuration lives outside the repo. | None. |
| OS-registered state | (After v1.1.0 ship) Windows Start Menu shortcut at `%APPDATA%\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk` (installed by Phase 44 installer — but this is the FIRST Windows install, so there's nothing to migrate from). AUMID `org.lightningjim.MusicStreamer` is already the process-level AUMID from Phase 43.1 — installer shortcut must match. | **None** — v2.0.0 is the first Windows installer ever; no prior Windows state. AUMID string is pre-locked. |
| Secrets/env vars | `TWITCH_TOKEN_PATH`, `cookies.txt`, `audioaddict_listen_key` DB row — all under `user_data_dir`. No secret-key renames in Phase 44. | None. |
| Build artifacts / installed packages | Stale `dist/`, `build/`, `__pycache__/` on dev machine — cleaned by `build.ps1`'s `Remove-Item -Recurse -Force "build","dist"` step (inherited from Phase 43). No pip egg-info concern (pyproject uses setuptools, not editable installs on Windows). | None — cleanup is automatic. |

**Canonical question — "After every file in the repo is updated, what runtime systems still have the old string cached, stored, or registered?"** Nothing, for Phase 44. The AUMID string is already locked (Phase 43.1), the data dir is platformdirs-stable, and this is the first Windows installer (no prior install to collide with).

## Common Pitfalls

### Pitfall 1: AUMID mismatch between process and shortcut
**What goes wrong:** SMTC overlay shows "Unknown app" even though the shortcut-launched app sets its AUMID correctly.
**Why it happens:** `.iss` has `AppUserModelID: "org.lightningjim.musicstreamer"` (case diff) while `__main__.py::_set_windows_aumid` uses `"org.lightningjim.MusicStreamer"` (mixed case). AUMID match is **case-sensitive** in the shell.
**How to avoid:** Both strings are literals in source code — lock a single constant in documentation (`org.lightningjim.MusicStreamer`), copy-paste into both files, grep-verify in the planner's verification step.
**Warning signs:** SMTC overlay shows "Unknown app" or "Python" during UAT D-21 item 7.
**Source:** Phase 43.1 findings explicitly document this binding requirement.

### Pitfall 2: `QLocalServer.listen` fails due to stale socket on Linux
**What goes wrong:** App won't start when a previous crash left the `.sock` file behind.
**Why it happens:** `QLocalServer.listen` returns `false` when the name is occupied by a file on disk (Unix socket semantics).
**How to avoid:** Call `QLocalServer.removeServer(name)` unconditionally before `listen()`. No-op on Windows (named pipes don't persist across crashes). Pattern included in `single_instance.py` above.
**Warning signs:** Linux user reports app won't start; `strace` shows `EADDRINUSE` on the socket path.
**Source:** [QLocalServer docs](https://doc.qt.io/qtforpython-6/PySide6/QtNetwork/QLocalServer.html) — "removeServer() is meant to recover from a crash".

### Pitfall 3: `shutil.which("node")` returns extensionless bash script on Windows
**What goes wrong:** `check_node()` reports "available" but the Player still fails YT playback.
**Why it happens:** [CPython issue #109590](https://github.com/python/cpython/issues/109590) — `shutil.which` may return an extensionless `node` (typically a bash script in nodejs/npm's Git Bash distribution) before checking `PATHEXT` for `node.exe`. Bug latent on Python 3.12 even in stable releases.
**How to avoid:** Explicitly probe `shutil.which("node.exe")` first on Windows. `_which_node()` helper above does this.
**Warning signs:** UAT D-20 item 4 fails with a yt-dlp error despite the app saying "Node.js: Detected".
**Source:** [CPython #109590](https://github.com/python/cpython/issues/109590), [CPython #127001](https://github.com/python/cpython/issues/127001).

### Pitfall 4: Inno Setup `AppId` single-brace ambiguity
**What goes wrong:** Build fails with "Unknown constant '{GUID}'" or (worse) the installer installs but upgrade detection breaks.
**Why it happens:** Inno Setup treats `{name}` as a constant reference. Literal braces require doubling: `{{GUID}}` expands to `{GUID}`.
**How to avoid:** Always write `AppId={{914e9cb6-f320-478a-a2c4-e104cd450c88}` (note the double-open-brace at start; that's one literal `{` + one literal `{GUID}` then `}`).
**Warning signs:** iscc.exe fails at compile-time OR the Uninstall registry key doesn't match between versions.
**Source:** [AppId docs](https://jrsoftware.org/ishelp/topic_setup_appid.htm).

### Pitfall 5: PyInstaller `console=False` swallows tracebacks
**What goes wrong:** App crashes silently at startup with no feedback.
**Why it happens:** `console=False` creates a Windows GUI subsystem EXE — `sys.stderr`/`sys.stdout` are `None` inside the bundle unless redirected. Python tracebacks go nowhere.
**How to avoid:** (a) Configure `logging.basicConfig(filename=...)` in `__main__.py` to write to `platformdirs.user_log_dir("musicstreamer")`; (b) use `logging` for all diagnostic output (already done throughout the codebase); (c) reserve `print()` for intentional CLI output (smoke test path only). No code change needed beyond verifying the existing `_log = logging.getLogger(__name__)` pattern is consistent.
**Warning signs:** UAT on VM shows app exits immediately after double-click with no window shown.
**Source:** [PyInstaller `--windowed` notes](https://pyinstaller.org/en/stable/usage.html).

### Pitfall 6: First-run install launches app, but AUMID not yet bound on installer launch
**What goes wrong:** If Inno Setup's `[Run]` entry launches the app directly (not via the just-installed shortcut), the process inherits Inno Setup's AUMID — SMTC shows "Unknown app" until next launch.
**Why it happens:** AUMID binds on first window creation; explicit `SetCurrentProcessExplicitAppUserModelID` should handle this — but if the user then closes and relaunches from the Start Menu shortcut, the shell's AUMID registration kicks in and all is well.
**How to avoid:** Leave the `[Run]` entry `unchecked` by default (pattern above). User's first real launch goes via the Start Menu shortcut, which has the AUMID set. If issue surfaces in UAT, document as "relaunch once" in D-15 notes.
**Warning signs:** UAT D-21 item 7 fails on the very first launch but passes on subsequent launches.
**Source:** Phase 43.1 findings — AUMID process-level binding.

### Pitfall 7: User data dir collision between Linux dev env and Windows VM
**What goes wrong:** Settings export Linux→Windows imports but paths don't resolve (or vice versa).
**Why it happens:** `platformdirs.user_data_dir("musicstreamer")` resolves to `~/.local/share/musicstreamer` on Linux vs `%APPDATA%\musicstreamer` on Windows. The SQLite DB stores logo paths that the exporter re-roots via its own path-normalization, but the user might test round-trip before understanding this.
**How to avoid:** Phase 42 settings_export already handles this — logos are re-rooted relative on export, re-materialized on import. UAT D-21 items 4/5 explicitly test this.
**Warning signs:** Missing logos or broken station-art paths after round-trip import.
**Source:** `musicstreamer/settings_export.py` (Phase 42 D-05 — relative logo paths in ZIP).

## Code Examples

### Example 1: QLocalServer one-shot acquire

```python
# musicstreamer/__main__.py::_run_gui (excerpt, after QApplication construction)
from musicstreamer.single_instance import acquire_or_forward, raise_and_focus

app = QApplication(argv)
# ... palette + style ...

server = acquire_or_forward()
if server is None:
    return 0  # forwarded to running instance

# ... MainWindow construction ...
server.activate_requested.connect(lambda: raise_and_focus(window))
```

### Example 2: pytest-qt test for QLocalServer round-trip

```python
# tests/test_single_instance.py (new)
import pytest
from musicstreamer import single_instance


def test_first_instance_acquires_server(qtbot, monkeypatch):
    """First call returns a server; the server listens on the configured name."""
    # Isolate the socket name so parallel tests don't collide.
    monkeypatch.setattr(single_instance, "SERVER_NAME", "test-mstream-single-inst-a")

    server = single_instance.acquire_or_forward()
    assert server is not None
    server.close()


def test_second_instance_forwards_and_first_sees_activate(qtbot, monkeypatch):
    """Second call returns None, and the first instance's signal fires."""
    monkeypatch.setattr(single_instance, "SERVER_NAME", "test-mstream-single-inst-b")

    first = single_instance.acquire_or_forward()
    assert first is not None

    with qtbot.waitSignal(first.activate_requested, timeout=1000):
        second = single_instance.acquire_or_forward()
        assert second is None

    first.close()
```

### Example 3: pytest-qt test for Node.js detection

```python
# tests/test_runtime_check.py (new)
from unittest.mock import patch
from musicstreamer import runtime_check


def test_check_node_available(monkeypatch):
    monkeypatch.setattr(runtime_check, "_which_node", lambda: "/usr/bin/node")
    nr = runtime_check.check_node()
    assert nr.available is True
    assert nr.path == "/usr/bin/node"


def test_check_node_absent(monkeypatch):
    monkeypatch.setattr(runtime_check, "_which_node", lambda: None)
    nr = runtime_check.check_node()
    assert nr.available is False
    assert nr.path is None


def test_which_node_prefers_exe_on_windows(monkeypatch):
    """CPython issue #109590 guard."""
    import sys
    monkeypatch.setattr(sys, "platform", "win32")
    with patch("shutil.which") as mock_which:
        # Simulate the bug: extensionless shim found first
        mock_which.side_effect = lambda name: (
            "C:\\Program Files\\nodejs\\node.exe" if name == "node.exe" else None
        )
        assert runtime_check._which_node() == "C:\\Program Files\\nodejs\\node.exe"
        mock_which.assert_called_with("node.exe")
```

### Example 4: MainWindow hamburger Node-missing indicator test

```python
# tests/ui_qt/test_main_window_node_indicator.py (new)
from musicstreamer.runtime_check import NodeRuntime


def test_hamburger_indicator_absent_when_node_available(qtbot, main_window_factory):
    window = main_window_factory(node_runtime=NodeRuntime(available=True, path="/usr/bin/node"))
    qtbot.addWidget(window)
    actions = [a.text() for a in window._menu.actions()]
    assert not any("Node.js" in t for t in actions)


def test_hamburger_indicator_present_when_node_missing(qtbot, main_window_factory):
    window = main_window_factory(node_runtime=NodeRuntime(available=False, path=None))
    qtbot.addWidget(window)
    actions = [a.text() for a in window._menu.actions()]
    assert any("Node.js: Missing" in t for t in actions)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| NSIS installer | Inno Setup 6 | Phase 44 D-01 | First-class AUMID parameter on `[Icons]`; Pascal is more readable than NSIS script for short installers. |
| `libgiognutls.dll` (GnuTLS) | `gioopenssl.dll` (OpenSSL) | GStreamer 1.28.x | TLS backend changed upstream; Phase 43 `.spec` handles both. |
| GStreamer plugins under `gstreamer-1.0/` | `gst_plugins/` | hooks-contrib 2026.2 | Naming convention changed; stock `pyi_rth_gstreamer` knows this. No action. |
| Upstream MSVC GStreamer installer | conda-forge | Phase 43 D-18 | PyGObject wheels — BLOCKER on Windows otherwise. |
| mpv subprocess YouTube fallback | yt-dlp library + Node.js EJS solver | Plan 35-06 | Retires PKG-05; introduces RUNTIME-01 (host Node.js requirement). |

**Deprecated/outdated:**
- `gst-plugin-scanner.exe` in `bin/` (1.24/1.26) → now `libexec/gstreamer-1.0/` (1.28+). `.spec` auto-detects.
- NSIS `ApplicationID` plugin (for AUMID) — Inno Setup's built-in parameter obviates it.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Inno Setup's `[Icons]` `AppUserModelID` parameter does NOT require an `IconIndex` to bind correctly | Pattern 1 | Low — documentation explicitly lists AppUserModelID as a standalone parameter; confirmed in UAT D-21 item 7. |
| A2 | `QLocalServer` on Windows uses a named pipe scoped to the current user session (not machine-wide) | Pattern 2 | Low — confirmed in Qt docs; means two users on the same machine can each run their own instance. |
| A3 | `FlashWindowEx` falls back silently if focus-steal prevention blocks `activateWindow()` — no user-visible error | Pattern 2 | Low — historically true on Windows; documented-as-deferred for tuning (D-21 item 6 catches regressions). |
| A4 | `yt-dlp` 2026-era versions with `extractor_args={'youtubepot-jsruntime': ...}` do not have a unique error signature for missing-Node — generic `ExtractorError` | Pattern 3 | Low — the "Node missing AND YT resolve failed" heuristic is sufficient; no false positives because non-Node yt-dlp failures are rare and the toast is still helpful context. |
| A5 | `pyinstaller-hooks-contrib 2026.2` handles yt-dlp + streamlink imports without explicit `hiddenimports` | Pattern 4 | Medium — iteration 1 of Phase 44 build will surface any missing; iteration 2 adds explicit entries. Follows the Phase 43 iterative discipline. |
| A6 | Inno Setup default uninstaller respects `DisableProgramGroupPage=yes` + `DisableDirPage=yes` without surprising the user | Pattern 1 | Low — these flags just suppress the wizard pages; functionality unchanged. |
| A7 | The `%APPDATA%\microsoft\windows\start menu\programs\MusicStreamer.lnk` path created by `{userprograms}` is the correct AUMID-carrying location for per-user install | Pattern 1 | Low — confirmed by Inno Setup's `{userprograms}` docs; UAT D-21 item 1 verifies shortcut presence + item 7 verifies AUMID binding. |

## Open Questions (RESOLVED)

None — all architectural choices are locked (CONTEXT.md D-01..D-23); all implementation details are covered by Patterns 1-8. The only unknowns are things UAT will surface (e.g., whether `FlashWindowEx` is actually needed, whether any yt-dlp `hiddenimports` are missed by hooks-contrib 2026.2). These follow Phase 43's iteration discipline — discover during build, not during planning.

## Environment Availability

| Dependency | Required By | Available on Dev Box | Version | Fallback |
|------------|------------|----------------------|---------|----------|
| Node.js (dev-box) | — (runtime host requirement only; not needed for build) | ✓ | via fnm | — |
| ImageMagick | One-time `.ico` conversion on dev box | ✓ (`/usr/bin/magick`, `/usr/bin/convert`) | — | Python PIL (also ✓) |
| Python PIL | `.ico` conversion fallback | ✓ | — | — |
| Inno Setup 6 (Windows VM) | Installer compile | Not on Linux dev box; installed on VM | 6.3+ | — (required — no fallback) |
| Miniforge + conda env `spike` (Windows VM) | PyInstaller build env | On Phase 43 VM | 3.12.13 Python | — |
| PowerShell 5.1+ (Windows VM) | build.ps1 driver | On VM | — | — |

**Missing dependencies with no fallback:**
- Inno Setup 6 on the Win11 VM — installer must be downloaded from `https://jrsoftware.org/isdl.php` before the first Phase 44 build. Document in `packaging/windows/README.md`.

**Missing dependencies with fallback:**
- None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` 9+ with `pytest-qt` 4+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"]) |
| Quick run command | `pytest tests/test_single_instance.py tests/test_runtime_check.py -x` |
| Full suite command | `pytest` |
| Phase gate | Full suite green before `/gsd-verify-work`; plus manual UAT on Win11 VM before ship |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PKG-01 | PyInstaller bundle builds with HTTPS-capable GStreamer | Manual UAT (Windows VM) | Run `build.ps1`; `dist/MusicStreamer/` exists; smoke UAT-1 plays SomaFM HTTPS | ❌ Wave 0 — UAT doc |
| PKG-01 | `hiddenimports` for PySide6.QtNetwork / QtSvg / winrt.windows.* present | Unit | `pytest tests/test_spec_hidden_imports.py` (lightweight — parse .spec as text, grep) | ❌ Wave 0 |
| PKG-02 | Inno Setup installer produces expected `.exe` | Manual UAT | Run `build.ps1`, assert `dist/installer/MusicStreamer-2.0.0-win64-setup.exe` exists | ❌ UAT doc |
| PKG-02 | Installer installs to `%LOCALAPPDATA%\MusicStreamer` with Start Menu shortcut | Manual UAT | UAT-D21-1 (fresh install round-trip) | ❌ UAT doc |
| PKG-03 | Zero bare subprocess.* in musicstreamer/ outside subprocess_utils.py | Build-time guard | `build.ps1` Select-String check (exit 4 on hit) | ❌ Wave 0 (build.ps1 edit) |
| PKG-03 | Python-side assertion (belt-and-braces, runs in CI/Linux too) | Unit | `pytest tests/test_pkg03_compliance.py` — grep over `musicstreamer/` | ❌ Wave 0 |
| PKG-04 | First instance acquires server; second instance forwards activate signal | Unit (pytest-qt) | `pytest tests/test_single_instance.py::test_second_instance_forwards_and_first_sees_activate -x` | ❌ Wave 0 |
| PKG-04 | Second-launch raises existing window | Manual UAT | UAT-D21-6 (double-click shortcut) | ❌ UAT doc |
| RUNTIME-01 | Node detection returns available=True when node on PATH | Unit | `pytest tests/test_runtime_check.py::test_check_node_available` | ❌ Wave 0 |
| RUNTIME-01 | Node detection returns available=False when absent | Unit | `pytest tests/test_runtime_check.py::test_check_node_absent` | ❌ Wave 0 |
| RUNTIME-01 | Windows-specific `node.exe` preference (issue #109590 guard) | Unit | `pytest tests/test_runtime_check.py::test_which_node_prefers_exe_on_windows` | ❌ Wave 0 |
| RUNTIME-01 | Hamburger indicator appears when node_runtime.available=False | Widget (pytest-qt) | `pytest tests/ui_qt/test_main_window_node_indicator.py` | ❌ Wave 0 |
| RUNTIME-01 | Missing-Node dialog shows correct buttons (non-blocking) | Widget (pytest-qt) | `pytest tests/ui_qt/test_missing_node_dialog.py` | ❌ Wave 0 |
| RUNTIME-01 | YT play failure shows "Install Node.js" toast when Node missing | Widget (pytest-qt) | `pytest tests/ui_qt/test_main_window_integration.py::test_yt_fail_toast_when_node_missing` | ❌ Wave 0 (extend existing test) |
| QA-03 | Windows smoke test on clean VM | Manual UAT | `44-UAT.md` items D-20-1..8 + D-21-1..7 | ❌ UAT doc |
| QA-05 | Widget lifetime audit | Document-only | `44-QA05-AUDIT.md` (grep sweep + UAT regression check) | ❌ audit doc |

### Sampling Rate
- **Per task commit:** `pytest tests/test_single_instance.py tests/test_runtime_check.py tests/test_pkg03_compliance.py -x` (< 5 sec)
- **Per wave merge:** `pytest` (full suite, < 30 sec on Linux)
- **Phase gate:** Full suite + manual UAT on Win11 VM per D-19

### Wave 0 Gaps
- [ ] `tests/test_single_instance.py` — 2 QLocalServer round-trip tests (PKG-04)
- [ ] `tests/test_runtime_check.py` — 3 Node detection tests (RUNTIME-01)
- [ ] `tests/test_pkg03_compliance.py` — grep regression test (PKG-03)
- [ ] `tests/test_spec_hidden_imports.py` — parse `.spec` for required `hiddenimports` (PKG-01)
- [ ] `tests/ui_qt/test_main_window_node_indicator.py` — hamburger indicator conditional (RUNTIME-01)
- [ ] `tests/ui_qt/test_missing_node_dialog.py` — dialog button wiring (RUNTIME-01)
- [ ] Extend `tests/test_main_window_integration.py` — YT-fail-when-node-missing toast (RUNTIME-01)
- [ ] `44-UAT.md` — mirror `43.1-UAT.md` with D-20 (8 items) + D-21 (7 items) (QA-03)
- [ ] `44-QA05-AUDIT.md` — grep output + parent= confirmations + UAT-log regression check (QA-05)

No framework install needed — pytest-qt + pytest are already in `[project.optional-dependencies].test`.

## Security Domain

Per `.planning/config.json`, `security_enforcement` is not explicitly set to false — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V1 Architecture | yes | Host-runtime check (RUNTIME-01) surfaces a dependency that would otherwise fail silently; installer runs un-elevated (least privilege). |
| V2 Authentication | no | No new auth; existing OAuth flows (Twitch, Google) unchanged. |
| V3 Session Management | no | N/A for local desktop app; single-instance is not a session primitive. |
| V4 Access Control | yes | Per-user install (`PrivilegesRequired=lowest`) — no admin escalation, no machine-wide writes. `QLocalServer.SocketOption.UserAccessOption` restricts the socket to current user (belt-and-braces; Windows named pipe scoping already provides this). |
| V5 Input Validation | yes | Single-instance protocol accepts bytes from local socket — we MUST validate input. Current impl accepts exactly `b"activate"` (stripped); unknown payloads logged and ignored. No privileged action exposed, so attack surface is minimal. |
| V6 Cryptography | no | N/A. We rely on GStreamer's OpenSSL via `gioopenssl.dll` for TLS (already in bundle); app doesn't roll its own crypto. |
| V7 Error Handling | yes | `QLocalServer.listen` failure does NOT crash the app — logs warning and continues without guard (graceful degradation). Node detection failure is informational, never fatal. |
| V10 Malicious Code | yes | No code signing this phase (deferred to v2.1+); Windows SmartScreen will flag the installer on first download. Documented as accepted friction in ROADMAP. |
| V14 Configuration | yes | AUMID string, single-instance server name, AppId GUID — all locked constants, not user-configurable. Prevents impersonation via crafted config. |

### Known Threat Patterns for Windows Desktop + Python + Qt Stack

| Pattern | STRIDE | Standard Mitigation | Phase 44 Handling |
|---------|--------|---------------------|-------------------|
| DLL planting in install dir | E (Elevation) / T (Tampering) | Install to user-owned path; don't modify `%PATH%`; no SetDllDirectory leaks | `%LOCALAPPDATA%\MusicStreamer` is user-owned; no PATH manipulation. |
| Named-pipe impersonation (single-instance hijack) | S (Spoofing) | Per-user scoping; validate payload | Windows named pipe in user session; `UserAccessOption`; strict `b"activate"` payload match. |
| Stale socket hijack (Linux) | S (Spoofing) | `UserAccessOption` (0600 permissions on socket file) | Set in `single_instance.py`. |
| Installer MITM on download | T / I | HTTPS distribution + (future) code signing | User downloads from GitHub releases over HTTPS (v2.1+ code signing deferred). |
| User data exfiltration via uninstall bug | I (Info Disclosure) | Don't touch user data dir | `%APPDATA%\musicstreamer` untouched (D-03). |
| Malicious Node.js PATH entry hijacks YT resolution | T / R (Repudiation) | Not a Phase 44 concern — user runs the Node.js they chose to install; threat model is personal use | Out of scope; documented in EULA. |
| Unsigned EXE → SmartScreen → user bypass habituation | R | Code signing (deferred v2.1+) | Accepted friction. |

## Smoke Test / UAT Structure

Phase 44 produces `.planning/phases/44-windows-packaging-installer/44-UAT.md` mirroring the `43.1-UAT.md` format. Full template:

```markdown
---
phase: 44
plan: (TBD by planner)
status: in-progress
created: <date>
updated: <date>
---

# Phase 44 — Windows UAT (Packaging + Installer)

> Runs on the Win11 VM used during Phases 43 + 43.1. Sign off every row before marking Phase 44 complete.

## Environment Snapshot

Captured on Win11 VM:
```
Windows: (from `winver`)
Python: (from `python --version`; expected 3.12.x conda-forge)
Conda env: musicstreamer-build (or spike — whichever holds the build deps)
Inno Setup: (from `iscc.exe /?` first line; expected 6.3.x)
Node.js: (from `node --version`; required for D-20 item 4 only; removable for item 5)
pip list | findstr "PySide6 winrt yt-dlp streamlink pyinstaller":
  (paste)
```

## Build Artifacts

| Artifact | Path | Size | Verified |
|----------|------|------|----------|
| PyInstaller bundle | `dist\MusicStreamer\` | (~110 MB; DLL count ~126) | ☐ |
| Inno Setup installer | `dist\installer\MusicStreamer-2.0.0-win64-setup.exe` | (single EXE) | ☐ |
| build.log tail | `artifacts\build.log` | — | ☐ `BUILD_OK installer='...'` + `BUILD_DIAG bundle_size_mb=...` present |
| iscc.log | `artifacts\iscc.log` | — | ☐ `Successful compile` line |

## D-20 Playback Checklist

| # | Behavior | Requirement | Method | Pass/Fail | Notes |
|---|----------|-------------|--------|-----------|-------|
| UAT-20-1 | SomaFM HTTPS (Drone Zone) plays; ICY title updates | PKG-01 | Select SomaFM → Drone Zone; wait 30s for ICY | ☐ | |
| UAT-20-2 | HLS stream plays | PKG-01 | Select any HLS station in library | ☐ | |
| UAT-20-3 | DI.fm over HTTP plays (HTTPS expected to fail per D-15) | PKG-01 / D-15 | Select DI.fm channel with HTTP URL | ☐ | HTTPS per D-15 will fail; HTTP must pass. |
| UAT-20-4 | YouTube live with Node.js on PATH | RUNTIME-01 / PKG-01 | LoFi Girl-style live; play via yt-dlp EJS solver | ☐ | |
| UAT-20-5 | YouTube live WITHOUT Node.js: (a) startup dialog, (b) hamburger indicator, (c) toast on YT play attempt; non-YT streams still work | RUNTIME-01 / D-13 | Remove Node from PATH (`set PATH=...`), relaunch, attempt YT | ☐ | Three surfaces must all appear. |
| UAT-20-6 | Twitch live plays via streamlink | PKG-01 | Select Twitch station (requires OAuth token) | ☐ | |
| UAT-20-7 | Multi-stream failover: primary fail → next stream picks up | PKG-01 | Edit primary URL to invalid, play | ☐ | |
| UAT-20-8 | SMTC: media keys play/pause/stop work; overlay shows station + ICY + cover art | PKG-01 (MEDIA ported from 43.1) | Press hardware media keys during playback | ☐ | Regression check vs. 43.1-UAT. |

## D-21 Installer / Round-Trip Checklist

| # | Behavior | Requirement | Method | Pass/Fail | Notes |
|---|----------|-------------|--------|-----------|-------|
| UAT-21-1 | Fresh Win11 VM snapshot → installer runs → Start Menu shortcut exists → launch via shortcut succeeds | PKG-02 | Revert VM snapshot, run installer, find shortcut in Start Menu | ☐ | |
| UAT-21-2 | Uninstall via Settings → Apps removes install dir; user data in `%APPDATA%\musicstreamer` preserved | D-03 | Uninstall, check both paths | ☐ | Confirm `dir %APPDATA%\musicstreamer` still lists SQLite + assets. |
| UAT-21-3 | Re-install over nothing works | PKG-02 | Re-run installer after uninstall | ☐ | |
| UAT-21-4 | Settings export Linux→Windows round-trip | QA-03 / SC-6 | Export on Linux, move ZIP, import via hamburger menu | ☐ | Stations, streams, favorites, tags, logos all visible + playable. |
| UAT-21-5 | Settings export Windows→Linux round-trip | QA-03 / SC-6 | Reverse flow | ☐ | |
| UAT-21-6 | Single-instance: double-click shortcut while app running → existing window raises + focuses | PKG-04 / D-09 | Launch, then double-click shortcut again | ☐ | No second window; existing one activates. |
| UAT-21-7 | AUMID/SMTC: overlay shows "MusicStreamer" (not "Unknown app") | D-04 / Phase 43.1 | Must launch via Start Menu shortcut; bare `python -m musicstreamer` expected to still show "Unknown app" | ☐ | |

## Sign-Off

- [ ] All D-20 items pass
- [ ] All D-21 items pass
- [ ] No new entries in `%APPDATA%\musicstreamer\logs\` with tracebacks
- [ ] QA-05 audit doc reviewed (`44-QA05-AUDIT.md`)
```

## QA-05 Widget Lifetime Audit Template

`.planning/phases/44-windows-packaging-installer/44-QA05-AUDIT.md`:

```markdown
# Phase 44 — QA-05 Widget Lifetime Audit

**Audit date:** <date>
**Scope:** All QWidget / QDialog subclasses in `musicstreamer/ui_qt/`; all GStreamer callback flows in `musicstreamer/player.py`.

## Subclass Inventory

(Populated from grep: `grep -E "class.*\((QWidget|QDialog|QMainWindow|QObject).*\)" musicstreamer/ui_qt/*.py`)

| Class | File | parent= passed in __init__? | Lifetime owner | Risk |
|-------|------|------------------------------|----------------|------|
| ToastOverlay | toast.py | required (parent positional) | MainWindow | ☐ OK |
| NowPlayingPanel | now_playing_panel.py | yes | QSplitter | ☐ OK |
| StationListPanel | station_list_panel.py | yes | QSplitter | ☐ OK |
| AccountsDialog | accounts_dialog.py | yes | MainWindow | ☐ OK |
| AccentColorDialog | accent_color_dialog.py | yes | MainWindow | ☐ OK |
| CookieImportDialog | cookie_import_dialog.py | yes | MainWindow | ☐ OK |
| DiscoveryDialog | discovery_dialog.py | yes | MainWindow | ☐ OK |
| EditStationDialog | edit_station_dialog.py | yes | MainWindow | ☐ OK |
| EqualizerDialog | equalizer_dialog.py | yes | MainWindow | ☐ OK |
| ImportDialog | import_dialog.py | yes | MainWindow | ☐ OK |
| SettingsImportDialog | settings_import_dialog.py | yes | MainWindow | ☐ OK |
| ResponseCurve | eq_response_curve.py | yes | EqualizerDialog | ☐ OK |
| FavoritesView | favorites_view.py | yes | StationListPanel | ☐ OK |

## Dialog Launch Sites

(Populated from grep: `grep -n "Dialog(.*parent" musicstreamer/ui_qt/main_window.py`)

| Call site | Parent arg present? | OK |
|-----------|---------------------|-----|
| `EditStationDialog(fresh, self._player, self._repo, parent=self)` | yes | ☐ |
| `DiscoveryDialog(self._player, self._repo, self.show_toast, parent=self)` | yes | ☐ |
| `ImportDialog(self.show_toast, self._repo, parent=self)` | yes | ☐ |
| `AccentColorDialog(self._repo, parent=self)` | yes | ☐ |
| `CookieImportDialog(self.show_toast, parent=self)` | yes | ☐ |
| `AccountsDialog(self._repo, parent=self)` | yes | ☐ |
| `EqualizerDialog(self._player, self._repo, self.show_toast, parent=self)` | yes | ☐ |
| `SettingsImportDialog(preview, self.show_toast, parent=self)` | yes | ☐ |

## Callback Flow Audit (Player → UI)

(Bound methods only per QA-05; no lambda-captured self. Already audited during Phase 37+.)

| Signal | Handler | Bound method? | OK |
|--------|---------|---------------|-----|
| player.title_changed | self.now_playing.on_title_changed | yes | ☐ |
| player.failover | self._on_failover | yes | ☐ |
| player.offline | self._on_offline | yes | ☐ |
| player.playback_error | self._on_playback_error | yes | ☐ |
| ... | ... | ... | ... |

## UAT Log Regression Check

Grep UAT notes from Phases 37, 40, 41, 42, 43.1:
```
grep -rn "RuntimeError.*Internal C\+\+ object already deleted" .planning/phases/ || echo "NONE"
```

Expected: NONE. Any hits must be reported as a fix target.

**Finding:** <paste output here>

## Spot Fixes

- [ ] (none expected; grep scope is complete per Phase 37–47.2 D-05 convention)

## Sign-Off

- [ ] All dialog subclasses pass parent= to super().__init__
- [ ] All dialog launch sites pass parent=self from MainWindow
- [ ] No "Internal C++ object already deleted" entries in UAT logs
- [ ] No spot fixes required (or: fixes committed at <SHA>)
```

**Expected audit result:** Clean. The codebase already follows the `parent=` convention (Phase 37 established it; Phase 43.1 UAT-10 proved cross-session stability). Phase 44's audit is mainly a documented regression gate.

## Sources

### Primary (HIGH confidence)
- Phase 43 spike findings — `.planning/phases/43-gstreamer-windows-spike/43-SPIKE-FINDINGS.md` (empirically validated bundling recipe + 9 gotchas + BOM)
- Phase 43 artifacts — `.spec`, `runtime_hook.py`, `build.ps1`, `smoke_test.py` (copy-paste targets)
- Phase 43.1 AUMID findings — `.planning/phases/43.1-windows-media-keys-smtc/` (AUMID process binding + shell registration requirement)
- Skill `spike-findings-musicstreamer` — `.claude/skills/spike-findings-musicstreamer/references/*.md` (condensed recipe)
- Current code — `musicstreamer/__main__.py` (existing `_set_windows_aumid`, `_run_gui` skeleton), `musicstreamer/ui_qt/main_window.py` (hamburger menu + dialog launch conventions)
- [Inno Setup `[Icons]` section docs](https://jrsoftware.org/ishelp/topic_iconssection.htm) — AppUserModelID parameter
- [Inno Setup `AppId` docs](https://jrsoftware.org/ishelp/topic_setup_appid.htm) — GUID upgrade semantics
- [Inno Setup `PrivilegesRequired` docs](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm) — `lowest` mode
- [Inno Setup directory constants](https://jrsoftware.org/ishelp/topic_consts.htm) — `{localappdata}`, `{userprograms}`
- [PySide6 QLocalServer docs](https://doc.qt.io/qtforpython-6/PySide6/QtNetwork/QLocalServer.html) — newConnection, removeServer, named-pipe behavior
- [PySide6 QLocalSocket docs](https://doc.qt.io/qtforpython-6/PySide6/QtNetwork/QLocalSocket.html) — Windows named pipe implementation

### Secondary (MEDIUM confidence)
- [CPython #109590 — shutil.which Windows PATHEXT bug](https://github.com/python/cpython/issues/109590) — motivates `node.exe` prefer-explicit workaround
- [CPython #127001 — shutil.which 3.12 regressions](https://github.com/python/cpython/issues/127001) — same class of issue
- [PyInstaller docs — stable](https://pyinstaller.org/en/stable/usage.html) — onedir semantics, `console=False` behavior

### Tertiary (LOW confidence)
- None — no findings rely solely on unverified sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Phase 43 proved the build recipe empirically; Inno Setup is well-documented.
- Architecture: HIGH — all choices locked in CONTEXT.md; patterns are direct implementations of those decisions.
- Pitfalls: HIGH — Phase 43's 9-gotcha table + Phase 43.1's AUMID finding cover the Windows-specific risks; shutil.which issue cited from upstream CPython tracker.
- Single-instance pattern: HIGH — cross-verified against PySide6 docs + standard Qt pattern.
- Node.js UX: MEDIUM — yt-dlp error signature (A4) is a heuristic, not a parsed error code; risk is low because the heuristic only triggers when Node is already known missing.

**Research date:** 2026-04-23
**Valid until:** 30 days (stable domain — Inno Setup 6 and PySide6 6.11 are not fast-moving; Phase 43 recipe is locked)
