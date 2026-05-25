# Phase 68: Live Stream Detection (DI.fm) - Pattern Map

**Mapped:** 2026-05-10
**Files analyzed:** 11 (3 new, 8 modified)
**Analogs found:** 11 / 11

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `musicstreamer/aa_live.py` | utility (pure helper) | request-response + transform | `musicstreamer/aa_import.py` (HTTP pattern) + `musicstreamer/url_helpers.py` (pure-function module) | role-match |
| `tests/test_aa_live.py` | test | batch (fixture-driven) | `tests/test_pick_similar_stations.py` | exact |
| `tests/fixtures/aa_live/*.json` | config/fixture | — | `tests/fixtures/gbs/*.json` | exact |
| `musicstreamer/ui_qt/now_playing_panel.py` | component (widget) | event-driven | itself — Phase 67 additions (`_similar_container`, `set_similar_visible`, `_refresh_similar_stations`) | exact |
| `musicstreamer/ui_qt/main_window.py` | controller | event-driven | itself — Phase 67 additions (`_act_show_similar` wiring, `similar_activated` connection, `gbs_vote_error_toast` connection) | exact |
| `musicstreamer/ui_qt/station_list_panel.py` | component (widget) | event-driven | itself — Phase 47.1 filter chip additions | exact |
| `musicstreamer/ui_qt/station_filter_proxy.py` | utility (proxy model) | transform | itself — existing `set_providers`, `set_tags`, `filterAcceptsRow` | exact |
| `tests/test_now_playing_panel.py` | test | event-driven | itself — Phase 67 similar-station tests (lines 949–1068) | exact |
| `tests/test_station_list_panel.py` | test | event-driven | itself — existing chip-visibility tests | role-match |
| `tests/test_station_filter_proxy.py` | test | transform | itself — `test_filter_by_tag_set`, `test_multi_select_and_between_or_within` | exact |
| `tests/test_main_window_integration.py` | test | event-driven | itself — Phase 67 `test_show_similar_*` tests (lines 1138–1290) | exact |

---

## Pattern Assignments

---

### `musicstreamer/aa_live.py` (utility, request-response + transform)

**Analogs:** `musicstreamer/aa_import.py` (HTTP pattern) and `musicstreamer/url_helpers.py` (module structure)

**Module docstring / public-API pattern** (url_helpers.py lines 1-8):
```python
"""Pure URL classification helpers for stream sources.

Extracted from musicstreamer/ui/edit_dialog.py during the Phase 36 GTK cutover
so that non-UI tests survive the deletion of the ui/ tree. These helpers have
zero GTK/Qt coupling — they are pure string and regex manipulation.
"""
from __future__ import annotations
```
Phase 68 analog: `aa_live.py` docstring must declare "no Qt coupling" and list public API: `fetch_live_map`, `_parse_live_map`, `detect_live_from_icy`.

**HTTP GET pattern** (aa_import.py lines 73-78):
```python
try:
    api_url = f"https://api.audioaddict.com/v1/{slug}/channels"
    with urllib.request.urlopen(api_url, timeout=10) as resp:
        data = json.loads(resp.read())
    # ... parse data ...
except urllib.error.HTTPError as e:
    if e.code in (401, 403):
        _log.warning("AA image map auth failure for %s: HTTP %s", slug, e.code)
    else:
        _log.warning("AA image map HTTP error for %s: %s", slug, e)
    return {}
except Exception as e:
    _log.warning("AA image map fetch failed for %s: %s", slug, e)
    return {}
```
Phase 68 deviation: The events endpoint requires no auth header. A-04 means any non-2xx → return `{}` silently (no logging of non-auth errors to avoid log spam on transient failures). Use `timeout=15` (matches `fetch_channels_multi` at aa_import.py:148).

**Per-network slug URL pattern** (aa_import.py lines 146-149):
```python
url = f"https://{net['domain']}/{tier}?listen_key={listen_key}"
```
Phase 68 analog:
```python
AA_EVENTS_URL = "https://api.audioaddict.com/v1/{slug}/events"
# No listen_key parameter — endpoint is public (A-02 finding)
url = AA_EVENTS_URL.format(slug=network_slug)
```

**Pure function pattern** (url_helpers.py `_aa_channel_key_from_url` lines 91-126):
```python
def _aa_channel_key_from_url(url: str, slug: str | None = None) -> str | None:
    """Extract channel key...

    Pure function — no Qt, no DB access, no logging.
    """
    try:
        # ... body ...
    except Exception:
        return None
```
Phase 68 `_parse_live_map` and `detect_live_from_icy` must follow: pure function, no Qt, no DB, no logging.

**Channel key derivation** (url_helpers.py lines 91-126 + RESEARCH Pattern 2):
```python
from musicstreamer.url_helpers import _aa_channel_key_from_url, _aa_slug_from_url, _is_aa_url

def get_di_channel_key(station) -> str | None:
    if not station.streams:
        return None
    url = station.streams[0].url
    if not _is_aa_url(url):
        return None
    slug = _aa_slug_from_url(url)
    if slug != "di":
        return None
    return _aa_channel_key_from_url(url, slug="di")
```

**Divergence from analog:** `aa_live.py` raises no `ValueError("invalid_key")` — the events API is public and returns no 401/403. All errors → return `{}`.

---

### `tests/test_aa_live.py` (test, batch/fixture-driven)

**Analog:** `tests/test_pick_similar_stations.py`

**File header pattern** (test_pick_similar_stations.py lines 1-21):
```python
"""Phase 67: pure unit tests for pick_similar_stations + render_similar_html.

Modeled on tests/test_aa_siblings.py — no Qt, no fixtures, one assertion
per test. Tests assert the contract of:

    pick_similar_stations(...) -> tuple[list[Station], list[Station]]
    render_similar_html(...) -> str
"""
import random
import time
from musicstreamer.models import Station, StationStream
from musicstreamer.url_helpers import pick_similar_stations, render_similar_html
```
Phase 68 analog:
```python
"""Phase 68: pure unit tests for aa_live helper functions.

No Qt, no live network calls. Tests assert the contract of:

    fetch_live_map(network_slug) -> dict[str, str]
    _parse_live_map(events) -> dict[str, str]
    detect_live_from_icy(title) -> str | None
"""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from musicstreamer.aa_live import _parse_live_map, detect_live_from_icy, fetch_live_map
```

**Fixture loading pattern** (modeled on gbs fixture pattern from RESEARCH.md):
```python
_FIXTURES = Path(__file__).parent / "fixtures" / "aa_live"

def _load(name: str) -> list:
    return json.loads((_FIXTURES / name).read_text())
```

**One-assertion-per-test pattern** (test_pick_similar_stations.py lines 45-62):
```python
def test_same_provider_pool_excludes_self_aa_and_no_provider():
    """Phase 67 / SIM-04 / T-04: ..."""
    # ... setup ...
    assert same_provider == [somafm_other]
```

**Divergence from analog:** Tests use `unittest.mock.patch` for HTTP mocking (no qtbot needed). Fixture files are JSON, not constructed inline, to match the gbs fixture pattern (TD-02).

---

### `tests/fixtures/aa_live/*.json` (fixtures)

**Analog:** `tests/fixtures/gbs/ajax_steady_state.json` (shape: structured JSON, realistic field subset)

**Shape:** Three files following RESEARCH.md §Code Examples:
- `events_no_live.json` — list of events all with `end_at` in past or `start_at` in future
- `events_with_live.json` — list with one event whose `start_at`/`end_at` bracket a fixed test timestamp
- `events_multiple_live.json` — list with 2+ concurrent live events on different channels

**Key fields per event** (verified from RESEARCH Pattern 1):
```json
{
  "id": 201572,
  "show_id": 10554145,
  "name": "#949",
  "start_at": "2026-05-10T11:00:00+00:00",
  "end_at": "2026-05-10T13:00:00+00:00",
  "show": {
    "id": 10554145,
    "name": "Deeper Shades of House",
    "channels": [{"id": 4, "key": "house", "name": "House"}]
  }
}
```
Note: Tests must use fixed timestamps, not `datetime.now()`, to avoid brittle time-sensitive assertions. Use `unittest.mock.patch("musicstreamer.aa_live.datetime")` or pass `now` as a parameter to `_parse_live_map`.

---

### `musicstreamer/ui_qt/now_playing_panel.py` (component, event-driven — MODIFY)

**Analog:** Itself — Phase 67 additions at lines 450-598 (`_similar_container`, `_similar_collapse_btn`, `_same_provider_subsection`), lines 770-786 (`set_similar_visible`), lines 1120-1230 (`_refresh_similar_stations`, `_on_similar_link_activated`).

**Signal declaration pattern** (now_playing_panel.py lines 186-219):
```python
# Phase 67 / I-02: emitted when user clicks a Similar Stations link
similar_activated = Signal(object)

# Phase 60 D-07a: fire on vote failure so MainWindow.show_toast surfaces
# the error to the user.
gbs_vote_error_toast = Signal(str)
```
Phase 68 adds at the same location (after `similar_activated`):
```python
# Phase 68 / T-01: emitted on live-status transition for bound station.
# MainWindow connects to show_toast (QA-05 bound-method).
live_status_toast = Signal(str)
```

**QThread worker class pattern** (now_playing_panel.py lines 73-99, `_GbsPollWorker`):
```python
class _GbsPollWorker(QThread):
    """Phase 60 D-06a / GBS-01c: poll gbs_api.fetch_active_playlist on a worker thread."""
    playlist_ready = Signal(int, object)   # (token, state_dict)
    playlist_error = Signal(int, str)      # (token, msg or sentinel)

    def __init__(self, token: int, cookies, cursor=None, parent=None):
        super().__init__(parent)
        self._token = token
        self._cookies = cookies
        self._cursor = cursor

    def run(self):
        from musicstreamer import gbs_api
        try:
            state = gbs_api.fetch_active_playlist(self._cookies, cursor=self._cursor)
            self.playlist_ready.emit(self._token, state)
        except Exception as exc:
            if isinstance(exc, gbs_api.GbsAuthExpiredError):
                self.playlist_error.emit(self._token, "auth_expired")
            else:
                self.playlist_error.emit(self._token, str(exc))
```
Phase 68 `_AaLiveWorker` mirrors this shape exactly, with `finished = Signal(object)` and `error = Signal(str)` (no token guard needed — single concurrent worker per poll cycle).

**QTimer poll setup** (now_playing_panel.py lines 418-427):
```python
self._gbs_poll_timer = QTimer(self)
self._gbs_poll_timer.setInterval(15000)
self._gbs_poll_timer.timeout.connect(self._on_gbs_poll_tick)  # QA-05
self._gbs_poll_token: int = 0
self._gbs_poll_worker = None  # SYNC-05 retention slot
```
Phase 68: `QTimer` is `setSingleShot(True)` (rescheduled each cycle per B-01 adaptive cadence), vs GBS's fixed-interval timer.

**`bind_station` insertion seam** (now_playing_panel.py lines 648-658):
```python
self._refresh_siblings()               # Phase 64
self._refresh_similar_stations()       # Phase 67
# Phase 68 NEW: insert _refresh_live_status() BEFORE _refresh_gbs_visibility
self._refresh_gbs_visibility()         # Phase 60 — MUST remain last
```
Phase 68 inserts `self._refresh_live_status()` between `_refresh_similar_stations()` and `_refresh_gbs_visibility()`.

**`_refresh_similar_stations` structure** (now_playing_panel.py lines 1120-1190):
```python
def _refresh_similar_stations(self) -> None:
    if self._station is None:
        self._same_provider_subsection.setVisible(False)
        self._same_tag_subsection.setVisible(False)
        return
    # ... derive + render ...
```
Phase 68 `_refresh_live_status` mirrors: guard on `self._station is None`, hide badge on None, detect live state, update `_live_badge.setVisible(is_live)`, compare to prior state for toast.

**Widget visibility pattern** (now_playing_panel.py lines 1051-1054):
```python
if self._station is None or not self._station.streams:
    self._sibling_label.setVisible(False)
    self._sibling_label.setText("")
    return
```
Phase 68 badge: `self._live_badge.setVisible(False)` as the guard-fail path.

**ICY title row replacement** — `icy_label` is currently added directly to center layout at line 301:
```python
center.addWidget(self.icy_label)
```
Phase 68 replaces with:
```python
icy_row = QHBoxLayout()
icy_row.setContentsMargins(0, 0, 0, 0)
icy_row.setSpacing(6)
self._live_badge = QLabel("LIVE", self)
self._live_badge.setTextFormat(Qt.PlainText)
self._live_badge.setVisible(False)
# Styling: reuse _CHIP_QSS "selected" state tokens — palette(highlight) bg,
# palette(highlighted-text) fg, border-radius 12px — for visual consistency.
self._live_badge.setStyleSheet(
    "QLabel {"
    "  background-color: palette(highlight);"
    "  color: palette(highlighted-text);"
    "  border-radius: 8px;"
    "  padding: 2px 6px;"
    "  font-weight: bold;"
    "}"
)
icy_row.addWidget(self._live_badge)
icy_row.addWidget(self.icy_label, 1)
center.addLayout(icy_row)
```

**Divergence from Phase 67 pattern:** Phase 67's `_similar_container` is a new QWidget added at the BOTTOM of center column. The `_live_badge` is INLINE next to `icy_label` (replaces `center.addWidget(self.icy_label)` with a QHBoxLayout). This is a layout seam change, not a bottom-append.

**Cross-file constraint:** `_first_bind_check` state (RESEARCH Pitfall 5) — `bind_station` must reset `self._first_bind_check = True` and `_refresh_live_status()` must clear it to `False` after firing the bind-to-already-live toast. Without this, a `title_changed` event arriving seconds after bind would fire a second T-01a toast.

---

### `musicstreamer/ui_qt/main_window.py` (controller, event-driven — MODIFY)

**Analog:** Itself — Phase 67 wiring at lines 197-202 (`_act_show_similar`), lines 340-342 (`similar_activated.connect`, `gbs_vote_error_toast.connect`), lines 354-359 (initial-state push).

**Signal-to-show_toast wiring pattern** (main_window.py line 342):
```python
# Phase 60 D-07a: forward vote-error toasts from NowPlayingPanel to show_toast (QA-05).
self.now_playing.gbs_vote_error_toast.connect(self.show_toast)
```
Phase 68 adds at same location:
```python
# Phase 68 / T-01: forward live-status transition toasts to show_toast (QA-05).
self.now_playing.live_status_toast.connect(self.show_toast)
```

**Poll loop lifecycle in `__init__`** — placed after panels are constructed and splitter set up (after line 281), before signal wiring or after it. Pattern: start after settings load (B-03).

**`closeEvent` stop pattern** (main_window.py lines 421-437):
```python
def closeEvent(self, event: QCloseEvent) -> None:
    try:
        self._player.shutdown_underrun_tracker()
    except Exception as exc:
        _log.warning("player shutdown_underrun_tracker failed: %s", exc)
    try:
        self._media_keys.shutdown()
    except Exception as exc:
        _log.warning("media_keys shutdown failed: %s", exc)
    super().closeEvent(event)
```
Phase 68 adds before `super().closeEvent(event)`:
```python
    if self._aa_poll_timer is not None:
        self._aa_poll_timer.stop()
```

**Post-dialog hook for B-04 (lazy poll-cycle check pattern)** — RESEARCH recommends the lazy option: no new signal from `AccountsDialog`. In `_open_accounts_dialog` (line 842) and `_open_import_dialog` (line 819), after `dlg.exec()`, call `self._check_and_start_aa_poll()`. This one-line hook is the simplest B-04 implementation.

**Existing dialog exec pattern** (main_window.py lines 819-823):
```python
def _open_import_dialog(self) -> None:
    """D-15: Open ImportDialog from hamburger menu."""
    dlg = ImportDialog(self.show_toast, self._repo, parent=self)
    dlg.import_complete.connect(self._refresh_station_list)
    dlg.exec()
    # Phase 68 NEW: check if AA key was saved/cleared during import
    self._check_and_start_aa_poll()
```

**`show_toast` signature** (main_window.py lines 395-397):
```python
def show_toast(self, text: str, duration_ms: int = 3000) -> None:
    """Show a toast notification on the centralWidget bottom-centre."""
    self._toast.show_toast(text, duration_ms)
```
`live_status_toast = Signal(str)` emits only `text` (no duration); `show_toast` uses default `duration_ms=3000`. Connection is direct: `live_status_toast.connect(self.show_toast)` — Qt binds with positional match on the single `str` argument.

**Cross-file constraint (QA-05):** The signal connection `self.now_playing.live_status_toast.connect(self.show_toast)` must use the bound method `self.show_toast` — no lambda. This is the same constraint as `gbs_vote_error_toast.connect(self.show_toast)` at line 342.

---

### `musicstreamer/ui_qt/station_list_panel.py` (component, event-driven — MODIFY)

**Analog:** Itself — Phase 47.1 provider chip and tag chip additions at lines 218-264.

**Chip creation pattern** (station_list_panel.py lines 218-246):
```python
# Provider chip group
self._provider_chip_group = QButtonGroup(self)
self._provider_chip_group.setExclusive(False)
provider_chip_container = QWidget(self._filter_strip)
provider_chip_layout = FlowLayout(provider_chip_container, h_spacing=4, v_spacing=8)
# ...
self._provider_chip_group.buttonClicked.connect(self._on_provider_chip_clicked)
```
and per-chip creation pattern (inferred from `_build_chip_rows`):
```python
btn = QPushButton("Provider Name", provider_chip_container)
btn.setCheckable(True)
btn.setProperty("chipState", "unselected")
btn.setStyleSheet(_CHIP_QSS)
self._provider_chip_group.addButton(btn)
provider_chip_layout.addWidget(btn)
```

**`_CHIP_QSS` tokens** (station_list_panel.py lines 53-67):
```python
_CHIP_QSS = """
QPushButton[chipState="unselected"] {
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 12px;
    padding: 4px 8px;
}
QPushButton[chipState="selected"] {
    background-color: palette(highlight);
    color: palette(highlighted-text);
    border: 1px solid palette(highlight);
    border-radius: 12px;
    padding: 4px 8px;
}
"""
```

**Phase 68 "Live now" chip — standalone pattern** (not added to `_provider_chip_group` or `_tag_chip_group`):
```python
# Phase 68: "Live now" chip — standalone (separate predicate dimension from
# provider/tag chips; not exclusive with them — AND composition per F-03).
# Hidden when no audioaddict_listen_key (F-07).
live_chip_row = QWidget(self._filter_strip)
lc_layout = QHBoxLayout(live_chip_row)
lc_layout.setContentsMargins(16, 4, 16, 0)
self._live_chip = QPushButton("Live now", live_chip_row)
self._live_chip.setCheckable(True)
self._live_chip.setProperty("chipState", "unselected")
self._live_chip.setStyleSheet(_CHIP_QSS)
# F-07: hidden when no listen key
has_key = bool(self._repo.get_setting("audioaddict_listen_key", ""))
self._live_chip.setVisible(has_key)
lc_layout.addWidget(self._live_chip)
lc_layout.addStretch(1)
fs_layout.addWidget(live_chip_row)
# QA-05: bound method, no lambda
self._live_chip.toggled.connect(self._on_live_chip_toggled)
```
**Divergence:** The "Live now" chip is NOT added to a `QButtonGroup` (it's not mutually exclusive with other chips). It's a standalone `QPushButton` whose `toggled` signal drives `station_filter_proxy.set_live_only(bool)`.

**chipState update on toggle** (mirrors `_on_provider_chip_clicked` pattern — inferred from chip QSS):
```python
def _on_live_chip_toggled(self, checked: bool) -> None:
    self._live_chip.setProperty("chipState", "selected" if checked else "unselected")
    self._live_chip.setStyleSheet(_CHIP_QSS)  # force style refresh
    self._proxy.set_live_only(checked)
```

**`set_live_map` public entry point** — `StationListPanel` must expose a method for `MainWindow` to push live map updates into the proxy:
```python
def update_live_map(self, live_map: dict) -> None:
    """Phase 68: push new live map from poll into the filter proxy."""
    self._proxy.set_live_map(live_map)
    # F-07: show chip only when key is present and map is being maintained
    # (chip visibility is set at construction; no change here unless key cleared)
```

---

### `musicstreamer/ui_qt/station_filter_proxy.py` (utility/proxy model, transform — MODIFY)

**Analog:** Itself — `set_providers`, `set_tags`, `has_active_filter`, `filterAcceptsRow` at lines 35-81.

**Existing predicate method pattern** (station_filter_proxy.py lines 35-51):
```python
def set_search(self, text: str) -> None:
    self._search_text = text
    self.invalidate()

def set_providers(self, providers: set[str]) -> None:
    self._provider_set = providers
    self.invalidate()

def set_tags(self, tags: set[str]) -> None:
    self._tag_set = tags
    self.invalidate()
```

**Phase 68 additions mirror this exactly:**
```python
def set_live_map(self, live_map: dict[str, str]) -> None:
    """Phase 68: update live channel keys from poll result.
    Calls invalidate() only when live_only is active (Pitfall 7 — avoids
    60s flicker when chip is off)."""
    self._live_channel_keys = set(live_map.keys())
    if self._live_only:
        self.invalidate()

def set_live_only(self, enabled: bool) -> None:
    self._live_only = enabled
    self.invalidate()
```

**`__init__` additions** (station_filter_proxy.py lines 25-29):
```python
def __init__(self, parent=None) -> None:
    super().__init__(parent)
    self._search_text: str = ""
    self._provider_set: set[str] = set()
    self._tag_set: set[str] = set()
    # Phase 68 NEW:
    self._live_only: bool = False
    self._live_channel_keys: set[str] = set()
```

**`has_active_filter` extension** (station_filter_proxy.py line 53-54):
```python
def has_active_filter(self) -> bool:
    return bool(self._search_text or self._provider_set or self._tag_set
                or self._live_only)   # Phase 68
```

**`filterAcceptsRow` extension** (station_filter_proxy.py lines 60-81):
```python
def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
    # ... existing provider/station logic ...
    if node.kind == "station":
        # Phase 68: live-only predicate (AND-composed with existing filters)
        if self._live_only:
            from musicstreamer.url_helpers import (
                _aa_channel_key_from_url, _aa_slug_from_url, _is_aa_url
            )
            station = node.station
            ch_key = None
            if station.streams:
                url = station.streams[0].url
                if _is_aa_url(url):
                    slug = _aa_slug_from_url(url)
                    ch_key = _aa_channel_key_from_url(url, slug=slug)
            if ch_key not in self._live_channel_keys:
                return False
        return matches_filter_multi(
            node.station, self._search_text, self._provider_set, self._tag_set
        )
```
**Divergence:** The lazy `import` inside `filterAcceptsRow` matches the existing pattern in `now_playing_panel.py` (where helpers are imported inside methods to avoid circular imports). The import only fires when `_live_only` is True, so hot-path cost is zero when chip is off.

---

### `tests/test_now_playing_panel.py` (test, event-driven — EXTEND)

**Analog:** Itself — Phase 67 similar-station tests at lines 949-1068.

**FakeRepo test-double pattern** (test_now_playing_panel.py lines 65-112):
```python
class FakeRepo:
    def __init__(self, settings: Optional[dict] = None,
                 stations: Optional[list] = None) -> None:
        self._settings = dict(settings or {})
        self._stations: list = list(stations or [])

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value

    def list_stations(self) -> list:
        return list(self._stations)
```
Phase 68 must support `FakeRepo(settings={"audioaddict_listen_key": "testkey123"}, stations=[...])`.

**Badge-visibility test pattern** (mirrors test_sibling_label_hidden_for_non_aa_station at line 793):
```python
def test_live_badge_hidden_on_non_live_bind(qtbot):
    """Phase 68 / U-01/U-04: badge hidden by default after bind to non-live station."""
    station = _station()
    repo = FakeRepo(settings={"audioaddict_listen_key": "key"})
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.bind_station(station)
    # _live_map is empty; no ICY live prefix → badge hidden
    assert panel._live_badge.isHidden() is True
```

**Toast-signal capture pattern** (mirrors test_star_btn_track_starred_signal at line 485):
```python
def test_bind_to_live_emits_toast(qtbot):
    """Phase 68 / T-01a: bind to already-live station → live_status_toast emitted."""
    station = _make_di_station(1, "House", "http://prem1.di.fm:80/di_house?listen_key=k")
    repo = FakeRepo(settings={"audioaddict_listen_key": "k"})
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    # Pre-populate live map as if poll already ran
    panel._live_map = {"house": "Deeper Shades of House"}
    with qtbot.waitSignal(panel.live_status_toast, timeout=1000) as blocker:
        panel.bind_station(station)
    assert "live" in blocker.args[0].lower()
```

**Cross-file constraint (Pitfall 5):** `_first_bind_check` state must be reset in `bind_station` and cleared in `_refresh_live_status`. Tests for T-01a vs T-01b must cover both the bind path and the mid-listen path. Use two separate tests.

---

### `tests/test_station_list_panel.py` (test, event-driven — EXTEND)

**Analog:** Itself — `test_filter_strip_hidden_in_favorites_mode` at line 318, `test_new_station_button_exists_and_right_aligned` at line 416.

**Chip-visibility test pattern** (test_filter_strip_hidden_in_favorites_mode at line 318):
```python
def test_filter_strip_hidden_in_favorites_mode(qtbot):
    """Search box and chip rows are on page 0; not visible when page 1 is active."""
    # ... setup ...
    w._favorites_btn.click()
    assert not w._search_box.isVisible()
```
Phase 68 analog:
```python
def test_live_chip_hidden_without_key(qtbot):
    """Phase 68 / F-07: when audioaddict_listen_key is empty, 'Live now' chip is hidden."""
    repo = FakeRepo(settings={})   # no listen key
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)
    assert panel._live_chip.isHidden() is True

def test_live_chip_visible_with_key(qtbot):
    """Phase 68 / F-07 / N-03: when key is present, chip is visible."""
    repo = FakeRepo(settings={"audioaddict_listen_key": "testkey"})
    panel = StationListPanel(repo)
    qtbot.addWidget(panel)
    assert panel._live_chip.isVisible() is True
```

---

### `tests/test_station_filter_proxy.py` (test, transform — EXTEND)

**Analog:** Itself — `test_filter_by_tag_set` at line 110 and `test_multi_select_and_between_or_within` at line 124.

**Proxy test factory** (test_station_filter_proxy.py lines 48-54):
```python
def _make_proxy(stations=None) -> tuple[StationTreeModel, StationFilterProxyModel]:
    model = StationTreeModel(stations or _STATIONS)
    proxy = StationFilterProxyModel()
    proxy.setSourceModel(model)
    return model, proxy
```

**AND-composition test pattern** (test_station_filter_proxy.py lines 124-138):
```python
def test_multi_select_and_between_or_within(qtbot):
    _, proxy = _make_proxy()
    proxy.set_providers({"SomaFM", "DI.fm"})
    proxy.set_tags({"chill"})
    visible = _visible_station_names(proxy)
    # AND between dimensions: stations must match provider AND tag
    assert "Groove Salad" in visible   # SomaFM + chill
    assert "Drone Zone" not in visible  # SomaFM but not chill
```
Phase 68 analog:
```python
def test_live_only_and_provider(qtbot):
    """Phase 68 / F-03: Live now chip + provider chip = AND composition."""
    _, proxy = _make_proxy(_DI_STATIONS)
    proxy.set_live_map({"trance": "Future Sound of Egypt"})
    proxy.set_live_only(True)
    proxy.set_providers({"DI.fm"})
    visible = _visible_station_names(proxy)
    assert "Trance" in visible
    assert "House" not in visible  # not in live_map

def test_live_only_empty(qtbot):
    """Phase 68 / F-04: chip ON, no live channels → empty tree."""
    _, proxy = _make_proxy(_DI_STATIONS)
    proxy.set_live_map({})
    proxy.set_live_only(True)
    assert _visible_station_names(proxy) == []

def test_set_live_map_no_invalidate_when_chip_off(qtbot):
    """Phase 68 / Pitfall 7: set_live_map does NOT call invalidate when live_only=False."""
    _, proxy = _make_proxy()
    proxy.set_live_only(False)
    # Patch invalidate to detect spurious calls
    calls = []
    original = proxy.invalidate
    proxy.invalidate = lambda: calls.append(1) or original()
    proxy.set_live_map({"trance": "Test"})
    assert calls == []  # no invalidate fired
```

---

### `tests/test_main_window_integration.py` (test, event-driven — EXTEND)

**Analog:** Itself — Phase 67 `test_show_similar_action_is_checkable` (line 1138), `test_show_similar_toggle_persists_and_toggles_panel` (line 1160), `test_no_lambda_on_similar_signal_connections` (line 1271).

**FakePlayer/FakeRepo test-double pattern** (test_main_window_integration.py lines 30-100):
Already includes `underrun_recovery_started = Signal()`, `cookies_cleared = Signal(str)`. Phase 68 needs no new signals on FakePlayer — the `live_status_toast` signal originates in `NowPlayingPanel`, not `Player`.

**Poll-loop lifecycle test pattern** (mirrors test_show_similar_toggle_persists_and_toggles_panel at line 1160):
```python
def test_poll_loop_starts_with_key(qtbot, fake_player, fake_repo):
    """Phase 68 / B-03: poll timer starts if audioaddict_listen_key is present."""
    fake_repo._settings["audioaddict_listen_key"] = "testkey"
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    assert w._aa_poll_timer.isActive() is True

def test_poll_loop_not_started_without_key(qtbot, fake_player, fake_repo):
    """Phase 68 / B-03 / N-01: no listen key → poll timer not started."""
    # fake_repo has no audioaddict_listen_key
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    assert w._aa_poll_timer.isActive() is False
```

**Toast wiring test pattern** (mirrors test at line 1271):
```python
def test_live_status_toast_wired_to_show_toast(qtbot, fake_player, fake_repo):
    """Phase 68 / T-01 / QA-05: live_status_toast signal must connect to
    show_toast via bound method (no lambda)."""
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    toasts = []
    original = w.show_toast
    w.show_toast = lambda t, d=3000: toasts.append(t) or original(t, d)
    w.now_playing.live_status_toast.emit("Now live: Test Show on Test Station")
    assert toasts == ["Now live: Test Show on Test Station"]
```

---

## Shared Patterns

### Authentication / Feature Gate
**Source:** `musicstreamer/ui_qt/accounts_dialog.py:169-171`
**Apply to:** `aa_live.py` (B-03 poll gate), `station_list_panel.py` (F-07 chip visibility), `main_window.py` (`_check_and_start_aa_poll`), all tests constructing DI.fm scenarios
```python
def _is_aa_key_saved(self) -> bool:
    """Phase 48 D-07: True when audioaddict_listen_key is non-empty."""
    return bool(self._repo.get_setting("audioaddict_listen_key", ""))
```
Phase 68 reads the same setting key: `self._repo.get_setting("audioaddict_listen_key", "")`. No write path in Phase 68 — read-only consumer.

### QThread Worker (no token guard, single concurrent)
**Source:** `musicstreamer/ui_qt/now_playing_panel.py:73-99` (`_GbsPollWorker`) and `musicstreamer/ui_qt/import_dialog.py:74-93` (`_YtScanWorker`)
**Apply to:** `_AaLiveWorker` in `now_playing_panel.py` (or `main_window.py` — planner picks)
```python
class _AaLiveWorker(QThread):
    finished = Signal(object)  # dict[str, str] — {channel_key: show_name}
    error = Signal(str)

    def __init__(self, network_slug: str = "di", parent=None):
        super().__init__(parent)
        self._slug = network_slug

    def run(self):
        try:
            from musicstreamer.aa_live import fetch_live_map
            live_map = fetch_live_map(self._slug)
            self.finished.emit(live_map)
        except Exception as exc:
            self.error.emit(str(exc))
```
Worker is created fresh each poll cycle (not reused). Parent must retain a reference in `self._aa_live_worker` (SYNC-05 pattern from `_gbs_poll_worker = None`).

### QTimer Single-Shot Reschedule Pattern
**Source:** `musicstreamer/ui_qt/now_playing_panel.py:418-427` (GBS poll timer, fixed interval)
**Apply to:** `_aa_poll_timer` in main_window.py or now_playing_panel.py
Phase 68 deviation: uses `setSingleShot(True)` instead of `setInterval(N)` because cadence is adaptive (60s vs 300s per B-01). Timer is restarted after each `_on_aa_live_ready` / `_on_aa_live_error` with the new cadence.

### Error Handling / Slots-Never-Raise
**Source:** `musicstreamer/ui_qt/now_playing_panel.py:1051-1065` (`_refresh_siblings` guard pattern)
**Apply to:** `_refresh_live_status()` in `now_playing_panel.py`
```python
try:
    all_stations = self._repo.list_stations()
except Exception:
    self._sibling_label.setVisible(False)
    self._sibling_label.setText("")
    return
```
Phase 68 analog: any exception in `_refresh_live_status()` → hide badge silently, return.

### QA-05 Bound-Method Signal Connections
**Source:** `musicstreamer/ui_qt/main_window.py:342`
**Apply to:** All new signal connections in Phase 68 — `live_status_toast.connect(self.show_toast)`, `_aa_poll_timer.timeout.connect(self._on_aa_poll_tick)`, `_aa_live_worker.finished.connect(...)`, `_live_chip.toggled.connect(...)`.
```python
# CORRECT (QA-05)
self.now_playing.gbs_vote_error_toast.connect(self.show_toast)

# FORBIDDEN
self.now_playing.gbs_vote_error_toast.connect(lambda msg: self.show_toast(msg))
```

### PlainText Security Lock
**Source:** `musicstreamer/ui_qt/now_playing_panel.py:300`
**Apply to:** `_live_badge` QLabel construction
```python
self.icy_label.setTextFormat(Qt.PlainText)
```
`_live_badge` must also use `Qt.PlainText` — show names from the AA API could contain HTML metacharacters (V5 ASVS constraint from RESEARCH security section).

---

## No Analog Found

All files have analogs in the codebase. No "no analog" entries.

---

## Metadata

**Analog search scope:** `musicstreamer/`, `musicstreamer/ui_qt/`, `tests/`
**Files read:** 15 source files + 4 test files
**Pattern extraction date:** 2026-05-10

**Key cross-file constraints:**
1. `_refresh_live_status()` inserts BEFORE `_refresh_gbs_visibility()` in `bind_station` (RESEARCH Pitfall 4).
2. `_live_badge.setTextFormat(Qt.PlainText)` — security requirement (V5 ASVS).
3. `live_status_toast = Signal(str)` declared in `NowPlayingPanel` class body alongside `gbs_vote_error_toast`. Connected in `MainWindow.__init__` via `self.now_playing.live_status_toast.connect(self.show_toast)` (QA-05 bound method).
4. `_first_bind_check: bool` must be reset to `True` in `bind_station` before calling `_refresh_live_status()`, and cleared after T-01a path executes — prevents duplicate toast on first `title_changed` after bind (RESEARCH Pitfall 5).
5. `set_live_map()` in `StationFilterProxyModel` must guard `invalidate()` with `if self._live_only:` — prevents 60s tree-flicker when chip is off (RESEARCH Pitfall 7).
6. `_AaLiveWorker.run()` must never call `QTimer.singleShot()` or touch Qt event-loop objects — use `Signal(QueuedConnection)` for all cross-thread communication (RESEARCH anti-pattern §1, spike-findings threading rules).
7. `aa_live.py` must have zero Qt imports — pure Python + stdlib only (RESEARCH anti-pattern §2, testability requirement TD-02).
