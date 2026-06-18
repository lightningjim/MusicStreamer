---
phase: 87B-gbs-zero-token-single-song-add
plan: "01"
subsystem: gbs-api
tags: [gbs, add-song, zero-token, drift-guard, fixtures, no-pii]
dependency_graph:
  requires: []
  provides:
    - gbs_api.add_song_zero_token()
    - gbs_api._capture_add_shape()
    - tests/fixtures/gbs_zero_token/ (provisional fixture directory)
    - tests/test_gbs_zero_token_drift_guard.py
  affects:
    - musicstreamer/gbs_api.py
    - tests/test_gbs_api.py
tech_stack:
  added: []
  patterns:
    - thin-wrapper over existing submit() — no HTTP duplication
    - no-PII structured WARN capture hook (T-87B-01 enforced)
    - source-grep drift-guard (comment-strip + regex function-body extraction)
    - provisional fixture + capture-on-use placeholder (Phase 87 D-04 pattern)
key_files:
  created:
    - tests/fixtures/gbs_zero_token/add_redirect_response_48tokens.txt
    - tests/fixtures/gbs_zero_token/add_redirect_zero_token_PLACEHOLDER.txt
    - tests/fixtures/gbs_zero_token/MANIFEST.md
    - tests/test_gbs_zero_token_drift_guard.py
  modified:
    - musicstreamer/gbs_api.py
    - tests/test_gbs_api.py
decisions:
  - "Docstrings for add_song_zero_token()/_capture_add_shape() written as # comments (not triple-quoted strings) to avoid bare 'token' word in string literals — the drift-guard regex matches triple-quoted docstring content through the surrounding quote chars"
  - "GBS-TOKEN-02 drift-guard: after _strip_comments(), # comment lines become empty, leaving only executable code for the banned-pattern scan"
metrics:
  duration: "~20 min"
  completed_date: "2026-06-18"
  tasks_completed: 3
  files_changed: 6
---

# Phase 87B Plan 01: GBS Zero-Token Add — Backend + Drift-Guard Summary

**One-liner:** `add_song_zero_token()` thin wrapper over `submit()` with no-PII capture hook, source-grep drift-guard, and provisional fixture directory for the zero-token `/add/<songid>` contract.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Provisional fixtures + GBS-TOKEN-02 drift-guard (RED) | 603ceb62 | tests/fixtures/gbs_zero_token/ (3 files), tests/test_gbs_zero_token_drift_guard.py |
| 2 | add_song_zero_token() wrapper + _capture_add_shape() hook (GREEN) | ab473c6a | musicstreamer/gbs_api.py |
| 3 | Unit tests — submit reuse, auth-expiry, PII-free, fixture-exists | d51a6878 | tests/test_gbs_api.py |

## What Was Built

### `musicstreamer/gbs_api.py`

Two new functions inserted immediately after `submit()` (line 1153):

- **`add_song_zero_token(songid, cookies) -> str`**: Calls `submit(songid, cookies)`, then `_capture_add_shape()`, returns result. No HTTP logic duplicated — `_open_no_redirect`, `_decode_django_messages`, `GBS_BASE`, `_TIMEOUT_WRITE` are absent from its body.
- **`_capture_add_shape(songid, message) -> None`**: Emits one `_log.warning(...)` with `endpoint=/add/%s`, `message_len`, and `message_category` (empty/error/success). No cookies, sessionid, csrftoken, Set-Cookie, or Authorization values logged.

Module docstring public-API list updated to include `add_song_zero_token`.

### `tests/fixtures/gbs_zero_token/`

Three files:
- `add_redirect_response_48tokens.txt` — verbatim copy of `tests/fixtures/gbs/add_redirect_response.txt` (HTTP/2 302 + `set-cookie: messages=...` line). Fixture-locks the observable `/add` shape at 48 tokens per GBS-TOKEN-05.
- `add_redirect_zero_token_PLACEHOLDER.txt` — comment-only placeholder reserved for first-live-use capture.
- `MANIFEST.md` — fixture provenance table with 48-token row (real-captured) and PLACEHOLDER row (pending-capture + `resolves_phase: 87B`).

### `tests/test_gbs_zero_token_drift_guard.py`

GBS-TOKEN-02 source-grep drift-guard cloned from `tests/test_gbs_marquee_drift_guard.py`. Extracts `add_song_zero_token` function body via regex from comment-stripped source, asserts no `\btoken\b` word boundary match in any string literal. Also serves as the GBS-TOKEN-03 existence guard.

### `tests/test_gbs_api.py`

Four new tests (all green):
- `test_add_song_zero_token_calls_submit` — proves wrapper routes through `submit()`'s decode path
- `test_add_song_zero_token_raises_auth_expired` — proves `GbsAuthExpiredError` propagates unchanged
- `test_capture_hook_no_pii` (**T-87B-01**) — verifies no sessionid/csrftoken/Set-Cookie/Authorization in log calls
- `test_zero_token_fixture_exists` — provisional fixture present and non-empty (GBS-TOKEN-05)

## Verification

```
.venv/bin/python -m pytest tests/test_gbs_api.py tests/test_gbs_zero_token_drift_guard.py -x
# 63 passed, 1 warning
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Triple-quoted docstrings matched the GBS-TOKEN-02 drift-guard regex**

- **Found during:** Task 2 (GREEN phase) — drift-guard still RED after function was created
- **Issue:** The drift-guard regex `"[^"]*\btoken\b[^"]*"` matches across lines through a triple-quoted docstring because `[^"]*` consumes newlines and the word "TOKEN" in "GBS-TOKEN-03" within the docstring was a match. The PATTERNS.md noted this risk but the provided example docstring still contained "TOKEN" in "GBS-TOKEN-03".
- **Fix:** Rewrote both `add_song_zero_token()` and `_capture_add_shape()` docstrings as `#` comment lines (not triple-quoted strings). After `_strip_comments()`, the comment lines become empty, leaving no string literals for the drift-guard to scan.
- **Files modified:** musicstreamer/gbs_api.py
- **Commit:** ab473c6a (same task commit — corrected before committing)

## Known Stubs

None — the provisional fixture is intentional and documented in MANIFEST.md with `resolves_phase: 87B`.

## Threat Flags

No new threat surface beyond the plan's registered threats. T-87B-01 mitigated and unit-test-enforced via `test_capture_hook_no_pii`.

## Self-Check: PASSED
