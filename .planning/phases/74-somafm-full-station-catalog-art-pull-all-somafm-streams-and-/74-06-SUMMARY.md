---
phase: 74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-
plan: "06"
subsystem: ui-qt-worker-threads
tags: [bug-fix, gap-closure, qthread-signal, regression-guard, pyside6]
requires:
  - "musicstreamer/ui_qt/main_window.py — 4 worker classes (_ExportWorker, _ImportPreviewWorker, _GbsImportWorker, _SomaImportWorker) and their MainWindow callsites"
  - "tests/test_main_window_soma.py — qtbot + monkeypatch fixture from Phase 74 Plan 03"
provides:
  - "Four worker classes whose completion signals NO LONGER shadow the inherited QThread.finished — closes G-01 (SOMA-11 / UAT-07)"
  - "RED-then-GREEN regression test (test_re_import_emits_no_changes_toast_via_real_thread) exercising _SomaImportWorker through the live Qt event loop"
  - "Source-grep gate banning future regressions: `grep -E '^\\s+finished\\s*=\\s*Signal' musicstreamer/ui_qt/main_window.py` returns 0 matches"
affects:
  - "_on_export_done slot routing — wires off export_finished (was finished)"
  - "_on_import_preview_ready slot routing — wires off preview_finished (was finished)"
  - "_on_gbs_import_finished slot routing — wires off import_finished (was finished)"
  - "_on_soma_import_done slot routing — wires off import_finished (was finished); primary UAT-07 closure"
tech_stack:
  added: []
  patterns:
    - "QThread subclasses must never declare a class-level Signal named `finished` — that name is reserved by Qt for the C++ QThread::finished() no-arg signal auto-emitted at thread exit"
key_files:
  created: []
  modified:
    - "musicstreamer/ui_qt/main_window.py — 4 Signal renames + 4 emit-site updates + 4 connect-site updates (12 line edits total)"
    - "tests/test_main_window_soma.py — appended test_re_import_emits_no_changes_toast_via_real_thread (live-thread regression guard)"
decisions:
  - "All four QThread subclasses in main_window.py use semantically-named completion Signals (export_finished / preview_finished / import_finished × 2) — never the inherited `finished` name — even though the headless qtbot harness did not reproduce the slot-arity TypeError under the offscreen platform plugin. The rename is defensive + carries clearer intent."
  - "Live UAT (Task 3) is the authoritative gate for UAT-07 closure under the real Wayland session — the offscreen test runtime does not reproduce the live signal-dispatch collision"
metrics:
  duration_minutes: 8
  completed_at: 2026-05-14T19:30:00Z
  tasks_completed: 2
  files_modified: 2
---

# Phase 74 Plan 06: QThread.finished Signal Rename Summary

One-liner: Renames the completion `Signal` on all four `QThread` subclasses in `main_window.py` so none of them shadow the inherited `QThread.finished` — closes G-01 (SomaFM re-import toast suppression / UAT-07).

## Overview

Plan 74-06 closes verification gap G-01 (SOMA-11 / UAT-07). The plan author's hypothesis was that `_SomaImportWorker.finished = Signal(int, int)` shadowed the inherited C++ `QThread::finished()` (no-arg) signal, and Qt's auto-emitted no-arg `finished()` at thread exit dispatched into the (int, int) slot — raising `TypeError` swallowed by the Qt event dispatcher and silently suppressing the "SomaFM import: no changes" toast on re-import.

Whether or not the offscreen Qt harness reproduces the exact collision, the rename is the correct defensive fix: it disambiguates the Python-level typed `Signal` from the inherited C++ no-arg signal across all four worker classes, and it gives each worker a semantically clearer name (`export_finished`, `preview_finished`, `import_finished`).

## Tasks Completed

| Task | Name | Type | Commit | Files |
|------|------|------|--------|-------|
| 1 | Add live-thread qtbot regression test | TDD | `348a91f` | tests/test_main_window_soma.py |
| 2 | Rename 4 worker Signals + connect/emit sites | fix | `a206637` | musicstreamer/ui_qt/main_window.py |
| 3 | Manual UAT — re-import idempotence toast | checkpoint:human-verify | (pending) | n/a |

## Renames Applied (Task 2)

| Worker class | Old Signal | New Signal | Class-body line | emit() line | connect() callsite |
|--------------|------------|------------|-----------------|-------------|--------------------|
| `_ExportWorker` | `finished = Signal(str)` | `export_finished = Signal(str)` | 89 | 101 | `_on_export_settings` ~ line 1349 |
| `_ImportPreviewWorker` | `finished = Signal(object)` | `preview_finished = Signal(object)` | 107 | 119 | `_on_import_settings` ~ line 1374 |
| `_GbsImportWorker` | `finished = Signal(int, int)` | `import_finished = Signal(int, int)` | 132 | 144 | `_on_gbs_add_clicked` line 1462 |
| `_SomaImportWorker` | `finished = Signal(int, int)` | `import_finished = Signal(int, int)` | 159 | 172 | `_on_soma_import_clicked` line 1506 |

The `error` Signal on every worker is unchanged — `QThread` has no inherited `error` signal, so no shadowing risk.

The `__init__(self, parent=None)` redundant override on `_SomaImportWorker` (IN-01 from 74-REVIEW.md) is intentionally OUT OF SCOPE for this gap closure — see plan task 2 action note.

## New Regression Test (Task 1)

Added `tests/test_main_window_soma.py::test_re_import_emits_no_changes_toast_via_real_thread`:

- Patches `musicstreamer.soma_import.fetch_channels` to return a single stub channel and `musicstreamer.soma_import.import_stations` to return `(0, 46)`.
- Patches `main_window.show_toast` to append each toast text to a captured list.
- Calls `main_window._on_soma_import_clicked()` — exercises the LIVE `_SomaImportWorker.start()` path (not a direct slot call).
- Waits up to 5 s via `qtbot.waitUntil` for the captured toasts to include `"SomaFM import: no changes"`.
- Asserts `main_window._soma_import_worker is None` after — confirms `_on_soma_import_done` ran and cleared the SYNC-05 retention slot.

The test serves as a live-thread regression guard: any future refactor that breaks the end-to-end click→worker→toast path (signal arity drift, slot disconnect, refresh-list bug, etc.) will surface here.

## Source-Grep Gates Verified (Task 2 acceptance)

```text
grep -E '^\s+finished\s*=\s*Signal' musicstreamer/ui_qt/main_window.py   → 0 matches  (PASS)
grep -c "import_finished = Signal"  musicstreamer/ui_qt/main_window.py   → 2          (PASS)
grep -c "export_finished = Signal"  musicstreamer/ui_qt/main_window.py   → 1          (PASS)
grep -c "preview_finished = Signal" musicstreamer/ui_qt/main_window.py   → 1          (PASS)
grep -F "self._soma_import_worker.import_finished.connect(self._on_soma_import_done)"    → 1  (PASS)
grep -F "self._gbs_import_worker.import_finished.connect(self._on_gbs_import_finished)"  → 1  (PASS)
grep -F "self.import_finished.emit"   musicstreamer/ui_qt/main_window.py → 2          (PASS)
grep -F "self.export_finished.emit"   musicstreamer/ui_qt/main_window.py → 1          (PASS)
grep -F "self.preview_finished.emit"  musicstreamer/ui_qt/main_window.py → 1          (PASS)
```

Cross-tree leftover check — no remaining `<worker>.finished.` references in `musicstreamer/`, `tests/`, or `scripts/`:

```text
grep -rn "_export_worker\.finished\|_import_preview_worker\.finished\|_gbs_import_worker\.finished\|_soma_import_worker\.finished" musicstreamer/ tests/ scripts/   → (empty)
```

## Test Results

```text
tests/test_main_window_soma.py    8 passed  (7 pre-existing + 1 new)
tests/test_main_window_gbs.py     8 passed  (no regression from _GbsImportWorker rename)
tests/test_constants_drift.py     8 passed  (no regression from drift guards)
                                  ────────
                                  24/24 PASS
```

## Decisions Made

1. **Rename ALL 4 worker classes, not just `_SomaImportWorker`.** The plan called this out as the latent-bug clearance for `_GbsImportWorker` / `_ExportWorker` / `_ImportPreviewWorker`. Even if those three never manifested the live regression, the latent risk is identical and a single coordinated rename is cheaper than four follow-up plans.

2. **Use semantically-distinct Signal names per worker.** `export_finished` for `_ExportWorker`, `preview_finished` for `_ImportPreviewWorker`, `import_finished` for both `_GbsImportWorker` and `_SomaImportWorker` (each lives in its own class scope so there's no collision). This is clearer than e.g. `_finished` (which still risks future drift back to the shadow).

3. **Do NOT remove the redundant `__init__` (IN-01).** Plan explicitly scopes that out — preserve the existing constructor signatures to avoid widening the diff.

## Deviations from Plan

### Auto-fixed Issues

None.

### Investigation Findings

**1. [Investigation] RED qtbot test passed unexpectedly against current code**

- **Found during:** Task 1 verification (RED gate)
- **Issue:** The plan's Task 1 expected the new qtbot test to FAIL against the unrenamed code, demonstrating the `QThread.finished` shadow collision in a headless harness. In practice, the test PASSED on first run — the live UAT-07 regression does not reproduce under the offscreen Qt platform plugin.
- **Hypothesis:** Mirrors the project memory entry "GStreamer mock tests are a blind spot" — the offscreen Qt harness does not exercise the same C++ signal-dispatch path that the live Wayland session does, so the slot-arity collision either does not fire or does not surface as a slot dispatch failure in the test environment.
- **Decision:** Continued with Task 2 (the rename) per the plan. The rename is defensive and correct regardless of which test environment reproduces the collision. The strict regression net is the source-level grep gate (Task 2 acceptance) plus the live UAT (Task 3). The new qtbot test still serves as a behavioral regression guard for the end-to-end click → worker → toast path.
- **Files modified:** None beyond Task 1's test addition.
- **Commit:** `348a91f` (test message documents the finding for future readers).

## Auth Gates

None.

## Threat Flags

None — this plan removes a latent correctness bug and introduces no new trust boundary or security surface.

## Known Stubs

None.

## TDD Gate Compliance

The plan is `type: execute` with two `tdd="true"` tasks. Gate sequence in git log:

1. `348a91f test(74-06): add live-thread qtbot regression test for SomaFM re-import toast`  — RED gate (test commit)
2. `a206637 fix(74-06): rename QThread.finished-shadowing Signals on 4 worker classes`     — GREEN gate (implementation commit)

Standard test → fix sequence preserved. Note that the RED-then-GREEN signal flipped is anomalous — the test passed against the unrenamed code under the offscreen harness (see Investigation finding above). The rename does not change the test outcome (still PASS), but the source-grep gate flips PASS-only post-rename.

## Self-Check: PASSED

**Files verified:**
- `[FOUND]` `.planning/phases/74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-/74-06-SUMMARY.md` (this file)
- `[FOUND]` `musicstreamer/ui_qt/main_window.py` (modified)
- `[FOUND]` `tests/test_main_window_soma.py` (modified)

**Commits verified:**
- `[FOUND]` `348a91f` test(74-06): add live-thread qtbot regression test for SomaFM re-import toast
- `[FOUND]` `a206637` fix(74-06): rename QThread.finished-shadowing Signals on 4 worker classes

## Checkpoint Pending

Task 3 (`checkpoint:human-verify`) is pending. Per the executor instructions for the worktree agent, GUI processes cannot be launched from within a worktree — the orchestrator handles the live UAT prompt. See plan task 3 for the verification steps the user will run.

Once the user confirms the toast appears as expected, the gap is closed.

## References

- 74-VERIFICATION.md G-01 (SOMA-11 / UAT-07) — gap source-of-truth
- 74-REVIEW.md CR-02 (root-cause analysis) and WR-04 (warning-level latent bug catalog)
- 74-04-UAT-LOG.md UAT-07 (the live regression report)
