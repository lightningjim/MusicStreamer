---
phase: 33
slug: fix-yt-video-playback-delay-until-all-streams-failed-toast
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-10
---

# Phase 33 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (with `unittest.mock`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run --with pytest pytest tests/test_player_failover.py -x` |
| **Full suite command** | `uv run --with pytest pytest` |
| **Estimated runtime** | Quick ~2s / Full ~12s (255 tests) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --with pytest pytest tests/test_player_failover.py -x`
- **After every plan wave:** Run `uv run --with pytest pytest tests/test_player_failover.py tests/test_twitch_playback.py tests/test_player_buffer.py -x`
- **Before `/gsd-verify-work`:** Full suite must be green (`uv run --with pytest pytest`)
- **Max feedback latency:** ~2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 33-01-01 | 01 | 1 | FIX-07 (a–c, e) | — | N/A | unit | `uv run --with pytest pytest tests/test_player_failover.py -x` | ✅ | ⬜ pending |
| 33-01-02 | 01 | 2 | FIX-07 (a) | — | N/A | unit | `uv run --with pytest pytest tests/test_player_failover.py::test_yt_premature_exit_does_not_failover_before_15s -x` | ❌ W0 | ⬜ pending |
| 33-01-03 | 01 | 2 | FIX-07 (b) | — | N/A | unit | `uv run --with pytest pytest tests/test_player_failover.py::test_yt_alive_at_window_close_succeeds -x` | ❌ W0 | ⬜ pending |
| 33-01-04 | 01 | 2 | FIX-07 (c) | — | N/A | unit | `uv run --with pytest pytest tests/test_player_failover.py::test_cookie_retry_reseeds_yt_window -x` | ❌ W0 | ⬜ pending |
| 33-01-05 | 01 | 2 | FIX-07 (e) | — | N/A | unit | `uv run --with pytest pytest tests/test_player_failover.py::test_cancel_clears_yt_attempt_ts -x` | ❌ W0 | ⬜ pending |
| 33-02-01 | 02 | 1 | FIX-07 (d) | — | N/A | manual UAT | See Manual-Only Verifications | ✅ | ⬜ pending |
| 33-02-02 | 02 | 1 | FIX-07 regression | — | N/A | unit | `uv run --with pytest pytest tests/test_twitch_playback.py tests/test_player_failover.py -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_player_failover.py` — add 4 new test functions for FIX-07 (a, b, c, e) using existing `make_player()` helper and `patch("musicstreamer.player.time")`, `patch("musicstreamer.player.GLib")` patterns at line 343.
- [ ] No new test file needed — `test_player_failover.py` is the established home.
- [ ] No framework install — pytest already drives 255 existing tests.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| "Connecting…" toast fires immediately on play and play_stream | FIX-07 (d) | `MainWindow` has no existing unit test harness; constructing a live Adw.ApplicationWindow in pytest requires a GTK event loop which is out of scope for this phase | 1. Launch app (`uv run musicstreamer`). 2. Click any station. 3. Observe: "Connecting…" toast appears immediately, auto-dismisses within ~4s. 4. Click a different stream via stream-picker popover. 5. Observe: "Connecting…" toast fires again. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
