# Testing Patterns

**Analysis Date:** 2026-04-28

## Test Framework

**Runner:**
- pytest 9+
- Config: `pyproject.toml` with `testpaths = ["tests"]`
- Markers defined: `integration` (marks tests requiring live services like D-Bus + playerctl)

**Assertion Library:**
- pytest's built-in assertions (e.g., `assert x == y`)
- `unittest.mock.MagicMock` and `patch` for mocking

**Run Commands:**
```bash
pytest tests              # Run all tests
pytest tests -v           # Verbose output
pytest tests -k "filter"  # Run tests matching pattern
pytest tests -m integration  # Run only integration tests
pytest tests --tb=short   # Short traceback format
```

## Test File Organization

**Location:**
- All tests in `tests/` directory at repo root, parallel to `musicstreamer/` source
- Integration tests in `tests/integration/` subdirectory
- No co-located test files (not `musicstreamer/player_test.py`)

**Naming:**
- `test_{component}.py` format (e.g., `test_player_volume.py`, `test_repo.py`, `test_cookies.py`)
- Functions named `test_{action}` (e.g., `test_set_volume_normal()`, `test_create_and_get_station()`)

**Structure:**
```
tests/
├── conftest.py                      # pytest-qt + GStreamer bus bridge stub
├── test_aa_import.py
├── test_aa_url_detection.py
├── test_accent_color_dialog.py
├── test_accent_provider.py
├── ...
├── integration/
│   └── [integration test files]
└── __init__.py
```

## Test Structure

**Suite Organization:**
```python
# conftest.py - module-level fixtures and session setup
import pytest

@pytest.fixture(autouse=True)
def _stub_bus_bridge(monkeypatch):
    """Replace _ensure_bus_bridge with a MagicMock so Player() construction
    never starts the real GLib.MainLoop daemon thread in unit tests."""
    try:
        import musicstreamer.player as _player_mod
    except ImportError:
        return
    monkeypatch.setattr(
        _player_mod, "_ensure_bus_bridge", lambda: MagicMock()
    )
```

**Per-Test-File Patterns:**

1. **Imports at top** — Standard library, unittest.mock, pytest, then application code
2. **Fixtures** — Define test data fixtures (repo, player, dialog mocks)
3. **Helper functions** — Factory functions like `make_player()` at module level
4. **Test functions** — Named `test_*`, use fixtures as parameters
5. **Comments** — Multi-line comments explain complex test setup or Phase/Plan context

**Example from `tests/test_player_volume.py`:**
```python
"""Tests for Player.set_volume() — clamping and GStreamer property set.

Phase 35 port: uses pytest-qt ``qtbot`` to anchor Qt object creation on
the main thread. No GTK / GLib imports.
"""
from unittest.mock import MagicMock, patch


def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out."""
    from musicstreamer.player import Player
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    # Replace the cached pipeline with a fresh mock so tests can assert
    # directly on set_property without init-time noise.
    player._pipeline = MagicMock()
    return player


def test_set_volume_normal(qtbot):
    """set_volume(0.8) sets pipeline volume to 0.8."""
    p = make_player(qtbot)
    p.set_volume(0.8)
    p._pipeline.set_property.assert_called_with("volume", 0.8)
```

**Example from `tests/test_repo.py` (database + fixtures):**
```python
@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)

def test_create_and_get_station(repo):
    station_id = repo.create_station()
    st = repo.get_station(station_id)
    assert st.id == station_id
    assert st.name == "New Station"
    assert st.streams == []
```

## Mocking

**Framework:** `unittest.mock` (from stdlib)

**Patterns:**

1. **GStreamer Pipeline Mocking** — Mock `Gst.ElementFactory.make()` to return MagicMock pipeline
   - bus is mocked: `mock_pipeline.get_bus.return_value = mock_bus`
   - Pipeline properties set via `set_property()` assertions

   **Example:**
   ```python
   with patch(
       "musicstreamer.player.Gst.ElementFactory.make",
       return_value=mock_pipeline,
   ):
       player = Player()
   ```

2. **Repository Mocking** — Use `FakeRepo` class for UI tests (faster than real SQLite)
   - Implements subset of `Repo` interface
   - Uses dict-based in-memory storage

   **Example from `tests/test_accent_color_dialog.py`:**
   ```python
   class FakeRepo:
       def __init__(self):
           self._settings: dict[str, str] = {}
   
       def get_setting(self, key: str, default: str = "") -> str:
           return self._settings.get(key, default)
   
       def set_setting(self, key: str, value: str) -> None:
           self._settings[key] = value
   ```

3. **Player Mocking** — QObject subclass with required signals/methods
   - Used in UI tests that don't need real playback

   **Example from `tests/test_ui_qt_scaffold.py`:**
   ```python
   class _FakePlayer(QObject):
       title_changed = Signal(str)
       failover = Signal(object)
       offline = Signal(str)
       playback_error = Signal(str)
       cookies_cleared = Signal(str)
       elapsed_updated = Signal(int)
       buffer_percent = Signal(int)
   
       def set_volume(self, v): pass
       def play(self, station): pass
       def pause(self): pass
       def stop(self): pass
   ```

4. **ytdlp/streamlink Mocking** — Mock context managers for library APIs
   - Used in `test_cookies.py` to mock YoutubeDL extraction

   **Example from `tests/test_cookies.py`:**
   ```python
   class FakeYDL:
       def __init__(self, opts):
           captured_opts.update(opts)
   
       def __enter__(self):
           return self
   
       def __exit__(self, *a):
           return False
   
       def extract_info(self, url, download=False):
           return {"entries": []}
   
   with patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", FakeYDL):
       from musicstreamer import yt_import
       yt_import.scan_playlist("https://youtube.com/playlist?list=test")
   ```

**What to Mock:**
- External services (GStreamer pipeline, YouTube/Twitch APIs, iTunes API)
- Filesystem operations (use `tmp_path` fixture for SQLite dbs, temp files)
- Subprocess calls (yt-dlp, streamlink)
- Global state access (paths via `monkeypatch`, module-level configs)

**What NOT to Mock:**
- Model dataclasses (`Station`, `StationStream`, `Provider`)
- Database layer (use real SQLite with `tmp_path`, very fast)
- Business logic functions (filter_utils, url_helpers — unit test directly)
- Qt widgets in UI tests (use `qtbot` to construct and manage lifecycle)

## Fixtures and Factories

**Test Data:**

**From `tests/test_repo.py` — Database fixture with temporary file:**
```python
@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)
```

**From `tests/test_edit_station_dialog.py` — Dataclass fixtures:**
```python
@pytest.fixture()
def station():
    return Station(
        id=1,
        name="Test FM",
        provider_id=1,
        provider_name="TestProvider",
        tags="jazz,electronic",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
    )
```

**From `tests/test_cookies.py` — Path override via monkeypatch:**
```python
def test_cookie_path_resolves_under_root(tmp_path, monkeypatch):
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    assert paths.cookies_path() == str(tmp_path / "cookies.txt")
```

**Location:**
- Simple fixtures defined in each test file (no shared fixture library)
- Complex fixtures and conftest hooks in `tests/conftest.py`
- Temporary files use pytest's `tmp_path` fixture (pathlib.Path object)
- Monkeypatch used to override module-level state (paths._root_override, etc.)

## Coverage

**Requirements:** Not enforced (no coverage target in pyproject.toml or CI)

**View Coverage:**
```bash
# If pytest-cov installed:
pytest tests --cov=musicstreamer --cov-report=html
# Open htmlcov/index.html in browser
```

## Test Types

**Unit Tests:**
- Scope: Single function or method
- Approach: Isolated from dependencies via mocking; test with known inputs and assert outputs
- Examples: `test_set_volume_*()`, `test_normalize_tags()`, `test_matches_filter()`
- Fast (< 1ms per test)

**Integration Tests:**
- Scope: Multiple components working together
- Approach: Use real or near-real dependencies (real SQLite db, real Qt widgets)
- Location: `tests/integration/` subdirectory
- Marked with `@pytest.mark.integration`
- Examples: `test_main_window_integration.py` (Qt rendering + signals), media keys tests (D-Bus)
- Slower (10-500ms per test)

**E2E Tests:**
- Not used in this codebase
- Would require full application startup and user interaction simulation
- Considered out of scope for current testing strategy

## Common Patterns

**Async Testing:**
Not directly used (no async/await in codebase). Threading is handled via:
- `GLib.MainLoop` daemon thread for GStreamer bus (mocked in unit tests)
- `threading.Thread` workers for Twitch/YouTube resolution (tested via signal emission)
- Qt main thread managed by `qtbot` fixture

**Error Testing:**
```python
def test_delete_station(repo):
    sid = repo.create_station()
    repo.delete_station(sid)
    with pytest.raises(ValueError):
        repo.get_station(sid)
```

**Migration Testing:**
```python
def test_migration_idempotent(repo_with_legacy_data):
    """Running db_init() twice does not duplicate stream rows or raise errors."""
    repo = repo_with_legacy_data
    db_init(repo.con)
    count = repo.con.execute("SELECT COUNT(*) FROM station_streams").fetchone()[0]
    assert count == 2  # not duplicated
```

**Qt Widget Testing with qtbot:**
```python
def test_main_window_constructs_and_renders(qtbot):
    window = _make_window()
    qtbot.addWidget(window)  # register for cleanup
    window.show()
    qtbot.waitExposed(window)  # wait for expose event in offscreen platform
    
    assert window.windowTitle() == "MusicStreamer"
    assert isinstance(window, QMainWindow)
```

**Signal Testing:**
```python
def test_swatch_populates_hex_entry(qtbot, dialog):
    """Clicking a swatch populates the hex entry with the matching preset."""
    for idx, preset_hex in enumerate(ACCENT_PRESETS):
        dialog._on_swatch_clicked(idx)  # triggers signal
        assert dialog._hex_edit.text() == preset_hex  # effect visible
```

**Mocking Qt Signals:**
```python
# Use MagicMock() for objects that need to receive signals but don't need real behavior
player = MagicMock()
player._current_station_name = ""

# Signals are MagicMock attributes
player.title_changed.connect(slot)  # works but is a mock call
```

## Conftest Features

**QT_QPA_PLATFORM Setup:**
```python
# tests/conftest.py line 13
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```
- Sets Qt to headless offscreen rendering (no X11/Wayland needed)
- Allows tests to run on CI and headless dev boxes
- Must happen BEFORE any PySide6 import

**Autouse Bus Bridge Stub:**
```python
# tests/conftest.py line 20-30
@pytest.fixture(autouse=True)
def _stub_bus_bridge(monkeypatch):
    """Replace _ensure_bus_bridge with a MagicMock so Player() construction
    never starts the real GLib.MainLoop daemon thread in unit tests."""
    try:
        import musicstreamer.player as _player_mod
    except ImportError:
        return
    monkeypatch.setattr(
        _player_mod, "_ensure_bus_bridge", lambda: MagicMock()
    )
```
- Prevents every unit test from spinning up a real GLib daemon thread
- Uses `autouse=True` so applies to all tests without explicit declaration
- Only GStreamer bus bridge tests use the real bridge

## Test Examples by Category

**Database/Repository Tests:** `tests/test_repo.py` (460+ lines)
- Fixture creates ephemeral SQLite db with `tmp_path`
- Tests schema, migrations, CRUD, cascade deletes
- Comprehensive coverage of legacy data migration path

**Player/GStreamer Tests:** `tests/test_player_volume.py`, `tests/test_player_tag.py`
- Mock `Gst.ElementFactory.make()` for pipeline construction
- Assert on mocked property setters, no real GStreamer rendering
- Test audio codec, volume, ICY tag handling

**Qt UI Tests:** `tests/test_accent_color_dialog.py`, `tests/test_edit_station_dialog.py`
- Use `qtbot` fixture to manage widget lifecycle
- Use `FakeRepo` for fast dependency injection
- Test user interactions (button clicks, field population)
- Assert on dialog state after actions

**External API Tests:** `tests/test_cookies.py`, `tests/test_yt_thumbnail.py`
- Mock HTTP clients (urllib.request, iTunes API)
- Test URL parsing and query building
- Mock context managers (YoutubeDL, streamlink)

**Pure Function Tests:** `tests/test_filter_utils.py`, `tests/test_aa_url_detection.py`
- No fixtures, no mocking
- Direct function calls with known inputs
- Assert on return values

---

*Testing analysis: 2026-04-28*
