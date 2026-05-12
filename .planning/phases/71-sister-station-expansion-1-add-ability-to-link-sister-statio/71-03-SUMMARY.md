---
phase: 71-sister-station-expansion
plan: 03
subsystem: ui
tags: [pyside6, flowlayout, sibling-stations, edit-station-dialog, chip-row, signal-routing]

requires:
  - phase: 71-00
    provides: 6 RED chip-row tests + EXPECTED_RICHTEXT_COUNT = 3 lock in tests/test_constants_drift.py
  - phase: 71-01
    provides: Repo.list_sibling_links(station_id) + remove_sibling_link(a_id, b_id)
  - phase: 71-02
    provides: find_manual_siblings + merge_siblings helpers in musicstreamer/url_helpers.py
  - phase: 71-04
    provides: AddSiblingDialog (two-step picker modal) + _linked_station_name public attribute
provides:
  - EditStationDialog._sibling_row_widget (QWidget + FlowLayout) replaces the Phase 51 / 64 Qt.RichText _sibling_label QLabel
  - sibling_toast = Signal(str) for MainWindow toast routing (D-14 / D-11)
  - "+ Add sibling" QPushButton wired to AddSiblingDialog modal exec + refresh
  - "×" unlink QPushButton on manual chips wired to Repo.remove_sibling_link + refresh + sibling_toast
  - AA chip (bare button, no ×) vs manual chip (compound widget with ×) renderer split
  - Dedup precedence: manual wins on conflict so users can undo their own action
affects: [71-06-main-window-toast-wiring, 71-08-uat-and-cleanup]

tech-stack:
  added: []
  patterns:
    - "FlowLayout chip row reuse of station_list_panel._CHIP_QSS (already imported in edit_station_dialog.py since Phase 39)"
    - "Bound-method signal connection for + Add sibling (QA-05) + default-arg lambda capture for per-chip × (T-71-23 mitigation)"
    - "_refresh_siblings reads self.url_edit.text() (live URL field) not self._station.streams (Pitfall 4)"
    - "FlowLayout teardown via takeAt(0) + widget.deleteLater() loop (Pitfall 5)"
    - "Try/except over both DB reads (list_stations, list_sibling_links) — falls through to + Add sibling-only row on Repo failure"

key-files:
  created: []
  modified:
    - musicstreamer/ui_qt/edit_station_dialog.py
    - tests/test_edit_station_dialog.py
    - tests/test_main_window_integration.py

key-decisions:
  - "D-11 (Phase 71): always-visible chip row — + Add sibling must be discoverable at zero siblings"
  - "D-14 (Phase 71): manual chip carries × unlink button + sibling_toast(str) for confirm-free unlink (UI-SPEC line 314)"
  - "D-15 (Phase 71): AA chips are bare QPushButtons — no × button (auto-detection is the only mutation path)"
  - "Dedup direction (Plan-level deviation): manual wins on conflict instead of the plan's documented 'AA precedence', so users can undo their own action even when the same sibling is AA-detected. Plan 71-00 RED test test_manual_chip_has_x_button (partner is AA-cross-network AND manually linked) only passes under manual-wins semantics."
  - "Plan 71-00 _sibling_label tests retired (Rule 3 — implementation removed). New chip-row tests cover the equivalent contract; HTML-escape test is moot under QPushButton.setText plain-text default (T-71-21 mitigation)."

patterns-established:
  - "Compound-widget chip pattern: QWidget objectName 'sibling_chip_{id}' wrapping QHBoxLayout(margins=0, spacing=0) of name button + × button reads visually as one chip"
  - "Default-arg lambda capture pins sibling_id at lambda-creation time per chip — defends against late binding (T-71-23 mitigation)"
  - "FakeRepo extension pattern: add list_sibling_links / add_sibling_link / remove_sibling_link no-op defaults at the base FakeRepo class so the new _refresh_siblings codepath has a defined Repo surface (mirrors Plan 71-05 FakeRepo extension)"

metrics:
  duration_minutes: ~25
  completed: 2026-05-12
  green_tests_added: 7
  green_tests_retired: 6
  files_modified: 3
  lines_added: ~273
  lines_removed: ~163
---

# Phase 71 Plan 03: EditStationDialog chip row + sibling_toast Summary

Replaced the Phase 51 / Phase 64 read-only Qt.RichText `_sibling_label` QLabel with a `_sibling_row_widget` FlowLayout container of per-sibling chip widgets and a trailing "+ Add sibling" button. Added `sibling_toast = Signal(str)` for toast routing and wired `_on_add_sibling_clicked` to `AddSiblingDialog` modal exec.

## Line ranges

| Region | Old (pre-71-03) | New (post-71-03) |
|--------|-----------------|------------------|
| `sibling_toast = Signal(str)` declaration | n/a | line 261 (adjacent to `navigate_to_sibling = Signal(int)` at line 255) |
| `_sibling_label` QLabel block (REMOVED) | lines 477-492 | n/a |
| `_sibling_row_widget` construction (NEW) | n/a | lines 482-499 |
| `_refresh_siblings` method | lines 617-651 (35 lines, Phase 51 AA-only) | lines 623-705 (83 lines, AA + manual + chip teardown) |
| `_add_aa_sibling_chip` helper (NEW) | n/a | lines 708-728 |
| `_add_manual_sibling_chip` helper (NEW) | n/a | lines 730-786 |
| `_on_unlink_sibling` slot (NEW) | n/a | lines 792-808 |
| `_on_add_sibling_clicked` slot (NEW) | n/a | lines 810-826 |
| `_on_sibling_link_activated` (REUSED unchanged) | lines 1241-1288 | lines ~1330-1377 (offset by +~89 LOC of new helpers) |

## RichText baseline

| Before plan | After plan | Locked-in expected | Test status |
|-------------|-----------|--------------------|-------------|
| 4 (1 in edit_station_dialog.py + 3 in now_playing_panel.py) | 3 (0 in edit_station_dialog.py + 3 in now_playing_panel.py) | EXPECTED_RICHTEXT_COUNT = 3 (Plan 71-00) | tests/test_constants_drift.py::test_richtext_baseline_unchanged_by_phase_71 GREEN |

## GREEN test count

| Test category | Tests | Status |
|---------------|-------|--------|
| Plan 71-00 chip-row RED tests | 6 | GREEN — test_add_sibling_button_present, test_manual_chip_has_x_button, test_aa_chip_has_no_x_button, test_x_click_calls_remove_sibling_link, test_x_click_fires_unlinked_toast, test_chip_click_emits_navigate_signal |
| Plan 71-00 RichText baseline test | 1 | GREEN — test_richtext_baseline_unchanged_by_phase_71 |
| Phase 51-04 navigate_to_sibling regression suite (clean/dirty/Save/Discard/Cancel/malformed) | 6 | GREEN — exercised via direct `_on_sibling_link_activated()` calls; unchanged by chip-row swap |
| Phase 51-05 end-to-end integration | 1 | GREEN — updated to assert on chip-row objectNames |
| tests/test_edit_station_dialog.py full file | 72 | GREEN |
| tests/test_constants_drift.py full file | 6 | GREEN |
| tests/test_main_window_integration.py full file | 66 | GREEN |

## Retired tests (Rule 3 deviation — implementation removed)

6 tests asserting against the now-removed `_sibling_label.text()` / `.isHidden()`:

1. `test_sibling_section_hidden_for_non_aa_station` — chip row is always visible, so this test's premise no longer applies. Equivalent coverage: chip row contains only the "+ Add sibling" button when there are no siblings (implicit in `test_add_sibling_button_present`).
2. `test_sibling_section_hidden_when_no_siblings` — same as above.
3. `test_sibling_section_renders_links_for_aa_station_with_siblings` — replaced by `test_chip_click_emits_navigate_signal` (link activation) and `test_main_window_integration::test_phase_51_sibling_navigation_end_to_end` (cross-network chip render + click).
4. `test_sibling_link_text_uses_network_name_when_station_names_match` — render formatting moved out of the dialog; chip text is the station name verbatim (no em-dash, no network prefix). This is a UX change documented in UI-SPEC.
5. `test_sibling_link_text_uses_network_dash_name_when_station_names_differ` — same as above.
6. `test_sibling_html_escapes_station_name` — moot. QPushButton.setText is plain-text by default (T-71-21 mitigation), so the threat surface no longer exists.

Comment block at the same location in tests/test_edit_station_dialog.py preserves a historical record of why these tests were retired.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Inverted dedup precedence on AA + manual sibling conflict**

- **Found during:** Task 1 verification (Plan 71-00 RED test `test_manual_chip_has_x_button` failed under the plan's documented "skip manual entry if station_id appears in AA list" rule).
- **Issue:** The plan's pseudo-code skipped manual chips when the same station_id appeared in the AA list, so a station that was BOTH AA-detected (cross-network identity match) AND manually linked would render as a bare AA chip with no "×" button — preventing the user from removing their own manual link without editing the URL. The Plan 71-00 RED test partner station has BOTH attributes (different AA networks with matching channel identity + explicit `list_sibling_links([42])`), and the test asserts the manual compound chip `sibling_chip_42` exists with a × button.
- **Fix:** Reversed the dedup direction: manual wins on conflict. Collect manual sibling_ids first, then skip AA chips whose station_id is in the manual set. Each manual chip retains its × button so users can always undo their own action.
- **Files modified:** musicstreamer/ui_qt/edit_station_dialog.py (`_refresh_siblings` loop logic + docstring).
- **Commit:** 4d1b049 — feat(71-03): swap EditStationDialog _sibling_label → chip-row + sibling_toast.

**2. [Rule 3 - Blocking] _sibling_label tests block GREEN gate**

- **Found during:** Task 1 verification.
- **Issue:** The plan said "Existing 399+ tests still GREEN" but six existing tests (test_sibling_section_hidden_for_non_aa_station, test_sibling_section_hidden_when_no_siblings, test_sibling_section_renders_links_for_aa_station_with_siblings, test_sibling_link_text_uses_network_name_when_station_names_match, test_sibling_link_text_uses_network_dash_name_when_station_names_differ, test_sibling_html_escapes_station_name) assert directly on `d._sibling_label.text()` / `.isHidden()` — implementation that the plan explicitly REMOVES. Keeping the QLabel AND removing it AND keeping these tests passing is logically impossible.
- **Fix:** Retired the six tests, replacing them with a comment block documenting the retirement and pointing at the equivalent new RED-tests-turned-GREEN that cover the chip-row contract. The HTML-escape test is genuinely moot under QPushButton's plain-text default (T-71-21 mitigation).
- **Files modified:** tests/test_edit_station_dialog.py.
- **Commit:** 4d1b049.

**3. [Rule 3 - Blocking] FakeRepo missing list_sibling_links in tests/test_main_window_integration.py**

- **Found during:** Task 1 verification.
- **Issue:** `_refresh_siblings` now calls `self._repo.list_sibling_links(self._station.id)`. The integration test's FakeRepo did not define that method, so `AttributeError` was caught by the broad `except Exception:` and the entire sibling list (AA + manual) returned empty, breaking `test_phase_51_sibling_navigation_end_to_end`. (Phase 71 Plan 71-05 already extended `tests/test_now_playing_panel.py::FakeRepo` for the same reason — this commit applies the parallel extension to the integration test's FakeRepo.)
- **Fix:** Added `list_sibling_links`, `add_sibling_link`, `remove_sibling_link` no-op defaults to `FakeRepo` in `tests/test_main_window_integration.py`. Returning `[]` keeps pre-Phase-71 integration tests on the AA-only path.
- **Files modified:** tests/test_main_window_integration.py.
- **Commit:** 4d1b049.

**4. [Rule 1 - Bug] test_phase_51_sibling_navigation_end_to_end asserted on _sibling_label.text()**

- **Found during:** Task 1 verification, immediately after fix #3.
- **Issue:** Integration test SC #1 captured `_sibling_label.text()` and asserted `'Also on:' in text`, `'href="sibling://2"' in text`, `'ZenRadio' in text`. With the chip-row replacement, none of those substrings exist.
- **Fix:** Replaced text-substring assertions with `findChildren(QPushButton)` over `_sibling_row_widget`, asserting the AA-chip objectName `sibling_aa_chip_2` is present. The functional semantic (DI.fm dialog renders a clickable chip pointing at the ZenRadio sibling) is preserved.
- **Files modified:** tests/test_main_window_integration.py.
- **Commit:** 4d1b049.

### Deferred Items

**1. Explicit `setTabOrder()` chain across chip-row children (Plan 71-03 Step L — soft requirement)**

- **Reason:** Plan 71-03 documents Step L as a soft requirement: "If implementation grows past 5 LOC, document as deferred in SUMMARY and accept default Qt focus chain order." Walking the dynamic chip list to issue `setTabOrder(prev, curr)` calls would add ~10 LOC of state-tracking inside `_refresh_siblings` (last-added widget reference, first-call special case) and is not exercised by any of the 7 Plan 71-00 GREEN tests. Default left-to-right widget-addition order (FlowLayout natural order) provides usable keyboard navigation.
- **Risk:** Negligible — accessibleName is set on every chip + × button + + Add sibling button (already implemented), so screen-reader users get the same content regardless of tab order. Sighted keyboard users get the visual order.
- **Disposition:** Accept default Qt focus chain. Surface in Phase 71-08 UAT if real users report a focus-trap.

## Auth Gates

None — Plan 71-03 is a UI surgery against existing in-repo widgets; no external authentication touched.

## Threat Mitigations Applied

| Threat ID | Component | Mitigation |
|-----------|-----------|------------|
| T-71-21 | Station name → QPushButton.setText | QPushButton.setText is plain-text by default; no Qt.RichText surface introduced. Verified via test_richtext_baseline_unchanged_by_phase_71 (GREEN). |
| T-71-22 | sibling://{id} href payload → int() | Existing Phase 51 try/except ValueError at `_on_sibling_link_activated()` reused unchanged. |
| T-71-23 | Stale sibling_id capture in × lambda closure | Default-argument capture (`lambda checked=False, sid=sibling_id, sname=station_name: ...`) binds at lambda creation time, not call time. Each chip's × button carries its own sibling_id. Verified implicitly via test_x_click_calls_remove_sibling_link (correct sibling_id is passed to Repo.remove_sibling_link). |
| T-71-24 | Cross-provider tooltip → information disclosure | Tooltip only set when `provider_name != self._station.provider_name`. Provider name is already public-visible in the app's station tree, so this is additive context not new disclosure. |

## Threat Flags

None — no new network endpoints, no new auth surfaces, no new file-access patterns, no new schema. All threats are listed in the plan's `<threat_model>` and mitigated as documented above.

## Self-Check: PASSED

- File `musicstreamer/ui_qt/edit_station_dialog.py` exists: FOUND
- File `tests/test_edit_station_dialog.py` exists: FOUND
- File `tests/test_main_window_integration.py` exists: FOUND
- File `.planning/phases/71-sister-station-expansion-1-add-ability-to-link-sister-statio/71-03-SUMMARY.md` exists: FOUND (this file)
- Commit `4d1b049` exists: FOUND
- `grep -c "sibling_toast = Signal(str)" musicstreamer/ui_qt/edit_station_dialog.py` returns 1: VERIFIED
- `grep -c "_sibling_label" musicstreamer/ui_qt/edit_station_dialog.py` returns 0: VERIFIED
- `grep -c "setTextFormat(Qt\.RichText)" musicstreamer/ui_qt/edit_station_dialog.py` returns 0: VERIFIED
- Package-wide `setTextFormat(Qt\.RichText)` count is 3 (down from 4): VERIFIED
- 6 chip-row RED tests + 1 RichText baseline test GREEN: VERIFIED via `pytest tests/test_edit_station_dialog.py tests/test_constants_drift.py` (78 passed)
- `tests/test_main_window_integration.py` GREEN (66 passed): VERIFIED
