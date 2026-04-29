---
phase: 54
slug: station-logo-aspect-ratio-fix
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-29
---

# Phase 54 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: 54-RESEARCH.md §4 "Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-qt 4.x [VERIFIED: pyproject.toml] |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| **Quick run command** | `pytest tests/test_art_paths.py -x` |
| **Full suite command** | `pytest -x` |
| **Estimated runtime** | ~2 seconds (focused) / ~30–60 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_art_paths.py -x`
- **After every plan wave:** Run `pytest -x`
- **Before `/gsd-verify-work`:** Full suite must be green + UAT screenshot pair captured
- **Max feedback latency:** 5 seconds (focused), 60 seconds (full suite)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 54-01-01 | 01 | 1 | BUG-05 / SC #3 | — | Portrait 1:2 logo preserves aspect (16w × 32h) — no center crop | unit | `pytest tests/test_art_paths.py::test_load_station_icon_preserves_portrait_aspect -x` | ❌ W0 (new test) | ⬜ pending |
| 54-01-02 | 01 | 1 | BUG-05 / SC #2 | — | Landscape 2:1 logo preserves aspect (32w × 16h) — no center crop | unit | `pytest tests/test_art_paths.py::test_load_station_icon_preserves_landscape_aspect -x` | ❌ W0 (new test) | ⬜ pending |
| 54-01-03 | 01 | 1 | BUG-05 / SC #1 | — | Square logo unchanged baseline | unit | `pytest tests/test_art_paths.py::test_default_size_is_32px -x` | ✅ | ⬜ pending |
| 54-01-04 | 01 | 1 | D-11 (no cache key bump) | — | QPixmapCache key stable across phase change | unit | `pytest tests/test_art_paths.py::test_cache_hit_on_second_call -x` | ✅ | ⬜ pending |
| 54-02-01 | 02 | 2 | BUG-05 / SC #4 | — | UAT screenshot — landscape letterboxes correctly in tree row | manual | UAT capture against station id=2 (Living Coffee) | n/a | ⬜ pending |
| 54-02-02 | 02 | 2 | BUG-05 / SC #3 | — | UAT screenshot — synthetic portrait pillarboxes correctly in tree row | manual | UAT install synthetic 50×100 PNG via EditStationDialog, capture screenshot | n/a | ⬜ pending |
| 54-02-03 | 02 | 2 | BUG-05 (Path A vs B-1 gate) | — | Decision: ship as test-only OR apply `_art_paths.py` patch | manual | UAT confirms whether real cropping observed; if not — Path A; if yes — Path B-1 | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_art_paths.py` exists with shared fixtures (`tmp_data_dir`, `_isolate_pixmap_cache`, `_make_station`, `_write_logo`)
- [ ] `_write_logo` helper extended with optional `width` / `height` kwargs (default `None` — preserves all 7 existing call sites)
- [ ] `pytest-qt` `qtbot` fixture available (already pinned in pyproject.toml)

*Wave 0 is effectively a no-op — only the `_write_logo` signature extension is required, which folds into the same Wave 1 commit as the two new tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tree row icon size/position does not shift between stations | BUG-05 / SC #4 | No automated row-height assertion; visual confirmation only | Launch app, scroll through provider tree, verify icon column is uniformly 32×32 across square + landscape stations. Screenshot if uncertain. |
| Live UAT — landscape letterbox renders correctly today | BUG-05 / SC #2 | Probe ran on offscreen platform; user's running build may differ | Launch app on user's Linux box, navigate to "Cafe BGM" → "Living Coffee: Smooth Jazz Radio" (station id=2). Inspect tree row. Expected: 32w × ~16h-equivalent letterboxed YouTube thumb with row's selection bg above + below. |
| Live UAT — portrait pillarbox renders correctly today | BUG-05 / SC #3 | No portrait logo exists in user's DB (0/172 stations); must synthesize | Generate `/tmp/portrait.png` via `python3 -c "from PySide6.QtGui import QPixmap; from PySide6.QtCore import Qt; from PySide6.QtWidgets import QApplication; import sys; app=QApplication(sys.argv); p=QPixmap(50,100); p.fill(Qt.red); p.save('/tmp/portrait.png','PNG')"`. Use EditStationDialog "Choose File…" on a throw-away test station; note the original `station_art_path` to restore after. Inspect the tree row — expected 16w × 32h pillarboxed red rectangle. |
| Path A vs Path B-1 decision gate | BUG-05 | Plan branches on UAT outcome | If both UAT steps render as expected (no cropping) → Path A: ship test-only, no production diff. If either shows actual cropping → Path B-1: apply `_art_paths.py` ~10-line canvas-paint patch (research §3 spec); rerun UAT. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers `_write_logo` extension
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s (full suite)
- [ ] `nyquist_compliant: true` set in frontmatter (deferred until plan tasks finalized)

**Approval:** pending
