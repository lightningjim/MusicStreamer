---
phase: 71-sister-station-expansion-1-add-ability-to-link-sister-statio
plan: 04
subsystem: ui
tags: [pyside6, qdialog, qcombobox, qlistwidget, sibling-station, manual-link, picker-modal]

# Dependency graph
requires:
  - phase: 71
    provides: "Repo.list_providers / list_stations / list_sibling_links / add_sibling_link (Plan 71-01); find_aa_siblings (Plan 71-02 / Phase 51)"
provides:
  - "AddSiblingDialog(QDialog) — application-modal two-step picker (provider QComboBox + filtered QListWidget) for manual sibling linking"
  - "Public attribute _linked_station_name read by caller after exec() == Accepted (for toast copy)"
  - "Exclusion-set computation that unions self + AA auto-detected + already-manually-linked station IDs"
affects:
  - "71-03 (Wave 3 EditStationDialog chip row) — imports AddSiblingDialog and opens it from the + Add sibling button"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Synchronous picker modal: reuse DiscoveryDialog's QDialog + QVBoxLayout structure without QThread/QProgressBar when the source list is already in memory"
    - "QDialogButtonBox label override (Ok→'Link Station', Cancel→'Don't Link') for outcome-named CTAs"
    - "QListWidgetItem(text) + setData(Qt.UserRole, station_id) for picker rows; setFlags(Qt.NoItemFlags) for non-selectable empty-state items"
    - "Two-step picker filter chain: provider combo filter → exclusion set filter → case-insensitive substring filter → alphabetical sort"

key-files:
  created:
    - "musicstreamer/ui_qt/add_sibling_dialog.py (270 LOC) — AddSiblingDialog class"
  modified: []

key-decisions:
  - "No synthetic '(no provider)' entry in the QComboBox — stations with provider_name=None default to the first provider; user can switch the combo manually if needed. (RESEARCH Open Decision 1 left unresolved; defaulting to first available provider keeps the UI simple and avoids a contract-stretching addition.)"
  - "_on_accept accepts variadic *args so a single slot serves both QDialogButtonBox.accepted (no args) and QListWidget.itemDoubleClicked (one QListWidgetItem arg) — avoids a separate double-click adapter."
  - "QFormLayout used for the Provider:/Station: rows (matches edit_station_dialog form-label pattern at line 343,358,364) — the form labels and the search QLineEdit placeholder 'Filter stations…' use a literal U+2026 HORIZONTAL ELLIPSIS character per UI-SPEC line 126, not three ASCII dots."
  - "Empty-state disambiguation: 'No other stations found for this provider.' when provider_candidates list (after self-exclusion only) is empty; 'All stations in this provider are already linked.' when candidates exist but all are excluded by AA or manual-link sets."
  - "Ok button explicitly disabled defensively inside _repopulate_station_list even though _on_selection_changed would also do so — clearing the QListWidget may not fire itemSelectionChanged in all Qt versions."

patterns-established:
  - "Variadic *args slot for combined QDialogButtonBox + QListWidget activation"
  - "Defensive Ok-disable on every list rebuild (clearing the list may not fire itemSelectionChanged)"

requirements-completed:
  - D-11
  - D-12
  - D-13

# Metrics
duration: 12min
completed: 2026-05-12
---

# Phase 71 Plan 04: AddSiblingDialog Summary

**Two-step picker QDialog (provider QComboBox → filtered station QListWidget) with outcome-named CTAs ('Link Station' / 'Don't Link') that excludes self + AA-auto-detected + already-manually-linked stations and persists the user's pick via Repo.add_sibling_link.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-12T21:56Z (approx — worktree-agent spawn)
- **Completed:** 2026-05-12T22:08:19Z
- **Tasks:** 1 (single-task plan)
- **Files modified:** 1 (created)

## Accomplishments

- New `musicstreamer/ui_qt/add_sibling_dialog.py` (270 LOC) implementing `AddSiblingDialog(QDialog)` per CONTEXT D-11/D-12/D-13 and UI-SPEC §"AddSiblingDialog (two-step picker modal)".
- 9/9 RED tests in `tests/test_add_sibling_dialog.py` turned GREEN (Plan 71-00 contract satisfied).
- Plan 71-01/02 GREEN tests in `tests/test_station_siblings.py` remain GREEN (13/13).
- Adjacent suites unchanged: `tests/test_aa_siblings.py` + `tests/test_discovery_dialog.py` (35/35 GREEN).

## Task Commits

1. **Task 1: Create AddSiblingDialog QDialog class** — `79eac36` (feat)

_Note: this is a non-TDD task wave-2 plan — the RED tests were already written in Plan 71-00; this plan only adds the production implementation._

## Files Created/Modified

- `musicstreamer/ui_qt/add_sibling_dialog.py` (NEW, 270 LOC) — `AddSiblingDialog(QDialog)` class with `_build_ui`, `_repopulate_station_list`, `_on_provider_changed`, `_on_search_changed`, `_on_selection_changed`, `_on_accept` slots. Provider combo, search filter, station list, button box composed per UI-SPEC layout sketch.

## Decisions Made

- **No synthetic "(no provider)" combo entry** — RESEARCH Assumption A3 was flagged but the planner did not resolve to include. Implementation defaults to the first available provider when `station.provider_name` is None or empty. Documented inline in the constructor.
- **`_on_accept` accepts `*args`** — wired to both `QDialogButtonBox.accepted` (0 args) and `QListWidget.itemDoubleClicked` (1 QListWidgetItem arg). Avoids a separate `_on_double_click` adapter slot.
- **QFormLayout for Provider:/Station: rows** — matches existing `edit_station_dialog.py` form-label pattern. The search QLineEdit placeholder uses a literal U+2026 HORIZONTAL ELLIPSIS character (verified by Python read).
- **Defensive Ok-disable on every list rebuild** — calling `_station_list.clear()` may not fire `itemSelectionChanged` in all Qt versions; explicit `setEnabled(False)` inside `_repopulate_station_list` guarantees the Ok gate.

## Deviations from Plan

None - plan executed exactly as written. No UI-SPEC empty-state copy or button-label copy deviations. No RichText/setStyleSheet calls introduced.

**Verification of acceptance-criteria grep gates:**

| Gate | Required | Actual |
|------|----------|--------|
| `class AddSiblingDialog(QDialog)` | 1 | 1 |
| `setWindowTitle("Add Sibling Station")` | 1 | 1 |
| `"Link Station"` / `'Link Station'` | ≥1 | 2 |
| `"Don't Link"` | ≥1 | 2 |
| `Filter stations` (U+2026 placeholder) | ≥1 | 1 |
| `find_aa_siblings`/`list_sibling_links`/`add_sibling_link` | ≥3 | 7 |
| `setTextFormat` | 0 | 0 (T-40-04 preserved) |
| `setStyleSheet` | 0 | 0 (theme inheritance only) |

## Issues Encountered

- **Stash mishandling during full-suite triage.** While confirming that 7 failing tests in `test_settings_export.py`, `test_edit_station_dialog.py`, and `test_now_playing_panel.py` were pre-existing RED tests (waiting for Plans 71-05/06/07), I stashed the new untracked `add_sibling_dialog.py` to re-run the suite at base. `git stash pop` failed due to a `uv.lock` conflict, and a subsequent `git stash drop` on the wrong stash discarded the file. Recovered by recreating the file from in-memory context (identical content). The 9 RED tests turned GREEN again on the recreated file. **Lesson:** when running pre-existing-failure triage, prefer `git stash --keep-index` with explicit pathspecs, and inspect `git stash show -u` before dropping.

## Stub / Threat Scan

- **Known Stubs:** None.
- **Threat Flags:** None new beyond the 4 entries already in PLAN.md `<threat_model>` (T-71-13..T-71-16).

## User Setup Required

None - this plan is a pure code addition; no external service configuration or env vars.

## Next Phase Readiness

- Plan 71-03 (Wave 3) — `EditStationDialog` chip row + `+ Add sibling` button — can now safely `from musicstreamer.ui_qt.add_sibling_dialog import AddSiblingDialog`, instantiate with `AddSiblingDialog(station=self._station, repo=self._repo, parent=self)`, call `dlg.exec()`, and on `QDialog.Accepted` read `dlg._linked_station_name` for the "Linked to {name}" toast.
- 7 pre-existing RED tests in `test_settings_export.py` / `test_edit_station_dialog.py` / `test_now_playing_panel.py` remain RED — these belong to Plans 71-05 (chip row), 71-06 (NowPlaying merged display), 71-07 (settings export forward-compat). Out of scope for Plan 71-04.

## Self-Check: PASSED

- File exists: `musicstreamer/ui_qt/add_sibling_dialog.py` (270 LOC) — FOUND.
- Commit exists: `79eac36 feat(71-04): create AddSiblingDialog — two-step picker modal` — FOUND.
- All 9 RED tests in `tests/test_add_sibling_dialog.py` GREEN.
- Wave 1 GREEN tests in `tests/test_station_siblings.py` still GREEN (13/13).
- Adjacent suites unchanged (test_aa_siblings.py + test_discovery_dialog.py: 35/35).

---
*Phase: 71-sister-station-expansion-1-add-ability-to-link-sister-statio*
*Completed: 2026-05-12*
