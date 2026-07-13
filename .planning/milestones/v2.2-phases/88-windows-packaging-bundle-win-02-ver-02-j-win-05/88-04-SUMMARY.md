---
phase: 88-windows-packaging-bundle-win-02-ver-02-j-win-05
plan: "04"
subsystem: windows-installer
tags: [inno-setup, dist-info, upgrade-cleanup, uat]
dependency_graph:
  requires: []
  provides: [installer-dist-info-cleanup, uat-17-row]
  affects: [packaging/windows/MusicStreamer.iss, 88-HUMAN-UAT.md]
tech_stack:
  added: []
  patterns: [inno-setup-installdeletesection, wildcard-scoped-cleanup]
key_files:
  created: []
  modified:
    - packaging/windows/MusicStreamer.iss
    - .planning/phases/88-windows-packaging-bundle-win-02-ver-02-j-win-05/88-HUMAN-UAT.md
decisions:
  - "[T-88-01] filesandordirs wildcard strictly scoped to {app}\\_internal\\musicstreamer-*.dist-info — install dir only, no user-data paths"
  - "UAT-17 row authored now; VM execution deferred to next VM session"
metrics:
  duration: "2m"
  completed: "2026-06-09T16:00:10Z"
  tasks_completed: 2
  files_modified: 2
requirements: [WIN-02-A, VER-02-J]
---

# Phase 88 Plan 04: Add Scoped dist-info [InstallDelete] Cleanup + UAT-17 Row Summary

## One-Liner

Closes UAT Gap G1: adds a scoped `[InstallDelete]` filesandordirs row to MusicStreamer.iss that wipes stale `musicstreamer-*.dist-info` directories from `{app}\_internal` before each upgrade install, plus authors the UAT-17 verification row with the exact PowerShell `.Count` expression.

## What Was Built

**Task 1 — MusicStreamer.iss [InstallDelete] extension:**
Added one new directive to the `[InstallDelete]` section:
```
Type: filesandordirs; Name: "{app}\_internal\musicstreamer-*.dist-info"
```
Placed after the two pre-existing shortcut-cleanup `Type: files` rows. The comment block above the section was fully rewritten to explain:
- WHY filesandordirs is now permitted for this one path (`{app}\_internal\` is the install dir, fully install-managed, replaced every build, contains no user data)
- WHY the prohibition remains for everything else (protects SQLite DB, cookies, tokens, accent CSS, EQ profiles, logo cache under platformdirs.user_data_dir per D-03)
- WHAT this fixes (Gap G1: stale dist-info pileup caused `importlib.metadata.version` to return the lowest version — observed 2.1.68 while running 2.2.86)
- HOW the timing makes it safe-and-sufficient ([InstallDelete] runs before [Files], leaving exactly one fresh dist-info after the bundle is copied)

This is the install-side analog of build.ps1's pre-bundle clean (~line 158-169) and post-bundle singleton assertion (exit 9, ~line 245-254).

**Task 2 — 88-HUMAN-UAT.md UAT-17 row:**
Appended new row UAT-17 (after UAT-16) to the UAT Checklist table, tagged WIN-02-A / VER-02-J, with:
- Behavior: upgrade install yields exactly ONE dist-info in installed `_internal` and app reports built version
- Method: exact PowerShell `(Get-ChildItem "$env:LOCALAPPDATA\Programs\MusicStreamer\_internal" -Filter "musicstreamer-*.dist-info").Count` expression plus `.Name` readback and optional `--version` check
- Expected: `.Count == 1`, surviving dir is `musicstreamer-<built X.Y.Z>.dist-info` (not a stale lower version)
- Pass/Fail: blank (pending VM session)
- Notes: references Gap G1 and the three stale dirs observed in Evidence § Diagnostic

Summary block updated: `total: 16 -> 17`, `pending: 0 -> 1`. Sign-Off checkbox updated to reference all 17 rows. No existing rows 1-16 were altered.

## Acceptance Criteria Verification

All criteria verified with `grep` after edits:

| Check | Result |
|-------|--------|
| filesandordirs dist-info line present in ISS | PASS |
| Two pre-existing Type: files shortcut rows unmodified | PASS |
| No [UninstallDelete] section added | PASS (count=0) |
| filesandordirs only under {app}\_internal (no userappdata/localappdata) | PASS |
| Comment explains scoped exception and D-03 preservation | PASS (written) |
| UAT-17 row exists | PASS |
| .Count expression present | PASS |
| WIN-02-A, VER-02-J tags present | PASS |
| Summary total updated to 17 | PASS |
| pending incremented to 1 | PASS |
| Rows 1-16 intact (spot-checked UAT-1 and UAT-16) | PASS |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. UAT-17 Pass/Fail column is intentionally blank (pending VM session) — this is by design, not a stub. The VM execution is deferred as specified in the plan's resume-signal.

## Threat Flags

No new threat surface beyond what the plan's threat model already covers. The new `[InstallDelete]` filesandordirs directive was verified to reference only `{app}\_internal\musicstreamer-*.dist-info` — no `{userappdata}` or `{localappdata}` paths, no path traversal, no `[UninstallDelete]` section.

## Self-Check: PASSED

Files created/modified verified to exist:
- packaging/windows/MusicStreamer.iss: modified (Task 1)
- .planning/phases/88-windows-packaging-bundle-win-02-ver-02-j-win-05/88-HUMAN-UAT.md: modified (Task 2)

Commits verified:
- 12cab5b2: feat(88-04): add scoped dist-info [InstallDelete] cleanup to MusicStreamer.iss
- f4fc1f67: docs(88-04): add UAT-17 upgrade dist-info cleanup row to 88-HUMAN-UAT.md
