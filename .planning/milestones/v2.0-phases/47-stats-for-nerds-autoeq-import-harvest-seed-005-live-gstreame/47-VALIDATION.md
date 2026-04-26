---
phase: 47
slug: stream-bitrate-quality-ordering
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-17
updated: 2026-04-18
---

# Phase 47 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-qt 4.x (per `pyproject.toml`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| **Quick run command** | `pytest tests/test_stream_ordering.py tests/test_repo.py -x` |
| **Full suite command** | `pytest -x` |
| **Estimated runtime** | ~25–40 seconds full suite; ~2–3 seconds for quick pure-logic subset |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_stream_ordering.py tests/test_repo.py -x` (quick)
- **After every plan wave:** Run the plan's combined test scope:
  - Wave 1 (47-01): `pytest tests/test_stream_ordering.py -x`
  - Wave 2 (47-02): `pytest tests/test_repo.py tests/test_player_failover.py -x`
  - Wave 2 (47-03): `pytest tests/test_aa_import.py tests/test_discovery_dialog.py tests/test_edit_station_dialog.py tests/test_settings_export.py -x`
  - **Wave 3 (gap-closure 47-04 / 47-05 / 47-06 — parallel):** `pytest tests/test_edit_station_dialog.py tests/test_player_failover.py tests/test_aa_import.py -x`
  - **Wave 4 (gap-closure 47-07 — serialized after 47-06):** `pytest tests/test_aa_import.py -x`
- **Before `/gsd-verify-work`:** Full suite must be green (`pytest -x`)
- **Max feedback latency:** ~40 seconds full suite

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 47-01-01 | 01 | 1 | D-01 | — | N/A (pure dataclass extension) | unit | `pytest tests/ -x` (backward-compat check) | ✅ existing | ⬜ pending |
| 47-01-02 | 01 | 1 | D-04..D-09, PB-03..PB-11 | T-47 V5 (input validation at order level) | Pure function rejects mutation; codec_rank is whitespace/case/None-tolerant | unit | `pytest tests/test_stream_ordering.py -x -v` | ❌ W0 new file | ⬜ pending |
| 47-02-01 | 02 | 2 | D-02, PB-01, PB-02 | T-47 V5 (SQL param binding) | `?` placeholders in widened insert_stream/update_stream; additive migration idempotent | unit | `pytest tests/test_repo.py -x -k bitrate` | ❌ W0 extend | ⬜ pending |
| 47-02-02 | 02 | 2 | G-7, PB-18 | — | N/A (pure wiring change) | integration | `pytest tests/test_player_failover.py -x` | ❌ W0 extend | ⬜ pending |
| 47-03-01 | 03 | 2 | D-10, D-11, PB-12, PB-13 | T-47 V5 (int coerce on API field) | `int(result.get("bitrate", 0) or 0)` neutralizes malformed RB payloads before SQL bind | integration | `pytest tests/test_aa_import.py tests/test_discovery_dialog.py -x -k bitrate` | ❌ W0 extend | ⬜ pending |
| 47-03-02 | 03 | 2 | D-12, D-13, D-14, PB-16, PB-17 | T-47 V5 (UI input validation) | `QIntValidator(0, 9999)` clamps at input; `int(text or "0")` coerces defensively at save | widget | `pytest tests/test_edit_station_dialog.py -x -k bitrate` | ❌ W0 extend | ⬜ pending |
| 47-03-03 | 03 | 2 | G-1, P-1, P-2, PB-14, PB-15 | T-47 V5 (import boundary) | Defensive `int(stream.get("bitrate_kbps", 0) or 0)` at both _insert_station and _replace_station; forward-compat with pre-47 ZIPs | integration | `pytest tests/test_settings_export.py -x -k "bitrate or forward_compat"` | ❌ W0 extend | ⬜ pending |
| 47-04-01 | 04 | 3 | UAT gap 1 (RED) | — | Delegate-path regression test for cleared-cell commit | widget | `pytest tests/test_edit_station_dialog.py::test_bitrate_delegate_persists_empty_string_on_commit -x` (expect NON-ZERO in RED) | ❌ gap-04 new test | ⬜ pending |
| 47-04-02 | 04 | 3 | UAT gap 1 (GREEN) | T-47 V5 (UI edit commit) | Explicit setModelData writes editor.text() to Qt.EditRole; empty cell persists as "" which int(text or "0") coerces to 0 at save | widget | `pytest tests/test_edit_station_dialog.py -x` | ✅ existing (extend) | ⬜ pending |
| 47-05-01 | 05 | 3 | UAT gap 5 (RED) | — | Two regression tests for error-cascade coalescing | integration | `pytest tests/test_player_failover.py::test_multiple_gst_errors_advance_queue_once -x` (expect NON-ZERO in RED) | ❌ gap-05 new tests | ⬜ pending |
| 47-05-02 | 05 | 3 | UAT gap 5 (GREEN) + UAT gap 4 (side-effect) | T-47 V5 (control-flow guard) | _recovery_in_flight coalesces cascading bus errors per URL; deferred QTimer.singleShot(0) clear preserves next-URL recoveries; reset in play/play_stream/stop/pause prevents stale-guard leak across user actions | integration | `pytest tests/test_player_failover.py -x` | ✅ existing (extend) | ⬜ pending |
| 47-06-01 | 06 | 3 | UAT gap 2 (RED) | — | Three regression tests for multi-URL PLS extraction and 2-server-per-tier import | unit+integration | `pytest tests/test_aa_import.py::test_resolve_pls_returns_all_entries tests/test_aa_import.py::test_fetch_channels_multi_preserves_primary_and_fallback -x` (expect NON-ZERO in RED) | ❌ gap-06 new tests | ⬜ pending |
| 47-06-02 | 06 | 3 | UAT gap 2 (GREEN) | T-47 V5 (parse boundary — regex-anchored PLS FileN= matcher) | re.match(r"^File(\d+)=(.+)$") bounds parser to well-formed PLS entries; unknown-format fallback returns [pls_url] preserving prior error semantics | integration | `pytest tests/test_aa_import.py -x` | ✅ existing (extend) | ⬜ pending |
| 47-07-01 | 07 | 4 | UAT gap 3 (codec RED) | — | Ground-truth codec mapping test against fetch_channels_multi output | integration | `pytest tests/test_aa_import.py::test_fetch_channels_multi_codec_map_ground_truth -x` (expect NON-ZERO in RED) | ❌ gap-07 new test | ⬜ pending |
| 47-07-02 | 07 | 4 | UAT gap 3 (codec GREEN) | — | Module-scope _CODEC_MAP replaces inline ternary; colocated with _POSITION_MAP / _BITRATE_MAP | unit | `pytest tests/test_aa_import.py -x` | ✅ existing (extend) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_stream_ordering.py` — NEW file, created in Plan 47-01 Task 2 (covers PB-03..PB-11)
- [x] `tests/test_repo.py` — existing file, extended in Plan 47-02 Task 1 (PB-01, PB-02)
- [x] `tests/test_player_failover.py` — existing file, extended in Plan 47-02 Task 2 (PB-18)
- [x] `tests/test_aa_import.py` — existing file, extended in Plan 47-03 Task 1 (PB-12)
- [x] `tests/test_discovery_dialog.py` — existing file, extended in Plan 47-03 Task 1 (PB-13)
- [x] `tests/test_edit_station_dialog.py` — existing file, extended in Plan 47-03 Task 2 (PB-16, PB-17, PB-17b)
- [x] `tests/test_settings_export.py` — existing file, extended in Plan 47-03 Task 3 (PB-14, PB-15)
- [x] Framework already present — pytest + pytest-qt declared in `pyproject.toml`; no install step needed

Each plan creates its own Wave 0 tests as the RED phase of its TDD cycle (all tasks have `tdd="true"`). There is no separate dedicated Wave 0 task — the test scaffolding is built into each task's RED phase per the TDD integration guidance.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Bitrate column visibility in Edit Station dialog | D-12 | Visual layout confirmation — column width, header alignment, cell editability | 1. Launch app. 2. Right-click any station -> Edit. 3. Confirm streams table has 5 columns: URL, Quality, Codec, Bitrate, Position. 4. Click Bitrate cell, type digits — confirm only numeric input accepted (QIntValidator). 5. Type letters — confirm rejected. 6. Type "320", tab away, Save. 7. Reopen dialog — confirm "320" persisted. |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every task has one)
- [x] Wave 0 covers all MISSING references (test files are created/extended by the RED phase of each task)
- [x] No watch-mode flags (`-x` fail-fast only)
- [x] Feedback latency < 40s (full suite)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-18 (planning)
