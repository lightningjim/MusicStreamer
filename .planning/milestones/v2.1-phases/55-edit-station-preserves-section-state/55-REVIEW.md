---
phase: 55-edit-station-preserves-section-state
reviewed: 2026-05-01T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - musicstreamer/ui_qt/station_list_panel.py
  - musicstreamer/ui_qt/station_tree_model.py
  - tests/test_station_list_panel.py
  - tests/test_station_tree_model.py
findings:
  critical: 0
  warning: 0
  info: 3
  total: 3
status: issues_found
---

# Phase 55: Code Review Report

**Reviewed:** 2026-05-01
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found (3 INFO; no BLOCKERs, no WARNINGs)

## Summary

Adversarial review of the BUG-06 fix: capture/restore provider-tree expansion across `StationListPanel.refresh_model()`. The implementation is tight and the four high-risk contracts called out in the phase context all hold:

1. **Pitfall #2 guard present** — `_restore_expanded_provider_names` at `station_list_panel.py:404-407` calls `proxy.mapFromSource(...)` and explicitly skips `if not proxy_idx.isValid()` before any `tree.expand(...)`. Capture-side guard at `station_list_panel.py:373-377` is also present.
2. **D-03 negative contract held** — `refresh_model` body (`station_list_panel.py:314-327`) does NOT call `_sync_tree_expansion()`. The body is capture / `model.refresh` / restore / `_populate_recent` / `_build_chip_rows`, in that order. `test_refresh_model_does_not_call_sync_tree_expansion` locks this in.
3. **D-05 positive lock held** — All four filter-change handlers still call `_sync_tree_expansion()`: `_on_search_changed:494`, `_on_provider_chip_clicked:504`, `_on_tag_chip_clicked:514`, `_clear_all_filters:530`. `test_filter_change_still_calls_sync_tree_expansion` locks this in.
4. **Suffix-bypass accessor correct** — `StationTreeModel.provider_name_at` (`station_tree_model.py:62-72`) reads `node.provider_name` (the raw `_TreeNode` field set in `_populate`), not `Qt.DisplayRole`. The `" (N)"` count suffix on `label` is preserved untouched. `test_provider_name_at_preserves_parens_in_raw_provider_name` locks the parens-in-name regression case.
5. **Capture key is a string set, not QModelIndex** — `_capture_expanded_provider_names` returns `tuple[set[str], set[str]]` (line 349). Provider names survive `beginResetModel`/`endResetModel`; QModelIndex would not.
6. **No scope creep** — The only non-trivial source change outside the four behaviors is a docstring tweak in `refresh_recent` (`_sync_tree_expansion()` → `_sync_tree_expansion`, prose-only) that is documented in `55-01-SUMMARY.md` Deviation #2 as gate-isolation. Verified by `git diff 108d515^..108d515 -- musicstreamer/ui_qt/station_list_panel.py`.

No bugs were found in the implementation. Three INFO-level test/style observations are recorded below for future polish; none block ship.

## Info

### IN-01: `test_refresh_model_preserves_state_under_active_filter` is mooted by filter-driven `_sync_tree_expansion`

**File:** `tests/test_station_list_panel.py:670-706`
**Issue:** The test expands `first_proxy` manually at line 678, then sets `_search_box.setText("a")` at line 686. The text-change signal hits `_on_search_changed`, which calls `_sync_tree_expansion()` → `expandAll()` because a filter is now active. So by the time `panel.refresh_model()` runs (line 689), every visible group is expanded by the filter handler — not by the user's pre-filter manual expand. The post-refresh assertion at line 701 (`isExpanded(proxy_idx) is True`) holds for the right reason in production, but the test cannot distinguish "captured user expansion preserved across refresh" from "filter pre-expanded everything, refresh was a no-op." A stronger test would set the search text first, then expand a SPECIFIC group while leaving others collapsed (impossible under `expandAll`), or read the `_proxy.has_active_filter()` state and assert that capture/restore drove expansion independently. Documenting as a lock-strength weakness, not a correctness defect — the production code is still correct.
**Fix:** Either (a) remove this test in favor of `test_refresh_model_preserves_user_expanded_groups` + `test_refresh_model_handles_filtered_out_expanded_provider_safely` which already cover the meaningful contracts, or (b) reshape it so the user's manual expansion is distinguishable from `_sync_tree_expansion`'s blanket expand:
```python
# Apply filter first (which expands all)
panel._search_box.setText("a")
# Now manually COLLAPSE one group to create a distinguishable user state
collapsible_proxy = panel._proxy.index(0, 0)
panel.tree.collapse(collapsible_proxy)
target_name = panel.model.provider_name_at(
    panel._proxy.mapToSource(collapsible_proxy).row()
)
panel.refresh_model()
# Now the test can assert the user's COLLAPSE survived refresh — something
# expandAll() cannot have caused.
```

### IN-02: Inconclusive-pass branch in `test_refresh_model_preserves_state_under_active_filter` has no assertion

**File:** `tests/test_station_list_panel.py:705-706`
**Issue:** The for-loop at line 695 iterates `panel.model.rowCount()` looking for `target_name`. If the model never contains `target_name` post-refresh (the comment at line 705-706 acknowledges the model "legitimately reshaped it out"), the function falls off the end with no assertion. The test would silently PASS even though it tested nothing. Combined with IN-01 above, the test can pass for one of three different reasons (target found and expanded; target filtered out and skipped; target gone entirely), only the first of which exercises the contract under review.
**Fix:** At minimum, add a `pytest.fail` or `pytest.skip` with a message in the fall-through path so silent passes become visible:
```python
import pytest
# end of loop body unchanged
pytest.skip(
    f"target provider {target_name!r} reshaped out of post-refresh model — "
    "cannot exercise D-04 under filter; broaden fixture or pick a different target"
)
```
Or fold this behavior into a stronger test per IN-01.

### IN-03: `_TreeNode.provider_name: Optional[str]` uses pre-PEP-604 typing in a project that prefers `X | Y`

**File:** `musicstreamer/ui_qt/station_tree_model.py:33,62`
**Issue:** The new `_TreeNode.provider_name: Optional[str] = None` field (line 33) and the new `provider_name_at(row) -> Optional[str]` accessor signature (line 62) use `Optional[T]` rather than the project-preferred `T | None`. `.planning/codebase/CONVENTIONS.md` explicitly states "Union types prefer modern `X | Y` syntax over `Union[X, Y]` (Python 3.10+)." The implementer documented in `55-01-SUMMARY.md` (Decisions Made) the choice: "Used `Optional[str]` (not `str | None`) ... to match the surrounding `station_for_index` style in the same file." Local consistency is reasonable, but the surrounding file's style itself drifts from the project convention — this fix entrenches the drift slightly further. Pure style; no behavioral impact.
**Fix:** Either (a) accept the local-consistency decision and move on (already documented), or (b) take a follow-up cleanup pass to migrate `station_tree_model.py`'s `Optional[Station]` and the new `Optional[str]` annotations together to `Station | None` / `str | None`. Given the existing local pattern, leaving this as-is is also defensible.

---

## Negative findings (verified absent)

For traceability, the following potential defects were specifically searched for and **not found**:

- **Stale `_sync_tree_expansion()` call in `refresh_model` body** — verified absent (`grep -B2 -A8 "def refresh_model" musicstreamer/ui_qt/station_list_panel.py | grep -c "_sync_tree_expansion()"` returns 0).
- **Missing `.isValid()` guard on `mapFromSource` in restore** — guard present at `station_list_panel.py:405-406` and capture-side at `:374-375`.
- **`provider_name_at` parsing the `" (N)"` suffix off `Qt.DisplayRole`** — does not parse the display label; reads the raw `_TreeNode.provider_name` field directly. Regression-locked by `test_provider_name_at_preserves_parens_in_raw_provider_name`.
- **QModelIndex used as capture key (would invalidate across `beginResetModel`)** — capture returns `set[str]`, not indices. Provider names are stable across reset.
- **Scope creep beyond the four BUG-06 contracts** — the only out-of-mandate edit (refresh_recent docstring tweak) is documented in `55-01-SUMMARY.md` Deviation #2 with a non-functional rationale (acceptance-grep gate isolation).
- **First-load auto-expand-everything regression** — `__init__` constructs `StationTreeModel` directly (line 272) and never calls `refresh_model`. Construction-time tree starts collapsed by default; the brand-new-group-defaults-to-expanded path in `_restore_expanded_provider_names` (D-06) only fires through `refresh_model`. `test_provider_groups_collapsed_after_construction` locks the construction default.
- **Lambda usage in tests violating QA-05** — phase context explicitly carves out monkeypatch lambdas as legitimate; both lambdas at `tests/test_station_list_panel.py:744,764` are in `monkeypatch.setattr` calls, not Qt signal/slot wiring.

## Pre-existing issues (out of Phase 55 scope, not flagged)

For the record, the following were observed but are pre-existing and unrelated to BUG-06:

- `_build_chip_rows()` is called from both `__init__` (line 245) and `refresh_model` (line 327) but never clears the existing chip buttons before appending — chips accumulate across refreshes. Verified pre-existing via `git show 108d515^:musicstreamer/ui_qt/station_list_panel.py` (the prior `refresh_model` already called `_build_chip_rows()`). Out of scope for Phase 55.
- `select_station` (line 430) calls `self.tree.expand(proxy_idx.parent())` without `.isValid()` guards on either `proxy_idx` or `proxy_idx.parent()`. Pre-existing from Phase 999.1-02 (commit `0add519`). Out of scope.
- Two existing tests fail on the un-edited base (`test_filter_strip_hidden_in_favorites_mode`, `test_refresh_recent_updates_list`) — already documented in `.planning/phases/55-edit-station-preserves-section-state/deferred-items.md`. Out of scope.

---

_Reviewed: 2026-05-01_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
