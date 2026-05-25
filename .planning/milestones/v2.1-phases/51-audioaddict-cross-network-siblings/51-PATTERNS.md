# Phase 51: AudioAddict Cross-Network Siblings — Pattern Map

**Mapped:** 2026-04-28
**Files analyzed:** 4 (2 modified, 1 possibly modified, 2 new tests)
**Analogs found:** 4 / 4 (1 modified file is its own analog — extending an existing class)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/ui_qt/edit_station_dialog.py` (modify — add sibling section, dirty-check, signal) | dialog (QDialog) | request-response (UI event → signal-out) | self — `EditStationDialog` already has `_LogoFetchWorker`, `station_saved`, `station_deleted`, `_on_delete` patterns; extend the same file | exact (in-file) |
| `musicstreamer/ui_qt/main_window.py` (modify — wire `navigate_to_sibling`) | controller (window orchestration) | event-driven (signal → slot → re-open dialog) | self — `_on_edit_requested` (line 462) already implements "open EditStationDialog → connect signals → exec" | exact (in-file) |
| `musicstreamer/url_helpers.py` (extend) **or** `musicstreamer/aa_siblings.py` (new) | utility (pure URL/data transform) | batch (list → filtered list) | `musicstreamer/url_helpers.py` (`_aa_channel_key_from_url` + `_aa_slug_from_url`) | exact (same module style, same dependencies) |
| `tests/test_aa_siblings.py` (new — unit) | test (pytest, no Qt) | request-response | `tests/test_aa_url_detection.py` (pure unit tests against `url_helpers`) | exact |
| `tests/test_edit_station_dialog.py` (extend — pytest-qt dialog tests) | test (pytest-qt) | request-response | `tests/test_edit_station_dialog.py` itself — fixtures + `qtbot` + `MagicMock` repo already set up | exact (in-file) |
| `tests/test_main_window_integration.py` (extend — sibling-navigation flow) | test (pytest-qt integration) | event-driven | `test_new_station_save_refreshes_and_selects` (line 623) — exact precedent for "monkeypatch `EditStationDialog.exec`, emit signal, assert MainWindow side-effect" | exact (in-file) |

**Rendering pattern note (the new clickable link):** `QLabel.linkActivated` + `setOpenExternalLinks(False)` + inline `<a href="sibling://{id}">` markup is **new for this codebase** — no existing precedent. All current `QLabel`s call `setTextFormat(Qt.PlainText)` (T-39-01). The planner must explicitly call `setTextFormat(Qt.RichText)` on the new sibling label and document the deviation. See `## Shared Patterns → Qt.PlainText safety` below.

**Dirty-state predicate:** also **new for this codebase** — no analog. The closest existing precedent is the `_is_new` flag (line 200) which is a different mechanism (lifecycle marker, not change detector). Document as a new pattern in the plan.

---

## Pattern Assignments

### `musicstreamer/ui_qt/edit_station_dialog.py` (dialog, request-response)

**Analog:** self — extending an existing class. The closest in-file precedents are:
- `_LogoFetchWorker` (lines 53–120) — "derive AA slug + channel_key inside the dialog"
- `station_saved` / `station_deleted` Signals (lines 187–188) — "signal out from dialog → MainWindow"
- `_on_delete` (lines 787–798) — "QMessageBox.question confirm before destructive action"
- `_populate` (lines 382–415) — "post-construction data wiring; called once from `__init__`"

**Imports pattern** (lines 23–50, additions for this phase):
```python
# EXISTING (already imported):
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                                QMessageBox, QVBoxLayout, ...)

# NEW additions for Phase 51:
from musicstreamer.url_helpers import _is_aa_url, _aa_slug_from_url, _aa_channel_key_from_url
# (or, if helper lives in a new module:)
# from musicstreamer.aa_siblings import find_aa_siblings
```
Project convention: `from __future__ import annotations` at module top (line 17), absolute imports rooted at `musicstreamer.*` (no relative imports).

**"Derive AA key inside the dialog" pattern** — the closest analog for the new sibling-detection helper call site. From `_LogoFetchWorker.run` (lines 89–101):
```python
from musicstreamer.url_helpers import (
    _is_aa_url, _aa_slug_from_url, _aa_channel_key_from_url,
)
if _is_aa_url(url):
    slug = _aa_slug_from_url(url)
    channel_key = _aa_channel_key_from_url(url, slug=slug)
    if not slug or not channel_key:
        # ... handle "AA URL but no key" case
        return
    # ... do something with (slug, channel_key)
```
Apply this exact gating pattern in the new sibling-detection path inside `_populate` (or a `_refresh_siblings()` helper called from `_populate`).

**Signal-out pattern** (lines 187–188):
```python
class EditStationDialog(QDialog):
    """Modal dialog for editing station properties and managing streams."""

    station_saved = Signal()
    station_deleted = Signal(int)

    # NEW in Phase 51 — same shape as station_deleted:
    navigate_to_sibling = Signal(int)   # sibling station id
```
The signal is emitted from a slot; `MainWindow` subscribes and re-routes (see `main_window.py` analog below). Bound-method connections only (QA-05) — no self-capturing lambdas in `EditStationDialog.__init__`. Lambdas inside `MainWindow._on_edit_requested` are the documented exception (line 470).

**Confirm-before-destructive pattern** (lines 787–798) — the analog for the new "Save & continue / Discard & continue / Cancel" dirty-state confirm:
```python
def _on_delete(self) -> None:
    answer = QMessageBox.question(
        self,
        "Delete Station",
        f"Delete '{self._station.name}'? This cannot be undone.",
        QMessageBox.Yes | QMessageBox.Cancel,
        QMessageBox.Cancel,
    )
    if answer == QMessageBox.Yes:
        self._repo.delete_station(self._station.id)
        self.station_deleted.emit(self._station.id)
        self.accept()
```
For the new 3-button confirm, expand the standard-buttons mask to `Save | Discard | Cancel` and dispatch on the answer:
```python
# NEW pattern for Phase 51 — same QMessageBox.question shape, 3 buttons.
answer = QMessageBox.question(
    self,
    "Unsaved changes",
    "You have unsaved changes. Save before navigating?",
    QMessageBox.StandardButton.Save
    | QMessageBox.StandardButton.Discard
    | QMessageBox.StandardButton.Cancel,
    QMessageBox.StandardButton.Cancel,
)
if answer == QMessageBox.StandardButton.Save:
    self._on_save()                     # may show its own validation warning
    if not self._save_succeeded:        # new flag — see "dirty-state pattern"
        return                          # save failed; stay in dialog
elif answer == QMessageBox.StandardButton.Discard:
    pass                                # fall through to navigation
else:                                   # Cancel
    return
self.navigate_to_sibling.emit(sibling_id)
```
Note the existing codebase uses both unqualified (`QMessageBox.Yes`, `QMessageBox.Cancel`) and qualified (`QMessageBox.StandardButton.Yes`) forms — `accounts_dialog.py:182` and `main_window.py:409` use the qualified form, `edit_station_dialog.py:792` uses the unqualified one. **Prefer the qualified form for new code** (matches the more recent usages in main_window/accounts_dialog).

**`_populate` extension pattern** (lines 382–415) — where to hook the sibling refresh:
```python
def _populate(self) -> None:
    station = self._station
    # ... existing population (name, url, provider, tags, ICY, streams) ...
    # Logo preview (Plan 40.1-04)
    self._refresh_logo_preview()

    # NEW for Phase 51 — append at end of _populate:
    self._refresh_siblings()
```
Note `_populate` already does a `streams = self._repo.list_streams(station.id)` at line 389. **Reuse the same first-stream URL** (`streams[0].url`) for the AA-URL gate so the dirty-check and the sibling lookup agree on which URL is canonical.

**Layout-insertion pattern** (lines 354 + 376) — where the new sibling row goes:
```python
# Existing structure of _build_ui (relevant tail):
form.addRow("Streams:", streams_container)        # line 354 — last form row
# ... button-box construction (lines 362-374) ...
outer.addWidget(self.button_box)                  # line 376 — last widget added

# NEW for Phase 51 — insert immediately before the button-box, after the form:
self._sibling_label = QLabel("", self)
self._sibling_label.setTextFormat(Qt.RichText)             # DEVIATION from T-39-01
self._sibling_label.setOpenExternalLinks(False)
self._sibling_label.linkActivated.connect(self._on_sibling_link_activated)
self._sibling_label.setVisible(False)                      # D-06: hidden when empty
outer.addWidget(self._sibling_label)
outer.addWidget(self.button_box)                            # existing — last
```
The `setVisible(False)` default supports the D-06 "zero vertical space when no siblings" requirement.

**Logo-preview cache-invalidation pattern as analog for "refresh on edit"** (lines 558–567) — if the planner picks the dirty-state mechanism that requires re-snapshotting after save, this is the closest precedent for "re-run a derived UI computation":
```python
def _refresh_logo_preview(self) -> None:
    resolved = abs_art_path(self._logo_path)
    if resolved and os.path.exists(resolved):
        pix = QPixmap(resolved)
        if not pix.isNull():
            self._logo_preview.setPixmap(...)
            return
    self._logo_preview.clear()
```
The new `_refresh_siblings()` follows the same shape: derive inputs from current dialog state, compute, render or clear.

**Cleanup-on-close pattern** (lines 680–698) — irrelevant to the new sibling code (sibling rendering owns no resources), but cited so the planner does **not** add new state to `closeEvent`/`reject` unless a new resource is introduced.

---

### `musicstreamer/ui_qt/main_window.py` (controller, event-driven)

**Analog:** `_on_edit_requested` (lines 462–472) — exact precedent for "open `EditStationDialog`, connect its signals, exec". The new `navigate_to_sibling` connection is a one-line addition.

**Existing pattern** (lines 462–472):
```python
def _on_edit_requested(self, station: Station) -> None:
    """Open EditStationDialog for the given station (D-08)."""
    # Re-fetch from DB so edits saved moments ago are visible (UAT #2 fix)
    fresh = self._repo.get_station(station.id)
    if fresh is None:
        return
    dlg = EditStationDialog(fresh, self._player, self._repo, parent=self)
    dlg.station_saved.connect(self._refresh_station_list)
    dlg.station_saved.connect(lambda: self._sync_now_playing_station(fresh.id))
    dlg.station_deleted.connect(self._on_station_deleted)
    dlg.exec()
```

**Apply the same pattern for the new signal:**
```python
# Inside _on_edit_requested, alongside the existing connects:
dlg.navigate_to_sibling.connect(self._on_navigate_to_sibling)
```
And add a new bound-method slot (QA-05 — no lambda):
```python
def _on_navigate_to_sibling(self, sibling_id: int) -> None:
    """Phase 51: re-open EditStationDialog for the sibling station.

    Called when user clicks an "Also on:" link in the current dialog.
    The current dialog has already accepted/rejected itself (via Save or
    Discard inside the dirty-state confirm path — see EditStationDialog).
    Match the shape of _on_edit_requested: re-fetch from DB, construct,
    connect signals, exec.
    """
    sibling = self._repo.get_station(sibling_id)
    if sibling is None:
        return
    self._on_edit_requested(sibling)   # reuse existing path
```
**Recommendation**: have `_on_navigate_to_sibling` delegate straight to `_on_edit_requested` so signal wiring lives in one place. The planner may inline if there's a reason to diverge (e.g. skipping the now-playing sync when navigating between siblings — neither sibling is the playing station's edit target in the typical case).

Also wire the `_on_new_station_clicked` path (line 437–460) for symmetry — but only if AA stations can be created via "+" (they can — the user could paste an AA URL into a fresh dialog). The simplest approach is to add the same `dlg.navigate_to_sibling.connect(self._on_navigate_to_sibling)` line in both locations.

**Signal-import pattern** (lines 56, 230, 256–258):
```python
# Existing imports at top:
from musicstreamer.ui_qt.edit_station_dialog import EditStationDialog

# Existing signal-wiring zone (line 230 area — "Signal wiring (D-18, QA-05)"):
self.now_playing.edit_requested.connect(self._on_edit_requested)
self.station_panel.edit_requested.connect(self._on_edit_requested)
```
The `navigate_to_sibling` signal is per-dialog-instance (not panel-wide), so it gets connected inside `_on_edit_requested` / `_on_new_station_clicked`, not in the constructor's signal-wiring block.

---

### `musicstreamer/url_helpers.py` (extend) **or** `musicstreamer/aa_siblings.py` (new) — utility, batch

**Analog:** `musicstreamer/url_helpers.py` itself — the new sibling-detection helper is a pure function over (current URL, current station id, list of stations), with the same dependency profile as `_aa_channel_key_from_url`.

**Module-style precedent** (`url_helpers.py:1–13`):
```python
"""Pure URL classification helpers for stream sources.

Extracted from musicstreamer/ui/edit_dialog.py during the Phase 36 GTK cutover
so that non-UI tests (test_aa_url_detection, test_yt_thumbnail) survive the
deletion of the ui/ tree. These helpers have zero GTK/Qt coupling — they are
pure string and regex manipulation over URL literals.
"""
from __future__ import annotations

import urllib.parse

from musicstreamer.aa_import import NETWORKS
```
**Constraint**: zero Qt coupling. The new helper must take primitive types (or the existing dataclass `Station` from `models.py`, which is also Qt-free). Do NOT import from `musicstreamer.ui_qt.*`.

**Helper-shape analog** (`url_helpers.py:38–69`):
```python
def _aa_channel_key_from_url(url: str, slug: str | None = None) -> str | None:
    """Extract channel key from an AudioAddict stream URL path segment.
    ...
    """
    try:
        parsed = urllib.parse.urlparse(url)
        ...
        return key or None
    except Exception:
        return None
```
**New helper shape** (planner's call: extend `url_helpers.py` or create `aa_siblings.py`):
```python
def find_aa_siblings(
    stations: list[Station],
    current_station_id: int,
    current_first_url: str,
) -> list[tuple[str, int, str]]:
    """Phase 51: return AA stations on other networks sharing the same channel key.

    Returns a list of (network_slug, station_id, station_name) tuples.
    Excludes the current station by id. Excludes stations whose first stream
    URL is non-AA, has no slug, or has no derivable channel key.
    Returns [] if the current URL is non-AA or has no channel key.

    Sort order: NETWORKS declaration order in aa_import.py
    (di → radiotunes → jazzradio → rockradio → classicalradio → zenradio).
    """
    ...
```
**Sort-order precedent** (`aa_import.py:87–94`):
```python
NETWORKS = [
    {"slug": "di",             "domain": "listen.di.fm",              "name": "DI.fm"},
    {"slug": "radiotunes",     "domain": "listen.radiotunes.com",     "name": "RadioTunes"},
    {"slug": "jazzradio",      "domain": "listen.jazzradio.com",      "name": "JazzRadio"},
    {"slug": "rockradio",      "domain": "listen.rockradio.com",      "name": "RockRadio"},
    {"slug": "classicalradio", "domain": "listen.classicalradio.com", "name": "ClassicalRadio"},
    {"slug": "zenradio",       "domain": "listen.zenradio.com",       "name": "ZenRadio"},
]
```
The sort key for siblings is the index of `slug` in `[n["slug"] for n in NETWORKS]`. The display-name lookup (`slug → "ZenRadio"`) is `next((n["name"] for n in NETWORKS if n["slug"] == slug), slug)`.

**Recommendation**: extend `url_helpers.py` rather than creating a new module. The helper depends on `_is_aa_url`, `_aa_slug_from_url`, `_aa_channel_key_from_url`, and `NETWORKS` — all of which already live in or are imported by `url_helpers.py`. Adding a new module here would force `url_helpers.py` to import from `aa_siblings.py` (or duplicate dependencies). One file, three new lines of import surface, one new public function.

**Edge-case handling** — the existing `_aa_channel_key_from_url` returns `None` on failure. The new helper inherits the same convention: any sibling candidate whose URL fails to parse is silently filtered out (D-03/D-04). No exceptions raised, no logging — match the precedent.

---

### `tests/test_aa_siblings.py` (test, request-response) — NEW

**Analog:** `tests/test_aa_url_detection.py` (full file, 55 lines) — the canonical "pure unit tests against `url_helpers`" pattern, no Qt, no fixtures, one assertion per test.

**Imports pattern** (`test_aa_url_detection.py:1`):
```python
from musicstreamer.url_helpers import _is_aa_url, _aa_channel_key_from_url
```
**Test-function shape** (`test_aa_url_detection.py:4–26`):
```python
def test_is_aa_url_di():
    assert _is_aa_url("http://prem2.di.fm:80/di_house?listen_key=abc") is True

def test_channel_key_strips_quality_suffix():
    # DI.fm/RadioTunes stream URLs append _hi quality tier — must be stripped
    assert _aa_channel_key_from_url("http://prem2.di.fm:80/ambient_hi?listen_key=abc", "di") == "ambient"

def test_channel_key_strips_zenradio_prefix():
    # ZenRadio stream URLs use 'zr' prefix — must be stripped to match API key
    assert _aa_channel_key_from_url("http://prem1.zenradio.com:80/zrambient", "zenradio") == "ambient"
```
Apply this exact shape for `find_aa_siblings`:
```python
from musicstreamer.models import Station, StationStream
from musicstreamer.url_helpers import find_aa_siblings  # or musicstreamer.aa_siblings


def _mk(id_, name, url):
    """Factory: a minimal Station with one stream at `url`."""
    return Station(
        id=id_, name=name, provider_id=None, provider_name=None,
        tags="", station_art_path=None, album_fallback_path=None,
        streams=[StationStream(id=id_*10, station_id=id_, url=url, position=1)],
    )


def test_finds_zenradio_sibling_for_difm_ambient():
    di = _mk(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    zr = _mk(2, "Ambient", "http://prem4.zenradio.com/zrambient?listen_key=abc")
    siblings = find_aa_siblings([di, zr], current_station_id=1, current_first_url=di.streams[0].url)
    assert siblings == [("zenradio", 2, "Ambient")]


def test_excludes_self_by_id():
    ...

def test_excludes_same_network_same_key():
    """Two DI.fm stations with the same channel key — not siblings (same network)."""
    ...

def test_excludes_non_aa_stations():
    ...

def test_excludes_stations_with_unparseable_first_url():
    ...

def test_returns_empty_when_current_is_non_aa():
    ...

def test_returns_empty_when_current_has_no_channel_key():
    ...

def test_sort_order_matches_networks_declaration():
    """Multiple siblings sort by NETWORKS order: di < radiotunes < jazzradio < rockradio < classicalradio < zenradio."""
    ...
```
**No Qt fixtures, no qtbot, no MagicMock** — pure data in / data out. Match `test_aa_url_detection.py` exactly.

---

### `tests/test_edit_station_dialog.py` (extend — pytest-qt) — dialog-level wiring tests

**Analog:** `tests/test_edit_station_dialog.py` itself — the existing fixtures (`station`, `repo`, `player`, `dialog`) at lines 19–60 and the existing test patterns are the direct precedent.

**Fixture pattern** (lines 33–60) — reuse as-is for new tests:
```python
@pytest.fixture()
def repo():
    r = MagicMock()
    r.list_providers.return_value = [
        Provider(1, "TestProvider"),
        Provider(2, "Other"),
    ]
    r.list_streams.return_value = [
        StationStream(id=10, station_id=1, url="http://s1.mp3",
                      label="", quality="hi", position=1, codec="MP3"),
    ]
    r.ensure_provider.return_value = 1
    return r


@pytest.fixture()
def dialog(qtbot, station, player, repo):
    d = EditStationDialog(station, player, repo, parent=None)
    qtbot.addWidget(d)
    return d
```
For Phase 51 the `repo` fixture also needs `r.list_stations.return_value = [...]` (the new sibling-detection path calls `repo.list_stations()`). The `station` fixture's `url` will need to be an AA URL for the sibling section to render. Either parameterize the existing fixtures or add a new `aa_dialog` fixture alongside.

**Signal-emission test pattern** — closest analog is the implicit `station_saved.emit()` in `test_save_calls_repo_correctly` (lines 210–225). For an explicit signal-emission test, the precedent in `test_main_window_integration.py:633` is:
```python
def _fake_exec(self):
    self.station_saved.emit()
    return QDialog.Accepted
```
For Phase 51, a `qtbot.waitSignal` pattern works cleanly:
```python
def test_link_activated_emits_navigate_to_sibling(qtbot, dialog):
    """Clicking an 'Also on:' link emits navigate_to_sibling(sibling_id)."""
    # ... arrange siblings via repo mock ...
    with qtbot.waitSignal(dialog.navigate_to_sibling, timeout=1000) as blocker:
        dialog._sibling_label.linkActivated.emit("sibling://42")
    assert blocker.args == [42]
```

**QMessageBox.question monkeypatch pattern** (lines 644–662):
```python
from PySide6.QtWidgets import QMessageBox

warning_calls: list = []
monkeypatch.setattr(
    QMessageBox,
    "warning",
    staticmethod(lambda *a, **kw: warning_calls.append((a, kw)) or QMessageBox.Ok),
)
```
Apply the same shape for the new `QMessageBox.question` confirm — monkeypatch the `question` static method to return `Save`, `Discard`, or `Cancel` and assert the corresponding side-effect:
```python
monkeypatch.setattr(
    QMessageBox, "question",
    staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Discard),
)
# now click a sibling link with dirty state, assert navigate_to_sibling fires
```

**Tests to add (suggested):**
- `test_sibling_section_hidden_for_non_aa_station` — non-AA URL → `_sibling_label.isVisible() == False`
- `test_sibling_section_hidden_when_no_siblings` — AA URL but no other AA stations → hidden
- `test_sibling_section_renders_links_for_aa_station_with_siblings`
- `test_sibling_link_format_uses_network_name_when_station_names_match`
- `test_sibling_link_format_uses_network_dash_name_when_station_names_differ`
- `test_link_activated_emits_navigate_to_sibling_when_clean`
- `test_link_activated_shows_confirm_when_dirty`
- `test_dirty_confirm_save_path_runs_save_then_navigates`
- `test_dirty_confirm_discard_path_navigates_without_saving`
- `test_dirty_confirm_cancel_stays_in_dialog`
- `test_is_dirty_after_name_edit`, `test_is_dirty_after_url_edit`, `test_is_dirty_after_streams_edit` — depending on which dirty-detection mechanism the planner picks

---

### `tests/test_main_window_integration.py` (extend — pytest-qt integration) — navigation flow

**Analog:** `test_new_station_save_refreshes_and_selects` (lines 623–671) — exact precedent for "monkeypatch `EditStationDialog.exec`, simulate signal emission, assert MainWindow side-effect".

**Existing pattern** (lines 623–671) — copy this shape verbatim:
```python
def test_new_station_save_refreshes_and_selects(
    qtbot, fake_player, fake_repo, monkeypatch
):
    """D-07a: after a successful save in the New Station flow, MainWindow
    refreshes the station panel model and selects the newly-created row."""
    from PySide6.QtWidgets import QDialog
    from musicstreamer.ui_qt import edit_station_dialog as esd_mod
    from musicstreamer.ui_qt import station_list_panel as slp_mod

    def _fake_exec(self):
        # Simulate "user hit Save" — emit station_saved, then accept.
        self.station_saved.emit()
        return QDialog.Accepted

    monkeypatch.setattr(esd_mod.EditStationDialog, "exec", _fake_exec)
    ...
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    action.trigger()
    ...
    assert select_calls == [new_id], ...
```
**For Phase 51** — same monkeypatch approach, but emit `navigate_to_sibling`:
```python
def test_navigate_to_sibling_reopens_dialog_for_sibling(
    qtbot, fake_player, fake_repo, monkeypatch
):
    """Phase 51 SC #2: clicking an Also-on link closes the current dialog and
    opens EditStationDialog for the sibling station."""
    from PySide6.QtWidgets import QDialog
    from musicstreamer.ui_qt import edit_station_dialog as esd_mod

    exec_calls: list = []

    def _fake_exec(self):
        # First call: emit navigate_to_sibling(SIBLING_ID), then accept.
        # Subsequent calls: just record + accept (the "sibling's dialog opened").
        exec_calls.append(self._station.id)
        if len(exec_calls) == 1:
            self.navigate_to_sibling.emit(SIBLING_ID)
        return QDialog.Accepted

    monkeypatch.setattr(esd_mod.EditStationDialog, "exec", _fake_exec)
    ...
    # Assert exec_calls == [original_id, SIBLING_ID]
```

**`fake_repo` / `fake_player` fixture context**: defined elsewhere in `test_main_window_integration.py` (search for `@pytest.fixture` near the top). The planner extends both fixtures with whatever is needed (e.g. multiple AA stations in `fake_repo.list_stations()` so a real sibling lookup works).

---

## Shared Patterns

### Bound-method signal connections (QA-05)
**Source:** `musicstreamer/ui_qt/edit_station_dialog.py:247–249`, `:265–266`, `:372–374`; `musicstreamer/ui_qt/main_window.py:230–260`
**Apply to:** all new `linkActivated`, `navigate_to_sibling`, `clicked`, `textChanged` connections introduced by Phase 51.

```python
# CORRECT — bound method:
self._sibling_label.linkActivated.connect(self._on_sibling_link_activated)
dlg.navigate_to_sibling.connect(self._on_navigate_to_sibling)

# WRONG — self-capturing lambda (QA-05 violation):
self._sibling_label.linkActivated.connect(lambda href: self._handle(href))  # NO
```
**Documented exception**: lambdas that capture only local-scope variables (not `self`) are accepted in `MainWindow._on_edit_requested` for `_sync_now_playing_station` (line 470). The Phase 51 wiring should not need this exception.

### Qt.PlainText safety (T-39-01) — and the documented deviation
**Source:** `musicstreamer/ui_qt/now_playing_panel.py:160`, `accent_color_dialog.py:73`, `accounts_dialog.py:82`, `cookie_import_dialog.py:103`, `settings_import_dialog.py:110` (and 9 more) — every QLabel in the project enforces `setTextFormat(Qt.PlainText)`.

```python
# Standard pattern (applied EVERYWHERE in the codebase today):
self._status_label.setTextFormat(Qt.PlainText)  # T-40-04: no rich-text injection
```
**Phase 51 deviation** (the new sibling label is the FIRST `QLabel` in the codebase to use `Qt.RichText`):
```python
# Phase 51 — explicit RichText for inline <a> links.
# Justification: the sibling href has the form "sibling://{int}" — a
# bounded, dialog-controlled scheme. Network display names come from the
# NETWORKS constant (compile-time). Station names (in the "Network — Name"
# format) are user-controllable BUT must be HTML-escaped before
# interpolation to defuse T-39-01 risk.
self._sibling_label.setTextFormat(Qt.RichText)
self._sibling_label.setOpenExternalLinks(False)
self._sibling_label.linkActivated.connect(self._on_sibling_link_activated)
```
**Mitigation requirement**: any station name interpolated into the rendered HTML must pass through `html.escape(name, quote=True)` before insertion. The planner must reference `html.escape` explicitly in the rendering helper — this is a NEW security-relevant edge for the project. Network names (`"DI.fm"`, `"ZenRadio"`, etc.) are compile-time constants and need no escaping.

### Re-fetch from repo before opening EditStationDialog
**Source:** `musicstreamer/ui_qt/main_window.py:464–465`
**Apply to:** the new `_on_navigate_to_sibling` slot.
```python
# Re-fetch from DB so edits saved moments ago are visible (UAT #2 fix)
fresh = self._repo.get_station(station.id)
if fresh is None:
    return
```
Sibling navigation passes through this same re-fetch path — guarantees the sibling's dialog sees fresh data even if the just-saved dialog modified it indirectly.

### `__future__` annotations + absolute imports
**Source:** every module (e.g. `edit_station_dialog.py:17`, `url_helpers.py:8`, `main_window.py:19`).
**Apply to:** any new module created (only `aa_siblings.py` if planner picks that path).
```python
from __future__ import annotations
```

---

## No Analog Found

| Need | Why no analog | Recommended approach |
|------|---------------|----------------------|
| `QLabel` with inline `<a href>` + `linkActivated` | Codebase has 16 QLabels, all `Qt.PlainText`. Phase 51 introduces the first rich-text QLabel. | Standard Qt idiom: `setTextFormat(Qt.RichText)` + `setOpenExternalLinks(False)` + `linkActivated.connect(slot)`. Document deviation from T-39-01 with HTML-escape for station names (see Shared Patterns). |
| Dialog-level `_is_dirty()` predicate | No existing dialog tracks edit-vs-pristine state. The `_is_new` flag on `EditStationDialog` is a lifecycle marker, not a change detector. | Planner picks: (a) snapshot on `_populate` end (capture name, URL, provider, tags, ICY, streams-table contents), then compare on `_is_dirty()` call; or (b) per-widget `textChanged` / `currentTextChanged` / `stateChanged` listeners that flip `self._dirty = True`. Option (a) is more robust against future field additions; option (b) is cheaper at check-time. Note streams-table dirty detection requires either snapshotting the row contents or wiring `cellChanged` — `QTableWidget` has no built-in dirty signal. |
| 3-button QMessageBox.question (Save / Discard / Cancel) | Codebase uses 2-button (Yes / Cancel or Yes / No) `QMessageBox.question` in 4 places. | Use `QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel` mask. Default to Cancel (matches the existing default-to-No pattern in `accounts_dialog.py`). Standard buttons render with platform-appropriate i18n labels — no custom strings needed. |

---

## Metadata

**Analog search scope:**
- `musicstreamer/ui_qt/` (16 files — full scan for QLabel patterns, signal patterns, QMessageBox patterns)
- `musicstreamer/url_helpers.py`, `musicstreamer/aa_import.py`, `musicstreamer/repo.py`, `musicstreamer/models.py` (full read for helper-shape and data-model)
- `tests/test_edit_station_dialog.py`, `tests/test_aa_url_detection.py`, `tests/test_main_window_integration.py` (selected ranges for test patterns)

**Files scanned (read in full or substantial portion):** 7 source files, 3 test files
**Files referenced for shared patterns (grep-only):** ~16 (QLabel + QMessageBox + Signal grep results)
**Pattern extraction date:** 2026-04-28
