# Phase 9: Station Editor Improvements — Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the freeform provider and tags text fields in EditStationDialog with proper selectors (Adw.ComboRow for provider, chip panel for tags). Support inline creation of new providers/tags without extra dialogs. Auto-import YouTube stream title into the name field when the URL is entered and the name is blank.

Requirements: MGMT-01, MGMT-02, MGMT-03, MGMT-04

</domain>

<decisions>
## Implementation Decisions

### Provider Picker (MGMT-01, MGMT-03)
- **D-01:** Replace `self.provider_entry` (Gtk.Entry) with `Adw.ComboRow` — native Adwaita, fits existing form with SwitchRow. Populated from `repo.list_providers()`.
- **D-02:** Inline creation: user types a new provider name directly in the ComboRow. If the typed value is not in the list, `repo.ensure_provider()` creates it on save. No extra UI (no "New…" option, no "+" button).

### Tag Multi-Select (MGMT-02, MGMT-03)
- **D-03:** Replace `self.tags_entry` (comma-separated Gtk.Entry) with a chip panel. Existing tags (from `repo.list_stations()` tag union) are shown as toggleable chips. Clicking a chip adds/removes it. A small text entry below allows typing a new tag not already in the list.
- **D-04:** Inline creation: user types a new tag name in the entry field. It is appended to the selected set on Enter or save. No extra dialog.

### YouTube Title Auto-Import (MGMT-04)
- **D-05:** On URL focus-out, if the URL is a YouTube URL, fetch the stream title via `yt-dlp --print title` (daemon thread + GLib.idle_add, same pattern as thumbnail fetch).
- **D-06:** Populate the name field ONLY if name is currently empty or equals "New Station". Do not overwrite a name the user has already set.
- **D-07:** Title fetch and thumbnail fetch can run in parallel on focus-out (both are YouTube URLs). Guard with `_fetch_in_progress` or separate flags if needed.

### Claude's Discretion
- Layout of chip panel within the dialog (above or below a tags label, scrollable or wrapping)
- Whether Adw.ComboRow uses `set_use_subtitle` or a separate label row
- How to handle the case where ComboRow typed value matches an existing entry case-insensitively

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Edit Dialog (primary file)
- `musicstreamer/ui/edit_dialog.py` — Current EditStationDialog implementation; provider_entry and tags_entry are the fields to replace; fetch_yt_thumbnail daemon pattern to reuse

### Repo
- `musicstreamer/repo.py` — `list_providers()`, `ensure_provider()`, `list_stations()` (for tag union), `update_station()`

### Models
- `musicstreamer/models.py` — Station and Provider dataclasses

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `fetch_yt_thumbnail(url, callback)` — daemon thread + GLib.idle_add pattern; reuse for title fetch with `yt-dlp --print title`
- `repo.ensure_provider(name)` — creates provider if not exists, returns id; already called in `_save()`
- `_fetch_in_progress` / `_fetch_cancelled` flags — guard pattern for async ops in dialog

### Established Patterns
- `Adw.SwitchRow` in form — Adwaita native widget; `Adw.ComboRow` follows same pattern
- `Gtk.Grid` form layout — provider and tags rows are at grid row 2 and 3; replacing widgets in-place
- Daemon thread + `GLib.idle_add` for all async network/subprocess ops

### Integration Points
- `_save()` reads provider from new ComboRow (typed or selected value) and passes to `ensure_provider()`
- `_save()` reads selected tags from chip panel state and serialises to comma-separated string for `update_station(tags=...)`
- `_on_url_focus_out()` — extend to also trigger title fetch alongside thumbnail fetch

</code_context>

<specifics>
## Specific Ideas

- Title fetch: `yt-dlp --print title --no-playlist <url>` (same invocation style as `--print thumbnail`)
- Name guard: check `self.name_entry.get_text().strip() in ("", "New Station")` before populating

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
