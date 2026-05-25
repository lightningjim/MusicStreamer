# Phase 71: Sister station expansion - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Make "this station has sister/variant stations" a first-class, in-app concept the user can manage manually — replacing the current need for hand-edited DB rows. This phase ships a **manual user-curated link mechanism** that AUGMENTS (does not replace) Phase 51's URL-derived AA cross-network sibling auto-detection.

The mechanism must handle two real cases the existing code can't:

1. **AA name-mismatch overrides** — Phase 51's `find_aa_siblings` keys off URL channel-keys (`_aa_channel_key_from_url` in `musicstreamer/url_helpers.py`), so DI.fm "Classical Relaxation" and RadioTunes "Relaxing Classical" don't auto-pair because their channel-key slugs diverge. Today the only fix is a manual DB edit.
2. **Same-provider variants** — SomaFM "Drone Zone" + "Drone Zone 2", and "Classic Groove Salad" / "Groove Salad" / "Groove Salad 2" — independent stations under one provider that share branding and concept but play different content. No auto-detection exists for these.

The new linking surface lives in `EditStationDialog`, with a '+ Add sibling' button that opens a two-step provider→station picker modal. Linked siblings render in the existing Phase 51/64 'Also on:' chip row, merged with AA auto-detected siblings into one unified display (no auto/manual visual distinction beyond the per-chip unlink affordance).

**In scope:**
- New `station_siblings` SQLite table with two FK columns to `stations.id`, a CHECK constraint `a_id < b_id` to enforce single-row symmetric representation, `UNIQUE(a_id, b_id)`, `ON DELETE CASCADE`. Migration follows the Phase 47.2 / Phase 70 idempotent pattern (try/except `sqlite3.OperationalError`, no `user_version` bump).
- New `Repo` methods (planner finalizes signatures): `list_sibling_links(station_id) -> list[int]`, `add_sibling_link(a_id, b_id)`, `remove_sibling_link(a_id, b_id)`. All normalize the (smaller_id, larger_id) ordering at the boundary.
- New helper `find_manual_siblings(stations, current_station_id, link_rows) -> list[tuple[network_slug, station_id, station_name]]` in `musicstreamer/url_helpers.py` (colocated with `find_aa_siblings` + `render_sibling_html` per Phase 64 D-03). Returns rows in a deterministic order (planner picks: alphabetical by name OR by station_id ASC).
- Merge layer that combines `find_aa_siblings(...)` + `find_manual_siblings(...)` into one ordered list, deduplicating by `station_id` (auto-detected entries take precedence so an entry can't appear twice if a user manually linked something AA already auto-detects). Output feeds `render_sibling_html` unchanged.
- `EditStationDialog` UX additions in the area around `_sibling_label` (edit_station_dialog.py:486):
  - Replace the read-only QLabel with a chip row where each linked sibling is a clickable chip. Manual chips have a small `×` button; AA auto-detected chips render as plain text (no `×`).
  - '+ Add sibling' button at the end of the chip row opens a new `AddSiblingDialog` (or similar) modal.
  - `AddSiblingDialog`: provider QComboBox at top (defaults to the editing station's provider_id), pre-populated with all providers from `Repo.list_providers()`. Below it, a QListView/QListWidget showing stations under the selected provider, with a search line-edit filter. Single-select; OK button enabled when a station is selected. Clicking OK persists the link via `Repo.add_sibling_link` and closes the modal. To add a second sibling, the user reopens the modal.
  - The picker excludes (a) the editing station itself, and (b) stations already linked as a sibling of the editing station (manual or AA auto).
- `NowPlayingPanel` surfacing: the existing Phase 64 'Also on:' line continues to render the merged result. No new label, no new row — manual links flow through `render_sibling_html` via the same `find_aa_siblings`-call site, replaced by the merge helper.
- ZIP export/import: each station's exported JSON gains a `siblings: ["Other Station Name", ...]` field, listing partner station NAMES (not IDs — survives ID renumbering across DBs). On import, names are resolved against the destination library; unresolved names are silently dropped. Implementation lands in `settings_export.py` `_insert_station` + `_replace_station` (Phase 42 / Phase 47.3 / Phase 70 forward-compat pattern). Old ZIPs without the key default to empty list.
- Tests: pure helper (`find_manual_siblings` correctness, merge dedup), repo round-trip (insert/list/delete/cascade), settings-export forward-compat (missing key + present key), dialog integration (provider switch reloads station list; search filters; OK persists), `EditStationDialog` chip row (manual chip has `×`, AA chip doesn't, click `×` removes link).

**Out of scope:**
- No URL-pattern auto-detection for SomaFM-style variants (deferred to Phase 74 — see Deferred Ideas).
- No override/suppression of AA auto-detected siblings. If `find_aa_siblings` returns a false positive, the user cannot hide it via this phase. (User confirmed at Concept question 1: "Merge into existing 'Also on:' line" — option 1, not option 3.)
- No directional/canonical-primary concept. Links are symmetric and unordered. (Storage Q1: chose `station_siblings(a_id, b_id)` symmetric table over `sister_of_id` directional FK.)
- No transitive closure auto-expansion. If A↔B and B↔C are linked separately, A sees only B and C sees only B. (User did not select "More storage questions" when offered.) Planner can choose whether the merge helper does a one-hop walk or strict direct-link lookup; defaulting to strict direct-link keeps the mental model simple.
- No sibling group ID column on `stations`. (Storage Q1: chose join table.)
- No multi-select in the picker modal. (UX Q2: chose "Provider defaults to current station's provider; one sibling per modal open" — single-select.)
- No 'Manage siblings' separate dialog. Unlinking happens inline via per-chip `×` in the Edit dialog. (UX Q3: chose option 1.)
- No keyboard shortcut for adding a sibling (not raised; no decision needed unless the planner spots a natural fit).
- No SomaFM, GBS.FM, or other provider-specific code paths. This phase is provider-agnostic — the picker shows all providers, the user picks.
- No surfacing on the station-tree row (no chain-link icon to signal "this has siblings"). Surfaces are NowPlaying + Edit dialog only. (Concept Q2: chose "NowPlaying line + Edit dialog", not the three-surface option.)
- No vocabulary change. The codebase, UI label ("Also on:"), and existing Phase 51/64 `_sibling_label` / `find_aa_siblings` / `render_sibling_html` names continue. The phase ROADMAP title uses "sister" colloquially; the code stays on "sibling".

</domain>

<decisions>
## Implementation Decisions

### Concept

- **D-01:** **One unified 'Also on:' display.** Manual sibling links are additive to the existing Phase 51/64 AA URL-derived 'Also on:' line — NOT a separate "Sisters:" or "Related:" row. (User Q1: "Merge into existing 'Also on:' line".)
- **D-02:** **Manual links can be cross-provider.** The new mechanism handles AA name-mismatch (DI.fm "Classical Relaxation" ↔ RadioTunes "Relaxing Classical" — different providers in the app) AND same-provider variants (SomaFM Drone Zone ↔ Drone Zone 2). The picker modal allows the user to select ANY provider, defaulting to the editing station's provider for the common SomaFM-variant case.
- **D-03:** **AA auto-detection unchanged.** Phase 51's `find_aa_siblings` keeps its existing URL-channel-key behavior. No suppression of AA false positives in this phase. (User Q1: chose option 1, not option 3 "merge with override".)
- **D-04:** **NowPlaying + Edit dialog only.** No station-tree chain-link icon, no hamburger menu entry. (User Q2: "NowPlaying line + Edit dialog", not the three-surface option.)

### Storage

- **D-05:** **Symmetric join table.** New table `station_siblings(a_id INTEGER NOT NULL, b_id INTEGER NOT NULL, FOREIGN KEY(a_id) REFERENCES stations(id) ON DELETE CASCADE, FOREIGN KEY(b_id) REFERENCES stations(id) ON DELETE CASCADE, UNIQUE(a_id, b_id), CHECK(a_id < b_id))`. The CHECK constraint enforces canonical (smaller_id, larger_id) ordering so a single row represents both directions of the symmetric link. (User Q1: "Symmetric join table `station_siblings(a_id, b_id)`".)
- **D-06:** **Migration follows Phase 47.2 idempotent pattern.** `CREATE TABLE IF NOT EXISTS` in the main `db_init` body; no `user_version` bump. New table only — no `ALTER TABLE` on existing tables. (Project convention: see `musicstreamer/repo.py:18-66` for the existing pattern.)
- **D-07:** **ZIP export carries siblings by station NAME, not ID.** Each station JSON gains `siblings: ["Other Station Name", ...]`. On import, the destination DB resolves names back to IDs against its own station table; unresolved names silently drop. Survives cross-machine sync where the same station has different IDs in different DBs. (User Q2: "Yes — export per-station as a list of partner station NAMES".)
- **D-08:** **ON DELETE CASCADE on both FKs.** Deleting a linked station auto-removes the link rows. The surviving partner just loses one entry from its 'Also on:' line. Matches the existing `station_streams` pattern (`repo.py:63`). (User Q3: "ON DELETE CASCADE — link rows auto-delete".)

### SomaFM Interpretation

- **D-09:** **SomaFM 'Drone Zone' and 'Drone Zone 2' are INDEPENDENT stations.** They play different curated content, with separate ICY metadata. They are NOT a multi-stream-on-one-station shape (which is the existing failover model). Each is its own row in `stations` with its own `station_streams` entries; the new sibling mechanism links them. (User Q1: "Different content — separate stations".)
- **D-10:** **Phase 71 ships fully manual linking only.** No SomaFM URL-pattern detector. (User Q2: "Fully manual — ship the linking mechanism, no SomaFM auto-detect".)

### Edit-dialog UX

- **D-11:** **'+ Add sibling' button next to the chip row.** The existing read-only `_sibling_label` QLabel (edit_station_dialog.py:486) is replaced (or supplemented in-place) with a chip row container plus a '+ Add sibling' QToolButton or similar. (User Q1: "'+ Add sibling' button → modal with library station search".)
- **D-12:** **Two-step picker: provider QComboBox → station list.** The modal opens with the editing station's provider pre-selected in a provider QComboBox at the top. Below it, a station QListView filtered to that provider. Changing the provider re-populates the station list. (User Q1 follow-up: "Select provider, unlocks another selection for stations under the provider".)
- **D-13:** **One sibling per modal open; single-select.** Clicking OK persists the link and closes the modal. For multiple siblings, the user reopens the modal. (User Q2: "Provider defaults to current station's provider; one sibling per modal open" — chose this over the multi-select Confirm/Cancel option.)
- **D-14:** **Per-chip `×` to unlink, in the merged 'Also on:' chip row.** Manual links render as a chip with a small `×` button. Clicking `×` calls `Repo.remove_sibling_link(...)` and refreshes the row. (User Q3: "Per-sibling 'x' next to each name in the 'Also on:' display".)
- **D-15:** **AA auto-detected chips show plain text, no `×`.** Visually distinguishable from manual chips by the absence of the `×` button. Removal of AA auto-siblings is not supported in this phase. (User Q4: "Only manually-linked siblings show 'x'; AA auto-siblings show plain text".)

### Claude's Discretion

- **Helper module placement** for `find_manual_siblings` and the merge wrapper: extending `musicstreamer/url_helpers.py` is the strong default (Phase 51-01 / Phase 64 D-03 precedent — `find_aa_siblings`, `render_sibling_html` colocated). Planner confirms.
- **Chip row implementation:** Qt has no built-in chip widget. Options: small `QPushButton` with `×` glyph + name; or a horizontal `FlowLayout` (already used in the dialog for tags). Planner picks based on `EditStationDialog` density.
- **Provider QComboBox shape in the picker modal:** native QComboBox vs. a list-style alternative. Native QComboBox is sufficient — provider count is small (typically 5–15).
- **Station list widget in the picker:** QListView with a `QSortFilterProxyModel` + line-edit filter follows the existing DiscoveryDialog pattern. Planner can choose QListWidget if simpler given the modal's lifetime.
- **Sort order of manual-linked siblings in the merged display:** alphabetical by name vs. station_id ASC vs. insertion order. Planner picks; alphabetical is the safe default for visual stability.
- **Whether the merge helper does a one-hop walk for transitive closures:** the user did not commit either way (declined "more storage questions"). Default to strict direct-link lookup (no transitive expansion) — matches the symmetric-table mental model. If usability gaps emerge, revisit.
- **Tooltip on chips:** none specified. Planner can add a tooltip showing the provider name on hover for cross-provider links.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase context (the existing sibling/sister code paths)
- `.planning/phases/51-audioaddict-cross-network-siblings/51-CONTEXT.md` — Phase 51 (BUG-02). Establishes the AA URL-derived sibling concept, `find_aa_siblings` placement convention in `url_helpers.py`, the `_sibling_label` QLabel + `_render_sibling_html` (now `render_sibling_html` free function), and the `navigate_to_sibling = Signal(int)` pattern. D-04 (sibling-detection runs only on AA) and D-06 (hidden when empty) are the precedents the merge layer must preserve.
- `.planning/phases/64-audioaddict-siblings-on-now-playing/64-CONTEXT.md` — Phase 64. Establishes the NowPlayingPanel 'Also on:' label position (between `name_provider_label` and `icy_label`, now_playing_panel.py:155-164), the D-03 helper-promotion pattern (`render_sibling_html` moved from `EditStationDialog` private method to `url_helpers.py` free function), and the D-05 zero-vertical-space hidden-when-empty contract. The merge helper output feeds this surface unchanged.

### Code paths the phase extends
- `musicstreamer/url_helpers.py` — Phase 51 / Phase 64 location of `find_aa_siblings` (line 171), `render_sibling_html` (line 237), and the NETWORKS/_is_aa_url/_aa_slug_from_url/_aa_channel_key_from_url helpers. New `find_manual_siblings` + merge wrapper land here.
- `musicstreamer/repo.py` — schema is in `db_init` (lines 15-67). New `station_siblings` table is added to the executescript block. New CRUD methods on `Repo` for sibling-link rows.
- `musicstreamer/ui_qt/edit_station_dialog.py` — `_sibling_label` at line 486, `_refresh_siblings` at line 617, `_on_sibling_link_activated` slot, `navigate_to_sibling = Signal(int)` at line 255. The '+ Add sibling' button and chip-row container replace/wrap the existing label area. New `AddSiblingDialog` (or equivalent) is the picker modal.
- `musicstreamer/ui_qt/now_playing_panel.py` — `_sibling_label` for the merged 'Also on:' line. No new widget — the merge happens at the helper-call site.
- `musicstreamer/settings_export.py` — `_insert_station` / `_replace_station` blocks gain a `siblings` key serialization and resolve-by-name on import. Phase 42 / Phase 47.3 / Phase 70 forward-compat pattern.

### Project-level
- `.planning/PROJECT.md` — Key Decisions table; the new D-NN entries from this phase get appended on phase completion.
- `.planning/REQUIREMENTS.md` — REQUIREMENTS-level traceability. Phase 71 is rolling-milestone; the phase title in ROADMAP.md is the active "requirement" entry, not a separate `SIB-NN` row (planner can propose a new requirement code if useful).
- `.planning/ROADMAP.md` line 596 — Phase 71 statement of intent. Line 626 — Phase 74 statement (SomaFM full catalog) is the home for deferred SomaFM URL-pattern auto-detection.

### Routing skill (auto-loaded on Windows-packaging / GStreamer / PyInstaller work — NOT directly load-bearing for this phase, but listed for completeness per project routing convention)
- `.claude/skills/spike-findings-musicstreamer/SKILL.md` — referenced by `CLAUDE.md` routing.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `find_aa_siblings(stations, current_station_id, current_first_url) -> list[tuple[str, int, str]]` at `url_helpers.py:171` — returns `(network_slug, station_id, station_name)` triples in NETWORKS declaration order. The new merge helper accepts and extends this output shape (or wraps it) to keep `render_sibling_html` unchanged.
- `render_sibling_html(siblings, current_name) -> str` at `url_helpers.py:237` — produces the 'Also on:' HTML with HTML-escaped names, U+2022 bullet separator, U+2014 em-dash for name-mismatch. The merge output feeds this unchanged in NowPlaying. The Edit dialog's new chip row uses a different rendering path (Qt widgets, not HTML).
- `EditStationDialog._sibling_label` at line 486 — Qt.RichText QLabel with `sibling://{id}` link scheme + `linkActivated` connected to `_on_sibling_link_activated` (Phase 51-03 / D-04..D-08). For the new chip row, this label is either replaced or supplemented by a horizontal container of clickable widgets.
- `navigate_to_sibling = Signal(int)` at `edit_station_dialog.py:255` — Phase 51 / D-09 pattern. The new chip-click flow can reuse this signal; the unlink (`×`) click is a separate slot that calls `Repo.remove_sibling_link` directly.
- `Repo` CRUD methods in `repo.py` — e.g., `list_streams`, `insert_stream`, `update_stream`, `list_stations`. The new `add_sibling_link` / `remove_sibling_link` / `list_sibling_links` follow the same shape (`con.execute(...)` + `con.commit()`).
- `Repo.list_providers()` and `Repo.list_stations()` — backing data for the picker modal's provider QComboBox and per-provider station list. No new queries needed.
- Phase 47.2 / Phase 70 idempotent ALTER TABLE pattern at `repo.py:69-103` — adapted as `CREATE TABLE IF NOT EXISTS` for the new `station_siblings` table.
- Phase 70 settings-export forward-compat idiom (`int(stream.get("sample_rate_hz", 0) or 0)`) — direct analog: `(station.get("siblings") or [])` returns empty list for old ZIPs.

### Established Patterns
- **Promote private helpers to `url_helpers.py` when needed across multiple UI surfaces** — Phase 64 D-03 promoted `_render_sibling_html` from `EditStationDialog` to `url_helpers.py`. The new merge helper is born in `url_helpers.py` for the same reason.
- **Symmetric storage via canonical (smaller_id, larger_id) row constraint** — not previously used in this codebase, but is the standard relational pattern for undirected edges. Avoids the dual-row-write + dedup-on-read alternative.
- **Idempotent migration (try/except OperationalError)** — for ALTER TABLE; for CREATE TABLE IF NOT EXISTS the IF NOT EXISTS clause is the equivalent.
- **Forward-compat ZIP import** — `(value.get("key") or default)` idiom at every read site so old ZIPs missing the key don't error.
- **Two-step modal pickers** — DiscoveryDialog (musicstreamer/ui_qt/discovery_dialog.py) is the closest existing reference for a search-driven station picker. Planner cross-references for layout/component reuse.
- **Self-exclusion + dedup at the helper level, not the call site** — `find_aa_siblings` excludes the current station's own id (line 122). The merge helper does the same for manual links AND dedups against AA auto-detected entries by station_id.

### Integration Points
- `EditStationDialog.__init__` constructs the existing siblings UI in `_refresh_siblings` (line 617). The new chip row + '+ Add sibling' button slot in here. The chip row's `×` slots call `Repo.remove_sibling_link` + `_refresh_siblings()` to repaint.
- `NowPlayingPanel._sibling_label` repopulates on `bind_station` (Phase 64 D-01). The merge helper replaces the direct `find_aa_siblings` call; everything downstream is unchanged.
- `settings_export._insert_station` / `_replace_station` — the `siblings` key is serialized after streams. On import, station rows are inserted first, then a second pass resolves names to IDs and writes `station_siblings` rows.
- The picker modal's `navigate_to_sibling` slot in `MainWindow` (Phase 51 / D-09) does not need to change for OK-button persistence — the picker modal calls `Repo.add_sibling_link` directly. The `navigate_to_sibling` signal continues to handle chip CLICKS (not unlink) to re-open EditStationDialog on the linked sibling.

</code_context>

<specifics>
## Specific Ideas

- **"Classical Relaxation and Relaxing Classical"** is the user's reference case for the AA name-mismatch problem. Today the user "had to insert by hand" — i.e., manually edit the DB. After this phase, the user opens EditStationDialog on either station, clicks '+ Add sibling', picks the other from the picker, and clicks OK. A row appears in `station_siblings`; both stations now show each other on the merged 'Also on:' line.
- **"SomaFM has 2 Drone Zones and 3 Groove Salad stations"** is the user's reference case for same-provider variants. After this phase, the user manually links Drone Zone ↔ Drone Zone 2 (1 link), and Classic Groove Salad ↔ Groove Salad ↔ Groove Salad 2 (3 links, A↔B / B↔C / A↔C — all manually created in 3 modal opens). The user explicitly accepted "one sibling per modal open" over multi-select.
- **Provider QComboBox default = editing station's provider** is load-bearing for the SomaFM use case — opens the modal already filtered to SomaFM, one-tap to pick the variant.
- The user said "Auto-connection can be deferred to Phase 74" — Phase 74 ("SomaFM full station catalog + art") is the natural home for URL-pattern auto-detection if the maintenance burden of manual SomaFM linking grows.
- Vocabulary: the user refers to "sister stations" colloquially (ROADMAP.md line 596) but the code stays on "sibling" (Phase 51/64 precedent). No vocabulary churn in code; UI label remains "Also on:".

</specifics>

<deferred>
## Deferred Ideas

- **SomaFM URL-pattern auto-detection** — parser for `ice4.somafm.com/dronezone-256-mp3` ↔ `dronezone2-256-mp3` (strip numeric suffix from slug, match remaining base across stations). User explicitly deferred to Phase 74 ("SomaFM full station catalog + art"). If accepted there, it lives as a `find_somafm_siblings` helper parallel to `find_aa_siblings`, merged into the same 'Also on:' line.
- **Auto-detection for other networks beyond AA and SomaFM** — the user noted "this may extend to other networks as I find more." Out of scope here; not yet on any roadmap phase. Future polish phase if a third network pattern emerges.
- **AA auto-detection override / suppression** — ability to hide a wrong AA URL-derived sibling. User rejected at Concept Q1 (chose option 1 "merge", not option 3 "merge with override"). If wrong AA matches become a real problem, future phase.
- **Transitive closure auto-expansion** — if A↔B and B↔C are linked separately, should A see C? User did not commit; default in this phase is strict direct-link (no expansion). If usability gaps emerge in a 3+ variant group, future polish.
- **Multi-select picker** — select all 3 Groove Salads at once and Confirm. User rejected at UX Q2 (chose single-select). If the user later discovers 4+ variant groups become tedious, a future UX polish phase could revisit.
- **Station-tree chain-link icon** — a visual cue that a station has siblings, paintable in the existing star delegate. User rejected at Concept Q2 (chose two-surface, not three-surface). Future polish if discoverability is an issue.
- **Vocabulary change to "sister" in the UI** — code and UI label stay on "sibling" / "Also on:". If the user later wants the label to read "Sisters" or "Variants", trivially editable.
- **Right-click context menu on a sibling chip** — alternative unlink affordance. User picked the per-chip `×` button. Future polish if `×` cluttering becomes an issue.
- **'Manage siblings' bulk dialog** — single dialog showing all current siblings with batch add/remove. User picked inline `×`. Future polish if mass-management is needed.
- **Cross-station bulk-link command** — e.g., select multiple stations in the tree, right-click "link as siblings." User did not raise. Future polish.

</deferred>

---

*Phase: 71-sister-station-expansion-1-add-ability-to-link-sister-statio*
*Context gathered: 2026-05-12*
