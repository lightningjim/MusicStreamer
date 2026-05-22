---
phase: 82
slug: twitch-only-station-still-tries-to-play-youtube-stream-first
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-21
---

# Phase 82 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (project standard; see `pyproject.toml` `[tool.pytest.ini_options]`) |
| **Config file** | `pyproject.toml` (pytest config inline) |
| **Quick run command** | `uv run pytest tests/test_repo.py tests/test_player.py tests/test_stream_picker.py -q` |
| **Full suite command** | `uv run pytest -q --tb=short` |
| **Estimated runtime** | ~0.5–2s (quick) · ~21s (full suite, 1670+ tests) |

---

## Sampling Rate

- **After every task commit:** Run quick command (above) — covers Repo + Player + UI stream picker
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green (excluding pre-existing `test_hamburger_menu_actions` and Win32 SMTC flakes documented in Phase 81 VERIFICATION.md)
- **Max feedback latency:** 2 seconds per task

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD by planner | TBD | TBD | D-01..D-08 | T-82-00 (no new threats) | preferred_stream_id round-trips through Repo and is honored by Player.play() | unit + integration | `uv run pytest tests/test_repo.py tests/test_player.py tests/test_stream_picker.py -q` | ✅ (existing) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Per-task rows will be filled by the planner once PLAN.md tasks are defined; this VALIDATION.md is the strategy contract that constrains what planner can defer or skip.*

---

## Wave 0 Requirements

- [x] `tests/test_repo.py` — exists; Phase 82 will append migration + preferred_stream_id round-trip tests
- [x] `tests/test_player.py` — exists; Phase 82 will append head-of-queue + failover regression tests
- [x] `tests/test_stream_picker.py` — exists; Phase 82 will append `_on_stream_selected` persistence test (and add `set_preferred_stream` no-op to FakeRepo if needed)
- [x] `tests/test_now_playing_panel.py` — exists; FakeRepo may need `set_preferred_stream` no-op added to prevent pre-existing test AttributeError regressions

*Existing infrastructure covers all phase requirements. No new test files required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-world Lofi Girl repro (user-reported) | D-01 + D-03 | Requires live YT-resolution-failure path + Twitch stream | 1) Start app, pick Lofi Girl from list. 2) Open dropdown, select Twitch. 3) Pause player. 4) Resume — confirm Twitch plays (not YT). 5) Restart app, re-pick Lofi Girl — confirm Twitch is still selected and plays. |
| Dropdown survives station re-click | D-03 (all entry points) | Visual confirmation that station-list re-activation honors sticky pick | After picking Twitch on Lofi Girl, click a different station, then click Lofi Girl again — confirm Twitch plays, not YT. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (none — all test files exist)
- [ ] No watch-mode flags
- [ ] Feedback latency < 2s per task (quick command), < 25s full suite
- [ ] `nyquist_compliant: true` set in frontmatter (planner sets this after Per-Task Verification Map is filled)

**Approval:** pending (planner-filled per-task map blocks approval)
