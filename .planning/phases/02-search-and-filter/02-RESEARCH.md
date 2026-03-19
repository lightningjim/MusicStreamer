# Phase 2: Search and Filter - Research

**Researched:** 2026-03-19
**Domain:** GTK4/Libadwaita search and filter UI
**Confidence:** HIGH

## Summary

Phase 2 adds three composing filter controls to an existing `Gtk.ListBox`-based station list: a `Gtk.SearchEntry` in the HeaderBar center, and two `Gtk.DropDown` widgets in a filter strip below. Filter logic is pure in-process: `Gtk.ListBox.set_filter_func` evaluates all three controls per row on every `_on_filter_changed` call. A Clear button and zero-result `Adw.StatusPage` complete the UX.

All widget choices, layout, spacing, and copy are fully specified in the approved UI-SPEC (`02-UI-SPEC.md`). No design decisions remain open. The only work is wiring the specified widgets into `main_window.py` and extracting a tag-normalization helper.

**Primary recommendation:** Implement entirely within `main_window.py` (and a small `filter_utils.py` helper for tag normalization). No new dependencies. No data-layer changes.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- `Gtk.SearchEntry` centered in HeaderBar as title widget — always visible, no toggle
- Provider and tag dropdowns in a horizontal filter strip below HeaderBar via `shell.add_top_bar(filter_box)`
- Clear button in the filter strip, visible only when any filter is active
- Zero-result state: `Adw.StatusPage` replacing ScrolledWindow content
- Tag normalization: split on `,` and `•`, strip whitespace, deduplicate case-insensitively
- AND composition: all active filters must match simultaneously

### Claude's Discretion
- GTK4 filter mechanism: `Gtk.ListBox.set_filter_func` (UI-SPEC confirms this choice)
- Dropdown widget: `Gtk.DropDown` with `Gtk.StringList` (UI-SPEC confirms)
- Filter strip spacing: 4px vertical, 8px horizontal (UI-SPEC confirms)
- Dropdown sort order: alphabetical

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FILT-01 | User can search stations by name via a search box that filters the list in real time | `Gtk.SearchEntry` `search-changed` signal → `_on_filter_changed` → `listbox.invalidate_filter()` |
| FILT-02 | User can filter stations by provider/source via a dropdown | `Gtk.DropDown` + `Gtk.StringList` populated from `Repo.list_providers()` distinct names; `notify::selected` signal |
| FILT-03 | User can filter stations by genre/tag via a dropdown populated from station tags | Tag vocab derived from `list_stations()` with normalization helper; same `Gtk.DropDown` pattern |
| FILT-04 | Search and both dropdowns compose with AND logic | `set_filter_func` callback reads all three controls; returns `True` only when all active conditions match |
| FILT-05 | User can clear all filters to return to full station list | Clear button resets SearchEntry + both dropdowns to index 0; `set_visible` driven by active-filter detection |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GTK4 (gi.repository.Gtk) | 4.0 (system) | ListBox filter, SearchEntry, DropDown, StringList | Already in use; all required widgets present |
| Libadwaita (gi.repository.Adw) | 1 (system) | ToolbarView, StatusPage, HeaderBar | Already in use; StatusPage is the standard empty-state widget |

No new packages to install. All widgets are already available via the system gi bindings.

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python stdlib `re` or str methods | — | Tag normalization (split, strip, casefold) | Tag parsing helper only |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `Gtk.ListBox.set_filter_func` | `Gtk.FilterListModel` + `Gtk.CustomFilter` | FilterListModel requires migrating ListBox to use a model; set_filter_func works directly on existing ListBox with zero migration cost |
| `Gtk.DropDown` | `Adw.ComboRow` | ComboRow is designed for settings list rows, not header/strip controls; DropDown is the right widget for freestanding dropdowns |

---

## Architecture Patterns

### Recommended Project Structure
No new directories needed. Changes are:
```
musicstreamer/
├── ui/
│   ├── main_window.py     # primary change: add search, filter strip, filter logic
│   └── station_row.py     # no changes needed
├── filter_utils.py        # NEW: tag normalization helper (pure function, no GTK)
└── models.py              # no changes
```

### Pattern 1: set_filter_func with multi-control state
**What:** Register a callback with `listbox.set_filter_func(fn)`. The callback receives each `Gtk.ListBoxRow` and returns `True` (show) or `False` (hide). Call `listbox.invalidate_filter()` to re-evaluate all rows.
**When to use:** Whenever filter criteria change (any signal from SearchEntry or either DropDown).
**Example:**
```python
# Source: GTK4 Python docs / gi-repository API
def _filter_func(self, row):
    text = self.search_entry.get_text().casefold()
    prov_idx = self.provider_dropdown.get_selected()   # 0 = "All Providers"
    tag_idx  = self.tag_dropdown.get_selected()        # 0 = "All Tags"
    st = row.station

    if text and text not in st.name.casefold():
        return False
    if prov_idx > 0:
        selected_prov = self._provider_items[prov_idx]  # "All Providers" at index 0
        if st.provider_name != selected_prov:
            return False
    if tag_idx > 0:
        selected_tag = self._tag_items[tag_idx].casefold()
        row_tags = {t.casefold() for t in _normalize_tags(st.tags)}
        if selected_tag not in row_tags:
            return False
    return True

def _on_filter_changed(self, *_):
    self.listbox.invalidate_filter()
    self._update_clear_button()
    self._update_empty_state()
```

### Pattern 2: Gtk.DropDown with Gtk.StringList
**What:** Build a `Gtk.StringList` from a Python list of strings, pass to `Gtk.DropDown`.
**When to use:** Any freestanding dropdown with a static or infrequently-updated string list.
**Example:**
```python
# Source: GTK4 API
items = ["All Providers"] + sorted(provider_names)
model = Gtk.StringList.new(items)
dropdown = Gtk.DropDown.new(model, None)
dropdown.connect("notify::selected", self._on_filter_changed)
```

### Pattern 3: Zero-result state swap
**What:** The `Adw.ToolbarView` content area holds either the `Gtk.ScrolledWindow` (normal) or an `Adw.StatusPage` (zero results). Swap by calling `shell.set_content(widget)`.
**When to use:** After every `invalidate_filter()`, count visible rows; if 0, swap to StatusPage.
**Example:**
```python
# Count visible rows after filter
visible = sum(
    1 for row in self._iter_rows()
    if row.get_visible()   # filter_func controls this
)
if visible == 0:
    self.shell.set_content(self.empty_page)
else:
    self.shell.set_content(self.scroller)
```

Note: `set_filter_func` hides rows but does not remove them. Visible-row counting must use `row.get_child_visible()` or test via `listbox.get_row_at_index` iteration — verify which property reflects filter state (it is `get_visible()` on the row after `invalidate_filter()`).

### Pattern 4: Tag normalization (pure helper)
**What:** Extract a function `normalize_tags(raw: str) -> list[str]` that splits on `,` and `•`, strips whitespace, and deduplicates case-insensitively (preserve first-seen display form).
**Example:**
```python
import re

def normalize_tags(raw: str) -> list[str]:
    tokens = re.split(r"[,•]", raw)
    seen = {}
    for t in tokens:
        t = t.strip()
        if not t:
            continue
        key = t.casefold()
        if key not in seen:
            seen[key] = t
    return list(seen.values())
```

### Anti-Patterns to Avoid
- **Re-populating the ListBox on every filter change:** `set_filter_func` + `invalidate_filter()` is O(n) in-place; do not clear and re-append rows
- **Rebuilding DropDown models on every filter change:** Build provider/tag models once at construction time from `list_stations()`; rebuild only when stations are added/edited (call a `_rebuild_filter_state()` from `reload_list()`)
- **Importing GTK inside filter_utils.py:** Tag normalization is pure Python; keeping it GTK-free makes it trivially testable

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Incremental list filtering | Custom show/hide loop | `set_filter_func` + `invalidate_filter()` | GTK manages row visibility and re-layout |
| Dropdown with string items | Gtk.ListStore + Gtk.ComboBox | `Gtk.DropDown` + `Gtk.StringList` | StringList is the GTK4 idiomatic model for string dropdowns |
| Empty-state placeholder | Custom Box with Label | `Adw.StatusPage` | Standard Adw component; supports icon, title, description, action button |
| Case-insensitive string compare | Locale-aware collation | Python `str.casefold()` | Sufficient for station names and tags |

---

## Common Pitfalls

### Pitfall 1: set_filter_func row visibility vs widget visibility
**What goes wrong:** After `invalidate_filter()`, code tests `row.get_visible()` which reflects the explicit `set_visible()` call, not the filter result. Filter results control whether the row appears in layout but via a separate internal flag.
**Why it happens:** GTK4 uses two visibility systems: explicit `set_visible()` and the filter-func result. They are independent.
**How to avoid:** To count "shown" rows after filter, iterate `listbox` children and check `row.get_mapped()` or count via a sentinel approach — accumulate `True` returns in the filter_func itself into an instance variable, reset it before `invalidate_filter()`.
**Warning signs:** Empty-state detection always triggers or never triggers.

Simpler alternative: maintain a `self._visible_count` counter as an instance variable, reset to 0 before `invalidate_filter()`, increment inside `_filter_func` for each `True` return. Swap content based on this counter in `_on_filter_changed` after `invalidate_filter()`.

### Pitfall 2: notify::selected fires during model rebuild
**What goes wrong:** When `Gtk.DropDown.set_model()` is called with a new `Gtk.StringList`, `notify::selected` fires (selection resets to 0), triggering `_on_filter_changed` during initialization.
**Why it happens:** GObject property notification is synchronous.
**How to avoid:** Use a `self._rebuilding` guard flag, or connect signals after model construction, or call `handler_block`/`handler_unblock`.

### Pitfall 3: Tag vocabulary built from stale station list
**What goes wrong:** Tag dropdown shows tags from stations that no longer exist, or misses tags from newly added stations.
**Why it happens:** Vocabulary is computed once at init and never refreshed.
**How to avoid:** Call `_rebuild_filter_state()` (recomputes provider and tag vocabs, rebuilds both DropDown models) at the end of `reload_list()` so it stays in sync after every edit.

### Pitfall 4: Gtk.SearchEntry search-changed signal vs changed signal
**What goes wrong:** Connecting to `changed` fires on every intermediate keystroke including programmatic `set_text("")` clearing; `search-changed` is debounced and also fires when the built-in clear icon is clicked.
**Why it happens:** `Gtk.SearchEntry` wraps `Gtk.Entry` and adds `search-changed` as the preferred signal.
**How to avoid:** Always connect to `search-changed`, not `changed`.

---

## Code Examples

### Full filter strip construction
```python
# Source: GTK4 API + UI-SPEC 02-UI-SPEC.md
filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
filter_box.set_margin_top(4)
filter_box.set_margin_bottom(4)
filter_box.set_margin_start(8)
filter_box.set_margin_end(8)

self.provider_dropdown = Gtk.DropDown.new(Gtk.StringList.new(["All Providers"]), None)
self.provider_dropdown.set_size_request(120, -1)
self.provider_dropdown.connect("notify::selected", self._on_filter_changed)

self.tag_dropdown = Gtk.DropDown.new(Gtk.StringList.new(["All Tags"]), None)
self.tag_dropdown.set_size_request(120, -1)
self.tag_dropdown.connect("notify::selected", self._on_filter_changed)

self.clear_btn = Gtk.Button(label="Clear")
self.clear_btn.set_visible(False)
self.clear_btn.connect("clicked", self._on_clear)
# Right-align clear button
spacer = Gtk.Box()
spacer.set_hexpand(True)

filter_box.append(self.provider_dropdown)
filter_box.append(self.tag_dropdown)
filter_box.append(spacer)
filter_box.append(self.clear_btn)

shell.add_top_bar(filter_box)
```

### SearchEntry in HeaderBar center
```python
# Source: GTK4 API + UI-SPEC 02-UI-SPEC.md
self.search_entry = Gtk.SearchEntry()
self.search_entry.set_placeholder_text("Search stations…")
self.search_entry.connect("search-changed", self._on_filter_changed)
header.set_title_widget(self.search_entry)
```

### Active-filter detection
```python
def _any_filter_active(self) -> bool:
    return (
        bool(self.search_entry.get_text())
        or self.provider_dropdown.get_selected() > 0
        or self.tag_dropdown.get_selected() > 0
    )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Gtk.ComboBox` + `Gtk.ListStore` | `Gtk.DropDown` + `Gtk.StringList` | GTK4 (2020) | Simpler API, no tree model needed for flat string lists |
| `Gtk.SearchBar` with Ctrl+F toggle | `Gtk.SearchEntry` always visible | Design choice | Zero toggle friction; matches GNOME Software/Files |
| Manual label swap for empty state | `Adw.StatusPage` | Libadwaita 1.0 | Standard component with icon, title, description, action |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (uv run --with pytest) |
| Config file | none (discovered by pytest convention) |
| Quick run command | `uv run --with pytest pytest tests/ -x -q` |
| Full suite command | `uv run --with pytest pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FILT-01 | Name search filters rows by case-insensitive substring | unit | `uv run --with pytest pytest tests/test_filter_utils.py -x -q` | ❌ Wave 0 |
| FILT-02 | Provider filter matches `station.provider_name` | unit | `uv run --with pytest pytest tests/test_filter_utils.py -x -q` | ❌ Wave 0 |
| FILT-03 | Tag filter matches normalized tag vocabulary | unit | `uv run --with pytest pytest tests/test_filter_utils.py -x -q` | ❌ Wave 0 |
| FILT-04 | AND composition: all three filters applied simultaneously | unit | `uv run --with pytest pytest tests/test_filter_utils.py -x -q` | ❌ Wave 0 |
| FILT-05 | Clear resets all filter state; full list returns | unit | `uv run --with pytest pytest tests/test_filter_utils.py -x -q` | ❌ Wave 0 |

Note: GTK widget signal/layout tests require a display and are not automated. Filter logic in `filter_utils.py` (normalize_tags, filter predicate) is pure Python and fully testable without GTK.

### Sampling Rate
- **Per task commit:** `uv run --with pytest pytest tests/ -x -q`
- **Per wave merge:** `uv run --with pytest pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_filter_utils.py` — covers FILT-01 through FILT-05 via pure predicate tests
- [ ] `musicstreamer/filter_utils.py` — `normalize_tags()` and `matches_filter()` must exist before tests run

---

## Open Questions

1. **Visible-row counting after invalidate_filter()**
   - What we know: `set_filter_func` hides rows internally; `get_visible()` may not reflect filter state
   - What's unclear: exact GTK4 Python API to count filter-hidden rows without iterating and checking a non-obvious property
   - Recommendation: Use the `self._visible_count` counter pattern (reset before `invalidate_filter()`, increment inside `_filter_func`) — avoids the ambiguity entirely

2. **notify::selected guard during model rebuild**
   - What we know: Replacing a DropDown model resets selection to 0 and fires the signal
   - What's unclear: whether `handler_block` is available on `Gtk.DropDown` in Python bindings
   - Recommendation: Use a `self._rebuilding = True/False` guard inside `_rebuild_filter_state()` and early-return in `_on_filter_changed` when guard is set

---

## Sources

### Primary (HIGH confidence)
- GTK4 Python API (gi.repository.Gtk) — `ListBox.set_filter_func`, `SearchEntry`, `DropDown`, `StringList` — verified against existing project usage
- Libadwaita API (gi.repository.Adw) — `StatusPage`, `ToolbarView.add_top_bar` — verified against existing `main_window.py`
- `02-UI-SPEC.md` (approved) — widget choices, layout, spacing, copy fully specified

### Secondary (MEDIUM confidence)
- GTK4 signal documentation — `search-changed` vs `changed` distinction; `notify::selected` for DropDown

### Tertiary (LOW confidence)
- Visible-row detection after `invalidate_filter()` — exact property/method to test filter-hidden state; use counter pattern to avoid

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all widgets already used in project; no new dependencies
- Architecture: HIGH — patterns derived directly from existing code + approved UI-SPEC
- Pitfalls: MEDIUM — filter visibility counting is the one genuinely uncertain GTK4 detail; counter pattern sidesteps it

**Research date:** 2026-03-19
**Valid until:** 2026-06-19 (GTK4/Adw stable; no fast-moving dependencies)
