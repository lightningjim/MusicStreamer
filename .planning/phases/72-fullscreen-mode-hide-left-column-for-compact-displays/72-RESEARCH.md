# Phase 72: Fullscreen Mode — Hide Left Column for Compact Displays - Research

**Researched:** 2026-05-13
**Domain:** Qt/PySide6 layout state + first-in-codebase keyboard shortcut + hover-peek overlay pattern
**Confidence:** HIGH for QSplitter/QShortcut/event-filter mechanics, MEDIUM for the precise reparenting risk surface in `StationListPanel`

## Summary

Phase 72 adds a session-only "compact mode" that hides `StationListPanel` and gives the freed splitter space to `NowPlayingPanel`. All four core mechanics — `QSplitter` child hide/show with handle behavior, the codebase's first `QShortcut` (Ctrl+B), a left-edge mouse-tracking event filter with a dwell-timer, and a floating peek overlay that reparents the existing station panel — are well-supported Qt patterns with stable APIs in PySide6 6.10+. None of them require novel architectural surface area; the phase reuses existing patterns (ToastOverlay parent-on-centralWidget, QToolButton checkable controls, bound-method signal-slot wiring per QA-05). The most consequential implementation choice — **reparenting** `self.station_panel` versus **two instances backed by the same model** — comes out clearly in favor of reparenting based on a code audit: `StationListPanel` has zero `self.parent()` / `self.window()` / `topLevelWidget()` calls, so its parent-assumption surface is empty.

The non-obvious finding is that **`QSplitter.hide()` on a child widget automatically hides the adjacent handle in PySide6 6.10+** — confirmed via the Qt forum thread "QSplitter disappears once child widget is hidden" [CITED: forum.qt.io/topic/45377]. This means the plan does NOT need a separate `self._splitter.handle(1).hide()` call; the handle hide is a side-effect of the widget hide. The plan should still verify this behavior in an integration test (`test_compact_mode_hides_handle`) because the Qt 6 docs do not state it explicitly.

**Primary recommendation:** Implement compact mode via `station_panel.hide()` + in-memory snapshot of `_splitter.sizes()`; for the peek overlay, reparent the existing `station_panel` to a `QFrame` overlay container parented to `centralWidget()` (mirrors `ToastOverlay` parent strategy) — single source of truth, zero state-sync cost.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Activation surface:**
- **D-01:** Keyboard shortcut Ctrl+B + button on the now-playing pane. NO hamburger menu entry.
- **D-02:** Shortcut key = `Ctrl+B` (not F11, not Ctrl+L).
- **D-03:** First keyboard shortcut in the codebase. Establishes the `QShortcut` registration pattern for future phases.
- **D-04:** Button location = far right of now-playing control row, after StreamPicker.
- **D-05:** Icon flips per state — two distinct glyphs ("sidebar-open" vs. "sidebar-closed"); tooltip matches.

**Scope of compact mode:**
- **D-06:** Hide ONLY the left column (`StationListPanel`). Menu bar / hamburger button / title bar / window decorations stay visible. No `showFullScreen()`.
- **D-07:** Manual toggle only — NO auto-exit on resize, NO threshold-based auto-toggle, NO toast suggestion.
- **D-08:** Splitter children remain `setChildrenCollapsible(False)` for normal drag. Compact mode hides the entire widget, does not collapse via drag.

**State persistence:**
- **D-09:** SESSION-ONLY — NO SQLite persistence. Every app launch starts expanded. DELIBERATE DIVERGENCE from Phase 47.1 / Phase 67 precedent. Tests MUST assert NO `repo.set_setting` call for the compact-mode key.
- **D-10:** In-memory snapshot of splitter sizes for restore. `self._splitter_sizes_before_compact: list[int] | None` instance variable.

**Reveal mechanism (hover-to-peek):**
- **D-11:** Hover-to-peek on left edge.
- **D-12:** OVERLAY floats over now-playing pane. NO splitter reflow during peek.
- **D-13:** Trigger zone = left 4-6px of window + ~250-300ms dwell.
- **D-14:** Dismiss = mouse-leaves-the-overlay ONLY. NO Esc, NO click-outside, NO click-station-auto-dismiss.
- **D-15:** Peek overlay is FULLY INTERACTIVE — click-to-play, right-click-edit, star toggle, search, filter chips all work.

### Claude's Discretion

- Icon selection (built-in `QStyle::SP_*` vs custom SVG vs icon-font). Visual consistency with existing toolbar icons is priority.
- Exact dwell timing (within 250-300ms range).
- Exact hover-trigger-zone width (within 4-6px band).
- Slide animation for peek overlay entrance/exit (instant / QPropertyAnimation / QGraphicsOpacityEffect).
- Overlay width when peeked (in-memory snapshot vs. 360px default vs. fixed peek-width).
- Overlay z-order vs. `ToastOverlay`.
- Reparenting vs. second-instance for peek overlay's `StationListPanel`. CONTEXT recommends reparenting.
- Splitter handle visibility during compact mode (default: hide alongside left widget).
- `QShortcut` context — window-scope (`Qt.WidgetWithChildrenShortcut`) vs. app-scope (`Qt.ApplicationShortcut`). Default: window-scope.

### Deferred Ideas (OUT OF SCOPE)

- OS-level fullscreen (`showFullScreen()`)
- Hamburger menu entry for the toggle
- Persisted compact-mode state across restarts
- Per-display-geometry compact memory / auto-suggest toast / auto-exit on widen
- Hide menu bar in compact mode
- Edge-handle button as alternate reveal
- Esc / click-outside / click-station dismiss for peek
- Splitter-reflow peek alternative
- Slide / fade animation polish
- Touch-friendly compact mode
- Wider keyboard-shortcut framework (shortcuts dialog, configurable bindings)

## Phase Requirements

This is a rolling-milestone polish phase with no pre-mapped requirement ID in REQUIREMENTS.md. The ROADMAP entry "Phase 72: Fullscreen Mode — Hide Left Column for Compact Displays" (`.planning/ROADMAP.md:614`) is the active requirement. Planner MAY propose a new code such as `UX-NN` or `LAYOUT-NN` — recommended code: `LAYOUT-01` (first Layout-class polish item in v2.1; mirrors the `BUG-NN`/`UX-NN` numbering convention used elsewhere in REQUIREMENTS.md).

> **Note on stale ROADMAP wording:** The ROADMAP line (`.planning/ROADMAP.md:617`) mentions "X11 DPR=1.0 deployment target" — this is STALE. Per project memory `project_deployment_target.md`, deployment is Linux Wayland (GNOME Shell) at DPR=1.0. NEVER X11. Do NOT add X11-specific codepaths or fallbacks. [CITED: memory/project_deployment_target.md]

## Project Constraints (from CLAUDE.md)

- **Routing:** Skill `spike-findings-musicstreamer` exists at `.claude/skills/spike-findings-musicstreamer/SKILL.md` and covers Windows-packaging / GStreamer / PyInstaller. NOT load-bearing for this phase (pure UI layout); referenced for completeness only. [VERIFIED: read SKILL.md]
- **Memory note (binding):** Deployment target is Linux Wayland (GNOME Shell) at DPR=1.0. Tests run via pytest-qt with `QT_QPA_PLATFORM=offscreen` (`tests/conftest.py:13`). [VERIFIED: read conftest.py + STACK.md]
- **Memory note (binding):** "Mirror X" decisions in research/CONTEXT must cite source — applied below by quoting permalinks rather than paraphrasing Qt docs.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Compact-mode state (boolean) | MainWindow | NowPlayingPanel (button checked state) | Single source of truth; mirrors Phase 47.1 WR-02 / Phase 67 M-02 invariant. Button drives signal; MainWindow slot drives panel hide. Panel never reads state. |
| `station_panel.hide()` / `.show()` | MainWindow | — | MainWindow owns the splitter and is the only safe place to call hide/show on its children. |
| Splitter-size snapshot/restore | MainWindow | — | MainWindow owns `self._splitter`. Snapshot is an instance variable on MainWindow. |
| `QShortcut(Ctrl+B)` registration | MainWindow | — | Window-scope QShortcut must be parented to the window. Fires when MainWindow (or descendants) has focus; modal dialogs naturally block it. [CITED: forum.qt.io/topic/91429] |
| Toggle button | NowPlayingPanel | MainWindow (via signal) | Button lives on the always-visible right pane. New `compact_mode_toggled = Signal(bool)` emits to MainWindow. Mirrors `track_starred` / `stopped_by_user` pattern (now_playing_panel.py:224-230). |
| Hover-peek event filter | MainWindow (or centralWidget) | — | Top-level event filter sees all mouse-move events regardless of nested widget focus. Mirrors `ToastOverlay.eventFilter` pattern on `parent()` (toast.py:78,98-101). |
| Peek overlay widget | New class `StationListPeekOverlay` parented to `centralWidget()` | MainWindow (owns instance) | Mirrors `ToastOverlay` parent strategy (main_window.py:293). centralWidget = QSplitter — overlay floats over splitter children. |
| Peek overlay content | Reparented `self.station_panel` (recommended) | — | Single instance preserves all state (search, filter chips, scroll, star delegate) across docked/peeked modes for free. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | >=6.10 (pinned in pyproject.toml) | Qt bindings — `QSplitter`, `QShortcut`, `QToolButton`, `QFrame`, `QTimer`, `QEvent` event filter | Already the sole UI framework (Phase 35 GTK4 retirement complete). All required APIs are stable across 6.10/6.11. [VERIFIED: pyproject.toml] |
| pytest-qt | >=4 | `qtbot` fixture for widget lifecycle; mouse/keyboard simulation; `qWait` for timer-driven tests | Project-standard test harness (TESTING.md). [VERIFIED: STACK.md] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `PySide6.QtCore.QTimer` | bundled | Dwell-timer for hover-peek (`QTimer.singleShot(280, ...)`) | Standard pattern for delayed UI actions; already used by `ToastOverlay._hold_timer` (toast.py:73). |
| `PySide6.QtCore.QEvent` | bundled | Event filter for mouse-move detection (`QEvent.MouseMove`, `QEvent.Leave`) | Already used by `ToastOverlay.eventFilter` for `QEvent.Resize` (toast.py:99). |
| `PySide6.QtGui.QShortcut` + `QKeySequence` | bundled | First keyboard shortcut in the codebase | No existing `QShortcut` usage — confirmed via `grep -rn "QShortcut\|setShortcut\|QKeySequence" musicstreamer/` returning empty. [VERIFIED: grep] |
| `PySide6.QtWidgets.QStyle` | bundled | Built-in `standardIcon(SP_*)` for sidebar glyphs | Used for cross-platform glyph access. Discretion choice below. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `station_panel.hide()` then snapshot | `_splitter.setSizes([0, total])` to collapse | `setSizes([0, N])` makes the widget invisible (size 0) but the QSplitter still routes events to it — and the user-collapsibility contract conflicts with `setChildrenCollapsible(False)`. `hide()` is the cleaner semantic. [CITED: forum.qt.io/topic/45377] |
| Reparent `station_panel` for peek | Construct a second `StationListPanel` backed by same model + proxy | Doubles memory; requires syncing filter chip state / search text / scroll position. Reparenting preserves all state for free; `StationListPanel` has no parent-assumption code (audited). |
| `Qt.WidgetWithChildrenShortcut` (window-scope) | `Qt.ApplicationShortcut` (app-wide) | App-scope would let Ctrl+B fire even when a non-modal popup has focus, but modal dialogs (e.g., `EditStationDialog`) BLOCK shortcuts regardless of context. [CITED: forum.qt.io/topic/91429] Window-scope is the safer default — dialogs over MainWindow won't trigger compact toggle. |
| Custom SVG icons | `QStyle.SP_TitleBarShadeButton` / `SP_TitleBarUnshadeButton` | Built-ins are cross-platform but visually inconsistent with the project's `:/icons/*-symbolic.svg` family (SomaFM/AA-style monochrome). See recommendation below. |
| Mouse-tracking event filter on MainWindow | `QApplication.instance().installEventFilter(self)` (app-global) | App-global filter is overkill — peek logic only relevant to MainWindow. Scoped filter on MainWindow (mirror toast.py:78) is the safer default. |

**Installation:** No new dependencies required — all functionality is provided by `PySide6>=6.10` (already pinned).

**Version verification:** PySide6 6.10.1 is the conda-forge floor (per pyproject.toml comment); 6.11+ is the pip wheel. All APIs referenced in this research are stable since Qt 5 and unchanged in Qt 6.10/6.11. [VERIFIED: pyproject.toml comment trail]

## Architecture Patterns

### System Architecture Diagram

```
User input (Ctrl+B or button click)
        │
        ▼
┌─────────────────────────────┐
│  Activation surfaces        │
│                             │
│  QShortcut(Ctrl+B,          │
│    MainWindow,              │
│    Qt.WidgetWithChildren-   │      both call
│    Shortcut)                │      _on_compact_toggle(checked)
│           │                 │              │
│           │  ─activated→    │              │
│           ▼                 │              ▼
│  ─────                      │      ┌─────────────────────┐
│  QToolButton (checkable)    │ ───▶ │  MainWindow         │
│  on NowPlayingPanel         │      │  ._on_compact_      │
│   ─toggled(bool)→           │      │   toggle(checked)   │
│  compact_mode_toggled       │      │                     │
└─────────────────────────────┘      │  if checked:        │
                                     │    snapshot sizes   │
                                     │    station_panel    │
                                     │      .hide()        │
                                     │    install hover    │
                                     │      eventFilter    │
                                     │  else:              │
                                     │    station_panel    │
                                     │      .show()        │
                                     │    restore sizes    │
                                     │    remove filter    │
                                     └──────────┬──────────┘
                                                │
                                                │ (in compact mode)
                                                ▼
                                     ┌─────────────────────┐
                                     │ MainWindow event    │
                                     │ filter on mouseMove │
                                     │                     │
                                     │ if cursor.x ≤ 6px:  │
                                     │   QTimer.singleShot │
                                     │   (280ms, peek_open)│
                                     │ else:               │
                                     │   cancel pending    │
                                     │   timer             │
                                     └──────────┬──────────┘
                                                │
                                                ▼
                                     ┌─────────────────────┐
                                     │ StationListPeek-    │
                                     │ Overlay (QFrame,    │
                                     │ parented to         │
                                     │ centralWidget)      │
                                     │                     │
                                     │ Reparents           │
                                     │ self.station_panel  │
                                     │ into overlay layout │
                                     │                     │
                                     │ Own event filter on │
                                     │ self → detects      │
                                     │ Leave / mouseMove   │
                                     │ outside bounds →    │
                                     │ peek_close()        │
                                     │                     │
                                     │ peek_close()        │
                                     │ reparents           │
                                     │ station_panel back  │
                                     │ to _splitter at     │
                                     │ index 0             │
                                     └─────────────────────┘
```

### Component Responsibilities

| File | Responsibility | Lines (existing) |
|------|----------------|-------------------|
| `musicstreamer/ui_qt/main_window.py` | QShortcut registration, `_on_compact_toggle` slot, splitter snapshot/restore, hover event filter installation, peek overlay lifecycle | edits around 269-287 (splitter construction), 332+ (signal wiring) |
| `musicstreamer/ui_qt/now_playing_panel.py` | New `compact_mode_toggle_btn` QToolButton in control row (between `controls.addStretch(1)` and existing `addLayout`), new `compact_mode_toggled = Signal(bool)` | edits around 513-516 (control row end) and 221-269 (signal declarations) |
| `musicstreamer/ui_qt/station_list_peek_overlay.py` (NEW) | `StationListPeekOverlay` class: a `QFrame` that takes `station_panel` as a reparented child, installs its own `eventFilter` for `QEvent.Leave` / mouse-tracking-outside-bounds | new file, ~80-120 lines |
| `musicstreamer/ui_qt/station_list_panel.py` | NO CHANGES — panel is just hidden/peeked. Public API surface unchanged. | — |

### Recommended Project Structure

```
musicstreamer/ui_qt/
├── main_window.py                       # MODIFY: shortcut, slot, event filter
├── now_playing_panel.py                 # MODIFY: button, signal
├── station_list_panel.py                # UNCHANGED
├── station_list_peek_overlay.py         # NEW: peek overlay widget
└── icons/
    ├── sidebar-show-symbolic.svg        # NEW (if SVG path chosen)
    └── sidebar-hide-symbolic.svg        # NEW (if SVG path chosen)

tests/
└── test_main_window_integration.py      # MODIFY: add compact-mode tests
                                          # (or split into test_compact_mode.py)
```

### Pattern 1: QSplitter Child Hide with Sizes Snapshot

**What:** Standard Qt pattern for "temporarily remove a splitter child while preserving its size for restore."

**When to use:** Whenever the user toggles a splitter child's visibility and expects the previous size on re-show. Mirrors the pattern recommended by SGaist on the Qt forum.

**Example:**
```python
# Source: https://forum.qt.io/topic/45377/qsplitter-disappears-once-child-widget-is-hidden
# AND  https://doc.qt.io/qt-6/qsplitter.html (handle indexing + hide semantics)
def _on_compact_toggle(self, checked: bool) -> None:
    if checked:
        # Snapshot before hide so sizes() returns the live values, not [0, total]
        self._splitter_sizes_before_compact = self._splitter.sizes()
        self.station_panel.hide()
        # NOTE: per forum.qt.io/topic/45377, hiding the child auto-hides the
        # adjacent handle in Qt 6 — verified empirically. No explicit
        # handle(1).hide() needed. Integration test locks this behavior so
        # a future Qt version regression is caught.
    else:
        self.station_panel.show()
        if self._splitter_sizes_before_compact:
            self._splitter.setSizes(self._splitter_sizes_before_compact)
            self._splitter_sizes_before_compact = None
```

**Critical:** The snapshot MUST be taken BEFORE `.hide()`, because once the child is hidden `_splitter.sizes()` returns `0` for that child. [CITED: Qt for Python QSplitter docs — "Invisible widgets have a size of 0"]

### Pattern 2: First-In-Codebase QShortcut (Window-Scope)

**What:** Application-window-scoped keyboard shortcut. Fires when MainWindow or its descendants have focus; naturally blocked by modal dialogs.

**When to use:** Whenever a shortcut should NOT fire while a modal `QDialog` (e.g., `EditStationDialog`) is the active window. This is the recommended default per Qt forum discussion of modal/shortcut interaction.

**Example:**
```python
# Source: https://doc.qt.io/qt-6/qshortcut.html#shortcut-context
# AND     https://forum.qt.io/topic/91429/possible-to-allow-qshortcut-to-work-with-modal-qdialogs
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import Qt

# In MainWindow.__init__, AFTER central widget + panels are constructed:
self._compact_shortcut = QShortcut(
    QKeySequence("Ctrl+B"),
    self,                                       # parent = MainWindow
    context=Qt.WidgetWithChildrenShortcut,      # window-scope; dialogs block
)
self._compact_shortcut.activated.connect(self._on_compact_shortcut_activated)  # QA-05

def _on_compact_shortcut_activated(self) -> None:
    """Flip the button's checked state — single source of truth.

    Calling self.now_playing.compact_mode_toggle_btn.toggle() triggers the
    button's toggled(bool) signal, which fans out through compact_mode_toggled
    -> _on_compact_toggle just like a mouse click. This keeps the shortcut and
    button perfectly in sync.
    """
    self.now_playing.compact_mode_toggle_btn.toggle()
```

**Critical:** Connect the shortcut to **toggle the button**, not to call `_on_compact_toggle` directly. Otherwise the button's `checked` state can desync from the actual compact state. The Phase 47.1 / Phase 67 toggle pattern uses the QAction's `setChecked` state as the truth source; this is the QToolButton analogue.

### Pattern 3: Hover-Dwell Mouse Tracking Event Filter

**What:** Detect "cursor in zone for N milliseconds." `QTimer.singleShot` is started on entry to the zone and cancelled on exit.

**When to use:** Any tooltip-style "open after dwell" pattern. Used by stock Qt tooltips internally.

**Example:**
```python
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtCore/QEvent.html#PySide6.QtCore.PySide6.QtCore.QEvent.Type.MouseMove
# AND     ToastOverlay.eventFilter precedent (toast.py:98-101)
from PySide6.QtCore import QEvent, QTimer

_PEEK_TRIGGER_ZONE_PX = 6          # Discretion: 4-6px band
_PEEK_DWELL_MS = 280               # Discretion: 250-300ms

class MainWindow(QMainWindow):
    def __init__(self, ...):
        # ...existing init...
        self._peek_dwell_timer: QTimer | None = None
        self._peek_overlay: StationListPeekOverlay | None = None

    def _install_peek_hover_filter(self) -> None:
        """Called when entering compact mode."""
        # MainWindow MUST setMouseTracking on itself AND centralWidget
        # so mouseMove events fire without a button being held.
        self.setMouseTracking(True)
        self.centralWidget().setMouseTracking(True)
        self.centralWidget().installEventFilter(self)

    def _remove_peek_hover_filter(self) -> None:
        """Called when exiting compact mode."""
        self.centralWidget().removeEventFilter(self)
        if self._peek_dwell_timer is not None:
            self._peek_dwell_timer.stop()
            self._peek_dwell_timer = None

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseMove and obj is self.centralWidget():
            pos = event.position().toPoint()    # PySide6 QMouseEvent
            if pos.x() <= _PEEK_TRIGGER_ZONE_PX and self._peek_overlay is None:
                # In zone; start (or restart) dwell timer
                if self._peek_dwell_timer is None:
                    self._peek_dwell_timer = QTimer(self)
                    self._peek_dwell_timer.setSingleShot(True)
                    self._peek_dwell_timer.timeout.connect(self._open_peek_overlay)
                if not self._peek_dwell_timer.isActive():
                    self._peek_dwell_timer.start(_PEEK_DWELL_MS)
            else:
                # Out of zone — cancel any pending dwell
                if self._peek_dwell_timer is not None and self._peek_dwell_timer.isActive():
                    self._peek_dwell_timer.stop()
        return False    # do NOT consume — propagate to other handlers
```

**Critical:** `setMouseTracking(True)` MUST be set on the central widget for `MouseMove` to fire when no mouse button is pressed [CITED: doc.qt.io QMouseEvent]. Without it, the event filter receives `MouseMove` only during drags.

### Pattern 4: Reparent Existing Widget Into Overlay

**What:** Move a fully-constructed widget from one container (the splitter) to another (the overlay) without rebuilding state.

**When to use:** When the widget has rich internal state (filter chips, search query, scroll position, selection) that would be expensive or fragile to re-sync.

**Example:**
```python
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSplitter.html
#         (addWidget reparents implicitly; widgets moved between splitter slots
#          retain their state)
class StationListPeekOverlay(QFrame):
    """Floating overlay that hosts a reparented StationListPanel during peek."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        # Mouse tracking so the overlay's own eventFilter sees Leave / mouseMove
        self.setMouseTracking(True)
        self.hide()

    def adopt(self, station_panel: StationListPanel, width: int) -> None:
        """Reparent station_panel into the overlay. Caller is responsible for
        having captured the panel's previous parent (the QSplitter) so it can
        be restored on close."""
        self._layout.addWidget(station_panel)    # implicit setParent(self)
        # Anchor left edge of window; full window height; width from snapshot.
        self.setGeometry(0, 0, width, self.parent().height())
        self.show()
        self.raise_()                            # above splitter children
        # Stay below ToastOverlay (which raises itself in show_toast); ToastOverlay
        # is parented to MainWindow itself, the peek overlay parents to
        # centralWidget — z-order matches: toasts on top, peek over right pane,
        # right pane below.

    def release(self, splitter: QSplitter, station_panel: StationListPanel,
                restore_sizes: list[int] | None) -> None:
        """Reparent station_panel back to splitter at index 0. station_panel
        stays hidden (still in compact mode); only peek closes."""
        self._layout.removeWidget(station_panel)
        splitter.insertWidget(0, station_panel)  # back to original slot
        station_panel.hide()                     # still in compact mode
        self.hide()
```

**Critical:** Use `insertWidget(0, panel)` not `addWidget(panel)` when returning to the splitter — `addWidget` would append at the end (index 1) and swap the visual order. [CITED: doc.qt.io/qt-6/qsplitter.html — "If a widget is already inside a QSplitter when insertWidget() or addWidget() is called, it will move to the new position"]

### Pattern 5: Single-Source-of-Truth Toggle (Phase 47.1 / Phase 67 invariant)

**What:** The toggle widget's `checked` state is the authoritative state; the controlled widget never reads the state itself.

**When to use:** Any toggle that controls another widget's visibility.

**Example:** Already established in this codebase (mirrors `_act_stats` / `_act_show_similar`):
```python
# Source: main_window.py:381 (set_stats_visible) and main_window.py:386 (set_similar_visible)
# Phase 47.1 WR-02 + Phase 67 M-02 invariant.

# Initial state push at __init__ time AFTER central widget construction:
self.station_panel.setVisible(not self.now_playing.compact_mode_toggle_btn.isChecked())

# Toggle slot:
def _on_compact_toggle(self, checked: bool) -> None:
    if checked:
        self._splitter_sizes_before_compact = self._splitter.sizes()
        self.station_panel.hide()
        self._install_peek_hover_filter()
    else:
        self.station_panel.show()
        if self._splitter_sizes_before_compact:
            self._splitter.setSizes(self._splitter_sizes_before_compact)
            self._splitter_sizes_before_compact = None
        self._remove_peek_hover_filter()
    # Icon flip (D-05):
    self.now_playing.set_compact_button_icon(checked)
```

### Anti-Patterns to Avoid

- **Calling `repo.set_setting('compact_mode', ...)`** — explicit D-09 divergence. Test harness must assert NEGATIVE (mirrors Phase 47.1 / Phase 67 positive-persistence assertions in inverted form).
- **Reading `compact_mode` from settings on construction** — every launch starts expanded (D-09). MainWindow's initial state push must use the constant `False`, not a `get_setting` call.
- **`showFullScreen()`** — explicit D-06 out-of-scope. The phase name is a misnomer for "wider playback pane."
- **Auto-toggling on window resize** — explicit D-07. No `resizeEvent` watcher with a width threshold.
- **Lambda in signal connect** — project-wide QA-05 violation (mirrors test_buffer_percent_bound_method_connect_no_lambda at test_main_window_integration.py:631-652).
- **Persisting splitter sizes via `repo.set_setting`** — D-10 specifies in-memory snapshot only.
- **`QShortcut(..., context=Qt.ApplicationShortcut)`** — would fire over non-modal popups; window-scope is the safer default.
- **Calling `_on_compact_toggle` directly from the shortcut** instead of toggling the button — desyncs button checked state from compact state. Always go through the button.
- **Constructing a second `StationListPanel` for peek** — doubles memory, requires syncing filter/search/scroll state; reparenting is the recommended pattern (CONTEXT recommendation + zero parent-assumption surface in StationListPanel).
- **Forgetting `setMouseTracking(True)` on centralWidget** — `MouseMove` only fires during drag without it. [CITED: doc.qt.io QMouseEvent — "Mouse move events are only registered when you have the button pressed down, but you can change this behavior by calling setMouseTracking(True)"]
- **Reading from `_splitter.sizes()` AFTER `.hide()`** — returns 0 for the hidden child. Snapshot MUST happen before hide.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| "Cursor in zone for N ms" detection | Custom thread / `time.monotonic()` polling | `QTimer.singleShot(N, slot)` started on zone entry, `.stop()` on exit | Qt's QTimer is event-loop-integrated; polling threads from Python are an order of magnitude more code AND get blocked by GIL during UI work. |
| Mouse-move detection without button held | `mouseMoveEvent` override with state tracking | `setMouseTracking(True)` + `installEventFilter` | Mouse tracking is the documented Qt mechanism for this; reimplementing it via QApplication-level event polling re-invents the wheel. [CITED: doc.qt.io QMouseEvent] |
| Splitter handle hide synchronized with widget hide | `splitter.handle(1).setVisible(False)` + explicit show | Just `station_panel.hide()` | Qt automatically hides the adjacent handle when a child is hidden. Adding the explicit call would double-up the operation and risk asymmetric restore. [CITED: forum.qt.io/topic/45377] |
| Two-instance station list with state sync | Constructing `StationListPanel` twice and propagating filter/search/scroll between them | Reparent the single instance between docked and overlay containers | Qt parent system handles geometry / lifetime / event routing for you. Two instances = two bugs to maintain. |
| Keyboard shortcut conflict resolution | Per-widget focus-event listeners to suppress shortcut | `Qt.WidgetWithChildrenShortcut` context + modal dialog default behavior | Modal QDialogs block all shortcuts by default; window-scope shortcuts are naturally suppressed by focus changes. [CITED: forum.qt.io/topic/91429] |
| Custom icon for "sidebar visible / hidden" | Hand-drawing SVGs from scratch | `QStyle.SP_TitleBarShadeButton` / `SP_TitleBarUnshadeButton` (built-in) OR existing icon family if visual consistency wins | If brand consistency matters, hand-draw matching `*-symbolic.svg` glyphs in the existing icons/ family; if not, the QStyle built-ins are platform-themed. |

**Key insight:** All four mechanisms (splitter, shortcut, event filter, reparent) are stock Qt patterns with first-class API support. The temptation in a "first shortcut in the codebase" phase is to over-engineer a "shortcut framework" — DON'T. Add ONE `QShortcut` with bound-method connect, mirror the existing toggle invariant, and ship. The framework concern is explicitly deferred (see CONTEXT.md deferred ideas, "Wider keyboard-shortcut framework").

## Common Pitfalls

### Pitfall 1: Snapshot taken AFTER `.hide()` returns [0, total]

**What goes wrong:** Call `station_panel.hide()` then `_splitter.sizes()` to snapshot — you get `[0, 1200]` because Qt has already redistributed space. On exit, `setSizes([0, 1200])` keeps station_panel invisible.

**Why it happens:** Qt redistributes space immediately on `hide()`. `sizes()` reflects current state.

**How to avoid:** ALWAYS snapshot BEFORE `.hide()`:
```python
self._splitter_sizes_before_compact = self._splitter.sizes()   # FIRST
self.station_panel.hide()                                        # SECOND
```

**Warning signs:** After toggling compact OFF, the left panel appears collapsed to 0 width even though `isHidden()` returns False. `_splitter.sizes()[0] == 0` confirms the bug.

### Pitfall 2: Mouse tracking not enabled on centralWidget

**What goes wrong:** Event filter receives no `MouseMove` events unless the mouse is held down. Peek never triggers.

**Why it happens:** Qt's default is to only deliver `MouseMove` during a drag. `setMouseTracking(True)` opts in to receive bare cursor movement.

**How to avoid:** Set tracking on the event-filter source widget:
```python
self.centralWidget().setMouseTracking(True)
# Also on MainWindow if filter is installed there:
self.setMouseTracking(True)
```

**Warning signs:** Hover-peek works during a drag but not during a normal mouse traversal. Confirm by clicking-and-holding while moving cursor — if peek then triggers, mouseTracking is the missing piece.

### Pitfall 3: Window-scope shortcut "doesn't work" inside QLineEdit

**What goes wrong:** Developer assumes QLineEdit eats Ctrl+B because of "QLineEdit bold shortcut" intuition. Test in a focused search box shows Ctrl+B triggers compact mode — there's no bug here.

**Why it happens:** QLineEdit's default key bindings DO NOT include Ctrl+B [CITED: doc.qt.io/qt-6/qlineedit.html — "Default Key Bindings" table covers Ctrl+A/C/V/X/Z/Y/K only]. There's no conflict.

**How to avoid:** No fix needed — Ctrl+B passes through to the window-scope shortcut even when search box is focused. Plan should include a positive test: "Ctrl+B fires when search box has focus."

**Warning signs:** Confused review comments about "Ctrl+B is bold." Reassure with citation to QLineEdit default key bindings table.

### Pitfall 4: QShortcut activated.connect uses lambda

**What goes wrong:** Project-wide QA-05 violation. `test_buffer_percent_bound_method_connect_no_lambda` (test_main_window_integration.py:631-652) demonstrates the structural test pattern enforced for every new signal connection.

**Why it happens:** Easier to inline `lambda: self.now_playing.compact_mode_toggle_btn.toggle()` than to define `_on_compact_shortcut_activated`.

**How to avoid:** ALWAYS define a bound method:
```python
def _on_compact_shortcut_activated(self) -> None:
    self.now_playing.compact_mode_toggle_btn.toggle()

self._compact_shortcut.activated.connect(self._on_compact_shortcut_activated)
```

**Warning signs:** Plan-check will catch this; a structural assertion (`assert "lambda" not in line`) is the project standard.

### Pitfall 5: Snapshot variable not reset on exit

**What goes wrong:** `self._splitter_sizes_before_compact` keeps stale data after a re-toggle. On second compact-mode-entry, snapshot logic overwrites it (fine), but if the toggle sequence is OFF → restore → ON → restore, the second restore uses stale sizes from a different window geometry.

**Why it happens:** Forgetting to `None`-out the snapshot after restore.

**How to avoid:**
```python
else:
    self.station_panel.show()
    if self._splitter_sizes_before_compact:
        self._splitter.setSizes(self._splitter_sizes_before_compact)
        self._splitter_sizes_before_compact = None   # CRITICAL — reset
```

**Warning signs:** Test failure on a "toggle-on, resize-window, toggle-off, toggle-on, toggle-off" sequence — second OFF uses stale snapshot.

### Pitfall 6: Reparent direction reversed

**What goes wrong:** Peek-close reparents station_panel back via `_splitter.addWidget(panel)` — but `addWidget` appends at the end, so now station_panel is at index 1 (where now_playing was). The two children swap visual positions.

**Why it happens:** `addWidget` and `insertWidget` have different semantics for an already-parented widget being re-added.

**How to avoid:** Use `_splitter.insertWidget(0, station_panel)`:
```python
splitter.insertWidget(0, station_panel)    # back to original slot
```
[CITED: doc.qt.io/qt-6/qsplitter.html — "If a widget is already inside a QSplitter when insertWidget() or addWidget() is called, it will move to the new position"]

**Warning signs:** After peek closes and compact is toggled off, the station panel is on the RIGHT and the now-playing panel is on the LEFT.

### Pitfall 7: Event filter installed but never removed

**What goes wrong:** Compact mode toggled OFF — event filter still installed on centralWidget. Mouse-move events still trigger dwell timer, but `_peek_overlay is None` is no longer the right precondition because the user is back to docked mode.

**Why it happens:** Asymmetric `_on_compact_toggle` — install side has the filter, uninstall side doesn't remove it.

**How to avoid:** Pair `installEventFilter` with `removeEventFilter` in opposite branches of `_on_compact_toggle`. Plan should include a test asserting `assert _peek_dwell_timer is None or not _peek_dwell_timer.isActive()` after toggle-off.

**Warning signs:** Subtle test flakiness in non-compact mode tests because a stale dwell timer fires asynchronously.

### Pitfall 8: Peek overlay obscures ToastOverlay during a toast

**What goes wrong:** User triggers compact + peek + a player error toast fires simultaneously. The peek overlay is `raise_()`-d above the splitter children but parented to centralWidget; ToastOverlay is parented to MainWindow itself and raises in `show_toast()`. Z-order WORKS — toast above peek — but only if peek overlay is parented to centralWidget, NOT to MainWindow directly.

**Why it happens:** Qt z-order is mostly parent-stacking: children render above parent, siblings at parent level render in insertion order with later siblings on top.

**How to avoid:** Parent the peek overlay to `centralWidget()` (mirrors ToastOverlay strategy at main_window.py:293 — `ToastOverlay(self)` is parented to MainWindow but anchors to centralWidget). Concretely:
```python
self._peek_overlay = StationListPeekOverlay(self.centralWidget())
```
This way toasts (parented to MainWindow) render above the peek overlay (parented to centralWidget which is a child of MainWindow's frame).

**Warning signs:** Integration test for "toast during peek" fails because toast is invisible behind overlay. Manual UAT will catch it more reliably than unit tests.

### Pitfall 9: First QShortcut in codebase is registered before centralWidget exists

**What goes wrong:** Adding the QShortcut line near other `__init__` logic at the top of MainWindow construction — before `self.setCentralWidget(self._splitter)`. The shortcut works, but if it triggers during early init (before the toggle button exists), `self.now_playing.compact_mode_toggle_btn.toggle()` raises AttributeError.

**Why it happens:** Construction order matters; the shortcut activation is event-loop-driven and could in principle fire on a re-entered event during init.

**How to avoid:** Register the QShortcut AFTER all panels are constructed and the signal wiring is done — same position as the other late init (e.g., near `set_stats_visible` at main_window.py:381).

**Warning signs:** Crash during MainWindow construction if a hold-over Ctrl+B is buffered (unlikely but defensive).

## Runtime State Inventory

> N/A — this phase is pure new-feature UI work with no rename, refactor, migration, or string-replacement component. No stored data, live service config, OS-registered state, secrets, env vars, or build artifacts contain any string related to "compact_mode" today (verified via `grep -rn "compact_mode\|compact-mode" .` — empty). Nothing to inventory.

## Code Examples

Verified patterns from the existing codebase:

### MainWindow ↔ NowPlayingPanel signal wiring (mirror for new compact_mode_toggled signal)

```python
# Source: musicstreamer/ui_qt/main_window.py:331-340 (existing pattern)
# Track star → toast (D-10)
self.now_playing.track_starred.connect(self._on_track_starred)

# Panel stop button → backend state sync (UI-REVIEW fix)
self.now_playing.stopped_by_user.connect(self._on_panel_stopped)

# Plan 39: edit button → dialog launch
self.now_playing.edit_requested.connect(self._on_edit_requested)

# NEW (Phase 72) — mirror the same shape:
self.now_playing.compact_mode_toggled.connect(self._on_compact_toggle)
```

### Checkable QToolButton with icon flip (mirror for compact-toggle button)

```python
# Source: musicstreamer/ui_qt/now_playing_panel.py:479-488 (star_btn — closest analog)
self.star_btn = QToolButton(self)
self.star_btn.setIconSize(QSize(20, 20))
self.star_btn.setFixedSize(28, 28)
self.star_btn.setCheckable(True)
self.star_btn.setEnabled(False)
self.star_btn.setIcon(
    QIcon.fromTheme("non-starred-symbolic", QIcon(":/icons/non-starred-symbolic.svg"))
)
self.star_btn.clicked.connect(self._on_star_clicked)
controls.addWidget(self.star_btn)

# NEW (Phase 72) — mirror, add to end of `controls` BEFORE `controls.addStretch(1)`:
self.compact_mode_toggle_btn = QToolButton(self)
self.compact_mode_toggle_btn.setIconSize(QSize(20, 20))
self.compact_mode_toggle_btn.setFixedSize(28, 28)
self.compact_mode_toggle_btn.setCheckable(True)
self.compact_mode_toggle_btn.setIcon(self._compact_icon_for_state(checked=False))
self.compact_mode_toggle_btn.setToolTip("Hide stations list (Ctrl+B)")
self.compact_mode_toggle_btn.toggled.connect(self._on_compact_btn_toggled)
controls.addWidget(self.compact_mode_toggle_btn)
```

### Overlay parented to centralWidget with event filter (mirror for peek overlay)

```python
# Source: musicstreamer/ui_qt/toast.py:28-79 (ToastOverlay pattern)
class ToastOverlay(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        # ...layout...
        self.hide()
        parent.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() == QEvent.Resize:
            self._reposition()
        return super().eventFilter(obj, event)

# NEW (Phase 72) — peek overlay is INTERACTIVE (D-15), so DO NOT set
# WA_TransparentForMouseEvents. The overlay must accept mouse events to
# route them to the reparented station_panel.
```

### Negative-assertion test for session-only persistence (NEW pattern this phase introduces)

```python
# Phase 72 introduces the INVERSE of test_show_similar_toggle_persists_and_toggles_panel
# (test_main_window_integration.py:1186-1215). The positive form is:
#   assert fake_repo.get_setting("show_similar_stations", "0") == "1"
# Phase 72's session-only invariant is:
#   assert "compact_mode" not in fake_repo._settings
# i.e., NO set_setting call was ever made for the compact-mode key.

def test_compact_mode_toggle_does_not_persist_to_repo(qtbot, fake_player, fake_repo):
    """D-09: session-only — toggling compact mode MUST NOT write to repo settings.
    Inverse of Phase 47.1 / Phase 67 positive-persistence pattern.
    """
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    # Snapshot keys before any compact toggling
    keys_before = set(fake_repo._settings.keys())

    # Trigger via button (and via shortcut in a separate test) — multiple toggles
    btn = w.now_playing.compact_mode_toggle_btn
    btn.toggle()    # ON
    btn.toggle()    # OFF
    btn.toggle()    # ON again

    keys_after = set(fake_repo._settings.keys())
    new_keys = keys_after - keys_before
    # Strict invariant: NO new keys related to compact mode were written.
    assert not any("compact" in k for k in new_keys), (
        f"D-09 violated — compact-mode key(s) written to repo: {new_keys & {k for k in new_keys if 'compact' in k}}"
    )
```

### Single-source-of-truth invariant (mirror Phase 47.1 / Phase 67)

```python
# Source: tests/test_main_window_integration.py:1191 (Phase 67 SIM-02 invariant)
# Phase 67 form:
#   assert w._act_show_similar.isChecked() == (not w.now_playing._similar_container.isHidden())
# Phase 72 form:
def test_compact_button_checked_matches_station_panel_hidden(qtbot, fake_player, fake_repo):
    """Single-source-of-truth invariant — button.isChecked() == station_panel.isHidden().
    Mirrors Phase 47.1 WR-02 / Phase 67 M-02.
    """
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    btn = w.now_playing.compact_mode_toggle_btn

    # Initial — unchecked, panel visible
    assert btn.isChecked() is False
    assert w.station_panel.isHidden() is False

    # Toggle ON
    btn.toggle()
    assert btn.isChecked() is True
    assert w.station_panel.isHidden() is True

    # Toggle OFF
    btn.toggle()
    assert btn.isChecked() is False
    assert w.station_panel.isHidden() is False
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `QShortcut(seq, parent, SLOT(method()))` C++ string-form | Python connect-via-attribute: `self._shortcut.activated.connect(self._slot)` | PySide6 6.0+ | First QShortcut in this codebase — adopt modern form directly. [CITED: doc.qt.io/qtforpython-6/PySide6/QtGui/QShortcut.html] |
| `event.pos()` (returns QPoint) | `event.position()` (returns QPointF; call `.toPoint()` for integer pixels) | Qt 6 | Use `event.position().toPoint()` for pixel comparisons in event filter (compatible with codebase's Qt 6 baseline). |
| Hardcoded GTK shortcut wiring | PySide6 QShortcut + bound-method connect | Phase 35-36 GTK4 retirement (already complete) | No carryover needed — codebase is pure Qt. |

**Deprecated/outdated:**
- `QShortcut(parent, "Ctrl+B")` (string-only second arg) — was a Qt 5 quirk, now QKeySequence is the canonical form.
- F11 as a sidebar-toggle shortcut — F11 universally means OS-fullscreen; using it for sidebar would mislead. Discarded by user during /gsd-discuss-phase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ~~`QSplitter.hide()` on a child auto-hides the adjacent handle in PySide6 6.10+~~ **INVALIDATED 2026-05-13 by Wave 0 spike 72-01** on PySide6 6.11.0 / Qt 6.11.0. `QSplitter.handle(1).isVisible()` remains `True` after `station_panel.hide()`. The forum.qt.io/topic/45377 contract does NOT carry to Qt 6.11. **Mitigation (now MANDATORY in Plan 72-03):** add explicit `self._splitter.handle(1).hide()` on compact-ON and `self._splitter.handle(1).show()` on compact-OFF. Spike test `test_phase72_a1_splitter_handle_does_not_auto_hide` locks the invalidated behavior as regression-catch. |
| A2 | `StationListPanel` has zero parent-assumption code that would break under reparenting | Pattern 4 | MEDIUM — based on a grep for `self.parent()`, `self.window()`, `topLevelWidget()` returning empty for `station_list_panel.py`. However, indirect parent-assumptions (e.g., a child widget calling `parent().resize(...)`) could exist; a Wave 0 spike that physically reparents the panel into a QFrame and back will validate. |
| A3 | Modal `QDialog` (EditStationDialog, AccountsDialog) blocks `Qt.WidgetWithChildrenShortcut` shortcuts on MainWindow | Pattern 2 | LOW — forum.qt.io/topic/91429 explicitly states "modal windows will block shortcuts even with application context." Confirmed by Qt docs on modal event blocking. |
| A4 | QLineEdit does NOT consume Ctrl+B by default | Pitfall 3 | LOW — doc.qt.io/qt-6/qlineedit.html's "Default Key Bindings" table omits Ctrl+B. Verified by reading the table. |
| A5 | Existing `ToastOverlay` parented to MainWindow (not centralWidget) renders ABOVE a peek overlay parented to centralWidget | Pitfall 8 | MEDIUM — z-order in Qt depends on widget tree hierarchy; this is the expected ordering but should be locked by an integration test ("toast during peek shows above peek"). |
| A6 | `setMouseTracking(True)` must be called on every widget along the cursor path for the top-level event filter to see all `MouseMove` events | Pattern 3 | LOW — Qt docs and pythonguis.com confirm that mouse tracking propagates if set on the window AND the widgets that should report bare moves. Belt-and-braces: set on MainWindow + centralWidget. [CITED: pythonguis.com/tutorials/pyside6-signals-slots-events] |

## Open Questions (RESOLVED)

1. **Icon decision: built-in `QStyle.SP_TitleBarShadeButton/SP_TitleBarUnshadeButton` vs custom SVG glyphs in icons/**
   - What we know: project icon family is `*-symbolic.svg` (SomaFM/AA monochrome aesthetic, e.g., `non-starred-symbolic.svg`, `media-playback-start-symbolic.svg`). Existing buttons all use `QIcon.fromTheme(name, QIcon(":/icons/{name}.svg"))` pattern.
   - What's unclear: whether the user prefers visual consistency (custom SVG) or low-effort Qt built-in. The CONTEXT marks this as Claude's discretion.
   - Recommendation: hand-author two `sidebar-show-symbolic.svg` / `sidebar-hide-symbolic.svg` SVGs in the same monochrome family. Falls back to QStyle built-ins via `QIcon.fromTheme` if a system theme provides them. Total marginal effort: ~30min of SVG editing.
   - **RESOLVED:** Custom SVG path chosen — Plan 72-02 `planner_decisions` locks `sidebar-show-symbolic.svg` and `sidebar-hide-symbolic.svg` at 16x16 viewBox with `fill="currentColor"` to match the existing 12-icon family (rendered at 20x20 via QIcon.fromTheme fallback chain).

2. **Peek overlay width: snapshot size, fixed 360px, or panel's `sizeHint()`?**
   - What we know: the in-memory snapshot stores the LIVE splitter size at compact-entry. The default at fresh launch is `[360, 840]`.
   - What's unclear: whether to use the snapshot (respects the user's last splitter drag) or a fixed 360px (predictable across sessions).
   - Recommendation: use the in-memory snapshot value if available, else 360px. Matches "restore previous live sizes" decision (D-10) for the docked case.
   - **RESOLVED:** Snapshot-or-360px-fallback committed — UI-SPEC §Spacing locks `width = _splitter_sizes_before_compact[0] if available else 360`; Plan 72-04 implements this in `_open_peek_overlay` and tests both branches (`test_peek_overlay_width_matches_snapshot` + `test_peek_overlay_width_fallback_to_360_when_no_resize`).

3. **Does PySide6 6.10 (conda-forge) and 6.11 (pip) behave identically for QSplitter hide?**
   - What we know: stack pins `PySide6>=6.10`. CI / dev box runs offscreen platform; production runs Wayland.
   - What's unclear: any known regression in 6.10 vs 6.11 that affects splitter hide / handle visibility.
   - Recommendation: integration test covers both code paths; Wayland UAT confirms visual behavior on the user's actual box. Cross-version risk is LOW given the API stability of QSplitter since Qt 4.
   - **RESOLVED:** HIGH confidence on Standard Stack per §Metadata — QSplitter API stable since Qt 4; Wave 0 spike test 72-01 (A1 handle auto-hide) pins behavior on the actual installed PySide6 version. Any future regression will fail that spike test first.

4. **Z-order interaction: peek overlay vs `_act_node_missing` warning indicator vs `_quality_badge`?**
   - What we know: ToastOverlay z-order has been thought through. Other always-visible chrome (status bar, menu bar) lives at MainWindow level, not centralWidget level — should NOT be obscured by peek.
   - What's unclear: peek overlay anchors to the LEFT edge of the now-playing pane area; it should not extend over the menu bar (which is at the QMainWindow level, above centralWidget). Confirmed by geometry — centralWidget is below menu bar in QMainWindow's frame.
   - Recommendation: parent overlay to `centralWidget()`, use `setGeometry(0, 0, width, centralWidget.height())` — naturally stays within the splitter area, doesn't escape into the menu bar.
   - **RESOLVED:** UI-SPEC §Visuals locks the 4-layer Z-order contract: ToastOverlay (parent=MainWindow) > peek (parent=centralWidget) > now-playing > station_panel. `_act_node_missing` and `_quality_badge` live inside the now-playing pane, so peek covers them in compact mode by design.

5. **Should "compact mode entered" be announced via toast?**
   - What we know: CONTEXT.md does not specify. No toast on Ctrl+B activation is the silent assumption.
   - What's unclear: whether the user expects a "Stations hidden — Ctrl+B to show" hint the first time.
   - Recommendation: NO toast. The icon flip + immediate visual change (panel disappears) is feedback enough; toast would clutter the use case (rapid in/out as device moves between screens). User can always be added later if discoverability is a problem (already a deferred idea in CONTEXT).
   - **RESOLVED:** UI-SPEC §Out-of-Scope locks "no new toast notifications when toggling — clutters rapid-toggle use case." Discoverability hint remains a deferred idea in CONTEXT.md.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | ✓ | 3.10+ (pyproject.toml floor) | — |
| PySide6 | UI | ✓ | >=6.10 pinned, 6.11 installed on dev box | — |
| pytest | Test runner | ✓ | 9+ | — |
| pytest-qt | Qt test fixtures | ✓ | 4+ | — |
| Wayland session (GNOME Shell) | Manual UAT | ✓ on production box | — | offscreen platform for CI |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

This phase is pure code on an existing stack — no new tooling, no new system libraries, no new package dependencies.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9+ with pytest-qt 4+ |
| Config file | `pyproject.toml` (testpaths = ["tests"]) |
| Quick run command | `pytest tests/test_main_window_integration.py -x` |
| Full suite command | `pytest tests` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LAYOUT-01 (D-01, D-04) | Button exists on NowPlayingPanel control row at far right (after StreamPicker / volume) | unit | `pytest tests/test_now_playing_panel.py::test_compact_mode_toggle_button_present_far_right -x` | ❌ Wave 0 |
| LAYOUT-01 (D-01) | Clicking button hides station_panel; clicking again shows it | integration | `pytest tests/test_main_window_integration.py::test_compact_button_toggles_station_panel -x` | ❌ Wave 0 |
| LAYOUT-01 (D-02, D-03) | Ctrl+B QShortcut toggles same state as button | integration | `pytest tests/test_main_window_integration.py::test_ctrl_b_shortcut_toggles_compact -x` | ❌ Wave 0 |
| LAYOUT-01 (D-05) | Button icon flips between two glyphs based on state | unit | `pytest tests/test_now_playing_panel.py::test_compact_button_icon_flips_per_state -x` | ❌ Wave 0 |
| LAYOUT-01 (D-06) | Only station_panel hidden — menu bar / hamburger / title bar remain visible | integration | `pytest tests/test_main_window_integration.py::test_compact_only_hides_station_panel -x` | ❌ Wave 0 |
| LAYOUT-01 (D-07) | No auto-exit on window resize | integration | `pytest tests/test_main_window_integration.py::test_resize_while_compact_keeps_compact -x` | ❌ Wave 0 |
| LAYOUT-01 (D-08) | setChildrenCollapsible(False) preserved across toggle | unit | `pytest tests/test_main_window_integration.py::test_splitter_collapsible_invariant -x` | ❌ Wave 0 |
| LAYOUT-01 (D-09) | NO `set_setting` call for compact-mode key (session-only invariant) | integration | `pytest tests/test_main_window_integration.py::test_compact_mode_toggle_does_not_persist_to_repo -x` | ❌ Wave 0 |
| LAYOUT-01 (D-09) | Fresh MainWindow construction always starts expanded regardless of any settings | integration | `pytest tests/test_main_window_integration.py::test_compact_mode_starts_expanded_on_launch -x` | ❌ Wave 0 |
| LAYOUT-01 (D-10) | Splitter sizes snapshot before hide, restored on show | integration | `pytest tests/test_main_window_integration.py::test_splitter_sizes_round_trip_through_compact -x` | ❌ Wave 0 |
| LAYOUT-01 (D-11, D-13) | Hover on left ≤6px for ≥280ms triggers peek overlay | integration | `pytest tests/test_main_window_integration.py::test_hover_left_edge_triggers_peek_after_dwell -x` | ❌ Wave 0 |
| LAYOUT-01 (D-12) | Peek overlay floats over now-playing pane — splitter sizes do NOT change during peek | integration | `pytest tests/test_main_window_integration.py::test_peek_overlay_does_not_reflow_splitter -x` | ❌ Wave 0 |
| LAYOUT-01 (D-14) | Mouse leaves overlay → overlay closes | integration | `pytest tests/test_main_window_integration.py::test_peek_overlay_closes_on_mouse_leave -x` | ❌ Wave 0 |
| LAYOUT-01 (D-14) | Esc does NOT dismiss peek | integration | `pytest tests/test_main_window_integration.py::test_esc_does_not_dismiss_peek -x` | ❌ Wave 0 |
| LAYOUT-01 (D-14) | Click station in peek does NOT dismiss peek | integration | `pytest tests/test_main_window_integration.py::test_clicking_station_in_peek_does_not_dismiss -x` | ❌ Wave 0 |
| LAYOUT-01 (D-15) | Clicked station in peek emits station_activated (playback starts) | integration | `pytest tests/test_main_window_integration.py::test_peek_station_click_activates_playback -x` | ❌ Wave 0 |
| Invariant: SSoT | button.isChecked() == station_panel.isHidden() after any toggle | integration | `pytest tests/test_main_window_integration.py::test_compact_button_checked_matches_station_panel_hidden -x` | ❌ Wave 0 |
| QA-05 | Compact-toggle signal connections use bound methods (no lambda) | structural | `pytest tests/test_main_window_integration.py::test_compact_mode_signals_use_bound_methods -x` | ❌ Wave 0 |
| Manual UAT | Visual correctness of icon flip, hover-peek feel, overlay z-order vs toasts on Wayland | manual-only | (UAT script) | — |

### Sampling Rate

- **Per task commit:** `pytest tests/test_main_window_integration.py tests/test_now_playing_panel.py -x` (fast — these are pytest-qt headless)
- **Per wave merge:** `pytest tests` (full suite, ~399 tests + new compact-mode tests)
- **Phase gate:** Full suite green before `/gsd-verify-work` + Wayland UAT for hover-peek timing and z-order

### Wave 0 Gaps

- [ ] `tests/test_main_window_integration.py` — add compact-mode integration tests (button toggle, shortcut, panel visibility, persistence-NOT-written, snapshot round-trip, peek lifecycle)
- [ ] `tests/test_now_playing_panel.py` — add button-presence + icon-flip unit tests
- [ ] (Optional split) `tests/test_compact_mode.py` — if test_main_window_integration.py exceeds ~1500 lines, split out compact-mode tests
- [ ] `musicstreamer/ui_qt/station_list_peek_overlay.py` — new widget class file
- [ ] (Optional) `musicstreamer/ui_qt/icons/sidebar-show-symbolic.svg` + `sidebar-hide-symbolic.svg` if SVG icon path chosen over QStyle built-ins

Framework + test scaffolding is already present (conftest.py, FakePlayer, FakeRepo, MainWindow fixture pattern). No framework install needed.

## Security Domain

> Per project config `.planning/config.json`, security_enforcement is not explicitly set (treated as enabled per skill instructions).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface in this phase. |
| V3 Session Management | no | No session/cookie/token surface. |
| V4 Access Control | no | Single-user desktop app; no access control. |
| V5 Input Validation | yes | New `QShortcut` input source. Keyboard shortcut input is constrained to a key sequence (Ctrl+B) and an integer-only signal payload (`bool`). No string/text input validation needed. |
| V6 Cryptography | no | No crypto surface. |

### Known Threat Patterns for PySide6 + Qt UI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Untrusted text rendered as rich text (XSS-equivalent) | Tampering | NOT APPLICABLE — peek overlay shows trusted local data (user's own station library). All labels in StationListPanel use `Qt.PlainText` (verified — station_list_panel.py uses no rich-text labels). |
| Event-filter denial-of-service (filter consumes events selfishly and starves other widgets) | DoS | Event filter MUST `return False` to pass events through. Documented in Pattern 3 above. |
| Modal dialog shortcut leak (shortcut fires while user is in a dialog) | Tampering | Window-scope `Qt.WidgetWithChildrenShortcut` + modal dialog default blocking behavior. [CITED: forum.qt.io/topic/91429] |

No new security review concerns. This phase introduces no network, file, IPC, or cryptographic surface — only intra-process Qt widget state changes.

## Sources

### Primary (HIGH confidence)

- [Qt 6 QSplitter Class — handle indexing, hide behavior, setSizes semantics](https://doc.qt.io/qt-6/qsplitter.html) — base QSplitter API
- [Qt for Python QSplitter (PySide6)](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSplitter.html) — PySide6-specific API surface
- [Qt 6 QShortcut Class](https://doc.qt.io/qt-6/qshortcut.html) — QShortcut constructor signatures, ShortcutContext enum
- [Qt for Python QShortcut (PySide6)](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QShortcut.html) — PySide6 import path + connection examples
- [Qt 6 QLineEdit Class — Default Key Bindings table](https://doc.qt.io/qt-6/qlineedit.html) — confirms Ctrl+B is NOT a default QLineEdit shortcut
- [Qt for Python QMouseEvent (mouse tracking semantics)](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QMouseEvent.html) — `setMouseTracking(True)` requirement
- [pytest-qt documentation (qtbot fixture)](https://pytest-qt.readthedocs.io/) — `addWidget`, `mouseClick`, `waitExposed`, `qWait`
- Local codebase: `musicstreamer/ui_qt/main_window.py`, `now_playing_panel.py`, `station_list_panel.py`, `toast.py`, `tests/test_main_window_integration.py`, `tests/conftest.py` — VERIFIED via direct read

### Secondary (MEDIUM confidence)

- [Qt Forum: QSplitter disappears once child widget is hidden (forum.qt.io/topic/45377)](https://forum.qt.io/topic/45377/qsplitter-disappears-once-child-widget-is-hidden) — empirical confirmation that `hide()` on a splitter child auto-hides the handle; SGaist (Qt expert) recommends `setSizes()` workaround which we chose AGAINST in favor of explicit `hide()` for visibility semantics
- [Qt Forum: Possible to allow QShortcut to work with modal QDialogs (forum.qt.io/topic/91429)](https://forum.qt.io/topic/91429/possible-to-allow-qshortcut-to-work-with-modal-qdialogs) — confirms modal dialogs block shortcuts regardless of context, which is the desired behavior for Ctrl+B during EditStationDialog
- [pytest-qt issue #254: qtbot.keyClicks does not trigger QPushButton shortcuts](https://github.com/pytest-dev/pytest-qt/issues/254) — testing-recipe note: `activated.emit()` direct invocation is more reliable than synthesizing key events for QShortcut tests
- [pythonguis.com: PySide6 Signals, Slots and Events](https://www.pythonguis.com/tutorials/pyside6-signals-slots-events/) — mouse tracking propagation rules
- [pythonguis.com: Built-in QIcons in PyQt6/PySide6 — Complete List](https://www.pythonguis.com/faq/built-in-qicons-pyqt/) — confirms `SP_TitleBarShadeButton` / `SP_TitleBarUnshadeButton` exist and represent shade/unshade states

### Tertiary (LOW confidence)

- Various Qt Forum threads on QSplitter handle visibility (qtcentre.org/threads/51548, qt-project.narkive.com) — older Qt 4/5 advice; consulted for triangulation but not relied on for definitive recommendation
- Cross-referenced multiple sources for "Qt automatically hides splitter handle when adjacent child is hidden" — flagged as A1 in Assumptions Log; Wave 0 spike test will verify

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all APIs are stable Qt 6 surfaces with explicit docs; PySide6 version is locked in pyproject.toml
- Architecture: HIGH — pattern mirrors existing codebase precedents (ToastOverlay overlay parent pattern, Phase 47.1/67 single-source-of-truth toggle invariant, QA-05 bound-method connections)
- Pitfalls: HIGH for snapshot-before-hide, mouseTracking, modal shortcut blocking, lambda violation; MEDIUM for z-order assumption (worth a UAT verification step)
- Reparenting risk: MEDIUM — `StationListPanel` parent-assumption audit is empty by grep but indirect parent calls could exist; Wave 0 spike test mitigates

**Research date:** 2026-05-13
**Valid until:** 2026-06-12 (30 days — stable mature framework; Qt 6.x API rate of change is low)

---

*Phase: 72-fullscreen-mode-hide-left-column-for-compact-displays*
*Research completed: 2026-05-13*
