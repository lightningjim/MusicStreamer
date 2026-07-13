# Phase 96: Manual Refresh of Live-Stream URLs from Channel - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a **manual, per-station opt-in "re-sync live URL from channel"** capability for YouTube live-stream stations whose video IDs churn (the channel periodically restarts its 24/7 live streams, minting a new `watch?v=` URL each time, so saved stations go stale).

Yellow Brick Cinema (@YellowBrickCinema) is the motivating case, but the feature is **NOT YBC-specific** — Cafe BGM and other channels have the same problem. The capability is a generic **per-station flag (default OFF)** plus a **provider-level "Refresh live streams" review dialog** that re-scans the channel's currently-live streams and lets the user reconcile their flagged stations against reality (update / replace / drop / add).

**Scope anchor:** YouTube only (gated to YouTube URLs, reusing `yt_import.scan_playlist`). Twitch and arbitrary custom sites are explicitly out of scope (deferred to v3 — see Deferred Ideas).

This is the *proactive* counterpart to Phase 95, which fixed stale resolved-URL state *post-edit*. Here the user deliberately re-syncs against what is actually live on the channel.
</domain>

<decisions>
## Implementation Decisions

### Opt-in flag (generic, not YBC-specific)
- **D-01:** A **per-station boolean flag, default OFF** — "Re-sync live URL from channel" — marks a station as live-URL-churning and eligible for refresh. New schema column on `stations` via an idempotent additive migration in `repo.py:db_init()` (follow the existing `station_art_path` / Phase 89.1 additive-column pattern; existing rows default to NULL/false).
- **D-02:** The flag is set via a checkbox in `EditStationDialog`, **gated to YouTube URLs only** (enabled only when the station's URL is a YouTube watch/channel URL — mirror the YouTube/Twitch gating already used for the avatar "Refresh" button at `edit_station_dialog.py:1289-1295`). Non-YouTube stations cannot enable it.
- **D-03:** At flag-time (and refreshed on each successful re-sync), store the stream's **current YouTube title as a hidden "anchor"** on the station. The anchor is used ONLY to pre-order / hint suggestions in the manual-map dialog — it is NOT used to auto-apply anything (see D-05). The station's user-facing display name is independent and may be user-customized, so it is never the match key.

### Trigger & surface (Claude's discretion — user deferred this area)
- **D-04:** Primary surface is a **provider/channel-level "Refresh live streams"** action via a **sidebar right-click context menu on the provider row**. No provider context-menu exists today (`station_list_panel.py:354-368` returns early for non-station rows) — this phase introduces one. The action re-scans the channel and opens the review/resolve dialog operating over ALL flagged stations of that provider/channel at once. (A per-station "Refresh now" button may be added at planner discretion, but the review dialog is the real surface because drop/replace/add cases have no single owning station.)

### Stream matching — ALWAYS MANUAL MAP
- **D-05:** **No automatic title matching.** On refresh, the review dialog always shows the channel's currently-live streams (from `scan_playlist`) **side-by-side** with the user's flagged stations, and the user maps / drops / adds **every time**. The stored title anchor (D-03) only pre-orders or pre-suggests likely pairings; it never auto-applies a URL change. Rationale: titles drift and siblings collide; the user wants explicit control over which live stream replaces which station.

### Resolution actions available in the review dialog
- **D-06:** **Update URL via manual map** — user maps a flagged station to a currently-live stream; the station's stream URL (and the title anchor) is re-pointed in place. Preserve name (unless edited per D-08), tags, avatar, and any other streams on the station.
- **D-07:** The dialog must also support: **map a replacement** (a flagged station whose old stream is gone → an otherwise-unrelated new live stream); **drop/delete** a flagged station whose stream is gone with no replacement; and **add** a brand-new currently-live stream as a new station. (Motivating reality: the old stream can vanish entirely and be replaced by an unconnected new one.)

### Naming — EDITABLE PER ROW
- **D-08:** Each add/replace row in the review dialog exposes an **editable name field**, pre-filled with the live stream's current YouTube title (for new adds) or the existing station's current name (for replacements/remaps). The user decides the final name case-by-case. Custom names are never silently clobbered.

### Apply flow — REVIEW-AND-CONFIRM, CONSERVATIVE DEFAULTS
- **D-09:** Refresh is **review-and-confirm**, not silent. It reuses the async-worker + main-thread-persist pattern from the avatar refresh (`_AvatarFetchWorker` at `edit_station_dialog.py:134-193`): scan runs off the UI thread, results populate the dialog, persistence happens on the main thread on Apply.
- **D-10:** **Conservative defaults.** Because matching is fully manual (D-05), there is no auto-applied bucket. The dialog's safety posture: an **unresolved flagged station is left untouched** (URL unchanged, NEVER auto-deleted); **drops and new-stream adds are opt-in** (unchecked by default — the user must explicitly tick them); deletions always require an explicit tick. Nothing destructive or additive happens without deliberate user action. A summary of what will change is shown before Apply commits.

### Claude's Discretion
- Exact dialog layout (two-column map UI vs. row-per-station with a "currently-live" dropdown), and how the title anchor pre-orders suggestions.
- Whether to also add a per-station "Refresh now" affordance in EditStationDialog alongside the flag (D-04).
- Migration column name/type for the flag and the title anchor.
- Whether the flag and anchor live on `stations` or are derived; dedup interaction with `station_exists_by_url` (today's URL-based dedup at `yt_import.py:140` is what causes restarted streams to import as duplicates — the refresh path must update-in-place rather than insert).
- Exact provider/channel grouping key used to scope "all flagged stations of this channel."
</decisions>

<specifics>
## Specific Ideas

- "There are situations where the old stream is gone and a new stream has replaced it that is not connected otherwise" — the replace/drop/add actions (D-07) exist specifically for this; a refresh is not just a URL swap.
- Yellow Brick Cinema (@YellowBrickCinema) and Cafe BGM are the concrete channels driving this; treat them as instances of a generic class, not special-cased providers.
- Default-OFF is deliberate: most stations are stable; only the churning live channels get flagged.
</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

This project has no formal external spec/ADR docs for this phase. The behavior contract is **D-01..D-10 above**. Relevant source-of-truth code the planner/researcher must study:

### YouTube live-stream scanning
- `musicstreamer/yt_import.py` §`scan_playlist` (47-125) — enumerates a channel's currently-live streams via `extract_flat` + `_entry_is_live`; returns `{title, url, provider}`. Reuse for the refresh scan.
- `musicstreamer/yt_import.py` §`import_stations` (128-152) — current bulk-import + **URL-based dedup** (`station_exists_by_url`, line 140); this is exactly why restarted streams duplicate today. Refresh must update-in-place, not insert.
- `musicstreamer/yt_import.py` §`is_yt_playlist_url` (28-44) — URL/tab recognition; basis for the YouTube-only gate (D-02).
- **Landmine:** node_runtime threading (`build_js_runtimes(node_runtime)`, ~line 86) — YouTube extraction breaks under `.desktop` launchers without a resolved node runtime. Thread `check_node()` through any new scan path. See memory `yt-dlp-callsites-need-resolved-node-runtime`.

### Data model
- `musicstreamer/repo.py` — `stations` table (96-106), `station_streams` table (124-137), `providers` table (91-94); `insert_station` (886-896), `station_exists_by_url` (880-884), `list_streams` (490-498), `update_stream` (~564-572), `get_station` (682-712). Additive-migration pattern in `db_init()`.
- `musicstreamer/models.py` — `Station` (27-45) incl. `provider_id`/`provider_name`/`streams`/`provider_avatar_path`; `StationStream` (12-24). NOTE: known top-level-URL ↔ first-StationStream-URL duplication is Phase 97's problem — be aware but don't solve it here.

### Existing refresh/UI patterns to reuse
- `musicstreamer/ui_qt/edit_station_dialog.py` — `_AvatarFetchWorker` (134-193) async-worker template; `_on_refresh_avatar_clicked` (1631-1649) manual-refresh + bypass-gate pattern; YouTube/Twitch URL gating (1289-1295).
- `musicstreamer/ui_qt/import_dialog.py` — YouTube scan→checklist→import flow (329-416); the review dialog is a close cousin of this UI.
- `musicstreamer/ui_qt/station_list_panel.py` — context-menu wiring (354-368), currently station-only; provider-row context menu is new here (D-04).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `yt_import.scan_playlist(url, node_runtime=...)` — drop-in live-stream enumerator for the refresh scan.
- `_AvatarFetchWorker` + manual-refresh-button pattern in `EditStationDialog` — template for the async refresh worker and the per-station affordance.
- `import_dialog.py` YouTube tab (scan → checkable list → import) — close analog for the review/resolve dialog UI.
- Additive idempotent migration pattern in `repo.py:db_init()` — for the flag + title-anchor columns.

### Established Patterns
- Off-UI-thread scan/fetch via QThread worker, main-thread persistence (avatar refresh, import workers).
- URL-based dedup (`station_exists_by_url`) — the refresh must explicitly bypass/replace this to update-in-place instead of duplicating.
- Provider rows in the sidebar are currently non-actionable — adding a provider context menu is net-new UI.

### Integration Points
- New `stations` columns (flag + title anchor) via `db_init()` migration.
- New provider-row right-click action in `station_list_panel.py` → opens the refresh review dialog.
- Refresh persistence calls into `repo` (`update_stream` for remaps, `insert_station` for adds, station delete for drops).
- Node-runtime resolution (`check_node()`) threaded into the scan path (landmine).
</code_context>

<deferred>
## Deferred Ideas

- **Pluggable, custom-site-aware live-URL resolver** — extend live-URL re-sync beyond YouTube to Twitch and arbitrary sites via a config-driven plugin process (custom site awareness, easy to update without hardcoding resolvers). User explicitly scoped this to a **v3 milestone** todo. Out of scope for Phase 96 (YouTube-only).
- Auto/scheduled refresh on app launch — not in scope; refresh stays a deliberate manual action this phase.
- Solving the top-level-URL ↔ first-StationStream-URL duplication — that is **Phase 97**, not here.
</deferred>

---

*Phase: 96-manual-refresh-of-yellow-brick-cinema-provider-with-what-is-*
*Context gathered: 2026-06-20*
