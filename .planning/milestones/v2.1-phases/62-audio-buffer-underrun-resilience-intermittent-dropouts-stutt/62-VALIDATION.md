---
phase: 62
slug: audio-buffer-underrun-resilience-intermittent-dropouts-stutt
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-07
---

# Phase 62 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source of truth for test layout: `62-RESEARCH.md` §"Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=9 + pytest-qt >=4 (pyproject.toml lines 28-29) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (line 50) |
| **Quick run command** | `pytest tests/test_player_underrun_tracker.py tests/test_player_underrun.py tests/test_main_window_underrun.py -x -q` |
| **Full suite command** | `pytest -x -q` |
| **Estimated runtime** | ~1-2s quick / ~current full-suite baseline |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_player_underrun_tracker.py tests/test_player_underrun.py tests/test_main_window_underrun.py -x -q`
- **After every plan wave:** `pytest -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~2 seconds quick / full suite as project baseline

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 62-00-01 | 00 | 0 | BUG-09 | T-62-01 | Tracker stubs encode contract; tests RED | unit | `pytest tests/test_player_underrun_tracker.py -x -q` | ❌ W0 | ⬜ pending |
| 62-00-02 | 00 | 0 | BUG-09 | T-62-01 | Player-integration stubs encode bus + close-path contract; tests RED | integration | `pytest tests/test_player_underrun.py -x -q` | ❌ W0 | ⬜ pending |
| 62-00-03 | 00 | 0 | BUG-09 | T-62-01 | MainWindow cooldown stubs encode 10s gate; tests RED | integration | `pytest tests/test_main_window_underrun.py -x -q` | ❌ W0 | ⬜ pending |
| 62-01-01 | 01 | 1 | BUG-09 | T-62-01 | `_BufferUnderrunTracker.on_buffering(percent<100, armed)` opens cycle (D-01, D-04) | unit | `pytest tests/test_player_underrun_tracker.py::test_armed_drop_opens_cycle -x` | ❌ W0 | ⬜ pending |
| 62-01-02 | 01 | 1 | BUG-09 | T-62-01 | Initial fill `<100` while unarmed does NOT open cycle (D-04) | unit | `pytest tests/test_player_underrun_tracker.py::test_unarmed_initial_fill_does_not_open_cycle -x` | ❌ W0 | ⬜ pending |
| 62-01-03 | 01 | 1 | BUG-09 | T-62-01 | First `100` per URL flips arm True (D-04 / Phase 47.1 D-14 mirror) | unit | `pytest tests/test_player_underrun_tracker.py::test_first_100_arms_tracker -x` | ❌ W0 | ⬜ pending |
| 62-01-04 | 01 | 1 | BUG-09 | T-62-01 | Natural close at `100` returns `_CycleClose(outcome='recovered')` w/ duration_ms + min_percent (D-02) | unit | `pytest tests/test_player_underrun_tracker.py::test_armed_drop_then_recover_returns_close_record -x` | ❌ W0 | ⬜ pending |
| 62-01-05 | 01 | 1 | BUG-09 | T-62-01 | Force-close returns record with `outcome ∈ {failover, stop, pause, shutdown}` (D-03) | unit | `pytest tests/test_player_underrun_tracker.py::test_force_close_returns_record_with_outcome -x` | ❌ W0 | ⬜ pending |
| 62-01-06 | 01 | 1 | BUG-09 | T-62-01 | `bind_url(...)` resets arm + open cycle state (D-04 / Pitfall 3) | unit | `pytest tests/test_player_underrun_tracker.py::test_bind_url_resets_state -x` | ❌ W0 | ⬜ pending |
| 62-01-07 | 01 | 1 | BUG-09 | T-62-01 | `note_error_in_cycle()` flips `cause_hint` to `'network'` (D-02 Discretion) | unit | `pytest tests/test_player_underrun_tracker.py::test_cause_hint_network_after_error -x` | ❌ W0 | ⬜ pending |
| 62-02-01 | 02 | 1 | BUG-09 | T-62-01 | `_on_gst_buffering` emits `_underrun_cycle_opened` on `<100` transition (Pitfall 2 — queued Signal) | integration | `pytest tests/test_player_underrun.py::test_buffering_drop_emits_cycle_opened -x` | ❌ W0 | ⬜ pending |
| 62-02-02 | 02 | 1 | BUG-09 | T-62-01 | `_on_gst_buffering` emits `_underrun_cycle_closed` on natural recover w/ full record payload | integration | `pytest tests/test_player_underrun.py::test_buffering_recover_emits_cycle_closed -x` | ❌ W0 | ⬜ pending |
| 62-02-03 | 02 | 1 | BUG-09 | T-62-01 | `_try_next_stream` force-closes open cycle with `outcome=failover` BEFORE binding new URL | integration | `pytest tests/test_player_underrun.py::test_try_next_stream_force_closes_with_failover_outcome -x` | ❌ W0 | ⬜ pending |
| 62-02-04 | 02 | 1 | BUG-09 | T-62-01 | `pause()` force-closes open cycle with `outcome=pause` | integration | `pytest tests/test_player_underrun.py::test_pause_force_closes_with_pause_outcome -x` | ❌ W0 | ⬜ pending |
| 62-02-05 | 02 | 1 | BUG-09 | T-62-01 | `stop()` force-closes open cycle with `outcome=stop` | integration | `pytest tests/test_player_underrun.py::test_stop_force_closes_with_stop_outcome -x` | ❌ W0 | ⬜ pending |
| 62-02-06 | 02 | 1 | BUG-09 | T-62-01 | Cycle close writes structured INFO log line w/ all 9 fields (D-02) | integration | `pytest tests/test_player_underrun.py::test_cycle_close_writes_structured_log -x` (uses `caplog`) | ❌ W0 | ⬜ pending |
| 62-02-07 | 02 | 1 | BUG-09 | T-62-01 | Dwell timer fires `underrun_recovery_started` after 1500ms (D-07) | integration | `pytest tests/test_player_underrun.py::test_dwell_timer_fires_after_threshold -x` | ❌ W0 | ⬜ pending |
| 62-02-08 | 02 | 1 | BUG-09 | T-62-01 | Sub-1500ms recovery cancels timer; toast Signal NOT emitted | integration | `pytest tests/test_player_underrun.py::test_sub_dwell_recovery_silent -x` | ❌ W0 | ⬜ pending |
| 62-03-01 | 03 | 2 | BUG-09 | T-62-01 | `MainWindow._on_underrun_recovery_started` shows toast on first call (D-06) | integration | `pytest tests/test_main_window_underrun.py::test_first_call_shows_toast -x` | ❌ W0 | ⬜ pending |
| 62-03-02 | 03 | 2 | BUG-09 | T-62-01 | Cooldown suppresses 2nd toast within 10s (D-08, monkeypatched `time.monotonic`) | integration | `pytest tests/test_main_window_underrun.py::test_second_call_within_cooldown_suppressed -x` | ❌ W0 | ⬜ pending |
| 62-03-03 | 03 | 2 | BUG-09 | T-62-01 | Toast allowed after cooldown elapses | integration | `pytest tests/test_main_window_underrun.py::test_toast_after_cooldown_allowed -x` | ❌ W0 | ⬜ pending |
| 62-03-04 | 03 | 2 | BUG-09 | — | `closeEvent` triggers `Player.shutdown_underrun_tracker()` for `outcome=shutdown` | integration | `pytest tests/test_main_window_underrun.py::test_close_event_force_closes_open_cycle -x` | ❌ W0 | ⬜ pending |
| 62-03-05 | 03 | 2 | BUG-09 | — | `__main__.py` adds `logging.getLogger("musicstreamer.player").setLevel(logging.INFO)` | integration | `grep -c 'getLogger("musicstreamer.player").setLevel(logging.INFO)' musicstreamer/__main__.py` returns ≥1 | ❌ W0 | ⬜ pending |
| 62-99-01 | n/a | n/a | BUG-09 | — | D-09 invariant: `BUFFER_DURATION_S == 10` and `BUFFER_SIZE_BYTES == 10*1024*1024` (existing) | unit | `pytest tests/test_player_buffer.py::test_buffer_duration_constant tests/test_player_buffer.py::test_buffer_size_constant -x` | ✅ exists | ⬜ baseline |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Note:** Task IDs above are the planner's expected layout. The planner is free to reshape (e.g., merge cooldown + closeEvent into one task) — the per-test mapping holds.

---

## Wave 0 Requirements

- [ ] `tests/test_player_underrun_tracker.py` — pure unit tests on `_BufferUnderrunTracker` (~7 tests, no Qt fixture). Mirrors `tests/test_stream_ordering.py` shape (pure-logic).
- [ ] `tests/test_player_underrun.py` — Player-integration tests. Reuses `make_player(qtbot)` harness from `tests/test_player_buffering.py:8-18`. Feeds `_fake_buffering_msg(percent)` to exercise Pitfall 1 path. ~8 tests.
- [ ] `tests/test_main_window_underrun.py` — MainWindow cooldown gate. ~3 tests. Uses `time.monotonic` monkeypatch for deterministic cooldown. May land as a section in `tests/test_main_window.py` if the file stays small — planner's call.
- [ ] No framework install needed — pytest + pytest-qt already pinned in pyproject.toml.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `Buffering…` toast appears under live repro (SC #2) | BUG-09 | Real GStreamer + real network needed to reproduce a genuine buffer underrun; throttled-network harness is deferred (per CONTEXT.md `<deferred>`). | Play any station for ≥10 minutes on a normal home network. If a brief stutter audibly occurs and lasts >1.5s, confirm a single `Buffering…` toast appears at the bottom-centre of the window and no second toast follows within 10s. Confirm structured INFO log line is written to stderr at cycle close. |
| Force-close with `outcome=shutdown` writes log on app exit | BUG-09 | Process-lifecycle hook only fires under real shutdown; `caplog` doesn't capture closeEvent path easily. | Open a station, mid-playback close the window. Confirm the most recent INFO log line in stderr has `outcome=shutdown` (or `outcome=recovered` if the window was healthy at close). |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
