# Phase 55: Edit Station Preserves Section State — Research

**Researched:** 2026-05-01
**Domain:** Qt6 / PySide6 model-view (QTreeView + QSortFilterProxyModel + custom QAbstractItemModel) — capture/restore expansion state across `beginResetModel`/`endResetModel`.
**Confidence:** HIGH

## Summary

Phase 55 fixes BUG-06 by making `StationListPanel.refresh_model()` preserve the user's per-provider-group expand/collapse state across the underlying `StationTreeModel.refresh()` call (which wraps `beginResetModel` / `endResetModel`). Today, `refresh_model()` calls `self._sync_tree_expansion()` immediately after the model reset, which unconditionally `expandAll()`s when a filter is active and `collapseAll()`s otherwise — destroying the user's manual state on every save/delete/import.

CONTEXT.md locks the design tightly: capture provider names (string-keyed) → call `model.refresh(...)` → restore expansion by walking the post-refresh model and `tree.expand(proxy.mapFromSource(provider_source_idx))` for each name in the captured set, with brand-new provider names (set difference) defaulting to expanded (D-06). The existing filter-change paths (`_on_search_changed`, `_on_provider_chip_clicked`, `_on_tag_chip_clicked`, `_clear_all_filters`) continue to call `_sync_tree_expansion()` unchanged — separation of concerns: **save = preserve, filter-change = drive expansion.**

**Primary recommendation:** Modify `StationListPanel.refresh_model()` in place. Drop line 317's `self._sync_tree_expansion()` call. Wrap `self.model.refresh(...)` with `_capture_expanded_provider_names()` (returns `set[str]`) before and `_restore_expanded_provider_names(captured)` after. Both helpers walk the source model rows directly (provider rows live there); for `isExpanded`/`expand` calls on the view, map source→proxy via `self._proxy.mapFromSource(provider_source_idx)` and guard against the invalid-`QModelIndex` returned for filtered-out provider rows. The pattern mirrors `select_station` at `station_list_panel.py:341-365` (already does the source-walk + proxy-map dance). Add one new model accessor — `StationTreeModel.provider_name_at(row: int) -> str | None` — to avoid string-stripping the labelled `"Foo (3)"` display text (the raw `provider_name` is not currently exposed; the label is the only externally-readable form).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pre-refresh capture of expanded provider names | View layer (`StationListPanel`) | Model (`StationTreeModel.provider_name_at`) | The view owns expansion state (`QTreeView.isExpanded`). A model accessor is the cleanest way to read raw provider names without parsing the labelled `"Foo (N)"` display string. |
| Model reset (`beginResetModel`/`endResetModel`) | Model (`StationTreeModel.refresh`) | — | Already correct; no model change beyond the new `provider_name_at` read API. |
| Post-refresh restore of expansion | View layer (`StationListPanel`) | Proxy (`StationFilterProxyModel.mapFromSource`) | Expansion lives on the view, indexed by proxy `QModelIndex`. Source→proxy mapping happens at the view boundary. |
| Filter-driven auto-expand (unchanged) | View layer (`_sync_tree_expansion`) | Proxy (`has_active_filter`) | Out of scope for this fix — kept exactly as-is. |
| Recently Played refresh | View layer (`_populate_recent`) | Repo (`list_recently_played`) | Already independent; left untouched per CONTEXT D-04 §Claude's Discretion. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | >=6.11 (per `pyproject.toml`) | QTreeView + QSortFilterProxyModel + QAbstractItemModel — already the project's UI toolkit | Project locked on Qt since Phase 36. No alternative under consideration. [VERIFIED: `pyproject.toml:13`] |
| pytest-qt | >=4 (test extra) | Headless Qt unit tests via `qtbot` fixture; `QT_QPA_PLATFORM=offscreen` already set in `tests/conftest.py:13` | Established project pattern — `tests/test_station_list_panel.py` already uses it. [VERIFIED: `pyproject.toml:29`, `tests/conftest.py:13`] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=9 | Existing test runner | All tests. [VERIFIED: `pyproject.toml:28`] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| String-keyed capture by provider name | Index-based `QPersistentModelIndex` capture | **Rejected** — Qt docs confirm persistent indexes are invalidated on `endResetModel`. [CITED: doc.qt.io/qt-6/qabstractitemmodel.html#endResetModel — "persistent model indexes... has been invalidated"] |
| Modify `refresh_model()` in place | Add sibling method `refresh_model_preserving_expansion()` | **Rejected by CONTEXT D-02** — single-truth API; future callers cannot pick the wrong one. |
| Walk via `index.data(Qt.DisplayRole)` to get provider names | Add `StationTreeModel.provider_name_at(row)` accessor | Display label is `"Foo (3)"` (suffix appended at `station_tree_model.py:84`). Stripping the suffix to recover raw name is fragile if a provider name itself ends in `" (N)"`. New accessor is 4 lines and exact. **Recommendation: add the accessor.** |

**Installation:** No new dependencies. All required libraries already installed.

**Version verification:** Skipped — no new packages introduced.

## Architecture Patterns

### System Architecture Diagram

```
                  user clicks Save in EditStationDialog
                                 |
                                 v
                     dlg.station_saved signal fires
                                 |
                                 v
                   MainWindow._refresh_station_list()  (main_window.py:561-563)
                                 |
                                 v
                   StationListPanel.refresh_model()    (THIS IS THE FIX SITE)
                                 |
        +------------------------+------------------------+
        |                        |                        |
        v                        v                        v
  CAPTURE (new)             model.refresh(...)       RESTORE (new)
  walk source model         beginResetModel/         walk new source model
  rows; for each            endResetModel;           rows; for each name:
  provider row, read         all view-side             - in captured set -> expand
  raw name +                 expansion is wiped        - new name (D-06)  -> expand
  isExpanded(proxy.          and persistent            - else             -> leave collapsed
  mapFromSource(             indexes invalidated     map source->proxy
  source_idx))                                        before tree.expand(...)
        |
        v
  expanded_names: set[str]
                                                            |
                                                            v
                            self._populate_recent()  (unchanged, line 318)
                                                            |
                                                            v
                            self._build_chip_rows()   (unchanged, line 319)

  PARALLEL PATH (unchanged): filter-change handlers
  _on_search_changed / _on_provider_chip_clicked /
  _on_tag_chip_clicked / _clear_all_filters
        |
        v
  proxy.set_search/set_providers/set_tags/clear_all
        |
        v
  self._sync_tree_expansion()   <-- still drives expandAll/collapseAll
        |
        v                         (filter-CHANGE only)
  view-side expansion updated
```

### Component Responsibilities

| Component | File:Lines | Phase 55 Change |
|-----------|-----------|-----------------|
| `StationListPanel.refresh_model()` | `station_list_panel.py:314-319` | Replace line 317 `self._sync_tree_expansion()` with capture-before / restore-after wrapping the `model.refresh(...)` call. |
| `StationListPanel._capture_expanded_provider_names()` (NEW) | new helper | Walk `self.model` rows; for each, read raw provider name (via new accessor) and `self.tree.isExpanded(self._proxy.mapFromSource(prov_source_idx))`; return `set[str]`. Skip names whose proxy mapping is invalid (filtered out — view cannot show them as expanded anyway). |
| `StationListPanel._restore_expanded_provider_names(captured: set[str])` (NEW) | new helper | After model reset, walk new `self.model` rows; for each, read raw name. If `name in captured` OR `name not in pre_refresh_names_set` (D-06: brand-new) → map source→proxy and expand if proxy index is valid. Else leave collapsed (default Qt state after reset). |
| `StationTreeModel.provider_name_at(row: int)` (NEW) | `station_tree_model.py` (new method) | `return self._root.children[row].label.rsplit(" (", 1)[0]` — OR better, store the raw name on `_TreeNode` (e.g., add `provider_name: str | None = None` field set at line 71) and return that. **Recommend the latter** to keep label-formatting reversible-only (avoids fragile `rsplit` on names ending in `" (N)"`). |
| `_sync_tree_expansion()` | `station_list_panel.py:333-339` | **No change.** Still called by the four filter-change handlers (lines 426, 436, 446, 462). |
| Five `_refresh_station_list()` call sites | `main_window.py:447, 467, 476, 633, 648, 653` | **No change.** Fix is upstream in `refresh_model()`; all five callers benefit automatically. |

### Recommended Project Structure

No new files. Modifications confined to:
- `musicstreamer/ui_qt/station_list_panel.py` (`refresh_model` body + 2 new private helpers)
- `musicstreamer/ui_qt/station_tree_model.py` (1 new public accessor `provider_name_at` + optional `_TreeNode.provider_name` field)
- `tests/test_station_list_panel.py` (new test cases under a Phase 55 / BUG-06 header — mirror Phase 50's pattern at lines 500-534)

### Pattern 1: Source-walk + proxy-map for view operations
**What:** When a method needs to (a) iterate source-model rows AND (b) operate on the view-visible proxy index, walk the source model directly with `self.model.index(row, 0)` then convert with `self._proxy.mapFromSource(source_idx)`.
**When to use:** Capture/restore loops, programmatic selection, programmatic expansion. Required because the source model owns the data shape but the view sees only proxy indices.
**Example (existing precedent — `select_station`):**
```python
# Source: musicstreamer/ui_qt/station_list_panel.py:355-365
for prov_row in range(self.model.rowCount()):
    prov_idx = self.model.index(prov_row, 0)
    for child_row in range(self.model.rowCount(prov_idx)):
        child_idx = self.model.index(child_row, 0, prov_idx)
        station = self.model.station_for_index(child_idx)
        if station is not None and station.id == station_id:
            proxy_idx = self._proxy.mapFromSource(child_idx)
            self.tree.expand(proxy_idx.parent())
            self.tree.setCurrentIndex(proxy_idx)
            self.tree.scrollTo(proxy_idx)
            return
```

### Pattern 2: Set-difference for newly-created group detection (D-06)
**What:** `new_names = {model.provider_name_at(r) for r in range(model.rowCount())}; brand_new = new_names - captured_names_pre_refresh`.
**When to use:** Whenever a save can produce a provider group that did not exist pre-save (e.g., user edits a station and assigns it to a provider that had no prior stations).
**Example:**
```python
# Pseudocode for _restore_expanded_provider_names
def _restore_expanded_provider_names(
    self, expanded_pre: set[str], all_pre: set[str]
) -> None:
    for prov_row in range(self.model.rowCount()):
        name = self.model.provider_name_at(prov_row)
        if name is None:
            continue
        was_expanded = name in expanded_pre
        is_brand_new = name not in all_pre  # D-06
        if not (was_expanded or is_brand_new):
            continue  # leave collapsed (Qt default after reset)
        source_idx = self.model.index(prov_row, 0)
        proxy_idx = self._proxy.mapFromSource(source_idx)
        if not proxy_idx.isValid():
            continue  # filtered out — cannot expand a row the proxy doesn't show
        self.tree.expand(proxy_idx)
```

### Anti-Patterns to Avoid
- **Stripping `" (N)"` suffix off `Qt.DisplayRole`:** Fragile (a provider name like `"Sounds (Hi-Res)"` would round-trip differently). Use a dedicated accessor that returns the raw name.
- **Capturing via `QPersistentModelIndex`:** Qt invalidates them on `endResetModel`. CITED above.
- **Calling `_sync_tree_expansion()` from `refresh_model()`:** That is exactly the bug being fixed (CONTEXT D-03). The four filter-change callers keep it.
- **Adding a `preserve_expansion: bool = True` kwarg:** CONTEXT marks this as Claude's Discretion but flags it as dead code today — all five current callers want preserve. Hardcode preserve.
- **Re-reading `repo.list_stations()` twice:** `refresh_model` already passes `self._repo.list_stations()` to `model.refresh`. The capture step reads the *current* (pre-refresh) model — a separate repo round-trip would be wasteful and could see a different result if anything mutates the DB between reads.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tracking expansion live via `expanded()`/`collapsed()` signals into a side dict | A signal-listener bookkeeping layer | `QTreeView.isExpanded(QModelIndex)` polled at capture time | Capture happens at one well-defined moment (entry to `refresh_model`); polling is simpler, has no signal-ordering concerns, and avoids state that can drift if a future code path mutates expansion outside the panel. |
| Source ↔ proxy index conversion | Manual row-arithmetic | `proxy.mapFromSource()` / `proxy.mapToSource()` | Filter proxies do not preserve row indices when filtering is active. Manual math will break under search/chip filters. The existing codebase already uses these methods consistently. |
| Re-implementing model reset semantics | Direct `dataChanged` storms | Existing `StationTreeModel.refresh()` (already wraps `beginResetModel`/`endResetModel`) | The model is already correctly written. Phase 55 does not touch model internals. |

**Key insight:** This fix is *narrow*. The model layer is correct, the proxy is correct, the view APIs are standard Qt. The defect is one mis-placed call (`_sync_tree_expansion()` inside `refresh_model`) destroying state that the model reset would otherwise leave the user free to re-establish. The fix replaces destruction-then-rebuild with capture-then-restore.

## Runtime State Inventory

> Phase 55 is a pure code change inside one Qt panel. No data migration, no service config, no OS-registered state, no secret/env var, no build artifact rename. Inventory below for completeness.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — verified by grep `expand|collapse|tree_state` against `repo.py`/`migrations`/`settings_export.py` | None |
| Live service config | None — no external service tracks expansion | None |
| OS-registered state | None — Qt expansion lives in-process only (no QSettings persistence today; per CONTEXT §Deferred, that's a future phase) | None |
| Secrets/env vars | None | None |
| Build artifacts | None | None |

**Nothing found in any category.** The fix is entirely in-process Qt model-view code.

## Common Pitfalls

### Pitfall 1: Capturing names from labelled display text
**What goes wrong:** Reading `idx.data(Qt.DisplayRole)` returns `"SomaFM (3)"` not `"SomaFM"`. Round-tripping into capture set and then comparing against future raw provider names produces empty intersection — every group restores as "brand new" → all expanded → looks like the bug is fixed, but D-07 ("destination groups in collapsed state stay collapsed when a station is moved into them") is silently broken.
**Why it happens:** `station_tree_model.py:82-84` mutates `grp.label` to append `" (N)"` after population. The raw provider name is not stored on `_TreeNode`.
**How to avoid:** Add `StationTreeModel.provider_name_at(row: int) -> str | None` (and ideally a `_TreeNode.provider_name` raw field) that returns the unlabelled name. Use it in both capture and restore.
**Warning signs:** Test `test_existing_group_remains_collapsed_when_user_had_collapsed_it` returns `expanded=True` instead of `False`.

### Pitfall 2: Calling `mapFromSource` on a filtered-out provider row during restore
**What goes wrong:** When a search/chip filter is active and a provider group has zero matching children, `filterAcceptsRow` returns `False` for that provider. `proxy.mapFromSource(source_idx)` returns an invalid `QModelIndex`. Calling `tree.expand(invalid_idx)` is silently a no-op in Qt, but defensive code reading `idx.row()` or asserting validity will misbehave.
**Why it happens:** `StationFilterProxyModel.filterAcceptsRow` (file `station_filter_proxy.py:60-73`) hides provider groups with no matching children when a filter is active.
**How to avoid:** Guard with `if proxy_idx.isValid(): self.tree.expand(proxy_idx)`. Captured names whose post-refresh proxy index is invalid silently stay "wanted-expanded but invisible" — when the user later clears the filter, `_sync_tree_expansion()` runs `collapseAll()`, so the want-state is lost. **This matches CONTEXT D-04**: filter-CHANGE deliberately drives expansion. The capture/restore loop is for the refresh-after-mutation path only.
**Warning signs:** AttributeError or assertion failure when filter is active during a save. (Should not happen with the validity guard.)

### Pitfall 3: Capturing from the proxy instead of the source model
**What goes wrong:** Walking `self._proxy.rowCount()` instead of `self.model.rowCount()` skips provider groups currently filtered out. Their expanded state is then "captured as not-expanded" — but the user may have expanded them earlier, before the filter was applied. After save, when the filter relaxes (e.g., user clears search), those groups appear collapsed even though the user had expanded them.
**Why it happens:** Confusion between proxy-row iteration (view-visible only) and source-row iteration (full model).
**How to avoid:** **However — this is acceptable behavior per CONTEXT D-04, which says "preserve user state under filter-active conditions"** for the SAVE-PATH only. The user's manual expansion of a group while the filter is active CAN be captured (proxy.mapFromSource of a *visible* provider returns a valid proxy index, and `tree.isExpanded(proxy_idx)` returns the user's actual state). Walking the source model and skipping invalid proxy mappings during capture means filtered-out groups are simply not represented in the captured set — which is fine: the view never showed them as expanded, so the user could not have manipulated their state during this session. Walking source-then-source is the correct strategy. **The trap is walking the proxy** — that loses access to filtered-out groups for the brand-new-group set difference (D-06).
**Warning signs:** New provider groups created post-save fail to auto-expand because `all_pre` was computed from the proxy and missed groups outside the active filter.

### Pitfall 4: Forgetting that `endResetModel` collapses every row
**What goes wrong:** Assuming "the user had it expanded → it's still expanded after `model.refresh`." Not so. Qt resets all view-side expansion. So the restore loop must re-expand every name in the captured set, not just newly-discovered names.
**Why it happens:** Naive intuition: "model reset reshapes data, view stays as-is." Wrong — view persistent indexes are invalidated and view reconstructs from row 0, all collapsed.
**How to avoid:** Restore loop processes ALL provider rows in the post-refresh model; only those NOT in the captured-expanded set AND NOT brand-new are left in their default (collapsed) state.
**Warning signs:** Test `test_existing_group_remains_expanded_after_save` returns `expanded=False`.

## Code Examples

Verified patterns from project source:

### Existing source-walk + proxy-map (precedent for capture/restore)
```python
# Source: musicstreamer/ui_qt/station_list_panel.py:341-365 (select_station)
def select_station(self, station_id: int) -> None:
    if self._stack.currentIndex() != 0:
        self._on_stations_clicked()
    for prov_row in range(self.model.rowCount()):
        prov_idx = self.model.index(prov_row, 0)
        for child_row in range(self.model.rowCount(prov_idx)):
            child_idx = self.model.index(child_row, 0, prov_idx)
            station = self.model.station_for_index(child_idx)
            if station is not None and station.id == station_id:
                proxy_idx = self._proxy.mapFromSource(child_idx)
                self.tree.expand(proxy_idx.parent())
                self.tree.setCurrentIndex(proxy_idx)
                self.tree.scrollTo(proxy_idx)
                return
```

### Existing pytest-qt test of expansion under filter (sanity for fix)
```python
# Source: tests/test_station_list_panel.py:113-132
def test_provider_groups_expand_when_search_active(qtbot):
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)
    panel._search_box.setText("a")
    any_expanded = False
    for row in range(panel._proxy.rowCount()):
        group_proxy = panel._proxy.index(row, 0)
        if panel.tree.isExpanded(group_proxy):
            any_expanded = True
            break
    assert any_expanded is True
    panel._search_box.clear()
    for row in range(panel._proxy.rowCount()):
        group_proxy = panel._proxy.index(row, 0)
        assert panel.tree.isExpanded(group_proxy) is False
```
**Why cite this?** It confirms (a) `pytest-qt`'s `qtbot` is the established harness, (b) `tree.isExpanded(proxy_idx)` is the read primitive, (c) the four filter-change paths (which Phase 55 must NOT regress) are testable directly via `setText`/`clear`. Phase 55 must keep this test green.

### New test shape (Phase 55 BUG-06)
```python
# To be added under "Phase 55 / BUG-06" header in tests/test_station_list_panel.py
def test_refresh_model_preserves_user_expanded_groups(qtbot):
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)
    # User expands SomaFM
    soma_proxy = panel._proxy.index(0, 0)  # alpha-first; assert via DisplayRole if order differs
    panel.tree.expand(soma_proxy)
    assert panel.tree.isExpanded(soma_proxy) is True
    # Simulate save -> refresh
    panel.refresh_model()
    # SomaFM remains expanded
    soma_proxy_after = panel._proxy.index(0, 0)
    assert panel.tree.isExpanded(soma_proxy_after) is True

def test_refresh_model_preserves_user_collapsed_groups(qtbot):
    # ... user collapses, save, assert still collapsed
    ...

def test_refresh_model_expands_brand_new_provider_group(qtbot):
    # User has SomaFM, DI.fm. Both collapsed. Save creates a new station with provider="JazzFM".
    # JazzFM appears as a third group, expanded. SomaFM and DI.fm stay collapsed.
    ...

def test_refresh_model_does_not_call_sync_tree_expansion(qtbot, monkeypatch):
    """SC enforcement: refresh_model() must not invoke _sync_tree_expansion()."""
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)
    calls = []
    monkeypatch.setattr(
        panel, "_sync_tree_expansion", lambda: calls.append(True)
    )
    panel.refresh_model()
    assert calls == [], "refresh_model must NOT call _sync_tree_expansion (BUG-06)"

def test_filter_change_still_calls_sync_tree_expansion(qtbot, monkeypatch):
    """Regression-lock: filter-change paths still drive auto-expand (CONTEXT D-05)."""
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)
    calls = []
    monkeypatch.setattr(panel, "_sync_tree_expansion", lambda: calls.append(True))
    panel._search_box.setText("a")
    assert calls, "search-changed must still drive _sync_tree_expansion"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `refresh_model()` calls `_sync_tree_expansion()` to bulk-set expansion after model reset | `refresh_model()` captures + restores user state; filter-change handlers still call `_sync_tree_expansion()` | This phase (Phase 55) | Save events stop reshaping the tree. Two paths, two responsibilities. |
| Phase 50 worked *around* the bug by adding `refresh_recent()` to avoid `refresh_model()` on the recently-played update path | Phase 55 fixes the underlying defect — future callers don't need to choose between "refresh the tree" and "preserve user state" | This phase (Phase 55) | `refresh_recent()` becomes a narrowed-scope method (recent-only) rather than an escape hatch from a broken refresh. |

**Deprecated/outdated:** None — `_sync_tree_expansion()` is not deprecated; it remains the correct primitive for the filter-change path. The change is *which paths call it*, not what it does.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BUG-06 | Saving an edit in `EditStationDialog` preserves the open/closed state of expandable sections (does not collapse all open sections on save) | Capture/restore design in §"Architecture Patterns" + Pattern 1 + Pattern 2; verified Qt behavior in §"Common Pitfalls" #4. SC #1/#2/#3 testable via §"Code Examples" → "New test shape". |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `tree.expand(invalid_proxy_idx)` is a silent no-op (no exception). Confirmed by Qt docs that `setExpanded(QModelIndex)` returns early when the index is invalid. [VERIFIED: docs + community consensus on Qt forums; not directly cited.] | Pitfall 2 | If wrong, restore would crash under active filter on a filtered-out provider. Mitigation: explicit `if proxy_idx.isValid():` guard regardless. **Recommend: keep the guard even if Qt is permissive — explicit is safer.** |
| A2 | Recommend storing `provider_name` as a raw field on `_TreeNode` (vs. parsing label suffix). | Pattern 1 / Pitfall 1 | Low risk — adding a dataclass field is mechanical. The alternative (rsplit) is fragile for provider names containing `" (N)"`. |

## Open Questions

1. **Where exactly should the new helpers live?**
   - What we know: `_capture_expanded_provider_names` and `_restore_expanded_provider_names` belong on `StationListPanel` (private).
   - What's unclear: Should the brand-new detection happen inside `_restore_*` (taking both `expanded_pre` and `all_pre` sets), or should `refresh_model` compute `all_pre` inline and pass only one set?
   - Recommendation: Capture returns a tuple `(expanded_names: set[str], all_names: set[str])`. Restore takes both. Keeps the call shape explicit and testable.

2. **Does `select_station` (called from `_on_save_new_station` lambda at `main_window.py:451`) interact with the new restore loop?**
   - What we know: `select_station` runs AFTER `refresh_model` returns, expands the destination provider, and selects the new station.
   - What's unclear: If the user had the destination collapsed pre-save, capture says "collapsed" → restore leaves it collapsed → `select_station` then expands it → user sees the destination expanded.
   - Recommendation: This is correct behavior — the user just created a new station, so jumping to it (with its parent expanded) is expected. **No conflict with D-07** ("station moved into a previously-collapsed group does NOT auto-expand the destination"): D-07 is about edits that move stations between providers, not new-station creation. The new-station flow at `main_window.py:441-458` is a separate code path that *deliberately* expands via `select_station`. **No code change needed.**

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PySide6 | All Qt code | ✓ | >=6.11 (locked in `pyproject.toml`) | — |
| pytest | Test execution | ✓ | >=9 (test extra) | — |
| pytest-qt | `qtbot` fixture for headless tests | ✓ | >=4 (test extra) | — |
| Qt offscreen platform plugin | Headless test runs | ✓ | bundled with PySide6 | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

All required tooling is already installed and exercised by the existing test suite (e.g., `tests/test_station_list_panel.py:73-534`).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=9 + pytest-qt >=4 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (lines 50-54) — `testpaths = ["tests"]`; no separate `pytest.ini` |
| Quick run command | `pytest tests/test_station_list_panel.py -x -k "phase_55 or refresh_model or expansion or BUG-06"` |
| Full suite command | `pytest tests/` |
| Headless harness | `tests/conftest.py` already sets `QT_QPA_PLATFORM=offscreen` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUG-06 / SC #1 | Sections expanded before Save remain expanded after Save | unit (pytest-qt) | `pytest tests/test_station_list_panel.py::test_refresh_model_preserves_user_expanded_groups -x` | ❌ Wave 0 (new test) |
| BUG-06 / SC #2 | Sections collapsed before Save remain collapsed after Save | unit (pytest-qt) | `pytest tests/test_station_list_panel.py::test_refresh_model_preserves_user_collapsed_groups -x` | ❌ Wave 0 (new test) |
| BUG-06 / SC #3 | Initial open state on freshly-launched dialog is unchanged (all groups collapsed at construction) | unit (pytest-qt) | `pytest tests/test_station_list_panel.py::test_provider_groups_collapsed_after_construction -x` | ✅ Already exists at line 103 |
| BUG-06 / D-06 | Brand-new provider group created by save defaults to expanded | unit (pytest-qt) | `pytest tests/test_station_list_panel.py::test_refresh_model_expands_brand_new_provider_group -x` | ❌ Wave 0 (new test) |
| BUG-06 / D-07 | Destination group of cross-provider move stays in captured state (collapsed if was collapsed) | unit (pytest-qt) | `pytest tests/test_station_list_panel.py::test_refresh_model_preserves_collapsed_destination_on_cross_provider_move -x` | ❌ Wave 0 (new test) |
| BUG-06 / D-04 | Refresh under active search filter preserves the captured manual state (does not call expandAll) | unit (pytest-qt) | `pytest tests/test_station_list_panel.py::test_refresh_model_preserves_state_under_active_filter -x` | ❌ Wave 0 (new test) |
| BUG-06 / D-03 evidence | `refresh_model` does NOT call `_sync_tree_expansion` | unit (pytest-qt + monkeypatch spy) | `pytest tests/test_station_list_panel.py::test_refresh_model_does_not_call_sync_tree_expansion -x` | ❌ Wave 0 (new test) |
| BUG-06 / D-05 regression-lock | Filter-change handlers still call `_sync_tree_expansion` | unit (pytest-qt + monkeypatch spy) | `pytest tests/test_station_list_panel.py::test_filter_change_still_calls_sync_tree_expansion -x` | ❌ Wave 0 (new test) |
| BUG-06 / Pre-existing regression | Filter-change still drives expandAll/collapseAll round-trip | unit (pytest-qt) | `pytest tests/test_station_list_panel.py::test_provider_groups_expand_when_search_active -x` | ✅ Already exists at line 113 |
| BUG-06 / Phase 50 regression-lock | `refresh_recent` does not touch tree | unit (pytest-qt) | `pytest tests/test_station_list_panel.py::test_refresh_recent_does_not_touch_tree -x` | ✅ Already exists at line 523 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_station_list_panel.py -x` (~1-3s)
- **Per wave merge:** `pytest tests/test_station_list_panel.py tests/test_main_window_integration.py -x` (~10s)
- **Phase gate:** `pytest tests/` full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_station_list_panel.py` — add Phase 55 / BUG-06 test header + 7 new tests listed in the table above (5 behavioral, 2 spy-based)
- [ ] No new conftest fixtures required — existing `_sample_repo()` and `make_station()` factories cover all cases. For brand-new-group / cross-provider-move scenarios, mutate the `FakeRepo._stations` list before calling `panel.refresh_model()` (mirrors Phase 50 pattern at line 512: `repo._recent = [new_top] + repo._recent`).
- [ ] Framework install: not needed — `pytest-qt>=4` already in `pyproject.toml:29`.

### Evidence-based validation requirements (Nyquist)

Two assertions are *behaviorally invisible* but architecturally critical:

1. **`refresh_model` does NOT invoke `_sync_tree_expansion`.** Without this assertion, a future contributor could re-introduce the bug by adding the call back "for good measure" while preserving SC #1 and SC #2 by accident (e.g., if save happens with no filter active and all groups happen to be collapsed). The spy-based test in §"Code Examples" → `test_refresh_model_does_not_call_sync_tree_expansion` is the lock. **Required.**
2. **Filter-change handlers DO invoke `_sync_tree_expansion`.** Symmetric regression-lock — without it, a refactor "simplifying" the panel could remove the call from `_on_search_changed` etc., silently breaking CONTEXT D-05. The spy-based test `test_filter_change_still_calls_sync_tree_expansion` is the lock. **Required.**

These are the two evidence-based assertions surfaced by Nyquist that aren't obvious from the success criteria alone.

## Scope-Creep Landmines

Things in `station_list_panel.py:270-462` that are tempting to "clean up" but are **out of scope** for BUG-06:

1. **`_sync_tree_expansion` could become two methods** (`_expand_all_groups` + `_collapse_all_groups`). Tempting refactor; not in scope. Keep it as one method called from four sites.
2. **`_populate_recent` and `_build_chip_rows` are still called from `refresh_model`** (lines 318-319). They run *after* the model reset. CONTEXT D-04 §Claude's Discretion confirms they don't touch tree expansion — leave them untouched.
3. **`_build_chip_rows` re-builds chips on every refresh.** This causes chip-state to be lost (a checked provider chip becomes unchecked after save). Tempting to fix as part of BUG-06; **out of scope** — different defect, different requirement, no requirement ID. If Kyle wants chip state preserved, that's a future phase.
4. **The `# ----- Population` comment at line 309** (then a duplicate `# Public refresh API` at 311). Cosmetic only. Don't touch.
5. **`refresh_model` could accept `stations: list[Station] | None = None`** to skip a redundant `repo.list_stations()` round-trip when caller already has the list. Tempting; **out of scope** — no caller benefits today.
6. **`StationFilterProxyModel` could expose `is_filter_active_for_provider(name)`** to short-circuit the proxy mapping check during restore. Tempting; **out of scope** — `proxy_idx.isValid()` is sufficient and standard.

## Sources

### Primary (HIGH confidence)
- `musicstreamer/ui_qt/station_list_panel.py` (full file) — capture/restore site, filter handlers, tree construction, `select_station` precedent.
- `musicstreamer/ui_qt/station_tree_model.py` (full file) — provider grouping, label-suffix mutation, `refresh()`/`beginResetModel`/`endResetModel`.
- `musicstreamer/ui_qt/station_filter_proxy.py` (full file) — `filterAcceptsRow` recursive child check, `mapFromSource` invalid-index behavior for filtered-out rows.
- `musicstreamer/ui_qt/main_window.py:441-563` — five `_refresh_station_list()` call sites + lambda `select_station` chaining.
- `tests/test_station_list_panel.py` (full file) — existing test patterns, fakes, conftest pytest-qt usage.
- `tests/conftest.py` — `QT_QPA_PLATFORM=offscreen` headless setup.
- `pyproject.toml` — pytest-qt + PySide6 locked versions.
- `.planning/phases/55-edit-station-preserves-section-state/55-CONTEXT.md` — locked decisions (D-01..D-07).
- `.planning/phases/50-recently-played-live-update/50-CONTEXT.md` — precedent (Phase 50 worked around the bug Phase 55 fixes).

### Secondary (MEDIUM confidence)
- [Qt 6 — QAbstractItemModel::endResetModel](https://doc.qt.io/qt-6/qabstractitemmodel.html#endResetModel) — confirms persistent model indexes are invalidated on reset.
- [Qt 6 — QSortFilterProxyModel::mapFromSource](https://doc.qt.io/qt-6/qsortfilterproxymodel.html#mapFromSource) — does not explicitly state the invalid-index behavior for filtered-out rows, but...
- [QSortFilterProxyModel source code (codebrowser.dev)](https://codebrowser.dev/qt5/qtbase/src/corelib/itemmodels/qsortfilterproxymodel.cpp.html) — confirms via implementation: filtered-out rows get `proxy_row=-1` → invalid `QModelIndex`.
- [Qt Centre Forum — QTreeView expansion after model reset](https://www.qtcentre.org/threads/61009-QTreeView-expansion-after-model-reset) — community consensus that `endResetModel` collapses all view-side expansion; capture/restore is the standard pattern.
- [Qt Forum — How do you save and restore the state of QTreeView?](https://forum.qt.io/topic/131650/how-do-you-save-and-restore-the-state-of-qtreeview) — same pattern, save list of expanded identifiers before reset, re-expand after.

### Tertiary (LOW confidence)
- None. The Qt model-view APIs in scope here are stable since Qt 5; no LOW-confidence claims rely on community-only sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies already locked in `pyproject.toml`, exercised by existing tests.
- Architecture: HIGH — pattern mirrors existing `select_station` precedent; CONTEXT.md fully prescribes the design.
- Pitfalls: HIGH — four pitfalls each verified against current source (label suffix at `station_tree_model.py:84`, filterAcceptsRow at `station_filter_proxy.py:60-73`, Qt docs on endResetModel).
- Tests: HIGH — pytest-qt + offscreen platform already wired; existing test file has the exact shape needed for new cases.

**Research date:** 2026-05-01
**Valid until:** 2026-05-31 (30 days — Qt 6 model-view APIs are stable; PySide6 minor versions do not change this surface)

## RESEARCH COMPLETE

CONTEXT.md locks the design; research confirms Qt API behavior (persistent indexes invalidated on `endResetModel`; `mapFromSource` returns invalid `QModelIndex` for filtered-out rows), surfaces the label-suffix pitfall (provider names need a new `provider_name_at` accessor — not display-text parsing), and maps all eight test cases to BUG-06 SC #1/#2/#3 + CONTEXT D-03/D-04/D-05/D-06/D-07.
