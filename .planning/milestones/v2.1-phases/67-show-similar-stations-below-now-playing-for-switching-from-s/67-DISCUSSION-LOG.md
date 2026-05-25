# Phase 67: Show similar stations below now playing for switching - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-09
**Phase:** 67-show-similar-stations-below-now-playing-for-switching-from-s
**Areas discussed:** Layout structure, Show/hide control, Tag matching semantics, Random sample lifetime + refresh

---

## Layout structure

### Q1: How should the two pools (same provider + same tag) be visually structured in the Now Playing panel?

| Option | Description | Selected |
|--------|-------------|----------|
| Two labeled sections | Two separate QLabel rows ("Same provider:" + "Same tag:"), each hidden-when-empty independently. Mirrors Phase 64's "Also on:" pattern shape. | ✓ |
| One combined list | Single "Similar:" line mixing both pools (with internal dedup). | |
| Two columns side-by-side | QHBoxLayout with two columns inside the center column. | |

**User's choice:** Two labeled sections.
**Notes:** Locked the explicit "why this is suggested" framing.

### Q2: Where should the two sub-sections sit relative to Phase 64's existing "Also on:" sibling line?

| Option | Description | Selected |
|--------|-------------|----------|
| Below "Also on:" line | Stack: name → "Also on:" → "Same provider:" → "Same tag:" → ICY. | |
| Below icy_label | Sections sit below ICY title and elapsed timer, away from station identity tagline. | |
| In a dedicated panel section | Add a new bordered/grouped sub-section at the bottom of the center column with its own "Similar Stations" header. | ✓ |

**User's choice:** In a dedicated panel section.
**Notes:** Promotes Similar Stations to its own UI region, clear separation from Phase 64's inline "Also on:" line.

### Q3: What should each suggestion render as inside the dedicated section?

| Option | Description | Selected |
|--------|-------------|----------|
| Inline link list | Phase 64 style: bullet-separated text links on one line. | |
| Vertical link list | One station per line stacked. | ✓ |
| Logo + name rows | Each row shows the station's logo next to the name. | |

**User's choice:** Vertical link list.
**Notes:** Easier to scan and click than the inline format; scales cleanly to up to 10 rows total (5 per pool).

### Q4: Should each suggestion line include any context beyond the station name?

| Option | Description | Selected |
|--------|-------------|----------|
| Just the name | Minimal; section header explains why each is suggested. | partial |
| Name + provider | "Drone Zone (SomaFM)" — adds station's provider in parens. | partial |
| Name + matched tag | "Drone Zone (ambient)" — only meaningful in Same tag section. | |

**User's choice:** Hybrid — name + provider for the Same tag section ONLY; just the name for the Same provider section.
**Notes:** Provider is implicit in the Same provider section (all rows share it); useful in the Same tag section because tag-matches cross provider boundaries.

---

## Show/hide control

### Q1: How should the user opt the Similar Stations section in/out (hidden by default per goal)?

| Option | Description | Selected |
|--------|-------------|----------|
| Hamburger menu toggle | Single "Show similar stations" checkable QAction in hamburger menu, persisted via Repo.set_setting. | |
| Panel collapsible button | Always-present "Show similar ▾" expander button on the panel itself. | |
| Hamburger toggle + section header collapser | Master enable in hamburger menu (off by default); when enabled, section header itself acts as collapser. Two levels of control. | ✓ |

**User's choice:** Hamburger toggle + section header collapser.
**Notes:** Cleanly satisfies "not shown by default" (master off → nothing on panel) AND gives a quick collapse without re-disabling the feature.

### Q2: Where in the hamburger menu should the master toggle sit?

| Option | Description | Selected |
|--------|-------------|----------|
| Top-level checkable item | A checkable QAction directly in the hamburger menu. | |
| Under a View submenu | Group with other view-toggles in a new View submenu. | |
| Near the Theme picker | Adjacent to Phase 66's Theme picker since both are visual/personalization toggles. | ✓ |

**User's choice:** Near the Theme picker.
**Notes:** Keeps related personalization controls together; no new submenu needed.

### Q3: When the master toggle is OFF (default), what does the user see on the panel?

| Option | Description | Selected |
|--------|-------------|----------|
| Nothing at all | Whole Similar Stations section hidden — zero vertical space, no header. | ✓ |
| Just the header collapsed | Section header still shows but body hidden. Hint that the feature exists. | |

**User's choice:** Nothing at all.
**Notes:** Strict reading of "not shown by default" — feature is invisible until enabled.

### Q4: When master toggle is ON and user uses the section-header collapser, should that collapsed state persist across launches or only across station changes?

| Option | Description | Selected |
|--------|-------------|----------|
| Persist across launches | Use a second Repo.set_setting key. Two persisted prefs total. | ✓ |
| Reset to expanded each launch | Header-collapse is purely in-memory. | |
| Reset to expanded on station change | Header-collapse only lasts until next station pick. | |

**User's choice:** Persist across launches.
**Notes:** `similar_stations_collapsed` is the second persisted key; user's collapse preference survives restarts.

---

## Tag matching semantics

### Q1: How should the "Same tag" pool be derived from a station with multiple tags?

| Option | Description | Selected |
|--------|-------------|----------|
| Union (any tag overlaps) | Pool = all stations sharing at least one tag. Largest, loosest. | ✓ |
| Intersection (all tags shared) | Pool = stations sharing all tags. Tight; often empty. | |
| Primary tag only | Pool = stations sharing the FIRST tag. | |

**User's choice:** Union (any tag overlaps).
**Notes:** Largest discovery pool; Refresh button handles the noise.

### Q2: How should tag comparisons handle case and whitespace?

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse normalize_tags | Use filter_utils.normalize_tags() — single source of truth. | ✓ |
| Custom tag parser | Roll a phase-specific parser for fuzzy/partial matching. | |

**User's choice:** Reuse normalize_tags.
**Notes:** No new tag-parsing convention introduced; matches existing station-list filter chips.

### Q3: Should a station qualifying under both pools appear in both lists, or be deduplicated?

| Option | Description | Selected |
|--------|-------------|----------|
| Allow duplicates | Same name can appear in both "Same provider" and "Same tag". | ✓ |
| Dedupe — provider wins | Cross-list dedup; provider-pool takes precedence. | |
| Dedupe — tag wins | Cross-list dedup; tag-pool takes precedence. | |

**User's choice:** Allow duplicates.
**Notes:** Each pool is sampled independently; user sees both reasons a station is similar.

### Q4: What stations should be EXCLUDED from both pools?

| Option | Description | Selected |
|--------|-------------|----------|
| The currently playing station itself | Always exclude self. | ✓ |
| Stations with no tags (Same tag pool only) | Empty-tag stations can never match by tag. | ✓ |
| Stations with no provider (Same provider pool only) | NULL provider can't match. | ✓ |
| Cross-network AA siblings already shown above | Avoid triple-listing across "Also on:" + "Same provider" + "Same tag". | ✓ |

**User's choice:** All four.
**Notes:** AA-sibling exclusion (T-04b) introduces a small Phase 64 dependency: derive sibling ids via `find_aa_siblings(...)` and filter both pools.

---

## Random sample lifetime + refresh

### Q1: When does the random sample of 5 (per pool) get re-rolled?

| Option | Description | Selected |
|--------|-------------|----------|
| Re-roll on every bind_station | Every new station shuffle. Predictable but restless. | |
| Re-roll only on Refresh click | Sample cached per (station, pool); reused even on revisit. | |
| Re-roll on bind, but stable until Refresh | Hybrid: roll if no cache for this station; otherwise reuse. Refresh always re-rolls. In-memory cache only. | ✓ |

**User's choice:** Re-roll on bind, but stable until Refresh.
**Notes:** In-memory dict on NowPlayingPanel keyed by station id; cleared on app restart.

### Q2: How should the Refresh control behave?

| Option | Description | Selected |
|--------|-------------|----------|
| Single Refresh button, both pools | One ↻ icon at section header; re-rolls both. | ✓ |
| Per-section refresh icons | One ↻ per sub-section. | |
| Refresh + per-section regen | Section-level button + click-on-header per-section. | |

**User's choice:** Single Refresh button, both pools.
**Notes:** Minimum-control surface; one-click re-roll for the whole section.

### Q3: What should happen to the cached sample if the underlying station library changes mid-session?

| Option | Description | Selected |
|--------|-------------|----------|
| Invalidate on library mutation | Subscribe to station_saved / deleted / import-complete signals. | |
| Stale-OK until Refresh or new station | No subscriptions; defensive lookup at click-time handles deletions. | ✓ |
| Invalidate only on station_deleted | Middle ground. | |

**User's choice:** Stale-OK until Refresh or new station.
**Notes:** Matches Phase 64 D-04 philosophy; defensive `get_station` wrap at click time mirrors `now_playing_panel.py:941-955`.

### Q4: When a pool has fewer than 5 candidates, what should the section show?

| Option | Description | Selected |
|--------|-------------|----------|
| Show all available | If only 3 same-provider stations exist, show all 3. No padding, no placeholder. | ✓ |
| Show all + 'no more' note | Italic "(only N similar stations)" hint. | |
| Show all + 'add more' hint | Promotional link to discovery dialog. | |

**User's choice:** Show all available.
**Notes:** Empty pool hides that sub-section entirely (per L-02).

---

## Claude's Discretion

- Section/sub-section header wording (planner can refine "Similar Stations" / "Same provider:" / "Same tag:" for visual fit; two-section structure is locked).
- Renderer choice (single QLabel with `<br>` vs QVBoxLayout of clickable rows — both meet contract).
- Signal name (`similar_activated` recommended; reusing `sibling_activated` acceptable if cleaner).
- Refresh icon placement on the section header (left vs right of collapse arrow).
- Container widget type (QGroupBox, custom styled QWidget, or plain QVBoxLayout block).
- Sample ordering in render (random order from `random.sample` vs alphabetical for stability).

## Deferred Ideas

- Surfacing on additional surfaces (right-click menu, mini-player, EditStationDialog).
- Smarter ranking (favorites boost, recency weighting, listener count, tag-overlap-count).
- Live-update on station_saved / deleted / import-complete signals.
- Per-section refresh icons.
- Keyboard shortcut for Refresh (Ctrl+R / F5).
- "Why suggested" tooltip (hover row to see which tag matched).
- Richer per-row content (logo, ICY preview, listener count, tag chips).
- Smarter random (deterministic seed per session, anti-recency).
- Per-pool size override (configurable count per pool).
- Same-tag-as-primary-tag-only fallback mode.
