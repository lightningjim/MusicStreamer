---
phase: 37
slug: station-list-now-playing
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-11
---

# Phase 37 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `37-RESEARCH.md § Validation Architecture`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-qt 4.x + PySide6 6.11.0 |
| **Config file** | `tests/conftest.py` — `QT_QPA_PLATFORM=offscreen` (inherited from Phase 35) |
| **Quick run command** | `.venv/bin/pytest tests/test_station_tree_model.py tests/test_now_playing_panel.py tests/test_toast_overlay.py tests/test_main_window_integration.py -x` |
| **Full suite command** | `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q` |
| **Estimated runtime** | ~5s for 4 new files; ~3s for full suite |

---

## Sampling Rate

- **After every task commit:** Run the test file matching the touched code (e.g., `pytest -x tests/test_station_tree_model.py` after 37-01 T2)
- **After every plan wave:** Run the 4-file phase suite
- **Before `/gsd-verify-work`:** Full suite must be green with `pytest` exit code 0
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 37-01-01 | 01 | 1 | UI-01 | — | asset | `test -f musicstreamer/ui_qt/icons/audio-x-generic-symbolic.svg && grep -q audio-x-generic musicstreamer/ui_qt/icons.qrc` | ❌ W0 | ⬜ |
| 37-01-02 | 01 | 1 | UI-01 | Provider rows non-selectable | unit | `pytest tests/test_station_tree_model.py -x` | ❌ W0 | ⬜ |
| 37-01-03 | 01 | 1 | UI-01 | — | integration | `pytest tests/test_station_tree_model.py::test_station_list_panel_click -x` | ❌ W0 | ⬜ |
| 37-02-01 | 02 | 2 | UI-02 | — | asset | 3 media icons exist + grep icons.qrc | ❌ W0 | ⬜ |
| 37-02-02 | 02 | 2 | UI-02, UI-14 | Plain text in labels (no rich text XSS) | unit | `pytest tests/test_now_playing_panel.py -x` | ❌ W0 | ⬜ |
| 37-03-01 | 03 | 2 | UI-12 | No `WA_DeleteOnClose`; parent-owned | unit | `pytest tests/test_toast_overlay.py -x` + `! grep -q WA_DeleteOnClose musicstreamer/ui_qt/toast.py` | ❌ W0 | ⬜ |
| 37-04-01 | 04 | 3 | UI-01, UI-02, UI-12 | — | integration | `pytest tests/test_main_window_integration.py -x` | ❌ W0 | ⬜ |
| 37-04-02 | 04 | 3 | QA-05 | Widget lifetime safe over 3 construct/destroy cycles | integration | `pytest tests/test_main_window_integration.py::test_widget_lifetime_no_runtime_error -x` | ❌ W0 | ⬜ |
| 37-04-03 | 04 | 3 | QA-02 | — | suite | `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q; test $? -eq 0` | ✅ existing | ⬜ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All 4 test files are new (Wave 0 gaps), authored during the plan tasks that own them.

- [ ] `tests/test_station_tree_model.py` — owns UI-01 model + StationListPanel integration
- [ ] `tests/test_now_playing_panel.py` — owns UI-02 + UI-14 + PORT-08 icon fallback
- [ ] `tests/test_toast_overlay.py` — owns UI-12 overlay unit
- [ ] `tests/test_main_window_integration.py` — owns UI-01..UI-14 end-to-end integration + QA-05 lifetime check; hosts `FakePlayer` test double from RESEARCH.md §6
- [ ] Shared fixture (add to `tests/conftest.py` if reused by multiple files): `tmp_path`-backed Repo with seeded providers/stations, monkeypatched via `paths._root_override` (verified to exist in `musicstreamer/paths.py:25`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| App launches with Qt window showing station list + now-playing panel | ROADMAP success #1 | Visual confirmation that the Phase 36 empty MainWindow now has real content | `.venv/bin/python -m musicstreamer` — verify: station list visible on left, now-playing panel visible on right, QSplitter handle draggable |
| ICY title updates live from a real stream | ROADMAP success #2 | Requires real network + GStreamer playback | `.venv/bin/python -m musicstreamer` → click a SomaFM station → verify ICY title updates in the center column within 10 seconds |
| Cover art fetch from iTunes works | ROADMAP success #3 | Requires real iTunes API call | Play a station with a known artist in the ICY title → verify 160×160 cover art loads in the right column within 5 seconds |
| Volume slider persistence across restarts | ROADMAP success #4 | Requires app relaunch | Change volume slider → close app → relaunch → verify slider starts at the same position |
| YouTube 16:9 thumbnail letterboxes inside 160×160 slot | UI-14 | Visual confirmation that panel doesn't resize | Play a YouTube live station → verify cover slot remains 160×160 (not inflated) with 160×90 thumbnail centered vertically |
| Toast appears and fades for failover / connecting events | UI-12 | Visual confirmation of QPropertyAnimation | Click a station with a broken primary stream (AudioAddict with expired key works) → verify "Connecting…" toast appears, then "Stream failed, trying next…" toast if failover engages |

---

## Security Domain

Phase 37 introduces Qt widget UI — ICY titles, station names, and GStreamer error messages are rendered in labels. Key mitigations (see RESEARCH.md § Security Domain for full analysis):

| Pattern | STRIDE | Mitigation | Verified In |
|---------|--------|------------|-------------|
| Untrusted ICY title rendered as rich text | Tampering | Explicit `icy_label.setTextFormat(Qt.PlainText)` prevents HTML/script injection | 37-02-02 (grep for `setTextFormat(Qt.PlainText)` in now_playing_panel.py) |
| Untrusted GStreamer error text in toast | Tampering | Same: `toast.label.setTextFormat(Qt.PlainText)` + 80-char truncation | 37-03-01 (grep for `setTextFormat(Qt.PlainText)` in toast.py) |
| Untrusted filesystem path in `QPixmap(station_art_path)` | Tampering | `QPixmap` handles malformed files gracefully; `isNull()` check before display | 37-01 integration test |

No auth, session, or crypto surface in this phase.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (4 new test files)
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending (automatic — plan-checker re-verification)
</content>
</invoke>
