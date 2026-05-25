---
phase: 72-fullscreen-mode-hide-left-column-for-compact-displays
verified: 2026-05-13T00:00:00Z
status: passed
score: 13/13 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: null
  previous_score: null
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 72: Fullscreen Mode — Hide Left Column for Compact Displays — Verification Report

**Phase Goal (ROADMAP.md:614-616):** Add a toggleable "fullscreen"/compact mode that hides the left column so the bottom-bar controls stop compressing and overlapping when the window is moved to a small/secondary display. Mode must be quick to enter and exit (Ctrl+B keyboard shortcut + QToolButton on the now-playing pane — no hamburger entry per D-01) so the user can flip in and out as they move the device between screens. Hover-to-peek overlay on the left edge (4px zone, 280ms dwell) reveals the station list without exiting compact mode. Session-only state (no SQLite persistence — D-09). Verify on Linux Wayland (GNOME Shell) at DPR=1.0.

**Verified:** 2026-05-13
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                          | Status      | Evidence                                                                                                                                                                                                                                                                                                                                                |
| --- | ---------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Ctrl+B keyboard shortcut + button on now-playing both toggle the same state                    | VERIFIED    | `main_window.py:498-503` registers `QShortcut(QKeySequence("Ctrl+B"), self, context=Qt.WidgetWithChildrenShortcut)` → `_on_compact_shortcut_activated` which calls `self.now_playing.compact_mode_toggle_btn.toggle()` (line 909). Button's `toggled` → `compact_mode_toggled` → `_on_compact_toggle`. Single source of truth = the button's checked state. Locked by `test_ctrl_b_shortcut_toggles_compact`, `test_compact_button_toggles_station_panel`. |
| 2   | Left column hidden, right pane fills width on compact ON; restored on OFF                      | VERIFIED    | `main_window.py:876` `self.station_panel.hide()` on ON branch; `:893` `self.station_panel.show()` on OFF branch. Locked by `test_compact_button_toggles_station_panel`, `test_compact_only_hides_station_panel`.                                                                                                                                       |
| 3   | Splitter handle explicitly hidden/shown (A1 invalidation finding)                              | VERIFIED    | `main_window.py:877` `self._splitter.handle(1).hide()` on ON; `:894` `self._splitter.handle(1).show()` on OFF. Wave 0 spike 72-01 INVALIDATED RESEARCH A1 (auto-hide does not happen on PySide6 6.11); regression locked by `test_splitter_handle_autohides_when_child_hidden` in `test_phase72_assumptions.py`.                                          |
| 4   | Splitter sizes round-trip via in-memory snapshot (D-10, Pitfall 1)                             | VERIFIED    | `main_window.py:875` snapshot captured BEFORE `hide()` (Pitfall 1); `:895-897` restores via `setSizes(...)` and resets snapshot to None (Pitfall 5). Locked by `test_splitter_sizes_round_trip_through_compact`, `test_multiple_toggle_cycles_preserve_sizes`.                                                                                              |
| 5   | Session-only persistence (D-09) — no repo.set_setting/get_setting for compact-mode key         | VERIFIED    | `grep set_setting/get_setting` in `main_window.py` returns ZERO compact-mode-keyed calls. `:436-438` initial state forced from constant `False` rather than repo. Locked by `test_compact_mode_toggle_does_not_persist_to_repo`, `test_compact_mode_starts_expanded_on_launch`, `test_compact_button_no_repo_setting_write`, `test_no_compact_setting_written_after_full_lifecycle`. |
| 6   | Icon flips per state (D-05) — sidebar-show ↔ sidebar-hide + tooltip flip                       | VERIFIED    | `now_playing_panel.py:1084-1106` `set_compact_button_icon(checked)` swaps icon (`sidebar-show-symbolic` ↔ `sidebar-hide-symbolic`) and tooltip ("Show stations (Ctrl+B)" ↔ "Hide stations (Ctrl+B)"). Called from `main_window.py:899` at end of every toggle. Icon files exist on disk + registered in `icons.qrc:16-17`. Locked by `test_compact_button_icon_flips_per_state`. |
| 7   | Hover-to-peek: 4px trigger zone + 280ms dwell + reparent + mouse-leave-only dismiss + interactive | VERIFIED    | Constants `_PEEK_TRIGGER_ZONE_PX = 4`, `_PEEK_DWELL_MS = 280` (`main_window.py:64,68`). Dwell timer `QTimer.singleShot(280, _open_peek_overlay)` at `:1062`. Reparent via `StationListPeekOverlay.adopt` (`station_list_peek_overlay.py:82-114`) using `_layout.addWidget` (implicit `setParent`). Esc not handled; click not consumed. Locked by 16 tests in `test_phase72_peek_overlay.py` including `test_dwell_fires_after_280ms_in_zone`, `test_leave_closes_overlay`, `test_esc_does_not_dismiss`, `test_click_station_keeps_overlay_open`, `test_peek_station_click_activates_playback`. |
| 8   | Z-order: toast above peek (Pitfall 8 / UI-SPEC §Z-order)                                      | VERIFIED    | `ToastOverlay.show()` calls `self.raise_()` (`toast.py:92`); `StationListPeekOverlay.adopt` deliberately omits `self.raise_()` (`station_list_peek_overlay.py:115-118` with comment). Both overlays parent to MainWindow; raise-ordering puts toasts above peek. Tests at `test_phase72_peek_overlay.py:320+` cover the Z-order contract.                                |
| 9   | First QShortcut in codebase establishes pattern (D-03)                                         | VERIFIED    | `grep -r QShortcut\|QKeySequence\|setShortcut musicstreamer/` returns ONLY the Phase-72 lines in `main_window.py:34,483-503`. No other instances anywhere in the source tree.                                                                                                                                                                            |
| 10  | No X11 codepaths — Wayland-only (memory `project_deployment_target.md`)                       | VERIFIED    | `grep -nE "X11\|x11" main_window.py now_playing_panel.py station_list_peek_overlay.py` returns ZERO matches.                                                                                                                                                                                                                                            |
| 11  | No new attack surface — UI-state-only changes (T-72-01..T-72-07 STRIDE all dispositioned)     | VERIFIED    | Threat-model registers in 72-01..72-05 SUMMARYs document T-72-01 (accept), T-72-02 (accept), T-72-03 (mitigated by context lock + `test_modal_dialog_blocks_ctrl_b`), T-72-04 (n/a — bool payload), T-72-05 (event filter returns `super().eventFilter(...)` — never consumes), T-72-06 (reparent corruption — locked by `test_station_panel_reparent_round_trip_preserves_state`), T-72-07 (UAT). No new I/O, sockets, file writes, or external interfaces introduced. |
| 12  | All 42 Phase 72 tests pass                                                                     | VERIFIED    | `pytest tests/test_phase72_*.py` → `42 passed, 1 warning in 3.79s`. Test breakdown: 2 assumptions, 13 compact_toggle, 3 integration, 8 now_playing_panel, 16 peek_overlay.                                                                                                                                                                              |
| 13  | UAT verdict — 72-UAT-SCRIPT.md shows Overall: PASS with all items checked                      | VERIFIED    | `72-UAT-SCRIPT.md:295` — `**Overall:** PASS`. All 5 UAT items checked (per `key_context`; UI-checker dimensions 6/6 approved in 72-UI-SPEC.md).                                                                                                                                                                                                                |

**Score:** 13/13 truths verified

### Required Artifacts

| Artifact                                                       | Expected                                                              | Status     | Details                                                                                                                                            |
| -------------------------------------------------------------- | --------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `musicstreamer/ui_qt/main_window.py`                           | Ctrl+B shortcut + `_on_compact_toggle` slot + peek hover filter       | VERIFIED   | 1396 lines; Phase 72 additions span `:58-73` (constants), `:83` (import), `:312-322` (state vars), `:394-397` (signal wire), `:482-503` (shortcut), `:836-1102` (toggle + peek lifecycle + eventFilter). Fully wired. |
| `musicstreamer/ui_qt/now_playing_panel.py`                     | `compact_mode_toggle_btn` QToolButton + `compact_mode_toggled` signal | VERIFIED   | 2225 lines; signal at `:275`, button construction at `:527-539`, slot at `:1077-1082`, icon-flip helper at `:1084-1106`. Far-right placement after `volume_slider` confirmed at `:521-522`. |
| `musicstreamer/ui_qt/station_list_peek_overlay.py`             | `StationListPeekOverlay(QFrame)` class with adopt/release/eventFilter | VERIFIED   | 162 lines; fully implements D-11..D-15. Class at `:43`, `adopt` at `:82-118`, `release` at `:120-143`, `eventFilter` at `:145-162`.                |
| `musicstreamer/ui_qt/icons/sidebar-show-symbolic.svg`          | Sidebar-show icon (compact ON state)                                  | VERIFIED   | File present (215 bytes), registered in `icons.qrc:16`.                                                                                            |
| `musicstreamer/ui_qt/icons/sidebar-hide-symbolic.svg`          | Sidebar-hide icon (default state)                                     | VERIFIED   | File present (218 bytes), registered in `icons.qrc:17`.                                                                                            |
| `tests/test_phase72_assumptions.py`                            | Wave 0 spike regression tests                                         | VERIFIED   | 2 tests, both pass (A1 invalidation lock + A2 reparent safety lock).                                                                               |
| `tests/test_phase72_compact_toggle.py`                         | Toggle + shortcut + persistence tests                                 | VERIFIED   | 13 tests, all pass.                                                                                                                                |
| `tests/test_phase72_now_playing_panel.py`                      | Button placement + icon + signal tests                                | VERIFIED   | 8 tests, all pass.                                                                                                                                 |
| `tests/test_phase72_peek_overlay.py`                           | Hover dwell + reparent + dismiss + Z-order tests                      | VERIFIED   | 16 tests, all pass (incl. `test_global_filter_fires_when_event_targets_now_playing` locking the Wayland event-filter regression). |
| `tests/test_phase72_integration.py`                            | End-to-end lifecycle tests                                            | VERIFIED   | 3 tests, all pass.                                                                                                                                 |
| `.planning/phases/72-.../72-UAT-SCRIPT.md`                     | Manual UAT script with verdict line                                   | VERIFIED   | Verdict line `**Overall:** PASS` at `:295`.                                                                                                        |

### Key Link Verification

| From                                       | To                                              | Via                                                | Status   | Details                                                                                                                            |
| ------------------------------------------ | ----------------------------------------------- | -------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| QShortcut(Ctrl+B)                          | compact_mode_toggle_btn                         | `_on_compact_shortcut_activated` → `.toggle()`     | WIRED    | `main_window.py:498-503` → `:901-909`. Activates button instead of slot directly (single source of truth invariant).               |
| compact_mode_toggle_btn.toggled            | NowPlayingPanel.compact_mode_toggled            | `_on_compact_btn_toggled` re-emits                 | WIRED    | `now_playing_panel.py:538` connect; `:1077-1082` re-emit.                                                                          |
| NowPlayingPanel.compact_mode_toggled       | MainWindow._on_compact_toggle                   | bound-method connect (QA-05, no lambda)            | WIRED    | `main_window.py:397` `self.now_playing.compact_mode_toggled.connect(self._on_compact_toggle)`.                                     |
| MainWindow._on_compact_toggle              | station_panel.hide() / .show()                  | direct call                                        | WIRED    | `main_window.py:876, 893`.                                                                                                         |
| MainWindow._on_compact_toggle              | splitter.handle(1).hide() / .show()             | direct call                                        | WIRED    | `main_window.py:877, 894`. Explicit hide/show per A1-invalidation regression.                                                       |
| MainWindow._on_compact_toggle (ON branch)  | self._splitter_sizes_before_compact (snapshot)  | `self._splitter.sizes()` BEFORE hide               | WIRED    | `main_window.py:875` — order matters (Pitfall 1).                                                                                  |
| MainWindow._on_compact_toggle (OFF branch) | self._splitter.setSizes(snapshot)               | direct call + reset to None                        | WIRED    | `main_window.py:895-897`.                                                                                                          |
| QApplication eventFilter (cursor.pos)      | _open_peek_overlay (after 280ms dwell)          | `QTimer.singleShot(_PEEK_DWELL_MS, ...)`           | WIRED    | `main_window.py:1054-1062`. Global filter avoids the Wayland-receiver-identity bug (commit 43ba666).                                |
| _open_peek_overlay                         | StationListPeekOverlay.adopt(station_panel,...) | reparent via `_layout.addWidget`                   | WIRED    | `main_window.py:994-998` → `station_list_peek_overlay.py:82-114`.                                                                  |
| Overlay QEvent.Leave                       | MainWindow._close_peek_overlay → release        | overlay's `eventFilter` calls window's slot        | WIRED    | `station_list_peek_overlay.py:145-162` → `main_window.py:1002-1012`.                                                               |
| release(splitter, station_panel)           | splitter.insertWidget(0, station_panel)         | direct call — index 0 not append (Pitfall 6)       | WIRED    | `station_list_peek_overlay.py:140-143`. Locked by `test_station_panel_returns_to_splitter_index_0`.                                |
| set_compact_button_icon(checked)           | QIcon.fromTheme(...) + setToolTip(...)          | direct calls at end of every toggle                | WIRED    | `now_playing_panel.py:1084-1106` called from `main_window.py:899`.                                                                 |

### Data-Flow Trace (Level 4)

| Artifact                                            | Data Variable                                | Source                                                                              | Produces Real Data                                                | Status   |
| --------------------------------------------------- | -------------------------------------------- | ----------------------------------------------------------------------------------- | ----------------------------------------------------------------- | -------- |
| _on_compact_toggle slot                             | `checked: bool`                              | button's `toggled(bool)` signal                                                     | Yes — Qt-native signal carries actual checked state                | FLOWING  |
| _splitter_sizes_before_compact                      | `list[int]`                                  | `self._splitter.sizes()` BEFORE `station_panel.hide()`                              | Yes — live splitter geometry; never `[]` because both panels visible | FLOWING  |
| _open_peek_overlay (overlay width)                  | `width: int`                                 | `self._splitter_sizes_before_compact[0]` else `_PEEK_FALLBACK_WIDTH_PX` (360)       | Yes — branches over real snapshot or design-default 360            | FLOWING  |
| eventFilter cursor gating                           | `pos: QPoint`                                | `cw.mapFromGlobal(QCursor.pos())`                                                   | Yes — global cursor mapped per-event (fixed Wayland regression)    | FLOWING  |
| StationListPeekOverlay (after adopt)                | station_panel children (tree, search, chips) | reparented existing StationListPanel instance — same model + filter state           | Yes — confirmed by `test_peek_station_click_activates_playback`    | FLOWING  |

### Behavioral Spot-Checks

| Behavior                                                                    | Command                                                                                                                                                      | Result                              | Status |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------- | ------ |
| All 42 Phase 72 tests pass                                                  | `pytest tests/test_phase72_*.py`                                                                                                                             | `42 passed, 1 warning in 3.79s`     | PASS   |
| Ctrl+B is the only QShortcut in the codebase (D-03)                         | `grep -rnE "QShortcut\|QKeySequence\|setShortcut" musicstreamer/`                                                                                            | Only Phase-72 lines in main_window.py | PASS   |
| No SQLite persistence for compact mode (D-09)                               | `grep -nE "set_setting\|get_setting" main_window.py \| grep -i compact`                                                                                      | Only a comment, no live call         | PASS   |
| Peek timing constants match D-13                                            | `grep "_PEEK_(TRIGGER\|DWELL)" main_window.py`                                                                                                                | `_PEEK_TRIGGER_ZONE_PX = 4` / `_PEEK_DWELL_MS = 280` | PASS   |
| No X11 codepaths                                                            | `grep -nE "X11\|x11" main_window.py now_playing_panel.py station_list_peek_overlay.py`                                                                       | ZERO matches                         | PASS   |
| Icon assets present + registered in qrc                                     | `ls icons/sidebar*.svg` + `grep sidebar icons.qrc`                                                                                                           | Both .svg files exist; both aliases in icons.qrc | PASS   |

### Probe Execution

Not applicable — Phase 72 is a UI-layout phase with no `scripts/*/tests/probe-*.sh` shell probes. Behavioral verification is via pytest (Step 7b).

### Requirements Coverage

| Requirement   | Source Plan      | Description                                                                                                                          | Status      | Evidence                                                                                                                                                                |
| ------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| LAYOUT-01     | 72-01..72-05     | Compact-mode toggle to hide left column when window moves to small/secondary display; Ctrl+B + button + hover-to-peek; session-only | SATISFIED   | All 13 must-haves verified above. ROADMAP entry (`:617`) labels LAYOUT-01 as "proposed — first Layout-class polish item in v2.1; rolling milestone, no pre-allocated REQ ID". |

### Anti-Patterns Found

| File                                              | Line  | Pattern                | Severity | Impact |
| ------------------------------------------------- | ----- | ---------------------- | -------- | ------ |
| (none)                                            | —     | —                      | —        | —      |

`grep -nE "TBD\|FIXME\|XXX"` across `main_window.py`, `now_playing_panel.py`, `station_list_peek_overlay.py` returned no live debt markers (only doc/comment references inside the UAT-script template, which is a planning artifact, not source). No `TODO`/`HACK`/`PLACEHOLDER` strings in Phase 72 code paths. No empty-return stubs. No `console.log`-style debug residue. No lambda-in-connect anti-patterns (locked by `test_compact_mode_signal_connections_no_lambda`, `test_no_lambda_in_compact_connect`, `test_no_lambda_in_peek_connects`).

### Human Verification Required

None — UAT-SCRIPT.md verdict line at `:295` is already `**Overall:** PASS` (manual user sign-off complete per Phase 72.5 Plan). UI-checker visual contract (72-UI-SPEC.md) is 6/6 dimensions approved.

### Gaps Summary

No gaps. The phase delivers all 13 derived must-haves:

- Ctrl+B keyboard shortcut + button on the now-playing pane, both wired to the same single-source-of-truth toggle (button's checked state).
- Compact ON hides `station_panel` + explicitly hides the splitter handle (RESEARCH A1 invalidation properly mitigated).
- Splitter sizes round-trip via in-memory snapshot captured BEFORE hide (Pitfall 1 respected).
- Session-only persistence — zero `set_setting`/`get_setting` calls for compact mode; constant-False initial state.
- Icon + tooltip flip per state (sidebar-hide ↔ sidebar-show).
- Hover-to-peek overlay with 4px trigger zone, 280ms dwell, reparented `StationListPanel` (single-instance), mouse-leave-only dismiss, fully interactive children.
- Z-order contract intact: ToastOverlay raises itself, peek deliberately does not.
- First QShortcut in the codebase — establishes the pattern for future phases.
- No X11 codepaths.
- Threat-model rows T-72-01..T-72-07 all dispositioned with regression locks where required.
- All 42 Phase 72 tests green.
- UAT verdict line is `**Overall:** PASS`.

**Notable executed deviations (documented and resolved — do not penalize):**

1. **Wave 0 spike 72-01 INVALIDATED RESEARCH A1.** PySide6 6.11 does NOT auto-hide the splitter handle when an adjacent child is hidden. Plan 72-03 added explicit `self._splitter.handle(1).hide()` / `.show()` calls; regression test `test_splitter_handle_autohides_when_child_hidden` locks the behavior. The test name reflects the assumption being checked, not the actual outcome — read its body for the invalidation lock.
2. **Wave 3 (72-04) overlay parent strategy deviation.** Plan body prescribed parenting to `centralWidget()` (for natural z-below-toast ordering), but `centralWidget()` is the QSplitter — parenting a QFrame there triggers splitter child-management. Mirror strategy adopted: overlay parents to MainWindow (like ToastOverlay); z-order intent preserved because ToastOverlay calls `.raise_()` in show, peek deliberately omits `.raise_()` (locked by docstring + Z-order tests). Documented in 72-04-SUMMARY.
3. **Post-UAT-1 Wayland event-filter bug fix (commit 43ba666).** Filter originally on `centralWidget()` and gated on receiver identity — on Wayland the filter never fired because MouseMove is delivered to the child under the cursor (`NowPlayingPanel` in compact mode), never to centralWidget. Fixed by switching to `QApplication.instance()`-level filter that reads `QCursor.pos()`. New regression test `test_global_filter_fires_when_event_targets_now_playing` locks the bug class. Resolved-debug record at `.planning/debug/resolved/phase-72-hover-peek-wayland.md`.

All three deviations are documented in the respective SUMMARY files, locked by tests, and do not affect goal achievement.

---

_Verified: 2026-05-13_
_Verifier: Claude (gsd-verifier)_
