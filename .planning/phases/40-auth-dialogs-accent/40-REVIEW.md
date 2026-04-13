---
phase: 40-auth-dialogs-accent
reviewed: 2026-04-13T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - musicstreamer/accent_utils.py
  - musicstreamer/oauth_helper.py
  - musicstreamer/subprocess_utils.py
  - musicstreamer/ui_qt/accent_color_dialog.py
  - musicstreamer/ui_qt/accounts_dialog.py
  - musicstreamer/ui_qt/cookie_import_dialog.py
  - musicstreamer/ui_qt/main_window.py
  - tests/test_accent_color_dialog.py
  - tests/test_accounts_dialog.py
  - tests/test_cookie_import_dialog.py
  - tests/test_main_window_integration.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 40: Code Review Report

**Reviewed:** 2026-04-13
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

All three new dialogs (AccentColorDialog, AccountsDialog, CookieImportDialog) are structurally sound. Security controls are in place: hex input is validated before QSS interpolation, QProcess is used with `sys.executable` (no shell), token/cookie files get `0o600` permissions, and all QLabels use `Qt.PlainText`. The test suite is thorough and covers the critical paths.

Three warnings found: a missing `FakeRepo.get_station` stub in the integration tests causes any test that reaches `_on_edit_requested` to crash with `AttributeError`; `_on_google_process_finished` references `self._google_process` after nullability check has already guarded against `None` but doesn't null it out on success, leaving a stale reference; and `build_accent_css` in `accent_utils.py` interpolates `hex_value` without validation (unlike its sibling `build_accent_qss`). Three info items cover dead export, a lambda with a stale closure, and a minor UX gap in the hex error style.

## Warnings

### WR-01: `FakeRepo` in integration tests missing `get_station` — AttributeError on `_on_edit_requested`

**File:** `tests/test_main_window_integration.py:60-107`
**Issue:** `FakeRepo` does not implement `get_station`. `MainWindow._on_edit_requested` (line 211) calls `self._repo.get_station(station.id)`, and `_sync_now_playing_station` (line 228) does the same. Any test that triggers the `edit_requested` signal — directly or indirectly — will raise `AttributeError: 'FakeRepo' object has no attribute 'get_station'`. No current test exercises this path, but it is one `station_panel.edit_requested.emit(station)` call away from a confusing failure.

**Fix:**
```python
# In FakeRepo (test_main_window_integration.py)
def get_station(self, station_id: int):
    for s in self._stations:
        if s.id == station_id:
            return s
    return None
```

---

### WR-02: `_google_process` not cleared after successful Google login

**File:** `musicstreamer/ui_qt/cookie_import_dialog.py:271-290`
**Issue:** `_on_google_process_finished` returns early when `exit_code != 0 or self._google_process is None` (line 275) but does not set `self._google_process = None` after a successful path (lines 279-290). If the user successfully imports cookies and then clicks "Open Google Login" a second time within the same dialog session, the old `QProcess` reference lingers. The new `QProcess` object assigned at line 264 replaces `self._google_process`, so this is not a crash, but the old process is not explicitly cleaned up and `_on_google_process_finished` reads from `self._google_process` (line 279) — if signals fire out of order, it would read the new process's output, not the completed one's.

**Fix:** Capture the process reference locally before clearing, and clear at the end of the handler:
```python
def _on_google_process_finished(self, exit_code: int, exit_status: object) -> None:
    proc = self._google_process          # capture before clearing
    self._google_process = None          # clear immediately
    self._google_btn.setEnabled(True)
    self._google_status_label.setVisible(False)

    if exit_code != 0 or proc is None:
        QMessageBox.warning(self, "Google Login", "Google login failed.")
        return

    stdout_bytes = proc.readAllStandardOutput().data()
    ...
```

---

### WR-03: `build_accent_css` interpolates hex without validation

**File:** `musicstreamer/accent_utils.py:16-26`
**Issue:** `build_accent_css` takes a `hex_value` parameter and interpolates it directly into CSS without calling `_is_valid_hex`. Its sibling `build_accent_qss` explicitly validates and returns `""` for bad input (lines 38-39). `build_accent_css` appears to be a GTK/legacy path that is currently unused by the Qt UI, but it is a public export and the inconsistency is a latent injection risk if it is ever called with untrusted input.

**Fix:**
```python
def build_accent_css(hex_value: str) -> str:
    """Return CSS that overrides accent-colored widgets with the given hex color."""
    if not _is_valid_hex(hex_value):
        return ""
    return (
        f"button.suggested-action {{\n"
        ...
    )
```

---

## Info

### IN-01: `build_accent_css` is a dead export — not called anywhere in Qt path

**File:** `musicstreamer/accent_utils.py:16-26`
**Issue:** `grep` confirms `build_accent_css` is defined but never imported or called from any Qt UI module. If the GTK code path has been fully superseded, this function is dead code. Fixing WR-03 is still recommended in case it is used in future or by external callers.

**Fix:** Either remove the function or add a comment noting it is retained for the GTK path.

---

### IN-02: Lambda with stale closure in `_on_edit_requested`

**File:** `musicstreamer/ui_qt/main_window.py:216`
**Issue:** `dlg.station_saved.connect(lambda: self._sync_now_playing_station(fresh.id))` captures `fresh` by closure. `fresh` is re-fetched from the DB at line 211 and passed to `EditStationDialog` at line 214. If the station ID changes between dialog open and `station_saved` emission (unlikely but possible if a future flow re-uses the dialog), the lambda still closes over the original `fresh.id`. The pattern is consistent with the rest of the codebase but worth noting.

**Fix:** Use a bound partial instead:
```python
import functools
dlg.station_saved.connect(functools.partial(self._sync_now_playing_station, fresh.id))
```
Or pass `station.id` rather than `fresh.id` since both are the same at that point.

---

### IN-03: Hex error style not cleared when field is emptied

**File:** `musicstreamer/ui_qt/accent_color_dialog.py:163-165`
**Issue:** The `_on_hex_changed` handler only clears the red border style when the text is valid (line 154). The `else` branch applies the red border only `if text` (line 164) — so entering invalid text, then deleting all characters, leaves the red border visible since `text` is empty (falsy) but the stylesheet is not reset to `""`.

**Fix:**
```python
else:
    if text:
        self._hex_edit.setStyleSheet("border: 1px solid #c0392b;")
    else:
        self._hex_edit.setStyleSheet("")  # clear error when field is emptied
```

---

_Reviewed: 2026-04-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
