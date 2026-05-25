---
phase: 71
status: issues_found
reviewed: 2026-05-12
depth: standard
files_reviewed: 7
critical: 3
warning: 7
info: 8
---

# Phase 71: Code Review Report

**Reviewed:** 2026-05-12
**Depth:** standard
**Status:** issues_found

## Files Reviewed
- `musicstreamer/repo.py` (DB layer — station_siblings table + 3 CRUD methods)
- `musicstreamer/url_helpers.py` (find_manual_siblings, merge_siblings)
- `musicstreamer/settings_export.py` (ZIP round-trip for siblings)
- `musicstreamer/ui_qt/add_sibling_dialog.py` (NEW — AddSiblingDialog)
- `musicstreamer/ui_qt/edit_station_dialog.py` (chip-row rewrite, sibling_toast)
- `musicstreamer/ui_qt/now_playing_panel.py` (merged-display call-site swap)
- `musicstreamer/ui_qt/main_window.py` (sibling_toast wiring)

## Summary

Implementation is generally well-architected: follows `find_aa_siblings` placement convention, applies canonical (min/max) ordering for symmetric pairs, uses `INSERT OR IGNORE` for idempotency, and provides defensive guards (CASCADE FKs, CHECK constraint, self-link rejection in import). However, three interacting Critical defects ship together and should be fixed before release.

---

## Critical Issues

### CR-01: Duplicate station names silently collapse during ZIP import siblings pass

**File:** `musicstreamer/settings_export.py:351-385`

The `commit_import` second pass builds `name_to_id = {r["name"]: r["id"] for r in ... SELECT id, name FROM stations}`. The `stations` table does NOT enforce a UNIQUE constraint on `name` (`repo.py:23-33` — only `providers.name` is UNIQUE). When two stations share a name (legitimate case: SomaFM "Groove Salad" and a same-named station from another provider), the dict comprehension silently overwrites earlier entries. The "winning" station_id is whichever row SQLite returns last — non-deterministic. Sibling rows for the loser are then either wrongly attributed to the winner or silently lost.

**Fix:** Group sibling resolution by (name, provider) tuple, or capture station_id directly from the first-pass inserts via a parallel array.

### CR-02: Inconsistent sibling-merge precedence between EditStationDialog and NowPlayingPanel

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:638-693` vs `musicstreamer/url_helpers.py:261-276`

Two surfaces compute "the same set of siblings" with opposite dedup precedence:
- `EditStationDialog._refresh_siblings`: "Manual wins on conflict" (deviation Rule 1 from 71-03).
- `merge_siblings` used by `NowPlayingPanel`: AA wins on conflict (per RESEARCH Q2 + CONTEXT D-03).

If a user manually links a station that is ALSO AA-detected, the two surfaces disagree: Edit dialog shows it as a manual chip with `×` unlink; NowPlaying shows it as bare AA chip. Worse: clicking `×` in Edit dialog succeeds (Repo removes the link), but the chip immediately reappears as AA-only — from the user's POV, the unlink button is broken.

**Fix:** Pick one rule everywhere. Per CONTEXT D-03, AA-wins is documented — update `EditStationDialog._refresh_siblings` to mirror `merge_siblings` semantics.

### CR-03: AddSiblingDialog exclusion uses stale `_station.streams[0]` URL instead of live `url_edit.text()`

**File:** `musicstreamer/ui_qt/add_sibling_dialog.py:219-232`

`_repopulate_station_list` reads `current_url = self._current_station.streams[0].url` to build the AA exclusion set. But during EditStationDialog editing, the source of truth is `self.url_edit.text()` (per Pitfall 4). User can change URL, click `+ Add sibling` without saving, and the dialog opens with the OLD URL feeding `find_aa_siblings` — producing a stale exclusion set. Adding a station that becomes AA-detected under the new URL leads to CR-02's display inconsistency after save.

**Fix:** Pass live URL into `AddSiblingDialog.__init__` from the parent's `url_edit.text().strip()`.

---

## Warnings

### WR-01: EditStationDialog._refresh_siblings docstring claims live URL reactivity, but `url_edit.textChanged` is not connected to `_refresh_siblings`

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:624-651`

The docstring states "URL field is the source of truth during editing" and reads `self.url_edit.text().strip()` per refresh — but `_refresh_siblings` only fires on `_populate()`, `_on_unlink_sibling()`, `_on_add_sibling_clicked()`. No `textChanged` connection exists. Either wire textChanged with debounce (analogous to logo-fetch at line 353-356), or correct the docstring.

### WR-02: `repo.list_streams(station_id)` called twice in `_populate` + `_on_save`

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:512, 1332`

Pre-existing pattern, redundant SQL. Flag only.

### WR-03: `_on_provider_changed` filters by `currentText()` not `currentData()`

**File:** `musicstreamer/ui_qt/add_sibling_dialog.py:237-245`

Works today because `providers.name` is UNIQUE. Robust fix: use `currentData()` and filter by `provider_id`.

### WR-04: Bare `except Exception` in `_refresh_siblings`

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:662-667`

Should be `except sqlite3.Error` and log at `_log.warning` per existing convention. `# noqa: BLE001` suppresses lint rather than fixing root cause.

### WR-05: Merge-mode ZIP import is silently additive for siblings (no DELETE before INSERT)

**File:** `musicstreamer/settings_export.py:343-385`

If user A deletes a sibling in DB-A, exports, and re-imports to DB-B, the deleted link survives. D-07 ambiguous on this. Either document the additive semantic or `DELETE FROM station_siblings WHERE a_id = ? OR b_id = ?` before reinsert.

### WR-06: Phase 71 introduces new `lambda` connections in EditStationDialog despite QA-05 "no lambdas" claim

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:722-727, 766-770, 779-783`

Phase notes call out QA-05 bound-method compliance. The chip code uses `clicked.connect(lambda checked=False, sid=...: ...)`. Closest local pattern that achieves per-instance capture without lambdas is `_make_chip_toggle` (line 843-850). Use `functools.partial` or a closure factory.

### WR-07: `_on_accept(*args)` slot accepts two signal shapes — fragile

**File:** `musicstreamer/ui_qt/add_sibling_dialog.py:176-191`

Wire `accepted` and `itemDoubleClicked` to two named slots that share a `_accept_selected()` helper.

---

## Info

### IN-01: `db_init` ALTER TABLE migrations could be condensed via `_try_alter(con, sql, label)` helper
**File:** `musicstreamer/repo.py:78-120` — pre-existing, optional refactor.

### IN-02: RichText baseline comment in `edit_station_dialog.py:486-488` is accurate
Independent grep confirms count is 3. No defect.

### IN-03: `_on_provider_changed(index)` parameter unused; `noqa: ARG002` masks lint
**File:** `musicstreamer/ui_qt/add_sibling_dialog.py:155-164` — drop the param.

### IN-04: Hardcoded English strings — no i18n hook
Consistent with rest of codebase. Flag for future.

### IN-05: Manual-sibling tooltip `f"Linked from {provider_name}"` not HTML-escaped
**File:** `musicstreamer/ui_qt/edit_station_dialog.py:765` — Qt auto-detects RichText. Use `html.escape(...)`.

### IN-06: Truncation logic for toasts duplicated in two slots
**File:** `musicstreamer/ui_qt/edit_station_dialog.py:803-808, 821-826` — extract `_truncate_for_toast` helper.

### IN-07: `dlg._linked_station_name` accessed externally despite underscore prefix
**File:** `musicstreamer/ui_qt/edit_station_dialog.py:821` reads `dlg._linked_station_name` — rename or expose accessor.

### IN-08: `blockSignals(True)` over-engineered for a one-line state reset
**File:** `musicstreamer/ui_qt/add_sibling_dialog.py:159-163` — accept redundant filter pass.

---

## Recap

- **3 Critical:** CR-01 (silent duplicate-name data corruption on import), CR-02 (Edit vs NowPlaying display inconsistency — "X button doesn't work" UX bug), CR-03 (stale URL in AddSiblingDialog exclusion, compounds CR-02).
- **7 Warning:** WR-01 (docstring/code contract mismatch), WR-02 (two-call pattern), WR-03 (currentText vs currentData), WR-04 (overbroad except), WR-05 (additive merge import), WR-06 (new lambdas vs QA-05), WR-07 (`*args` slot smell).
- **8 Info:** db_init refactor, comment confirmation, unused params, i18n, tooltip escape, duplicated truncation, private-attr access, blockSignals simplification.

CR-01 + CR-02 + CR-03 interact and should be fixed before this phase ships. Recommended remediation: run `/gsd-code-review 71 --fix` after merging, then `/gsd-execute-phase 71.1` for a polish phase to address WR-class items.
