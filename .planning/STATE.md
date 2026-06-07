---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: Package Building and QOL features/tweaks
status: executing
stopped_at: Phase 89a context gathered
last_updated: "2026-06-07T05:16:29.248Z"
last_activity: 2026-06-05 -- Phase 88 execution started
progress:
  total_phases: 16
  completed_phases: 4
  total_plans: 30
  completed_plans: 22
  percent: 25
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-25)

**Core value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.
**Current focus:** Phase 88 — Windows Packaging Bundle (WIN-02 + VER-02-J + WIN-05)

## Current Position

Phase: 88 (Windows Packaging Bundle (WIN-02 + VER-02-J + WIN-05)) — EXECUTING
Plan: 3 of 3
Status: Executing Phase 88
Last activity: 2026-06-05 -- Phase 88 execution started

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

Last session: 2026-06-07T05:16:29.235Z
Stopped at: Phase 89a context gathered
Resume file: .planning/phases/89A-channel-avatar-db-migration-storage-layout/89A-CONTEXT.md

## Operator Next Steps

- Begin Phase 85a with `/gsd:plan-phase 85a --research-phase` (spike — de-risk linuxdeploy + conda + GStreamer plugin discovery)
- Phase 91 (FIX-MPRIS) can run in parallel — `/gsd:plan-phase 91` (no research-phase flag needed)
