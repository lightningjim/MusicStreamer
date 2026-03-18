# Phase 1: Module Extraction - Research

**Researched:** 2026-03-18
**Domain:** Python package restructuring — GTK4/GStreamer monolith split
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Project layout:**
- Use a `musicstreamer/` package subdirectory (not flat files in root)
- Structure:
  ```
  MusicStreamer/
  ├── musicstreamer/
  │   ├── __init__.py
  │   ├── __main__.py       ← entry point
  │   ├── models.py         ← Station, Provider dataclasses
  │   ├── repo.py           ← Repo class, all SQLite access
  │   ├── player.py         ← GStreamer Player (extracted from MainWindow)
  │   ├── assets.py         ← asset file copying, path management
  │   └── ui/
  │       ├── __init__.py
  │       ├── main_window.py
  │       ├── edit_dialog.py
  │       └── station_row.py   ← StationRow widget (extracted now, Phase 2 will touch heavily)
  ├── org.example.Streamer.desktop
  └── stations.json
  ```
- No `main.py` shim — entry point is `musicstreamer/__main__.py`

**Launch method:**
- App is launched via `python3 -m musicstreamer`
- Update `org.example.Streamer.desktop` to use `python3 -m musicstreamer`
- Remove top-level `main.py` entirely (or keep as a one-liner shim if the .desktop update is deferred)

**Test scaffolding:**
- Add pytest to the project alongside the extraction
- Write basic smoke tests for `Repo` (create/list/get station) and `models` (dataclass instantiation)
- Tests go in `tests/` directory
- Tests verify the extraction didn't break data layer behavior
- GTK/GStreamer UI code is NOT unit tested (GTK requires a display; defer to manual verification)

### Claude's Discretion
- Exact contents of `__init__.py` files
- Import structure and ordering within modules
- How to handle `APP_ID`, `DATA_DIR`, `DB_PATH`, `ASSETS_DIR` constants (module-level in a `constants.py` or inline in relevant modules)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CODE-01 | Codebase refactored from monolith into logical modules (models, repo, player, assets, UI) before feature work begins | Full extraction map below with exact line ranges; import dependency graph ensures no circular imports; smoke tests verify data layer correctness |
</phase_requirements>

---

## Summary

`main.py` is a clean 512-line monolith with four naturally separated logical layers that are already non-circular in their dependencies. The extraction is a mechanical cut-and-paste with import rewiring — no logic changes required. The only architectural judgment call is where constants live (discretion area) and how `Player` is factored out of `MainWindow`.

The code is already well-structured for this split. `models.py` depends on nothing. `repo.py` depends only on `models.py` and stdlib. `assets.py` depends only on stdlib (and references constants). `player.py` extracts the GStreamer playbin setup and yt-dlp resolution from `MainWindow`. The UI modules depend on all of the above but nothing cycles back.

`Gst.init(None)` is called at module level in `main.py` (line 24). This must move to `__main__.py` before any GStreamer import is used — it is a one-time global initialization call.

**Primary recommendation:** Extract bottom-up (models → repo → assets → player → ui) with a smoke-test gate after each layer. Delete `main.py` and update the `.desktop` file as the final step.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | latest (8.x) | Test runner for `tests/` smoke tests | Standard Python test framework; zero config for simple cases |
| python3 stdlib | 3.x | `os`, `shutil`, `sqlite3`, `dataclasses`, `typing` | Already used; no new dependencies needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-tmp-path (built-in fixture) | — | Isolated temp dirs for SQLite smoke tests | Use in `tests/test_repo.py` to avoid touching real `~/.local/share` |

**Installation:**
```bash
pip install pytest
# or
pip3 install pytest
```

**Version verification:**
```bash
python3 -m pytest --version
```
No pytest is currently installed in this environment. Wave 0 task must install it before tests can run.

---

## Architecture Patterns

### Recommended Project Structure
```
musicstreamer/
├── __init__.py          # empty or package version string
├── __main__.py          # App class, Gst.init(None), sys.argv entry
├── constants.py         # APP_ID, DATA_DIR, DB_PATH, ASSETS_DIR (recommended — see below)
├── models.py            # Provider, Station dataclasses
├── repo.py              # Repo class, db_connect(), db_init()
├── assets.py            # ensure_dirs(), copy_asset_for_station()
├── player.py            # Player class (extracts GStreamer playbin from MainWindow)
└── ui/
    ├── __init__.py      # empty
    ├── main_window.py   # MainWindow
    ├── edit_dialog.py   # EditStationDialog
    └── station_row.py   # StationRow (new class, split from MainWindow.reload_list)
tests/
├── __init__.py          # empty
└── test_repo.py         # smoke tests for Repo + models
```

### Constants placement (discretion area)

Recommendation: create `musicstreamer/constants.py` with `APP_ID`, `DATA_DIR`, `DB_PATH`, `ASSETS_DIR`. These are referenced in `repo.py` (DB_PATH), `assets.py` (ASSETS_DIR, DATA_DIR), `__main__.py` (ensure_dirs), and `ui/main_window.py` (DATA_DIR for art paths). A single source of truth avoids duplication without creating circular imports. All modules import from `constants` and `constants` imports nothing.

### Dependency graph (no cycles)
```
constants.py     ← nothing
models.py        ← nothing
repo.py          ← models, constants, sqlite3
assets.py        ← constants, os, shutil
player.py        ← models, constants, gi.Gst, GLib, yt_dlp
ui/station_row.py ← models, constants, gi.Gtk, gi.Adw
ui/edit_dialog.py ← models, repo, assets, constants, gi.Gtk, gi.Adw, gi.GLib
ui/main_window.py ← models, repo, player, ui/station_row, ui/edit_dialog, constants, gi.Gtk, gi.Adw
__main__.py      ← repo, ui/main_window, gi.Adw, gi.Gst, sys
```

### Pattern 1: Exact source line ranges for each module

| Module | Source lines in main.py | Notes |
|--------|------------------------|-------|
| `constants.py` | lines 18–23 (`APP_ID`, `DATA_DIR`, `DB_PATH`, `ASSETS_DIR`) | Add `Gst.init(None)` to `__main__.py` instead |
| `models.py` | lines 70–86 (`Provider`, `Station`) | Move as-is |
| `repo.py` | lines 32–36 (`db_connect`), 39–67 (`db_init`), 88–180 (`Repo`) | Move as-is; import `Station`, `Provider` from `models`; import `DB_PATH` from `constants` |
| `assets.py` | lines 27–29 (`ensure_dirs`), 182–197 (`copy_asset_for_station`) | Import `ASSETS_DIR`, `DATA_DIR` from `constants` |
| `player.py` | lines 367–374 (playbin setup), 411–447 (`_play_station` logic) | Extract GStreamer logic into a `Player` class; see Pattern 2 |
| `ui/edit_dialog.py` | lines 200–355 (`EditStationDialog`) | Import `Repo` from `repo`, `copy_asset_for_station` from `assets`, `DATA_DIR` from `constants` |
| `ui/station_row.py` | lines 463–478 (row construction inside `reload_list`) | Extract as `StationRow(Gtk.ListBoxRow)` class; import `Station` from `models`, `DATA_DIR` from `constants` |
| `ui/main_window.py` | lines 358–493 (`MainWindow`) | Replace inline playbin with `Player` instance; replace inline row-building with `StationRow` |
| `__main__.py` | lines 495–511 (`App`, `if __name__`) | Add `Gst.init(None)` here; call `ensure_dirs`, `db_connect`, `db_init` |

### Pattern 2: Player class extraction

The GStreamer playbin setup (currently in `MainWindow.__init__`) and `_play_station` / `_stop` methods move into a `Player` class in `player.py`. `MainWindow` holds a `self.player = Player()` instance and delegates play/stop to it. The `Player` class has no GTK imports.

```python
# musicstreamer/player.py
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib
from yt_dlp import YoutubeDL
from musicstreamer.models import Station


class Player:
    def __init__(self):
        self._pipeline = Gst.ElementFactory.make("playbin", "player")
        self._pipeline.set_property(
            "video-sink", Gst.ElementFactory.make("fakesink", "fake-video")
        )
        audio_sink = Gst.ElementFactory.make("pulsesink", "audio-output")
        if audio_sink:
            self._pipeline.set_property("audio-sink", audio_sink)

    def play(self, station: Station, on_title: callable):
        """Start playback. Calls on_title(title_str) when title is known."""
        url = (station.url or "").strip()
        if not url:
            on_title("(no URL set)")
            return
        if "youtube.com" in url or "youtu.be" in url:
            self._play_youtube(url, station.name, on_title)
        else:
            self._set_uri(url, station.name, on_title)

    def stop(self):
        self._pipeline.set_state(Gst.State.NULL)

    def _play_youtube(self, url: str, fallback_name: str, on_title: callable):
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "noplaylist": True,
            "format": "best[protocol^=m3u8]/best",
            "cachedir": False,
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                stream_url = info.get("url")
                title = info.get("title") or fallback_name
        except Exception as e:
            print("yt-dlp error:", e)
            on_title("yt-dlp error")
            return
        if stream_url:
            self._set_uri(stream_url, title, on_title)

    def _set_uri(self, uri: str, title: str, on_title: callable):
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.set_property("uri", uri)
        self._pipeline.set_state(Gst.State.PLAYING)
        on_title(title)
```

`MainWindow` then calls `self.player.play(st, on_title=lambda t: self.now_label.set_text(f"Now Playing: {t}"))`.

### Pattern 3: StationRow extraction

The row-building block inside `MainWindow.reload_list` (lines 463–478) becomes a `StationRow(Gtk.ListBoxRow)` class. The `station` object is attached as `self.station` (not just `station_id`) to support Phase 2 filter functions without DB round-trips.

```python
# musicstreamer/ui/station_row.py
import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw
from musicstreamer.models import Station
from musicstreamer.constants import DATA_DIR


class StationRow(Gtk.ListBoxRow):
    def __init__(self, station: Station):
        super().__init__()
        self.station = station          # full object for Phase 2 filter_func
        self.station_id = station.id   # backward compat

        provider = station.provider_name or "Unknown"
        subtitle = provider
        if station.tags:
            subtitle += f" • {station.tags}"

        row = Adw.ActionRow(title=station.name, subtitle=subtitle)
        row.set_activatable(True)

        if station.station_art_path:
            abs_path = os.path.join(DATA_DIR, station.station_art_path)
            if os.path.exists(abs_path):
                pic = Gtk.Picture.new_for_filename(abs_path)
                pic.set_size_request(48, 48)
                pic.set_content_fit(Gtk.ContentFit.COVER)
                row.add_prefix(pic)

        self.set_child(row)
```

### Pattern 4: `__main__.py` entry point

```python
# musicstreamer/__main__.py
import sys
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")
from gi.repository import Adw, Gst

from musicstreamer.repo import db_connect, db_init, Repo
from musicstreamer.assets import ensure_dirs
from musicstreamer.ui.main_window import MainWindow

Gst.init(None)  # moved from top-level in main.py


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.example.MusicStreamer")

    def do_activate(self):
        ensure_dirs()
        con = db_connect()
        db_init(con)
        repo = Repo(con)
        win = MainWindow(self, repo)
        win.present()


if __name__ == "__main__":
    app = App()
    app.run(sys.argv)
```

### Anti-Patterns to Avoid

- **Circular imports:** Never import from `ui/` inside `models.py`, `repo.py`, `assets.py`, or `player.py`. The dependency arrow always points down the stack.
- **Top-level `Gst.init(None)` in imported modules:** `Gst.init` must run in `__main__.py` before any GStreamer element is created. If it runs at import time in `player.py`, it fires whenever `player` is imported — including in tests that don't want GStreamer. Move it to `__main__.py`.
- **Keeping `main.py` as a real module:** Once extraction is complete, delete `main.py`. A leftover `main.py` that imports `musicstreamer.*` creates confusion about the real entry point and can shadow module names.
- **Relative imports in `ui/`:** Use absolute imports (`from musicstreamer.models import Station`) not relative (`from ..models import Station`). The codebase uses no relative imports currently; keep consistent.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Circular import detection | Manual review | `python3 -c "import musicstreamer"` smoke check | Import system raises `ImportError` immediately on cycles |
| Temp DB for tests | Custom fixture | `pytest` `tmp_path` fixture + `sqlite3.connect(tmp_path/"test.db")` | Built-in, clean, isolated per test |
| Package entry point | Shell wrapper script | `python3 -m musicstreamer` via `__main__.py` | Standard Python `-m` module execution; no wrapper needed |

---

## Common Pitfalls

### Pitfall 1: `Gst.init(None)` at module import time

**What goes wrong:** `Gst.init(None)` is currently on line 24 of `main.py`, executed whenever the file is imported. After extraction, if it remains at module level in `player.py`, it fires on `import player` — including in test environments without GStreamer daemons running or in CI. It may also cause double-init warnings if called again in `__main__.py`.

**Why it happens:** Direct port of module-level code without considering import semantics.

**How to avoid:** Move `Gst.init(None)` exclusively to `__main__.py`. The `Player` class can assume `Gst.init` was already called by the time it is instantiated.

**Warning signs:** Tests importing `player.py` fail with GStreamer errors; or GStreamer logs "GStreamer already initialized" warnings at startup.

---

### Pitfall 2: `gi.require_version` must precede `from gi.repository import`

**What goes wrong:** If any module imports from `gi.repository` without first calling `gi.require_version`, PyGObject raises `ValueError: Namespace Gtk not available`. This is a global registry — the first `require_version` call wins for the process lifetime.

**Why it happens:** When splitting into modules, it is tempting to call `require_version` only in `__main__.py`. But if any module is imported standalone (e.g., in a test), it may try to import from `gi.repository` before `require_version` has fired.

**How to avoid:** Include `gi.require_version(...)` calls at the top of every module that imports from `gi.repository`. The calls are idempotent for matching versions.

**Warning signs:** `ValueError: Namespace not available` when running individual modules or tests.

---

### Pitfall 3: `DATA_DIR` path used before `ensure_dirs()` is called

**What goes wrong:** `assets.py` and `repo.py` reference `DATA_DIR`/`DB_PATH` as constants. If `ensure_dirs()` has not been called before `db_connect()`, `sqlite3.connect(DB_PATH)` will fail because `~/.local/share/musicstreamer/` does not exist.

**Why it happens:** The call order `ensure_dirs → db_connect → db_init → Repo(con)` is currently enforced by `App.do_activate()`. After extraction, this order must be preserved in `__main__.py`.

**How to avoid:** `ensure_dirs()` is always the first call in `App.do_activate()`. Document this in `__main__.py` with a comment.

---

### Pitfall 4: `StationRow` not attaching full `Station` object

**What goes wrong:** Phase 2 filter functions need `row.station` (the full `Station` dataclass) to filter by provider, tags, and name without DB queries. If `StationRow` only attaches `station_id` (current behavior in `main.py`), Phase 2 must add the full object attachment anyway — creating a double change.

**Why it happens:** Minimal extraction ports the existing `listrow.station_id = st.id` pattern only.

**How to avoid:** `StationRow.__init__` attaches `self.station = station` in addition to `self.station_id = station.id`. The context decision explicitly calls this out.

---

### Pitfall 5: `Adw.ActionRow` is not a direct `Gtk.ListBoxRow` subclass for GTK4

**What goes wrong:** In the current code, the row structure is `Gtk.ListBoxRow` wrapping an `Adw.ActionRow`. If `StationRow` is subclassed from `Adw.ActionRow` instead of `Gtk.ListBoxRow`, the `station` attribute attachment and the `listbox.append()` call change behavior.

**Why it happens:** `Adw.ActionRow` is itself a `Gtk.ListBoxRow` subclass — it is tempting to use it directly. But the existing code uses a wrapper pattern (`listrow = Gtk.ListBoxRow(); listrow.set_child(row)`).

**How to avoid:** Keep the existing wrapper pattern in `StationRow` — subclass `Gtk.ListBoxRow`, create an `Adw.ActionRow` child. This preserves existing behavior and keeps `station` on the outermost row object.

---

## Code Examples

### Smoke test for Repo (no GTK/GStreamer required)

```python
# tests/test_repo.py
import sqlite3
import pytest
from musicstreamer.models import Station, Provider
from musicstreamer.repo import Repo, db_init


@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)


def test_list_stations_empty(repo):
    assert repo.list_stations() == []


def test_create_and_get_station(repo):
    station_id = repo.create_station()
    st = repo.get_station(station_id)
    assert st.id == station_id
    assert st.name == "New Station"
    assert st.url == ""


def test_update_station(repo):
    sid = repo.create_station()
    repo.update_station(sid, "My Station", "http://example.com/stream", None, "jazz", None, None)
    st = repo.get_station(sid)
    assert st.name == "My Station"
    assert st.tags == "jazz"


def test_models_dataclass(repo):
    sid = repo.create_station()
    st = repo.get_station(sid)
    assert isinstance(st, Station)
    assert st.provider_id is None
```

### `__init__.py` contents (minimal)

```python
# musicstreamer/__init__.py
# Package marker — intentionally empty.
```

```python
# musicstreamer/ui/__init__.py
# UI subpackage marker — intentionally empty.
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single-file Python apps | Package layout with `python3 -m pkg` | Python 3.3+ (namespace packages) | `__main__.py` is the standard entry point; no `setup.py` needed for dev use |
| `gi.require_version` once at top level | Per-module `require_version` before import | Always required by PyGObject | Each module must be self-contained for import safety |

---

## Open Questions

1. **`constants.py` vs inline constants**
   - What we know: `APP_ID`, `DATA_DIR`, `DB_PATH`, `ASSETS_DIR` are referenced in at least 4 future modules
   - What's unclear: User left this to Claude's discretion
   - Recommendation: Create `constants.py` — avoids duplication, no risk of circular import since it imports nothing

2. **`org.example.Streamer.desktop` content**
   - What we know: Currently empty; needs `python3 -m musicstreamer` as Exec value; CONTEXT.md notes it "needs to be properly populated"
   - What's unclear: Whether a full valid `.desktop` file is in scope for this phase (icon, categories, etc.)
   - Recommendation: Populate with minimal valid entry (`[Desktop Entry]`, `Exec=python3 -m musicstreamer`, `Type=Application`, `Name=MusicStreamer`) as part of the final "remove main.py" task

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (not yet installed) |
| Config file | none — Wave 0 creates `pyproject.toml` or runs bare pytest |
| Quick run command | `python3 -m pytest tests/ -x -q` |
| Full suite command | `python3 -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CODE-01 | `Repo.create_station()` returns valid ID | unit | `python3 -m pytest tests/test_repo.py::test_create_and_get_station -x` | Wave 0 |
| CODE-01 | `Repo.list_stations()` returns empty list on fresh DB | unit | `python3 -m pytest tests/test_repo.py::test_list_stations_empty -x` | Wave 0 |
| CODE-01 | `Repo.update_station()` persists fields correctly | unit | `python3 -m pytest tests/test_repo.py::test_update_station -x` | Wave 0 |
| CODE-01 | `Station` dataclass instantiates correctly | unit | `python3 -m pytest tests/test_repo.py::test_models_dataclass -x` | Wave 0 |
| CODE-01 | App launches without error (no circular imports) | smoke | `python3 -c "import musicstreamer"` | Wave 0 (after extraction) |
| CODE-01 | No circular imports in package | smoke | `python3 -c "import musicstreamer"` | Wave 0 |
| CODE-01 | GTK/GStreamer UI loads correctly | manual | Launch app, verify station list visible | N/A (GTK requires display) |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/ -x -q`
- **Per wave merge:** `python3 -m pytest tests/ -v`
- **Phase gate:** Full suite green + manual app launch verification before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/__init__.py` — package marker
- [ ] `tests/test_repo.py` — covers CODE-01 data layer tests
- [ ] pytest install: `pip3 install pytest` — not currently installed
- [ ] `musicstreamer/__init__.py` — package marker
- [ ] `musicstreamer/ui/__init__.py` — UI subpackage marker

---

## Sources

### Primary (HIGH confidence)
- `main.py` (full read, lines 1–512) — definitive source for extraction line ranges, import structure, class boundaries
- `.planning/codebase/ARCHITECTURE.md` — layer analysis, data flow, entry points
- `.planning/codebase/CONVENTIONS.md` — naming patterns, import ordering, type annotation style
- `.planning/research/ARCHITECTURE.md` — Player extraction rationale, module boundary table, `Player` class pattern
- `.planning/phases/01-module-extraction/01-CONTEXT.md` — locked decisions, line ranges per module

### Secondary (MEDIUM confidence)
- Python docs: `python3 -m pkg` invokes `pkg/__main__.py` — standard behavior since Python 3.1
- PyGObject: `gi.require_version` must precede `from gi.repository import` — documented requirement

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib + pytest, no novel dependencies
- Architecture: HIGH — all extraction decisions derived directly from reading the source code
- Pitfalls: HIGH — `Gst.init` placement and `gi.require_version` are well-known PyGObject gotchas; `ensure_dirs` ordering visible in source

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable domain — Python packaging and PyGObject conventions don't shift rapidly)
