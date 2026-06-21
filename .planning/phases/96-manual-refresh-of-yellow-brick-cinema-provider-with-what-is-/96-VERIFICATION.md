---
phase: 96-manual-refresh-of-yellow-brick-cinema-provider-with-what-is-
verified: 2026-06-21T00:00:00Z
status: passed
score: 10/10 must-haves verified
has_blocking_gaps: false
overrides_applied: 0
---

# Phase 96: Manual Live-Stream URL Refresh Verification Report

**Phase Goal:** A user can mark a YouTube live station as "re-sync live URL from channel" (per-station opt-in, default OFF, YouTube-only), supply the channel's `/streams` scan URL once per provider, then right-click the provider row to open a review-and-confirm dialog that re-scans the channel's currently-live streams and lets them manually map / replace / drop / add their flagged stations against reality — updating churned `watch?v=` URLs in place (no duplicate-import) with conservative, opt-in destructive defaults.
**Verified:** 2026-06-21T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (D-01..D-10)

| # | Decision | Truth | Status | Evidence |
|---|----------|-------|--------|----------|
| 1 | D-01 | Per-station boolean flag `live_url_syncs_from_channel` (DEFAULT 0) added idempotently via additive migration, round-trips through all Station-building queries | VERIFIED | `repo.py:344` ALTER TABLE after rebuild block; 5 `Station(live_url_syncs_from_channel=bool(...))` call sites; 7/7 repo tests pass |
| 2 | D-02 | Flag checkbox enabled ONLY for youtube.com/youtu.be URLs (not Twitch, not others); disabled+unchecked when URL is non-YouTube | VERIFIED | `edit_station_dialog.py:1324` `_live_resync_checkbox.setEnabled(is_yt)` where `is_yt` excludes Twitch; `test_live_resync_checkbox_gating` passes |
| 3 | D-03 | Title anchor `live_url_title_anchor` (nullable TEXT) stored at flag-time via dedicated setter; capped at 500 chars; used only to pre-order suggestions | VERIFIED | `repo.py:354,1037-1052`; `_build_row_suggestions` returns pre-ordered list but stages no mapping; round-trip test passes |
| 4 | D-04 | Provider-level `channel_scan_url` (nullable TEXT) on `providers` table; `_TreeNode.provider_id` populated; provider right-click context menu triggers `provider_refresh_requested` signal; Ungrouped row (provider_id=None) gets no menu | VERIFIED | `repo.py:363,511,514,1054-1065`; `station_tree_model.py:37,221`; `station_list_panel.py:91,693-702`; `test_tree_node_carries_provider_id` passes; Ungrouped gate confirmed at L691-693 |
| 5 | D-05 | No automatic title matching — `_build_row_suggestions` pre-orders by anchor similarity but NEVER auto-stages any URL change; user maps every time | VERIFIED | `live_refresh_dialog.py:104-127` returns sorted list with no staged changes; `test_suggestions_pre_order_no_auto_apply` passes |
| 6 | D-06 | REMAP: `update_stream` called with new URL preserving ALL non-URL fields (label/quality/position/stream_type/codec/bitrate); `set_live_url_title_anchor` updated; `list_flagged_stations_for_provider` scoped to one provider | VERIFIED | `live_refresh_dialog.py:234-256`; `repo.py:1067-1106`; `test_apply_remap_preserves_metadata` passes |
| 7 | D-07 | Drop/delete (explicit tick only) → `delete_station`; Add (explicit tick only) → `insert_station` + `set_live_url_syncs_from_channel(True)` + `set_live_url_title_anchor` so new station is itself refresh-eligible | VERIFIED | `live_refresh_dialog.py:261,270-274`; `test_apply_drop_and_add_actions` passes |
| 8 | D-08 | ADD row name defaults to scan result's YouTube title; REMAP/REPLACE row name defaults to existing station name (never silently clobbered) | VERIFIED | `live_refresh_dialog.py:143-147,372-377`; `test_name_field_prepopulation` passes |
| 9 | D-09 | Scan runs off UI thread on `_LiveRefreshScanWorker(QThread)`; `node_runtime` threaded MainWindow → `StationListPanel` → `LiveRefreshDialog` → `_LiveRefreshScanWorker` → `scan_playlist`; results returned via `Qt.QueuedConnection` | VERIFIED | `station_list_panel.py:91-96`; `main_window.py:404,1380`; `live_refresh_dialog.py:78-92,537`; `test_scan_worker_uses_qthread` and `test_scan_worker_forwards_node_runtime` pass |
| 10 | D-10 | Conservative defaults: DROP+ADD rows unchecked by default; REMAP rows checked; unresolved flagged station produces no repo mutation; empty staged-changes list produces zero mutations; duplicate-target guard blocks silent URL collapse; station list reloads after apply | VERIFIED | `live_refresh_dialog.py:167-173,203-222`; `main_window.py:1384`; `test_conservative_defaults` and `test_apply_refresh_rejects_duplicate_targets` pass |

**Score:** 10/10 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/repo.py` | 3 additive migrations + 4 setters/queries + 5 Station-query updates | VERIFIED | ALTER TABLEs at lines 344, 354, 363 (all after rebuild block at ~252); setters at 1023, 1037, 1054; `list_flagged_stations_for_provider` at 1067; 5 Station() call sites carry new fields |
| `musicstreamer/models.py` | `Station.live_url_syncs_from_channel`, `Station.live_url_title_anchor`, `Provider.channel_scan_url` | VERIFIED | Lines 9, 46, 47 |
| `musicstreamer/ui_qt/edit_station_dialog.py` | `_live_resync_checkbox` + companion URL field + YouTube-only gate + on-save persistence via dedicated setters | VERIFIED | `_live_resync_checkbox` at 525; gate at 1324; WR-04 fix (clear on empty) at 1892-1895; setters called at 1884,1889,1895,1898-1899 |
| `musicstreamer/ui_qt/station_tree_model.py` | `_TreeNode.provider_id` field + populate from first station of each group | VERIFIED | Field at line 37; `provider_id=st.provider_id` at line 221 |
| `musicstreamer/ui_qt/live_refresh_dialog.py` | `LiveRefreshDialog(QDialog)` + `_LiveRefreshScanWorker(QThread)` + pure `apply_refresh` helper | VERIFIED | Classes at lines 62, 431; `apply_refresh` at 176; `_build_row_suggestions` at 104 |
| `musicstreamer/ui_qt/station_list_panel.py` | `provider_refresh_requested = Signal(int, str)` + provider context-menu branch + `node_runtime` param | VERIFIED | Signal at 91; `__init__` node_runtime at 93-96; branch at 690-702 |
| `musicstreamer/ui_qt/main_window.py` | `LiveRefreshDialog` import + `node_runtime` to `StationListPanel` + `_on_provider_refresh_requested` slot + `refresh_complete` → reload | VERIFIED | Import at 81; construction at 404; signal wire at 553; slot at 1356-1385; `refresh_complete.connect` at 1384 |
| `musicstreamer/yt_import.py` | `_entry_is_live` duration-fallback for channel `/streams` tab | VERIFIED | Duration fallback at lines 59-60 (commit fbebaf1a); `test_scan_playlist_flat_channel_tab_falls_back_to_duration` passes |
| `tests/test_live_refresh_dialog.py` | 9 dialog-logic tests covering D-05..D-10 | VERIFIED | All 9 tests collected and passing; includes `test_row_labels_use_plaintext_against_injection` (CR-01) and `test_apply_refresh_rejects_duplicate_targets` (WR-03) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `edit_station_dialog.py` | `repo.py` | `set_live_url_syncs_from_channel`, `set_live_url_title_anchor`, `set_provider_channel_scan_url` | WIRED | Lines 1884, 1889, 1895, 1898-1899 — never via `update_station` |
| `station_tree_model.py` | `models.py` | `_TreeNode.provider_id = st.provider_id` | WIRED | Line 221 |
| `live_refresh_dialog.py` | `yt_import.py` | `_LiveRefreshScanWorker.run → scan_playlist(node_runtime=...)` | WIRED | Line 89-92 |
| `live_refresh_dialog.py` | `repo.py` | `apply_refresh → update_stream / delete_station / insert_station + setters` | WIRED | Lines 244, 261, 271, 257, 273-274; `station_exists_by_url` NOT called (confirmed via grep) |
| `station_list_panel.py` | `live_refresh_dialog.py` | `provider_refresh_requested → MainWindow._on_provider_refresh_requested → LiveRefreshDialog(node_runtime=...)` | WIRED | Signal at SLP:91,698; slot at MW:1356-1385; LiveRefreshDialog constructed at MW:1375 with `node_runtime=self._node_runtime` |
| `main_window.py` | `station_list_panel.py` | `StationListPanel(repo, parent=..., node_runtime=self._node_runtime)` | WIRED | Line 404 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `live_refresh_dialog.py` | `flagged_stations` (left panel) | `repo.list_flagged_stations_for_provider(provider_id)` | Yes — DB query at `repo.py:1067-1106` filters `live_url_syncs_from_channel=1` | FLOWING |
| `live_refresh_dialog.py` | `scan_results` (right panel) | `_LiveRefreshScanWorker.run → yt_import.scan_playlist` | Yes — live yt-dlp channel scan; `finished` signal populates combo widgets | FLOWING |
| `apply_refresh` | `primary` stream | `repo.list_streams(station_id)` | Yes — DB query returns real `StationStream` rows; `update_stream` writes new URL back | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Repo migration adds 3 columns idempotently | `.venv/bin/python -m pytest tests/test_repo.py -k "migration_idempotent" -q` | 3 passed | PASS |
| Flag round-trips through all Station-building paths | `.venv/bin/python -m pytest tests/test_repo.py -k "round_trip or live_flag_loaded" -q` | 3 passed | PASS |
| `list_flagged_stations_for_provider` scopes to provider | `.venv/bin/python -m pytest tests/test_repo.py -k "flagged_stations" -q` | 1 passed | PASS |
| YouTube-only gate on checkbox | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py::test_live_resync_checkbox_gating -q` | 1 passed | PASS |
| `_TreeNode.provider_id` populated; Ungrouped=None | `.venv/bin/python -m pytest tests/test_station_tree_model.py::test_tree_node_carries_provider_id -q` | 1 passed | PASS |
| All 9 dialog-logic tests (D-05..D-10 + CR-01 + WR-03) | `.venv/bin/python -m pytest tests/test_live_refresh_dialog.py -q` | 9 passed | PASS |
| node_runtime threading wiring assertion | `.venv/bin/python -m pytest tests/test_station_list_panel.py -k "provider_refresh_wiring" -q` | 1 passed | PASS |
| Duration-fallback live detection regression | `.venv/bin/python -m pytest tests/test_yt_import_library.py::test_scan_playlist_flat_channel_tab_falls_back_to_duration -q` | 1 passed | PASS |
| Imports cleanly | `.venv/bin/python -c "import musicstreamer.ui_qt.main_window; import musicstreamer.ui_qt.station_list_panel"` | no output | PASS |

---

### Requirements Coverage

| Decision | Source Plan | Description | Status | Evidence |
|----------|------------|-------------|--------|----------|
| D-01 | 96-02/96-03 | Per-station `live_url_syncs_from_channel` flag, additive migration, default OFF | SATISFIED | Migration at repo.py:344; 5 Station() sites; 6 repo tests green |
| D-02 | 96-03 | YouTube-only gate on checkbox (not Twitch) | SATISFIED | edit_station_dialog.py:1324 `is_yt` without `is_twitch`; gating test green |
| D-03 | 96-02/96-03 | Title anchor `live_url_title_anchor`, stored at flag-set, pre-orders suggestions only, never auto-applies | SATISFIED | repo.py:354,1037; `_build_row_suggestions` returns sorted list, no staged changes |
| D-04 | 96-02/96-03/96-05 | Provider `channel_scan_url`, `_TreeNode.provider_id`, provider right-click menu, Ungrouped excluded | SATISFIED | repo.py:363; station_tree_model.py:37,221; station_list_panel.py:91,693-702 |
| D-05 | 96-04 | No auto-matching; user maps every time; anchor only pre-orders | SATISFIED | `_build_row_suggestions` at live_refresh_dialog.py:104-127; `test_suggestions_pre_order_no_auto_apply` green |
| D-06 | 96-04 | REMAP preserves all non-URL stream metadata via `update_stream`; `list_flagged_stations_for_provider` | SATISFIED | live_refresh_dialog.py:234-257; `test_apply_remap_preserves_metadata` green |
| D-07 | 96-04 | Drop (explicit tick) and Add (explicit tick, then mark refresh-eligible) actions available | SATISFIED | live_refresh_dialog.py:261-274; `test_apply_drop_and_add_actions` green |
| D-08 | 96-04 | ADD name defaults to scan title; REMAP name defaults to station name | SATISFIED | live_refresh_dialog.py:143-147,372-377; `test_name_field_prepopulation` green |
| D-09 | 96-04/96-05 | Off-UI-thread scan via `_LiveRefreshScanWorker(QThread)`; `node_runtime` threaded end-to-end | SATISFIED | Worker at live_refresh_dialog.py:62; node_runtime chain confirmed at SLP:93-96, MW:404,1380, LRD:84,92; 2 worker tests green |
| D-10 | 96-04/96-05 | Conservative defaults (DROP/ADD unchecked, REMAP checked); untouched station never mutated; empty staged-changes = zero mutations; duplicate-target guard; station list reloads | SATISFIED | live_refresh_dialog.py:167-173,203-222; main_window.py:1384; `test_conservative_defaults` and `test_apply_refresh_rejects_duplicate_targets` green |

---

### Code Review Findings — Disposition

| Finding | Severity | Status |
|---------|----------|--------|
| CR-01: Untrusted scan titles rendered as rich text (T-39-01 violation) | BLOCKER | FIXED — `station_label.setTextFormat(Qt.PlainText)` and `anchor_label.setTextFormat(Qt.PlainText)` at live_refresh_dialog.py:323,328; `test_row_labels_use_plaintext_against_injection` added and passing |
| WR-03: No guard against multiple REMAP rows mapping to same live stream | WARNING | FIXED — duplicate-target guard in `apply_refresh` at live_refresh_dialog.py:206-222 raises `ValueError` before any mutation; `test_apply_refresh_rejects_duplicate_targets` green |
| WR-04: Channel scan URL cannot be cleared once set | WARNING | FIXED — WR-04 clear path at edit_station_dialog.py:1892-1895 calls `set_provider_channel_scan_url(provider_id, None)` when flag is on and field is empty |
| WR-01: Scan worker not awaited on Cancel (QThread destroyed while running) | WARNING | DEFERRED — per 96-REVIEW.md disposition: matches existing `import_dialog._YtScanWorker` pattern which has the same lifecycle; deferred to future hardening. Not a goal blocker. |
| WR-02: `_entry_is_live` duration-fallback widens "live" globally | WARNING | DEFERRED — per 96-REVIEW.md: the shared-predicate widening concern was reviewed; import tests remain green; the fallback only fires when both `live_status` and `is_live` are None (a channel-tab-specific yt-dlp behavior). Not a goal blocker. |
| IN-01: QFormLayout label orphaned when field hidden | INFO | Deferred — cosmetic only |
| IN-02: ADD-row name field shows empty until combo changes | INFO | Deferred — cosmetic; `build_staged_change` fallback ensures correct committed record |
| IN-03: ADD inserts via provider name (fragile on name collision) | INFO | Deferred — no known collision in current data; cosmetic for single-name flows |

---

### Anti-Patterns Found

No `TBD`, `FIXME`, or `XXX` markers found in any Phase 96 modified file. No unreferenced stub patterns detected. The `return []` at `live_refresh_dialog.py:119` is the correct empty-input guard for `_build_row_suggestions` when `scan_results` is empty — not a stub (the function returns a reordered copy of its input; an empty input yields an empty output).

---

### Human Verification

The human-verify checkpoint (Plan 05 Task 3) was completed and approved by the user during execution. The user confirmed:

1. "Re-sync live URL from channel" checkbox enabled for YouTube stations, disabled for Twitch/other
2. Provider right-click "Refresh live streams…" appears on named provider rows, absent on Ungrouped
3. Dialog opened and scan ran without UI freeze
4. 9 live/upcoming streams returned from the YBC channel (after live-detection fix fbebaf1a)
5. REMAP confirmed working; DROP+ADD rows unchecked by default; summary shown before Apply
6. Station list reloaded after Apply; remapped station plays new live URL; untouched station unchanged

No further human verification required for this verification pass.

---

### Gaps Summary

No gaps. All 10 D-01..D-10 decisions are realized in production code and covered by passing automated tests. The three code-review blockers/warnings resolved before this verification (CR-01, WR-03, WR-04) are confirmed fixed in source. The two deferred warnings (WR-01 worker lifetime, WR-02 shared predicate) are non-goal-blocking deviations accepted by the implementer with rationale, consistent with the existing import dialog pattern.

---

_Verified: 2026-06-21T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
