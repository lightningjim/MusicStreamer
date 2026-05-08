---
status: testing
phase: 65-show-current-version-in-app
source:
  - 65-01-SUMMARY.md
  - 65-02-SUMMARY.md
  - 65-03-SUMMARY.md
started: 2026-05-08T20:00:00Z
updated: 2026-05-08T20:00:00Z
---

## Current Test

[testing complete — issues found, diagnosis in progress]

## Tests

### 1. Hamburger menu version footer (Linux Wayland)
expected: |
  Run `uv run python -m musicstreamer` to launch the dev app.
  Click the hamburger menu (≡) in the top-left.
  The very LAST entry in the menu reads `v2.1.65` (greyed out, non-clickable).
  A separator appears immediately above it.
result: pass
validation_id: VER-02-I

### 2. Windows bundled exe shows version (Win11 VM)
expected: |
  Build the Windows installer via `packaging/windows/build.ps1` from the
  Win11 VM. Run the installer. Launch MusicStreamer.exe from Start Menu.
  Click the hamburger menu (≡). The last entry shows `v2.1.65` (same as
  dev), greyed out, non-clickable. No PackageNotFoundError on launch.
result: issue
reported: "No, I see v1.1.0"
severity: major
validation_id: VER-02-J

## Summary

total: 2
passed: 1
issues: 1
pending: 0
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
