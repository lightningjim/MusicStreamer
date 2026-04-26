---
phase: 47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame
plan: 07
subsystem: audioaddict-import
type: gap_closure
tags: [audioaddict, codec, failover, uat-gap-3]
gap_closure: true
closes_uat_gaps: [3]
depends_on: [47-06]
requires:
  - "musicstreamer/aa_import.py::fetch_channels_multi stream-emission loop (post-47-06)"
provides:
  - "_CODEC_MAP module-scope constant with ground-truth paid-AA codec tiers"
  - "fetch_channels_multi emits codec values hi=MP3, med=AAC, low=AAC (corrected)"
affects:
  - "musicstreamer/aa_import.py::fetch_channels_multi (codec line only)"
tech-stack:
  added: []
  patterns:
    - "Lookup-table-over-ternary — _CODEC_MAP colocated with _POSITION_MAP + _BITRATE_MAP at module scope"
key-files:
  created: []
  modified:
    - musicstreamer/aa_import.py
    - tests/test_aa_import.py
decisions:
  - "Static module-scope _CODEC_MAP (vs. metadata-driven codec inference from AA content_type) — ground truth is stable across all paid AA networks; metadata introspection deferred as future enhancement"
  - "No update to fetch_channels (single-quality legacy path) — verified that path does not set codec on result dicts, so no ternary to replace"
  - "No update to pre-existing tests — none asserted codec on fetch_channels_multi output; seed-data codec literals in test_import_multi_* are arbitrary input for import_stations_multi and semantically unaffected"
metrics:
  duration_seconds: 90
  tasks_completed: 2
  tests_added: 1
  tests_updated: 0
  files_modified: 2
  completed: 2026-04-18
---

# Phase 47 Plan 07: AudioAddict Codec Mapping Ground-Truth Correction (UAT Gap 3) Summary

Corrected inverted AudioAddict paid-tier codec labels. Introduced module-scope `_CODEC_MAP = {"hi": "MP3", "med": "AAC", "low": "AAC"}` colocated with the existing `_POSITION_MAP` and `_BITRATE_MAP`, and replaced the inline `"AAC" if tier == "premium_high" else "MP3"` ternary with an `_CODEC_MAP[quality]` lookup.

## Root cause

UAT gap 3 (severity: major). The codec assignment in `fetch_channels_multi` used the inline ternary:

```python
"codec": "AAC" if tier == "premium_high" else "MP3",
```

This produced the inverted mapping `hi=AAC, med=MP3, low=MP3` — all three tiers labeled wrong. Ground truth, verified against the AudioAddict hardware-player settings UI and consistent across all paid AA networks (DI.fm, RadioTunes, JazzRadio, RockRadio, ClassicalRadio, ZenRadio):

| Tier | Ground truth codec | Bitrate (already correct) |
|------|--------------------|-----------------------------|
| hi   | MP3                | 320                          |
| med  | AAC                | 128                          |
| low  | AAC                | 64                           |

Impact: the Edit Station dialog's Codec column displayed wrong labels for every paid-AA import since Phase 47 landed, misleading users and introducing a subtle bug in the failover sort's `codec_rank` tiebreaker at equal bitrate edges.

## Fix

### `_CODEC_MAP` module-scope constant (musicstreamer/aa_import.py:106-110)

Added alongside the existing tier-metadata tables:

```python
_POSITION_MAP = {"hi": 1, "med": 2, "low": 3}
_BITRATE_MAP = {"hi": 320, "med": 128, "low": 64}  # D-10: DI.fm tier -> kbps
# gap-07: ground-truth paid-AA codec mapping (user-verified from AA hardware-player
# settings UI — consistent across all paid AA networks): hi=MP3, med=AAC, low=AAC.
# Supersedes the previous inline 'AAC' if tier == 'premium_high' else 'MP3' ternary
# which produced the inverted mapping hi=AAC, med=MP3, low=MP3.
_CODEC_MAP = {"hi": "MP3", "med": "AAC", "low": "AAC"}
```

### Stream-emission loop (musicstreamer/aa_import.py:196)

```python
"codec": _CODEC_MAP[quality],
```

replaced

```python
"codec": "AAC" if tier == "premium_high" else "MP3",
```

No other sites required update:
- The legacy `fetch_channels` (single-quality path, line ~119) does **not** set a codec field on its result dicts — re-verified by reading the function body.
- `tier` continues to flow through the AA URL template (`premium_high` / `premium` / `premium_medium`); tier semantics are unchanged.

### Bitrate unchanged

`_BITRATE_MAP = {"hi": 320, "med": 128, "low": 64}` stays — the bitrate half of UAT gap 3 was already correct.

## Tests

### New regression test

| Test | What it asserts |
|------|-----------------|
| `test_fetch_channels_multi_codec_map_ground_truth` | For every channel in `fetch_channels_multi` output, `{quality: codec}` dict equals ground truth: `hi=MP3, med=AAC, low=AAC`. Uses `_resolve_pls` patch returning `["http://mock"]` (post-47-06 list signature). |

### Pre-existing tests updated

**None.** Scanned every `codec` reference in `tests/test_aa_import.py`:
- Lines 426-428, 446, 464, 468, 512-514 — all seed-data for `import_stations_multi` / `import_stations` tests; arbitrary input dicts, not assertions on `fetch_channels_multi` output.
- Tests that exercise `fetch_channels_multi` (`test_fetch_channels_multi_returns_streams`, `test_fetch_channels_multi_stream_has_quality`, `test_fetch_channels_multi_positions`, `test_fetch_channels_multi_bitrate_kbps`, `test_fetch_channels_multi_preserves_primary_and_fallback`) never asserted on `codec` values.

Leaving seed literals as-is matches the plan's explicit instruction ("any test that seeds its OWN channel dicts does NOT need updating — its seed data is arbitrary input").

### Result

- `pytest tests/test_aa_import.py` — 30 passed (29 pre-existing + 1 new)
- `pytest tests/test_aa_import.py tests/test_repo.py tests/test_stream_ordering.py` — 102 passed (logically-related suites)

## TDD Gate Compliance

| Gate   | Commit  | Verified |
|--------|---------|----------|
| RED    | 2ddcd9b | `test(47-07): add failing regression for ground-truth AA codec mapping` — new test created, FAILED against old ternary (asserts MP3, got AAC for hi tier). All 29 pre-existing tests still passed (deselect check). |
| GREEN  | 8196a34 | `fix(47-07): correct paid-AA codec mapping to ground truth (hi=MP3, med=AAC, low=AAC)` — `_CODEC_MAP` added, ternary replaced; 30/30 AA tests green. |
| REFACTOR | — | Not needed; GREEN implementation is already minimal (one const + one lookup). |

## Commits

| # | Hash     | Type | Message |
|---|----------|------|---------|
| 1 | 2ddcd9b  | test | add failing regression for ground-truth AA codec mapping |
| 2 | 8196a34  | fix  | correct paid-AA codec mapping to ground truth (hi=MP3, med=AAC, low=AAC) |

## Deviations from Plan

None — plan executed exactly as written. The plan anticipated possibly needing to update pre-existing tests that assert codec values on `fetch_channels_multi` output, but a careful scan confirmed no such assertions existed.

## Deferred (out of scope)

1. **Metadata-driven codec inference.** A future enhancement could read codec from AA stream metadata (`content_type` response header) and fall back to the corrected tier map. Paid-tier static mapping is user-verified as ground truth across all paid AA networks, so this is nice-to-have, not gap-closing.
2. **Pre-existing collection errors.** 6 test files fail collection with `ModuleNotFoundError` (gi, yt_dlp, pytest-qt fixtures) and 25 unrelated tests fail with module-loading issues. Documented in `deferred-items.md` from plan 47-01. Not touched.

## Verification

- [x] `_CODEC_MAP = {"hi": "MP3", "med": "AAC", "low": "AAC"}` defined at module scope alongside `_POSITION_MAP` and `_BITRATE_MAP` (3 parallel lines at musicstreamer/aa_import.py:104-110)
- [x] Every site that set codec per tier uses `_CODEC_MAP[quality]` lookup
- [x] Inverted ternary `"AAC" if tier == "premium_high" else "MP3"` completely removed (grep returns 0 matches)
- [x] Ground-truth regression test passes
- [x] All 30 `tests/test_aa_import.py` tests pass
- [x] 102 passed across aa_import + repo + stream_ordering
- [x] `_BITRATE_MAP` unchanged
- [x] UAT gap 3 closed (codec half); bitrate half was already correct

## File-conflict note with plan 47-06

47-06 landed first (its changes are in the base commit for this worktree). 47-07 touches only:
- Line 106-110: new `_CODEC_MAP` constant (immediately after `_BITRATE_MAP`, new lines)
- Line 196: codec assignment inside the 47-06 rewritten stream-emission loop (`enumerate(stream_urls)` iterator)

Edits cleanly overlay 47-06 with no textual conflict — the codec line is a single-line replacement inside 47-06's loop body.

## Self-Check: PASSED

- FOUND: musicstreamer/aa_import.py (modified)
- FOUND: tests/test_aa_import.py (modified)
- FOUND: commit 2ddcd9b (RED — test(47-07))
- FOUND: commit 8196a34 (GREEN — fix(47-07))
- `_CODEC_MAP = {"hi": "MP3", "med": "AAC", "low": "AAC"}`: present (1 match at line 110)
- `_CODEC_MAP[quality]`: present (1 match at line 196)
- old ternary `"AAC" if tier == "premium_high" else "MP3"`: 0 matches (fully removed)
- UAT gap 3 closed (codec half).
