---
phase: 42-settings-export-import
reviewed: 2026-04-16T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - musicstreamer/settings_export.py
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/ui_qt/settings_import_dialog.py
  - tests/test_settings_export.py
  - tests/test_settings_import_dialog.py
findings:
  critical: 0
  warning: 3
  info: 5
  total: 8
status: issues_found
---

# Phase 42: Code Review Report

**Reviewed:** 2026-04-16
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the settings export/import feature (SYNC-01..05). The pure-logic module (`settings_export.py`) is well-structured with clear separation between `build_zip`, `preview_import`, and `commit_import`, and uses a single SQLite transaction for atomicity. The Qt integration in `main_window.py` correctly threads export/preview via `QThread` with connection-per-thread and retains worker references to prevent GC. The dialog uses QueuedConnection for cross-thread signal delivery and confirms `replace_all` via a modal warning.

No critical security or correctness issues found. The path-traversal guard and credential-exclusion logic both function as intended. Three Warnings relate to defense-in-depth gaps (re-validation in `commit_import`, filesystem rollback on partial failure, schema robustness for malformed settings entries). Info items cover minor polish (lost error detail, test coverage gaps, unused error messages).

## Warnings

### WR-01: Filesystem logo writes are not rolled back on DB transaction failure

**File:** `musicstreamer/settings_export.py:247-274`
**Issue:** `commit_import` writes extracted logo files to `assets/{station_id}/station_art{ext}` inside the `with repo.con:` block. If any SQL statement fails mid-loop (e.g. a later stream INSERT, a bad favorites row), the SQLite transaction rolls back all DB changes but the logo files already written to disk remain. This leaves orphaned files referencing station IDs that no longer exist in the DB. On `replace_all` mode this is especially messy because the old `assets/` tree was not wiped but the DB now points at reused IDs.
**Fix:** Accumulate `(abs_path, bytes)` tuples in a list during the loop and only flush to disk after the `with repo.con:` exits successfully. Example:
```python
pending_logos = []  # [(art_abs, bytes)]
with repo.con:
    # ... do all DB work, including UPDATE stations SET station_art_path=? ...
    # but defer the actual file write:
    pending_logos.append((art_abs, logo_src.read()))
# After commit:
for art_abs, data in pending_logos:
    os.makedirs(os.path.dirname(art_abs), exist_ok=True)
    with open(art_abs, "wb") as f:
        f.write(data)
```
Alternatively, write to a temp path and `os.rename` after commit so partial state never lands at the final location.

### WR-02: `commit_import` does not re-validate ZIP members (TOCTOU)

**File:** `musicstreamer/settings_export.py:247-248`
**Issue:** `preview_import` validates zip members for path-traversal (`..`, leading `/`), but `commit_import` re-opens the ZIP from `preview.zip_path` without repeating the check. Between preview and commit the file on disk could change (user swaps, antivirus quarantines then restores a modified copy, etc.). While `logo_file in zip_names` gates extraction to named members, a malicious ZIP swap could still bypass the intended invariant that no archive contents ever trigger traversal-like logic. Defense-in-depth practice is to revalidate at the point of use.
**Fix:** Extract the validation into a helper and call it in both places:
```python
def _validate_zip_members(zf: zipfile.ZipFile) -> None:
    for member in zf.infolist():
        fname = member.filename
        if fname.startswith("/") or ".." in fname or "\\" in fname:
            raise ValueError(f"Unsafe path in archive: {fname}")

# in commit_import:
with zipfile.ZipFile(preview.zip_path, "r") as zf:
    _validate_zip_members(zf)
    zip_names = set(zf.namelist())
```
Also consider adding `"\\"` to the rejection set for Windows-style separators.

### WR-03: Settings row uses `setting["key"]` / `setting["value"]` without `.get()`

**File:** `musicstreamer/settings_export.py:294-295`
**Issue:** Every other JSON consumer in this module uses `.get("field", "")` to tolerate malformed rows, but the settings loop uses direct `setting["key"]` / `setting["value"]` access. A malformed settings entry (e.g. `{"key": "volume"}` missing `"value"`, or `{}`) raises `KeyError` inside the `with repo.con:` block, aborts the entire import, and rolls back everything — including successfully imported stations and favorites. This is a fragile failure mode for a v1 schema that may evolve.
**Fix:**
```python
for setting in preview.settings:
    key = setting.get("key")
    if not key:
        continue  # skip malformed entry; do not fail whole import
    repo.con.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES (?,?)",
        (key, setting.get("value", "")),
    )
```

## Info

### IN-01: Error detail is discarded in `_on_import_preview_error`

**File:** `musicstreamer/ui_qt/main_window.py:438-439`
**Issue:** The slot receives a `msg` argument but shows a generic "Invalid settings file" toast, losing the specific ValueError message (e.g. "Unsupported version: 99", "Unsafe path in archive: ../evil", "Missing settings.json"). Users cannot tell what is wrong with their file.
**Fix:** Include the error detail, truncated:
```python
def _on_import_preview_error(self, msg: str) -> None:
    truncated = msg[:80] + "\u2026" if len(msg) > 80 else msg
    self.show_toast(f"Invalid settings file: {truncated}")
```

### IN-02: `_on_commit_error` path is uncovered and marked `# pragma: no cover`

**File:** `musicstreamer/ui_qt/settings_import_dialog.py:64-65`
**Issue:** The worker's `except Exception` branch is marked `# pragma: no cover` but represents the primary failure path for import commits (disk full, schema migration mismatch, corrupt ZIP swapped post-preview). Marking the main error path as uncoverable hides real bugs.
**Fix:** Add a test that injects a failing `commit_import` (e.g. monkeypatch to raise) and asserts the error toast and re-enabled Import button. Remove the pragma.

### IN-03: `test_settings_import_dialog.py` does not exercise the commit flow

**File:** `tests/test_settings_import_dialog.py:1-55`
**Issue:** Tests cover initial widget state (summary label, mode toggle, warning visibility, tree population, title) but never click the Import button, assert the replace_all confirmation dialog appears, or verify `import_complete` emission. The commit path is the dialog's core responsibility.
**Fix:** Add tests that:
- Click Import in merge mode with a real (or mocked) preview and assert `import_complete` fires.
- Select replace_all, use `QTest` / monkeypatch of `QMessageBox.warning` to return Cancel, and assert worker is not started.
- Verify the Import button is disabled during commit and re-enabled on error.

### IN-04: Weak path-traversal check also rejects legitimate names

**File:** `musicstreamer/settings_export.py:182`
**Issue:** `".." in fname` uses substring matching, so a legitimate filename like `logos/foo..bar.jpg` would be rejected. It also does not reject backslash separators (`logos\\..\\evil`) which matter if a Windows-produced archive is ever consumed.
**Fix:** Use a proper normalization check:
```python
import posixpath
normalized = posixpath.normpath(fname)
if (normalized.startswith("/") or normalized.startswith("../")
        or normalized == ".." or "\\" in fname):
    raise ValueError(f"Unsafe path in archive: {fname}")
```

### IN-05: `_sanitize` can return "." or ".." for pathological station names

**File:** `musicstreamer/settings_export.py:61-68`
**Issue:** A station named `".."` or `"."` passes through `_sanitize` unchanged (dots are preserved by the `[^\w\s.\-]` allow-list, `strip()` doesn't remove dots, non-empty result skips the `"station"` fallback). The resulting archive member is `logos/..jpg` or `logos/..{ext}`, which would then be rejected by the importer's own `".."` substring check — i.e. an export can produce a ZIP that fails its own re-import validation. Very unlikely in practice but worth hardening.
**Fix:** After the current logic, add an explicit check:
```python
name = name[:80]
if name in (".", "..") or not name:
    return "station"
return name
```

---

_Reviewed: 2026-04-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
