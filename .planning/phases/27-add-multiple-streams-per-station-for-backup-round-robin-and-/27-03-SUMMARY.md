---
phase: 27-add-multiple-streams-per-station-for-backup-round-robin-and-
plan: "03"
subsystem: import-flows
tags: [aa_import, discovery_dialog, multi-quality, attach-to-existing, tdd]
dependency_graph:
  requires: [27-01]
  provides: [multi-quality-aa-import, attach-to-existing-rb-flow]
  affects: [aa_import, discovery_dialog, import_dialog, yt_import]
tech_stack:
  added: []
  patterns: [multi-stream import per station, new-vs-attach dialog flow, auto-detect station match]
key_files:
  created: []
  modified:
    - musicstreamer/aa_import.py
    - musicstreamer/ui/discovery_dialog.py
    - musicstreamer/ui/import_dialog.py
    - tests/test_aa_import.py
decisions:
  - "fetch_channels_multi iterates all 3 quality tiers per network in one pass, keyed by (slug, channel_key) to collate streams"
  - "import_stations_multi updates the auto-created stream (position=1) with quality/codec metadata, then inserts remaining streams"
  - "discovery_dialog attach flow uses case-insensitive substring match for auto-detection; defaults to index 0 if no match"
  - "yt_import.py required no changes - repo.insert_station interface is backward-compatible"
metrics:
  duration: "~3 min"
  completed: "2026-04-09"
  tasks_completed: 2
  files_modified: 4
requirements: [STR-06, STR-12, STR-13, STR-14]
---

# Phase 27 Plan 03: Import Flows Multi-Stream Update Summary

**One-liner:** AudioAddict import now creates hi/med/low stream rows per channel; Radio-Browser save offers new-station vs attach-to-existing picker with name auto-detection.

## What Was Built

- `fetch_channels_multi(listen_key)` in `aa_import.py`: fetches all 6 AA networks across all 3 quality tiers in one pass. Returns channels with a `streams` list containing `{url, quality, position, codec}` for hi (position=1), med (position=2), low (position=3).
- `import_stations_multi(channels, repo)` in `aa_import.py`: creates one station per channel, updates the auto-created stream with quality/codec metadata, and inserts 2 additional stream rows. Skips channel if any stream URL already exists. Returns `(imported, skipped)`.
- `import_dialog.py` updated to call `fetch_channels_multi` / `import_stations_multi` instead of the single-quality functions. Quality dropdown UI preserved (no regression).
- `discovery_dialog.py` `_on_save_clicked` now shows `Adw.MessageDialog` with "New Station" / "Attach to Existing..." / "Cancel" responses.
- `_save_as_new` helper extracted from prior inline save logic.
- `_show_station_picker` method: opens an `Adw.Window` picker listing all stations with name+stream count subtitle; auto-selects the first case-insensitive substring match; "Attach Stream" inserts a new stream row at next sequential position.
- 8 new tests in `tests/test_aa_import.py` covering multi-quality fetch and import.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 8e7edd0 | feat(27-03): add fetch_channels_multi and import_stations_multi to aa_import |
| 2 | 76e2528 | feat(27-03): add new-vs-attach save flow to discovery_dialog |

## Deviations from Plan

None — plan executed exactly as written. `yt_import.py` required no changes (repo interface backward-compatible, as predicted).

## Known Stubs

None.

## Threat Flags

None — T-27-07 mitigated: all DB operations use parameterized SQL via repo methods; station names displayed via `GLib.markup_escape_text` in the picker rows.

## Self-Check: PASSED

- musicstreamer/aa_import.py contains `def fetch_channels_multi`: FOUND
- musicstreamer/aa_import.py contains `def import_stations_multi`: FOUND
- musicstreamer/ui/discovery_dialog.py contains `_show_station_picker`: FOUND
- musicstreamer/ui/discovery_dialog.py contains `_save_as_new`: FOUND
- musicstreamer/ui/discovery_dialog.py contains `Attach to Existing`: FOUND
- tests/test_aa_import.py contains `test_fetch_channels_multi_returns_streams`: FOUND
- tests/test_aa_import.py contains `test_import_multi_creates_streams`: FOUND
- Commits 8e7edd0 and 76e2528: FOUND
- 76 tests passing
