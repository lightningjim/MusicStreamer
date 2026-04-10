---
phase: 32-add-twitch-authentication-via-streamlink-oauth-token
plan: "01"
subsystem: player/constants
tags: [twitch, auth, streamlink, tdd]
dependency_graph:
  requires: []
  provides: [TWITCH_TOKEN_PATH, clear_twitch_token, twitch-api-header-injection]
  affects: [musicstreamer/constants.py, musicstreamer/player.py]
tech_stack:
  added: []
  patterns: [token-file-read, OSError-guard, list-arg-injection]
key_files:
  created:
    - tests/test_twitch_auth.py
  modified:
    - musicstreamer/constants.py
    - musicstreamer/player.py
decisions:
  - "Token read with open().read().strip() inside OSError guard — no shell=True, no splitting, no logging of token value (T-32-02 mitigated)"
  - "TWITCH_TOKEN_PATH mirrors COOKIES_PATH pattern in constants.py for consistency"
metrics:
  duration_minutes: 1
  completed_date: "2026-04-10"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 3
requirements:
  - TAUTH-01
  - TAUTH-02
  - TAUTH-03
---

# Phase 32 Plan 01: Twitch Auth Token Constants and _play_twitch() Injection Summary

**One-liner:** TWITCH_TOKEN_PATH constant + clear_twitch_token() utility + --twitch-api-header OAuth injection in _play_twitch(), all TDD with 6 unit tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | TDD — TWITCH_TOKEN_PATH, clear_twitch_token(), _play_twitch() auth header | 5714fa0 | musicstreamer/constants.py, musicstreamer/player.py, tests/test_twitch_auth.py |

## Decisions Made

- Token read via `open(TWITCH_TOKEN_PATH).read().strip()` inside `except OSError` — safe list-arg injection, no shell=True, token value never logged (mitigates T-32-02).
- `TWITCH_TOKEN_PATH` placed after `COOKIES_PATH` in constants.py, `clear_twitch_token()` placed after `clear_cookies()` — mirrors existing pattern exactly.
- Thread patched synchronously in tests via `lambda target, daemon: type('T', (), {'start': lambda self: target()})()` — same approach as existing test_twitch_playback.py but via monkeypatch for cleaner isolation.

## Verification

- `pytest tests/test_twitch_auth.py -x` — 6 passed
- `pytest tests/ -x` — 261 passed (no regressions)
- `grep TWITCH_TOKEN_PATH musicstreamer/constants.py` — present
- `grep clear_twitch_token musicstreamer/constants.py` — present
- `grep twitch-api-header musicstreamer/player.py` — present
- `grep TWITCH_TOKEN_PATH musicstreamer/player.py` — present

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints or trust boundaries beyond what the plan's threat model already registers (T-32-01 through T-32-03 addressed; T-32-01 file permissions are Plan 02's responsibility as documented).

## Self-Check: PASSED

- musicstreamer/constants.py — FOUND, contains TWITCH_TOKEN_PATH and clear_twitch_token
- musicstreamer/player.py — FOUND, contains twitch-api-header injection
- tests/test_twitch_auth.py — FOUND, 6 tests
- Commit 5714fa0 — FOUND
