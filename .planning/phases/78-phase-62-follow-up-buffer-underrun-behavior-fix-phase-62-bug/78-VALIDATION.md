---
phase: 78
slug: phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-17
---

# Phase 78 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `78-RESEARCH.md` §Validation Architecture (researcher-derived).
> **Scope: Commit A (harvest infrastructure) only.** Commit B (the actual buffer-tuning fix) gets its own VALIDATION.md update in the second planning pass after ~1 week of harvested log samples.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (+ pytest-qt for Qt tests) — pinned in dev deps |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_buffer_events_log.py tests/test_player_underrun_count.py tests/test_main_window_underrun.py tests/test_fake_player_signal_parity.py -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~2s quick / ~30s full (local) |

---

## Sampling Rate

- **After every task commit:** Run the quick command above.
- **After every plan wave:** Run the full suite command above.
- **Before `/gsd:verify-work`:** Full suite must be green; the harvest-week instrumentation must be live in the user's daily-use sessions.
- **Max feedback latency:** ~2 seconds (quick command).

---

## Per-Task Verification Map

| Behavior ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| B-78A-01 | 01 | 0 | BUG-09 SC#3 (file sink — handler attach) | T-78A-DoS-disk (V7) | RotatingFileHandler attached to `musicstreamer.player` with `maxBytes=1_048_576`, `backupCount=3`, path = `paths.buffer_events_log_path()` | unit | `uv run pytest tests/test_buffer_events_log.py::test_handler_attached_to_player_logger -x` | ❌ Wave 0 | ⬜ pending |
| B-78A-02 | 01 | 0 | BUG-09 SC#3 (file sink — emit) | — | INFO `buffer_underrun ...` record reaches the file (single emit → single line) | unit | `uv run pytest tests/test_buffer_events_log.py::test_emit_writes_line_to_file -x` | ❌ Wave 0 | ⬜ pending |
| B-78A-03 | 01 | 0 | BUG-09 SC#3 (file sink — rotation) | T-78A-DoS-disk (V7) | At >1MB, `buffer-events.log.1` appears; `.4` never created | unit | `uv run pytest tests/test_buffer_events_log.py::test_rotation_at_1mb tests/test_buffer_events_log.py::test_never_creates_backup_4 -x` | ❌ Wave 0 | ⬜ pending |
| B-78A-04 | 01 | 0 | BUG-09 SC#3 (file sink — idempotent install) | T-78A-DoS-fd (V7) | Calling install twice does NOT double the handler count | unit | `uv run pytest tests/test_buffer_events_log.py::test_install_is_idempotent -x` | ❌ Wave 0 | ⬜ pending |
| B-78A-05 | 01 | 0 | BUG-09 SC#3 (file sink — propagate sanity) | — | Both stderr AND file receive the same INFO record (propagate=True path) | unit | `uv run pytest tests/test_buffer_events_log.py::test_record_reaches_both_sinks -x` | ❌ Wave 0 | ⬜ pending |
| B-78A-06 | 01 | 0 | BUG-09 SC#3 (path helper) | — | `paths.buffer_events_log_path()` returns `{data_dir}/buffer-events.log`; respects `_root_override` test hook | unit | `uv run pytest tests/test_paths.py::test_buffer_events_log_path -x` | ❌ Wave 0 (file exists; new test added) | ⬜ pending |
| B-78A-07 | 02 | 0 | BUG-09 SC#3 (counter init/increment) | — | `Player._underrun_event_count` initialized 0 in `__init__`; increments by 1 per `_on_underrun_cycle_closed` call | unit | `uv run pytest tests/test_player_underrun_count.py::test_count_starts_at_zero tests/test_player_underrun_count.py::test_count_increments_per_close -x` | ❌ Wave 0 | ⬜ pending |
| B-78A-08 | 02 | 0 | BUG-09 SC#3 (counter — all outcomes) | — | Counter increments on EVERY outcome (`recovered` / `failover` / `stop` / `pause` / `shutdown`) | unit | `uv run pytest tests/test_player_underrun_count.py::test_count_increments_for_all_outcomes -x` | ❌ Wave 0 | ⬜ pending |
| B-78A-09 | 02 | 0 | BUG-09 SC#3 (Signal declaration + emit) | — | `underrun_count_changed = Signal(int)` declared at class scope; emits from `_on_underrun_cycle_closed` with the new count value | unit | `uv run pytest tests/test_player_underrun_count.py::test_signal_emits_with_count_value -x` | ❌ Wave 0 | ⬜ pending |
| B-78A-10 | 02 | 0 | INFRA-01 (drift-guard parity) | — | `tests/_fake_player.py` mirrors `underrun_count_changed = Signal(int)` next to existing `underrun_recovery_started` | drift-guard | `uv run pytest tests/test_fake_player_signal_parity.py -x` | ✅ exists (passes once parity is added) | ⬜ pending |
| B-78A-11 | 03 | 0 | BUG-09 SC#3 (UI row presence) | — | `NowPlayingPanel._build_stats_widget` produces a `QFormLayout` with an `Underruns` row; default value text "0" | unit | `uv run pytest tests/test_now_playing_panel.py::test_underrun_count_row_present -x` | ❌ Wave 0 (file exists; new test added) | ⬜ pending |
| B-78A-12 | 03 | 0 | BUG-09 SC#3 (UI wiring end-to-end) | — | `MainWindow.__init__` connects `Player.underrun_count_changed` → `NowPlayingPanel.set_underrun_count`; emit updates label text | integration | `uv run pytest tests/test_main_window_underrun.py::test_count_changed_updates_stats_row -x` | ❌ Wave 0 (file exists; new test added) | ⬜ pending |
| B-78A-13 | 01 | 0 | Phase 62 / Pitfall 5 invariant (regression lock) | — | `__main__.py` still has `basicConfig(level=logging.WARNING)`; per-logger INFO escalation preserved | source-grep | `uv run pytest tests/test_main_window_underrun.py::test_main_module_sets_player_logger_to_info -x` | ✅ exists (already covers Pitfall 5) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_buffer_events_log.py` — new file; covers file-sink layer (handler attachment, path, rotation, idempotency, propagate sanity check). Pattern template: `tests/test_oauth_log.py`.
- [ ] `tests/test_player_underrun_count.py` — new file; covers counter init / increment-per-outcome / Signal emission.
- [ ] `tests/test_paths.py::test_buffer_events_log_path` — new test in existing file.
- [ ] `tests/test_now_playing_panel.py::test_underrun_count_row_present` — new test in existing file.
- [ ] `tests/test_main_window_underrun.py::test_count_changed_updates_stats_row` — new test in existing file.
- [ ] `tests/_fake_player.py` parity edit — add `underrun_count_changed = Signal(int)` adjacent to `underrun_recovery_started = Signal()` at line 69.

*Framework install: not needed — `pytest` + `pytest-qt` already in dev deps.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Harvest week (real-world A/B baseline) | BUG-09 SC#3 — pre-fix baseline | Requires daily-use environment for ~1 week to accumulate real samples. No CI substitute is meaningful at this stage; Commit A's only job is to make harvest possible. | After Commit A ships, run MusicStreamer via the `.desktop` entry for ~1 week of normal listening. Verify `~/.local/share/musicstreamer/buffer-events.log` accumulates `buffer_underrun ...` lines. Verify the `Underruns: {N}` row in stats-for-nerds increments live. Sign-off = a populated log file + meaningful sample count noted in `78-VERIFICATION.md`. SC #3 closure itself is deferred to Commit B's verification pass. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s (quick command estimated ~2s)
- [ ] `nyquist_compliant: true` set in frontmatter after planner sign-off

**Approval:** pending
