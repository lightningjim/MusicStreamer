---
phase: 65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb
fixed_at: 2026-05-08T00:00:00Z
review_path: .planning/phases/65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb/65-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 65: Code Review Fix Report

**Fixed at:** 2026-05-08
**Source review:** `.planning/phases/65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb/65-REVIEW.md`
**Iteration:** 1

**Summary:**

- Findings in scope (Critical + Warning): 5
- Fixed: 5
- Skipped: 0
- Bonus drift-guard hardening: 1 commit (test-only, follow-up to WR-01)

All 5 in-scope findings were applied cleanly. Info-severity findings (IN-01 through IN-04) were excluded per `fix_scope: critical_warning`. The verification suite `uv run pytest tests/test_packaging_spec.py tests/test_main_run_gui_ordering.py -x` passes all 9 tests after the fix sequence.

## Fixed Issues

### BLK-01: `test_ensure_installed_runs_after_gst_init` is a vacuous assertion (false-pass invariant)

**Files modified:** `tests/test_main_run_gui_ordering.py`
**Commit:** `8bcb56f`
**Applied fix:** Added `_slice_run_gui(source) -> (body, offset)` helper that locates `def _run_gui(` and slices to the next top-level `def`. All three ordering tests (`test_ensure_installed_runs_before_qapplication`, `test_ensure_installed_runs_after_gst_init`, `test_set_application_version_in_run_gui`) now operate on the `_run_gui` body slice instead of the whole file, so they cannot accidentally cross-match against `Gst.init(None)` in `_run_smoke` (the false-pass surface BLK-01 documented). Replaced "byte" with "char" in error messages (also closes IN-01 incidentally for these tests, though IN-01 was out of scope). Confirmed all three tests still pass against current `__main__.py`.

### WR-01: `Write-Error ... ; exit N` does not emit the documented exit code

**Files modified:** `packaging/windows/build.ps1`
**Commit:** `39ce373`
**Applied fix:** Replaced every `Write-Error "BUILD_FAIL ..." ; exit N` pair (15+ sites covering exit codes 1, 2, 4, 5, 6, 7, 8, 9) with `Write-Host "BUILD_FAIL ..." -ForegroundColor Red ; exit N`. Under `$ErrorActionPreference = "Stop"`, `Write-Error` is escalated to a terminating error and the script unwinds through the surrounding `try/finally` as an unhandled exception, emitting PowerShell's default exit 1 — never reaching the documented `exit N`. `Write-Host` does NOT terminate under Stop, so the explicit `exit N` now actually fires, restoring the documented exit-code contract for CI / wrapper scripts. Added a multi-line comment block at the top of the script explaining the rationale and warning future maintainers not to revert the pattern.

### WR-02: pyproject.toml `version` regex is fragile to ordering of TOML sections

**Files modified:** `packaging/windows/build.ps1`
**Commit:** `d0b9b6a`
**Applied fix:** Tightened `(?ms)^\[project\].*?^version\s*=\s*"([^"]+)"` to `(?ms)^\[project\][^\[]*?^version\s*=\s*"([^"]+)"`. The `[^\[]*?` (lazy non-`[`) prevents the match from crossing into a sibling table — if `[project]` had no `version` key but a later `[other]` did, the old regex would incorrectly match the sibling's version. Added a clearer diagnostic hint to the `version_not_found_in_pyproject` failure message (now references `[project]` table boundary). Verified with a Python regex sanity check: still extracts `2.1.65` from current pyproject.toml AND correctly returns no match for a synthetic input where `version` lives in a sibling table. Single-quoted TOML version support deferred (out of scope; project policy is double-quoted strings in pyproject.toml).

### WR-03: `setApplicationVersion` source-of-truth check matches any `version(` call

**Files modified:** `tests/test_main_run_gui_ordering.py`
**Commit:** `3e102e9`
**Applied fix:** Tightened both halves of the contract check in `test_set_application_version_in_run_gui`:
1. Import pin: now requires `from importlib.metadata import version` (or `version as _pkg_version`) — the bare `from importlib.metadata import` was accepting any symbol (e.g. `distributions`).
2. Setter-site pin: now requires `_pkg_version(` or `metadata.version(` in the 200-char window after `setApplicationVersion(` — the bare `version(` was a strict subset of `packaging.version.version("1.0")` and similar. Updated assertion messages to call out the specific regression shape (`packaging.version.version`) so a future reviewer hitting the assertion knows what the test is defending against. Confirmed test still passes against current `__main__.py` (which uses `from importlib.metadata import version as _pkg_version` + `_pkg_version("musicstreamer")` — both forms accepted).

### WR-04: `Get-ChildItem -Filter "musicstreamer-*.dist-info"` over-matches subpackages

**Files modified:** `packaging/windows/build.ps1`
**Commit:** `cb44374`
**Applied fix:** Two-stage enumeration: `$msDistInfosBroad` keeps the original `Get-ChildItem -Filter "musicstreamer-*.dist-info"` (preserves the `musicstreamer-*.dist-info` literal that `tests/test_packaging_spec.py:226` drift-guards on), then `$msDistInfos = @($msDistInfosBroad | Where-Object { $_.Name -match '^musicstreamer-\d+\.\d+\.\d+\.dist-info$' })` filters to the canonical X.Y.Z shape only. Sibling distributions like `musicstreamer-extras-1.0.0.dist-info`, `musicstreamer-cli-2.0.0.dist-info`, `musicstreamer-old.dist-info`, and underscore-normalized names (`musicstreamer_extras-...`) are now correctly rejected. The failure-path diagnostic dump shows BOTH the matching set AND the broad set's rejected names so an operator hitting `exit 9` can immediately see what siblings were present in the build env. Verified the regex with a Python regex sanity check covering 6 test cases (3 expected matches, 3 expected rejections — all correct).

### Drift-guard hardening (WR-01 follow-up, user-requested)

**Files modified:** `tests/test_packaging_spec.py`
**Commit:** `a5a69ca`
**Applied fix:** Per user prompt — drift-guard tests previously asserted only that `"exit 8"` / `"exit 9"` literals appear somewhere in `build.ps1`, which is satisfied even by a `Write-Error ... ; exit N` pattern that silently regresses WR-01. Tightened both `test_build_ps1_pre_bundle_clean_present` and `test_build_ps1_post_bundle_dist_info_assertion_present` to:
1. Require the specific `BUILD_FAIL reason=...` diagnostic strings be present (5 reason tags for step 4a, 1 for step 3c).
2. For each diagnostic, verify `Write-Host` (NOT `Write-Error`) appears within ~120 chars before it — directly defending against accidental Write-Error reintroduction.
3. Verify the matching `exit N` follows within ~400 chars (allowing for multi-line diagnostic dumps before the exit). All 6 packaging-spec tests + 3 ordering tests pass after the hardening.

## Skipped Issues

None — all 5 in-scope findings (BLK-01, WR-01, WR-02, WR-03, WR-04) were applied cleanly.

## Out of Scope (Info, not fixed)

These were excluded per `fix_scope: critical_warning`. They are recorded here for visibility:

- **IN-01:** `_index()` "byte" vs "char" terminology — incidentally addressed in BLK-01's edits to `tests/test_main_run_gui_ordering.py` (the three tests this finding cited now say "char @ offset" instead of "byte @"). The other test files referenced were not touched.
- **IN-02:** `Invoke-Native` ErrorRecord-stringification dead-code documentation — not addressed.
- **IN-03:** `$LASTEXITCODE` stale-value risk on `command not found` — not addressed.
- **IN-04:** `_act_node_missing` conditional-attribute hazard in `MainWindow` — not addressed.

## Verification

```
uv run pytest tests/test_packaging_spec.py tests/test_main_run_gui_ordering.py -x
========================= 9 passed, 1 warning in 0.08s =========================
```

All ordering tests + drift-guard tests pass after the full fix sequence.

---

_Fixed: 2026-05-08_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
