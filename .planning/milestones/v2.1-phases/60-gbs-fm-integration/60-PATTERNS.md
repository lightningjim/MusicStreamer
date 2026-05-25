# Phase 60: GBS.FM Integration — Pattern Map

**Mapped:** 2026-05-04
**Files analyzed:** 14 (8 source/UI + 6 test/fixture/script)
**Analogs found:** 13 / 14 (one fixture-bundle has no source analog by design)

All analog file paths below are absolute. Line numbers reflect the analog
file's current state (verified by reading each file in this pass).

---

## File Classification

### Source files (NEW)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `musicstreamer/gbs_api.py` | service (HTTP client + import orchestrator + HTML parsers) | request-response (urllib) + transform (HTML/JSON parse) + CRUD (Repo writes) | `musicstreamer/aa_import.py` | exact (multi-quality import + module-scope tier constants + ThreadPoolExecutor logo download) |
| `musicstreamer/ui_qt/gbs_search_dialog.py` | component (QDialog) | request-response + CRUD-ish (submits to remote) | `musicstreamer/ui_qt/discovery_dialog.py` | exact (search-box + results-table + per-row action button + worker QThread + bound-method connections) |

### Source files (MODIFIED)

| Modified File | Role | Data Flow | Closest Analog (in same file) | Match Quality |
|---------------|------|-----------|-------------------------------|---------------|
| `musicstreamer/ui_qt/main_window.py` | controller (menu wiring + dialog launchers) | event-driven (QAction triggered) | `_open_discovery_dialog` (lines 668-672) + `_open_import_dialog` (lines 674-678) | exact |
| `musicstreamer/ui_qt/accounts_dialog.py` | component (provider QGroupBox) | event-driven (Connect/Disconnect button) | YouTube `_youtube_box` (lines 91-103) + Twitch group (lines 104-115) | exact (third sibling group, identical shape) |
| `musicstreamer/ui_qt/now_playing_panel.py` | component (active-playlist widget + vote buttons) | event-driven (QTimer poll + button click) + worker-thread API call | Phase 64 `_sibling_label` (lines 183-189, 646-688) hide-when-empty + star_btn (lines 261-271, 491-519) optimistic action + cover_art adapter (lines 575-601) worker-pattern | role-match (precedents are a hide-when-empty optional widget + an off-thread mutation, not a polling widget — but both shapes apply directly) |
| `musicstreamer/paths.py` | utility (path accessor) | static helper | `cookies_path` (line 46) + `twitch_token_path` (line 50) | exact (one-liner mirror) |
| `musicstreamer/ui_qt/cookie_import_dialog.py` | component (QDialog tabs) | event-driven (file pick / paste / subprocess) | the dialog itself — needs parameterization for gbs.fm OR a sibling `GbsCookieImportDialog`; planner picks. Currently hard-codes YouTube. | self-as-analog (refactor target) |
| `musicstreamer/oauth_helper.py` | controller (subprocess) | event-driven (QWebEngineCookieStore.cookieAdded) | `_TwitchCookieWindow` (lines 108-...) — `--mode twitch` cookie-harvest pattern | role-match (only if planner adds the optional `--mode gbs` polish — see RESEARCH §Open Questions Q3 → not required for v1) |

### Test / fixture / script files (NEW)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `tests/test_gbs_api.py` | test (unit + integration) | mock-driven | `tests/test_aa_import.py` (urlopen-patch + MagicMock context-manager helper at lines 19-30) + `tests/test_radio_browser.py` (pure-urllib mock) | exact |
| `tests/ui_qt/test_now_playing_panel_gbs.py` | test (pytest-qt) | UI assertions on widget state | `tests/test_now_playing_panel.py` (qtbot fixture at line 166) | exact |
| `tests/ui_qt/test_gbs_search_dialog.py` | test (pytest-qt) | UI assertions on dialog flow | `tests/test_discovery_dialog.py` (search-flow tests) | exact |
| `tests/fixtures/gbs/*.{json,html,txt}` | fixture (captured payloads) | static data | none — Phase 60 is the first GBS fixture set | no analog (by design) |
| `scripts/gbs_capture_fixtures.sh` | utility (bash + curl) | I/O (writes to `tests/fixtures/gbs/`) | none — first fixture-capture script in repo | no analog (by design — short script, planner writes from scratch) |
| `tests/conftest.py` (extension) | fixture | shared mocks | existing autouse `_stub_bus_bridge` at lines 20-30 | role-match (extends, doesn't replace) |
| `tests/test_stream_ordering.py` (extension) | regression test | pure-function | existing tests in same file | exact (add one test function for FLAC bitrate sentinel) |

---

## Pattern Assignments

### `musicstreamer/gbs_api.py` (service, request-response + transform + CRUD)

**Analog:** `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/aa_import.py`

**Module docstring + imports pattern** (analog lines 1-20):
```python
"""AudioAddict network import backend.

Public API:
  fetch_channels(listen_key, quality) -> list[dict]
  import_stations(channels, repo, on_progress=None, on_logo_progress=None) -> (imported, skipped)
"""

import json
import logging
import os
import re
import tempfile
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from musicstreamer.assets import copy_asset_for_station
from musicstreamer.repo import db_connect, Repo

_log = logging.getLogger(__name__)
```
**Apply to gbs_api.py:** Same docstring shape + same import block. Phase 60 adds
`http.cookiejar`, `urllib.parse`, `from html.parser import HTMLParser`, and
`base64` (for Django messages cookie decode). `from musicstreamer import paths`
for `paths.gbs_cookies_path()`.

**Module-scope constants pattern** (analog lines 88-111):
```python
NETWORKS = [
    {"slug": "di",             "domain": "listen.di.fm",              "name": "DI.fm"},
    {"slug": "radiotunes",     "domain": "listen.radiotunes.com",     "name": "RadioTunes"},
    ...
]

QUALITY_TIERS = {
    "hi":  "premium_high",
    "med": "premium",
    "low": "premium_medium",
}

# IN-02: module-scope constants for AA quality tier metadata
_POSITION_MAP = {"hi": 1, "med": 2, "low": 3}
_BITRATE_MAP = {"hi": 320, "med": 128, "low": 64}
_CODEC_MAP = {"hi": "MP3", "med": "AAC", "low": "AAC"}
```
**Apply to gbs_api.py:** Replace with `GBS_BASE`, `GBS_STATION_METADATA`,
`_GBS_QUALITY_TIERS` per RESEARCH §Capability 1 (six rows: 96/128/192/256/320 MP3 +
flac with `bitrate_kbps=1411` sentinel). The sentinel value choice is documented in
RESEARCH Pitfall 0 / Open Questions Q1; planner re-reads `stream_ordering.py:43-64`
(see _Shared Patterns / Stream-ordering FLAC sentinel_ below) before locking.

**Multi-quality output shape pattern** (analog lines 187-199 — THE canonical shape):
```python
# gap-06 fix for UAT gap 2: emit one stream dict per PLS File= entry
# (primary + fallback). Position preserves PLS order within the tier
# (tier_base * 10 + pls_index), so primary sorts before fallback when
# order_streams uses position as the tiebreaker.
tier_base = _POSITION_MAP[quality]
for pls_index, url in enumerate(stream_urls, start=1):
    channels_by_net_key[key]["streams"].append({
        "url": url,
        "quality": quality,
        "position": tier_base * 10 + pls_index,
        "codec": _CODEC_MAP[quality],
        "bitrate_kbps": _BITRATE_MAP[quality],
    })
```
**Apply to gbs_api.py:** `fetch_streams() -> list[dict]` returns
`[{url, quality, position, codec, bitrate_kbps}]` exactly — no enclosing
channel-list wrapper because GBS.FM is one station. The list is static
(see RESEARCH §Capability 1 — no HTTP needed). Phase 60 simplifies to
`return list(_GBS_QUALITY_TIERS)`.

**Idempotent import orchestrator pattern** (analog lines 207-309):
```python
def import_stations_multi(channels, repo, on_progress=None, on_logo_progress=None) -> tuple[int, int]:
    """Import multi-quality AA channels. Creates one station per channel with multiple streams.
    ...
    """
    imported = 0
    skipped = 0
    logo_targets = []

    for ch in channels:
        if not ch.get("streams"):
            skipped += 1
            ...
            continue
        any_exists = any(repo.station_exists_by_url(s["url"]) for s in ch["streams"])
        if any_exists:
            skipped += 1
        else:
            first_url = ch["streams"][0]["url"]
            station_id = repo.insert_station(
                name=ch["title"], url=first_url,
                provider_name=ch["provider"], tags="",
            )
            # insert_station already created a stream for first_url at position=1
            # Update the auto-created stream with quality/codec metadata, then insert remaining
            for s in ch["streams"]:
                if s["url"] == first_url:
                    streams = repo.list_streams(station_id)
                    if streams:
                        repo.update_stream(
                            streams[0].id, s["url"], s.get("label", ""),
                            s["quality"], s["position"],
                            "shoutcast", s.get("codec", ""),
                            bitrate_kbps=s.get("bitrate_kbps", 0),
                        )
                else:
                    repo.insert_stream(
                        station_id, s["url"], label="",
                        quality=s["quality"], position=s["position"],
                        stream_type="shoutcast", codec=s.get("codec", ""),
                        bitrate_kbps=s.get("bitrate_kbps", 0),
                    )
            imported += 1
            ...
```
**Apply to gbs_api.py:** `import_station(repo, on_progress=None) -> tuple[int, int]`
returns `(inserted, updated)`. Single station; no outer for-channel loop. The
"already exists" branch refreshes streams in place (D-02a idempotent re-fetch) —
truncate-and-reset semantics (RESEARCH Pitfall 4 path a). `provider="GBS.FM"`
(D-02d). The "first URL == auto-created stream → update; rest → insert" pattern
at analog lines 246-262 transfers verbatim.

**Logo download with `copy_asset_for_station` pattern** (analog lines 275-293):
```python
def _download_logo(station_id: int, image_url: str) -> None:
    try:
        with urllib.request.urlopen(image_url, timeout=15) as resp:
            data = resp.read()
        suffix = os.path.splitext(image_url.split("?")[0])[1] or ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            art_path = copy_asset_for_station(station_id, tmp_path, "station_art")
            thread_repo = Repo(db_connect())
            thread_repo.update_station_art(station_id, art_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception:
        pass
```
**Apply to gbs_api.py:** Reuse verbatim with `image_url = "https://gbs.fm/images/logo_3.png"`.
No `ThreadPoolExecutor` needed (one logo, no parallelism win — D-discretion noted).
Inline-call directly from `import_station` after the Repo writes commit. The
`thread_repo = Repo(db_connect())` reconnect is irrelevant for the
single-station inline case; can use the passed-in `repo` directly when not in
a worker pool.

**Pure urllib + 10s/15s timeout pattern** (analog lines 124-128, 277):
```python
with urllib.request.urlopen(url, timeout=15) as resp:
    data = json.loads(resp.read())
```
**Apply to gbs_api.py:** 10s for read endpoints (`/ajax`, `/search`,
`/api/nowplaying`, `/api/metadata`); 15s for write endpoints (`/ajax?vote=`,
`/add/<id>`) per RESEARCH §Capability 4/6. No retry. RESEARCH Pitfall 7
explicitly forbids retry on GET-with-side-effects.

**Cookie jar + HTTPCookieProcessor pattern** (NEW for Phase 60 — RESEARCH Example 2):
```python
def _open_with_cookies(url: str, cookies: http.cookiejar.MozillaCookieJar, timeout: int = 10):
    handler = urllib.request.HTTPCookieProcessor(cookies)
    opener = urllib.request.build_opener(handler)
    req = urllib.request.Request(url, headers={"User-Agent": "MusicStreamer/2.0"})
    return opener.open(req, timeout=timeout)
```
**Apply to gbs_api.py:** Single helper used by every auth-gated endpoint.
Also see RESEARCH Pitfall 3: any 302 with `Location` starting with
`/accounts/login/` raises `GbsAuthExpiredError`. The intercepted-redirect
shape (used by `submit()`) is in RESEARCH Example 4.

**Typed exceptions pattern** (analog: `ValueError("invalid_key")` / `ValueError("no_channels")`
at lines 130-131, 144-145):
```python
raise ValueError("invalid_key")
...
raise ValueError("no_channels")
```
**Apply to gbs_api.py:** Mirror with named exception classes
(`GbsApiError`, `GbsAuthExpiredError`, optionally `GbsRateLimitError`). RESEARCH
Pitfall 3 + RESEARCH §Don't Hand-Roll explicitly recommends typed exceptions
over sentinel values for the auth-expired path.

---

### `musicstreamer/ui_qt/gbs_search_dialog.py` (component, request-response + CRUD-ish)

**Analog:** `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/discovery_dialog.py`

**Module docstring + class header pattern** (analog lines 1-17, 144-185):
```python
"""Phase 39-02: DiscoveryDialog — Radio-Browser.info search, preview, save.

Non-modal QDialog for UI-06. Key behaviors:
  D-09: Search bar with tag/country filter combos.
  ...

Security:
  T-39-04: QStandardItem cells are plain-text by default — no markup injection.
  T-39-06: limit=50 caps result set size.

Lifetime: all signal connections use bound methods (no self-capturing lambdas)
per QA-05. Filter workers are started lazily in showEvent to avoid emitting
signals onto unshown (or already-closed) widgets.
"""
...
class DiscoveryDialog(QDialog):
    station_saved = Signal()

    def __init__(
        self, player, repo, toast_callback: Callable[[str], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        ...
        self.setWindowTitle("Discover Stations")
        self.setMinimumSize(720, 520)
        self.setModal(False)
        self._build_ui()
```
**Apply to gbs_search_dialog.py:** Same constructor signature shape
(`repo, toast_callback, parent=None` — drop `player` since no preview-play per
CONTEXT.md "Phase 60's search dialog does NOT need preview play"). Keep the
QA-05 + T-39-04 lock. Class name `GBSSearchDialog`. `submission_completed`
signal mirrors `station_saved`.

**Worker QThread + signal pattern** (analog lines 95-123):
```python
class _SearchWorker(QThread):
    """Search Radio-Browser stations on a worker thread."""

    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self, name: str, tag: str, countrycode: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._tag = tag
        self._countrycode = countrycode

    def run(self) -> None:
        try:
            results = radio_browser.search_stations(
                name=self._name, tag=self._tag,
                countrycode=self._countrycode, limit=50,
            )
            self.finished.emit(results)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
```
**Apply to gbs_search_dialog.py:** Two workers — `_GbsSearchWorker(query, page, cookies)`
and `_GbsSubmitWorker(songid, cookies)`. Submit worker emits a Signal-payload
including the decoded `messages` cookie text per RESEARCH Example 4 / Pitfall 8.

**Search flow (button-driven, NOT debounced) pattern** (analog lines 312-326):
```python
def _start_search(self) -> None:
    name = self._search_edit.text().strip()
    ...
    self._search_btn.setEnabled(False)
    self._progress_bar.setRange(0, 0)
    self._progress_bar.setVisible(True)
    self._clear_table()

    self._search_worker = _SearchWorker(name, tag, countrycode, self)
    self._search_worker.finished.connect(self._on_search_finished)
    self._search_worker.error.connect(self._on_search_error)
    self._search_worker.start()
```
**Apply to gbs_search_dialog.py:** Same shape.
**RESEARCH Claude's Discretion** strongly recommends explicit-button (not
debounced live search) — gbs.fm `/search` is Django ORM with `LIKE` queries;
live debounce reads as a probe attack.

**Per-row action button factory pattern** (analog lines 388-396):
```python
def _make_play_slot(self, row_index: int):
    def _slot():
        self._on_play_row(row_index)
    return _slot

def _make_save_slot(self, row_index: int):
    def _slot():
        self._on_save_row(row_index)
    return _slot
```
**Apply to gbs_search_dialog.py:** `_make_submit_slot(row_index)` for each
result row's "Add!" button. Closure form is the QA-05-compliant alternative to
self-capturing lambdas.

**QStandardItem result-rendering pattern** (analog lines 343-377):
```python
for row_idx, result in enumerate(results):
    name_item = QStandardItem(result.get("name", ""))
    ...
    self._model.appendRow(...)

    save_btn = QPushButton("Save", self._results_table)
    save_btn.clicked.connect(self._make_save_slot(row_idx))
    self._save_buttons.append(save_btn)

    self._results_table.setIndexWidget(
        self._model.index(row_idx, _COL_SAVE), save_btn
    )
```
**Apply to gbs_search_dialog.py:** Same shape; columns are
`Artist | Title | Duration | Submit`. T-39-04 — `QStandardItem` is plain-text
by default, no Qt.RichText. Inline error label below the table (not toast)
for duplicate / token-quota errors per D-08d.

---

### `musicstreamer/ui_qt/main_window.py` modifications (controller, event-driven)

**Analog within file:** `_open_discovery_dialog` and `_open_import_dialog`
(lines 668-678).

**Menu wiring pattern** (lines 131-141):
```python
# Group 1: New + Discovery + Import (D-01, D-14, D-15)
act_new = self._menu.addAction("New Station")
act_new.triggered.connect(self._on_new_station_clicked)

act_discover = self._menu.addAction("Discover Stations")
act_discover.triggered.connect(self._open_discovery_dialog)

act_import = self._menu.addAction("Import Stations")
act_import.triggered.connect(self._open_import_dialog)

self._menu.addSeparator()
```
**Apply to main_window.py edit:** Insert two new actions in Group 1 BEFORE the
`addSeparator()` at line 141:
```python
act_gbs_add = self._menu.addAction("Add GBS.FM")
act_gbs_add.triggered.connect(self._on_gbs_add_clicked)

act_gbs_search = self._menu.addAction("Search GBS.FM…")
act_gbs_search.triggered.connect(self._open_gbs_search_dialog)
```
QA-05 bound-method connections. Ellipsis is U+2026 per project copywriting
convention (see line 325 `"Connecting…"`).

**Dialog launcher handler pattern** (lines 668-678):
```python
def _open_discovery_dialog(self) -> None:
    """D-14: Open DiscoveryDialog from hamburger menu."""
    dlg = DiscoveryDialog(self._player, self._repo, self.show_toast, parent=self)
    dlg.exec()
    self._refresh_station_list()

def _open_import_dialog(self) -> None:
    """D-15: Open ImportDialog from hamburger menu."""
    dlg = ImportDialog(self.show_toast, self._repo, parent=self)
    dlg.import_complete.connect(self._refresh_station_list)
    dlg.exec()
```
**Apply to main_window.py edits:**
- `_open_gbs_search_dialog` mirrors `_open_discovery_dialog` exactly (drop the
  `self._player` arg per CONTEXT.md "no preview play").
- `_on_gbs_add_clicked` does NOT open a dialog — it kicks off
  `gbs_api.import_station(self._repo, on_progress=...)` (likely on a worker
  thread similar to `_ExportWorker` at lines 64-79) and toasts on completion
  ("GBS.FM added" / "GBS.FM streams updated") via `self.show_toast`.

**Worker QThread for non-blocking import pattern** (lines 64-79 — `_ExportWorker`):
```python
class _ExportWorker(QThread):
    finished = Signal(str)   # emits dest_path on success
    error = Signal(str)

    def __init__(self, dest_path: str, parent=None):
        super().__init__(parent)
        self._dest_path = dest_path

    def run(self):
        try:
            from musicstreamer.repo import Repo
            repo = Repo(db_connect())
            settings_export.build_zip(repo, self._dest_path)
            self.finished.emit(self._dest_path)
        except Exception as exc:
            self.error.emit(str(exc))
```
**Apply to main_window.py edit:** New `_GbsImportWorker(QThread)` follows the same
shape — `finished = Signal(int, int)` (inserted, updated counts) +
`error = Signal(str)`. Stored as `self._gbs_import_worker` for GC retention
(SYNC-05 precedent at line 174).

**Toast surface pattern** (line 302):
```python
def show_toast(self, text: str, duration_ms: int = 3000) -> None:
    self._toast.show_toast(text, duration_ms)
```
**Apply:** Pass `self.show_toast` as a callback into both new dialogs and into
`_on_gbs_add_clicked`. Already established as the standard plumbing —
AccountsDialog (line 693) and DiscoveryDialog (line 670) both receive it.

---

### `musicstreamer/ui_qt/accounts_dialog.py` modifications (component, event-driven)

**Analog within file:** YouTube `_youtube_box` (lines 91-103) and Twitch group
(lines 104-115). Phase 60's `_gbs_box` is the third sibling.

**QGroupBox + status_label + action_btn pattern** (lines 91-103):
```python
# Phase 53: YouTube group box (D-01, D-09 — first / topmost group).
self._youtube_box = QGroupBox("YouTube", self)
youtube_layout = QVBoxLayout(self._youtube_box)

self._youtube_status_label = QLabel(self)
self._youtube_status_label.setTextFormat(Qt.TextFormat.PlainText)  # T-40-04
self._youtube_status_label.setFont(status_font)
youtube_layout.addWidget(self._youtube_status_label)

self._youtube_action_btn = QPushButton(self)
self._youtube_action_btn.clicked.connect(self._on_youtube_action_clicked)  # QA-05
youtube_layout.addWidget(self._youtube_action_btn)
```
**Apply to accounts_dialog.py edit:** Insert `_gbs_box` block between
`_youtube_box` block and the Twitch block per D-04c. Use the SAME `status_font`
shared variable defined at lines 88-89. `Qt.TextFormat.PlainText` (T-40-04)
mandatory for the status label.

**Layout ordering pattern** (lines 134-140):
```python
layout = QVBoxLayout(self)
layout.setContentsMargins(16, 16, 16, 16)
layout.setSpacing(8)
layout.addWidget(self._youtube_box)
layout.addWidget(twitch_box)
layout.addWidget(aa_box)
layout.addWidget(btn_box)
```
**Apply to accounts_dialog.py edit:** Insert `layout.addWidget(self._gbs_box)`
between `_youtube_box` and `twitch_box` per D-04c.

**Status detection pattern** (lines 148-157):
```python
def _is_connected(self) -> bool:
    return os.path.exists(paths.twitch_token_path())

def _is_youtube_connected(self) -> bool:
    """Phase 53 D-02: True when paths.cookies_path() exists on disk."""
    return os.path.exists(paths.cookies_path())

def _is_aa_key_saved(self) -> bool:
    """Phase 48 D-07: True when ``audioaddict_listen_key`` is non-empty."""
    return bool(self._repo.get_setting("audioaddict_listen_key", ""))
```
**Apply to accounts_dialog.py edit:** Add `_is_gbs_connected(self) -> bool`
returning `os.path.exists(paths.gbs_cookies_path())`. Mirrors the YouTube
predicate exactly because ladder #3 chose the cookies-file path.

**Status update + button text pattern** (lines 161-166):
```python
if self._is_youtube_connected():
    self._youtube_status_label.setText("Connected")
    self._youtube_action_btn.setText("Disconnect")
else:
    self._youtube_status_label.setText("Not connected")
    self._youtube_action_btn.setText("Import YouTube Cookies...")
```
**Apply to accounts_dialog.py edit:** Inside `_update_status()`, add a sibling
block: `Connected` / `Not connected` + button text `Disconnect` /
`Import GBS.FM Cookies...`.

**Connect/Disconnect handler pattern** (lines 235-270 — YouTube precedent):
```python
def _on_youtube_action_clicked(self) -> None:
    if self._is_youtube_connected():
        answer = QMessageBox.question(
            self, "Disconnect YouTube?",
            "This will delete your saved YouTube cookies. ...",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            try:
                os.remove(paths.cookies_path())
            except FileNotFoundError:
                pass
            self._update_status()
    else:
        from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog
        dlg = CookieImportDialog(self._toast_callback, parent=self)
        dlg.exec()
        self._update_status()
```
**Apply to accounts_dialog.py edit:** New `_on_gbs_action_clicked` follows the
same shape — `os.remove(paths.gbs_cookies_path())` on Disconnect (with
`FileNotFoundError` race tolerance), and on Connect open the parameterized
CookieImportDialog (or new `GbsCookieImportDialog` per planner choice in
D-04 ladder #3 refactor decision).

---

### `musicstreamer/ui_qt/now_playing_panel.py` modifications (component)

**Analog within file:** Phase 64 `_sibling_label` (hide-when-empty) + `star_btn`
(optimistic + bound-method) + cover-art adapter (worker-thread → Qt signal).

**Hide-when-empty conditional widget pattern** (lines 183-189, 661-688):
```python
# Phase 64 / D-01, D-05, D-05a: cross-network "Also on:" sibling line.
# ...
# Hidden until populated (D-05) -- QVBoxLayout reclaims zero vertical
# space for hidden children.
self._sibling_label = QLabel("", self)
self._sibling_label.setTextFormat(Qt.RichText)
self._sibling_label.setOpenExternalLinks(False)
self._sibling_label.setVisible(False)
# QA-05: bound-method connection (no self-capturing lambda).
self._sibling_label.linkActivated.connect(self._on_sibling_link_activated)
center.addWidget(self._sibling_label)
```
And the refresh logic (lines 661-688):
```python
def _refresh_siblings(self) -> None:
    if self._station is None or not self._station.streams:
        self._sibling_label.setVisible(False)
        self._sibling_label.setText("")
        return
    ...
    if not siblings:
        self._sibling_label.setVisible(False)
        self._sibling_label.setText("")
        return
    self._sibling_label.setText(render_sibling_html(siblings, self._station.name))
    self._sibling_label.setVisible(True)
```
**Apply to now_playing_panel.py edits:**
- `_gbs_playlist_widget = QListWidget(self)` constructed with `setVisible(False)`,
  added to layout (planner picks placement; below the controls row is the most
  natural fit — consistent with how `_stats_widget` lands as the last
  center-column item at line 305).
- `_gbs_vote_buttons` list of 5 `QPushButton` (per RESEARCH §Claude's Discretion
  "5 separate buttons labeled 1-5") — all `setVisible(False)` initially.
- New `_refresh_gbs_visibility()` method called from `bind_station()` (line 353-376
  is the only call site mirror — see `_refresh_siblings` at line 376) that:
  - Shows `_gbs_playlist_widget` iff `station.provider_name == "GBS.FM"`.
  - Shows the 5 vote buttons iff GBS AND `_is_gbs_logged_in()`
    (mirrors `_is_youtube_connected` predicate).
  - Starts/stops `_gbs_poll_timer` (`QTimer` 15s — matches gbs.fm web UI's
    `DELAY = 15000` per RESEARCH Pitfall 5 + Pitfall 11).

**Important deviation:** the `_sibling_label` uses `Qt.RichText` (deviation from
T-39-01 default — see in-file comment at lines 173-178). Phase 60's playlist
widget rows + vote buttons MUST use `Qt.TextFormat.PlainText` per RESEARCH
Pitfall 11 (artist/title/score strings come from gbs.fm and could carry HTML).

**Optimistic UI + bound-method click pattern** (lines 491-519 — `_on_star_clicked`):
```python
def _on_star_clicked(self) -> None:
    if self._station is None or not self._last_icy_title:
        return
    is_fav = self._repo.is_favorited(self._station.name, self._last_icy_title)
    if is_fav:
        self._repo.remove_favorite(self._station.name, self._last_icy_title)
        self.star_btn.setChecked(False)
        self.star_btn.setIcon(
            QIcon.fromTheme("non-starred-symbolic", QIcon(":/icons/non-starred-symbolic.svg"))
        )
        self.star_btn.setToolTip("Save track to favorites")
        self.track_starred.emit(...)
    else:
        ...
```
**Apply to now_playing_panel.py edits:** `_on_gbs_vote_clicked()` reads the
clicked button's `vote_value` property (set per RESEARCH Code Examples §Pattern 5 —
`b.setProperty("vote_value", v)`), updates the visual state immediately, and
kicks a `_GbsVoteWorker` (analog: `_SearchWorker` at discovery_dialog.py:95-123).
On worker `finished` signal use the API-returned `userVote` + `score` as the
truth (RESEARCH Pitfall 2). On worker `error`, restore the prior visual state
and call `self.parent_main_window.show_toast(...)` (or the equivalent owned
toast surface).

**Worker-thread → Qt-signal queued-connection pattern** (lines 333-337, 575-601):
```python
# Cover art signal adapter — queued connection so emission from the
# cover_art worker thread is marshalled onto the main thread.
self.cover_art_ready.connect(
    self._on_cover_art_ready, Qt.ConnectionType.QueuedConnection
)
...
def _fetch_cover_art_async(self, icy_title: str) -> None:
    self._cover_fetch_token += 1
    token = self._cover_fetch_token
    emit = self.cover_art_ready.emit  # bound Signal.emit — no self-capture
    def _cb(path_or_none):
        # Runs on worker thread — emit only, no widget access.
        emit(f"{token}:{path_or_none or ''}")
    fetch_cover_art(icy_title, _cb)

def _on_cover_art_ready(self, payload: str) -> None:
    token_str, _, path = payload.partition(":")
    try:
        token = int(token_str)
    except ValueError:
        return
    if token != self._cover_fetch_token:
        return  # stale response — a newer fetch is in flight
    ...
```
**Apply to now_playing_panel.py edits:** Critical pattern for both the
playlist refresh AND the vote click:
- `Qt.QueuedConnection` is mandatory when worker thread emits signals into
  the panel.
- The "stale response token" trick (lines 576-577, 596-597) MUST apply to the
  playlist refresh — when station changes mid-poll, the in-flight response is
  for the wrong station and must be discarded. Use `_gbs_poll_token` integer.
- This also addresses RESEARCH Pitfall 1 (ICY title → entryid race): vote
  worker captures the entryid AT CLICK TIME (not from `_last_icy_title`), and
  the entryid is updated only by the poll worker's `now_playing` event.

**bind_station hook for refresh pattern** (lines 353-376 — exact insertion point):
```python
def bind_station(self, station: Station) -> None:
    self._station = station
    if station.provider_name:
        self.name_provider_label.setText(
            f"{station.name} · {station.provider_name}"
        )
    else:
        self.name_provider_label.setText(station.name)
    ...
    self._populate_stream_picker(station)
    # Phase 64 / D-04: re-derive 'Also on:' line for the newly bound station.
    # This is the ONLY call site for _refresh_siblings -- D-04 invariant
    # (locked by test_refresh_siblings_runs_once_per_bind_station_call).
    self._refresh_siblings()
```
**Apply to now_playing_panel.py edit:** Add `self._refresh_gbs_visibility()` as
the LAST line of `bind_station`. Mirror the "this is the ONLY call site"
invariant + add a corresponding test
(`test_refresh_gbs_visibility_runs_once_per_bind_station_call`) per the
Phase 64 D-04 precedent at line 374.

---

### `musicstreamer/paths.py` modifications (utility)

**Analog within file:** `cookies_path` (line 46) and `twitch_token_path`
(line 50).

**Path accessor pattern** (lines 46-51):
```python
def cookies_path() -> str:
    return os.path.join(_root(), "cookies.txt")


def twitch_token_path() -> str:
    return os.path.join(_root(), "twitch-token.txt")
```
**Apply to paths.py edit:** Add at the same indent and section:
```python
def gbs_cookies_path() -> str:
    return os.path.join(_root(), "gbs-cookies.txt")
```
Pure — does NOT create the directory (per file's docstring contract at line 13).

---

### `musicstreamer/ui_qt/cookie_import_dialog.py` modifications (component)

**Analog within file:** the dialog itself — Phase 60 either parameterizes it
or subclasses for `GbsCookieImportDialog`. RESEARCH §Pattern 4 + Open Questions Q4
recommends parameterize (option 1); planner picks at PLAN time.

**`_validate_youtube_cookies` pattern to mirror as `_validate_gbs_cookies`** (lines 50-63):
```python
def _validate_youtube_cookies(text: str) -> bool:
    """Return True if text contains at least one .youtube.com domain line.

    Expects Netscape-format tab-separated lines; lines starting with '#'
    and blank lines are skipped.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split("\t")
        if len(parts) >= 6 and ".youtube.com" in parts[0]:
            return True
    return False
```
**Apply (new helper):** `_validate_gbs_cookies(text)` returns True iff text has
at least one Netscape line for domain `gbs.fm` AND a cookie named `sessionid`
AND a cookie named `csrftoken` (RESEARCH §Auth Ladder Recommendation +
Assumption A9). Defensive — use the cookie-name as the column-6 value check
(Netscape format columns: `domain | flag | path | secure | expiry | name | value`).

**Three-tab dialog shape** (lines 70-186) — applied verbatim if planner
parameterizes:
```python
class CookieImportDialog(QDialog):
    """Three-tab dialog for importing YouTube cookies.
    Tabs: File | Paste | Google Login
    All paths call _write_cookies() which enforces 0o600 permissions.
    """
    def __init__(self, toast_callback: Callable[[str], None], parent: ...):
        super().__init__(parent)
        ...
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_file_tab(), "File")
        self._tabs.addTab(self._build_paste_tab(), "Paste")
        self._tabs.addTab(self._build_google_tab(), "Google Login")
```
**Apply (refactor):** Constructor takes config:
```python
def __init__(
    self,
    toast_callback: Callable[[str], None],
    parent=None,
    *,
    target_label: str = "YouTube",      # window title + tab labels
    cookies_path: Callable[[], str] = paths.cookies_path,
    validator: Callable[[str], bool] = _validate_youtube_cookies,
    oauth_mode: str = "google",         # subprocess --mode argument
):
```
Phase 60 v1 ships file-picker + paste tabs only (RESEARCH §Open Questions Q3 —
in-app login subprocess deferred). The third tab is optional polish — guard
on `oauth_mode is not None` if planner wants to make it optional from config.

**0o600 file write pattern** (lines 299-308 — Phase 999.7 convention):
```python
def _write_cookies(self, text: str) -> None:
    """Write cookie text to cookies_path() with 0o600 permissions."""
    dest = paths.cookies_path()
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(dest, 0o600)
    self._toast("YouTube cookies imported.")
    self.accept()
```
**Apply (refactor):** Replace `paths.cookies_path()` with `self._cookies_path()`
config callable. Replace `"YouTube cookies imported."` toast text with
`f"{self._target_label} cookies imported."` (planner can wire the exact
copywriting per `target_label`).

---

### `musicstreamer/oauth_helper.py` modifications (controller — OPTIONAL)

**RESEARCH §Open Questions Q3 → "in-app login subprocess for ladder #3 — required for v1? NO."**

**Analog within file:** `_TwitchCookieWindow` (lines 108+ — cookie-harvest pattern).

**If planner adds `--mode gbs` (optional polish in v1):**
- argparse flag at the top-level dispatcher (read existing flag handling for
  --mode shape).
- New `_GbsCookieWindow(QMainWindow)` modeled on `_TwitchCookieWindow` (line 108).
  Login URL: `https://gbs.fm/accounts/login/`. Cookie names to harvest:
  `sessionid` AND `csrftoken` on domain `gbs.fm`.
- `_emit_event` schema (lines 71-86) reused as-is; `provider="gbs"` in the JSON
  payload.

---

## `tests/test_gbs_api.py` (NEW test file)

**Analog:** `/home/kcreasey/OneDrive/Projects/MusicStreamer/tests/test_aa_import.py`
+ `/home/kcreasey/OneDrive/Projects/MusicStreamer/tests/test_radio_browser.py`

**Imports + helpers pattern** (analog test_aa_import.py lines 1-34):
```python
import json
import urllib.error
from unittest.mock import MagicMock, patch, call

import pytest

from musicstreamer.aa_import import _resolve_pls, fetch_channels, import_stations
from musicstreamer.aa_import import fetch_channels_multi, import_stations_multi


def _mock_channel_json(name: str, key: str) -> bytes:
    return json.dumps([{"name": name, "key": key}]).encode()


def _urlopen_factory(data: bytes, content_type: str = "audio/x-scpls"):
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    cm.read = MagicMock(return_value=data)
    headers_mock = MagicMock()
    headers_mock.get = MagicMock(return_value=content_type)
    cm.headers = headers_mock
    return cm


def _make_http_error(code: int):
    return urllib.error.HTTPError(url="http://test", code=code, msg="err", hdrs=None, fp=None)
```
**Apply to test_gbs_api.py:** Same helper structure. Two new helpers:
- `_load_fixture(name) -> bytes` — reads from `tests/fixtures/gbs/{name}`.
- `_urlopen_with_redirect(status, location, body)` — for the 302→login
  detection tests (RESEARCH Pitfall 3 + Capability 6).

**urlopen-patching pattern** (analog lines 45-48):
```python
with patch("musicstreamer.aa_import.urllib.request.urlopen",
           side_effect=lambda url, timeout=None: _urlopen_factory(channel_data)), \
     patch("musicstreamer.aa_import._resolve_pls", side_effect=lambda url: [url]):
    result = fetch_channels("testkey123", "hi")
```
**Apply to test_gbs_api.py:** Same pattern targeting
`musicstreamer.gbs_api.urllib.request.urlopen` (or
`musicstreamer.gbs_api._open_with_cookies` for cookie-bearing endpoints —
patch the helper to skip cookie-jar plumbing in unit tests).

**Mock Repo with `station_exists_by_url` pattern** (analog lines 143, 161, 175):
```python
mock_repo.station_exists_by_url.return_value = False
...
mock_repo.station_exists_by_url.return_value = True
...
mock_repo.station_exists_by_url.side_effect = [False, True]
```
**Apply to test_gbs_api.py:** Same shape for `import_station` idempotent tests
(D-02a) — first call inserts (mock returns False), second call updates in
place (mock returns True). Use a `fake_repo` shared fixture in `conftest.py`
to standardize across the suite per RESEARCH Wave 0 Gaps.

---

## `tests/conftest.py` extension

**Analog within file:** existing autouse `_stub_bus_bridge` fixture (lines 20-30):
```python
@pytest.fixture(autouse=True)
def _stub_bus_bridge(monkeypatch):
    """Replace _ensure_bus_bridge with a MagicMock so Player() construction
    never starts the real GLib.MainLoop daemon thread in unit tests."""
    try:
        import musicstreamer.player as _player_mod
    except ImportError:
        return
    monkeypatch.setattr(
        _player_mod, "_ensure_bus_bridge", lambda: MagicMock()
    )
```
**Apply to conftest.py edit:** Add NON-autouse fixtures:
- `mock_gbs_api` — `MagicMock(spec=musicstreamer.gbs_api)` with `fetch_streams`,
  `fetch_active_playlist`, `vote_now_playing`, `search`, `submit` pre-stubbed.
- `fake_repo` — minimal in-memory dict-backed Repo double matching the
  `station_exists_by_url` / `insert_station` / `insert_stream` / `list_streams`
  / `update_stream` / `get_setting` / `set_setting` API used in Phase 60.
- `fake_cookies_jar` — empty `http.cookiejar.MozillaCookieJar` instance.

---

## `tests/ui_qt/test_now_playing_panel_gbs.py` (NEW test file)

**Analog:** `/home/kcreasey/OneDrive/Projects/MusicStreamer/tests/test_now_playing_panel.py`

**qtbot fixture pattern** (analog line 166):
```python
def test_panel_construction(qtbot):
    ...
```
**Apply to test_now_playing_panel_gbs.py:** Same `qtbot` injection. Tests per
RESEARCH §Phase Requirements → Test Map (`test_playlist_hidden_for_non_gbs`,
`test_playlist_populates`, `test_playlist_timer_pauses`,
`test_vote_hidden_when_logged_out`, `test_vote_optimistic_success`,
`test_vote_optimistic_rollback`, `test_vote_entryid_updates_from_ajax`).

---

## Shared Patterns

### Authentication / cookie persistence
**Source:** `musicstreamer/cookie_utils.py` (lines 33-83)
**Apply to:** `musicstreamer/gbs_api.py` (load auth context), AccountsDialog (Connect
flow), validation in `cookie_import_dialog.py`.
```python
# From cookie_utils.py:33-49 — corruption predicate
def is_cookie_file_corrupted(path: str) -> bool:
    """Return True if ``path`` was written by yt-dlp's save_cookies()."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(512)
    except OSError:
        return False
    for line in head.splitlines()[:4]:
        if _YTDLP_MARKER in line:
            return True
    return False

# From cookie_utils.py:52-83 — temp-copy contextmanager
@contextlib.contextmanager
def temp_cookies_copy() -> Iterator[Optional[str]]:
    """Yield a path to a per-call temp copy of paths.cookies_path(), or None."""
    canonical = paths.cookies_path()
    if not os.path.exists(canonical):
        yield None
        return
    fd, tmp_path = tempfile.mkstemp(prefix="ms-cookies-", suffix=".txt")
    os.close(fd)
    try:
        try:
            shutil.copy2(canonical, tmp_path)
        except OSError:
            yield None
            return
        yield tmp_path
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
```
**Phase 60 reuse:** `is_cookie_file_corrupted()` works as-is (the yt-dlp marker
detection is content-agnostic). For `temp_cookies_copy()`, planner needs a
parallel `temp_gbs_cookies_copy()` that targets `paths.gbs_cookies_path()` —
or the existing helper can be parameterized to accept a path callable.
RESEARCH §Don't Hand-Roll forbids reimplementing this.

### Bound-method connections (QA-05)
**Source:** every Qt connection in the codebase (project convention).
**Apply to:** ALL new menu connections (`act_gbs_add.triggered`,
`act_gbs_search.triggered`), button connections in `_gbs_box`
(`_gbs_action_btn.clicked`), each vote button (`b.clicked`), search dialog
buttons (`_search_btn.clicked`, per-row submit buttons).
**Verify-work signal:** "self-capturing lambda detected" — see RESEARCH Pitfall 10.

### `Qt.TextFormat.PlainText` (T-40-04)
**Source:** `accounts_dialog.py:96, 109, 122` (every status_label) +
`now_playing_panel.py:168, 198` (name_provider_label, icy_label).
**Apply to:** `_gbs_status_label`, every label rendering gbs.fm strings
(artist, title, score, account name, search row text). The Phase 64
`_sibling_label` exception (RichText for `<a href>` links) does NOT extend to
Phase 60 — vote buttons / playlist rows do not contain user-clickable
gbs.fm-side links.
**Verify-work signal:** RESEARCH Pitfall 11 ("Account name renders with HTML
formatting").

### 0o600 file mode for sensitive data
**Source:** `cookie_import_dialog.py:306` and `accounts_dialog.py:349`:
```python
os.chmod(dest, 0o600)
os.chmod(token_path, 0o600)  # T-40-03: restrict permissions immediately
```
**Apply to:** `paths.gbs_cookies_path()` write-path. Mandatory — Phase 999.7
convention.

### Stream-ordering FLAC sentinel
**Source:** `musicstreamer/stream_ordering.py:43-64` — partition logic:
```python
def order_streams(streams: List[StationStream]) -> List[StationStream]:
    """Return a NEW list of streams sorted for failover.

    Sort key: (quality_rank desc, codec_rank desc, bitrate_kbps desc, position asc).
    Unknown bitrates (bitrate_kbps <= 0) are partitioned LAST and sorted
    among themselves by position asc (D-07).
    """
    known = [s for s in streams if (s.bitrate_kbps or 0) > 0]
    unknown = [s for s in streams if (s.bitrate_kbps or 0) <= 0]
    known_sorted = sorted(
        known,
        key=lambda s: (
            -quality_rank(s.quality),
            -codec_rank(s.codec),
            -(s.bitrate_kbps or 0),
            s.position,
        ),
    )
    unknown_sorted = sorted(unknown, key=lambda s: s.position)
    return known_sorted + unknown_sorted
```
**Apply to gbs_api.py:** RESEARCH recommends `bitrate_kbps=1411` for FLAC so it
sorts FIRST among known-bitrate streams (FLAC codec_rank=3 already beats
MP3 codec_rank=1 — see line 18 — so `quality_rank` ties are broken by codec
before bitrate matters). However, GBS.FM streams have `quality="96"`/`"flac"`
not `"hi"`/`"med"`/`"low"`, so they all fall to `quality_rank=0` (line 22 —
no match) and the codec_rank + bitrate become the primary tiebreakers. With
codec_rank(FLAC)=3 > codec_rank(MP3)=1, FLAC wins regardless of `bitrate_kbps`
value as long as it's > 0 (so the sentinel can be 1411 or even 1 — both work).
**Test:** `test_gbs_flac_ordering` (RESEARCH Wave 0 Gaps + GBS-01a Test Map
row) MUST verify FLAC sorts first.

### Repo multi-stream insert/update
**Source:** `musicstreamer/repo.py:185-201`:
```python
def insert_stream(self, station_id: int, url: str, label: str = "",
                  quality: str = "", position: int = 1,
                  stream_type: str = "", codec: str = "",
                  bitrate_kbps: int = 0) -> int:
    cur = self.con.execute(
        "INSERT INTO station_streams(station_id,url,label,quality,position,stream_type,codec,bitrate_kbps) VALUES(?,?,?,?,?,?,?,?)",
        (station_id, url, label, quality, position, stream_type, codec, bitrate_kbps))
    self.con.commit()
    return int(cur.lastrowid)

def update_stream(self, stream_id: int, url: str, label: str,
                  quality: str, position: int, stream_type: str, codec: str,
                  bitrate_kbps: int = 0):
    self.con.execute(
        "UPDATE station_streams SET url=?,label=?,quality=?,position=?,stream_type=?,codec=?,bitrate_kbps=? WHERE id=?",
        (url, label, quality, position, stream_type, codec, bitrate_kbps, stream_id))
    self.con.commit()
```
**Apply to gbs_api.py `import_station`:** Per-quality `repo.insert_stream(...)`
calls. The first stream is auto-created by `repo.insert_station(...)` (line 416 —
`if url: self.insert_stream(station_id, url)` with default args), so the orchestrator
must `update_stream` the first row to add quality/codec/bitrate metadata
(precedent at aa_import.py:246-255). Also see `discovery_dialog.py:432-439`
for the post-insert fix-up pattern.

### `station_exists_by_url` for idempotent re-fetch
**Source:** `musicstreamer/repo.py:401-405`:
```python
def station_exists_by_url(self, url: str) -> bool:
    row = self.con.execute(
        "SELECT 1 FROM station_streams WHERE url = ?", (url,)
    ).fetchone()
    return row is not None
```
**Apply to gbs_api.py D-02a:** Phase 60's "is GBS.FM already in the library?"
check uses URL pattern match (RESEARCH Claude's Discretion recommendation —
gbs.fm is one station, so `repo.station_exists_by_url("https://gbs.fm/96")`
or any of the 6 stable stream URLs is sufficient).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/fixtures/gbs/*.{json,html,txt}` | fixture (15 files) | static data | First HTTP-replay fixture set in repo. RESEARCH §Validation Architecture has the full list with `curl` source URLs. No structural analog needed — they're captured payloads. |
| `scripts/gbs_capture_fixtures.sh` | utility | I/O | First fixture-capture script in repo. Short bash + curl with cookies; planner writes from RESEARCH §Validation Architecture table directly. |

---

## Metadata

**Analog search scope:**
- `musicstreamer/` (top-level Python modules)
- `musicstreamer/ui_qt/` (Qt UI modules)
- `tests/` (pytest suite)
- `tests/ui_qt/` (pytest-qt suite)

**Files scanned (full read):** 11
- `musicstreamer/aa_import.py` (380 lines)
- `musicstreamer/radio_browser.py` (76 lines)
- `musicstreamer/cookie_utils.py` (83 lines)
- `musicstreamer/paths.py` (86 lines)
- `musicstreamer/cover_art.py` (101 lines)
- `musicstreamer/ui_qt/cookie_import_dialog.py` (316 lines)
- `musicstreamer/ui_qt/discovery_dialog.py` (505 lines)
- `musicstreamer/ui_qt/accounts_dialog.py` (449 lines)
- `tests/conftest.py` (30 lines)
- `tests/test_aa_import.py` (first 100 lines for helper shape)
- `musicstreamer/stream_ordering.py` (full)

**Files targeted (offset+limit):** 3
- `musicstreamer/ui_qt/main_window.py` (200 + 61 lines around the relevant ranges)
- `musicstreamer/ui_qt/now_playing_panel.py` (lines 155-355, 485-645, 645-762)
- `musicstreamer/repo.py` (lines 175-225, 395-430)
- `musicstreamer/oauth_helper.py` (first 120 lines for `--mode` dispatch shape)

**Pattern extraction date:** 2026-05-04

---

## PATTERN MAPPING COMPLETE
