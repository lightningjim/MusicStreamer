# Phase 75: Extend theme coloring to include toast colors — Research

**Researched:** 2026-05-15
**Domain:** PySide6 `QPalette`/`QWidget.changeEvent` plumbing + Phase 66 theme system extension
**Confidence:** HIGH (codebase facts file:line-cited; one Qt recursion risk verified against PySide6 6.11 docs)

<user_constraints>
## User Constraints (from CONTEXT.md + UI-SPEC.md)

### Locked Decisions (DO NOT relitigate)

- **D-01** ToolTipBase + ToolTipText are the palette roles.
- **D-02** alpha=220 preserved on bg; ToolTipText fully opaque.
- **D-03** `changeEvent(PaletteChange | StyleChange)` for live retint — but see §Risk Surface for a concrete recursion risk on `StyleChange` that this research flags as needing the planner's attention.
- **D-04** Single retinted style — NO severity tiers.
- **D-05** Editor grows 9 → 11 rows (append `"ToolTipBase"` then `"ToolTipText"` to `EDITABLE_ROLES`).
- **D-06** `theme_custom` JSON additive — no SQLite change.
- **D-08** All 6 non-system presets get the two keys; `system` stays `{}`.
- **D-09** `theme = 'system'` → legacy `rgba(40, 40, 40, 220)` + white QSS, byte-identical to today's string.
- **D-10 RECOMMENDED** — option (b): `QApplication.setProperty("theme_name", theme_name)` set inside `apply_theme_palette()` AND mirrored in `theme_picker_dialog._on_tile_clicked()` live-preview path. Confirmed viable — see §1.
- **UI-SPEC** per-preset hex pairs are LOCKED (vaporwave `#f9d6f0`/`#3a2845`, overrun `#1a0a18`/`#ffe8f4`, gbs `#2d5a2a`/`#f0f5e8`, gbs_after_dark `#d5e8d3`/`#0a1a0d`, dark `#181820`/`#f0f0f0`, light `#2a2a32`/`#f5f5f5`).
- **UI-SPEC Editor labels** `"Toast background"` / `"Toast text"`.
- **UI-SPEC typography invariant** No `font-*` properties in produced QSS.
- **UI-SPEC geometry invariant** `border-radius: 8px; padding: 8px 12px;` in BOTH branches.

### Claude's Discretion (research recommends below)

- Branching mechanism (D-10 a vs b) → **b** confirmed (decoupled, mirrors existing patterns; see §1).
- Lazy vs eager `theme_name` read in toast → **lazy** confirmed (see §4).
- System-theme branch detection when property is unset → **default to system branch** (see §6).
- `app.setProperty` call in `apply_theme_palette` → **YES, always** (see §1).
- Docstring "9 roles" → "11 roles" → **YES**, update at `theme.py:9`, `theme.py:175` (defense-in-depth comment is fine as-is).
- Hex value pre-population for empty Custom slot on first editor-open → **already automatic** via existing `_compute_source_palette` (see §7 Wave note).

### Deferred Ideas (OUT OF SCOPE)

Severity tiers, ERROR_COLOR_HEX/WARNING_COLOR_HEX/STATION_ICON_SIZE migration, accent layering, new SQLite keys, hover-preview, animated retint, editing toast colors from picker, BrightText/Mid/Dark/Shadow role additions, GTK/Adwaita live system tooltip detection.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| THEME-02 (NEW — planner adds to REQUIREMENTS.md before any plan) | Toast notifications track the active theme via `QPalette.ToolTipBase`/`ToolTipText`. When user picks a theme via Picker (preset or Custom), the next-fired and currently-visible toasts retint to the theme's tooltip colors at alpha=220. `theme='system'` preserves the legacy `rgba(40, 40, 40, 220)` + white QSS. Custom theme editor grows to 11 editable roles. | All file:line citations below; the locked UI-SPEC §Test surface table (lines 296–316) gives the planner copy-pasteable assertions. |

THEME-02 lands as a sibling of the completed THEME-01 in `.planning/REQUIREMENTS.md:44` (Features section). The status table at `.planning/REQUIREMENTS.md:154` gets a new row `| THEME-02 | Phase 75 | Pending |`.
</phase_requirements>

## Summary

Phase 75 is small and well-anticipated by Phase 66 RESEARCH (lines 1020-1023 explicitly flagged it as v1.1 work). The five concrete code changes are:

1. `theme.py` — add 2 keys to 6 preset dicts (12 hex literals, UI-SPEC-locked); append 2 entries to `EDITABLE_ROLES`; add one `app.setProperty("theme_name", theme_name)` call inside `apply_theme_palette`.
2. `theme_picker_dialog.py:260-285` `_on_tile_clicked` — mirror the `setProperty("theme_name", theme_id)` call so live-preview keeps the property in sync (no `apply_theme_palette` call in this path; the picker calls `app.setPalette()` directly).
3. `toast.py` — replace lines 44-52 hardcoded QSS with a `_rebuild_stylesheet()` method that branches on `QApplication.instance().property("theme_name")`; add `changeEvent` override that calls `_rebuild_stylesheet()` on `PaletteChange` only (NOT `StyleChange`, see §Risk Surface §1).
4. `theme_editor_dialog.py:37-47` `ROLE_LABELS` — add 2 entries (`"Toast background"`, `"Toast text"`). No other change; rows auto-grow because the dialog iterates `EDITABLE_ROLES` at lines 161-167.
5. Test surface — 1 file existing-test gate (line 143 to system-theme-only), and ~12-15 new assertions across 4 test files following the locked UI-SPEC §Test surface table.

**Primary recommendation:** Adopt the recommended D-10 path (b) verbatim. Filter `changeEvent` on `QEvent.PaletteChange` ONLY (drop `StyleChange` from CONTEXT.md D-03 to eliminate the documented `setStyleSheet`→`StyleChange` recursion risk). The 6-wave dependency graph in §7 is the minimum-risk plan ordering.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Per-preset toast colors | Domain (theme.py) | — | Already where palette presets live (THEME_PRESETS at `theme.py:34-127`); additive keys flow through `build_palette_from_dict` unchanged. |
| Active-theme branch signal | Domain (theme.py) → App-level (QApplication property) | — | `apply_theme_palette` already runs once at startup (`__main__.py:201`) AND every time picker applies — the natural single source-of-truth. App-level property is read by toast lazily; no widget-tree coupling. |
| QSS retint trigger | UI (toast.py) | Qt signal infrastructure | `QApplication.setPalette()` fires `PaletteChange` on every widget — toast subscribes to that event, no new signal needed. |
| Editor row growth | UI (theme_editor_dialog.py) | Domain (EDITABLE_ROLES tuple) | Editor already iterates `EDITABLE_ROLES` at `theme_editor_dialog.py:161` — appending to the tuple auto-grows the dialog. |
| Custom JSON round-trip | Domain (theme.py:build_palette_from_dict) | Domain (settings_export.py) | Free-form `{role_name: hex}` already accepts any `QPalette.ColorRole` member; `settings_export.py:178-181` exports ALL settings rows (only `audioaddict_listen_key` excluded), so the new keys round-trip in ZIP without code change. |

## Standard Stack

This is a code-change phase, not a new-library phase. Stack is unchanged from Phase 66.

### Core (versions unchanged)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | `>=6.10` (`pyproject.toml:18`) | Qt bindings; `QPalette`, `QEvent`, `QWidget.changeEvent`, `QApplication.setProperty/property` | Project's pinned UI toolkit since Phase 1. Verified `ToolTipBase`/`ToolTipText` are valid `QPalette.ColorRole` enum members — already in active use at `musicstreamer/__main__.py:88-89`. [VERIFIED: musicstreamer/__main__.py:88-89] |
| pytest-qt | (transitive — provides `qapp`, `qtbot` fixtures) | Headless Qt test harness | Already in use throughout `tests/`; offscreen platform set in `tests/conftest.py:13`. [VERIFIED: tests/conftest.py:13] |

No new dependencies. No `pyproject.toml` change. No `uv.lock` change.

### Supporting (existing, reused)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `musicstreamer.accent_utils._is_valid_hex` | — | hex validator for defense-in-depth | Already imported into `theme.py:26`; reused by `build_palette_from_dict` for the new keys (no code change — getattr+regex pattern). [VERIFIED: musicstreamer/theme.py:26, 180] |
| `musicstreamer.settings_export` | — | ZIP round-trip | Exports all `settings` table rows except `audioaddict_listen_key` (`settings_export.py:40, 178-181`). `theme` and `theme_custom` already flow through; new JSON keys are additive. NO change required. [VERIFIED: musicstreamer/settings_export.py:40, 178-181] |

### Alternatives Considered (already rejected by CONTEXT.md / UI-SPEC.md — listed for completeness)

| Instead of | Could Use | Why Rejected |
|------------|-----------|--------------|
| `QPalette.ToolTipBase`/`ToolTipText` | A new synthetic `QPalette.ColorRole` enum member | Enum is closed in Qt — can't extend. (CONTEXT.md D-01.) |
| `QApplication.setProperty("theme_name", ...)` | Pass `repo` into ToastOverlay constructor | Couples toast to repo; threading `repo` through `main_window.py:356` is needless coupling. CONTEXT.md D-10 explicitly recommends path (b). |
| Filter on `(PaletteChange, StyleChange)` in changeEvent | Filter on `PaletteChange` only | CONTEXT.md D-03 says "both for symmetry" — but `setStyleSheet()` inside the handler may re-fire `StyleChange`, causing recursion (see §Risk Surface §1). Recommend filtering on `PaletteChange` only. |

**No `pip install` needed:** PySide6 already pinned at `pyproject.toml:18`. [VERIFIED: pyproject.toml:18]

## Architecture Patterns

### System Architecture Diagram

```
User picks a theme via ThemePickerDialog
        │
        ├── tile click  → theme_picker_dialog._on_tile_clicked(theme_id)  [picker_dialog.py:260]
        │                       │
        │                       ├── app.setPalette(build_palette_from_dict(THEME_PRESETS[theme_id]))   [line 278]
        │                       ├── app.setProperty("theme_name", theme_id)   ← NEW Phase 75
        │                       └── apply_accent_palette(app, accent)  [line 283 — unchanged]
        │
        └── Apply        → theme_picker_dialog._on_apply()  [picker_dialog.py:287]
                                │
                                └── repo.set_setting("theme", id) + dialog.accept()
                                       (next startup → __main__._run_gui → apply_theme_palette)

apply_theme_palette(app, repo)  [theme.py:189]
        │
        ├── theme_name = repo.get_setting("theme", "system")
        ├── app.setProperty("theme_name", theme_name)  ← NEW Phase 75 (single point of truth)
        ├── branch on theme_name: system / custom / preset
        └── app.setPalette(palette)   [line 231]
                │
                └── Qt sends QEvent.PaletteChange to every QWidget in the app
                        │
                        └── ToastOverlay.changeEvent(event)   ← NEW Phase 75 override
                                │
                                └── self._rebuild_stylesheet()   ← NEW Phase 75
                                        │
                                        ├── theme_name = app.property("theme_name") or "system"
                                        ├── if theme_name == "system":
                                        │       legacy QSS (rgba(40,40,40,220) + white)
                                        └── else:
                                                bg = palette().color(ToolTipBase) → "rgba(R, G, B, 220)"
                                                fg = palette().color(ToolTipText).name() → "#rrggbb"
                                                self.setStyleSheet(...)
```

### Recommended Project Structure (unchanged)

```
musicstreamer/
├── theme.py                          # +12 hex literals, +2 EDITABLE_ROLES, +1 setProperty line
├── ui_qt/
│   ├── toast.py                      # +_rebuild_stylesheet, +changeEvent, system-branch
│   ├── theme_editor_dialog.py        # +2 ROLE_LABELS entries (auto-grows from there)
│   └── theme_picker_dialog.py        # +1 setProperty line in _on_tile_clicked
tests/
├── test_toast_overlay.py             # line 143 → system-only; +new assertions
├── test_theme.py                     # +per-preset hex assertions, +EDITABLE_ROLES count
├── test_theme_editor_dialog.py       # +11-row coverage (Save/Reset/Cancel)
└── test_theme_picker_dialog.py       # +property-mirror assertion
```

### Pattern 1: `changeEvent(QEvent.PaletteChange)` — palette-track-on-app-flip

**What:** Override `QWidget.changeEvent` and re-apply palette-dependent state on `PaletteChange`.
**When to use:** Any widget that caches a palette-derived color (whether as `setPalette` mutation or as a QSS string).
**Verbatim template (from `now_playing_panel.py:194-197`):**

```python
# musicstreamer/ui_qt/now_playing_panel.py:194-197 — Phase 66 _MutedLabel pattern
def changeEvent(self, event: QEvent) -> None:  # type: ignore[override]
    if event.type() in (QEvent.PaletteChange, QEvent.StyleChange):
        self._apply_muted_palette()
    super().changeEvent(event)
```

**Source:** `musicstreamer/ui_qt/now_playing_panel.py:194-197` (also at `musicstreamer/ui_qt/eq_response_curve.py:121-124`). [VERIFIED]

Phase 75 caveat: the toast's `_rebuild_stylesheet()` calls `setStyleSheet()`, which Qt forum + runebook confirm emits a fresh `QEvent.StyleChange` internally. The two existing examples in the codebase do NOT call `setStyleSheet` from within `changeEvent` — they call `setPalette` (which fires `PaletteChange`, not `StyleChange`) and `update()` (which fires no event). Phase 75 introduces the FIRST `setStyleSheet`-from-`changeEvent` site, so it must filter on `PaletteChange` only. See §Risk Surface §1 for full mitigation.

### Pattern 2: Lazy palette read inside QSS builder

**What:** Read `palette().color(role)` at QSS-build time, not at `__init__` time. Cache nothing.
**When to use:** Widget whose color tracks palette flips (Phase 75 is the textbook case).

```python
# Phase 75 — toast.py palette-driven QSS builder template
def _rebuild_stylesheet(self) -> None:
    app = QApplication.instance()
    theme_name = app.property("theme_name") if app is not None else None
    # None/empty → system branch (D-09 + Phase 66 D-23 startup-order invariant)
    if not theme_name or theme_name == "system":
        self.setStyleSheet(
            "QLabel#ToastLabel {"
            " background-color: rgba(40, 40, 40, 220);"
            " color: white;"
            " border-radius: 8px;"
            " padding: 8px 12px;"
            "}"
        )
        return
    pal = self.palette()
    bg = pal.color(QPalette.ToolTipBase)
    fg = pal.color(QPalette.ToolTipText).name()  # lowercase #rrggbb
    self.setStyleSheet(
        "QLabel#ToastLabel {"
        f" background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, 220);"
        f" color: {fg};"
        " border-radius: 8px;"
        " padding: 8px 12px;"
        "}"
    )
```

**Source:** new code; UI-SPEC §Color §Non-system QSS build template (lines 110-125) is the locked spec. [CITED: UI-SPEC.md:94-125]

### Pattern 3: Mirror `setProperty` across two write sites

**What:** The active-theme name must be propagated to `QApplication` at every site that mutates the live palette. Two sites today:
1. `theme.apply_theme_palette()` — called at startup (`__main__.py:201`)
2. `theme_picker_dialog._on_tile_clicked()` — called per-tile-click for live preview (`theme_picker_dialog.py:260-285`)

The editor's `_on_role_color_changed` (`theme_editor_dialog.py:253-268`) does NOT need to set the property because per-role color edits only change ONE role inside the existing palette; the theme identity stays "custom" (already set by the parent picker's tile click, or by the prior `apply_theme_palette` if entering edit from a saved Custom).

The editor's `_on_save` also does NOT need to set the property (it does set `theme='custom'` in repo, but the in-running QSS branch already correctly reads "custom" from the property set by the picker tile click that preceded the Customize button).

The editor's `_on_reset` does NOT need to set the property (Reset restores the source-preset values within the existing palette; theme identity doesn't move).

### Anti-Patterns to Avoid

- **`StyleChange` in the changeEvent filter** — the `setStyleSheet()` call inside `_rebuild_stylesheet()` re-fires `StyleChange`; filtering on `StyleChange` causes recursion. Use `PaletteChange` ONLY. (Diverges from CONTEXT.md D-03 "both for symmetry"; documented risk + mitigation in §Risk Surface §1.)
- **Caching `theme_name` in `__init__`** — startup application order (Phase 66 D-23) is theme → accent → MainWindow → ToastOverlay; toast constructed AFTER `apply_theme_palette`, so theoretically the property is set. But the picker's live-preview flow ALSO mutates the property; caching would freeze the toast on whatever the initial theme was. Always read `app.property("theme_name")` inside `_rebuild_stylesheet()`.
- **Threading `repo` into ToastOverlay** — D-10 explicitly rejects this in favor of the QApplication property approach. Don't reintroduce it.
- **Adding `font-*` properties to the rebuilt QSS** — typography invariant (UI-SPEC §Typography); the test at the bottom of `tests/test_toast_overlay.py` should assert NO `font-size:`/`font-family:`/`font-weight:` substrings in either branch.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Detect when theme changes | `QObject.installEventFilter` on the picker dialog, custom signals, polling timer | `QWidget.changeEvent(QEvent.PaletteChange)` | Qt already fires `PaletteChange` on every widget when `QApplication.setPalette()` is called. The pattern is in active use at two sites in the codebase. [VERIFIED: now_playing_panel.py:194, eq_response_curve.py:121] |
| Track active theme name app-wide | Singleton, global, repo-coupling, ThreadLocal | `QApplication.setProperty("theme_name", str)` | `QApplication` is the natural process-wide singleton; `setProperty`/`property` is Qt's stock K/V on QObjects. Zero-coupling: no import dependency between toast.py and theme.py. [CITED: Qt 6.11 docs — `QObject::setProperty` returns bool, accepts any `QVariant`-convertible value.] |
| Validate hex round-trip in JSON | New regex | `musicstreamer.accent_utils._is_valid_hex` | Already imported into `theme.py:26`; already used by `build_palette_from_dict` at `theme.py:180`. The new ToolTipBase/ToolTipText keys flow through this validator with zero new code. [VERIFIED: musicstreamer/theme.py:180] |
| Append new settings to ZIP export | Update `settings_export.py` allow-list | (nothing) | `settings_export.py:178-181` does `SELECT key, value FROM settings` and excludes only `audioaddict_listen_key` — the new JSON keys inside the existing `theme_custom` row are byte-for-byte additive. NO change to settings_export.py. [VERIFIED: musicstreamer/settings_export.py:40, 178-181] |
| Map role-name → enum | New dict | `getattr(QPalette.ColorRole, role_name, None)` | Already used at `theme.py:182` and `theme_editor_dialog.py:243, 257, 295`. Silently skips unknown names — defense-in-depth for tampered theme_custom JSON. [VERIFIED] |

**Key insight:** Phase 75 introduces ZERO new abstractions. Every mechanism it uses (palette construction, hex validation, JSON round-trip, ZIP export, changeEvent handlers, EDITABLE_ROLES iteration, accent-layering re-impose) is already in place from Phase 59/66. The only NEW code surface area is (1) two presets-dict literals × 6 presets = 12 hex strings, (2) one `setProperty` call mirrored at two sites, (3) one `_rebuild_stylesheet()` method + one `changeEvent` override on `ToastOverlay`, and (4) two `ROLE_LABELS` entries.

## Runtime State Inventory

Not applicable — Phase 75 is a code-level extension of an existing in-app system, not a rename/refactor/migration. Stored data:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `settings.theme_custom` JSON gains two new keys on next editor-save. Existing Custom theme records lack the two keys and silently fall back to Qt defaults until the user re-opens the editor and clicks Save. | NONE — additive; no migration script needed (CONTEXT.md D-06 explicit; verified via `theme.py:182-184` getattr-default-None pattern). |
| Live service config | None — no external services. | None. |
| OS-registered state | None — no OS registrations. | None. |
| Secrets/env vars | None — no env vars or secrets referenced. | None. |
| Build artifacts | None — pure Python, no compiled artifacts. | None. |

## Specific File:Line Answers to Phase Prompt Questions

### 1. QApplication property propagation (D-10 path b)

**`apply_theme_palette` signature today** — `theme.py:189`:

```python
def apply_theme_palette(app: "QApplication", repo) -> None:
```

Called from exactly ONE site: `musicstreamer/__main__.py:201`:

```python
from musicstreamer import theme
theme.apply_theme_palette(app, repo)
```

**Exact change (Phase 75) — `theme.py:206`:** insert ONE line at the top of the function body, right after `theme_name = repo.get_setting("theme", "system")`:

```python
theme_name = repo.get_setting("theme", "system")
app.setProperty("theme_name", theme_name)   # ← NEW Phase 75 (D-10 path b)
```

Rationale for placement: the property must hold whatever theme is ACTIVE — set it BEFORE any of the branch logic, so even early-return paths (system on Linux returns at `theme.py:214` without calling setPalette) leave the property in a sane state.

**Live-preview entry point — `theme_picker_dialog.py:260-285`:** `ThemePickerDialog._on_tile_clicked(theme_id)` is the tile-click handler. Existing body sets `self._selected_theme_id`, `self._active_tile_id`, then branches on `theme_id` to call `app.setPalette(...)` with one of three palette sources (line 267 `QPalette()` fresh; line 276 `build_palette_from_dict(json_dict)`; line 278 `build_palette_from_dict(THEME_PRESETS[id])`). Then line 283 re-imposes accent.

**Exact mirror site (Phase 75):** insert ONE line at `theme_picker_dialog.py:264`, immediately after `app = QApplication.instance()`:

```python
app = QApplication.instance()
app.setProperty("theme_name", theme_id)   # ← NEW Phase 75 (mirror of apply_theme_palette)
```

This sets the property BEFORE the palette mutation so that if Qt synchronously dispatches `PaletteChange` inside `app.setPalette()`, the toast's `changeEvent` handler sees the new theme_name when it reads `app.property("theme_name")`.

**No editor change required.** `_on_save` at `theme_editor_dialog.py:270` calls `self._repo.set_setting("theme", "custom")` — persistence only; the live palette is already in the "custom-edited" state from the per-row `_on_role_color_changed` calls. The property reads "vaporwave" (or whatever source_preset the picker tile click set) all through the editing session, which is technically wrong (the user is editing the Custom slot, not Vaporwave) — BUT it doesn't matter because the toast's QSS depends on the PALETTE colors, not the theme_name string, EXCEPT for the system/non-system branch. As long as the property is not "system" the non-system branch fires with the right palette. Recommend leaving the editor untouched on this dimension.

Edge case: a user enters editor from theme='system'. The picker tile click for "system" at `theme_picker_dialog.py:267` calls `app.setPalette(QPalette())` (fresh default) and would set `property("theme_name", "system")`. Now the user clicks Customize…; editor opens with `source_preset='system'`; user edits Window. The toast still reads property=="system" and renders legacy dark-grey QSS even though the palette is no longer the system default. **Recommend:** in the editor's `_on_role_color_changed`, ALSO set `app.setProperty("theme_name", "custom")` once the user has made an edit. This is a third mirror site for the property. (See §Risk Surface §3 for the alternative if the planner prefers minimal editor diff.)

### 2. changeEvent mechanics

**`super().changeEvent()` order — first or last?** Looking at the two existing patterns:

- `now_playing_panel.py:194-197` — handler logic runs FIRST, then `super().changeEvent(event)` (line 197).
- `eq_response_curve.py:121-124` — same: handler logic FIRST, then `super().changeEvent(event)` (line 124).

Both put `super()` LAST. Phase 75 should match that order for codebase consistency.

**Qt docs guidance:** Qt 6.11 QWidget docs note that `changeEvent` is a notification hook; `super().changeEvent(event)` propagates to base class for default handling (which may include emitting the change signal or recomputing geometry). Order of calling `super()` is not load-bearing for `PaletteChange` specifically — Qt's default `QWidget::changeEvent(PaletteChange)` is a no-op (just dispatches to derived classes via the vtable). The two existing patterns both put it last; copy that.

**Filter on `event.type()`:** The codebase pattern is `if event.type() in (QEvent.PaletteChange, QEvent.StyleChange)`. Phase 75 must NARROW this filter to `event.type() == QEvent.PaletteChange` ONLY — see §Risk Surface §1 for the recursion-risk rationale.

**Subtle Qt gotcha — `setStyleSheet()` re-triggers `changeEvent`:** Confirmed by Qt forum + runebook docs (Qt 6.11). When a widget's `setStyleSheet()` is called, Qt internally re-resolves the style and fires `QEvent.StyleChange` to the widget. If the handler that called `setStyleSheet()` also responds to `StyleChange`, you get infinite recursion. The two existing in-tree patterns avoid this because they call `setPalette()` (fires `PaletteChange`, not `StyleChange`) or `update()` (fires nothing).

Phase 75 is the FIRST `setStyleSheet`-inside-`changeEvent` site in the codebase. Filter on `PaletteChange` only to avoid recursion. The "symmetry" CONTEXT.md D-03 mentioned is unnecessary because `QApplication.setPalette()` (the trigger that matters — picker tile click) fires `PaletteChange`, not `StyleChange`. `StyleChange` is for when Qt's style ENGINE (`QStyle`) changes, e.g. `app.setStyle("Fusion")` — which Phase 75 does not trigger on Linux.

[CITED: Qt 6.11 QWidget docs, Qt forum thread "Stylesheet recomputing after property change", runebook.dev "Qt changeEvent() Explained"]

### 3. QSS rebuild trigger surface

**ToastOverlay's parent:** `main_window.py:356` — `self._toast = ToastOverlay(self)`. The parent is `MainWindow` itself (the toast is a child of the QMainWindow, not centralWidget).

**Verify toast receives `QEvent.PaletteChange`:** `QApplication.setPalette()` propagates to every QWidget in the application tree via Qt's stock event-dispatch. MainWindow is a top-level QWidget; its descendant tree (centralWidget + everything inside) ALSO receives the event. ToastOverlay is a descendant of MainWindow (constructed at `main_window.py:356`), so YES it receives `PaletteChange` whenever `app.setPalette()` fires — same as NowPlayingPanel which is inside centralWidget and receives the same event.

**Confirm via existing pattern:** `now_playing_panel.py:194-197` works today — Phase 66's picker tile click → `app.setPalette()` → `_MutedLabel.changeEvent(PaletteChange)` fires → `_apply_muted_palette()` runs. ToastOverlay (sibling-ish descendant of MainWindow, child of the QMainWindow root) gets the same event dispatch.

**Important nuance:** `QGraphicsOpacityEffect` (which the toast uses at `toast.py:56`) is a GraphicsEffect, NOT a QWidget — but it doesn't affect event dispatch. The toast itself is still a QWidget and receives PaletteChange normally.

### 4. Lazy vs eager `theme_name` read

**Recommendation: LAZY.** Read `app.property("theme_name")` inside `_rebuild_stylesheet()` at every call, not cached in `__init__`.

**Reasoning:**
1. The picker live-preview flow mutates the property mid-session (see §1 mirror site). Caching at `__init__` would freeze the toast on whatever startup theme was active.
2. There's no startup-order race: `ToastOverlay.__init__` runs from inside `main_window.py:356`, which is called from `__main__._run_gui` AFTER `apply_theme_palette` (which sets the property). But even if it WERE called before, lazy read handles the "property unset" branch correctly via §6 (defaults to system branch).
3. The rebuild is cheap — single string interpolation + one `setStyleSheet()` call — and only runs (a) once at `__init__`, (b) on `PaletteChange` (handful per session).

**No code-reading refutation found.** Existing `_compute_source_palette` at `theme_editor_dialog.py:187-227` reads `theme_custom` JSON lazily per dialog construction — same lazy-read idiom.

### 5. Test plumbing

**Qt fixture setup — `tests/conftest.py`:**

- Line 13: `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` runs at import time, BEFORE PySide6 is imported — sets headless platform. Confirmed working on Wayland per project memory and the Phase 37 UAT note in `tests/test_toast_overlay.py:1-9`.
- Lines 20-30: autouse fixture stubs `_ensure_bus_bridge` (Player concern, not relevant to Phase 75).
- **`qapp` and `qtbot` fixtures are provided by `pytest-qt`** (not defined in conftest); usage at `tests/test_theme.py:140` (`def test_build_palette_from_dict_sets_all_9_roles(qapp):`) and `tests/test_toast_overlay.py:19-26` (`parent_widget` fixture uses `qtbot.addWidget`/`qtbot.waitExposed`).

**How existing toast tests construct ToastOverlay — `tests/test_toast_overlay.py:19-26, 30`:**

```python
@pytest.fixture
def parent_widget(qtbot):
    parent = QWidget()
    parent.resize(1200, 800)
    qtbot.addWidget(parent)
    parent.show()
    qtbot.waitExposed(parent)
    return parent

def test_1_construct_hidden(qtbot, parent_widget):
    toast = ToastOverlay(parent_widget)
```

Parent is a plain `QWidget`, NOT a `MainWindow`. The toast is constructed with `ToastOverlay(parent_widget)` directly. No `repo` fixture in this file — confirms D-10 path (b) is the right choice (no repo threading needed).

**How theme tests trigger a palette change — `tests/test_theme.py:222-226`:**

```python
def test_apply_theme_palette_uses_repo_setting(qapp, repo):
    repo.set_setting("theme", "gbs")
    apply_theme_palette(qapp, repo)
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == "#a1d29d"
```

Direct `apply_theme_palette(qapp, repo)` call. The `repo` fixture (`tests/test_theme.py:129-135`) is a real `Repo` over a temp-path SQLite — NOT the FakeRepo used in other test files. For Phase 75, the toast tests can use FakeRepo (or none at all, since toast doesn't need repo).

**How `tests/test_theme_editor_dialog.py` simulates Save/Reset/Cancel — three patterns at `tests/test_theme_editor_dialog.py:`**

- Save: `dlg._on_save()` (line 188) — direct method call; then assert `repo.get_setting("theme", "")`.
- Reset: `dlg._on_reset()` (line 156) — direct method call; assert palette colors.
- Cancel: `dlg.reject()` (line 227) — direct method call; assert palette restored.
- Per-row swatch click: `qtbot.mouseClick(dlg._rows["Window"]._swatch_btn, Qt.LeftButton)` (line 128) — gated by a monkeypatched `QColorDialog.getColor` returning a pre-set `QColor` (lines 70-79 fixture `stub_color_dialog`).

For Phase 75's 11-row coverage:
- Reuse `stub_color_dialog` fixture for the new swatch clicks (lines 70-79).
- The dialog already iterates `EDITABLE_ROLES` at `theme_editor_dialog.py:161` — once the tuple gains two more entries, `dlg._rows["ToolTipBase"]` and `dlg._rows["ToolTipText"]` exist for free. Tests can directly `dlg._rows["ToolTipBase"]._swatch_btn.click()`.
- The existing test `test_editor_shows_9_color_rows` at `tests/test_theme_editor_dialog.py:86-90` will FAIL after the change (it asserts `len(dialog._rows) == 9`). Phase 75 task list must include updating this test to assert 11.

**How `tests/test_theme_picker_dialog.py` does live preview — `tests/test_theme_picker_dialog.py:75-80`:**

```python
def test_tile_click_applies_palette(qtbot, repo, qapp):
    dlg = ThemePickerDialog(repo)
    qtbot.addWidget(dlg)
    qtbot.mouseClick(dlg._tiles["vaporwave"], Qt.LeftButton)
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == "#efe5ff"
```

For Phase 75 live-preview retint test: after the tile click, assert `qapp.property("theme_name") == "vaporwave"` and `qapp.palette().color(QPalette.ColorRole.ToolTipBase).name().lower() == "#f9d6f0"`.

### 6. System-theme branch wiring

**The ambiguity:** `app.property("theme_name")` returns `None` (or empty `QVariant`) if never set. Both "theme never applied yet" and "theme='system' explicitly applied" need to render legacy QSS.

**Recommendation: Option (a) — Default to system branch when property is None/empty.**

Reasoning:
1. `apply_theme_palette('system', ...)` early-returns on Linux at `theme.py:214` WITHOUT calling `app.setPalette()`. If we add the `setProperty` BEFORE the branch (as recommended in §1), the property IS set to the literal string `"system"` even for Linux+system. So in practice option (b) is also satisfied.
2. BUT the picker's `_on_tile_clicked('system')` at `theme_picker_dialog.py:266-267` also needs the mirror — when set as recommended at line 264, the property is set to `"system"` before the `app.setPalette(QPalette())` call. Symmetric.
3. The "property never set" case is a defensive guard for edge scenarios (e.g., toast constructed in a test fixture that never called `apply_theme_palette`).

**Concrete code:** the toast's branch condition is `if not theme_name or theme_name == "system":` — covers BOTH the literal "system" case AND the unset (None/empty) case.

[ASSUMED: PySide6 6.11's `QObject.property()` returns Python `None` when the property has never been set on the object. Confirmed by Qt 6.11 docs: "If no such property exists, the returned variant is invalid." PySide6 translates invalid QVariant to Python `None`. The boolean falsy check (`not theme_name`) handles both None and empty string.]

### 7. Wave structure

Proposed dependency graph (6 plans; 3 waves):

**Wave 1 — Foundation (parallel-safe):**

- **PLAN-01: `theme.py` foundation**
  - Add `ToolTipBase` + `ToolTipText` hex pairs to all 6 non-system presets (12 literals from UI-SPEC).
  - Append `"ToolTipBase"`, `"ToolTipText"` to `EDITABLE_ROLES` tuple.
  - Add `app.setProperty("theme_name", theme_name)` at `apply_theme_palette` right after the `repo.get_setting` line.
  - Update docstring at `theme.py:9` "Theme owns 9 QPalette primary roles" → "Theme owns 11 QPalette primary roles".
  - Files touched: `musicstreamer/theme.py`.
  - Verifiable via existing `tests/test_theme.py::test_all_presets_cover_9_roles` (will break — must update to 11 in same plan or in PLAN-05).
- **PLAN-02: REQUIREMENTS bookkeeping**
  - Add `THEME-02` requirement under Features (THEME family) at `.planning/REQUIREMENTS.md:44` neighbourhood.
  - Add `| THEME-02 | Phase 75 | Pending |` row at `.planning/REQUIREMENTS.md:154` neighbourhood (status table).
  - Files touched: `.planning/REQUIREMENTS.md`.
  - Pure docs change — no code dependency; truly parallel with PLAN-01.

**Wave 2 — Consumers (both depend on PLAN-01):**

- **PLAN-03: `toast.py` retint plumbing**
  - Add `_rebuild_stylesheet()` method to `ToastOverlay` (system-branch + non-system-branch per UI-SPEC §Color templates).
  - Replace lines 44-52 hardcoded `setStyleSheet(...)` with a call to `self._rebuild_stylesheet()`.
  - Add `changeEvent(self, event)` override filtering on `QEvent.PaletteChange` ONLY (NOT StyleChange — see §Risk Surface §1).
  - Files touched: `musicstreamer/ui_qt/toast.py`.
- **PLAN-04: `theme_picker_dialog.py` property mirror**
  - In `_on_tile_clicked` at line 264, insert `app.setProperty("theme_name", theme_id)` immediately after `app = QApplication.instance()`.
  - Files touched: `musicstreamer/ui_qt/theme_picker_dialog.py`.
- **PLAN-05: `theme_editor_dialog.py` row labels**
  - Add to `ROLE_LABELS` dict (`theme_editor_dialog.py:37-47`): `"ToolTipBase": "Toast background"`, `"ToolTipText": "Toast text"`.
  - OPTIONAL (planner's call): add `app.setProperty("theme_name", "custom")` to `_on_role_color_changed` to handle the system→edit→toast-stays-grey edge case from §1 closing paragraph. Recommend YES for defense.
  - Files touched: `musicstreamer/ui_qt/theme_editor_dialog.py`.

PLAN-03, PLAN-04, PLAN-05 are independent of each other (they touch different files), so all three can run in parallel within Wave 2.

**Wave 3 — Tests (each test plan depends on the matching code plan; bundle for serial execution):**

- **PLAN-06: `tests/test_toast_overlay.py` + `tests/test_theme.py`**
  - test_toast_overlay.py line 143: gate the `rgba(40, 40, 40, 220)` assertion to a `theme='system'` setup (set property via `qapp.setProperty("theme_name", "system")` first).
  - Add: non-system QSS assertions (palette-driven rgba + hex), `changeEvent(PaletteChange)` retint assertion via snapshot before/after `qapp.setPalette(...)`, NO `font-*` substrings, geometry preservation in both branches.
  - test_theme.py: update `test_all_presets_cover_9_roles` → "_11_roles" (or add new test); per-preset hex assertions for the 12 locked values; `EDITABLE_ROLES` has exactly 11 entries; system preset stays `{}`; `app.setProperty` happens inside `apply_theme_palette`.
  - Files touched: `tests/test_toast_overlay.py`, `tests/test_theme.py`.
  - Depends on PLAN-01 + PLAN-03.
- **PLAN-07: `tests/test_theme_editor_dialog.py`**
  - Update `test_editor_shows_9_color_rows` → `_11_color_rows` (or add new); assert `dlg._rows["ToolTipBase"]` + `dlg._rows["ToolTipText"]` exist.
  - Save round-trip includes both new keys in JSON.
  - Reset restores both new rows to source-preset hex.
  - Cancel snapshot covers both new roles in `QApplication.palette()`.
  - `ROLE_LABELS["ToolTipBase"] == "Toast background"`, `ROLE_LABELS["ToolTipText"] == "Toast text"`.
  - Files touched: `tests/test_theme_editor_dialog.py`.
  - Depends on PLAN-01 + PLAN-05.
- **PLAN-08: `tests/test_theme_picker_dialog.py`**
  - Add `test_tile_click_sets_theme_name_property` — after clicking vaporwave tile, assert `qapp.property("theme_name") == "vaporwave"`.
  - Add `test_tile_click_retints_toast` — light integration: construct a ToastOverlay with a QWidget parent in the test, then `qtbot.mouseClick(dlg._tiles["vaporwave"], Qt.LeftButton)`, then assert toast's styleSheet contains the rgba tuple derived from `#f9d6f0`.
  - Files touched: `tests/test_theme_picker_dialog.py`.
  - Depends on PLAN-01 + PLAN-03 + PLAN-04.

Strict dependency graph:
```
PLAN-01 ──┬─→ PLAN-03 ──┐
          ├─→ PLAN-04 ──┼─→ PLAN-06
          └─→ PLAN-05 ──┤   PLAN-07
                        └─→ PLAN-08
PLAN-02 (independent, no downstream blockers)
```

**Realistic execution waves** (using gsd's wave terminology where each wave can run plans in parallel):

| Wave | Plans | Parallelism |
|------|-------|-------------|
| 1 | PLAN-01, PLAN-02 | Two parallel (no shared file) |
| 2 | PLAN-03, PLAN-04, PLAN-05 | Three parallel (three different files) |
| 3 | PLAN-06, PLAN-07, PLAN-08 | Three parallel (three different test files; PLAN-06 covers 2 test files but they're both purely test-only and don't conflict with PLAN-07/PLAN-08) |

### 8. Risk Surface

**Risk 1 (HIGH — verified gotcha):** `setStyleSheet()` called from inside a `changeEvent(StyleChange)` handler causes infinite recursion. Qt fires `QEvent.StyleChange` internally whenever a widget's stylesheet is set.

- **What goes wrong:** ToastOverlay enters `changeEvent` on a real style change, runs `_rebuild_stylesheet()` which calls `setStyleSheet()`, which re-fires `StyleChange`, which re-enters `changeEvent`, etc. Stack overflow.
- **Why it happens:** Qt's QSS engine has to mark the widget dirty and re-render — it dispatches `StyleChange` after every `setStyleSheet()` call as the canonical notification.
- **How to avoid:** Filter the changeEvent handler on `QEvent.PaletteChange` ONLY, NOT `(PaletteChange, StyleChange)`. The palette-flip trigger we actually care about (`QApplication.setPalette()` in picker tile click + `apply_theme_palette`) fires `PaletteChange`, not `StyleChange`. This DIVERGES from CONTEXT.md D-03 which says "respond to both for symmetry" — but the divergence is well-justified, and the existing in-tree `changeEvent` handlers (`now_playing_panel.py`, `eq_response_curve.py`) get away with the both-filter only because they call `setPalette()`/`update()`, not `setStyleSheet()`.
- **Warning signs in tests:** Stack overflow / RecursionError when running any test that exercises the changeEvent path. If PLAN-06's "changeEvent triggers rebuild" assertion hangs or crashes, this is the cause.
- **Belt-and-suspenders alternative:** keep `(PaletteChange, StyleChange)` filter but guard with a `self._rebuilding = True/False` flag. Less idiomatic. Not recommended.

[CITED: Qt 6.11 QWidget docs; runebook.dev "Qt changeEvent() Explained"; Qt Forum thread "Stylesheet recomputing after property change"]

**Risk 2 (LOW — verified by code reading):** `QApplication.setProperty()` does NOT fire any palette- or style-related signal. It fires `QDynamicPropertyChangeEvent` (event type `QEvent.DynamicPropertyChange`), which the toast does not filter on. No other widget in the codebase reads `qapp.property("theme_name")` or filters on `DynamicPropertyChange`. Safe.

**Risk 3 (LOW — already mitigated by existing code):** Custom theme JSON parser silently swallowing malformed ToolTip hex values. `build_palette_from_dict` at `theme.py:179-186` does `if not _is_valid_hex(hex_value): continue` then `if role is None: continue` — malformed hex or unknown role names fall through to Qt defaults. No code change needed; existing defense covers the new keys.

**Risk 4 (NONE — verified by grep):** Hardcoded `rgba(40, 40, 40, 220)` substring exists in EXACTLY one test location (`tests/test_toast_overlay.py:143`). No other places. Grep confirmed clean.

**Risk 5 (LOW — verified by code reading):** ZIP export/import round-trip. `settings_export.py:178-181` exports all rows from `settings` table except `audioaddict_listen_key`. Both `theme` and `theme_custom` already round-trip; the new JSON keys inside `theme_custom` are additive and flow through automatically. NO change required.

**Risk 6 (MEDIUM — surfaced by audit):** `QPalette.ToolTipBase` / `QPalette.ToolTipText` are ALSO used by Qt's stock `QToolTip` for `widget.setToolTip("hover text")` rendering. Wiring these roles into 6 presets means tooltips on every widget that uses `setToolTip` will retint with the theme. Audit results: 15+ `setToolTip` call sites across the UI (`favorites_view.py:192`, `equalizer_dialog.py:126`, `import_dialog.py:276/433/436`, `theme_picker_dialog.py:61/248/250`, `discovery_dialog.py:364/461/468/489`, `station_list_panel.py:114/256/306`, `theme_editor_dialog.py:75`, `now_playing_panel.py:453/467/478/514`).
- **Impact:** Existing dark/light/vaporwave/etc. tooltips currently render with Qt's default (pale yellow on Linux GNOME). After Phase 75, they'll render with the locked preset ToolTipBase/ToolTipText hex. The UI-SPEC §Color (lines 81-89) explicitly acknowledges this: "ToolTipBase/ToolTipText reserved for: `QLabel#ToastLabel` inside `ToastOverlay` only. Qt may also use these roles for `setToolTip()` strings on other widgets; that's Qt's stock behavior and is not a regression — `setToolTip()` rendering on theme-driven palettes is a bonus side-effect, not a Phase 75 contract."
- **Risk-management:** PLAN-01 should NOT add a "tooltip QSS for QToolTip" test (out of scope). PLAN-03 should NOT touch Qt's stock tooltip code path. If a tooltip looks bad on a specific theme post-deploy, that's a separate UAT issue, not a Phase 75 regression — the hex pairs were WCAG-validated for body text per UI-SPEC §Accessibility (lines 281-289).

**Risk 7 (LOW — verified by code reading):** `_compute_source_palette` in `theme_editor_dialog.py:187-227` reads source preset case-by-case:
- Case A/B (`source_preset == 'custom'`): iterates `EDITABLE_ROLES` (which after PLAN-01 includes the new keys) — auto-handles.
- Case C (`source_preset == 'system'`): builds dict from `QPalette()` fresh, iterating `EDITABLE_ROLES` — auto-handles (Qt's default `QPalette` has stock ToolTipBase/ToolTipText values like off-yellow `#ffffdc`).
- Case D (`source_preset in THEME_PRESETS`): iterates `EDITABLE_ROLES` filtered by `if role_name in preset` — auto-handles once PLAN-01 adds the keys to the preset dicts.
- Case E (unknown): falls back to active app palette via `_read_app_palette_role_dict` — auto-handles.

No `_compute_source_palette` code change required. Existing test `test_editor_prefills_from_source_preset` will still pass.

**Risk 8 (LOW — edge case from §1):** User on theme='system' opens editor, edits Window color. ToastOverlay's `app.property("theme_name")` still reads "system" because editor's `_on_role_color_changed` doesn't update the property. Toast renders legacy dark-grey QSS even though user is editing Custom. Mitigation: PLAN-05 should set `app.setProperty("theme_name", "custom")` in `_on_role_color_changed`. Trade-off: tiny code addition vs. wrong toast preview during edit. Recommend YES.

## Code Examples

Verified patterns from existing codebase.

### Example 1: `setProperty` on QApplication

```python
# Inside theme.py apply_theme_palette — Phase 75 addition
def apply_theme_palette(app, repo):
    theme_name = repo.get_setting("theme", "system")
    app.setProperty("theme_name", theme_name)  # NEW — single source of truth
    # ... rest unchanged ...
```

### Example 2: ToastOverlay changeEvent + _rebuild_stylesheet

```python
# musicstreamer/ui_qt/toast.py — Phase 75 additions
from PySide6.QtCore import QEvent  # already imported at toast.py:9
from PySide6.QtGui import QPalette  # NEW import
from PySide6.QtWidgets import QApplication  # NEW import

# Inside ToastOverlay class:

def _rebuild_stylesheet(self) -> None:
    app = QApplication.instance()
    theme_name = app.property("theme_name") if app is not None else None
    if not theme_name or theme_name == "system":
        self.setStyleSheet(
            "QLabel#ToastLabel {"
            " background-color: rgba(40, 40, 40, 220);"
            " color: white;"
            " border-radius: 8px;"
            " padding: 8px 12px;"
            "}"
        )
        return
    pal = self.palette()
    bg = pal.color(QPalette.ToolTipBase)
    fg = pal.color(QPalette.ToolTipText).name()
    self.setStyleSheet(
        "QLabel#ToastLabel {"
        f" background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, 220);"
        f" color: {fg};"
        " border-radius: 8px;"
        " padding: 8px 12px;"
        "}"
    )

def changeEvent(self, event) -> None:  # type: ignore[override]
    # NB: PaletteChange only — NOT StyleChange. setStyleSheet() re-fires
    # StyleChange and would cause infinite recursion (see RESEARCH §Risk 1).
    if event.type() == QEvent.PaletteChange:
        self._rebuild_stylesheet()
    super().changeEvent(event)
```

In `__init__`, replace lines 44-52 with `self._rebuild_stylesheet()` (called AFTER `self.label.setObjectName("ToastLabel")` at line 39 and AFTER `layout.addWidget(self.label)` at line 42).

### Example 3: Mirror in picker tile click

```python
# musicstreamer/ui_qt/theme_picker_dialog.py — Phase 75 addition at line 264
def _on_tile_clicked(self, theme_id: str) -> None:
    self._selected_theme_id = theme_id
    self._active_tile_id = theme_id
    app = QApplication.instance()
    app.setProperty("theme_name", theme_id)  # NEW Phase 75 — mirror of apply_theme_palette
    # ... rest unchanged (existing branch on system/custom/preset + setPalette + accent re-impose) ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded toast color | Palette-driven QSS via ToolTipBase/ToolTipText | Phase 75 | Toast retints with theme |
| Implicit theme name | Explicit `QApplication.property("theme_name")` | Phase 75 | Decouples toast from repo; opens path for other widgets to branch on theme name without coupling to theme.py |

**Deprecated/outdated:** None. Phase 66's hardcoded-toast exemption (66-RESEARCH.md:372 — "rgba(40,40,40,220) background hardcoded ✓ By D-03 | Theme-independent toast") is explicitly reversed by Phase 75.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | PySide6 `QObject.property()` returns Python `None` for never-set properties (not raise, not return empty `QVariant` wrapped object). | §6 System-theme branch | LOW — even if it returns an empty string instead of None, `not theme_name` covers both. Test will catch any deviation. |
| A2 | `QApplication.setPalette()` fires `QEvent.PaletteChange` synchronously to every widget in the tree (including ToastOverlay as a descendant of MainWindow). | §3 QSS rebuild trigger | LOW — verified empirically by the existing `_MutedLabel` pattern in NowPlayingPanel working today on the same picker flow. |
| A3 | The `setStyleSheet()` re-fires `StyleChange` claim. | §Risk Surface §1 | MEDIUM — verified via Qt forum + runebook docs (cited). If the planner wants belt-and-suspenders, add a `_rebuilding` flag guard regardless of filter narrowness. |
| A4 | `QApplication.setProperty()` does NOT fire palette- or style-relevant events. | §Risk Surface §2 | LOW — Qt docs (CITED in §1) state `DynamicPropertyChange` is the only event fired. Grep confirms no widget in codebase listens for it. |

If this table seems short: most claims in this RESEARCH are file:line-cited from the codebase (the highest-confidence source for an "extend an existing system" phase). The four assumptions above are the only places where external Qt-runtime behavior matters more than codebase code-reading.

## Open Questions

None. All planner-blocking questions resolved by file:line citation + UI-SPEC.md locks.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-qt (offscreen platform) |
| Config file | `tests/conftest.py` (offscreen platform set at line 13) |
| Quick run command | `pytest tests/test_toast_overlay.py tests/test_theme.py -x` |
| Full suite command | `pytest tests/test_toast_overlay.py tests/test_theme.py tests/test_theme_editor_dialog.py tests/test_theme_picker_dialog.py -x` |
| Phase gate | All 4 test files green |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| THEME-02 | Toast retints with theme via ToolTipBase/ToolTipText (non-system branch) | unit | `pytest tests/test_toast_overlay.py -x` | ✅ exists |
| THEME-02 | `theme='system'` → legacy `rgba(40, 40, 40, 220)` + white QSS | unit | `pytest tests/test_toast_overlay.py -x -k system` | ✅ exists (line 143 retrofit) |
| THEME-02 | `changeEvent(PaletteChange)` triggers stylesheet rebuild | unit | `pytest tests/test_toast_overlay.py -x -k changeEvent` | ✅ exists (new test) |
| THEME-02 | Geometry invariant (border-radius + padding) in BOTH branches | unit | `pytest tests/test_toast_overlay.py -x -k geometry` | ✅ exists (new test) |
| THEME-02 | Typography invariant (NO font-* in either branch) | unit | `pytest tests/test_toast_overlay.py -x -k typography` | ✅ exists (new test) |
| THEME-02 | All 6 non-system presets declare ToolTipBase + ToolTipText | unit | `pytest tests/test_theme.py -x -k preset` | ✅ exists (extend `test_all_presets_cover_*_roles`) |
| THEME-02 | Per-preset hex pin (6 × 2 = 12 assertions, locked in UI-SPEC) | unit | `pytest tests/test_theme.py -x -k locked_hex` | ✅ exists (new test) |
| THEME-02 | `system` preset stays `{}` | unit | `pytest tests/test_theme.py -x -k system_empty` | ✅ exists (new test) |
| THEME-02 | `EDITABLE_ROLES` length = 11 with new keys last | unit | `pytest tests/test_theme.py -x -k editable_roles` | ✅ exists (new test) |
| THEME-02 | `apply_theme_palette` sets `app.property("theme_name")` | unit | `pytest tests/test_theme.py -x -k property` | ✅ exists (new test) |
| THEME-02 | Editor shows 11 `_ColorRow` instances | unit | `pytest tests/test_theme_editor_dialog.py -x -k 11_color` | ✅ exists (update existing 9_color test) |
| THEME-02 | `ROLE_LABELS` has `"Toast background"` + `"Toast text"` | unit | `pytest tests/test_theme_editor_dialog.py -x -k label` | ✅ exists (new test) |
| THEME-02 | Save round-trips both new keys to `theme_custom` JSON | unit | `pytest tests/test_theme_editor_dialog.py -x -k save` | ✅ exists (extend existing Save test) |
| THEME-02 | Reset restores both new keys to source-preset | unit | `pytest tests/test_theme_editor_dialog.py -x -k reset` | ✅ exists (extend existing Reset test) |
| THEME-02 | Cancel restores both new roles in palette | unit | `pytest tests/test_theme_editor_dialog.py -x -k cancel` | ✅ exists (extend existing Cancel test) |
| THEME-02 | Picker tile click sets `theme_name` property | integration | `pytest tests/test_theme_picker_dialog.py -x -k property` | ✅ exists (new test) |
| THEME-02 | Picker tile click retints visible toast | integration | `pytest tests/test_theme_picker_dialog.py -x -k retint` | ✅ exists (new test) |
| THEME-02 (manual UAT) | Wayland live-flip: pick theme via picker → currently-visible toast retints instantly | manual | (no command — UAT) | — |

### Sampling Rate

- **Per task commit:** `pytest tests/test_toast_overlay.py tests/test_theme.py -x` (~2-3 s on offscreen)
- **Per wave merge:** Full 4-file run (~5-8 s)
- **Phase gate:** Full 4-file suite green before `/gsd-verify-work`

### Wave 0 Gaps

None — all 4 test files exist; Phase 75 extends rather than creates.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | `musicstreamer.accent_utils._is_valid_hex` already validates every hex in `theme_custom` JSON via `theme.build_palette_from_dict` (`theme.py:180`). New ToolTipBase/ToolTipText keys flow through this same validator — no new validation code required. |
| V6 Cryptography | no | — |

### Known Threat Patterns for {Python desktop / Qt widget}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Tampered `theme_custom` JSON injects QSS via hex value | Tampering | `_is_valid_hex` regex constrains values to `#[0-9a-fA-F]{6}` (validated at `accent_utils.py`). QColor only consumes validated hex. setStyleSheet f-string interpolation uses `.red() .green() .blue()` (int) and `QColor.name()` (validated lowercase hex), never raw user-controlled strings. |
| Tampered JSON injects unknown `QPalette.ColorRole` name | Tampering | `getattr(QPalette.ColorRole, role_name, None)` returns None for unknown names; loop continues. No exception, no crash. Verified at `theme.py:182-184`. |
| ZIP-import payload with malformed `theme_custom` value | Tampering | Existing JSONDecodeError catch at `theme.py:217-220` + isinstance(dict) at line 222 catches tampered values. Phase 75 inherits this defense for additive keys. |

## Project Constraints (from CLAUDE.md)

- Routing: spike-findings-musicstreamer skill exists for Windows packaging concerns. Phase 75 is pure Linux Wayland / Qt code, no GStreamer/PyInstaller/conda-forge concerns — skill NOT relevant.

## Sources

### Primary (HIGH confidence — codebase file:line citations)

- `musicstreamer/theme.py` (entire file, 232 lines) — THEME_PRESETS, EDITABLE_ROLES, build_palette_from_dict, apply_theme_palette
- `musicstreamer/ui_qt/toast.py` (entire file, 115 lines) — modification target
- `musicstreamer/ui_qt/theme_picker_dialog.py:260-285` — _on_tile_clicked, mirror site
- `musicstreamer/ui_qt/theme_editor_dialog.py` (entire file, 315 lines) — ROLE_LABELS, EDITABLE_ROLES iteration, _compute_source_palette, Save/Reset/Cancel
- `musicstreamer/ui_qt/now_playing_panel.py:194-197` — changeEvent template
- `musicstreamer/ui_qt/eq_response_curve.py:121-124` — second changeEvent example
- `musicstreamer/__main__.py:88-89, 196-201` — ToolTipBase/ToolTipText usage on Windows; apply_theme_palette call site
- `musicstreamer/ui_qt/main_window.py:356, 539-541` — ToastOverlay construction + show_toast proxy
- `musicstreamer/settings_export.py:40, 178-181` — ZIP export of all settings rows
- `tests/conftest.py:13` — QT_QPA_PLATFORM=offscreen
- `tests/test_toast_overlay.py` (entire file) — fixture + line 143 + existing 14 tests
- `tests/test_theme.py` — existing per-preset assertions, qapp/repo fixtures
- `tests/test_theme_editor_dialog.py` — Save/Reset/Cancel patterns, _FakePicker stub, stub_color_dialog fixture
- `tests/test_theme_picker_dialog.py` — tile-click pattern, FakeRepo, dialog fixture
- `.planning/phases/75-extend-theme-coloring-to-include-toast-colors-phase-66-intro/75-CONTEXT.md` (entire file) — locked decisions
- `.planning/phases/75-extend-theme-coloring-to-include-toast-colors-phase-66-intro/75-UI-SPEC.md` (entire file) — locked hex pairs, geometry/typography invariants, test surface
- `.planning/REQUIREMENTS.md:44, 154` — THEME-01 entry + status table

### Secondary (MEDIUM confidence — official docs)

- Qt 6.11 `QWidget` docs (https://doc.qt.io/qt-6/qwidget.html) — changeEvent semantics, PaletteChange/StyleChange propagation
- runebook.dev "Qt changeEvent() Explained" — recursion warnings on changeEvent
- Qt Forum thread "Stylesheet recomputing after property change" (https://forum.qt.io/topic/81644) — confirms setStyleSheet re-fires StyleChange

### Tertiary (LOW confidence — none needed)

No claims rest on unverified sources. All recursion-risk and event-dispatch claims cross-verified between Qt docs + Qt forum + runebook.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — no new libraries; codebase introspection only
- Architecture: HIGH — extends Phase 66 patterns 1:1; mirror sites identified by code reading
- Pitfalls: HIGH — Risk 1 verified against Qt 6.11 docs + forum; Risk 6 verified by grep; Risks 2/3/4/5/7 verified by code reading
- Test plumbing: HIGH — fixture origins, mock patterns, and assertion sites all cited file:line

**Research date:** 2026-05-15
**Valid until:** 2026-06-14 (30 days — stable codebase, no fast-moving deps)
