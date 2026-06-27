"""
YouTube playlist import backend.

Public API:
  is_yt_playlist_url(url) -> bool
  scan_playlist(url) -> list[dict]   # [{"title", "url", "provider"}, ...]
  import_stations(entries, repo, on_progress=None) -> (imported: int, skipped: int)
  fetch_channel_avatar(channel_url) -> bytes
  register_avatar_fetcher(provider, fetcher) -> None
  get_avatar_fetcher(provider) -> Optional[Callable[[str], bytes]]
  resolve_live_title(url) -> str     # per-video title fetch for blank flat-scan entries (D-01)

Internal helpers: _is_blank_title (D-01 predicate), _fallback_title (D-03 fallback).

Uses the yt_dlp Python library API directly (PORT-09 / D-17). No subprocess.
"""
import logging
import os
import re
import urllib.request
from typing import Callable, Optional

import yt_dlp

from musicstreamer import constants, cookie_utils, paths, yt_dlp_opts
from musicstreamer.runtime_check import NodeRuntime

_log = logging.getLogger(__name__)


def is_yt_playlist_url(url: str) -> bool:
    """Return True if url looks like a scannable YouTube playlist or channel tab."""
    return bool(
        re.search(r"youtube\.com/playlist\?.*list=", url)
        or re.search(r"youtube\.com/@[^/]+/(streams|live|videos)", url)
    )


# Patterns used exclusively by normalize_yt_channel_scan_url — broader than
# is_yt_playlist_url: accepts bare channel handles and normalizes to /streams.
_YT_NORM_PLAYLIST_RE = re.compile(r"youtube\.com/playlist\?.*list=", re.IGNORECASE)
_YT_NORM_TABBED_RE = re.compile(
    r"^https?://(?:www\.)?youtube\.com/"
    r"(?:@[^/?#]+|channel/[^/?#]+|c/[^/?#]+|user/[^/?#]+)"
    r"/(streams|live|videos|featured)"
    r"(?:[/?#].*)?$",
    re.IGNORECASE,
)
_YT_NORM_BARE_RE = re.compile(
    r"^(https?://(?:www\.)?youtube\.com/"
    r"(?:@[^/?#]+|channel/[^/?#]+|c/[^/?#]+|user/[^/?#]+))"
    r"/?$",
    re.IGNORECASE,
)


def normalize_yt_channel_scan_url(url: str) -> "str | None":
    """Return a normalized YouTube channel/playlist URL for the live-resync scanner.

    Accepts a broader set of URL forms than is_yt_playlist_url and normalizes
    bare channel handles/IDs to the /streams tab.  The live-resync scanner uses
    the /streams tab to surface live and upcoming streams via the
    ``duration is None`` heuristic (MEMORY.md: yt-streams-tab-flat-scan).

    Accepted inputs and their normalized output:

    - youtube.com/@handle           → same URL + /streams appended
    - youtube.com/channel/UCxxx     → same URL + /streams appended
    - youtube.com/c/Name            → same URL + /streams appended
    - youtube.com/user/Name         → same URL + /streams appended
    - youtube.com/@handle/streams   → unchanged (already tabbed)
    - youtube.com/@handle/live      → unchanged (already tabbed)
    - youtube.com/@handle/videos    → unchanged (already tabbed)
    - youtube.com/playlist?list=PL  → unchanged (playlist)

    http:// and https://, with or without www., are accepted.
    Non-YouTube URLs, watch URLs, and /about tabs return None.

    Distinct from is_yt_playlist_url: that function validates import-dialog
    entries and deliberately rejects bare handles (no /streams suffix).  This
    function is for the save path of the channel-scan-URL field where users
    paste bare channel links and the normalization ensures downstream
    scan_playlist always receives a /streams-tab URL.
    """
    url = url.strip()
    if not url:
        return None
    if _YT_NORM_PLAYLIST_RE.search(url):
        return url
    if _YT_NORM_TABBED_RE.match(url):
        return url
    m = _YT_NORM_BARE_RE.match(url)
    if m:
        # Append /streams to the captured prefix (trailing slash already stripped
        # by the regex anchor — the bare pattern requires no path component after
        # the channel identifier).
        return m.group(1) + "/streams"
    return None


def _entry_is_live(entry: dict) -> bool:
    """RESEARCH.md Pitfall 1 — extract_flat may leave is_live as None for sparse
    entries. Prefer live_status, fall back to is_live.

    Phase 96: extract_flat='in_playlist' on a channel ``/streams`` tab leaves
    BOTH ``live_status`` and ``is_live`` as None for *every* entry, so the
    explicit-status checks can never fire and a channel scan would return zero
    currently-live streams. When no explicit signal is present, fall back to
    ``duration``: a finished VOD always carries a concrete duration, whereas a
    currently-live or scheduled stream has ``duration=None``. Upcoming streams
    also lack a duration and are intentionally included as candidates — the
    refresh dialog is manual review-and-confirm (D-05..D-10), and distinguishing
    live-now from scheduled requires fragile per-video resolution.
    """
    status = entry.get("live_status")
    if status == "is_live":
        return True
    if status in ("was_live", "not_live", "post_live"):
        return False
    if entry.get("is_live") is True:
        return True
    # Flat channel-tab fallback: no explicit live signal at all. Treat an entry
    # with no duration as a live/upcoming stream; a real duration means a VOD.
    if status is None and entry.get("is_live") is None:
        return entry.get("duration") is None
    return False


# ---------------------------------------------------------------------------
# D-01 blank-title predicate + D-03 fallback helper
# ---------------------------------------------------------------------------

_BLANK_TITLES: frozenset[str] = frozenset({"", "untitled"})


def _is_blank_title(title: str) -> bool:
    """Return True when a flat-scan title needs per-video resolution (D-01).

    Matches the empty string, whitespace-only strings, and any case variant of
    "Untitled" — the placeholder scan_playlist injects when yt-dlp returns no
    title for a live entry (line below: entry.get("title", "Untitled")).
    """
    return not title or title.strip().lower() in _BLANK_TITLES


def _fallback_title(url: str) -> str:
    """Return the D-03 fallback title string for a YouTube watch URL.

    Derives the video ID via ``urllib.parse`` (function-local import to keep
    the module-level import list unchanged). Returns "Untitled — watch?v=<id>"
    when a ``v=`` query param exists, else "Untitled — <url>".
    Uses the em dash character (U+2014) to match D-03 wording exactly.
    """
    import urllib.parse as _urlparse  # function-local; urllib.request already imported above

    parsed = _urlparse.urlparse(url)
    params = _urlparse.parse_qs(parsed.query)
    video_ids = params.get("v")
    if video_ids:
        return f"Untitled — watch?v={video_ids[0]}"
    return f"Untitled — {url}"


def scan_playlist(
    url: str,
    toast_callback: Optional[Callable[[str], None]] = None,
    *,
    node_runtime: "NodeRuntime | None" = None,
) -> list[dict]:
    """Scan a YouTube playlist/channel tab and return currently-live entries.

    Each returned dict has keys: "title", "url", "provider".
    Raises ValueError for private/unavailable playlists.
    Raises RuntimeError on other yt-dlp failures.

    Phase 999.7: cookies.txt is routed through ``cookie_utils.temp_cookies_copy``
    so yt-dlp's save_cookies() side effect on ``__exit__`` never touches the
    canonical file. If the canonical file is already corrupted (yt-dlp marker
    header from a previous unprotected call), it is auto-cleared and the
    optional ``toast_callback`` is invoked.
    """
    # Phase 999.7 corruption check — MUST run BEFORE building opts.
    canonical = paths.cookies_path()
    if os.path.exists(canonical) and cookie_utils.is_cookie_file_corrupted(canonical):
        constants.clear_cookies()
        if toast_callback is not None:
            toast_callback("YouTube cookies cleared — re-import via Accounts menu.")

    node_path = node_runtime.path if node_runtime else None
    _log.info("youtube scan: node_path=%s", node_path)

    opts = {
        "extract_flat": "in_playlist",
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        # Phase 79 / BUG-11: thread the resolved Node executable path through to
        # yt-dlp so .desktop-stripped PATH launches don't fail JS-requiring scans.
        # Single source of truth shared with player._youtube_resolve_worker.
        # Note: extract_flat='in_playlist' short-circuits per-entry JS solving
        # today (yt_dlp/YoutubeDL.py:1894-1909) so this is defensive parity for
        # the helper invariant (D-10), not a live-bug fix on the scan path.
        "js_runtimes": yt_dlp_opts.build_js_runtimes(node_runtime),
        # BUG-YT-COOKIES: yt-dlp 2026.03.17+ requires the EJS remote component
        # when YouTube account cookies are detected (authenticated code path).
        # Same fix as player.py::_youtube_resolve_worker.
        "remote_components": {"ejs:github"},
    }

    # Phase 999.7 Pitfall 1: yt_dlp.YoutubeDL MUST nest INSIDE temp_cookies_copy
    # so yt-dlp's save_cookies() on __exit__ writes to the temp path, not
    # canonical. Unlinking the temp after yt-dlp closes is handled by the
    # context manager's finally.
    with cookie_utils.temp_cookies_copy() as cookiefile:
        if cookiefile is not None:
            opts["cookiefile"] = cookiefile
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as e:
            msg = str(e).lower()
            if "private" in msg or "unavailable" in msg or "not accessible" in msg:
                raise ValueError("Playlist Not Accessible") from e
            raise RuntimeError(str(e)) from e

    entries = (info or {}).get("entries") or []
    results: list[dict] = []
    for entry in entries:
        if entry is None:
            continue
        if not _entry_is_live(entry):
            continue
        results.append(
            {
                "title": entry.get("title", "Untitled"),
                "url": entry.get("url") or entry.get("webpage_url"),
                "provider": entry.get("playlist_channel")
                or entry.get("playlist_uploader")
                or entry.get("uploader", ""),
            }
        )
    return results


def import_stations(entries: list[dict], repo, on_progress=None) -> tuple[int, int]:
    """Import a list of entries into the station library via repo.

    Skips entries whose URL already exists (repo.station_exists_by_url).
    Calls on_progress(imported, skipped) after each entry if provided.

    Returns (imported_count, skipped_count).
    """
    imported = 0
    skipped = 0
    for entry in entries:
        url = entry["url"]
        if repo.station_exists_by_url(url):
            skipped += 1
        else:
            repo.insert_station(
                name=entry["title"],
                url=url,
                provider_name=entry["provider"],
                tags="",
            )
            imported += 1
        if on_progress:
            on_progress(imported, skipped)
    return imported, skipped


def fetch_channel_avatar(
    channel_url: str,
    *,
    node_runtime: "NodeRuntime | None" = None,
) -> bytes:
    """Fetch the channel avatar image for a YouTube channel URL.

    Accepts both channel URLs (e.g. https://www.youtube.com/@LofiGirl) and
    video URLs (e.g. https://www.youtube.com/watch?v=...). For video URLs a
    two-step resolution is performed: the channel_url is extracted from the
    video info dict, then avatar extraction runs on the channel URL.

    Selects the ``avatar_uncropped`` thumbnail (preferred) or ``avatar`` (belt-
    and-suspenders fallback; never matches in current yt-dlp — see RESEARCH.md
    Pitfall 1). Rejects entries where BOTH width and height are present and
    unequal (null-safe: ``None != None`` is False, so uncropped entries with no
    dimensions are never rejected — see RESEARCH.md Pitfall 2).

    Downloads the avatar bytes via urllib.request with a 10-second timeout.
    Runs on a worker thread (Plan 05); must NOT touch any Qt widget.

    Thread safety: cookie_utils.temp_cookies_copy() is used (same as
    scan_playlist) so yt-dlp's save_cookies() on __exit__ writes to a temp
    copy, never the canonical cookies file (T-89-05).

    node_runtime: when supplied, its absolute node path is threaded into
    build_js_runtimes so GNOME .desktop launchers (which strip the shell
    PATH) can resolve the JS runtime needed for the EarlyJS/ejs:github
    challenge. Mirrors the identical fix applied to scan_playlist and
    player._youtube_resolve_worker (BUG-11 / D-02).

    Raises:
        ValueError: No avatar entry found, or avatar entry is non-square.
        RuntimeError: yt-dlp extraction failure.
        urllib.error.URLError: Network error downloading the avatar.
    """
    opts = {
        # OMIT extract_flat — it suppresses channel thumbnails (RESEARCH.md Pitfall 3).
        # BUT bound the playlist to zero items: a bare channel URL otherwise makes
        # yt-dlp recursively extract every video in the channel (no extract_flat =>
        # full per-video extraction), which hangs for minutes on large channels and
        # is never bounded by the 10s urllib timeout below. The channel's own
        # avatar_uncropped thumbnail lives at the channel/playlist level and is
        # preserved with playlist_items="0" (verified against @LofiGirl: 0 entries,
        # avatar_uncropped still present). See Phase 89 UAT gap.
        "playlist_items": "0",
        # Bound yt-dlp's own network ops so extract_info() cannot hang the worker
        # thread indefinitely on a stalled connection (the worker is wait()-ed at
        # dialog teardown; an unbounded extract risks "QThread: Destroyed while
        # thread is still running" on close). See Phase 89 UAT gap.
        "socket_timeout": 10,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        # Thread the resolved absolute Node path so .desktop-stripped PATH
        # launches can find the JS runtime for the EarlyJS channel challenge.
        # Mirrors scan_playlist:86 / player.py:1866 (BUG-11 / D-02).
        "js_runtimes": yt_dlp_opts.build_js_runtimes(node_runtime),
        "remote_components": {"ejs:github"},
    }

    with cookie_utils.temp_cookies_copy() as cookiefile:
        if cookiefile is not None:
            opts["cookiefile"] = cookiefile
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)
                # Two-step resolution: if the URL resolved to a video (not a channel),
                # re-extract using the channel_url from the video info dict.
                # A channel page has its own avatar thumbnails; a video page does not.
                thumbnails = (info or {}).get("thumbnails", [])
                has_avatar = any(
                    t.get("id") in ("avatar_uncropped", "avatar") for t in thumbnails
                )
                if not has_avatar:
                    redirect_url = (info or {}).get("channel_url") or (info or {}).get(
                        "uploader_url"
                    )
                    if redirect_url:
                        info = ydl.extract_info(redirect_url, download=False)
        except yt_dlp.utils.DownloadError as e:
            raise RuntimeError(str(e)) from e

    thumbnails = (info or {}).get("thumbnails", [])
    # Prefer avatar_uncropped (explicitly named); fall back to id == 'avatar'
    # (belt-and-suspenders for future yt-dlp versions — never matches in 2026.3.17).
    avatar_entry = next(
        (t for t in thumbnails if t.get("id") == "avatar_uncropped"), None
    ) or next(
        (t for t in thumbnails if t.get("id") == "avatar"), None
    )
    if avatar_entry is None:
        raise ValueError("No channel avatar found")

    # Null-safe square guard: only reject when BOTH width and height are
    # present and differ. ``None != None`` evaluates to False in Python, so
    # avatar_uncropped entries (which have no width/height) are never rejected.
    w = avatar_entry.get("width")
    h = avatar_entry.get("height")
    if w is not None and h is not None and w != h:
        raise ValueError(f"Avatar is not square: {w}x{h}")

    url = avatar_entry["url"]
    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310  # T-89-06 timeout
        return resp.read()


# ---------------------------------------------------------------------------
# Phase 96.1: Per-video title resolution for blank flat-scan entries (D-01)
# ---------------------------------------------------------------------------


def resolve_live_title(
    url: str,
    *,
    node_runtime: "NodeRuntime | None" = None,
) -> str:
    """Resolve the real current title for a live stream URL via a per-video fetch.

    Used when scan_playlist's flat extract returns a blank/"Untitled" title for
    a live entry (D-01 root cause). Mirrors fetch_channel_avatar but omits
    ``playlist_items`` and ``extract_flat`` to get full per-video metadata.

    D-02 LANDMINE: ``js_runtimes`` is always passed via
    ``yt_dlp_opts.build_js_runtimes(node_runtime)`` — never an inline dict.
    This is required so .desktop launchers (which strip the shell PATH) can
    resolve the JS runtime for the EarlyJS/ejs:github challenge.

    D-03 fallback: on any failure, or when the resolved title is still blank,
    returns ``_fallback_title(url)`` — never a bare blank string.

    Thread safety: ``cookie_utils.temp_cookies_copy()`` wraps yt-dlp so
    save_cookies() side effects land on a temp copy, never the canonical file
    (T-96.1-03 / Phase 999.7 pattern).

    Truncation is handled downstream by repo.set_live_url_title_anchor
    (500-char cap, T-96.1-04 / RESEARCH Security Domain). Not re-truncated here.
    """
    node_path = node_runtime.path if node_runtime else None
    _log.info("resolve_live_title: url=%s node_path=%s", url, node_path)

    opts = {
        # OMIT extract_flat — it suppresses per-video metadata resolution (Pitfall 1).
        # OMIT playlist_items — we need the per-video title, not channel metadata.
        # T-96.1-02: socket_timeout=10 bounds the network op so the worker thread
        # cannot hang indefinitely on a stalled connection (mirrors fetch_channel_avatar).
        "socket_timeout": 10,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        # D-02 LANDMINE: thread the resolved absolute Node path so .desktop-stripped
        # PATH launches can find the JS runtime for the EarlyJS channel challenge.
        # Single source of truth via build_js_runtimes — never an inline dict.
        # Mirrors scan_playlist and fetch_channel_avatar (BUG-11 / D-02).
        "js_runtimes": yt_dlp_opts.build_js_runtimes(node_runtime),
        # BUG-YT-COOKIES: yt-dlp 2026.03.17+ requires the EJS remote component
        # when YouTube account cookies are detected (authenticated code path).
        "remote_components": {"ejs:github"},
    }

    with cookie_utils.temp_cookies_copy() as cookiefile:
        if cookiefile is not None:
            opts["cookiefile"] = cookiefile
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            _log.warning("resolve_live_title: extraction failed for %s: %s", url, e)
            return _fallback_title(url)

    title = (info or {}).get("title", "")
    if title and title.strip():
        return title.strip()
    return _fallback_title(url)


# ---------------------------------------------------------------------------
# Per-provider avatar fetcher registry (D-04)
# ---------------------------------------------------------------------------

_AVATAR_FETCHERS: dict[str, Callable[[str], bytes]] = {}


def register_avatar_fetcher(provider: str, fetcher: Callable[[str], bytes]) -> None:
    """Register a per-provider avatar fetcher callable.

    Phase 89 registers YouTube at module load. Phase 89b will register Twitch
    without touching any dialog or cover-slot code (D-04).
    """
    _AVATAR_FETCHERS[provider] = fetcher


def get_avatar_fetcher(provider: str) -> Optional[Callable[[str], bytes]]:
    """Return the registered avatar fetcher for the given provider, or None."""
    return _AVATAR_FETCHERS.get(provider)


# Register YouTube avatar fetcher at module load (D-04).
register_avatar_fetcher("youtube", fetch_channel_avatar)

# Register Twitch avatar fetcher at module load (Phase 89b D-05).
# Late/local import avoids an import cycle: twitch_helix imports `paths` (not
# yt_import), so there is no circular dependency — but we defer the import
# until after _AVATAR_FETCHERS and register_avatar_fetcher are defined above.
from musicstreamer import twitch_helix as _twitch_helix  # noqa: E402
register_avatar_fetcher("twitch", _twitch_helix.fetch_channel_avatar)
