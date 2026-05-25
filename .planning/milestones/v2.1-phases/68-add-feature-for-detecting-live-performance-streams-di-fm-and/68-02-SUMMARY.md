---
phase: 68
plan: "02"
subsystem: aa_live
tags: [pure-helper, no-qt, urllib, datetime-iso8601, regex, html-no-injection]
dependency_graph:
  requires: [68-01]
  provides: [musicstreamer/aa_live.py]
  affects: [musicstreamer/url_helpers.py]
tech_stack:
  added: []
  patterns:
    - urllib.request.urlopen for AA events HTTP GET (mirrors aa_import.py)
    - datetime.fromisoformat with timezone.utc for ISO 8601 comparison
    - re.compile with IGNORECASE for ICY prefix matching
    - keyword-only `now` parameter for deterministic test injection
key_files:
  created:
    - musicstreamer/aa_live.py
  modified: []
decisions:
  - "fetch_live_map() wraps _parse_live_map() for separation of network I/O and parsing"
  - "A-04 silent failure: all exceptions return {} without logging to avoid poll-cycle noise"
  - "detect_live_from_icy() accepts Optional[str] and short-circuits on falsy input"
  - "get_di_channel_key() uses getattr defensively for stations without a streams attribute"
  - "_parse_live_map() defaults now=datetime.now(timezone.utc) to avoid naive/aware comparison TypeError (Pitfall 2)"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-10"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
---

# Phase 68 Plan 02: aa_live Pure Helpers Summary

**One-liner:** Pure-Python `musicstreamer/aa_live.py` implementing AudioAddict events fetcher, ICY-title prefix matcher, and DI.fm channel key derivation — zero Qt coupling, all 4 functions per plan spec.

## What Was Built

Created `musicstreamer/aa_live.py` (149 lines) as a new pure-Python module with four functions:

1. **`fetch_live_map(network_slug="di") -> dict[str, str]`** — HTTP GET against `https://api.audioaddict.com/v1/{slug}/events` with `timeout=15`, silent `{}` return on any failure (A-04). Calls `_parse_live_map(data)` and guards `isinstance(data, list)` before parsing.

2. **`_parse_live_map(events, *, now=None) -> dict[str, str]`** — Pure parser with a deterministic `now=` keyword-only argument for test injection. Parses ISO 8601 timestamps via `datetime.fromisoformat`, skips malformed dates silently (Pitfall 2), and collects `{channel_key: show_name}` for events where `start_at <= now < end_at`.

3. **`detect_live_from_icy(title) -> str | None`** — Compiles `_LIVE_ICY_RE = re.compile(r'^\s*LIVE\s*[:\-]\s*(.+?)\s*$', re.IGNORECASE)` at module level (P-01 prefix match, P-02 substring rejection, P-03 stateless). Returns captured group stripped, or None.

4. **`get_di_channel_key(station) -> str | None`** — Reads `station.streams[0].url`, calls `_is_aa_url`, `_aa_slug_from_url`, and returns a channel key only when slug == 'di' (D-02 v1 scope) via `_aa_channel_key_from_url(url, slug="di")`.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create musicstreamer/aa_live.py | 39a4b7c | musicstreamer/aa_live.py (new, 149 lines) |

## Verification

- `grep -c "from PySide6\|import PySide6\|from PyQt" musicstreamer/aa_live.py` → **0** (no Qt coupling)
- `grep -c "^from musicstreamer.url_helpers import" musicstreamer/aa_live.py` → **1** (single canonical import block)
- Regression: `pytest tests/test_aa_siblings.py tests/test_aa_url_detection.py` → **58 passed** (url_helpers unchanged)
- Smoke tests: `detect_live_from_icy`, `_parse_live_map` (in-window, out-of-window), module import — all passed
- File line count: 149 lines (min_lines: 80 — satisfied)
- `git diff --diff-filter=D --name-only HEAD~1 HEAD` → no accidental deletions

**Note:** `tests/test_aa_live.py` is authored by Plan 01 (parallel worktree). Tests could not be run in isolation because Plan 01's test file and fixtures are not yet merged into this worktree at execution time. The orchestrator will verify all 20 tests pass GREEN after wave merge.

## Deviations from Plan

None — plan executed exactly as written. The `<behavior>` section provided verbatim implementation; the module was written to match exactly.

## Known Stubs

None. The module contains no placeholder values, hardcoded empty returns for production paths, or TODO markers. All functions implement their full specified behavior.

## Threat Flags

No new threat surface introduced. `musicstreamer/aa_live.py` has:
- No network endpoints exposed (it's a client-side HTTP caller only)
- No HTML rendering — all strings are returned as plain Python `str` values for callers to display via `Qt.PlainText` labels
- No SQL or file-system access
- Channel keys used only as `dict` keys — no interpolation

## Self-Check: PASSED

- [x] `musicstreamer/aa_live.py` exists at correct path
- [x] Commit `39a4b7c` verified: `git log --oneline --all | grep 39a4b7c`
- [x] Function signatures match acceptance criteria exactly
- [x] Zero Qt imports confirmed
- [x] url_helpers.py unmodified (no diff against HEAD)
