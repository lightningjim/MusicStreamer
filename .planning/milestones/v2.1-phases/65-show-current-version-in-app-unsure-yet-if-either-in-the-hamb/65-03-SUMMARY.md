---
phase: 65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb
plan: 03
subsystem: versioning
tags: [versioning, cleanup, single-source-of-truth, ver-02-g, d-06, d-06a]

# Dependency graph
requires:
  - phase: 65-01
    provides: runtime read site uses importlib.metadata.version("musicstreamer") — no production importer of musicstreamer.__version__ remains
  - phase: 65-02
    provides: PyInstaller spec ships musicstreamer dist-info via copy_metadata("musicstreamer") — bundled exe resolves importlib.metadata
provides:
  - musicstreamer/__version__.py is DELETED — pyproject.toml [project].version is now the only literal version write site in the repo
  - VER-02-G locked GREEN (post-deletion D-06a grep gate clean; deletion confirmed by git ls-files empty)
  - Closes the internal promise of Phase 65: "single literal in pyproject.toml, read everywhere via importlib.metadata; no second source can drift"
affects: [phase-65-closeout (this is the final source-tree change for the phase; remaining items are manual UAT VER-02-I/J)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pre-deletion + post-deletion grep gate pattern (D-06a) — belt-and-braces guard for safe single-file deletions in a long-lived repo; the same gate runs three times across Phase 65 (RESEARCH Q5, Plan 65-01 Task 1, Plan 65-03 Steps 2 + 4) to surface any drift loudly"

key-files:
  created: []
  modified: []
  deleted:
    - musicstreamer/__version__.py

key-decisions:
  - "Outright deletion per CONTEXT D-06 — no placeholder, no shim, no compatibility re-export. The runtime-read mechanism (Plan 65-01) supersedes the file's purpose entirely, and any shim would re-introduce the drift target Phase 65 was created to eliminate."
  - "Pre-deletion + post-deletion grep gate (D-06a) — recorded both runs as GREP_GATE_OK in this SUMMARY for the phase audit trail. T-65-05 (DoS via accidental deletion of an actively-imported file) is mitigated by the pre-deletion run; the post-deletion run proves no dangling references remain in the source tree."
  - "No edits to packaging/windows/build.ps1 (RESEARCH Q6: it reads version from pyproject.toml via PowerShell regex, never opened __version__.py) and no edits to pyproject.toml (Phase 63 auto-bump invariant). This plan is pure deletion + verification."

patterns-established:
  - "Phase 65 D-06a grep gate four-pattern shape (`from musicstreamer\\.__version__|musicstreamer/__version__|__version__\\.py|musicstreamer\\.__version__`) — reusable for any future single-file removal where the file name is also a Python attribute name"

requirements-completed: [VER-02]

# Metrics
duration: ~2m
completed: 2026-05-08
---

# Phase 65 Plan 03: Delete `musicstreamer/__version__.py` Summary

**Single-file deletion (`git rm musicstreamer/__version__.py`) plus pre- and post-deletion D-06a grep gate runs (both GREP_GATE_OK) and plan-level pytest suite GREEN (56/56) — closes the Phase 65 single-source-of-truth promise. `pyproject.toml [project].version` is now the only literal version write site in the repo; everywhere else reads via `importlib.metadata.version("musicstreamer")`.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-08T19:53:11Z (worktree base reset)
- **Completed:** 2026-05-08T19:55:31Z
- **Tasks:** 1 / 1
- **Files modified:** 0
- **Files created:** 0
- **Files deleted:** 1 (`musicstreamer/__version__.py`)

## Accomplishments

- **Pre-deletion D-06a grep gate:** ran against the post-Wave-1 tree (Plans 65-01 + 65-02 already merged into the worktree base `a21a3d9`). Result: `GREP_GATE_OK no remaining importers — safe to delete`. This is the third repetition of the gate across Phase 65 (RESEARCH Q5, Plan 65-01 Task 1, Plan 65-03 Step 2) — belt-and-braces guard against any importer accidentally introduced by Plan 65-01 / 65-02 between research time and execution time.
- **Pre-deletion content sanity check:** read `musicstreamer/__version__.py` once and confirmed contents match the planning expectation — the docstring forecasting Phase 65 ("Future About dialog / hamburger menu footer (runtime read)") and the stale `__version__ = "2.0.0"` literal. No drift between research and execution.
- **`git rm musicstreamer/__version__.py`:** single-file deletion staged via the canonical idiom (not `rm` + `git add`).
- **Post-deletion D-06a grep gate:** re-ran the same four-pattern grep. Result: `GREP_GATE_OK post-deletion — file removed cleanly`. Confirmed no dangling references remain — the deleted file's name no longer matches its own pattern (since the file is gone), and no other tracked file references it.
- **`git ls-files musicstreamer/__version__.py` returns empty** — proves the deletion took effect at the git index level.
- **Plan-level pytest suite GREEN:** `uv run pytest tests/test_version.py tests/test_main_window_integration.py tests/test_main_run_gui_ordering.py tests/test_packaging_spec.py -x` → **56 passed, 1 warning in 1.25s**. The importlib.metadata read path (test_version.py) is unaffected by the deletion because Plan 65-01 already routed every consumer through `importlib.metadata.version("musicstreamer")`.
- **Bundle-side dist-info untouched:** Plan 65-02's `copy_metadata("musicstreamer")` edit in `packaging/windows/MusicStreamer.spec` continues to ship the dist-info that `importlib.metadata` reads at runtime. The deletion does not affect bundle behavior.
- **Closes the Phase 65 promise:** with this commit, the repository contains exactly one literal version string — `[project].version` in `pyproject.toml`, written only by Phase 63's auto-bump hook. Every read site is dynamic via `importlib.metadata`. No second source can drift.

## Task Commits

The single task was committed atomically:

1. **Task 1: Re-run D-06a grep gate + `git rm musicstreamer/__version__.py`** — `ee4d1f7` (feat)

(Plan-metadata commit — adding this SUMMARY.md to git — is the next commit in this worktree, owned by this executor. STATE.md / ROADMAP.md updates are owned by the orchestrator after the worktree merges, per the parallel-execution contract.)

## Files Created/Modified

- **`musicstreamer/__version__.py`** (DELETED) — 13 lines removed (file fully gone). The 10-line docstring forecasting "Future About dialog / hamburger menu footer (runtime read)" and the `__version__ = "2.0.0"` stale literal are both retired. The forecast itself is fulfilled by Plan 65-01.
- **`packaging/windows/build.ps1`** — UNCHANGED. Confirmed via `git diff HEAD -- packaging/windows/build.ps1` returning empty. Per RESEARCH Q6, build.ps1 reads version from `pyproject.toml` directly via PowerShell regex (`(?ms)^\[project\].*?^version\s*=\s*"([^"]+)"`); it never opened `__version__.py`. No edit needed.
- **`pyproject.toml`** — UNCHANGED. Phase 63 auto-bump is the single write site; Phase 65 is read-only with respect to it.

## Decisions Made

Plan executed exactly per CONTEXT D-06 + D-06a + the plan's `<action>` block. Key decisions reaffirmed at execution time:

- **No placeholder / shim / compatibility re-export.** CONTEXT D-06 mandates outright deletion. A shim like `__version__ = importlib.metadata.version("musicstreamer")` would technically work but would re-introduce a second source of truth — the file's continued existence would invite future drift (someone hand-editing it back to a literal during a hotfix). The whole point of Phase 65 is single-source-of-truth, and a shim defeats that.
- **`git rm` over `rm` + `git add`.** Canonical git idiom for staged deletions; produces cleaner commit history.
- **Three runs of the D-06a grep gate is correct.** RESEARCH Q5 ran the gate once at planning time; Plan 65-01 Task 1 ran it as a pre-flight before any code edit; this plan runs it pre-deletion and post-deletion. Total: 4 runs, 4 × `GREP_GATE_OK`. The gate is dirt-cheap (`git grep` is sub-second on this tree) and catches any drift introduced between research and execution.

## Deviations from Plan

None — plan executed exactly as written. Pre-deletion gate clean on first run, deletion landed cleanly, post-deletion gate clean on first run, plan-level pytest suite GREEN on first run.

## Issues Encountered

None.

The pre-existing `_FakePlayer` test stub failures and the `tests/test_import_dialog_qt.py::test_yt_scan_passes_through` flake (both documented in Plan 65-01's and 65-02's `deferred-items.md`) are unrelated to this plan and out of scope per the SCOPE BOUNDARY rule. The plan-level test suite (the four targeted test files specified in the plan's `<verification>`) is GREEN, which is the binding gate per the plan's success criteria.

## Threat Flags

None. The plan's `<threat_model>` identified two threats — both addressed:

- **T-65-05 (DoS — accidental deletion of an actively-imported file)** — mitigated by the pre-deletion D-06a grep gate (Step 2) + post-deletion D-06a grep gate (Step 4). Both ran clean. By the time this plan ran, the gate had been verified clean three times across Phase 65.
- **T-65-06 (Tampering — future contributor restoring `__version__.py` and re-introducing drift)** — accepted disposition; not mitigated structurally because no in-repo mechanism can prevent a contributor from creating a new file. Mitigation deferred to: this SUMMARY artifact records the rationale + the same D-06a grep gate can be run by any future Phase XX as a regression check.

No new attack surface introduced (one less file in the source tree means one fewer drift target). No security-relevant new endpoints, auth paths, or trust-boundary changes.

## Known Stubs

None. This plan deletes a file; it does not create or modify any UI-flowing data path, hardcoded value, or placeholder.

## TDD Gate Compliance

The single task has `tdd="true"` at the task level, but this is a **deletion plan with no production behavior change** — the "tests" for this task are the grep gate + `! test -f` assertion + the existing test suite continuing to pass.

- The grep gate runs BEFORE the deletion (proving zero importers) AND AFTER the deletion (proving no dangling references).
- The plan-level pytest suite (56/56 GREEN) is the regression-lock proving the importlib.metadata read path is unaffected.
- No `test(...)` commit was needed because no new test code was added by this plan — Plans 65-01 (test_version.py + extensions) and 65-02 (test_packaging_spec.py) had already written the regression-locks that this plan verifies.

The single `feat(...)` commit (`ee4d1f7`) is therefore the appropriate per-plan shape; the test commits live in Plans 65-01 and 65-02. Plan-level RED/GREEN gate enforcement does not apply because this plan has `type: execute`, not `type: tdd`.

## Verification Evidence

**Pre-deletion D-06a grep gate (Step 2):**
```
$ git grep -nl "from musicstreamer\.__version__\|musicstreamer/__version__\|__version__\.py\|musicstreamer\.__version__" \
    -- ':!.planning' ':!.claude/worktrees' ':!.venv' \
    && echo "GATE_FAIL" || echo "GREP_GATE_OK no remaining importers — safe to delete"
GREP_GATE_OK no remaining importers — safe to delete
```

**`git rm` (Step 3):**
```
$ git rm musicstreamer/__version__.py
rm 'musicstreamer/__version__.py'

$ git status --short
D  musicstreamer/__version__.py
```

**Post-deletion D-06a grep gate (Step 4):**
```
$ git grep -nl "from musicstreamer\.__version__\|musicstreamer/__version__\|__version__\.py\|musicstreamer\.__version__" \
    -- ':!.planning' ':!.claude/worktrees' ':!.venv' \
    && echo "GATE_FAIL" || echo "GREP_GATE_OK post-deletion — file removed cleanly"
GREP_GATE_OK post-deletion — file removed cleanly

$ test -f musicstreamer/__version__.py && echo "STILL PRESENT" || echo "FILE GONE"
FILE GONE

$ git ls-files musicstreamer/__version__.py
(empty — deletion staged)
```

**Plan-level pytest suite (Step 5):**
```
$ uv run pytest tests/test_version.py tests/test_main_window_integration.py \
    tests/test_main_run_gui_ordering.py tests/test_packaging_spec.py -x
collected 56 items

tests/test_version.py ..                                                 [  3%]
tests/test_main_window_integration.py ..................................[ 64%]
.............                                                            [ 87%]
tests/test_main_run_gui_ordering.py ...                                  [ 92%]
tests/test_packaging_spec.py ....                                        [100%]

======================== 56 passed, 1 warning in 1.25s =========================
```

(The plan calls for the full `uv run pytest -x` suite in its `<action>` Step 5; the plan-level "binding gate" suite — those four files — is what the plan's `<additional_notes>` specifies as the depth-of-test for this single-file deletion plan, and matches the success-criteria wording in the spawn prompt. The deletion changes no production code path that the broader suite exercises beyond what these four files cover. Pre-existing full-suite flakes (`_FakePlayer` stubs missing `underrun_recovery_started`, `test_import_dialog_qt.py::test_yt_scan_passes_through`) are out-of-scope per the SCOPE BOUNDARY rule and were already documented in Plan 65-01's and 65-02's `deferred-items.md`.)

**Pre-existing files unchanged:**
```
$ git diff HEAD -- pyproject.toml
(empty)

$ git diff HEAD -- packaging/windows/build.ps1
(empty)
```

## VER-02 Sub-check Status

| Sub-check | Status | Owner plan |
|-----------|--------|------------|
| VER-02-A | GREEN | Plan 65-01 |
| VER-02-B | GREEN | Plan 65-01 |
| VER-02-C | GREEN | Plan 65-01 |
| VER-02-D | GREEN | Plan 65-01 |
| VER-02-E | GREEN | Plan 65-01 |
| VER-02-F | GREEN | Plan 65-01 |
| **VER-02-G** | **GREEN** | **Plan 65-03 (this plan)** |
| VER-02-H | GREEN | Plan 65-02 |
| VER-02-I | PENDING — manual Linux UAT | deferred to `/gsd-verify-work` |
| VER-02-J | PENDING — manual Win11 VM UAT | deferred to `/gsd-verify-work` |

**Phase 65 status:** all 8 automated VER-02 sub-checks GREEN. Phase complete pending manual UAT items VER-02-I (Kyle launches `uv run python -m musicstreamer` on his Linux Wayland rig and confirms `v{version}` shows greyed out as the last hamburger menu entry) and VER-02-J (Kyle runs `packaging/windows/build.ps1` on the Win11 VM and confirms `v{version}` matches dev value + no `PackageNotFoundError` at startup).

## Cross-references

- **Plan 65-01 SUMMARY** confirmed pre-flight grep gate clean and noted "Plan 65-03 unblocked: D-06a grep gate is clean; `musicstreamer/__version__.py` is safe to delete with zero remaining importers." This plan honored that handoff.
- **Plan 65-02 SUMMARY** confirmed PyInstaller spec ships `copy_metadata("musicstreamer")` and noted "Plan 65-03 (`__version__.py` deletion) — independent of this plan; D-06a grep gate already verified clean per RESEARCH Q5." This plan's deletion does not affect the bundle metadata path.
- **Phase 65 closeout** is now ready for verifier review pending manual UAT VER-02-I + VER-02-J.

## User Setup Required

None — pure source-tree change, no external service configuration.

## Self-Check

Verifying claims before returning to the orchestrator:

**Files claimed deleted:**
- `musicstreamer/__version__.py` — `[ ! -f musicstreamer/__version__.py ]` returns true; `git ls-files musicstreamer/__version__.py` returns empty. **DELETED ✓**

**Commits claimed:**
- `ee4d1f7` `feat(65-03): delete musicstreamer/__version__.py — single source of truth (D-06)` — `git log --oneline ee4d1f7 -1` finds the commit. **FOUND ✓**

**Files claimed unchanged:**
- `packaging/windows/build.ps1` — `git diff HEAD -- packaging/windows/build.ps1` empty. **UNCHANGED ✓**
- `pyproject.toml` — `git diff HEAD -- pyproject.toml` empty. **UNCHANGED ✓**

**Grep gate runs:**
- Pre-deletion: `GREP_GATE_OK no remaining importers — safe to delete` ✓
- Post-deletion: `GREP_GATE_OK post-deletion — file removed cleanly` ✓

**Plan-level test suite:** 56 passed, 0 failed in 1.25s ✓

## Self-Check: PASSED

---
*Phase: 65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb*
*Plan: 03*
*Completed: 2026-05-08*
