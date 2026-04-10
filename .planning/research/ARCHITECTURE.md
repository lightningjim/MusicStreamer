# Architecture Research

**Domain:** Desktop streaming radio app — GTK4 → Qt/PySide6 port
**Researched:** 2026-04-10
**Confidence:** HIGH (based on direct source audit)

---

## 1. Backend Isolation Audit

### Clean reuse — zero changes needed

| Module | Why clean |
|--------|-----------|
| `musicstreamer/models.py` | Pure dataclasses, no imports from gi or Adw |
| `musicstreamer/repo.py` | sqlite3 + models only; `DB_PATH` from constants |
| `musicstreamer/constants.py` | stdlib only (`os`); one GTK-unrelated concern: `DATA_DIR` is Linux-flavored (`~/.local/share/...`) — needs a platform abstraction (see Section 5) |
| `musicstreamer/cover_art.py` | stdlib only (`json`, `threading`, `urllib`); the `GLib.idle_add` call is **not** in this module — it lives in the callers in `main_window.py` |
| `musicstreamer/radio_browser.py` | urllib + daemon threads; no GTK |
| `musicstreamer/yt_import.py` | yt-dlp subprocess + threading + thread-local SQLite; no GTK |
| `musicstreamer/aa_import.py` | urllib + ThreadPoolExecutor + thread-local SQLite; no GTK |
| `musicstreamer/filter_utils.py` | Pure Python string/set logic; no GTK |
| `musicstreamer/assets.py` | stdlib file copy; no GTK |
| `musicstreamer/accent_utils.py` | Pure Python regex + string building; produces CSS strings — the CSS format will differ between GTK and Qt, but the hex-validation logic is reusable |

### Requires refactoring — GTK/GLib/dbus contamination

| Module | Contamination | Refactor scope |
|--------|--------------|----------------|
| `musicstreamer/player.py` | `gi.repository.Gst`, `gi.repository.GLib` — GLib is used for `idle_add`, `timeout_add`, `source_remove` throughout. GStreamer itself stays; only the GLib timer/idle calls must be replaced with Qt equivalents. | Medium — remove all `GLib.*` calls, replace with Qt signal emission or `QMetaObject.invokeMethod` (see Section 3) |
| `musicstreamer/mpris.py` | `dbus`, `dbus.service`, `dbus.mainloop.glib`, `gi.repository.GLib` — entire file is Linux D-Bus specific. | Replace entirely with platform media-key shim (see Section 5) |
| `musicstreamer/ui/main_window.py` | Full GTK4/Adw window — replace entirely | Replace with `musicstreamer/ui_qt/main_window.py` |
| `musicstreamer/ui/station_row.py` | GTK4 `Gtk.ListBoxRow` + Adw.ActionRow | Replace with Qt widget |
| `musicstreamer/ui/edit_dialog.py` | GTK4/Adw dialog; references `GLib.idle_add` for background fetches | Replace with Qt dialog |
| `musicstreamer/ui/discovery_dialog.py` | `Adw.Window` + GLib | Replace with Qt dialog |
| `musicstreamer/ui/import_dialog.py` | `Adw.Window` + GLib | Replace with Qt dialog |
| `musicstreamer/ui/accent_dialog.py` | `Adw.Window` + `Gtk.CssProvider` | Replace with Qt dialog; accent logic moves to Qt stylesheet injection |
| `musicstreamer/ui/accounts_dialog.py` | `Adw.Window` + `GLib`; spawns a WebKit2 subprocess for Twitch OAuth | Replace with Qt dialog; WebKit2 subprocess call is an exec() — the subprocess itself (a separate Python script) can stay or be replaced with QWebEngineView |
| `musicstreamer/ui/streams_dialog.py` | `Adw.Window` + GLib | Replace with Qt dialog |

### The `player.py` GLib dependency is the critical seam

`player.py` uses `GLib.idle_add` and `GLib.timeout_add` in three patterns:
1. Marshalling GStreamer bus callbacks (`_on_gst_tag`, `_on_gst_error`) back to the UI thread
2. One-shot failover timers (`GLib.timeout_add(BUFFER_DURATION_S * 1000, ...)`)
3. YouTube poll timer (`GLib.timeout_add(1000, self._yt_poll_cb)`)

All three must be ported. The GStreamer pipeline itself does not change.

---

## 2. Package Layout — Cutover Sequencing

**Recommendation: hard cutover, not parallel ui/ + ui_qt/**

Rationale: the GTK UI is being retired entirely. A dual-UI period creates dead weight — two full window implementations diverging as backend work continues, with no consumer for the GTK path after the port starts. The test suite tests backend logic, not UI widgets, so keeping GTK alive for test coverage is not a reason.

Sequencing:

```
Phase A (backend prep): Refactor player.py to remove GLib; verify tests still pass.
Phase B (scaffold):     Create musicstreamer/ui_qt/ with skeleton MainWindow (QMainWindow).
Phase C (cutover):      Delete musicstreamer/ui/ entirely. Move __main__ / app entry point to Qt.
Phases D-N (features):  Implement each dialog and view inside ui_qt/.
```

The moment `musicstreamer/ui/` is deleted (Phase C), the GTK dependency chain is gone. `gi` package can be removed from the dev environment for UI work. GStreamer still requires `gi.repository.Gst` — only the GTK/Adw/GLib pieces go away.

**Package layout post-cutover:**

```
musicstreamer/
├── __init__.py
├── constants.py              # data dir stays; platform abstraction added alongside
├── models.py                 # unchanged
├── repo.py                   # unchanged
├── cover_art.py              # unchanged
├── filter_utils.py           # unchanged
├── assets.py                 # unchanged
├── radio_browser.py          # unchanged
├── yt_import.py              # unchanged
├── aa_import.py              # unchanged
├── accent_utils.py           # hex validation reused; CSS template rewritten for Qt
├── player.py                 # refactored: GLib removed, QObject + signals + QTimer
├── platform_utils.py         # NEW: data dir, secure write, tool search path
├── media_keys/               # replaces mpris.py
│   ├── __init__.py           # factory: returns platform impl
│   ├── mpris.py              # Linux: MPRIS2 (ported to QDBusConnection or kept dbus-python)
│   └── smtc.py               # Windows: SMTC via winsdk or winrt
└── ui_qt/
    ├── __init__.py
    ├── main_window.py        # QMainWindow
    ├── station_row.py        # custom QWidget
    ├── edit_dialog.py        # QDialog
    ├── discovery_dialog.py
    ├── import_dialog.py
    ├── accent_dialog.py
    ├── accounts_dialog.py
    ├── streams_dialog.py
    └── widgets/              # reusable: ExpanderSection, ToastOverlay, FlowLayout, etc.
        ├── expander_section.py
        ├── toast_overlay.py
        └── flow_layout.py
```

---

## 3. Threading Model: GLib → Qt

### Current GTK pattern

GStreamer's bus callbacks fire on GStreamer's internal thread. GTK is not thread-safe, so all UI mutations go through `GLib.idle_add(fn, args)`, which schedules `fn` on the GLib main loop.

Timers use `GLib.timeout_add(ms, cb)` which returns a source ID; `GLib.source_remove(id)` cancels it. Return `True` to repeat, `False` to stop.

### Qt equivalent pattern

Qt is also not thread-safe from non-main threads. The standard replacement:

**For callbacks (idle_add equivalent):**

Qt signals emitted from a non-main thread are delivered via `QueuedConnection` by default when the receiver lives on a different thread. This makes signal emission safe from GStreamer's bus thread.

**Recommended approach for Player:** Make `Player` a `QObject` and define signals for each callback type.

```python
from PySide6.QtCore import QObject, Signal, QTimer

class Player(QObject):
    title_changed = Signal(str)      # replaces on_title callback
    failover_event = Signal(object)  # replaces on_failover callback
    offline_event = Signal(str)      # replaces on_offline callback

    def __init__(self):
        super().__init__()
        # GStreamer init unchanged
        ...
        self._failover_timer = QTimer(self)
        self._failover_timer.setSingleShot(True)
        self._failover_timer.timeout.connect(self._on_timeout_cb)

        self._yt_poll_timer = QTimer(self)
        self._yt_poll_timer.setInterval(1000)
        self._yt_poll_timer.timeout.connect(self._yt_poll_cb)
```

**GStreamer bus callbacks** (`_on_gst_tag`, `_on_gst_error`) still fire on the GStreamer thread. Emit the signal directly — Qt signals emitted from a non-main thread with `QueuedConnection` (the default when receiver is on a different thread) are safe:

```python
def _on_gst_tag(self, bus, msg):
    taglist = msg.parse_tag()
    found, value = taglist.get_string(Gst.TAG_TITLE)
    self._cancel_failover_timer()
    if found:
        title = _fix_icy_encoding(value)
        self.title_changed.emit(title)  # safe — Qt queues across threads
```

**Timers:** Replace `GLib.timeout_add` / `GLib.source_remove` with `QTimer`:
- One-shot: `timer.setSingleShot(True); timer.start(ms)`
- Repeating: `timer.start(ms)` with `timer.timeout.connect(cb)`
- Cancel: `timer.stop()`

**`_cancel_failover_timer`** becomes:

```python
def _cancel_failover_timer(self):
    self._failover_timer.stop()
    self._yt_poll_timer.stop()
    self._yt_attempt_start_ts = None
```

**Callback API on play():** The `on_title`, `on_failover`, `on_offline` callable parameters can be retired — callers connect to the signals instead. This is a cleaner API.

---

## 4. GStreamer + Qt Event Loop Integration

### The problem

GStreamer uses GLib's `GMainContext`. GTK apps run GLib's main loop (`GApplication.run()`), which naturally drives GStreamer's bus watch. Qt runs its own `QEventLoop`, which does not drive GLib.

This means `bus.add_signal_watch()` + `bus.connect("message::tag", ...)` only fires if the GLib main context is iterating.

### Solution: GLib main loop in a background thread

Run a minimal `GMainLoop` on a dedicated daemon thread alongside Qt's main loop:

```python
import threading
from gi.repository import GLib

def _run_glib_loop():
    loop = GLib.MainLoop()
    loop.run()  # blocks this thread; drives GStreamer bus

glib_thread = threading.Thread(target=_run_glib_loop, daemon=True)
glib_thread.start()
```

Start this before instantiating `Player`. The GStreamer pipeline and its bus watch are driven by this loop. GStreamer callbacks fire on the glib thread; they emit Qt signals (queued connection), which deliver to the Qt main thread.

Qt's `QApplication.exec()` runs normally on the main thread.

This is the idiomatic pattern for GStreamer + Qt coexistence. Confidence: MEDIUM (confirmed by GStreamer documentation on GMainContext threading; no Context7 entry for this specific combination).

**Alternative (not recommended):** `GLib.MainContext.default().iteration(False)` polled from a QTimer. This is fragile and wastes cycles.

### What does NOT need GLib

`GLib.idle_add` and `GLib.timeout_add` in `player.py` are fully replaced by Qt signals and `QTimer`. After the refactor, the GLib thread exists only to drive the GStreamer bus. If GStreamer is ever replaced with a Qt-native backend, even this thread goes away — but that is out of v2.0 scope.

---

## 5. Platform Abstraction Seams

### Seam 1: Data directory paths

**Current:** `constants.py` hardcodes `~/.local/share/musicstreamer/` (XDG on Linux).

**Windows equivalent:** `%APPDATA%\MusicStreamer\`.

**Module boundary:** Add `musicstreamer/platform_utils.py`:

```python
import sys, os
from pathlib import Path

def app_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())).expanduser()
    else:
        base = Path.home() / ".local" / "share"
    d = base / "musicstreamer"
    d.mkdir(parents=True, exist_ok=True)
    return d
```

`constants.py` calls `platform_utils.app_data_dir()` for `DATA_DIR`. No other module changes.

### Seam 2: Media keys

**Current:** `mpris.py` — MPRIS2 via `dbus-python`. Linux only.

**Windows equivalent:** Windows SMTC (System Media Transport Controls) via `winsdk` Python package.

**Module boundary:** `musicstreamer/media_keys/__init__.py` exposes a factory:

```python
import sys

def create_media_keys_service(window):
    if sys.platform == "win32":
        from musicstreamer.media_keys.smtc import SmtcService
        return SmtcService(window)
    else:
        from musicstreamer.media_keys.mpris import MprisService
        return MprisService(window)
```

Both classes expose: `start()`, `stop()`. On Linux, `MprisService` can be rewritten to use `QDBusConnection` (removes `dbus-python` dep) or kept as-is.

### Seam 3: Cookie / token file permissions

**Current:** `os.chmod(path, 0o600)` — POSIX only; no-op on Windows.

**Platform boundary:** Wrap in `platform_utils.secure_file_write(path, content)`. On Windows, skip chmod (NTFS user home is private by default). Low risk.

### Seam 4: Subprocess PATH expansion

**Current:** `player.py` prepends `~/.local/bin` to PATH for subprocess calls (mpv, streamlink, yt-dlp).

**Windows equivalent:** Binaries installed via pip/pipx land elsewhere; PATH composition differs.

**Module boundary:** `platform_utils.extra_tool_dirs() -> list[str]`. Linux returns `[~/.local/bin]`; Windows returns `[]`.

### Seam 5: File picker

**Current:** `Gtk.FileDialog` / `Gtk.FileChooserDialog` — GTK only.

**Qt equivalent:** `QFileDialog.getOpenFileName()` — cross-platform. No additional seam needed.

### Seam 6: Twitch OAuth browser

`accounts_dialog.py` spawns a subprocess running a WebKit2 GTK browser to capture the Twitch auth cookie. On Windows, WebKit2 is unavailable.

**Platform boundary:** Replace the subprocess approach with `QWebEngineView` (bundled with PySide6, works on both platforms). The accounts dialog uses `QWebEngineView` inline and intercepts the cookie directly — no subprocess needed. This simplifies the implementation and removes the `tempfile.mktemp` debt noted in MILESTONES.md.

---

## 6. GTK Widget → Qt Widget Mapping

| GTK / Libadwaita widget | Purpose | Qt equivalent | Notes |
|-------------------------|---------|---------------|-------|
| `Adw.ApplicationWindow` | Top-level window | `QMainWindow` | Direct equivalent |
| `Adw.ToolbarView` | Window chrome with header + content | `QMainWindow` layout (central widget + toolbar) | Maps directly |
| `Adw.HeaderBar` | Title bar with packed widgets | Horizontal `QWidget` in a `QToolBar` or custom title bar | Qt doesn't enforce an opinionated header bar pattern |
| `Adw.ExpanderRow` | Collapsible group row in list | No direct Qt built-in — custom `ExpanderSection(QWidget)`: `QPushButton` header + collapsible `QFrame` child | Most complex widget to replicate; ~80 lines |
| `Adw.ActionRow` | List row with title, subtitle, prefix/suffix | Custom `QWidget` with `QHBoxLayout`: icon, `QVBoxLayout` (title + subtitle labels), suffix buttons | No direct equivalent; straightforward to build |
| `Adw.ComboRow` | Dropdown in form | `QComboBox` with label | Simpler in Qt |
| `Adw.Toast` / `Adw.ToastOverlay` | Snackbar notification | No Qt built-in — `ToastOverlay(QWidget)` that creates floating labeled overlays at window bottom | ~50 lines; position relative to parent window |
| `Adw.ToggleGroup` / `Adw.Toggle` | Segmented control (Stations/Favorites) | `QButtonGroup` with exclusive `QToolButton`s, styled as pill group | No direct match; ~20 lines + CSS |
| `Adw.StatusPage` | Empty state with icon + message | Custom `QWidget`: `QVBoxLayout` with icon `QLabel`, title `QLabel`, desc `QLabel`, optional `QPushButton` | Trivial to build |
| `Adw.Window` (dialogs) | Modal window | `QDialog` | Direct equivalent |
| `Adw.WindowTitle` | Title + subtitle header | `QLabel` with two lines, centered | Simple |
| `Adw.SwitchRow` | Toggle switch in form | Horizontal layout: `QLabel` + `QCheckBox` | No form-row abstraction in Qt |
| `Gtk.ListBox` | Selectable vertical list | `QListWidget` (simple) or `QListView` + model (complex) | Use direct fill — see Section 7 |
| `Gtk.FlowBox` | Wrapping chip/tile layout | No Qt built-in — use Qt's documented `FlowLayout` QLayout subclass (~100 lines from Qt examples) | Required for provider/tag chip strips and tag editor |
| `Gtk.Stack` | Swap between children (logo vs spinner) | `QStackedWidget` | Direct equivalent |
| `Gtk.Picture` | Image with content-fit modes | `QLabel` with `QPixmap` + manual scale-to-fit | Scale manually for CONTAIN letterbox behavior |
| `Gtk.Image` | Icon / scaled image | `QLabel` with `QPixmap` | Direct equivalent |
| `Gtk.SearchEntry` | Search bar | `QLineEdit` with leading search icon action | No special subclass needed |
| `Gtk.ScrolledWindow` | Scrollable container | `QScrollArea` | Direct equivalent |
| `Gtk.Scale` | Volume slider | `QSlider` (horizontal, 0–100) | Direct equivalent |
| `Gtk.MenuButton` + `Gio.Menu` | Hamburger menu | `QToolButton` with `setMenu(QMenu())` | Direct equivalent |
| `Gio.SimpleAction` | Named app-level actions | `QAction` added to `QMainWindow` or `QApplication` | Direct equivalent |
| `Gtk.CssProvider` at PRIORITY_USER | Accent color injection | `QApplication.setStyleSheet(css)` | CSS format differs — GTK `button.suggested-action` → Qt `QPushButton`; `scale trough highlight` → `QSlider::sub-page:horizontal` |
| `GLib.markup_escape_text` | Escape Pango markup | Not needed — Qt labels don't parse HTML by default | Plain `setText()` is safe without escaping |
| `Gtk.Notebook` (tabbed ImportDialog) | Tabs | `QTabWidget` | Direct equivalent |

### GTK idioms with no direct Qt match (require custom code)

1. **`Adw.ExpanderRow`** — Custom `ExpanderSection(QWidget)`, ~80 lines. Lives in `ui_qt/widgets/expander_section.py`.
2. **`Adw.Toast` / `Adw.ToastOverlay`** — Custom `ToastOverlay(QWidget)`, ~50 lines. Lives in `ui_qt/widgets/toast_overlay.py`.
3. **`Gtk.FlowBox`** — Qt's `FlowLayout` from official examples, ~100 lines. Lives in `ui_qt/widgets/flow_layout.py`.
4. **`Adw.ToggleGroup`** — `QButtonGroup` + styled `QToolButton`s, ~20 lines + stylesheet.

---

## 7. Data Layer: QAbstractListModel or Direct Fill?

**Recommendation: direct widget fill. No QAbstractListModel.**

At 200 stations, direct `QListWidget` population renders in under a millisecond. The GTK codebase already clears and repopulates the listbox on every filter change (`_render_list` calls `_clear_listbox` then populates). This pattern translates directly.

`QAbstractListModel` is warranted when the data changes frequently with incremental updates, or the same data feeds multiple views simultaneously. Neither applies here.

The grouped-view case (provider `ExpanderSection` widgets) further argues against a flat model — a model index space doesn't cleanly map to collapsible grouped rows. Direct population of a `QVBoxLayout` with `ExpanderSection` widgets matches the GTK `ExpanderRow` pattern exactly.

Favorites view is a simple `QListWidget` with trash buttons — also direct fill.

---

## 8. System Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────┐
│                    Qt Main Thread (QEventLoop)                     │
│                                                                    │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │   MainWindow      │  │   Dialogs    │  │   MediaKeys      │    │
│  │  (QMainWindow)    │  │  (QDialog)   │  │  (platform shim) │    │
│  └────────┬──────────┘  └──────┬───────┘  └────────┬─────────┘    │
│           │                   │                    │              │
│           └─────────┬─────────┘                    │              │
│                     │                              │              │
│  ┌──────────────────▼──────────────────────────────▼────────────┐ │
│  │                    Player (QObject)                           │ │
│  │  Signals: title_changed, failover_event, offline_event        │ │
│  │  Timers:  QTimer (failover_timer, yt_poll_timer)              │ │
│  └────────────────────────────┬──────────────────────────────────┘ │
└────────────────────────────────┼──────────────────────────────────┘
                                 │ GStreamer callbacks emit signals
┌────────────────────────────────▼──────────────────────────────────┐
│                    GLib Thread (GMainLoop, daemon)                  │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │  GStreamer playbin3 bus — _on_gst_tag, _on_gst_error       │    │
│  └───────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                    Backend (any thread, stateless)                  │
│  repo.py  cover_art.py  radio_browser.py  filter_utils.py          │
│  yt_import.py  aa_import.py  assets.py  platform_utils.py          │
└────────────────────────────────────────────────────────────────────┘
```

---

## 9. Build Order (Phase Sequence)

### Phase A: Backend isolation (prerequisite)

**Deliverable:** `player.py` compiles without `gi.repository.GLib`. All 265 tests pass.

- Remove `GLib` import from `player.py`; make `Player` a `QObject`
- Replace `GLib.idle_add(fn, arg)` with `self.<signal>.emit(arg)`
- Replace `GLib.timeout_add(ms, cb)` / `source_remove(id)` with `QTimer` instances
- Add `GLib.MainLoop` daemon thread to app entry point (not in Player)
- Delete `mpris.py` (replaced in Phase G)
- Create stub `platform_utils.py` with `app_data_dir()` (Linux-only for now)

**Why first:** Everything else depends on a working Player. Tests prove backend is intact before any UI work begins.

### Phase B: Qt scaffold

**Deliverable:** `python -m musicstreamer` launches a Qt window (empty, no crash).

- Add PySide6 to dependencies
- Create `musicstreamer/ui_qt/__init__.py` and `main_window.py` (bare `QMainWindow`)
- Wire `__main__.py` to `QApplication` + `MainWindow` + GLib thread
- Load and apply persisted accent color via `QApplication.setStyleSheet`
- Confirm launch on Linux

### Phase C: Delete GTK UI

**Deliverable:** `musicstreamer/ui/` directory deleted; `gi` GTK/Adw packages no longer imported at runtime.

- Delete all files under `musicstreamer/ui/`
- Remove GTK-related imports from entry point
- `gi.repository.Gst` still needed (GStreamer); `gi.repository.GLib` still needed (GMainLoop thread)

### Phase D: Station list + now-playing panel

**Deliverable:** Stations load, grouped by provider in ExpanderSections, clicking plays, title updates.

- `FlowLayout` (from Qt examples)
- `ExpanderSection` custom widget
- `StationRow` widget (icon + title/subtitle + edit button)
- Now-playing panel: `QStackedWidget` logo slot, center column, cover slot
- `Player.title_changed` signal wired to UI label
- Volume `QSlider` wired to `Player.set_volume()`
- Recently played section
- `ToastOverlay` widget (needed for failover toasts)

### Phase E: Filter strip

**Deliverable:** Search + provider/tag chip filters + clear button.

- Search `QLineEdit` in toolbar
- Provider chip strip (exclusive `QToolButton` toggles in `FlowLayout`)
- Tag chip strip
- Clear button
- Empty state widget

### Phase F: Favorites view

**Deliverable:** Star button, Favorites list, remove.

- Star button in now-playing controls
- Favorites `QListWidget` with trash buttons
- Stations/Favorites segmented control (`QButtonGroup`)
- Empty state

### Phase G: Dialogs

**Deliverable:** All modal dialogs functional.

- `EditStationDialog` (form widgets, YT/AA auto-fetch, tag chips, streams sub-dialog)
- `ManageStreamsDialog` (CRUD + reorder)
- `DiscoveryDialog` (Radio-Browser search, preview, save)
- `ImportDialog` (`QTabWidget`: YouTube + AudioAddict tabs)
- `AccentDialog` (swatch grid + hex entry; writes `QApplication.setStyleSheet`)
- `AccountsDialog` (file picker + paste + `QWebEngineView` OAuth; replaces WebKit2 subprocess)

### Phase H: Platform integration

**Deliverable:** Media keys work on Linux and Windows.

- `musicstreamer/media_keys/` package with factory
- Linux: MPRIS2 via `QDBusConnection` (PySide6 ships DBus support on Linux) or `dbus-python` wrapper
- Windows: SMTC via `winsdk`
- Complete `platform_utils.py`: data dir, secure write, tool search dirs
- First Windows boot test

### Phase I: Settings export/import

**Deliverable:** Stations + config export as JSON; import merges.

- Serialize stations, providers, streams, settings to JSON
- `QFileDialog` for export/import
- Menu entry in hamburger

### Phase J: Windows packaging

**Deliverable:** Installable Windows binary.

- PyInstaller spec for Windows (bundle GStreamer DLLs, yt-dlp, streamlink)
- Installer (NSIS or WiX)
- End-to-end test on clean Windows install

---

## Integration Points

### Player signals → UI

| Signal | Emitted from | Consumed by | Qt transport |
|--------|-------------|-------------|-------------|
| `title_changed(str)` | GStreamer bus thread (via Player) | `MainWindow._on_title` | Queued signal |
| `failover_event(stream)` | Player (main or glib thread) | `MainWindow._on_failover` | Queued signal |
| `offline_event(channel)` | Player (glib thread) | `MainWindow._on_offline` | Queued signal |

### Cover art thread → UI

`cover_art.fetch_cover_art()` uses a daemon thread and calls a callback with the downloaded image path. In Qt, replace the raw callable with a small `QObject` wrapper that emits a signal, or use `QMetaObject.invokeMethod(main_window, "on_cover_art", Qt.QueuedConnection, ...)`.

### Platform seams

| Seam | Interface | Linux | Windows |
|------|-----------|-------|---------|
| Data dir | `platform_utils.app_data_dir()` | `~/.local/share/musicstreamer` | `%APPDATA%\MusicStreamer` |
| Media keys | `media_keys.create_service(window)` | MPRIS2 D-Bus | SMTC winsdk |
| File permissions | `platform_utils.secure_file_write(path, data)` | `os.chmod 0o600` | no-op |
| Subprocess PATH | `platform_utils.extra_tool_dirs()` | `[~/.local/bin]` | `[]` |
| OAuth browser | `AccountsDialog` | QWebEngineView (inline) | QWebEngineView (inline) |

---

## Anti-Patterns

### Anti-Pattern 1: Keeping GLib.idle_add in player.py

**What people do:** Leave `gi.repository.GLib` in `player.py` and run both loops.
**Why it's wrong:** Two blocking event loops cannot share one thread. Using `GLib.idle_add` from `player.py` while GLib runs on a background thread means the callbacks fire on the background thread, not the Qt main thread — causing UI crashes or silent threading violations.
**Do this instead:** Remove all `GLib.*` calls from `player.py`. Use Qt signals. GLib thread only drives the GStreamer bus.

### Anti-Pattern 2: QAbstractListModel for station list

**What people do:** Wrap station data in a `QAbstractListModel` and use `QListView`.
**Why it's wrong:** The grouped `ExpanderSection` layout doesn't fit a flat model index. Over-engineering for 200 items with no incremental update requirement.
**Do this instead:** Direct widget population, matching the existing GTK `_render_list()` pattern.

### Anti-Pattern 3: Translating GTK CSS selectors verbatim to Qt

**What people do:** Copy `build_accent_css()` output verbatim into `QApplication.setStyleSheet`.
**Why it's wrong:** GTK CSS selectors (`button.suggested-action`, `scale trough highlight`) are GTK-specific. Qt uses different syntax (`QPushButton`, `QSlider::sub-page:horizontal`).
**Do this instead:** Rewrite only the CSS template string in `build_accent_css()`. The hex validation logic is unchanged.

### Anti-Pattern 4: Parallel ui/ + ui_qt/ in production

**What people do:** Ship with both `ui/` (GTK) and `ui_qt/` (Qt) coexisting.
**Why it's wrong:** Double maintenance burden; no consumers for the GTK path after cutover begins.
**Do this instead:** Delete `ui/` at Phase C. Git history preserves the GTK implementation.

---

## Sources

- Direct source audit of `musicstreamer/` package (2026-04-10) — HIGH confidence
- GStreamer threading: GStreamer documentation on GMainContext and threading — MEDIUM confidence (not tested in this codebase yet)
- Qt signal thread affinity: PySide6 documentation on QueuedConnection — HIGH confidence
- Qt FlowLayout: Qt official examples, `layouts/flowlayout` — HIGH confidence
- SMTC on Windows: `winsdk` package — MEDIUM confidence (needs validation in Phase H)

---
*Architecture research for: MusicStreamer v2.0 Qt/PySide6 port*
*Researched: 2026-04-10*
