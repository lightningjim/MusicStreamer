---
phase: 60-gbs-fm-integration
plan: "10"
subsystem: gbs_api + ui
tags: [phase60, gap-closure, html-parser, active-playlist, queue-enumeration, tdd]
requires:
  - 60-02
  - 60-05
  - 60-08
provides:
  - "_QueueRowParser HTMLParser in gbs_api.py"
  - "queue_rows: list[dict] in _fold_ajax_events state"
  - "_parse_adds_html helper in gbs_api.py"
  - "Enumerated queue_rows renderer in _on_gbs_playlist_ready"
  - "_GBS_QUEUE_MAX_ROWS = 10 constant in now_playing_panel.py"
affects:
  - "now_playing_panel active-playlist widget"
  - "gbs_api _fold_ajax_events state shape"
requirements-completed: [GBS-01c]
key-decisions:
  - "D-10a: max 10 upcoming rows (cap at _GBS_QUEUE_MAX_ROWS)"
  - "D-10b: '{n}. {artist} - {title} [{duration}]' row format"
  - "D-10c: pllength summary line entirely replaced by enumeration"
  - "queue_html_snippets retained for backward-compat (zero callers, rev-2 decision)"
tech-stack:
  added: []
  patterns:
    - "_QueueRowParser(HTMLParser) mirrors _SongRowParser precedent in gbs_api.py"
    - "skip-discriminator: 'playing' or 'history' in tr.class => skip row"
    - "_parse_adds_html wraps feed/close in try/except (Pitfall 6 defensive)"
    - "_GBS_QUEUE_MAX_ROWS slice before enumerate loop (T-60-10-03 DoS mitigation)"
key-files:
  created: []
  modified:
    - musicstreamer/gbs_api.py
    - musicstreamer/ui_qt/now_playing_panel.py
    - tests/test_gbs_api.py
    - tests/test_now_playing_panel.py

# Metrics
duration: 15min
completed: "2026-05-04"
tasks: 3
files: 4
---

# Phase 60 Plan 10: Active Playlist Enumeration Summary

**One-liner:** Add _QueueRowParser + queue_rows state to gbs_api, replace pllength queue_summary with per-row enumeration in now_playing_panel renderer (D-10a/b/c defaults locked).

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-05-04T23:37:00Z
- **Tasks:** 3 (TDD-RED + 2x TDD-GREEN)
- **Files modified:** 4

## Accomplishments

- T8 closed: active-playlist widget now shows one row per upcoming queued track in `{n}. {artist} - {title} [{duration}]` format instead of the pllength "Playlist is X long with Y dongs" summary
- `_QueueRowParser(HTMLParser)` added to `gbs_api.py` after `_SongRowParser` — extracts entryid, songid, artist, title, duration from `<adds>` event HTML; skips rows with class containing 'playing' or 'history'
- `_parse_adds_html(html_str)` helper added — wraps feed/close in try/except per Pitfall 6 defensive pattern
- `_fold_ajax_events` now populates `state["queue_rows"]` (alongside retained `state["queue_html_snippets"]`)
- `_GBS_QUEUE_MAX_ROWS = 10` module-level constant added to `now_playing_panel.py`
- `_on_gbs_playlist_ready` renderer: `queue_summary` line removed (D-10c); `queue_rows` loop added with `[:_GBS_QUEUE_MAX_ROWS]` cap (D-10a); D-10b format applied
- All 4 threat mitigations applied: T-60-10-01 (PlainText QListWidgetItem), T-60-10-02 (playing/history skip), T-60-10-03 (_GBS_QUEUE_MAX_ROWS cap), T-60-10-04 (try/except in _parse_adds_html)
- 26 test_gbs_api.py tests pass (24 from 60-08 + 2 new parser tests)
- 76 test_now_playing_panel.py tests pass (74 from 60-09 + 2 new renderer tests; 1 updated in-place)

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | TDD-RED: 4 failing tests for parser + renderer | e7cf943 | tests/test_gbs_api.py, tests/test_now_playing_panel.py |
| 2 | TDD-GREEN: _QueueRowParser + queue_rows in fold_ajax_events | 06b1e3c | musicstreamer/gbs_api.py |
| 3 | TDD-GREEN: renderer enumerates queue_rows + existing test update | a4eaeb7 | musicstreamer/ui_qt/now_playing_panel.py, tests/test_now_playing_panel.py |

## Files Created/Modified

| File | Change |
|------|--------|
| `musicstreamer/gbs_api.py` | Added `_QueueRowParser` class (skip-discriminator for playing/history, entryid/songid/artist/title/duration extraction). Added `_parse_adds_html` helper. `_fold_ajax_events` state dict gains `"queue_rows": []`; `adds` branch now calls `state["queue_rows"].extend(_parse_adds_html(payload))`. `queue_html_snippets` retained (rev-2). |
| `musicstreamer/ui_qt/now_playing_panel.py` | Added `_GBS_QUEUE_MAX_ROWS = 10` constant. `_on_gbs_playlist_ready` renderer: replaced `queue_summary` single-item render with `queue_rows[:_GBS_QUEUE_MAX_ROWS]` loop using D-10b format. |
| `tests/test_gbs_api.py` | Appended `test_fetch_playlist_enumerates_queue` and `test_queue_parser_skips_playing_and_history`. |
| `tests/test_now_playing_panel.py` | Updated `test_gbs_playlist_populates_from_mock_state` (Step 3a: queue_summary assertion replaced with queue_rows enumeration assertions). Appended `test_gbs_playlist_renders_enumerated_queue` and `test_gbs_playlist_caps_queue_at_10`. |

## Decisions Made

1. **D-10a locked: max 10 rows** — `_GBS_QUEUE_MAX_ROWS = 10` via `[:_GBS_QUEUE_MAX_ROWS]` slice. Widget setMaximumHeight(180) shows ~6 rows; 10 provides scrollback without QListWidget bloat.

2. **D-10b locked: include duration** — format `"{n}. {artist} - {title} [{duration}]"` (graceful fallback to `"{n}. {artist} - {title}"` when duration is empty).

3. **D-10c locked: replace pllength summary** — the "Playlist is X long with Y dongs" line is no longer rendered. The jargon "dongs" is gbs.fm-internal and user-facing noise (per diagnosis §5c).

4. **queue_html_snippets retained (revision-2 decision)** — zero production callers found across `musicstreamer/`, `tests/`, `.planning/`. Cost of removal non-zero; benefit purely cosmetic. Retained alongside `queue_rows` with comment. Future plan can clean up if desired.

## TDD Gate Compliance

- RED gate: commit `e7cf943` — `test(60-10): add failing tests...` (4 tests failing: KeyError on queue_rows, ImportError on _parse_adds_html, count mismatches)
- GREEN gate 1: commit `06b1e3c` — `feat(60-10): _QueueRowParser + queue_rows...` (26 test_gbs_api.py tests pass)
- GREEN gate 2: commit `a4eaeb7` — `feat(60-10): renderer enumerates queue_rows...` (76 test_now_playing_panel.py tests pass)

## Deviations from Plan

### Notes on plan iteration

**test_gbs_playlist_populates_from_mock_state in-place update (Step 3a)** — Required by revision-2 plan directive. The existing test passed `queue_summary` and asserted `assert any("Playlist is 11:21" in t for t in items)`. After the D-10c renderer change, this assertion would fail. Updated in-place: added `queue_rows` to state dict, replaced "Playlist is 11:21" assertion with `"1. Foo - Bar [3:00]"` and `"2. Baz - Quux [4:30]"` assertions, added negative assertion `assert not any("Playlist is 11:21" in t for t in items)`. This is explicitly documented in the revision-2 plan as Step 3a and is not an unplanned deviation.

**None — plan executed exactly as written for all other items.**

## User Feedback Hooks

- If the user wants the pllength summary back alongside enumeration (e.g., to see total queue duration "11:34"), capture as a new gap plan or revise this plan with D-10c flipped to "keep summary as additional row". The `queue_summary` key is still present in `_fold_ajax_events` state; only the renderer was changed.
- If the user wants a different row format (e.g., omit duration, add track number prefix differently), revise D-10b in a follow-up plan.
- If the user wants more or fewer rows visible, adjust `_GBS_QUEUE_MAX_ROWS` constant in `now_playing_panel.py`.

## Known Stubs

None. Both the parser and renderer are fully wired. queue_rows is populated from real fixture data (verified by test_fetch_playlist_enumerates_queue). No placeholder values or TODO markers introduced.

## Threat Flags

No new trust boundaries beyond what is in the plan's `<threat_model>`. All 4 threats mitigated:

| Flag | File | Mitigation |
|------|------|------------|
| T-60-10-01: HTML injection via artist/title | gbs_api.py + now_playing_panel.py | `handle_data` extracts plain str; QListWidgetItem uses PlainText by default |
| T-60-10-02: Parser misidentifies rows | gbs_api.py `_QueueRowParser` | Skip-discriminator: "playing" OR "history" substring in class → skip; covered by `test_queue_parser_skips_playing_and_history` |
| T-60-10-03: DoS via thousands of tr rows | now_playing_panel.py | `queue_rows[:_GBS_QUEUE_MAX_ROWS]` cap before loop |
| T-60-10-04: Malformed HTML raises | gbs_api.py `_parse_adds_html` | try/except wrapping feed/close → returns [] on any exception |

## Self-Check

### Files exist:

- [x] `musicstreamer/gbs_api.py` — contains `_QueueRowParser`, `_parse_adds_html`, `queue_rows`
- [x] `musicstreamer/ui_qt/now_playing_panel.py` — contains `_GBS_QUEUE_MAX_ROWS`, `queue_rows` loop
- [x] `tests/test_gbs_api.py` — contains `test_fetch_playlist_enumerates_queue`, `test_queue_parser_skips_playing_and_history`
- [x] `tests/test_now_playing_panel.py` — contains `test_gbs_playlist_renders_enumerated_queue`, `test_gbs_playlist_caps_queue_at_10`

### Commits exist:

- [x] e7cf943 — RED test commit
- [x] 06b1e3c — GREEN parser commit
- [x] a4eaeb7 — GREEN renderer + test update commit

### Test counts:

- test_gbs_api.py: 26 tests (24 from 60-08 + 2 new parser tests = 26 as specified)
- test_now_playing_panel.py: 76 tests (74 from 60-09 + 2 new renderer + 1 updated in-place = 76 effective as specified)

## Self-Check: PASSED
