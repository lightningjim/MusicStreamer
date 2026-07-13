---
phase: 89c-provider-brand-avatar-cover-slot-fallback
plan: 02
subsystem: cover-art / brand-avatar override picker
tags: [brand-avatar, edit-station-dialog, picker, tdd, d-09]
completed: "2026-06-17T17:20:00Z"
duration: "~8 min"

dependency_graph:
  requires:
    - 89c-01 (brand_avatars registry + _resolve_brand_avatar_fallback in now_playing_panel)
  provides:
    - _on_choose_brand_image — synchronous QFileDialog picker in EditStationDialog
    - _choose_brand_image_btn — "Choose brand image..." button in avatar row
    - test_choose_brand_image_uses_provider_keyed_persist — D-09/D-09a drift-guard
  affects:
    - musicstreamer/ui_qt/edit_station_dialog.py — avatar row + handler

tech_stack:
  added: []
  patterns:
    - Synchronous QFileDialog.getOpenFileName (mirrors _on_choose_logo shape)
    - In-memory → preview → DB persist 3-step sequence (mirrors _on_avatar_fetched)
    - Pitfall-7 guard (provider_id is None early return before any write)
    - Non-silent-reset single-column UPDATE via update_provider_avatar_path
    - Source-grep drift-guard test (structural contract, no Qt mock)
    - TDD: RED drift-guard in Task 1, GREEN implementation in same task

key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/edit_station_dialog.py
    - tests/test_brand_avatars.py

key_decisions:
  - "D-09: _on_choose_brand_image uses synchronous file read + write_provider_avatar + update_provider_avatar_path (non-silent-reset single-column UPDATE)"
  - "D-09a: picker is structurally disjoint from _AvatarFetchWorker; no _AvatarFetchWorker reference in method body"
  - "Pitfall-7: provider_id is None guard placed as first check before any write"
  - "Drift-guard docstring must not mention _AvatarFetchWorker — test greps the full method body including docstring"

metrics:
  tasks_completed: 1
  tasks_total: 1
  files_created: 0
  files_modified: 2
  tests_added: 1
  tests_passing: 19
---

# Phase 89c Plan 02: Brand Image Upload Override Summary

**One-liner:** Synchronous "Choose brand image..." picker in EditStationDialog writes provider-keyed avatar via write_provider_avatar + update_provider_avatar_path, with Pitfall-7 guard and D-09a structural disjointness from the network auto-fetch path.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 (RED) | 88defb0b | test(89c-02): add RED drift-guard for _on_choose_brand_image D-09/D-09a |
| Task 1 (GREEN) | 7f5f34b3 | feat(89c-02): add _on_choose_brand_image picker + button in avatar row (D-09/D-09a) |

## Tasks Executed

### Task 1: "Choose brand image..." picker + provider-keyed persist (D-09/D-09a)

**TDD RED:** Added `test_choose_brand_image_uses_provider_keyed_persist` to `tests/test_brand_avatars.py`. Test greps `edit_station_dialog.py` as text for: method definition `_on_choose_brand_image`, body contains `write_provider_avatar`, `update_provider_avatar_path`, `provider_id is None`, and does NOT contain `_AvatarFetchWorker`. Test FAILED (method not yet defined). Committed as RED test.

**TDD GREEN:** Edited `musicstreamer/ui_qt/edit_station_dialog.py`:
1. In avatar_row setup (~L516), after `_refresh_avatar_btn.clicked.connect(...)`, added:
   - `self._choose_brand_image_btn = QPushButton("Choose brand image...", self)` appended to `avatar_row`
   - Connected `clicked` to `self._on_choose_brand_image`
   - No change to `_refresh_avatar_btn` enabling/gating (stays YouTube/Twitch-only)
2. Added `_on_choose_brand_image(self) -> None` method after `_on_choose_logo`:
   - Pitfall-7 guard first: `if self._station.provider_id is None` → set status + return
   - `QFileDialog.getOpenFileName(...)` for PNG/JPG/JPEG/WEBP images
   - Synchronous `open(path, "rb")` read — no network, no thread worker
   - `assets.write_provider_avatar(self._station.provider_id, data)` (provider-keyed atomic write)
   - 3-step: `self._station.provider_avatar_path = rel_path` → `_refresh_avatar_preview()` → `update_provider_avatar_path()`
   - Docstring avoids mentioning `_AvatarFetchWorker` (test greps full method body)

**Deviation — Rule 1 (Auto-fix):** Initial docstring mentioned `_AvatarFetchWorker` by name. The drift-guard test extracts the full method body (including docstring) and asserts `_AvatarFetchWorker` is absent. Fixed by rephrasing docstring to "no network worker thread involved (D-09a)" without naming the class.

**Verification:** All 19 tests GREEN (8 in test_brand_avatars.py including the new drift-guard, 11 in test_cover_art_avatar.py — all 89c-01 guards still pass).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Drift-guard test greps full method body including docstring**
- **Found during:** Task 1 (TDD GREEN, first test run)
- **Issue:** The test asserts `_AvatarFetchWorker not in method_body`. Initial docstring contained "Disjoint from _AvatarFetchWorker" causing the assertion to fail even though the implementation code itself correctly excluded the class.
- **Fix:** Rephrased docstring to "no network worker thread involved (D-09a)" — semantically equivalent, test-clean.
- **Files modified:** `musicstreamer/ui_qt/edit_station_dialog.py`
- **Commit:** 7f5f34b3

## Known Stubs

None — the picker wires to live `write_provider_avatar` + `update_provider_avatar_path` which are fully implemented. The override is consumed by `89c-01`'s `_resolve_brand_avatar_fallback` D-08 step-1 (reads `provider_avatar_path` first) with no additional render code needed.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries beyond what the threat model already covers in T-89c-05/06/07/08. The provider-keyed filename (derived from int `provider_id`, not user input) eliminates path traversal; atomic write via `write_provider_avatar` prevents corruption; non-silent-reset UPDATE prevents collateral column damage.

## Self-Check: PASSED

- `musicstreamer/ui_qt/edit_station_dialog.py`: contains `_on_choose_brand_image` (grep count: 1), contains `Choose brand image` (count: 3 — button label, dialog title, comment)
- Commit 88defb0b (RED test): confirmed in git log
- Commit 7f5f34b3 (GREEN impl): confirmed in git log
- All 19 tests GREEN
