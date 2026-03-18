# Architecture

**Analysis Date:** 2026-03-18

## Pattern Overview

**Overall:** Monolithic single-file application using layered architecture with clear separation between data access, business logic, and UI presentation.

**Key Characteristics:**
- Single-file Python application (`main.py`) with 512 lines of code
- Data persistence layer (SQLite database)
- Domain models using Python dataclasses
- GTK4/Libadwaita UI framework with GStreamer for media playback
- External service integration for YouTube URL resolution via yt-dlp

## Layers

**Data Access Layer (Repository):**
- Purpose: Abstracts SQLite database operations and enforces data consistency
- Location: `main.py` lines 88-180 (class `Repo`)
- Contains: Database queries, data persistence, transaction management
- Depends on: `sqlite3` module, dataclass models
- Used by: UI layer (EditStationDialog, MainWindow)
- Operations: List/create/get/update stations, manage providers

**Domain Model Layer:**
- Purpose: Represents core business concepts
- Location: `main.py` lines 70-86
- Contains: `Provider` and `Station` dataclasses
- Depends on: Python `dataclasses` module
- Used by: Repository and UI layer
- Pattern: Immutable dataclasses with optional fields for nullable relationships

**Business Logic Layer:**
- Purpose: Handles cross-cutting concerns like file management and initialization
- Location: `main.py` lines 27-36 (DB setup), lines 182-197 (asset management), lines 411-447 (playback resolution)
- Contains: Database initialization, asset file copying, URL resolution for YouTube
- Depends on: `sqlite3`, `shutil`, `yt_dlp`, `os` modules
- Used by: Application startup and playback handling
- Pattern: Functions at module level (not class-based)

**UI Presentation Layer:**
- Purpose: Renders user interface and handles user interactions
- Location: `main.py` lines 200-493 (classes `EditStationDialog`, `MainWindow`)
- Contains: GTK window setup, form controls, list rendering, playback controls
- Depends on: `Gtk`, `Adw`, `Gst` bindings via `gi.repository`
- Used by: Application entry point
- Pattern: GTK4 Adwaita window classes with signal-based event handling

**Application Entry Point:**
- Purpose: Bootstraps the application and manages application lifecycle
- Location: `main.py` lines 495-511 (class `App`)
- Triggers: System application launch, GTK main loop activation
- Responsibilities: Initialization of database, repository, main window; connection of services

## Data Flow

**Playback Flow:**

1. User double-clicks station row in UI → `MainWindow._play_row()` called
2. Station data fetched from database via `repo.get_station(station_id)`
3. `MainWindow._play_station(st: Station)` called with station object
4. For YouTube URLs: yt-dlp extracts playable stream URL via `YoutubeDL.extract_info()`
5. GStreamer `playbin` element receives URI via `set_property("uri", stream_url)`
6. Playback state set to `Gst.State.PLAYING`, UI label updated
7. Audio output routed to system audio sink (PulseAudio/PipeWire)

**Station CRUD Flow:**

1. Create: User clicks "Add Station" → `repo.create_station()` inserts row → new ID returned → EditStationDialog opens
2. Read: `repo.get_station()` or `repo.list_stations()` fetch from DB with provider JOIN
3. Update: EditStationDialog collects form inputs → `repo.update_station()` executes UPDATE → `on_saved` callback triggers UI reload
4. Delete: Not implemented (concern)

**Asset Management Flow:**

1. User selects image file via `EditStationDialog._choose_station_art()` or `_choose_album_art()`
2. File picker dialog (`Gtk.FileDialog`) filters for PNG/JPEG/WebP
3. `copy_asset_for_station()` copies file to `~/.local/share/musicstreamer/assets/<station_id>/<kind>.<ext>`
4. Relative path stored in database column
5. UI loads image via `Gtk.Picture.new_for_filename(abs_path)` for display

**State Management:**

- **Database as source of truth:** All persistent state (stations, providers, asset paths) stored in SQLite
- **Repository pattern:** `Repo` class holds connection reference and methods; stateless query functions
- **UI-local state:** Temporary edit state in `EditStationDialog` (`self.station_art_rel`, `self.album_art_rel`) before save
- **Playback state:** Tracked in GStreamer pipeline; minimal synchronization to UI label
- **List state:** `MainWindow` lazily reloads entire station list on `reload_list()` after edits

## Key Abstractions

**Station:**
- Purpose: Represents a radio station/stream with metadata
- Location: `main.py` lines 76-86
- Fields: `id`, `name`, `url`, `provider_id`, `provider_name`, `tags`, `station_art_path`, `album_fallback_path`
- Pattern: Immutable dataclass; `provider_name` computed from JOIN in repository

**Provider:**
- Purpose: Represents a provider/network (e.g., "Chillhop")
- Location: `main.py` lines 70-74
- Fields: `id`, `name`
- Pattern: Immutable dataclass; enforced unique by database constraint

**Repo:**
- Purpose: Data access abstraction layer
- Location: `main.py` lines 88-180
- Pattern: Instance holds connection; methods execute queries and return dataclass objects
- Responsibility isolation: All SQL logic centralized; no direct queries from UI

## Entry Points

**Application Entry:**
- Location: `main.py` line 509-511
- Triggers: Script executed as `python3 main.py` or system app launcher
- Responsibilities: Create `App()` instance and call `run(sys.argv)` to start GTK main loop

**do_activate() Method:**
- Location: `main.py` lines 499-506
- Triggers: GTK application activation (called after app initialization and signal handling setup)
- Responsibilities: Create data directories, initialize database, instantiate Repo, create and present MainWindow

**MainWindow Initialization:**
- Location: `main.py` lines 358-400
- Triggers: Called from `App.do_activate()`
- Responsibilities: Initialize GStreamer playbin, set up UI widgets (header bar, list box), load station list

**EditStationDialog Initialization:**
- Location: `main.py` lines 200-282
- Triggers: Called when user clicks "Add Station" or existing station row → `_open_editor()`
- Responsibilities: Load station data, render form controls, set up image pickers, display previews

## Error Handling

**Strategy:** Mix of exception catching and defensive checks. Errors logged to console; limited user feedback.

**Patterns:**

- **Database errors:** `ValueError` raised in `repo.get_station()` if station not found (line 148)
- **File operations:** `os.path.exists()` checks before loading images; silent failure if file missing (lines 288, 295)
- **YouTube resolution:** Try-catch around `YoutubeDL.extract_info()` with fallback error label (lines 427-435)
- **GLib async errors:** Caught generically in file dialog callback (line 318: `except GLib.Error`)
- **UI validation:** Defensive text stripping; empty names replaced with "Unnamed" (line 336)
- **Missing URLs:** Checked before playback attempt (lines 412-415)

## Cross-Cutting Concerns

**Logging:**
- No structured logging framework
- Console `print()` statements for errors (line 434: "yt-dlp error: {e}")
- No persistent audit trail

**Validation:**
- Input validation in `EditStationDialog._save()`: text stripping, empty name handling
- Database constraints: `UNIQUE` on provider names, `NOT NULL` on station name/url
- File type filtering: MIME type filters in file dialog (PNG, JPEG, WebP)

**Authentication:**
- None implemented. Application assumes single-user desktop environment.
- File permissions rely on system directory permissions (~/.local/share/)

**Cleanup:**
- Database connection passed through application lifecycle; no explicit close (connection will be garbage collected)
- Temporary files: Image assets stored persistently (by design); no cleanup of orphaned assets

---

*Architecture analysis: 2026-03-18*
