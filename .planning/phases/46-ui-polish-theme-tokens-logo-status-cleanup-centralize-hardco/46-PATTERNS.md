# Phase 46: UI polish — theme tokens + logo status cleanup - Pattern Map

**Mapped:** 2026-04-17
**Files analyzed:** 10 (1 NEW module + 1 NEW test + 8 MODIFIED UI/test files)
**Analogs found:** 10 / 10

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/ui_qt/_theme.py` (NEW) | utility-module (UI tokens) | constants-export | `musicstreamer/ui_qt/_art_paths.py` | exact (mirror) |
| `tests/test_theme.py` (NEW) | test (unit + grep-assertion) | static analysis | `tests/test_art_paths.py` | role-match |
| `musicstreamer/ui_qt/edit_station_dialog.py` (MOD) | UI widget (QDialog) | event-driven (signals/slots) | self (reference `main_window.py` cursor pattern) | behavioral extension |
| `musicstreamer/ui_qt/_art_paths.py` (MOD) | utility-module | constants-consumer | self | trivial migration |
| `musicstreamer/ui_qt/settings_import_dialog.py` (MOD) | UI widget (QDialog) | constants-consumer | self (delete local `_ERROR_COLOR`) | trivial migration |
| `musicstreamer/ui_qt/import_dialog.py` (MOD) | UI widget (QDialog) | constants-consumer | self | trivial migration |
| `musicstreamer/ui_qt/cookie_import_dialog.py` (MOD) | UI widget (QDialog) | constants-consumer | self | trivial migration |
| `musicstreamer/ui_qt/accent_color_dialog.py` (MOD) | UI widget (QDialog) | constants-consumer | self | trivial migration |
| `musicstreamer/ui_qt/station_list_panel.py` (MOD) | UI widget (panel) | constants-consumer | self | trivial migration |
| `musicstreamer/ui_qt/favorites_view.py` (MOD) | UI widget (panel) | constants-consumer | self | trivial migration |
| `tests/test_edit_station_dialog.py` (MOD) | test | behavioral (pytest-qt) | self (extend existing) | role-match |

**Note:** CONTEXT lists `station_tree_model.py` under `QSize(32, 32)` migrations, but grep against the working tree shows ZERO `QSize(32, 32)` occurrences in that file — the 3 real sites are in `station_list_panel.py` (×2) and `favorites_view.py` (×1). Plan should NOT touch `station_tree_model.py` for icon-size migration.

## Pattern Assignments

### `musicstreamer/ui_qt/_theme.py` (NEW — utility-module, constants-export)

**Analog:** `musicstreamer/ui_qt/_art_paths.py`

**Module-docstring + imports pattern** (analog lines 1-28):

```python
"""Shared resolver for station_art_path → absolute filesystem path and the
unified station-icon loader.
...
The module is underscore-prefixed to mark it internal-to-ui_qt; the functions
and constant are the public surface.
"""
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPixmapCache

from musicstreamer import paths
# Side-effect import: registers :/icons/ resource prefix before QPixmap lookups.
from musicstreamer.ui_qt import icons_rc  # noqa: F401
```

**Copy for `_theme.py`:**
- Triple-quoted module docstring declaring scope (UI tokens, underscore-prefix = internal)
- `from __future__ import annotations` at top
- Minimal PySide6 import: only `QColor` from `PySide6.QtGui` (no `QPixmap`, no `Qt`, no icons_rc — see G-7 in RESEARCH)
- Module-level constants only — NO functions, NO classes

**Module-level constant pattern** (analog line 31):

```python
FALLBACK_ICON = ":/icons/audio-x-generic-symbolic.svg"
```

**Copy for `_theme.py` body:**

```python
# Token: destructive/error foreground color. Use _HEX in stylesheet strings
# ("color: {ERROR_COLOR_HEX};") and _QCOLOR for APIs that take a QColor
# (item.setForeground). The two forms exist because QSS strings cannot
# consume a QColor and QColor APIs cannot consume a raw hex string.
ERROR_COLOR_HEX = "#c0392b"
ERROR_COLOR_QCOLOR = QColor(ERROR_COLOR_HEX)

# Station-row icon dimension (pixels). Consumed by load_station_icon default
# and by every list/tree that shows station rows.
STATION_ICON_SIZE = 32
```

Rationale for names: matches the two-form pattern called out in D-02; `_HEX` / `_QCOLOR` suffixes are unambiguous and grep-friendly. `STATION_ICON_SIZE` follows the existing `FALLBACK_ICON` `SCREAMING_SNAKE` convention in `_art_paths.py`.

---

### `tests/test_theme.py` (NEW — test, unit + grep-assertion)

**Analog:** `tests/test_art_paths.py`

**Module docstring + import pattern** (analog lines 1-23):

```python
"""Phase 45-01: regression tests for the unified station-icon loader.
...
"""
from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPixmapCache

from musicstreamer import paths
from musicstreamer.models import Station
from musicstreamer.ui_qt._art_paths import FALLBACK_ICON, load_station_icon
# Side-effect import: registers the :/icons/ resource prefix so QPixmap can
# resolve FALLBACK_ICON in tests.
from musicstreamer.ui_qt import icons_rc  # noqa: F401
```

**Copy for `test_theme.py`:**
- `from __future__ import annotations`
- `import re` + `from pathlib import Path` (for grep-based assertions)
- `from PySide6.QtGui import QColor`
- `from musicstreamer.ui_qt._theme import (ERROR_COLOR_HEX, ERROR_COLOR_QCOLOR, STATION_ICON_SIZE)`
- No `qtbot` fixture needed for the 3 unit tests (plain `str`/`int`/`QColor` assertions); no `QApplication.instance()` gymnastics (QColor constructor does not need QGuiApplication per RESEARCH G-4/P-7)

**Test body pattern** — use plain `def test_...():` (no qtbot) mirroring the compact assertion style of `test_art_paths.py::test_missing_file_falls_back_without_raising` (lines 88-93):

```python
def test_error_color_hex_is_string():
    assert isinstance(ERROR_COLOR_HEX, str)
    assert ERROR_COLOR_HEX.startswith("#")
    assert len(ERROR_COLOR_HEX) == 7  # '#' + 6 hex digits


def test_error_color_qcolor_is_qcolor():
    assert isinstance(ERROR_COLOR_QCOLOR, QColor)
    assert ERROR_COLOR_QCOLOR.name().lower() == ERROR_COLOR_HEX.lower()


def test_station_icon_size_is_32():
    assert isinstance(STATION_ICON_SIZE, int)
    assert STATION_ICON_SIZE == 32
```

**Grep-assertion pattern** — see RESEARCH §Validation Architecture for the recipe. Place at module bottom after unit tests. Scope to `musicstreamer/ui_qt/` only (NOT `tests/` — existing `test_station_list_panel.py` asserts `iconSize() == QSize(32, 32)` against the widget, which is semantically correct and unaffected by migration).

---

### `musicstreamer/ui_qt/edit_station_dialog.py` (MOD — UI widget, event-driven)

**Analog for cursor override:** `musicstreamer/ui_qt/main_window.py:397-405`

**Cursor begin/end pattern** (analog lines 397-405):

```python
def _begin_busy(self) -> None:
    QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
    self._act_export.setEnabled(False)
    self._act_import_settings.setEnabled(False)

def _end_busy(self) -> None:
    QApplication.restoreOverrideCursor()
    self._act_export.setEnabled(True)
    self._act_import_settings.setEnabled(True)
```

**Key details from analog:**
- `QApplication.setOverrideCursor` is a classmethod (no `.instance()` needed)
- Paired 1:1 with `restoreOverrideCursor`
- Import `QCursor` from `PySide6.QtGui`, `Qt` from `PySide6.QtCore`, `QApplication` from `PySide6.QtWidgets`

**Copy for Phase 46:**
- Call `QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))` inside `_on_url_timer_timeout` (at `edit_station_dialog.py:437-453`) — immediately before `self._logo_fetch_worker.start()`, AT the same indentation level as the existing `_logo_status.setText("Fetching…")` call at line 449. Dispatch site, NOT inside `_LogoFetchWorker.run` (D-11).
- Call `QApplication.restoreOverrideCursor()` at the **very top** of `_on_logo_fetched` (line 498) — BEFORE the stale-token check at line 502. See RESEARCH Pitfalls P-1 and P-2: exactly ONE override and ONE restore per fetch, regardless of token freshness.
- Import additions to the top of `edit_station_dialog.py`: add `QApplication` to the existing `PySide6.QtWidgets` import block (line 25-42) and add `QCursor` to a new `from PySide6.QtGui` line (currently imports `QPixmap, QPixmapCache` at line 24).

**Analog for QTimer lifecycle (cancellable):** `musicstreamer/ui_qt/edit_station_dialog.py:209-213` (same file — URL debounce timer)

**QTimer attribute-stored pattern** (analog lines 209-213):

```python
self._url_timer = QTimer()
self._url_timer.setSingleShot(True)
self._url_timer.setInterval(500)
self.url_edit.textChanged.connect(self._on_url_text_changed)
self._url_timer.timeout.connect(self._on_url_timer_timeout)
```

**Copy for `_logo_status_clear_timer`** (placement: inside `_build_ui`, immediately after the `_logo_status = QLabel("", self)` at line 186 or grouped with the `_url_timer` block at lines 209-213):

```python
# Auto-clear timer for _logo_status (D-09). 3s after a status message is
# set, clear the label. Cancelled/restarted via _clear_logo_status_now()
# which is triggered both by url_edit.textChanged and by the worker's
# status-setting slots.
self._logo_status_clear_timer = QTimer(self)    # parented — G-1 safety
self._logo_status_clear_timer.setSingleShot(True)
self._logo_status_clear_timer.setInterval(3000)
self._logo_status_clear_timer.timeout.connect(self._logo_status.clear)
```

**Why `QTimer(self)` not `QTimer()`:** see RESEARCH G-1 — parented timer is cheap insurance against pending-fire-after-dialog-teardown. The existing `_url_timer` uses the unparented form; do NOT refactor it (out of scope) but DO use the better form for the new timer.

**Why NOT `QTimer.singleShot(3000, ...)`:** see RESEARCH Pitfall P-3 — the free-function form returns no handle, so there is no way to cancel on `textChanged`.

**Auto-clear wiring pattern** — augment existing `_on_url_text_changed` slot at line 434 (Option 2 per RESEARCH G-3 — simpler than adding a second slot):

```python
def _on_url_text_changed(self) -> None:
    # Debounce fetch (existing behavior — do NOT remove)
    self._url_timer.start()
    # Auto-clear status + cancel any pending 3s clear (D-09)
    self._logo_status_clear_timer.stop()
    self._logo_status.clear()
```

`QLabel.clear()` is idempotent — safe even when text is already empty (G-3 confirmed `QLabel` has no `textChanged` signal so no recursion concern).

**Status-set + start-timer pattern** — every site that writes to `_logo_status` must also `.start()` the clear timer. Sites:
- `_on_url_timer_timeout` line 449: `"Fetching…"` — do NOT start the clear timer here (fetch is mid-flight)
- `_on_fetch_logo_clicked` line 460: `"Enter a URL first"` — start the clear timer
- `_on_logo_fetched` lines 516, 518, 533: `"Fetch failed"`, `"Fetch not supported for this URL"`, `"Fetched"`, and the new `"AudioAddict station — use Choose File to supply a logo"` — start the clear timer after each

**AA-URL classification pattern** — see RESEARCH Pitfall P-4 and G-6. CONTEXT leaves mechanism to Claude's discretion (D-08). **Recommended:** extend the `finished` signal to a 3-arg form so classification flows through the same emit path:

```python
# In _LogoFetchWorker:
finished = Signal(str, int, str)  # tmp_path, token, classification

# classification values:
#   ""              — success or generic failure (existing behavior)
#   "aa_no_key"     — AA URL but slug/channel_key could not be derived
```

In `_LogoFetchWorker.run` (lines 86-93), replace:

```python
if _is_aa_url(url):
    from musicstreamer.aa_import import _fetch_image_map
    import urllib.request
    slug = _aa_slug_from_url(url)
    channel_key = _aa_channel_key_from_url(url, slug=slug)
    if not slug or not channel_key:
        self.finished.emit("", token)
        return
```

with:

```python
if _is_aa_url(url):
    from musicstreamer.aa_import import _fetch_image_map
    import urllib.request
    slug = _aa_slug_from_url(url)
    channel_key = _aa_channel_key_from_url(url, slug=slug)
    if not slug or not channel_key:
        self.finished.emit("", token, "aa_no_key")
        return
```

All other `self.finished.emit("", token)` and `self.finished.emit(tmp, token)` sites must add the third positional `""` (empty classification).

**In `_on_logo_fetched`** at line 498, update the signature and branch on classification:

```python
def _on_logo_fetched(self, tmp_path: str, token: int = 0, classification: str = "") -> None:
    # P-1: restore cursor BEFORE stale-token check so every override is paired.
    QApplication.restoreOverrideCursor()

    # Stale response (existing behavior at lines 502-508) — unchanged.
    if token and token != self._logo_fetch_token:
        ...

    self._fetch_logo_btn.setEnabled(True)
    if not tmp_path or not os.path.exists(tmp_path):
        if classification == "aa_no_key":
            self._logo_status.setText(
                "AudioAddict station — use Choose File to supply a logo"
            )
        else:
            from musicstreamer.url_helpers import _is_aa_url
            url = self.url_edit.text().strip()
            lower = url.lower()
            if "youtube.com" in lower or "youtu.be" in lower or _is_aa_url(url):
                self._logo_status.setText("Fetch failed")
            else:
                self._logo_status.setText("Fetch not supported for this URL")
        self._logo_status_clear_timer.start()  # auto-clear in 3s
        ...
        return

    # Success path — existing code through line 533, then:
    self._logo_status.setText("Fetched")
    self._logo_status_clear_timer.start()  # auto-clear in 3s
```

**Test-compat note (G-8 / P-5):** keep `token: int = 0` default AND add `classification: str = ""` default so `tests/test_edit_station_dialog.py:362` (`dialog._on_logo_fetched(str(fetched))`) continues to pass without modification.

**ERROR_COLOR migration (edit_station_dialog.py:131):**

Current:
```python
_DELETE_BTN_QSS = "QPushButton { color: #c0392b; }"
```

Migrate to:
```python
from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX

_DELETE_BTN_QSS = f"QPushButton {{ color: {ERROR_COLOR_HEX}; }}"
```

F-string with doubled braces (`{{`/`}}`) escapes the QSS literal braces.

---

### `musicstreamer/ui_qt/_art_paths.py` (MOD — consume STATION_ICON_SIZE)

**Analog:** self — trivial migration.

**Current pattern** (line 47):

```python
def load_station_icon(station, size: int = 32) -> QIcon:
```

**Migration:**

```python
from musicstreamer.ui_qt._theme import STATION_ICON_SIZE

def load_station_icon(station, size: int = STATION_ICON_SIZE) -> QIcon:
```

**Import-cycle check** (RESEARCH G-5 / P-7): `_art_paths.py` currently does not import from `_theme.py`, and `_theme.py` does not import from `_art_paths.py`. One-way dep is safe. Add the import to the existing import block at top of `_art_paths.py` (lines 18-28).

---

### `musicstreamer/ui_qt/settings_import_dialog.py` (MOD — fold local _ERROR_COLOR)

**Analog:** self (delete local, import shared).

**Current pattern** (lines 44-46):

```python
# UI-REVIEW follow-up: unify error-row foreground with the destructive token
# used on the Replace All warning label (#c0392b) rather than Qt.red, so all
# red-state UI in this dialog uses the same palette entry.
_ERROR_COLOR = QColor("#c0392b")
```

**Migration:**

```python
from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX, ERROR_COLOR_QCOLOR
```

Then at lines 179-180 replace `_ERROR_COLOR` (QColor form) with `ERROR_COLOR_QCOLOR`:

```python
item.setForeground(0, ERROR_COLOR_QCOLOR)
item.setForeground(1, ERROR_COLOR_QCOLOR)
```

And at line 140 replace the inline hex:

```python
self._replace_warning.setStyleSheet(
    f"color: {ERROR_COLOR_HEX}; font-size: 9pt;"
)
```

Delete the local `_ERROR_COLOR = QColor("#c0392b")` line per D-03 (no backwards-compat alias).

Also: the QColor import at top of `settings_import_dialog.py` can be removed if nothing else in the file uses it — check before deleting to avoid breaking other lines.

---

### `musicstreamer/ui_qt/import_dialog.py` (MOD — 5 hex → constant)

**Analog:** self — all 5 sites use the same `setStyleSheet("color: #c0392b;")` QSS-string form.

**Migration pattern** (applied at lines 264, 292, 339, 433, 466):

```python
# Before:
self._aa_status.setStyleSheet("color: #c0392b;")

# After:
self._aa_status.setStyleSheet(f"color: {ERROR_COLOR_HEX};")
```

Add import at top:

```python
from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX
```

---

### `musicstreamer/ui_qt/cookie_import_dialog.py` (MOD — 1 hex → constant)

Same pattern as `import_dialog.py`. Line 106:

```python
# Before:
self._error_label.setStyleSheet("color: #c0392b;")

# After:
self._error_label.setStyleSheet(f"color: {ERROR_COLOR_HEX};")
```

Add `from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX` at top.

---

### `musicstreamer/ui_qt/accent_color_dialog.py` (MOD — 1 hex → constant)

Border form. Line 166:

```python
# Before:
self._hex_edit.setStyleSheet("border: 1px solid #c0392b;")

# After:
self._hex_edit.setStyleSheet(f"border: 1px solid {ERROR_COLOR_HEX};")
```

Add `from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX` at top.

---

### `musicstreamer/ui_qt/station_list_panel.py` (MOD — 2 QSize(32, 32) → STATION_ICON_SIZE)

Lines 151 and 257:

```python
# Before:
self.recent_view.setIconSize(QSize(32, 32))
...
self.tree.setIconSize(QSize(32, 32))

# After:
self.recent_view.setIconSize(QSize(STATION_ICON_SIZE, STATION_ICON_SIZE))
...
self.tree.setIconSize(QSize(STATION_ICON_SIZE, STATION_ICON_SIZE))
```

Add `from musicstreamer.ui_qt._theme import STATION_ICON_SIZE` at top.

---

### `musicstreamer/ui_qt/favorites_view.py` (MOD — 1 QSize(32, 32) → STATION_ICON_SIZE)

Line 97. Same migration pattern as `station_list_panel.py`.

---

### `tests/test_edit_station_dialog.py` (MOD — behavioral tests)

**Analog:** self — extend existing test module. Fixtures (`station`, `repo`, `player`, `dialog`) at lines 19-60 cover all 4 new tests.

**Worker-mock pattern** (existing test at lines 325-343):

```python
def test_auto_fetch_worker_starts_on_url_change(qtbot, monkeypatch, dialog):
    """Timeout handler instantiates _LogoFetchWorker and starts it."""
    from unittest.mock import MagicMock
    import musicstreamer.ui_qt.edit_station_dialog as esd_mod
    fake_worker_instance = MagicMock()
    fake_worker_instance.isRunning.return_value = False
    fake_worker_cls = MagicMock(return_value=fake_worker_instance)
    monkeypatch.setattr(esd_mod, "_LogoFetchWorker", fake_worker_cls)

    dialog.url_edit.setText("https://www.youtube.com/watch?v=abc")
    dialog._on_url_timer_timeout()

    fake_worker_cls.assert_called_once()
    assert "youtube.com" in fake_worker_cls.call_args[0][0]
    fake_worker_instance.start.assert_called_once()
```

**Copy for new tests:**

- **T6 / T9 (AA-no-key classification + exact message):** call `dialog._on_logo_fetched("", token=0, classification="aa_no_key")` directly and assert `dialog._logo_status.text() == "AudioAddict station — use Choose File to supply a logo"`.
- **T7 (3s auto-clear):** call `_on_logo_fetched` with a success path, then use `qtbot.wait(3100)` and assert `dialog._logo_status.text() == ""`. Keep the wait tight — pytest-qt default is 5s.
- **T8 (textChanged cancels pending clear):** set status via `_on_logo_fetched`, immediately call `dialog.url_edit.setText("new")` (which fires textChanged), then `qtbot.wait(3100)` and assert the label was cleared IMMEDIATELY (text == "" right after setText) AND the timer was stopped (`dialog._logo_status_clear_timer.isActive() is False`).

**Cursor override NOT tested** per CONTEXT §Claude's Discretion — skip that dimension in test planning.

---

## Shared Patterns

### Theme Import

**Source:** `musicstreamer/ui_qt/_theme.py` (this phase creates it)
**Apply to:** every file in the ERROR_COLOR / STATION_ICON_SIZE migration map (9 UI files).

Import line (place alongside other `from musicstreamer.ui_qt...` imports):

```python
from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX       # for stylesheet strings
from musicstreamer.ui_qt._theme import ERROR_COLOR_QCOLOR    # for setForeground / QColor APIs
from musicstreamer.ui_qt._theme import STATION_ICON_SIZE     # for QSize(N, N) sites
```

Each file imports only what it uses.

### QSS-String Format via F-String

**Source:** New convention introduced by this phase.
**Apply to:** all 9 `setStyleSheet("... #c0392b ...")` sites and the `_DELETE_BTN_QSS` module constant.

Pattern:

```python
widget.setStyleSheet(f"color: {ERROR_COLOR_HEX};")
# Border variant:
widget.setStyleSheet(f"border: 1px solid {ERROR_COLOR_HEX};")
# Multi-property QSS with f-string:
widget.setStyleSheet(f"color: {ERROR_COLOR_HEX}; font-size: 9pt;")
# Nested braces (QSS selectors) — double the literal braces:
_DELETE_BTN_QSS = f"QPushButton {{ color: {ERROR_COLOR_HEX}; }}"
```

### QColor API Form

**Source:** existing `settings_import_dialog.py:179-180` pattern.
**Apply to:** any `setForeground(QColor)` or equivalent QColor-consuming API (only `settings_import_dialog.py` in this phase's scope).

```python
item.setForeground(0, ERROR_COLOR_QCOLOR)
item.setForeground(1, ERROR_COLOR_QCOLOR)
```

### Icon-Size Migration

**Source:** New convention introduced by this phase.
**Apply to:** 3 `setIconSize(QSize(32, 32))` sites.

```python
# Before:
widget.setIconSize(QSize(32, 32))

# After:
widget.setIconSize(QSize(STATION_ICON_SIZE, STATION_ICON_SIZE))
```

`QSize` import is already in place at both `station_list_panel.py` and `favorites_view.py` — no import change needed for `QSize` itself, just add the `_theme` import.

### Cursor Override

**Source:** `main_window.py:397-405`
**Apply to:** `edit_station_dialog.py` only.

Pair 1:1 per RESEARCH P-1/P-2:
- ONE `QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))` at the dispatch slot `_on_url_timer_timeout`.
- ONE `QApplication.restoreOverrideCursor()` at the VERY TOP of `_on_logo_fetched`, before the stale-token check.
- No duplicate restore — there is no separate error signal on `_LogoFetchWorker` (G-7).

### QTimer (Cancellable, Parented)

**Source:** `edit_station_dialog.py:209-213` (existing pattern; use parented form `QTimer(self)` for the new timer per G-1).
**Apply to:** `_logo_status_clear_timer` only.

```python
self._logo_status_clear_timer = QTimer(self)
self._logo_status_clear_timer.setSingleShot(True)
self._logo_status_clear_timer.setInterval(3000)
self._logo_status_clear_timer.timeout.connect(self._logo_status.clear)
```

`.start()` to arm/rearm (auto-resets elapsed time). `.stop()` to cancel. Do NOT use `QTimer.singleShot(ms, callable)` — not cancellable (P-3).

## No Analog Found

All 10 files have exact or near-exact analogs in the codebase. No file is designed against a pattern that does not already exist.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | (None) |

## Metadata

**Analog search scope:** `musicstreamer/ui_qt/**/*.py`, `tests/test_*.py`, `musicstreamer/ui_qt/main_window.py` for cursor pattern, `musicstreamer/url_helpers.py` for AA URL classification helpers referenced by `_LogoFetchWorker`.
**Files scanned:** 10 UI modules + 2 test modules + 2 helpers = 14 files read directly.
**Grep verifications:** `#c0392b` (10 hits across 5 files, matches CONTEXT), `QSize\(\s*32\s*,\s*32\s*\)` (3 hits across 2 files — CONTEXT's `station_tree_model.py` reference is wrong).
**Pattern extraction date:** 2026-04-17
