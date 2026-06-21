---
phase: 96
plan: "05"
subsystem: ui-integration
tags: [wave-3, station-list-panel, main-window, context-menu, node-runtime, tdd-green]
dependency_graph:
  requires:
    - "96-03 (_TreeNode.provider_id populated, EditStationDialog refresh fields)"
    - "96-04 (LiveRefreshDialog + _LiveRefreshScanWorker + apply helpers)"
  provides:
    - "StationListPanel.provider_refresh_requested Signal(int, str) (D-04)"
    - "StationListPanel.__init__ node_runtime kwarg + _node_runtime store (D-09)"
    - "_on_tree_context_menu provider branch with Ungrouped gate (D-04 / Pitfall 4)"
    - "MainWindow._on_provider_refresh_requested slot (D-04/D-09/D-10)"
    - "node_runtime threaded MainWindow -> StationListPanel -> LiveRefreshDialog -> _LiveRefreshScanWorker -> scan_playlist (D-09)"
    - "Station list reload on refresh_complete (D-10)"
    - "Empty channel_scan_url toast guard (RESEARCH Open Question 3)"
  affects:
    - musicstreamer/ui_qt/station_list_panel.py
    - musicstreamer/ui_qt/main_window.py
    - tests/test_station_list_panel.py
tech_stack:
  added: []
  patterns:
    - "Provider branch inserted BEFORE station path in _on_tree_context_menu; guards on node.provider_id is not None"
    - "Signal wired in same region as edit_requested + new_station_requested at L548-553"
    - "LiveRefreshDialog imported at dialog-import block (L81); mirrors ImportDialog import pattern"
    - "_on_provider_refresh_requested mirrors _on_edit_requested: resolves data from repo, constructs dialog, connects completion signal, calls exec()"
    - "test_provider_refresh_wiring uses monkeypatch on _mw_mod.LiveRefreshDialog to capture constructor args"
key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/station_list_panel.py
    - musicstreamer/ui_qt/main_window.py
    - tests/test_station_list_panel.py
decisions:
  - "Phase 96 D-04: provider_refresh_requested = Signal(int, str) added to StationListPanel signal declarations; provider branch in _on_tree_context_menu emits before returning (station path unchanged below)"
  - "Phase 96 D-09: node_runtime threaded StationListPanel(node_runtime=...) -> self._node_runtime -> LiveRefreshDialog(node_runtime=...) -> _LiveRefreshScanWorker -> scan_playlist; closes .desktop-launcher landmine"
  - "Phase 96 D-10: refresh_complete connected to _refresh_station_list so list reloads immediately after apply"
  - "Phase 96 RESEARCH OQ-3: empty/None channel_scan_url shows a descriptive toast and returns without opening the dialog"
  - "Phase 96 T-96-15: Ungrouped provider rows (provider_id None) get no menu — gated at node.provider_id is not None in the provider branch"
  - "Phase 96 W3: test_provider_refresh_wiring asserts node_runtime stored on panel, Signal exists, MainWindow slot constructs LiveRefreshDialog with correct node_runtime + channel_scan_url, and absent URL toasts without opening dialog"
metrics:
  duration: "~40 minutes (including human-verify + external fix iteration)"
  completed: "2026-06-21"
  tasks_completed: 3
  tasks_total: 3
  tasks_remaining: 0
  files_modified: 5
---

# Phase 96 Plan 05: Provider Context Menu + node_runtime Threading Summary

**One-liner:** Provider right-click "Refresh live streams..." in StationListPanel wired end-to-end to LiveRefreshDialog with node_runtime threaded MainWindow → panel → dialog → worker → scan_playlist; Ungrouped excluded; station list reloads on apply; empty-URL path toasts — human-verified with real YBC channel returning 9 live/upcoming streams after fixing a pre-existing live-detection bug (fbebaf1a).

## What Was Built

Plan 05 closes the integration seam between Plans 03+04 (eligibility surface + dialog) and makes the feature reachable from the sidebar with correct node_runtime threading to prevent silent failure under GNOME .desktop launchers.

### Task 1: Provider context-menu branch + signal + node_runtime param in StationListPanel (D-04/D-09)

Three changes to `musicstreamer/ui_qt/station_list_panel.py`:

**Signal declaration** — `provider_refresh_requested = Signal(int, str)` added after `new_station_requested` in the class-level signal block. Carries `(provider_id, provider_name)`.

**Constructor** — Signature changed from `def __init__(self, repo, parent=None)` to `def __init__(self, repo, parent=None, *, node_runtime=None)`. Stores `self._node_runtime = node_runtime` immediately after `self._repo = repo`. This closes Pitfall 3 from the plan research — the panel holds it for the MainWindow to consume when opening the dialog.

**`_on_tree_context_menu` provider branch** — Inserted BEFORE the existing station path. Uses `node = source_idx.internalPointer()` and gates on `node is not None and node.kind == "provider" and node.provider_id is not None`. Provider rows with `provider_id is None` (Ungrouped) fall through to the existing station path with no effect (Pitfall 4 / T-96-15). Provider rows with a real `provider_id` build a QMenu with "Refresh live streams...", execute it at the viewport-global pos, and on selection emit `provider_refresh_requested(node.provider_id, node.provider_name or "")`, then return. The existing station-only menu (Edit Station) is unchanged below the branch.

### Task 2: MainWindow wiring — node_runtime, open LiveRefreshDialog, reload on complete (D-04/D-09/D-10)

Four changes to `musicstreamer/ui_qt/main_window.py`:

**Import** — `from musicstreamer.ui_qt.live_refresh_dialog import LiveRefreshDialog` added to the dialog-import block (line 81), adjacent to `ImportDialog`.

**StationListPanel construction** — Changed to `StationListPanel(repo, parent=self._splitter, node_runtime=self._node_runtime)`. This is the critical D-09 threading step — previously the panel received no node_runtime, so any LiveRefreshDialog opened from it would have silently broken YouTube channel scans under GNOME .desktop launchers (minimal PATH, no node on PATH, yt-dlp build_js_runtimes(None) failure).

**Signal wiring** — `self.station_panel.provider_refresh_requested.connect(self._on_provider_refresh_requested)` added next to the existing panel signal connections at the end of the `__init__` signal-wiring block.

**Slot `_on_provider_refresh_requested`** — Added adjacent to `_on_edit_requested` (line 1356):
- Resolves `channel_scan_url` by iterating `self._repo.list_providers()` (Plan 02 returns `Provider.channel_scan_url`)
- Empty/None URL: calls `self.show_toast(...)` with a descriptive message prompting the user to set the URL via Edit Station, then returns (RESEARCH Open Question 3 / T-96-14 empty-URL guard)
- URL present: constructs `LiveRefreshDialog(self._repo, provider_id, provider_name, channel_scan_url, node_runtime=self._node_runtime, toast_callback=self.show_toast, parent=self)`, connects `refresh_complete` to `_refresh_station_list` (D-10), and calls `dlg.exec()`

**Wiring test** — `test_provider_refresh_wiring` added to `tests/test_station_list_panel.py`:
- (a) Constructs `StationListPanel(_sample_repo(), node_runtime=sentinel)`, asserts `panel._node_runtime is sentinel`
- (b) Asserts `hasattr(panel, "provider_refresh_requested")`
- (c) Constructs a `MainWindow` with a `_FakeRepoForWiring` that returns a `Provider` with `channel_scan_url` set, monkeypatches `musicstreamer.ui_qt.main_window.LiveRefreshDialog` to a capture class, calls `w._on_provider_refresh_requested(FAKE_PROVIDER_ID, FAKE_PROVIDER_NAME)`, asserts dialog was instantiated with correct `provider_id`, `channel_scan_url`, and `node_runtime`; then asserts absent-URL path shows toast and does not instantiate the dialog

## Task 3: Human-Verify — APPROVED

The user launched the app and walked all how-to-verify steps:

1. Confirmed the "Re-sync live URL from channel" checkbox is enabled for YouTube stations and disabled for Twitch/non-YouTube URLs.
2. Right-clicked the provider row for the YBC provider — "Refresh live streams..." appeared. Confirmed it does NOT appear on the "Ungrouped" row (Pitfall 4 / T-96-15).
3. Clicked "Refresh live streams..." — dialog opened, scan ran without UI freeze.
4. Dialog initially showed 0 live streams. Root cause: pre-existing Phase 35-03 bug in `_entry_is_live` (see Deviations). After external fix (fbebaf1a), re-verify returned 9 live/upcoming streams.
5. Performed a REMAP of a flagged station to a currently-live stream. Confirmed DROP and ADD rows are unchecked by default. Confirmed review-and-confirm summary shown before Apply (D-10).
6. Clicked Apply — station list reloaded, remapped station plays the new live URL. Confirmed an untouched flagged station was unchanged and NOT deleted.

**Result: APPROVED**

## Verification

```
.venv/bin/python -m pytest tests/test_station_tree_model.py -x -q
14 passed, 1 warning in 0.11s

.venv/bin/python -m pytest tests/test_station_list_panel.py -k "provider_refresh_wiring" -x -q
1 passed, 2 warnings in 0.48s

.venv/bin/python -m pytest tests/test_station_list_panel.py tests/test_live_refresh_dialog.py -q
46 passed, 2 warnings in 0.69s

.venv/bin/python -c "import musicstreamer.ui_qt.main_window; import musicstreamer.ui_qt.station_list_panel"
(no output — imports clean)
```

The broader suite run (`-k "main_window or station_panel or live_refresh or station_list_panel"`) showed 1 pre-existing failure (`test_hamburger_menu_actions` — unrelated hamburger menu count assertion, confirmed pre-existing before this plan's changes by running against an unmodified main_window.py). All other tests in scope pass.

## Deviations from Plan

### Auto-fixed Issues (External — orchestrator-committed)

**1. [Rule 1 - Bug] Pre-existing live-detection bug in `yt_import._entry_is_live` blocked plan goal — committed fbebaf1a**

- **Found during:** Task 3 human-verify (initial run returned "0 live streams" on a channel with 8+ live)
- **Issue:** `_entry_is_live` in `musicstreamer/yt_import.py`, introduced in Phase 35-03, required an explicit `live_status` or `is_live` field. `extract_flat='in_playlist'` on a YouTube channel `/streams` tab returns `live_status=None` and `is_live=None` for every entry, so the explicit-status filter rejected all of them. This is a latent bug that only surfaces on the channel `/streams` tab extraction path used by the LiveRefreshDialog scan worker.
- **Fix:** Added a duration-fallback to `_entry_is_live`: when no explicit live signal is present, treat `duration is None` as the live signal. VODs always carry a concrete integer duration; live streams and upcoming/scheduled streams have `duration=None`. This is the correct discriminant for flat-extracted channel tab entries.
- **Regression test:** `tests/test_yt_import_library.py::test_scan_playlist_flat_channel_tab_falls_back_to_duration` added and passing.
- **Files modified:** `musicstreamer/yt_import.py`, `tests/test_yt_import_library.py`
- **Verification:** End-to-end re-verify returned 9 live/upcoming streams from the YBC channel; regression test passes.
- **Committed in:** `fbebaf1a` (committed by orchestrator during human-verify iteration — NOT re-committed here)

---

**Total deviations:** 1 external fix (pre-existing Phase 35-03 bug, essential to achieving this plan's goal)
**Impact on plan:** The fix was necessary — without it the dialog opened but the scan returned no streams, making the D-10 review-and-apply flow unreachable. Regression test added. No scope creep.

### Minor test detail (not a plan deviation)

The `_FakeNodeRuntime` object in `test_provider_refresh_wiring` (not in the plan spec) was necessary because `MainWindow.__init__` checks `self._node_runtime.available` when building the hamburger menu indicator, and the test's simple string sentinel would raise `AttributeError`. Using `type("_FakeNodeRuntime", (), {"available": True})()` is the minimal fix — not a deviation, just filling in a required test detail that the plan spec left implicit.

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: Provider context-menu branch + signal + node_runtime param | d6cc01e8 | musicstreamer/ui_qt/station_list_panel.py (+18 lines) |
| Task 2: MainWindow wiring + test_provider_refresh_wiring | 5973b167 | musicstreamer/ui_qt/main_window.py (+34 lines), tests/test_station_list_panel.py (+133 lines) |
| External fix (human-verify iteration): live-detection duration fallback | fbebaf1a | musicstreamer/yt_import.py, tests/test_yt_import_library.py |
| Task 3: human-verify checkpoint (approved, no code) | — | — |

## Known Stubs

None — all surfaces are fully wired:
- `provider_refresh_requested` Signal declared and emitted in `_on_tree_context_menu` provider branch
- `_on_provider_refresh_requested` constructs real `LiveRefreshDialog` (not a stub) with all required args
- `LiveRefreshDialog.refresh_complete` connected to `_refresh_station_list` (real reload, not a no-op)

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced by Plan 05. All threat model mitigations from the plan are in place:
- T-96-14 (SSRF/DoS): URL was validated at store time (Plan 03); empty URL guarded with toast; URL goes to yt-dlp (not raw urllib)
- T-96-15 (Ungrouped elevation): `node.provider_id is not None` gate in provider branch
- T-96-16 (node_runtime missing): node_runtime threaded end-to-end via Task 1 + Task 2

## Self-Check: PASSED

- musicstreamer/ui_qt/station_list_panel.py modified: FOUND (provider_refresh_requested at L91, node_runtime at L93-94, provider branch at L685-702)
- musicstreamer/ui_qt/main_window.py modified: FOUND (LiveRefreshDialog import at L81, node_runtime at L404, signal wire at L553, slot at L1356)
- tests/test_station_list_panel.py modified: FOUND (test_provider_refresh_wiring at end of file)
- musicstreamer/yt_import.py modified (fbebaf1a): FOUND (duration fallback in _entry_is_live)
- tests/test_yt_import_library.py modified (fbebaf1a): FOUND (test_scan_playlist_flat_channel_tab_falls_back_to_duration)
- Commit d6cc01e8: FOUND
- Commit 5973b167: FOUND
- Commit fbebaf1a: FOUND (external fix, not re-committed)
- `grep "provider_refresh_requested" station_list_panel.py` = 2 lines (Signal + emit): CONFIRMED
- `grep "_on_provider_refresh_requested" main_window.py` = 2 lines (connect + def): CONFIRMED
- `grep "node_runtime=self._node_runtime" main_window.py` shows StationListPanel construction + LiveRefreshDialog construction: CONFIRMED
- 46 tests PASS (test_station_list_panel + test_live_refresh_dialog), 0 regressions: CONFIRMED
- Human-verify Task 3: APPROVED — 9 live/upcoming streams returned, REMAP + Apply verified, untouched station preserved
