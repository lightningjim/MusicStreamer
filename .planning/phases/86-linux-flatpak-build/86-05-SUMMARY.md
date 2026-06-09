---
phase: 86-linux-flatpak-build
plan: "05"
subsystem: linux-packaging
tags: [flatpak, human-uat, in-sandbox, mpris2, qtwebengine, aac, gnome-software]
dependency_graph:
  requires: ["86-01", "86-02", "86-03", "86-04"]
  provides: ["86-VERIFICATION.md"]
  affects: ["io.github.kcreasey.MusicStreamer.yaml", "musicstreamer/mpris2.py", "flatpak-requirements.txt"]
tech_stack:
  added: []
  patterns: ["human-UAT-evidence-bundle", "single-host-Wayland-GNOME", "in-sandbox-runtime-verification"]
key_files:
  created:
    - .planning/phases/86-linux-flatpak-build/86-VERIFICATION.md
  modified:
    - io.github.kcreasey.MusicStreamer.yaml
    - flatpak-requirements.txt
    - python3-modules.yaml
    - tools/linux-flatpak/build.sh
    - tests/test_packaging_linux_spec.py
decisions:
  - "Classified the initial BUILD_FAIL as environmental (system flatpak-builder absent → rofiles-fuse fallback bug), not a manifest defect — installed system flatpak-builder rather than patching the verified driver"
  - "SC5 import-wizard FAIL was a genuine app-logic defect (wizard unwired + migration auto-copy in sandbox) → spun out to follow-up phase 86.1 rather than patching inline"
  - "Six runtime-only packaging defects (invisible to the 52 automated tests) fixed in commit 477367a1 to reach a working in-sandbox bundle"
metrics:
  duration: "human UAT session"
  completed: "2026-06-05"
  tasks_completed: 2
  files_changed: 5
---

# Phase 86 Plan 05: In-Sandbox UAT Evidence Bundle Summary

Built, installed, and ran the signed `.flatpak` on the native Wayland GNOME dev rig and captured the empirical evidence bundle (`86-VERIFICATION.md`) for the five capabilities that no automated test can cover. **SC1–SC4 PASS**; SC5 (first-launch import offer) initially FAILED on two app-logic defects and was **resolved via follow-up phase 86.1** (human UAT 3/3 PASS, 2026-06-05). Reaching a working in-sandbox bundle required fixing **6 packaging/manifest defects** that only surface at runtime inside the sandbox, plus one environmental issue.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Build + install signed `.flatpak` on the rig (after env fix + 6 runtime defect fixes) | 477367a1, 8918c98c, cc923399 | `io.github.kcreasey.MusicStreamer.yaml`, `flatpak-requirements.txt`, `python3-modules.yaml`, `build.sh` |
| 2 | Capture SC1–SC5 evidence bundle | 409e0731 | `.planning/phases/86-linux-flatpak-build/86-VERIFICATION.md` |

## Verification Results

| SC | Capability | Requirement | Result |
|----|-----------|-------------|--------|
| SC1 | Install / launch + GNOME Software listing | PKG-LIN-FP-02 (D-11) | ✅ PASS |
| SC2 | AAC audible via ffmpeg-full | PKG-LIN-FP-07 | ✅ PASS (`avdec_aac` present, streams audible) |
| SC3 | GBS.FM QtWebEngine login + cookie persistence | PKG-LIN-FP-05 (D-12) | ✅ PASS (no namespace error; persists across quit) |
| SC4 | MPRIS2 media-key control | PKG-LIN-FP-08 (D-10) | ✅ PASS (`busctl` shows short lowercase `org.mpris.MediaPlayer2.musicstreamer`) |
| SC5 | First-launch import offer | PKG-LIN-FP-06 (functional) | ❌ FAIL → **RESOLVED via phase 86.1** (3/3 PASS 2026-06-05) |

Evidence transcripts, in-sandbox pre-checks, and screenshot references recorded in `86-VERIFICATION.md` (status: `human_completed`).

## Deviations from Plan

The plan assumed an automatable build → straight to evidence capture. In practice the UAT session uncovered defects invisible to the 52 automated tests, requiring iterative fix-and-rebuild before evidence could be captured:

- **6 runtime/packaging defects fixed** (commit `477367a1` + `8918c98c` + `cc923399`):
  1. `python3-pillow` removed (unused; sdist broke `--no-build-isolation` build)
  2. `musicstreamer` module: added `--no-build-isolation` (network-less build sandbox)
  3. `appstreamcli` gate: `--no-net` for local `SKIP_SIGN=1` builds (unpublished metainfo URLs)
  4. SC4 MPRIS2 name case mismatch — manifest `--own-name` corrected to lowercase `musicstreamer`; drift guard now cross-checks against source `SERVICE_NAME`
  5. SC3 `QTWEBENGINEPROCESS_PATH=/app/bin/QtWebEngineProcess` env added (BaseApp/runtime path divergence)
  6. SC1 desktop integration — `.desktop`/metainfo/pre-rendered icons (128/256/512) installed into `/app/share` + drift guard
- **SC5 deferred to a follow-up phase (86.1)** rather than patched inline — root cause was two coupled app-logic defects (wizard never wired into startup; `migration.run_migration()` auto-copies host data in the `:ro`-mounted sandbox without consent), warranting its own plan + tests.

## Key Technical Decisions

### Environmental BUILD_FAIL, not a defect
The initial build died at `rofiles-fuse` setup (`file descriptor 4 is not a socket`, exit 256). Diagnosed as environmental: the system `flatpak-builder` was absent, so `build.sh:51-54` fell back to `flatpak run org.flatpak.Builder`, whose nested sandbox can't pass the FUSE fd. Fixed by installing the system `flatpak-builder` (zero code change) rather than patching `--disable-rofiles-fuse` into the verified driver. A second environmental snag — `onedrive --monitor` grabbing rofiles-overlay files and blocking unmount — was resolved by pausing OneDrive sync for the build.

### SC5 → phase 86.1 instead of inline patch
The import-wizard failure was a real privacy-relevant defect (host secrets silently copied into the sandbox), not a packaging issue. Spinning it into phase 86.1 kept the SC5 fix properly planned, threat-modeled, and test-covered. Phase 86.1 is complete with its own human UAT passing 3/3.

## Known Stubs

None. The evidence bundle is complete and the one open item (SC5) has been resolved in a separate, completed phase.

## Threat Flags

No new security surface introduced by the UAT itself. The SC5 finding surfaced a privacy concern (unconsented secret copy in-sandbox) that phase 86.1 mitigated via sandbox-aware migration (`is_sandboxed()` skip) and a consent-gated, offer-once import wizard.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `86-VERIFICATION.md` (status: human_completed) | FOUND |
| `86-05-SUMMARY.md` | FOUND |
| Commit 477367a1 (runtime defect fixes) | FOUND |
| Commit 409e0731 (UAT results recorded) | FOUND |
| Phase 86.1 SC5 resolution (b048d34d, 3/3 PASS) | FOUND |
| Artifact MusicStreamer-2.1.84.flatpak | FOUND |
