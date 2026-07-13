---
phase: 96
slug: manual-refresh-of-yellow-brick-cinema-provider-with-what-is
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-20
---

# Phase 96 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `96-RESEARCH.md` § Validation Architecture. Requirement IDs are the
> CONTEXT.md decisions D-01..D-10 (no REQ-IDs mapped in ROADMAP).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | `pyproject.toml` (project root) |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_repo.py -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -x --ignore=tests/integration -q` |
| **Estimated runtime** | quick ~15s; full >600s (scope per-wave) |

> Must use `.venv/bin/python` — system `python3` lacks `PySide6.QtWidgets` and yields false failures.

---

## Sampling Rate

- **After every task commit:** `.venv/bin/python -m pytest tests/test_repo.py -x -q` (plus the new-file test once it exists)
- **After every plan wave:** `.venv/bin/python -m pytest tests/ -x --ignore=tests/integration -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~15s (quick) per task

---

## Per-Decision Verification Map

| Decision | Behavior | Test Type | Automated Command | File Exists |
|----------|----------|-----------|-------------------|-------------|
| D-01 | `live_url_syncs_from_channel` column; DEFAULT 0; idempotent migration | unit | `pytest tests/test_repo.py::test_live_url_syncs_from_channel_migration_idempotent -x` | ❌ W0 |
| D-01 | `set_live_url_syncs_from_channel` round-trips | unit | `pytest tests/test_repo.py::test_live_url_syncs_from_channel_round_trip -x` | ❌ W0 |
| D-01 | `Station.live_url_syncs_from_channel` loaded by get/list_stations | unit | `pytest tests/test_repo.py::test_station_live_flag_loaded_from_db -x` | ❌ W0 |
| D-02 | Checkbox enabled for youtube.com, disabled for twitch.tv/other | unit | `pytest tests/test_edit_station_dialog.py::test_live_resync_checkbox_gating -x` | ❌ W0 |
| D-03 | `live_url_title_anchor` column; nullable; idempotent | unit | `pytest tests/test_repo.py::test_live_url_title_anchor_migration_idempotent -x` | ❌ W0 |
| D-03 | `set_live_url_title_anchor` persists + loaded by get_station | unit | `pytest tests/test_repo.py::test_live_url_title_anchor_round_trip -x` | ❌ W0 |
| D-04 | `providers.channel_scan_url` column; nullable; idempotent | unit | `pytest tests/test_repo.py::test_provider_channel_scan_url_migration_idempotent -x` | ❌ W0 |
| D-04 | `_TreeNode` carries `provider_id`; provider context-menu branch fires | unit | `pytest tests/test_station_tree_model.py::test_tree_node_carries_provider_id -x` | ❌ W0 |
| D-05 | `_build_row_suggestions` pre-orders by anchor similarity, NO auto-apply | unit | `pytest tests/test_live_refresh_dialog.py::test_suggestions_pre_order_no_auto_apply -x` | ❌ W0 |
| D-06 | Update remap: `update_stream` new URL; other fields preserved | unit | `pytest tests/test_live_refresh_dialog.py::test_apply_remap_preserves_metadata -x` | ❌ W0 |
| D-06 | `list_flagged_stations_for_provider` returns only flagged | unit | `pytest tests/test_repo.py::test_list_flagged_stations_for_provider -x` | ❌ W0 |
| D-07 | Drop calls `delete_station`; add calls `insert_station` (flag=True) | unit | `pytest tests/test_live_refresh_dialog.py::test_apply_drop_and_add_actions -x` | ❌ W0 |
| D-08 | Editable name field pre-populated per action type | unit | `pytest tests/test_live_refresh_dialog.py::test_name_field_prepopulation -x` | ❌ W0 |
| D-09 | Scan off UI thread (QThread); dialog populated via Signal on main thread | unit | `pytest tests/test_live_refresh_dialog.py::test_scan_worker_uses_qthread -x` | ❌ W0 |
| D-10 | Unresolved flagged untouched; drops/adds unchecked by default | unit | `pytest tests/test_live_refresh_dialog.py::test_conservative_defaults -x` | ❌ W0 |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky — planner assigns Task IDs/Waves.*

---

## Wave 0 Requirements

- [ ] `tests/test_live_refresh_dialog.py` — NEW file; covers D-05/D-06/D-07/D-08/D-09/D-10
- [ ] `tests/test_repo.py` additions — D-01/D-03/D-04 migration idempotency + round-trip + `list_flagged_stations_for_provider`
- [ ] `tests/test_station_tree_model.py` additions — `_TreeNode.provider_id` + provider context-menu detection
- [ ] `tests/test_edit_station_dialog.py` additions — D-02 flag gating

---

## Manual-Only Verifications

| Behavior | Decision | Why Manual | Test Instructions |
|----------|----------|------------|-------------------|
| Confirm-summary shown before Apply commits | D-10 | Visual confirmation of the review-and-confirm gate | Open Live Refresh dialog, stage changes, observe summary line before clicking Apply |
| Real YBC channel re-sync end-to-end | D-01..D-10 | Requires live YouTube channel with churned stream IDs | Flag a real YBC station, right-click its provider → Refresh live streams, scan, manually map a remap, Apply; confirm URL updated in place and station plays |

---

## Validation Sign-Off

- [ ] All decisions have `<automated>` verify or a justified Manual-Only entry
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (4 test files above)
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s (quick)
- [ ] `nyquist_compliant: true` set in frontmatter (set by plan-checker/planner)

**Approval:** pending
