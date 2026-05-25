---
phase: 64-audioaddict-siblings-on-now-playing
plan: 01
subsystem: ui
tags:
  - audioaddict
  - url-helpers
  - renderer-promotion
  - phase-51-followup
  - qt-richtext
  - html-escape

# Dependency graph
requires:
  - phase: 51-audioaddict-cross-network-siblings
    provides: "private EditStationDialog._render_sibling_html implementation (D-07/D-08); html.escape mitigation for T-39-01"
provides:
  - "musicstreamer.url_helpers.render_sibling_html — free function colocated with find_aa_siblings; produces 'Also on: <a href=\"sibling://{id}\">{label}</a>' joined with U+2022 BULLET"
  - "EditStationDialog import + call-site update consuming the free function (no private renderer method)"
  - "5 pure unit tests for render_sibling_html (basic, em-dash, html-escape, bullet, unknown-slug fallback)"
affects:
  - "Phase 64-02 (NowPlayingPanel siblings panel) — will import render_sibling_html for the same surface contract"
  - "Any future surface that needs the 'Also on:' line (Phase 51 dialog + Phase 64 panel today, more surfaces possible)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure-function renderer colocated with its data-source helper (find_aa_siblings + render_sibling_html in url_helpers.py)"
    - "T-39-01 deviation mitigation pattern preserved across renderer promotion: html.escape(name, quote=True) on every Station.name interpolation"
    - "Single source of HTML rendering across multiple Qt surfaces (D-03)"

key-files:
  created: []
  modified:
    - "musicstreamer/url_helpers.py — added `import html` and `render_sibling_html` free function"
    - "musicstreamer/ui_qt/edit_station_dialog.py — removed private renderer method, dropped dead `import html` and `from musicstreamer.aa_import import NETWORKS` imports, swapped call site to free function, updated rationale comment"
    - "tests/test_aa_siblings.py — added 5 pure unit tests for render_sibling_html"

key-decisions:
  - "Lifted EditStationDialog._render_sibling_html body verbatim into url_helpers.render_sibling_html (zero `self` references in body — mechanical lift)"
  - "Preserved U+2014 EM DASH and U+2022 BULLET as literal Unicode characters (D-03 byte-parity invariant — round-trip equality across surfaces)"
  - "Preserved html.escape(station_name, quote=True) verbatim on every Station.name interpolation (T-39-01 deviation mitigation, threat model T-64-01)"
  - "Updated stale rationale comment in edit_station_dialog.py:397-406 to point at the new free function location (accuracy fix, treated as Rule 1 deviation)"

patterns-established:
  - "Renderer promotion: when a private dialog/widget renderer is needed by a second surface, lift the body verbatim to the data-source module (here url_helpers.py colocated with find_aa_siblings) — keep imports minimal (only `import html` added)"
  - "Renderer-test pattern: pure data-in/data-out tests with tuples (no Qt, no fixtures) that mirror Phase 51 dialog test expectations but call the free function directly"

requirements-completed:
  - BUG-02

# Metrics
duration: 6min
completed: 2026-05-01
---

# Phase 64 Plan 01: Promote render_sibling_html to url_helpers Summary

**Promoted Phase 51's private `EditStationDialog._render_sibling_html` to a shared free function `render_sibling_html` in `musicstreamer/url_helpers.py` so Plan 02's NowPlayingPanel can consume the same renderer; preserved html.escape mitigation and integer-only sibling://{id} href format verbatim.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-01T16:19:08Z
- **Completed:** 2026-05-01T16:24:57Z
- **Tasks:** 2 (TDD: RED + GREEN per task)
- **Files modified:** 3 (musicstreamer/url_helpers.py, musicstreamer/ui_qt/edit_station_dialog.py, tests/test_aa_siblings.py)

## Accomplishments

- `render_sibling_html` exists as a top-level free function in `musicstreamer/url_helpers.py`, colocated with `find_aa_siblings` (D-03 single-source invariant)
- `EditStationDialog` now imports and calls the free function — `_render_sibling_html` no longer exists in the dialog source
- Dead imports `import html` and `from musicstreamer.aa_import import NETWORKS` removed from the dialog (only the renderer used them in this module)
- 5 new pure unit tests in `tests/test_aa_siblings.py` exercise the renderer directly: basic same-name link, U+2014 em-dash for differing names, html.escape mitigation, U+2022 bullet separator across multiple siblings, and unknown-slug defensive fallback
- Phase 51 dialog sibling tests (`tests/test_edit_station_dialog.py -k sibling`) remain fully green with zero test modifications — they read `d._sibling_label.text()` (public side-effect transparent to the renderer move)

## Task Commits

Each task followed TDD RED → GREEN. (Refactor commits not needed — Task 1 GREEN matched expectations on first run; Task 2 was a verbatim move with comment cleanup.)

1. **Task 1 RED — failing tests for render_sibling_html** — `032c38a` (test)
2. **Task 1 GREEN — promote render_sibling_html to url_helpers** — `e540722` (feat)
3. **Task 2 — replace EditStationDialog._render_sibling_html with free function** — `78a3841` (refactor)

## Files Created/Modified

- `musicstreamer/url_helpers.py` — added `import html` (line 10) and the 33-line `render_sibling_html` free function at end of file. `find_aa_siblings` body unchanged.
- `musicstreamer/ui_qt/edit_station_dialog.py` — three surgical edits: import line at 51 now imports `render_sibling_html` alongside `find_aa_siblings`; call site at 563 calls the free function (`self.` removed); the 44-line `_render_sibling_html` method block deleted. Plus dead-import cleanup: `import html` (was line 19) and `from musicstreamer.aa_import import NETWORKS` (was line 48) removed. Plus stale-reference comment fix at lines 397-406 pointing the rationale comment at the new free-function location.
- `tests/test_aa_siblings.py` — import line updated to pull `render_sibling_html`; 5 unit tests appended at end of file (existing tests untouched).

## Decisions Made

Followed plan as specified — no architectural decisions. Renderer body was lifted verbatim (zero `self` references in source, verified by grep at planning time and confirmed during execution).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Updated stale rationale comment in edit_station_dialog.py:397-406**

- **Found during:** Task 2 (CHANGE 4 — dead-import cleanup verification)
- **Issue:** The Phase 51-03 rationale comment for the `_sibling_label` config block referenced `_render_sibling_html` (a method we just deleted) as the location of the html.escape mitigation. After Task 2's deletion, this reference was a dangling pointer to a function that no longer exists in the dialog module — accuracy bug in code documentation.
- **Fix:** Updated the comment to reference `musicstreamer.url_helpers.render_sibling_html` (with a parenthetical noting the Phase 64 / D-03 promotion) so the rationale still describes the active mitigation site.
- **Files modified:** musicstreamer/ui_qt/edit_station_dialog.py (comment block at lines 397-406, scoped to the same file the plan already directed edits to)
- **Verification:** Pure comment-text edit — no behavior change; full dialog test suite still green (52 passed). The plan's `<verification>` and `<acceptance_criteria>` blocks all pass.
- **Committed in:** `78a3841` (Task 2 commit — bundled with the plan's directed edits since it's a same-file accuracy fix discovered during the dead-import grep verification step)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 — code-comment accuracy)
**Impact on plan:** Within scope (same file, same plan). No new code paths, no scope creep, no test changes. The fix prevents code-comment drift from the renderer promotion.

## Issues Encountered

- **pytest-qt not installed in worktree venv on first run.** The aa_siblings tests passed under `uv run --with pytest pytest …` but the dialog suite needs the `qtbot` fixture (pytest-qt). Resolved by running `uv sync --extra test` to install the project's `[project.optional-dependencies].test` extra, which pulls `pytest-qt>=4`. Subsequent runs use `uv run pytest …` directly. This produced an incidental change to `uv.lock`; the change was NOT committed (out of scope — only the plan's `files_modified` were committed).
- **One transient test isolation glitch.** `tests/test_edit_station_dialog.py::test_logo_status_clears_after_3s` failed once when run as part of the full dialog suite at `-x` then passed on a second isolated run and on a subsequent full-suite run. Root cause is timing-related (the test waits 3s for QTimer; first-run pytest-qt fixture init may have eaten some of the wait budget). Out of scope for this plan — pre-existing test that has nothing to do with the sibling renderer.

## Threat Flags

None — no new security-relevant surface introduced. `render_sibling_html` produces the same HTML output the dialog has been producing since Phase 51; the T-64-01 mitigation (html.escape on every Station.name) is preserved verbatim; the href payload remains integer-only `sibling://{id}`. Network display names continue to come from the compile-time `NETWORKS` constant.

## User Setup Required

None — no external service configuration, no environment variables, no migration.

## Next Phase Readiness

- **Plan 02 ready to import.** `from musicstreamer.url_helpers import find_aa_siblings, render_sibling_html` is the single import the panel needs for sibling rendering.
- **Renderer call sites:** now exactly two — `EditStationDialog._refresh_siblings` (line 563) and the upcoming `NowPlayingPanel._refresh_siblings` (Plan 02). Both will produce byte-identical HTML for identical inputs, satisfying the D-03 single-source invariant.
- **No blockers.**

## Self-Check

Verified all SUMMARY.md claims against the filesystem and git log:

- Created file `musicstreamer/url_helpers.py` (modified): `def render_sibling_html` present at line 150 — FOUND
- Modified file `musicstreamer/ui_qt/edit_station_dialog.py`: `render_sibling_html(siblings, self._station.name)` at line 563 — FOUND; `_render_sibling_html` count = 0 — CONFIRMED; `^import html$` count = 0 — CONFIRMED; `^from musicstreamer.aa_import import NETWORKS$` count = 0 — CONFIRMED
- Modified file `tests/test_aa_siblings.py`: `from musicstreamer.url_helpers import find_aa_siblings, render_sibling_html` at line 9 — FOUND; 5 new test functions present — CONFIRMED
- Commit `032c38a` (test RED) — FOUND in `git log`
- Commit `e540722` (feat GREEN) — FOUND in `git log`
- Commit `78a3841` (refactor) — FOUND in `git log`
- `pytest tests/test_aa_siblings.py -x -q` exits 0 (17 tests) — CONFIRMED
- `pytest tests/test_edit_station_dialog.py -x -q` exits 0 (52 tests) — CONFIRMED
- `git diff --stat 2853783a..HEAD` shows changes only in `musicstreamer/url_helpers.py`, `musicstreamer/ui_qt/edit_station_dialog.py`, `tests/test_aa_siblings.py` — CONFIRMED

## Self-Check: PASSED

---
*Phase: 64-audioaddict-siblings-on-now-playing*
*Plan: 01*
*Completed: 2026-05-01*
