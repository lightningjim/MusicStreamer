---
phase: 69-debug-why-aac-streams-aren-t-playing-in-windows-possibly-mis
reviewed: 2026-05-11T12:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - tools/check_bundle_plugins.py
  - packaging/windows/build.ps1
  - packaging/windows/README.md
  - tests/test_packaging_spec.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 69: Code Review Report

**Reviewed:** 2026-05-11T12:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 69 adds a build-time plugin-presence guard so that AAC-codec regressions
(missing `gst-libav` / `gst-plugins-good` in the conda recipe) fail the
Windows bundle at build time instead of silently shipping a broken installer.
The implementation is structurally sound: it mirrors the existing PKG-03 /
spec-entry / dist-info guard idioms in `build.ps1`, single-sources the
required-plugin list in `tools/check_bundle_plugins.py`, and adds two
drift-guard pytest functions that cross-check README, build script, and the
required-list dict. The new tool follows the WR-01 Write-Host discipline,
emits structured `BUILD_FAIL reason=...` diagnostics, and uses the documented
exit-code convention (10).

No security or correctness blockers. Findings concentrate on drift-guard
brittleness (substring matching can produce false negatives or
false-positives in plausible future edits), one regex that picks the first
of N matching blocks rather than asserting uniqueness, a couple of
documentation drifts (the "What each step produces" table doesn't list the
new step 4b), and the previously-known fragility of the Python tool's
relative-path default. All findings are non-blocking; the phase ships
safely.

## Warnings

### WR-01: P-01 drift-guard regex picks first conda-create block; does not assert uniqueness

**File:** `tests/test_packaging_spec.py:445-456`
**Issue:** The `test_readme_conda_recipe_lists_every_required_plugin_package`
test uses `re.search(r"conda create -n musicstreamer-build[^\n]*\n((?:[^\n]*\n)+?)\`\`\`", readme_source)`,
which matches the FIRST `conda create -n musicstreamer-build` occurrence in
the README. If a future README edit adds a second example block before the
canonical recipe (e.g. a minimal "quick try" snippet preceding the full
recipe), the drift-guard would validate the first (incomplete) block and
silently miss the actual recipe. Repro (Python regression test, simulated):
inserting a minimal block above the canonical one yields a match where
`'gst-libav' not in m.group(0)` — but a substring scan in
`recipe_block = block_match.group(0)` would then fail the test for the
wrong reason ("missing gst-libav from recipe") or, worse, pass if the
required-plugin list shrinks. The test passes today only because exactly
one matching block exists in the current README.
**Fix:** Either (a) anchor the regex on the canonical recipe with a unique
marker (e.g. require `# AAC playback requires gst-libav` to appear inside
the block), or (b) use `re.findall` and assert exactly one match before
proceeding:
```python
blocks = re.findall(
    r"conda create -n musicstreamer-build[^\n]*\n(?:[^\n]*\n)+?```",
    readme_source,
)
assert len(blocks) == 1, (
    f"README must contain exactly one canonical 'conda create -n "
    f"musicstreamer-build' recipe block; found {len(blocks)}. If you "
    f"added an example/demo block, anchor the drift-guard on a unique "
    f"marker inside the canonical block."
)
recipe_block = blocks[0]
```

### WR-02: P-01 drift-guard uses substring match — admits typo / truncated package names as passing

**File:** `tests/test_packaging_spec.py:458-469`
**Issue:** `missing = [pkg for pkg in required_packages if pkg not in recipe_block]`
treats `pkg in recipe_block` as a substring match. If a future
maintainer accidentally types a required package name as a prefix of a
real conda-forge package (e.g. typo `gst-plugins` instead of
`gst-plugins-good`), the substring `gst-plugins` is present in the recipe
(matches the literal "gst-plugins-base", "gst-plugins-good", etc.), so the
drift-guard would pass even though the typed package name does not
correspond to a real conda-forge artifact. The build would then succeed
locally on a host that happens to have the real packages installed but
the guard's promise — "every required-list package is also in the
recipe" — is broken. Affects only future edits where someone introduces
a substring-of-existing-package as a required entry.
**Fix:** Match on whole-word boundaries, e.g.:
```python
import re as _re
missing = [
    pkg
    for pkg in required_packages
    if not _re.search(rf"(?<![\w-]){_re.escape(pkg)}(?![\w-])", recipe_block)
]
```
or tokenize the recipe block by whitespace/backtick continuations and
check set membership.

### WR-03: G-01 drift-guard asserts `"exit 10"` literal but only the first occurrence; later occurrences could go undetected

**File:** `tests/test_packaging_spec.py:515-518, 544-550`
**Issue:** `test_build_ps1_invokes_plugin_guard_with_exit_10` asserts
`"exit 10" in build_ps1_source` to confirm the failure path exists.
Today, `build.ps1` contains exactly one `exit 10` site (line 305). If
a future maintainer copies the step 4b block as a template for a
hypothetical step 4c and forgets to update the exit code (leaving two
`exit 10` lines that mean different things), the test still passes —
masking a real exit-code collision. The subsequent
`assert "exit 10" in after` (line 546) where `after = build_ps1_source[idx : idx + 400]`
catches a stricter "near the plugin_missing BUILD_FAIL" case, so the
literal-exists check on line 515 is redundant with line 546 anyway.
**Fix:** Strengthen the global check to assert uniqueness if the
phase contract is "one exit-10 site":
```python
assert build_ps1_source.count("exit 10") == 1, (
    "build.ps1 must have exactly one `exit 10` site (step 4b "
    "plugin-presence guard). Found {n}."
).format(n=build_ps1_source.count("exit 10"))
```
…or drop the redundant global check and rely on line 546's near-anchor.

### WR-04: `tools/check_bundle_plugins.py` default `--bundle` value is fragile to CWD; succeeds-or-fails-loudly is luck, not contract

**File:** `tools/check_bundle_plugins.py:51-59`
**Issue:** The default is `Path("dist/MusicStreamer/_internal")`, a
relative path. When invoked from `build.ps1` (CWD = `packaging/windows/`),
`--bundle` is passed explicitly, so this is moot. But the tool's
docstring (line 14) advertises it as runnable as
`python tools/check_bundle_plugins.py --bundle <path>` "from the repo
root" — without `--bundle`, the default works only when CWD is the
repo root. Run it from anywhere else (or invoke via an absolute
`python /full/path/to/check_bundle_plugins.py`) and the tool fails with
"bundle plugins dir not found" — which is the same exit code (10) used
for the actual plugin-missing case, conflating a usage error with a
genuine drift. Per WIN-05 the tool is invoked only via `build.ps1`, so
this is low impact, but a maintainer running the tool ad-hoc during
diagnosis will be misled.
**Fix:** Either (a) resolve the default relative to the tool's own
location:
```python
_REPO_ROOT = Path(__file__).resolve().parent.parent
default=_REPO_ROOT / "dist" / "MusicStreamer" / "_internal",
```
or (b) make `--bundle` required and remove the default, since the
tool is currently always invoked with `--bundle` anyway. Bonus: at
minimum, distinguish "bundle dir doesn't exist" from "plugin DLL
missing" with different exit codes (e.g. 10 for missing plugin, 11
for missing bundle dir) so CI logs can disambiguate the two failure
modes.

## Info

### IN-01: README "What each step produces" table omits new step 4b plugin guard

**File:** `packaging/windows/README.md:55-65`
**Issue:** The table at lines 57-65 lists Pre-flight, PKG-03, Spec
entry, PyInstaller, Inno Setup, Diagnostic — but the new
post-bundle plugin-presence guard (step 4b) is not listed. A future
maintainer reading the README will see PyInstaller -> Inno Setup with
no intermediate guard, then be surprised when `exit 10` appears in
the build log without README documentation.
**Fix:** Add a row, e.g.:
```
| Plugin-presence guard       | Runs `tools/check_bundle_plugins.py` (AAC codec DLLs in bundle) |
```
Place it between the PyInstaller row and the Inno Setup row to
reflect chronological order.

### IN-02: README rationale comments live INSIDE the fenced PowerShell code block (will execute as PS comments at build time)

**File:** `packaging/windows/README.md:24-25`
**Issue:** Lines 24-25 are PowerShell `#` comments embedded inside
the fenced ```powershell``` recipe block. They render fine in
markdown, and if a user copy-pastes the block they harmlessly
execute as PS no-ops. However, the comments are documentation
metadata about WHY certain packages are required — they would be
better served as prose paragraphs immediately after the fenced
block so they don't get accidentally tokenized as `conda` arguments
by a careless paste (PowerShell's `\`` line-continuation immediately
above line 24 ends the `conda create` invocation, so this is
currently safe, but the visual separation between the conda command
and the comment lines is subtle).
**Fix:** Move lines 24-25 below the closing ```\`\`\``` fence as a
prose paragraph. No functional change; clarity-only.

### IN-03: docstring exit-code description in `check_bundle_plugins.py` is generic — does not mention "bundle dir missing" sub-case

**File:** `tools/check_bundle_plugins.py:10-12`
**Issue:** The docstring lists `10 — plugin missing` but the code
also returns 10 when the bundle plugins directory doesn't exist
(line 71). A future reader scanning the docstring will not know to
look at the bundle-dir-not-found path. Pairs with WR-04 if exit
codes are differentiated.
**Fix:** Either update the docstring:
```
10 — plugin missing OR bundle plugins directory not found
```
or split the exit codes (preferred, per WR-04).

### IN-04: `test_build_ps1_invokes_plugin_guard_with_exit_10` substring `"10=post-bundle plugin-presence guard fail"` will silently survive a renamed step

**File:** `tests/test_packaging_spec.py:519-524`
**Issue:** The test asserts the exit-code header literal
`"10=post-bundle plugin-presence guard fail"` is present, but the
trailing `(Phase 69)` tag in the actual header line 7 is NOT included
in the assertion. If a maintainer adds a new exit code 11 in a
future phase and accidentally renumbers 10 to mean something else
while keeping the original `10=post-bundle plugin-presence guard fail`
text intact (low-likelihood but the kind of mistake drift-guards
exist for), the test passes. Low impact; flagged for completeness.
**Fix:** Tighten by including the phase tag:
```python
assert "10=post-bundle plugin-presence guard fail (Phase 69)" in build_ps1_source
```

---

_Reviewed: 2026-05-11T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
