---
status: resolved
phase: 65-show-current-version-in-app
source:
  - 65-01-SUMMARY.md
  - 65-02-SUMMARY.md
  - 65-03-SUMMARY.md
  - 65-04-SUMMARY.md
  - 65-05-SUMMARY.md
started: 2026-05-08T20:00:00Z
updated: 2026-05-09T02:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Hamburger menu version footer (Linux Wayland)
expected: |
  Run `uv run python -m musicstreamer` to launch the dev app.
  Click the hamburger menu (≡) in the top-left.
  The very LAST entry in the menu reads `v2.1.65` (greyed out, non-clickable).
  A separator appears immediately above it.
result: pass
validation_id: VER-02-I

### 2. Windows bundled exe shows version (Win11 VM) — RETEST after Plan 65-04
expected: |
  Re-run `packaging/windows/build.ps1` on the Win11 VM. Build log MUST contain
  both `PRE-BUNDLE CLEAN OK` and `POST-BUNDLE ASSERTION OK -- dist-info
  singleton: musicstreamer-2.1.65.dist-info (version 2.1.65 matches pyproject)`.
  Then run the installer, launch MusicStreamer.exe, click hamburger (≡).
  Last entry shows `v2.1.65` (NOT v1.1.0), greyed out, non-clickable.
result: issue
reported: |
  2026-05-09 retest on Win11 VM (conda env: spike):
  build.ps1 crashed at step 3c "PRE-BUNDLE CLEAN: uv pip uninstall + reinstall musicstreamer".
  Verbatim error: "uv : The term 'uv' is not recognized as the name of a cmdlet, function, script file, or operable program."
  Build did NOT reach PRE-BUNDLE CLEAN OK or POST-BUNDLE ASSERTION OK; no dist/ produced.
  Prior context (2026-05-08): original failure "No, I see v1.1.0".
severity: blocker
validation_id: VER-02-J

## Summary

total: 2
passed: 1
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "Bundled Windows exe shows v2.1.65 (matching pyproject.toml [project].version) in the hamburger menu footer"
  status: resolved
  resolved_by: "Plans 65-04 (PRE-BUNDLE CLEAN + POST-BUNDLE ASSERTION) and 65-05 (uv pip -> python -m pip swap for spike conda env). Confirmed end-to-end on Win11 VM 2026-05-09: hamburger shows v2.1.65."
  reason: "User reported: No, I see v1.1.0"
  severity: major
  test: 2
  validation_id: VER-02-J
  artifacts: []
  missing: []
  hypotheses:
    - h1: "Old installer still on disk — Win11 VM has a pre-Phase-65 (or pre-2.0) MusicStreamer installation; user hasn't rebuilt today's bundle yet. v1.1.0 is suspicious because it predates the menu footer code, so this would mean the user is seeing the version somewhere OTHER than the new hamburger footer (or the build is not what we think)."
    - h2: "PyInstaller copy_metadata picked up wrong dist-info — if the build environment had a stale `musicstreamer-1.1.0.dist-info` from an editable install made during v1.1, copy_metadata could have shipped that one. Bundle would then show v1.1.0 even on a today-built exe."
    - h3: "build.ps1 staged version drift — build.ps1 reads pyproject.toml at build time. If the user built before today's 2.1.65 bump, the installer's /DAppVersion (Inno Setup) and the package metadata could disagree from the running pyproject."

- truth: "build.ps1 PRE-BUNDLE CLEAN step (Plan 65-04 step 3c) runs successfully and emits PRE-BUNDLE CLEAN OK on Win11 VM"
  status: resolved
  resolved_by: "Plan 65-05: swapped uv pip uninstall|install -e for python -m pip uninstall|install -e (conda env always provides python+pip). Confirmed on Win11 VM 2026-05-09: build progressed past pre-bundle clean to BUILD_OK step=pyinstaller and POST-BUNDLE ASSERTION OK."
  reason: "User reported: build.ps1 crashed at PRE-BUNDLE CLEAN step on Win11 VM (conda env spike). Verbatim: \"uv : The term 'uv' is not recognized as the name of a cmdlet, function, script file, or operable program.\" Build aborted before reaching POST-BUNDLE ASSERTION; no dist/ produced; bundle version cannot be verified."
  severity: blocker
  test: 2
  validation_id: VER-02-J
  artifacts: []
  missing: []
  hypotheses:
    - h1: "uv not installed in spike conda env on Win11 VM — Plan 65-04 step 3c hard-codes the `uv` CLI. On Linux dev `uv` is on PATH (project tooling), but the Win11 spike env was provisioned without it. The fix needs to either install uv into spike (conda or pip), invoke it via `python -m uv`, or replace the uv calls with `python -m pip uninstall/install` which IS guaranteed to be on PATH inside any conda env."
    - h2: "PATH not refreshed in this shell — `uv` was just installed in another shell and PowerShell hasn't picked up the new PATH. Less likely given the user is on a clean `conda activate spike` session, but cheap to rule out by running `where.exe uv` or `python -m pip show uv`."
    - h3: "build.ps1 design assumption mismatch — the script may have been written assuming the project's top-level uv venv on Linux dev rather than a conda env on Windows. The pre-bundle clean was added in Plan 65-04 specifically to remove a stale `musicstreamer-1.1.0.dist-info`; the same intent can be expressed with `python -m pip uninstall musicstreamer -y` followed by `python -m pip install -e ../..` (or `--no-deps`), which works in any conda env without extra tooling."
