---
phase: 67-show-similar-stations-below-now-playing-for-switching-from-s
verified: 2026-05-10T14:15:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 67: Show Similar Stations — Verification Report

**Phase Goal:** When the master toggle is on, NowPlayingPanel shows a 'Similar Stations' section at the bottom of the center column with two pools (Same provider, Same tag — up to 5 random each), refreshable via ↻ button, collapsible, with click-to-switch playback. Off by default; persisted via SQLite settings. Phase 64 'Also on:' line stays untouched and is excluded from both pools.

**Verified:** 2026-05-10T14:15:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Master toggle is off by default (default `'0'`), persisted via SQLite `show_similar_stations` key | VERIFIED | `main_window.py:200` reads `get_setting("show_similar_stations", "0") == "1"`; `QAction.setChecked(...)` called with that result; `test_show_similar_action_is_checkable` passes (`isChecked() is False`) |
| 2 | Section appears at bottom of center column when toggle on | VERIFIED | `_similar_container = QWidget(self)` added to `center` layout via `center.addWidget(self._similar_container)` at `now_playing_panel.py:544`; `set_similar_visible(True)` calls `setVisible(True)` on the container; `test_similar_section_renders_when_master_toggle_on` passes |
| 3 | Two pools: Same provider (name-only) + Same tag (Name (Provider)) | VERIFIED | `render_similar_html(same_provider, show_provider=False)` at line 1175; `render_similar_html(same_tag, show_provider=True)` at line 1185; `test_render_similar_html_provider_section_no_provider_in_text` and `test_render_similar_html_tag_section_includes_provider` both pass |
| 4 | Up to 5 random each, refreshable via ↻ | VERIFIED | `pick_similar_stations(..., sample_size=5)` called in `_refresh_similar_stations`; `_similar_refresh_btn` (QToolButton, text="↻") connected to `_on_refresh_similar_clicked` which pops cache and re-derives; `test_refresh_similar_pops_cache_and_rerolls` passes |
| 5 | Collapsible (▾/▸ glyphs, collapse state persisted to `similar_stations_collapsed`) | VERIFIED | `_similar_collapse_btn` toggles `_similar_body.setVisible(...)`, updates glyph, calls `set_setting("similar_stations_collapsed", ...)` in `_on_similar_collapse_clicked`; `test_similar_collapse_persists` and `test_similar_collapse_initial_state_from_setting` pass |
| 6 | Click-to-switch via `similar_activated` signal → MainWindow `_on_similar_activated` → `_on_station_activated` | VERIFIED | `_on_similar_link_activated` emits `self.similar_activated.emit(station)`; `main_window.py:340` connects to `_on_similar_activated`; `_on_similar_activated` at line 474 delegates to `_on_station_activated(station)`; `test_similar_link_switches_playback_via_main_window` passes |
| 7 | Phase 64 "Also on:" line untouched and excluded from both pools | VERIFIED | `_sibling_label`, `_refresh_siblings`, `render_sibling_html` at `sibling://` prefix unmodified; `find_aa_siblings` called inside `pick_similar_stations` to build `excluded_ids`; `test_phase_64_sibling_label_unchanged_after_phase_67` and `test_sibling_label_visible_for_aa_station_with_siblings` both pass; `test_aa_siblings_excluded_from_both_pools` passes |
| 8 | No `lambda` on Phase 67 signal connections (QA-05) | VERIFIED | `_act_show_similar.toggled.connect(self._on_show_similar_toggled)` and `similar_activated.connect(self._on_similar_activated)` have no lambda; `test_no_lambda_on_similar_signal_connections` (structural grep test) passes |
| 9 | Test discipline: 22 pure-helper + 14 panel widget + 6 integration tests all pass (188 total test corpus including pre-existing) | VERIFIED | `pytest test_pick_similar_stations.py`: 22 passed; `pytest test_now_playing_panel.py -k similar`: 14 passed; `pytest test_main_window_integration.py -k "show_similar or similar_link or no_lambda"`: 6 passed; all 245 Phase 67-related tests pass |

**Score:** 9/9 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|---------|--------|---------|
| `musicstreamer/url_helpers.py` | `pick_similar_stations` + `render_similar_html` pure helpers | VERIFIED | Lines 269-391; substantive implementation with AA-exclusion, tag-union semantics, k=min clamp, html.escape on both name and provider |
| `musicstreamer/ui_qt/now_playing_panel.py` | `similar_activated` signal, widget tree, cache, 5 methods | VERIFIED | Signal at line 214; `_similar_cache` at line 237; container widget tree lines 453-544; methods at lines 770, 1120, 1192, 1231, 1249 |
| `musicstreamer/ui_qt/main_window.py` | `_act_show_similar` QAction, signal connection, initial push, 2 slot methods | VERIFIED | QAction at lines 197-202; signal connection at line 340; initial push at line 359; `_on_similar_activated` at 464; `_on_show_similar_toggled` at 577 |
| `tests/test_pick_similar_stations.py` | 22 pure-helper tests | VERIFIED | 22 tests, all passing |
| `tests/test_now_playing_panel.py` | Phase 67 section with 14 qtbot tests | VERIFIED | 14 tests matching `-k similar`, all passing |
| `tests/test_main_window_integration.py` | Phase 67 section with 6 integration tests | VERIFIED | 6 tests matching `-k "show_similar or similar_link or no_lambda_on_similar"`, all passing |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pick_similar_stations` | `find_aa_siblings` | In-module call for T-04b exclusion | WIRED | `url_helpers.py:313` calls `find_aa_siblings(...)` inside `pick_similar_stations`; `excluded_ids.update(sid for _, sid, _ in aa)` |
| `_refresh_similar_stations` | `pick_similar_stations` | Direct call in cache-miss branch | WIRED | `now_playing_panel.py:1165` — `pick_similar_stations(all_stations, self._station, sample_size=5)` |
| `_same_provider_links_label.linkActivated` | `_on_similar_link_activated` | `linkActivated.connect(self._on_similar_link_activated)` | WIRED | Line 507 (provider label) and 523 (tag label) — both QA-05 compliant bound-method connects |
| `_on_similar_link_activated` | `similar_activated` signal | `self.similar_activated.emit(station)` | WIRED | Line 1229; only emit site; five-guard chain before emit |
| `similar_activated` | `_on_similar_activated` | `now_playing.similar_activated.connect(self._on_similar_activated)` | WIRED | `main_window.py:340`; QA-05 compliant |
| `_on_similar_activated` | `_on_station_activated` | One-line delegate | WIRED | `main_window.py:474` — `self._on_station_activated(station)` |
| `_act_show_similar.toggled` | `_on_show_similar_toggled` | `toggled.connect(self._on_show_similar_toggled)` | WIRED | `main_window.py:202`; QA-05 compliant; no lambda |
| `_on_show_similar_toggled` | `set_similar_visible` | Direct call after `set_setting` | WIRED | `main_window.py:587` — `self.now_playing.set_similar_visible(checked)` |
| `bind_station` | `_refresh_similar_stations` | Direct call after `_refresh_siblings()` | WIRED | `now_playing_panel.py:653` |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `_same_provider_links_label` (QLabel, RichText) | `same_provider` list | `pick_similar_stations` sampling `repo.list_stations()` filtered by `provider_id` | Yes — derives from live SQLite station list | FLOWING |
| `_same_tag_links_label` (QLabel, RichText) | `same_tag` list | `pick_similar_stations` sampling `repo.list_stations()` filtered by tag intersection via `normalize_tags` | Yes — derives from live SQLite station list | FLOWING |
| `_similar_container` visibility | `_act_show_similar.isChecked()` | `repo.get_setting("show_similar_stations", "0")` on MainWindow init; `set_similar_visible(checked)` on toggle | Yes — reads from SQLite settings table | FLOWING |
| `_similar_body` visibility | `similar_stations_collapsed` setting | `repo.get_setting("similar_stations_collapsed", "0")` in `__init__`; `set_setting(...)` in `_on_similar_collapse_clicked` | Yes — round-trips to SQLite | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `pick_similar_stations` importable and returns correct types | `python -c "from musicstreamer.url_helpers import pick_similar_stations, render_similar_html; print('OK')"` | OK | PASS |
| 22 pure-helper tests pass | `uv run pytest tests/test_pick_similar_stations.py` | 22 passed | PASS |
| 14 panel widget tests pass | `uv run pytest tests/test_now_playing_panel.py -k similar` | 14 passed | PASS |
| 6 integration tests pass | `uv run pytest tests/test_main_window_integration.py -k "show_similar or similar_link or no_lambda"` | 6 passed | PASS |
| Phase 64 regression baseline | `uv run pytest tests/test_now_playing_panel.py::test_sibling_label_visible_for_aa_station_with_siblings tests/test_now_playing_panel.py::test_phase_64_sibling_label_unchanged_after_phase_67` | 2 passed | PASS |
| Combined 245-test corpus | `uv run pytest test_pick_similar_stations.py test_now_playing_panel.py test_main_window_integration.py test_aa_siblings.py test_filter_utils.py` | 245 passed | PASS |
| QA-05 structural no-lambda check | `test_no_lambda_on_similar_signal_connections` | PASSED | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| SIM-01 | 67-01, 67-04 | Hamburger QAction for master toggle exists, checkable, reads SQLite setting | SATISFIED | `_act_show_similar` at `main_window.py:197-202`; test passes |
| SIM-02 | 67-01, 67-04 | Toggle persists and flips panel container visibility | SATISFIED | `_on_show_similar_toggled` dual-write; `set_similar_visible` on panel; tests pass |
| SIM-03 | 67-01, 67-03 | Collapse state persisted to `similar_stations_collapsed` SQLite key | SATISFIED | `_on_similar_collapse_clicked` at line 1249; tests pass |
| SIM-04 | 67-01, 67-02 | Same-provider pool: excludes self, AA siblings, no-provider candidates | SATISFIED | `pick_similar_stations` lines 322-330; test corpus passes |
| SIM-05 | 67-01, 67-02 | Same-tag pool: union semantics via `normalize_tags`, excludes self/AA/no-tag | SATISFIED | `pick_similar_stations` lines 332-343; test corpus passes |
| SIM-06 | 67-01, 67-03 | In-memory cache keyed by station id, reused on revisit | SATISFIED | `_similar_cache` dict; cache-hit branch in `_refresh_similar_stations`; tests pass |
| SIM-07 | 67-01, 67-03 | Refresh button pops cache and re-derives both pools | SATISFIED | `_on_refresh_similar_clicked` pops cache, calls `_refresh_similar_stations`; test passes |
| SIM-08 | 67-01, 67-03, 67-04 | Click similar link emits signal → MainWindow → `_on_station_activated` | SATISFIED | Full pipeline wired; `test_similar_link_switches_playback_via_main_window` passes |
| SIM-09 | 67-01, 67-02 | `render_similar_html`: BR separator, escapes name+provider, `similar://` prefix | SATISFIED | `render_similar_html` at `url_helpers.py:355-391`; all 9 renderer tests pass |
| SIM-10 | 67-01, 67-03 | Sub-sections hidden when pool empty; header stays visible | SATISFIED | `setVisible(False)` per sub-section on empty pool; `test_similar_same_provider_subsection_hidden_when_empty` and `test_similar_section_header_visible_with_empty_pools` pass |
| SIM-11 | 67-01, 67-03 | Click handler: 5 guards, silent no-op on any failure | SATISFIED | `_on_similar_link_activated` five-guard chain at lines 1192-1229; 4 defense tests pass |
| SIM-12 | 67-01, 67-03 | Phase 64 "Also on:" line structurally unchanged | SATISFIED | `_sibling_label`, `_refresh_siblings`, `sibling://` prefix all unchanged; regression tests pass |
| QA-05 | 67-01, 67-04 | No lambda on Phase 67 signal connections | SATISFIED | Confirmed via structural grep test `test_no_lambda_on_similar_signal_connections`; lambda count in `now_playing_panel.py` = 0 (all occurrences are in comment text, not production code) |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|---------|--------|
| `now_playing_panel.py` | 237, 1155 | Cache never invalidated when bound station is edited — stale pools remain until user clicks ↻ | Warning | REVIEW.md WR-01; user sees stale recommendations after editing current station's tags/provider; not a goal blocker (CONTEXT.md R-04 explicitly accepts stale-OK) |
| `now_playing_panel.py` | 237 | `_similar_cache` grows unboundedly per session (no LRU eviction) | Warning | REVIEW.md WR-02; memory concern for long sessions with many stations; not a goal blocker for target 50-200 station libraries |
| `url_helpers.py` | 323 | `provider_id == 0` treated as valid provider | Info | REVIEW.md WR-03; unlikely to fire in practice; no blocker |
| `tests/test_now_playing_panel.py` | ~1047 | `test_refresh_similar_pops_cache_and_rerolls` uses reference identity (`is not`) test that passes even when pool content is identical | Warning | REVIEW.md WR-05; test is weaker than claimed — passes whenever a new tuple is constructed, not necessarily when re-sampling produced different content; does not block goal |

All warnings are pre-acknowledged quality improvements. None blocks the stated phase goal. WR-01 and WR-04 (pre-existing `_on_station_deleted` double-fire) are explicitly accepted per CONTEXT.md R-04 stale-OK philosophy and Phase 64 precedent respectively.

---

## Human Verification Required

None. All must-have behaviors are verifiable programmatically and all test assertions confirm them.

---

## Gaps Summary

No gaps. All 9 must-have truths are verified by the actual codebase:

- `pick_similar_stations` and `render_similar_html` exist in `url_helpers.py` as substantive pure functions (not stubs) — 22 unit tests confirm all behavioral contracts.
- `NowPlayingPanel` has all required attributes (`similar_activated` signal, `_similar_container`, `_similar_body`, `_similar_collapse_btn`, `_similar_refresh_btn`, `_same_provider_subsection`, `_same_tag_subsection`, `_similar_cache`) and all 5 required methods (`set_similar_visible`, `_refresh_similar_stations`, `_on_similar_link_activated`, `_on_refresh_similar_clicked`, `_on_similar_collapse_clicked`).
- `MainWindow` has `_act_show_similar` (checkable QAction, default off, reads SQLite setting), signal connection (`similar_activated.connect`), initial-state push (`set_similar_visible`), and both slots (`_on_show_similar_toggled`, `_on_similar_activated`).
- Phase 64 "Also on:" line is verified untouched (`sibling://` prefix, `_sibling_label`, `render_sibling_html` all unmodified).
- AA siblings are excluded from both pools via `find_aa_siblings` call inside `pick_similar_stations`.
- QA-05 structural test passes: no lambda on Phase 67 `.connect` lines.
- Pre-existing test failures noted in the instructions (`test_audioaddict_tab_widgets`, `test_audioaddict_quality_combo`, and Qt-fragile tests) are unrelated to Phase 67 and were confirmed pre-existing on base commit 5663b15.

---

_Verified: 2026-05-10T14:15:00Z_
_Verifier: Claude (gsd-verifier)_
