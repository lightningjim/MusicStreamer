---
phase: 99-migrate-avatar-add-path-tests-off-removed-url-edit-widget-ga
reviewed: 2026-06-28T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - tests/test_twitch_provider_assign.py
  - tests/test_edit_station_dialog_avatar.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 99: Code Review Report

**Reviewed:** 2026-06-28
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Test-only gap-closure phase. The migration moves the avatar add-path tests off the
removed `url_edit` widget and onto the Phase-97 streams-table / `_on_canonical_cell_changed`
path. I verified the migrated tests against the live production code in
`musicstreamer/ui_qt/edit_station_dialog.py`.

Verification results (the review's stated focus):

- **No silently-weakened assertions.** The diff only swaps the URL *input mechanism*;
  every `assert` block is byte-for-byte unchanged. Behavioral coverage is preserved.
- **`_canonical_row` / `_COL_URL` are used correctly.** `_COL_URL = 0` (prod line 279)
  is imported in `test_edit_station_dialog_avatar.py`. After `_populate()` with one
  stream row and no `canonical_stream_id`, `_canonical_row` resolves to `0`
  (prod lines 718-727), so `streams_table.item(d._canonical_row, _COL_URL)` is a live
  item — no None-deref risk. `_on_canonical_cell_changed(0, 0)` clears the guard at
  prod line 1384 and reaches the refresh body. The migration is functionally correct.
- **No dead references.** `grep` confirms zero remaining `url_edit` / `_on_url_text_changed`
  references in either file.

One real test-robustness regression introduced by the migration (WR-01) plus two
pre-existing unused imports (IN-01, IN-02).

The CONVENTION rule packs are JS/TS-only and skip gracefully on `.py` files (D-05),
so no convention findings are emitted.

## Warnings

### WR-01: Twitch derivation tests now depend on a URL hidden in a shared fixture

**File:** `tests/test_twitch_provider_assign.py:48` (fixture) driving `:128`, `:181`, `:402` (assertions)
**Issue:** Before Phase 97 the URL that drives the `Twitch:`-provider derivation was set
*explicitly in each test body* via `d.url_edit.setText("https://www.twitch.tv/twitchdev")`,
so the test's load-bearing input sat next to the assertion. After this migration the
derivation source is `_get_canonical_url_live()` (prod line 2027), which reads the canonical
streams-table row populated from `repo.list_streams` — and that URL now lives only in the
shared `repo` fixture (line 48). The input is no longer redundant with `url_edit`; it is
authoritative and remote. A future edit to the fixture's `url=` value would silently change
the meaning of `test_save_derives_provider_for_blank_twitch`,
`test_save_preserves_manual_provider_for_twitch`, and
`test_save_manual_provider_not_overwritten_still_holds` without touching the tests, and the
"Twitch: twitchdev" assertions could pass or fail for reasons invisible at the call site.
The replacement comment ("URL pre-loaded from repo.list_streams via _populate()") documents
the coupling but does not guard it.
**Fix:** Add a cheap precondition that pins the load-bearing input at the point of use, e.g.
right after `qtbot.addWidget(d)`:
```python
# Pin the derivation-driving input so a fixture change can't silently re-scope the test.
assert d._get_canonical_url_live().strip() == "https://www.twitch.tv/twitchdev"
```
(or set the canonical cell explicitly as the avatar test now does). This restores
test-local intent without reintroducing `url_edit`.

## Info

### IN-01: Unused `inspect` import

**File:** `tests/test_twitch_provider_assign.py:10`
**Issue:** `import inspect` is never referenced (`grep` finds no `inspect.` usage; the
source-grep guards use `importlib.resources`). Pre-existing, not introduced by this phase,
but it is in a reviewed file.
**Fix:** Remove the `import inspect` line.

### IN-02: Unused `call` import

**File:** `tests/test_edit_station_dialog_avatar.py:10`
**Issue:** `from unittest.mock import MagicMock, call, patch` — `call` is never constructed
(the `.call_args` / `.call_args_list` references are mock attributes, and the textual "call"
hits are inside docstrings/string literals). `MagicMock`, `patch`, and `inspect` are all used.
Pre-existing.
**Fix:** Drop `call` from the import: `from unittest.mock import MagicMock, patch`.

---

_Reviewed: 2026-06-28_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
