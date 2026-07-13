---
phase: 96-manual-refresh-of-yellow-brick-cinema-provider-with-what-is-
reviewed: 2026-06-21T00:00:00Z
depth: deep
files_reviewed: 8
files_reviewed_list:
  - musicstreamer/repo.py
  - musicstreamer/models.py
  - musicstreamer/ui_qt/edit_station_dialog.py
  - musicstreamer/ui_qt/station_tree_model.py
  - musicstreamer/ui_qt/live_refresh_dialog.py
  - musicstreamer/ui_qt/station_list_panel.py
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/yt_import.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 96: Code Review Report

**Reviewed:** 2026-06-21
**Depth:** deep
**Files Reviewed:** 8 (phase-96 hunks only, per scope note)
**Status:** issues_found

## Summary

Phase 96 adds manual live-URL refresh from a provider's YouTube channel: three
additive idempotent SQLite migrations, model fields + dedicated setters +
`list_flagged_stations_for_provider` (repo/models), a YouTube-gated resync
checkbox (edit_station_dialog/station_tree_model), a new `LiveRefreshDialog`
(scan worker + review UI + pure `apply_refresh`), provider context-menu wiring
(station_list_panel/main_window), and a duration-fallback live-detection change
in `yt_import._entry_is_live`.

The migration discipline (additive `ALTER`, idempotent `OperationalError`
catch, ordering after the legacy rebuild block), parameterized SQL in all new
setters, the dedicated-setter pattern that avoids `update_station` silent-reset,
the threading model (worker `run()` touches no widgets, results marshalled via
`Qt.QueuedConnection`, `node_runtime` threaded through), and the conservative
DROP/ADD-unchecked defaults are all sound.

Key concerns: **(1 BLOCKER)** the new `LiveRefreshDialog` renders untrusted
scan titles / station names / anchors into auto-detected rich-text `QLabel`s,
directly violating the project's documented T-39-01 PlainText invariant; plus a
worker-lifetime crash risk on Cancel-during-scan, a global widening of
`_entry_is_live` affecting the shared import path, and an unguarded
duplicate-remap default.

## Critical Issues

### CR-01: Untrusted scan titles / station names / anchors rendered as rich text (T-39-01 violation)

**File:** `musicstreamer/ui_qt/live_refresh_dialog.py:301,305`
**Issue:** The project enforces a documented security invariant — `edit_station_dialog.py:11-12`: *"Security: all QLabel instances use Qt.PlainText to prevent rich-text injection from untrusted station metadata (T-39-01)"* — and this is consistently applied across `favorites_view.py`, `settings_import_dialog.py`, `flatpak_import_wizard.py`, `announcement_banner.py` via `setTextFormat(Qt.PlainText)`. The new dialog creates QLabels from untrusted content **without** setting PlainText, so Qt's default `Qt.AutoText` interprets embedded markup as rich text:

```python
station_label = QLabel(station.name)                                  # line 301
...
anchor_label = QLabel(f"<i>Anchor: {station.live_url_title_anchor}</i>")  # line 305
```

`station.name` and `live_url_title_anchor` are populated from YouTube scan titles (`apply_refresh` calls `set_live_url_title_anchor(..., new_title)` and `insert_station(name=scan title, ...)`). A scanned title such as `<img src=http://attacker/leak.png>` is rendered as rich text by QLabel, causing Qt to issue an outbound request when the row is shown — an IP/ "tool is open" leak (SSRF-style remote-resource load) plus layout/markup injection. This is exactly the threat T-39-01 was written to close.

**Fix:** Set PlainText on every QLabel that carries untrusted data. Prefer plain interpolation for the anchor (drop the `<i>` HTML) or explicitly format:
```python
station_label = QLabel(station.name)
station_label.setTextFormat(Qt.PlainText)
...
anchor_label = QLabel(f"Anchor: {station.live_url_title_anchor}")
anchor_label.setTextFormat(Qt.PlainText)
```
Audit all QLabels in the file; the fixed-string `<b>…</b>` action label (line 296) is safe, but any label whose text derives from scan/station data must be PlainText.

## Warnings

### WR-01: Scan worker not awaited on Cancel — QThread destroyed while running

**File:** `musicstreamer/ui_qt/live_refresh_dialog.py:443,510-522,479-481`
**Issue:** `_LiveRefreshScanWorker(parent=self)` is started on open. If the user clicks Cancel during the scan, `rejected → self.reject()` returns from `exec()`; `main_window._on_provider_refresh_requested` then returns and drops its `dlg` reference, so the dialog (and its child QThread) is garbage-collected while the worker is still running a blocking yt-dlp call. Destroying a running QThread triggers Qt's "QThread: Destroyed while thread is still running" abort / crash. The dialog overrides neither `reject()` nor `closeEvent()` to wait on the worker.
**Fix:** Override `reject()`/`closeEvent()` to stop and join the worker before tearing down, e.g.:
```python
def reject(self):
    self._teardown_worker()
    super().reject()

def _teardown_worker(self):
    w = self._scan_worker
    if w is not None and w.isRunning():
        w.requestInterruption()  # or set a cancel flag
        w.wait(5000)
```
At minimum call `self._scan_worker.wait()` before the dialog is destroyed.

### WR-02: `_entry_is_live` duration-fallback widens "live" globally for the shared import path

**File:** `musicstreamer/yt_import.py:55-61`
**Issue:** The new no-signal fallback `return entry.get("duration") is None` lives in `_entry_is_live`, which `scan_playlist` applies to **every** caller — including `import_dialog._YtScanWorker` (regular playlist import), not just the new channel-refresh path. For any flat playlist entry that yt-dlp returns with neither `live_status`/`is_live` **nor** a `duration` (e.g. some sparse/region-limited entries, members-only, or genuinely upcoming/scheduled streams), the entry is now classified as live and surfaced in the import list. The docstring itself acknowledges upcoming/scheduled streams (`duration=None`) are "intentionally included" — but that intent applies to the manual review dialog, not the import flow that shares this function. This is a behavioral regression risk for import.
**Fix:** Scope the duration fallback to the channel-refresh caller rather than baking it into the shared predicate — e.g. add a `duration_fallback: bool = False` parameter to `_entry_is_live`/`scan_playlist` and enable it only from `LiveRefreshDialog`'s worker, leaving `import_dialog` on the strict explicit-signal behavior.

### WR-03: No guard against multiple REMAP rows mapping to the same live stream

**File:** `musicstreamer/ui_qt/live_refresh_dialog.py:167-173,567-576,209-239`
**Issue:** REMAP rows are checked by default (`default_check_state("remap")` returns True) and each row's combo defaults to index 0 — the anchor-closest match. When a channel that previously had N live streams now exposes only 1 (the common "what is the live stream today" case), every flagged station's combo defaults to that single live stream, and `apply_refresh` will point every station's primary stream URL at the same URL with no warning. The result is silent collapse of multiple distinct stations onto one URL on a single Apply with default selections.
**Fix:** Detect duplicate target URLs across staged REMAP changes in `_on_apply` (or in `apply_refresh`) and warn / block before committing, e.g. collect `scan_result["url"]` for all remap changes and `QMessageBox.warning` if any URL is targeted by more than one station. Alternatively, leave REMAP unchecked by default like ADD/DROP so duplicate mapping requires explicit opt-in per row.

### WR-04: Channel scan URL cannot be cleared once set

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:1887-1901`
**Issue:** On save, the companion channel URL is persisted only when non-empty:
```python
channel_url = self._live_resync_channel_url_edit.text().strip()
if channel_url and station.provider_id is not None:
    ...
    repo.set_provider_channel_scan_url(station.provider_id, channel_url)
```
If the user blanks the field to remove a previously-saved scan URL, the `if channel_url` guard is false and `set_provider_channel_scan_url(..., None)` is never called, so the stale URL persists on the provider. There is no path to clear it through the UI.
**Fix:** When the resync flag is on and the field is empty, clear the stored URL:
```python
if station.provider_id is not None:
    if channel_url and is_yt_playlist_url(channel_url):
        repo.set_provider_channel_scan_url(station.provider_id, channel_url)
    elif not channel_url:
        repo.set_provider_channel_scan_url(station.provider_id, None)
    else:
        QMessageBox.warning(... invalid ...)
```

## Info

### IN-01: QFormLayout label "Channel scan URL:" stays visible when the field is hidden

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:535-536,1331-1335`
**Issue:** The field widget is toggled with `setVisible(...)`, but in a `QFormLayout` the paired label ("Channel scan URL:") is a separate widget that is not hidden, leaving an orphaned label with no field when the resync checkbox is unchecked.
**Fix:** Use `form.setRowVisible(self._live_resync_channel_url_edit, visible)` (Qt 6.4+) or hold a reference to the label and toggle both together.

### IN-02: ADD-row name field shows empty until the combo selection changes

**File:** `musicstreamer/ui_qt/live_refresh_dialog.py:314-316,344-353`
**Issue:** ADD rows initialize the name edit via `build_row_data(action, scan_result={}, ...)` → empty string, and `_on_add_selection_changed` only fires on `currentIndexChanged`. Because the single ADD entry is already at index 0 with no change signal, the visible name field stays blank until the user interacts. `build_staged_change` falls back to the scan title so the committed record is correct, but the displayed empty name is misleading.
**Fix:** Seed the name edit from the first scan result when constructing an ADD row (pass the entry into `build_row_data` instead of `{}`), or call `_on_add_selection_changed(0)` once after wiring the combo.

### IN-03: ADD inserts via provider *name*, risking provider mismatch vs. the refreshed provider_id

**File:** `musicstreamer/ui_qt/live_refresh_dialog.py:245-256`
**Issue:** The ADD path calls `repo.insert_station(name, url, provider_name, "")`, and `insert_station` resolves the provider via `ensure_provider(provider_name)` (name lookup/create) rather than the `provider_id` the dialog was scoped to. If two providers ever share a display name, or the name drifts, the new station could attach to a different/duplicate provider than the one being refreshed (which also owns the `channel_scan_url`). For the current single-name flow it resolves correctly, but it is fragile.
**Fix:** Consider an `insert_station` variant that accepts an explicit `provider_id`, or pass the dialog's `provider_id` through the staged-change record and bind the new station to it directly.

---

_Reviewed: 2026-06-21_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
