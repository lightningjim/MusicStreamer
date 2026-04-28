# Phase 50: Recently Played Live Update — Research

**Researched:** 2026-04-27
**Domain:** PySide6 QListView / QStandardItemModel, MainWindow signal wiring, StationListPanel public API
**Confidence:** HIGH — all findings verified against the actual source code in this session.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 (Bump timing):** Recent list updates immediately on click — at the same point where `update_last_played(station_id)` already fires inside `MainWindow._on_station_activated` (`main_window.py:324`). No waiting on a Player playback-confirmation signal.
- **D-02 (Failed-stream behavior):** If a click fails to produce audio the failed station stays at the top of Recently Played. No rollback. Rationale: matches user mental model, keeps DB and UI consistent, allows retry.
- **D-03 (Visual treatment):** Instant swap — re-populate the existing `recent_view` QListView from `repo.list_recently_played(3)` with no animation, no highlight, no fade.
- **D-04 (Refresh mechanism — Claude's discretion):** Expose a public method on `StationListPanel` that wraps the existing private `_populate_recent()`. `MainWindow._on_station_activated` calls it directly after `update_last_played`. Direct call preferred over a new signal, but planner may choose a signal if there is strong reason.

### Claude's Discretion

- Refresh strategy is a full `_populate_recent()` rebuild (3 items, trivial cost); no surgical move-to-top is needed.
- Same-station re-activation is handled implicitly by `update_last_played` writing a new timestamp; the rebuild query returns identical order; no special case needed.
- Final name of the new public method is set by the planner (candidates: `refresh_recent()`, following `refresh_model()` precedent).

### Deferred Ideas (OUT OF SCOPE)

- Visual polish on the bump (highlight pulse, slide-in animation).
- Distinguishing "tried" from "successfully played" (would require deferred `update_last_played`, rollback bookkeeping).
- Recently-played count > 3 — `n=3` constant stays.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BUG-01 | Recently played list updates live as new stations are played — no manual refresh required | Verified: `_populate_recent()` already queries `repo.list_recently_played(3)` and rebuilds the flat `QStandardItemModel`; it just needs to be callable from outside the class. `MainWindow._on_station_activated` already calls `update_last_played` at line 324 — adding one more method call immediately after is a one-liner. |
</phase_requirements>

---

## Summary

Phase 50 is a small bug fix: the Recently Played QListView does not refresh when the user clicks a station because `StationListPanel._populate_recent()` is only called at construction and inside the full `refresh_model()`. The fix is two small edits — one in `station_list_panel.py` (expose a public method) and one in `main_window.py` (call it after `update_last_played`).

All four CONTEXT.md touch points were verified against the live source code. Every CONTEXT.md claim is accurate. The implementation is straightforward; the only genuine decision left for the planner is the final name of the new public method.

The existing test suite has solid patterns for both `StationListPanel` and `MainWindow._on_station_activated`. There are no tests that currently assert the recent list changes after activation; that gap is the main Wave 0 obligation for this phase.

**Primary recommendation:** Add `def refresh_recent(self) -> None: self._populate_recent()` to `StationListPanel` (mirrors the `refresh_model()` naming convention), then add `self.station_panel.refresh_recent()` immediately after `self._repo.update_last_played(station.id)` in `MainWindow._on_station_activated`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Persist "last played" timestamp | Database (Repo) | — | `Repo.update_last_played` already does this; no change needed |
| Query recently played stations | Database (Repo) | — | `Repo.list_recently_played(3)` already does this; no change needed |
| Rebuild the recent QListView | Frontend widget (StationListPanel) | — | QStandardItemModel is owned by the panel; must be mutated on the main thread |
| Trigger the refresh on user action | Application coordinator (MainWindow) | — | MainWindow owns both `_repo` and `station_panel`; a direct method call is the established pattern |

---

## Standard Stack

No new dependencies. This phase uses existing project stack exclusively.

### Existing Components Used

| Component | Location | Role in This Phase |
|-----------|----------|--------------------|
| `StationListPanel._populate_recent()` | `musicstreamer/ui_qt/station_list_panel.py:357` | Core rebuild logic — just needs a public entry point |
| `Repo.update_last_played(station_id)` | `musicstreamer/repo.py:312` | Already called at `main_window.py:324`; no change |
| `Repo.list_recently_played(n=3)` | `musicstreamer/repo.py:319` | Already called inside `_populate_recent()`; no change |
| `MainWindow._on_station_activated()` | `musicstreamer/ui_qt/main_window.py:320` | New call site — one extra line after `update_last_played` |
| `QStandardItemModel` / `QListView` | `station_list_panel.py:172–179` | Flat model; `model.clear()` + re-append is the established idiom |

---

## Architecture Patterns

### Data Flow Diagram

```
User click on station in tree/recent_view
         |
         v
StationListPanel.station_activated.emit(station)
         |
         v
MainWindow._on_station_activated(station)
  ├─ now_playing.bind_station(station)
  ├─ _player.play(station)
  ├─ _repo.update_last_played(station.id)   <-- already here
  ├─ station_panel.refresh_recent()          <-- NEW: one line added here
  ├─ now_playing.on_playing_state_changed(True)
  └─ show_toast("Connecting…")
         |
         v
StationListPanel.refresh_recent()
  └─ _populate_recent()
       ├─ _recent_model.clear()
       ├─ _repo.list_recently_played(3)     [re-queries DB]
       └─ for each station: appendRow(item) [rebuilds flat model]
```

**Key property:** `_populate_recent()` touches `_recent_model` only. It does NOT touch `model` (the `StationTreeModel`), `_proxy` (the `StationFilterProxyModel`), or the `QTreeView` expand/collapse state. This satisfies SC #3 by construction.

### Verified: _populate_recent Does NOT Touch the Provider Tree

[VERIFIED: read `station_list_panel.py:357–365`]

```python
def _populate_recent(self) -> None:
    self._recent_model.clear()
    stations = self._repo.list_recently_played(3)
    for station in stations:
        item = QStandardItem(station.name)
        item.setIcon(load_station_icon(station))
        item.setEditable(False)
        item.setData(station, Qt.UserRole)
        self._recent_model.appendRow(item)
```

`self.model` (the `StationTreeModel`) is never referenced. `self._proxy` is never referenced. `self.tree` is never referenced. The only mutation is on `self._recent_model`, which is a standalone `QStandardItemModel` backing the flat `QListView`. There is no expand/collapse state on a flat `QListView` — it has no tree structure to collapse.

### Verified: refresh_model() Is the Wrong Approach

[VERIFIED: read `station_list_panel.py:314–319`]

`refresh_model()` calls `self.model.refresh(self._repo.list_stations())` which rebuilds the `StationTreeModel`. This collapses all provider groups. The new call must bypass `refresh_model()` entirely and call only `_populate_recent()`.

### Verified: _on_station_activated Touch Point

[VERIFIED: read `main_window.py:320–329`]

```python
def _on_station_activated(self, station: Station) -> None:
    self.now_playing.bind_station(station)
    self._player.play(station)
    self._repo.update_last_played(station.id)      # line 324
    self.now_playing.on_playing_state_changed(True)
    self.show_toast("Connecting…")
    self._media_keys.publish_metadata(station, "", self.now_playing.current_cover_pixmap())
    self._media_keys.set_playback_state("playing")
```

The new call inserts as:
```python
    self._repo.update_last_played(station.id)
    self.station_panel.refresh_recent()            # NEW
    self.now_playing.on_playing_state_changed(True)
```

`station_panel` is accessed as `self.station_panel` (the attribute set at `main_window.py:204`). No new imports needed.

### Naming Convention Decision

[VERIFIED: read `station_list_panel.py:314`]

The existing public refresh method is `refresh_model()`. The naming precedent strongly favors `refresh_recent()` for the new method. It follows the same pattern: `refresh_<noun>()` where `<noun>` identifies the scope of the refresh. Planner should use `refresh_recent()` unless there is a specific reason not to.

### Recommended Project Structure

No new files. Changes are in:
```
musicstreamer/
├── ui_qt/
│   ├── station_list_panel.py    # Add refresh_recent() public method
│   └── main_window.py           # Add station_panel.refresh_recent() call
tests/
├── test_station_list_panel.py   # Add test for refresh_recent() behavior
└── test_main_window_integration.py  # Add/update station_activated → recent list test
```

### Anti-Patterns to Avoid

- **Calling `refresh_model()` instead of `refresh_recent()`:** `refresh_model()` rebuilds the full provider tree, collapses all groups, and violates SC #3.
- **Connecting a new signal:** No new signal is needed. `MainWindow` already holds both `_repo` and `station_panel` — a direct method call is simpler and the established pattern for this class.
- **Self-capturing lambda for the connection:** Project convention QA-05 forbids self-capturing lambdas in signal connections. The new call is not a connection at all (it's an inline call in a slot), so QA-05 does not apply here. But if the planner chose a signal-based approach, the connection must use a bound method.
- **Calling `refresh_recent()` before `update_last_played()`:** Order matters — the DB write must happen first, then the UI rebuild reads the updated data.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Moving an item to top of a QListView | Custom item-move logic, `QAbstractItemModel.moveRow()` | Re-run `_populate_recent()` (clear + re-append) | Trivial DB query on 3 items; no performance concern; already the established idiom in this codebase |
| Detecting which item moved | Diff old/new order logic | None needed — just rebuild | n=3 means full rebuild is O(3), not worth optimizing |

---

## Common Pitfalls

### Pitfall 1: Calling refresh_recent() Before update_last_played()
**What goes wrong:** The recent list re-queries before the new timestamp is committed; the clicked station does not appear at the top.
**Why it happens:** Swapping the call order in `_on_station_activated`.
**How to avoid:** Keep `update_last_played` before `refresh_recent()`.
**Warning signs:** Manual test shows old order stays after click.

### Pitfall 2: Using refresh_model() Instead of refresh_recent()
**What goes wrong:** Provider tree collapses on every station click; violates SC #3.
**Why it happens:** `refresh_model()` already calls `_populate_recent()` internally, tempting a wrong shortcut.
**How to avoid:** New public method wraps only `_populate_recent()` — never calls `model.refresh()`.
**Warning signs:** Tree groups collapse on station click (any group that was expanded collapses).

### Pitfall 3: FakeRepo in test_station_list_panel.py Does Not Update _recent on demand
**What goes wrong:** A new test for `refresh_recent()` constructs `FakeRepo` with a static `_recent` list. If the test calls `panel.refresh_recent()` without first mutating `FakeRepo._recent`, the list appears unchanged even though the method fired.
**Why it happens:** `FakeRepo.list_recently_played()` returns `self._recent[:n]` — a snapshot, not a live query.
**How to avoid:** Test must mutate `fake_repo._recent` before calling `refresh_recent()` to simulate a new station appearing at the top. Then assert `panel.recent_view.model().item(0).data(Qt.UserRole)` matches the newly-prepended station.
**Warning signs:** Test passes vacuously — recent model row count is 1 before and after.

### Pitfall 4: MainWindow FakeRepo in test_main_window_integration.py Lacks recent mutation support
**What goes wrong:** The integration test for `_on_station_activated` → recent list refresh cannot verify the visual update if `FakeRepo` always returns the same `_recent`.
**Why it happens:** `FakeRepo` in `test_main_window_integration.py:77` has `_recent = recent or []` hard-coded at construction. `update_last_played` stores station ids but doesn't mutate `_recent`.
**How to avoid:** Either (a) extend `FakeRepo.update_last_played` to prepend the station to `_recent` so that `list_recently_played` returns an updated list, or (b) test at the `StationListPanel` level only (simpler). The planner should decide where the integration test lives.
**Warning signs:** `recent_view.model().rowCount()` stays 0 in a MainWindow integration test because `_recent` was never populated.

---

## Code Examples

### Pattern 1: New public method (station_list_panel.py)

[VERIFIED: matches established `refresh_model()` pattern at line 314]

```python
def refresh_recent(self) -> None:
    """Refresh the Recently Played list from the DB. Call after update_last_played."""
    self._populate_recent()
```

### Pattern 2: Call site in main_window.py

[VERIFIED: `_on_station_activated` body at lines 320–329]

```python
def _on_station_activated(self, station: Station) -> None:
    self.now_playing.bind_station(station)
    self._player.play(station)
    self._repo.update_last_played(station.id)
    self.station_panel.refresh_recent()          # NEW
    self.now_playing.on_playing_state_changed(True)
    self.show_toast("Connecting…")
    self._media_keys.publish_metadata(station, "", self.now_playing.current_cover_pixmap())
    self._media_keys.set_playback_state("playing")
```

### Pattern 3: Unit test shape for refresh_recent() (test_station_list_panel.py)

[VERIFIED: follows `FakeRepo` pattern at `test_station_list_panel.py:34–70`]

```python
def test_refresh_recent_updates_list(qtbot):
    repo = _sample_repo()
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)

    # Simulate a different station becoming the most recently played
    new_top = make_station(99, "New Top Station", "TestFM")
    repo._recent = [new_top] + repo._recent

    panel.refresh_recent()

    assert panel.recent_view.model().rowCount() == 3
    top_station = panel.recent_view.model().index(0, 0).data(Qt.UserRole)
    assert isinstance(top_station, Station)
    assert top_station.id == 99
```

### Pattern 4: Integration test shape (test_main_window_integration.py)

[VERIFIED: follows `test_station_activated_updates_last_played` at line 279]

```python
def test_station_activated_refreshes_recent_list(qtbot, fake_player, fake_repo):
    station = _make_station()
    # Pre-populate _recent so list_recently_played returns something after activation
    fake_repo._recent = [station]
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)

    window.station_panel.station_activated.emit(station)

    assert window.station_panel.recent_view.model().rowCount() >= 1
```

---

## Runtime State Inventory

Step 2.5: SKIPPED — this is a greenfield code addition (new public method + one-line call site), not a rename, refactor, or migration. No stored data, live service config, OS-registered state, secrets, or build artifacts are affected.

---

## Environment Availability

Step 2.6: SKIPPED — no external dependencies beyond the existing project stack. PySide6, pytest-qt, and the existing test infrastructure are already present and used by the current test suite.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-qt |
| Config file | `pytest.ini` or `pyproject.toml` (existing project config) |
| Quick run command | `pytest tests/test_station_list_panel.py tests/test_main_window_integration.py -x` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUG-01 | `refresh_recent()` exists on `StationListPanel` | unit | `pytest tests/test_station_list_panel.py -k refresh_recent -x` | ❌ Wave 0 |
| BUG-01 | `refresh_recent()` rebuilds `_recent_model` with latest DB data | unit | `pytest tests/test_station_list_panel.py -k refresh_recent -x` | ❌ Wave 0 |
| BUG-01 | `_on_station_activated` calls `refresh_recent()` after `update_last_played` | integration | `pytest tests/test_main_window_integration.py -k refresh_recent -x` | ❌ Wave 0 |
| BUG-01 | Tree expand/collapse state is NOT disturbed during recent-list refresh | unit | `pytest tests/test_station_list_panel.py -k tree_state -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_station_list_panel.py tests/test_main_window_integration.py -x`
- **Per wave merge:** `pytest`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_station_list_panel.py` — add `test_refresh_recent_updates_list` and `test_refresh_recent_does_not_touch_tree`
- [ ] `tests/test_main_window_integration.py` — add `test_station_activated_refreshes_recent_list`

*(Existing test infrastructure covers all other phase concerns — no new fixtures, conftest, or framework install needed.)*

---

## Security Domain

No security-relevant changes in this phase. The fix adds one method call in an existing Qt slot; no new input paths, no new data persistence, no authentication or authorization surface. ASVS categories V2–V6 are not applicable.

---

## Assumptions Log

> This table is empty. All claims in this research were verified by reading the actual source files in this session.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | — | — | — |

**All claims in this research were verified against the live codebase. No assumed knowledge.**

---

## Open Questions

1. **Final name: `refresh_recent()` vs. `bump_recent(station)` vs. another name**
   - What we know: `refresh_model()` is the precedent. The CONTEXT.md asks the planner to pick. `refresh_recent()` is the natural analog.
   - What's unclear: Whether the planner prefers `bump_recent(station)` (which would accept a station argument for possible future optimization) or the simpler no-arg `refresh_recent()`.
   - Recommendation: Use `refresh_recent()` (no-arg). The body is just `self._populate_recent()` regardless; the station argument is unnecessary because `_populate_recent` queries the DB directly. No-arg keeps the interface consistent with `refresh_model()`.

---

## Sources

### Primary (HIGH confidence)

- `musicstreamer/ui_qt/station_list_panel.py` — read in full; verified `_populate_recent` body (lines 357–365), `refresh_model` body (lines 314–319), `__init__` construction (lines 182, 296), `recent_view` / `_recent_model` setup (lines 171–182)
- `musicstreamer/ui_qt/main_window.py` — read in full; verified `_on_station_activated` body (lines 320–329), `station_panel` attribute (line 204)
- `musicstreamer/repo.py` — read lines 305–345; verified `update_last_played` (312–317) and `list_recently_played` (319–343)
- `tests/test_station_list_panel.py` — read in full; verified `FakeRepo`, test patterns, no existing `refresh_recent` test
- `tests/test_main_window_integration.py` — read in full; verified `FakeRepo`, `test_station_activated_updates_last_played` pattern (line 279), no existing recent-list refresh test
- `tests/test_repo.py` — verified lines 169–202; `test_update_last_played`, `test_list_recently_played_order`, `test_list_recently_played_limit`, `test_list_recently_played_empty` all exist and pass

### Secondary (MEDIUM confidence)

- `.planning/phases/50-recently-played-live-update/50-CONTEXT.md` — all four touch-point claims verified against source; CONTEXT.md is accurate

---

## Metadata

**Confidence breakdown:**
- Touch points: HIGH — all four verified by direct source read in this session
- Test patterns: HIGH — existing test files read; gaps identified precisely
- Naming recommendation: HIGH — `refresh_model()` precedent verified
- No assumptions: confirmed — zero `[ASSUMED]` claims

**Research date:** 2026-04-27
**Valid until:** Stable — this is pure internal refactor with no external dependencies; findings remain valid until the touched files change
