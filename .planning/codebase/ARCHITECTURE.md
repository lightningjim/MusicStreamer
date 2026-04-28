<!-- refreshed: 2026-04-28 -->
# Architecture

**Analysis Date:** 2026-04-28

## System Overview

MusicStreamer is a Python/PySide6 desktop audio streamer with GStreamer backend. It plays internet radio stations (AudioAddict, SomaFM, ShoutCast, YouTube, Twitch) with platform-specific media-session integration (MPRIS2 on Linux, SMTC on Windows).

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                    Qt GUI Layer (PySide6 Widgets)                       │
│  MainWindow (QMainWindow) — centralWidget QSplitter                     │
├──────────────────────────┬──────────────────────────┬──────────────────┤
│  StationListPanel        │   NowPlayingPanel        │   Toast Overlay  │
│  `ui_qt/station_list`    │   `ui_qt/now_playing`    │   `ui_qt/toast`  │
│  - StationTreeModel      │   - Display + Controls   │   - Notifications│
│  - StationFilterProxy    │   - Cover Art Fetch      │   - Errors/Info  │
└──────────────┬───────────┴──────────────┬───────────┴──────────────────┘
               │                          │
               │                          │
               ▼                          ▼
┌────────────────────────────────────────────────────────────────────────┐
│              Player (QObject, Qt Signals/Slots)                         │
│  `musicstreamer/player.py`                                              │
│  - Failover Queue Management (stream ordering)                          │
│  - YouTube Resolver (yt-dlp + Node.js)                                  │
│  - Twitch Resolver (streamlink)                                          │
│  - Equalizer State (Phase 47.2)                                          │
│  - Elapsed Time Tracking (1Hz timer)                                     │
└────────────────┬──────────────────────────────────────────────┬─────────┘
                 │                                              │
                 ▼                                              ▼
    ┌──────────────────────────┐         ┌──────────────────────────┐
    │ GStreamer Bus Bridge     │         │ Platform Media-Keys      │
    │ (GLib.MainLoop thread)   │         │ Backend (D-Bus/winrt)    │
    │ `gst_bus_bridge.py`      │         │ `media_keys/*.py`        │
    │ - message::error handler │         │ - Linux: MPRIS2          │
    │ - message::tag handler   │         │ - Windows: SMTC          │
    │ - message::buffering     │         │ - Metadata Publishing    │
    └──────────────┬───────────┘         │ - Playback State Sync    │
                 │                       └──────────────────────────┘
                 │
                 ▼
    ┌──────────────────────────┐
    │  GStreamer Pipeline      │
    │  (playbin3 element)      │
    │                          │
    │ - pulsesink (audio)      │
    │ - equalizer-nbands (EQ) │
    │ - Adaptive buffering     │
    └──────────────┬───────────┘
                   │
                   ▼
         ┌─────────────────┐
         │  Audio Hardware │
         └─────────────────┘
                   ▲
                   │ (audio output)

┌────────────────────────────────────────────────────────────────────────┐
│                     Data Layer (SQLite)                                 │
│  `musicstreamer/repo.py` — Data Access Object                          │
│  - Stations table (with streams)                                        │
│  - Favorites table (starred tracks)                                     │
│  - Settings table (accent color, volume, etc.)                          │
└────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| **MainWindow** | Qt window frame, menu bar, signal routing, error toasts | `ui_qt/main_window.py` |
| **StationListPanel** | Left panel: station tree, filter/search, favorites tab | `ui_qt/station_list_panel.py` |
| **StationTreeModel** | 2-level tree (providers → stations), icon caching | `ui_qt/station_tree_model.py` |
| **NowPlayingPanel** | Right panel: station art, track title, elapsed/controls | `ui_qt/now_playing_panel.py` |
| **Player** | GStreamer playback, failover, YouTube/Twitch resolvers | `musicstreamer/player.py` |
| **GstBusLoopThread** | GLib.MainLoop daemon for async GStreamer bus messages | `musicstreamer/gst_bus_bridge.py` |
| **MediaKeysBackend** | Abstract base for OS media-session integration | `musicstreamer/media_keys/base.py` |
| **LinuxMprisBackend** | MPRIS2 D-Bus service for Linux media controls | `musicstreamer/media_keys/mpris2.py` |
| **WindowsMediaKeysBackend** | Windows SMTC session for media buttons | `musicstreamer/media_keys/smtc.py` |
| **Repo** | SQLite queries: stations, favorites, settings CRUD | `musicstreamer/repo.py` |
| **CoverArt** | iTunes API worker thread for album art fetch | `musicstreamer/cover_art.py` |

## Pattern Overview

**Overall:** Multi-threaded event-driven architecture with explicit thread boundaries.

**Key Characteristics:**
- **Qt main thread:** All UI construction, QTimer, QObject signals/slots
- **GStreamer bus loop:** Daemon GLib.MainLoop on separate thread for pipeline bus watchers
- **Worker threads:** Ad-hoc threading.Thread for yt-dlp, streamlink, iTunes API (blocking I/O)
- **Cross-thread marshaling:** Signals with `QueuedConnection` explicitly bridge threads
- **No global state:** Each instance (Player, MainWindow) is self-contained; module-level `_BUS_BRIDGE` singleton is initialized on demand

## Layers

**Qt GUI (Presentation):**
- Purpose: Render station list, now-playing metadata, playback controls
- Location: `musicstreamer/ui_qt/`
- Contains: QWidget subclasses, signal connections, icon loading, dialogs
- Depends on: Player (signals), Repo (queries)
- Used by: QApplication via MainWindow

**Player (Playback Control):**
- Purpose: Manage GStreamer pipeline, failover queue, resolver threads
- Location: `musicstreamer/player.py`
- Contains: QObject with signals, GStreamer element setup, stream ordering
- Depends on: GstBusLoopThread, models (Station/StationStream), yt-dlp, streamlink
- Used by: MainWindow, NowPlayingPanel

**GStreamer Bus Bridge (Event Loop):**
- Purpose: Run GLib.MainLoop on daemon thread so bus handlers fire in Qt app
- Location: `musicstreamer/gst_bus_bridge.py`
- Contains: GLib.MainLoop setup, sync-call marshaling via `run_sync()`
- Depends on: GLib/gi.repository
- Used by: Player (Phase 35 PORT-02 contract)

**Media-Session (Platform Integration):**
- Purpose: Publish playback state + metadata to OS media-control surface
- Location: `musicstreamer/media_keys/*.py`
- Contains: Abstract MediaKeysBackend base class, platform subclasses (MPRIS2, SMTC)
- Depends on: PySide6.QtDBus or winrt wheels
- Used by: MainWindow (state sync), Player (metadata publish)

**Data Layer (Persistence):**
- Purpose: CRUD operations on SQLite database
- Location: `musicstreamer/repo.py`
- Contains: db_connect(), db_init(), Repo class with query methods
- Depends on: sqlite3, models (dataclasses)
- Used by: MainWindow, dialogs, settings persistence

## Data Flow

### Primary Request Path: User Plays a Station

1. User clicks station row in StationListPanel (`ui_qt/station_list_panel.py`)
2. `station_activated(Station)` signal emitted (`ui_qt/station_list_panel.py:100-120`)
3. MainWindow slot `_on_station_activated(station)` runs (`ui_qt/main_window.py:240+`)
4. Calls `player.play(station)` with preferred quality from settings (`musicstreamer/player.py:229`)
5. Player builds ordered stream queue via `order_streams()` (`musicstreamer/stream_ordering.py`)
6. Player calls `_try_next_stream()` to pop first stream (`musicstreamer/player.py:414`)
7. **URL routing:**
   - YouTube URL → `_play_youtube()` spawns worker thread with yt-dlp (`musicstreamer/player.py:460-474`)
   - Twitch URL → `_play_twitch()` spawns worker thread with streamlink
   - Direct URL (ShoutCast/Icecast) → `_set_uri()` sets playbin3 URI directly (`musicstreamer/player.py:450`)
8. Pipeline transitions to PLAYING state
9. GStreamer bus-loop thread (GstBusLoopThread) receives messages:
   - `message::tag` → extracts ICY title → emits `player.title_changed(str)` signal (queued to main)
   - `message::error` → emits `player.playback_error(str)`, triggers failover via `_handle_gst_error_recovery()` 
   - `message::buffering` → emits `player.buffer_percent(int)` de-duped signal
10. MainWindow receives `player.title_changed` → passes to `now_playing.on_title_changed()`
11. NowPlayingPanel updates title label; spawns iTunes worker thread for cover art
12. Cover art callback marshaled via `cover_art_ready` signal (QueuedConnection) updates pixmap

### Failover Flow (Stream Exhaustion)

1. GStreamer emits error message on bus (broken stream)
2. Bus-loop handler `_on_gst_error()` emits `_error_recovery_requested` signal (queued to main)
3. Main-thread slot `_handle_gst_error_recovery()` runs:
   - Sets `_recovery_in_flight` guard to coalesce cascading errors (Phase 43.1 bugfix)
   - If Twitch URL with < 1 retry: calls `_play_twitch()` (re-resolve via streamlink)
   - Else: calls `_try_next_stream()` (pop next from queue)
4. If queue empty: emits `player.failover(None)` → MainWindow shows "Stream exhausted" toast

### Elapsed Time Flow (Phase 40.1)

1. On first `player.play()` call, `_elapsed_timer` QTimer starts (`musicstreamer/player.py:438`)
2. Timer fires every 1000ms on main thread → `_on_elapsed_tick()` increments counter
3. Emits `player.elapsed_updated(int)` → MainWindow → `now_playing.on_elapsed_updated()`
4. UI updates displayed elapsed time (wall-clock, not reset on failover)

**State Management:**
- **Queue state:** `player._streams_queue` (list of StationStream)
- **Current stream:** `player._current_stream` (StationStream or None)
- **Recovery guard:** `player._recovery_in_flight` (bool, coalesces cascading errors)
- **Elapsed counter:** `player._elapsed_seconds` (int, preserved across failover)
- **Pipeline state:** Gst.State enum (NULL/PAUSED/PLAYING), managed by Player
- **UI state:** NowPlayingPanel holds current pixmaps, elapsed display; no persistence layer

## Key Abstractions

**Station/StationStream (Models):**
- Purpose: Represent a radio station and its alternate stream URLs
- Examples: `musicstreamer/models.py:Station`, `musicstreamer/models.py:StationStream`
- Pattern: Dataclass with optional fields (art_path, album_fallback_path, etc.)

**MediaKeysBackend (Interface):**
- Purpose: Platform-agnostic contract for OS media-session integration
- Examples: `musicstreamer/media_keys/base.py:MediaKeysBackend` (abstract), `mpris2.py:LinuxMprisBackend`, `smtc.py:WindowsMediaKeysBackend`
- Pattern: Abstract base with NotImplementedError; subclasses override `publish_metadata()`, `_apply_playback_state()`, `shutdown()`

**Resolver Pattern:**
- Purpose: Convert user-friendly URLs (youtube.com, twitch.tv) to direct HLS/MP3 URLs playable by GStreamer
- Examples: `_play_youtube()` with yt-dlp worker, `_play_twitch()` with streamlink worker
- Pattern: Blocking HTTP call on ad-hoc threading.Thread, emit Qt signal with result (queued to main)

## Entry Points

**Application Entry:**
- Location: `musicstreamer/__main__.py`
- Triggers: `python -m musicstreamer` or console script `musicstreamer`
- Responsibilities: Parse CLI args (--smoke for headless test), initialize Gst, construct QApplication/MainWindow, start event loop
- CLI paths:
  - `_run_gui()` (default) → QApplication + MainWindow + Player + Repo + single-instance lock + Node.js check
  - `_run_smoke()` (--smoke URL) → QCoreApplication + Player only (no UI, for regression testing)

**Player Initialization:**
- Constructs playbin3 element with audio sink (pulsesink on Linux) and equalizer-nbands element (Phase 47.2)
- Ensures GstBusLoopThread is running via `_ensure_bus_bridge()` (module-level singleton)
- Wires bus handlers for error/tag/buffering async messages (via daemon thread)
- Creates QTimer objects for failover timeout and elapsed-time 1Hz tick

**Media-Keys Factory:**
- Location: `musicstreamer/media_keys/__init__.py:create(player, repo)`
- Called from: MainWindow constructor after all panels are ready
- Dispatch logic:
  - `sys.platform.startswith("linux")` → tries `LinuxMprisBackend`, falls back to NoOp on any Exception
  - `sys.platform == "win32"` → tries `create_windows_backend()`, falls back to NoOp on any Exception
  - Other → NoOp immediately
- No-op fallback guarantees app startup never blocks (D-06 requirement)

## Architectural Constraints

- **Threading:** Qt main thread (QApplication.exec()) runs GUI + QTimer objects. GStreamer bus loop runs on daemon GLib.MainLoop thread. Workers (yt-dlp, streamlink, iTunes API) are ad-hoc threading.Thread instances with no Qt affinity.
- **Global state:** Only `musicstreamer/player.py:_BUS_BRIDGE` (module-level GstBusLoopThread singleton). All other state is instance-bound (MainWindow, Player, Repo).
- **Circular imports:** None detected; ui_qt modules import from core (player, repo, models) but not vice versa.
- **Signal marshaling:** Cross-thread Qt signals use `Qt.ConnectionType.QueuedConnection` explicitly; unmarked signals auto-select connection type based on thread affinity.
- **GStreamer pipeline state:** Player owns the pipeline and all state transitions. External code never calls `pipeline.set_state()` directly.
- **UI construction order:** QApplication must be constructed before single_instance.acquire_or_forward() (requires event loop). MainWindow construction must occur AFTER single-instance check (avoid constructing hidden window in second instance). Windows AUMID must be set BEFORE QApplication construction (Phase 43.1 bugfix).
- **Media-keys construction:** Must occur AFTER all panels are ready (MainWindow uses the backend for state sync). Fall-back to NoOp if D-Bus/winrt unavailable (D-06 non-blocking requirement).

## Anti-Patterns

### Sync Message Handlers on Bus

**What happens:** Code attempts to call `bus.connect("message::sync-...", handler)` in player.py

**Why it's wrong:** Sync handlers block the GStreamer streaming thread. Even a trivial handler that just logs will cause audio stuttering/dropout.

**Do this instead:** Only register async signal watches via `bus.add_signal_watch()`. All handlers run on GstBusLoopThread (daemon) and must only emit Qt signals, never touch Qt widgets directly or call GStreamer state-change methods. See `musicstreamer/player.py:116-132` for the correct pattern (D-07 comment).

### QTimer.singleShot() from GstBusLoopThread

**What happens:** Bus handler calls `QTimer.singleShot(0, callback)` to marshal work to main thread. Qt ignores it silently.

**Why it's wrong:** QTimer objects have thread affinity. singleShot(0, ...) from a non-Qt-thread posts to the calling thread's default MainContext, which is not iterated on Windows. The callback never fires.

**Do this instead:** Emit a Qt Signal with `QueuedConnection` from the bus handler. Qt auto-detects thread mismatch and queues to the target object's thread. See `musicstreamer/player.py:82-88` for the pattern (Phase 43.1 cross-thread marshaling signals).

### Constructing QTimer on GstBusLoopThread

**What happens:** Code tries to create a QTimer in a bus handler or worker thread to schedule delayed work.

**Why it's wrong:** QTimer requires the main Qt event loop to fire. If constructed on a daemon thread with no event loop, it will never fire.

**Do this instead:** Emit a queued Qt signal from the worker/bus handler. Let the main thread (which constructed the Player QObject) handle the delayed work via its own QTimer. See `musicstreamer/player.py:135-148` for QTimer construction pattern (only on main thread).

### Calling add_signal_watch() from Main Thread

**What happens:** Phase 43.1 latent bug: code calls `bus.add_signal_watch()` inline on the main thread.

**Why it's wrong:** The call attaches the GSource to the main thread's default MainContext, which is NOT iterated by GLib (Qt event dispatcher is installed instead). Bus messages are queued but never dispatched.

**Do this instead:** Marshal `add_signal_watch()` onto the GstBusLoopThread via `run_sync()`. The bridge thread has its own thread-default MainContext that its GLib.MainLoop drives. See `musicstreamer/player.py:126` literal (D-07 comment, Phase 43.1 bugfix).

### Touching UI Widgets in Bus Handlers

**What happens:** Bus handler directly updates a label or pixmap (e.g., `label.setText(title)`).

**Why it's wrong:** Bus handlers run on GstBusLoopThread daemon, not the main thread. Qt widgets have thread affinity to the main thread; touching them from another thread causes memory corruption and crashes.

**Do this instead:** Bus handler emits a Qt signal (auto-queued to main), and a main-thread slot updates the UI. See `musicstreamer/player.py:375-376` for the pattern (title_changed signal).

## Error Handling

**Strategy:** Three-layer error recovery with graceful degradation.

**Patterns:**

1. **GStreamer pipeline errors:**
   - Bus handler emits `playback_error` signal (for toast)
   - Emits `_error_recovery_requested` queued signal (for main-thread recovery)
   - Main thread checks `_recovery_in_flight` guard to coalesce cascading errors (gap-05 fix)
   - If Twitch: retry resolve (streamlink may have stale auth)
   - Else: advance failover queue via `_try_next_stream()`
   - If queue empty: emit `failover(None)` signal (UI shows "Stream exhausted")

2. **Resolver failures (YouTube/Twitch):**
   - Worker thread catches exception during resolve
   - Emits error signal (queued to main) `youtube_resolution_failed(str)` or equiv.
   - Main thread advances failover via `_try_next_stream()`

3. **iTunes cover-art fetch failures:**
   - Worker thread catches HTTP error
   - Callback invoked with None
   - UI displays fallback generic icon (no toast, silent)

4. **Media-keys backend unavailable:**
   - Factory `create()` catches ImportError/RuntimeError
   - Returns NoOpMediaKeysBackend (D-06 requirement)
   - App starts normally, media buttons simply don't work

## Cross-Cutting Concerns

**Logging:**
- Module-level `_log = logging.getLogger(__name__)` in all non-UI modules
- WARNING level set globally in `__main__.py:179`
- Used for media-keys fallback warnings (`media_keys/__init__.py:42`)
- No debug logging in hot paths (bus handlers, timers)

**Validation:**
- StationStream quality field checked during ordering (`stream_ordering.py`)
- PlaybackState validated in `MediaKeysBackend.set_playback_state()` (raises ValueError if invalid)
- Settings queries return defaults (e.g., accent_color defaults to `ACCENT_COLOR_DEFAULT`)

**Authentication:**
- YouTube: yt-dlp uses cookies.txt if present (`cookie_utils.py`)
- Twitch: streamlink uses auth token from twitch_token_path (`player.py:_play_twitch()`)
- Both are optional; playback falls back to no-auth on missing credentials

---

*Architecture analysis: 2026-04-28*
