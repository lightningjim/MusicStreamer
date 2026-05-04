---
phase: 60-gbs-fm-integration
plan: 02
subsystem: api-client
tags: [gbs-fm, api-client, foundation, urllib, html-parser, tdd, wave1]

# Dependency graph
requires: ["60-01"]
provides:
  - "musicstreamer/gbs_api.py: pure-urllib GBS.FM HTTP client + import orchestrator + HTML/JSON parsers + typed exceptions"
  - "musicstreamer/paths.py: gbs_cookies_path() D-04 ladder #3 LOCKED"
  - "tests/test_gbs_api.py: 18 unit+integration tests covering GBS-01a..e"
  - "tests/test_stream_ordering.py: test_gbs_flac_ordering regression (GBS-01f)"
affects:
  - "60-03-import (consumes import_station + paths.gbs_cookies_path)"
  - "60-04-accounts (consumes _validate_gbs_cookies + load_auth_context + GbsAuthExpiredError)"
  - "60-05-active-playlist (consumes fetch_active_playlist)"
  - "60-06-vote (consumes vote_now_playing)"
  - "60-07-search-submit (consumes search + submit + _decode_django_messages)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Static tier-list approach: GBS.FM stream variants hard-coded (no HTTP needed for fetch_streams)"
    - "FLAC bitrate_kbps=1411 CD-baseline sentinel for stream_ordering.order_streams compatibility"
    - "_open_with_cookies / _open_no_redirect urllib helper pair for auth-gated + redirect-capture flows"
    - "_SongRowParser(HTMLParser) anchoring on /song/X, /add/X, /artist/X hrefs (Pitfall 6 resilience)"
    - "_decode_django_messages: base64url decode + JSON parse with graceful fallback (Pitfall 8)"
    - "TDD RED/GREEN cycle: test_gbs_flac_ordering RED before gbs_api.py existed; GREEN after"

key-files:
  created:
    - "musicstreamer/gbs_api.py"
    - "tests/test_gbs_api.py"
  modified:
    - "musicstreamer/paths.py"
    - "tests/test_stream_ordering.py"

key-decisions:
  - "D-04 ladder #3 LOCKED (cookies-import): gbs_cookies_path() returns <XDG_DATA_HOME>/musicstreamer/gbs-cookies.txt"
  - "FLAC bitrate_kbps=1411 sentinel (not 0): ensures FLAC partitioned as 'known bitrate' by order_streams, sorts FIRST via codec_rank(FLAC)=3 > codec_rank(MP3)=1 (RESEARCH Q1 resolved)"
  - "fetch_streams() is pure (no HTTP): static tier list avoids unnecessary network call since GBS.FM stream URLs are stable"
  - "import_station() idempotent via provider_name='GBS.FM' + stream URL cross-check: preserves station.id across re-import (D-02a)"
  - "_SongRowParser uses HTMLParser (not regex): more robust against whitespace variation in Django-rendered HTML"
  - "test_fetch_playlist_auth_expired raises GbsAuthExpiredError directly (not HTTPError): _open_with_cookies is the conversion layer; mocking it means raising the already-converted exception"

# Metrics
duration: 6min
completed: 2026-05-04
---

# Phase 60 Plan 02: GBS.FM API Client Summary

**Pure-urllib GBS.FM HTTP client with 6-tier static stream variants, FLAC 1411 kbps sentinel, Django session cookie auth, /ajax event-stream parser, HTML search parser, Django messages cookie decoder, typed exceptions, and 18 passing tests**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-04T18:48:35Z
- **Completed:** 2026-05-04T18:54:36Z
- **Tasks:** 2 completed
- **Files modified:** 4 (2 created + 2 modified)

## Accomplishments

- Created `musicstreamer/gbs_api.py` (562 LOC) exposing all 9 public functions + 2 exception classes per D-03:
  - `fetch_streams()`: static 6-tier list (96/128/192/256/320 MP3 + FLAC with bitrate_kbps=1411)
  - `fetch_station_metadata()`: static GBS.FM metadata dict
  - `import_station(repo, on_progress=None)`: idempotent multi-quality import orchestrator
  - `fetch_active_playlist(cookies, cursor=None)`: /ajax event-stream fold → state dict
  - `vote_now_playing(entryid, vote, cookies)`: /ajax?vote=N submit with ValueError guard
  - `search(query, page, cookies)`: /search HTML parse via `_SongRowParser(HTMLParser)`
  - `submit(songid, cookies)`: /add/<songid> redirect intercept + messages cookie decode
  - `load_auth_context()`: MozillaCookieJar from `paths.gbs_cookies_path()` with corruption check
  - `_validate_gbs_cookies(text)`: Netscape format validator for sessionid+csrftoken on gbs.fm
  - `_decode_django_messages(cookie_value)`: base64url + JSON decode with graceful fallback
  - `GbsApiError`, `GbsAuthExpiredError(GbsApiError)` typed exceptions
- Extended `musicstreamer/paths.py` with `gbs_cookies_path()` (D-04 ladder #3 LOCKED)
- Extended `tests/test_stream_ordering.py` with `test_gbs_flac_ordering` regression (GBS-01f)
- Created `tests/test_gbs_api.py` (295 LOC, 18 tests) covering all requirement rows GBS-01a through GBS-01e

## Task Commits

1. **Task 1: Create musicstreamer/gbs_api.py + paths.gbs_cookies_path() + FLAC regression test** - `f606b24` (feat)
2. **Task 2: Create tests/test_gbs_api.py — 18 tests covering GBS-01a..e** - `28e5a8f` (feat)

## Files Created/Modified

- `musicstreamer/gbs_api.py` — pure-urllib GBS.FM API client + import orchestrator + HTML/JSON parsers; 562 LOC; exports all 9 public names + 2 exceptions per plan artifacts spec
- `musicstreamer/paths.py` — `gbs_cookies_path()` one-liner added after `twitch_token_path()` per D-04 ladder #3
- `tests/test_gbs_api.py` — 18 tests across GBS-01a (4 tests), GBS-01b (2), GBS-01c (3), GBS-01d (2), GBS-01e (5), messages-cookie unit test (2); all use monkeypatching (no real HTTP)
- `tests/test_stream_ordering.py` — `test_gbs_flac_ordering` appended at bottom; FLAC sorts first among known-bitrate GBS streams via codec_rank=3 > 1

## Decisions Made

- **FLAC bitrate_kbps=1411**: CD-baseline sentinel chosen per RESEARCH Q1. codec_rank(FLAC)=3 is the primary differentiator, but bitrate_kbps must be >0 to avoid the unknown-bitrate-LAST partition in `order_streams`. 1411 kbps is the standard lossless baseline; consistent with what real FLAC decoders report for CD audio.
- **`_open_with_cookies` as conversion layer**: Typed `GbsAuthExpiredError` wraps the HTTPError inside the helper, so callers never see raw urllib errors for the auth-expired case. Tests that monkeypatch the helper raise the converted exception directly.
- **No `list[dict]` type hints on `fetch_streams()`/`import_station()` return types**: Used `list` and `tuple` (without subscript) for Python 3.8 compatibility consistency with rest of codebase.
- **`_SongRowParser` third-td heuristic for duration**: The GBS.FM search HTML places duration in column 3 (artistry, title, duration, uploader, votes, score, ...). Heuristic is recorded in code comment.

## TDD Gate Compliance

- **RED gate**: `test_gbs_flac_ordering` ran RED with `ModuleNotFoundError: No module named 'musicstreamer.gbs_api'` before gbs_api.py was created. Confirmed via pytest run.
- **RED gate (Task 2)**: `tests/test_gbs_api.py` did not exist before Task 2 was written — all tests would have failed. File created, then all 18 passed immediately (GREEN).
- **GREEN gate**: 18 tests passed after implementation. FLAC regression test passed after gbs_api.py creation.
- No REFACTOR gate commits needed — code was clean on first pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_fetch_playlist_auth_expired raised urllib.error.HTTPError instead of GbsAuthExpiredError**

- **Found during:** Task 2 GREEN phase
- **Issue:** The test monkeypatched `_open_with_cookies` (the conversion layer) to raise `urllib.error.HTTPError`. But since `_open_with_cookies` IS the conversion layer, replacing it means the HTTPError was never wrapped — `fetch_active_playlist` received a raw `HTTPError` instead of `GbsAuthExpiredError`.
- **Fix:** Changed the monkeypatch to raise `GbsAuthExpiredError` directly (the already-converted exception that the real `_open_with_cookies` would emit). This is the correct behavior contract for callers of `_open_with_cookies`.
- **Files modified:** `tests/test_gbs_api.py`
- **Commit:** Included in Task 2 commit `28e5a8f`

## Known Stubs

None — all functions are fully implemented and wired. `_download_logo` always attempts a real HTTP request; tests patch it out cleanly.

## Threat Flags

None beyond what was documented in the plan's threat_model. All 7 STRIDE entries (T-60-05 through T-60-11) are mitigated by implementation:
- T-60-05 (HTML parser): `_SongRowParser` anchors on stable href patterns; parse failures → empty results + log
- T-60-06 (no retry on GET-with-side-effects): `vote_now_playing` and `submit` are single-call; no retry logic exists
- T-60-07 (auth context): `load_auth_context()` returns None on missing OR corrupted file; never logs cookie values
- T-60-08 (timeouts): `_TIMEOUT_READ=10`, `_TIMEOUT_WRITE=15` applied on all endpoints
- T-60-09 (malformed messages cookie): `_decode_django_messages` wraps decode+parse in try/except → returns [] on any failure
- T-60-10 (auth expiry): `GbsAuthExpiredError` raised on 302→/accounts/login/ in both `_open_with_cookies` and `submit`
- T-60-11 (logo URL): logo URL is hard-coded constant (`https://gbs.fm/images/logo_3.png`); no SSRF

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `musicstreamer/gbs_api.py` exists | FOUND |
| `tests/test_gbs_api.py` exists | FOUND |
| Commit f606b24 (Task 1) | FOUND |
| Commit 28e5a8f (Task 2) | FOUND |
| Module assertions (GBS_BASE, 6 streams, FLAC=1411, paths, exception hierarchy) | PASS |
| 19 tests pass (18 test_gbs_api + test_gbs_flac_ordering) | PASS |
