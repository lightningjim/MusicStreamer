# Phase 55: Edit Station Preserves Section State — Pattern Map

**Mapped:** 2026-05-01
**Files analyzed:** 3 (2 modified source + 1 modified test)
**Analogs found:** 3 / 3 (all in-file — single-file phase, all analogs colocated with the changes)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/ui_qt/station_list_panel.py` (modify `refresh_model`, add 2 helpers) | view (Qt panel widget) | event-driven (refresh-after-mutation, capture/restore around model reset) | `StationListPanel.select_station` (same file, lines 341-365) | **exact** — same source-walk + proxy-map pattern, same widget, same class |
| `musicstreamer/ui_qt/station_tree_model.py` (add `provider_name_at` accessor + `_TreeNode.provider_name` field) | model (custom `QAbstractItemModel`) | request-response (row-indexed scalar accessor) | `StationTreeModel.station_for_index` (same file, lines 53-59) | **exact** — same scalar-from-row accessor shape, same model |
| `tests/test_station_list_panel.py` (add 8 Phase 55 / BUG-06 tests) | test (pytest-qt unit tests) | request-response (assertions on view state) | `test_provider_groups_expand_when_search_active` (lines 113-132) + `test_refresh_recent_does_not_touch_tree` (lines 523-534) | **exact** — same harness, same `_sample_repo()` factory, same `tree.isExpanded(proxy_idx)` primitive |

> **Note on path discrepancy.** Both 55-CONTEXT and 55-VALIDATION refer to `musicstreamer/tests/test_station_list_panel.py`, but the on-disk file lives at `tests/test_station_list_panel.py` (project root, not under the package). The planner should use the on-disk path. `tests/conftest.py` already sets `QT_QPA_PLATFORM=offscreen` so qtbot works headless — no conftest changes needed.

---

## Pattern Assignments

### `musicstreamer/ui_qt/station_list_panel.py` — `refresh_model()` rewrite + 2 new helpers

**Analog:** `StationListPanel.select_station` (same file, `station_list_panel.py:341-365`)

**Why this analog:** `select_station` already does the exact source-model walk + `proxy.mapFromSource(source_idx)` + `tree.expand(proxy_idx)` triple that capture/restore needs. It is the established precedent in the very same class. Mirror it for the new helpers.

#### Imports pattern (lines 17-49)

The file already imports everything the new helpers need — no new imports required:

```python
# musicstreamer/ui_qt/station_list_panel.py:17-19
from __future__ import annotations

from PySide6.QtCore import QEvent, QModelIndex, QSize, Qt, Signal
```

`QModelIndex` is already imported and used in `_on_tree_activated` / `_on_recent_clicked`. The new helpers need no additional imports.

#### Source-walk + proxy-map (the exact pattern to mirror)

```python
# musicstreamer/ui_qt/station_list_panel.py:355-365 (select_station body)
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

**What to copy for capture/restore:** The outer loop `for prov_row in range(self.model.rowCount()): prov_idx = self.model.index(prov_row, 0)` is *exactly* what the new helpers need (provider rows live at the top level of the source model). Skip the inner `for child_row` loop — capture/restore operates only on provider rows. After getting `prov_idx`, call `self._proxy.mapFromSource(prov_idx)` and read/write expansion via `self.tree.isExpanded(proxy_idx)` / `self.tree.expand(proxy_idx)`.

#### The current `refresh_model` (the call site to wrap)

```python
# musicstreamer/ui_qt/station_list_panel.py:314-319 (CURRENT — the bug)
def refresh_model(self) -> None:
    """Reload station tree and recently played after external changes (edit/delete/import)."""
    self.model.refresh(self._repo.list_stations())
    self._sync_tree_expansion()      # <-- D-03: REMOVE this line (the bug)
    self._populate_recent()          # <-- keep
    self._build_chip_rows()          # <-- keep
```

**Target shape after the fix (planner's pseudocode — final form is implementer's call):**

```python
def refresh_model(self) -> None:
    """Reload station tree and recently played after external changes (edit/delete/import).

    Preserves user-set per-provider expand/collapse state across model.refresh()
    (BUG-06 / Phase 55). New provider groups created by the refresh default to
    expanded (CONTEXT D-06). Filter-change paths still drive expansion via
    _sync_tree_expansion (CONTEXT D-05) — that wiring is untouched.
    """
    expanded_pre, all_pre = self._capture_expanded_provider_names()
    self.model.refresh(self._repo.list_stations())
    self._restore_expanded_provider_names(expanded_pre, all_pre)
    self._populate_recent()
    self._build_chip_rows()
```

#### `_sync_tree_expansion` (UNCHANGED — keep, just decoupled from refresh)

```python
# musicstreamer/ui_qt/station_list_panel.py:333-339
def _sync_tree_expansion(self) -> None:
    # Expand groups when a filter is active so matches are visible;
    # collapse them otherwise so the full station list is scannable.
    if self._proxy.has_active_filter():
        self.tree.expandAll()
    else:
        self.tree.collapseAll()
```

**Do not modify this method.** It is still called by the four filter-change handlers (lines 426, 436, 446, 462) — that wiring is the D-05 regression-lock contract.

#### Filter-change handlers (UNCHANGED — regression-lock target)

```python
# musicstreamer/ui_qt/station_list_panel.py:424-446 (the four call sites that MUST keep calling _sync_tree_expansion)
def _on_search_changed(self, text: str) -> None:
    self._proxy.set_search(text)
    self._sync_tree_expansion()

def _on_provider_chip_clicked(self, btn: QPushButton) -> None:
    ...
    self._proxy.set_providers(provider_set)
    self._sync_tree_expansion()

def _on_tag_chip_clicked(self, btn: QPushButton) -> None:
    ...
    self._proxy.set_tags(tag_set)
    self._sync_tree_expansion()
```

```python
# musicstreamer/ui_qt/station_list_panel.py:453-462 (clear-all also calls _sync_tree_expansion)
def _clear_all_filters(self) -> None:
    self._search_box.clear()
    for btn in self._provider_chip_group.buttons():
        btn.setChecked(False)
        self._set_chip_state(btn, False)
    for btn in self._tag_chip_group.buttons():
        btn.setChecked(False)
        self._set_chip_state(btn, False)
    self._proxy.clear_all()
    self._sync_tree_expansion()
```

#### Proxy-validity guard (Pitfall #2)

`StationFilterProxyModel.filterAcceptsRow` returns `False` for provider rows whose children are all filtered out. In that case `proxy.mapFromSource(prov_idx)` returns an invalid `QModelIndex`. The restore loop must guard:

```python
# musicstreamer/ui_qt/station_filter_proxy.py:60-73 (why the guard is needed)
def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
    source = self.sourceModel()
    if source is None:
        return True
    idx = source.index(source_row, 0, source_parent)
    node = idx.internalPointer()
    if node is None:
        return True
    if node.kind == "provider":
        # Show provider group if any child station passes filter (Pitfall 2 fix)
        for i in range(source.rowCount(idx)):
            if self.filterAcceptsRow(i, idx):
                return True
        return False                       # <-- causes mapFromSource to return invalid
    ...
```

The new `_restore_expanded_provider_names` must include `if proxy_idx.isValid(): self.tree.expand(proxy_idx)` to handle this case cleanly.

---

### `musicstreamer/ui_qt/station_tree_model.py` — `provider_name_at` accessor + `_TreeNode.provider_name` field

**Analog:** `StationTreeModel.station_for_index` (same file, `station_tree_model.py:53-59`)

**Why this analog:** `station_for_index` is the existing scalar-from-index accessor on the same model. The new `provider_name_at(row)` is its sibling — same shape, same return-`None`-on-miss semantics, same file.

#### Existing accessor pattern (the shape to mirror)

```python
# musicstreamer/ui_qt/station_tree_model.py:53-59
def station_for_index(self, index: QModelIndex) -> Optional[Station]:
    if not index.isValid():
        return None
    node: _TreeNode = index.internalPointer()
    if node is None:
        return None
    return node.station if node.kind == "station" else None
```

**Target shape for `provider_name_at(row: int) -> str | None`:**

```python
def provider_name_at(self, row: int) -> str | None:
    if row < 0 or row >= len(self._root.children):
        return None
    node = self._root.children[row]
    return node.provider_name if node.kind == "provider" else None
```

#### `_TreeNode` dataclass — where to add the new field

```python
# musicstreamer/ui_qt/station_tree_model.py:26-32 (CURRENT)
@dataclass
class _TreeNode:
    kind: str  # "root" | "provider" | "station"
    label: str
    parent: Optional["_TreeNode"] = None
    children: list["_TreeNode"] = field(default_factory=list)
    station: Optional[Station] = None
```

**Target:** add `provider_name: Optional[str] = None` as a new field. Keep it `None` for `kind="root"` and `kind="station"` nodes; populate the raw name only for `kind="provider"` nodes.

#### `_populate` — where to set the new field (Pitfall #1: do NOT parse the label suffix)

```python
# musicstreamer/ui_qt/station_tree_model.py:65-84 (CURRENT)
def _populate(self, stations: list[Station]) -> None:
    groups: dict[str, _TreeNode] = {}
    for st in stations:
        pname = st.provider_name or "Ungrouped"
        grp = groups.get(pname)
        if grp is None:
            grp = _TreeNode(kind="provider", label=pname, parent=self._root)
            self._root.children.append(grp)
            groups[pname] = grp
        grp.children.append(
            _TreeNode(
                kind="station",
                label=st.name,
                parent=grp,
                station=st,
            )
        )
    # D-04: append (N) count suffix to each provider label
    for grp in self._root.children:
        grp.label = f"{grp.label} ({len(grp.children)})"
```

**Target change:** when constructing the provider node, also set `provider_name=pname`:

```python
grp = _TreeNode(
    kind="provider",
    label=pname,
    parent=self._root,
    provider_name=pname,   # <-- NEW: raw name, never gets the " (N)" suffix
)
```

The label-suffix mutation at line 84 stays — it touches `grp.label`, not `grp.provider_name`. The new `provider_name` is the unlabelled, suffix-free, round-tripable key for capture/restore.

#### `refresh()` is already correct (no change needed)

```python
# musicstreamer/ui_qt/station_tree_model.py:47-51 — DO NOT MODIFY
def refresh(self, stations: list[Station]) -> None:
    self.beginResetModel()
    self._root = _TreeNode(kind="root", label="")
    self._populate(stations)
    self.endResetModel()
```

This is already wrapped correctly with `beginResetModel`/`endResetModel`. RESEARCH §"Standard Stack" Alternatives Considered table confirms persistent indexes are invalidated on `endResetModel`; that is *why* the capture/restore wraps this call from outside.

---

### `tests/test_station_list_panel.py` — 8 new Phase 55 / BUG-06 tests

**Analogs:** Two — one for the expand/collapse-state read pattern, one for the post-mutation refresh pattern.

#### Analog 1 — read expansion state via proxy index

```python
# tests/test_station_list_panel.py:113-132 (test_provider_groups_expand_when_search_active)
def test_provider_groups_expand_when_search_active(qtbot):
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)

    panel._search_box.setText("a")

    # Any group that survives the filter should be expanded so matches are visible
    any_expanded = False
    for row in range(panel._proxy.rowCount()):
        group_proxy = panel._proxy.index(row, 0)
        if panel.tree.isExpanded(group_proxy):
            any_expanded = True
            break
    assert any_expanded is True

    # Clearing the search collapses them again
    panel._search_box.clear()
    for row in range(panel._proxy.rowCount()):
        group_proxy = panel._proxy.index(row, 0)
        assert panel.tree.isExpanded(group_proxy) is False
```

**Pattern to copy:**
- Iterate `panel._proxy.rowCount()` and read `panel.tree.isExpanded(group_proxy)` — this is the canonical way to read provider-group expansion in tests.
- Drive panel state via the public input widgets (`panel._search_box.setText(...)`, `panel._search_box.clear()`) — pytest-qt's `qtbot` does not need to simulate keystrokes for this case.
- All Phase 55 SC #1/#2/D-04/D-06/D-07 tests follow this read-shape: set up a state, call `panel.refresh_model()`, then iterate proxy rows and assert `tree.isExpanded(...)` matches the expected per-group preservation/expansion.

#### Analog 2 — post-mutation refresh test (Phase 50 precedent)

```python
# tests/test_station_list_panel.py:504-520 (test_refresh_recent_updates_list — Phase 50)
def test_refresh_recent_updates_list(qtbot):
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    # Simulate a different station becoming the most recently played.
    # Pitfall #3: mutate repo._recent BEFORE calling refresh_recent —
    # list_recently_played returns a snapshot of _recent at call time.
    new_top = make_station(99, "New Top Station", "TestFM")
    repo._recent = [new_top] + repo._recent

    panel.refresh_recent()

    assert panel.recent_view.model().rowCount() == 3
    top_station = panel.recent_view.model().index(0, 0).data(Qt.UserRole)
    assert isinstance(top_station, Station)
    assert top_station.id == 99
```

```python
# tests/test_station_list_panel.py:523-534 (test_refresh_recent_does_not_touch_tree — Phase 50 SC #3)
def test_refresh_recent_does_not_touch_tree(qtbot):
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    # SC #3: refresh_recent must not rebuild the provider tree.
    # If model.refresh() were called, rowCount would be re-derived from repo.list_stations().
    row_count_before = panel.tree.model().rowCount()

    panel.refresh_recent()

    assert panel.tree.model().rowCount() == row_count_before
```

**Pattern to copy:**
- **Mutate `repo._stations` directly** (mirror line 513's `repo._recent = [new_top] + repo._recent` pattern) to simulate save/edit/delete creating, removing, or moving stations between providers. The `FakeRepo.list_stations()` at line 41 returns `list(self._stations)` — mutating `_stations` in-place is the established way to drive `refresh_model` through different scenarios.
- **For brand-new provider group tests (D-06):** append a `make_station(99, "New", "BrandNewProvider")` to `repo._stations` between the user-expansion setup step and the `panel.refresh_model()` call.
- **For cross-provider move tests (D-07):** mutate an existing station's `provider_name` in-place: e.g., `repo._stations[0].provider_name = "DI.fm"` to move "Groove Salad" out of SomaFM into DI.fm.

#### Spy-based test pattern (D-03 + D-05 evidence — Nyquist-required per RESEARCH §Validation Architecture)

There is no exact pre-existing analog for the spy-based tests in this file. Use `monkeypatch` from pytest's standard fixture set (already implicit in the project's `pyproject.toml` `[tool.pytest.ini_options]`). RESEARCH §"Code Examples" gives the exact target shape:

```python
# RESEARCH-recommended shape (no exact precedent in the file — adopt verbatim)
def test_refresh_model_does_not_call_sync_tree_expansion(qtbot, monkeypatch):
    """SC enforcement: refresh_model() must not invoke _sync_tree_expansion()."""
    panel = StationListPanel(_sample_repo())
    qtbot.addWidget(panel)
    calls = []
    monkeypatch.setattr(panel, "_sync_tree_expansion", lambda: calls.append(True))
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

#### Test header location — where to insert the new block

Existing file ends at line 535 with the Phase 50 / BUG-01 block (lines 500-534). **Append the Phase 55 / BUG-06 block at line 535+**, mirroring the comment-banner style used for Phase 50:

```python
# tests/test_station_list_panel.py:500-502 (Phase 50 comment-banner — copy this style)
# ----------------------------------------------------------------------
# Phase 50 / BUG-01: refresh_recent() public API
# ----------------------------------------------------------------------
```

For Phase 55, use:
```python
# ----------------------------------------------------------------------
# Phase 55 / BUG-06: refresh_model preserves provider expand/collapse
# ----------------------------------------------------------------------
```

---

## Shared Patterns

### Source-walk + proxy-map (Pattern 1 from RESEARCH)

**Source:** `StationListPanel.select_station` (`musicstreamer/ui_qt/station_list_panel.py:355-365`).
**Apply to:** Both new helpers `_capture_expanded_provider_names` and `_restore_expanded_provider_names`.

```python
# Skeleton (excerpt from select_station — adapt the outer-loop only for capture/restore)
for prov_row in range(self.model.rowCount()):
    prov_idx = self.model.index(prov_row, 0)
    proxy_idx = self._proxy.mapFromSource(prov_idx)
    if not proxy_idx.isValid():
        continue                                    # filtered out — view cannot show it expanded
    # capture: was_expanded = self.tree.isExpanded(proxy_idx)
    # restore: self.tree.expand(proxy_idx)
```

**Rule:** Walk the **source model** (always full data shape, no filter occlusion); convert to **proxy index** at the view boundary; guard against invalid proxy indices for filtered-out rows. CONTEXT §"Integration Points" line 106 mandates this exact mapping pattern; RESEARCH Pitfall #3 confirms walking the proxy instead is an anti-pattern.

### Provider-name as stable key (Pattern 2 from RESEARCH)

**Source:** `_TreeNode.provider_name` (NEW field, `station_tree_model.py`) read via `StationTreeModel.provider_name_at(row)` (NEW accessor).
**Apply to:** Both helpers' capture set + the brand-new-detection set difference.

**Rule:** Use the raw `provider_name` field, never `idx.data(Qt.DisplayRole)` (which returns the `"Foo (3)"` labelled form — RESEARCH Pitfall #1). Set difference `new_names - all_pre` is the brand-new-group detector for D-06.

### pytest-qt headless harness (existing — unchanged)

**Source:** `tests/conftest.py` (sets `QT_QPA_PLATFORM=offscreen`) — already in place.
**Apply to:** Every Phase 55 test. Use `qtbot` fixture and `qtbot.addWidget(panel)` exactly as the existing tests do (`tests/test_station_list_panel.py:74-75, 87-88, 93-94, 104-105, 114-115, ...`).

### `FakeRepo` mutation pattern for refresh testing (existing — Phase 50 precedent)

**Source:** `tests/test_station_list_panel.py:512-513` — `repo._recent = [new_top] + repo._recent` mutate-then-call shape.
**Apply to:** All eight Phase 55 tests that need to drive `refresh_model()` through a state change. Mutate `repo._stations` (append for D-06 brand-new group; mutate `.provider_name` in-place for D-07 cross-provider move; remove for delete-path coverage); then call `panel.refresh_model()`; then assert.

---

## No Analog Found

Files with no close match in the codebase:

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| Spy-based test of `_sync_tree_expansion` non-invocation | test (monkeypatch-based behavioral lock) | request-response | No existing test in `test_station_list_panel.py` uses `monkeypatch.setattr` on a panel method. Adopt verbatim from RESEARCH §"Code Examples" lines 288-307 (provided fully formed). pytest's `monkeypatch` fixture is implicit project-wide via pytest defaults. |

---

## Key Patterns Identified

- **All capture/restore should mirror `select_station`'s outer-loop shape.** Walk source model rows, map to proxy at the view boundary, guard `isValid()`. Same class, same file, same precedent.
- **`provider_name_at` is the sibling of `station_for_index`.** Both are `model.X(...)` scalar-from-row accessors that return `None` on a non-matching kind. New accessor matches the shape exactly.
- **Tests drive `refresh_model` by mutating `FakeRepo._stations` in-place.** Mirrors Phase 50's `repo._recent = [...]` shape. No new fixtures, no new fakes.
- **Two distinct contracts (Boundary A vs Boundary B).** `refresh_model` MUST NOT call `_sync_tree_expansion` (D-03 spy-lock). The four filter-change handlers MUST keep calling it (D-05 spy-lock). Both contracts get a dedicated spy-based pytest-qt test.
- **`_TreeNode.provider_name` is the round-tripable key.** Never parse `" (N)"` off the label (Pitfall #1). The label suffix mutation at `station_tree_model.py:84` stays untouched — the new field bypasses it cleanly.

---

## Metadata

**Analog search scope:**
- `musicstreamer/ui_qt/station_list_panel.py` (full file, 557 lines)
- `musicstreamer/ui_qt/station_tree_model.py` (full file, 156 lines)
- `musicstreamer/ui_qt/station_filter_proxy.py` (full file, 82 lines)
- `tests/test_station_list_panel.py` (full file, 535 lines)
- `.planning/phases/55-edit-station-preserves-section-state/55-CONTEXT.md`
- `.planning/phases/55-edit-station-preserves-section-state/55-RESEARCH.md`
- `.planning/phases/55-edit-station-preserves-section-state/55-UI-SPEC.md`
- `.planning/phases/55-edit-station-preserves-section-state/55-VALIDATION.md`

**Files scanned:** 8.

**Pattern extraction date:** 2026-05-01.

**Path correction:** Both 55-CONTEXT and 55-VALIDATION reference `musicstreamer/tests/test_station_list_panel.py`; the on-disk path is `tests/test_station_list_panel.py` (project root). Planner should use the on-disk path.
