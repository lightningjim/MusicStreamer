---
phase: 71
fixed_at: 2026-05-12T18:50:00Z
review_path: .planning/phases/71-sister-station-expansion-1-add-ability-to-link-sister-statio/71-REVIEW.md
iteration: 1
findings_in_scope: 18
fixed: 13
skipped: 5
status: partial
---

# Phase 71: Code Review Fix Report

**Fixed at:** 2026-05-12T18:50:00Z
**Source review:** `.planning/phases/71-sister-station-expansion-1-add-ability-to-link-sister-statio/71-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 18 (3 Critical + 7 Warning + 8 Info)
- Fixed: 13 (3 Critical + 6 Warning + 4 Info)
- Skipped: 5 (1 Warning + 4 Info)

**Verification:** All 7 Phase-71-affected test files run green
(337 tests total = 271 in test_station_siblings + test_add_sibling_dialog
+ test_edit_station_dialog + test_now_playing_panel + test_settings_export
+ test_constants_drift, plus 66 in test_main_window_integration). No
regressions introduced; new regression tests added for CR-01, CR-02, CR-03.

## Fixed Issues

### CR-02: Align EditStationDialog dedup with merge_siblings (AA-wins)

**Files modified:** `musicstreamer/ui_qt/edit_station_dialog.py`, `tests/test_edit_station_dialog.py`
**Commit:** 547b3ec
**Applied fix:** Per CONTEXT D-03 + RESEARCH Q2, AA-wins is the documented design.
EditStationDialog._refresh_siblings previously built `manual_ids` and
suppressed AA chips for those station_ids — opposite of merge_siblings
(used by NowPlayingPanel). Fix builds `aa_ids` instead and skips manual
entries already in aa_ids. Both surfaces now render identical chip
variants for the AA+manual collision case. Two new regression tests:
- `test_aa_and_manual_collision_renders_as_aa_chip_no_x`
- `test_aa_and_manual_collision_matches_merge_siblings_semantics`

Pre-existing manual-chip tests updated to use a non-AA partner URL
(`http://example.com/somafm/manual-partner`) so they isolate the
manual-chip path regardless of dedup precedence. The original tests had
been relying on manual-wins to suppress an incidental AA match.

### CR-01: Disambiguate ZIP import siblings by (name, provider) tuple

**Files modified:** `musicstreamer/settings_export.py`, `tests/test_settings_export.py`
**Commit:** a8a0336
**Applied fix:** stations.name is NOT UNIQUE in the schema (verified
repo.py:23-33 — only providers.name is UNIQUE). Two stations can share a
name across different providers — the SomaFM-variant case is a primary
motivating use case for Phase 71. The pre-fix
`{r["name"]: r["id"] for r in SELECT ...}` dict comprehension silently
collapsed duplicate-name entries; "winning" station_id was
non-deterministic (no ORDER BY).

Fix replaces name_to_id with `key_to_id: dict[(name, provider_name), id]`
built from `LEFT JOIN stations + providers`. Editing-station lookup uses
the full (name, provider) tuple. For sibling-name resolution (the ZIP
carries only names, not partner provider), the code searches all provider
buckets — if exactly one matches, link; if multiple match, silently drop
(matches D-07 "unresolved names silently drop" for ambiguous-resolution
cases). Tracks `ambiguous_keys` for the defensive case where the same
(name, provider) appears twice.

Regression test `test_siblings_round_trip_with_cross_provider_duplicate_names`
seeds 4 stations across 2 providers with two "Groove Salad" entries each
linked to its provider's "Drone Zone"; asserts no cross-pollination.

### CR-03: Pass live url_edit.text() into AddSiblingDialog

**Files modified:** `musicstreamer/ui_qt/add_sibling_dialog.py`, `musicstreamer/ui_qt/edit_station_dialog.py`, `tests/test_add_sibling_dialog.py`
**Commit:** 710645c
**Applied fix:** AddSiblingDialog.__init__ gains an optional
`live_url: Optional[str]` parameter. None preserves backwards-compat
fallback to `streams[0].url`; an explicit empty string `""` is honored
(user cleared the URL field). `_repopulate_station_list` prefers
`live_url` over the stale persisted URL. EditStationDialog spawn site
(line 818 in original) now passes
`live_url=self.url_edit.text().strip()`.

Three regression tests:
- `test_live_url_drives_aa_exclusion` — live URL triggers AA exclusion
  when stale URL would not have.
- `test_stale_url_no_longer_drives_aa_exclusion` — stale URL ignored
  when live URL is supplied.
- `test_live_url_omitted_falls_back_to_streams` — backwards-compat path
  preserved when live_url is None.

### WR-01: Correct _refresh_siblings docstring re live URL reactivity

**Files modified:** `musicstreamer/ui_qt/edit_station_dialog.py`
**Commit:** e05ca6d
**Applied fix:** Docstring previously implied live URL reactivity; chose
to correct the docstring rather than wire textChanged with debounce.
Rationale documented: AA URL channel-key matching produces noisy
partial-keystroke matches; live debounce was considered and rejected.

### WR-04 + WR-06: Narrow except + replace lambdas with partial

**Files modified:** `musicstreamer/ui_qt/edit_station_dialog.py`
**Commit:** aa87e22
**Applied fix:**
- WR-04: `_refresh_siblings` now catches `sqlite3.Error` specifically
  instead of bare Exception + `# noqa: BLE001`. Adds module imports for
  `logging`, `sqlite3`, and `_log = logging.getLogger(__name__)`. On
  sqlite failure it logs at WARNING with `exc_info=True` and falls
  through to the empty chip row.
- WR-06: chip-construction lambdas (4 sites: AA-chip name button,
  manual-chip name button, manual-chip × button, plus the navigate signal)
  replaced with `functools.partial`. Two slot helpers added:
  `_emit_navigate_for_sibling(sibling_id, *_args, **_kwargs)` and
  `_emit_unlink_for_sibling(sibling_id, station_name, *_args, **_kwargs)`
  absorb the QPushButton.clicked(bool) payload via varargs.

### WR-05: Document additive merge-mode semantic for ZIP sibling import

**Files modified:** `musicstreamer/settings_export.py`
**Commit:** 1f8d3fc
**Applied fix:** D-07 was ambiguous; implementation chose additive but
the rationale was not recorded. Documented inline: if you unlink in DB-A,
export, and re-import to DB-B, the deleted link survives in DB-B
(non-destructive sync). `replace_all` mode is unaffected because
`DELETE FROM stations` cascades to station_siblings via ON DELETE CASCADE
(D-08). Future "replace siblings only" mode would be the right shape for
destructive sync if needed.

### WR-03 + WR-07: Filter by provider_id + split itemDoubleClicked slot

**Files modified:** `musicstreamer/ui_qt/add_sibling_dialog.py`
**Commit:** a50ee0b
**Applied fix:**
- WR-03: `_repopulate_station_list` now reads
  `self._provider_combo.currentData()` (the integer provider_id attached
  via `addItem(p.name, p.id)`) and compares against `st.provider_id`
  instead of comparing `currentText()` against `st.provider_name`. Robust
  against provider rename; one fewer string comparison per candidate.
- WR-07: `_on_accept(*args)` split into:
  - `_on_accept()` — zero-arg, wired to QDialogButtonBox.accepted
  - `_on_item_double_clicked(item)` — typed, wired to itemDoubleClicked
  - `_accept_selected()` — shared helper doing the validation + persist
    + accept

### IN-03: Drop unused param on _on_provider_changed / _on_search_changed

**Files modified:** `musicstreamer/ui_qt/add_sibling_dialog.py`
**Commit:** 3feaa6e
**Applied fix:** PySide6 accepts shorter slot signatures (Qt drops the
extra args). Removed `index: int` / `text: str` parameters and the
accompanying `# noqa: ARG002` suppressions.

### IN-05: HTML-escape provider_name in chip tooltip

**Files modified:** `musicstreamer/ui_qt/edit_station_dialog.py`
**Commit:** 3feaa6e
**Applied fix:** Added `import html` and routed `provider_name` through
`html.escape(..., quote=True)` in the
`f"Linked from {provider_name}"` tooltip. Qt auto-detects rich text on
`setToolTip`; user-controlled `provider_name` strings containing `<`,
`>`, or `&` would have rendered as HTML markup. Defense-in-depth mirrors
the existing `render_sibling_html` treatment of station_name.

### IN-06: Extract _truncate_for_toast helper

**Files modified:** `musicstreamer/ui_qt/edit_station_dialog.py`
**Commit:** 3feaa6e
**Applied fix:** Extracted the duplicated 40-char-with-U+2026
truncation pattern from `_on_unlink_sibling` and
`_on_add_sibling_clicked` into a single `@staticmethod _truncate_for_toast`
helper. Single source of truth for the rule.

### IN-07: Public accessor for linked_station_name

**Files modified:** `musicstreamer/ui_qt/add_sibling_dialog.py`, `musicstreamer/ui_qt/edit_station_dialog.py`
**Commit:** 3feaa6e
**Applied fix:** Added a read-only `@property linked_station_name`
delegating to `self._linked_station_name`. EditStationDialog now reads
via the property. The underscored backing attribute is preserved for
backwards compatibility with any code path that may still touch it.

### IN-08: Drop blockSignals dance in _on_provider_changed

**Files modified:** `musicstreamer/ui_qt/add_sibling_dialog.py`
**Commit:** 3feaa6e
**Applied fix:** Replaced
`blockSignals(True) / setText("") / blockSignals(False)` triplet with a
plain `setText("")` — accepts one redundant `_repopulate_station_list`
call from the textChanged → _on_search_changed signal. Cost is
O(stations) over a 50-200 in-memory list — microseconds at modal-open
scale.

## Skipped Issues

### WR-02: list_streams(station_id) called twice in _populate + _on_save

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:512, 1360`
**Reason:** Pre-existing pattern flagged as "Flag only" by the reviewer.
The two call sites serve different purposes: `_populate` reads the
initial dialog state at construction time; `_on_save` reads fresh
persisted state at save time to merge server-side fields (label,
stream_type, sample_rate_hz, bit_depth) that the editor table does not
expose. Caching the populate-time result would risk overwriting those
fields with stale values if the user edits + saves quickly. Not in
Phase 71 scope.
**Original issue:** Pre-existing pattern, redundant SQL.

### IN-01: db_init ALTER TABLE migrations could be condensed

**File:** `musicstreamer/repo.py:78-120`
**Reason:** Explicitly tagged "pre-existing, optional refactor" — not
introduced by Phase 71 and touches pre-existing migration code outside
the phase boundary. Out of scope for a fix pass.
**Original issue:** db_init ALTER TABLE migrations could be condensed
via `_try_alter(con, sql, label)` helper.

### IN-02: RichText baseline comment is accurate

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:486-488`
**Reason:** Reviewer explicitly states "No defect" — the comment is
accurate (independent grep confirms 3 RichText sites). Nothing to fix.
**Original issue:** RichText baseline comment in `edit_station_dialog.py:486-488`
is accurate.

### IN-04: Hardcoded English strings — no i18n hook

**File:** (project-wide)
**Reason:** Reviewer notes "Consistent with rest of codebase. Flag for
future." Out of scope for Phase 71 fix pass; would require a project-wide
i18n architecture decision (gettext? Qt linguist?) that does not exist.
**Original issue:** Hardcoded English strings — no i18n hook.

---

_Fixed: 2026-05-12T18:50:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
