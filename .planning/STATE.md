---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Discovery & Favorites
status: Defining requirements
stopped_at: ~
last_updated: "2026-03-27T00:00:00.000Z"
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.
**Current focus:** v1.2 complete — planning next milestone

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-03-27 — Milestone v1.3 started

## Performance Metrics

**Velocity:**

- Total plans completed: 10 (v1.0 + v1.1)
- Average duration: ~30 min
- Total execution time: ~5 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 05-display-polish P01 | 1 | 10m | 10m |
| 05-display-polish P02 | 1 | 3m | 3m |
| 06-station-management P01 | 1 | 3m | 3m |
| 06-station-management P02 | 1 | 45m | 45m |

**Recent Trend:**

- Last 4 plans: 10m, 3m, 3m, 45m
- Trend: Stable

*Updated after each plan completion*
| Phase 07 P01 | 525659min | 1 tasks | 3 files |
| Phase 07 P01 | 8min | 1 tasks | 3 files |
| Phase 07 P02 | 2 | 1 tasks | 1 files |
| Phase 07 P03 | 15 | 1 tasks | 1 files |
| Phase 08 P01 | 1 | 1 tasks | 2 files |
| Phase 08 P02 | 10 | 1 tasks | 1 files |
| Phase 09-station-editor-improvements P01 | 8 | 1 tasks | 1 files |
| Phase 09 P02 | 5 | 1 tasks | 1 files |
| Phase 09-station-editor-improvements P02 | 5 | 2 tasks | 1 files |
| Phase 10 P01 | 1 | 1 tasks | 2 files |
| Phase 10-now-playing-audio P02 | 4 | 2 tasks | 1 files |
| Phase 11-ui-polish P01 | 35 | 3 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 06]: fetch_yt_thumbnail uses GLib.idle_add inside helper so callers never wrap themselves
- [Phase 06]: Gtk.Stack swap pattern for spinner/content slot; _fetch_cancelled flag guards post-close widget updates
- [Phase 06]: ICY suppression guard in _on_title closure (UI-side), not in Player — keeps suppression tied to user intent via _current_station
- [Phase 05]: Pass raw ICY title to cover art lookup; escape only for GTK label display
- [Phase 04]: cover_stack mirrors logo_stack Gtk.Stack pattern; _last_cover_icy dedup cleared on stop
- [Phase 07]: Use strftime millisecond precision for last_played_at; datetime('now') second-level granularity caused ordering failures
- [Phase 07]: Drop set_filter_func entirely — filter_func cannot inspect ExpanderRow children added via add_row()
- [Phase 07]: ExpanderRow children use activated signal -> _play_by_id; row-activated on outer ListBox does not fire for group children
- [Phase 07]: Use Gtk.ListBox.insert(row, 0) for in-place RP refresh rather than reload_list — preserves ExpanderRow expand/collapse state
- [Phase 07]: recently_played_count configurable via settings table with default 3
- [Phase 08]: Empty set = inactive filter dimension (parallel to matches_filter None/empty string convention)
- [Phase 08]: Tag matching casefolded at call time — no mutation of input sets
- [Phase 08]: Chip x dismiss calls btn.set_active(False) — fires toggled signal, avoids double _on_filter_changed call
- [Phase 08]: _rebuilding flag wraps bulk chip mutations in _rebuild_filter_state and _on_clear to prevent spurious filter updates
- [Phase 09-station-editor-improvements]: new_provider_entry takes precedence over provider_combo on save — explicit typed value always wins
- [Phase 09-station-editor-improvements]: Case-insensitive provider dedup via casefold() prevents Soma.fm/soma.fm duplicates
- [Phase 09]: Split _fetch_in_progress into _thumb_fetch_in_progress and _title_fetch_in_progress — thumbnail and title fetches are independent
- [Phase 09]: Name guard in _on_title_fetched: only auto-populate if current name is blank or New Station
- [Phase 09]: Strip trailing date/time suffix from yt-dlp stream title output — live streams append YYYY-MM-DD HH:MM and it makes poor station names
- [Phase 10]: Store _volume as float 0.0-1.0; convert to int at mpv call site only
- [Phase 10]: mpv volume applied only at launch via --volume arg; no live IPC adjustment needed
- [Phase 10-now-playing-audio]: provider_name shown inline as 'Name · Provider' in station_name_label using U+00B7 middle dot
- [Phase 10-now-playing-audio]: volume slider default 80 (not 100) to avoid blasting on first launch; no debounce needed for local GStreamer property write
- [Phase 11-ui-polish]: 5px border-radius on now-playing-art (logo_stack, cover_stack) — slight rounding per user feedback
- [Phase 11-ui-polish]: GTK4 border-radius clipping requires set_overflow(Gtk.Overflow.HIDDEN) on the Gtk.Stack widget — CSS overflow:hidden alone does not clip child Gtk.Image paint nodes

### Pending Todos

- .planning/notes/2026-03-21-collapse-expand-radio-stations.md
- .planning/notes/2026-03-21-now-playing-show-provider.md
- .planning/notes/2026-03-21-sdr-live-radio-support.md
- .planning/notes/2026-03-21-sync-config-between-computers.md
- .planning/notes/2026-03-20-icy-override-per-station.md
- .planning/notes/2026-03-20-yt-thumbnail-station-image.md

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-03-24T23:42:00.762Z
Stopped at: Completed 11-01-PLAN.md (Phase 11 plan 01 complete)
Resume file: None
