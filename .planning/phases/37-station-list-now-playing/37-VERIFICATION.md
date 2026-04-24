---
phase: 37-station-list-now-playing
verified: 2026-04-12T17:45:00Z
status: passed
score: 4/5 must-haves verified
overrides_applied: 0
gaps:
  - truth: "StationListPanel.station_activated -> MainWindow.play(station) + 'Connecting...' toast + repo.update_last_played + NowPlayingPanel.bind_station"
    status: partial
    reason: "repo.update_last_played(station.id) is never called in MainWindow._on_station_activated. Recently-played list will not update when a station is played."
    artifacts:
      - path: "musicstreamer/ui_qt/main_window.py"
        issue: "_on_station_activated missing repo.update_last_played(station.id) call"
    missing:
      - "Add self._repo.update_last_played(station.id) to MainWindow._on_station_activated"
      - "Add integration test asserting update_last_played is called on station activation"
---

# Phase 37: Station List + Now Playing Verification Report

**Phase Goal:** A user can open the app, see their stations grouped by provider, click one to play, and see ICY title, cover art, elapsed timer, and volume slider update in the now-playing panel
**Verified:** 2026-04-12T17:45:00Z
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Station list shows provider groups (collapsible), recently-played section, and per-row logos | VERIFIED | StationTreeModel groups by provider with (N) suffix; StationListPanel has QListView for recent + QTreeView for main list; audio-x-generic-symbolic.svg fallback icon ships in qrc; 18 tests pass |
| 2 | Clicking a station plays it; ICY track title updates live in the now-playing panel | VERIFIED | station_activated signal -> _on_station_activated -> player.play + bind_station; player.title_changed -> now_playing.on_title_changed; 339 tests all pass including integration tests |
| 3 | Cover art loads from iTunes; YouTube 16:9 thumbnails display without panel sizing regression | VERIFIED | cover_art.fetch_cover_art wired via cover_art_ready Signal with QueuedConnection; _set_cover_pixmap uses QPixmap.scaled(160,160, KeepAspectRatio); test_youtube_thumbnail_letterbox proves 320x180 -> 160x90 inside 160x160 slot |
| 4 | Volume slider adjusts playback volume and persists across restarts | VERIFIED | volume_slider.valueChanged -> _on_volume_changed_live -> player.set_volume(v/100.0); sliderReleased -> _on_volume_released -> repo.set_setting("volume", str(value)); initial value from repo.get_setting("volume", "80") with try/except guard |
| 5 | Toast notifications appear for failover and connecting states | VERIFIED | ToastOverlay with fade-in/hold/fade-out animation; _on_station_activated shows "Connecting..."; _on_failover shows "Stream failed, trying next..." or "Stream exhausted"; _on_offline shows "Channel offline"; _on_playback_error shows truncated error; 14 toast tests + 7 integration toast tests pass |

**Score:** 5/5 roadmap success criteria verified

### Plan-Level Must-Have Gap

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | repo.update_last_played called on station activation | FAILED | grep for update_last_played in main_window.py returns zero matches; method exists in repo.py but is never called from _on_station_activated |

**Plan 37-04 frontmatter truth:** "StationListPanel.station_activated -> MainWindow.play(station) + 'Connecting...' toast + repo.update_last_played + NowPlayingPanel.bind_station"

The `repo.update_last_played(station.id)` call was specified in the plan but omitted from the implementation. Without it, the "Recently Played" section at the top of StationListPanel will never update with new play activity. The method exists in `musicstreamer/repo.py` (line 293) but is not invoked.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/ui_qt/station_tree_model.py` | StationTreeModel two-level tree | VERIFIED | 171 lines, full QAbstractItemModel implementation with provider grouping |
| `musicstreamer/ui_qt/station_list_panel.py` | StationListPanel with Recently Played + QTreeView | VERIFIED | 153 lines, station_activated Signal, recent QListView + tree QTreeView |
| `musicstreamer/ui_qt/now_playing_panel.py` | NowPlayingPanel 3-column layout | VERIFIED | 335 lines, all widgets with correct fixed sizes, cover art adapter |
| `musicstreamer/ui_qt/toast.py` | ToastOverlay with fade animation | VERIFIED | 109 lines, QPropertyAnimation, parent-owned, no WA_DeleteOnClose |
| `musicstreamer/ui_qt/main_window.py` | MainWindow with QSplitter + all wiring | VERIFIED | 140 lines, QSplitter with both panels, Player signals wired, toast triggers |
| `musicstreamer/ui_qt/icons/audio-x-generic-symbolic.svg` | Adwaita fallback icon | VERIFIED | 962 bytes, registered in icons.qrc |
| `musicstreamer/ui_qt/icons/media-playback-start-symbolic.svg` | Play icon | VERIFIED | 554 bytes |
| `musicstreamer/ui_qt/icons/media-playback-pause-symbolic.svg` | Pause icon | VERIFIED | 519 bytes |
| `musicstreamer/ui_qt/icons/media-playback-stop-symbolic.svg` | Stop icon | VERIFIED | 345 bytes |
| `tests/test_station_tree_model.py` | Model tests | VERIFIED | 9 tests |
| `tests/test_station_list_panel.py` | Panel tests | VERIFIED | 9 tests |
| `tests/test_now_playing_panel.py` | Now-playing tests | VERIFIED | 19 tests |
| `tests/test_toast_overlay.py` | Toast tests | VERIFIED | 14 tests |
| `tests/test_main_window_integration.py` | Integration tests | VERIFIED | 22 tests |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| StationListPanel.tree.clicked | station_activated signal | _on_tree_activated -> model.station_for_index | WIRED | station_list_panel.py:120-121, station_tree_model.py:56-62 |
| StationTreeModel.data DecorationRole | QPixmapCache | _icon_for_station | WIRED | station_tree_model.py:89-101, QPixmapCache.find/insert present |
| Player.title_changed | NowPlayingPanel.on_title_changed | bound-method connection | WIRED | main_window.py:97 |
| Player.elapsed_updated | NowPlayingPanel.on_elapsed_updated | bound-method connection | WIRED | main_window.py:98 |
| QSlider.valueChanged | player.set_volume | _on_volume_changed_live | WIRED | now_playing_panel.py:206, 286-288 |
| QSlider.sliderReleased | repo.set_setting | _on_volume_released | WIRED | now_playing_panel.py:207, 290-291 |
| Player.failover | MainWindow._on_failover -> toast | bound-method | WIRED | main_window.py:101 |
| StationListPanel.station_activated | MainWindow._on_station_activated | Qt AutoConnection | WIRED | main_window.py:94 |
| ToastOverlay show_toast | QPropertyAnimation windowOpacity | _fade_in.start | WIRED | toast.py:56-58, 87 |
| parent.resizeEvent | ToastOverlay._reposition | eventFilter QEvent.Resize | WIRED | toast.py:92-94 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| StationListPanel.tree | StationTreeModel | repo.list_stations() | DB query via Repo | FLOWING |
| StationListPanel.recent_view | QStandardItemModel | repo.list_recently_played(3) | DB query via Repo | FLOWING |
| NowPlayingPanel.icy_label | title text | Player.title_changed signal | Live ICY stream data | FLOWING |
| NowPlayingPanel.volume_slider | initial value | repo.get_setting("volume", "80") | DB query via Repo | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All phase 37 tests pass | QT_QPA_PLATFORM=offscreen pytest (5 test files) | 73 passed in 1.03s | PASS |
| Full suite regression | QT_QPA_PLATFORM=offscreen pytest | 339 passed in 2.60s | PASS |
| No self-capturing lambdas | grep 'lambda.*self' in all 5 ui_qt modules | 0 matches | PASS |
| No WA_DeleteOnClose | grep in all ui_qt modules | Only comment references in toast.py | PASS |
| No TODO/FIXME/placeholder | grep in all 5 modules | 0 matches | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| UI-01 | 37-01, 37-04 | Station list -- provider groups, recently-played, per-row logos, click-to-play | SATISFIED | StationTreeModel groups by provider with (N) suffix; StationListPanel renders recent + tree; station_activated signal fires on click; integration tests verify end-to-end |
| UI-02 | 37-02, 37-04 | Now-playing panel -- logo, Name/Provider, ICY, cover art, elapsed, volume, play/pause, stop | SATISFIED | NowPlayingPanel has 3-column layout with all listed widgets; star and edit deferred to phases 38/39 per plan; all slots wired |
| UI-12 | 37-03, 37-04 | Toast overlay for failover/connecting/error messages | SATISFIED | ToastOverlay with fade animation; wired to failover, offline, playback_error signals; "Connecting..." on station activation |
| UI-14 | 37-02 | YouTube 16:9 thumbnail in fixed slot, no sizing regression | SATISFIED | QPixmap.scaled with KeepAspectRatio; test_youtube_thumbnail_letterbox proves 320x180 -> 160x90 inside 160x160 fixed slot |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| musicstreamer/ui_qt/main_window.py | 139 | Truncation uses msg[:80] instead of msg[:79] (off-by-one vs plan spec) | Info | Truncated body is 81 chars instead of 80; cosmetic only |
| musicstreamer/ui_qt/main_window.py | 117-122 | Missing repo.update_last_played(station.id) | Warning | Recently-played list won't update on play |

### Human Verification Required

### 1. Visual Station List Layout

**Test:** Launch app with stations in DB, verify provider groups render with bold headers, station rows show 32x32 logos, recently-played section appears at top
**Expected:** Provider groups collapsible, station logos visible, recently-played shows top 3
**Why human:** Visual layout, font sizing, icon rendering quality cannot be verified programmatically

### 2. Now-Playing Panel Visual Layout

**Test:** Click a station, verify 3-column layout: 180x180 logo left, text/controls center, 160x160 cover art right
**Expected:** Labels readable, buttons clickable, volume slider functional, cover art appears after ICY title received
**Why human:** Visual proportions, spacing, font readability

### 3. Toast Notification Visibility

**Test:** Trigger failover or click a station, verify toast appears bottom-center with dark background
**Expected:** Toast fades in, holds, fades out smoothly; readable text on dark background
**Why human:** Animation smoothness, visual contrast, positioning

### Gaps Summary

One gap found: `repo.update_last_played(station.id)` is not called in `MainWindow._on_station_activated`. This was explicitly specified in Plan 37-04's must-have truths and in the plan's task action block. The method exists in `repo.py` but was omitted during implementation. Without it, the "Recently Played" section will stale -- it will show whatever was last played before Phase 37, and new play activity won't be recorded.

The fix is a one-line addition to `_on_station_activated` in `main_window.py` plus a corresponding integration test assertion.

---

_Verified: 2026-04-12T17:45:00Z_
_Verifier: Claude (gsd-verifier)_
