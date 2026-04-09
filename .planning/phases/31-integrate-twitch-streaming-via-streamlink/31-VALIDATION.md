---
phase: 31
slug: integrate-twitch-streaming-via-streamlink
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 31 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (detected via pyproject.toml) |
| **Config file** | pyproject.toml |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 31-01-01 | 01 | 0 | — | — | N/A | unit | `pytest tests/test_twitch.py -x -q` | ❌ W0 | ⬜ pending |
| 31-01-02 | 01 | 1 | — | T-31-01 | URL detection branch prevents non-Twitch URLs reaching streamlink | unit | `pytest tests/test_twitch.py::test_twitch_url_detection -x -q` | ❌ W0 | ⬜ pending |
| 31-01-03 | 01 | 1 | — | — | N/A | unit | `pytest tests/test_twitch.py::test_play_twitch_live -x -q` | ❌ W0 | ⬜ pending |
| 31-01-04 | 01 | 1 | — | — | N/A | unit | `pytest tests/test_twitch.py::test_play_twitch_offline -x -q` | ❌ W0 | ⬜ pending |
| 31-01-05 | 01 | 1 | — | — | N/A | unit | `pytest tests/test_twitch.py::test_re_resolve_on_error -x -q` | ❌ W0 | ⬜ pending |
| 31-01-06 | 01 | 1 | — | — | N/A | unit | `pytest tests/test_twitch.py::test_path_includes_local_bin -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_twitch.py` — stubs for all Twitch behaviors (URL detection, live resolution, offline handling, re-resolve, PATH setup)

*Existing test infrastructure (pytest, conftest) covers all other phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Twitch live stream audio plays through speakers | D-01 | Requires live Twitch channel + audio hardware | 1. Add a Twitch station (e.g., twitch.tv/shroud when live) 2. Click play 3. Verify audio |
| Toast "channel is offline" appears | D-05 | Requires GTK runtime + offline Twitch channel | 1. Add a Twitch station with offline channel 2. Click play 3. Verify toast |
| Re-resolve on long session (URL expiry) | D-02 | Requires 6+ hour session | 1. Play Twitch stream 2. Wait for HLS URL to expire 3. Verify auto-reconnect |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
