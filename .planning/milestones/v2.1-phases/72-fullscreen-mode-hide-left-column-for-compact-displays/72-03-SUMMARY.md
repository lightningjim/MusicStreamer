---
phase: 72
plan: 03
subsystem: ui/qt-main-window
tags: [wave-2, layout-01, qshortcut-first, qsplitter, qa-05, d-09-session-only, tdd, a1-invalidated]
requires:
  - "72-01 (Wave 0 spike — A1 invalidated, A2 confirmed) — completed at ca4be24"
  - "72-02 (NowPlayingPanel.compact_mode_toggle_btn + Signal + set_compact_button_icon helper) — completed at 884b7f7"
provides:
  - "musicstreamer/ui_qt/main_window.py — _on_compact_toggle slot + _on_compact_shortcut_activated slot + four Plan-04 stub methods (_install_peek_hover_filter, _remove_peek_hover_filter, _open_peek_overlay, _close_peek_overlay) + _splitter_sizes_before_compact / _peek_overlay / _peek_dwell_timer instance vars + Ctrl+B QShortcut registration (first in codebase) + initial-state push (D-09 constant False, no repo read)"
  - "tests/test_phase72_compact_toggle.py — 12 integration tests (10 behavior-adding RED-then-GREEN, 2 invariant/negative guards that hold pre- and post-impl)"
affects:
  - ".planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/72-04-PLAN.md — Plan 04 will grep for the marker '# TODO Plan 04: insert peek-release guard here' and replace it with the overlay-release guard; will fill bodies of the four Plan-04 stub methods"
  - ".planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/deferred-items.md — appended a new entry for a pre-existing Qt teardown crash in a specific cross-file ordering"
tech_stack_added: []
tech_stack_patterns:
  - "QShortcut(QKeySequence(...), parent, context=Qt.WidgetWithChildrenShortcut) — first QShortcut in the codebase (D-03); establishes the window-scope shortcut-registration pattern for future phases"
  - "single-source-of-truth toggle (Phase 47.1 WR-02 / Phase 67 M-02 mirror) — button.toggle() drives the slot; the shortcut activates the button rather than calling the slot directly"
  - "in-memory snapshot-and-restore for QSplitter sizes (Pitfall 1: snapshot BEFORE hide; Pitfall 5: reset to None after restore); session-only (D-09)"
  - "explicit splitter.handle(1).hide()/.show() — REQUIRED per Wave 0 spike on PySide6 6.11 (A1 INVALIDATED); the handle does NOT auto-hide when its adjacent child hides"
  - "stub-method hand-off contract — Plan 03 declares four `pass`-body methods that the toggle slot calls; Plan 04 fills bodies without re-wiring entry points"
  - "TDD RED → GREEN cycle with separate commits per phase"
key_files_created:
  - "tests/test_phase72_compact_toggle.py (273 lines, 12 tests)"
key_files_modified:
  - "musicstreamer/ui_qt/main_window.py (+147 / -1; imports, instance vars, signal connect, initial-state push, QShortcut registration, _on_compact_toggle slot, _on_compact_shortcut_activated slot, four Plan-04 stub methods)"
  - ".planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/deferred-items.md (+1 entry — pre-existing cross-file Qt teardown crash; out of scope per SCOPE BOUNDARY rule)"
decisions:
  - "D-02 / D-03 locked: Ctrl+B QShortcut registered at MainWindow scope (Qt.WidgetWithChildrenShortcut context); first shortcut in the codebase"
  - "Wave 0 A1 invalidation HONORED: explicit self._splitter.handle(1).hide() and .show() calls present in the slot. This deviates from the plan body lines 201/220 (which inherited pre-Wave-0 wording saying handle calls should NOT appear); the plan frontmatter must_haves #3-4 and 72-02-SUMMARY recommendation #2 override the inline body — see Deviations section."
  - "Single-source-of-truth wiring locked: _on_compact_shortcut_activated calls compact_mode_toggle_btn.toggle(), NOT _on_compact_toggle directly — keyboard and mouse paths converge on the same button-driven signal."
  - "D-09 invariants locked by two negative-assertion tests (test_compact_mode_toggle_does_not_persist_to_repo + test_compact_mode_starts_expanded_on_launch); zero repo I/O for any compact-* key."
  - "Plan-04 hand-off marker emitted as `# TODO Plan 04: insert peek-release guard here` (the first line of the compact-OFF else-branch). Plan 04 will grep-and-replace this exact string."
metrics:
  duration_seconds: 534
  duration_human: "~8min 54sec"
  tasks_completed: 1
  files_created: 1
  files_modified: 2
  test_count_added: 12
  test_pass_rate: "12/12 PASS for the new file; plan-specified verify (test_phase72_compact_toggle.py + test_main_window_integration.py) 78 passed."
  completed: "2026-05-13"
---

# Phase 72 Plan 03: MainWindow compact-toggle wiring — Summary

**One-liner:** Wired the MainWindow half of compact mode — Ctrl+B QShortcut
(first in the codebase) + central `_on_compact_toggle` slot with explicit
`splitter.handle(1).hide()/show()` (per Wave 0 A1 invalidation) and
snapshot-before-hide / reset-after-restore ordering + single-source-of-truth
shortcut→button→slot flow + session-only D-09 invariants (zero repo I/O for
any compact-* key) + four Plan-04 stub methods plus the `# TODO Plan 04:
insert peek-release guard here` hand-off marker so Plan 04 only fills bodies
and replaces one marker line.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1-RED  | Failing tests for MainWindow compact wiring   | `6fd6d86` | `tests/test_phase72_compact_toggle.py` (new) |
| 1-GREEN | _on_compact_toggle + Ctrl+B QShortcut + stubs | `1399ee8` | `musicstreamer/ui_qt/main_window.py` |

TDD cycle: RED (`6fd6d86`) → GREEN (`1399ee8`). No REFACTOR step — the
implementation directly mirrors the Phase 47.1 / Phase 67 toggle precedent
plus the 72-02-SUMMARY recommendation §2 snippet, so there is no
cleanup target.

## Final Source Locations

| Element | File | Line |
| ------- | ---- | ---- |
| `from PySide6.QtGui import ... QKeySequence, QShortcut` | `musicstreamer/ui_qt/main_window.py` | 34 |
| `self._splitter_sizes_before_compact: list[int] \| None = None` | `musicstreamer/ui_qt/main_window.py` | 296 |
| `self._peek_overlay = None` (Plan 04 lazy-construct stub) | `musicstreamer/ui_qt/main_window.py` | 299 |
| `self._peek_dwell_timer = None` (Plan 04 lazy-construct stub) | `musicstreamer/ui_qt/main_window.py` | 300 |
| `self.now_playing.compact_mode_toggled.connect(self._on_compact_toggle)` | `musicstreamer/ui_qt/main_window.py` | 376 |
| Initial-state push `self.station_panel.setVisible(...)` (D-09 constant False) | `musicstreamer/ui_qt/main_window.py` | 415 |
| QShortcut registration `self._compact_shortcut = QShortcut(...)` | `musicstreamer/ui_qt/main_window.py` | 477 |
| `self._compact_shortcut.activated.connect(self._on_compact_shortcut_activated)` | `musicstreamer/ui_qt/main_window.py` | 482 |
| `def _on_compact_toggle(self, checked)` | `musicstreamer/ui_qt/main_window.py` | 818 |
| Snapshot BEFORE hide (Pitfall 1) | `musicstreamer/ui_qt/main_window.py` | 854 |
| `self._splitter.handle(1).hide()` (Wave 0 A1 invalidation) | `musicstreamer/ui_qt/main_window.py` | 856 |
| `self._install_peek_hover_filter()` call | `musicstreamer/ui_qt/main_window.py` | 857 |
| `# TODO Plan 04: insert peek-release guard here` marker | `musicstreamer/ui_qt/main_window.py` | 859 |
| `self._splitter.handle(1).show()` (Wave 0 A1 invalidation, symmetric) | `musicstreamer/ui_qt/main_window.py` | 861 |
| Snapshot reset to None (Pitfall 5) | `musicstreamer/ui_qt/main_window.py` | 864 |
| `self._remove_peek_hover_filter()` call | `musicstreamer/ui_qt/main_window.py` | 865 |
| `def _on_compact_shortcut_activated(self)` | `musicstreamer/ui_qt/main_window.py` | 868 |
| `def _install_peek_hover_filter` (Plan 04 stub) | `musicstreamer/ui_qt/main_window.py` | 885 |
| `def _remove_peek_hover_filter` (Plan 04 stub) | `musicstreamer/ui_qt/main_window.py` | 890 |
| `def _open_peek_overlay` (Plan 04 stub) | `musicstreamer/ui_qt/main_window.py` | 895 |
| `def _close_peek_overlay` (Plan 04 stub) | `musicstreamer/ui_qt/main_window.py` | 900 |

## Slot Implementation

The central toggle slot lives at lines 818-866 of `main_window.py`. Its
ordering is LOAD-BEARING — both the snapshot-before-hide and the
reset-after-restore are independently locked by tests
(`test_splitter_sizes_round_trip_through_compact` exercises both):

```python
def _on_compact_toggle(self, checked: bool) -> None:
    if checked:
        self._splitter_sizes_before_compact = self._splitter.sizes()   # Pitfall 1: BEFORE hide
        self.station_panel.hide()
        self._splitter.handle(1).hide()                                # Wave 0 A1 invalidation
        self._install_peek_hover_filter()
    else:
        # TODO Plan 04: insert peek-release guard here
        self.station_panel.show()
        self._splitter.handle(1).show()
        if self._splitter_sizes_before_compact:
            self._splitter.setSizes(self._splitter_sizes_before_compact)
            self._splitter_sizes_before_compact = None                 # Pitfall 5: reset
        self._remove_peek_hover_filter()
    self.now_playing.set_compact_button_icon(checked)
```

The shortcut slot is a one-liner that drives the button (single source of
truth):

```python
def _on_compact_shortcut_activated(self) -> None:
    self.now_playing.compact_mode_toggle_btn.toggle()
```

## Deviations from Plan

### [Rule 1 - Bug] Plan body says `handle(1).hide()/show()` must NOT appear; Wave 0 spike + frontmatter say they MUST appear

- **Found during:** Plan reading (before any code was written).
- **Issue:** The plan file `72-03-PLAN.md` has an internal contradiction:
  - **Frontmatter `must_haves.truths` lines 19-20** explicitly require:
    > "Compact ON: snapshot is taken BEFORE station_panel.hide() (Pitfall 1); station_panel hidden; **explicit `self._splitter.handle(1).hide()` call required** — Wave 0 spike 72-01 INVALIDATED A1 on PySide6 6.11"
    > "Compact OFF: station_panel.show() called; **explicit `self._splitter.handle(1).show()` call required**"
  - **Inline body line 201** says the opposite:
    > "Per RESEARCH A1 result (from Plan 01 SUMMARY) — do NOT call self._splitter.handle(1).hide() explicitly; Qt auto-hides the handle when the child is hidden. Plan 01's test locks this behavior."
  - **Acceptance criterion line 220** restates the wrong direction:
    > "Handle gate (RESEARCH A1): `grep -E "_splitter\.handle\(1\)\.hide|_splitter\.handle\(1\)\.show" musicstreamer/ui_qt/main_window.py` returns no matches"

  The Wave 0 SUMMARY (72-01) confirms A1 was INVALIDATED — `handle.isVisible()` is `True` after `station_panel.hide()` on PySide6 6.11.0. The 72-02 SUMMARY recommendation #2 also explicitly says these explicit calls are REQUIRED.

- **Resolution:** Followed the frontmatter `must_haves`, the Wave 0 SUMMARY, the 72-02 SUMMARY recommendation, and the orchestrator's CRITICAL directive (all four agree). The inline body lines 201/220 inherited the pre-Wave-0 wording that nobody re-edited after the A1 spike result. Both `self._splitter.handle(1).hide()` (line 856) and `self._splitter.handle(1).show()` (line 861) appear in the slot.
- **Files modified:** `musicstreamer/ui_qt/main_window.py` (the slot at lines 856 + 861 inverts what the inline acceptance criterion would have produced).
- **Commits:** `1399ee8` (GREEN feat commit explicitly cites this deviation in its commit message).
- **Tests:** No test in `test_phase72_compact_toggle.py` directly asserts handle visibility — the Wave 0 spike test `test_splitter_handle_autohides_when_child_hidden` in `test_phase72_assumptions.py` already locks the A1 contract on PySide6 6.11 (the handle stays visible until explicitly hidden). A future Plan 03 follow-up could add a `test_compact_mode_explicit_handle_hide_and_show` test if the orchestrator prefers an explicit binding; not added now because (a) Wave 0 already locks the underlying contract and (b) the GREEN tests prove the slot does the right thing end-to-end via the visible-panel observable.

### test_modal_dialog_blocks_ctrl_b — context-property fallback (documented test docstring choice)

- **Type:** Test methodology (not a code deviation).
- **Issue:** Plan 03 Task 1's `<behavior>` block allowed a fallback: "If pytest-qt cannot reliably simulate modal-blocking in offscreen mode, fall back to verifying the shortcut's context property == Qt.WidgetWithChildrenShortcut".
- **Resolution:** Used the fallback path. Offscreen mode lacks a real focus chain (Qt input-method routing is partial under `QT_QPA_PLATFORM=offscreen`), so a strong-form modal-blocks-shortcut test would either hang on `dialog.exec()` or pass for the wrong reason. The context property is the Qt-documented precondition that makes modal-blocking work; locking it locks the necessary half of the contract that pytest-qt CAN reliably verify. The test docstring explicitly says so:

  > "Strong-form modal simulation is unreliable in offscreen mode (no real focus chain), so the test verifies the necessary-but-sufficient precondition: the shortcut's `context` property equals `Qt.WidgetWithChildrenShortcut`."

  Real modal-blocking behavior would be exercised during UAT (manual verification with EditStationDialog open).

## Verification Results

| Check | Result |
| ----- | ------ |
| `pytest tests/test_phase72_compact_toggle.py -v` | 12 passed |
| `pytest tests/test_phase72_compact_toggle.py tests/test_main_window_integration.py -x -v` (plan-specified) | 78 passed |
| `pytest tests/test_main_window_integration.py` (regression) | 66 passed |
| `pytest tests/test_phase72_assumptions.py tests/test_phase72_now_playing_panel.py tests/test_phase72_compact_toggle.py tests/test_main_window_integration.py` | 88 passed |
| `python -c "from musicstreamer.ui_qt.main_window import MainWindow; assert hasattr(MainWindow, '_on_compact_toggle')"` | exit 0 |
| `grep -nc "^from PySide6.QtGui import.*QShortcut" main_window.py` | 1 |
| `grep -c "QShortcut(" main_window.py` | 1 |
| `grep -c "_on_compact_toggle" main_window.py` | 5 (≥ 3) |
| `grep -c "_splitter_sizes_before_compact" main_window.py` | 5 (≥ 4) |
| Pitfall 1 source-order (snapshot BEFORE hide) | PASS — snapshot at slot-line 37, hide at slot-line 38 |
| Pitfall 5 source-order (reset AFTER restore) | PASS — setSizes at slot-line 46, reset to None at slot-line 47 |
| `grep -E "compact.*connect.*lambda" main_window.py` | 0 matches (QA-05 OK) |
| `grep -E "(set_setting\|get_setting).*compact" main_window.py` | 1 match — INSIDE a `#` comment block documenting the D-09 invariant; no executable call. Acceptance criterion's intent (no I/O) satisfied. |
| `grep -E "_act_compact\|action.*[Cc]ompact" main_window.py` | 0 matches (D-01 OK — no hamburger entry) |
| `grep -c "Qt.WidgetWithChildrenShortcut" main_window.py` | 2 — 1 executable (line 480) + 1 docstring reference (line 467). RESEARCH A3 context locked. |
| `grep -c "# TODO Plan 04: insert peek-release guard here" main_window.py` | 1 (plan 04 grep target present) |
| `grep -E "QShortcut\|QKeySequence\|setShortcut" musicstreamer/ \| grep -v main_window.py` | 0 matches (D-03 OK — first shortcut in codebase) |
| Explicit Wave 0 A1 invalidation: `grep -E "_splitter\.handle\(1\)\.hide\|_splitter\.handle\(1\)\.show" main_window.py` | 4 matches — 2 executable calls (lines 856, 861) + 2 docstring references; intentional and load-bearing per Wave 0 + frontmatter must_haves |

## Known Stubs

Four intentional stubs in `main_window.py`:

| Method | Line | Body | Plan 04 contract |
| ------ | ---- | ---- | ---------------- |
| `_install_peek_hover_filter` | 885 | `pass` | Install mouse-move event filter for left-edge hover detection |
| `_remove_peek_hover_filter` | 890 | `pass` | Uninstall the hover filter; cancel pending dwell timer |
| `_open_peek_overlay`         | 895 | `pass` | Lazy-construct `StationListPeekOverlay`; show anchored to centralWidget |
| `_close_peek_overlay`        | 900 | `pass` | Hide the overlay (called from overlay's mouse-leave eventFilter) |

These are documented in the plan's <objective> section as Plan-04 hand-off
stubs. The toggle slot already calls `_install_peek_hover_filter` /
`_remove_peek_hover_filter`, so Plan 04 only fills the bodies without
re-wiring the entry points. The `# TODO Plan 04: insert peek-release guard
here` marker at line 859 is the single grep-replace target.

These stubs do NOT block Phase 72's mid-phase goal (compact-mode core
toggle via mouse + Ctrl+B works fully today); they are deliberate Wave 2 /
Wave 3 hand-off contracts.

## Threat Flags

None. Plan 03 introduces:
- One first-of-its-kind keyboard shortcut (`Ctrl+B` window-scope) — payload
  is `bool` (button toggled state). T-72-03 (modal dialog shortcut leak) is
  mitigated by `Qt.WidgetWithChildrenShortcut` context (per RESEARCH A3 /
  forum.qt.io/topic/91429). T-72-04 (payload validation) is degenerate —
  `bool` has no string/path/SQL injection surface.
- No new I/O, no auth, no network, no file system, no IPC.

Per the plan's `<threat_model>`: T-72-03 mitigated by context-property
lock (test_modal_dialog_blocks_ctrl_b); T-72-04 accepted (n/a — V5 input
validation degenerate).

## Self-Check: PASSED

- **Created files exist:**
  - `tests/test_phase72_compact_toggle.py` — 273 lines, 12 tests collected
    and PASS (`pytest -v` exit 0).
- **Modified files contain the changes:**
  - `musicstreamer/ui_qt/main_window.py` — verified `_on_compact_toggle`
    defined at line 818, `_compact_shortcut = QShortcut(...)` at line 477,
    initial-state push at line 415, signal connect at line 376.
- **Commits exist in the worktree branch `worktree-agent-a76662ee8191b7ed1`:**
  - `6fd6d86` `test(72-03): RED — failing tests for MainWindow compact-toggle wiring` — `git log --oneline | grep 6fd6d86` PASS.
  - `1399ee8` `feat(72-03): wire compact-mode toggle in MainWindow` — `git log --oneline | grep 1399ee8` PASS.
- **TDD gate compliance:** `test(72-03)` commit at `6fd6d86` precedes
  `feat(72-03)` at `1399ee8` (RED before GREEN). Behavior-adding under the
  MVP+TDD predicate (tdd="true" frontmatter + <behavior> block +
  non-test source file in <files>). RED/GREEN sequence verified.
- **Acceptance criteria:** All gates in `<acceptance_criteria>` pass (see
  Verification Results above); two minor false-positives noted in line
  with their criterion (the `Qt.WidgetWithChildrenShortcut` count is 2
  due to a docstring; the `(set_setting|get_setting).*compact` grep matches
  one comment line documenting the D-09 invariant — both are documentation,
  not executable code).
- **Success criteria (from plan `<success_criteria>`):**
  - Compact mode end-to-end works via button click AND Ctrl+B: VERIFIED
    by `test_compact_button_toggles_station_panel` +
    `test_ctrl_b_shortcut_toggles_compact`.
  - Splitter sizes round-trip with no drift: VERIFIED by
    `test_splitter_sizes_round_trip_through_compact`.
  - Single-source-of-truth invariant: VERIFIED by
    `test_compact_button_checked_matches_station_panel_hidden` and the
    fact that `_on_compact_shortcut_activated` calls
    `compact_mode_toggle_btn.toggle()`.
  - D-09 invariant: VERIFIED by
    `test_compact_mode_toggle_does_not_persist_to_repo` +
    `test_compact_mode_starts_expanded_on_launch`.
  - QA-05 invariant: VERIFIED by
    `test_compact_mode_signal_connections_no_lambda`.
  - Modal dialogs block Ctrl+B: VERIFIED via context-property fallback
    (`test_modal_dialog_blocks_ctrl_b`).
  - Peek-overlay hooks present as stubs: VERIFIED by inspection — four
    `pass`-bodied methods at lines 885 / 890 / 895 / 900.

---

*Plan 72-03 completed: 2026-05-13*
*Phase: 72-fullscreen-mode-hide-left-column-for-compact-displays*
