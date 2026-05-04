---
phase: 60
plan: 02
type: execute
wave: 1
depends_on: ["60-01"]
files_modified:
  - musicstreamer/gbs_api.py
  - musicstreamer/paths.py
  - tests/test_gbs_api.py
  - tests/test_stream_ordering.py
autonomous: true
requirements: [GBS-01a, GBS-01b, GBS-01c, GBS-01d, GBS-01e, GBS-01f]
tags: [phase60, api-client, foundation, gbs-fm]

must_haves:
  truths:
    - "fetch_streams() returns 6 hard-coded quality variants (96/128/192/256/320 MP3 + FLAC), with FLAC bitrate_kbps=1411 (CD-quality sentinel per RESEARCH §Open Question Q1 / D-01a)"
    - "fetch_station_metadata() returns the static metadata dict (name, description, logo_url, homepage)"
    - "import_station(repo, on_progress=None) is idempotent — first call inserts a Station + 6 streams + logo art; second call updates in-place preserving the station_id"
    - "fetch_active_playlist(cookies, cursor=None) parses /ajax JSON event arrays into a folded state dict; raises GbsAuthExpiredError on 302→/accounts/login/"
    - "vote_now_playing(entryid, vote, cookies) sends GET /ajax?vote=N&now_playing=<id> and returns {user_vote, score} parsed from the same response"
    - "search(query, page, cookies) parses /search HTML into {results: [...], page, total_pages}; anchors on data-songid / /add/<id> href / /song/<id> href (Pitfall 6)"
    - "submit(songid, cookies) sends GET /add/<id>, intercepts the 302, decodes the Django messages cookie, returns the success/error string"
    - "_validate_gbs_cookies(text) returns True iff text has Netscape header + a sessionid line + a csrftoken line, both for domain matching gbs.fm"
    - "GbsApiError, GbsAuthExpiredError typed exceptions exist; submit/vote/fetch never retry on transient failure (Pitfall 7)"
    - "FLAC stream sorts FIRST through stream_ordering.order_streams (regression test extending tests/test_stream_ordering.py)"
  artifacts:
    - path: "musicstreamer/gbs_api.py"
      provides: "Pure-urllib HTTP client + import orchestrator + HTML parsers + typed exceptions"
      min_lines: 250
      exports: ["GBS_BASE", "GBS_STATION_METADATA", "fetch_streams", "fetch_station_metadata", "import_station", "fetch_active_playlist", "vote_now_playing", "search", "submit", "load_auth_context", "GbsApiError", "GbsAuthExpiredError"]
    - path: "musicstreamer/paths.py"
      provides: "gbs_cookies_path() helper returning <root>/gbs-cookies.txt"
      contains: "def gbs_cookies_path"
    - path: "tests/test_gbs_api.py"
      provides: "Unit + integration tests covering all 9 public functions + parser edge cases + auth-expired path"
      min_lines: 300
    - path: "tests/test_stream_ordering.py"
      provides: "test_gbs_flac_ordering — extends existing file"
      contains: "def test_gbs_flac_ordering"
  key_links:
    - from: "musicstreamer.gbs_api.import_station"
      to: "musicstreamer.repo.Repo.insert_stream / update_stream / list_streams / station_exists_by_url"
      via: "AA-import precedent (aa_import.py:207-309)"
      pattern: "repo\\.(insert_stream|update_stream|list_streams|station_exists_by_url|insert_station|update_station_art)"
    - from: "musicstreamer.gbs_api.import_station"
      to: "musicstreamer.assets.copy_asset_for_station"
      via: "Logo download (aa_import.py:281 precedent)"
      pattern: "copy_asset_for_station"
    - from: "musicstreamer.gbs_api"
      to: "stream_ordering.order_streams"
      via: "FLAC bitrate_kbps=1411 sentinel sorts FIRST"
      pattern: "bitrate_kbps.*1411|1411.*FLAC"
    - from: "musicstreamer.gbs_api.submit"
      to: "Django messages cookie decoder"
      via: "_decode_django_messages helper (base64-url + json)"
      pattern: "urlsafe_b64decode|_decode_django_messages"
    - from: "musicstreamer.paths.gbs_cookies_path"
      to: "<XDG_DATA_HOME>/musicstreamer/gbs-cookies.txt"
      via: "Mirrors paths.cookies_path() shape (paths.py:46)"
      pattern: "gbs-cookies\\.txt"
---

<objective>
Ship `musicstreamer/gbs_api.py` — the foundation HTTP client + import orchestrator + HTML/JSON parsers + typed exceptions for Phase 60. Also adds `paths.gbs_cookies_path()` (D-04 ladder #3 LOCKED — file at `~/.local/share/musicstreamer/gbs-cookies.txt`) and the `_validate_gbs_cookies` helper used by AccountsDialog (60-04) and CookieImportDialog (60-04).

Purpose: Every other Phase 60 plan (import wiring, accounts dialog, active playlist, vote, search/submit) consumes this module. Locking the API surface here means downstream plans can run in parallel without coordination.

Output: One Python module (~250 LOC) + one paths helper line + one comprehensive test file (~300 LOC) + one regression test extension. Pure stdlib (urllib, http.cookiejar, html.parser, base64, json) — no new pip dependencies.
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
@.planning/phases/60-gbs-fm-integration/60-01-SUMMARY.md
@musicstreamer/aa_import.py
@musicstreamer/repo.py
@musicstreamer/stream_ordering.py
@musicstreamer/paths.py
@musicstreamer/assets.py

<interfaces>
<!-- repo.py:178-202 — multi-stream CRUD signatures -->
From musicstreamer/repo.py:
```python
def list_streams(self, station_id: int) -> List[StationStream]
def insert_stream(self, station_id: int, url: str, label: str = "",
                  quality: str = "", position: int = 1,
                  stream_type: str = "", codec: str = "",
                  bitrate_kbps: int = 0) -> int
def update_stream(self, stream_id: int, url: str, label: str,
                  quality: str, position: int, stream_type: str, codec: str,
                  bitrate_kbps: int = 0) -> None
def station_exists_by_url(self, url: str) -> bool   # repo.py:401
def insert_station(self, name: str, url: str, provider_name: str, tags: str) -> int   # repo.py:407 (auto-creates first stream if url)
def update_station_art(self, station_id: int, art_path: str) -> None   # repo.py:459
def get_setting(self, key: str, default: str) -> str   # repo.py:348
def set_setting(self, key: str, value: str) -> None    # repo.py:354
```

<!-- assets.py — logo download helper -->
From musicstreamer/assets.py:
```python
def copy_asset_for_station(station_id: int, src_path: str, kind: str) -> str
# kind: "station_art" | "cover_art" | etc. Returns the destination path.
# Used by aa_import.py:281, yt_import similar.
```

<!-- stream_ordering.py:43 — quality ordering invariants -->
From musicstreamer/stream_ordering.py:
```python
# codec_rank: FLAC=3, MP3=1, AAC=2, default 0 (line 25-32)
# quality_rank: "hi"/"med"/"low" → 3/2/1; default 0 (line 34-41)
# order_streams: partition known(bitrate_kbps>0) FIRST sorted by
#   (-quality_rank, -codec_rank, -bitrate_kbps, position),
#   unknown LAST sorted by position.
# GBS streams use quality="96"/"128"/.../"flac" → all quality_rank=0,
# so codec_rank + bitrate_kbps drive ordering.
# With FLAC codec_rank=3 vs MP3=1, FLAC wins regardless of bitrate_kbps
# AS LONG AS bitrate_kbps > 0 (otherwise partitioned LAST).
# RESEARCH recommends FLAC bitrate_kbps=1411 (CD-baseline sentinel).
```

<!-- paths.py:46 — accessor pattern (mirror) -->
From musicstreamer/paths.py:
```python
def cookies_path() -> str:
    return os.path.join(_root(), "cookies.txt")

def twitch_token_path() -> str:
    return os.path.join(_root(), "twitch-token.txt")
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create musicstreamer/gbs_api.py module + paths.gbs_cookies_path()</name>
  <read_first>
    - musicstreamer/aa_import.py (read in full — primary analog: lines 1-50 imports + 88-111 module constants + 207-309 import orchestrator + 275-293 logo download)
    - musicstreamer/paths.py (read in full — 87 lines)
    - musicstreamer/repo.py (lines 178-202, 348-360, 401-417, 459-465 — every Repo method gbs_api calls)
    - musicstreamer/assets.py (skim — confirm copy_asset_for_station signature)
    - musicstreamer/stream_ordering.py (read full — 64 lines — for FLAC sentinel reasoning)
    - .planning/phases/60-gbs-fm-integration/60-RESEARCH.md (read §"Code Examples" Examples 1–4 verbatim — these are the canonical implementations; §"API Surface Map" §Capability 1-6 for endpoint signatures)
    - .planning/phases/60-gbs-fm-integration/60-PATTERNS.md (read §"musicstreamer/gbs_api.py" subsection — gives line-by-line pattern application)
    - musicstreamer/cookie_utils.py (skim — for is_cookie_file_corrupted reuse)
  </read_first>
  <behavior>
    - fetch_streams() returns the static 6-tier list with FLAC bitrate_kbps=1411
    - fetch_station_metadata() returns dict with name="GBS.FM", logo_url="https://gbs.fm/images/logo_3.png"
    - import_station(repo) inserts a new Station + 6 streams when none exist (returns (1, 0))
    - import_station(repo) updates streams in place when already present (returns (0, 1)) — preserves station.id
    - import_station downloads logo via copy_asset_for_station and calls repo.update_station_art
    - fetch_active_playlist(cookies) sends GET /ajax with cursor and folds the JSON event array into {now_playing_entryid, now_playing_songid, icy_title, song_length, song_position, user_vote, score, queue_html_snippets, removed_ids, queue_summary, last_add_entryid, last_removal_id}
    - fetch_active_playlist raises GbsAuthExpiredError when 302 → /accounts/login/
    - vote_now_playing(entryid, vote, cookies) sends GET /ajax?vote=N&now_playing=<id> with vote in {0,1,2,3,4,5}; returns {user_vote, score}
    - vote_now_playing raises ValueError on invalid vote
    - search(query, page, cookies) parses /search HTML, returns {results: [{songid, artist, title, duration, add_url}], page, total_pages}
    - search empty page returns {results: [], page: 1, total_pages: 1} (no exception)
    - submit(songid, cookies) intercepts 302, decodes messages cookie, returns the message text
    - submit raises GbsAuthExpiredError on 302 → /accounts/login/
    - _decode_django_messages(cookie_value) returns list of message strings
    - _validate_gbs_cookies(text) returns True for Netscape file with sessionid+csrftoken on gbs.fm domain; False otherwise
    - load_auth_context() returns a MozillaCookieJar loaded from paths.gbs_cookies_path() if file exists; None otherwise
    - GbsApiError and GbsAuthExpiredError(GbsApiError) classes exist
  </behavior>
  <action>
**Step A — extend `musicstreamer/paths.py`:**

Insert after `twitch_token_path()` (after line 51, before `oauth_log_path()` at line 54):

```python
def gbs_cookies_path() -> str:
    """Phase 60 D-04 (ladder #3 LOCKED): GBS.FM session cookies file.

    Mirrors the YouTube cookies path shape. Pure — does not create the
    directory. Caller writes with 0o600 perms (Phase 999.7 convention).
    """
    return os.path.join(_root(), "gbs-cookies.txt")
```

**Step B — create `musicstreamer/gbs_api.py`** (~250 LOC):

Use the EXACT shape below. Constants are LOCKED per RESEARCH §Capability 1; do not edit values.

```python
"""GBS.FM API client + multi-quality import orchestrator (Phase 60 D-03).

Public API:
  fetch_streams() -> list[dict]
  fetch_station_metadata() -> dict
  import_station(repo, on_progress=None) -> tuple[int, int]
  fetch_active_playlist(cookies, cursor=None) -> dict
  vote_now_playing(entryid, vote, cookies) -> dict
  search(query, page, cookies) -> dict
  submit(songid, cookies) -> str
  load_auth_context() -> http.cookiejar.MozillaCookieJar | None
  _validate_gbs_cookies(text) -> bool
  _decode_django_messages(cookie_value) -> list[str]

Auth model: Django session cookies (sessionid + csrftoken). D-04 ladder #3
LOCKED. Cookies live at paths.gbs_cookies_path() with 0o600 perms.

Pitfalls (RESEARCH §Common Pitfalls — see also threat_model in 60-02-PLAN):
  1. ICY title → entryid race: vote uses entryid from /ajax, never ICY (consumer plan 60-06)
  2. Optimistic UI: callers use returned user_vote/score for confirm/rollback
  3. Auth expiry: 302 → /accounts/login/ → GbsAuthExpiredError
  6. HTML scraping fragility: anchor on data-songid + /song/X + /add/X
  7. GET-with-side-effects: NO retries
  8. Token-quota: messages cookie decoded for inline error
"""
from __future__ import annotations

import base64
import http.cookiejar
import json
import logging
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Optional

from musicstreamer import paths
from musicstreamer.assets import copy_asset_for_station
from musicstreamer.repo import Repo

_log = logging.getLogger(__name__)

# ---------- Constants (D-01a / RESEARCH §Capability 1, 2) ----------

GBS_BASE = "https://gbs.fm"

GBS_STATION_METADATA = {
    "name": "GBS.FM",
    "description": "",
    "logo_url": f"{GBS_BASE}/images/logo_3.png",
    "homepage": f"{GBS_BASE}/",
}

# Position: lower = higher quality (matches stream_ordering convention).
# FLAC bitrate_kbps=1411 is the CD-baseline sentinel per RESEARCH Open
# Question Q1 — interacts with stream_ordering.order_streams Phase 47.1
# D-09 partition logic so FLAC sorts FIRST among GBS quality tiers.
# (codec_rank(FLAC)=3 > codec_rank(MP3)=1 carries the order — but
# bitrate_kbps must be > 0 to avoid the unknown-bitrate-LAST partition.)
_GBS_QUALITY_TIERS = [
    {"url": f"{GBS_BASE}/96",   "quality": "96",   "position": 60, "codec": "MP3",  "bitrate_kbps": 96},
    {"url": f"{GBS_BASE}/128",  "quality": "128",  "position": 50, "codec": "MP3",  "bitrate_kbps": 128},
    {"url": f"{GBS_BASE}/192",  "quality": "192",  "position": 40, "codec": "MP3",  "bitrate_kbps": 192},
    {"url": f"{GBS_BASE}/256",  "quality": "256",  "position": 30, "codec": "MP3",  "bitrate_kbps": 256},
    {"url": f"{GBS_BASE}/320",  "quality": "320",  "position": 20, "codec": "MP3",  "bitrate_kbps": 320},
    {"url": f"{GBS_BASE}/flac", "quality": "flac", "position": 10, "codec": "FLAC", "bitrate_kbps": 1411},
]

# Read timeouts (D-03a)
_TIMEOUT_READ = 10
_TIMEOUT_WRITE = 15

_USER_AGENT = "MusicStreamer/2.0 (gbs_api)"


# ---------- Typed exceptions (D-03c) ----------

class GbsApiError(Exception):
    """Generic GBS.FM API failure."""


class GbsAuthExpiredError(GbsApiError):
    """302 → /accounts/login/ — session cookie no longer authorizes."""


# ---------- Auth context (D-04 ladder #3) ----------

def load_auth_context() -> Optional[http.cookiejar.MozillaCookieJar]:
    """Return a loaded MozillaCookieJar from paths.gbs_cookies_path() or None.

    Returns None if the cookies file does not exist OR if it is corrupted
    per cookie_utils.is_cookie_file_corrupted (Phase 999.7).
    """
    path = paths.gbs_cookies_path()
    if not os.path.exists(path):
        return None
    try:
        # Lazy import to avoid Qt-side circular deps in test environments.
        from musicstreamer import cookie_utils
        if cookie_utils.is_cookie_file_corrupted(path):
            return None
    except ImportError:
        pass
    jar = http.cookiejar.MozillaCookieJar(path)
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except Exception:
        return None
    return jar


def _validate_gbs_cookies(text: str) -> bool:
    """Return True iff text is a Netscape cookies.txt with sessionid+csrftoken on gbs.fm.

    Mirrors _validate_youtube_cookies (cookie_import_dialog.py:50).
    """
    has_sessionid = False
    has_csrftoken = False
    has_gbs_domain = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split("\t")
        if len(parts) < 7:
            continue
        # Netscape columns: domain | flag | path | secure | expiry | name | value
        domain = parts[0].lstrip(".")
        name = parts[5]
        if "gbs.fm" not in domain:
            continue
        has_gbs_domain = True
        if name == "sessionid":
            has_sessionid = True
        elif name == "csrftoken":
            has_csrftoken = True
    return has_gbs_domain and has_sessionid and has_csrftoken


# ---------- Low-level HTTP helpers ----------

def _open_with_cookies(url: str, cookies: http.cookiejar.MozillaCookieJar,
                      timeout: int = _TIMEOUT_READ):
    """Send GET with cookies; return urlopen response (caller closes via with).

    Raises GbsAuthExpiredError on 302 → /accounts/login/.
    """
    handler = urllib.request.HTTPCookieProcessor(cookies)
    opener = urllib.request.build_opener(handler)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        return opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302) and "/accounts/login/" in (e.headers.get("Location") or ""):
            raise GbsAuthExpiredError(f"Session expired (302→login from {url})") from e
        raise


def _open_no_redirect(url: str, cookies: http.cookiejar.MozillaCookieJar,
                     timeout: int = _TIMEOUT_WRITE):
    """GET that does NOT follow redirects — used for /add/<songid> submit.

    The 302 response is returned directly so caller can read Set-Cookie:
    messages=... before following. RESEARCH Code Example 4.
    """
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **kw):
            return None
    handler_cookie = urllib.request.HTTPCookieProcessor(cookies)
    handler_noredir = _NoRedirect()
    opener = urllib.request.build_opener(handler_cookie, handler_noredir)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    return opener.open(req, timeout=timeout)


# ---------- Capability 1+2: Streams + station metadata ----------

def fetch_streams() -> list[dict]:
    """Returns the 6-tier static list. No HTTP call (RESEARCH §Capability 1)."""
    return [dict(t) for t in _GBS_QUALITY_TIERS]


def fetch_station_metadata() -> dict:
    """Returns a copy of the static metadata dict (name/description/logo_url/homepage)."""
    return dict(GBS_STATION_METADATA)


# ---------- Capability 3: Active playlist ----------

_LINKED_SONGID_RE = re.compile(r'href=[\'"]/song/(\d+)[\'"]', re.IGNORECASE)


def _extract_songid_from_linked(html_str: str) -> Optional[int]:
    m = _LINKED_SONGID_RE.search(html_str or "")
    return int(m.group(1)) if m else None


def fetch_active_playlist(cookies: http.cookiejar.MozillaCookieJar,
                         cursor: Optional[dict] = None) -> dict:
    """GET /ajax with cursor; parse event array; return folded state dict.

    cursor keys (any optional, default 0): position, last_comment, last_removal,
    last_add, now_playing.

    Returns: {now_playing_entryid?, now_playing_songid?, icy_title?,
      linked_metadata_html?, song_length?, song_position?, user_vote=0,
      score="no votes", queue_html_snippets=[], removed_ids=[],
      last_add_entryid?, last_removal_id?, queue_summary?}
    """
    args = dict(cursor or {})
    args.setdefault("position", 0)
    args.setdefault("last_comment", 0)
    args.setdefault("last_removal", 0)
    args.setdefault("last_add", 0)
    args.setdefault("now_playing", 0)
    url = f"{GBS_BASE}/ajax?{urllib.parse.urlencode(args)}"
    with _open_with_cookies(url, cookies, timeout=_TIMEOUT_READ) as resp:
        events = json.loads(resp.read().decode("utf-8"))
    return _fold_ajax_events(events)


def _fold_ajax_events(events: list) -> dict:
    state: dict = {
        "user_vote": 0,
        "score": "no votes",
        "queue_html_snippets": [],
        "removed_ids": [],
    }
    for evt in events:
        if not isinstance(evt, list) or len(evt) < 2:
            continue
        name, payload = evt[0], evt[1]
        if name == "now_playing":
            state["now_playing_entryid"] = payload
        elif name == "metadata":
            state["icy_title"] = payload
        elif name == "linkedMetadata":
            state["linked_metadata_html"] = payload
            sid = _extract_songid_from_linked(payload)
            if sid is not None:
                state["now_playing_songid"] = sid
        elif name == "songLength":
            state["song_length"] = payload
        elif name == "songPosition":
            state["song_position"] = payload
        elif name == "userVote":
            state["user_vote"] = payload
        elif name == "score":
            state["score"] = payload
        elif name == "adds":
            state["queue_html_snippets"].append(payload)
        elif name == "removal":
            if isinstance(payload, dict) and "id" in payload:
                state["removed_ids"].append(payload["id"])
                state["last_removal_id"] = payload["id"]
        elif name == "pllength":
            state["queue_summary"] = (payload or "").strip()
    return state


# ---------- Capability 4: Vote on now-playing ----------

def vote_now_playing(entryid: int, vote: int,
                    cookies: http.cookiejar.MozillaCookieJar) -> dict:
    """Send vote 0..5 for the current entryid; return {user_vote, score}.

    Pitfall 7: caller MUST NOT retry on transient failure — vote is GET
    with side effects.
    """
    if vote not in (0, 1, 2, 3, 4, 5):
        raise ValueError(f"Invalid vote: {vote}")
    args = {"position": 0, "last_comment": 0, "vote": vote, "now_playing": int(entryid)}
    url = f"{GBS_BASE}/ajax?{urllib.parse.urlencode(args)}"
    with _open_with_cookies(url, cookies, timeout=_TIMEOUT_WRITE) as resp:
        events = json.loads(resp.read().decode("utf-8"))
    state = _fold_ajax_events(events)
    return {"user_vote": state.get("user_vote", 0), "score": state.get("score", "no votes")}


# ---------- Capability 5: Search ----------

class _SongRowParser(HTMLParser):
    """Extracts songid + artist + title + duration + add_url from /search HTML.

    Anchors on:
      - <a href='/song/X'>...</a>  → songid + title
      - <a href='/artist/Y'>...</a> → artist
      - <a href='/add/X'>           → add_url (per row)
      - <td>3:08</td>                → duration (text-only td between artist and the add button)
    Ignores <p class="artists"> / <p class="albums"> blocks (D-08e — only song results count).
    """
    _SONG_RE = re.compile(r"^/song/(\d+)$")
    _ADD_RE = re.compile(r"^/add/(\d+)$")
    _ARTIST_RE = re.compile(r"^/artist/(\d+)$")

    def __init__(self):
        super().__init__()
        self._in_songs_table = False
        self._row: Optional[dict] = None
        self._capture: Optional[str] = None
        self._td_text = ""
        self._tds_in_row = 0
        self.results: list[dict] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table" and "songs" in (a.get("class") or ""):
            self._in_songs_table = True
            return
        if not self._in_songs_table:
            return
        if tag == "tr":
            self._row = {}
            self._tds_in_row = 0
            return
        if tag == "td":
            self._td_text = ""
            self._tds_in_row += 1
            return
        if tag == "a" and self._row is not None:
            href = a.get("href", "")
            m_song = self._SONG_RE.match(href)
            m_add = self._ADD_RE.match(href)
            m_artist = self._ARTIST_RE.match(href)
            if m_song:
                self._row["songid"] = int(m_song.group(1))
                self._capture = "title"
            elif m_add:
                self._row["add_url"] = href
            elif m_artist:
                self._capture = "artist"

    def handle_endtag(self, tag):
        if tag == "table" and self._in_songs_table:
            self._in_songs_table = False
            return
        if not self._in_songs_table:
            return
        if tag == "tr" and self._row is not None:
            if "songid" in self._row and "artist" in self._row and "title" in self._row:
                self._row.setdefault("duration", "")
                self._row.setdefault("add_url", f"/add/{self._row['songid']}")
                self.results.append(self._row)
            self._row = None
            self._capture = None
            return
        if tag == "td" and self._row is not None:
            # Heuristic: the third <td> in the row is the duration column.
            if self._tds_in_row == 3 and "duration" not in self._row:
                self._row["duration"] = self._td_text.strip()
        if tag == "a":
            self._capture = None

    def handle_data(self, data):
        if self._capture and self._row is not None:
            self._row[self._capture] = (self._row.get(self._capture, "") + data).strip()
        if self._in_songs_table and self._row is not None:
            self._td_text += data


_PAGE_OF_RE = re.compile(r"page\s+(\d+)\s+of\s+(\d+)", re.IGNORECASE)


def search(query: str, page: int,
          cookies: http.cookiejar.MozillaCookieJar) -> dict:
    """GET /search?query=&page=. Returns {results, page, total_pages}."""
    args = {"query": query, "page": int(page)}
    url = f"{GBS_BASE}/search?{urllib.parse.urlencode(args)}"
    try:
        with _open_with_cookies(url, cookies, timeout=_TIMEOUT_READ) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code in (301, 302) and "/accounts/login/" in (e.headers.get("Location") or ""):
            raise GbsAuthExpiredError(f"Session expired (search 302→login)") from e
        raise

    parser = _SongRowParser()
    try:
        parser.feed(html)
    except Exception as exc:
        # Pitfall 6: parse failure → empty results, log and move on
        _log.warning("search HTML parse failed for query=%r page=%s: %s", query, page, exc)
        return {"results": [], "page": int(page), "total_pages": int(page)}

    total_pages = int(page)
    m = _PAGE_OF_RE.search(html)
    if m:
        try:
            total_pages = int(m.group(2))
        except ValueError:
            total_pages = int(page)
    return {"results": parser.results, "page": int(page), "total_pages": total_pages}


# ---------- Capability 6: Submit ----------

def _decode_django_messages(cookie_value: str) -> list[str]:
    """Decode Django messages cookie → list of message body strings.

    Format: <urlsafe_b64_encoded_json>:<sig>:<sig>. We don't verify the
    signature (we only need the body); we strip everything after the first
    colon and base64url-decode the prefix.
    """
    encoded = (cookie_value or "").split(":", 1)[0]
    if not encoded:
        return []
    encoded += "=" * (-len(encoded) % 4)
    try:
        raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
        parsed = json.loads(raw)
    except Exception:
        return []
    out = []
    for entry in parsed:
        if isinstance(entry, list) and len(entry) >= 4:
            out.append(str(entry[3]))
    return out


def submit(songid: int, cookies: http.cookiejar.MozillaCookieJar) -> str:
    """GET /add/<songid>; intercept 302; decode messages cookie; return text.

    Raises GbsAuthExpiredError if 302 Location is /accounts/login/.
    Returns "" if no messages cookie was set (caller can interpret as success
    with no message OR retry).
    """
    url = f"{GBS_BASE}/add/{int(songid)}"
    resp = _open_no_redirect(url, cookies, timeout=_TIMEOUT_WRITE)
    try:
        location = resp.headers.get("Location") or ""
        if "/accounts/login/" in location:
            raise GbsAuthExpiredError(f"Session expired (submit 302→login)")
        for cookie_line in (resp.headers.get_all("Set-Cookie") or []):
            if cookie_line.startswith("messages="):
                raw_val = cookie_line.split(";", 1)[0].split("=", 1)[1]
                msgs = _decode_django_messages(raw_val)
                return "; ".join(msgs)
        return ""
    finally:
        try:
            resp.close()
        except Exception:
            pass


# ---------- Import orchestrator (D-01, D-02a) ----------

def _download_logo(image_url: str) -> Optional[str]:
    """Download to a temp file; return the temp path or None on failure."""
    try:
        with urllib.request.urlopen(image_url, timeout=_TIMEOUT_WRITE) as resp:
            data = resp.read()
        suffix = os.path.splitext(image_url.split("?")[0])[1] or ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            return tmp.name
    except Exception as exc:
        _log.warning("Failed to download GBS.FM logo: %s", exc)
        return None


def _find_existing_station_id(repo: Repo) -> Optional[int]:
    """Return the station_id of an existing GBS.FM library row, if any.

    Identifier strategy: URL pattern match against any of the 6 stable
    stream URLs (RESEARCH Claude's Discretion — gbs.fm is one station,
    URLs are stable). Walks list_stations rather than adding a new Repo
    method.
    """
    target_urls = {tier["url"] for tier in _GBS_QUALITY_TIERS}
    for st in repo.list_stations():
        if st.provider_name == "GBS.FM":
            return st.id
        # Fallback: cross-check streams in case provider_name was edited.
        for s in repo.list_streams(st.id):
            if s.url in target_urls:
                return st.id
    return None


def import_station(repo: Repo, on_progress=None) -> tuple[int, int]:
    """Idempotent multi-quality import per D-01 / D-02a.

    Returns (inserted, updated). 1+0 on first call, 0+1 on re-import.
    Logo + metadata refresh on every call. Pitfall 4: re-import is
    truncate-and-reset (matches aa_import semantics).
    """
    streams = fetch_streams()
    meta = fetch_station_metadata()
    if on_progress:
        try:
            on_progress("Importing GBS.FM…")
        except Exception:
            pass

    existing_id = _find_existing_station_id(repo)
    first_url = streams[0]["url"]

    if existing_id is None:
        station_id = repo.insert_station(
            name=meta["name"], url=first_url,
            provider_name="GBS.FM", tags="",
        )
        # repo.insert_station auto-creates the first stream (repo.py:407-417).
        # Update it with quality metadata, then insert remaining 5.
        for s in streams:
            if s["url"] == first_url:
                rows = repo.list_streams(station_id)
                if rows:
                    repo.update_stream(
                        rows[0].id, s["url"], "",
                        s["quality"], s["position"],
                        "shoutcast", s["codec"],
                        bitrate_kbps=s["bitrate_kbps"],
                    )
            else:
                repo.insert_stream(
                    station_id, s["url"], label="",
                    quality=s["quality"], position=s["position"],
                    stream_type="shoutcast", codec=s["codec"],
                    bitrate_kbps=s["bitrate_kbps"],
                )
        inserted, updated = 1, 0
    else:
        station_id = existing_id
        # Refresh streams in place: align by URL (URLs are stable per RESEARCH §Capability 1).
        existing_streams = {s.url: s for s in repo.list_streams(station_id)}
        for s in streams:
            if s["url"] in existing_streams:
                row = existing_streams[s["url"]]
                repo.update_stream(
                    row.id, s["url"], row.label or "",
                    s["quality"], s["position"],
                    row.stream_type or "shoutcast", s["codec"],
                    bitrate_kbps=s["bitrate_kbps"],
                )
            else:
                repo.insert_stream(
                    station_id, s["url"], label="",
                    quality=s["quality"], position=s["position"],
                    stream_type="shoutcast", codec=s["codec"],
                    bitrate_kbps=s["bitrate_kbps"],
                )
        inserted, updated = 0, 1

    # Logo download (always re-fetch — catches gbs.fm-side updates)
    tmp_path = _download_logo(meta["logo_url"])
    if tmp_path:
        try:
            art_path = copy_asset_for_station(station_id, tmp_path, "station_art")
            repo.update_station_art(station_id, art_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    return (inserted, updated)
```

**Step C — extend `tests/test_stream_ordering.py`** with `test_gbs_flac_ordering` regression:

Read existing file shape; append at the bottom (do NOT modify existing tests):

```python
# Phase 60 / GBS-01f: regression — FLAC bitrate sentinel sorts FIRST among GBS quality tiers.
def test_gbs_flac_ordering():
    """RESEARCH §Open Question Q1: bitrate_kbps=1411 for FLAC interacts with
    Phase 47.1 D-09 partition logic so FLAC sorts above all MP3 tiers.

    With codec_rank(FLAC)=3 > codec_rank(MP3)=1, FLAC wins regardless of
    bitrate_kbps as long as bitrate_kbps > 0 (otherwise FLAC would be
    partitioned LAST as 'unknown bitrate').
    """
    from musicstreamer.stream_ordering import order_streams
    from musicstreamer.repo import StationStream
    from musicstreamer.gbs_api import _GBS_QUALITY_TIERS
    streams = []
    for i, t in enumerate(_GBS_QUALITY_TIERS, start=1):
        streams.append(StationStream(
            id=i, station_id=1, url=t["url"], label="",
            quality=t["quality"], position=t["position"],
            stream_type="shoutcast", codec=t["codec"],
            bitrate_kbps=t["bitrate_kbps"],
        ))
    ordered = order_streams(streams)
    # FLAC must be first
    assert ordered[0].codec == "FLAC", f"FLAC should sort first; got {ordered[0].codec}"
    assert ordered[0].bitrate_kbps == 1411
    # All FLAC tiers come before all MP3 tiers
    flac_indices = [i for i, s in enumerate(ordered) if s.codec == "FLAC"]
    mp3_indices = [i for i, s in enumerate(ordered) if s.codec == "MP3"]
    assert max(flac_indices) < min(mp3_indices)
    # Among MP3 tiers, highest bitrate wins
    mp3_streams = [s for s in ordered if s.codec == "MP3"]
    assert mp3_streams[0].bitrate_kbps == 320
```

If `StationStream` has different positional args in your repo.py, adjust kwargs accordingly — read repo.py:51-110 for the exact dataclass shape.

Decisions implemented: D-01 (multi-quality), D-01a (stream_ordering compat), D-01b (Repo.insert_stream/update_stream), D-02a (idempotent), D-02d (provider="GBS.FM"), D-03 (module surface), D-03a (urllib + 10s/15s timeouts), D-03b (logo via copy_asset_for_station), D-03c (typed exceptions), D-04 ladder #3 LOCKED (paths.gbs_cookies_path), D-04b (dev fixture not user surface), D-06a RESOLVED (15s polling cadence — implemented in 60-05; gbs_api itself is request-shape-only), D-07b RESOLVED (entryid from /ajax response — vote_now_playing param), D-08c RESOLVED (search auth-required — search() takes cookies), Pitfalls 3, 6, 7, 8, 11.
  </action>
  <verify>
    <automated>python -c "from musicstreamer import gbs_api; assert gbs_api.GBS_BASE == 'https://gbs.fm'; assert len(gbs_api.fetch_streams()) == 6; flac = [t for t in gbs_api.fetch_streams() if t['codec'] == 'FLAC'][0]; assert flac['bitrate_kbps'] == 1411, f'FLAC bitrate {flac[\"bitrate_kbps\"]} != 1411'; assert gbs_api.GbsAuthExpiredError.__bases__[0] is gbs_api.GbsApiError; assert gbs_api._validate_gbs_cookies('# Netscape HTTP Cookie File\n.gbs.fm\tTRUE\t/\tTRUE\t9999999999\tcsrftoken\tx\ngbs.fm\tFALSE\t/\tTRUE\t9999999999\tsessionid\ty\n'); assert not gbs_api._validate_gbs_cookies('.gbs.fm\tTRUE\t/\tTRUE\t9999999999\tcsrftoken\tx\n'); print('OK')" &amp;&amp; python -c "from musicstreamer import paths; assert paths.gbs_cookies_path().endswith('gbs-cookies.txt'); print('OK')" &amp;&amp; grep -q 'def gbs_cookies_path' musicstreamer/paths.py &amp;&amp; grep -c '1411' musicstreamer/gbs_api.py | grep -qE '^[1-9]'</automated>
  </verify>
  <done>
- musicstreamer/gbs_api.py exists, exports all 9 public functions + 2 exception classes
- FLAC tier has bitrate_kbps=1411 (sentinel)
- musicstreamer/paths.py has gbs_cookies_path() returning <root>/gbs-cookies.txt
- _validate_gbs_cookies accepts well-formed Netscape input + rejects missing-sessionid input
- GbsAuthExpiredError subclasses GbsApiError
- Module imports cleanly from a fresh Python process
- tests/test_stream_ordering.py has test_gbs_flac_ordering function
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create tests/test_gbs_api.py covering all 9 public functions + parsers</name>
  <read_first>
    - tests/test_aa_import.py (read top 100 lines — `_urlopen_factory` MagicMock helper at lines 19-30, urlopen-patching pattern at lines 45-48, mock Repo `station_exists_by_url` shape at lines 143/161/175)
    - tests/test_radio_browser.py (skim — pure-urllib mock pattern reference)
    - tests/conftest.py (already extended in 60-01 — uses fake_repo, mock_gbs_api, fake_cookies_jar, gbs_fixtures_dir)
    - .planning/phases/60-gbs-fm-integration/60-PATTERNS.md (read §"tests/test_gbs_api.py" subsection)
    - .planning/phases/60-gbs-fm-integration/60-VALIDATION.md (read §"Per-Task Verification Map" rows mapped to GBS-01a..f — ~20 tests)
    - .planning/phases/60-gbs-fm-integration/60-RESEARCH.md (re-skim §Capability 3-6 for parser-target shapes; §Code Examples for the patterns under test)
    - tests/fixtures/gbs/ (the 15 captured payloads from 60-01 — these tests load them via gbs_fixtures_dir fixture)
  </read_first>
  <behavior>
    GBS-01a (4 tests):
      - test_fetch_streams_returns_six_qualities
      - test_fetch_station_metadata
      - test_import_idempotent (fake_repo: 1st call inserts, 2nd updates in place, station.id stable)
      - test_logo_download (patches urlopen + copy_asset_for_station; asserts update_station_art called)
    GBS-01b (2 tests):
      - test_validate_cookies_accept (loads cookies_valid.txt fixture)
      - test_validate_cookies_reject (loads cookies_invalid_no_sessionid.txt + cookies_invalid_wrong_domain.txt)
    GBS-01c (3 tests):
      - test_fetch_playlist_cold_start (parses ajax_cold_start.json fixture)
      - test_fetch_playlist_steady_state (parses ajax_steady_state.json fixture)
      - test_fetch_playlist_auth_expired (HTTPError(302) with /accounts/login/ Location → GbsAuthExpiredError)
    GBS-01d (1 unit test):
      - test_vote_now_playing_success (parses ajax_vote_set.json fixture; returns {user_vote: 3, score: "..."})
      - test_vote_now_playing_invalid_value (raises ValueError on vote=6)
    GBS-01e (4 tests):
      - test_search_parses_results (loads search_test_p1.html fixture; results list non-empty with songid+artist+title)
      - test_search_pagination (loads search_test_p2.html; total_pages parsed from "page X of Y")
      - test_search_empty (loads search_empty.html; results=[] no exception)
      - test_submit_success_decodes_messages (loads add_redirect_response.txt; decodes messages cookie)
      - test_submit_auth_expired (302 to /accounts/login/ → GbsAuthExpiredError)
      - test_decode_django_messages (load messages_cookie_track_added.txt; returns list with "Track added successfully!")
  </behavior>
  <action>
Create `tests/test_gbs_api.py` (~300 LOC). Use the helper pattern from `tests/test_aa_import.py:19-30` and the `gbs_fixtures_dir` fixture from `tests/conftest.py` (added in 60-01).

```python
"""Phase 60 / GBS-01a..f: gbs_api unit + integration tests.

Fixture sources:
  tests/fixtures/gbs/*.{json,html,txt} — captured in 60-01 via
  scripts/gbs_capture_fixtures.sh (or hand-crafted from RESEARCH §Capability examples).

Pattern: monkey-patch urllib.request.urlopen / opener.open at the gbs_api
module level (mirrors tests/test_aa_import.py:45-48). Real network calls
are forbidden in this test module.
"""
from __future__ import annotations

import http.cookiejar
import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from musicstreamer import gbs_api
from musicstreamer.gbs_api import (
    GbsApiError,
    GbsAuthExpiredError,
    _decode_django_messages,
    _validate_gbs_cookies,
    fetch_active_playlist,
    fetch_station_metadata,
    fetch_streams,
    import_station,
    search,
    submit,
    vote_now_playing,
)


# ---------- helpers ----------

def _urlopen_factory(data: bytes, content_type: str = "application/json", status: int = 200):
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    cm.read = MagicMock(return_value=data)
    cm.status = status
    headers = MagicMock()
    headers.get = MagicMock(side_effect=lambda k, *_: {"Content-Type": content_type}.get(k))
    headers.get_all = MagicMock(return_value=[])
    cm.headers = headers
    cm.close = MagicMock()
    return cm


def _http_error_redirect(location: str = "/accounts/login/?next=/ajax"):
    headers = MagicMock()
    headers.get = MagicMock(return_value=location)
    return urllib.error.HTTPError(url="https://gbs.fm/ajax", code=302, msg="redirect",
                                  hdrs=headers, fp=None)


# ---------- GBS-01a: streams + metadata + import ----------

def test_fetch_streams_returns_six_qualities():
    streams = fetch_streams()
    assert len(streams) == 6
    qualities = {s["quality"] for s in streams}
    assert qualities == {"96", "128", "192", "256", "320", "flac"}
    flac = [s for s in streams if s["quality"] == "flac"][0]
    assert flac["codec"] == "FLAC"
    assert flac["bitrate_kbps"] == 1411  # CD-baseline sentinel (RESEARCH Q1)


def test_fetch_station_metadata():
    meta = fetch_station_metadata()
    assert meta["name"] == "GBS.FM"
    assert meta["logo_url"].startswith("https://gbs.fm/")
    assert meta["logo_url"].endswith(".png")
    assert "homepage" in meta


def test_import_idempotent(fake_repo):
    """First call inserts; second call updates in place; station_id stable."""
    with patch("musicstreamer.gbs_api._download_logo", return_value=None):
        inserted_1, updated_1 = import_station(fake_repo)
    assert (inserted_1, updated_1) == (1, 0)
    stations_1 = fake_repo.list_stations()
    assert len(stations_1) == 1
    sid_1 = stations_1[0].id
    streams_1 = fake_repo.list_streams(sid_1)
    assert len(streams_1) == 6
    qualities_1 = sorted(s.quality for s in streams_1)
    assert qualities_1 == sorted(["96", "128", "192", "256", "320", "flac"])

    with patch("musicstreamer.gbs_api._download_logo", return_value=None):
        inserted_2, updated_2 = import_station(fake_repo)
    assert (inserted_2, updated_2) == (0, 1)
    stations_2 = fake_repo.list_stations()
    assert len(stations_2) == 1
    assert stations_2[0].id == sid_1, "station_id MUST be preserved across re-import"
    streams_2 = fake_repo.list_streams(sid_1)
    assert len(streams_2) == 6


def test_logo_download(fake_repo, monkeypatch):
    """copy_asset_for_station + update_station_art are called when logo fetch succeeds."""
    fake_tmp_path = "/tmp/fake_gbs_logo.png"
    monkeypatch.setattr(gbs_api, "_download_logo", lambda url: fake_tmp_path)
    art_path_holder = {}
    def fake_copy(station_id, src, kind):
        art_path_holder["station_id"] = station_id
        art_path_holder["src"] = src
        art_path_holder["kind"] = kind
        return f"/fake/assets/{station_id}_logo.png"
    monkeypatch.setattr(gbs_api, "copy_asset_for_station", fake_copy)
    monkeypatch.setattr("os.unlink", lambda p: None)
    import_station(fake_repo)
    assert art_path_holder["src"] == fake_tmp_path
    assert art_path_holder["kind"] == "station_art"
    sid = fake_repo.list_stations()[0].id
    assert fake_repo.get_station(sid).station_art_path is not None  # HIGH 1: matches canonical Station.station_art_path attribute


# ---------- GBS-01b: cookie validator ----------

def test_validate_cookies_accept(gbs_fixtures_dir):
    text = (gbs_fixtures_dir / "cookies_valid.txt").read_text()
    assert _validate_gbs_cookies(text) is True


def test_validate_cookies_reject(gbs_fixtures_dir):
    no_session = (gbs_fixtures_dir / "cookies_invalid_no_sessionid.txt").read_text()
    wrong_domain = (gbs_fixtures_dir / "cookies_invalid_wrong_domain.txt").read_text()
    assert _validate_gbs_cookies(no_session) is False
    assert _validate_gbs_cookies(wrong_domain) is False
    assert _validate_gbs_cookies("") is False
    assert _validate_gbs_cookies("# garbage\n") is False


# ---------- GBS-01c: active playlist parser ----------

def test_fetch_playlist_cold_start(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    payload = (gbs_fixtures_dir / "ajax_cold_start.json").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload),
    )
    state = fetch_active_playlist(fake_cookies_jar)
    assert "now_playing_entryid" in state
    assert "icy_title" in state
    assert state["user_vote"] == 0
    assert "score" in state
    # Cold-start fixture has at least one removal event
    assert isinstance(state["removed_ids"], list)


def test_fetch_playlist_steady_state(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    payload = (gbs_fixtures_dir / "ajax_steady_state.json").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload),
    )
    state = fetch_active_playlist(fake_cookies_jar, cursor={"position": 200})
    assert state.get("song_position") is not None or state["score"] != "no votes"


def test_fetch_playlist_auth_expired(fake_cookies_jar, monkeypatch):
    def _raise(url, cookies, timeout=10):
        raise _http_error_redirect()
    monkeypatch.setattr(gbs_api, "_open_with_cookies", _raise)
    with pytest.raises(GbsAuthExpiredError):
        fetch_active_playlist(fake_cookies_jar)


# ---------- GBS-01d: vote_now_playing ----------

def test_vote_now_playing_success(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    payload = (gbs_fixtures_dir / "ajax_vote_set.json").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=15: _urlopen_factory(payload),
    )
    result = vote_now_playing(1810737, 3, fake_cookies_jar)
    assert result["user_vote"] == 3
    assert "score" in result


def test_vote_now_playing_invalid_value(fake_cookies_jar):
    with pytest.raises(ValueError):
        vote_now_playing(123, 6, fake_cookies_jar)
    with pytest.raises(ValueError):
        vote_now_playing(123, -1, fake_cookies_jar)


# ---------- GBS-01e: search + submit ----------

def test_search_parses_results(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    payload = (gbs_fixtures_dir / "search_test_p1.html").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload, content_type="text/html"),
    )
    out = search("test", 1, fake_cookies_jar)
    assert out["page"] == 1
    assert isinstance(out["results"], list)
    assert len(out["results"]) >= 1
    r0 = out["results"][0]
    assert "songid" in r0 and isinstance(r0["songid"], int)
    assert "artist" in r0 and r0["artist"]
    assert "title" in r0 and r0["title"]
    assert r0["add_url"].startswith("/add/")


def test_search_pagination(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    payload = (gbs_fixtures_dir / "search_test_p1.html").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload, content_type="text/html"),
    )
    out = search("test", 1, fake_cookies_jar)
    assert out["total_pages"] >= 1


def test_search_empty(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    payload = (gbs_fixtures_dir / "search_empty.html").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload, content_type="text/html"),
    )
    out = search("zzzzzzzzznoresults", 1, fake_cookies_jar)
    assert out["results"] == []
    assert out["page"] == 1


def test_submit_success_decodes_messages(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    """submit() returns the decoded messages cookie text."""
    raw_response = (gbs_fixtures_dir / "add_redirect_response.txt").read_text()
    # Simulate the 302 response with the messages cookie in Set-Cookie header.
    def fake_open(url, cookies, timeout=15):
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=cm)
        cm.__exit__ = MagicMock(return_value=False)
        # Find Set-Cookie line(s) in the captured response
        cookie_lines = [l for l in raw_response.splitlines()
                       if l.lower().startswith("set-cookie:") and "messages=" in l]
        # Strip the "set-cookie: " prefix
        cookie_values = [l.split(":", 1)[1].strip() for l in cookie_lines]
        location_lines = [l for l in raw_response.splitlines() if l.lower().startswith("location:")]
        location = location_lines[0].split(":", 1)[1].strip() if location_lines else "/playlist"
        headers = MagicMock()
        headers.get = MagicMock(side_effect=lambda k, *_: {"Location": location}.get(k))
        headers.get_all = MagicMock(return_value=cookie_values)
        cm.headers = headers
        cm.close = MagicMock()
        return cm
    monkeypatch.setattr(gbs_api, "_open_no_redirect", fake_open)
    result = submit(88135, fake_cookies_jar)
    # Must decode to "Track added successfully!" or similar non-empty string
    assert result, f"submit returned empty string; expected decoded messages text"
    assert "added" in result.lower() or "track" in result.lower()


def test_submit_auth_expired(fake_cookies_jar, monkeypatch):
    def fake_open(url, cookies, timeout=15):
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=cm)
        cm.__exit__ = MagicMock(return_value=False)
        headers = MagicMock()
        headers.get = MagicMock(return_value="/accounts/login/?next=/add/123")
        headers.get_all = MagicMock(return_value=[])
        cm.headers = headers
        cm.close = MagicMock()
        return cm
    monkeypatch.setattr(gbs_api, "_open_no_redirect", fake_open)
    with pytest.raises(GbsAuthExpiredError):
        submit(123, fake_cookies_jar)


def test_decode_django_messages(gbs_fixtures_dir):
    text = (gbs_fixtures_dir / "messages_cookie_track_added.txt").read_text().strip()
    msgs = _decode_django_messages(text)
    assert len(msgs) >= 1
    assert "added" in msgs[0].lower() or "track" in msgs[0].lower()


def test_decode_django_messages_garbage_returns_empty():
    """Pitfall 8: graceful fallback if decode fails."""
    assert _decode_django_messages("") == []
    assert _decode_django_messages("not-base64") == []
    assert _decode_django_messages("###:::") == []
```

Decisions implemented: VALIDATION.md §Per-Task Verification Map ~20 tests (every GBS-01a..e row in the table matches a test function above). Pitfalls 3 (auth-expired test), 6 (HTML parse failure graceful), 8 (messages decode + graceful empty), 7 (no-retry implicit — single mocked call per test).
  </action>
  <verify>
    <automated>pytest tests/test_gbs_api.py -x -q 2>&amp;1 | tail -20</automated>
  </verify>
  <done>
- tests/test_gbs_api.py exists and ALL tests pass
- Coverage: 6 GBS-01a tests, 2 GBS-01b tests, 3 GBS-01c tests, 2 GBS-01d tests, 5 GBS-01e tests, 1 messages-cookie unit test
- No real HTTP calls (every test patches `_open_with_cookies` or `_open_no_redirect`)
- test_import_idempotent verifies station.id stability across re-import (D-02a)
- test_search_parses_results extracts songid + artist + title + add_url
- test_submit_success_decodes_messages decodes the Django messages cookie
- pytest tests/test_stream_ordering.py::test_gbs_flac_ordering also passes (Wave 0 regression)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MusicStreamer ↔ gbs.fm (HTTPS) | All API calls cross here; gbs.fm returns JSON, HTML, plain text, and redirects. Untrusted input crosses on every call. |
| Filesystem ↔ MozillaCookieJar | Cookies file is a sensitive secret; loaded into memory by gbs_api.load_auth_context. |
| Module ↔ Repo | gbs_api writes to SQLite via Repo (insert_station, insert_stream, update_stream, update_station_art). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-60-05 | Tampering | gbs_api.search HTML parser | mitigate | Anchor on stable selectors (`/song/X`, `/add/X`, `/artist/X` href patterns) per Pitfall 6; parse failures → empty results + log (not exception); fixture-pinned tests catch regressions. Implements RESEARCH §Pitfall 6. |
| T-60-06 | Repudiation | gbs_api submit/vote retry on transient error | mitigate | NO retries on GET-with-side-effects (Pitfall 7). Single-call urllib semantics; failure surfaces to caller immediately. Implements RESEARCH §Pitfall 7. |
| T-60-07 | Information Disclosure | Auth context loading | mitigate | load_auth_context() returns None (not the partial jar) when file missing OR cookie_utils.is_cookie_file_corrupted() detects yt-dlp-style overwrite (Pitfall 999.7 reuse). Module never logs the cookie value. Implements RESEARCH §Pitfall 11 + §Pitfall 3. |
| T-60-08 | Denial of Service | Long-running urlopen calls (network outage) | mitigate | 10s timeout for read endpoints, 15s for write endpoints (D-03a). No silent infinite hangs. Implements D-03a. |
| T-60-09 | Tampering | _decode_django_messages on malformed cookie | mitigate | base64 + JSON decode wrapped in try/except → returns [] on failure (graceful fallback per Assumption A3). Caller can show generic "submit failed" if list is empty. |
| T-60-10 | Spoofing | Auth-expired session silently used | mitigate | 302 → /accounts/login/ raises typed GbsAuthExpiredError; consumer plans translate to AccountsDialog "Not connected" + toast. Implements RESEARCH §Pitfall 3. |
| T-60-11 | Information Disclosure | Logo file ingest into asset directory | accept | _download_logo writes to a tempfile then copy_asset_for_station moves it; logo URL is hard-coded `https://gbs.fm/images/logo_3.png` (no SSRF — URL never user-controlled). |

Citations: Pitfalls 3, 6, 7, 8, 11 from RESEARCH.md.
</threat_model>

<verification>
After both tasks complete, run the focused subset (per VALIDATION.md sampling rate):

```bash
pytest tests/test_gbs_api.py tests/test_stream_ordering.py -x -q

# Then full suite regression
pytest -x

# Module-level smoke: import + listed exports
python -c "from musicstreamer import gbs_api; assert all(hasattr(gbs_api, n) for n in ['fetch_streams', 'fetch_station_metadata', 'import_station', 'fetch_active_playlist', 'vote_now_playing', 'search', 'submit', 'load_auth_context', '_validate_gbs_cookies', '_decode_django_messages', 'GbsApiError', 'GbsAuthExpiredError', 'GBS_BASE'])"
```
</verification>

<success_criteria>
- `musicstreamer/gbs_api.py` exists; module imports cleanly; all public names present
- FLAC sentinel value is exactly `1411` (grep gate confirms)
- `paths.gbs_cookies_path()` returns `<root>/gbs-cookies.txt`
- All ~18 tests in `tests/test_gbs_api.py` pass
- `test_gbs_flac_ordering` regression test passes (FLAC sorts first via stream_ordering)
- Existing `tests/test_stream_ordering.py` tests still pass (no regression)
- Full `pytest -x` runs green (no broken tests elsewhere)
</success_criteria>

<output>
After completion, create `.planning/phases/60-gbs-fm-integration/60-02-SUMMARY.md`
</output>
