# Phase 55: Edit Station Preserves Section State - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-30
**Phase:** 55-edit-station-preserves-section-state
**Areas discussed:** Scope of the fix, Filter-active behavior post-save, New provider groups post-save

---

## Scope of the fix

### Q1: Should the fix preserve provider-tree expand state across all five callers, or just the edit-save path called out in SC #1/#2?

| Option | Description | Selected |
|--------|-------------|----------|
| All five callers (Recommended) | Fix at the layer where the damage happens — make `refresh_model()` (or `_sync_tree_expansion()`) preserve expansion by default, so edit, create, delete, discovery import, and settings import all benefit. Same code change, broader coverage. Matches Phase 50's pattern of fixing the layer that actually destroys state. | ✓ |
| Edit-save only | Narrowly addresses SC #1/#2: route only `EditStationDialog.station_saved` through a new state-preserving refresh, leave create/delete/import on the existing collapseAll path. Smaller diff but the bug stays for the other four flows. | |
| Edit-save + create-new (the two save paths) | The two `EditStationDialog.station_saved` emitters get the new path; delete and the two import paths stay on the old path. Reasoning: 'save' is one mental category for the user. | |

**User's choice:** All five callers
**Notes:** SC #1/#2 is the visible promise, but the underlying defect is shared across edit, new-station, delete, discovery import, and settings import paths.

### Q2: How should the state-preserving behavior be exposed in StationListPanel's API?

| Option | Description | Selected |
|--------|-------------|----------|
| Modify `refresh_model()` in place (Recommended) | `refresh_model()` itself becomes state-preserving (capture expansion before `model.refresh`, restore after). Any current or future caller benefits automatically. `_sync_tree_expansion()`'s filter-driven auto-expand becomes the fallback for groups with no captured state. Smallest, most maintainable diff. | ✓ |
| Add a new sibling method | Keep `refresh_model()` unchanged. Add `refresh_model_preserving_expansion()` (or similar) and update the 5 call sites in `main_window.py`. Two methods to maintain; future callers can pick the wrong one. | |
| Drop `_sync_tree_expansion` entirely | Remove the auto-expand-when-filter-active behavior from `refresh_model()` altogether. Capture/restore manual state on refresh. Filter changes get their own dedicated path (the filter-changed signal handlers, not refresh). | |

**User's choice:** Modify `refresh_model()` in place
**Notes:** Single API truth. No risk of future callers picking the wrong method.

---

## Filter-active behavior post-save

### Q1: After a save with a filter active, what should happen to the user's per-group expand/collapse state?

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve manual state always (Recommended) | Refresh on save preserves what the user had: groups they collapsed stay collapsed even when a filter is active. Filter-driven 'expand-all-matching' becomes the responsibility of the filter-CHANGE path (search input changed, chip clicked) — not the refresh-AFTER-save path. Matches user mental model: 'I just saved a station, don't reshape my tree.' | ✓ |
| Preserve manual state, but auto-expand only newly-matching groups | If a save makes a group newly match the active filter (e.g., user retagged a station so it now passes a tag-chip filter), expand that one group. Pre-existing groups keep their manual state. More logic, more edge cases, but maybe friendlier for tag-based searches. | |
| Keep current expandAll-when-filter behavior | Don't override the filter-driven expansion at all — a filter that's active still expands everything on refresh. Only fixes the no-filter case. Probably violates SC #1 ("expanded sections remain expanded") when reading literally, since the bug repro under filter is the worst case. | |

**User's choice:** Preserve manual state always
**Notes:** SC #1/#2 honored under the worst-case (filter-active) condition.

### Q2: Should filter-CHANGE events still trigger the existing expandAll-when-filter-active behavior, or should that go away entirely?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep filter-change auto-expand (Recommended) | When the user types in search or clicks a chip, the tree still expands matching groups so they can see results. `_sync_tree_expansion()` stays — just stops being called from `refresh_model()`. Refresh preserves manual state; filter-change drives the auto-expand. Two distinct paths, each doing one thing. | ✓ |
| Remove filter-change auto-expand too | Even when typing into search, the tree doesn't auto-expand groups — user must manually expand to see matches under each provider. More 'pure' but degrades discoverability when searching across providers. | |
| Keep auto-expand on filter-change AND on filter-CLEAR | When the user clears all filters, return groups to the default state (collapsed). Same as today's collapseAll-when-no-filter, but only triggered on filter-cleared, not on every refresh. | |

**User's choice:** Keep filter-change auto-expand
**Notes:** Two paths, two responsibilities — refresh preserves, filter-change drives expansion. The four existing filter-change call sites in `station_list_panel.py` (lines 426, 436, 446, 462) keep calling `_sync_tree_expansion()` unchanged.

---

## New provider groups post-save

### Q1: When a save creates a brand-new provider group, what's the default state for the new group?

| Option | Description | Selected |
|--------|-------------|----------|
| Expanded (Recommended) | The user just created/edited a station that landed in this new group — expand it so the station is visible without an extra click. Pre-existing groups still keep their captured state. Discoverability beats consistency here because the user's mental thread is 'where did my station go?'. | ✓ |
| Collapsed | Match the default app-start behavior (everything collapsed). Pre-existing groups keep captured state; new groups start collapsed. Consistent rule, but the user has to hunt for the station they just saved. | |
| Match the surrounding groups | If most pre-existing groups are expanded, the new one starts expanded; if most are collapsed, the new one starts collapsed. More 'invisible' but unpredictable when there's a tie. | |

**User's choice:** Expanded
**Notes:** Visibility wins for the just-touched group.

### Q2: If a save moves a station INTO an existing (already-known) provider group that the user had collapsed, what should happen to that destination group?

| Option | Description | Selected |
|--------|-------------|----------|
| Stay collapsed (Recommended) | Preserve manual state, even when the destination group just received a station from a save. Matches the 'preserve manual state always' principle from filter-active behavior. The user can re-expand if they want to see where it went. | ✓ |
| Auto-expand the destination group | Apply the same 'visibility wins' rule from new-group default: if a save lands a station in a group, expand that group so the user sees the result. More intrusive — every cross-provider edit will silently re-expand groups the user had deliberately collapsed. | |
| Auto-expand only if the source group also got changed | Detect 'station moved between groups' specifically (provider name changed); auto-expand destination only in that case. Edits within the same group (the common case) leave both groups untouched. | |

**User's choice:** Stay collapsed
**Notes:** Manual state always wins for groups the user has touched. Only brand-new (never-seen) groups default to expanded.

---

## Claude's Discretion

- **State capture key.** Provider name (string) vs row index. Provider name is the natural stable key — `model.refresh()` invalidates `QModelIndex` via `beginResetModel`/`endResetModel`, so index-based capture would break across the very reset we're protecting against.
- **Detecting newly-created provider groups.** Set difference between captured names and post-refresh model names.
- **API surface.** Whether to expose a `preserve_expansion: bool = True` kwarg on `refresh_model()` for future opt-out vs hardcoding preserve. All five current callers want preserve; a kwarg would be dead code today.
- **Recently Played coupling.** `refresh_model()` also calls `_populate_recent()` (line 318) and `_build_chip_rows()` (line 319). Neither touches the tree expansion state — leave both untouched.
- **Empty-source-group cleanup.** If a save empties the user's previously-current provider group, `StationTreeModel` drops the empty group; the captured state for the gone-now group is naturally pruned by intersecting captured names with current model names.

## Deferred Ideas

- Persist expand state across app restarts (QSettings) — out of scope; today the tree starts collapsed on launch (SC #3 honors this).
- Animated expansion on new-group default-expand — future polish, not in scope.
- "Scroll to the saved station" affordance after a cross-provider move — possible follow-up if user testing shows D-07 confuses people.
