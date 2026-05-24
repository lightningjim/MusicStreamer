---
phase: 84-bug-09-commit-b-buffer-tuning-behavior-fix-reframed-from-str
verified: 2026-05-24T00:00:00Z
status: human_needed
score: 13/13 must-haves verified (Phase 84 ship-side)
overrides_applied: 0
closure_model: ship-plus-monitor
nyquist_compliant: true
waived_gates:
  - id: phase-78-D-06
    text: "M < N AND median lower"
    rationale: "Harvest week yielded 12 buffer_underrun events / 7 days — insufficient sample for marginal-effect detection. Reframed per Phase 84 D-13."
human_verification:
  - test: "Post-ship 2-week monitor window (~/.local/share/musicstreamer/buffer-events.log)"
    expected: "Over 2 weeks of normal daily-use after the Phase 84 ship commit, the buffer-events.log shows REDUCED long-event count vs the harvest-week baseline (12 events / 5 long: 2 YouTube + 3 SomaFM, max magnitude 7389ms) OR holds steady. If any of the three Follow-Up Triggers below fires, open a follow-up phase for reconnect-on-stall evaluation."
    why_human: "Requires real-world environmental conditions and 2 weeks of accumulated samples. No CI substitute is meaningful — the entire Phase 84 reframe predicate is that statistical sample size is too low for synthetic A/B."
---

# Phase 84: BUG-09 Commit B — Buffer-Tuning Behavior Fix (ship + monitor closure) Verification Report

**Phase Goal:** Ship the deferred Commit B buffer-tuning behavior fix under a **ship + monitor** reframe. Four-part contract:

- **D-10** — static bump `BUFFER_DURATION_S` 10→30s and `BUFFER_SIZE_BYTES` 10MB→20MB in `musicstreamer/constants.py` (single coordinated edit).
- **D-11** — adaptive growth state machine 30→60→120s (cap), implemented as a stage-and-apply fallback (stage at `_on_underrun_cycle_closed`, apply at next URI bind in BOTH `_try_next_stream` and `_on_preroll_about_to_finish`). Mid-session `set_property` writes were FALSIFIED by direct `gstplaybin3.c` source inspection — the fallback shape is mandatory, not optional (84-RESEARCH §D-11 Resolution, evidence A1).
- **D-12** — always-visible `Buf duration` stats-for-nerds row + `buffer_duration_changed = Signal(int)` wired through `MainWindow` DirectConnection to `NowPlayingPanel.set_buffer_duration`.
- **D-13** — this VERIFICATION.md (waived statistical gate + 2-week monitor plan + explicit follow-up trigger thresholds + explicit SC #3 closure statement).

Closes BUG-09 SC #3 (behavior side) on the Phase 84 ship commit. SC #3 logging side already closed by Phase 78 Commit A (2026-05-17). The full BUG-09 SC #3 closure chain is Phase 62 → Phase 78 Commit A → Phase 84, all three plans now closed.

**Verified:** 2026-05-24
**Status:** human_needed (Phase 84 ship-side deliverables complete; monitor-window UAT requires real-world daily-use accumulation per D-13)
**Re-verification:** No — initial verification.

## Closure Model — Waived Statistical Gate

This phase ships under a **WAIVED** statistical-closure model. The Phase 78 D-06 closure gate (`M < N AND median lower`, where M = post-fix long-event count over a comparable window and N = the pre-fix baseline count harvested by Phase 78 Commit A) is explicitly **WAIVED** for Phase 84.

**Rationale:** The harvest week (2026-05-19 → 2026-05-24, ~5.25 days of recorded events / 7 days since Commit A ship) yielded 12 `buffer_underrun` events. 12 events / 7 days is insufficient sample for marginal-effect detection at any reasonable confidence level. The data IS sufficient to lock the D-10 magnitudes (30s covers the observed 7.4s worst case with ~3× headroom) and the D-11 schedule shape (30→60→120 doubling, the only schedule that lets a station survive two long underruns without exceeding the perceptual ceiling), but NOT to detect "did the fix reduce long-event count by X%" via post-ship A/B.

Closure is therefore **ship + monitor**: the D-10 / D-11 / D-12 deliverables are technically complete on the ship commit, and the 2-week monitor plan below is forward-looking guidance for OPENING a follow-up phase if needed — it is NOT a closure prerequisite for Phase 84.

This waiver is intentional, sanctioned by CONTEXT D-13, and documented here (the closure record itself) plus in the frontmatter `waived_gates` block above for tooling consumers (`gsd:verify-work`).

## Goal Achievement

Must-haves merged from CONTEXT.md `<decisions>` D-10 through D-13 and the four prior plans' (`84-01`, `84-02`, `84-03`) `must_haves.truths` and SUMMARY.md `provides` blocks. Each row cites the file path + line range that satisfies the truth AND the pytest test name that GREEN-locks the behavior.

| #  | Truth | Status | Evidence |
| -- | ----- | ------ | -------- |
| 1  | `BUFFER_DURATION_S == 30` in `musicstreamer/constants.py` (D-10 static bump from Phase 16 baseline of 10s) | VERIFIED | `musicstreamer/constants.py:54-56`; bumped at commit `c003662` (`feat(84-02): D-10 bump buffer constants 10→30s / 10→20MB`); `tests/test_player_buffer.py::test_buffer_duration_constant` GREEN; `tests/test_player_buffer_growth.py::test_constants_match_phase_84_d10_bump` GREEN (5 passed in `tests/test_player_buffer.py` per Plan 02 SUMMARY). |
| 2  | `BUFFER_SIZE_BYTES == 20 * 1024 * 1024` in `musicstreamer/constants.py` (D-10 coordinated edit; 20MB ensures byte cap does not constrain duration at FLAC bitrate) | VERIFIED | `musicstreamer/constants.py:54-56`; bumped in same commit `c003662`; misleading `# 5 MB` inline comment replaced with `# 20 MB (was 10 MB despite the wrong inline comment)`; `tests/test_player_buffer.py::test_buffer_size_constant` GREEN. |
| 3  | `buffer_duration_changed = Signal(int)` declared at `Player` class scope (D-11 / D-12 Signal contract; mirrors Phase 78 `underrun_count_changed`) | VERIFIED | `musicstreamer/player.py:306` immediately after `underrun_count_changed = Signal(int)` (Phase 78 mirror at :297); shipped in commit `29d0dea`; `tests/test_player_buffer_growth.py::test_buffer_duration_changed_signal_at_class_scope` GREEN. |
| 4  | Three instance fields initialized in `Player.__init__`: `_growth_step: int = 0`, `_current_buffer_duration_s: int = BUFFER_DURATION_S`, `_pending_buffer_duration_s: int \| None = None` (D-11 state surface) | VERIFIED | `musicstreamer/player.py:523-525`; all three fields type-annotated; commit `29d0dea`; `tests/test_player_buffer_growth.py::test_instance_fields_initialized` GREEN. |
| 5  | `_maybe_grow_buffer_duration()` helper implements 30→60→120 schedule with cap at growth step 2; emits `buffer_duration_changed` only when the value changes (Pitfall 3 — no spurious emit at baseline) | VERIFIED | `musicstreamer/player.py:1165` (helper) with inline `{1:60, 2:120}` schedule and `if self._growth_step >= 2: return` cap at ~:1183; commit `29d0dea`; `tests/test_player_buffer_growth.py::test_growth_step_caps_at_120s` GREEN + `test_growth_emits_signal_on_change` GREEN. |
| 6  | `_apply_pending_buffer_duration_to_pipeline()` helper writes `set_property("buffer-duration", N * Gst.SECOND)` and clears pending state (D-11 apply half) | VERIFIED | `musicstreamer/player.py:1203`; commit `29d0dea`; `tests/test_player_buffer_growth.py::test_apply_writes_to_pipeline_then_clears_pending` GREEN. |
| 7  | `_reset_buffer_duration_to_baseline()` helper resets per-URL; Pitfall 3 early-return at baseline so spurious Signal does NOT fire (would cause stats row twitch at every URL bind) | VERIFIED | `musicstreamer/player.py:1230`; commit `29d0dea`; `tests/test_player_buffer_growth.py::test_reset_at_baseline_no_signal` GREEN (Pitfall 3 catcher). |
| 8  | Cycle-close staging hook: `self._maybe_grow_buffer_duration()` called at end of `_on_underrun_cycle_closed` so each cycle-close stages the next growth step | VERIFIED | `musicstreamer/player.py:1163`; commit `29d0dea`; `tests/test_player_buffer_growth.py::test_cycle_close_stages_growth` GREEN. |
| 9  | Both URI-bind apply sites present (D-11 + Pitfall 2): `_apply_pending_buffer_duration_to_pipeline` + `_reset_buffer_duration_to_baseline` are called in `_try_next_stream` BEFORE the uri `set_property` AND in `_on_preroll_about_to_finish` BEFORE the gapless uri `set_property` (the SomaFM hourly gapless handoff path that is easy to forget) | VERIFIED | `musicstreamer/player.py:1280-1282` (`_try_next_stream` site) and `musicstreamer/player.py:1486-1488` (`_on_preroll_about_to_finish` site); `grep -cE "self\._apply_pending_buffer_duration_to_pipeline\(\)" musicstreamer/player.py` → 2; `grep -cE "self\._reset_buffer_duration_to_baseline\(\)" musicstreamer/player.py` → 2 (Plan 02 SUMMARY invariant block); `tests/test_player_buffer_growth.py::test_try_next_stream_applies_pending_before_uri_bind` + `::test_preroll_handoff_applies_pending_before_uri_swap` BOTH GREEN. |
| 10 | Dash-form property name `"buffer-duration"` used at every callsite; underscore form `"buffer_duration"` banned (Pitfall 4 / hygiene gate — playbin 1.x spelling silently no-ops on playbin3) | VERIFIED | `grep -nE "set_property\(['\"]buffer_duration['\"]" musicstreamer/player.py` → 0 lines (Plan 02 SUMMARY); `tests/test_playbin3_property_hygiene.py::test_no_banned_playbin_1x_property_spellings` GREEN (allowlist + banned-list pair). |
| 11 | `flags \| 0x100` (GST_PLAY_FLAG_BUFFERING) literal preserved byte-identical at `musicstreamer/player.py:342` (formerly :325 pre-Plan-02; relocated by interleaving but bit-identical). Without this bit, ALL Phase 84 buffer-tuning work is invisible on HTTP sources. | VERIFIED | `grep -nE "flags\s*\|\s*0x100" musicstreamer/player.py` → `342:` (Plan 02 SUMMARY invariant block); `tests/test_playbin3_property_hygiene.py::test_flags_play_buffering_bit_present` GREEN (forever-locked source-grep gate from Plan 01). |
| 12 | `musicstreamer/__main__.py` untouched (Phase 62 Pitfall 5 — `basicConfig(WARNING)` + per-logger INFO escalation MUST stay byte-identical; Phase 78 Commit A drift-guard carries forward) | VERIFIED | `git diff --stat musicstreamer/__main__.py` → empty across all Phase 84 commits (Plan 02 SUMMARY invariant block + Plan 03 SUMMARY untouched-file verification); `tests/test_main_window_underrun.py::test_main_module_sets_player_logger_to_info` (Phase 78 drift-guard) GREEN. |
| 13 | D-12 NowPlayingPanel surface: `set_buffer_duration(seconds: int) -> None` slot at `now_playing_panel.py:1012`; always-visible `Buf duration` QFormLayout row at `now_playing_panel.py:2966` (between Phase 78 Underruns row at :2956 and trailing `wrapper.setVisible(False)` at :2969); MainWindow DirectConnection wire at `main_window.py:402` (bound method, no lambda, no QueuedConnection arg) | VERIFIED | Plan 03 SUMMARY post-edit line anchors table; commits `e60d165` (NowPlayingPanel slot + row) and `3f0c82c` (MainWindow wire); `tests/test_now_playing_panel.py::test_buffer_duration_row_present` + `::test_set_buffer_duration_baseline_format` + `::test_set_buffer_duration_adapted_format[60-60s (adapted)]` + `::test_set_buffer_duration_adapted_format[120-120s (adapted)]` ALL GREEN (146 passed in `tests/test_now_playing_panel.py` per Plan 03 SUMMARY); `tests/test_main_window_underrun.py::test_buffer_duration_changed_updates_stats_row` GREEN post-wave-merge (passes once Plan 02 baseline `BUFFER_DURATION_S=30` is live, which it now is at commit `c003662`). |

**Score:** 13/13 must-haves VERIFIED (Phase 84 ship-side).

The 14th candidate truth — the post-ship harvest monitor itself — is captured as the single human-verification item below. It is the WAIVED-gate replacement: instead of a statistical A/B closure, the monitor window is forward-looking guidance that opens a follow-up phase ONLY if the verbatim D-13 thresholds fire. Per CONTEXT D-13 it is explicitly NOT a closure prerequisite.

## Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `musicstreamer/constants.py` | D-10 literal bumps + comment freshening | VERIFIED | `BUFFER_DURATION_S = 30`, `BUFFER_SIZE_BYTES = 20 * 1024 * 1024` (lines 54-62 per Plan 02 SUMMARY). Commit `c003662`. |
| `musicstreamer/player.py` | D-11 + D-12 state machine: Signal decl + 3 init fields + 3 helper methods + cycle-close hook + 2 URI-bind apply sites + drive-by comment freshening | VERIFIED | +130/-4 lines per Plan 02 SUMMARY metrics; Signal at :306; init at :523-525; helpers at :1165 / :1203 / :1230; cycle-close hook at :1163; apply sites at :1280-1282 and :1486-1488; freshened comment block at :332-341; `flags \| 0x100` preserved at :342. Commit `29d0dea`. |
| `musicstreamer/ui_qt/now_playing_panel.py` | D-12 set_buffer_duration slot + always-visible `Buf duration` row | VERIFIED | Slot at :1012 (immediately after Phase 78 `set_underrun_count` at :1002); row at :2966 (between Underruns row at :2956 and `wrapper.setVisible(False)` at :2969); +28 lines per Plan 03 SUMMARY. Commit `e60d165`. |
| `musicstreamer/ui_qt/main_window.py` | D-12 buffer_duration_changed Signal wire | VERIFIED | `self._player.buffer_duration_changed.connect(self.now_playing.set_buffer_duration)` at :402 immediately after the Phase 78 `underrun_count_changed` wire at :390; bound method (no lambda — QA-05), DirectConnection (no `Qt.ConnectionType.QueuedConnection` argument — both ends main-thread per qt-glib-bus-threading Pitfall 2); +12 lines per Plan 03 SUMMARY. Commit `3f0c82c`. |
| `tests/test_player_buffer.py` | D-10 constants assertion bump (Wave 0 RED → Wave 1 GREEN) | VERIFIED | Plan 01 commit `d4ab335` flipped expected values; 5 passed at Plan 02 GREEN per SUMMARY. |
| `tests/test_player_buffer_growth.py` (NEW) | D-11 state-machine + URI-bind apply-ordering RED suite (Wave 0 RED → Wave 1 GREEN) | VERIFIED | 356 lines / 9 tests per Plan 01 SUMMARY; all 9 GREEN at Plan 02 per SUMMARY pytest line. |
| `tests/test_playbin3_property_hygiene.py` (NEW) | Source-grep hygiene gate: allowlist (8 names) + banned-list (5 names) + `flags \| 0x100` regression lock | VERIFIED | 259 lines / 3 tests per Plan 01 SUMMARY; all 3 GREEN throughout Wave 1 (Plan 02 SUMMARY: "hygiene gate stays GREEN"). Forever-locks the playbin3 property-name surface against Phase 78 / 84 / future regressions. |
| `tests/test_now_playing_panel.py` | D-12 stats row + slot tests (Wave 0 RED → Wave 1 GREEN) | VERIFIED | +70 lines / 3 new tests per Plan 01 SUMMARY (`test_buffer_duration_row_present`, `test_set_buffer_duration_baseline_format`, `test_set_buffer_duration_adapted_format`); 146 passed at Plan 03 GREEN. |
| `tests/test_main_window_underrun.py` | D-12 Signal-wire end-to-end test (Wave 0 RED → Wave 1 GREEN post-wave-merge) | VERIFIED | +23 lines / 1 new test (`test_buffer_duration_changed_updates_stats_row`) per Plan 01 SUMMARY; passes post-wave-merge once Plan 02's `BUFFER_DURATION_S=30` is live (Plan 03 SUMMARY wave-merge coupling note). |
| `tests/_fake_player.py` | INFRA-01 parity mirror: `buffer_duration_changed = Signal(int)` (FakePlayer leads Player in Wave 0) | VERIFIED | Plan 01 commit `d4ab335` added the mirror + docstring count clarification; `tests/test_fake_player_signal_parity.py` 2/2 GREEN throughout Wave 0 and Wave 1. |

## Monitor Plan (Post-Ship — 2 Weeks)

**Window:** From the Phase 84 ship commit date forward 14 days of normal daily-use listening.

**Source:** `~/.local/share/musicstreamer/buffer-events.log` (Phase 78 Commit A `RotatingFileHandler`, 1MB × 3 backups; the harvest infrastructure is unchanged across Phase 84 — Phase 84 modifies the buffer-tuning behavior, NOT the logging).

**Baseline reference (harvest-week, from 84-CONTEXT.md `<data-summary>` — corrected from the ROADMAP entry's "11 events" figure per user choice to NOT amend ROADMAP):**

- **12 total `buffer_underrun` events / 7 days** (~1.7 / day average).
- **5 long events (>1s):**
  - 2026-05-19 09:09 — 6683ms — lofi hip hop — YouTube — `min_percent=0` — `cause_hint=unknown` — recovered
  - 2026-05-19 12:03 — 1356ms — Groove Salad — SomaFM mp3 — `min_percent=0` — `cause_hint=unknown` — recovered
  - 2026-05-24 10:22 — 5474ms — Drone Zone — SomaFM mp3 — `min_percent=1` — **`cause_hint=network`** — recovered
  - 2026-05-24 11:23 — 7389ms — medieval lofi — YouTube — `min_percent=0` — `cause_hint=unknown` — recovered
  - 2026-05-24 15:07 — 2446ms — Drone Zone — SomaFM mp3 — `min_percent=0` — `cause_hint=unknown` — recovered
- **7 brief events (<200ms):** 6 SomaFM micro-recoveries + 1 GBS.FM.
- **Cluster split:** 2 YouTube / 3 SomaFM among long events. YouTube worst-case magnitude 7389ms; SomaFM worst-case magnitude 5474ms (the one `cause_hint=network` event). **Both clusters are worth targeting** per D-09 framing correction (NOT YouTube-only as the original ROADMAP entry implied).

**Monitor procedure:** At the end of the 2-week window, count `buffer_underrun` lines in the current log + any rotated backups (`buffer-events.log.1`, `.2`, `.3`). Compare event count, long-event count (>1s), worst-case magnitude, and cluster split against the baseline above. Expected outcome under the D-10 / D-11 fix: long-event count DECREASES (the 30s baseline absorbs most underruns silently before they exceed 1s; the 60s/120s adaptive growth absorbs the rest after the first long event in a session). The brief-event count may stay similar — brief events are micro-recoveries that the buffer-tuning fix does not directly target.

## Follow-Up Triggers

If ANY of the following thresholds fires inside the 2-week post-ship monitor window, **open a follow-up phase for reconnect-on-stall evaluation** (Phase 78 deferred item, still parked). Thresholds are **verbatim from CONTEXT.md D-13** — they are NOT to be invented or paraphrased.

| Trigger                | Threshold                                                            | Action                                                        |
| ---------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------- |
| Long-event recurrence  | ≥3 long events (>1s) with `min_percent=0` in 2-week window           | Open follow-up phase: reconnect-on-stall evaluation           |
| Very-long recovery     | Any `recovered` event >10s                                           | Open follow-up phase: reconnect-on-stall evaluation           |
| Network cause-hint     | ≥1 `cause_hint=network` event                                        | Open follow-up phase: reconnect-on-stall evaluation           |

Reconnect-on-stall sketch (preserved from Phase 78 deferred-items block and 84-CONTEXT `<deferred>`): when a cycle exceeds N seconds, force same-URL `set_state(NULL)` → `set_state(PLAYING)` instead of waiting for natural recovery. The thresholds above are the DETERMINISTIC predicate for opening the follow-up phase; no judgment call is required — if any threshold trips, the follow-up phase is justified.

## SC #3 Closure (BUG-09)

- **BUG-09 SC #3 (behavior side) CLOSED on the Phase 84 ship commit** (the merge of this worktree branch). The D-10 static bump + D-11 adaptive growth state machine + D-12 always-visible stats row are all live; Goal Achievement table above is 13/13 VERIFIED.
- **BUG-09 SC #3 (logging side) ALREADY CLOSED by Phase 78 Commit A** (2026-05-17). See `.planning/phases/78-phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug/78-VERIFICATION.md`.
- **Full BUG-09 SC #3 closure chain:** Phase 62 (instrumentation half — SC #1, #2, #4 closed; SC #3 deferred) → Phase 78 Commit A (harvest infrastructure shipped, SC #3 logging side closed) → **Phase 84 (behavior fix shipped under ship + monitor reframe, SC #3 behavior side closed)**. All three plans are now closed.
- **The 2-week monitor window above is NOT a re-opening of SC #3.** SC #3 is closed on the Phase 84 ship commit per D-13 part 4. The monitor window is **forward-looking guidance** for OPENING a NEW follow-up phase (reconnect-on-stall evaluation) if the verbatim D-13 trigger thresholds fire. Disambiguation by repetition (per the plan's T-84-12 threat mitigation): SC #3 closes here; the monitor is separate.

## Cross-Phase References

- **Phase 62 — `.planning/phases/62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt/62-VERIFICATION.md`** — the original BUG-09 closure record where SC #3 (behavior fix) was explicitly deferred (the predecessor closure that gated SC #3 on harvest data, then on a follow-up behavior-fix phase — which became Phase 78 Commit B → reframed and shipped as Phase 84).
- **Phase 78 Commit A — `.planning/phases/78-phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug/78-VERIFICATION.md`** — the harvest-infra closure record (2026-05-17). Structural template for this VERIFICATION.md (frontmatter shape, Goal Achievement table layout, Required Artifacts table layout, human-verification block). SC #3 logging side closed there; this Phase 84 record closes the behavior side under the ship + monitor reframe.
- **84-CONTEXT.md `<data-summary>`** — the corrected harvest-week data (12 events; supersedes the ROADMAP entry's "11 events" figure). ROADMAP.md is **NOT amended** in this phase per user choice (the historical record of the reframe decision stands; this CONTEXT.md / VERIFICATION.md is the corrected forward-going source).
- **84-RESEARCH.md §D-11 Resolution** — direct `gstplaybin3.c` source inspection on master branch (2026-05-24) FALSIFIED the playbin3 mid-session-write premise (evidence A1: `gst_play_bin3_set_property` for `PROP_BUFFER_DURATION` does NOT propagate to active uridecodebin3). This is why the D-11 implementation MANDATORILY used the fallback "stage at cycle_close, apply at next URI bind" shape rather than mid-session `set_property` writes. The fallback shape was authorized by CONTEXT D-11 specifically for this case.

---

_Verified: 2026-05-24_
_Verifier: Claude Code (gsd-executor running Plan 84-04)_
