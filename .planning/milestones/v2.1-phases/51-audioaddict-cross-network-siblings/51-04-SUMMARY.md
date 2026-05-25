---
phase: 51-audioaddict-cross-network-siblings
plan: 04
status: complete
wave: 3
completed: 2026-04-28
requirements-completed: []
---

# Plan 51-04 Summary — navigate_to_sibling Wiring

## What was built

Click-to-navigate flow that turns Plan 51-03's clickable sibling links into
working dialog navigation. Delivers SC #2 (user can navigate from one sibling
to another), enforces D-11 (Save / Discard / Cancel confirm on dirty
navigation), and connects `EditStationDialog` to `MainWindow` via the new
`navigate_to_sibling = Signal(int)` (D-09).

## Files modified

- `musicstreamer/ui_qt/edit_station_dialog.py` — new signal, slot, save-success flag.
- `musicstreamer/ui_qt/main_window.py` — new MainWindow slot, two new connect lines.
- `tests/test_edit_station_dialog.py` — six new pytest-qt tests.

## Implementation

### EditStationDialog

- **Signal:** `navigate_to_sibling = Signal(int)` declared at class scope.
- **Slot:** `_on_sibling_link_activated(href: str)` parses `sibling://{int}`
  (defensive: malformed hrefs silently ignored), then dispatches based on
  `_is_dirty()`:

  | Dialog state    | Confirm answer | Action                                        |
  |-----------------|----------------|-----------------------------------------------|
  | clean           | n/a            | emit + accept()                               |
  | dirty           | Save (valid)   | _on_save() emits station_saved + accepts; emit |
  | dirty           | Save (invalid) | _on_save warning shown, no emit, dialog stays |
  | dirty           | Discard        | emit, then reject() (preserves _is_new cleanup) |
  | dirty           | Cancel         | no emit, dialog stays open                    |

- **Save-success bridge:** `_on_save` returns `None` unconditionally, so
  `_on_sibling_link_activated` cannot tell success from failure by return value.
  Added `self._save_succeeded: bool` instance attribute, initialized to `False`
  in `__init__`, reset to `False` at the start of `_on_save`, and set to `True`
  immediately before `self.accept()`. The slot reads it after calling
  `_on_save()` to decide whether to navigate. Exactly four occurrences
  (init / reset / set-True / read).

- **Connection:** `self._sibling_label.linkActivated.connect(self._on_sibling_link_activated)`
  installed in `_build_ui` (replacing Plan 51-03's hook comment). Bound method,
  no lambda (QA-05).

- **QMessageBox:** Uses `QMessageBox.StandardButton.Save | Discard | Cancel`,
  default `Cancel`.

### MainWindow

- **Slot:** `_on_navigate_to_sibling(sibling_id: int)` re-fetches the sibling
  via `self._repo.get_station(sibling_id)` (mirrors UAT #2 fix at
  `_on_edit_requested` line 464), early-returns on `None` (sibling deleted
  between render and click), then delegates to `self._on_edit_requested(sibling)`.
  Single source of truth for dialog setup (signal wiring lives in one place,
  including recursive `navigate_to_sibling` for sibling chains).

- **Connections:** `dlg.navigate_to_sibling.connect(self._on_navigate_to_sibling)`
  added to BOTH dialog-instantiation sites:
  - `_on_edit_requested` (existing edit path)
  - `_on_new_station_clicked` (new-station path — supports paste-AA-url
    flow where a brand-new station could itself match siblings)

  Both are bound-method connections (QA-05).

### SC #4 enforcement (no playback regression)

Both new methods are forbidden from referencing `player`, `failover`,
`stream_queue`, `self._player`, `self.now_playing`, or `_media_keys`. Verified
via grep gates in the plan's acceptance criteria — both return zero matches.

The currently-playing station is unaffected by sibling navigation. The user
can navigate sibling chains while playback continues uninterrupted.

## Tests

Six new pytest-qt tests in `tests/test_edit_station_dialog.py` cover every
dispatch path:

| Test | Path |
|------|------|
| `test_link_activated_emits_navigate_to_sibling_when_clean` | clean |
| `test_link_activated_save_path_emits_when_save_succeeds` | dirty + Save (valid) |
| `test_link_activated_save_path_does_not_emit_when_save_fails` | dirty + Save (invalid) |
| `test_link_activated_discard_path_emits_without_saving` | dirty + Discard |
| `test_link_activated_cancel_path_no_signal` | dirty + Cancel |
| `test_link_activated_ignores_malformed_href` | malformed |

Save/Discard/Cancel paths use `monkeypatch.setattr(QMessageBox, "question", ...)`
to drive the confirm flow deterministically. Discard test asserts
`aa_repo.update_station.called is False`. Save-failure test asserts
`d._save_succeeded is False` and that `QMessageBox.warning` was called once.

**Test results:** 6/6 new pass. 51/52 dialog file pass (the one failure is
the pre-existing `test_logo_status_clears_after_3s` 3-second flaky timer
documented in 51-02-SUMMARY.md as a 20–30% spurious failure rate — verified
unrelated to this plan by reproducing it on the prior commit).

`tests/test_main_window_integration.py` and `tests/test_main_window_media_keys.py`:
56/56 pass. D-10 invariant verified at the file-import boundary (no media-keys
test regressed).

## Acceptance criteria

All 7 grep-based acceptance criteria from PLAN passed:

| Criterion | Result |
|-----------|--------|
| `navigate_to_sibling = Signal(int)` declared | 1 match ✓ |
| `def _on_sibling_link_activated` exists | 1 match ✓ |
| `self._save_succeeded` count ≥ 4 | 4 matches ✓ (W1 fix) |
| `linkActivated.connect(self._on_sibling_link_activated)` | 1 match ✓ |
| Lambda near linkActivated.connect | 0 matches ✓ |
| `QMessageBox.StandardButton.Save \| Discard \| Cancel` | all 3 referenced ✓ |
| SC #4: zero playback symbols in slot | 0 matches ✓ |

MainWindow side:

| Criterion | Result |
|-----------|--------|
| `def _on_navigate_to_sibling` exists | 1 match ✓ |
| `self._on_edit_requested(sibling)` delegation | 1 match ✓ |
| `navigate_to_sibling.connect` whitespace-tolerant grep returns 2 | 2 matches ✓ (W3 fix) |
| `self._repo.get_station(sibling_id)` re-fetch | 1 match ✓ |
| SC #4: zero playback symbols in slot | 0 matches ✓ |
| Lambda near navigate_to_sibling.connect | 0 matches ✓ |

## Commits

- `4ecb79c` — `feat(51-04): add navigate_to_sibling signal + dirty-state confirm to EditStationDialog`
- `ab09fe9` — `feat(51-04): wire navigate_to_sibling -> MainWindow._on_navigate_to_sibling`
- `b7b9218` — `test(51-04): add tests for navigate_to_sibling clean/dirty/Save/Discard/Cancel paths`

## Deviations

None — plan executed inline (without subagent isolation, due to a usage-limit
recovery) but the actions, sequence, and acceptance criteria match the plan
verbatim.

## Note for Plan 51-05

The end-to-end integration test should monkeypatch `EditStationDialog.exec`
(or use `qtbot.waitSignal` against `navigate_to_sibling`) to capture which
station is opened on each call. The plan already specifies using
`fake_player.play_calls == []` for SC #4 verification — that fixture is
intact at `tests/test_main_window_integration.py:44` and ready to use.
