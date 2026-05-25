# Phase 59 — UAT Log

**Tester:** Kyle Creasey
**Date:** 2026-05-03
**Display server:** Linux X11 (DPR=1.0)
**Compositor:** GNOME (ubuntu:GNOME / DESKTOP_SESSION=ubuntu)
**XDG_CURRENT_DESKTOP:** ubuntu:GNOME
**App build:** main @ `0f46a77` (post Plan 02 + X11 render fix `0f46a77`)

---

## Pre-UAT Readiness

### Plan 02 fixed during UAT

| Check | Command | Result | Status |
|-------|---------|--------|--------|
| Initial Plan 02 ship | `git log --oneline` | `4b1d74e` — feat(59-02): rewrite AccentColorDialog as QColorDialog wrapper | PASS |
| X11 render fix | `git log --oneline` | `0f46a77` — fix(59-02): strip QColorDialog Qt.Dialog flag | PASS |
| Plan 01 RED → GREEN | `pytest tests/test_accent_color_dialog.py tests/test_accent_provider.py -x` | 27 passed | PASS |

**Issue surfaced during UAT (now fixed):** initial launch of the new dialog showed only the Apply / Reset / Cancel button row — the inner `QColorDialog` was suppressed by Qt's default `Qt.Dialog` window flag on real X11 (offscreen Qt rendered fine, which is why `pytest-qt` did not catch it). Fixed by `setWindowFlags(Qt.Widget)` on the inner widget before `addWidget`. UAT then proceeded successfully.

---

## ROADMAP §Phase 59 — Success Criteria Attestations

### SC #1 — Visual color picker present alongside swatches + hex field
- **Status:** PASS
- **Notes:** Dialog renders the full Qt `QColorDialog` surface — hue picker, saturation/value square, R/G/B + H/S/V numeric fields, hex (`HTML:`) field, Basic Colors row, Custom Colors row with the 8 ACCENT_PRESETS in slots 0..7, and the "Pick Screen Color" eyedropper button. Wrapper button row reads `Apply | Reset | Cancel` left-to-right.

### SC #2 — Live preview during drag (no flicker)
- **Status:** PASS
- **Flicker observed:** no
- **Throttle decision:** KEEP NO-THROTTLE (D-11 default; do not promote `QTimer.singleShot(50, ...)`)
- **Notes:** Dragging through the hue picker and saturation/value square updates the app's Stop button + volume slider sub-page in real time, smoothly, with no visible flicker on Linux X11 DPR=1.0 / GNOME.

### SC #3 — Hex entry still works
- **Status:** PASS
- **Notes:** Typing a hex value into the QColorDialog `HTML:` field updates the hue picker, sat/val square, R/G/B + H/S/V fields, and the live app accent.

### SC #4 — Persistence across app restart
- **Status:** PASS
- **Notes:** Color picked via Apply persists to SQLite (`accent_color` setting) and `paths.accent_css_path()` QSS file. After full quit + relaunch, the chosen accent is restored on first paint via `main_window.py:189-192` (`apply_accent_palette` invoked at startup when the saved hex is non-empty).

---

## Additional Attestations

### Eyedropper UAT (T-59-UAT row)
- **Status:** PASS
- **Notes:** "Pick Screen Color" button activates the haircross cursor; clicking on a screen pixel updates the picker + live-previews the app accent. No Pitfall 4 X11 mouse-grab caveats observed on GNOME/X11.

### Reset UAT (D-15)
- **Status:** PASS
- **Notes:** Reset clears the saved `accent_color` setting, restores the snapshot palette, returns the picker to default blue (`#3584e4`), and the dialog stays open as designed. After full quit + relaunch the app boots with the system/theme default accent (no stale QSS file applied — D-15.6 empty-string write to `accent.css` works as intended).

### Cancel/Esc/X UAT (D-13)
- **Status:** PASS
- **Notes:** Cancel button, Esc key, and the window-manager X close all route through `reject()` and restore the snapshot palette + styleSheet captured in `__init__`. No save happens; the previously-applied accent is preserved across the dialog open/cancel cycle.

### Idempotent reseed UAT (D-03)
- **Status:** PASS
- **Notes:** Overwriting Custom Colors slot 0 within a session and reopening the dialog confirms that `setCustomColor(0..7, ACCENT_PRESETS)` runs in `__init__` and overwrites any user edits to slots 0..7. Slots 8..15 retain user edits within the process (and reset on app exit, which is the locked D-03 behavior).

---

## Closure

- **All 4 ROADMAP SCs:** PASS
- **Phase 59 status:** COMPLETE
- **Follow-up Plan 04 needed:** no (no flicker, no Pitfall 4 caveats)
- **Resume signal:** approved
