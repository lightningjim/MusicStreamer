---
phase: 42-settings-export-import
reviewed: 2026-04-16T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - musicstreamer/settings_export.py
  - musicstreamer/ui_qt/settings_import_dialog.py
  - musicstreamer/ui_qt/main_window.py
  - tests/test_settings_export.py
  - tests/test_settings_import_dialog.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 42: Code Review Report

**Reviewed:** 2026-04-16
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

The export/import logic is well-structured: credentials exclusion,
path-traversal guard, and the single-transaction guarantee in `commit_import`
are all correctly implemented. The `replace_all` branch correctly routes
URL-matched stations to `_insert_station` (not `_replace_station`) after wiping
the DB. Background-thread patterns in both `main_window.py` and
`settings_import_dialog.py` follow established project convention.

Three warnings: unbounded logo write (potential disk fill), a worker debounce
gap that can produce duplicate signal firings, and a swallowed error message on
preview failure. Three info items cover typing gaps and test coverage.

---

## Warnings

### WR-01: Logo file written without size limit — potential disk fill

**File:** `musicstreamer/settings_export.py:268-270`
**Issue:** During `commit_import`, logo data is read from the ZIP in one call
(`logo_src.read()`) and written to disk with no size check. A crafted ZIP with a
multi-GB deflated logo entry will fill the filesystem before any error surfaces.
ZIP-bomb style entries (tiny compressed, huge uncompressed) are the primary
concern.
**Fix:**
```python
MAX_LOGO_BYTES = 5 * 1024 * 1024  # 5 MB

with zf.open(logo_file) as logo_src:
    data = logo_src.read(MAX_LOGO_BYTES + 1)
    if len(data) > MAX_LOGO_BYTES:
        continue  # skip oversized logo; station still imported without art
    with open(art_abs, "wb") as logo_dst:
        logo_dst.write(data)
```

---

### WR-02: `_on_import_preview_error` silently discards the error reason

**File:** `musicstreamer/ui_qt/main_window.py:438-439`
**Issue:** When `preview_import` raises (bad ZIP, path traversal, wrong
version), the error handler shows a fixed "Invalid settings file" toast and
drops `msg`. Users cannot distinguish a corrupt file from a version mismatch.

```python
def _on_import_preview_error(self, msg: str) -> None:
    self.show_toast("Invalid settings file")   # msg silently dropped
```

**Fix:**
```python
def _on_import_preview_error(self, msg: str) -> None:
    short = msg[:60] + "\u2026" if len(msg) > 60 else msg
    self.show_toast(f"Import failed \u2014 {short}")
```

---

### WR-03: Worker reference overwritten before thread completes — stale signal firings

**File:** `musicstreamer/ui_qt/main_window.py:401-404` and `423-430`
**Issue:** `self._export_worker` and `self._import_preview_worker` are the sole
strong references keeping each worker alive from the Python side. If the user
triggers Export (or Import Settings) a second time while the first thread is
still running, the old reference is overwritten. Qt's parent keeps the thread
alive, but the `finished`/`error` connections from the old thread remain and
fire into `_on_export_done` / `_on_import_preview_ready` with stale data — a
second run can open a stale import dialog on top of the current one.
**Fix:** Guard against re-entry at the top of each handler:
```python
def _on_export_settings(self) -> None:
    if self._export_worker and self._export_worker.isRunning():
        return
    ...

def _on_import_settings(self) -> None:
    if self._import_preview_worker and self._import_preview_worker.isRunning():
        return
    ...
```

---

## Info

### IN-01: `_EXCLUDED_SETTINGS` is easy to miss when adding new credential keys

**File:** `musicstreamer/settings_export.py:28`
**Issue:** The credential exclusion list is a module-level bare set. As the
settings table grows, new credential keys can be added without noticing this
exclusion list exists.
**Fix:** Rename to `_CREDENTIAL_SETTINGS` (or `_EXPORT_EXCLUDED_KEYS`) and add
a comment: `# Add any credential / machine-local keys here to prevent export.`

---

### IN-02: `ImportPreview` list fields typed as bare `list`

**File:** `musicstreamer/settings_export.py:49-53`
**Issue:** `detail_rows`, `track_favorites`, and `settings` are annotated as
`list` without element types. `mypy` infers `Any` for their contents, which
defeats type checking in `commit_import`.
**Fix:**
```python
detail_rows: List[ImportDetailRow] = field(default_factory=list)
track_favorites: List[dict] = field(default_factory=list)
settings: List[dict] = field(default_factory=list)
```

---

### IN-03: No test for `_on_import_preview_error` / error-path toast content

**File:** `tests/test_settings_import_dialog.py` (missing coverage)
**Issue:** The dialog tests cover only the happy-path constructor. The error
path (`_on_import_preview_error` in `main_window.py`) has no test, so WR-02's
silent discard would not be caught by regression.
**Fix:** Add a test (in `tests/test_main_window.py` or a new file) that calls
`_on_import_preview_error("Unsupported version: 99")` and asserts the toast text
includes the error detail.

---

_Reviewed: 2026-04-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
