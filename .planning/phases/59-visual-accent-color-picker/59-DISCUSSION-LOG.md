# Phase 59: Visual Accent Color Picker - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 59-visual-accent-color-picker
**Areas discussed:** Picker surface choice, Integration shape in the dialog, Live preview while dragging, Custom-color memory

---

## Picker surface choice

### Q1: Picker technology

| Option | Description | Selected |
|--------|-------------|----------|
| Qt's QColorDialog (Recommended) | Stock PySide6 QColorDialog — native, full-featured: hue wheel + saturation/value square, R/G/B + H/S/V + alpha fields, eyedropper. Zero custom paint code. | ✓ |
| Custom HSV wheel widget | Hand-built QWidget with a hue ring + saturation/value square painted via QPainter. ~150-300 LOC + tests. Tighter integration but reinvents Qt's dialog. | |
| QColorDialog embedded inline | QColorDialog with NoButtons, embedded as a child widget inside the existing AccentColorDialog. Keeps presets + hex + visual picker in one dialog. | |

**User's choice:** Qt's QColorDialog (Recommended)
**Notes:** No custom paint code. Stock PySide6.

### Q2: Interaction with existing 8 ACCENT_PRESETS

| Option | Description | Selected |
|--------|-------------|----------|
| Hide standard color buttons | NoButtons + DontUseNativeDialog. Hide built-in basics; seed Custom Colors with our 8 ACCENT_PRESETS. Single source of truth. | |
| Let QColorDialog show its own basics, drop our 8 presets | Embrace QColorDialog wholesale. Existing 8 swatches removed. | ✓ |
| Keep our 8 swatches at top, QColorDialog below | Two-section layout: ACCENT_PRESETS row stays, QColorDialog below with internal swatches suppressed. | |

**User's choice:** Let QColorDialog show its own basics, drop our 8 presets
**Notes:** Drop the standalone preset row. Followed up to clarify how `ACCENT_PRESETS` constant survives.

### Q3: ACCENT_PRESETS constant fate

| Option | Description | Selected |
|--------|-------------|----------|
| Seed them into QColorDialog Custom Colors (Recommended) | setCustomColor(0..7) at dialog open with our 8 ACCENT_PRESETS hex values. ACCENT_PRESETS constant stays. | ✓ |
| Remove ACCENT_PRESETS entirely | Delete the constant; rely on QColorDialog's built-in basics + wheel + custom slots. | |
| Keep ACCENT_PRESETS only as the default fallback | Constant stays for ACCENT_COLOR_DEFAULT but no longer surfaced as swatches anywhere. | |

**User's choice:** Seed them into QColorDialog Custom Colors (Recommended)
**Notes:** One-click access preserved in QColorDialog's idiom; constant survives unchanged.

### Q4: QColorDialog options

| Option | Description | Selected |
|--------|-------------|----------|
| Alpha channel (transparency slider) | ShowAlphaChannel. Translucent accent. QPalette Highlight + slider QSS don't honor alpha well. | |
| Eyedropper / screen color picker | Pick Screen Color button on Linux/Windows when DontUseNativeDialog is set. Free with Qt. | ✓ |
| Native OS dialog | Use platform native picker. Loses ability to seed custom colors / hide options uniformly. | |

**User's choice:** Eyedropper / screen color picker (only)
**Notes:** Alpha OFF. Native OFF. Eyedropper ON. DontUseNativeDialog implied for the latter.

---

## Integration shape in the dialog

### Q1: AccentColorDialog fate

| Option | Description | Selected |
|--------|-------------|----------|
| Replace AccentColorDialog with QColorDialog directly (Recommended) | Hamburger menu launches QColorDialog directly (or via thin wrapper that seeds custom colors + wires Reset). | ✓ |
| Keep AccentColorDialog shell, embed QColorDialog as inner widget | AccentColorDialog stays as the QDialog with its own Apply / Reset / Cancel button row, body is a QColorDialog widget. | |
| Keep current AccentColorDialog, add 'More colors…' button | Conflicts with the previous answer to drop the 8-swatch row. Skipped. | |

**User's choice:** Replace AccentColorDialog with QColorDialog directly (Recommended)
**Notes:** Public class name `AccentColorDialog` preserved for callers.

### Q2: Reset button location

| Option | Description | Selected |
|--------|-------------|----------|
| Thin wrapper class around QColorDialog adds a Reset button (Recommended) | Tiny subclass / factory in accent_color_dialog.py that builds a QColorDialog, adds a Reset button, seeds custom colors, wires currentColorChanged. | ✓ |
| Drop Reset entirely — use a hamburger menu 'Reset Accent Color' item | QColorDialog stays unmodified; main menu gets a sibling 'Reset Accent Color' item. | |
| Drop Reset — user picks default blue from QColorDialog to reset | Cheapest; loses the 'I want it gone' affordance. | |

**User's choice:** Thin wrapper class around QColorDialog adds a Reset button (Recommended)
**Notes:** Reset stays in the dialog button row.

### Q3: Modality

| Option | Description | Selected |
|--------|-------------|----------|
| Modal — same as today (Recommended) | setModal(True). Blocks main window while open. Matches every other dialog in the app. | ✓ |
| Modeless — user can play/pause/skip while picking | setModal(False). Picker stays floating, user can interact with main window. | |

**User's choice:** Modal — same as today (Recommended)
**Notes:** No change from current behavior.

---

## Live preview while dragging

### Q1: Preview trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Apply on every currentColorChanged (Recommended) | Wire QColorDialog.currentColorChanged → apply_accent_palette directly. Matches today's keystroke-live behavior. | ✓ |
| Apply only on colorSelected (mouse release / OK) | Avoids any flicker risk during drag, but loses 'see it before commit' affordance. | |
| Apply on currentColorChanged but throttled (~50ms QTimer) | Coalesces rapid emissions. Adds ~30 LOC. Worth it only if real-world flicker is observed. | |

**User's choice:** Apply on every currentColorChanged (Recommended)
**Notes:** No throttling unless flicker is observed in practice. Captured as Claude's Discretion in CONTEXT.md.

### Q2: Cancel / Reset semantics with live preview

| Option | Description | Selected |
|--------|-------------|----------|
| Cancel = restore snapshot, Reset = clear setting + restore default (Recommended) | Snapshot QApplication.palette() and styleSheet() at open. Cancel restores both, repo untouched. Reset clears setting + restores default + keeps dialog open. Apply writes setting + QSS file. | ✓ |
| Cancel reverts to last applied (saved) accent, not the snapshot | Read repo on cancel rather than snapshot. Functionally identical when nothing else mutates the palette. | |
| No live preview; Apply commits, Cancel does nothing to revert | Conflicts with the previous answer. Skipped. | |

**User's choice:** Cancel = restore snapshot, Reset = clear setting + restore default (Recommended)
**Notes:** Same shape as today's dialog. Window-manager close (X) routes through reject() automatically.

---

## Custom-color memory

### Q1: Persistence of custom picks

| Option | Description | Selected |
|--------|-------------|----------|
| No persistence — just seed ACCENT_PRESETS each open (Recommended) | Slots 0..7 reset to ACCENT_PRESETS each open; slots 8..15 die with the process. Saved accent_color is the only memory. | ✓ |
| Persist last N picks in repo as 'recent_accents' | New SQLite key with JSON list of up to 8 hex strings. Adds repo plumbing. | |
| Persist QColorDialog's full custom-color row across sessions | Save all 16 slots at dialog close, restore on open. Conflates 'preset' with 'recent'. | |

**User's choice:** No persistence — just seed ACCENT_PRESETS each open (Recommended)
**Notes:** No new SQLite key. Captured as deferred idea for future polish if usage demands it.

### Q2: setCustomColor static-state handling

| Option | Description | Selected |
|--------|-------------|----------|
| Set on every dialog open (idempotent reseed) (Recommended) | Call QColorDialog.setCustomColor(0..7, ACCENT_PRESETS) every time the wrapper opens. Predictable and stateless. | ✓ |
| Set once at app startup | Seed in main_window's __init__ before any dialog opens. Adds startup-time concern that's hard to test without running the full app. | |
| Set on open AND on close (force-reset) | Pedantic; not needed since static state dies with the process. | |

**User's choice:** Set on every dialog open (idempotent reseed) (Recommended)
**Notes:** Slots 8..15 stay user-editable within a session; reset on next process start.

### Q3: Pre-selection on open

| Option | Description | Selected |
|--------|-------------|----------|
| Saved accent_color or default blue (Recommended) | setCurrentColor(QColor(saved_hex)) where saved_hex = repo.get_setting('accent_color', ACCENT_COLOR_DEFAULT). Mirrors today's _load_saved_accent. | ✓ |
| Always default blue (#3584e4) | Ignore saved accent on open. Jarring. | |
| Last-clicked color in QColorDialog (cross-instance) | Static state — not meaningful when our wrapper is the only consumer. | |

**User's choice:** Saved accent_color or default blue (Recommended)
**Notes:** Same shape as today's _load_saved_accent.

---

## Claude's Discretion

- Subclass `QColorDialog` vs. wrapper `QDialog` shape (CONTEXT.md D-07). Recommended (b) wrapper.
- Optional QSS-file cleanup on Reset (CONTEXT.md D-15.6).
- Throttle on `currentColorChanged` if real-world flicker is observed (CONTEXT.md D-11).
- Reset button label / role wording (CONTEXT.md D-15).
- Test fixture shape — likely `qtbot.addWidget(dlg)` like today (CONTEXT.md D-18).

## Deferred Ideas

- Cross-session "recent custom colors" memory.
- Alpha channel / translucent accents.
- Native OS color dialog on Windows/macOS.
- Modeless picker for live-preview-while-playing.
- QSS-file cleanup on Reset (Claude's Discretion → could promote).
- Throttle `currentColorChanged` previews (Claude's Discretion → could promote).
- Theme picker integration (Phase 66 — explicitly designed to layer on top of Phase 59).
- Discoverability hints / extra labels in the dialog.
