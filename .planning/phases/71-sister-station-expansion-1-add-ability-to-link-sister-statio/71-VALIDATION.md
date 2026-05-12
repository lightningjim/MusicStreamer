---
phase: 71
slug: sister-station-expansion-1-add-ability-to-link-sister-statio
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
---

# Phase 71 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source of truth: 71-RESEARCH.md §Validation Architecture (lines 690-728).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 9 + pytest-qt >= 4 (existing) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) |
| **Quick run command** | `uv run --with pytest --with pytest-qt pytest tests/test_station_siblings.py tests/test_add_sibling_dialog.py -x --tb=short` |
| **Full suite command** | `uv run --with pytest --with pytest-qt pytest tests/ -x --tb=short -q` |
| **Estimated runtime** | ~2s quick / ~25s full (extrapolated from Phase 70 baseline: 399 tests, ~22s) |

---

## Sampling Rate

- **After every task commit:** Run quick command — `pytest tests/test_station_siblings.py tests/test_add_sibling_dialog.py -x --tb=short`
- **After every plan wave:** Run full suite command — `pytest tests/ -x --tb=short -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 25 seconds

---

## Per-Task Verification Map

Tasks are not yet enumerated — planner produces the wave/task breakdown next. The following table maps **CONTEXT.md decisions and merge-helper invariants** to their automated test entry. The planner fills in the `Task ID` + `Plan` + `Wave` columns when producing per-plan PLAN.md files; each plan's task will reference its row here.

| Decision / Invariant | Behavior | Test Type | Automated Command | File Exists | Status |
|----------------------|----------|-----------|-------------------|-------------|--------|
| D-05 | `station_siblings` table with CHECK(a_id < b_id) + UNIQUE(a_id, b_id) + ON DELETE CASCADE | unit | `pytest tests/test_station_siblings.py::test_schema_create_with_check_unique_cascade -x` | ❌ W0 | ⬜ pending |
| D-06 | `db_init` idempotent — call twice without error (Phase 47.2 / Phase 70 precedent) | unit | `pytest tests/test_station_siblings.py::test_db_init_idempotent_with_siblings_table -x` | ❌ W0 | ⬜ pending |
| D-07 | ZIP siblings round-trip by station name | unit | `pytest tests/test_settings_export.py::test_siblings_round_trip -x` | ❌ W0 | ⬜ pending |
| D-07 | Old ZIP (missing `siblings` key) → no error, defaults empty | unit | `pytest tests/test_settings_export.py::test_siblings_missing_key_defaults_empty -x` | ❌ W0 | ⬜ pending |
| D-07 | Unresolved sibling name on import is silently dropped | unit | `pytest tests/test_settings_export.py::test_siblings_unresolved_name_silently_dropped -x` | ❌ W0 | ⬜ pending |
| D-08 | ON DELETE CASCADE removes link rows when partner station deleted | unit | `pytest tests/test_station_siblings.py::test_cascade_on_station_delete -x` (requires `PRAGMA foreign_keys = ON` in fixture — Pitfall 3 in research) | ❌ W0 | ⬜ pending |
| D-01 | NowPlaying merged AA+manual siblings via shared `render_sibling_html` path | integration | `pytest tests/test_now_playing_panel.py::test_now_playing_shows_merged_siblings -x` | ❌ W0 | ⬜ pending |
| D-11 | `+ Add sibling` button present in EditStationDialog chip row | integration | `pytest tests/test_edit_station_dialog.py::test_add_sibling_button_present -x` | ❌ W0 | ⬜ pending |
| D-12 | AddSiblingDialog provider switch reloads station list | integration | `pytest tests/test_add_sibling_dialog.py::test_provider_switch_reloads_station_list -x` | ❌ W0 | ⬜ pending |
| D-13 | Picker excludes self + already-linked stations | integration | `pytest tests/test_add_sibling_dialog.py::test_self_excluded_from_list -x` + `::test_already_linked_excluded` | ❌ W0 | ⬜ pending |
| D-13 | OK button enabled only when one item is selected | integration | `pytest tests/test_add_sibling_dialog.py::test_ok_enabled_only_on_single_select -x` | ❌ W0 | ⬜ pending |
| D-14 | × button click calls `Repo.remove_sibling_link` and refreshes chip row | integration | `pytest tests/test_edit_station_dialog.py::test_x_click_calls_remove_sibling_link -x` | ❌ W0 | ⬜ pending |
| D-14 | × button click fires `sibling_toast` signal with `"Unlinked from {name}"` | integration | `pytest tests/test_edit_station_dialog.py::test_x_click_fires_unlinked_toast -x` | ❌ W0 | ⬜ pending |
| D-15 | AA-auto chip has NO × button | integration | `pytest tests/test_edit_station_dialog.py::test_aa_chip_has_no_x_button -x` | ❌ W0 | ⬜ pending |
| Merge layer | Dedup by station_id; AA wins on collision | unit | `pytest tests/test_station_siblings.py::test_merge_siblings_dedup_by_station_id -x` | ❌ W0 | ⬜ pending |
| Symmetric storage | `list_sibling_links` sees rows where station_id is either a_id or b_id | unit | `pytest tests/test_station_siblings.py::test_list_sibling_links_symmetric -x` | ❌ W0 | ⬜ pending |
| Idempotent CRUD | `add_sibling_link` is INSERT OR IGNORE — re-adding does not raise | unit | `pytest tests/test_station_siblings.py::test_add_sibling_link_idempotent -x` | ❌ W0 | ⬜ pending |
| Idempotent CRUD | `add_sibling_link` normalizes (smaller, larger) at boundary | unit | `pytest tests/test_station_siblings.py::test_add_sibling_link_normalizes_order -x` | ❌ W0 | ⬜ pending |
| T-40-04 invariant | RichText grep baseline does NOT increase | unit | `pytest tests/test_constants_drift.py::test_richtext_grep_baseline_unchanged -x` (extend existing module per Phase 60.3 precedent; baseline is current grep -c of `setTextFormat\|setHtml\|RichText` across `musicstreamer/`) | ❌ W0 | ⬜ pending |
| Navigation invariant | `sibling://{id}` link-scheme + `navigate_to_sibling = Signal(int)` preserved | integration | `pytest tests/test_edit_station_dialog.py::test_chip_click_emits_navigate_signal -x` | ❌ W0 | ⬜ pending |
| find_manual_siblings | Pure helper returns `list[tuple[provider_name, id, name]]` (compat with render_sibling_html) | unit | `pytest tests/test_station_siblings.py::test_find_manual_siblings_tuple_shape -x` | ❌ W0 | ⬜ pending |
| find_manual_siblings | Excludes current station's own id (mirrors find_aa_siblings line 122) | unit | `pytest tests/test_station_siblings.py::test_find_manual_siblings_excludes_self -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_station_siblings.py` — NEW. Covers schema, repo CRUD, CASCADE, idempotence, symmetric query, find_manual_siblings, merge dedup.
- [ ] `tests/test_add_sibling_dialog.py` — NEW. Covers AddSiblingDialog provider switch, search filter, exclusion of self + already-linked, OK gate, OK persists + closes, Don't Link dismisses.
- [ ] `tests/test_settings_export.py` — EXTEND. Add `test_siblings_round_trip`, `test_siblings_missing_key_defaults_empty`, `test_siblings_unresolved_name_silently_dropped`.
- [ ] `tests/test_edit_station_dialog.py` — EXTEND. Add chip row tests (× button presence rule, × click → remove_sibling_link + toast, AA chip no ×, navigate signal on name click, + Add sibling button presence).
- [ ] `tests/test_now_playing_panel.py` — EXTEND. Add `test_now_playing_shows_merged_siblings` (manual + AA stations merged into the one 'Also on:' line).
- [ ] `tests/test_constants_drift.py` — EXTEND. Add `test_richtext_grep_baseline_unchanged` per Phase 60.3 precedent.

`PRAGMA foreign_keys = ON` MUST be enabled in test fixtures that exercise CASCADE behavior (Pitfall 3 in 71-RESEARCH.md line 624). The existing `tests/test_repo.py` fixture pattern may not enable it — the planner verifies and adds the pragma to the new `test_station_siblings.py` conftest or per-test fixture.

---

## Manual-Only Verifications

| Behavior | Decision | Why Manual | Test Instructions |
|----------|----------|------------|-------------------|
| Linking "Classical Relaxation" + "Relaxing Classical" cross-provider (AA name-mismatch case) | CONTEXT specifics line 1 | Live AA library + cross-network playback validates the headline use case | 1) Open EditStationDialog on one of the pair. 2) Click `+ Add sibling`. 3) Pick the other provider, select the sister station, click `Link Station`. 4) Verify chip appears in 'Also on:' row. 5) Close + reopen dialog — chip persists. 6) Click partner chip name — switches to that station's editor. 7) Open NowPlaying for either station — 'Also on:' line shows the partner. |
| Linking SomaFM 3× Groove Salad set | CONTEXT specifics line 2 | Live SomaFM 3-variant case validates multi-link UX | 1) Open EditStationDialog on "Groove Salad". 2) Add "Classic Groove Salad" as sibling. 3) Re-open `+ Add sibling`, add "Groove Salad 2". 4) Verify both chips present. 5) Edit "Classic Groove Salad" → see Groove Salad in its row but NOT Groove Salad 2 (no transitive closure per CONTEXT D-04 out-of-scope). 6) Click × on one chip → unlink + toast fires. |
| ZIP export/import round-trip carries siblings | D-07 | DB-snapshot + cross-machine sync validates the persistence boundary | 1) Link 2 sibling pairs in source DB. 2) Hamburger → Export settings → save ZIP. 3) Manually delete the partner stations in source DB. 4) Hamburger → Import settings, pick the ZIP. 5) Verify all 4 stations restored AND sibling links restored AND 'Also on:' rows render correctly. |
| AA auto + manual co-exist on 'Also on:' line | D-01 | Real DI.fm/RadioTunes pairs validate merge semantics | 1) Pick a DI.fm station that has a known cross-network AA sibling (already in 'Also on:' via Phase 51). 2) Add a manual sibling to a different (non-AA) station. 3) Verify NowPlaying shows AA chip plain text + manual chip with × in the same 'Also on:' line. 4) × removes the manual link only; AA chip stays. |

*All other behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (planner fills task IDs)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 25s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner produces PLAN.md files and maps task IDs into the verification map above)

**Approval:** pending
