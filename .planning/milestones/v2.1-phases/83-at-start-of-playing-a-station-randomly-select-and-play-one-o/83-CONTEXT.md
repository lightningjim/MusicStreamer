# Phase 83: At start of playing a SomaFM station, randomly select and play one of its prerolls - Context

**Gathered:** 2026-05-22
**Status:** Ready for planning

<domain>
## Phase Boundary

When the user starts playing a SomaFM station, the player must randomly pick one of that station's prerolls (short station-ID m4a clips from `api.somafm.com/channels.json`'s `preroll[]` array) and play it before transitioning gaplessly into the station's actual stream. Stations whose `preroll[]` is empty (the majority — e.g. Seven Inch Soul) behave exactly as today.

The integration point is `Player.play(station)` — the single funnel all play paths route through (station-list activation, sibling/similar activation, Play button, media-key play). Preroll lookup, throttle gate, random selection, and the playbin3 about-to-finish handoff all live inside that one method (mirrors Phase 82 D-03's "fix at the Player layer" principle).

Real-world reference: SomaFM Beat Blender (`api.somafm.com/channels.json`) ships 3 preroll URLs (`https://somafm.com/prerolls/beatblender/BeatBlenderID{1,2,3}.m4a`), each ~5s. Picking randomly mirrors real SomaFM radio behavior.

</domain>

<decisions>
## Implementation Decisions

### Preroll storage (where the URLs live)
- **D-01:** Prerolls live in the **database**, in a dedicated `station_prerolls` table. Schema: `(id INTEGER PK, station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE, url TEXT NOT NULL, position INTEGER NOT NULL)`. Mirrors the `station_streams` pattern (Phase 47/74) — additive table, no `ALTER TABLE stations`. Reason: offline-clean (no network at play time), simple random pick via `ORDER BY RANDOM() LIMIT 1`.
- **D-02:** `soma_import.fetch_channels()` is extended to capture each channel's `preroll[]` array. `soma_import.import_stations()` is extended to insert one `station_prerolls` row per preroll URL after the station/streams insert succeeds.
- **D-03:** Pre-Phase-83 SomaFM stations already in the user's library get prerolls via **lazy on-demand backfill**, not eager migration. The schema migration creates `station_prerolls` empty; the first time the user plays a SomaFM station with zero stored prerolls, a background fetch hits `api.somafm.com/channels.json`, locates that channel by `slug` (the SomaFM `id` matches MusicStreamer's per-provider slug — Phase 74 idiom), and inserts any prerolls it finds. **The play itself does not block on this fetch** (see D-13).
- **D-04:** **No empty-marker sentinel for "channel genuinely has no prerolls" vs "fetch never attempted"**, ON SECOND THOUGHT — yes, distinguish them. Add a `prerolls_fetched_at INTEGER NULL` column on `stations` (epoch seconds). On a successful on-demand fetch (even one that returns 0 prerolls for the channel), set `prerolls_fetched_at = now`. The on-demand backfill gate becomes: `if station has 0 prerolls AND prerolls_fetched_at IS NULL → schedule fetch`. This prevents hammering the SomaFM API every play for SomaFM stations that legitimately have no prerolls (the majority).

### Playback transition (preroll → stream handoff)
- **D-05:** Use **playbin3's `about-to-finish` signal** for gapless transition. Implementation outline inside `Player.play(station)`:
  1. Build `_streams_queue` exactly as today (Phase 82 preferred-stream + `order_streams`).
  2. If preroll gate passes (D-11/D-12), randomly select one preroll URL.
  3. Set playbin3 URI to the preroll URL.
  4. Connect a one-shot `about-to-finish` handler that sets playbin3's next URI to `_streams_queue[0]`'s URL (via the existing stream URL extraction path — YouTube/Twitch streams that need resolution still need their normal resolve dance; preroll → simple-HTTP-stream handoff is the easy case but YT/Twitch still has to be wired through).
  5. After the handoff fires, disconnect the handler. The pipeline is now playing the station stream as if `_try_next_stream()` had selected `_streams_queue[0]` directly.
- **D-06:** `_streams_queue` is **not modified** by preroll logic — the queue holds station streams only, exactly as today. Preroll URLs never enter the failover queue. Reason: a 404 preroll shouldn't cause us to give up on the actual station stream; reusing the failover queue would create wrong semantics ("if this fails try next" — but the next isn't another preroll, it's the station's primary stream, which we want to reach anyway).
- **D-07:** **Now Playing display during preroll:** show the **station name** in the title bar; suppress whatever ICY-metadata or m4a tag the preroll might emit. Reason: the preroll is ~5s of "This is Beat Blender on SomaFM" voiceover — exposing the m4a's title tag would create UI flicker for no user benefit. Practical hook: the existing title-changed pipeline runs on bus tag messages; gate tag emissions when `_preroll_in_flight = True` (or equivalent). Researcher/planner pick the exact mechanism.
- **D-08:** **User controls during preroll behave normally.** Pause freezes the preroll mid-clip; Stop tears it down; Resume continues the preroll from where it paused. No special-case logic, no "skip preroll" affordance — prerolls are ~5s so a skip button is overkill. Re-pressing Play after a Stop (which re-enters `Player.play(station)`) re-evaluates the throttle gate (D-11/D-12); if still inside the window, no preroll the second time.

### Failover during/after preroll
- **D-09:** If the **preroll URL fails** (bus error, network timeout, 404, EOS before about-to-finish fires) — cancel the preroll, log a warning, and immediately call `_try_next_stream()` to start the station's actual stream (`_streams_queue[0]`). User experience: a slightly faster intro than expected, nothing else. **No retry of a different preroll** — keep it simple; a missing preroll shouldn't double the time-to-stream.
- **D-10:** If the **station's first stream fails after the preroll handoff** — `_try_next_stream` advances normally through `_streams_queue[1]`, `_streams_queue[2]`, etc., exactly as today. Preroll never replays during failover recovery (state guard: preroll already consumed for this `Player.play()` call).

### Trigger / throttle (when does a preroll play)
- **D-11:** **Provider gate:** Player.play consults `station_prerolls` ONLY when `station.provider_name == "SomaFM"`. Non-SomaFM stations skip the preroll codepath entirely, even if some other future import populates `station_prerolls` rows. Reason: scope explicit per the phase title; opens cleanly later by relaxing the gate. The literal string `"SomaFM"` (Phase 74 D-02 — CamelCase, no space, no period) is the discriminator.
- **D-12:** **Throttle gate:** a **global** in-memory `self._last_preroll_played_at: float | None = None` on `Player`. If the throttle window has not elapsed (default **10 minutes** — matches real SomaFM station-ID cadence and dampens rapid station-flipping), the preroll is suppressed and play proceeds directly to `_try_next_stream()`. The timestamp is updated when the preroll **starts playing** (not when about-to-finish fires), so a rapid replay press within the window is suppressed even if the prior preroll hasn't fully finished. Resets on app restart so a fresh launch always feels like "radio coming on."
- **D-13:** **Background fetch race:** if `Player.play()` sees a SomaFM station with 0 stored prerolls and `prerolls_fetched_at IS NULL` (D-04), it kicks off the background fetch but **does NOT wait for it**. The current play goes straight to the stream (no preroll this time). The fetch populates the DB so the **next** time the user plays this station (after the throttle window elapses) a preroll may play. No blocking, no UI delay, no timeout-based wait.

### Test coverage
- **D-14:** Behavioral tests live in `tests/test_player.py` (and a new `tests/test_soma_import.py` segment for the import-time preroll capture). Required tests:
  1. SomaFM station with ≥1 preroll in DB + throttle window expired → playbin3 URI is the preroll, `about-to-finish` is connected, queue is built but not played yet.
  2. SomaFM station with prerolls + throttle window NOT expired → playbin3 URI is the stream, no preroll path taken.
  3. SomaFM station with 0 prerolls and `prerolls_fetched_at IS NULL` → background fetch is scheduled, play proceeds to stream, no block on fetch.
  4. SomaFM station with 0 prerolls and `prerolls_fetched_at IS NOT NULL` → no fetch scheduled, play proceeds to stream.
  5. Non-SomaFM station with rows in `station_prerolls` (synthetic) → preroll codepath is bypassed via provider gate.
  6. `about-to-finish` handler fires → next URI is set to `_streams_queue[0]`.
  7. Preroll bus error → preroll is cancelled, `_try_next_stream()` is called for `_streams_queue[0]`.
  8. **Source-grep drift-guard** pinning the preroll-selection access in `Player.play()` (Phase 51/55/61/63/81/82 idiom) — pins both the `provider_name == "SomaFM"` literal AND the preroll lookup so refactors that silently drop one or the other fail loudly. Anchored in MEMORY: `feedback_gstreamer_mock_blind_spot.md` — drift-guard assertions go on `_streams_queue`/URI-set call args, NOT on bus signals.

### Migration
- **D-15:** Schema change requires a SQLite `user_version` bump and a forward-only migration in `musicstreamer/migration.py`:
  ```sql
  CREATE TABLE IF NOT EXISTS station_prerolls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    position INTEGER NOT NULL,
    FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
  );
  ALTER TABLE stations ADD COLUMN prerolls_fetched_at INTEGER;
  ```
  Existing SomaFM stations have `prerolls_fetched_at NULL` post-migration → they qualify for lazy backfill (D-03/D-04).

### Claude's Discretion
- **Stream-URL extraction inside the about-to-finish handler:** the YouTube and Twitch resolution dance currently runs inside `_try_next_stream` / `_play_youtube` / `_resolve_twitch`. The about-to-finish callback runs on GStreamer's streaming thread — calling Qt/PySide signals from there requires queued connections (the codebase already does this for `_try_next_stream_requested` per player.py:261). Researcher/planner should confirm whether the cleanest pattern is: about-to-finish marshals a "preroll done" signal to the main thread, which then calls `_try_next_stream` (treating the preroll-end as a synthetic queue-head completion), OR set the next URI to a placeholder and let the existing resolve path fire on the actual stream. The first is closer to existing patterns.
- **Random selection algorithm:** `random.choice(list_of_prerolls)` from Python's stdlib `random` module is sufficient. No need for seeding, weighted selection, or "avoid recent repeat" tracking — the user explicitly wanted random with no memory.
- **Preroll URL fetch path** (the m4a itself): SomaFM's preroll URLs are direct https (`https://somafm.com/prerolls/...`). playbin3 handles HTTPS via souphttpsrc. No special source element selection needed.
- **Drift-guard literals to pin:** at minimum, the string `"SomaFM"` in `Player.play()`'s gate AND a stable token in the preroll-selection block (e.g. `station_prerolls` table name or `_last_preroll_played_at` attribute name).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### SomaFM API surface
- `https://api.somafm.com/channels.json` — channels endpoint; each channel object includes a `preroll: [...]` array of m4a URLs (empty for most channels). Live sample shows Beat Blender has 3 prerolls; Seven Inch Soul has 0.
- `musicstreamer/soma_import.py:174` — `fetch_channels(timeout)` — must be extended to capture each channel's `preroll[]` and include it in the returned channel dict alongside `id/title/description/image_url/streams`.
- `musicstreamer/soma_import.py:256` — `import_stations(channels, repo, on_progress)` — must be extended to insert `station_prerolls` rows per imported channel (mirror the per-stream insertion pattern with try/except per-channel wrapper for crash resilience — Phase 74 D-15).
- `musicstreamer/soma_import.py:299-303` — `provider_name="SomaFM"` literal — the EXACT discriminator string that D-11's provider gate must match.

### Player and pipeline (D-05/D-06/D-07/D-08/D-09/D-10/D-11/D-12/D-13 surface)
- `musicstreamer/player.py:505` — `Player.play(station, ...)` — the single funnel; preroll logic gates and dispatches here, BEFORE the existing `_streams_queue` build at line 526 (preroll setup wraps around it).
- `musicstreamer/player.py:521-547` — current Phase 82 preferred-stream + `order_streams` queue-build block — preroll logic must NOT mutate `_streams_queue`; it sits alongside.
- `musicstreamer/player.py:549` — `Player.play_stream(stream)` — direct-play path; preroll logic does NOT trigger here (this is the `_on_stream_selected` path, not "start of playing a station").
- `musicstreamer/player.py:261-263` — `_try_next_stream_requested = Signal()` — existing queued-signal pattern for marshaling from GStreamer threads to the main thread. Preroll's about-to-finish handoff likely uses the same idiom (Claude's Discretion).
- `musicstreamer/player.py:404-405` — `_try_next_stream_requested.connect(_try_next_stream, QueuedConnection)` — pattern reference.
- `musicstreamer/player.py:297` — `self._pipeline = Gst.ElementFactory.make("playbin3", "player")` — playbin3 supports `about-to-finish` (GStreamer canonical gapless signal).
- `musicstreamer/player.py:864` — top-level playbin3 state-change message filter — preroll-state tracking must not conflict with the existing PLAYING-detection logic.
- `musicstreamer/player.py:891` — volume re-application on PLAYING — applies to preroll AND stream transitions; no change required, but be aware the preroll → stream handoff via about-to-finish is internal to playbin3 and may not fire a fresh PLAYING transition.

### Repo + schema (D-01/D-03/D-04/D-15 surface)
- `musicstreamer/repo.py:99-105` — `stations` CREATE TABLE — must add `prerolls_fetched_at INTEGER` column.
- `musicstreamer/repo.py:441` — `Repo.list_stations()` — must SELECT `prerolls_fetched_at` and include in returned `Station` dataclass (analogous to Phase 82's `preferred_stream_id` field addition).
- `musicstreamer/repo.py:678` — `Repo.list_favorite_stations()` — same.
- `musicstreamer/repo.py:453,490` — `get_station` SELECT queries — same.
- `musicstreamer/repo.py` `@dataclass Station` — add `prerolls_fetched_at: Optional[int] = None`.
- `musicstreamer/repo.py` — needs new methods: `insert_preroll(station_id, url, position)`, `list_prerolls(station_id) -> list[Preroll]` (or just `list[str]` of URLs), `set_prerolls_fetched_at(station_id, ts)`. Consider whether `@dataclass StationPreroll` is needed or if `list[str]` URLs is sufficient (the player only needs URLs).
- `musicstreamer/migration.py` — `user_version` bump + the two DDL statements from D-15.

### Prior-phase precedents
- `.planning/phases/82-twitch-only-station-still-tries-to-play-youtube-stream-first/82-CONTEXT.md` — Phase 82's `Player.play(station)`-layer fix pattern; same "single integration point" principle. Read this before designing the preroll gate.
- `.planning/phases/82-twitch-only-station-still-tries-to-play-youtube-stream-first/82-01-PLAN.md` / `82-02-PLAN.md` — schema migration + `Player.play` modification idiom (additive column, no data rewrite).
- `.planning/phases/74-*/` — SomaFM full-catalog wipe + re-import; relevant for "how is `soma_import.import_stations` structured" and the per-channel try/except wrapper idiom. Confirms `provider_name="SomaFM"` is the stable identifier.
- `.planning/phases/47-*/` — `station_streams` schema precedent; same shape as new `station_prerolls` table.
- `.planning/phases/81-*/81-01-PLAN.md` — source-grep drift-guard idiom (latest precedent).
- `.planning/PROJECT.md` §Key Decisions — drift-guard pattern (Phase 51/55/61/63/81/82 precedent).

### MEMORY anchors
- `feedback_gstreamer_mock_blind_spot.md` — pipeline mocks pass through any `pipeline.emit(...)` call. Drift-guard for D-14 MUST assert on URI / `_streams_queue` / call-arg state, NOT on bus signals or `pipeline.emit` invocations.
- `reference_musicstreamer_db_schema.md` — DB is `musicstreamer.sqlite3`; `stations.provider_id` FK semantics; JOIN-required patterns. The new `station_prerolls.station_id` FK uses the same `ON DELETE CASCADE` self-healing approach (Phase 47 idiom).

No external ADRs or specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `soma_import.fetch_channels()` (soma_import.py:174) — already parses `channels.json`; the `preroll` field is read by simply adding `"preroll_urls": ch.get("preroll", [])` to the channel dict it returns (one line in the existing loop at line 234).
- `soma_import.import_stations()` (soma_import.py:256) — already has the per-channel try/except + rollback pattern (Phase 74 D-15 / REVIEW CR-04). Preroll insertion fits as another step inside that block.
- `playbin3.about-to-finish` — GStreamer's canonical gapless signal; perfect for preroll → stream. The pipeline (`Player._pipeline`, player.py:297) is already a playbin3 instance.
- `Repo.update_last_played(station_id)` pattern — same shape as needed `Repo.set_prerolls_fetched_at(station_id, ts)`.
- `Player._try_next_stream_requested` queued signal (player.py:261-263, 404-405) — exact pattern for marshaling preroll's about-to-finish callback from GStreamer's streaming thread to the main thread.

### Established Patterns
- **Source-grep drift-guards:** Phases 51/55/61/63/81/82 all ship a regex-on-source test pinning a literal that must not silently disappear. Same idiom locks both `"SomaFM"` and the preroll-selection token in `Player.play()`.
- **Additive schema via `user_version` bump:** `musicstreamer/migration.py` follows `PRAGMA user_version` → DDL → bump pattern. Phase 83 is one new table + one nullable column — pure forward migration, no data rewrite.
- **FK with `ON DELETE CASCADE` for child rows:** `station_streams` uses this (Phase 47); `station_prerolls` does too. Deleting a station cleans up its prerolls.
- **Per-channel try/except in importers:** Phase 74 D-15 wraps each `for ch in channels` body in try/except so one malformed channel doesn't kill the whole import. Preroll insertion lives inside the same block.

### Integration Points
- `Player.play(station)` (player.py:505) — gate (D-11 SomaFM check), throttle check (D-12), random preroll pick (D-05.2), URI set + about-to-finish handler attach (D-05.3-5).
- `soma_import.fetch_channels` (soma_import.py:234) — extend returned channel dict with `preroll_urls: list[str]`.
- `soma_import.import_stations` (soma_import.py:273+) — insert `station_prerolls` rows after the per-stream insert loop.
- `musicstreamer/repo.py` — new methods `insert_preroll`, `list_prerolls`, `set_prerolls_fetched_at`; extend `Station` dataclass + every `Station`-building SELECT (list_stations, list_favorite_stations, get_station).
- `musicstreamer/migration.py` — new DDL block.
- (No UI integration points — D-07 keeps the preroll invisible to Now Playing display logic except for the title-tag suppression hook.)

### MEMORY.md anchors
- `feedback_gstreamer_mock_blind_spot.md` — pipeline mocks pass through any `pipeline.emit(...)` call. For Phase 83, behavioral tests (D-14 tests 1-7) assert on URI / `_streams_queue` / call-arg state; the source-grep drift-guard (D-14 test 8) closes the mock-blind-spot for the preroll-gate literals.
- `reference_musicstreamer_db_schema.md` — DB path is `musicstreamer.sqlite3`. New `station_prerolls.station_id` FK to `stations.id` follows existing FK conventions.

</code_context>

<specifics>
## Specific Ideas

- **Reference channel:** Beat Blender (SomaFM `id="beatblender"`) ships 3 preroll URLs: `https://somafm.com/prerolls/beatblender/BeatBlenderID{1,2,3}.m4a`. Each is ~5s of voiceover ("This is Beat Blender on SomaFM"). Use this as the manual UAT fixture — pick Beat Blender, click Play, hear the station ID, then the deep-house stream.
- **Reference channel with NO preroll:** Seven Inch Soul (SomaFM `id="7soul"`) has `preroll: [ ]` — verify Player.play() goes straight to the stream with no delay (D-04 prerolls_fetched_at gate kicks in post-fetch).
- **Throttle UAT:** Play Beat Blender → hear preroll → stop → immediately replay Beat Blender → should NOT hear preroll (within 10-min window). Wait 10 minutes → replay → should hear preroll again.
- Phase tone: medium-sized — one new table, one new column, one ~30-line block in `Player.play`, soma_import extension, on-demand fetch path, eight behavioral tests + drift-guard. Comparable in shape to Phase 82 plus an importer extension.

</specifics>

<deferred>
## Deferred Ideas

- **"Skip preroll" UX affordance** (button or hotkey to bypass the ~5s clip) — defer; user explicitly chose "no special-case logic" (D-08). Revisit only if a user complains.
- **Per-station throttle** (instead of global) — defer; global is simpler and the user explicitly chose it (D-12).
- **Persisted last-preroll timestamp** (survives restart) — defer; user wants every fresh launch to feel like "radio coming on" (D-12).
- **Weighted / no-repeat random selection** — defer; user explicitly wanted pure random (Claude's Discretion).
- **"Replay preroll on first-stream failover"** — defer; explicitly rejected (D-10).
- **Toast / UI surface for preroll fetch failures** — defer; explicitly chose silent (D-04 / failure handling answer 2).
- **Generic preroll support for non-SomaFM providers** (AudioAddict, GBS.FM, etc.) — defer; provider gate is SomaFM-only by D-11. Reopen when a second provider gains prerolls; `station_prerolls` table is already provider-agnostic so the future change is gate-only.
- **Eager backfill at migration time** (one-time bulk SomaFM fetch on upgrade) — defer; lazy on-demand was explicitly chosen (D-03).
- **Periodic background refresh of prerolls** (e.g. weekly) — defer; SomaFM preroll lists rarely change. Re-import flow + lazy backfill cover the realistic refresh cases.
- **Integration test that exercises about-to-finish end-to-end with a real m4a** — defer; GStreamer mock blind spot (MEMORY anchor) makes this flaky. Behavioral tests + drift-guard are the closing-the-loop strategy.

### Reviewed Todos (not folded)
None — no matching todos surfaced.

</deferred>

---

*Phase: 83-at-start-of-playing-a-station-randomly-select-and-play-one-o*
*Context gathered: 2026-05-22*
