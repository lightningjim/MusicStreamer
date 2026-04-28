# Coding Conventions

**Analysis Date:** 2026-04-28

## Naming Patterns

**Files:**
- Module files use `snake_case` (e.g., `player.py`, `cover_art.py`, `gst_bus_bridge.py`)
- Dialogue files follow `{component}_dialog.py` pattern (e.g., `edit_station_dialog.py`, `accent_color_dialog.py`)
- Test files use `test_{component}.py` format (e.g., `test_player_volume.py`, `test_repo.py`)
- Resource files are named descriptively (e.g., `icons_rc.py` for generated Qt resource module)

**Functions:**
- Use `snake_case` for all function names
- Private/internal functions prefixed with single underscore (e.g., `_build_itunes_query()`, `_fix_icy_encoding()`)
- Factory functions use descriptive names like `make_player()`, `_make_window()`
- Property accessor functions often omit subject when obvious from context (e.g., `db_connect()`, `db_init()`)
- Async/worker-thread functions often have descriptive docstring mentioning threading context

**Variables:**
- Use `snake_case` for local variables and module-level variables
- Private module-level state prefixed with underscore (e.g., `_BUS_BRIDGE`, `_AA_STREAM_DOMAINS`)
- Qt signal members at class scope are ALL_CAPS in signal declarations, e.g. `title_changed = Signal(str)`
- Private instance attributes prefixed with single underscore (e.g., `self._pipeline`, `self._volume`, `self._settings`)
- Dataclass fields are `snake_case` with no leading underscores

**Types:**
- Class names use `PascalCase` (e.g., `Player`, `Station`, `StationStream`)
- Dataclass field type hints are explicit (e.g., `Optional[int]`, `List[StationStream]`)
- Union types prefer modern `X | Y` syntax over `Union[X, Y]` (Python 3.10+)

## Code Style

**Formatting:**
- No formatter enforced (no black, ruff format, or prettier configured in pyproject.toml)
- Code uses 4-space indentation (Python standard)
- Line length is pragmatic, no strict enforcement visible
- Imports are organized but not automatically formatted

**Linting:**
- No linter configured (no ruff, flake8, pylint, or mypy in pyproject.toml)
- Code uses type hints throughout but not enforced via mypy
- `# noqa` comments used sparingly to suppress violations (e.g., `# noqa: F401` for unused imports that register side effects, `# noqa: BLE001` for bare `except Exception`)

## Import Organization

**Order:**
1. Future imports (`from __future__ import annotations`)
2. Standard library imports (`import os`, `import threading`)
3. Third-party library imports (`from PySide6.QtCore import...`, `import gi`)
4. Local application imports (`from musicstreamer.models import...`)

**Path Aliases:**
- No path aliases configured (no `src/` layout, no `@` aliases)
- Relative imports avoided; all imports are absolute from `musicstreamer` root
- Subpackage imports use full paths (e.g., `from musicstreamer.ui_qt.main_window import MainWindow`)

**Example from `musicstreamer/player.py`:**
```python
from __future__ import annotations

import os
import threading

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst
from PySide6.QtCore import QObject, Qt, QTimer, Signal

from musicstreamer import constants, cookie_utils, paths
from musicstreamer.constants import BUFFER_DURATION_S, BUFFER_SIZE_BYTES
from musicstreamer.eq_profile import EqBand, EqProfile, parse_autoeq
from musicstreamer.gst_bus_bridge import GstBusLoopThread
from musicstreamer.models import Station, StationStream
from musicstreamer.stream_ordering import order_streams
```

## Error Handling

**Patterns:**
- Broad exception catching used in daemon/worker threads with `except Exception as e:` (marked with `# noqa: BLE001`)
- Specific exception catching for known/expected errors (e.g., `except (UnicodeDecodeError, UnicodeEncodeError)`, `except sqlite3.OperationalError`)
- Try/except blocks in migration code use `pass` for idempotency checks (e.g., ALTER TABLE if column already exists)
- Top-level try/except backstops in worker threads to surface ALL failures (threaded code must never silently fail)

**Example from `musicstreamer/player.py` (line 683):**
```python
try:
    return self.get_property("volume")
except (TypeError, ValueError):
    return 0.0
```

**Example from `musicstreamer/repo.py` (migration pattern, line 68):**
```python
try:
    con.execute("ALTER TABLE stations ADD COLUMN icy_disabled INTEGER NOT NULL DEFAULT 0")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists
```

## Logging

**Framework:** Python standard `logging` module (or print-based for simple cases)

**Patterns:**
- Minimal use of logging in visible code (not configured in scope of samples)
- Error messages emitted via Qt signals for UI display (e.g., `playback_error = Signal(str)`)
- Debug output via print() in some utility functions (e.g., `_parse_itunes_result` may print)

**Example from `musicstreamer/player.py`:**
```python
# Errors surface via Qt signals, not logging
playback_error = Signal(str)  # GStreamer error text
```

## Comments

**When to Comment:**
- Docstrings mandatory on all module-level code (file header explains purpose)
- Docstrings on all public classes and functions (describe purpose and parameters)
- Inline comments explain WHY, not WHAT (e.g., "Phase 43.1 bugfix: add_signal_watch attaches its GSource to the calling thread's thread-default MainContext")
- Phase/Plan references used to contextualize comments (e.g., "Phase 35 port:", "Plan 35-06:")

**Docstring/TSDoc:**
- Functions use plain docstring format (not strict Google/NumPy style)
- One-line summaries on first line, followed by blank line and details
- Parameters and return values documented in prose form
- Thread-safety and timing constraints documented at module level

**Example from `musicstreamer/gst_bus_bridge.py`:**
```python
"""GStreamer bus -> Qt main thread bridge (Phase 35 / PORT-02 / D-07).

Runs a GLib.MainLoop on a daemon thread so GStreamer's bus signal watches
fire even though the main thread runs Qt's event loop. Handlers installed
via bus.connect(...) after attach_bus() run on THAT thread and must emit
Qt signals (queued connection, cross-thread) to reach the main thread.
"""
```

**Example from `musicstreamer/cover_art.py`:**
```python
def fetch_cover_art(icy_string: str, callback: callable) -> None:
    """Fetch cover art for the given ICY title string and call callback(path_or_None).

    The callback is invoked from a background thread. Callers that update GTK
    widgets must wrap the callback body with GLib.idle_add.

    If the title is junk or the fetch fails, callback(None) is called.
    """
```

## Function Design

**Size:** 
- Functions range from 5-50 lines in typical cases
- Longer functions (~70+ lines) reserved for complex logic with clear phase transitions (e.g., `player._play_youtube()`)
- Helper functions extracted to module level for reusability and testability

**Parameters:** 
- Explicit parameters preferred over *args/**kwargs
- Optional parameters use `| None` type hints (Python 3.10+)
- Callback parameters documented as `callable` type hint
- Qt parent objects passed as `parent: QObject | None = None`

**Return Values:** 
- Functions return concrete types (dataclass instances, int, bool, str)
- Optional returns explicitly typed as `X | None`
- Multi-value returns use tuples (e.g., `tuple[str, str]`)

**Example from `musicstreamer/filter_utils.py`:**
```python
def normalize_tags(raw: str) -> list[str]:
    """Split raw tag string on comma/bullet, strip whitespace, deduplicate case-insensitively.

    Preserves first-seen display form for each unique tag (case-folded key).
    """
    tokens = re.split(r"[,•]", raw)
    seen: dict[str, str] = {}
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        key = token.casefold()
        if key not in seen:
            seen[key] = token
    return list(seen.values())
```

## Module Design

**Exports:** 
- All public functions and classes exported directly (no `__all__` pattern, implicit)
- Private functions prefixed with underscore and not re-exported
- Modules may have side-effect imports (e.g., `icons_rc` for Qt resource registration)

**Barrel Files:** 
- Not used; `musicstreamer/ui_qt/__init__.py` is empty
- Direct imports from full module paths preferred (e.g., `from musicstreamer.ui_qt.main_window import MainWindow`)

**Dataclasses:**
- Heavy use of dataclasses for models (`Station`, `StationStream`, `Provider`, `Favorite`)
- Located in `musicstreamer/models.py`
- Use `field(default_factory=list)` for mutable defaults
- Optional fields use `Optional[Type]` syntax

**Example from `musicstreamer/models.py`:**
```python
@dataclass
class Station:
    id: int
    name: str
    provider_id: Optional[int]
    provider_name: Optional[str]
    tags: str
    station_art_path: Optional[str]
    album_fallback_path: Optional[str]
    icy_disabled: bool = False
    streams: List[StationStream] = field(default_factory=list)
    last_played_at: Optional[str] = None
    is_favorite: bool = False
```

## Qt Patterns

**Signal Declaration:**
- Signals declared at class scope as class variables
- All-caps naming (e.g., `title_changed = Signal(str)`)
- Docstring comments explain signal purpose (e.g., "# ICY title (after encoding fix)")
- Complex cross-thread signals documented with thread context

**Example from `musicstreamer/player.py`:**
```python
class Player(QObject):
    # Class-level Signals (Pitfall 4 -- MUST be at class scope, not instance)
    title_changed              = Signal(str)     # ICY title (after encoding fix)
    failover                   = Signal(object)  # StationStream | None
    offline                    = Signal(str)     # Twitch channel name
    twitch_resolved            = Signal(str)     # internal: resolved Twitch HLS URL -- queued back to main thread
    youtube_resolved           = Signal(str)     # internal: resolved YouTube HLS URL -- queued back to main thread
    youtube_resolution_failed  = Signal(str)     # internal: yt-dlp error message -- queued back to main thread
    playback_error             = Signal(str)     # GStreamer error text
```

**Bound Methods for Signals:**
- Use bound methods (no self-capturing lambdas) per QA-05 pattern
- Signal connections made in `__init__` after all widgets created
- Thread-crossing signals use Qt.QueuedConnection for automatic marshaling

**Side-Effect Imports:**
- `icons_rc` imported at module top in files that use icons to register Qt resource prefix `:/`
- Marked with `# noqa: F401` to suppress unused import warnings

---

*Convention analysis: 2026-04-28*
