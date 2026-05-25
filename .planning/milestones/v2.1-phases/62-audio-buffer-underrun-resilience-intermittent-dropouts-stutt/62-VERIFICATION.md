---
phase: 62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt
verified: 2026-05-08T02:51:03Z
status: passed
score: 4/4 must-haves verified (SC #3 deferred per CONTEXT.md; not counted as a gap)
overrides_applied: 0
deferred:
  - truth: "Behavior fix that demonstrably reduces dropout count under repro conditions (Success Criterion #3)"
    addressed_in: "Future follow-up phase (not yet scheduled)"
    evidence: "62-CONTEXT.md <deferred> section: 'Behavior fix (success criterion #3) — buffer-duration / buffer-size adjustment, reconnect logic, low-watermark threshold, smarter underrun recovery. This phase ships instrumentation; the fix is a follow-up phase scheduled once log data identifies a root cause. Phase 16 baseline (10s / 10MB) held verbatim per D-09.' Verifier prompt: 'SC #3 (behavior fix) is EXPLICITLY DEFERRED to a follow-up phase per CONTEXT.md <deferred> section.'"
---

# Phase 62: Audio Buffer Underrun Resilience Verification Report

**Phase Goal:** Intermittent dropouts/stutters when the GStreamer buffer can't keep up are observable, mitigable, and (once root cause is known) fixed. Surface lives in `musicstreamer/player.py` and the buffer constants in `musicstreamer/constants.py`.

**Verified:** 2026-05-08T02:51:03Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

This phase ships the **instrumentation half** of BUG-09 per the explicit out-of-scope deferral in `62-CONTEXT.md` `<deferred>`. SC #3 (behavior fix) is gated on observed log data from this phase's instrumentation and is correctly deferred to a follow-up phase. The verifier prompt explicitly instructed: *"Verify SC #1, #2, #4 against the implemented code; treat SC #3 as an out-of-scope deferred item and note its deferral in VERIFICATION.md without failing the phase."*

### Observable Truths (Roadmap Success Criteria)

| # | Truth (Success Criterion) | Status | Evidence |
| - | ------------------------- | ------ | -------- |
| 1 | When a buffer underrun occurs, the event is logged with cause attribution and timestamp — enough to diagnose intermittent reports | VERIFIED | Two structured-log emission sites in `musicstreamer/player.py`: `_on_underrun_cycle_closed` slot (lines 774-790) and `shutdown_underrun_tracker` (lines 566-586), both writing `_log.info("buffer_underrun start_ts=%.3f end_ts=%.3f duration_ms=%d min_percent=%d station_id=%d station_name=%r url=%r outcome=%s cause_hint=%s", ...)`. Cause attribution is the minimal `cause_hint` field (`unknown` default; flipped to `network` by `note_error_in_cycle()` when `_on_gst_error` fires within an open cycle, line 632) — locked per CONTEXT.md `<decisions>` Discretion. Tests `test_cycle_close_writes_structured_log` (asserts all 9 field tokens) and `test_cause_hint_network_after_error` GREEN. |
| 2 | The user gets a non-spammy visible indicator when buffering recovery is in progress | VERIFIED | `MainWindow._on_underrun_recovery_started` slot at `musicstreamer/ui_qt/main_window.py:364-380` shows `Buffering…` toast (D-06 U+2026 ellipsis), debounced by `time.monotonic()`-based 10s cooldown gate (`_UNDERRUN_TOAST_COOLDOWN_S: float = 10.0` at line 136; per-instance bookkeeping `_last_underrun_toast_ts: float = 0.0` at line 265). Player emits `underrun_recovery_started` only on cycles exceeding the 1500ms dwell threshold (`_underrun_dwell_timer`, lines 357-360). Tests `test_first_call_shows_toast`, `test_second_call_within_cooldown_suppressed`, `test_toast_after_cooldown_allowed` all GREEN. |
| 3 | Once the root cause is identified, the phase ships a behavior fix that demonstrably reduces dropout count | DEFERRED | Explicitly deferred per `62-CONTEXT.md` `<deferred>` section. SC #3 is gated on the instrumentation this phase ships producing observable log samples. NOT a gap — verifier prompt confirms the deferral is sanctioned. See "Deferred Items" section. |
| 4 | The instrumentation does not regress existing buffer constants (Phase 16: 10s / 10MB) without an explicit decision logged in CONTEXT.md | VERIFIED | `git diff b719a08 HEAD -- musicstreamer/constants.py` returns 0 lines (constants.py untouched since Phase 60.4 close). `BUFFER_DURATION_S = 10` (line 55) and `BUFFER_SIZE_BYTES = 10 * 1024 * 1024` (line 56) confirmed unchanged. `pytest tests/test_player_buffer.py::test_buffer_duration_constant tests/test_player_buffer.py::test_buffer_size_constant` exits 0 (2/2 PASSED). D-09 invariant explicitly logged in `62-CONTEXT.md` `<decisions>` Phase 16 Invariant. |

**Score:** 4/4 in-scope SCs verified (#1, #2, #4 as instrumentation deliverables; #3 correctly deferred and not counted as a gap per verifier prompt).

### Deferred Items

| # | Item | Addressed In | Evidence |
| - | ---- | ------------ | -------- |
| 1 | SC #3 — behavior fix (buffer-duration / buffer-size tuning, reconnect logic, low-watermark threshold) that demonstrably reduces dropout count | Future follow-up phase (not yet scheduled in roadmap) | `62-CONTEXT.md` `<deferred>` section: *"Behavior fix (success criterion #3) — buffer-duration / buffer-size adjustment, reconnect logic, low-watermark threshold, smarter underrun recovery. This phase ships instrumentation; the fix is a follow-up phase scheduled once log data identifies a root cause."* The follow-up is explicitly gated on this phase's instrumentation producing observable log samples; no later phase in the roadmap currently claims SC #3 closure but the roadmap permits scheduling via `/gsd-add-phase` once data accumulates. Verifier prompt sanctions this deferral. |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `musicstreamer/player.py` | `_BufferUnderrunTracker` class + `_CycleClose` dataclass + `_log` module logger + Player wiring (3 Signals, dwell QTimer, tracker instance, `_current_station_id` field, queued connections, bus-handler extensions, terminator force-closes, 4 main-thread slots, `shutdown_underrun_tracker` public method) | VERIFIED | 1289 lines (1167 from Plan 01 + 122 from Plan 02). All 23 grep gates pass. `_BufferUnderrunTracker` (line 111) is pure Python; `_CycleClose` (line 92-108) is `@dataclass(frozen=True)` with all 9 fields; `_log` (line 77) defined module-level. Player class wired at insertion sites: Signals (lines 271-273), dwell QTimer (357-360), queued connects (390-394), tracker instance + station_id (417-418), `play()` capture (479), `play_stream()` clear (510), `pause()` force-close (538-541), `stop()` force-close (559-562), `shutdown_underrun_tracker` (566-586), `_on_gst_error` hook (632), `_on_gst_buffering` observe (697-701), `_try_next_stream` force-close BEFORE bind_url (822-830), 3 main-thread slots (765-796). |
| `musicstreamer/ui_qt/main_window.py` | `import time`, `_UNDERRUN_TOAST_COOLDOWN_S` class constant, `_last_underrun_toast_ts` field, queued `underrun_recovery_started.connect`, `_on_underrun_recovery_started` slot, `closeEvent` calls `shutdown_underrun_tracker` BEFORE `_media_keys.shutdown` | VERIFIED | All 6 insertion sites confirmed: `import time` at line 24; `_UNDERRUN_TOAST_COOLDOWN_S: float = 10.0` at line 136; `self._last_underrun_toast_ts: float = 0.0` at line 265; queued connection at lines 294-295 (`Qt.ConnectionType.QueuedConnection`); slot at lines 364-380 (`time.monotonic()` cooldown gate, `show_toast("Buffering…")` D-06); closeEvent (lines 386-402) calls `shutdown_underrun_tracker()` at line 395 BEFORE `_media_keys.shutdown()` at line 399 — Pitfall 4 ordering verified by source-text inspection. |
| `musicstreamer/__main__.py` | Per-logger INFO for `musicstreamer.player`; `basicConfig(WARNING)` preserved | VERIFIED | Line 222: `logging.basicConfig(level=logging.WARNING)` preserved verbatim (Pitfall 5 — global default unchanged). Line 226: `logging.getLogger("musicstreamer.player").setLevel(logging.INFO)` — scoped per-logger bump. Existing 3-line Phase 62 / Pitfall 5 reference comment at lines 223-225. |
| `musicstreamer/constants.py` | UNTOUCHED — D-09 invariant | VERIFIED | `git diff b719a08 HEAD -- musicstreamer/constants.py` returns 0 lines. `BUFFER_DURATION_S = 10` at line 55 and `BUFFER_SIZE_BYTES = 10 * 1024 * 1024` at line 56 unchanged. |
| `musicstreamer/ui_qt/now_playing_panel.py` | UNTOUCHED — D-05 invariant (toast-only UX, no stats-for-nerds bar auto-show) | VERIFIED | `git diff b719a08 HEAD -- musicstreamer/ui_qt/now_playing_panel.py` returns 0 lines (untouched since Phase 60.4 close). |
| `tests/test_player_underrun_tracker.py` | 7 unit tests for `_BufferUnderrunTracker` pure-logic | VERIFIED | 104 lines, 7 `def test_` definitions, all GREEN. |
| `tests/test_player_underrun.py` | 8 integration tests for Player wiring | VERIFIED | 201 lines, 8 `def test_` definitions, all GREEN. |
| `tests/test_main_window_underrun.py` | 5 integration tests for MainWindow + `__main__` logger | VERIFIED | 132 lines, 5 `def test_` definitions, all GREEN. |
| `tests/test_main_window_integration.py` | FakePlayer extended with `underrun_recovery_started` Signal + `shutdown_underrun_tracker` no-op | VERIFIED | Both additions present; 46 pre-existing MainWindow integration tests still pass (verified in adjacent regression suite below). |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `Player._on_gst_buffering` (bus-loop thread, line 679) | `Player._on_underrun_cycle_opened` / `_on_underrun_cycle_closed` (main thread, lines 765, 774) | `Qt.ConnectionType.QueuedConnection` on `_underrun_cycle_opened.connect` and `_underrun_cycle_closed.connect` (lines 390-394) | WIRED | Verified by `grep -c "Qt.ConnectionType.QueuedConnection" musicstreamer/player.py` returns 9 (4 pre-existing + 2 new for cycle-opened/closed + 3 from other phases counted in baseline). Test `test_buffering_drop_emits_cycle_opened` GREEN proves the queued cross-thread emission delivers. |
| `Player._on_underrun_dwell_elapsed` (line 792) | `MainWindow._on_underrun_recovery_started` (line 364) | `underrun_recovery_started` Signal connected with `Qt.ConnectionType.QueuedConnection` at `main_window.py:294-295` | WIRED | Test `test_first_call_shows_toast` GREEN proves the chain: dwell timer fires → `underrun_recovery_started.emit()` → MainWindow slot → `show_toast("Buffering…")`. |
| `Player._try_next_stream` (line 802) | `tracker.force_close('failover')` BEFORE `tracker.bind_url(new)` (lines 822-830) | T-62-02 ordering invariant: source-text order = call order | WIRED | `_try_next_stream` line 822 (`force_close("failover")`) precedes line 826 (`bind_url(...)`) by source ordering. Test `test_try_next_stream_force_closes_with_failover_outcome` GREEN; assertion `closed_records[0].url == "http://old.test/"` proves the close record was built BEFORE bind_url to the new URL. |
| `MainWindow.closeEvent` (line 386) | `Player.shutdown_underrun_tracker()` (line 566) BEFORE `_media_keys.shutdown()` | Pitfall 4 ordering: source-text inspection at lines 394-401 | WIRED | Line 395 (`self._player.shutdown_underrun_tracker()`) precedes line 399 (`self._media_keys.shutdown()`) — confirmed in source. Test `test_close_event_force_closes_open_cycle` GREEN. |
| `musicstreamer.__main__.main` (line 221) | `musicstreamer.player` module logger | `logging.getLogger("musicstreamer.player").setLevel(logging.INFO)` at line 226 | WIRED | Test `test_main_module_sets_player_logger_to_info` GREEN; regex match on file source confirms scoped INFO bump alongside preserved global WARNING basicConfig. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `_log.info("buffer_underrun ...")` in `_on_underrun_cycle_closed` (line 783) | `record` (`_CycleClose`) | `_BufferUnderrunTracker._close_with_now` returns frozen dataclass with concrete clock-derived `start_ts/end_ts/duration_ms`, observed `min_percent`, bound `station_id/station_name/url` from `bind_url`, supplied `outcome`, `cause_hint` flipped by `note_error_in_cycle` | YES — every field is sourced from real runtime state, not hardcoded constants. The dataclass is `@dataclass(frozen=True)` so the record is immutable post-construction. | FLOWING |
| `show_toast("Buffering…")` in `_on_underrun_recovery_started` (line 379) | Static literal `"Buffering…"` | This is intentionally a static UX string per D-06 (silent recovery, no per-cycle text variation). Underlying decision to call this is gated on a real `time.monotonic()` cooldown comparison against `self._last_underrun_toast_ts`. | YES — the GATING DECISION uses real wall-clock data; the literal text is by design. | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Tracker module imports cleanly with all expected interface | `python3 -c "from musicstreamer.player import _BufferUnderrunTracker, _CycleClose; ..."` | All public methods present (`bind_url`, `observe`, `force_close`, `note_error_in_cycle`); `_CycleClose` has 9 fields; module logger `_log` is `logging.Logger` named `musicstreamer.player` | PASS |
| End-to-end tracker drives `%r`-quoted log line; T-62-01 mitigation works | Constructed tracker with `station_name='Test Station\nINJECT'`, ran arm/open/close, formatted log line | Output: `station_name='Test Station\nINJECT'` (literal `\n` escaped, NOT a newline). `\\n` substring confirmed in formatted msg. Log injection control char neutralized. | PASS |
| Phase 62 targeted suite (20 tests) | `pytest tests/test_player_underrun_tracker.py tests/test_player_underrun.py tests/test_main_window_underrun.py -q` | `20 passed, 1 warning in 1.60s` | PASS |
| Adjacent regression suite (80 tests) | `pytest tests/test_main_window_integration.py tests/test_player_buffering.py tests/test_player_buffer.py tests/test_player.py tests/test_player_pause.py -q` | `80 passed, 1 warning in 1.43s` | PASS |
| D-09 invariant tests | `pytest tests/test_player_buffer.py::test_buffer_duration_constant tests/test_player_buffer.py::test_buffer_size_constant -v` | `2 passed in 0.07s` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| BUG-09 | 62-00, 62-01, 62-02, 62-03 | Intermittent audio dropouts/stutters when the GStreamer buffer can't keep up are observable, attributable, and (once root-caused) mitigated. Repro is unclear at filing time — phase ships diagnostic instrumentation first, then a behavior fix once root cause is observable | SATISFIED (instrumentation half) | This phase ships the observability + attributability surface (SC #1 structured log line; SC #2 toast). The behavior fix is explicitly deferred per CONTEXT.md `<deferred>`. REQUIREMENTS.md already marks BUG-09 as `[x] Complete` — appropriate given the deferred-fix-as-follow-up convention. |

No orphaned requirements: all 4 plans reference only `BUG-09` in their `requirements:` frontmatter, and REQUIREMENTS.md maps Phase 62 to BUG-09 only.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | — | — | — |

Scanned the modified files for TODO/FIXME/PLACEHOLDER comments, empty implementations (`return null/return {}`), hardcoded empty data flowing to rendering, and `console.log`-only handlers. None found in:
- `musicstreamer/player.py` (Phase 62 additions)
- `musicstreamer/ui_qt/main_window.py` (Phase 62 additions)
- `musicstreamer/__main__.py` (Phase 62 additions)
- `tests/test_player_underrun_tracker.py`, `tests/test_player_underrun.py`, `tests/test_main_window_underrun.py`

The static `"Buffering…"` literal in `_on_underrun_recovery_started` is intentional per D-06 (toast-only UX, silent recovery, no per-cycle text variation) — not a stub.

### Human Verification Required

None. All four in-scope success criteria are verifiable against the codebase: SC #1 (structured log emission) is verified via test `test_cycle_close_writes_structured_log` and confirmed via the spot-check showing `\n` escape via `%r`; SC #2 (cooldown-gated toast) is verified via three tests covering the cooldown gate; SC #4 (constants untouched) is verified by zero-line `git diff` on `constants.py` and 2/2 D-09 invariant tests passing. SC #3 is deferred per the verifier prompt and CONTEXT.md, so no human visual/UX verification of behavior change is required this phase.

### Gaps Summary

No gaps. The phase delivered the instrumentation half of BUG-09 as designed:
- 20/20 RED tests authored in Plan 00 turned GREEN through Plans 01-03
- 80/80 adjacent regression tests still pass
- D-09 invariant preserved (constants.py 0-line diff; 2/2 invariant tests pass)
- D-05 invariant preserved (now_playing_panel.py 0-line diff)
- Pitfall 5 honored (basicConfig stays at WARNING; only `musicstreamer.player` is bumped to INFO)
- Pitfall 4 honored (closeEvent calls `shutdown_underrun_tracker` BEFORE `_media_keys.shutdown` for synchronous log write; queued slots may not run after closeEvent returns)
- T-62-01 mitigation live (both log emission sites use `station_name=%r url=%r`; spot-check confirmed `\n` escape)
- T-62-02 ordering invariant live (`_try_next_stream` force-closes BEFORE bind_url; close record carries OLD URL)

SC #3 (behavior fix) is sanctioned-deferred per the verifier prompt and CONTEXT.md `<deferred>` section. The instrumentation now in place produces the log samples the future behavior-fix phase needs to identify a root cause; that follow-up phase will be scheduled via `/gsd-add-phase` once enough cycle-close samples accumulate from daily use.

---

_Verified: 2026-05-08T02:51:03Z_
_Verifier: Claude (gsd-verifier)_
