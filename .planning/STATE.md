---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: Package Building and QOL features/tweaks
status: verifying
stopped_at: Phase 88.2 context gathered
last_updated: "2026-06-09T22:21:09.718Z"
last_activity: "2026-06-09 -- Phase 88.1 executed: winrt collect_all bundling fix + factory diagnostics + --check-mediakeys + build.ps1 exit-11 guard + drift tests"
progress:
  total_phases: 18
  completed_phases: 6
  total_plans: 34
  completed_plans: 26
  percent: 33
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-25)

**Core value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.
**Current focus:** Phase 88.1 — fix-smtc-media-overlay-absent-and-dead-media-keys-on-bundled

## Current Position

Phase: 88.1 (fix-smtc-media-overlay-absent-and-dead-media-keys-on-bundled) — LINUX-SIDE COMPLETE (VM proof deferred to 88-03)
Plan: 2 of 2 complete (88.1-01, 88.1-02)
Status: Phase 88.1 code complete + Linux-verified (6/6 must-haves, 90 tests green, code review clean). VERIFICATION status: human_needed — 3 VM items rolled into consolidated 88-03 session (Option C).
Last activity: 2026-06-09 -- Phase 88.1 executed: winrt collect_all bundling fix + factory diagnostics + --check-mediakeys + build.ps1 exit-11 guard + drift tests

## Phase 88 Gap Disposition (from 88-HUMAN-UAT.md, 2026-06-09)

- G1 (stale dist-info → version mislabel): FIXED via 88-04 ([InstallDelete] scoped wildcard). Pending VM re-verify via UAT-17.
- G2 (SMTC overlay absent → media keys dead, fails WIN-02/VER-02-J): FIX LANDED via Phase 88.1 (Linux-side, 2026-06-09). Root cause confirmed: pywinrt 3.x ships per-namespace compiled `.pyd` modules at the `winrt/` root that `hiddenimports` alone never bundled → frozen `import winrt.*` failed → factory silently degraded to NoOp. Fix: `collect_all` for all 5 winrt distributions in MusicStreamer.spec + factory backend-selection logging + `--check-mediakeys` harness + build.ps1 step-4c smoke guard (exit 11). Pending VM re-verify in 88-03 (88.1-HUMAN-UAT.md: build smoke guard + UAT-3 + UAT-7).
- G3 (GBS.FM login won't start, fails VER-02-J): NEEDS FIX PHASE. Investigate in-app login dialog launch path.
- G4 (zip "not a valid zip"): RESOLVED — text-mode transfer corruption, not a defect. Backlog item 999.1 (friendlier import error).
- G5 (UAT-15 exit-10 guard blocked on $pluginsDir typo): VM re-run only — corrected one-shot in 88-HUMAN-UAT Evidence § UAT-15.

Consolidated VM session (close 88-03) must cover: UAT-17 (G1 re-verify), UAT-15 re-run (G5), re-test of G2 (88.1 fix — rebuild via build.ps1; step-4c smoke guard fast-fails if winrt bundling is still wrong, then UAT-3/UAT-7) + G3 (after 88.2 lands). 88-03 closes with a clean pass only then.

## v2.2 Phase Roster

Tier 1 (parallel-eligible, Week 1):

- Phase 85a: Linux Packaging Spike (research-flag YES)
- Phase 91: FIX-MPRIS

Tier 2 (sequential, Weeks 2-3):

- Phase 85: Linux Common + AppImage Build
- Phase 86: Linux Flatpak Build (research-flag YES; depends on Phase 91)

Tier 3 (Week 4):

- Phase 88: Windows Packaging Bundle (WIN-02 + VER-02-J + WIN-05)

Tier 4 (Week 5+, channel-avatar):

- Phase 89a: DB Migration + Storage Layout
- Phase 89: YT Channel-Avatar (research-flag YES; depends on 89a + 87)
- Phase 89b: Twitch Channel-Avatar (depends on 89a + 89)

Tier 5 (Week 6, GBS):

- Phase 87: GBS Marquee + Themed-Day (research-flag YES)
- Phase 87b: GBS Zero-Token Add (depends on 87)

Tier 6 (Week 7, SomaFM):

- Phase 90: SomaFM Preroll Instrumentation
- Phase 90b (CONDITIONAL): SomaFM Preroll Fix

Tier 7 (carry-overs):

- Phase 92: FIX-PLS
- Phase 93 (CONDITIONAL): BUFFER-MONITOR Follow-Up

Tier 8 (post-roadmap additions):

- Phase 94: Sidebar Logo Thumbnail Optimization
- Phase 95: YT URL-Change Replay Bug (post-edit "stream exhausted" on first play)

## Performance Metrics

**Velocity:**

- Total plans completed: 208+ (v1.0–v2.1 combined)
- Average duration: ~14 min/plan
- Total execution time: ~12 hours (carried over baseline)

**Recent Trend:**

- Last milestone (v2.1): 187 plans across 42 phases — Stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Key v2.0 decisions already settled:

- GStreamer event loop: GLib.MainLoop daemon thread + bus.enable_sync_message_emission() + Qt queued signals (not QTimer polling)
- MPRIS2: PySide6.QtDBus replaces dbus-python entirely
- OAuth: subprocess-isolated QWebEngineView (oauth_helper.py) — avoids 130MB QtWebEngine in main process startup
- Data paths: platformdirs.user_data_dir("musicstreamer") — XDG on Linux, %APPDATA% on Windows
- GTK cutover: hard cutover in Phase 36; no parallel dual-UI period

v2.2 roadmap-level decisions (2026-05-25):

- Phase numbering continues from Phase 84 (no `--reset-phase-numbers` flag); first v2.2 phase is Phase 85
- Tier 1 runs Phase 85a (Linux spike) and Phase 91 (FIX-MPRIS) in parallel — FIX-MPRIS is tests-only, no production dependency
- Flatpak (Phase 86) depends on Phase 91 because PKG-LIN-FP-08 acceptance requires the clean MPRIS2 test baseline
- Phase 87 (GBS marquee) precedes Phase 89 (YT avatar) for the cookie-persistence-cross-process pattern, even though Phase 89a (DB migration) can land earlier in parallel
- Channel-avatar precedence is locked at `ICY → iTunes → MB-CAA → channel-avatar → placeholder` — channel-avatar must NEVER short-circuit Phase 73 MB-CAA Vaporwave/niche-electronic coverage (Pitfall 8)
- Flatpak app ID locked at `io.github.kcreasey.MusicStreamer` (PKG-LIN-FP-01)
- AppImage GLIBC baseline locked at 2.35 or lower (Ubuntu 22.04 LTS); build container pinned in Phase 85a
- Phase 90b (SomaFM fix) and Phase 93 (BUFFER-MONITOR) are CONDITIONAL placeholders — they exist in the roadmap but only fire on trigger

(Phase-level decisions accumulate as phases close; v2.1 phase decisions preserved below.)

- [Phase ?]: Lazy imports for flatpak_first_launch, paths, FlatpakImportWizard, and QTimer inside _run_gui keep _run_smoke Qt-light (D-05/D-24)
- [Phase ?]: QTimer.singleShot(0, _maybe_offer_import) defers wizard modal until event loop start so it renders over shown MainWindow

### Decisions (v2.1, preserved for context)

(Truncated — full v2.1 decision log preserved at `.planning/milestones/v2.1-ROADMAP.md`.)

### Roadmap Evolution

- 2026-05-25: v2.2 roadmap created. 14 phases mapping 62 requirements (61 unconditional + 1 conditional). Phase numbering continues from v2.1's Phase 84. Tier-ordered build: Tier 1 spike + FIX-MPRIS parallel; Tier 2 Linux packaging build; Tier 3 Windows bundle; Tier 4 channel-avatar; Tier 5 GBS polish; Tier 6 SomaFM; Tier 7 carry-overs. Research-flag YES for Phases 85a, 86, 87, 89.
- 2026-05-25: Phase 94 added — Sidebar logo thumbnail optimization. Investigate sidebar scroll slowdown on large lists (DI.fm cited); hypothesis is that full-resolution station logos are being scaled per-paint. If confirmed, generate pre-scaled small thumbnails for sidebar while preserving full-res for Now Playing. Originally landed in directory as Phase 93 via `phase.add`; manually renumbered to 94 because Phase 93 was already taken by CONDITIONAL BUFFER-MONITOR (no directory existed yet, so SDK didn't detect the clash).
- 2026-05-25: Phase 95 added — YT URL-change replay bug. After editing a YouTube stream whose URL has changed, first play after save fails with "stream exhausted"; replaying picks up the new URL successfully. Suggests stale resolved-URL cache or pipeline state surviving the station-edit save path. Diagnose and invalidate the cached state on update.
- Phase 86.1 inserted after Phase 86: SC5 failure followup from phase 86 (URGENT)
- 2026-06-06: Phase 96 added — Manual refresh of Yellow Brick Cinema provider with what is actually live on their channel (@YellowBrickCinema). Add the ability to manually re-sync the YBC provider against the channel's currently-live streams.
- Phase 88.1 inserted after Phase 88: Fix SMTC media overlay absent + dead media keys on bundled Windows build (Phase 88 UAT G2) (URGENT)
- Phase 88.2 inserted after Phase 88: Fix GBS.FM in-app login dialog fails to start (Phase 88 UAT G3) (URGENT)

### Pending Todos

- .planning/notes/2026-03-21-sdr-live-radio-support.md
- .planning/notes/2026-04-03-station-art-fetching-beyond-youtube.md

### Blockers/Concerns

- Phase 85a (Linux spike) is HIGH-RISK gate: linuxdeploy-plugin-gstreamer + conda paths feasibility must be verified BEFORE Phase 85 recipe lock
- Phase 86 (Flatpak) depends on Phase 91 (FIX-MPRIS) closure for in-sandbox MPRIS verification
- Open user-input questions (from research SUMMARY.md §Open Questions): AppImage zsync update URL host, themed-day visual treatment scope (logo-only vs accent retint), zero-token wording final pick

## Deferred Items

Items acknowledged and deferred at v2.1 milestone close on 2026-05-25 (still tracked here for visibility during v2.2):

| Category | Item | Status |
|----------|------|--------|
| requirement | WIN-02 (SMTC AUMID Start-Menu shortcut) | In v2.2 — Phase 88 |
| verification | Phase 84 — 2-week buffer-events.log monitor window | In v2.2 — Phase 93 (CONDITIONAL) |
| verification | Phase 65 VER-02-J — Win11 VM bundled-exe end-to-end | In v2.2 — Phase 88 |
| seed | SEED-009 — Linux AppImage install | In v2.2 — Phases 85a + 85 |
| todo | 2026-05-10-pls-codec-bitrate-url-fallback | In v2.2 — Phase 92 |
| Phase 86.1 P02 | 1 | 2 tasks | 2 files |
| Phase 88 P02 | 104 | 2 tasks | 1 files |

## Session Continuity

Last session: 2026-06-09T21:55:25.082Z
Stopped at: Phase 88.2 context gathered
Resume file: .planning/phases/88.2-fix-gbs-fm-in-app-login-dialog-fails-to-start-phase-88-uat-g/88.2-CONTEXT.md

## Operator Next Steps

Phase 88 is held open (Option C). Before 88-03 can close with a clean VM pass:

1. ✅ DONE — G2 fix phase (88.1): SMTC winrt bundling fix landed Linux-side (collect_all 5 dists + diagnostics + `--check-mediakeys` + build.ps1 exit-11 guard). 90 tests green, code review clean. VM re-verify rolls into 88-03 (see 88.1-HUMAN-UAT.md).
2. Create the G3 fix phase (GBS.FM login won't start) — e.g. `/gsd:insert-phase 88.2` then `/gsd:plan-phase 88.2`. VER-02-J blocker. (Phase 88.2 already inserted in roadmap.)
3. After 88.2 lands, do ONE consolidated Win11 VM session re-running 88-HUMAN-UAT.md rows: UAT-17 (G1), UAT-15 (G5), UAT-3/UAT-7 (G2 — rebuild via build.ps1; step-4c smoke guard fast-fails if winrt still missing), UAT-10 (G3). Set 88-HUMAN-UAT frontmatter status: resolved when all pass, then close 88-03 and verify Phase 88.
