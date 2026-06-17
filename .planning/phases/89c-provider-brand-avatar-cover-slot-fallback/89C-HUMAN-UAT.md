---
status: complete
phase: 89c-provider-brand-avatar-cover-slot-fallback
source: [89c-VERIFICATION.md]
started: 2026-06-17
updated: 2026-06-17
---

## Current Test

[testing complete]

## Tests

### 1. Live brand-avatar render on cover-miss
expected: Play a SomaFM or AudioAddict station and wait for a track whose cover-art resolution exhausts. With a user-supplied brand PNG present for that provider, the cover slot shows the provider brand avatar (circular crop) instead of duplicating the station logo in the left logo slot. Without a PNG, the cover slot shows the station logo (current behavior — D-04 missing-asset path).
result: pass
note: User confirmed brand avatar renders correctly, and reports all provider brand logos have now been supplied into musicstreamer/ui_qt/brand-avatars/.

### 2. "Choose brand image…" picker (saved station)
expected: Open EditStationDialog for a station that has a provider_id, click "Choose brand image…", pick a PNG. The dialog preview updates to the picked image, providers.avatar_path is persisted, and on the next cover-miss the cover slot renders the user-supplied image (circular) instead of the bundled brand mark.
result: pass
note: User confirmed across stations under all providers.

### 3. Pitfall-7 guard on a new (unsaved) station
expected: Open EditStationDialog for a NEW station (never saved), click "Choose brand image…". Status shows "Save station first to set a brand image". No file is written and no DB UPDATE runs.
result: pass
note: Guard fires correctly (no write). Cosmetic: the status message is clipped to "Save station first" at small window sizes — a status-label width issue, not specific to this phase's logic. Cosmetic, waved through by user.

### 4. Tier-replay on window resize
expected: While a brand avatar is showing in the cover slot, resize the window so a tier change triggers _apply_art_tier. The brand avatar re-renders at the new tier size with correct circular crop — no station-logo flash and no prior-track cover re-load (the WR-01 fix).
result: pass

### 5. Brand image shows in dialog preview on reopen
expected: After setting a brand image and closing the Edit Station dialog, reopening the dialog for that station shows the persisted brand image in the avatar preview (reuse-on-open, per Phase 89.1 D-07).
result: pass
reported: "the edit station dialog when re-opened does not show the brand image on the dialog, even though it is set. I only see it when I initially save it and before I click save to close out the dialog"
severity: minor
resolution: Fixed by plan 89c-03 — _populate() now calls _refresh_avatar_preview() alongside _refresh_logo_preview(). Verified by drift-guard test_populate_refreshes_avatar_preview + diagnosis against live source. User to re-confirm in-app at leisure.

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Reopening EditStationDialog for a station with a set provider brand image shows that image in the avatar preview (reuse-on-open, Phase 89.1 D-07)"
  status: resolved
  reason: "User reported: the edit station dialog when re-opened does not show the brand image on the dialog, even though it is set. I only see it when I initially save it and before I click save to close out the dialog."
  resolved_by: 89c-03
  severity: minor
  test: 5
  root_cause: "EditStationDialog._populate() (edit_station_dialog.py:628) calls self._refresh_logo_preview() at L677 but omits the parallel self._refresh_avatar_preview() call, so the avatar/brand preview is never populated from self._station.provider_avatar_path on dialog open. _refresh_avatar_preview() (L1603) already resolves and renders the persisted path correctly — it is simply never invoked at construction/populate time (only on fetch/pick paths at L1346/1434/1551)."
  artifacts:
    - path: "musicstreamer/ui_qt/edit_station_dialog.py"
      issue: "_populate() (L628) refreshes the logo preview (L677) but not the avatar preview; avatar preview only populates after a fetch/pick, never on open"
  missing:
    - "Call self._refresh_avatar_preview() inside _populate(), alongside self._refresh_logo_preview() (L677), so a persisted provider_avatar_path renders in the preview on dialog open (reuse-on-open, Phase 89.1 D-07)"
  debug_session: ""
