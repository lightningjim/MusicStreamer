---
phase: 77
slug: test-infrastructure-stabilization-fix-pre-existing-test-doub
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-17
---

# Phase 77 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Mirrors the **Validation Architecture** section of `77-RESEARCH.md`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-qt 4.5.0 + PySide6 6.11.0 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` + `tests/conftest.py` |
| **Quick run command** | `uv run pytest tests/<file>.py::<test_name> -x` |
| **Full suite command** | `uv run pytest tests/` |
| **Estimated runtime** | ~30–60 seconds full suite (399+ tests today) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/<modified_test_file>.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -x` (must reach final test without abort)
- **Before `/gsd:verify-work` / phase gate:** `uv run pytest tests/` exits 0 with zero `xfail`/`skip` masking the six clusters
- **Max feedback latency:** ~60s (full suite)

---

## Per-Task Verification Map

> The planner assigns plan/task numbers when scope-locking; the rows below are anchored to the proposed plan ordering (77-01..77-06) per `77-RESEARCH.md §Summary`'s recommended structure. Task IDs are placeholders pending planner output.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 77-01-01 | 01 | 0 | INFRA-01-a | — | Shared `tests/_fake_player.py` declares every Player Signal with matching arity | unit | `uv run pytest tests/test_fake_player_signal_parity.py -x` | ❌ Wave 0 | ⬜ pending |
| 77-01-02 | 01 | 0 | INFRA-01-b | — | No inline `class _?FakePlayer(QObject)` outside `tests/_fake_player.py` | unit | `uv run pytest tests/test_fake_player_no_inline.py -x` | ❌ Wave 0 | ⬜ pending |
| 77-02-01 | 02 | 1 | INFRA-01-c | — | 11 test sites import shared FakePlayer; covered by 77-01-02 grep gate | unit | `uv run pytest tests/test_fake_player_no_inline.py -x` | ✅ existing (covered) | ⬜ pending |
| 77-02-02 | 02 | 1 | INFRA-01-c | — | `audio_caps_detected` arity drift at gbs/soma sites auto-fixed via shared import | unit | `uv run pytest tests/test_main_window_gbs.py tests/test_main_window_soma.py -x` | ✅ existing | ⬜ pending |
| 77-03-01 | 03 | 1 | INFRA-01-d | T-77-01 (DBus name leak) | MPRIS2 7 tests pass with per-test unique `SERVICE_NAME` suffix; teardown unregisters | integration | `uv run pytest tests/test_media_keys_mpris2.py -x` | ✅ existing — fixture wired | ⬜ pending |
| 77-04-01 | 04 | 1 | INFRA-01-e | — | `_aa_quality` orphan assertions deleted; tests no longer reference removed widget | unit | `uv run pytest tests/test_import_dialog_qt.py -x` (orphans absent) | ✅ existing — assertions deleted | ⬜ pending |
| 77-04-02 | 04 | 1 | INFRA-01-f | — | Twitch test asserts `session.set_option("twitch-api-header", ...)` (production-correct migrated API per D-05 revised) | unit | `uv run pytest tests/test_twitch_auth.py -x` | ✅ existing — function rewritten | ⬜ pending |
| 77-04-03 | 04 | 1 | INFRA-01-g | — | `test_refresh_recent_updates_list` asserts `rowCount() == 5` matching production limit (BROWSE-04) | unit | `uv run pytest tests/test_station_list_panel.py::test_refresh_recent_updates_list -x` | ✅ existing | ⬜ pending |
| 77-04-04 | 04 | 1 | INFRA-01-h | — | `test_filter_strip_hidden_in_favorites_mode` uses `panel._stack.currentIndex() == 0` (per D-15 revised; not `isVisibleTo`) | unit | `uv run pytest tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode -x` | ✅ existing | ⬜ pending |
| 77-05-01 | 05 | 2 | INFRA-01-i | T-77-02 (real-network race) | `test_first_call_shows_toast` runs in mid-suite without aborting; monkeypatches `urllib.request.urlretrieve` AND `urllib.request.urlopen` | integration | `uv run pytest tests/test_main_window_integration.py tests/test_main_window_underrun.py -x` | ✅ existing — fixture added | ⬜ pending |
| 77-05-02 | 05 | 2 | INFRA-01-j | T-77-02 | `test_phase72_now_playing_panel → test_phase72_assumptions` ordering crash eliminated | integration | `uv run pytest tests/test_phase72_now_playing_panel.py tests/test_phase72_assumptions.py -x` | ✅ existing | ⬜ pending |
| 77-05-03 | 05 | 2 | INFRA-01-j | T-77-02 | `test_main_window_integration → test_now_playing_panel` ordering crash eliminated | integration | `uv run pytest tests/test_main_window_integration.py tests/test_now_playing_panel.py -x` | ✅ existing | ⬜ pending |
| 77-05-04 | 05 | 2 | INFRA-01-k | — | `test_yt_scan_passes_through` mid-suite crash eliminated (worker `wait()` / `deleteLater()` in fixture) | integration | `uv run pytest tests/ -x` reaches this test without abort | ✅ existing | ⬜ pending |
| 77-06-01 | 06 | 3 | INFRA-01-l | — | **Phase gate:** `uv run pytest tests/` exits 0 with no xfail/skip masking the six named clusters | phase gate | `uv run pytest tests/` | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/_fake_player.py` — new shared module; mirrors all 18 Signals from `musicstreamer/player.py` `Player.__dict__` with correct arity; method stubs (`set_volume`, `play`, `pause`, `stop`) for the surface tests touch
- [ ] `tests/test_fake_player_signal_parity.py` — D-16 drift-guard; `ast.parse` both `musicstreamer/player.py` and `tests/_fake_player.py`, compare `Signal(...)` name + arity tuples
- [ ] `tests/test_fake_player_no_inline.py` — D-17 grep-based drift-guard; walks `tests/test_*.py` + `tests/ui_qt/test_*.py`, fails if any file matches `class\s+_?FakePlayer\s*\(QObject\)` except `tests/_fake_player.py`
- [x] **No framework install needed** — pytest, pytest-qt, PySide6 all already pinned in `pyproject.toml` `[project.optional-dependencies] test`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| (none) | — | All Phase 77 outputs are automated. No GUI workflows touched. | — |

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify (no Wave 0 dependencies beyond the 3 listed above)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (verified — every task above has its own command)
- [ ] Wave 0 covers all MISSING references (3 new test files; planner assigns to Plan 77-01)
- [ ] No watch-mode flags (Phase 77 ships no watch loops)
- [ ] Feedback latency < 60s (full suite ~30–60s on a stock dev box)
- [ ] `nyquist_compliant: true` set in frontmatter (set at phase-close after all task commands turn ✅ green)

**Approval:** pending
