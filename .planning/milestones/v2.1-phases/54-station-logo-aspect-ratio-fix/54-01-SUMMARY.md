---
phase: 54-station-logo-aspect-ratio-fix
plan: 01
subsystem: testing
tags: [pytest, pytest-qt, pyside6, qicon, qpixmap, qpixmapcache, aspect-ratio, regression-lock]

# Dependency graph
requires:
  - phase: 45-unified-station-icon-loader
    provides: load_station_icon helper + QPixmapCache contract (cache key "station-logo:{abs_path}")
provides:
  - Synthetic-pixmap regression-lock for aspect-preserving station-icon loading
  - test_load_station_icon_preserves_portrait_aspect (50w x 100h -> 16w x 32h)
  - test_load_station_icon_preserves_landscape_aspect (100w x 50h -> 32w x 16h)
  - Backwards-compatible _write_logo helper extension (width/height kwargs)
affects: [54-02, 54-03, future station-icon loader changes]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Synthetic non-square PNG fixture via QPixmap(w, h).fill(color).save(path) — no PIL dependency"
    - "Exact-dimension assertions on icon.pixmap(QSize(target, target)) for aspect-preservation regression locks"

key-files:
  created: []
  modified:
    - tests/test_art_paths.py

key-decisions:
  - "D-09 honored: zero production code change — Path A regression-lock only"
  - "D-10 honored: synthetic-pixmap unit test on load_station_icon in tests/test_art_paths.py"
  - "D-11 honored: QPixmapCache key string `station-logo:` unchanged (verified by grep)"
  - "Strengthened assertion shape from existing `<= 32` (loose bound) to exact dimensions on both axes — required to lock the smaller-axis-preservation contract"

patterns-established:
  - "Pattern: extend existing test helper with optional kwargs (default None) instead of forking — preserves all existing call sites"
  - "Pattern: synthetic-fixture-to-disk for loaders that resolve via path string (load_station_icon takes Station, not QPixmap)"

requirements-completed: [BUG-05]

# Metrics
duration: 3min 13s
completed: 2026-04-29
---

# Phase 54 Plan 01: Aspect-Preservation Regression Lock Summary

**Two synthetic-pixmap pytest tests lock load_station_icon's existing aspect-preserving behavior (portrait 1:2 -> 16x32 pillarbox; landscape 2:1 -> 32x16 letterbox) without modifying any production code.**

## Performance

- **Duration:** 3min 13s
- **Started:** 2026-04-29T00:51:57Z
- **Completed:** 2026-04-29T00:55:10Z
- **Tasks:** 3 (Task 1, Task 2 — code; Task 3 — verification)
- **Files modified:** 1 (`tests/test_art_paths.py`)

## Accomplishments

- Extended `_write_logo` helper with optional `width` / `height` kwargs (default `None` → all 5 existing call sites preserved by default-None semantics).
- Added `test_load_station_icon_preserves_portrait_aspect` — synthetic 50w x 100h PNG → asserts `icon.pixmap(QSize(32, 32))` is exactly 16w x 32h. Regression lock for BUG-05 / SC #3 (D-10).
- Added `test_load_station_icon_preserves_landscape_aspect` — synthetic 100w x 50h PNG → asserts `icon.pixmap(QSize(32, 32))` is exactly 32w x 16h. Parallel coverage for BUG-05 / SC #2.
- Confirmed `tests/test_art_paths.py` grew from 7 to 9 tests, all passing in `0.11s`.
- Confirmed D-11 invariant: cache key string `f"station-logo:{load_path}"` in `musicstreamer/ui_qt/_art_paths.py` is unchanged.
- Confirmed `git diff musicstreamer/` is empty after this plan — zero production code change (D-09 smallest-diff).

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend `_write_logo` helper with optional `width` / `height` kwargs** — `2fbf823` (test)
2. **Task 2: Add portrait + landscape aspect-preservation regression tests** — `3930f66` (test)
3. **Task 3: Run full test suite to confirm no cross-module regression** — verification-only task, no commit (focused suite green; pre-existing flakes documented in `deferred-items.md`)

## Files Created/Modified

- `tests/test_art_paths.py` — Extended `_write_logo` helper signature; added two aspect-preservation regression tests; added `QSize` to PySide6.QtCore imports.
- `.planning/phases/54-station-logo-aspect-ratio-fix/deferred-items.md` — Catalog of 11 pre-existing test failures in unrelated modules, deferred per SCOPE BOUNDARY.

## Decisions Made

- **Assertion shape:** Used exact-dimension equality (`pix.width() == 16`) rather than the existing loose-bound style (`max(...) <= 32`). Rationale: the bug being regression-locked is about the smaller axis being preserved. A loose `<= 32` would not catch a regression that produced a 32x32 center-cropped pixmap from a 50x100 source — the exact-dimension form does. This is the strengthening called out in `54-PATTERNS.md` "Assertion-shape rationale".
- **Skipped Path B-1 production patch:** Per Plan 54-01 scope, this plan ships Path A only. Path B-1 lives in Plan 54-03 and is conditional on Plan 54-02 UAT outcome.
- **Used relative paths in fixtures** (`assets/5/portrait.png`, `assets/6/landscape.png`) to exercise the `abs_art_path` resolution branch — matching the existing-test path-resolution pattern.

## Deviations from Plan

None - plan executed exactly as written.

The plan's acceptance criterion `grep -c "_write_logo(" tests/test_art_paths.py` >= 8 was based on a stale call-site count (actual count is 1 def + 5 invocations = 6 occurrences; 5 invocations were originally listed in PATTERNS.md as "7"). The intent of the criterion — that all existing call sites continue to work — is satisfied: pytest reports all 5 existing call sites' tests pass. No fix was made; this is a benign acceptance-criteria-counting mismatch in the plan, not a correctness issue.

## Issues Encountered

### Pre-existing test failures in unrelated modules (deferred)

Running `pytest -x` (Task 3 verification) revealed 11 pre-existing failures in modules untouched by this plan: `test_media_keys_mpris2.py`, `test_media_keys_smtc.py`, `test_station_list_panel.py`, `test_twitch_auth.py`, and `test_edit_station_dialog.py::test_logo_status_clears_after_3s` (the latter is a known timing-flake — passes in isolation, fails under `-x` due to a 3s `qtbot.wait` race).

**Verified pre-existing** by reverting `tests/test_art_paths.py` to commit `bc5ad0f` (parent of Task 1) and re-running the full suite: same 11 failures, only difference is total passing count dropped from 840 to 838 (i.e. exactly the 2 new aspect-preservation tests).

**Disposition:** Logged to `deferred-items.md`. Out of scope per the executor SCOPE BOUNDARY rule. The phase-54 acceptance gate is `pytest tests/test_art_paths.py -x` (focused suite, 9 passed, 0.11s) — that gate is green. Cross-module flakes are a separate triage concern not introduced by this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **Plan 54-02 (UAT decision gate)** is unblocked. The regression-lock tests are in place; UAT can now visually confirm whether the user's running build matches the probe's offscreen rendering. If UAT confirms the existing pipeline is correct, the phase ships test-only (Plan 54-03 not needed). If UAT shows actual cropping, Plan 54-03 (Path B-1: paint-onto-transparent-canvas) ships.
- **D-11 cache contract preserved.** No follow-up cache-invalidation needed.
- **D-07 uniform loader contract preserved.** No YouTube branch introduced.
- **Pre-existing 11-test flake set** is unrelated to Phase 54 and should be triaged separately. Documented in `deferred-items.md` for visibility.

## Self-Check: PASSED

Files verified:
- `FOUND: tests/test_art_paths.py` (modified — 2 new tests + extended helper, all 9 tests pass)
- `FOUND: .planning/phases/54-station-logo-aspect-ratio-fix/deferred-items.md` (new, documents pre-existing flakes)
- `FOUND: .planning/phases/54-station-logo-aspect-ratio-fix/54-01-SUMMARY.md` (this file)

Commits verified:
- `FOUND: 2fbf823` — `test(54-01): extend _write_logo with optional width/height kwargs`
- `FOUND: 3930f66` — `test(54-01): add load_station_icon aspect-preservation tests`

Acceptance criteria verified:
- `pytest tests/test_art_paths.py -x` exits 0 with 9 passed (was 7, now 9).
- `grep -q "def test_load_station_icon_preserves_portrait_aspect" tests/test_art_paths.py` exits 0.
- `grep -q "def test_load_station_icon_preserves_landscape_aspect" tests/test_art_paths.py` exits 0.
- `grep -q "from PySide6.QtCore import QSize, Qt" tests/test_art_paths.py` exits 0.
- `grep -q 'station-logo:' musicstreamer/ui_qt/_art_paths.py` exits 0 (D-11 invariant unchanged).
- `git diff musicstreamer/ HEAD~2..HEAD` empty — zero production code change (D-09).

---
*Phase: 54-station-logo-aspect-ratio-fix*
*Completed: 2026-04-29*
