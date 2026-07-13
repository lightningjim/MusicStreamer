# Phase 91: FIX-MPRIS — Discussion Log

> **Audit trail only.** Decisions are captured in `91-CONTEXT.md`.

**Date:** 2026-05-26
**Phase:** 91-fix-mpris-phase-77-deferred-mpris2-tests
**Mode:** discuss (standard)

## Pre-discussion scout findings (driving the gray areas)

1. Phase 77-VERIFICATION.md "Deferred Items" row 1 documents that the 7 MPRIS2 cluster-2 failures were closed by commit `378440c`.
2. Local run of `tests/test_media_keys_mpris2.py` on this host (commit `d2efdae`): **12 passed, 1 skipped, 0 failed**. The skip is `test_playerctl_lists_service` (playerctl not installed).
3. SC1 grep `grep -rn "class FakePlayer(QObject)" tests/ | wc -l` returns **2** today — one real declaration at `tests/_fake_player.py:37`, one docstring quote at `tests/test_fake_player_no_inline.py:28`. The SC1 line is provably miswritten.
4. The "1462-test baseline" referenced in SC2 is the Phase 77 close-out count; current suite is 1827 collected.
5. Five currently-failing tests on `pytest tests/` (none MPRIS-related): `test_bump_version` ×2, `test_constants_drift::test_soma_nn_requirements_registered`, `test_main_window_integration::test_hamburger_menu_actions` (pre-existing D-03 hamburger), `test_media_keys_smtc::test_end_to_end_factory_fallback_on_win32_without_winrt`.

## Q1 — Phase 91 premise

**Options presented:**
1. Close as already-done, bookkeeping only.
2. Hunt for currently-failing tests (broader scope).
3. Try to reproduce 7 MPRIS failures in fresh env first.
4. Other.

**User selected:** Close as already-done, bookkeeping only.

**Note:** No need to reproduce — Phase 77-VERIFICATION.md "Truth 5" already proved the cross-file ordering case, and local runs confirm. Phase 91 is a closure phase.

## Q2 — SC1 grep gotcha

**Options presented:**
1. Tighten the grep in the success criterion.
2. Move the docstring guard mention.
3. Accept 2 and update SC1 to expect 2.
4. Other.

**User selected:** Tighten the grep in the success criterion.

**Locked form:** `grep -rnP '^\s*class\s+FakePlayer\s*\(\s*QObject\s*\)\s*:' tests/ | wc -l` — anchored, returns 1 today against the current tree. Planner may equivalently scope to `tests/_fake_player.py` directly.

## Q3 — Test-baseline number

**Options presented:**
1. Refresh to current count at phase-close.
2. Drop the number, keep the intent.
3. Leave as historical 1462 anchor.
4. Other.

**User selected:** Refresh to current count at phase-close.

**Locked rule:** Phase 91 plan records pre-phase count; verification asserts `passed >= baseline`.

## Q4 — Verification rigor (Phase 86 dependency)

**Options presented:**
1. Single host run + grep checks.
2. Multi-order run (cross-file ordering proof).
3. Full suite + multi-order run.
4. Other.

**User selected:** Single host run + grep checks.

**Locked check set:** see CONTEXT.md D-08 (4 commands). Phase 77-VERIFICATION.md "Truth 5" is cited by reference for the multi-order case rather than re-run.

## Q5 — Other failing tests

**Options presented:**
1. Document as deferred, no action.
2. Capture as todos in `.planning/todos/pending/`.
3. Skip mentioning them entirely.
4. Other.

**User selected:** Capture as todos in `.planning/todos/pending/`.

**Action taken:** 4 new todo files created (the hamburger fail is already documented in Phase 77-VERIFICATION.md, so a todo for it points back rather than re-stating). Referenced in CONTEXT.md `<deferred>`.

## Deferred ideas (carried forward, not acted on)

- 4 new todos for unrelated test failures (see CONTEXT.md `<deferred>`).
- The Phase 77-VERIFICATION.md row about Python 3.13 venv + system-gi-for-3.14 mismatch — environmental, not actionable in Phase 91.

## Claude's discretion items

- Single-plan vs. two-plan structure (verify-and-grep vs. flip-statuses).
- Exact grep phrasing in the updated SC1 — D-04 PCRE form is the locked semantic; planner may simplify.
- Whether RETROSPECTIVE.md is the right home for the closure log entry (D-11).
