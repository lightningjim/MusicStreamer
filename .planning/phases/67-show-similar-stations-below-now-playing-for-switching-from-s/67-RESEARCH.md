# Phase 67: Show similar stations below now playing for switching - Research

**Researched:** 2026-05-09
**Domain:** PySide6 UI extension to NowPlayingPanel — Phase 64 sibling-line conceptual parallel; Phase 47.1 stats-toggle / Phase 50 BUG-01 panel-method seam patterns; SQLite settings persistence; pure-Python random sampling helper
**Confidence:** HIGH (every code reference verified by direct file read; every reusable pattern in the codebase has 1+ landed precedent; standard-library `random.sample` semantics verified by live Python invocation)

## Summary

Phase 67 is a pure composition of patterns already shipped in this codebase. There is **no novel framework decision required**. The closest precedent — Phase 64's `_sibling_label` / `sibling_activated` chain — supplies the renderer pattern, click-handler shape, MainWindow handler shape, and test scaffolding. The Phase 47.1 "Stats for Nerds" QAction supplies the master-toggle pattern (checkable QAction in hamburger → bound-method slot → persist + push to panel via `set_X_visible` public method). The Phase 50 / BUG-01 dual-shape repo defense pattern (`now_playing_panel.py:941-955`) supplies the click-time `get_station(id)` lookup shape. Phase 66 only contributes the hamburger-menu **insertion site** (the new "Show similar stations" QAction is a peer of "Theme" / "Accent Color" in the Settings group); Phase 66 itself uses a *dialog* pattern that is **not** the right model for Phase 67's checkable toggle.

The single net-new piece of factoring is a **pure-Python helper** `pick_similar_stations(stations, current_station, *, sample_size=5, rng=None)` that returns `(same_provider_sample, same_tag_sample)`. Living in `musicstreamer/url_helpers.py` (next to `find_aa_siblings` / `render_sibling_html`) keeps phase-67 logic colocated with phase-51/64 logic and lets the bulk of behavior be unit-tested without a Qt fixture — the existing `tests/test_aa_siblings.py` is the structural template.

The collapsible-section header is implemented with the **`station_list_panel.py:516-519` `_toggle_filter_strip` pattern** — a flat `QPushButton` with `▶ ` / `▼ ` glyph prefix that toggles the body container's `setVisible(...)`. This is the only collapsible-widget idiom in the codebase; no third-party widget, no `QGroupBox.setCheckable(True)`. Persistence uses the same SQLite settings keys mechanism (`Repo.get_setting` / `Repo.set_setting`) Phase 47.1 / 59 / 66 already use.

**Primary recommendation:** Mirror Phase 64 verbatim for the renderer + click chain. Mirror Phase 47.1 verbatim for the hamburger toggle + `set_X_visible` panel method. Extract the pool-derivation + sampling into a pure helper that takes an injectable `rng` for deterministic tests. Use the `_toggle_filter_strip`-style flat-button collapse header. Use a single Qt.RichText `QLabel` per sub-section (one for "Same provider:", one for "Same tag:") with `<br>`-separated `<a>` rows, mirroring Phase 64's renderer reuse — alphabetical ordering after sampling for scannability.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pool derivation (filter all stations into "same provider" + "same tag") | Pure Python helper (`musicstreamer/url_helpers.py`) | — | Has zero Qt/DB coupling; mirrors `find_aa_siblings` placement and testability shape |
| Random sampling (5 from each pool, with `rng` injection) | Pure Python helper (`musicstreamer/url_helpers.py`) | — | Deterministic via injected `random.Random`; testable with no Qt fixture |
| Tag normalization | Existing pure helper (`musicstreamer/filter_utils.normalize_tags`) | — | Already canonical (T-02 LOCK); reused unchanged |
| AA-sibling exclusion source | Existing pure helper (`musicstreamer/url_helpers.find_aa_siblings`) | — | Already canonical; called read-only inside the new helper for the T-04b exclusion set |
| Per-station-id cache (in-memory) | NowPlayingPanel instance attribute | — | Cache lifetime tied to panel lifetime; no SQLite persistence per R-01 |
| Section render (RichText `<a>` link list) | NowPlayingPanel (Qt widget) | Pure helper for HTML construction (`render_similar_html`) | Renderer can be a free function colocated with `render_sibling_html` for dual-test surface |
| Click-to-switch handler (panel side) | NowPlayingPanel (`_on_similar_link_activated`) | — | Mirrors `_on_sibling_link_activated`; defense-in-depth `get_station` wrapper |
| Click delegation (window side) | MainWindow (`_on_similar_activated`) | — | Mirrors `_on_sibling_activated`; one-line delegate to `_on_station_activated` |
| Master toggle persistence | Repo.set_setting (SQLite settings table) | — | Same persistence path as Phase 47.1 / 59 / 66 |
| Master toggle UI control | MainWindow QAction (checkable, in `_menu`) | — | Mirrors `_act_stats` (Phase 47.1) — peer placement next to Phase 66 Theme picker |
| Section-header collapse persistence | Repo.set_setting (SQLite settings table) | — | Second key alongside master toggle |
| Section-header collapse UI control | NowPlayingPanel (flat `QPushButton` with `▶`/`▼` prefix) | — | Mirrors `station_list_panel._toggle_filter_strip` — only collapsible-section idiom in codebase |
| Refresh button | NowPlayingPanel (`QToolButton` with `↻` icon) | — | Same shape as existing controls (e.g., star_btn 28×28 QToolButton) |
| Initial visibility wiring | MainWindow `__init__` after panel construction | — | Mirrors Phase 47.1 WR-02 line 338: `self.now_playing.set_stats_visible(self._act_stats.isChecked())` |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Layout structure
- **D-01:** A new dedicated "Similar Stations" section is added to `NowPlayingPanel`. Placement: at the bottom of the **center column** (`center: QVBoxLayout`, the same column that holds `name_provider_label`, `_sibling_label`, `icy_label`, `elapsed_label`, controls). Position: after the existing controls block, as a new visually-grouped sub-region with its own header — NOT inline below the Phase 64 `_sibling_label` "Also on:" line. The Phase 64 line keeps its current insertion point at `now_playing_panel.py:265-271` between `name_provider_label` and `icy_label`.
- **D-02:** Inside the Similar Stations region, render **two labeled sub-sections**: "Same provider:" and "Same tag:". Each sub-section is hidden-when-empty independently (zero vertical space when empty, mirroring Phase 64's D-05 contract). When both pools are empty for the bound station, the entire Similar Stations section body is empty — but the section header still shows (when master toggle ON) so the user knows the feature is active and can refresh.
- **D-03:** Each suggestion renders as a **vertical link list** — one station per line, one clickable row per station. Distinct from Phase 64's single-line bullet-separated inline format, because per-row rendering scales cleanly to up to 5 rows × 2 sections = up to 10 rows of vertical real estate without cramming. Implementation: planner picks between (a) a single `QLabel` per sub-section using `Qt.RichText` with `<br>`-separated `<a>` links, or (b) a `QVBoxLayout` of one clickable widget per row. Both are acceptable; (a) reuses Phase 64's renderer pattern more closely.
- **D-04:** Per-row content varies by section:
  - "Same provider" rows show **just the station name** (e.g., `"Drone Zone"`) — provider is implicit in the section header.
  - "Same tag" rows show **`"{Name} ({Provider})"`** (e.g., `"Drone Zone (SomaFM)"`) — provider matters because tag-matches cross provider boundaries.
- **D-04a:** Section header uses a discreet font (planner picks; default to Phase 66 theme defaults). Sub-section labels ("Same provider:" / "Same tag:") render at smaller weight than the section header, larger weight than the link rows.

#### Show/hide control
- **S-01:** Master enable toggle in hamburger menu, near the Phase 66 Theme picker. `QAction` with `setCheckable(True)`, persisted via `Repo.set_setting('show_similar_stations', '0' or '1')`, default `'0'`.
- **S-02:** When master toggle is OFF, panel shows NOTHING for the section (container `setVisible(False)`).
- **S-03:** When master toggle is ON, section renders with collapsible header (`▾` expanded / `▸` collapsed), persisted via `Repo.set_setting('similar_stations_collapsed', '0' or '1')`, default `'0'` (expanded) on first enable.
- **S-03a:** Two persisted settings keys total: `show_similar_stations` (master) and `similar_stations_collapsed` (header collapse). Both stable across launches; toggling master OFF then back ON remembers prior collapse state.

#### Tag matching semantics
- **T-01:** Union semantics — pool = candidates sharing at least one normalized tag.
- **T-02:** Reuse `filter_utils.normalize_tags()` verbatim.
- **T-03:** Allow duplicates between pools (no cross-list dedup).
- **T-04:** Pool exclusions for both pools:
  - **(a)** Self id (mirrors `find_aa_siblings` self-exclusion at `url_helpers.py:122`).
  - **(b)** Phase 64 AA siblings — call `find_aa_siblings(...)` once during pool derivation; collect ids into exclusion set; remove from both pools.
  - **(c)** For Same tag pool only: candidates with empty `normalize_tags(tags)`.
  - **(d)** For Same provider pool only: candidates with `provider_id is None` when current station's `provider_id` is set.

#### Random sample lifetime + refresh
- **R-01:** In-memory cache only — `self._similar_cache: dict[int, tuple[list[Station], list[Station]]]`.
- **R-02:** Roll-on-bind-if-not-cached. After existing `_refresh_siblings()` call at `bind_station` line 532, invoke new `_refresh_similar_stations()` method.
- **R-03:** Refresh button always re-rolls — single ↻ icon at section header, deletes current station's cache entry and re-derives both pools.
- **R-04:** Stale-OK on library mutations (no signal subscriptions; defense-in-depth at click time).
- **R-05:** Show all when pool < 5 (no padding).
- **R-06:** Use `random.sample()` for distinct picks within each pool.

#### Integration with existing Phase 64 sibling line
- **I-01:** `_sibling_label` and `_refresh_siblings()` are not modified structurally. Phase 67 calls `find_aa_siblings(...)` independently for the exclusion set.
- **I-02:** Click handling — recommendation is new signal `similar_activated = Signal(object)` for traceability and decoupling. Reuse of `sibling_activated` is acceptable but not preferred. **Locked: object payload (Station), not int id.**
- **I-03:** Href payload format is integer-only. Same security properties as `sibling://{id}`. Use `similar://{id}` if new signal; reuse `sibling://{id}` if signal reused.

#### Click action wiring
- **C-01:** MainWindow handler `_on_similar_activated(Station)` delegates to `self._on_station_activated(station)` for uniform side-effect set.
- **C-02:** No dirty-state confirmation, no failover machinery, no preview/hover.

#### Hamburger menu integration
- **M-01:** New QAction connected via bound method (QA-05) to `_on_show_similar_toggled(bool)` slot which (1) persists to SQLite, (2) calls `self.now_playing.set_similar_visible(bool)`.
- **M-02:** On `MainWindow.__init__`, after constructing the action, set its initial checked state from `Repo.get_setting('show_similar_stations', '0') == '1'` and pass the same value to `set_similar_visible(...)`.

### Claude's Discretion

- **Exact section/sub-section header wording** — "Similar Stations" / "Same provider:" / "Same tag:" recommended; planner can refine. Two-section structure (D-02) is locked.
- **Renderer choice (D-03)** — single `QLabel` with `<br>`-separated `<a>` links vs `QVBoxLayout` of clickable rows. Both meet the contract. Reusing `render_sibling_html`-style with thin wrapper acceptable.
- **Signal name (I-02)** — `similar_activated` recommended; reuse of `sibling_activated` (with discriminator on href prefix) acceptable.
- **Where Refresh icon sits** — right edge of section header recommended; left/right of collapse arrow is planner judgment. No keyboard shortcut for v1.
- **Where the "Similar Stations" container widget lives in the layout** — inside the existing center column (after controls) is locked; whether it's a `QGroupBox`, custom `QWidget` with styled border, or plain `QVBoxLayout` block is planner's call.
- **Sample ordering within rendered list** — random order vs alphabetical; alphabetical recommended for predictability.

### Deferred Ideas (OUT OF SCOPE)

- Surfacing on additional surfaces (station-list right-click menu, hamburger menu mini-list, mini-player, EditStationDialog).
- Smarter ranking — favorites boost, recently-played weighting, listener count, tag-overlap-count ranking.
- Live-update on library mutations (`station_saved` / `station_deleted` / discovery-import-complete subscriptions).
- Per-section refresh icons (currently single ↻ refreshes both).
- Keyboard shortcut for Refresh.
- "Why suggested" tooltip on Same tag rows.
- Visual context beyond name + provider (logos, ICY title preview, listener count, tag chips).
- Smarter random — deterministic seed per session, anti-recency.
- Per-pool size override.
- Same-tag-as-primary-tag-only pool variant.

</user_constraints>

## Project Constraints (from CLAUDE.md)

`./CLAUDE.md` only routes to skills (`Skill("spike-findings-musicstreamer")` for Windows packaging knowledge — not relevant to Phase 67). The file delegates project conventions to `.planning/codebase/CONVENTIONS.md` and the project memory file `~/.claude/projects/-home-kcreasey-OneDrive-Projects-MusicStreamer/memory/MEMORY.md`.

**Active project-memory directives:**

| # | Directive | Application to Phase 67 |
|---|-----------|------------------------|
| 1 | **Linux Wayland deployment, DPR=1.0** — never X11; HiDPI/fractional-scaling findings downgrade from CRITICAL to WARNING in any UI audit. Prefer Wayland-native diagnostics over xprop. | Any UI audit on the new vertical 5+5 row stack treats fractional-scaling overflow as WARNING, not CRITICAL. Test on Wayland DPR=1.0 only. |
| 2 | **`gsd-sdk` wrapper at `~/.local/bin/gsd-sdk`** | Used by orchestrator only; does not affect implementation. |
| 3 | **QNAP Gitea → GitHub mirror** — treat QNAP pushes as effectively public. | Affects commit hygiene only. |
| 4 | **2026-05-04 cookie-leak scrub history** | No bearing on Phase 67. |

**From `.planning/codebase/CONVENTIONS.md` (project conventions, applies during planning):**

| # | Directive |
|---|-----------|
| 1 | snake_case + type hints throughout; no formatter, no linter on save. |
| 2 | Bound-method signal connections (QA-05) — no self-capturing lambdas. Applies to: new `linkActivated` connections on the renderer label(s), new `similar_activated` connection in MainWindow, new `triggered` connection on master-toggle QAction, section-header click handler, Refresh button click handler. |
| 3 | T-39-01 PlainText convention — deviated for any new `<a>`-rendering label. Use `html.escape` mitigation on all user-controlled text. |
| 4 | Dataclass models (`Station`, `StationStream`) live in `musicstreamer/models.py`. No schema change in Phase 67. |
| 5 | Tests in `tests/` parallel to `musicstreamer/`; pytest-qt `qtbot` for widget tests; Qt platform `offscreen` set in `tests/conftest.py:13`. |

<phase_requirements>
## Phase Requirements

Phase 67 has **no formal requirement IDs** in `.planning/REQUIREMENTS.md` — it is a v2.1 rolling-polish discoverability feature added during the milestone (per CONTEXT.md `<canonical_refs>`). The phase's authoritative scope is CONTEXT.md itself, captured verbatim in `<user_constraints>` above. Below is the implicit decision-traceability mapping the planner should use to write success criteria:

| ID (synthetic) | Behavior | Research Support |
|---|---|---|
| SIM-01 | Master toggle in hamburger persists to SQLite key `show_similar_stations`, default `'0'` | M-01/M-02 + Phase 47.1 `_act_stats` precedent (`main_window.py:205-210, 338`) |
| SIM-02 | Master toggle ON shows section container; OFF hides container with zero vertical space | S-02 + Phase 64 D-05 `setVisible(False)` precedent (`now_playing_panel.py:265-271`) |
| SIM-03 | Section header collapse state persisted to SQLite key `similar_stations_collapsed`, default `'0'` (expanded) on first enable | S-03/S-03a |
| SIM-04 | "Same provider" sub-section pool: stations with same `provider_id`, excluding self id and AA-sibling ids; up to 5 random | T-01..T-04 + R-05/R-06 |
| SIM-05 | "Same tag" sub-section pool: stations sharing ≥1 normalized tag, excluding self id, AA-sibling ids, and no-tag candidates; up to 5 random | T-01..T-04 + R-05/R-06 + `filter_utils.normalize_tags` |
| SIM-06 | Cache: keyed by station id, in-memory; rolled on first bind, reused on revisit | R-01/R-02 |
| SIM-07 | Refresh button re-rolls both pools for current station id | R-03 |
| SIM-08 | Click on a similar-station link switches active playback (delegates to `_on_station_activated`) | C-01 + Phase 64 `_on_sibling_activated` precedent (`main_window.py:430-441`) |
| SIM-09 | "Same provider" rows render station name only; "Same tag" rows render `{Name} ({Provider})` | D-04 |
| SIM-10 | Hidden-when-empty: each sub-section reclaims zero vertical space when its pool is empty | D-02 + Phase 64 D-05 |
| SIM-11 | Defense-in-depth at click time: `repo.get_station` wrap + None-check; emits no signal on failure | Phase 64 dual-shape pattern (`now_playing_panel.py:941-955`) |
| SIM-12 | Phase 64 line untouched: `_sibling_label` / `_refresh_siblings` not structurally modified | I-01 |

</phase_requirements>

## Standard Stack

### Core (no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | 6.11.0 | QWidget / QLabel / QPushButton / QToolButton / QVBoxLayout / Signal | Already the canonical UI framework; verified installed via `uv run python -c "import PySide6; PySide6.__version__"` returning 6.11.0 [VERIFIED: live invocation 2026-05-09] |
| Python `random` (stdlib) | 3.10+ | `random.sample(population, k=...)` for distinct-picks per pool; `random.Random(seed)` for testable injection | Stdlib only; no project-wide `import random` exists today (verified by grep returning empty) — Phase 67 introduces the first usage. [VERIFIED: `grep -rn "import random\|from random\|random\." musicstreamer/ tests/` returns no hits] |
| Python `html` (stdlib) | 3.10+ | `html.escape(name, quote=True)` on user-controlled station names interpolated into RichText | Already used in `url_helpers.py:10, 260` for `render_sibling_html`; same pattern. [VERIFIED: file read] |

### Supporting (existing project assets — reused unchanged)

| Library/Module | Purpose | When to Use |
|----------------|---------|-------------|
| `musicstreamer.filter_utils.normalize_tags` | Canonical tag parser — comma/bullet split, casefold, dedup | Pool intersection check in the Same-tag pool derivation (T-02) |
| `musicstreamer.url_helpers.find_aa_siblings` | AA cross-network sibling detection | Read-only call to derive the AA-sibling exclusion id-set (T-04b) |
| `musicstreamer.url_helpers.render_sibling_html` | Existing free-function HTML renderer for `<a href="sibling://{id}">` links | **Reference shape only** — Phase 67 needs a different per-row format, so introduce a sibling free function `render_similar_html` that mirrors the same security envelope (`html.escape`, integer-only href) |
| `musicstreamer.repo.Repo.list_stations` | Library snapshot for pool derivation | One call per refresh (per `_refresh_similar_stations` invocation) |
| `musicstreamer.repo.Repo.get_station(id)` | Click-time lookup for sibling station | Same defense-in-depth pattern as Phase 64 — wrap in `try/except Exception` + `is None` check |
| `musicstreamer.repo.Repo.get_setting(key, default) -> str` | Read both new persisted keys | `'0'` default for both keys |
| `musicstreamer.repo.Repo.set_setting(key, value)` | Write both new persisted keys | Called from MainWindow toggle slot + panel collapse-header click |

### Alternatives Considered

| Instead of | Could Use | Tradeoff / Why Rejected |
|------------|-----------|-------------------------|
| `random.sample(pool, k=min(5, len(pool)))` | `random.choices(pool, k=5)` | `choices()` allows replacement (duplicates within a pool), violates "5 distinct stations" implied by R-05 ("Show all when pool < 5"). |
| Stdlib `random` with module-level state | `secrets.SystemRandom()` | This is a UI discovery feature, not a security context — `random.sample()` is the canonical, fastest, deterministic-via-seed choice. `secrets` is needed for cryptographic randomness only. |
| In-class `_pick_similar_stations` private method | Module-level pure function `pick_similar_stations` in `url_helpers.py` | Module-level pure function is testable without `qtbot`, mirrors `find_aa_siblings` placement (next to it), and lets the bulk of phase-67 logic be covered by a dedicated `tests/test_pick_similar_stations.py` with no Qt fixture. **Recommended.** |
| `QGroupBox` with `setCheckable(True)` for the collapsible header | Phase 67 D-02 / S-03 wants a custom `▾`/`▸` arrow header | `QGroupBox.setCheckable(True)` renders a checkbox visual prefix on the title — not the visual idiom requested. The codebase already has the `_toggle_filter_strip` flat-button + arrow-glyph pattern at `station_list_panel.py:191-198, 516-519` — Phase 67 should reuse it. |
| Third-party `QCollapsibleSection` widget | Hand-rolled `QPushButton`-with-arrow header + `QWidget` body container | This codebase rolls its own collapsible widgets (no third-party Qt widget libraries in deps). [VERIFIED: `pyproject.toml` shows only PySide6, yt-dlp, streamlink, platformdirs, chardet, optional winrt-* on Windows] |
| `QGroupBox` for the "Similar Stations" container | Plain `QWidget` with internal `QVBoxLayout` | `QGroupBox` adds a frame and title-bar that may visually compete with the collapsible header. Plain `QWidget` matches the pattern of every other section in `NowPlayingPanel.__init__` (`_stats_widget`, `_gbs_playlist_widget`). |

**Installation:** No new dependencies required. The `random` and `html` stdlib modules are always available on Python 3.10+.

**Version verification:** `PySide6 6.11.0 / Qt 6.11.0` confirmed via `uv run python -c "import PySide6; from PySide6.QtCore import qVersion; print(PySide6.__version__, qVersion())"` on 2026-05-09. [VERIFIED] No need to upgrade for Phase 67 — `QLabel` / `QToolButton` / `linkActivated` / `Qt.RichText` are all stable Qt 6 APIs unchanged since 6.0.

## Architecture Patterns

### System Architecture Diagram

The Phase 67 sub-system is a strict pure-helper + Qt-widget split, parallel to the Phase 64 sub-system:

```text
                 ┌────────────────────────────────────────────────────┐
                 │  MainWindow (QMainWindow)                          │
                 │                                                    │
                 │  ┌─────────────────────────────┐                   │
                 │  │ Hamburger Menu              │                   │
                 │  │  - "Theme" (Phase 66)       │                   │
                 │  │  - "Show similar stations"  │ <─── new QAction  │
                 │  │     QAction (checkable)     │     (M-01)        │
                 │  │  - "Accent Color"           │                   │
                 │  │  - … rest unchanged …       │                   │
                 │  └──────────┬──────────────────┘                   │
                 │             │                                      │
                 │             │ triggered(bool)                      │
                 │             ▼                                      │
                 │  ┌─────────────────────────────┐                   │
                 │  │ _on_show_similar_toggled    │                   │
                 │  │  1. repo.set_setting(...)   │                   │
                 │  │  2. now_playing             │                   │
                 │  │      .set_similar_visible() │                   │
                 │  └─────────────────────────────┘                   │
                 │                                                    │
                 │  ┌─────────────────────────────┐                   │
                 │  │ _on_similar_activated       │ <── connected     │
                 │  │   (Station) -> delegates    │     in __init__   │
                 │  │   to _on_station_activated  │                   │
                 │  └────────┬────────────────────┘                   │
                 │           │ similar_activated(Station)             │
                 │           │                                        │
                 └───────────┼────────────────────────────────────────┘
                             │
                             │ Qt signal
                             │
                 ┌───────────┴────────────────────────────────────────┐
                 │  NowPlayingPanel (QWidget)                         │
                 │                                                    │
                 │   center: QVBoxLayout                              │
                 │     ├── name_provider_label   (existing)           │
                 │     ├── _sibling_label        (Phase 64, untouched)│
                 │     ├── icy_label             (existing)           │
                 │     ├── elapsed_label         (existing)           │
                 │     ├── controls (QHBoxLayout) (existing)          │
                 │     ├── _stats_widget         (Phase 47.1)         │
                 │     ├── _gbs_playlist_widget  (Phase 60)           │
                 │     ├── _gbs_vote_row         (Phase 60)           │
                 │     │                                              │
                 │     └── _similar_container    <── NEW (D-01)       │
                 │           ├── _similar_header_row (collapse btn +  │
                 │           │     refresh btn)                       │
                 │           └── _similar_body                        │
                 │                ├── _same_provider_label_caption    │
                 │                ├── _same_provider_links_label      │
                 │                │   (RichText QLabel,               │
                 │                │    <br>-sep <a> links)            │
                 │                ├── _same_tag_label_caption         │
                 │                └── _same_tag_links_label           │
                 │                    (RichText QLabel,               │
                 │                     <br>-sep <a> links)            │
                 │                                                    │
                 │   bind_station(station):                           │
                 │     …                                              │
                 │     self._refresh_siblings()       (Phase 64)      │
                 │     self._refresh_similar_stations() <── NEW R-02  │
                 │     …                                              │
                 │                                                    │
                 │   _refresh_similar_stations():                     │
                 │     if cached for self._station.id: reuse          │
                 │     else: derive pools, sample, cache, render      │
                 │                                                    │
                 │   _on_similar_link_activated(href):                │
                 │     parse "similar://{id}", lookup, emit           │
                 │                                                    │
                 │   _on_refresh_similar_clicked():                   │
                 │     pop cache for self._station.id, re-derive      │
                 │                                                    │
                 │   _on_similar_collapse_clicked():                  │
                 │     toggle _similar_body.setVisible, persist       │
                 │                                                    │
                 │   set_similar_visible(visible: bool):              │
                 │     self._similar_container.setVisible(visible)    │
                 │                                                    │
                 │   _similar_cache:                                  │
                 │     dict[int, tuple[list[Station],list[Station]]]  │
                 └────────────────────────────────────────────────────┘
                             │
                             │ list_stations() / get_station(id)      │
                             ▼
                 ┌────────────────────────────────────────────────────┐
                 │  Repo (existing)                                   │
                 │   list_stations() -> list[Station]                 │
                 │   get_station(id) -> Station (raises ValueError)   │
                 │   get_setting(k,default) / set_setting(k,v)        │
                 └────────────────────────────────────────────────────┘
                             ▲
                             │
                 ┌────────────────────────────────────────────────────┐
                 │  Pure helpers in musicstreamer/url_helpers.py      │
                 │                                                    │
                 │   find_aa_siblings(...)            (Phase 51, R-O) │
                 │   render_sibling_html(...)         (Phase 64, R-O) │
                 │                                                    │
                 │   pick_similar_stations(            <── NEW        │
                 │     stations, current,                             │
                 │     *, sample_size=5,                              │
                 │     rng: random.Random | None=None                 │
                 │   ) -> tuple[list[Station], list[Station]]         │
                 │                                                    │
                 │   render_similar_html(             <── NEW         │
                 │     stations, *, show_provider: bool,              │
                 │     href_prefix: str = "similar://",               │
                 │   ) -> str                                         │
                 └────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
musicstreamer/
├── url_helpers.py                  # +pick_similar_stations, +render_similar_html
├── filter_utils.py                 # untouched (normalize_tags reused)
├── repo.py                         # untouched (settings table reused)
├── models.py                       # untouched
└── ui_qt/
    ├── now_playing_panel.py        # +Similar Stations container, +signal,
    │                               #  +_refresh_similar_stations,
    │                               #  +_on_similar_link_activated,
    │                               #  +_on_refresh_similar_clicked,
    │                               #  +_on_similar_collapse_clicked,
    │                               #  +set_similar_visible,
    │                               #  +_similar_cache attribute
    └── main_window.py              # +"Show similar stations" QAction (M-01),
                                    #  +_on_show_similar_toggled slot,
                                    #  +_on_similar_activated slot,
                                    #  +similar_activated.connect(...)

tests/
├── test_pick_similar_stations.py   # NEW — pure helper tests, mirrors
│                                   #  test_aa_siblings.py shape, no qtbot
├── test_now_playing_panel.py       # +tests for similar-section visibility,
│                                   #  cache lifetime, click → signal,
│                                   #  collapse persistence, refresh re-roll
└── test_main_window_integration.py # +tests for QAction → repo persistence
                                    #  + panel.set_similar_visible push;
                                    #  +similar_activated → playback switch
                                    #  (mirrors line 1115 sibling pattern)
```

### Pattern 1: Checkable QAction in hamburger drives panel `set_X_visible(bool)` (Phase 47.1 verbatim)

**What:** Hamburger-menu QAction with `setCheckable(True)`; bound-method connect to `MainWindow._on_X_toggled(bool)` slot which (1) persists to SQLite via `Repo.set_setting`, (2) calls `panel.set_X_visible(bool)`. After construction, MainWindow `__init__` reads the setting once and pushes initial state into both action AND panel via the same `set_X_visible` call (single source of truth — WR-02 invariant).

**When to use:** Master toggle for any panel feature that is opt-in across launches.

**Example:** [VERIFIED: `musicstreamer/ui_qt/main_window.py:205-210, 338, 539-542`]
```python
# Construction (main_window.py:205-210)
self._act_stats = self._menu.addAction("Stats for Nerds")
self._act_stats.setCheckable(True)
self._act_stats.setChecked(
    self._repo.get_setting("show_stats_for_nerds", "0") == "1"
)
self._act_stats.toggled.connect(self._on_stats_toggled)

# Initial-push wiring (main_window.py:338) — runs AFTER panel is constructed
self.now_playing.set_stats_visible(self._act_stats.isChecked())

# Slot (main_window.py:539-542)
def _on_stats_toggled(self, checked: bool) -> None:
    """Persist the Stats for Nerds toggle and update the panel (D-04, D-07). Phase 47.1."""
    self._repo.set_setting("show_stats_for_nerds", "1" if checked else "0")
    self.now_playing.set_stats_visible(checked)

# Panel-side public method (now_playing_panel.py:645-647)
def set_stats_visible(self, visible: bool) -> None:
    """Toggle the stats-for-nerds wrapper visibility (D-07). Phase 47.1."""
    self._stats_widget.setVisible(bool(visible))
```

**Phase 67 application:**
- New action: `self._act_show_similar = self._menu.addAction("Show similar stations")`, `setCheckable(True)`, place adjacent to Phase 66 Theme picker (`main_window.py:188-190`). Reads `self._repo.get_setting("show_similar_stations", "0") == "1"` for initial check state.
- Wiring: `self._act_show_similar.toggled.connect(self._on_show_similar_toggled)`.
- Initial push (after panel construction at line 338-area): `self.now_playing.set_similar_visible(self._act_show_similar.isChecked())`.
- Slot: `_on_show_similar_toggled(self, checked: bool)` writes setting and calls `set_similar_visible`.
- Panel public method: `set_similar_visible(self, visible: bool)` toggles `self._similar_container.setVisible(visible)`.

### Pattern 2: Phase 64 sibling click chain (verbatim shape)

**What:** Panel emits a typed Qt Signal carrying a `Station` payload when a sibling link is clicked. MainWindow connects via bound method to a one-line delegator that calls `_on_station_activated(station)` so all "user picked a station" side-effects (`bind_station`, `player.play`, `update_last_played`, `refresh_recent`, `Connecting…` toast, media-keys publish + state) fire identically.

**When to use:** Any new panel-level "switch playback to this station" affordance.

**Example:** [VERIFIED: `musicstreamer/ui_qt/now_playing_panel.py:200, 941-975` + `main_window.py:324, 430-441`]
```python
# Panel signal declaration (now_playing_panel.py:200)
sibling_activated = Signal(object)  # payload: resolved sibling Station

# Panel click handler (now_playing_panel.py:941-975)
def _on_sibling_link_activated(self, href: str) -> None:
    prefix = "sibling://"
    if not href.startswith(prefix):
        return
    try:
        sibling_id = int(href[len(prefix):])
    except ValueError:
        return
    if self._station is None or self._station.id == sibling_id:
        return
    try:
        sibling = self._repo.get_station(sibling_id)
    except Exception:
        return
    if sibling is None:
        return
    self.sibling_activated.emit(sibling)

# MainWindow wiring (main_window.py:324)
self.now_playing.sibling_activated.connect(self._on_sibling_activated)

# MainWindow slot (main_window.py:430-441)
def _on_sibling_activated(self, station: Station) -> None:
    """Phase 64 / D-02: user clicked an 'Also on:' link in NowPlayingPanel.
    Delegate to _on_station_activated so the canonical 'user picked a
    station' side-effect block ... fires identically regardless of activation
    source (station list vs sibling click)."""
    self._on_station_activated(station)
```

**Phase 67 application:**
- Panel signal: `similar_activated = Signal(object)` declared adjacent to existing `sibling_activated` at line 200.
- Panel click handler: `_on_similar_link_activated(self, href: str)` — same shape as above, but parses `"similar://{id}"` prefix.
- MainWindow wiring: `self.now_playing.similar_activated.connect(self._on_similar_activated)` adjacent to line 324.
- MainWindow slot: `_on_similar_activated(self, station: Station)` — one-line `self._on_station_activated(station)`. Place adjacent to `_on_sibling_activated` at line 430-441.

### Pattern 3: Pure helper colocated with `find_aa_siblings` (Phase 51 / 64 placement)

**What:** Pool derivation + random sampling logic lives as a module-level pure function in `musicstreamer/url_helpers.py`, next to `find_aa_siblings` and `render_sibling_html`. No Qt, no DB, no logging — just dataclass-in / sample-out.

**When to use:** Any non-trivial filtering/sampling/scoring logic that reads `Station` objects and returns lists of `Station` objects. Keeps the Qt panel layer thin and the bulk of behavior unit-testable without a `qtbot` fixture.

**Recommended signature:**
```python
import random
from musicstreamer.models import Station
from musicstreamer.filter_utils import normalize_tags
from musicstreamer.url_helpers import find_aa_siblings


def pick_similar_stations(
    stations: list[Station],
    current_station: Station,
    *,
    sample_size: int = 5,
    rng: random.Random | None = None,
) -> tuple[list[Station], list[Station]]:
    """Return (same_provider_sample, same_tag_sample) for the currently
    playing station, both up to sample_size stations long.

    Pure function — no Qt, no DB access, no logging. Mirrors find_aa_siblings
    placement convention (musicstreamer/url_helpers.py).

    Sampling:
      - Each pool is sampled independently via random.sample (distinct picks).
      - Pools < sample_size return all candidates (no padding).
      - Both pools may share stations (T-03: cross-pool dedup is intentionally
        not performed).

    Pool exclusions (both pools, T-04):
      - (a) self id
      - (b) AA-sibling ids returned by find_aa_siblings(...)
      - (c) Same-tag pool only: candidates with empty normalize_tags(tags)
      - (d) Same-provider pool only: candidates with provider_id is None
            when current_station.provider_id is set

    rng: inject a seeded random.Random for deterministic tests; defaults to
    the module-global random instance for production.
    """
    rng = rng or random
    # ... (implementation mirrors find_aa_siblings shape)
```

**Why this matters:** Tests can pass `rng=random.Random(42)` for byte-exact reproducibility without monkeypatching module globals. The same fixture works in `tests/test_pick_similar_stations.py` (pure-helper tests) and in `tests/test_now_playing_panel.py` if the panel grows a `_pick_similar` seam (recommended: panel calls the helper directly with `rng=None`, tests on the helper own determinism).

### Pattern 4: Collapsible flat-button header with arrow glyph (`station_list_panel.py` verbatim)

**What:** A `QPushButton` styled flat with a left-aligned text containing the section title prefixed by `▼ ` (expanded) / `▶ ` (collapsed). Click toggles the body container's `setVisible(...)` and re-stamps the button text with the new glyph.

**When to use:** Any in-panel collapsible section. The codebase has exactly one of these today (the Filters strip in StationListPanel); Phase 67's section header is the second.

**Example:** [VERIFIED: `musicstreamer/ui_qt/station_list_panel.py:191-198, 516-519`]
```python
# Header construction (station_list_panel.py:191-198)
self._filter_toggle = QPushButton("▶ Filters", stations_page)  # ▶ Filters
self._filter_toggle.setFlat(True)
self._filter_toggle.setFixedHeight(24)
self._filter_toggle.setStyleSheet(
    "QPushButton { text-align: left; padding-left: 16px; color: palette(highlight); }"
)
self._filter_toggle.clicked.connect(self._toggle_filter_strip)
sp_layout.addWidget(self._filter_toggle)

# Initial collapsed (line 266-267)
self._filter_strip.setVisible(False)
sp_layout.addWidget(self._filter_strip)

# Toggle slot (station_list_panel.py:516-519)
def _toggle_filter_strip(self) -> None:
    visible = not self._filter_strip.isVisible()
    self._filter_strip.setVisible(visible)
    self._filter_toggle.setText(("▼ Filters" if visible else "▶ Filters"))
```

**Phase 67 application:**
- Header row is a `QHBoxLayout` containing: collapse button (flat `QPushButton` with `▼ ` / `▶ ` prefix on text "Similar Stations") + a stretch + a Refresh `QToolButton` (↻ icon).
- Collapse glyph difference from CONTEXT.md: CONTEXT specifies `▾`/`▸` (U+25BE / U+25B8 — small triangles). Either set works; the codebase precedent uses `▼`/`▶` (U+25BC / U+25B6 — full triangles). **Recommendation: use the CONTEXT.md-specified `▾`/`▸`** for visual softness in the now-playing context, but the planner can choose. Both are pure Unicode glyphs; neither requires icon resources.
- Persistence: collapse toggle slot also calls `self._repo.set_setting('similar_stations_collapsed', '1' if collapsed else '0')`.
- Initial state on `bind_station` first run for a station: read `self._repo.get_setting('similar_stations_collapsed', '0')` and set `_similar_body.setVisible(...)` + button glyph accordingly (only meaningful when master toggle is ON; if OFF, the whole container is hidden and collapse state is irrelevant until next ON).

### Pattern 5: Hidden-when-empty container with zero vertical reclamation

**What:** `QVBoxLayout` children call `setVisible(False)` when empty; PySide6 reclaims their vertical space automatically with no manual `setMaximumHeight(0)` or layout-stretching tricks.

**When to use:** Any panel section whose visibility is data-dependent.

**Example:** [VERIFIED: Phase 64 `_sibling_label` at `now_playing_panel.py:265-271, 911-915`]
```python
# Construction
self._sibling_label = QLabel("", self)
self._sibling_label.setVisible(False)  # default: hidden, zero vertical space
center.addWidget(self._sibling_label)

# Refresh path (line 911-915)
if self._station is None or not self._station.streams:
    self._sibling_label.setVisible(False)
    self._sibling_label.setText("")
    return
```

**Phase 67 application:**
- Each sub-section's links label (`_same_provider_links_label`, `_same_tag_links_label`) AND its caption label (`_same_provider_caption`, `_same_tag_caption`) are hidden together when their pool is empty (D-02). Recommendation: wrap each sub-section's caption + links label in a `QWidget` container (e.g., `_same_provider_subsection: QWidget`) and toggle visibility on the container — keeps the caption/links pair atomic and simplifies the hide-when-empty toggle.

### Anti-Patterns to Avoid

- **Self-capturing lambdas in signal connects.** QA-05 violation. The codebase enforces this explicitly at multiple test sites (e.g., `tests/test_main_window_integration.py:609-628` test_buffer_percent_bound_method_connect_no_lambda greps for the literal text `lambda` on connect lines).
- **Subscribing to `station_saved` / `station_deleted` / discovery-import-complete signals to invalidate the cache.** R-04 explicitly forbids this. The cache is stale-OK; click-time `repo.get_station` defense handles deleted-station case.
- **Calling `_refresh_similar_stations()` from anywhere except `bind_station()` and the Refresh button click handler.** D-04-style invariant — the only call sites are deterministic. Mirrors Phase 64 D-04 (`test_refresh_siblings_runs_once_per_bind_station_call` pins the equivalent for the Phase 64 helper).
- **`Qt.PlainText` on the new renderer label.** The label MUST be `Qt.RichText` (deviation from T-39-01) because it carries `<a>` links. Mitigation: `html.escape` on every Station.name interpolation in the new `render_similar_html` helper.
- **Using `random.choices(pool, k=5)` for within-pool sampling.** Allows replacement (duplicate stations within a pool). R-06 implies distinct picks; use `random.sample(pool, k=min(5, len(pool)))`.
- **Passing a `set` to `random.sample()`.** [VERIFIED: live invocation 2026-05-09] Python 3.11+ raises `TypeError: Population must be a sequence. For dicts or sets, use sorted(d).` Use `list(pool)` (the helper builds list pools naturally).
- **Mutating the cache from `station_saved` / discovery-complete handlers.** Out of scope per R-04. The only mutation sites are `bind_station` (insert if missing) and Refresh button (delete current id).
- **Reusing the `sibling://` href prefix when introducing a new `similar_activated` signal.** Causes signal-routing ambiguity. If `similar_activated` is new (recommended per I-02), use `similar://` href prefix exclusively for it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tag parsing (split on comma/bullet, casefold, dedup) | A new `_normalize_for_similar` function | `musicstreamer.filter_utils.normalize_tags(s)` | Already canonical (T-02 LOCK); used by station-list filter chips and matches_filter; reuse keeps the union-semantics behavior identical to user's filter chip experience. |
| AA-sibling detection for the exclusion set | A new in-house AA-aware filter | `musicstreamer.url_helpers.find_aa_siblings(stations, current_id, current_first_url)` | 12 tests in `tests/test_aa_siblings.py` already cover the edge cases (cross-network identity, prefix stripping, empty-streams guard); reusing inherits all of them automatically. |
| HTML escaping on station names interpolated into RichText | Manual replacement of `<>&"` | `html.escape(name, quote=True)` | Stdlib; already used in `url_helpers.render_sibling_html`; covers all 5 metacharacters (`< > & ' "`). [VERIFIED: read `url_helpers.py:260`] |
| Random distinct sampling | Implementing reservoir sampling | `random.sample(population, k=...)` (stdlib) | Stdlib's reservoir-sampling is C-implemented and correct; documented contract `Returns a new list containing elements from the population while leaving the original population unchanged` covers the exact need. [VERIFIED: `python3 -c "import random; help(random.sample)"`] Edge case: `k > len(pool)` raises `ValueError("Sample larger than population or is negative")` — phase code MUST clamp via `k=min(sample_size, len(pool))`. |
| Deterministic-test-injectable random source | Module-level seeding via `random.seed()` (mutates global state, leaks across tests) | `random.Random(seed)` instance passed via `rng` parameter | `random.Random(42).sample([1..5], k=3)` returns identical results across separate instances [VERIFIED: live invocation]; isolated per call, no global leak. |
| Settings persistence (master toggle + collapse state) | A new JSON file or new SQLite column | `Repo.get_setting(key, default) -> str` / `Repo.set_setting(key, value)` | Same SQLite settings table Phase 47.1 (`show_stats_for_nerds`), Phase 59 (`accent_color`), Phase 66 (`theme`, `theme_custom`), Phase 47.2 (`eq_enabled`) all use; zero schema migration; preserves Phase 42 export/import ZIP round-trip automatically (settings keys are part of the ZIP payload). |
| Click-time station lookup with crash protection | Bare `repo.get_station(id)` call | Wrapped in `try/except Exception:` + `is None` check (Phase 64 dual-shape pattern) | Production `Repo.get_station` raises `ValueError("Station not found")` on miss; some test doubles (`MainWindow.FakeRepo`) return `None` instead. Single try/except + None-check covers both shapes and satisfies the slots-never-raise contract. [VERIFIED: `repo.py:271`, `now_playing_panel.py:941-975`, `tests/test_main_window_integration.py:140-161`] |
| Collapsible section widget | A custom `QCollapsibleSection` class or a third-party Qt widget library | The `_toggle_filter_strip` flat-button + arrow-glyph idiom from `station_list_panel.py:191-198, 516-519` | Already shipped, already tested via UI behavior. No third-party dep, no custom QWidget subclass needed. |

**Key insight:** Phase 67 is **almost entirely composition** of patterns landed by Phases 47.1, 51, 59, 64, and the Phase 50 `refresh_recent` panel-method pattern. The single net-new piece is the pure-helper `pick_similar_stations(...)` plus a thin renderer; everything else is one-line additions adjacent to existing constructs.

## Runtime State Inventory

**Skipped — Phase 67 is a greenfield additive feature, not a rename/refactor/migration.** No existing data, service config, OS-registered state, secrets, or build artifacts are renamed or moved. The only persistence additions are two new SQLite settings keys (`show_similar_stations`, `similar_stations_collapsed`) which read default `'0'` for users who have never toggled the feature — no migration step is needed because `Repo.get_setting(key, default)` returns the default for missing keys (verified at `repo.py:348-352`).

## Common Pitfalls

### Pitfall 1: `random.sample` raises on `k > len(population)`
**What goes wrong:** Calling `random.sample([s1, s2, s3], k=5)` raises `ValueError: Sample larger than population or is negative`. [VERIFIED: live invocation 2026-05-09]
**Why it happens:** stdlib enforces no-replacement by default, so it can't return more elements than exist.
**How to avoid:** Always clamp via `k=min(sample_size, len(pool))`. R-05 explicitly says "show all when pool < 5", which this clamp implements.
**Warning signs:** ValueError in tests with small libraries.

### Pitfall 2: `random.sample` rejects sets as population in Python 3.11+
**What goes wrong:** `random.sample({s1, s2, s3, s4, s5}, k=2)` raises `TypeError: Population must be a sequence. For dicts or sets, use sorted(d).` [VERIFIED: live invocation]
**Why it happens:** Set iteration order has been deterministic enough to mislead callers; Python 3.11 made the deprecation hard.
**How to avoid:** Pool variables MUST be `list[Station]` (not `set[Station]`). The natural shape from a filtered comprehension is already a list — just don't convert it to a set during exclusion logic. Use a set ONLY for the exclusion-id lookup (e.g., `excluded_ids: set[int] = {current.id} | {s_id for _, s_id, _ in aa_siblings}`), and apply that set as a membership filter against the list pools.

### Pitfall 3: Stale cache references a deleted station
**What goes wrong:** User plays Drone Zone, sees the random sample, deletes "Pop Vibes" from the library, switches to Drone Zone again, sees Pop Vibes in the cached sample, clicks it. Without defense, `_repo.get_station(pop_vibes_id)` raises `ValueError`.
**Why it happens:** R-01/R-04 cache is in-memory and not invalidated on library mutations (intentional simplicity). The deleted station's id stays in the cache until the user clicks Refresh or the app restarts.
**How to avoid:** Phase 64 pattern at `now_playing_panel.py:941-975` — wrap `_repo.get_station(...)` in `try/except Exception:` + `is None` check. On failure, return silently from the click handler. The link is effectively dead but fails gracefully. **Test:** `test_similar_link_handler_no_op_when_repo_get_station_raises` (mirror Phase 64 test at `tests/test_now_playing_panel.py:870-882`).

### Pitfall 4: Master toggle and panel container desync
**What goes wrong:** User checks the QAction; the SQLite key is written; but the panel container stays hidden because nobody pushed the new state to the panel.
**Why it happens:** Two sources of truth — QAction state and panel widget visibility — without explicit linkage.
**How to avoid:** Phase 47.1 WR-02 pattern — `_on_show_similar_toggled(checked)` does BOTH: `repo.set_setting(...)` AND `self.now_playing.set_similar_visible(checked)`. AND, `MainWindow.__init__` does the same dual-write at startup using the QAction's initial-checked state derived from the persisted setting. **Lock:** structural test that asserts `_act_show_similar.isChecked() == now_playing._similar_container.isVisible()` after construction (mirrors `test_stats_toggle_persists_and_toggles_panel` at `tests/test_main_window_integration.py:587-606`).

### Pitfall 5: Collapse state is meaningless when master toggle is OFF
**What goes wrong:** User collapses the section; toggles master OFF; toggles master ON. Persisted state says "collapsed", but the user expects to see the section they just turned on.
**Why it happens:** Two orthogonal preferences — visibility AND collapse — interact non-orthogonally if the visible-but-collapsed state is unfriendly.
**How to avoid:** S-03a explicitly says "Toggling the master OFF then back ON should remember the prior `similar_stations_collapsed` value (no auto-reset)." Implementation: `set_similar_visible(True)` reads `similar_stations_collapsed` and applies it to the body container's visibility, leaving the collapse glyph correct. If the user wants the section visible, the collapse persistence is honored. **First-enable special case:** `similar_stations_collapsed` defaults to `'0'` (expanded) so the user immediately sees the contents on first turn-on — handled by the default arg to `Repo.get_setting('similar_stations_collapsed', '0')`.

### Pitfall 6: Cache populated by a stale `_station` reference
**What goes wrong:** User clicks station A → bind_station(A) starts → `_refresh_similar_stations()` reads `self._station.id` (=A) and starts deriving pools. Before derivation completes, user clicks station B → bind_station(B) → `_refresh_similar_stations()` runs again → first call's results land in cache under id A but reflect a stale snapshot.
**Why it happens:** `_refresh_similar_stations` is synchronous (not threaded), so this race is theoretical — but the same is technically true of any cross-station rebind in quick succession.
**How to avoid:** Because `_refresh_similar_stations` runs synchronously on the Qt main thread (just like `_refresh_siblings` at `now_playing_panel.py:897-939`), there is no actual race — `bind_station(A)` blocks until its slot returns before any subsequent `bind_station(B)` slot fires. **No mitigation needed**, but document the synchronous invariant in the helper docstring so a future "make this async to handle huge libraries" refactor sees the assumption.

### Pitfall 7: HTML escape forgotten on the provider name in "Same tag" rows
**What goes wrong:** D-04 says "Same tag" rows render `"{Name} ({Provider})"`. The Phase 64 renderer escapes only `Station.name`. Provider names from user-managed stations can also contain HTML metacharacters (e.g., a provider named `Best & Brightest`).
**Why it happens:** Phase 64's `render_sibling_html` only ever interpolates Station.name (network names come from the compile-time `NETWORKS` list and are safe). Phase 67's renderer adds a second user-controlled string into the HTML output.
**How to avoid:** In `render_similar_html`, escape BOTH name and provider: `f"{html.escape(s.name, quote=True)} ({html.escape(s.provider_name or '', quote=True)})"`. Add a test analogous to `test_render_sibling_html_html_escapes_station_name` (`tests/test_aa_siblings.py:203-211`) that asserts a malicious `provider_name="<script>"` is escaped. **Test:** `test_render_similar_html_escapes_provider_name`.

### Pitfall 8: `linkActivated` href format ambiguity if signals are reused
**What goes wrong:** Reusing the `sibling_activated` signal for both Phase 64 and Phase 67 would force the renderer to encode "which feature emitted me" into the href. Distinguishing `sibling://2` (Phase 64 AA) from `sibling://2` (Phase 67 same-tag) is impossible.
**Why it happens:** I-02 leaves the choice open between new signal vs reuse.
**How to avoid:** Pick the new-signal path (CONTEXT.md recommendation). New signal `similar_activated` + new href prefix `similar://` keep the two surfaces fully decoupled. Even if the same `Station` could appear in both surfaces theoretically (Phase 67 T-04b excludes Phase 64 ids, so this is moot for the resolved set), distinct signals + distinct prefixes make the click chain self-documenting and let each surface's tests assert independence cleanly.

### Pitfall 9: Performance — `repo.list_stations()` called per refresh
**What goes wrong:** Library of 200 stations; user repeatedly clicks Refresh; each click runs the full `list_stations()` → pool filter → sample pipeline. Could be perceived as slow.
**Why it happens:** Defensive single-source-of-truth design — `list_stations()` always returns the freshest snapshot.
**How to avoid:** Project size guarantee from `.planning/PROJECT.md` is "personal library of 50–200 stations", and `Repo.list_stations()` does one `SELECT s.*, p.name LEFT JOIN providers ORDER BY` followed by per-station `list_streams(id)` calls (verified at `repo.py:225-251`). For 200 stations that's 1 + 200 SQL queries — sub-millisecond on local SQLite. No optimization needed for v1. If profiling later shows the per-station `list_streams` to be a bottleneck (e.g., user grows library to 1000+), introduce a `list_stations_with_streams()` method that uses a single JOIN — but that's deferred. **Lock:** include a sampling-perf test that constructs a 500-station synthetic library and asserts `pick_similar_stations(...)` returns in < 50ms (loose budget).

### Pitfall 10: Wayland fractional scaling on the vertical 5+5 row stack
**What goes wrong:** On HiDPI / fractional-scaling displays, vertical text rendering with `<br>` separators in a `QLabel` can produce uneven row spacing, glyph clipping, or scroll-position drift.
**Why it happens:** Qt 6 RichText has well-known cross-DPI rendering quirks; the codebase has a documented WARNING posture per project-memory.
**How to avoid:** Per the project-memory directive (Linux Wayland deployment, DPR=1.0), this is a WARNING-level concern, not CRITICAL. Test on Wayland DPR=1.0; do not block on HiDPI. If alignment issues are observed during UAT, the per-row `QVBoxLayout` of clickable widgets (D-03 option b) is a fallback path with cleaner row-spacing control. **Recommendation: ship D-03 option (a) — single QLabel with `<br>`-separated `<a>` links — and if Wayland UAT shows uneven spacing, Plan 04 falls back to option (b).**

### Pitfall 11: Bound station may have empty `streams` (defensive against test doubles)
**What goes wrong:** `find_aa_siblings(stations, current.id, current.streams[0].url)` indexes `[0]` into an empty list → `IndexError`.
**Why it happens:** Production `Repo.list_stations()` always populates `streams` (verified at `repo.py:248`), but test doubles (e.g., `_FakeStation` in conftest at line 102-115) construct stations with `streams=[]` for non-AA-related tests.
**How to avoid:** Phase 64 already handles this at `now_playing_panel.py:911-915` with `if self._station is None or not self._station.streams:` early-return + hide. Phase 67 must do the same — check `not self._station.streams` before reading `streams[0].url` for the AA-exclusion-set call. **Note:** the AA exclusion call is OPTIONAL for the Same-tag pool (the pool can be derived even without AA exclusion if AA detection fails). Implementation: if `not self._station.streams`, treat the AA-sibling exclusion set as empty and continue with same-provider + same-tag pool derivation. This is friendlier than hiding the entire similar-stations section just because the bound station happens to have no streams.

## Code Examples

Verified patterns from official sources. All examples below have a corresponding production code reference.

### Example 1: Pure helper signature for pool derivation + sampling

```python
# musicstreamer/url_helpers.py — additive
import random
from musicstreamer.models import Station
from musicstreamer.filter_utils import normalize_tags
# find_aa_siblings is already in this module — no import needed

def pick_similar_stations(
    stations: list[Station],
    current_station: Station,
    *,
    sample_size: int = 5,
    rng: random.Random | None = None,
) -> tuple[list[Station], list[Station]]:
    """Phase 67 / T-01..T-04, R-05, R-06: derive and sample two pools.

    Returns (same_provider_sample, same_tag_sample). Both lists are up to
    sample_size long; pools < sample_size return all candidates (no padding).

    Pool exclusions (both pools): self id, ids of AA siblings of current_station
    (call find_aa_siblings to compute), no-tag candidates (Same tag pool only),
    no-provider candidates (Same provider pool only — when current's provider
    is set).

    Pure function — no Qt, no DB, no logging. Mirrors find_aa_siblings.
    rng: pass random.Random(seed) for deterministic tests.
    """
    rng = rng or random
    excluded_ids: set[int] = {current_station.id}
    # T-04b: exclude AA siblings already shown in Phase 64's "Also on:" line.
    if current_station.streams:
        aa = find_aa_siblings(
            stations,
            current_station_id=current_station.id,
            current_first_url=current_station.streams[0].url,
        )
        excluded_ids.update(sid for _, sid, _ in aa)

    # Same provider pool.
    same_provider_pool: list[Station] = []
    if current_station.provider_id is not None:
        for s in stations:
            if s.id in excluded_ids:
                continue
            if s.provider_id is None:  # T-04d
                continue
            if s.provider_id == current_station.provider_id:
                same_provider_pool.append(s)

    # Same tag pool.
    current_tags = set(t.casefold() for t in normalize_tags(current_station.tags))
    same_tag_pool: list[Station] = []
    if current_tags:
        for s in stations:
            if s.id in excluded_ids:
                continue
            cand_tags = set(t.casefold() for t in normalize_tags(s.tags))
            if not cand_tags:  # T-04c
                continue
            if current_tags & cand_tags:  # T-01: union semantics
                same_tag_pool.append(s)

    # Sample (R-05/R-06).
    same_provider_sample = rng.sample(
        same_provider_pool, k=min(sample_size, len(same_provider_pool))
    )
    same_tag_sample = rng.sample(
        same_tag_pool, k=min(sample_size, len(same_tag_pool))
    )
    return same_provider_sample, same_tag_sample
```

### Example 2: Renderer (mirrors `render_sibling_html` security envelope)

```python
# musicstreamer/url_helpers.py — additive
import html
from musicstreamer.models import Station


def render_similar_html(
    stations: list[Station],
    *,
    show_provider: bool,
    href_prefix: str = "similar://",
) -> str:
    """Phase 67 / D-03 / D-04: render a vertical link list with one <a> per row.

    show_provider=False (Same provider section) -> rows render '{Name}'.
    show_provider=True  (Same tag section)      -> rows render '{Name} ({Provider})'.

    Security: Station.name AND Station.provider_name are user-controlled and
    pass through html.escape(..., quote=True). The href payload is
    integer-only ({prefix}{id}) so it cannot carry injectable content.
    """
    parts: list[str] = []
    for s in stations:
        safe_name = html.escape(s.name, quote=True)
        if show_provider:
            safe_prov = html.escape(s.provider_name or "", quote=True)
            link_text = f"{safe_name} ({safe_prov})"
        else:
            link_text = safe_name
        parts.append(f'<a href="{href_prefix}{s.id}">{link_text}</a>')
    return "<br>".join(parts)
```

### Example 3: Panel-side wiring (sketch — reference shape only)

```python
# musicstreamer/ui_qt/now_playing_panel.py — additive in __init__ + new methods

# Signal declaration (adjacent to sibling_activated at line 200)
similar_activated = Signal(object)  # payload: resolved Station

# Container construction (after controls block in center column)
self._similar_container = QWidget(self)
sc_layout = QVBoxLayout(self._similar_container)
sc_layout.setContentsMargins(0, 0, 0, 0)
sc_layout.setSpacing(4)

# Header row: collapse btn + stretch + refresh btn
header_row = QHBoxLayout()
self._similar_collapse_btn = QPushButton("▾ Similar Stations", self)  # ▾
self._similar_collapse_btn.setFlat(True)
self._similar_collapse_btn.setStyleSheet(
    "QPushButton { text-align: left; padding-left: 0px; }"
)
self._similar_collapse_btn.clicked.connect(self._on_similar_collapse_clicked)
header_row.addWidget(self._similar_collapse_btn)
header_row.addStretch(1)
self._similar_refresh_btn = QToolButton(self)
self._similar_refresh_btn.setText("↻")  # ↻
self._similar_refresh_btn.setToolTip("Refresh similar stations")
self._similar_refresh_btn.setFixedSize(24, 24)
self._similar_refresh_btn.clicked.connect(self._on_refresh_similar_clicked)
header_row.addWidget(self._similar_refresh_btn)
sc_layout.addLayout(header_row)

# Body container (collapsible)
self._similar_body = QWidget(self._similar_container)
body_layout = QVBoxLayout(self._similar_body)
body_layout.setContentsMargins(0, 0, 0, 0)
body_layout.setSpacing(8)
# (sub-section labels + RichText link labels added here, mirroring
#  _sibling_label config: setTextFormat(Qt.RichText), setOpenExternalLinks(False),
#  linkActivated.connect(self._on_similar_link_activated))
sc_layout.addWidget(self._similar_body)
center.addWidget(self._similar_container)

# Default-hidden until MainWindow pushes initial visibility
self._similar_container.setVisible(False)

# Cache attribute
self._similar_cache: dict[int, tuple[list, list]] = {}
```

### Example 4: MainWindow QAction wiring (Phase 47.1 verbatim)

```python
# musicstreamer/ui_qt/main_window.py — additive

# Construction (in Settings group, adjacent to act_theme at line 188-190)
self._act_show_similar = self._menu.addAction("Show similar stations")
self._act_show_similar.setCheckable(True)
self._act_show_similar.setChecked(
    self._repo.get_setting("show_similar_stations", "0") == "1"
)
self._act_show_similar.toggled.connect(self._on_show_similar_toggled)

# Initial-state push (after panel construction, adjacent to line 338)
self.now_playing.set_similar_visible(self._act_show_similar.isChecked())

# Signal connection (adjacent to line 324)
self.now_playing.similar_activated.connect(self._on_similar_activated)

# Slot (adjacent to _on_stats_toggled at line 539-542)
def _on_show_similar_toggled(self, checked: bool) -> None:
    """Phase 67 / S-01, M-01: persist toggle and push visibility to panel."""
    self._repo.set_setting("show_similar_stations", "1" if checked else "0")
    self.now_playing.set_similar_visible(checked)

# Sibling-activation delegator (adjacent to _on_sibling_activated at line 430-441)
def _on_similar_activated(self, station: Station) -> None:
    """Phase 67 / C-01: user clicked a similar-station link.
    Delegate to _on_station_activated for uniform side-effect set."""
    self._on_station_activated(station)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| dbus-python for MPRIS2 | PySide6.QtDBus | Phase 41 (v2.0) | Not relevant to Phase 67 (already settled) |
| GLib.idle_add for GTK cross-thread updates | Qt signals with `Qt.QueuedConnection` | Phase 36 (v2.0) | Phase 67 has no cross-thread work — pure synchronous UI slot |
| Phase 51's private `_render_sibling_html` on EditStationDialog | Phase 64's free-function `render_sibling_html` in `url_helpers.py` | Phase 64 (v2.1) | Sets the precedent: Phase 67's `render_similar_html` follows the same free-function placement |
| Single `QLabel` with `<br>`-separated `<a>` (Phase 64 inline) | Same — but tested at scale up to 5 rows × 2 sub-sections | Phase 67 first | Risk: vertical density on Wayland fractional scaling (Pitfall 10); mitigated by WARNING-only project-memory directive |
| `random.sample(set, k)` (worked pre-3.11) | `random.sample(list, k)` only | Python 3.11+ | New code in Phase 67 must build pools as lists, not sets [VERIFIED: live invocation] |

**Deprecated/outdated:** Nothing in Phase 67 touches the deprecated GTK4 / GLib.idle_add code paths (deleted in Phase 36). The phase is built entirely on the post-v2.0 PySide6 surface.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Wayland DPR=1.0 deployment makes vertical 5-row `<br>`-separated `<a>` rendering acceptable without HiDPI testing. | Pitfall 10 + Architecture Patterns Pattern 4 | Low — if Kyle ever moves to a fractional-scaling display, planner falls back to D-03 option (b) per CONTEXT.md (per-row `QVBoxLayout` of clickable widgets). |
| A2 | `Repo.list_stations()` cost is negligible at 50–200 stations (1 + N SQL queries). | Pitfall 9 | Low — confirmed by reading `repo.py:225-251`; SQLite local file. If user grows library to 1000+, the `list_stations_with_streams` JOIN is a future optimization. |
| A3 | Click-time `repo.get_station(id)` ValueError-on-miss + None-on-test-double dual shape is the only crash path that matters. Other transient DB errors are similarly catchable. | Pitfall 3 + Pattern 2 | Low — Phase 64 ships this pattern in production today; no regressions reported. |
| A4 | The user wants "Same provider" matching by `provider_id` (foreign-key match) rather than `provider_name` string match. | Architecture / Code Examples / Pitfall reference | Medium — provider_id match is more correct (handles renamed providers); provider_name match is what the station-list filter chips use. CONTEXT.md does not explicitly say. **Recommendation: planner defaults to `provider_id` match per dataclass-correctness; if both provider_id is None, both stations are excluded from each other (T-04d covers one direction; the symmetric case is "current.provider_id is None → empty Same provider pool, which is the natural outcome").** Tests should pin both directions. |

**A4 deserves explicit attention from the planner.** CONTEXT.md says "Same provider" but doesn't specify the matching field. `provider_id` (int) and `provider_name` (str) are both available on `Station`. provider_id is the canonical foreign-key reference; provider_name is the denormalized-for-display string. **Default to provider_id with a None-safe guard** (T-04d covers None-on-candidate; current's None means an empty pool, naturally).

## Open Questions

1. **Should the Refresh button be a `QToolButton` with a glyph (`↻`) or a `QPushButton` with text "Refresh"?**
   - What we know: codebase precedent for icon-only controls in NowPlayingPanel uses `QToolButton` (`star_btn`, `eq_toggle_btn`, `play_pause_btn`, `stop_btn`, `edit_btn` all 28-36px QToolButton). Phase 60.4 uses `QPushButton` for vote buttons (1-5 score) because they need text glyphs and check state. The Refresh button has no check state; just an icon. **Recommendation: `QToolButton` with Unicode `↻` (U+21BB) glyph, 24×24, no setIcon required.**
   - What's unclear: Whether the codebase has an SVG icon resource for Refresh. [Searched `:/icons/` references in code — no `refresh-symbolic.svg` is registered.] Using the Unicode glyph avoids needing to add a new icon resource.
   - Recommendation: Plan 02 chooses `QToolButton(text="↻")`, 24×24, with `setToolTip("Refresh similar stations")`.

2. **Does CONTEXT.md's `▾ ` (U+25BE small triangle) vs the codebase precedent's `▼ ` (U+25BC full triangle) matter?**
   - What we know: CONTEXT.md S-03 specifies `▾`/`▸` (U+25BE / U+25B8). The existing `_toggle_filter_strip` uses `▼`/`▶` (U+25BC / U+25B6).
   - What's unclear: Whether visual consistency with the existing collapsible header matters more than the CONTEXT.md exact spec.
   - Recommendation: Use CONTEXT.md's `▾`/`▸` (smaller, more discreet — fits the now-playing context where the header is a sub-feature, not a primary navigation affordance like the Filters strip). Both are pure Unicode; no resource files needed.

3. **Should the panel push the persisted collapse state into the body widget on `set_similar_visible(True)`, or only on first construction?**
   - What we know: S-03a says "Toggling the master OFF then back ON should remember the prior `similar_stations_collapsed` value (no auto-reset)." If the body widget retains its visibility state after the container is hidden, then re-showing the container should naturally reveal the body in its prior state. But Qt's `setVisible(False)` on a parent container doesn't change child visibility; child `isVisible()` still returns `True` (just visually hidden as part of the parent). So the natural behavior IS persistence — no extra read needed at `set_similar_visible(True)` time.
   - What's unclear: Whether a fresh-launch-with-master-ON scenario needs to read the collapse setting. Yes — on `__init__`, the panel must read `Repo.get_setting('similar_stations_collapsed', '0')` and apply it to the body widget's visibility before the master toggle's first push.
   - Recommendation: Read collapse setting once in `__init__` (after constructing the body widget) and apply to `_similar_body.setVisible(...)`. After that, the collapse toggle is the only writer. `set_similar_visible(visible)` only touches `_similar_container.setVisible(visible)` and never re-reads the collapse setting.

4. **Should there be a "no similar stations" placeholder when both pools are empty for a station whose master toggle is ON?**
   - What we know: D-02 says "When both pools are empty for the bound station, the entire Similar Stations section body is empty — but the section header still shows (when master toggle ON) so the user knows the feature is active and can refresh." So the header shows but the body is genuinely empty (no placeholder text).
   - What's unclear: Whether an empty section body is visually disorienting (a header with nothing under it).
   - Recommendation: Ship as specced (empty body when both pools empty). The Refresh button at the right of the header signals affordance — clicking it just re-rolls the empty pool to the same empty result, which is fine. If UAT shows confusion, Plan 04 can add a small italic hint label "No similar stations in your library yet."

5. **Does the Phase 67 `_refresh_similar_stations` method need a panel-public `refresh_similar_stations()` seam for testability (mirroring Phase 64 D-04 discretion)?**
   - What we know: Phase 64 keeps `_refresh_siblings` private and tests bind via `panel.bind_station(station)` to drive it. Phase 67 can do the same.
   - What's unclear: Whether tests will want to invoke the refresh logic directly without a full bind cycle (e.g., to exercise the Refresh button without mocking the click).
   - Recommendation: Keep `_refresh_similar_stations` private. Tests for the Refresh button drive it via `panel._on_refresh_similar_clicked()` directly (Qt button click is well-tested elsewhere; we don't need to test that QToolButton.clicked emits when clicked).

## Environment Availability

Phase 67 is a pure code+config change with no new external tool dependencies. No probe step is required.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | Type hints, `random.Random`, `html.escape` | ✓ | 3.14.4 (development) / 3.10+ (production minimum per pyproject.toml) | — |
| PySide6 6.11+ | QLabel.linkActivated, Qt.RichText, QToolButton, QPushButton | ✓ | 6.11.0 (verified) | — |
| SQLite (via stdlib `sqlite3`) | Repo.set_setting / get_setting | ✓ | bundled with Python stdlib | — |
| pytest 9+ | Test runner | ✓ | per pyproject.toml | — |
| pytest-qt 4+ | Qt widget tests via `qtbot` | ✓ | per pyproject.toml | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9+ + pytest-qt 4+ |
| Config file | `pyproject.toml` (`testpaths = ["tests"]`, marker `integration`) |
| Quick run command | `uv run --with pytest --with pytest-qt pytest tests/test_pick_similar_stations.py tests/test_now_playing_panel.py -x -k "similar"` |
| Full suite command | `uv run --with pytest --with pytest-qt pytest tests` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SIM-01 | Master toggle in hamburger persists default `'0'` to SQLite | integration | `pytest tests/test_main_window_integration.py::test_show_similar_action_is_checkable -x` | ❌ Wave 0 |
| SIM-01 | Master toggle persists `'1'` on check; `'0'` on uncheck; panel container visibility flips | integration | `pytest tests/test_main_window_integration.py::test_show_similar_toggle_persists_and_toggles_panel -x` | ❌ Wave 0 |
| SIM-02 | When master toggle is OFF on construction, `_similar_container.isHidden() is True` | integration | `pytest tests/test_main_window_integration.py::test_show_similar_default_off_hides_container -x` | ❌ Wave 0 |
| SIM-03 | Section header collapse persists `'0'`/`'1'`; on next `__init__` body visibility matches | unit + integration | `pytest tests/test_now_playing_panel.py::test_similar_collapse_persists -x` | ❌ Wave 0 |
| SIM-04 | Same-provider pool excludes self id, AA siblings, no-provider candidates; 5 random picks (deterministic via seeded rng) | unit (pure helper) | `pytest tests/test_pick_similar_stations.py::test_same_provider_pool_excludes_self_aa_and_no_provider -x` | ❌ Wave 0 |
| SIM-04 | Same-provider pool returns ALL candidates when pool < 5 (no padding) | unit | `pytest tests/test_pick_similar_stations.py::test_same_provider_pool_lt_5_returns_all -x` | ❌ Wave 0 |
| SIM-05 | Same-tag pool excludes self id, AA siblings, no-tag candidates; uses `normalize_tags` union; 5 random picks | unit | `pytest tests/test_pick_similar_stations.py::test_same_tag_pool_union_semantics -x` | ❌ Wave 0 |
| SIM-05 | Same-tag pool returns ALL candidates when pool < 5 | unit | `pytest tests/test_pick_similar_stations.py::test_same_tag_pool_lt_5_returns_all -x` | ❌ Wave 0 |
| SIM-04+05 | Cross-pool dedup is NOT performed: a station qualifying for both pools appears in both lists | unit | `pytest tests/test_pick_similar_stations.py::test_pools_allow_cross_pool_duplicates -x` | ❌ Wave 0 |
| SIM-04+05 | Reproducibility via injected `rng=random.Random(42)`: identical input → identical output | unit | `pytest tests/test_pick_similar_stations.py::test_seeded_rng_reproducibility -x` | ❌ Wave 0 |
| SIM-04+05 | AA-sibling exclusion: a DI.fm station with a ZenRadio sibling does NOT see the ZenRadio sibling in either pool (when ZenRadio shares the same provider or tag) | unit | `pytest tests/test_pick_similar_stations.py::test_aa_siblings_excluded_from_both_pools -x` | ❌ Wave 0 |
| SIM-04+05 | Empty library (only the playing station) → both pools empty | unit | `pytest tests/test_pick_similar_stations.py::test_empty_library_returns_empty_pools -x` | ❌ Wave 0 |
| SIM-04+05 | Current station with no provider + no tags → both pools empty | unit | `pytest tests/test_pick_similar_stations.py::test_no_provider_no_tags_returns_empty_pools -x` | ❌ Wave 0 |
| SIM-04+05 | Performance: 500-station library returns in < 50ms | unit | `pytest tests/test_pick_similar_stations.py::test_perf_500_stations_under_50ms -x` | ❌ Wave 0 |
| SIM-06 | Cache: bind_station(A) populates `_similar_cache[A.id]`; second bind_station(A) reuses cached sample (no re-roll) | qtbot | `pytest tests/test_now_playing_panel.py::test_similar_cache_reused_on_revisit -x` | ❌ Wave 0 |
| SIM-06 | Cache: bind_station(A) then bind_station(B) populates both keys; bind_station(A) again returns A's original sample | qtbot | `pytest tests/test_now_playing_panel.py::test_similar_cache_keyed_by_station_id -x` | ❌ Wave 0 |
| SIM-07 | Refresh button click pops current station's cache entry and re-derives both pools (with possibly different random sample) | qtbot | `pytest tests/test_now_playing_panel.py::test_refresh_similar_pops_cache_and_rerolls -x` | ❌ Wave 0 |
| SIM-08 | Click on similar-link emits `similar_activated(Station)` with resolved Station payload | qtbot | `pytest tests/test_now_playing_panel.py::test_similar_link_emits_similar_activated_with_station_payload -x` | ❌ Wave 0 |
| SIM-08 | MainWindow `_on_similar_activated` delegates to `_on_station_activated` (playback DID switch) | integration | `pytest tests/test_main_window_integration.py::test_similar_link_switches_playback -x` | ❌ Wave 0 |
| SIM-09 | "Same provider" rows render `{Name}` only (no provider in label text) | unit | `pytest tests/test_pick_similar_stations.py::test_render_similar_html_provider_section_no_provider_in_text -x` | ❌ Wave 0 |
| SIM-09 | "Same tag" rows render `{Name} ({Provider})` | unit | `pytest tests/test_pick_similar_stations.py::test_render_similar_html_tag_section_includes_provider -x` | ❌ Wave 0 |
| SIM-09 | Renderer escapes both name AND provider against HTML injection | unit | `pytest tests/test_pick_similar_stations.py::test_render_similar_html_escapes_name_and_provider -x` | ❌ Wave 0 |
| SIM-10 | Sub-section hidden-when-empty: empty same-provider pool → `_same_provider_subsection.isHidden() is True` | qtbot | `pytest tests/test_now_playing_panel.py::test_same_provider_subsection_hidden_when_empty -x` | ❌ Wave 0 |
| SIM-10 | Both sub-sections hidden but section header visible when master toggle ON and both pools empty | qtbot | `pytest tests/test_now_playing_panel.py::test_section_header_visible_with_empty_pools -x` | ❌ Wave 0 |
| SIM-11 | Click-time defense: `repo.get_station` raises ValueError → silent no-op (no signal emit) | qtbot | `pytest tests/test_now_playing_panel.py::test_similar_link_handler_no_op_when_repo_get_station_raises -x` | ❌ Wave 0 |
| SIM-11 | Click-time defense: malformed href (wrong prefix, non-int payload) → silent no-op | qtbot | `pytest tests/test_now_playing_panel.py::test_similar_link_handler_no_op_on_malformed_href -x` | ❌ Wave 0 |
| SIM-11 | Click-time defense: id matches bound station → silent no-op | qtbot | `pytest tests/test_now_playing_panel.py::test_similar_link_handler_no_op_when_id_matches_bound_station -x` | ❌ Wave 0 |
| SIM-12 | Phase 64 untouched: `_sibling_label` exists, `_refresh_siblings` runs once per bind_station; both unchanged after Phase 67 lands | qtbot (regression) | `pytest tests/test_now_playing_panel.py::test_sibling_label_visible_for_aa_station_with_siblings -x` (existing test must remain green) | ✅ exists |
| QA-05 | All new signal connections use bound methods (no lambdas) | structural (grep) | `pytest tests/test_main_window_integration.py::test_no_lambda_on_similar_signal_connections -x` | ❌ Wave 0 |
| QA-05 | Master toggle action's `triggered`/`toggled` connection uses bound method | structural | (covered by `test_no_lambda_on_similar_signal_connections`) | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run --with pytest --with pytest-qt pytest tests/test_pick_similar_stations.py tests/test_now_playing_panel.py -x -k "similar or sibling"` (~ 5–10 sec on existing test corpus shape; runs both Phase 67 NEW tests and Phase 64 REGRESSION tests so the I-01 invariant is checked on every commit)
- **Per wave merge:** `uv run --with pytest --with pytest-qt pytest tests/test_pick_similar_stations.py tests/test_now_playing_panel.py tests/test_main_window_integration.py tests/test_aa_siblings.py tests/test_filter_utils.py -x` (~ 30 sec; full sub-system + adjacent regressions)
- **Phase gate:** `uv run --with pytest --with pytest-qt pytest tests` green before `/gsd-verify-work`. Project full-suite has been ~400+ tests at 5-10 sec total since v2.0.

### Wave 0 Gaps

- [ ] `tests/test_pick_similar_stations.py` — covers SIM-04, SIM-05, SIM-09. New file. Shape mirror: `tests/test_aa_siblings.py` (231 lines, no qtbot, no fixtures, one assertion per test, factory-only setup). Recommended file size: ~ 250-350 lines.
- [ ] `tests/test_now_playing_panel.py` — extend with sections covering SIM-03, SIM-06, SIM-07, SIM-08, SIM-10, SIM-11. Existing file at 2554 lines; add a Phase 67 section after the Phase 64 section (which ends around line 898). Mirror the shape of the Phase 64 section verbatim.
- [ ] `tests/test_main_window_integration.py` — extend with sections covering SIM-01, SIM-02, SIM-08 (integration), QA-05 structural. Existing file at 1125 lines; add a Phase 67 section after the Phase 64 section (which ends around line 1125). Mirror the shape of the Phase 47.1 stats-toggle tests at lines 568-606 verbatim.
- [ ] **Framework install:** None needed — pytest + pytest-qt already in `pyproject.toml [project.optional-dependencies] test`.
- [ ] **conftest fixture extension:** none — `FakeRepo` in `tests/test_now_playing_panel.py` already supports `stations=` parameter (added for Phase 64) at line 65-112; `FakeRepo` in `tests/test_main_window_integration.py` at line 86-178 already supports `settings=`. No new fixture surface needed.
- [ ] **Conftest `_FakeRepo` (in `tests/conftest.py:132-206`):** does NOT have `is_favorited` (used by NowPlayingPanel internally), but Phase 64 testing doesn't touch the panel through this fixture path. Phase 67 tests should use the `FakeRepo` defined inside `tests/test_now_playing_panel.py` (lines 65-112), which is purpose-built for panel tests and already has `is_favorited`. **No conftest change needed.**

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 67 surfaces no auth flows |
| V3 Session Management | no | No session state |
| V4 Access Control | no | Single-user desktop app, no access tiers |
| V5 Input Validation | yes | (1) `repo.get_station(int(href[len(prefix):]))` parses an int from the link href — must wrap in `try/except ValueError` (Phase 64 pattern at `now_playing_panel.py:961-962`); (2) `Repo.get_setting('similar_stations_collapsed', '0')` reads `str` and is compared `== '1'` — no parsing risk; (3) `random.sample(pool, k=...)` requires `k <= len(pool)` — clamp via `k=min(sample_size, len(pool))` (Pitfall 1) |
| V6 Cryptography | no | `random` (not `secrets`) is correct — discovery feature, not security context |

### Known Threat Patterns for PySide6 + Qt.RichText QLabel

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| HTML injection via Station.name interpolated into RichText `<a>` link text | Tampering | `html.escape(station.name, quote=True)` — already canonical at `url_helpers.py:260`; Phase 67's renderer extends to also escape `provider_name` |
| HTML injection via Station.provider_name in "Same tag" rows | Tampering | NEW for Phase 67: `html.escape(station.provider_name or "", quote=True)` (Pitfall 7) |
| URL injection via `<a href="...">` payload | Tampering | href payload is `f"similar://{station.id}"` — `station.id` is an int from SQLite; no string interpolation possible. **Lock:** the renderer constructs the href via f-string with the int id only, never with any user-controlled string |
| Open external link bypass (Qt loads a `javascript:` URL) | Tampering | `setOpenExternalLinks(False)` on the renderer label (Phase 64 pattern at `now_playing_panel.py:267`) — `linkActivated` signal is the only path; the slot rejects any href not starting with `"similar://"` (Pitfall 8) |
| Click-time station deletion → ValueError → unhandled exception in slot | Denial of Service (slot crash → Qt slots-never-raise violation) | Wrap `repo.get_station(...)` in `try/except Exception:` + `is None` check (Phase 64 pattern at `now_playing_panel.py:969-974`) |
| Repo.list_stations transient DB failure during `_refresh_similar_stations` | Denial of Service | Wrap `repo.list_stations()` in `try/except Exception:` + hide section + bail (Phase 64 pattern at `now_playing_panel.py:921-926`) |

**Threat-model surface review per CONTEXT.md request 11:**
- **User-controlled strings flowing into RichText render:** Station.name + Station.provider_name. Both must pass `html.escape(..., quote=True)`. Network names (`NETWORKS`) are not used by Phase 67's renderer — only by Phase 64's. No tag matched-display name is rendered (D-04 specifies just `{Name}` and `{Name} ({Provider})`).
- **Tooltip on rows:** D-04a does not specify tooltips; CONTEXT.md does not request them. **Recommendation: no tooltips on similar-station rows for v1**, sidestepping any user-controlled string flowing into a tooltip.
- **href payload safety:** integer-only `similar://{int(station.id)}`. Same injection-safe property as Phase 64's `sibling://{id}`. The slot validates `href.startswith("similar://")` and `int(...)` parsing; rejects all other shapes silently.
- **Bound station name in any peripheral display:** the Phase 67 section header reads "Similar Stations" — a compile-time string. The current bound station's name is NOT interpolated into any new label text in Phase 67. (`name_provider_label` is a Phase 37 widget already using `Qt.PlainText`.) No new escape surface.

## Sources

### Primary (HIGH confidence)
- `musicstreamer/url_helpers.py` (264 lines) — read in full; `find_aa_siblings` at lines 168-231, `render_sibling_html` at lines 234-263. **All Phase 67 helpers go in this file.**
- `musicstreamer/ui_qt/now_playing_panel.py` (1408 lines) — read lines 1-650 + targeted greps for sibling/similar/stats anchors; Phase 64 sibling implementation at lines 200, 253-271, 529-538, 893-975. **The Phase 67 panel surface mirrors this exactly.**
- `musicstreamer/ui_qt/main_window.py` (861 lines) — read lines 160-260 + 418-500 + 535-545 + 780-810; Phase 47.1 stats QAction at lines 205-210/338/539-542; Phase 64 sibling wiring at lines 324/430-441; Phase 66 Theme picker at lines 188-190/780-790. **The Phase 67 hamburger entry goes adjacent to Theme; the slot signature mirrors `_on_stats_toggled` verbatim.**
- `musicstreamer/ui_qt/station_list_panel.py` (lines 191-198, 266-267, 516-519) — Filter strip flat-button collapsible header pattern. **The Phase 67 collapsible header reuses this idiom.**
- `musicstreamer/repo.py` (lines 220-360) — `Repo.list_stations`, `get_station`, `get_setting`, `set_setting` signatures. **All Phase 67 calls verified.**
- `musicstreamer/filter_utils.py` (81 lines) — `normalize_tags` at lines 5-19. **T-02 reuses verbatim.**
- `musicstreamer/models.py` (47 lines) — `Station` and `StationStream` dataclass shapes. **No schema change.**
- `tests/conftest.py` (224 lines) — autouse `_stub_bus_bridge`, Qt `offscreen` env var, Phase 60 `_FakeRepo`. **Phase 67 tests inherit cleanly.**
- `tests/test_aa_siblings.py` (231 lines) — pure-helper test shape; one factory `_mk(...)`, one assertion per test, no fixtures, no qtbot. **The Phase 67 `test_pick_similar_stations.py` mirrors this verbatim.**
- `tests/test_now_playing_panel.py` (2554 lines) — Phase 64 panel test section at lines 770-898; existing `FakeRepo` with `stations=` and `is_favorited` at lines 65-112; `_make_aa_station` factory at lines 132-158. **Phase 67 panel tests extend this file.**
- `tests/test_main_window_integration.py` (1125 lines) — Phase 47.1 stats toggle tests at lines 568-606; Phase 64 integration test at lines 1075-1124; existing `FakeRepo` at lines 86-178; lambda-grep structural test at lines 609-628. **Phase 67 integration tests extend this file.**
- `.planning/phases/64-audioaddict-siblings-on-now-playing/64-CONTEXT.md` — D-01..D-08 conceptual sibling locks; Phase 67 inherits the signal-out-from-panel pattern, bind_station refresh trigger, hidden-when-empty contract, integer-href format, defense-in-depth repo lookup, bound-method connections.
- `.planning/phases/66-color-themes-preset-and-custom-color-schemes-vaporwave-paste/66-CONTEXT.md` — Theme picker hamburger placement (M-01-equivalent at 66 D-15) confirms the Settings group position adjacent to Accent Color. Phase 67's "Show similar stations" QAction is the next entry in this group.
- `.planning/codebase/CONVENTIONS.md` — QA-05 bound-method connection mandate; T-39-01 PlainText convention deviation pattern with `html.escape`.
- `.planning/codebase/ARCHITECTURE.md` — Three-thread model (Qt main / GLib bus / worker daemons). Phase 67 has zero cross-thread work.
- `.planning/codebase/TESTING.md` — pytest-qt `qtbot`, `FakeRepo` patterns, `qtbot.waitSignal` usage.
- `.planning/PROJECT.md` — "personal library of 50–200 stations" performance budget guarantee; "hamburger menu is the canonical location for global toggles".

### Secondary (MEDIUM confidence)
- Python stdlib `random` documentation — `random.sample(population, k, *, counts=None)` signature [VERIFIED via `python3 -c "import random; help(random.sample)"`]; `random.Random(seed)` reproducibility [VERIFIED via live invocation]; `k > len` raises ValueError; sets-as-population deprecated in 3.11+ [VERIFIED via live invocation].
- Python stdlib `html.escape(s, quote=True)` — escapes `& < > " '`; already used in `url_helpers.render_sibling_html`.
- PySide6 6.11 / Qt 6.11 — `QLabel.linkActivated(QString)` signal fires on `<a href>` clicks when `setTextFormat(Qt.RichText)` and `setOpenExternalLinks(False)`; standard since Qt 5. Verified via existing Phase 64 implementation in production.

### Tertiary (LOW confidence)
- None. All claims in this research are verified against either the codebase (read directly), Python stdlib (verified by live invocation), or PySide6 production usage (verified by Phase 64 / 47.1 / 50 / 60 / 66 having shipped).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every library/version verified by live invocation or pyproject.toml read; no new dependencies introduced.
- Architecture: HIGH — every pattern has 1+ landed precedent in this codebase (Phase 47.1 / 51 / 64 / 66); zero novel architecture decisions.
- Pitfalls: HIGH — Pitfalls 1, 2, 5 are stdlib-verified; Pitfalls 3, 4, 6, 11 are codebase-precedent verified; Pitfall 7 is a NEW concern flagged for the planner; Pitfall 9 is grounded in PROJECT.md's library size guarantee; Pitfall 10 is grounded in the project-memory Wayland directive.
- Renderer security envelope: HIGH — direct read of `url_helpers.py:234-263` and `tests/test_aa_siblings.py:185-231`.
- Test placement: HIGH — direct read of all three target test files (`test_now_playing_panel.py`, `test_main_window_integration.py`, `test_aa_siblings.py`) confirms structural shape and existing fixture support for Phase 67 needs.
- Provider matching field choice (provider_id vs provider_name) [A4]: MEDIUM — CONTEXT.md does not explicitly say. Recommendation defaults to provider_id (foreign-key correctness) with planner override possible if user prefers provider_name (display-string match parity with filter chips).

**Research date:** 2026-05-09
**Valid until:** 2026-06-09 (30 days; Phase 67 touches stable Qt 6 + PySide6 6.11 + Python stdlib APIs that don't churn on month-scale; codebase patterns are all v2.1-current)
