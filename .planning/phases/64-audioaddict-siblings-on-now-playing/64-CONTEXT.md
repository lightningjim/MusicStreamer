# Phase 64: AudioAddict Siblings on Now Playing — Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

When the user is playing an AudioAddict station that has at least one cross-network sibling (same `(channel_key)` derived from the URL, different `network_slug`), the **Now Playing panel** surfaces those siblings inline as one-click playback jumps. Playing DI.fm "Ambient" shows `Also on: ZenRadio • JazzRadio` immediately under the station name; clicking ZenRadio switches active playback to ZenRadio's "Ambient".

This is the closure follow-up to Phase 51, which scoped sibling visibility to `EditStationDialog` only and explicitly deferred the Now Playing surface (Phase 51 deferred-ideas list).

**In scope:**
- Render the "Also on:" line in `NowPlayingPanel` when an AA station with siblings is playing.
- Wire click-to-switch-playback through MainWindow so the same plumbing as picking from the station list (refresh recent, toast, media-keys metadata, last-played update) fires for sibling jumps.
- Reuse Phase 51's `find_aa_siblings(stations, current_station_id, current_first_url)` as the single detection path (SC #4).
- Promote Phase 51's private `_render_sibling_html` to a shared free function so EditStationDialog and NowPlayingPanel use the same renderer.

**Out of scope:**
- Surfacing siblings on additional surfaces (station-list right-click menu, hamburger menu, mini-player). Could be a future polish phase.
- Live updates while the line is visible: if the user edits/deletes/imports stations mid-playback, the visible "Also on:" line is **not** re-derived until the user activates a different station (D-04).
- Cross-network failover: clicking a sibling is a deliberate user action, not auto-failover. `Player.failover` and the multi-stream queue are untouched (parity with Phase 51 SC #4).
- Dirty-state confirmation flow from Phase 51 — N/A here (no editable form to lose).
- Visual polish beyond default Qt link styling (animations, hover beyond underline, color theming).

</domain>

<decisions>
## Implementation Decisions

### UI placement

- **D-01:** The "Also on: ZenRadio • JazzRadio" line is rendered as a new `QLabel` inserted into the center column of `NowPlayingPanel` **immediately below `self.name_provider_label`** (the "Station · Provider" line at `now_playing_panel.py:155-161`) and **above `self.icy_label`** (the ICY title at line 164). This positions siblings as part of the station's identity tagline — read order: `Groove Salad · SomaFM` → `Also on: …` → ICY title — rather than as a secondary affordance. Hidden-when-empty (D-05) means non-AA stations and AA stations without siblings reclaim that vertical space, so the panel does not leave a gap.

### Click action wiring

- **D-02:** `NowPlayingPanel` exposes a new signal `sibling_activated = Signal(Station)` (object payload, mirrors the existing `edit_requested = Signal(object)` precedent at `now_playing_panel.py:112`). The panel's `linkActivated` slot looks up the sibling `Station` by id from `self._repo.get_station(...)` and emits `sibling_activated(station)`. `MainWindow` connects this signal to a new handler `_on_sibling_activated(Station)` that delegates to the existing `_on_station_activated` flow (bind_station, player.play, update_last_played, refresh_recent, "Connecting…" toast, media-keys metadata + playing state). Single source of truth for "user picked a station to play"; the only divergence from `_on_station_activated` is the originating signal, not the side-effect set.
- **D-02a:** `_on_sibling_activated` is wired in `MainWindow.__init__` alongside the existing `now_playing.edit_requested.connect(...)` line at `main_window.py:252`. Bound-method connection (QA-05).

### Renderer reuse

- **D-03:** Phase 51's `_render_sibling_html(siblings, current_name) -> str` (currently a private method on `EditStationDialog` at `edit_station_dialog.py:531-574`) is **promoted to a free function `render_sibling_html(siblings, current_name) -> str` in `musicstreamer/url_helpers.py`** — colocated with `find_aa_siblings` so the Phase 51 helpers and renderer share a module. The function body is moved verbatim; the `NETWORKS` lookup, `html.escape` mitigation, U+2022 separator, U+2014 em-dash for name-mismatch, and "Also on: " prefix are preserved. `EditStationDialog._render_sibling_html` is replaced with a direct call to the new free function (the existing private method is deleted; callers update to `render_sibling_html(siblings, current_name)`).
- **D-03a:** The href format `sibling://{id}` is preserved verbatim, including its security properties (integer-only payload, no injection surface). Both `EditStationDialog._on_sibling_link_activated` and the new `NowPlayingPanel._on_sibling_link_activated` parse the same `sibling://{id}` shape so the renderer remains agnostic about which surface is hosting it.

### Refresh trigger

- **D-04:** The "Also on:" line is recomputed **only inside `NowPlayingPanel.bind_station(station)`** — at the same point where `_populate_stream_picker(station)` runs (line 344). No subscription to `station_saved`, `station_deleted`, or discovery-import-complete signals. Rationale: panel state (logo, name, ICY label, stream picker) is already static-per-station; the "Also on:" line follows that contract for consistency. If a user edits a sibling mid-playback, the new state appears the next time any station is activated — including re-clicking the same station in the list, which already calls `_on_station_activated → bind_station`.

### Hidden-when-empty

- **D-05:** The new sibling label uses the same Phase 51 D-06 contract: `setVisible(False)` when `find_aa_siblings(...)` returns an empty list, with **zero vertical space**. Three trigger cases (mirrored from Phase 51):
  1. Non-AA station (current URL fails `_is_aa_url` or has no derivable channel key).
  2. AA station with a key but no other AA library stations on different networks share the key.
  3. No station bound (`self._station is None`) or `streams` is empty.
- **D-05a:** The label uses `setTextFormat(Qt.RichText)`, `setOpenExternalLinks(False)`, and `linkActivated.connect(self._on_sibling_link_activated)` — same configuration as `EditStationDialog._sibling_label` at `edit_station_dialog.py:405-410`. T-39-01 PlainText convention is deviated for inline `<a>` links exactly as Phase 51 deviated, with the same `html.escape` mitigation in the now-shared renderer (D-03).

### URL source for sibling detection

- **D-06:** The "current first URL" passed to `find_aa_siblings(...)` comes from **`self._station.streams[0].url`** when `self._station` is non-None and `self._station.streams` is non-empty. The `Station` object passed to `bind_station` is constructed by `Repo.list_stations()`, which already populates `streams` (Phase 51 verified at `repo.py:225`). Defensive fallback to empty string (which `find_aa_siblings` handles by returning `[]`, triggering the hide path) when streams are absent — matches Phase 51's empty-streams guard at `url_helpers.py:126-127`.

### SC #5 protection (no self-listing)

- **D-07:** SC #5 ("currently-playing station's own row is not listed as a sibling of itself") is enforced by `find_aa_siblings`'s existing `if st.id == current_station_id: continue` at `url_helpers.py:122`. No additional guard needed in the panel. Re-stated here for traceability so the planner adds an explicit assertion to the test set (e.g. when the playing station's id is excluded from the rendered link list).

### Click-while-clicked debounce

- **D-08:** Multiple rapid clicks on the same sibling link should not fire `Player.play(...)` repeatedly. The bound-method connection on `linkActivated` is fine for single clicks, but the panel handler should be a no-op when `self._station is None or self._station.id == sibling_id` (the latter is theoretically unreachable because `find_aa_siblings` excludes self, but a defense-in-depth check protects against rendering staleness). This is a 2-line guard at the top of `_on_sibling_link_activated`.

### Claude's Discretion

- The exact `Signal` name on `NowPlayingPanel`. `sibling_activated` is the recommended default but if the planner finds a better name (`switch_to_sibling`, `sibling_play_requested`) that reads more clearly at the connect site in `MainWindow`, the planner picks. Object-payload (Station) over int-payload is locked.
- Whether `_on_sibling_activated` is a thin delegator that calls `self._on_station_activated(station)` directly, or duplicates the side-effect block. The "Connecting…" toast wording matches `_on_station_activated`. Locking it to "delegates" is preferred but the planner can split if there is a behavior divergence (e.g., a different toast).
- Phase 51's existing `EditStationDialog._render_sibling_html` is removed cleanly. If the planner finds a way to keep the private method as a thin wrapper for backward source-stability, that is fine — the goal is single-source rendering, not strict deletion.
- Test placement: extend `tests/test_now_playing_panel.py` (if exists) for the new label + signal, and `tests/test_url_helpers.py` for the promoted `render_sibling_html`. If `test_now_playing_panel.py` does not exist, planner creates it. Phase 51's `tests/test_edit_station_dialog.py::test__render_sibling_html_*` should remain green after `_render_sibling_html` becomes a wrapper or is replaced by the import; planner adjusts those tests to call the free function if they tested the private method directly.
- Whether to add a `panel.refresh_siblings()` public-method seam alongside `bind_station` for testability, or keep refresh logic inline. Phase 51 has `_refresh_siblings` (private) — mirror that name in NowPlayingPanel.

</decisions>

<specifics>
## Specific Ideas

- The user-visible promise: **"While I'm playing DI.fm Ambient, one click on 'ZenRadio' switches me to Zen Ambient."** No edit dialog detour. No confirmation. No playback failover machinery. Just like clicking a station in the list, but the source is the cross-network sibling line.
- The shared renderer (D-03) is the one piece of net-new factoring. Everything else is pure plumbing: a label widget, a signal, a handler, and a `bind_station` hook that calls the existing helper.
- Phase 64 is the missing half of Phase 51's `BUG-02` story. Phase 51 made siblings visible only when you opened the editor; Phase 64 makes them visible when you're listening, which is the higher-value surface.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 64: AudioAddict Siblings on Now Playing" — goal, five success criteria.
- `.planning/REQUIREMENTS.md` §BUG-02 — closure follow-up requirement.
- `.planning/PROJECT.md` Key Decisions — `_aa_channel_key_from_url` strips network slug prefix; AA NETWORKS declaration order.

### Phase 51 precedent (READ FIRST — Phase 64 is its sibling)
- `.planning/phases/51-audioaddict-cross-network-siblings/51-CONTEXT.md` — D-01..D-12 lock the detection mechanism, rendering format, click-action contract for the dialog. Phase 64 inherits D-01 (on-demand detection), D-04 (AA-only gating), D-06 (hidden-when-empty), D-07 (rendering format with `<a>` links and U+2022 bullet), D-08 (link-text format with U+2014 em-dash on name-mismatch), and rejects D-09–D-12 (those are dialog-only).
- `.planning/phases/51-audioaddict-cross-network-siblings/51-PATTERNS.md` — Phase 51 pattern map.

### Code touch points (load these to understand current state)

#### Detection helper (no changes)
- `musicstreamer/url_helpers.py:86-146` — `find_aa_siblings(stations, current_station_id, current_first_url) -> list[tuple[str, int, str]]`. Already pure, already AA-gated, already self-excluded, already NETWORKS-sorted. Phase 64 reuses verbatim per SC #4.
- `musicstreamer/url_helpers.py:32` — `_is_aa_url(url)` — internal gate inside `find_aa_siblings`.
- `musicstreamer/url_helpers.py:38` — `_aa_channel_key_from_url(url, slug=...)`.
- `musicstreamer/url_helpers.py:72` — `_aa_slug_from_url(url)`.

#### Renderer to promote (D-03)
- `musicstreamer/ui_qt/edit_station_dialog.py:531-574` — `EditStationDialog._render_sibling_html(siblings, current_name) -> str`. Move body to `musicstreamer/url_helpers.py` as `render_sibling_html`. Update the only call site at `edit_station_dialog.py` (search for `_render_sibling_html(`) to call the free function via the existing `from musicstreamer.url_helpers import find_aa_siblings` line at `edit_station_dialog.py:53`.

#### NowPlayingPanel surface (where Phase 64 widgets land)
- `musicstreamer/ui_qt/now_playing_panel.py:94` — `class NowPlayingPanel(QWidget)`.
- `musicstreamer/ui_qt/now_playing_panel.py:107-115` — existing `Signal` declarations (`cover_art_ready`, `track_starred`, `edit_requested`, `stopped_by_user`). New `sibling_activated = Signal(object)` joins this group.
- `musicstreamer/ui_qt/now_playing_panel.py:155-161` — `name_provider_label` construction. New sibling label is inserted at line ~162 (immediately after, before `icy_label` at line 164).
- `musicstreamer/ui_qt/now_playing_panel.py:325-344` — `bind_station(station)`. New `self._refresh_siblings()` call inserted after `_populate_stream_picker(station)` at line 344.

#### MainWindow wiring (where the new signal connects)
- `musicstreamer/ui_qt/main_window.py:252` — existing `now_playing.edit_requested.connect(self._on_edit_requested)`. New connection on the next line: `now_playing.sibling_activated.connect(self._on_sibling_activated)`.
- `musicstreamer/ui_qt/main_window.py:316-326` — `_on_station_activated(station)`. Phase 64 reference behavior — `_on_sibling_activated` either delegates here or duplicates the side-effect set per planner judgment.

#### Repo (data source)
- `musicstreamer/repo.py:225` — `Repo.list_stations()` returns `List[Station]` with `streams=...` populated. Phase 64 calls this once inside `_refresh_siblings`.
- `musicstreamer/repo.py` — `get_station(id)` for the sibling lookup at click time.

### Project conventions (apply during planning)
- Bound-method signal connections, no self-capturing lambdas (QA-05) — applies to the new `linkActivated` and `sibling_activated` connections.
- T-39-01 PlainText convention is deviated for the new sibling `QLabel` exactly as Phase 51 deviated, with `html.escape` mitigation preserved by the shared renderer (D-03).
- snake_case + type hints throughout, no formatter (per `.planning/codebase/CONVENTIONS.md`).
- Linux X11 deployment target, DPR=1.0 (per project memory) — HiDPI/Retina/Wayland-fractional findings are downgraded from CRITICAL → WARNING in any UI audit.

### No external specs
No ADRs or external design docs apply. The phase is fully captured by the five success criteria in ROADMAP.md, the Phase 51 precedent, and the four code touch-point clusters above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`find_aa_siblings`** — pure, AA-gated, self-excluded, NETWORKS-sorted. Phase 64 reuses verbatim (SC #4 enforcement is automatic).
- **`_render_sibling_html` body** — exact rendering shape (HTML with `<a>` links, U+2022 bullet, "Also on: " prefix, U+2014 em-dash on name-mismatch, `html.escape` mitigation). Promoted to free function in D-03.
- **`Repo.list_stations()` / `Repo.get_station(id)`** — data sources; no schema change.
- **`MainWindow._on_station_activated`** — the canonical "play this station" side-effect block. Phase 64's new handler delegates to it (D-02).
- **Phase 51 navigation tests** — pattern for testing the click → signal → handler chain (`tests/test_edit_station_dialog.py::test__on_sibling_link_activated_*`). Same shape applies to the new panel handler.

### Established Patterns
- **Signal-out from panel → MainWindow** — `NowPlayingPanel` already emits `edit_requested(Station)`, `track_starred(...)`, `stopped_by_user()`. The new `sibling_activated(Station)` signal slots into the existing pattern.
- **Hidden-when-empty form sections** — `_sibling_label.setVisible(False)` with zero vertical space (Phase 51 D-06; mirrored as Phase 64 D-05).
- **First-stream-URL convention** — `streams[0].url` is the canonical URL for any AA station. Used in `_LogoFetchWorker`, `EditStationDialog._populate`, and now `NowPlayingPanel._refresh_siblings`.
- **Bound-method connections (QA-05)** — applies to all new connections.

### Integration Points
- **New layout slot** — between `name_provider_label` (line 161) and `icy_label` (line 164) in `NowPlayingPanel.__init__`. New `self._sibling_label = QLabel(...)` + four configuration lines (Qt.RichText, no external links, hidden, linkActivated.connect) + `center.addWidget(self._sibling_label)`.
- **New signal** — `sibling_activated = Signal(object)` declared next to existing signals at `now_playing_panel.py:107-115`.
- **New `_refresh_siblings(self)` method** — called from `bind_station` after `_populate_stream_picker`. Reads `self._station.streams[0].url`, calls `find_aa_siblings`, then either `setText(render_sibling_html(...))` + `setVisible(True)` or `setText("")` + `setVisible(False)`.
- **New `_on_sibling_link_activated(self, href)`** — parses `sibling://{id}` href, looks up the sibling via `self._repo.get_station(int(id_str))`, emits `self.sibling_activated.emit(sibling)`. Defense-in-depth: skip if `self._station is None or self._station.id == sibling_id`.
- **New MainWindow handler `_on_sibling_activated(Station)`** — delegates to `self._on_station_activated(station)` (D-02 default) or duplicates the side-effect block per planner judgment. Connected at `main_window.py:~253`.
- **Renderer extraction** — `_render_sibling_html` body moves from `edit_station_dialog.py:531-574` to `url_helpers.py` (next to `find_aa_siblings`). The `EditStationDialog` call site updates to `render_sibling_html(siblings, current_name)`. Phase 51's existing tests adjust if they targeted the private method by name.

</code_context>

<deferred>
## Deferred Ideas

- **Live updates while bound** — D-04 explicitly defers re-derivation on library mutations. If user feedback later shows people expect mid-playback updates (e.g., they edit a sibling, expect it to appear without restarting playback), a follow-up phase can add subscriptions to `station_saved` / `station_deleted` / discovery-import-complete and trigger `_refresh_siblings()`. Pattern precedent: Phase 50's recent-list live-update.
- **Sibling visibility on additional surfaces** — station-list right-click menu, hamburger menu, mini-player. Phase 51 deferred these; Phase 64 closes only the Now Playing surface. Future polish phase if Kyle wants broader reach.
- **Playback continuity hints** — visual indicator that clicking a sibling will interrupt the current track. Today the click is silent and immediate; could become a mini-toast ("Switching to ZenRadio…") for clarity. Not requested; Phase 64 reuses the existing `_on_station_activated` "Connecting…" toast.
- **Keyboard shortcut for sibling jump** — e.g., Alt+1/2/3 for first/second/third sibling. Out of scope; pure mouse/click for v1.
- **Sibling preview on hover** — tooltip showing channel description, current ICY title for the sibling, listener count. Out of scope; default Qt link styling only (Phase 51 D-07 parity).
- **Persisted `aa_channel_key` column** — same rejection as Phase 51 D-01. Library is small enough that on-demand detection cost is negligible.

</deferred>

---

*Phase: 64-audioaddict-siblings-on-now-playing*
*Context gathered: 2026-05-01*
