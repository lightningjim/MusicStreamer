---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: OS-Agnostic Revamp
status: executing
stopped_at: Phase 47 context gathered (bitrate-only after split)
last_updated: "2026-04-18T03:00:21.878Z"
last_activity: 2026-04-18
progress:
  total_phases: 19
  completed_phases: 11
  total_plans: 40
  completed_plans: 40
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-10)

**Core value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.
**Current focus:** Phase 46 — UI polish

## Current Position

Phase: 47
Plan: Not started
Status: Executing Phase 46
Last activity: 2026-04-18

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 75 (v1.0–v1.5 combined)
- Average duration: ~14 min/plan
- Total execution time: ~12 hours

**Recent Trend:**

- Last milestone (v1.5): 21 plans across 14 phases
- Trend: Stable

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
- [Phase 35]: KEEP_MPV: cookie-protected YouTube path fails through yt-dlp library API; mpv subprocess fallback retained for _play_youtube() in Plan 35-04
- [Phase 35]: Plan 35-02: PEP 562 __getattr__ shim in constants.py preserves backward compat for DATA_DIR/DB_PATH/etc. — re-evaluates paths.* on every access so paths._root_override monkeypatching works
- [Phase 35]: Spike branch KEEP_MPV: cookie-protected YouTube live fails on yt_dlp library + cookiefile, mpv subprocess retained
- [Phase 36]: icons.qrc uses file alias attributes so resources resolve at :/icons/<name>.svg (pyside6-rcc otherwise nests prefix + file path)
- [Phase 36]: Move function-local urllib.parse import to module level in url_helpers.py (only non-verbatim extraction change)
- [Phase 36]: Delete test_fetch_aa_logo tests in Plan 36-02 alongside test_fetch_yt_thumbnail — both rely on GLib patches that die with ui/ deletion in 36-03; Phase 39 rebuilds with Qt signals
- [Phase 36]: Atomic GTK cutover: deleted musicstreamer/ui/, mpris.py, test_mpris.py, and stale build/ artifact in a single commit. No ripple fixes required thanks to 36-02 url_helpers extraction.
- [Phase 41]: NotImplementedError over abc.ABCMeta for QObject subclasses (PySide6 metaclass constraint)
- [Phase 41-platform-media-keys]: publish_metadata(None) placed before set_playback_state('stopped') so MPRIS clients see cleared metadata before stopped state
- [Phase 41-platform-media-keys]: logging.basicConfig in main() only — not duplicated in _run_smoke or _run_gui

### Roadmap Evolution

- Phase 45 added: Unify station-icon loader (note: original add-phase op reported 46; retired placeholder freed slot 45 at commit time) — completed 2026-04-14
- Phase 46 added: UI polish — theme tokens + logo status cleanup (from 40.1 + 45 UI-REVIEW findings) — 2026-04-14
- Phase 47 added: Stats for nerds + AutoEQ import — harvests SEED-005 (buffer indicator) + SEED-007 (AutoEQ profile import) — 2026-04-14
- Phase 41 narrowed: scope restricted to Linux Media Keys (MPRIS2 via QtDBus); MEDIA-03 + Windows slice of MEDIA-04/05 split out — 2026-04-14
- Phase 43.1 inserted: Windows Media Keys (SMTC), depends on Phase 41 (factory) + Phase 43 (runtime); requires live Windows VM validation — 2026-04-14
- Phase 44 success criteria amended: added Phase 42 Linux↔Windows settings-export round-trip UAT — 2026-04-14
- Phase 48 added: Fix AudioAddict listen key not persisting to DB (surfaced by Phase 42 UAT test 7; skipped as out-of-scope) — 2026-04-17

### Pending Todos

- .planning/notes/2026-03-21-sdr-live-radio-support.md
- .planning/notes/2026-03-21-sync-config-between-computers.md
- .planning/notes/2026-03-20-icy-override-per-station.md

### Blockers/Concerns

- Phase 43 (GStreamer Windows Spike) must complete before Phase 44 can be planned — spike results determine exact PyInstaller spec
- Phase 41 (SMTC on Windows): winrt async pattern for button_pressed needs real Windows validation before planning
- Phase 40 (OAuth): QWebEngineCookieStore.cookieAdded in subprocess context needs proof-of-concept before planning

## Session Continuity

Last session: 2026-04-18T03:00:21.875Z
Stopped at: Phase 47 context gathered (bitrate-only after split)
Resume file: .planning/phases/47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame/47-CONTEXT.md
