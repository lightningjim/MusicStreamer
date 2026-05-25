---
phase: 84
slug: bug-09-commit-b-buffer-tuning-behavior-fix-reframed-from-str
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-24
plans: 4
---

# Phase 84 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. All Wave 1 production changes have at least one Wave 0 RED test driving them; the Wave 2 closure artifact is a markdown file with grep-gate acceptance criteria.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7+ with pytest-qt 4+ (PySide6) |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `uv run pytest tests/test_player_buffer.py tests/test_player_buffer_growth.py tests/test_playbin3_property_hygiene.py tests/test_now_playing_panel.py tests/test_main_window_underrun.py tests/test_fake_player_signal_parity.py -v` |
| **Full suite command** | `uv run pytest -q` (full project test suite) |
| **Estimated runtime** | quick ~15s; full ~60-90s |

---

## Sampling Rate

- **After every task commit:** Run the quick run command (the 6-file subset above — covers all Phase 84 contracts in ~15s).
- **After every plan wave:** Run the full suite to catch cross-cutting regressions (Phase 47.1 Buffer progressbar, Phase 62 cycle tracker, Phase 78 Underruns row + harvest infra, Phase 83 gapless preroll handoff).
- **Before `/gsd:verify-work`:** Full suite must be green.
- **Max feedback latency:** ~15 seconds for the quick subset.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 84-01-01 | 01 | 0 | BUG-09 | T-84-01 | constants test RED-on-current; FakePlayer parity STILL GREEN; no underscore property-name spellings introduced | unit | `uv run pytest tests/test_player_buffer.py tests/test_fake_player_signal_parity.py -x` | ✅ W0 | ⬜ pending |
| 84-01-02 | 01 | 0 | BUG-09 | T-84-04 | 9 RED tests in test_player_buffer_growth.py drive D-11 contracts (state machine + URI-bind apply ordering + reset semantics + no-spurious-Signal-at-baseline) | unit | `uv run pytest tests/test_player_buffer_growth.py -v` | ✅ W0 | ⬜ pending |
| 84-01-03 | 01 | 0 | BUG-09 | T-84-01, T-84-04 | source-grep gate banning playbin 1.x underscore spellings + flags\|0x100 regression-lock — GREEN on Wave 0 (lock-only, forward-looking) | unit | `uv run pytest tests/test_playbin3_property_hygiene.py -v` | ✅ W0 | ⬜ pending |
| 84-01-04 | 01 | 0 | BUG-09 | T-84-09 | 3 RED tests in test_now_playing_panel.py for 'Buf duration' row + slot; 1 RED test in test_main_window_underrun.py for wire (T-40-04 plain-text invariant preserved by mirroring set_underrun_count) | unit/integration | `uv run pytest tests/test_now_playing_panel.py tests/test_main_window_underrun.py -k "buffer_duration" -v` | ✅ W0 | ⬜ pending |
| 84-02-01 | 02 | 1 | BUG-09 | — | D-10 literal bump 30s / 20MB takes effect at first URI bind (uridecodebin3.new_source_handler reads playbin3 struct fields per RESEARCH §D-11) | unit | `uv run pytest tests/test_player_buffer.py -v` | ✅ W0 (RED→GREEN flip) | ⬜ pending |
| 84-02-02 | 02 | 1 | BUG-09 | T-84-03, T-84-04, T-84-05, T-84-06, T-84-07 | D-11 stage-and-apply state machine on Player; both URI-bind apply sites called BEFORE set_property('uri', ...); flags\|0x100 preserved; underscore property spellings banned; __main__.py byte-identical (Phase 62 Pitfall 5) | unit | `uv run pytest tests/test_player_buffer.py tests/test_player_buffer_growth.py tests/test_playbin3_property_hygiene.py tests/test_player_underrun_count.py tests/test_fake_player_signal_parity.py -v` | ✅ W0 (9 RED→GREEN flip + regression-clean) | ⬜ pending |
| 84-03-01 | 03 | 1 | BUG-09 | T-84-08, T-84-09 | D-12 'Buf duration' always-visible stats row; baseline 30s renders bare; adapted values get ' (adapted)' suffix; wrapper-level visibility unchanged (Pitfall 8); T-40-04 plain-text invariant preserved | unit/integration | `uv run pytest tests/test_now_playing_panel.py -k "buffer_duration or underrun_count_row or stats_widget" -v` | ✅ W0 (3 RED→GREEN flip) | ⬜ pending |
| 84-03-02 | 03 | 1 | BUG-09 | T-84-10 | D-12 MainWindow wire: bound-method DirectConnection (no lambda, no QueuedConnection); end-to-end emit→label-update within one event-loop spin | integration | `uv run pytest tests/test_main_window_underrun.py -v` | ✅ W0 (1 RED→GREEN flip + Phase 78 regression-clean) | ⬜ pending |
| 84-04-01 | 04 | 2 | BUG-09 | T-84-11, T-84-12 | 84-VERIFICATION.md exists with frontmatter `closure_model: ship-plus-monitor` + WAIVED gate language + 2-week monitor plan + 3 verbatim CONTEXT D-13 follow-up thresholds; SC #3 explicitly closed on ship commit | unit (grep gates) | `test -f .planning/phases/84-bug-09-commit-b-buffer-tuning-behavior-fix-reframed-from-str/84-VERIFICATION.md && grep -cE "WAIVED" $_ && grep -cE "reconnect.on.stall" $_` | ✅ W2 output | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_player_buffer_growth.py` — NEW; 9 tests stub for D-11 state machine + URI-bind apply ordering (Plan 01 Task 2).
- [x] `tests/test_playbin3_property_hygiene.py` — NEW; 3 tests for source-grep hygiene gate + flags|0x100 regression lock (Plan 01 Task 3).
- [x] `tests/test_player_buffer.py` — literal bump 10→30 / 10MB→20MB (Plan 01 Task 1).
- [x] `tests/_fake_player.py` — INFRA-01 parity: new `buffer_duration_changed = Signal(int)` mirror line (Plan 01 Task 1).
- [x] `tests/test_now_playing_panel.py` — +3 tests inline for D-12 row + slot (Plan 01 Task 4).
- [x] `tests/test_main_window_underrun.py` — +1 test inline for D-12 wire (Plan 01 Task 4).
- [x] No conftest.py edit — codebase convention per PATTERNS §S-6 (per-file helper duplication).
- [x] No new framework install (pytest + pytest-qt + PySide6 already pinned).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Post-ship 2-week monitor window (harvest-week-baseline-vs-post-ship comparison in `~/.local/share/musicstreamer/buffer-events.log`) | BUG-09 SC #3 (forward-looking guidance, NOT a closure prerequisite) | Requires real-world environmental conditions and 2 weeks of accumulated samples. The entire Phase 84 reframe predicate is that statistical sample size is too low for synthetic A/B. | After 14 days of normal daily-use post-ship: `wc -l ~/.local/share/musicstreamer/buffer-events.log* | tail -1`; compare against harvest-week baseline (12 events / 7 days, 5 long max 7389ms). If any follow-up trigger threshold from 84-VERIFICATION.md is met (≥3 long events with `min_percent=0`, OR any `recovered` event >10s, OR ≥1 `cause_hint=network` event), open follow-up phase for reconnect-on-stall evaluation. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every task is `<automated>`-instrumented).
- [x] Wave 0 covers all MISSING references (every Wave 1 production behavior has at least one RED Wave 0 test).
- [x] No watch-mode flags.
- [x] Feedback latency < 84s (quick subset ~15s).
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-05-24
