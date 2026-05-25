---
phase: 59
slug: visual-accent-color-picker
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-03
---

# Phase 59 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source: `59-RESEARCH.md` §"Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7+ with pytest-qt 4.5.0 plugin |
| **Config file** | `tests/conftest.py` (sets `QT_QPA_PLATFORM=offscreen`); `pyproject.toml` for pytest config |
| **Quick run command** | `pytest tests/test_accent_color_dialog.py tests/test_accent_provider.py -x` |
| **Full suite command** | `pytest -x` |
| **Estimated runtime** | ~1-2 seconds quick / ~30-60 seconds full |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_accent_color_dialog.py tests/test_accent_provider.py -x`
- **After every plan wave:** Run `pytest -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Filled by gsd-planner during plan creation. Each plan task with `<automated>` block must reference one of the rows below by Test ID.

| Test ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| T-59-A | TBD | TBD | ACCENT-02 SC#1 | — | Inner `QColorDialog` constructed with `DontUseNativeDialog \| NoButtons` and `ACCENT_PRESETS[0..7]` seeded into Custom Colors slots | unit | `pytest tests/test_accent_color_dialog.py::test_dialog_seeds_custom_colors_from_presets -x` | ❌ W0 | ⬜ pending |
| T-59-B | TBD | TBD | ACCENT-02 SC#2 | — | `setCurrentColor(QColor)` emits `currentColorChanged`; slot mutates `self._current_hex`; `apply_accent_palette` mutates `QApplication.palette()` Highlight | unit | `pytest tests/test_accent_color_dialog.py::test_setting_color_emits_signal_and_applies_palette -x` | ❌ W0 | ⬜ pending |
| T-59-C | TBD | TBD | ACCENT-02 SC#3 | — | QColorDialog's built-in hex field accepts `#rrggbb`; covered at API level via setCurrentColor (subsumed by T-59-B) | unit | (covered by T-59-B) | ❌ W0 | ⬜ pending |
| T-59-D | TBD | TBD | ACCENT-02 SC#4 | T-40-02 | After `_on_apply`, `repo.get_setting("accent_color")` returns picked hex AND `paths.accent_css_path()` exists with QSS contents | unit | `pytest tests/test_accent_color_dialog.py::test_apply_persists_to_repo_and_writes_qss -x` | ❌ W0 | ⬜ pending |
| T-59-E | TBD | TBD | ACCENT-02 (Cancel) | — | `dlg.reject()` leaves `repo.get_setting("accent_color")` unchanged AND `qapp.palette().Highlight` returns to snapshot | unit | `pytest tests/test_accent_color_dialog.py::test_cancel_restores_palette_and_does_not_save -x` | ❌ W0 | ⬜ pending |
| T-59-F | TBD | TBD | ACCENT-02 (Reset) | — | `dlg._on_reset()` clears repo setting + restores snapshot palette + dialog stays open + picker returns to default | unit | `pytest tests/test_accent_color_dialog.py::test_reset_clears_setting_and_keeps_dialog_open -x` | ❌ W0 | ⬜ pending |
| T-59-G | TBD | TBD | ACCENT-02 (X-button) | — | `dlg.close()` triggers `reject()` → snapshot restore + does not save | unit | `pytest tests/test_accent_color_dialog.py::test_window_close_behaves_like_cancel -x` | ❌ W0 | ⬜ pending |
| T-59-H | TBD | TBD | ACCENT-02 (Pre-select on open) | — | `repo.set_setting("accent_color", hex)` then opening dialog → `dlg._inner.currentColor().name() == hex` AND `dlg._current_hex == hex` | unit | `pytest tests/test_accent_color_dialog.py::test_load_saved_accent_pre_selects_in_picker -x` | ❌ W0 | ⬜ pending |
| T-59-UAT | TBD | final wave | ACCENT-02 (Eyedropper / drag UX) | — | Eyedropper picks a screen color and live-preview applies smoothly; drag through wheel produces flicker-free preview | manual-only UAT | n/a — UAT step | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_accent_color_dialog.py` — full rewrite per CONTEXT.md D-18. Today's 107 LOC reference removed attributes (`_swatches`, `_hex_edit`); rewrite drops them and adds the 8 tests above (~120-150 LOC estimated).
- [ ] No new shared fixtures needed — existing `qtbot` (pytest-qt), `qapp` (pytest-qt), local `FakeRepo` (pattern at today's `tests/test_accent_color_dialog.py:19-27`) are sufficient.
- [ ] No framework install — PySide6 6.11.0 + pytest-qt 4.5.0 already installed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Eyedropper / "Pick Screen Color" picks an actual screen pixel | ACCENT-02 (eyedropper UX) | Offscreen Qt cannot grab real pixels; Pitfall 4 in RESEARCH.md notes X11 mouse-grab caveats | (1) Launch app on Linux X11 desktop, (2) Open hamburger → Accent Color, (3) Click "Pick Screen Color" button, (4) Cursor becomes hairline crosshair, (5) Click any screen pixel, (6) Verify the picked color appears in the picker AND is applied live to the app's accent (e.g., Stop button, slider sub-page) |
| Live drag through wheel / sat-val produces flicker-free preview | ACCENT-02 SC#2 (live preview) | `QTest`-driven mouse drag through internal QColorDialog widgets is unreliable across pytest-qt versions | (1) Open Accent Color dialog, (2) Click+drag through hue ring at ~normal mouse speed, (3) Observe app's accent color updates smoothly without visible flicker or stutter, (4) Drag through saturation/value square similarly, (5) Release mouse — final color persists in preview |
| Apply persists across app restart | ACCENT-02 SC#4 | Confirms end-to-end startup-time accent restore at `main_window.py:189-192` | (1) Open Accent Color, (2) Pick a non-default color (e.g., bright orange), (3) Apply, (4) Verify accent applied, (5) Quit app fully, (6) Relaunch, (7) Verify the picked color is still applied on first paint |
| Apply / Reset / Cancel button order in the wrapper button row | CONTEXT.md D-09 | Visual sanity check; not worth a Qt geometry assertion | (1) Open Accent Color, (2) Verify button row reads left-to-right: `Apply` then `Reset` then `Cancel` (matches today's order at `accent_color_dialog.py:111-117`) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`tests/test_accent_color_dialog.py` rewrite)
- [ ] No watch-mode flags (pytest-qt is one-shot under offscreen Qt)
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
