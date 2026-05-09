---
phase: 65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb
plan: 05
subsystem: packaging-windows-build-script
tags: [packaging, windows, build-ps1, pre-bundle-clean, conda-env, ver-02-j, gap-closure, drift-guard, plan-65-05]
requires:
  - "Plan 65-04's step 3c rationale block at packaging/windows/build.ps1 lines 131-150 (pre-existing)"
  - "Plan 65-04's drift-guard test scaffolding at tests/test_packaging_spec.py::test_build_ps1_pre_bundle_clean_present (pre-existing)"
  - ".claude/skills/spike-findings-musicstreamer/references/windows-gstreamer-bundling.md (conda-forge spike env recipe — `uv` is NOT in the recipe)"
provides:
  - "build.ps1 step 3c that runs end-to-end on the Win11 spike conda env (no `uv` dependency)"
  - "Drift-guard locking the `python -m pip` literal as the post-Plan-65-05 authoritative substring in step 3c"
  - "NEW: negative drift-guard catching the partial-revert failure mode (where both `uv pip` and `python -m pip` end up on executable lines simultaneously, which on Win11 is functionally equivalent to no-fix because the `uv pip` line crashes the script first)"
affects:
  - "Win11 VM build pipeline (unblocks VER-02-J retest gate)"
  - "Linux dev pytest suite for tests/test_packaging_spec.py (still 6 passed, unchanged warning posture)"
  - "VER-02-J validation_id (REUSED, not new — same UAT prompt re-runs after this plan ships)"
tech-stack:
  added: []
  patterns:
    - "negative drift-guard via line-split + comment-strip + 'not in' substring check (catches partial-revert without false-positives from rationale comment text)"
key-files:
  created: []
  modified:
    - "packaging/windows/build.ps1 (step 3c only: 5 line modifications + 6-line breadcrumb comment block insert; total +11 -5)"
    - "tests/test_packaging_spec.py (module docstring +6 lines; test_build_ps1_pre_bundle_clean_present docstring + uninstall assertion + reinstall acceptance set + new negative drift-guard; total +77 -11)"
decisions:
  - "Use `python -m pip` not `pip` (bare): conda env always provides `python` on PATH; bare `pip` could resolve to a base-env or system pip with surprising sys.path. `python -m pip` is the established project precedent at step 3 (line 103) — same idiom."
  - "Keep the legacy `uv pip install -e` and `uv sync --reinstall-package musicstreamer` shapes accepted in the reinstall acceptance set: forward-compat for a hypothetical future maintainer reintroducing a uv-managed env on Windows. Cost is one extra `or` clause; benefit is the test does not over-constrain."
  - "Make the negative drift-guard check EXECUTABLE lines only (strip lines whose first non-whitespace char is `#`), not the whole source: the rationale comment block legitimately discusses the pre-Plan-65-05 history with `uv pip ...` references, so a whole-source `not in` check would false-positive against the very comment that documents the swap."
  - "Strict ASCII in the new breadcrumb comment block: per spike-findings landmine, PS 5.1 parses .ps1 files as cp1252 without a BOM; multi-byte chars (em-dash, smart quotes) corrupt the parse. The breadcrumb uses straight quotes and hyphens only."
  - "Sanity-check the negative drift-guard by injecting an `uv pip uninstall musicstreamer` line into build.ps1's first non-comment line and confirming pytest reports the assertion fires RED — proves the guard is reachable, not trivially-passing."
metrics:
  duration: "~6 minutes (Linux dev side; Win11 VM retest is a separate manual UAT step)"
  completed: "2026-05-09"
  tasks_completed: 2
  files_modified: 2
---

# Phase 65 Plan 05: Replace `uv pip` with `python -m pip` in build.ps1 step 3c (VER-02-J retest gate fix) Summary

`build.ps1` step 3c "PRE-BUNDLE CLEAN" now uses `python -m pip uninstall musicstreamer -y` + `python -m pip install -e ..\..` instead of `uv pip ...`, so it runs end-to-end on the Win11 conda-forge spike env where `uv` is not provisioned; the drift-guard test in `tests/test_packaging_spec.py` was updated in lockstep with positive `python -m pip` substring locks plus a NEW negative drift-guard that catches partial-revert.

## What Shipped

### `packaging/windows/build.ps1` step 3c rewrite (commit e224633)

Edits confined to the existing step 3c block (lines 131-168 after edit; was 131-162 before). Step ordering, exit codes, failure-branch shape, and WR-01 invariants preserved.

| Change | Line (post-edit) | Was | Now |
|---|---|---|---|
| Banner Write-Host | 157 | `=== PRE-BUNDLE CLEAN: uv pip uninstall + reinstall musicstreamer ===` | `=== PRE-BUNDLE CLEAN: python -m pip uninstall + reinstall musicstreamer ===` |
| Uninstall command | 158 | `Invoke-Native { uv pip uninstall musicstreamer -y 2>&1 \| Out-Host }` | `Invoke-Native { python -m pip uninstall musicstreamer -y 2>&1 \| Out-Host }` |
| Uninstall-comment block | 159 | references `uv pip uninstall` | references `python -m pip uninstall` |
| Reinstall command | 163 | `Invoke-Native { uv pip install -e ..\.. 2>&1 \| Out-Host }` | `Invoke-Native { python -m pip install -e ..\.. 2>&1 \| Out-Host }` |
| BUILD_FAIL hint | 165 | `hint='uv pip install -e ..\..\\ failed; check uv install + ...'` | `hint='python -m pip install -e ..\..\\ failed; check pip install + ...'` |
| DO-NOT-REMOVE breadcrumb | 151-156 (NEW) | (absent) | 6-line ASCII-only block citing spike-findings-musicstreamer for the pip-not-uv choice |

**Preserved verbatim** (verified by grep): `BUILD_FAIL reason=pre_bundle_clean_failed` CI grep token, `PRE-BUNDLE CLEAN OK` success-log marker, `exit 8` failure code, `Write-Host` (NOT `Write-Error`) on the failure path (WR-01), step ordering 3b → 3c → 4 → 4a → 5 → 6.

### `tests/test_packaging_spec.py` drift-guard updates (commit 03194cf)

Confined to the module docstring + `test_build_ps1_pre_bundle_clean_present` only.

| Change | Where |
|---|---|
| Module docstring (line 17-26) | One-paragraph append: notes Plan 65-05's amendment to step-3c drift-guard, references the 2026-05-09 retest discovery |
| Test docstring | New paragraph at end: explains the `uv pip` → `python -m pip` swap rationale and that the legacy `uv` shapes stay accepted for forward-compat |
| Uninstall assertion | `assert "uv pip uninstall musicstreamer"` → `assert "python -m pip uninstall musicstreamer"` (with explanatory comment block referencing the negative drift-guard at function bottom) |
| Reinstall acceptance set | Extended from 2 → 3 accepted shapes: `python -m pip install -e` (Plan 65-05 primary) OR `uv pip install -e` (Plan 65-04 legacy) OR `uv sync --reinstall-package musicstreamer` (alt legacy) |
| **NEW negative drift-guard** | At function end: splits build.ps1 by line, strips comment-only lines, asserts `uv pip uninstall musicstreamer` and `uv pip install -e` are NOT in what remains. Catches partial-revert (both forms present simultaneously, which on Win11 is functionally equivalent to no-fix). |

**Preserved byte-identical** (sha256 verified): 4 spec_source tests (`test_spec_imports_copy_metadata`, `test_spec_includes_copy_metadata_for_musicstreamer`, `test_spec_concatenates_ms_datas_into_datas_list`, `test_spec_has_no_try_except_around_copy_metadata`), `test_build_ps1_post_bundle_dist_info_assertion_present`, `_SPEC` / `_BUILD_PS1` / `spec_source` / `build_ps1_source` fixtures.

## Untouched-File Invariants (sha256 evidence)

5 files MUST be byte-identical pre vs post-plan. Verified:

```
b2aada6a9790e762a497b40819702a2f0821abe79d46aa02087dfe521ecace8a  packaging/windows/MusicStreamer.spec
c5b3c0f11a76a5ce90167e1320f50840180b7289cb92aaff876867bc4697149d  musicstreamer/__main__.py
66108fbd908600d647a52bf162a8b95f0428565f4910597c1a4d1cf0a6e10056  musicstreamer/ui_qt/main_window.py
fc27cd40335c287e03b768dfe2d29d215676ba122267e0349dbe197beb778f25  tests/test_pkg03_compliance.py
1c08f5506c80bbca7f1414b745999d1e3f091721d1432526d6ae60c4f0b557ce  pyproject.toml
```

Pre and post sha256 lists `diff` cleanly (no differences).

## Test Counts (pre vs post)

| Suite | Pre | Post |
|---|---|---|
| `tests/test_packaging_spec.py` | 6 passed, 1 warning | 6 passed, 1 warning |
| `tests/test_packaging_spec.py::test_build_ps1_pre_bundle_clean_present` (target) | passed (against `uv pip`-shaped build.ps1) | passed (against `python -m pip`-shaped build.ps1, with NEW partial-revert negative drift-guard) |
| Pre-existing PyGIDeprecationWarning | 1 | 1 (unchanged — no new warnings introduced) |

The single warning (`gi.overrides.__init__:159 PyGIDeprecationWarning: GLib.unix_signal_add_full is deprecated`) is pre-existing and unrelated to this plan's surface — it fires from PyGObject's import machinery during `tests/test_packaging_spec.py::test_spec_imports_copy_metadata`'s test collection, not from any test code.

## Grep-Gate Evidence

**Positive** (all on executable lines):

```
python -m pip uninstall musicstreamer    → 1 hit (line 158)
python -m pip install -e                  → 2 hits (line 163 command + line 165 hint string)
PRE-BUNDLE CLEAN OK                       → 1 hit (line 168)
BUILD_FAIL reason=pre_bundle_clean_failed → 1 hit (line 165)
exit 8                                     → 2 hits (line 6 exit-codes header + line 166 actual exit)
VER-02-J                                   → 3 hits (rationale comment in step 3c, header for step 3c, header for step 4a)
```

**Negative** (executable lines only — comment-stripped via `grep -vE '^[[:space:]]*#'`):

```
uv pip uninstall musicstreamer  → 0 hits
uv pip install -e                → 0 hits
```

The rationale comment block at lines 132-156 still mentions `uv pip` historically (e.g. line 151's breadcrumb explicitly explains the swap), but the comment-stripped grep correctly excludes those.

## Negative Drift-Guard Sanity-Check

To prove the new partial-revert negative drift-guard is REACHABLE (i.e. it would actually fire RED if a future maintainer reintroduced `uv pip` on an executable line), I temporarily injected `Invoke-Native { uv pip uninstall musicstreamer -y }` into build.ps1's first non-comment line and ran the target test:

```
FAILED tests/test_packaging_spec.py::test_build_ps1_pre_bundle_clean_present
1 failed, 1 warning in 0.11s
```

Restored build.ps1 from a temp copy, re-ran:

```
6 passed, 1 warning in 0.07s
```

The drift-guard is not trivially-passing — it has teeth.

## Step-Ordering Invariant (lifted from Plan 65-04 SUMMARY)

```
123:    # --- 3b. Spec entry-point guard (PKG-01) ----------------------------
131:    # --- 3c. Pre-bundle dist-info clean (VER-02-J defense) -------------
170:    # --- 4. PyInstaller -------------------------------------------------
180:    # --- 4a. Post-bundle dist-info assertion (VER-02-J defense) ---------
285:    # --- 5. Smoke test --------------------------------------------------
294:    # --- 6. Inno Setup compile (D-01, D-07) -----------------------------
```

3b → 3c → 4 → 4a → 5 → 6 — UNCHANGED. Line numbers shifted slightly within step 3c due to the +6-line breadcrumb insert (lines 151-156); ordering is exact.

## Deviations from Plan

None — plan executed exactly as written. The 7 sub-edits enumerated in Task 1's `<action>` block all applied; the 5 sub-edits enumerated in Task 2's `<action>` block all applied; the negative drift-guard added matches the plan's text verbatim (`executable_lines` join, two `not in` assertions with the documented messages).

## Auth Gates

None — Linux dev pytest is the only automated verification (Win11 VM retest is a separate manual UAT step on the user's side, deferred per the plan's verification block).

## VER-02-J Closure Status

**Linux dev side (this plan's automated scope):** CLOSED.
- `tests/test_packaging_spec.py` 6 passed (binding gate).
- Positive grep-gates confirm `python -m pip` literals are on executable lines.
- Negative grep-gates confirm zero `uv pip` literals on executable lines.
- Step ordering invariant unchanged.
- Untouched-files invariant unchanged (5 files byte-identical).

**Win11 VM side (manual UAT):** DEFERRED — user re-runs `packaging\windows\build.ps1` on the Win11 spike conda env. Pass signal: build reaches `PRE-BUNDLE CLEAN OK` AND `POST-BUNDLE ASSERTION OK -- dist-info singleton: musicstreamer-2.1.65.dist-info (version 2.1.65 matches pyproject)`, exits 0, and the installed `MusicStreamer.exe` hamburger menu shows `v2.1.65` (NOT `v1.1.0`). The same VER-02-J validation_id is REUSED — not a new gap, just the unblocked retest of Plan 65-04's defenses.

## Out-of-Scope Discoveries

The full pytest suite (`uv run pytest`) shows 8 pre-existing failures in `_FakePlayer`-using test files (test_main_window_media_keys, test_ui_qt_scaffold, ui_qt/test_main_window_node_indicator) plus the test_main_window_gbs / test_import_dialog_qt flakes. All 8 are documented in `.planning/phases/65-.../deferred-items.md` as pre-existing Phase 62 follow-up work (FakePlayer test doubles missing the `underrun_recovery_started` Signal). Plan 65-05 does not touch any of these files (`git diff f91827b -- ...` empty for both `musicstreamer/ui_qt/main_window.py` and `tests/test_main_window_media_keys.py`); the failures reproduce against the plan's base commit. Per SCOPE BOUNDARY, not fixed in-plan; deferred-items.md not updated (entries already present).

## Self-Check: PASSED

- Plan file: `.planning/phases/65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb/65-05-PLAN.md` — FOUND
- Modified file 1: `packaging/windows/build.ps1` — FOUND, contains `python -m pip uninstall musicstreamer` (executable line 158)
- Modified file 2: `tests/test_packaging_spec.py` — FOUND, contains both positive (`assert "python -m pip uninstall musicstreamer"`) and negative drift-guard (`assert "uv pip uninstall musicstreamer" not in executable_lines`)
- Task 1 commit: `e224633` — FOUND in `git log --oneline f91827b..HEAD`
- Task 2 commit: `03194cf` — FOUND in `git log --oneline f91827b..HEAD`
- Untouched-file invariants: 5 sha256s match pre vs post (verified)
- Test gate: `uv run pytest tests/test_packaging_spec.py -x` reports 6 passed, 1 warning (verified)
- Step ordering: 3b → 3c → 4 → 4a → 5 → 6 (verified by grep)
