---
phase: 06-station-management
plan: "02"
subsystem: ui
tags: [edit-dialog, delete, icy-toggle, youtube-thumbnail, tdd]
dependency_graph:
  requires: [06-01]
  provides: [delete-station-ui, icy-disabled-ui, yt-thumbnail-fetch-ui]
  affects: [musicstreamer/ui/edit_dialog.py]
tech_stack:
  added: []
  patterns: [daemon-thread-callback, GLib.idle_add, Gtk.Stack, Adw.SwitchRow, Adw.MessageDialog]
key_files:
  created:
    - tests/test_yt_thumbnail.py
  modified:
    - musicstreamer/ui/edit_dialog.py
decisions:
  - "fetch_yt_thumbnail uses GLib.idle_add wrapper so callbacks always run on GTK main thread"
  - "Gtk.Stack (pic/spinner) used in arts grid to avoid re-parenting station_pic during fetch"
  - "Adw.SwitchRow appended to content Box (not Grid) since it is a ListBoxRow subclass"
  - "_fetch_cancelled flag on close-request guards against widget updates after dialog close"
metrics:
  duration: "2 minutes"
  completed: "2026-03-21"
  tasks_completed: 2
  tasks_total: 3
  files_changed: 2
---

# Phase 06 Plan 02: EditStationDialog — Delete, ICY Toggle, YT Thumbnail Summary

EditStationDialog now supports station deletion with confirmation/playing-guard, per-station ICY metadata disable toggle persisted to DB, and automatic YouTube thumbnail fetch via yt-dlp with spinner feedback.

## Tasks Completed

| # | Task | Commit | Status |
|---|------|--------|--------|
| 1 | YouTube thumbnail fetch helper + tests (TDD) | c9967ca (RED: c2fe612, GREEN: c9967ca) | Done |
| 2 | EditStationDialog — delete button, ICY toggle, YT fetch wiring | 6176f27 | Done |
| 3 | Verify all three features end-to-end | — | Awaiting human verification |

## What Was Built

### Task 1: fetch_yt_thumbnail + _is_youtube_url

Module-level helpers added to `edit_dialog.py`:

- `_is_youtube_url(url)` — checks for youtube.com / youtu.be
- `fetch_yt_thumbnail(url, callback)` — runs yt-dlp in daemon thread, downloads thumbnail via urllib, calls callback via `GLib.idle_add` with temp file path (or None on failure)

4 unit tests in `tests/test_yt_thumbnail.py` covering success, empty output, subprocess error, and URL detection. All mock subprocess.run and urlopen.

### Task 2: EditStationDialog wiring

**Delete Station (MGMT-01):**
- "Delete Station" button in header bar (destructive-action, pack_start)
- Blocked when `is_playing()` returns True — shows "Cannot Delete Station" Adw.MessageDialog
- Confirmed delete: Adw.MessageDialog with "Keep Station" / "Delete" responses (Delete is DESTRUCTIVE appearance)
- On confirm: calls `repo.delete_station`, triggers `on_saved`, closes dialog

**ICY Metadata Toggle (ICY-01):**
- `Adw.SwitchRow(title="Disable ICY metadata")` appended to content Box between form and separator
- Initialized from `station.icy_disabled`
- `_save` passes `icy_disabled=self.icy_switch.get_active()` to `repo.update_station`

**YouTube Thumbnail Fetch (MGMT-02):**
- `Gtk.EventControllerFocus` on url_entry triggers fetch on focus-leave if URL is YouTube
- "Fetch from URL" button at arts grid row 3 triggers manual fetch
- `Gtk.Stack` wraps station_pic and a `Gtk.Spinner` — stack switches to "spinner" during fetch, back to "pic" on completion
- Race guard: `_fetch_in_progress` flag prevents concurrent fetches
- Close guard: `_fetch_cancelled` set on close-request prevents widget updates after dialog close
- On success: copies thumbnail via `copy_asset_for_station`, refreshes picture, deletes temp file

## Decisions Made

- `GLib.idle_add` wraps callback in `fetch_yt_thumbnail` so callers never need to wrap themselves — same decision as cover_art.py but applied inside the helper rather than at call site.
- `Gtk.Stack` used rather than removing/re-parenting `station_pic` to avoid GTK widget tree errors.
- `Adw.SwitchRow` cannot go in `Gtk.Grid` (it is a `Gtk.ListBoxRow` subclass) — appended to the content `Gtk.Box` between form and separator instead.
- `_fetch_cancelled` flag (not `is_realized()` check) used for close guard — simpler and avoids GTK version differences.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

Pending (to be verified after human-verify checkpoint).
