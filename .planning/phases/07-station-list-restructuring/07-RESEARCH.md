# Phase 7: Station List Restructuring - Research

**Researched:** 2026-03-22
**Domain:** GTK4 / Libadwaita widget hierarchy, SQLite schema migration, UI mode switching
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Use `Adw.ExpanderRow` for provider group headers — native Libadwaita collapsible row
- **D-02:** All provider groups collapsed by default on every launch (no state persistence)
- **D-03:** Stations within each group are `Adw.ActionRow` entries (or equivalent) preserving logo + name display
- **D-04:** Stations with `provider_id = NULL` appear in an "Uncategorized" group at the bottom
- **D-05:** "Uncategorized" group collapsed by default, same as all other groups
- **D-06:** Recently Played section appears above all provider groups, always visible (not collapsible)
- **D-07:** Shows last N played stations, most recent first; default N = 3
- **D-08:** N is configurable — store in user-facing config (SQLite `settings` table or JSON in DATA_DIR)
- **D-09:** Recently Played persists via `last_played_at` TEXT column on `stations` table; update on play; query top-N by `last_played_at DESC WHERE last_played_at IS NOT NULL`
- **D-10:** Recently Played updates immediately after a station starts playing (not on stop)
- **D-11:** A station in Recently Played is fully playable from that row
- **D-12:** Provider filter active → flat ungrouped list, grouping suppressed
- **D-13:** Search text only (no provider filter) → grouped view, non-matching rows hidden within groups, empty groups hidden
- **D-14:** Provider filter + search → flat list
- **D-15:** Recently Played section hidden when any filter is active

### Claude's Discretion

- Exact widget type for station rows inside ExpanderRow (Adw.ActionRow vs custom StationRow subclass)
- Whether empty groups (all stations filtered out) are hidden or shown collapsed
- Settings storage mechanism for Recently Played count (SQLite `settings` table recommended)

### Deferred Ideas (OUT OF SCOPE)

- Configurable Recently Played count UI (settings dialog)
- Recently Played section collapsibility
- Phase 8 multi-select provider/tag filter chips
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BROWSE-01 | Stations grouped by provider in station list, collapsed by default, expandable per group | `Adw.ExpanderRow` confirmed working in `Gtk.ListBox`; `set_expanded(False)` confirmed; `add_row()` confirmed |
| BROWSE-04 | "Recently Played" section at top showing last 3 played stations, most recent first | SQLite `last_played_at` column migration pattern confirmed; `settings` table pattern confirmed |
</phase_requirements>

---

## Summary

Phase 7 replaces the flat `Gtk.ListBox` of `StationRow` entries with a structured list: a Recently Played section (up to 3 rows) followed by `Adw.ExpanderRow` provider groups. The implementation splits into three areas: (1) SQLite schema additions (`last_played_at` column, `settings` table), (2) new `Repo` methods (`update_last_played`, `list_recently_played`, `get_setting`/`set_setting`), and (3) a full rewrite of `reload_list()` and `_on_filter_changed()` in `MainWindow` to support two render modes — GROUPED and FLAT.

The critical architectural decision is that `Gtk.ListBox.set_filter_func()` only sees top-level rows (`Adw.ExpanderRow` instances), not the children added via `add_row()`. This means the existing filter_func approach cannot filter individual stations within groups. The cleanest solution is to **drop set_filter_func entirely for the grouped view** and instead rebuild the list on filter changes (the existing `reload_list()` pattern extended for filtered cases). For the flat mode (provider filter active), standard iteration is used.

**Primary recommendation:** Implement two explicit render methods — `_rebuild_grouped(stations)` and `_rebuild_flat(stations)` — called from a unified `_render_list()` dispatcher that also manages Recently Played visibility. This keeps each mode self-contained and avoids a complex hybrid filter_func.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `Adw.ExpanderRow` | Adw 1.8.0 (installed) | Collapsible provider group header | Native Libadwaita; `Gtk.ListBoxRow` subclass; `add_row()` + `set_expanded()` confirmed working |
| `Adw.ActionRow` | Adw 1.8.0 (installed) | Station row inside group | `activated` signal fires when clicked; cleaner than nesting `ListBoxRow` inside `ExpanderRow` |
| `sqlite3` (stdlib) | 3.x | `last_played_at` column + `settings` table | Already in use; ALTER TABLE migration pattern already established in `db_init` |

### No New Dependencies

This phase adds no new Python packages. All GTK/Adw widgets are already imported.

---

## Architecture Patterns

### Render Mode Architecture

Two explicit modes replace the old single-mode list:

```
_render_list(stations, recently_played)
  ├── if provider filter active → _rebuild_flat(stations)  # no grouping
  └── else → _rebuild_grouped(stations, recently_played)   # ExpanderRows + RP section
```

`_on_filter_changed()` calls `_render_list()` instead of `listbox.invalidate_filter()`. The `set_filter_func` is **removed** — it cannot inspect ExpanderRow children and adds complexity without benefit.

### ListBox Structure (grouped mode, no filter)

```
Gtk.ListBox
├── [non-interactive ListBoxRow]           # "Recently Played" label header
├── StationRow (most recent)               # recently played row 1
├── StationRow                             # recently played row 2
├── StationRow                             # recently played row 3
├── Adw.ExpanderRow "Provider A"           # collapsed
│   ├── Adw.ActionRow (station)            #   child row
│   └── Adw.ActionRow (station)
├── Adw.ExpanderRow "Provider B"           # collapsed
│   └── Adw.ActionRow (station)
└── Adw.ExpanderRow "Uncategorized"        # collapsed, last, only if needed
    └── Adw.ActionRow (station)
```

Recently Played rows and the header label row are grouped into a container that can be toggled with `set_visible()` based on filter state (D-15).

### Pattern 1: ExpanderRow Group Creation

```python
# Source: verified against Adw 1.8.0 installed library
group = Adw.ExpanderRow()
group.set_title(provider_name or "Uncategorized")
group.set_expanded(False)

for station in provider_stations:
    row = Adw.ActionRow(
        title=GLib.markup_escape_text(station.name, -1),
        subtitle=GLib.markup_escape_text(station.tags or "", -1),
    )
    row.set_activatable(True)
    # Attach station_id for play dispatch
    row._station_id = station.id
    row.connect("activated", lambda r, _sid=station.id: self._play_by_id(_sid))
    group.add_row(row)

self.listbox.append(group)
```

### Pattern 2: Recently Played Section

```python
# Header label (non-interactive row)
label = Gtk.Label(label="Recently Played")
label.set_margin_top(8)
label.set_margin_bottom(4)
label.set_margin_start(12)
label.set_margin_end(8)
label.set_xalign(0.0)
header_row = Gtk.ListBoxRow()
header_row.set_activatable(False)
header_row.set_selectable(False)
header_row.set_child(label)
self.listbox.append(header_row)

# Station rows (reuse StationRow — they ARE ListBoxRow subclasses)
# StationRow placed directly in ListBox (not inside an ExpanderRow)
# The existing listbox row-activated signal handles these
for st in recently_played:
    row = StationRow(st)
    self.listbox.append(row)
```

The Recently Played rows live directly in the outer `Gtk.ListBox`, so the existing `row-activated` → `_play_row` handler works for them unchanged.

### Pattern 3: SQLite Schema Migration

Follow the established try/except `ALTER TABLE` pattern:

```python
# In db_init(), after existing migrations:
try:
    con.execute(
        "ALTER TABLE stations ADD COLUMN last_played_at TEXT"
    )
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists

try:
    con.execute(
        "CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    con.commit()
except sqlite3.OperationalError:
    pass  # table already exists
```

### Pattern 4: Recently Played Repo Methods

```python
def update_last_played(self, station_id: int):
    self.con.execute(
        "UPDATE stations SET last_played_at = datetime('now') WHERE id = ?",
        (station_id,),
    )
    self.con.commit()

def list_recently_played(self, n: int = 3) -> List[Station]:
    rows = self.con.execute(
        """
        SELECT s.*, p.name AS provider_name
        FROM stations s
        LEFT JOIN providers p ON p.id = s.provider_id
        WHERE s.last_played_at IS NOT NULL
        ORDER BY s.last_played_at DESC
        LIMIT ?
        """,
        (n,),
    ).fetchall()
    # ... same Station construction as list_stations()
```

### Pattern 5: Settings Table

```python
def get_setting(self, key: str, default: str) -> str:
    row = self.con.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else default

def set_setting(self, key: str, value: str):
    self.con.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
        (key, value),
    )
    self.con.commit()
```

Usage: `self.repo.get_setting("recently_played_count", "3")` → parse as int.

### Pattern 6: Grouped Search Filtering (D-13)

When search text is active but no provider filter:

```python
def _rebuild_grouped_filtered(self, stations, search_text):
    # Group stations by provider
    from itertools import groupby
    groups = {}
    for st in stations:  # already ordered by provider then name
        key = st.provider_name or ""
        groups.setdefault(key, []).append(st)

    for provider_name, provider_stations in groups.items():
        matching = [s for s in provider_stations if search_text.lower() in s.name.lower()]
        if not matching:
            continue  # hide empty groups
        group = Adw.ExpanderRow()
        group.set_title(provider_name or "Uncategorized")
        group.set_expanded(False)
        for st in matching:
            # ... add ActionRow children
```

### Anti-Patterns to Avoid

- **Using set_filter_func with ExpanderRow groups:** `filter_func` only sees `ExpanderRow` objects at the ListBox top level, NOT the children added via `add_row()`. Do not attempt to filter station rows through `set_filter_func` when in grouped mode.
- **Nesting StationRow (ListBoxRow) inside ExpanderRow via add_row():** While it works technically, it creates a ListBoxRow-inside-ListBoxRow structure. Use `Adw.ActionRow` directly as ExpanderRow children; connect `activated` signal directly. StationRow stays appropriate only for top-level ListBox entries (Recently Played rows).
- **Relying on `_visible_count` with the new architecture:** The `_visible_count` counter increments in `_filter_func`. Since `set_filter_func` is removed in grouped mode, track empty-state differently (e.g., count rows added during rebuild).
- **Calling `reload_list()` on every play:** `reload_list()` rebuilds the full list including filter dropdowns. For Recently Played refresh after play (D-10), use a dedicated `_refresh_recently_played()` that only updates the RP section rows, not the whole list.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Collapsible section headers | Custom toggle widget | `Adw.ExpanderRow` | Built-in expand/collapse, Adwaita styling, keyboard navigation |
| Settings persistence | Custom JSON file parser | SQLite `settings` table | Already have a DB connection; consistent with existing data layer |
| Station row art + name display | New widget | `Adw.ActionRow` with `add_prefix()` | Matches existing `StationRow` internals exactly |

**Key insight:** `Adw.ExpanderRow` is a `Gtk.ListBoxRow` subclass — it can be appended directly to a `Gtk.ListBox` with no adapter. The collapsible behavior, animation, and chevron icon are all built in.

---

## Common Pitfalls

### Pitfall 1: set_filter_func Does Not See ExpanderRow Children

**What goes wrong:** Developer sets `filter_func` expecting it to show/hide individual station rows inside provider groups. In practice, `filter_func` is only called for top-level `ListBox` children — the `ExpanderRow` instances. Children added via `add_row()` live in an internal sub-listbox managed by Libadwaita and are invisible to the outer `filter_func`.

**Why it happens:** `Gtk.ListBox.set_filter_func` operates on direct children only. `Adw.ExpanderRow.add_row()` inserts into an internal structure, not the outer `ListBox`.

**How to avoid:** Remove `set_filter_func` for grouped mode. Implement search filtering by rebuilding the list (re-running `_rebuild_grouped` with a filter predicate).

**Warning signs:** Filter changes appear to have no effect on station rows inside groups.

---

### Pitfall 2: row-activated Not Fired for ExpanderRow Children

**What goes wrong:** Developer expects `listbox.connect("row-activated", ...)` to fire when a user clicks a station row inside an `Adw.ExpanderRow`. It does not — `row-activated` fires for the `ExpanderRow` itself (header click = expand/collapse), not for its children.

**Why it happens:** Children of `ExpanderRow` are in an internal sub-listbox; their activation events do not bubble up to the outer `Gtk.ListBox`.

**How to avoid:** Connect `activated` signal on each `Adw.ActionRow` added as child: `row.connect("activated", callback)`. The existing `row-activated` handler continues to work for Recently Played rows (which are direct `ListBox` children as `StationRow` instances).

**Warning signs:** Clicking inside a group header expands it (correct) but clicking a station row inside does nothing.

---

### Pitfall 3: reload_list() Breaks Expand State

**What goes wrong:** Calling the full `reload_list()` on play (to refresh Recently Played) resets all ExpanderRow expand states back to collapsed and also rebuilds filter dropdowns unnecessarily.

**Why it happens:** `reload_list()` removes all children and recreates from scratch, including calling `_rebuild_filter_state()`.

**How to avoid:** Add a narrow `_refresh_recently_played()` method that only replaces the top N rows of the listbox (the RP header + station rows), leaving ExpanderRows untouched. Track which rows are the RP section (e.g., store count as instance variable).

**Warning signs:** Every time a station is played, all provider groups collapse.

---

### Pitfall 4: _rebuilding Guard Must Cover New Rebuild Paths

**What goes wrong:** The `_rebuilding` flag in `_rebuild_filter_state()` prevents filter callback loops when dropdowns are rebuilt. If `_rebuild_grouped()` / `_render_list()` modify dropdown models without setting `_rebuilding = True`, the guard is bypassed.

**How to avoid:** Ensure any code path that calls `_rebuild_filter_state()` (which touches dropdown models) still sets `_rebuilding = True` first.

---

### Pitfall 5: Empty State with Mixed Row Types

**What goes wrong:** The existing empty state logic uses `_visible_count` (incremented in `_filter_func`) to detect zero visible rows. With `set_filter_func` removed, `_visible_count` is never incremented.

**How to avoid:** Track empty state explicitly during list rebuild. After `_rebuild_grouped()` or `_rebuild_flat()`, if zero station rows were added, show `self.empty_page`.

---

## Code Examples

### ExpanderRow + ActionRow (verified Adw 1.8.0)

```python
# Source: verified against installed Adw 1.8.0
group = Adw.ExpanderRow()
group.set_title("Soma FM")
group.set_expanded(False)

ar = Adw.ActionRow(title="Groove Salad", subtitle="Ambient")
ar.set_activatable(True)
pic = Gtk.Picture.new_for_filename("/path/to/art.png")
pic.set_size_request(48, 48)
pic.set_content_fit(Gtk.ContentFit.COVER)
ar.add_prefix(pic)
ar.connect("activated", lambda r: play_station(station_id))
group.add_row(ar)
self.listbox.append(group)
```

### SQLite alter-table migration (established pattern)

```python
# In db_init() — follows existing icy_disabled migration pattern
try:
    con.execute("ALTER TABLE stations ADD COLUMN last_played_at TEXT")
    con.commit()
except sqlite3.OperationalError:
    pass
```

### Hiding Recently Played section

```python
# Simplest: set_visible on a container Box, or on each RP row
# Since rows are in the ListBox directly, simplest is set_visible on each
def _set_recently_played_visible(self, visible: bool):
    for row in self._rp_rows:  # list of refs to RP rows (header + station rows)
        row.set_visible(visible)
```

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (inferred from existing `tests/` directory) |
| Config file | `pyproject.toml` (no `[tool.pytest]` section yet — pytest runs with defaults) |
| Quick run command | `pytest tests/test_repo.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| BROWSE-01 | `Adw.ExpanderRow` groups created per provider | manual/smoke | N/A — GTK requires display | N/A |
| BROWSE-01 | Grouped list rebuild logic (grouping by provider_name) | unit | `pytest tests/test_repo.py -x -q` | ✅ |
| BROWSE-04 | `update_last_played` stores ISO datetime in DB | unit | `pytest tests/test_repo.py::test_update_last_played -x` | ❌ Wave 0 |
| BROWSE-04 | `list_recently_played(n)` returns top-N ordered by recency | unit | `pytest tests/test_repo.py::test_list_recently_played -x` | ❌ Wave 0 |
| BROWSE-04 | `last_played_at` column migration (existing DB) | unit | `pytest tests/test_repo.py::test_last_played_migration -x` | ❌ Wave 0 |
| D-08 | `get_setting` / `set_setting` round-trip | unit | `pytest tests/test_repo.py::test_settings_round_trip -x` | ❌ Wave 0 |
| D-08 | `get_setting` returns default when key absent | unit | `pytest tests/test_repo.py::test_settings_default -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_repo.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_repo.py` — add `test_update_last_played`, `test_list_recently_played`, `test_last_played_migration`, `test_settings_round_trip`, `test_settings_default` (new test functions in existing file)

*(No new test files needed — all new repo methods fit naturally in `tests/test_repo.py`.)*

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `set_filter_func` for station rows | Explicit list rebuild per render mode | Phase 7 | `set_filter_func` cannot see ExpanderRow children; rebuild is simpler |
| Flat `StationRow` list | GROUPED mode (ExpanderRows) + FLAT mode (StationRows) | Phase 7 | Two render paths required |
| No play history | `last_played_at` column + Recently Played section | Phase 7 | Schema migration needed |

---

## Open Questions

1. **Recently Played section visibility implementation**
   - What we know: Use `set_visible()` toggle per D-15
   - What's unclear: Best granularity — hide/show individual rows vs a container widget wrapping them all
   - Recommendation: Store RP row references in `self._rp_rows: list` (header + station rows). Call `set_visible(visible)` on each. Simple, no extra container widget.

2. **_edit_selected with grouped view**
   - What we know: `_edit_selected` calls `listbox.get_selected_row()` — returns the currently selected top-level row
   - What's unclear: If user clicks a station inside an ExpanderRow, does `get_selected_row()` return the ExpanderRow or nothing?
   - Recommendation: In grouped mode, Edit button can be disabled or use a different mechanism. The phase scope doesn't mention Edit behavior changes — flag as a known limitation for now; Edit still works for Recently Played rows (direct ListBox children) and in flat mode.

---

## Sources

### Primary (HIGH confidence)

- Adw 1.8.0 installed library — `ExpanderRow.add_row()`, `set_expanded()`, `ActionRow.activated` signal, `Gtk.ListBox.set_filter_func` scope — verified via Python introspection and smoke tests in this session
- `musicstreamer/repo.py` — existing migration pattern (`ALTER TABLE ... ADD COLUMN icy_disabled`)
- `musicstreamer/ui/main_window.py` — `reload_list()`, `_on_filter_changed()`, `_rebuilding` guard, `_visible_count` pattern
- `musicstreamer/ui/station_row.py` — existing `StationRow` widget structure
- `tests/test_repo.py` — existing test fixture pattern (`repo` fixture with `tmp_path`)

### Secondary (MEDIUM confidence)

- Adwaita HIG — ExpanderRow usage for collapsible content sections (inferred from widget design)

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — verified against installed Adw 1.8.0; all widget APIs confirmed via introspection
- Architecture: HIGH — filter_func limitation confirmed by direct testing; render mode approach derived from verified behavior
- Pitfalls: HIGH — all pitfalls confirmed by live Python tests in this session, not inferred

**Research date:** 2026-03-22
**Valid until:** 2026-06-22 (stable GTK4/Adw API)
