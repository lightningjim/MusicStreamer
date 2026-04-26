# Phase 44: Windows Packaging + Installer — Pattern Map

**Mapped:** 2026-04-25
**Files analyzed:** 14 created + 4 edited + ~7 new tests
**Analogs found:** 17 / 18 (one truly new: Inno Setup `.iss` — no existing analog in repo)

## File Classification

### New files

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `packaging/windows/MusicStreamer.iss` | config (installer script) | build-time | (none in repo — RESEARCH §Pattern 1 is canonical) | no analog |
| `packaging/windows/MusicStreamer.spec` | config (PyInstaller spec) | build-time | `.planning/phases/43-gstreamer-windows-spike/43-spike.spec` | exact (verbatim copy + diff per RESEARCH §Pattern 4) |
| `packaging/windows/runtime_hook.py` | config (PyInstaller rthook) | runtime env | `.planning/phases/43-gstreamer-windows-spike/runtime_hook.py` | exact (copy verbatim per D-17) |
| `packaging/windows/build.ps1` | utility (build driver) | build-time | `.planning/phases/43-gstreamer-windows-spike/build.ps1` | exact (extend per RESEARCH §Pattern 5) |
| `packaging/windows/EULA.txt` | config (text content) | n/a | (none — RESEARCH §Pattern 8 draft is canonical) | no analog |
| `packaging/windows/README.md` | doc | n/a | `.planning/phases/43-gstreamer-windows-spike/README.md` | role-match |
| `packaging/windows/icons/MusicStreamer.ico` | asset (binary) | n/a | `org.lightningjim.MusicStreamer.png` (source) — convert per RESEARCH §Pattern 7 | source-match |
| `musicstreamer/single_instance.py` | service (Qt helper) | event-driven (named-pipe IPC + Qt signal) | `musicstreamer/media_keys/__init__.py` (factory + NoOp degradation pattern) + `musicstreamer/subprocess_utils.py` (flat helper-module convention) | role-match (no existing IPC module) |
| `musicstreamer/runtime_check.py` | service (host-runtime probe) | request-response (one-shot) | `musicstreamer/subprocess_utils.py` (flat helper module) + `musicstreamer/media_keys/__init__.py` (sys.platform guard + dataclass-style return) | role-match |
| `musicstreamer/__version__.py` | config (version literal) | n/a | (none — single-literal module is trivially new) | no analog |
| `tests/test_single_instance.py` | test (pytest-qt) | unit | `tests/test_media_keys_scaffold.py` (qtbot + monkeypatch + signal wait) | exact |
| `tests/test_runtime_check.py` | test (unit + monkeypatch) | unit | `tests/test_media_keys_scaffold.py::test_create_returns_noop_on_win32` (sys.platform monkeypatch idiom) | exact |
| `tests/test_pkg03_compliance.py` | test (grep regression guard) | unit | (none — new style; mirror pytest convention from existing tests) | role-match |
| `tests/test_spec_hidden_imports.py` | test (text parse of `.spec`) | unit | (none — new style) | no analog |
| `tests/ui_qt/test_main_window_node_indicator.py` | test (pytest-qt widget) | unit | `tests/test_main_window_integration.py` (existing main_window factory pattern) | role-match |
| `tests/ui_qt/test_missing_node_dialog.py` | test (pytest-qt widget) | unit | `tests/test_main_window_integration.py` | role-match |
| `.planning/phases/44-windows-packaging-installer/44-QA05-AUDIT.md` | doc (audit deliverable) | n/a | `.planning/phases/43.1-windows-media-keys-smtc/43.1-UAT.md` (deliverable doc style) | role-match |
| `.planning/phases/44-windows-packaging-installer/44-UAT.md` | doc (UAT deliverable) | n/a | `.planning/phases/43.1-windows-media-keys-smtc/43.1-UAT.md` | exact |

### Edited files

| Edited File | Role | Data Flow | Pattern Source |
|-------------|------|-----------|----------------|
| `musicstreamer/__main__.py` | controller (entry point) | request-response | self (existing `_run_gui` body — extend in place per RESEARCH §Pattern 2 wiring block) |
| `musicstreamer/ui_qt/main_window.py` | controller (Qt main window) | event-driven | self (existing hamburger menu + `_on_playback_error` — extend in place) |
| `pyproject.toml` | config (project metadata) | n/a | self (bump `version = "1.1.0"` → `"2.0.0"` per D-06) |
| `tests/test_main_window_integration.py` | test (pytest-qt integration) | unit | self (extend existing tests with Node-missing case) |

---

## Pattern Assignments

### `musicstreamer/single_instance.py` (service, event-driven IPC)

**Analogs:**
- Module shape & flat-helper convention: `musicstreamer/subprocess_utils.py`
- Factory + degradation pattern: `musicstreamer/media_keys/__init__.py`
- Qt-aware module + bound-method signal handling: `musicstreamer/media_keys/base.py`

**Module docstring + imports pattern** (mirror `subprocess_utils.py:1-10` + `media_keys/base.py:10-20`):

```python
"""Single-instance enforcement via QLocalServer/QLocalSocket (D-08, D-09).

First instance calls acquire_or_forward() and receives a running QLocalServer
(kept alive for the app lifetime). Subsequent launches connect to that server,
send b"activate\\n", and exit cleanly. The first instance's newConnection
handler raises and focuses the main window.

On Windows QLocalSocket uses a named pipe (no socket file to clean up).
On Linux, removeServer deletes a stale socket so a crashed prior instance
does not block us.
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

_log = logging.getLogger(__name__)
```

**Constants-at-top pattern** (mirror `media_keys/base.py:22` `_VALID_STATES = frozenset({...})`):

```python
SERVER_NAME = "org.lightningjim.MusicStreamer.single-instance"  # D-08
_CONNECT_TIMEOUT_MS = 500
```

**QObject + Signal pattern** (mirror `media_keys/base.py:25-35`):

```python
class SingleInstanceServer(QObject):
    """Wraps QLocalServer; emits activate_requested on each activation."""

    activate_requested = Signal()

    def __init__(self, server: QLocalServer, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server = server
        self._server.newConnection.connect(self._on_new_connection)
```

**Bound-method-only signal binding** (QA-05 rule — mirror `main_window.py:223` `self._player.playback_error.connect(self._on_playback_error)`):
- All `.connect(...)` calls bind a bound method, never a self-capturing lambda.
- The one acceptable lambda is parameter-only: `lambda: self._drain(socket)` — the closure captures `socket`, not `self`. RESEARCH §Pattern 2 line 404 already follows this rule.

**Module-level `acquire_or_forward()` factory** (mirror `media_keys/__init__.py:23-54` `create()` factory):
- Returns `Optional[SingleInstanceServer]` — `None` signals "second instance, exit cleanly".
- All failure modes log + degrade rather than raise (matches `media_keys.create` "never raises" contract).
- Use `_log.warning(...)` for non-fatal degradation paths (mirror `media_keys/__init__.py:42` `_log.warning(...)`).

**Platform-split FlashWindowEx fallback** (mirror `__main__.py:113-125` `_set_windows_aumid` ctypes pattern):
- `if sys.platform != "win32": return` early-exit
- `import ctypes` + `from ctypes import wintypes` inside the function (lazy, not module-scope)
- Wrap in `try/except Exception as exc: _log.debug(...)` so a fallback failure is silent
- See RESEARCH §Pattern 2 lines 458-502 for the full block (copy verbatim)

---

### `musicstreamer/runtime_check.py` (service, request-response)

**Analogs:**
- Flat-helper convention + Windows guard: `musicstreamer/subprocess_utils.py:14-18`
- Logging + module docstring: `musicstreamer/media_keys/base.py:1-20`
- `sys.platform == "win32"` early-branch: `musicstreamer/__main__.py:113-114`

**Imports + dataclass pattern** (mirror `models.py` dataclass usage; QMessageBox import idiom matches `main_window.py:33-41`):

```python
from __future__ import annotations

import logging
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
    path: Optional[str]
```

**Platform-branch helper pattern** (mirror `subprocess_utils.py:14-18` exactly — same shape, same comment style):

```python
def _which_node() -> Optional[str]:
    """Locate node executable on PATH with Windows 3.12 safety
    (CPython issue #109590). On win32 prefer node.exe explicitly.
    """
    if sys.platform == "win32":
        result = shutil.which("node.exe")
        if result:
            return result
        result = shutil.which("node")
        if result and result.lower().endswith(".exe"):
            return result
        return None
    return shutil.which("node")
```

**Lazy-import inside function** (mirror `__main__.py:115-116, 136-141` lazy-import idiom — keeps Linux/test imports cheap):

```python
def show_missing_node_dialog(parent) -> None:
    """Non-blocking warning dialog (D-12)."""
    box = QMessageBox(parent)
    # ... configure box ...
    box.exec()
    if box.clickedButton() is open_btn:
        from PySide6.QtGui import QDesktopServices  # lazy
        from PySide6.QtCore import QUrl             # lazy
        QDesktopServices.openUrl(QUrl(NODEJS_INSTALL_URL))
```

---

### `musicstreamer/__main__.py` (EDIT — controller, request-response)

**Self-analog:** existing `_run_gui` (lines 128-156). Extend in place; do not refactor.

**Insertion points** (preserve existing order):

```python
def _run_gui(argv: list[str]) -> int:
    _set_windows_aumid()         # EXISTING line 130 — keep
    Gst.init(None)               # EXISTING line 131 — keep

    from musicstreamer import migration
    migration.run_migration()    # EXISTING — keep

    from PySide6.QtWidgets import QApplication
    # ... existing icons_rc, MainWindow, Player, Repo imports — keep ...

    app = QApplication(argv)
    app.setApplicationName("MusicStreamer")
    app.setDesktopFileName("org.example.MusicStreamer")
    if sys.platform == "win32":
        app.setStyle("Fusion")
        _apply_windows_palette(app)

    # === D-10 INSERTION: single-instance BEFORE MainWindow ===
    from musicstreamer import single_instance  # lazy (matches existing idiom)
    server = single_instance.acquire_or_forward()
    if server is None:
        return 0  # second instance forwarded — exit cleanly

    # === D-11 INSERTION: Node.js detection BEFORE window.show() ===
    from musicstreamer import runtime_check
    node_runtime = runtime_check.check_node()
    if not node_runtime.available:
        runtime_check.show_missing_node_dialog(parent=None)

    con = db_connect()
    db_init(con)
    player = Player()
    repo = Repo(con)

    window = MainWindow(player, repo, node_runtime=node_runtime)  # NEW kwarg
    server.activate_requested.connect(  # bound-method-friendly closure
        lambda: single_instance.raise_and_focus(window)
    )
    window.show()
    return app.exec()
```

**Lazy-import convention** (existing pattern in `__main__.py:133-141`): all UI-layer modules imported inside `_run_gui`, never at module scope. New imports follow the same rule.

**Single-line `if sys.platform == "win32":` guard** (existing line 145) — Node.js check is cross-platform but the AUMID call already follows this idiom; new code stays cross-platform (no extra guards).

---

### `musicstreamer/ui_qt/main_window.py` (EDIT — controller, event-driven)

**Self-analog:** existing constructor (lines 100-228) + `_on_playback_error` (lines 328-331).

**Constructor signature change** (mirror existing kwarg style on line 103):

```python
# BEFORE
def __init__(self, player, repo, parent: QWidget | None = None) -> None:

# AFTER (add node_runtime as keyword-only kwarg, default None for back-compat)
def __init__(
    self,
    player,
    repo,
    *,
    node_runtime=None,  # NodeRuntime | None — avoid hard import (lazy in _run_gui)
    parent: QWidget | None = None,
) -> None:
```

Store the runtime as `self._node_runtime = node_runtime` immediately after `self._player = player; self._repo = repo` (line 106-107).

**Hamburger menu indicator pattern** (mirror existing `_menu.addAction` + `triggered.connect` idiom on lines 124-147):

```python
# Insert AFTER existing Group 3 (export/import settings, line 166)
# and AFTER worker reference retention (line 170), to keep menu order stable.

if self._node_runtime is not None and not self._node_runtime.available:
    self._menu.addSeparator()
    self._act_node_missing = self._menu.addAction(
        "⚠ Node.js: Missing (click to install)"
    )
    self._act_node_missing.triggered.connect(self._on_node_install_clicked)
```

Use `⚠` (U+26A0 WARNING SIGN) escape literal — matches existing copywriting convention `…` for ellipsis (line 306, 319).

**Bound-method handler pattern** (mirror existing `_on_*` slot conventions):

```python
def _on_node_install_clicked(self) -> None:
    """Open nodejs.org in the default browser (D-13 part 3)."""
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtCore import QUrl
    QDesktopServices.openUrl(QUrl("https://nodejs.org/en/download"))
```

**`_on_playback_error` extension** (extend existing implementation lines 328-331 — do NOT replace):

```python
def _on_playback_error(self, message: str) -> None:
    """Called by Player.playback_error(str)."""
    # D-13 part 2: nudge toward Node install when YT resolve fails AND Node is missing.
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

The early `return` on the Node-missing branch keeps the existing truncation path untouched for non-YT errors.

---

### `packaging/windows/MusicStreamer.spec` (config, build-time)

**Analog:** `.planning/phases/43-gstreamer-windows-spike/43-spike.spec` — copy verbatim (D-17), apply diff per RESEARCH §Pattern 4.

**Imports + GST_ROOT auto-detect** (copy lines 1-34 verbatim):
```python
import os
import sys
from pathlib import Path

GST_ROOT = Path(os.environ.get("GSTREAMER_ROOT", r"C:\spike-gst\runtime"))
assert GST_ROOT.is_dir(), f"GStreamer root not found: {GST_ROOT}"

# Scanner: 1.28.x MSVC ships it under libexec/gstreamer-1.0/; legacy bin/ fallback.
_scanner_libexec = GST_ROOT / "libexec" / "gstreamer-1.0" / "gst-plugin-scanner.exe"
_scanner_bin = GST_ROOT / "bin" / "gst-plugin-scanner.exe"
SCANNER_SRC = _scanner_libexec if _scanner_libexec.is_file() else _scanner_bin
```

**Tree() blocks for gio/typelibs/schemas** (copy lines 42-67 verbatim — these were the spike's hard-won discoveries; RESEARCH §Pattern 4 explicitly says "minimal diff").

**Required edits to `Analysis(...)` block** (lines 74-113 — apply RESEARCH §Pattern 4 diff exactly):
- `["smoke_test.py"]` → `["../../musicstreamer/__main__.py"]`
- Add `datas=[("../../musicstreamer/ui_qt/icons", "musicstreamer/ui_qt/icons"), ("icons/MusicStreamer.ico", "icons")]`
- Extend `hiddenimports` with `PySide6.QtNetwork`, `PySide6.QtSvg`, and the four `winrt.windows.*` modules
- Extend `excludes` with `mpv`, `gi.repository.Gtk`, `gi.repository.Adw`

**Required edits to `EXE(...)` block** (lines 117-132):
- `name="spike"` → `name="MusicStreamer"`
- `console=True` → `console=False` (D-04, PKG-03 — no console flash)
- Add `icon="icons/MusicStreamer.ico"`
- Keep `upx=False` exactly as-is (Phase 43 anti-pattern: never UPX GStreamer DLLs)

**Required edits to `COLLECT(...)` block** (lines 134-146):
- `name="spike"` → `name="MusicStreamer"`
- Keep all three `Tree()` references (`gio_modules_tree`, `typelib_tree`, `glib_share_tree`) — these are the rthook's reason for existing.

---

### `packaging/windows/runtime_hook.py` (config, runtime env)

**Analog:** `.planning/phases/43-gstreamer-windows-spike/runtime_hook.py` — **copy verbatim, zero edits** (D-17).

The three env vars it sets (`GIO_EXTRA_MODULES`, `GI_TYPELIB_PATH`, `GST_PLUGIN_SCANNER`) are necessary in any GStreamer + PyInstaller bundle; the spike validation is the canonical proof.

Optional cosmetic: rename the `SPIKE_DIAG_RTHOOK` log prefix to `MUSICSTREAMER_DIAG_RTHOOK` if a phase-44 grep would filter cleaner — not required.

---

### `packaging/windows/build.ps1` (utility, build-time)

**Analog:** `.planning/phases/43-gstreamer-windows-spike/build.ps1` — copy verbatim, then extend.

**Header pattern** (copy lines 1-13 verbatim — `#Requires`, exit-code legend, param block, `$ErrorActionPreference = "Stop"`, `Set-StrictMode -Version Latest`).

**`Invoke-Native` helper** (copy lines 19-24 verbatim — non-negotiable for PowerShell 5.1 stderr trap; documented in skill `references/windows-gstreamer-bundling.md`).

**Pre-flight checks** (copy lines 36-56 verbatim — gstreamer-1.0-0.dll, gst-inspect, gioopenssl/libgiognutls, gst-plugin-scanner).

**Spec rename** (line 88):
- `python -m PyInstaller 43-spike.spec` → `python -m PyInstaller MusicStreamer.spec`

**NEW: PKG-03 ripgrep guard** (insert before pyinstaller step) — copy from RESEARCH §Pattern 5 lines 762-775. Exit code `4`. Uses `Select-String` (not `rg`) for VM portability.

**NEW: Inno Setup compile step** (insert after pyinstaller step, before final exit) — copy from RESEARCH §Pattern 5 lines 781-813. Exit code `5` (version parse fail) / `6` (iscc not found / nonzero). Reads version from `pyproject.toml` regex.

**NEW: Diagnostic step** (last step) — copy from RESEARCH §Pattern 5 lines 816-819. Logs `BUILD_DIAG bundle_size_mb=...` matching the existing `SPIKE_OK ...` machine-grepable convention.

**Failure-message convention** (already established in spike on lines 37, 41, 47, 52): `Write-Error "BUILD_FAIL reason=<token> hint='<advice>'"` — keep this exact shape for new failure points (`reason=iscc_not_found`, `reason=iscc_nonzero`, `reason=version_not_found_in_pyproject`).

---

### `packaging/windows/MusicStreamer.iss` (config, build-time — NO ANALOG IN REPO)

No analog in the codebase. Use RESEARCH §Pattern 1 (lines 268-347) verbatim as the canonical skeleton. Key invariants:

- `AppId={{914e9cb6-f320-478a-a2c4-e104cd450c88}` — double-open-brace required (Pitfall 4)
- `PrivilegesRequired=lowest` + `DefaultDirName={localappdata}\MusicStreamer` — no admin elevation
- `[Icons]` `AppUserModelID: "org.lightningjim.MusicStreamer"` — must match `__main__.py::_set_windows_aumid` constant exactly (Pitfall 1; verify via grep at planner verification step)
- No `[UninstallDelete]` entries — `%APPDATA%\musicstreamer` is preserved (D-03)

---

### `tests/test_single_instance.py` (test, unit)

**Analog:** `tests/test_media_keys_scaffold.py` (qtbot + monkeypatch + signal-wait pattern).

**Module docstring + imports** (mirror `test_media_keys_scaffold.py:1-13`):

```python
"""Tests for musicstreamer.single_instance (Phase 44, PKG-04).

Uses pytest-qt qtbot fixture (offscreen Qt via conftest.py).
Monkeypatches SERVER_NAME so parallel tests do not collide on the named pipe.
"""
from __future__ import annotations

import pytest

from musicstreamer import single_instance
```

**Test function pattern** (mirror `test_media_keys_scaffold.py:30-36` `qtbot.waitSignal` idiom):

```python
def test_first_instance_acquires_server(qtbot, monkeypatch):
    monkeypatch.setattr(single_instance, "SERVER_NAME", "test-mstream-single-inst-a")
    server = single_instance.acquire_or_forward()
    assert server is not None
    server.close()


def test_second_instance_forwards_and_first_sees_activate(qtbot, monkeypatch):
    monkeypatch.setattr(single_instance, "SERVER_NAME", "test-mstream-single-inst-b")

    first = single_instance.acquire_or_forward()
    assert first is not None

    with qtbot.waitSignal(first.activate_requested, timeout=1000):
        second = single_instance.acquire_or_forward()
        assert second is None

    first.close()
```

Per-test unique `SERVER_NAME` is mandatory — mirrors the existing `monkeypatch.setattr(sys, "platform", ...)` per-test isolation in `test_media_keys_scaffold.py:67-82`.

---

### `tests/test_runtime_check.py` (test, unit)

**Analog:** `tests/test_media_keys_scaffold.py:67-82` (sys.platform monkeypatch idiom) + `from unittest.mock import patch` for the `shutil.which` simulation.

```python
"""Tests for musicstreamer.runtime_check (Phase 44, RUNTIME-01)."""
from unittest.mock import patch
import sys
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
    monkeypatch.setattr(sys, "platform", "win32")
    with patch("shutil.which") as mock_which:
        mock_which.side_effect = lambda name: (
            r"C:\Program Files\nodejs\node.exe" if name == "node.exe" else None
        )
        assert runtime_check._which_node() == r"C:\Program Files\nodejs\node.exe"
        mock_which.assert_called_with("node.exe")
```

---

### `tests/test_pkg03_compliance.py` (test, grep regression guard)

**Analog:** none in repo. Pattern: pure-Python grep over `musicstreamer/` with `pathlib` (no shelling out — keeps the test cross-platform).

Skeleton:
```python
"""PKG-03 compliance: no bare subprocess.{Popen,run,call} outside subprocess_utils.py."""
import re
from pathlib import Path

_FORBIDDEN = re.compile(r"\bsubprocess\.(Popen|run|call)\b")

def test_no_raw_subprocess_in_musicstreamer():
    root = Path(__file__).resolve().parent.parent / "musicstreamer"
    offenders = []
    for path in root.rglob("*.py"):
        if path.name == "subprocess_utils.py":
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if _FORBIDDEN.search(line):
                offenders.append(f"{path}:{lineno}: {stripped}")
    assert not offenders, "PKG-03 violation:\n" + "\n".join(offenders)
```

This mirrors the build.ps1 ripgrep guard semantically (belt-and-braces — runs on Linux CI too).

---

### `tests/ui_qt/test_main_window_node_indicator.py` + `tests/ui_qt/test_missing_node_dialog.py`

**Analog:** `tests/test_main_window_integration.py` — uses an existing `main_window_factory` fixture pattern (referenced in RESEARCH §Code Example 4, lines 1077-1089).

Use the same `qtbot.addWidget(window)` + iterate `window._menu.actions()` pattern. Test bodies are short (assert-style) — see RESEARCH lines 1077-1089 for the literal copy.

---

## Shared Patterns

### Logging
**Source:** `musicstreamer/media_keys/__init__.py:20` + `musicstreamer/media_keys/base.py:20`
**Apply to:** `single_instance.py`, `runtime_check.py`
```python
import logging
_log = logging.getLogger(__name__)
```
Use `_log.info(...)` for one-shot detections, `_log.warning(...)` for graceful-degradation paths, `_log.debug(...)` for fallback failures (mirrors `media_keys/__init__.py:42, 50`).

### Platform Split
**Source:** `musicstreamer/__main__.py:113-114, 145` + `musicstreamer/subprocess_utils.py:16`
**Apply to:** Any new code with Windows-specific behavior (FlashWindowEx, node.exe preference)
```python
if sys.platform != "win32":
    return
# Windows-only block follows
```
Or the alternate form:
```python
if sys.platform == "win32":
    # win-only branch
```

### Lazy Imports for UI Modules
**Source:** `musicstreamer/__main__.py:115-116, 133-141` (ctypes + ui_qt + Player imported inside function)
**Apply to:** All new module imports added inside `_run_gui`; all `QDesktopServices`/`QUrl` imports inside one-shot button handlers (`runtime_check.show_missing_node_dialog`, `main_window._on_node_install_clicked`).
**Why:** Keeps `__main__.py`'s `_run_smoke` path cheap (no Qt widgets pulled in); keeps test imports minimal.

### Graceful-Degradation Factory
**Source:** `musicstreamer/media_keys/__init__.py:23-54`
**Apply to:** `single_instance.acquire_or_forward()` (returns `None` instead of raising on `QLocalServer.listen` failure)
```python
try:
    # attempt resource acquisition
    ...
except Exception as e:
    _log.warning("subsystem disabled: %s", e)
    return SafeFallback()
```

### Bound-Method Signal Connections (QA-05)
**Source:** `musicstreamer/ui_qt/main_window.py:213-227` — every `.connect(self._on_*)` is a bound method, never a `lambda: self.do_thing()`
**Apply to:** All Qt signal wiring in new code. The single permitted lambda is parameter-only (closure over a non-self var), e.g. `socket.readyRead.connect(lambda: self._drain(socket))` — captures `socket`, not `self`.

### Copywriting (Unicode Escapes)
**Source:** `musicstreamer/ui_qt/main_window.py:306, 319, 330` — `…` for ellipsis
**Apply to:** New menu actions and toasts. The Node-missing menu uses `⚠` (warning sign). Keep escapes literal (not the raw character) — matches existing convention.

### Module Docstring Convention
**Source:** every existing module — single triple-quoted string starting with the module's purpose, followed by a blank line and bullet/sub-section detail
**Apply to:** `single_instance.py`, `runtime_check.py`, `__version__.py`, every new test file
**Example (already drafted in RESEARCH §Pattern 2):** see `single_instance.py` block above.

### Constants-At-Top Convention
**Source:** `musicstreamer/media_keys/base.py:22` (`_VALID_STATES`), `subprocess_utils.py` (no constants but flat-helper structure)
**Apply to:** `SERVER_NAME`, `_CONNECT_TIMEOUT_MS` in `single_instance.py`; `NODEJS_INSTALL_URL` in `runtime_check.py`. Public constants get no underscore; private get `_`.

### Test Module Docstring + qtbot Fixture
**Source:** `tests/test_media_keys_scaffold.py:1-13`
**Apply to:** `test_single_instance.py`, `test_runtime_check.py`, both `tests/ui_qt/test_*.py` files.

### Test sys.platform Monkeypatch
**Source:** `tests/test_media_keys_scaffold.py:67-82`
```python
def test_xxx_on_win32(monkeypatch, qtbot):
    monkeypatch.setattr(sys, "platform", "win32")
    # ...
```
**Apply to:** `test_runtime_check.py::test_which_node_prefers_exe_on_windows`.

---

## No Analog Found

| File | Role | Data Flow | Reason | Fallback Source |
|------|------|-----------|--------|-----------------|
| `packaging/windows/MusicStreamer.iss` | config (Pascal-style installer script) | build-time | First Inno Setup script in repo | RESEARCH §Pattern 1 — full canonical skeleton (80 lines) |
| `packaging/windows/EULA.txt` | text content | n/a | First EULA in repo | RESEARCH §Pattern 8 — drafted text (~20 lines) |
| `packaging/windows/icons/MusicStreamer.ico` | binary asset | n/a | First multi-res .ico in repo | RESEARCH §Pattern 7 — `magick ... -define icon:auto-resize=...` |
| `musicstreamer/__version__.py` | config (single literal) | n/a | Trivially new (4-line module) | RESEARCH §Pattern 6 |
| `tests/test_spec_hidden_imports.py` | test (text grep over `.spec`) | unit | First spec-content test | Plan author's discretion — `Path(...).read_text()` + `assert "PySide6.QtNetwork" in spec_text` |

---

## Metadata

**Analog search scope:**
- `musicstreamer/` — all submodules (factory + flat-helper conventions)
- `musicstreamer/ui_qt/main_window.py` — controller patterns
- `musicstreamer/media_keys/` — Qt + factory + degradation reference
- `tests/` — pytest-qt + monkeypatch idioms
- `.planning/phases/43-gstreamer-windows-spike/` — verbatim-copy artifacts (D-17)
- `.planning/phases/43.1-windows-media-keys-smtc/` — UAT doc style + AUMID reference
- `.claude/skills/spike-findings-musicstreamer/` — validated landmines (UPX, gioopenssl/libgiognutls dual path, scanner bin/libexec dual path, named-pipe behavior)

**Files scanned:** 14 source/test files read; 2 phase-43 artifacts read in full; phase-44 RESEARCH.md sections 1-1100 read.

**Pattern extraction date:** 2026-04-25
