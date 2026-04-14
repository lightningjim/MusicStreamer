# Phase 37: Station List + Now Playing — Research

**Researched:** 2026-04-11
**Domain:** PySide6 / Qt6 widget UI porting (GTK4 → Qt), MVC station list, now-playing panel, frameless toast overlay
**Confidence:** HIGH (stack verified in-repo; patterns cited from official Qt docs)

## Summary

Phase 37 is the first visual-content Qt phase. It populates the Phase 36 bare MainWindow with (1) a provider-grouped station list (QTreeView + custom QAbstractItemModel), (2) a three-column now-playing panel (logo | text+controls | 160×160 cover art), (3) a volume slider with persistence, and (4) a frameless ToastOverlay for failover/connecting notifications. CONTEXT.md D-01..D-24 lock every major structural decision — this research exists only to pin implementation details (MVC skeletons, signal wiring, ownership, QSS strategy) so the planner can write prescriptive task actions.

**Primary recommendation:** Build 5 widget modules (`station_tree_model.py`, `station_list_panel.py`, `now_playing_panel.py`, `toast.py`, updated `main_window.py`) plus 4 test files. Own the `Player` instance on `MainWindow`, forward Player signals directly to `NowPlayingPanel` slots via auto-connection, and expose a `show_toast(text, duration_ms=3000)` method on `MainWindow` that `NowPlayingPanel` calls for failover/connecting messages. Use `QPixmapCache` for station row icons in the model's `DecorationRole`. Use `QPropertyAnimation` on `windowOpacity` for toast fade. Parent the toast to `centralWidget()` and re-anchor on `resizeEvent`.

## User Constraints (from CONTEXT.md)

### Locked Decisions (D-01..D-24)

**Station list:**
- **D-01:** `QTreeView` + custom `StationTreeModel(QAbstractItemModel)`. Two-level hierarchy: provider groups (top) → stations (children).
- **D-02:** Recently Played is a separate widget ABOVE the provider tree (not a tree branch). Planner picks implementation — (a) second QTreeView, (b) QListView with delegate, (c) custom widget stack. Simplest wins.
- **D-03:** Click or double-click → `player.play(station, preferred_quality=...)`. No drag-to-reorder. Expand/collapse is stock QTreeView.
- **D-04:** Provider group row shows bold label + `(N)` count (e.g. `SomaFM (12)`). Station row = 32×32 logo + name. Logo from `station.station_art_path`; fallback `audio-x-generic-symbolic.svg` (added this phase).

**Now-playing panel:**
- **D-05:** 3-column `QHBoxLayout`: [180×180 logo | center stretch | 160×160 cover]. Center column is `QVBoxLayout`: `Name · Provider` / ICY title / elapsed / control row.
- **D-06:** `QSplitter(Qt.Horizontal)` 30/70 left/right. Not persisted across restarts.
- **D-07:** Control row contains ONLY play/pause, stop, volume. Star/edit/stream-picker ABSENT this phase (not placeholder spacers — cleaner diff).
- **D-08:** `QSlider(Qt.Horizontal)` 0–100, initial from `repo.get_setting("volume", 80)`, `NoTicks`, width ~120px. `valueChanged` → `player.set_volume(value/100.0)` + `repo.set_setting("volume", value)`. Tooltip shows percentage.

**Toast overlay:**
- **D-09:** `ToastOverlay(QWidget)` in `musicstreamer/ui_qt/toast.py`. Frameless, bottom-center of `centralWidget()`, `QPropertyAnimation` on `windowOpacity`, auto-dismiss via `QTimer.singleShot`.
- **D-10:** Lives on `MainWindow`. Public API: `show_toast(text, duration_ms=3000)`. `Qt.WA_TransparentForMouseEvents` = True.
- **D-11:** Phase 37 triggers: (a) "Connecting…" on `play()` for a new station, cleared when ICY title arrives; (b) "Stream failed, trying next…" on `failover` with non-None, "Stream exhausted" with None. No other sources.

**Controls scope:**
- **D-12:** Only play/pause, stop, volume. Star → 38, edit → 39, stream picker → 39.
- **D-13:** Play/pause toggles `media-playback-start-symbolic` ↔ `media-playback-pause-symbolic`.
- **D-14:** Stop always `media-playback-stop-symbolic`. `QToolButton` + `setIconSize(QSize(24,24))` + `Qt.ToolButtonIconOnly`.
- **D-15:** `QIcon.fromTheme("name", QIcon(":/icons/name.svg"))` pattern. Four new SVGs this phase: `media-playback-start-symbolic`, `media-playback-pause-symbolic`, `media-playback-stop-symbolic`, `audio-x-generic-symbolic`.

**YouTube thumbnails:**
- **D-16:** `QPixmap.scaled(QSize(160,160), Qt.KeepAspectRatio, Qt.SmoothTransformation)` → letterboxed 160×90 in 160×160 slot.
- **D-17:** Cover slot always 160×160 fixed.

**Player signals → UI slots:**
- **D-18:** All signals connect at MainWindow construction via `Qt.ConnectionType.AutoConnection` (default).
  - `title_changed[str]` → updates ICY label + triggers `_fetch_cover_art_async`
  - `playback_error[str]` → error toast
  - `failover[object]` → "Stream failed, trying next…" or "Stream exhausted"
  - `offline[str]` → "Channel offline" toast
  - `elapsed_updated[int]` → updates elapsed label (`M:SS` / `H:MM:SS`)
- **D-19:** Cover art uses existing `cover_art.fetch_cover_art` — callback wrapped as lambda emitting a new Qt signal `cover_art_ready[str]` on `NowPlayingPanel`, with a `QueuedConnection` slot that runs on the main thread. No modifications to `cover_art.py`.
- **D-20:** `_last_cover_icy` dedup and `last_itunes_result` stay as-is.

**Testing:**
- **D-21:** Four new test files: `test_station_tree_model.py`, `test_now_playing_panel.py`, `test_toast_overlay.py`, `test_main_window_integration.py`.
- **D-22:** `qtbot` + `QT_QPA_PLATFORM=offscreen`. Target ≥ ~280 tests (266 baseline + new).
- **D-23:** `FakePlayer(QObject)` test double exposing the same Signal surface — no real GStreamer.
- **D-24:** UI-SPEC.md exists and is approved — planner MUST consume it.

### Claude's Discretion (Phase 37)
- Exact QSplitter initial ratio (30/70 is suggested — confirmed by UI-SPEC).
- QTreeView styling (UI-SPEC resolves: Qt-native flat, no QSS override except toast).
- Elapsed timer visible format (UI-SPEC pins: `M:SS` / `H:MM:SS`).
- Toast timings (UI-SPEC pins: 150ms fade-in / 3000ms hold / 300ms fade-out).
- Station row height (UI-SPEC pins: 40px).
- Keyboard shortcuts: leave to Qt focus defaults.
- Whether Recently Played is second QTreeView / QListView / custom stack — **recommendation below**.
- Whether absent star/edit slots leave an inline comment — **recommended: yes, minimal comment with target phase**.

### Deferred Ideas (OUT OF SCOPE for Phase 37)
- Search box / filter chips → Phase 38
- Favorites toggle view + star wiring → Phase 38
- EditStationDialog + edit icon → Phase 39
- Stream picker dropdown → Phase 39
- Discovery / Import dialogs → Phase 39
- AccountsDialog, YT cookies, accent color, hamburger menu actions → Phase 40
- Window geometry persistence → deferred (Phase 36 D-02 precedent)
- Keyboard shortcuts phase → later QoL
- Drag-to-reorder / right-click context menu → post-v2.0

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | Station list — provider groups, recently-played, per-row logo, click-to-play | Architecture Patterns §1 (QAbstractItemModel skeleton), §2 (QTreeView config), §4 (RecentlyPlayed choice), Code Examples §1, §2 |
| UI-02 | Now-playing panel — logo, Name·Provider, ICY, cover, elapsed, volume, (+star/edit/play/pause/stop; star/edit deferred per D-07) | Architecture Patterns §3, §5 (cover art adapter), §6 (volume persistence), Code Examples §3, §4 |
| UI-12 | Toast overlay — custom ToastOverlay, used for failover/connecting/errors | Architecture Patterns §7 (QPropertyAnimation), §8 (toast parenting/positioning), Code Examples §5 |
| UI-14 | YouTube 16:9 pre-scaled pixmap in fixed slot (no sizing regression) | D-16/D-17 + Code Examples §4 (QPixmap.scaled with KeepAspectRatio) |

## Project Constraints (from CLAUDE.md)

No `./CLAUDE.md` in project root. Global `~/.claude/CLAUDE.md` applies (terse communication, tight scope, no feature creep). No project-local skills directory.

## Standard Stack

### Core (already installed — verified in repo)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | 6.11.0 | Qt6 widgets, signals, MVC, animations | [VERIFIED: `.venv` query] Established Phase 35; Qt is the porting target per PORT-03 |
| pytest-qt | (installed) | `qtbot` fixture, offscreen test harness | [VERIFIED: `.venv` query] Established Phase 35/36 (QA-01) |

### Supporting (existing — consumed as-is)

| Module | Purpose | Notes |
|--------|---------|-------|
| `musicstreamer.player.Player` | QObject with all signals | [VERIFIED: player.py read] Consume only — do not modify. Thread-safe by design (queued connections). |
| `musicstreamer.repo.Repo` | `list_stations`, `list_recently_played`, `list_streams`, `get_setting`, `set_setting` | [VERIFIED: repo.py read] Single `sqlite3.Connection` per Repo instance — NOT thread-safe; must be called from UI thread only. See Pitfall §3. |
| `musicstreamer.cover_art.fetch_cover_art` | Worker-thread iTunes fetcher with callback | [VERIFIED: cover_art.py read] No changes — callback wrapping happens at the call site. |
| `musicstreamer.models` | `Station`, `StationStream` dataclasses | [VERIFIED] Unchanged. |

### No new dependencies
This phase adds zero pip packages. All required Qt classes ship with PySide6.

**Installation verification:**
```bash
.venv/bin/python -c "import PySide6; print(PySide6.__version__)"   # 6.11.0
```

## Architecture Patterns

### §1: `StationTreeModel(QAbstractItemModel)` — two-level hierarchy

**The core challenge:** A `QAbstractItemModel` with mixed node types (synthetic provider headers + real Station rows). The standard idiom is a lightweight internal `TreeNode` class that holds `kind` ("provider" | "station"), a parent pointer, children list, and the underlying payload.

**Required methods:** `index`, `parent`, `rowCount`, `columnCount`, `data(role)`, `flags`, `headerData` (optional). `index()` must return a `QModelIndex` whose `internalPointer()` is the child node. `parent()` must look up the parent of the node behind `internalPointer()`.

**Selection semantics (D-03):** Override `flags()` — return `Qt.ItemIsEnabled | Qt.ItemIsSelectable` for station rows; return `Qt.ItemIsEnabled` only (NO `Selectable`) for provider group rows. Result: clicking a provider header expands/collapses but does not emit `selectionChanged`.

**Source:** [CITED: https://doc.qt.io/qtforpython-6/PySide6/QtCore/QAbstractItemModel.html]

### §2: `QTreeView` configuration

Standard config (set once at construction):

```python
view.setModel(model)
view.setHeaderHidden(True)                     # no column header row
view.setRootIsDecorated(False)                 # remove the expand-arrow indent column
view.setIndentation(16)                        # tighter than default 20
view.setUniformRowHeights(True)                # perf — constant 40px rows
view.setIconSize(QSize(32, 32))                # D-04 per-row logo
view.setExpandsOnDoubleClick(True)             # default, explicit for clarity
view.expandAll()                               # D-03 — expand all on load (no state persistence)
view.setSelectionBehavior(QAbstractItemView.SelectRows)
view.setSelectionMode(QAbstractItemView.SingleSelection)
view.clicked.connect(self._on_station_clicked)   # D-03 — click-to-play
view.doubleClicked.connect(self._on_station_clicked)  # D-03 — same as click
```

**Keyboard nav** is free — arrow keys walk the tree, Enter triggers the row. No extra code.

**Expand-all-on-load vs remember state:** Expand all on load. State persistence is deferred (Phase 36 D-02 precedent). `[CITED: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QTreeView.html]`

### §3: `NowPlayingPanel(QWidget)` layout

The panel is a `QWidget` owning: `_player_ref` (Player), `_station` (Station | None), `_cover_fetch_token` (int, monotonically incremented to dedupe stale worker results — the existing `_last_cover_icy` pattern ported).

Child widgets (all fixed or stretch per UI-SPEC):

```python
self.logo_label = QLabel()           # 180x180 fixed
self.logo_label.setFixedSize(180, 180)
self.logo_label.setAlignment(Qt.AlignCenter)

self.name_provider_label = QLabel()  # 9pt, "Name · Provider"
self.icy_label = QLabel()            # 13pt DemiBold, ICY title
self.elapsed_label = QLabel("0:00")  # 10pt TypeWriter

self.play_pause_btn = QToolButton()
self.play_pause_btn.setIconSize(QSize(24, 24))
self.play_pause_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
self.play_pause_btn.setFixedSize(36, 36)

self.stop_btn = QToolButton()  # same shape

self.volume_slider = QSlider(Qt.Horizontal)
self.volume_slider.setRange(0, 100)
self.volume_slider.setFixedWidth(120)
self.volume_slider.setTickPosition(QSlider.NoTicks)

self.cover_label = QLabel()          # 160x160 fixed
self.cover_label.setFixedSize(160, 160)
self.cover_label.setAlignment(Qt.AlignCenter)
```

### §4: RecentlyPlayedSection — recommendation

**Recommendation:** `QListView` with a tiny custom `QStyledItemDelegate` for the 40px row height + 32px logo + name layout, backed by a simple `QStandardItemModel`. Reasons:
1. Simpler than a second full `QAbstractItemModel` subclass.
2. Qt-native (unlike a custom stack of 3 row widgets, which means re-implementing selection/focus/keyboard nav).
3. Row height set via delegate `sizeHint()` — 4 lines of code.
4. Model is re-populated on every MainWindow construction via `repo.list_recently_played(3)` — no dynamic refresh needed this phase (no play event yet wires back into the list — station's `last_played_at` is updated by `repo.update_last_played` but the recently-played section does not auto-refresh until the next app launch; this is acceptable per D-02 scope and matches v1.5 behavior).

Click handler: same as the station tree — calls `player.play(station)` via the parent MainWindow.

### §5: Cover art Qt-signal adapter

The existing `fetch_cover_art(icy_string, callback)` invokes `callback(path_or_None)` on a worker thread. To marshal that onto the Qt main thread:

```python
# Inside NowPlayingPanel
cover_art_ready = Signal(str)   # empty string == "no cover"

def __init__(...):
    ...
    # QueuedConnection forces the slot to run on the owning thread even when
    # the signal is emitted from a non-Qt worker thread.
    self.cover_art_ready.connect(self._on_cover_art_ready, Qt.ConnectionType.QueuedConnection)

def _fetch_cover_art_async(self, icy_title: str) -> None:
    token = self._cover_fetch_token = self._cover_fetch_token + 1
    def _cb(path_or_none):
        # Runs on worker thread — emit ONLY. No widget access.
        self.cover_art_ready.emit(path_or_none or "")
    fetch_cover_art(icy_title, _cb)

def _on_cover_art_ready(self, path: str) -> None:
    # Main thread — safe to touch widgets.
    if not path:
        self._show_station_logo_in_cover_slot()
        return
    pix = QPixmap(path).scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    self.cover_label.setPixmap(pix)
```

**Signal lives on `NowPlayingPanel`, not `MainWindow`** — because the panel owns the cover slot and the dedup token. `MainWindow` just forwards `player.title_changed` into `NowPlayingPanel._on_title_changed`, which then calls `_fetch_cover_art_async`.

**Source:** [CITED: https://doc.qt.io/qtforpython-6/tutorials/basictutorial/signals_and_slots.html] — QueuedConnection required for cross-thread signal-to-slot dispatch.

### §6: Volume persistence

`repo.get_setting(key, default)` returns `str` (see `repo.py:328-332`). `set_setting(key, value)` stores as `str`. So:

```python
stored = repo.get_setting("volume", "80")    # always a str
try:
    initial = int(stored)
except ValueError:
    initial = 80
self.volume_slider.setValue(initial)
player.set_volume(initial / 100.0)
# ...
self.volume_slider.valueChanged.connect(self._on_volume_changed_live)   # live audio
self.volume_slider.sliderReleased.connect(self._on_volume_released)     # persistence

def _on_volume_changed_live(self, value: int) -> None:
    self.player.set_volume(value / 100.0)
    self.volume_slider.setToolTip(f"Volume: {value}%")

def _on_volume_released(self) -> None:
    self.repo.set_setting("volume", str(self.volume_slider.value()))
```

**Why split live vs persist:** `valueChanged` fires on every pixel while dragging — persisting on every tick is wasteful SQLite writes. `sliderReleased` fires once when the user lets go. Also call `set_setting` from `valueChanged` only when the change was by keyboard (no release event) — simplest fix is to also persist in a zero-delay `QTimer.singleShot(250, ...)` debounce triggered from `valueChanged`. **Recommended: start with `sliderReleased`-only; if keyboard adjust turns out to matter, add debounced persist in a follow-up.**

### §7: `QPropertyAnimation` on `windowOpacity` for toast

```python
self._fade_in  = QPropertyAnimation(self, b"windowOpacity", self)
self._fade_in.setDuration(150)
self._fade_in.setStartValue(0.0)
self._fade_in.setEndValue(1.0)

self._fade_out = QPropertyAnimation(self, b"windowOpacity", self)
self._fade_out.setDuration(300)
self._fade_out.setStartValue(1.0)
self._fade_out.setEndValue(0.0)
self._fade_out.finished.connect(self.hide)

self._hold_timer = QTimer(self)
self._hold_timer.setSingleShot(True)
self._hold_timer.timeout.connect(self._fade_out.start)

def show_toast(self, text: str, duration_ms: int = 3000) -> None:
    if self._fade_out.state() == QAbstractAnimation.Running:
        self._fade_out.stop()         # interrupt fade-out if re-showing
    self.label.setText(text)
    self._reposition()                # re-anchor before showing
    self.setWindowOpacity(0.0)
    self.show()
    self.raise_()
    self._fade_in.start()
    self._hold_timer.start(duration_ms)
```

**Pitfall — re-show during fade-out:** Starting `_fade_in` while `_fade_out` is still running causes a flicker. The guard `if self._fade_out.state() == Running: stop()` handles it. `[CITED: https://doc.qt.io/qtforpython-6/PySide6/QtCore/QPropertyAnimation.html]`

**Pitfall — `Qt.WA_DeleteOnClose`:** Do NOT set `WA_DeleteOnClose` on the toast. The overlay is owned by the MainWindow parent and reused for every toast — deleting on close would crash on the next `show_toast` call. Parent ownership is the safer lifetime model.

### §8: Toast parenting and positioning

```python
class ToastOverlay(QWidget):
    def __init__(self, parent: QWidget) -> None:
        # No Qt.Window flag — we want it to be a child widget of centralWidget,
        # not a top-level window. Frameless visual comes from the QSS on the
        # inner QLabel.
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(self)
        self.label.setObjectName("ToastLabel")   # QSS hook
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel#ToastLabel {
                background-color: rgba(40, 40, 40, 220);
                color: white;
                border-radius: 8px;
                padding: 8px 12px;
            }
        """)
        layout.addWidget(self.label)
        self.hide()
        parent.installEventFilter(self)   # catch parent resize events

    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() == QEvent.Resize:
            self._reposition()
        return super().eventFilter(obj, event)

    def _reposition(self) -> None:
        parent = self.parent()
        if parent is None:
            return
        self.adjustSize()
        max_w = min(parent.width() - 64, 480)
        self.setFixedWidth(max(240, min(max_w, self.sizeHint().width())))
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - 32
        self.move(x, y)
```

**Notes:**
- Parent is `MainWindow.centralWidget()` — toast is always inside the central area, never over the status bar.
- `installEventFilter(parent)` + `QEvent.Resize` is the idiomatic way to re-anchor on parent resize without subclassing the parent. `[CITED: https://doc.qt.io/qtforpython-6/PySide6/QtCore/QObject.html#PySide6.QtCore.QObject.installEventFilter]`
- The toast widget itself is transparent for mouse events — clicks pass through. Anti-pattern: forgetting this would block the volume slider if the toast covers it (unlikely given bottom-center placement, but D-10 mandates it).

### §9: Signal wiring — who owns Player

**Recommendation:** `MainWindow` owns the single `Player()` instance (construct it in `MainWindow.__init__`, after the repo, before the panels). Pass the Player as a constructor argument to `NowPlayingPanel` and `StationListPanel`. This is the simplest ownership model — no module-level singletons.

```python
# main_window.py
class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._con = db_connect()
        db_init(self._con)
        self._repo = Repo(self._con)
        self._player = Player(parent=self)   # parent-owned — cleaned up on window close
        # ...
        self.station_panel = StationListPanel(self._repo, parent=self)
        self.now_playing = NowPlayingPanel(self._player, self._repo, parent=self)
        self.toast_overlay = ToastOverlay(self.centralWidget())

        # D-18: direct signal wiring to NowPlayingPanel slots (not forwarding through MainWindow)
        self._player.title_changed.connect(self.now_playing.on_title_changed)
        self._player.elapsed_updated.connect(self.now_playing.on_elapsed_updated)
        self._player.failover.connect(self._on_failover)         # toast — MainWindow slot
        self._player.playback_error.connect(self._on_playback_error)
        self._player.offline.connect(self._on_offline)

        # StationListPanel click-to-play → route to player
        self.station_panel.station_activated.connect(self._on_station_activated)

    def _on_station_activated(self, station: Station) -> None:
        self.toast_overlay.show_toast("Connecting\u2026")
        self._player.play(station)
        self._repo.update_last_played(station.id)
        self.now_playing.bind_station(station)

    def _on_failover(self, stream) -> None:
        if stream is None:
            self.toast_overlay.show_toast("Stream exhausted")
        else:
            self.toast_overlay.show_toast("Stream failed, trying next\u2026")

    def _on_playback_error(self, msg: str) -> None:
        trimmed = msg if len(msg) <= 80 else msg[:79] + "\u2026"
        self.toast_overlay.show_toast(f"Playback error: {trimmed}")

    def _on_offline(self, channel: str) -> None:
        self.toast_overlay.show_toast("Channel offline")
```

Why MainWindow owns Player and NOT NowPlayingPanel: station-click comes from the StationListPanel, which needs a reference to Player — MainWindow is the natural arbiter. Also, toasts live on MainWindow and need to respond to failover, so failover signal must reach MainWindow anyway.

### §10: QPixmap loading + caching for station rows

`QPixmap(path)` works directly on a file path — no need for `QImage + fromImage` unless you need pixel-level access first. The station row logos are 32×32, so load + scale once and cache.

**`QPixmapCache` + `DecorationRole`:**

```python
from PySide6.QtGui import QPixmapCache

def data(self, index, role):
    if role == Qt.DecorationRole:
        node = index.internalPointer()
        if node.kind != "station":
            return None
        path = node.station.station_art_path or ":/icons/audio-x-generic-symbolic.svg"
        key = f"station-logo:{path}"
        pix = QPixmap()
        if not QPixmapCache.find(key, pix):
            pix = QPixmap(path).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            QPixmapCache.insert(key, pix)
        return QIcon(pix)
```

`QPixmapCache` is process-global and has a default 10MB cache — plenty for 200 32×32 station logos. `[CITED: https://doc.qt.io/qtforpython-6/PySide6/QtGui/QPixmapCache.html]`

**Caveat:** `station.station_art_path` is typically an absolute filesystem path (per `assets.py`). If the file is missing, `QPixmap(path)` returns a null pixmap silently — check `pix.isNull()` and substitute the resource-backed fallback. Code Examples §2 shows the guarded version.

### §11: Resize handling — splitter + panel collapse

`QSplitter` handles narrowing automatically as long as both panels have sensible `setMinimumWidth`:

- Station list panel: `setMinimumWidth(280)` (UI-SPEC)
- Now-playing panel: `setMinimumWidth(560)` (UI-SPEC)

Initial sizes via `splitter.setSizes([360, 840])` (roughly 30/70 of 1200 default width), and `setStretchFactor(0, 0)` + `setStretchFactor(1, 1)` so the now-playing panel takes growth. The 3-column layout inside NowPlayingPanel does NOT need a secondary responsive breakpoint this phase — the center column stretches, the two fixed columns stay fixed, and below ~560px the window cannot narrow further.

### §12: Icon theme fallback on Linux without `adwaita-icon-theme`

`QIcon.fromTheme("name", QIcon(":/icons/name.svg"))` uses the second arg as a fallback **only when the theme lookup returns a null icon**. On most Linux distros with any desktop environment installed, the call succeeds from the system theme. On truly bare systems (minimal Docker containers, some WMs, offscreen test harness), the theme is empty and the fallback kicks in.

Phase 36 already verified this pattern works end-to-end (`test_fromtheme_fallback_uses_bundled_svg` — see 36-VERIFICATION.md line 25). Phase 37 tests follow the same pattern for the four new SVGs.

**Test for Phase 37:** One parameterized test per new icon name asserting `QIcon.fromTheme("nonexistent", QIcon(":/icons/name.svg")).isNull() is False`. Same pattern as Phase 36 PORT-08 test.

### Anti-Patterns to Avoid

- **Constructing QTimer from a non-owning thread** (already handled by conftest stub for Player, but relevant if any new background worker is added).
- **Holding a QPixmap on a non-GUI thread** — QPixmap is not thread-safe. Worker threads must pass file paths or `QByteArray`, never `QPixmap` instances.
- **Setting `Qt.WA_DeleteOnClose` on the toast** — see §7.
- **Forgetting to disconnect signals in widget destructors** — QA-05 risk. Qt's parent ownership handles most cases, but when connecting `player.X.connect(panel.Y)`, if the panel is destroyed before the player, Qt auto-disconnects (the slot target is gone). If the player is destroyed first, the panel's connection is also cleaned up. The danger is **lambda slots** that capture `self` — these can keep the target alive. Prefer bound methods (`self.player.title_changed.connect(self.now_playing.on_title_changed)`) over lambdas wherever possible.
- **Calling `repo.py` methods from a worker thread** — the sqlite3.Connection is not thread-safe. See Pitfall §3.
- **Reading `station.station_art_path` without null-checking** — it can be None. Fallback to the bundled `audio-x-generic-symbolic.svg` resource path.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tree widget with grouping | Custom QWidget stack of collapsible sections | `QTreeView` + `QAbstractItemModel` | Qt handles selection, keyboard nav, expand state, scrolling, row rendering — all free |
| Row logo caching | Per-row QPixmap reload on redraw | `QPixmapCache` (process-global LRU, 10MB default) | One-liner, handles memory budget automatically |
| Fade animation | QTimer + manual opacity ticks | `QPropertyAnimation` on `windowOpacity` | Proper easing, interruption, finished signal |
| Toast positioning on parent resize | Parent subclass override | `installEventFilter` + `QEvent.Resize` | Non-invasive; works for any parent |
| Signal marshaling from worker thread | Queue + QTimer poll | Emit a `Signal` with `Qt.QueuedConnection` | Qt auto-marshals; no boilerplate |
| Cross-thread cover art callback | GLib.idle_add port | Wrap callback as lambda emitting a Qt Signal | Same pattern established in `player.py` for `twitch_resolved`/`youtube_resolved` |
| Elapsed timer tick | Custom QThread | Use `player.elapsed_updated[int]` signal | Already exists in Phase 35 Player |

**Key insight:** Every widget this phase needs is either a stock Qt class or a ~50-line subclass. The complexity lives in signal wiring, not custom painting.

## Runtime State Inventory

Not applicable — this is a greenfield widget phase, not a rename/refactor. No stored data, OS registrations, or installed packages reference anything that changes this phase. The only state-touching operations are:

- `repo.set_setting("volume", N)` — writes to `settings` table (additive; key may or may not already exist from v1.5 data migrated by Phase 35 PORT-06).
- `repo.update_last_played(station_id)` — writes `stations.last_played_at` (additive; already used by v1.5).

Neither is a migration — both are normal runtime writes that v1.5 already performed.

## Common Pitfalls

### §1: Constructing QObject children before `QApplication.exec()`
**What goes wrong:** Signal-slot connections made before the event loop runs can silently drop queued events if any emitter runs on a non-GUI thread before `exec()` starts.
**Why it happens:** Queued connections require an event loop.
**How to avoid:** All panel construction happens synchronously inside `MainWindow.__init__`, and `player.play(...)` is never called before `app.exec()`. Phase 35 already established this discipline with `QTimer.singleShot(0, lambda: player.play(...))` in the smoke harness.
**Warning signs:** Title labels not updating on first play; cover art ready signal appears to be emitted but slot never runs.

### §2: Lambda slots leaking widget references
**What goes wrong:** `signal.connect(lambda x: self.do_thing(x))` captures `self` in a closure. When the widget is destroyed, the lambda keeps a dangling C++ reference, and the next signal emission raises `RuntimeError: Internal C++ object already deleted`.
**Why it happens:** PySide6 can't automatically disconnect lambda slots — they're ordinary Python callables.
**How to avoid:** Use bound methods (`signal.connect(self.do_thing)`) whenever possible. Bound methods are tracked by PySide6 and auto-disconnected on parent destruction. For lambdas that are unavoidable, explicitly disconnect in `closeEvent` or use `functools.partial` stored as an instance attribute so it can be disconnected.
**Warning signs:** `RuntimeError: Internal C++ object already deleted` in tests that construct-and-destroy widgets repeatedly (QA-05 gate).

### §3: `repo.py` thread safety
**What goes wrong:** Calling `repo.list_stations()` from a worker thread raises `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`.
**Why it happens:** `db_connect()` creates a connection without `check_same_thread=False`. [VERIFIED: repo.py:8-12] The connection is implicitly bound to the creating thread.
**How to avoid:** Only call Repo methods from the Qt main (UI) thread. Cover art, YouTube resolution, Twitch resolution, GStreamer bus callbacks — NONE of these touch `repo`. If Phase 38+ needs background DB access, it must either (a) create a separate connection per thread, or (b) marshal the call through a Qt signal to the main thread.
**Warning signs:** `sqlite3.ProgrammingError` on playback-error paths. For Phase 37, this shouldn't happen because every repo call is main-thread (station list population, volume persist, recently-played refresh).

### §4: QAbstractItemModel `parent()` infinite recursion
**What goes wrong:** Incorrect parent pointer handling returns the child itself, causing Qt to walk up forever on `expandAll()`.
**Why it happens:** Hand-rolled tree model where `parent()` returns `index()` on a top-level node instead of an invalid `QModelIndex()`.
**How to avoid:** Top-level nodes (provider groups) MUST return `QModelIndex()` (the invisible root) from `parent()`. Station rows return a `QModelIndex` pointing at their provider group.
**Warning signs:** Hang / stack overflow on `view.expandAll()`. Hard to spot without a unit test — `test_station_tree_model.py` should explicitly assert `model.parent(model.index(0, 0)).isValid() is False`.

### §5: Pixmap cache miss pattern is subtle
**What goes wrong:** `QPixmapCache.find(key)` returns a bool AND a pixmap out-parameter. The Python binding uses a two-arg form: `find(key, pixmap)`. Forgetting to check the return value leads to always-miss and no caching.
**How to avoid:** Code Examples §2 shows the correct idiom.
**Warning signs:** Scrolling the station list feels the same speed with and without the cache — suggests cache is never hit.

### §6: `QPropertyAnimation` target object deletion
**What goes wrong:** Creating `QPropertyAnimation(target)` without a parent — if the animation's Python reference goes out of scope, it's garbage-collected mid-flight and the fade silently freezes.
**How to avoid:** Pass `self` as the animation's parent: `QPropertyAnimation(self, b"windowOpacity", self)`. The third arg makes the animation a child of the toast widget — Qt keeps it alive as long as the toast exists.
**Warning signs:** Toast appears but never fades out, or fades out once and never again after the first animation object is GC'd.

### §7: `setHeaderHidden(True)` doesn't remove the column
**What goes wrong:** Even with the header hidden, `QTreeView` still renders columns. If the model reports `columnCount() > 1`, extra columns waste horizontal space.
**How to avoid:** `columnCount()` returns `1` from `StationTreeModel`. Always.
**Warning signs:** Station rows have weird trailing whitespace.

## Code Examples

### §1: `StationTreeModel` skeleton

```python
# musicstreamer/ui_qt/station_tree_model.py
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtGui import QIcon, QPixmap, QPixmapCache

from musicstreamer.models import Station


@dataclass
class _TreeNode:
    kind: str                          # "provider" or "station"
    label: str
    parent: Optional["_TreeNode"] = None
    children: list["_TreeNode"] = field(default_factory=list)
    station: Optional[Station] = None  # set when kind == "station"


class StationTreeModel(QAbstractItemModel):
    """Provider-grouped station list. Two-level tree:
    root (invisible) → provider groups → station rows.
    """

    FALLBACK_ICON = ":/icons/audio-x-generic-symbolic.svg"

    def __init__(self, stations: list[Station], parent=None) -> None:
        super().__init__(parent)
        self._root = _TreeNode(kind="root", label="")
        self._populate(stations)

    def refresh(self, stations: list[Station]) -> None:
        self.beginResetModel()
        self._root = _TreeNode(kind="root", label="")
        self._populate(stations)
        self.endResetModel()

    def _populate(self, stations: list[Station]) -> None:
        groups: dict[str, _TreeNode] = {}
        for st in stations:
            pname = st.provider_name or "Ungrouped"
            grp = groups.get(pname)
            if grp is None:
                grp = _TreeNode(kind="provider", label=pname, parent=self._root)
                self._root.children.append(grp)
                groups[pname] = grp
            grp.children.append(
                _TreeNode(kind="station", label=st.name, parent=grp, station=st)
            )
        # Add count suffix to provider labels (D-04)
        for grp in self._root.children:
            grp.label = f"{grp.label} ({len(grp.children)})"

    def station_for_index(self, index: QModelIndex) -> Optional[Station]:
        if not index.isValid():
            return None
        node: _TreeNode = index.internalPointer()
        return node.station if node.kind == "station" else None

    # --- Required QAbstractItemModel overrides ---

    def columnCount(self, parent=QModelIndex()) -> int:
        return 1

    def rowCount(self, parent=QModelIndex()) -> int:
        if not parent.isValid():
            return len(self._root.children)
        node: _TreeNode = parent.internalPointer()
        return len(node.children)

    def index(self, row, column, parent=QModelIndex()) -> QModelIndex:
        if column != 0:
            return QModelIndex()
        parent_node = parent.internalPointer() if parent.isValid() else self._root
        if row < 0 or row >= len(parent_node.children):
            return QModelIndex()
        return self.createIndex(row, 0, parent_node.children[row])

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        node: _TreeNode = index.internalPointer()
        parent_node = node.parent
        if parent_node is None or parent_node is self._root:
            return QModelIndex()
        grandparent = parent_node.parent or self._root
        row = grandparent.children.index(parent_node)
        return self.createIndex(row, 0, parent_node)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        node: _TreeNode = index.internalPointer()
        if node.kind == "station":
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable
        return Qt.ItemIsEnabled  # provider groups: not selectable

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        node: _TreeNode = index.internalPointer()
        if role == Qt.DisplayRole:
            return node.label
        if role == Qt.DecorationRole and node.kind == "station":
            return self._icon_for_station(node.station)
        if role == Qt.FontRole and node.kind == "provider":
            from PySide6.QtGui import QFont
            f = QFont()
            f.setBold(True)
            f.setPointSize(13)   # UI-SPEC: 13pt DemiBold for group headers
            return f
        return None

    def _icon_for_station(self, station: Station) -> QIcon:
        path = station.station_art_path or self.FALLBACK_ICON
        key = f"station-logo:{path}"
        pix = QPixmap()
        if not QPixmapCache.find(key, pix):
            pix = QPixmap(path)
            if pix.isNull():
                pix = QPixmap(self.FALLBACK_ICON)
            pix = pix.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            QPixmapCache.insert(key, pix)
        return QIcon(pix)
```

### §2: `StationListPanel` with the tree and click-to-play

```python
# musicstreamer/ui_qt/station_list_panel.py
from PySide6.QtCore import QModelIndex, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QLabel, QTreeView, QVBoxLayout, QWidget,
)

from musicstreamer.models import Station
from musicstreamer.repo import Repo
from musicstreamer.ui_qt.station_tree_model import StationTreeModel


class StationListPanel(QWidget):
    station_activated = Signal(Station)   # emitted on click-to-play

    def __init__(self, repo: Repo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo
        self.setMinimumWidth(280)   # UI-SPEC

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(0)

        # Recently Played section
        recent_label = QLabel("Recently Played")
        recent_label.setContentsMargins(16, 0, 16, 4)
        layout.addWidget(recent_label)
        # ... RecentlyPlayedSection (QListView + QStandardItemModel + delegate)
        # populates from self._repo.list_recently_played(3)
        # emits self.station_activated on row click

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        # Main station tree
        self.tree = QTreeView()
        self.model = StationTreeModel(self._repo.list_stations())
        self.tree.setModel(self.model)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(16)
        self.tree.setUniformRowHeights(True)
        self.tree.setIconSize(QSize(32, 32))
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.expandAll()
        self.tree.clicked.connect(self._on_activated)
        self.tree.doubleClicked.connect(self._on_activated)
        layout.addWidget(self.tree, stretch=1)

    def _on_activated(self, index: QModelIndex) -> None:
        station = self.model.station_for_index(index)
        if station is not None:
            self.station_activated.emit(station)
```

### §3: `NowPlayingPanel` construction + signal handlers (abbreviated)

```python
# musicstreamer/ui_qt/now_playing_panel.py — essential slots
def on_title_changed(self, title: str) -> None:
    self.icy_label.setText(title)
    # Clear "Connecting…" toast — ICY title means audio is flowing
    # (handled by MainWindow watching this signal too? — simpler to just call panel.on_title_changed
    #  from MainWindow and let MainWindow hide its own toast via QTimer after a short delay)
    if not is_junk_title(title) and self._station is not None:
        self._fetch_cover_art_async(title)

def on_elapsed_updated(self, seconds: int) -> None:
    if seconds < 3600:
        self.elapsed_label.setText(f"{seconds // 60}:{seconds % 60:02d}")
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        self.elapsed_label.setText(f"{h}:{m:02d}:{s:02d}")

def bind_station(self, station: Station) -> None:
    self._station = station
    self.name_provider_label.setText(
        f"{station.name} \u00B7 {station.provider_name}" if station.provider_name else station.name
    )
    self.icy_label.setText("")
    self._show_station_logo()
    self._show_station_logo_in_cover_slot()   # fallback until iTunes lookup returns
```

### §4: YouTube thumbnail in 160×160 cover slot (D-16)

```python
def _set_cover_pixmap(self, path: str) -> None:
    pix = QPixmap(path)
    if pix.isNull():
        self._show_station_logo_in_cover_slot()
        return
    scaled = pix.scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    self.cover_label.setPixmap(scaled)
    # KeepAspectRatio letterboxes a 16:9 source to 160x90 inside the 160x160 QLabel
    # The label's setAlignment(Qt.AlignCenter) centers the resulting pixmap.
```

### §5: ToastOverlay full implementation

See §7 (animation) and §8 (parenting) combined into `musicstreamer/ui_qt/toast.py`:

```python
from PySide6.QtCore import (
    QAbstractAnimation, QEvent, QPropertyAnimation, QTimer, Qt,
)
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ToastOverlay(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(self)
        self.label.setObjectName("ToastLabel")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "QLabel#ToastLabel {"
            " background-color: rgba(40, 40, 40, 220);"
            " color: white;"
            " border-radius: 8px;"
            " padding: 8px 12px;"
            "}"
        )
        layout.addWidget(self.label)

        self._fade_in = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_in.setDuration(150)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)

        self._fade_out = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_out.setDuration(300)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.finished.connect(self.hide)

        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._fade_out.start)

        self.hide()
        parent.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() == QEvent.Resize:
            self._reposition()
        return super().eventFilter(obj, event)

    def show_toast(self, text: str, duration_ms: int = 3000) -> None:
        if self._fade_out.state() == QAbstractAnimation.Running:
            self._fade_out.stop()
        self._hold_timer.stop()
        self.label.setText(text)
        self.adjustSize()
        self._reposition()
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._fade_in.start()
        self._hold_timer.start(duration_ms)

    def _reposition(self) -> None:
        parent = self.parent()
        if parent is None:
            return
        self.adjustSize()
        hint = self.sizeHint().width()
        max_w = min(parent.width() - 64, 480)
        width = max(240, min(max_w, hint))
        self.setFixedWidth(width)
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - 32
        self.move(x, y)
```

### §6: `FakePlayer` test double (D-23)

```python
# tests/test_now_playing_panel.py — top-of-file helper
from PySide6.QtCore import QObject, Signal


class FakePlayer(QObject):
    """Mirrors the Player signal surface without any GStreamer pipeline."""
    title_changed   = Signal(str)
    failover        = Signal(object)
    offline         = Signal(str)
    playback_error  = Signal(str)
    elapsed_updated = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.play_calls = []
        self.set_volume_calls = []
        self.stop_calls = 0
        self.pause_calls = 0

    def play(self, station, on_title=None, preferred_quality="",
             on_failover=None, on_offline=None) -> None:
        self.play_calls.append((station, preferred_quality))

    def set_volume(self, v: float) -> None:
        self.set_volume_calls.append(v)

    def pause(self) -> None:
        self.pause_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1
```

Tests emit signals programmatically: `fake_player.title_changed.emit("Artist - Track")` and assert `panel.icy_label.text() == "Artist - Track"`. `pytest-qt`'s `qtbot.waitSignal(signal, timeout=500)` works against any `QObject` subclass, not just the real Player — this is the key insight that makes the fake double work.

## State of the Art

| Old Approach (v1.5 GTK) | Current Approach (v2.0 Qt) | Impact |
|-------------------------|----------------------------|--------|
| `Gtk.TreeView` + `Gtk.TreeStore` | `QTreeView` + `QAbstractItemModel` | Native Qt MVC; cleaner for Phase 38 filter proxy |
| `Gtk.Image.set_from_file` | `QLabel.setPixmap(QPixmap(path).scaled(...))` | Direct file loading; scaling is a one-liner |
| `GLib.idle_add(callback)` | `Signal.emit()` with QueuedConnection | Unified cross-thread dispatch |
| `Adw.Toast` | Custom `ToastOverlay(QWidget)` | Qt has no built-in toast; custom is required (UI-12) |
| GTK CSS (`.css` file + `Adw.StyleManager`) | Qt native palette + targeted QSS | UI-SPEC: Qt-native flat, QSS only for toast |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| PySide6 | All widgets | ✓ | 6.11.0 | — |
| pytest-qt | Widget tests | ✓ | installed | — |
| Qt offscreen platform | Headless tests | ✓ | bundled in PySide6 | — |
| adwaita-icon-theme (host) | Icon theme on Linux | varies | — | Bundled SVGs via `:/icons/` — Phase 36 pattern |
| Network (iTunes Search API) | Cover art fetch at runtime | — | — | `fetch_cover_art` calls `callback(None)` on failure; panel shows station logo in cover slot |

No blocking missing dependencies. All Phase 37 code paths have graceful degradation (missing station art → fallback icon; missing iTunes result → station logo; missing adwaita theme → bundled SVG).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-qt + PySide6 6.11.0 |
| Config file | `tests/conftest.py` (sets `QT_QPA_PLATFORM=offscreen`, stubs bus bridge) |
| Quick run command | `.venv/bin/pytest tests/test_station_tree_model.py tests/test_now_playing_panel.py tests/test_toast_overlay.py tests/test_main_window_integration.py -x` |
| Full suite command | `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| UI-01 | StationTreeModel groups by provider | unit | `pytest tests/test_station_tree_model.py::test_provider_grouping` | ❌ Wave 0 |
| UI-01 | StationTreeModel returns correct row counts | unit | `pytest tests/test_station_tree_model.py::test_row_counts` | ❌ Wave 0 |
| UI-01 | Provider group rows are not selectable | unit | `pytest tests/test_station_tree_model.py::test_provider_rows_not_selectable` | ❌ Wave 0 |
| UI-01 | `parent()` on top-level returns invalid index | unit | `pytest tests/test_station_tree_model.py::test_top_level_parent_invalid` | ❌ Wave 0 |
| UI-01 | Per-row logo fallback works when path is None | unit | `pytest tests/test_station_tree_model.py::test_decoration_fallback` | ❌ Wave 0 |
| UI-01 | StationListPanel click emits station_activated | integration | `pytest tests/test_station_tree_model.py::test_station_list_panel_click` | ❌ Wave 0 |
| UI-01 | Recently Played populated from repo | integration | `pytest tests/test_station_tree_model.py::test_recently_played_section` | ❌ Wave 0 |
| UI-02 | NowPlayingPanel ICY label updates on title_changed | integration | `pytest tests/test_now_playing_panel.py::test_icy_title_update` | ❌ Wave 0 |
| UI-02 | NowPlayingPanel elapsed label formats M:SS and H:MM:SS | unit | `pytest tests/test_now_playing_panel.py::test_elapsed_format` | ❌ Wave 0 |
| UI-02 | Play/pause toggles icon | integration | `pytest tests/test_now_playing_panel.py::test_play_pause_icon_toggle` | ❌ Wave 0 |
| UI-02 | Stop button calls player.stop() | integration | `pytest tests/test_now_playing_panel.py::test_stop_button` | ❌ Wave 0 |
| UI-02 | Volume slider initial from repo, persists on release | integration | `pytest tests/test_now_playing_panel.py::test_volume_slider_persistence` | ❌ Wave 0 |
| UI-02 | Cover art ready signal updates pixmap via queued connection | integration | `pytest tests/test_now_playing_panel.py::test_cover_art_signal_adapter` | ❌ Wave 0 |
| UI-02 | Name · Provider format uses U+00B7 | unit | `pytest tests/test_now_playing_panel.py::test_name_provider_separator` | ❌ Wave 0 |
| UI-12 | ToastOverlay.show_toast starts fade-in animation | unit | `pytest tests/test_toast_overlay.py::test_show_starts_fade_in` | ❌ Wave 0 |
| UI-12 | ToastOverlay auto-hides after duration_ms | integration | `pytest tests/test_toast_overlay.py::test_auto_dismiss` | ❌ Wave 0 |
| UI-12 | ToastOverlay re-show interrupts fade-out | unit | `pytest tests/test_toast_overlay.py::test_reshow_during_fade_out` | ❌ Wave 0 |
| UI-12 | ToastOverlay repositions on parent resize | integration | `pytest tests/test_toast_overlay.py::test_reposition_on_parent_resize` | ❌ Wave 0 |
| UI-12 | ToastOverlay is transparent for mouse events | unit | `pytest tests/test_toast_overlay.py::test_mouse_transparent` | ❌ Wave 0 |
| UI-12 | MainWindow shows toast on failover signal | integration | `pytest tests/test_main_window_integration.py::test_failover_shows_toast` | ❌ Wave 0 |
| UI-12 | MainWindow shows "Connecting…" on station activated | integration | `pytest tests/test_main_window_integration.py::test_connecting_toast` | ❌ Wave 0 |
| UI-14 | QPixmap.scaled with KeepAspectRatio on 16:9 source produces 160x90 | unit | `pytest tests/test_now_playing_panel.py::test_youtube_thumbnail_letterbox` | ❌ Wave 0 |
| PORT-08 | 4 new icons load via fromTheme fallback | unit | `pytest tests/test_now_playing_panel.py::test_new_icons_load` | ❌ Wave 0 |
| QA-02 | Full suite remains ≥ 266 + new tests | suite | `.venv/bin/pytest -q` | ✅ existing |
| QA-05 | Widget construct/destroy cycles don't raise RuntimeError | integration | `pytest tests/test_main_window_integration.py::test_widget_lifetime_no_runtime_error` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** targeted test file only (e.g. `pytest tests/test_station_tree_model.py -x`)
- **Per wave merge:** full 4-file phase suite (`pytest tests/test_station_tree_model.py tests/test_now_playing_panel.py tests/test_toast_overlay.py tests/test_main_window_integration.py -x`)
- **Phase gate:** full suite green via `.venv/bin/pytest -q` — target ≥ 266 + N new tests (≥ ~285 expected)

### Wave 0 Gaps
- [ ] `tests/test_station_tree_model.py` — covers UI-01 (model unit + panel integration)
- [ ] `tests/test_now_playing_panel.py` — covers UI-02 + UI-14 + PORT-08 icon tests
- [ ] `tests/test_toast_overlay.py` — covers UI-12 (overlay unit)
- [ ] `tests/test_main_window_integration.py` — covers UI-01..UI-14 integration + QA-05 lifetime check; hosts `FakePlayer` at top of file (or moved to `tests/conftest.py` if reused)
- [ ] Shared fixtures: in-memory Repo with seeded providers/stations/streams (new fixture in `tests/conftest.py` — probably a `tmp_path`-backed temporary SQLite file since `repo.py` uses `paths.db_path()`, monkeypatched via `paths.db_path` to return the tmp path)

Framework: installed. No install step needed.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | — (no auth surface this phase) |
| V3 Session Management | no | — |
| V4 Access Control | no | — (desktop app, single user) |
| V5 Input Validation | partial | ICY titles are user-controlled by remote stations — already sanitized to text by `_fix_icy_encoding` in Phase 35. The `Playback error: {msg}` toast truncates to 80 chars, preventing UI overflow from pathological GStreamer error text. |
| V6 Cryptography | no | — (no crypto in this phase) |

### Known Threat Patterns for Qt desktop widget UI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Untrusted filesystem path in QPixmap | Tampering | `QPixmap(path)` handles malformed files gracefully (returns null); we check `isNull()` [VERIFIED: Qt docs] |
| Untrusted ICY title rendering in QLabel | Tampering | `QLabel` renders plain text by default; we do NOT call `setTextFormat(Qt.RichText)` anywhere — no HTML/script injection surface |
| Long ICY titles causing layout thrash | DoS (UI) | `QFontMetrics.elidedText()` pattern for station rows (noted in CONTEXT canonical_refs); planner should apply to ICY title label too or rely on QLabel word-wrap |
| Error message text injection into toast | Tampering | `f"Playback error: {msg}"` uses plain text formatting; no rich-text parse. 80-char truncation bounds the display cost. |

**Lock-down recommendation:** Explicitly set `self.icy_label.setTextFormat(Qt.PlainText)` and `self.toast.label.setTextFormat(Qt.PlainText)` — belt-and-suspenders against any future refactor accidentally enabling rich text. [CITED: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QLabel.html#PySide6.QtWidgets.QLabel.setTextFormat]

No other threat surfaces relevant to this phase. No network input (cover_art.py uses https to itunes.apple.com with a 5s timeout — existing v1.5 code, unchanged).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `QPixmapCache` default size (10MB) holds ~200 station logos comfortably | Architecture §10 | [ASSUMED] — untested with 200 stations. Mitigation: cache misses fall back to re-loading, which is still fast for 32×32 SVGs. No functional failure, only marginal perf regression. |
| A2 | Lambda slot capture of `self` is the primary QA-05 offender in widget lifetime bugs | Pitfalls §2 | [ASSUMED] based on general Qt/PySide6 community wisdom. Mitigation: test_main_window_integration.py::test_widget_lifetime_no_runtime_error explicitly exercises construct/destroy to detect. |
| A3 | `QTreeView.expandAll()` is cheap enough for ~200 stations at startup | Patterns §2 | [ASSUMED] — untested at scale. Fallback: if construction feels slow, add a single-shot `QTimer.singleShot(0, tree.expandAll)` to defer expansion past the first paint. |
| A4 | `sliderReleased`-only persistence is acceptable (keyboard-driven volume change won't persist without release) | Patterns §6 | [ASSUMED] — user may adjust volume only via mouse, matching v1.5 expectations. Fallback: add a `QTimer.singleShot(250, self._on_volume_released)` debounce in `_on_volume_changed_live`. |
| A5 | `QEvent.Resize` fires on `centralWidget` when MainWindow is resized | Patterns §8 | [ASSUMED] Standard Qt behavior. Test `test_reposition_on_parent_resize` in Wave 0 verifies explicitly by calling `main_window.resize()` and checking toast position. |
| A6 | `fetch_cover_art` callback invocation on a non-Qt thread safely emits a bound-method Qt signal | Patterns §5 | [VERIFIED: Phase 35 established this pattern for `twitch_resolved`/`youtube_resolved` in player.py:381-418 — same idiom, same threading model] |

## Open Questions

1. **Recently Played refresh timing.** Should the Recently Played section update when a station is activated in the current session, or only at app startup?
   - What we know: D-02 says "only on construction" is acceptable.
   - What's unclear: Whether users expect to see the station they just clicked immediately appear at the top of Recently Played.
   - Recommendation: **Startup-only for Phase 37.** Matches v1.5 behavior and D-02 intent. If user feedback demands live refresh, add a simple `repo.update_last_played` → `station_panel.refresh_recently_played()` call after `player.play()` in a follow-up — trivial one-liner.

2. **Should MainWindow slot forwarding or direct panel connection be preferred?**
   - What we know: Both work. Direct connection is simpler.
   - Recommendation: **Direct connection** (`self._player.title_changed.connect(self.now_playing.on_title_changed)`) for title/elapsed; MainWindow slots for failover/error/offline because the toast lives on MainWindow. Both approaches coexist in the same phase — clarity wins.

3. **Fake Repo vs real temp-file Repo in tests.**
   - What we know: `db_connect()` uses `paths.db_path()`. Phase 35 tests already monkeypatch this.
   - Recommendation: **Temp-file Repo with seeded data** — more realistic than a fake, and doesn't add a new mock layer. A single `tests/conftest.py` fixture returning a `Repo` with 2 providers × 3 stations × 1 stream covers all model/panel tests.

## Sources

### Primary (HIGH confidence)
- [VERIFIED: `.venv/bin/python -c "import PySide6; print(PySide6.__version__)"`] PySide6 6.11.0 installed
- [VERIFIED: `musicstreamer/player.py` read] Signal surface, thread model, queued-connection idiom for cover_art.py port
- [VERIFIED: `musicstreamer/repo.py` read] `get_setting` returns str, `list_stations` populates `.streams`, sqlite3 connection is thread-bound
- [VERIFIED: `musicstreamer/cover_art.py` read] `fetch_cover_art` invokes callback from worker thread — wrapping as signal emitter is the correct port
- [VERIFIED: `musicstreamer/ui_qt/main_window.py` read] Current scaffold state; `icons_rc` side-effect import, centralWidget structure, hamburger menu placeholder
- [VERIFIED: `tests/conftest.py` read] Offscreen platform set; `_stub_bus_bridge` autouse fixture prevents GLib MainLoop in tests
- [VERIFIED: `.planning/phases/36-qt-scaffold-gtk-cutover/36-VERIFICATION.md`] 266 tests baseline; icon fallback pattern established
- [CITED: https://doc.qt.io/qtforpython-6/PySide6/QtCore/QAbstractItemModel.html] `index`, `parent`, `rowCount`, `data`, `flags` contract
- [CITED: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QTreeView.html] `setHeaderHidden`, `setUniformRowHeights`, `setIconSize`, `expandAll`
- [CITED: https://doc.qt.io/qtforpython-6/PySide6/QtCore/QPropertyAnimation.html] `windowOpacity` property animation + state/finished signals
- [CITED: https://doc.qt.io/qtforpython-6/PySide6/QtGui/QPixmapCache.html] Process-global pixmap LRU cache
- [CITED: https://doc.qt.io/qtforpython-6/tutorials/basictutorial/signals_and_slots.html] Cross-thread queued connections
- [CITED: https://doc.qt.io/qtforpython-6/PySide6/QtCore/QObject.html#PySide6.QtCore.QObject.installEventFilter] Parent-resize event filter pattern

### Secondary (MEDIUM confidence)
- Phase 35 player.py twitch/youtube resolver signal pattern — treated as an in-repo reference implementation for Qt-signal-as-cross-thread-callback-adapter

### Tertiary (LOW confidence)
- None. All Phase 37 recommendations trace to either Qt official docs or in-repo verified code.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PySide6 6.11.0 verified installed; no new dependencies
- Architecture: HIGH — all patterns cite Qt official docs or in-repo precedent
- Pitfalls: HIGH — §1..§7 are all known PySide6 gotchas documented in Qt or PySide6 issue trackers
- Signal wiring: HIGH — established by Phase 35 player.py
- Test strategy: HIGH — FakePlayer pattern is standard pytest-qt testing for `QObject` subclasses

**Research date:** 2026-04-11
**Valid until:** 2026-05-11 (30 days — PySide6 6.11 is the current stable; Qt doesn't move fast in this area)
