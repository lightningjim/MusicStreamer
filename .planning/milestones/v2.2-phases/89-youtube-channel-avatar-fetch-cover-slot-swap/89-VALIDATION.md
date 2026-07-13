---
phase: 89
slug: youtube-channel-avatar-fetch-cover-slot-swap
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-16
---

# Phase 89 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_cover_art_avatar.py tests/test_constants_drift.py -x` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -x` |
| **Estimated runtime** | quick ~10s · full >600s (scope per-wave to touched modules) |

> **Run tests with `.venv/bin/python`** — system `python3` lacks `PySide6.QtWidgets` and yields false failures. Two known pre-existing failures in the full suite are unrelated to Phase 89.

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/test_cover_art_avatar.py tests/test_constants_drift.py -x`
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/test_cover_art.py tests/test_cover_art_avatar.py tests/test_yt_import_library.py tests/test_edit_station_dialog.py tests/test_now_playing_panel.py tests/test_constants_drift.py tests/test_repo.py tests/test_paths.py -x`
- **Before `/gsd:verify-work`:** Full suite must be green (modulo the 2 known pre-existing failures)
- **Max feedback latency:** ~10 seconds (quick), ~60 seconds (per-wave scoped)

---

## Per-Task Verification Map

| Req ID | Requirement | Test Type | Automated Command | File Exists |
|--------|-------------|-----------|-------------------|-------------|
| ART-AVATAR-03 | `fetch_channel_avatar` filters `thumbnails[].id == 'avatar_uncropped'`; rejects `width != height` entries | unit | `.venv/bin/python -m pytest tests/test_yt_import_library.py -k avatar -x` | ❌ W0 (add to existing file) |
| ART-AVATAR-05 | Auto-fetch on debounced URL paste + "Refresh avatar" button present and gated | unit (Qt) | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -k avatar -x` | ❌ W0 (add to existing file) |
| ART-AVATAR-06 | ICY-disabled YT station shows circular-cropped avatar in cover slot | unit (Qt) | `.venv/bin/python -m pytest tests/test_now_playing_panel.py -k avatar -x` | ❌ W0 (add to existing file) |
| ART-AVATAR-07 | Precedence `ICY → iTunes → MB-CAA → channel-avatar → placeholder`; avatar fires only when ICY empty/disabled | source-grep | `.venv/bin/python -m pytest tests/test_cover_art_avatar.py::test_mb_caa_runs_before_channel_avatar -x` | ❌ W0 (new file) |
| ART-AVATAR-08 | Cached avatar load <1s via QPixmap; clean fallback to station thumbnail on miss/fail | unit (timing) | `.venv/bin/python -m pytest tests/test_now_playing_panel.py -k avatar -x` (asserts `elapsed < 1.0` on cached-PNG load) | ❌ W0 |
| ART-AVATAR-09 | Source-grep drift-guard: `_mb_caa_lookup` appears before `_channel_avatar_lookup` in `cover_art.py` | source-grep | `.venv/bin/python -m pytest tests/test_cover_art_avatar.py::test_mb_caa_runs_before_channel_avatar -x` | ❌ W0 (new file) |
| ART-AVATAR-10 | Phase 71 sibling-render parity: `setTextFormat(Qt.RichText)` count unchanged (`EXPECTED_RICHTEXT_COUNT = 3`) | source-grep | `.venv/bin/python -m pytest tests/test_constants_drift.py::test_richtext_baseline_unchanged_by_phase_89 -x` | ❌ W0 (append to existing file) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky — populated during execution.*

> **Validation philosophy (project convention):** precedence/ordering invariants (ART-AVATAR-07/09/10) are enforced by SOURCE-GREP drift-guards, not behavioral mocks — see `feedback_gstreamer_mock_blind_spot`. The named `_mb_caa_lookup` / `_channel_avatar_lookup` functions MUST live in the same `cover_art.py` source file for the grep gate to be meaningful (D-14).

---

## Wave 0 Requirements

- [ ] `tests/test_cover_art_avatar.py` — NEW file; `test_mb_caa_runs_before_channel_avatar` source-grep guard (ART-AVATAR-07, ART-AVATAR-09)
- [ ] `tests/test_yt_import_library.py` — add avatar field-filter tests (ART-AVATAR-03): `avatar_uncropped` selected, `width != height` rejected, video-URL → channel-URL two-step
- [ ] `tests/test_edit_station_dialog.py` — add debounced-fetch + Refresh-button tests (ART-AVATAR-05)
- [ ] `tests/test_now_playing_panel.py` — add circular-avatar cover-slot + fallback + <1s tests (ART-AVATAR-06, ART-AVATAR-08)
- [ ] `tests/test_constants_drift.py` — append `test_richtext_baseline_unchanged_by_phase_89` re-asserting `EXPECTED_RICHTEXT_COUNT = 3` (ART-AVATAR-10)
- [ ] `tests/conftest.py` / `_root_override` — reuse existing 89a test-isolation convention for avatar path construction

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual circular-crop quality (antialiased edge, diameter/inset balance) | ART-AVATAR-06 (D-06/D-07) | Subjective visual balance against adjacent square covers; QPainter antialiasing not pixel-asserted | Bind a real ICY-disabled YT station (e.g., Lofi Girl) with a stored avatar; confirm clean circular crop, no border, no jaggies, balanced size vs. neighboring covers |
| End-to-end auto-fetch UX on real paste | ART-AVATAR-05 | Real yt-dlp network extraction + 500ms debounce timing | Paste a real YT channel URL in EditStationDialog; confirm "Fetching avatar…" → preview within reasonable time; click Refresh to re-fetch |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (every task in 89-01..89-05 carries a `.venv/bin/python -m pytest` command)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (10/10 tasks have automated verify)
- [x] Wave 0 covers all MISSING references (5 test files folded into the plans via task-level TDD: test written RED before production GREEN)
- [x] No watch-mode flags
- [x] Feedback latency < 60s (per-wave scoped)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-16

> Note: ART-AVATAR-08's <1s budget is an automated timing assertion (`elapsed < 1.0`) in `tests/test_now_playing_panel.py`; the only manual item is subjective circular-crop visual balance (D-07).
