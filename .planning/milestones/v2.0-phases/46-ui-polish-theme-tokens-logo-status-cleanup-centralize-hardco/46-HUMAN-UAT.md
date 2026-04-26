---
status: complete
phase: 46-ui-polish-theme-tokens-logo-status-cleanup
source:
  - .planning/phases/46-ui-polish-theme-tokens-logo-status-cleanup-centralize-hardco/46-VERIFICATION.md
started: 2026-04-17T17:00:00Z
updated: 2026-04-17T18:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Wait cursor during logo fetch
expected: Launch `python -m musicstreamer`. Edit a station, paste a URL that triggers fetch (e.g. a YouTube live URL). Cursor changes to `Qt.WaitCursor` (hourglass/busy) for the ~1-2s fetch duration, then returns to default.
result: pass

### 2. AA-no-key classification message
expected: In EditStationDialog, paste an AudioAddict URL whose channel key cannot be derived (e.g., a provider root URL like `https://www.di.fm/` rather than a specific channel). Wait for the fetch. The `_logo_status` label should read `"AudioAddict station — use Choose File to supply a logo"` — NOT the generic `"Fetch not supported for this URL"`.
result: pass

### 3. Logo status auto-clear (3s + textChanged)
expected: In EditStationDialog, paste a URL that produces a terminal status (e.g. an unsupported URL → "Fetch not supported for this URL"). Wait ~3 seconds; label clears. Repeat: after the status appears, immediately type another character in the URL field — label clears instantly (no 3s wait).
result: pass

### 4. Empty-state glyph preservation
expected: Stations without a cached logo continue to show the generic `audio-x-generic-symbolic` music-note icon (unchanged from prior behavior). No visual regression.
result: pass

### 5. Error-red color unchanged
expected: Visually confirm the error-red color in dialogs (e.g. Replace All warning in SettingsImportDialog, delete-button color in EditStationDialog, invalid-hex border in AccentColorDialog) is still the same `#c0392b` shade — nothing rendered in a different red or accidentally in black.
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
