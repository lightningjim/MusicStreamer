---
audit_date: 2026-04-25
phase: 44
plan: 05
scope: All QWidget / QDialog / QMainWindow / QObject subclasses in `musicstreamer/ui_qt/`; all GStreamer + media-key callback flows wired in `musicstreamer/ui_qt/main_window.py`.
auditor: Claude (executor agent, GSD)
expected_result: Clean — Phase 37 established the `parent=` convention; Phases 37–43.1 UAT logs contain no `RuntimeError: Internal C++ object already deleted` regression entries.
actual_result: Clean. No spot fixes required.
---

# Phase 44 — QA-05 Widget Lifetime Audit

**Audit date:** 2026-04-25
**Scope:** All `QWidget` / `QDialog` / `QMainWindow` / `QObject` subclasses in `musicstreamer/ui_qt/`; all GStreamer/media-key callback flows in `musicstreamer/ui_qt/main_window.py`.
**Method:** Static grep sweep + manual constructor + signal-connection inspection. Document-only audit per D-23 (no stress tests added).

---

## Subclass Inventory

Source command:
```
grep -E "^class.*\((QWidget|QDialog|QMainWindow|QObject).*\)" musicstreamer/ui_qt/*.py
```

| Class | File | `parent=` passed in `__init__`? | `super().__init__(parent)` called? | Lifetime owner | Risk |
|-------|------|---------------------------------|------------------------------------|----------------|------|
| ResponseCurve | `musicstreamer/ui_qt/eq_response_curve.py` | yes (`parent=None` default) | yes | EqualizerDialog (`ResponseCurve(self)` — equalizer_dialog.py:136) | OK |
| FavoritesView | `musicstreamer/ui_qt/favorites_view.py` | yes (`parent: Optional[QWidget] = None`) | yes | StationListPanel `_stack` (favorites_view created with `parent=self._stack` — station_list_panel.py:299) | OK |
| ToastOverlay | `musicstreamer/ui_qt/toast.py` | yes (positional, required `parent: QWidget`) | yes | MainWindow (`ToastOverlay(self)` — main_window.py:221) | OK |
| ImportDialog | `musicstreamer/ui_qt/import_dialog.py` | yes | yes | MainWindow (modal `dlg.exec()`) | OK |
| _ImportPreviewSheet (internal) | `musicstreamer/ui_qt/import_dialog.py` | yes (`parent=None`) | yes | ImportDialog | OK |
| _DiscoveryProgressSheet (internal) | `musicstreamer/ui_qt/import_dialog.py` | yes (`parent=None`) | yes | ImportDialog | OK |
| _DiscoveryResultsSheet (internal) | `musicstreamer/ui_qt/import_dialog.py` | yes (`parent=None`) | yes | ImportDialog | OK |
| AccountsDialog | `musicstreamer/ui_qt/accounts_dialog.py` | yes (`parent: QWidget \| None = None`) | yes | MainWindow (modal) | OK |
| NowPlayingPanel | `musicstreamer/ui_qt/now_playing_panel.py` | yes (`parent: Optional[QWidget] = None`) | yes | QSplitter (`NowPlayingPanel(player, repo, parent=self._splitter)` — main_window.py:206) | OK |
| _ElidedLabel (internal) | `musicstreamer/ui_qt/now_playing_panel.py` | yes (`parent: Optional[QWidget] = None`) | yes (passes `text, parent` to base QLabel) | NowPlayingPanel | OK |
| EqualizerDialog | `musicstreamer/ui_qt/equalizer_dialog.py` | yes | yes | MainWindow (modal) | OK |
| EditStationDialog | `musicstreamer/ui_qt/edit_station_dialog.py` | yes (`parent=None`) | yes | MainWindow (modal) | OK |
| _StreamRowEditor (internal) | `musicstreamer/ui_qt/edit_station_dialog.py` | yes (`parent=None`) | yes | EditStationDialog | OK |
| CookieImportDialog | `musicstreamer/ui_qt/cookie_import_dialog.py` | yes | yes | MainWindow (modal) | OK |
| MainWindow | `musicstreamer/ui_qt/main_window.py` | yes (top-level, no parent — owned by QApplication / `_run_gui`) | yes | QApplication / `__main__._run_gui()` | OK |
| _ExportWorker (QThread, internal) | `musicstreamer/ui_qt/main_window.py` | yes (`parent=None`) | yes | MainWindow (`self._export_worker` attribute — held alive for thread duration) | OK |
| _ImportPreviewWorker (QThread, internal) | `musicstreamer/ui_qt/main_window.py` | yes (`parent=None`) | yes | MainWindow (`self._import_preview_worker` attribute) | OK |
| SettingsImportDialog | `musicstreamer/ui_qt/settings_import_dialog.py` | yes | yes | MainWindow (modal) | OK |
| _SettingsImportSummary (internal) | `musicstreamer/ui_qt/settings_import_dialog.py` | yes (`parent=None`) | yes | SettingsImportDialog | OK |
| AccentColorDialog | `musicstreamer/ui_qt/accent_color_dialog.py` | yes (`parent=None`) | yes | MainWindow (modal) | OK |
| DiscoveryDialog | `musicstreamer/ui_qt/discovery_dialog.py` | yes | yes | MainWindow (modal) | OK |
| _DiscoveryWorker (internal) | `musicstreamer/ui_qt/discovery_dialog.py` | yes | yes | DiscoveryDialog | OK |
| StationListPanel | `musicstreamer/ui_qt/station_list_panel.py` | yes (`parent: QWidget \| None = None`) | yes | QSplitter (`StationListPanel(repo, parent=self._splitter)` — main_window.py:203) | OK |

**Result:** 23 classes inventoried. All pass `parent` through `super().__init__(parent)` per Phase 37 convention. No subclass relies on Python-only references for lifetime; every widget either has a Qt parent (QSplitter, dialog parent, attribute on a longer-lived object) or is the top-level QMainWindow. QThread workers (`_ExportWorker`, `_ImportPreviewWorker`, `_DiscoveryWorker`) are stored on instance attributes — Python GC cannot reclaim them mid-flight.

---

## Dialog Launch Sites

Source command:
```
grep -nE "Dialog\(.*parent" musicstreamer/ui_qt/main_window.py
```

| Call site | Line | Parent arg present? | OK |
|-----------|------|---------------------|-----|
| `EditStationDialog(fresh, self._player, self._repo, parent=self)` | main_window.py:414 | yes (`parent=self`) | OK |
| `SettingsImportDialog(preview, self.show_toast, parent=self)` | main_window.py:558 | yes (`parent=self`) | OK |
| `DiscoveryDialog(self._player, self._repo, self.show_toast, parent=self)` | main_window.py:572 | yes (`parent=self`) | OK |
| `ImportDialog(self.show_toast, self._repo, parent=self)` | main_window.py:578 | yes (`parent=self`) | OK |
| `AccentColorDialog(self._repo, parent=self)` | main_window.py:584 | yes (`parent=self`) | OK |
| `CookieImportDialog(self.show_toast, parent=self)` | main_window.py:589 | yes (`parent=self`) | OK |
| `AccountsDialog(self._repo, parent=self)` | main_window.py:598 | yes (`parent=self`) | OK |
| `EqualizerDialog(self._player, self._repo, self.show_toast, parent=self)` | main_window.py:604 | yes (`parent=self`) | OK |
| `EditStationDialog(...)` (new-station path, around line 391-396) | main_window.py:391-396 | yes (`parent=self`) | OK |

**Result:** 9 distinct dialog launch sites confirmed. Every modal dialog opened from MainWindow passes `parent=self`, ensuring Qt destroys the dialog when MainWindow goes away.

---

## Callback Flow Audit (Player → UI / MediaKeys → UI)

Source commands:
```
grep -nE "self\._player\..*\.connect" musicstreamer/ui_qt/main_window.py
grep -nE "self\._media_keys\..*\.connect" musicstreamer/ui_qt/main_window.py
```

QA-05 rule: handler must be a bound method or another widget's bound slot — never a self-capturing lambda used as a long-lived signal handler (transient dialog-scoped lambdas are accepted; see "Lambda Audit" below).

| Line | Signal | Handler | Bound method / slot? | OK |
|------|--------|---------|----------------------|-----|
| 235 | `self._player.title_changed` | `self.now_playing.on_title_changed` | yes (NowPlayingPanel bound slot) | OK |
| 236 | `self._player.elapsed_updated` | `self.now_playing.on_elapsed_updated` | yes | OK |
| 237 | `self._player.buffer_percent` | `self.now_playing.set_buffer_percent` | yes | OK |
| 240 | `self._player.failover` | `self._on_failover` | yes (MainWindow bound) | OK |
| 241 | `self._player.offline` | `self._on_offline` | yes | OK |
| 242 | `self._player.playback_error` | `self._on_playback_error` | yes | OK |
| 243 | `self._player.cookies_cleared` | `self.show_toast` (Phase 999.7) | yes (MainWindow bound) | OK |
| 262 | `self._player.failover` | `self.now_playing._sync_stream_picker` | yes (NowPlayingPanel bound) | OK |
| 282 | `self._media_keys.play_pause_requested` | `self._on_media_key_play_pause` | yes | OK |
| 283 | `self._media_keys.stop_requested` | `self._on_media_key_stop` | yes | OK |
| 285 | `self._media_keys.next_requested` | `self._on_media_key_next` | yes | OK |
| 286 | `self._media_keys.previous_requested` | `self._on_media_key_previous` | yes | OK |
| 289 | `self._player.title_changed` | `self._on_title_changed_for_media_keys` | yes | OK |

**Result:** 13 long-lived signal connections from `_player` and `_media_keys` to MainWindow/NowPlayingPanel are all bound-method handlers. None capture `self` in a closure. Lifetime is bound to the MainWindow (which lives for the whole app) — when MainWindow is destroyed at app exit, Qt disconnects automatically.

### Lambda Audit (transient dialog-scoped — ACCEPTED)

`grep -nE "lambda" musicstreamer/ui_qt/main_window.py` reports two `lambda` connections:

| Line | Connection | Lifetime | Verdict |
|------|------------|----------|---------|
| 401 | `dlg.station_saved.connect(lambda: self.station_panel.select_station(new_id))` (new-station EditStationDialog) | Lambda lifetime is bound to `dlg`, a modal `EditStationDialog(parent=self)`. Dialog closes after `dlg.exec()` returns → connection torn down with the dialog. | ACCEPTED — already documented in main_window.py:398-399 ("self-capturing id is accepted pattern here") |
| 416 | `dlg.station_saved.connect(lambda: self._sync_now_playing_station(fresh.id))` (edit-station path) | Same pattern: lambda dies with the modal dialog. | ACCEPTED |

Both lambdas are scoped to a modal dialog whose lifetime is shorter than `self` (MainWindow). The QA-05 anti-pattern is **long-lived** lambdas on player/timer signals where the widget can be destroyed before the lambda's next emission. Modal-dialog lambdas are not at risk because the dialog cannot outlive its `parent=self` MainWindow.

---

## UAT Log Regression Check

Source command:
```
grep -rn "RuntimeError.*Internal C\+\+ object already deleted" .planning/phases/ | grep -v 44-QA05-AUDIT.md
```

**Finding:** No UAT-log regression entries.

All grep hits are in research, planning, and context documentation discussing the QA-05 anti-pattern itself (37-CONTEXT.md, 37-RESEARCH.md, 37-03-PLAN.md, 37-04-PLAN.md, 39-RESEARCH.md, 40.1-RESEARCH.md, 44-VALIDATION.md, 44-CONTEXT.md, 44-05-PLAN.md). None are UAT incident reports. Specifically:

- `.planning/phases/37-station-list-now-playing/37-CONTEXT.md:155` — QA-05 gate definition
- `.planning/phases/37-station-list-now-playing/37-RESEARCH.md:477,480` — anti-pattern explanation + warning sign
- `.planning/phases/37-station-list-now-playing/37-03-PLAN.md:218` — TDD test-13 wraps in try/except, asserts no raise
- `.planning/phases/37-station-list-now-playing/37-04-PLAN.md:254` — TDD lifetime test 12
- `.planning/phases/39-core-dialogs/39-RESEARCH.md:225` — QThread local-variable anti-pattern explanation
- `.planning/phases/40.1-fix-youtube-live-stream-detection-in-import-discovery-play-s/40.1-RESEARCH.md:378` — `_LogoFetchWorker` cancellation discussion
- `.planning/phases/44-windows-packaging-installer/44-VALIDATION.md:52`, `44-CONTEXT.md:76`, `44-05-PLAN.md:118` — Phase 44's own audit definition

Phase 43.1 UAT (`43.1-UAT.md`) — the most recent live UAT log — passed UAT-1 through UAT-10 with no widget-lifetime regression. Phase 37 lifetime tests (test 12, test 13) were green at landing and haven't regressed (399 tests pass per 44-VALIDATION.md).

**Conclusion:** Clean. The Phase 37 `parent=` convention has held through Phases 38, 39, 40, 41, 42, 43, 43.1, 999.7 with no widget-lifetime escapes.

---

## Spot Fixes

- [x] None required. Grep sweep is clean: every QWidget/QDialog subclass passes `parent` through `super().__init__(parent)`; every dialog launch site from MainWindow passes `parent=self`; every long-lived player/media-keys signal connection is a bound method; the two `lambda` connections are dialog-scoped (lifetime ≤ MainWindow). No "Internal C++ object already deleted" entries in any UAT log from Phases 37–43.1.

---

## Sign-Off

- [x] All dialog subclasses pass `parent` to `super().__init__`
- [x] All dialog launch sites pass `parent=self` from MainWindow
- [x] All long-lived player/media-keys signal connections use bound methods (not self-capturing lambdas)
- [x] Transient dialog-scoped lambdas (2 occurrences in main_window.py:401, 416) inspected and accepted — lifetime bound to modal `EditStationDialog(parent=self)`
- [x] No "Internal C++ object already deleted" entries in UAT logs (Phases 37, 39, 40, 41, 42, 43.1)
- [x] No spot fixes required (no code changes from this audit)

**Auditor:** Claude (GSD executor agent)
**Date:** 2026-04-25
**Result:** PASS — QA-05 widget-lifetime gate clean. Phase 44 may proceed to UAT execution and ship-readiness sign-off.
