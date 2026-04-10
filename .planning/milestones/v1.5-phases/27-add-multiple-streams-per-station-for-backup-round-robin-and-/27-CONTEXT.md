# Phase 27: Add multiple streams per station for backup/round-robin and quality selection - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend the station model from a single URL to multiple stream URLs per station. This phase covers the data model, migration, editor UI for managing streams, quality tier definitions, and import flow updates. Actual failover/round-robin playback logic is Phase 28.

</domain>

<decisions>
## Implementation Decisions

### Stream Data Model
- **D-01:** New normalized `station_streams` table with columns: `id`, `station_id` (FK), `url`, `label` (free text), `quality` (tier), `position` (integer for ordering), `stream_type` (hint: shoutcast/youtube/hls), `codec` (MP3/AAC/OPUS/FLAC/etc)
- **D-02:** Migrate existing `stations.url` column data into `station_streams` (one row per existing station at position 1). Remove `stations.url` column after migration. Single source of truth in `station_streams`.

### Station Editor UX
- **D-03:** "Manage Streams" button in the station editor opens a separate sub-dialog for adding/editing/removing/reordering streams
- **D-04:** Stream reorder method is Claude's discretion (up/down buttons or drag-and-drop — pick what fits GTK4/Libadwaita best)

### Quality Tiers
- **D-05:** Quality tiers use fixed presets (hi/med/low) plus a custom text option for edge cases (e.g., "320kbps", "FLAC", "Mobile")
- **D-06:** Global "preferred quality" setting in addition to position-based ordering. Position is the default play order; global quality preference can override when quality tiers are set on streams.

### Import Behavior
- **D-07:** AudioAddict import creates one station per channel with all quality variants (hi/med/low) as separate streams, each with appropriate quality tier and position
- **D-08:** Radio-Browser Discovery saves a single stream per action. User can either "Add as new station" or "Add stream to existing station"
- **D-09:** Radio-Browser attach-to-existing uses auto-detection (match by similar name/provider) with manual override to pick any existing station. When no match is detected, defaults to new station.

### Claude's Discretion
- Stream reorder UX (D-04) — up/down buttons vs drag-and-drop
- Exact sub-dialog layout for stream management
- Migration strategy details (ALTER TABLE vs table recreation)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Data Model
- `musicstreamer/models.py` — Current Station dataclass (url field to be removed)
- `musicstreamer/repo.py` — Current schema, all station CRUD methods referencing `url`

### Player
- `musicstreamer/player.py` — `play()` method reads `station.url` directly; must be updated to get URL from streams

### Import Flows
- `musicstreamer/aa_import.py` — AudioAddict import; currently imports single quality; needs multi-quality stream creation
- `musicstreamer/radio_browser.py` — Radio-Browser discovery; needs attach-to-existing flow
- `musicstreamer/yt_import.py` — YouTube import; single URL per station (unchanged behavior but must use new table)

### UI
- `musicstreamer/ui/` — Station editor dialog; needs "Manage Streams" button and streams sub-dialog

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Repo` class pattern — all DB access through repo methods; new stream CRUD follows same pattern
- `db_init()` migration pattern — uses ALTER TABLE with try/except for idempotent column additions; extend for new table
- `settings` table — can store global preferred quality setting via existing `get_setting`/`set_setting`
- Station editor dialog — existing form layout provides the anchor point for "Manage Streams" button

### Established Patterns
- SQLite with `sqlite3.Row` row factory and manual SQL
- Dataclasses for models (`Station`, `Provider`, `Favorite`)
- `GLib.idle_add` for cross-thread UI updates
- `ThreadPoolExecutor` for bulk import operations

### Integration Points
- `Player.play(station)` — currently reads `station.url`; must resolve to a stream URL (Phase 28 handles failover logic, but Phase 27 must provide at least "get first/preferred stream URL")
- `station_exists_by_url()` — dedup check used by imports; must query `station_streams.url` instead
- `insert_station()` — must also create stream rows
- `update_station()` — url parameter must route to stream table

</code_context>

<specifics>
## Specific Ideas

- AudioAddict already provides hi/med/low quality PLS URLs per channel — leverage this directly to populate all three stream rows per station
- Radio-Browser often lists multiple entries for the same station (different mirrors/bitrates/regions) — the attach-to-existing flow addresses this real-world pattern
- Codec field captures what AudioAddict and Radio-Browser metadata already provide (e.g., AAC, MP3)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 27-add-multiple-streams-per-station-for-backup-round-robin-and*
*Context gathered: 2026-04-08*
