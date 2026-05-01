---
phase: 64
slug: audioaddict-siblings-on-now-playing
status: draft
shadcn_initialized: false
preset: none
created: 2026-05-01
---

# Phase 64 — UI Design Contract

> One new visible widget on `NowPlayingPanel`: an "Also on: Network • Network" sibling line that, when clicked, switches active playback to the sibling AA station. The visual format (HTML, U+2022 BULLET separator, U+2014 EM DASH on name-mismatch) is **inherited verbatim from Phase 51's `EditStationDialog._sibling_label`** via the promoted `render_sibling_html` free function (CONTEXT D-03). The substantive design dimension for this phase is **Interaction / state contract** — every other dimension reduces to "no change, inherits Phase 37 / Phase 51 tokens."

---

## Phase Classification

**Type:** Feature add (one new widget) on an existing panel surface.
**New visual chrome:** ONE `QLabel` (`self._sibling_label`) inserted into `NowPlayingPanel`'s center column.
**New components:** None on the dialog side (CONTEXT D-03 promotes Phase 51's private `_render_sibling_html` to a free function `render_sibling_html` in `musicstreamer/url_helpers.py` — the dialog continues to render via the same shared renderer).
**New copy:** None — the visible "Also on: …" string is produced by the shared renderer at runtime from runtime data + the compile-time `NETWORKS` constant.
**Visual diff vs. Phase 51 ship:** Identical sibling format on a new surface. The only pixel-level diff is **where** the line appears — `NowPlayingPanel`'s center column instead of the bottom of `EditStationDialog`.

CONTEXT.md (D-01..D-08) and RESEARCH.md fully lock the implementation. Auto mode active — no user questions asked. Choices flagged as "Inferred" are minimum-surprise defaults documented for the planner / executor.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (Qt6 / PySide6 — desktop app, not web; shadcn N/A) |
| Preset | not applicable |
| Component library | PySide6 native widgets — `QLabel` only for this phase |
| Icon library | n/a — this phase adds no icon |
| Font | Qt platform default (Fusion / adwaita-qt — same family policy as Phase 37) |
| Theme tokens module | `musicstreamer/ui_qt/_theme.py` — `ERROR_COLOR_HEX`, `ERROR_COLOR_QCOLOR`, `STATION_ICON_SIZE`. **Phase 64 reads zero theme tokens.** |
| Style direction | Qt-native flat — no global QSS override. The new label inherits the platform palette `Link` role from the `QPalette` (Phase 37 §Style direction policy unchanged). |

**No design-system migration in this phase.** All tokens, palette references, and fonts are inherited from prior phases unchanged.

---

## Spacing Scale

**No new spacing values.** The new label lives inside the existing `NowPlayingPanel` center-column `QVBoxLayout` which already declares `setSpacing(8)` (`now_playing_panel.py:151`). Inserting a widget into that layout yields automatic 8px vertical gap above (from `name_provider_label`) and below (to `icy_label`) — **no `setContentsMargins` or per-widget spacing override is added**.

| Token | Value | Existing usage (unchanged) | Phase 64 use |
|-------|-------|----------------------------|--------------|
| sm | 8px | `center.setSpacing(8)` (`now_playing_panel.py:151`) | Implicit gap above and below new sibling label |
| md | 16px | `outer.setContentsMargins(16, 16, 16, 16)` (`now_playing_panel.py:135`) | Inherited; the new label's left edge aligns with `name_provider_label`'s left edge |

Larger tokens (`lg`/`xl`/`2xl`/`3xl`) exist in the Phase 37 scale but are **not exercised by this phase** and are not introduced here.

Exceptions: none. Phase 64 changes zero spacing values.

---

## Typography

**No new typography roles.** The new sibling label inherits the Qt platform default font (no `setFont` call). This matches Phase 51's `EditStationDialog._sibling_label` (verified at `edit_station_dialog.py:405-411` — no `setFont`), preserving visual parity across surfaces.

| Role | Size | Weight | Line Height | Source — unchanged |
|------|------|--------|-------------|--------------------|
| Body (sibling link text) | Qt platform default (~10pt on Linux X11 DPR=1.0) | Normal (400) | platform default | Phase 37 §Typography Body — inherited via no-`setFont` policy |
| Label (Name · Provider — sibling line is a continuation of the station-identity tagline) | 9pt | Normal (400) | platform default | `now_playing_panel.py:155-159` (unchanged; the sibling label is read-order-adjacent to it) |
| Heading (ICY title — visually below the sibling line) | 13pt | DemiBold (600) | platform default | `now_playing_panel.py:163-170` (unchanged) |
| Body (elapsed timer) | 10pt | Normal (400) + `QFont.TypeWriter` style hint | platform default | `now_playing_panel.py:174-179` (unchanged) |

**Decision: default font (no `setFont`) for the new sibling label** — RESEARCH §Pattern 2 / Assumption A1 default; CONTEXT-prompt-flagged choice resolved in favor of **default (link-text-readable size)** over 9pt-`name_provider_label`-parity. Rationale: Qt's default `<a>` link styling reads cleanly at platform body size; Phase 51's dialog version uses default font and shipped through UAT. If the planner-ux-reviewer prefers 9pt parity to make the line read as a lighter sub-tagline, it is a 3-line `QFont` override the executor can add without affecting any other contract — **but the default is locked here** to keep visual parity with Phase 51.

**Font count:** 4 roles (already declared in Phase 37). 2 weights (Normal + DemiBold). No third weight, no italics.

---

## Color

**No new color usage.** The new sibling label renders inline `<a href="sibling://{id}">…</a>` HTML; Qt resolves the link color from the platform `QPalette`'s `Link` role. The project does not set a custom `Link` color anywhere in `_theme.py` or via `QPalette.setColor(Link, ...)` — verified by absence of any `QPalette.Link` reference in the codebase.

| Role | Value | Phase 64 use |
|------|-------|--------------|
| Dominant (60%) | `QPalette.Window` (Fusion `#353535` on dark; system default on light) | Panel background — inherited unchanged |
| Secondary (30%) | `QPalette.Base` / `QPalette.AlternateBase` | Not touched by this phase |
| Accent (10%) | `QPalette.Highlight` (`#2A82DA` on Fusion dark; system accent on Linux) | **NOT used by the sibling line** — links are not accent-colored |
| Link | `QPalette.Link` (Fusion default `#0094ff`-ish on dark; system browser-link blue on Linux) | **The sibling link text inherits this role from Qt — zero override** |
| LinkVisited | `QPalette.LinkVisited` (system default) | Inherited; sibling links may render as "visited" after a click in some platform palettes — accepted as platform behavior, not contracted |
| Destructive | `ERROR_COLOR_HEX = "#c0392b"` (`_theme.py:32`) | Not used in this phase |

**Accent reserved for** (unchanged from Phase 37): selected station row highlight, volume slider groove fill, play/pause button pressed state, keyboard focus ring. Phase 64 introduces zero new accent usage — **the sibling link is `QPalette.Link`, not `QPalette.Highlight`**.

**Hover state:** Qt's default `<a>` hover behavior (cursor change + underline depending on platform) is the contract. No custom `:hover` QSS, no animation.

---

## Component Inventory

| Component | Status | Source-of-truth file:line |
|-----------|--------|---------------------------|
| `QLabel` (the new "Also on: …" sibling line) | **NEW — `self._sibling_label`** | (new in `musicstreamer/ui_qt/now_playing_panel.py`) |
| `Signal(object)` (`sibling_activated`) | **NEW** | (new in `now_playing_panel.py`, declared next to existing `edit_requested = Signal(object)` at line 112) |
| `_refresh_siblings()` (private method) | **NEW** | (new in `now_playing_panel.py`; called from `bind_station` after `_populate_stream_picker` per CONTEXT D-04) |
| `_on_sibling_link_activated(href)` (private slot) | **NEW** | (new in `now_playing_panel.py`; bound-method-connected to `_sibling_label.linkActivated`) |
| `_on_sibling_activated(Station)` (`MainWindow` slot) | **NEW** | (new in `main_window.py`, alongside existing `_on_edit_requested`) |
| `render_sibling_html(siblings, current_name)` (free function) | **NEW (promoted from Phase 51 verbatim per CONTEXT D-03)** | `musicstreamer/url_helpers.py` — body lifted from `edit_station_dialog.py:531-574` |
| `name_provider_label` (`QLabel`, 9pt Normal) | Existing — read-order neighbor above the new sibling label | `now_playing_panel.py:155-161` (unchanged) |
| `icy_label` (`QLabel`, 13pt DemiBold) | Existing — read-order neighbor below the new sibling label | `now_playing_panel.py:163-171` (unchanged) |
| `_sibling_label` on `EditStationDialog` (Phase 51) | Existing — independently rendered by the same shared `render_sibling_html` | `edit_station_dialog.py:405-411` (unchanged in Phase 64; only the renderer call site at line 608 updates from `self._render_sibling_html(...)` to `render_sibling_html(...)`) |

### New `QLabel` Configuration (locked, mirrors Phase 51 verbatim)

The exact configuration block — five lines plus the `addWidget` insertion — must match the Phase 51 dialog version (`edit_station_dialog.py:405-411`) so the two surfaces render identically:

```python
self._sibling_label = QLabel("", self)
self._sibling_label.setTextFormat(Qt.RichText)              # T-39-01 deviation; mitigated by html.escape in renderer
self._sibling_label.setOpenExternalLinks(False)             # links are intra-app navigation, not URLs
self._sibling_label.setVisible(False)                       # D-05: hidden when empty (zero vertical space)
self._sibling_label.linkActivated.connect(self._on_sibling_link_activated)  # bound-method per QA-05
center.addWidget(self._sibling_label)
```

**Layout insertion:** Inline construction in visual order, between `center.addWidget(self.name_provider_label)` (existing line 161) and the ICY label block (existing lines 163-171). Equivalent to `center.insertWidget(1, self._sibling_label)` — RESEARCH §Pattern 2 confirmed both work; **inline construction is the locked choice** because it matches the existing in-file convention (every other widget in `__init__` is constructed in visual order via `addWidget`).

**Text-interaction flags:** Not explicitly set. Qt's default for a `QLabel` with `setTextFormat(Qt.RichText)` is `Qt.LinksAccessibleByMouse` enabled by default; keyboard accessibility (`Qt.LinksAccessibleByKeyboard`) is **not** enabled by default and is not added by this phase — Phase 51's dialog version does not enable it either, so this is parity. Keyboard-only sibling activation is deferred to a future phase (CONTEXT.md §Deferred Ideas: "Keyboard shortcut for sibling jump").

---

## Interaction Contract

This is the only dimension with substantive Phase 64 content. Two distinct event boundaries (A — click-to-play; B — refresh-on-bind-only) plus an ancillary delegation contract from `MainWindow`.

### Boundary A — Sibling click → switch playback

**Precondition (state machine):** An AA station X is bound and playing. `find_aa_siblings` returned ≥1 sibling. `self._sibling_label` is visible and contains rendered HTML (e.g., `Also on: <a href="sibling://7">ZenRadio</a>`).

**Trigger:** User mouse-clicks on the rendered link. (Default Qt behavior for `QLabel` + `Qt.RichText` + `linkActivated` — no keyboard activation in this phase.)

**Slot fires:** `NowPlayingPanel._on_sibling_link_activated(href: str)` runs on the main thread (queued from Qt's event loop). The slot must execute to completion synchronously and never raise (Qt slots-never-raise contract — RESEARCH Pitfall #2).

**Step-by-step contract** (load-bearing for the executor and tests):

1. **Parse `href`:**
   - `if not href.startswith("sibling://"): return` — silent no-op for malformed prefix.
   - `try: sibling_id = int(href[len("sibling://"):]) except ValueError: return` — silent no-op for non-integer payload.
2. **D-08 defense-in-depth no-op guard:**
   - `if self._station is None or self._station.id == sibling_id: return` — covers (a) panel never bound, (b) renderer staleness re-emitting the bound station's own id (theoretically unreachable since `find_aa_siblings` excludes self at `url_helpers.py:122`, locked by SC #5).
3. **Repo lookup with dual-shape exception handling** (RESEARCH Pitfall #2):
   - Production `Repo.get_station` raises `ValueError` on missing id (`repo.py:271`); some test doubles (`MainWindow.FakeRepo`) return `None`. Wrap in `try: sibling = self._repo.get_station(sibling_id) except Exception: return` — silent no-op. Then `if sibling is None: return`.
4. **Emit signal:** `self.sibling_activated.emit(sibling)` — `Signal(object)` payload (resolved `Station`, not int id; mirrors `edit_requested(Station)` shape).

**`MainWindow._on_sibling_activated(station: Station)` delegation contract:**

The slot is a thin delegator: `self._on_station_activated(station)`. CONTEXT D-02 default; locked unless the planner finds a behavior divergence (none expected — RESEARCH Assumption A2).

This means **the side-effect set is identical** to "user clicked a station in the station list":

| Side effect | Source | Verifiable via |
|-------------|--------|----------------|
| `self.now_playing.bind_station(sibling)` | `MainWindow._on_station_activated` | Panel's `_station` attribute updated |
| `self._player.play(sibling)` | `MainWindow._on_station_activated` | `Player.play_calls` spy |
| `self._repo.update_last_played(sibling.id)` | `MainWindow._on_station_activated` | `Repo._last_played_ids` spy |
| `self.station_panel.refresh_recent()` | `MainWindow._on_station_activated` (Phase 50 wiring) | `StationListPanel.refresh_recent_calls` spy |
| `self.show_toast("Connecting…")` (U+2026 ellipsis, Phase 37 copy) | `MainWindow._on_station_activated` | `MainWindow.toast_messages` spy |
| `self._media_keys.publish_metadata(...)` + `set_playback_state('playing')` | `MainWindow._on_station_activated` | `media_keys.metadata_calls` spy |

**Toast wording is locked to the existing "Connecting…"** — no separate "Switched to ZenRadio" toast, no "Switching…" preamble. RESEARCH Open Question #1 resolved in favor of D-02 default.

**Postcondition (state machine):** Panel is re-bound to the sibling Station. Audio transitions cleanly (`Player.play` clears the previous stream queue and starts the new one — no explicit `Player.stop()` call before `Player.play(sibling)`; verified at `player.py:255-285`). The sibling line is **re-rendered for the NEW bound station's siblings**, which may be different (D-04 `_refresh_siblings` runs again inside `bind_station`, automatically picking up the new station's network and excluding it from the new sibling list).

**Re-rendering after a click is automatic by D-04** — no extra wiring needed; the same `bind_station` → `_refresh_siblings` chain that runs on the initial activation runs on the sibling-click activation.

### Boundary B — Refresh trigger (D-04 invariant)

**Single load-bearing invariant:** `_refresh_siblings()` runs **only** inside `NowPlayingPanel.bind_station(station)`, immediately after `self._populate_stream_picker(station)` (existing line 344). It does NOT subscribe to `Repo.station_saved`, `Repo.station_deleted`, discovery-import-complete, or any other library-mutation signal.

**Three trigger paths into `bind_station` already exist** — Phase 64 reuses all three, not a fourth:

| Trigger path | Call site | Resulting `_refresh_siblings` behavior |
|--------------|-----------|----------------------------------------|
| (1) Station list double-click / row activation | `MainWindow._on_station_activated` (`main_window.py:316-326`) → `now_playing.bind_station(station)` | Re-derive siblings for the newly-activated station |
| (2) Sibling link click (Phase 64 — this phase) | `NowPlayingPanel._on_sibling_link_activated` → emit `sibling_activated(Station)` → `MainWindow._on_sibling_activated(Station)` → `_on_station_activated(Station)` → `now_playing.bind_station(Station)` | Re-derive siblings for the newly-jumped-to sibling (its own self-id is now excluded; original station is now potentially in the new list) |
| (3) Edit-save sync re-bind | `MainWindow._sync_now_playing_station` (post-Phase 51 wiring) → `now_playing.bind_station(updated_station)` | Re-derive siblings for the (possibly URL-changed) updated station |

**Negative contract (must NOT happen):**
- `_refresh_siblings()` MUST NOT be wired to `Repo.station_saved` or any equivalent mutation signal. (Verifiable by spy: `pytest tests/test_now_playing_panel.py::test_refresh_siblings_runs_once_per_bind` per RESEARCH §Validation Architecture.)
- `_refresh_siblings()` MUST NOT be called from `_populate_stream_picker`, `on_title_changed`, `on_elapsed_updated`, `_on_play_pause_clicked`, `_on_stop_clicked`, or any other internal slot. The only legal call site is the line directly after `self._populate_stream_picker(station)` inside `bind_station`.

**Race / ordering contract:**
1. `bind_station(station)` runs (sets `self._station = station`).
2. `_populate_stream_picker(station)` runs (sets `self._streams`).
3. `_refresh_siblings()` runs — reads `self._station.streams[0].url` (D-06; with empty-streams defensive fallback) and `self._repo.list_stations()`.
4. The label is updated atomically: either `(setText(html), setVisible(True))` or `(setText(""), setVisible(False))` — no intermediate visible-but-empty state.

**Animation / motion contract:** None. `setVisible(True/False)` is instantaneous in Qt's layout system. The user perceives the line as appearing/disappearing in the same frame as the new station's name and provider tag — the panel does not "shimmer" or "fade" the sibling line in or out.

**Hidden-when-empty (D-05) — four trigger cases:**

| Case | `_refresh_siblings` outcome |
|------|----------------------------|
| `self._station is None` (panel not bound) | `setVisible(False)`; label text cleared |
| `self._station.streams` is empty | `setVisible(False)`; label text cleared |
| Bound station is non-AA (URL fails `_is_aa_url` inside `find_aa_siblings`) — `find_aa_siblings` returns `[]` | `setVisible(False)`; label text cleared |
| Bound AA station has no other AA stations on different networks sharing the channel key — `find_aa_siblings` returns `[]` | `setVisible(False)`; label text cleared |

**Zero vertical space** is guaranteed by `QVBoxLayout`'s default behavior: a hidden child contributes `sizeHint.height() == 0`. No `setSizePolicy` override needed.

### Boundary separation guarantee

The single-line load-bearing invariants the executor must preserve:

> 1. **`_refresh_siblings()` runs exactly once per `bind_station(station)` call, and from no other call site.** (D-04 / SC enforcement)
> 2. **The sibling-click-to-play path delegates to `_on_station_activated` — the same canonical "user picked a station" side-effect set fires regardless of where the activation came from.** (D-02)
> 3. **The visible string format is produced by `render_sibling_html` (free function in `url_helpers.py`) — both `EditStationDialog._refresh_siblings` and `NowPlayingPanel._refresh_siblings` call the same renderer.** (D-03)

Spy-based regression tests are required for (1) and the negative half of (2). RESEARCH §Validation Architecture lists the specific test commands.

---

## Copywriting Contract

**No new strings.** All visible text is produced from existing constants at runtime.

| Element | Copy | Source | Status |
|---------|------|--------|--------|
| Sibling line prefix | `Also on: ` (with single trailing space) | Hardcoded in `render_sibling_html` (Phase 51 D-07; preserved verbatim per Phase 64 D-03) | Inherited from Phase 51 |
| Sibling separator | ` • ` (space + U+2022 BULLET + space) | Hardcoded in `render_sibling_html` (Phase 51 D-07) | Inherited from Phase 51 |
| Network display name | `ZenRadio`, `JazzRadio`, `RockRadio`, `Classical Radio`, `RadioTunes`, `DI` (whatever) | `NETWORKS` constant in `aa_import.py:87` (`name` field) | Inherited from Phase 17 |
| Name-mismatch separator | ` — ` (space + U+2014 EM DASH + space) | Hardcoded in `render_sibling_html` (Phase 51 D-08) | Inherited from Phase 51 |
| Sibling station name (when name differs from current) | `{station.name}` passed through `html.escape(name, quote=True)` | Renderer mitigation (T-39-01 deviation) | Inherited from Phase 51 |
| Toast on sibling-click | `Connecting…` (U+2026 ellipsis) | `MainWindow._on_station_activated`'s existing toast call (Phase 37 §Copywriting) | Inherited from Phase 37 — no new toast added |
| Primary CTA | n/a — the sibling link itself is the activation; no button | n/a | n/a |
| Empty state heading | n/a — phase relies on hidden-when-empty (D-05); no placeholder copy | n/a | n/a |
| Empty state body | n/a | n/a | n/a |
| Error state | n/a — `_on_sibling_link_activated` is silently no-op on every failure path (malformed href, missing station, repo error) per D-08 + RESEARCH Pitfall #2 | n/a | n/a |
| Destructive confirmation | n/a — sibling click does NOT confirm; it is a deliberate one-click switch (analog to picking from the station list, which also does not confirm) | n/a | n/a |
| Tooltip on the sibling label | none — Qt's default `<a>` cursor change is the affordance (matches Phase 51 dialog version) | n/a | Inherited from Phase 51 |

**Specifically excluded (RESEARCH Open Question #1 resolved):** No "Switched to ZenRadio" distinct toast. No "Switching…" preamble. No mid-action toast difference vs. the station-list activation path. The sibling-click toast is exactly `Connecting…` — the same toast that fires from a station-list click — for two reasons: (a) one canonical user-feedback string per "user picked a station" event, and (b) ship-D-02-default discipline.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| n/a | none — desktop Qt/PySide6 application; no shadcn, no third-party UI registry, no new dependency | not applicable |

Phase 64 introduces zero new packages. RESEARCH §Standard Stack confirms the only new module-level import is `import html` in `url_helpers.py` (stdlib; needed by the promoted renderer because `url_helpers.py` does not currently import it — verified by grep). All other behavior reuses existing PySide6, pytest, pytest-qt, and project-internal symbols.

---

## Acceptance & Dimension Mapping

This phase's "design" is dominated by **interaction / state contract**. The six checker dimensions resolve as follows:

| Dimension | Verdict | Evidence |
|-----------|---------|----------|
| Visual fidelity | **PASS** | One new widget; visual format inherited verbatim from Phase 51 via shared renderer. Pixel-level diff = "same line, new surface." |
| Layout | **PASS** | Inline construction in visual order in `NowPlayingPanel.__init__`'s center-column block, between `name_provider_label` and `icy_label`. Inherits 8px vertical rhythm from `center.setSpacing(8)`. No new margins, no `setSizePolicy`. |
| Typography | **PASS** | Default Qt platform font (no `setFont`) — parity with Phase 51 dialog version. Decision locked: not 9pt-`name_provider_label`-parity; planner may revisit only if visual review demands sub-tagline weight. |
| Color | **PASS** | Inherits `QPalette.Link` (platform default link color). No theme-token read, no `_theme.py` change, no `setStyleSheet`. |
| Spacing | **PASS** | Zero new spacing values — pure inheritance from existing `center.setSpacing(8)` + outer 16px margins. |
| Interaction / state | **The substance of this phase** — see §Interaction Contract above. Boundary A (click-to-play) delegates to canonical `_on_station_activated`; Boundary B (refresh-on-bind-only) is the load-bearing invariant. Both contracts have spy-based test mappings in RESEARCH §Validation Architecture. |
| Registry Safety | **n/a** | No third-party UI registry, no new package. |

The auditor's job at phase close: confirm that (a) the "Also on:" line on `NowPlayingPanel` and the line on `EditStationDialog` produce byte-equal HTML for the same `(siblings, current_name)` input (both call `render_sibling_html` — single source of rendering); (b) clicking a sibling on `NowPlayingPanel` switches active playback (SC #2); (c) clicking a sibling on `EditStationDialog` continues to navigate the editor only (Phase 51 D-09 / D-10 unchanged); (d) `_refresh_siblings` is reachable only from `bind_station` (negative spy lock).

---

## Brand / Style References

- **`musicstreamer/ui_qt/_theme.py`** — three exposed tokens (`ERROR_COLOR_HEX`, `ERROR_COLOR_QCOLOR`, `STATION_ICON_SIZE`); none are read by Phase 64.
- **Phase 51 `EditStationDialog._sibling_label`** (`edit_station_dialog.py:405-411`) — the visual contract Phase 64 mirrors. The same configuration block (`Qt.RichText`, `setOpenExternalLinks(False)`, `setVisible(False)`, `linkActivated.connect`) appears unchanged on the new panel widget.
- **Phase 51 renderer body** (`edit_station_dialog.py:531-574`, becoming `url_helpers.py::render_sibling_html` in Phase 64) — the source of the U+2022 / U+2014 / "Also on: " / `html.escape` shape.
- **No external design references** — no Figma, no ADR, no third-party design system. Phase fully captured by Phase 51 precedent + the five SC in ROADMAP §Phase 64.

**Sketch findings:** None. No design sketches were produced for this phase; the visual contract is fully derived from Phase 51's shipped UAT.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS — no new strings; sibling line text produced from `NETWORKS` constant + runtime data via shared `render_sibling_html`; toast wording inherits `Connecting…` from `_on_station_activated`
- [ ] Dimension 2 Visuals: PASS — one new `QLabel` (`self._sibling_label`); configuration block mirrors Phase 51 dialog version verbatim
- [ ] Dimension 3 Color: PASS — inherits `QPalette.Link` for sibling link color; zero `_theme.py` read; no custom QSS
- [ ] Dimension 4 Typography: PASS — default Qt platform font (no `setFont`); decision locked over 9pt-parity alternative
- [ ] Dimension 5 Spacing: PASS — inherits `center.setSpacing(8)` 8px vertical rhythm; zero new spacing values
- [ ] Dimension 6 Registry Safety: PASS — n/a (desktop Qt/PySide6, no third-party UI registry)
- [ ] Dimension 7 Interaction (project-specific weight for this phase): the click-to-play delegation contract (Boundary A) and the refresh-on-bind-only invariant (Boundary B) are fully documented and testable; spy-based regression locks specified in RESEARCH §Validation Architecture

**Approval:** pending

---

## UI-SPEC COMPLETE

Phase 64 adds one new `QLabel` (`self._sibling_label`) to `NowPlayingPanel`'s center column, inheriting Phase 51's visual sibling-line contract verbatim via the promoted free-function renderer `render_sibling_html` in `url_helpers.py`. The substantive design dimension is **interaction / state**: click-to-play delegates to `MainWindow._on_station_activated` (one canonical "user picked a station" side-effect set), and `_refresh_siblings` runs only inside `bind_station` (no library-mutation subscription) — both contracts spy-lockable per RESEARCH §Validation Architecture. All non-interaction dimensions reduce to "no change — reuse Phase 37 / Phase 51 tokens."
