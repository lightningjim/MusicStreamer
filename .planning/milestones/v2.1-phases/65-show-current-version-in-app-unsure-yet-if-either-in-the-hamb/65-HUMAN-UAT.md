---
status: complete
phase: 65-show-current-version-in-app
source:
  - 65-VERIFICATION.md
started: 2026-05-09T01:00:00Z
updated: 2026-05-09T02:00:00Z
---

## Current Test

[testing complete]

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
result: pass
validation_id: VER-02-J
verified: 2026-05-09T02:00:00Z
notes: |
  User confirmed on Win11 VM: build markers #3 (BUILD_OK step=pyinstaller)
  and #4 (POST-BUNDLE ASSERTION OK -- dist-info singleton: musicstreamer-2.1.65.dist-info)
  observed in build log; installer ran, MusicStreamer.exe launched,
  hamburger menu last entry shows v2.1.65 greyed out.
  Plan 65-05's `python -m pip` swap unblocked the build that today's earlier
  retest crashed on; the bundled exe now shows v2.1.65 instead of v1.1.0.
  VER-02-J fully closed.

## Summary

total: 1
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none — VER-02-J fully closed end-to-end]
