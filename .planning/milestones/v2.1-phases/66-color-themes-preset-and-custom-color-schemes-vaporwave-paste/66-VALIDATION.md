---
phase: 66
slug: color-themes-preset-and-custom-color-schemes-vaporwave-paste
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-09
---

# Phase 66 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-qt (existing — no install needed) |
| **Config file** | `pyproject.toml` (existing pytest config) |
| **Quick run command** | `pytest tests/test_theme.py tests/test_theme_picker_dialog.py tests/test_theme_editor_dialog.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~30s quick / ~3-5min full |

---

## Sampling Rate

- **After every task commit:** Run quick command (theme-only tests, ~30s)
- **After every plan wave:** Run full suite — must include `tests/test_accent_color_dialog.py` and `tests/test_accent_provider.py` to verify Phase 59 layering contract has not regressed
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Filled in by planner during plan-phase. Reference taxonomy below.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 66-01-01 | 01 | 0 | THEME-01 | — | Test stubs for theme.py palette construction | unit (RED) | `pytest tests/test_theme.py -x -q` | ❌ W0 | ⬜ pending |
| (Planner extends) | … | … | … | … | … | … | … | … | … |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_theme.py` — RED stubs for `theme.py` palette construction (per-preset hex assertions for all 6 hardcoded presets), `theme_custom` JSON round-trip, `_is_valid_hex` defense-in-depth on JSON load
- [ ] `tests/test_theme_picker_dialog.py` — RED stubs for tile-grid construction, click = live preview + apply, snapshot-restore on Cancel, "Customize…" button opens editor, empty Custom tile is disabled
- [ ] `tests/test_theme_editor_dialog.py` — RED stubs for 9-role color rows (Highlight excluded), live preview per role, Save = persist + apply + switch theme to custom, Reset = revert to source preset, snapshot-restore on Cancel
- [ ] `tests/conftest.py` — extend with `theme_repo` fixture if not present (in-memory `Repo` with `theme` and `theme_custom` settings keys ready)
- [ ] No new framework installs — pytest + pytest-qt already configured (Phase 59 set up the qt-test fixtures)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual mood matches branding | THEME-01 | Subjective — "does Vaporwave feel Vaporwave-ish?" cannot be unit-tested | Open app, select each preset (System, Vaporwave, Overrun, GBS.FM, GBS.FM After Dark, Dark, Light), confirm visual coherence at-a-glance |
| WCAG AA contrast in practice | THEME-01 | Automated contrast math is unit-tested but real-world readability requires human judgment, especially for borderline links/buttons | Open app on Vaporwave + Overrun + GBS.FM After Dark; read 5 station names, ICY track titles, hamburger menu items in each; flag any unreadable text |
| Live preview perceptual smoothness | THEME-01 | Live preview latency / flicker is hardware-dependent (Wayland DPR=1.0) | Click each tile in picker, observe whether re-tint feels instant or shows visible repaint flicker |
| Layered Highlight contract preserved end-to-end | THEME-01, ACCENT-02 | Combinatorial state across two settings keys; subjective "did my pink accent survive?" check | Set accent_color = `#ff77ff`. Then switch theme to Overrun. Verify Highlight = pink (accent override), not the Overrun magenta. Reset accent. Verify Highlight = Overrun magenta (theme baseline). |
| Custom theme persistence across restarts | THEME-01 | Tests cover SQLite round-trip but full process restart is manual UAT | Save Custom palette, quit app, relaunch, confirm Custom slot is the active theme and palette renders identically |
| Settings export/import round-trip carries Custom | THEME-01 | Full ZIP round-trip is integration UAT | Export settings ZIP, delete `theme_custom` key (sqlite3 CLI), import ZIP, confirm Custom palette restored |
| Windows System default branch unchanged | THEME-01 | Windows VM verification — cannot run pytest-qt against Windows palette behavior from Linux | On Win11 VM: launch app with `theme = system`, confirm `_apply_windows_palette` Fusion + dark-mode branch runs verbatim (visual: dark window chrome, blue Highlight) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (test_theme.py, test_theme_picker_dialog.py, test_theme_editor_dialog.py)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
