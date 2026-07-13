---
phase: 88-windows-packaging-bundle-win-02-ver-02-j-win-05
plan: "01"
subsystem: windows-packaging
tags: [inno-setup, windows, aumid, shortcut, release-notes]
dependency_graph:
  requires: []
  provides: [WIN-02-A]
  affects: [packaging/windows/MusicStreamer.iss, RELEASE-NOTES.md]
tech_stack:
  added: []
  patterns: [InstallDelete, Inno Setup upgrade shortcut cleanup]
key_files:
  created:
    - RELEASE-NOTES.md
  modified:
    - packaging/windows/MusicStreamer.iss
decisions:
  - "[88-01] [InstallDelete] scoped to exactly two literal .lnk paths — no wildcards, no filesandordirs — to satisfy T-88-01 tamper mitigation"
  - "[88-01] Comment block in .iss references WIN-02-A and Pitfall 6 for future maintainer context"
metrics:
  duration: 1 min
  completed: "2026-06-05T23:10:36Z"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 88 Plan 01: Inno [InstallDelete] shortcut cleanup + RELEASE-NOTES.md taskbar-unpin footnote

**One-liner:** Added Inno Setup `[InstallDelete]` section removing two stale `.lnk` shortcuts before upgrade and created `RELEASE-NOTES.md` with the AUMID-caching taskbar-unpin guidance for v2.2.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Add `[InstallDelete]` section to `MusicStreamer.iss` | e0eef865 | packaging/windows/MusicStreamer.iss |
| 2 | Create `RELEASE-NOTES.md` with v2.2 taskbar-unpin note | 212672e0 | RELEASE-NOTES.md |

## What Was Built

**Task 1 — `[InstallDelete]` section in `MusicStreamer.iss`:**
Inserted an `[InstallDelete]` section positioned directly before the existing `[Icons]` section. The section contains exactly two `Type: files` entries:
- `{userprograms}\MusicStreamer.lnk` — the main shortcut (which carries the AUMID)
- `{userprograms}\Uninstall MusicStreamer.lnk` — the companion uninstall shortcut

A comment block above the section explains the WIN-02-A rationale and Pitfall 6 (stale taskbar-pinned AUMID). No wildcards, no `filesandordirs`, no `{userappdata}` / `{localappdata}` paths — scoped to exactly the two literal paths per T-88-01 mitigation. The D-03 trailing comment (preserve user data on uninstall) is untouched.

**Task 2 — `RELEASE-NOTES.md`:**
Created at the repo root with a `## v2.2` section documenting the Windows upgrade procedure for users who had MusicStreamer pinned to the taskbar. Explains the AUMID caching mechanism (`org.lightningjim.MusicStreamer`), why the installer's `[InstallDelete]` cannot reach an already-pinned taskbar shortcut, and the four-step unpin→upgrade→launch→repin procedure. References WIN-02-A / Pitfall 6.

## Verification Results

**Task 1 automated checks (all pass):**
- `grep -q '^\[InstallDelete\]'` — section header present
- `grep -q 'MusicStreamer\.lnk'` — .lnk target present
- `grep -q 'Type: files'` — correct Inno deletion type
- `awk '/^\[InstallDelete\]/{d=NR} /^\[Icons\]/{i=NR} END{exit !(d>0 && i>0 && d<i)}'` — [InstallDelete] before [Icons]
- No `filesandordirs` as an active directive (only in comment)
- No `*` glob anywhere in `[InstallDelete]` section
- No `{userappdata}` / `{localappdata}` paths in `[InstallDelete]` section

**Task 2 automated checks (all pass):**
- `test -f RELEASE-NOTES.md` — file exists
- `grep -qi 'unpin'` — "unpin" present
- `grep -qi 'taskbar'` — "taskbar" present
- `grep -q '## v2.2'` — v2.2 section header present
- `grep -q 'org\.lightningjim\.MusicStreamer'` — AUMID literal present

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Changes are installer configuration (static `.iss` file) and documentation only. Threat model T-88-01 and T-88-02 mitigations confirmed satisfied by scoped deletion implementation.

## Known Stubs

None.

## Self-Check: PASSED

- `packaging/windows/MusicStreamer.iss` — FOUND (modified)
- `RELEASE-NOTES.md` — FOUND (created)
- Commit `e0eef865` — FOUND (Task 1)
- Commit `212672e0` — FOUND (Task 2)
