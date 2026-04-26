# Phase 46: UI polish — theme tokens + logo status cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-17
**Phase:** 46-ui-polish-theme-tokens-logo-status-cleanup
**Areas discussed:** Token module location, Dark mode scope, Fetch-in-flight indicator, Empty-state glyph

---

## Token module location

| Option | Description | Selected |
|--------|-------------|----------|
| New `musicstreamer/ui_qt/_theme.py` module | Dedicated module for design tokens. Starts with ERROR_COLOR + STATION_ICON_SIZE; can grow. Mirrors the `_art_paths.py` pattern. Low risk, easy migration to QPalette/QSS later. | ✓ |
| Add to existing `_art_paths.py` | Co-locate in _art_paths.py. Simpler but muddies the 'art paths' scope. | |
| Qt QPalette / QSS stylesheet | Qt-native theming via QApplication.setStyleSheet(). More Qt-idiomatic but larger refactor. | |

**User's choice:** New `_theme.py` module (recommended).
**Notes:** Matches the established `_art_paths.py` pattern; keeps theming separable from path resolution.

---

## Dark mode scope

| Option | Description | Selected |
|--------|-------------|----------|
| Unblock only — no dark mode impl | Centralize the token so dark mode is NOT blocked, but do not implement light/dark switching. Keeps this phase tight. Dark mode becomes its own later phase. | ✓ |
| Include a basic light/dark toggle | Add QPalette-based dark mode + a settings toggle. Bigger scope: needs color audit, Qt.ColorScheme detection, persistence. | |

**User's choice:** Unblock only (recommended).
**Notes:** Dark mode deferred to a future phase. Scope stays tight on the 5 UI-REVIEW items.

---

## Fetch-in-flight indicator

| Option | Description | Selected |
|--------|-------------|----------|
| Busy cursor + existing "Fetching…" label | QApplication.setOverrideCursor(Qt.WaitCursor) for the worker duration, plus existing status label. Zero new widgets, lowest complexity. | ✓ |
| Animated QLabel (QMovie with small GIF) | Bundle a tiny throbber GIF next to the status label. Nicer visually but adds an asset and animation lifecycle. | |
| Indeterminate QProgressBar (thin, inline) | 0-0 range QProgressBar below URL field, shown only during fetch. Good visibility but uses vertical space. | |

**User's choice:** Busy cursor + label (recommended).
**Notes:** Paired override/restore with try/finally discipline. No new widgets or assets.

---

## Empty-state logo glyph

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing fallback music-note icon | Keep `audio-x-generic-symbolic` fallback already in use. No new asset. Consistent with current behavior. | ✓ |
| Distinct "empty logo" glyph | New icon asset for visual differentiation between "no logo" and "music content". | |

**User's choice:** Reuse existing fallback (recommended).
**Notes:** No new asset in this phase.

---

## Claude's Discretion

Decisions explicitly left to the planner/executor:
- Exact constant names in `_theme.py` (ERROR_COLOR vs ERROR_RED, etc.)
- Whether to expose an `error_stylesheet()` helper vs inline format strings
- Whether to keep a backwards-compat alias in settings_import_dialog.py (lean: delete it)
- Test coverage scope (smoke test for exports + behavioral test for textChanged cancellation)

## Deferred Ideas

- Dark mode implementation (future phase)
- QSS stylesheet migration (future phase)
- `now_playing_panel._FALLBACK_ICON` deduplication (different use, different phase)
- A11y mnemonics audit (separate a11y phase)
- `EditStationDialog.closeEvent` 2s hang on fetch (future phase)
- Toast + inline label duplication on import complete (future phase)
