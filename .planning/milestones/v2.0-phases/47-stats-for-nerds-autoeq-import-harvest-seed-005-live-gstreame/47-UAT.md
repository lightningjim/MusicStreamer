---
status: resolved
phase: 47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame
source:
  - 47-01-SUMMARY.md
  - 47-02-SUMMARY.md
  - 47-03-SUMMARY.md
started: 2026-04-18T18:04:11Z
updated: 2026-04-18T22:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Bitrate column visible in Edit Station
expected: |
  Open Edit Station for any station. streams_table shows 5 columns:
  URL | Quality | Codec | Bitrate (kbps) | Position. Hover the Bitrate header
  to see tooltip "Higher bitrate streams play first on failover".
result: pass

### 2. Bitrate cell accepts only integers 0-9999
expected: |
  In Edit Station, double-click a Bitrate cell. Typing letters or a 5-digit
  number is rejected by the editor (QIntValidator 0-9999). Placeholder text
  "e.g. 128" appears on empty cells. Clearing a cell and pressing Enter/Tab
  to save shows 0 afterward (empty saves as 0, no crash).
result: issue
reported: |
  5-digit rejection works as designed. But clearing a cell and pressing
  Enter/Tab does NOT save as 0 — the cell reverts to its previous value
  (either blank or the original bitrate).
severity: major

### 3. DI.fm import populates Bitrate
expected: |
  Use Discover Stations (AudioAddict) to import from DI.fm. After import, open
  Edit Station on one of the imported DI.fm stations. Bitrate column shows the
  tier-mapped values: 320 for hi-quality streams, 128 for med, 64 for low.
  Stations with unknown tiers or no quality info may show 0.
result: issue
reported: |
  Bitrate values are correct (320/128/64). Two separate problems surfaced:
  (a) Each AudioAddict PLS file lists 2 servers per tier (primary + fallback);
      only 1 stream per tier is imported — we drop the fallback URL.
  (b) Codec labels are wrong across ALL paid AA tiers. Ground truth from the
      AA hardware-player settings UI: hi=320 MP3, med=128 AAC, low=64 AAC
      (and 320 is not available on the free tier at all). Current import
      labels are hi=AAC, med=MP3, low=MP3 — inverted. Fix the tier→codec
      map (or read codec from AA stream metadata instead of inferring).
severity: major

### 4. Settings export/import preserves Bitrate
expected: |
  Pick a station with non-zero bitrate values, confirm the numbers in Edit Station.
  Export settings to ZIP (Settings → Export). Delete or edit the bitrate values,
  then import the ZIP back. Reopen Edit Station on that station — bitrate values
  match what was exported.
result: pass

### 5. Failover prefers higher-bitrate stream
expected: |
  Find (or temporarily craft) a station with 2+ streams at different bitrates.
  Break the highest-bitrate stream URL (edit it to garbage like "http://broken.local/")
  so it will fail on play. Click play. After the broken stream fails, playback
  transitions to the next-highest bitrate stream (not position order). Stats-for-nerds
  / log confirms which stream is playing. Restore the URL afterward.
  (Skip this test if you don't have a station with multiple streams at different bitrates — reply "skip".)
result: issue
reported: |
  Playback does eventually succeed, but (a) there is no visible indication
  anywhere in the UI that the primary stream failed and failover occurred —
  no status text, no stats-for-nerds / log entry the user could find; and
  (b) separately: when only the low-quality AA stream was functional (higher
  qualities were broken), the app reported "stream exhausted" even though
  the low-quality stream plays fine when selected directly. The failover
  queue appears to give up before actually trying (or correctly recognizing
  success on) the low-quality stream.
severity: major

## Summary

total: 5
passed: 2
issues: 3
pending: 0
skipped: 0

## Gaps

- truth: "Clearing a Bitrate cell and committing the edit (Enter/Tab) persists the cell as 0 (int(text or \"0\") defensive coerce on save path)"
  status: resolved
  resolved_by: 47-04
  reason: |
    User reported: empty cell does NOT save as 0. On commit, the cell reverts
    to its prior value (either blank or the original bitrate). Likely cause:
    the QStyledItemDelegate `setModelData` path does not write back the empty
    string to the table item, OR the save-to-model code reads the existing
    stream.bitrate_kbps when the cell text is empty rather than coercing to 0.
    Investigate `_BitrateDelegate.setModelData` and `edit_station_dialog`'s
    _commit/_save path to ensure empty-cell edits round-trip to the stream
    record as bitrate_kbps=0.
  severity: major
  test: 2
  artifacts: []
  missing: []

- truth: "AudioAddict PLS import captures all server URLs per quality tier (primary + fallback), not just the first"
  status: resolved
  resolved_by: 47-06
  reason: |
    User reported: each AA PLS file lists 2 servers per tier (primary + fallback),
    but only 1 stream per tier is imported. The fallback URL is silently dropped.
    Investigate the AA PLS-parsing path: likely only the first `File1=` entry is
    kept per quality, or a dedupe pass collapses same-tier URLs. The fallback
    is critical for failover redundancy — losing it defeats the bitrate-failover
    benefit this phase was meant to enable.
    NOTE: This bug may predate Phase 47 (PLS parsing wasn't touched by this phase).
    Verify by checking if previous imports also dropped fallbacks.
  severity: major
  test: 3
  artifacts: []
  missing: []

- truth: "AudioAddict paid-tier codec/bitrate mapping matches reality: hi=320 MP3, med=128 AAC, low=64 AAC (user-confirmed via AA hardware-player settings — consistent across all paid AA networks)"
  status: resolved
  resolved_by: 47-07
  reason: |
    Ground truth from AA hardware-player settings UI (user-provided):
      Excellent = 128k AAC
      Excellent = 320k MP3
      Good      = 64k AAC
    So the paid AA tier→(codec,bitrate) mapping is:
      hi  → MP3, 320
      med → AAC, 128
      low → AAC,  64
    Note: 320 is NOT available on the free tier at all.

    Current app mapping after Phase 47 is:
      hi  → AAC, 320   (codec wrong — should be MP3)
      med → MP3, 128   (codec wrong — should be AAC)
      low → MP3,  64   (codec wrong — should be AAC)

    Bitrate values are correct; codec labels for hi/med/low are all wrong.
    Fix: update `aa_import.py`'s codec inference (and any related tier-map
    constants) to use the real paid-AA mapping above, or read codec from
    the AA channel/stream metadata (content_type) instead of inferring from
    the tier name. Codec labelling existed pre-47, but Phase 47 hardcoded
    bitrate alongside the tier so this is the right moment to correct both.
  severity: major
  test: 3
  artifacts: []
  missing: []

- truth: "Stream failover events are visible to the user (status line, stats-for-nerds entry, or log) so the user knows a fallback occurred instead of silently believing the primary succeeded"
  status: deferred
  deferred_to: 47.1
  reason: |
    User reported: when the primary stream failed and playback transitioned
    to the next stream, there was NO visible indication anywhere — no status
    bar text, no stats-for-nerds entry, no in-app log. Playback just "worked"
    eventually. For a failover feature to be useful, the user needs feedback
    that it occurred (at minimum: which stream is actually playing, and
    whether a failover happened). Suggest: status-line message
    "Primary stream failed, trying {N}/{M}..." + add the active-stream URL
    and position to stats-for-nerds (phase 47.1 scope territory).
  severity: major
  test: 5
  artifacts: []
  missing: []

- truth: "Failover queue tries EVERY stream in order and succeeds on the first working one — does NOT report 'stream exhausted' until all streams have actually been attempted and failed"
  status: resolved
  resolved_by: 47-05
  debug_session: stream-exhausted-premature.md
  reason: |
    User reported: on an AA station where ONLY the low-quality stream was
    functional (higher qualities were broken), the app reported "stream
    exhausted" — but when the user selected the low-quality stream directly,
    it played fine. So the failover queue is either (a) giving up before
    attempting the low-quality stream, (b) misreporting a successful connect
    as a failure on that stream, or (c) the order_streams ordering is
    placing the low-quality stream somewhere the failover loop doesn't
    reach. This is a correctness bug in the failover path that DEFEATS
    the core feature this phase was meant to ship — failover should
    exhaust the full list before giving up.
    Investigate `player.py` failover loop: confirm it iterates all items
    in `order_streams(station.streams)`, tracks per-stream success/fail,
    and only emits "exhausted" when every candidate has actually errored.
    Check whether `preferred_quality` short-circuit (player.py:167-177
    per 47-02 SUMMARY) prematurely filters the queue.
  severity: major
  test: 5
  artifacts: []
  missing: []
