# Codebase Structure

**Analysis Date:** 2026-03-18

## Directory Layout

```
MusicStreamer/
├── main.py                                # Application entry point and all code
├── stations.json                          # Sample station data (not used at runtime)
├── org.example.Streamer.desktop           # Desktop shortcut file
├── .planning/
│   └── codebase/                         # Analysis documents (generated)
├── .git/                                 # Version control
├── .idea/                                # IDE configuration
└── ~/.local/share/musicstreamer/         # Runtime data directory (created by app)
    ├── musicstreamer.sqlite3             # SQLite database
    └── assets/                           # Station artwork storage
        └── <station_id>/
            ├── station_art.<ext>         # Station logo/image
            └── album_fallback.<ext>      # Default album artwork
```

## Directory Purposes

**Project Root:**
- Purpose: Single-file Python project for desktop music streaming application
- Contains: Main application code, configuration files, documentation scaffolding
- Key files: `main.py` (512 lines, only application code)

**~/.local/share/musicstreamer/ (Runtime):**
- Purpose: User data directory (created at first launch by `ensure_dirs()`)
- Contains: SQLite database, cached/user artwork
- Key files:
  - `musicstreamer.sqlite3`: Persistent station and provider data
  - `assets/<station_id>/`: Image files copied from user's filesystem

**.planning/codebase/ (Analysis):**
- Purpose: Generated documentation for code navigation and future development
- Contains: ARCHITECTURE.md, STRUCTURE.md, and other analysis documents
- Generated: Yes (created by GSD mapping tool)
- Committed: Yes

## Key File Locations

**Entry Points:**
- `main.py`: Single Python script containing all application code. Executed as `python3 main.py` or via desktop launcher.

**Configuration:**
- `org.example.Streamer.desktop`: Desktop application shortcut (empty in current state)
- Constants in `main.py` lines 18-23: APP_ID, DATA_DIR, DB_PATH, ASSETS_DIR

**Core Logic:**
- Data layer (lines 27-180): Database initialization, connection, repository
- Domain models (lines 70-86): Provider and Station dataclasses
- Business logic (lines 182-447): Asset management, playback pipeline
- UI layer (lines 200-493): EditStationDialog and MainWindow classes
- Application (lines 495-511): App class and entry point

**Testing:**
- Not applicable. No test directory or test files present.

## Naming Conventions

**Files:**
- Python module: `main.py` (lowercase, underscore-separated)
- Data file: `stations.json` (lowercase, JSON format)
- Desktop entry: `org.example.Streamer.desktop` (reverse domain notation)

**Directories:**
- Runtime data: `~/.local/share/musicstreamer/` (lowercase, hyphenated)
- Asset subdirectory: `assets/<station_id>/` (plural for collections, numeric IDs)
- Planning: `.planning/codebase/` (dot-prefixed for hidden/meta directories)

**Functions and Methods:**
- Public functions: `ensure_dirs()`, `db_connect()`, `copy_asset_for_station()` (snake_case)
- Private methods: `_play_row()`, `_choose_file()`, `_refresh_pictures()` (leading underscore convention)
- Callbacks: `_save()`, `done()`, `set_art()` (action verbs, snake_case)

**Variables:**
- Instance variables: `self.player`, `self.station_id`, `self.listbox` (snake_case)
- Local variables: `con` (abbreviation for connection), `st` (abbreviation for station), `row`, `flt` (filter)
- Constants: `APP_ID`, `DATA_DIR`, `DB_PATH`, `ASSETS_DIR` (UPPER_CASE)

**Types:**
- Classes: `Provider`, `Station`, `Repo`, `EditStationDialog`, `MainWindow`, `App` (PascalCase)
- Dataclasses: `@dataclass` decorator on domain models
- Type hints: `Optional[int]`, `List[Station]`, `sqlite3.Connection` (used throughout)

**SQL/Database:**
- Table names: `providers`, `stations` (lowercase, plural)
- Column names: `id`, `name`, `url`, `provider_id`, `tags`, `station_art_path`, `album_fallback_path` (snake_case)
- Foreign key convention: `provider_id` references `providers(id)`

## Where to Add New Code

**New Feature (e.g., delete station, import/export):**
- Primary code: Add method to `Repo` class (lines 88-180) for data operations
- UI handler: Add method to `MainWindow` (lines 358-493) or `EditStationDialog` (lines 200-356)
- Database schema: Add migration to `db_init()` (lines 39-66) if needed
- Example: To add delete, add `Repo.delete_station(station_id)` method using `con.execute("DELETE FROM stations WHERE id = ?", ...)`, then add UI button with `MainWindow._delete_selected()` handler

**New Component/Module:**
- Keep in `main.py` to maintain single-file structure
- Follow class-based organization: Data (dataclass) → Repository (methods) → UI (GTK window class)
- If file grows beyond 1000 lines, consider splitting: `models.py`, `repo.py`, `ui.py`, but keep imports minimal

**Utilities (asset handling, playback resolution):**
- Shared helpers at module level (lines 27-197): Keep utility functions before class definitions
- Pattern: Define function with clear input/output, use at module scope before class instantiation
- Example: `copy_asset_for_station()` (lines 182-197) is called from UI layer

**Database Schema Changes:**
- Add table definitions or columns to `db_init()` executescript (lines 39-66)
- Create trigger as needed (example: `stations_updated_at` trigger on line 60)
- Run `db_init()` at startup; it uses `IF NOT EXISTS` to be idempotent

**UI Components:**
- Dialogs: Inherit from `Adw.Window` (see `EditStationDialog` lines 200-356)
- Main windows: Inherit from `Adw.ApplicationWindow` (see `MainWindow` lines 358-493)
- Use `Adw.ToolbarView` for consistent header/content layout
- Connect signals with `.connect("signal-name", handler_method)`

## Special Directories

**Runtime Data (~/.local/share/musicstreamer/):**
- Purpose: User-persistent state; created by `ensure_dirs()` at startup
- Generated: Yes (created if not present)
- Committed: No (user data, outside repository)
- Cleanup: Manual (user must delete ~/.local/share/musicstreamer/ to reset)

**Assets Directory (~/.local/share/musicstreamer/assets/):**
- Purpose: Cache for station artwork and default album art
- Generated: Yes (subdirectories created per station as images added)
- Committed: No (file storage, outside repository)
- Pattern: Images organized by `<station_id>/<kind>.<ext>` (e.g., `assets/12/station_art.png`)

**.planning/ Directory:**
- Purpose: Generated analysis and planning documents
- Generated: Yes (created by GSD tools)
- Committed: Yes (committed to repository for team reference)
- Usage: Referenced by `/gsd:plan-phase` and `/gsd:execute-phase` commands

**.git/ and .idea/ Directories:**
- Purpose: Version control and IDE metadata
- Generated: Yes
- Committed: Partially (.git tracked by git; .idea may be .gitignored)
- Not to be modified during feature development

## Module Organization Pattern

All code is in a single file (`main.py`) organized in this order:

1. **Imports** (lines 1-16): Standard library, third-party, GTK/GStreamer bindings
2. **Constants** (lines 18-23): Configuration and paths
3. **Initialization** (line 24): `Gst.init(None)`
4. **Utility functions** (lines 27-197): Database, asset management
5. **Domain models** (lines 70-86): Dataclasses (placed before repository that uses them)
6. **Repository class** (lines 88-180): Data access layer
7. **UI classes** (lines 200-493): EditStationDialog, MainWindow
8. **Application class** (lines 495-506): App entry point
9. **Entry point** (lines 509-511): `if __name__ == "__main__"` guard

**Rationale:** Dependencies flow downward; utilities support repository which supports UI.

---

*Structure analysis: 2026-03-18*
