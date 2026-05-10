---
phase: 67
plan: "02"
subsystem: url_helpers
tags: [pure-helper, random-sample, html-escape, no-qt, tag-normalization, tdd]
dependency_graph:
  requires: [67-01]
  provides: [pick_similar_stations, render_similar_html]
  affects: [musicstreamer/url_helpers.py, tests/test_pick_similar_stations.py]
tech_stack:
  added: [random (stdlib), musicstreamer.filter_utils.normalize_tags, musicstreamer.models.Station]
  patterns: [pure-function, seedable-rng, html-escape-both-fields, clamp-sample-size]
key_files:
  created: [tests/test_pick_similar_stations.py]
  modified: [musicstreamer/url_helpers.py]
decisions:
  - "pick_similar_stations added after render_sibling_html at module end (Phase 51/64 placement convention)"
  - "rng=rng or random idiom enables seedable RNG injection without extra None checks"
  - "k=min(sample_size, len(pool)) clamp prevents random.sample ValueError (Pitfall 1)"
  - "find_aa_siblings called with streams[0].url; guarded by if current_station.streams (Pitfall 11)"
  - "render_similar_html escapes BOTH Station.name AND Station.provider_name via html.escape(quote=True)"
  - "Test file created in this plan as Rule 3 deviation — Plan 01 (wave 0) had not committed before wave 1 spawned"
metrics:
  duration: "3 minutes"
  completed: "2026-05-10T13:06:27Z"
  tasks: 1
  files_modified: 2
---

# Phase 67 Plan 02: Pure Helper Functions for Similar Stations Summary

Pure-Python pool derivation + HTML rendering for Phase 67's similar-stations feature: `pick_similar_stations` samples same-provider and same-tag pools with AA-sibling exclusion and seeded-RNG injection; `render_similar_html` renders a vertical `<br>`-separated link list with `html.escape` on both name and provider.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED | Add failing tests for pick_similar_stations + render_similar_html | 10d3643 | tests/test_pick_similar_stations.py (+316) |
| GREEN | Add pick_similar_stations + render_similar_html to url_helpers.py | 7f6cf46 | musicstreamer/url_helpers.py (+128) |

## Verification Results

- `tests/test_pick_similar_stations.py`: 22 tests — all passed (RED → GREEN)
- `tests/test_aa_siblings.py`: 22 tests — all passed (Phase 64 regression preserved)
- `tests/test_filter_utils.py`: 35 tests — all passed (normalize_tags consumers unaffected)
- Import sanity: `python -c "from musicstreamer.url_helpers import pick_similar_stations, render_similar_html; print('OK')"` → OK

## Acceptance Criteria

- `grep -c "^def pick_similar_stations("`: 1 ✓
- `grep -c "^def render_similar_html("`: 1 ✓
- `grep -c "^def find_aa_siblings("`: 1 ✓ (Phase 64 untouched)
- `grep -c "^def render_sibling_html("`: 1 ✓ (Phase 64 untouched)
- `grep -c "^import random"`: 1 ✓
- `grep -c "^from musicstreamer.filter_utils import normalize_tags"`: 1 ✓
- `grep -c "^from musicstreamer.models import Station"`: 1 ✓
- `grep -c "html.escape"`: 5 (≥3 required) ✓
- `grep -c 'href_prefix'`: 2 ✓
- `grep -c "k=min(sample_size, len("`: 2 ✓ (clamp on both pools)
- `grep -c '"<br>"'`: 1 ✓
- `grep -c "find_aa_siblings("`: 2 ✓ (def line + call from pick_similar_stations)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created test file from Plan 01 dependency**
- **Found during:** Pre-execution dependency check
- **Issue:** Plan 02 depends on `67-01` (wave 0) which creates `tests/test_pick_similar_stations.py`. The test file did not exist when wave 1 started — the Plan 01 worktree agent was still active but had not committed.
- **Fix:** Created `tests/test_pick_similar_stations.py` as part of this plan's execution, following the exact spec from 67-01-PLAN.md Task 1. The file contains 22 tests (≥18 required) with full RED-state ImportError, factory function, and all required test functions.
- **Files modified:** `tests/test_pick_similar_stations.py` (new file, 316 lines)
- **Commit:** 10d3643

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes. All new code is pure-function helpers with no I/O. Threat mitigations implemented:
- T-67-02-01: `html.escape(s.name, quote=True)` — locked by test_render_similar_html_escapes_name
- T-67-02-02: `html.escape(s.provider_name or "", quote=True)` — locked by test_render_similar_html_escapes_provider
- T-67-02-03: href integer-only payload — locked by test_render_similar_html_href_payload_is_integer_only
- T-67-02-04: k=min clamp — locked by pool-lt-5 tests
- T-67-02-05: empty-streams guard — locked by test_pick_similar_stations_handles_current_with_empty_streams

## Known Stubs

None. Both functions are fully implemented and wired to the test corpus.

## TDD Gate Compliance

1. RED commit: `test(67-02)` — test file created (22 tests fail with ImportError)
2. GREEN commit: `feat(67-02)` — production code implemented (22 tests pass)
3. No REFACTOR phase needed (implementation was clean on first pass)

## Self-Check: PASSED

Files exist:
- `musicstreamer/url_helpers.py` — FOUND ✓
- `tests/test_pick_similar_stations.py` — FOUND ✓

Commits exist:
- 10d3643 (RED phase) — FOUND ✓
- 7f6cf46 (GREEN phase) — FOUND ✓
