# Phase 12: Favorites - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a star button to the now-playing panel for ICY track titles. Persist favorites to SQLite (denormalized: station name, provider name, track title, iTunes genre). Toggle the left sidebar between Stations and Favorites views using an Adw.ToggleGroup. Allow removal of favorites from the Favorites view via a per-row trash icon.

</domain>

<decisions>
## Implementation Decisions

### Toggle UI
- **D-01:** Toggle placed above the station list area — a row containing an `Adw.ToggleGroup` with two segments: "Stations" and "Favorites"
- **D-02:** Widget: `Adw.ToggleGroup` (native Adwaita segmented control, HIG-compliant)
- **D-03:** Switching views replaces the list content inline — no navigation, no page transitions
- **D-04:** Filter bar (provider/tag chips) is hidden or inactive when Favorites view is active (favorites are not filterable by station chips)

### Star Button
- **D-05:** Star button lives in the center column of the now-playing panel, to the left of the Stop button
- **D-06:** Icon state: `non-starred-symbolic` (outline) when not yet favorited; `starred-symbolic` (filled) when already in favorites
- **D-07:** Button is hidden (not just disabled) when there is no actionable ICY title (nothing playing, junk title, or YouTube stream without meaningful track title)
- **D-08:** Star state updates immediately on click (optimistic UI) — no loading state needed since DB write is synchronous

### Favorites Row Content
- **D-09:** Each row shows: primary label = track title; secondary label = "Station Name · Provider"
- **D-10:** No date/timestamp displayed in the row (not needed for v1.3)
- **D-11:** Trash icon button on the right side of each row — always visible, one tap removes the favorite immediately (no confirmation dialog)

### Duplicate Handling
- **D-12:** Deduplication key: `(station_name, track_title)` — if an identical favorite already exists, starring silently skips (no error, no toast). Star button remains filled.

### iTunes Genre Capture
- **D-13:** When the user stars a track, the genre is captured from the iTunes API response for that track title and stored in the DB. This requires either reading it from the in-flight cover art fetch result or making a second iTunes call at star time. Claude's Discretion: choose the simpler approach (likely: cache the last parsed iTunes result alongside `_last_cover_icy` so it's available at star-click time without a second API call).

### Claude's Discretion
- Exact widget hierarchy for the toggle row above the list (e.g., whether it's inside a `Gtk.Box` with margins or an `Adw.ActionRow`)
- Whether filter bar widgets are `set_visible(False)` or just `set_sensitive(False)` in Favorites view
- DB migration approach: `ALTER TABLE` for `favorites` table creation (same pattern as `icy_disabled`)
- Order of favorites list (insert order / created_at descending is reasonable default)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Data model & persistence
- `musicstreamer/models.py` — `Station` dataclass; new `Favorite` dataclass to be added
- `musicstreamer/repo.py` — `Repo` class; `db_init()` for schema; needs `add_favorite()`, `remove_favorite()`, `list_favorites()`, `is_favorited()` methods

### Now-playing panel (star button)
- `musicstreamer/ui/main_window.py` — center column layout (lines ~70–94); `_on_title` callback; `_on_cover_art` where iTunes result is available; `_play_station` and `_stop`
- `musicstreamer/cover_art.py` — `is_junk_title()` (gating), `_parse_artwork_url()` (genre capture requires reading iTunes JSON here)

### Station list / view toggle
- `musicstreamer/ui/main_window.py` — `_build_station_list()`, `empty_page`, `Gtk.Stack` for empty state; toggle group inserts above this area

### Prior UI patterns
- `musicstreamer/ui/edit_dialog.py` — `Adw.SwitchRow`, `Adw.MessageDialog` pattern (for reference, delete in Phase 12 does NOT need confirm dialog)

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `is_junk_title(icy_string)` in `cover_art.py` — already used for cover art gating; same check gates star button visibility
- `GLib.idle_add` pattern — established for all cross-thread UI updates; star button state update after async iTunes result must use this
- `Gtk.Stack` + named pages — used for logo/art fallback in now-playing; same pattern could be used if empty-favorites state needs an empty page

### Established Patterns
- `ALTER TABLE … ADD COLUMN` with try/except — migration pattern in `db_init()`; use same approach for `CREATE TABLE IF NOT EXISTS favorites`
- `GLib.markup_escape_text` on all `Adw.ActionRow` title/subtitle — required since ActionRow parses Pango markup
- Daemon thread + `GLib.idle_add(callback)` — cover_art.py threading model; follow if any async work needed at star time

### Integration Points
- `_on_title` closure in `_play_station` — where current ICY title string is available; star button visibility toggled here
- `_on_cover_art` in `MainWindow` — where iTunes API result arrives; cache genre here for star-click retrieval
- Center column `Gtk.Box` (lines ~70–94) — where star button is inserted (left of Stop button)
- List area in `MainWindow` — `Gtk.Stack` / scrolled window holding the station list; toggle group added above this

</code_context>

<specifics>
## Specific Ideas

- Star icon: `starred-symbolic` (filled, active state) and `non-starred-symbolic` (outline, inactive) — standard GNOME icon names, available in Adwaita icon theme
- User explicitly wants the icon to behave like standard app favorites: silhouette/outline when not favorited, filled when favorited
- Favorites view occupies the same sidebar area as the station list (from user note 2026-03-22: "separate view in the bottom half, same area as station list")
- Genre storage: iTunes API response includes `primaryGenreName` — capture this alongside artwork URL in `cover_art.py` and surface it for DB storage

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 12-favorites*
*Context gathered: 2026-03-30*
