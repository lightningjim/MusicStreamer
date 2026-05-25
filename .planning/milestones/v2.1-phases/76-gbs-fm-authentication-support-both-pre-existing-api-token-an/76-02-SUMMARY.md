---
phase: 76
plan: 02
subsystem: oauth_helper
tags: [tests, red-stubs, gbs, contract-pin]
requires:
  - tests/test_oauth_helper_twitch.py (mirror source)
  - musicstreamer/gbs_api.py::_validate_gbs_cookies (existing validator)
provides:
  - tests/test_oauth_helper_gbs.py (21 RED contract tests)
affects:
  - musicstreamer/oauth_helper.py (target of imports — symbols delivered by Plan 76-01)
tech_stack:
  added: []
  patterns:
    - deferred-imports-inside-test-functions (mirrors test_oauth_helper_twitch.py discipline)
    - __new__-bypass-init-with-manual-attr-seed (avoids QtWebEngine + QApplication for unit tests)
    - monkeypatch-QApplication-quit-exit-noop (so _finish doesn't block)
key_files:
  created:
    - tests/test_oauth_helper_gbs.py
  modified: []
decisions:
  - "Deferred imports inside each test function (NOT module-level) so collection succeeds before Plan 76-01 lands"
  - "Real fixture-mirroring contracts, no pytest.fail placeholders — tests auto-turn-GREEN as Plan 76-01 Tasks 1-4 merge"
  - "_make_bare_window helper uses __new__ + manual attr init to skip GUI plumbing while exercising pure-Python state-machine paths"
  - "_make_secure_fake_cookie extension stubs the QNetworkCookie surface _cookie_to_netscape touches (isSecure/path/isSessionCookie), keeping the verbatim _fake_cookie helper from Twitch intact"
  - "test_emit_event_default_provider_is_twitch passes at base AND after 76-01 (Twitch invariant guard)"
  - "test_gbs_emits_provider_gbs_field uses monkeypatch.setattr default raising=True so AttributeError before _PROVIDER is added is the desired RED signal"
metrics:
  duration_sec: 301
  tasks_complete: 2
  files_changed: 1
  tests_added: 21
  completed: 2026-05-23T21:28:22Z
---

# Phase 76 Plan 76-02: RED Test Stubs for GBS.FM Oauth Helper Summary

Wave 0 contract pins — 21 failing-first tests in `tests/test_oauth_helper_gbs.py` that encode every behavior Plan 76-01 (running in parallel worktree) ships for the `_GbsLoginWindow` subprocess, `_cookie_domain_matches_gbs`, `_GBS_LOGIN_URL` / `_GBS_TRIGGER_COOKIES` constants, `_PROVIDER` module variable, and `--mode gbs` argparse extension. Tests auto-transition RED → GREEN as Plan 76-01 Tasks 1-4 merge.

## Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Constants + domain-match + _emit_event provider tests | `39f888e` | tests/test_oauth_helper_gbs.py (10 tests) |
| 2 | _GbsLoginWindow construction + cookie-trigger + Netscape-flush + argparse tests | `04c175d` | tests/test_oauth_helper_gbs.py (+11 tests) |

## Test Coverage Map (Group A from 76-RESEARCH.md §Test Strategy lines 762-805)

| Test | Plan 76-01 Symbol Required | RED Failure Mode |
|------|----------------------------|------------------|
| `test_gbs_login_url_constant` | `_GBS_LOGIN_URL` (Task 1) | AttributeError |
| `test_gbs_trigger_cookies_constant` | `_GBS_TRIGGER_COOKIES` (Task 1) | ImportError |
| `test_cookie_domain_matches_gbs_{dot,www,bare,subdomain}` | `_cookie_domain_matches_gbs` (Task 1) | ImportError |
| `test_cookie_domain_rejects_{lookalike_gbs,subdomain_attack}` | `_cookie_domain_matches_gbs` (Task 1) | ImportError |
| `test_gbs_emits_provider_gbs_field` | `_PROVIDER` module attr (Task 2) | AttributeError via monkeypatch.setattr default raising=True |
| `test_emit_event_default_provider_is_twitch` | (passes at base AND post-76-01) | Twitch invariant preservation guard |
| `test_argparse_accepts_mode_gbs` | `_GBS_LOGIN_URL` (Task 1) | AttributeError on the hasattr cross-check; local parser construction always works |
| `test_gbs_login_window_constructor_smoke` | `_GbsLoginWindow` (Task 3) | ImportError |
| `test_gbs_trigger_fires_on_both_cookies` | `_GbsLoginWindow._on_cookie_added` (Task 3) | ImportError |
| `test_gbs_trigger_does_not_fire_on_only_sessionid` | `_GbsLoginWindow` (Task 3) | ImportError |
| `test_gbs_trigger_does_not_fire_on_only_csrftoken` | `_GbsLoginWindow` (Task 3) | ImportError |
| `test_gbs_trigger_ignores_non_gbs_domain` | `_GbsLoginWindow` + `_cookie_domain_matches_gbs` | ImportError |
| `test_gbs_flush_produces_valid_netscape` | `_GbsLoginWindow._flush_cookies` + `_validate_gbs_cookies` (existing) | ImportError on _GbsLoginWindow |
| `test_gbs_flush_deduplicates_repeated_cookies` | `_GbsLoginWindow._flush_cookies` dedup loop (Task 3) | ImportError |
| `test_gbs_timeout_emits_login_timeout` | `_GbsLoginWindow._on_timeout` + `_PROVIDER` | ImportError + AttributeError |
| `test_gbs_window_closed_before_login` | `_GbsLoginWindow.closeEvent` + `_PROVIDER` | ImportError + AttributeError |
| `test_gbs_collects_all_gbs_cookies_not_just_triggers` | `_GbsLoginWindow._on_cookie_added` collects every gbs.fm cookie | ImportError |

## RED State Verification (current base = f3811b54)

`python -m pytest tests/test_oauth_helper_gbs.py -x -q` exits non-zero with:
- `test_gbs_login_url_constant` → `AttributeError: module 'musicstreamer.oauth_helper' has no attribute '_GBS_LOGIN_URL'`

This is the desired Wave 0 contract-pin behavior. Other tests fail with `ImportError` (for `_GBS_TRIGGER_COOKIES`, `_cookie_domain_matches_gbs`, `_GbsLoginWindow`) or `AttributeError` (for `_PROVIDER` via monkeypatch).

## Collection Standalone (gate for Wave 0 — passes against base)

```bash
$ python -m pytest tests/test_oauth_helper_gbs.py --collect-only -q
... (21 tests listed)
21 tests collected in 0.03s
```

Deferred imports work as designed — no test file pulls `musicstreamer.oauth_helper` symbols at module load.

## Cross-Test Independence

```bash
$ python -m pytest tests/test_oauth_helper_twitch.py -x -q
14 passed, 1 warning in 0.13s
```

No regressions in the existing Twitch test surface.

## Mirror Source Citations (per project memory feedback_mirror_decisions_cite_source.md)

Each cloned test carries an inline `# Mirror: tests/test_oauth_helper_twitch.py:LL-LL` comment above the function definition. 9 such citations:

- `_fake_cookie` helper → `tests/test_oauth_helper_twitch.py:73-80`
- `test_gbs_login_url_constant` → `:118-120`
- `test_gbs_trigger_cookies_constant` → `:123-125`
- `test_cookie_domain_matches_gbs_dot` → `:83-85`
- `test_cookie_domain_matches_gbs_www` → `:88-90`
- `test_cookie_domain_matches_gbs_bare` → `:93-95`
- `test_cookie_domain_rejects_lookalike_gbs` → `:103-106`
- `test_gbs_emits_provider_gbs_field` → `:20-34` (adapted)
- `test_gbs_login_window_constructor_smoke` → `:151-154`

## Deviations from Plan

None — plan executed exactly as written.

Acceptance criteria for both tasks passed verbatim:
- Task 1: 10 `def test_` lines ✓, 1 `_fake_cookie` def ✓, 0 `pytest.fail` ✓, ≥ 1 `monkeypatch` (actual: 3 mentions) ✓, deferred imports inside function bodies ✓, collection succeeds ✓.
- Task 2: 21 total `def test_` lines (≥ 21) ✓, 5 `test_gbs_trigger` (≥ 3) ✓, 2 `test_gbs_flush` (≥ 2) ✓, 2 timeout|window_closed (≥ 2) ✓, 1 `test_argparse_accepts_mode_gbs` ✓, 4 `_validate_gbs_cookies` mentions (≥ 1) ✓, 9 `# Mirror:` citations (≥ 5) ✓, collection succeeds ✓, Twitch suite passes ✓.

## Threat Hygiene (per `<threat_model>` T-76-T1 + T-76-T2 + T-76-SC)

- **T-76-T1 (Information Disclosure):** All cookie values are synthetic short strings (`"v1"`, `"v2"`, `"tok"`, `"val"`, `"first"`, `"second"`, `"aux-val"`). `grep -E '[a-f0-9]{20,}' tests/test_oauth_helper_gbs.py | wc -l` returns 0. No dev-fixture file reads. No `gbs_api.cookies_path()` reads. ✓
- **T-76-T2 (Collection-failure tamper):** All `from musicstreamer.oauth_helper import ...` statements are inside test function bodies; `from musicstreamer.gbs_api import _validate_gbs_cookies` is also deferred. Module-level imports are limited to stdlib (`argparse`, `json`, `unittest.mock.MagicMock`). Collection passes against base. ✓
- **T-76-SC (Supply chain):** No new package installs. Test file uses existing pytest 8.x + unittest.mock. ✓

## Continuation Notes for Plan 76-01 Executor

When Plan 76-01 Tasks 1-4 land in main, `python -m pytest tests/test_oauth_helper_gbs.py -x -q` should exit 0 with all 21 tests passing. If any test fails post-merge, the failure pinpoints a contract drift:

- `test_gbs_emits_provider_gbs_field` failure → `_emit_event` was not refactored to read `_PROVIDER` module constant (76-01 Task 2 regression).
- `test_gbs_flush_produces_valid_netscape` failure → `_flush_cookies` output is not the format `_validate_gbs_cookies` accepts (76-01 Task 3 regression).
- `test_gbs_flush_deduplicates_repeated_cookies` failure → `_flush_cookies` missing the `(domain, name)` dedup pass (76-01 Task 3 regression — see PATTERNS.md Excerpt 1A lines 200-218).
- `test_gbs_collects_all_gbs_cookies_not_just_triggers` failure → `_on_cookie_added` is filtering to only trigger names before storage (forward-compat regression — see PATTERNS.md anti-pitfall line 148).

## Self-Check: PASSED

Files created:
- `tests/test_oauth_helper_gbs.py` — FOUND

Commits:
- `39f888e` (Task 1) — FOUND in worktree-agent branch log
- `04c175d` (Task 2) — FOUND in worktree-agent branch log
