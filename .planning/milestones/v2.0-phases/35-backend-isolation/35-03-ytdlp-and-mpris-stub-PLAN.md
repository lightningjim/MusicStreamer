---
phase: 35-backend-isolation
plan: 03
type: execute
wave: 2
depends_on: [35-01, 35-02]
files_modified:
  - musicstreamer/yt_import.py
  - musicstreamer/mpris.py
  - tests/test_yt_import_library.py
autonomous: true
requirements: [PORT-09]
must_haves:
  truths:
    - "yt_import.scan_playlist uses yt_dlp.YoutubeDL.extract_info — zero subprocess/CLI invocations of yt-dlp"
    - "mpris.MprisService is a no-op stub with the exact same public surface main_window.py consumes (constructor, emit_properties_changed, _build_metadata)"
    - "Constructing the stub logs a one-line debug warning so the non-functional state is discoverable (D-11)"
  artifacts:
    - path: "musicstreamer/yt_import.py"
      provides: "Library-API playlist scan"
      contains: "yt_dlp.YoutubeDL"
    - path: "musicstreamer/mpris.py"
      provides: "No-op MprisService stub"
      contains: "class MprisService"
      max_lines: 60
    - path: "tests/test_yt_import_library.py"
      provides: "Tests for library-API scan_playlist covering happy path, private playlist, and cookies passthrough"
  key_links:
    - from: "musicstreamer/yt_import.py"
      to: "musicstreamer.paths.cookies_path"
      via: "cookie file resolution via paths helper"
      pattern: "paths\\.cookies_path"
    - from: "musicstreamer/mpris.py"
      to: "logging.getLogger"
      via: "one-line debug warning on construction"
      pattern: "_log\\.(debug|info|warning)"
---

<objective>
Satisfy the non-player portion of PORT-09 and D-09..D-11: port `yt_import.py` from `subprocess.Popen(['yt-dlp', ...])` to the `yt_dlp.YoutubeDL` library API, and replace `mpris.py` with a no-op stub that preserves the public surface `main_window.py` calls into.

Purpose: Unblock Plan 35-04 (which owns player.py). The player rewrite depends on `paths.cookies_path()` (from 35-02) and on `yt_import.py` no longer holding a subprocess reference (shared helper), and the mpris stub must exist so `main_window.py` imports don't break mid-phase.

Output:
- `musicstreamer/yt_import.py` rewritten around `yt_dlp.YoutubeDL` — all subprocess/tempfile code deleted.
- `musicstreamer/mpris.py` replaced with a ~40-line stub (class + 3 methods + 1 debug log on __init__).
- `tests/test_yt_import_library.py` covering scan_playlist library path (new).
- `tests/test_mpris.py` stays in place but is NOT rewritten here — the pytest-qt port (Plan 35-05) handles it per D-25/Pitfall 8 in RESEARCH.md, since the test uses GTK/GLib fixtures that only get rewritten during the test-suite big-bang port.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/35-backend-isolation/35-CONTEXT.md
@.planning/phases/35-backend-isolation/35-RESEARCH.md
@musicstreamer/yt_import.py
@musicstreamer/mpris.py
@musicstreamer/paths.py

<interfaces>
<!-- yt-dlp library API — RESEARCH.md Pattern 6 -->
```python
import yt_dlp
opts = {
    'extract_flat': 'in_playlist',
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    # 'cookiefile': '/path',  # optional, only if cookies file exists
}
with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info(url, download=False)
# info['entries'] is an iterable of sparse dicts when extract_flat='in_playlist'
# yt_dlp.utils.DownloadError is the exception raised on HTTP/extractor failures
```

<!-- MprisService public surface consumed by main_window.py (grep confirmed) -->
<!-- line 19:  from musicstreamer.mpris import MprisService -->
<!-- line 36:  self.mpris = MprisService(self) -->
<!-- lines 702,775,809,965:  self.mpris.emit_properties_changed({...}) -->
<!-- lines 811,967:  self.mpris._build_metadata() -->
<!-- Only these three names need to exist: MprisService (class), emit_properties_changed (method), _build_metadata (method) -->

<!-- RESEARCH.md Pitfall 1: entries may lack is_live when extract_flat is set. Use live_status OR fall through to per-entry extract_info(process=False) -->
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Port yt_import.scan_playlist to yt_dlp library API</name>
  <files>musicstreamer/yt_import.py, tests/test_yt_import_library.py</files>
  <read_first>musicstreamer/yt_import.py, .planning/phases/35-backend-isolation/35-RESEARCH.md (Pattern 6 + Pitfall 1)</read_first>
  <behavior>
Tests in `tests/test_yt_import_library.py` (use `unittest.mock.patch` to stub `yt_dlp.YoutubeDL`; no real network):
- `test_scan_playlist_happy_path_returns_live_entries`: Mock `yt_dlp.YoutubeDL.__enter__().extract_info` to return `{'entries': [{'title': 'A', 'url': 'https://x/a', 'is_live': True, 'live_status': 'is_live', 'playlist_uploader': 'Uploader'}, {'title': 'B', 'is_live': False, 'live_status': 'was_live'}]}`. Call `scan_playlist("https://youtube.com/@lofigirl/streams")`. Result must be a 1-element list: `[{'title': 'A', 'url': 'https://x/a', 'provider': 'Uploader'}]`.
- `test_scan_playlist_uses_live_status_when_is_live_missing`: Same mock but entry A has `is_live=None, live_status='is_live'`. Scan still includes A. (Handles Pitfall 1.)
- `test_scan_playlist_private_raises_valueerror`: Mock `extract_info` to raise `yt_dlp.utils.DownloadError("Video is private")`. `scan_playlist(...)` raises `ValueError` with "Playlist Not Accessible".
- `test_scan_playlist_other_error_raises_runtimeerror`: Mock raises `yt_dlp.utils.DownloadError("HTTP Error 500")`. Raises `RuntimeError`.
- `test_scan_playlist_passes_cookies_when_file_exists`: Monkeypatch `paths._root_override = str(tmp_path)`. Create `tmp_path / "cookies.txt"`. Patch `yt_dlp.YoutubeDL` with a `MagicMock`; assert that when called, the opts dict contains `'cookiefile': <cookies path>`.
- `test_scan_playlist_omits_cookiefile_when_missing`: Same but no cookies file. Opts must NOT contain `cookiefile`.
- `test_is_yt_playlist_url_unchanged`: `is_yt_playlist_url("https://www.youtube.com/playlist?list=PL123")` returns True; `"https://example.com"` returns False. (Regression — behavior preserved from current subprocess version.)
- `test_import_stations_unchanged`: Use a fake `repo` with `station_exists_by_url` + `insert_station`; assert current behavior preserved (tuple return, dedup, on_progress callback).
  </behavior>
  <action>
**Step 1 — Add failing tests first.** Create `tests/test_yt_import_library.py` implementing all 8 test cases above. Run `pytest tests/test_yt_import_library.py -x`; first subset should fail because `yt_import.py` still uses subprocess.

**Step 2 — Rewrite `musicstreamer/yt_import.py`.** Replace the entire file with:

```python
"""
YouTube playlist import backend.

Public API:
  is_yt_playlist_url(url) -> bool
  scan_playlist(url) -> list[dict]
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
    """Handle RESEARCH.md Pitfall 1 — extract_flat may leave is_live as None
    for sparse entries. Prefer live_status, fall back to is_live."""
    status = entry.get("live_status")
    if status == "is_live":
        return True
    if status in ("was_live", "not_live", "post_live"):
        return False
    return entry.get("is_live") is True


def scan_playlist(url: str) -> list[dict]:
    """Scan a YouTube playlist/channel tab and return currently-live entries.

    Each returned dict: {"title", "url", "provider"}.
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
        results.append({
            "title": entry.get("title", "Untitled"),
            "url": entry.get("url") or entry.get("webpage_url"),
            "provider": entry.get("playlist_channel")
                        or entry.get("playlist_uploader")
                        or entry.get("uploader", ""),
        })
    return results


def import_stations(entries: list[dict], repo, on_progress=None) -> tuple[int, int]:
    """Import entries into the repo. Unchanged from subprocess version."""
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
```

Delete the now-unused imports (`json`, `shutil`, `subprocess`, `tempfile`). Keep `os` and `re`.

**Step 3 — Run tests (GREEN).** `pytest tests/test_yt_import_library.py -x` must pass.
  </action>
  <verify>
    <automated>pytest tests/test_yt_import_library.py -x && ! grep -qE "^import subprocess|^from subprocess|subprocess\.(run|Popen)" musicstreamer/yt_import.py</automated>
  </verify>
  <acceptance_criteria>
- `grep -q "import yt_dlp" musicstreamer/yt_import.py` matches
- `grep -q "YoutubeDL" musicstreamer/yt_import.py` matches
- `! grep -qE "subprocess|shutil|tempfile" musicstreamer/yt_import.py` (none of those imports remain)
- `grep -q "from musicstreamer import paths" musicstreamer/yt_import.py` matches
- `grep -q "extract_flat" musicstreamer/yt_import.py` matches
- `grep -q "live_status" musicstreamer/yt_import.py` matches (Pitfall 1 handled)
- `pytest tests/test_yt_import_library.py -x` exits 0
  </acceptance_criteria>
  <done>yt_import.py uses only the library API; all 8 new tests pass; no subprocess references remain in the file.</done>
</task>

<task type="auto">
  <name>Task 2: Replace mpris.py with no-op stub</name>
  <files>musicstreamer/mpris.py</files>
  <read_first>musicstreamer/mpris.py, musicstreamer/ui/main_window.py (lines 19, 36, 700-815, 960-970 — all MprisService call sites), .planning/phases/35-backend-isolation/35-RESEARCH.md (Pattern 8)</read_first>
  <action>
Replace the ENTIRE contents of `musicstreamer/mpris.py` with:

```python
"""No-op MPRIS2 stub for Phase 35.

Phase 41 (MEDIA-02) will rewrite this against PySide6.QtDBus. Between
Phase 35 and Phase 41 media keys are NON-FUNCTIONAL by design — see
.planning/phases/35-backend-isolation/35-CONTEXT.md D-09, D-10, D-11.

This module intentionally has zero dbus-python, zero GLib, and zero Qt
imports. Its only job is to preserve the public surface main_window.py
consumes so the GTK app still launches during the transition.

Public surface preserved (from grep of musicstreamer/ui/main_window.py):
  - MprisService(window)             # line 36
  - mpris.emit_properties_changed(d) # lines 702, 775, 809, 965
  - mpris._build_metadata()          # lines 811, 967
"""
import logging

_log = logging.getLogger(__name__)


class MprisService:
    """No-op stub. Accepts the same constructor arguments as the real service;
    every method is a no-op. Logs a one-line debug warning on construction so
    the non-functional state is discoverable in logs (D-11)."""

    def __init__(self, window=None):
        self._window = window
        _log.debug(
            "MprisService stub active — media keys disabled until Phase 41 (MEDIA-02)"
        )

    def emit_properties_changed(self, props: dict) -> None:
        """No-op. Accepts any dict shape (including dbus-typed values from
        main_window.py's legacy call sites) and silently discards it."""
        return None

    def _build_metadata(self) -> dict:
        """Return empty dict. main_window.py passes the result back into
        emit_properties_changed, which is itself a no-op."""
        return {}
```

**Critical:** `main_window.py` lines 701, 704, 774, 809, 964 construct `dbus.Dictionary` / `dbus.String` / `dbus.ObjectPath` objects LOCALLY before calling `self.mpris.emit_properties_changed(...)`. Per RESEARCH.md Pattern 8 recommendation (option 1): **do NOT touch main_window.py** — leave those local `import dbus` lines alone. `dbus-python` stays installed during Phase 35 because the GTK UI still imports it; the stub accepts any argument shape because it ignores the payload. Phase 36 deletes main_window.py entirely and removes `dbus-python` from the dependency list at the same time.

Do NOT rewrite `tests/test_mpris.py` in this task — that test uses `patch.dict("sys.modules", _MODULE_PATCHES)` to mock dbus at import time, which is incompatible with the new stub's interface. It will be rewritten during the big-bang pytest-qt port in Plan 35-05 Task 2 (per RESEARCH.md Pitfall 8). For Phase 35-03 acceptance, `test_mpris.py` is expected to fail — this is recorded as known-failing and picked up by 35-05.
  </action>
  <verify>
    <automated>python -c "from musicstreamer.mpris import MprisService; s = MprisService(None); s.emit_properties_changed({'x': 1}); assert s._build_metadata() == {}; print('ok')" && ! grep -qE "^import dbus|^from dbus|dbus\.(service|mainloop|Dictionary|String|ObjectPath)|from gi|import gi" musicstreamer/mpris.py</automated>
  </verify>
  <acceptance_criteria>
- `grep -q "class MprisService" musicstreamer/mpris.py` matches
- `! grep -qE "^import dbus|^from dbus|dbus\\.service|dbus\\.mainloop" musicstreamer/mpris.py` (no dbus imports)
- `! grep -qE "from gi|import gi|GLib" musicstreamer/mpris.py` (no GLib imports)
- `! grep -qE "from PySide6|import PySide6|QtDBus" musicstreamer/mpris.py` (no Qt imports — stub is pure Python)
- `grep -q "def emit_properties_changed" musicstreamer/mpris.py` matches
- `grep -q "def _build_metadata" musicstreamer/mpris.py` matches
- `grep -qE "_log\\.(debug|info|warning).*stub" musicstreamer/mpris.py` matches
- `wc -l < musicstreamer/mpris.py` returns ≤ 60
- `python -c "from musicstreamer.mpris import MprisService; MprisService(None)"` exits 0
- `python -c "from musicstreamer.ui.main_window import MusicStreamerWindow" 2>&1` — may fail on GTK init in headless env but MUST NOT fail on `from musicstreamer.mpris import MprisService`. Check with: `python -c "import ast, sys; tree=ast.parse(open('musicstreamer/ui/main_window.py').read()); print('ok')"` (static syntax check).
  </acceptance_criteria>
  <done>mpris.py is a 40-line no-op stub with zero dbus/GLib/Qt imports; main_window.py imports still resolve; tests/test_mpris.py is known-failing and flagged for Plan 35-05.</done>
</task>

</tasks>

<verification>
This plan leaves two deliberate known-failing states that are fixed in Plan 35-05:
1. `tests/test_mpris.py` — stale dbus mocks, rewritten in 35-05 Task 2.
2. Any test that imports `musicstreamer.yt_import` and monkeypatches subprocess calls to yt-dlp — those are now library-API calls and need their mocks updated. If such tests exist in the current suite, they get picked up during the big-bang port.

Record these in 35-03-SUMMARY.md so Plan 35-05 can target them explicitly.
</verification>

<success_criteria>
1. `yt_import.py` uses `yt_dlp.YoutubeDL` — zero `subprocess` / `shutil.which` / `tempfile` references.
2. `mpris.py` is a pure-Python stub — zero dbus/GLib/Qt imports.
3. New `tests/test_yt_import_library.py` passes end-to-end.
4. `from musicstreamer.mpris import MprisService` succeeds on a Python with `dbus-python` uninstalled (future-proofing check).
</success_criteria>

<output>
After completion, create `.planning/phases/35-backend-isolation/35-03-SUMMARY.md` with: (a) confirmation of library-API port, (b) mpris stub location, (c) list of known-failing tests for Plan 35-05 to address.
</output>
