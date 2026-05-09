---
status: partial
phase: 65-show-current-version-in-app
source:
  - 65-VERIFICATION.md
started: 2026-05-09T01:00:00Z
updated: 2026-05-09T01:00:00Z
---

## Current Test

[awaiting human testing — Win11 VM rebuild required]

## Tests

### 1. VER-02-J end-to-end on Win11 VM (post Plans 65-04 + 65-05)
expected: |
  In the Win11 VM, `conda activate spike` then run
  `packaging\windows\build.ps1`. Build log MUST show all four markers:
    - `=== PRE-BUNDLE CLEAN: python -m pip uninstall + reinstall musicstreamer ===`
    - `PRE-BUNDLE CLEAN OK -- fresh musicstreamer dist-info materialized in build env`
    - `BUILD_OK step=pyinstaller`
    - `POST-BUNDLE ASSERTION OK -- dist-info singleton: musicstreamer-2.1.65.dist-info (version 2.1.65 matches pyproject)`
  Then run the installer, launch MusicStreamer.exe, click hamburger (≡).
  Last entry shows `v2.1.65` (greyed out, non-clickable).
result: [pending]
validation_id: VER-02-J
notes: |
  Same validation_id as 65-UAT.md Test 2 — REUSED, not a new gap.
  Plan 65-05 closed the `uv not on PATH` blocker that prevented today's
  retest from running. This UAT confirms the closure on Win11.

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps

[none yet — pending human testing]
