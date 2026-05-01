---
status: resolved
trigger: |
  DATA_START
  Some DI.fm streams get a Fetch failed for the image, such as EDM Festival and Electro House
  DATA_END
created: 2026-05-01
updated: 2026-05-01
slug: di-fm-image-fetch-failed
---

# Debug Session: di-fm-image-fetch-failed

## Symptoms

- **Expected behavior:** When opening EditStationDialog for a DI.fm station, the AA channel logo auto-fetches from the AudioAddict API and renders in the image area on the right (replacing the "Fetching..." placeholder).
- **Actual behavior:** For some DI.fm channels (confirmed: **EDM Festival**, **Electro House**), the placeholder transitions to a "Fetch failed" state instead of rendering the logo.
- **Where surfaced:** EditStationDialog auto-load image area — the same right-side panel that shows "Fetching" while the AA logo loads.
- **Error messages:** UI text reads "Fetch failed" (line 777 of `edit_station_dialog.py` — set when `image_url` is None/empty after `_fetch_image_map` lookup).
- **Timeline:** Unknown — user does not know whether these channels ever worked.
- **Reproduction:** Open EditStationDialog for an affected DI.fm channel (EDM Festival, Electro House); observe the auto-fetch image transition from "Fetching" to "Fetch failed".
- **Scope:** Affects 4 DI.fm channels confirmed (see Evidence). Broader networks (radiotunes etc.) have similar prefix issues but were not reported.
- **Source path (per user):** AudioAddict API (channel asset URL) — `_fetch_image_map` / `_aa_channel_key_from_url` code path.

## Current Focus

- **hypothesis:** CONFIRMED — two layered issues in `_aa_channel_key_from_url` in `url_helpers.py`
- **test:** 9 new regression tests added to `tests/test_aa_url_detection.py`; all 72 AA-related tests pass
- **expecting:** Logo fetches successfully for all 4 affected channels
- **next_action:** DONE — fix applied

## Evidence

- timestamp: 2026-05-01T00:00:00Z
  finding: |
    `_fetch_image_map('di')` returns a dict keyed by AA API channel keys. The key for
    "Electro House" is `electro` and for "EDM Festival" is `edmfestival`. Both have
    `square` image URLs available in the API response.

- timestamp: 2026-05-01T00:00:01Z
  finding: |
    DI.fm public PLS files (e.g. https://listen.di.fm/public3/electro.pls) resolve to stream
    URLs with a `di_` path prefix: `http://pub8.di.fm:80/di_electrohouse`. This prefix is NOT
    stripped by `_aa_channel_key_from_url`, so `channel_key` comes out as `di_electrohouse`
    (or `di_mainstage` for EDM Festival). Neither key exists in the image map -> image_url is
    None -> "Fetch failed".

- timestamp: 2026-05-01T00:00:02Z
  finding: |
    All 119 DI.fm channels were checked against their public PLS path. 99/119 use the pattern
    `di_{api_key}` (stripping `di_` gives the correct API key). 4 channels have an additional
    mismatch where the stripped URL path segment doesn't match the current API key:
      - `electro` (Electro House): URL uses `di_electrohouse` -> stripped `electrohouse` != `electro`
      - `edmfestival` (EDM Festival): URL uses `di_mainstage` -> stripped `mainstage` != `edmfestival`
      - `club` (Club): URL uses `di_clubsounds` -> stripped `clubsounds` != `club`
      - `classictechno` (Classic Techno): URL uses `di_oldschoolelectronica` -> stripped doesn't match
    These are channel renames/aliases in the DI.fm backend where the stream URL path was not
    updated to match the new API key.

- timestamp: 2026-05-01T00:00:03Z
  finding: |
    The existing `_NETWORK_URL_PREFIXES` dict only contained `zenradio -> 'zr'`. DI.fm was
    missing. Premium DI.fm stream URLs also use the `di_` prefix (confirmed by docstring
    example on line 76 of url_helpers.py: `'http://prem2.di.fm:80/di_house' -> 'di'`).

## Eliminated

- TLS/HTTPS issue on CDN: image URLs fetch fine once the correct key is used (confirmed by curl)
- Network auth failure: `_fetch_image_map` returns valid data; the bug is in key lookup, not API access
- Missing `square` field: all 4 affected channels have `square` and `default` images in the API response
- EDM Festival being a new/unlisted channel: it has `key=edmfestival` with full image data

## Resolution

**Root cause:** Two compounding issues in `_aa_channel_key_from_url` (`musicstreamer/url_helpers.py`):

1. **Missing `di_` prefix stripping**: `_NETWORK_URL_PREFIXES` only mapped `zenradio -> 'zr'`. DI.fm stream URLs use a `di_` path prefix (e.g. `/di_chillout`, `/di_ambient_hi`) that was not stripped, so the derived channel key was `di_chillout` instead of `chillout`. This prevented image map lookups for ALL DI.fm stations.

2. **Channel key aliases not handled**: After stripping `di_`, 4 channels have URL path segments that don't match the current AA API key (renamed channels). For example, the Electro House URL path is `di_electrohouse` -> stripped `electrohouse`, but the API key is `electro`.

**Fix applied** in `musicstreamer/url_helpers.py`:
- Added `"di": "di_"` to `_NETWORK_URL_PREFIXES`
- Added `_AA_CHANNEL_KEY_ALIASES` dict mapping the 4 legacy URL path names to current API keys: `electrohouse -> electro`, `mainstage -> edmfestival`, `clubsounds -> club`, `oldschoolelectronica -> classictechno`
- Applied alias lookup as final step in `_aa_channel_key_from_url` after prefix stripping
- Updated docstring with accurate DI.fm example

**Tests added** in `tests/test_aa_url_detection.py`:
- 3 tests for `di_` prefix stripping (bare, with `_hi` suffix, other channels)
- 4 tests for `electrohouse -> electro` alias (public + premium URL forms)
- 4 tests for `mainstage -> edmfestival`, `clubsounds -> club`, `oldschoolelectronica -> classictechno`

72 AA-related tests pass. Pre-existing test failures (MPRIS DBus, SMTC) are unrelated.

## Notes

- Project context: AA logo fetching code lives in `url_helpers.py` (per Phase 51 decision: `find_aa_siblings` was added there alongside existing `_aa_slug_from_url`, `_aa_channel_key_from_url`, and the AA channel logo helpers). EditStationDialog is the surfacing UI.
- Phase 36-02 deleted `test_fetch_aa_logo` tests; Phase 39 rebuilt loader path with Qt signals — current loader is the GTK-cutover successor.
- The `find_aa_siblings` function in the same file also calls `_aa_channel_key_from_url`, so this fix also corrects sibling matching for the 4 aliased channels (cross-network sibling detection would have failed to match Electro House across networks).
