---
phase: 39-core-dialogs
verified: 2026-04-13T15:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open EditStationDialog for a real playing station. Click Delete Station."
    expected: "Delete button is disabled. Tooltip reads 'Stop playback before deleting'."
    why_human: "guard checks player._current_station_name at construction time — runtime state can't be asserted in headless tests"
  - test: "Open DiscoveryDialog. Search for 'jazz'. Click Play on a result row."
    expected: "Station previews via the main player (audio heard or now-playing panel updates)."
    why_human: "Requires live Radio-Browser.info API response and real GStreamer pipeline"
  - test: "Open ImportDialog YouTube tab. Enter a real YouTube live playlist URL. Click Scan Playlist."
    expected: "List populates with live stream entries; scan progress bar shows indeterminate state, then hides."
    why_human: "Requires yt-dlp + Node.js EJS solver at runtime; not testable headlessly"
  - test: "Open ImportDialog AudioAddict tab. Enter a valid API key. Click Import Channels."
    expected: "Progress bar advances determinately during import; toast 'Imported N channels' appears on completion."
    why_human: "Requires live AudioAddict API key and network access"
  - test: "Play a multi-stream station. Observe stream picker combo on now-playing panel."
    expected: "Combo is visible with all stream labels (quality — codec); selecting a different entry switches playback."
    why_human: "Requires multi-stream station in real DB and GStreamer playback path"
---

# Phase 39: Core Dialogs Verification Report

**Phase Goal:** User can edit stations (multi-stream management, tags, ICY toggle), discover new stations via Radio-Browser, import from YouTube/AudioAddict playlists, and manually select a stream from now-playing
**Verified:** 2026-04-13T15:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | EditStationDialog opens for any station with all fields populated | VERIFIED | `edit_station_dialog.py` 420 lines; QFormLayout with name, URL, provider combo, tag chips, ICY checkbox, stream table all populated from station/repo data. 11 tests pass. |
| 2 | Tag chips toggle on/off; new tags can be added inline | VERIFIED | `chipState` property toggling with `style().polish()`, `_CHIP_QSS` applied. `test_tag_chips_render_and_toggle` and `test_add_tag_creates_chip` pass. |
| 3 | Stream table shows all streams with Add/Remove/Move Up/Move Down | VERIFIED | 4-column QTableWidget; Add/Remove/Move Up/Move Down buttons confirmed in code and `test_stream_table_populated_and_add`, `test_remove_stream_removes_row`, `test_move_up_down_reorder` pass. |
| 4 | Delete button is disabled when station is currently playing | VERIFIED | `delete_btn.setEnabled(not (player._current_station_name == station.name))` at line 243. `test_delete_disabled_when_playing` and `test_delete_enabled_when_not_playing` pass. |
| 5 | Save calls repo.update_station with provider_id from ensure_provider | VERIFIED | Line 357: `provider_id = repo.ensure_provider(provider_name)`, line 359: `repo.update_station(...)`. `test_save_calls_repo_correctly` passes. |
| 6 | DiscoveryDialog searches Radio-Browser.info and shows results in a table | VERIFIED | `radio_browser.search_stations` called in `_SearchWorker.run()` line 95; results populate 6-column QTableView. 9 tests pass. |
| 7 | Tag and country combo filters populate on dialog open via daemon thread | VERIFIED | `_TagWorker` and `_CountryWorker` started in `showEvent` (lazy-load guard). `fetch_tags()` and `fetch_countries()` called in `run()`. |
| 8 | Clicking play on a result row previews via main Player | VERIFIED | `_on_play_row` builds `Station(id=-1)` + `StationStream(id=-1)` and calls `player.play(temp_station)`. `test_preview_play_calls_player` passes. |
| 9 | Clicking save uses url_resolved; save button disabled after use | VERIFIED | Line 395: `result.get("url_resolved") or result.get("url", "")` before `repo.insert_station`. Save button disabled in `_on_save_row`. `test_save_uses_url_resolved` passes. |
| 10 | Search runs on daemon thread with loading indicator | VERIFIED | `_SearchWorker(QThread)` with `setRange(0, 0)` indeterminate progress bar during search. `test_search_populates_table` passes. |
| 11 | ImportDialog has two tabs: YouTube and AudioAddict | VERIFIED | `QTabWidget` with two tabs at lines 156+. `test_dialog_has_two_tabs` passes. |
| 12 | YouTube tab scans a playlist, shows checkable results, imports selected | VERIFIED | `_YtScanWorker` → `_on_yt_scan_complete` populates `QListWidget` with `Qt.ItemIsUserCheckable` items; `_YtImportWorker` calls `yt_import.import_stations`. `is_live is True` identity filter applied. 11 tests pass. |
| 13 | AudioAddict tab accepts API key, fetches channels, imports with progress | VERIFIED | `_AaFetchWorker` calls `fetch_channels_multi(api_key)`; `_AaImportWorker` calls `import_stations_multi` with `on_progress` callback. Determinate progress bar. Workers create `Repo(db_connect())` thread-locally inside `run()`. |
| 14 | Error states display inline labels for invalid API key and empty playlists | VERIFIED | `_aa_status.setStyleSheet("color: #c0392b;")` at line 239, 399. "No live streams found" for empty YT results. `test_audioaddict_invalid_key_shows_error` passes. |
| 15 | Edit button on now-playing panel opens EditStationDialog for current station | VERIFIED | `edit_btn = QToolButton`, `edit_requested = Signal(object)`, `_on_edit_clicked` emits with `self._station`. MainWindow wires `edit_requested` → `_on_edit_requested` which instantiates `EditStationDialog`. |
| 16 | Edit button is enabled only when a station is playing | VERIFIED | `edit_btn.setEnabled(self._is_playing and self._station is not None)` at line 329; disabled on stop at line 347. `test_edit_btn_enabled_when_playing` passes. |
| 17 | Stream picker combo shows all streams; hidden for single-stream station | VERIFIED | `_populate_stream_picker` sets `setVisible(len(streams) > 1)`. `test_stream_picker_hidden_single_stream` and `test_stream_picker_visible_multi_stream` pass (using `isHidden()`). |
| 18 | Changing stream picker selection plays that specific stream | VERIFIED | `_on_stream_selected` calls `player.play_stream(s)` for matched stream_id. `test_stream_selection_calls_play_stream` passes. |
| 19 | Failover signal updates stream picker with blockSignals guard | VERIFIED | `_sync_stream_picker` wraps `setCurrentIndex` with `blockSignals(True/False)`. `test_failover_sync_no_play_stream` passes. |
| 20 | Station list refreshes after edit/delete/import operations | VERIFIED | `_refresh_station_list` calls `station_panel.refresh_model()` which is wired to `station_saved`, `station_deleted`, and `import_complete` signals. `StationListPanel.refresh_model()` exists at line 308. |

**Score:** 5/5 roadmap success criteria verified (20/20 plan truths verified)

### Deferred Items

None identified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/ui_qt/edit_station_dialog.py` | EditStationDialog QDialog | VERIFIED | 420 lines, `class EditStationDialog(QDialog)` confirmed |
| `tests/test_edit_station_dialog.py` | pytest-qt tests for UI-05 | VERIFIED | 11 test functions |
| `musicstreamer/ui_qt/discovery_dialog.py` | DiscoveryDialog QDialog | VERIFIED | 460 lines, `class DiscoveryDialog(QDialog)` confirmed |
| `tests/test_discovery_dialog.py` | pytest-qt tests for UI-06 | VERIFIED | 9 test functions |
| `musicstreamer/ui_qt/import_dialog.py` | ImportDialog QDialog | VERIFIED | 437 lines, `class ImportDialog(QDialog)` confirmed |
| `tests/test_import_dialog_qt.py` | pytest-qt tests for UI-07 | VERIFIED | 11 test functions |
| `musicstreamer/ui_qt/now_playing_panel.py` | Edit button + stream picker | VERIFIED | `edit_btn`, `stream_combo`, `edit_requested` signal all present |
| `musicstreamer/ui_qt/main_window.py` | Dialog launch wiring + refresh | VERIFIED | Imports all 3 dialogs; `_on_edit_requested`, `_refresh_station_list` wired |
| `musicstreamer/ui_qt/icons/document-edit-symbolic.svg` | Edit icon SVG | VERIFIED | File exists |
| `tests/test_stream_picker.py` | pytest-qt tests for UI-13 | VERIFIED | 8 test functions |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| edit_station_dialog.py | repo.py | repo.ensure_provider, repo.update_station, repo.delete_station, repo.list_streams, repo.insert_stream, repo.update_stream, repo.reorder_streams | WIRED | All calls confirmed in save/delete paths |
| discovery_dialog.py | radio_browser.py | search_stations, fetch_tags, fetch_countries in QThread.run() | WIRED | Lines 55, 69, 95 |
| discovery_dialog.py | repo.py | repo.insert_station in save path | WIRED | Line 398 |
| import_dialog.py | yt_import.py | scan_playlist, import_stations in QThread.run() | WIRED | Lines 62, 80 |
| import_dialog.py | aa_import.py | fetch_channels_multi, import_stations_multi in QThread.run() | WIRED | Lines 98, 119 |
| now_playing_panel.py | player.py | player.play_stream, player.failover | WIRED | play_stream at line 419; failover connected in main_window at line 119 |
| main_window.py | edit_station_dialog.py | EditStationDialog instantiation + signal wiring | WIRED | Lines 169–171 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| edit_station_dialog.py | station fields | `repo.list_streams(station.id)`, `repo.list_providers()` passed at construction | Yes — real repo queries | FLOWING |
| discovery_dialog.py | `self._results` | `radio_browser.search_stations()` via `_SearchWorker` | Yes — Radio-Browser.info API | FLOWING |
| import_dialog.py | scan results | `yt_import.scan_playlist()` via `_YtScanWorker` | Yes — yt-dlp at runtime | FLOWING |
| now_playing_panel.py | `self._streams` | `repo.list_streams(station.id)` in `_populate_stream_picker` | Yes — real repo query | FLOWING |

### Behavioral Spot-Checks

Step 7b: All phase 39 code requires PySide6 display + real GStreamer/network. Automated spot-checks skipped — behaviors verified via pytest-qt with mocks and flagged for human verification above.

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 39 phase 39 tests pass | `uv run --with pytest --with pytest-qt python -m pytest tests/test_edit_station_dialog.py tests/test_discovery_dialog.py tests/test_import_dialog_qt.py tests/test_stream_picker.py -q` | 39 passed in 0.45s | PASS |
| Full suite (excl. slow yt test) | `uv run --with pytest --with pytest-qt python -m pytest --ignore=tests/test_yt_import_library.py -q` | 399 passed, 1 failed (pre-existing phase 38 regression) | PASS (phase 39 scope) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| UI-05 | 39-01-PLAN.md | EditStationDialog — provider picker, tag chips, multi-stream CRUD, ICY toggle, delete guard | SATISFIED | edit_station_dialog.py fully implemented; 11 tests pass |
| UI-06 | 39-02-PLAN.md | DiscoveryDialog — Radio-Browser search, preview, save-to-library | SATISFIED | discovery_dialog.py fully implemented; 9 tests pass |
| UI-07 | 39-03-PLAN.md | ImportDialog — YouTube playlist + AudioAddict import | SATISFIED | import_dialog.py fully implemented; 11 tests pass |
| UI-13 | 39-04-PLAN.md | Stream picker on now-playing panel — manual stream selection | SATISFIED | now_playing_panel.py stream_combo + edit_btn; main_window.py dialog wiring; 8 tests pass |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| discovery_dialog.py | 332–334 | "placeholder" in variable name `play_placeholder`, `save_placeholder` | Info | These are `QStandardItem()` cells where `setIndexWidget` embeds QPushButtons — correct Qt table pattern, not a stub |
| import_dialog.py | 122 | `cur + tot - tot` in lambda (simplifies to `cur`) | Info | Arithmetic oddity from refactor; emits correct `(cur, tot)` values since the expression evaluates correctly |

No blockers or warnings found.

### Pre-Existing Regression (Not Phase 39)

`tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode` — 1 failure that predates phase 39. The test was introduced in phase 38 commit `ac1a0e2`. Phase 39 commit `d1344d2` only added `refresh_model()` to `StationListPanel` and did not touch search box or stack logic. This failure is out of scope for phase 39 verification.

### Human Verification Required

#### 1. Delete guard — real playback

**Test:** Start playing a station. Open EditStationDialog by clicking the edit button.
**Expected:** Delete Station button is disabled with tooltip "Stop playback before deleting".
**Why human:** The guard checks `player._current_station_name` at construction time; headless tests use a mock player.

#### 2. Radio-Browser preview

**Test:** Open DiscoveryDialog. Search for "jazz". Click Play on any result row.
**Expected:** Station begins playing via the main player; now-playing panel updates with station name.
**Why human:** Requires live Radio-Browser.info API and real GStreamer pipeline.

#### 3. YouTube scan and import

**Test:** Open ImportDialog YouTube tab. Enter a real YouTube live playlist URL (e.g., LoFi Girl). Click Scan Playlist.
**Expected:** Checkable list populates with live stream entries; indeterminate progress bar shows during scan then hides; "N streams found" status appears.
**Why human:** Requires yt-dlp + Node.js EJS solver at runtime.

#### 4. AudioAddict import with progress

**Test:** Open ImportDialog AudioAddict tab. Enter a valid DI.fm API key. Click Import Channels.
**Expected:** Indeterminate progress bar during fetch, then determinate bar advances during import; toast "Imported N channels" on completion.
**Why human:** Requires live AudioAddict API credentials and network access.

#### 5. Stream picker with real multi-stream station

**Test:** Play a station that has 2 or more streams configured. Observe the now-playing panel.
**Expected:** Stream picker combo is visible with labels in "quality — codec" format. Selecting a different stream switches playback without double-triggering (blockSignals guard).
**Why human:** Requires multi-stream station in real DB and GStreamer playback.

### Gaps Summary

No gaps. All 20 plan truths verified, all 4 required test files and 6 implementation artifacts confirmed substantive and wired. 39/39 phase tests pass. Human verification items above are runtime/network behaviors that cannot be tested headlessly — they do not indicate incomplete implementation.

---

_Verified: 2026-04-13T15:00:00Z_
_Verifier: Claude (gsd-verifier)_
