---
phase: 51-audioaddict-cross-network-siblings
plan: 05
status: complete
wave: 4
completed: 2026-04-28
requirements-completed:
  - BUG-02
---

# Plan 51-05 Summary — End-to-End Sibling Navigation Test

## What was built

A single pytest-qt integration test that exercises the full Phase 51 chain
end-to-end and asserts all four ROADMAP success criteria. Lives in
`tests/test_main_window_integration.py`.

## File modified

- `tests/test_main_window_integration.py` — appended `test_phase_51_sibling_navigation_end_to_end`.

## Test mechanics

**Setup:**
- Two synthetic AA stations: DI.fm Ambient (id=1) and ZenRadio Ambient (id=2),
  with first-stream URLs that normalize to the same channel_key (`ambient`).
- `monkeypatch.setattr(type(fake_repo), ...)` patches `list_stations`,
  `get_station`, `list_streams`, `list_providers`, `ensure_provider` on
  the real `FakeRepo` class (W5 fix — consistent with the file's existing
  `monkeypatch.setattr(...)` convention used at line 623+, NOT MagicMock
  instance-attr shadowing).

**Drive:**
- `monkeypatch.setattr(esd_mod.EditStationDialog, "exec", _fake_exec)` —
  the patched `_fake_exec` records the dialog's station id, captures the
  rendered sibling-label HTML on the first call, and programmatically
  triggers `_on_sibling_link_activated("sibling://2")` to simulate the
  user clicking the link.
- `MainWindow._on_edit_requested(di_station)` opens the first dialog;
  the link click recursively opens the sibling dialog via the
  `navigate_to_sibling` signal → `_on_navigate_to_sibling` → second
  `_on_edit_requested(zen_station)` chain.

## Assertion → Success Criterion mapping

| Assertion | SC | What it proves |
|-----------|-----|----------------|
| `exec_calls == [1, 2]` | SC #2 | Click on link opens sibling dialog (DI.fm first, ZenRadio second) |
| `'Also on:' in text and 'href="sibling://2"' in text and 'ZenRadio' in text` | SC #1 | DI.fm dialog rendered the sibling label with a clickable link |
| `dataclasses.fields(Station)` lacks `aa_channel_key` | SC #3 | No schema column — sibling detection is purely URL-derived (D-01) |
| `fake_player.play_calls == []` | SC #4 | No playback occurred during sibling navigation — cross-network failover NOT introduced |

## SC #4 spy mechanism

`FakePlayer.play_calls: list[Station]` (initialized to `[]` at
`tests/test_main_window_integration.py:44`, appended on every `play()`
call at line 53) is the canonical spy. The plan-checker B1 fix replaced
the original hasattr-guarded MagicMock check (which was a silent no-op
against the real FakePlayer class) with this direct list-equality
assertion. The acceptance criterion `grep -qE 'fake_player\.play_calls\s*==\s*\[\s*\]'`
enforces a working assertion, not a string-match on broken code.

## SC #3 verification

Uses `from dataclasses import fields as dc_fields` and
`{f.name for f in dc_fields(Station)}` to introspect the Station
dataclass at runtime. The assertion `"aa_channel_key" not in
station_field_names` will fail loudly if a future change adds the column
that D-01 explicitly rejects. The acceptance criterion grep enforces the
functional dataclass-fields check (W2 fix — replaces the original
permissive `grep -q 'aa_channel_key'` that would pass on a comment).

## FakeRepo configuration consistency (W5 fix)

The original plan draft used `MagicMock(...)` instance-attr shadowing.
The plan-checker W5 finding noted this conflicted with the file's
existing convention (`monkeypatch.setattr(FakeRepo, "method", ...)` at
line 648-653). The implemented test uses `monkeypatch.setattr(type(fake_repo), ...)`
exclusively, with `raising=False` for `ensure_provider` (which doesn't
exist on the base FakeRepo class). The acceptance criterion grep for
`monkeypatch.setattr(FakeRepo|monkeypatch.setattr(type(fake_repo)`
returns 2 matches.

## Test results

- `pytest tests/test_main_window_integration.py -k "phase_51"` — 1/1 pass.
- `pytest tests/test_main_window_integration.py` — 44/44 pass (full file).
- `pytest tests/test_aa_siblings.py tests/test_edit_station_dialog.py tests/test_main_window_integration.py` — 107/107 pass after deselecting the pre-existing flaky `test_logo_status_clears_after_3s` (timing-sensitive 3-second qtbot.wait, documented in 51-02-SUMMARY as 20-30% spurious failure rate, unrelated to Phase 51).
- All 33 new Phase 51 tests pass:
  - 12 from Plan 51-01 (find_aa_siblings unit)
  - 8 from Plan 51-02 (_is_dirty unit)
  - 6 from Plan 51-03 (sibling rendering unit)
  - 6 from Plan 51-04 (link click dispatch unit)
  - 1 from Plan 51-05 (end-to-end integration)

## Acceptance criteria

All criteria from the plan satisfied:

| Criterion | Result |
|-----------|--------|
| Test name `test_phase_51_sibling_navigation_end_to_end` | ✓ |
| `exec_calls == [1, 2]` assertion | ✓ |
| `href="sibling://2"` assertion | ✓ |
| SC #3: `aa_channel_key.*not in` / `dc_fields(Station)` (W2 fix) | ✓ |
| SC #4: `fake_player.play_calls == []` (B1 fix) | ✓ |
| W5: `monkeypatch.setattr(type(fake_repo)` pattern | ✓ |
| Phase 51 test pass | ✓ |
| Full file pass | ✓ |

## Commits

- `6cbbe3b` — `test(51-05): add end-to-end sibling navigation integration test (SC #1, #2, #3, #4)`

## Deviations

- One implementation deviation: needed `raising=False` on the
  `ensure_provider` monkeypatch because that method doesn't exist on the
  base `FakeRepo` class. Pattern stays consistent with the file (line 649,
  `slp_mod.StationListPanel.select_station` is patched with `raising=False`
  for the same reason — class doesn't have the attribute).
- Plan executed inline (no subagent isolation, due to a usage-limit
  recovery mid-Wave 3). Actions, sequence, and acceptance criteria match
  the plan verbatim.

## BUG-02 closed

Phase 51 ships the user-visible cross-network sibling feature end-to-end:
- Editing DI.fm "Ambient" shows "Also on: ZenRadio • JazzRadio • ..." with
  hyperlink-style clickable network names.
- Clicking a network opens the sibling's edit dialog. Save/Discard/Cancel
  confirmation if the current dialog has unsaved edits.
- No DB schema change. No cross-network failover. No playback regression.

`requirements-completed: [BUG-02]` — the marker for the requirement
mark-complete pass during phase verification.
