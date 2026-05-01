# Phase 64: AudioAddict Siblings on Now Playing - Research

**Researched:** 2026-05-01
**Domain:** Qt UI plumbing (PySide6) — promote a renderer, add a label + signal + handler to an existing panel, mirror an existing main-window slot
**Confidence:** HIGH

## Summary

Phase 64 is a pure Qt main-thread UI/plumbing change. The detection logic, sort
order, hidden-when-empty contract, and HTML rendering shape are already shipped
by Phase 51 in `find_aa_siblings` and `EditStationDialog._render_sibling_html`.
The work is mechanical: (a) lift the renderer from a private dialog method to a
free function in `url_helpers.py`; (b) add a `QLabel`, signal, refresh hook, and
link handler to `NowPlayingPanel`; (c) add one connect line and one
delegating slot to `MainWindow`. There is no schema change, no new helper, no
new dependency, no threading concern, and no new UX decision space — every
behavior that needs to be implemented has a verbatim or near-verbatim Phase 51
analog.

The two non-mechanical risks are: (1) the panel's `FakeRepo` test double has
no `list_stations` / `get_station` and must be extended before any sibling
test will run (Wave 0), and (2) `repo.get_station` raises `ValueError` on
missing id in production but `MainWindow.FakeRepo.get_station` returns `None`
— the panel's `_on_sibling_link_activated` must handle both shapes.

**Primary recommendation:** Single render-promotion plan + single panel-and-wiring
plan + test plan. Reuse Phase 51's `tests/test_aa_siblings.py` shape for
renderer tests, extend `tests/test_now_playing_panel.py` for the new label and
signal, extend `tests/test_main_window_integration.py` for the click->play
delegation flow.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Sibling label inserted as a new `QLabel` in `NowPlayingPanel`'s
  center column **immediately below `name_provider_label`** (line 161) and
  **above `icy_label`** (line 164). Hidden-when-empty reclaims the vertical
  space.
- **D-02:** New `sibling_activated = Signal(object)` (Station payload). Panel's
  `linkActivated` slot looks up the sibling by id via `self._repo.get_station(...)`
  and emits.
- **D-02a:** `MainWindow` connects the signal to `_on_sibling_activated` next
  to the existing `now_playing.edit_requested.connect(...)` line at
  `main_window.py:252`. Bound-method (QA-05).
- **D-03:** Promote `EditStationDialog._render_sibling_html(siblings, current_name) -> str`
  (currently at `edit_station_dialog.py:531-574`) to a **free function
  `render_sibling_html(siblings, current_name)` in `musicstreamer/url_helpers.py`**.
  Body moves verbatim. EditStationDialog's existing `_render_sibling_html` is
  deleted; the call site at `_refresh_siblings` (line 608) updates to call
  the free function.
- **D-03a:** `sibling://{id}` href format preserved verbatim across both
  surfaces.
- **D-04:** `_refresh_siblings()` runs only inside `bind_station(station)`. No
  subscription to library-mutation signals (deferred).
- **D-05 / D-05a:** Hidden-when-empty zero-vertical-space; same Qt.RichText /
  setOpenExternalLinks(False) / linkActivated wiring as Phase 51.
- **D-06:** Sibling URL source is `self._station.streams[0].url` with empty-streams
  defensive fallback (find_aa_siblings already returns [] for empty URL).
- **D-07:** SC #5 (no self-listing) is enforced by `find_aa_siblings`'s existing
  self-id exclusion (`url_helpers.py:122`). Re-stated for traceability.
- **D-08:** Defense-in-depth no-op guard in panel's `_on_sibling_link_activated`
  if `self._station is None or self._station.id == sibling_id`.

### Claude's Discretion

- Exact `Signal` name on `NowPlayingPanel`. `sibling_activated` recommended.
  Object payload (Station) is locked.
- Whether `_on_sibling_activated` is a thin delegator to `_on_station_activated`
  (preferred) or duplicates the side-effect block.
- Whether to keep `EditStationDialog._render_sibling_html` as a thin wrapper or
  delete it cleanly.
- Test placement: extend `tests/test_now_playing_panel.py` for label + signal;
  test the renderer in `tests/test_aa_siblings.py` (existing) — see
  Sibling-rendering test placement below.
- Whether to add a `panel.refresh_siblings()` public seam. Phase 51 used a
  private `_refresh_siblings` — mirror.

### Deferred Ideas (OUT OF SCOPE)

- Live updates while bound (subscribe to `station_saved` / `station_deleted` /
  discovery-import-complete) — D-04 deferred.
- Sibling visibility on additional surfaces (right-click menu, hamburger,
  mini-player).
- Playback continuity hints (extra toast, "Switching to..." message).
- Keyboard shortcut for sibling jump (Alt+1/2/3).
- Sibling preview on hover (tooltip with channel description, listener count).
- Persisted `aa_channel_key` column. Same rejection as Phase 51 D-01.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BUG-02 | Cross-network AudioAddict sibling streams surface as related streams when **playing** a station (closure follow-up to Phase 51, which only surfaced them on the edit dialog). | Reuse `find_aa_siblings` (`url_helpers.py:86`) verbatim per SC #4. Reuse the rendering body of `EditStationDialog._render_sibling_html` (lines 531-574) by promoting to a free function. New label + signal + handler in `NowPlayingPanel` follow the same shape as `edit_requested = Signal(object)` (line 112) and `_on_edit_clicked` (lines 527-530). Click->play delegation through `MainWindow._on_station_activated` (lines 316-326) reuses the canonical "user picked a station" side-effect block. |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Sibling detection (URL parsing, key extraction, list filter) | Pure helper (`url_helpers.py`) | — | Already there; SC #4 forbids any parallel detection logic. Pure function, no Qt. |
| Sibling HTML rendering (link markup + `html.escape`) | Pure helper (`url_helpers.py`) | — | Promoted from dialog per D-03. Pure string transform; needs `NETWORKS` and `html.escape` only. |
| Sibling label widget + visibility + click parsing | UI panel (`now_playing_panel.py`) | — | Layout owns its widgets. The href format (`sibling://{id}`) is parsed by both surfaces independently — no shared parser, no new module. |
| Sibling lookup at click time (id -> Station) | UI panel (`now_playing_panel.py`) | Repo | Panel emits a fully-resolved `Station` so MainWindow can delegate to existing `_on_station_activated(Station)` without another DB hop. |
| Click action (switch active playback, side-effects) | Window (`main_window.py`) | Player + Repo + station list panel + media keys | The "user activated a station" side-effect set is canonical at `_on_station_activated`. Phase 64's new handler delegates there. |
| Test scaffolding for the panel-side flow | `tests/test_now_playing_panel.py` | `tests/test_main_window_integration.py` | Panel-internal contract (signal emit, label visibility, html rendering pickup) lives next to the panel; the full click->play->media-keys delegation flow is integration-shaped. |

## Standard Stack

This phase introduces zero new packages.

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | (existing) | Qt bindings; `QLabel`, `Signal`, `Qt.RichText`, `linkActivated` | Project standard; verified in use at `now_playing_panel.py` and `edit_station_dialog.py`. [VERIFIED: codebase grep] |
| Python `html` (stdlib) | stdlib | `html.escape(text, quote=True)` mitigation for the T-39-01 RichText deviation | Already imported by `edit_station_dialog.py:19` for the existing renderer. Will need to be imported by `url_helpers.py` after the promotion. [VERIFIED: stdlib + codebase grep] |
| `pytest-qt` | (existing) | `qtbot` fixture, `qtbot.waitSignal` | Project test framework; verified at `tests/test_now_playing_panel.py` and `tests/test_edit_station_dialog.py`. [VERIFIED: codebase grep] |

### Existing helpers reused verbatim
| Symbol | Location | Use |
|--------|----------|-----|
| `find_aa_siblings(stations, current_station_id, current_first_url)` | `url_helpers.py:86-146` | Sibling detection (SC #4: single source). Returns `list[tuple[str, int, str]]` sorted in NETWORKS order, self-excluded, AA-gated. |
| `NETWORKS` | `aa_import.py:87` | Slug -> display-name lookup inside the renderer. |
| `MainWindow._on_station_activated(station)` | `main_window.py:316-326` | Canonical "play this station" side-effect block. New `_on_sibling_activated` delegates here. |

## Architecture Patterns

### System Architecture Diagram

```
                  +--------------------------------------+
   user click --> | NowPlayingPanel._sibling_label       |
                  |   (Qt.RichText, <a href="sibling://N">) |
                  +-------------------+------------------+
                                      |
                       linkActivated(href)
                                      v
                  +--------------------------------------+
                  | NowPlayingPanel._on_sibling_link_    |
                  |   activated(href)                    |
                  |   - parse "sibling://{id}"            |
                  |   - guard: self._station is None      |
                  |   - guard: id == self._station.id     |
                  |   - sibling = repo.get_station(id)    |
                  |   - guard: sibling is None / Value-   |
                  |       Error -> silent no-op           |
                  +-------------------+------------------+
                                      |
                          sibling_activated.emit(Station)
                                      v
                  +--------------------------------------+
                  | MainWindow._on_sibling_activated     |
                  |   (delegates to _on_station_         |
                  |    activated)                        |
                  +-------------------+------------------+
                                      |
                                      v
                  +--------------------------------------+
                  | _on_station_activated(Station)       |
                  |   bind_station / play / update_last_ |
                  |   played / refresh_recent / toast /  |
                  |   media_keys.publish_metadata        |
                  +-------------------+------------------+
                                      |
                                      v
                  +--------------------------------------+
                  | NowPlayingPanel.bind_station(...)    |
                  |   ...                                |
                  |   self._populate_stream_picker(...)  |
                  |   self._refresh_siblings()  <-- NEW  |
                  |     reads self._station.streams[0]   |
                  |     calls find_aa_siblings           |
                  |     calls render_sibling_html        |
                  |     setText / setVisible             |
                  +--------------------------------------+

    Independent / parallel renderer consumer (unchanged contract):
      EditStationDialog._refresh_siblings ->
        render_sibling_html(siblings, current_name)
        (free-function call after promotion; same href shape)
```

### Recommended Project Structure

No new files. Modifications only.

```
musicstreamer/
  url_helpers.py                  # ADD: render_sibling_html(siblings, current_name) -> str
                                  # ADD: import html (currently absent)
  ui_qt/
    now_playing_panel.py          # ADD: sibling_activated Signal
                                  # ADD: self._sibling_label QLabel (Qt.RichText)
                                  # ADD: _refresh_siblings() called from bind_station
                                  # ADD: _on_sibling_link_activated(href) handler
                                  # ADD: from musicstreamer.url_helpers import find_aa_siblings, render_sibling_html
    edit_station_dialog.py        # MODIFY: _render_sibling_html body deleted (or made wrapper)
                                  # MODIFY: _refresh_siblings calls render_sibling_html (free function)
                                  # CLEANUP: drop `import html` (only the renderer used it)
                                  # CLEANUP: drop `from musicstreamer.aa_import import NETWORKS` (renderer-only)
                                  # MODIFY: import line at :53 becomes
                                  #   from musicstreamer.url_helpers import find_aa_siblings, render_sibling_html
    main_window.py                # ADD: now_playing.sibling_activated.connect(self._on_sibling_activated) at ~line 253
                                  # ADD: _on_sibling_activated(Station) slot (one-line delegator)
tests/
  test_aa_siblings.py             # ADD: render_sibling_html unit tests (mirror Phase 51 dialog tests
                                  #      that currently target _render_sibling_html)
  test_now_playing_panel.py       # ADD: sibling label visibility, signal emission, FakeRepo extensions
  test_main_window_integration.py # ADD: click->play delegation flow
  test_edit_station_dialog.py     # MODIFY: existing sibling-rendering tests already use the public
                                  #   side-effect of _refresh_siblings (read _sibling_label.text()).
                                  #   They keep working without change. See "Test migration" below.
```

### Pattern 1: Renderer promotion (D-03)

**What:** Move `EditStationDialog._render_sibling_html` body verbatim to
`url_helpers.py` as a top-level free function. Remove the `self` parameter;
keep `siblings` and `current_name`. The body has zero `self` references —
verified by reading lines 531-574 — so the lift is mechanical.

**When to use:** Apply once during the planning step. The Phase 51
`_render_sibling_html` source is unchanged at lines 531-574; lifting it does
not regress any Phase 51 test because every existing test reads through
`d._sibling_label.text()` (the public side effect) rather than calling
`_render_sibling_html` directly. [VERIFIED: grep `_render_sibling_html` in
`tests/test_edit_station_dialog.py` — zero hits; only `_sibling_label`,
`_on_sibling_link_activated`, `navigate_to_sibling`, `_refresh_siblings` are
referenced.]

**Example (the post-promotion shape):**
```python
# musicstreamer/url_helpers.py
# Source: edit_station_dialog.py:531-574 (verbatim body, self removed).

from __future__ import annotations

import html
import urllib.parse

from musicstreamer.aa_import import NETWORKS

# (existing helpers above ...)

def render_sibling_html(
    siblings: list[tuple[str, int, str]],
    current_name: str,
) -> str:
    """Phase 51 / D-07, D-08 renderer. Promoted to free function in Phase 64
    so EditStationDialog and NowPlayingPanel share the same renderer.

    siblings: from find_aa_siblings -- already sorted in NETWORKS order.
    current_name: the bound station's display name. Drives D-08 link-text
                  format: same name -> network only; different -> "Network -- Name".
    Returns: 'Also on: <a href="sibling://{id}">{label}</a> ...'

    Security: html.escape on every interpolated station_name; network names
    are compile-time NETWORKS constants and need no escape. The href payload
    is integer-only ("sibling://{id}") so it cannot carry injectable content.
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
- Use the literal `—` and `•` Unicode escapes in the new file as in
  the existing dialog source — they survive editor quirks and round-trip
  through `git diff` cleanly.
- `url_helpers.py` does NOT currently `import html`; the planner must add it.
  [VERIFIED: `grep "import html" url_helpers.py` returns no hits.]
- `NETWORKS` is already imported by `url_helpers.py` (line 12). No new import
  needed for that.
- Preferred approach: **delete** the dialog's `_render_sibling_html` outright
  and update `_refresh_siblings` (line 608) to call
  `render_sibling_html(siblings, self._station.name)`. Keeping a wrapper
  invites drift; a clean delete is the recommendation.

### Pattern 2: Panel widget insertion (D-01, D-05)

**What:** Insert a new `QLabel` between `name_provider_label` (line 161) and
`icy_label` (line 164) in `NowPlayingPanel.__init__`.

**When to use:** Once, in `__init__` during the center-column construction at
lines 154-171.

**Layout API:** The center column is a `QVBoxLayout` populated linearly via
`center.addWidget(...)`. To insert at position 1 (right after the
already-added `name_provider_label`), the planner has two equivalent
options:

1. **Add inline at the right point in `__init__`** — the simplest approach,
   matches every other widget construction in this file. Insert the four
   sibling-label lines between the existing `center.addWidget(self.name_provider_label)`
   (line 161) and `# ICY title` block (lines 163-171). New code lands here:

   ```python
   center.addWidget(self.name_provider_label)        # existing line 161

   # Phase 64 / D-01, D-05, D-05a: cross-network "Also on:" sibling line.
   # Same Qt.RichText deviation from T-39-01 as Phase 51's dialog version,
   # with the same html.escape mitigation in the shared renderer.
   self._sibling_label = QLabel("", self)
   self._sibling_label.setTextFormat(Qt.RichText)
   self._sibling_label.setOpenExternalLinks(False)
   self._sibling_label.setVisible(False)             # D-05: hidden when empty
   self._sibling_label.linkActivated.connect(self._on_sibling_link_activated)
   center.addWidget(self._sibling_label)

   # ICY title (UI-SPEC Heading role 13pt DemiBold)
   self.icy_label = QLabel("No station playing", self)   # existing line 164
   ```

2. **Use `center.insertWidget(1, self._sibling_label)`** — equivalent. Qt's
   `QBoxLayout.insertWidget(index, widget)` inserts at the given index,
   shifting later widgets down. [VERIFIED: Qt6 docs — QBoxLayout.insertWidget.]
   This is mechanically fine but harder to read than constructing widgets in
   visual order.

**Recommendation:** **Inline construction (option 1).** Matches the
existing in-file style; no `insertWidget` index magic for a future reader to
verify against the visual order.

**Font choice:** `name_provider_label` uses `QFont().setPointSize(9)`
(line 156-159). The sibling label is a continuation of the station identity
tagline — recommend **inheriting the Qt platform default** (no `setFont`
call) so the link styling renders at the system body-text size. The Phase 51
dialog version sets no font either — visual parity. Recommendation is
explicit because CONTEXT.md flagged this as a font question; if the planner
wants 9pt parity with `name_provider_label`, both are defensible; the default
is more readable as link text. **Recommendation: default font (no setFont).**

### Pattern 3: Click handler with no-op guards (D-08)

```python
def _on_sibling_link_activated(self, href: str) -> None:
    """Phase 64 / D-02, D-08: parse the sibling href, look up the Station,
    emit sibling_activated.

    Mirrors EditStationDialog._on_sibling_link_activated (lines 1004-1051) but
    has no dirty-state confirm path — the panel has no editable form. The
    surface contract is "user clicked a sibling -> switch playback to it",
    not "user clicked a sibling -> navigate to its editor".
    """
    prefix = "sibling://"
    if not href.startswith(prefix):
        return
    try:
        sibling_id = int(href[len(prefix):])
    except ValueError:
        return
    # D-08 defense-in-depth: silent no-op if no station bound, or if the
    # sibling id matches the bound station (find_aa_siblings excludes self,
    # but rendering staleness could theoretically allow a stale link).
    if self._station is None or self._station.id == sibling_id:
        return
    # Repo lookup. Production Repo.get_station raises ValueError; some test
    # doubles (MainWindow.FakeRepo) return None. Handle both.
    try:
        sibling = self._repo.get_station(sibling_id)
    except Exception:
        return
    if sibling is None:
        return
    self.sibling_activated.emit(sibling)
```

**Source attribution for the try/except:** `repo.py:271` raises
`ValueError("Station not found")`; `MainWindow.FakeRepo.get_station` (test_main_window_integration.py:131-152)
returns `None` for unknown ids. The dialog's existing `_on_navigate_to_sibling`
in `MainWindow` only checks `if sibling is None` (line 498) — production
would raise before that check ever fires. The panel's handler runs in the
hot-path on every click; a bare except followed by `is None` matches the
existing `_LogoFetchWorker.run` exception-swallow pattern (`edit_station_dialog.py:122-123`)
and is the safest contract for a UI slot. [VERIFIED: grep `def get_station`
in `repo.py` and `tests/test_main_window_integration.py`.]

### Pattern 4: MainWindow delegating slot (D-02 default)

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

**One-liner connect, next to the existing `edit_requested` connect:**

```python
# main_window.py around line 252-253
self.now_playing.edit_requested.connect(self._on_edit_requested)
self.now_playing.sibling_activated.connect(self._on_sibling_activated)  # NEW Phase 64
```

### Anti-Patterns to Avoid

- **Re-implementing detection in the panel.** SC #4 forbids parallel logic.
  Use `find_aa_siblings` only. Verification: grep the new code for
  `_aa_*`, `_is_aa_url`, `NETWORKS` — only the renderer module should
  reference them.
- **Self-capturing lambdas in the new connections.** QA-05. The Phase 51
  exception (lambda capturing only local id in `_on_edit_requested`) is for
  per-dialog signal wiring — Phase 64 has no analog need.
- **Subscribing the panel to `station_saved` / `station_deleted` /
  discovery signals to live-update the sibling line.** D-04 explicitly
  defers this. Refresh runs only inside `bind_station`.
- **Calling `Player.stop()` before `Player.play(sibling)`.** `Player.play`
  already cancels timers, clears the streams queue, and sets the new
  station's name (player.py:255-285) — playing a fresh station handles the
  transition cleanly. No explicit stop needed. [VERIFIED:
  `musicstreamer/player.py:255-285`]
- **Adding a new `panel.refresh_siblings()` public seam.** CONTEXT.md leaves
  this to the planner; recommendation is to keep it private (`_refresh_siblings`)
  matching Phase 51's dialog naming. Tests can call the private method
  directly (the panel uses `_` prefix for "internal but tested" already —
  `_on_play_pause_clicked`, `_on_stop_clicked`, etc.).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sibling detection | A second helper that grep-scans stations or re-parses URLs | `find_aa_siblings` (`url_helpers.py:86`) | SC #4 explicit single source; the existing helper handles AA-gating, self-exclusion, NETWORKS sort, empty-streams, unparseable-URLs. All edge cases are tested in `tests/test_aa_siblings.py`. |
| HTML rendering with `<a>` links | A panel-local renderer or a dialog-local renderer | The promoted `render_sibling_html` free function (D-03) | Single source of rendering means the U+2022 / U+2014 / "Also on:" / `html.escape` / `sibling://{id}` shape can never drift between surfaces. |
| URL classification (`_is_aa_url`, slug, key) | Direct string parsing in the panel | The existing `url_helpers.py` private helpers | They are already imported transitively by `find_aa_siblings`. The panel never needs them directly. |
| Click-to-play side effects | Custom playback transition logic, explicit stop+play sequence | Delegate to `MainWindow._on_station_activated(station)` | One canonical path for all "user picked a station" side effects (bind, play, last_played, refresh_recent, toast, media-keys). Two paths invite drift. |
| Sibling-label widget | A `QFrame` with custom paintEvent or a `QToolButton` flow | `QLabel` with `Qt.RichText` + `linkActivated` | Phase 51 verified the idiom works; tests run against the same shape. |

**Key insight:** The phase is **plumbing only**. Every piece of behavior has
a verbatim Phase 51 analog. The risk is not in choosing the right tool — it
is in *not* re-deriving anything.

## Common Pitfalls

### Pitfall 1: FakeRepo missing `list_stations` / `get_station`
**What goes wrong:** `tests/test_now_playing_panel.py`'s `FakeRepo` class
(lines 65-92) defines `get_setting`, `set_setting`, `is_favorited`,
`add_favorite`, `remove_favorite`, `list_streams` — but **not**
`list_stations` or `get_station`. Any test that drives `bind_station(aa_station)`
with sibling expectations will `AttributeError` on the new
`_refresh_siblings` call.
**Why it happens:** The panel's existing test surface never needed those
methods. Phase 64 is the first time the panel calls `list_stations` /
`get_station`.
**How to avoid:** Wave 0 of the panel test plan extends `FakeRepo` with both
methods, parameterized by a constructor argument:
```python
class FakeRepo:
    def __init__(self, settings=None, stations=None):
        self._settings = dict(settings or {})
        self._stations = list(stations or [])
        # ...

    def list_stations(self):
        return list(self._stations)

    def get_station(self, station_id):
        for s in self._stations:
            if s.id == station_id:
                return s
        raise ValueError("Station not found")  # match real Repo.get_station
```
**Warning signs:** `AttributeError: 'FakeRepo' object has no attribute
'list_stations'` on the very first sibling test run.

### Pitfall 2: `repo.get_station` raises vs returns None
**What goes wrong:** Production `Repo.get_station` raises `ValueError("Station
not found")` for unknown ids (`repo.py:271`). `MainWindow.FakeRepo.get_station`
returns `None` (`tests/test_main_window_integration.py:152`). If the panel's
`_on_sibling_link_activated` only checks `is None`, integration tests pass
but production crashes the slot.
**Why it happens:** API shape mismatch between the real repo and a popular
test double; the existing `MainWindow._on_navigate_to_sibling` (line 498)
checks `is None` only — it works because `EditStationDialog.exec` is
monkeypatched in those tests, never reaching production `repo.get_station`.
**How to avoid:** Wrap the lookup in `try/except Exception` and bail
silently. Match the `_LogoFetchWorker.run` precedent
(`edit_station_dialog.py:122-123`).
**Warning signs:** Click on a sibling that was just deleted in another
window -> uncaught `ValueError` propagates out of the slot. Qt may print
to stderr or terminate the connection.

### Pitfall 3: Phase 51's existing renderer tests
**What goes wrong:** Promoting `_render_sibling_html` could break Phase 51's
dialog-level tests if those tests called the private method by name.
**Why it doesn't actually happen here:** [VERIFIED: 2026-05-01] grep over
`tests/test_edit_station_dialog.py` shows zero references to
`_render_sibling_html`. The Phase 51 sibling tests (lines 843-949) all read
the rendered output via `d._sibling_label.text()` — a public side-effect.
The promotion is transparent to those tests.
**How to avoid:** Run the existing Phase 51 dialog test suite after the
promotion; expect 100% green with zero changes. The planner does not need a
test-migration step for `tests/test_edit_station_dialog.py`. The new
`render_sibling_html` unit tests live in `tests/test_aa_siblings.py` (D-04
of test placement).
**Warning signs:** None expected. If a test does fail, its failure message
will name `_render_sibling_html` directly — adjust to call `render_sibling_html`
from `url_helpers`.

### Pitfall 4: Connection ordering in `MainWindow.__init__`
**What goes wrong:** `now_playing` is constructed at the panel-build site
(earlier in `__init__`) and the signal-wiring block at lines 230-260 fires
sequentially. The new `now_playing.sibling_activated.connect(...)` line must
land **after** `self.now_playing` is constructed and **alongside** the existing
`edit_requested.connect` (line 252). Putting it before construction
attribute-errors at startup; putting it in a separate method invites missed
wiring.
**How to avoid:** Insert the connect line at line 253 (immediately after
`self.now_playing.edit_requested.connect(self._on_edit_requested)`).
Consistent ordering keeps the related connects co-located.
**Warning signs:** `AttributeError: 'NoneType' object has no attribute
'sibling_activated'` at startup — connect ran before `self.now_playing` was
assigned.

### Pitfall 5: Dropping `import html` from edit_station_dialog
**What goes wrong:** After deleting `_render_sibling_html` from the dialog,
the planner removes `import html` (line 19) and `from musicstreamer.aa_import
import NETWORKS` (line 48) as dead imports — but if a future change
(unrelated to Phase 64) reintroduces a need for either, the import order will
have to be re-established.
**How to avoid:** Drop both imports in the same plan task that deletes
`_render_sibling_html`. Mark the task description "remove dead imports left
over from `_render_sibling_html` deletion" so the diff is grep-able later.
[VERIFIED: 2026-05-01] After the deletion, the only two remaining
`html.` references in the dialog are inside docstring/comment text (lines
400-401) — no code use. Same for `NETWORKS` — the only non-comment use is
inside `_render_sibling_html`.
**Warning signs:** A linter or `pyflakes` run would flag both as unused.
Project has no linter (per CONVENTIONS.md), so this only matters for code
hygiene.

## Code Examples

### Adding the new Signal (next to existing signals)
```python
# musicstreamer/ui_qt/now_playing_panel.py around line 115
# Source: existing pattern at lines 106-115.

# Emitted when user clicks edit button -- passes current Station to MainWindow.
edit_requested = Signal(object)

# Emitted when the user stops playback via the in-panel Stop button (not via OS media key).
stopped_by_user = Signal()

# Phase 64 / D-02: emitted when user clicks an 'Also on:' sibling link in
# the cross-network sibling line. Payload is the resolved sibling Station;
# MainWindow connects to _on_sibling_activated which delegates to
# _on_station_activated to switch active playback. Mirrors edit_requested
# in payload shape (Station via Signal(object)).
sibling_activated = Signal(object)
```

### Calling `_refresh_siblings` from `bind_station`
```python
# musicstreamer/ui_qt/now_playing_panel.py around line 344
# Source: existing pattern at line 344.

self._populate_stream_picker(station)
self._refresh_siblings()                # NEW Phase 64: must run after the
                                         # station is bound (uses self._station)
```

### `_refresh_siblings` body
```python
def _refresh_siblings(self) -> None:
    """Phase 64 / D-04, D-05: refresh the 'Also on:' label for the bound station.

    Reads self._station.streams[0].url, scans repo.list_stations() for AA
    siblings on different networks, then either populates _sibling_label
    with HTML or hides it entirely (zero vertical space when no siblings).

    Hidden-when-empty (D-05) covers four cases (mirrors Phase 51 dialog):
      1. self._station is None.
      2. self._station.streams is empty (defensive -- find_aa_siblings
         returns [] for empty current_first_url).
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

## Project Constraints (from CLAUDE.md)

- `Skill("spike-findings-musicstreamer")` is the routed skill for **Windows
  packaging / GStreamer+PyInstaller / conda-forge / PowerShell** topics.
  **Phase 64 is none of those** — pure Qt main-thread UI. Do **not** auto-load
  this skill; it would inject hundreds of lines of irrelevant findings.

## Project Conventions Applied

- snake_case + type hints everywhere (CONVENTIONS.md). Apply to new
  `render_sibling_html`, `_refresh_siblings`, `_on_sibling_link_activated`,
  `_on_sibling_activated`.
- No formatter; 4-space indent; `from __future__ import annotations` at module
  top of any modified file (`url_helpers.py` already has it; the modified
  panel and main_window files already have it).
- Bound-method signal connections (QA-05). Apply to:
  - `self._sibling_label.linkActivated.connect(self._on_sibling_link_activated)`
  - `self.now_playing.sibling_activated.connect(self._on_sibling_activated)`
- T-39-01 PlainText convention deviated for the new `_sibling_label` exactly
  as Phase 51 deviated for `EditStationDialog._sibling_label`. Mitigation
  (`html.escape`) lives in the shared renderer.
- Linux X11 deployment target, DPR=1.0 (per project memory). No HiDPI
  considerations apply.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` + `pytest-qt` (existing) |
| Config file | `pyproject.toml` (existing) |
| Quick run command | `pytest tests/test_now_playing_panel.py tests/test_aa_siblings.py -x` |
| Full suite command | `pytest -x` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUG-02 / SC #1 | Bound AA station with siblings -> `_sibling_label` is visible and contains "Also on:" + a network link | unit (pytest-qt) | `pytest tests/test_now_playing_panel.py::test_sibling_label_visible_for_aa_station_with_siblings -x` | Wave 0: extend `tests/test_now_playing_panel.py` |
| BUG-02 / SC #2 | Click on sibling link emits `sibling_activated(Station)` with correct Station | unit (pytest-qt) | `pytest tests/test_now_playing_panel.py::test_sibling_link_emits_sibling_activated -x` | Wave 0: extend `tests/test_now_playing_panel.py` |
| BUG-02 / SC #2 (integration) | Click on sibling link results in `Player.play(sibling)` and `Repo.update_last_played(sibling.id)` and `_on_station_activated`-equivalent side effects | integration (pytest-qt) | `pytest tests/test_main_window_integration.py::test_sibling_activated_switches_playback -x` | Wave 0: extend `tests/test_main_window_integration.py` |
| BUG-02 / SC #3 (non-AA hidden) | Bound non-AA station -> label hidden | unit (pytest-qt) | `pytest tests/test_now_playing_panel.py::test_sibling_label_hidden_for_non_aa_station -x` | Wave 0 |
| BUG-02 / SC #3 (no-siblings hidden) | Bound AA station with no other AA stations on other networks -> label hidden | unit (pytest-qt) | `pytest tests/test_now_playing_panel.py::test_sibling_label_hidden_when_no_siblings -x` | Wave 0 |
| BUG-02 / SC #3 (no-station hidden) | No bound station (panel default) -> label hidden | unit (pytest-qt) | `pytest tests/test_now_playing_panel.py::test_sibling_label_hidden_when_no_station -x` | Wave 0 |
| BUG-02 / SC #4 (single source) | No new detection logic introduced. Negative spy: panel module imports only `find_aa_siblings` (and `render_sibling_html`); does not import `_is_aa_url`, `_aa_slug_from_url`, `_aa_channel_key_from_url`, or `NETWORKS`. | static (pytest grep) | `pytest tests/test_now_playing_panel.py::test_panel_does_not_reimplement_aa_detection -x` | Wave 0 |
| BUG-02 / SC #5 (no self-list) | Bound AA station's own id is excluded from the rendered link list. Verifies `find_aa_siblings`'s self-exclusion is exercised end-to-end. | unit (pytest-qt) | `pytest tests/test_now_playing_panel.py::test_sibling_label_excludes_self -x` | Wave 0 |
| Renderer parity (D-03) | Promoted `render_sibling_html` produces identical output to the deleted `_render_sibling_html` for representative inputs. | unit (pure) | `pytest tests/test_aa_siblings.py::test_render_sibling_html_basic -x` (and four sibling tests for name-match, name-mismatch, html-escape, U+2022/U+2014) | Wave 0: extend `tests/test_aa_siblings.py` |
| Phase 51 regression (renderer promotion) | Existing `tests/test_edit_station_dialog.py` sibling-rendering tests stay green after the promotion (Phase 51 tests read `_sibling_label.text()` -- public side effect, transparent to the renderer move). | unit (pytest-qt) | `pytest tests/test_edit_station_dialog.py -k sibling -x` | Already exists (lines 843-1052); no changes expected |
| Defense-in-depth (D-08) | `_on_sibling_link_activated` is a no-op when self._station is None, when sibling_id == self._station.id, when href is malformed, when href has non-int payload, and when `repo.get_station` raises or returns None. | unit (pytest-qt) | `pytest tests/test_now_playing_panel.py::test_sibling_link_handler_guards -x` | Wave 0 |
| Refresh trigger (D-04) | `_refresh_siblings` runs exactly once per `bind_station` call. Spy on the helper to confirm no other call site (e.g., no library-mutation subscription wired). | unit (pytest-qt) | `pytest tests/test_now_playing_panel.py::test_refresh_siblings_runs_once_per_bind -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_now_playing_panel.py tests/test_aa_siblings.py -x`
- **Per wave merge:** `pytest tests/test_now_playing_panel.py tests/test_aa_siblings.py tests/test_edit_station_dialog.py tests/test_main_window_integration.py -x`
- **Phase gate:** `pytest -x` full suite green before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `tests/test_now_playing_panel.py` — extend the existing `FakeRepo` to
      support `list_stations` and `get_station(id)` (raises `ValueError` on
      miss to match production `Repo.get_station` semantics). Add an
      `_make_aa_station(...)` factory mirroring the one at
      `tests/test_edit_station_dialog.py:783`. Add the `aa_station`,
      `aa_repo` fixtures or a parameterized panel constructor pattern.
- [ ] `tests/test_aa_siblings.py` — add `render_sibling_html` unit tests
      (basic, name-match, name-mismatch, html-escape, U+2022, U+2014, empty
      list -> "Also on: " edge case if applicable). Mirror the existing
      `_mk(...)` factory at line 12.
- [ ] `tests/test_main_window_integration.py` — add a click->play
      delegation test. The existing `FakeRepo` already supports
      `list_stations` and `get_station`. Pattern from
      `test_station_activated_updates_last_played` (line 279). Approach:
      construct a `MainWindow` with a bound AA station and one sibling in
      `fake_repo._stations`, drive `panel._on_sibling_link_activated("sibling://2")`,
      assert `fake_player.play_calls` contains the sibling and
      `fake_repo._last_played_ids` records the sibling's id.

*(If no gaps existed: "None — existing test infrastructure covers all phase
requirements." That is **not** the case here; the panel's `FakeRepo` is the
gating gap.)*

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `_render_sibling_html` private to `EditStationDialog` (Phase 51) | `render_sibling_html` free function in `url_helpers.py` (Phase 64 D-03) | Phase 64 | Two surfaces (dialog + panel) share one renderer; eliminates drift. |
| Sibling visibility scoped to edit dialog only (Phase 51) | Sibling visibility on Now Playing too (Phase 64) | Phase 64 | Closes BUG-02 follow-up; primary user-value surface. |
| Click on sibling -> navigate to sibling's editor (Phase 51 D-09) | Click on sibling on Now Playing -> switch playback to sibling (Phase 64 SC #2) | Phase 64 | Different surfaces, different actions. The dialog action is unchanged; the panel action is a deliberate, distinct contract. |

**Deprecated/outdated:** None. Phase 51 contracts remain authoritative for
the dialog surface; Phase 64 layers a parallel surface with its own
contract.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Default Qt platform font (no `setFont`) is the right choice for `_sibling_label`, not 9pt to match `name_provider_label`. | Pattern 2: Panel widget insertion | Low — purely visual. If Kyle prefers 9pt, the planner can mirror `name_provider_label`'s font construction in two extra lines. The Phase 51 dialog version uses default font and looked fine in UAT, which is the strongest signal. [ASSUMED based on visual judgment, not verified in UAT] |
| A2 | `MainWindow._on_sibling_activated` should be a thin delegator to `_on_station_activated`, not a duplicated side-effect block. | Pattern 4: MainWindow delegating slot | Low — CONTEXT.md D-02 prefers delegation. Risk is only if `_on_station_activated` later grows a station-list-source-specific branch (e.g., logging origin), in which case the slot will need divergence. None visible today. [ASSUMED based on D-02 default; not verified by external UX requirement] |
| A3 | The Phase 51 sibling-rendering tests in `tests/test_edit_station_dialog.py` will remain green after the renderer promotion without changes, because they all read through `d._sibling_label.text()` rather than calling `_render_sibling_html` by name. | Pitfall 3 | Low — verified by grep (zero hits for `_render_sibling_html` in that test file); marked ASSUMED only to flag that the tests have not literally been re-run after the promotion. The planner's plan-checker should run `pytest tests/test_edit_station_dialog.py -k sibling` after the promotion task and before the panel-add task. [VERIFIED by grep; ASSUMED that no subtle test reads it indirectly] |

## Open Questions

1. **Should `_on_sibling_activated` produce a different toast string than
   "Connecting..." to signal "you switched stations"?**
   - What we know: CONTEXT.md leaves toast wording locked to
     `_on_station_activated`'s "Connecting..." (D-02 default).
   - What's unclear: Whether the user mental model "I jumped to a sibling"
     deserves a distinct toast (e.g., "Switched to ZenRadio").
   - Recommendation: **Ship D-02's default ("Connecting...")**. If post-UAT
     feedback requests a distinct toast, that's a one-line follow-up patch.
     Don't over-design pre-UAT.

2. **Is the dialog's existing `_render_sibling_html` deleted outright, or
   kept as a thin wrapper?**
   - What we know: D-03 says delete cleanly; D-03's "Claude's Discretion"
     allows a wrapper for source stability.
   - What's unclear: Nothing functional. Wrapper invites drift; clean delete
     is cleaner.
   - Recommendation: **Delete cleanly.** Tests do not call the private
     method by name (verified). No wrapper.

## Environment Availability

This phase has no external runtime dependencies beyond what's already in the
project. Skipping the dependency probe step is appropriate.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PySide6 | All Qt UI work | (existing) | (existing) | — |
| pytest + pytest-qt | Test execution | (existing) | (existing) | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Sources

### Primary (HIGH confidence) — codebase verified 2026-05-01

- `musicstreamer/url_helpers.py:86-146` — `find_aa_siblings` body, sort order,
  exclusion logic.
- `musicstreamer/url_helpers.py` (lines 1-13) — module docstring; "zero
  GTK/Qt coupling" constraint applies to the new `render_sibling_html`.
- `musicstreamer/ui_qt/edit_station_dialog.py:531-574` —
  `_render_sibling_html` body to lift verbatim.
- `musicstreamer/ui_qt/edit_station_dialog.py:397-412` — Phase 51
  `_sibling_label` construction shape (mirror in panel).
- `musicstreamer/ui_qt/edit_station_dialog.py:1004-1051` — Phase 51
  `_on_sibling_link_activated` shape (mirror in panel without the dirty-state
  branch).
- `musicstreamer/ui_qt/now_playing_panel.py:94-115` — Signal-declaration zone
  for the new `sibling_activated`.
- `musicstreamer/ui_qt/now_playing_panel.py:155-171` — center-column layout
  insertion site.
- `musicstreamer/ui_qt/now_playing_panel.py:325-344` — `bind_station` site
  for the new `_refresh_siblings()` call.
- `musicstreamer/ui_qt/main_window.py:251-256` — signal-wiring zone for the
  new connect line.
- `musicstreamer/ui_qt/main_window.py:316-326` — `_on_station_activated`
  reference for delegation.
- `musicstreamer/ui_qt/main_window.py:482-500` — Phase 51's
  `_on_navigate_to_sibling` precedent for the new `_on_sibling_activated`
  slot shape.
- `musicstreamer/player.py:255-285` — `Player.play` clears the previous
  stream queue and starts the new one. Confirms no explicit `stop()` is
  needed before sibling switch.
- `musicstreamer/repo.py:225-284` — `list_stations` and `get_station`
  signatures. `get_station` raises `ValueError`.
- `tests/test_now_playing_panel.py:65-92` — current `FakeRepo` shape;
  missing `list_stations` and `get_station` (Wave 0 gap).
- `tests/test_aa_siblings.py:1-130` — pure-unit pattern for renderer tests.
- `tests/test_edit_station_dialog.py:773-1105` — Phase 51 sibling tests;
  zero hits for `_render_sibling_html` (verified, supports A3).
- `tests/test_main_window_integration.py:77-200` — integration `FakeRepo`
  and `fake_repo`/`window` fixtures.
- `.planning/phases/51-audioaddict-cross-network-siblings/51-CONTEXT.md` —
  Phase 51 D-01..D-12.
- `.planning/phases/51-audioaddict-cross-network-siblings/51-PATTERNS.md` —
  pattern map; analog selections.
- `.planning/codebase/CONVENTIONS.md` — snake_case, type hints, no formatter,
  bound-method signal connections (QA-05).
- `.planning/ROADMAP.md:373-388` — Phase 64 goal + 5 success criteria.

### Secondary (MEDIUM confidence) — Qt API references

- `QBoxLayout.insertWidget(index, widget)` semantics — Qt6 standard
  documentation; verified the API exists for the alternative-pattern note in
  Pattern 2. Recommendation does not depend on `insertWidget`.

### Tertiary (LOW confidence) — none

No claims in this research rest on web search alone.

## Metadata

**Confidence breakdown:**
- Standard stack (no new deps): HIGH — codebase grep confirmed.
- Architecture (delegation, layout slot, signal shape): HIGH — verbatim
  Phase 51 analog with one verified divergence (panel-side click changes
  playback; dialog-side does not).
- Pitfalls: HIGH for #1 (`FakeRepo` gap, verified), HIGH for #2 (`get_station`
  raises, verified), HIGH for #3 (Phase 51 tests don't ref private name,
  verified by grep), MEDIUM for #4 (connect ordering — speculative based
  on standard Qt startup semantics, not a known regression in this codebase).

**Research date:** 2026-05-01
**Valid until:** 2026-05-31 (30 days — stable codebase, no upstream library
risk; renderer/helper layer hasn't changed since Phase 51 closed)

## RESEARCH COMPLETE

Phase 64 is plumbing only — promote `_render_sibling_html` to a free function,
add a `QLabel` + `Signal` + handler to `NowPlayingPanel`, and add one
delegating slot to `MainWindow`. The single material gap is `FakeRepo` in
`tests/test_now_playing_panel.py` lacking `list_stations` / `get_station` —
plan Wave 0 must extend it.
