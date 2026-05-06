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
    messages=... and Location headers. RESEARCH Code Example 4.

    CPython's urllib chain (HTTPRedirectHandler.http_error_302 →
    redirect_request → None → http_error_default) unconditionally raises
    HTTPError(302) when redirect_request returns None. The fix is to override
    http_error_302 directly to return fp (the raw response file-object), which
    stops the chain at the response and prevents the HTTPError raise.
    See: cpython/Lib/urllib/request.py HTTPDefaultErrorHandler.http_error_default
    and 60-DIAGNOSIS-302-messages.md §2 + §5a.
    """
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        # Override http_error_302 to return fp (the raw response) instead of
        # following the redirect. The former redirect_request-returns-None
        # pattern caused CPython's http_error_default to raise HTTPError(302),
        # which prevented submit() from ever reading the Set-Cookie: messages
        # header (T13 root cause — 60-DIAGNOSIS-302-messages.md §2).
        def http_error_302(self, req, fp, code, msg, headers):
            return fp
        # Belt-and-braces: cover 301/303/307 in case gbs.fm changes its
        # redirect code in the future (diagnosis §6 Open Question 1).
        http_error_301 = http_error_307 = http_error_303 = http_error_302

    handler_cookie = urllib.request.HTTPCookieProcessor(cookies)
    handler_noredir = _NoRedirect()
    opener = urllib.request.build_opener(handler_cookie, handler_noredir)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    return opener.open(req, timeout=timeout)


# ---------- Capability 1+2: Streams + station metadata ----------

def fetch_streams() -> list:
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
        "queue_html_snippets": [],   # RETAINED for backward-compat (rev-2 decision — zero callers)
        "queue_rows": [],             # 60-10 / T8: parsed upcoming queue rows (list[dict])
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
            state["queue_html_snippets"].append(payload)   # RETAINED (rev-2)
            state["queue_rows"].extend(_parse_adds_html(payload))  # 60-10 / T8
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
    """Anchors on <table class='songs'>; collects <tr> rows.

    Phase 60-11 added _ArtistAlbumParser to extract <p class="artists"> / <p class="albums">
    blocks separately. _SongRowParser handles only the songs table; the artist/album panel
    population happens via _parse_artist_album_html (separate pass over the same HTML).
    Each row produces dict: {songid, artist, title, duration, add_url}.
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
        self.results: list = []

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


class _QueueRowParser(HTMLParser):
    """Parse `adds` event HTML — one or more <tr> rows describing the upcoming queue.

    Skips rows with class containing 'playing' (now-playing, rendered separately via
    icy_title) and class containing 'history' (already played). Returns one dict per
    upcoming row.

    Per-row dict keys: entryid (int), songid (int|None), artist (str), title (str),
    duration (str).

    Reference: 60-DIAGNOSIS-playlist-enumeration.md §5a.
    Mitigates: T-60-10-02 (parser misidentifies rows), T-60-10-04 (malformed HTML).
    """

    _SONG_RE = re.compile(r"^/song/(\d+)$")
    _ARTIST_RE = re.compile(r"^/artist/(\d+)$")

    def __init__(self):
        super().__init__()
        self.rows: list = []
        self._current: Optional[dict] = None
        self._skip_current: bool = False
        self._in_artistry_td: bool = False
        self._in_time_td: bool = False
        self._in_song_anchor: bool = False
        self._in_artist_anchor: bool = False

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag == "tr":
            row_class = (ad.get("class") or "")
            row_id = ad.get("id") or ""
            # T-60-10-02: skip playing/history rows — they are NOT upcoming.
            self._skip_current = ("playing" in row_class) or ("history" in row_class)
            if not self._skip_current and row_id:
                try:
                    entryid = int(row_id)
                except ValueError:
                    self._skip_current = True
                    return
                self._current = {
                    "entryid": entryid,
                    "songid": None,
                    "artist": "",
                    "title": "",
                    "duration": "",
                }
            else:
                self._current = None
        elif self._current and tag == "td":
            td_class = ad.get("class") or ""
            self._in_artistry_td = "artistry" in td_class
            self._in_time_td = "time" in td_class
        elif self._current and tag == "a":
            href = ad.get("href") or ""
            m_song = self._SONG_RE.match(href)
            m_artist = self._ARTIST_RE.match(href)
            if m_song:
                self._current["songid"] = int(m_song.group(1))
                self._in_song_anchor = True
            elif m_artist:
                self._in_artist_anchor = True

    def handle_endtag(self, tag):
        if tag == "tr":
            if self._current is not None and not self._skip_current:
                self.rows.append(self._current)
            self._current = None
            self._skip_current = False
            self._in_artistry_td = False
            self._in_time_td = False
            self._in_song_anchor = False
            self._in_artist_anchor = False
        elif tag == "td":
            self._in_artistry_td = False
            self._in_time_td = False
        elif tag == "a":
            self._in_song_anchor = False
            self._in_artist_anchor = False

    def handle_data(self, data):
        if not self._current or self._skip_current:
            return
        txt = data.strip()
        if not txt:
            return
        if self._in_artist_anchor and self._in_artistry_td:
            self._current["artist"] = txt
        elif self._in_song_anchor:
            self._current["title"] = txt
        elif self._in_time_td:
            self._current["duration"] = txt


def _parse_adds_html(html_str: str) -> list:
    """Parse `adds` event HTML and return a list of upcoming queue row dicts.

    Each dict has keys: entryid (int), songid (int|None), artist (str),
    title (str), duration (str).

    Pitfall 6 / T-60-10-04: defensive — bad HTML returns empty list, never raises.
    Reference: 60-DIAGNOSIS-playlist-enumeration.md §5a.
    """
    parser = _QueueRowParser()
    try:
        parser.feed(html_str or "")
        parser.close()
    except Exception:
        return []  # Pitfall 6: bad HTML → empty, never raises
    return parser.rows


class _ArtistAlbumParser(HTMLParser):
    """Extract `<p class="artists">` blocks above the songs table.

    gbs.fm reuses class="artists" for BOTH the Artist and Album blocks
    (diagnosis §2a). The block's category is determined by the leading
    text node — "Artists:" vs "Albums:".

    Each block contains <li><a href="/artist/N">name</a></li> entries
    (or /album/N for the album block).

    Mitigates T-60-11-01 (HTML injection): stores plain str from handle_data;
    URL stored separately in dict, not rendered. T-60-11-02 (off-host hrefs):
    hrefs are stored as-is; click handler (Shape 4) uses item.text() not href.
    """

    def __init__(self):
        super().__init__()
        self.artist_links: list = []
        self.album_links: list = []
        self._in_artists_p: bool = False
        self._current_block: Optional[str] = None  # "artists" | "albums" | None
        self._pending_anchor_url: Optional[str] = None
        self._collect_anchor_text: bool = False

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag == "p" and "artists" in (ad.get("class") or ""):
            self._in_artists_p = True
            self._current_block = None  # decided by next non-empty data node
        elif self._in_artists_p and tag == "a":
            self._pending_anchor_url = ad.get("href") or ""
            self._collect_anchor_text = True

    def handle_endtag(self, tag):
        if tag == "p" and self._in_artists_p:
            self._in_artists_p = False
            self._current_block = None
        elif tag == "a":
            self._collect_anchor_text = False
            self._pending_anchor_url = None

    def handle_data(self, data):
        if not self._in_artists_p:
            return
        txt = data.strip()
        if not txt:
            return
        # First non-empty data node decides the block category.
        if self._current_block is None:
            lower = txt.lower()
            if lower.startswith("artists"):
                self._current_block = "artists"
            elif lower.startswith("albums"):
                self._current_block = "albums"
            return
        # Inside an anchor: collect the text + href pair.
        if self._collect_anchor_text and self._pending_anchor_url is not None:
            target = (self.artist_links if self._current_block == "artists"
                      else self.album_links)
            target.append({"text": txt, "url": self._pending_anchor_url})
            self._collect_anchor_text = False  # one text node per anchor


def _parse_artist_album_html(html_str: str) -> tuple:
    """Parse search HTML and return (artist_links, album_links) lists.

    Each list contains dicts with keys: text (str), url (str).
    Returns ([], []) on parse error or no matches.

    Defensive: never raises — Pitfall 6 applies here too.
    """
    parser = _ArtistAlbumParser()
    try:
        parser.feed(html_str or "")
        parser.close()
    except Exception:
        return ([], [])
    return (parser.artist_links, parser.album_links)


class _ArtistPageParser(HTMLParser):
    """Phase 60.1 / GBS-01e drill-down: parse /artist/<id> page.

    Anchors on <table class="artist"> inside the dialog's drill-down flow.
    Skips <tr class="albumTitle"> separator rows (they group the artist's
    catalog by album — RESEARCH §Pitfall 5) and <th>-only header rows.

    Captures the page-title artist name from <th class='album' colspan='3'>
    ONCE on first encounter, then re-emits per-row in the {songid, artist,
    title, duration, add_url} shape so _render_results() works unchanged.

    Defensive: HTML parse errors are caught by fetch_artist_songs's wrapper
    (Pitfall 6 idiom), NOT by this class.
    """

    _SONG_RE = re.compile(r"^/song/(\d+)$")
    _ADD_RE = re.compile(r"^/add/(\d+)$")

    def __init__(self):
        super().__init__()
        self.results: list = []
        self._artist_name: str = ""        # page-title artist, captured once
        self._page_title_seen: bool = False
        self._in_artist_table: bool = False
        self._row: Optional[dict] = None
        self._capture: Optional[str] = None  # "page_title" | "title" | "duration" | None
        self._td_text: str = ""
        self._tds_in_row: int = 0
        self._ths_in_row: int = 0
        self._skip_current: bool = False

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag == "table" and "artist" in (ad.get("class") or ""):
            self._in_artist_table = True
            return
        if not self._in_artist_table:
            return
        if tag == "tr":
            self._row = {"songid": None, "title": "", "duration": "", "add_url": ""}
            self._tds_in_row = 0
            self._ths_in_row = 0
            self._capture = None
            self._td_text = ""
            row_class = ad.get("class") or ""
            self._skip_current = "albumTitle" in row_class
            return
        if self._skip_current:
            # albumTitle rows are skipped entirely — no inner-tag handling.
            return
        if tag == "th":
            self._ths_in_row += 1
            # Page-title capture: <th class='album' colspan='3'>Testament</th>
            # Triggers ONCE on first encounter (covered by self._page_title_seen guard).
            if not self._page_title_seen and "album" in (ad.get("class") or ""):
                self._capture = "page_title"
            return
        if tag == "td":
            self._td_text = ""
            self._tds_in_row += 1
            # Position-based capture: 1 → title (filled by anchor), 2 → duration text, 3 → add anchor
            if self._tds_in_row == 1:
                self._capture = None  # filled by <a href="/song/N"> anchor
            elif self._tds_in_row == 2:
                self._capture = "duration"
            else:
                self._capture = None
            return
        if tag == "a" and self._row is not None:
            href = ad.get("href", "")
            m_song = self._SONG_RE.match(href)
            m_add = self._ADD_RE.match(href)
            if m_song:
                self._row["songid"] = int(m_song.group(1))
                self._capture = "title"
            elif m_add:
                self._row["add_url"] = href

    def handle_data(self, data):
        if not self._in_artist_table:
            return
        if self._capture == "page_title" and not self._page_title_seen:
            self._artist_name += data
            return
        if self._skip_current:
            return
        if self._capture == "title" and self._row is not None:
            self._row["title"] += data
            return
        if self._capture == "duration" and self._row is not None:
            self._row["duration"] += data

    def handle_endtag(self, tag):
        if tag == "th" and self._capture == "page_title":
            # Close the page-title capture window after the </th>
            self._artist_name = self._artist_name.strip()
            self._page_title_seen = True
            self._capture = None
            return
        if tag == "a" and self._capture == "title":
            # Stop title capture at end of song anchor
            self._capture = None
            return
        if tag == "tr":
            # Commit the row if it looks like a real song row
            if (self._row is not None
                    and not self._skip_current
                    and self._row.get("songid") is not None
                    and self._tds_in_row >= 2):
                self._row["artist"] = self._artist_name or "(unknown)"
                self._row["title"] = (self._row.get("title") or "").strip()
                self._row["duration"] = (self._row.get("duration") or "").strip()
                self._row["add_url"] = self._row.get("add_url") or f"/add/{self._row['songid']}"
                self.results.append(self._row)
            self._row = None
            self._skip_current = False
            self._tds_in_row = 0
            self._ths_in_row = 0
            self._capture = None
            return
        if tag == "table" and self._in_artist_table:
            self._in_artist_table = False


class _AlbumPageParser(HTMLParser):
    """Phase 60.1 / GBS-01e drill-down: parse /album/<id> page.

    D-02 belt-and-suspenders gate: locks onto the FIRST <table width="620">
    inside <div class="playlist"> AND explicitly REJECTS class="artist" or
    class="songs". Without these explicit rejections, a router bug feeding
    an artist page or search response into _AlbumPageParser would silently
    produce garbage rows.

    Row shape (RESEARCH §Pitfall 6, 6 columns):
      td 0: <a href="/artist/Y">{artist_name}</a>   — per-row artist
      td 1: <a href="/song/X">{title}</a>           — per-row title + songid
      td 2: codec (e.g., "mp3") — skipped
      td 3: bitrate (e.g., "192") — skipped
      td 4: duration "M:SS"
      td 5: <a class="boxed add" href="/add/X">Add!</a>

    Output dict shape matches _SongRowParser / _ArtistPageParser:
      {"songid": int, "artist": str, "title": str, "duration": str, "add_url": str}

    Defensive: HTML parse errors are caught by fetch_album_songs's wrapper.
    """

    _SONG_RE = re.compile(r"^/song/(\d+)$")
    _ADD_RE = re.compile(r"^/add/(\d+)$")
    _ARTIST_RE = re.compile(r"^/artist/(\d+)$")

    def __init__(self):
        super().__init__()
        self.results: list = []
        self._in_playlist_div: bool = False
        self._in_album_table: bool = False
        self._table_locked: bool = False
        self._row: Optional[dict] = None
        self._capture: Optional[str] = None  # "artist" | "title" | "duration" | None
        self._tds_in_row: int = 0
        self._skip_current: bool = False

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag == "div" and "playlist" in (ad.get("class") or ""):
            self._in_playlist_div = True
            return
        if not self._in_playlist_div:
            return
        if not self._in_album_table:
            if self._table_locked:
                return
            if tag == "table" and ad.get("width") == "620":
                cls = ad.get("class") or ""
                # D-02 belt-and-suspenders: explicitly reject artist-page and search-response
                # tables. Both have width="620" inside <div class="playlist"> too.
                if "artist" in cls or "songs" in cls:
                    return
                self._in_album_table = True
                self._table_locked = True
            return
        # Inside album table:
        if tag == "tr":
            self._row = {"songid": None, "artist": "", "title": "", "duration": "", "add_url": ""}
            self._tds_in_row = 0
            self._capture = None
            self._skip_current = False
            return
        if tag == "th":
            # Header row — mark current row to skip
            self._skip_current = True
            return
        if self._skip_current:
            return
        if tag == "td":
            self._tds_in_row += 1
            # Position-based capture pre-set: duration is td 5 (1-indexed)
            if self._tds_in_row == 5:
                self._capture = "duration"
            else:
                self._capture = None
            return
        if tag == "a" and self._row is not None:
            href = ad.get("href", "")
            m_artist = self._ARTIST_RE.match(href)
            m_song = self._SONG_RE.match(href)
            m_add = self._ADD_RE.match(href)
            if m_artist and self._tds_in_row == 1:
                self._capture = "artist"
            elif m_song:
                self._row["songid"] = int(m_song.group(1))
                self._capture = "title"
            elif m_add:
                self._row["add_url"] = href
                # No text capture — add_url is the entire payload from this anchor

    def handle_data(self, data):
        if not (self._in_album_table and self._row is not None and not self._skip_current):
            return
        if self._capture == "artist":
            self._row["artist"] += data
            return
        if self._capture == "title":
            self._row["title"] += data
            return
        if self._capture == "duration":
            self._row["duration"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self._capture in ("artist", "title"):
            self._capture = None
            return
        if tag == "td" and self._capture == "duration":
            self._capture = None
            return
        if tag == "tr":
            if (self._row is not None
                    and not self._skip_current
                    and self._row.get("songid") is not None
                    and self._tds_in_row >= 5):
                self._row["artist"] = (self._row.get("artist") or "").strip()
                self._row["title"] = (self._row.get("title") or "").strip()
                self._row["duration"] = (self._row.get("duration") or "").strip()
                if not self._row.get("add_url"):
                    self._row["add_url"] = f"/add/{self._row['songid']}"
                self.results.append(self._row)
            self._row = None
            self._tds_in_row = 0
            self._skip_current = False
            self._capture = None
            return
        if tag == "table" and self._in_album_table:
            self._in_album_table = False


_PAGE_OF_RE = re.compile(r"page\s+(\d+)\s+of\s+(\d+)", re.IGNORECASE)


def search(query: str, page: int,
          cookies: http.cookiejar.MozillaCookieJar) -> dict:
    """GET /search?query=&page=. Returns {results, page, total_pages, artist_links, album_links}.

    60-11 / T12: artist_links and album_links are new keys ([] on page 2+ or no matches).
    Backward-compatible: existing callers that only read results/page/total_pages are unaffected.
    """
    args = {"query": query, "page": int(page)}
    url = f"{GBS_BASE}/search?{urllib.parse.urlencode(args)}"
    try:
        with _open_with_cookies(url, cookies, timeout=_TIMEOUT_READ) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code in (301, 302) and "/accounts/login/" in (e.headers.get("Location") or ""):
            raise GbsAuthExpiredError(f"Session expired (search 302→login)") from e
        raise

    # 60-11 / T12: parse artist/album blocks BEFORE song rows (same HTML, different parser).
    # _parse_artist_album_html is defensive — returns ([], []) on any parse error.
    artist_links, album_links = _parse_artist_album_html(html)

    parser = _SongRowParser()
    try:
        parser.feed(html)
    except Exception as exc:
        # Pitfall 6: parse failure → empty results, log and move on
        _log.warning("search HTML parse failed for query=%r page=%s: %s", query, page, exc)
        return {"results": [], "page": int(page), "total_pages": int(page),
                "artist_links": artist_links, "album_links": album_links}

    total_pages = int(page)
    m = _PAGE_OF_RE.search(html)
    if m:
        try:
            total_pages = int(m.group(2))
        except ValueError:
            total_pages = int(page)
    return {
        "results": parser.results,
        "page": int(page),
        "total_pages": total_pages,
        "artist_links": artist_links,   # 60-11 / T12: [] on page 2+ or no matches
        "album_links": album_links,     # 60-11 / T12: [] on page 2+ or no matches
    }


def fetch_artist_songs(artist_id: int,
                       cookies: http.cookiejar.MozillaCookieJar) -> dict:
    """Phase 60.1 / GBS-01e: GET /artist/<id>; parse with _ArtistPageParser.

    Defensive: parse failure → {"results": []}, never raises (except auth-expired).
    Mirrors search() shape — HTTPError 302→login bubbles up as GbsAuthExpiredError.
    """
    url = f"{GBS_BASE}/artist/{int(artist_id)}"
    try:
        with _open_with_cookies(url, cookies, timeout=_TIMEOUT_READ) as resp:
            html_str = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code in (301, 302) and "/accounts/login/" in (e.headers.get("Location") or ""):
            raise GbsAuthExpiredError(f"Session expired (artist 302→login from {url})") from e
        raise
    parser = _ArtistPageParser()
    try:
        parser.feed(html_str)
        parser.close()
    except Exception as exc:
        _log.warning("artist HTML parse failed for id=%s: %s", artist_id, exc)
        return {"results": []}
    return {"results": parser.results}


def fetch_album_songs(album_id: int,
                      cookies: http.cookiejar.MozillaCookieJar) -> dict:
    """Phase 60.1 / GBS-01e: GET /album/<id>; parse with _AlbumPageParser.

    Defensive: parse failure → {"results": []}, never raises (except auth-expired).
    """
    url = f"{GBS_BASE}/album/{int(album_id)}"
    try:
        with _open_with_cookies(url, cookies, timeout=_TIMEOUT_READ) as resp:
            html_str = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code in (301, 302) and "/accounts/login/" in (e.headers.get("Location") or ""):
            raise GbsAuthExpiredError(f"Session expired (album 302→login from {url})") from e
        raise
    parser = _AlbumPageParser()
    try:
        parser.feed(html_str)
        parser.close()
    except Exception as exc:
        _log.warning("album HTML parse failed for id=%s: %s", album_id, exc)
        return {"results": []}
    return {"results": parser.results}


# ---------- Capability 6: Submit ----------

def _decode_django_messages(cookie_value: str) -> list:
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


def import_station(repo: Repo, on_progress=None) -> tuple:
    """Idempotent multi-quality import per D-01 / D-02a.

    Returns (inserted, updated).
      (1, 0)  — first call; GBS.FM station not yet in library
      (0, 1)  — re-import with at least one stream field changed
      (0, 0)  — re-import with no field changes (idempotent no-op)

    Logo + metadata refresh on every call. Pitfall 4: re-import is
    truncate-and-reset (matches aa_import semantics).

    Field-level dirty-check (T6 fix, 60-DIAGNOSIS-302-messages.md §3):
    The update path now compares (url, quality, position, codec, bitrate_kbps)
    for each existing stream against the canonical tier list. repo.update_stream
    is always called (keeps SQLite WAL consistent), but the return value only
    counts as updated=1 when at least one field actually changed.
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
        # Field-level dirty flag: True if ANY stream field changed (T6 fix).
        # repo.update_stream is still called unconditionally to keep SQLite WAL
        # consistent (T-60-08-04 threat mitigation). Only the return tuple changes.
        any_field_changed = False
        for s in streams:
            if s["url"] in existing_streams:
                row = existing_streams[s["url"]]
                # Compare the 5 canonical fields (label/stream_type excluded —
                # those aren't part of the canonical tier list and may carry
                # user edits or default values).
                target = (s["url"], s["quality"], s["position"],
                          s["codec"], int(s["bitrate_kbps"]))
                existing = (row.url, row.quality, row.position,
                            row.codec, int(row.bitrate_kbps or 0))
                if target != existing:
                    any_field_changed = True
                repo.update_stream(
                    row.id, s["url"], row.label or "",
                    s["quality"], s["position"],
                    row.stream_type or "shoutcast", s["codec"],
                    bitrate_kbps=s["bitrate_kbps"],
                )
            else:
                # New tier URL not previously in library — counts as a change.
                any_field_changed = True
                repo.insert_stream(
                    station_id, s["url"], label="",
                    quality=s["quality"], position=s["position"],
                    stream_type="shoutcast", codec=s["codec"],
                    bitrate_kbps=s["bitrate_kbps"],
                )
        inserted, updated = 0, (1 if any_field_changed else 0)

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
