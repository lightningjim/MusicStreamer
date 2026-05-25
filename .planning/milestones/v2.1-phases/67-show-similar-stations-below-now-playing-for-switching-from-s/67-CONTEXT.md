# Phase 67: Show similar stations below now playing for switching - From same Provider and Same Tag, random 5 from each with refresh, hideable and not shown by default - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning

<domain>
## Phase Boundary

When the user is playing any station, the **Now Playing panel** can surface a dedicated "Similar Stations" section showing two independent random samples drawn from the local library: up to 5 stations from the same provider, and up to 5 stations sharing at least one tag. Each suggestion is a one-click playback switch. A Refresh control re-rolls both samples. The whole feature is opt-in (off by default) via a hamburger-menu toggle, and once enabled the section header itself can be collapsed.

This is a discoverability feature for switching mid-listen — distinct from Phase 64's "Also on:" line, which surfaces only the deterministic AudioAddict cross-network siblings of the same channel. Phase 64's line keeps its position and behavior; Phase 67 adds a separate UI region.

**In scope:**
- New "Similar Stations" sub-section at the bottom of `NowPlayingPanel`'s center column with two labeled lists ("Same provider:" and "Same tag:"), each rendering up to 5 vertical clickable rows.
- Hamburger-menu master toggle ("Show similar stations") near the Phase 66 Theme picker, persisted via `Repo.set_setting('show_similar_stations', '0'/'1')`, default `'0'`.
- Section-header collapser (only meaningful when master toggle is ON), persisted via `Repo.set_setting('similar_stations_collapsed', '0'/'1')`.
- Refresh button (single ↻ icon) at the section header that re-rolls both pools.
- Click-to-switch wiring through `MainWindow` — same plumbing as picking from the station list and as Phase 64 sibling click (refresh recent, "Connecting…" toast, media-keys metadata, last-played update).
- Random sample lifetime: rolled on first `bind_station` for a given station, cached in-memory keyed by station id, reused on subsequent binds of the same station; Refresh always re-rolls.
- Pool exclusions: self, AA siblings already shown in Phase 64's "Also on:" line, no-tag candidates (Same tag pool only), no-provider candidates (Same provider pool only).
- Show-all when pool < 5 (no padding, no placeholder).

**Out of scope:**
- Surfacing similar stations on additional surfaces (station-list right-click menu, hamburger menu, mini-player, EditStationDialog) — could be future polish.
- Live-update the rendered sample on `station_saved` / `station_deleted` / discovery-import-complete signals. Sample is stale-OK until next `bind_station` of a different station, or until user clicks Refresh. Click-time defensive lookup handles deleted-station case (skip silently, parity with Phase 64 dual-shape repo handling).
- Cross-pool dedup — a station qualifying under both "Same provider" and "Same tag" intentionally appears in both lists (allow-duplicates per T-03).
- Smarter ranking — favorites boost, recently-played weighting, listener count, tag-overlap-count ranking. Today the pool is uniformly randomly sampled.
- New tag-parsing semantics — reuses `filter_utils.normalize_tags()` verbatim (T-02).
- Custom collapsible-widget animations, theme-aware refresh icon styling beyond what Phase 66 themes already provide.
- Phase 64 "Also on:" line behavior — untouched. The Phase 67 exclusion (T-04b) reads from the same `find_aa_siblings` call, but does not modify the existing `_sibling_label` or its `_refresh_siblings` method.

</domain>

<decisions>
## Implementation Decisions

### Layout structure

- **D-01:** A new dedicated "Similar Stations" section is added to `NowPlayingPanel`. Placement: at the bottom of the **center column** (`center: QVBoxLayout`, the same column that holds `name_provider_label`, `_sibling_label`, `icy_label`, `elapsed_label`, controls). Position: after the existing controls block, as a new visually-grouped sub-region with its own header — NOT inline below the Phase 64 `_sibling_label` "Also on:" line. The Phase 64 line keeps its current insertion point at `now_playing_panel.py:265-271` between `name_provider_label` and `icy_label`.
- **D-02:** Inside the Similar Stations region, render **two labeled sub-sections**: "Same provider:" and "Same tag:". Each sub-section is hidden-when-empty independently (zero vertical space when empty, mirroring Phase 64's D-05 contract). When both pools are empty for the bound station, the entire Similar Stations section body is empty — but the section header still shows (when master toggle ON) so the user knows the feature is active and can refresh.
- **D-03:** Each suggestion renders as a **vertical link list** — one station per line, one clickable row per station. Distinct from Phase 64's single-line bullet-separated inline format, because per-row rendering scales cleanly to up to 5 rows × 2 sections = up to 10 rows of vertical real estate without cramming. Implementation: planner picks between (a) a single `QLabel` per sub-section using `Qt.RichText` with `<br>`-separated `<a>` links, or (b) a `QVBoxLayout` of one clickable widget per row. Both are acceptable; (a) reuses Phase 64's renderer pattern more closely.
- **D-04:** Per-row content varies by section:
  - "Same provider" rows show **just the station name** (e.g., `"Drone Zone"`) — provider is implicit in the section header.
  - "Same tag" rows show **`"{Name} ({Provider})"`** (e.g., `"Drone Zone (SomaFM)"`) — provider matters because tag-matches cross provider boundaries.
- **D-04a:** Section header uses a discreet font (planner picks; default to Phase 66 theme defaults). Sub-section labels ("Same provider:" / "Same tag:") render at smaller weight than the section header, larger weight than the link rows.

### Show/hide control

- **S-01:** A **master enable toggle** is added to the hamburger menu, placed **near the Phase 66 Theme picker** (which sits in the visual/personalization region of the menu). Implemented as a `QAction` with `setCheckable(True)`. State is persisted in the SQLite settings table via `Repo.set_setting('show_similar_stations', '0' or '1')` and read with `Repo.get_setting('show_similar_stations', '0')`. **Default `'0'`** on first launch — satisfies the "not shown by default" goal.
- **S-02:** When the master toggle is **OFF**, the panel shows **NOTHING** for the Similar Stations section — no header, no expander, no body. The `QVBoxLayout` reclaims zero vertical space (use `setVisible(False)` on the section's container widget). Feature is invisible until enabled. This satisfies "hideable" cleanly: if you don't want to see it, it isn't there.
- **S-03:** When the master toggle is **ON**, the section is rendered with a **collapsible section header**. Header text: `"Similar Stations"` with an arrow indicator (`▾` when expanded, `▸` when collapsed). Clicking the header toggles the body visibility and persists the new state via `Repo.set_setting('similar_stations_collapsed', '0' or '1')`. Default collapsed state on first enable: **expanded** (`'0'`) so the user immediately sees what they just enabled.
- **S-03a:** Two persisted settings keys total: `show_similar_stations` (master) and `similar_stations_collapsed` (header collapse). Both are stable across launches. Toggling the master OFF then back ON should remember the prior `similar_stations_collapsed` value (no auto-reset).

### Tag matching semantics

- **T-01:** **Union semantics.** The "Same tag" pool consists of all candidate stations sharing **at least one tag** (after normalization) with the currently playing station. For a station tagged `"ambient, downtempo, electronic"`, candidates tagged with any one of those three qualify.
- **T-02:** **Reuse `filter_utils.normalize_tags()`** as the single source of truth for tag parsing. `normalize_tags(station.tags)` returns a list of casefolded, stripped, deduplicated tags — same code path as the station-list filter chips. Pool intersection check: `len(set(normalize_tags(current.tags)) & set(normalize_tags(candidate.tags))) > 0`.
- **T-03:** **Allow duplicates between pools.** A station qualifying under both "Same provider" (e.g., SomaFM "Drone Zone" when current station is also on SomaFM) and "Same tag" (because they share a tag) appears in BOTH lists. No cross-list dedup. Sampling is independent per pool.
- **T-04:** **Pool exclusions** (apply to both pools):
  - **(a) Self** — the currently playing station's id is excluded. Mirrors Phase 64's `find_aa_siblings` self-exclusion guard at `url_helpers.py:122`.
  - **(b) Phase 64 AA siblings already shown** — call `find_aa_siblings(stations, current_station.id, current.streams[0].url)` once during pool derivation; collect those station ids into an exclusion set; remove from both Same provider and Same tag pools. Avoids triple-listing the same station across "Also on:", "Same provider:", and "Same tag:". Acceptable cost: one additional in-memory pass over the station list per refresh.
  - **(c) For Same tag pool only:** candidates whose `normalize_tags(candidate.tags)` returns an empty list. They could never match by tag anyway; explicit guard makes intent clear.
  - **(d) For Same provider pool only:** candidates whose `provider_id` is `None` are excluded when the current station's `provider_id` is set. Two-NULL-providers are not considered "same provider" — drop them from the pool.

### Random sample lifetime + refresh

- **R-01:** **Cached random sample, in-memory only.** A new private dict on `NowPlayingPanel` (e.g., `self._similar_cache: dict[int, tuple[list[Station], list[Station]]]`) maps `station_id → (same_provider_sample, same_tag_sample)`. The cache is purely in-memory (not persisted to SQLite) and is cleared on app restart.
- **R-02:** **Roll-on-bind-if-not-cached.** Inside `bind_station`, after the existing `_refresh_siblings()` call (line 532), invoke a new `_refresh_similar_stations()` method. If `self._station.id` already has an entry in `self._similar_cache`, reuse it (no re-roll). If not, derive both pools from `self._repo.list_stations()`, apply exclusions (T-04), randomly sample up to 5 from each, store under `self._station.id`, render. Result: switching back to a station you already played returns the same suggestions you saw last time, until you Refresh or restart the app.
- **R-03:** **Refresh button always re-rolls.** A single small `↻` icon button placed at the right edge of the section header (or as a sibling to the collapse arrow). Clicking deletes the current station's entry from `self._similar_cache` and re-runs the derivation+sample step, then re-renders. Re-rolls **both** pools (Same provider + Same tag) in one action. No per-section refresh icons.
- **R-04:** **Stale-OK on library mutations.** No subscriptions to `station_saved` / `station_deleted` / discovery-import-complete signals. Cached sample may reference deleted stations (handled via defense-in-depth at click-time: `_repo.get_station(...)` wrapped in try/except + None-check, mirroring Phase 64's dual-shape repo pattern at `now_playing_panel.py:941-955`) or miss newly-imported stations (user clicks Refresh to see them). Matches Phase 64's D-04 invariant philosophy.
- **R-05:** **Show all when pool < 5.** If the Same provider pool has only 3 candidates, the sample is all 3 (no random selection needed; no padding, no "(only N similar stations)" note, no "import more" promo). Empty pool → that sub-section hidden per D-02.
- **R-06:** **Random source.** Use Python's `random.sample()` (or `random.choices(k=...)` if duplicate-allowed, but T-03 is about cross-pool, not within-pool — so within-pool uses `random.sample` for distinct picks). No deterministic seeding; truly random per refresh. Acceptable since the sample is cached (R-02), so the user sees a stable result until they explicitly refresh.

### Integration with existing Phase 64 sibling line

- **I-01:** The Phase 64 `_sibling_label` and its `_refresh_siblings()` method are **not modified** structurally. The Phase 67 derivation calls `find_aa_siblings(...)` independently to compute the exclusion set (T-04b); it does not share state with Phase 64's renderer.
- **I-02:** Click handling reuses the **existing `sibling_activated = Signal(object)`** pattern. Either (a) introduce a new signal `similar_activated = Signal(object)` with its own MainWindow handler, or (b) reuse `sibling_activated` for both Phase 64 and Phase 67 since the side-effect (switch playback to the chosen station) is identical. **Recommendation: new signal** for traceability and decoupling — the planner can still wire its handler to delegate to `_on_station_activated` exactly like `_on_sibling_activated` does.
- **I-03:** The `<a href>` payload format mirrors Phase 64's: integer-only `"sibling://{id}"` (or use a fresh prefix like `"similar://{id}"` if a new signal is introduced per I-02). Same security properties: integer-only payload, no injection surface.

### Click action wiring

- **C-01:** The MainWindow handler for similar-station clicks is `_on_similar_activated(Station)` (or whatever name the planner picks per I-02). It **delegates to `self._on_station_activated(station)`** so the entire side-effect set (bind_station, player.play, update_last_played, refresh_recent, "Connecting…" toast, media-keys metadata + playing state) fires uniformly. Same delegation pattern as Phase 64's `_on_sibling_activated`.
- **C-02:** No dirty-state confirmation; no playback failover machinery; no preview/hover behavior — pure click → switch. Parity with Phase 64.

### Hamburger menu integration

- **M-01:** The new `QAction` for the master toggle ("Show similar stations") is added in `MainWindow`'s hamburger-menu construction code. Place adjacent to the Phase 66 Theme picker (search for the Theme picker `QAction` insertion site). Connected via bound method (QA-05 — no self-capturing lambdas) to a new slot `_on_show_similar_toggled(bool)` that:
  1. Calls `self._repo.set_setting('show_similar_stations', '1' if checked else '0')`.
  2. Calls `self.now_playing.set_similar_visible(bool)` (a new public method on `NowPlayingPanel`) which toggles the section container's visibility.
- **M-02:** On `MainWindow.__init__`, after constructing the action, set its initial checked state from `self._repo.get_setting('show_similar_stations', '0') == '1'` and pass the same value to `self.now_playing.set_similar_visible(...)` so the initial render matches the persisted preference. Same wiring pattern Phase 66 uses for the Theme picker initial state.

### Claude's Discretion

- **Exact section/sub-section header wording.** "Similar Stations" / "Same provider:" / "Same tag:" are recommendations. Planner can refine for visual fit (e.g., "More on this provider:" / "Similar genres:") but the **two-section structure (D-02) is locked**.
- **Renderer choice (D-03).** Single `QLabel` with `<br>`-separated `<a>` links, vs `QVBoxLayout` of clickable rows. Both meet the contract; planner picks based on test ergonomics and code reuse with Phase 64's `render_sibling_html`. If reusing `render_sibling_html`, a thin wrapper (e.g., `render_similar_html(stations, separator='<br>', show_provider=bool)`) is acceptable.
- **Signal name (I-02).** `similar_activated` is the recommended default. If the planner finds reuse of the existing `sibling_activated` signal cleaner (with a discriminator on the href prefix), that is acceptable as long as the side-effect set remains uniform.
- **Where the Refresh icon sits.** Right edge of the section header is recommended; left of the collapse arrow vs right of it is a planner judgment call. Keyboard shortcut for Refresh is **not** required for v1.
- **Where the "Similar Stations" container widget lives in the layout.** Inside the existing center column (after controls) is the lock; whether it's a `QGroupBox`, a custom `QWidget` with a styled border, or a plain `QVBoxLayout` block is the planner's call.
- **Sample ordering within the rendered list.** After `random.sample(...)` returns the picks, render order can be (a) the random order returned by `random.sample`, or (b) alphabetical for stability/scannability. Either is acceptable; alphabetical recommended for predictability since the contents are random.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 67: Show similar stations below now playing for switching - From same Provider and Same Tag, random 5 from each with refresh, hideable and not shown by default" — the goal statement and the source of all locked nouns ("Same Provider", "Same Tag", "random 5 from each", "refresh", "hideable", "not shown by default").
- `.planning/REQUIREMENTS.md` — Phase 67 is a v2.1 rolling-polish phase added during the milestone; not yet mapped in the traceability table at the time of this discussion. The phase ships a discoverability feature, not a requirement-driven bug fix.
- `.planning/PROJECT.md` Current State — confirms `NowPlayingPanel` three-column layout (logo | center | cover art), confirms tags are comma-separated and parsed via `filter_utils`, confirms hamburger menu is the canonical location for global toggles.

### Phase 64 precedent (READ FIRST — Phase 67 is its conceptual sibling)
- `.planning/phases/64-audioaddict-siblings-on-now-playing/64-CONTEXT.md` — D-01..D-08 lock the AA-only "Also on:" rendering, signal pattern, click-action delegation, hidden-when-empty contract, and the dual-shape repo defense-in-depth pattern. Phase 67 inherits the **signal-out-from-panel pattern (D-02), bind_station refresh trigger (D-04), hidden-when-empty (D-05), `<a href="sibling://{id}">` href format (D-03a), bound-method connections, defense-in-depth repo lookup at click time** — and rejects the AA-network-only gating (Phase 67 is provider-agnostic + tag-driven).

### Code touch points (load these to understand current state)

#### Now Playing panel surface (where Phase 67 widgets land)
- `musicstreamer/ui_qt/now_playing_panel.py:94` — `class NowPlayingPanel(QWidget)`.
- `musicstreamer/ui_qt/now_playing_panel.py:200` — `sibling_activated = Signal(object)` — Phase 64 signal; Phase 67 adds a sibling signal (e.g., `similar_activated = Signal(object)` per I-02).
- `musicstreamer/ui_qt/now_playing_panel.py:240-291` — center column construction (`name_provider_label` → `_sibling_label` → `icy_label` → `elapsed_label` → controls). Phase 67's "Similar Stations" container is appended after the controls block (last item in the column).
- `musicstreamer/ui_qt/now_playing_panel.py:325-540` — `bind_station(station)`. Phase 67 adds a new `_refresh_similar_stations()` call **after** the existing `_refresh_siblings()` call at line 532 (so the Phase 64 line populates first; the Phase 67 exclusion set reads from the result).
- `musicstreamer/ui_qt/now_playing_panel.py:893-1010` — Phase 64 helper region (`_refresh_siblings`, `_on_sibling_link_activated`). Phase 67's parallel helpers (`_refresh_similar_stations`, `_on_similar_link_activated`) live in a new region immediately below this block; the file structure mirrors Phase 64.

#### MainWindow wiring (where the new signal connects + hamburger menu sits)
- `musicstreamer/ui_qt/main_window.py:252` — existing `now_playing.edit_requested.connect(...)`.
- `musicstreamer/ui_qt/main_window.py:~253-254` — Phase 64 `now_playing.sibling_activated.connect(self._on_sibling_activated)`. Phase 67 adds `now_playing.similar_activated.connect(self._on_similar_activated)` on the next line.
- `musicstreamer/ui_qt/main_window.py:316-326` — `_on_station_activated(station)` — the canonical "play this station" side-effect block. Phase 67's new `_on_similar_activated(Station)` delegates here (C-01), parity with `_on_sibling_activated`.
- `musicstreamer/ui_qt/main_window.py` (Theme picker construction site, Phase 66) — locate the Theme picker `QAction` and add the "Show similar stations" `QAction` adjacent to it (M-01). Search for Phase 66 hamburger insertion or the THEME-01 commit.

#### Tag parsing helper (no changes — reuse only)
- `musicstreamer/filter_utils.py:44, 75` — `normalize_tags(station.tags)` — canonical tag parser, returns list of casefolded, stripped, deduplicated tags. Phase 67 calls this directly (T-02).

#### AA siblings exclusion source (read-only call)
- `musicstreamer/url_helpers.py:86-146` — `find_aa_siblings(stations, current_station_id, current_first_url)`. Phase 67 calls this once per `_refresh_similar_stations` invocation, collects the returned `(name, id, network)` tuples' ids into an exclusion set (T-04b). No modifications to `find_aa_siblings`.

#### Settings persistence (master toggle + collapser state)
- `musicstreamer/repo.py:93` — settings table schema (`(key TEXT PRIMARY KEY, value TEXT NOT NULL)`).
- `musicstreamer/repo.py:348-359` — `Repo.get_setting(key, default) -> str` and `Repo.set_setting(key, value)`. Phase 67 introduces two new keys: `show_similar_stations` (S-01, default `'0'`) and `similar_stations_collapsed` (S-03, default `'0'` after first enable).

#### Repo (data source for pool derivation)
- `musicstreamer/repo.py:225` — `Repo.list_stations()` — already used by Phase 64's `_refresh_siblings`. Phase 67 reuses the same call (one read per refresh).
- `musicstreamer/repo.py:271+` — `Repo.get_station(id)` — used at click time for sibling lookup. Phase 67 click handler does the same; defense-in-depth wrap per Phase 64's pattern at `now_playing_panel.py:941-955`.

#### Models (no schema change)
- `musicstreamer/models.py:24-37` — `Station` dataclass. Relevant fields: `id`, `name`, `provider_id`, `provider_name`, `tags`, `streams`. No schema change.

### Project conventions (apply during planning)
- **Bound-method signal connections, no self-capturing lambdas (QA-05)** — applies to the new `linkActivated` connection on the Similar Stations renderer, the new `similar_activated` connection in MainWindow, the new `triggered` connection on the master-toggle `QAction`, and the section-header click handler.
- **T-39-01 PlainText convention** — deviated for the new Similar Stations renderer label exactly as Phase 51/64 deviated, with `html.escape` mitigation in any HTML produced. Network/provider names from compile-time constants are safe; station names from user input are escaped.
- **snake_case + type hints throughout, no formatter** (per `.planning/codebase/CONVENTIONS.md`).
- **Linux Wayland deployment target, DPR=1.0** (per project memory) — HiDPI/Retina/Wayland-fractional findings are downgraded from CRITICAL → WARNING in any UI audit; Wayland-native diagnostics preferred over xprop.

### No external specs
No ADRs or external design docs apply. The phase is fully captured by the ROADMAP.md goal, the Phase 64 precedent for the panel-signal-MainWindow pattern, the four code touch-point clusters above, and the decisions in this CONTEXT.md.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`filter_utils.normalize_tags(station.tags)`** — canonical tag parser. Same call already used by `station_list_panel.py` for filter chips and by `filter_utils` itself for filter logic. T-02 reuses verbatim.
- **`find_aa_siblings(stations, current_station_id, current_first_url)`** — pure, AA-gated, self-excluded function. Phase 67 calls it for the **exclusion set** (T-04b), not for inclusion — the returned siblings are removed from the Phase 67 pools so they don't triple-list with Phase 64's "Also on:" line.
- **`Repo.list_stations()` / `Repo.get_station(id)`** — same data sources Phase 64 uses; one list_stations per refresh, one get_station per click.
- **`Repo.get_setting / set_setting`** — SQLite settings table is the persistence path for both new preference keys (S-01, S-03). Same pattern Phase 66 (theme picker) uses.
- **`MainWindow._on_station_activated(station)`** — the canonical "play this station" side-effect block. Phase 67's `_on_similar_activated` delegates here (C-01). Same pattern as Phase 64's `_on_sibling_activated`.
- **Phase 64 `_refresh_siblings` and `_on_sibling_link_activated`** — direct structural template for Phase 67's `_refresh_similar_stations` and `_on_similar_link_activated`. Same defense-in-depth shape (try/except on repo calls, None-check on dual-shape `get_station`, slots-never-raise discipline).
- **Phase 66 Theme picker** — direct template for the new master-toggle `QAction` in the hamburger menu (M-01, M-02): construction site, persistence wiring, initial-state read on `__init__`.
- **Phase 64 navigation tests** (`tests/test_now_playing_panel.py::test__on_sibling_link_activated_*` if it exists; otherwise `tests/test_edit_station_dialog.py::test__on_sibling_link_activated_*`) — pattern for testing the click → signal → handler chain. Same shape applies to the new similar-station handler.

### Established Patterns
- **Signal-out from panel → MainWindow** — `NowPlayingPanel` already emits `edit_requested(Station)`, `track_starred(...)`, `stopped_by_user()`, `sibling_activated(Station)`. New `similar_activated(Station)` (or reused `sibling_activated`, planner's call per I-02) slots into the existing pattern.
- **Hidden-when-empty form sections** — `_sibling_label.setVisible(False)` with zero vertical space (Phase 51 D-06, Phase 64 D-05). Phase 67 mirrors this for both sub-sections (D-02) AND for the entire section container when the master toggle is OFF (S-02).
- **First-stream-URL convention** — `streams[0].url` is the canonical URL for any station. Used in Phase 64's `_refresh_siblings`. Phase 67 needs `current_first_url` for the `find_aa_siblings(...)` exclusion call (T-04b); reuses the same convention.
- **Bound-method connections (QA-05)** — applies to all new connections (linkActivated, similar_activated, QAction.triggered, header-click handler).
- **PlainText convention deviation for `<a>` link rendering** — Phase 51 and Phase 64 both deviate from T-39-01 for `_sibling_label`; Phase 67's similar-list renderer follows the same pattern with `html.escape` mitigation.
- **SQLite-key/value settings persistence pattern** — Phase 66 (theme), color theming (accent_color), and now Phase 67's two new keys all flow through `Repo.get_setting / set_setting`. Consistent with project convention.

### Integration Points
- **New Similar Stations container** — appended to `center: QVBoxLayout` after the controls block in `NowPlayingPanel.__init__` (around line 290+, after `controls.addLayout(...)` if that's where controls end).
- **New `_refresh_similar_stations(self)` method** — called from `bind_station` after `_refresh_siblings` at line 532. Reads `self._station`, `self._station.streams[0].url` (defensively), calls `self._repo.list_stations()`, calls `find_aa_siblings(...)` for exclusion set, derives both pools, samples, caches under `self._station.id`, renders.
- **New `_on_similar_link_activated(self, href)`** — parses `similar://{id}` (or `sibling://{id}` if signal is reused), looks up Station via wrapped `self._repo.get_station(int(id_str))` (dual-shape pattern from `now_playing_panel.py:941-955`), emits `self.similar_activated.emit(station)`. Defense-in-depth: skip if `self._station is None or self._station.id == similar_id`.
- **New MainWindow handler `_on_similar_activated(Station)`** — delegates to `self._on_station_activated(station)`. Connected at `main_window.py:~254` adjacent to the existing Phase 64 connection.
- **New hamburger menu `QAction` "Show similar stations"** — added near the Phase 66 Theme picker. Wired to `_on_show_similar_toggled(bool)` slot which persists to SQLite and calls `self.now_playing.set_similar_visible(bool)`. Initial state read on `__init__` from `Repo.get_setting('show_similar_stations', '0')`.
- **New public `set_similar_visible(visible: bool)` method on `NowPlayingPanel`** — toggles the Similar Stations container `setVisible(visible)`. Public surface required because `MainWindow` owns the menu state and needs to push it into the panel.
- **New `_similar_cache: dict[int, tuple[list[Station], list[Station]]]`** — instance attribute on `NowPlayingPanel`. Initialized in `__init__` to `{}`. Read/written by `_refresh_similar_stations`. Cleared on Refresh-button click for the current station id only (not flushed wholesale).

</code_context>

<specifics>
## Specific Ideas

- The user-visible promise: **"While I'm playing Drone Zone, I see up to 5 other SomaFM stations and up to 5 stations tagged 'ambient' below — one click on any of them switches me to that station, just like clicking from the station list."**
- The feature is **off by default** because most users want a clean Now Playing panel; only users who actively want discoverability turn it on.
- The Refresh button is the user's "I don't like these picks" affordance. No need for sorting, ranking, or smart selection — randomness + the Refresh button is the answer.
- Phase 67 explicitly composes with Phase 64 (T-04b exclusion) so the three lists never duplicate the same station. From top to bottom on a station with both AA siblings and similar stations: `Also on:` (AA cross-network siblings, Phase 64 inline) → controls → `Similar Stations` (collapsible) → `Same provider:` → `Same tag:`.
- Cache lifetime (R-01..R-04) is deliberately the simplest model that meets the goal: in-memory only, keyed by station id, no signal subscriptions, defense-in-depth at click-time. This was the Phase 64 D-04 philosophy and is reaffirmed for Phase 67.

</specifics>

<deferred>
## Deferred Ideas

- **Surfacing on additional surfaces** — station-list right-click menu, hamburger menu mini-list, mini-player, EditStationDialog. Phase 67 only touches NowPlayingPanel. Future polish if Kyle wants broader reach.
- **Smarter ranking** — favorites boost (preferentially sample stations the user has starred), recently-played weighting, listener count from RadioBrowser, tag-overlap-count ranking (stations sharing more tags ranked higher within the random pool). Today the pool is uniformly randomly sampled. Could become Phase 67.x or a separate "discovery quality" phase.
- **Live-update on library mutations** — subscribe to `station_saved` / `station_deleted` / discovery-import-complete so the cached sample auto-invalidates when the underlying library changes. Today: stale-OK until next bind/refresh, with click-time defensive lookup. If users complain about ghost entries after deletes, revisit.
- **Per-section refresh icons** — currently a single ↻ refreshes both pools (R-03). Per-section refresh would let users keep one pool and re-roll the other. Adds two icons to a small section.
- **Keyboard shortcut for Refresh** — e.g., `Ctrl+R` or `F5` while focus is in the panel. Out of scope for v1; pure mouse/click.
- **"Why suggested" tooltip** — hover a "Same tag" row to see which tag matched. Useful for current station with multiple tags. Out of scope; section header is sufficient.
- **Visual context on each row beyond name + provider** — tiny logo, ICY title preview, listener count, tag chips. D-04 locks the per-row content; richer rendering is a future polish.
- **Smarter random** — deterministic seed per session for reproducibility, anti-recency (don't re-pick a station that was in the last 3 refreshes). Today truly random with no anti-recency.
- **Per-pool size override** — let the user configure "show 5 from same provider, 10 from same tag" via the hamburger or a settings dialog. Today fixed at 5+5 per the goal.
- **Same-tag-as-primary-tag-only pool** — if the union semantics (T-01) produces too noisy a pool for a station with many tags, an alternate "primary tag only" mode could be added. Today: union, with the Refresh button as the noise-mitigator.

</deferred>

---

*Phase: 67-show-similar-stations-below-now-playing-for-switching-from-s*
*Context gathered: 2026-05-09*
