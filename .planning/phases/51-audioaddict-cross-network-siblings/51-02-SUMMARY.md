---
phase: 51-audioaddict-cross-network-siblings
plan: 02
subsystem: ui
tags: [pyside6, qdialog, qtablewidget, dirty-state, snapshot, edit-station, tdd]

# Dependency graph
requires:
  - phase: 39
    provides: EditStationDialog (PySide6 modal port of v1.5 station editor)
  - phase: 999.1
    provides: _is_new lifecycle flag + placeholder-row pattern (orthogonal to dirty state per D-12)
provides:
  - EditStationDialog._is_dirty() predicate — returns True when name/URL/provider/tags/ICY/streams differ from clean baseline
  - EditStationDialog._capture_dirty_baseline() — freezes a clean-state snapshot, called at end of _populate and re-called in __init__ after the is_new placeholder row
  - EditStationDialog._snapshot_form_state() — pure helper that builds a deterministic dict (frozenset/tuple values) for == comparison
  - 8 pytest-qt tests covering all six tracked form domains
affects: [51-04, dirty-state, edit-station-dialog, sibling-navigation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Snapshot-and-compare dirty-state predicate (project-first)"
    - "Deterministic-equality snapshot dict (frozenset for tag chips, tuple-of-tuples for QTableWidget rows)"
    - "Two-call baseline capture (end of _populate + __init__ post-placeholder-row for is_new)"

key-files:
  created: []
  modified:
    - musicstreamer/ui_qt/edit_station_dialog.py
    - tests/test_edit_station_dialog.py

key-decisions:
  - "Snapshot-and-compare picked over per-widget listeners (D-12). Rationale: (a) one extension site for future field additions — _snapshot_form_state is the only file to touch when a new dirty-tracked field is added; (b) survives QTableWidget's lack of a built-in dirty signal cleanly (no per-cell wiring needed, and cellChanged would still need a row-snapshot fallback for inserts/removes); (c) cheap because _is_dirty() runs only at navigation time, not per-keystroke."
  - "Snapshot shape uses immutable nested containers (frozenset for tags, tuple-of-tuples for streams) so dict equality is deterministic regardless of insertion order."
  - "Stream cells are captured as raw text (item.text() or '') with no int coercion. Rationale: a press-and-erase on Bitrate matches the on-screen state and avoids dirty-flips when the saved-state interpretation would round empty -> 0."
  - "_dirty_baseline initialized to None (not {}); _is_dirty() returns False defensively when baseline is unset. Rationale: a caller invoking _is_dirty() before _populate has a chance to fire (defensive ordering) reads as clean rather than panicking with KeyError or false-dirty."
  - "_is_new lifecycle (line 200) untouched — D-12 orthogonality preserved. The is_new branch in __init__ re-captures the baseline AFTER its own _add_stream_row() call so a fresh new-station dialog reads clean ('user has not modified the placeholder') instead of dirty ('the placeholder itself is a modification')."
  - "Logo path excluded from dirty tracking — it has its own refresh path (_refresh_logo_preview, _on_logo_fetched) and is not in the D-12 scope (name/URL/provider/tags/ICY/streams)."

patterns-established:
  - "Dialog-level dirty-state predicate via snapshot-and-compare (first in codebase). Future dialogs needing change detection should follow the three-method shape: _snapshot_form_state (pure) + _capture_dirty_baseline (write) + _is_dirty (read)."
  - "Two-stage baseline capture for dialogs that mutate state during __init__ (the is_new placeholder-row pattern). _populate captures a clean baseline; __init__ re-captures after any post-_populate widget mutations the lifecycle flag triggers."

requirements-completed: [BUG-02]

# Metrics
duration: 7 min
completed: 2026-04-28
---

# Phase 51 Plan 02: EditStationDialog dirty-state predicate Summary

**Snapshot-and-compare `_is_dirty()` predicate added to `EditStationDialog`, enabling Plan 51-04 to gate sibling-link clicks with a Save / Discard / Cancel confirm.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-28T14:55:26Z
- **Completed:** 2026-04-28T15:03:10Z
- **Tasks:** 2 / 2 (RED + GREEN)
- **Files modified:** 2 (`musicstreamer/ui_qt/edit_station_dialog.py` +79 lines, `tests/test_edit_station_dialog.py` +84 lines)

## Accomplishments

- Introduced the project's first dialog-level dirty-state mechanism (no prior precedent — `_is_new` is a lifecycle flag, not a change detector).
- Scoped to exactly the six fields the user can edit on `EditStationDialog`: name, URL, provider, tags, ICY, streams table contents.
- Preserved `_is_new` lifecycle orthogonality (D-12) — the dirty baseline is re-captured in `__init__` after the placeholder row is added so a fresh new-station dialog still reads clean.
- 8 pytest-qt tests covering every tracked form domain plus a row-add scenario; all pass on every run; runtime ~0.21s for the dirty-state subset, ~3.5s for the full 40-test dialog file.

## Task Commits

1. **Task 1: RED — failing pytest-qt tests for `_is_dirty`** — `2596592` (test)
2. **Task 2: GREEN — `_capture_dirty_baseline` + `_is_dirty` + `_snapshot_form_state` on `EditStationDialog`** — `98c632b` (feat)

_TDD plan: RED -> GREEN, no REFACTOR commit (implementation was clean as written; no follow-up cleanup needed)._

## Files Created/Modified

- `musicstreamer/ui_qt/edit_station_dialog.py` — added `self._dirty_baseline: dict | None = None` to `__init__`, three new private methods (`_snapshot_form_state`, `_capture_dirty_baseline`, `_is_dirty`) under a new "Phase 51-02 / D-11 / D-12 — dirty-state predicate" section between `_populate` and `_make_chip`, hooked `_capture_dirty_baseline()` at the end of `_populate`, and added a re-capture call in `__init__` immediately after the `is_new` placeholder `_add_stream_row()`. Net +79 lines, no deletions, no behavior change to any pre-existing path.
- `tests/test_edit_station_dialog.py` — appended 8 tests under a new "Phase 51-02 / D-11 / D-12" section: `test_is_dirty_false_after_populate`, `test_is_dirty_after_name_edit`, `test_is_dirty_after_url_edit`, `test_is_dirty_after_provider_change`, `test_is_dirty_after_tag_toggle`, `test_is_dirty_after_icy_toggle`, `test_is_dirty_after_stream_cell_edit`, `test_is_dirty_after_stream_row_added`. Reused the existing `dialog`, `station`, `repo`, `player`, `qtbot` fixtures.

## Snapshot shape

The snapshot is a `dict` with deterministic-equality nested containers:

```python
{
    "name":     str,                                          # self.name_edit.text()
    "url":      str,                                          # self.url_edit.text()
    "provider": str,                                          # self.provider_combo.currentText()
    "icy":      bool,                                         # self.icy_checkbox.isChecked()
    "tags":     frozenset[tuple[str, str]],                   # {(tag, "selected"|"unselected"), ...}
    "streams":  tuple[tuple[str, str, str, str, str], ...],   # ((url, quality, codec, bitrate, position), ...)
}
```

All container types are immutable and order-insensitive (frozenset) or order-sensitive (tuple) as appropriate. `dict.__eq__` compares element-wise; equality is invariant across hash randomization seeds.

## Note for Plan 51-04

When wiring the `linkActivated` slot for sibling navigation, call `self._is_dirty()` BEFORE emitting `navigate_to_sibling`:

```python
def _on_sibling_link_activated(self, href: str) -> None:
    sibling_id = int(href.removeprefix("sibling://"))
    if self._is_dirty():
        # 3-button QMessageBox.question (Save / Discard / Cancel) per D-11.
        # See 51-PATTERNS.md for the canonical confirm-dialog shape.
        ...
    self.navigate_to_sibling.emit(sibling_id)
```

The predicate returns `False` defensively when `_dirty_baseline is None`, so a slot invoked before `_populate` has run does not surface a phantom confirm.

## Deviations from Plan

None — plan executed exactly as written. The two atomic commits match the plan's commit-message templates verbatim.

## Issues Encountered

None within the scope of this plan.

### Out-of-scope observations (logged, not fixed)

- **Pre-existing test flakiness**: `tests/test_edit_station_dialog.py::test_logo_status_clears_after_3s` is a 3-second `qtbot.wait()`-based timer test that is timing-sensitive on this hardware (~20-30% spurious failure rate observed both BEFORE and AFTER my changes — verified by stashing my diff and re-running 5x: 4 pass, 1 fail; same ratio with my changes applied). This is NOT a regression introduced by Phase 51-02 and is out of scope per the executor's scope-boundary rule. Logged here for future test-stability work.
- **Pre-existing environmental dep gap**: ~21 tests under `tests/test_player*.py`, `tests/test_player_buffer.py`, `tests/test_media_keys_*.py`, `tests/test_headless_entry.py`, `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode`, `tests/test_cookies.py`, `tests/test_twitch_*.py`, `tests/test_windows_palette.py` all fail with `ModuleNotFoundError: No module named 'gi'` when run via `uv run --with pytest --with pytest-qt`. This is because `gi` (PyGObject for GStreamer) is not declared as a `--with` dep in the ephemeral uv-managed runtime. Pre-existing; not a regression from Phase 51-02. The plan's verify command (`pytest tests/test_edit_station_dialog.py`) does not transitively load `musicstreamer.player` and is unaffected. Logged for future test-environment work (likely a phase-level concern around `pyproject.toml` test-extras rather than this plan's scope).

## TDD Gate Compliance

- RED gate (`test(...)`): `2596592` — landed BEFORE GREEN; verified non-zero exit and `AttributeError: 'EditStationDialog' object has no attribute '_is_dirty'` in the test output.
- GREEN gate (`feat(...)`): `98c632b` — landed AFTER RED; verified all 8 new tests pass and no existing test regresses (40/40 in the dialog file pass on stable runs).
- REFACTOR gate: omitted (implementation needed no cleanup; the three-method shape was clean as authored).

## Verification Log

- `uv run --with pytest --with pytest-qt pytest tests/test_edit_station_dialog.py -k "is_dirty" -v` -> 8 passed, 32 deselected (0.21s).
- `uv run --with pytest --with pytest-qt pytest tests/test_edit_station_dialog.py -v` -> 40 passed (3.39-3.52s) on every stable run; the pre-existing flaky `test_logo_status_clears_after_3s` occasionally fails per the timing-sensitivity note above, with no causal link to this plan.
- `grep -c 'def test_is_dirty' tests/test_edit_station_dialog.py` -> 8.
- `grep -E 'def test_is_dirty_(false_after_populate|after_name_edit|after_url_edit|after_provider_change|after_tag_toggle|after_icy_toggle|after_stream_cell_edit|after_stream_row_added)\b' tests/test_edit_station_dialog.py | wc -l` -> 8.
- `grep -c 'self\._dirty_baseline' musicstreamer/ui_qt/edit_station_dialog.py` -> 5.
- `grep -c 'self\._capture_dirty_baseline()' musicstreamer/ui_qt/edit_station_dialog.py` -> 2.
- `grep -q 'self\._is_new = is_new' musicstreamer/ui_qt/edit_station_dialog.py` -> success (line 200 untouched).

## Self-Check: PASSED

- `[ -f musicstreamer/ui_qt/edit_station_dialog.py ]` -> FOUND.
- `[ -f tests/test_edit_station_dialog.py ]` -> FOUND.
- `git log --oneline | grep -E '^(2596592|98c632b)'` -> both commits FOUND.
- All 8 acceptance criteria for Task 1 PASS.
- 7/8 acceptance criteria for Task 2 PASS in-scope (the 8th — full unit suite — is blocked by pre-existing `gi` import errors unrelated to this plan).
- All `<success_criteria>` items satisfied: clean baseline after `_populate`, dirty after each of the six tracked field mutations, `_is_new` path captures its own baseline, 8 new tests pass, no existing dialog test regresses, two atomic commits (RED + GREEN).
