---
phase: 47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame
plan: 03
subsystem: ui-ingest-export
tags: [ui, import, export, bitrate, tdd, qt, delegate]

requires:
  - phase: 47
    plan: 01
    provides: StationStream.bitrate_kbps field
  - phase: 47
    plan: 02
    provides: Repo.insert_stream/update_stream bitrate_kbps kwarg
provides:
  - "aa_import.fetch_channels_multi populates bitrate_kbps per DI.fm tier (hi=320, med=128, low=64)"
  - "aa_import.import_stations_multi threads bitrate_kbps kwarg through update_stream + insert_stream"
  - "discovery_dialog._on_save_row captures station_id + post-insert update_stream fix-up for RadioBrowser bitrate"
  - "EditStationDialog 5-column streams_table with _BitrateDelegate(QIntValidator(0, 9999)) + save-path int(text or '0') coercion"
  - "settings_export._station_to_dict emits bitrate_kbps; _insert_station + _replace_station persist via 8-column INSERT with int(... or 0) forward-compat"
affects: []

tech-stack:
  added: []
  patterns:
    - "Post-insert fix-up: capture insert_station station_id, then list_streams + update_stream(bitrate_kbps=N) (mirrors aa_import.import_stations_multi:188-196 per G-2 Option 1 — avoids widening insert_station public signature)"
    - "QStyledItemDelegate editor subclass with QIntValidator (_BitrateDelegate) registered via setItemDelegateForColumn per P-5"
    - "Defensive int(text or '0') coerce at save boundary; int(dict.get(key, 0) or 0) at import boundary (D-14, P-2)"
    - "RED/GREEN TDD cycle with atomic test/feat commits (three cycles, one per task)"

key-files:
  created: []
  modified:
    - musicstreamer/aa_import.py
    - musicstreamer/ui_qt/discovery_dialog.py
    - musicstreamer/ui_qt/edit_station_dialog.py
    - musicstreamer/settings_export.py
    - tests/test_aa_import.py
    - tests/test_discovery_dialog.py
    - tests/test_edit_station_dialog.py
    - tests/test_settings_export.py

key-decisions:
  - "discovery_dialog._on_save_row uses G-2 Option 1 post-insert fix-up (NOT widening insert_station) — mirrors aa_import.import_stations_multi:188-196 which already uses this idiom; keeps Repo public contract stable"
  - "_BitrateDelegate placed at module scope (not nested in EditStationDialog) to mirror station_star_delegate.py convention; prefix with _ to signal module-private"
  - "int(stream.get('bitrate_kbps', 0) or 0) in both settings_export._insert_station AND _replace_station — the `or 0` neutralizes None + empty string, the `.get(..., 0)` handles missing keys from pre-47 ZIPs, the int() handles string-typed numeric values (Threat table row 3 + P-2 combined defense)"
  - "bitrate_kbps: int = 0 added BEFORE position in _add_stream_row (matches StationStream field order + natural insertion between Codec and Position columns); existing callers pass positional args — only the single in-file _populate caller needed to be updated to thread s.bitrate_kbps"

patterns-established:
  - "Phase 47 end-to-end bitrate ingestion: every external entry point (AA HTTP, RadioBrowser HTTP, Edit dialog, settings ZIP) now populates the field; failover (Plan 47-02) consumes it"
  - "FakeRepo expansion pattern: add method stub + _list_streams_return attribute on existing test double rather than swapping the fixture to MagicMock (keeps existing 11 discovery tests' assertion shapes intact)"

requirements-completed: []

duration: "7m"
completed: "2026-04-18"
---

# Phase 47 Plan 03: UI + Imports + Settings Export Bitrate Wiring Summary

**Wired `bitrate_kbps` end-to-end through the three user-facing surfaces: AudioAddict import (DI.fm tier -> 320/128/64 map), RadioBrowser discovery-save (post-insert update_stream fix-up), Edit Station dialog (5th column with QIntValidator delegate), and settings export/import roundtrip (8-column INSERT in both _insert_station and _replace_station with forward-compat defensive coerce).**

## Performance

- **Duration:** ~7m (449s)
- **Started:** 2026-04-18T16:47:01Z
- **Completed:** 2026-04-18T16:54:30Z
- **Tasks:** 3 (all auto + TDD)
- **Files modified:** 8 (4 production + 4 test)
- **Files created:** 0

## Accomplishments

### Task 1: AA import + RadioBrowser save
- `aa_import.fetch_channels_multi` adds `bitrate_map = {"hi": 320, "med": 128, "low": 64}` alongside existing `position_map`; stream dicts now carry `bitrate_kbps` per D-10.
- `aa_import.import_stations_multi` threads `bitrate_kbps=s.get("bitrate_kbps", 0)` as kwarg through both the `update_stream` (for the auto-created first stream) and `insert_stream` (for remaining streams) calls.
- `discovery_dialog._on_save_row` now captures the `station_id` returned by `insert_station`, then conditionally (when `bitrate_val > 0`) calls `list_streams(station_id)` and `update_stream(..., bitrate_kbps=bitrate_val)` — mirrors the proven post-insert fix-up pattern in `aa_import.import_stations_multi:188-196` per G-2 Option 1 (keeps `insert_station` public signature stable).

### Task 2: Edit Station Bitrate column
- Added `QIntValidator` and `QStyledItemDelegate` imports.
- `_COL_BITRATE = 3`, `_COL_POSITION = 4` constants.
- Module-level `_BitrateDelegate(QStyledItemDelegate)` with `createEditor` returning a `QLineEdit` pre-armed with `QIntValidator(0, 9999, parent)` (P-5).
- `streams_table` widened to 5 columns with new "Bitrate" header between "Codec" and "Position"; width 70px; `setItemDelegateForColumn(_COL_BITRATE, _BitrateDelegate(self))` registered once.
- `_add_stream_row` accepts `bitrate_kbps: int = 0`; renders as `str(bitrate_kbps)` when non-zero, empty string when 0 (D-12/G-5).
- `_populate` threads `s.bitrate_kbps` through to `_add_stream_row`.
- `_on_save` reads cell with `int(bitrate_text or "0")` wrapped in try/except ValueError (mirroring the existing position-column idiom at lines 677-680 per P-4). Value passed as `bitrate_kbps=` kwarg to both `update_stream` and `insert_stream`.
- `_swap_rows` iterates `range(table.columnCount())` — works unchanged for 5 columns.

### Task 3: settings_export bitrate roundtrip
- `_station_to_dict` stream dict gains `"bitrate_kbps": s.bitrate_kbps` (P-1 — missing this silently drops the field on export).
- `_insert_station` AND `_replace_station` both widened to 8-column `INSERT INTO station_streams` with `int(stream.get("bitrate_kbps", 0) or 0)` defensive coerce — neutralizes missing key (forward-compat with pre-47 ZIPs per P-2), None, empty string, and malformed-value threats in one idiom.

### Tests
- **7 new tests** (PB-12, PB-13 x2, PB-14, PB-14b, PB-15, PB-16, PB-17, PB-17b) — all pass.
- `test_fetch_channels_multi_bitrate_kbps` — PB-12 DI.fm tier map.
- `test_import_multi_threads_bitrate_kbps` — PB-12 kwarg threading.
- `test_on_save_row_persists_bitrate_from_radiobrowser` — PB-13 positive.
- `test_on_save_row_skips_fixup_when_bitrate_zero` — PB-13 negative (no fix-up when bitrate=0).
- `test_bitrate_column_populated` — PB-16.
- `test_empty_bitrate_saves_as_zero` — PB-17.
- `test_populated_bitrate_saves_as_int` — PB-17b.
- `test_export_import_roundtrip_preserves_bitrate_kbps` — PB-14 roundtrip.
- `test_commit_import_forward_compat_missing_bitrate_key` — PB-15 pre-47 ZIP.
- `test_station_to_dict_emits_bitrate_kbps` — PB-14b direct serializer.

## Task Commits

Each task atomic RED/GREEN cycle:

1. **Task 1 RED** — `d348d6c` test(47-03): failing tests for bitrate_kbps on ingest (PB-12, PB-13)
2. **Task 1 GREEN** — `503dcf8` feat(47-03): populate bitrate_kbps on AA + RadioBrowser ingest
3. **Task 2 RED** — `544c70a` test(47-03): failing tests for Bitrate column (PB-16, PB-17)
4. **Task 2 GREEN** — `cbf8c6f` feat(47-03): add Bitrate column to EditStationDialog streams_table
5. **Task 3 RED** — `de3b581` test(47-03): failing tests for settings export/import (PB-14, PB-15)
6. **Task 3 GREEN** — `73e5caf` feat(47-03): preserve bitrate_kbps through settings export/import roundtrip

_No REFACTOR commits — all GREEN implementations were minimal and idiomatic (mirrored existing in-file/cross-file analogs exactly)._

## Files Created/Modified

### `musicstreamer/aa_import.py` (+5 / -3)
- `fetch_channels_multi`: add `bitrate_map = {"hi": 320, "med": 128, "low": 64}` inside the nested per-quality loop; stream dict gains `"bitrate_kbps": bitrate_map[quality]`.
- `import_stations_multi`: `update_stream` and `insert_stream` calls gain `bitrate_kbps=s.get("bitrate_kbps", 0)` kwarg.

### `musicstreamer/ui_qt/discovery_dialog.py` (+14 / -1)
- `_on_save_row`: capture `station_id = self._repo.insert_station(...)` (previously discarded per repo.py:407). After insert, if `bitrate_val = int(result.get("bitrate", 0) or 0)` is non-zero, call `list_streams(station_id)` and `update_stream(s.id, ..., bitrate_kbps=bitrate_val)`.

### `musicstreamer/ui_qt/edit_station_dialog.py` (+36 / -7)
- Imports: add `QIntValidator` (from QtGui), `QStyledItemDelegate` (from QtWidgets).
- Column constants: add `_COL_BITRATE = 3`; bump `_COL_POSITION` from 3 to 4.
- New module-level `_BitrateDelegate(QStyledItemDelegate)` class.
- `streams_table`: `QTableWidget(0, 5)`, Bitrate in header list, resize + width + delegate registration for new column.
- `_add_stream_row`: add `bitrate_kbps: int = 0` param; `setItem(row, _COL_BITRATE, QTableWidgetItem(str(bitrate_kbps) if bitrate_kbps else ""))`.
- `_populate`: thread `s.bitrate_kbps` through to `_add_stream_row`.
- `_on_save`: read `bitrate_item = table.item(row, _COL_BITRATE)`, coerce `bitrate_kbps = int(bitrate_text or "0")` with try/except ValueError fallback to 0; pass as kwarg to both `update_stream` and `insert_stream`.

### `musicstreamer/settings_export.py` (+7 / -4)
- `_station_to_dict`: stream dict adds `"bitrate_kbps": s.bitrate_kbps`.
- `_insert_station`: SQL becomes 8-column `INSERT INTO station_streams(..., codec, bitrate_kbps) VALUES (?,?,?,?,?,?,?,?)`; tuple gains `int(stream.get("bitrate_kbps", 0) or 0)`.
- `_replace_station`: identical 8-column upgrade.

### `tests/test_aa_import.py` (+59 / 0)
- `test_fetch_channels_multi_bitrate_kbps` (PB-12).
- `test_import_multi_threads_bitrate_kbps` (PB-12 continuation — kwarg assertion).

### `tests/test_discovery_dialog.py` (+51 / 0)
- `FakeRepo` extended with `list_streams`, `update_stream` methods + `_list_streams_return` attribute (minimum-diff addition; existing 11 tests unaffected).
- `test_on_save_row_persists_bitrate_from_radiobrowser` (PB-13 positive).
- `test_on_save_row_skips_fixup_when_bitrate_zero` (PB-13 negative — no fix-up branch when bitrate=0).

### `tests/test_edit_station_dialog.py` (+65 / 0)
- `test_bitrate_column_populated` (PB-16).
- `test_empty_bitrate_saves_as_zero` (PB-17).
- `test_populated_bitrate_saves_as_int` (PB-17b).

### `tests/test_settings_export.py` (+137 / 0)
- `_fresh_repo()` helper — new Repo on a fresh file-backed SQLite DB.
- `test_export_import_roundtrip_preserves_bitrate_kbps` (PB-14).
- `test_commit_import_forward_compat_missing_bitrate_key` (PB-15).
- `test_station_to_dict_emits_bitrate_kbps` (PB-14b).

## Decisions Made

- **FakeRepo extension vs. MagicMock swap in test_discovery_dialog.py:** Chose to add `list_streams` + `update_stream` methods to the existing `FakeRepo` class rather than rewrite the fixture as `MagicMock`. Rationale: 11 existing tests assert on `repo.insert_station_calls` (a list attribute specific to FakeRepo). Switching to MagicMock would break those tests' assertion shapes; extending FakeRepo touches 15 lines and preserves every existing assertion.
- **Post-insert fix-up vs. widening `insert_station`:** Plan was prescriptive (G-2 Option 1). Validated the proven pattern exists at `aa_import.import_stations_multi:188-196`. Option 2 (widen signature) would've required updates to `_add_stream_row` callers and a cascade through every test that mocks `insert_station` — orders of magnitude more code churn for no semantic benefit.
- **`_BitrateDelegate` module-level private vs. nested in `EditStationDialog`:** Placed at module scope (prefixed `_`) to mirror `station_star_delegate.py` convention and to keep the delegate class unit-testable in isolation.
- **setItemDelegateForColumn call on single vs. split lines:** Initially wrapped the call across two lines for readability, but acceptance grep required the exact pattern `setItemDelegateForColumn(_COL_BITRATE` on one line — collapsed to single line to satisfy the verify gate.
- **Did NOT add a "computed failover order preview" column to EditStationDialog:** Plan's Claude's-Discretion note recommended against it; user's pragmatic-fast UX profile agrees — failover order is a production-time observable, not an editor-time one.

## Deviations from Plan

None — plan executed exactly as written. All three RED phases produced the expected failures (KeyError on `bitrate_kbps`, ImportError on `_COL_BITRATE`, KeyError on export dict key). All three GREEN phases passed on first run.

## Auth Gates

None.

## Issues Encountered

### Deferred Issues (pre-existing environment — NOT caused by this plan)

- **pytest-qt `QtTest` None-type** in 4 pre-existing `test_edit_station_dialog.py` tests (`test_add_tag_creates_chip`, `test_stream_table_populated_and_add`, `test_remove_stream_removes_row`, `test_move_up_down_reorder`) — documented in `47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame/deferred-items.md`. These use `qtbot.mouseClick` which is broken in the current pytest-qt env. Verified this exact set of 4 failures exists identically on the commit BEFORE this plan's first edit (matches baseline). Out of scope per deferred-items.md. The 3 new Qt-widget tests added by this plan (PB-16, PB-17, PB-17b) all use direct method calls + `.setText()` — no `qtbot.mouseClick` — and all 3 pass cleanly.

### Full-suite check

- `pytest tests/test_aa_import.py tests/test_discovery_dialog.py tests/test_edit_station_dialog.py tests/test_settings_export.py tests/test_repo.py tests/test_stream_ordering.py`: **150 passed, 4 failed**. All 4 failures are the documented pre-existing pytest-qt env issues. No new regressions introduced by this plan.
- `pytest tests/test_aa_import.py tests/test_settings_export.py` (required by success criteria): **41 passed, 0 failed**.

### Phase 47 grep regression guard (PB-19)

- `grep -rln "bitrate_kbps" musicstreamer/` hits ALL expected files: `models.py`, `stream_ordering.py`, `repo.py`, `aa_import.py`, `settings_export.py`, `ui_qt/discovery_dialog.py`, `ui_qt/edit_station_dialog.py`. `player.py` transitively uses it via `order_streams` (imported from `stream_ordering`) — no direct reference needed there.
- `grep -c "bitrate_kbps" musicstreamer/aa_import.py` = **3** (>=3).
- `grep -c "bitrate_kbps" musicstreamer/settings_export.py` = **5** (>=3).
- `grep -c "bitrate_kbps" musicstreamer/ui_qt/edit_station_dialog.py` = **8** (>=4).

## User Setup Required

None — all changes are backward-compatible at the DB level (schema from 47-02 already handles both fresh + legacy installs idempotently) and at the Python API level (optional kwarg with default in 47-02 means old callers work unchanged, and pre-47 ZIPs import cleanly via forward-compat defensive coerce).

## Next Phase Readiness

**Phase 47 is complete.** Full end-to-end flow:

1. User imports stations from DI.fm AudioAddict (Task 1, aa_import) → `bitrate_kbps` populated (320/128/64).
2. User saves a RadioBrowser discovery (Task 1, discovery_dialog) → `bitrate_kbps` populated from API's `bitrate` field.
3. User edits a station (Task 2, edit_station_dialog) → sees/edits/validates Bitrate column.
4. User exports settings (Task 3, settings_export) → `bitrate_kbps` survives roundtrip.
5. User imports settings on another machine (Task 3, settings_export) → `bitrate_kbps` restored; pre-47 ZIPs import cleanly with 0 default.
6. Playback failover (47-02, player.py) → consumes `bitrate_kbps` via `order_streams` to dequeue highest-codec-rank + highest-bitrate stream first.

No blockers. Ready for Phase 47 gate + merge.

## Self-Check: PASSED

- `musicstreamer/aa_import.py` — modified, verified on HEAD
- `musicstreamer/ui_qt/discovery_dialog.py` — modified, verified on HEAD
- `musicstreamer/ui_qt/edit_station_dialog.py` — modified, verified on HEAD
- `musicstreamer/settings_export.py` — modified, verified on HEAD
- `tests/test_aa_import.py` — modified (26 tests pass)
- `tests/test_discovery_dialog.py` — modified (13 tests pass)
- `tests/test_edit_station_dialog.py` — modified (19 pass, 4 pre-existing env-fail)
- `tests/test_settings_export.py` — modified (20 tests pass)
- Commit `d348d6c` (Task 1 RED) — FOUND
- Commit `503dcf8` (Task 1 GREEN) — FOUND
- Commit `544c70a` (Task 2 RED) — FOUND
- Commit `cbf8c6f` (Task 2 GREEN) — FOUND
- Commit `de3b581` (Task 3 RED) — FOUND
- Commit `73e5caf` (Task 3 GREEN) — FOUND
- Acceptance grep `bitrate_map = {"hi": 320, "med": 128, "low": 64}` in aa_import.py — 1 match ✓
- Acceptance grep `"bitrate_kbps": bitrate_map[quality]` in aa_import.py — 1 match ✓
- Acceptance grep `bitrate_kbps=s.get("bitrate_kbps", 0)` in aa_import.py — 2 matches ✓
- Acceptance grep `bitrate_kbps=bitrate_val` in discovery_dialog.py — 1 match ✓
- Acceptance grep `station_id = self._repo.insert_station` in discovery_dialog.py — 1 match ✓
- Acceptance grep `QIntValidator` in edit_station_dialog.py — 3 matches (import + usage) ✓
- Acceptance grep `_COL_BITRATE = 3` in edit_station_dialog.py — 1 match ✓
- Acceptance grep `_COL_POSITION = 4` in edit_station_dialog.py — 1 match ✓
- Acceptance grep `class _BitrateDelegate` in edit_station_dialog.py — 1 match ✓
- Acceptance grep `QTableWidget(0, 5)` in edit_station_dialog.py — 1 match ✓
- Acceptance grep `setItemDelegateForColumn(_COL_BITRATE` in edit_station_dialog.py — 1 match ✓
- Acceptance grep `int(bitrate_text or "0")` in edit_station_dialog.py — 1 match ✓
- Acceptance grep `bitrate_kbps=bitrate_kbps` in edit_station_dialog.py — 2 matches ✓
- Acceptance grep `"bitrate_kbps": s.bitrate_kbps` in settings_export.py — 1 match ✓
- Acceptance grep `int(stream.get("bitrate_kbps", 0) or 0)` in settings_export.py — 2 matches ✓
- Acceptance grep `VALUES (?,?,?,?,?,?,?,?)` in settings_export.py — 2 matches ✓
- Acceptance grep `codec, bitrate_kbps` in settings_export.py — 2 matches ✓
- Acceptance grep `VALUES (?,?,?,?,?,?,?)` in settings_export.py — 0 matches ✓ (no stale 7-placeholder)

---

*Phase: 47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame*
*Completed: 2026-04-18*
