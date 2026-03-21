# Phase 06: Station Management - Research

**Researched:** 2026-03-21
**Domain:** GTK4/libadwaita Python desktop — station CRUD, yt-dlp thumbnail fetch, ICY playback override
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Delete UX**
- Delete action lives inside `EditStationDialog` (not a row button or context menu)
- Confirmation required: `Adw.MessageDialog` with "Delete [Station Name]?" and Cancel / Delete buttons
- If the station being deleted is currently playing: block the delete and show an error/warning — user must stop playback first
- After confirmed delete: close the dialog, remove the station from the list, no further action needed

**YouTube Thumbnail Fetch**
- Auto-fetch triggers on URL field focus-out (when user leaves the URL entry)
- A persistent "Fetch from URL" button also exists in the dialog for manual re-fetch
- Both auto-fetch and manual button always replace station art, even if art is already set
- During fetch: show a `Gtk.Spinner` in the station art preview slot
- Only triggered for YouTube URLs (detect `youtube.com` or `youtu.be` in the URL)
- Use yt-dlp (already a dependency) to retrieve the thumbnail URL, then download and store via `copy_asset_for_station`

**ICY Override**
- Toggle lives in `EditStationDialog`: an `Adw.SwitchRow` labeled "Disable ICY metadata"
- Persisted to DB as a new `icy_disabled` boolean column on the `stations` table (DEFAULT 0, backward-compatible migration via `ALTER TABLE`)
- `Station` dataclass gets a new `icy_disabled: bool` field
- During playback: if `icy_disabled` is True, suppress ICY TAG bus events and show the station name in the title label instead

### Claude's Discretion
- Exact placement of the Delete button within the dialog (e.g., destructive-action footer vs header)
- Threading model for the yt-dlp thumbnail fetch (daemon thread + GLib.idle_add, same pattern as cover_art.py)
- Error handling when yt-dlp cannot retrieve a thumbnail (silent no-op or status label)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MGMT-01 | User can delete a station from the station list | `Repo.delete_station()` (new), `Adw.MessageDialog` confirm flow, `MainWindow.reload_list()` callback pattern already in place |
| MGMT-02 | Station editor auto-populates station image from YouTube thumbnail when a YouTube URL is entered | `yt-dlp --print thumbnail` extracts URL; daemon thread + `GLib.idle_add` pattern from `cover_art.py`; `copy_asset_for_station` stores result |
| ICY-01 | User can disable ICY metadata per station | `ALTER TABLE` migration for `icy_disabled` column; `Station.icy_disabled` field; guard in `_on_title` callback in `main_window.py` |
</phase_requirements>

---

## Summary

All three features are tightly scoped to two files (`repo.py` / `models.py`) and one UI file (`edit_dialog.py`), with a one-line guard added to `main_window.py` for ICY suppression. The codebase already provides all the patterns and helpers needed — there is nothing to design from scratch.

The riskiest piece is the yt-dlp thumbnail fetch: the subprocess call is synchronous, so it must run on a daemon thread to avoid blocking the GTK main loop. The `cover_art.py` daemon threading pattern is the exact model to replicate. The `Gtk.Spinner` swap requires careful state management to handle races (user triggers fetch twice, or closes dialog mid-fetch).

The DB migration is a single `ALTER TABLE ADD COLUMN` statement that is safe to run at startup. `list_stations` and `get_station` queries must be updated to select and map the new column, and `update_station` must accept the new parameter.

**Primary recommendation:** Implement in three independent tasks — (1) DB/model changes + delete, (2) ICY toggle wiring, (3) yt-dlp thumbnail fetch — in that order, since tasks 2 and 3 both depend on the `icy_disabled` model field being present.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GTK4 (gi.repository.Gtk) | 4.x (system) | All UI widgets | Already the project stack |
| libadwaita (gi.repository.Adw) | 1.x (system) | `Adw.SwitchRow`, `Adw.MessageDialog` | Already the project stack |
| sqlite3 | stdlib | DB migrations and CRUD | Already in use via `repo.py` |
| yt-dlp | 2026.03.17 (verified on host) | YouTube thumbnail URL extraction | Already a project dependency; `--print thumbnail` flag confirmed working |
| urllib.request | stdlib | Download thumbnail image bytes | Matches pattern in `cover_art.py` |
| threading | stdlib | Daemon thread for yt-dlp subprocess | Matches pattern in `cover_art.py` |
| GLib.idle_add | gi.repository.GLib | Marshal background-thread results to GTK main loop | Project-wide pattern; mandatory for cross-thread UI updates |

**Installation:** No new dependencies. All libraries already present.

---

## Architecture Patterns

### Recommended Project Structure
No new files needed. Changes are in-place to existing modules:

```
musicstreamer/
├── models.py          # add icy_disabled: bool field to Station
├── repo.py            # add delete_station(), schema migration, update update_station()
├── ui/
│   └── edit_dialog.py # add Delete button, SwitchRow, Fetch button + spinner logic
└── ui/
    └── main_window.py # guard in _on_title for icy_disabled
```

### Pattern 1: SQLite backward-compatible migration

**What:** Add `icy_disabled` column via `ALTER TABLE` at `db_init` time, wrapped in a try/except to tolerate existing DBs.

**When to use:** Any time a new nullable/defaulted column is added to an existing table.

```python
# Idiomatic pattern for the project (repo.py db_init)
try:
    con.execute("ALTER TABLE stations ADD COLUMN icy_disabled INTEGER NOT NULL DEFAULT 0")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists
```

Confidence: HIGH — standard SQLite pattern; no library needed.

### Pattern 2: Daemon thread + GLib.idle_add (yt-dlp fetch)

**What:** Spawn daemon thread for subprocess/network work; marshal result back to GTK loop via `GLib.idle_add`.

**When to use:** Any blocking operation called from a GTK signal handler.

```python
# Source: cover_art.py _worker pattern — replicate for yt-dlp fetch
import threading, subprocess, urllib.request, tempfile
from gi.repository import GLib

def fetch_yt_thumbnail(url: str, callback: callable) -> None:
    def _worker():
        try:
            result = subprocess.run(
                ["yt-dlp", "--print", "thumbnail", "--no-playlist", "--no-download", url],
                capture_output=True, text=True, timeout=15
            )
            thumb_url = result.stdout.strip()
            if not thumb_url:
                GLib.idle_add(callback, None)
                return
            with urllib.request.urlopen(thumb_url, timeout=10) as resp:
                data = resp.read()
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(data)
                GLib.idle_add(callback, tmp.name)
        except Exception:
            GLib.idle_add(callback, None)
    threading.Thread(target=_worker, daemon=True).start()
```

Key notes:
- `--no-download` is not a valid yt-dlp flag; use `--print thumbnail` which skips download implicitly when combined with `--no-playlist`. Confirmed: `yt-dlp --print thumbnail <url>` outputs the URL and exits without downloading.
- `GLib.idle_add` is called from the worker thread — this is correct and required.
- Callback receives `temp_path: str | None`.

Confidence: HIGH — verified locally; pattern matches `cover_art.py`.

### Pattern 3: Spinner swap in art preview slot

**What:** Replace `station_pic` with a `Gtk.Spinner` during fetch; restore on completion.

**When to use:** Any async operation that updates a Gtk.Picture slot.

```python
# In EditStationDialog — spinner replaces station_pic in arts grid
self._fetch_spinner = Gtk.Spinner()
self._fetch_spinner.set_size_request(128, 128)

def _start_spinner(self):
    # swap picture out, spinner in — grid col 0 row 1
    self.arts.remove(self.station_pic)
    self.arts.attach(self._fetch_spinner, 0, 1, 1, 1)
    self._fetch_spinner.start()

def _stop_spinner(self):
    self.arts.remove(self._fetch_spinner)
    self._fetch_spinner.stop()
    self.arts.attach(self.station_pic, 0, 1, 1, 1)
```

Alternative (simpler): use a `Gtk.Stack` with two children ("pic" and "spinner") — avoids grid manipulation. Either approach works; the Stack approach is more reliable if `arts` grid ref isn't straightforward.

Confidence: MEDIUM — no official source checked for Gtk.Stack vs grid removal; both are valid GTK4 patterns.

### Pattern 4: Adw.MessageDialog confirmation

**What:** Modal confirmation before destructive action.

```python
# Source: GNOME HIG / libadwaita
dlg = Adw.MessageDialog(
    transient_for=self,
    heading="Delete Radio Station?",
    body="This station will be permanently removed.",
)
dlg.add_response("cancel", "Keep Station")
dlg.add_response("delete", "Delete")
dlg.set_default_response("cancel")
dlg.set_close_response("cancel")
dlg.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
dlg.connect("response", self._on_delete_response)
dlg.present()
```

Confidence: HIGH — matches project's existing GNOME HIG conventions; `Adw.ResponseAppearance.DESTRUCTIVE` is the correct enum for red styling.

### Pattern 5: "Is currently playing" guard

**What:** `EditStationDialog` must know if its station is the one currently playing. The dialog is opened via `_open_editor(station_id)` in `MainWindow`.

**How to pass the state:** `MainWindow` should pass a callable (or the current station ID) to `EditStationDialog.__init__` so the delete handler can check `current_station_id == self.station_id`.

```python
# main_window.py _open_editor
dlg = EditStationDialog(
    app, repo, station_id,
    on_saved=self.reload_list,
    is_playing=lambda: self._current_station_id == station_id,  # new kwarg
)
```

`MainWindow` needs `self._current_station_id` tracked: set in `_play_station`, cleared in `_stop`.

Currently `MainWindow` does not track `_current_station_id` as an attribute — this must be added.

Confidence: HIGH — code inspection; `_play_station` receives `st: Station` but does not store it as `self._current_station`.

### Anti-Patterns to Avoid

- **Calling yt-dlp synchronously from a GTK signal handler:** Blocks the main loop for several seconds. Always use daemon thread.
- **Accessing `self.station_pic` from the worker thread:** GTK widgets are not thread-safe. All UI manipulation must go through `GLib.idle_add`.
- **Running `ALTER TABLE` unconditionally without catching `OperationalError`:** Will crash on an existing DB that already has the column. Wrap in try/except.
- **Storing `icy_disabled` as Python `bool` in SQLite directly:** SQLite has no bool type; store as `INTEGER` (0/1) and cast in the dataclass. Use `bool(r["icy_disabled"])` in `list_stations`/`get_station`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YouTube thumbnail URL extraction | Custom YouTube API client or HTML scraping | `yt-dlp --print thumbnail` | yt-dlp handles all YouTube URL variants, auth, and format selection; already a project dependency |
| Modal confirmation dialog | Custom dialog class | `Adw.MessageDialog` | Libadwaita provides accessible, HIG-compliant modal with response appearance styling |
| Cross-thread UI updates | Queue or custom signaling | `GLib.idle_add` | Already established project pattern; thread-safe and GTK-idiomatic |

---

## Common Pitfalls

### Pitfall 1: Race condition on double thumbnail fetch
**What goes wrong:** User focuses out of URL field (auto-fetch starts), then immediately clicks "Fetch from URL" button — two concurrent threads, second result may arrive before first and be overwritten.
**Why it happens:** No cancellation mechanism in the daemon thread approach.
**How to avoid:** Add a `self._fetch_in_progress: bool` guard. If True when fetch is triggered, skip the new request (or cancel + restart; but skip is simpler and sufficient).
**Warning signs:** Spinner starts but never stops, or station art flickers.

### Pitfall 2: Dialog closed before fetch completes
**What goes wrong:** User closes `EditStationDialog` mid-fetch; `GLib.idle_add` fires and tries to update `self.station_pic` on a destroyed widget.
**Why it happens:** Daemon thread holds a reference to `self` (the dialog), which may be in a partially destroyed state.
**How to avoid:** Set a `self._fetch_cancelled = True` flag in a `destroy` signal handler. The `GLib.idle_add` callback checks this flag before touching widgets.

### Pitfall 3: `icy_disabled` not propagated to playback guard
**What goes wrong:** ICY toggle is saved to DB but `_play_station` re-fetches the station from DB by ID — if `get_station` doesn't select the new column, `station.icy_disabled` always returns `False`.
**Why it happens:** Forgetting to update the SELECT in `get_station` / `list_stations` after adding the column.
**How to avoid:** Update both `list_stations` and `get_station` row-mapping code in `repo.py` to include `icy_disabled`.

### Pitfall 4: `_on_title` callback fires after station changes
**What goes wrong:** After user switches stations quickly, a stale `_on_title` closure from the previous station fires and overwrites the new station's title.
**Why it happens:** `player.play()` stores `on_title` and calls it from the GStreamer bus — there is a window between `NULL` and `PLAYING` states where stale events can arrive.
**How to avoid:** This is a pre-existing issue (not introduced by this phase). The ICY guard only needs to check `self._current_station.icy_disabled` — which is set at the start of `_play_station`, so it's always the correct station.

### Pitfall 5: yt-dlp JS runtime warning on stdout
**What goes wrong:** `yt-dlp --print thumbnail` prints a WARNING to stderr about missing JS runtime before printing the thumbnail URL to stdout.
**Why it happens:** Host system lacks deno/node; yt-dlp warns but still resolves the URL.
**How to avoid:** Parse only `result.stdout.strip()` — stderr warnings do not pollute stdout. Already confirmed on this system: thumbnail URL is correctly returned on stdout despite the warning.

---

## Code Examples

### Repo: delete_station
```python
# repo.py — new method
def delete_station(self, station_id: int):
    self.con.execute("DELETE FROM stations WHERE id = ?", (station_id,))
    self.con.commit()
```

### Repo: icy_disabled migration + mapping
```python
# db_init addition
try:
    con.execute(
        "ALTER TABLE stations ADD COLUMN icy_disabled INTEGER NOT NULL DEFAULT 0"
    )
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists

# list_stations / get_station row mapping addition
icy_disabled=bool(r["icy_disabled"]),
```

### models.py: Station dataclass update
```python
@dataclass
class Station:
    id: int
    name: str
    url: str
    provider_id: Optional[int]
    provider_name: Optional[str]
    tags: str
    station_art_path: Optional[str]
    album_fallback_path: Optional[str]
    icy_disabled: bool = False  # new field; default False for safety
```

### main_window.py: ICY suppression guard
```python
# _play_station — capture station ref
self._current_station = st

# _on_title closure inside _play_station
def _on_title(title):
    if self._current_station and self._current_station.icy_disabled:
        return  # suppress ICY metadata; title stays as station name
    safe = GLib.markup_escape_text(title, -1)
    self.title_label.set_text(safe)
    self._on_cover_art(title)

# _stop — clear ref
self._current_station = None
```

### yt-dlp invocation (verified)
```bash
# Confirmed working on host (yt-dlp 2026.03.17):
yt-dlp --print thumbnail --no-playlist "https://www.youtube.com/watch?v=jfKfPfyJRdk"
# Output: https://i.ytimg.com/vi/jfKfPfyJRdk/maxresdefault.jpg
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `Adw.AlertDialog` (older libadwaita) | `Adw.MessageDialog` | Project already uses `Adw.MessageDialog`; no change needed |
| Manual thread + queue | `GLib.idle_add` from thread | Project already on idle_add pattern |

---

## Open Questions

1. **Spinner swap implementation**
   - What we know: `station_pic` is attached to `arts` grid at (col=0, row=1). Grid manipulation (remove + attach) works but is verbose.
   - What's unclear: Whether `Gtk.Grid.remove` + `Gtk.Grid.attach` reliably re-attaches to the same cell in all GTK4 versions, vs using a `Gtk.Stack`.
   - Recommendation: Use a `Gtk.Stack` with "pic" and "spinner" children as the grid cell at (0,1) — more robust, easier to reason about state. Decision left to planner/implementer.

2. **`on_deleted` callback vs reload_list**
   - What we know: `on_saved` callback triggers `MainWindow.reload_list()`. Delete should do the same.
   - What's unclear: Whether `EditStationDialog` should reuse `on_saved` as the post-delete callback, or receive a separate `on_deleted` kwarg.
   - Recommendation: Reuse `on_saved` — same effect (reload list + close dialog). No need for a separate callback.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | none (pytest auto-discovers `tests/`) |
| Quick run command | `~/.local/bin/pytest tests/ -x -q` |
| Full suite command | `~/.local/bin/pytest tests/` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MGMT-01 | `delete_station(id)` removes row from DB | unit | `~/.local/bin/pytest tests/test_repo.py::test_delete_station -x` | ❌ Wave 0 |
| MGMT-01 | `list_stations` returns empty after delete | unit | `~/.local/bin/pytest tests/test_repo.py::test_delete_station_list -x` | ❌ Wave 0 |
| MGMT-02 | `fetch_yt_thumbnail` calls yt-dlp and returns a path (mocked) | unit | `~/.local/bin/pytest tests/test_yt_thumbnail.py -x` | ❌ Wave 0 |
| ICY-01 | `Station.icy_disabled` round-trips through `update_station`/`get_station` | unit | `~/.local/bin/pytest tests/test_repo.py::test_icy_disabled_round_trip -x` | ❌ Wave 0 |
| ICY-01 | DB migration adds `icy_disabled` column to existing schema | unit | `~/.local/bin/pytest tests/test_repo.py::test_icy_disabled_migration -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `~/.local/bin/pytest tests/ -x -q`
- **Per wave merge:** `~/.local/bin/pytest tests/`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_repo.py` — add `test_delete_station`, `test_delete_station_list`, `test_icy_disabled_round_trip`, `test_icy_disabled_migration` tests
- [ ] `tests/test_yt_thumbnail.py` — new file; covers MGMT-02 with mocked subprocess

---

## Sources

### Primary (HIGH confidence)
- Code inspection: `musicstreamer/repo.py`, `models.py`, `ui/edit_dialog.py`, `ui/main_window.py`, `cover_art.py`, `assets.py`, `player.py`
- Local verification: `yt-dlp --print thumbnail` command confirmed working on host (2026.03.17)
- Local verification: 48 existing tests pass with pytest 9.0.2

### Secondary (MEDIUM confidence)
- `Adw.MessageDialog` / `Adw.ResponseAppearance.DESTRUCTIVE` — inferred from libadwaita 1.x API conventions and existing project usage

### Tertiary (LOW confidence)
- `Gtk.Stack` vs `Gtk.Grid` cell removal reliability — based on general GTK4 knowledge, not verified in official docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project; yt-dlp command verified locally
- Architecture: HIGH — patterns directly copied from existing code; no speculation
- Pitfalls: HIGH — identified from code inspection; threading races are mechanical

**Research date:** 2026-03-21
**Valid until:** 2026-04-21 (stable stack; no fast-moving dependencies)
