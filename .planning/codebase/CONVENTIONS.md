# Coding Conventions

**Analysis Date:** 2026-03-18

## Naming Patterns

**Files:**
- Module files use lowercase with underscores: `main.py`
- Single entry point pattern: all application code in `main.py`

**Functions:**
- Use snake_case for function names
- Private/internal functions prefixed with underscore: `_stop()`, `_play_row()`, `_refresh_pictures()`
- Public functions without prefix: `db_connect()`, `db_init()`, `ensure_dirs()`, `list_stations()`
- Examples: `ensure_dirs()`, `db_connect()`, `copy_asset_for_station()`, `list_providers()`

**Variables:**
- Use snake_case for all variables: `station_art_path`, `album_fallback_path`, `provider_id`
- Module-level constants in UPPER_CASE: `APP_ID`, `DATA_DIR`, `DB_PATH`, `ASSETS_DIR`
- Private instance variables use underscore prefix: `self.on_saved`

**Types and Classes:**
- Class names in PascalCase: `Provider`, `Station`, `Repo`, `EditStationDialog`, `MainWindow`, `App`
- Classes explicitly inherit from their base types: `class EditStationDialog(Adw.Window)`, `class MainWindow(Adw.ApplicationWindow)`

## Code Style

**Formatting:**
- No explicit formatter configured (Prettier/Black not present)
- Uses 4-space indentation (Python standard)
- Single blank line between method definitions within classes
- Double blank line between top-level class/function definitions

**Imports:**
- Standard library imports first: `os`, `shutil`, `sqlite3`, `sys`
- Then dataclasses and typing: `from dataclasses import dataclass`, `from typing import Optional, List`
- Then third-party framework imports with explicit version control:
  ```python
  import gi
  gi.require_version("Gtk", "4.0")
  gi.require_version("Adw", "1")
  gi.require_version("Gst", "1.0")
  from gi.repository import Gtk, Adw, Gio, GLib
  from gi.repository import Gst
  ```
- Application imports last: `from yt_dlp import YoutubeDL`

**Linting:**
- No .eslintrc, .pylintrc, or similar linting configuration detected
- No formatter configuration (no .prettierrc, pyproject.toml, or black config)

## Error Handling

**Patterns:**
- Explicit exception catching with specific exception types: `except GLib.Error`, `except Exception as e`
- Exceptions logged to stdout with `print()`: `print("yt-dlp error:", e)`
- ValueError raised for domain errors: `raise ValueError("Station not found")`
- Guard clauses for null/empty checks:
  ```python
  if not r:
      raise ValueError("Station not found")
  ```
- Try-except blocks for external service calls (yt-dlp extraction):
  ```python
  try:
      with YoutubeDL(ydl_opts) as ydl:
          info = ydl.extract_info(url, download=False)
  except Exception as e:
      self.now_label.set_text("Now Playing: yt-dlp error")
      print("yt-dlp error:", e)
      return
  ```
- Graceful degradation pattern for missing files/data:
  ```python
  if self.station_art_rel:
      abs_path = os.path.join(DATA_DIR, self.station_art_rel)
      if os.path.exists(abs_path):
          self.station_pic.set_filename(abs_path)
  else:
      self.station_pic.set_paintable(None)
  ```

## Logging

**Framework:** Built-in `print()` function

**Patterns:**
- Use `print()` for debug information: `print("yt-dlp error:", e)`
- Error output to stdout (not stderr)
- No structured logging framework

## Comments

**When to Comment:**
- Docstrings present on public functions explaining purpose:
  ```python
  def copy_asset_for_station(station_id: int, source_path: str, kind: str) -> str:
      """
      Copies the chosen image into ~/.local/share/musicstreamer/assets/<station_id>/<kind>.<ext>
      Returns relative path under assets/.
      """
  ```
- Inline comments explain complex logic or non-obvious intent:
  ```python
  # suppress video windows for YouTube/HLS
  self.player.set_property("video-sink", Gst.ElementFactory.make("fakesink", "fake-video"))

  # Double-click a station row to play (for testing)
  self.listbox.connect("row-activated", self._play_row)

  # Many livestreams only expose muxed HLS (m3u8) formats
  "format": "best[protocol^=m3u8]/best",
  ```
- Comments for SQL schema triggers:
  ```sql
  CREATE TRIGGER IF NOT EXISTS stations_updated_at
  AFTER UPDATE ON stations
  BEGIN
    UPDATE stations SET updated_at = datetime('now') WHERE id = NEW.id;
  END;
  ```

## Type Annotations

**Pattern:**
- Use type hints on function parameters and returns
- Examples: `def db_connect() -> sqlite3.Connection:`, `def list_providers(self) -> List[Provider]:`
- Use `Optional[Type]` for nullable values: `Optional[int]`, `Optional[str]`
- Dataclass annotations for type-safe domain objects:
  ```python
  @dataclass
  class Station:
      id: int
      name: str
      url: str
      provider_id: Optional[int]
  ```

## Function Design

**Size:** Functions are compact, typically 5-20 lines

**Parameters:**
- Positional parameters for required values
- No default parameters observed (all parameters explicit)
- Type hints on all parameters
- Methods that modify state: `update_station(station_id, name, url, ...)`

**Return Values:**
- Explicit return types with annotations
- Return None implicitly at end of void methods
- Return objects or primitives explicitly typed

## Module Design

**Dataclasses for Domain Objects:**
- Use `@dataclass` decorator for immutable value objects:
  ```python
  @dataclass
  class Provider:
      id: int
      name: str
  ```
- Domain objects: `Provider`, `Station`

**Repository Pattern:**
- Encapsulate database logic in `Repo` class
- Single connection passed to repository: `def __init__(self, con: sqlite3.Connection):`
- CRUD methods: `list_providers()`, `create_station()`, `get_station()`, `update_station()`

**UI Widget Subclassing:**
- Subclass GTK/Libadwaita classes for custom widgets:
  ```python
  class EditStationDialog(Adw.Window):
      def __init__(self, app, repo: Repo, station_id: int, on_saved):
  ```
  ```python
  class MainWindow(Adw.ApplicationWindow):
      def __init__(self, app, repo: Repo):
  ```

**Callbacks Pattern:**
- Pass callbacks as parameters to widgets: `on_saved=self.reload_list`
- Callbacks are methods or inline lambdas:
  ```python
  stop_btn.connect("clicked", lambda *_: self._stop())
  save_btn.connect("clicked", self._save)
  dlg.open(self, None, done)  # done is callback
  ```

---

*Convention analysis: 2026-03-18*
