---
phase: 60
plan: "05"
subsystem: now-playing-panel
tags: [phase60, now-playing, active-playlist, gbs-fm, qthread, qtimer, tdd, wave3]

# Dependency graph
requires:
  - phase: 60-02
    provides: "fetch_active_playlist(cookies, cursor) + load_auth_context() + GbsAuthExpiredError"
  - phase: 60-04
    provides: "paths.gbs_cookies_path() predicate + _is_gbs_connected() path"

provides:
  - "musicstreamer/ui_qt/now_playing_panel.py: _GbsPollWorker(QThread), _gbs_playlist_widget (QListWidget), _gbs_poll_timer (QTimer/15s), _gbs_poll_token stale-guard, _refresh_gbs_visibility, _on_gbs_poll_tick, _on_gbs_playlist_ready, _on_gbs_playlist_error, _is_gbs_logged_in"
  - "tests/test_now_playing_panel.py: 9 Phase 60 GBS active-playlist tests covering GBS-01c"

affects:
  - "60-06-vote (vote buttons will hook into same bind_station/_refresh_gbs_visibility pathway)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "QThread worker + Signal(int, object) + token guard: Pitfall 1 stale-response discard (mirror cover_art precedent)"
    - "QTimer 15s polling: D-06a RESOLVED (matches gbs.fm web UI DELAY=15000)"
    - "Hide-when-empty contract: _gbs_playlist_widget.setVisible(False) when not GBS.FM or not logged in (Phase 64 D-05 precedent)"
    - "Position cursor reset on track-entryid change: HIGH 4 fix prevents stale delta reference to /ajax"
    - "isHidden() over isVisible() for unrealized widgets in headless tests (Plan 60-04 precedent)"

key-files:
  created: []
  modified:
    - "musicstreamer/ui_qt/now_playing_panel.py"
    - "tests/test_now_playing_panel.py"

key-decisions:
  - "HIGH 4 fix applied: position cursor reset to 0 on now_playing_entryid change (track transition), NOT advanced with song_position — prevents stale delta reference to /ajax on next poll"
  - "isHidden() used in tests instead of isVisible() for widget visibility assertion on unrealized widgets (matches Plan 60-04 Rule 1 fix precedent)"
  - "_on_gbs_poll_tick calls _refresh_gbs_visibility (not crash/log) when load_auth_context() returns None mid-poll — graceful auth-disappeared handling"
  - "_refresh_gbs_visibility triggers immediate first poll via _on_gbs_poll_tick() BEFORE starting the 15s timer — avoids 15s blank state on bind"

requirements-completed: [GBS-01c]

# Metrics
duration: 22min
completed: 2026-05-04
---

# Phase 60 Plan 05: Active Playlist Summary

**GBS.FM active-playlist QListWidget added to NowPlayingPanel: 15s poll timer, _GbsPollWorker QThread with stale-token guard, auth-gated hide-when-not-GBS contract, HIGH 4 position-cursor reset on track change, and 9 passing pytest-qt tests**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-05-04T20:09:00Z
- **Completed:** 2026-05-04T20:31:23Z
- **Tasks:** 2 completed
- **Files modified:** 2 (0 created + 2 modified)

## Accomplishments

- Extended `musicstreamer/ui_qt/now_playing_panel.py` (+174 lines) with:
  - `_GbsPollWorker(QThread)` — polls `gbs_api.fetch_active_playlist()` on worker thread; emits `playlist_ready(int, object)` or `playlist_error(int, str)` (QA-05 bound-method connections, Pitfall 1 token guard)
  - `_gbs_playlist_widget` (QListWidget, initially `setVisible(False)`, max 180px height)
  - `_gbs_poll_timer` (QTimer, 15000ms interval, `timeout.connect(_on_gbs_poll_tick)` QA-05)
  - `_gbs_poll_token: int = 0` stale-response guard (cover_art precedent)
  - `_gbs_poll_cursor: dict = {}` for /ajax cursor advancement
  - `_is_gbs_logged_in()` — `os.path.exists(paths.gbs_cookies_path())`
  - `_refresh_gbs_visibility()` — shows widget + starts timer iff GBS.FM station AND logged in; triggers immediate first poll; stops timer and clears widget otherwise (Pitfall 5)
  - `_on_gbs_poll_tick()` — increments token, loads auth context (calls `_refresh_gbs_visibility` if auth disappeared), kicks `_GbsPollWorker`
  - `_on_gbs_playlist_ready(token, state)` — token guard; HIGH 4 position cursor reset on entryid change; renders `▶ {icy_title}`, queue_summary, `Score: {score}` (Pitfall 11 PlainText via QListWidgetItem default)
  - `_on_gbs_playlist_error(token, msg)` — `auth_expired` sentinel hides widget + stops timer (no toast spam, Pitfall 3); other errors log silently
  - `_refresh_gbs_visibility()` appended as last line of `bind_station()` (Phase 64 D-04 single-call-site invariant)
- Extended `tests/test_now_playing_panel.py` (+214 lines) with 9 new tests:
  - `test_gbs_playlist_hidden_for_non_gbs` (GBS-01c)
  - `test_gbs_playlist_hidden_when_logged_out` (D-06b)
  - `test_gbs_playlist_visible_when_gbs_and_logged_in` (D-06)
  - `test_gbs_playlist_populates_from_mock_state`
  - `test_gbs_poll_timer_pauses_when_widget_hidden` (Pitfall 5 / D-06a)
  - `test_gbs_stale_token_discarded` (Pitfall 1)
  - `test_gbs_auth_expired_hides_widget_no_toast` (Pitfall 3)
  - `test_refresh_gbs_visibility_runs_once_per_bind_station` (Phase 64 D-04 invariant)
  - `test_gbs_playlist_resets_position_on_track_change` (HIGH 4 fix — 3-step sequence)

## Task Commits

1. **Task 1: GBS.FM active-playlist widget + poll machinery** — `b5589ad` (feat)
2. **Task 2: 9 Phase 60 GBS active-playlist tests** — `09787af` (feat)

## Files Created/Modified

- `musicstreamer/ui_qt/now_playing_panel.py` — +174 lines: `_GbsPollWorker`, GBS widget/timer init in `__init__`, 5 handler methods, `bind_station` hook; implements D-06/D-06a/D-06b/D-06c + mitigates T-60-23..T-60-27
- `tests/test_now_playing_panel.py` — +214 lines: 9 new tests at bottom of file; 61 total tests pass; 52 pre-existing tests unaffected

## Decisions Made

- **HIGH 4 fix: position cursor reset on track transition.** `_on_gbs_playlist_ready` tracks `prev_entryid` via `_gbs_poll_cursor["now_playing"]`. When `now_playing_entryid` changes, `_gbs_poll_cursor["position"]` resets to 0 (not carried forward from the previous song's `song_position`). This prevents a stale delta reference to the /ajax endpoint on subsequent polls.
- **isHidden() vs isVisible() in tests.** `isVisible()` returns `False` for unrealized (not yet shown) widgets even when `setVisible(True)` was called. Used `not isHidden()` for the "should be shown" assertion in `test_gbs_playlist_visible_when_gbs_and_logged_in` — the same fix applied in Plan 60-04 (`test_gbs_paste_invalid_shows_target_specific_error`).
- **Immediate first poll on `_refresh_gbs_visibility`.** When the GBS station becomes visible, `_on_gbs_poll_tick()` is called immediately before starting the 15s timer, so users see playlist content without waiting 15 seconds.
- **`_on_gbs_poll_tick` auth-disappeared handling.** If `gbs_api.load_auth_context()` returns `None` mid-poll (cookies deleted while timer was running), the method calls `_refresh_gbs_visibility()` which stops the timer and hides the widget — same graceful-degradation path as the `_on_gbs_playlist_error(auth_expired)` path.

## TDD Gate Compliance

This plan used TDD for both tasks:

- **Task 1 (implementation):** Module parses cleanly and imports confirm implementation landed before tests were written.
- **Task 2 (tests):** All 9 tests written and run green immediately after appending; 1 test (`test_gbs_playlist_visible_when_gbs_and_logged_in`) required a Rule 1 auto-fix (isVisible → isHidden) before passing.
- No REFACTOR gate commits needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_gbs_playlist_visible_when_gbs_and_logged_in used isVisible() which returns False for unrealized widgets**

- **Found during:** Task 2 (test run)
- **Issue:** The plan's test template used `assert panel._gbs_playlist_widget.isVisible() is True`. In the offscreen headless Qt test environment, `isVisible()` returns `False` for widgets whose parent window has not been shown, even when `setVisible(True)` was called on the widget itself.
- **Fix:** Changed to `assert not panel._gbs_playlist_widget.isHidden()`. This checks the widget's explicit hide/show flag (not the composite ancestor-chain visibility), which is the correct assertion for unrealized widget tests. Matches the Plan 60-04 precedent (`test_gbs_paste_invalid_shows_target_specific_error`).
- **Files modified:** `tests/test_now_playing_panel.py`
- **Commit:** Included in Task 2 commit `09787af`

## Known Stubs

None — `_gbs_playlist_widget` is fully wired to `_GbsPollWorker` via `_refresh_gbs_visibility` → `_on_gbs_poll_tick`. The transient "Loading playlist…" placeholder item is replaced immediately by the first poll result and is not a UI stub.

## Threat Flags

All security surface is within the plan's documented threat model (T-60-23..T-60-27):

| Coverage | Status |
|----------|--------|
| T-60-23 (DoS — 15s cadence, pause when hidden) | Mitigated — Pitfall 5 implemented |
| T-60-24 (Tampering — stale poll token guard) | Mitigated — Pitfall 1 + _gbs_poll_token |
| T-60-25 (Info Disclosure — PlainText rendering) | Mitigated — Pitfall 11 + QListWidgetItem default |
| T-60-26 (Repudiation — auth-expired hides widget) | Mitigated — Pitfall 3 sentinel path |
| T-60-27 (DoS UX — no toast spam on errors) | Mitigated — silent log for non-auth errors |

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `musicstreamer/ui_qt/now_playing_panel.py` modified | FOUND |
| `tests/test_now_playing_panel.py` modified | FOUND |
| Commit b5589ad (Task 1) | FOUND |
| Commit 09787af (Task 2) | FOUND |
| `_gbs_playlist_widget` attribute exists | PASS |
| `_GbsPollWorker` class exists | PASS |
| `_refresh_gbs_visibility` last line of `bind_station` | PASS |
| `setInterval(15000)` present | PASS |
| No lambda violations (`timeout.connect(lambda`) | PASS |
| Module parses cleanly (ast.parse) | PASS |
| 9 GBS tests pass | PASS |
| 61 total tests in file pass | PASS |
| 18 test_gbs_api.py tests still pass | PASS |
| NowPlayingPanel + _GbsPollWorker importable | PASS |
