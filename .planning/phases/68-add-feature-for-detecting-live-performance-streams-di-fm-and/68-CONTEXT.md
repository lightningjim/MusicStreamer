# Phase 68: Add feature for detecting Live performance streams (DI.fm and similar) - Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

When the user is playing — or browsing — a DI.fm station, MusicStreamer surfaces whether that channel is currently broadcasting a **live show** (a curated DJ set or live performance) versus its normal automated programming. Detection uses the AudioAddict API as the authoritative source for DI.fm channels and falls back to a conservative `LIVE:` ICY-title prefix match for everything else. Three UI surfaces are added: an inline `LIVE` badge next to the track title in `NowPlayingPanel`, toast notifications on three transition events, and a "Live now" filter chip in `StationListPanel`'s existing filter strip that scopes the visible list to currently-live stations.

This is a discoverability + awareness feature for a specific listening style — catching scheduled live shows on DI.fm — distinct from generic "is the audio stream alive" liveness. It composes with Phase 67's similar-stations panel and Phase 64's AA sibling line without modifying either.

**In scope:**
- Live-show detection for DI.fm channels via the AudioAddict API (authenticated with the existing `audioaddict_listen_key` setting from Phase 48).
- ICY-title pattern fallback (`LIVE:` / `LIVE -` prefix only) for any station — including DI.fm when the listen key is absent.
- A `LIVE` badge rendered inline next to the ICY track title in `NowPlayingPanel`'s center column when the bound station is currently live.
- Toast notifications on three transition events: bind-to-already-live, off→on (live show starts mid-listen), on→off (live show ends mid-listen).
- A "Live now" filter chip in the existing `StationListPanel` filter strip that, when active, scopes the visible station tree to stations currently broadcasting a live show.
- Background poll loop maintaining a per-DI.fm-channel "is live now" map: adaptive cadence — 60 s while playing a DI.fm station, 5 min otherwise.
- Per-current-station detection refresh on `bind_station` and on `Player.title_changed` (for ICY-pattern detection).
- Silent fallback to ICY-pattern-only detection when no `audioaddict_listen_key` is saved — no prompt, no banner.

**Out of scope:**
- Provider scope beyond DI.fm. The AA API call code path generalizes to other AudioAddict networks (RadioTunes, JazzGroove, Frisky, ClassicalRadio, RockRadio) but this phase ships DI.fm only. Other networks will work via the universal ICY-pattern fallback if their stations follow the `LIVE:` convention.
- Universal ICY-pattern variants beyond `LIVE:` / `LIVE -` prefix. Phrases like "live set", "live mix", "DJ set", "@ <name>", "| Live from X" are not matched in v1 — too high false-positive risk on legitimate track titles ("Live and Let Die", etc.).
- Recording, archiving, or persistence of live-show history (timestamps, show names, set lists). Live status is transient and not stored beyond the in-memory poll cache.
- Hamburger menu toggle for the feature. The badge and toasts are always-on when a station is detected as live; the filter chip is opt-in by clicking it (same pattern as other filter chips). No master enable/disable switch.
- Listener counts, schedules / EPG fetches, "starts at HH:MM" surfacing, or post-show recap. Detection is binary: currently live, or not.
- A separate "Browse live shows" dialog. The filter chip is the single discovery surface.
- Per-station opt-out / mute. If you don't want toasts, you can ignore them — no per-station toast suppression in v1.
- Modifying the Phase 64 sibling line, the Phase 67 Similar Stations panel, or any other existing NowPlayingPanel widget. The badge is a new inline child of the existing track-title row.

</domain>

<decisions>
## Implementation Decisions

### Detection signal source

- **D-01:** **Hybrid detection**, two ranked sources with the API winning when both are available:
  - **(a) Primary — AudioAddict API.** For any bound DI.fm station, fetch the channel's current show metadata via the AA API using the saved `audioaddict_listen_key`. The API authoritatively says whether the channel is in a "live show" segment (vs normal track rotation) and gives the show name for badge/toast text.
  - **(b) Fallback — ICY-title prefix match.** For non-DI.fm stations, or DI.fm when the listen key is empty, examine the most recent ICY title (from `Player.title_changed`). If it starts with the literal prefix `LIVE:` (case-insensitive, optional surrounding whitespace) or `LIVE -` (with the dash), the station is treated as live and the rest of the ICY string is the show name.
- **D-02:** **Provider scope is DI.fm only** for the API code path. The implementation code MUST be structured so that adding RockRadio / JazzGroove / etc. is a one-line change to a network allowlist (the AA API base URL takes a `{slug}` parameter). But ROADMAP scope and tests verify DI.fm behavior only.
- **D-03:** **No master enable/disable toggle.** The feature is always-on when conditions are met (station is DI.fm with key saved, OR station's ICY matches `LIVE:`). Surface visibility is naturally gated: badge only appears when a station is detected live; filter chip only highlights stations when poll has data; toasts only fire on transitions.

### ICY title pattern (D-01b detail)

- **P-01:** **Match `LIVE:` and `LIVE -` prefix only.** Case-insensitive. The match is applied to the trimmed ICY title:
  - `re.match(r'^\s*LIVE\s*[:\-]\s*(.+?)\s*$', title, re.IGNORECASE)` (planner picks final regex)
  - The captured group is the show name (used for badge text + toast).
- **P-02:** **Reject substring matches** — `"Live and Let Die"`, `"Live at Wembley"`, `"Live set in Berlin"` do NOT trigger live mode. Prefix-only is intentional to keep false positives near zero. If real DI.fm ICY data turns out to use a different convention, P-01 can be revisited in a follow-up.
- **P-03:** **No state on ICY-pattern detection beyond the current title.** Whenever `title_changed` fires, re-evaluate. If the new title does not match, the station is no longer in live mode (toast fires for `on → off`).

### AudioAddict API integration (D-01a detail)

- **A-01:** **Use the existing `audioaddict_listen_key` setting** (persisted at `accounts_dialog.py:171` / `import_dialog.py:459`). Read via `repo.get_setting("audioaddict_listen_key", "")`. If empty → silent fallback to ICY-only detection (D-04).
- **A-02:** **Endpoint to call** — research deliverable. The most likely candidates are:
  - `https://api.audioaddict.com/v1/di/track_history?listen_key={key}` — returns an array of recent tracks per channel; "show" entries include a `track_type` or `show_id` distinguishing them from normal tracks.
  - `https://api.audioaddict.com/v1/di/currently_playing?listen_key={key}` — returns current state per channel, possibly including `show.title`.
  - `https://www.di.fm/_papi/v1/di/currently_playing` — undocumented PAPI endpoint used by the DI.fm web player.
  - **Researcher MUST verify the exact endpoint, response shape, and rate limits before planning. Plan must reference the chosen endpoint by full URL.**
- **A-03:** **Auth model** — query-string `listen_key` (matches the existing `aa_import.py` convention at lines 146 / 159). No OAuth, no headers beyond a User-Agent string.
- **A-04:** **Failure mode** — any non-2xx HTTP response, JSON parse error, network timeout, or missing key field → treat as "not live" silently. No error toasts. No retry loop within a single poll cycle. The next poll cycle re-attempts.
- **A-05:** **No retries within a poll** — bandwidth and latency are tiny, but cascading retries during transient AA outages would amplify load. One attempt per channel per poll. Stale data persists until the next successful poll.
- **A-06:** **Channel keying** — match AA API channel responses against the user's stored DI.fm `Station` rows by the channel's `key` field as it appears in `aa_import.fetch_channels_multi()` output (the same key used during AA import). Planner verifies this maps cleanly to a column already on `Station` (likely `provider_station_id` or a stream URL substring).

### Background polling (filter freshness)

- **B-01:** **Adaptive cadence.**
  - **60 s** while the user is currently playing any DI.fm station (high-engagement window — likely to want fresh transitions for the badge AND filter).
  - **5 min** otherwise (still useful for the filter chip; minimal background traffic).
  - Cadence reassessment fires whenever `bind_station` switches stations — if the new station is DI.fm-provider, snap to 60 s; if not, snap to 5 min.
- **B-02:** **Single batched poll per cycle.** Each cycle issues one HTTP call (or however many the chosen AA endpoint requires for "all DI.fm channels" — researcher confirms whether one call returns all channels or whether multiple calls are needed). The result populates an in-memory `dict[channel_key, LiveState]` map keyed by AA channel slug.
- **B-03:** **Poll runs while the app is open.** Started in `MainWindow.__init__` after settings load, stopped on `closeEvent`. Skipped if no `audioaddict_listen_key` is saved.
- **B-04:** **Listen-key change reactive.** When the user adds or clears the AA key in `AccountsDialog` / `ImportDialog`, the poll loop is started / stopped / restarted. (Planner picks: signal-based push from AccountsDialog, or settings-watch on next poll cycle. Either acceptable.)
- **B-05:** **Poll loop runs on a `QTimer`** (single-shot rescheduled each cycle) on the Qt main thread. The HTTP call itself runs in a worker `QThread` to avoid blocking the UI event loop. Result emitted via signal back to main thread for state updates.

### Per-current-station refresh (badge freshness)

- **C-01:** **Detect on bind.** Inside `NowPlayingPanel.bind_station`, after the existing Phase 64 `_refresh_siblings()` call and Phase 67 `_refresh_similar_stations()` call, invoke a new `_refresh_live_status()` method.
- **C-02:** **Detect on track change.** Subscribe to `Player.title_changed` (already-existing signal at `player.py:237`). On every fire, re-run `_refresh_live_status()`. This handles ICY-pattern transitions (live → normal → live) and refreshes the AA-API badge text mid-show.
- **C-03:** **`_refresh_live_status()` decision tree** (planner formalizes):
  1. If station's provider is DI.fm AND `audioaddict_listen_key` is non-empty:
     - Look up channel state from the in-memory poll cache (B-02). Use the cached result. If the cache has not been populated yet (very early in app lifecycle), trigger a one-shot poll for just this channel.
     - If the cache says "live", use the cached `show.title` as badge text.
  2. Else (non-DI.fm OR no key):
     - Apply the ICY pattern (P-01) to the most recent `Player.title`.
     - If matches, the captured group is the badge text.
  3. Compare the new live state to the previous state for this station. On transition, fire the appropriate toast (T-01).

### UI: badge

- **U-01:** **Badge placement: inline next to the track title** in `NowPlayingPanel`'s center column. Mechanism: a small `QLabel` (e.g., `_live_badge`) created in `_init_now_playing_widgets`, hidden by default, added as a sibling to the existing `icy_label` in a new `QHBoxLayout` so the badge sits to the LEFT of the ICY title text.
- **U-02:** **Badge text format:** When live, the badge reads `LIVE` in uppercase. The show name is appended to the ICY title row as " — {show name}" — i.e., the ICY title slot becomes `[LIVE] — Drone Zone Live: DJ Set`. Planner picks final separator and styling.
- **U-03:** **Badge styling:** Reuse the Phase 66 theme accent color for the badge background; small rounded chip; white-or-theme-contrast text. Do not introduce a new global style; use whatever `_theme` token is closest to "accent / attention". Planner picks the exact token.
- **U-04:** **Badge visibility:** `setVisible(True)` only when `_refresh_live_status()` reports live. `setVisible(False)` immediately when no longer live. No animation; matches the rest of the panel's sub-widget show/hide convention.

### UI: toasts

- **T-01:** **Three toast triggers** (all use the existing `MainWindow._toast` ToastOverlay):
  - **(a) Bind-to-already-live** — fires when `bind_station` resolves to a station that is currently live. Text: `"Now live: {show name} on {station name}"`.
  - **(b) Off → On (becomes-live mid-listen)** — fires when the currently bound station transitions from not-live to live. Text: `"Live show starting: {show name}"`.
  - **(c) On → Off (returns-to-normal mid-listen)** — fires when the currently bound station transitions from live to not-live. Text: `"Live show ended on {station name}"`.
- **T-02:** **No toast cooldown.** Live transitions are infrequent — at most a few per session. Unlike the Phase 62 buffering toast (which cooldowns to suppress chatter), live-transition toasts are individually meaningful events.
- **T-03:** **No toast for poll-only library transitions.** The background poll updates the filter map, but toasts ONLY fire for the currently bound station's transitions. Catching every DI.fm channel going live would spam the user.
- **T-04:** **Toast emoji / glyph** — none in v1 (Phase 999.7-02 toast convention). Planner picks any glyph from the existing toast vocabulary if it improves scannability. Default: text-only.

### UI: "Live now" filter chip

- **F-01:** **Placement: new chip in the existing `StationListPanel` filter strip** alongside the existing tag/provider chips (the Phase 47.1 FlowLayout filter strip).
- **F-02:** **Behavior: toggle that scopes the visible tree.** Click → tree shows only stations whose AA channel key is currently in the in-memory live map (B-02) with `is_live=True`. Click again → toggle off, full tree restored.
- **F-03:** **Mode interaction:** Composes with the existing tag/provider chip filters (AND-between). I.e., "Live now" + "ambient" tag chip → only live DI.fm stations tagged ambient.
- **F-04:** **Empty-state when active:** When the chip is on but no DI.fm channels are currently live, the tree is empty. Show the existing empty-tree placeholder (no special "no live shows right now" copy).
- **F-05:** **Chip styling:** Reuse existing Phase 47.1 chip styling. Optionally with a subtle "live" accent (red dot, Phase 66 accent token) to distinguish from tag chips. Planner picks.
- **F-06:** **Polled-data freshness vs reality lag:** Filter results may be up to 60 s / 5 min stale (per B-01). Acceptable — this is a discovery surface, not a real-time monitor. No spinner, no "last updated" caption.
- **F-07:** **No-key fallback:** When `audioaddict_listen_key` is empty (and therefore the poll loop is not running), the "Live now" chip is **hidden entirely** from the filter strip — there is no data to filter against. ICY-pattern detection is per-current-station only and cannot drive a library-wide filter.

### No-listen-key handling

- **N-01:** **Silent fallback to ICY-pattern only.** No prompt, no toast, no banner. The badge still works for any station whose ICY title matches `LIVE:` (D-01b / P-01). The "Live now" filter chip is hidden (F-07). Background poll is not started (B-03).
- **N-02:** **No proactive nudge.** The user discovers the feature by configuring the AA listen key in `AccountsDialog` (Phase 48 already established that flow). Adding a nudge here couples Phase 68 to Phase 48's UX in a way that feels intrusive.
- **N-03:** **Reactive activation.** When the user later saves a key (B-04), the poll loop starts and the filter chip becomes visible.

### Test discipline

- **TD-01:** **Wave 0 RED contract first.** Following the Phase 67 / Phase 65 pattern, write all failing tests first in a Wave 0 plan, then implement subsystems against them. Test surfaces:
  - Pure helper tests for the ICY pattern matcher (P-01, P-02) — no Qt, no network.
  - Pure helper tests for the AA API response parser (A-02 candidates, fixture-based) — mock HTTP, parse JSON.
  - Panel widget tests for the badge (U-01, U-02, U-03, U-04) — qtbot, mock state.
  - Filter widget tests for the "Live now" chip (F-01..F-07) — qtbot, mock poll cache.
  - Integration tests for poll-loop start/stop on key save/clear (B-04).
  - Integration tests for the three toast triggers (T-01a/b/c) — mock state transitions.
- **TD-02:** **AA API mocking** — record real DI.fm API responses as fixtures (similar to `tests/fixtures/gbs/`), check them in. Tests do NOT hit the live AA API — too flaky, too dependent on what's currently live.
- **TD-03:** **No QA-05-style lambda-grep test required** (Phase 67's test_no_lambda was specific to the new signal). Phase 68 introduces no new long-lived signal connections; the badge updates are direct method calls within the panel.

### Claude's Discretion

- Module structure: planner picks whether the AA API client lives in a new `musicstreamer/aa_live.py`, extends `aa_import.py`, or sits inside `musicstreamer/ui_qt/now_playing_panel.py`. Recommendation: a new `musicstreamer/aa_live.py` for testability + reuse.
- Poll thread implementation: planner picks `QThread` + `Worker` object, vs a `QTimer.singleShot` + `concurrent.futures.ThreadPoolExecutor`, vs `requests` in a thread with signal callback. Researcher should note any prior pattern (e.g., `_YtScanWorker` in `yt_import.py` from Phase 999.7-02).
- Cache invalidation on poll failure: keep last successful state vs immediately mark all channels not-live. Recommendation: keep last successful state (graceful degradation), with a TTL (e.g., 15 min) after which stale entries are dropped.
- Show-name truncation in badge text: long show names ("DJ Drez & Marti Nikko: Live from the Bhakti Fest 2024") may overflow the title row. Planner picks a max-width / ellipsis policy.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 68 inputs
- `.planning/ROADMAP.md` §"Phase 68" — high-level goal (single sentence; this CONTEXT.md is the operative source for everything else)
- `.planning/PROJECT.md` — current state, requirements, milestone scope (v2.1 Fixes and Tweaks)

### Prior-phase context that constrains this phase
- `.planning/phases/64-*/64-CONTEXT.md` — AA sibling line ("Also on:") in NowPlayingPanel — shape Phase 68's badge must coexist with
- `.planning/phases/64-*/64-SUMMARY.md` — `find_aa_siblings`, `render_sibling_html`, sibling-click delegation pattern (mirror for live-toast wiring)
- `.planning/phases/67-*/67-CONTEXT.md` — Similar Stations panel beneath the Phase 64 line — same `bind_station` insertion seam Phase 68 hooks into
- `.planning/phases/67-*/67-SUMMARY.md` — `_refresh_similar_stations` pattern, in-memory cache pattern, signal-delegation pattern

### AudioAddict API
- `musicstreamer/aa_import.py` — existing AA API client, `fetch_channels_multi(listen_key)` at line 131 — shape Phase 68's live-poll client should mirror (same `listen_key` query-string auth, same per-network endpoint convention)
- `musicstreamer/ui_qt/accounts_dialog.py:169` — `_is_aa_key_saved()` helper + `audioaddict_listen_key` setting key — Phase 68 reads the same setting
- `musicstreamer/ui_qt/import_dialog.py:459` — write path for `audioaddict_listen_key` — Phase 68 must react to saves here (B-04)

### Toast infrastructure
- `musicstreamer/ui_qt/toast.py` (or wherever `ToastOverlay` lives) — referenced from `main_window.py:62, 287`. Phase 68 uses the same overlay for T-01a/b/c.
- `musicstreamer/ui_qt/main_window.py:284–312` — toast wiring example (Phase 999.7-02 / Phase 62 patterns) — Phase 68's transition handlers wire similarly.

### NowPlayingPanel + filter strip
- `musicstreamer/ui_qt/now_playing_panel.py` — `bind_station`, `_refresh_siblings` (Phase 64), `_refresh_similar_stations` (Phase 67), `icy_label` placement — Phase 68's `_refresh_live_status` + `_live_badge` slot in next to ICY label.
- `musicstreamer/ui_qt/station_list_panel.py` — Phase 47.1 filter strip + chip mechanics — Phase 68's "Live now" chip plugs in here.
- `musicstreamer/ui_qt/station_filter_proxy.py` — proxy filter logic that current chip filters use — Phase 68's "Live now" filter is one more predicate.

### Player + ICY title pipeline
- `musicstreamer/player.py:237` — `title_changed = Signal(str)` — Phase 68 subscribes to drive ICY-pattern detection (C-02).
- `musicstreamer/player.py:67` — `_fix_icy_encoding` — already applied to the title before signal emission, so Phase 68 receives clean text.

### MusicStreamer spike findings (project-local)
- `.claude/skills/spike-findings-musicstreamer/SKILL.md` — load ONLY if Phase 68 hits Windows packaging, GStreamer, PyInstaller, conda-forge, or Qt/GLib bus-handler threading. None expected for this phase.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`aa_import.py:fetch_channels_multi(listen_key)`** — established AA API client pattern (`requests.get`, listen_key query-string, per-network endpoint). Phase 68's live-poll client should mirror auth + URL conventions. Live endpoint differs but plumbing is the same.
- **`audioaddict_listen_key` SQLite setting** — already persisted (read at `accounts_dialog.py:171`, `import_dialog.py:262`; written at `import_dialog.py:459`). Phase 68 reads only.
- **`ToastOverlay` (`musicstreamer/ui_qt/toast.py`)** — anchored bottom-centre; main_window has the wired instance at `_toast`. Phase 68 reuses for all three transition toasts.
- **`Player.title_changed = Signal(str)`** — already emits ICY title (post-encoding-fix). Subscribed by `NowPlayingPanel.on_title_changed` (or similar). Phase 68 piggybacks.
- **Phase 47.1 filter strip + chip mechanics** in `station_list_panel.py` — Phase 68's "Live now" chip reuses the same chip widget class.
- **Phase 64's dual-shape repo defense pattern** at `now_playing_panel.py:941–955` — Phase 68 borrows for any AA channel-state lookup that may yield None.

### Established Patterns
- **`bind_station` insertion seam** — Phases 64 and 67 each appended a `_refresh_*()` call inside `bind_station`. Phase 68 follows: `_refresh_live_status()` after `_refresh_similar_stations()`.
- **In-memory cache + on-demand refresh** (Phase 67 `_similar_cache`) — Phase 68's poll-cache uses the same idiom: `dict` keyed by stable id, no SQLite persistence, cleared on app restart.
- **Worker-thread + signal-back-to-main pattern** (Phase 999.7-02 `_YtScanWorker`) — Phase 68's HTTP poll runs in a `QThread` worker, emits results back to the main thread.
- **Settings-driven feature gating** — Phase 48's pattern of "feature live only when key saved" — Phase 68 mirrors for AA-API path; ICY fallback always on.
- **Wave 0 RED contract first** (Phases 65, 67) — write all failing tests in plan 01 then implement subsystems against them in plans 02+.
- **Test fixtures for HTTP responses** (`tests/fixtures/gbs/`) — Phase 68 records DI.fm AA API responses as fixtures.

### Integration Points
- **`MainWindow.__init__`** — start the poll loop here after settings load + AccountsDialog instantiation; stop in `closeEvent`.
- **`AccountsDialog` save/clear AA key** — Phase 68 either receives a signal here (`aa_key_changed`) or polls `repo.get_setting()` lazily on the next cycle. Decision deferred to planner.
- **`StationListPanel` filter strip** — add a new chip widget; wire its `toggled` signal to `station_filter_proxy.set_live_only(bool)`.
- **`NowPlayingPanel.bind_station`** — append `_refresh_live_status()` call after Phase 67's `_refresh_similar_stations()`.
- **`Player.title_changed`** — `NowPlayingPanel` already subscribes; extend the existing slot to also call `_refresh_live_status()`.

</code_context>

<specifics>
## Specific Ideas

- The user references DI.fm specifically — they listen to DI.fm regularly and want this to "just work" for that one provider. "And similar" in the phase title acknowledges the AA family share an API but is explicitly out of v1 scope (D-02).
- The user picked an **adaptive** poll cadence (60s while playing DI.fm, 5min otherwise), valuing low background traffic when not actively engaged. Researcher should validate that 60s is not too aggressive for DI.fm's API rate limits.
- The user picked the **conservative** ICY pattern (`LIVE:` prefix only, no substring matches) — preference for zero false positives over wider coverage.
- The user picked **silent fallback** with no listen-key prompt — preference for non-intrusive UX. The Phase 48 AccountsDialog is the discovery surface for AA key configuration.
- The user picked **inline-next-to-track-title** badge placement — wants the strongest visual coupling to "what am I hearing right now".
- The user picked **all three transition toasts** (bind-to-live, off→on, on→off) — wants symmetric awareness of live mode entry and exit.

</specifics>

<deferred>
## Deferred Ideas

- **Universal ICY pattern variants** ("live set", "live mix", "DJ set", "@ <name>", "| Live from X") — defer until we observe real ICY data from non-AA providers and can quantify false-positive risk.
- **Multi-network AA support** (RockRadio, JazzGroove, Frisky, ClassicalRadio, RockRadio, RadioTunes) — code path generalizes naturally; ship in a follow-up phase once DI.fm pattern is proven.
- **Live-show history / archive** — recording timestamps, show names, set lists. Belongs in a separate "Listening history" or "Favorites for shows" phase.
- **Schedule / EPG fetch** — "DJ Drez goes live at 18:00 today" requires schedule API integration. Belongs in a separate "Live show calendar" phase.
- **"Browse live shows" dialog** — a modal listing all currently-live channels with show name + start time. The filter chip subsumes the basic "what's live now" need; a dedicated dialog is enhancement.
- **Per-station opt-out / mute for toasts** — fine-grained control. Defer until we see whether toast frequency is actually a problem.
- **Master enable/disable toggle in hamburger** — Phase 67's pattern. Deferred because the feature is naturally gated by station provider + key presence; no master switch needed.
- **Recording / capturing live shows to local audio files** — large scope, separate phase if it ever becomes a goal.
- **Visual color picker for the LIVE badge color** — out of scope; reuses Phase 66 theme tokens.

</deferred>

---

*Phase: 68-add-feature-for-detecting-live-performance-streams-di-fm-and*
*Context gathered: 2026-05-10*
