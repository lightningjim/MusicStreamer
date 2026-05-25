---
phase: 84
plan: 02
subsystem: gstreamer/playbin3
tags: [gstreamer, playbin3, buffer-tuning, qt-signal, green-implementation, bug-09, commit-b]
requires:
  - 84-01 (Wave 0 RED test surface + Signal parity in tests/_fake_player.py)
provides:
  - "musicstreamer.constants.BUFFER_DURATION_S = 30 (was 10)"
  - "musicstreamer.constants.BUFFER_SIZE_BYTES = 20 * 1024 * 1024 (was 10MB)"
  - "musicstreamer.player.Player.buffer_duration_changed = Signal(int) (class-level, D-12)"
  - "musicstreamer.player.Player._maybe_grow_buffer_duration (D-11 staging)"
  - "musicstreamer.player.Player._apply_pending_buffer_duration_to_pipeline (D-11 apply)"
  - "musicstreamer.player.Player._reset_buffer_duration_to_baseline (D-11 per-URL reset)"
affects:
  - "Wave 1 Plan 84-03 (UI wire) reads buffer_duration_changed Signal"
  - "Phase 78 underrun-count signal pattern (mirror — adjacent at player.py:297/306)"
  - "Phase 83 gapless preroll handoff (new apply/reset insertion at line ~1486)"
tech-stack:
  added: []
  patterns:
    - "Stage-and-apply state machine (D-11 fallback for playbin3 mid-session-write no-ops)"
    - "Class-level PySide6 Signal + main-thread emission with DirectConnection receiver"
    - "Per-URL reset with Pitfall 3 early-return (no spurious Signal at baseline)"
key-files:
  created: []
  modified:
    - "musicstreamer/constants.py (D-10 literal bumps + comment freshening; +8/-3 lines)"
    - "musicstreamer/player.py (Signal + 3 fields + 3 helpers + 5 callsite insertions + drive-by comment; +130/-4 lines)"
decisions:
  - "D-10 static constant bump applied via existing player.py:327 construction-time set_property call (no new wiring; uridecodebin3.new_source_handler reads the bumped literal at first URI bind per 84-RESEARCH §D-11)"
  - "D-11 stage-and-apply implemented at BOTH URI-bind sites (_try_next_stream AND _on_preroll_about_to_finish) — Pitfall 2 honored: missing the gapless preroll site would silently regress adaptive growth for SomaFM users"
  - "D-11 per-URL reset uses pending=BUFFER_DURATION_S (not None) so the baseline value is pushed to playbin3 at the next bind, flushing any prior 60s/120s value applied to a previous URL session"
  - "Inline schedule literals {1:60, 2:120} kept in _maybe_grow_buffer_duration (NOT module-level constants) per RESEARCH Alternatives and Phase 78 in-Player convention"
  - "Drive-by: freshened comment block at player.py:332-341 to explain GST_PLAY_FLAG_BUFFERING propagation semantics (URI-bind time, NOT mid-session); flags|0x100 literal at line 342 preserved byte-identical"
metrics:
  duration: "~30 min execution wall-clock"
  completed: "2026-05-24T22:48:00Z"
  tasks_completed: "2/2"
  files_modified: 2
---

# Phase 84 Plan 02: D-10/D-11/D-12 Player Buffer-Duration State Machine Summary

D-10 static bump (30s / 20MB) + D-11/D-12 adaptive growth state machine (30→60→120s with per-URL reset) implemented on Player using the playbin3 mid-session-write FALLBACK shape (stage at cycle_close, apply at next URI bind).

## What Shipped

### Task 1 — D-10 constants bump (commit `c003662`)

`musicstreamer/constants.py` lines 54-62:

- `BUFFER_DURATION_S = 30` (was `10`)
- `BUFFER_SIZE_BYTES = 20 * 1024 * 1024` (was `10 * 1024 * 1024`)
- Misleading `# 5 MB` inline comment replaced with `# 20 MB (was 10 MB despite the wrong inline comment)`
- Cluster header comment freshened with Phase 84 / D-10 citation + 84-CONTEXT.md `<data-summary>` rationale (3× headroom over harvest-week 7.4s worst-case underrun)

The existing construction-time `set_property` calls at `musicstreamer/player.py:327-328` pick up the bumped literals at first URI bind (no new wiring needed — uridecodebin3.new_source_handler reads the playbin3 struct field per 84-RESEARCH §D-11).

### Task 2 — D-11/D-12 state machine on Player (commit `29d0dea`)

`musicstreamer/player.py` — five coordinated edits in one commit:

| Edit | Location (post-edit line) | What |
|------|--------------------------|------|
| Signal declaration | `player.py:306` | `buffer_duration_changed = Signal(int)` immediately after `underrun_count_changed = Signal(int)` (Phase 78 mirror) |
| Init fields | `player.py:523-525` | `_growth_step: int = 0` / `_current_buffer_duration_s: int = BUFFER_DURATION_S` / `_pending_buffer_duration_s: int \| None = None` |
| `_maybe_grow_buffer_duration` method | `player.py:1165` | 30→60→120 schedule with cap; stages pending + mirrors current + emits Signal |
| `_apply_pending_buffer_duration_to_pipeline` method | `player.py:1203` | Writes `set_property("buffer-duration", _pending * Gst.SECOND)` then clears pending |
| `_reset_buffer_duration_to_baseline` method | `player.py:1230` | Per-URL reset; Pitfall 3 early-return at baseline (no spurious Signal) |
| Cycle-close hook | `player.py:1163` | `self._maybe_grow_buffer_duration()` at end of `_on_underrun_cycle_closed` |
| `_try_next_stream` apply | `player.py:1280-1282` | `_apply_pending` + `_reset_baseline` AFTER `_last_buffer_percent = -1` and BEFORE `force_close("failover")` |
| `_on_preroll_about_to_finish` apply | `player.py:1486-1488` | `_apply_pending` + `_reset_baseline` IMMEDIATELY BEFORE `set_property("uri", aa_normalize_stream_url(stream.url))` |

Drive-by: freshened comment block at `player.py:332-341` explaining how GST_PLAY_FLAG_BUFFERING (0x100) makes the construction-time `set_property` values propagate to queue2 at URI-bind time (NOT mid-session).

## Test Results

```
tests/test_player_buffer.py ............................ 5 passed
tests/test_player_buffer_growth.py ................... 9 passed   (RED → GREEN this plan)
tests/test_playbin3_property_hygiene.py .............. 3 passed   (hygiene gate stays GREEN)
tests/test_player_underrun_count.py .................. 7 passed   (Phase 78 regression-clean)
tests/test_fake_player_signal_parity.py .............. 2 passed   (Wave 0 parity edit covers new Signal)
                                                       --
                                                       27 passed in 0.64s
```

Phase 78 broader regression sweep (`test_main_window_underrun.py` + `test_buffer_events_log.py`): **12 passed**, 1 failure is Plan 84-03's UI scope (`test_buffer_duration_changed_updates_stats_row` — depends on `NowPlayingPanel._buffer_duration_label` to be added by Plan 84-03 in the same wave, intentionally RED here).

## Invariant Verification

- `grep -nE "flags\s*\|\s*0x100" musicstreamer/player.py` → line 342 (Phase 16 invariant; hygiene gate locks it)
- `grep -nE "set_property\(['\"]buffer_duration['\"]" musicstreamer/player.py` → **0 lines** (underscore form forbidden — none introduced)
- `grep -cE "self\._apply_pending_buffer_duration_to_pipeline\(\)" musicstreamer/player.py` → **2** (both URI-bind sites present; Pitfall 2 honored)
- `grep -cE "self\._reset_buffer_duration_to_baseline\(\)" musicstreamer/player.py` → **2** (paired with each apply site)
- `git diff --stat musicstreamer/__main__.py` → empty (Pitfall 5 enforced — basicConfig WARNING + per-logger INFO preserved byte-identical)
- `git status tests/_fake_player.py` → clean (Wave 0 parity edit unchanged this plan)
- `git diff --diff-filter=D --name-only HEAD~2 HEAD` → empty (no file deletions)

## Deviations from Plan

None — plan executed exactly as written. The optional drive-by comment freshening at `player.py:320-323` was applied per RESEARCH Discretion guidance.

## Threat Flags

None new. The plan's existing `<threat_model>` (T-84-03 through T-84-07) is fully realized by the implementation:

- T-84-03 (DoS via uncapped growth): mitigated by `_maybe_grow_buffer_duration`'s `if self._growth_step >= 2: return` at line ~1183 (cap at 120s) and per-URL reset in both apply sites.
- T-84-04 (property typo silently no-op'd): all property strings are dash-form; hygiene gate `tests/test_playbin3_property_hygiene.py` regression-locks the allowlist.
- T-84-05 (log line drift): Phase 62 `_log.info("buffer_underrun ...")` call at `player.py:1122` left byte-identical.
- T-84-06 (Signal info disclosure): Signal payload is a small int {30, 60, 120}; no PII / network identifier surface.
- T-84-07 (mid-session set_property crash): no mid-session writes — the stage-and-apply pattern ensures writes only land at URI-bind time, before uridecodebin3 negotiation.

## Known Stubs

None. The Player half of the BUG-09 SC #3 surface is complete; Plan 84-03 (UI wire) is the companion in this wave that surfaces `buffer_duration_changed` on the stats-for-nerds row.

## Continuation Notes for Plan 84-03 (UI wire)

Post-edit line numbers Plan 84-03's MainWindow + NowPlayingPanel wires will reference:

- Player Signal: `musicstreamer/player.py:306` (`buffer_duration_changed = Signal(int)`)
- Connect pattern mirror: `underrun_count_changed.connect(...)` wiring in `musicstreamer/main_window.py` (Phase 78 precedent — bound method per QA-05, DirectConnection per qt-glib-bus-threading Pitfall 2)
- Initial baseline value: `Player._current_buffer_duration_s` reads `BUFFER_DURATION_S` (= 30) at `__init__` — set the stats row to "30s" before any Signal arrives so the panel does not blank on construction

## Self-Check: PASSED

- File exists: `.planning/phases/84-bug-09-commit-b-buffer-tuning-behavior-fix-reframed-from-str/84-02-SUMMARY.md` — FOUND
- Commit `c003662` (Task 1) — FOUND in `git log`
- Commit `29d0dea` (Task 2) — FOUND in `git log`
- 27/27 targeted tests GREEN — verified above
- Hygiene gate (3 tests) STILL GREEN
- No banned underscore property spellings introduced
- `flags | 0x100` literal preserved at player.py:342
- `__main__.py` untouched (0 lines changed)
- `tests/_fake_player.py` untouched in this plan
