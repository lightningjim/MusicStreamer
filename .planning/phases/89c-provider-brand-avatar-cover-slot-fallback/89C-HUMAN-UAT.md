---
status: partial
phase: 89c-provider-brand-avatar-cover-slot-fallback
source: [89c-VERIFICATION.md]
started: 2026-06-17
updated: 2026-06-17
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live brand-avatar render on cover-miss
expected: Play a SomaFM or AudioAddict station and wait for a track whose cover-art resolution exhausts. With a user-supplied brand PNG present for that provider, the cover slot shows the provider brand avatar (circular crop) instead of duplicating the station logo in the left logo slot. Without a PNG, the cover slot shows the station logo (current behavior — D-04 missing-asset path).
result: [pending]

### 2. "Choose brand image…" picker (saved station)
expected: Open EditStationDialog for a station that has a provider_id, click "Choose brand image…", pick a PNG. The dialog preview updates to the picked image, providers.avatar_path is persisted, and on the next cover-miss the cover slot renders the user-supplied image (circular) instead of the bundled brand mark.
result: [pending]

### 3. Pitfall-7 guard on a new (unsaved) station
expected: Open EditStationDialog for a NEW station (never saved), click "Choose brand image…". Status shows "Save station first to set a brand image". No file is written and no DB UPDATE runs.
result: [pending]

### 4. Tier-replay on window resize
expected: While a brand avatar is showing in the cover slot, resize the window so a tier change triggers _apply_art_tier. The brand avatar re-renders at the new tier size with correct circular crop — no station-logo flash and no prior-track cover re-load (the WR-01 fix).
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
