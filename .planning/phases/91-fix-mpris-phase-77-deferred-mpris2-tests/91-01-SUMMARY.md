---
phase: 91-fix-mpris-phase-77-deferred-mpris2-tests
plan: 01
subsystem: test-infrastructure
tags: [bookkeeping, mpris2, test-verification, requirements-closeout]
dependency_graph:
  requires: [Phase 77 close-out commit 378440c]
  provides: [FIX-MPRIS-01, FIX-MPRIS-02, FIX-MPRIS-03 Complete; clean MPRIS2 test baseline for Phase 86]
  affects: [.planning/ROADMAP.md, .planning/REQUIREMENTS.md, .planning/RETROSPECTIVE.md]
tech_stack:
  added: []
  patterns: [bookkeeping-only close-out, verification evidence capture]
key_files:
  created: [.planning/phases/91-fix-mpris-phase-77-deferred-mpris2-tests/91-01-SUMMARY.md]
  modified:
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/RETROSPECTIVE.md
decisions:
  - "SC1 grep replaced with anchored PCRE form (D-04): old bare form returned 2 due to docstring literal in test_fake_player_no_inline.py:28"
  - "SC2 baseline refreshed to 1838 passed (captured 2026-06-02); stale 1462 count scrubbed from both ROADMAP and REQUIREMENTS"
  - "FIX-MPRIS-01/02/03 flipped Pending -> Complete backed by D-08 verification evidence on this host"
  - "Cross-file ordering proof (D-09): cited Phase 77-VERIFICATION.md Truth 5 by reference; not re-run locally"
metrics:
  duration: ~10 min
  completed: 2026-06-02
---

# Phase 91 Plan 01: FIX-MPRIS Bookkeeping Close-Out Summary

**One-liner:** Bookkeeping-only close-out verifying Phase 77 commit 378440c still holds; SC1 grep corrected to anchored PCRE form, SC2 baseline refreshed to 1838 passed, FIX-MPRIS-01/02/03 flipped to Complete.

---

## Objective

Close out Phase 91 (FIX-MPRIS-01/02/03) as bookkeeping-only. The 7 D-03-deferred MPRIS2 cross-file failures were already repaired by Phase 77 close-out commit `378440c`. This plan re-verified closure on this host, corrected the provably miswritten SC1 grep, refreshed the stale SC2 baseline count, and flipped requirement statuses + ROADMAP checkboxes.

---

## Task 1: Verification Evidence (D-08, read-only)

All seven D-08 evidence captures recorded verbatim below. No test or production files were modified.

### Evidence 1 — MPRIS2 cluster-2 test suite

```
uv run pytest tests/test_media_keys_mpris2.py -v
...
tests/test_media_keys_mpris2.py::test_cover_path_for_station_returns_correct_path_and_creates_dir PASSED
tests/test_media_keys_mpris2.py::test_write_cover_png_none_pixmap_returns_none PASSED
tests/test_media_keys_mpris2.py::test_write_cover_png_valid_pixmap_creates_file PASSED
tests/test_media_keys_mpris2.py::test_write_cover_png_overwrites_same_file PASSED
tests/test_media_keys_mpris2.py::test_write_cover_png_respects_root_override PASSED
tests/test_media_keys_mpris2.py::test_linux_mpris_backend_constructs PASSED
tests/test_media_keys_mpris2.py::test_linux_mpris_backend_publish_metadata PASSED
tests/test_media_keys_mpris2.py::test_linux_mpris_backend_publish_metadata_none PASSED
tests/test_media_keys_mpris2.py::test_linux_mpris_backend_set_playback_state PASSED
tests/test_media_keys_mpris2.py::test_playerctl_lists_service SKIPPED
tests/test_media_keys_mpris2.py::test_linux_mpris_backend_slot_play_pause_emits_signal PASSED
tests/test_media_keys_mpris2.py::test_linux_mpris_backend_shutdown_idempotent PASSED
tests/test_media_keys_mpris2.py::test_xesam_title_passthrough_verbatim PASSED

=================== 12 passed, 1 skipped, 1 warning in 0.17s ===================
```

**Result: PASS** — 12 passed, 1 skipped (test_playerctl_lists_service — playerctl binary absent, legitimate environmental skip per D-01), 0 failed.

### Evidence 2 — FakePlayer drift-guards

```
uv run pytest tests/test_fake_player_signal_parity.py tests/test_fake_player_no_inline.py -v
...
tests/test_fake_player_signal_parity.py::test_fake_player_mirrors_every_player_signal PASSED
tests/test_fake_player_signal_parity.py::test_fake_player_signal_arity_matches_player PASSED
tests/test_fake_player_no_inline.py::test_no_inline_fake_player_subclass_in_tests PASSED

========================= 3 passed, 1 warning in 0.10s =========================
```

**Result: PASS** — 3 passed. Runtime offender count == 0: asserted by `test_no_inline_fake_player_subclass_in_tests` passing (the programmatic drift-guard at line 50 of test_fake_player_no_inline.py).

### Evidence 3 — SC1 grep comparison

**Anchored PCRE form (D-04 replacement):**
```
grep -rnP '^\s*class\s+FakePlayer\s*\(\s*QObject\s*\)\s*:' tests/ | wc -l
1
```
Match: `tests/_fake_player.py:37:class FakePlayer(QObject):`

**Old miswritten form (returns 2 — documents why SC1 line had to change, D-03):**
```
grep -rn "class FakePlayer(QObject)" tests/ | wc -l
2
```
The second match is `tests/test_fake_player_no_inline.py:28` — a docstring literal describing the rule. The bare grep can never return 1 while that docstring exists (D-05 prohibits editing the docstring — the runtime drift-guard supersedes it).

### Evidence 4 — Runtime offender count == 0

Proven by `tests/test_fake_player_no_inline.py::test_no_inline_fake_player_subclass_in_tests` passing in Evidence 2. No separate command needed.

### Evidence 5 — SC3 drift-guard

```
uv run pytest tests/test_constants_drift.py::test_richtext_baseline_unchanged_by_phase_71 -v
...
tests/test_constants_drift.py::test_richtext_baseline_unchanged_by_phase_71 PASSED

========================= 1 passed, 1 warning in 0.10s =========================
```

**Result: PASS** — 1 passed. No source-introspection regression.

### Evidence 6 — Cross-file ordering (D-09, cited by reference)

Per D-09, the multi-order pair is NOT re-run locally. Phase 77-VERIFICATION.md "Truth 5" already proves:
- `test_main_window_integration.py` followed by `test_media_keys_mpris2.py`: 77 passed, 1 skipped, 1 pre-existing fail.
- The 1 failure is the documented Phase 74/76 hamburger carry-over (`test_hamburger_menu_actions`) — NOT an MPRIS failure.
- Cross-file isolation via `unique_mpris_service_name` fixture is proven. Re-running here would be duplicate work.

### Evidence 7 — SC2 baseline anchor (D-06/D-07)

```
uv run pytest tests/ -q
...
5 failed, 1838 passed, 1 skipped, 2 warnings in 22.83s
```

**SC2 baseline: N = 1838 passed** (captured 2026-06-02, pre-phase).

The 5 non-MPRIS failures are catalogued in CONTEXT.md `<deferred>` and are out of scope:
- `tests/test_bump_version.py` — JSON decoder errors (release-tooling regression)
- `tests/test_constants_drift.py::test_soma_nn_requirements_registered` — Phase 83 SomaFM NN follow-up
- `tests/test_main_window_integration.py::test_hamburger_menu_actions` — Phase 74/76 carry-over
- `tests/test_media_keys_smtc.py::test_end_to_end_factory_fallback_on_win32_without_winrt` — Windows-only path, winrt absent on Linux
- (1 additional per deferred list)

### Scope fence verification

```
git status --porcelain tests/ musicstreamer/
(empty — no modifications)
```

**PASS** — zero edits under `tests/` or `musicstreamer/`.

---

## Task 2: Fix Miswritten SC1 Grep (D-03/D-04)

Replaced the SC1 line in ROADMAP.md Phase 91 detail block:

**Old (returned 2, can never return 1):**
```
`grep -rn "class FakePlayer(QObject)" tests/ | wc -l` returns exactly 1 and the only declaration site is `tests/_fake_player.py` (Pitfall 15 verified at source level before any test edits).
```

**New (D-04 anchored PCRE, returns 1):**
```
`grep -rnP '^\s*class\s+FakePlayer\s*\(\s*QObject\s*\)\s*:' tests/ | wc -l` returns exactly 1 and the only declaration site is `tests/_fake_player.py:37` (Pitfall 15 verified at source level; anchored to a real class declaration so the docstring literal in `tests/test_fake_player_no_inline.py:28` no longer false-positives — D-04).
```

`tests/test_fake_player_no_inline.py` was NOT edited (D-05 prohibits it; the docstring is the correct English documentation of the rule).

**Commit:** `83302cf`

---

## Task 3: Bookkeeping Flips (D-06/D-10/D-11)

All edits to `.planning/` documents only:

### A. REQUIREMENTS.md — Checkbox flips
- Lines 97-99: `- [ ] **FIX-MPRIS-01/02/03**` → `- [x] **FIX-MPRIS-01/02/03**`
- FIX-MPRIS-02 body: replaced `the 1462-test baseline` with `the pre-phase test baseline`

### B. REQUIREMENTS.md — Traceability table
- Lines 213-215: `FIX-MPRIS-0X | Phase 91 | Pending` → `FIX-MPRIS-0X | Phase 91 | Complete` (all 3)

### C. ROADMAP.md — "### Phases" checkbox
- Line 30: `- [ ] **Phase 91: FIX-MPRIS ...` → `- [x] **Phase 91: FIX-MPRIS ...`

### D. ROADMAP.md — Plan-item checkbox
- Line 84: `- [ ] 91-01-PLAN.md ...` → `- [x] 91-01-PLAN.md ...`

### E. ROADMAP.md — Progress Table
- `| 91. FIX-MPRIS | 0/? | Not started | - |` → `| 91. FIX-MPRIS | 1/1 | Complete | 2026-06-02 |`

### F. ROADMAP.md — SC2 baseline refresh
- Replaced `1462-test baseline` with `the Phase 91 pre-phase baseline of 1838 passed (captured 2026-06-02); verification asserts passed >= 1838, never shrinkage.`

### G. RETROSPECTIVE.md — Phase 91 close-out note
Appended:
```
## Phase 91 — FIX-MPRIS Close-Out (2026-06-02)

Phase 91 (FIX-MPRIS) closed as bookkeeping-only: verified Phase 77 close-out commit 378440c
still holds (MPRIS2 cluster-2: 12 passed, 1 skipped, 0 failed), corrected the miswritten SC1
grep to an anchored PCRE form, refreshed the SC2 baseline to 1838 passed (captured 2026-06-02),
scrubbed the stale 1462 count from REQUIREMENTS+ROADMAP, and flipped FIX-MPRIS-01/02/03 to
Complete. No test or production-code changes.
```

**Commit:** `42de013`

---

## Deviations from Plan

None — plan executed exactly as written. All three tasks completed in strict bookkeeping-only mode with zero edits to `tests/` or `musicstreamer/`.

---

## Known Stubs

None. This plan is bookkeeping-only; no data sources or UI components involved.

---

## Threat Flags

None. No new attack surface introduced. `.planning/` document edits only; zero production-code, network, auth, file-access, or schema changes (T-91-NA).

---

## Self-Check: PASSED

- [x] `.planning/ROADMAP.md` Phase 91 SC1 line contains anchored PCRE form
- [x] `.planning/ROADMAP.md` old bare grep form count = 0
- [x] `.planning/ROADMAP.md` Phase 91 "### Phases" checkbox = - [x]
- [x] `.planning/ROADMAP.md` 91-01-PLAN.md plan-item checkbox = - [x]
- [x] `.planning/ROADMAP.md` Progress Table row = `1/1 | Complete | 2026-06-02`
- [x] `.planning/ROADMAP.md` `1462-test baseline` phrase count = 0
- [x] `.planning/ROADMAP.md` SC2 line contains `1838` and `passed >= `
- [x] `.planning/REQUIREMENTS.md` FIX-MPRIS-01/02/03 checkboxes = - [x]
- [x] `.planning/REQUIREMENTS.md` traceability rows = Complete (3)
- [x] `.planning/REQUIREMENTS.md` `1462` count = 0
- [x] `.planning/RETROSPECTIVE.md` contains `378440c`
- [x] `git status --porcelain tests/ musicstreamer/` = empty
- [x] Commits 83302cf (Task 2) and 42de013 (Task 3) exist
