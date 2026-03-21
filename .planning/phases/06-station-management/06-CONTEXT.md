# Phase 6: Station Management - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Add station deletion (from within the edit dialog), YouTube thumbnail auto-populate in the station editor, and a per-station ICY metadata disable toggle. All three features touch the Station data model and/or the EditStationDialog. The station list and playback engine are modified only where required to support these three features.

</domain>

<decisions>
## Implementation Decisions

### Delete UX
- Delete action lives inside `EditStationDialog` (not a row button or context menu)
- Confirmation required: `Adw.MessageDialog` with "Delete [Station Name]?" and Cancel / Delete buttons
- If the station being deleted is currently playing: block the delete and show an error/warning — user must stop playback first
- After confirmed delete: close the dialog, remove the station from the list, no further action needed

### YouTube Thumbnail Fetch
- Auto-fetch triggers on URL field focus-out (when user leaves the URL entry)
- A persistent "Fetch from URL" button also exists in the dialog for manual re-fetch (needed when the channel refreshes their live stream thumbnail)
- Both auto-fetch and manual button always replace station art, even if art is already set
- During fetch: show a `Gtk.Spinner` in the station art preview slot
- Only triggered for YouTube URLs (detect `youtube.com` or `youtu.be` in the URL)
- Use yt-dlp (already a dependency) to retrieve the thumbnail URL, then download and store via `copy_asset_for_station`

### ICY Override
- Toggle lives in `EditStationDialog`: an `Adw.SwitchRow` labeled "Disable ICY metadata"
- Persisted to DB as a new `icy_disabled` boolean column on the `stations` table (DEFAULT 0, backward-compatible migration via `ALTER TABLE`)
- `Station` dataclass gets a new `icy_disabled: bool` field
- During playback: if `icy_disabled` is True, suppress ICY TAG bus events and show the station name in the title label instead

### Claude's Discretion
- Exact placement of the Delete button within the dialog (e.g., destructive-action footer vs header)
- Threading model for the yt-dlp thumbnail fetch (daemon thread + GLib.idle_add, same pattern as cover_art.py)
- Error handling when yt-dlp cannot retrieve a thumbnail (silent no-op or status label)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Station data model
- `musicstreamer/models.py` — `Station` dataclass; needs `icy_disabled: bool` field added
- `musicstreamer/repo.py` — `Repo` class; needs `delete_station()`, schema migration for `icy_disabled`, `update_station()` signature update

### Station editor
- `musicstreamer/ui/edit_dialog.py` — `EditStationDialog`; site for delete button, YT fetch button/trigger, ICY toggle

### Playback / ICY handling
- `musicstreamer/ui/main_window.py` — `_on_title` callback and `_play_station`; ICY override must suppress title update here
- `musicstreamer/player.py` — GStreamer pipeline; reference for how TAG bus events flow

### Asset handling
- `musicstreamer/assets.py` — `copy_asset_for_station`; used for saving downloaded thumbnail to disk
- `musicstreamer/cover_art.py` — daemon thread + GLib.idle_add pattern to follow for yt-dlp fetch

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `copy_asset_for_station(station_id, path, kind)` in `assets.py` — already handles saving images to the correct location under DATA_DIR; use for storing downloaded thumbnails
- `cover_art.py` daemon threading pattern — daemon thread calls network, result passed back via `GLib.idle_add(callback)` — identical pattern needed for yt-dlp thumbnail fetch

### Established Patterns
- `Adw.MessageDialog` — standard GNOME confirmation pattern; use for delete confirmation
- `Gtk.Stack` — used for logo/art slots in now-playing; not needed here but illustrates existing fallback pattern
- `GLib.idle_add` — mandatory for all cross-thread UI updates; already used in cover_art and main_window

### Integration Points
- `EditStationDialog.__init__` — add ICY toggle (`Adw.SwitchRow`), Fetch button, and Delete button to the existing form layout
- `EditStationDialog._save` — update to include `icy_disabled` in `repo.update_station()` call
- `Repo.update_station()` — signature must accept `icy_disabled` parameter
- `main_window._on_title` — add guard: if `self._current_station.icy_disabled`, ignore ICY tags and keep title as station name
- `main_window._play_station` — pass `icy_disabled` state to the title-display logic

</code_context>

<specifics>
## Specific Ideas

- The "Fetch from URL" button use case: YouTube channels (e.g. LoFi Girl) periodically change their live stream thumbnail; user wants to be able to re-fetch without re-entering the URL
- ICY override use case: some stations return an incorrect or irrelevant ICY track title (e.g. a YouTube stream that always returns a stale title); the station name is more useful in those cases

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 06-station-management*
*Context gathered: 2026-03-21*
