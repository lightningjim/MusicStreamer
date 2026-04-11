# Phase 37: Station List + Now Playing - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning (UI-SPEC required — first visual-content phase)

<domain>
## Phase Boundary

Populate the Phase 36 empty `MainWindow` with the core playback UI: provider-grouped station list on the left, three-column now-playing panel on the right, volume slider, and toast overlay for failover/connecting notifications. A user opens the app, sees their stations, clicks one to play, and sees live ICY title + cover art + elapsed timer updates. All widgets live inside `musicstreamer/ui_qt/`.

Out of scope for Phase 37 (explicit cut-lines — DO NOT PULL FORWARD):
- Search box and filter chips → Phase 38 (UI-03)
- Favorites view + star button wiring → Phase 38 (UI-04)
- EditStationDialog and the edit icon on now-playing → Phase 39 (UI-05)
- Stream picker dropdown → Phase 39 (UI-13)
- DiscoveryDialog, ImportDialog → Phase 39 (UI-06, UI-07)
- AccountsDialog, YouTube cookies import, accent color, hamburger menu actions → Phase 40 (UI-08..UI-11)

</domain>

<decisions>
## Implementation Decisions

### Station List Widget (Gray Area 1 → option a)
- **D-01:** Station list uses **`QTreeView` + a custom `QAbstractItemModel` subclass** (probably `StationTreeModel(QAbstractItemModel)`). Provider groups are top-level rows; stations are children under each provider. This is the native Qt MVC pattern — scales cleanly to 50–200 stations (user's stated library size), supports keyboard navigation for free, and gives Phase 38's filter chips a clean entry point via `QSortFilterProxyModel` layering on top without touching the view.
- **D-02:** The "Recently Played" section (top-3 from `repo.list_recently_played()`) sits ABOVE the provider-grouped tree as a separate widget group, not as another tree branch. Options to implement: (a) a second `QTreeView` pinned to the top of the left panel with no groups, (b) a simple `QListView` with custom item delegate, (c) a small vertical stack of custom row widgets. Planner picks — all three satisfy the UX; the simplest (b or c) wins. The separation avoids mixing "recently played" items into the main tree model (which would complicate filtering and selection semantics).
- **D-03:** Clicking a station row triggers `player.play(station, preferred_quality=...)`. Double-click is treated as equivalent to single-click for this phase (no drag-to-reorder yet). Expanding/collapsing a provider group is standard `QTreeView` behavior — no custom handling needed.
- **D-04:** Provider groups render their group header with a bold label and an integer count suffix (e.g., "SomaFM (12)"). Station rows render logo + name. The per-row logo is a 32×32 `QIcon` loaded from `station.station_art_path` (already populated by Phase 27 station schema); fallback is a generic stream icon from the bundled Adwaita set (planner adds `audio-x-generic-symbolic.svg` to `ui_qt/icons/` during this phase).

### Now-Playing Panel Layout (Gray Area 2 → option a)
- **D-05:** Three-column horizontal layout matching v1.5: **[ logo | text + controls | cover art ]** via `QHBoxLayout`.
  - **Left column (~180px wide):** `QLabel` with scaled station logo via `QPixmap`. Fixed-width so the center column gets stable space.
  - **Center column (stretch):** `QVBoxLayout` — station `Name · Provider` label at top (U+00B7 middle dot separator, same as v1.5), ICY track title label below (large, bold), elapsed timer label below that, then a horizontal control row.
  - **Right column (160×160 fixed):** `QLabel` with cover art pixmap. 160×160 is the same slot size v1.5 used.
- **D-06:** Window width and panel proportions: the main window splits into [left 30% station list | right 70% now-playing + future content] via a `QSplitter(Qt.Horizontal)`. Splitter handle width is restorable but NOT persisted across restarts (defer to a future QoL phase per Phase 36 D-02 precedent).
- **D-07:** Control row in the center column contains ONLY: **play/pause button, stop button, volume slider**. Star, edit, and stream-picker widgets are either completely absent this phase OR placeholder `QWidget()` spacers to reserve their grid slot (planner picks — I recommend absent for a cleaner diff, with an inline comment noting where Phase 38/39/40 will insert them).
- **D-08:** Volume slider is a `QSlider(Qt.Horizontal)` with range 0–100, initial value from `repo.get_setting("volume", 80)` (v1.5 default), `setTickPosition(QSlider.NoTicks)`, fixed width ~120px. On `valueChanged(int)`: (a) update `player.set_volume(value / 100.0)`, (b) `repo.set_setting("volume", value)` for persistence. Volume slider tooltip shows the current percentage.

### Toast Overlay (Gray Area 3 → option a)
- **D-09:** Custom `ToastOverlay(QWidget)` widget — frameless, positioned bottom-center of `MainWindow.centralWidget()`, fade-in/fade-out via `QPropertyAnimation` on the `windowOpacity` property, auto-dismiss via `QTimer.singleShot(timeout_ms, self.hide)`. Lives in `musicstreamer/ui_qt/toast.py`.
- **D-10:** The `ToastOverlay` instance lives on `MainWindow` (not on each dialog that needs it — future dialogs call `main_window.show_toast(...)` via a parent-walk helper). Public API: `show_toast(text: str, duration_ms: int = 3000)`. The overlay is non-interactive (`Qt.WA_TransparentForMouseEvents`) so clicks pass through to whatever's behind it.
- **D-11:** Phase 37 wires toasts for two trigger conditions only: (a) **connecting** — "Connecting…" when `player.play()` is called for a new station, cleared when ICY title arrives (per v1.5 FIX-07 semantics); (b) **failover** — "Stream failed, trying next…" when `player.failover.emit(stream)` fires with a non-None stream, "Stream exhausted" when it fires with `None`. No other trigger sources this phase.

### Phase 37 Control Scope (Gray Area 4 → option a)
- **D-12:** Only **play/pause, stop, volume slider** ship in the control row this phase. Star, edit icon, stream picker dropdown are deferred:
  - Star button → Phase 38 when favorites DB layer and toggle view land
  - Edit button → Phase 39 when `EditStationDialog` is built
  - Stream picker dropdown → Phase 39 with `UI-13` (StreamPicker widget) + the existing `station.streams` list
- **D-13:** The play/pause button toggles between two icons: `media-playback-start-symbolic` (show when paused/stopped) and `media-playback-pause-symbolic` (show when playing). Both icons get added to `ui_qt/icons/` + `icons.qrc` this phase — same Adwaita source as Phase 36.
- **D-14:** Stop button always uses `media-playback-stop-symbolic`. Both buttons use `QToolButton` with `setIconSize(QSize(24, 24))` and the `Qt.ToolButtonIconOnly` style to match v1.5 aesthetic (icon-only, no text labels).
- **D-15:** Control-row icon palette: bundled SVG → `QIcon.fromTheme("name", QIcon(":/icons/name.svg"))` fallback (same pattern Phase 36 established). The new SVGs ship in Phase 37: `media-playback-start-symbolic`, `media-playback-pause-symbolic`, `media-playback-stop-symbolic`, `audio-x-generic-symbolic` (for station list fallback). Four additions.

### YouTube 16:9 Thumbnail (Gray Area 5 → option a)
- **D-16:** YouTube station thumbnails display in the same 160×160 cover-art slot as other stations, using `QPixmap.scaled(QSize(160, 160), Qt.KeepAspectRatio, Qt.SmoothTransformation)`. `KeepAspectRatio` preserves the 16:9 ratio → thumbnails render as 160×90 letterboxed inside the 160×160 slot. This matches v1.5's `Gtk.ContentFit.CONTAIN` semantics and UI-14's "no panel sizing regression" clause.
- **D-17:** The cover art slot always stays 160×160 fixed. No dynamic resizing based on source material.

### Data Flow — Player Signals → UI Slots
- **D-18:** All Player signals connect to MainWindow slots at window construction time via `Qt.ConnectionType.AutoConnection` (default — auto-resolves to `QueuedConnection` when sender/receiver cross threads):
  - `player.title_changed[str]` → `_on_title_changed` → updates ICY title label, triggers `_fetch_cover_art_async(icy_title)`
  - `player.playback_error[str]` → `_on_playback_error` → shows error toast + advances failover queue (player handles the advance internally)
  - `player.failover[object]` → `_on_failover` → shows "Stream failed, trying next…" toast or "Stream exhausted" toast depending on arg
  - `player.offline[str]` → `_on_offline` → shows "Channel offline" toast (Twitch-specific, still fires for non-Twitch as dead code — harmless)
  - `player.elapsed_updated[int]` → `_on_elapsed_updated` → updates elapsed-time label (format `MM:SS` or `HH:MM:SS` past 1 hour)
- **D-19:** Cover art fetch uses the existing `musicstreamer/cover_art.py` module (pure Python, reusable as-is). Port the callback to emit a new Qt signal `MainWindow.cover_art_ready[str]` which runs on the main thread via queued connection — replaces the `GLib.idle_add` comment in the old module. The module itself doesn't need code changes; only the calling site in `MainWindow` wraps the callback as a Qt signal emitter.
- **D-20:** Cover art session dedup via the existing `_last_cover_icy` mechanism stays as-is. Genre lookup via `last_itunes_result` stays as-is (needed by Phase 38's favorites when it arrives).

### Testing Strategy (QA-04 + carried QA-02 invariants)
- **D-21:** Phase 37 adds widget tests via `pytest-qt`:
  - `tests/test_station_tree_model.py` — `StationTreeModel` populated from fake repo data, verifies row/column counts, provider grouping, station ordering
  - `tests/test_now_playing_panel.py` — NowPlayingPanel widget construction, title label updates on `title_changed` signal, control button connections
  - `tests/test_toast_overlay.py` — `ToastOverlay.show_toast()` triggers animation, auto-dismisses on timer, respects parent window positioning
  - `tests/test_main_window_integration.py` — integration test: construct `MainWindow`, feed a fake `Player` via monkeypatch, emit `title_changed` signal, assert the title label updates
- **D-22:** All new tests use `qtbot` and `QT_QPA_PLATFORM=offscreen` (inherited from Phase 35/36). Full suite floor for Phase 37 completion: ≥ 266 + new tests (target ~280+).
- **D-23:** The new widget tests must NOT require a real `Player` instance with a real GStreamer pipeline. Use a `FakePlayer(QObject)` test double that exposes the same Signal surface (`title_changed`, `failover`, etc.) so tests can emit signals programmatically. This doubles as a template for Phase 38–40 widget tests.

### Claude's Discretion
- Exact `QSplitter` initial ratio (30/70 is a starting suggestion)
- `QTreeView` styling — rounded corners via QSS? Match Adwaita's soft look or go native Qt flat? (UI-SPEC will resolve)
- Elapsed timer label format (`0:00` vs `00:00`) and whether seconds tick visibly
- Toast animation duration (fade-in 150ms / hold 3000ms / fade-out 300ms is a sensible starting point)
- Station row height in the tree view
- Keyboard shortcuts for play/pause/stop (defer to a shortcuts phase or leave to natural Qt focus behavior)

### UI-SPEC Generation (unlike Phase 36, this phase needs one)
- **D-24:** Phase 37 is the first phase with real visual design work. The plan-phase workflow will detect "UI hint: yes" and auto-generate `37-UI-SPEC.md` via `gsd-ui-phase`. This is **appropriate and should NOT be skipped** — the UI spec pins down typography, spacing, colors, QSS overrides, and the exact look of the station list rows / now-playing panel / toast widget. Planner must read UI-SPEC.md before creating plans.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap + Requirements
- `.planning/ROADMAP.md` § "Phase 37: Station List + Now Playing" — goal, success criteria
- `.planning/REQUIREMENTS.md` § "UI — Feature-parity port" — UI-01, UI-02, UI-12, UI-14 full text
- `.planning/PROJECT.md` — Key Decisions table (historical v1.5 choices for station list, now-playing panel, cover art — most still apply as aesthetic/behavioral guidance)

### Phase 36 output to build on
- `.planning/phases/36-qt-scaffold-gtk-cutover/36-VERIFICATION.md` — confirms MainWindow scaffold + structural containers ready
- `musicstreamer/ui_qt/main_window.py` — starting point for widget insertion (empty menubar, central widget, status bar)
- `musicstreamer/ui_qt/icons/` — Adwaita icon directory ready for additions; `icons.qrc` + `icons_rc.py` pattern established
- `musicstreamer/__main__.py` — entry point already wires `QApplication` + dark palette; nothing to change

### Data layer (stable from v1.5, reused as-is)
- `musicstreamer/repo.py` — `list_stations()`, `list_recently_played()`, `list_streams(station_id)`, `get_setting(key, default)`, `set_setting(key, value)` — all usable
- `musicstreamer/models.py` — `Station`, `StationStream` dataclasses
- `musicstreamer/cover_art.py` — pure Python iTunes fetcher with worker thread + callback pattern; only the `GLib.idle_add` comment needs updating to Qt-signal guidance
- `musicstreamer/assets.py` — station logo path helpers
- `musicstreamer/constants.py` — PEP 562 lazy re-exports through `paths.py`
- `musicstreamer/paths.py` — platformdirs-rooted helpers

### Backend signals (from Phase 35 player.py)
- `Player.title_changed = Signal(str)` — ICY title
- `Player.failover = Signal(object)` — StationStream | None
- `Player.offline = Signal(str)` — Twitch channel name
- `Player.playback_error = Signal(str)` — error text
- `Player.elapsed_updated = Signal(int)` — seconds since playback start
- `Player.youtube_resolved`, `Player.youtube_resolution_failed` — internal Twitch/YouTube resolver signals (MainWindow doesn't wire these; Player handles internally)

### External specs (researcher should consult)
- PySide6 `QAbstractItemModel`, `QTreeView`, `QSortFilterProxyModel` docs
- PySide6 `QPropertyAnimation`, `QTimer`, `Qt.WA_TransparentForMouseEvents` for toast overlay
- PySide6 `QSplitter` for the main left/right layout
- `QPixmap.scaled` with `Qt.KeepAspectRatio` + `Qt.SmoothTransformation`
- `QToolButton` vs `QPushButton` with icons — v1.5 reference is GTK, Qt convention prefers `QToolButton` for icon-only buttons
- `QFontMetrics` for text elision in station rows (long station names)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (untouched — consumed by new widgets)
- **`repo.list_stations()`** returns `List[Station]` with `.streams` populated via `list_streams()`. Perfect feed for `StationTreeModel`.
- **`repo.list_recently_played(n=3)`** returns top-N most recently played stations. Feed for the RecentlyPlayed widget.
- **`cover_art.fetch_cover_art(icy_string, callback)`** — worker thread pattern, reusable as-is. Callback gets temp file path or None. Wrap the callback to emit a Qt signal (via lambda or a small adapter) instead of calling `GLib.idle_add`.
- **`cover_art.is_junk_title(s)`** — junk detector; used by `fetch_cover_art` but also available for the panel to decide whether to even attempt a fetch.
- **`assets.copy_asset_for_station()`** — for station logo import (not used in Phase 37 but available if needed).

### Established Patterns
- **Qt signals + queued connections** (Phase 35): sender emits on any thread, Qt auto-queues to the receiver's thread. Worker-thread callbacks (like `fetch_cover_art`'s) become trivial via a lambda that emits a Signal.
- **Bundled icons via `.qrc`** (Phase 36): `musicstreamer/ui_qt/icons/` + `icons.qrc` + regenerate `icons_rc.py` when adding SVGs. Phase 37 adds 4 new SVGs (`media-playback-start-symbolic`, `media-playback-pause-symbolic`, `media-playback-stop-symbolic`, `audio-x-generic-symbolic`) and regenerates.
- **`QIcon.fromTheme` fallback** (Phase 36 PORT-08): every `QIcon` lookup goes through `QIcon.fromTheme("name", QIcon(":/icons/name.svg"))` so Linux theme wins and Windows has a bundled fallback.
- **`ui_qt/main_window.py` top-of-file side-effect import** of `icons_rc` — already in place from Phase 36. New icons are automatically registered.

### Integration Points
- **`MainWindow.__init__`** gets two new child widgets: `StationListPanel(QWidget)` on the left, `NowPlayingPanel(QWidget)` on the right, joined by a `QSplitter(Qt.Horizontal)` as the `centralWidget()`.
- **`MainWindow.__init__`** also constructs a `Player()` instance and wires its signals to `NowPlayingPanel` slots (or to `MainWindow` slots that forward — planner picks).
- **Toast overlay** constructs last (after the central widget is set) and parents itself to `MainWindow.centralWidget()` with explicit positioning.

### Constraints
- **No feature creep beyond UI-01, UI-02, UI-12, UI-14.** Any "since we're here, we should also add X" gets redirected to its proper phase (search box → 38, edit dialog → 39, etc.). Plan checker will catch this.
- **Existing 266 tests must keep passing.** New widget tests are additive; they do not modify existing test files except where `MainWindow` integration requires it.
- **No widget lifetime (`RuntimeError: Internal C++ object already deleted`) issues** — QA-05 gate. Pay attention to signal connections: disconnect in destructors or use parent-based ownership. Planner flags this explicitly in the task acceptance criteria.

</code_context>

<specifics>
## Specific Ideas

- User chose **defaults** across the board (1a/2a/3a/4a/5a). This signals: "v1.5 was good enough, port faithfully, don't redesign."
- Faithful port means v1.5 decisions become implicit UI guidance: 3-column layout, middle-dot separator, `Name · Provider` label format, 160×160 cover slot, iTunes search dedup, 80% default volume.
- User's terse-pragmatic profile suggests the planner should favor small/simple widget choices over clever Qt tricks. Four new tests (D-21) over twenty is the right instinct.

</specifics>

<deferred>
## Deferred Ideas

- **Search box / filter chips** → Phase 38 (UI-03)
- **Favorites toggle view + star button wiring** → Phase 38 (UI-04, FAVES-01..04)
- **Star button on now-playing panel** → Phase 38 (needs favorites DB + toggle view first)
- **EditStationDialog + edit icon on now-playing** → Phase 39 (UI-05)
- **Stream picker dropdown on now-playing** → Phase 39 (UI-13)
- **DiscoveryDialog, ImportDialog** → Phase 39 (UI-06, UI-07)
- **AccountsDialog, cookie import, accent color, hamburger menu** → Phase 40 (UI-08..UI-11)
- **Window geometry persistence** → continued defer from Phase 36 D-02
- **Keyboard shortcuts** → a later QoL phase or left to Qt focus defaults
- **Drag-to-reorder stations** → future enhancement (not in v2.0 scope)
- **Right-click context menu on stations** → future enhancement

</deferred>

---

*Phase: 37-station-list-now-playing*
*Context gathered: 2026-04-11*
</content>
</invoke>
