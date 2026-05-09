---
phase: 65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb
reviewed: 2026-05-09T13:30:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - packaging/windows/build.ps1
  - tests/test_packaging_spec.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 65 Plan 05: Code Review Report

**Reviewed:** 2026-05-09T13:30:00Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Plan 65-05 swaps `uv pip uninstall|install -e` for `python -m pip uninstall|install -e` in `build.ps1` step 3c (the VER-02-J pre-bundle clean defense), and updates the corresponding drift-guards in `tests/test_packaging_spec.py::test_build_ps1_pre_bundle_clean_present` to lock the new literals.

**The core swap is correct.** Both calls use `python -m pip`, the failure path on the install (line 164-167) preserves `Write-Host ... -ForegroundColor Red` + `exit 8` + `BUILD_FAIL reason=pre_bundle_clean_failed` (so WR-01's exit-code reachability invariant still holds), and the uninstall exit code is intentionally not checked with a documented rationale. Other steps in `build.ps1` were not touched. The new negative drift-guard correctly strips comment-only lines before asserting `uv pip` absence, so the rationale block at lines 151-156 (which legitimately discusses the pre-Plan-65-05 history) does not trip the guard.

**Issues found:** Two stale `uv pip ...` references in `build.ps1` survived the swap inside diagnostic / explanatory comments, where they will misdirect future maintainers debugging a related failure. Two test-side inconsistencies in the reinstall acceptance set and the negative drift-guard's comment-stripping precision are also flagged.

No security issues. No shell-injection or path-traversal surface introduced. PowerShell quoting at lines 158 and 163 is consistent with the existing precedent at lines 102-108 (bare `python -m pip` tokens inside `Invoke-Native { ... 2>&1 | Out-Host }`).

## Warnings

### WR-01: Stale `uv pip uninstall` reference in step 4a's `post_bundle_version_mismatch` hint

**File:** `packaging/windows/build.ps1:279`
**Issue:** The hint string for the post-bundle version-mismatch BUILD_FAIL diagnostic still says:

```
hint='step 3c pre-bundle clean did not refresh dist-info -- investigate uv pip uninstall behavior'
```

After Plan 65-05, step 3c no longer calls `uv pip` — it calls `python -m pip`. A future maintainer hitting `BUILD_FAIL reason=post_bundle_version_mismatch` and following this hint will:

1. grep `build.ps1` for `uv pip uninstall` on executable lines and find nothing (the new negative drift-guard at `tests/test_packaging_spec.py:277-286` explicitly forbids that),
2. waste cycles cross-referencing the hint against `uv` documentation when the actual culprit lives in `python -m pip` semantics.

This is a Plan 65-05 swap that was missed during the find-and-replace — the literal lives in a diagnostic message string, not on a command line, so the negative drift-guard does not catch it (the test asserts the exact substring `"uv pip uninstall musicstreamer"` is absent from executable lines; the message at line 279 contains `uv pip uninstall behavior`, so the substring assertion passes despite the regression).

**Fix:** Update the hint to refer to the current command:

```powershell
Write-Host "BUILD_FAIL reason=post_bundle_version_mismatch bundled='$bundledVersion' expected='$appVersion' hint='step 3c pre-bundle clean did not refresh dist-info -- investigate python -m pip uninstall/install behavior'" -ForegroundColor Red
```

### WR-02: Reinstall acceptance set in test contains a self-contradictory branch

**File:** `tests/test_packaging_spec.py:204-217` and `tests/test_packaging_spec.py:287-292`
**Issue:** `test_build_ps1_pre_bundle_clean_present` declares (lines 197-217) that the reinstall command may be any of three shapes:

1. `python -m pip install -e` (Plan 65-05 default)
2. `uv pip install -e` (legacy Plan 65-04 form, "tolerated for forward-compat")
3. `uv sync --reinstall-package musicstreamer` (legacy alternative)

But the negative drift-guard later in the same test (lines 287-292) hard-asserts `"uv pip install -e" not in executable_lines`. So if a future maintainer reintroduced `uv pip install -e ..\..` (the very forward-compat shape the docstring promises is tolerated), the `has_reinstall` check at line 204 would pass while the negative guard at line 287 would fail — the test would always FAIL on that input, contradicting the docstring's tolerance claim.

The only forward-compat shape that is genuinely tolerated by both halves of the test is `uv sync --reinstall-package musicstreamer` (which the negative guard does not block). The `uv pip install -e` branch in the acceptance set is dead code — reaching it would simultaneously fire the negative guard.

This matters because the docstring (a contract for future maintainers) says one thing while the test enforces another. A Win11-on-uv migration in the future would hit a confusing dual-failure shape: the "tolerated" branch is in fact forbidden.

**Fix:** Either:
- (a) tighten the docstring + acceptance set to drop the `uv pip install -e` branch, leaving `python -m pip install -e` (required) OR `uv sync --reinstall-package musicstreamer` (tolerated alternate); or
- (b) tighten the negative drift-guard to only forbid `uv pip uninstall musicstreamer` (the actual Win11-VM failure-mode shape), and allow `uv pip install -e` to remain a forward-compat shape.

Option (a) is simpler and matches the spirit of "Plan 65-05 hard-required `python -m pip` because uv is not on PATH":

```python
has_reinstall = (
    "python -m pip install -e" in build_ps1_source
    or "uv sync --reinstall-package musicstreamer" in build_ps1_source
)
assert has_reinstall, (
    "build.ps1 step 3c must reinstall musicstreamer after uninstalling, "
    "via either `python -m pip install -e ..\\..` (Plan 65-05 default) "
    "or `uv sync --reinstall-package musicstreamer` (forward-compat for "
    "a future uv-managed Windows env). The legacy `uv pip install -e` "
    "shape is forbidden by the negative drift-guard below — Plan 65-05 "
    "removed it because uv is not on PATH in the Win11 spike conda env."
)
```

## Info

### IN-01: Stale `uv install fail` reference in build.ps1 header comment

**File:** `packaging/windows/build.ps1:24`
**Issue:** The Phase 65 WR-01 explainer block at lines 18-27 contains:

```
# $LASTEXITCODE (e.g. exit 8 -> uv install fail, exit 9 -> dist-info drift)
```

After Plan 65-05, exit code 8 is no longer "uv install fail" — it's "python -m pip install fail" (or more generally, "pre-bundle clean fail"). The comment is hedged with `e.g.` so it is not strictly a contract, but a reader scanning the header for a quick reference to what each exit code means will still get a misleading mental model.

**Fix:** Update the parenthetical to reflect Plan 65-05:

```powershell
# $LASTEXITCODE (e.g. exit 8 -> pre-bundle clean (python -m pip) fail, exit 9 -> dist-info drift)
```

This also matches the canonical exit-code header at line 6 (`8=pre-bundle clean fail`) which is already command-agnostic.

### IN-02: Negative drift-guard's comment-stripping is too coarse for inline comments

**File:** `tests/test_packaging_spec.py:273-276`
**Issue:** The new negative drift-guard splits `build.ps1` by line and drops lines whose first non-whitespace character is `#`:

```python
executable_lines = "\n".join(
    line for line in build_ps1_source.splitlines()
    if not line.lstrip().startswith("#")
)
```

This correctly strips fully-commented lines (the rationale block at build.ps1 lines 151-156, which legitimately mentions the pre-Plan-65-05 `uv pip` history, is correctly excluded). However, it does NOT strip PowerShell inline comments of the form `command  # comment`. If a future maintainer wrote, e.g.:

```powershell
Invoke-Native { python -m pip install -e ..\.. }   # legacy was: uv pip install -e ..\..
```

…the line is not comment-only, so it is included in `executable_lines`, and the substring `uv pip install -e` would appear there — firing the negative drift-guard despite the actual command being correct.

This is a low-probability false-positive (PowerShell hash-comment-after-command is uncommon, and `Invoke-Native { ... }` lines tend not to carry trailing comments), but the docstring at lines 261-272 implies the guard is comment-aware in general. Worth either tightening the regex or documenting the limitation in the docstring.

**Fix:** Either strip inline comments before the comparison, or document the limitation. Stripping is straightforward:

```python
import re
_INLINE_COMMENT = re.compile(r"\s+#.*$")
executable_lines = "\n".join(
    _INLINE_COMMENT.sub("", line)
    for line in build_ps1_source.splitlines()
    if not line.lstrip().startswith("#")
)
```

Caveat: this regex does not understand string literals — if a `# ` lives inside a single-quoted PowerShell string (rare but possible in BUILD_FAIL hint strings), it would be stripped too. For the current build.ps1 there are no such strings, so the simple regex is safe today, but the limitation should be in a comment.

Alternatively (lower-effort): leave the code as-is and add a one-liner caveat to the existing docstring at lines 261-272 explaining that inline `# ...` comments are NOT stripped, so a future maintainer who reaches for that idiom will know to refactor the comment to its own line.

---

_Reviewed: 2026-05-09T13:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
