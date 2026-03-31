# Phase 12: Favorites - Research

**Researched:** 2026-03-30
**Domain:** GTK4/libadwaita UI, SQLite persistence, ICY metadata integration
**Confidence:** HIGH

## Summary

Phase 12 adds a star-favorites feature: a star button in the now-playing panel, a `favorites` SQLite table, and an `Adw.ToggleGroup` toggle to switch the sidebar between Stations and Favorites views. All decisions are locked in CONTEXT.md — this research confirms implementation approach and surfaces concrete API details from the installed environment.

The codebase is well-structured for this addition. `repo.py` follows a clear migration pattern (try/except ALTER TABLE / CREATE TABLE IF NOT EXISTS). `main_window.py` has a single `Gtk.Stack`-based content swap pattern already proven for empty state. `cover_art.py` exposes `is_junk_title()` already used as a gate. The only nontrivial design question is genre capture: `_parse_artwork_url()` currently returns only the artwork URL string — it needs a companion function or return-value expansion to surface `primaryGenreName`.

**Primary recommendation:** Add `_parse_itunes_result()` returning a small named tuple or dict `{artwork_url, genre}`, cache it in `MainWindow._last_itunes_result`, and read it at star-click time. No second iTunes call needed.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Toggle placed above the station list area — a row containing an `Adw.ToggleGroup` with two segments: "Stations" and "Favorites"
- **D-02:** Widget: `Adw.ToggleGroup` (native Adwaita segmented control, HIG-compliant)
- **D-03:** Switching views replaces the list content inline — no navigation, no page transitions
- **D-04:** Filter bar (provider/tag chips) is hidden or inactive when Favorites view is active
- **D-05:** Star button lives in the center column of the now-playing panel, to the left of the Stop button
- **D-06:** Icon state: `non-starred-symbolic` (outline) / `starred-symbolic` (filled)
- **D-07:** Button is hidden (not just disabled) when no actionable ICY title
- **D-08:** Star state updates immediately on click (optimistic UI); DB write is synchronous
- **D-09:** Each row shows: primary = track title; secondary = "Station Name · Provider"
- **D-10:** No date/timestamp in the row
- **D-11:** Trash icon always visible, one tap removes immediately (no confirmation)
- **D-12:** Deduplication key: `(station_name, track_title)` — duplicate star silently no-ops
- **D-13:** Genre captured from iTunes API response; cache last parsed iTunes result alongside `_last_cover_icy`

### Claude's Discretion

- Exact widget hierarchy for toggle row (e.g., `Gtk.Box` with margins or `Adw.ActionRow`)
- Whether filter bar is `set_visible(False)` or `set_sensitive(False)` in Favorites view
- DB migration approach for `favorites` table
- Order of favorites list (insert order / `created_at` descending)

### Deferred Ideas (OUT OF SCOPE)

None.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FAVES-01 | Star the currently playing ICY track title (star button in now-playing, gated on non-junk title) | `is_junk_title()` gate confirmed; `Gtk.Button.set_visible()` is the hide mechanism; `_on_title` callback is the correct hook |
| FAVES-02 | Stored in DB: station name, provider name, track title, iTunes genre (denormalized) | `CREATE TABLE IF NOT EXISTS favorites` in `db_init()`; `_parse_artwork_url` needs expansion to expose `primaryGenreName` |
| FAVES-03 | Toggle between Stations and Favorites inline via sidebar control | `Adw.ToggleGroup` + `Adw.Toggle` confirmed present in libadwaita 1.8.0; `notify::active-name` signal for change detection; `shell.add_top_bar()` insertion point |
| FAVES-04 | Remove a track from Favorites view | Per-row `Gtk.Button` with `user-trash-symbolic`; `repo.remove_favorite()` + UI row removal |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GTK4 | 4.20 (installed) | Widget toolkit | Project standard, system package |
| libadwaita | 1.8.0 (installed) | GNOME HIG widgets | Project standard; `Adw.ToggleGroup` confirmed available |
| SQLite (stdlib) | 3.x | Favorites persistence | Already used for all DB operations |
| Python stdlib | 3.10+ | Threading, JSON, urllib | No new dependencies needed |

**No new dependencies required for this phase.** All needed libraries are already installed system packages.

### New Widgets Confirmed Available (libadwaita 1.8.0)
| Widget | Availability | Notes |
|--------|-------------|-------|
| `Adw.ToggleGroup` | Confirmed | `hasattr(Adw, 'ToggleGroup')` → True |
| `Adw.Toggle` | Confirmed | Constructor: `Adw.Toggle(label=..., name=...)` |
| `Adw.StatusPage` | Already used | Empty-state pattern proven in codebase |

---

## Architecture Patterns

### Adw.ToggleGroup Usage (verified against installed 1.8.0)

```python
# Source: live introspection of gi.repository.Adw 1.8.0
toggle_group = Adw.ToggleGroup()
toggle_group.set_halign(Gtk.Align.CENTER)
toggle_group.set_margin_top(8)
toggle_group.set_margin_bottom(8)

stations_toggle = Adw.Toggle(label="Stations", name="stations")
favorites_toggle = Adw.Toggle(label="Favorites", name="favorites")
toggle_group.add(stations_toggle)
toggle_group.add(favorites_toggle)
toggle_group.set_active_name("stations")

# Connect to property change (not a signal, use notify)
toggle_group.connect("notify::active-name", self._on_view_toggled)

# In handler:
def _on_view_toggled(self, group, _pspec):
    name = group.get_active_name()  # "stations" or "favorites"
```

**API confirmed:** `get_active_name()`, `set_active_name()`, `add()` (takes `Adw.Toggle`), `notify::active-name` property notification.

### DB Schema for Favorites

```python
# In db_init() — follows established try/except pattern
try:
    con.executescript("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_name TEXT NOT NULL,
            provider_name TEXT NOT NULL DEFAULT '',
            track_title TEXT NOT NULL,
            genre TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(station_name, track_title)
        );
    """)
    con.commit()
except sqlite3.OperationalError:
    pass
```

`UNIQUE(station_name, track_title)` enforces D-12 deduplication at the DB level. `INSERT OR IGNORE` on `add_favorite()` silently skips duplicates.

### Repo Methods to Add

```python
def add_favorite(self, station_name: str, provider_name: str,
                 track_title: str, genre: str) -> None:
    self.con.execute(
        "INSERT OR IGNORE INTO favorites(station_name, provider_name, track_title, genre) "
        "VALUES (?, ?, ?, ?)",
        (station_name, provider_name or "", track_title, genre or ""),
    )
    self.con.commit()

def remove_favorite(self, station_name: str, track_title: str) -> None:
    self.con.execute(
        "DELETE FROM favorites WHERE station_name = ? AND track_title = ?",
        (station_name, track_title),
    )
    self.con.commit()

def list_favorites(self) -> list["Favorite"]:
    rows = self.con.execute(
        "SELECT * FROM favorites ORDER BY created_at DESC"
    ).fetchall()
    return [Favorite(...) for r in rows]

def is_favorited(self, station_name: str, track_title: str) -> bool:
    row = self.con.execute(
        "SELECT 1 FROM favorites WHERE station_name = ? AND track_title = ?",
        (station_name, track_title),
    ).fetchone()
    return row is not None
```

### Favorite Dataclass

```python
# In models.py
@dataclass
class Favorite:
    id: int
    station_name: str
    provider_name: str
    track_title: str
    genre: str
    created_at: Optional[str] = None
```

### Genre Capture from iTunes

`cover_art.py._parse_artwork_url()` currently returns only `str | None`. Needs to be split or augmented to expose `primaryGenreName`.

**Recommended approach:** Add `_parse_itunes_result()` returning a dict:

```python
def _parse_itunes_result(json_bytes: bytes) -> dict:
    """Return {'artwork_url': str|None, 'genre': str} from iTunes JSON."""
    data = json.loads(json_bytes)
    if not data.get("resultCount", 0) or not data.get("results"):
        return {"artwork_url": None, "genre": ""}
    result = data["results"][0]
    artwork_url = result.get("artworkUrl100")
    if artwork_url:
        artwork_url = artwork_url.replace("100x100", "160x160")
    genre = result.get("primaryGenreName", "")
    return {"artwork_url": artwork_url, "genre": genre}
```

Cache in `MainWindow`:
```python
self._last_itunes_result: dict = {}  # {"artwork_url": ..., "genre": ...}
```

Set in `_on_art_fetched` callback (GLib.idle_add context), read at star-click time. `_on_cover_art` already deduplicates on `_last_cover_icy`, so genre will be fresh for the current title.

**Threading note:** `_on_art_fetched` already runs inside `GLib.idle_add(_update_ui)`, so writing `self._last_itunes_result` there is safe (main thread). Star button click is also on the main thread. No locking needed.

### View Toggle Integration

The toggle group wraps in a `Gtk.Box` and is added as a top bar after `filter_box`:

```python
toggle_box = Gtk.Box()
toggle_box.set_halign(Gtk.Align.CENTER)
toggle_box.set_margin_top(8)
toggle_box.set_margin_bottom(8)
toggle_box.append(self.view_toggle)
shell.add_top_bar(toggle_box)
```

`filter_box` is stored as `self.filter_box` to allow `set_visible(False)` in Favorites mode.

### Favorites List Rendering

Favorites view uses the **same `self.listbox`** but cleared and repopulated with `Adw.ActionRow` widgets instead of `StationRow`/`ExpanderRow`. The `shell.set_content()` swap pattern is already proven for empty state and can serve the favorites empty state (`Adw.StatusPage` "No favorites yet").

Track current view mode with:
```python
self._view_mode: str = "stations"  # "stations" | "favorites"
```

### Star Button Insertion

Star button inserts into `center` box between `station_name_label` and `stop_btn`:

```python
self.star_btn = Gtk.Button()
self.star_btn.set_icon_name("non-starred-symbolic")
self.star_btn.set_halign(Gtk.Align.START)
self.star_btn.set_visible(False)
self.star_btn.set_tooltip_text("Add to favorites")
self.star_btn.connect("clicked", self._on_star_clicked)
center.append(self.star_btn)   # append before stop_btn
center.append(self.stop_btn)   # re-order: remove stop_btn append from earlier, append here
```

Wait — the `stop_btn` is already appended to `center` at line 94. Star button must be **inserted** before it. GTK4's `Gtk.Box` has no `insert_child_after` at API level — instead, **build in correct order**: append `star_btn` before appending `stop_btn`. This requires reordering the constructor code, not inserting after the fact.

Actually GTK4 does have `insert_child_after()` on `Gtk.Box` (inherited from `Gtk.Widget`). But the cleanest approach is to reorder construction so `star_btn` is appended to `center` before `stop_btn`.

### Anti-Patterns to Avoid

- **Using `Gtk.Box.insert_child_after()` after-the-fact** when reordering construction is possible — reorder construction for clarity.
- **Re-calling `_parse_artwork_url()` at star-click time** — adds a redundant iTunes call; use cached `_last_itunes_result` instead.
- **Storing station_id in favorites** — denormalized by design (D-13); station deletion must not break favorites.
- **Using `set_sensitive(False)` on filter_box** instead of `set_visible(False)` — UI spec calls for `set_visible(False)` (Claude's Discretion resolved in UI-SPEC line 153).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Deduplication | Custom check-before-insert logic | `INSERT OR IGNORE` with `UNIQUE(station_name, track_title)` |
| Empty state | Custom visibility toggle | `Adw.StatusPage` + `shell.set_content()` swap |
| Segmented toggle | Custom `Gtk.ToggleButton` pair | `Adw.ToggleGroup` + `Adw.Toggle` |
| Destructive styling | Custom CSS red button | `.destructive-action` CSS class on `Gtk.Button` |

---

## Common Pitfalls

### Pitfall 1: `_parse_artwork_url()` discards genre
**What goes wrong:** Current function returns only `str | None`, discarding `primaryGenreName` from iTunes JSON. Storing empty genre in DB without fixing this.
**Why it happens:** Function was written for cover art only; genre was not needed until now.
**How to avoid:** Add `_parse_itunes_result()` that returns both fields. Update `fetch_cover_art` to use it and pass genre to callback or cache separately.

### Pitfall 2: Star button visible while `_current_station` is None
**What goes wrong:** Edge case — if stop is called and `_last_cover_icy` is not cleared before `_on_title` fires, star_btn might stay visible.
**How to avoid:** `_stop()` must call `star_btn.set_visible(False)` and clear `_last_itunes_result`.

### Pitfall 3: `notify::active-name` fires before toggles are added
**What goes wrong:** Signal fires during initialization if `set_active_name()` is called before connecting the handler.
**How to avoid:** Connect handler after both toggles are added and default active name is set. Or guard with `if self._view_mode == name: return` in handler.

### Pitfall 4: Favorites list uses `_rp_rows` logic
**What goes wrong:** `_refresh_recently_played()` and `_render_list()` both operate on `self.listbox`; if called while in Favorites mode, they corrupt the view.
**How to avoid:** Guard `_refresh_recently_played()` and `_render_list()` with `if self._view_mode != "stations": return`.

### Pitfall 5: Trash button removes by index rather than identity
**What goes wrong:** If list is rebuilt during removal, index-based row removal removes the wrong item.
**How to avoid:** Capture `(station_name, track_title)` in closure at row creation time, not the row index.

### Pitfall 6: `Adw.ActionRow` markup injection
**What goes wrong:** Track titles with `&`, `<`, `>` break Pango markup parsing in `Adw.ActionRow`.
**Already handled:** Use `GLib.markup_escape_text(value, -1)` — established pattern per CONTEXT.md and UI-SPEC.

---

## Code Examples

### Favorites row construction
```python
# Source: UI-SPEC.md + existing _make_action_row() pattern in main_window.py
row = Adw.ActionRow(
    title=GLib.markup_escape_text(fav.track_title, -1),
    subtitle=GLib.markup_escape_text(
        f"{fav.station_name} \u00b7 {fav.provider_name}", -1
    ),
)
row.add_css_class("favorites-list-row")

trash_btn = Gtk.Button()
trash_btn.set_icon_name("user-trash-symbolic")
trash_btn.add_css_class("destructive-action")
trash_btn.add_css_class("flat")
trash_btn.set_valign(Gtk.Align.CENTER)
trash_btn.connect("clicked", lambda _, sn=fav.station_name, tt=fav.track_title:
    self._remove_favorite(sn, tt))
row.add_suffix(trash_btn)
```

### Star click handler
```python
def _on_star_clicked(self, _btn):
    if not self._current_station or not self._last_cover_icy:
        return
    title = self._last_cover_icy
    station = self._current_station
    if self.repo.is_favorited(station.name, title):
        self.repo.remove_favorite(station.name, title)
        self.star_btn.set_icon_name("non-starred-symbolic")
        self.star_btn.set_tooltip_text("Add to favorites")
    else:
        genre = self._last_itunes_result.get("genre", "")
        self.repo.add_favorite(
            station.name,
            station.provider_name or "",
            title,
            genre,
        )
        self.star_btn.set_icon_name("starred-symbolic")
        self.star_btn.set_tooltip_text("Remove from favorites")
```

---

## State of the Art

| Old Pattern | Current Pattern | Impact |
|-------------|-----------------|--------|
| `try: ALTER TABLE ADD COLUMN` | `CREATE TABLE IF NOT EXISTS` (new table, not column) | Favorites table uses cleaner `CREATE TABLE IF NOT EXISTS` inside `executescript`; no try/except needed for new table |

**Note:** The `icy_disabled` and `last_played_at` columns used `ALTER TABLE` because they were added to an existing table. The `favorites` table is new — use `CREATE TABLE IF NOT EXISTS` directly inside the existing `executescript` call (no migration try/except needed). However, wrapping in try/except is also fine for consistency. Preference: add directly to `executescript` for cleanliness.

---

## Environment Availability

Step 2.6: No new external dependencies. All required tools are system GTK4/libadwaita packages already installed and verified.

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| libadwaita | Adw.ToggleGroup, Adw.Toggle | Yes | 1.8.0 | — |
| GTK4 | Gtk.Button, Gtk.ListBox | Yes | 4.20 | — |
| SQLite | favorites table | Yes | stdlib | — |
| `starred-symbolic` icon | star button | Yes (Adwaita) | system | — |
| `user-trash-symbolic` icon | trash button | Yes (Adwaita) | system | — |
| `non-starred-symbolic` icon | star button | Yes (Adwaita) | system | — |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing, 85 tests passing) |
| Config file | none (pytest auto-discovery from project root) |
| Quick run command | `python3 -m pytest tests/test_repo.py -q` |
| Full suite command | `python3 -m pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FAVES-01 | `is_junk_title()` gates star button | unit | `pytest tests/test_cover_art.py -q` | Yes (cover_art tests exist) |
| FAVES-02 | `add_favorite()` stores record; `is_favorited()` returns True; duplicate insert is no-op | unit | `pytest tests/test_repo.py -q` | Yes (needs new test cases) |
| FAVES-02 | `list_favorites()` returns rows ordered by `created_at DESC` | unit | `pytest tests/test_repo.py -q` | Yes (needs new test cases) |
| FAVES-03 | `Adw.ToggleGroup` active-name switching (UI) | manual-only | — | — (GTK4 UI, no headless testing) |
| FAVES-04 | `remove_favorite()` deletes record | unit | `pytest tests/test_repo.py -q` | Yes (needs new test cases) |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_repo.py -q`
- **Per wave merge:** `python3 -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_repo.py` — add favorites test cases (add, remove, list, is_favorited, duplicate no-op, db_init idempotent) — covers FAVES-02, FAVES-04

*(Existing test infrastructure is complete; only new test cases needed within `test_repo.py`, no new test files required.)*

---

## Open Questions

1. **`fetch_cover_art()` callback signature change**
   - What we know: `_on_art_fetched(temp_path)` currently receives only a path string.
   - What's unclear: Should genre be passed through callback, or cached separately in a module-level dict / returned from a new `fetch_itunes_data()` function?
   - Recommendation: Keep `fetch_cover_art(icy, callback)` signature unchanged. Add a parallel `fetch_itunes_metadata(icy, callback)` or change internal `_worker` to also invoke a separate metadata callback. Simplest: cache genre in `MainWindow` directly by expanding `_on_cover_art` to call a new `_parse_itunes_result()` that returns `{artwork_url, genre}` and store it as `self._last_itunes_result`. This avoids changing `fetch_cover_art()`'s public signature.

---

## Sources

### Primary (HIGH confidence)
- Live introspection: `gi.repository.Adw` version 1.8.0 — `Adw.ToggleGroup`, `Adw.Toggle` API surface
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/repo.py` — migration pattern, `db_init`, `Repo` class
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/cover_art.py` — `_parse_artwork_url`, threading model
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui/main_window.py` — widget hierarchy, `_on_title`, `_on_cover_art`, `_stop`
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/models.py` — `Station`, `Provider` dataclasses

### Secondary (MEDIUM confidence)
- `.planning/phases/12-favorites/12-CONTEXT.md` — locked decisions
- `.planning/phases/12-favorites/12-UI-SPEC.md` — widget specifications

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — installed versions verified by live Python introspection
- Architecture: HIGH — all patterns derived from existing codebase or live API inspection
- Pitfalls: HIGH — derived from actual code paths in `main_window.py` and `cover_art.py`

**Research date:** 2026-03-30
**Valid until:** 2026-06-30 (stable GTK4/libadwaita stack)
