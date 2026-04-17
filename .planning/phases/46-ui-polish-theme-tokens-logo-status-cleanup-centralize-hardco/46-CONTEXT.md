# Phase 46: UI polish — theme tokens + logo status cleanup - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Centralize the hardcoded error-red color and other UI constants into a dedicated `_theme` module so future theming work is unblocked, AND close five small UX gaps surfaced by the 40.1 + 45 UI-REVIEW passes:

1. Extract `#c0392b` from 10 hardcoded sites into `musicstreamer/ui_qt/_theme.py` as `ERROR_COLOR` (unblocks dark mode — dark mode itself is out of scope).
2. Export `STATION_ICON_SIZE = 32` from `_theme.py` (or `_art_paths.py`) and use it at the three icon-size call sites.
3. Distinguish "AudioAddict URL but channel key not derivable" from "Fetch not supported for this URL" in `EditStationDialog._logo_status`.
4. Auto-clear `_logo_status` label after 3s or on next `textChanged` (whichever fires first).
5. Add fetch-in-flight indicator: `Qt.WaitCursor` override during the logo worker.
6. Logo empty-state glyph: keep the existing `audio-x-generic-symbolic` fallback (no new asset).

**Not in scope:** implementing dark/light mode, palette switching, QSS stylesheet migration, new icon assets, a11y sweep, or any widget beyond those touched by items 1–6.

</domain>

<decisions>
## Implementation Decisions

### Theme Token Module
- **D-01:** Create a new module `musicstreamer/ui_qt/_theme.py`. Mirror the `_art_paths.py` convention (underscore prefix = internal UI helper). Start with two constants only — `ERROR_COLOR` and `STATION_ICON_SIZE` — and leave room to grow.
- **D-02:** `ERROR_COLOR` exported as both a hex string (`"#c0392b"`) and a `QColor` — two module-level constants (e.g., `ERROR_COLOR_HEX` and `ERROR_COLOR_QCOLOR`) to avoid callers needing to construct QColor every time. Downstream agent may refine names.
- **D-03:** Migration: replace all 10 hardcoded `#c0392b` sites (`import_dialog.py` ×5, `edit_station_dialog.py`, `cookie_import_dialog.py`, `accent_color_dialog.py`, `settings_import_dialog.py` ×2) with imports from `_theme`. The existing `_ERROR_COLOR` in `settings_import_dialog.py:46` is folded into the shared token.
- **D-04:** Do NOT migrate to QPalette/QSS. Direct token imports only. QSS migration is a future phase.

### Dark Mode
- **D-05:** Dark mode is **not** implemented in this phase. Goal is purely to unblock it by ending the hardcoded-hex pattern. No palette switcher, no settings toggle, no Qt.ColorScheme detection.

### Station Icon Size
- **D-06:** `STATION_ICON_SIZE = 32` lives in `_theme.py` (not `_art_paths.py`). Reason: it's a visual token, not a path-resolution concern. Update `load_station_icon` default arg to use it, and migrate the three `setIconSize(QSize(32, 32))` call sites identified in the 45 UI-REVIEW (`station_tree_model`, `favorites_view:97`, `station_list_panel:151,257`).

### Logo Fetch Status (EditStationDialog)
- **D-07:** Distinguish two states with two different messages:
  - `"AudioAddict station — use Choose File to supply a logo"` → when `_LogoFetchWorker` detects the URL is AudioAddict (slug or channel_key parse succeeds partially OR host is audioaddict.com / di.fm / radiotunes.com / etc.) but cannot auto-derive a valid fetch target.
  - `"Fetch not supported for this URL"` → remaining unsupported-URL case (non-AA, non-YT, no recognizable pattern).
- **D-08:** The detection code lives inside `_LogoFetchWorker.run` (or a helper called from there). Don't add new network calls — classify based on URL parse only.
- **D-09:** Auto-clear `_logo_status` label: whichever fires first wins.
  - On successful state transitions (`"Fetched"`, `"Fetch failed"`, `"Fetch not supported"`, `"AudioAddict station — use Choose File"`), start a `QTimer.singleShot(3000, ...)` that clears the label.
  - On `QLineEdit.textChanged` fired by the URL field, immediately clear the label AND cancel any pending clear timer.
  - The active timer is stored on `self` (e.g., `self._logo_status_clear_timer`) so it can be cancelled/replaced; only one pending clear at a time.

### Fetch-in-Flight Indicator
- **D-10:** Use `QApplication.setOverrideCursor(Qt.WaitCursor)` at the start of `_LogoFetchWorker` dispatch and `QApplication.restoreOverrideCursor()` in the `finished`/`error` handlers. No new widgets. No spinner GIF. No QProgressBar.
- **D-11:** Ensure cursor restore is exception-safe — pair the override with a try/finally in the calling slot (or restore in BOTH finished and error slots, matched to exactly one override call).

### Empty-State Logo Glyph
- **D-12:** Reuse the existing `audio-x-generic-symbolic` fallback in `load_station_icon`. No new asset, no distinct glyph. This phase only ensures callers that currently render nothing (if any) show the fallback consistently.

### Claude's Discretion
- Exact constant names in `_theme.py` (e.g., `ERROR_COLOR` vs `ERROR_RED`, `STATION_ICON_SIZE` vs `ICON_SIZE_STATION`). Pick a consistent convention.
- Whether to expose a small helper (`error_stylesheet()` returning `"color: {ERROR_COLOR_HEX};"`) or have callers inline the format string. Lean toward whatever produces the least churn at call sites.
- Whether to keep a backwards-compat `_ERROR_COLOR` alias in `settings_import_dialog.py`. Preference: no — delete the local, import from `_theme`.
- Test coverage scope: smoke test verifying `_theme.py` exports the two constants + their types; behavioral test for the timer cancellation on textChanged. No test for cursor override (stateful Qt global).

### Folded Todos
None — no pending todos matched this phase's scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### UI-REVIEW sources (the source of this phase's scope)
- `.planning/phases/40.1-fix-youtube-live-stream-detection-in-import-discovery-play-s/40.1-UI-REVIEW.md` — Top 3 fixes #1 (centralize `#c0392b`), #2 (AA URL distinction), #3 (logo status sticky). Gaps section documents the closeEvent 2s hang context.
- `.planning/phases/45-unify-station-icon-loader-dedup-station-tree-model-favorites/45-UI-REVIEW.md` §Top Fixes #3 — `STATION_ICON_SIZE` DRY recommendation.

### Call-site inventory (files the phase touches)
- `musicstreamer/ui_qt/import_dialog.py:264, 292, 339, 433, 466` — 5 ERROR_COLOR sites.
- `musicstreamer/ui_qt/edit_station_dialog.py:131, 186, 191, 449, 460, 516, 518, 533, 563` — ERROR_COLOR (delete button), `_logo_status` label, fetch worker wiring, closeEvent wait.
- `musicstreamer/ui_qt/cookie_import_dialog.py:106` — ERROR_COLOR site.
- `musicstreamer/ui_qt/accent_color_dialog.py:166` — ERROR_COLOR site (border).
- `musicstreamer/ui_qt/settings_import_dialog.py:44-46, 140` — `_ERROR_COLOR` local to replace + inline hex site.
- `musicstreamer/ui_qt/_art_paths.py:47` — `load_station_icon` default `size=32`; update to use `STATION_ICON_SIZE`.
- `musicstreamer/ui_qt/station_tree_model.py`, `favorites_view.py:97`, `station_list_panel.py:151, 257` — `setIconSize(QSize(32, 32))` migrations.

### Related prior CONTEXT
- `.planning/phases/45-unify-station-icon-loader-dedup-station-tree-model-favorites/45-CONTEXT.md` — single-source-of-truth pattern rationale; phase 46 extends this to ERROR_COLOR + icon size.
- `.planning/phases/42-settings-export-import/42-CONTEXT.md` — where `_ERROR_COLOR` local token was first introduced (now being folded into shared module).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `musicstreamer/ui_qt/_art_paths.py` — naming/structure template for `_theme.py` (module-level constants, underscore-prefixed internal module, imported by siblings).
- `settings_import_dialog.py:46` `_ERROR_COLOR = QColor("#c0392b")` — existing token pattern, just local in scope. Phase 46 generalizes it.
- `load_station_icon(station, size: int = 32)` at `_art_paths.py:47` — already parameterized on size, just needs the default to come from the new constant.

### Established Patterns
- Qt stylesheet strings passed via `setStyleSheet("color: #c0392b;")` and QColor passed to `setForeground(QColor)`. Both forms in use → token module needs to support both cleanly (hex string + QColor).
- Workers use `QThread` + custom signals; `EditStationDialog._LogoFetchWorker` is the one being touched for fetch status distinction + cursor override.
- `QTimer.singleShot(ms, callable)` used elsewhere in the codebase for deferred UI actions; safe pattern to reuse for the 3s clear.

### Integration Points
- `EditStationDialog.__init__` at `edit_station_dialog.py:186-191` — where `_logo_status` QLabel is created; is where the timer attribute + `textChanged.connect(self._clear_logo_status)` wiring belongs.
- `EditStationDialog._LogoFetchWorker.run` at `edit_station_dialog.py:86-104` (per 40.1 UI-REVIEW) — where the AA URL classification logic attaches.
- `_art_paths.py` public surface — `load_station_icon`, `abs_art_path`, `FALLBACK_ICON`. Adding `STATION_ICON_SIZE` here is acceptable as an alternate location if planner prefers; current decision is to keep it in `_theme.py`.

</code_context>

<specifics>
## Specific Ideas

- Token module name: `musicstreamer/ui_qt/_theme.py` (underscore prefix, mirrors `_art_paths.py`).
- Two-constant start: `ERROR_COLOR` (as hex string) and `STATION_ICON_SIZE` (int = 32). Optionally expose a QColor companion (`ERROR_QCOLOR`) if callers need it — planner decides.
- AA URL detection: reuse whatever hostname/slug parser already exists in `_LogoFetchWorker.run`. Do NOT add regex scans in a new place.
- Logo status auto-clear: timer lives on `self._logo_status_clear_timer`. `textChanged` handler both cancels the pending timer and clears the label — idempotent when no timer is pending.
- Cursor override: single override call, paired restore in BOTH the finished AND error slots. Do NOT restore in the worker thread itself.

</specifics>

<deferred>
## Deferred Ideas

- **Dark mode implementation** — light/dark palette switching with settings toggle. Not in this phase (D-05). Future phase — roadmap backlog.
- **QSS stylesheet migration** — moving from direct `setStyleSheet` per-widget to an app-wide QSS file. Future phase.
- **`now_playing_panel._FALLBACK_ICON` deduplication** — 45 UI-REVIEW noted this is a different use (cover art slot, not station row). Out of scope here.
- **A11y mnemonics (`&` accelerators) audit across dialogs** — flagged by 40.1 UI-REVIEW Gaps section. Separate a11y phase.
- **`EditStationDialog.closeEvent` / `reject` 2s hang on fetch in progress** — flagged by 40.1 UI-REVIEW. Needs QProgressDialog or cursor override; not in this phase scope (D-10 covers only in-flight fetch, not the discard-while-fetching path).
- **Toast + inline label duplication on import complete** — 40.1 UI-REVIEW Gaps section. Out of scope.

</deferred>

---

*Phase: 46-ui-polish-theme-tokens-logo-status-cleanup*
*Context gathered: 2026-04-17*
