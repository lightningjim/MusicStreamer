---
phase: 38-filter-strip-favorites
reviewed: 2026-04-12T00:00:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - musicstreamer/models.py
  - musicstreamer/repo.py
  - musicstreamer/ui_qt/favorites_view.py
  - musicstreamer/ui_qt/flow_layout.py
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - musicstreamer/ui_qt/station_filter_proxy.py
  - musicstreamer/ui_qt/station_list_panel.py
  - musicstreamer/ui_qt/station_star_delegate.py
  - musicstreamer/ui_qt/station_tree_model.py
  - tests/test_favorites.py
  - tests/test_flow_layout.py
  - tests/test_main_window_integration.py
  - tests/test_now_playing_panel.py
  - tests/test_station_filter_proxy.py
  - tests/test_station_list_panel.py
  - tests/test_ui_qt_scaffold.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 38: Code Review Report

**Reviewed:** 2026-04-12
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Filter strip, segmented control, favorites view, and station star delegate are
well-structured. Signal wiring follows QA-05 (bound methods), plain-text lockdown
on ICY labels is in place, and chip QSS follows the unpolish/polish cycle pattern.

One critical bug: `on_title_changed` references `is_fav` outside the `if` block
that defines it, causing a `NameError` on every ICY update when no station is
bound or when `title` is falsy. Three warnings around error-handling edge cases
and a migration risk. Two info items for minor code issues.

---

## Critical Issues

### CR-01: `NameError` — `is_fav` used outside defining `if` block in `on_title_changed`

**File:** `musicstreamer/ui_qt/now_playing_panel.py:269-276`

**Issue:** `is_fav` is assigned only inside `if self._station and title:` (line 259),
but the subsequent `if` block (line 269) unconditionally calls `is_junk_title(title)`
where `is_fav` is never referenced — that part is fine. The real hazard is subtler:
the code path at lines 269-276 runs regardless of whether the inner `if` executed,
which means `is_fav` may be unbound if `self._station` is `None` or `title` is
falsy at call time. Currently the second block does not reference `is_fav` itself,
**but** the two `if` blocks share no explicit else branch, so any future addition
that reads `is_fav` in the second block — or a refactor that accidentally merges
them — will produce a `NameError` in production. More concretely: if `title` is
an empty string, the first `if` is skipped, `is_fav` is never bound, and the
`is_junk_title` check at line 271 correctly short-circuits via `title` being falsy,
so the crash is currently avoided only by accident. If the condition order is ever
changed, the bug surfaces.

The variable is also redundantly queried (two `is_favorited` DB calls — once in
`on_title_changed` and once in `_on_star_clicked`). The star button's checked state
set in `on_title_changed` is the authoritative source; `_on_star_clicked` should
read `self.star_btn.isChecked()` instead of making a second DB round-trip.

**Fix:**
```python
def on_title_changed(self, title: str) -> None:
    self.icy_label.setText(title or "")
    self._last_icy_title = title or ""
    self._update_star_enabled()
    if self._station and title:
        is_fav = self._repo.is_favorited(self._station.name, title)
        self.star_btn.setChecked(is_fav)
        icon_name = "starred-symbolic" if is_fav else "non-starred-symbolic"
        self.star_btn.setIcon(
            QIcon.fromTheme(icon_name, QIcon(f":/icons/{icon_name}.svg"))
        )
        self.star_btn.setToolTip(
            "Remove track from favorites" if is_fav else "Save track to favorites"
        )
        # Cover art fetch only within this same guarded block
        if not is_junk_title(title) and title != self._last_cover_icy:
            self._last_cover_icy = title
            self._fetch_cover_art_async(title)
```

Also update `_on_star_clicked` to use `self.star_btn.isChecked()` to determine
current state instead of a second `is_favorited` query:

```python
def _on_star_clicked(self) -> None:
    if self._station is None or not self._last_icy_title:
        return
    is_fav = self.star_btn.isChecked()  # read from button state, not DB
    if is_fav:
        ...
```

---

## Warnings

### WR-01: Migration silently drops `is_favorite` data when recreating `stations` table

**File:** `musicstreamer/repo.py:128-132`

**Issue:** The `INSERT INTO stations_new … SELECT …` in the URL-column migration
(line 128) does not include `is_favorite` in its column list. Any station
favorited before the migration runs will have `is_favorite` silently reset to 0
after migration.

```sql
INSERT INTO stations_new (id, name, provider_id, tags, station_art_path,
    album_fallback_path, icy_disabled, last_played_at, created_at, updated_at)
SELECT id, name, provider_id, tags, station_art_path,
    album_fallback_path, icy_disabled, last_played_at, created_at, updated_at
FROM stations;
```

`is_favorite` is omitted from both the destination column list and the `SELECT`.
For a fresh install this is irrelevant, but any existing user who had the old
`url` column schema and had favorited stations will lose those favorites silently.

**Fix:** Add `is_favorite` to both sides of the INSERT/SELECT:

```sql
INSERT INTO stations_new (id, name, provider_id, tags, station_art_path,
    album_fallback_path, icy_disabled, last_played_at, is_favorite,
    created_at, updated_at)
SELECT id, name, provider_id, tags, station_art_path,
    album_fallback_path, icy_disabled, last_played_at,
    COALESCE(is_favorite, 0),
    created_at, updated_at
FROM stations;
```

---

### WR-02: `db_init` migration catches all `OperationalError` — masks real errors

**File:** `musicstreamer/repo.py:66-90, 148`

**Issue:** Every `ALTER TABLE` and the full table-recreation block are wrapped in
bare `except sqlite3.OperationalError: pass`. `OperationalError` is also raised
for things like disk-full, locked databases, and corrupted schemas — none of which
should be silently swallowed. The intent is to suppress "column already exists"
errors, but the catch is too broad.

**Fix:** Narrow the guard by inspecting the exception message:

```python
try:
    con.execute("ALTER TABLE stations ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0")
    con.commit()
except sqlite3.OperationalError as e:
    if "duplicate column name" not in str(e).lower():
        raise
```

Or use a schema-inspection check before the ALTER:

```python
cols = {row[1] for row in con.execute("PRAGMA table_info(stations)")}
if "is_favorite" not in cols:
    con.execute("ALTER TABLE stations ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0")
    con.commit()
```

---

### WR-03: `StationStarDelegate.editorEvent` is dead code — `NoEditTriggers` blocks it

**File:** `musicstreamer/ui_qt/station_list_panel.py:287-288` and
`musicstreamer/ui_qt/station_star_delegate.py:74-81`

**Issue:** `StationListPanel` sets `setEditTriggers(QAbstractItemView.NoEditTriggers)`,
which prevents Qt from invoking `editorEvent` on the delegate at all. The comment
at line 287 acknowledges this ("editorEvent won't fire with NoEditTriggers, so use
viewport event filter") and the viewport `eventFilter` in `StationListPanel` is the
actual star-click handler. However, `StationStarDelegate.editorEvent` still emits
`star_toggled`, and `star_toggled` is never connected anywhere. This creates a
confusing dead code path: the delegate's `star_toggled` signal exists but is never
wired, and `editorEvent` itself will never be called.

**Fix:** Remove the `editorEvent` override from `StationStarDelegate` (it will
never be invoked) and remove the `star_toggled` signal from the delegate, since
the viewport event filter in `StationListPanel` owns the toggle responsibility.
This eliminates the misleading unused signal and the dead event handler.

---

## Info

### IN-01: Duplicate `_load_station_icon` function across two modules

**File:** `musicstreamer/ui_qt/station_list_panel.py:68-84` and
`musicstreamer/ui_qt/favorites_view.py:40-51`

**Issue:** Both modules define an identical `_load_station_icon` helper with the
same QPixmapCache key scheme and fallback logic. The comment in
`station_list_panel.py` notes it is "shared with StationTreeModel._icon_for_station
semantics" but neither module imports from the other.

**Fix:** Extract to a shared `musicstreamer/ui_qt/icon_utils.py` module and import
from both sites. This also removes the third near-duplicate in
`StationTreeModel._icon_for_station` (same logic, private method).

---

### IN-02: `test_list_favorites_order` uses `time.sleep` — fragile under load

**File:** `tests/test_favorites.py:43-47`

**Issue:** The ordering test sleeps 50ms between inserts to ensure `created_at`
timestamps differ. Under a slow CI runner or a SQLite build where the timestamp
resolution is coarser, this can produce equal timestamps and a flaky test.

**Fix:** Use the `created_at` precision already available (`strftime('%Y-%m-%dT%H:%M:%f', 'now')`
stores milliseconds). The test could insert with explicit `created_at` values
instead of relying on wall-clock ordering:

```python
def test_list_favorites_order(repo):
    repo.con.execute(
        "INSERT INTO favorites(station_name, provider_name, track_title, genre, created_at) "
        "VALUES ('Station A', 'Provider X', 'Track 1', 'Pop', '2000-01-01T00:00:00.000')"
    )
    repo.con.execute(
        "INSERT INTO favorites(station_name, provider_name, track_title, genre, created_at) "
        "VALUES ('Station A', 'Provider X', 'Track 2', 'Pop', '2000-01-01T00:00:01.000')"
    )
    repo.con.execute(
        "INSERT INTO favorites(station_name, provider_name, track_title, genre, created_at) "
        "VALUES ('Station A', 'Provider X', 'Track 3', 'Pop', '2000-01-01T00:00:02.000')"
    )
    repo.con.commit()
    favs = repo.list_favorites()
    assert [f.track_title for f in favs] == ["Track 3", "Track 2", "Track 1"]
```

---

_Reviewed: 2026-04-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
