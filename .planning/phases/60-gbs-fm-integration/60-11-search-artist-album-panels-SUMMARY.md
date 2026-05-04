---
phase: 60-gbs-fm-integration
plan: 11
subsystem: gbs-search-dialog
tags: [phase60, gap-closure, search, artist-album-panels, fixture-capture, html-parser, qt-dialog, tdd]
dependency_graph:
  requires: [60-02, 60-07, 60-10]
  provides:
    - "_ArtistAlbumParser: HTMLParser extracts <p class='artists'> blocks from /search HTML"
    - "search() artist_links + album_links keys in return dict"
    - "GBSSearchDialog _artist_list + _album_list QListWidget panels (hidden by default, D-11c)"
    - "metadata_ready Signal on _GbsSearchWorker (streams parsed lists separately from finished)"
    - "click navigation per locked D-11a=Shape 4 (free-text search fallback for both surfaces)"
  affects: [gbs_api.py, gbs_search_dialog.py]
tech_stack:
  added: []
  patterns:
    - "HTMLParser subclass discriminating two same-class blocks by leading text node"
    - "Dual-signal pattern (finished + metadata_ready) for backward-compatible extension"
    - "Qt ORDERING INVARIANT comment pinning emit order (finished BEFORE metadata_ready)"
    - "D-11c hide-when-empty: panels start hidden, shown only via _on_metadata_ready"
key_files:
  created: []
  modified:
    - musicstreamer/gbs_api.py
    - musicstreamer/ui_qt/gbs_search_dialog.py
    - tests/test_gbs_api.py
    - tests/test_gbs_search_dialog.py
decisions:
  - "D-11a=Shape 4: both /artist/<id> and /album/<id> have no <table class='songs'> per Task 0 fixture inspection; both surfaces use Option A free-text search fallback"
  - "D-11b=80px: max-height for artist/album QListWidget panels (prevents panels dominating dialog)"
  - "D-11c=hide-when-empty: panels not rendered when artist_links/album_links is []"
  - "metadata_ready emits AFTER finished (ORDERING INVARIANT) to prevent _clear_table hiding newly-populated panels"
requirements_completed: [GBS-01e]
metrics:
  duration_minutes: 45
  completed_date: "2026-05-04"
  tasks_completed: 4
  files_modified: 4
  tests_added: 7
  tests_total: 49
---

# Phase 60 Plan 11: Search Artist/Album Panels Summary

**One-liner:** Artist:/Album: QListWidget panels above song results table using HTMLParser discriminating same-class `<p class="artists">` blocks by leading text node; Shape 4 (both Option A) click navigation via free-text search.

## Performance

- Duration: ~45 minutes
- Tasks completed: 4/4 (Task 0 completed by orchestrator)
- Tests added: 7 (3 parser + 2 panel + 2 integration)
- Total passing tests: 49 (29 api + 20 dialog)

## Accomplishments

1. **T12 closed**: Search dialog now mirrors gbs.fm's Artist:/Album: panels above the song results table. Panels show on page 1 with matches; hidden on page 2+ and empty search (D-11c).

2. **`_ArtistAlbumParser`**: New HTMLParser subclass added after `_QueueRowParser` (wave-6 anchor) in `gbs_api.py`. Discriminates Artist vs Album blocks by inspecting the leading text node inside `<p class="artists">` — both block types share the same CSS class (diagnosis §2a). Each entry yields `{"text": str, "url": str}`.

3. **`search()` extended**: Return dict gains `artist_links` and `album_links` keys. Backward-compatible — pre-existing callers reading only `results/page/total_pages` are unaffected (confirmed: all 26 pre-existing api tests still pass).

4. **Dual-signal pattern**: `_GbsSearchWorker` keeps its existing `finished(list, int, int)` signal stable. New `metadata_ready(list, list)` signal carries the parsed artist/album links. ORDERING INVARIANT enforced: `finished` emits BEFORE `metadata_ready` so `_clear_table` never hides a just-populated panel.

5. **Dialog panels**: `_artist_list` + `_album_list` QListWidgets inserted above the results table in `_build_ui()`. Max-height 80px (D-11b). Both start hidden. `_on_metadata_ready()` slot populates and shows/hides per D-11c.

6. **Shape 4 navigation**: Click handlers use `item.text()` → `_search_edit.setText()` → `_start_search()` (free-text search fallback). No `fetch_artist_songs`/`fetch_album_songs` helper needed — Shape 4 doesn't fetch artist/album pages.

## Task Commits

| Task | Name | Commit | Key Changes |
|------|------|--------|-------------|
| 0 | Capture fixtures + lock D-11a | 7376b1a | artist_4803.html, album_1488.html, script update |
| 1 | RED: 5 failing tests | 90ed2b9 | test_gbs_api.py (+3), test_gbs_search_dialog.py (+2) |
| 2 | GREEN: _ArtistAlbumParser | 8b95efa | musicstreamer/gbs_api.py |
| 3 | GREEN: Dialog panels | 03ffdbb | musicstreamer/ui_qt/gbs_search_dialog.py |
| 4 | Integration tests Shape 4 | 4d1e1db | test_gbs_search_dialog.py (+2) |

## Files Modified

| File | Change |
|------|--------|
| `musicstreamer/gbs_api.py` | Added `_ArtistAlbumParser` class + `_parse_artist_album_html()` helper; updated `search()` to return `artist_links`/`album_links` |
| `musicstreamer/ui_qt/gbs_search_dialog.py` | Added `metadata_ready` signal + ORDERING INVARIANT comment; `_artist_list`/`_album_list` panels in `_build_ui()`; `_on_metadata_ready()` slot; `_clear_table()` extended; Shape 4 click handlers |
| `tests/test_gbs_api.py` | Added 3 parser tests: `test_search_returns_artist_links`, `test_search_returns_album_links`, `test_search_page2_has_no_artist_album_links` |
| `tests/test_gbs_search_dialog.py` | Added 2 panel tests + 2 Shape 4 integration tests |

## Decisions Made

- **D-11a=Shape 4**: Task 0 found `grep -c '<table class="songs"'` = 0 for both `artist_4803.html` and `album_1488.html`. Both surfaces → Option A (free-text search fallback). No `fetch_artist_songs`/`fetch_album_songs` needed.
- **D-11b=80px**: Max-height for both panels (default from plan; prevents panels dominating dialog on queries like "test" which return 46+ artist matches).
- **D-11c=hide-when-empty**: Panels completely hidden when `artist_links`/`album_links == []`. Shows only via `_on_metadata_ready()` after a successful page-1 search with matches.
- **metadata_ready ordering**: `finished` MUST emit before `metadata_ready` (ORDERING INVARIANT comment block in `_GbsSearchWorker.run()` pins this — 3 occurrences in the source).

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED | 90ed2b9 `test(60-11)` | PASS — 5 tests failed as expected |
| GREEN (parser) | 8b95efa `feat(60-11)` | PASS — 29 api tests pass |
| GREEN (dialog) | 03ffdbb `feat(60-11)` | PASS — 47 tests pass (29 api + 18 dialog) |
| Integration | 4d1e1db `test(60-11)` | PASS — 49 tests pass |

## Deviations from Plan

None — plan executed exactly as written. D-11a was pre-locked to Shape 4 by the orchestrator (Task 0), and all subsequent tasks collapsed to Shape 4 code paths as specified in the plan caveats.

## Known Stubs

None introduced by this plan. The `placeholder = QStandardItem("")` at line 464 of `gbs_search_dialog.py` is a pre-existing artifact from the results table's "Add!" button column — not from this plan.

## User-Visible Follow-Ups

- **Shape 4 semantic false positives**: Clicking "Testament" re-searches with `query="Testament"` — this is a free-text search, not a filtered `/artist/4803` lookup. If gbs.fm adds a `?artist_id=` or `?album_id=` search filter parameter in the future, navigation could be hardened. For now, Option A is the correct call given the Task 0 fixture inspection.
- **Album name collisions**: Album names containing common words (e.g. "Greatest Hits") may return noisy results. Same fundamental limitation as Option A for artists.
- **D-11c panel visibility on pagination**: Clicking Prev/Next re-runs `_kick_search_worker()` → `_clear_table()` which hides panels, then `metadata_ready` re-shows them only if the new page is page 1 with matches. This matches gbs.fm's web behavior (artist/album panels only on page 1).

## Threat Flags

No new threat surface beyond what was covered in the plan's threat model. All mitigations applied:
- T-60-11-01 (HTML injection): `QListWidgetItem` uses PlainText (T-40-04 compliant).
- T-60-11-02 (off-host hrefs): Shape 4 uses `item.text()` not the href — off-host URLs cannot escape the search query path.
- T-60-11-03 (DoS via too many links): `setMaximumHeight(80)` limits visible rows; list is scrollable.
- T-60-11-06 (future reorder): ORDERING INVARIANT comment block (3 occurrences in source).

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| SUMMARY.md exists | FOUND |
| Task 1 commit 90ed2b9 | FOUND |
| Task 2 commit 8b95efa | FOUND |
| Task 3 commit 03ffdbb | FOUND |
| Task 4 commit 4d1e1db | FOUND |
| 49 tests pass (api + dialog) | PASS |
| ORDERING INVARIANT >= 1 | PASS (3 occurrences) |
| _ArtistAlbumParser in gbs_api.py | PASS (2 occurrences) |
| File ordering: _SongRowParser < _QueueRowParser < _ArtistAlbumParser < search() | PASS (lines 305, 384, 496, 579) |
