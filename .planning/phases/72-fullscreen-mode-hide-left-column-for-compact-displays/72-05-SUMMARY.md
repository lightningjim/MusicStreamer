---
phase: 72
plan: 05
subsystem: ui/qt-layout
tags: [wave-4, layout-01, integration-test, uat-script, wayland, human-verify-gate, flaky-fix]
requires:
  - "72-01 (Wave 0 spike — A1 invalidated, A2 confirmed) — completed at ca4be24"
  - "72-02 (NowPlayingPanel compact_mode_toggle_btn + Signal + icons) — completed at 884b7f7"
  - "72-03 (MainWindow _on_compact_toggle + Ctrl+B QShortcut + Plan-04 stubs) — completed at 1399ee8"
  - "72-04 (StationListPeekOverlay + filled peek-lifecycle stubs) — completed at c0e8d3b"
provides:
  - "tests/test_phase72_integration.py — 3 end-to-end integration tests pinning the full compact+peek+restore lifecycle (toggle ON → peek → station-click → mouse-leave → toggle OFF), multi-cycle splitter-size round-trip, and D-09 session-only invariant at integration level (419 lines)"
  - ".planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/72-UAT-SCRIPT.md — Manual UAT script with 5 numbered items (UAT-01..05) covering icon-flip judgment, hover-peek timing/feel, overlay z-order vs ToastOverlay, bottom-bar overlap fix on small/secondary display, and Wayland-GNOME-Shell full-lifecycle confirmation (PENDING gate)"
affects:
  - ".planning/STATE.md — phase 72 will move from in-progress to complete (orchestrator-owned write after UAT signoff)"
  - ".planning/ROADMAP.md — phase 72 progress row will reflect 5/5 plans complete (orchestrator-owned write)"
tech_stack_added: []
tech_stack_patterns:
  - "qtbot.waitUntil(predicate, timeout) for poll-based dwell-timer assertions — supersedes brittle `qtbot.wait(280)` patterns that race against the offscreen platform's event-loop drain"
  - "bound-method predicate factory (`_make_peek_visible_predicate(window)`) — closure over window state, avoids inline-lambda anti-pattern per QA-05"
  - "MouseMove + QEvent.Leave synthesis via QApplication.sendEvent — mirrors the helper pattern established by tests/test_phase72_peek_overlay.py"
key_files_created:
  - "tests/test_phase72_integration.py"
  - ".planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/72-UAT-SCRIPT.md"
key_files_modified: []
decisions:
  - "End-to-end integration tests use `qtbot.waitUntil` instead of fixed `qtbot.wait(280)` to eliminate the flaky-timing race on offscreen Qt 6.11.0 (Rule 1 fix discovered during 15-run stress test — initial code had ~1 in 10 failure rate; after fix, 15/15 PASS)."
  - "Bound-method predicate helper `_make_peek_visible_predicate(window)` introduced to keep `qtbot.waitUntil` callers QA-05 compliant (no inline lambdas)."
  - "UAT script written for Wayland exclusively — zero X11 references (negative gate satisfied) per project memory `project_deployment_target.md`. The original draft mentioned 'do NOT run X11' five times; rewritten to positively frame Wayland confirmation steps so the literal `grep -ci X11` returns 0."
  - "UAT script's overall-result gate ships with `**Overall:** PENDING` so the Task 3 checkpoint grep (`^\\*\\*Overall:\\*\\* PASS`) does NOT yet match — the gate stays closed until the user actually runs the script."
metrics:
  duration_seconds: 921
  duration_human: "~15min 21sec"
  tasks_completed: 2  # Tasks 1+2; Task 3 is the human-verify checkpoint (not "completed" by this agent)
  files_created: 2
  files_modified: 0
  test_count_added: 3
  test_pass_rate: "3/3 PASS (stable across 15-run stress test post-fix); 41/41 total Phase 72 tests PASS"
  completed: "2026-05-13"
---

# Phase 72 Plan 05: Integration test + UAT script + checkpoint gate — Summary

**One-liner:** Final regression lock for Phase 72 — three end-to-end
integration tests in `tests/test_phase72_integration.py` exercise the full
compact + peek + restore lifecycle without mocking the production widgets,
plus a five-item Manual UAT script (`72-UAT-SCRIPT.md`) for the
human-verify gate that will close the phase. The script is initialized in
`**Overall:** PENDING` state so the orchestrator's checkpoint grep stays
closed until the user runs UAT on a live Wayland session.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | End-to-end integration test (3 tests) | `4c32cb3` | `tests/test_phase72_integration.py` (NEW) |
| 1-fix | Replace `qtbot.wait(280)` with `qtbot.waitUntil` (flaky-fix) | `2468b0f` | `tests/test_phase72_integration.py` |
| 2 | Manual UAT script (5 numbered items, Wayland-targeted) | `f1d210b` | `.planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/72-UAT-SCRIPT.md` (NEW) |
| 3 | Checkpoint: User runs UAT and marks PASS/FAIL | (no commit by this agent) | — |

Task 3 is a `checkpoint:human-verify` gate. This executor agent does NOT
self-certify the gate; the orchestrator surfaces the `## CHECKPOINT REACHED`
message at the end of this run, and a separate user action (running UAT
+ editing the script's overall line to `PASS`) closes the gate.

## Final Source Locations

### `tests/test_phase72_integration.py` (NEW — 419 lines)

| Element | Line |
| ------- | ---- |
| `_send_mouse_move(widget, x, y)` helper | 100 |
| `_send_leave(widget)` helper | 121 |
| `_make_peek_visible_predicate(window)` factory (QA-05 lambda-free predicate) | 128 |
| `test_full_compact_peek_lifecycle` | 147 |
| `test_multiple_toggle_cycles_preserve_sizes` | 308 |
| `test_no_compact_setting_written_after_full_lifecycle` | 348 |

### `.planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/72-UAT-SCRIPT.md` (NEW)

| Section | Content |
| ------- | ------- |
| UAT-01 | Icon flip visual correctness (D-05) |
| UAT-02 | Hover-peek feel & timing (D-13, 280ms + 4px) |
| UAT-03 | Overlay z-order vs ToastOverlay |
| UAT-04 | Bottom-bar overlap fix on small/secondary display (LAYOUT-01 root cause) |
| UAT-05 | Wayland GNOME Shell full-lifecycle confirmation |
| Overall line | `**Overall:** PENDING` (Task 3 checkpoint gate target) |

## Deviations from Plan

### [Rule 1 — Bug] Flaky `qtbot.wait(280)` race vs offscreen event-loop drain

- **Found during:** Task 1 stability stress-test (a 15-run loop) immediately
  after the initial test file commit.
- **Issue:** The first version of `test_full_compact_peek_lifecycle` used
  `qtbot.wait(280)` (and `qtbot.wait(300)` for the third test) immediately
  after a synthesized `MouseMove` on the left-edge trigger zone, asserting
  `_peek_overlay.isVisible() is True` right after the wait returned. On the
  offscreen Qt 6.11.0 platform, the event-loop drain occasionally lags the
  wall clock by a few-dozen ms, so the 280-ms `QTimer.singleShot` fires
  AFTER `qtbot.wait(280)` returns — making the immediate `isVisible`
  assertion race. Stress-test result: ~1 in 10 runs of `pytest tests/test_phase72_*.py -q`
  reported `1 failed, 40 passed` on `test_full_compact_peek_lifecycle` at
  the second-peek-cycle assertion (step 7).
- **Fix:** Replace all three peek-visibility assertions with
  `qtbot.waitUntil(predicate, timeout=1000)`. The substantive contract —
  "peek opens after the dwell completes" — is what `waitUntil` enforces;
  the literal "opens at exactly 280 ms" was never the goal. Two of the
  three call sites are in `test_full_compact_peek_lifecycle` (step 4 first
  peek + step 7 second peek); the third is the lifecycle-compressed peek
  inside `test_no_compact_setting_written_after_full_lifecycle`.
- **QA-05 preservation:** `qtbot.waitUntil` requires a callable, and the
  obvious lambda anti-pattern would violate the phase's no-lambda rule.
  Solution: a new top-level helper `_make_peek_visible_predicate(window)`
  returns a closure-based bound predicate that captures the window. The
  literal `grep -c "lambda" tests/test_phase72_integration.py` STILL
  returns 0 (the QA-05 acceptance gate stays satisfied).
- **Files modified:** `tests/test_phase72_integration.py` (29 insertions / 3
  deletions).
- **Commit:** `2468b0f` (`fix(72-05): replace fixed-wait dwell assertions
  with qtbot.waitUntil`).
- **Verification:** Same 15-run stress test after the fix: 15/15 PASS.

### [Rule 1 — Bug] Plan acceptance criterion `grep -ci X11` returned 5 (initial draft)

- **Found during:** Task 2 acceptance-criteria gate run on the first
  UAT-script draft.
- **Issue:** The plan's negative gate is `grep -ci "X11" 72-UAT-SCRIPT.md`
  must return 0. The initial draft mentioned X11 five times in
  "do NOT use X11" instruction text — each mention served the gate's
  intent (warn the user away from X11), but the literal grep counted
  them and FAILED the gate.
- **Fix:** Rewrote the relevant instruction paragraphs to positively frame
  Wayland confirmation — `echo "$XDG_SESSION_TYPE"` MUST return `wayland`,
  with no mention of any other session type. References to the project
  memory note (`project_deployment_target.md`) carry the rationale without
  naming X11 verbatim.
- **Files modified:** `.planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/72-UAT-SCRIPT.md`
  (3 paragraph rewrites).
- **Verification:** `grep -ci X11 72-UAT-SCRIPT.md` returns 0; `grep -ci wayland`
  returns 17.

### Out-of-scope: pre-existing test-suite failures

- **Type:** Out-of-scope / pre-existing test breakage on the worktree's
  base commit.
- **Observation:** Running the full `pytest tests/` suite reports 17
  failures + 18 errors. Spot-check: `tests/test_import_dialog_qt.py::test_audioaddict_tab_widgets`
  fails with `AttributeError: 'ImportDialog' object has no attribute '_aa_quality'`;
  several `test_main_window_media_keys.py` tests fail with
  `AttributeError: '_FakePlayer' object has no attribute 'underrun_recovery_started'`.
  These failures reproduce when this plan's changes are reverted (verified
  by 72-01-SUMMARY § "Full test suite has pre-existing failures unrelated
  to Wave 0"). They predate this phase entirely.
- **Disposition:** Out of scope per SCOPE BOUNDARY rule. The plan's
  `<acceptance_criteria>` line "Full test suite: `pytest tests -x` exits 0"
  cannot be satisfied for reasons predating Phase 72; the intent —
  "the integration test does not introduce new failures" — is verified
  by the focused `pytest tests/test_phase72_*.py` run (41/41 PASS) and by
  spot-checking that the same pre-existing failures appear before and
  after this plan's changes.

## Verification Results

| Check | Result |
| ----- | ------ |
| `pytest tests/test_phase72_integration.py -x -v` | 3 passed |
| `pytest tests/test_phase72_*.py` (all 5 plans' tests) | 41 passed |
| Stability stress-test: 15 consecutive runs of `pytest tests/test_phase72_*.py -q` | 15/15 PASS post-flaky-fix (was 14/15 pre-fix) |
| `grep -c "def test_full_compact_peek_lifecycle" tests/test_phase72_integration.py` | 1 |
| `grep -c "_splitter_sizes_before_compact" tests/test_phase72_integration.py` | 8 (≥ 2) |
| `grep -c "lambda" tests/test_phase72_integration.py` | 0 (QA-05 OK) |
| `test -f .planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/72-UAT-SCRIPT.md` | exit 0 |
| `grep -c "^## UAT-" 72-UAT-SCRIPT.md` | 5 |
| `grep -c "^\[ \]" 72-UAT-SCRIPT.md` | 5 (≥ 5) |
| `grep -ci wayland 72-UAT-SCRIPT.md` | 17 (≥ 1) |
| `grep -ci X11 72-UAT-SCRIPT.md` | 0 (negative gate OK) |
| `grep -c "^\*\*Overall:\*\* PENDING" 72-UAT-SCRIPT.md` | 1 (gate not yet closed) |
| `grep -c "^\*\*Overall:\*\* PASS" 72-UAT-SCRIPT.md` | 0 (Task 3 gate closed — correct) |

## Phase 72 Final Test Inventory (across all 5 plans)

| Plan | Test file | Tests | Cumulative |
| ---- | --------- | ----- | ---------- |
| 01 | `tests/test_phase72_assumptions.py` (Wave 0 spike — A1 INVALIDATED, A2 CONFIRMED) | 2 | 2 |
| 02 | `tests/test_phase72_now_playing_panel.py` (button + signal + icon helper) | 8 | 10 |
| 03 | `tests/test_phase72_compact_toggle.py` (MainWindow slot + Ctrl+B QShortcut) | 12 | 22 |
| 04 | `tests/test_phase72_peek_overlay.py` (peek overlay + lifecycle stubs filled) | 16 | 38 |
| 05 | `tests/test_phase72_integration.py` (end-to-end lifecycle + UAT script) | 3 | **41** |

**Total Phase 72 test count: 41 PASS** (stable across 15-run stress test).
This count does not yet include any tests the user might add post-UAT to
close a UAT-FAIL gap (a `Phase 72.1` gap-closure plan would extend the
file).

## Phase 72 Success Criteria

The phase's success-criteria check (per `72-CONTEXT.md` § In Scope) cannot
be finalized until UAT completes. The orchestrator-owned post-checkpoint
write will gate this section against the user's UAT result:

- [ ] Compact mode hides left column on Ctrl+B and on button click (UAT-01,
      UAT-04, UAT-05). **Automated tests confirm; UAT pending.**
- [ ] Bottom-bar overlap resolved on small display when compact mode is ON
      (UAT-04, the phase root-cause goal). **UAT pending — real-device
      requirement.**
- [ ] Hover-peek behaves per spec (D-11..D-15) — opens after 280ms on left
      ≤ 4px, closes on mouse-leave only, click-station keeps overlay
      open, peeked panel is fully interactive (UAT-02, UAT-05).
      **Automated tests confirm contract; UAT pending for feel/timing.**
- [ ] Session-only persistence holds — every app launch starts expanded,
      no `compact_*` keys in `repo._settings` after a full lifecycle
      (D-09). **Automated tests confirm at both unit (Plan 02 panel-level
      negative test + Plan 03 _on_compact_toggle negative test) and
      integration (Plan 05 lifecycle negative test) levels.**

## UAT Result

**Status:** PENDING — checkpoint gate is open. The user has not yet run
72-UAT-SCRIPT.md.

Once the user runs UAT and signs off (by editing the script's final line
from `**Overall:** PENDING` to `**Overall:** PASS`), this section will be
updated by the orchestrator's post-checkpoint pass, or by a subsequent
`Phase 72.1` gap-closure plan if any UAT item failed.

If PASS — Phase 72 closes; the SC list above gets all checkboxes ticked.
If FAIL — the user notes which UAT item(s) failed in the script's
"Failure notes" section, and the orchestrator scopes a Phase 72.1 plan
to fix the specific issue(s).

## Deferred Polish Items (from prior plans + new from Plan 05)

(These are tracked here only for visibility; they remain in
`deferred-items.md` for the canonical list.)

- **From Plan 04:** Pre-existing Qt teardown crash in a specific cross-file
  ordering (unrelated to Phase 72; documented in `deferred-items.md`).
- **From Plan 05:** None new yet — any UAT-surfaced "nice to have"
  (animation desire, alternate dwell time, etc.) will land here once the
  user fills in the UAT script's "Notes / observations" sections.

## Known Stubs

None. Every artifact in this plan is fully implemented:
- Integration tests run green against the production code (no mocks
  beyond `FakePlayer` / `FakeRepo`).
- UAT script is ready for the user to execute end-to-end.
- The Plan 04 stub-filling work has already eliminated every `pass`-body
  method declared in Plan 03.

## Threat Flags

None new. Plan 05 introduces:
- One new test file (`tests/test_phase72_integration.py`) — pure in-process
  Qt widget state, no I/O, no auth, no network, no IPC.
- One new docs file (`72-UAT-SCRIPT.md`) — markdown describing manual
  steps; no executable surface.

Per the plan's `<threat_model>` STRIDE register: T-72-07 (UAT execution)
Disposition: accept — manual test under user's Wayland session, no new
code, no new I/O.

## Self-Check: PASSED

- **Created files exist:**
  - `tests/test_phase72_integration.py` — 419 lines (after the Rule 1
    fix), 3 tests, all PASS (`pytest -v` exit 0 across 15 consecutive
    runs).
  - `.planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/72-UAT-SCRIPT.md` —
    5 UAT items, 5 pass-criteria checkboxes, 17 Wayland references, 0 X11
    references, 1 `**Overall:** PENDING` line.
- **Commits exist in the worktree branch `worktree-agent-abb1462623f2ef0b8`:**
  - `4c32cb3` `test(72-05): end-to-end integration test for compact+peek lifecycle` — verified via `git log --oneline`.
  - `f1d210b` `docs(72-05): manual UAT script with 5 Wayland-targeted items` — verified via `git log --oneline`.
  - `2468b0f` `fix(72-05): replace fixed-wait dwell assertions with qtbot.waitUntil` — verified via `git log --oneline`.
- **Acceptance criteria:** All Task 1 and Task 2 gates PASS (see
  Verification Results table above). Task 3 gate is the human-verify
  checkpoint — by design NOT closed by this agent.
- **Success criteria (from plan `<success_criteria>`):**
  - End-to-end test green (full compact+peek lifecycle locked): VERIFIED
    (41/41 Phase 72 tests PASS).
  - UAT script on disk with 5 numbered items, all referencing Wayland
    explicitly, none referencing X11: VERIFIED (negative + positive gates
    both pass).
  - User has run UAT and approved: PENDING — by design, Task 3 emits the
    checkpoint; this agent does not self-certify.

---

*Plan 72-05 completed (Tasks 1+2): 2026-05-13. Task 3 awaits user UAT.*
*Phase: 72-fullscreen-mode-hide-left-column-for-compact-displays*
