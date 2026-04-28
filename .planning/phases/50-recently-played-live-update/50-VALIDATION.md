---
phase: 50
slug: recently-played-live-update
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-27
---

# Phase 50 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-qt (existing project config) |
| **Config file** | `pyproject.toml` / `pytest.ini` (existing) |
| **Quick run command** | `pytest tests/test_station_list_panel.py tests/test_main_window_integration.py -x` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~30s quick / ~3min full |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_station_list_panel.py tests/test_main_window_integration.py -x`
- **After every plan wave:** Run `pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~30s

---

## Per-Task Verification Map

> Filled in by planner. One row per task with concrete test command and Wave-0 dependency status.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD-by-planner | — | — | BUG-01 | — | N/A | unit/integration | TBD | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_station_list_panel.py` — add `test_refresh_recent_updates_list` and `test_refresh_recent_does_not_touch_tree` (RED stubs for BUG-01).
- [ ] `tests/test_main_window_integration.py` — add `test_station_activated_refreshes_recent_list` (RED stub for BUG-01).
- [ ] If `FakeRepo` in either file does not yet support mutating `_recent` from `update_last_played`, extend it so `list_recently_played` returns updated data after activation. (Determined when planner reads the existing fakes.)

*Existing test infrastructure (pytest + pytest-qt + project conftest) covers all other concerns — no new fixtures, no framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual confirmation that the recently-played QListView updates within the same session | BUG-01 / SC #1, #2 | Pixel-level UI rendering is asserted in code via model contents; live-eye smoke check is still useful. | Launch app → click any station not currently in top-3 → confirm it jumps to row 0 of Recently Played within ~1 frame, with no provider tree collapse. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter (set by planner once Per-Task Verification Map is filled)

**Approval:** pending
