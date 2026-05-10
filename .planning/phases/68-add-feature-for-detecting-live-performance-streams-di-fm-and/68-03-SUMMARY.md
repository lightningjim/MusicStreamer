---
phase: 68
plan: "03"
subsystem: ui_qt/now_playing_panel
tags: [pyside6, qthread-worker, qtimer-singleshot, qa-05, qt-plaintext, signal-emit, tdd-green]
dependency_graph:
  requires: [68-01, 68-02]
  provides:
    - NowPlayingPanel._AaLiveWorker (QThread)
    - NowPlayingPanel.live_status_toast Signal
    - NowPlayingPanel._live_badge QLabel (LIVE chip)
    - NowPlayingPanel._refresh_live_status (C-03 decision tree + T-01 toasts)
    - NowPlayingPanel poll loop lifecycle (start/stop/tick/ready/error/reschedule)
  affects:
    - musicstreamer/ui_qt/now_playing_panel.py
    - tests/test_now_playing_panel.py
tech_stack:
  added: []
  patterns:
    - _AaLiveWorker mirrors _GbsPollWorker shape (typed signals, single-attempt run, SYNC-05 retention)
    - QTimer.setSingleShot(True) + adaptive cadence (60s DI.fm, 5min others)
    - Pitfall 5 _first_bind_check flag: distinguishes bind-to-already-live (T-01a) from off->on (T-01b)
    - Pitfall 4 ordering: _refresh_similar_stations -> _refresh_live_status -> _refresh_gbs_visibility
    - Anti-pattern §1: worker run() has zero QTimer references
    - Qt.PlainText on _live_badge (V5 ASVS — AA API show names may contain HTML metacharacters)
    - palette(highlight)/palette(highlighted-text) chip QSS — consistent with station_list_panel.py
key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/now_playing_panel.py
    - tests/test_now_playing_panel.py
decisions:
  - "Pitfall 5 _first_bind_check flag clears after first _refresh_live_status to prevent duplicate T-01a toast on first title_changed"
  - "Rule 1 deviation: two Plan 01 tests used isVisible() is True in headless mode (always False when parent not shown); fixed to not isHidden() following Phase 60 precedent at test line 1258"
  - "_AaLiveWorker.run() uses local import alias _fetch to keep module test-importable without Qt and allow mock at specific resolution path"
  - "_refresh_live_status placed in its own Phase 68 section after Phase 67 _on_similar_collapse_clicked, before Phase 60 GBS section"
metrics:
  duration_minutes: 18
  completed_date: "2026-05-10"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 2
---

# Phase 68 Plan 03: NowPlayingPanel Live Stream Detection Wiring Summary

## One-Liner

NowPlayingPanel Phase 68 surface landed: _AaLiveWorker QThread, live_status_toast signal, LIVE badge chip, _refresh_live_status C-03 decision tree with T-01a/b/c transition toasts, Pitfall 5 _first_bind_check guard, and adaptive poll loop lifecycle — all 14 Plan 01 RED tests GREEN.

## What Was Done

### Task 1: Scaffold (d95c5a4)

Five insertions to `musicstreamer/ui_qt/now_playing_panel.py`:

1. **Module import** — `from musicstreamer.aa_live import fetch_live_map, detect_live_from_icy, get_di_channel_key` added after the existing url_helpers import block.

2. **`_AaLiveWorker` class** — inserted between `_GbsPollWorker` and `_GbsVoteWorker` (line ~102). Mirrors `_GbsPollWorker` shape: `finished = Signal(object)` / `error = Signal(str)` / single-attempt `run()`. Worker uses a local import `from musicstreamer.aa_live import fetch_live_map as _fetch` inside `run()` to keep the class test-importable without Qt and allow mock at the local resolution path. Zero QTimer references inside the class body (Anti-pattern §1).

3. **`live_status_toast = Signal(str)`** — declared adjacent to `gbs_vote_error_toast` with T-01a/b/c comment explaining toast semantics.

4. **5 instance attributes** — `_live_map`, `_live_show_active`, `_first_bind_check`, `_aa_poll_timer`, `_aa_live_worker` added after `_similar_cache` in `__init__`.

5. **LIVE badge widget** — replaced `center.addWidget(self.icy_label)` with `icy_row = QHBoxLayout()` containing `_live_badge` (left, hidden by default, Qt.PlainText, palette(highlight) chip QSS) and `icy_label` (right, stretch=1). Existing icy_label font/PlainText format preserved.

### Task 2: Behavior + Lifecycle (e01a97c)

Six edits to `musicstreamer/ui_qt/now_playing_panel.py` plus one Rule 1 test fix:

1. **`bind_station` extension** — `self._first_bind_check = True; self._refresh_live_status()` inserted between `_refresh_similar_stations()` and `_refresh_gbs_visibility()` (Pitfall 4 ordering preserved).

2. **`on_title_changed` extension** — `self._refresh_live_status()` appended as final statement of the method (C-02; fires irrespective of GBS suppression, outside the icy_disabled early-return).

3. **`_detect_live_for_current_station()`** — C-03 decision tree: AA key lookup in `_live_map` when key present and station is DI.fm; else ICY pattern fallback via `detect_live_from_icy(_last_icy_title)`. Slots-never-raise: returns None on any exception.

4. **`_refresh_live_status()`** — compares `show_name is not None` vs `_live_show_active` for transition detection. Emits T-01a ("Now live: {show} on {station}") on bind-to-already-live, T-01b ("Live show starting: {show}") on off→on, T-01c ("Live show ended on {station}") on on→off. Clears `_first_bind_check` after first evaluation (Pitfall 5). Slots-never-raise with badge-hide fallback.

5. **Poll loop lifecycle** — 7 methods: `is_aa_poll_active`, `start_aa_poll_loop` (no-op when no key), `stop_aa_poll_loop` (idempotent), `_on_aa_poll_tick` (spawns worker, QueuedConnection), `_on_aa_live_ready` (updates cache, calls `_refresh_live_status`), `_on_aa_live_error` (silent, reschedules), `_reschedule_aa_poll` (60s for DI.fm, 300s otherwise).

6. **`tests/test_now_playing_panel.py` Rule 1 fix** — two Plan 01 tests used `isVisible() is True` for headless unrealized widgets (always False; same documented pitfall at line 1258). Fixed to `not isHidden()` following Phase 60 precedent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed isVisible() headless assertion in 2 Plan 01 tests**
- **Found during:** Task 2 verification (all 14 tests run, 2 failed)
- **Issue:** `test_live_badge_visible_when_live` and `test_live_badge_via_icy_pattern_for_non_aa_station` used `panel._live_badge.isVisible() is True`. In Qt headless testing (offscreen platform), `isVisible()` returns False when parent widget has not been shown — regardless of `setVisible(True)` having been called on the child. The badge was correctly receiving `setVisible(True)` but the assertion was semantically wrong.
- **Fix:** Changed `assert panel._live_badge.isVisible() is True` → `assert not panel._live_badge.isHidden()`. This matches Phase 60 precedent documented at test line 1258-1260: "isVisible() returns False for unrealized widgets even when setVisible(True) was called — use isHidden() to check explicit flag."
- **Files modified:** `tests/test_now_playing_panel.py` (lines 2842, 2852)
- **Commit:** e01a97c

## Verification Results

| Check | Result |
|-------|--------|
| All 14 Phase 68 panel tests | 14/14 PASSED |
| Phase 67 similar/sibling regression | 71/71 PASSED |
| Phase 60 GBS regression | Included in above |
| Plan 02 aa_live regression | 21/21 PASSED |
| Full test_now_playing_panel.py | 127/127 PASSED |
| Anti-pattern §1 (no QTimer in worker) | 0 QTimer refs in _AaLiveWorker body |
| T-40-04 RichText invariant | 3 RichText lines (unchanged from baseline) |
| bind_station ordering (Pitfall 4) | similar(34) → live(46) → gbs(51) in awk output |
| Only now_playing_panel.py + test modified | Confirmed via git diff --name-only |

## Known Stubs

None. All live-status behavior is fully wired. The poll loop produces real _AaLiveWorker requests (Plan 05 will wire `start_aa_poll_loop` to MainWindow startup; until then, the loop is dormant — no timer starts unless `start_aa_poll_loop()` is explicitly called).

## Threat Flags

None. No new network endpoints introduced. The `_AaLiveWorker.run()` calls `fetch_live_map` which was already audited in Plan 02 (GET-only, no credentials, A-04 silent failure). The `_live_badge` text "LIVE" is hardcoded — no AA API data touches the badge text (only badge visibility is driven by live state). Show names appear in toast strings via `live_status_toast` but not in the badge widget itself, so Qt.PlainText on the badge is belt-and-suspenders (the badge text is static).

## Self-Check: PASSED

- `musicstreamer/ui_qt/now_playing_panel.py` exists and was committed: d95c5a4, e01a97c
- `tests/test_now_playing_panel.py` fix committed: e01a97c
- git log confirms both commits on worktree-agent-a56a20e5659b292cf branch
- 127/127 test_now_playing_panel.py tests pass
- 21/21 test_aa_live.py tests pass
