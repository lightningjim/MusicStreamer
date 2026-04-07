"""
YouTube playlist import backend.

Public API:
  is_yt_playlist_url(url) -> bool
  scan_playlist(url) -> list[dict]   # [{"title", "url", "provider"}, ...]
  import_stations(entries, repo, on_progress=None) -> (imported: int, skipped: int)
"""

import json
import os
import re
import shutil
import subprocess
import tempfile

from musicstreamer.constants import COOKIES_PATH


def is_yt_playlist_url(url: str) -> bool:
    """Return True if url looks like a scannable YouTube playlist or channel tab."""
    return bool(
        re.search(r"youtube\.com/playlist\?.*list=", url)
        or re.search(r"youtube\.com/@[^/]+/(streams|live|videos)", url)
    )


def scan_playlist(url: str) -> list[dict]:
    """Run yt-dlp flat-playlist scan and return only currently-live entries.

    Each returned dict has keys: "title", "url", "provider".
    Raises ValueError for private/unavailable playlists, RuntimeError on other failures.
    """
    cmd = ["yt-dlp", "--flat-playlist", "--dump-json", "--no-cookies-from-browser"]
    cookie_tmp = None
    if os.path.exists(COOKIES_PATH):
        try:
            fd, cookie_tmp = tempfile.mkstemp(suffix=".txt", prefix="ms_cookies_")
            os.close(fd)
            shutil.copy2(COOKIES_PATH, cookie_tmp)
            cmd += ["--cookies", cookie_tmp]
        except OSError:
            cookie_tmp = None
    cmd.append(url)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        if cookie_tmp and os.path.exists(cookie_tmp):
            os.unlink(cookie_tmp)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "private" in stderr.lower() or "unavailable" in stderr.lower():
            raise ValueError("Playlist Not Accessible")
        raise RuntimeError(stderr or "yt-dlp failed")

    entries = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("is_live") is True:
            entries.append({
                "title": entry.get("title", "Untitled"),
                "url": entry.get("url") or entry.get("webpage_url"),
                "provider": entry.get("playlist_channel") or entry.get("playlist_uploader", ""),
            })
    return entries


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
