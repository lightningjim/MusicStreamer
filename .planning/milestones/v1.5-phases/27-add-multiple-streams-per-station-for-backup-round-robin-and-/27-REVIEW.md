---
phase: 27-add-multiple-streams-per-station
reviewed: 2026-04-09T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - musicstreamer/aa_import.py
  - musicstreamer/constants.py
  - musicstreamer/models.py
  - musicstreamer/player.py
  - musicstreamer/repo.py
  - musicstreamer/ui/discovery_dialog.py
  - musicstreamer/ui/edit_dialog.py
  - musicstreamer/ui/import_dialog.py
  - musicstreamer/ui/main_window.py
  - musicstreamer/ui/streams_dialog.py
  - tests/test_aa_import.py
  - tests/test_repo.py
findings:
  critical: 0
  warning: 5
  info: 3
  total: 8
status: issues_found
---

# Phase 27: Code Review Report

**Reviewed:** 2026-04-09
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 27 introduces the `station_streams` table, a schema migration away from the single `url` column, and the full CRUD stack for multi-stream stations. The data layer and migration are well-implemented — the migration is idempotent and the cascade delete works correctly. Test coverage is solid.

Three issues stand out: a position-ordering bug in `import_stations_multi` that stores the wrong positions in the database, an `_on_move_up`/`_on_move_down` crash when a stream's ID is not in the loaded list (stale reference), and a silent data-loss edge case in the multi-import when `list_streams` returns empty after `insert_station`. The remaining findings are minor.

---

## Warnings

### WR-01: `import_stations_multi` updates stream with wrong position from `position_map`

**File:** `musicstreamer/aa_import.py:188-196`
**Issue:** The code updates the auto-created stream with `s["position"]` from the channel dict (1, 2, or 3), but `insert_station` always inserts the first stream at `position=1`. This is correct for the hi-quality stream. However, the logic also iterates all `ch["streams"]` looking for `s["url"] == first_url`, then falls through to `insert_stream` for the rest with `s["position"]` values. The real bug is that `position_map` in `fetch_channels_multi` assigns positions `{"hi": 1, "med": 2, "low": 3}`, but streams are iterated in dict insertion order (which mirrors `QUALITY_TIERS` iteration order). If the first stream in `ch["streams"]` is not `hi` (e.g. due to network failure on hi tier but success on med/low), `first_url` will point to a med/low URL, and the auto-created stream will be positioned at 1 while its actual quality is med or low.

**Fix:** Instead of matching on URL equality to find which stream is the auto-created one, always update by quality:
```python
first_stream = ch["streams"][0]
first_url = first_stream["url"] if ch["streams"] else ""
station_id = repo.insert_station(name=ch["title"], url=first_url, ...)
streams_in_db = repo.list_streams(station_id)
if streams_in_db:
    s0 = first_stream
    repo.update_stream(
        streams_in_db[0].id, s0["url"], s0.get("label", ""),
        s0["quality"], s0["position"], "shoutcast", s0.get("codec", "")
    )
for s in ch["streams"][1:]:
    repo.insert_stream(station_id, s["url"], label="", quality=s["quality"],
                       position=s["position"], stream_type="shoutcast", codec=s.get("codec", ""))
```

---

### WR-02: `import_stations_multi` silently drops stream metadata when `list_streams` is empty

**File:** `musicstreamer/aa_import.py:190-196`
**Issue:** After `repo.insert_station(...)`, the code calls `repo.list_streams(station_id)` to get the auto-created stream's DB id so it can call `update_stream`. If `list_streams` returns `[]` (e.g. because the URL was empty or a bug in `insert_station`), the `if streams:` branch is skipped silently — the auto-created stream retains default metadata (no quality, position=1, no codec). This is a silent data integrity failure.

**Fix:** Assert or log when `streams_in_db` is unexpectedly empty:
```python
streams_in_db = repo.list_streams(station_id)
if not streams_in_db:
    # insert_station created no stream — insert first manually
    repo.insert_stream(station_id, first_url, label="",
                       quality=first_stream["quality"],
                       position=first_stream["position"],
                       stream_type="shoutcast", codec=first_stream.get("codec", ""))
```

---

### WR-03: `_on_move_up` / `_on_move_down` crash if stream ID not in current list

**File:** `musicstreamer/ui/streams_dialog.py:233`
**Issue:** `ids.index(stream.id)` raises `ValueError` if `stream.id` is not in `ids`. This can happen if the stream was deleted in another path (e.g. another dialog instance, or a concurrent `_on_delete_stream` that ran between when the row was built and when the button was clicked). The exception is unhandled and propagates as a GTK critical error.

**Fix:**
```python
try:
    idx = ids.index(stream.id)
except ValueError:
    self._refresh_list()
    return
```

---

### WR-04: `player.py` blocks the main thread for 2 seconds on every YouTube play

**File:** `musicstreamer/player.py:133`
**Issue:** `time.sleep(2)` is called unconditionally inside `_play_youtube`, which is called from `_play_station` on the GTK main thread. This freezes the entire UI (including the Now Playing panel and all controls) for 2 seconds each time a YouTube station is played or resumed.

**Fix:** Move the mpv exit-retry check into a `GLib.timeout_add(2000, ...)` callback so it runs asynchronously:
```python
def _check_mpv_exit():
    if self._yt_cookie_tmp and self._yt_proc and self._yt_proc.poll() is not None:
        import sys
        print("mpv exited immediately with cookies, retrying without", file=sys.stderr)
        self._cleanup_cookie_tmp()
        cmd_no_cookies = [a for a in cmd if not a.startswith("--ytdl-raw-options=cookies=")]
        self._yt_proc = subprocess.Popen(
            cmd_no_cookies,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=env,
        )
    return False  # don't repeat

GLib.timeout_add(2000, _check_mpv_exit)
```

---

### WR-05: `_on_form_save` in `streams_dialog.py` uses stale `existing` position on update

**File:** `musicstreamer/ui/streams_dialog.py:301-305`
**Issue:** When updating an existing stream, the code re-fetches all streams to find `existing.position`, but if `_editing_stream_id` is not found (the stream was deleted externally), `existing` is `None`, and `position = existing.position` raises `AttributeError`. The `if existing else 1` fallback on line 303 handles the `None` case but silently resets the position to 1, which corrupts the stream order.

**Fix:** If the stream is not found, cancel the edit gracefully:
```python
existing = next((s for s in streams if s.id == self._editing_stream_id), None)
if existing is None:
    self._clear_form()
    self._form_frame.set_visible(False)
    self._refresh_list()
    return
position = existing.position
```

---

## Info

### IN-01: `import` inside `__init__` in `player.py`

**File:** `musicstreamer/player.py:41`
**Issue:** `import glob` is deferred inside `__init__`. `glob` is a stdlib module — it should be at the top of the file with the other imports.

**Fix:** Move `import glob` to the top-level imports alongside `import os`, `import shutil`, etc.

---

### IN-02: `import urllib.parse` deferred inside a function in `edit_dialog.py`

**File:** `musicstreamer/ui/edit_dialog.py:51`
**Issue:** `import urllib.parse` is deferred inside `_aa_channel_key_from_url`. Standard library; no reason for a deferred import here.

**Fix:** Move to top-level imports.

---

### IN-03: `fetch_channels_multi` calls `_fetch_image_map` once per network but inside the quality tier loop

**File:** `musicstreamer/aa_import.py:122`
**Issue:** `_fetch_image_map` is called once per network (outside the quality loop), which is correct. However, reading the code flow carefully, `img_map` is fetched at line 122 before any quality tier check, meaning if the network's first quality tier raises a 401/403, the image fetch cost was wasted. This is a minor inefficiency rather than a correctness issue, but worth noting.

**Fix:** No code change required — just noting the pattern is intentional and the placement is acceptable. Could move `img_map` fetch inside a `try/finally` block guarded by successful tier fetch, but the current approach is fine given the 401/403 path raises immediately.

---

_Reviewed: 2026-04-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
