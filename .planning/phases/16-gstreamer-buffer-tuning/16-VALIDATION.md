---
phase: 16
slug: gstreamer-buffer-tuning
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-03
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (127 tests passing) |
| **Config file** | none — pytest discovers via pyproject.toml |
| **Quick run command** | `python3 -m pytest tests/test_player_buffer.py tests/test_player_tag.py -q` |
| **Full suite command** | `python3 -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_player_buffer.py tests/test_player_tag.py -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 0 | STREAM-01 | unit | `python3 -m pytest tests/test_player_buffer.py -q` | ❌ W0 | ⬜ pending |
| 16-01-02 | 01 | 1 | STREAM-01 | unit | `python3 -m pytest tests/test_player_buffer.py -q` | ❌ W0 | ⬜ pending |
| 16-01-03 | 01 | 1 | STREAM-01 | unit | `python3 -m pytest tests/test_player_buffer.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_player_buffer.py` — stubs/tests for STREAM-01 (buffer property values, constants existence)

*Existing test infrastructure (`pytest`, `tests/`) covers all other needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ShoutCast stream plays 5+ min without audible drop-outs on 320 kbps | STREAM-01 (criteria 1) | Cannot simulate live network streaming in automated tests | Play a 320 kbps ShoutCast stream (e.g. AudioAddict hi quality) for 5+ min; listen for buffering/dropout artifacts |
| YouTube stream continues to play correctly after changes | STREAM-01 (criteria 3) | mpv subprocess not testable via GStreamer mocks | Play a YouTube live station before and after the change; confirm unaffected |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
