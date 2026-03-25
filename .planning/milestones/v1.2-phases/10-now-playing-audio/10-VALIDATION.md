---
phase: 10
slug: now-playing-audio
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pyproject.toml |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 0 | AUDIO-01 | unit | `pytest tests/test_player_volume.py -x -q` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 1 | NP-01 | manual | n/a — GTK widget requires display | N/A | ⬜ pending |
| 10-02-02 | 02 | 1 | AUDIO-01 | unit | `pytest tests/test_player_volume.py -x -q` | ❌ W0 | ⬜ pending |
| 10-02-03 | 02 | 1 | AUDIO-02 | unit | `pytest tests/test_repo.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_player_volume.py` — covers AUDIO-01 (`Player.set_volume` clamp + property set)

*Existing infrastructure covers all other phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Provider name shown inline next to station name | NP-01 | GTK label update requires display | Play a station with a provider assigned; verify label shows "Name · Provider" |
| No provider suffix when provider is empty/None | NP-01 | GTK label update requires display | Play a station with no provider; verify label shows only station name |
| Volume slider appears below stop button | AUDIO-01 | GTK widget layout requires display | Launch app; verify slider is visible in now-playing panel |
| Volume slider controls playback in real time | AUDIO-01 | Audio output requires display + speakers | Play a station; drag slider; verify volume changes |
| Volume persists on restart | AUDIO-02 | Requires app restart | Set volume to 40; quit; relaunch; verify slider shows 40 |
| Panel height stays ≤ 160px | UI-SPEC | Visual layout requires display | Verify now-playing panel does not expand beyond logo/art height |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
