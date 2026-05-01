# Phase 55: Edit Station Preserves Section State — Context

**Gathered:** 2026-04-30
**Status:** Ready for planning

<domain>
## Phase Boundary

When the user saves an edit (or creates, deletes, or imports a station), the **provider groups in the StationListPanel tree** keep whatever expand/collapse state the user had set. The save path no longer reshapes the tree.

The "sections" in the phase title are the provider groups in `StationListPanel`'s `QTreeView` — `EditStationDialog` itself has no collapsible widgets, confirmed by reading `musicstreamer/ui_qt/edit_station_dialog.py`.

**In scope:**
- Capture/restore provider-tree expansion across every refresh-after-mutation path that today calls `StationListPanel.refresh_model()`. That covers all five callers wired through `MainWindow._refresh_station_list()`: edit-save, new-station-save, delete, discovery import-complete, settings import-complete.
- Decouple the refresh path from the existing filter-driven `_sync_tree_expansion()` so that filter-change handlers continue to drive auto-expand on filter input, but refresh after a mutation does not.

**Out of scope:**
- Persisting expand state across app restarts (today the tree starts collapsed on launch — keep that).
- Changing filter-CHANGE behavior (search input, chip click, clear-all-filters still call `_sync_tree_expansion()` unchanged).
- Recently Played refresh (Phase 50 already preserves tree state via `refresh_recent()` — unaffected).

</domain>

<decisions>
## Implementation Decisions

### Scope of fix
- **D-01:** Fix at the layer where the damage happens — `StationListPanel.refresh_model()`. All five callers wired through `MainWindow._refresh_station_list()` benefit automatically: edit-save (`main_window.py:467`), new-station-save (`main_window.py:447`), delete (`main_window.py:476` via `_on_station_deleted`), discovery import-complete (`main_window.py:633`), and settings import-complete (`main_window.py:648`/`653`).
- **D-02:** Modify `refresh_model()` in place. Do NOT introduce a sibling method like `refresh_model_preserving_expansion()` — kept-in-place keeps the API single-truth and prevents future callers from picking the wrong one.
- **D-03:** Drop the `self._sync_tree_expansion()` call from inside `refresh_model()` (currently `station_list_panel.py:317`). The four existing filter-change callers — `_on_search_changed` (line 426), `_on_provider_chip_clicked` (line 436), `_on_tag_chip_clicked` (line 446), `_clear_all_filters` (line 462) — keep calling `_sync_tree_expansion()` unchanged.

### Filter-active behavior post-save
- **D-04:** Refresh-after-mutation preserves the user's manual per-group expand state **always**, even when a search or chip filter is active. Save events do not reshape the tree under any filter condition. SC #1/#2 are honored under filter-active conditions, which is where the bug bites worst today.
- **D-05:** Filter-CHANGE events keep the existing auto-expand behavior: typing into search or clicking a chip still calls `_sync_tree_expansion()`, which `expandAll()`s when any filter is active and `collapseAll()`s when filters are cleared. Two distinct paths: **refresh = preserve, filter-change = drive expansion.**

### New provider groups post-save
- **D-06:** When a save creates a brand-new provider group (a provider name not present in the captured pre-refresh state), the new group defaults to **expanded** — the user just touched a station that landed there, so the result should be visible without an extra click.
- **D-07:** Existing groups — including destination groups when a save moves a station between groups — preserve their captured manual state. A station moved into a previously-collapsed group does NOT auto-expand the destination. Consistent with D-04: only filter-change events drive expansion; save events never do.

### Claude's Discretion
- **State capture key.** By provider name (string) vs row index. Claude picks. Provider names are the stable key across `model.refresh()` (which invalidates indices via `beginResetModel`/`endResetModel`); index-based capture would break across the very reset we're protecting against.
- **Detecting newly-created provider groups.** Set difference between captured names and post-refresh model names. Implementation detail.
- **API surface.** Whether to expose a `preserve_expansion: bool = True` kwarg on `refresh_model()` for future opt-out vs hardcoding preserve. All five current callers want preserve; a kwarg would be dead code today. Hardcode unless planner finds a strong reason.
- **Recently Played coupling.** `refresh_model()` also calls `_populate_recent()` (line 318) and `_build_chip_rows()` (line 319). Neither touches the tree expansion state — leave both untouched.
- **Empty-source-group cleanup.** If a save empties the user's previously-current provider group (e.g., they edited the last station in a group and gave it a different provider), `StationTreeModel` drops the empty group. The captured state for that gone-now group is naturally pruned by the "intersect captured names with current model names" step. No special case needed.

</decisions>

<specifics>
## Specific Ideas

- The user-visible promise: **"Save doesn't shuffle my tree. Filter changes deliberately do."** Two paths, two responsibilities, no crosstalk.
- This generalizes Phase 50's pattern. Phase 50 added `refresh_recent()` so the recent-played update path could avoid `refresh_model()`. Phase 55 makes `refresh_model()` itself safe, so future callers don't have to choose between "refresh the tree" and "preserve user state."

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 55: Edit Station Preserves Section State" — goal, dependencies, three success criteria.
- `.planning/REQUIREMENTS.md` §BUG-06 — phase requirement statement.

### Phase 50 precedent (READ FIRST — same constraint, narrower fix)
- `.planning/phases/50-recently-played-live-update/50-CONTEXT.md` — D-04 explicitly avoids `refresh_model()` because it collapses tree groups. Phase 55 fixes the underlying generic defect Phase 50 worked around.

### Code touch points (load these to understand current state)
- `musicstreamer/ui_qt/station_list_panel.py:314-319` — `StationListPanel.refresh_model()`. Line 317 is the offending call to `_sync_tree_expansion()`. Replace the call site with capture-before / restore-after around `self.model.refresh(...)`.
- `musicstreamer/ui_qt/station_list_panel.py:333-339` — `_sync_tree_expansion()`. Implementation unchanged; just stops being called from `refresh_model()`.
- `musicstreamer/ui_qt/station_list_panel.py:424-462` — filter-change handlers (`_on_search_changed`, `_on_provider_chip_clicked`, `_on_tag_chip_clicked`, `_clear_all_filters`). Keep calling `_sync_tree_expansion()` unchanged.
- `musicstreamer/ui_qt/station_list_panel.py:270-288` — tree construction (`self.tree`, model, proxy). The `QTreeView.isExpanded(QModelIndex)` and `expand(QModelIndex)`/`collapse(QModelIndex)` API are the capture/restore primitives.
- `musicstreamer/ui_qt/station_tree_model.py:60-80` — `StationTreeModel` provider-grouping shape (provider name → list of station rows). Used to identify provider groups by name during capture/restore.
- `musicstreamer/ui_qt/main_window.py:447,467,476,633,648,653` — the five `_refresh_station_list()` call sites. No change required at these sites; the fix is upstream.
- `musicstreamer/ui_qt/main_window.py:561-563` — `_refresh_station_list()` itself. No change.

### Project conventions
- `.planning/codebase/CONVENTIONS.md` — snake_case, no formatter/linter, type hints throughout.
- Bound-method signal connections, no self-capturing lambdas (QA-05). No new signal wiring is required for this fix, so this is a non-issue here, but worth flagging if a planner reaches for one.

### No external specs
No ADRs or external feature docs apply — the bug is fully captured by the four code touch-point clusters above and the three success criteria in ROADMAP.md.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `StationTreeModel.refresh(stations)` — already wraps `beginResetModel`/`endResetModel` correctly; no model change needed.
- `QTreeView.isExpanded(QModelIndex)` / `expand(QModelIndex)` / `collapse(QModelIndex)` — standard Qt API, no abstraction needed.
- `_sync_tree_expansion()` — unchanged, just decoupled from the refresh path. Filter-change wiring stays.
- Provider-name-as-stable-key — `Station.provider_name` is the same field `StationTreeModel` groups by, so it's the natural capture key.

### Established Patterns
- `refresh_recent()` (Phase 50) is the precedent for "external trigger refreshes a slice without resetting the tree." Phase 55 generalizes by making the tree-resetting refresh itself non-destructive.
- `model.refresh()` invalidates `QModelIndex` instances. Any captured state must use a stable key (provider name string) — index-based capture would defeat the fix.

### Integration Points
- Capture/restore wraps `self.model.refresh(self._repo.list_stations())` inside `refresh_model()`. Pseudocode shape (planner picks final form):
  1. Walk `self.model` rows, build `expanded_provider_names: set[str]` from `self.tree.isExpanded(self._proxy.mapFromSource(provider_index))` for each provider row.
  2. `self.model.refresh(self._repo.list_stations())`.
  3. Walk new model rows; for each provider name in the new model: if name was captured as expanded → expand the new index; if name is brand-new (not in captured set) → expand by default (D-06); otherwise → leave collapsed (default Qt state after reset).
  4. `self._populate_recent()` and `self._build_chip_rows()` continue to run unchanged after the model refresh.
- Source-vs-proxy index mapping matters: provider rows are accessed via `self._proxy.mapFromSource(...)` for the view's `isExpanded`/`expand` calls (the view sees proxy indices). Mirrors the pattern at `select_station` (`station_list_panel.py:361`).

</code_context>

<deferred>
## Deferred Ideas

- **Persist expand state across app restarts (QSettings).** Today the tree starts fully collapsed on launch (SC #3 confirms this is the desired initial state). A future phase could persist user expansion to settings — out of scope here.
- **Animated expansion on new-group default-expand.** D-06 expands new groups instantly. A future polish phase could add a brief expand animation. Not in scope.
- **Cross-provider move detection in the editor.** D-07 keeps destination groups in their captured state, even on cross-provider moves. If user testing later shows people lose their just-saved station, a follow-up could add a "scroll to the saved station" affordance — separate phase.

</deferred>

---

*Phase: 55-edit-station-preserves-section-state*
*Context gathered: 2026-04-30*
