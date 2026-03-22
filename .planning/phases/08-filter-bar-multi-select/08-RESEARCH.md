# Phase 8: Filter Bar Multi-Select - Research

**Researched:** 2026-03-22
**Domain:** GTK4/Python — Gtk.ToggleButton chip strip, multi-select filter logic
**Confidence:** HIGH

## Summary

This phase replaces two `Gtk.DropDown` widgets with horizontally-scrollable chip rows built from `Gtk.ToggleButton`. All decisions are locked in CONTEXT.md. The core work is: (1) replace the existing single-value filter state with `set[str]` for providers and tags, (2) update `matches_filter` to accept sets, (3) rebuild the filter strip UI with chip rows, and (4) update `_any_filter_active`, `_on_clear`, and `_rebuild_filter_state`.

No new dependencies. No API calls. All logic is in-memory against the already-loaded station list. The existing `_rebuilding` guard, `_on_filter_changed` wiring, and `_render_list` structure are all reused.

**Primary recommendation:** Add `matches_filter_multi(station, search_text, provider_set, tag_set)` to `filter_utils.py` alongside the existing function (keeps backward compatibility), then update `_render_list` to call the new variant.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Replace both `Gtk.DropDown` widgets with horizontally-arranged `Gtk.ToggleButton` chips — one chip per provider, one chip per tag
- **D-02:** Chips are always visible in the filter strip (no popover); strip scrolls horizontally if chip count overflows
- **D-03:** Each chip has a per-chip × suffix button; clicking × deselects that chip without requiring a toggle click
- **D-04:** The existing "Clear" button is retained for bulk reset (deselects all chips, clears search)
- **D-05:** Provider filter active (any chip selected) → flat mode, same as Phase 7 D-12; no grouped-by-provider view when filtering
- **D-06:** Multiple providers selected → still flat; all matching stations from all selected providers in one flat list
- **D-07:** Tag filter applies in both flat and grouped modes (same as current behavior)
- **D-08:** Provider chips compose with OR within providers (station matches if it belongs to any selected provider)
- **D-09:** Tag chips compose with OR within tags (station matches if it has any selected tag)
- **D-10:** Provider selection AND tag selection compose with AND (station must match at least one selected provider AND at least one selected tag)
- **D-11:** Clearing all chip selections returns to the full grouped view (same as Phase 7 no-filter state)
- **D-12:** Recently Played section hidden when any chip or search filter is active (Phase 7 D-15 still holds)
- **D-13:** `_any_filter_active()` updated to check chip selection state instead of dropdown index

### Claude's Discretion

- Exact widget for chip row (Gtk.ScrolledWindow + Gtk.Box vs Gtk.FlowBox)
- Spacing and visual styling of chips (keep consistent with existing filter strip margins)
- Whether provider and tag chips share one row or occupy separate rows

### Deferred Ideas (OUT OF SCOPE)

- Tag chip overflow handling / search within tags — if tag count becomes large in future, a popover may be warranted; defer
- Chip color coding by provider — visual enhancement only; Phase 11 if desired
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BROWSE-02 | User can filter by multiple providers simultaneously (multi-select) | D-01, D-06, D-08: ToggleButton chips with OR logic within providers |
| BROWSE-03 | User can filter by multiple genres/tags simultaneously (multi-select) | D-01, D-07, D-09: ToggleButton chips with OR logic within tags |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GTK4 (PyGObject) | system (4.0) | ToggleButton, ScrolledWindow, Box | Already in use; no new dep |
| Python builtins | 3.10+ | `set[str]` for multi-select state | No library needed |

No new packages. All widget types (`Gtk.ToggleButton`, `Gtk.ScrolledWindow`, `Gtk.Box`, `Gtk.Button`) are already imported and available.

**Installation:** None required.

## Architecture Patterns

### Chip Strip Layout (Claude's Discretion — recommended)

Use `Gtk.ScrolledWindow` + `Gtk.Box` (horizontal). `Gtk.FlowBox` would allow wrapping but decisions specify horizontal scroll only (D-02), making `ScrolledWindow + Box` the right fit.

Two separate rows:
- Row 1: provider chips
- Row 2: tag chips

Both rows sit inside `filter_box` (the existing `Gtk.Box` in `__init__`), replacing `provider_dropdown` and `tag_dropdown`. Vertical stacking within `filter_box` is acceptable since `filter_box` is already a top bar added via `shell.add_top_bar(filter_box)`. Alternatively, keep `filter_box` as one horizontal box and stack the two chip ScrolledWindows in a vertical box inserted into `filter_box`.

Given the existing layout uses a single horizontal `filter_box`, the cleanest approach: replace the dropdowns with a `Gtk.Box(VERTICAL)` containing two chip rows, append that vertical box into `filter_box` in place of the two dropdowns. This preserves the Add/Edit/Clear button layout.

### Multi-Select State

Store selected chips as two instance sets on `MainWindow`:

```python
# Source: design derived from existing _provider_items / _tag_items pattern
self._selected_providers: set[str] = set()
self._selected_tags: set[str] = set()
```

Store chip widget references to enable bulk deselect in `_on_clear`:

```python
self._provider_chip_btns: list[Gtk.ToggleButton] = []
self._tag_chip_btns: list[Gtk.ToggleButton] = []
```

### Updated filter_utils.py

Add new function alongside existing `matches_filter` (backward compatible):

```python
# Source: design based on existing matches_filter signature
def matches_filter_multi(
    station: Station,
    search_text: str,
    provider_set: set[str],   # empty set = inactive
    tag_set: set[str],         # empty set = inactive
) -> bool:
    if search_text:
        if search_text.casefold() not in station.name.casefold():
            return False
    if provider_set:
        if station.provider_name not in provider_set:
            return False
    if tag_set:
        station_tags = {t.casefold() for t in normalize_tags(station.tags)}
        if not tag_set.intersection(station_tags):
            return False
    return True
```

Note: `tag_set` values should be stored casefold'd at selection time so the intersection check is consistent.

### Chip Creation Pattern

```python
# Source: UI-SPEC component inventory + GTK4 patterns
def _make_chip(self, label: str, on_toggle, on_dismiss) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    btn = Gtk.ToggleButton(label=label)
    btn.connect("toggled", on_toggle)
    dismiss = Gtk.Button()
    dismiss.set_icon_name("window-close-symbolic")
    dismiss.add_css_class("flat")
    dismiss.connect("clicked", on_dismiss)
    box.append(btn)
    box.append(dismiss)
    return box, btn  # return btn for deselect tracking
```

The × button callback: `lambda *_: (btn.set_active(False))` — the `toggled` signal fires when `set_active` is called, so `_on_filter_changed` is invoked automatically. No need to call it again explicitly.

### _rebuild_filter_state Pattern

Existing `_rebuild_filter_state` already enumerates providers and tags. Extend it to:
1. Clear the chip rows (remove all children from the inner `Gtk.Box`)
2. Repopulate chips from current station data
3. Restore selection state by matching previously-selected values against new chip labels (handles station add/edit triggering `reload_list`)

The `_rebuilding` flag guards this rebuild from triggering filter callbacks — same pattern as before.

### _any_filter_active Update

```python
def _any_filter_active(self) -> bool:
    return (
        bool(self.search_entry.get_text())
        or bool(self._selected_providers)
        or bool(self._selected_tags)
    )
```

### _on_clear Update

```python
def _on_clear(self, *_):
    self.search_entry.set_text("")
    self._rebuilding = True
    for btn in self._provider_chip_btns:
        btn.set_active(False)
    for btn in self._tag_chip_btns:
        btn.set_active(False)
    self._selected_providers.clear()
    self._selected_tags.clear()
    self._rebuilding = False
    self._on_filter_changed()
```

### _render_list Update

```python
def _render_list(self):
    stations = self.repo.list_stations()
    search_text = self.search_entry.get_text().strip()

    # Tag filter: casefold the stored set for matching
    tag_set = {t.casefold() for t in self._selected_tags}

    if tag_set:
        stations = [s for s in stations if matches_filter_multi(s, "", set(), tag_set)]

    if self._selected_providers:
        filtered = [s for s in stations
                    if matches_filter_multi(s, search_text, self._selected_providers, set())]
        self._rebuild_flat(filtered)
    else:
        self._rebuild_grouped(stations, search_text)
```

### Anti-Patterns to Avoid

- **Calling `_on_filter_changed` from inside the × button callback when toggled signal already fires:** The `toggled` signal fires when `set_active(False)` is called, so double-triggering `_on_filter_changed` will cause a redundant re-render. Use `_rebuilding` guard or rely solely on `toggled`.
- **Storing chip widget references in a dict keyed by label:** Provider/tag names can theoretically collide across dimensions; use separate lists for provider chips and tag chips.
- **Using `Gtk.FlowBox` for chip row:** Introduces row-wrapping behavior that conflicts with D-02 (horizontal scroll, always visible, no overflow UI). Use `ScrolledWindow + horizontal Box`.
- **Rebuilding chip rows on every filter change:** `_rebuild_filter_state` (and chip row rebuild) should only trigger on `reload_list` (station add/edit), not on every filter interaction. `_on_filter_changed` only calls `_render_list`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Horizontal overflow scroll | Custom scroll logic | `Gtk.ScrolledWindow(hscrollbar_policy=AUTOMATIC, vscrollbar_policy=NEVER)` | GTK handles scroll natively |
| Toggle accent styling | Custom CSS | Adwaita `Gtk.ToggleButton` active state | Adwaita applies accent automatically on active |
| Set intersection for tag matching | Manual loop | `set.intersection()` | Builtin, O(min(m,n)) |

## Common Pitfalls

### Pitfall 1: toggled signal fires during _rebuild_filter_state

**What goes wrong:** When `_rebuild_filter_state` creates new chip buttons and calls `set_active(False)` to initialize them, the `toggled` signal fires, calling `_on_filter_changed`, which re-renders the list mid-rebuild.

**Why it happens:** `toggled` fires on any `set_active` call, including initialization.

**How to avoid:** Wrap all chip creation and initialization in the existing `_rebuilding = True / False` guard. `_on_filter_changed` already returns early when `_rebuilding` is True.

**Warning signs:** List flickers or shows incorrect state immediately after adding/editing a station.

### Pitfall 2: Selection state lost when _rebuild_filter_state replaces chip widgets

**What goes wrong:** `reload_list` calls `_rebuild_filter_state` which destroys and recreates all chip buttons. Previously-selected chips lose their active state.

**Why it happens:** New `Gtk.ToggleButton` instances start inactive by default.

**How to avoid:** After recreating chips, iterate through `_selected_providers` and `_selected_tags` and call `set_active(True)` on matching buttons inside the `_rebuilding = True` guard.

**Warning signs:** Selecting a chip, adding a new station, then noticing the chip appears deselected while the list still filters correctly (or vice versa).

### Pitfall 3: × button calls set_active(False) then _on_filter_changed explicitly

**What goes wrong:** Double render — `set_active(False)` fires `toggled` which calls `_on_filter_changed`, then the explicit call triggers a second render.

**Why it happens:** Developer adds safety call not realizing `toggled` already fired.

**How to avoid:** × button callback only calls `btn.set_active(False)`. Let `toggled` → `_on_filter_changed` chain handle the rest.

### Pitfall 4: tag_set casefold mismatch

**What goes wrong:** `_selected_tags` stores display-form strings (e.g., "Lofi"); `normalize_tags` returns display-form strings too. If the intersection check uses raw strings, case variations fail.

**Why it happens:** `_selected_tags` populated from chip label (display form); station tags split by `normalize_tags` (display form); both need to be casefold'd before intersection.

**How to avoid:** At match time, casefold both sides: `{t.casefold() for t in normalize_tags(s.tags)}` vs `{t.casefold() for t in self._selected_tags}`.

## Code Examples

### ScrolledWindow chip row setup

```python
# Source: GTK4 docs / UI-SPEC component inventory
provider_scroll = Gtk.ScrolledWindow()
provider_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
provider_scroll.set_margin_top(4)
provider_scroll.set_margin_bottom(4)
provider_scroll.set_margin_start(8)
provider_scroll.set_margin_end(8)
self._provider_chip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
provider_scroll.set_child(self._provider_chip_box)
```

### Chip toggle callback

```python
# Source: design pattern — mirrors _on_filter_changed wiring
def _make_provider_toggle_cb(self, provider_name: str):
    def _cb(btn):
        if self._rebuilding:
            return
        if btn.get_active():
            self._selected_providers.add(provider_name)
        else:
            self._selected_providers.discard(provider_name)
        self._on_filter_changed()
    return _cb
```

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | none (runs via `pytest tests/`) |
| Quick run command | `cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/test_filter_utils.py -x -q` |
| Full suite command | `cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BROWSE-02 | Station matches any selected provider (OR within providers) | unit | `pytest tests/test_filter_utils.py -x -q` | ❌ Wave 0 (new test cases needed) |
| BROWSE-03 | Station matches any selected tag (OR within tags) | unit | `pytest tests/test_filter_utils.py -x -q` | ❌ Wave 0 (new test cases needed) |
| BROWSE-02+03 | Provider AND tag compose with AND | unit | `pytest tests/test_filter_utils.py -x -q` | ❌ Wave 0 |
| BROWSE-02+03 | Empty sets = no filter (returns all) | unit | `pytest tests/test_filter_utils.py -x -q` | ❌ Wave 0 |

Existing `test_filter_utils.py` covers the single-value `matches_filter`. New test cases are needed for `matches_filter_multi`.

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_filter_utils.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_filter_utils.py` — add `test_matches_filter_multi_*` cases covering: multi-provider OR, multi-tag OR, provider AND tag AND, empty sets inactive, casefold normalization

*(Existing test file present; new test functions appended, not a new file.)*

## Sources

### Primary (HIGH confidence)

- `musicstreamer/ui/main_window.py` — complete filter strip, rendering, and state management code read directly
- `musicstreamer/filter_utils.py` — complete filter utility code read directly
- `musicstreamer/models.py` — Station dataclass fields confirmed
- `.planning/phases/08-filter-bar-multi-select/08-CONTEXT.md` — all decisions locked
- `.planning/phases/08-filter-bar-multi-select/08-UI-SPEC.md` — component inventory and spacing

### Secondary (MEDIUM confidence)

- GTK4 `Gtk.ScrolledWindow` policy constants — verified from existing project usage patterns and GTK4 API conventions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps, all widgets already in codebase
- Architecture: HIGH — derived directly from existing code + locked decisions
- Pitfalls: HIGH — derived from actual code analysis, not speculation

**Research date:** 2026-03-22
**Valid until:** 2026-06-22 (stable GTK4 API)
