---
phase: 35-backend-isolation
plan: 02
type: execute
wave: 2
depends_on: [35-01]
files_modified:
  - musicstreamer/paths.py
  - musicstreamer/migration.py
  - musicstreamer/constants.py
  - musicstreamer/assets.py
  - musicstreamer/repo.py
  - musicstreamer/ui/accounts_dialog.py
  - musicstreamer/ui/edit_dialog.py
  - musicstreamer/ui/main_window.py
  - musicstreamer/ui/station_row.py
  - tests/test_paths.py
  - tests/test_migration.py
autonomous: true
requirements: [PORT-05, PORT-06]
must_haves:
  truths:
    - "Every data-path access in musicstreamer/ resolves through musicstreamer.paths (no hard-coded ~/.local/share/musicstreamer literals)"
    - "First-launch migration helper runs non-destructively and leaves a .platformdirs-migrated marker"
    - "Tests can monkeypatch the data root to a tmp_path without touching the real home directory"
  artifacts:
    - path: "musicstreamer/paths.py"
      provides: "Single source of truth for data_dir / db_path / cookies_path / twitch_token_path / assets_dir / accent_css_path / migration_marker"
      exports: ["data_dir", "db_path", "assets_dir", "cookies_path", "twitch_token_path", "accent_css_path", "migration_marker"]
      min_lines: 30
    - path: "musicstreamer/migration.py"
      provides: "run_migration() — non-destructive first-launch copy + marker"
      exports: ["run_migration"]
    - path: "tests/test_paths.py"
      provides: "Monkeypatch-based tests confirming root override + each path accessor"
    - path: "tests/test_migration.py"
      provides: "Tests for same-path no-op, different-path copy, and idempotency via marker"
  key_links:
    - from: "musicstreamer/constants.py"
      to: "musicstreamer.paths"
      via: "module-level delegation (DATA_DIR = paths.data_dir(), etc.)"
      pattern: "from musicstreamer.paths import|from musicstreamer import paths"
    - from: "musicstreamer/migration.py"
      to: "musicstreamer.paths.migration_marker"
      via: "marker file write"
      pattern: "migration_marker"
---

<objective>
Centralize all MusicStreamer data-path resolution through a single `musicstreamer/paths.py` helper rooted at `platformdirs.user_data_dir("musicstreamer")` (D-12, D-13), add a non-destructive first-launch migration helper (`musicstreamer/migration.py`, D-14..D-16), and rewrite every hard-coded `~/.local/share/musicstreamer` literal in the codebase to route through those helpers.

Purpose: Satisfy PORT-05 (platformdirs everywhere) and PORT-06 (non-destructive migration with marker) before Plan 35-03 ports `yt_import.py` and Plan 35-04 rewrites `player.py`. Both downstream plans depend on the new `paths.cookies_path()` / `paths.twitch_token_path()` helpers.

Output:
- `musicstreamer/paths.py` — 7 path accessors + test-friendly `_root_override`.
- `musicstreamer/migration.py` — `run_migration()` that writes `.platformdirs-migrated` marker.
- `musicstreamer/constants.py` — refactored: `DATA_DIR`, `DB_PATH`, `ASSETS_DIR`, `COOKIES_PATH`, `TWITCH_TOKEN_PATH` become thin delegates to `paths.py` OR are deleted in favor of direct `paths.*` calls at call sites.
- Every GTK UI call site updated to import from `paths` (minimum-diff — keep re-exports in `constants.py` if that is less churn, Claude's discretion).
- Two new test modules: `tests/test_paths.py`, `tests/test_migration.py`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/35-backend-isolation/35-CONTEXT.md
@.planning/phases/35-backend-isolation/35-RESEARCH.md
@musicstreamer/constants.py
@musicstreamer/assets.py
@musicstreamer/repo.py

<interfaces>
<!-- RESEARCH.md Pattern 4 — paths.py target shape -->
```python
# musicstreamer/paths.py
import os
import platformdirs

_root_override: str | None = None

def _root() -> str:
    return _root_override if _root_override is not None else platformdirs.user_data_dir("musicstreamer")

def data_dir() -> str:        return _root()
def db_path() -> str:         return os.path.join(_root(), "musicstreamer.sqlite3")
def assets_dir() -> str:      return os.path.join(_root(), "assets")
def cookies_path() -> str:    return os.path.join(_root(), "cookies.txt")
def twitch_token_path() -> str: return os.path.join(_root(), "twitch-token.txt")
def accent_css_path() -> str: return os.path.join(_root(), "accent.css")
def migration_marker() -> str: return os.path.join(_root(), ".platformdirs-migrated")
```

<!-- Existing call sites — these all need rewriting -->
<!-- musicstreamer/constants.py lines 4-8 — module-level path literals -->
<!-- musicstreamer/assets.py lines 4,8,9,19,26 — DATA_DIR / ASSETS_DIR -->
<!-- musicstreamer/repo.py lines 5,9 — DB_PATH -->
<!-- musicstreamer/ui/accounts_dialog.py lines 11,51,52,117,150,162,239,240,241,254,255,257,277,278,283,337,338,340,401,402,418,422 — COOKIES_PATH + TWITCH_TOKEN_PATH -->
<!-- musicstreamer/ui/edit_dialog.py lines 12,533,540 — DATA_DIR -->
<!-- musicstreamer/ui/main_window.py lines 16,614,891,920,941 — DATA_DIR -->
<!-- musicstreamer/ui/station_row.py lines 7,30 — DATA_DIR -->
<!-- musicstreamer/__main__.py line 49 — ensure_dirs() creates DATA_DIR -->
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create paths.py + migration.py with tests</name>
  <files>musicstreamer/paths.py, musicstreamer/migration.py, tests/test_paths.py, tests/test_migration.py</files>
  <read_first>.planning/phases/35-backend-isolation/35-RESEARCH.md (Patterns 4 + 5), musicstreamer/constants.py</read_first>
  <behavior>
Tests for `musicstreamer/paths.py`:
- `test_data_dir_uses_platformdirs_default`: With `_root_override=None`, `paths.data_dir()` equals `platformdirs.user_data_dir("musicstreamer")`.
- `test_root_override_redirects_all_accessors`: Monkeypatch `paths._root_override = str(tmp_path)`; then `db_path()`, `assets_dir()`, `cookies_path()`, `twitch_token_path()`, `accent_css_path()`, `migration_marker()` all resolve under `tmp_path`.
- `test_paths_do_no_io_on_import`: Import `musicstreamer.paths` and assert no directories are created (compare `os.listdir(tmp_path)` before and after import, with `_root_override` set). Pure helper — no side effects.
- `test_db_path_filename`: `os.path.basename(paths.db_path()) == "musicstreamer.sqlite3"`.

Tests for `musicstreamer/migration.py`:
- `test_migration_same_path_writes_marker_and_returns`: Monkeypatch `paths._root_override = str(tmp_path)`. Monkeypatch `migration._LEGACY_LINUX = str(tmp_path)` (same path). Call `run_migration()`. Assert `os.path.exists(paths.migration_marker())`.
- `test_migration_different_path_copies_nondestructive`: Legacy src = `tmp_path/"src"` with `musicstreamer.sqlite3` containing `b"DB"`. Dest = `tmp_path/"dst"`. Monkeypatch override to dst, legacy to src. Run. Assert dest has `musicstreamer.sqlite3` with `b"DB"`, marker exists, AND src file still present (non-destructive).
- `test_migration_idempotent_via_marker`: Call `run_migration()` twice. Second call must be a no-op (mtime of marker unchanged between calls, or marker write count == 1 via a patched `_write_marker` spy).
- `test_migration_preserves_existing_dest_files`: Pre-populate dest with `cookies.txt` containing `b"KEEP"`. Src has different `cookies.txt` with `b"OLD"`. Run. Dest `cookies.txt` still `b"KEEP"` (non-destructive: existing dest files are NOT overwritten).
  </behavior>
  <action>
**Step 1 — Write failing tests first (TDD RED).** Create `tests/test_paths.py` and `tests/test_migration.py` implementing every test in `<behavior>` above. Use `pytest` (no Qt fixtures needed — these are pure-Python helpers). Run `pytest tests/test_paths.py tests/test_migration.py` and confirm tests fail with `ModuleNotFoundError` or `AttributeError`.

**Step 2 — Write `musicstreamer/paths.py` (TDD GREEN).** Implement exactly the shape in the `<interfaces>` block. Module MUST import cleanly without creating any directories. `_root_override` is a module-level `str | None = None`.

**Step 3 — Write `musicstreamer/migration.py`.** Implement `run_migration()` per RESEARCH.md Pattern 5:
```python
from __future__ import annotations
import os, shutil
from pathlib import Path
from musicstreamer import paths

_LEGACY_LINUX = os.path.expanduser("~/.local/share/musicstreamer")

def run_migration() -> None:
    marker = paths.migration_marker()
    if os.path.exists(marker):
        return
    dest = paths.data_dir()
    os.makedirs(dest, exist_ok=True)
    src = _LEGACY_LINUX
    if os.path.realpath(src) == os.path.realpath(dest):
        _write_marker(marker)
        return
    if os.path.isdir(src):
        _copy_tree_nondestructive(src, dest)
    _write_marker(marker)

def _copy_tree_nondestructive(src: str, dst: str) -> None:
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target_dir = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(target_dir, exist_ok=True)
        for f in files:
            s = os.path.join(root, f)
            d = os.path.join(target_dir, f)
            if not os.path.exists(d):
                shutil.copy2(s, d)

def _write_marker(path: str) -> None:
    Path(path).write_text("platformdirs migration complete\n")
```

**Step 4 — Run tests (TDD GREEN).** `pytest tests/test_paths.py tests/test_migration.py -x` must pass.

Do NOT touch constants.py or any call sites in this task — that is Task 2. This task stands alone so the tests can run before any other file is edited.
  </action>
  <verify>
    <automated>pytest tests/test_paths.py tests/test_migration.py -x</automated>
  </verify>
  <acceptance_criteria>
- `test -f musicstreamer/paths.py` exits 0
- `test -f musicstreamer/migration.py` exits 0
- `grep -q "platformdirs.user_data_dir" musicstreamer/paths.py` matches
- `grep -q "_root_override" musicstreamer/paths.py` matches
- `grep -qE "def (data_dir|db_path|assets_dir|cookies_path|twitch_token_path|accent_css_path|migration_marker)" musicstreamer/paths.py` matches all 7 (verify with: `grep -cE "^def (data_dir|db_path|assets_dir|cookies_path|twitch_token_path|accent_css_path|migration_marker)" musicstreamer/paths.py` returns 7)
- `grep -q "def run_migration" musicstreamer/migration.py` matches
- `grep -q ".platformdirs-migrated" musicstreamer/paths.py` matches
- `pytest tests/test_paths.py tests/test_migration.py -x` exits 0
  </acceptance_criteria>
  <done>Both helper modules exist with passing unit tests; no production code else touched yet.</done>
</task>

<task type="auto">
  <name>Task 2: Route constants.py + all call sites through paths.py</name>
  <files>musicstreamer/constants.py, musicstreamer/assets.py, musicstreamer/repo.py, musicstreamer/ui/accounts_dialog.py, musicstreamer/ui/edit_dialog.py, musicstreamer/ui/main_window.py, musicstreamer/ui/station_row.py</files>
  <read_first>musicstreamer/constants.py, musicstreamer/assets.py, musicstreamer/repo.py, musicstreamer/ui/accounts_dialog.py (lines 1-50, 230-260, 395-425), musicstreamer/ui/main_window.py (lines 14-20, 610-620, 885-945), musicstreamer/ui/station_row.py, musicstreamer/ui/edit_dialog.py (lines 1-20, 525-545)</read_first>
  <action>
Replace every hard-coded `~/.local/share/musicstreamer` literal and every `from musicstreamer.constants import DATA_DIR|DB_PATH|ASSETS_DIR|COOKIES_PATH|TWITCH_TOKEN_PATH` with `paths.*` calls. Chosen strategy (minimum churn): **rewrite `constants.py` to re-export from `paths.py` as module-level properties, NOT as snapshot literals**. This keeps call sites that already do `from musicstreamer.constants import DATA_DIR` working without touching them, while ensuring monkeypatching `paths._root_override` in tests actually affects running code.

**Step 1 — Rewrite `musicstreamer/constants.py`:**

```python
import os
from musicstreamer import paths

APP_ID = "org.example.MusicStreamer"

# These are backward-compat shims — new code should import from musicstreamer.paths directly.
# They evaluate on access so tests that monkeypatch paths._root_override still see the override.
def __getattr__(name):
    if name == "DATA_DIR":       return paths.data_dir()
    if name == "DB_PATH":        return paths.db_path()
    if name == "ASSETS_DIR":     return paths.assets_dir()
    if name == "COOKIES_PATH":   return paths.cookies_path()
    if name == "TWITCH_TOKEN_PATH": return paths.twitch_token_path()
    raise AttributeError(f"module 'musicstreamer.constants' has no attribute {name!r}")


def clear_cookies() -> bool:
    p = paths.cookies_path()
    if os.path.exists(p):
        os.remove(p)
        return True
    return False


def clear_twitch_token() -> bool:
    p = paths.twitch_token_path()
    if os.path.exists(p):
        os.remove(p)
        return True
    return False


# GStreamer playbin3 buffer tuning (Phase 16 / STREAM-01) — unchanged
BUFFER_DURATION_S = 10
BUFFER_SIZE_BYTES = 10 * 1024 * 1024

# YouTube mpv minimum wait window (Phase 33 / FIX-07) — unchanged
YT_MIN_WAIT_S = 15

# Quality tiers — unchanged
QUALITY_PRESETS = ("hi", "med", "low")
QUALITY_SETTING_KEY = "preferred_quality"

# Accent color — unchanged
ACCENT_COLOR_DEFAULT = "#3584e4"
ACCENT_PRESETS = [
    "#3584e4", "#2190a4", "#3a944a", "#c88800",
    "#ed5b00", "#e62d42", "#9141ac", "#c64d92",
]
```

The `__getattr__` module-level hook (PEP 562) is required — plain module-level `DATA_DIR = paths.data_dir()` evaluates ONCE at import time and breaks monkeypatching. Every existing `from musicstreamer.constants import DATA_DIR` continues to work but re-evaluates on each access via the hook.

**Step 2 — Rewrite `musicstreamer/assets.py`:** replace `from musicstreamer.constants import DATA_DIR, ASSETS_DIR` with `from musicstreamer import paths`; replace `DATA_DIR` → `paths.data_dir()`, `ASSETS_DIR` → `paths.assets_dir()`. Update the comment on line 14 (`~/.local/share/musicstreamer/assets/...`) to `paths.assets_dir()`. Update `os.path.relpath(dst, DATA_DIR)` → `os.path.relpath(dst, paths.data_dir())`.

**Step 3 — Rewrite `musicstreamer/repo.py`:** replace `from musicstreamer.constants import DB_PATH` with `from musicstreamer import paths`; replace `sqlite3.connect(DB_PATH)` with `sqlite3.connect(paths.db_path())`.

**Step 4 — `musicstreamer/ui/accounts_dialog.py`:** replace `from musicstreamer.constants import COOKIES_PATH, clear_cookies, TWITCH_TOKEN_PATH, clear_twitch_token` with `from musicstreamer.constants import clear_cookies, clear_twitch_token` and add `from musicstreamer import paths`. Replace every `COOKIES_PATH` literal with `paths.cookies_path()`, every `TWITCH_TOKEN_PATH` with `paths.twitch_token_path()`. Because these are called per-method, the function-call overhead is negligible and the monkeypatch path works.

**Step 5 — `musicstreamer/ui/edit_dialog.py`, `musicstreamer/ui/main_window.py`, `musicstreamer/ui/station_row.py`:** same pattern — `from musicstreamer.constants import DATA_DIR` stays (backward-compat via `__getattr__`) OR replace with `from musicstreamer import paths` and use `paths.data_dir()`. Claude's discretion: keeping the `constants` import is zero diff at call sites. **Recommendation:** leave these three files' imports alone — the `__getattr__` shim makes them work without modification. Only touch these files if grep verification below fails.

**Step 6 — Run existing tests** (without the pytest-qt port — that's Plan 35-05). The GTK tests import `DATA_DIR` etc. from constants — they should keep working via the shim.
  </action>
  <verify>
    <automated>grep -rn "~/.local/share/musicstreamer\|~/\.local/share/musicstreamer" musicstreamer/ | grep -v "migration.py" | grep -v "# " | grep -v "\"\"\""; test $? -eq 1 && pytest tests/test_paths.py tests/test_migration.py tests/test_repo.py -x</automated>
  </verify>
  <acceptance_criteria>
- `grep -rn "\"~/.local/share/musicstreamer\"\|os.path.expanduser.*\.local/share.*musicstreamer" musicstreamer/ | grep -v "migration.py"` returns nothing (only `migration.py` may reference the legacy path as `_LEGACY_LINUX`)
- `grep -q "from musicstreamer import paths" musicstreamer/constants.py` matches
- `grep -q "def __getattr__" musicstreamer/constants.py` matches
- `grep -q "paths.db_path" musicstreamer/repo.py` matches
- `grep -q "paths.data_dir\|paths.assets_dir" musicstreamer/assets.py` matches
- `grep -q "paths.cookies_path\|paths.twitch_token_path" musicstreamer/ui/accounts_dialog.py` matches
- `python -c "from musicstreamer import constants; print(constants.DATA_DIR)"` prints a path and exits 0 (__getattr__ works)
- `pytest tests/test_repo.py tests/test_paths.py tests/test_migration.py -x` exits 0
  </acceptance_criteria>
  <done>All data paths flow through `musicstreamer.paths`; the `constants.py` `__getattr__` shim keeps old imports working; no `~/.local/share/musicstreamer` string literals remain outside `migration.py`.</done>
</task>

</tasks>

<verification>
Grep-based sweep: after this plan, the only files in `musicstreamer/` containing the string `".local/share/musicstreamer"` should be `migration.py` (`_LEGACY_LINUX` constant). Every other reference is via `platformdirs.user_data_dir("musicstreamer")` inside `paths.py`.

The `constants.py` `__getattr__` shim is a deliberate design choice — it preserves all existing `from musicstreamer.constants import DATA_DIR` call sites unchanged while ensuring `paths._root_override` monkeypatching works end-to-end. Tests for the shim are covered by `test_repo.py` (indirectly via DB connection) and `test_paths.py` (directly).
</verification>

<success_criteria>
1. `musicstreamer/paths.py` + `musicstreamer/migration.py` exist with passing unit tests.
2. Zero hard-coded `~/.local/share/musicstreamer` literals remain in `musicstreamer/` except `migration.py`'s `_LEGACY_LINUX`.
3. `constants.py` exposes `DATA_DIR`/`DB_PATH`/`ASSETS_DIR`/`COOKIES_PATH`/`TWITCH_TOKEN_PATH` via `__getattr__` delegating to `paths.*`.
4. `pytest tests/test_paths.py tests/test_migration.py tests/test_repo.py -x` passes (legacy GTK tests still work because the shim preserves the old import names).
</success_criteria>

<output>
After completion, create `.planning/phases/35-backend-isolation/35-02-SUMMARY.md` documenting the paths.py shape and the __getattr__ shim strategy for downstream plans.
</output>
