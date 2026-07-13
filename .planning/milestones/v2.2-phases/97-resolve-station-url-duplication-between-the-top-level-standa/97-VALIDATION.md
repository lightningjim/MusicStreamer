---
phase: 97
slug: resolve-station-url-duplication-between-the-top-level-standa
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-23
---

# Phase 97 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9+ with pytest-qt |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py tests/test_repo.py -x --tb=short` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -x --tb=short` |
| **Estimated runtime** | quick ~30–90s; full suite >600s (scope it) |

> NOTE: run with `.venv/bin/python` — system `python3` lacks `PySide6.QtWidgets` and yields false failures.

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/test_edit_station_dialog.py tests/test_repo.py -x --tb=short`
- **After every plan wave:** Run the full suite scoped to modified-file tests (add `tests/test_url_helpers.py tests/test_aa_siblings.py tests/test_player_*.py` as those areas are touched)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~90 seconds (quick run)

---

## Per-Task Verification Map

| Behavior | Test Type | Automated Command | File Exists | Status |
|----------|-----------|-------------------|-------------|--------|
| `canonical_stream_id` column added idempotently | unit/migration | `.venv/bin/python -m pytest tests/test_repo.py -k canonical_stream_id -x` | ❌ W0 | ⬜ pending |
| Backfill defaults canonical to position-1 stream | unit/migration | `.venv/bin/python -m pytest tests/test_repo.py -k canonical_backfill -x` | ❌ W0 | ⬜ pending |
| `set_canonical_stream` round-trip | unit | `.venv/bin/python -m pytest tests/test_repo.py -k canonical -x` | ❌ W0 | ⬜ pending |
| FK ON DELETE SET NULL when canonical stream deleted | unit/migration | `.venv/bin/python -m pytest tests/test_repo.py -k canonical_on_delete -x` | ❌ W0 | ⬜ pending |
| Dialog opens with no `url_edit` widget (D-01 drift-guard) | unit/UI | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -k "no_url_edit or url_edit_widget" -x` | ❌ W0 | ⬜ pending |
| Canonical marker defaults to first row (D-04) | unit/UI | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -k canonical -x` | ❌ W0 | ⬜ pending |
| Metadata reads canonical row live, unsaved (D-02) | unit/UI | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -k canonical_live -x` | ❌ W0 | ⬜ pending |
| `canonical_stream_id` persisted on Save | unit/UI | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -k save_canonical -x` | ❌ W0 | ⬜ pending |
| Canonical stays pinned after reorder, not positional (D-04) | unit/UI | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -k reorder_canonical -x` | ❌ W0 | ⬜ pending |
| Auto-create primary row on empty/new station (D-03) | unit/UI | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -k "auto_row or primary_row" -x` | ❌ W0 | ⬜ pending |
| `canonical_url()` resolves FK, falls back to position 1 | unit | `.venv/bin/python -m pytest tests/test_url_helpers.py -k canonical -x` | ❌ W0 | ⬜ pending |
| AA siblings use `canonical_url`, not `streams[0]` (D-07) | unit | `.venv/bin/python -m pytest tests/test_aa_siblings.py -k canonical -x` | ❌ W0 | ⬜ pending |
| Playback still uses `preferred_stream_id` (D-05) | unit | `.venv/bin/python -m pytest tests/test_player_*.py -x --tb=short` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_repo.py` — `test_canonical_stream_id_migration_idempotent` (mirror `test_preferred_stream_id_migration_idempotent`)
- [ ] `tests/test_repo.py` — `test_canonical_stream_id_backfill_defaults_position1`
- [ ] `tests/test_repo.py` — `test_canonical_stream_id_default_none_on_fresh_station`
- [ ] `tests/test_repo.py` — `test_set_canonical_stream_round_trip`
- [ ] `tests/test_repo.py` — `test_canonical_stream_id_on_delete_set_null_when_stream_deleted`
- [ ] `tests/test_edit_station_dialog.py` — `test_url_edit_widget_does_not_exist` (D-01 drift-guard)
- [ ] `tests/test_edit_station_dialog.py` — `test_canonical_marker_defaults_to_row_0`
- [ ] `tests/test_edit_station_dialog.py` — `test_canonical_marker_stays_pinned_after_reorder`
- [ ] `tests/test_edit_station_dialog.py` — `test_save_persists_canonical_stream_id`
- [ ] `tests/test_edit_station_dialog.py` — `test_metadata_reads_canonical_cell_live` (D-02)
- [ ] `tests/test_edit_station_dialog.py` — `test_dirty_state_captures_canonical_url_not_url_edit`
- [ ] `tests/test_url_helpers.py` — `test_canonical_url_resolves_fk_with_position1_fallback`
- [ ] `tests/test_aa_siblings.py` — sibling-detection test asserting canonical URL is matched

*Plus: update existing `url_edit`-referencing tests (~14 sites in test_edit_station_dialog.py) to drive the canonical table cell instead — see RESEARCH.md "Existing tests that will break."*

---

## Manual-Only Verifications

| Behavior | Why Manual | Test Instructions |
|----------|------------|-------------------|
| Canonical marker visual affordance (star/radio) renders + single-selects in the live app | Widget appearance/feel not asserted by pytest-qt cleanly | Open Edit Station dialog on a multi-stream station; confirm exactly one canonical control is checked, clicking another moves it, reorder leaves it pinned |
| Avatar/sibling/scan-toggle react live as the canonical URL cell is typed (D-02) end-to-end | Cross-widget live wiring best confirmed visually | Edit the canonical row's URL to a twitch.tv/YouTube URL; confirm provider derive / channel-scan field / avatar react before Save |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
