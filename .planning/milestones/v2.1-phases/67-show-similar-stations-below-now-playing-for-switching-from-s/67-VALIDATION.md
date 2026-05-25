---
phase: 67
slug: show-similar-stations-below-now-playing-for-switching-from-s
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-09
---

# Phase 67 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9+ + pytest-qt 4+ |
| **Config file** | `pyproject.toml` (`testpaths = ["tests"]`, marker `integration`) |
| **Quick run command** | `uv run --with pytest --with pytest-qt pytest tests/test_pick_similar_stations.py tests/test_now_playing_panel.py -x -k "similar or sibling"` |
| **Full suite command** | `uv run --with pytest --with pytest-qt pytest tests` |
| **Estimated runtime** | ~5–10 sec quick, ~30 sec full |

---

## Sampling Rate

- **After every task commit:** Run quick command (above)
- **After every plan wave:** Run `uv run --with pytest --with pytest-qt pytest tests/test_pick_similar_stations.py tests/test_now_playing_panel.py tests/test_main_window_integration.py tests/test_aa_siblings.py tests/test_filter_utils.py -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Populated by gsd-planner from RESEARCH.md §Validation Architecture (SIM-01 .. SIM-12 + QA-05). The planner maps each task to its requirement, secure behavior, automated command, and Wave 0 file existence flag during planning.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (planner-filled) | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pick_similar_stations.py` — new file; covers SIM-04, SIM-05, SIM-09 (pure-helper tests; mirror `tests/test_aa_siblings.py` shape)
- [ ] `tests/test_now_playing_panel.py` — extend with Phase 67 section after the Phase 64 section (~line 898+); covers SIM-03, SIM-06, SIM-07, SIM-08, SIM-10, SIM-11
- [ ] `tests/test_main_window_integration.py` — extend with Phase 67 section after the Phase 64 section (~line 1125+); covers SIM-01, SIM-02, SIM-08 (integration), QA-05 structural
- [ ] No framework install needed — pytest + pytest-qt already in `pyproject.toml [project.optional-dependencies] test`
- [ ] No conftest fixture extension — `FakeRepo` in `test_now_playing_panel.py` (lines 65-112) and `test_main_window_integration.py` (lines 86-178) already support `stations=` and `settings=`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual layout of "Similar Stations" section in the live app on Wayland DPR=1.0 — section header rendering, collapsed-glyph rendering (▾/▸), Refresh icon (↻) visibility, link underline color theming with the active Phase 66 theme | UAT | Qt rich-text + theme-driven palette renders identically in tests but visual chrome (font, spacing, contrast) only verifiable in the running app | (1) Launch the app; (2) enable "Show similar stations" in hamburger menu; (3) play a SomaFM station with siblings; (4) verify section appears with both sub-sections; (5) click Refresh — verify both samples change; (6) click section header — verify collapse/expand persists across restart; (7) click a similar-station link — verify playback switches |
| Smooth UX of click-to-switch (no perceptible lag for libraries of 50–200 stations per PROJECT.md) | Performance | The < 50ms automated perf test asserts the helper, but full panel re-render perceived smoothness needs human eyes | Click any similar-station link 5 times rapidly switching between stations; verify no UI freeze, no flicker, "Connecting…" toast appears each time |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (3 test files: 1 new, 2 extended)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
