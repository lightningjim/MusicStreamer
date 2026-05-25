---
phase: 78
plan: 03
subsystem: ui_qt + tests
tags: [bug-09, commit-a, phase-78, now-playing-panel, main-window, stats-for-nerds, signal-wiring, ui-row]
requires:
  - "musicstreamer.player.Player.underrun_count_changed = Signal(int) (Plan 78-02 — producer side, ships in same wave merge)"
  - "musicstreamer.player.Player._underrun_event_count: int = 0 (Plan 78-02 — drives default UI row text '0')"
  - "tests/_fake_player.py::FakePlayer.underrun_count_changed = Signal(int) (Plan 78-02 — INFRA-01 parity mirror used by the integration test)"
  - "musicstreamer.ui_qt.now_playing_panel.NowPlayingPanel._build_stats_widget (Phase 47.1 — extensible QFormLayout)"
  - "musicstreamer.ui_qt.now_playing_panel._MutedLabel (Phase 47.1 D-10 — theme-flip safety)"
  - "musicstreamer.ui_qt.main_window.MainWindow.__init__ Player→panel wiring block (existing buffer_percent precedent at line 381)"
provides:
  - "NowPlayingPanel._build_stats_widget — Underruns row (after Buffer row, before wrapper.setVisible(False))"
  - "NowPlayingPanel._underrun_count_label — _MutedLabel widget, default text '0'"
  - "NowPlayingPanel.set_underrun_count(int) — slot receiver for Player.underrun_count_changed"
  - "MainWindow.__init__ — wires self._player.underrun_count_changed → self.now_playing.set_underrun_count (DirectConnection, bound method)"
  - "tests/test_now_playing_panel.py — 2 new tests: test_underrun_count_row_present (B-78A-11), test_set_underrun_count_updates_label"
  - "tests/test_main_window_underrun.py — 1 new test: test_count_changed_updates_stats_row (B-78A-12, end-to-end Signal → label)"
affects:
  - "musicstreamer/ui_qt/now_playing_panel.py — +18 lines (Underruns row construction in _build_stats_widget + set_underrun_count slot)"
  - "musicstreamer/ui_qt/main_window.py — +9 lines (1 connect line + 8-line inline comment block)"
  - "tests/test_now_playing_panel.py — +23 lines (2 new test functions in the Phase 47.1 stats-section neighborhood)"
  - "tests/test_main_window_underrun.py — +19 lines (1 new integration test between test_first_call_shows_toast and test_second_call_within_cooldown_suppressed)"
tech-stack:
  added: []
  patterns:
    - "Pattern 3 (RESEARCH §Architecture Patterns): extensible QFormLayout row addition in _build_stats_widget — Phase 47.1 D-09 design"
    - "§S-4 (PATTERNS): _MutedLabel used for both new widgets so theme flips remain readable (Phase 47.1 D-10 UAT follow-up)"
    - "Pattern 2 (RESEARCH): main→main typed Signal wire — DirectConnection (default) is correct; both emitter (Player._on_underrun_cycle_closed main-thread slot) and receiver (NowPlayingPanel.set_underrun_count QWidget slot) are on the main thread (Pitfall 2 satisfied)"
    - "§S-3 (PATTERNS): bound-method Signal.connect (QA-05) — no lambdas, no functools.partial; mirrors the sibling buffer_percent.connect at main_window.py:381"
    - "Pitfall 5 invariant preserved (Phase 62 carry-forward): __main__.py NOT modified — basicConfig(WARNING) + per-logger INFO escalation untouched; drift-guard test_main_module_sets_player_logger_to_info GREEN"
key-files:
  created: []
  modified:
    - "musicstreamer/ui_qt/now_playing_panel.py"
    - "musicstreamer/ui_qt/main_window.py"
    - "tests/test_now_playing_panel.py"
    - "tests/test_main_window_underrun.py"
decisions:
  - "RESEARCH Pattern 2 + Open Q2 + CONTEXT D-08 Discretion: two-column QFormLayout shape mirrors the existing Buffer row (label _MutedLabel('Underruns') on the left, value _MutedLabel('0') on the right). Rejected the alternative single-cell colon-formatted 'Underruns: N' shape — two-column reads identically when rendered and matches Phase 47.1 idiom."
  - "RESEARCH Pattern 2 + A3 + CONTEXT D-08: new MainWindow connect uses DEFAULT (Direct) connection — explicitly NOT Qt.ConnectionType.QueuedConnection. Documented in inline comment to dispel the 'be safe, add QueuedConnection' overreach. The Phase 62 underrun_recovery_started connection 3 lines below uses QueuedConnection defensively for unrelated reasons; the two wires are intentionally not 'harmonized'."
  - "Default value text '0' on _underrun_count_label mirrors Plan 78-02's Player._underrun_event_count: int = 0 initial state. set_underrun_count is idempotent on the default value (covered by test_set_underrun_count_updates_label)."
  - "set_underrun_count slot lands BETWEEN set_buffer_percent (line 946) and set_stats_visible (line 961) per PATTERNS.md analog placement — preserves the 'sibling-slot' visual cohesion and lets reviewers find the receiver next to its analog."
  - "Wrapper-level visibility governance preserved: NO per-row visibility code was added; the existing set_stats_visible(bool) and wrapper.setVisible(False) at the end of _build_stats_widget govern BOTH the Buffer row and the new Underruns row (Phase 47.1 D-05/D-07 invariant)."
  - "Hard constraint honored: 'Buffer config: Xs (adapted)' row is Commit B work — explicitly NOT added in this plan. CONTEXT D-08 second bullet defers it pending the ~1-week harvest data; PLAN.md hard constraint reinforces this."
metrics:
  duration: "3m 19s"
  completed: "2026-05-18T00:59:34Z"
  tasks: 2
  files_modified: 4
  files_created: 0
  lines_added: 69
  lines_removed: 0
---

# Phase 78 Plan 03: NowPlayingPanel Underruns Row + MainWindow Signal Wiring Summary

UI consumer half of Phase 78 Commit A: adds an `Underruns` row to `NowPlayingPanel._build_stats_widget` (after the existing `Buffer` progressbar row, default text `"0"`), exposes a `set_underrun_count(int)` slot, and wires `Player.underrun_count_changed` → `NowPlayingPanel.set_underrun_count` in `MainWindow.__init__` via a bound-method DirectConnection sibling to the `buffer_percent` wire.

## One-Liner

Live `Underruns` stats-for-nerds row + end-to-end `Signal(int) → QLabel.setText` wire — closes the visible-without-grep observability gap from Plan 78-02's cumulative cycle counter.

## Tasks Completed

| # | Name                                                                                                          | Commit    | Files                                                                                                |
|---|---------------------------------------------------------------------------------------------------------------|-----------|------------------------------------------------------------------------------------------------------|
| 1 | Add Underruns row + set_underrun_count slot to NowPlayingPanel + unit tests                                   | `4de2a8b` | `musicstreamer/ui_qt/now_playing_panel.py`, `tests/test_now_playing_panel.py`                        |
| 2 | Wire Player.underrun_count_changed → NowPlayingPanel.set_underrun_count in MainWindow + integration test      | `5359910` | `musicstreamer/ui_qt/main_window.py`, `tests/test_main_window_underrun.py`                           |

## Acceptance Criteria — Verified

### Plan-level success criteria (frontmatter `must_haves.truths`)

- [x] `NowPlayingPanel._build_stats_widget` produces a `QFormLayout` with an `Underruns` row positioned AFTER the existing `Buffer` progressbar row and BEFORE `wrapper.setVisible(False)`. Verified by grep gates + the new `test_underrun_count_row_present` test.
- [x] `Underruns` row has default value text `"0"` (mirrors `Player._underrun_event_count: int = 0` initial state from Plan 78-02). Verified by `test_underrun_count_row_present`.
- [x] Both new row widgets use `_MutedLabel` (Phase 47.1 D-10 theme-flip safety). Verified by `grep -nE "_MutedLabel\\(['\"]Underruns['\"], wrapper\\)"` and `grep -nE "_MutedLabel\\(['\"]0['\"], wrapper\\)"` each returning 1 match.
- [x] `NowPlayingPanel.set_underrun_count(count: int)` updates `self._underrun_count_label` text to `str(int(count))`. Verified by `test_set_underrun_count_updates_label`.
- [x] `MainWindow.__init__` connects `self._player.underrun_count_changed` → `self.now_playing.set_underrun_count` via bound method (QA-05) and DEFAULT connection type (no `Qt.ConnectionType.QueuedConnection` argument). Verified by grep gates + new integration test.
- [x] Emitting `fake_player.underrun_count_changed.emit(N)` updates the `_underrun_count_label` text to `str(N)` end-to-end. Verified by `test_count_changed_updates_stats_row` (emits 3 → asserts "3"; emits 7 → asserts "7").

### Plan-level success criteria (plan `<success_criteria>`)

- [x] B-78A-11 covered by `tests/test_now_playing_panel.py::test_underrun_count_row_present` — GREEN.
- [x] B-78A-12 covered by `tests/test_main_window_underrun.py::test_count_changed_updates_stats_row` — GREEN.
- [x] `NowPlayingPanel._build_stats_widget` has an Underruns row positioned after the Buffer row.
- [x] `NowPlayingPanel.set_underrun_count(int)` slot exists and updates `self._underrun_count_label`.
- [x] `MainWindow.__init__` connects `Player.underrun_count_changed` → `NowPlayingPanel.set_underrun_count` via bound method, DirectConnection.
- [x] Pitfall-5 drift-guard `test_main_module_sets_player_logger_to_info` remains GREEN (B-78A-13). `__main__.py` was NOT modified.

### Acceptance gate grep results (Task 1 — `musicstreamer/ui_qt/now_playing_panel.py`)

```
grep -c "self._underrun_count_label"                                       → 3   (decl in _build_stats_widget + setText in slot + form.addRow value column)
grep -nE "def set_underrun_count\(self, count: int\) -> None:"             → 951 (after set_buffer_percent@946, before set_stats_visible@961)
grep -nE "_MutedLabel\(['\"]Underruns['\"], wrapper\)"                     → 1 match (line 2494)
grep -nE "_MutedLabel\(['\"]0['\"], wrapper\)"                             → 1 match (line 2495)
py_compile (Python 3.13 syntactic check)                                   → OK
```

### Acceptance gate grep results (Task 2 — `musicstreamer/ui_qt/main_window.py`)

```
grep -c "underrun_count_changed.connect"                                                                       → 1 (exactly one)
grep -nE "self\._player\.underrun_count_changed\.connect\(self\.now_playing\.set_underrun_count\)"             → 390
grep -nE "underrun_count_changed.*Qt\.ConnectionType\.QueuedConnection"                                        → 0 (DirectConnection lock)
grep -nE "underrun_count_changed.*lambda"                                                                      → 0 (QA-05 / §S-3 — no lambdas)
Ordering: buffer_percent.connect@381 < underrun_count_changed.connect@390 < underrun_recovery_started.connect@400  ✓
py_compile (Python 3.13 syntactic check)                                                                       → OK
```

## Test Results

### Plan-level verification (PLAN.md `<verification>` narrowed wave-merge suite)

```
$ uv run pytest tests/test_now_playing_panel.py tests/test_main_window_underrun.py tests/test_fake_player_signal_parity.py -q
150 passed in 1.73s
```

- **142 tests** in `tests/test_now_playing_panel.py` — includes the 2 new B-78A-11 + `test_set_underrun_count_updates_label` tests, plus regression coverage for the existing Phase 47.1 stats tests (`test_stats_widget_always_constructed`, `test_stats_hidden_by_default`, `test_stats_visible_after_set_stats_visible_true`, `test_stats_uses_form_layout`, `test_buffer_bar_properties`, `test_set_buffer_percent_updates_both`, `test_set_stats_visible_toggles`) — all GREEN.
- **6 tests** in `tests/test_main_window_underrun.py` — includes the new B-78A-12 (`test_count_changed_updates_stats_row`), the Phase 62 cooldown-gate suite (`test_first_call_shows_toast`, `test_second_call_within_cooldown_suppressed`, `test_toast_after_cooldown_allowed`, `test_close_event_force_closes_open_cycle`), and the Pitfall-5 drift-guard (`test_main_module_sets_player_logger_to_info`) — all GREEN.
- **2 tests** in `tests/test_fake_player_signal_parity.py` — INFRA-01 drift-guards (Phase 77) — both GREEN (Plan 78-02's parity mirror still satisfies the production Player.underrun_count_changed declaration).

### Per-task narrow verification

```
$ uv run pytest tests/test_now_playing_panel.py::test_underrun_count_row_present tests/test_now_playing_panel.py::test_set_underrun_count_updates_label -x
2 passed in 0.34s

$ uv run pytest tests/test_main_window_underrun.py::test_count_changed_updates_stats_row -x
1 passed in 0.60s

$ uv run pytest tests/test_main_window_underrun.py::test_main_module_sets_player_logger_to_info -x
1 passed in 0.25s
```

## Environment Limitations

**No `gi` env-gap encountered for Plan 78-03 tests.** Unlike Plan 78-02 (which needed `tests/test_player_underrun_count.py` to import `musicstreamer.player` → transitively imports `gi`), every Plan 78-03 test uses the project's `FakePlayer(QObject)` test double — none import `musicstreamer.player` directly. The `gi` env-gap noted in 78-02's SUMMARY does NOT impact this plan's automated verification.

**For traceability:** the worktree's `uv`-managed `.venv` runs CPython 3.13.13 with PySide6 6.11.0 / Qt 6.11.0; B-78A-11, `test_set_underrun_count_updates_label`, and B-78A-12 all execute end-to-end under `uv run pytest`. Acceptance criteria for B-78A-11 and B-78A-12 are fully verified by automated test execution, not just `py_compile` + grep gates.

## Deviations from Plan

None. Plan executed exactly as written. Both tasks landed in one shot with no Rule 1 / Rule 2 / Rule 3 fixes needed; no Rule 4 architectural questions encountered. The plan's `<action>` sections were unusually precise — every edit site was named down to the line, every grep gate was specified, and the threading-decision rationale was already lined up so the inline comment block wrote itself.

### Auto-fixed Issues

None.

### Architectural Decisions

None.

## Authentication Gates

None — this is a pure code-edit plan with no auth surface.

## Threat Surface

No new threat surface introduced beyond what the plan's `<threat_model>` already documents (T-78A-Pitfall2-NewWire / T-78A-Toast-Regress / T-78A-Pitfall5-Regress / T-78A-QA05 — all four mitigated as planned):

| Threat | Mitigation | Verification |
|---|---|---|
| T-78A-Pitfall2-NewWire | Both emitter and receiver on main thread; DirectConnection is the project-idiomatic default for main→main wires (RESEARCH A3) | Inline comment at main_window.py:382-389 documents the thread-affinity decision; grep gate `grep -nE "underrun_count_changed.*Qt\\.ConnectionType\\.QueuedConnection"` returns 0 |
| T-78A-Toast-Regress | NO new toast paths added; the new wire targets `set_underrun_count` (silent stats row), not `show_toast` | Source review of new connect line + grep gate (no new `show_toast` call) |
| T-78A-Pitfall5-Regress | `__main__.py` was NOT modified by this plan | `git diff e2bd1c6..HEAD -- musicstreamer/__main__.py` → 0 lines; drift-guard test `test_main_module_sets_player_logger_to_info` GREEN |
| T-78A-QA05 | Bound-method connect; no lambda | `grep -nE "underrun_count_changed.*lambda"` returns 0 |

## Files Changed Summary

| File | Lines Added | Lines Removed | Net |
|---|---|---|---|
| `musicstreamer/ui_qt/now_playing_panel.py` | 18 | 0 | +18 |
| `musicstreamer/ui_qt/main_window.py` | 9 | 0 | +9 |
| `tests/test_now_playing_panel.py` | 23 | 0 | +23 |
| `tests/test_main_window_underrun.py` | 19 | 0 | +19 |

**Total:** +69 lines / -0 lines across 4 files (0 new, 4 modified). Pure-additive — no rewrites, no refactoring, no deletions.

## Sub-system Wave Handoff (for Phase 78 Commit A wave-merge)

Plan 78-03 closes the consumer side of the producer/consumer pair shipped across Plans 78-01, 78-02, and 78-03 in Phase 78 Commit A:

- **Plan 78-01:** file sink (`buffer_log.py` + `paths.buffer_events_log_path()` + `_run_gui` install). Out-of-process artifact: `~/.local/share/musicstreamer/buffer-events.log`.
- **Plan 78-02:** Player-side counter + Signal + FakePlayer parity mirror. Producer.
- **Plan 78-03 (this plan):** UI row + `set_underrun_count` slot + `MainWindow` wiring. Consumer.

After this plan's wave merge, the user can launch MusicStreamer, toggle "Stats for nerds" from the hamburger menu, and watch the `Underruns: N` row tick up live during the ~1-week harvest period defined by CONTEXT D-01.

**Commit B (deferred):** `Buffer config: Xs (adapted)` row, adaptive buffer-duration growth, and the `_current_buffer_duration_s` runtime state are all explicitly OUT OF SCOPE for Plan 78-03 and will be planned in a separate pass after the harvest week (per CONTEXT D-01 + D-04..D-06 [informational]).

## Self-Check: PASSED

### Created files exist

```
$ [ -f .planning/phases/78-phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug/78-03-SUMMARY.md ] && echo "FOUND" || echo "MISSING"
FOUND  (this file)
```

### Modified files contain expected anchors

```
$ grep -nE "def set_underrun_count\(self, count: int\) -> None:" musicstreamer/ui_qt/now_playing_panel.py
951:    def set_underrun_count(self, count: int) -> None:

$ grep -nE "self\._player\.underrun_count_changed\.connect\(self\.now_playing\.set_underrun_count\)" musicstreamer/ui_qt/main_window.py
390:        self._player.underrun_count_changed.connect(self.now_playing.set_underrun_count)

$ grep -nE "def test_underrun_count_row_present|def test_set_underrun_count_updates_label" tests/test_now_playing_panel.py
666:def test_underrun_count_row_present(qtbot):
675:def test_set_underrun_count_updates_label(qtbot):

$ grep -nE "def test_count_changed_updates_stats_row" tests/test_main_window_underrun.py
45:def test_count_changed_updates_stats_row(qtbot, fake_player, fake_repo, block_real_network):
```

### Commits exist

```
$ git log --oneline -2
5359910 feat(78-03): wire Player.underrun_count_changed → NowPlayingPanel in MainWindow
4de2a8b feat(78-03): add Underruns stats row + set_underrun_count slot to NowPlayingPanel
```

Both task commits present on `worktree-agent-a37a53253ebfc6341`.

### Invariants preserved

- `__main__.py` unchanged: `git diff e2bd1c6..HEAD -- musicstreamer/__main__.py` → 0 lines (Pitfall 5 invariant intact).
- `musicstreamer/constants.py` unchanged: out-of-scope for Plan 78-03 (no buffer-duration bump in Commit A).
- `musicstreamer/player.py` unchanged: producer-side work was Plan 78-02; this plan is consumer-only.
- `tests/_fake_player.py` unchanged: parity mirror was Plan 78-02; this plan reuses it.
- Phase 62 `underrun_recovery_started` QueuedConnection at `main_window.py:400-402` unchanged: explicitly NOT "harmonized" with the new DirectConnection wire (RESEARCH Anti-Pattern lock).

---

*Plan execution complete. SUMMARY.md committed before worktree return per parallel-executor protocol (#2070). STATE.md / ROADMAP.md updates deferred to the orchestrator (worktree mode invariant).*
