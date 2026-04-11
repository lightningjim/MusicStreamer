---
phase: 35-backend-isolation
plan: 02
subsystem: backend
tags: [paths, platformdirs, migration, refactor]
requires:
  - "musicstreamer/constants.py existed and centralized data paths"
provides:
  - "musicstreamer.paths — single source of truth for all data-file locations"
  - "musicstreamer.migration.run_migration — non-destructive first-launch migration with marker"
  - "Test hook (paths._root_override) so the entire suite can redirect every accessor at tmp_path"
  - "PEP 562 __getattr__ shim in constants.py preserves backward compat for DATA_DIR / DB_PATH / ASSETS_DIR / COOKIES_PATH / TWITCH_TOKEN_PATH"
affects:
  - musicstreamer/paths.py
  - musicstreamer/migration.py
  - musicstreamer/constants.py
  - musicstreamer/assets.py
  - musicstreamer/repo.py
  - musicstreamer/ui/accounts_dialog.py
  - tests/test_paths.py
  - tests/test_migration.py
  - tests/test_cookies.py
  - tests/test_twitch_auth.py
tech-stack:
  added:
    - "platformdirs.user_data_dir('musicstreamer') as data root"
  patterns:
    - "PEP 562 module-level __getattr__ for lazy attribute delegation"
    - "Pure path module — no I/O on import; tests monkeypatch _root_override"
    - "shutil.copy2 to preserve 0600 mode bits across migration (security-critical for cookies/token)"
key-files:
  created:
    - musicstreamer/paths.py
    - musicstreamer/migration.py
    - tests/test_paths.py
    - tests/test_migration.py
  modified:
    - musicstreamer/constants.py
    - musicstreamer/assets.py
    - musicstreamer/repo.py
    - musicstreamer/ui/accounts_dialog.py
    - tests/test_cookies.py
    - tests/test_twitch_auth.py
decisions:
  - "PEP 562 __getattr__ shim in constants.py: re-evaluates paths.* on every attribute access so paths._root_override monkeypatching works without rewriting every call site that does `from musicstreamer.constants import DATA_DIR`"
  - "UI files importing DATA_DIR (edit_dialog, main_window, station_row) left untouched — the shim makes them transparent. Minimum churn per plan Step 5."
metrics:
  duration_min: 8
  tasks: 2
  files_changed: 10
  completed: 2026-04-11
requirements: [PORT-05, PORT-06]
---

# Phase 35 Plan 02: platformdirs Paths + Migration Summary

**One-liner:** Centralized every data-file location behind `musicstreamer.paths` (rooted at `platformdirs.user_data_dir`), added a non-destructive `run_migration()` helper with a `.platformdirs-migrated` marker, and preserved every existing `from musicstreamer.constants import DATA_DIR` call site via a PEP 562 `__getattr__` shim.

## What Shipped

### 1. `musicstreamer/paths.py` — pure path helper (D-12, D-13)
Seven accessors — `data_dir`, `db_path`, `assets_dir`, `cookies_path`, `twitch_token_path`, `accent_css_path`, `migration_marker` — all routed through a single `_root()` function. The module-level `_root_override: str | None = None` is the test hook: tests assign it directly and every accessor immediately resolves under that path. The module is **pure**: importing it (or calling any accessor) does NOT touch the filesystem. Verified by `test_paths_do_no_io_on_import`.

### 2. `musicstreamer/migration.py` — first-launch helper (D-14..D-16)
`run_migration()` checks `paths.migration_marker()` and short-circuits if present. Otherwise it:

1. `os.makedirs(dest, exist_ok=True)` — ensure platformdirs root exists.
2. If `_LEGACY_LINUX == dest` (the Linux v1.5 → v2.0 case), just write the marker and return.
3. Otherwise call `_copy_tree_nondestructive(src, dest)` which walks the legacy tree and copies any file whose dest counterpart does NOT yet exist using `shutil.copy2` (preserves mode bits — security-critical for cookies.txt and twitch-token.txt at 0600).
4. Write the `.platformdirs-migrated` marker.

`_LEGACY_LINUX` is module-level so tests can monkeypatch it to a tmp directory.

### 3. `musicstreamer/constants.py` — PEP 562 shim
The five data-path constants (`DATA_DIR`, `DB_PATH`, `ASSETS_DIR`, `COOKIES_PATH`, `TWITCH_TOKEN_PATH`) are exposed via module-level `__getattr__` that delegates to `paths.*` on every access. **This is the load-bearing design choice** — assigning them as plain module-level attributes would snapshot the path once at import time and silently break `paths._root_override` monkeypatching in tests. Every existing `from musicstreamer.constants import DATA_DIR` call site continues to work without modification, and re-evaluates on each access.

`clear_cookies()` and `clear_twitch_token()` were updated to call `paths.cookies_path()` / `paths.twitch_token_path()` directly (not via the shim) to avoid an extra attribute lookup.

### 4. Direct call-site rewrites
- `assets.py` — `from musicstreamer import paths`; `ensure_dirs()` and `copy_asset_for_station()` use `paths.data_dir()` / `paths.assets_dir()`.
- `repo.py` — `db_connect()` uses `paths.db_path()`.
- `ui/accounts_dialog.py` — every `COOKIES_PATH` / `TWITCH_TOKEN_PATH` literal replaced with `paths.cookies_path()` / `paths.twitch_token_path()`. Per-call overhead is negligible (these only fire on user dialog interactions) and crucially the monkeypatch path now works end-to-end.

### 5. UI files left untouched
`edit_dialog.py`, `main_window.py`, `station_row.py` still do `from musicstreamer.constants import DATA_DIR` — they're transparently routed through the `__getattr__` shim. Zero diff at those call sites per plan Step 5 (minimum churn).

## Downstream Contract for Plans 35-03 / 35-04 / 35-05

- **Plan 35-03** (`yt_import.py`, `mpris.py`): the `cookies_path()` accessor is what `yt_import` should call. The plan was running in parallel during this execution and has already replaced `from musicstreamer.constants import COOKIES_PATH` with its own resolution path inside `yt_import.py`.
- **Plan 35-04** (`player.py` QObject conversion): when porting `_play_youtube` and `_play_twitch`, replace `from musicstreamer.constants import COOKIES_PATH, TWITCH_TOKEN_PATH` with `from musicstreamer import paths` and call `paths.cookies_path()` / `paths.twitch_token_path()` per use. The `__getattr__` shim will keep working transitively if you forget — but direct calls are clearer.
- **Plan 35-05** (pytest-qt port): use `paths._root_override = str(tmp_path)` in conftest fixtures to redirect every data-file write inside the test suite.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Two existing `clear_*` tests broke after the shim landed**
- **Found during:** Task 2 (running test suite)
- **Issue:** `tests/test_cookies.py::test_clear_removes_cookies_file` and `tests/test_twitch_auth.py::test_clear_twitch_token_removes_file` both did `monkeypatch.setattr("musicstreamer.constants.COOKIES_PATH", str(...))`. The `__getattr__` shim resolves the attribute lazily via `paths.cookies_path()`, so monkeypatching `constants.COOKIES_PATH` directly no longer affects the actual lookup.
- **Fix:** Rewrote both tests (and their `_returns_false_when_absent` siblings) to monkeypatch `paths._root_override` instead. This is the canonical test hook the rest of the new test suite uses.
- **Files modified:** `tests/test_cookies.py`, `tests/test_twitch_auth.py`
- **Commit:** `6602c34`

### Out-of-Scope Failures (NOT fixed — belong to Plan 35-03)
The full `tests/test_cookies.py` collection raises `ImportError: No module named 'yt_dlp'` for 7 tests that `monkeypatch.setattr("musicstreamer.yt_import.COOKIES_PATH", ...)`. This is **caused by the parallel Plan 35-03 in-progress edits** to `yt_import.py` (which now imports `yt_dlp` at module top-level and removed its `COOKIES_PATH` attribute). These failures are out of this plan's scope — Plan 35-03 owns those tests. Verified by inspecting `git status` showing `mpris.py` and `yt_import.py` modified by the parallel plan, neither of which I touched.

The `yt_dlp` import error itself is pre-existing project state — `yt_dlp` is installed in the project venv but not in the `python3` interpreter the test runner picked up. Plan 35-03's verification will resolve this.

## Authentication Gates

None.

## Verification

| Check | Result |
|-------|--------|
| `test -f musicstreamer/paths.py` | PASS |
| `test -f musicstreamer/migration.py` | PASS |
| `grep -c "^def (data_dir\|db_path\|assets_dir\|cookies_path\|twitch_token_path\|accent_css_path\|migration_marker)" musicstreamer/paths.py` | 7 |
| `grep "platformdirs.user_data_dir" musicstreamer/paths.py` | PASS |
| `grep "_root_override" musicstreamer/paths.py` | PASS |
| `grep "def run_migration" musicstreamer/migration.py` | PASS |
| `grep ".platformdirs-migrated" musicstreamer/paths.py` | PASS |
| `grep -rn '"~/.local/share/musicstreamer"\|os.path.expanduser.*\.local/share.*musicstreamer' musicstreamer/ \| grep -v migration.py` | EMPTY (only `_LEGACY_LINUX` in `migration.py` references the legacy literal) |
| `grep "from musicstreamer import paths" musicstreamer/constants.py` | PASS |
| `grep "def __getattr__" musicstreamer/constants.py` | PASS |
| `grep "paths.db_path" musicstreamer/repo.py` | PASS |
| `grep "paths.data_dir\|paths.assets_dir" musicstreamer/assets.py` | PASS |
| `grep "paths.cookies_path\|paths.twitch_token_path" musicstreamer/ui/accounts_dialog.py` | PASS |
| `python -c "from musicstreamer import constants; print(constants.DATA_DIR)"` | prints `/home/kcreasey/.local/share/musicstreamer` (shim works) |
| `pytest tests/test_paths.py tests/test_migration.py tests/test_repo.py -x` | 61 passed |
| `pytest tests/test_cookies.py::test_cookie_path_constant ::test_clear_removes_cookies_file ::test_clear_returns_false_when_absent` | 3 passed |
| `pytest tests/test_twitch_auth.py::test_twitch_token_path_constant ::test_clear_twitch_token_removes_file ::test_clear_twitch_token_returns_false_when_absent` | 3 passed |

## Commits

- `739d455` feat(35-02): add paths.py + migration.py with TDD tests
- `6602c34` refactor(35-02): route data paths through musicstreamer.paths

## Self-Check: PASSED

- `musicstreamer/paths.py` exists
- `musicstreamer/migration.py` exists
- `tests/test_paths.py` exists
- `tests/test_migration.py` exists
- `739d455` and `6602c34` resolve in `git log`
- All 14 acceptance criteria from the plan return their expected values
