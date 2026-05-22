# Phase 82: User-selected stream provider is honored on next Play - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning

<domain>
## Phase Boundary

When the user picks a non-default stream from the Now-Playing stream dropdown (e.g. Twitch on Lofi Girl, when the YT stream is the higher-quality default), the player must honor that selection on *subsequent* play actions — not just the immediate `currentIndexChanged` slot that already works. Today, every callsite that re-enters `Player.play(station)` rebuilds the failover queue via `order_streams()` (quality-first) and silently overrides the user's pick, so the next press of the play button (or station-list re-click while the same station is bound) resets to YT-first.

The fix is a **preferred-stream-id persistence layer**: the user's selection is saved on the station row, and `Player.play(station)` consults it to put the picked stream at the head of the failover queue. Failover semantics otherwise remain unchanged — if the user's stream fails, the player falls back through the rest of `order_streams`'s ordering as today.

Real-world repro: Lofi Girl with both YT and Twitch streams while the main Lofi Girl YT channel was down (2026-05-21). Selecting Twitch from the dropdown plays Twitch (current `_on_stream_selected` works), but the very next Play press re-attempts the expired YT link instead of staying on Twitch.

</domain>

<decisions>
## Implementation Decisions

### Persistence Layer
- **D-01:** User's stream selection is **per-station sticky, persisted in the DB**. Add a `preferred_stream_id INTEGER NULL` column on the `stations` table, FK to `streams.id` with `ON DELETE SET NULL` so dangling refs from stream deletions self-heal. Selection survives app restarts, station list re-clicks, and pause/resume cycles. Reason: the user explicitly wanted "remember next time I open Lofi Girl", not session-only.
- **D-02:** Selection is **set on every `_on_stream_selected` invocation**, including when the user picks back the original highest-quality stream. Always recording the current pick means `order_streams`'s ranking can shift in the future (e.g., a new higher-bitrate codec lands) without silently overriding a deliberate user choice.

### Fix Layer (where the preferred-stream logic lives)
- **D-03:** Fix at the **`Player.play(station)` layer**, NOT scattered across UI callsites. When `Player.play()` builds the failover queue, it first checks `station.preferred_stream_id`. If set AND the id resolves to a stream in `station.streams`, that stream goes to the head of the queue; the rest follow in `order_streams()` order. This single change covers every play entry point — play button, station-list re-click, sibling activation (Phase 64), similar activation (Phase 67), media-key play — because all of them route through `Player.play(station)` in `main_window.py:_on_station_activated` or `now_playing_panel.py:_on_play_pause_clicked`.
- **D-04:** `Player.play_stream(stream)` (the direct-play path used by `_on_stream_selected`) does NOT change. It already bypasses the queue (D-08 from earlier player work). It just becomes the reference pattern for how a user-picked stream should be played.

### Failover Behavior
- **D-05:** If the user-picked stream itself fails, **fall back through the rest of `order_streams`'s ordering** (current default `_try_next_stream` semantics). User's pick is "preferred first", not "only". Existing `_failover_timer` and `_handle_gst_error_recovery` flows stay unchanged. Reason: when the user's pick is also unavailable, having *something* play is better than stopping; the user can always re-pick.

### Out-of-Scope (within scope of D-05 default)
- **D-06:** No "stop and toast" mode, no "offer retry-with-default" toast button, no cross-device sync, no per-quality fallback policy beyond the existing `preferred_quality` kwarg on `Player.play`.

### Dropdown UX
- **D-07:** Behavior is **silent** — no pin icon, no "Using Twitch" tooltip, no "Reset to default" menu action. The combo's current text already shows the active selection; persistence is invisible-by-design. Reason: minimum visual noise, and the user opted for the no-extra-UI path.

### Migration
- **D-08:** Schema change requires a SQLite `user_version` bump and a forward-only migration in `musicstreamer/migration.py`. New column defaults to `NULL` — existing stations behave exactly as today until the user makes a pick. No backfill, no data rewrite.

### Claude's Discretion
- **Test fixture scope** — recommend a behavioral test that exercises the full repro path: insert a 2-stream station, pick the secondary stream via the equivalent of `_on_stream_selected`, call `Player.play(station)` again, assert the picked stream is at the head of `_streams_queue`. Plus a regression test for the failover path (picked stream errors → queue advances through the rest in `order_streams` order). Plus a source-grep drift-guard pinning the `preferred_stream_id` access in `Player.play()` (Phase 51/55/61/63/81 precedent).
- **Stream-id stability across re-imports** — researcher should confirm whether SomaFM / AudioAddict / GBS.FM imports use stable stream ids or rebuild them per re-import (e.g., Phase 74 wipe + re-import). If unstable, `ON DELETE SET NULL` on the FK silently resets the pick — which is acceptable behavior (next time the user has to re-pick).
- **Column naming** — `preferred_stream_id` is the working name; researcher/planner can pick a better one (`last_picked_stream_id`, `user_preferred_stream_id`, etc.) as long as the semantics match D-01.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Player and failover (D-03 / D-04 / D-05 surface)
- `musicstreamer/player.py:505` — `Player.play(station, preferred_quality=...)` — failover queue build; `preferred_stream_id` check goes here
- `musicstreamer/player.py:538` — `Player.play_stream(stream)` — direct stream play; pattern reference for "head-of-queue" behavior
- `musicstreamer/player.py:661-693` — `_on_gst_error` + `_handle_gst_error_recovery` — existing GST-error → `_try_next_stream` failover flow
- `musicstreamer/player.py:1024,1130` — `_play_youtube` + `_on_youtube_resolution_failed` — YT-specific resolution failure already advances queue via `_try_next_stream`
- `musicstreamer/stream_ordering.py:46` — `order_streams()` — unchanged sort; remains the fallback ordering after the user's pick

### Repo + schema (D-01 / D-08 surface)
- `musicstreamer/repo.py` — `Repo` class; needs `set_preferred_stream(station_id, stream_id)` setter + `Station` model needs `preferred_stream_id` field
- `musicstreamer/repo.py:441` — `Repo.list_stations()` (just modified in Phase 81) — must include `preferred_stream_id` in SELECT
- `musicstreamer/repo.py:678` — `Repo.list_favorite_stations()` (Phase 81) — same
- `musicstreamer/migration.py` — `user_version` bump + `ALTER TABLE stations ADD COLUMN preferred_stream_id INTEGER REFERENCES streams(id) ON DELETE SET NULL`
- `musicstreamer/repo.py` `@dataclass Station` definition — add `preferred_stream_id: Optional[int]` field

### UI hookup (D-02 surface)
- `musicstreamer/ui_qt/now_playing_panel.py:1281` — `_on_stream_selected` — call `repo.set_preferred_stream(station_id, stream_id)` after `_player.play_stream(s)`
- `musicstreamer/ui_qt/now_playing_panel.py:1038` — `_on_play_pause_clicked` — no direct change; benefits from Player-layer fix
- `musicstreamer/ui_qt/main_window.py:751` — `_on_station_activated` — no direct change; benefits from Player-layer fix
- `musicstreamer/ui_qt/now_playing_panel.py:1293` — `_sync_stream_picker` — verify it stays in sync when a sticky pick is auto-applied at play time

### Prior-phase precedents (drift-guard idiom + DB patterns)
- `.planning/phases/81-station-list-alphabetical-sorting-is-case-sensitive-a-z-then/81-01-PLAN.md` — Phase 81's source-grep drift-guard pattern (same idiom for `preferred_stream_id` access)
- `.planning/phases/70-*/` and `.planning/phases/64-*/` — prior stream-picker / sibling activation phases that flow through `_player.play(station)`
- `.planning/phases/74-*/` — SomaFM full-catalog wipe + re-import; relevant for "are stream ids stable" research question
- `.planning/PROJECT.md` §Key Decisions — drift-guard pattern (Phase 51 / 55 / 61 / 63 / 81 precedent)

No external ADRs or specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Player.play_stream(stream)` already implements "play exactly this stream at the head of the queue" (player.py:538). The `Player.play()` change is essentially "if `station.preferred_stream_id` resolves, behave like `play_stream` for the first item, then queue the rest via `order_streams` for failover."
- `Player.play(station, preferred_quality="...")` already has a precedent for biasing the head of the queue (the `preferred_quality` arg). Same pattern, different key (stream id vs quality string).
- `order_streams()` is pure and deterministic (player.py:55 import; stream_ordering.py:46) — no need to change it. The fix just *inserts* the user's pick at index 0 of the resulting list, then dedupes.
- `Repo` already has a `last_played_at` column + `update_last_played(station_id)` setter — same shape as the new `set_preferred_stream(station_id, stream_id)` will take.

### Established Patterns
- **Source-grep drift-guards:** Phases 51, 55, 61, 63, 81 all ship a regex-on-source test pinning a literal that must not silently disappear. Same idiom locks the `preferred_stream_id` lookup in `Player.play()`.
- **DB migration via `user_version` bump:** existing migrations in `musicstreamer/migration.py` follow a `PRAGMA user_version` → `ALTER TABLE` → bump pattern. Phase 82 is an additive column, so no data rewrite — purely forward migration.
- **FK with `ON DELETE SET NULL` for self-healing references:** the codebase already uses this pattern elsewhere (e.g., `stations.provider_id` FK behavior); reusing it for `preferred_stream_id` means stream deletions auto-clear stale picks.
- **Direct-play path bypasses failover queue:** `play_stream(stream)` already does this (D-08 from earlier work); the Phase 82 change is consistent with that prior decision.

### Integration Points
- `Player.play(station)` is called from: `main_window.py:_on_station_activated` (station-list activation, sibling activation via `_on_sibling_activated`, similar activation via `_on_similar_activated`), `now_playing_panel.py:_on_play_pause_clicked` (play button), media-key play handlers. ALL of these benefit from the single change inside `Player.play()` — no per-callsite touch required (D-03).
- `now_playing_panel.py:_on_stream_selected` is the ONE place that needs a new line: persist the pick to the repo after invoking `play_stream(s)`.
- `Station` dataclass: every Repo method that builds a `Station` (list_stations, list_favorite_stations, get_station, etc.) must include the new column in its SELECT and pass it through the dataclass constructor.

### MEMORY.md anchors
- `reference_musicstreamer_db_schema.md` — DB is `musicstreamer.sqlite3`; `stations.provider_id` FK semantics; JOIN-required patterns. Phase 82 adds one column; no JOIN-required changes for the lookup itself.
- `feedback_gstreamer_mock_blind_spot.md` — GStreamer mock tests pass through any `pipeline.emit(...)` call. For Phase 82, the Player-layer test should assert on `_streams_queue` ordering at the head, NOT on bus signals, to avoid the mock blind spot.
- `feedback_mirror_decisions_cite_source.md` — any "external precedent" claims in plan/PR must cite source + permalink. Phase 82's decisions are project-internal; no external mirrors needed.

</code_context>

<specifics>
## Specific Ideas

- User-reported repro fixture: **Lofi Girl** station with both YT and Twitch streams, while the main Lofi Girl YT channel was down (2026-05-21). The exact failure mode is: select Twitch from the dropdown → Twitch plays correctly → click Play (or re-click the station in the list) → player attempts the now-expired YT link instead of remembering Twitch.
- The 2026-05-21 incident also means the YT-resolution-failure path (`_on_youtube_resolution_failed` → `_try_next_stream`) is being exercised every time the user retries — confirming that failover *does* eventually recover to Twitch, but the user shouldn't have to wait through that loop on every Play press.
- Phase tone: behavioral fix with a small schema bump. Comparable in shape to Phase 74's import work (added/changed columns) but much smaller in scope — one column, one Player-layer check, one UI persistence call.

</specifics>

<deferred>
## Deferred Ideas

- **"Stop and toast" mode** (the strict-honor alternative to D-05) — would only ship if D-05 proves wrong in practice; collect telemetry first.
- **"Retry with default order" toast button** — same: defer until a user actually asks.
- **Pinned-stream UX cue** (icon next to dropdown when a non-default pick is active) — defer; current "silent" behavior is the explicit choice in D-07.
- **"Reset to default stream order" hamburger / right-click action** — defer; user can manually re-pick the highest-quality stream from the dropdown to achieve the same effect.
- **Cross-device sync of preferred-stream picks** — explicitly out of scope; no cloud sync surface exists.
- **Per-quality fallback policy** (e.g., "prefer the highest-quality stream of codec X") — different mental model from per-stream-id pick; defer until a real use case appears.
- **Bulk "clear all preferred-stream picks" admin action** — defer; not a real user need.

### Reviewed Todos (not folded)
None — discussion stayed within phase scope.

</deferred>

---

*Phase: 82-twitch-only-station-still-tries-to-play-youtube-stream-first*
*Context gathered: 2026-05-21*
