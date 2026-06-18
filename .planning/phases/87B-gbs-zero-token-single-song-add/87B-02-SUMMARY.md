---
phase: 87B-gbs-zero-token-single-song-add
plan: "02"
subsystem: gbs-ui
tags: [gbs, add-song, now-playing-panel, main-window, ui, wiring, docs-amendment]
dependency_graph:
  requires:
    - 87B-01 (add_song_zero_token wrapper + capture hook)
  provides:
    - now_playing_panel._gbs_add_btn (persistent "Add a song" QPushButton)
    - now_playing_panel.add_song_requested (Signal)
    - now_playing_panel._on_add_song_clicked (slot)
    - now_playing_panel.trigger_gbs_repoll() (public method)
    - main_window._open_gbs_search_dialog: submission_completed → trigger_gbs_repoll wiring
    - main_window.__init__: add_song_requested → _open_gbs_search_dialog wiring
    - gbs_search_dialog._GbsSubmitWorker.run: uses add_song_zero_token() (not bare submit)
  affects:
    - musicstreamer/ui_qt/now_playing_panel.py
    - musicstreamer/ui_qt/main_window.py
    - musicstreamer/ui_qt/gbs_search_dialog.py
    - tests/test_now_playing_panel.py
    - tests/test_main_window_gbs.py
    - .planning/REQUIREMENTS.md (GBS-TOKEN-01/04/05 amended)
    - .planning/ROADMAP.md (Phase 87b line-45 one-liner + SC#1/#3/#4/#5 amended)
    - .planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md (created)
tech_stack:
  added: []
  patterns:
    - Signal() class-level declaration on NowPlayingPanel (mirrors submission_completed in GBSSearchDialog)
    - QA-05 bound-method signal connections throughout
    - should_show = is_gbs and logged_in visibility predicate (D-05 — token-count-independent)
    - trigger_gbs_repoll() direct _on_gbs_poll_tick() call (mirrors _on_gbs_relogin_succeeded pattern)
    - Plan-TDD RED/GREEN/REFACTOR with isHidden() for Qt widget visibility assertions
key_files:
  created:
    - .planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md
  modified:
    - musicstreamer/ui_qt/now_playing_panel.py
    - musicstreamer/ui_qt/main_window.py
    - musicstreamer/ui_qt/gbs_search_dialog.py
    - tests/test_now_playing_panel.py
    - tests/test_main_window_gbs.py
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
decisions:
  - "isHidden() used instead of isVisible() for widget visibility assertions in tests — isVisible() returns False for unrealized (not-yet-shown) Qt widgets even after setVisible(True); isHidden() checks the explicit flag (same pattern documented at test_now_playing_panel.py:1365)"
  - "test_submit_worker_calls_add_song_zero_token regex targets _GbsSubmitWorker class body first, then extracts run() — the file has multiple run() methods; the initial regex picked up _GbsSearchWorker.run() instead (Rule 1 bug found during RED, fixed before GREEN commit)"
  - "add_song_requested Signal uses Option A from 87B-RESEARCH Pattern 2 — panel emits signal, MainWindow connects to _open_gbs_search_dialog; panel never imports GBSSearchDialog directly (D-10 reuse)"
metrics:
  duration: "~25 min"
  completed_date: "2026-06-18"
  tasks_completed: 3
  files_changed: 7
---

# Phase 87B Plan 02: GBS Zero-Token Add — UI Wiring + Docs Amendment Summary

**One-liner:** Persistent "Add a song" QPushButton in the GBS now-playing cluster (token-count-independent visibility), wired via add_song_requested → _open_gbs_search_dialog → submission_completed → trigger_gbs_repoll(), with the worker routing through add_song_zero_token() and stale planning docs reframed per 87B-CONTEXT D-03/D-05/D-08.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 (RED) | Failing tests for button + visibility + repoll | e3d9e96b | tests/test_now_playing_panel.py (+227 lines) |
| 1 (GREEN) | "Add a song" button + trigger_gbs_repoll() in NowPlayingPanel | f3705a4a | musicstreamer/ui_qt/now_playing_panel.py, tests/test_now_playing_panel.py |
| 2 (RED) | Failing tests for dialog wiring + worker call-site | 4bc59443 | tests/test_main_window_gbs.py (+73 lines) |
| 2 (GREEN) | Wire dialog launch + re-poll in main_window + gbs_search_dialog | 7ecb64e2 | musicstreamer/ui_qt/main_window.py, musicstreamer/ui_qt/gbs_search_dialog.py, tests/test_main_window_gbs.py |
| 3 | Amend stale planning docs + create capture-on-use todo | (docs-only — gitignored; orchestrator commits) | .planning/REQUIREMENTS.md, .planning/ROADMAP.md, .planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md |

## What Was Built

### `musicstreamer/ui_qt/now_playing_panel.py`

Three additions:

- **`add_song_requested = Signal()`** — class-level signal declaration (mirrors `submission_completed` in `GBSSearchDialog`). Main window connects this to `_open_gbs_search_dialog` so the panel never imports the dialog directly (Option A / D-10 reuse pattern).
- **`_gbs_add_btn = QPushButton("Add a song", self)`** with tooltip `"Add a song to the GBS.FM queue"` — inserted after `_gbs_expiry_widget` and before `_gbs_vote_row` (load-bearing order per D-04). No stylesheet, no flat style, no width override (87B-UI-SPEC). Connected via `clicked.connect(self._on_add_song_clicked)` (QA-05 bound method).
- **`_refresh_gbs_visibility()`** extended: `self._gbs_add_btn.setVisible(should_show)` added alongside the vote-button loop, using the same `should_show = is_gbs and logged_in` predicate (D-05 — token-count-independent; no `fetch_user_tokens()` call).
- **`_on_add_song_clicked(self)`** — emits `add_song_requested`.
- **`trigger_gbs_repoll(self)`** — guarded on `station is GBS.FM` AND `not _gbs_poll_in_flight()`; resets `_gbs_poll_cursor = {}` (force full re-fetch so new song appears — Pitfall 5), then calls `_on_gbs_poll_tick()`. Mirrors `_on_gbs_relogin_succeeded` direct-call pattern (D-09).

### `musicstreamer/ui_qt/main_window.py`

Two additions:

- **`__init__` signal wiring**: `self.now_playing.add_song_requested.connect(self._open_gbs_search_dialog)` — QA-05 bound method, D-10 reuse.
- **`_open_gbs_search_dialog()`**: before `dlg.exec()`, adds `dlg.submission_completed.connect(self.now_playing.trigger_gbs_repoll)` — QA-05 bound method, D-09 post-add re-poll. Docstring updated: stale "submission_completed is not connected here" line removed.

### `musicstreamer/ui_qt/gbs_search_dialog.py`

One change:

- **`_GbsSubmitWorker.run()`**: `gbs_api.submit(...)` → `gbs_api.add_song_zero_token(...)` (GBS-TOKEN-03 / D-02). `GbsAuthExpiredError` propagates unchanged through the wrapper. Exception handling block is untouched.

### Planning Docs

- **`REQUIREMENTS.md`**: GBS-TOKEN-01 rewritten (persistent button, any token count — AMENDED D-05); GBS-TOKEN-04 rewritten (button persists, no hide-after-add, re-poll — AMENDED D-08); GBS-TOKEN-05 rewritten (provisional fixture now, capture-on-use deferred — RELAXED D-03). GBS-TOKEN-02/03 unchanged.
- **`ROADMAP.md`**: Line-45 one-liner drops "gated on tokens==0 AND queue empty" framing. Phase 87b Goal + SC#1/#3/#4/#5 rewritten per D-03/D-05/D-08 reframe. SC#2 unchanged.
- **`.planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md`**: Created with `resolves_phase: 87B`, condition (first observed tokens==0 add via capture hook), and 4-step action (confirm/adjust provisional contract, replace placeholder fixture, update MANIFEST, re-run tests if needed).

## Verification

```
.venv/bin/python -m pytest tests/test_now_playing_panel.py -k "add_song or repoll" \
  tests/test_main_window_gbs.py -k "repoll or add_song or submission" \
  tests/test_gbs_zero_token_drift_guard.py -x
# 15 passed, 0 failed
```

Task 3 doc verification:
```
grep -q "AMENDED per 87B-CONTEXT D-05" .planning/REQUIREMENTS.md
grep -q "AMENDED per 87B-CONTEXT D-08" .planning/REQUIREMENTS.md
grep -q "RELAXED per 87B-CONTEXT D-03" .planning/REQUIREMENTS.md
grep -q "resolves_phase: 87B" .planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md
# DOCS_OK
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] isVisible() returned False for unrealized Qt widgets in visibility tests**

- **Found during:** Task 1 GREEN phase — `test_add_song_visibility_gbs_logged_in` failed even after button implementation
- **Issue:** Qt's `isVisible()` returns `False` for widgets whose parent chain has never been shown (the offscreen test platform), even when `setVisible(True)` was explicitly called. The plan's behavior block said "visible is True" without specifying the API.
- **Fix:** Replaced `isVisible()` with `isHidden()` in visibility tests — `isHidden()` checks the explicit visibility flag set by `setVisible()`, matching the same pitfall documented at `test_now_playing_panel.py:1365` for the `_gbs_playlist_widget` tests.
- **Files modified:** `tests/test_now_playing_panel.py`
- **Commit:** f3705a4a (same task commit)

**2. [Rule 1 - Bug] test_submit_worker_calls_add_song_zero_token regex matched wrong run() method**

- **Found during:** Task 2 GREEN phase — the source-grep test picked `_GbsSearchWorker.run()` instead of `_GbsSubmitWorker.run()` because `gbs_search_dialog.py` has multiple worker classes each with a `run()` method
- **Fix:** Updated the regex to find the `_GbsSubmitWorker` class body first, then extract `run()` from within that class body
- **Files modified:** `tests/test_main_window_gbs.py`
- **Commit:** 7ecb64e2 (same task commit)

## Known Stubs

None — the provisional fixture from Plan 01 is intentional and documented with `resolves_phase: 87B` in both the MANIFEST.md and the new capture-on-use todo.

## Threat Flags

No new threat surface beyond the plan's registered threats. The call-site change in `_GbsSubmitWorker.run()` routes through `add_song_zero_token()` which adds only the no-PII capture hook (T-87B-01, mitigated and enforced by `test_capture_hook_no_pii` in Plan 01). No new logging, no new network endpoints, no new auth paths introduced by this plan.

## Self-Check: PASSED

Files exist:
- [FOUND] musicstreamer/ui_qt/now_playing_panel.py — contains "Add a song", add_song_requested, trigger_gbs_repoll
- [FOUND] musicstreamer/ui_qt/main_window.py — contains submission_completed.connect, add_song_requested.connect
- [FOUND] musicstreamer/ui_qt/gbs_search_dialog.py — contains add_song_zero_token (not bare submit in _GbsSubmitWorker.run)
- [FOUND] .planning/REQUIREMENTS.md — GBS-TOKEN-01/04/05 amended
- [FOUND] .planning/ROADMAP.md — SC#1/#3/#4/#5 amended
- [FOUND] .planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md — resolves_phase: 87B

Commits exist:
- [FOUND] e3d9e96b — test(87B-02): RED — add_song visibility, label, repoll tests
- [FOUND] f3705a4a — feat(87B-02): add 'Add a song' button + trigger_gbs_repoll()
- [FOUND] 4bc59443 — test(87B-02): RED — dialog wiring + worker call-site tests
- [FOUND] 7ecb64e2 — feat(87B-02): wire dialog launch + re-poll; route worker through add_song_zero_token()
