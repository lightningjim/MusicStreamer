# Phase 91: FIX-MPRIS (Phase 77 Deferred MPRIS2 Tests) - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Bookkeeping-only close-out of FIX-MPRIS-01/02/03. The 7 D-03-deferred MPRIS2 cross-file failures the roadmap entry was written to repair were already turned green by Phase 77 close-out commit `378440c` ("fix(77-06): unregister MPRIS2 OBJECT_PATH in fixture teardown — cluster 2 close-out"). Phase 91 verifies that closure still holds, tightens the success-criterion grep that is provably miswritten, refreshes the stale baseline test count, and flips the requirement statuses. No test edits, no production code changes, no fixture changes.

</domain>

<decisions>
## Implementation Decisions

### Premise — closure vs. repair
- **D-01:** Phase 91 closes as already-done; bookkeeping only. The 7 MPRIS2 cluster-2 failures from Phase 77 D-03 are already fixed by commit `378440c`. Local run `uv run pytest tests/test_media_keys_mpris2.py`: **12 passed, 1 skipped** (skip is `test_playerctl_lists_service` — playerctl not installed; legitimate environmental skip, not a cluster mask). The `unique_mpris_service_name` fixture is wired into all 8 backend tests at `tests/conftest.py:35`. Phase 77-VERIFICATION.md "Deferred Items" row 1 explicitly records the close-out via 378440c.
- **D-02:** Phase 91 plan therefore is a single bookkeeping plan — verify, tighten SC1, refresh SC2 baseline, flip FIX-MPRIS-01/02/03 to `Complete`. No test files in `tests/` are edited.

### SC1 grep precision
- **D-03:** Tighten the SC1 grep in the ROADMAP entry. Current text `grep -rn "class FakePlayer(QObject)" tests/ | wc -l` returns **2**, not 1, because `tests/test_fake_player_no_inline.py:28` mentions the literal pattern inside its own docstring describing the drift-guard. The grep as written can never pass even when the structural invariant is true.
- **D-04:** Replace with an anchored form that excludes docstring-quoted occurrences. Locked candidate: `grep -rnP '^\s*class\s+FakePlayer\s*\(\s*QObject\s*\)\s*:' tests/ | wc -l` (PCRE anchor to line start with leading whitespace, balanced parens, trailing colon — matches only an actual class declaration). Verified-by-hand against the current tree: returns 1, matches only `tests/_fake_player.py:37`. Planner may equivalently scope to `tests/_fake_player.py` and the inline-ban guard (`tests/test_fake_player_no_inline.py`) — both reach the same invariant.
- **D-05:** Do not edit `tests/test_fake_player_no_inline.py` to remove the literal from its docstring — the drift-guard runtime check at `tests/test_fake_player_no_inline.py:50` already implements the structural rule programmatically (and currently passes with 0 offenders per Phase 77-VERIFICATION.md). The docstring is the right place to document the rule in English; the source-grep is where SC1 needs the precision fix.

### Baseline test count (SC2)
- **D-06:** SC2 reference "1462-test baseline" is historical (Phase 77 close-out count); current `pytest tests/` reports **1827 collected** (1821 passed + 1 skipped + 5 failed today). Refresh SC2 at phase-close to whatever count `pytest tests/` reports immediately after Phase 91's commits land. No semantic change — "no MPRIS test-runtime regressions vs. the pre-phase baseline" is what the criterion is actually asserting.
- **D-07:** Phase 91 plan records the exact pre-phase count as the baseline anchor; verification asserts `passed >= baseline` (allowing for any independent count growth, never shrinkage).

### Verification rigor before Flatpak (Phase 86 dependency)
- **D-08:** Single host run on this dev machine is sufficient evidence for closure. Required checks in the verification plan:
  1. `uv run pytest tests/test_media_keys_mpris2.py` → 12 passed, 1 skipped, 0 failed (the playerctl skip is legitimate env-absent).
  2. `uv run pytest tests/test_fake_player_signal_parity.py tests/test_fake_player_no_inline.py` → 3 passed (drift-guards green).
  3. Tightened SC1 grep (D-04 form) returns exactly `1`.
  4. `tests/test_fake_player_no_inline.py` runtime offender count == 0.
- **D-09:** Phase 77-VERIFICATION.md "Truth 5" already proves the cross-file ordering case (`test_main_window_integration.py → test_media_keys_mpris2.py`: 77 passed, 1 skipped, 1 pre-existing fail — the hamburger fail, not MPRIS). Phase 91 plan cites that proof by reference; does not re-run the multi-order pair locally. Flatpak in-sandbox MPRIS verification belongs to Phase 86 acceptance, not Phase 91.

### Requirement / roadmap status updates
- **D-10:** Flip `FIX-MPRIS-01`, `FIX-MPRIS-02`, `FIX-MPRIS-03` in `.planning/REQUIREMENTS.md` from `Pending` to `Complete`. Flip Phase 91 checkbox in ROADMAP from `- [ ]` to `- [x]`. Update the SC1 line in the ROADMAP Phase 91 detail block to the D-04 tightened grep.
- **D-11:** Phase 77-VERIFICATION.md "Deferred Items" row 1 (the close-out reference to 378440c) is the canonical pointer Phase 91 cites. Add a one-line entry in `.planning/RETROSPECTIVE.md` (if the project convention is to log retroactive closures there) noting that Phase 91 verified Phase 77's close-out and did no further test changes — planner picks the exact destination if RETROSPECTIVE.md is not the right home.

### Claude's Discretion
- Whether the Phase 91 single plan is named `91-01-PLAN.md` or split into `91-01-PLAN.md` (verify + grep update) + `91-02-PLAN.md` (REQUIREMENTS + ROADMAP flips). Planner picks; single plan is preferred unless the SUMMARY rhythm calls for two.
- Exact grep phrasing in the updated SC1 — the D-04 PCRE form is the locked semantic; planner may simplify to a multi-line invocation if PCRE portability is a concern (e.g., `grep -rn 'class FakePlayer(QObject)' tests/_fake_player.py | wc -l` — single-file scope reaching the same invariant via a different route).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 77 close-out evidence (defines what's already done)
- `.planning/milestones/v2.1-phases/77-test-infrastructure-stabilization-fix-pre-existing-test-doub/77-VERIFICATION.md` — "Truth 5" (MPRIS isolation + cross-file order), "Deferred Items" row 1 (close-out commit 378440c), "Required Artifacts" (fixtures + drift-guards). The authoritative proof that Phase 91's premise is satisfied.
- `.planning/milestones/v2.1-phases/77-test-infrastructure-stabilization-fix-pre-existing-test-doub/77-CONTEXT.md` §D-10, §D-18 — locked shape of the MPRIS2 SERVICE_NAME-monkeypatch fixture (`unique_mpris_service_name`); §D-17 — source-grep drift-guard pattern Phase 91 is preserving.
- Commit `378440c` — "fix(77-06): unregister MPRIS2 OBJECT_PATH in fixture teardown (cluster 2 close-out)" — the actual repair Phase 91 verifies.

### Roadmap / requirements (targets of the bookkeeping flips)
- `.planning/ROADMAP.md` §"Phase 91" — current entry with the miswritten SC1 grep; D-04 updates the SC1 line; D-10 flips the checkbox.
- `.planning/REQUIREMENTS.md` rows `FIX-MPRIS-01`, `FIX-MPRIS-02`, `FIX-MPRIS-03` — Pending → Complete per D-10.

### Test convention (read-only — no edits in Phase 91)
- `tests/_fake_player.py` — canonical FakePlayer (line 37 declaration); 18 Signal declarations mirroring `musicstreamer/player.py`.
- `tests/conftest.py:35` — `unique_mpris_service_name` fixture (already in place).
- `tests/conftest.py:55-71` — OBJECT_PATH preemptive release + teardown (the 378440c fix).
- `tests/test_fake_player_no_inline.py:50` — runtime drift-guard (programmatic check that supersedes the SC1 source-grep as the day-to-day enforcement).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/conftest.py:35` — `unique_mpris_service_name` already monkeypatches `musicstreamer.media_keys.mpris2.SERVICE_NAME` per test. Wired into 8 of the 13 tests in `tests/test_media_keys_mpris2.py` (the 5 not using it are the cover-art-path tests that don't construct a backend).
- `tests/_fake_player.py:37` — canonical `class FakePlayer(QObject)` with 18 Signal declarations; sole-declaration site preserved by both drift-guards.
- `tests/test_fake_player_no_inline.py` (53 lines) — runtime source-grep enforcement of D-17 shape; passes today.
- `tests/test_fake_player_signal_parity.py` (86 lines) — runtime AST-parse enforcement of D-16 name+arity parity; passes today.

### Established Patterns
- **Drift-guards programmatic, not text-anchored.** The project's convention (Phase 79 `test_yt_dlp_opts_drift.py`, Phase 69 `test_packaging_spec.py`, Phase 77 D-16/D-17) is to encode invariants as pytest tests that read source via `ast.parse` or `re.compile(...).search`. The Phase 91 SC1 grep is an out-of-band proxy for the same invariant — fine as a roadmap-level check, but only if textually correct.
- **Bookkeeping-only phases exist.** Several v2.1 phases closed with no test/code edits — pattern is one short plan, a verification commit, REQUIREMENTS flip, ROADMAP flip. Phase 91 fits that shape.

### Integration Points
- Phase 86 (Flatpak) `PKG-LIN-FP-08` accepts on in-sandbox MPRIS2 verification AFTER Phase 91 closes. Phase 91 closure means: requirement statuses are flipped, SC1 grep is honest, baseline number is current. Phase 86 still has to do its own in-sandbox MPRIS proof.

</code_context>

<specifics>
## Specific Ideas

- Verification command set (locked per D-08): the four checks above, run in this order, evidence captured in the Phase 91 SUMMARY.
- Tightened SC1 grep candidate (locked per D-04): `grep -rnP '^\s*class\s+FakePlayer\s*\(\s*QObject\s*\)\s*:' tests/ | wc -l` — anchored, returns 1 today.

</specifics>

<deferred>
## Deferred Ideas

The full-suite `uv run pytest tests/` baseline today is **1821 passed, 1 skipped, 5 failed**. None of the 5 are MPRIS-related and none belong to Phase 91's scope, but they are real failures and should not get lost. Captured as separate todos in `.planning/todos/pending/` so future phases can fold them:

- `2026-05-26-test-bump-version-json-decoder-failures.md` — `tests/test_bump_version.py::test_bump_stages_pyproject` and `::test_rollback_on_simulated_commit_failure` both fail with JSON decoder errors; needs diagnosis (release-tooling regression, separate from runtime code).
- `2026-05-26-test-constants-drift-soma-nn-requirements.md` — `tests/test_constants_drift.py::test_soma_nn_requirements_registered` failing; likely Phase 83 SomaFM NN follow-up.
- `2026-05-26-test-hamburger-menu-actions-pre-existing-d03.md` — `tests/test_main_window_integration.py::test_hamburger_menu_actions`; documented as a Phase 74/76 carry-over in Phase 77-VERIFICATION.md "Deferred Items" row 2. Not new.
- `2026-05-26-test-media-keys-smtc-win32-fallback.md` — `tests/test_media_keys_smtc.py::test_end_to_end_factory_fallback_on_win32_without_winrt`; Windows-only path, fires on Linux when winrt absent. Test design issue, not behavioral.
- Phase 77-VERIFICATION.md "Deferred Items" row 3 (12 `gi` collection errors + 34 test-item failures under Python 3.13 venv when system gi is built for 3.14) — environmental; project currently runs Python 3.14. If a Python 3.13 venv reappears, this resurfaces.

### Out of scope for Phase 91 (do not pull in)
- Editing any test file in `tests/`. Phase 91 is bookkeeping.
- Editing any fixture in `tests/conftest.py`. Already correct.
- Editing any production code in `musicstreamer/`. Phase 77 left it byte-identical and Phase 91 does the same.
- Re-running the multi-order pair locally — Phase 77-VERIFICATION.md "Truth 5" already proves it; re-asserting it here is duplicate work.

</deferred>

---

*Phase: 91-fix-mpris-phase-77-deferred-mpris2-tests*
*Context gathered: 2026-05-26*
