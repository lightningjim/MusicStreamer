---
slug: stream-remove-not-persisted
status: resolved
trigger: |
  I can't seem to remove a stream from an existing station. I remove and save and
  reopen and it's still there. The current example in the DB is the Groove Salad
  and I've set the quality/label to DELETEME to delineate it in the DB.
created: 2026-05-10
updated: 2026-05-10
---

# Debug: stream-remove-not-persisted

## Symptoms

DATA_START
- **Expected behavior:** After removing a stream row from a station in the Edit
  Station dialog and clicking Save, that stream should no longer be associated
  with the station. Reopening the station should show the stream gone.
- **Actual behavior:** The removed stream persists. After remove → Save →
  reopen Edit Station, the stream is still present. The current repro example
  in the DB is the Groove Salad station; the offending stream's
  quality/label was manually set to "DELETEME" to make it identifiable in
  the DB.
- **Error messages:** No errors — silent failure. Save completes cleanly; the
  stream just reappears on reopen.
- **Timeline:** Has worked before. User suspects this issue may be related to
  the **original single-stream identifier** carried over from the
  **Radio-Browser import** process.
- **Reproduction:** Open Edit Station dialog → remove a stream row → click
  Save → reopen Edit Station → removed stream is still present.
DATA_END

## Current Focus

- **hypothesis:** CONFIRMED — The Edit Station save path never deletes streams
  the user removed from the UI table. `reorder_streams` updates position values
  only; it ignores IDs absent from `ordered_ids`.
- **next_action:** DONE — fix applied, tests added.

## Evidence

- timestamp: 2026-05-10T00:00:00
  finding: |
    DB confirmed: Groove Salad has stream id=2337 quality="DELETEME" (the repro
    target), alongside 24 other streams (ids 4647-4671) imported from Radio-Browser.

- timestamp: 2026-05-10T00:00:01
  finding: |
    Root cause located in `edit_station_dialog.py` `_on_save` (lines 1164-1165).
    After building `ordered_ids` from the UI table rows, the code calls:
      `repo.reorder_streams(station.id, ordered_ids)`
    `reorder_streams` (repo.py lines 207-211) does only:
      `UPDATE station_streams SET position=? WHERE id=? AND station_id=?`
    — it never DELETEs any rows. Streams whose IDs do not appear in ordered_ids
    (i.e., rows the user removed from the table) are silently left in the DB.
    No "import primary URL" re-injection occurs; the bug is purely on the
    write/delete side.

## Eliminated

- Radio-Browser import re-injection: the save path does not touch the import
  module; it only calls update_stream/insert_stream/reorder_streams. The
  "canonical stream" theory was not the mechanism.
- Read-side (re-hydration) bug: the DB itself retained the removed rows, so the
  bug is on the write side, not the read side.

## Resolution

- **root_cause:** `EditStationDialog._on_save` calls `repo.reorder_streams`
  after building `ordered_ids` from the remaining UI table rows. `reorder_streams`
  only updates `position` values — it never deletes stream rows whose IDs are
  absent from the list. Removed streams therefore survive in the DB untouched.

- **fix:** Added `Repo.prune_streams(station_id, keep_ids)` to `repo.py`. It
  queries all existing stream IDs for the station and deletes any whose ID is
  not in `keep_ids`. Called unconditionally from `_on_save` in
  `edit_station_dialog.py` before the existing `reorder_streams` call.
  6 new tests added (4 in `test_repo.py`, 2 in `test_edit_station_dialog.py`).
  All 126 tests pass.

- **files_changed:**
  - `musicstreamer/repo.py` — added `prune_streams` method
  - `musicstreamer/ui_qt/edit_station_dialog.py` — call `prune_streams` in `_on_save`
  - `tests/test_repo.py` — 4 new `prune_streams` tests
  - `tests/test_edit_station_dialog.py` — 2 new dialog-level regression tests
