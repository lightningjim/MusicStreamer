---
phase: 97-resolve-station-url-duplication-between-the-top-level-standa
reviewed: 2026-06-24T03:29:18Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - musicstreamer/aa_live.py
  - musicstreamer/models.py
  - musicstreamer/repo.py
  - musicstreamer/ui_qt/add_sibling_dialog.py
  - musicstreamer/ui_qt/edit_station_dialog.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - musicstreamer/ui_qt/station_filter_proxy.py
  - musicstreamer/url_helpers.py
  - tests/test_aa_siblings.py
  - tests/test_edit_station_dialog.py
  - tests/test_repo.py
  - tests/test_url_helpers.py
findings:
  critical: 1
  warning: 5
  info: 3
  total: 9
status: resolved
---

# Phase 97: Code Review Report

**Reviewed:** 2026-06-24T03:29:18Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 97 unifies station URL duplication behind a `canonical_stream_id` FK and a
derived `Station.canonical_url` property. The consumer migrations
(`aa_live.get_di_channel_key`, `url_helpers.find_aa_siblings`,
`url_helpers.pick_similar_stations`, `station_filter_proxy.filterAcceptsRow`,
`add_sibling_dialog._repopulate_station_list`) are clean: each reads
`station.canonical_url` and the property's four-branch resolution
(FK → position-1 → "") is correct and well-tested.

The repo layer (schema ALTER, backfill, `set_canonical_stream`, FK
`ON DELETE SET NULL`, Station hydration) is sound and the parameterized SQL is
injection-safe.

The defect surface is concentrated in the `EditStationDialog` rewire. There is
**one BLOCKER**: marking a *brand-new* (unsaved) stream row as canonical and
saving silently anchors the canonical to the *wrong* stream, because the
freshly-inserted row's `stream_id` is never written back into the table item
that the canonical-persist step reads. Several WARNINGs cover the stale
row-index lambda capture on the canonical star buttons after reordering, a
position-tie ordering mismatch between the dialog and the model, and a couple of
robustness gaps in the save path.

## Critical Issues

### CR-01: New canonical stream row persists the wrong canonical FK on save

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:2010-2035`
**Issue:**
In `_on_save`, when a row is a newly-added stream (`stream_id is None`), the loop
calls `repo.insert_stream(...)` and appends the returned `new_id` to
`ordered_ids`, but it **never writes `new_id` back into the URL item's
`Qt.UserRole`**:

```python
else:
    new_id = repo.insert_stream(station.id, url, label="", quality=quality, ...)
    if isinstance(new_id, int):
        ordered_ids.append(new_id)
    # <-- url_item.setData(Qt.UserRole, new_id) is missing
```

Then the canonical-persist step reads the canonical row's id directly from the
item:

```python
_can_item = table.item(self._canonical_row, _COL_URL) if self._canonical_row >= 0 else None
_can_stream_id = _can_item.data(Qt.UserRole) if _can_item else None  # None for a new row
if _can_stream_id not in ordered_ids:           # None not in ordered_ids -> True
    _can_stream_id = ordered_ids[0] if ordered_ids else None  # WRONG: falls back to first stream
repo.set_canonical_stream(station.id, _can_stream_id)
```

For a new station (`is_new=True`) the pre-added blank row is always a new row, so
the very common flow "create station, paste the only URL, save" marks that row
canonical with `_canonical_row=0` — and since its `UserRole` is `None`, the
fallback happens to pick `ordered_ids[0]` (the same row's new id) by luck. But as
soon as the user has **more than one stream and stars a newly-added row that is
not position-1**, the canonical is silently persisted as the position-1 stream
instead of the starred new stream. This is a correctness/data-anchor bug that
defeats the entire feature for the canonical use case (anchor metadata to a
secondary/non-first stream that was just added).

Note the same staleness also affects the `_populate` round-trip: after save the
in-memory item still carries `UserRole=None`, so a subsequent star-click +
re-save in the same dialog session re-triggers the wrong-fallback path.

**Fix:** write the new id back onto the item inside the insert branch so the
canonical-persist step (and any later save in the same session) can resolve it:

```python
else:
    new_id = repo.insert_stream(station.id, url, label="", quality=quality,
                                position=position, stream_type="", codec=codec,
                                bitrate_kbps=bitrate_kbps)
    if isinstance(new_id, int):
        ordered_ids.append(new_id)
        if url_item is not None:
            url_item.setData(Qt.UserRole, new_id)  # so canonical resolution can find it
```

Add a regression test: build a dialog with one existing stream, add a second
row, star the second row, `_on_save()`, and assert
`repo.set_canonical_stream` was called with the *new* stream id (not
`ordered_ids[0]`).

## Warnings

### WR-01: Canonical star button lambda captures a stale row index after reorder

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:1188` (with `_swap_rows` at 1227-1245)
**Issue:**
Each canonical button is wired with `lambda checked, r=row: self._on_canonical_btn_clicked(r)`,
binding `r` to the row index *at creation time*. `_swap_rows` (used by Move
Up/Move Down) moves the `QToolButton` cell widgets between rows via
`setCellWidget` but does **not** rebind the lambda. After a swap, clicking a
star button calls `_on_canonical_btn_clicked` with the button's *original* row,
so `self._canonical_row` is set to the wrong row and the wrong stars are
checked/unchecked. `_on_move_up/_on_move_down` patch `_canonical_row` to track
content, but a *user click* on a star after any reorder still uses the stale
index. This produces a canonical marker that visually points at one row but
persists another.

**Fix:** resolve the row dynamically at click time instead of capturing it.
Either look up the button's current row via
`self.streams_table.indexAt(btn.pos()).row()` / `cellWidget` scan, or pass the
button object and derive its row:

```python
canonical_btn.clicked.connect(
    partial(self._on_canonical_btn_clicked_for_widget, canonical_btn)
)
# handler:
def _on_canonical_btn_clicked_for_widget(self, btn, *_):
    for r in range(self.streams_table.rowCount()):
        if self.streams_table.cellWidget(r, _COL_CANONICAL) is btn:
            self._on_canonical_btn_clicked(r)
            return
```

### WR-02: Dialog assumes row 0 == position-1, but `list_streams` ordering is not tie-broken

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:717,735` and `musicstreamer/repo.py:571-579`
**Issue:**
`_populate` defaults `_canonical_row = 0` (and treats row 0 as the position-1
fallback), relying on `list_streams` returning the position-1 stream first.
`list_streams` orders by `position` only (`ORDER BY position`), with no secondary
`id` tiebreaker. `Station.canonical_url`'s fallback, however, sorts by
`(position, id)` (`models.py:65`). When two streams share the same `position`,
SQLite's row order is undefined, so the dialog's "row 0" and the model's
`sorted(..., key=(position, id))[0]` can disagree. The result: the dialog shows
the star on one stream while `canonical_url` (and the persisted fallback in
CR-01's branch) resolves to a different one — an inconsistent canonical anchor.

**Fix:** make the two orderings identical. Either change `list_streams` to
`ORDER BY position, id` (matches the model and the backfill's
`ORDER BY position ASC, id ASC`), or have `_populate` compute the fallback row
with the same `(position, id)` key the model uses.

### WR-03: `_can_stream_id not in ordered_ids` membership test is fragile

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:2033`
**Issue:**
The deleted-stream fallback `if _can_stream_id not in ordered_ids:` is correct
only because `ordered_ids` never contains `None`. With CR-01 unfixed,
`_can_stream_id` is frequently `None` for new canonical rows, which silently
collapses into the "stream was deleted" fallback path even though the stream was
*not* deleted — masking the real bug as a benign-looking fallback. Even after
CR-01 is fixed, the comment ("If canonical stream was deleted") does not match
the actual condition (it also fires for `None`/unparseable ids). The logic
should distinguish "canonical row resolved to a real id that is absent from
ordered_ids (deleted)" from "canonical row had no id at all".

**Fix:** guard explicitly:

```python
if _can_stream_id is None or _can_stream_id not in ordered_ids:
    _can_stream_id = ordered_ids[0] if ordered_ids else None
```

and update the comment to reflect both cases. (This is a clarity/robustness fix;
CR-01 is the substantive defect.)

### WR-04: `_get_canonical_url_live` does not strip — dirty-baseline can drift vs. saved value

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:795,1251-1262`
**Issue:**
`_snapshot_form_state` stores `"canonical_url": self._get_canonical_url_live()`
(un-stripped). Every *consumer* call site strips it
(`_get_canonical_url_live().strip()` at 875, 1100, 1481, 1497, 1557, 1673, 1936,
2073). The dirty snapshot is the only un-stripped read. This is internally
consistent for dirty-compare (baseline and live both un-stripped), so it does
not currently mis-fire, but it is an inconsistency that invites a future bug:
any change that strips at snapshot time (or in one of the two snapshot calls but
not the other) would make a clean dialog report dirty. Stream cells were
deliberately captured raw per the docstring; the canonical URL should follow the
same documented rationale or be stripped consistently.

**Fix:** either document that `canonical_url` is intentionally captured raw (one
line in the `_snapshot_form_state` docstring), or strip it the same way as the
consumers to remove the asymmetry.

### WR-05: `_populating` guard does not cover `setCellWidget`-driven canonical button construction during populate

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:702-738,1187-1188`
**Issue:**
During `_populate`, `_add_stream_row` is called under `self._populating = True`,
which the `cellChanged` handler honors. But each `_add_stream_row` also creates a
canonical `QToolButton` and calls `canonical_btn.setChecked(row == self._canonical_row)`.
At populate time `self._canonical_row` is still its pre-resolution value (`0`
from line 717 set *before* the loop, or `-1` on the very first populate path),
so every row's button is initialized against a not-yet-final canonical row, then
re-synced afterward by `_sync_canonical_buttons()` (line 738). The re-sync makes
the end state correct, but `setChecked` on a checkable `QToolButton` can emit
`toggled`; if any future wiring listens to `toggled` (today only `clicked` is
wired, so no live bug) this becomes a spurious-canonical-change source. Flagging
as a latent robustness gap given the feature's reliance on button state.

**Fix:** set the canonical row *before* building rows, or construct the buttons
unchecked during populate and rely solely on `_sync_canonical_buttons()` for the
initial checked state.

## Info

### IN-01: `_on_url_text_changed` is now a dead no-op shim

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:1473-1477`
**Issue:** With `url_edit` removed (D-01), `_on_url_text_changed` is no longer
connected to any signal and is preserved only as a no-op "in case external
callers exist." A grep of the package shows no caller. Dead code that will
confuse future readers about which path is live (`_on_canonical_cell_changed` is
the real one).
**Fix:** remove the method, or keep it but tighten the docstring to state
definitively that it is retained only for test back-compat (cite the test if
one exists).

### IN-02: Other `streams[0]` consumers not migrated (out of scope but inconsistent)

**File:** `musicstreamer/ui_qt/live_refresh_dialog.py:455,613`; `musicstreamer/ui_qt/discovery_dialog.py:434`
**Issue:** Phase 97 migrated 5 metadata/derivation consumers to `canonical_url`,
but `live_refresh_dialog.py` (`self._station.streams[0].id`,
`chosen.streams[0].id`) and `discovery_dialog.py` (`streams[0]`) still index
positionally. These are outside this phase's declared file scope and may be
intentionally positional (live-URL write target vs. metadata anchor), but the
split between "metadata reads canonical / writes stay positional" is undocumented
at those call sites and is a likely source of future confusion.
**Fix:** add a one-line comment at each remaining `streams[0]` site clarifying
why it is *not* canonical (write target / primary playback stream), so the
distinction from the Phase 97 reads is explicit.

### IN-03: Backfill/model ordering tiebreaker documented inconsistently

**File:** `musicstreamer/repo.py:402-409` vs `musicstreamer/models.py:65`
**Issue:** The backfill UPDATE uses `ORDER BY position ASC, id ASC` and the model
fallback uses `sorted(..., key=lambda s: (s.position, s.id))` — these agree
(good). `list_streams` (`ORDER BY position`) is the odd one out (see WR-02).
Worth a short comment in `list_streams` noting that callers relying on
"first == canonical fallback" must account for the missing `id` tiebreaker.
**Fix:** align as described in WR-02 and drop a clarifying comment.

---

_Reviewed: 2026-06-24T03:29:18Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

---

## Resolution (applied during execute-phase, 2026-06-24)

Substantive correctness findings fixed inline with regression tests
(commits `347ded42`, `10bdd33a`):

- **CR-01 (BLOCKER) — RESOLVED.** `_on_save` now writes `insert_stream()`'s id
  back onto the URL item, so a newly-added starred row persists its own
  canonical FK. Regression: `test_save_persists_new_canonical_row_with_real_id`.
- **WR-01 — RESOLVED (and a deeper bug fixed).** Investigation found `_swap_rows`
  was *destroying* the canonical star widgets on reorder (sequential
  `setCellWidget` deletes the replaced widget). Fix: stars stay in place, resolve
  their row dynamically at click time, and re-sync checked state via
  `_sync_canonical_buttons()` after move up/down. Regression:
  `test_canonical_star_survives_and_tracks_content_after_reorder`.
- **WR-02 — RESOLVED.** `list_streams` now `ORDER BY position, id`, matching
  `Station.canonical_url` and the backfill.
- **WR-03 — RESOLVED.** Save fallback guard now explicitly handles
  `_can_stream_id is None`.

Deferred as latent/cosmetic (no functional impact, tracked for future cleanup):
**WR-04** (un-stripped canonical URL in dirty snapshot — internally consistent),
**WR-05** (populate-time `setChecked` against not-yet-final row — re-synced;
no `toggled` listener today), **IN-01** (dead `_on_url_text_changed` shim),
**IN-02** (out-of-scope `streams[0]` write-target consumers), **IN-03** (ordering
tiebreaker doc comment).
