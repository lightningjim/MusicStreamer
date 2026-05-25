---
phase: 55
slug: edit-station-preserves-section-state
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-01
---

# Phase 55 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=7 with `pytest-qt>=4` |
| **Config file** | `pyproject.toml` (test config), `musicstreamer/tests/conftest.py` (sets `QT_QPA_PLATFORM=offscreen`) |
| **Quick run command** | `pytest musicstreamer/tests/test_station_list_panel.py -x -q` |
| **Full suite command** | `pytest musicstreamer/tests -q` |
| **Estimated runtime** | ~10 seconds (panel-only); ~60 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `pytest musicstreamer/tests/test_station_list_panel.py -x -q`
- **After every plan wave:** Run `pytest musicstreamer/tests -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~10s panel, ~60s full

---

## Per-Task Verification Map

> Populated by the planner. Every `<task>` in PLAN.md must have either an `<automated>` verify command (per-task or via the plan's wave verification) or an explicit Wave 0 stub dependency listed in the task's acceptance criteria. Manual UAT is documented in the "Manual-Only Verifications" section below.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| _to be filled by planner — one row per task in 55-*-PLAN.md_ | | | BUG-06 | — | N/A (UI behavior fix) | unit/integration (pytest-qt) | `pytest musicstreamer/tests/test_station_list_panel.py::<test_name> -x -q` | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `musicstreamer/tests/test_station_list_panel.py` — extend with test stubs covering:
  - SC #1: previously-expanded provider stays expanded after `refresh_model()` triggered by save
  - SC #2: previously-collapsed provider stays collapsed after `refresh_model()` triggered by save
  - SC #3: fresh dialog launch starts collapsed (regression-lock — no expansion is *added* by the fix at construction time)
  - D-04: under an active filter, refresh-after-save preserves manual per-group expansion (does NOT call `_sync_tree_expansion()`)
  - D-05 regression-lock: each of the four filter-change handlers (`_on_search_changed`, `_on_provider_chip_clicked`, `_on_tag_chip_clicked`, `_clear_all_filters`) still calls `_sync_tree_expansion()`
  - D-06: a brand-new provider group introduced by the save defaults to expanded
  - D-07: an existing provider group whose station moved in/out of it preserves its captured manual state
  - Filtered-out provider guard: a previously-expanded provider that is filtered out post-save does not crash the restore loop
- [ ] `musicstreamer/tests/conftest.py` — no changes required (offscreen platform already configured)
- [ ] `pytest-qt` install — already present in `pyproject.toml`; no install task needed

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end UX feel of "save doesn't shuffle my tree" | BUG-06 (SC #1, #2) | The user-visible promise is a perceived absence of motion — automated tests prove the state vector preserves, but a human eye confirms there is no flicker, no scroll jump, and no visual reset on save | 1. Launch app. 2. Expand a subset of provider groups in the station list. 3. Right-click a station → Edit → change name → Save. 4. Confirm the same provider groups remain expanded with no flicker. 5. Repeat with a search filter active. 6. Repeat: collapse all, edit, confirm none expand. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (Wave 0 here is "extend `test_station_list_panel.py`")
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
