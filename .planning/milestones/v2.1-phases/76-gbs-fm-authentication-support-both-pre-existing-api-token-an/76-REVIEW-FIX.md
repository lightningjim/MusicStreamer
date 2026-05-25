---
phase: 76-gbs-fm-authentication-support-both-pre-existing-api-token-an
fixed_at: 2026-05-23T00:00:00Z
review_path: .planning/phases/76-gbs-fm-authentication-support-both-pre-existing-api-token-an/76-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 8
skipped: 1
status: partial
---

# Phase 76: Code Review Fix Report

**Fixed at:** 2026-05-23
**Source review:** .planning/phases/76-gbs-fm-authentication-support-both-pre-existing-api-token-an/76-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 9 (CR-01 + WR-01..WR-04 + IN-01..IN-04)
- Fixed: 8
- Skipped: 1 (IN-01 — deferred per reviewer's "optional / defer to follow-up phase" guidance)

All in-scope test subset (`test_oauth_helper_gbs.py + test_oauth_helper_twitch.py +
test_accounts_dialog.py + test_gbs_api.py`) was re-run after every commit. Baseline
was 144 tests passing; after the fix series the subset reports **160 passing, 1
warning** (16 new tests added across CR-01, WR-02, WR-03, WR-04). No regressions.

## Fixed Issues

### CR-01 + WR-01: Provider-aware failure dialog (title + retry target)

**Files modified:** `musicstreamer/ui_qt/accounts_dialog.py`, `tests/test_accounts_dialog.py`
**Commit:** c787e60
**Applied fix:**
- Widened `_show_failure_dialog(category, detail)` → `_show_failure_dialog(provider, category, detail)`.
- Added `_PROVIDER_TITLES = {"twitch": "Twitch", "gbs": "GBS.FM"}` class constant; window title now becomes `f"{provider_title} Connection Failed"`. Unknown providers render the raw provider string (visibly wrong rather than misleadingly Twitch-branded — a defensive choice noted in the comment).
- Retry-Accepted branch now routes to `_launch_gbs_login_subprocess()` when `provider == "gbs"`, else `_launch_oauth_subprocess()`. Previously hardcoded to Twitch.
- Updated `_classify_and_show_failure` to pass `provider` through to the display sink.
- **WR-01 cascade (mandatory):** updated all 8 Twitch test sites that monkeypatched `_show_failure_dialog` with the old 2-arg signature to the new 3-arg `(provider, category, detail)` shape, and tightened their assertions to verify the provider argument is `"twitch"`. Sites: `test_oauth_finished_failure_calls_show_failure_dialog`, four `TestAccountsDialogStderrParsing` tests, two `TestAccountsDialogFailureDialogPlainText` tests, two `TestAccountsDialogOAuthLog` tests.
- Added new test class `TestAccountsDialogProviderAwareFailureDialog` with 4 tests: `test_gbs_failure_dialog_title_is_gbs`, `test_twitch_failure_dialog_title_unchanged` (regression guard), `test_gbs_failure_retry_launches_gbs_subprocess`, `test_twitch_failure_retry_launches_twitch_subprocess` (regression guard).

### WR-02: closeEvent terminates orphan subprocesses

**Files modified:** `musicstreamer/ui_qt/accounts_dialog.py`, `tests/test_accounts_dialog.py`
**Commit:** 8e60b05
**Applied fix:**
- Added `closeEvent` override that walks both `_oauth_proc` and `_gbs_login_proc` attributes, calls `terminate()`, waits up to 2000ms via `waitForFinished`, falls back to `kill()` on timeout, and always calls `super().closeEvent(event)`.
- Each step wrapped in `try/except Exception` so one subprocess failing during cleanup cannot prevent the other from being cleaned up or block close.
- Added new test class `TestAccountsDialogCloseEventCleanup` with 5 tests covering: terminate-fires path, waitForFinished-timeout-triggers-kill path, both-subprocesses-cleaned-up path, no-subprocess-running graceful path, and one-subprocess-throws-still-cleans-the-other regression guard.

### WR-03: Re-entrancy guard + button disable while GBS subprocess running

**Files modified:** `musicstreamer/ui_qt/accounts_dialog.py`, `tests/test_accounts_dialog.py`
**Commit:** 2831d44
**Applied fix:**
- `_launch_gbs_login_subprocess` now early-returns when `self._gbs_login_proc is not None` (re-entrancy guard).
- `_update_status` extended with a new branch: when `_gbs_login_proc is not None`, status shows `"Connecting..."`, the `_gbs_action_btn` is disabled, and `_gbs_import_btn` is hidden — mirroring Twitch's `"Connecting..."` gate at lines 205-207. Also explicitly re-enables `_gbs_action_btn` in the connected/not-connected branches so it returns to active state after `_on_gbs_login_finished` clears `_gbs_login_proc`.
- Added new test class `TestAccountsDialogGbsReentrancy` with 3 tests: button-disabled-while-running, second-launch-is-no-op-while-first-in-flight (asserts only ONE QProcess constructed and the slot reference doesn't flip), button-re-enabled-after-subprocess-finishes.

### WR-04: Harden `_validate_gbs_cookies` against lookalike domains (out-of-Phase-76-scope but exposed by Phase 76's import path)

**Files modified:** `musicstreamer/gbs_api.py`, `tests/test_gbs_api.py`
**Commit:** ce13ace
**Applied fix:**
- Replaced substring check `"gbs.fm" not in domain` with label-boundary check `not (domain == "gbs.fm" or domain.endswith(".gbs.fm"))`. Mirrors `oauth_helper._cookie_domain_matches_gbs` semantics so the validator and the subprocess-side cookie capture share one contract.
- Added 4 tests in `tests/test_gbs_api.py`: `test_validate_cookies_rejects_fakegbs_lookalike` (the canonical WR-04 attack), `test_validate_cookies_rejects_subdomain_attack` (`gbs.fm.evil.com`), `test_validate_cookies_accepts_subdomain_of_gbs` (positive regression guard), `test_validate_cookies_accepts_bare_gbs_domain` (positive regression for the no-leading-dot case).

**Out-of-Phase-76-scope deviation note:** `musicstreamer/gbs_api.py` is NOT in Phase 76's declared `files_modified` (Phase 76 owns oauth_helper.py + accounts_dialog.py + the two test files). However, the bug is **exposed** by Phase 76 via the new `_on_gbs_import_clicked` path (D-14) which routes through `CookieImportDialog`'s File/Paste tabs into this validator. The subprocess path Phase 76 added is safe (subprocess filters at collection time via `_cookie_domain_matches_gbs`), but the secondary import path Phase 76 also wires up was not. The fix is small and surgical (one line of substantive code change), and the reviewer explicitly justifies touching `gbs_api.py` for this finding. Treated as a deliberate, well-scoped deviation.

### IN-02: Narrowed exception type in `test_gbs_window_closed_before_login`

**Files modified:** `tests/test_oauth_helper_gbs.py`
**Commit:** efe83e0
**Applied fix:**
- Narrowed `except Exception: pass` (covering super().closeEvent's failure on a `__new__`'d instance) to `except (TypeError, RuntimeError): pass` — the specific Qt-side failure modes when the C++ QMainWindow was never constructed.
- Added a docstring comment explaining what the narrowing prevents (silent test pass if `_emit_event` or `_finish` itself raised on a JSON encoding bug — those would now propagate and fail the test loudly).

### IN-03: Extracted shared `_parse_oauth_stderr` helper

**Files modified:** `musicstreamer/ui_qt/accounts_dialog.py`
**Commit:** 58069c7
**Applied fix:**
- Lifted the duplicated 23-line stderr-parse block (verbatim across `_on_oauth_finished` lines 396-417 and `_on_gbs_login_finished` lines 473-496) into a single `@staticmethod _parse_oauth_stderr(proc) -> dict | None` helper.
- Both handlers now call `last_event = self._parse_oauth_stderr(proc)` — one line each, replacing the 20-line inline block.
- Comments at both call sites cite IN-03 and note any future D-12 evolution lands in one place.
- The two existing anti-pitfall source-inspection tests (`test_gbs_login_finished_no_strip_anti_pitfall`, `test_gbs_login_finished_no_provider_twitch_hardcode`) still pass: `.strip()` no longer appears on `netscape_text` lines, and `provider="gbs"` still appears in the success log_event body. No test-surface change required.

### IN-04: Documented `_make_bare_window` fragility

**Files modified:** `tests/test_oauth_helper_gbs.py`
**Commit:** 14ba8e4
**Applied fix:**
- Added a `.. warning::` docstring block to `_make_bare_window()` that flags the `__new__`-bypass-init pattern as **known fragile**, explains the IN-02-narrowed `(TypeError, RuntimeError)` cases as the canonical failure mode, and tells future maintainers that PySide6-upgrade trip-ups are **test-infrastructure regressions, not production regressions** — and that the fix is to extend this helper, not revert production code.
- Pure documentation hygiene; no behavior change.

## Skipped Issues

### IN-01: `_PROVIDER` default `"twitch"` couples to startup ordering

**File:** `musicstreamer/oauth_helper.py:59`
**Reason:** Deliberate skip per reviewer guidance. The REVIEW.md fix block is explicitly tagged "**Fix (optional, not strictly required for Phase 76 scope)**" and the reviewer concludes "**Defer to a follow-up phase if the risk is judged low.**"

The fix would require:
1. Changing `_PROVIDER = "twitch"` → `_PROVIDER: str | None = None` with a `RuntimeError` guard in `_emit_event`.
2. **Migrating** the existing pinned test `test_emit_event_default_provider_is_twitch` (lines 125-139 in `tests/test_oauth_helper_gbs.py`) which currently asserts the legacy default is Twitch — that test's contract is exactly the invariant IN-01 wants to break.

Cost/benefit for Phase 76:
- Risk reward is low: there is no current code path that imports `oauth_helper` from the main app process and calls `_emit_event` outside the subprocess (`oauth_helper.py` is a subprocess entry point, not a library imported by the GUI).
- Cost is non-trivial: test migration + new module-state assertion contract + risk of breaking the future startup-ordering invariant the existing test was added to guard.
- The reviewer's "defer to follow-up phase" framing explicitly authorizes deferral.

**Original issue:** `_PROVIDER = "twitch"` (module-level default at oauth_helper.py:59) is read by `_emit_event` (line 93). Future code paths that import `oauth_helper` and call `_emit_event` before `main()` runs would silently report `"twitch"` for the provider. Test `test_emit_event_default_provider_is_twitch` (lines 125-139) pins the current behavior as a "Twitch invariant preservation guard."

**Recommended follow-up:** schedule a small dedicated phase (or roll into the next oauth_helper-touching phase) that swaps the default to None, adds the runtime guard, AND replaces the pinned Twitch-default test with the inverse "must be explicitly set" contract.

---

## Verification Summary

- **Baseline (before fixes):** 144 tests passing on the in-scope subset.
- **After fixes:** 160 tests passing on the in-scope subset, 1 warning (pre-existing GLib deprecation, unrelated). Net +16 tests added across CR-01 (+4), WR-02 (+5), WR-03 (+3), WR-04 (+4).
- **Files modified:** `musicstreamer/ui_qt/accounts_dialog.py`, `musicstreamer/gbs_api.py` (out-of-scope deviation, justified), `tests/test_accounts_dialog.py`, `tests/test_oauth_helper_gbs.py`, `tests/test_gbs_api.py`.
- **Files NOT modified:** `musicstreamer/oauth_helper.py` (IN-01 was the only oauth_helper.py finding; it was the deliberate skip).
- **Commit history (chronological):**
  1. `c787e60` — fix(76): CR-01+WR-01 parameterize _show_failure_dialog for provider-aware title + retry
  2. `8e60b05` — fix(76): WR-02 add closeEvent to terminate orphan oauth_helper subprocesses on dialog close
  3. `2831d44` — fix(76): WR-03 gate GBS Connect button while subprocess in flight + early-return re-entrancy guard
  4. `ce13ace` — fix(76): WR-04 harden _validate_gbs_cookies domain match against fakegbs.fm lookalikes
  5. `efe83e0` — fix(76): IN-02 narrow super().closeEvent exception type in test_gbs_window_closed_before_login
  6. `58069c7` — fix(76): IN-03 extract shared _parse_oauth_stderr helper from twin Twitch/GBS handlers
  7. `14ba8e4` — fix(76): IN-04 document _make_bare_window fragility (PySide6-upgrade fault-isolation note)

---

_Fixed: 2026-05-23_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
