---
phase: 84
plan: 01
subsystem: gstreamer/player + ui_qt stats-for-nerds (test surface only)
tags: [gstreamer, playbin3, buffer-tuning, qt-signal, tdd-red, wave-0]
requires:
  - "Phase 78 Commit A: Player.underrun_count_changed Signal + cycle counter (mirror pattern)"
  - "Phase 80: tokenize-blanked source-grep gate (test_db_connect_is_sole_connection_factory.py template)"
  - "Phase 47.1: _MutedLabel + _build_stats_widget extensibility"
  - "Phase 83: _on_preroll_about_to_finish slot with _preroll_in_flight + _preroll_seq guards"
provides:
  - "RED test contracts driving Wave 1 (Plan 84-02): Player Signal name + arity, 3 instance fields, 3 helper methods, 2 URI-bind apply sites"
  - "RED test contracts driving Wave 1 (Plan 84-03): NowPlayingPanel.set_buffer_duration slot, _buffer_duration_label widget, third QFormLayout row labeled 'Buf duration', MainWindow DirectConnection wire"
  - "GREEN-by-coincidence source-grep gate: _ALLOWED_PIPELINE_PROPERTIES (8 names), _BANNED_SPELLINGS (5 names), flags|0x100 regression lock"
  - "INFRA-01 FakePlayer parity edit: buffer_duration_changed = Signal(int) (FakePlayer leads Player in Wave 0)"
affects:
  - "tests/_fake_player.py (parity edit)"
  - "tests/test_player_buffer.py (constants assertion bump)"
  - "tests/test_player_buffer_growth.py (NEW)"
  - "tests/test_playbin3_property_hygiene.py (NEW)"
  - "tests/test_now_playing_panel.py (3 new tests)"
  - "tests/test_main_window_underrun.py (1 new test)"
tech_stack:
  added: []  # zero new deps; pytest + pytest-qt + tokenize stdlib were already present
  patterns:
    - "tokenize-blanked source-grep gate (Phase 80 precedent → Phase 84 mock-blind-spot guardrail)"
    - "Per-file make_player + _make_record helper duplication (S-6 — NO conftest extraction)"
    - "Hard-coded _GST_SECOND = 1_000_000_000 (D-26 / QA-02 — avoid import gi)"
    - "Bound-method Signal.connect to received.append (QA-05 / Pattern S-1 — no lambdas)"
    - "Two-phase stage-and-apply growth lifecycle (cycle_close stages → URI-bind applies)"
key_files:
  created:
    - "tests/test_player_buffer_growth.py (356 lines, 9 tests)"
    - "tests/test_playbin3_property_hygiene.py (259 lines, 3 tests)"
  modified:
    - "tests/_fake_player.py (+1 Signal mirror + docstring count bump)"
    - "tests/test_player_buffer.py (literal D-10 bump 10→30, 10MB→20MB)"
    - "tests/test_now_playing_panel.py (+70 lines, 3 new tests after existing Phase 78 row tests)"
    - "tests/test_main_window_underrun.py (+23 lines, 1 new wire test after existing Phase 78 wire test)"
decisions:
  - "Honored D-11 fallback (per RESEARCH §D-11 Resolution): URI-bind apply ordering tested directly via _pipeline.set_property.call_args_list index comparison — buffer-duration write MUST precede uri write so uridecodebin3.new_source_handler reads the staged value."
  - "Pitfall 2 catcher: dedicated test for _on_preroll_about_to_finish apply-site (the SomaFM gapless preroll handoff path that fires hourly — easy to forget). Setup mirrors tests/test_player.py:1136-1144."
  - "Pitfall 3 catcher: dedicated test that reset-when-already-at-baseline does NOT emit a spurious Signal (would cause stats row to twitch at every URL bind)."
  - "FakePlayer leads Player by one Signal in Wave 0: buffer_duration_changed is added to FakePlayer NOW (parity test allows FakePlayer to be a superset of Player Signals); Player itself gains the Signal in Wave 1."
  - "Source-grep gate split into 3 separate test functions (allowlist / banned / flags) rather than one combined test — clean failure attribution per Pattern S-8."
metrics:
  duration_minutes: 10
  completed: "2026-05-24T22:36:10Z"
---

# Phase 84 Plan 01: Wave 0 RED Test Surface — BUG-09 Commit B (buffer-tuning behavior fix, reframed) Summary

Lay down 4 task-atomic commits creating the Wave 0 RED test surface for Phase 84 / BUG-09 Commit B: D-10 constants assertion bump (30s / 20MB), D-11 adaptive buffer-duration growth state machine with URI-bind apply ordering, D-12 always-visible Buf-duration stats-for-nerds row plus Signal wire, INFRA-01 FakePlayer parity mirror, and the Pattern 4 source-grep gate banning playbin 1.x property spellings + regression-locking the flags|0x100 bit.

## Wave 0 Test State

| Bucket                                                                 | Count | State          | Notes                                                                |
| ---------------------------------------------------------------------- | ----- | -------------- | -------------------------------------------------------------------- |
| tests/test_player_buffer.py constants assertions (D-10)                | 2     | RED (expected) | RED until Wave 1 Plan 84-02 bumps constants.py:55-56                 |
| tests/test_player_buffer_growth.py D-11 state-machine + apply ordering | 9     | RED (expected) | All collect cleanly; AttributeError / AssertionError                 |
| tests/test_now_playing_panel.py D-12 stats row + slot                  | 4 (3 funcs, 1 parametrized × 2) | RED (expected) | AttributeError on _buffer_duration_label / set_buffer_duration       |
| tests/test_main_window_underrun.py D-12 Signal wire                    | 1     | RED (expected) | AttributeError on _buffer_duration_label after FakePlayer emit       |
| tests/test_playbin3_property_hygiene.py source-grep gate (3 funcs)     | 3     | GREEN (by coincidence — locks structural invariants forever) | Allowlist matches today; no banned spellings; flags\|0x100 at line 325 |
| tests/test_fake_player_signal_parity.py INFRA-01 drift-guard           | 2     | GREEN (parity test allows FakePlayer superset of Player Signals) | FakePlayer leads Player by one Signal in Wave 0                      |

**Total RED count driving Wave 1 implementation: 16** (plan threshold was ≥13).
**Total GREEN-by-coincidence + parity tests: 5.**

## Wave 1 Contracts Now Locked

### Player (musicstreamer/player.py — Plan 84-02)

- `buffer_duration_changed = Signal(int)` at class scope (test_buffer_duration_changed_signal_at_class_scope pins existence + Signal type)
- `_growth_step: int = 0` instance field
- `_current_buffer_duration_s: int = BUFFER_DURATION_S` instance field
- `_pending_buffer_duration_s: int | None = None` instance field
- `_maybe_grow_buffer_duration()` — bump 0→1→2 (cap), stage pending, emit Signal (called from _on_underrun_cycle_closed)
- `_apply_pending_buffer_duration_to_pipeline()` — write `set_property("buffer-duration", N * Gst.SECOND)` BEFORE the next URI bind, then clear pending
- `_reset_buffer_duration_to_baseline()` — no-op when already at baseline (no Signal); else reset + emit
- Apply-and-reset block in `_try_next_stream` BEFORE the uri set_property (test_try_next_stream_applies_pending_before_uri_bind + test_try_next_stream_resets_growth_to_baseline)
- Apply-and-reset block in `_on_preroll_about_to_finish` BEFORE the gapless uri set_property (test_preroll_handoff_applies_pending_before_uri_swap)

### Constants (musicstreamer/constants.py — Plan 84-02)

- `BUFFER_DURATION_S = 30` (D-10)
- `BUFFER_SIZE_BYTES = 20 * 1024 * 1024` (D-10)

### NowPlayingPanel (musicstreamer/ui_qt/now_playing_panel.py — Plan 84-03)

- `_buffer_duration_label` widget initialized to `f"{BUFFER_DURATION_S}s"` (i.e. "30s") in `_build_stats_widget`
- Third QFormLayout row with label text `"Buf duration"` (NOT `"Buffer"` — would shadow row 0 progressbar label), positioned AFTER the Phase 78 Underruns row
- `set_buffer_duration(seconds: int) -> None` slot:
  - `BUFFER_DURATION_S` → `"30s"` (no suffix)
  - any other value → `"Ns (adapted)"` suffix
- form.rowCount() must be ≥ 3 after construction

### MainWindow (musicstreamer/ui_qt/main_window.py — Plan 84-03)

- One new `self._player.buffer_duration_changed.connect(self.now_playing.set_buffer_duration)` line immediately after the Phase 78 underrun_count_changed wire (line ~390). DirectConnection (both ends main-thread), bound method (QA-05).

### Hygiene gate constraints (test_playbin3_property_hygiene.py — forever)

- `_ALLOWED_PIPELINE_PROPERTIES = {"video-sink", "audio-sink", "buffer-duration", "buffer-size", "flags", "audio-filter", "uri", "volume"}` — adding a new property name to a `self._pipeline.set_property(...)` callsite requires adding the name to the allowlist in the same commit.
- `_BANNED_SPELLINGS = {"buffer_duration", "buffer_size", "connection_speed", "low-percent", "high-percent"}` — banned forever (or until an explicit phase decision unlocks low-percent / high-percent for the deferred queue2 watermark tuning).
- `flags | 0x100` (GST_PLAY_FLAG_BUFFERING) literal must remain in executable code of musicstreamer/player.py — currently at player.py:325. Without it ALL Phase 84 work is invisible.

## Commit Trail

| Task | Hash      | Subject                                                                  |
| ---- | --------- | ------------------------------------------------------------------------ |
| 1    | `d4ab335` | test(84-01): bump D-10 buffer constants + add FakePlayer parity mirror   |
| 2    | `a6f3443` | test(84-01): add D-11 buffer-growth state-machine + URI-bind RED suite   |
| 3    | `d8b540d` | test(84-01): add playbin3 property hygiene + flags\|0x100 source-grep gate |
| 4    | `5910302` | test(84-01): add D-12 Buf-duration stats row + Signal-wire RED tests     |

Final SUMMARY.md commit (this file) will be the fifth commit on this worktree branch.

## Deviations from Plan

### RED expected per Wave 0 contract (informational, not a deviation)

Per the wave_context section of the orchestrator brief: "All 4 tasks in this plan are TEST-ONLY (no production code changes to musicstreamer/* in this plan). Tests are EXPECTED to fail at the end of this plan — that's the RED contract."

- Task 1 verify command: 2 RED in test_player_buffer.py (constants assertions). Parity test stays GREEN. Expected.
- Task 2 verify command: 9 RED in test_player_buffer_growth.py (no Signal / no state fields / no helpers on Player yet). Expected.
- Task 3 verify command: 3 GREEN-by-coincidence in test_playbin3_property_hygiene.py. Expected.
- Task 4 verify command: 4 RED (5 reported due to parametrize expansion) in test_now_playing_panel.py + test_main_window_underrun.py. Expected.

### Minor: docstring count language in tests/_fake_player.py

The plan asked to update the "20 signals, D-16 invariant" docstring text to "21 signals". I split this into a slightly clearer two-clause explanation: "20 signals, D-16 invariant + 1 Wave-0 forward-compatible mirror" — because Player itself does NOT have the new Signal in Wave 0, so saying "21 signals" without context would be misleading. The parity drift-guard tests do not depend on the count text in the docstring (they grep `name = Signal(...)` declarations directly), so this prose change is purely informational. Tracked as `[Rule 2 - clarity, no behavior change]`.

### Minor: test_set_buffer_duration_adapted_format parametrized

The plan said "Parametrize over `[(60, "60s (adapted)"), (120, "120s (adapted)")]`" which I implemented exactly. The pytest reporter counts this as 2 instances (one per parametrize case), so the verify command shows 4 RED rather than 3 RED for the Now Playing block. Acceptance criterion was on def count (3 grep matches for `^def test_set_buffer_duration_adapted_format`) — count is 1 def, satisfying the criterion. Tracked as `[Rule 1 - count clarification]`.

### Authentication gates

None.

## Files NOT Touched (invariants honored)

- `musicstreamer/*` — zero production-code changes (verified via `git diff --stat 341c143..HEAD -- 'musicstreamer/*'` returning empty).
- `musicstreamer/__main__.py:222 / :226` — Phase 62 Pitfall 5 invariant (basicConfig(WARNING) + per-logger INFO escalation). Not touched.
- `musicstreamer/player.py:325` (`flags | 0x100`) — load-bearing GST_PLAY_FLAG_BUFFERING bit. Not touched (regression-locked by the new hygiene gate).
- `tests/conftest.py` — no shared-fixture extraction per Pattern S-6 (per-file helper duplication is the project convention).

## Threat Flags

None. All test code reads `Path(__file__).resolve().parent.parent / "musicstreamer"`-relative paths; no hardcoded user paths, no credentials, no network calls.

## Known Stubs

None. This is a Wave 0 RED test plan; the RED state IS the contract — Wave 1 (Plan 84-02) ships the production code, Wave 2 (Plan 84-04) ships the closure VERIFICATION.md.

## Self-Check

FOUND: tests/test_player_buffer_growth.py
FOUND: tests/test_playbin3_property_hygiene.py
FOUND: tests/_fake_player.py (modified)
FOUND: tests/test_player_buffer.py (modified)
FOUND: tests/test_now_playing_panel.py (modified)
FOUND: tests/test_main_window_underrun.py (modified)
FOUND: d4ab335 (Task 1)
FOUND: a6f3443 (Task 2)
FOUND: d8b540d (Task 3)
FOUND: 5910302 (Task 4)

## Self-Check: PASSED
