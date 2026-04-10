---
phase: 27
slug: add-multiple-streams-per-station-for-backup-round-robin-and
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-08
---

# Phase 27 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — existing test infrastructure |
| **Quick run command** | `uv run --with pytest pytest tests/ -x -q` |
| **Full suite command** | `uv run --with pytest pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --with pytest pytest tests/ -x -q`
- **After every plan wave:** Run `uv run --with pytest pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 27-01-01 | 01 | 1 | D-01 | — | N/A | unit | `uv run --with pytest pytest tests/ -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_streams.py` — stubs for stream CRUD, migration, quality tiers
- [ ] Existing `tests/` infrastructure covers shared fixtures

*Existing infrastructure covers base requirements; new test file needed for stream-specific tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Streams sub-dialog opens from editor | D-03 | GTK UI interaction | Open station editor, click "Manage Streams", verify dialog appears |
| Stream reorder persists | D-04 | GTK UI interaction | Reorder streams via up/down, close and reopen, verify order persists |
| Global quality preference selects correct stream | D-06 | End-to-end playback | Set preferred quality, play station with multiple streams, verify correct stream plays |
| AA import creates multi-quality streams | D-07 | Requires AA API key | Import AA channels, verify 3 streams per station in editor |
| Radio-Browser attach-to-existing | D-08/D-09 | Discovery dialog interaction | Search Radio-Browser, find duplicate, attach to existing station |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
