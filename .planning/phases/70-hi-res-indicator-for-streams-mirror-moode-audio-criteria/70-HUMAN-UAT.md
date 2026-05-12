---
status: partial
phase: 70-hi-res-indicator-for-streams-mirror-moode-audio-criteria
source: [70-VERIFICATION.md]
started: 2026-05-12T16:30:00Z
updated: 2026-05-12T16:30:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. NowPlayingPanel _quality_badge visual rendering
expected: A 'HI-RES' pill badge appears immediately left of the LIVE badge in the icy_row. Badge uses palette(highlight) background, palette(highlighted-text) text, border-radius 8px, bold weight. Badge is hidden for an MP3-only station.
how_to: Open the app with a station bound that has a cached FLAC hi-res stream. Observe the now-playing panel.
result: [pending]

### 2. Stream picker tier suffix
expected: Each hi-res stream item shows a label such as 'FLAC 1411 — HI-RES' (em-dash separator, all-caps tier suffix). Lossless CD stream shows 'FLAC 1411 — LOSSLESS'. MP3 stream shows no suffix.
how_to: While a hi-res stream is playing, observe the stream picker combo box items in the now-playing panel.
result: [pending]

### 3. Station tree tier pill
expected: Hi-res station row shows a 'HI-RES' pill before the star icon. CD-FLAC station shows 'LOSSLESS' pill. MP3-only station shows no pill. Provider rows show no pill. When a hi-res row is selected (highlighted), the pill fill and text colors swap (Highlight/HighlightedText) so the pill remains visible.
how_to: Open the station tree (StationListPanel). Observe tree rows for a known hi-res station versus an MP3-only station; click to highlight the hi-res row.
result: [pending]

### 4. EditStationDialog Audio quality column
expected: A 6th column 'Audio quality' (Sentence case) appears, 90 px wide, Fixed mode. The cell for the hi-res stream reads 'Hi-Res' (title-case prose). Cell is read-only (cannot be edited). Header tooltip reads 'Auto-detected from playback. Hi-Res ≥ 48 kHz or ≥ 24-bit on a lossless codec.'
how_to: Open EditStationDialog for a station with a FLAC 96/24 stream (already played once so caps are cached). Inspect the streams table.
result: [pending]

### 5. Hi-Res only filter chip end-to-end
expected: The 'Hi-Res only' chip becomes visible after any station has a cached hi-res stream. Clicking it filters the station list to only stations with at least one cached hi-res stream. Unclicking restores all stations. Chip has tooltip 'Show only stations with at least one Hi-Res stream'.
how_to: In StationListPanel, play a hi-res stream to completion so caps are cached. Observe the 'Hi-Res only' chip.
result: [pending]

### 6. Runtime caps detection live flow
expected: Initially the badge shows 'LOSSLESS' (FLAC cold-start D-03 default). After GStreamer reports the actual caps (96 kHz / 24-bit), the badge text switches to 'HI-RES' and the tooltip updates to 'Hi-Res — 96 kHz / 24-bit'.
how_to: Play a hi-res stream; observe whether the badge updates live after GStreamer caps are negotiated (runtime detection).
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
