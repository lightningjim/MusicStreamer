# Phase 42: Settings Export/Import - Research

**Researched:** 2026-04-16
**Domain:** Python stdlib zipfile, PySide6 QFileDialog/QThread/QDialog, SQLite data serialization
**Confidence:** HIGH

## Summary

Phase 42 is entirely within the existing project stack — no new dependencies. Python's stdlib `zipfile` covers ZIP creation and reading without any third-party library. All data access goes through the existing `Repo` class. The credential exclusion list (`audioaddict_listen_key`, `cookies.txt`, `twitch-token.txt`) is confirmed against the live settings table.

The main implementation complexity is the import merge logic and the summary dialog UX. Everything else (file pickers, thread workers, toast errors) follows established patterns already in the codebase.

**Primary recommendation:** Implement export/import as two new files — `musicstreamer/settings_export.py` (pure logic, no Qt) and `musicstreamer/ui_qt/settings_import_dialog.py` (summary/merge UI). Wire both into `main_window.py` via QThread workers matching the `import_dialog.py` pattern.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Full DB dump — settings.json contains all stations, streams, station_streams, favorites (ICY track favorites and station star flags), providers, and settings table entries.
- **D-02:** Station logos stored as `logos/<sanitized_station_name>.<ext>` in the ZIP — human-readable, filesystem-safe names.
- **D-03:** Include `last_played_at` timestamps — full fidelity round-trip.
- **D-04:** Include `is_favorite` station star flags alongside ICY track favorites table.
- **D-05:** Cookies (`cookies.txt`), Twitch OAuth tokens (`twitch-token.txt`), and AudioAddict API keys (`audioaddict_listen_key`) are explicitly excluded from the export.
- **D-06:** Merge key is **stream URL** — match imported stations against existing by any URL in `station_streams`. Uses existing `Repo.station_exists_by_url()`.
- **D-07:** Import dialog has a **Merge / Replace All toggle** (radio buttons or segmented control), defaulting to Merge.
- **D-08:** On URL match in Merge mode, **replace everything** on the existing station.
- **D-09:** Favorites merge as **union** — `INSERT OR IGNORE` by `(station_name, track_title)`. Replace All mode replaces favorites too.
- **D-10:** Import summary dialog shows **counts + expandable list** — "12 added, 3 replaced, 1 skipped, 0 errors" at top with expandable section listing each station and its action.
- **D-11:** **All-or-nothing** — no per-station cherry-picking. OK or Cancel.
- **D-12:** Malformed/invalid ZIPs get a **toast + abort** — "Invalid settings file" toast, no partial import.
- **D-13:** Export default filename `musicstreamer-export-YYYY-MM-DD.zip`.
- **D-14:** File dialog defaults to **user's Documents folder** — `QStandardPaths.DocumentsLocation`.

### Claude's Discretion

- JSON schema design within settings.json (field names, nesting structure)
- Station name sanitization strategy for logo filenames in the ZIP
- Exact layout of the import summary dialog (widget choices, sizing)
- Whether "Replace All" mode prompts a confirmation before wiping

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SYNC-01 | Export produces `.zip` with `settings.json` + `logos/` folder; credentials absent | stdlib zipfile confirmed; credential key list verified against live DB |
| SYNC-02 | Export explicitly excludes cookies, Twitch tokens, AudioAddict API keys | Settings keys audited: exclude `audioaddict_listen_key`; files `cookies.txt`, `twitch-token.txt` are path-based, not in ZIP by construction |
| SYNC-03 | Import merges by stream URL; replace-on-match; user toggle for replace-all vs merge | `Repo.station_exists_by_url()` confirmed; all write accessors confirmed |
| SYNC-04 | Import summary dialog (N added, M replaced, K skipped, L errors) before committing | All-or-nothing transaction via SQLite; QDialog pattern confirmed |
| SYNC-05 | Export/Import accessible from hamburger menu | Placeholder actions at lines 101–107 confirmed; just enable + connect |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ZIP creation/writing | Backend module (`settings_export.py`) | — | Pure I/O; no Qt needed; testable without Qt |
| ZIP validation/reading | Backend module (`settings_export.py`) | — | Same; error results returned as data, not exceptions propagated to UI |
| Merge logic (add/replace/skip) | Backend module (`settings_export.py`) | Repo layer | Business logic belongs off UI thread |
| File picker (save/open) | UI (main_window.py handlers) | — | Qt file dialogs must run on main thread |
| Long-running I/O (export/import with 400+ stations) | QThread worker | — | Matches existing import_dialog.py pattern |
| Summary dialog | UI (`settings_import_dialog.py`) | — | Modal QDialog; shown after worker completes |
| Menu wiring | UI (main_window.py lines 101–107) | — | Enable existing disabled placeholders |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `zipfile` (stdlib) | Python 3.x | ZIP creation and reading | No extra dep; `BadZipFile` covers invalid archive detection [VERIFIED: live test] |
| `json` (stdlib) | Python 3.x | settings.json serialization | Already used project-wide |
| `re` + `unicodedata` (stdlib) | Python 3.x | Station name sanitization for logo filenames | No extra dep [VERIFIED: live test] |
| `PySide6.QtCore.QStandardPaths` | installed | Documents folder resolution | [VERIFIED: resolves `/home/kcreasey/Documents` on Linux] |
| `PySide6.QtWidgets.QFileDialog` | installed | File save/open pickers | Existing pattern in `cookie_import_dialog.py` [VERIFIED: codebase] |
| `PySide6.QtCore.QThread` | installed | Background export/import worker | Existing pattern in `import_dialog.py` [VERIFIED: codebase] |

**No new dependencies required.** [VERIFIED: all imports available in existing virtualenv]

---

## Architecture Patterns

### System Architecture Diagram

```
[Hamburger Menu]
  act_export.triggered ──────────────────────────────────┐
  act_import_settings.triggered ─────────────────────┐   │
                                                      │   │
[MainWindow handlers]                                 │   │
  _on_export_settings() ────── QFileDialog.getSaveFileName
                                    │ path
                              _ExportWorker(QThread)
                                    │ run(): settings_export.build_zip(repo, path)
                                    │ finished()/error() → toast
                                    
  _on_import_settings() ────── QFileDialog.getOpenFileName
                                    │ path
                              _ImportPreviewWorker(QThread)
                                    │ run(): settings_export.preview_import(path, repo)
                                    │ Returns: ImportPreview(added, replaced, skipped, errors, detail_rows)
                                    │
                              [SettingsImportDialog]  ← shown with preview data
                                    │ user clicks OK / Cancel
                                    │ OK → _ImportCommitWorker(QThread)
                                    │        run(): settings_export.commit_import(preview, repo, mode)
                                    │        finished() → toast + station_list refresh

[settings_export.py] (no Qt)
  build_zip(repo, dest_path)        — writes ZIP to dest_path
  preview_import(zip_path, repo)    — validates + dry-run, returns ImportPreview
  commit_import(preview, repo, mode) — applies ImportPreview to DB (transactional)
```

### Recommended Project Structure

```
musicstreamer/
├── settings_export.py      # NEW: pure ZIP/JSON logic (no Qt)
musicstreamer/ui_qt/
├── settings_import_dialog.py   # NEW: summary dialog
├── main_window.py              # MODIFY: enable placeholders, add handlers + workers
tests/
├── test_settings_export.py     # NEW: unit tests for build_zip, preview_import, commit_import
```

### Pattern 1: ZIP Export (stdlib zipfile)

```python
# Source: stdlib zipfile — VERIFIED via live test
import zipfile, json, os, re, unicodedata, datetime

def build_zip(repo, dest_path: str) -> None:
    """Write full settings archive to dest_path."""
    stations = repo.list_stations()
    favorites = repo.list_favorites()
    # Exclude credential keys (D-05)
    _EXCLUDED_KEYS = {"audioaddict_listen_key"}
    settings_rows = [
        {"key": r["key"], "value": r["value"]}
        for r in repo.con.execute("SELECT key, value FROM settings").fetchall()
        if r["key"] not in _EXCLUDED_KEYS
    ]

    payload = {
        "version": 1,
        "exported_at": datetime.datetime.now().isoformat(),
        "stations": [_station_to_dict(s) for s in stations],
        "track_favorites": [_fav_to_dict(f) for f in favorites],
        "settings": settings_rows,
    }

    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("settings.json", json.dumps(payload, indent=2))
        for station in stations:
            art = station.station_art_path
            if art:
                abs_path = os.path.join(paths.data_dir(), art) if not os.path.isabs(art) else art
                if os.path.exists(abs_path):
                    ext = os.path.splitext(abs_path)[1]
                    logo_name = f"logos/{_sanitize(station.name)}{ext}"
                    zf.write(abs_path, logo_name)
```

### Pattern 2: Logo filename sanitization

```python
# VERIFIED: live test — handles Unicode, slashes, colons, emoji
def _sanitize(name: str) -> str:
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w\s.-]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return (name[:80] or "station")
```

**Note:** Two stations sanitizing to the same filename (e.g. "SomaFM Groove Salad" twice) will silently overwrite in the ZIP. Acceptable for a personal-scale export. If collision is a concern, append `_{station_id}` to disambiguate.

### Pattern 3: QThread worker (matches import_dialog.py)

```python
# Source: musicstreamer/ui_qt/import_dialog.py — VERIFIED codebase
class _ImportPreviewWorker(QThread):
    finished = Signal(object)   # ImportPreview dataclass
    error = Signal(str)

    def __init__(self, zip_path: str, parent=None):
        super().__init__(parent)
        self._zip_path = zip_path

    def run(self):
        try:
            from musicstreamer.repo import db_connect, Repo
            repo = Repo(db_connect())   # thread-local connection
            result = settings_export.preview_import(self._zip_path, repo)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))
```

### Pattern 4: Invalid ZIP detection

```python
# Source: stdlib zipfile — VERIFIED via live test
import zipfile
try:
    with zipfile.ZipFile(path, "r") as zf:
        if "settings.json" not in zf.namelist():
            raise ValueError("Missing settings.json")
        payload = json.loads(zf.read("settings.json"))
        if payload.get("version") != 1:
            raise ValueError(f"Unsupported version: {payload.get('version')}")
except zipfile.BadZipFile:
    raise ValueError("Not a valid ZIP archive")
```

### Pattern 5: All-or-nothing import transaction

```python
# Use a single DB transaction to guarantee atomicity (D-11)
def commit_import(preview, repo, mode: str) -> None:
    """mode: 'merge' | 'replace_all'"""
    with repo.con:  # implicit BEGIN/COMMIT or ROLLBACK
        if mode == "replace_all":
            repo.con.execute("DELETE FROM station_streams")
            repo.con.execute("DELETE FROM stations")
            repo.con.execute("DELETE FROM favorites")
            repo.con.execute("DELETE FROM providers")
        for item in preview.detail_rows:
            if item.action in ("add", "replace"):
                _apply_station(repo, item, mode)
        # Favorites union (merge) or replace (replace_all already cleared)
        for fav in preview.track_favorites:
            repo.add_favorite(fav["station_name"], fav["provider_name"],
                              fav["track_title"], fav["genre"])
```

### Pattern 6: File dialog with Documents default (D-13, D-14)

```python
# Source: QStandardPaths — VERIFIED resolves /home/kcreasey/Documents on this machine
from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QFileDialog
import datetime, os

def _on_export_settings(self):
    docs = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation
    )
    default = os.path.join(docs, f"musicstreamer-export-{datetime.date.today().isoformat()}.zip")
    path, _ = QFileDialog.getSaveFileName(
        self, "Export Settings", default, "ZIP Archive (*.zip)"
    )
    if not path:
        return
    # launch _ExportWorker(path, self._repo, parent=self)
```

### Pattern 7: Summary dialog layout (D-10)

```
SettingsImportDialog
├── QLabel "12 added, 3 replaced, 1 skipped, 0 errors"   (summary line)
├── QLabel "▶ Details" (clickable/toggle)                  (expandable)
├── QListWidget (initially hidden, shown on toggle)         (per-station rows)
│     "✓ Added: Station Name"
│     "↻ Replaced: Other Station"
│     "— Skipped: Already exists"
│     "✗ Error: Bad entry"
├── QGroupBox "Import mode"
│     ○ Merge (add new + replace matches)   [default]
│     ○ Replace All (wipe library + restore)
└── QDialogButtonBox (OK / Cancel)
```

Widgets: `QLabel`, `QListWidget`, `QRadioButton`/`QButtonGroup`, `QDialogButtonBox(Ok|Cancel)`. All existing in the project. `QListWidget` is already used in `import_dialog.py`.

**Replace All confirmation:** Per Claude's Discretion — recommend a `QMessageBox.warning` confirm step when user selects Replace All and clicks OK, before dispatching the commit worker. Text: "This will erase your entire station library and replace it with the import. Continue?"

### Anti-Patterns to Avoid

- **Passing `Repo` across thread boundary:** The commit worker must open its own `db_connect()`. Never pass `self._repo` into a QThread. [VERIFIED: established pattern in `import_dialog.py`]
- **Importing logos synchronously on main thread:** Asset writes during import can be slow for 400+ stations. Do in the commit worker thread.
- **Partial import on error:** Use a single `with repo.con:` transaction block. Any exception rolls back automatically via SQLite context manager.
- **Relative art path in import:** When writing imported logos to disk, set `station_art_path` as a relative path `assets/<station_id>/station_art<ext>` to match the existing convention (D-03 round-trip fidelity). Create the `assets/<id>/` directory.
- **Logo filename collisions in ZIP:** Two stations with identical sanitized names produce the same logo filename. The last one wins. Acceptable for export; on import, `logo_file` in the JSON is the authoritative link, not the filename.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ZIP creation | Custom archive writer | `zipfile.ZipFile` (stdlib) | Handles compression, streaming, error detection |
| Invalid archive detection | Manual header check | `zipfile.BadZipFile` exception | stdlib raises this automatically on any invalid ZIP |
| File dialogs | Custom file picker widget | `QFileDialog.getSaveFileName` / `getOpenFileName` | OS-native picker; existing pattern in cookie_import_dialog.py |
| Background I/O | `threading.Thread` | `QThread` with `Signal` | Consistent with all other workers; Qt signal delivery to main thread is safe |
| Documents folder path | Hardcoded `~/Documents` | `QStandardPaths.DocumentsLocation` | Works correctly on Linux and Windows [VERIFIED] |

---

## Settings JSON Schema

Claude's Discretion — recommended schema:

```json
{
  "version": 1,
  "exported_at": "2026-04-16T11:30:00.000",
  "stations": [
    {
      "name": "Station Name",
      "provider": "DI.fm",
      "tags": "electronic,trance",
      "icy_disabled": false,
      "is_favorite": true,
      "last_played_at": "2026-04-16T10:00:00.000",
      "logo_file": "logos/Station_Name.jpg",
      "streams": [
        {
          "url": "http://...",
          "label": "Hi",
          "quality": "hi",
          "position": 1,
          "stream_type": "shoutcast",
          "codec": "MP3"
        }
      ]
    }
  ],
  "track_favorites": [
    {
      "station_name": "Station Name",
      "provider_name": "DI.fm",
      "track_title": "Artist - Track",
      "genre": "trance",
      "created_at": "2026-04-16T10:00:00.000"
    }
  ],
  "settings": [
    {"key": "accent_color", "value": "#bf00ff"},
    {"key": "audioaddict_quality", "value": "hi"},
    {"key": "volume", "value": "90"}
  ]
}
```

**Excluded keys:** `audioaddict_listen_key` [VERIFIED: only credential key in live settings table]. File-based credentials (`cookies.txt`, `twitch-token.txt`) are excluded by construction (not included in ZIP).

**`logo_file` field:** `null` when station has no art. Importer checks `logo_file is not None` before attempting extraction.

---

## Common Pitfalls

### Pitfall 1: Station art path convention on import
**What goes wrong:** Imported station art written to a path that doesn't follow the `assets/<station_id>/station_art<ext>` convention, causing `_art_paths.abs_art_path()` to silently return null.
**Why it happens:** Export stores sanitized-name logo paths; import needs to remap to ID-based paths after inserting the station and getting its new `station_id`.
**How to avoid:** In the commit worker, after `repo.insert_station()` returns the new `station_id`, write the logo to `assets/<station_id>/station_art<ext>` and call `repo.update_station_art(station_id, f"assets/{station_id}/station_art{ext}")`.
**Warning signs:** Station rows appear in DB but logos show as fallback icon after import.

### Pitfall 2: Merge mode "replace" leaves stale streams
**What goes wrong:** In Merge mode on URL match, the station row is updated but old `station_streams` rows aren't deleted, leaving duplicate streams.
**Why it happens:** `Repo.update_station()` doesn't touch `station_streams`.
**How to avoid:** On replace: `DELETE FROM station_streams WHERE station_id=?` before re-inserting streams from the import. Foreign key `ON DELETE CASCADE` would also handle this via `delete_station`, but re-insert is cleaner.
**Warning signs:** Stations with doubled stream lists after import.

### Pitfall 3: Replace All mode foreign key ordering
**What goes wrong:** DELETE on `stations` without first deleting `station_streams` raises FK constraint error even with `ON DELETE CASCADE` if executed in a script context with `PRAGMA foreign_keys = ON` and the cascade hasn't fired yet.
**Why it happens:** SQLite FK cascades fire per-row during DELETE, but in Replace All we execute in a transaction. Order matters.
**How to avoid:** Delete `station_streams` before `stations`, or rely on `ON DELETE CASCADE` (already schema-defined) and trust it. Safest: delete `station_streams` explicitly first, then `stations`.
**Warning signs:** `FOREIGN KEY constraint failed` on import in Replace All mode.

### Pitfall 4: QThread parent ownership vs. worker lifetime
**What goes wrong:** Worker QThread is GC'd before `finished` signal fires, causing a crash or silent drop.
**Why it happens:** Local variable goes out of scope.
**How to avoid:** Keep a reference on the dialog/window: `self._export_worker = _ExportWorker(...)`. Pattern already established in `import_dialog.py` with `self._yt_scan_worker` etc.

### Pitfall 5: Large export blocking UI
**What goes wrong:** 400 stations × ~2 assets each = potentially slow disk I/O. If run synchronously on the main thread, the window freezes.
**Why it happens:** Export wasn't put on a worker thread.
**How to avoid:** Always run `build_zip()` on a `_ExportWorker(QThread)`. Show a brief toast "Exporting..." and replace with "Exported to /path/to/file.zip" on success.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `audioaddict_listen_key` is the only credential-like key in the settings table | Credential exclusion / SYNC-02 | Low: confirmed by querying the live DB; schema is additive so new keys could appear in future phases, but none are planned before phase 42 |
| A2 | `album_fallback_path` is not exported (only `station_art_path`) | Schema design | Low: album_fallback is downloaded cover art, not a persistent user asset; re-downloaded on playback. Could include it but adds ZIP bloat. |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-qt (offscreen) |
| Config file | `pytest.ini` or `pyproject.toml` (existing) |
| Quick run command | `pytest tests/test_settings_export.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SYNC-01 | `build_zip` produces ZIP with `settings.json` + `logos/` | unit | `pytest tests/test_settings_export.py::test_build_zip_structure -x` | Wave 0 |
| SYNC-01 | `settings.json` contains all stations, streams, favorites, settings | unit | `pytest tests/test_settings_export.py::test_export_content_completeness -x` | Wave 0 |
| SYNC-02 | `audioaddict_listen_key` absent from exported `settings.json` | unit | `pytest tests/test_settings_export.py::test_credentials_excluded -x` | Wave 0 |
| SYNC-03 | `preview_import` returns correct add/replace/skip counts | unit | `pytest tests/test_settings_export.py::test_preview_merge -x` | Wave 0 |
| SYNC-03 | `commit_import` merge mode adds new + replaces matched | unit | `pytest tests/test_settings_export.py::test_commit_merge -x` | Wave 0 |
| SYNC-03 | `commit_import` replace_all wipes and restores | unit | `pytest tests/test_settings_export.py::test_commit_replace_all -x` | Wave 0 |
| SYNC-04 | Summary dialog shows correct counts from preview | unit (Qt) | `pytest tests/test_settings_import_dialog.py -x` | Wave 0 |
| SYNC-04 | All-or-nothing: DB unchanged if user cancels | unit | `pytest tests/test_settings_export.py::test_cancel_no_change -x` | Wave 0 |
| SYNC-05 | Menu actions enabled and connected | unit (Qt) | `pytest tests/test_ui_qt_scaffold.py -x` (extend existing) | ✅ exists |

### Sampling Rate

- **Per task commit:** `pytest tests/test_settings_export.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_settings_export.py` — covers SYNC-01 through SYNC-04 (pure logic tests, no Qt needed)
- [ ] `tests/test_settings_import_dialog.py` — covers SYNC-04 dialog rendering (pytest-qt offscreen)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Validate ZIP structure + JSON schema version before any DB write; reject with toast |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed ZIP with path traversal (`logos/../../etc/passwd`) | Tampering | `zipfile` members: check each `name` doesn't start with `/` or contain `..` before extraction |
| ZIP bomb (decompresses to GB) | Denial of Service | Limit extracted size: check `file_size` in `ZipInfo` before extracting; reject if total > reasonable threshold (e.g., 500 MB) |
| Injected SQL via station name in JSON | Tampering | Repo uses parameterized queries throughout — no risk |
| Credential leak via settings | Information Disclosure | Exclude `audioaddict_listen_key` from export by key blocklist |

**ZIP path traversal check (required):**
```python
for member in zf.infolist():
    if member.filename.startswith('/') or '..' in member.filename:
        raise ValueError(f"Unsafe path in archive: {member.filename}")
```

---

## Environment Availability

Step 2.6: SKIPPED — no external dependencies. All required libraries (`zipfile`, `json`, `re`, `unicodedata`, `PySide6`, `platformdirs`) are already installed and verified as part of the existing project stack.

---

## Sources

### Primary (HIGH confidence)

- Codebase: `musicstreamer/repo.py` — all data accessors verified
- Codebase: `musicstreamer/paths.py` — path conventions verified
- Codebase: `musicstreamer/ui_qt/import_dialog.py` — QThread worker pattern verified
- Codebase: `musicstreamer/ui_qt/cookie_import_dialog.py` — QFileDialog pattern verified
- Codebase: `musicstreamer/ui_qt/toast.py` — ToastOverlay API verified
- Live DB: `musicstreamer.sqlite3` — settings keys + station art paths verified
- Live test: Python stdlib `zipfile` — ZIP creation, reading, BadZipFile verified
- Live test: `QStandardPaths.DocumentsLocation` — resolves `/home/kcreasey/Documents`

### Secondary (MEDIUM confidence)

None needed — all claims verified against codebase or live tests.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all verified against installed environment
- Architecture: HIGH — follows established QThread + Repo patterns exactly
- Pitfalls: HIGH — derived from codebase inspection of actual data structures
- Security: MEDIUM — ZIP path traversal and bomb mitigations are standard; not verified against specific attacks

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (stable stdlib + Qt stack)
