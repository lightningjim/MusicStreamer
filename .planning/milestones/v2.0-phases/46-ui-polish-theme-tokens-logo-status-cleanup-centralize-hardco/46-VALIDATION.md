---
phase: 46
slug: ui-polish-theme-tokens-logo-status-cleanup
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-17
---

# Phase 46 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9+ with pytest-qt 4+ (already installed per `pyproject.toml:21-22`) |
| **Config file** | `pyproject.toml` §`[tool.pytest.ini_options]` (testpaths = `["tests"]`) |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_theme.py tests/test_edit_station_dialog.py -x` |
| **Full suite command** | `.venv/bin/python -m pytest -x` |
| **Estimated runtime** | Quick ~5s · Per-wave ~30s · Full suite ~60s |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/test_theme.py tests/test_edit_station_dialog.py -x` (~5s)
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/test_theme.py tests/test_edit_station_dialog.py tests/test_art_paths.py tests/test_station_list_panel.py tests/test_settings_import_dialog.py tests/test_import_dialog.py -x` (~30s)
- **Before `/gsd-verify-work`:** Full suite must be green — `.venv/bin/python -m pytest -x`
- **Max feedback latency:** 5s per task, 30s per wave

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 46-01-01 | 01 | 1 | Phase boundary item 1 + 2 (CONTEXT) | — | N/A (mechanical token extraction) | unit + grep-regression | `.venv/bin/python -m pytest tests/test_theme.py -v` | ❌ W0 (Task 1 creates) | ⬜ pending |
| 46-01-02 | 01 | 1 | Phase boundary item 1 + 2 (CONTEXT) | — | N/A | integration (migration regression) | `.venv/bin/python -m pytest tests/test_theme.py tests/test_art_paths.py tests/test_station_list_panel.py tests/test_settings_import_dialog.py tests/test_import_dialog.py tests/test_edit_station_dialog.py -v` | ✅ (existing) | ⬜ pending |
| 46-02-01 | 02 | 1 | Phase boundary items 3, 4, 5 (CONTEXT) | — | N/A (UX polish; no new trust boundary) | behavioral (pytest-qt) | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py::test_aa_no_key_message_string tests/test_edit_station_dialog.py::test_logo_status_clears_after_3s tests/test_edit_station_dialog.py::test_text_changed_cancels_pending_clear tests/test_edit_station_dialog.py::test_aa_url_no_key_worker_emits_aa_no_key_classification -v` | ❌ W0 (Task 1 appends) | ⬜ pending |
| 46-02-02 | 02 | 1 | Phase boundary items 3, 4, 5 (CONTEXT) | — | N/A | behavioral (pytest-qt) | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -v` | ✅ (existing + appended) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Per-test mapping (from RESEARCH §Phase Requirements → Test Map)

| ID | Behavior | Plan/Task | Test Name |
|----|----------|-----------|-----------|
| P46-T1 | `_theme.py` exports `ERROR_COLOR_HEX` as `str` starting with `#` | 46-01 / Task 1 | `test_error_color_hex_is_string` |
| P46-T2 | `_theme.py` exports `ERROR_COLOR_QCOLOR` as `QColor` | 46-01 / Task 1 | `test_error_color_qcolor_is_qcolor` |
| P46-T3 | `_theme.py` exports `STATION_ICON_SIZE` as `int == 32` | 46-01 / Task 1 | `test_station_icon_size_is_32` |
| P46-T4 | Zero `#c0392b` in `musicstreamer/ui_qt/` except `_theme.py` | 46-01 / Task 2 | `test_no_raw_error_hex_outside_theme` |
| P46-T5 | Zero `QSize(32, 32)` in migrated UI files | 46-01 / Task 2 | `test_no_raw_icon_size_in_migrated_sites` |
| P46-T6 + T9 | AA-no-key classification shows exact AA message | 46-02 / Task 1+2 | `test_aa_no_key_message_string` |
| P46-T7 | `_logo_status` clears 3s after terminal status | 46-02 / Task 1+2 | `test_logo_status_clears_after_3s` |
| P46-T8 | `url_edit.textChanged` cancels pending clear + clears label immediately | 46-02 / Task 1+2 | `test_text_changed_cancels_pending_clear` |
| Sanity | `_LogoFetchWorker` emits `"aa_no_key"` for AA-no-key URL | 46-02 / Task 1+2 | `test_aa_url_no_key_worker_emits_aa_no_key_classification` |
| P46-T10 | Existing `_on_logo_fetched` single-arg call path still works | 46-02 / Task 2 (regression guard) | `test_auto_fetch_completion_copies_via_assets` (pre-existing) |

---

## Wave 0 Requirements

- [ ] `tests/test_theme.py` — NEW file covering `_theme.py` constant exports (3 unit tests) + grep-based regression guards (2 assertions). Created in Plan 46-01 Task 1. Framework: pytest, no qtbot needed.
- [ ] `tests/test_edit_station_dialog.py` — EXTEND existing file with 4 new behavioral tests (T6/T9, T7, T8, sanity). Created in Plan 46-02 Task 1. Uses existing `qtbot` and `dialog` fixtures.
- [ ] No framework install needed — pytest-qt already installed.
- [ ] No shared conftest changes.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Wait cursor appears during fetch | CONTEXT §D-10 | Qt overrideCursor is stateful app-wide global; asserting it via `QApplication.overrideCursor()` couples tests to Qt internals for dubious benefit (per CONTEXT §Claude's Discretion — "no test for cursor override") | 1. Launch app, open EditStationDialog. 2. Paste a URL that triggers a slow fetch (YouTube live URL works best). 3. Observe cursor changes to wait-pointer for the ~1-2s fetch duration. 4. Cursor returns to default after fetch completes. |
| Empty-state glyph on station row | CONTEXT §D-12 | Visual check — `audio-x-generic-symbolic` icon resource | 1. Launch app. 2. Confirm stations without logos show the generic music-note glyph (unchanged from existing behavior). No regression is sufficient — this is a "preserve existing behavior" item, not a new behavior. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: 4 tasks total, each has automated verify — no 3-consecutive-without gap
- [x] Wave 0 covers all MISSING references (`tests/test_theme.py` NEW; `tests/test_edit_station_dialog.py` extension)
- [x] No watch-mode flags
- [x] Feedback latency < 5s per task, < 30s per wave
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-17 (planner)
