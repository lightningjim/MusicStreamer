---
status: complete
phase: 39-core-dialogs
source: [39-01-SUMMARY.md, 39-02-SUMMARY.md, 39-03-SUMMARY.md, 39-04-SUMMARY.md]
started: 2026-04-13T09:15:00Z
updated: 2026-04-13T09:45:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Edit Station Dialog Opens
expected: Click a station to play it. Click the edit (pencil) icon on the now-playing panel. An EditStationDialog opens showing the station's name, URL, provider, tags, and streams.
result: pass
notes: Missing stream label column in stream table — label field exists in data model but not exposed in UI

### 2. Edit Station — Save Changes
expected: Change a station's name or provider in the edit dialog. Click "Save Station". Dialog closes. Station list refreshes with the updated name.
result: issue
reported: "Save works and list refreshes, but re-opening edit dialog without replaying the station shows the original (stale) info. Double-clicking to replay then edit shows updated info."
severity: major

### 3. Edit Station — Delete Guard
expected: While a station is playing, open its edit dialog. The "Delete Station" button should be disabled. Stop playback, re-open the edit dialog — delete button should now be enabled.
result: issue
reported: "Edit button only enabled when station is playing. No way to edit a non-playing station at all. Stopping unloads the station context. Pausing also keeps delete disabled."
severity: major

### 4. Edit Station — Stream Table
expected: Open edit dialog for a multi-stream station. Stream table shows multiple rows with URL, Quality, Codec, Position. Add/Remove/Move Up/Move Down buttons work.
result: pass
notes: Position column numbers don't visually update after reorder — cosmetic only

### 5. Discovery — Search and Results
expected: Open the Discovery dialog. Type a station name, click "Search Stations". Results appear in a table.
result: pass
notes: Works via hamburger menu. User prefers play/stop icons instead of text buttons in results table.

### 6. Discovery — Preview and Save
expected: In Discovery results, click Play/Save on a row.
result: pass
notes: Works. Play/stop buttons should use icons instead of words (cosmetic).

### 7. Import — YouTube Playlist
expected: Open Import dialog, YouTube tab. Scan and import live streams.
result: issue
reported: "Fails with 'No live streams detected' even though there are live streams in playlist https://www.youtube.com/playlist?list=PL6NdkXsPL07Il2hEQGcLI4dg_LTg7xA2L"
severity: major

### 8. Import — AudioAddict
expected: Open Import dialog, AudioAddict tab. Import channels with progress.
result: pass
notes: Worked but very slow. Came back empty — user already had all AA stations imported (dedup). Consider showing "0 new, N skipped" instead of empty result.

### 9. Stream Picker — Visibility
expected: Stream picker hidden for single-stream stations, visible for multi-stream stations.
result: pass

### 10. Stream Picker — Manual Switch
expected: Select a different stream from the picker dropdown. Playback switches.
result: pass

## Summary

total: 10
passed: 7
issues: 3
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Re-opening edit dialog for the same station (without replaying) should show current DB data"
  status: resolved
  reason: "Fixed: dialog now re-fetches from DB before opening"
  severity: major
  test: 2
  artifacts: [musicstreamer/ui_qt/main_window.py]

- truth: "User should be able to edit any station, not just the currently playing one"
  status: resolved
  reason: "Fixed: right-click context menu on station list"
  severity: major
  test: 3
  artifacts: [musicstreamer/ui_qt/station_list_panel.py]

- truth: "YouTube playlist import should detect live streams in valid playlists"
  status: failed
  reason: "User reported: 'No live streams detected' for playlist with live streams (PL6NdkXsPL07Il2hEQGcLI4dg_LTg7xA2L)"
  severity: major
  test: 7
  artifacts: [musicstreamer/ui_qt/import_dialog.py, musicstreamer/yt_import.py]
  missing: [investigate _entry_is_live filter logic — may reject entries with live_status not set in extract_flat mode]

- truth: "User should be able to edit any station, not just the currently playing one"
  status: failed
  reason: "User reported: edit button only enabled during playback; no edit path for stopped/paused stations"
  severity: major
  test: 3
  artifacts: [musicstreamer/ui_qt/now_playing_panel.py, musicstreamer/ui_qt/station_list_panel.py]
  missing: [edit entry point on station list (right-click or double-click), or keep edit enabled for last-selected station]
