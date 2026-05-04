---
phase: 60
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - scripts/gbs_capture_fixtures.sh
  - tests/fixtures/gbs/ajax_cold_start.json
  - tests/fixtures/gbs/ajax_steady_state.json
  - tests/fixtures/gbs/ajax_vote_set.json
  - tests/fixtures/gbs/ajax_vote_clear.json
  - tests/fixtures/gbs/ajax_login_redirect.txt
  - tests/fixtures/gbs/home_playlist_table.html
  - tests/fixtures/gbs/search_test_p1.html
  - tests/fixtures/gbs/search_test_p2.html
  - tests/fixtures/gbs/search_empty.html
  - tests/fixtures/gbs/add_redirect_response.txt
  - tests/fixtures/gbs/api_nowplaying.txt
  - tests/fixtures/gbs/api_metadata.txt
  - tests/fixtures/gbs/api_vote_legacy.txt
  - tests/fixtures/gbs/cookies_valid.txt
  - tests/fixtures/gbs/cookies_invalid_no_sessionid.txt
  - tests/fixtures/gbs/cookies_invalid_wrong_domain.txt
  - tests/fixtures/gbs/messages_cookie_track_added.txt
  - tests/conftest.py
autonomous: true
requirements: [GBS-01a, GBS-01b, GBS-01c, GBS-01d, GBS-01e, GBS-01f]
tags: [phase60, fixtures, wave0, gbs-fm]

must_haves:
  truths:
    - "All 15 fixture files exist under tests/fixtures/gbs/ with concrete payloads matching shapes documented in 60-RESEARCH.md §Validation Architecture"
    - "scripts/gbs_capture_fixtures.sh exists, is executable, and re-runs the capture flow against ~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt"
    - "tests/conftest.py exposes mock_gbs_api, fake_repo, fake_cookies_jar fixtures usable by every Phase 60 test file"
    - "All fixture files commit-safe — no real csrftoken/sessionid values; only documented PLACEHOLDER tokens (per RESEARCH §Validation Architecture)"
  artifacts:
    - path: "scripts/gbs_capture_fixtures.sh"
      provides: "Re-runnable bash script that curls gbs.fm with the dev cookies fixture and writes to tests/fixtures/gbs/"
      min_lines: 30
    - path: "tests/fixtures/gbs/ajax_cold_start.json"
      provides: "Cold-start /ajax response — drives fetch_active_playlist parser unit test (GBS-01c)"
    - path: "tests/fixtures/gbs/cookies_valid.txt"
      provides: "Sanitized Netscape cookies fixture for _validate_gbs_cookies accept-path"
      contains: "gbs.fm"
    - path: "tests/conftest.py"
      provides: "Shared pytest fixtures (mock_gbs_api, fake_repo, fake_cookies_jar)"
      contains: "fake_repo"
  key_links:
    - from: "tests/conftest.py"
      to: "musicstreamer.gbs_api"
      via: "MagicMock(spec=...) — module is referenced by name only; physical module ships in 60-02"
      pattern: "spec=.*gbs_api|fake_repo|fake_cookies_jar"
    - from: "scripts/gbs_capture_fixtures.sh"
      to: "~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt"
      via: "curl -b <path> https://gbs.fm/..."
      pattern: "dev-fixtures/gbs.fm.cookies.txt"
---

<objective>
Wave 0 deliverable: pin all 15 captured-payload fixtures, the capture-script harness, and the shared pytest fixtures into the repo so every later Phase 60 plan can write deterministic unit/integration tests against real gbs.fm response shapes (no live HTTP in CI).

Purpose: Lock the test-data contract before any production code is written. RESEARCH.md §Validation Architecture tied 29 test cases to specific fixture files; without them, Plans 02–07 cannot ship green automated verification. Per VALIDATION.md, this also unblocks the Nyquist-validation gate.

Output: 15 fixture files (committed), 1 bash capture script, conftest.py extension with three new fixtures.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/60-gbs-fm-integration/60-CONTEXT.md
@.planning/phases/60-gbs-fm-integration/60-RESEARCH.md
@.planning/phases/60-gbs-fm-integration/60-PATTERNS.md
@.planning/phases/60-gbs-fm-integration/60-VALIDATION.md
@tests/conftest.py

<interfaces>
<!-- Existing conftest.py shape (extends, doesn't replace) -->
From tests/conftest.py (30 LOC, autouse _stub_bus_bridge fixture):
```python
import pytest
from unittest.mock import MagicMock

@pytest.fixture(autouse=True)
def _stub_bus_bridge(monkeypatch):
    """Replace _ensure_bus_bridge with a MagicMock so Player() construction
    never starts the real GLib.MainLoop daemon thread in unit tests."""
    try:
        import musicstreamer.player as _player_mod
    except ImportError:
        return
    monkeypatch.setattr(_player_mod, "_ensure_bus_bridge", lambda: MagicMock())
```

<!-- gbs_api module surface (will be created in Plan 60-02; conftest fixtures spec against it by name) -->
Forward reference (Plan 60-02 creates these — conftest uses MagicMock(spec=) by string):
- musicstreamer.gbs_api.fetch_streams() -> list[dict]
- musicstreamer.gbs_api.fetch_station_metadata() -> dict
- musicstreamer.gbs_api.import_station(repo, on_progress=None) -> tuple[int, int]
- musicstreamer.gbs_api.fetch_active_playlist(cookies, cursor=None) -> dict
- musicstreamer.gbs_api.vote_now_playing(entryid, vote, cookies) -> dict
- musicstreamer.gbs_api.search(query, page, cookies) -> dict
- musicstreamer.gbs_api.submit(songid, cookies) -> str
- musicstreamer.gbs_api.GbsApiError
- musicstreamer.gbs_api.GbsAuthExpiredError
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create gbs_capture_fixtures.sh + capture all 15 fixtures</name>
  <read_first>
    - .planning/phases/60-gbs-fm-integration/60-RESEARCH.md (read §Validation Architecture → "Pinned Fixtures" table — 15 rows; §Capability 1-6 for response-shape examples; §Code Examples §Example 4 for messages-cookie raw shape)
    - ~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt (verify presence; if missing the script will be created but capture step fails — document in summary)
  </read_first>
  <action>
Create `scripts/gbs_capture_fixtures.sh` with the following EXACT shape (per D-04a + RESEARCH §Validation Architecture):

```bash
#!/usr/bin/env bash
# Phase 60 — Capture gbs.fm response fixtures for tests/fixtures/gbs/.
# Re-runnable; reads the dev cookies fixture from ~/.local/share/musicstreamer/dev-fixtures/.
# Outputs are sanitized: real csrftoken/sessionid values replaced with PLACEHOLDERs in cookies_valid.txt.
#
# Usage: bash scripts/gbs_capture_fixtures.sh
set -euo pipefail

COOKIES="${HOME}/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt"
OUT="tests/fixtures/gbs"
BASE="https://gbs.fm"

if [[ ! -f "$COOKIES" ]]; then
  echo "ERROR: dev cookies missing at $COOKIES — see 60-CONTEXT.md D-04a." >&2
  exit 1
fi

mkdir -p "$OUT"

# Pick a stable now_playing entryid by reading /api/nowplaying first.
ENTRYID="$(curl -sS -b "$COOKIES" "$BASE/api/nowplaying")"
echo "Captured entryid: $ENTRYID"

# 1. /ajax cold-start
curl -sS -b "$COOKIES" "$BASE/ajax?position=0&last_comment=0&last_removal=0&last_add=0&now_playing=0" > "$OUT/ajax_cold_start.json"

# 2. /ajax steady-state
curl -sS -b "$COOKIES" "$BASE/ajax?position=200&last_comment=0&last_removal=0&last_add=0&now_playing=$ENTRYID" > "$OUT/ajax_steady_state.json"

# 3. /ajax vote=3 (set)
curl -sS -b "$COOKIES" "$BASE/ajax?vote=3&now_playing=$ENTRYID&position=0&last_comment=0" > "$OUT/ajax_vote_set.json"

# 4. /ajax vote=0 (clear)
curl -sS -b "$COOKIES" "$BASE/ajax?vote=0&now_playing=$ENTRYID&position=0&last_comment=0" > "$OUT/ajax_vote_clear.json"

# 5. /ajax with no cookies → 302 to /accounts/login/
curl -sS -i "$BASE/ajax" | head -20 > "$OUT/ajax_login_redirect.txt"

# 6. Home page playlist table (just the relevant block)
curl -sS -b "$COOKIES" "$BASE/" > "$OUT/home_playlist_table.html"

# 7-9. Search (p1, p2, empty)
curl -sS -b "$COOKIES" "$BASE/search?query=test&page=1" > "$OUT/search_test_p1.html"
curl -sS -b "$COOKIES" "$BASE/search?query=test&page=2" > "$OUT/search_test_p2.html"
curl -sS -b "$COOKIES" "$BASE/search?query=zzzzzzzzznoresults&page=1" > "$OUT/search_empty.html"

# 10. /add/<id> redirect with messages cookie (DESTRUCTIVE — adds song 88135 to live playlist).
# Skip by default; uncomment the next line and pick a fresh songid to capture.
# curl -sS -i -b "$COOKIES" "$BASE/add/88135" | head -30 > "$OUT/add_redirect_response.txt"

# 11-13. Auxiliary plain-text endpoints
curl -sS -b "$COOKIES" "$BASE/api/nowplaying" > "$OUT/api_nowplaying.txt"
curl -sS -b "$COOKIES" "$BASE/api/metadata" > "$OUT/api_metadata.txt"
curl -sS -b "$COOKIES" "$BASE/api/vote?songid=88135&vote=0" > "$OUT/api_vote_legacy.txt" || true

echo "Done. Fixtures written to $OUT/"
echo "REMEMBER: sanitize cookies_valid.txt manually — replace real sessionid/csrftoken values with PLACEHOLDERs."
```

`chmod +x scripts/gbs_capture_fixtures.sh`.

Then RUN the script once (if dev cookies fixture present at `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt`) to capture the live payloads.

If the fixture is MISSING (D-04a path), instead create each of the 15 fixture files with concrete shapes derived from RESEARCH.md §Capability 1-6. Specifically:

- `ajax_cold_start.json` — JSON array per RESEARCH §Capability 3 "Cold-start call" example. Use the documented response shape: `[["removal", {"entryid": 44, "id": 1}], ..., ["now_playing", 1810736], ["metadata", "Crippling Alcoholism (With Love From A Padded Room) - Templeton"], ["linkedMetadata", "<a href='/artist/84134'>...</a>"], ["songLength", 274], ["clearComments", ""], ["userVote", 0], ["score", "no votes"], ["adds", "<tr id='1810736' class='playing odd'>...</tr>"], ["pllength", "Playlist is 11:21 long with 3 dongs"], ["songPosition", 202.68999999999997]]`. Provide AT LEAST one of each event type (now_playing, metadata, linkedMetadata, songLength, songPosition, userVote, score, adds, removal, clearComments, pllength).
- `ajax_steady_state.json` — minimal-delta: `[["userVote", 0], ["score", "5.0 (1 vote)"], ["songPosition", 200.49000000000004]]`.
- `ajax_vote_set.json` — `[["userVote", 3], ["score", "4.0 (2 votes)"], ["songPosition", 200.49]]`.
- `ajax_vote_clear.json` — `[["userVote", 0], ["score", "5.0 (1 vote)"], ["songPosition", 201.49]]`.
- `ajax_login_redirect.txt` — HTTP raw response head: `HTTP/2 302\nlocation: /accounts/login/?next=/ajax\n\n`.
- `home_playlist_table.html` — wrap the row template from RESEARCH.md §Capability 3 "HTML row parsing" inside `<table class="playlist"><tbody>...</tbody></table>` with at least 3 rows (one `class="playing odd"`, two queue rows).
- `search_test_p1.html` — wrap rows from RESEARCH §Capability 5 inside `<table class="songs">` with 5 rows + a `<p>Results: page 1 of 12</p>` marker.
- `search_test_p2.html` — same shape, 5 rows, `<p>Results: page 2 of 12</p>`.
- `search_empty.html` — `<html><body><p>Results: page 1 of 1</p><p>No songs matched your query.</p></body></html>` (no `<table class="songs">`).
- `add_redirect_response.txt` — raw HTTP response head: `HTTP/2 302\nlocation: /playlist\nset-cookie: messages=W1siX19qc29uX21lc3NhZ2UiLDAsMjUsIlRyYWNrIGFkZGVkIHN1Y2Nlc3NmdWxseSEiLCIiXV0:1wJtOd:6O1abc; path=/; httponly\n\n` (the base64-prefixed value before `:` decodes to `[["__json_message",0,25,"Track added successfully!",""]]`).
- `api_nowplaying.txt` — single line: `1810737\n`.
- `api_metadata.txt` — three lines: `Crippling Alcoholism\nWith Love From A Padded Room\nTempleton\n`.
- `api_vote_legacy.txt` — `0 the pentagon (test 1) - $$ VIRAL $$ (tonetta777 cover) (test 2)\n`.
- `cookies_valid.txt` — Netscape cookies.txt format (per RESEARCH §Auth Ladder Recommendation):
  ```
  # Netscape HTTP Cookie File
  .gbs.fm	TRUE	/	TRUE	1761855552	csrftoken	<csrftoken-PLACEHOLDER>
  gbs.fm	FALSE	/	TRUE	1747491264	sessionid	<sessionid-PLACEHOLDER>
  ```
- `cookies_invalid_no_sessionid.txt` — same shape, csrftoken row only (no sessionid line).
- `cookies_invalid_wrong_domain.txt` — same shape but domain `.evil.example.com` for both rows.
- `messages_cookie_track_added.txt` — single line: `W1siX19qc29uX21lc3NhZ2UiLDAsMjUsIlRyYWNrIGFkZGVkIHN1Y2Nlc3NmdWxseSEiLCIiXV0`. (Base64-url; padding will be re-added by the decoder.)

After running script OR hand-creating: ensure `tests/fixtures/gbs/cookies_valid.txt` has BOTH cookie lines AND the `# Netscape HTTP Cookie File` header. Replace any leaked real csrftoken/sessionid values with PLACEHOLDERs before commit.

Decision implements D-04a (corrected dev fixture location), VALIDATION.md Wave 0 Requirements rows 6-7, RESEARCH.md §Validation Architecture "Pinned Fixtures" table.
  </action>
  <verify>
    <automated>test -x scripts/gbs_capture_fixtures.sh &amp;&amp; ls tests/fixtures/gbs/*.json tests/fixtures/gbs/*.html tests/fixtures/gbs/*.txt | wc -l | grep -qE '^\s*1[5-9]|^\s*2[0-9]' &amp;&amp; grep -q 'Netscape HTTP Cookie File' tests/fixtures/gbs/cookies_valid.txt &amp;&amp; grep -q 'csrftoken-PLACEHOLDER' tests/fixtures/gbs/cookies_valid.txt &amp;&amp; grep -q 'sessionid-PLACEHOLDER' tests/fixtures/gbs/cookies_valid.txt &amp;&amp; ! grep -E 'q6UZ9t0|v6mfkwosmt' tests/fixtures/gbs/cookies_valid.txt</automated>
  </verify>
  <done>
- 15 fixture files exist under tests/fixtures/gbs/ (json + html + txt mix)
- scripts/gbs_capture_fixtures.sh exists, is executable, references the D-04a path
- cookies_valid.txt has Netscape header + sessionid + csrftoken with PLACEHOLDERs (no leaked real tokens)
- ajax_cold_start.json contains a now_playing event AND a userVote event AND a score event AND an adds event
- search_test_p1.html contains "Results: page 1 of"
  </done>
</task>

<task type="auto">
  <name>Task 2: Extend tests/conftest.py with mock_gbs_api, fake_repo, fake_cookies_jar fixtures</name>
  <read_first>
    - tests/conftest.py (current file, 30 lines — extend without breaking _stub_bus_bridge)
    - .planning/phases/60-gbs-fm-integration/60-PATTERNS.md (read §"tests/conftest.py extension" — lines documenting fake_repo API surface)
    - .planning/phases/60-gbs-fm-integration/60-RESEARCH.md (skim §Code Examples — for the gbs_api function signatures referenced by the MagicMock spec)
    - musicstreamer/repo.py (read lines 178-225 + 348-410 — the Repo methods Phase 60 calls: insert_station, insert_stream, list_streams, update_stream, station_exists_by_url, get_setting, set_setting, update_station_art)
  </read_first>
  <action>
Append to `tests/conftest.py` (do NOT remove or modify the existing autouse `_stub_bus_bridge` fixture):

```python
# === Phase 60 (GBS.FM) shared fixtures =====================================
# Spec: 60-PATTERNS.md §"tests/conftest.py extension" + 60-VALIDATION.md
# §Wave 0 Requirements row 5. These fixtures are NON-autouse — opt-in
# per test by injection.

from pathlib import Path
import http.cookiejar


@pytest.fixture
def mock_gbs_api():
    """MagicMock with the gbs_api module surface pre-stubbed.

    Phase 60-02 creates the real module. This fixture stays decoupled
    via spec-by-name — no import — so Wave 0 tests can RED against the
    spec before 60-02 lands.
    """
    api = MagicMock()
    api.fetch_streams.return_value = [
        {"url": "https://gbs.fm/96", "quality": "96", "position": 60, "codec": "MP3", "bitrate_kbps": 96},
        {"url": "https://gbs.fm/128", "quality": "128", "position": 50, "codec": "MP3", "bitrate_kbps": 128},
        {"url": "https://gbs.fm/192", "quality": "192", "position": 40, "codec": "MP3", "bitrate_kbps": 192},
        {"url": "https://gbs.fm/256", "quality": "256", "position": 30, "codec": "MP3", "bitrate_kbps": 256},
        {"url": "https://gbs.fm/320", "quality": "320", "position": 20, "codec": "MP3", "bitrate_kbps": 320},
        {"url": "https://gbs.fm/flac", "quality": "flac", "position": 10, "codec": "FLAC", "bitrate_kbps": 1411},
    ]
    api.fetch_station_metadata.return_value = {
        "name": "GBS.FM",
        "description": "",
        "logo_url": "https://gbs.fm/images/logo_3.png",
        "homepage": "https://gbs.fm/",
    }
    api.fetch_active_playlist.return_value = {
        "now_playing_entryid": 1810736,
        "now_playing_songid": 782491,
        "icy_title": "Crippling Alcoholism - Templeton",
        "song_length": 274,
        "song_position": 202.68999999999997,
        "user_vote": 0,
        "score": "no votes",
        "queue_html_snippets": [],
        "removed_ids": [],
        "queue_summary": "Playlist is 11:21 long with 3 dongs",
    }
    api.vote_now_playing.return_value = {"user_vote": 3, "score": "4.0 (2 votes)"}
    api.search.return_value = {
        "results": [
            {"songid": 782491, "artist": "Crippling Alcoholism", "title": "Templeton",
             "duration": "4:34", "add_url": "/add/782491"},
        ],
        "page": 1,
        "total_pages": 1,
    }
    api.submit.return_value = "Track added successfully!"
    return api


class _FakeStation:
    def __init__(self, station_id, name, url, provider_name, tags=""):
        self.id = station_id
        self.name = name
        self.url = url
        self.provider_name = provider_name
        self.tags = tags
        self.streams = []
        self.station_art = None


class _FakeStream:
    def __init__(self, stream_id, station_id, url, label="", quality="",
                 position=1, stream_type="", codec="", bitrate_kbps=0):
        self.id = stream_id
        self.station_id = station_id
        self.url = url
        self.label = label
        self.quality = quality
        self.position = position
        self.stream_type = stream_type
        self.codec = codec
        self.bitrate_kbps = bitrate_kbps


class _FakeRepo:
    """In-memory Repo double — covers every Repo method Phase 60 calls.

    Tracks stations, streams, and settings via Python dicts. Mirrors:
      - station_exists_by_url
      - insert_station / list_streams / insert_stream / update_stream
      - get_setting / set_setting
      - update_station_art / get_station / list_stations
    """
    def __init__(self):
        self._stations = {}      # station_id -> _FakeStation
        self._streams = {}       # stream_id -> _FakeStream
        self._settings = {}      # key -> str
        self._next_station_id = 1
        self._next_stream_id = 1

    def station_exists_by_url(self, url):
        for s in self._streams.values():
            if s.url == url:
                return True
        return False

    def insert_station(self, name, url, provider_name, tags):
        sid = self._next_station_id
        self._next_station_id += 1
        st = _FakeStation(sid, name, url, provider_name, tags)
        self._stations[sid] = st
        # Mirrors repo.py:407-417 — auto-create first stream
        if url:
            self.insert_stream(sid, url)
        return sid

    def list_streams(self, station_id):
        return [s for s in self._streams.values() if s.station_id == station_id]

    def insert_stream(self, station_id, url, label="", quality="", position=1,
                      stream_type="", codec="", bitrate_kbps=0):
        sid = self._next_stream_id
        self._next_stream_id += 1
        self._streams[sid] = _FakeStream(
            sid, station_id, url, label, quality, position, stream_type, codec, bitrate_kbps,
        )
        return sid

    def update_stream(self, stream_id, url, label, quality, position,
                      stream_type, codec, bitrate_kbps=0):
        s = self._streams[stream_id]
        s.url = url
        s.label = label
        s.quality = quality
        s.position = position
        s.stream_type = stream_type
        s.codec = codec
        s.bitrate_kbps = bitrate_kbps

    def delete_stream(self, stream_id):
        self._streams.pop(stream_id, None)

    def get_setting(self, key, default=""):
        return self._settings.get(key, default)

    def set_setting(self, key, value):
        self._settings[key] = value

    def update_station_art(self, station_id, art_path):
        if station_id in self._stations:
            self._stations[station_id].station_art = art_path

    def get_station(self, station_id):
        return self._stations.get(station_id)

    def list_stations(self):
        return list(self._stations.values())


@pytest.fixture
def fake_repo():
    """Empty in-memory Repo double matching the API Phase 60 calls."""
    return _FakeRepo()


@pytest.fixture
def fake_cookies_jar():
    """Empty MozillaCookieJar — drop-in for gbs_api auth_context arguments."""
    return http.cookiejar.MozillaCookieJar()


@pytest.fixture
def gbs_fixtures_dir():
    """Path to tests/fixtures/gbs/ — for tests that read captured HTML/JSON."""
    return Path(__file__).parent / "fixtures" / "gbs"
```

Decision implements VALIDATION.md Wave 0 Requirements row 5 + PATTERNS.md §"tests/conftest.py extension". `fake_repo` mirrors the real `Repo` API surface used in PATTERNS.md §"Repo multi-stream insert/update". `mock_gbs_api` is decoupled from the actual `musicstreamer.gbs_api` module via `MagicMock()` (no spec=) — Plan 60-02 will create the module; this fixture is forward-compatible.
  </action>
  <verify>
    <automated>python -c "import sys; sys.path.insert(0, '.'); from tests.conftest import _FakeRepo; r = _FakeRepo(); sid = r.insert_station('GBS.FM', 'https://gbs.fm/96', 'GBS.FM', ''); assert r.station_exists_by_url('https://gbs.fm/96'); assert len(r.list_streams(sid)) == 1; r.insert_stream(sid, 'https://gbs.fm/128', quality='128', bitrate_kbps=128); assert len(r.list_streams(sid)) == 2; r.set_setting('foo', 'bar'); assert r.get_setting('foo') == 'bar'; print('OK')" &amp;&amp; pytest tests/conftest.py --collect-only -q 2>&amp;1 | grep -qE 'no tests ran|0 tests collected' &amp;&amp; grep -q '_stub_bus_bridge' tests/conftest.py</automated>
  </verify>
  <done>
- tests/conftest.py extended with mock_gbs_api, fake_repo, fake_cookies_jar, gbs_fixtures_dir fixtures
- _stub_bus_bridge autouse fixture intact (regression)
- _FakeRepo offers station_exists_by_url, insert_station (auto-streams), list_streams, insert_stream, update_stream, get_setting, set_setting, update_station_art, get_station, list_stations
- mock_gbs_api.fetch_streams() returns 6 entries (96/128/192/256/320/flac) with FLAC bitrate_kbps=1411
- pytest collects without errors (no test regressions)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Filesystem ↔ git | Fixture content (cookies_valid.txt) crosses into version control; real session tokens MUST be stripped |
| Local FS ↔ third-party (gbs.fm) | Capture script reads dev cookies and exercises gbs.fm endpoints; no untrusted input enters the repo |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-60-01 | Information Disclosure | tests/fixtures/gbs/cookies_valid.txt | mitigate | Force PLACEHOLDER tokens (verify command greps for both `csrftoken-PLACEHOLDER` and `sessionid-PLACEHOLDER`, AND greps OUT the real fixture values `q6UZ9t0` / `v6mfkwosmt`). RESEARCH §Validation Architecture row "cookies_valid.txt" notes "REPLACE the real csrftoken/sessionid values". |
| T-60-02 | Information Disclosure | scripts/gbs_capture_fixtures.sh | mitigate | Script reads cookies from `~/.local/share/musicstreamer/dev-fixtures/` (D-04a corrected path — outside OneDrive sync, outside git tree). Echo statements never print cookie values. |
| T-60-03 | Tampering | Fixture content (HTML/JSON shapes) | mitigate | Fixtures are committed verbatim from real gbs.fm responses (or hand-written from RESEARCH §Capability examples) — no transformation that could introduce parser-bypass payloads. RESEARCH §Pitfall 6 "HTML scraping fragility" — fixtures pin the contract. |
| T-60-04 | DoS (3rd-party) | Capture script live HTTP | accept | Script exercises gbs.fm with the dev cookies — single-user one-shot capture, well within the 15s polling cadence the gbs.fm web UI itself uses (RESEARCH §Pitfall 5). The destructive `/add/<id>` capture is commented out by default. |

Citations: Pitfalls 5, 6, 11 from RESEARCH.md.
</threat_model>

<verification>
After both tasks complete:

```bash
# Wave 0 fixture inventory check
ls tests/fixtures/gbs/ | wc -l   # ≥ 15
test -x scripts/gbs_capture_fixtures.sh
grep -q 'PLACEHOLDER' tests/fixtures/gbs/cookies_valid.txt
! grep -E 'q6UZ9t0|v6mfkwosmt' tests/fixtures/gbs/    # no leaked real tokens

# conftest sanity
pytest --collect-only -q 2>&1 | grep -E '(error|PASSED|FAILED)' || echo "Collection clean"
pytest tests/test_aa_import.py -x -q   # regression — existing autouse fixture still works
```
</verification>

<success_criteria>
- 15 fixture files in `tests/fixtures/gbs/` matching VALIDATION.md row count
- `scripts/gbs_capture_fixtures.sh` exists, executable, references `~/.local/share/musicstreamer/dev-fixtures/`
- `tests/conftest.py` has `mock_gbs_api`, `fake_repo`, `fake_cookies_jar`, `gbs_fixtures_dir` fixtures alongside the existing autouse `_stub_bus_bridge`
- No real csrftoken/sessionid values leaked into committed fixtures
- `pytest --collect-only` runs cleanly (no import errors from conftest extension)
- One existing test file (e.g. `tests/test_aa_import.py`) still passes (regression check that autouse fixture still works)
</success_criteria>

<output>
After completion, create `.planning/phases/60-gbs-fm-integration/60-01-SUMMARY.md`
</output>
