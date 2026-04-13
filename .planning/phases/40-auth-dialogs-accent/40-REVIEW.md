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
  warning: 5
  info: 3
  total: 8
status: issues_found
---

# Phase 40: Code Review Report

**Reviewed:** 2026-04-13T00:00:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

All three new dialogs (AccentColorDialog, AccountsDialog, CookieImportDialog) are structurally sound. Security controls are in place: hex input is validated before QSS interpolation, QProcess is used with `sys.executable` (no shell), token/cookie files get `0o600` permissions, and all QLabels use `Qt.PlainText`. The test suite is thorough for the critical paths.

Five warnings found: `build_accent_css` interpolates hex without validation (unlike its sibling); `apply_accent_palette` is called on startup without pre-validating the stored hex, allowing a corrupt DB value to silently set the accent to black; `_google_process` is not cleared after successful Google login, creating a stale reference; `FakeRepo` in integration tests is missing `get_station`, causing a latent `AttributeError`; and the hex error style is not cleared when the field is emptied. Three info items: dead export, lambda closure, and a defensive guard opportunity.

---

## Warnings

### WR-01: `build_accent_css` interpolates hex without validation

**File:** `musicstreamer/accent_utils.py:16-26`

**Issue:** `build_accent_css` interpolates `hex_value` directly into CSS without calling `_is_valid_hex`. Its sibling `build_accent_qss` explicitly validates and returns `""` for invalid input (lines 38-39). `build_accent_css` is currently unused in the Qt path but is a public export — it is a latent CSS injection risk if called with untrusted input.

**Fix:**
```python
def build_accent_css(hex_value: str) -> str:
    """Return CSS that overrides accent-colored widgets with the given hex color."""
    if not _is_valid_hex(hex_value):
        return ""
    return (
        f"button.suggested-action {{\n"
        f"    background-color: {hex_value};\n"
        ...
    )
```

---

### WR-02: `apply_accent_palette` called with unvalidated value on startup

**File:** `musicstreamer/ui_qt/main_window.py:97-100`

**Issue:** `_saved_accent = self._repo.get_setting("accent_color", "")` is passed directly to `apply_accent_palette` with only a truthiness check. `build_accent_qss` (called inside `apply_accent_palette`) validates and returns `""` for bad input, so the QSS is safe. However `palette.setColor(QPalette.ColorRole.Highlight, QColor(hex_value))` in `accent_utils.py:56` is called unconditionally — `QColor` silently accepts an invalid string as black (`#000000`), which would set the accent palette to black if a corrupt value is stored in the DB.

**Fix:**
```python
from musicstreamer.accent_utils import apply_accent_palette, _is_valid_hex

_saved_accent = self._repo.get_setting("accent_color", "")
if _saved_accent and _is_valid_hex(_saved_accent):
    apply_accent_palette(QApplication.instance(), _saved_accent)
```

---

### WR-03: `_google_process` not cleared after successful Google login

**File:** `musicstreamer/ui_qt/cookie_import_dialog.py:271-290`

**Issue:** `_on_google_process_finished` does not set `self._google_process = None` on the success path. If the dialog stays open after a successful import and the user somehow triggers a second login, `_on_google_login` would overwrite `self._google_process` with a new `QProcess` while the completed one's reference still lingers. More critically, `_on_google_process_finished` reads from `self._google_process` at line 279 — if a second process is started and its `finished` signal fires, it would read from the second process even though the first one may have already written its output.

**Fix:** Capture and clear the reference at the top of the handler:
```python
def _on_google_process_finished(self, exit_code: int, exit_status: object) -> None:
    proc = self._google_process   # capture before clearing
    self._google_process = None   # clear immediately
    self._google_btn.setEnabled(True)
    self._google_status_label.setVisible(False)

    if exit_code != 0 or proc is None:
        QMessageBox.warning(self, "Google Login", "Google login failed.")
        return

    stdout_bytes = proc.readAllStandardOutput().data()
    text = stdout_bytes.decode("utf-8", errors="replace").strip()
    ...
```

---

### WR-04: `FakeRepo` missing `get_station` — latent `AttributeError` in integration tests

**File:** `tests/test_main_window_integration.py:60-107`

**Issue:** `FakeRepo` does not implement `get_station`. `MainWindow._on_edit_requested` (line 211) calls `self._repo.get_station(station.id)`, and `_sync_now_playing_station` (line 228) does the same. No current test exercises this path, but any future test that emits `edit_requested` or `station_panel.edit_requested` will raise `AttributeError: 'FakeRepo' object has no attribute 'get_station'`.

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

### WR-05: Hex error style not cleared when field is emptied

**File:** `musicstreamer/ui_qt/accent_color_dialog.py:163-166`

**Issue:** `_on_hex_changed` only clears the red border style when the text is valid (line 154-155). The `else` branch applies the red border only `if text:` (line 165). Entering invalid text, then clearing the field leaves the red border visible — `text` is falsy so no style is applied, but the previous red border stylesheet is never reset to `""`.

**Fix:**
```python
else:
    if text:
        self._hex_edit.setStyleSheet("border: 1px solid #c0392b;")
    else:
        self._hex_edit.setStyleSheet("")  # clear error when field is emptied
```

---

## Info

### IN-01: `build_accent_css` is a dead export

**File:** `musicstreamer/accent_utils.py:16-26`

**Issue:** `build_accent_css` is defined but never imported or called anywhere in the Qt UI modules. If the GTK path has been fully replaced, this function is dead code. WR-01 (adding validation) is still recommended regardless.

**Fix:** Remove or add a comment noting it is retained for a future GTK build target.

---

### IN-02: Lambda closure over `fresh` in `_on_edit_requested`

**File:** `musicstreamer/ui_qt/main_window.py:216`

**Issue:** `dlg.station_saved.connect(lambda: self._sync_now_playing_station(fresh.id))` uses a lambda where other connections on the same dialog use bound methods (QA-05 comment at module top: "no self-capturing lambdas"). `fresh` is stable within this call so there is no correctness bug, but the inconsistency is worth aligning.

**Fix:**
```python
import functools
dlg.station_saved.connect(functools.partial(self._sync_now_playing_station, fresh.id))
```

---

### IN-03: `_cookie_to_netscape` uses non-idiomatic `str(bytes, encoding)` without error handling

**File:** `musicstreamer/oauth_helper.py:89-90`

**Issue:** `str(cookie.name(), "utf-8")` and `str(cookie.value(), "utf-8")` are valid but unusual. If a cookie contains non-UTF-8 bytes (uncommon but possible), this raises `UnicodeDecodeError` uncaught, crashing the subprocess.

**Fix:**
```python
name = cookie.name().decode("utf-8", errors="replace")
value = cookie.value().decode("utf-8", errors="replace")
```

---

_Reviewed: 2026-04-13T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
