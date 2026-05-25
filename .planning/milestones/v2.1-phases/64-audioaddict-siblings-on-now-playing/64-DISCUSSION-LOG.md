# Phase 64 Discussion Log

**Phase:** 64 — AudioAddict Siblings on Now Playing
**Date:** 2026-05-01
**Mode:** discuss (default) + --chain

## Gray areas presented

User selected all 4:
1. UI placement on Now Playing
2. Click action wiring
3. Renderer reuse
4. Refresh trigger on library changes

## Q&A

### Q1 — UI placement

**Question:** Where should the 'Also on: ZenRadio • JazzRadio' line live in NowPlayingPanel?
**Options presented:**
1. (Recommended) Below name_provider_label — under "Station · Provider", above ICY title
2. Below the control row — after play/stop/volume, before stats
3. Below the stats widget — last item in center column
4. Full-width row spanning under the 3-column layout

**User selected:** Below name_provider_label (Recommended)
**Captured as:** D-01 — sibling label inserted between `name_provider_label` (line 161) and `icy_label` (line 164) in `NowPlayingPanel.__init__`.

### Q2 — Click action wiring

**Question:** How does NowPlayingPanel tell MainWindow to switch playback to a sibling?
**Options presented:**
1. (Recommended) New signal `sibling_activated(Station)` — mirrors `edit_requested` precedent
2. Reuse `station_activated` signal directly — DRY but conflates source semantics
3. New signal `sibling_play_requested(int)` — int payload, MainWindow does repo fetch
4. Direct method call into MainWindow — tightest coupling

**User selected:** New signal `sibling_activated(Station)` (Recommended)
**Captured as:** D-02, D-02a — Signal(object) on NowPlayingPanel; MainWindow connects to a new `_on_sibling_activated` handler that delegates to `_on_station_activated`.

### Q3 — Renderer reuse

**Question:** Phase 51's `_render_sibling_html` lives privately on EditStationDialog. How do we share it?
**Options presented:**
1. (Recommended) Promote to free function in `url_helpers.py` next to `find_aa_siblings`
2. Promote to a new module `aa_siblings.py` (also moves `find_aa_siblings`)
3. Copy-adapt into NowPlayingPanel — DRY violation
4. Keep on EditStationDialog and import from there — bad layering

**User selected:** Promote to free function in `url_helpers.py` (Recommended)
**Captured as:** D-03, D-03a — `render_sibling_html(siblings, current_name) -> str` in `musicstreamer/url_helpers.py`; Phase 51's call site updates; href format `sibling://{id}` preserved verbatim.

### Q4 — Refresh trigger

**Question:** Should the line auto-update mid-playback if siblings are added/edited/deleted while playing?
**Options presented:**
1. (Recommended) Refresh on `bind_station` only — matches existing panel-state semantics
2. Refresh on `bind_station` + library-mutation signals — live-correct but more wiring
3. Refresh on every play/pause/stop transition — wasteful

**User selected:** Refresh on `bind_station` only (Recommended)
**Captured as:** D-04 — `_refresh_siblings` invoked only from `bind_station`. No subscription to `station_saved` / `station_deleted` / discovery-import-complete signals. Live-update deferred (see Deferred Ideas).

## Deferred ideas surfaced

- Live updates on library mutations (D-04 defers; pattern precedent = Phase 50)
- Sibling visibility on additional surfaces (right-click menu, hamburger menu, mini-player)
- Playback continuity hints / explicit "Switching to ..." toast
- Keyboard shortcut for sibling jump
- Sibling preview on hover
- Persisted `aa_channel_key` column (same rejection as Phase 51 D-01)

## Claude's discretion items

Captured in CONTEXT.md `<decisions>` § Claude's Discretion:
- Exact `Signal` name on NowPlayingPanel (`sibling_activated` recommended; planner picks)
- `_on_sibling_activated` as thin delegator vs duplicated side-effect block
- Cleanup of Phase 51's existing `EditStationDialog._render_sibling_html`
- Test placement (`tests/test_now_playing_panel.py`, `tests/test_url_helpers.py`)
- `panel.refresh_siblings()` public seam vs private `_refresh_siblings`

## No scope-creep redirects

User stayed within phase boundary. No new-capability suggestions during discussion.
