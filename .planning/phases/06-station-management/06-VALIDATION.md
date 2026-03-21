---
phase: 06
slug: station-management
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-21
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none — existing pytest setup |
| **Quick run command** | `uv run --with pytest pytest tests/ -q` |
| **Full suite command** | `uv run --with pytest pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --with pytest pytest tests/ -q`
- **After every plan wave:** Run `uv run --with pytest pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | MGMT-01 | unit | `uv run --with pytest pytest tests/test_station_mgmt.py -q` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | MGMT-01 | unit | `uv run --with pytest pytest tests/test_station_mgmt.py -q` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | MGMT-02 | unit | `uv run --with pytest pytest tests/test_yt_thumbnail.py -q` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 1 | ICY-01 | unit | `uv run --with pytest pytest tests/test_icy_override.py -q` | ❌ W0 | ⬜ pending |
| 06-03-02 | 03 | 1 | ICY-01 | unit | `uv run --with pytest pytest tests/test_icy_override.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_station_mgmt.py` — stubs for MGMT-01 (delete station, blocked-if-playing guard)
- [ ] `tests/test_yt_thumbnail.py` — stubs for MGMT-02 (YT URL detection, thumbnail fetch)
- [ ] `tests/test_icy_override.py` — stubs for ICY-01 (icy_disabled persists, title suppressed)

*Existing infrastructure (pytest via uv) covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Spinner visible during thumbnail fetch | MGMT-02 | Requires GTK4 UI rendering | Open edit dialog, enter YT URL, tab out — spinner should appear in art slot |
| Delete dialog blocked when playing | MGMT-01 | Requires live GStreamer pipeline | Play a station, open edit dialog, click Delete — should show error, not confirmation |
| ICY title suppressed during playback | ICY-01 | Requires live GStreamer stream | Enable ICY override, play station — title label should show station name, not ICY data |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
