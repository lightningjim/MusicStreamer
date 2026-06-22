---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: Package Building and QOL features/tweaks
status: executing
stopped_at: Phase 96.1 context gathered
last_updated: "2026-06-22T03:30:40.033Z"
last_activity: 2026-06-22 -- Phase 96.1 execution started
progress:
  total_phases: 24
  completed_phases: 22
  total_plans: 80
  completed_plans: 78
  percent: 92
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-25)

**Core value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.
**Current focus:** Phase 96.1 — Show currently-live stream titles for newly-discovered streams

## Current Position

Phase: 96.1 (Show currently-live stream titles for newly-discovered streams) — EXECUTING
Plan: 2 of 3
Status: Executing Phase 96.1
Last activity: 2026-06-22 -- Phase 96.1 execution started

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
- Phase 93 (CONDITIONAL): BUFFER-MONITOR Follow-Up — ✅ FIRED + closed 2026-06-15 (deviation close)

Tier 8 (post-roadmap additions):

- Phase 94: Sidebar Logo Thumbnail Optimization
- Phase 95: YT URL-Change Replay Bug (post-edit "stream exhausted" on first play)

## Performance Metrics

**Velocity:**

- Total plans completed: 245+ (v1.0–v2.1 combined)
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
- Phase 90b (SomaFM fix) is a CONDITIONAL placeholder — exists in the roadmap but only fires on trigger
- Phase 93 (BUFFER-MONITOR) was CONDITIONAL — condition FIRED (all 3 triggers, 05-24→06-07 window); closed 2026-06-15 via deviation: YouTube live-edge starvation fixed out-of-band (commit f716f083, DVR seek), SomaFM/network residual closed as no-action. See 93-VERIFICATION.md

(Phase-level decisions accumulate as phases close; v2.1 phase decisions preserved below.)

- [Phase ?]: Lazy imports for flatpak_first_launch, paths, FlatpakImportWizard, and QTimer inside _run_gui keep _run_smoke Qt-light (D-05/D-24)
- [Phase ?]: QTimer.singleShot(0, _maybe_offer_import) defers wizard modal until event loop start so it renders over shown MainWindow
- [Phase ?]: Legacy 2-arg callers use original load_path behavior when on_thumb_needed=None to preserve existing test contracts
- [Phase ?]: 89-02 Phase 89 Plan 02
- [Phase ?]: Phase 89-05
- [Phase ?]: Phase 89-05
- [Phase 89.1 Plan 01]: Backfill guards provider_id and channel_avatar_path column presence before running SQL (avoids OperationalError on legacy test-fixture schemas)
- [Phase 89.1 Plan 01]: Same-file skip in backfill: when station_id == provider_id, abspath comparison skips copy but DB UPDATE still runs (file already provider-keyed)
- [Phase 89.1 Plan 01]: Cleanup pass excludes rows where s.channel_avatar_path == p.avatar_path to prevent deleting the newly-written provider file
- [Phase 89.1 Plan 02]: bind_station uses os.path.isfile guard on provider_avatar_path before _set_avatar_pixmap_from_path (D-06 / T-89.1-05)
- [Phase 89.1 Plan 02]: D-07 reuse gate placed inside the YouTube URL branch of _on_url_timer_timeout; controlled by _force_avatar_refresh instance flag (D-08)
- [Phase 89.1 Plan 02]: _on_refresh_avatar_clicked uses try/finally to guarantee _force_avatar_refresh resets to False after D-08 bypass
- [Phase ?]: Bearer token scoped to Helix Request object only (T-89b-01); late import of twitch_helix in yt_import avoids import cycle
- [Phase 89B Plan 02]: Registry dispatch by URL sniff in _AvatarFetchWorker.run(): "twitch.tv" → "twitch" key, else "youtube"; node_runtime only for YouTube path (Pitfall 1)
- [Phase 89B Plan 02]: Single is_avatar_url gate in _on_url_timer_timeout covers YouTube+Twitch with single provider_id-None guard (Pitfall 7 compliance)
- [Phase 89B Plan 02]: blank-provider guard (not provider_name) enforces D-04: manual providers never overwritten by Twitch: login derivation in _on_save
- [Phase ?]: [Phase 89B Plan 03]: Add-path avatar fetch is SYNCHRONOUS (not async _AvatarFetchWorker) — accept() teardown disconnects the finished signal before the queued slot fires, so a pre-accept async fetch never persists
- [Phase ?]: [Phase 89B Plan 03]: _on_save refreshes self._station.provider_id/provider_name after ensure_provider for both derived-Twitch and manual cases; the sync helper provider_id None-check is a distinct call site, not a duplicate of the line-1331 Pitfall-7 guard
- [Phase ?]: Phase 89c Plan 02
- [Phase ?]: Phase 89c Plan 02
- [Phase ?]: Phase 95: invalidate_for_edit reuses Player.play(station) for the D-01 restart — no hand-rolled queue reset
- [Phase ?]: Phase 95: edit URL-change detection compares stored StationStream.url .strip(), never the resolved playbin3 URI
- [Phase ?]: Phase 95: youtube_resolved widened to Signal(str, bool, int); _youtube_resolve_seq guard no-ops stale YT resolutions
- [Phase ?]: Phase 999.1 Plan 01: extended BadZipFile except scope to cover member-read site
- [Phase ?]: Phase 96 D-04/D-09/D-10: provider_refresh_requested signal + node_runtime threading wired end-to-end; human-verified with real YBC channel

### Decisions (v2.1, preserved for context)

(Truncated — full v2.1 decision log preserved at `.planning/milestones/v2.1-ROADMAP.md`.)

### Roadmap Evolution

- 2026-05-25: v2.2 roadmap created. 14 phases mapping 62 requirements (61 unconditional + 1 conditional). Phase numbering continues from v2.1's Phase 84. Tier-ordered build: Tier 1 spike + FIX-MPRIS parallel; Tier 2 Linux packaging build; Tier 3 Windows bundle; Tier 4 channel-avatar; Tier 5 GBS polish; Tier 6 SomaFM; Tier 7 carry-overs. Research-flag YES for Phases 85a, 86, 87, 89.
- 2026-05-25: Phase 94 added — Sidebar logo thumbnail optimization. Investigate sidebar scroll slowdown on large lists (DI.fm cited); hypothesis is that full-resolution station logos are being scaled per-paint. If confirmed, generate pre-scaled small thumbnails for sidebar while preserving full-res for Now Playing. Originally landed in directory as Phase 93 via `phase.add`; manually renumbered to 94 because Phase 93 was already taken by CONDITIONAL BUFFER-MONITOR (no directory existed yet, so SDK didn't detect the clash).
- 2026-05-25: Phase 95 added — YT URL-change replay bug. After editing a YouTube stream whose URL has changed, first play after save fails with "stream exhausted"; replaying picks up the new URL successfully. Suggests stale resolved-URL cache or pipeline state surviving the station-edit save path. Diagnose and invalidate the cached state on update.
- Phase 86.1 inserted after Phase 86: SC5 failure followup from phase 86 (URGENT)
- 2026-06-06: Phase 96 added — Manual refresh of Yellow Brick Cinema provider with what is actually live on their channel (@YellowBrickCinema). Add the ability to manually re-sync the YBC provider against the channel's currently-live streams.
- 2026-06-19: Phase 97 added — Resolve station URL duplication between the top-level "standard URL" (originally THE stream URL, now used for fetching/metadata) and the first StationStream URL. The two are expected to always be identical, so the same URL is maintained in two places and forces duplicate edits (surfaced during Phase 95 YT URL-edit work). Investigate the data model + edit flow and unify to a single source of truth.
- Phase 88.1 inserted after Phase 88: Fix SMTC media overlay absent + dead media keys on bundled Windows build (Phase 88 UAT G2) (URGENT)
- Phase 88.2 inserted after Phase 88: Fix GBS.FM in-app login dialog fails to start (Phase 88 UAT G3) (URGENT)
- Phase 88.3 inserted after Phase 88: Bundle QtWebEngine in frozen Windows build — OAuth helper crashes exit 2 (oauth_helper.py module-level QtWebEngineWidgets import) because QtWebEngine is not in the musicstreamer-build env nor bundled in MusicStreamer.spec. New gap exposed after 88.2 fixed the launcher. Phase 88 UAT G6/G3-bis (UAT-10 GBS + Twitch + Google all crash). Fix: provision PySide6-Addons/qt6-webengine + explicit WebEngine collect in spec + deepen step-4d guard. (URGENT)
- Phase 87.1 inserted after Phase 87: GBS.FM session-expiry re-login prompt — surface GbsAuthExpiredError as a re-login affordance instead of silent playlist-load failure (user-reported symptom 2026-06-12; planned feature, GBS cluster, reusable by 87 marquee + 87b)
- Phase 89c inserted after Phase 89b: Provider brand-avatar cover-slot fallback (SomaFM, AudioAddict) — distinct brand avatar when per-track art resolution is exhausted, trigger is resolution-exhausted not icy_disabled (URGENT)
- Phase 89.1 inserted after Phase 89: Re-key channel avatar from per-station to per-provider (channel) — dedupe fetch + storage across sibling YT streams of the same channel (URGENT)
- Phase 96.1 inserted after Phase 96: Show currently-live stream titles for newly-discovered streams in the live-refresh dialog so they can be mapped/merged (URGENT)

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
| verification | Phase 84 — 2-week buffer-events.log monitor window | ✅ Closed — Phase 93 (deviation close, 2026-06-15) |
| verification | Phase 65 VER-02-J — Win11 VM bundled-exe end-to-end | In v2.2 — Phase 88 |
| seed | SEED-009 — Linux AppImage install | In v2.2 — Phases 85a + 85 |
| todo | 2026-05-10-pls-codec-bitrate-url-fallback | In v2.2 — Phase 92 |
| Phase 86.1 P02 | 1 | 2 tasks | 2 files |
| Phase 88 P02 | 104 | 2 tasks | 1 files |
| Phase 88.3 P01 | 5m | 2 tasks | 5 files |
| Phase 94-optimize-sidebar-logo-loading-with-pre-scaled-thumbnails-for P02 | 22m | 2 tasks | 1 files |
| Phase 94 P03 | 26 | 2 tasks | 2 files |
| Phase 89 P02 | 2m | 2 tasks | 2 files |
| Phase 89 P05 | 22 | 2 tasks | 2 files |
| Phase 89B-twitch-channel-avatar-fetch P01 | 2m | 2 tasks | 3 files |
| Phase 89B P03 | 8m | 3 tasks | 2 files |
| Phase 89c P02 | 8m | 1 tasks | 2 files |
| Phase 87.1 P04 | 211 | 3 tasks | 3 files |
| Phase 90-somafm-preroll-instrumentation P01 | 8m | 2 tasks | 5 files |
| Phase 90 P03 | 8 | 2 tasks | 2 files |
| Phase 92-fix-pls-pls-url-fallback-for-codec-bitrate P01 | 3m | 3 tasks | 2 files |
| Phase 95 P01 | 25min | 3 tasks | 5 files |
| Phase 95 P02 | 4m | 2 tasks | 3 files |
| Phase 999.1 P02 | 6m | 2 tasks | 1 files |
| Phase 95 P03 | 3m | 2 tasks | 2 files |
| Phase 96 P03 | 10 minutes | 2 tasks | 2 files |
| Phase 96 P04 | 12 minutes | 2 tasks | 1 files |
| Phase 96 P05 | 40 | 3 tasks | 5 files |
| Phase 96.1 P01 | 8m | 2 tasks | 2 files |

## Session Continuity

Last session: 2026-06-22T03:30:40.020Z
Stopped at: Phase 96.1 context gathered
Resume file: .planning/phases/96.1-show-currently-live-stream-titles-for-newly-discovered-strea/96.1-CONTEXT.md

## Operator Next Steps

✅ Phase 88 CLOSED (2026-06-13). The consolidated Option-C Win11 VM session passed all 8 rows (`88-UAT.md` status: resolved, 0 blocked) covering Phase 88 (G1/G5), 88.1 (G2 SMTC), 88.2 (G3 OAuth-helper launch), and 88.3 (G6 QtWebEngine logins). `88-03-SUMMARY.md` written 2026-06-16 to close the plan-without-summary bookkeeping gap; ROADMAP progress table 88 → 4/4 Complete.

Next: advance v2.2 phase work via `/gsd:next` (Phase 89 YT Channel-Avatar has context gathered and is ready to plan).
