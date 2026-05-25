---
status: passed
phase: 70-hi-res-indicator-for-streams-mirror-moode-audio-criteria
source: [70-VERIFICATION.md]
started: 2026-05-12T16:30:00Z
updated: 2026-05-12T17:30:00Z
completed: 2026-05-12T17:30:00Z
---

## Current Test

[complete]

## Tests

### 1. NowPlayingPanel _quality_badge visual rendering
expected: A 'HI-RES' pill badge appears immediately left of the LIVE badge in the icy_row. Badge uses palette(highlight) background, palette(highlighted-text) text, border-radius 8px, bold weight. Badge is hidden for an MP3-only station with bitrate ≤ 128 kbps; visible for high-bitrate lossy or any lossless.
how_to: Open the app with a station bound that has a cached FLAC hi-res stream OR a lossy stream at > 128 kbps. Observe the now-playing panel.
result: pass — user confirmed badge appears on all expected stations after D-04 mirror fix (commit f53d4cb)

### 2. Stream picker tier suffix
expected: Each hi-res stream item shows a label such as 'FLAC 1411 — HI-RES' or 'MP3 320 — HI-RES' (em-dash separator, all-caps tier suffix). MP3 128K stream shows no suffix.
how_to: While a hi-res stream is playing, observe the stream picker combo box items in the now-playing panel.
result: pass — user confirmed via DI.FM Lounge MP3 320K

### 3. Station tree tier pill
expected: Hi-res station row shows a 'HI-RES' pill before the star icon. CD-FLAC station shows 'LOSSLESS' pill. Sub-128-kbps MP3-only station shows no pill. Provider rows show no pill. When a hi-res row is selected (highlighted), the pill fill and text colors swap (Highlight/HighlightedText) so the pill remains visible.
how_to: Open the station tree (StationListPanel). Observe tree rows for a known hi-res station versus a low-bitrate-lossy-only station.
result: pass

### 4. EditStationDialog Audio quality column
expected: A 6th column 'Audio quality' (Sentence case) appears, 90 px wide, Fixed mode. The cell for the hi-res stream reads 'Hi-Res' (title-case prose). MP3 ≤ 128 kbps reads ''. Cell is read-only (cannot be edited). Header tooltip reads 'Auto-detected from playback. Hi-Res ≥ 48 kHz or ≥ 24-bit on a lossless codec.'
how_to: Open EditStationDialog for a station with mixed lossless + lossy streams.
result: pass — note: header tooltip prose now slightly understates the rule (post-fix D-04 also includes lossy > 128 kbps); follow-up tooltip refresh tracked as a polish item.

### 5. Hi-Res only filter chip end-to-end
expected: The 'Hi-Res only' chip becomes visible after any station has a cached hi-res stream. Clicking it filters the station list to only stations with at least one Hi-Res stream.
how_to: In StationListPanel, observe the chip after streams populate.
result: pass — user confirmed "no obvious regressions or other issues"

### 6. Runtime caps detection live flow
expected: Initially the badge shows 'LOSSLESS' (FLAC cold-start D-03 default) OR 'HI-RES' for lossy > 128 kbps (immediate via bitrate, no caps wait needed). After GStreamer reports the actual caps on a FLAC, the badge text switches to 'HI-RES' and the tooltip updates.
how_to: Play a high-bitrate lossy stream and a FLAC stream; observe the badge.
result: pass — also required commit e57051e (playbin3 audio-sink pad probe replacing the legacy `get-audio-pad` action signal that crashed on live playback)

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

(none — all 6 UAT items passed after two post-UAT fixes:
 commit e57051e — playbin3 compat for caps pad extraction
 commit f53d4cb — D-04 revised to mirror moOde RADIO_BITRATE_THRESHOLD=128)
