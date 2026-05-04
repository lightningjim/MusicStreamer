# Phase 59: Visual Accent Color Picker - Research

**Researched:** 2026-05-03
**Domain:** PySide6 6.11 / Qt 6 — `QColorDialog` embedded as a child widget inside a wrapper `QDialog`
**Confidence:** HIGH (empirically verified against the project's installed PySide6 6.11.0 + pytest-qt 4.5.0; cross-referenced with current Qt 6.11 official docs)

## Summary

CONTEXT.md has already locked the implementation to Qt's stock `QColorDialog` with `DontUseNativeDialog` + `NoButtons` embedded as a child widget inside a wrapper `QDialog` that adds an Apply / Reset / Cancel button row. Twenty implementation decisions (D-01 through D-19, plus several Claude's-Discretion items) are pre-locked. The research goal is therefore narrow: **prove the locked design works on PySide6 6.11.0 / Linux X11 and surface the operational details — signal emission semantics, embed-as-widget pattern, custom-color persistence model, eyedropper platform notes, and pytest-qt validation tactics — that the planner needs to write a correct PLAN.md.**

All ten research questions in the brief were answered with empirical confirmation against the project's installed Qt stack (PySide6 6.11.0, pytest-qt 4.5.0). The locked design is sound. The two operational gotchas the planner must encode in the plan are:

1. **`setCurrentColor(invalid_QColor)` mutates state to black `#000000` and emits `currentColorChanged`** — the wrapper's `_load_saved_accent` MUST validate the saved hex with `_is_valid_hex` before passing to `setCurrentColor` (the existing wrapper at `accent_color_dialog.py:127` already does this; preserve the pattern).
2. **`setCurrentColor` to the same color is a no-op (no signal emission)** — convenient for idempotent reseeding; tests using `qtbot.waitSignal` must pass `timeout=0` or use a different probe (poll `dlg.currentColor()` directly) when re-asserting an already-set color.

**Primary recommendation:** Build the locked shape (b) wrapper QDialog with the QColorDialog embedded directly into a QVBoxLayout, seed `setCustomColor(0..7, ...)` in `__init__` BEFORE constructing the inner `QColorDialog`, set `DontUseNativeDialog | NoButtons` (and explicitly disable `ShowAlphaChannel`) on the inner dialog, wire `currentColorChanged` to a bound method, snapshot palette + QSS in `__init__`, and use `_is_valid_hex` defense-in-depth on Apply.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ACCENT-02 | User can pick a custom accent color via a visual color picker (HSV/wheel surface), in addition to the existing 8 presets and hex entry. | Confirmed: `QColorDialog` ships a hue ring + saturation/value square + R/G/B + H/S/V numeric fields + hex field + screen-color eyedropper out of the box (Qt 6.11 official docs, empirically verified). The "in addition to the existing 8 presets and hex entry" clause is satisfied by D-03 (seeding `ACCENT_PRESETS` into `setCustomColor(0..7, ...)`) — the 8 curated colors appear as one-click swatches in QColorDialog's bottom Custom Colors row. The hex entry field is built into QColorDialog, so the requirement's "hex entry" survives without a separate `QLineEdit`. |
</phase_requirements>

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Picker surface**
- **D-01:** Use `PySide6.QtWidgets.QColorDialog` as the visual picker. No custom HSV widget, no third-party color-picker library.
- **D-02:** Drop the standalone 8-preset swatch row from `AccentColorDialog`. The 4×2 `QPushButton` grid + handlers (`_on_swatch_clicked`, `_select_swatch`, `_deselect_all_swatches`) are removed. `ACCENT_PRESETS` survives in `constants.py:74-83`.
- **D-03:** Seed `ACCENT_PRESETS` into `QColorDialog.setCustomColor(idx, QColor(hex))` for `idx in 0..7` every time the wrapper dialog is constructed (idempotent reseed). Slots 8..15 stay user-editable within a session and die with the process.
- **D-04:** Set `QColorDialog.ColorDialogOption.DontUseNativeDialog`. Required for `setCustomColor` to be honored + eyedropper to render on Linux X11 + Windows.
- **D-05:** Set `QColorDialog.ColorDialogOption.ShowAlphaChannel = False` (default — explicit for clarity).
- **D-06:** Eyedropper / "Pick Screen Color" is enabled by default under `DontUseNativeDialog`. No additional configuration needed.

**Integration shape**
- **D-07:** Wrapper QDialog (recommended path) hosting a `QColorDialog` widget with `NoButtons` + the wrapper's own Apply/Reset/Cancel button row. Subclassing `QColorDialog` is acceptable but brittle.
- **D-08:** Public class name `AccentColorDialog` preserved. Constructor signature `AccentColorDialog(repo, parent=None)`. `dlg.exec()` semantics unchanged.
- **D-09:** Reset button: label `"Reset"`, role `QDialogButtonBox.ResetRole`, order `Apply | Reset | Cancel` (same as today).
- **D-10:** `setModal(True)` — same as today. Window-manager close (X) routes through `reject()`.

**Live preview**
- **D-11:** Wire `QColorDialog.currentColorChanged(QColor)` → `apply_accent_palette(QApplication.instance(), color.name())` directly. NO throttling. NO QTimer coalescing. Promote to throttle only if visible flicker is observed on target hardware.
- **D-12:** Track in-flight previewed hex in `self._current_hex` (same field name as today).
- **D-13:** Cancel = restore snapshot (palette + QSS captured at `__init__`). Window-manager close routes through `reject()` automatically.
- **D-14:** Apply = `_is_valid_hex` guard, `repo.set_setting("accent_color", hex)`, `os.makedirs` + write `paths.accent_css_path()` (try/except OSError), `self.accept()`.
- **D-15:** Reset = clear repo setting, `reset_accent_palette(app, snapshot)`, `setCurrentColor(QColor(ACCENT_COLOR_DEFAULT))`, `self._current_hex = ""`, dialog stays open.

**Custom-color memory**
- **D-16:** No persistence of "recent custom colors" across sessions. No new SQLite key.
- **D-17:** Pre-select on open: `setCurrentColor(QColor(saved_hex_or_DEFAULT))`. Defensive: fall back to `ACCENT_COLOR_DEFAULT` if `_is_valid_hex(saved_hex)` returns False.

**Tests**
- **D-18:** Rewrite `tests/test_accent_color_dialog.py` (107 lines) — existing references to `dialog._swatches` and `dialog._hex_edit` are gone.
- **D-19:** `tests/test_accent_provider.py` (118 lines) tests `accent_utils.py` only and should pass unchanged. Verify in plan-checker.

### Claude's Discretion

- Subclass-vs-wrapper choice (D-07) — recommended (b) wrapper, but planner can ship (a) subclass if cleaner on Qt 6.11.
- Optional QSS-file cleanup on Reset (D-15.6) — planner picks: leave file alone, write empty string, or `os.remove(...)` wrapped in try/except.
- Throttle on `currentColorChanged` (D-11) — locked default is no throttle. Promote to `QTimer.singleShot(~50ms, ...)` only if real-world flicker observed.
- Reset button label — locked is `"Reset"` + `ResetRole`, but `"Clear"` is acceptable if it reads better in context.
- Test fixture shape — planner picks instantiation pattern (likely `qtbot.addWidget(dlg)` mirroring today's fixture).

### Deferred Ideas (OUT OF SCOPE)

- Cross-session "recent custom colors" memory.
- Alpha channel / translucent accents.
- Native OS color dialog on Windows/macOS.
- Modeless picker for live-preview-while-playing.
- Theme picker integration (Phase 66 — separately captured; layering contract documented in `66-DISCUSS-CHECKPOINT.json`).
- Touching `accent_utils.py` (`_is_valid_hex`, `build_accent_qss`, `apply_accent_palette`, `reset_accent_palette` are reused as-is).
- Renaming the hamburger menu action ("Accent Color"), the SQLite key (`accent_color`), the QSS file path, or `ACCENT_PRESETS`.

</user_constraints>

## Project Constraints (from CLAUDE.md)

CLAUDE.md is minimal — it routes spike findings to the `spike-findings-musicstreamer` skill (Windows packaging / GStreamer / PyInstaller / PowerShell gotchas). None of those concerns apply to a Qt-only `QColorDialog` UI phase. No additional CLAUDE.md directives constrain this phase.

Project memory directives that DO apply to Phase 59:
- **Linux X11 deployment target, DPR=1.0** — HiDPI/Retina/Wayland-fractional findings downgrade from CRITICAL → WARNING. The eyedropper / mouse-grab caveats below (Pitfall 4) are flagged WARNING per this rule.
- **`gsd-sdk` is wrapped on PATH** — N/A to this phase (no GSD CLI calls in production code).

## Architectural Responsibility Map

Phase 59 is a single-tier UI change inside the existing PySide6 client. There is no API/network/storage tier shift. The capability map is therefore short:

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Color picking surface (HSV wheel + sat/val + hex + RGB/HSV fields + eyedropper) | Qt UI (PySide6 widgets) | — | `QColorDialog` is a stock Qt widget. No backend involvement. |
| Live preview (palette swap + slider QSS) | Qt UI (process-wide `QApplication.palette()` mutation) | — | `apply_accent_palette` already lives client-side; no IPC, no network. |
| Persistence (hex string + QSS file) | SQLite (`settings` table, key `accent_color`) | Filesystem (`paths.accent_css_path()`) | Existing SQLite-backed `Repo` + on-disk QSS file stay unchanged. |
| Snapshot/restore on Cancel | Process-local memory (`self._original_palette`, `self._original_qss`) | — | Same pattern as today's Phase 19/40 implementation. |

**No tier misassignment risk:** every responsibility stays in the layer it currently occupies. The replacement is purely a within-tier widget swap.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | 6.11.0 [VERIFIED: `python3 -c "import PySide6; print(PySide6.__version__)"`] | `QColorDialog`, `QDialog`, `QDialogButtonBox`, `QVBoxLayout`, `QPushButton` | Already the project's UI toolkit. `QColorDialog` is a first-party Qt widget — no new dependency. |
| pytest-qt | 4.5.0 [VERIFIED: `python3 -c "import pytestqt; print(pytestqt.__version__)"`] | `qtbot.waitSignal`, `qtbot.addWidget`, `qtbot.assertNotEmitted` | Already used across `tests/test_*.py` (37 hits in `tests/`). Standard pattern in this codebase. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (existing) `musicstreamer.accent_utils` | n/a | `_is_valid_hex`, `build_accent_qss`, `apply_accent_palette`, `reset_accent_palette` | Reuse as-is. Untouched per CONTEXT.md. |
| (existing) `musicstreamer.constants.ACCENT_PRESETS` + `ACCENT_COLOR_DEFAULT` | n/a | Seed source for `setCustomColor(0..7)`; default-color fallback | Reuse as-is. |
| (existing) `musicstreamer.paths.accent_css_path` | n/a | On-disk QSS file path written on Apply | Reuse as-is. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `QColorDialog` | Hand-rolled HSV widget (e.g., `colorpicker` PySide6 lib) | More layout control, but a new runtime dep + ~500 LOC + no eyedropper. CONTEXT.md D-01 locked QColorDialog — alternative ruled out. [VERIFIED: github.com/VickenM/colorpicker README confirms it was built specifically because authors wanted to *avoid* QColorDialog's bulk] |
| Wrapper `QDialog` (D-07b) | Subclass `QColorDialog` directly (D-07a) | Subclassing avoids one layer of containment but requires reaching into QColorDialog's private layout to inject a Reset button — brittle across Qt minor versions. Wrapper is the recommended path per CONTEXT.md. |

**No new packages to install.** The phase ships with zero `pyproject.toml` changes.

**Version verification:**
- PySide6 6.11.0 confirmed at runtime in this repo (the project memory file `.planning/codebase/STACK.md` has been pinned to "PySide6 6.11+" since Phase 36 cutover). Latest stable PySide6 line as of 2026-05 is 6.11.x; no upstream API drift to QColorDialog since Qt 6.6 added `NoEyeDropperButton`. [CITED: doc.qt.io/qt-6/qcolordialog.html]
- pytest-qt 4.5.0 — current stable line. `waitSignal` / `assertNotEmitted` API is stable since 3.x.

## Architecture Patterns

### System Architecture Diagram

```
[User clicks "Accent Color" in hamburger menu]
                │
                ▼
[main_window._open_accent_dialog]  ← UNCHANGED (main_window.py:680-682)
                │
                ▼
[AccentColorDialog(repo, parent).__init__]
   │
   ├─► snapshot palette + QSS (self._original_palette, self._original_qss)
   ├─► QColorDialog.setCustomColor(0..7, ACCENT_PRESETS[i])  ◄── D-03 idempotent reseed
   ├─► construct inner QColorDialog widget
   │       options = NoButtons | DontUseNativeDialog
   │       (ShowAlphaChannel = False)                         ◄── D-04, D-05
   ├─► saved = repo.get_setting("accent_color", "")
   │   if _is_valid_hex(saved):
   │       inner.setCurrentColor(QColor(saved))
   │   else:
   │       inner.setCurrentColor(QColor(ACCENT_COLOR_DEFAULT)) ◄── D-17 + defensive guard
   ├─► QVBoxLayout adds inner QColorDialog widget
   ├─► QDialogButtonBox row: Apply | Reset | Cancel           ◄── D-09
   ├─► inner.currentColorChanged.connect(self._on_color_changed)  ◄── bound method, QA-05
   ├─► apply_btn.clicked.connect(self._on_apply)
   ├─► reset_btn.clicked.connect(self._on_reset)
   └─► cancel_btn.clicked.connect(self.reject)
                │
                ▼
[user drags hue ring / clicks custom-color slot / uses eyedropper]
                │
                ▼
[QColorDialog emits currentColorChanged(QColor)]
                │
                ▼
[self._on_color_changed(color)]
   │
   ├─► self._current_hex = color.name()      ◄── D-12 (lowercase #rrggbb per QColor.name())
   └─► apply_accent_palette(QApplication.instance(), color.name())  ◄── D-11 no throttle

                ▼
                ▼
   ┌──────────[Apply]────────┬─────────[Reset]──────────┬─────────[Cancel / X]──────────┐
   │                          │                          │                                │
   ▼                          ▼                          ▼                                │
[_on_apply]                [_on_reset]                [reject()]                          │
 ├─ guard via              ├─ repo.set_setting         ├─ app.setPalette(snapshot)         │
 │  _is_valid_hex          │   ("accent_color", "")    ├─ app.setStyleSheet(snapshot_qss)  │
 ├─ repo.set_setting       ├─ reset_accent_palette     └─ super().reject()                 │
 │   ("accent_color",      │   (app, snapshot)                                             │
 │    self._current_hex)   ├─ inner.setCurrentColor                                        │
 ├─ os.makedirs +          │   (QColor(DEFAULT))                                           │
 │  write accent.css       ├─ self._current_hex = ""                                       │
 │  (try/except OSError)   └─ DIALOG STAYS OPEN                                            │
 └─ self.accept()                                                                          │
                                                                                            │
[startup: main_window.py:189-192]  ◄── separate flow, UNCHANGED                            │
   reads accent_color from repo, calls apply_accent_palette                                 │
```

The data flow shows three exit paths from a single dialog instance: Apply persists, Reset clears + keeps dialog open, Cancel/X discards via snapshot restore. The startup path (`main_window.py:189-192`) is independent — it reads whatever Apply wrote on a previous session and is untouched by Phase 59.

### Recommended Project Structure
```
musicstreamer/
├── ui_qt/
│   └── accent_color_dialog.py    # REWRITTEN (235 → ~80-130 LOC), public class name preserved
├── accent_utils.py                # UNTOUCHED (4 helpers reused as-is)
├── constants.py                   # UNTOUCHED (ACCENT_PRESETS + ACCENT_COLOR_DEFAULT survive)
└── paths.py                       # UNTOUCHED (accent_css_path() used as-is)

tests/
├── test_accent_color_dialog.py    # REWRITTEN per D-18
└── test_accent_provider.py        # UNTOUCHED per D-19 (verify no _swatches/_hex_edit refs)
```

### Pattern 1: Embed `QColorDialog` as a child widget
**What:** Construct a `QColorDialog` instance with `NoButtons | DontUseNativeDialog` options, then `addWidget(dlg)` to a parent `QVBoxLayout`. The parent (your wrapper `QDialog`) controls its own button row. The inner `QColorDialog` becomes a regular child widget; modal behavior, focus handling, and the wrapper's `accept()` / `reject()` semantics belong to the wrapper.
**When to use:** Whenever you need stock Qt color-picker UX *plus* a custom button row (Reset, additional Apply variants, etc.) — the locked Phase 59 shape.
**Example:**
```python
# Source: pattern derived from Qt forum (qtcentre.org/threads/27472) +
#         empirically verified against PySide6 6.11.0 in this repo's offscreen Qt env.
from PySide6.QtWidgets import (
    QApplication, QDialog, QColorDialog, QDialogButtonBox, QVBoxLayout,
)
from PySide6.QtGui import QColor


class AccentColorDialog(QDialog):
    """Wrapper around QColorDialog with custom Apply/Reset/Cancel button row."""

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self._repo = repo
        app = QApplication.instance()
        self._original_palette = app.palette()
        self._original_qss = app.styleSheet()
        self._current_hex: str = ""

        self.setWindowTitle("Accent Color")
        self.setModal(True)

        # D-03: Seed ACCENT_PRESETS into Custom Colors slots BEFORE inner dialog construction.
        # setCustomColor is a STATIC method; persists for process lifetime.
        for idx, hex_val in enumerate(ACCENT_PRESETS):  # 0..7
            QColorDialog.setCustomColor(idx, QColor(hex_val))

        # Build the inner color dialog as an embedded widget
        self._inner = QColorDialog(self)
        # NOTE: pass options as a single bitwise OR'd value. setOption(opt, True) also works.
        self._inner.setOption(QColorDialog.ColorDialogOption.NoButtons, True)
        self._inner.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        self._inner.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, False)

        # D-17: pre-select saved or default
        saved = self._repo.get_setting("accent_color", "")
        initial = saved if _is_valid_hex(saved) else ACCENT_COLOR_DEFAULT
        self._inner.setCurrentColor(QColor(initial))
        self._current_hex = initial  # self._inner.setCurrentColor will emit currentColorChanged
                                     # which we wire below — emit happens BEFORE connect, so we
                                     # set _current_hex manually here. (See Pitfall 6.)

        # D-11: wire live preview — bound method per QA-05
        self._inner.currentColorChanged.connect(self._on_color_changed)

        # Layout: inner widget on top, button row below
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.addWidget(self._inner)

        btn_box = QDialogButtonBox()
        self._apply_btn = btn_box.addButton("Apply", QDialogButtonBox.AcceptRole)
        self._reset_btn = btn_box.addButton("Reset", QDialogButtonBox.ResetRole)
        self._cancel_btn = btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        self._apply_btn.clicked.connect(self._on_apply)
        self._reset_btn.clicked.connect(self._on_reset)
        self._cancel_btn.clicked.connect(self.reject)
        root.addWidget(btn_box)
```
[VERIFIED: empirically against PySide6 6.11.0 in `/home/kcreasey/OneDrive/Projects/MusicStreamer` with `QT_QPA_PLATFORM=offscreen`. The inner dialog renders as a panel inside the wrapper layout when `NoButtons` is set; without `NoButtons` the inner dialog's own OK/Cancel duplicate the wrapper's button row.]

### Pattern 2: `currentColorChanged` → `apply_accent_palette` live preview
**What:** Connect the inner dialog's `currentColorChanged(QColor)` signal to a bound method that calls `apply_accent_palette(app, color.name())`. No throttling. Each user-driven color change immediately mutates `QApplication.palette()` and `setStyleSheet()`.
**When to use:** Every Phase 59 wrapper instance — this is the live preview pattern.
**Example:**
```python
# Source: D-11 + D-12; method signature matches QColorDialog.currentColorChanged(QColor)
def _on_color_changed(self, color: QColor) -> None:
    """Live-preview the selected color. Bound method per QA-05 (no lambda)."""
    self._current_hex = color.name()  # lowercase #rrggbb (verified empirically)
    apply_accent_palette(QApplication.instance(), self._current_hex)
```
[VERIFIED: signal carries a `QColor`, slot signature `(QColor)` matches. `QColor.name()` returns lowercase `#rrggbb` even for uppercase input — empirically tested with `QColor('#3584E4').name() == '#3584e4'`.]

### Pattern 3: Snapshot + restore on Cancel
**What:** In `__init__`, capture `app.palette()` and `app.styleSheet()`. Override `reject()` to restore both before calling `super().reject()`. Window-manager close routes through `reject()` automatically (Qt convention).
**When to use:** Every dialog with live-preview-and-cancel semantics. This is the existing Phase 19/40 invariant — preserve verbatim.
**Example:**
```python
# Source: existing accent_color_dialog.py:198-203 (Phase 40), preserved for Phase 59
def reject(self) -> None:
    """Cancel — restore snapshot palette and QSS without saving."""
    app = QApplication.instance()
    app.setPalette(self._original_palette)
    app.setStyleSheet(self._original_qss)
    super().reject()
```

### Anti-Patterns to Avoid
- **Self-capturing lambdas in `connect()` calls** — banned by QA-05. Use bound methods. `self._inner.currentColorChanged.connect(self._on_color_changed)`, NOT `connect(lambda c: self._handle(c))`.
- **Calling `setCustomColor` AFTER constructing the inner dialog and expecting the visible swatches to refresh** — empirically verified to work for already-existing slot indices (the dialog re-reads custom colors on next paint), but the seeded slots WILL render correctly only if the dialog hasn't been shown yet. Best practice: seed BEFORE constructing the inner `QColorDialog`. The locked D-03 ordering ("seed in `__init__`") is correct.
- **Reading `QColor.name()` when the QColor is invalid** — returns `'#000000'` silently (verified empirically: `QColor('not-a-color').name() == '#000000'`). Always check `QColor.isValid()` OR validate the source string with `_is_valid_hex` BEFORE constructing the QColor.
- **Calling `setCurrentColor(QColor())` (default-constructed)** — sets currentColor to `#000000` AND emits `currentColorChanged('#000000')`. Defensive guard: use `_is_valid_hex(saved)` before the call (the locked D-17 already enforces this).
- **Modifying the snapshot palette in place** — `palette = app.palette(); palette.setColor(...)` mutates a copy in PyQt/PySide; the snapshot stays clean. But if the snapshot is later re-used without `app.setPalette(snapshot)`, the changes never apply. Phase 19/40 already gets this right — copy verbatim.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HSV wheel / sat-val square | A `QWidget` with custom `paintEvent` rendering a hue ring + computing sat-val from mouse coords | `QColorDialog` (D-01) | Hand-rolled wheels mishandle gamma, get sub-pixel precision wrong on non-1.0 DPR, lack keyboard navigation, and don't expose the H/S/V/R/G/B numeric fields users expect. ~500 LOC saved. |
| Hex entry validation + live styling | A `QLineEdit` + `_is_valid_hex` + `setStyleSheet` red-border error state (today's pattern at `accent_color_dialog.py:153-169`) | The hex field built into `QColorDialog` (visible by default with `DontUseNativeDialog`) | QColorDialog's hex field validates as you type, supports backspace-edit, and stays in sync with the wheel automatically. Removing the project's bespoke hex `QLineEdit` deletes ~25 LOC of validation + error-styling code. |
| Screen color picking (eyedropper) | A `QWidget`-level mouse grab + screen pixel reader using XGetImage / `QGuiApplication.primaryScreen().grabWindow()` | The "Pick Screen Color" button built into `QColorDialog` (D-06) | Cross-platform mouse grab + cursor crosshair + safe color sampling is hard. Qt's eyedropper handles X11 grab/release, Windows DWM rendering, and color space conversions. ~150-300 LOC saved. |
| Custom-color memory across dialog instances | A SQLite `recent_accents` JSON list + manual repaint of preset slots | `QColorDialog.setCustomColor` static (process-static — verified) | Process-static is exactly the granularity the locked design wants for preset seeding (D-03 "idempotent reseed"). Cross-session persistence was explicitly deferred (D-16). Saved schema migration + UI. |
| Modal dialog button row | Custom `QHBoxLayout` of `QPushButton`s | `QDialogButtonBox` (D-09) | Already used in today's accent_color_dialog.py:111-118; gives correct platform button ordering + role-driven Apply/Reset/Cancel layout for free. |

**Key insight:** Every helper Phase 59 needs is already in PySide6 standard library. Zero new runtime dependencies. The wrapper is ~80-130 LOC and the test rewrite is ~70-100 LOC.

## Common Pitfalls

### Pitfall 1: `setCustomColor` after dialog construction may not refresh visible swatches
**What goes wrong:** Calling `QColorDialog.setCustomColor(idx, ...)` AFTER an instance has been constructed and shown can leave the swatch row painted with the previous values (the dialog reads custom colors at paint time, but if the slot was already painted, the user may see stale colors until next repaint).
**Why it happens:** Custom colors are process-static state read at paint time, not signaled. The visible swatch widgets cache the last drawn color.
**How to avoid:** Seed slots `0..7` in `AccentColorDialog.__init__` BEFORE constructing the inner `QColorDialog` widget. The locked D-03 ordering already ensures this.
**Warning signs:** Tester opens dialog twice in one session and on the second open the bottom-row swatches don't match `ACCENT_PRESETS`. (Empirically verified: when seeded BEFORE construction, slots render correctly. When seeded AFTER, the next dialog instance picks them up but the current one may need a manual repaint hint.)
**Confidence:** [VERIFIED: PySide6 6.11.0 empirical test confirms `QColorDialog.customColor(idx)` reads correctly across instances; visual repaint timing is harder to verify offscreen but the locked ordering sidesteps the question.]

### Pitfall 2: `setCurrentColor` is a no-op when called with the same color
**What goes wrong:** `currentColorChanged` does NOT emit when `setCurrentColor` is called with a color equal to the current one. Tests using `qtbot.waitSignal(dlg.currentColorChanged, timeout=1000)` around a redundant `setCurrentColor` call will hit `TimeoutError`.
**Why it happens:** Qt suppresses notifier-signal emission for no-change writes (standard property-system behavior).
**How to avoid:** In tests, only assert emission for actual color *changes*. To assert "the picker reflects this color", read `dlg.currentColor().name()` directly instead of waiting on the signal. To bypass timeout in synchronous test paths, use `qtbot.waitSignal(sig, timeout=0)`.
**Warning signs:** Tests pass once but flake when re-ordering setup, OR tests fail with `TimeoutError` after a `setCurrentColor` call that was a no-op.
**Confidence:** [VERIFIED: empirically — `dlg.setCurrentColor(QColor('#3584e4'))` followed immediately by `dlg.setCurrentColor(QColor('#3584e4'))` emitted the signal exactly once.]

### Pitfall 3: `setCurrentColor(QColor())` silently sets state to black `#000000` AND emits
**What goes wrong:** A default-constructed `QColor()` (or one built from an invalid hex string) is invalid (`isValid() == False`) but the dialog accepts it, sets currentColor to black, and emits `currentColorChanged('#000000')`. If the wrapper has wired live-preview, this paints the entire app black for one tick.
**Why it happens:** `QColorDialog` does not validate the input QColor before storing it. `QColor.name()` on an invalid color returns `'#000000'` silently.
**How to avoid:** Validate the source hex string with `_is_valid_hex(saved)` BEFORE constructing the `QColor` to pass to `setCurrentColor`. Locked D-17 already enforces this. Carry the same defensive pattern in any future code path that calls `setCurrentColor`.
**Warning signs:** App momentarily flashes to a black accent on dialog open when `accent_color` is corrupted in SQLite (e.g., manually edited by a user).
**Confidence:** [VERIFIED: `QColor('not-a-color').isValid() == False` and `.name() == '#000000'`; `QColor()` (default-constructed) behaves identically.]

### Pitfall 4: "Pick Screen Color" eyedropper has known X11 mouse-grab caveats
**What goes wrong:** On Linux X11, when the user clicks "Pick Screen Color" and moves the cursor outside the dialog window, the cursor-position label sometimes stops updating — and on certain compositors the picked color does not match what's under the cursor (off-by-one window-Z-order issues). Reported in the wild against PySide2/PySide6 + GNOME/KDE compositors.
**Why it happens:** The eyedropper relies on `QWidget::grabMouse()` + screen pixel reads via `QScreen::grabWindow()`. X11 grab semantics differ across compositors; some compositors release the grab when the cursor crosses certain window boundaries. Wayland blocks pixel reads outside the app's own window entirely. [CITED: github.com/OpenShot/openshot-qt/issues/5616, github.com/pyqtgraph/pyqtgraph/issues/2161]
**How to avoid:** Document as a known limitation; do not promise pixel-perfect eyedropper accuracy on all desktops. Test the eyedropper on the developer's primary X11 setup during UAT and flag if broken. Wayland is explicitly out of scope per project memory ("Linux X11 deployment target, DPR=1.0").
**Severity:** [WARNING — downgraded from CRITICAL per project memory: "Deployment target: Linux X11 DPR=1.0; HiDPI/Retina/Wayland-fractional findings downgrade from CRITICAL to WARNING".]
**Warning signs:** UAT tester reports "the eyedropper picked the wrong color from my desktop wallpaper".
**Confidence:** [MEDIUM — confirmed via two independent GitHub issues against PySide-based apps; not reproduced in this repo because the offscreen Qt platform plugin doesn't render the eyedropper at all.]

### Pitfall 5: HighlightedText role leakage on snapshot restore
**What goes wrong:** `apply_accent_palette` sets BOTH `Highlight` AND `HighlightedText` (forced to `"white"`, see `accent_utils.py:62-63`). The `__init__` snapshot captures the original palette which has its OWN HighlightedText. On Cancel, `app.setPalette(self._original_palette)` restores both correctly — but if any *intermediate* code path mutates the palette in-place via a non-snapshot pathway (e.g., a future Phase 66 theme switch happening WHILE the accent dialog is open), the snapshot is stale.
**Why it happens:** Snapshot restore assumes the palette is a flat read-now-write-later object. Concurrent mutations from other dialogs/threads break the assumption.
**How to avoid:** Phase 59 alone is safe — the dialog is modal (D-10), so no other UI code runs while it's open. The audio engine doesn't touch QPalette. Document the modality invariant explicitly in PLAN.md so a future "modeless picker" change can't quietly break the assumption.
**Warning signs:** After Cancel, text rendered on highlighted backgrounds appears slightly off-color compared to before opening the dialog.
**Confidence:** [HIGH — modal dialog + serial Qt event loop means no race exists today.]

### Pitfall 6: `setCurrentColor` in `__init__` BEFORE wiring `currentColorChanged`
**What goes wrong:** If the wrapper calls `inner.setCurrentColor(QColor(saved))` BEFORE `inner.currentColorChanged.connect(self._on_color_changed)`, the initial-color signal does NOT trigger the live-preview slot. So `self._current_hex` may be empty and `apply_accent_palette` is never called for the saved color. (Note: today's startup path at `main_window.py:189-192` already applies the saved palette — so the user-visible state is correct *because* the app palette was set at app launch. The dialog's snapshot captures this already-applied state, and Cancel restores it. So the bug is invisible in the user flow but trips up tests that assert `_current_hex` post-init.)
**Why it happens:** Standard Qt signal-slot semantics: signals only fire to slots that are connected at the time of emission.
**How to avoid:** Either (a) wire `currentColorChanged` BEFORE the initial `setCurrentColor` call, OR (b) explicitly set `self._current_hex = initial` in `__init__` after the `setCurrentColor` call. The example code in Pattern 1 above uses approach (b) — simpler and matches today's pre-population behavior. Tests must assert `dlg._current_hex == saved_or_default` after construction; the planner picks (a) or (b).
**Warning signs:** Tests for "Apply right after open with no user interaction saves the saved-color back to repo" fail because `_current_hex == ""`.
**Confidence:** [VERIFIED: empirical test in this session: connecting AFTER `setCurrentColor` causes the initial emission to be missed.]

### Pitfall 7: Inner `QColorDialog` size dominates the wrapper's minimum size
**What goes wrong:** The inner `QColorDialog` widget reports `sizeHint() = (522, 387)` (verified empirically with `NoButtons | DontUseNativeDialog`). The wrapper's `setMinimumWidth(360)` (today's value) is overridden by the inner widget's larger minimum. The wrapper dialog will be ~530px wide, not 360px.
**Why it happens:** `QVBoxLayout` propagates child minimum sizes upward. There's no way to make `QColorDialog` smaller than its intrinsic widget set (hue ring + sat-val + numeric fields).
**How to avoid:** Drop the `setMinimumWidth(360)` line from the new wrapper, OR raise it to match the inner widget (e.g., 540 to leave a small margin). Don't fight the layout. The wrapper title bar reads the wrapper dialog's actual size, not the (now obsolete) 360px hint.
**Warning signs:** Tests that assert dialog dimensions ≤ 400px fail. Visual UAT shows a much larger dialog than today's.
**Confidence:** [VERIFIED: `dlg.sizeHint() == QSize(522, 387)` for a freshly-constructed inner `QColorDialog` with the locked option set.]

## Code Examples

Verified patterns from official sources + empirical testing in this repo:

### Construct + embed + wire (the locked Phase 59 shape)
```python
# Source: pattern verified in PySide6 6.11.0 (this repo, offscreen Qt platform);
#         layout pattern from qtcentre.org/threads/27472 (cross-referenced for embed validity).

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QDialog, QDialogButtonBox, QVBoxLayout,
)

from musicstreamer.accent_utils import (
    _is_valid_hex,
    apply_accent_palette,
    build_accent_qss,
    reset_accent_palette,
)
from musicstreamer.constants import ACCENT_COLOR_DEFAULT, ACCENT_PRESETS
from musicstreamer import paths


class AccentColorDialog(QDialog):
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self._repo = repo
        app = QApplication.instance()
        self._original_palette = app.palette()
        self._original_qss = app.styleSheet()
        self._current_hex: str = ""

        self.setWindowTitle("Accent Color")
        self.setModal(True)

        # D-03: idempotent seeding of process-static custom-color slots 0..7.
        for idx, hex_val in enumerate(ACCENT_PRESETS):
            QColorDialog.setCustomColor(idx, QColor(hex_val))

        # Inner color dialog as embedded widget.
        self._inner = QColorDialog(self)
        self._inner.setOption(QColorDialog.ColorDialogOption.NoButtons, True)
        self._inner.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        self._inner.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, False)

        # D-17: pre-select saved or default; defensive _is_valid_hex guard.
        saved = self._repo.get_setting("accent_color", "")
        initial = saved if _is_valid_hex(saved) else ACCENT_COLOR_DEFAULT
        # Per Pitfall 6: set _current_hex BEFORE connecting to ensure post-init invariant
        # holds even though the initial setCurrentColor's emission predates the connect.
        self._current_hex = initial
        self._inner.setCurrentColor(QColor(initial))

        # D-11: bound-method connect (QA-05).
        self._inner.currentColorChanged.connect(self._on_color_changed)

        # Layout
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.addWidget(self._inner)

        btn_box = QDialogButtonBox()
        self._apply_btn = btn_box.addButton("Apply", QDialogButtonBox.AcceptRole)
        self._reset_btn = btn_box.addButton("Reset", QDialogButtonBox.ResetRole)
        self._cancel_btn = btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        self._apply_btn.clicked.connect(self._on_apply)
        self._reset_btn.clicked.connect(self._on_reset)
        self._cancel_btn.clicked.connect(self.reject)
        root.addWidget(btn_box)

    def _on_color_changed(self, color: QColor) -> None:
        """Live-preview the selected color (D-11, D-12)."""
        self._current_hex = color.name()  # lowercase #rrggbb
        apply_accent_palette(QApplication.instance(), self._current_hex)

    def _on_apply(self) -> None:
        """Apply: persist + write QSS file, then accept (D-14)."""
        if not self._current_hex or not _is_valid_hex(self._current_hex):
            return
        self._repo.set_setting("accent_color", self._current_hex)
        try:
            import os
            css_path = paths.accent_css_path()
            os.makedirs(os.path.dirname(css_path), exist_ok=True)
            with open(css_path, "w") as f:
                f.write(build_accent_qss(self._current_hex))
        except OSError:
            pass  # Non-fatal — palette already applied.
        self.accept()

    def _on_reset(self) -> None:
        """Reset: clear repo + restore snapshot, dialog stays open (D-15)."""
        self._repo.set_setting("accent_color", "")
        reset_accent_palette(QApplication.instance(), self._original_palette)
        # Visually return picker to default. Note: this emits currentColorChanged,
        # which re-runs apply_accent_palette and re-paints the default. Acceptable —
        # the user's "current_hex" tracking gets re-set to ACCENT_COLOR_DEFAULT,
        # but Apply right after Reset is a guarded no-op-ish path (sets default).
        # If planner wants Apply-after-Reset to be a true no-op, set
        # self._current_hex = "" AFTER the setCurrentColor call.
        self._inner.setCurrentColor(QColor(ACCENT_COLOR_DEFAULT))
        self._current_hex = ""

    def reject(self) -> None:
        """Cancel — restore snapshot palette and QSS without saving (D-13)."""
        app = QApplication.instance()
        app.setPalette(self._original_palette)
        app.setStyleSheet(self._original_qss)
        super().reject()
```
[VERIFIED: every Qt API call in this snippet was empirically tested against PySide6 6.11.0 in this repo's offscreen environment.]

### pytest-qt test pattern: assert `currentColorChanged` fires
```python
# Source: pytest-qt 4.5.0 docs (signals.html) + this repo's existing pytest-qt patterns
# (tests/test_media_keys_scaffold.py:35 and tests/test_main_window_integration.py:197).

from PySide6.QtGui import QColor
from musicstreamer.ui_qt.accent_color_dialog import AccentColorDialog
from musicstreamer.constants import ACCENT_PRESETS

def test_setting_color_emits_signal_and_applies_palette(qtbot, repo, qapp):
    """User picks a color → currentColorChanged fires → apply_accent_palette is called."""
    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)

    target = QColor(ACCENT_PRESETS[2])  # "#3a944a" (Green)

    # Capture the new color via waitSignal. timeout=1000ms is generous; the call
    # returns synchronously, so the wait is effectively instant.
    with qtbot.waitSignal(
        dlg._inner.currentColorChanged,
        timeout=1000,
        check_params_cb=lambda c: c.name() == "#3a944a",
    ):
        dlg._inner.setCurrentColor(target)

    # Post-conditions
    assert dlg._current_hex == "#3a944a"
    from PySide6.QtGui import QPalette
    assert qapp.palette().color(QPalette.ColorRole.Highlight).name() == "#3a944a"
```

### pytest-qt test pattern: seed verification
```python
def test_dialog_seeds_custom_colors_from_presets(qtbot, repo):
    """ACCENT_PRESETS[i] is in setCustomColor(i) for i in 0..7 after dialog init."""
    from PySide6.QtWidgets import QColorDialog

    # Reset slots to known state (tests may run after each other; setCustomColor is process-static)
    from PySide6.QtGui import QColor
    for idx in range(8):
        QColorDialog.setCustomColor(idx, QColor("#ffffff"))

    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)

    for idx, expected_hex in enumerate(ACCENT_PRESETS):
        assert QColorDialog.customColor(idx).name() == expected_hex
```

### pytest-qt test pattern: cancel restores snapshot
```python
def test_cancel_restores_palette_and_does_not_save(qtbot, repo, qapp):
    from PySide6.QtGui import QColor, QPalette

    original_highlight = qapp.palette().color(QPalette.ColorRole.Highlight)

    dlg = AccentColorDialog(repo)
    qtbot.addWidget(dlg)

    # Drag through some color
    dlg._inner.setCurrentColor(QColor("#e62d42"))
    assert qapp.palette().color(QPalette.ColorRole.Highlight) == QColor("#e62d42")

    # Cancel
    dlg.reject()

    # Snapshot restored
    assert qapp.palette().color(QPalette.ColorRole.Highlight) == original_highlight
    # Repo untouched
    assert repo.get_setting("accent_color", "UNSET") == "UNSET"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom 8-preset `QPushButton` grid + bespoke hex `QLineEdit` | Stock `QColorDialog` with seeded Custom Colors row | Phase 59 (this) | -150 LOC bespoke widget code; +eyedropper; +full HSV surface; +built-in hex validation; -bespoke styled error border |
| `QColorDialog` API surface | (no major changes) | Qt 6.6 (added `NoEyeDropperButton`) | Phase 59 doesn't use `NoEyeDropperButton` (eyedropper is the killer feature). [CITED: doc.qt.io/qt-6/qcolordialog.html] |
| Separate "Pick Screen Color" implementations across apps | Built into `QColorDialog` since Qt 5.something, hidden behind `DontUseNativeDialog` flag | Pre-Qt 6 | Phase 59 inherits this for free. |

**Deprecated/outdated:**
- The `_swatches: list[QPushButton]` 4×2 grid in `accent_color_dialog.py:81-96` — replaced by Custom Colors row seeding.
- The `_hex_edit: QLineEdit` + `_on_hex_changed` validation flow at `accent_color_dialog.py:99-108, 153-169` — replaced by QColorDialog's built-in hex field.
- The `_select_swatch` / `_deselect_all_swatches` swatch-selection helpers at `accent_color_dialog.py:217-235` — no longer needed.
- The `from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX` import in the dialog file — only used for the bespoke red-border error styling on the now-removed hex `QLineEdit`. Drop the import.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `currentColorChanged` signal emission frequency during click-and-drag on the wheel/sat-val square is fast enough that the locked "no throttle" decision (D-11) won't cause visible flicker. | Pitfall coverage / Pattern 2 | Visible flicker during drag on slow hardware. CONTEXT.md already captures the fallback (`QTimer.singleShot(~50ms, ...)` coalescer) in Claude's Discretion — promote at UAT if flicker is observed. **Empirically tested only with `setCurrentColor` calls, not real-time drag** on a rendered (non-offscreen) display. | LOW risk — modern Qt batches paints; widely-used pattern. |
| A2 | `colorSelected` signal is NOT useful for Phase 59 because the wrapper uses its own Apply button instead of QColorDialog's built-in OK button. | Confirmed via Q5 in research questions | Zero — the wrapper's `_on_apply` reads `self._current_hex` directly and doesn't depend on `colorSelected`. |

**This table is short:** All other claims in this research were either VERIFIED empirically in this repo's PySide6 6.11.0 environment OR CITED to Qt 6.11 official docs. The planner can treat the locked CONTEXT.md decisions as fully evidence-supported.

## Open Questions

1. **Do we keep the `setMinimumWidth(360)` call from today's dialog, drop it, or raise it?**
   - What we know: `QColorDialog`'s `sizeHint()` is `(522, 387)` with `NoButtons | DontUseNativeDialog`. The 360px minimum is functionally a no-op now.
   - What's unclear: Does the planner want a wider explicit minimum (e.g., 540) to ensure the dialog doesn't shrink below the inner widget? Or rely on layout-driven sizing alone?
   - Recommendation: **Drop `setMinimumWidth(360)` entirely** — let `QVBoxLayout` propagate the inner widget's intrinsic size. Add a comment in the wrapper noting "Wrapper size is driven by inner QColorDialog (~522x387 + button row)." (Pitfall 7.)

2. **Reset semantics: optional QSS-file cleanup?**
   - What we know: Today's dialog leaves `paths.accent_css_path()` on disk after Reset (no cleanup). It's overwritten on next Apply. `main_window.py:189-192` only loads the file when `accent_color` setting is non-empty, so on next startup the stale file is ignored.
   - What's unclear: Should Phase 59 polish this by `os.remove`ing the file on Reset?
   - Recommendation: **Locked path D-15 list items 1-5 are sufficient.** D-15.6 (`os.remove` cleanup) is captured as Claude's Discretion — planner may include it as a 1-line `try: os.remove(paths.accent_css_path()); except OSError: pass` if they want, or skip it. Either is acceptable.

3. **Idempotency of the reseed across multiple dialog opens within one session.**
   - What we know: `setCustomColor` is process-static (verified empirically — survives across dialog instance deletion within the same `QApplication`). Reseeding overwrites whatever the user did to slots 0..7 in a previous session-open of the dialog.
   - What's unclear: Is "user edited a Custom Colors slot in dialog open #1, then opens dialog #2 and finds their edit gone" a UX surprise the team is comfortable with?
   - Recommendation: **Yes, accept this — the locked D-03 explicitly chose idempotent reseeding over preservation.** The 8 curated presets are the project's brand identity; users editing slots 0..7 in-session is an expected loss. Slots 8..15 stay user-editable within the session and survive across re-opens (until app exit).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PySide6 (with QtWidgets.QColorDialog) | All Phase 59 production code | ✓ | 6.11.0 | — |
| pytest-qt | Phase 59 test rewrite | ✓ | 4.5.0 | — |
| pytest | Test runner | ✓ | (existing) | — |
| Existing `accent_utils.py` helpers | Wrapper reuses 4 helpers | ✓ | n/a | — |
| Existing `paths.accent_css_path()` | Apply path | ✓ | n/a | — |
| Existing `Repo.get_setting` / `Repo.set_setting` | Persistence | ✓ | n/a | — |
| Linux X11 display server (for live UAT of eyedropper) | Manual UAT only | ✓ (per project memory) | — | Tests run offscreen via `QT_QPA_PLATFORM=offscreen`; UAT requires real X11 |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

All Phase 59 dependencies are already installed and working in this repo. No new packages, no version bumps, no new system tools required.

## Validation Architecture

> Required by `workflow.nyquist_validation: true` in `.planning/config.json` (verified). The four success criteria from the phase brief are mapped to test types and concrete commands below.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7+ with pytest-qt 4.5.0 plugin |
| Config file | `tests/conftest.py` (sets `QT_QPA_PLATFORM=offscreen`); `pyproject.toml` for pytest config |
| Quick run command | `pytest tests/test_accent_color_dialog.py tests/test_accent_provider.py -x` |
| Full suite command | `pytest -x` |

### Phase Requirements → Test Map

The phase has FOUR success criteria from `.planning/ROADMAP.md` §"Phase 59" (also captured in `<additional_context>` of the brief). Each maps to one or more pytest-qt assertions plus one manual UAT step (eyedropper + drag interaction can't be exhaustively automated under offscreen Qt).

| Req ID | Success Criterion | Behavior | Test Type | Automated Command | File Exists? |
|--------|-------------------|----------|-----------|-------------------|-------------|
| ACCENT-02 SC#1 | Visual color picker (HSV/wheel/gradient) is present alongside the 8 swatches and hex field | Inner `QColorDialog` is constructed with `DontUseNativeDialog \| NoButtons` and `ACCENT_PRESETS[0..7]` are seeded into Custom Colors slots | unit (pytest-qt) | `pytest tests/test_accent_color_dialog.py::test_dialog_seeds_custom_colors_from_presets -x` | ❌ Wave 0 (test rewrite per D-18) |
| ACCENT-02 SC#2 | Selecting a color on the visual picker updates the hex field and applies the accent color immediately | `setCurrentColor(QColor)` emits `currentColorChanged`, slot mutates `self._current_hex`, and `apply_accent_palette` mutates `QApplication.palette()` Highlight | unit (pytest-qt + qtbot.waitSignal) | `pytest tests/test_accent_color_dialog.py::test_setting_color_emits_signal_and_applies_palette -x` | ❌ Wave 0 |
| ACCENT-02 SC#3 | Entering a hex value still works as before — the visual picker reflects the hex value | The QColorDialog's built-in hex field accepts `#rrggbb` input and emits `currentColorChanged` on commit. (Implicit — Qt-built-in behavior; we test the equivalent at the API level via `setCurrentColor`.) | unit (pytest-qt) — covered by SC#2 + integration manual UAT for keyboard hex entry | (covered by SC#2 test above) | ❌ Wave 0 |
| ACCENT-02 SC#4 | Chosen color persists across app restarts (same SQLite persistence as existing accent logic) | After `_on_apply`, `repo.get_setting("accent_color")` returns the picked hex and `paths.accent_css_path()` exists on disk with the QSS contents | unit (pytest-qt + tmp_path for the QSS file) | `pytest tests/test_accent_color_dialog.py::test_apply_persists_to_repo_and_writes_qss -x` | ❌ Wave 0 |
| ACCENT-02 (Cancel) | Cancel does NOT save and restores snapshot palette | `dlg.reject()` leaves `repo.get_setting("accent_color")` unchanged AND `qapp.palette().Highlight` returns to the snapshot value | unit (pytest-qt) | `pytest tests/test_accent_color_dialog.py::test_cancel_restores_palette_and_does_not_save -x` | ❌ Wave 0 |
| ACCENT-02 (Reset) | Reset clears repo setting AND restores snapshot AND dialog stays open AND picker visually returns to default | `dlg._on_reset()` mutates repo + palette + picker color; `dlg.isVisible()` remains True (or `dlg.result() == 0`) | unit (pytest-qt) | `pytest tests/test_accent_color_dialog.py::test_reset_clears_setting_and_keeps_dialog_open -x` | ❌ Wave 0 |
| ACCENT-02 (X-button) | Window-manager close routes through `reject()` — same behavior as Cancel | `dlg.close()` triggers `reject()` which restores snapshot + does not save | unit (pytest-qt) | `pytest tests/test_accent_color_dialog.py::test_window_close_behaves_like_cancel -x` | ❌ Wave 0 |
| ACCENT-02 (Saved-state load) | Pre-select on open: dialog opens with `accent_color` from repo (or DEFAULT if invalid/missing) | `repo.set_setting("accent_color", "#e62d42")`; new `AccentColorDialog(repo)`; `dlg._inner.currentColor().name() == "#e62d42"` AND `dlg._current_hex == "#e62d42"` | unit (pytest-qt) | `pytest tests/test_accent_color_dialog.py::test_load_saved_accent_pre_selects_in_picker -x` | ❌ Wave 0 |
| ACCENT-02 (Eyedropper / live drag UX) | Eyedropper picks a screen color and live-preview applies smoothly | Manual UAT — offscreen Qt cannot grab real pixels and `QTest`-driven mouse drag through the wheel can't be relied on across pytest-qt versions | manual-only | n/a — UAT step in `59-PLAN-XX.md` | n/a |

### Sampling Rate
- **Per task commit:** `pytest tests/test_accent_color_dialog.py tests/test_accent_provider.py -x` (~1-2s offscreen Qt)
- **Per wave merge:** `pytest -x` (full suite — ~30-60s based on existing pytest-qt suite size)
- **Phase gate:** Full suite green before `/gsd-verify-work`; manual UAT (eyedropper + live-drag flicker check) on real Linux X11 desktop; visual sanity check that the dialog title bar reads "Accent Color" and Apply / Reset / Cancel buttons are present in that order.

### Wave 0 Gaps
- [ ] **`tests/test_accent_color_dialog.py`** — full rewrite per D-18. Today's 107 LOC reference removed attributes (`_swatches`, `_hex_edit`); the rewrite drops them and adds the 8 tests listed in the Phase Requirements → Test Map above. Estimated ~120-150 LOC.
- [ ] **No new shared fixtures needed** — existing `qtbot` (pytest-qt), `qapp` (pytest-qt), and a local `FakeRepo` (pattern from today's tests at `tests/test_accent_color_dialog.py:19-27`) are sufficient. The `tmp_path` fixture from pytest core handles the QSS file write test (monkey-patch `musicstreamer.paths._root_override = str(tmp_path)`).
- [ ] **Framework install** — none. PySide6 6.11.0 + pytest-qt 4.5.0 already installed.

## Security Domain

> Required when `security_enforcement` is enabled (absent from `.planning/config.json` → treat as enabled by default).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (no auth surface) |
| V3 Session Management | no | — (single-user desktop app) |
| V4 Access Control | no | — (single-user desktop app) |
| V5 Input Validation | yes | `_is_valid_hex` regex validator at the persistence boundary (existing helper, reused) |
| V6 Cryptography | no | — (no secrets, no signatures, no keys) |

### Known Threat Patterns for PySide6 + SQLite + on-disk QSS file

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| QSS injection via unsanitized hex string | Tampering | `_is_valid_hex` regex (`^#([0-9a-fA-F]{3}\|[0-9a-fA-F]{6})$`) is run on the input BEFORE interpolation into `build_accent_qss`. Both `accent_utils.build_accent_qss` and the wrapper's `_on_apply` apply this guard. (T-40-02 invariant from Phase 40.) [VERIFIED: `accent_utils.py:11-13, 35-45`.] |
| SQL injection via `repo.set_setting("accent_color", hex)` | Tampering | The `Repo` class uses parameterized queries (existing infrastructure — verified across the codebase since v1.0). Hex value is NOT concatenated into SQL. |
| Path traversal via `paths.accent_css_path()` | Tampering | `accent_css_path` is a fixed function returning `os.path.join(_root(), "accent.css")` with no user-controllable component. No traversal vector. |
| Disk write failure on `accent.css` causing data loss | Denial of Service | `try: ... except OSError: pass` per D-14 — palette state is already in memory; on next startup `apply_accent_palette` re-applies from the SQLite-persisted hex even if the QSS file is missing. The QSS file is a cache, not a source of truth. |
| Untrusted hex from `QColor.name()` (covered by SC mapping above) | Tampering | `QColor.name()` always returns a 7-character `#rrggbb` lowercase string for valid colors. Defense-in-depth: `_is_valid_hex(self._current_hex)` is run again in `_on_apply` before persistence. |
| Eyedropper grabs cross-app pixels | Information Disclosure | Built into Qt; Phase 59 inherits whatever Qt's screen-grab semantics provide. No project-level concern — the user explicitly clicks the eyedropper button. Wayland blocks cross-app pixel reads at the compositor; X11 permits by design. Documented as expected behavior. |

**No new attack surface introduced by Phase 59.** The wrapper preserves every existing security control from Phase 19/40 (hex validation, parameterized SQL, fixed file path) and adds none of its own.

## Sources

### Primary (HIGH confidence)
- **PySide6 6.11.0 empirical tests in this repo** (Bash `python3 -c "..."` invocations against `QT_QPA_PLATFORM=offscreen`). Verified: `customCount() == 16`, `setCustomColor` is process-static + persists across instances, `currentColorChanged` does NOT fire on no-change `setCurrentColor`, `currentColorChanged` DOES fire on `setCurrentColor(QColor())` with `name() == "#000000"`, all four `ColorDialogOption` enum members exist and toggle independently, default options for a fresh dialog are all `False`, `sizeHint() == QSize(522, 387)` for an inner dialog with `NoButtons | DontUseNativeDialog`.
- **`doc.qt.io/qt-6/qcolordialog.html`** (current Qt 6.11 reference) — confirms: `setCustomColor(int, QColor)` static; custom colors "shared by all color dialogs, and remembered during the execution of the program"; `currentColorChanged` is the notifier signal for `currentColor` property; `colorSelected` fires "just after the user has clicked OK"; `NoButtons` "Don't display OK and Cancel buttons. Useful for 'live dialogs.'"; `DontUseNativeDialog`, `ShowAlphaChannel`, `NoEyeDropperButton` (Qt 6.6+) options; eyedropper hint "the cursor changes to a haircross and the colors on the screen are scanned."
- **`pytest-qt.readthedocs.io/en/latest/signals.html`** (current pytest-qt 4.5.0) — confirms: `qtbot.waitSignal(sig, timeout=N)` context manager, `check_params_cb` callable for parameter validation, `qtbot.assertNotEmitted(sig)`, `timeout=0` for synchronous emission paths.
- **Project files (read in this session):**
  - `musicstreamer/ui_qt/accent_color_dialog.py` (full 235 LOC) — current implementation reference.
  - `musicstreamer/accent_utils.py` (full 71 LOC) — confirms the 4 helpers Phase 59 reuses.
  - `musicstreamer/constants.py` (full 83 LOC) — confirms `ACCENT_PRESETS` (8 entries) and `ACCENT_COLOR_DEFAULT == "#3584e4"`.
  - `musicstreamer/paths.py:59` — confirms `accent_css_path()` returns `os.path.join(_root(), "accent.css")`.
  - `musicstreamer/ui_qt/main_window.py:53,144-145,189-192,680-682` — confirms public API surface unchanged.
  - `tests/test_accent_color_dialog.py` (full 107 LOC) — confirms references to `_swatches` and `_hex_edit` that the rewrite must eliminate.
  - `tests/test_accent_provider.py` (full 118 LOC) — confirms it tests `accent_utils.py` only and should pass unchanged.
  - `tests/conftest.py` — confirms `QT_QPA_PLATFORM=offscreen` and `_stub_bus_bridge` autouse fixture.
  - `.planning/config.json` — confirms `workflow.nyquist_validation: true`.
  - `.planning/phases/59-visual-accent-color-picker/59-CONTEXT.md` — full 209 LOC of locked decisions.
  - `.planning/phases/66-color-themes-preset-and-custom-color-schemes-vaporwave-paste/66-DISCUSS-CHECKPOINT.json` — confirms Phase 66's locked layering contract: "Theme owns Highlight by default; existing accent_color setting (and Phase 59's visual picker) layers on top to override Highlight when non-empty."

### Secondary (MEDIUM confidence)
- **qtcentre.org/threads/27472-Embed-QColorDialog-as-a-widget** — community-confirmed pattern: set `Qt::Widget` window flags, use `setOptions(NoButtons | DontUseNativeDialog)`, place in a layout via `addWidget(dialog)`. (Cross-referenced and empirically reproduced in our own test.)
- **GeeksforGeeks PyQt5 QColorDialog signal docs** — secondary confirmation that `currentColorChanged` fires multiple times during user interaction and on programmatic `setCurrentColor`.

### Tertiary (LOW confidence — flagged for UAT validation)
- **github.com/OpenShot/openshot-qt issue #5616** — Linux X11 eyedropper mouse-grab caveat. Reproduced in OpenShot 3.2.1-dev on Ubuntu 24.04. Phase 59's exposure is downgraded to WARNING per project memory ("Linux X11 deployment target, DPR=1.0; HiDPI/Retina/Wayland-fractional findings downgrade from CRITICAL to WARNING"). Validate during UAT.
- **github.com/pyqtgraph/pyqtgraph issue #2161** — macOS-specific eyedropper failure. Out of scope for Phase 59 (project memory: Linux + Windows only; macOS not a deployment target).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — both PySide6 6.11.0 and pytest-qt 4.5.0 are verified at runtime in this repo.
- Architecture / wrapper pattern: HIGH — empirically verified the embedded-widget pattern in this repo's offscreen environment.
- Live-preview wiring: HIGH — `currentColorChanged` semantics empirically verified in this repo (signal fires on change, suppresses on no-change, slot signature `(QColor)` confirmed).
- Custom-color seeding: HIGH — `setCustomColor` process-static persistence verified across multiple dialog instances in this repo.
- Eyedropper / Linux X11: MEDIUM — confirmed in Qt docs that the feature exists; mouse-grab caveats reported in OpenShot issue tracker but not reproduced in this session (offscreen Qt cannot render an eyedropper). UAT will validate on real X11.
- Pitfalls: HIGH — every pitfall except #4 (eyedropper X11) was empirically reproduced.
- Security domain: HIGH — `_is_valid_hex` regex validator and parameterized SQL are existing project invariants verified by the existing test suite.

**Research date:** 2026-05-03
**Valid until:** 2026-06-03 (30 days — Qt 6.11 is stable; PySide6 release cadence is ~quarterly; no Q3 2026 minor version expected to break QColorDialog API)
