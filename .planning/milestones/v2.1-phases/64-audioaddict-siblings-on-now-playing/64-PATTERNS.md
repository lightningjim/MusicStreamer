# Phase 64: AudioAddict Siblings on Now Playing — Pattern Map

**Mapped:** 2026-05-01
**Files analyzed:** 7 (4 modified, 3 test extensions/new)
**Analogs found:** 7 / 7 (100% — Phase 64 is a near-twin of Phase 51; every behavior has a verbatim or near-verbatim in-codebase analog)

> **Phase characterization:** Pure Qt main-thread plumbing. Every new method body, every new signal declaration, every new layout block has a Phase 51 source you can cite line-numbers against. PATTERNS.md surfaces the **5–15 line excerpts** the planner should embed in `<read_first>` blocks so each task is mechanical.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/url_helpers.py` (modify — add `render_sibling_html` free function + `import html`) | utility (pure HTML rendering) | transform (data → string) | `musicstreamer/ui_qt/edit_station_dialog.py:531-574` (the body to lift verbatim, minus `self`) | **exact (verbatim body lift)** |
| `musicstreamer/ui_qt/edit_station_dialog.py` (modify — delete `_render_sibling_html`, update import at :53, update call site at :608, drop dead imports) | dialog (QDialog) | request-response (in-place refactor) | self — same file, same call site, same import block | exact (in-file refactor) |
| `musicstreamer/ui_qt/now_playing_panel.py` (modify — add `Signal`, `QLabel`, `_refresh_siblings`, `_on_sibling_link_activated`, `bind_station` hook) | panel (QWidget) | event-driven (signal-out from panel → MainWindow) | `musicstreamer/ui_qt/edit_station_dialog.py:397-411` (sibling label config) + `:1004-1051` (click handler) + `:576-610` (refresh body) | **exact (verbatim Phase 51 mirror, minus dirty-state branch)** |
| `musicstreamer/ui_qt/main_window.py` (modify — add `connect` line at :253, add `_on_sibling_activated` slot) | window (controller) | event-driven (signal → slot → reuse `_on_station_activated`) | `main_window.py:316-326` (`_on_station_activated`) + `:482-500` (`_on_navigate_to_sibling` shape) | **exact (one-line delegator)** |
| `tests/test_now_playing_panel.py` (extend — `FakeRepo.list_stations` / `get_station`, AA fixtures, panel-level tests) | test (pytest-qt) | request-response | `tests/test_main_window_integration.py:131-152` (`get_station`) + `tests/test_station_list_panel.py:34-56` (`list_stations`) + `tests/test_edit_station_dialog.py:783-806` (`_make_aa_station`) | **exact (copy method shapes verbatim)** |
| `tests/test_aa_siblings.py` (extend — `render_sibling_html` unit tests) | test (pytest, no Qt) | transform | `tests/test_aa_siblings.py:1-23` (existing `_mk` factory) + `tests/test_edit_station_dialog.py:870-949` (rendering test shape, port to free-function call) | **exact (mirror shape, swap dialog access for free-function call)** |
| `tests/test_main_window_integration.py` (extend — sibling-click → `Player.play(sibling)` integration) | test (pytest-qt integration) | event-driven | `tests/test_main_window_integration.py:920-993` (Phase 51 sibling-nav integration test, exact shape minus the "no playback" assertion which **inverts** for Phase 64) | **exact (mirror shape, invert SC #4 assertion)** |

**Single net-new pattern in Phase 64:** none. The renderer-promotion is a verbatim body lift; the panel is a Phase 51 dialog with the dirty-state branch deleted and the click action redirected.

---

## Pattern Assignments

### `musicstreamer/url_helpers.py` (utility, transform) — add `render_sibling_html`

**Analog:** `musicstreamer/ui_qt/edit_station_dialog.py:531-574` — the source body. The lift is **mechanical** (zero `self` references in the body; verified by reading the function).

**Existing module imports** (`url_helpers.py:1-12`):
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

**Required new import** — `url_helpers.py` does NOT currently `import html`. Add it after `import urllib.parse`:
```python
import html
import urllib.parse
```

**Verbatim function body to lift** (from `edit_station_dialog.py:531-574`, drop `self`):
```python
def render_sibling_html(
    siblings: list[tuple[str, int, str]],
    current_name: str,
) -> str:
    """Phase 51 / D-07, D-08 (promoted in Phase 64 / D-03 from
    EditStationDialog._render_sibling_html). Render the 'Also on: ...' HTML
    for an AA cross-network sibling label.

    siblings: from find_aa_siblings — already sorted in NETWORKS order.
    current_name: the bound station's display name. Drives D-08 link-text
                  format: same name -> network-only; different -> "Network — Name".
    Returns: 'Also on: <a href="sibling://{id}">{label}</a> • <a ...>...'

    Security: every interpolated station_name passes through
    html.escape(name, quote=True) (T-39-01 deviation mitigation). Network
    display names come from the NETWORKS compile-time constant and need no
    escape. The href payload is integer-only ('sibling://{id}') so it cannot
    carry injectable content.
    """
    name_for_slug = {n["slug"]: n["name"] for n in NETWORKS}
    parts: list[str] = []
    for slug, station_id, station_name in siblings:
        network_display = name_for_slug.get(slug, slug)
        if station_name == current_name:
            link_text = network_display
        else:
            safe_name = html.escape(station_name, quote=True)
            link_text = f"{network_display} — {safe_name}"  # U+2014 EM DASH
        parts.append(f'<a href="sibling://{station_id}">{link_text}</a>')
    return "Also on: " + " • ".join(parts)  # U+2022 BULLET
```

**Notes for the planner:**
- Preserve the **literal Unicode characters** `—` (U+2014) and `•` (U+2022) — do **not** substitute with `—` / `•` escapes. Phase 51's source uses the literal characters; round-trip-equality of the rendered HTML across both surfaces (D-03) requires byte parity.
- `NETWORKS` is **already imported** by `url_helpers.py:12`. No new import for that.
- Place the new function at the bottom of `url_helpers.py`, after `find_aa_siblings`. The `aa_*` helpers and the renderer form a cohesive section.

---

### `musicstreamer/ui_qt/edit_station_dialog.py` (dialog, request-response refactor) — delete renderer, update call site

**Analog:** self — extending the same file. Three surgical changes:

**Change 1: Update the import line** (`edit_station_dialog.py:53`) to add `render_sibling_html`:
```python
# BEFORE (line 53):
from musicstreamer.url_helpers import find_aa_siblings

# AFTER:
from musicstreamer.url_helpers import find_aa_siblings, render_sibling_html
```

**Change 2: Delete `_render_sibling_html`** (`edit_station_dialog.py:531-574` — the entire 44-line method block, including its docstring). Phase 51's existing tests in `tests/test_edit_station_dialog.py` reference this only through the public side effect `d._sibling_label.text()` (lines 868, 891, 909, 928, 946) — verified by grep, zero direct references to `_render_sibling_html`. The deletion is transparent.

**Change 3: Update the call site** (`edit_station_dialog.py:607-609` — inside `_refresh_siblings`):
```python
# BEFORE (lines 607-609):
self._sibling_label.setText(
    self._render_sibling_html(siblings, self._station.name)
)

# AFTER:
self._sibling_label.setText(
    render_sibling_html(siblings, self._station.name)
)
```

**Dead import cleanup** (verify before deletion via grep — only the renderer used these in the dialog):
```python
# BEFORE (lines 19, 48):
import html
from musicstreamer.aa_import import NETWORKS

# AFTER deletion of _render_sibling_html, verify no other code references
# `html.` (excluding docstring/comment text at ~lines 400-401) or `NETWORKS`
# in this file. If clean, drop both lines.
```

**Verification command for the planner before deleting imports:**
```
grep -n "html\.\|NETWORKS" musicstreamer/ui_qt/edit_station_dialog.py
```
Expect zero non-comment matches after `_render_sibling_html` is deleted.

---

### `musicstreamer/ui_qt/now_playing_panel.py` (panel, event-driven) — add Signal, QLabel, refresh, click handler

**Analog cluster:**
- `edit_station_dialog.py:397-411` — sibling label configuration block (Phase 51 D-05a verbatim mirror)
- `edit_station_dialog.py:576-610` — `_refresh_siblings` body (Phase 51 D-04/D-06 mirror)
- `edit_station_dialog.py:1004-1051` — `_on_sibling_link_activated` body (Phase 51 D-09/D-10/D-11; **strip the dirty-state branch** for the panel)
- `now_playing_panel.py:106-115` — existing Signal-declaration zone
- `now_playing_panel.py:155-171` — center-column layout slot
- `now_playing_panel.py:325-344` — `bind_station` extension point

**Imports pattern** (`now_playing_panel.py:30-48` existing; add `find_aa_siblings`, `render_sibling_html`):
```python
# EXISTING (line 30):
from PySide6.QtCore import QEvent, QSize, Qt, Signal

# NEW addition near the bottom of the imports block (after cover_art import,
# before models import — alphabetical-ish keeping musicstreamer.* together):
from musicstreamer.url_helpers import find_aa_siblings, render_sibling_html
```

**Signal declaration** (mirrors existing `edit_requested = Signal(object)` at line 112):
```python
# Add at line ~115, after stopped_by_user, before __init__:

# Emitted when the user clicks edit button — passes current Station to MainWindow.
edit_requested = Signal(object)

# Emitted when the user stops playback via the in-panel Stop button (not via OS media key).
stopped_by_user = Signal()

# Phase 64 / D-02: emitted when user clicks an 'Also on:' sibling link.
# Payload is the resolved sibling Station; MainWindow connects to
# _on_sibling_activated which delegates to _on_station_activated to switch
# active playback. Mirrors edit_requested in payload shape (Station via
# Signal(object)).
sibling_activated = Signal(object)
```

**Layout-insertion pattern** — between existing `name_provider_label` (line 161) and `icy_label` (line 164):
```python
# EXISTING (lines 154-161):
self.name_provider_label = QLabel("", self)
np_font = QFont()
np_font.setPointSize(9)
np_font.setWeight(QFont.Normal)
self.name_provider_label.setFont(np_font)
self.name_provider_label.setTextFormat(Qt.PlainText)
center.addWidget(self.name_provider_label)

# NEW Phase 64 / D-01, D-05, D-05a — insert here, before `# ICY title` block:
# Mirrors EditStationDialog._sibling_label config at edit_station_dialog.py:405-411.
# First QLabel in NowPlayingPanel to use Qt.RichText (deviation from T-39-01) —
# required for inline <a href> links. Mitigation: html.escape on every
# Station.name interpolation inside render_sibling_html. Hidden until populated
# (D-05) — QVBoxLayout reclaims zero vertical space for hidden children.
self._sibling_label = QLabel("", self)
self._sibling_label.setTextFormat(Qt.RichText)
self._sibling_label.setOpenExternalLinks(False)
self._sibling_label.setVisible(False)
self._sibling_label.linkActivated.connect(self._on_sibling_link_activated)
center.addWidget(self._sibling_label)

# EXISTING (line 164) — unchanged:
self.icy_label = QLabel("No station playing", self)
```

**Font choice (UI-SPEC locked):** **No `setFont` call.** The label inherits the Qt platform default, mirroring Phase 51's dialog version which also has no `setFont` (verified at `edit_station_dialog.py:405-411`). UI-SPEC §Typography records this as a locked decision: do **not** mirror `name_provider_label`'s 9pt construction.

**`bind_station` extension** (`now_playing_panel.py:325-344`) — append `_refresh_siblings()` call after `_populate_stream_picker(station)`:
```python
# EXISTING tail of bind_station (line 344):
self._populate_stream_picker(station)

# NEW Phase 64 / D-04: re-derive 'Also on:' line for the newly bound station.
# This is the ONLY call site for _refresh_siblings — D-04 invariant.
self._refresh_siblings()
```

**`_refresh_siblings` body** — verbatim mirror of Phase 51 dialog version at `edit_station_dialog.py:576-610`, with two adjustments: (a) read URL from `self._station.streams[0].url` instead of `self.url_edit.text().strip()` (D-06), (b) add the `self._station is None` guard at the top (the dialog cannot be constructed without a station; the panel can be in an unbound state):
```python
def _refresh_siblings(self) -> None:
    """Phase 64 / D-04, D-05: refresh the 'Also on:' label for the bound station.

    Reads self._station.streams[0].url, scans repo.list_stations() for AA
    siblings on different networks, then either populates _sibling_label
    with HTML or hides it entirely (zero vertical space when no siblings).

    Hidden-when-empty (D-05) covers four cases (mirrors Phase 51 dialog):
      1. self._station is None (panel never bound).
      2. self._station.streams is empty (defensive — find_aa_siblings
         returns [] for empty current_first_url anyway).
      3. Bound station is non-AA -> find_aa_siblings returns [].
      4. AA station with a key but no other AA stations on other networks
         share the key -> returns [].
    """
    if self._station is None or not self._station.streams:
        self._sibling_label.setVisible(False)
        self._sibling_label.setText("")
        return
    current_url = self._station.streams[0].url
    all_stations = self._repo.list_stations()
    siblings = find_aa_siblings(
        stations=all_stations,
        current_station_id=self._station.id,
        current_first_url=current_url,
    )
    if not siblings:
        self._sibling_label.setVisible(False)
        self._sibling_label.setText("")
        return
    self._sibling_label.setText(
        render_sibling_html(siblings, self._station.name)
    )
    self._sibling_label.setVisible(True)
```

**`_on_sibling_link_activated` body** — Phase 51 dialog version at `edit_station_dialog.py:1004-1051` is the source; **strip the entire dirty-state confirm branch** (lines 1028-1051: `_is_dirty()`, `QMessageBox.question`, Save / Discard / Cancel dispatch). The panel has no editable form. Add D-08 defense-in-depth guard and dual-shape `repo.get_station` exception handling (RESEARCH Pitfall #2):
```python
def _on_sibling_link_activated(self, href: str) -> None:
    """Phase 64 / D-02, D-08: parse the sibling href, look up the Station,
    emit sibling_activated.

    Mirrors EditStationDialog._on_sibling_link_activated (lines 1004-1051) but
    has no dirty-state confirm path — the panel has no editable form. The
    surface contract is 'user clicked a sibling -> switch playback to it',
    not 'user clicked a sibling -> navigate to its editor'.

    Dual-shape repo.get_station handling (RESEARCH Pitfall #2):
      - Production Repo.get_station raises ValueError on miss (repo.py:271).
      - MainWindow.FakeRepo.get_station returns None
        (tests/test_main_window_integration.py:152).
    Wrap in try/except Exception + check `is None` to be safe in both shapes.
    Qt slots-never-raise: bail silently on any failure path.
    """
    prefix = "sibling://"
    if not href.startswith(prefix):
        return
    try:
        sibling_id = int(href[len(prefix):])
    except ValueError:
        return
    # D-08 defense-in-depth: silent no-op if no station bound, or if the
    # sibling id matches the bound station (find_aa_siblings excludes self
    # at url_helpers.py:122, but rendering staleness could theoretically
    # allow a stale link).
    if self._station is None or self._station.id == sibling_id:
        return
    try:
        sibling = self._repo.get_station(sibling_id)
    except Exception:
        return
    if sibling is None:
        return
    self.sibling_activated.emit(sibling)
```

---

### `musicstreamer/ui_qt/main_window.py` (window, event-driven) — connect line + delegating slot

**Analog:** `main_window.py:316-326` (`_on_station_activated`) is the canonical "user picked a station" side-effect block. The new slot **delegates** to it (D-02 default).

**Existing connect-zone pattern** (`main_window.py:248-256`):
```python
# Plan 39: edit button → dialog launch
self.now_playing.edit_requested.connect(self._on_edit_requested)
# Right-click edit from station list
self.station_panel.edit_requested.connect(self._on_edit_requested)
# Phase 999.1 D-02: "+" button in panel header shares MainWindow slot
self.station_panel.new_station_requested.connect(self._on_new_station_clicked)
```

**New connect line** — insert immediately after `self.now_playing.edit_requested.connect(self._on_edit_requested)` at line 252 (D-02a + RESEARCH Pitfall #4: must land **after** `self.now_playing` is constructed, alongside related `now_playing` connects):
```python
# Plan 39: edit button → dialog launch
self.now_playing.edit_requested.connect(self._on_edit_requested)
# Phase 64 / D-02a: 'Also on:' sibling click → switch playback (bound-method per QA-05).
self.now_playing.sibling_activated.connect(self._on_sibling_activated)
# Right-click edit from station list
self.station_panel.edit_requested.connect(self._on_edit_requested)
```

**Existing `_on_station_activated` reference** (`main_window.py:316-326`) — the canonical side-effect block:
```python
def _on_station_activated(self, station: Station) -> None:
    """Called when the user selects a station in StationListPanel."""
    self.now_playing.bind_station(station)
    self._player.play(station)
    self._repo.update_last_played(station.id)
    self.station_panel.refresh_recent()  # Phase 50 / BUG-01: live recent-list update (D-01, D-04)
    self.now_playing.on_playing_state_changed(True)
    self.show_toast("Connecting…")  # UI-SPEC copywriting: U+2026
    # Seed the OS media session with station name before ICY title arrives (D-05)
    self._media_keys.publish_metadata(station, "", self.now_playing.current_cover_pixmap())
    self._media_keys.set_playback_state("playing")
```

**New delegating slot** — one-line body (mirrors the Phase 51 `_on_navigate_to_sibling` shape at `main_window.py:482-500`, but **inverts the D-10 invariant**: this slot DOES change playback, deliberately):
```python
def _on_sibling_activated(self, station: Station) -> None:
    """Phase 64 / D-02: user clicked an 'Also on:' link in NowPlayingPanel.

    Delegate to _on_station_activated so the canonical 'user picked a
    station' side-effect block (bind_station, player.play, update_last_played,
    refresh_recent, toast, media-keys publish + state) fires identically
    regardless of where the activation came from (station list vs sibling).

    NOTE: unlike Phase 51's _on_navigate_to_sibling (lines 482-500) — which
    re-opens the EditStationDialog and explicitly avoids touching playback —
    this slot DOES change playback. That divergence is the entire point of
    Phase 64 (ROADMAP SC #2).
    """
    self._on_station_activated(station)
```

Place adjacent to `_on_navigate_to_sibling` at lines 482-500 (or near `_on_station_activated` at 316 — planner picks based on what reads better in the file's existing slot ordering).

---

### `tests/test_now_playing_panel.py` (test, pytest-qt) — extend FakeRepo + AA fixtures + panel-level tests

**Analog cluster:**
- `tests/test_main_window_integration.py:131-152` — `FakeRepo.get_station(station_id)` shape (returns Station from `_stations` list, falls back to `None` on miss; **for Phase 64 the panel-test FakeRepo should raise `ValueError`** to match production semantics — RESEARCH Pitfall #2)
- `tests/test_station_list_panel.py:34-44` — minimal `FakeRepo.__init__(stations, ...)` + `list_stations()` shape
- `tests/test_edit_station_dialog.py:783-806` — `_make_aa_station(station_id, name, url)` factory (verbatim copy)
- `tests/test_edit_station_dialog.py:870-949` — sibling-rendering test shapes (`isHidden()`, `text()` assertions)
- `tests/test_edit_station_dialog.py:958-973` — signal-emission test shape with `qtbot.waitSignal`

**Existing FakeRepo** (`tests/test_now_playing_panel.py:65-92`) — extend with two methods:
```python
class FakeRepo:
    def __init__(self, settings: Optional[dict] = None,
                 stations: Optional[list] = None) -> None:  # NEW: stations kwarg
        self._settings = dict(settings or {})
        self._favorites: list = []
        self._stations: list = list(stations or [])  # NEW

    # ... existing methods ...

    def list_streams(self, station_id: int) -> list:
        return []

    # NEW Phase 64 — Wave 0 gap fill (RESEARCH Pitfall #1):
    def list_stations(self) -> list:
        return list(self._stations)

    def get_station(self, station_id: int):
        """Match production Repo.get_station semantics (repo.py:271):
        raise ValueError on miss. Panel handler must wrap in try/except."""
        for s in self._stations:
            if s.id == station_id:
                return s
        raise ValueError("Station not found")
```

**`_make_aa_station` factory** — copy verbatim from `tests/test_edit_station_dialog.py:783-806`:
```python
def _make_aa_station(station_id, name, url):
    """Factory: a minimal Station with one stream at `url`.

    Used by sibling-label tests below to construct AA-flavored stations
    whose first stream URL drives find_aa_siblings.

    Mirrors tests/test_edit_station_dialog.py:783-806 (Phase 51 fixture).
    """
    return Station(
        id=station_id,
        name=name,
        provider_id=1,
        provider_name="DI.fm",
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[
            StationStream(
                id=station_id * 10,
                station_id=station_id,
                url=url,
                position=1,
            )
        ],
    )
```

**Visibility test shape** — port from `test_edit_station_dialog.py:880-895`:
```python
def test_sibling_label_visible_for_aa_station_with_siblings(qtbot):
    """Phase 64 / SC #1: bound AA station with cross-network sibling ->
    _sibling_label visible with 'Also on:' + a network <a> link."""
    di = _make_aa_station(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    zr = _make_aa_station(2, "Ambient", "http://prem1.zenradio.com/zrambient?listen_key=abc")
    repo = FakeRepo({"volume": "80"}, stations=[di, zr])
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.bind_station(di)
    # isHidden() reflects setVisible() state directly without windowing-system
    # parent-shown dependency (per test_edit_station_dialog.py:846-849 rationale).
    assert panel._sibling_label.isHidden() is False
    text = panel._sibling_label.text()
    assert "Also on:" in text
    assert 'href="sibling://2"' in text
    assert "ZenRadio" in text
```

**Hidden-when-empty test** — port from `test_edit_station_dialog.py:843-868`:
```python
def test_sibling_label_hidden_for_non_aa_station(qtbot):
    """Phase 64 / D-05 case 3: non-AA URL -> _sibling_label hidden."""
    yt = _make_aa_station(1, "Whatever", "https://www.youtube.com/watch?v=xyz")
    repo = FakeRepo({"volume": "80"}, stations=[yt])
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.bind_station(yt)
    assert panel._sibling_label.isHidden() is True
```

**Signal-emission test** — port from `test_edit_station_dialog.py:958-973`:
```python
def test_sibling_link_emits_sibling_activated_with_station_payload(qtbot):
    """Phase 64 / SC #2: clicking a sibling link emits sibling_activated(Station)
    with the resolved sibling Station — payload is Station, not int id (D-02)."""
    di = _make_aa_station(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    zr = _make_aa_station(2, "Ambient", "http://prem1.zenradio.com/zrambient?listen_key=abc")
    repo = FakeRepo({"volume": "80"}, stations=[di, zr])
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.bind_station(di)
    with qtbot.waitSignal(panel.sibling_activated, timeout=1000) as blocker:
        panel._on_sibling_link_activated("sibling://2")
    assert blocker.args == [zr]  # Station object payload, not just id
```

**D-08 self-id guard test:**
```python
def test_sibling_link_handler_no_op_when_id_matches_bound_station(qtbot):
    """Phase 64 / D-08: defense-in-depth — sibling://{self.id} must be a no-op
    even though find_aa_siblings should never produce such a link."""
    di = _make_aa_station(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    repo = FakeRepo({"volume": "80"}, stations=[di])
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    panel.bind_station(di)
    emitted: list = []
    panel.sibling_activated.connect(lambda s: emitted.append(s))
    panel._on_sibling_link_activated("sibling://1")  # bound station's own id
    assert emitted == []
```

**Full test list to add** (RESEARCH §Validation Architecture):
- `test_sibling_label_visible_for_aa_station_with_siblings` — SC #1
- `test_sibling_label_hidden_for_non_aa_station` — D-05 case 3
- `test_sibling_label_hidden_when_no_siblings` — D-05 case 4
- `test_sibling_label_hidden_when_no_station` — D-05 case 1 (bind never called)
- `test_sibling_label_excludes_self` — SC #5 (re-state Phase 51 contract through panel)
- `test_sibling_link_emits_sibling_activated_with_station_payload` — SC #2
- `test_sibling_link_handler_no_op_when_id_matches_bound_station` — D-08 self-id guard
- `test_sibling_link_handler_guards` — malformed href, non-int payload, repo raises, repo returns None (Pitfall #2)
- `test_refresh_siblings_runs_once_per_bind` — D-04 invariant (spy)
- `test_panel_does_not_reimplement_aa_detection` — SC #4 (negative spy on imports)

---

### `tests/test_aa_siblings.py` (test, pure unit) — extend with `render_sibling_html` tests

**Analog cluster:**
- `tests/test_aa_siblings.py:1-23` — existing module shape, `_mk` factory (already in place)
- `tests/test_edit_station_dialog.py:870-949` — Phase 51's renderer-output assertions (port shape, swap dialog access for free-function call)

**Existing pattern** (`tests/test_aa_siblings.py:1-30`) — reuse the `_mk` factory; add `render_sibling_html` to imports:
```python
# EXISTING (line 9):
from musicstreamer.url_helpers import find_aa_siblings

# AFTER:
from musicstreamer.url_helpers import find_aa_siblings, render_sibling_html
```

**Renderer test shape** — pure data in / data out, no Qt, no fixtures:
```python
def test_render_sibling_html_basic_link():
    """Phase 64 / D-03: single sibling renders 'Also on: <a href="sibling://2">ZenRadio</a>'."""
    siblings = [("zenradio", 2, "Ambient")]
    out = render_sibling_html(siblings, current_name="Ambient")
    assert out == 'Also on: <a href="sibling://2">ZenRadio</a>'


def test_render_sibling_html_uses_em_dash_when_names_differ():
    """Phase 64 / D-03 / Phase 51 D-08: name mismatch -> 'Network — Name' with U+2014."""
    siblings = [("zenradio", 2, "Ambient (Sleep)")]
    out = render_sibling_html(siblings, current_name="Ambient")
    assert "ZenRadio — Ambient (Sleep)" in out
    assert "—" in out  # literal U+2014 EM DASH


def test_render_sibling_html_html_escapes_station_name():
    """T-39-01 deviation mitigation (preserved by D-03): name with HTML
    metachars must be escaped — <script> rendered as &lt;script&gt;."""
    siblings = [("zenradio", 2, "<script>alert(1)</script>")]
    out = render_sibling_html(siblings, current_name="Ambient")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_render_sibling_html_uses_bullet_separator_for_multiple():
    """Phase 64 / D-03 / Phase 51 D-07: multiple siblings joined with ' • ' (U+2022)."""
    siblings = [("jazzradio", 2, "Ambient"), ("zenradio", 3, "Ambient")]
    out = render_sibling_html(siblings, current_name="Ambient")
    assert " • " in out  # literal U+2022 BULLET surrounded by spaces
    assert out.count("<a ") == 2
```

**Empty-list note for the planner:** if Phase 51's contract for `[]` produces `"Also on: "` (literal trailing space), Phase 64 inherits that. The current panel/dialog `_refresh_siblings` never calls the renderer with `[]` (returns early on empty list), so the empty-list output is **not load-bearing** — a test asserting `render_sibling_html([], "X") == "Also on: "` is documentation, not a behavioral guarantee. Planner discretion on whether to assert it.

---

### `tests/test_main_window_integration.py` (test, pytest-qt integration) — sibling click → `Player.play(sibling)`

**Analog:** `tests/test_main_window_integration.py:920-1000` — Phase 51's full sibling-navigation integration test. Phase 64's version is structurally identical with **two inversions:**

1. **Driver:** Phase 51 calls `w._on_edit_requested(di_station)` (opens dialog → emits `navigate_to_sibling`). Phase 64 calls `w.now_playing.bind_station(di_station)` then `w.now_playing._on_sibling_link_activated("sibling://2")`.
2. **SC #4 assertion inverts:** Phase 51 asserts `fake_player.play_calls == []` ("navigation does NOT touch playback", line 990). Phase 64 asserts `fake_player.play_calls == [zen_station]` ("sibling click DOES switch playback", per ROADMAP SC #2).

**Phase 51's existing test** (lines 920-993) — read in full as the template. Key excerpt for the planner's `<read_first>`:
```python
# tests/test_main_window_integration.py:935-945 (Phase 51 setup that Phase 64 reuses):
monkeypatch.setattr(type(fake_repo), "list_stations", lambda self: [di_station, zen_station])
monkeypatch.setattr(
    type(fake_repo), "get_station",
    lambda self, sid: {1: di_station, 2: zen_station}.get(sid),
)
monkeypatch.setattr(
    type(fake_repo), "list_streams",
    lambda self, sid: {1: di_station.streams, 2: zen_station.streams}.get(sid, []),
)
```

**Phase 64 test sketch** (planner refines):
```python
def test_sibling_click_switches_playback_via_main_window(qtbot, fake_player, fake_repo, monkeypatch):
    """Phase 64 / SC #2: clicking an 'Also on:' link on NowPlayingPanel
    triggers Player.play(sibling) and updates last_played(sibling.id)."""
    # ... (di_station + zen_station construction same as line 905-928) ...
    monkeypatch.setattr(type(fake_repo), "list_stations", lambda self: [di_station, zen_station])
    monkeypatch.setattr(
        type(fake_repo), "get_station",
        lambda self, sid: {1: di_station, 2: zen_station}.get(sid),
    )
    monkeypatch.setattr(
        type(fake_repo), "list_streams",
        lambda self, sid: {1: di_station.streams, 2: zen_station.streams}.get(sid, []),
    )

    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    # Bind to DI.fm Ambient first (simulates the user activating it).
    w._on_station_activated(di_station)
    # Reset spies to isolate the sibling click's effects.
    fake_player.play_calls.clear()
    fake_repo._last_played_ids = []

    # Drive the click handler directly — the panel's render path has been
    # exercised already (panel-level test asserts text content).
    w.now_playing._on_sibling_link_activated("sibling://2")

    # Phase 64 / SC #2 (inverts Phase 51 SC #4 assertion):
    assert fake_player.play_calls == [zen_station]
    assert fake_repo._last_played_ids == [2]
    # Bound station is now the sibling (delegates through bind_station).
    assert w.now_playing._station is zen_station
```

`fake_repo._last_played_ids` is populated by `FakeRepo.update_last_played` at `tests/test_main_window_integration.py:97-99`.

---

## Shared Patterns

### Bound-method signal connections (QA-05)
**Source:** `musicstreamer/ui_qt/edit_station_dialog.py:393-395, 410`; `musicstreamer/ui_qt/main_window.py:230-260`
**Apply to:** every new connection introduced by Phase 64 — `_sibling_label.linkActivated` and `now_playing.sibling_activated`. No self-capturing lambdas.

```python
# CORRECT — bound-method:
self._sibling_label.linkActivated.connect(self._on_sibling_link_activated)
self.now_playing.sibling_activated.connect(self._on_sibling_activated)

# WRONG — self-capturing lambda (QA-05 violation):
self._sibling_label.linkActivated.connect(lambda h: self._handle(h))  # NO
```

### `Qt.RichText` deviation (T-39-01) — mitigated by `html.escape` in renderer
**Source:** `edit_station_dialog.py:397-411` (existing Phase 51 deviation; Phase 64 mirrors it on the panel).
**Apply to:** the new `self._sibling_label` only. Every other QLabel in NowPlayingPanel keeps `setTextFormat(Qt.PlainText)` (`now_playing_panel.py:160, 170`).

```python
self._sibling_label.setTextFormat(Qt.RichText)              # T-39-01 deviation
self._sibling_label.setOpenExternalLinks(False)             # intra-app navigation only
```

**Mitigation requirement:** all station-name interpolation passes through `html.escape(name, quote=True)` inside `render_sibling_html`. Network display names are compile-time `NETWORKS` constants and need no escape. The href payload is integer-only (`sibling://{id}`).

### `__future__` annotations + absolute imports
**Source:** every modified module (`url_helpers.py:8`, `now_playing_panel.py:26`, `main_window.py:19`, `edit_station_dialog.py:17`).
**Apply to:** no new modules in Phase 64 — pure modifications. The convention is already in place; do not remove the `from __future__ import annotations` line from any modified file.

### Single-source AA detection (SC #4)
**Source:** `musicstreamer/url_helpers.py:86-146` (`find_aa_siblings`).
**Apply to:** all surfaces that need sibling detection. The new panel imports **only** `find_aa_siblings` and `render_sibling_html` — never `_is_aa_url`, `_aa_slug_from_url`, `_aa_channel_key_from_url`, or `NETWORKS` directly. SC #4 negative-spy test verifies this.

### Slot-never-raises (Qt UI contract)
**Source:** `_LogoFetchWorker.run` exception swallow at `edit_station_dialog.py:73-120` (broad try around the whole worker body); `_on_navigate_to_sibling` `is None` check at `main_window.py:498`.
**Apply to:** `NowPlayingPanel._on_sibling_link_activated` — wrap `self._repo.get_station(sibling_id)` in `try/except Exception` to absorb both production `ValueError` and test-double `None`-return shapes (RESEARCH Pitfall #2). Bare `except Exception` is the locked choice; do not narrow to `except ValueError` (test-double could return `None`, which then crashes on `is None` if not also handled).

---

## No Analog Found

| Need | Why no analog | Recommended approach |
|------|---------------|----------------------|
| (none) | Every Phase 64 behavior has a Phase 51 analog. The renderer is a verbatim body lift; the panel mirrors Phase 51 dialog config and click-handler shape with the dirty-state branch removed; the MainWindow slot mirrors `_on_navigate_to_sibling` shape with the playback-touching action **inverted** (deliberate per ROADMAP SC #2). | n/a — no novel pattern needed. |

---

## Metadata

**Analog search scope:**
- `musicstreamer/url_helpers.py` (full read — 147 lines)
- `musicstreamer/ui_qt/edit_station_dialog.py` (targeted reads at lines 1-80, 390-440, 525-615, 1000-1060)
- `musicstreamer/ui_qt/now_playing_panel.py` (targeted reads at lines 1-50, 90-180, 320-360)
- `musicstreamer/ui_qt/main_window.py` (targeted reads at lines 240-330, 480-505)
- `musicstreamer/repo.py` (lines 220-285 — `list_stations`, `get_station` signatures)
- `tests/test_now_playing_panel.py` (lines 1-120 — existing FakeRepo + fixtures)
- `tests/test_main_window_integration.py` (lines 77-160, 920-1001 — FakeRepo + Phase 51 sibling integration test)
- `tests/test_station_list_panel.py` (lines 30-90 — minimal FakeRepo with `list_stations`)
- `tests/test_aa_siblings.py` (lines 1-65 — module shape + existing detection tests)
- `tests/test_edit_station_dialog.py` (lines 775-1110 — Phase 51 sibling fixtures + render tests + click-handler tests)

**Files scanned (read in full or substantial portion):** 6 source files, 5 test files
**Pattern extraction date:** 2026-05-01
