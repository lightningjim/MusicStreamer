---
phase: 76
plan: 04
subsystem: ui_qt
tags: [gbs-fm, tests, accounts-dialog, tdd, regression-guards]
requires:
  - 76-01
  - 76-03
provides:
  - test_gbs_status_shows_connected_when_cookies_present
  - test_gbs_status_shows_not_connected_when_no_cookies
  - test_gbs_import_button_exists_with_correct_text_and_handler
  - test_gbs_action_launches_subprocess_when_not_connected
  - test_gbs_disconnect_clears_cookies_with_yes
  - test_gbs_disconnect_no_op_with_no
  - test_gbs_disconnect_tolerates_oserror
  - test_gbs_import_button_opens_cookieimportdialog
  - test_gbs_login_finished_writes_cookies_on_success
  - test_gbs_login_finished_does_not_strip_netscape
  - test_gbs_login_finished_logs_provider_gbs_event
  - test_gbs_login_finished_invalidates_bad_netscape
  - test_gbs_login_finished_failure_dialog_for_each_category  # parametrized x4
  - test_gbs_login_finished_no_strip_anti_pitfall
  - test_gbs_login_finished_no_provider_twitch_hardcode
affects:
  - tests/test_accounts_dialog.py
tech_stack:
  added: []
  patterns:
    - MagicMock(spec=QProcess) + _mock_proc_with_stderr helper for finished-handler tests
    - monkeypatch.setattr on module-attribute paths (e.g. accounts_dialog.os.remove) for deferred-import / module-level-symbol patching
    - inspect.getsource regression guards for source-level invariants (no .strip(), no hardcoded provider)
    - pytest.mark.parametrize over Phase 999.3 category list
    - Synthetic Netscape fixture as class constant (test_sessionid_value / test_csrftoken_value literals — T-76-T4)
key_files:
  created: []
  modified:
    - tests/test_accounts_dialog.py
decisions:
  - "Used isHidden() instead of isVisible() for QPushButton visibility assertions because Qt widgets that have not been show()'n return isVisible()==False regardless of setVisible(True). isHidden() reflects the explicit setVisible(False) state directly and is the canonical test-without-show pattern in offscreen Qt test runs."
  - "Migrated test_gbs_connect_opens_dialog_with_correct_kwargs (pre-Plan-76-04 line 1000-1020) into a RENAMED test (test_gbs_connect_delegates_to_launch_subprocess) rather than deleting it — the rename preserves git-blame continuity for the test that originally locked the connect-branch contract, while the kwargs-on-CookieImportDialog assertion gets a NEW home in test_gbs_import_button_opens_cookieimportdialog."
  - "Synthetic Netscape fixture stored as a class constant _GBS_NETSCAPE_VALID so all three success-path tests share the exact same bytes (no drift risk between tests). Uses verbatim literals from PLAN 76-04 <interfaces> block."
  - "os.remove monkeypatch targets musicstreamer.ui_qt.accounts_dialog.os.remove (module-attribute path) rather than os.remove (global) — the source calls os.remove() against its module-level os import, so patching at the use-site is the canonical monkeypatch-where-it-is-used pattern and is more explicit about scope."
  - "Anti-pitfall regression guards 6 & 7 (no .strip() / no provider='twitch' hardcode) use inspect.getsource at runtime rather than relying on the plan's grep gates. This is belt-and-braces: a refactor that reformats the source could break a grep gate (or worse, silently pass when broken) but inspect.getsource is robust to whitespace changes."
metrics:
  duration: "~25 minutes"
  completed: "2026-05-23"
  tasks_completed: 3
  files_modified: 1
  lines_changed: "+543 -18 (net +525)"
---

# Phase 76 Plan 04: AccountsDialog GBS Test Coverage Summary

Extended `TestAccountsDialogGBS` with 15 new test cases (counting the
parametrized failure-category test as 4 cases) and migrated 2 pre-existing
tests that asserted against the Plan-76-03-superseded GBS surface. The
class now provides RED→GREEN contract coverage for every behavior Plan
76-03 ships: 2-state status enumeration, secondary import button,
QProcess subprocess launch with `--mode gbs`, disconnect-Yes/No flow,
PermissionError tolerance, and the full `_on_gbs_login_finished` matrix
(success Netscape write with 0o600, leading-newline preservation,
provider='gbs' logger event, validator-reject failure routing,
parametrized failure-category propagation, and two `inspect.getsource`
regression guards for the no-`.strip()` + no-hardcoded-'twitch' invariants).

## What Was Built

### Task 1: Migrate stale tests + status/import-button tests (commit `f1fe633`)

**Migrations (2 tests):**

| Pre-Plan-76-04 test | Migration |
|----|----|
| `test_gbs_status_initial_not_connected` (line 919-929) | Updated to assert `"Connect to GBS.FM…"` (U+2026) instead of old `"Import GBS.FM Cookies..."`; added secondary-import-button visibility assertion. |
| `test_gbs_connect_opens_dialog_with_correct_kwargs` (line 1000-1020) | RENAMED to `test_gbs_connect_delegates_to_launch_subprocess`. Connect-branch now asserts delegation to `_launch_gbs_login_subprocess` (monkeypatch-replaced recorder). The kwargs-on-CookieImportDialog assertion moved to a NEW test in Task 2 (`test_gbs_import_button_opens_cookieimportdialog`). |

Each migration carries an inline `# Migrated for Phase 76 D-03 collapse —
was <name> at tests/test_accounts_dialog.py:LL-LL` comment per project
memory `feedback_mirror_decisions_cite_source.md`.

**New tests (3):**

- `test_gbs_status_shows_connected_when_cookies_present` — flexes between
  `"Connected"` and `"Connected (cookies)"` per plan latitude; pins
  `"Disconnect"` primary text + import-btn hidden.
- `test_gbs_status_shows_not_connected_when_no_cookies` — monkeypatched
  `_is_gbs_connected` False; pins `"Connect to GBS.FM…"` + import-btn
  visible.
- `test_gbs_import_button_exists_with_correct_text_and_handler` — type
  check, U+2026 single-char ellipsis, NOT three-dot variant, bound
  handler exists.

### Task 2: Subprocess + disconnect + import-button tests (commit `7c1a9bc`)

**5 new tests** mirroring the Twitch shape (each with `# Mirror:` comment
citing the source line range):

1. `test_gbs_action_launches_subprocess_when_not_connected` — mirror
   `TestAccountsDialogConnect:158-178`; asserts `QProcess.start` argv
   `["-m", "musicstreamer.oauth_helper", "--mode", "gbs"]` verbatim.
2. `test_gbs_disconnect_clears_cookies_with_yes` — mirror
   `TestAccountsDialogDisconnect:113-134`; `os.remove` called once with
   `paths.gbs_cookies_path()`; status flips to Not connected.
3. `test_gbs_disconnect_no_op_with_no` — mirror
   `TestAccountsDialogDisconnect:136-153`; `os.remove.assert_not_called()`;
   cookies file still exists.
4. `test_gbs_disconnect_tolerates_oserror` — Phase 60 HIGH 2 regression
   guard; `PermissionError` swallowed AND `_update_status` still fires
   (verified via call-count recorder).
5. `test_gbs_import_button_opens_cookieimportdialog` — replacement
   home for the pre-Plan-76-04 kwargs-on-CookieImportDialog invariant;
   asserts `target_label="GBS.FM"`, `cookies_path=paths.gbs_cookies_path`,
   `validator=gbs_api._validate_gbs_cookies`, `oauth_mode=None`.

### Task 3: Finished-handler + anti-pitfall regression guards (commit `4986633`)

**6 new tests + 1 parametrized (x4) + 2 inspect.getsource guards:**

1. `test_gbs_login_finished_writes_cookies_on_success` — exit 0 + valid
   Netscape → file written verbatim, 0o600 perms, status flips to
   Connected.
2. `test_gbs_login_finished_does_not_strip_netscape` — feeds stdout with
   `"\n\n"` prefix; written bytes still start with `"\n\n"` (RESEARCH
   line 709 anti-pitfall regression guard at the bytewise level).
3. `test_gbs_login_finished_logs_provider_gbs_event` — OAuthLogger
   monkeypatched to a MagicMock; asserts `event["provider"] == "gbs"`
   (T-76-D4 Spoofing mitigation).
4. `test_gbs_login_finished_invalidates_bad_netscape` — exit 0 +
   `b"garbage text not netscape format"` stdout fails
   `_validate_gbs_cookies` → no file write + `_classify_and_show_failure`
   invoked with `provider="gbs"`.
5. `test_gbs_login_finished_failure_dialog_for_each_category` —
   parametrized over `["LoginTimeout", "WindowClosedBeforeLogin",
   "InvalidTokenResponse", "SubprocessCrash"]`; each category in stderr
   JSON is preserved in `last_event["category"]` when handed off to
   `_classify_and_show_failure`.
6. `test_gbs_login_finished_no_strip_anti_pitfall` — `inspect.getsource`
   gate: no `.strip()` appears on any line mentioning `netscape_text`.
7. `test_gbs_login_finished_no_provider_twitch_hardcode` — T-76-D4
   Spoofing: no `'"provider": "twitch"'` (or `'provider': 'twitch'`)
   literal anywhere in `_on_gbs_login_finished` body; positive
   `'"provider": "gbs"'` assertion.

The synthetic Netscape fixture is stored as a class constant
`_GBS_NETSCAPE_VALID` with literal `test_sessionid_value` /
`test_csrftoken_value` values per T-76-T4 (no real session IDs in test
code).

## Verification

```bash
$ python -m pytest tests/test_accounts_dialog.py::TestAccountsDialogGBS -q
24 passed, 1 warning in 0.21s

$ python -m pytest tests/test_accounts_dialog.py -q
61 passed, 1 warning in 0.27s

$ python -m pytest \
    tests/test_accounts_dialog.py::TestAccountsDialogOAuthFinished \
    tests/test_accounts_dialog.py::TestAccountsDialogStderrParsing \
    tests/test_accounts_dialog.py::TestAccountsDialogFailureDialogPlainText \
    tests/test_accounts_dialog.py::TestAccountsDialogRetry -q
11 passed, 1 warning in 0.14s
```

Anti-pitfall verification gates from the plan:

```bash
$ grep -c 'def test_gbs_login_finished' tests/test_accounts_dialog.py
7              # plan requires >= 6 ✓

$ grep -c 'inspect.getsource' tests/test_accounts_dialog.py
2              # plan requires >= 2 ✓

$ grep -c 'def test_gbs_status_shows_connected\|def test_gbs_status_shows_not_connected\|def test_gbs_import_button_exists' tests/test_accounts_dialog.py
3              # plan requires 3 ✓
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Used `isHidden()` instead of `isVisible()` for QPushButton visibility assertions**

- **Found during:** Task 1 first test execution.
- **Issue:** The plan's behavior block called for
  `dialog._gbs_import_btn.isVisible() == True` / `== False` assertions.
  When tested on the offscreen Qt platform (`QT_QPA_PLATFORM=offscreen`
  in the project's pytest setup), `QPushButton.isVisible()` returns
  `False` for any widget whose parent dialog has not been `.show()`'n,
  regardless of the explicit `setVisible(True)` state.
- **Fix:** Switched all three visibility assertions to use `isHidden()`,
  which directly reflects the explicit `setVisible(False)` flag (not
  derived from the show-state chain). `isHidden() is False` means
  "not explicitly hidden" — semantically what the test wants to verify.
- **Files modified:** `tests/test_accounts_dialog.py` (Task 1).
- **Commit:** `f1fe633`.
- **Acceptance-criterion impact:** The plan's source-grep gate
  `_gbs_import_btn\.isVisible\|_gbs_import_btn.*[vV]isible` returns 0
  matches for the new `isHidden`-based assertions. The SPIRIT of the
  criterion (both visibility branches exercised) is met — the tests
  assert hidden+False (visible) and hidden+True (hidden) — but the
  literal grep pattern no longer matches. Rule 1 takes precedence over
  the source-grep gate; the alternative (using `isVisible()`) produces
  a failing test against correctly-implemented production code, which
  would be a worse outcome.

**2. [Rule 3 - Blocking] One "Import GBS.FM Cookies..." string remains in a comment**

- **Found during:** Final verification gate.
- **Issue:** The plan's acceptance criterion says `grep -c
  "Import GBS.FM Cookies..."` should return 0. After Task 1, one match
  remains — but it's inside a `# Migrated for Phase 76 D-03 collapse`
  audit comment in `test_gbs_status_initial_not_connected`, NOT in a
  test body assertion.
- **Fix:** Kept the comment. Project memory
  `feedback_mirror_decisions_cite_source.md` requires migration audit
  trails to NAME the original test purpose so reviewers can verify the
  migration didn't lose coverage. Deleting the string from the comment
  would defeat that audit requirement.
- **Files modified:** None (intentional comment retention).
- **Acceptance-criterion impact:** The criterion's INTENT was "no test
  body asserts the old text." Verified: no test body asserts the old
  text. The single comment match is an audit feature.

No architectural changes. No new dependencies. No CLAUDE.md directives
were applicable beyond the existing routing skill (not relevant for this
test-only plan).

## Authentication Gates

None — this plan does not touch live external services. All tests use
mocks/monkeypatches.

## Known Stubs

None. All tests are fully wired and green.

## Threat Flags

No new threat surface introduced. T-76-T4 (Information Disclosure —
synthetic cookie values only) is mitigated by the class constant
`_GBS_NETSCAPE_VALID` using literal `test_sessionid_value` /
`test_csrftoken_value`. T-76-T3 (cookies-pollution on dev machine) is
mitigated by the existing `monkeypatch.setattr(paths, "_root_override",
str(tmp_path))` pattern reused from the Plan 76-03-merged class. T-76-T5
(stale-text silent pass) is mitigated by the two pre-existing failing
tests now being migrated to the new contract (audit-trail comment
preserves the original text reference).

## Notes for Plan 76-05 (UAT)

The full `TestAccountsDialogGBS` class is now 24 tests strong and
exercises every code path in `_on_gbs_action_clicked`, `_on_gbs_import_clicked`,
`_launch_gbs_login_subprocess`, and `_on_gbs_login_finished` that does not
require a live subprocess. UAT-side work for Plan 76-05 should focus on:

- Live `oauth_helper --mode gbs` subprocess invocation (this plan
  intentionally mocks `QProcess` everywhere).
- The actual `_GbsLoginWindow` QWebEngineView interaction (Plan 76-01).
- End-to-end Netscape file write + subsequent gbs_api read flow.

## Self-Check: PASSED

- File exists: `tests/test_accounts_dialog.py` — FOUND (1346 lines)
- Commit `f1fe633` (Task 1) — FOUND in git log
- Commit `7c1a9bc` (Task 2) — FOUND in git log
- Commit `4986633` (Task 3) — FOUND in git log
- All 24 GBS tests pass: `TestAccountsDialogGBS` 24/24 ✓
- Full file regression: 61/61 ✓
- Twitch regression: 11/11 ✓
- Anti-pitfall gates: 3/3 PASS (`inspect.getsource` >= 2, `def test_gbs_login_finished` >= 6, new status/import-button defs == 3)
