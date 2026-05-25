# Phase 59: Visual Accent Color Picker - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the existing `AccentColorDialog` (8 preset swatches + hex entry) with a thin wrapper around Qt's stock `QColorDialog`, giving users a full HSV/wheel + saturation-value square + numeric R/G/B/H/S/V fields + screen-color eyedropper to pick an arbitrary accent color. The 8 curated presets (`ACCENT_PRESETS`) survive as one-click shortcuts seeded into `QColorDialog`'s Custom Colors slots; the standalone preset-grid surface is removed.

The persisted SQLite key remains `accent_color` (hex string), the Highlight palette role is still the override target (per Phase 66 checkpoint), and the public class name `AccentColorDialog` is preserved so `main_window.py:53` (`from musicstreamer.ui_qt.accent_color_dialog import AccentColorDialog`) and `main_window.py:680-682` (`_open_accent_dialog`) need no changes.

**In scope:**
- Rewrite `musicstreamer/ui_qt/accent_color_dialog.py` so `AccentColorDialog` constructs and returns a `QColorDialog`-based picker (subclass or factory with a wrapper QDialog — planner's call).
- Seed `QColorDialog.setCustomColor(0..7, ...)` with `ACCENT_PRESETS` on every dialog open (idempotent reseed).
- Wire `currentColorChanged` → `apply_accent_palette` for live preview matching today's keystroke-live behavior.
- Add a Reset button to the dialog button row (QColorDialog only ships OK / Cancel).
- Preserve current snapshot-and-restore semantics: snapshot palette + styleSheet at open, Cancel restores both, Reset clears repo setting + restores snapshot but keeps dialog open.
- Apply (OK) writes `repo.set_setting("accent_color", hex)` and writes `paths.accent_css_path()` QSS file (same as today, `accent_color_dialog.py:171-184`).
- Pre-select saved `accent_color` (or `ACCENT_COLOR_DEFAULT` blue if unset) via `setCurrentColor` on open.
- Disable native OS dialog (`DontUseNativeDialog`) so `setCustomColor` seeding + screen-color eyedropper work consistently across Linux/Windows.
- Update or rewrite `tests/test_accent_color_dialog.py` to target the new QColorDialog-based shape (existing tests use `dialog._swatches` and `dialog._hex_edit` which are removed).

**Out of scope:**
- Persisting "recent custom colors" across sessions in repo. No new SQLite key. The seeded 8 preset slots reset on every dialog open; user-edited slots 8..15 in QColorDialog's Custom Colors row die with the process.
- Alpha / transparency channel. `ShowAlphaChannel` stays OFF — Highlight palette + slider QSS don't render translucent accents reliably and the requirement is solid colors only (ACCENT-02).
- Native OS color dialog. `DontUseNativeDialog` is set so that `setCustomColor`, eyedropper, and option toggles behave identically on Linux X11 (deployment target) and Windows.
- Modeless behavior. Dialog stays modal — same as today and every other dialog in the app.
- Theme-system integration changes. Phase 66's checkpoint already locks the layered Highlight model (theme owns Highlight by default; accent_color overrides when non-empty). Phase 59 does NOT touch theme code; it just replaces the picker UI for the existing accent_color setting.
- Touching `accent_utils.py` (build_accent_qss, apply_accent_palette, reset_accent_palette, _is_valid_hex). All four helpers are reused as-is from the new wrapper.
- Renaming the hamburger menu action ("Accent Color"), the SQLite key (`accent_color`), the QSS file path, or the requirement label (ACCENT-02). User-facing copywriting stays identical.
- Removing or renaming the `ACCENT_PRESETS` constant. It survives as the seed source for QColorDialog Custom Colors and as the canonical reference for `ACCENT_COLOR_DEFAULT`.

</domain>

<decisions>
## Implementation Decisions

### Picker surface

- **D-01:** Use Qt's stock `PySide6.QtWidgets.QColorDialog` as the visual picker. No custom HSV widget, no third-party color-picker library. Qt's dialog supplies the hue ring (or hue+sat square depending on platform), saturation/value square, R/G/B + H/S/V numeric fields, hex field, and screen-color eyedropper out of the box.
- **D-02:** **Drop the standalone 8-preset swatch row** from `AccentColorDialog`. The current `QPushButton`-based 4×2 grid (`accent_color_dialog.py:81-96`) and its handlers (`_on_swatch_clicked`, `_select_swatch`, `_deselect_all_swatches`) are removed. The 8 presets continue to exist as `ACCENT_PRESETS` in `constants.py:74-83` — they are seeded into QColorDialog's Custom Colors row instead (D-03).
- **D-03:** **Seed `ACCENT_PRESETS` into `QColorDialog.setCustomColor(idx, QColor(hex))` for `idx in 0..7`** every time the wrapper dialog is constructed. This is idempotent — if the user has somehow edited a custom-color slot in a previous dialog instance within the same process, slots 0..7 are overwritten back to the curated presets on next open. Slots 8..15 stay at their default (white) and are user-editable within a session; they die with the process. **Do not** seed at app startup (introduces a startup-time concern that's hard to test without running the full app); seed inside the wrapper's `__init__`.
- **D-04:** **Set `QColorDialog.ColorDialogOption.DontUseNativeDialog`** explicitly. Required so `setCustomColor` is honored (native dialogs ignore Qt's custom-color array on Linux/Windows) and so the screen-color eyedropper button is rendered (Qt-only feature). Trade-off: the dialog will look Qt-styled rather than GTK-styled on the user's Linux X11 desktop — acceptable, matches the rest of the app which is already Qt-styled.
- **D-05:** **Set `QColorDialog.ColorDialogOption.ShowAlphaChannel = False`** (default — explicit for clarity). No transparency. Solid hex colors only.
- **D-06:** **Eyedropper / "Pick Screen Color" is enabled** (default behavior under `DontUseNativeDialog` on Linux X11 + Windows). No additional configuration needed.

### Integration shape

- **D-07:** **Replace `AccentColorDialog`'s implementation** with a thin wrapper around `QColorDialog`. Two acceptable shapes (planner picks):
  - (a) `class AccentColorDialog(QColorDialog)` — subclass that adds a Reset button, wires preview, manages snapshot. Fewer LOC, but `QColorDialog`'s internal layout is private and subclassing it for a custom button is brittle.
  - (b) `class AccentColorDialog(QDialog)` — wrapper QDialog whose body is a `QColorDialog` widget with `NoButtons` + the wrapper's own Apply / Reset / Cancel button row below. More predictable, ~30-50 LOC overhead.
  - Recommended path: (b) — the QColorDialog widget can be added directly to a QVBoxLayout when constructed with `NoButtons`, and the wrapper retains full control over its own button row identical to today's shape.
- **D-08:** **Preserve the public class name `AccentColorDialog` in `musicstreamer/ui_qt/accent_color_dialog.py`** so the existing import + launch site at `main_window.py:53, 680-682` are untouched. Constructor signature stays `AccentColorDialog(repo, parent=None)`. `dlg.exec()` semantics unchanged from caller's perspective.
- **D-09:** **Reset button location:** in the dialog's button row, label `"Reset"`, role `QDialogButtonBox.ResetRole` (matches today's button at `accent_color_dialog.py:113`). Order in the row: `Apply | Reset | Cancel` (same as today). Reset semantics: clear `accent_color` setting, restore snapshot palette, deselect any non-default color in the picker (calling `setCurrentColor(QColor(ACCENT_COLOR_DEFAULT))` is acceptable), keep dialog open so user can re-pick or cancel.
- **D-10:** **Modality is `setModal(True)`** — same as today (`accent_color_dialog.py:57`). User must Apply or Cancel before resuming main window interaction. Window-manager close (X) routes through `reject()` and triggers the snapshot restore (D-13).

### Live preview

- **D-11:** **Wire `QColorDialog.currentColorChanged(QColor)` → `apply_accent_palette(QApplication.instance(), color.name())`** with no throttling, no QTimer coalescing. Matches today's keystroke-live preview semantics on the hex field. `apply_accent_palette` is cheap (palette swap + 1-line QSS via `setStyleSheet`); Qt batches repaints; QColorDialog itself only emits during user interaction. If the planner observes visible flicker on the target hardware (Linux X11 DPR=1.0), a `QTimer.singleShot(50, …)` debounce can be added — but ship without it first.
- **D-12:** **Track the in-flight previewed hex in `self._current_hex`** (same field as today, `accent_color_dialog.py:53`) so the Apply handler can persist it without re-reading from QColorDialog.
- **D-13:** **Cancel semantics — restore snapshot:** snapshot `QApplication.palette()` and `QApplication.styleSheet()` in `__init__` (today: lines 49-51, behavior unchanged). On `reject()`: `app.setPalette(self._original_palette); app.setStyleSheet(self._original_qss)`. **Do not** read repo on cancel — the snapshot is the source of truth for "where we were before opening the dialog". Window-manager close (X) routes through `reject()` automatically.
- **D-14:** **Apply (OK) semantics — same as today** (`accent_color_dialog.py:171-184`):
  1. Bail if `self._current_hex` is empty or invalid (defense-in-depth — `currentColorChanged` always emits valid `QColor` values, so this is belt-and-suspenders).
  2. `repo.set_setting("accent_color", self._current_hex)`.
  3. `os.makedirs(os.path.dirname(paths.accent_css_path()), exist_ok=True)` then write `build_accent_qss(self._current_hex)` to that path. Wrap in `try: … except OSError: pass` (non-fatal; palette is already applied via QPalette).
  4. `self.accept()`.
- **D-15:** **Reset semantics:**
  1. `repo.set_setting("accent_color", "")` — clears persisted override.
  2. `reset_accent_palette(QApplication.instance(), self._original_palette)` — restores snapshot.
  3. `setCurrentColor(QColor(ACCENT_COLOR_DEFAULT))` — picker visually returns to default blue so the user sees the reset took effect.
  4. `self._current_hex = ""` — Apply path no-ops if the user clicks Apply right after Reset.
  5. **Dialog stays open.** User can re-pick or Cancel.
  6. **Optional QSS-file cleanup:** call `os.remove(paths.accent_css_path())` if the file exists, wrapped in a `try: … except OSError: pass`. Keeps the on-disk state clean and prevents stale QSS application on next startup. Planner decision — minor polish.

### Custom-color memory

- **D-16:** **No persistence of "recent custom colors" across sessions.** No new SQLite setting. The user's last applied color is reflected in `setCurrentColor(saved_hex)` on dialog open (D-17), but slot positions 8..15 in QColorDialog's Custom Colors row are not saved. This keeps the repo schema unchanged and avoids coupling Phase 59 to a future "color history" feature.
- **D-17:** **Pre-select on open:** `saved_hex = repo.get_setting("accent_color", ACCENT_COLOR_DEFAULT)` then `dlg.setCurrentColor(QColor(saved_hex))` (or via the wrapper's inner QColorDialog widget if shape (b) from D-07). The wheel + sat-val square + numeric fields all reflect the current accent on open. Defensive: if `saved_hex` is invalid (`_is_valid_hex(saved_hex)` returns False), fall back to `ACCENT_COLOR_DEFAULT`.

### Tests

- **D-18:** **Rewrite `tests/test_accent_color_dialog.py`** (107 lines). Existing tests reference `dialog._swatches` and `dialog._hex_edit` which no longer exist — they will fail compilation. The new test set should cover at minimum:
  - Dialog constructs and seeds `QColorDialog.customColor(0..7) == ACCENT_PRESETS` (use `QColorDialog.customColor(idx).name()` for comparison; expect lowercase `#rrggbb`).
  - `setCurrentColor` reflects saved `accent_color` on open (replaces `test_load_saved_accent_selects_swatch`).
  - Selecting a color via `setCurrentColor` emits `currentColorChanged` and applies the palette (replaces `test_swatch_populates_hex_entry` + the hex-entry tests).
  - Apply (OK) saves `accent_color` to repo and writes the QSS file.
  - Reset clears `accent_color` setting and restores the snapshot palette.
  - Cancel does NOT touch repo and restores snapshot palette.
  - Window-manager close routes through `reject()` and behaves like Cancel.
- **D-19:** **`tests/test_accent_provider.py` (118 lines)** tests `accent_utils.py` (the QSS builder + palette helpers). Phase 59 does NOT touch `accent_utils.py`, so this test file should pass unchanged. **Verify** during plan checking that no test references the removed swatch grid.

### Claude's Discretion

- **Subclass vs. wrapper QDialog (D-07)** — recommended (b) wrapper, but planner can ship (a) subclass if the layout-injection of a Reset button proves clean on the target Qt 6.11 build. Either shape preserves the public `AccentColorDialog(repo, parent=None)` constructor.
- **Optional QSS-file cleanup on Reset (D-15.6)** — nice polish; planner decides whether to ship it. Without it, the stale `paths.accent_css_path()` file persists on disk after Reset until a non-empty accent is saved (and overwrites it). Functionally harmless — `main_window.py:189-192` only loads the file when `accent_color` setting is non-empty — but it leaves clutter.
- **Throttle on `currentColorChanged` (D-11)** — locked default is "no throttle". Planner promotes to a `QTimer.singleShot(~50ms, …)` coalescer only if the implementer observes visible flicker on the target Linux X11 DPR=1.0 hardware. Capture the alternative explicitly in PLAN.md for visibility either way.
- **Reset button label / role** — locked is `"Reset"` + `ResetRole`. Planner can rename to `"Clear"` if it reads better in context, but keep the role for stylistic consistency with today.
- **Whether Reset also writes `paths.accent_css_path()` to empty string** vs. removing the file vs. leaving it alone — see D-15.6. All three are acceptable; pick one and note it.
- **Test fixture shape** — the planner picks how to instantiate `AccentColorDialog` in tests (likely via `qtbot.addWidget(dlg)` like today's fixture at `tests/test_accent_color_dialog.py:30-46`). Repo can stay an in-memory fixture as today.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements

- `.planning/ROADMAP.md` §"Phase 59: Visual Accent Color Picker" (lines 314-324) — goal, four success criteria.
- `.planning/REQUIREMENTS.md` §ACCENT-02 (line 40) — "User can pick a custom accent color via a visual color picker (HSV/wheel surface), in addition to the existing 8 presets and hex entry." Note: "in addition to" is satisfied here by seeding the 8 presets into QColorDialog's Custom Colors row (D-03), not by keeping a separate swatch grid.
- `.planning/seeds/SEED-006-accent-color-wheel.md` — original seed for the visual color wheel follow-up to SEED-002.
- `.planning/seeds/SEED-002-custom-highlight-color.md` (✅ shipped as v1.4 Phase 19) — the original 8-preset + hex feature; provides the historical context for what's being upgraded.

### Phase 19 / 40 precedent (what exists today — DO NOT BREAK the public API)

- `musicstreamer/ui_qt/accent_color_dialog.py` (entire file, 235 lines) — current `AccentColorDialog` implementation. Phase 59 rewrites this file but preserves the public class name and constructor signature.
- `musicstreamer/accent_utils.py` (entire file, 71 lines) — `_is_valid_hex`, `build_accent_qss`, `apply_accent_palette`, `reset_accent_palette`. **Untouched** by Phase 59 — the wrapper calls these as-is.
- `musicstreamer/constants.py:72-83` — `ACCENT_COLOR_DEFAULT = "#3584e4"` and `ACCENT_PRESETS = [...]`. Both survive; `ACCENT_PRESETS` becomes the seed source for QColorDialog Custom Colors slots 0..7.
- `musicstreamer/ui_qt/main_window.py:53` — `from musicstreamer.ui_qt.accent_color_dialog import AccentColorDialog`. Must continue to import successfully.
- `musicstreamer/ui_qt/main_window.py:144-145` — hamburger menu wires `act_accent.triggered.connect(self._open_accent_dialog)`. Must continue to work; menu label `"Accent Color"` unchanged.
- `musicstreamer/ui_qt/main_window.py:189-192` — startup-time accent restore: reads `accent_color` from repo, applies if `_is_valid_hex(saved)`. Phase 59 doesn't touch this; it must continue to work with whatever hex the new picker writes.
- `musicstreamer/ui_qt/main_window.py:680-682` — `_open_accent_dialog` launcher: `dlg = AccentColorDialog(self._repo, parent=self); dlg.exec()`. Must continue to work as-is.
- `musicstreamer/paths.py:59` — `accent_css_path()`. Phase 59 keeps writing to this path on Apply (D-14).

### Phase 66 forward-compat (theme + accent layering — DO NOT REGRESS)

- `.planning/phases/66-color-themes-preset-and-custom-color-schemes-vaporwave-paste/66-DISCUSS-CHECKPOINT.json` — locked: "Theme owns Highlight by default; existing accent_color setting (and Phase 59's visual picker) layers on top to override Highlight when non-empty. Accent dialog Reset only clears accent_color override; theme's Highlight stays in effect." Phase 59's Reset (D-15) clears `accent_color` and restores snapshot — when Phase 66 lands, the snapshot will already have the theme's Highlight in place, and clearing `accent_color` will leave the theme Highlight untouched. **Do not** make Phase 59's Reset write a non-empty default into `accent_color` — that would break Phase 66's layering.

### Existing tests (planner must update or rewrite)

- `tests/test_accent_color_dialog.py` (107 lines) — exercises `dialog._swatches`, `dialog._hex_edit`, `_on_swatch_clicked`, `_load_saved_accent`. **Will not compile** against the new dialog — needs rewrite per D-18.
- `tests/test_accent_provider.py` (118 lines) — tests `accent_utils.py` only. **Should pass unchanged** — verify in plan-checker.

### Project conventions

- `.planning/codebase/CONVENTIONS.md` — snake_case, type hints throughout, no formatter, no linter on save.
- `.planning/codebase/STACK.md` — Python 3.10+, PySide6 6.11+, no new runtime deps for Phase 59 (QColorDialog ships with PySide6).
- `.planning/codebase/CONCERNS.md` — security review checklist; the `_is_valid_hex` validator is reused on the Apply path (defense-in-depth) even though `QColor` always produces valid hex.
- Bound-method signal connections, no self-capturing lambdas (QA-05) — applies to `currentColorChanged`, `Reset.clicked`, etc.
- Linux X11 deployment target, DPR=1.0 (per project memory) — HiDPI / Retina / Wayland-fractional findings in any UI audit downgrade from CRITICAL → WARNING. `DontUseNativeDialog` (D-04) ensures consistent rendering on this target.

### No external specs

No ADRs apply. The phase is captured by ROADMAP §Phase 59 (4 success criteria), ACCENT-02, the existing `accent_color_dialog.py` + `accent_utils.py` + `constants.py` triad, the Phase 66 theme-layering checkpoint, and Qt's `QColorDialog` documentation (stdlib — no external doc to vendor in).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`musicstreamer/accent_utils.py`** — all four exports (`_is_valid_hex`, `build_accent_qss`, `apply_accent_palette`, `reset_accent_palette`) are reused as-is. No changes.
- **`ACCENT_PRESETS` constant** (`constants.py:74`) — survives unchanged; becomes the seed source for `QColorDialog.setCustomColor(0..7, ...)` instead of a Python-rendered button grid.
- **`ACCENT_COLOR_DEFAULT` constant** (`constants.py:73`) — survives; is the fallback for `setCurrentColor` on open when `accent_color` is unset (D-17), and the visual reset target on Reset click (D-15).
- **`paths.accent_css_path()`** (`paths.py:59`) — same destination for the Apply-time QSS file write. No path change.
- **`QApplication.palette()` / `setPalette()` / `styleSheet()` / `setStyleSheet()` snapshot pattern** (`accent_color_dialog.py:49-51, 200-202`) — copy verbatim into the new wrapper.
- **`repo.get_setting` / `repo.set_setting`** — same SQLite settings table; no schema change.
- **`main_window.py:189-192` startup accent restore** — reads `accent_color` and applies. No coupling change.

### Established Patterns

- **Snapshot-and-restore for live-preview cancel** — Phase 19/40 invariant. Phase 59 preserves it (D-13).
- **Bound-method signal connections (QA-05)** — applies to `currentColorChanged.connect(self._on_color_changed)`, `Reset.clicked.connect(self._on_reset)`, etc.
- **`_is_valid_hex` defense-in-depth on Apply path** — even though `QColor.name()` always returns valid hex, the Apply handler validates again before persisting (D-14.1).
- **QSS file write wrapped in `try: … except OSError: pass`** — non-fatal on disk-write failure; palette is already applied (`accent_color_dialog.py:175-183`).
- **Modal QDialog with `setModal(True)`** — every other dialog in the app uses this; Phase 59 keeps it (D-10).

### Integration Points

- **Replaces:** `musicstreamer/ui_qt/accent_color_dialog.py` (235 lines → likely ~80-130 lines depending on subclass-vs-wrapper choice in D-07).
- **No new files** under `musicstreamer/` (no new helper module needed — wrapper is small enough to live in the same file).
- **Consumed by:** `main_window.py:53` (import), `main_window.py:680-682` (launch). Both untouched.
- **Public API surface:** `AccentColorDialog(repo, parent=None)` constructor + `.exec()` method. Same as today.
- **Test files:** `tests/test_accent_color_dialog.py` rewritten (D-18); `tests/test_accent_provider.py` should pass unchanged (D-19).

</code_context>

<specifics>
## Specific Ideas

- **The user-visible promise:** *"I open Accent Color, drag through a hue ring + sat/val square or click the eyedropper to grab a color from anywhere on screen, and the app's accent color updates live as I move. The 8 GTK-aligned presets are still one click away in the dialog's bottom swatch row."*
- **The 8 presets are not "presets" anymore — they are seeds in QColorDialog's Custom Colors row.** Functionally identical for the user (one click → that color is selected → live preview applies). The mental shift is: the user no longer sees a custom-built grid above a custom-built picker; they see a single Qt color dialog whose Custom Colors row has been preloaded with our 8.
- **Eyedropper is the killer feature unique to QColorDialog.** Letting users grab a color from anywhere on screen (a wallpaper, a website, another app's branding) is something the old 8-preset + hex dialog could never do. ACCENT-02 doesn't require it explicitly, but it's free and dramatically lifts the perceived quality of the picker.
- **Phase 66's checkpoint already accounts for Phase 59.** Phase 66 explicitly says "the existing accent_color setting (and Phase 59's visual picker) layers on top to override Highlight when non-empty". Reset's "clear accent_color" semantics (D-15) is the exact behavior Phase 66 expects.

</specifics>

<deferred>
## Deferred Ideas

- **Cross-session "recent custom colors" memory** — explicitly rejected (D-16). If a future user complaint surfaces ("I keep losing my exact teal"), a follow-up phase adds a `recent_accents` SQLite key (JSON list, max 8) and seeds slots 8..15 from it. Schema change is small; UX value is the open question.
- **Alpha channel / translucent accents** — explicitly rejected (D-05). Highlight palette + slider QSS sub-page rendering doesn't honor alpha consistently. If a future phase adds proper alpha-aware accent rendering across all consumers, ShowAlphaChannel can be enabled.
- **Native OS color dialog on Windows/macOS** — rejected (D-04). DontUseNativeDialog is required for setCustomColor seeding + eyedropper. If a future phase decides "native look beats curated presets", the trade-off can be revisited.
- **Modeless picker for live-preview-while-playing** — rejected (D-10). Playback already runs while the modal dialog is open (audio engine doesn't block on UI events); modeless adds risk for marginal UX gain.
- **QSS-file cleanup on Reset (D-15.6)** — captured as Claude's Discretion; if usage shows clutter accumulating, promote to a locked decision.
- **Throttle `currentColorChanged` previews** — captured as Claude's Discretion; promote if real-world flicker is observed.
- **Theme picker integration (Phase 66)** — out of scope. Phase 59 ships before Phase 66; the layering contract is documented in 66-DISCUSS-CHECKPOINT.json and Phase 59's Reset semantics (D-15) are designed to be compatible without Phase 59 owning any theme code.
- **Discoverability hints in the dialog** — e.g., a small label "Click the eyedropper to pick from screen" near the Pick Screen Color button. Not needed for v1; Qt's icon + tooltip on the eyedropper button are sufficient.

</deferred>

---

*Phase: 59-visual-accent-color-picker*
*Context gathered: 2026-05-03*
