---
phase: 88-windows-packaging-bundle-win-02-ver-02-j-win-05
plan: "03"
subsystem: windows-packaging
tags: [uat, win11-vm, aumid, smtc, aac, human-verify, checkpoint]
dependency_graph:
  requires: [88-01, 88-02, 88-04]
  provides: [win11-vm-uat-signoff, ver-02-j-closure]
  affects: [88-HUMAN-UAT.md, 88-03-CONSOLIDATED-VM-UAT.md, 88-UAT.md]
tech_stack:
  added: []
  patterns: [checkpoint-human-verify, consolidated-vm-uat-session]
key_files:
  created:
    - .planning/phases/88-windows-packaging-bundle-win-02-ver-02-j-win-05/88-HUMAN-UAT.md
  modified:
    - .planning/phases/88-windows-packaging-bundle-win-02-ver-02-j-win-05/88-UAT.md
decisions:
  - "Option C: held Phase 88 open and ran ONE consolidated Win11 VM session covering 88 (G1/G5), 88.1 (G2), 88.2 (G3) instead of three separate VM passes"
  - "QtWebEngine OAuth-login gap (G6, tests 6/7/8) was carved out to Phase 88.3 (B1 isolated-helper); 88-03 closes once 88.3's logins passed"
requirements: [WIN-02, WIN-02-A, WIN-02-B, VER-02-J, WIN-05]
---

# Phase 88 Plan 03: Win11 VM UAT (AUMID + Upgrade Cleanup + Golden-Path + AAC) Summary

## One-Liner

Closes the VM-only half of Phase 88: this `checkpoint:human-verify` plan authored `88-HUMAN-UAT.md` (the executable Win11 VM UAT script), and the consolidated VM session was run by hand and recorded `8/8 PASS, 0 blocked` in `88-UAT.md` (status: resolved, 2026-06-13).

## What Was Built / Verified

This is an `autonomous: false` plan whose single task was a `checkpoint:human-verify`. The agent authored the UAT script on Linux; the human executed it on a Win11 VM across one consolidated session (Option C), covering Phase 88 plus the inserted fix phases 88.1, 88.2, and 88.3.

VM UAT outcome (per `88-UAT.md`, status `resolved`, summary `passed: 8, issues: 0, blocked: 0`):

| # | Test | Requirement | Result |
|---|------|-------------|--------|
| 1 | build.ps1 + step-4c/4d smoke guards | WIN-02 / VER-02-J | PASS (after `pip install -e ".[windows]"` re-synced the pywinrt 3.x split dists; guards correctly caught the missing dep pre-ship) |
| 2 | check_bundle_plugins exit-10 guard (UAT-15/16) | WIN-05 | PASS (exit 10 PHASE-69 FAIL on renamed gstlibav.dll; exit 0 after restore) |
| 3 | Install + dist-info cleanup (UAT-17/1b) | WIN-02-A / VER-02-J | PASS (exactly one `musicstreamer-2.2.86.dist-info`, one Start-Menu `.lnk` — G1 [InstallDelete] fix confirmed) |
| 4 | SMTC overlay shows "MusicStreamer" (UAT-3) | WIN-02 | PASS (G2 winrt collect_all + AUMID identity confirmed) |
| 5 | Hardware media keys (UAT-7) | WIN-02 | PASS (play/pause + stop functional on frozen bundle) |
| 6 | GBS.FM in-app login + playback (UAT-10) | VER-02-J | PASS (resolved via Phase 88.3 B1 isolated oauth_helper.exe) |
| 7 | Twitch login (UAT-10b) | VER-02-J | PASS (resolved via 88.3 + PySide6 6.11.0 Chromium bump clearing Kasada) |
| 8 | Google/YouTube login (UAT-10c) | VER-02-J | PASS (resolved via 88.3 isolated helper) |

## Acceptance Criteria Verification

| Success Criterion | Result |
|-------------------|--------|
| SC1 WIN-02 — installed `.lnk` AUMID = `org.lightningjim.MusicStreamer` + SMTC "MusicStreamer" overlay | PASS (tests 3, 4) |
| SC2 WIN-02-A — upgrade deletes old `.lnk` before creating new one | PASS (test 3) |
| SC3 WIN-02-B — live `.lnk` AUMID equals the static parity-test literal | PASS (test 3) |
| SC4 VER-02-J — full golden-path UAT incl. media keys, AAC, GBS.FM logins | PASS (tests 4–8) |
| SC5 WIN-05 — DI.fm/AudioAddict/SomaFM AAC tiers audible + exit-10 guard fires | PASS (tests 1, 2) |

## Deviations from Plan

The originally-planned QtWebEngine OAuth logins (tests 6/7/8) failed at the first VM pass with a NEW gap (G6: `oauth_helper.py` module-level `QtWebEngineWidgets` import → `sys.exit(2)` because the frozen bundle shipped no QtWebEngine). Rather than block Phase 88 indefinitely, the gap was carved out to inserted **Phase 88.3** (B1 isolated-helper architecture). 88-03 was held until 88.3's logins passed; all three then flipped to PASS (see `88.3-UAT.md`, G6-T6/T7/T8).

## Known Stubs

None. All 8 UAT rows are PASS; all three documented gaps are `status: resolved`.

## Self-Check: PASSED

- `88-HUMAN-UAT.md` authored (the executable VM script). ✓
- `88-03-CONSOLIDATED-VM-UAT.md` runner authored for the Option-C single session. ✓
- `88-UAT.md` records the resolved outcome (8/8 PASS). ✓

Evidence commits:
- fb3d9a43: docs(88): consolidated VM UAT — close G1/G2/G5, insert 88.3 for G6 (QtWebEngine)
- 4b012672: docs(phase-88): resolve UAT gaps (tests 6/7/8) after 88.3 gap closure
