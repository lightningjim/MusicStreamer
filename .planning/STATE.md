---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: OS-Agnostic Revamp
status: executing
stopped_at: Phase 39 UAT complete, fixes applied
last_updated: "2026-04-13T15:49:45.116Z"
last_activity: 2026-04-13
progress:
  total_phases: 10
  completed_phases: 5
  total_plans: 20
  completed_plans: 20
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-10)

**Core value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.
**Current focus:** Phase 37 — Station List + Now Playing

## Current Position

Phase: 40
Plan: Not started
Status: Ready to execute
Last activity: 2026-04-13

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 63 (v1.0–v1.5 combined)
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

### Pending Todos

- .planning/notes/2026-03-21-sdr-live-radio-support.md
- .planning/notes/2026-03-21-sync-config-between-computers.md
- .planning/notes/2026-03-20-icy-override-per-station.md

### Blockers/Concerns

- Phase 43 (GStreamer Windows Spike) must complete before Phase 44 can be planned — spike results determine exact PyInstaller spec
- Phase 41 (SMTC on Windows): winrt async pattern for button_pressed needs real Windows validation before planning
- Phase 40 (OAuth): QWebEngineCookieStore.cookieAdded in subprocess context needs proof-of-concept before planning

## Session Continuity

Last session: 2026-04-13T15:49:45.113Z
Stopped at: Phase 39 UAT complete, fixes applied
Resume file: .planning/phases/39-core-dialogs/39-UAT.md
