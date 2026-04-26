---
phase: 47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame
reviewed: 2026-04-18T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - musicstreamer/aa_import.py
  - musicstreamer/models.py
  - musicstreamer/player.py
  - musicstreamer/repo.py
  - musicstreamer/settings_export.py
  - musicstreamer/stream_ordering.py
  - musicstreamer/ui_qt/discovery_dialog.py
  - musicstreamer/ui_qt/edit_station_dialog.py
  - tests/test_aa_import.py
  - tests/test_discovery_dialog.py
  - tests/test_edit_station_dialog.py
  - tests/test_player_failover.py
  - tests/test_repo.py
  - tests/test_settings_export.py
  - tests/test_stream_ordering.py
findings:
  critical: 0
  warning: 2
  info: 4
  total: 6
status: issues_found
---

# Phase 47: Code Review Report

**Reviewed:** 2026-04-18
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Phase 47 introduces `bitrate_kbps` on `StationStream`, an `order_streams` pure-function module for failover ordering by (codec_rank desc, bitrate_kbps desc, position asc), a numeric-only bitrate column in the edit dialog, and post-insert fix-ups for import paths (DiscoveryDialog, aa_import multi). The phase's focus areas are in good shape:

- **Schema migration correctness**: The `CREATE TABLE IF NOT EXISTS station_streams` includes `bitrate_kbps INTEGER NOT NULL DEFAULT 0` (repo.py:60), and an idempotent `ALTER TABLE ... ADD COLUMN bitrate_kbps` handles pre-47 DBs (repo.py:86-89). Second-call safety verified by `test_bitrate_kbps_migration_adds_column`.
- **SQL tuple width consistency**: `_insert_station` and `_replace_station` in settings_export.py both use an 8-column insert matching an 8-value tuple (settings_export.py:374-387, 429-442).
- **Post-insert fix-up**: DiscoveryDialog.`_on_save_row` does NOT widen `repo.insert_station` — it inserts then updates the auto-created position=1 stream with `bitrate_kbps` (discovery_dialog.py:421-439). Same pattern in aa_import.import_stations_multi (aa_import.py:190-199).
- **Qt delegate correctness**: `_BitrateDelegate` wires `QIntValidator(0, 9999, parent)` on a `QLineEdit` editor (edit_station_dialog.py:166). Save path coerces via `int(bitrate_text or "0")` with a `ValueError` fallback to 0 (edit_station_dialog.py:707-710) — belt-and-suspenders per D-14.
- **Purity of stream_ordering**: Only imports `StationStream` from models; no Qt, GStreamer, or DB imports. `order_streams` returns a new list and does not mutate input (verified by `test_does_not_mutate_input`).

Findings below are either minor robustness gaps or maintainability suggestions — none are blockers.

## Warnings

### WR-01: `order_streams` crashes if `bitrate_kbps` is `None`

**File:** `musicstreamer/stream_ordering.py:35-36`
**Issue:** The partition uses `s.bitrate_kbps > 0` and `s.bitrate_kbps <= 0`. `StationStream.bitrate_kbps` is typed `int` with default `0`, and the schema declares `NOT NULL DEFAULT 0`, so `None` should not occur in practice. However, any test double or construction path that passes `bitrate_kbps=None` (e.g. a `MagicMock`) raises `TypeError: '>' not supported between instances of 'NoneType' and 'int'` — this would abort failover mid-play. The cost of a None-guard is trivial compared to the crash surface.

**Fix:**
```python
def order_streams(streams: List[StationStream]) -> List[StationStream]:
    known = [s for s in streams if (s.bitrate_kbps or 0) > 0]
    unknown = [s for s in streams if (s.bitrate_kbps or 0) <= 0]
    known_sorted = sorted(
        known,
        key=lambda s: (-codec_rank(s.codec), -(s.bitrate_kbps or 0), s.position),
    )
    unknown_sorted = sorted(unknown, key=lambda s: s.position)
    return known_sorted + unknown_sorted
```

### WR-02: `aa_import.import_stations_multi` writes `first_url` to DB even when `ch["streams"]` is empty

**File:** `musicstreamer/aa_import.py:181-187`
**Issue:** `first_url = ch["streams"][0]["url"] if ch["streams"] else ""`. When `streams` is empty, `repo.insert_station(..., url="")` creates a station with no stream row (`insert_station` short-circuits on empty url — repo.py:415-416). The subsequent `for s in ch["streams"]` loop then does nothing. Net effect: an orphaned station with zero streams gets imported and counted as `imported += 1`. Unlikely given `fetch_channels_multi` never emits empty streams, but if a future caller passes such data it silently pollutes the library.

**Fix:** Skip empty-stream channels explicitly:
```python
if not ch.get("streams"):
    skipped += 1
    if on_progress:
        on_progress(imported, skipped)
    continue
any_exists = any(repo.station_exists_by_url(s["url"]) for s in ch["streams"])
```

## Info

### IN-01: `aa_import._fetch_image_map` swallows 401/403 silently

**File:** `musicstreamer/aa_import.py:43-57`
**Issue:** `_fetch_image_map` uses a bare `except Exception: return {}`. An expired/invalidated listen_key during the image-map fetch would be swallowed, producing channel dicts with `image_url=None` — the user gets partial import with no diagnostic. Other AA network calls raise `invalid_key`, so this is inconsistent. Low priority because image-map is orthogonal to stream access.

**Fix:** Let `urllib.error.HTTPError` with 401/403 propagate; keep broad catch for everything else (network blips).

### IN-02: `aa_import.import_stations_multi` redefines `position_map`/`bitrate_map` per iteration

**File:** `musicstreamer/aa_import.py:136-137`
**Issue:** `position_map` and `bitrate_map` are rebuilt inside the `for quality, tier in QUALITY_TIERS.items()` inner loop — allocating two small dicts on every network×tier iteration (18 times per call). Functionally correct but wasteful. Move them to module scope alongside `QUALITY_TIERS` for clarity and parity with the other AA constants.

**Fix:**
```python
_POSITION_MAP = {"hi": 1, "med": 2, "low": 3}
_BITRATE_MAP = {"hi": 320, "med": 128, "low": 64}  # D-10: DI.fm tier -> kbps
```
Use `_POSITION_MAP[quality]` / `_BITRATE_MAP[quality]` in the loop.

### IN-03: `_BitrateDelegate` upper bound of 9999 is not a hard constraint in the DB

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:166`
**Issue:** `QIntValidator(0, 9999, parent)` caps UI entry at 9999 kbps. The SQLite column is `INTEGER NOT NULL DEFAULT 0` with no CHECK constraint, so the import path (settings_export) or aa_import could legitimately persist values > 9999 (e.g. future FLAC streams at 1411 kbps stereo PCM — fine, but a hypothetical 12000 kbps multichannel case would round-trip through export/import then appear uneditable in the UI). Not a bug today; worth a comment so the cap is intentional.

**Fix:** Add a comment on the validator line referencing the decision (D-13) so the next reader knows 9999 is a display/edit policy, not a domain invariant.

### IN-04: `codec_rank` returns `0` for both empty/unknown and missing — loses information

**File:** `musicstreamer/stream_ordering.py:17-23`
**Issue:** `codec_rank("OPUS")`, `codec_rank("")`, and `codec_rank(None)` all return 0. This is fine for ordering (unknowns tie on codec, broken by bitrate then position), but OPUS is an efficient codec that in principle should rank between AAC and MP3. Future work — not a phase 47 defect.

**Fix:** When OPUS support lands, extend `_CODEC_RANK` with `"OPUS": 2` or similar. No change needed now.

---

_Reviewed: 2026-04-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
