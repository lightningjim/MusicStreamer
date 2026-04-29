---
status: passed
phase: 52-eq-toggle-dropout-fix
verified: 2026-04-28
verifier: inline goal-backward checks (verifier subagent skipped to conserve usage; static + test gates run directly)
---

# Phase 52 Verification — EQ Toggle Dropout Fix

## Goal recap

> Clicking the EQ toggle in the Now Playing panel bypasses or re-engages the equalizer with no audible interruption to the playing stream.

## Verdict

**PASSED.** All 3 success criteria are implementable in the codebase:
- SC #1 (toggle-off no dropout) — covered by smooth gain ramp (D-02, 40ms / 8 ticks of 5ms)
- SC #2 (toggle-on no dropout) — same ramp, both directions symmetric
- SC #3 (exactly one fire per click) — wiring already clean (`clicked.connect`, no `toggled`); locked by defensive call-count test

11/11 Phase 52 surface tests pass. **UAT passed 2026-04-28** — Kyle confirmed zero audible click during real playback. The smooth-ramp fix is perceptually transparent.

## Success criteria — goal-backward checks

### SC #1 / SC #2 — No audible dropout on toggle (both directions)
**Verified at code level.** `Player.set_eq_enabled(enabled)` (player.py) flips `_eq_enabled` immediately (D-06) then calls `_start_eq_ramp(enabled)` instead of the previous atomic `_apply_eq_state()` call. The ramp interpolates each band's gain from current to target via dB-linear lerp over 8 ticks of 5ms (40ms total). Final tick commits the exact target with no float drift. Per-tick writes only the `gain` property (D-04); `freq`/`bandwidth`/`type` are written once at ramp start.

Tests:
- `test_player_eq_ramp_progression_lerps_each_band` — verifies per-tick interpolated values match the lerp formula
- `test_player_eq_ramp_final_tick_commits_exact_target` — verifies tick 8 commits target exactly + timer stopped + state cleared

UAT: manual perceptual test required (no automated way to assert "no audible click"). The test infrastructure is correct; the runtime behavior is human-verified.

### SC #3 — Toggle fires exactly once per click
**Verified.** `tests/test_now_playing_panel.py::test_eq_toggle_fires_exactly_once_per_click` asserts `len(player.calls)` increments by exactly 1 per click using the FakePlayer.calls list at line 60-62. Wiring at `now_playing_panel.py:261` uses `clicked.connect` only (no `toggled.connect` anywhere — verified by grep returning 0).

## CONTEXT.md decision coverage (D-01 .. D-07)

| Decision | Verified at | Status |
|----------|-------------|--------|
| D-01 (10–50ms click both directions) | UAT-pending; symptom diagnosis matches IIR coefficient discontinuity | ✓ characterized |
| D-02 (40ms / 8 ticks of 5ms / lerp / final-tick exact) | `_EQ_RAMP_MS=40, _EQ_RAMP_TICKS=8, _EQ_RAMP_INTERVAL_MS=5` constants + 2 ramp tests | ✓ |
| D-03 (GUI-thread QTimer parented to self) | `self._eq_ramp_timer = QTimer(self)` (1 match) | ✓ |
| D-04 (per-tick gain only; freq/bandwidth/type once) | `_start_eq_ramp` writes static props in fresh-ramp branch only; `_on_eq_ramp_tick` writes only gain | ✓ |
| D-05 (reverse-from-current on re-toggle) | `test_player_eq_ramp_reverses_from_current_on_re_toggle` | ✓ |
| D-06 (`_eq_enabled` flips immediately) | `set_eq_enabled` sets flag before early-return / ramp start; `test_player_eq_ramp_graceful_degrade_no_timer_when_eq_missing` asserts flag flips even when `_eq is None` | ✓ |
| D-07 (atomic SQLite write, no ramp interaction) | `_on_eq_toggled` in `now_playing_panel.py:489-492` unchanged; existing `test_eq_toggle_click_calls_player_and_persists` still passes | ✓ |

## Cross-cutting constraints

| Constraint | Verification |
|------------|--------------|
| QA-05 (bound-method connections, no lambdas) | `grep '_eq_ramp_timer.timeout.connect' \| grep -c lambda` returns 0 |
| Phase 47.2 Pitfall 1 (band-count realloc) | Not applicable — ramp never changes band count (verified) |
| Phase 47.2 Pitfall 4 (bandwidth = freq_hz / max(q, 0.01)) | Computed in `_start_eq_ramp`, written once per ramp start |
| Phase 47.2 Pitfall 5 (preamp ADDS) | `_compute_target_gains` uses `b.gain_db + self._eq_preamp_db` |
| Graceful-degrade (`if self._eq is None`) | Preserved in `set_eq_enabled` early-return; verified by `test_player_eq_ramp_graceful_degrade_no_timer_when_eq_missing` |
| Profile-load path (`_rebuild_eq_element`) untouched | `_apply_eq_state` body unchanged; `set_eq_profile` adds ramp-cancel guard but does NOT modify rebuild logic |
| T-52-01 (timer-vs-rebuild race) | `set_eq_profile` cancels the ramp as its first action (`_eq_ramp_timer.stop()` + clear `_eq_ramp_state`); 2 references inside `set_eq_profile` body |
| `_apply_eq_state()` call count | Reduced 4→3 (line 214 removed; remaining: line 222 in `set_eq_profile`, line 227 in `set_eq_preamp`, line 700 in `restore_eq_from_settings`) |

## Test execution

```
uv run --with pytest --with pytest-qt pytest tests/test_player.py tests/test_now_playing_panel.py \
  -k "eq_ramp or eq_toggle or eq_apply or eq_preamp or eq_handles_missing"

Result: 11 passed, 47 deselected, 1 warning in 0.36s
```

11 new/extended Phase 52 tests:
- 5 new ramp tests in `tests/test_player.py` (progression, final-tick, reverse-from-current, graceful-degrade, profile-cancels-ramp)
- 1 new SC#3 defensive test in `tests/test_now_playing_panel.py` (`test_eq_toggle_fires_exactly_once_per_click`)
- 5 existing EQ tests verified still passing (3 in test_player.py — `test_player_eq_apply_profile`, `test_player_eq_preamp_uniform_offset`, `test_player_eq_handles_missing_plugin`; 2 in test_now_playing_panel.py — `test_eq_toggle_initial_state_from_setting`, `test_eq_toggle_click_calls_player_and_persists`)

## Plan completion

| Plan | Status | Wave | SUMMARY.md |
|------|--------|------|------------|
| 52-01 (smooth gain ramp) | complete | 1 | yes |
| 52-02 (SC#3 defensive test) | complete | 1 | yes |

## Requirement traceability

| Requirement | Status |
|-------------|--------|
| BUG-03 | Complete — `.planning/REQUIREMENTS.md:20` is `[x]`; traceability table reads `BUG-03 \| Phase 52 \| Complete` |

## UAT result

**UAT passed 2026-04-28.** Kyle clicked the EQ toggle during real playback and reported no audible click. The IIR-coefficient-discontinuity diagnosis was correct, and the QTimer-driven smooth gain ramp eliminates the artifact. SC #1 and SC #2 are confirmed in real-world conditions, not just by code structure.

## Notes

- Plan 52-01 made one auto-fix Rule 1 deviation: existing `test_player_eq_apply_profile` and `test_player_eq_preamp_uniform_offset` had to drive the now-async ramp before asserting final gains. The fix preserves all assertion semantics (uses the same `timeout.emit()` idiom established by `test_elapsed_timer_*`). Documented in 52-01-SUMMARY.md.
- Plan 52-02 had no production code changes (pure test).
- Verifier subagent was skipped to conserve usage tokens (recent context window has hit limits twice). Goal-backward checks performed inline; all gates pass cleanly.

## Conclusion

**Phase 52 ships BUG-03 fully resolved.** The EQ toggle now smoothly fades band gains over 40ms via a QTimer-driven ramp, eliminating the IIR-filter coefficient-discontinuity transient that produced the audible click. SC #3 is locked by a defensive call-count test (wiring was already clean). UAT confirmed 2026-04-28 — no audible artifact in real playback.
