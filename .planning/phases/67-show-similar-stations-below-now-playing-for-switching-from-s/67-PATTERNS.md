# Phase 67: Show similar stations below now playing - Pattern Map

**Mapped:** 2026-05-09
**Files analyzed:** 6 (2 modified production, 1 modified production, 1 new test, 2 modified tests)
**Analogs found:** 6 / 6 (100% coverage — Phase 67 is pure composition of landed patterns)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/url_helpers.py` (modify) | utility (pure helper module) | transform | `musicstreamer/url_helpers.py:168-263` (`find_aa_siblings` + `render_sibling_html`) | exact — same module, mirror placement |
| `musicstreamer/ui_qt/now_playing_panel.py` (modify) | component (Qt widget panel) | event-driven (Signal-out) + request-response (data render) | `musicstreamer/ui_qt/now_playing_panel.py:200, 253-271, 645-647, 893-975` (Phase 64 sibling region + Phase 47.1 `set_stats_visible`) | exact — same file, sibling region |
| `musicstreamer/ui_qt/main_window.py` (modify) | controller (Qt window wiring) | event-driven (Signal in, Action toggle) | `musicstreamer/ui_qt/main_window.py:204-210, 322-324, 338, 430-441, 539-542` (Phase 47.1 stats action + Phase 64 sibling delegate) | exact — same file, peer regions |
| `tests/test_pick_similar_stations.py` (create) | test (pure-helper unit) | request-response (factory in / assertion out) | `tests/test_aa_siblings.py:1-231` | exact — same test shape, no qtbot |
| `tests/test_now_playing_panel.py` (modify) | test (qtbot widget) | event-driven (Signal capture) | `tests/test_now_playing_panel.py:770-898` (Phase 64 sibling section) | exact — same file, mirror section |
| `tests/test_main_window_integration.py` (modify) | test (qtbot integration) | event-driven (QAction trigger + signal) | `tests/test_main_window_integration.py:564-630, 1049-1126` (Phase 47.1 stats + Phase 64 sibling integration) | exact — same file, peer sections |

## Pattern Assignments

### `musicstreamer/url_helpers.py` (modify) — utility, transform

**Analog:** `musicstreamer/url_helpers.py:168-263` (`find_aa_siblings` + `render_sibling_html` — same file, additive)

**Imports pattern** (lines 1-16 — already in file, additive imports may be needed):
```python
"""Pure URL classification helpers for stream sources.

Extracted from musicstreamer/ui/edit_dialog.py during the Phase 36 GTK cutover
so that non-UI tests (test_aa_url_detection, test_yt_thumbnail) survive the
deletion of the ui/ tree. These helpers have zero GTK/Qt coupling — they are
pure string and regex manipulation over URL literals.
"""
from __future__ import annotations

import html
import logging
import urllib.parse

from musicstreamer.aa_import import NETWORKS
```

Phase 67 ADDS at the top of the module:
```python
import random
from musicstreamer.models import Station
from musicstreamer.filter_utils import normalize_tags
# find_aa_siblings already in this module — no import needed
```

**Pure-helper signature pattern** (lines 168-187 — `find_aa_siblings` docstring shape):
```python
def find_aa_siblings(
    stations: list,
    current_station_id: int,
    current_first_url: str,
) -> list[tuple[str, int, str]]:
    """Phase 51 / BUG-02: return AA stations on other networks sharing the same channel key.

    Returns a list of (network_slug, station_id, station_name) tuples.
    Excludes the current station by id. Excludes stations whose first stream
    URL is non-AA, has no slug, has no derivable channel key, or whose
    streams list is empty. Returns [] if the current URL is non-AA or has
    no channel key (D-04: callers may rely on emptiness as the "hide section"
    signal).

    ...

    Pure function — no Qt, no DB access, no logging. Match the
    url_helpers.py module convention.
    """
```

Phase 67 ADDS `pick_similar_stations(stations, current_station, *, sample_size=5, rng=None)` colocated next to `find_aa_siblings` (per RESEARCH §"Pattern 3" + Don't Hand-Roll table). The "Pure function — no Qt, no DB access, no logging" docstring boilerplate is mandatory.

**Self-exclusion + per-station filter loop pattern** (lines 204-228):
```python
siblings: list[tuple[int, str, int, str]] = []  # (sort_index, slug, id, name)
for st in stations:
    # Exclude self by id (D-03).
    if st.id == current_station_id:
        continue
    # Exclude stations with no streams (defensive — Repo always populates,
    # but tests construct Station(streams=[]) directly).
    if not st.streams:
        continue
    cand_url = st.streams[0].url
    # D-03: candidate must be AA, have a slug, and have a derivable key.
    if not _is_aa_url(cand_url):
        continue
    # ... (filter chain)
    siblings.append(...)
```

Phase 67 mirrors this filter-chain shape for both pools. T-04 exclusions become `excluded_ids: set[int]` (self id + AA-sibling ids returned by `find_aa_siblings(...)`); the per-pool loop appends to `same_provider_pool` and `same_tag_pool` lists. No sets-as-population (RESEARCH Pitfall 2).

**Renderer pattern** (lines 234-263 — `render_sibling_html`):
```python
def render_sibling_html(
    siblings: list[tuple[str, int, str]],
    current_name: str,
) -> str:
    """Phase 51 / D-07, D-08 (promoted in Phase 64 / D-03 from
    EditStationDialog._render_sibling_html). Render the 'Also on: ...' HTML
    for an AA cross-network sibling label.
    ...
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

Phase 67 ADDS `render_similar_html(stations, *, show_provider: bool, href_prefix: str = "similar://") -> str` mirroring this security envelope. **Critical difference (RESEARCH Pitfall 7):** Phase 67 escapes BOTH `Station.name` AND `Station.provider_name`. Use `<br>` join (vertical, per D-03) instead of ` • ` (Phase 64's inline format). Format per row:
- `show_provider=False` → `f'<a href="similar://{s.id}">{html.escape(s.name, quote=True)}</a>'`
- `show_provider=True` → `f'<a href="similar://{s.id}">{html.escape(s.name, quote=True)} ({html.escape(s.provider_name or "", quote=True)})</a>'`

**Where to insert in file:** After the existing `render_sibling_html` (line 263), in the same module-end region. Both new functions land in `musicstreamer/url_helpers.py`.

---

### `musicstreamer/ui_qt/now_playing_panel.py` (modify) — component, event-driven + request-response

**Analog A:** `musicstreamer/ui_qt/now_playing_panel.py:195-200` (Signal declaration adjacent to existing signals)

**Signal declaration pattern**:
```python
# Phase 64 / D-02: emitted when user clicks an 'Also on:' sibling link.
# Payload is the resolved sibling Station; MainWindow connects to
# _on_sibling_activated which delegates to _on_station_activated to switch
# active playback. Mirrors edit_requested in payload shape (Station via
# Signal(object)).
sibling_activated = Signal(object)
```

Phase 67 ADDS adjacent on the next line:
```python
# Phase 67 / I-02: emitted when user clicks a Similar Stations link
# (Same provider OR Same tag). Payload is the resolved Station; MainWindow
# connects to _on_similar_activated which delegates to _on_station_activated.
# Mirrors sibling_activated in payload shape (Station via Signal(object)) —
# distinct signal so each surface tests independently and the href routing
# stays unambiguous (RESEARCH Pitfall 8).
similar_activated = Signal(object)
```

---

**Analog B:** `musicstreamer/ui_qt/now_playing_panel.py:253-271` (Phase 64 sibling label construction)

**RichText QLabel construction pattern** (lines 253-271):
```python
# Phase 64 / D-01, D-05, D-05a: cross-network "Also on:" sibling line.
# Mirrors EditStationDialog._sibling_label config at edit_station_dialog.py:405-411.
# First QLabel in NowPlayingPanel to use Qt.RichText (deviation from
# T-39-01 PlainText convention) -- required for inline <a href> links.
# Mitigation: html.escape on every Station.name interpolation inside
# render_sibling_html (Plan 01, url_helpers.py). Network display names
# come from the NETWORKS compile-time constant; the href payload is
# integer-only ("sibling://{id}") so it cannot carry injectable content.
# Hidden until populated (D-05) -- QVBoxLayout reclaims zero vertical
# space for hidden children.
# UI-SPEC font lock: NO setFont call (inherits Qt platform default,
# parity with Phase 51 dialog version).
self._sibling_label = QLabel("", self)
self._sibling_label.setTextFormat(Qt.RichText)
self._sibling_label.setOpenExternalLinks(False)
self._sibling_label.setVisible(False)
# QA-05: bound-method connection (no self-capturing lambda).
self._sibling_label.linkActivated.connect(self._on_sibling_link_activated)
center.addWidget(self._sibling_label)
```

Phase 67 mirrors this 4-line config (`setTextFormat(Qt.RichText)`, `setOpenExternalLinks(False)`, `setVisible(False)`, `linkActivated.connect(...)` bound-method) for BOTH `_same_provider_links_label` and `_same_tag_links_label`. Both share the same `_on_similar_link_activated` slot (one bound-method connection per label). **Construction location:** after the controls block in the center column (per D-01, locked at the bottom of `center: QVBoxLayout`).

---

**Analog C:** `musicstreamer/ui_qt/station_list_panel.py:191-198, 266-267, 516-519` (collapsible flat-button header)

**Collapsible header construction pattern** (lines 191-198):
```python
# Filter strip toggle button
self._filter_toggle = QPushButton("▶ Filters", stations_page)  # ▶ Filters
self._filter_toggle.setFlat(True)
self._filter_toggle.setFixedHeight(24)
self._filter_toggle.setStyleSheet(
    "QPushButton { text-align: left; padding-left: 16px; color: palette(highlight); }"
)
self._filter_toggle.clicked.connect(self._toggle_filter_strip)
sp_layout.addWidget(self._filter_toggle)
```

**Collapsible body insertion pattern** (lines 266-267):
```python
# Start collapsed
self._filter_strip.setVisible(False)
sp_layout.addWidget(self._filter_strip)
```

**Toggle slot pattern** (lines 516-519):
```python
def _toggle_filter_strip(self) -> None:
    visible = not self._filter_strip.isVisible()
    self._filter_strip.setVisible(visible)
    self._filter_toggle.setText(("▼ Filters" if visible else "▶ Filters"))
```

Phase 67 ADDS a similar header + body pair for the Similar Stations section. **Differences:**
- Use `▾`/`▸` (U+25BE / U+25B8 small triangles, per CONTEXT.md S-03) instead of `▼`/`▶` (codebase precedent's full triangles) for visual softness. RESEARCH §"Open Question 2" gives planner discretion either way.
- Collapse slot ALSO persists state: `self._repo.set_setting('similar_stations_collapsed', '0' if visible else '1')` at the end of the toggle method.
- The header row uses `QHBoxLayout(collapse_btn + stretch + refresh_btn)` (the refresh button is unique to Phase 67, not in the filter-strip analog).
- Initial state read on `__init__`: `self._repo.get_setting('similar_stations_collapsed', '0')` (default `'0'` = expanded). Apply `_similar_body.setVisible(...)` and update glyph accordingly.

---

**Analog D:** `musicstreamer/ui_qt/now_playing_panel.py:645-647` (Phase 47.1 `set_stats_visible` public method)

**Public visibility-setter pattern** (lines 645-647):
```python
def set_stats_visible(self, visible: bool) -> None:
    """Toggle the stats-for-nerds wrapper visibility (D-07). Phase 47.1."""
    self._stats_widget.setVisible(bool(visible))
```

Phase 67 ADDS the parallel public method:
```python
def set_similar_visible(self, visible: bool) -> None:
    """Phase 67 / S-02, M-01: toggle Similar Stations container visibility
    (master toggle from MainWindow's hamburger menu)."""
    self._similar_container.setVisible(bool(visible))
```

---

**Analog E:** `musicstreamer/ui_qt/now_playing_panel.py:528-532` (`bind_station` refresh-trigger insertion)

**Bind-time refresh trigger pattern** (lines 528-532):
```python
self._populate_stream_picker(station)
# Phase 64 / D-04: re-derive 'Also on:' line for the newly bound station.
# This is the ONLY call site for _refresh_siblings -- D-04 invariant
# (locked by test_refresh_siblings_runs_once_per_bind_station_call).
self._refresh_siblings()
```

Phase 67 ADDS on the next line (per RESEARCH §"Pattern 3" / R-02):
```python
# Phase 67 / R-02: re-derive Similar Stations for the newly bound station
# IF cache miss; reuse cached sample if hit. ONLY call site outside
# _on_refresh_similar_clicked.
self._refresh_similar_stations()
```

---

**Analog F:** `musicstreamer/ui_qt/now_playing_panel.py:893-975` (Phase 64 `_refresh_siblings` + `_on_sibling_link_activated`)

**Refresh-method pattern** (lines 893-939) — defense-in-depth + hidden-when-empty:
```python
def _refresh_siblings(self) -> None:
    """Phase 64 / D-04, D-05: refresh the 'Also on:' label for the bound station.
    ...
    """
    if self._station is None or not self._station.streams:
        self._sibling_label.setVisible(False)
        self._sibling_label.setText("")
        return
    current_url = self._station.streams[0].url
    # Defense-in-depth (REVIEW WR-01): repo.list_stations() can in principle
    # raise on transient DB failures; this method runs from bind_station()
    # which is on the Qt slot path. Slots-never-raise -- on failure, hide
    # the label and bail silently.
    try:
        all_stations = self._repo.list_stations()
    except Exception:
        self._sibling_label.setVisible(False)
        self._sibling_label.setText("")
        return
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

Phase 67's `_refresh_similar_stations()` mirrors this shape with these additions:
1. **Cache check first**: `if self._station.id in self._similar_cache: same_provider, same_tag = self._similar_cache[self._station.id]; ... render; return`
2. **Try/except around `repo.list_stations()`** identical to above (slots-never-raise).
3. **Empty-streams handling**: per RESEARCH Pitfall 11, do NOT bail when `not self._station.streams`. Skip ONLY the AA-sibling exclusion (`find_aa_siblings` requires `current_first_url`); continue with same-provider + same-tag pool derivation. The pure helper handles this gracefully via `if current_station.streams:` guard.
4. **Call helper**: `same_provider, same_tag = pick_similar_stations(all_stations, self._station, sample_size=5)`
5. **Cache write**: `self._similar_cache[self._station.id] = (same_provider, same_tag)`
6. **Render call**: `self._same_provider_links_label.setText(render_similar_html(same_provider, show_provider=False))` + `self._same_tag_links_label.setText(render_similar_html(same_tag, show_provider=True))`
7. **Per-sub-section hidden-when-empty** (per D-02): each sub-section's container widget calls `setVisible(bool(pool))` so empty pools reclaim zero vertical space; section header stays visible (RESEARCH §Open Question 4).
8. **Sample ordering** (per CONTEXT discretion + RESEARCH recommendation): sort by `s.name.casefold()` after sampling for predictability.

**Click-handler pattern** (lines 941-975):
```python
def _on_sibling_link_activated(self, href: str) -> None:
    """Phase 64 / D-02, D-08: parse the sibling href, look up the Station,
    emit sibling_activated.
    ...
    Dual-shape repo.get_station handling (RESEARCH Pitfall #2):
      - Production Repo.get_station raises ValueError on miss (repo.py:271).
      - Some test doubles (MainWindow.FakeRepo) return None.
    Wrap in try/except Exception + check `is None` to be safe in both
    shapes. Qt slots-never-raise: bail silently on any failure path.
    """
    prefix = "sibling://"
    if not href.startswith(prefix):
        return
    try:
        sibling_id = int(href[len(prefix):])
    except ValueError:
        return
    # D-08 defense-in-depth: silent no-op if no station bound, or if the
    # sibling id matches the bound station ...
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

Phase 67's `_on_similar_link_activated(self, href: str)` is a near-verbatim copy with two changes:
- `prefix = "similar://"` (not `"sibling://"`)
- Final emit: `self.similar_activated.emit(station)` (not `sibling_activated`)

All five guards (prefix check, int parse, station-bound check, self-id check, dual-shape `get_station` wrap, None check) are preserved verbatim.

**New methods Phase 67 introduces** (place in a new region IMMEDIATELY BELOW the Phase 64 `_on_sibling_link_activated` block at line 975, with section-header comment `# ---- Phase 67 / similar stations ----`):
- `_refresh_similar_stations()` — per Analog F above
- `_on_similar_link_activated(self, href)` — per Analog F above
- `_on_refresh_similar_clicked()` — pop `self._similar_cache.pop(self._station.id, None)` then `self._refresh_similar_stations()`
- `_on_similar_collapse_clicked()` — toggle `self._similar_body.setVisible(...)`, update glyph, persist via `self._repo.set_setting('similar_stations_collapsed', ...)`
- `set_similar_visible(self, visible: bool)` — public, per Analog D (place near `set_stats_visible` at line 645 for symmetry)

**New instance attributes** in `__init__` (after `self._streams: list = []` at line 217):
```python
# Phase 67 / R-01: in-memory cache, keyed by station id.
self._similar_cache: dict[int, tuple[list, list]] = {}
```

---

### `musicstreamer/ui_qt/main_window.py` (modify) — controller, event-driven

**Analog A:** `musicstreamer/ui_qt/main_window.py:204-210` (Phase 47.1 stats QAction construction in hamburger menu)

**Hamburger checkable QAction pattern** (lines 204-210):
```python
# Phase 47.1 D-03: Stats for Nerds toggle -- its own menu group.
self._act_stats = self._menu.addAction("Stats for Nerds")
self._act_stats.setCheckable(True)
self._act_stats.setChecked(
    self._repo.get_setting("show_stats_for_nerds", "0") == "1"
)
self._act_stats.toggled.connect(self._on_stats_toggled)
```

Phase 67 ADDS adjacent to the Phase 66 Theme picker construction site (lines 187-200, in Group 2 "Settings" — per CONTEXT.md M-01). Recommended placement: AFTER `act_theme = self._menu.addAction("Theme")` (line 189) and BEFORE the Accent Color action (line 192). However, RESEARCH Pattern 1 is anchored on the Phase 47.1 `_act_stats` shape which lives in its own Group 3 separator — the planner picks the exact insertion line. The construction code:
```python
# Phase 67 / S-01, M-01: Show similar stations master toggle.
self._act_show_similar = self._menu.addAction("Show similar stations")
self._act_show_similar.setCheckable(True)
self._act_show_similar.setChecked(
    self._repo.get_setting("show_similar_stations", "0") == "1"
)
self._act_show_similar.toggled.connect(self._on_show_similar_toggled)  # QA-05
```

---

**Analog B:** `musicstreamer/ui_qt/main_window.py:322-324` (Phase 64 sibling signal connection)

**Signal-connection pattern** (lines 322-324):
```python
# Plan 39: edit button → dialog launch
self.now_playing.edit_requested.connect(self._on_edit_requested)
# Phase 64 / D-02a: 'Also on:' sibling click → switch playback (bound-method per QA-05).
self.now_playing.sibling_activated.connect(self._on_sibling_activated)
```

Phase 67 ADDS on the next line:
```python
# Phase 67 / I-02, M-01: Similar Stations link click → switch playback (bound-method per QA-05).
self.now_playing.similar_activated.connect(self._on_similar_activated)
```

---

**Analog C:** `musicstreamer/ui_qt/main_window.py:335-338` (Phase 47.1 WR-02 initial-push pattern)

**Initial visibility push pattern** (lines 335-338):
```python
# Phase 47.1 WR-02: drive panel visibility from the QAction's initial
# checked state. Single source of truth — the panel no longer reads the
# setting itself, so the menu checkmark and panel visibility cannot drift.
self.now_playing.set_stats_visible(self._act_stats.isChecked())
```

Phase 67 ADDS on the next line (per Pitfall 4):
```python
# Phase 67 / M-02: drive Similar Stations container visibility from the
# QAction's initial checked state. Same single-source-of-truth invariant
# as Phase 47.1 WR-02 (locked by test_show_similar_toggle_persists_and_toggles_panel).
self.now_playing.set_similar_visible(self._act_show_similar.isChecked())
```

---

**Analog D:** `musicstreamer/ui_qt/main_window.py:430-441` (Phase 64 `_on_sibling_activated` delegate slot)

**Delegate slot pattern** (lines 430-441):
```python
def _on_sibling_activated(self, station: Station) -> None:
    """Phase 64 / D-02: user clicked an 'Also on:' link in NowPlayingPanel.

    Delegate to _on_station_activated so the canonical 'user picked a
    station' side-effect block (bind_station, player.play,
    update_last_played, refresh_recent, toast, media-keys publish + state)
    fires identically regardless of activation source (station list vs
    sibling click). Unlike Phase 51's _on_navigate_to_sibling (lines
    482-500) — which re-opens EditStationDialog and avoids touching
    playback — this slot DOES change playback (ROADMAP SC #2).
    """
    self._on_station_activated(station)
```

Phase 67 ADDS adjacent:
```python
def _on_similar_activated(self, station: Station) -> None:
    """Phase 67 / C-01: user clicked a Similar Stations link in NowPlayingPanel.

    Delegate to _on_station_activated for uniform side-effect set
    (bind_station, player.play, update_last_played, refresh_recent,
    'Connecting…' toast, media-keys publish + state). Mirrors Phase 64's
    _on_sibling_activated; the only divergence from `_on_station_activated`
    is the originating signal, not the side-effect set.
    """
    self._on_station_activated(station)
```

---

**Analog E:** `musicstreamer/ui_qt/main_window.py:539-542` (Phase 47.1 `_on_stats_toggled` toggle slot)

**Toggle-slot pattern** (lines 539-542):
```python
def _on_stats_toggled(self, checked: bool) -> None:
    """Persist the Stats for Nerds toggle and update the panel (D-04, D-07). Phase 47.1."""
    self._repo.set_setting("show_stats_for_nerds", "1" if checked else "0")
    self.now_playing.set_stats_visible(checked)
```

Phase 67 ADDS adjacent:
```python
def _on_show_similar_toggled(self, checked: bool) -> None:
    """Phase 67 / S-01, M-01: persist the Show Similar Stations toggle and
    update the panel container visibility."""
    self._repo.set_setting("show_similar_stations", "1" if checked else "0")
    self.now_playing.set_similar_visible(checked)
```

---

### `tests/test_pick_similar_stations.py` (create) — test, request-response

**Analog:** `tests/test_aa_siblings.py:1-231` (Phase 51/64 pure-helper test file)

**Module docstring + imports pattern** (lines 1-9):
```python
"""Phase 51 / BUG-02: pure unit tests for find_aa_siblings.

Modeled on tests/test_aa_url_detection.py — no Qt, no fixtures, one assertion
per test. Tests assert the contract of
find_aa_siblings(stations, current_station_id, current_first_url)
-> list[tuple[network_slug, station_id, station_name]].
"""
from musicstreamer.models import Station, StationStream
from musicstreamer.url_helpers import find_aa_siblings, render_sibling_html
```

Phase 67 mirrors with imports:
```python
"""Phase 67: pure unit tests for pick_similar_stations + render_similar_html.

Modeled on tests/test_aa_siblings.py — no Qt, no fixtures, one assertion
per test. Tests assert the contract of
pick_similar_stations(stations, current_station, *, sample_size, rng)
-> tuple[list[Station], list[Station]].
"""
import random
from musicstreamer.models import Station, StationStream
from musicstreamer.url_helpers import pick_similar_stations, render_similar_html
```

**Factory pattern** (lines 12-23):
```python
def _mk(id_, name, url):
    """Factory: a minimal Station with one StationStream at `url`."""
    return Station(
        id=id_,
        name=name,
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=[StationStream(id=id_ * 10, station_id=id_, url=url, position=1)],
    )
```

Phase 67 needs an extended factory: `_mk(id_, name, url, *, provider_id=None, provider_name=None, tags="")` — adds three keyword args so per-test setup can construct stations with specific provider/tag combinations needed for the pool-derivation tests. Same construction shape, additive only.

**Assertion pattern (one per test)** — see lines 26-91 for examples. Each test sets up a small station list (2-5 stations), calls the pure helper, and asserts ONE thing about the return value. No fixtures, no qtbot, no monkeypatching.

**Renderer test pattern** (lines 185-231 — `render_sibling_html` tests):
```python
def test_render_sibling_html_html_escapes_station_name():
    """Phase 64 / D-03 / T-39-01 deviation mitigation preserved: malicious
    sibling name with HTML metachars must be escaped — raw '<script>'
    must NOT appear in the output."""
    siblings = [("zenradio", 2, "<script>alert(1)</script>")]
    out = render_sibling_html(siblings, current_name="Ambient")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "alert(1)" in out  # the text content survives escaping
```

Phase 67 ADDS analogous renderer tests for `render_similar_html`:
- `test_render_similar_html_provider_section_no_provider_in_text` — `show_provider=False` → row text is just `Name`
- `test_render_similar_html_tag_section_includes_provider` — `show_provider=True` → row text is `Name (Provider)`
- `test_render_similar_html_escapes_name_and_provider` — `Pitfall 7 lock` — both `<script>` in name AND in provider must escape
- `test_render_similar_html_uses_br_separator` — multiple stations joined with `<br>` (vertical, not bullet)
- `test_render_similar_html_href_uses_similar_prefix` — `<a href="similar://{id}">` not `sibling://`

**Recommended file size:** ~250-350 lines (per RESEARCH §Wave 0 Gaps), covering SIM-04, SIM-05, SIM-09 success criteria + RESEARCH Pitfalls 1, 2, 7 + reproducibility via seeded `rng=random.Random(42)`.

---

### `tests/test_now_playing_panel.py` (modify) — test, event-driven

**Analog:** `tests/test_now_playing_panel.py:770-898` (Phase 64 sibling section)

**FakeRepo extension pattern** (lines 65-112) — already supports `stations=`, `is_favorited`, `list_stations`, dual-shape `get_station(raises ValueError)`. **No modifications needed** to `FakeRepo` for Phase 67 (per RESEARCH §"Wave 0 Gaps" - "no new fixture surface needed").

**AA-station factory pattern** (lines 132-158):
```python
def _make_aa_station(station_id: int, name: str, url: str,
                     provider: str = "DI.fm") -> Station:
    """Phase 64 Wave 0: factory mirroring tests/test_edit_station_dialog.py:783-806.
    ...
    """
    return Station(
        id=station_id,
        name=name,
        provider_id=1,
        provider_name=provider,
        tags="",
        ...
        streams=[StationStream(...)]
    )
```

Phase 67 may extend this factory inline (or add a sibling `_make_similar_station(...)` factory) that takes `provider_id`, `provider_name`, and `tags` parameters explicitly. The existing `_make_aa_station` is already close — its `tags=""` default is the only blocker for tag-based pool tests.

**qtbot panel test pattern** (lines 774-790):
```python
def test_sibling_label_visible_for_aa_station_with_siblings(qtbot):
    """Phase 64 / SC #1: bound AA station with cross-network sibling ->
    _sibling_label visible with 'Also on:' + a network <a> link."""
    di = _make_aa_station(1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc")
    zr = _make_aa_station(2, "Ambient", "http://prem1.zenradio.com/zrambient?listen_key=abc",
                          provider="ZenRadio")
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

Phase 67 ADDS Phase-67 section AFTER line 898 (per RESEARCH §"Wave 0 Gaps") with mirror tests:
- `test_similar_section_renders_when_master_toggle_on(qtbot)` — analogous to line 774
- `test_similar_section_hidden_when_master_toggle_off(qtbot)` — analogous to line 793
- `test_same_provider_subsection_hidden_when_empty(qtbot)` — D-02 hidden-when-empty
- `test_similar_cache_reused_on_revisit(qtbot)` — R-02 cache hit (assert `panel._similar_cache[di.id]` populated; second `bind_station(di)` reuses)
- `test_similar_cache_keyed_by_station_id(qtbot)` — R-01 multi-station cache
- `test_refresh_similar_pops_cache_and_rerolls(qtbot)` — R-03 (call `_on_refresh_similar_clicked()` directly per RESEARCH Open Q5)
- `test_similar_link_emits_similar_activated_with_station_payload(qtbot)` — Phase 67 mirror of line 840 (use `panel.similar_activated`)
- `test_similar_link_handler_no_op_when_repo_get_station_raises(qtbot)` — Pitfall 3 mirror of line 870
- `test_similar_link_handler_no_op_on_malformed_href(qtbot)` — mirror of line 885
- `test_similar_link_handler_no_op_when_id_matches_bound_station(qtbot)` — mirror of line 856
- `test_similar_collapse_persists(qtbot)` — collapse toggle writes `similar_stations_collapsed` to repo settings
- `test_section_header_visible_with_empty_pools(qtbot)` — header stays visible when both pools empty

**Click-handler signal-capture pattern** (lines 840-853):
```python
def test_sibling_link_emits_sibling_activated_with_station_payload(qtbot):
    ...
    with qtbot.waitSignal(panel.sibling_activated, timeout=1000) as blocker:
        panel._on_sibling_link_activated("sibling://2")
    assert blocker.args == [zr]
```

Phase 67 mirrors with `qtbot.waitSignal(panel.similar_activated, timeout=1000)` and href `"similar://2"`.

**Insertion point:** new section header `# Phase 67 / SIM-01..SIM-12: Similar Stations on the panel` after line 898.

---

### `tests/test_main_window_integration.py` (modify) — test, event-driven

**Analog A:** `tests/test_main_window_integration.py:564-606` (Phase 47.1 stats integration tests)

**QAction-checkable test pattern** (lines 568-584):
```python
def test_stats_action_is_checkable(qtbot, fake_player, fake_repo):
    """D-03: hamburger 'Stats for Nerds' QAction exists, is checkable, and
    initial checked state reflects repo setting (default '0' -> False)."""
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    assert hasattr(w, "_act_stats")
    assert w._act_stats.isCheckable() is True
    # Default repo has no setting -> get_setting returns default "0" -> unchecked
    assert w._act_stats.isChecked() is False


def test_stats_action_initial_checked_when_setting_is_1(qtbot, fake_player):
    """D-04: if repo has 'show_stats_for_nerds' = '1', action starts checked."""
    repo = FakeRepo(stations=[_make_station()], settings={"show_stats_for_nerds": "1"})
    w = MainWindow(fake_player, repo)
    qtbot.addWidget(w)
    assert w._act_stats.isChecked() is True
```

Phase 67 mirrors as `test_show_similar_action_is_checkable` and `test_show_similar_action_initial_checked_when_setting_is_1` (covers SIM-01, SIM-02). Substitute `_act_show_similar` and `show_similar_stations` setting key.

**Persist-and-toggle-panel test pattern** (lines 587-606):
```python
def test_stats_toggle_persists_and_toggles_panel(qtbot, fake_player, fake_repo):
    """D-04 + D-07: triggering the action persists '1'/'0' AND flips the
    panel's _stats_widget visibility accordingly."""
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    # Initial: unchecked, widget hidden
    assert w._act_stats.isChecked() is False
    assert w.now_playing._stats_widget.isHidden() is True

    # Trigger ON
    w._act_stats.trigger()
    assert w._act_stats.isChecked() is True
    assert fake_repo.get_setting("show_stats_for_nerds", "0") == "1"
    assert w.now_playing._stats_widget.isHidden() is False

    # Trigger OFF
    w._act_stats.trigger()
    assert w._act_stats.isChecked() is False
    assert fake_repo.get_setting("show_stats_for_nerds", "0") == "0"
    assert w.now_playing._stats_widget.isHidden() is True
```

Phase 67 mirrors as `test_show_similar_toggle_persists_and_toggles_panel` — substitute `_act_show_similar`, `show_similar_stations`, `_similar_container`. **Critical lock from Pitfall 4:** asserts `_act_show_similar.isChecked() == not _similar_container.isHidden()` after each trigger to enforce single-source-of-truth invariant.

---

**Analog B:** `tests/test_main_window_integration.py:609-630` (QA-05 lambda-grep structural test)

**Bound-method structural test pattern** (lines 609-630):
```python
def test_buffer_percent_bound_method_connect_no_lambda(qtbot, window, fake_player):
    """D-13 + QA-05: emitting Player.buffer_percent updates both bar and
    label on the now-playing panel via a bound-method connect (no lambda)."""
    import inspect
    from musicstreamer.ui_qt import main_window as mw_mod
    ...
    # Structural: no 'lambda' appears on the buffer_percent.connect line
    src = inspect.getsource(mw_mod.MainWindow)
    for line in src.splitlines():
        if "buffer_percent.connect" in line:
            assert "lambda" not in line, (
                f"D-13 violated — lambda found on buffer_percent.connect line: {line!r}"
            )
            break
    else:
        raise AssertionError("buffer_percent.connect line not found in MainWindow source")
```

Phase 67 ADDS `test_no_lambda_on_similar_signal_connections` mirroring this grep — assert `similar_activated.connect`, `_act_show_similar.toggled.connect` (or `triggered.connect`), and the new linkActivated lines all are bound-method.

---

**Analog C:** `tests/test_main_window_integration.py:1049-1126` (Phase 64 sibling integration test)

**Sibling-click-switches-playback test pattern** (lines 1055-1125):
```python
def test_sibling_click_switches_playback_via_main_window(qtbot, monkeypatch):
    """Phase 64 / SC #2: clicking an 'Also on:' link in NowPlayingPanel
    routes through MainWindow's slot to switch active playback. ..."""
    di_station = Station(id=1, name="Ambient", provider_id=1, provider_name="DI.fm",
                         tags="", ..., streams=[StationStream(id=10, ..., url="http://prem1.di.fm:80/ambient_hi?listen_key=abc", position=1)])
    zen_station = Station(id=2, name="Ambient", provider_id=2, provider_name="ZenRadio", ...)

    fake_player = FakePlayer()
    fake_repo = FakeRepo(stations=[di_station, zen_station])

    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)

    # Bind to DI.fm first (simulates the user activating it from the list).
    w._on_station_activated(di_station)
    fake_player.play_calls.clear()
    fake_repo._last_played_ids = []

    # Drive the panel-side click handler directly. The Plan 02 panel test
    # already asserts that this emits sibling_activated(zen_station). This
    # integration test asserts the MainWindow handler picks up the signal
    # and runs the canonical activation chain.
    w.now_playing._on_sibling_link_activated("sibling://2")

    # Phase 64 / SC #2: playback DID switch.
    assert fake_player.play_calls == [zen_station]
    assert fake_repo._last_played_ids == [2]
    assert w.now_playing._station is zen_station
```

Phase 67 ADDS `test_similar_link_switches_playback_via_main_window` (covers SIM-08) mirroring this exactly with substitutions:
- Construct two stations sharing a `provider_id` (or shared tag) so Phase 67's pool derivation includes the second
- Drive `w.now_playing._on_similar_link_activated("similar://2")`
- Same three asserts: `fake_player.play_calls == [other_station]`, `fake_repo._last_played_ids == [2]`, `w.now_playing._station is other_station`

**FakeRepo dual-shape note:** the integration `FakeRepo` (lines 86-178) returns `None` on miss (different from the panel-test `FakeRepo` which raises `ValueError`). Both shapes are covered by Phase 67's defense-in-depth wrap (per RESEARCH Pitfall 3 / Phase 64 precedent).

**Insertion point:** new section header `# Phase 67 / SIM-01..SIM-12: Similar Stations integration` after line 1125.

---

## Shared Patterns

### Bound-method signal connections (QA-05)
**Source:** `musicstreamer/ui_qt/now_playing_panel.py:270` (`linkActivated.connect(self._on_sibling_link_activated)`) + `musicstreamer/ui_qt/main_window.py:210, 322-324, 338` (`toggled.connect`, `sibling_activated.connect`, `set_stats_visible(...)`)

**Apply to:** ALL new connections in Phase 67:
- `self._same_provider_links_label.linkActivated.connect(self._on_similar_link_activated)`
- `self._same_tag_links_label.linkActivated.connect(self._on_similar_link_activated)`
- `self._similar_collapse_btn.clicked.connect(self._on_similar_collapse_clicked)`
- `self._similar_refresh_btn.clicked.connect(self._on_refresh_similar_clicked)`
- `self.now_playing.similar_activated.connect(self._on_similar_activated)` (in MainWindow)
- `self._act_show_similar.toggled.connect(self._on_show_similar_toggled)` (in MainWindow)

**Lock:** structural test `test_no_lambda_on_similar_signal_connections` greps source for the literal `lambda` on each `*.connect` line per the precedent at `tests/test_main_window_integration.py:609-630`.

### Slots-never-raise / dual-shape repo defense
**Source:** `musicstreamer/ui_qt/now_playing_panel.py:921-926` (try/except around `repo.list_stations()`), `now_playing_panel.py:969-974` (try/except around `repo.get_station()` + None-check)

**Apply to:**
- `_refresh_similar_stations` — wrap `self._repo.list_stations()` in `try/except Exception:` + hide section + bail silently
- `_on_similar_link_activated` — wrap `self._repo.get_station(similar_id)` in `try/except Exception:` + check `is None` + bail silently

**Lock:** test `test_similar_link_handler_no_op_when_repo_get_station_raises(qtbot)` mirrors `tests/test_now_playing_panel.py:870-882`.

### T-39-01 PlainText deviation mitigation
**Source:** `musicstreamer/url_helpers.py:259-260` (`html.escape(station_name, quote=True)`)

**Apply to:** EVERY user-controlled string interpolated into RichText in `render_similar_html`:
- `Station.name` — escape unconditionally
- `Station.provider_name` — escape unconditionally (RESEARCH Pitfall 7 — NEW for Phase 67; Phase 64's renderer didn't need this since network names came from compile-time `NETWORKS`)

**Lock:** test `test_render_similar_html_escapes_name_and_provider` (mirrors `tests/test_aa_siblings.py:203-211`).

### Hidden-when-empty container
**Source:** `musicstreamer/ui_qt/now_playing_panel.py:265-268, 911-915` (Phase 64 `_sibling_label.setVisible(False)` zero-vertical-space pattern)

**Apply to:**
- Each Same provider / Same tag sub-section container (D-02 — independent hide-when-empty)
- The entire `_similar_container` (S-02 — hidden when master toggle OFF)
- Sub-section captions (`_same_provider_caption`, `_same_tag_caption`) hidden together with their links label

**Lock:** tests `test_same_provider_subsection_hidden_when_empty(qtbot)` and `test_show_similar_default_off_hides_container`.

### Single-source-of-truth between QAction and panel widget visibility
**Source:** `musicstreamer/ui_qt/main_window.py:335-338` (Phase 47.1 WR-02 invariant) + `tests/test_main_window_integration.py:587-606`

**Apply to:** Every push of `show_similar_stations` state must go through `set_similar_visible(...)`:
- On `__init__` after panel construction (initial push)
- In `_on_show_similar_toggled` slot (user toggle)
- The panel does NOT read the setting itself

**Lock:** `test_show_similar_toggle_persists_and_toggles_panel` asserts `_act_show_similar.isChecked() == (not _similar_container.isHidden())` after each trigger.

### SQLite settings persistence
**Source:** `musicstreamer/repo.py:348-359` (`get_setting`/`set_setting`) + Phase 47.1 `show_stats_for_nerds`, Phase 66 `theme`/`theme_custom`, Phase 59 `accent_color` precedents

**Apply to:** Phase 67's two new keys:
- `show_similar_stations` — default `'0'`, written by `_on_show_similar_toggled`
- `similar_stations_collapsed` — default `'0'` (expanded), written by `_on_similar_collapse_clicked`

No schema migration needed — `get_setting(key, default)` returns the default for missing keys.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | Phase 67 is pure composition of patterns landed by Phases 47.1, 51, 64, 66; every file has an exact analog. |

## Metadata

**Analog search scope:**
- `musicstreamer/url_helpers.py` (264 lines, read in full)
- `musicstreamer/filter_utils.py` (81 lines, read in full)
- `musicstreamer/ui_qt/now_playing_panel.py` (lines 190-300 + 510-580 + 640-660 + 880-980 — Phase 64 sibling region, `set_stats_visible`, `bind_station` refresh trigger)
- `musicstreamer/ui_qt/main_window.py` (lines 180-260 + 315-350 + 425-455 + 535-545 + 775-810 — hamburger menu construction, signal connections, sibling delegate, stats toggle)
- `musicstreamer/ui_qt/station_list_panel.py` (lines 185-275 + 510-525 — collapsible filter strip)
- `musicstreamer/repo.py` (lines 220-280 + 340-360 — `list_stations`, `get_station`, `get_setting`, `set_setting`)
- `tests/test_aa_siblings.py` (lines 1-100 + 175-231 — pure-helper tests)
- `tests/test_now_playing_panel.py` (lines 60-160 + 770-898 — FakeRepo, `_make_aa_station` factory, Phase 64 panel tests)
- `tests/test_main_window_integration.py` (lines 86-180 + 560-630 + 1070-1126 — FakeRepo, Phase 47.1 stats tests, Phase 64 sibling integration)

**Files scanned:** 9 production + test files (all directly analogous to Phase 67 surfaces; no broader codebase scan needed since Phase 67 is purely additive composition)

**Pattern extraction date:** 2026-05-09

**Coverage summary:**
- Files with exact analog: 6 / 6 (100%)
- Files with role-match analog only: 0
- Files with no analog: 0

**Phase 67 is the cleanest pattern-composition phase yet seen in this codebase** — every code touch point has a 1+ landed precedent, the only net-new piece of factoring is the pure-Python `pick_similar_stations` helper, and the test file shape (pure-helper unit + qtbot panel + qtbot integration) maps 1:1 onto the existing Phase 51/64/47.1 corpus.
