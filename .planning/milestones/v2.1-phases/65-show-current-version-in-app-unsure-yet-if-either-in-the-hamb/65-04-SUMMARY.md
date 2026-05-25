---
phase: 65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb
plan: 04
subsystem: packaging-windows-build-ps1
gap_closure: true
requirements: [VER-02]
tags: [packaging, windows, build-ps1, dist-info, copy_metadata, ver-02-j, gap-closure, defense-in-depth]
dependency_graph:
  requires:
    - "Plan 65-02 (copy_metadata in MusicStreamer.spec) — already shipped, untouched here"
    - "Plan 65-03 (musicstreamer/__version__.py removal) — runtime read sites untouched here"
  provides:
    - "build.ps1 step 3c — pre-bundle dist-info clean (uv pip uninstall + reinstall before pyinstaller)"
    - "build.ps1 step 4a — post-bundle dist-info singleton + Version: equality assertion"
    - "tests/test_packaging_spec.py drift-guards for both build.ps1 steps"
  affects:
    - "Future Win11 VM (and any other Windows build host) — bundles cannot silently ship a stale dist-info"
tech_stack:
  added:
    - "PowerShell Get-ChildItem -Filter dist-info pattern (defensive bundle inspection idiom new to this project)"
    - "uv pip uninstall + uv pip install -e ..\\.. as a build-tier reset step (new in build.ps1)"
  patterns:
    - "Single-source-of-truth for $appVersion (lifted regex parse from step 6 to step 4a; consumed by both POST-BUNDLE ASSERTION and iscc.exe)"
    - "Drift-guard test pattern (build_ps1_source fixture + read_text + substring/regex assertions) parallel to existing _SPEC + spec_source pattern in same module"
key_files:
  created: []
  modified:
    - path: packaging/windows/build.ps1
      change: "+121 -10: added step 3c (pre-bundle clean) + step 4a (post-bundle assertion); lifted pyproject regex parse from step 6 to step 4a; added exit codes 8 + 9 to header"
    - path: tests/test_packaging_spec.py
      change: "+136: added _BUILD_PS1 constant + build_ps1_source fixture + 2 new tests (4-substring + 6-substring drift-guards); existing 4 tests untouched"
decisions:
  - "Lifted vs duplicated $appVersion regex parse: chose to LIFT from step 6 to step 4a (single source of truth) per PLAN's preferred-but-optional guidance — cleaner diff, no two-source-of-truth smell. Removed the duplicate in step 6, replacing it with a comment pointing back to step 4a. Both step 4a's POST-BUNDLE ASSERTION and step 6's /DAppVersion=$appVersion now consume the lifted variable."
  - "Pre-bundle reinstall command: chose `uv pip install -e ..\\..` (editable install via PEP 660) over `uv sync --reinstall-package musicstreamer` — PLAN's recommended form; doesn't depend on uv.lock being present and is more idempotent across virtualenv layouts (conda env vs. plain venv). Drift-guard test accepts either form."
  - "Exit-code header update done in Task 1: claimed both `8=pre-bundle clean fail` AND `9=post-bundle dist-info assertion fail` in a single edit, even though Task 2 lands the `9=` step. Single-edit-per-header is cleaner than two header tweaks across two commits."
metrics:
  duration: "5m11s (311 seconds)"
  completed: "2026-05-08T23:53:49Z"
  tasks_completed: 3
  files_modified: 2
  files_created: 0
  commits: 3
---

# Phase 65 Plan 04: Harden Win11 build to ship exactly one matching musicstreamer dist-info (VER-02-J fix) — Summary

**One-liner:** Defense-in-depth at the build-script tier — `build.ps1` now uninstalls + reinstalls `musicstreamer` before PyInstaller (step 3c) AND scans the produced bundle to assert exactly one `musicstreamer-*.dist-info` whose `METADATA Version:` matches `pyproject.toml [project].version` (step 4a); two source-text drift-guard tests in `tests/test_packaging_spec.py` lock both new steps against accidental removal.

## Why

UAT VER-02-J: Bundled Windows `MusicStreamer.exe` showed `v1.1.0` in the hamburger menu instead of expected `v2.1.65`. Root cause (HIGH confidence): the Win11 VM build env had a stale `musicstreamer-1.1.0.dist-info` left over from a v1.x editable install. PyInstaller's `copy_metadata("musicstreamer")` (shipped by Plan 65-02) picked up BOTH the stale 1.1.0 dist-info AND the current 2.1.65 dist-info, bundled both, and at runtime `importlib.metadata.version("musicstreamer")` resolved to whichever appeared first on `sys.path` — the stale 1.1.0 won.

Phase 65 RESEARCH §Landmine 2 had mapped this exact failure mode (editable-install double-distribution); the Linux dev `.venv` was verified clean during research, but the Win11 VM was not, so the bug slipped past Plan 65-02's automated dev-side tests and only surfaced under manual UAT.

## What Changed

### `packaging/windows/build.ps1` (+121 −10)

**Step 3c — Pre-bundle dist-info clean (VER-02-J defense)** — inserted between step 3b (Spec entry-point guard) and step 4 (PyInstaller):

- Header rationale block citing VER-02-J + cross-references to drift-guard test + this plan, marked `DO NOT REMOVE without...`
- `Invoke-Native { uv pip uninstall musicstreamer -y 2>&1 | Out-Host }` — uninstall exit-code intentionally not checked (uv returns non-zero if package isn't installed, fine on a fresh build env)
- `Invoke-Native { uv pip install -e ..\.. 2>&1 | Out-Host }` — editable install via PEP 660 produces a real `.dist-info` matching `pyproject.toml [project].version`
- `if ($LASTEXITCODE -ne 0) { Write-Error ...; exit 8 }` — fail-loud on reinstall failure with `BUILD_FAIL reason=pre_bundle_clean_failed`
- Success log: `PRE-BUNDLE CLEAN OK -- fresh musicstreamer dist-info materialized in build env`

**Step 4a — Post-bundle dist-info assertion (VER-02-J defense)** — inserted between `BUILD_OK step=pyinstaller` and step 5 (smoke test):

- Header rationale block citing VER-02-J + cross-references; explains belt-and-braces guard for build-env edge cases the pre-bundle clean might miss
- **Lifted** the `pyproject.toml [project].version` regex parse from step 6 (lines 142–148) to the top of step 4a; deleted the duplicate at step 6 (replaced with a comment pointing back). `$appVersion` is now read once and consumed by both step 4a's POST-BUNDLE ASSERTION AND step 6's `/DAppVersion=$appVersion` for iscc.exe.
- `Test-Path` precondition on `..\..\dist\MusicStreamer\_internal` (failure: `BUILD_FAIL reason=bundle_internal_not_found ... exit 9`)
- `Get-ChildItem -Path $bundleInternal -Filter "musicstreamer-*.dist-info" -Directory` enumerates bundled dist-info(s)
- Singleton assertion: `if ($msDistInfos.Count -ne 1)` — dumps all found dist-info names to `Write-Host` before `Write-Error BUILD_FAIL reason=post_bundle_distinfo_not_singleton found_count=... exit 9`
- METADATA preconditions: `Test-Path` on bundled `METADATA` file; presence-of-Version-line check (both `exit 9` on failure)
- Version-match assertion: `if ($bundledVersion -ne $appVersion)` — dumps `pyproject` + `bundled METADATA Version:` + bundled dist-info dir name before `Write-Error BUILD_FAIL reason=post_bundle_version_mismatch ... exit 9`
- Success log: `POST-BUNDLE ASSERTION OK -- dist-info singleton: <name> (version <X.Y.Z> matches pyproject)`

**Exit-codes header (line 5)** updated with `8=pre-bundle clean fail, 9=post-bundle dist-info assertion fail`.

### `tests/test_packaging_spec.py` (+136)

- `_BUILD_PS1` module-level Path constant (parallel to existing `_SPEC`)
- `build_ps1_source` module-scoped fixture (parallel to existing `spec_source`)
- `test_build_ps1_pre_bundle_clean_present(build_ps1_source)` — 4 substring assertions: `VER-02-J`, `uv pip uninstall musicstreamer`, reinstall (accepts either `uv pip install -e` OR `uv sync --reinstall-package musicstreamer`), `exit 8`
- `test_build_ps1_post_bundle_dist_info_assertion_present(build_ps1_source)` — 6 substring assertions: `VER-02-J` count ≥2, `Get-ChildItem`, `musicstreamer-*.dist-info`, `.Count -ne 1`, `$bundledVersion -ne $appVersion`, `exit 9`
- Module docstring extended (one line) to mention Phase 65 Plan 04 / VER-02-J coverage
- Existing 4 spec_source tests UNCHANGED (function bodies byte-identical — verified via `grep -n "^def test_"` and full passing run)

## Untouched-File Invariants (sha256 evidence)

These files MUST be byte-identical before and after this plan. Captured at start; re-captured at end of each task; matched in all checks:

| File | sha256 (before & after) |
|------|------------------------|
| `packaging/windows/MusicStreamer.spec` | `b2aada6a9790e762a497b40819702a2f0821abe79d46aa02087dfe521ecace8a` |
| `musicstreamer/__main__.py` | `c5b3c0f11a76a5ce90167e1320f50840180b7289cb92aaff876867bc4697149d` |
| `musicstreamer/ui_qt/main_window.py` | `66108fbd908600d647a52bf162a8b95f0428565f4910597c1a4d1cf0a6e10056` |
| `tests/test_pkg03_compliance.py` | `fc27cd40335c287e03b768dfe2d29d215676ba122267e0349dbe197beb778f25` |

CONTEXT.md decision coverage:
- **D-08 (no try/except fallback at runtime read site):** PRESERVED. No runtime code touched. Step 4a is a build-time fail-loud assertion that EXTENDS D-08's contract from "fail loudly if metadata is missing" to "fail loudly if metadata is wrong." Strictly stronger; never weaker.
- **D-06a (grep gate for `__version__` importers):** N/A — `__version__.py` was already deleted by Plan 65-03.
- **D-01..D-07, D-09..D-13 (UI placement, label format, click behavior, Qt slot):** N/A — runtime UI code is not modified.

## Verification

### Quick suite (binding gate)

```
$ uv run pytest tests/test_packaging_spec.py -x
========================= 6 passed, 1 warning in 0.07s =========================
```

Pre/post test counts: **4 → 6** (4 existing spec_source tests unchanged; 2 new build_ps1_source tests added).

### Source-text grep gates

| Gate | Expected | Actual |
|------|----------|--------|
| `grep -c 'uv pip uninstall musicstreamer' packaging/windows/build.ps1` | ≥1 | 1 ✓ |
| `grep -c 'VER-02-J' packaging/windows/build.ps1` | ≥2 | 3 ✓ |
| `grep -c 'exit 8' packaging/windows/build.ps1` | ≥1 | 1 ✓ |
| `grep -c 'musicstreamer-\*\.dist-info' packaging/windows/build.ps1` | ≥1 | 5 ✓ |
| `grep -c '\$bundledVersion -ne \$appVersion' packaging/windows/build.ps1` | ≥1 | 1 ✓ |
| `grep -c 'exit 9' packaging/windows/build.ps1` | ≥1 | 5 ✓ |

### Step-ordering invariant

```
112:    # --- 3b. Spec entry-point guard (PKG-01) ----------------------------
120:    # --- 3c. Pre-bundle dist-info clean (VER-02-J defense) -------------
153:    # --- 4. PyInstaller -------------------------------------------------
163:    # --- 4a. Post-bundle dist-info assertion (VER-02-J defense) ---------
247:    # --- 5. Smoke test --------------------------------------------------
256:    # --- 6. Inno Setup compile (D-01, D-07) -----------------------------
```

3b → 3c → 4 → 4a → 5 → 6 (iscc) — exactly the placement the plan specified. Step 4a runs AFTER PyInstaller and BEFORE iscc.exe so a wrong-bundle build cannot reach the installer compile step.

### Single-source-of-truth check

```
$ grep -nE 'pyproject -match' packaging/windows/build.ps1
193:    if ($pyproject -match '(?ms)^\[project\].*?^version\s*=\s*"([^"]+)"') {
```

Exactly one regex parse remains (in step 4a). Step 6's iscc.exe call (`/DAppVersion=$appVersion` at line 275 + `MusicStreamer-$appVersion-win64-setup.exe` at line 282) reuses the lifted value.

## VER-02-J Closure Status

VER-02-J cannot be closed in-plan — closure requires a manual UAT cycle on the Win11 VM (PowerShell + PyInstaller + Inno Setup are not invoked in CI on Linux dev). The plan's defensive contract is verified at the source-text level (grep gates + 6 passing tests); the manual UAT closes the remaining real-host gap.

**Manual UAT (deferred to `/gsd-verify-work 65` post-merge on Win11 VM):**

1. User pulls main on Win11 VM after this plan merges
2. User runs `packaging\windows\build.ps1` from a conda-forge GStreamer env
3. User confirms build log shows `PRE-BUNDLE CLEAN OK` AND `POST-BUNDLE ASSERTION OK -- dist-info singleton: musicstreamer-2.1.<phase>.dist-info (version 2.1.<phase> matches pyproject)`
4. User installs the produced `.exe`, launches `MusicStreamer.exe`, opens hamburger menu (≡), confirms last entry shows `v2.1.<phase>` matching `pyproject.toml [project].version` (NOT `v1.1.0`)

If the bundle still ships a wrong version after this plan, the failure mode has shifted to one of:
- Step 3c didn't run (build.log missing `PRE-BUNDLE CLEAN OK`)
- Step 4a didn't catch it (build.log missing `POST-BUNDLE ASSERTION OK` and missing the failure dump)
- Runtime read site bypassing `importlib.metadata` (Plan 65-01 source-text tests would have caught this on Linux dev)

## Deviations from Plan

None. Plan executed exactly as written.

The only optional decision the plan left open — "lift vs duplicate the pyproject regex parse" — was resolved per the plan's stated preference (LIFT, single source of truth). The lift is reflected in the diff as a 7-line removal at step 6 (replaced with a 3-line comment pointing back) plus a 9-line addition at the top of step 4a's body. Net: cleaner diff, identical observable behavior at iscc.exe call site.

## Auth Gates

None encountered.

## Deferred Issues

Out-of-scope failure surfaced during full-suite regression sweep:

- `tests/test_main_window_gbs.py::test_add_gbs_menu_entry_exists` errors at setup with `AttributeError: '_FakePlayer' object has no attribute 'underrun_recovery_started'` — this is a **pre-existing** Phase 62 follow-up gap already documented in `.planning/phases/65-.../deferred-items.md` (the `_FakePlayer` test-double across 18+ test files needs the `underrun_recovery_started` Signal added; out of scope for VER-02-J build-tier work). Plan 65-04 only touched `packaging/windows/build.ps1` and `tests/test_packaging_spec.py`; this error is unrelated.

## Known Stubs

None. This plan does not introduce any UI rendering, hardcoded empty values, or placeholder text. The build-script edits are concrete, fail-loud invariants — no stubs.

## Threat Flags

None. The threat surface introduced by this plan (uv pip writes to build-env site-packages; Get-ChildItem reads on `dist/MusicStreamer/_internal`; Get-Content reads on bundled METADATA) is fully covered by the threat model in `65-04-PLAN.md` (T-65-04-01..05). All five threat IDs are dispositioned (`accept` or `mitigate`); the `mitigate` disposition for T-65-04-03 (stale dist-info silently shipping) IS the plan itself, and that mitigation is structurally in place + locked by drift-guard tests.

No new security-relevant surface introduced beyond what the threat model already covers.

## Self-Check: PASSED

- [x] Created/modified files exist:
  - `packaging/windows/build.ps1` — FOUND
  - `tests/test_packaging_spec.py` — FOUND
- [x] Commits exist (verified via `git log --oneline | grep`):
  - `ebf0ffb` (Task 1) — FOUND
  - `4f7267a` (Task 2) — FOUND
  - `f682180` (Task 3) — FOUND
- [x] Untouched-file sha256 invariants preserved (4 files; before == after)
- [x] `uv run pytest tests/test_packaging_spec.py -x` → 6 passed (4 existing + 2 new)
- [x] All success criteria from PLAN met
