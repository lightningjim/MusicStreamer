---
status: testing
phase: 65-show-current-version-in-app
source:
  - 65-01-SUMMARY.md
  - 65-02-SUMMARY.md
  - 65-03-SUMMARY.md
  - 65-04-SUMMARY.md
started: 2026-05-08T20:00:00Z
updated: 2026-05-08T23:55:00Z
---

## Current Test

[VER-02-J defense shipped via Plan 65-04 — awaiting Win11 VM rebuild + retest]

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
result: pending
reported: |
  Original failure (2026-05-08): "No, I see v1.1.0"
  Defense shipped in Plan 65-04 + review fixes (commits 8bcb56f..a5a69ca):
    - build.ps1 step 3c: pre-bundle uv pip uninstall+reinstall musicstreamer
    - build.ps1 step 4a: post-bundle dist-info singleton + Version: assertion (exit 9 on mismatch)
    - tests/test_packaging_spec.py: drift-guards lock both new build steps
severity: major
validation_id: VER-02-J

## Summary

total: 2
passed: 1
issues: 0
pending: 1
skipped: 0

## Gaps

- truth: "Bundled Windows exe shows v2.1.65 (matching pyproject.toml [project].version) in the hamburger menu footer"
  status: failed
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
