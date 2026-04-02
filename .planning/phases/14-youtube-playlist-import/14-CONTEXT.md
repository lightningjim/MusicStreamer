# Phase 14: YouTube Playlist Import - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can paste a public YouTube playlist URL into an import dialog and import its live streams as stations. The dialog has two stages: (1) scan the playlist and show a checklist of found live streams, (2) user confirms selection then import runs with real-time progress feedback. Non-live videos are silently skipped. No playback preview — this is an import-only flow.

</domain>

<decisions>
## Implementation Decisions

### Entry Point
- **D-01:** A separate "Import" button in the header bar (next to the existing "Discover" button) triggers the dialog. Consistent with the Discover pattern — always accessible, no extra navigation.

### Dialog Flow
- **D-02:** Two-stage modal dialog (Adw.Window, same pattern as DiscoveryDialog):
  - **Stage 1:** URL entry field + "Scan" button. After scan, spinner shows while yt-dlp processes the playlist.
  - **Stage 2:** Checklist of found live streams (all checked by default). User unchecks any to skip. "Import Selected" button commits.
- **D-03:** Progress feedback during import (Stage 2 → commit): spinner + real-time label updating as each station is processed: "3 imported, 1 skipped". Matches IMPORT-01 spec exactly.

### Provider Assignment
- **D-04:** Provider name is auto-derived from the YouTube channel name returned by yt-dlp playlist metadata. Stations group naturally under the channel in the station list (e.g., "Lofi Girl"). No user input required for provider.

### Station Naming
- **D-05:** yt-dlp video title used as-is for the station name. No rename step in the review checklist — checkboxes only (select/deselect, no editing).

### Duplicate Handling
- **D-06:** Stations already in the library (matched by URL) are silently skipped — counted in the "skipped" total in the progress label. No error shown per duplicate; handled quietly since this is a bulk import.

### Claude's Discretion
- Exact yt-dlp invocation for playlist scanning (`extract_flat` mode with `is_live` filter — researcher must validate `is_live` field availability in flat mode against a real mixed playlist before coding)
- Dialog widget hierarchy and sizing
- How to handle scan errors (invalid URL, private playlist, network failure) — inline error label in the dialog
- Whether "Import Selected" button is disabled until scan completes
- How to surface scan completion (spinner stops, checklist appears)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs — requirements fully captured in decisions above and REQUIREMENTS.md (IMPORT-01).

### Codebase
- `musicstreamer/ui/discovery_dialog.py` — Closest existing dialog (Adw.Window, threading, GLib.idle_add pattern)
- `musicstreamer/ui/edit_dialog.py` — `fetch_yt_thumbnail()` and `fetch_yt_title()` show daemon thread + yt-dlp subprocess pattern
- `musicstreamer/ui/main_window.py` — Header bar wiring (see `_open_discovery` at line 823 and `discover_btn` at line 37)
- `musicstreamer/player.py` — YouTube URL detection pattern (`_is_youtube_url`)
- `musicstreamer/repo.py` — `create_station()` for saving imported stations; URL uniqueness check
- `musicstreamer/models.py` — Station and Provider dataclasses

### Research Flag
- STATE.md note: **Validate `is_live` field in yt-dlp `extract_flat` mode against a real mixed playlist before writing filter logic.** This is the critical unknown for Phase 14 — researcher must confirm the field name and behavior before the planner can spec the yt-dlp invocation.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DiscoveryDialog` (Adw.Window): Dialog structure, threading model, GLib.idle_add callbacks — copy this pattern
- `fetch_yt_thumbnail()` / `fetch_yt_title()` in edit_dialog.py: Daemon thread + `subprocess.run(["yt-dlp", ...])` pattern for yt-dlp calls
- `repo.create_station()`: Existing method for persisting a new station to SQLite
- Header bar wiring in main_window.py: `discover_btn` + `_open_discovery` shows exactly how to add a second button

### Established Patterns
- Modal dialogs: `Adw.Window` subclasses with `set_transient_for(main_window)` and `set_modal(True)`
- Background work: daemon threads call `GLib.idle_add(callback, result)` to post results back to main thread
- yt-dlp called via `subprocess.run()` / `subprocess.Popen()` with `stdout=PIPE`

### Integration Points
- "Import" button added to header bar alongside existing "Discover" button
- Import dialog calls `repo.create_station()` for each selected live stream
- After import completes, triggers `main_window.reload_list()` to refresh the station list

</code_context>

<specifics>
## Specific Ideas

- The checklist review step (Stage 2) should show all-checked by default — user only acts if they want to exclude something. Minimize friction for the common case (import everything).
- "Skipped" in the progress count covers both: (a) non-live videos filtered by yt-dlp, and (b) stations already in library by URL. Both are quiet skips.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 14-youtube-playlist-import*
*Context gathered: 2026-04-01*
