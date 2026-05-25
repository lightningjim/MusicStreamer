# Phase 50: Recently Played Live Update — Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

When the user starts playing a station, the **Recently Played** section in the left-panel station list reflects it within the same session — no app restart, no full provider-tree rebuild, provider expand/collapse states preserved.

In scope:
- Wire `StationListPanel`'s recent QListView to refresh after `MainWindow._on_station_activated` calls `update_last_played(station_id)`.
- Preserve provider-tree expand/collapse state during the refresh (do not call the existing `refresh_model()` — that rebuilds the tree and collapses groups).

Out of scope (deferred to other phases):
- Animations, highlights, slide effects on the recent-list bump.
- Rolling back a recent-list bump if playback fails.
- Distinguishing "tried to play" vs "actually played" — DB state already says "tried" via `update_last_played` firing on click.

</domain>

<decisions>
## Implementation Decisions

### Bump timing
- **D-01:** The recent list updates immediately on click — at the same point where `update_last_played(station_id)` already fires inside `MainWindow._on_station_activated` (`musicstreamer/ui_qt/main_window.py:324`). No waiting on a Player playback-confirmation signal.

### Failed-stream behavior
- **D-02:** If the click fails to produce audio (dead URL, all streams exhausted via Player.failover, YouTube live-stream-ended dialog, generic playback_error), the failed station **stays at the top of Recently Played**. No rollback of the bump and no rollback of `update_last_played`. Rationale: matches user mental model ("I just tried that station"), keeps DB and UI consistent, and lets the user re-attempt the failed station from Recently Played without rummaging through the provider tree.

### Visual treatment
- **D-03:** Instant swap — re-populate the existing `recent_view` QListView from `repo.list_recently_played(3)` with no animation, no highlight, no fade. Mirrors how `StationListPanel.refresh_model()` already updates the recent list today. Future polish (highlight pulse, slide animation) is an explicit non-goal for this phase.

### Refresh mechanism (Claude's discretion)
- **D-04 (Claude):** Expose a public method on `StationListPanel` (likely `refresh_recent()` or similar — final name set by planner) that wraps the existing private `_populate_recent()`. `MainWindow._on_station_activated` calls it directly after `update_last_played`. Direct method call rather than a new player/main-window signal: there is no need for additional decoupling — `MainWindow` already owns both `self._repo` (which mutates the DB) and `self._station_list_panel` (which renders the UI), so a direct call keeps the diff minimal and the data-flow legible. If a planner finds a strong reason to prefer signals, that is open.

### Claude's Discretion
- Refresh strategy is a full `_populate_recent()` rebuild (3 items, trivial cost); no surgical move-to-top is needed.
- Same-station re-activation (clicking the already-#1 station) is handled implicitly: `update_last_played` writes a new ms-precision timestamp, the rebuild query returns identical order, the QListView re-renders the same items. No special case.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 50: Recently Played Live Update" — goal, dependencies, three success criteria.
- `.planning/REQUIREMENTS.md` §BUG-01 — phase requirement statement.
- `.planning/PROJECT.md` Key Decisions table — ms-precision `last_played_at` (Phase 7 — `strftime('%Y-%m-%dT%H:%M:%f', 'now')`), `ListBox.insert(row,0)` for RP refresh that preserves expand state (GTK-era, now superseded by Qt model rebuild).

### Code touch points (load these to understand current state)
- `musicstreamer/repo.py:312–319` — `Repo.update_last_played(station_id)` and `Repo.list_recently_played(n=3)`.
- `musicstreamer/ui_qt/station_list_panel.py:357–365` — `StationListPanel._populate_recent()` (private; needs a public entry point).
- `musicstreamer/ui_qt/station_list_panel.py:314–319` — `StationListPanel.refresh_model()` (do NOT use — calls `model.refresh(...)` which collapses tree groups; SC #3 violation).
- `musicstreamer/ui_qt/main_window.py:320–329` — `MainWindow._on_station_activated()`; the call site where `update_last_played` already fires.

### Project conventions
- Bound-method signal connections, no self-capturing lambdas (QA-05) — applies if a signal-based refresh is chosen instead of a direct method call.

### No external specs
No ADRs or external docs referenced — the bug is fully captured by the four code touch points above and the three success criteria in ROADMAP.md.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Repo.list_recently_played(n)` — already returns `Station[]` ordered by `last_played_at DESC`, ms precision.
- `Repo.update_last_played(station_id)` — already called in `_on_station_activated` (no change needed).
- `StationListPanel._populate_recent()` — already does the right thing (clears `_recent_model`, re-queries, re-fills with `load_station_icon` + `Qt.UserRole` station data). Just needs to be invokable from outside the class.

### Established Patterns
- `StationListPanel.refresh_model()` (line 314) is the precedent for "external triggers refresh" — but it ALSO rebuilds the tree (collapses groups). The new refresh path must be narrower: recent list only.
- `_recent_model` is a flat `QStandardItemModel` on a flat `QListView` — no expand state, no proxy. `model.clear()` + re-append is the established idiom.
- `_populate_recent()` is already called once at construction (line 182) and inside `refresh_model()` (line 318). The new call site is a third caller of the same private method.

### Integration Points
- New entry point on `StationListPanel`: a public wrapper around `_populate_recent()`. Naming likely `refresh_recent()` (planner picks).
- New caller: `MainWindow._on_station_activated()` immediately after `self._repo.update_last_played(station.id)` at `main_window.py:324`.

</code_context>

<specifics>
## Specific Ideas

- The provider tree must NOT be rebuilt during the recent-list refresh — that is the explicit constraint from SC #3 (preserve expand/collapse state). The chosen approach (call only the recent-populate path, not `refresh_model`) satisfies this by construction.
- Failed-play stations stay at top — this is a positive product decision, not an oversight. The user can re-click from Recently Played to retry, which is a natural recovery affordance.

</specifics>

<deferred>
## Deferred Ideas

- **Visual polish on the bump** (highlight pulse, slide-in animation): can be its own future phase if Kyle wants it. Not in scope here.
- **Distinguishing "tried" from "successfully played"**: would require deferring `update_last_played` to a Player playback-confirmation signal, plus rollback bookkeeping for `_on_failover` / `_on_offline` / `_on_playback_error` / YouTube live-stream-ended dialog. Explicitly rejected for v2.1 per D-02.
- **Recently-played count > 3**: not raised in discussion; current `n=3` constant in `_populate_recent` stays.

</deferred>

---

*Phase: 50-recently-played-live-update*
*Context gathered: 2026-04-27*
