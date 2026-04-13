# Phase 39: Core Dialogs - Research

**Researched:** 2026-04-13
**Domain:** PySide6 QDialog patterns, Qt worker-thread signal wiring, station CRUD UI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**EditStation Dialog**
- D-01: Single `EditStationDialog(QDialog)` — no sub-dialog. Fields: name, URL, editable provider combo, tag chips (FlowLayout), ICY disable toggle, stream table, delete button.
- D-02: `QComboBox(setEditable=True)` populated from `repo.list_providers()`. Typed value takes precedence over dropdown selection.
- D-03: Tag editor reuses Phase 38 `FlowLayout`. Existing tags shown as toggleable chips; `QLineEdit` + "Add" button for new tags inline.
- D-04: Multi-stream management via `QTableWidget`. Columns: URL, Quality (QComboBox hi/med/low/custom), Codec, Position. Buttons: Add, Remove, Move Up, Move Down.
- D-05: Delete button at bottom, disabled when `player.current_station` matches this station. Confirmation prompt before delete.
- D-06: ICY toggle is `QCheckBox("Disable ICY metadata")` → `station.icy_disabled`.
- D-07: YouTube thumbnail auto-fetch on URL paste (daemon thread + signal). AA logo auto-fetch on URL paste using `_normalize_aa_image_url` pattern.
- D-08: Edit button on now-playing panel at line 174 marker. `QToolButton` with `document-edit-symbolic` icon, enabled only when playing.

**Discovery Dialog**
- D-09: Search bar (QLineEdit + tag/country QComboBoxes + Search button). Results in `QTableView`.
- D-10: Tag and country combos populated on dialog open via daemon threads (non-blocking).
- D-11: Per-row play/stop toggle. Uses main Player instance with temporary station object (not saved).
- D-12: Per-row "Save" button. Saves via `repo.insert_station()`. Uses `url_resolved` over `url`. Button disables after save. Toast: "Saved [name] to library".
- D-13: Search on daemon thread with loading indicator.

**Import Dialog**
- D-14: `ImportDialog(QDialog)` with `QTabWidget` — "YouTube" and "AudioAddict" tabs.
- D-15: YouTube tab: URL + Scan → checkable `QListWidget` → Import via `yt_import.import_stations()`.
- D-16: AudioAddict tab: API key + quality `QComboBox` → Import via `aa_import.fetch_channels_multi()` + `import_stations_multi()`.
- D-17: Inline `QProgressBar` + status label per tab. YouTube: determinate scan then determinate import. AA: indeterminate fetch, determinate import. Inputs disabled during active import.
- D-18: Error handling: invalid API key → inline error label; network errors → toast; empty playlist → inline message.

**Stream Picker**
- D-19: `QComboBox` on now-playing controls row. Shows current stream label/quality.
- D-20: Hidden when station has only 1 stream.
- D-21: Selection change triggers `player.play(station, stream=selected_stream)`.
- D-22: `player.failover` signal sync via `blockSignals(True)` during programmatic update.

### Claude's Discretion
- Exact dialog dimensions and minimum sizes
- QTableWidget column widths and resize policies
- Whether Discovery results table is read-only or selectable
- Stream table styling (alternating row colors, header style)
- Edit dialog field ordering within the form layout
- Whether to show station art preview in the edit dialog
- Loading indicator style (spinner widget vs indeterminate progress bar)

### Deferred Ideas (OUT OF SCOPE)
None.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-05 | `EditStationDialog` — provider picker, wrapping tag chip FlowLayout, multi-stream management (reorder, quality presets hi/med/low/custom), ICY disable toggle, delete with playing guard | D-01..D-08; `repo.update_station()`, `repo.list_streams()`, `repo.insert_stream()`, `repo.update_stream()`, `repo.reorder_streams()` all verified in repo.py |
| UI-06 | `DiscoveryDialog` — Radio-Browser.info search, tag/country filters, per-row preview play, save-to-library | D-09..D-13; `radio_browser.search_stations()`, `fetch_tags()`, `fetch_countries()` verified; `url_resolved` preference confirmed |
| UI-07 | `ImportDialog` — YouTube playlist tab (scan → checklist → import with progress) and AudioAddict tab (API key, quality selector, network import, logo download) | D-14..D-18; `yt_import.scan_playlist()`, `import_stations()`, `aa_import.fetch_channels_multi()`, `import_stations_multi()` all verified |
| UI-13 | Stream picker on now-playing panel — manual stream selection dropdown; reflects round-robin and quality fallback state | D-19..D-22; `player.play_stream()` verified; `player.failover` signal signature confirmed as `Signal(object)` |
</phase_requirements>

---

## Summary

Phase 39 is pure UI work — all four backend modules (`radio_browser.py`, `yt_import.py`, `aa_import.py`, `repo.py`) are stable and proven in v1.5. The task is building four PySide6 dialog/widget components that wrap those backends with correct Qt threading discipline.

The established Phase 35/36/37 patterns (daemon `QThread` + `Signal` queued connection, bound-method slots, `QIcon.fromTheme` with fallback) fully cover every threading need here. No new patterns are required. The main risks are (1) widget-lifetime bugs in dialog workers, (2) stale `QComboBox` signals when programmatically syncing the stream picker, and (3) tags stored as comma-separated strings (no separate tags table) requiring split/join handling in the tag chip editor.

**Primary recommendation:** Implement each dialog as a standalone `QDialog` subclass in `musicstreamer/ui_qt/`, follow the Phase 35 `Signal` + queued connection pattern for all blocking I/O, and wire dialogs into `MainWindow` via menu/button actions.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | project-established | QDialog, QTableWidget, QComboBox, QProgressBar, QListWidget, QTabWidget | Already in use throughout Phase 35–38 |
| Python stdlib threading | — | `QThread` subclass or `threading.Thread` (daemon=True) for blocking I/O | Established pattern in Phase 35 |

No new library installs required for this phase.

### Established Patterns (in-repo)
| Asset | Location | Use in Phase 39 |
|-------|----------|-----------------|
| `FlowLayout` | `ui_qt/flow_layout.py` | Tag chip editor in EditStationDialog |
| `ToastOverlay` | `ui_qt/toast.py` | Save/delete/import feedback |
| `icons_rc` | `ui_qt/icons_rc.py` | Must re-run `pyside6-rcc` after adding `document-edit-symbolic.svg` |
| `repo.Repo` | `musicstreamer/repo.py` | All DB ops — `update_station`, `list_streams`, `insert_stream`, `update_stream`, `reorder_streams`, `list_providers` |

---

## Architecture Patterns

### Recommended Project Structure
```
musicstreamer/ui_qt/
├── edit_station_dialog.py    # UI-05 — EditStationDialog
├── discovery_dialog.py       # UI-06 — DiscoveryDialog
├── import_dialog.py          # UI-07 — ImportDialog
├── now_playing_panel.py      # UI-13 — add edit button + stream picker at line 174
└── icons/
    └── document-edit-symbolic.svg   # new icon (D-08)
```

`MainWindow` wires dialog launch from hamburger menu (Phase 40 wires the actual menu; Phase 39 can expose launch methods called by the edit button and any stub menu entries).

### Pattern 1: Daemon Thread + Queued Signal (all blocking I/O)

Established in Phase 35, used throughout Phase 37. Every dialog that calls a blocking backend (radio_browser, yt_import, aa_import) follows this pattern:

```python
# Source: Phase 35 patterns, verified in now_playing_panel.py
class _SearchWorker(QThread):
    finished = Signal(list)   # emits results on main thread
    error = Signal(str)

    def __init__(self, query, tag, country, parent=None):
        super().__init__(parent)
        self._query = query
        self._tag = tag
        self._country = country

    def run(self):
        try:
            results = radio_browser.search_stations(self._query, self._tag, self._country)
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))

class DiscoveryDialog(QDialog):
    def _start_search(self):
        self._worker = _SearchWorker(name, tag, country, parent=self)
        self._worker.finished.connect(self._on_results, Qt.QueuedConnection)
        self._worker.error.connect(self._on_error, Qt.QueuedConnection)
        self._worker.start()
```

**Critical:** Parent the worker to the dialog (`parent=self`) so Qt owns its lifetime. Never access widgets from inside `run()`.

### Pattern 2: blockSignals for Programmatic QComboBox Updates

Required for stream picker sync (D-22):

```python
# Source: established Qt pattern, verified against D-22 requirement
def _sync_stream_picker(self, active_stream):
    self.stream_combo.blockSignals(True)
    for i in range(self.stream_combo.count()):
        if self.stream_combo.itemData(i) == active_stream.id:
            self.stream_combo.setCurrentIndex(i)
            break
    self.stream_combo.blockSignals(False)
```

### Pattern 3: Tags as Comma-Separated String

Tags are stored as `stations.tags TEXT` (comma-separated). The EditStation dialog must split on load and rejoin on save:

```python
# Source: verified in repo.py schema (line 27) and Station dataclass
existing_tags = [t.strip() for t in station.tags.split(",") if t.strip()]
# ... chip UI ...
new_tags_str = ",".join(selected_tags)
repo.update_station(station_id, name, provider_id, new_tags_str, ...)
```

No separate tags table exists — do not attempt to query one.

### Pattern 4: provider_id Resolution for EditStation

`update_station()` takes `provider_id: Optional[int]`, not a name string. The dialog must call `repo.ensure_provider(name)` to get or create the provider and pass the integer ID:

```python
# Source: verified in repo.py lines 280–300, 397–407
provider_name = self.provider_combo.currentText().strip()
provider_id = self._repo.ensure_provider(provider_name) if provider_name else None
self._repo.update_station(station_id, name, provider_id, tags_str, art_path, fallback_path, icy_disabled)
```

### Pattern 5: url_resolved Preference for Radio-Browser

Radio-Browser returns both `url` and `url_resolved`. v1.5 key decision: prefer `url_resolved`:

```python
# Source: v1.5 key decision documented in CONTEXT.md D-12
stream_url = result.get("url_resolved") or result.get("url", "")
```

### Anti-Patterns to Avoid

- **Widget access in `QThread.run()`:** Never touch any QWidget from inside a worker thread. Emit signals only.
- **Self-capturing lambdas as slots:** Use bound methods per QA-05. In dialogs, define `_on_result(self, data)` methods, not `lambda d: self.foo(d)`.
- **`WA_DeleteOnClose` on reused dialogs:** If dialogs are opened multiple times, do NOT set `WA_DeleteOnClose` unless a fresh instance is created each time. Simpler: create fresh dialog instance on each launch (standard pattern for modal dialogs).
- **Forgetting `blockSignals`:** Stream picker `currentIndexChanged` fires during programmatic updates. Always `blockSignals(True/False)` around programmatic `setCurrentIndex`.
- **Assuming a tags table:** Tags are a comma-separated string in `stations.tags`. No `tags` table exists.
- **`player.play()` vs `player.play_stream()`:** For stream picker manual selection (D-21), use `player.play_stream(selected_stream)` to bypass the failover queue, not `player.play(station)`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Wrapping chip layout | Custom layout manager | `FlowLayout` (ui_qt/flow_layout.py) | Already implemented and tested in Phase 38 |
| Save/error feedback | Custom notification widget | `ToastOverlay.show_toast()` | Already implemented in Phase 37 |
| Radio-Browser API | Custom HTTP client | `radio_browser.search_stations/fetch_tags/fetch_countries` | Already implemented and tested |
| YouTube playlist scan | yt-dlp subprocess | `yt_import.scan_playlist()` | PORT-09 compliance; library API only |
| AA channel fetch | Custom AA API client | `aa_import.fetch_channels_multi()` | Already implemented; handles multi-quality + logo download |
| Thread-safe DB in workers | Shared repo connection | `Repo(db_connect())` per thread | SQLite thread-safety requirement; verified pattern in `aa_import.py` line 225 |
| Progress reporting | Polling | `on_progress` callback + `Signal.emit` | Established pattern in `aa_import.import_stations_multi` |

---

## Common Pitfalls

### Pitfall 1: QThread Parent Lifetime
**What goes wrong:** Worker `QThread` is stored as a local variable. Python GC destroys it mid-execution, causing `RuntimeError: Internal C++ object already deleted`.
**Why it happens:** PySide6 needs Python to hold a reference; if no parent is set and no instance variable holds it, GC fires.
**How to avoid:** Always parent the worker to the dialog (`_SearchWorker(..., parent=self)`) or store it as `self._worker`. Both patterns work; parent is simpler.
**Warning signs:** Intermittent crashes that only happen on fast machines.

### Pitfall 2: QComboBox Signal Re-entrance in Stream Picker
**What goes wrong:** `failover` signal fires → update stream picker → `currentIndexChanged` → triggers `player.play_stream()` → infinite loop or double play.
**Why it happens:** `setCurrentIndex` emits `currentIndexChanged` even during programmatic updates.
**How to avoid:** Wrap all programmatic updates with `blockSignals(True)` / `blockSignals(False)` (D-22).

### Pitfall 3: Import Worker Thread DB Connection
**What goes wrong:** SQLite raises `ProgrammingError: SQLite objects created in a thread can only be used in that same thread`.
**Why it happens:** `aa_import.import_stations_multi` creates a `Repo(db_connect())` inside each worker. If the caller passes the main-thread `Repo`, it fails.
**How to avoid:** The import backends already create their own thread-local `Repo(db_connect())` for logo download (verified in `aa_import.py` line 225). The main import loop in `import_stations_multi` uses the `repo` parameter — this must be called from a worker thread with its own `Repo(db_connect())` instance. Do NOT pass `self._repo` directly to a worker; instantiate a fresh `Repo(db_connect())` inside `QThread.run()`.

### Pitfall 4: QProgressBar Indeterminate Mode
**What goes wrong:** `setMaximum(0)` is needed for indeterminate (marquee) mode; `setMinimum(0)` alone is not enough.
**How to set:** `progress_bar.setRange(0, 0)` for indeterminate; `progress_bar.setRange(0, total)` for determinate.

### Pitfall 5: EditStation Delete Guard
**What goes wrong:** `player.current_station` is not a public attribute on the Player — the player tracks `_current_station_name` (str), not a Station object reference.
**Correct check:** Compare `player._current_station_name == station.name` or expose a public property. Check `player.py` line 146 — `_current_station_name` is set in `play()`. Prefer: check `self._player._current_station_name == self._station.name` in `EditStationDialog` since `current_station` is not a public API.

### Pitfall 6: icons_rc Must Be Regenerated
**What goes wrong:** New SVG added to `ui_qt/icons/` but `icons_rc.py` not regenerated. `QIcon(":/icons/document-edit-symbolic.svg")` silently returns a null icon.
**How to avoid:** Run `pyside6-rcc musicstreamer/ui_qt/icons.qrc -o musicstreamer/ui_qt/icons_rc.py` after adding any new SVG.

---

## Code Examples

### EditStation — Opening from NowPlayingPanel (line 174 insertion point)

```python
# Source: CONTEXT.md D-08, verified now_playing_panel.py line 174
# Insert BEFORE controls.addWidget(self.stop_btn):
self.edit_btn = QToolButton(self)
self.edit_btn.setIconSize(QSize(24, 24))
self.edit_btn.setFixedSize(36, 36)
self.edit_btn.setIcon(
    QIcon.fromTheme("document-edit-symbolic", QIcon(":/icons/document-edit-symbolic.svg"))
)
self.edit_btn.setToolTip("Edit station")
self.edit_btn.setEnabled(False)
self.edit_btn.clicked.connect(self._on_edit_clicked)
controls.addWidget(self.edit_btn)
# Then the existing: controls.addWidget(self.stop_btn)
```

Enable/disable in `on_playing_state_changed`:
```python
self.edit_btn.setEnabled(is_playing and self._station is not None)
```

### Stream Picker — Populating

```python
# Source: CONTEXT.md D-19..D-22
def populate_stream_picker(self, station: Station) -> None:
    streams = self._repo.list_streams(station.id)
    self.stream_combo.blockSignals(True)
    self.stream_combo.clear()
    for s in streams:
        label = f"{s.quality} — {s.codec}" if s.codec else s.quality or s.label or "stream"
        self.stream_combo.addItem(label, userData=s.id)
    self.stream_combo.blockSignals(False)
    self.stream_combo.setVisible(len(streams) > 1)
```

### Discovery Dialog — Saving a Row

```python
# Source: CONTEXT.md D-12; url_resolved preference from v1.5 key decisions
def _save_row(self, result: dict) -> None:
    stream_url = result.get("url_resolved") or result.get("url", "")
    if not stream_url:
        return
    self._repo.insert_station(
        name=result.get("name", "Unknown"),
        url=stream_url,
        provider_name="Radio-Browser",
        tags=result.get("tags", ""),
    )
    self._main_window.show_toast(f"Saved {result['name']!r} to library")
```

### Worker Thread Pattern (reusable template)

```python
# Source: Phase 35 patterns; verified in now_playing_panel._fetch_cover_art_async
class _Worker(QThread):
    result_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, fn, *args, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._args = args

    def run(self):
        try:
            self.result_ready.emit(self._fn(*self._args))
        except Exception as exc:
            self.error_occurred.emit(str(exc))
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-qt |
| Config file | `pytest.ini` (or `pyproject.toml [tool.pytest]`) |
| Quick run command | `python -m pytest tests/test_edit_station_dialog.py tests/test_discovery_dialog.py tests/test_import_dialog_qt.py tests/test_stream_picker.py -x` |
| Full suite command | `python -m pytest --ignore=tests/test_yt_import_library.py` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-05 | EditStationDialog opens, fields populated, save calls `update_station` | unit (pytest-qt) | `pytest tests/test_edit_station_dialog.py -x` | ❌ Wave 0 |
| UI-05 | Delete button disabled when station playing | unit | same file | ❌ Wave 0 |
| UI-05 | Tag chip add/remove updates tags string | unit | same file | ❌ Wave 0 |
| UI-05 | Stream table add/remove/reorder calls repo methods | unit | same file | ❌ Wave 0 |
| UI-06 | DiscoveryDialog search invokes radio_browser (mocked) | unit | `pytest tests/test_discovery_dialog.py -x` | ❌ Wave 0 |
| UI-06 | Save row calls `insert_station` with `url_resolved` | unit | same file | ❌ Wave 0 |
| UI-07 | ImportDialog YouTube tab scan → checklist → import | unit | `pytest tests/test_import_dialog_qt.py -x` | ❌ Wave 0 |
| UI-07 | ImportDialog AA tab error label on `invalid_key` | unit | same file | ❌ Wave 0 |
| UI-13 | Stream picker hidden for single-stream station | unit | `pytest tests/test_stream_picker.py -x` | ❌ Wave 0 |
| UI-13 | Stream picker blockSignals during failover sync | unit | same file | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_edit_station_dialog.py tests/test_discovery_dialog.py tests/test_import_dialog_qt.py tests/test_stream_picker.py -x`
- **Per wave merge:** `python -m pytest --ignore=tests/test_yt_import_library.py`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_edit_station_dialog.py` — covers UI-05
- [ ] `tests/test_discovery_dialog.py` — covers UI-06
- [ ] `tests/test_import_dialog_qt.py` — covers UI-07 (separate from existing `tests/test_import_dialog.py` which tests backend only)
- [ ] `tests/test_stream_picker.py` — covers UI-13

Note: `tests/test_import_dialog.py` already exists but tests the backend (`yt_import` module) only — not the Qt dialog widget. New `test_import_dialog_qt.py` covers the widget layer.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | AudioAddict API key is opaque string — passed directly to URL; no SQL injection vector since it goes through `urllib.request.urlopen`, not a DB query. YouTube URL validated by `is_yt_playlist_url()` before scan. |
| V6 Cryptography | no | No crypto operations |
| V2 Authentication | no | API key is stored in UI only (not persisted in this phase) |

ICY title in EditStation dialog: already established `Qt.PlainText` pattern from now_playing_panel prevents rich-text injection — apply same to any labels displaying untrusted station metadata.

---

## Key Repo API Reference

Verified signatures from `musicstreamer/repo.py`:

```python
# [VERIFIED: repo.py lines 156-200]
repo.list_providers() -> List[Provider]
repo.list_streams(station_id: int) -> List[StationStream]
repo.insert_stream(station_id, url, label="", quality="", position=1, stream_type="", codec="") -> None
repo.update_stream(stream_id, url, label, quality, position, stream_type, codec) -> None
repo.reorder_streams(station_id, ordered_ids: List[int]) -> None
repo.update_station(station_id, name, provider_id, tags, station_art_path, album_fallback_path, icy_disabled=False) -> None
repo.delete_station(station_id) -> None
repo.insert_station(name, url, provider_name, tags) -> int  # returns station_id
repo.station_exists_by_url(url) -> bool
repo.ensure_provider(name) -> int  # get or create, returns provider_id
```

**Tags:** `Station.tags` is a comma-separated string (e.g., `"jazz,electronic"`). No separate tags table.

**Player public API (relevant):**
```python
# [VERIFIED: player.py lines 140-179]
player.play(station: Station, preferred_quality: str = "", ...) -> None
player.play_stream(stream: StationStream) -> None  # bypasses failover queue
player._current_station_name: str  # no public current_station property
player.failover: Signal(object)  # emits StationStream | None
```

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — all backends are in-repo Python modules already installed; no new CLI tools required).

---

## Open Questions

1. **`player.current_station` is not public**
   - What we know: `player._current_station_name` (str) is set at `play()`. No `current_station: Station` property exists.
   - What's unclear: D-05 says "check `player.current_station`" but that property doesn't exist.
   - Recommendation: Use `self._player._current_station_name == self._station.name` in `EditStationDialog._check_delete_guard()`. Alternatively add a `current_station_name` property to Player in the same plan.

2. **`player.play()` signature for stream picker (D-21)**
   - What we know: D-21 says `player.play(station, stream=selected_stream)` but the actual signature is `player.play(station, preferred_quality="", ...)` — no `stream=` kwarg. `player.play_stream(stream)` exists and bypasses the queue.
   - Recommendation: Use `player.play_stream(selected_stream)` for stream picker selection (D-21). This matches the intent (bypass failover queue, play exactly this stream).

---

## Sources

### Primary (HIGH confidence)
- `musicstreamer/repo.py` — all repo method signatures verified by direct read
- `musicstreamer/player.py` — `play()`, `play_stream()`, `failover` signal verified
- `musicstreamer/radio_browser.py` — all three functions verified
- `musicstreamer/yt_import.py` — `scan_playlist()`, `import_stations()` verified
- `musicstreamer/aa_import.py` — `fetch_channels_multi()`, `import_stations_multi()` verified
- `musicstreamer/ui_qt/now_playing_panel.py` — line 174 insertion point verified
- `musicstreamer/ui_qt/flow_layout.py` — `FlowLayout` API verified
- `musicstreamer/ui_qt/toast.py` — `ToastOverlay.show_toast()` verified
- `musicstreamer/models.py` — `Station`, `StationStream`, `Provider` dataclasses verified
- `.planning/phases/39-core-dialogs/39-CONTEXT.md` — all locked decisions

### Tertiary (LOW confidence — not verified this session)
- QProgressBar `setRange(0,0)` for indeterminate mode — [ASSUMED] standard Qt behavior

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `QProgressBar.setRange(0, 0)` produces indeterminate (marquee) mode | Common Pitfalls §4 | Minor — easy to fix at implementation; indeterminate look is a UX nicety |

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are project-established, no new installs
- Architecture: HIGH — patterns directly verified from existing codebase
- Pitfalls: HIGH — most derived from direct code inspection; A1 is low-risk assumption
- Repo API: HIGH — all signatures read from source

**Research date:** 2026-04-13
**Valid until:** 2026-05-13 (stable codebase; no fast-moving dependencies)
