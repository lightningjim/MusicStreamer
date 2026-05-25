---
phase: 72-fullscreen-mode-hide-left-column-for-compact-displays
reviewed: 2026-05-13T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - musicstreamer/ui_qt/icons.qrc
  - musicstreamer/ui_qt/icons_rc.py
  - musicstreamer/ui_qt/icons/sidebar-hide-symbolic.svg
  - musicstreamer/ui_qt/icons/sidebar-show-symbolic.svg
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - musicstreamer/ui_qt/station_list_peek_overlay.py
  - tests/test_phase72_assumptions.py
  - tests/test_phase72_compact_toggle.py
  - tests/test_phase72_integration.py
  - tests/test_phase72_now_playing_panel.py
  - tests/test_phase72_peek_overlay.py
findings:
  blocker: 1
  warning: 6
  info: 5
  total: 12
status: issues_found
---

# Phase 72: Code Review Report

**Reviewed:** 2026-05-13
**Depth:** standard
**Files Reviewed:** 12 (7 source + 5 test) — `icons_rc.py` flagged Info-only per generated-file policy; SVGs verified XSS-free.
**Status:** issues_found

## Summary

Phase 72 introduces a compact-display toggle that hides the left station list and a hover-peek overlay floating it back over the now-playing pane. The implementation is generally careful — bound-method connects throughout (no lambdas in new code), defensive `try/except` around all Qt slot bodies, an explicit single-source-of-truth invariant (`button.isChecked() == station_panel.isHidden()`), explicit `splitter.handle(1).hide()/show()` (correctly compensating for the invalidated A1 assumption), and a Wave 0 spike that locked the two load-bearing Qt assumptions before any production code was written.

That said, the implementation has one BLOCKER-grade defect and several worthwhile WARNING-grade concerns:

1. **BLOCKER**: `closeEvent` does **not** remove the QApplication-level global event filter or clean up the dwell timer when the window closes while compact mode is active. If the user quits while in compact mode, the filter remains installed on a soon-to-be-destroyed `MainWindow` and the lazy-constructed `_peek_overlay` (also a `MainWindow`-parented widget) is not explicitly torn down. Most-common path: window destruction destroys the C++ filter object, but a queued/post-event `MouseMove` already in the queue can dispatch through a dead filter → crash. The Phase 41/62 closeEvent shutdown discipline is explicit about cleaning up timers and async resources before `super().closeEvent`; the Phase 72 additions broke that pattern.
2. **WARNING (D-14 hole)**: the hover-peek overlay can re-open behind a modal `QDialog`. The Ctrl+B `QShortcut` is correctly scoped with `Qt.WidgetWithChildrenShortcut` to be eaten by modals (RESEARCH A3), but the global mouse-move event filter is **not** modal-aware — it fires regardless of `QApplication.activeModalWidget()`.
3. **WARNING**: an empty `sizes()` (zero-children edge) would silently skip restore in the compact-OFF branch because `if self._splitter_sizes_before_compact:` is truthiness, not `is not None`. The same code path correctly snapshots, so this is asymmetric.
4. **WARNING**: the dwell timer is reconstructed on every compact cycle (`_peek_dwell_timer = None` in remove-filter), which guarantees parent-owned timers proliferate across many toggle cycles (mitigated by Qt's parent ownership, but the previous timer is never explicitly `.deleteLater()`'d).
5. **WARNING**: race between `_on_compact_toggle(False)` peek-release and a still-pending `_open_peek_overlay` invocation queued in the dwell timer's `timeout` signal. If the dwell timer fires after the OFF-branch ran the release guard, `_open_peek_overlay` will reparent `station_panel` out of the splitter and back into the overlay AFTER the panel has been shown — leaving a phantom peek and an invisible station list.
6. **WARNING**: test-quality issues in `test_phase72_peek_overlay.py` — two tests rely on `qtbot.wait(280)` rather than `qtbot.waitUntil(...)`, which the same test file otherwise prefers and which the integration tests adopted; these are CI flake candidates.
7. **WARNING (silent failure)**: `eventFilter` uses `pos.x() < cw.width()` (exclusive upper) but `pos.y() < cw.height()` (exclusive upper) — Qt's mapFromGlobal can produce values equal to width/height in some edge cases; the asymmetric strict-less-than with `pos.x() <= _PEEK_TRIGGER_ZONE_PX` (inclusive zone) is internally consistent but the cw-bound check would mis-classify a cursor exactly on the right/bottom edge as "outside" and cancel an in-flight dwell.

The test suite is otherwise solid (assumption locks, integration round-trips, source-grep gates for QA-05 lambda discipline, D-09 negative-persistence checks). Test coverage of the BLOCKER (closeEvent cleanup) and the modal-peek hole is absent — a fix should add at least one regression test for each.

## Blocker Issues

### BL-01: `closeEvent` leaves global QApplication event filter installed (use-after-free risk)

**File:** `musicstreamer/ui_qt/main_window.py:659-683`

**Issue:** When the user closes the window while in compact mode, the QApplication-level event filter installed by `_install_peek_hover_filter` (line 939) is never removed. The lazily-constructed `_peek_overlay` (line 984) and the `_peek_dwell_timer` (line 1055) are also not explicitly torn down. Mouse-move events already queued in Qt's event dispatcher will continue to be routed to `MainWindow.eventFilter` after `super().closeEvent(event)` initiates widget destruction — this is exactly the queued-slot-after-shutdown class of bug that the Phase 62 `BUG-09` comment at lines 663-666 was explicit about preventing.

The same closeEvent already does the right thing for the underrun tracker, media keys, and the AA poll loop (lines 667-682). The Phase 72 additions introduced a new long-lived resource (the global filter) and a new timer (`_peek_dwell_timer`) without extending the closeEvent shutdown sequence.

Concretely, on a Wayland session where the user does `Ctrl+B` to compact, then immediately closes the window, this sequence can race:
1. closeEvent fires, `super().closeEvent(event)` begins MainWindow destruction.
2. A `MouseMove` event delivered to any widget under the cursor is dispatched through the still-installed filter.
3. The filter accesses `self.station_panel`, `self.centralWidget()`, `self._peek_overlay`, `self._peek_dwell_timer` on a partially-destroyed Python/Qt object.

Even when no race occurs, the dwell timer's QTimer remains alive (parented to MainWindow → cleaned up by Qt) but the filter installed on `QApplication.instance()` outlives the parent reference assumption.

**Fix:**

```python
def closeEvent(self, event: QCloseEvent) -> None:
    """..."""
    # Phase 72 / BL-01: remove the global hover-peek filter and stop the
    # dwell timer BEFORE super().closeEvent() destroys widget state. Mirror
    # the Phase 62 BUG-09 closeEvent discipline — no queued slot may fire
    # against a partially-destroyed MainWindow.
    try:
        self._remove_peek_hover_filter()
    except Exception as exc:
        _log.warning("peek hover filter teardown failed: %s", exc)
    # Optionally explicitly tear down the peek overlay if visible — Qt's
    # parent-owned cleanup handles destruction, but the explicit release
    # restores splitter shape so any save-on-close hook sees consistent state.
    try:
        if self._peek_overlay is not None and self._peek_overlay.isVisible():
            self._peek_overlay.release(self._splitter, self.station_panel, None)
    except Exception as exc:
        _log.warning("peek overlay teardown failed: %s", exc)

    try:
        self._player.shutdown_underrun_tracker()
    # ... rest unchanged
```

Add a regression test that constructs `MainWindow`, toggles compact ON, closes the window, and asserts neither `QApplication.instance()._event_filters` (via Qt introspection) contains the MainWindow nor that subsequent synthetic MouseMove events trigger an exception.

## Warnings

### WR-01: Global hover-peek filter is not modal-aware — peek opens behind QDialog

**File:** `musicstreamer/ui_qt/main_window.py:919-1069`

**Issue:** The `Ctrl+B` `QShortcut` is correctly scoped to `Qt.WidgetWithChildrenShortcut` (line 501) so a modal `QDialog.exec()` (EditStationDialog, AccountsDialog, DiscoveryDialog, ImportDialog, GBSSearchDialog, ThemePickerDialog, AccentColorDialog, EqualizerDialog, SettingsImportDialog) blocks it — RESEARCH A3 documented this and `test_modal_dialog_blocks_ctrl_b` locks it.

The hover-peek event filter has no equivalent gate. When a modal dialog is open while compact mode is active and the user moves their cursor near the left edge of the now-obscured main window (e.g., bumping the cursor while reading the dialog), the dwell timer fires and `_open_peek_overlay` reparents `station_panel` out of the splitter onto the overlay — behind the modal, invisible. When the user dismisses the modal, the peek may be visible but un-dismissible because their cursor never entered the overlay, so the mouse-leave path cannot fire. The next click on the now-playing pane (which is partly underneath the peek) may misroute.

This is a D-14 hole: dismiss-via-mouse-leave only works if the cursor was actually inside the overlay rect.

**Fix:** add an early-return in `eventFilter` when a modal dialog is active:

```python
def eventFilter(self, obj, event):
    if event.type() != QEvent.MouseMove:
        return super().eventFilter(obj, event)
    # WR-01: skip dwell when a modal dialog is up — the peek would open
    # behind it and be undismissible until the user re-enters the overlay rect.
    if QApplication.activeModalWidget() is not None:
        if (self._peek_dwell_timer is not None
                and self._peek_dwell_timer.isActive()):
            self._peek_dwell_timer.stop()
        return super().eventFilter(obj, event)
    if not self.station_panel.isHidden():
        return super().eventFilter(obj, event)
    # ... rest unchanged
```

Add a regression test analogous to `test_modal_dialog_blocks_ctrl_b` that opens a modal, sends a MouseMove inside the trigger zone, waits past the dwell, and asserts `_peek_overlay is None or not isVisible()`.

### WR-02: Race between dwell-timer expiry and compact-OFF can reparent panel after restore

**File:** `musicstreamer/ui_qt/main_window.py:874-899` and `1053-1062`

**Issue:** The dwell timer is a single-shot 280ms QTimer connected to `_open_peek_overlay`. If the user starts a hover (timer armed), then quickly hits `Ctrl+B` to leave compact mode before the 280ms elapses, the OFF branch runs but does NOT stop the dwell timer until `_remove_peek_hover_filter` near the end (line 898) — and that line is executed AFTER `station_panel.show()` and `setSizes(...)`. If the timer's `timeout` was already queued onto the main thread event queue (between the OFF branch's lines), the queued `_open_peek_overlay` slot would then fire after the OFF branch returns, reparenting `station_panel` out of the splitter back into the overlay — which is invisible because compact mode is OFF and the overlay was never shown for this cycle.

Result: `station_panel` is invisible (parented to overlay), now-playing pane sits where it always was, splitter has a zombie left slot, and the user has no way to recover except another Ctrl+B-Ctrl+B cycle.

The likelihood is low (sub-280ms window) but real, especially because the spec encourages keyboard-driven workflow.

**Fix:** stop the dwell timer FIRST in the OFF branch, before any layout mutations, AND verify the timer is not pending dispatch when calling release:

```python
else:
    # WR-02: stop the dwell timer FIRST so a queued _open_peek_overlay
    # cannot fire after the splitter has been restored.
    if (self._peek_dwell_timer is not None
            and self._peek_dwell_timer.isActive()):
        self._peek_dwell_timer.stop()
    if (self._peek_overlay is not None
            and self._peek_overlay.isVisible()):
        self._peek_overlay.release(self._splitter, self.station_panel, None)
    self.station_panel.show()
    # ... rest unchanged
```

Note that `_remove_peek_hover_filter` already stops the timer, but it runs AFTER `setSizes` and AFTER `station_panel.show()`. Moving the stop to the top of the OFF branch closes the window.

### WR-03: `if self._splitter_sizes_before_compact:` is falsy for `[]` — asymmetric with snapshot side

**File:** `musicstreamer/ui_qt/main_window.py:895`

**Issue:** The snapshot side (line 875) writes `self._splitter.sizes()` unconditionally. The restore side (line 895) gates on truthiness, which treats `None`, `[]`, and any other empty container as "no snapshot" and silently skips restore. The annotation is `list[int] | None`, so `[]` would only happen if `sizes()` ever returned empty (zero-children splitter) — which the existing two-child layout precludes.

But the asymmetry is fragile: a future refactor that adds/removes splitter children, or any code path that explicitly sets `self._splitter_sizes_before_compact = []` (for example, a defensive reset on error), would cause silent restore loss.

**Fix:** use explicit `is not None` check:

```python
if self._splitter_sizes_before_compact is not None:
    self._splitter.setSizes(self._splitter_sizes_before_compact)
    self._splitter_sizes_before_compact = None
```

### WR-04: Dwell timer is reconstructed each cycle instead of stopped + reused

**File:** `musicstreamer/ui_qt/main_window.py:941-955`

**Issue:** `_remove_peek_hover_filter` sets `self._peek_dwell_timer = None` rather than just stopping it. On the next compact-ON cycle, the eventFilter (line 1054) constructs a fresh `QTimer(self)`. Across many toggle cycles (which is exactly the workflow the feature is built for — moving between displays), the parent-owned QTimer chain grows. Qt's parent ownership eventually reclaims them, but the previous timer is never explicitly `deleteLater()`'d.

The docstring at line 948-949 documents this as intentional ("forces the next compact-ON cycle to lazy-reconstruct the timer"), but doesn't explain why reconstruction is preferable to `.stop()`. The implicit reason — that a reconstructed timer guarantees a clean disconnect from any previously-firing slot — is over-cautious because QTimer is single-shot and connected to a bound method.

**Fix:** stop the timer but keep the instance, OR if reconstruction is truly desired, `.deleteLater()` the old timer to make Qt reclaim it immediately:

```python
def _remove_peek_hover_filter(self) -> None:
    QApplication.instance().removeEventFilter(self)
    if self._peek_dwell_timer is not None:
        if self._peek_dwell_timer.isActive():
            self._peek_dwell_timer.stop()
        # Keep the instance for reuse — eliminates per-cycle QTimer allocation.
```

### WR-05: Bounds check inconsistency in eventFilter — strict-less-than on width/height

**File:** `musicstreamer/ui_qt/main_window.py:1039`

**Issue:** The bounds check `0 <= pos.x() < cw.width() and 0 <= pos.y() < cw.height()` uses strict-less-than on the upper bound, but Qt's coordinate space treats the rect as `[0, width()]` (inclusive of the right edge in some contexts, e.g., when the cursor is on the very last pixel column). A cursor at `(cw.width(), 50)` would be classified as "outside centralWidget" and the dwell timer would be stopped — even though the user has not actually left the window.

This is mostly a minor false-negative (the cursor immediately moves back inside on the next event), but on slow CI / very wide windows with sub-pixel rounding, it can cause flaky cancellation of an in-progress dwell.

The same line uses `<=` on the trigger zone width check (line 1048: `pos.x() <= _PEEK_TRIGGER_ZONE_PX`), making the upper-bound conventions inconsistent across the same function.

**Fix:** use `QRect.contains(pos)` for the centralWidget bounds check — it's the idiomatic Qt way and matches the rect's inclusion semantics:

```python
in_cw = cw.rect().contains(pos)
```

### WR-06: Two peek-overlay tests use `qtbot.wait(280)` instead of `waitUntil` — CI flake risk

**File:** `tests/test_phase72_peek_overlay.py:142-145` and `208-211`

**Issue:** `test_dwell_fires_after_280ms_in_zone` and `test_global_filter_fires_when_event_targets_now_playing` both call `qtbot.wait(280)` after the partial-dwell wait, then assert `_peek_overlay is not None and isVisible() is True`. Under offscreen platform load (CI) or a slow Wayland event-loop drain, the timer's `timeout` slot can fire a few ms after the 280ms mark, causing the assertion to read a still-None overlay.

The same test file's `test_zone_exit_cancels_dwell` uses `qtbot.wait(300)` (giving a 20ms grace), and the integration tests (`tests/test_phase72_integration.py:244, 306, 433`) correctly use `qtbot.waitUntil(_make_peek_visible_predicate(window), timeout=1000)`. The two flaky cases should adopt the same `waitUntil` pattern.

**Fix:** replace the fixed wait with a predicate-based wait:

```python
def test_dwell_fires_after_280ms_in_zone(window, qtbot, monkeypatch):
    btn = window.now_playing.compact_mode_toggle_btn
    btn.click()  # compact ON
    cw = window.centralWidget()
    assert window._peek_overlay is None or not window._peek_overlay.isVisible()
    _send_mouse_move(cw, 2, 100, monkeypatch=monkeypatch)
    qtbot.wait(50)  # Dwell not yet complete — peek must stay closed
    assert window._peek_overlay is None or not window._peek_overlay.isVisible()
    # WR-06: waitUntil() instead of fixed wait(280) — offscreen event-loop
    # drain can lag the wall clock by tens of ms on slow CI.
    def _peek_visible():
        return (window._peek_overlay is not None
                and window._peek_overlay.isVisible())
    qtbot.waitUntil(_peek_visible, timeout=1000)
```

The same predicate (and existing `_make_peek_visible_predicate` helper from the integration test) should be lifted into the peek-overlay test module too.

## Info

### IN-01: `icons_rc.py` is auto-generated — flag confirms no hand-edits required

**File:** `musicstreamer/ui_qt/icons_rc.py:1-4`

**Issue:** Header banner says "All changes made in this file will be lost!" — confirming it's `pyside6-rcc`-generated. No findings against the file itself, but flagging here to confirm it should not be edited by hand. The `.qrc` was correctly updated (lines 16-17) and the `.py` file regenerated. The file should remain in source control but be regenerated on every `.qrc` change.

**Fix:** none required — the project pattern is correct. Consider adding a `make` target or pre-commit hook (`pyside6-rcc musicstreamer/ui_qt/icons.qrc -o musicstreamer/ui_qt/icons_rc.py`) to prevent drift.

### IN-02: SVG icons verified XSS-free

**File:** `musicstreamer/ui_qt/icons/sidebar-hide-symbolic.svg` and `sidebar-show-symbolic.svg`

**Issue:** Both new SVGs are static `<svg>` with a single `<path>` element. No `<script>`, no `onload`/`onerror`, no `javascript:` URIs, no external references. Safe to bundle.

**Fix:** none.

### IN-03: Dead/forward-compat parameter on overlay `release()`

**File:** `musicstreamer/ui_qt/station_list_peek_overlay.py:120-138`

**Issue:** `release()` accepts `restore_sizes: list[int] | None` but the parameter is never used inside the method (and both call sites in `main_window.py:891, 1011` pass `None`). The docstring explicitly notes this is intentional ("part of the public signature for forward compatibility"), so this is more of a maintainability flag than a defect.

**Fix:** either delete the parameter (YAGNI) and update both call sites, or add a `# noqa: ARG002 — see docstring "forward compatibility"` annotation and add a unit test that exercises the parameter so it cannot quietly fall out of use.

### IN-04: Pre-existing lambda usage in MainWindow (not phase-72 code)

**File:** `musicstreamer/ui_qt/main_window.py:1093, 1111`

**Issue:** Two `lambda:` signal connects exist in `_on_new_station_clicked` and `_on_edit_requested` — both pre-date Phase 72. The QA-05 grep-based source-test in `test_phase72_compact_toggle.py:232-252` is scoped narrowly to lines containing `compact_mode_toggled.connect` or `_compact_shortcut.activated.connect`, so it correctly does not catch these legacy lambdas.

**Fix:** none required for Phase 72. Mentioned for completeness — a project-wide `test_no_lambda_in_signal_connects` would catch these and align with QA-05 intent.

### IN-05: Magic numbers `60_000` and `300_000` in `_reschedule_aa_poll`

**File:** `musicstreamer/ui_qt/now_playing_panel.py:1791`

**Issue:** Hardcoded poll cadences `60_000` (60s) and `300_000` (5min) appear inline. Phase 72 didn't introduce them but they were touched indirectly via the now-playing-panel review scope. Other tuning constants in the file (`_GBS_QUEUE_MAX_ROWS = 10` at line 72, `_PEEK_DWELL_MS = 280` at main_window.py:68) are module-level constants with comments — the AA poll cadences should follow that convention.

**Fix:** lift to module-level constants:

```python
_AA_POLL_INTERVAL_FAST_MS = 60_000   # 60s when actively playing a DI.fm station
_AA_POLL_INTERVAL_SLOW_MS = 300_000  # 5min otherwise
```

This is a Phase 68 concern surfaced because the file was in review scope. Not blocking Phase 72.

---

_Reviewed: 2026-05-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
