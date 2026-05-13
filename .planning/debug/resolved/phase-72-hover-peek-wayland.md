---
slug: phase-72-hover-peek-wayland
status: fix_applied
trigger: phase 72 hover-peek fails on live wayland — sit 10 seconds, nothing happens
created: 2026-05-13
updated: 2026-05-13
related_phase: 72
related_plans: [72-04]
fix_commit: 43ba666
awaiting: user re-runs UAT-02/03/05 on live Wayland to confirm resolution
---

# Debug: Phase 72 hover-peek fails on live Wayland

## Symptoms

**Expected:** In compact mode (`Ctrl+B`), hovering the left 4px of the window for ~280ms should open a station-list peek overlay (per UI-SPEC §Interaction Contract, D-11/D-12/D-13).

**Actual:** "Sit for 10 secs, nothing happens." Hover at the left edge — no peek opens, no overlay appears. The 280ms dwell timer apparently never fires (or its callback `_open_peek_overlay` runs but the overlay never shows). Rapid traversal also produces nothing — consistent with "no MouseMove events delivered" rather than "dwell timer fires but overlay logic broken."

**Error messages:** None. No exception, no toast, no log output. Silent failure.

**Timeline:** Newly introduced in Phase 72 Plan 04 (`72-04-PLAN.md`, commit `c0e8d3b` → merged at `9b40c52`). Never worked on live Wayland.

**Reproduction:**
1. Launch `python -m musicstreamer` on Linux Wayland (GNOME Shell, DPR=1.0).
2. Press `Ctrl+B` to enter compact mode — station_panel hides correctly (UAT-01 passed).
3. Move cursor to the leftmost ~4 pixels of the window.
4. Hold cursor stationary for 10+ seconds.
5. **Expected:** peek overlay slides in after ~280ms.
6. **Actual:** nothing happens.

**Other UAT signals:**
- UAT-01 (icon flip): PASS — button click + Ctrl+B both work, slot fires, station_panel.hide()/show() succeed
- UAT-04 (bottom-bar overlap fix): PASS — core deliverable works
- UAT-03, UAT-05: blocked on UAT-02

**Automated tests that DO pass:** 16 tests in `tests/test_phase72_peek_overlay.py` all green via `pytest-qt`. They send synthetic `MouseMove` events via `QTest.mouseMove` or `qtbot.mouseMove(widget, QPoint(2, 100))` — bypass the real Wayland event-delivery path.

## Hypotheses to investigate (priority order)

### H1: `setMouseTracking(True)` not propagating to children on Wayland
**Reasoning:** Plan 04 sets `MainWindow.setMouseTracking(True)` and `centralWidget().setMouseTracking(True)`. Under Qt 6 / Wayland, `centralWidget()` IS the QSplitter. The splitter and its child widgets (still-visible `now_playing_panel`) may not have mouse-tracking, so bare `MouseMove` events at the splitter's leftmost pixels never bubble up to the event filter on centralWidget.
**Test:** Add diagnostic log inside MainWindow.eventFilter to count incoming MouseMove events, regardless of x-coordinate. If 0 events arrive when cursor moves over the window in compact mode, mouse tracking is the bottleneck.
**Outcome:** Partially correct — `setMouseTracking` does not propagate, but the deeper root cause is event-filter installation location (see H5 result + Root Cause below).

### H2: Event filter not installed because `_install_peek_hover_filter` was never called
**Reasoning:** Plan 04 fills the `_install_peek_hover_filter` stub in MainWindow. The slot is supposed to be called from `_on_compact_toggle` on compact-ON. If the call site was not wired up, the filter never installs.
**Test:** Read main_window.py for the call site. Confirm `self._install_peek_hover_filter()` is invoked in the if-branch of `_on_compact_toggle` (compact-ON path).
**Outcome:** ELIMINATED — main_window.py:878 confirms `_install_peek_hover_filter()` IS called on compact-ON. The filter IS installed; it's just installed on the wrong receiver.

### H3: GNOME Shell intercepts cursor events at window edge for resize handles
**Reasoning:** Under Wayland with client-side decorations (CSD), the leftmost few pixels may be a window-edge resize handle owned by GTK/GNOME Shell. Qt's `MouseMove` events never fire there because the compositor routes those pixels to the shell.
**Test:** Visually identify whether the cursor changes to a resize arrow at x=0..2. If yes, the trigger zone overlaps the resize handle.
**Outcome:** NOT THE PRIMARY CAUSE — the bug is upstream of any edge-pixel question (events never reach centralWidget at any x-coordinate). May still be a secondary tuning concern after the primary fix.

### H4: Compact-mode QSplitter handle still receives events at the left edge
**Reasoning:** A1 spike showed the splitter handle does NOT auto-hide in PySide6 6.11 — Plan 72-03 added explicit `handle(1).hide()`. But the splitter itself (the centralWidget container) may still consume MouseMove events at its drag-handle's position even when the handle is hidden, swallowing them before they reach the event filter.
**Test:** Log event types arriving at centralWidget when cursor is at left edge.
**Outcome:** Adjacent to root cause — the splitter is not "swallowing" events; events simply never target the splitter at all because `now_playing` (the splitter's child filling the entire content area in compact mode) is the receiver.

### H5: Event filter's `obj` check excludes centralWidget
**Reasoning:** Plan 04's `MainWindow.eventFilter(self, obj, event)` may check `if obj is self._central_widget` but the actual event source might be a sub-widget (the splitter handle, or `now_playing` panel itself if mouse-tracked). The filter then never sees the MouseMove because it filters by obj-identity.
**Test:** Remove the `obj is` guard temporarily, log obj.objectName() / type, see which widget the events actually come from.
**Outcome:** CONFIRMED — this is the root cause direction. See Root Cause section. `eventFilter` at main_window.py:1024 gates on `obj is self.centralWidget()`, but in real Qt event delivery the MouseMove never targets centralWidget (the QSplitter); it targets `now_playing` (the right pane, which fills the compact-mode viewport).

## Current Focus

**hypothesis:** ROOT CAUSE FOUND — event filter installed on wrong receiver.

**test:** N/A — root cause established by source analysis (no live diagnostic needed, but optional confirmation step proposed).

**next_action:** Either (a) plant a 30-second-lifetime global application-event-filter diagnostic that logs MouseMove receiver types, ask user to re-run UAT-02, then verify the prediction (zero events targeting centralWidget; all targeting `NowPlayingPanel` or its descendants) — or (b) apply the fix directly with confidence. User choice.

## Evidence

- 2026-05-13: UAT-02 reported failure. Sit 10 seconds at left edge, no peek opens. All 41 automated tests still pass — failure is Wayland-specific.
- 2026-05-13: UAT-01 (icon flip) and UAT-04 (overlap fix) pass — compact mode entry/exit works correctly; failure is isolated to the hover-peek event delivery path.
- 2026-05-13: Source analysis — `musicstreamer/ui_qt/main_window.py:1024` — `if event.type() == QEvent.MouseMove and obj is self.centralWidget():` filters by **receiver identity**. The filter is installed on centralWidget at line 933 (`self.centralWidget().installEventFilter(self)`).
- 2026-05-13: Source analysis — `musicstreamer/ui_qt/main_window.py:293,302-303,308` — centralWidget IS the QSplitter; its two children are `station_panel` (left, index 0) and `now_playing` (right, index 1). In compact mode `station_panel` is hidden (line 876), so the entire content viewport is occupied by `now_playing`.
- 2026-05-13: Qt event-delivery semantics — `QApplication` looks up which widget is **under the cursor** and delivers MouseMove to that widget. Events do not bubble through a parent widget's event filter unless the filter is installed on the actual receiver (or on `QApplication.instance()` as a global filter). The eventFilter installed on the splitter therefore sees MouseMove only when the cursor is over the **splitter's own** pixels — i.e. its drag handle. In compact mode the handle is hidden (line 877), so the splitter has effectively zero pixel area exposed to the cursor.
- 2026-05-13: `setMouseTracking(True)` at main_window.py:931-932 is set only on MainWindow and centralWidget — NOT on `now_playing` or its descendants. Even if the filter were installed correctly, the now_playing children would silently swallow MouseMove without delivering it unless a button is held. (Two compounding defects.)
- 2026-05-13: Test analysis — `tests/test_phase72_peek_overlay.py:76-95` (`_send_mouse_move`) uses `QApplication.sendEvent(widget, ev)` with `widget = window.centralWidget()` (test line 121). This **forces** centralWidget to be the receiver, short-circuiting the real Qt dispatcher. The 16 passing tests therefore validate filter logic but cannot detect a wrong-receiver bug. (Matches MEMORY pattern: "GStreamer mock tests are a blind spot" — synthetic-event tests pass through whatever you hand them.)

## Eliminated

- **H2** (filter not installed at call site): main_window.py:878 confirms the call IS made on compact-ON.

## Root Cause

**Specialist hint:** typescript→N/A; closest match is `general` / `engineering:debug` (PySide6/Qt — no dedicated skill).

**Statement:** In `musicstreamer/ui_qt/main_window.py`, `_install_peek_hover_filter` installs `self` as an event filter on `centralWidget()` (the QSplitter), and `eventFilter` gates incoming events on `obj is self.centralWidget()`. On a real Qt event-delivery path (any OS — not Wayland-specific in principle, but only visible on real systems), MouseMove events are delivered to the widget **under the cursor**. In compact mode the QSplitter's only direct child filling the viewport is `now_playing` (and recursively its descendants); MouseMove events therefore target `now_playing` (or deeper), never centralWidget. The filter never fires; the dwell timer is never started; the overlay never opens.

**Why the 16 automated tests pass:** `tests/test_phase72_peek_overlay.py:_send_mouse_move` calls `QApplication.sendEvent(window.centralWidget(), ev)`, hand-feeding the event directly to centralWidget and bypassing `QApplication`'s receiver-resolution stage. The test simulates "the filter is firing" not "the OS delivers events to a widget the filter watches."

**Secondary defect (independent but compounding):** `setMouseTracking(True)` is set only on MainWindow + centralWidget. Even after the receiver bug is fixed, `now_playing` and its descendants still need tracking enabled so MouseMove fires without a held button. The cleanest universal fix avoids per-widget tracking entirely (see fix proposal below).

## Proposed Fix

**Approach (idiomatic Qt 6 for "watch the cursor anywhere in the window"):**

Install the event filter on **`QApplication.instance()`** instead of on `centralWidget()`. A global QApplication event filter receives **every** QMouseEvent before delivery, regardless of which widget is under the cursor — there is no need for `setMouseTracking` propagation, no need to chase splitter children, no Wayland edge-case interaction. In the filter:

1. Bail unless `event.type() == QEvent.MouseMove`.
2. Bail unless compact mode is currently active (cheap guard: `self.now_playing.compact_mode_toggle_btn.isChecked()`).
3. Bail unless the cursor is inside MainWindow's frame (`self.geometry().contains(QCursor.pos())`).
4. Map global cursor pos to `centralWidget()` local coords via `centralWidget().mapFromGlobal(QCursor.pos())`.
5. Apply the existing `pos.x() <= _PEEK_TRIGGER_ZONE_PX` zone check and the dwell-timer start/stop logic.

The receiver-identity guard `obj is self.centralWidget()` is removed (would always be false now). The cleanup path becomes `QApplication.instance().removeEventFilter(self)`. The `setMouseTracking(True)` calls on MainWindow + centralWidget can stay (harmless) or be removed (no longer needed).

**Patch sketch (`musicstreamer/ui_qt/main_window.py`):**

```python
# _install_peek_hover_filter
def _install_peek_hover_filter(self) -> None:
    from PySide6.QtWidgets import QApplication
    QApplication.instance().installEventFilter(self)

# _remove_peek_hover_filter
def _remove_peek_hover_filter(self) -> None:
    from PySide6.QtWidgets import QApplication
    QApplication.instance().removeEventFilter(self)
    if self._peek_dwell_timer is not None:
        if self._peek_dwell_timer.isActive():
            self._peek_dwell_timer.stop()
        self._peek_dwell_timer = None

# eventFilter
def eventFilter(self, obj, event):
    if event.type() == QEvent.MouseMove:
        # Guard 1: only active in compact mode
        if not self.now_playing.compact_mode_toggle_btn.isChecked():
            return super().eventFilter(obj, event)
        # Guard 2: cursor must be inside this MainWindow's frame
        global_pos = QCursor.pos()
        if not self.frameGeometry().contains(global_pos):
            return super().eventFilter(obj, event)
        # Map to centralWidget-local coords
        cw = self.centralWidget()
        pos = cw.mapFromGlobal(global_pos)
        in_zone = 0 <= pos.x() <= _PEEK_TRIGGER_ZONE_PX and 0 <= pos.y() <= cw.height()
        no_visible_peek = (
            self._peek_overlay is None
            or not self._peek_overlay.isVisible()
        )
        if in_zone and no_visible_peek:
            if self._peek_dwell_timer is None:
                self._peek_dwell_timer = QTimer(self)
                self._peek_dwell_timer.setSingleShot(True)
                self._peek_dwell_timer.timeout.connect(self._open_peek_overlay)
            if not self._peek_dwell_timer.isActive():
                self._peek_dwell_timer.start(_PEEK_DWELL_MS)
        else:
            if (
                self._peek_dwell_timer is not None
                and self._peek_dwell_timer.isActive()
            ):
                self._peek_dwell_timer.stop()
    return super().eventFilter(obj, event)
```

Requires adding `QCursor` to existing PySide6.QtGui import.

**Test changes needed:**

The 16 existing tests use `_send_mouse_move(cw, x, y)` with `widget = window.centralWidget()`. Two options:

(a) Keep existing tests + add a `QApplication.sendEvent(QApplication.instance(), ev)` variant — but `sendEvent(app, MouseEvent)` is not how QApplication-installed filters fire in real life (the filter fires on app.notify, before dispatch). Better:

(b) Update `_send_mouse_move` to use `QTest.mouseMove(window, QPoint(x, y))` (the real cursor-position-based API) — this exercises the actual receiver-resolution path. Add an explicit assertion that the global filter fires regardless of which descendant the synthetic move targets. This closes the synthetic-event blind spot for future regressions.

(c) Cheapest interim: keep existing tests as-is (they cover filter logic), and add ONE new live-integration test that monkey-patches `QCursor.pos` to a fixed point and posts `QEvent.MouseMove` events to `now_playing` (a non-centralWidget child), asserting the dwell timer still starts. This is the test that would have caught the bug.

I recommend (b) + a new "filter fires for events targeting non-centralWidget receivers" regression test.

## Sources to check

- `musicstreamer/ui_qt/main_window.py` — peek-overlay stubs filled by Plan 04 (search "peek", "_install_peek_hover_filter", "_open_peek_overlay", "_PEEK_TRIGGER_ZONE_PX", "_PEEK_DWELL_MS", "eventFilter")
- `musicstreamer/ui_qt/station_list_peek_overlay.py` — overlay class (Plan 04 new file). Confirmed OK — Leave detection on the overlay-self path is correct because the overlay IS a top-level-style widget at peek-open time.
- `.planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/72-04-SUMMARY.md` — implementation notes including the parent-change deviation (overlay parented to MainWindow not centralWidget)
- `.planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/72-RESEARCH.md` — A6 assumption "setMouseTracking(True) must be called on every widget along the cursor path" — this assumption was acknowledged but not fully implemented; the QApplication-filter approach moots the need entirely.
- `tests/test_phase72_peek_overlay.py` — the 16 passing automated tests; understand WHY they pass (synthetic events bypass real OS event routing).
