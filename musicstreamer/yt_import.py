"""
YouTube playlist import backend.

Public API:
  is_yt_playlist_url(url) -> bool
  scan_playlist(url) -> list[dict]   # [{"title", "url", "provider"}, ...]
  import_stations(entries, repo, on_progress=None) -> (imported: int, skipped: int)

Uses the yt_dlp Python library API directly (PORT-09 / D-17). No subprocess.
"""
import os
import re

import yt_dlp

from musicstreamer import paths


def is_yt_playlist_url(url: str) -> bool:
    """Return True if url looks like a scannable YouTube playlist or channel tab."""
    return bool(
        re.search(r"youtube\.com/playlist\?.*list=", url)
        or re.search(r"youtube\.com/@[^/]+/(streams|live|videos)", url)
    )


def _entry_is_live(entry: dict) -> bool:
    """RESEARCH.md Pitfall 1 — extract_flat may leave is_live as None for sparse
    entries. Prefer live_status, fall back to is_live."""
    status = entry.get("live_status")
    if status == "is_live":
        return True
    if status in ("was_live", "not_live", "post_live"):
        return False
    return entry.get("is_live") is True


def scan_playlist(url: str) -> list[dict]:
    """Scan a YouTube playlist/channel tab and return currently-live entries.

    Each returned dict has keys: "title", "url", "provider".
    Raises ValueError for private/unavailable playlists.
    Raises RuntimeError on other yt-dlp failures.
    """
    opts = {
        "extract_flat": "in_playlist",
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    cookies = paths.cookies_path()
    if os.path.exists(cookies):
        opts["cookiefile"] = cookies

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
