---
phase: 01-module-extraction
plan: 01
subsystem: database
tags: [sqlite3, dataclasses, pytest, python-package]

requires: []
provides:
  - musicstreamer Python package with constants, models, repo, assets modules
  - Repo class with full CRUD for stations and providers
  - pytest smoke test suite for data layer (6 tests)
affects:
  - 01-module-extraction (plan 02 — UI module extraction imports from this package)
  - All future phases that use Repo, Station, Provider

tech-stack:
  added: [pytest via uv, musicstreamer package]
  patterns:
    - constants.py as dependency leaf (imports nothing from musicstreamer)
    - models.py has no dependencies (pure dataclasses)
    - repo.py imports from models and constants only
    - assets.py imports from constants only
    - No GTK/GStreamer imports in data-layer modules

key-files:
  created:
    - musicstreamer/__init__.py
    - musicstreamer/constants.py
    - musicstreamer/models.py
    - musicstreamer/repo.py
    - musicstreamer/assets.py
    - musicstreamer/ui/__init__.py
    - tests/__init__.py
    - tests/test_repo.py
    - .gitignore
  modified: []

key-decisions:
  - "pytest installed via uv (uv run --with pytest) — no pip available on system python, apt requires sudo"
  - "constants.py as dependency leaf for APP_ID, DATA_DIR, DB_PATH, ASSETS_DIR — avoids duplication across 4+ future modules"

patterns-established:
  - "Absolute imports throughout: from musicstreamer.models import Station (not relative)"
  - "No gi/GTK/GStreamer imports in data-layer modules — those belong exclusively to UI layer"
  - "Gst.init(None) deferred to __main__.py — not at module import time"

requirements-completed: [CODE-01]

duration: 2min
completed: 2026-03-18
---

# Phase 1 Plan 1: Package Structure and Data-Layer Extraction Summary

**musicstreamer Python package extracted from main.py monolith with constants, models, repo, assets modules and 6 passing pytest smoke tests**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-18T22:10:40Z
- **Completed:** 2026-03-18T22:12:41Z
- **Tasks:** 2
- **Files modified:** 9 created

## Accomplishments
- musicstreamer/ package importable with zero GTK/GStreamer dependencies in data-layer
- Repo class fully extracted with create/list/get/update for stations + ensure_provider
- 6 smoke tests pass using tmp_path fixture for isolated SQLite instances
- .gitignore added to suppress __pycache__ from version control

## Task Commits

1. **Task 1: Create package structure and extract data-layer modules** - `59fc516` (feat)
2. **Task 2: Install pytest and write data-layer smoke tests** - `f48b97c` (test)

## Files Created/Modified
- `musicstreamer/__init__.py` - Package marker
- `musicstreamer/constants.py` - APP_ID, DATA_DIR, DB_PATH, ASSETS_DIR
- `musicstreamer/models.py` - Provider and Station dataclasses
- `musicstreamer/repo.py` - Repo class, db_connect, db_init
- `musicstreamer/assets.py` - ensure_dirs, copy_asset_for_station
- `musicstreamer/ui/__init__.py` - UI subpackage marker
- `tests/__init__.py` - Test package marker
- `tests/test_repo.py` - 6 smoke tests for data layer
- `.gitignore` - Excludes __pycache__, pytest artifacts

## Decisions Made
- Used `uv run --with pytest` to install/run pytest — system Python has no pip and apt requires sudo; uv was already present with pytest cached
- Created `constants.py` as the dependency leaf rather than inlining constants in each module — APP_ID, DATA_DIR, DB_PATH, ASSETS_DIR needed in at least 4 modules

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pytest installation via uv instead of pip3**
- **Found during:** Task 2 (pytest install)
- **Issue:** pip3/pip not found; system Python has no pip; apt-get requires sudo; ensurepip disabled on Debian/Ubuntu system Python
- **Fix:** Used `uv run --with pytest python3 -m pytest` — uv available at ~/.local/bin/uv with pytest 9.0.2 cached
- **Files modified:** None (runtime tool, not project files)
- **Verification:** `uv run --with pytest python3 -m pytest --version` returned pytest 9.0.2; all 6 tests passed
- **Committed in:** f48b97c (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking — install mechanism)
**Impact on plan:** No scope creep. Tests run identically; uv is a transparent runner.

## Issues Encountered
- System Python environment blocked pip/pip3. Resolved by using uv which was already installed. Tests run with `uv run --with pytest python3 -m pytest tests/test_repo.py -v`.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- musicstreamer data-layer package ready for Plan 02 to import
- Plan 02 (UI module extraction) can import Station, Provider, Repo, ensure_dirs, copy_asset_for_station from the package
- main.py still exists unchanged — removal deferred to plan 02 per scope boundary
- Run tests: `uv run --with pytest python3 -m pytest tests/ -v`

---
*Phase: 01-module-extraction*
*Completed: 2026-03-18*
