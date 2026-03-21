---
phase: 05-display-polish
plan: 01
subsystem: ui
tags: [bug-fix, gtk, icy, cover-art]
dependency_graph:
  requires: []
  provides: [escaped-icy-titles, station-logo-cover-default]
  affects: [musicstreamer/ui/main_window.py]
tech_stack:
  added: []
  patterns: [GLib.markup_escape_text, GdkPixbuf cover-stack]
key_files:
  created:
    - tests/test_icy_escaping.py
  modified:
    - musicstreamer/ui/main_window.py
decisions:
  - "Pass raw (unescaped) title to _on_cover_art so iTunes lookup works with literal characters"
  - "On junk ICY title simply return without resetting cover, preserving station logo"
metrics:
  duration: "~10 minutes"
  completed: "2026-03-21"
  tasks_completed: 2
  files_changed: 2
---

# Phase 05 Plan 01: Display Polish Summary

**One-liner:** GLib.markup_escape_text applied to ICY titles and station names; station logo pre-loaded into cover art slot as default before ICY art arrives.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Escape ICY track titles for safe GTK display | f888ef0 | tests/test_icy_escaping.py, musicstreamer/ui/main_window.py |
| 2 | Show station logo in cover art slot as default fallback | 517a767 | musicstreamer/ui/main_window.py |

## Deviations from Plan

None — plan executed exactly as written.

## Decisions Made

- Pass raw (unescaped) title to `_on_cover_art` so iTunes lookup receives real characters, not HTML entities.
- On junk ICY title, simply `return` without touching `cover_stack` — this preserves the station logo loaded at playback start, rather than resetting to the generic notes icon.

## Verification

- `grep -c "markup_escape_text" musicstreamer/ui/main_window.py` → 3 (station_name_label, title_label initial, _on_title)
- `grep -c "cover_stack.set_visible_child_name" musicstreamer/ui/main_window.py` → 9
- All 48 tests pass (43 pre-existing + 5 new escaping tests)

## Self-Check: PASSED
