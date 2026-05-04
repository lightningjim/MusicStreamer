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
