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
result: blocked
blocked_by: prior-phase
reason: "No UI entry point to open DiscoveryDialog — hamburger menu is Phase 40 (UI-10)"

### 6. Discovery — Preview and Save
expected: In Discovery results, click Play/Save on a row.
result: blocked
blocked_by: prior-phase
reason: "Same as test 5 — no launch point for DiscoveryDialog"

### 7. Import — YouTube Playlist
expected: Open Import dialog, YouTube tab. Scan and import live streams.
result: blocked
blocked_by: prior-phase
reason: "No UI entry point to open ImportDialog — hamburger menu is Phase 40 (UI-10)"

### 8. Import — AudioAddict
expected: Open Import dialog, AudioAddict tab. Import channels with progress.
result: blocked
blocked_by: prior-phase
reason: "Same as test 7 — no launch point for ImportDialog"

### 9. Stream Picker — Visibility
expected: Stream picker hidden for single-stream stations, visible for multi-stream stations.
result: pass

### 10. Stream Picker — Manual Switch
expected: Select a different stream from the picker dropdown. Playback switches.
result: pass

## Summary

total: 10
passed: 4
issues: 2
pending: 0
skipped: 0
blocked: 4

## Gaps

- truth: "Re-opening edit dialog for the same station (without replaying) should show current DB data"
  status: failed
  reason: "User reported: dialog constructs from stale in-memory Station object, not re-fetched from DB"
  severity: major
  test: 2
  artifacts: [musicstreamer/ui_qt/main_window.py]
  missing: [re-fetch station from repo before constructing EditStationDialog]

- truth: "User should be able to edit any station, not just the currently playing one"
  status: failed
  reason: "User reported: edit button only enabled during playback; no edit path for stopped/paused stations"
  severity: major
  test: 3
  artifacts: [musicstreamer/ui_qt/now_playing_panel.py, musicstreamer/ui_qt/station_list_panel.py]
  missing: [edit entry point on station list (right-click or double-click), or keep edit enabled for last-selected station]
