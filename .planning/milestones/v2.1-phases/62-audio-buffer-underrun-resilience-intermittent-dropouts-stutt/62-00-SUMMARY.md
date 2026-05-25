---
phase: 62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt
plan: 00
subsystem: testing
tags: [pytest, qt-threading, gstreamer, tdd-red, bug-09]

# Dependency graph
requires:
  - phase: 47-stats-for-nerds-and-autoeq
    provides: "Player.buffer_percent Signal + _on_gst_buffering bus handler + per-stream _last_buffer_percent dedup sentinel (Phase 47.1 D-12/D-14) — extended in Plan 02 with the underrun cycle tracker"
  - phase: 43.1-windows-media-keys
    provides: "qt-glib-bus-threading Pitfall 1+2 — bus.add_signal_watch on bridge thread + cross-thread Signal.emit (NOT QTimer.singleShot from non-QThread) — locked into Plan 02 contract via Test 1/Test 7 in test_player_underrun.py"
provides:
  - "20 RED tests across 3 new files locking Phase 62 contract for Plans 01-03"
  - "tests/test_player_underrun_tracker.py — 7 unit tests for _BufferUnderrunTracker pure-logic (D-01..D-04, D-02, D-03, Pitfall 3, Discretion network hint)"
  - "tests/test_player_underrun.py — 8 integration tests for Player wiring (Pitfall 1/2/3, D-02/D-03/D-07, T-62-01 log injection, T-62-02 force-close-before-bind ordering)"
  - "tests/test_main_window_underrun.py — 5 integration tests for MainWindow cooldown (D-06/D-08), closeEvent (D-03/Pitfall 4), __main__ logger (Pitfall 5)"
  - "FakePlayer fixture extension: underrun_recovery_started Signal + shutdown_underrun_tracker no-op stub (preserves 46-test integration baseline)"
affects: [62-01, 62-02, 62-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD-RED Wave 0 — tests fail via ImportError / AttributeError on names introduced by Plans 01-03 (no pytest.fail placeholders)"
    - "T-62-01 mitigation lock — caplog test asserts station_name='Test Station' single-quoted form, forcing Plan 02 to use %r format specifier for log injection escape"
    - "T-62-02 ordering lock — close-record url assertion proves force_close runs BEFORE bind_url to new URL (no race during _try_next_stream)"
    - "Pitfall 5 file-level grep gate — regex pin getLogger('musicstreamer.player').setLevel(INFO) AND retain basicConfig(WARNING) (no global INFO bump that would surface other modules' chatter)"
    - "PATTERNS §S-7 helper duplication — make_player + _fake_buffering_msg copied verbatim from test_player_buffering.py rather than extracted to conftest"

key-files:
  created:
    - "tests/test_player_underrun_tracker.py — 104 lines, 7 RED unit tests"
    - "tests/test_player_underrun.py — 201 lines, 8 RED integration tests"
    - "tests/test_main_window_underrun.py — 132 lines, 5 RED integration tests"
    - ".planning/phases/62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt/62-00-SUMMARY.md"
  modified:
    - "tests/test_main_window_integration.py — extended FakePlayer with underrun_recovery_started Signal + shutdown_underrun_tracker no-op (additive; 46 existing tests still green)"

key-decisions:
  - "Phase 62 Wave 0 — RED via real ImportError/AttributeError, not pytest.fail (the import failure IS the contract; mirrors Phase 60.4 / Phase 999.1 Wave 0 conventions)"
  - "Phase 62 — make_player + _fake_buffering_msg duplicated verbatim from test_player_buffering.py per PATTERNS §S-7 (no shared conftest extraction)"
  - "Phase 62 — Pitfall 5 enforced via file-level regex on __main__.py source (not pytest plugin / log capture) — Plan 03 must add per-logger setLevel and keep basicConfig(WARNING) intact"

patterns-established:
  - "T-62-01 single-quote canary — `assert \"station_name='Test Station'\" in msg` is a one-line invariant that fails the moment Plan 02 drifts from %r to %s on the log call"
  - "T-62-02 ordering canary — `assert closed_records[0].url == 'http://old.test/'` after _try_next_stream proves force_close-before-bind_url; the new URL is never bound during the close emission"
  - "Wave 0 success criterion: collection ImportError IS valid RED — tracker test file blocks at line 10 import, the other 13 tests collect and run-fail with AttributeError (combined: 20 RED)"

requirements-completed: [BUG-09]

# Metrics
duration: 5min
completed: 2026-05-08
---

# Phase 62 Plan 00: Wave 0 RED Test Contract Summary

**Locked the Phase 62 / BUG-09 executable contract — 20 RED tests across 3 new files plus 1 fixture extension — encoding D-01..D-09, T-62-01 log-injection mitigation, T-62-02 force-close-before-bind ordering, and qt-glib-bus-threading Pitfalls 1/2/3/5 as machine-checkable assertions before any production code is written**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-08T02:08:33Z
- **Completed:** 2026-05-08T02:13:38Z
- **Tasks:** 4
- **Files modified:** 4 (3 created, 1 extended)

## Accomplishments
- 20 RED tests authored: 7 unit (tracker pure-logic) + 8 integration (Player) + 5 integration (MainWindow)
- T-62-01 STRIDE mitigation locked into a one-line caplog grep — `station_name='Test Station'` single-quote canary fails if Plan 02 ever drifts from `%r` to `%s`
- T-62-02 STRIDE ordering invariant locked into a one-line record assertion — close record's URL must equal the OLD URL, proving force_close ran BEFORE bind_url to the new URL during `_try_next_stream`
- FakePlayer extended additively (Signal + no-op method) — all 46 pre-existing MainWindow integration tests still green
- D-09 invariant tests (BUFFER_DURATION/SIZE constants) verified untouched

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend FakePlayer with Phase 62 scaffolding** — `aa081a9` (test)
2. **Task 2: Create tests/test_player_underrun_tracker.py with 7 RED unit tests** — `7292bdc` (test)
3. **Task 3: Create tests/test_player_underrun.py with 8 RED Player integration tests** — `8b74c0b` (test)
4. **Task 4: Create tests/test_main_window_underrun.py with 5 RED MainWindow tests** — `3425d3e` (test)

**Plan metadata:** _to be added on final docs commit_

## Files Created/Modified
- `tests/test_player_underrun_tracker.py` (created, 104 lines) — 7 RED unit tests for `_BufferUnderrunTracker` pure-logic state machine; pure-Python (no qtbot fixture); injectable clock for deterministic `duration_ms` assertions; covers D-04 unarmed gate, D-01/D-04 arm-then-drop opens cycle, D-02 close record fields, D-03 force_close + idempotent guard, Pitfall 3 bind_url state reset, Discretion network cause_hint flip
- `tests/test_player_underrun.py` (created, 201 lines) — 8 RED integration tests for Player buffer-underrun cycle wiring; reuses `make_player` + `_fake_buffering_msg` verbatim from test_player_buffering.py (per PATTERNS §S-7); covers Pitfall 2 queued-Signal emission from bus handler, D-02 cycle_closed record payload, T-62-02 force_close-before-bind ordering during failover, D-03 pause/stop force-close, D-02+T-62-01 structured INFO log with `%r` quoting, D-07 1500ms dwell-timer fires recovery, D-07 sub-dwell silent
- `tests/test_main_window_underrun.py` (created, 132 lines) — 5 RED integration tests for MainWindow cooldown + closeEvent + __main__ logger; reuses FakePlayer + FakeRepo from test_main_window_integration.py (extended in Task 1); covers D-06 first-call shows toast, D-08 cooldown gate (suppress within 10s, allow after 10s — monkeypatch `time.monotonic` for determinism), D-03/Pitfall 4 closeEvent calls Player.shutdown_underrun_tracker, Pitfall 5 file-level regex pin on per-logger `setLevel(INFO)` plus retained `basicConfig(WARNING)`
- `tests/test_main_window_integration.py` (modified, +9 lines) — FakePlayer extended with `underrun_recovery_started = Signal()` (Phase 62 D-07 main→MainWindow toast trigger) + `shutdown_underrun_tracker(self) -> None` no-op stub (Phase 62 D-03 closeEvent contract); additive change preserves the 46-test pre-existing baseline

## Decisions Made
- **Wave 0 RED via real ImportError/AttributeError** — no `pytest.fail("not yet implemented")` placeholders. Test files import names that don't exist yet (`_BufferUnderrunTracker`, `Player._underrun_cycle_opened`, `Player.shutdown_underrun_tracker`, etc.) and that import-time/access-time failure IS the contract. Mirrors Phase 60.4 / Phase 999.1 Wave 0 convention.
- **Helper duplication, not conftest extraction** — `make_player` and `_fake_buffering_msg` are verbatim duplicates of test_player_buffering.py:8-27. Per PATTERNS §S-7, the codebase convention is per-file helper duplication; conftest extraction would be a project-first deviation rejected by the plan.
- **Pitfall 5 enforced via file-level regex on __main__.py source** — rather than asserting via pytest log capture (which would require running main()), Test 5 reads `musicstreamer/__main__.py` directly and regex-matches `getLogger('musicstreamer.player').setLevel(logging.INFO)` AND `basicConfig(level=logging.WARNING)`. Plan 03 must add the per-logger line without bumping the global level.

## Deviations from Plan

### Auto-fixed Issues

None — Wave 0 is purely additive test authoring with no production-code changes.

### Acceptance-Criterion Discrepancy (documented, not auto-fixed)

**1. [Documentation] Task 3 grep gate `qtbot.waitSignal ≥3` underspecified vs. prescribed test bodies**
- **Found during:** Task 3 (verification)
- **Issue:** Plan acceptance criterion for `tests/test_player_underrun.py` reads `grep -c "qtbot.waitSignal" tests/test_player_underrun.py returns ≥3`, but the verbatim test bodies prescribed in the `<action>` block only use `qtbot.waitSignal` in Test 1 (cycle_opened) and Test 7 (dwell_timer_fires_after_threshold) — count = 2. Tests 2-6 + 8 deliberately use the list-collector + `qtbot.wait(N)` pattern (with `closed_records.append` connected to `_underrun_cycle_closed`) which is the documented assertion shape for tests that need to inspect the emitted payload, not just observe the signal fires.
- **Fix:** None applied. The verbatim test bodies match the action specification and lock the canonical assertion shape. The acceptance-criterion grep gate appears to be miscalibrated relative to the prescribed test bodies. Documenting here so Plan 02 verification doesn't trip on a stale gate; the test contract itself (8 tests covering D-02/D-03/D-07/T-62-01/T-62-02) is fully encoded.
- **Files modified:** None (test bodies match the prescribed shape; no edit needed)
- **Verification:** All 8 tests collect successfully + fail RED with AttributeError on `_tracker`/`_underrun_cycle_opened`/etc; the 5 list-collector tests still encode the contract via `len(closed_records) == 1` + payload field assertions
- **Committed in:** `8b74c0b` (Task 3 commit)

---

**Total deviations:** 1 documented acceptance-criterion miscalibration (no code change)
**Impact on plan:** Zero impact on Phase 62 contract — 20 RED tests cover all 9 CONTEXT decisions + 2 STRIDE threats + 5 Pitfalls; the documented discrepancy is between a grep gate and the prescribed test body and does not weaken the test contract.

## Issues Encountered

- **Test 1 RED state surfaces as ImportError, not AttributeError** — `monkeypatch.setattr("musicstreamer.ui_qt.main_window.time.monotonic", ...)` requires `main_window.py` to `import time` at module level. Pre-Plan-03, `main_window.py` doesn't import `time`, so the monkeypatch raises `ImportError: import error in musicstreamer.ui_qt.main_window.time: No module named 'musicstreamer.ui_qt.main_window.time'`. This is a legitimate RED contract — Plan 03 must add `import time` AND call `time.monotonic()` in the cooldown slot for the monkeypatch to bind. Documented; no action needed in Wave 0.

## Self-Check: PASSED

**Files verified to exist:**
- `tests/test_player_underrun_tracker.py` — FOUND
- `tests/test_player_underrun.py` — FOUND
- `tests/test_main_window_underrun.py` — FOUND
- `tests/test_main_window_integration.py` — FOUND (modified, 46 existing tests still green)

**Commits verified to exist:**
- `aa081a9` — FOUND (Task 1: extend FakePlayer)
- `7292bdc` — FOUND (Task 2: tracker RED tests)
- `8b74c0b` — FOUND (Task 3: Player integration RED tests)
- `3425d3e` — FOUND (Task 4: MainWindow + __main__ RED tests)

**Verification gates passed:**
- 20 RED tests authored (7 + 8 + 5)
- 4 D-09 invariant tests still pass (BUFFER_DURATION_S / BUFFER_SIZE_BYTES untouched)
- 46 pre-existing MainWindow integration tests still pass (FakePlayer extension is additive)
- 54 tests pass across pre-existing test_main_window_integration + test_player_buffering + test_player_buffer

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

**Ready for Plan 01:** Wave 1 — implement `_BufferUnderrunTracker` (pure-logic class + `_CycleClose` dataclass) in `musicstreamer/player.py`. Plan 01 turns the 7 tracker unit tests GREEN; the 8 Player integration tests + 5 MainWindow integration tests stay RED until Plans 02 + 03.

**Open questions for Plans 01-03:**
1. **Plan 01 / `_close()` reset semantics** — Test 5 (`test_force_close_returns_record_with_outcome`) asserts that `force_close('stop')` on an already-closed cycle returns `None`. The cleanest implementation is for `force_close` to clear the `open` flag after emitting the record, so a second call sees no open cycle. Plan 01's `<implementation>` block should pin this idempotent guard explicitly.
2. **Plan 02 / `_streams_queue` shape during failover** — Test 3 (`test_try_next_stream_force_closes_with_failover_outcome`) seeds `player._streams_queue = [new_stream]` and `player._is_first_attempt = False` before calling `_try_next_stream()`. Plan 02 should preserve this seam (don't refactor `_streams_queue` into a different attribute name) so the test continues to drive the failover path.
3. **Plan 03 / `import time` placement in main_window.py** — Plan 03 must add `import time` at the top of `musicstreamer/ui_qt/main_window.py` before `time.monotonic()` is referenced in the cooldown slot, otherwise Tests 1-3 fail at the monkeypatch step (not at the assertion). Suggest placing it adjacent to the existing `import logging` if present, alphabetically.

**Blockers/concerns:**
- None. Wave 0 contract fully encoded; D-09 invariants preserved; no production code touched.

---
*Phase: 62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt*
*Completed: 2026-05-08*
