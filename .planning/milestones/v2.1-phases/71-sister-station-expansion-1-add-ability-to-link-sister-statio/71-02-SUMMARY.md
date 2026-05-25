---
phase: 71
plan: 02
subsystem: url_helpers
tags: [pure-helper, sibling-station, merge-layer, wave-1]
dependency_graph:
  requires:
    - "71-00 RED contract (find_manual_siblings + merge_siblings test signatures in tests/test_station_siblings.py)"
  provides:
    - "find_manual_siblings(stations, current_station_id, link_ids) -> list[tuple[str,int,str]]"
    - "merge_siblings(aa_siblings, manual_siblings) -> list[tuple[str,int,str]]"
  affects:
    - "Plan 71-03 (EditStationDialog chip row) — will consume find_manual_siblings output"
    - "Plan 71-05 (NowPlayingPanel) — will consume merge_siblings(aa, manual) output through render_sibling_html (signature unchanged)"
tech_stack:
  added: []
  patterns:
    - "Phase 64 D-03 colocation: pure-helper promotion into url_helpers.py module"
    - "find_aa_siblings self-exclusion (line 210) mirrored in find_manual_siblings"
    - "Casefold sort key for case-insensitive alphabetical stability"
    - "dedup-by-id with seen-set + ordered list pattern"
key_files:
  created: []
  modified:
    - "musicstreamer/url_helpers.py (added 42 lines, lines 237-277 for the two new pure helpers, between find_aa_siblings@171 and render_sibling_html@279)"
decisions:
  - "D-01 honored: manual sibling link semantics are bidirectional and order-stable per find_manual_siblings input contract"
  - "D-03 honored: helpers colocated with find_aa_siblings/render_sibling_html per Phase 64 D-03 promotion convention"
  - "D-15 honored: merge_siblings AA-precedence on collision (AA chip surfaces, manual duplicate dropped — so collision station gets no × button)"
metrics:
  duration_minutes: 2
  tasks_completed: 1
  files_modified: 1
  completed_date: "2026-05-12"
---

# Phase 71 Plan 02: Sister Station Expansion — Pure Helpers Summary

One-liner: Added two pure helpers (`find_manual_siblings`, `merge_siblings`) to `musicstreamer/url_helpers.py` — the data-transformation layer between Repo CRUD (Plan 71-01) and the rendering surfaces (Plans 71-03 EditStationDialog, 71-05 NowPlayingPanel) — turning the 4 Wave 0 RED tests GREEN with a purely additive diff.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add find_manual_siblings + merge_siblings to musicstreamer/url_helpers.py | be98cc8 | musicstreamer/url_helpers.py |

## What Was Built

### `find_manual_siblings(stations, current_station_id, link_ids)`

Inserted at `musicstreamer/url_helpers.py` lines 237-260 (immediately after `find_aa_siblings`).

- Returns `list[tuple[provider_name_or_empty, station_id, station_name]]` — tuple shape matches `find_aa_siblings` for input-compatibility with `render_sibling_html`.
- Defensive self-exclusion: drops `current_station_id` from output even if it appears in `link_ids` (mirrors `find_aa_siblings` line 210 pattern).
- Silently drops stale `link_ids` that don't correspond to any station in the input list (defensive against orphan rows surviving CASCADE in concurrent DB scenarios).
- Sort: alphabetical by `station_name` using `casefold()` for case-insensitive stability.
- First tuple element is `station.provider_name or ""` — empty-string fallback for stations with no provider; `render_sibling_html`'s `name_for_slug.get(slug, slug)` fallback at line 301 transparently handles both populated and empty strings.

### `merge_siblings(aa_siblings, manual_siblings)`

Inserted at `musicstreamer/url_helpers.py` lines 263-277 (immediately after `find_manual_siblings`, before `render_sibling_html`).

- Dedup by `station_id` (tuple's integer second element).
- AA-precedence on collision: when a station_id appears in both lists, the AA tuple is preserved and the manual tuple is dropped. This makes the surviving entry render as an AA chip (no `×` per D-15).
- Order-stable: aa_siblings come first verbatim, then non-duplicate manual_siblings in their input order.
- Pure function: builds `seen: set[int]` from AA ids, iterates manual list once, appends + adds to `seen`.

## Insertion Line Range

| Helper | Lines | Position |
|--------|-------|----------|
| `find_manual_siblings` | 237-260 | After `find_aa_siblings` (ends at 234), before next helper |
| `merge_siblings` | 263-277 | After `find_manual_siblings`, before `render_sibling_html` (now at 279) |

Prior to this plan: `render_sibling_html` was at line 237. After this plan: it is at line 279. No deletions; only insertions in the gap between `find_aa_siblings` (ends line 234) and the previous location of `render_sibling_html`.

## Verification

### Plan 71-00 RED tests turned GREEN (4 of 4 helper tests)

```
$ uv run --with pytest pytest tests/test_station_siblings.py \
    -k "find_manual_siblings or merge_siblings" --tb=short
collected 35 items / 31 deselected / 4 selected
tests/test_station_siblings.py ....                                      [100%]
======================= 4 passed, 31 deselected in 0.06s =======================
```

The 4 specific tests:
- `test_find_manual_siblings_tuple_shape`
- `test_find_manual_siblings_excludes_self`
- `test_find_manual_siblings_sorts_alphabetically`
- `test_merge_siblings_dedup_by_station_id`

Note: the test module previously failed at *collection* time with `ImportError: cannot import name 'find_manual_siblings'` (the canonical Phase 47/62/68/70 import-fail-as-RED convention noted in tests/test_station_siblings.py docstring). After this plan, the module imports cleanly and the 4 helper tests pass.

### Rendering invariant preserved — `render_sibling_html` signature unchanged

```
$ uv run --with pytest pytest tests/test_aa_siblings.py -x --tb=short
collected 22 items
tests/test_aa_siblings.py ......................                         [100%]
============================== 22 passed in 0.05s ==============================
```

All 22 AA sibling tests still GREEN. Per 71-RESEARCH Pitfall 2, the existing `(siblings: list[tuple[str, int, str]], current_name: str) -> str` signature was preserved verbatim. The `name_for_slug.get(slug, slug)` fallback at line 301 (was 259 pre-plan) transparently handles the manual tuple's `provider_name` string in the first position — same code path as the existing "unknown slug" fallback test (`test_render_sibling_html_unknown_slug_falls_back_to_slug_literal`).

### Acceptance criteria — all 9 passed

| Check | Expected | Actual |
|-------|----------|--------|
| `grep -c '^def find_manual_siblings'` | 1 | 1 |
| `grep -c '^def merge_siblings'` | 1 | 1 |
| `grep -c 'casefold' url_helpers.py` | ≥ existing + 1 | 4 (existed: 3; new: 1 in `find_manual_siblings` sort key) |
| `grep -c '^def render_sibling_html'` | 1 (unchanged) | 1 |
| `git diff` deletions count | 0 | 0 (purely additive: `1 file changed, 42 insertions(+)`) |
| `pytest -k "find_manual_siblings or merge_siblings"` | 4 passes | 4 passes |
| `pytest tests/test_aa_siblings.py` | all GREEN | 22/22 passes |
| `grep -c '^from PySide6\|^import PySide6\|^from PyQt'` | 0 | 0 |
| Repo / sqlite3 actual imports | 0 | 0 (3 grep hits are docstring/comment text only; no `import` statements) |

## Decisions Made

- **Defensive self-exclusion**: kept even though `Repo.list_sibling_links` should never return the queried id, mirroring `find_aa_siblings` line 210 — guards against caller bugs and test doubles that bypass Repo. (71-RESEARCH Q1)
- **`provider_name or ""` empty-string fallback**: chosen over `None`-in-tuple so the consuming renderer never has to special-case None. The empty string flows through `render_sibling_html`'s `name_for_slug.get("", "")` fallback path correctly (`name_for_slug.get(slug, slug)` returns `""` for slug `""`, and the existing HTML-escape path handles empty strings safely). (71-RESEARCH Q1)
- **AA precedence in `merge_siblings`**: matches D-15 — when the same station qualifies as both an AA cross-network sibling AND a manually-linked sibling, surface the AA chip (no `×` button) rather than the manual chip. Prevents accidental unlink of an AA cross-network relationship via the manual `×`. (71-RESEARCH Q2)
- **Casefold sort key over `lower()`**: standard Unicode-correct case-insensitive sort idiom; consistent with `pick_similar_stations` line 333 which already uses `t.casefold()`. (71-RESEARCH Q1)

## Deviations from Plan

None — plan executed exactly as written.

The plan specified verbatim function bodies in 71-PATTERNS.md lines 360-402, and the implementation matches those bodies character-for-character apart from a minor docstring whitespace tweak (blank line before "Returns aa_siblings + non-duplicate manual_siblings." in `merge_siblings`, for PEP-257 readability).

## Self-Check: PASSED

- musicstreamer/url_helpers.py: FOUND (modified with 42 insertions)
- Commit be98cc8: FOUND in git log
- 4 RED tests now GREEN: verified by pytest output
- 22 AA invariant tests still GREEN: verified by pytest output
- No Qt imports added: verified by grep (0)
- No DB / Repo imports added: verified by grep (only docstring/comment text mentions)
- render_sibling_html signature preserved: verified by `grep -c '^def render_sibling_html' = 1` and AA test pass
