# Phase 68: Add feature for detecting Live performance streams (DI.fm and similar) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 68-add-feature-for-detecting-live-performance-streams-di-fm-and
**Areas discussed:** Detection signal, Provider scope, UI surface, Freshness (per-station), Filter freshness, ICY pattern, Badge placement, Toast triggers, Poll cadence, Filter location, No-listen-key handling

---

## Detection signal source

| Option | Description | Selected |
|--------|-------------|----------|
| ICY title pattern | Match the live ICY title text against patterns like 'LIVE:', 'Live from', 'DJ set:', specific artist words. No network fetch needed — uses the metadata GStreamer already gives us via the Player.title_changed signal. | ✓ |
| AudioAddict API metadata | Poll DI.fm / AA channel API for the current track or show object. AA's `/v1/{network}/track_history` and `/v1/{network}/now_playing` endpoints return the active show. Adds network polling + listen_key auth. | ✓ |
| DI.fm 'Live' channel slug | Treat DI.fm's permanent 'live' channels (e.g. di.fm/live, di.fm/livesets) as live by static channel-key allowlist. Detected at station-bind time — no live polling, no per-track lookup. | |
| User-tagged 'live' | Let the user mark a station as a live channel via EditStationDialog (a checkbox) or by adding a 'live' tag. No network detection — manual curation only. | |

**User's choice:** Hybrid — AA API + ICY pattern.
**Notes:** AA API is authoritative when listen_key is present; ICY pattern is the universal fallback.

---

## Provider scope

| Option | Description | Selected |
|--------|-------------|----------|
| DI.fm only | Strictly DI.fm (via AudioAddict API or hard-coded slug). Clean, narrow scope — ships in one phase. | ✓ |
| All AudioAddict networks | DI.fm + RadioTunes + JazzGroove + Frisky + ClassicalRadio + RockRadio. Same API code path; broader coverage. | |
| Universal pattern match | Any station, any provider, ICY-title pattern only (e.g., 'LIVE:' prefix). No per-provider integration needed. | |
| DI.fm + universal fallback | Real API integration for DI.fm (gives accurate show name), plus ICY-pattern fallback for everything else. Hybrid. | |

**User's choice:** DI.fm only.
**Notes:** Other AA networks deferred — code path will generalize, but tests + scope ship DI.fm-only. Universal ICY fallback still applies to non-DI.fm stations naturally.

---

## UI surface

| Option | Description | Selected |
|--------|-------------|----------|
| Badge in NowPlayingPanel | A 'LIVE' chip / colored label shown next to the track title in the now-playing area while the live event is active. Highest visibility while you're listening. | ✓ |
| Indicator in station list | A small icon / accent on rows in the station tree for stations currently broadcasting live. Lets you spot live shows without binding each one. | |
| Toast notification on transition | A brief popup when a stream you're playing transitions into or out of a live segment. Catches mode changes without hunting the UI. | ✓ |
| Filter / quick-jump | A 'Live now' filter chip in the station list (or hamburger entry) that shows only stations currently broadcasting live. Discovery surface for live content. | ✓ |

**User's choice:** Badge + Toast + Filter.
**Notes:** Indicator-in-tree was passed over in favor of the filter chip — same discoverability without per-row rendering complexity.

---

## Freshness (per-current-station)

| Option | Description | Selected |
|--------|-------------|----------|
| On bind only | Check once when you start playing a station; cache for the session. Cheapest. Misses live shows that start mid-listen. | |
| Bind + periodic poll | Re-check every N minutes while playing. Catches transitions mid-listen. Adds modest network traffic per session. | |
| Bind + on track change | Re-check whenever ICY title changes. Free if detection is ICY-pattern based; one extra API call per track change for AA-API detection. | ✓ |
| Manual refresh only | Ship a 'Refresh live status' button. Zero background traffic. | |

**User's choice:** Bind + on track change.
**Notes:** Reuses the existing `Player.title_changed` signal. Per-current-station only — library-wide freshness handled separately by the background poll (see Filter freshness).

---

## Filter freshness (library-wide poll)

| Option | Description | Selected |
|--------|-------------|----------|
| Background poll all DI.fm channels | On a timer (e.g., every 2-5 min while the app is open), poll AA API for ALL DI.fm channels' show status. Filter is always current. | ✓ |
| Lazy poll only when filter is opened | Don't poll in the background. When the user opens the 'Live now' filter, poll DI.fm channels at that moment, show a spinner, render results. Zero background traffic. | |
| Bind-time only (filter shows known-live) | Filter only includes stations whose live status was learned during this session via bind events. Empty on app start; populates as you listen. | |
| Drop the filter for v1 | Ship just the badge + toast in this phase. Defer the 'Live now' filter to a later phase. Smallest scope. | |

**User's choice:** Background poll all DI.fm channels.
**Notes:** The filter chip needs library-wide truth, which only background polling provides. Adaptive cadence (next question) keeps cost low.

---

## ICY title pattern (for universal fallback)

| Option | Description | Selected |
|--------|-------------|----------|
| Prefix 'LIVE:' or 'LIVE -' | Match stations that prefix the live track title with the word LIVE followed by a colon or dash. Common DI.fm convention. | ✓ |
| Contains 'live set' / 'live mix' / 'DJ set' | Substring match for these phrases anywhere in the ICY title. Catches more variants but risks false positives on track titles that legitimately contain 'live' (e.g., 'Live and Let Die'). | |
| Show name in title (delimited) | Pattern like 'Show Name @ DJ Name' or 'Title \| Live from X' — a heuristic delimiter that signals show-mode rather than track-mode. | |
| Skip ICY patterns — AA API only | For v1, trust only the DI.fm AA API metadata. Defer ICY pattern matching. | |

**User's choice:** Prefix 'LIVE:' or 'LIVE -' only.
**Notes:** Conservative — false-positive avoidance prioritized over coverage. Substring matches deferred until real data shows them necessary.

---

## Badge placement

| Option | Description | Selected |
|--------|-------------|----------|
| Inline next to track title | On the same row as the ICY title (e.g., '[LIVE] Drone Zone Live - DJ Set'). Strongest visual coupling to what you're hearing. | ✓ |
| Below station name, above track title | On its own row between the 'Name · Provider' line and the ICY title. Always-visible spot when active. | |
| Right edge of the controls row | A small badge in the same row as Play/Pause/Star/Edit. Closer to interactive elements but visually further from the title. | |
| Replace 'Also on:' position when live | Reuse the Phase 64 sibling-line slot. Compact; reuses existing space. | |

**User's choice:** Inline next to track title.
**Notes:** Phase 64 sibling line stays untouched (preserves Phase 64/67 layout invariants).

---

## Toast triggers

| Option | Description | Selected |
|--------|-------------|----------|
| Live show starts (becomes-live) | While you're playing a station, fire a toast when it transitions OFF → ON live. | ✓ |
| Live show ends (returns-to-normal) | Fire a toast when the station transitions ON → OFF live. | ✓ |
| Bind to a station that's already live | When you start playing a station that is currently live, fire a toast immediately so you know you're catching mid-show. | ✓ |
| Skip toasts — badge only | Just update the badge silently — don't surface live transitions as notifications. | |

**User's choice:** All three transition events.
**Notes:** Symmetric awareness of live mode entry and exit. No cooldown needed — transitions are infrequent.

---

## Poll cadence

| Option | Description | Selected |
|--------|-------------|----------|
| Every 60 seconds | Tightest freshness. Live show transitions surface within ~1 min. ~60 API calls/hour while app is open. | |
| Every 2 minutes | Good balance — transitions surface within 2 min, ~30 calls/hour. AA APIs respond in ms; bandwidth is tiny. | |
| Every 5 minutes | Conservative. Transitions surface within 5 min. ~12 calls/hour. Easiest on AA's infra; longest user-perceptible delay. | |
| Adaptive (60s while playing DI.fm, 5min otherwise) | Tight when you're listening to DI.fm, relaxed when playing other providers. More logic; more responsive when it matters. | ✓ |

**User's choice:** Adaptive cadence.
**Notes:** Researcher must validate that 60s is within DI.fm's API rate limits. Cadence reassessed on every `bind_station` switch.

---

## Filter location

| Option | Description | Selected |
|--------|-------------|----------|
| New chip in the existing filter strip | Add a 'Live now' chip alongside the existing tag/provider filter chips in StationListPanel. Click toggles 'show only currently-live stations'. Reuses Phase 47.1 filter strip mechanics. | ✓ |
| Hamburger menu entry that opens a dialog | A 'Browse live shows' menu item that opens a modal listing currently-live DI.fm channels with show name + start time. | |
| New segmented toggle (Stations / Favorites / Live now) | Extend the existing Stations / Favorites segmented toggle with a third 'Live now' mode. | |
| Right-click 'Browse live' on any DI.fm station | Add a context-menu entry on DI.fm rows that opens an inline live-shows panel. | |

**User's choice:** New chip in the existing filter strip.
**Notes:** Composes naturally with existing tag/provider chip filters (AND semantics). Reuses Phase 47.1 chip widget infrastructure.

---

## No-listen-key handling

| Option | Description | Selected |
|--------|-------------|----------|
| Silent fallback to ICY pattern only | Without a key, just use the 'LIVE:' prefix detection. Badge/toast still work whenever DI.fm puts 'LIVE:' in ICY. No prompt, no banner. Quietest UX. | ✓ |
| One-time toast prompt, then silent | First time you bind a DI.fm station with no key, show a toast: 'Add AudioAddict key for live show detection → Accounts'. After that, silent fallback. | |
| Disable feature entirely | If no key, don't show badge or run polls at all even when ICY says 'LIVE:'. Treat the feature as opt-in via the AA key. | |
| Status indicator in Accounts dialog | Show 'AA listen key required for live detection' next to the AA section in AccountsDialog. No runtime prompts; user discovers when configuring accounts. | |

**User's choice:** Silent fallback to ICY pattern only.
**Notes:** When no key is saved, the "Live now" filter chip is hidden (no library-wide data); badge still works for any station whose ICY matches `LIVE:`.

---

## Claude's Discretion

- Module structure: whether the AA API client lives in a new `musicstreamer/aa_live.py`, extends `aa_import.py`, or sits inside `now_playing_panel.py`. Recommendation: new `aa_live.py`.
- Poll thread implementation: `QThread` worker vs `QTimer.singleShot` + `ThreadPoolExecutor` vs `requests` in a thread with signal callback. Researcher should note Phase 999.7-02 `_YtScanWorker` precedent.
- Cache invalidation on poll failure: keep last successful state vs immediately mark all not-live. Recommendation: keep last successful state with a 15-min TTL.
- Show-name truncation in badge text for long show names. Planner picks max-width / ellipsis policy.
- Exact Phase 66 theme token to use for badge accent color.
- AA API endpoint specifics — three candidates listed in CONTEXT.md A-02; researcher must verify which exists and is most reliable.

## Deferred Ideas

- Universal ICY pattern variants ("live set", "live mix", "DJ set", "@ <name>", "| Live from X") — defer until real data justifies.
- Multi-network AA support (RockRadio, JazzGroove, Frisky, ClassicalRadio, RadioTunes) — code generalizes naturally; ship in a follow-up phase.
- Live-show history / archive (timestamps, show names, set lists). Belongs in a separate "Listening history" phase.
- Schedule / EPG fetch — "DJ X goes live at 18:00 today". Belongs in a separate "Live show calendar" phase.
- Dedicated "Browse live shows" dialog. Filter chip subsumes basic need; dialog is enhancement.
- Per-station opt-out / mute for toasts. Defer until toast frequency is shown to be a problem.
- Master enable/disable toggle in hamburger. Feature naturally gated by provider + key presence.
- Recording / capturing live shows to local audio files. Large scope, separate phase.
- Visual color picker for the LIVE badge color. Reuses Phase 66 theme tokens.
