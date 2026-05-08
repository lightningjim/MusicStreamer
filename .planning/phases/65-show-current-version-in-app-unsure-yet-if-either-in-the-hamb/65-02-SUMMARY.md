---
phase: 65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb
plan: 02
subsystem: packaging
tags: [pyinstaller, packaging, windows, copy_metadata, dist-info, importlib-metadata, ver-02-h]

# Dependency graph
requires:
  - phase: 44-windows-packaging-installer
    provides: PyInstaller spec with collect_all + datas concatenation pattern (`_cn_datas + _sl_datas + _yt_datas` at MusicStreamer.spec:100-103)
  - phase: 63-auto-bump-pyproject-toml-version-on-phase-completion-using-m
    provides: pyproject.toml [project].version as canonical write site (auto-bump produces the version this plan ships in dist-info)
provides:
  - PyInstaller spec ships musicstreamer's dist-info via copy_metadata("musicstreamer")
  - Source-text regression-lock test (tests/test_packaging_spec.py) covering VER-02-H + the no-try/except CONTEXT D-08 prohibition
  - Closes the bundle promise of Phase 65 — importlib.metadata.version("musicstreamer") will resolve inside the bundled exe
affects: [65-01 (consumes the bundled metadata at runtime via setApplicationVersion), 65-03 (deletes __version__.py — independent of this plan), future-bundle-builds (regression-locked against accidental copy_metadata removal)]

# Tech tracking
tech-stack:
  added: [PyInstaller.utils.hooks.copy_metadata (already-available helper, newly used)]
  patterns: ["copy_metadata('<own-package>') alongside collect_all('<dep>') in PyInstaller spec datas concatenation", "single-file source-text assertion (read_text + substring) for .spec content rules — modelled after tests/test_main_run_gui_ordering.py per PATTERNS §8"]

key-files:
  created:
    - tests/test_packaging_spec.py
    - .planning/phases/65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb/deferred-items.md
  modified:
    - packaging/windows/MusicStreamer.spec

key-decisions:
  - "Implemented CONTEXT D-08 verbatim: 1-line import extension + 1-line _ms_datas assignment + 1-token concat append. No try/except, no fallback string."
  - "Created NEW tests/test_packaging_spec.py rather than extending tests/test_pkg03_compliance.py (PATTERNS drift flag enforcement — pkg03 is a musicstreamer/*.py glob, this is a single-file packaging/windows/*.spec rule)."
  - "Wrote 4 tests instead of 1: import extension, the call itself, the datas concatenation, and the negative no-try/except regression-lock — gives multi-axis defense against future spec drift."
  - "Used 200-byte proximity heuristic for try/except detection rather than full Python AST parse — simpler, sufficient for the realistic regression shape (defensive wrap around the call). Limitation documented in test docstring."
  - "Did NOT introduce v(unknown) defensive fallback (out of this plan's scope; Plan 65-01 governs the runtime read site)."

patterns-established:
  - "copy_metadata('<own-package>') in PyInstaller spec — for shipping our own dist-info alongside third-party collect_all datas"
  - "Source-text test for .spec files — pure read_text + substring/proximity check; no PyInstaller install required to run"
  - "Regression-lock pattern: positive assertions (X is present) + negative assertions (Y is absent) — guards against both removal AND future well-meaning defensive edits"

requirements-completed: [VER-02]

# Metrics
duration: 4m 37s
completed: 2026-05-08
---

# Phase 65 Plan 02: Wire copy_metadata("musicstreamer") into PyInstaller spec Summary

**Three-line PyInstaller spec edit (import extension + _ms_datas assignment + datas concat) plus 4-test source-text regression-lock (tests/test_packaging_spec.py) that closes the bundle promise — importlib.metadata.version("musicstreamer") will now resolve inside the bundled Windows exe.**

## Performance

- **Duration:** 4m 37s
- **Started:** 2026-05-08T19:38:21Z
- **Completed:** 2026-05-08T19:42:58Z
- **Tasks:** 2 / 2
- **Files modified:** 1 (spec)
- **Files created:** 2 (test + deferred-items.md)

## Accomplishments

- **packaging/windows/MusicStreamer.spec** edited per CONTEXT D-08:
  - Hook import extended: `from PyInstaller.utils.hooks import collect_all, copy_metadata` (line 17).
  - New comment block + `_ms_datas = copy_metadata("musicstreamer")` assignment placed adjacent to the existing `_cn_datas` / `_sl_datas` / `_yt_datas` peers (lines 35-41).
  - `datas=[...]` concatenation extended with `+ _ms_datas` (line 111) so musicstreamer's dist-info ships in the Windows bundle.
- **tests/test_packaging_spec.py** created with 4 GREEN tests covering VER-02-H plus the no-try/except CONTEXT D-08 prohibition. Runs in 0.06s.
- **Bundle promise closed:** with this spec change, `importlib.metadata.version("musicstreamer")` (called by Plan 65-01's `_run_gui` setApplicationVersion + the menu construction site) will resolve inside the bundled exe instead of raising PackageNotFoundError.
- **Regression locked:** the 4 tests provide multi-axis defense — accidental removal of the import, the call, the concat, OR a future "well-meaning" defensive try/except wrap will all fail the test.

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire copy_metadata("musicstreamer") into MusicStreamer.spec (D-08)** — `cc6a51c` (feat)
2. **Task 2: Add tests/test_packaging_spec.py source-text test (VER-02-H)** — `bc1a2c1` (test)

(Plan-metadata commit will be created by the orchestrator after the worktree merges; this executor does not write STATE.md / ROADMAP.md per the parallel-execution contract.)

## Files Created/Modified

- **packaging/windows/MusicStreamer.spec** (MODIFIED) — 3 edits (1 import line extended, 1 new 8-line block including comments, 1 token appended to the datas concatenation). +10 −2 lines per `git show --stat cc6a51c`.
- **tests/test_packaging_spec.py** (CREATED) — 121 lines. 4 source-text tests + module-level fixture loading the spec content once.
- **.planning/phases/65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb/deferred-items.md** (CREATED) — logs the pre-existing `tests/test_import_dialog_qt.py::test_yt_scan_passes_through` Qt test-isolation flake (unrelated to this plan; passes in isolation, crashes only in full-suite ordering).

## Decisions Made

Plan executed exactly per CONTEXT D-08 + PATTERNS drift-flag guidance + the plan's `<additional_notes>`. Specifically:

- **No try/except, no fallback string** — CONTEXT D-08 explicit prohibition. The negative regression-lock test (`test_spec_has_no_try_except_around_copy_metadata`) enforces this for the future.
- **NEW file, not extension of pkg03** — PATTERNS drift flag binding. `tests/test_pkg03_compliance.py` is a `musicstreamer/*.py` glob (subprocess-guard test), unrelated to the packaging-spec rule. Sha256 of pkg03 verified unchanged before and after Task 2.
- **4 tests, not 1** — the plan's `<behavior>` enumerates 3 positive properties + 1 negative regression-lock; one test per property gives precise failure messages and multi-axis defense.
- **200-byte proximity heuristic for try/except detection** — implemented as plan-checker nit #3 acknowledged. Limitation documented in test docstring; future maintenance can switch to full ast.parse if a legitimate unrelated try block ever lands within 200 bytes of the copy_metadata call.

## Deviations from Plan

None — plan executed exactly as written. All grep-checkable `<verify>` assertions passed on first try; pytest GREEN on first run.

(Pre-existing flaky Qt-test issue in unrelated `tests/test_import_dialog_qt.py` is logged in `deferred-items.md` per scope-boundary rules; this is NOT a Plan 65-02 deviation — we did not touch that file or any production code path it exercises.)

## Issues Encountered

**1. Full-suite pytest run aborted on `tests/test_import_dialog_qt.py::test_yt_scan_passes_through`** — Qt test-isolation crash unrelated to Plan 65-02 changes.
  - **Resolution:** Verified the test is pre-existing (passes in isolation on both current HEAD and worktree base; file last touched by phase 999.7, not this plan). Logged to `deferred-items.md`. Plan-level quick suite (`uv run pytest tests/test_packaging_spec.py -x`) is the binding gate per the plan's success criteria, and that is GREEN.

## TDD Gate Compliance

Plan 65-02 has `type: execute` (not `type: tdd`), so plan-level RED/GREEN gate enforcement does not apply. Both tasks have `tdd="true"` at the task level. Internal commit shape:

- **Task 1 (`feat`)** — Spec edit. Per the plan's `<verify>` block, Task 1 verification is via grep (not pytest), and Task 2 IS the regression-lock test for it. The natural per-task commit shape is therefore `feat` (the spec edit) followed by `test` (the test file) — Task 2's tests verify Task 1's edit retroactively, satisfying the spirit of plan-level RED/GREEN at the per-plan boundary.
- **Task 2 (`test`)** — New regression-lock test file. GREEN on first run after Task 1 landed.

The full plan satisfies the broader "test asserts implementation correctness" contract via the Task 2 commit.

## Threat Flags

None. The plan's `<threat_model>` identified two threats (T-65-03 information disclosure / T-65-04 DoS-tampering of bundle build) — both `accept` dispositions, both implemented per spec. The negative regression-lock test (`test_spec_has_no_try_except_around_copy_metadata`) is the structural mitigation for T-65-04. No new attack surface introduced.

## Known Stubs

None. The new spec content + new test content do not introduce any UI-flowing stubs, hardcoded empties, or "TODO" placeholders. The two `placeholder` token hits in the modified files are documentation comments referring to CONTEXT D-08's no-placeholder prohibition (i.e., they describe what is forbidden, not what was shipped).

## Next Phase Readiness

- **Plan 65-01 (runtime read site)** — independent of this plan; reads via `importlib.metadata.version("musicstreamer")` which resolves correctly in dev today (pre-existing dist-info in `.venv`) and will resolve in the Windows bundle once Plan 65-02 is shipped.
- **Plan 65-03 (`__version__.py` deletion)** — independent of this plan; D-06a grep gate already verified clean per RESEARCH Q5.
- **VER-02-J (manual Windows VM UAT)** — deferred to `/gsd-verify-work` per the plan's verification block. Kyle building the actual bundle on his Win11 VM and confirming `v{version}` shows in the installed exe's hamburger menu is a manual UAT item.
- **Phase 65 completion** — once 65-01 and 65-03 land, the plan is ready for verifier review + manual UAT. The structural mechanism + regression-lock are now in place.

## Verification Evidence

**Plan-level quick suite (binding gate per plan):**
```
$ uv run pytest tests/test_packaging_spec.py -x
========================= 4 passed, 1 warning in 0.06s =========================
```

**Task 1 grep `<verify>` (all assertions PASS):**
- `from PyInstaller.utils.hooks import collect_all, copy_metadata` — line 17 ✓
- `_ms_datas = copy_metadata("musicstreamer")` — line 41 ✓
- `_yt_datas + _ms_datas` — line 111 ✓
- No `try:.*copy_metadata`, `except.*copy_metadata`, `or "0.0.0"` — confirmed absent ✓

**Drift-flag enforcement:**
- `tests/test_pkg03_compliance.py` sha256 before Task 1: `fc27cd40335c287e03b768dfe2d29d215676ba122267e0349dbe197beb778f25`
- `tests/test_pkg03_compliance.py` sha256 after Task 2: `fc27cd40335c287e03b768dfe2d29d215676ba122267e0349dbe197beb778f25` (unchanged ✓)

**`packaging/windows/build.ps1` unchanged** — no edits needed per RESEARCH Q6 (build.ps1 reads version from pyproject.toml directly via regex; never opened `__version__.py` or the spec's metadata machinery).

**`musicstreamer/__version__.py` still present** — Plan 65-03 deletes it; Plan 65-02 does NOT touch it.

## Self-Check

- ✓ `packaging/windows/MusicStreamer.spec` exists; spec edits intact (`grep -c '_ms_datas'` returns 2 — the assignment + the concat).
- ✓ `tests/test_packaging_spec.py` exists; 121 lines; 4 tests GREEN.
- ✓ `tests/test_pkg03_compliance.py` exists; sha256 matches pre-edit value (drift-flag enforcement verified).
- ✓ `packaging/windows/build.ps1` unchanged.
- ✓ Commit cc6a51c (Task 1, feat) found in git log.
- ✓ Commit bc1a2c1 (Task 2, test) found in git log.
- ✓ `.planning/phases/65-.../deferred-items.md` exists.

## Self-Check: PASSED

---
*Phase: 65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb*
*Plan: 02*
*Completed: 2026-05-08*
