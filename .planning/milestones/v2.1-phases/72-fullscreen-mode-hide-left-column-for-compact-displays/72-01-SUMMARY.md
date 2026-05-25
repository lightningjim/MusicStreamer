---
phase: 72
plan: 01
subsystem: ui/qt-layout
tags: [wave-0, spike, pyside6, qsplitter, qframe-reparent, assumption-verification]
requires: []
provides:
  - "tests/test_phase72_assumptions.py — Wave 0 regression locks for A1 (handle non-auto-hide on PySide6 6.11.0) and A2 (StationListPanel reparent round-trip preserves _search_box state)"
affects:
  - ".planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/72-RESEARCH.md (A1 row needs ASSUMPTION-INVALIDATED annotation)"
  - "Plan 72-02 must_haves (compact-toggle slot MUST add explicit `self._splitter.handle(1).hide()` / `.show()` calls)"
  - "Plan 72-04 / 72-05 (peek overlay reparent pattern CONFIRMED safe — proceed)"
tech_stack_added: []
tech_stack_patterns:
  - "pytest-qt qtbot fixture + offscreen Qt platform for headless spike tests"
  - "QFrame + QVBoxLayout(contentsMargins=0) as overlay-style container (mirrors RESEARCH §Pattern 4 / PATTERNS §3)"
  - "splitter.insertWidget(0, panel) round-trip pattern (Pitfall 6 lock)"
key_files_created:
  - "tests/test_phase72_assumptions.py (2 tests, ~280 lines, both PASS on PySide6 6.11.0)"
key_files_modified: []
decisions:
  - "RESEARCH A1 INVALIDATED on PySide6 6.11.0 — handle does NOT auto-hide when station_panel hides. Plans 02-05 must add explicit `handle(1).hide()`/`.show()`."
  - "RESEARCH A2 CONFIRMED on PySide6 6.11.0 — single-instance reparent pattern is safe; _search_box state survives the round trip."
  - "Test docstrings + assertion messages document the observed-not-the-expected behavior so the test now serves as a regression lock for the actual Qt 6.11 contract."
metrics:
  duration_seconds: 337
  duration_human: "~5min 37sec"
  tasks_completed: 2
  files_created: 1
  files_modified: 0
  test_count_added: 2
  test_pass_rate: "2/2 PASS on PySide6 6.11.0 / Qt 6.11.0"
  completed: "2026-05-13"
---

# Phase 72 Plan 01: Wave 0 Spike — Assumption Verification Summary

**One-liner:** Wave 0 spike validated 1 of 2 RESEARCH assumptions on PySide6 6.11.0
— A1 (auto-hide of QSplitter handle) is INVALIDATED and requires Plan 02 to add an
explicit `handle(1).hide()` call; A2 (StationListPanel reparent round-trip) is
CONFIRMED, so the single-instance overlay pattern proceeds as planned.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1+2 (combined) | Wave 0 spike tests A1 + A2 (single new test file) | `ca4be24` | `tests/test_phase72_assumptions.py` |

**Combined-commit note:** Tasks 1 and 2 both create new test functions in the **same**
new file (`tests/test_phase72_assumptions.py`). Per the plan's Task 2 action
("Add test_station_panel_reparent_round_trip_preserves_state to the **same**
tests/test_phase72_assumptions.py file"), the file was authored in one Write
operation containing both tests. The single commit captures the complete Wave 0
deliverable atomically. Future plans that touch this file should follow the
standard one-commit-per-task pattern; the spike's all-in-one-file structure is a
one-time exception driven by Task 2's explicit "same file" instruction.

## Wave 0 Findings

### A1 — INVALIDATED (HIGH-IMPACT FINDING)

**Stated assumption (RESEARCH §Assumptions Log A1):**
> "Calling station_panel.hide() on the live QSplitter auto-hides the adjacent splitter
> handle in the project's PySide6 version (forum.qt.io/topic/45377)."
> Risk: LOW — even if it doesn't, a one-line `self._splitter.handle(1).hide()` is a
> trivial addition.

**Observed behavior on PySide6 6.11.0 / Qt 6.11.0 (offscreen platform):**
After `w.station_panel.hide()`, `w.centralWidget().handle(1).isVisible()` returns
`True`. The handle does **NOT** auto-hide when the adjacent child is hidden. The
forum thread that inspired this assumption is a Qt 4/5-era discussion; the behavior
does NOT carry over to Qt 6.11.

**Test result:** The Wave 0 spike test `test_splitter_handle_autohides_when_child_hidden`
now LOCKS the observed behavior — it asserts `handle.isVisible() is True` after
`station_panel.hide()`, with a docstring + assertion message that explicitly call
out the RESEARCH-vs-observed delta. A future PySide6 release that adds auto-hide will
fail this assertion and prompt Plans 02-05 to drop the now-redundant explicit hide
call. The risk severity was correctly RESEARCH-rated as LOW because the mitigation is
a one-line addition.

**Required mitigation for Plan 72-02 (REQUIRED, not optional):**
The compact-toggle slot in `MainWindow._on_compact_toggle` MUST include explicit
handle-visibility management:

```python
def _on_compact_toggle(self, checked: bool) -> None:
    if checked:
        self._splitter_sizes_before_compact = self._splitter.sizes()
        self.station_panel.hide()
        self._splitter.handle(1).hide()       # REQUIRED — A1 invalidated, handle does NOT auto-hide
    else:
        self.station_panel.show()
        self._splitter.handle(1).show()       # REQUIRED — symmetric restore
        if self._splitter_sizes_before_compact:
            self._splitter.setSizes(self._splitter_sizes_before_compact)
            self._splitter_sizes_before_compact = None
```

**Downstream documentation updates:**

1. `72-RESEARCH.md` §Assumptions Log row A1 should be annotated:
   `"Wave 0 result: ASSUMPTION INVALIDATED on PySide6 6.11.0 — handle does NOT auto-hide. Mitigation: explicit handle(1).hide()/show() in Plan 02 must_haves."`
2. `72-RESEARCH.md` §Architecture Patterns §Pattern 1: remove the NOTE comment that
   says "per forum.qt.io/topic/45377, hiding the child auto-hides the adjacent
   handle in Qt 6 — verified empirically. No explicit handle(1).hide() needed."
   Replace with: "Wave 0 spike test 72-01 verified: handle does NOT auto-hide on
   PySide6 6.11.0; explicit handle(1).hide()/show() required."
3. `72-RESEARCH.md` §Don't Hand-Roll table row "Splitter handle hide synchronized
   with widget hide" needs inversion: the Wave 0 finding is that the explicit call
   IS now required, not redundant.
4. `Plan 72-02` `must_haves.truths` should add an entry:
   `"Compact-toggle slot includes explicit self._splitter.handle(1).hide() / .show() — A1 was invalidated by Wave 0 spike 72-01."`

### A2 — CONFIRMED

**Stated assumption (RESEARCH §Assumptions Log A2):**
> "StationListPanel has no parent-assumption code that would break under reparenting."
> Risk: MEDIUM — based on a grep audit alone.

**Observed behavior on PySide6 6.11.0 / Qt 6.11.0 (offscreen platform):**

1. `grep -nE 'self\.parent\(\)|self\.window\(\)|topLevelWidget' musicstreamer/ui_qt/station_list_panel.py` returns ZERO matches (re-verified during Wave 0).
2. The full round trip executes without exception:
   - `container_layout.addWidget(panel)` correctly reparents the panel into a `QFrame` container; `panel.parent() is container`.
   - The splitter correctly reports `indexOf(panel) == -1` after the panel leaves it.
   - `splitter.insertWidget(0, panel)` correctly returns the panel to splitter index 0; `splitter.widget(0) is panel` and `splitter.widget(1) is w.now_playing`.
3. **State survives both legs of the round trip:** A sentinel value written into the panel's `_search_box` is intact after reparenting INTO the QFrame container AND after reparenting BACK into the splitter at index 0.
4. The panel remains `isWidgetType()` (i.e., not destroyed) throughout.

**Test result:** The Wave 0 spike test `test_station_panel_reparent_round_trip_preserves_state`
PASSES and locks the observed behavior. Pitfall 6 (RESEARCH §Common Pitfalls) is
exercised: the return trip uses `splitter.insertWidget(0, panel)` and the test
explicitly asserts `splitter.widget(0) is panel` and `splitter.widget(1) is now_playing`
so a future regression that swaps to `addWidget(panel)` (which would append at the
end and swap visual order) will fail this test.

**Downstream impact (NO action needed):** Plans 04-05 may proceed with the
single-instance reparent pattern as RESEARCH §Pattern 4 recommends. The two-instance
alternative remains available as fallback in the rare case the peek-overlay
geometry / z-order surfaces additional state issues, but the Wave 0 finding does
not require it.

## Deviations from Plan

### Combined Task 1 + Task 2 commit

**Type:** Process exception (single new file authored in one Write)
**Tasks affected:** Both Task 1 and Task 2 write to the same new file
`tests/test_phase72_assumptions.py`.
**Reason:** Task 2's action verbatim says "Add … to the **same**
tests/test_phase72_assumptions.py file." The file was created with both test
functions in one editor operation. Per the plan's atomic-commit guidance, this
creates one commit covering both task deliverables. The commit message explicitly
calls out both A1 and A2 coverage.
**Impact:** None on downstream — both tests are pinned, both gates verified.

### Acceptance criterion `pytest -W error` reports unrelated PyGI deprecation

**Type:** Out-of-scope / pre-existing environment issue (logged for awareness)
**Task affected:** Task 2 acceptance criterion: "No new pytest warnings introduced
(`pytest -W error tests/test_phase72_assumptions.py`)."
**Observation:** Running `pytest -W error` against the new test file raises an
ERROR — but the warning being escalated is a SYSTEM-WIDE `PyGIDeprecationWarning`
from `/usr/lib/python3/dist-packages/gi/overrides/__init__.py:159` complaining
about `GLib.unix_signal_add_full is deprecated; use GLibUnix.signal_add_full
instead`. This warning fires for ALL pytest-qt tests in the project that import
`musicstreamer.player` (verified by running `pytest -W error` against
`tests/test_main_window_integration.py::test_central_widget_is_splitter` — same
ERROR). It is NOT introduced by Wave 0; it is a pre-existing
system-Python-PyGI-version issue on the dev box.
**Disposition:** Pre-existing — out of scope per execution rules SCOPE BOUNDARY.
The Task 2 acceptance criterion's intent ("no NEW warnings introduced by Wave 0")
is satisfied: my test file introduces zero new warnings; the only warning observed
is the pre-existing system-level deprecation. No work-item filed.

### Full test suite has pre-existing failures unrelated to Wave 0

**Type:** Out-of-scope / pre-existing test breakage on worktree base commit
**Observation:** Running `pytest tests/` reports a `FAILED` on
`tests/test_import_dialog_qt.py::test_audioaddict_tab_widgets` (AttributeError on
`ImportDialog._aa_quality`) and several `ERROR at setup of …` lines on
GBS/media-keys/title-changed tests. These failures reproduce when my Wave 0 changes
are reverted, so they are NOT introduced by this plan. The worktree's base commit
(83c1e88, Phase 69) predates Phase 70/71's test-suite repair work.
**Disposition:** Out of scope per execution rules SCOPE BOUNDARY. Logged to
`deferred-items.md` for visibility. The Wave 0 mission — verify A1/A2 with
automated spike tests — is complete and unaffected.

## Environment

- **PySide6 version:** `6.11.0` (verified via `import PySide6; PySide6.__version__`)
- **Qt runtime version:** `6.11.0` (verified via `from PySide6.QtCore import qVersion; qVersion()`)
- **Python:** `3.14.4` (`/home/kcreasey/OneDrive/Projects/MusicStreamer/.venv/bin/python`)
- **Platform:** `QT_QPA_PLATFORM=offscreen` (per `tests/conftest.py:13`)
- **Test framework:** pytest-9.0.3 + pytest-qt-4.5.0

## Verification Results

| Check | Result |
| ----- | ------ |
| `pytest tests/test_phase72_assumptions.py::test_splitter_handle_autohides_when_child_hidden` | PASS (locks observed: handle stays visible) |
| `pytest tests/test_phase72_assumptions.py::test_station_panel_reparent_round_trip_preserves_state` | PASS (locks observed: state survives round trip) |
| `pytest tests/test_phase72_assumptions.py -x -v` | 2 passed, 1 warning (pre-existing PyGI deprecation) |
| `grep -E '^\s*(lambda\|QShortcut\|setShortcut\|QKeySequence)' tests/test_phase72_assumptions.py` | exit=1 (zero matches — QA-05 + premature-pattern gates OK) |
| `grep -c "station_panel.hide()" tests/test_phase72_assumptions.py` | 7 (≥1 — A1 source assertion OK) |
| `grep -c "insertWidget(0" tests/test_phase72_assumptions.py` | 5 (≥1 — Pitfall 6 path exercised) |
| `grep -E "addWidget\(.*station_panel" tests/test_phase72_assumptions.py` | 1 match (inside assertion-message string only, NOT live code) |
| Full suite regression check (Wave 0 file alone) | PASS — no impact on unrelated tests |

## Known Stubs

None. The Wave 0 deliverable is a pair of spike tests with full assertions.

## Threat Flags

None. Wave 0 introduces no I/O, no auth, no network, no file, no IPC surface —
pure pytest assertions against existing in-process Qt widget state. Mirrors
the plan's `<threat_model>` STRIDE row T-72-01 (Disposition: accept).

## Recommendations for Plan 72-02 (next plan in wave)

1. **A1 mitigation is REQUIRED, not optional.** Plan 72-02 must include explicit
   `self._splitter.handle(1).hide()` and `self._splitter.handle(1).show()` calls
   in the compact-toggle slot, paired symmetrically with `station_panel.hide()`
   and `.show()`. Add a unit test `test_compact_mode_hides_splitter_handle` that
   asserts handle visibility after toggle.
2. **A2 confirmation unlocks the reparent pattern for Plans 04-05.** The peek
   overlay can use the recommended single-instance reparent approach without
   added risk; the two-instance fallback is not needed unless future surface area
   (e.g., new parent-assumption code added to StationListPanel) breaks the round
   trip. Add a regression test in `tests/test_phase72_assumptions.py` or split it
   to a new test file if 72-02 grows the assumption surface (e.g., chip-row
   state, scroll position).
3. **Wave 0 test file is a permanent regression lock.** Do not delete or move
   `tests/test_phase72_assumptions.py` in subsequent waves; future PySide6
   upgrades will use it as the canary for A1 + A2 behavior drift.

## Self-Check: PASSED

- File `tests/test_phase72_assumptions.py` exists at the expected absolute path:
  `/home/kcreasey/OneDrive/Projects/MusicStreamer/.claude/worktrees/agent-a410b1e9473a3f813/tests/test_phase72_assumptions.py`
  → verified via `pytest` successfully importing and running both tests.
- Commit `ca4be24` exists in the worktree branch `worktree-agent-a410b1e9473a3f813`:
  `git log --oneline | grep ca4be24` confirms `test(72-01): A1 Wave 0 spike — handle does NOT auto-hide on PySide6 6.11`.
- Both spike tests pass on the dev-box PySide6 6.11.0 / Qt 6.11.0:
  `pytest tests/test_phase72_assumptions.py -v` → 2 passed.

---

*Plan 72-01 completed: 2026-05-13*
*Phase: 72-fullscreen-mode-hide-left-column-for-compact-displays*
