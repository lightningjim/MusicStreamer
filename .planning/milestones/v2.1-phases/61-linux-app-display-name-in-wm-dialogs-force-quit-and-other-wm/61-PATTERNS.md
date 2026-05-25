# Phase 61: Linux App Display Name in WM Dialogs - Pattern Map

**Mapped:** 2026-05-05
**Files analyzed:** 11 (3 NEW, 5 MODIFY, 1 RENAME, 1 DELETE-implied, plus diagnostic artifact)
**Analogs found:** 9 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/desktop_install.py` (NEW) | service / first-launch helper | file-I/O + subprocess best-effort | `musicstreamer/migration.py` | exact (same role: marker-guarded one-shot first-launch routine; same imports — `os`, `shutil`, `pathlib`, `paths`) |
| `tests/test_desktop_install.py` (NEW) | test | file-I/O fixture | `tests/test_migration.py` | exact (same role + data flow: `tmp_path` + `monkeypatch` of `paths._root_override`) |
| `tests/test_constants_drift.py` (NEW) | test (drift-guard) | static file inspection | `tests/test_aumid_string_parity.py` | exact (same role: literal-parity guard between two repo locations; both regex/grep-style assertions) |
| `musicstreamer/__main__.py` (MODIFY) | controller / process-startup wiring | request-response (Qt init + GST init) | self (existing `_run_gui` / `_set_windows_aumid`) | self-modify — pull `from musicstreamer import constants`, swap literal for `constants.APP_ID`, add `setApplicationDisplayName`, insert `desktop_install.ensure_installed()` call |
| `musicstreamer/constants.py` (MODIFY) | config / single-source-of-truth literal | static | self (line 17) | self-modify — single-line rename of `APP_ID` literal |
| `musicstreamer/media_keys/mpris2.py` (MODIFY) | D-Bus adaptor / property getter | request-response (D-Bus property query) | self (line 102-104) | self-modify — single-line property body change |
| `Makefile` (MODIFY) | build/install script | file-I/O (`install -Dm644`) | self (lines 5-6, 32, 43) | self-modify — three literal renames + one path repoint |
| `org.example.MusicStreamer.desktop` (RENAME) → `packaging/linux/org.lightningjim.MusicStreamer.desktop` | repo asset (XDG `.desktop` file) | static text | self (current content) | self-modify — rename, relocate, audit `Categories=` |
| `61-DIAGNOSTIC-LOG.md` (NEW artifact) | docs / UAT readback | n/a | `.planning/phases/56-windows-di-fm-smtc-start-menu/56-03-DIAGNOSTIC-LOG.md` | exact (same artifact convention) |

**No-analog category:** None — every file has a matched analog. The closest "no-analog" candidate would have been an icon-cache/desktop-database refresh helper, but the chosen pattern (best-effort subprocess wrapped in try/except, no helper module) reuses stdlib + existing patterns from `subprocess_utils.py` shape.

---

## Pattern Assignments

### `musicstreamer/desktop_install.py` (NEW — service, file-I/O + subprocess best-effort)

**Analog:** `musicstreamer/migration.py` (exact match: marker-guarded one-shot first-launch routine).

**Imports pattern** (`migration.py:16-22`):

```python
"""First-launch data migration helper (PORT-06, D-14..D-16).

Behaviour:
...
* The marker file (``.platformdirs-migrated``) makes the helper idempotent:
  re-invocations are a single ``os.path.exists`` check.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from musicstreamer import paths
```

→ For `desktop_install.py` add `subprocess`, `sys`, `tempfile`, `logging`, and `from musicstreamer import constants` (the new module needs `constants.APP_ID` for the install basenames). Module docstring follows the same "Phase 61 / D-09" header convention.

**Marker-guarded entry-point pattern** (`migration.py:28-45`):

```python
def run_migration() -> None:
    marker = paths.migration_marker()
    if os.path.exists(marker):
        return

    dest = paths.data_dir()
    os.makedirs(dest, exist_ok=True)

    src = _LEGACY_LINUX
    # Same path → nothing to copy. Linux v1.5 → v2.0 is this branch.
    if os.path.isdir(src) and os.path.realpath(src) == os.path.realpath(dest):
        _write_marker(marker)
        return

    if os.path.isdir(src):
        _copy_tree_nondestructive(src, dest)

    _write_marker(marker)
```

→ For `desktop_install.ensure_installed()`: same marker-check-then-do-then-write pattern. Replace `paths.migration_marker()` with a sibling `paths.data_dir() / ".desktop-installed-v1"`. Add a `sys.platform.startswith("linux")` early-return at the top (the inverse of `_set_windows_aumid`'s `if sys.platform != "win32": return` guard at `__main__.py:113`). Wrap the body in try/except per RESEARCH.md Pattern 2 — log warning + early-return on failure (no marker write) so next launch retries.

**Atomic marker-write pattern** (`migration.py:65-66`):

```python
def _write_marker(path: str) -> None:
    Path(path).write_text("platformdirs migration complete\n")
```

→ For `desktop_install._write_marker()`: upgrade to atomic `tmp + os.replace` per RESEARCH Pattern 2 (lines 436-445 of RESEARCH.md). The migration helper's plain `Path.write_text` is acceptable for an idempotent marker, but RESEARCH.md explicitly recommends atomic for the desktop-install marker because mid-launch crashes are more plausible (Qt init can fail). Code excerpt below comes from RESEARCH.md and is copy-paste-ready:

```python
# From RESEARCH.md Example (Pattern 2)
def _write_marker(marker: Path) -> None:
    """Atomically write the install marker."""
    marker.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=str(marker.parent), prefix=f".{marker.name}.",
        delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(f"desktop install v1 complete; app_id={constants.APP_ID}\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, marker)
```

**File-copy with mode preservation** (`migration.py:62`):

```python
shutil.copy2(s, d)
```

→ For `desktop_install`: same `shutil.copy2(src, dst)` for both `.desktop` and `.png`. RESEARCH.md upgrades this to a `_atomic_copy()` helper that writes via `tempfile.NamedTemporaryFile` then `os.replace` — that pattern is documented in RESEARCH.md Pattern 2 lines 404-415 and should be copied verbatim.

**Existing-file preservation pattern** (`migration.py:61`):

```python
if not os.path.exists(d):
    shutil.copy2(s, d)
```

→ Identical guard for `desktop_install`: skip the copy if the destination already exists. This is what makes the routine safe against pre-existing user-installed files (Pitfall 3 / D-11 additive-only). The matching test mirrors `test_migration.py::test_migration_preserves_existing_dest_files` (lines 69-82).

**Best-effort subprocess pattern** (no direct analog file, but pattern shape established by `subprocess_utils.py`):

`subprocess_utils.py` is a thin wrapper, not a best-effort helper, but it documents the project convention to centralize subprocess. RESEARCH.md Pattern 2 defines the exact `_best_effort()` helper to copy:

```python
# From RESEARCH.md (Pattern 2 — proposed implementation)
def _best_effort(cmd: list[str]) -> None:
    """Run cmd; log failure but never raise."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            _log.debug(
                "%s exit %d: %s", cmd[0], result.returncode, result.stderr.strip()
            )
    except FileNotFoundError:
        _log.debug("%s not found on PATH — skipping cache refresh", cmd[0])
    except subprocess.TimeoutExpired:
        _log.debug("%s timed out — skipping", cmd[0])
    except Exception as exc:  # noqa: BLE001
        _log.debug("%s raised %s — skipping", cmd[0], exc)
```

→ Copy verbatim. Used for D-13 `update-desktop-database` and `gtk-update-icon-cache` calls. Note: `cmd` is `list[str]` and `shell=False` (default) — matches the project's mitigation against subprocess command-injection (RESEARCH.md Security Domain).

**Logger convention** (project-wide — used in `mpris2.py:52`, `aa_import.py`, `single_instance.py:27`):

```python
_log = logging.getLogger(__name__)
```

→ Same one-liner at module scope.

---

### `tests/test_desktop_install.py` (NEW — test, file-I/O fixture)

**Analog:** `tests/test_migration.py` (exact match: same `tmp_path` + `monkeypatch._root_override` shape).

**Imports + autouse fixture pattern** (`test_migration.py:1-16`):

```python
"""Tests for musicstreamer.migration — first-launch non-destructive migration."""
import os

import pytest

from musicstreamer import migration, paths


@pytest.fixture(autouse=True)
def _reset_root_override():
    saved = paths._root_override
    saved_legacy = migration._LEGACY_LINUX
    paths._root_override = None
    yield
    paths._root_override = saved
    migration._LEGACY_LINUX = saved_legacy
```

→ For `test_desktop_install.py` adapt the autouse fixture to:
1. Set `paths._root_override = str(tmp_path / "data")` so the marker lands under tmp.
2. `monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg_data"))` so `_xdg_data_home()` resolves under tmp.
3. Save/restore both, plus any module-level paths in `desktop_install` (e.g., `_BUNDLED_DESKTOP`, `_BUNDLED_ICON`) — same mechanic as `migration._LEGACY_LINUX` save/restore.

**Test-case happy path** (`test_migration.py:19-23`):

```python
def test_migration_same_path_writes_marker_and_returns(tmp_path):
    paths._root_override = str(tmp_path)
    migration._LEGACY_LINUX = str(tmp_path)
    migration.run_migration()
    assert os.path.exists(paths.migration_marker())
```

→ Mirror as `test_first_launch_installs_files` (writes both `.desktop` and `.png` under XDG, plus the marker). RESEARCH.md test examples (lines 487-497) are copy-paste-ready.

**Idempotency test pattern** (`test_migration.py:44-66`):

```python
def test_migration_idempotent_via_marker(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "musicstreamer.sqlite3").write_bytes(b"DB")
    paths._root_override = str(dst)
    migration._LEGACY_LINUX = str(src)

    write_calls = {"n": 0}
    real_write = migration._write_marker

    def spy(p):
        write_calls["n"] += 1
        real_write(p)

    migration._write_marker = spy
    try:
        migration.run_migration()
        migration.run_migration()
    finally:
        migration._write_marker = real_write

    assert write_calls["n"] == 1
```

→ For `test_idempotent_via_marker`: simpler shape — call `ensure_installed()` twice, delete the installed `.desktop` between calls, assert it is NOT recreated (the marker prevents re-install). RESEARCH.md test pattern lines 500-508.

**Existing-file preservation test pattern** (`test_migration.py:69-82`):

```python
def test_migration_preserves_existing_dest_files(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "cookies.txt").write_bytes(b"OLD")
    (dst / "cookies.txt").write_bytes(b"KEEP")
    paths._root_override = str(dst)
    migration._LEGACY_LINUX = str(src)

    migration.run_migration()

    assert (dst / "cookies.txt").read_bytes() == b"KEEP"
```

→ Mirror as `test_existing_files_preserved` — pre-create a fake user-modified `.desktop` file under XDG `applications/`; assert that `ensure_installed()` does NOT clobber the user's content. RESEARCH.md test pattern lines 518-526.

**Mode-preservation note** (`test_migration.py:85-100`):

`test_migration` covers 0o600 mode preservation for cookies/tokens. **Not relevant for desktop_install** — the `.desktop` file and PNG are public-readable assets; default mode bits (0644) are correct. No mode-preservation test needed.

**Additional Wave 0 tests required** (no direct analog — write fresh from RESEARCH.md examples):
- `test_no_op_off_linux` — monkeypatch `desktop_install.sys.platform = "win32"`, assert no marker / no install.
- `test_cache_hooks_called_best_effort` — monkeypatch `desktop_install.subprocess.run`, capture call list, assert both `update-desktop-database` and `gtk-update-icon-cache` invoked.
- `test_missing_cache_tool_does_not_raise` — fake `subprocess.run` raises `FileNotFoundError`; assert `ensure_installed()` does not raise AND marker still written.

RESEARCH.md provides full source for all six tests at lines 487-551.

---

### `tests/test_constants_drift.py` (NEW — test, static file inspection)

**Analog:** `tests/test_aumid_string_parity.py` (exact role match: literal-parity guard between two repo locations; both rely on `pathlib.Path` + regex/grep-style assertions; both ship to fail-loud on rename drift).

**Imports + repo-root resolution pattern** (`test_aumid_string_parity.py:1-17`):

```python
"""Phase 56 / D-09 #3: AUMID literal parity between __main__.py and MusicStreamer.iss.

A typo in either file silently breaks the SMTC overlay binding without any
runtime error or Linux-CI test failure. This guard catches drift at unit-test
time (Linux-CI safe -- no Windows dependency).

Mitigates T-56-02 (Tampering: silent AUMID drift causes packaging regression).
"""
import re
from pathlib import Path


def test_aumid_string_parity():
    """D-09 #3: __main__.py and MusicStreamer.iss must declare the same AUMID literal."""
    repo_root = Path(__file__).parent.parent
    main_py = (repo_root / "musicstreamer" / "__main__.py").read_text()
    iss = (repo_root / "packaging" / "windows" / "MusicStreamer.iss").read_text()
```

→ For `test_constants_drift.py`: same docstring shape ("Phase 61 / D-02 drift guard…"), same `repo_root = Path(__file__).parent.parent` idiom, same fail-loud assertion style.

**Test-case shape** (`test_aumid_string_parity.py:13-31`):

```python
def test_aumid_string_parity():
    """D-09 #3: __main__.py and MusicStreamer.iss must declare the same AUMID literal."""
    repo_root = Path(__file__).parent.parent
    main_py = (repo_root / "musicstreamer" / "__main__.py").read_text()
    iss = (repo_root / "packaging" / "windows" / "MusicStreamer.iss").read_text()
    main_match = re.search(r'app_id:\s*str\s*=\s*"([^"]+)"', main_py)
    iss_match = re.search(r'AppUserModelID:\s*"([^"]+)"', iss)
    assert main_match is not None, ...
    assert iss_match is not None, ...
    assert main_match.group(1) == iss_match.group(1), (
        f"AUMID drift: __main__.py='{main_match.group(1)}' "
        f"iss='{iss_match.group(1)}'"
    )
```

→ The Phase 61 drift-guard tests are simpler than this — they assert file-existence (e.g., `packaging/linux/<APP_ID>.desktop` exists) rather than regex-matched literals across files. Use RESEARCH.md Example 7 (lines 866-916) verbatim for all four tests:
1. `test_app_id_is_lightningjim_and_matches_phase_56_aumid` — pure equality check on `constants.APP_ID`.
2. `test_bundled_desktop_basename_matches_app_id` — `Path.exists()` check.
3. `test_bundled_icon_basename_matches_app_id` — `Path.exists()` check.
4. `test_no_org_example_literal_remains_in_python_sources` — `Path.rglob("*.py")` + `"org.example.MusicStreamer" in text` scan.

The `_aumid` test in `test_aumid_string_parity.py` becomes obsolete after Phase 61 IF the drift-guard test #1 above asserts the AUMID and `__main__.py` literal in lockstep — but per D-02 (single-source via `constants.APP_ID`) the `__main__.py` literal goes away, so `test_aumid_string_parity` itself drifts. **Planner note:** flag `test_aumid_string_parity.py` for either deletion (the drift guard now covers `constants.APP_ID` ↔ `MusicStreamer.iss`) or update (regex pattern in `__main__.py` changes from `app_id: str = "..."` to a `constants.APP_ID` reference). Either way, this is a known-impact site that needs explicit handling.

---

### `musicstreamer/__main__.py` (MODIFY — controller / process-startup wiring)

**Analog:** self (existing `_run_gui` and `_set_windows_aumid` already establish the patterns to extend).

**Existing platform-guard pattern** (`__main__.py:113-114`):

```python
if sys.platform != "win32":
    return
```

→ The new `desktop_install.ensure_installed()` body uses the inverse guard `if not sys.platform.startswith("linux"): return`. Same shape, opposite direction.

**Existing Qt application setup block** (`__main__.py:142-144`):

```python
app = QApplication(argv)
app.setApplicationName("MusicStreamer")
app.setDesktopFileName("org.example.MusicStreamer")
```

→ Modified to (per RESEARCH.md Example 2):

```python
from musicstreamer import constants  # add at module top

app = QApplication(argv)
app.setApplicationName("MusicStreamer")              # D-07: keep
app.setApplicationDisplayName("MusicStreamer")       # D-06: NEW
app.setDesktopFileName(constants.APP_ID)             # D-02: read from constants (no .desktop suffix per Qt convention)
```

**Existing AUMID setter signature** (`__main__.py:99`):

```python
def _set_windows_aumid(app_id: str = "org.lightningjim.MusicStreamer") -> None:
```

→ Modified to read `constants.APP_ID` instead of carrying the hardcoded default (D-02). RESEARCH.md Example 2:

```python
from musicstreamer import constants  # already added at top per above

def _set_windows_aumid(app_id: str | None = None) -> None:
    if app_id is None:
        app_id = constants.APP_ID
    if sys.platform != "win32":
        return
    ...
```

**Existing `_run_gui` startup ordering** (`__main__.py:128-134`):

```python
def _run_gui(argv: list[str]) -> int:
    """Open the Qt GUI — QApplication + MainWindow."""
    _set_windows_aumid()  # Phase 43.1: before QApplication (binds on first window)
    Gst.init(None)

    from musicstreamer import migration
    migration.run_migration()
```

→ Modified to (per RESEARCH.md Example 3):

```python
def _run_gui(argv: list[str]) -> int:
    """Open the Qt GUI — QApplication + MainWindow."""
    _set_windows_aumid()
    Gst.init(None)

    from musicstreamer import desktop_install   # NEW (D-09)
    desktop_install.ensure_installed()          # NEW

    from musicstreamer import migration
    migration.run_migration()
```

The pattern for "lazy import inside `_run_gui`" is established (line 133, 137-140, 152, 160) — keep `desktop_install` imported lazily for symmetry with `migration`.

---

### `musicstreamer/constants.py` (MODIFY — config / single literal)

**Analog:** self (line 17).

**Current** (`constants.py:17`):

```python
APP_ID = "org.example.MusicStreamer"
```

**After Phase 61** (per RESEARCH.md Example 1):

```python
APP_ID = "org.lightningjim.MusicStreamer"
```

Single-line edit. No imports change. Module docstring (lines 1-12) stays unchanged.

---

### `musicstreamer/media_keys/mpris2.py` (MODIFY — D-Bus adaptor / property getter)

**Analog:** self (lines 102-104) — existing `DesktopEntry` property.

**Current** (`mpris2.py:102-104`):

```python
@Property(str)
def DesktopEntry(self) -> str:
    return "org.example.MusicStreamer"
```

**After Phase 61** (per RESEARCH.md Example 4):

```python
@Property(str)
def DesktopEntry(self) -> str:
    return constants.APP_ID
```

**Import addition** — add `from musicstreamer import constants` at the top of the file. Existing imports at `mpris2.py:48-50` already use the `from musicstreamer.media_keys.X import Y` style; the new `from musicstreamer import constants` follows the same convention:

```python
from musicstreamer.media_keys._art_cache import write_cover_png
from musicstreamer.media_keys.base import MediaKeysBackend
from musicstreamer.models import Station
# ADD:
from musicstreamer import constants
```

**Note:** `IFACE_ROOT`, `IFACE_PLAYER`, `SERVICE_NAME`, `OBJECT_PATH` constants at `mpris2.py:54-57` are **NOT touched** — they follow the MPRIS spec, not the reverse-DNS app id (D-04).

---

### `Makefile` (MODIFY — build/install script)

**Analog:** self (lines 5-6, 32, 43).

**Current**:

```makefile
DESKTOP_FILE = org.example.MusicStreamer.desktop
ICON_FILE    = musicstreamer/assets/org.example.MusicStreamer.svg
```

(line 32) `install -Dm644 $(ICON_FILE) $(ICON_DIR)/org.example.MusicStreamer.svg`
(line 43) `rm -f $(ICON_DIR)/org.example.MusicStreamer.svg`

**After Phase 61**:

```makefile
DESKTOP_FILE = org.lightningjim.MusicStreamer.desktop
DESKTOP_SRC  = packaging/linux/$(DESKTOP_FILE)   # if relocated per Claude's discretion
ICON_FILE    = packaging/linux/org.lightningjim.MusicStreamer.png
ICON_DIR     = $(PREFIX)/share/icons/hicolor/256x256/apps   # bucket repoint (was /scalable/)
```

(line 30 and 32 install targets) repoint to the new file basenames + the 256x256 bucket.
(line 43 uninstall target) repoint to the new icon basename (`.png`, not `.svg`).

**Why the changes:** RESEARCH.md Pitfall 1 + Open Question #10 — the Makefile references an SVG that has never existed in the repo; the only icon is the PNG at `packaging/linux/org.lightningjim.MusicStreamer.png`. The rename is mostly mechanical, but planner must also fix the `.svg` → `.png` bug and the `/scalable/` → `/256x256/` bucket.

---

### `packaging/linux/org.lightningjim.MusicStreamer.desktop` (RENAME from repo root)

**Analog:** self (current `org.example.MusicStreamer.desktop` content at repo root).

**Current content** (`org.example.MusicStreamer.desktop`):

```ini
[Desktop Entry]
Type=Application
Name=MusicStreamer
GenericName=Internet Radio
Exec=musicstreamer
Icon=org.lightningjim.MusicStreamer
Categories=Audio;Music;Network;
Comment=Internet radio stream player
Keywords=radio;stream;music;internet;
StartupNotify=true
StartupWMClass=MusicStreamer
```

**After Phase 61** — content unchanged except (per RESEARCH.md Example 5 + Pitfall 7):
- (Optional, low-priority hygiene) `Categories=AudioVideo;Audio;Music;Network;` — registers under the umbrella `AudioVideo` main category for cross-DE breadth. RESEARCH.md notes the current value is technically valid (`Audio` is a registered main category since freedesktop 1.0) and the upgrade is a hygiene win, not a bug fix. **Audit-and-decide during the rename plan.**
- File **renamed and relocated** to `packaging/linux/org.lightningjim.MusicStreamer.desktop` (repo-root path retired).
- `Exec=musicstreamer` kept as-is — works for `uv run` from a venv-active shell; the assumption is documented in RESEARCH.md A7.

**Drift-guard locks the basename**: `tests/test_constants_drift.py::test_bundled_desktop_basename_matches_app_id` asserts `packaging/linux/{constants.APP_ID}.desktop` exists. If a contributor renames either side without the other, the test fails loud.

---

### `61-DIAGNOSTIC-LOG.md` (NEW artifact — UAT readback)

**Analog:** `.planning/phases/56-windows-di-fm-smtc-start-menu/56-03-DIAGNOSTIC-LOG.md` (exact convention match — Phase 56 D-07/D-08 diagnose-first artifact pattern).

**Pattern:** Two sections — PRE-FIX (run before code change ships) and POST-FIX (run after Wave-N implementation, captured during UAT). Commands enumerated in RESEARCH.md Example 6 (lines 775-855). All commands work without elevated privileges; verified present on Kyle's rig (2026-05-05).

**X11/Wayland branch** (RESEARCH.md Pitfall 8): the diagnostic includes a session-type check first; if `XDG_SESSION_TYPE=wayland`, the user must log into "GNOME on Xorg" before the WM_CLASS readout works.

---

## Shared Patterns

### Pattern A: Logger initialization at module scope

**Source:** `musicstreamer/media_keys/mpris2.py:52`, `musicstreamer/single_instance.py:27`, `musicstreamer/migration.py` (does not log — but the project pattern is established universally elsewhere).

**Apply to:** `musicstreamer/desktop_install.py` (NEW)

```python
import logging
_log = logging.getLogger(__name__)
```

### Pattern B: Lazy module imports inside `_run_gui`

**Source:** `musicstreamer/__main__.py:133` (`from musicstreamer import migration`), 137-140 (Qt + UI imports), 152 (`from musicstreamer import single_instance`), 160 (`from musicstreamer import runtime_check`).

**Apply to:** `musicstreamer/__main__.py` insertion of `from musicstreamer import desktop_install` — keep lazy for symmetry with `migration` and to avoid unconditionally loading on `_run_smoke` paths.

### Pattern C: `sys.platform` early-return guard

**Source:** `musicstreamer/__main__.py:113-114` (Windows-only AUMID setter), throughout `media_keys/` and `subprocess_utils.py:16`.

**Apply to:** `musicstreamer/desktop_install.py` (Linux-only — inverse direction):

```python
if not sys.platform.startswith("linux"):
    return
```

### Pattern D: Marker-guarded one-shot first-launch

**Source:** `musicstreamer/migration.py:28-45` — read marker, return early if exists; do work; write marker.

**Apply to:** `musicstreamer/desktop_install.py` (`ensure_installed()` body).

**Marker location convention:** under `paths.data_dir()` (which routes through `paths._root_override` for tests). For desktop install, use `Path(paths.data_dir()) / ".desktop-installed-v1"` — same shape as `paths.migration_marker()` returning `os.path.join(_root(), ".platformdirs-migrated")`. The version suffix (`-v1`) is forward-looking: if Phase 6X bumps the bundled `.desktop` content (e.g., new `Exec=` for a packaged install), the marker bumps to `-v2` to force re-install.

### Pattern E: Tests use `tmp_path` + `monkeypatch._root_override` for path-isolation

**Source:** `tests/test_migration.py:9-17` — autouse fixture saves/restores `paths._root_override`; tests redirect by assigning `paths._root_override = str(tmp_path / "...")`.

**Apply to:** `tests/test_desktop_install.py` (NEW). Add `monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg_data"))` for the install destinations on top of the `_root_override` redirection for the marker.

### Pattern F: Static drift-guard test (file existence + literal scan)

**Source:** `tests/test_aumid_string_parity.py:13-31` — `repo_root = Path(__file__).parent.parent`, regex-extract literals, assert equality.

**Apply to:** `tests/test_constants_drift.py` (NEW). Same `repo_root` idiom; simplified to `Path.exists()` + literal-presence checks. Four tests per RESEARCH.md Example 7.

**Cross-cutting decision:** `tests/test_aumid_string_parity.py` itself becomes brittle after Phase 61 (the regex `app_id:\s*str\s*=\s*"([^"]+)"` no longer matches `__main__.py` once the literal is replaced by `constants.APP_ID`). Planner must explicitly handle: (a) delete the test (the new drift-guard fully covers the AUMID parity via `constants.APP_ID`), or (b) update the regex to point at `constants.py` and `MusicStreamer.iss`. **Recommend (a) — `test_constants_drift.py::test_app_id_is_lightningjim_and_matches_phase_56_aumid` covers it**.

### Pattern G: `from musicstreamer import constants` import line

**Source:** `musicstreamer/migration.py:22` (`from musicstreamer import paths`), `musicstreamer/single_instance.py` style, project-wide convention.

**Apply to:** `musicstreamer/__main__.py`, `musicstreamer/media_keys/mpris2.py`, `musicstreamer/desktop_install.py` — all need `from musicstreamer import constants` to read `constants.APP_ID`. Place under the existing `from musicstreamer.X import Y` block in each file (alphabetical by submodule is the project's tendency but not strict).

---

## No Analog Found

None — every file in the phase has a strong analog. The closest "no analog" topics are:
- **Linux WM coverage in project skills** — `.claude/skills/spike-findings-musicstreamer/` exists but is Windows-only (gstreamer-bundling, qt-glib-bus-threading, PowerShell). RESEARCH.md confirms no Linux-WM coverage in the skill (line 87). **Implication for the planner:** no skill-loaded reference rules to consult; rely on RESEARCH.md sources directly.
- **Best-effort subprocess helper** — no project-level `_best_effort()` exists yet; `subprocess_utils.py` is a Windows console-flash mitigation stub, not a fault-tolerant runner. RESEARCH.md Pattern 2 fully specifies the helper inline; copy verbatim into `desktop_install.py` (do NOT factor out into `subprocess_utils.py` — RESEARCH.md scopes the helper module-local).

---

## Metadata

**Analog search scope:**
- `musicstreamer/` (all `.py` files — ~30 modules)
- `tests/` (all `test_*.py` files — ~70 test modules)
- `packaging/linux/` (icon asset)
- Repo root (`.desktop` file, `Makefile`)
- `.planning/phases/56-*/` (Phase 56 diagnostic-log artifact convention)
- `.claude/skills/` (Windows-only — no Linux match)

**Files scanned in detail:**
- `musicstreamer/migration.py` (full read — primary analog)
- `tests/test_migration.py` (full read — primary test analog)
- `tests/test_aumid_string_parity.py` (full read — drift-guard analog)
- `musicstreamer/__main__.py` (full read — modification target)
- `musicstreamer/constants.py` (full read — modification target)
- `musicstreamer/media_keys/mpris2.py` (lines 1-130 — modification target)
- `musicstreamer/paths.py` (full read — supporting context for marker location)
- `musicstreamer/subprocess_utils.py` (lines 1-19 — convention reference, not a direct analog)
- `musicstreamer/single_instance.py` (lines 1-40 — module-doc and SERVER_NAME convention reference)
- `org.example.MusicStreamer.desktop` (full read — content baseline for rename)
- `Makefile` (full read — drift sites)
- `.planning/phases/61-*/61-CONTEXT.md` (full read — phase scope)
- `.planning/phases/61-*/61-RESEARCH.md` (full read — research-driven excerpts)

**Pattern extraction date:** 2026-05-05
**Phase directory:** `.planning/phases/61-linux-app-display-name-in-wm-dialogs-force-quit-and-other-wm/`
