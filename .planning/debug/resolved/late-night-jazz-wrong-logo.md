---
status: resolved
trigger: |
  DATA_START
  More possible misreads. Late Night Jazz is pulling the Trumpet Jazz logo
  DATA_END
created: 2026-05-09
updated: 2026-05-09
resolved: 2026-05-09
slug: late-night-jazz-wrong-logo
---

# Debug Session: late-night-jazz-wrong-logo

## Symptoms

- **Expected behavior:** When fetching the AA channel logo for the JazzRadio.com station "Late Night Jazz", the EditStationDialog (or the on-disk cached image) should resolve to Late Night Jazz's own square logo from the AudioAddict / JazzRadio API.
- **Actual behavior:** The logo that comes back is the **Trumpet Jazz** channel logo — i.e., the channel-key derivation or image-map lookup is collapsing "Late Night Jazz" onto the wrong channel ("Trumpet Jazz").
- **Where surfaced (per user):** "specifically the fetch from AA/JazzRadio" — the AA/JazzRadio image fetch path (i.e. `_fetch_image_map('jazzradio')` lookup keyed off `_aa_channel_key_from_url` for the Late Night Jazz stream URL).
- **Error messages:** None visible in UI — no "Fetch failed" surfaced. The fetch *succeeds*, it just returns the wrong channel's image. This is a silent misread, not a fetch error.
- **Timeline:** Just noticed / recent (2026-05-09). The previous DI.fm-prefix fix (`di-fm-image-fetch-failed`, resolved 2026-05-01, commit landed in url_helpers.py) is the most recent change to `_aa_channel_key_from_url`; the regression window may overlap that change.
- **Reproduction:** Open the AA/JazzRadio image fetch for the "Late Night Jazz" station and observe the rendered square image — it shows the Trumpet Jazz logo instead of the Late Night Jazz logo.
- **Scope:** Confirmed only on Late Night Jazz so far. User flagged this as "more possible misreads" → there may be additional collisions on other JazzRadio (or sibling-network) channels not yet observed.
- **Source path (per user answers):** Network = JazzRadio (Audio Addict family; user picked DI.fm as the closest source label since the two are sister networks). The fetch is via the AA channel-key → image-map lookup.

## Current Focus

- **hypothesis:** ~~Late Night Jazz's stream URL path segment is being normalized by `_aa_channel_key_from_url` to a key that collides with Trumpet Jazz~~ → **DISPROVEN.** The key derivation is correct (`latenightjazz` for the Late Night URL, `trumpetjazz` for the Trumpet URL). Real cause: AudioAddict's upstream JazzRadio channels API returns the **same `square` image URL** for both Late Night Jazz and Trumpet Jazz (data-quality bug upstream). Our `_fetch_image_map` (`musicstreamer/aa_import.py:73`) prefers `square` over `default`, so the lookup picks the colliding image. The `default` image is correct and channel-specific for both.
- **test:** ~~Print `_aa_channel_key_from_url(<late_night_jazz_stream_url>)`~~ — done; key is correct.
- **expecting:** ~~Derived channel_key incorrectly hits Trumpet Jazz's entry~~ — refuted; lookup uses correct key but the `square` image at that key is shared.
- **next_action:** apply fix in `_fetch_image_map` to prefer `default` over `square` for JazzRadio (or globally), since `default` is correct and channel-specific while `square` is corrupted upstream for these two channels.

## Evidence

- timestamp: 2026-05-09
  finding: User-DB stations confirmed via SQLite query of `~/.local/share/musicstreamer/musicstreamer.sqlite3`:
    - id=607 'Late Night Jazz' streams: `http://prem1.jazzradio.com:80/latenightjazz?...` and `http://prem4.jazzradio.com:80/latenightjazz?...`
    - id=630 'Trumpet Jazz' stream: `http://prem4.jazzradio.com:80/trumpetjazz?...`
  source: SELECT join across stations + station_streams in musicstreamer.sqlite3

- timestamp: 2026-05-09
  finding: `_aa_channel_key_from_url` returns the **correct** keys for both URLs:
    - `_aa_channel_key_from_url('http://prem1.jazzradio.com:80/latenightjazz?...', slug='jazzradio')` → `'latenightjazz'`
    - `_aa_channel_key_from_url('http://prem4.jazzradio.com:80/trumpetjazz?...', slug='jazzradio')` → `'trumpetjazz'`
    - The hypothesis that key derivation was collapsing names is REFUTED. JazzRadio URL paths use bare keys (no prefix), and `_NETWORK_URL_PREFIXES` correctly omits jazzradio (see test_aa_url_detection.py:43-44 expectation `_aa_channel_key_from_url('http://prem1.jazzradio.com:80/afrojazz', 'jazzradio') == 'afrojazz'`).
  source: live python trace using `from musicstreamer.url_helpers import _aa_channel_key_from_url`

- timestamp: 2026-05-09
  finding: AudioAddict JazzRadio API returns BOTH `latenightjazz` (id=510) and `trumpetjazz` (id=103) as distinct channels with distinct `key`, `asset_url`, `images.default`, `images.compact`, and `images.vertical` — all referencing channel-correct images:
    - latenightjazz `default`/`asset_url`: `27b53094587879b41afc3bda7818d1ff.png`
    - trumpetjazz   `default`/`asset_url`: `731ea8de93d76acb76846c6b26982a16.png`
  source: `curl https://api.audioaddict.com/v1/jazzradio/channels` (live API, 2026-05-09)

- timestamp: 2026-05-09
  finding: **Upstream collision:** `images.square` is **identical** for both channels:
    - latenightjazz `square`: `9239265c7c58eb6adaa762f65f13787f.jpg`
    - trumpetjazz   `square`: `9239265c7c58eb6adaa762f65f13787f.jpg`
  This is the smoking gun. `_fetch_image_map` at `musicstreamer/aa_import.py:73` uses `raw = img.get("square") or img.get("default")` — `square` wins, so both keys map to the same JPG. End-to-end trace shows `_fetch_image_map('jazzradio')['latenightjazz'] == _fetch_image_map('jazzradio')['trumpetjazz'] == 'https://cdn-images.audioaddict.com/9/2/3/9/2/6/9239265c7c58eb6adaa762f65f13787f.jpg'`.
  source: live API JSON inspection + end-to-end Python trace through `_fetch_image_map` and `img_map.get(channel_key)`

- timestamp: 2026-05-09
  finding: Audited all 6 AA networks for `square`/`default` image collisions. Results:
    - di (n=119): 0 square collisions, 1 default collision (5 X-prefixed UMF stage channels share a default — likely intentional placeholder for inactive channels)
    - radiotunes (n=119): 0 square, 0 default
    - **jazzradio (n=49): 1 square collision (latenightjazz + trumpetjazz)**, 0 default
    - rockradio (n=48): 0 square, 0 default
    - classicalradio (n=58): 0 square, 0 default
    - zenradio (n=40): 0 square, 0 default
  This is the only `square` collision across the entire AA family. The user's worry about "more possible misreads" is **mostly unfounded** — only Trumpet Jazz / Late Night Jazz are currently affected. (The DI.fm `default` collision is on inactive X-channels and would not surface in the user-DB.)
  source: bulk audit of all 6 `https://api.audioaddict.com/v1/<slug>/channels` endpoints

## Eliminated

- `_aa_channel_key_from_url` is producing a wrong/colliding key for JazzRadio URLs — REFUTED by direct trace; both keys are correct.
- Missing `jazzradio` entry in `_NETWORK_URL_PREFIXES` is the bug — REFUTED. JazzRadio URLs use bare keys (no prefix to strip), so the absence is correct (matches test_aa_url_detection.py:44 expectation).
- Missing `_AA_CHANNEL_KEY_ALIASES` entry for jazzradio — REFUTED. No alias is needed; `latenightjazz` and `trumpetjazz` are the same in URL path and API key.
- Bug in EditStationDialog UI lookup — REFUTED. The dialog calls `_fetch_image_map(slug)` then `img_map.get(channel_key)`; both inputs are correct, so the bug must be in `_fetch_image_map` itself.
- Widespread image-collision pattern — REFUTED. Only this one square-image pair is affected across all 6 networks (49 + 119 + 119 + 48 + 58 + 40 = 433 channels audited).

## Notes

- **Prior related fix:** `.planning/debug/resolved/di-fm-image-fetch-failed.md` (resolved 2026-05-01). That session added `"di": "di_"` to `_NETWORK_URL_PREFIXES` and introduced `_AA_CHANNEL_KEY_ALIASES` with 4 DI.fm legacy → current key pairs. The same code path (`_aa_channel_key_from_url` in `musicstreamer/url_helpers.py`) was the prime suspect here, but is **not** the cause of this bug.
- **Difference from prior bug:** Prior bug was a *fetch failure* (no image at all). This bug is a *silent misread* — fetch succeeds but returns the wrong station's image.
- **JazzRadio context:** JazzRadio.com is part of the AudioAddict network family. API slug = `'jazzradio'`.
- **EditStationDialog:** Calls `_fetch_image_map(slug)` (aa_import.py:58) then `img_map.get(channel_key)`. Bug is upstream of this — in `_fetch_image_map`'s field-priority choice.
- **Upstream-data caveat:** This is a data-quality bug in AudioAddict's `images.square` for two specific JazzRadio channels. It could be reported to AA, but we cannot wait on an upstream fix; the fix has to be on our side.

## Resolution

### Root Cause

`_fetch_image_map` in `musicstreamer/aa_import.py` (line 73) preferred `images.square` over `images.default` when building the channel-key → image-URL map. AudioAddict's JazzRadio channels API returns the **same `square` image URL** for both Trumpet Jazz (`trumpetjazz`, id=103) and Late Night Jazz (`latenightjazz`, id=510), although the `default`, `compact`, and `vertical` images for each channel are correct and channel-specific. Result: when the EditStationDialog logo-fetch worker derived the correct channel key (`latenightjazz`) and looked it up in the image map, it got the shared `square` JPG — which happens to render as the Trumpet Jazz logo.

Audit of all 6 AA networks (433 channels) found this as the only `square` collision in the entire AA family, so the user's "more possible misreads" worry is otherwise unfounded.

### Fix Applied

`musicstreamer/aa_import.py` `_fetch_image_map`:

1. **Image-key priority swap** — `raw = img.get("default") or img.get("square")` (was the inverse). `default` is `asset_url`, which is unique per channel for every audited channel across all 6 networks. Backward-compatible: existing `square`-only fixtures still resolve via the `or` fallthrough.

2. **Scope-collision guard** — `_fetch_image_map` now tracks the set of normalized image URLs as it builds the map and emits a `_log.warning(...)` when two channel keys resolve to the same URL. Format: `"AA image collision in <slug>: channels <a> and <b> share image <url>"`. Catches future upstream regressions before users notice.

3. **Docstring** updated to document image-key priority and the upstream-collision rationale.

### Tests Added

In `tests/test_aa_import.py` (new `_fetch_image_map tests` section, 4 tests):

- `test_fetch_image_map_prefers_default_over_square` — when both fields are present and `square` is collided (the JazzRadio scenario), the resolved URLs are channel-distinct.
- `test_fetch_image_map_falls_back_to_square_when_default_absent` — backward compat for fixtures and channels that only set `square`.
- `test_fetch_image_map_logs_warning_on_collision` — collision guard fires (exactly once, per pair) when two channels share the same normalized URL.
- `test_fetch_image_map_no_warning_when_unique` — no warning when every channel is distinct.

### Verification

- `tests/test_aa_import.py` — 37 passed (33 prior + 4 new)
- `tests/test_aa_url_detection.py` — 36 passed (untouched but verified — same code-family)
- Total: 73 passed, 0 failed.

### Files Changed

- `musicstreamer/aa_import.py` — `_fetch_image_map` field-priority swap + collision guard + docstring
- `tests/test_aa_import.py` — 4 new regression tests

### User-Facing Follow-Up

The on-disk cached logo for Late Night Jazz (downloaded under the old behavior) is the wrong image. To refresh it, re-open EditStationDialog for Late Night Jazz and re-fetch — the dialog will now pull the correct `default` image from `https://cdn-images.audioaddict.com/c/o/r/r/e/c/27b53094587879b41afc3bda7818d1ff.png` and overwrite the cached asset.
