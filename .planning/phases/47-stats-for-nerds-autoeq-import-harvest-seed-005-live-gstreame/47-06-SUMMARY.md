---
phase: 47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame
plan: 06
subsystem: audioaddict-import
type: gap_closure
tags: [audioaddict, pls, failover, bitrate-ordering, uat-gap-2]
gap_closure: true
closes_uat_gaps: [2]
depends_on: []
depends_on_info: "shares musicstreamer/aa_import.py with plan 47-07 — this plan landed first; disjoint line ranges so 47-07 rebases cleanly"
requires: []
provides:
  - "_resolve_pls returning list[str] (all FileN= entries in PLS order)"
  - "fetch_channels_multi emitting one stream dict per PLS server entry (2x per tier for AA premium)"
  - "Widened position scheme: tier_base * 10 + pls_index (hi-primary=11, hi-fallback=12, ..., low-fallback=32)"
affects:
  - "musicstreamer/aa_import.py::_resolve_pls (signature changed str -> list[str])"
  - "musicstreamer/aa_import.py::fetch_channels (updated to take urls[0] for back-compat)"
  - "musicstreamer/aa_import.py::fetch_channels_multi (stream emission widened)"
tech-stack:
  added: []
  patterns:
    - "re.match(r'^File(\\d+)=(.+)$') scan preserves File-number order (handles non-contiguous N)"
    - "list-form fallback-on-error [pls_url] keeps legacy callers working via [0]"
key-files:
  created: []
  modified:
    - musicstreamer/aa_import.py
    - tests/test_aa_import.py
decisions:
  - "Return list from _resolve_pls rather than adding a new _resolve_pls_all — legacy fetch_channels adapts trivially via [0]; avoids API surface duplication"
  - "Position scheme tier_base * 10 + pls_index (vs. sparser base * 100) — 10 is enough for AA (max 2 servers per tier) and stays within small-int range"
  - "Preserve codec line 'AAC if tier == premium_high else MP3' as-is — the codec bug (UAT gap 3) is fixed independently by plan 47-07 on disjoint lines"
metrics:
  duration_seconds: 260
  tasks_completed: 2
  tests_added: 3
  tests_updated: 3
  files_modified: 2
  completed: 2026-04-18
---

# Phase 47 Plan 06: Stream Bitrate Quality Ordering (Gap Closure — UAT Gap 2) Summary

AudioAddict PLS files contain 2 server entries per tier (primary + fallback); `_resolve_pls` dropped the fallback silently. Rewrote the helper to return `list[str]`, widened `fetch_channels_multi` to emit one stream dict per URL with a `tier_base * 10 + pls_index` position scheme, and kept the legacy `fetch_channels` API stable via `urls[0]`.

## Root cause

UAT gap 2 (severity: major). The original implementation at `musicstreamer/aa_import.py:23-35` parsed PLS bodies looking only for the `File1=` line and returned it as a single string. AA premium PLS files always contain two entries:

```
[playlist]
numberofentries=2
File1=http://primary.server.com:8000/listen
File2=http://fallback.server.com:8000/listen
```

`File2=` was never emitted, so within-tier failover redundancy (the whole point of Phase 47's bitrate-ordering feature) had nothing to fall back to when the primary hi-quality server dropped. Phase 47-01's `order_streams` would promote primary-hi to position 1 and then degrade straight to primary-med, skipping the healthy fallback-hi server entirely.

## Fix

### `_resolve_pls` (musicstreamer/aa_import.py:23-47)

Now returns `list[str]` with all `FileN=` entries in file order:

```python
def _resolve_pls(pls_url: str) -> list[str]:
    try:
        with urllib.request.urlopen(pls_url, timeout=10) as resp:
            body = resp.read().decode()
        entries = []
        for line in body.splitlines():
            m = re.match(r"^File(\d+)=(.+)$", line.strip())
            if m:
                entries.append((int(m.group(1)), m.group(2).strip()))
        if not entries:
            return [pls_url]
        entries.sort(key=lambda t: t[0])
        return [url for _, url in entries]
    except Exception:
        pass
    return [pls_url]
```

Sorting by the file index tolerates non-contiguous numbering (rare but legal per PLS spec); for AA — always contiguous 1,2 — it reduces to file order.

### `fetch_channels` (legacy, line ~119)

Single-quality path takes the first URL for back-compat:

```python
urls = _resolve_pls(pls_url)  # gap-06: list, not str
stream_url = urls[0] if urls else pls_url
```

### `fetch_channels_multi` (line ~157-180)

Iterates the list and emits one stream dict per URL. New position scheme widens the old tier-ordinal `{hi:1, med:2, low:3}` to `tier_base * 10 + pls_index`:

| Tier | Primary pos | Fallback pos |
|------|-------------|--------------|
| hi   | 11          | 12           |
| med  | 21          | 22           |
| low  | 31          | 32           |

This preserves tier-then-PLS-order and never collides with legacy rows whose positions are all ≤ 3. Phase 47-01's `order_streams` uses `position asc` only as a tiebreaker within the same `(codec_rank, bitrate_kbps)` bucket — because primary and fallback in a tier share codec + bitrate, position cleanly orders primary before fallback.

## Tests

### New regression tests (RED commit 467f86d, pass after GREEN commit b725488)

| Test | What it asserts |
|------|-----------------|
| `test_resolve_pls_returns_all_entries` | PLS with `File1=` + `File2=` returns both URLs as a list in file order |
| `test_resolve_pls_single_entry` | PLS with only `File1=` returns a one-element list |
| `test_fetch_channels_multi_preserves_primary_and_fallback` | For a 3-tier AA channel with 2-server PLS per tier, `fetch_channels_multi` emits 6 streams; each tier has 2 entries sharing codec + bitrate with distinct URLs; primary position < fallback position within every tier |

### Pre-existing tests updated

| Test | Change |
|------|--------|
| `test_resolve_pls` | Asserted single string; now asserts list of all File= URLs |
| `test_resolve_pls_fallback_on_error` | Asserted `pls_url` string; now asserts `[pls_url]` list-form |
| `test_fetch_channels_multi_positions` | Asserted `{hi:1, med:2, low:3}`; now asserts `{hi:11, med:21, low:31}` (single-entry mock → pls_index=1) with uniqueness invariant |
| 9 `_resolve_pls` mock side_effects | `lambda url: url` → `lambda url: [url]` to match new list signature |

### Result

- `pytest tests/test_aa_import.py` — 29 passed (26 pre-existing + 3 new)
- `pytest tests/test_aa_import.py tests/test_repo.py tests/test_stream_ordering.py` — 101 passed

## TDD Gate Compliance

| Gate   | Commit  | Verified |
|--------|---------|----------|
| RED    | 467f86d | `test(47-06): add failing regressions for AA PLS primary + fallback extraction` — 3 new tests created, all failed against old implementation (verified) |
| GREEN  | b725488 | `fix(47-06): _resolve_pls returns all File= entries; fetch_channels_multi emits per-URL streams` — all 3 new tests + all pre-existing AA tests pass |
| REFACTOR | — | Not needed; GREEN implementation is already minimal |

## Commits

| # | Hash     | Type | Message |
|---|----------|------|---------|
| 1 | 467f86d  | test | add failing regressions for AA PLS primary + fallback extraction |
| 2 | b725488  | fix  | _resolve_pls returns all File= entries; fetch_channels_multi emits per-URL streams |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Updated 9 pre-existing `_resolve_pls` mock side_effects**
- **Found during:** Task 2 (GREEN verification)
- **Issue:** After `_resolve_pls` signature change from `str` to `list[str]`, every pre-existing test that mocked `_resolve_pls` with `side_effect=lambda url: url` broke — callers now take `[0]` or iterate, yielding the first character of the URL or a character sequence.
- **Fix:** Bulk replace `lambda url: url` → `lambda url: [url]` across 9 call sites in `tests/test_aa_import.py`.
- **Files modified:** tests/test_aa_import.py
- **Commit:** b725488

**2. [Rule 3 — Blocking] Updated `test_resolve_pls` + `test_resolve_pls_fallback_on_error` assertions**
- **Found during:** Task 2
- **Issue:** Both tests asserted string equality against `_resolve_pls` return; new signature returns list.
- **Fix:** Updated assertions to list form; added "gap-06" comment marker.
- **Files modified:** tests/test_aa_import.py
- **Commit:** b725488

**3. [Planned deviation — documented in plan] Updated `test_fetch_channels_multi_positions`**
- **Found during:** Task 2 (the plan explicitly flagged this)
- **Issue:** Hardcoded `{hi:1, med:2, low:3}` is no longer produced by the new scheme.
- **Fix:** Updated to `{hi:11, med:21, low:31}` (single-entry mock ⇒ pls_index=1) and added a uniqueness invariant assertion so the test stays meaningful if the scheme changes again.
- **Files modified:** tests/test_aa_import.py
- **Commit:** b725488

**4. [Rule 3 — Blocking] Fixed PLS URL detection in new integration test**
- **Found during:** Task 1 (initial RED run of `test_fetch_channels_multi_preserves_primary_and_fallback`)
- **Issue:** Initial mock used `url.endswith(".pls")` to route PLS responses, but the actual PLS URLs have `?listen_key=…` appended, so they never match. The mock returned channel JSON for PLS requests, silently falling through and producing only 3 streams (primary only, because `_resolve_pls` took first-char of the fake JSON).
- **Fix:** Changed detection to `".pls?" in url or url.endswith(".pls")` to handle both forms.
- **Files modified:** tests/test_aa_import.py
- **Commit:** 467f86d (initial RED) + survives into b725488 unchanged

### Deferred (out of scope)

Pre-existing environment collection errors (missing `gi` module, missing `qtbot` fixture from pytest-qt) were present before this plan began. They are already documented in `.planning/phases/47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame/deferred-items.md` from plan 47-01. Not touched.

## File-conflict note with plan 47-07

Both plans modify `musicstreamer/aa_import.py`. This plan lands first. The edits are on disjoint line ranges:

- **47-06 (this):** `_resolve_pls` body (lines 23-47 post-edit), `fetch_channels` line ~119 (`urls[0]` adaptation), `fetch_channels_multi` stream-emission loop (lines ~157-180)
- **47-07 (next):** codec/bitrate MAP constants at module scope (lines 93-94) and/or the `codec=` line in the stream-emission loop

If 47-07 edits the `codec=` line inside the loop that this plan rewrote, it will need to rebase onto this commit — the loop body is different (now iterates `enumerate(stream_urls)`) but the `codec=` expression sits on the same logical line inside each appended dict. Merge conflict is textual but trivial.

## Verification

- [x] `_resolve_pls` returns `list[str]` with all `FileN=` entries in PLS order (or `[pls_url]` on failure)
- [x] `fetch_channels_multi` emits one stream dict per PLS entry; primary and fallback share quality/codec/bitrate within a tier; positions preserve PLS order
- [x] Legacy `fetch_channels` still returns one URL per channel
- [x] 3-tier AA station with 2-server PLS files imports 6 streams; each tier has 2 streams; primary position < fallback position (asserted by new test)
- [x] Failover queue (Phase 47-01 `order_streams`) will naturally try primary before fallback within the same tier (same codec + bitrate → position tiebreaker)
- [x] All 29 tests in `tests/test_aa_import.py` pass
- [x] 101 passed across aa_import + repo + stream_ordering (logically-related suites)

## Self-Check: PASSED

- FOUND: musicstreamer/aa_import.py (modified)
- FOUND: tests/test_aa_import.py (modified)
- FOUND: commit 467f86d (RED — test(47-06))
- FOUND: commit b725488 (GREEN — fix(47-06))
- signature `def _resolve_pls(pls_url: str) -> list[str]`: present (1 match)
- `tier_base * 10 + pls_index`: present (code + comment — 2 matches)
- `for pls_index, url in enumerate(stream_urls`: present (1 match)
- legacy back-compat `urls[0]`: present (1 match)
- UAT gap 2 closed.
