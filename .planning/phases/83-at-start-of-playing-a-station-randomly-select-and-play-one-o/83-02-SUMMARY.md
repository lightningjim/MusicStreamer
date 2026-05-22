---
phase: 83-at-start-of-playing-a-station-randomly-select-and-play-one-o
plan: 02
status: complete
completed_at: 2026-05-22
files_modified:
  - musicstreamer/soma_import.py
  - tests/test_soma_import.py
tags: [phase-83, soma-import, preroll, fetch-channels, import-stations, prerolls-fetched-at]
---

# Phase 83 Plan 02 — SUMMARY

## What landed

SomaFM importer extension: `fetch_channels` now surfaces the upstream `preroll[]` array as `preroll_urls` on each channel dict; `import_stations` inserts one `station_prerolls` row per URL and stamps `prerolls_fetched_at` once per imported channel (D-04 marker semantics — even for empty preroll lists). All new writes land INSIDE the existing per-channel rollback window so a mid-step exception still triggers `delete_station` + CASCADE on `station_prerolls` (Pitfall 4 mitigation). Per-channel cap of 50 preroll inserts enforced with `_log.warning` for excess; channel still imports.

One-liner: SomaFM preroll data-capture path; without it, Plan 83-03's Player can never play prerolls on freshly-imported or re-imported SomaFM stations.

## Key file:line landmarks

### `musicstreamer/soma_import.py`
- **`import time` (line 26)** — newly added to the stdlib import block (was previously absent). Needed for the `int(time.time())` argument to `set_prerolls_fetched_at`.
- **`"preroll_urls": ch.get("preroll", [])` (line 244)** — appended one new key to the channel dict literal returned by `fetch_channels`. Verbatim per Pitfall 7 — no URL decode, no normalization.
- **Preroll block in `import_stations` (lines 339–356)** — sits BETWEEN `imported += 1` (line 338) and the existing rollback sentinel clear `inserted_station_id = None` (line 360). The block:
  - Reads `ch.get("preroll_urls", [])` (line 344)
  - Caps at 50 entries with `_log.warning` citing channel title + original length (lines 345–351) — `preroll_urls[:50]` (line 351)
  - Loops `repo.insert_preroll(station_id, preroll_url, pos)` with positions monotone from 1 (line 352)
  - Calls `repo.set_prerolls_fetched_at(station_id, int(time.time()))` exactly once (line 356) — fires EVEN when `preroll_urls == []` (D-04 marker semantics)
- Pitfall 4 invariant: the preroll block lands STRICTLY between the streams loop (ends at line 337) and the rollback sentinel clear (line 360). A mid-step exception (logo enqueue at line 364, on_progress callback at line 384) still triggers `delete_station(inserted_station_id)` + CASCADE on `station_prerolls`.

### `tests/test_soma_import.py`
- **8 new tests appended (~421 lines)** after the existing Phase 74.1 bitrate-slug tests, all anchored to VALIDATION.md row names verbatim:
  1. `test_fetch_channels_returns_preroll_urls_when_upstream_has_preroll` — Beat Blender shape (3 m4a URLs); verbatim list round-trip.
  2. `test_fetch_channels_returns_empty_preroll_urls_for_channels_without_preroll` — Seven Inch Soul shape (no key); defaults to `[]`.
  3. `test_fetch_channels_preserves_url_encoded_spaces_in_preroll` — Pitfall 7; `%20` survives round-trip.
  4. `test_import_calls_insert_preroll_per_url_in_position_order` — 3-channel; channel 1 has 2 prerolls; assert `[(101, url1, 1), (101, url2, 2)]` exactly.
  5. **`test_import_sets_prerolls_fetched_at_for_empty_preroll`** — D-04 **canonical anchor** (name verbatim per VALIDATION.md row 47); single empty-preroll channel; asserts `set_prerolls_fetched_at.call_count == 1` AND `insert_preroll.call_count == 0`.
  6. `test_import_sets_prerolls_fetched_at_for_every_imported_channel` — D-04 companion guard; 3-channel (populated + empty + empty); asserts `set_prerolls_fetched_at.call_count == 3`.
  7. `test_import_caps_preroll_at_50_per_channel_and_emits_warning` — T-83-02 DoS; 55 prerolls; asserts exactly 50 `insert_preroll` calls + single warning citing `"55"` + still imports.
  8. `test_import_rolls_back_prerolls_via_cascade_when_stream_insert_raises_mid_channel` — Pitfall 4 ordering invariant; channel 2's `insert_stream` raises mid-loop; asserts `insert_preroll` NEVER called for channel 2 (proves prerolls land AFTER streams), `delete_station(502)` called, channel 1 prerolls inserted normally.

- New helper added: `_make_channel_with_preroll(channel_id, title, preroll=None)` — builds a single SomaFM channel dict in the upstream `channels.json` shape; `preroll=None` omits the key (legitimately-empty case).

- **No new fixture files added under `tests/fixtures/`** — all preroll fixtures inlined via `json.dumps` + `_urlopen_factory` (acceptable per plan; reuses the existing pattern).

## Verification

| Command | Result |
|---------|--------|
| `uv run pytest tests/test_soma_import.py -k "preroll" -x -q` | 8 passed |
| `uv run pytest tests/test_soma_import.py::test_import_sets_prerolls_fetched_at_for_empty_preroll -x -q` (VALIDATION.md D-04 row) | 1 passed |
| `uv run pytest tests/test_soma_import.py -x -q` | 23 passed (15 existing Phase 74/74.1 + 8 new) |
| `uv run pytest tests/test_player.py tests/test_soma_import.py tests/test_repo.py -q` | 136 passed (128 main + 8 new) |
| `grep -c '"preroll_urls":' musicstreamer/soma_import.py` | 1 |
| `grep -c 'repo.insert_preroll' musicstreamer/soma_import.py` | 1 |
| `grep -c 'repo.set_prerolls_fetched_at' musicstreamer/soma_import.py` | 1 |
| `grep -c 'preroll_urls\[:50\]' musicstreamer/soma_import.py` | 1 |
| `grep -c '^import time$' musicstreamer/soma_import.py` | 1 |
| `grep -c 'def test_.*preroll' tests/test_soma_import.py` | 8 |
| `grep -c 'def test_import_sets_prerolls_fetched_at_for_empty_preroll' tests/test_soma_import.py` | 1 |
| `grep -c 'def test_import_sets_prerolls_fetched_at_for_every_imported_channel' tests/test_soma_import.py` | 1 |

## Pitfall 4 invariant confirmation

The new preroll block sits STRICTLY between the streams loop and the rollback sentinel clear:

```
line 337  (end of streams loop)
line 338  imported += 1
line 339      # Phase 83 D-02 / D-04 / T-83-02 / Pitfall 4 (comment header)
...
line 352      repo.insert_preroll(station_id, preroll_url, pos)
...
line 356      repo.set_prerolls_fetched_at(station_id, int(time.time()))
line 357      # All streams + prerolls inserted ... clear the rollback sentinel
line 360      inserted_station_id = None
line 363      if ch.get("image_url"):
line 364          logo_targets.append((station_id, ch["image_url"]))
```

A raise inside the logo append (or any later step in the channel-success branch) still hits the outer `except Exception` with `inserted_station_id` set, which triggers `delete_station(inserted_station_id)` → CASCADE clears `station_prerolls` rows.

## D-04 canonical test name

Confirmed: `test_import_sets_prerolls_fetched_at_for_empty_preroll` (verbatim, no alias, no parenthetical) — matches VALIDATION.md row 47 exactly. Companion guard `test_import_sets_prerolls_fetched_at_for_every_imported_channel` lives alongside for cross-channel marker assertion.

## `time` import confirmation

`time` was NOT previously imported in `musicstreamer/soma_import.py`. Added at line 26 in the stdlib band (alphabetical position between `tempfile` and `urllib.error`).

## Deviations from Plan

None — plan executed exactly as written. The plan body lists "7 new tests" in success_criteria but the canonical names list contains 8 names; I implemented all 8 (D-04 canonical + D-04 companion guard + 6 others). The `<done>` block uses `>= 7` so 8 satisfies both readings.

## Self-Check: PASSED

All commits exist and target files are present:
- `eeae31c` feat(83-02): capture preroll_urls in fetch_channels + import time stdlib
- `49b3575` feat(83-02): insert station_prerolls + set_prerolls_fetched_at in import_stations
- `3be6633` test(83-02): add 8 preroll tests to tests/test_soma_import.py

Files verified:
- `musicstreamer/soma_import.py` — present; grep counts all = 1
- `tests/test_soma_import.py` — present; 8 new preroll tests + canonical test name present

## Followups for downstream

- Plan 83-03 (Player layer) can now consume `Station.prerolls` (eager-loaded by Plan 83-01) and `Station.prerolls_fetched_at` (now populated by this plan for every freshly-imported SomaFM station). The throttle gate + provider gate logic specified in Phase 83 CONTEXT D-11/D-12 has all the data it needs.
- Re-import safety (Phase 74): when a SomaFM station is deleted and re-imported, the new station row gets fresh `station_prerolls` rows AND a fresh `prerolls_fetched_at` timestamp because `set_prerolls_fetched_at` always fires inside the `else:` branch (which runs for every cleanly-imported channel). The throttle gate will NOT misclassify the freshly-imported channel as "never fetched."
- D-03 on-demand backfill path is NOT implemented by this plan — that's Plan 83-03's responsibility. Pre-existing SomaFM stations whose row was inserted before Phase 83 still have `prerolls_fetched_at IS NULL`; Plan 83-03 detects that and schedules the background fetch.
