---
phase: 94
slug: optimize-sidebar-logo-loading-with-pre-scaled-thumbnails-for
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-15
---

# Phase 94 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-qt 4.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_art_paths.py tests/test_station_icon_integration.py tests/test_station_thumb_async.py -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -x -q` |
| **Estimated runtime** | quick ~tens of seconds; full suite >600s |

> **MEMORY.md:** Run tests with `.venv/bin/python -m pytest`, NOT system `python3` — system python lacks `PySide6.QtWidgets` and produces false failures. Full suite >600s; scope to phase-relevant files during development. Two known pre-existing failures unrelated to this phase.

---

## Sampling Rate

- **After every task commit:** Run the quick command (art_paths + station_icon_integration + station_thumb_async)
- **After every plan wave:** Run the full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~60 seconds (quick run)

---

## Per-Task Verification Map

| Decision | Behavior | Test Type | Automated Command | File Exists | Status |
|----------|----------|-----------|-------------------|-------------|--------|
| D-02 (lazy gen) | `load_station_icon` returns fallback when no thumb, enqueues generation | unit | `.venv/bin/python -m pytest tests/test_art_paths.py::test_thumb_missing_returns_fallback -x` | ❌ W0 | ⬜ pending |
| D-02 (disk write) | Worker writes valid PNG to `station_art.thumb.png` | unit | `.venv/bin/python -m pytest tests/test_art_paths.py::test_generate_thumb_writes_png -x` | ❌ W0 | ⬜ pending |
| D-03 (async repaint) | `dataChanged` emitted after thumb lands | integration | `.venv/bin/python -m pytest tests/test_station_thumb_async.py::test_thumb_landing_emits_datachanged -x` | ❌ W0 | ⬜ pending |
| D-04 (96px size) | Generated thumb is ≤96px on longest axis | unit | `.venv/bin/python -m pytest tests/test_art_paths.py::test_thumb_is_96px -x` | ❌ W0 | ⬜ pending |
| D-05 (path) | Thumb lives at `assets/{id}/station_art.thumb.png` | unit | `.venv/bin/python -m pytest tests/test_art_paths.py::test_thumb_path_derivation -x` | ❌ W0 | ⬜ pending |
| D-06 (mtime) | Fresh thumb skips regen; stale thumb re-enqueues | unit | `.venv/bin/python -m pytest tests/test_art_paths.py::test_thumb_freshness_check -x` | ❌ W0 | ⬜ pending |
| D-01 (now_playing unchanged) | `_load_scaled_pixmap` does NOT reference `station_art.thumb` | drift-guard | `.venv/bin/python -m pytest tests/test_station_thumb_async.py::test_now_playing_panel_does_not_use_thumb -x` | ❌ W0 | ⬜ pending |
| D-03 (dedup) | Same station not enqueued twice during fast scroll | unit | `.venv/bin/python -m pytest tests/test_station_thumb_async.py::test_in_flight_dedup -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_art_paths.py` — extend: thumb path derivation, freshness (mtime) check, 96px size, miss/stale behavior (5 new tests)
- [ ] `tests/test_station_thumb_async.py` — NEW: async generation, `dataChanged` emit, in-flight dedup, drift-guard for `now_playing_panel` (4 new tests)

*Existing `tests/test_station_icon_integration.py` passes unchanged — fallback behavior is preserved when no thumb exists.*

---

## Manual-Only Verifications

| Behavior | Decision | Why Manual | Test Instructions |
|----------|----------|------------|-------------------|
| Sidebar scroll feels smooth on a large list (DI.fm-scale), including first pass | D-03 | Perceptual smoothness / event-loop timing under real scroll cannot be asserted deterministically in unit tests | Import a large AudioAddict network (e.g. DI.fm), fast-scroll the sidebar top-to-bottom on first launch after import; confirm no multi-row stalls and that logos fill in progressively from fallback |
| Logos render sharp at HiDPI | D-04 | Visual sharpness on fractional/Retina scaling is perceptual | On a HiDPI display (Wayland fractional / Retina 2x), confirm sidebar logos are crisp, not blurry |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (9 new tests across 2 files)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s (quick run)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
