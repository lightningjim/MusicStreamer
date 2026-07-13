---
phase: 96
plan: "03"
subsystem: ui-layer
tags: [wave-2, edit-station-dialog, station-tree-model, tdd-green, youtube-only-gate]
dependency_graph:
  requires:
    - "96-02 (dedicated setters: set_live_url_syncs_from_channel, set_live_url_title_anchor, set_provider_channel_scan_url)"
    - "96-01 (RED tests: test_tree_node_carries_provider_id, test_live_resync_checkbox_gating)"
  provides:
    - "_TreeNode.provider_id field populated from first station of each provider group"
    - "EditStationDialog._live_resync_checkbox (YouTube-only gate, D-02)"
    - "EditStationDialog._live_resync_channel_url_edit (companion URL, hidden by default)"
    - "On-save persistence via dedicated setters (D-01/D-03/D-04)"
    - "companion URL validated with is_yt_playlist_url before persist (T-96-06)"
  affects:
    - musicstreamer/ui_qt/station_tree_model.py
    - musicstreamer/ui_qt/edit_station_dialog.py
tech_stack:
  added: []
  patterns:
    - "YouTube-only gate: is_yt = 'youtube.com' in lower or 'youtu.be' in lower; setEnabled(is_yt) — no is_twitch"
    - "Dedicated-setter persistence in _on_save: never routed through update_station (Pitfall 1)"
    - "Late import of is_yt_playlist_url inside _on_save to validate companion URL (T-96-06)"
    - "QMessageBox.warning for invalid companion URL; bad URL never persisted"
    - "_TreeNode.provider_id set by first station of each provider group in _populate()"
key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/station_tree_model.py
    - musicstreamer/ui_qt/edit_station_dialog.py
decisions:
  - "Phase 96 D-02: live-resync checkbox gated on is_yt ONLY (not is_twitch) — avatar gate remains is_yt or is_twitch but the flag gate is YouTube-exclusive"
  - "Phase 96 D-01: set_live_url_syncs_from_channel always called on save (even when unchecked) to persist flag=False explicitly"
  - "Phase 96 D-03: anchor captured as first stream label or station name on flag-set"
  - "Phase 96 D-04: _TreeNode.provider_id set from st.provider_id for the first station of each group; Ungrouped (provider_id=None) yields None"
  - "T-96-06: companion URL validated with is_yt_playlist_url() before set_provider_channel_scan_url; non-YouTube URLs rejected with QMessageBox.warning"
  - "T-96-07: no update_station call for Phase 96 fields — all persistence via dedicated setters"
  - "T-96-08: checkbox disabled (and force-unchecked) when URL is not youtube.com/youtu.be"
metrics:
  duration: "10 minutes"
  completed: "2026-06-21T18:10:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 96 Plan 03: UI-Layer Opt-In Surface Summary

**One-liner:** YouTube-only live-resync checkbox + companion URL field in EditStationDialog with dedicated-setter persistence, and _TreeNode.provider_id populated in the tree model for provider context-menu use.

## What Was Built

Plan 03 wires the user-facing entry point that makes a station eligible for live-URL refresh (D-01/D-02/D-03) and delivers the provider-id plumbing the sidebar tree needs to scope a refresh (D-04). Both Plan 01 RED tests are now GREEN.

### Task 1: _TreeNode.provider_id field + populate (D-04)

Added `provider_id: Optional[int] = None` to the `_TreeNode` dataclass in `station_tree_model.py` after `provider_name`. In `_populate()`, passed `provider_id=st.provider_id` to the `_TreeNode(kind="provider", ...)` constructor — the first station of each provider group sets the group node's `provider_id`. Ungrouped stations have `provider_id=None`, which is the gate Plan 05 checks before showing the "Refresh live streams…" menu item (Pitfall 4).

### Task 2: Live-resync checkbox, companion URL field, YouTube-only gate, on-save persist

**Widget construction** (added after the channel-avatar row in the form, before the streams table):
- `_live_resync_checkbox = QCheckBox("Re-sync live URL from channel")` — disabled by default, toggled-connected to `_on_live_resync_toggled`
- `_live_resync_channel_url_edit = QLineEdit()` — placeholder `https://youtube.com/@Channel/streams`, hidden by default

**Pre-population on open:**
- `_live_resync_checkbox.setChecked(station.live_url_syncs_from_channel)`
- If `station.provider_id` is set, looks up the provider from `list_providers()` and pre-fills the channel URL from `prov.channel_scan_url` when available

**YouTube-only gate in `_on_url_text_changed()`** (appended after the avatar gate):
```python
self._live_resync_checkbox.setEnabled(is_yt)
if not is_yt:
    self._live_resync_checkbox.setChecked(False)
self._live_resync_channel_url_edit.setVisible(is_yt and self._live_resync_checkbox.isChecked())
```
The gate uses the existing `is_yt` local only — explicitly does NOT include `is_twitch` (D-02).

**`_on_live_resync_toggled(checked)`** toggles the companion URL field visibility when the checkbox state changes.

**On-save persistence** (after stream prune/reorder, before `station_saved.emit()`):
- `repo.set_live_url_syncs_from_channel(station.id, flag)` always called (D-01)
- When `flag=True`:
  - `anchor = (streams[0].label if streams else "") or station.name`; `repo.set_live_url_title_anchor(station.id, anchor)` (D-03)
  - Companion URL: validated with `is_yt_playlist_url(channel_url)` (late import); valid URLs call `repo.set_provider_channel_scan_url(station.provider_id, channel_url)` (D-04); invalid URLs surface `QMessageBox.warning` and are never persisted (T-96-06)

## Verification

```
.venv/bin/python -m pytest tests/test_edit_station_dialog.py tests/test_station_tree_model.py -x -q
111 passed, 2 warnings in 5.91s

.venv/bin/python -m pytest tests/test_repo.py -x -q
115 passed, 1 warning in 0.92s
```

Plan 01 RED tests now GREEN:
- `test_tree_node_carries_provider_id` PASS
- `test_live_resync_checkbox_gating` PASS (youtube.com enabled, twitch.tv disabled, other disabled+unchecked)

## Deviations from Plan

None — plan executed exactly as written.

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: _TreeNode.provider_id field + populate | 52081a36 | musicstreamer/ui_qt/station_tree_model.py (+2 lines) |
| Task 2: Live-resync checkbox + URL field + gate + persist | 879ad8bb | musicstreamer/ui_qt/edit_station_dialog.py (+67 lines) |

## Known Stubs

None — the checkbox is wired to the Plan-02 setters end-to-end: widget → _on_url_text_changed gate → _on_save persistence → repo setter → SQLite column.

## Threat Flags

None — T-96-06, T-96-07, T-96-08 all mitigated:
- T-96-06 (SSRF): is_yt_playlist_url gate before set_provider_channel_scan_url
- T-96-07 (Tampering via update_station): no update_station call; all Phase 96 fields use dedicated setters
- T-96-08 (Elevation via non-YT flag): checkbox disabled+unchecked unless URL is youtube.com/youtu.be

## Self-Check: PASSED

- musicstreamer/ui_qt/station_tree_model.py modified: FOUND (provider_id field at line 37, populate at line 221)
- musicstreamer/ui_qt/edit_station_dialog.py modified: FOUND (_live_resync_checkbox, _live_resync_channel_url_edit, gate in _on_url_text_changed, persistence in _on_save)
- Commit 52081a36: FOUND
- Commit 879ad8bb: FOUND
- `grep -n "provider_id" station_tree_model.py` = 2 lines: CONFIRMED
- `grep -n "set_live_url_syncs_from_channel|set_live_url_title_anchor|set_provider_channel_scan_url|is_yt_playlist_url" edit_station_dialog.py` = 4 lines: CONFIRMED
- Checkbox gate uses `is_yt` only, not `is_yt or is_twitch`: CONFIRMED
- 111 combined tests PASS, 115 repo tests PASS: CONFIRMED
