# Codebase Structure

**Analysis Date:** 2026-04-28

## Directory Layout

```
MusicStreamer/
├── musicstreamer/              # Main package
│   ├── __main__.py             # Entry point (Qt + headless modes)
│   ├── __init__.py             # Package marker (empty)
│   ├── __version__.py           # Version string
│   │
│   ├── player.py               # GStreamer playback engine
│   ├── gst_bus_bridge.py       # GLib.MainLoop daemon thread
│   ├── models.py               # Dataclasses (Station, StationStream, Favorite)
│   ├── repo.py                 # SQLite CRUD layer
│   ├── constants.py            # App-wide constants + PEP 562 __getattr__
│   ├── paths.py                # XDG data dir discovery
│   │
│   ├── stream_ordering.py       # Algorithm: order streams by quality/position
│   ├── cover_art.py            # iTunes API worker thread
│   ├── radio_browser.py        # Radio-Browser API queries
│   ├── filter_utils.py         # Station search/filter helpers
│   ├── accent_utils.py         # Palette manipulation (Phase 19)
│   ├── accent_color_dialog.py  # (moved to ui_qt/)
│   │
│   ├── oauth_helper.py         # Generic OAuth flow (YouTube auth)
│   ├── oauth_log.py            # OAuth debug logging
│   ├── cookie_utils.py         # YouTube cookies.txt handling
│   ├── yt_import.py            # YouTube URL → Station import
│   ├── aa_import.py            # AudioAddict JSON import
│   │
│   ├── migration.py            # First-launch DB migration (PORT-06)
│   ├── single_instance.py      # App singleton lock (D-10)
│   ├── runtime_check.py        # Node.js / tool availability checks
│   ├── subprocess_utils.py     # Subprocess wrappers
│   ├── url_helpers.py          # URL parsing utilities
│   ├── settings_export.py      # Export/import settings as ZIP
│   ├── eq_profile.py           # Equalizer profile parsing (Phase 47.2)
│   ├── assets.py               # Resource bundling
│   │
│   ├── media_keys/             # Platform media-session backends
│   │   ├── __init__.py         # Factory (create function)
│   │   ├── base.py             # Abstract MediaKeysBackend
│   │   ├── mpris2.py           # Linux D-Bus MPRIS2 backend
│   │   ├── smtc.py             # Windows SMTC/winrt backend
│   │   └── _art_cache.py       # PNG cover caching for media-keys
│   │
│   └── ui_qt/                  # PySide6 Qt GUI
│       ├── __init__.py         # Package marker
│       ├── main_window.py      # QMainWindow root + signal wiring
│       ├── now_playing_panel.py # Right panel (track info + controls)
│       ├── station_list_panel.py # Left panel (station tree + favorites)
│       ├── station_tree_model.py # QAbstractItemModel (2-level tree)
│       ├── station_filter_proxy.py # QSortFilterProxyModel (search)
│       ├── station_star_delegate.py # Star button rendering in tree
│       │
│       ├── favorites_view.py   # Favorites tab UI (Phase 38)
│       ├── accent_color_dialog.py # (D-12: moved from parent)
│       ├── accounts_dialog.py  # Account management dialog
│       ├── discovery_dialog.py # Radio-Browser discovery
│       ├── import_dialog.py    # Station import dialog
│       ├── cookie_import_dialog.py # YouTube cookie import
│       ├── edit_station_dialog.py # Manual station creation
│       ├── equalizer_dialog.py # EQ adjustment dialog (Phase 47.2)
│       ├── eq_response_curve.py # EQ response graph visualization
│       │
│       ├── toast.py            # Toast notification overlay
│       ├── flow_layout.py       # Custom layout (wrapping chips)
│       ├── _art_paths.py       # Art file resolution (Station → QPixmap)
│       ├── _theme.py           # Theme constants (icon sizes, colors)
│       ├── icons_rc.py         # Qt resource file (auto-generated from icons/)
│       ├── settings_import_dialog.py # Settings ZIP import preview
│       │
│       └── icons/              # SVG icon sources
│           ├── app-icon.svg
│           ├── audio-x-generic-symbolic.svg
│           └── ...
│
├── tests/                      # Pytest suite
│   ├── __init__.py
│   ├── test_main_window_integration.py # GUI smoke test
│   ├── test_now_playing_panel.py
│   ├── test_station_list_panel.py
│   ├── test_station_tree_model.py
│   ├── test_station_filter_proxy.py
│   ├── test_ui_qt_scaffold.py
│   ├── test_media_keys_scaffold.py # MPRIS2/SMTC interface tests
│   ├── test_media_keys_smtc.py # Windows-specific SMTC tests
│   ├── test_headless_entry.py   # --smoke flag test
│   ├── test_player_volume.py    # Player.set_volume()
│   ├── test_player_tag.py       # ICY tag extraction
│   ├── test_art_paths.py        # Art resolution logic
│   ├── test_repo.py             # CRUD operations
│   ├── test_migration.py        # First-launch migration
│   ├── test_radio_browser.py    # Radio-Browser API
│   ├── test_discovery_dialog.py
│   ├── test_edit_station_dialog.py
│   ├── test_cookie_import_dialog.py
│   ├── test_equalizer_dialog.py
│   ├── test_windows_palette.py  # Windows dark-mode palette
│   ├── test_twitch_auth.py
│   ├── test_aa_url_detection.py
│   └── test_stream_picker.py
│
├── packaging/                  # Platform-specific packaging
│   ├── windows/                # PyInstaller spec + runtime hooks
│   └── ...
│
├── .planning/                  # Planning documents (phases, concerns)
│   └── codebase/               # This directory
│       ├── ARCHITECTURE.md
│       └── STRUCTURE.md
│
├── .claude/                    # Claude-specific config
│   └── skills/
│       └── spike-findings-musicstreamer/
│
├── pyproject.toml             # Project metadata + dependencies
├── Makefile                   # Test/build targets
└── README.md                  # User-facing docs

```

## Directory Purposes

**musicstreamer/:**
- Purpose: Main application package
- Contains: Core playback engine, data model, UI layer
- Key files: `player.py` (GStreamer), `repo.py` (database), `__main__.py` (entry)

**musicstreamer/media_keys/:**
- Purpose: Platform-specific media-session integration
- Contains: MPRIS2 (Linux), SMTC (Windows), abstract base class
- Key files: `base.py` (interface), `mpris2.py` (Linux D-Bus), `smtc.py` (Windows winrt)

**musicstreamer/ui_qt/:**
- Purpose: PySide6 GUI widgets and dialogs
- Contains: QMainWindow, panels, tree models, dialogs
- Key files: `main_window.py` (root), `station_list_panel.py` (left), `now_playing_panel.py` (right)

**tests/:**
- Purpose: Pytest suite
- Contains: Unit tests (models, widgets), integration tests (player + GStreamer), UI smoke tests
- Key files: `test_main_window_integration.py` (GUI entry), `test_player_volume.py` (backend)

**packaging/:**
- Purpose: Platform-specific bundling
- Contains: Windows PyInstaller spec, runtime hooks, conda-forge build scripts
- Key files: (Phase 44+; currently empty in production)

**.planning/codebase/:**
- Purpose: Architecture/design reference documents
- Contains: ARCHITECTURE.md, STRUCTURE.md, TESTING.md, CONVENTIONS.md

## Key File Locations

**Entry Points:**
- `musicstreamer/__main__.py`: CLI entry point; dispatches to `_run_gui()` (default) or `_run_smoke()` (--smoke URL)
- `musicstreamer/__init__.py`: Package marker (empty)

**Configuration:**
- `pyproject.toml`: Dependencies, version, optional features (test, windows)
- `musicstreamer/paths.py`: XDG data/config directory discovery
- `musicstreamer/constants.py`: App-wide constants + PEP 562 __getattr__ for paths

**Core Logic:**
- `musicstreamer/player.py`: GStreamer playbin3 pipeline, failover queue, resolvers (yt-dlp, streamlink)
- `musicstreamer/gst_bus_bridge.py`: GLib.MainLoop daemon thread for async bus handlers
- `musicstreamer/repo.py`: SQLite CRUD wrapper
- `musicstreamer/models.py`: Station, StationStream, Favorite dataclasses

**Testing:**
- `tests/test_main_window_integration.py`: GUI construction smoke test
- `tests/test_headless_entry.py`: `--smoke` URL playback harness
- `tests/test_player_volume.py`: Player.set_volume() unit test
- `tests/test_repo.py`: Database CRUD tests

**UI Widgets:**
- `musicstreamer/ui_qt/main_window.py`: QMainWindow root (splitter layout + menu + signal wiring)
- `musicstreamer/ui_qt/station_list_panel.py`: Left panel (tree + search + favorites tab)
- `musicstreamer/ui_qt/now_playing_panel.py`: Right panel (metadata + controls)

**Platform Integration:**
- `musicstreamer/media_keys/mpris2.py`: Linux MPRIS2 D-Bus service
- `musicstreamer/media_keys/smtc.py`: Windows SMTC media-session backend
- `musicstreamer/ui_qt/_theme.py`: Theme constants (icon sizes, colors)

## Naming Conventions

**Files:**
- `_private_module.py` — Internal-only (underscore prefix; not re-exported)
- `module_name.py` — Public module
- `module_dialog.py` — QDialog subclass
- `module_panel.py` — QWidget panel subclass
- `*_model.py` — QAbstractItemModel subclass
- `test_*.py` — Pytest test file

**Directories:**
- Lowercase, underscore-separated (`media_keys`, `ui_qt`)
- Logical grouping by layer or concern (UI, platform, data)

**Classes:**
- PascalCase (Python standard): `Player`, `MediaKeysBackend`, `StationListPanel`
- Internal helper classes prefixed with `_`: `_TreeNode`, `_MutedLabel`, `_ExportWorker`

**Functions/Variables:**
- snake_case (Python standard): `db_connect()`, `order_streams()`, `_on_gst_error()`
- Private module functions prefixed with `_`: `_set_uri()`, `_try_next_stream()`
- Signal handlers named `on_*` or `_on_*`: `on_title_changed()`, `_on_station_activated()`

**Qt Signals:**
- Descriptive names, verb-last (signal announces completion): `title_changed`, `failover`, `station_activated`
- Internal signals prefixed with `_`: `_error_recovery_requested`, `_cancel_timers_requested`

**Constants:**
- UPPERCASE_WITH_UNDERSCORES: `BUFFER_DURATION_S`, `QUALITY_PRESETS`, `ACCENT_COLOR_DEFAULT`
- Module-level PEP 562 __getattr__ for dynamic paths: `DATA_DIR`, `DB_PATH`, `ASSETS_DIR`

## Where to Add New Code

**New Feature (Station Type):**
- Core logic: Add resolver method in `musicstreamer/player.py` (e.g., `_play_radio_station()`)
- URL detection: Update URL routing in `_try_next_stream()` (Phase 47 pattern)
- Tests: `tests/test_player_*.py`

**New Component/Module:**
- If backend logic: `musicstreamer/module_name.py` (import in __main__.py if it's an entry point)
- If UI widget: `musicstreamer/ui_qt/module_name.py` (inherit from QWidget/QDialog)
- If platform-specific: `musicstreamer/media_keys/module_name.py`
- Tests: `tests/test_module_name.py`

**Utilities:**
- Shared helpers (no side effects): `musicstreamer/util_name.py` (e.g., `filter_utils.py`, `url_helpers.py`)
- Tests: `tests/test_util_name.py`

**Dialogs:**
- Qt dialogs: `musicstreamer/ui_qt/dialog_name_dialog.py` (e.g., `edit_station_dialog.py`)
- Tests: `tests/test_dialog_name_dialog.py`

**Data Models:**
- Dataclasses: Extend `musicstreamer/models.py` (or separate file if >100 lines)
- Database layer: Methods in `musicstreamer/repo.py` Repo class

## Special Directories

**musicstreamer/ui_qt/icons/:**
- Purpose: SVG icon sources
- Generated: No; committed to git
- Process: SVG files are compiled into `icons_rc.py` via Qt resource compiler (rcc)
- Import side effect: `from musicstreamer.ui_qt import icons_rc  # noqa: F401` registers `:/icons/` resource prefix
- Usage: `QIcon(":/icons/app-icon.svg")` or `QPixmap(":/icons/audio-x-generic-symbolic.svg")`

**musicstreamer/__pycache__/:**
- Purpose: Python bytecode cache
- Generated: Yes; auto-created by Python
- Committed: No (.gitignore)

**.planning/codebase/:**
- Purpose: Reference documentation (auto-generated by gsd-map-codebase)
- Files:
  - `ARCHITECTURE.md` — System design, layers, data flow
  - `STRUCTURE.md` — Directory layout, file purposes
  - `CONVENTIONS.md` — Naming, code style, import organization
  - `TESTING.md` — Test framework, structure, patterns
  - `CONCERNS.md` — Technical debt, known bugs, security issues
- Committed: Yes (versioned with code)

---

*Structure analysis: 2026-04-28*
