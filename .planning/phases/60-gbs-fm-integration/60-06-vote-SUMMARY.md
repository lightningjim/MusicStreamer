---
phase: 60
plan: "06"
subsystem: now-playing-panel
tags: [phase60, now-playing, vote, optimistic-ui, gbs-fm, qthread, tdd, wave4]

# Dependency graph
requires:
  - phase: 60-02
    provides: "vote_now_playing(entryid, vote, cookies) + GbsAuthExpiredError + load_auth_context()"
  - phase: 60-04
    provides: "paths.gbs_cookies_path() + AccountsDialog GBS.FM group"
  - phase: 60-05
    provides: "_GbsPollWorker + _on_gbs_playlist_ready + _refresh_gbs_visibility + _gbs_poll_token"

provides:
  - "musicstreamer/ui_qt/now_playing_panel.py: _GbsVoteWorker(QThread), 5 _gbs_vote_buttons (QPushButton), _gbs_vote_token, _gbs_vote_worker, _gbs_current_entryid, _last_confirmed_vote, _apply_vote_highlight, _current_highlighted_vote, _on_gbs_vote_clicked, _on_gbs_vote_finished, _on_gbs_vote_error, gbs_vote_error_toast Signal"
  - "musicstreamer/ui_qt/main_window.py: gbs_vote_error_toast.connect(show_toast) wiring"
  - "tests/test_now_playing_panel.py: 10 Phase 60 GBS vote tests covering GBS-01d"

affects:
  - "NowPlayingPanel: now shows 5 vote buttons when GBS.FM station active + user logged in"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "QThread worker + Signal(int,int,int,str) + token guard: Pitfall 2 server-truth confirmation (mirrors _GbsPollWorker shape)"
    - "setProperty('vote_value', N) + sender().property(): QA-05 compliant multi-button slot (no lambda capture)"
    - "Optimistic UI + rollback: _apply_vote_highlight called immediately on click; rolled back in _on_gbs_vote_error"
    - "BLOCKER 1 fix: _last_confirmed_vote tracks server-confirmed state separately from QPushButton.isChecked() — Qt toggles checkable buttons before 'clicked' fires"
    - "_gbs_current_entryid set ONLY by _on_gbs_playlist_ready from /ajax response (Pitfall 1)"

key-files:
  created: []
  modified:
    - "musicstreamer/ui_qt/now_playing_panel.py"
    - "musicstreamer/ui_qt/main_window.py"
    - "tests/test_now_playing_panel.py"

key-decisions:
  - "BLOCKER 1 fix: _last_confirmed_vote separate from QPushButton.isChecked() — Qt toggles checkable button state before 'clicked' emits, making post-click highlight unreliable for the vote-clear check"
  - "_GbsVoteWorker placed alongside _GbsPollWorker (above _MutedLabel) for cohesion"
  - "gbs_vote_error_toast Signal added to NowPlayingPanel; wired to MainWindow.show_toast (QA-05 bound method)"
  - "Vote buttons placed below playlist widget in center QVBoxLayout (D-07 'near controls row' — accessible but subordinate to ICY title)"
  - "test_gbs_vote_clicking_same_value_clears uses plain _CapturingWorker class (not MagicMock subclass) to reliably capture __init__ kwargs — MagicMock intercepts the call protocol and prevents kwargs capture"

requirements-completed: [GBS-01d]

# Metrics
duration: 20min
completed: 2026-05-04
---

# Phase 60 Plan 06: Vote Control Summary

**GBS.FM vote control added to NowPlayingPanel: 5 checkable QPushButton widgets with optimistic UI, _GbsVoteWorker QThread round-trip, server-truth confirmation (Pitfall 2), _gbs_current_entryid stamped only from /ajax (Pitfall 1), and 10 passing pytest-qt tests**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-04T20:23:00Z
- **Completed:** 2026-05-04T20:43:02Z
- **Tasks:** 2 completed
- **Files modified:** 3 (0 created + 3 modified)

## Accomplishments

- Extended `musicstreamer/ui_qt/now_playing_panel.py` (+198 lines) with:
  - `_GbsVoteWorker(QThread)` — sends vote on worker thread; emits `vote_finished(int, int, int, str)` or `vote_error(int, int, str)` (QA-05 bound-method connections, Pitfall 2 server-truth payloads)
  - `gbs_vote_error_toast = Signal(str)` — forwarded to `MainWindow.show_toast`
  - `_gbs_vote_buttons: list[QPushButton]` — 5 checkable buttons (labels "1".."5"), hidden by default
  - `_gbs_vote_token: int = 0` stale-response guard
  - `_gbs_current_entryid: Optional[int] = None` — set ONLY by `_on_gbs_playlist_ready` (Pitfall 1)
  - `_last_confirmed_vote: int = 0` — BLOCKER 1 fix; tracks server-confirmed vote value separately from button check state
  - `_apply_vote_highlight(vote_value)` — sets/clears `isChecked()` on all 5 buttons
  - `_current_highlighted_vote()` — reads highlighted button value (used by tests)
  - `_on_gbs_vote_clicked()` — QA-05 multi-button slot via `sender().property('vote_value')`; optimistic highlight + _GbsVoteWorker kick
  - `_on_gbs_vote_finished(token, server_user_vote, prior_vote, score)` — Pitfall 2: apply server-returned vote; update `_last_confirmed_vote`
  - `_on_gbs_vote_error(token, prior_vote, msg)` — rollback + toast via `gbs_vote_error_toast`
  - Extended `_refresh_gbs_visibility`: vote buttons share same auth+provider predicate as playlist widget
  - Extended `_on_gbs_playlist_ready`: captures `now_playing_entryid` into `_gbs_current_entryid`; applies server `user_vote` highlight; updates `_last_confirmed_vote`
- Modified `musicstreamer/ui_qt/main_window.py` (+1 line):
  - `self.now_playing.gbs_vote_error_toast.connect(self.show_toast)` — QA-05 bound-method connection
- Extended `tests/test_now_playing_panel.py` (+233 lines) with 10 new tests:
  - `test_gbs_vote_buttons_hidden_for_non_gbs` (D-07)
  - `test_gbs_vote_buttons_hidden_when_logged_out` (D-04 ladder #3)
  - `test_gbs_vote_buttons_visible_when_gbs_and_logged_in` (D-07)
  - `test_gbs_vote_optimistic_success` (Pitfall 2 server-truth)
  - `test_gbs_vote_optimistic_rollback_on_error` (rollback + toast)
  - `test_gbs_vote_optimistic_rollback_on_auth_expired` (auth sentinel toast)
  - `test_gbs_vote_entryid_only_from_ajax` (Pitfall 1)
  - `test_gbs_vote_clicking_same_value_clears` (vote=0 on re-click)
  - `test_gbs_vote_stale_token_discarded` (stale token guard)
  - `test_gbs_vote_no_entryid_ignores_click` (no-entryid no-op)

## Task Commits

1. **Task 1: GBS.FM vote control implementation** — `46d0941` (feat)
2. **Task 2: 10 Phase 60 GBS vote tests** — `43b6f19` (feat)

## Files Created/Modified

- `musicstreamer/ui_qt/now_playing_panel.py` — +198 lines: `_GbsVoteWorker`, `gbs_vote_error_toast` Signal, vote button construction in `__init__`, `_refresh_gbs_visibility` extension, `_on_gbs_playlist_ready` extension, 5 handler/helper methods; implements D-07/D-07a..D-07d + mitigates T-60-28..T-60-33
- `musicstreamer/ui_qt/main_window.py` — +1 line: `gbs_vote_error_toast.connect(show_toast)` wiring
- `tests/test_now_playing_panel.py` — +233 lines: 10 new tests at bottom of file; 71 total tests pass; 61 pre-existing tests unaffected

## Decisions Made

- **BLOCKER 1 fix: `_last_confirmed_vote` separate from `QPushButton.isChecked()`.** Qt toggles a checkable button's check state BEFORE emitting `clicked`. After the toggle, reading `isChecked()` in the `clicked` slot gives the NEW (post-toggle) state, not the prior state. The vote-clear logic (`vote_value == prior_vote → submit_value=0`) requires the PREVIOUS server-confirmed vote — not what the button shows. `_last_confirmed_vote` tracks this reliably; it's updated by `_on_gbs_playlist_ready` (from /ajax `user_vote`) and `_on_gbs_vote_finished` (from server round-trip).
- **_CapturingWorker in test_gbs_vote_clicking_same_value_clears.** The plan template used `class FakeVoteWorker(MagicMock)` — but MagicMock subclasses intercept the call protocol (`__call__`) rather than `__init__`, so kwargs never reach the custom `__init__`. Used a plain Python class `_CapturingWorker` with no-op signal stubs instead. Matches Rule 1 auto-fix (bug in test template).
- **Vote buttons in center QVBoxLayout, below playlist widget.** The plan said "near the controls row" (D-07). The center column layout already has: name/provider → sibling → ICY → elapsed → controls row → stats widget → playlist widget. Adding vote buttons after the playlist widget keeps the visual hierarchy stable and ensures the controls row remains the primary interaction target.

## TDD Gate Compliance

This plan used TDD for both tasks:

- **Task 1 (implementation first — GREEN):** All implementation landed, module parses cleanly, and imports confirm. Followed by Task 2 tests.
- **Task 2 (tests):** All 10 tests written and run green on first pass (except `test_gbs_vote_clicking_same_value_clears` which required a Rule 1 fix to the test template — see Deviations).
- No REFACTOR gate commits needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_gbs_vote_clicking_same_value_clears used `MagicMock` subclass that silently discards `__init__` kwargs**

- **Found during:** Task 2 (test run — `KeyError: 'vote_value'`)
- **Issue:** The plan's test template had `class FakeVoteWorker(MagicMock)`. When Python instantiates a MagicMock subclass, `MagicMock.__call__` intercepts the call and returns a new mock object — the custom `__init__` is never invoked with the keyword arguments from the production code's `_GbsVoteWorker(token=..., vote_value=..., ...)` call. So `captured_worker_args` remained empty.
- **Fix:** Replaced with a plain Python `_CapturingWorker` class that stores `**kwargs` in `__init__` and provides no-op `start()` and signal stub methods. This is a standard pattern for capturing constructor args in Qt tests where the class receives `Signal` connections.
- **Files modified:** `tests/test_now_playing_panel.py`
- **Commit:** Included in Task 2 commit `43b6f19`

**2. [Rule 2 - Missing critical functionality] `fake_repo` fixture referenced in plan test templates not defined in test file**

- **Found during:** Task 2 (before test run — code inspection)
- **Issue:** The plan's test action used `def test_gbs_vote_*(qtbot, fake_repo, tmp_path, monkeypatch)` — but `fake_repo` is not a pytest fixture in this test file. The existing GBS tests use `_construct_gbs_panel(qtbot)` which internally creates `FakeRepo`. Leaving `fake_repo` in the signature would cause pytest to fail with `fixture 'fake_repo' not found`.
- **Fix:** Removed `fake_repo` from all 10 test signatures. The tests use `_construct_gbs_panel(qtbot)` which already constructs a `FakeRepo` internally.
- **Files modified:** `tests/test_now_playing_panel.py`
- **Commit:** Included in Task 2 commit `43b6f19`

## Known Stubs

None — `_gbs_vote_buttons` are fully wired to `_on_gbs_vote_clicked` → `_GbsVoteWorker` → `gbs_api.vote_now_playing`. The optimistic highlight is confirmed or rolled back by the worker's signal emissions. No data is hardcoded or placeholder.

## Threat Flags

All security surface is within the plan's documented threat model (T-60-28..T-60-33):

| Coverage | Status |
|----------|--------|
| T-60-28 (Tampering — vote-on-stale-track) | Mitigated — `_gbs_current_entryid` set ONLY from /ajax |
| T-60-29 (Repudiation — optimistic UI desync) | Mitigated — `_on_gbs_vote_finished` applies server `user_vote` |
| T-60-30 (DoS — vote spam) | Mitigated — no retries; `_gbs_vote_token` guards stale responses |
| T-60-31 (Spoofing — auth expiry mid-vote) | Mitigated — "auth_expired" sentinel → rollback + toast |
| T-60-32 (Info Disclosure — lambda self-capture) | Mitigated — all buttons connect via bound method; vote value via `setProperty` + `sender().property()` |
| T-60-33 (Info Disclosure — HTML injection in labels) | Accepted — hard-coded "1".."5" labels, not user-controlled |

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `musicstreamer/ui_qt/now_playing_panel.py` modified | FOUND |
| `musicstreamer/ui_qt/main_window.py` modified | FOUND |
| `tests/test_now_playing_panel.py` modified | FOUND |
| Commit 46d0941 (Task 1) | FOUND |
| Commit 43b6f19 (Task 2) | FOUND |
| `_gbs_vote_buttons` attribute exists (5 buttons) | PASS |
| `_GbsVoteWorker` class exists | PASS |
| `gbs_vote_error_toast` Signal declared | PASS |
| `gbs_vote_error_toast.connect(show_toast)` in main_window | PASS |
| `_gbs_current_entryid` set only in `_on_gbs_playlist_ready` | PASS |
| `_last_confirmed_vote` tracks server-confirmed vote | PASS |
| No lambda violations (`clicked.connect(lambda`) | PASS |
| Module parses cleanly (ast.parse) | PASS |
| 10 GBS vote tests pass | PASS |
| 71 total tests in file pass | PASS |
| 18 test_gbs_api.py tests still pass | PASS |
| NowPlayingPanel + _GbsVoteWorker importable | PASS |
