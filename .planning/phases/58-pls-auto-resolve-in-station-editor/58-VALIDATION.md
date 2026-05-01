---
phase: 58
slug: pls-auto-resolve-in-station-editor
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-01
---

# Phase 58 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `pytest tests/test_playlist_parser.py tests/test_edit_station_dialog.py -x -q` |
| **Full suite command** | `pytest -x -q` |
| **Estimated runtime** | ~30 seconds (quick) / ~2 min (full) |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

To be filled in by the planner — every task in PLAN.md needs a row here mapping to its `<automated>` verify command. Pure parser tests (Wave 1) feed into dialog-integration tests (Wave 2).

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 58-01-XX | 01 | 1 | STR-15 | unit | `pytest tests/test_playlist_parser.py -x -q` | ❌ W0 | ⬜ pending |
| 58-02-XX | 02 | 2 | STR-15 | integration | `pytest tests/test_edit_station_dialog.py::test_pls_* -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_playlist_parser.py` — stub fixtures for PLS, M3U, M3U8, XSPF parsers (per-format minimal valid + edge cases)
- [ ] `tests/test_edit_station_dialog.py` — extend with stub tests for `_on_add_pls`, `_on_pls_fetched`, `_apply_pls_entries(mode)` paths

*Existing infrastructure covers framework + Qt fixtures (`pytest-qt`).*

---

## Validation Dimensions (from RESEARCH §10)

1. **Input shape** — parser accepts bytes vs str correctly per format (XSPF requires bytes when XML prologue declares encoding).
2. **Format dispatch** — URL extension first, Content-Type fallback, give-up third (no body sniffing).
3. **File-order preservation** — gap-06 invariant: PLS `FileN=` entries returned in numeric order; M3U entries in line order; XSPF tracks in document order.
4. **Error handling** — every failure path (HTTP error, malformed body, empty entries, parser exception) maps to "no rows added" + `QMessageBox.warning`.
5. **Threading correctness** — `_PlaylistFetchWorker` lifecycle: token monotonic stale-discard; cursor restored at top of slot unconditionally; `wait()` from `accept()` / `closeEvent()` / `reject()` to prevent QThread destroy crash.
6. **Bitrate/codec extraction** — regex matches expected formats; codec priority order does not produce wrong answers; HEAACv2 / VORBIS edge cases handled per planner's call.
7. **Replace/Append semantics** — Replace clears UI rows only (no DB delete); Append continues from `max(position) + 1`; both insert via `_add_stream_row(stream_id=None)`.
8. **Dirty-state interaction** — resolved-row insert trips Phase 51-02 dirty-state baseline so Save/Discard/Cancel continues to work.
9. **AA-import compatibility** — `aa_import._resolve_pls` wrapper preserves `list[str]` contract + `[pls_url]` fallback for both call sites at lines 135, 177.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live PLS resolution against a real station | STR-15 SC #1 | Network-dependent; not reproducible offline | UAT: open EditStationDialog → Add from PLS → paste e.g. `http://somafm.com/groovesalad.pls` → verify rows appear |
| Cursor + button state during fetch | UI-SPEC | Visual feedback timing | UAT: click Add from PLS, confirm wait cursor + disabled button until result |
| Replace/Append/Cancel default-button keyboard | UI-SPEC | Keyboard focus + Enter activation | UAT: trigger prompt with existing rows, press Enter, confirm Append fires (not Replace) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
