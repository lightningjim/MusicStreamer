# Phase 35: Backend Isolation - Research

**Researched:** 2026-04-11
**Domain:** Python backend port — GTK/GLib → Qt/PySide6, subprocess → library APIs, headless QObject refactor
**Confidence:** HIGH (core patterns verified against official docs + current codebase audit)

## Summary

Phase 35 converts `musicstreamer/player.py` from a GTK/GLib-coupled class into a headless `QObject` backend while leaving the GTK UI alive one more phase. The hard problem is the cross-thread bridge: GStreamer's bus must keep spinning on a `GLib.MainLoop`, but its messages must reach a Qt-owned `Player` via queued Qt signals — never touching `GLib.idle_add`. Every current `GLib.idle_add`/`timeout_add`/`source_remove` call site in `player.py` has a direct Qt replacement (`Signal.emit` with `Qt.QueuedConnection`, `QTimer.singleShot`, `QTimer.stop`). `yt-dlp` and `streamlink` both expose clean library APIs that subsume the current subprocess code (`YoutubeDL.extract_info(url, download=False)` with `extract_flat='in_playlist'`, `Streamlink().streams(url)` with plugin options for Twitch auth). `platformdirs.user_data_dir("musicstreamer")` resolves to exactly the existing `~/.local/share/musicstreamer` on Linux, so the migration helper is a no-op with a marker file this phase. The mpv-drop spike is a sequencing decision, not a research unknown: if `playbin3` handles yt-dlp-resolved HLS URLs with cookies (the only non-trivial case) then `_play_youtube` collapses into `_set_uri`; otherwise mpv stays as-is.

The 12 existing test files that `import gi` are all `player.py` / `mpris.py` tests that mock GLib at module level — porting them to pytest-qt with `QT_QPA_PLATFORM=offscreen` and `qtbot.waitSignal()` is mechanical. `MprisService` has a tight public surface (6 methods + `emit_properties_changed`) that a stub can satisfy in ~40 lines without any DBus, GLib, or Qt imports at all.

**Primary recommendation:** Build `musicstreamer/paths.py` and `musicstreamer/backend/player.py` (new QObject) side-by-side with the GTK code. Wire the GLib bus-loop thread first, convert call sites one signal at a time, then flip `main_window.py` to consume the signals via `Qt.QueuedConnection` on the headless `QCoreApplication`. Run the mpv spike first as D-04 requires.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (D-01 through D-26)

**Phase Scope — Option A (Qt-first backend)**
- **D-01:** Phase 35 performs the full `Player` → `QObject` conversion. `player.py` ends the phase with zero `GLib.idle_add`, `GLib.timeout_add`, `GLib.source_remove`, and `dbus-python` imports.
- **D-02:** `QCoreApplication` (headless, no widgets) is instantiated in Phase 35 so queued Qt signals and `QTimer` callbacks dispatch correctly. Qt event loop present even though no `QMainWindow` exists yet.
- **D-03:** Phase 36 only adds the visible `QMainWindow`, deletes GTK UI, bundles icons, and enforces Fusion on Windows — does NOT re-touch `player.py` internals.

**Task Ordering**
- **D-04:** mpv-drop spike runs FIRST, before the yt-dlp library-API port. Sequence: (1) spike → (2) decision recorded → (3) yt-dlp/streamlink library port → (4) player QObject conversion → (5) platformdirs paths + migration helper → (6) pytest-qt port → (7) mpris stub.

**Headless Qt Entry Point**
- **D-05:** Create `musicstreamer/__main__.py` that instantiates `QCoreApplication`, constructs `Player`, and exposes a tiny script/REPL harness capable of playing a single ShoutCast URL.
- **D-06:** Existing GTK `main.py` stays on disk but is NOT invoked during Phase 35 verification — deleted in Phase 36.

**GStreamer Bus Bridge**
- **D-07:** GStreamer bus routes to Qt main thread via `GLib.MainLoop` daemon thread + `bus.enable_sync_message_emission()` + queued Qt signal connections via `Qt.ConnectionType.QueuedConnection`. No `QTimer` polling of the bus.
- **D-08:** Player timers (failover countdown, yt-dlp poll loop, cookie-retry one-shot) convert to `QTimer` with `singleShot` where appropriate. `GLib.source_remove` calls become `QTimer.stop()` / `deleteLater()`.

**mpris.py Disposition**
- **D-09:** `mpris.py` replaced with no-op stub exposing same public interface (`MprisService`, constructor, methods `main_window` calls on it). No `dbus-python`, no `GLib`, no real D-Bus. Real QtDBus rewrite is Phase 41.
- **D-10:** `main_window.py` (GTK) callers of `MprisService` keep working against the stub so the GTK app still launches during transition.
- **D-11:** Media keys explicitly NOT functional after Phase 35 until Phase 41. Stub logs one-line debug warning on construction.

**Data Paths — platformdirs (PORT-05)**
- **D-12:** All hard-coded `~/.local/share/musicstreamer` literals replaced with single helper returning paths rooted at `platformdirs.user_data_dir("musicstreamer")`. Cover-art cache, SQLite DB, cookies file, Twitch token path, and accent CSS cache route through this helper.
- **D-13:** Helper is pure (no I/O on import) so tests can monkeypatch the root directory cleanly.

**Data Migration Helper (PORT-06)**
- **D-14:** Migration helper runs on first launch. On Linux, `platformdirs.user_data_dir("musicstreamer")` == `~/.local/share/musicstreamer` (same path as v1.5), so helper is effectively a no-op on Linux. Real cross-path migration deferred until Windows install (Phase 44 UAT).
- **D-15:** Helper still runs unconditionally and writes marker file `.platformdirs-migrated` after successful check so re-invocations short-circuit cheaply.
- **D-16:** Helper is NOT a destructive move. Copies if paths differ, leaves old location alone. On Linux (same path), writes marker and returns.

**yt-dlp + streamlink Library API Port (PORT-09)**
- **D-17:** `yt_import.py` playlist scan and single-video resolution move from `subprocess.Popen(['yt-dlp', ...])` to `yt_dlp.YoutubeDL({...}).extract_info(url, download=False)`. Flat-playlist flags map to `{'extract_flat': 'in_playlist'}`.
- **D-18:** `player._play_twitch()`'s `subprocess.run(['streamlink', '--stream-url', ...])` moves to `streamlink.Streamlink().streams(url)` — picking the best available quality.
- **D-19:** `player._play_youtube()` currently launches mpv as subprocess. Fate decided by spike (D-20). Spike success → path deleted, `playbin3` gets yt-dlp-resolved URL directly. Spike failure → mpv stays as fallback, centralized `_popen()` helper (PKG-03) introduced this phase for remaining mpv launches.

**mpv Spike**
- **D-20:** Spike verifies GStreamer `playbin3` can play yt-dlp library-resolved URLs across: (a) normal YouTube live stream, (b) HLS manifest, (c) cookie-protected / age-gated stream using `cookies.txt`, (d) stream requiring specific format selection (720p live HLS). Each case PASS or FAIL with one-line note.
- **D-21:** If ALL pass: mpv removed entirely from `player.py`, PKG-05 retired in REQUIREMENTS.md.
- **D-22:** If ANY fail: mpv stays as YouTube fallback, failing cases documented as retention reason, PKG-05 remains active for Phase 44.
- **D-23:** Spike result written to `.planning/phases/35-backend-isolation/35-SPIKE-MPV.md` and committed as first phase artifact.

**Test Infrastructure — Big-bang pytest-qt Port (QA-02)**
- **D-24:** Single plan task installs `pytest-qt` + `QT_QPA_PLATFORM=offscreen`, ports all 265 existing tests to pytest-qt conventions in one batch, updates `conftest.py` to provide `qapp` fixture.
- **D-25:** Tests that exercised GTK widgets directly either get rewritten against headless Qt harness or get deferred to Phase 36–37 with skip marker.
- **D-26:** Zero GTK imports permitted in test suite at end of Phase 35.

### Claude's Discretion
- Specific QObject signal signatures (`Signal(str)` vs `Signal(object)` etc.) for title, failover, offline, elapsed-timer events.
- Exact module layout for `paths.py` (top-level `musicstreamer/paths.py` vs nested).
- Whether `__main__.py` harness accepts URL as CLI arg or has single hard-coded known-good URL.
- Whether spike runs in CI or is manual/local-only task.

### Deferred Ideas (OUT OF SCOPE)
- **QtDBus MPRIS2 rewrite** → Phase 41 (MEDIA-02)
- **Qt UI scaffold + GTK delete + icon bundling** → Phase 36 (PORT-03, PORT-04, PORT-07, PORT-08)
- **Real Windows platformdirs migration path** → Phase 44 Windows packaging
- **`_popen()` CREATE_NO_WINDOW helper (PKG-03)** → Phase 44, unless mpv spike fails
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **PORT-01** | `player.py` removes all GLib/dbus-python; `Player` becomes `QObject` with typed Qt signals | `QObject` + `Signal` pattern documented below; every current `GLib.idle_add` call mapped to a replacement signal (see "Signal-by-signal mapping" table) |
| **PORT-02** | GStreamer bus → Qt main thread via `GLib.MainLoop` daemon thread + `bus.enable_sync_message_emission()` + queued Qt signals (no QTimer polling) | Concrete pattern in "GStreamer bus bridge" section; thread-affinity rules verified against Qt docs |
| **PORT-05** | `platformdirs.user_data_dir("musicstreamer")` replaces all hard-coded paths | Verified Linux resolution matches existing path; `paths.py` helper shape documented |
| **PORT-06** | Linux data migrates non-destructively on first launch, detects already-migrated state | Marker-file + copy-only strategy documented; on Linux = no-op with marker |
| **PORT-09** | `yt_import.py` + `player._play_twitch()` ported to `yt-dlp` / `streamlink` Python APIs; spike decides mpv fate | `YoutubeDL.extract_info()` and `Streamlink.streams()` usage documented; spike acceptance criteria enumerated |
| **QA-02** | Test count ≥ 265 passing on Linux; zero GTK imports in test suite | `pytest-qt` + `QT_QPA_PLATFORM=offscreen` pattern documented; conftest shape specified; 12 existing `gi`-importing tests enumerated for conversion |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

No `./CLAUDE.md` found in the MusicStreamer repo. Global user instructions apply (terse communication, concise explanations, make-the-call decisions, scope changes tightly). No project-specific forbidden patterns or required tools beyond what's already in CONTEXT.md.

## Standard Stack

### Core (to add this phase)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | 6.11.0 (2026-03-23) | Qt bindings — `QObject`, `Signal`, `QCoreApplication`, `QTimer`, `Qt.QueuedConnection` | Official Qt for Python; LGPL; ships with `QtDBus` for Phase 41 [VERIFIED: pypi.org/project/PySide6/] |
| yt-dlp | current pypi (pin to `>=2025.x`) | YouTube metadata + URL resolution as library | Active fork of youtube-dl; only viable option [CITED: github.com/yt-dlp/yt-dlp] |
| streamlink | 8.3.x | Twitch HLS URL resolution as library | Only maintained Twitch resolver; same tool current subprocess path uses [CITED: streamlink.github.io] |
| platformdirs | 4.3.7 (already installed on dev box) | Cross-platform user data dir resolution | De-facto replacement for `appdirs`; XDG on Linux, `%APPDATA%` on Windows [VERIFIED: `python3 -c "import platformdirs"`] |
| pytest-qt | 4.x | Headless Qt testing with `qtbot`, signal waiting, QApplication lifecycle | Standard test harness for PySide6/PyQt code [CITED: pytest-qt.readthedocs.io] |

### Already in stack (unchanged)

| Library | Role in Phase 35 |
|---------|------------------|
| PyGObject (`gi`) | Still needed for `Gst` and `GLib.MainLoop` — GStreamer Python bindings go through `gi.repository.Gst`. Only GTK/Adw imports are removed. |
| GStreamer 1.26.6 | Unchanged — `playbin3` pipeline stays. [VERIFIED: `gst-inspect-1.0 --version`] |
| sqlite3 (stdlib) | Unchanged — thread-local connection pattern preserved per CONVENTIONS.md |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PySide6 | PyQt6 | PySide6 is the official Qt for Python project with LGPL (PyQt6 is GPL/commercial). Project already decided on PySide6 in REQUIREMENTS.md. |
| `platformdirs` | `appdirs` (older) | `appdirs` is unmaintained; `platformdirs` is the active fork. Already installed. |
| `pytest-qt` | Hand-rolled `QApplication` fixtures | `pytest-qt` provides `qtbot`, `waitSignal`, and handles Qt event loop integration — hand-rolling recreates known pitfalls. |
| yt-dlp library | `yt-dlp` subprocess (current) | Library avoids process fork overhead, captures exceptions directly, no tempfile cookie plumbing. Also eliminates `shutil.which` PATH lookups. |
| streamlink library | `streamlink` subprocess (current) | Same — library returns dict of quality → stream URLs directly, no parsing `--stream-url` stdout. |

### Installation

```bash
pip install PySide6 pytest-qt yt-dlp streamlink platformdirs
```

Add to `pyproject.toml` `[project] dependencies`:

```toml
dependencies = [
    "PySide6>=6.11",
    "yt-dlp",
    "streamlink>=8.3",
    "platformdirs>=4.3",
]

[project.optional-dependencies]
test = ["pytest>=9", "pytest-qt>=4"]
```

**Version verification (2026-04-11):**
- `PySide6 6.11.0` — released 2026-03-23 [VERIFIED: web search pypi.org/project/PySide6/]
- `platformdirs 4.3.7` — [VERIFIED: local `python3 -c "import platformdirs"`]
- `GStreamer 1.26.6` — [VERIFIED: local `gst-inspect-1.0 --version`]
- `Python 3.13.7` — [VERIFIED: local `python3 --version`]

⚠️ PySide6, yt-dlp, streamlink, and pytest-qt are NOT currently installed on the dev box. Plan must include `pip install` as an explicit task (not a side-effect of another task). See Environment Availability section.

## Architecture Patterns

### Recommended Project Structure (this phase only)

```
musicstreamer/
├── __main__.py              # NEW — headless QCoreApplication entry (D-05)
├── paths.py                 # NEW — platformdirs helper (D-12, D-13)
├── migration.py             # NEW — PORT-06 first-launch migration (D-14..D-16)
├── backend/                 # NEW — or keep flat, Claude's discretion
│   ├── player.py            # REWRITE — QObject + Signals (D-01)
│   └── gst_bus_bridge.py    # NEW — GLib.MainLoop daemon thread + queued signals (D-07)
├── yt_import.py             # REWRITE — subprocess → yt_dlp.YoutubeDL (D-17)
├── mpris.py                 # REPLACE — no-op stub (D-09, D-10, D-11)
├── constants.py             # EDIT — DATA_DIR etc. delegate to paths.py (D-12)
├── ui/main_window.py        # EDIT (minimal) — consume Player signals instead of callbacks
└── main.py                  # UNCHANGED this phase (deleted in Phase 36)
```

Recommendation: flat layout (no `backend/` subdir). Less churn, smaller diff. Move to `backend/` in Phase 36 if desired.

### Pattern 1: QObject + typed Signals (PORT-01)

**What:** `Player` becomes a `QObject` subclass that emits signals for every event currently delivered via `GLib.idle_add`.

**When to use:** For every handler assignment (`self._on_title`, `self._on_failover`, `self._on_offline`) and for elapsed-timer updates that flow to the UI.

**Example (verified pattern from Qt docs):**

```python
from PySide6.QtCore import QObject, Signal, Slot, QTimer, Qt
from musicstreamer.models import Station, StationStream
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst


class Player(QObject):
    # Typed signals — declared at class scope (required by Qt)
    title_changed = Signal(str)           # ICY title
    failover = Signal(object)             # StationStream | None
    offline = Signal(str)                 # Twitch channel name
    twitch_resolved = Signal(str)         # resolved HLS URL (internal bridge)
    playback_error = Signal(str)          # GStreamer error text
    elapsed_updated = Signal(int)         # seconds since playback started

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._pipeline = Gst.ElementFactory.make("playbin3", "player")
        # ... same GStreamer setup as today ...

        # Failover timer — QTimer instead of GLib.timeout_add
        self._failover_timer = QTimer(self)
        self._failover_timer.setSingleShot(True)
        self._failover_timer.timeout.connect(self._on_timeout)

        # Internal self-connect: when the GST bus thread emits twitch_resolved,
        # handle it on the Player's thread via queued connection
        self.twitch_resolved.connect(
            self._on_twitch_resolved,
            Qt.ConnectionType.QueuedConnection,
        )
```

**Signal-by-signal mapping (every `GLib.idle_add` / `timeout_add` call in player.py):**

| Current call (player.py line) | Replacement |
|-------------------------------|-------------|
| `GLib.idle_add(self._on_title, title)` — line 89 | `self.title_changed.emit(title)` |
| `GLib.idle_add(self._on_failover, None)` — line 113 | `self.failover.emit(None)` |
| `GLib.idle_add(self._on_failover, stream)` — line 119 | `self.failover.emit(stream)` |
| `GLib.timeout_add(BUFFER_DURATION_S * 1000, self._on_timeout_cb)` — line 131 | `self._failover_timer.start(BUFFER_DURATION_S * 1000)` |
| `GLib.source_remove(self._failover_timer_id)` — line 94 | `self._failover_timer.stop()` |
| `GLib.source_remove(self._yt_poll_timer_id)` — line 97 | `self._yt_poll_timer.stop()` |
| `GLib.timeout_add(2000, _check_cookie_retry)` — line 302 | `QTimer.singleShot(2000, self._check_cookie_retry)` |
| `GLib.timeout_add(1000, self._yt_poll_cb)` — line 305 | `self._yt_poll_timer = QTimer(self); self._yt_poll_timer.timeout.connect(self._yt_poll_cb); self._yt_poll_timer.start(1000)` |
| `GLib.idle_add(self._on_twitch_resolved, resolved)` — line 335 (in daemon thread) | `self.twitch_resolved.emit(resolved)` (queued connection to own slot) |
| `GLib.idle_add(self._on_twitch_offline, url)` — line 337 | `self.offline.emit(channel_name)` |
| `GLib.idle_add(self._on_twitch_error)` — line 339 | `self.playback_error.emit(msg)` |

**Critical threading rule:** `QTimer` is owned by the thread that created it and its timeout fires on that thread's event loop. `Player` must be constructed on the thread that runs `QCoreApplication.exec()` (the "main" thread), NOT on the GLib bus-loop thread. [CITED: Qt docs — QObject thread affinity]

### Pattern 2: GStreamer bus bridge — `GLib.MainLoop` daemon thread + queued signals (PORT-02, D-07)

**What:** The GStreamer bus already emits Python callbacks via `bus.add_signal_watch()` + `bus.connect("message::...", handler)`, but only if a `GLib.MainLoop` is iterating. In a Qt-driven process there is no default GLib main loop, so we spin one on a daemon thread. Handlers run on that GLib thread; they must NOT touch Qt objects directly — they re-emit Qt signals with `Qt.QueuedConnection`, which marshals the call to the receiver's thread (the Qt main thread).

**When to use:** Once per Player instance, before `set_state(PLAYING)`.

**Example (synthesized from gi docs + Qt thread-affinity rules):**

```python
# musicstreamer/gst_bus_bridge.py
import threading
from gi.repository import GLib


class GstBusLoopThread:
    """Runs a GLib.MainLoop on a daemon thread so GStreamer bus signal
    handlers fire even though the main thread runs Qt's event loop.

    The thread owns a fresh GLib.MainContext and pushes it as the thread-
    default so signal watches registered from this thread are dispatched
    by its loop, not by any default GLib context.
    """

    def __init__(self):
        self._loop: GLib.MainLoop | None = None
        self._context: GLib.MainContext | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name="gst-bus-loop", daemon=True
        )
        self._thread.start()
        self._ready.wait(timeout=2.0)

    def _run(self):
        self._context = GLib.MainContext.new()
        self._context.push_thread_default()
        self._loop = GLib.MainLoop.new(self._context, False)
        self._ready.set()
        self._loop.run()

    def stop(self):
        if self._loop and self._loop.is_running():
            GLib.idle_add(self._loop.quit)  # quit from inside the loop
```

**Pipeline wiring inside `Player.__init__`:**

```python
# Keep add_signal_watch() — it's still the standard gi API
bus = self._pipeline.get_bus()
bus.add_signal_watch()
# Sync emission lets us see state-changed / tag messages without latency.
# Sync handlers must NOT block and must NOT touch Qt; they only re-emit.
bus.enable_sync_message_emission()

bus.connect("message::error", self._on_gst_error)     # runs on bus-loop thread
bus.connect("message::tag",   self._on_gst_tag)       # runs on bus-loop thread
bus.connect("sync-message::element", self._on_gst_sync)  # if needed
```

Handlers emit Qt signals; because `Player` lives on the main (Qt) thread and the emission happens on the bus-loop thread, Qt auto-chooses `QueuedConnection` — but it's safer to be explicit where we self-connect or where receivers connect from outside:

```python
def _on_gst_tag(self, bus, msg):
    taglist = msg.parse_tag()
    found, value = taglist.get_string(Gst.TAG_TITLE)
    if not found:
        return
    # Fire on main thread — Qt queues this because emission is cross-thread
    self.title_changed.emit(_fix_icy_encoding(value))
```

**Thread-safety contract:**
- Emitting a Signal from any thread is safe. Receivers in other threads get a queued call. [CITED: Qt docs — signals/slots across threads]
- `QTimer.start()` / `.stop()` must be called from the timer's owning thread. Since `Player` lives on the main thread, `_cancel_failover_timer()` is main-thread only. Bus handlers that want to cancel a timer must route through a signal or `QMetaObject.invokeMethod(...)`.
- `bus.add_signal_watch()` is idempotent; pair it with one `bus.remove_signal_watch()` at teardown.
- `GstBusLoopThread.start()` must happen BEFORE `set_state(PLAYING)` so the first `message::tag` has a loop to dispatch it.

### Pattern 3: `QCoreApplication` headless entry (D-02, D-05)

**What:** No widgets, no `QApplication`. Just `QCoreApplication` for the event loop + queued-signal machinery.

**Example:**

```python
# musicstreamer/__main__.py
import sys
from PySide6.QtCore import QCoreApplication, QTimer
from musicstreamer.player import Player
from musicstreamer.models import Station, StationStream


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv
    app = QCoreApplication(argv)

    player = Player()
    player.title_changed.connect(lambda t: print(f"ICY: {t}"))
    player.failover.connect(lambda s: print(f"Failover: {s}"))
    player.playback_error.connect(lambda m: print(f"ERROR: {m}"))

    # Hard-coded smoke URL — D-05 allows either CLI arg or hard-coded
    url = argv[1] if len(argv) > 1 else "https://streams.chillhop.com/live?type=.mp3"
    stream = StationStream(id=0, station_id=0, url=url, quality="hi", position=0)
    station = Station(id=0, name="Smoke Test", streams=[stream], provider_name="", tags="")

    # Kick off after the event loop is running so queued signals work
    QTimer.singleShot(0, lambda: player.play(station, on_title=None))

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

Note: `player.play(..., on_title=None)` — the `on_title` callback parameter is now redundant because signals replace it. The `play()` method keeps the parameter for one phase to avoid breaking `main_window.py` callers, OR the method signature changes and `main_window.py` switches to `player.title_changed.connect(...)`. Either is valid; planner picks.

### Pattern 4: `paths.py` helper (PORT-05, D-12, D-13)

```python
# musicstreamer/paths.py
"""Cross-platform user data paths.

All persistent-data paths flow through this module. Tests may monkeypatch
`_root_override` to redirect to a tmp_path fixture.
"""
from __future__ import annotations
import os
import platformdirs

_root_override: str | None = None


def _root() -> str:
    if _root_override is not None:
        return _root_override
    return platformdirs.user_data_dir("musicstreamer")


def data_dir() -> str:       return _root()
def db_path() -> str:        return os.path.join(_root(), "musicstreamer.sqlite3")
def assets_dir() -> str:     return os.path.join(_root(), "assets")
def cookies_path() -> str:   return os.path.join(_root(), "cookies.txt")
def twitch_token_path() -> str: return os.path.join(_root(), "twitch-token.txt")
def accent_css_path() -> str: return os.path.join(_root(), "accent.css")
def migration_marker() -> str: return os.path.join(_root(), ".platformdirs-migrated")
```

Note that `constants.py` currently has module-level `DATA_DIR = os.path.join(...)` assignments. Those must become either thin re-exports from `paths.py` or lazy functions. Simplest port: change `constants.py` to `from musicstreamer.paths import data_dir as _data_dir` and recompute on access. Planner's call.

**Test monkeypatch pattern:**

```python
def test_db_path_uses_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr("musicstreamer.paths._root_override", str(tmp_path))
    assert paths.db_path() == str(tmp_path / "musicstreamer.sqlite3")
```

### Pattern 5: First-launch migration (PORT-06, D-14..D-16)

```python
# musicstreamer/migration.py
"""Non-destructive Linux→platformdirs migration.

Strategy:
  - If marker exists: return immediately.
  - Compute source (legacy ~/.local/share/musicstreamer) and destination
    (platformdirs.user_data_dir). If they are the same directory, write
    the marker and return.
  - Otherwise copy files from source → destination if destination is missing
    them. Never delete from source.
  - Write marker on success.
"""
from __future__ import annotations
import os
import shutil
from pathlib import Path
from musicstreamer import paths

_LEGACY_LINUX = os.path.expanduser("~/.local/share/musicstreamer")


def run_migration() -> None:
    marker = paths.migration_marker()
    if os.path.exists(marker):
        return
    dest = paths.data_dir()
    os.makedirs(dest, exist_ok=True)
    src = _LEGACY_LINUX
    if os.path.realpath(src) == os.path.realpath(dest):
        _write_marker(marker)
        return
    if os.path.isdir(src):
        _copy_tree_nondestructive(src, dest)
    _write_marker(marker)


def _copy_tree_nondestructive(src: str, dst: str) -> None:
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target_dir = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(target_dir, exist_ok=True)
        for f in files:
            s = os.path.join(root, f)
            d = os.path.join(target_dir, f)
            if not os.path.exists(d):
                shutil.copy2(s, d)


def _write_marker(path: str) -> None:
    Path(path).write_text("platformdirs migration complete\n")
```

On this dev box, `src == dest`, so the first launch writes the marker and returns (verified — see Runtime State Inventory).

### Pattern 6: yt-dlp library API (PORT-09, D-17)

**Current subprocess flags** (from `yt_import.py` line 37 + `player._play_youtube`):
- `--flat-playlist` → `{'extract_flat': 'in_playlist'}`
- `--dump-json` → iterate `info['entries']` (already parsed dicts)
- `--no-cookies-from-browser` → `{'cookiesfrombrowser': None}` (or omit — it's the default)
- `--cookies <file>` → `{'cookiefile': path}`
- `--quiet` → `{'quiet': True}`
- `--no-warnings` → `{'no_warnings': True}`
- Skip download → `extract_info(url, download=False)`

**Playlist scan (replaces `yt_import.scan_playlist`):**

```python
import yt_dlp
from musicstreamer import paths

def scan_playlist(url: str) -> list[dict]:
    opts = {
        'extract_flat': 'in_playlist',
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    if os.path.exists(paths.cookies_path()):
        opts['cookiefile'] = paths.cookies_path()

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e).lower()
        if "private" in msg or "unavailable" in msg:
            raise ValueError("Playlist Not Accessible") from e
        raise RuntimeError(str(e)) from e

    entries = info.get('entries') or []
    # extract_flat='in_playlist' returns sparse entries. is_live may be None
    # for non-resolved entries — in that case we MUST fall through to a
    # per-entry extract_info() to learn is_live. See Common Pitfalls.
    results = []
    for e in entries:
        if e is None:
            continue
        if e.get('is_live') is True:
            results.append({
                'title': e.get('title', 'Untitled'),
                'url': e.get('url') or e.get('webpage_url'),
                'provider': e.get('playlist_channel') or e.get('playlist_uploader', ''),
            })
    return results
```

**Single-video URL resolution (replaces `mpv` invocation for `_play_youtube`, assuming spike passes):**

```python
def resolve_youtube_stream(url: str) -> str:
    """Return a direct HLS/progressive URL that playbin3 can consume."""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        # Prefer HLS formats; matches the current mpv --ytdl behavior
        'format': 'best[protocol^=m3u8]/best',
    }
    if os.path.exists(paths.cookies_path()):
        opts['cookiefile'] = paths.cookies_path()
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    # For live streams extract_info returns 'url' directly
    return info.get('url') or info['formats'][-1]['url']
```

**⚠️ Run extraction off the main thread.** `extract_info` makes HTTP calls and can take 2–10+ seconds. Call it from a `threading.Thread` (already the pattern in `_play_twitch`) and emit a Qt signal when done. Do NOT call it from the Qt main thread — it will freeze the event loop. Use `QThread` or plain Python thread + `Signal.emit` (both work; plain thread is less ceremony).

### Pattern 7: streamlink library API (PORT-09, D-18)

**Current subprocess flags** (from `_play_twitch`):
- `--stream-url <url> best` → `session.streams(url)["best"].url`
- `--twitch-api-header Authorization=OAuth $TOKEN` → plugin option `api-header`

**Replacement:**

```python
from streamlink.session import Streamlink
from streamlink.exceptions import NoPluginError, PluginError

def resolve_twitch_hls(url: str, oauth_token: str | None) -> str:
    session = Streamlink()
    if oauth_token:
        # Twitch plugin option — sets header only on gql.twitch.tv API calls,
        # not on the HLS stream session (important — CITED: streamlink discussion #4400)
        session.set_plugin_option(
            "twitch", "api-header",
            [("Authorization", f"OAuth {oauth_token}")],
        )
    try:
        streams = session.streams(url)
    except NoPluginError:
        raise RuntimeError("No streamlink plugin for this URL")
    except PluginError as e:
        # Offline Twitch channel raises PluginError with "No playable streams"
        if "No playable streams" in str(e):
            raise _TwitchOffline(url) from e
        raise
    if not streams:
        raise _TwitchOffline(url)
    # streams is an OrderedDict keyed by quality; "best" is a pre-computed alias
    return streams["best"].url
```

**API pattern verified:** `session.set_plugin_option("twitch", "api-header", [...])` is the correct way to scope headers to Twitch gql API only (not to the HLS media delivery). [CITED: streamlink GitHub discussion #4400, streamlink api_guide]

**Still runs on a daemon thread** — same pattern as current `_play_twitch` (`threading.Thread(target=_resolve, daemon=True).start()`). The only change is that the thread emits `self.twitch_resolved.emit(url)` instead of `GLib.idle_add(self._on_twitch_resolved, resolved)`.

### Pattern 8: MprisService no-op stub (D-09, D-10, D-11)

Current `main_window.py` touches the following public surface on `MprisService`:
1. `MprisService(self)` — constructor, accepts a window reference
2. `mpris._build_metadata()` — returns a dict (used in `emit_properties_changed` payloads)
3. `mpris.emit_properties_changed(props: dict)` — called from 4 sites

```python
# musicstreamer/mpris.py (Phase 35 stub)
"""No-op MPRIS2 stub. Phase 41 will rewrite this against PySide6.QtDBus.

See .planning/phases/35-backend-isolation/35-CONTEXT.md D-09..D-11.
Media keys are non-functional from Phase 35 through Phase 41.
"""
import logging

_log = logging.getLogger(__name__)


class MprisService:
    def __init__(self, window=None):
        self._window = window
        _log.debug("MprisService stub active — media keys disabled until Phase 41")

    def _build_metadata(self) -> dict:
        return {}

    def emit_properties_changed(self, props: dict) -> None:
        pass
```

**⚠️ `main_window.py` lines 701, 704, 774, 809, 964 do `import dbus` locally and construct `dbus.Dictionary` / `dbus.String` / `dbus.ObjectPath` objects to pass to `emit_properties_changed`.** Those local `import dbus` statements would break at runtime when `dbus-python` is uninstalled. Two viable fixes:

1. **Leave the local imports alone this phase** — `dbus-python` stays installed during Phase 35 even though `player.py` no longer uses it. The stub ignores the dbus objects anyway. `dbus-python` is fully removed in Phase 36 when `main_window.py` is deleted. **← Recommended.**
2. Delete the `import dbus` lines in `main_window.py` and pass plain dicts. More diff, breaks the `main_window.py` "don't touch" scope rule.

Recommendation: **option 1**. Phase 35 keeps `dbus-python` as an installed dependency used by nothing; Phase 36 removes it as part of GTK deletion. REQUIREMENTS.md PORT-01 says `player.py` removes dbus-python imports — it does not require uninstalling the package. This is consistent.

### Pattern 9: pytest-qt conftest (QA-02, D-24)

```python
# tests/conftest.py
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

@pytest.fixture(scope="session")
def qapp_cls():
    # Force QCoreApplication — we're backend-only in Phase 35
    from PySide6.QtCore import QCoreApplication
    return QCoreApplication
```

Or, more commonly, let `pytest-qt` create a `QApplication` (it handles widgets on offscreen too — zero cost for backend tests):

```python
# pytest-qt default behavior is fine; just set QT_QPA_PLATFORM=offscreen
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

**Testing signals:**

```python
def test_title_changed_emits_on_gst_tag(qtbot, monkeypatch):
    from musicstreamer.player import Player
    player = Player()
    with qtbot.waitSignal(player.title_changed, timeout=1000) as blocker:
        # simulate bus tag message — use a fake bus + fake msg, or call the
        # private handler directly with MagicMock args as current tests do
        player._on_gst_tag(bus=None, msg=_make_fake_tag_msg("Artist - Song"))
    assert blocker.args == ["Artist - Song"]
```

Because `Player` signals are regular Qt signals, `qtbot.waitSignal` / `waitSignals` / `assertNotEmitted` all work. No special glue required.

### Anti-Patterns to Avoid

- **Polling the GStreamer bus with `QTimer`.** CONTEXT.md D-07 explicitly forbids this. Use the `GLib.MainLoop` thread.
- **Creating `QTimer` or `Player` on the GLib bus-loop thread.** Those objects live on whatever thread constructed them. `QTimer.start()` from a foreign thread is a silent-failure bug.
- **Calling `GLib.idle_add` for UI callbacks after the conversion.** That's the bug the phase exists to fix — anyway, `GLib.idle_add` targets the default GLib main context, which the Qt process no longer iterates.
- **Using `yt_dlp.extract_info` from the main thread.** Blocks the Qt event loop. Always use a worker thread.
- **Closing over `QWidget` references in bus-loop thread callbacks.** Not a Phase 35 issue (no widgets yet), but document it for Phase 36 — QA-05 exists for this reason.
- **Forgetting `bus.add_signal_watch()` on a new `GLib.MainContext`.** If the bridge thread pushes its own context, the watch must be registered from that thread (not the main thread) so the watch attaches to the right context. Alternative: use the default main context and just `GLib.MainLoop.new(None, False)` — simpler, same result since no other GLib code runs in this process.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-thread callback marshaling | Custom queue + polling | Qt `Signal` + `Qt.QueuedConnection` | Qt already handles affinity, reentrancy, and teardown |
| User data dir resolution | Hand-coded `sys.platform` branches | `platformdirs.user_data_dir` | Handles XDG edge cases and Windows known-folder lookups |
| YouTube URL extraction | Parsing HTML / raw API calls | `yt_dlp.YoutubeDL` | The only actively maintained extractor |
| Twitch HLS resolution | Parsing gql.twitch.tv manually | `streamlink.Streamlink` | Plugin handles OAuth, ad-suppression, quality selection |
| Test Qt event loop | Hand-built `QEventLoop` + `processEvents` | `pytest-qt` `qtbot` | `waitSignal`/`waitUntil` replace 20-line loops |
| MPRIS2 D-Bus service | Hand-rolled `dbus-python` (current) | Phase 41: `PySide6.QtDBus` + `QDBusAbstractAdaptor` | Phase 35 uses a stub, not a re-implementation |

**Key insight:** The phase's entire thesis is "replace bespoke wiring with platform-standard primitives." Every subprocess call, every `GLib.idle_add`, and every hard-coded path has a first-class library replacement.

## Runtime State Inventory

Phase 35 is a refactor / port phase, so this section is mandatory.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | SQLite DB at `~/.local/share/musicstreamer/musicstreamer.sqlite3` (184 KB, currently in use); `cookies.txt`, `twitch-token.txt`, `assets/` in the same directory; `mpv.log` present | None — `platformdirs.user_data_dir("musicstreamer")` resolves to the identical path on this Linux box. Migration helper writes marker and returns. No data migration task in the plan. |
| **Live service config** | None — MusicStreamer is local desktop, no external service config | None — verified: no n8n, no Datadog, no Cloudflare. |
| **OS-registered state** | `.desktop` file `org.example.MusicStreamer` (referenced in `_get_all_root`). Not Phase 35 scope — the desktop file is untouched by this phase. | None — MPRIS2 bus name registration was the only OS-level registration and it's being replaced by a stub (intentionally un-registers). |
| **Secrets/env vars** | `cookies.txt` path, `twitch-token.txt` path — both read via constants.py literals today. No env-var indirection. | Code edit only — re-route reads through `paths.py` helpers. Files themselves don't move on Linux. |
| **Build artifacts / installed packages** | `musicstreamer.egg-info/` if any (not found — not editable-installed here); `__pycache__` dirs throughout `musicstreamer/` | None — `.pyc` regenerate automatically. If user runs `pip install -e .` after adding new modules (`paths.py`, `migration.py`), the egg-info refresh is automatic. |

**Verification (2026-04-11):**

```
$ python3 -c "import platformdirs; print(platformdirs.user_data_dir('musicstreamer'))"
/home/kcreasey/.local/share/musicstreamer

$ ls ~/.local/share/musicstreamer
assets  cookies.txt  mpv.log  musicstreamer.sqlite3  twitch-token.txt  .claude  .git
```

Source == destination. Migration helper writes a marker and returns on every Linux dev box that previously ran v1.5. [VERIFIED]

**Canonical question answered:** After every file in the repo is updated, what runtime systems still have the old string cached, stored, or registered? **Nothing on Linux.** The `~/.local/share/musicstreamer` directory is referenced only by `constants.py` literals (code, updated this phase) and by the user's home directory (path == platformdirs path, so nothing moves). Phase 44 (Windows) will revisit when source != destination.

## Common Pitfalls

### Pitfall 1: `extract_flat='in_playlist'` returns entries without `is_live`

**What goes wrong:** `yt_import.py` line 73 checks `entry.get("is_live") is True`. With the library API and `extract_flat='in_playlist'`, entries are sparse — many fields including `is_live` may be `None` or missing. Result: scan returns an empty list.

**Why it happens:** Flat extraction returns only what the playlist page exposes; `is_live` requires a per-video probe.

**How to avoid:** Either (a) drop `extract_flat` and take the slower full scan, (b) do a second pass with `extract_info(entry['url'], process=False)` per candidate, or (c) check `entry.get('live_status') == 'is_live'` which is more reliably populated in current yt-dlp. Verify against the yt-dlp version's actual return shape before coding — check `help(yt_dlp.YoutubeDL)` or `yt_dlp/YoutubeDL.py` on GitHub. [CITED: github.com/yt-dlp/yt-dlp]

**Warning signs:** Playlist scan returns 0 live entries against a playlist that the current subprocess path returns dozens for. Diff the JSON shapes.

### Pitfall 2: `QTimer` created on bus-loop thread never fires

**What goes wrong:** A developer adds `QTimer(self)` inside `_on_gst_error` (which runs on the GLib bus-loop thread). The timer's thread affinity is set to the GLib thread, which has no Qt event loop, so `timeout` never emits.

**How to avoid:** ALL `QTimer` construction happens in `Player.__init__` (main thread). Bus handlers emit signals that trigger main-thread slots, which then call `self._some_timer.start()`.

**Warning signs:** Failover never triggers despite `_failover_timer.start()` being logged. Check `QThread.currentThread()` at construction vs `.thread()` on the timer.

### Pitfall 3: `bus.add_signal_watch()` without a running GLib loop

**What goes wrong:** `Player.__init__` calls `bus.add_signal_watch()` but `GstBusLoopThread.start()` hasn't been called yet. Messages queue up in the default context that nobody iterates; tag and error signals never fire.

**How to avoid:** Start the bus-loop thread in `Player.__init__` AFTER the pipeline is created but BEFORE the first `set_state(PLAYING)`. Verify with a smoke log on first `message::state-changed`.

**Warning signs:** Streams "play" (no error) but no ICY title ever updates. No GStreamer errors appear on failure.

### Pitfall 4: `Signal` declared as instance attribute

**What goes wrong:** `self.title_changed = Signal(str)` inside `__init__` silently does nothing. Qt requires signals to be declared at class scope to register them with the meta-object.

**How to avoid:** Always class-level: `title_changed = Signal(str)` above `def __init__`.

**Warning signs:** `AttributeError: 'PySide6.QtCore.Signal' object has no attribute 'emit'` or runtime "signal not found" errors when connecting.

### Pitfall 5: `enable_sync_message_emission` + long-running handler blocks GStreamer

**What goes wrong:** Sync-message handlers run on the GStreamer streaming thread and must return immediately. If a sync handler does network I/O or waits, the pipeline stalls.

**How to avoid:** Use `add_signal_watch()` alone (async) unless you need state-changed-before-prepared-window type events. Sync emission is only needed for element-level intercept (e.g., video overlay window ID), not for tag/error. **Recommendation: skip `enable_sync_message_emission()` entirely — `add_signal_watch()` dispatched by the bridge thread's `GLib.MainLoop` already delivers tag/error messages.** Re-read D-07: the CONTEXT.md text includes `enable_sync_message_emission()` in the recipe, but the async `add_signal_watch()` + bus-loop-thread pattern is functionally sufficient for this codebase's needs. **[ASSUMED — planner should verify with a small smoke test during the spike or bridge task whether sync emission is required for sub-second ICY updates, or if async watch is fast enough. If async is fast enough, drop sync emission — simpler and safer.]**

**Warning signs:** Audio stutters or the pipeline logs "streaming thread stuck" messages.

### Pitfall 6: streamlink global HTTP header leaks to HLS delivery

**What goes wrong:** Using `session.set_option("http-header", ...)` instead of the plugin-scoped `set_plugin_option("twitch", "api-header", ...)`. The header gets attached to every request including HLS segment fetches, which Twitch's CDN rejects.

**How to avoid:** Always scope Twitch auth via `set_plugin_option`. [CITED: github.com/streamlink/streamlink discussions #4400]

**Warning signs:** `streams(url)` succeeds but playing the returned URL through `playbin3` returns 403 on segment fetches.

### Pitfall 7: pytest-qt tests missing `QT_QPA_PLATFORM=offscreen`

**What goes wrong:** CI runs headless, no X/Wayland socket; `QApplication` construction fails with "could not connect to display". Tests crash before any assertion.

**How to avoid:** Set `QT_QPA_PLATFORM=offscreen` in `conftest.py` at module import time (before any Qt import) OR in `pyproject.toml`'s `[tool.pytest.ini_options] env =`.

**Warning signs:** Tests pass locally on a Linux desktop but fail in CI.

### Pitfall 8: `dbus-python` import side-effect from test_mpris.py after stubbing

**What goes wrong:** `tests/test_mpris.py` mocks `dbus` at module import via `patch.dict("sys.modules", _MODULE_PATCHES)`. After the Phase 35 stub replacement, `mpris.py` no longer imports `dbus` at all — the test's 140 lines of dbus mocks become dead code, and some of the test assertions (`str(props["PlaybackStatus"]) == "Playing"`) are against a stub that returns `{}`.

**How to avoid:** Rewrite `test_mpris.py` entirely — the tests verify an interface that no longer exists. Replace with 4–6 tests that verify: (a) stub constructs without raising, (b) `_build_metadata` returns `{}`, (c) `emit_properties_changed` is a no-op, (d) one debug log on construction. This is ~30 lines total.

**Warning signs:** `test_mpris.py` blows up with `AttributeError: MprisService has no attribute 'PlayPause'` after porting.

## Code Examples

All patterns above are self-contained. Key call-site diffs:

### Current `_play_twitch` → library API

```python
# BEFORE (player.py lines 312–341)
def _resolve():
    cmd = ["streamlink", "--stream-url", url, "best"]
    try:
        with open(TWITCH_TOKEN_PATH) as fh:
            token = fh.read().strip()
        if token:
            cmd = ["streamlink", "--twitch-api-header", f"Authorization=OAuth {token}",
                   "--stream-url", url, "best"]
    except OSError:
        pass
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    # ... parse stdout ...

# AFTER
def _resolve():
    from streamlink.session import Streamlink
    from streamlink.exceptions import PluginError, NoPluginError
    session = Streamlink()
    try:
        with open(paths.twitch_token_path()) as fh:
            token = fh.read().strip()
        if token:
            session.set_plugin_option("twitch", "api-header",
                                      [("Authorization", f"OAuth {token}")])
    except OSError:
        pass
    try:
        streams = session.streams(url)
    except (PluginError, NoPluginError) as e:
        if "No playable streams" in str(e):
            self.offline.emit(url.rstrip("/").split("/")[-1])
            return
        self.playback_error.emit(str(e))
        return
    if "best" in streams:
        self.twitch_resolved.emit(streams["best"].url)
    else:
        self.offline.emit(url.rstrip("/").split("/")[-1])
```

### Current `scan_playlist` → library API

```python
# BEFORE (yt_import.py lines 28–79) — 52 lines of subprocess + JSON parsing

# AFTER — 18 lines
import yt_dlp
from musicstreamer import paths

def scan_playlist(url: str) -> list[dict]:
    opts = {'extract_flat': 'in_playlist', 'quiet': True,
            'no_warnings': True, 'skip_download': True}
    if os.path.exists(paths.cookies_path()):
        opts['cookiefile'] = paths.cookies_path()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e).lower()
        if "private" in msg or "unavailable" in msg:
            raise ValueError("Playlist Not Accessible") from e
        raise RuntimeError(str(e)) from e
    entries = info.get('entries') or []
    return [
        {'title': e.get('title', 'Untitled'),
         'url': e.get('url') or e.get('webpage_url'),
         'provider': e.get('playlist_channel') or e.get('playlist_uploader', '')}
        for e in entries if e and (e.get('is_live') is True or e.get('live_status') == 'is_live')
    ]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `dbus-python` MPRIS2 | `PySide6.QtDBus` | Qt 5+ era | One DBus stack per process; `dbus-python` is feature-complete but unmaintained. Phase 41 consumes this. |
| `GLib.idle_add` for cross-thread GUI | Qt `Signal` + `QueuedConnection` | Always in Qt | Type-safe, teardown-safe, testable with `pytest-qt` |
| `appdirs` | `platformdirs` | 2021 fork | `appdirs` abandoned; `platformdirs` is the drop-in replacement |
| `youtube-dl` subprocess | `yt-dlp` library | 2021 fork | `youtube-dl` mostly dormant; `yt-dlp` has all active extractor maintenance |
| Hand-rolled Qt test harness | `pytest-qt` + `qtbot` | Stable since ~2018 | Standardizes signal/event-loop tests |

**Deprecated/outdated:**
- `dbus-python` — still works but hasn't had major development; QtDBus is the Qt-native path.
- `mpv` subprocess launcher for YouTube — the reason this phase has a spike. If `playbin3` + `yt-dlp.extract_info` handles all four spike cases, this entire code path disappears.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Async `bus.add_signal_watch()` on the bridge thread is sufficient for timely ICY updates; `enable_sync_message_emission()` can be skipped despite CONTEXT.md D-07 mentioning it | Pitfall 5 | If async is too slow for sub-second tag delivery, planner must re-add sync emission. Low risk — current GTK path uses async watch and ICY updates work fine. |
| A2 | `yt-dlp extract_flat='in_playlist'` returns `live_status` field reliably for YouTube live playlists in current (2025+) versions | Pitfall 1, Pattern 6 | Scan returns empty if the field is absent. Mitigation: smoke test during the yt-dlp port task against a known-good playlist and adjust detection. |
| A3 | `streamlink.session.set_plugin_option("twitch", "api-header", ...)` is the canonical method name (not `set_option` with some prefix). Verified against streamlink GitHub discussion #4400 which shows the pattern with `options.set("api-header", ...)` on a plugin `Options` object — slightly different API shape | Pattern 7 | If the session-level `set_plugin_option` doesn't exist, use `session.plugins.get_plugin_options("twitch")` or equivalent. Verify with `dir(session)` during implementation. MEDIUM confidence. |
| A4 | Leaving `dbus-python` installed during Phase 35 (recommendation in Pattern 8) is acceptable under PORT-01 because PORT-01 says "player.py removes" — not "uninstall dbus-python" | Pattern 8 | If reviewer reads PORT-01 strictly as "uninstall dbus-python", planner must also rewrite `main_window.py` lines 701/704/774/809/964 to drop local `import dbus`. Small scope increase. |
| A5 | `test_mpris.py` can be rewritten to ~6 tests against the stub; the 260+ other tests port mechanically to pytest-qt without structural rewrites | Pitfall 8, Pattern 9 | If GTK-widget tests exist and weren't scouted, the "big-bang port" task scope balloons. D-25 already acknowledges this as a deferral option. Planner should scout test file imports during planning. |
| A6 | Current 265 test count holds across the port (no tests dropped); 12 files currently `import gi` | QA-02 mapping | Verified via grep: 12 files. Remaining 10 test files have no GTK/GLib dependency and port trivially. |
| A7 | `QCoreApplication` (headless) is sufficient for `pytest-qt` `qtbot`; widgets-in-offscreen `QApplication` also works and is cheaper in developer effort | Pattern 9 | If pytest-qt requires `QApplication` specifically, the conftest uses `QApplication` with offscreen platform — zero runtime cost, no widgets exist anyway. HIGH confidence this works either way. |
| A8 | The mpv spike's cookie-protected case (D-20c) is the most likely to fail — `souphttpsrc` in GStreamer has historically had rough edges with cookie-jar injection on HLS manifests | Pattern 6 / spike | Informs planner that the spike task should start with case (c) to fail fast. [ASSUMED from general GStreamer knowledge; not verified against current GStreamer 1.26 release notes] |

**Recommendation:** Assumptions A3 and A8 are worth a 5-minute verification at the start of the library-port task and the spike task respectively. The rest are low-risk or self-verifying during implementation.

## Open Questions (RESOLVED)

1. **Does `enable_sync_message_emission()` materially improve ICY update latency vs. async-only `add_signal_watch()` on the bridge thread?**
   - What we know: CONTEXT.md D-07 mentions sync emission as part of the recipe; the current GTK path uses async only and works.
   - What's unclear: Whether the phrase in D-07 is prescriptive ("you must add sync emission") or descriptive ("GStreamer supports sync emission and we can use it if needed").
   - Recommendation: Treat D-07 as prescriptive per CONTEXT.md rules; implement with `enable_sync_message_emission()` but use async handlers only (sync handlers would stall the streaming thread per Pitfall 5). If there's doubt, open a discuss-phase question.
   - **Resolution:** Implement the bridge WITH `bus.enable_sync_message_emission()` as D-07 requires (prescriptive). Per Pitfall 5, use async handlers ONLY — never attach sync handlers to sync-emitted messages, since sync handlers run on the GStreamer streaming thread and would stall playback. Concretely: call `bus.enable_sync_message_emission()` in `Player.__init__()` immediately before `bus.add_signal_watch()`, then connect handlers via `bus.connect("message::tag", ...)` etc. All handlers fire on the bridge thread's GLib main loop and emit queued Qt signals. No sync-emission handlers are registered. This matches CONTEXT.md D-07 literally and avoids the sync-handler pitfall.

2. **Does the spike run in CI or as a manual local task?** (CONTEXT.md says Claude's discretion.)
   - Recommendation: Manual + checked-in spike doc (`35-SPIKE-MPV.md`). CI-ing a network-dependent YouTube probe is flaky.
   - **Resolution:** Manual + committed artifact. The spike runs locally on the developer's machine (requires network + real YouTube streams + real cookies file). Results are hand-written into `.planning/phases/35-backend-isolation/35-SPIKE-MPV.md` and committed as the first Phase 35 artifact. CI does not gate on the spike. Rationale: CI cannot reliably reach YouTube live streams or handle cookie-protected content; the spike is a one-shot design decision, not a recurring test.

3. **Is there a known-good ShoutCast URL that should be hard-coded into `__main__.py` for smoke testing, or should it take a CLI arg?**
   - Recommendation: CLI arg with a documented-in-comments fallback URL (e.g., the existing Chillhop stream referenced in INTEGRATIONS.md: `https://streams.chillhop.com/live?type=.mp3`). Covers both cases.
   - **Resolution:** CLI arg with a documented Chillhop ShoutCast fallback. Usage: `python -m musicstreamer [URL]`. If no arg given, default to a well-known-good ShoutCast stream URL for the smoke test (Chillhop's public stream). Rationale: flexibility for spike cases (test different URL types), plus a no-arg sanity check for the roadmap success criterion #1 verification.

4. **Does `extract_flat='in_playlist'` in the current yt-dlp version populate `live_status`?**
   - What we know: Issue #9983 on yt-dlp GitHub discusses flat-playlist field sparsity; the answer has shifted over versions.
   - Recommendation: Write the library-port task to probe this at implementation time. Pin a yt-dlp version that behaves as expected (bumping pin is safer than chasing API drift).
   - **Resolution:** Probe at implementation. The library port task MUST add a test that calls `yt_dlp.YoutubeDL({'extract_flat': 'in_playlist', 'quiet': True}).extract_info(test_playlist_url, download=False)` and asserts that entries have either `live_status` OR that `is_live is True` works as a fallback. If `extract_flat` returns sparse entries missing both fields, fall back to a per-entry non-flat resolution for live-detection only (slower but reliable). Record the observed field shape in `35-03-ytdlp-and-mpris-stub-PLAN.md`'s notes at implementation time.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | All tasks | ✓ | 3.13.7 | — |
| GStreamer | `playbin3` bus bridge | ✓ | 1.26.6 | — |
| PyGObject (`gi`) | `Gst`, `GLib.MainLoop` | ✓ (system) | — | — |
| platformdirs | `paths.py`, migration | ✓ | 4.3.7 | — |
| pytest | Test runner | ✓ | 9.0.2 | — |
| **PySide6** | QObject, Signals, QCoreApplication, QTimer | **✗** | — | **None — must pip install (blocks PORT-01 / PORT-02)** |
| **yt-dlp** (Python pkg) | Playlist scan + YouTube resolution | **✗** | — | **None — currently used only via `shutil.which("yt-dlp")`; library port requires pip install** |
| **streamlink** (Python pkg) | Twitch HLS resolution | **✗** | — | **None — library port requires pip install** |
| **pytest-qt** | Headless Qt test harness | **✗** | — | **None — QA-02 blocker** |
| mpv binary | Current `_play_youtube` | Not probed — depends on spike outcome | — | yt-dlp library + playbin3 (spike decides) |

**Missing dependencies with no fallback (blocking):**
- `PySide6`, `yt-dlp`, `streamlink`, `pytest-qt` — all four must be installed before any Phase 35 code task can run. Planner must include an explicit "install Phase 35 dependencies" task as the first plan task AFTER the spike (D-23 spike doc doesn't need them, but everything else does).

**Missing dependencies with fallback:**
- None — the spike's purpose is to determine whether `mpv` can be removed; it's not a fallback for another tool.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-qt (to install) |
| Config file | `pyproject.toml` — add `[tool.pytest.ini_options]` with `env = QT_QPA_PLATFORM=offscreen` |
| Quick run command | `pytest -x -q tests/test_player_tag.py tests/test_player_failover.py` |
| Full suite command | `QT_QPA_PLATFORM=offscreen pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| **PORT-01** | `Player` is `QObject`; `title_changed`, `failover`, `offline`, `playback_error` are Qt Signals | unit | `pytest tests/test_player_signals.py -x` | ❌ Wave 0 (new file) |
| **PORT-01** | `_on_gst_tag` emits `title_changed` with decoded ICY title | unit | `pytest tests/test_player_tag.py::test_title_signal_emitted -x` | ⚠️ Rewrite existing `test_player_tag.py` |
| **PORT-01** | `_on_gst_error` emits `failover` (next) or `playback_error` | unit | `pytest tests/test_player_failover.py -x` | ⚠️ Rewrite existing file |
| **PORT-01** | `player.py` contains zero `GLib.idle_add`, `GLib.timeout_add`, `GLib.source_remove`, `dbus` imports | smoke (grep) | `pytest tests/test_no_gtk_imports.py::test_player_no_glib -x` | ❌ Wave 0 (new grep test) |
| **PORT-02** | `GstBusLoopThread.start()` spins a `GLib.MainLoop` on a daemon thread; `bus.add_signal_watch()` handlers fire under the loop | integration | `pytest tests/test_gst_bus_bridge.py -x` | ❌ Wave 0 (new) |
| **PORT-02** | Signal emitted from bus-loop thread reaches main-thread slot via queued connection | integration | `pytest tests/test_gst_bus_bridge.py::test_cross_thread_signal -x` (uses `qtbot.waitSignal`) | ❌ Wave 0 |
| **PORT-05** | `paths.db_path()` returns `platformdirs.user_data_dir('musicstreamer') + '/musicstreamer.sqlite3'` | unit | `pytest tests/test_paths.py -x` | ❌ Wave 0 (new) |
| **PORT-05** | `paths.py` allows `_root_override` monkeypatch for tests | unit | `pytest tests/test_paths.py::test_monkeypatch -x` | ❌ Wave 0 |
| **PORT-05** | No string literal `~/.local/share/musicstreamer` remains in `musicstreamer/` source | smoke (grep) | `pytest tests/test_no_gtk_imports.py::test_no_hardcoded_paths -x` | ❌ Wave 0 |
| **PORT-06** | `migration.run_migration()` is idempotent — writes marker and short-circuits on second call | unit | `pytest tests/test_migration.py::test_idempotent -x` | ❌ Wave 0 (new) |
| **PORT-06** | Non-destructive copy when src != dest, skips existing files at dest | unit | `pytest tests/test_migration.py::test_copy_nondestructive -x` | ❌ Wave 0 |
| **PORT-06** | Linux same-path case writes marker without copying | unit | `pytest tests/test_migration.py::test_linux_same_path -x` | ❌ Wave 0 |
| **PORT-09** | `scan_playlist(url)` uses `yt_dlp.YoutubeDL` (not subprocess); ValueError on private/unavailable | unit | `pytest tests/test_yt_import.py -x` (mock `yt_dlp.YoutubeDL`) | ⚠️ Rewrite existing `test_import_dialog.py` partially + new `test_yt_import.py` |
| **PORT-09** | `_play_twitch` uses `streamlink.session.Streamlink` (not subprocess); sets `api-header` plugin option when token present | unit | `pytest tests/test_twitch_playback.py -x` (mock `streamlink.session`) | ⚠️ Rewrite existing file |
| **PORT-09** | Subprocess module is NOT imported in `player.py` or `yt_import.py` (unless mpv fallback retained) | smoke (grep) | `pytest tests/test_no_gtk_imports.py::test_no_subprocess -x` | ❌ Wave 0 (conditional on spike) |
| **PORT-09** | Spike result document exists at `.planning/phases/35-backend-isolation/35-SPIKE-MPV.md` | manual | checked at verify-work gate | — |
| **QA-02** | Test suite count ≥ 265 on Linux | smoke | `pytest --collect-only -q | grep -c "::" ` ≥ 265 | — |
| **QA-02** | Zero files in `tests/` contain `import gi` or `from gi` | smoke (grep) | `pytest tests/test_no_gtk_imports.py::test_tests_have_no_gi -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest -x -q tests/<files touched by this task>`
- **Per wave merge:** `QT_QPA_PLATFORM=offscreen pytest -q`
- **Phase gate:** Full suite green + manual smoke via `python -m musicstreamer <shoutcast_url>` showing ICY title updates in terminal (success criterion #1).

### Wave 0 Gaps

- [ ] `pip install PySide6 pytest-qt yt-dlp streamlink` — before any test can even import
- [ ] `tests/conftest.py` — set `QT_QPA_PLATFORM=offscreen` at top, add `qapp` fixture override if needed
- [ ] `tests/test_player_signals.py` — new file, verifies Qt signals exist and emit correctly
- [ ] `tests/test_gst_bus_bridge.py` — new file, verifies bus-loop thread + queued signal delivery
- [ ] `tests/test_paths.py` — new file, verifies `paths.py` helpers and monkeypatch support
- [ ] `tests/test_migration.py` — new file, verifies PORT-06 three cases
- [ ] `tests/test_yt_import.py` — new file, verifies library-API scan (or merge into rewritten `test_import_dialog.py`)
- [ ] `tests/test_no_gtk_imports.py` — new file, grep-style smoke tests: no `GLib.idle_add` in `player.py`, no `import gi` in `tests/`, no hard-coded `~/.local/share/musicstreamer` literals in source, no `subprocess` in `yt_import.py`
- [ ] `tests/test_mpris.py` — **rewrite** entirely to test the stub (6 tests replacing 140 lines of dbus mocking)
- [ ] `tests/test_player_tag.py`, `test_player_failover.py`, `test_player_pause.py`, `test_player_buffer.py`, `test_player_volume.py`, `test_twitch_auth.py`, `test_twitch_playback.py`, `test_cookies.py`, `test_icy_escaping.py`, `test_aa_url_detection.py`, `test_yt_thumbnail.py` — port `gi` imports to Qt signal assertions via `qtbot.waitSignal` (12 files total; verified count)

## Security Domain

Phase 35 is a backend refactor with no new attack surface. STRIDE / ASVS applicability:

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (Twitch OAuth token already stored; this phase just changes how it's read) |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | minimal | URL parsing delegated to `yt-dlp` and `streamlink` libraries — no hand-rolled URL handling |
| V6 Cryptography | no | — |

**Relevant threats:**

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Token file world-readable after migration | Information disclosure | `shutil.copy2` preserves mode bits; current `twitch-token.txt` is already `0600` (verified: `ls -la` shows `-rw-------`). Migration helper must preserve this. Document in PORT-06 task: use `copy2` not `copy`. |
| Cookie file copied to new location without mode preservation | Information disclosure | Same — `copy2` preserves mode. Verified source `cookies.txt` is already `0600`. |
| yt-dlp library executes `ffmpeg` / other binaries via its extractor chain | Elevation (already latent) | Unchanged from current subprocess path — yt-dlp has always been able to invoke ffmpeg. Not new in this phase. Not a Phase 35 concern. |

**No new secrets handled. No new network endpoints. No new file writes outside `user_data_dir`.** Security review: pass.

## Sources

### Primary (HIGH confidence)
- PySide6 docs — `Signal`, `QObject`, `QTimer`, `QCoreApplication`, `Qt.ConnectionType`: https://doc.qt.io/qtforpython-6/
- PyPI PySide6 6.11.0 release (2026-03-23): https://pypi.org/project/PySide6/
- platformdirs docs: https://platformdirs.readthedocs.io/
- yt-dlp Python API source: https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py
- streamlink API guide: https://streamlink.github.io/api_guide.html
- streamlink Twitch plugin docs: https://streamlink.github.io/cli/plugins/twitch.html
- pytest-qt docs: https://pytest-qt.readthedocs.io/
- Local audit of `musicstreamer/player.py`, `yt_import.py`, `mpris.py`, `constants.py`, `ui/main_window.py` (2026-04-11)
- Local verification: `gst-inspect-1.0 --version` → 1.26.6; `platformdirs.user_data_dir('musicstreamer')` → `/home/kcreasey/.local/share/musicstreamer`

### Secondary (MEDIUM confidence)
- streamlink discussion #4400 (Twitch OAuth API header scoping): https://github.com/streamlink/streamlink/discussions/4400
- streamlink discussion #5173 (options in Python API): https://github.com/streamlink/streamlink/discussions/5173
- yt-dlp issue #9983 (extract_flat field sparsity): https://github.com/yt-dlp/yt-dlp/issues/9983

### Tertiary (LOW confidence / assumed)
- A8 (souphttpsrc + HLS + cookies rough edges) — general GStreamer ecosystem knowledge, not verified against 1.26.6 release notes
- A2 (`live_status` reliability with `extract_flat='in_playlist'`) — yt-dlp shape varies by version

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PySide6, platformdirs, pytest-qt, yt-dlp, streamlink are all verified against current pypi/docs
- Architecture (QObject + GLib bridge): HIGH — Qt threading model is well-documented and the pattern is standard
- yt-dlp library API shape: MEDIUM — field-level details (`live_status` vs `is_live`) drift between versions; plan must probe at implementation time
- streamlink plugin-option API: MEDIUM — discussions show the pattern but exact method name on `Streamlink` session varies (may need `set_plugin_option` or `plugin_manager` indirection)
- Runtime state inventory: HIGH — empirically verified on this box
- mpv spike outcome: UNKNOWN by design — that's why the spike exists
- Current test coverage shape: HIGH — 12 gi-importing test files enumerated; `test_mpris.py` structure read and planned for rewrite

**Research date:** 2026-04-11
**Valid until:** 2026-05-11 (30 days — stack is stable; only yt-dlp/streamlink field shapes drift meaningfully)
