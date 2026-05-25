---
phase: 74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-
plan: "05"
subsystem: soma-import
tags: [gap-closure, soma-02, cr-01, uat-f-01, tdd]
gap_closure: true
requirements: [SOMA-02]
dependency_graph:
  requires:
    - 74-02 (soma_import.py exists with _TIER_BY_FORMAT_QUALITY)
    - 74-REVIEW.md CR-01 (verbatim reference implementation)
    - 74-VERIFICATION.md G-02 (gap source-of-truth)
  provides:
    - musicstreamer.soma_import._bitrate_from_url(url, default) helper
    - per-stream bitrate_kbps override in fetch_channels from relay URL slug
    - _BITRATE_FROM_URL_RE module-level compiled pattern
  affects:
    - Phase 70 hi-res indicator sort (now sees true MP3 bitrate)
    - tier quality map (hi/hi2/med/low) accuracy for non-128 channels
tech_stack:
  added:
    - re (stdlib) module imported into soma_import
  patterns:
    - "URL-slug regex with default-fallback"
    - "verbatim reference impl reuse from REVIEW.md (no paraphrase)"
key_files:
  created: []
  modified:
    - musicstreamer/soma_import.py
    - tests/test_soma_import.py
decisions:
  - "Reused 74-REVIEW.md CR-01 reference implementation verbatim (regex, helper body, fetch_channels override) per project memory 'Mirror X decisions must cite source'"
  - "Did NOT modify _TIER_BY_FORMAT_QUALITY[(mp3,highest)].bitrate_kbps=128 — that is the intentional fallback for unparseable slugs per CR-01"
  - "Did NOT clean up unused urllib.error import (IN-02) — explicitly out of scope per plan task action notes"
metrics:
  duration_minutes: 5
  completed_at: "2026-05-14T19:14:58Z"
  tasks_completed: 2
  files_modified: 2
  tests_added: 4
  tests_total: 15
---

# Phase 74 Plan 05: Bitrate URL-Slug Parser (G-02 Closure) Summary

**One-liner:** Added `_bitrate_from_url` URL-slug parser (verbatim from REVIEW.md CR-01) so SomaFM channels like Synphaera Radio store `bitrate_kbps=256` instead of the table default 128 — closes gap G-02 (SOMA-02 / UAT Finding F-01).

## What Changed

### `musicstreamer/soma_import.py`

1. **Added `import re`** in the existing alphabetical import block (between `os` and `tempfile`).
2. **Added module-level constants + helper** (immediately after `_TIER_BY_FORMAT_QUALITY`, before `_resolve_pls`) — body is verbatim from `74-REVIEW.md` CR-01 lines 48-72:

   ```python
   _BITRATE_FROM_URL_RE = re.compile(r"-(\d+)-(?:mp3|aac|aacp)\b")

   def _bitrate_from_url(url: str, default: int) -> int:
       """Extract bitrate from SomaFM ICE URL slug like ice2.somafm.com/foo-256-mp3.

       Falls back to ``default`` when the slug is missing or non-numeric.
       """
       m = _BITRATE_FROM_URL_RE.search(url)
       if m:
           try:
               return int(m.group(1))
           except ValueError:
               pass
       return default
   ```

3. **Wired into `fetch_channels` `streams.append` site** — added the per-stream `parsed_bitrate` line and replaced `tier_meta["bitrate_kbps"]` with `parsed_bitrate` in the dict literal. Table default remains the fallback path inside `_bitrate_from_url`.

### `tests/test_soma_import.py`

Appended 4 new tests after `test_user_agent_literal_present_in_source`:

1. `test_bitrate_from_url_parses_256_mp3_slug` — direct unit test for Synphaera-style URL (256).
2. `test_bitrate_from_url_parses_192_mp3_slug` — direct unit test for Groove Salad 192k relay URL.
3. `test_bitrate_from_url_falls_back_to_default_for_unparseable_slug` — two assertions covering both fallback paths (missing slug + non-numeric bitrate `-XYZ-mp3`).
4. `test_fetch_channels_overrides_bitrate_from_relay_url_slug` — end-to-end integration: monkeypatches `_resolve_pls` to return `-256-mp3` URLs on MP3-highest PLS URLs (those containing "256"), delegates other tiers to `_make_any_resolve_pls_stub`. Asserts `channels[0]["streams"]` has 5 streams with `quality == "hi"` AND `bitrate_kbps == 256`.

## Reference to CR-01 / VERIFICATION G-02 Closure

- **74-REVIEW.md CR-01 (lines 48-72):** Reference implementation reused verbatim — regex pattern, helper body, and `fetch_channels` override pattern.
- **74-VERIFICATION.md G-02 (lines 19-29):** Gap closed. The two `missing[]` items —
  1. "Add `_bitrate_from_url(url, default)` helper in soma_import.py using `re.compile(r'-(\d+)-(?:mp3|aac|aacp)\b')` and override the table default per stream in fetch_channels."
  2. "Add a RED unit test feeding a PLS body with `synphaera-256-mp3` URLs and asserting the stored bitrate_kbps is 256 (not 128)."
  — are now both satisfied by Tasks 1 + 2.
- **74-04-UAT-LOG.md Finding F-01:** Synphaera Radio bitrate-parse failure will be re-verified in Plan 74-07.

## Test Results

### `tests/test_soma_import.py` — 15 passed (11 pre-existing + 4 new)

```
test_fetch_channels_parses_canonical_blob PASSED
test_fetch_channels_maps_four_tiers_twenty_streams_per_channel PASSED
test_fetch_channels_position_numbering_tier_base_times_ten PASSED
test_aacp_codec_maps_to_AAC_not_aacplus PASSED
test_resolve_pls_returns_all_five_direct_urls PASSED
test_import_skips_when_url_exists PASSED
test_import_three_channels_full_path_creates_stations_and_streams PASSED
test_logo_failure_is_non_fatal PASSED
test_per_channel_exception_skips_only_that_channel PASSED
test_no_aacplus_codec_literal_in_source PASSED
test_user_agent_literal_present_in_source PASSED
test_bitrate_from_url_parses_256_mp3_slug PASSED              # NEW (Task 1)
test_bitrate_from_url_parses_192_mp3_slug PASSED              # NEW (Task 1)
test_bitrate_from_url_falls_back_to_default_for_unparseable_slug PASSED  # NEW (Task 1)
test_fetch_channels_overrides_bitrate_from_relay_url_slug PASSED  # NEW (Task 1)
```

### Regression Gate — `tests/test_main_window_soma.py` + `tests/test_constants_drift.py` — 15 passed

All related Phase 74 tests still PASS; no cross-file regressions from the soma_import change.

(Note: `pytest-qt` plugin is required for `test_main_window_soma.py` because of the `qtbot` fixture. Tests pass when invoked as `uv run --with pytest --with pytest-qt pytest …`.)

## TDD Gate Compliance

- **RED gate (Task 1):** `test(74-05): add 4 RED tests for _bitrate_from_url URL-slug parser` — commit `47ae178`. All 4 new tests failed against pre-Task-2 source (3 AttributeErrors + 1 assertion failure).
- **GREEN gate (Task 2):** `feat(74-05): add _bitrate_from_url parser, override fetch_channels bitrate per stream` — commit `13897a3`. All 4 new tests PASS; 11 pre-existing tests PASS.
- **REFACTOR gate:** Not needed — implementation was already at the verbatim CR-01 reference form. No additional cleanup commit.

## Deviations from Plan

None — plan executed exactly as written. CR-01 reference implementation reused verbatim per planning intent.

## Acceptance Criteria — All Met

### Task 1
- `grep -c "^def test_bitrate_from_url_parses_256_mp3_slug" tests/test_soma_import.py` → 1
- `grep -c "^def test_bitrate_from_url_parses_192_mp3_slug" tests/test_soma_import.py` → 1
- `grep -c "^def test_bitrate_from_url_falls_back_to_default_for_unparseable_slug" tests/test_soma_import.py` → 1
- `grep -c "^def test_fetch_channels_overrides_bitrate_from_relay_url_slug" tests/test_soma_import.py` → 1
- 4 new tests RED before Task 2; 11 pre-existing tests still PASS

### Task 2
- `grep -c "^import re$" musicstreamer/soma_import.py` → 1
- `grep -c "_BITRATE_FROM_URL_RE" musicstreamer/soma_import.py` → 2
- `grep -c "_bitrate_from_url" musicstreamer/soma_import.py` → 2 (def + call site)
- `grep -F 'parsed_bitrate = _bitrate_from_url(relay_url, tier_meta["bitrate_kbps"])'` → 1
- `grep -F '"bitrate_kbps": parsed_bitrate'` → 1
- `grep -F 'r"-(\d+)-(?:mp3|aac|aacp)\b"'` → 1
- 15 soma_import tests PASS; related Phase 74 tests PASS (no regressions)

## Commits

| Task | Type | Hash      | Message                                                                 |
|------|------|-----------|-------------------------------------------------------------------------|
| 1    | test | `47ae178` | `test(74-05): add 4 RED tests for _bitrate_from_url URL-slug parser`    |
| 2    | feat | `13897a3` | `feat(74-05): add _bitrate_from_url parser, override fetch_channels bitrate per stream` |

## Known Stubs

None.

## Threat Flags

None — the regex pattern is linear-time (no nested quantifiers / no ReDoS surface) and the bitrate int is parameterised into SQL inserts downstream. Threat model T-74.1-01 / T-74.1-02 already addressed in plan and not violated.

## Self-Check

- `musicstreamer/soma_import.py` — FOUND (modified, import re + helper + override present)
- `tests/test_soma_import.py` — FOUND (4 new tests appended)
- `.planning/phases/74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-/74-05-SUMMARY.md` — FOUND (this file)
- Commit `47ae178` — FOUND on `worktree-agent-a1699393da284e249`
- Commit `13897a3` — FOUND on `worktree-agent-a1699393da284e249`

## Self-Check: PASSED
