---
phase: 58-pls-auto-resolve-in-station-editor
plan: "02"
subsystem: aa-import
tags: [refactor, aa-import, playlist, pls, python, playlist-parser, delegation]

dependency_graph:
  requires:
    - phase: 58-01
      provides: musicstreamer/playlist_parser.parse_playlist (D-09 pure parser module)
  provides:
    - musicstreamer/aa_import._resolve_pls (thin wrapper around parse_playlist — D-10)
  affects:
    - musicstreamer/ui_qt/edit_station_dialog (Plan 03 worker also calls parse_playlist)

tech_stack:
  added: []
  patterns:
    - Thin-wrapper delegation: _resolve_pls calls parse_playlist, extracts url from each dict
    - Lazy import inside try block (parse_playlist imported inside function to keep side-effects minimal)
    - Decode with errors="replace" per D-17 (latin-1/Win-1252 resilience)
    - _urlopen_factory mock updated with headers.get support for Content-Type extraction

key_files:
  created: []
  modified:
    - musicstreamer/aa_import.py
    - tests/test_aa_import.py

key_decisions:
  - "D-10 (Phase 58): _resolve_pls is now a thin wrapper that delegates to playlist_parser.parse_playlist — single source of truth for PLS parsing"
  - "Lazy import of parse_playlist inside try block: prevents side-effect imports if aa_import is loaded without needing PLS resolution, and keeps existing urlopen mocks working without also patching the parser module"
  - "Decode change: resp.read().decode() -> decode('utf-8', errors='replace') per D-17 to match Plan 03 worker permissive decode policy and handle latin-1/Windows-1252 PLS files in the wild"
  - "Rule 1 fix: _urlopen_factory mock extended with headers mock (headers.get returns content_type string) to support _resolve_pls Content-Type extraction in test environment"

requirements-completed:
  - STR-15

duration: ~12min
completed: "2026-05-01"
---

# Phase 58 Plan 02: AA Import _resolve_pls Delegation Summary

**_resolve_pls refactored from inline re.match PLS parser to thin wrapper around playlist_parser.parse_playlist (D-10), preserving list[str] contract and [pls_url] fallback for both call sites**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-01T00:00:00Z
- **Completed:** 2026-05-01
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments

- Replaced inline `re.match(r"^File(\d+)=...")` regex parsing with delegation to `playlist_parser.parse_playlist` — single source of truth for PLS parsing across the project
- Preserved `list[str]` return contract and `[pls_url]` fallback for both call sites at aa_import.py:135 and aa_import.py:177
- Added 3 new delegation tests locking the parse_playlist wiring, empty-result fallback, and urlopen-exception fallback
- Fixed `_urlopen_factory` test helper to mock `headers.get` correctly for Content-Type extraction

## Refactored Line Range

- **Was:** lines 23-46 (inline `re.match` regex parsing, `decode()` without error handling)
- **Now:** lines 23-47 (thin wrapper calling `parse_playlist`, `decode("utf-8", errors="replace")`)
- The signature `def _resolve_pls(pls_url: str) -> list[str]:` is unchanged

## Lazy vs Eager Import Decision

Used **lazy import** (`from musicstreamer.playlist_parser import parse_playlist` inside the try block). Rationale:

1. Keeps `aa_import` side-effect-free when imported by code that doesn't need PLS resolution
2. Existing `test_aa_import.py` mocks patch `musicstreamer.aa_import.urllib.request.urlopen` — these continue working without also needing to patch the parser module
3. If `playlist_parser` cannot be imported (broken install), the bare `except Exception` catches the `ImportError` and falls through to `[pls_url]` — graceful degradation

## Decode Change Rationale (D-17)

Changed `.decode()` (default UTF-8, raises `UnicodeDecodeError` on malformed bytes) to `.decode("utf-8", errors="replace")`. This:

- Matches the decode policy established in Plan 03's worker and in `playlist_parser._as_text`
- Handles latin-1/Windows-1252 PLS files from third-party AA-compatible streams
- Converts malformed bytes to replacement characters rather than raising an exception (which the bare `except Exception` would catch anyway, but errors="replace" keeps more of the body available for parsing)

## Call Sites Not Modified

Lines 135 and 177 of `aa_import.py` remain exactly as written:

- Line 135: `urls = _resolve_pls(pls_url)  # gap-06: list, not str` / `stream_url = urls[0] if urls else pls_url`
- Line 177: `stream_urls = _resolve_pls(pls_url)  # gap-06: list, not str`

Both depend on `_resolve_pls` returning a non-empty `list[str]` — the `[pls_url]` fallback guarantees this on all failure paths.

## New Tests Added

| Test | What it locks |
|------|---------------|
| `test_resolve_pls_delegates_to_playlist_parser` | `parse_playlist` called once; receives decoded body string, `content_type=` kwarg, `url_hint=pls_url` kwarg; result is `[entry["url"] for entry in entries]` |
| `test_resolve_pls_falls_back_when_parse_playlist_returns_empty` | When `parse_playlist` returns `[]`, `_resolve_pls` returns `[pls_url]` (D-10 fallback) |
| `test_resolve_pls_falls_back_on_urlopen_exception` | When `urlopen` raises `URLError`, `_resolve_pls` returns `[pls_url]` (bare-except backstop) |

All 7 `resolve_pls` tests pass (4 pre-existing + 3 new). Full `test_aa_import.py` suite: 33 passed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Refactor aa_import._resolve_pls into thin wrapper** - `79edc9d` (refactor)
2. **Task 2: Add delegation tests** - `6d944d4` (test)

## Files Created/Modified

- `/home/kcreasey/OneDrive/Projects/MusicStreamer/.claude/worktrees/agent-aea35fecd54ac35bd/musicstreamer/aa_import.py` — `_resolve_pls` refactored to thin wrapper (lines 23-47); `import re` retained (still used elsewhere in file)
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/.claude/worktrees/agent-aea35fecd54ac35bd/tests/test_aa_import.py` — `_urlopen_factory` extended with `headers` mock; 3 new delegation test functions added after line 589

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed _urlopen_factory mock missing headers.get support**

- **Found during:** Task 1 (running existing tests after refactor)
- **Issue:** `_urlopen_factory` returned a MagicMock without a proper `headers.get` method. The refactored `_resolve_pls` calls `resp.headers.get("Content-Type", "")`, but with a plain MagicMock, `.get()` returns another MagicMock (not `""`). For test URLs like `"http://any.pls"` (which parse to empty path), `parse_playlist` dispatches via content-type — it calls `content_type.lower()` which returns another MagicMock, causing dispatch to fail and `parse_playlist` to return `[]`, triggering the fallback.
- **Fix:** Updated `_urlopen_factory(data, content_type="audio/x-scpls")` to mock `headers` with a `get` method that returns a real string. Default `"audio/x-scpls"` matches AA server responses and ensures correct dispatch for the PLS test URL pattern.
- **Files modified:** `tests/test_aa_import.py`
- **Verification:** All 30 pre-existing tests continue to pass; `_urlopen_factory(channel_data)` usage in non-PLS tests unaffected (headers not accessed in those code paths)
- **Committed in:** `79edc9d` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — Bug)
**Impact on plan:** Required for correctness — pre-existing PLS tests with bare-hostname URLs would have silently started falling back instead of resolving after the refactor. Fix is minimal and contained to the helper function.

## Issues Encountered

Pre-existing test failures unrelated to this plan (documented, out of scope):

- `tests/test_media_keys_mpris2.py::test_linux_mpris_backend_constructs` — D-Bus service name already registered in CI environment (flaky environment issue)
- `tests/test_media_keys_smtc.py::test_thumbnail_from_in_memory_stream` — Windows SMTC mock incompatibility (Windows-only feature, not available on Linux)
- `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode` — Pre-existing failure, confirmed present on base commit before any changes

## Known Stubs

None — all wiring is live. `parse_playlist` is the real implementation from Plan 01; `_resolve_pls` calls it with real response body.

## Threat Flags

None — no new security surface beyond what is documented in the plan's threat model. The only change to the trust boundary is using `decode("utf-8", errors="replace")` instead of `decode()`, which is strictly more permissive (not a new attack surface — malformed bytes become replacement chars rather than raising exceptions).

## Next Phase Readiness

- Plan 03 (Add from PLS dialog) can now reference `playlist_parser.parse_playlist` knowing that `aa_import._resolve_pls` has already validated the Plan 01 parser works correctly in the AA import flow
- `_urlopen_factory` in `test_aa_import.py` now has proper headers mock — Test 2's delegation test can assert `content_type` kwarg is passed correctly

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `musicstreamer/aa_import.py` exists | FOUND |
| `tests/test_aa_import.py` exists | FOUND |
| `58-02-SUMMARY.md` exists | FOUND |
| Commit 79edc9d (Task 1) exists | FOUND |
| Commit 6d944d4 (Task 2) exists | FOUND |
| parse_playlist call in aa_import.py | FOUND (line 42) |
| old re.match regex removed | CONFIRMED (grep = 0) |
| return [pls_url] fallback | FOUND (line 47, count = 1) |
| pytest resolve_pls tests | 7 passed |
| pytest test_aa_import.py full | 33 passed |

---
*Phase: 58-pls-auto-resolve-in-station-editor*
*Completed: 2026-05-01*
