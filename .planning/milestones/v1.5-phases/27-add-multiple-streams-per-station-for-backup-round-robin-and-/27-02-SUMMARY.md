---
phase: 27-add-multiple-streams-per-station-for-backup-round-robin-and-
plan: "02"
subsystem: ui-streams-editor
tags: [gtk4, adwaita, streams, edit-dialog, quality-presets]
dependency_graph:
  requires: [27-01]
  provides: [ManageStreamsDialog, manage-streams-button, quality-constants]
  affects: [edit_dialog, constants, ui-streams]
tech_stack:
  added: [ManageStreamsDialog, QUALITY_PRESETS constant]
  patterns: [Adw.Window sub-dialog, inline add/edit form, lazy import]
key_files:
  created:
    - musicstreamer/ui/streams_dialog.py
  modified:
    - musicstreamer/constants.py
    - musicstreamer/ui/edit_dialog.py
decisions:
  - "Up/Down buttons used for stream reorder (simpler than drag-and-drop in GTK4 ListBox)"
  - "Inline form at bottom of ManageStreamsDialog (no nested dialog needed)"
  - "_on_fetch_clicked reads first stream from DB (no url_entry in editor anymore)"
  - "on_changed callback fires on both Save and dialog close to keep count label fresh"
metrics:
  duration: "~12 min"
  completed: "2026-04-09T11:56:20Z"
  tasks_completed: 1
  files_modified: 3
requirements: [STR-09, STR-10, STR-11]
---

# Phase 27 Plan 02: Manage Streams UI Summary

**One-liner:** ManageStreamsDialog with add/edit/delete/reorder streams plus QUALITY_PRESETS constants; URL entry replaced by Manage Streams button in station editor.

## What Was Built

- `QUALITY_PRESETS = ("hi", "med", "low")` and `QUALITY_SETTING_KEY = "preferred_quality"` added to `constants.py`
- New `musicstreamer/ui/streams_dialog.py`: `ManageStreamsDialog(Adw.Window)` with:
  - `Gtk.ListBox` of `Adw.ActionRow` rows showing stream label/URL, quality badge, codec
  - Per-row Up/Down reorder buttons (first row Up insensitive, last row Down insensitive)
  - Per-row Edit (pencil) and Delete (trash) buttons
  - Inline add/edit form in a `Gtk.Frame` with URL, label, quality dropdown (hi/med/low/custom + custom text entry), stream type dropdown, codec entry
  - Save validates non-empty URL; inserts new or updates existing stream
  - `on_changed` callback fires after save and on dialog close
- `edit_dialog.py` updated:
  - `self.url_entry` removed entirely
  - URL focus-out controller removed; `_on_url_focus_out` removed
  - URL form row replaced with "Manage Streams…" button + stream count label (`{n} streams configured`)
  - `_on_manage_streams` opens `ManageStreamsDialog` with `on_changed=self._update_stream_count`
  - `_update_stream_count` calls `repo.list_streams` and updates label
  - `_on_fetch_clicked` reads `streams[0].url` from DB instead of `url_entry`
  - `_on_aa_key_confirmed` reads `streams[0].url` from DB
  - `_save` no longer touches stream table (streams managed via sub-dialog)

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | b086a6f | feat(27-02): add ManageStreamsDialog and replace URL entry with Manage Streams button |

## Checkpoint: Awaiting Human Verify

Task 2 is a `checkpoint:human-verify` — functional verification of the Manage Streams dialog is required before this plan is considered fully complete. See 27-02-PLAN.md Task 2 for the 13-point checklist.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all stream data reads from and writes to SQLite via repo methods.

## Threat Flags

None — all form inputs flow through parameterized SQL via repo methods (T-27-04 mitigated).

## Self-Check: PASSED

- musicstreamer/ui/streams_dialog.py: FOUND (contains ManageStreamsDialog)
- musicstreamer/constants.py: FOUND (contains QUALITY_PRESETS, QUALITY_SETTING_KEY)
- musicstreamer/ui/edit_dialog.py: FOUND (contains Manage Streams button, no url_entry)
- Commit b086a6f: FOUND in git log
- Imports verified: `from musicstreamer.ui.streams_dialog import ManageStreamsDialog` — OK
