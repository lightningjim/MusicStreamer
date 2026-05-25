---
phase: 60-gbs-fm-integration
plan: 01
subsystem: testing
tags: [gbs-fm, fixtures, conftest, pytest, cookies, netscape-cookies, wave0]

# Dependency graph
requires: []
provides:
  - "17 pinned gbs.fm fixture files under tests/fixtures/gbs/ (15 live-captured + 2 hand-crafted validator-rejection cookies)"
  - "scripts/gbs_capture_fixtures.sh: re-runnable bash capture harness for refreshing live fixtures"
  - "tests/conftest.py: mock_gbs_api, fake_repo, fake_cookies_jar, gbs_fixtures_dir shared fixtures"
  - "_FakeRepo in-memory Repo double with full Phase 60 API surface (insert_station, insert_stream, update_stream, update_station_art, etc.)"
  - "_FakeStation with canonical station_art_path attribute matching musicstreamer.models.Station"
affects: [60-02-api-client, 60-03-import, 60-04-accounts, 60-05-active-playlist, 60-06-vote, 60-07-search-submit]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Live-capture-then-pin fixture pattern: curl against real API with dev cookies → commit sanitized fixture files"
    - "MagicMock(spec=[...]) by string-name list: forward-compatible gbs_api mock that works before the real module exists"
    - "In-memory Repo double (_FakeRepo) for deterministic unit test coverage of data layer"

key-files:
  created:
    - "scripts/gbs_capture_fixtures.sh"
    - "tests/fixtures/gbs/ajax_cold_start.json"
    - "tests/fixtures/gbs/ajax_steady_state.json"
    - "tests/fixtures/gbs/ajax_vote_set.json"
    - "tests/fixtures/gbs/ajax_vote_clear.json"
    - "tests/fixtures/gbs/ajax_login_redirect.txt"
    - "tests/fixtures/gbs/home_playlist_table.html"
    - "tests/fixtures/gbs/search_test_p1.html"
    - "tests/fixtures/gbs/search_test_p2.html"
    - "tests/fixtures/gbs/search_empty.html"
    - "tests/fixtures/gbs/add_redirect_response.txt"
    - "tests/fixtures/gbs/api_nowplaying.txt"
    - "tests/fixtures/gbs/api_metadata.txt"
    - "tests/fixtures/gbs/api_vote_legacy.txt"
    - "tests/fixtures/gbs/cookies_valid.txt"
    - "tests/fixtures/gbs/cookies_invalid_no_sessionid.txt"
    - "tests/fixtures/gbs/cookies_invalid_wrong_domain.txt"
    - "tests/fixtures/gbs/messages_cookie_track_added.txt"
  modified:
    - "tests/conftest.py"

key-decisions:
  - "Live-captured the 13 curl-able fixtures against real gbs.fm using dev cookies (D-04a path confirmed present); script ran successfully on 2026-05-04"
  - "Hand-crafted 4 remaining fixtures: add_redirect_response.txt (302+messages cookie), cookies_valid.txt (sanitized Netscape format), cookies_invalid_no_sessionid.txt, cookies_invalid_wrong_domain.txt (GBS-01b validator rejection cases)"
  - "search_empty.html contains real gbs.fm response ('No exact dong/artist matches for search...' — no <table class=songs>) rather than plan's placeholder HTML; more accurate for parser unit tests"
  - "mock_gbs_api uses spec=[string-name-list] (not spec=module) so Wave 0 tests can run RED before 60-02 ships the real module (BLOCKER 4 fix)"
  - "_FakeStation.station_art_path matches musicstreamer.models.Station.station_art_path:31 (HIGH 1 fix — original draft used 'station_art')"

patterns-established:
  - "Pattern 1: Fixture capture script reads dev cookies from D-04a XDG path (~/.local/share/musicstreamer/dev-fixtures/) so cookies never enter the repo tree"
  - "Pattern 2: cookies_valid.txt uses <csrftoken-PLACEHOLDER>/<sessionid-PLACEHOLDER> tokens — verify commands grep for both presence of PLACEHOLDERs AND absence of real token values"
  - "Pattern 3: _FakeRepo auto-creates first stream in insert_station (mirrors repo.py:415-416) so test setup is single-call"

requirements-completed: [GBS-01a, GBS-01b, GBS-01c, GBS-01d, GBS-01e, GBS-01f]

# Metrics
duration: 6min
completed: 2026-05-04
---

# Phase 60 Plan 01: GBS.FM Fixtures and Test Infrastructure Summary

**17 live-captured and hand-crafted gbs.fm fixture files plus pytest shared fixtures (mock_gbs_api, fake_repo, fake_cookies_jar) pinning the test-data contract before any production gbs_api.py code ships**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-04T18:19:47Z
- **Completed:** 2026-05-04T18:25:51Z
- **Tasks:** 2 completed
- **Files modified:** 19 (18 created + 1 extended)

## Accomplishments

- Ran `scripts/gbs_capture_fixtures.sh` against live gbs.fm using dev cookies (D-04a path), capturing 13 real response payloads including `ajax_cold_start.json` with the full event taxonomy (now_playing, metadata, linkedMetadata, songLength, userVote, score, adds, pllength, songPosition)
- Hand-crafted 4 remaining fixtures: sanitized `cookies_valid.txt` (PLACEHOLDER tokens), `cookies_invalid_no_sessionid.txt` and `cookies_invalid_wrong_domain.txt` (GBS-01b validator rejection cases), and `messages_cookie_track_added.txt` (base64-url Django message payload)
- Extended `tests/conftest.py` with `mock_gbs_api` (MagicMock spec-by-string-list, forward-compatible with 60-02), `fake_repo` (_FakeRepo in-memory double), `fake_cookies_jar`, and `gbs_fixtures_dir` fixtures, preserving the existing `_stub_bus_bridge` autouse fixture

## Task Commits

1. **Task 1: Create gbs_capture_fixtures.sh + capture all 17 fixtures** - `2d00c29` (feat)
2. **Task 2: Extend tests/conftest.py with mock_gbs_api, fake_repo, fake_cookies_jar fixtures** - `c887711` (feat)

## Files Created/Modified

- `scripts/gbs_capture_fixtures.sh` - Re-runnable curl harness; reads D-04a dev cookies; 13 live fixture outputs + reminder to hand-create 2 cookie rejection cases
- `tests/fixtures/gbs/ajax_cold_start.json` - Live-captured cold-start /ajax response with full event taxonomy
- `tests/fixtures/gbs/ajax_steady_state.json` - Live-captured steady-state /ajax (minimal delta: userVote, score, songPosition)
- `tests/fixtures/gbs/ajax_vote_set.json` - Live-captured vote=3 response
- `tests/fixtures/gbs/ajax_vote_clear.json` - Live-captured vote=0 clear response
- `tests/fixtures/gbs/ajax_login_redirect.txt` - Live-captured 302 to /accounts/login/ response head
- `tests/fixtures/gbs/home_playlist_table.html` - Live-captured home page HTML (41KB)
- `tests/fixtures/gbs/search_test_p1.html` - Live-captured search page 1 (86KB, "Results: page 1 of 12")
- `tests/fixtures/gbs/search_test_p2.html` - Live-captured search page 2 (44KB, "Results: page 2 of 12")
- `tests/fixtures/gbs/search_empty.html` - Live-captured empty search ("No exact dong/artist matches", no songs table)
- `tests/fixtures/gbs/add_redirect_response.txt` - Hand-crafted 302+messages cookie response head
- `tests/fixtures/gbs/api_nowplaying.txt` - Live-captured entryid (single int line)
- `tests/fixtures/gbs/api_metadata.txt` - Live-captured 3-line metadata
- `tests/fixtures/gbs/api_vote_legacy.txt` - Live-captured legacy vote endpoint response
- `tests/fixtures/gbs/cookies_valid.txt` - Hand-crafted Netscape format with PLACEHOLDER tokens (T-60-01)
- `tests/fixtures/gbs/cookies_invalid_no_sessionid.txt` - Hand-crafted (no sessionid line) - drives test_validate_cookies_reject_no_sessionid
- `tests/fixtures/gbs/cookies_invalid_wrong_domain.txt` - Hand-crafted (.evil.example.com domain) - drives test_validate_cookies_reject_wrong_domain
- `tests/fixtures/gbs/messages_cookie_track_added.txt` - Hand-crafted base64-url Django message payload
- `tests/conftest.py` - Extended with 193 lines of Phase 60 fixtures (existing autouse fixture intact)

## Decisions Made

- Live-captured 13 fixtures from real gbs.fm (dev cookies present at D-04a path) rather than hand-crafting all 17 — produces more accurate parser test contracts
- `search_empty.html` uses real gbs.fm "No exact dong/artist matches..." response (no `<table class="songs">`) rather than plan's placeholder HTML — more robust for parser unit tests in 60-02
- `mock_gbs_api` uses `MagicMock(spec=[...])` with string-name list (not `spec=module`) so no import of the not-yet-existing `musicstreamer.gbs_api` is required at Wave 0
- `_FakeStation.station_art_path` matches `musicstreamer.models.Station.station_art_path` (line 31) — verified by reading models.py

## Deviations from Plan

None - plan executed exactly as written. The live capture succeeded (dev cookies present), and all 4 hand-crafted fixtures were created per plan specification. The `search_empty.html` uses real content rather than the plan's illustrative HTML, but this is strictly better (more accurate fixture) and matches the plan's intent.

## Issues Encountered

None - the dev cookies fixture was present at `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt` and all 13 curl captures succeeded on first run. The 7 pre-existing pytest collection errors (test_twitch_auth, test_twitch_playback, test_windows_palette) are pre-existing and unrelated to this plan's changes.

## User Setup Required

None - no external service configuration required for this plan.

## Next Phase Readiness

- All 17 fixture files committed and verified — Plans 60-02 through 60-07 can write deterministic parser and UI unit tests against real gbs.fm response shapes with no live HTTP in CI
- `mock_gbs_api` fixture is forward-compatible with Plan 60-02's `musicstreamer/gbs_api.py` module (spec catches API drift via string-name list)
- `fake_repo` covers all Repo methods Phase 60 needs (insert_station, insert_stream, update_stream, update_station_art, station_exists_by_url, get_setting, set_setting)
- No blockers for 60-02 or parallel wave plans

## Threat Flags

None - T-60-01 (cookie file to git) verified via grep: `csrftoken-PLACEHOLDER`/`sessionid-PLACEHOLDER` present in `cookies_valid.txt`; real tokens `q6UZ9t0`/`v6mfkwosmt` absent from all fixtures. T-60-02 (capture script to dev cookies path): script reads cookies from D-04a XDG path (outside OneDrive, outside git tree); echo statements never print cookie values.

---
*Phase: 60-gbs-fm-integration*
*Completed: 2026-05-04*
