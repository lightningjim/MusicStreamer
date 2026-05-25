---
phase: 57-windows-audio-glitch-test-fix
plan: 01
subsystem: testing
tags: [windows, smtc, asyncmock, win-04, test-fix, winrt-mock]

# Dependency graph
requires:
  - phase: 43.1-windows-media-keys-smtc
    provides: "Production `_await_store(writer)` + `asyncio.run(_await_store(writer))` driver in smtc.py — the awaited winrt path that the AsyncMock now satisfies"
provides:
  - "Linux-CI-green `tests/test_media_keys_smtc.py::test_thumbnail_from_in_memory_stream` (was failing on `MagicMock object can't be awaited`)"
  - "First AsyncMock convention seeded in tests/ — future async winrt methods can copy the `return_value.store_async = AsyncMock(...)` shape"
affects: [57-02, 57-03, 57-04, 57-05, 43.1-windows-media-keys-smtc]

# Tech tracking
tech-stack:
  added: []  # AsyncMock is stdlib (unittest.mock) — no new dependency
  patterns:
    - "AsyncMock for awaitable winrt class-instance methods: set on `<MockClass>.return_value.<method>` (not `<MockClass>.<method>`) so production-code instance awaits resolve"

key-files:
  created: []
  modified:
    - "tests/test_media_keys_smtc.py"

key-decisions:
  - "D-08 minimal patch shape — top-of-file `from unittest.mock import AsyncMock, MagicMock` (line 13) over inline import; matches existing convention"
  - "D-09 scope — only `DataWriter.return_value.store_async` becomes AsyncMock; InMemoryRandomAccessStream / RandomAccessStreamReference / write_bytes stay MagicMock because they are synchronous in production"
  - "D-10 invariant preserved — musicstreamer/media_keys/smtc.py was NOT edited (production path was already correct; Phase 43.1 UAT validated against real winrt)"

patterns-established:
  - "AsyncMock-on-return_value pattern: when a winrt class is mocked via `MagicMock(name=...)` and production code calls `<class>(args)` then awaits an instance method, the awaitable lives on `<MockClass>.return_value.<method>`, NOT on `<MockClass>.<method>` — production awaits the instance, not the class"
  - "Failure-mode forensics: SMTC's broad try/except in publish_metadata swallows `TypeError: object MagicMock can't be used in 'await' expression`, surfacing as a downstream `create_from_stream.called` AssertionError. Future debug: check the captured WARNING log for the underlying await failure before chasing the failed assertion."

requirements-completed: [WIN-04]

# Metrics
duration: 3min
completed: 2026-05-02
---

# Phase 57 Plan 01: WIN-04 SMTC Thumbnail Test AsyncMock Fix Summary

**Replaced implicit `MagicMock` with `AsyncMock` for `DataWriter().store_async` in `tests/test_media_keys_smtc.py::_build_winrt_stubs` so `await writer.store_async()` resolves cleanly; production `smtc.py` untouched (D-10).**

## Performance

- **Duration:** ~3 min (incl. RED verification + full-suite run)
- **Started:** 2026-05-02T23:44:42Z
- **Completed:** 2026-05-02T23:47:36Z
- **Tasks:** 1 / 1
- **Files modified:** 1 (tests/test_media_keys_smtc.py)

## Accomplishments

- **WIN-04 closed.** `test_thumbnail_from_in_memory_stream` now passes — no `MagicMock object can't be awaited` swallowed-await chain.
- **D-08 / D-09 / D-10 invariants all preserved.** Two-line essence patch (one import addition + one attribute assignment), exactly the shape locked by 57-CONTEXT.md and 57-PATTERNS.md.
- **AsyncMock convention seeded in test suite.** No prior AsyncMock usage existed under `tests/`; future awaitable winrt methods now have a precedent to copy (one attribute on `<MockClass>.return_value`).
- **Full Linux test suite remains green where it was green** — 958 passing, 1 skipped, 0 new failures introduced. The 10 pre-existing failures (mpris2, station_list_panel, twitch_auth) predate this work and are out of scope.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add AsyncMock to import + attach AsyncMock store_async to DataWriter mock** — `c1c783c` (test)

(Plan was a single-task TDD plan. Per the gate-sequence rule for `tdd="true"` tasks, the RED phase was confirmed before the patch was applied — `test_thumbnail_from_in_memory_stream` fails on `ca0dff5` with the captured warning `'MagicMock' object can't be awaited`. The single commit is a `test:` commit because the entire diff lives in `tests/`; production code was deliberately untouched per D-10. There is no `feat:` commit for this plan because the production GREEN code already exists from Phase 43.1 — WIN-04 is purely a test-side correctness fix to a mock that was incorrectly built when the SMTC backend was first stubbed for Linux CI.)

**Plan metadata:** (will be added by orchestrator after wave completes — this executor does not write the metadata commit because STATE.md / ROADMAP.md updates are owned by the orchestrator in worktree mode.)

## Files Created/Modified

- `tests/test_media_keys_smtc.py` — Two edits, 5 lines added net:
  - Line 13: `from unittest.mock import MagicMock` → `from unittest.mock import AsyncMock, MagicMock`
  - Lines 96-99 (inserted between existing lines 95 and 96): a 3-line `# Phase 57 / WIN-04 D-08 ...` comment block + `storage_streams.DataWriter.return_value.store_async = AsyncMock(name="store_async")` assignment, sitting between the `DataWriter = MagicMock(...)` line and the `RandomAccessStreamReference = MagicMock(...)` line so the fix is co-located with the surrounding mock graph.

### Exact Diff Applied

```diff
@@ -10,7 +10,7 @@ import tomllib
 import types
 import unittest.mock as mock  # noqa: F401
 from pathlib import Path
-from unittest.mock import MagicMock
+from unittest.mock import AsyncMock, MagicMock

 import pytest

@@ -93,6 +93,10 @@ def _build_winrt_stubs():
     storage_streams = types.ModuleType("winrt.windows.storage.streams")
     storage_streams.InMemoryRandomAccessStream = MagicMock(name="InMemoryRandomAccessStream")
     storage_streams.DataWriter = MagicMock(name="DataWriter")
+    # Phase 57 / WIN-04 D-08: instances of DataWriter must carry an awaitable
+    # `store_async` attribute. Production `_await_store` (smtc.py:52) awaits it.
+    # Scoped per D-09 to ONLY this attribute -- no broader winrt-async audit.
+    storage_streams.DataWriter.return_value.store_async = AsyncMock(name="store_async")
     storage_streams.RandomAccessStreamReference = MagicMock(name="RandomAccessStreamReference")

     foundation = types.ModuleType("winrt.windows.foundation")
```

(One file changed, 5 insertions, 1 deletion — matches PLAN.md's locked `D-08 + 3-line comment + 1-line assignment` shape exactly.)

## Decisions Made

None novel — followed PLAN.md and 57-CONTEXT.md verbatim:

- D-08: top-of-file `from`-import addition (matches existing convention; PLAN.md explicitly chose this shape from the two D-08-permitted alternatives).
- D-09: scoped fix to `store_async` only; did NOT audit the rest of `_build_winrt_stubs` for hypothetical future async winrt methods.
- D-10: production `musicstreamer/media_keys/smtc.py` not touched. Phase 43.1's `asyncio.run(_await_store(writer))` driver is already correct (UAT-validated against real winrt 3.2.x).

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

### Test infrastructure: pytest extras + system PyGObject

- **Issue:** First attempt to run pytest via `uv run --with pytest` created a fresh virtualenv that did not include `pytest-qt` (under `[project.optional-dependencies].test`) and did not include `gi` (PyGObject is installed via apt, not via uv per the pyproject comment; the project's primary `.venv` has `include-system-site-packages = true`).
- **Resolution:** Switched to running pytest via the project's primary venv with `PYTHONPATH=.` so the worktree's source tree is the one imported. This is the project's standard test invocation; no code change required, just the right invocation. The plan's verify command will work out-of-the-box for any local developer who already has the project venv set up; CI uses its own conda+pip recipe.
- **Impact:** None. The patch correctness is verified — single test passes, full file passes, full suite produces no new failures vs. base.

### Pre-existing test failures (out of scope, NOT introduced by WIN-04)

Stashed the patch, ran the full suite on base ref `ca0dff5`, and confirmed all 10 failures pre-exist. This work introduced zero new failures.

| File / Test | Pre-existing on ca0dff5 | Status post-WIN-04 |
|---|---|---|
| tests/test_media_keys_mpris2.py (7 tests) | failing | unchanged |
| tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode | failing | unchanged |
| tests/test_station_list_panel.py::test_refresh_recent_updates_list | failing | unchanged |
| tests/test_twitch_auth.py::test_play_twitch_sets_plugin_option_when_token_present | failing | unchanged |

Per the executor scope-boundary rule ("Only auto-fix issues DIRECTLY caused by the current task's changes. Pre-existing... failures in unrelated files are out of scope"), these 10 failures are not WIN-04's concern. They should be triaged separately — possibly under a v2.1 follow-up phase or rolled into Phase 57 Plan 05 UAT scope if the executor for that plan finds they regressed during the milestone.

### `uv.lock` reconciliation (out of scope)

- `uv.lock` was modified by `uv` itself when our worktree ran `uv run` for the first time. The change is purely a `version = "2.0.0" → "2.1.58"` reconciliation to match `pyproject.toml`. This change pre-dates and is independent of the WIN-04 patch, was not staged into our task commit, and remains unstaged in the worktree at SUMMARY-write time. Mentioned for transparency; orchestrator can decide whether to roll it into the metadata commit or leave for a separate maintenance commit.

## TDD Gate Compliance

This is a `tdd="true"` task within an `execute`-type plan (not a plan-level `tdd` gate), so the strict RED→GREEN→REFACTOR commit triple does not apply. However, the RED→GREEN gate behavior is observed:

1. **RED verified.** Pre-patch, `pytest tests/test_media_keys_smtc.py::test_thumbnail_from_in_memory_stream -x` failed with the captured warning `'MagicMock' object can't be awaited` and a downstream AssertionError on `create_from_stream.called`. The base ref `ca0dff5` reproduces this.
2. **GREEN verified.** Post-patch, the same command exits 0 (1 passed in 0.24s).
3. **No REFACTOR pass needed.** The patch is already minimal — 4 added lines, no cleanup opportunity.

Since the production code under test is `_await_store` in `smtc.py` and that code is already shipped + UAT-validated (Phase 43.1), the appropriate commit shape is a single `test:` commit covering the test-only change. This matches the plan's explicit guidance ("test-only patch; no runtime change").

## User Setup Required

None — pure test-side patch, no external services or environment configuration.

## Plan 57-05 UAT Note

Per PLAN.md's `<output>` section: **WIN-04 closure can be verified solely by running the full test suite on the merge candidate branch** — no Win11 VM step required. WIN-04 is the only sub-requirement of Phase 57 that can be fully validated on Linux CI. The remaining Phase 57 work (WIN-03 audio glitch + volume slider) still requires the Win11 VM UAT path.

## Next Phase Readiness

- ROADMAP Phase 57 SC #3 is satisfied (`test_thumbnail_from_in_memory_stream` passes).
- ROADMAP Phase 57 SC #4 is satisfied modulo the 10 pre-existing unrelated failures called out above.
- Other Phase 57 plans (57-02 diagnostic log, 57-03 / 57-04 WIN-03 fix shape, 57-05 UAT) are independent of this plan per the wave layout — Plan 01 is wave 1 with no dependencies; subsequent plans depend on the WIN-03 diagnostic readbacks, not on WIN-04.

## Self-Check: PASSED

- [x] `tests/test_media_keys_smtc.py` exists (modified) — verified via `git diff`.
- [x] Commit `c1c783c` exists in this worktree branch's git log — verified via `git log --oneline -1`.
- [x] D-08 grep gate: `grep -nq "from unittest.mock import AsyncMock, MagicMock" tests/test_media_keys_smtc.py` returns 0.
- [x] D-09 grep gate: `grep -nq "DataWriter.return_value.store_async = AsyncMock" tests/test_media_keys_smtc.py` returns 0.
- [x] D-10 invariant: `git diff musicstreamer/media_keys/smtc.py` is empty.
- [x] PLAN.md verify command's spirit holds: `pytest tests/test_media_keys_smtc.py::test_thumbnail_from_in_memory_stream -x` exits 0; `pytest tests/test_media_keys_smtc.py -x` exits 0 (24/24); full `pytest` run produces no new failures vs. base.

---
*Phase: 57-windows-audio-glitch-test-fix*
*Plan: 01*
*Completed: 2026-05-02*
