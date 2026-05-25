---
phase: 71-sister-station-expansion
plan: 05
subsystem: ui
tags: [pyside6, qlabel, sibling-stations, url_helpers, now_playing_panel]

requires:
  - phase: 71-00
    provides: RED test test_now_playing_shows_merged_siblings + _FakeRepoWithSiblings fixture
  - phase: 71-01
    provides: Repo.list_sibling_links(station_id) -> list[int]
  - phase: 71-02
    provides: find_manual_siblings + merge_siblings helpers in url_helpers.py
provides:
  - NowPlayingPanel "Also on:" line surfaces manual sibling links alongside AA URL-derived siblings (single unified row)
  - Hidden-when-empty contract preserved when both AA and manual lists are empty
  - Existing sibling_activated navigation signal continues to drive playback switching for both AA and manual chips
affects: [71-03-edit-station-dialog-picker, 71-04-settings-export, future-similar-stations-merges]

tech-stack:
  added: []
  patterns:
    - "call-site composition: merge_siblings(find_aa_siblings(...), find_manual_siblings(...)) -> render_sibling_html (unchanged signature, Pitfall 2)"
    - "both DB reads (list_stations + list_sibling_links) inside the same try/except for T-71-27 mitigation"

key-files:
  created: []
  modified:
    - musicstreamer/ui_qt/now_playing_panel.py
    - tests/test_now_playing_panel.py

key-decisions:
  - "D-01 (Phase 71): Merge AA + manual siblings into the existing 'Also on:' line, not a new label"
  - "D-04 (Phase 71): NowPlaying + Edit dialog only — no station-tree surface for sibling indication"
  - "Both DB reads (list_stations, list_sibling_links) wrapped in the same try/except per T-71-27"

patterns-established:
  - "Minimum-diff merge call-site swap: existing helper call replaced with merge_siblings composition; downstream renderer signature stable (Pitfall 2)"
  - "FakeRepo base-class default for new Repo methods: returning [] preserves prior-phase test contracts when the new code path adds a Repo call"

requirements-completed: [D-01, D-04]

duration: 7min
completed: 2026-05-12
---

# Phase 71 Plan 05: NowPlayingPanel sibling merge — Summary

**Surfaced manual sibling links on NowPlaying's "Also on:" line by composing merge_siblings(find_aa_siblings(...), find_manual_siblings(...)) at the existing _refresh_siblings call site — zero widget changes, zero new HTML output paths.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-12T22:02:58Z
- **Completed:** 2026-05-12T22:09:31Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- `_refresh_siblings` in `now_playing_panel.py` now reads `link_ids` from `self._repo.list_sibling_links(...)` inside the existing try/except wrapper, then composes `find_aa_siblings` + `find_manual_siblings` -> `merge_siblings` and passes the merged list to the unchanged `render_sibling_html`.
- The Phase 71 RED test `test_now_playing_shows_merged_siblings` (plan 71-00) turns GREEN; all 11 pre-existing sibling tests stay GREEN.
- The `_sibling_label` QLabel construction (lines 354-360, including `setTextFormat(Qt.RichText)` at line 357) is **untouched** — T-40-04 per-file RichText count in `now_playing_panel.py` remains exactly 3.
- The Phase 64 D-05 hidden-when-empty contract is preserved (when both AA and manual lists empty -> `setVisible(False)` + `setText("")`).
- The existing `sibling_activated = Signal(object)` chip-click navigation path is unchanged — both AA and manual chips share the `sibling://{id}` href scheme via `render_sibling_html`.

## Task Commits

1. **Task 1: Swap _refresh_siblings to use merge_siblings(find_aa_siblings, find_manual_siblings)** — `e957ea8` (feat)

## Files Created/Modified

- `musicstreamer/ui_qt/now_playing_panel.py` — Two edits:
  - **Import line (lines 55-62):** extended the existing multi-line `from musicstreamer.url_helpers import (...)` block with `find_manual_siblings` and `merge_siblings` (alphabetical order).
  - **`_refresh_siblings` body (lines 1206-1230, was 1206-1224):** inside the existing try/except, added `link_ids = self._repo.list_sibling_links(self._station.id)`; replaced the single `siblings = find_aa_siblings(...)` call with the three-step chain `aa_list = find_aa_siblings(...)` -> `manual_list = find_manual_siblings(...)` -> `siblings = merge_siblings(aa_list, manual_list)`. All other lines (hidden-when-empty branch, `render_sibling_html` call, `setVisible(True)`) are byte-for-byte unchanged. Net diff: +10/-1 lines.
- `tests/test_now_playing_panel.py` — added 7 lines (Rule 3 deviation; see below).

## Decisions Made

- Preserved the existing multi-line import form rather than converting to a one-line `from ... import a, b, c, d, e, f` — readability and matches the surrounding `now_playing_panel.py` style (Phase 67 added `pick_similar_stations` and `render_similar_html` the same way).
- Did NOT add any tab-order changes, widget construction, or new RichText labels (per plan Step C "no other modifications").
- Did NOT introduce a sort/dedup pass at the call site — `merge_siblings` already deduplicates by station_id with AA precedence, and `find_manual_siblings` already sorts alphabetically.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added default `list_sibling_links(...) -> []` to base `FakeRepo` in tests/test_now_playing_panel.py**
- **Found during:** Task 1 verification (initial pytest run)
- **Issue:** Plan 71-00 added `_FakeRepoWithSiblings` (subclass) only for the new RED test, but the 11 pre-existing Phase 64 sibling tests still construct bare `FakeRepo`. With the new `_refresh_siblings` body calling `self._repo.list_sibling_links(...)` inside the existing try/except, the missing method raised `AttributeError`, which the broad `except Exception:` caught and hid the label. This broke `test_sibling_label_visible_for_aa_station_with_siblings` and `test_phase_64_sibling_label_unchanged_after_phase_67` (both assert `isHidden() is False`).
- **Fix:** Added a default `list_sibling_links(self, station_id: int) -> list: return []` method on the base `FakeRepo` class (after `get_station`). This makes the AA-only path equivalent to the pre-71 behavior (empty manual list -> merge with AA-only output -> identical render). The `_FakeRepoWithSiblings` subclass (Plan 71-00) continues to override for the merge test.
- **Files modified:** `tests/test_now_playing_panel.py` (added 7 lines: method + docstring).
- **Verification:** `uv run --with pytest --with pytest-qt pytest tests/test_now_playing_panel.py -k "siblings or sibling" -x` returns 12 passed (11 pre-existing + 1 new); full `tests/test_now_playing_panel.py` returns 136 passed.
- **Committed in:** `e957ea8` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking)
**Impact on plan:** Necessary to satisfy the plan's `done` criteria ("All existing tests/test_now_playing_panel.py tests that exercise the 'Also on:' surface ... remain GREEN"). Test-fixture extension only — no production-code or behavior changes beyond those specified in the plan. No scope creep.

## Issues Encountered

- `uv.lock` was incidentally updated by `uv run` from `2.1.68` -> `2.1.70` (matches `pyproject.toml` version 2.1.70). This is environment plumbing, not a plan deliverable; left unstaged and uncommitted.
- Pre-existing test-collection errors (`ModuleNotFoundError: No module named 'gi'`) and an unrelated Qt segfault in `test_main_window_underrun.py` exist in this worktree environment. Not caused by this plan; not addressed (out of scope per executor scope-boundary rule).
- Wave 1 sibling-baseline `test_richtext_baseline_unchanged_by_phase_71` (test_constants_drift.py) is correctly RED at count=4 in this worktree (Plan 71-03 in a parallel worktree drops it to 3). Plan 71-05's per-file RichText count for `now_playing_panel.py` remains 3 — invariant honored.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Wave 2 / Plan 71-05 GREEN gate complete. NowPlayingPanel renders merged AA + manual siblings without any widget reconstruction.
- Parallel-safe with Plan 71-03 (EditStationDialog picker UI) — zero file overlap.
- Plan 71-04 (settings_export round-trip) and Plan 71-03 (edit-dialog chip row) can now rely on the NowPlaying surface accepting any future Phase 71 sibling additions without further panel changes.

## Self-Check: PASSED

- `musicstreamer/ui_qt/now_playing_panel.py` exists and contains `find_manual_siblings`, `merge_siblings`, `list_sibling_links` references at the expected call sites.
- `tests/test_now_playing_panel.py` exists and contains the default `list_sibling_links` method on `FakeRepo`.
- `.planning/phases/71-sister-station-expansion-1-add-ability-to-link-sister-statio/71-05-SUMMARY.md` is being written by this Write call.
- Commit `e957ea8` exists in `git log --oneline -5` (verified pre-summary).

---
*Phase: 71-sister-station-expansion-1-add-ability-to-link-sister-statio*
*Completed: 2026-05-12*
