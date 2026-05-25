---
phase: 51-audioaddict-cross-network-siblings
plan: 03
subsystem: ui
tags: [pyside6, qdialog, qlabel, rich-text, sibling-list, html-escape, audioaddict, t-39-01-deviation]

# Dependency graph
requires:
  - phase: 51
    plan: 01
    provides: find_aa_siblings(stations, current_id, current_url) -> list[(slug, id, name)]
  - phase: 51
    plan: 02
    provides: EditStationDialog._capture_dirty_baseline / _is_dirty / _snapshot_form_state
  - phase: 17-audioaddict-import
    provides: NETWORKS catalog (slug -> display name)
provides:
  - EditStationDialog._sibling_label QLabel (Qt.RichText, hidden by default)
  - EditStationDialog._refresh_siblings() — _populate hook reading repo.list_stations() into the label
  - EditStationDialog._render_sibling_html(siblings, current_name) — pure HTML builder with html.escape mitigation
  - 6 pytest-qt tests pinning hide/show, link-text format, and HTML-escape contract
affects:
  - 51-04 (linkActivated wiring — connects _sibling_label.linkActivated -> _on_sibling_link_activated -> dirty-confirm + navigate_to_sibling signal)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Qt.RichText QLabel with inline <a href> links (project-first, T-39-01 deviation)"
    - "html.escape(name, quote=True) at the rendering boundary as the T-39-01 mitigation"
    - "U+2022 BULLET separator with surrounding spaces; U+2014 EM DASH for the differing-name link form (D-07, D-08)"
    - "isHidden()-based widget-state tests (avoids WM-dependence of isVisible() for unshown dialogs)"

key-files:
  created:
    - .planning/phases/51-audioaddict-cross-network-siblings/51-03-SUMMARY.md
  modified:
    - musicstreamer/ui_qt/edit_station_dialog.py
    - tests/test_edit_station_dialog.py

key-decisions:
  - "Qt.RichText QLabel with inline <a href> is the standard Qt idiom for clickable text spans. Mitigated by html.escape on every Station.name interpolation (T-39-01 deviation, locally bounded to one QLabel)."
  - "Network display names come from the NETWORKS compile-time constant — no runtime escape needed. Only Station.name is user-controllable and must pass through html.escape."
  - "href payload is integer-only ('sibling://{station_id}') — type system bounds prevent string injection in this position. Plan 51-04 will further validate via int() in the linkActivated slot."
  - "Sibling refresh hooked at end of _populate AFTER _capture_dirty_baseline. The label visibility change is not in the dirty-snapshot scope, so order is symmetric with _refresh_logo_preview (both are derived UI state, not user-edit state)."
  - "Tests use isHidden() rather than isVisible() because qtbot.addWidget does not actually show the dialog and isVisible() depends on WM-level visibility. isHidden() reflects the explicit setVisible(True/False) state directly."
  - "W4 fix: existing `repo` MagicMock fixture in tests/test_edit_station_dialog.py:33-46 explicitly sets list_stations.return_value=[] so pre-existing tests deterministically hit the no-siblings path."

patterns-established:
  - "Project-first Qt.RichText QLabel — documented as T-39-01 deviation with html.escape mitigation. Future RichText labels must follow the same pattern: explicit deviation comment + html.escape on every untrusted interpolation."
  - "Three-method shape for inline-rendered widgets (mirrors Plan 51-02's dirty-state shape): _refresh_X (hooked from _populate) + _render_X_html (pure helper) + setVisible(False) initial."

requirements-completed: []  # BUG-02 advances but does not close — Plan 51-04 ships the click handler that delivers SC #2.

# Metrics
duration: 8min
completed: 2026-04-28
---

# Phase 51 Plan 03: EditStationDialog cross-network sibling list Summary

**Visible "Also on: ZenRadio • JazzRadio" RichText QLabel added to `EditStationDialog`, hidden when non-AA or no siblings, rendering hooked from `_populate` after the dirty-state baseline.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-28T15:08:36Z
- **Completed:** 2026-04-28T15:17:30Z
- **Tasks:** 2 / 2
- **Files modified:** 2 (musicstreamer/ui_qt/edit_station_dialog.py +118 lines, tests/test_edit_station_dialog.py +184 lines including W4 fixture line)

## Accomplishments

- **`_sibling_label` QLabel** — first `Qt.RichText` QLabel in the project. Configured with `setOpenExternalLinks(False)` and `setVisible(False)` default. Inserted in `_build_ui` immediately above `outer.addWidget(self.button_box)` so the layout sequence is `[..., form, _sibling_label, button_box]` (D-05).
- **`_render_sibling_html(siblings, current_name) -> str`** — pure helper that builds `'Also on: <a href="sibling://2">ZenRadio</a> • <a href="sibling://5">JazzRadio</a>'`. Applies `html.escape(name, quote=True)` on every `Station.name` interpolated into the HTML (T-39-01 deviation mitigation). Network display names come from `NETWORKS` compile-time constant. Bullet `' • '` (U+2022 with surrounding spaces) separator. Em-dash `' — '` (U+2014 with surrounding spaces) only in the differing-names "Network — SiblingName" link-text form (D-07, D-08).
- **`_refresh_siblings()`** — appended to the end of `_populate` AFTER `_capture_dirty_baseline()`. Reads `self.url_edit.text().strip()`, calls `self._repo.list_stations()`, delegates to `find_aa_siblings()`, and either populates the label HTML + `setVisible(True)` or `setVisible(False)` + clear. Hidden-when-empty (D-06) covers all three cases: non-AA station, AA station with no derivable channel key, AA station with no other AA stations on other networks sharing the key.
- **W4 fix** — existing `repo` MagicMock fixture in `tests/test_edit_station_dialog.py:33-46` got an explicit `r.list_stations.return_value = []` so pre-existing tests deterministically hit the no-siblings path through the new `_refresh_siblings` call (rather than relying on MagicMock auto-iteration of an unset return value).
- **6 pytest-qt tests** added pinning the rendering contract: hide-for-non-AA, hide-when-no-siblings, render-with-siblings, name-match link text, name-differ link text with U+2014 em-dash, html.escape mitigation for `<script>alert(1)</script>` station names.

## Widget placement

```
outer = QVBoxLayout
  ├─ logo_row                                  (existing)
  ├─ form                                      (existing — name, url, provider, tags, ICY, streams)
  ├─ self._sibling_label  (NEW — Phase 51-03)  ← inserted here
  └─ self.button_box                           (existing — moved one line down)
```

## Render shape

For an AA station "Ambient" with two cross-network siblings (matching name on ZenRadio, differing name on JazzRadio):

```html
Also on: <a href="sibling://2">ZenRadio</a> • <a href="sibling://5">JazzRadio — Ambient (Sleep)</a>
```

- `Also on:` literal prefix.
- Bullet separator is `' • '` (space + U+2022 + space).
- Each href is `sibling://{integer_station_id}` — integer only; non-injectable.
- Link text is the network display name (D-08 matching-names form) or `"Network — Name"` with U+2014 EM DASH (D-08 differing-names form).
- Station names HTML-escaped via `html.escape(name, quote=True)`.

## T-39-01 Deviation — documented and mitigated

`_sibling_label` is the **first `QLabel` in the project to use `Qt.RichText`** — every other label uses `Qt.PlainText` per T-39-01. The deviation is required to render inline `<a href>` links (the standard Qt idiom for clickable text spans inside a non-button widget). The deviation is documented in three places:

1. **Inline source comment at the widget construction site** (`_build_ui`, around line 388–400):
   ```python
   # First QLabel in the project to use Qt.RichText (deviation from
   # T-39-01) — required for inline <a href> links. Mitigation:
   # html.escape on every Station.name interpolation inside
   # _render_sibling_html. Network display names come from the
   # NETWORKS compile-time constant and need no escaping; the href
   # payload is integer-only ("sibling://{id}") so it cannot carry
   # injectable content. Hidden until populated with siblings (D-06).
   ```

2. **`_render_sibling_html` docstring** explicitly calls out the security contract: "every Station.name interpolated into the HTML is passed through html.escape(name, quote=True) (T-39-01 deviation mitigation). Network display names come from the NETWORKS compile-time constant and need no escape. The href payload is integer-only ('sibling://{id}') so it cannot carry injectable content."

3. **`test_sibling_html_escapes_station_name`** — dedicated test asserts a malicious `<script>alert(1)</script>` station name renders as `&lt;script&gt;alert(1)&lt;/script&gt;` and that the raw `<script>` tag does NOT appear in the rendered text.

The deviation is **bounded to ONE QLabel in ONE dialog** — every other QLabel in the project remains `Qt.PlainText`. Verified by `grep -rn "Qt.RichText" musicstreamer/ui_qt/` returning exactly two lines (the comment + the actual `setTextFormat(Qt.RichText)` call), both inside `edit_station_dialog.py`.

## Task Commits

1. **Task 1: Production code** — `bc47a6e` (feat): import html / NETWORKS / find_aa_siblings; insert _sibling_label widget above button_box; add _render_sibling_html + _refresh_siblings methods; hook _refresh_siblings at end of _populate; W4 fixture update.
2. **Task 2: Tests** — `f7c2cc5` (test): _make_aa_station factory + aa_repo / aa_station / aa_dialog fixtures; 6 new sibling-rendering tests.

_Plan metadata commit follows separately._

## Files Created/Modified

- `musicstreamer/ui_qt/edit_station_dialog.py` (+118 lines, 0 deletions):
  - Module top: `import html`, `from musicstreamer.aa_import import NETWORKS`, `from musicstreamer.url_helpers import find_aa_siblings`.
  - `_build_ui` end: `self._sibling_label = QLabel("", self)` + 3 setters + `outer.addWidget(self._sibling_label)` immediately before the existing `outer.addWidget(self.button_box)`.
  - `_populate` end: `self._refresh_siblings()` after `self._capture_dirty_baseline()`.
  - New section "Phase 51-03 / D-04..D-08 — cross-network sibling list (BUG-02)" between `_is_dirty` and `_make_chip` containing `_render_sibling_html` and `_refresh_siblings`.
- `tests/test_edit_station_dialog.py` (+184 lines, 0 deletions):
  - Existing `repo` fixture: added explicit `r.list_stations.return_value = []` (W4 fix).
  - New section "Phase 51-03 / D-04..D-08 — cross-network 'Also on:' sibling label" appended to file with `_make_aa_station` factory, `aa_repo` / `aa_station` / `aa_dialog` fixtures, and 6 tests.

## Decisions Made

- **Qt.RichText QLabel with inline `<a href>` is the standard Qt idiom** — chosen over QTextBrowser / custom widget because it is the minimal/native solution for clickable text spans in a dialog. The T-39-01 deviation is bounded to ONE QLabel and mitigated by `html.escape` at the rendering boundary.
- **Tests use `isHidden()` rather than `isVisible()`** — Plan-as-written specified `assert d._sibling_label.isVisible() is True`, but pytest-qt's `qtbot.addWidget` does not actually show the dialog. `isVisible()` returns False even when `setVisible(True)` was called if the parent widget isn't shown by the WM. `isHidden()` reflects the explicit `setVisible(True/False)` state directly, which is exactly what the rendering contract specifies. Documented in test docstrings. (Treated as a minor in-test-only adjustment; production code is unchanged from the plan.)
- **`_refresh_siblings` hooked AFTER `_capture_dirty_baseline`** — the sibling-label visibility/content is not in the dirty-snapshot scope (per Plan 51-02's `_snapshot_form_state` which covers only name/URL/provider/tags/ICY/streams). Order is symmetric with `_refresh_logo_preview` (both are derived UI state, not user-edit state) and matches the plan's instruction.
- **Bullet U+2022 and em-dash U+2014 — embedded literally in the Python source** rather than as `•` / `—` escapes. The file has `from __future__ import annotations` and is UTF-8 (project convention). Using the literal characters keeps the source readable and tests assert the literal characters as well. Verified portable by `grep`-matching the literals.
- **W4 fix uses one line: `r.list_stations.return_value = []`** — the absolute minimum to make the existing fixture deterministic when the new `_refresh_siblings → repo.list_stations()` call is added. Tests that need siblings (the new `aa_repo` fixture) override the value.

## Deviations from Plan

**1. [Rule 1 — Bug] Tests changed `isVisible()` -> `isHidden()` for visibility assertions**
- **Found during:** Task 2 verification — `test_sibling_section_renders_links_for_aa_station_with_siblings` failed with `assert False is True` on `d._sibling_label.isVisible()`.
- **Issue:** `qtbot.addWidget` does not show the dialog; `isVisible()` reports False on a widget whose top-level parent has not been shown by the windowing system, even when `setVisible(True)` was called. The plan's test specifications used `isVisible()` which produced false-negative test failures.
- **Fix:** Switched the visibility assertions to `isHidden()` (which directly reflects the explicit `setVisible(True/False)` state regardless of whether the parent is shown). Production code is unchanged. Test docstrings document why isHidden is used.
- **Files modified:** `tests/test_edit_station_dialog.py` (3 sibling tests use `isHidden()`).
- **Commit:** `f7c2cc5`

No other deviations — production code (Task 1) executed exactly as written.

## Authentication Gates

None — pure UI/data flow with no external services.

## Issues Encountered

- **Pre-existing flaky timer test** — `tests/test_edit_station_dialog.py::test_logo_status_clears_after_3s` is a 3-second `qtbot.wait()`-based test with documented ~20-30% spurious failure rate (per Plan 51-02 SUMMARY). Reproduced once during Task 1 verification on this hardware; subsequent runs of the full file pass deterministically (46/46). Out of scope for Phase 51 per executor scope-boundary rule. Already logged in Plan 51-02's deferred-items section.
- **Pre-existing `gi`/PyGObject environment gap** — running the full unit suite via `uv run --with pytest --with pytest-qt` triggers `ModuleNotFoundError: No module named 'gi'` in `tests/test_player_*.py`, `tests/test_media_keys_*.py`, `tests/test_twitch_*.py`, `tests/test_headless_entry.py`, `tests/test_cookies.py`, `tests/test_windows_palette.py`. Documented in Plan 51-02's deferred-items.md as a phase-level test-extras concern. Not a regression from Plan 51-03.
- **`uv.lock` modified by `uv run`** — the `--with pytest --with pytest-qt` flags refresh `uv.lock` (also noted in Plan 51-01 SUMMARY). Reverted with `git checkout -- uv.lock` before each commit; not committed as part of this plan.

## Verification Log

- `uv run --with pytest --with pytest-qt pytest tests/test_edit_station_dialog.py -v` — **46 passed in 3.46s** (40 existing + 6 new sibling tests).
- `uv run --with pytest --with pytest-qt pytest tests/test_edit_station_dialog.py -k "sibling"` — **6 passed, 40 deselected in 0.24s**.
- `uv run --with pytest --with pytest-qt pytest tests/test_aa_siblings.py tests/test_aa_url_detection.py` — **27 passed in 0.08s** (Wave 1 helpers and url-helper tests still green).
- `grep -rn "Qt.RichText" musicstreamer/ui_qt/` — exactly **2 matches** in `edit_station_dialog.py` (1 comment + 1 actual `setTextFormat(Qt.RichText)` call). Confirms project-first deviation is bounded to one QLabel.
- `grep -rcn "setTextFormat(Qt.PlainText)" musicstreamer/ui_qt/` — existing PlainText labels unchanged across 5 other UI files (favorites_view, accent_color_dialog, now_playing_panel, cookie_import_dialog, settings_import_dialog).

## TDD Gate Compliance

This plan's frontmatter is `type: execute` (not `type: tdd`), so the plan-level RED/GREEN/REFACTOR gate is not enforced. Both task-level commits use the conventional types per the plan's commit-message templates:
- Task 1: `feat(51-03): ...` (production code).
- Task 2: `test(51-03): ...` (tests added).

All 6 new tests pass against the production code from Task 1. The plan structures Task 1 (production) before Task 2 (tests) — which is acceptable for `type: execute` plans (the plan's tdd attribute on each task is descriptive, not prescriptive of strict RED-before-GREEN ordering).

## Note for Plan 51-04

`self._sibling_label.linkActivated` is configured but **not yet connected to a slot** — that wiring is Plan 51-04's job:

```python
# Plan 51-04 will add inside _build_ui or __init__:
self._sibling_label.linkActivated.connect(self._on_sibling_link_activated)

# Plan 51-04 will add as a new slot:
def _on_sibling_link_activated(self, href: str) -> None:
    sibling_id = int(href.removeprefix("sibling://"))
    if self._is_dirty():
        # 3-button QMessageBox.question (Save / Discard / Cancel) per D-11.
        ...
    self.navigate_to_sibling.emit(sibling_id)
```

The `setOpenExternalLinks(False)` configuration ensures `linkActivated` will fire (rather than Qt opening a browser for the `sibling://` scheme) once the connection is wired.

## Self-Check

Files:
- `musicstreamer/ui_qt/edit_station_dialog.py` — FOUND (modified)
- `tests/test_edit_station_dialog.py` — FOUND (modified)
- `.planning/phases/51-audioaddict-cross-network-siblings/51-03-SUMMARY.md` — FOUND (this file)

Commits:
- `bc47a6e` (Task 1: feat) — FOUND in `git log --oneline`.
- `f7c2cc5` (Task 2: test) — FOUND in `git log --oneline`.

Tests:
- `pytest tests/test_edit_station_dialog.py` → 46 passed.
- `pytest tests/test_edit_station_dialog.py -k sibling` → 6 passed.
- `pytest tests/test_aa_siblings.py tests/test_aa_url_detection.py` → 27 passed (Wave 1 unaffected).

## Self-Check: PASSED
