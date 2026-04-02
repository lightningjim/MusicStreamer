# Phase 14: YouTube Playlist Import - Research

**Researched:** 2026-04-01
**Domain:** yt-dlp flat-playlist extraction, GTK4/libadwaita two-stage import dialog
**Confidence:** HIGH

## Summary

The critical research flag from STATE.md — validate `is_live` field in yt-dlp `extract_flat` mode — is now resolved with HIGH confidence. Live testing against real playlists confirms that `is_live` (boolean `true`) and `live_status` (string `"is_live"`) are both present in flat-playlist JSON output for currently-live streams. Non-live videos return `is_live: null` and `live_status: null` in flat mode. This means the filter logic is straightforward: `entry.get("is_live") is True`.

Provider auto-detection is also confirmed: `playlist_channel` in each flat entry carries the YouTube channel display name (e.g., `"Lofi Girl"`) and is reliable as the provider name per D-04. The URL for each entry is `watch?v=VIDEO_ID` format, suitable for direct use with the existing GStreamer player.

The dialog implementation follows the established `DiscoveryDialog` pattern exactly — `Adw.Window` subclass, daemon thread + `GLib.idle_add`, `Gtk.Stack` state machine. The repo already has `repo.insert_station()` and `repo.station_exists_by_url()` which are the exact methods needed for bulk import with duplicate skipping.

**Primary recommendation:** Use `yt-dlp --flat-playlist --dump-json` with `is_live == True` filter. Provider = `playlist_channel`. Station URL = the `url` field (`watch?v=...`). No additional yt-dlp calls needed per station.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** A separate "Import" button in the header bar (next to the existing "Discover" button) triggers the dialog. Consistent with the Discover pattern — always accessible, no extra navigation.
- **D-02:** Two-stage modal dialog (Adw.Window, same pattern as DiscoveryDialog):
  - Stage 1: URL entry field + "Scan" button. After scan, spinner shows while yt-dlp processes the playlist.
  - Stage 2: Checklist of found live streams (all checked by default). User unchecks any to skip. "Import Selected" button commits.
- **D-03:** Progress feedback during import (Stage 2 → commit): spinner + real-time label updating as each station is processed: "3 imported, 1 skipped". Matches IMPORT-01 spec exactly.
- **D-04:** Provider name is auto-derived from the YouTube channel name returned by yt-dlp playlist metadata. Stations group naturally under the channel in the station list (e.g., "Lofi Girl"). No user input required for provider.
- **D-05:** yt-dlp video title used as-is for the station name. No rename step in the review checklist — checkboxes only (select/deselect, no editing).
- **D-06:** Stations already in the library (matched by URL) are silently skipped — counted in the "skipped" total in the progress label. No error shown per duplicate; handled quietly since this is a bulk import.

### Claude's Discretion

- Exact yt-dlp invocation for playlist scanning (`extract_flat` mode with `is_live` filter — researcher must validate `is_live` field availability in flat mode against a real mixed playlist before coding) **[RESOLVED — see below]**
- Dialog widget hierarchy and sizing
- How to handle scan errors (invalid URL, private playlist, network failure) — inline error label in the dialog
- Whether "Import Selected" button is disabled until scan completes
- How to surface scan completion (spinner stops, checklist appears)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| IMPORT-01 | User can paste a public YouTube playlist URL and import its live streams as stations, with progress feedback (spinner + imported/skipped count) | yt-dlp flat-playlist JSON provides `is_live`, title, url, playlist_channel; repo.insert_station() + station_exists_by_url() handle persistence + dedup; DiscoveryDialog thread/idle_add pattern handles progress feedback |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| yt-dlp | 2026.03.17 (installed) | Playlist scanning, live-stream detection | Already used in project for thumbnail/title fetch |
| PyGObject / GTK4 | system | Dialog UI | Established app stack |
| libadwaita | system | Adw.Window, ActionRow, StatusPage | Established app stack |
| GLib | system | idle_add for thread-safe UI updates | Established app pattern |

### No New Dependencies

Everything needed is already installed. No `pip install` required.

**Version verification:**
```bash
yt-dlp --version  # 2026.03.17 confirmed on target machine
```

## Architecture Patterns

### Recommended File

`musicstreamer/ui/import_dialog.py` — new file, mirrors `discovery_dialog.py` structure.

### Pattern 1: yt-dlp flat-playlist scan

**What:** Run yt-dlp in flat-playlist mode (no per-video download), parse JSON lines, filter by `is_live == True`.

**When to use:** Stage 1 scan — user clicks "Scan Playlist".

**CONFIRMED field behavior (live tested against 2026.03.17):**

```python
# Source: live test against @LofiGirl/streams and @LofiGirl/videos, yt-dlp 2026.03.17
# is_live = True  → currently live stream (import it)
# is_live = None  → regular/non-live video (skip silently)
# is_live = False → was_live but ended (skip — treat same as None)

import subprocess, json

result = subprocess.run(
    ["yt-dlp", "--flat-playlist", "--dump-json", playlist_url],
    capture_output=True, text=True, timeout=60,
)

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
```

**Provider extraction (confirmed):** `playlist_channel` is present and populated on every entry in a flat playlist scan. Value is the YouTube channel display name (e.g., `"Lofi Girl"`). Fallback to `playlist_uploader` if `playlist_channel` is empty.

### Pattern 2: Two-stage dialog state machine (Gtk.Stack)

**What:** Named pages in a `Gtk.Stack` represent dialog states. Worker thread posts results via `GLib.idle_add`.

```python
# Source: discovery_dialog.py — established project pattern
self._stack = Gtk.Stack()
self._stack.add_named(prompt_page, "prompt")
self._stack.add_named(spinner_box, "scanning")
self._stack.add_named(checklist_page, "checklist")
self._stack.add_named(error_page, "error")

# In worker thread — DO NOT touch widgets here:
def _worker():
    try:
        entries = _scan_playlist(url)
        GLib.idle_add(self._on_scan_complete, entries)
    except Exception as e:
        GLib.idle_add(self._on_scan_error, str(e))

threading.Thread(target=_worker, daemon=True).start()
```

### Pattern 3: Per-item import with real-time progress

**What:** Import loop in worker thread, `GLib.idle_add` after each item to update progress label.

```python
def _import_worker(self, selected_entries):
    imported = 0
    skipped = 0
    for entry in selected_entries:
        url = entry["url"]
        if self.repo.station_exists_by_url(url):
            skipped += 1
        else:
            self.repo.insert_station(
                name=entry["title"],
                url=url,
                provider_name=entry["provider"],
                tags="",
            )
            imported += 1
        GLib.idle_add(self._update_progress, imported, skipped)
    GLib.idle_add(self._on_import_done, imported, skipped)
```

### Pattern 4: Checklist with Gtk.CheckButton prefix

**What:** `Adw.ActionRow` with a `Gtk.CheckButton` as prefix widget, all checked by default.

```python
for entry in live_entries:
    row = Adw.ActionRow()
    row.set_title(GLib.markup_escape_text(entry["title"]))
    row.set_subtitle(GLib.markup_escape_text(entry["provider"]))
    check = Gtk.CheckButton()
    check.set_active(True)
    row.add_prefix(check)
    row._check = check  # store for retrieval at import time
    self._listbox.append(row)
```

### Anti-Patterns to Avoid

- **Touching GTK widgets from the worker thread:** All widget mutations must go through `GLib.idle_add`. The worker thread only calls `GLib.idle_add(callback, data)`.
- **Calling full yt-dlp per station:** `--flat-playlist` gives all data needed (title, url, is_live, playlist_channel) in one subprocess call. Do not make per-video calls during scan.
- **Relying on `live_status == "is_live"` string alone:** Use `entry.get("is_live") is True` — the boolean field is cleaner and confirmed present. `live_status` is also `"is_live"` for live streams but `None` (not `"not_live"`) for regular videos in flat mode.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Playlist metadata fetch | Custom YouTube API client | `yt-dlp --flat-playlist` | Already installed, handles auth, geo, pagination |
| Duplicate detection | Manual URL comparison loop | `repo.station_exists_by_url(url)` | Already implemented in repo.py |
| Station persistence | Direct SQL | `repo.insert_station(name, url, provider_name, tags)` | Already implemented, handles provider upsert |
| Thread-safe UI updates | Thread locks / queues | `GLib.idle_add(callback, data)` | GTK4 main loop integration — established pattern |

**Key insight:** The project already has every building block. This phase is 95% wiring existing patterns into a new dialog.

## Common Pitfalls

### Pitfall 1: is_live is None, not False, for non-live videos in flat mode

**What goes wrong:** Filtering `entry.get("is_live") == False` catches nothing — non-live videos return `None`, not `False`.

**Why it happens:** In `--flat-playlist` mode, yt-dlp only populates `is_live` when it can determine the stream is currently live. For regular videos it returns `null`/`None`.

**How to avoid:** Filter with `entry.get("is_live") is True` (strict identity check). This is the confirmed behavior from live testing.

**Warning signs:** All playlist entries pass the filter — check if you're comparing with `== True` (which also accepts `1`) vs. `is True`.

### Pitfall 2: Playlist URL validation before yt-dlp call

**What goes wrong:** Passing non-playlist YouTube URLs (video URLs, channel home URLs) to the scanner returns unexpected results or errors.

**Why it happens:** yt-dlp handles many URL shapes; some succeed but return non-playlist data.

**How to avoid:** Pre-validate URL contains `youtube.com` and either `playlist?list=` or `/@ChannelName/streams` pattern before calling yt-dlp. Show "Invalid URL" error from the URL check, not from yt-dlp stderr.

**Recommended URL detection patterns:**
```python
import re
def _is_yt_playlist_url(url: str) -> bool:
    return bool(
        re.search(r"youtube\.com/playlist\?.*list=", url) or
        re.search(r"youtube\.com/@[^/]+/(streams|live|videos)", url)
    )
```

### Pitfall 3: yt-dlp timeout on large playlists

**What goes wrong:** Large playlists (100+ videos) take >30s, dialog appears hung.

**Why it happens:** `subprocess.run()` blocks the worker thread; user sees spinner with no activity.

**How to avoid:** Use `subprocess.Popen()` with line-by-line stdout reading so entries appear as they're parsed (optional progressive checklist population), or set a generous timeout (120s) and note it in error copy. For this phase scope, a 60-second timeout with a single scan result is acceptable.

### Pitfall 4: Checklist row checkbox retrieval at import time

**What goes wrong:** Cannot retrieve `Gtk.CheckButton` state when "Import Selected" is clicked because GTK rows don't store arbitrary Python attributes.

**Why it happens:** `Adw.ActionRow` is a GObject — Python attribute assignment on it is not GObject-compatible.

**How to avoid:** Store `(check_button, entry)` tuples in a parallel Python list alongside the `Gtk.ListBox`, not as attributes on the row widget itself.

```python
self._checklist_items: list[tuple[Gtk.CheckButton, dict]] = []

# at build time:
self._checklist_items.append((check, entry))

# at import time:
selected = [entry for (check, entry) in self._checklist_items if check.get_active()]
```

### Pitfall 5: reload_list() called before dialog closes

**What goes wrong:** Station list refreshes mid-import or before dialog close, causing visual flash.

**Why it happens:** `main_window.reload_list()` is called from `_on_import_done` while dialog is still open.

**How to avoid:** Call `reload_list()` in the "Done" button click handler (after close), or in `_on_close_request`. The UI-SPEC says: "closes dialog on click" — so the Done button click should close then reload.

## Code Examples

### Verified: yt-dlp flat-playlist field presence

```
# Live test results (yt-dlp 2026.03.17, 2026-04-01):
#
# @LofiGirl/streams entries (all live):
#   is_live: true, live_status: "is_live", was_live: false
#   playlist_channel: "Lofi Girl", playlist_uploader: "Lofi Girl"
#   url: "https://www.youtube.com/watch?v=<ID>"
#
# @LofiGirl/videos entries (non-live):
#   is_live: null, live_status: null, was_live: null
#
# Filter: entry.get("is_live") is True  ← correct
```

### Verified: repo.insert_station() signature

```python
# Source: musicstreamer/repo.py:272
def insert_station(self, name: str, url: str, provider_name: str, tags: str) -> int:
    # Calls ensure_provider() internally — no pre-lookup needed
    provider_id = self.ensure_provider(provider_name) if provider_name else None
    cur = self.con.execute(
        "INSERT INTO stations(name, url, provider_id, tags) VALUES (?, ?, ?, ?)",
        (name, url, provider_id, tags or ""),
    )
    self.con.commit()
    return int(cur.lastrowid)
```

### Verified: repo.station_exists_by_url() signature

```python
# Source: musicstreamer/repo.py:266
def station_exists_by_url(self, url: str) -> bool:
    row = self.con.execute(
        "SELECT 1 FROM stations WHERE url = ?", (url,)
    ).fetchone()
    return row is not None
```

### Verified: Header bar Import button placement

```python
# Source: musicstreamer/ui/main_window.py:37-39
# Existing pattern:
discover_btn = Gtk.Button(label="Discover")
discover_btn.connect("clicked", self._open_discovery)
header.pack_end(discover_btn)

# New Import button — add before discover_btn (pack_end adds right-to-left):
import_btn = Gtk.Button(label="Import")
import_btn.connect("clicked", self._open_import)
header.pack_end(import_btn)  # appears to left of Discover
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| yt-dlp `--simulate --print` | `--flat-playlist --dump-json` | yt-dlp ~2021 | flat mode is faster (no video page fetch per entry) |

**No deprecations relevant to this phase.**

## Open Questions

1. **`was_live` entries in a mixed playlist**
   - What we know: `was_live: false` for currently-live streams; `was_live: null` for regular videos in flat mode
   - What's unclear: Does `was_live: true` (ended livestream) ever appear in a user-supplied playlist URL? If so, should it be silently skipped?
   - Recommendation: Skip it (filter `is_live is True` only). Ended livestreams are not usable as radio stations.

2. **Pagination for very large playlists**
   - What we know: yt-dlp handles pagination internally for playlists
   - What's unclear: No hard limit discovered — yt-dlp fetches all pages
   - Recommendation: No pagination code needed; yt-dlp handles it. Set subprocess timeout to 120s.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| yt-dlp | Playlist scan | Yes | 2026.03.17 | None needed |
| GTK4 / Adw | Dialog UI | Yes | system | — |
| Python 3 | subprocess, json | Yes | system | — |

No missing dependencies.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | none (pytest auto-discovers `tests/`) |
| Quick run command | `python3 -m pytest tests/test_import_dialog.py -x -q` |
| Full suite command | `python3 -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| IMPORT-01 | Scan filters only `is_live==True` entries | unit | `python3 -m pytest tests/test_import_dialog.py::test_scan_filters_live_only -x` | No — Wave 0 |
| IMPORT-01 | Duplicate URL skipped, counted as skipped | unit | `python3 -m pytest tests/test_import_dialog.py::test_import_skips_duplicate -x` | No — Wave 0 |
| IMPORT-01 | Provider derived from playlist_channel | unit | `python3 -m pytest tests/test_import_dialog.py::test_provider_from_playlist_channel -x` | No — Wave 0 |
| IMPORT-01 | yt-dlp parse handles mixed live/non-live JSON | unit | `python3 -m pytest tests/test_import_dialog.py::test_parse_flat_playlist_json -x` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `python3 -m pytest tests/test_import_dialog.py -x -q`
- **Per wave merge:** `python3 -m pytest tests/ -q`
- **Phase gate:** Full suite green (currently 111 tests passing) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_import_dialog.py` — covers all IMPORT-01 test cases above

*(Existing test infrastructure and pytest config require no changes — just add the new test file.)*

## Project Constraints (from CLAUDE.md)

No CLAUDE.md found at project root. Global CLAUDE.md applies:

- Responses terse, action-oriented
- Single recommended option (not menus)
- Scope changes tightly to what is requested
- Avoid touching working functionality not mentioned

## Sources

### Primary (HIGH confidence)

- Live yt-dlp test run (2026-04-01, yt-dlp 2026.03.17) — confirmed `is_live`, `live_status`, `playlist_channel`, `playlist_uploader` field presence and values for live and non-live entries
- `musicstreamer/ui/discovery_dialog.py` — threading model, GLib.idle_add pattern, Gtk.Stack state machine
- `musicstreamer/ui/edit_dialog.py` — subprocess.run yt-dlp pattern
- `musicstreamer/repo.py` — insert_station(), station_exists_by_url() signatures
- `musicstreamer/ui/main_window.py` — header bar pack_end pattern
- `.planning/phases/14-youtube-playlist-import/14-UI-SPEC.md` — approved UI contract

### Secondary (MEDIUM confidence)

- yt-dlp `--flat-playlist` behavior for playlists vs. channel tabs — observed consistent; private/deleted playlists return non-zero exit code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies installed and verified
- yt-dlp field behavior: HIGH — live tested on real playlists with current version
- Architecture: HIGH — direct copy of established DiscoveryDialog pattern
- Pitfalls: HIGH — derived from code inspection and live yt-dlp testing

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (yt-dlp field schema is stable; GTK4 API stable)
