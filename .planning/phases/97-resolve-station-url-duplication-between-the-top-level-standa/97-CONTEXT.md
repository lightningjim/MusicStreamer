# Phase 97: Resolve station URL duplication - Context

**Gathered:** 2026-06-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Unify the station-URL editing experience to a single source of truth so the "top-level standard URL" (used for fetch/metadata) and the "first StationStream URL" (used for playback) are never maintained in two places.

**Key finding from scouting:** The *database* is already single-source. The legacy `stations.url` column was migrated away into `station_streams.url` (see `repo.py` lines 208–265). The duplication that this phase targets lives entirely in the **edit dialog** (`edit_station_dialog.py`):

- The prominent top **"URL:" field** (`url_edit`) is what the metadata/fetch logic reads *live* (unsaved) — iTunes/channel avatar fetch, Twitch provider derivation, AA sibling detection, YouTube channel-scan toggle, Phase-96 live-resync.
- The **first row of the streams table** is what actually persists and drives playback.
- Both seed from `streams[0].url` on load (`edit_station_dialog.py:652`), but on **save only the table persists** (`edit_station_dialog.py:1828–1878`) — `url_edit` is never written back. So the user must edit the URL in two places, and editing only one silently drifts metadata away from playback.

Scope = the edit flow plus the read sites that consume `url_edit`. The DB schema work is limited to adding a canonical-stream marker (see D-04). No re-migration of the existing single-source URL storage.

</domain>

<decisions>
## Implementation Decisions

### Source of truth (which UI surface owns the URL)
- **D-01:** Remove the top **"URL:" field** (`url_edit`) from the edit dialog entirely. The **streams table is the sole URL editor.** All metadata/derivation code currently reading `url_edit.text()` is rewired to read from the table instead.
- **D-02:** Metadata operations read the **live (unsaved) cell text** of the canonical stream's table row — preserving today's interactive behavior where avatar / siblings / channel-scan toggle / provider derivation react as the user types (not only after Save).
- **D-03:** The table **auto-creates an editable primary row** when a station has no streams (new station) or when the dialog opens with none, so the common single-stream case stays one-step (no "Add stream" click required to enter the first URL).

### Multi-stream mapping (which stream is "primary")
- **D-04:** Introduce a **new, pinned "canonical/primary" marker** on a stream (e.g. a star/radio control on the row). It **auto-defaults to the first stream** when a station is created, but once set it **stays pinned through reordering** (it does NOT follow row position). This is a **new, distinct field** — separate from Phase-82 `preferred_stream_id`.
- **D-05:** The canonical marker anchors the **canonical station URL + all metadata**; Phase-82 `preferred_stream_id` continues to control **which stream plays**. The two are independent. (For new/typical single-stream stations they coincide.)

### Metadata vs playback coupling
- **D-06:** Divergence between the canonical (metadata) stream and the preferred (playback) stream on multi-stream stations is **allowed silently — no warning or guard.** For typical single-stream stations they are the same stream.
- **D-07:** **All** metadata/derivation consumers key off the single canonical stream URL uniformly — avatar fetch, Twitch provider derivation, YouTube channel-scan toggle, Phase-96 live-resync anchor, **and** AA sibling detection. One rule, matching today's "everything read the single top URL" behavior.

### Claude's Discretion
- Exact widget/control used for the canonical marker (star vs radio button vs context action) and its placement in the streams table.
- Precise DB representation of the canonical marker (e.g. `stations.canonical_stream_id` FK vs a `station_streams.is_canonical` boolean) — planner/researcher to choose, with a migration that defaults existing stations' canonical to their position-1 stream.
- Exact mechanism for wiring the metadata consumers to the live canonical table cell.

</decisions>

<specifics>
## Specific Ideas

- The pain point in the user's words: the same URL is maintained in two places, forcing duplicate edits; the two are "expected to always be identical." The fix is to make the streams table the one place URLs live, with an explicit canonical marker selecting the metadata anchor.
- Canonical marker should feel like a lightweight pin, defaulting sensibly (first stream) so single-stream users never think about it.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs or ADRs exist for this phase (ROADMAP.md lists no `Canonical refs:` line for Phase 97). Requirements are fully captured in the decisions above. Key code touchpoints (current state, from scouting):

### Edit flow (primary change surface)
- `musicstreamer/ui_qt/edit_station_dialog.py` — `url_edit` definition (431, 444), load seeding from `streams[0].url` (652), live metadata reads of `url_edit.text()` (832 siblings, 1057 AA exclusion, 1318/1334/1350/1410 YT channel-scan toggle, 1526, 1684, 1789 Twitch provider derive, 1916 avatar fetch), dirty-state snapshot (754), save loop that persists ONLY the streams table (1828–1878). This is where the top field is removed and the canonical marker is added.

### Data model & persistence
- `musicstreamer/models.py` — `Station` (28–48, has NO top-level `url`), `StationStream` (13–24). Add canonical-marker field here.
- `musicstreamer/repo.py` — `station_streams` schema (124–137), legacy `stations.url` migration that already unified storage (208–265), `insert_stream`/`update_stream`/`list_streams`/`prune_streams`/`reorder_streams`, `get_station`/`list_stations`. Add canonical-marker column + setter + migration here.

### Metadata / read consumers to rewire (D-07)
- `musicstreamer/url_helpers.py` — AA sibling detection reads `st.streams[0].url` (216, 358).
- `musicstreamer/player.py` — playback ordering via `order_streams(station.streams)` + `preferred_stream_id` (757–786) — must keep using preferred, NOT canonical (D-05).
- `musicstreamer/ui_qt/live_refresh_dialog.py` — `streams[0].url` reads (271, 455, 613).
- `musicstreamer/ui_qt/station_filter_proxy.py` — `streams[0].url` (179).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `repo.list_streams()` / `update_stream()` / `insert_stream()` / `reorder_streams()` / `prune_streams()` — existing stream CRUD; extend with a canonical-marker setter rather than overloading `update_station`.
- Phase-82 `preferred_stream_id` + `order_streams()` — established pattern for per-station sticky stream selection; the canonical marker is a parallel concept (metadata anchor) that should reuse the same FK-on-station + dedicated single-column setter shape.
- Phase-96 single-column setters (`set_live_url_syncs_from_channel`, `set_live_url_title_anchor`) — the precedent for "NEVER update_station for these" (Pitfall 1); the canonical-marker setter should follow it.

### Established Patterns
- Streams table (`streams_table`, `_COL_URL=0`, etc.) already supports per-row editing, positions, and reorder — the canonical marker is an added column/affordance, not a new table.
- DB is single-source for URL storage already; this phase resolves the *UI/derivation* duplication, not storage.

### Integration Points
- The edit dialog's save path (`_on_save`) writes streams and Phase-96 flags — the canonical marker persists in the same save transaction.
- All metadata consumers (avatar, provider derive, siblings, YT scan, live-resync) currently funnel through `url_edit.text()`; they converge to a single "canonical stream URL" accessor after this phase.

</code_context>

<deferred>
## Deferred Ideas

- **New-station entry flow** — offered as a discussion area but not selected. D-03 (auto-create primary row) already covers the core ergonomic; any further new-station URL-entry polish can be addressed in planning or a later tweak.
- No warning/guard UI for canonical-vs-playback divergence (D-06 chose silent) — could revisit if multi-stream users report confusion.

</deferred>

---

*Phase: 97-resolve-station-url-duplication-between-the-top-level-standa*
*Context gathered: 2026-06-23*
