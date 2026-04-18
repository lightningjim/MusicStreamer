---
phase: 47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame
verified: 2026-04-18T22:00:00Z
status: passed
score: 15/15 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 11/11
  gaps_closed:
    - "UAT gap 1: empty-cell Bitrate commits as 0 (plan 04)"
    - "UAT gap 5: cascading GStreamer bus errors coalesce into one queue advance (plan 05)"
    - "UAT gap 2: AA PLS fallback URL preserved (plan 06)"
    - "UAT gap 3: AA codec map corrected to ground truth hi=MP3/med=AAC/low=AAC (plan 07)"
    - "REVIEW WR-01: quality_rank primary sort key prevents med-AAC-128 from beating hi-MP3-320 (commit 1961775)"
  gaps_remaining: []
  regressions: []
---

# Phase 47: Stream bitrate quality ordering — Post Gap-Closure Verification

**Phase Goal:** Stream bitrate quality ordering — add `bitrate_kbps` to StationStream; failover orders by (quality, codec, bitrate); wired through AA import, RadioBrowser discovery, Edit Station dialog, and settings export. Gap-closure plans 04-07 addressed UAT gaps 1/2/3/5 and review WR-01.
**Verified:** 2026-04-18T22:00:00Z
**Status:** passed
**Re-verification:** Yes — post gap-closure (plans 04-07 + WR-01 follow-up)

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
| -- | ----- | ------ | -------- |
| 1  | `stream_ordering.py` exports `order_streams`, `codec_rank`, `quality_rank` | PASSED | `stream_ordering.py:25,34,43`; imported at `tests/test_stream_ordering.py:7` as `from musicstreamer.stream_ordering import codec_rank, order_streams, quality_rank` |
| 2  | `order_streams` sort key is (quality_rank desc, codec_rank desc, bitrate_kbps desc, position asc) with unknowns last | PASSED | `stream_ordering.py:52-63` — partitions by `(s.bitrate_kbps or 0) > 0`, sorts known by `(-quality_rank, -codec_rank, -bitrate, position)`, sorts unknown by position, concatenates known+unknown |
| 3  | `codec_rank` returns FLAC=3 AAC=2 MP3=1 other=0 case-insensitively | PASSED | `stream_ordering.py:18` `_CODEC_RANK = {"FLAC": 3, "AAC": 2, "MP3": 1}`; `:31` `(codec or "").strip().upper()`. 10 parametrized tests pass incl. FLAC/flac/whitespace/None |
| 4  | `quality_rank` returns hi=3 med=2 low=1 other=0 case-insensitively (WR-01 fix) | PASSED | `stream_ordering.py:22` `_QUALITY_RANK = {"hi": 3, "med": 2, "low": 1}`; `:40` `(quality or "").strip().lower()`. 10 parametrized tests pass incl. hi/HI/whitespace/premium/None |
| 5  | `StationStream.bitrate_kbps: int = 0` field present | PASSED | `models.py:21` `bitrate_kbps: int = 0     # numeric bitrate in kbps; 0 = unknown (D-01)` |
| 6  | `station_streams` has `bitrate_kbps INTEGER NOT NULL DEFAULT 0` in CREATE TABLE and ALTER TABLE | PASSED | `repo.py:60` (inside CREATE TABLE); `repo.py:86` ALTER in try/except migration block |
| 7  | `player.py` uses `order_streams(station.streams)` for failover queue | PASSED | `player.py:36` import; `player.py:169` `streams_by_position = order_streams(station.streams)` |
| 8  | `player.py::_handle_gst_error_recovery` has in-flight guard coalescing multiple bus errors per URL into ONE queue advance (gap 5) | PASSED | `player.py:139` `_recovery_in_flight: bool = False` init; `:267-269` guard check + set; `:279,282` `QTimer.singleShot(0, self._clear_recovery_guard)` on both twitch + main paths; `:284-289` `_clear_recovery_guard`; resets at `:158,192,201,210` (play/play_stream/pause/stop). Both regression tests `test_multiple_gst_errors_advance_queue_once` + `test_recovery_guard_resets_between_distinct_url_failures` PASS |
| 9  | `aa_import.py::_resolve_pls` returns ALL `FileN=` entries (primary + fallback) (gap 2) | PASSED | `aa_import.py:23` `def _resolve_pls(pls_url: str) -> list[str]`; `:37` `re.match(r"^File(\d+)=(.+)$"`; `:42-43` sort + return list. Tests `test_resolve_pls_returns_all_entries` + `test_resolve_pls_single_entry` PASS |
| 10 | `aa_import.py::_CODEC_MAP` is `{"hi": "MP3", "med": "AAC", "low": "AAC"}` (gap 3, ground truth) | PASSED | `aa_import.py:110` `_CODEC_MAP = {"hi": "MP3", "med": "AAC", "low": "AAC"}`. No remaining `"AAC" if tier == "premium_high" else "MP3"` ternary in file. Test `test_fetch_channels_multi_codec_map_ground_truth` PASSES |
| 11 | `aa_import.py::fetch_channels_multi` emits one stream per PLS URL with `bitrate_kbps` from `_BITRATE_MAP` | PASSED | `aa_import.py:190-198` `tier_base = _POSITION_MAP[quality]; for pls_index, url in enumerate(stream_urls, start=1): append({"url": url, ..., "position": tier_base * 10 + pls_index, "codec": _CODEC_MAP[quality], "bitrate_kbps": _BITRATE_MAP[quality]})`. Test `test_fetch_channels_multi_preserves_primary_and_fallback` PASSES (6 streams/channel for 3-tier × 2-URL PLS) |
| 12 | `discovery_dialog._on_save_row` post-insert fix-up calls `update_stream` with bitrate | PASSED | `discovery_dialog.py:421` `station_id = self._repo.insert_station(name=..., url=..., provider_name=..., tags=...)` (4 kwargs — unchanged); `:430-439` post-insert `list_streams` + `update_stream(..., bitrate_kbps=bitrate_val)` when `bitrate_val > 0` |
| 13 | Edit Station 5-column `streams_table` with `_BitrateDelegate`; `_BitrateDelegate.setModelData` override persists empty text as 0 (gap 1) | PASSED | `edit_station_dialog.py:151` `_COL_BITRATE = 3`; `:155-181` `class _BitrateDelegate(QStyledItemDelegate)` with `createEditor` (QIntValidator 0-9999) AND `setModelData(editor, model, index): model.setData(index, editor.text(), Qt.EditRole)` explicit override; `:322` `setItemDelegateForColumn(_COL_BITRATE, _BitrateDelegate(self))`; `:730-732` `int(bitrate_text or "0")` defensive coerce. Test `test_bitrate_delegate_persists_empty_string_on_commit` PASSES |
| 14 | `settings_export.py::_station_to_dict` emits `bitrate_kbps`; import uses `.get("bitrate_kbps", 0)` for forward-compat | PASSED | `settings_export.py:119` `"bitrate_kbps": s.bitrate_kbps` in serializer; `:375,431` 8-col INSERT in both `_insert_station` and `_replace_station` paths; `:385,441` `int(stream.get("bitrate_kbps", 0) or 0)` defensive coerce |
| 15 | All phase-47 tests pass (ignore documented pre-existing env failures: QtTest=None, missing yt_dlp/streamlink, missing gi) | PASSED | `pytest tests/test_stream_ordering.py tests/test_aa_import.py tests/test_settings_export.py tests/test_repo.py -q` → **136 passed, 0 failed in 0.71s**. The 7 gap-closure regression tests each pass individually. 6 Qt-dep failures in test_edit_station_dialog + test_player_failover are pre-existing env-only (`'NoneType' object has no attribute 'QTest'`) — exactly as documented in `deferred-items.md` |

**Score:** 15/15 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `musicstreamer/stream_ordering.py` | Pure module with codec_rank, quality_rank, order_streams | PASSED | 65 lines; imports only `typing.List` + `musicstreamer.models`; wired at `player.py:36` |
| `musicstreamer/models.py` | `StationStream.bitrate_kbps` field | PASSED | Line 21 default 0 |
| `musicstreamer/repo.py` | Schema CREATE + ALTER migration + CRUD widening | PASSED | Lines 60, 86, 183, 188-200 |
| `musicstreamer/player.py` | `order_streams` + `_recovery_in_flight` guard | PASSED | Lines 36, 139, 158-210 (4 resets), 169, 258, 260-289 |
| `musicstreamer/aa_import.py` | `_resolve_pls`→list, `_CODEC_MAP`, `fetch_channels_multi` per-URL emit | PASSED | Lines 23-46, 102-110, 148-203 |
| `musicstreamer/ui_qt/discovery_dialog.py` | Post-insert fix-up with bitrate | PASSED | Lines 421, 430-439 |
| `musicstreamer/ui_qt/edit_station_dialog.py` | 5-col table + _BitrateDelegate with setModelData override | PASSED | Lines 151, 155-181, 316-328, 722-748 |
| `musicstreamer/settings_export.py` | 8-col INSERT in both paths | PASSED | Lines 119, 375-385, 431-441 |
| `tests/test_stream_ordering.py` | 32 tests incl. quality_rank + WR-01 regressions | PASSED | 32 passed |
| `tests/test_aa_import.py` | Gap-closure regressions for PLS + codec ground truth | PASSED | 4 new tests pass |
| `tests/test_player_failover.py` | Gap-closure regressions for error-cascade coalescing | PASSED | 2 new tests pass |
| `tests/test_edit_station_dialog.py` | Delegate-path empty-cell regression | PASSED | New test passes; 4 other failures are pre-existing Qt env issue |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `player.py::play` | `stream_ordering.order_streams` | import + call | WIRED | `player.py:36,169` |
| `player.py::_on_gst_error` | `_handle_gst_error_recovery` | `QTimer.singleShot(0, ...)` | WIRED | `player.py:258` |
| `player.py::_handle_gst_error_recovery` | `_recovery_in_flight` + `_clear_recovery_guard` | guard check + deferred clear | WIRED | `player.py:267-282` |
| `play`/`play_stream`/`pause`/`stop` | `_recovery_in_flight = False` | reset co-located with queue reset | WIRED | 4 sites: lines 158, 192, 201, 210 |
| `fetch_channels_multi` stream loop | `_resolve_pls` (list) | `for pls_index, url in enumerate(stream_urls, start=1)` | WIRED | `aa_import.py:177,191` |
| `fetch_channels_multi` stream dict | `_CODEC_MAP[quality]` | lookup replacing ternary | WIRED | `aa_import.py:196` |
| `fetch_channels` (legacy) | `_resolve_pls[0]` | first element unwrap (backwards compat) | WIRED | `aa_import.py:135-136` |
| `discovery_dialog._on_save_row` | `repo.update_stream` | post-insert fix-up with `bitrate_kbps=` | WIRED | `discovery_dialog.py:430-439` |
| `_BitrateDelegate.setModelData` | QTableWidget item at `_COL_BITRATE` | `model.setData(index, editor.text(), Qt.EditRole)` | WIRED | `edit_station_dialog.py:181` |
| Edit Station save path | `int(text or "0")` | defensive coerce on commit | WIRED | `edit_station_dialog.py:730-732` |
| `settings_export._station_to_dict` | JSON export | dict key `bitrate_kbps` | WIRED | `settings_export.py:119` |
| settings import | `station_streams` 8-col INSERT | `.get("bitrate_kbps", 0)` | WIRED | `settings_export.py:375-385,431-441` |
| DB `station_streams.bitrate_kbps` | `StationStream.bitrate_kbps` | `list_streams` hydration | WIRED | `repo.py:183` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `order_streams` output | sorted list | `station.streams` (hydrated from DB row with real bitrate_kbps column) | Yes — real DB data, populated by AA import / Edit Station / settings import | FLOWING |
| `_BitrateDelegate` table cell | editor.text() → item text | User input via QLineEdit; reloaded from `StationStream.bitrate_kbps` on dialog open (line 399) | Yes — real round-trip through repo | FLOWING |
| `fetch_channels_multi` stream dicts | `_CODEC_MAP[quality]` + `_BITRATE_MAP[quality]` + `_resolve_pls` URLs | Module-scope constants (ground truth) + HTTP fetch of AA PLS files | Yes — live AA HTTP fetch + ground-truth map | FLOWING |
| `_handle_gst_error_recovery` guard effect | `_recovery_in_flight` bool | Mutated by recovery handler, cleared by deferred singleShot, reset by public play/stop/pause | Yes — real state machine | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Gap-closure regression tests (all 7) | `pytest test_multiple_gst_errors_advance_queue_once test_recovery_guard_resets_between_distinct_url_failures test_resolve_pls_returns_all_entries test_resolve_pls_single_entry test_fetch_channels_multi_preserves_primary_and_fallback test_fetch_channels_multi_codec_map_ground_truth test_bitrate_delegate_persists_empty_string_on_commit -v` | 7 passed in 0.17s | PASS |
| WR-01 quality-tier primacy tests | `pytest tests/test_stream_ordering.py -v` | 32 passed in 0.07s (incl. `test_quality_tier_beats_codec_rank`, `test_quality_tier_full_order`) | PASS |
| Non-Qt phase-47 suite | `pytest tests/test_stream_ordering.py tests/test_aa_import.py tests/test_settings_export.py tests/test_repo.py -q` | 136 passed, 0 failed in 0.71s | PASS |
| Old codec ternary fully removed | `grep '"AAC" if tier == "premium_high" else "MP3"' musicstreamer/aa_import.py` | 0 matches | PASS |
| `_recovery_in_flight` reset-on-public-action invariant | grep for `self._recovery_in_flight = False` in player.py | 4 matches (play, play_stream, pause, stop) as required | PASS |
| `_resolve_pls` always returns list | grep `def _resolve_pls(pls_url: str) -> list[str]` | 1 match | PASS |
| Qt-dep failures match deferred-items.md (env-only) | pytest test_edit_station_dialog + test_player_failover | 6 failures all `AttributeError: 'NoneType' object has no attribute 'QTest'` — exactly the documented pre-existing pytest-qt env issue | PASS (env, not code) |

### Anti-Patterns Scan

| Anti-Pattern | Severity | Status | Evidence |
| ------------ | -------- | ------ | -------- |
| Inverted AA codec labels (UAT gap 3) | Blocker | NOT VIOLATED | Ground-truth `_CODEC_MAP` at line 110; old ternary removed (grep=0) |
| Silent-drop of AA fallback URL (UAT gap 2) | Blocker | NOT VIOLATED | `_resolve_pls` returns full list; `fetch_channels_multi` emits per-URL (test verifies 6 streams for 3-tier × 2-URL) |
| Cascading errors prematurely drain queue (UAT gap 5) | Blocker | NOT VIOLATED | `_recovery_in_flight` guard + deferred clear; two regression tests assert coalescing |
| Empty Bitrate cell doesn't save as 0 (UAT gap 1) | Blocker | NOT VIOLATED | Explicit `setModelData` override writes `editor.text()` to `Qt.EditRole`; regression test asserts empty → 0 through delegate |
| WR-01 codec-efficiency tiebreak inverts user's quality choice | Warning | NOT VIOLATED | `quality_rank` is primary sort key in `order_streams`; `test_quality_tier_beats_codec_rank` + `test_quality_tier_full_order` PASS |

### Requirements Coverage

Phase 47 has no required requirement IDs (`requirements: []` across all 7 plans). REQUIREMENTS.md does not map any REQ-IDs specifically to Phase 47. No orphaned requirements.

### Human Verification Required

None. All 15 must-haves are programmatically verifiable via grep + pytest against the actual codebase. The full runtime loop (AA import → DB persist → failover ordering with quality-tier primacy → guarded recovery → settings roundtrip → Edit Station delegate) is covered by automated tests:

- 7 new gap-closure regression tests (plans 04-07)
- WR-01 quality-tier primacy tests in `tests/test_stream_ordering.py`
- Pre-existing PB-12/13/14/15/16/17/17b/18 tests from 47-01/02/03

The 3 UAT live-retest observations are still reasonable but would only yield additional confidence, not expose new gaps — all reported issues have direct regression tests now:

- UAT test 2 (clear Bitrate cell) → `test_bitrate_delegate_persists_empty_string_on_commit`
- UAT test 3 (AA import codec/bitrate) → `test_fetch_channels_multi_codec_map_ground_truth` + `test_fetch_channels_multi_preserves_primary_and_fallback`
- UAT test 5 (failover on broken streams) → `test_multiple_gst_errors_advance_queue_once` + `test_recovery_guard_resets_between_distinct_url_failures`

### Gap Closure Summary

| Gap | Source | Plan | Status | Commit |
| --- | ------ | ---- | ------ | ------ |
| UAT gap 1: empty Bitrate cell reverts | UAT | 47-04 | CLOSED | 1c6e133 |
| UAT gap 5: cascading errors → spurious "Stream exhausted" | UAT | 47-05 | CLOSED | a8e6e0b |
| UAT gap 2: AA PLS fallback URL dropped | UAT | 47-06 | CLOSED | b725488 |
| UAT gap 3: AA codec labels inverted | UAT | 47-07 | CLOSED | 8196a34 |
| UAT gap 4: no visible failover indication | UAT | (partial) | DEFERRED | Side-effect of gap-5 fix mitigates toast visibility; full status-line UX deferred to future phase |
| REVIEW WR-01: codec-efficiency inverts user quality choice | REVIEW-GAPS | follow-up | CLOSED | 1961775 |

UAT gap 4 (failover visibility status-line) was explicitly deferred — the gap-5 fix restores per-stream BUFFER_DURATION_S visibility of the existing toast, but a dedicated stats-for-nerds / log-row UX was not in scope of plans 04-07 and does not block the phase goal (bitrate quality ordering is achieved end-to-end). No new gap is raised for this.

### SUMMARY Integrity

| Plan | Self-Check | Status |
| ---- | ---------- | ------ |
| 47-01 | PASSED | OK |
| 47-02 | PASSED | OK |
| 47-03 | PASSED | OK |
| 47-04 | PASSED | OK |
| 47-05 | PASSED | OK |
| 47-06 | PASSED | OK |
| 47-07 | PASSED | OK |

### Gaps Summary

None. All 15 goal-backward truths pass. All 4 UAT gaps that blocked the phase goal are closed with direct regression tests. The WR-01 review finding (which would have inverted paid-AA failover order once the correct codec map landed) is also closed by the `quality_rank` primary-sort-key refactor. The only remaining UAT observation (gap 4 — visible failover indication) is a UX nice-to-have, not a goal blocker, and is explicitly deferred.

---

_Verified: 2026-04-18T22:00:00Z_
_Verifier: Claude (gsd-verifier)_
