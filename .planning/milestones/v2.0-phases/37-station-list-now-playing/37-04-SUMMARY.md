---
phase: 37
plan: "04"
subsystem: ui_qt
tags: [qt, integration, main-window, splitter, signal-wiring, toast, qa-05]
dependency_graph:
  requires:
    - musicstreamer.ui_qt.station_list_panel.StationListPanel
    - musicstreamer.ui_qt.now_playing_panel.NowPlayingPanel
    - musicstreamer.ui_qt.toast.ToastOverlay
    - musicstreamer.player.Player
    - musicstreamer.repo.Repo
  provides:
    - musicstreamer.ui_qt.main_window.MainWindow (fully wired)
    - tests/test_main_window_integration.py
  affects:
    - musicstreamer/ui_qt/main_window.py
    - tests/test_ui_qt_scaffold.py
tech_stack:
  added: []
  patterns:
    - QSplitter(Qt.Horizontal) 30/70 initial split as centralWidget
    - Bound-method signal slots (no self-capturing lambdas — QA-05)
    - FakePlayer(QObject) test double with full Signal surface
    - ToastOverlay parented to QSplitter (centralWidget)
key_files:
  created:
    - tests/test_main_window_integration.py
  modified:
    - musicstreamer/ui_qt/main_window.py
    - tests/test_ui_qt_scaffold.py
decisions:
  - "MainWindow now requires player and repo at construction — no optional defaults. FakePlayer/FakeRepo added to test_ui_qt_scaffold.py to keep Phase 36 tests passing (Rule 1 auto-fix for broken scaffold tests)."
  - "ToastOverlay parented to self._splitter (the centralWidget) rather than self so it anchors correctly inside the splitter bounds."
metrics:
  duration_min: 20
  completed_date: "2026-04-12"
  tasks_completed: 2
  files_changed: 3
  tests_added: 22
  tests_total: 339
requirements: [UI-01, UI-02, UI-12, UI-14]
---

# Phase 37 Plan 04: MainWindow Integration Summary

**One-liner:** Wired Phase 36's bare-chrome QMainWindow with QSplitter layout hosting StationListPanel (left 30%) + NowPlayingPanel (right 70%) + ToastOverlay, with all Player signals connected via bound methods and 22 integration tests covering structure, signal flow, toast triggers, and QA-05 lifetime safety.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wire MainWindow with all panels + signal connections | 628e115 | musicstreamer/ui_qt/main_window.py, tests/test_ui_qt_scaffold.py |
| 2 | Integration tests (FakePlayer test double + 22 tests) | 209b78c | tests/test_main_window_integration.py |

## What Was Built

### MainWindow (`musicstreamer/ui_qt/main_window.py`)

Replaced the Phase 36 empty scaffold with a fully wired window:

```
QMainWindow
├── QMenuBar (≡ hamburger placeholder — Phase 40)
├── QSplitter(Qt.Horizontal) [centralWidget]
│   ├── StationListPanel(repo)  [30%, min 280px]
│   └── NowPlayingPanel(player, repo)  [70%, min 560px]
├── ToastOverlay(splitter)  [anchored to splitter bottom-centre]
└── QStatusBar
```

**Constructor signature changed:** `MainWindow(player, repo, parent=None)` — previously took no domain args. Phase 36 scaffold tests updated accordingly.

**Signal wiring (D-18, QA-05):**

| Signal | Handler | Effect |
|--------|---------|--------|
| `station_panel.station_activated` | `_on_station_activated` | `bind_station` + `player.play` + `on_playing_state_changed(True)` + "Connecting…" toast |
| `player.title_changed` | `now_playing.on_title_changed` | ICY label update |
| `player.elapsed_updated` | `now_playing.on_elapsed_updated` | Elapsed timer update |
| `player.failover(stream)` | `_on_failover` | "Stream failed, trying next…" or "Stream exhausted" toast + playing state |
| `player.offline(channel)` | `_on_offline` | "Channel offline" toast + playing state cleared |
| `player.playback_error(msg)` | `_on_playback_error` | "Playback error: {truncated}" toast |

**Toast copy (UI-SPEC Copywriting Contract):**
- Connecting: `"Connecting…"` (U+2026)
- Failover to next: `"Stream failed, trying next…"` (U+2026)
- All exhausted: `"Stream exhausted"`
- Twitch offline: `"Channel offline"`
- Playback error: `"Playback error: {msg[:80]}…"` (80-char truncation)

### Integration Tests (`tests/test_main_window_integration.py` — 22 tests)

`FakePlayer(QObject)` exposes the full Signal surface (`title_changed`, `failover`, `offline`, `playback_error`, `elapsed_updated`) plus `play_calls`, `pause_calls`, `stop_calls` tracking attributes. `FakeRepo` provides configurable `list_stations`, `list_recently_played`, `get_setting`, `set_setting`.

Test coverage:
- **Structure (7):** `test_central_widget_is_splitter`, `test_station_panel_present`, `test_now_playing_panel_present`, `test_splitter_orientation_horizontal`, `test_station_panel_min_width`, `test_now_playing_min_width`, `test_window_title`, `test_window_default_size`
- **Player → NowPlayingPanel (2):** `test_title_changed_updates_icy_label`, `test_elapsed_updated_updates_elapsed_label`
- **Station activation (3):** `test_station_activated_calls_player_play`, `test_station_activated_binds_now_playing`, `test_station_activated_sets_playing_state`
- **Toast wiring (7):** connecting, failover-with-stream, failover-none, failover-none-clears-state, offline, playback_error, long-message-truncation, show_toast-public-api
- **QA-05 lifetime (1):** `test_widget_lifetime_no_runtime_error` — 3 construct/signal-emit/destroy cycles with no RuntimeError

**Full suite: 339 passed** (317 baseline + 22 new), 0 failures.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Phase 36 scaffold tests broke after MainWindow constructor signature change**
- **Found during:** Task 1 verification.
- **Issue:** `test_ui_qt_scaffold.py` called `MainWindow()` with no args; new signature requires `player` and `repo`.
- **Fix:** Added `_FakePlayer` and `_FakeRepo` stubs to `test_ui_qt_scaffold.py` and a `_make_window()` helper; updated the two test functions that called `MainWindow()` directly.
- **Files modified:** `tests/test_ui_qt_scaffold.py`
- **Commit:** `628e115` (same task commit)

## Deferred Issues

None.

## Threat Flags

None — this plan introduces no new network surface, auth paths, or trust boundary crossings. Signal connections are local in-process (no IPC). The one untrusted string path (`player.playback_error`) is 80-char truncated before display, and ICY metadata is already `Qt.PlainText` locked in `NowPlayingPanel`.

## Known Stubs

None. All panels are live and wired. Phase 38 (favorites/search) and Phase 39 (dialogs) will add functionality without modifying this integration layer.

## Self-Check: PASSED

- `musicstreamer/ui_qt/main_window.py` exists — FOUND
- `tests/test_main_window_integration.py` exists — FOUND
- `tests/test_ui_qt_scaffold.py` updated — FOUND
- Commit `628e115` exists (Task 1)
- Commit `209b78c` exists (Task 2)
- Full test suite: 339 passed (317 + 22 new), 0 failures
- `grep 'lambda.*self' musicstreamer/ui_qt/main_window.py` → no match (QA-05)
