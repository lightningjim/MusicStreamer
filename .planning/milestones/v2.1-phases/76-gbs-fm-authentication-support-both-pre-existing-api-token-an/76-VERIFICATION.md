---
phase: 76-gbs-fm-authentication-support-both-pre-existing-api-token-an
status: passed
score: 1/1 (GBS-AUTH-01 — manual UAT closure)
verified_at: 2026-05-23T23:05:00Z
backfilled_at: 2026-05-25T00:00:00Z
backfill_reason: "Phase 76 closed via Plan 76-05 manual UAT 2026-05-23; no VERIFICATION.md was authored at the time. Backfilled during v2.1 milestone audit (2026-05-25) for bookkeeping parity with the rest of v2.1."
closure_model: manual-uat
nyquist_compliant: false
human_verification:
  - test: "Plan 76-05 live UAT (4 scenarios)"
    expected: "All 4 live scenarios pass on a real Linux Wayland session with a live gbs.fm login"
    why_human: "QtWebEngine subprocess + cookie file mode bits + dialog flips + actual gbs.fm credentials cannot be exercised in CI"
    result: "PASS — completed 2026-05-23T23:05:00Z; see 76-05-HUMAN-UAT.md (total: 5, passed: 4 — Test 5 automated portion completed earlier; Tests 1-4 live UAT all passed)"
---

# Phase 76: GBS.FM Authentication — Verification Report

**Phase Goal:** Add in-app GBS.FM login subprocess via QtWebEngine (mirroring Twitch/Google patterns) so users no longer have to hand-import cookies files. Token-paste half dropped per Phase 76 D-03 verdict (Phase 60 + Phase 76 re-probe both confirmed 403/302 across all 8 auth vectors).

**Verified:** 2026-05-23 (Plan 76-05 manual UAT closure)
**Backfilled:** 2026-05-25 (this VERIFICATION.md authored during v2.1 milestone audit)
**Status:** `passed`

## Closure Model — Manual UAT (Plan 76-05)

Phase 76 ships under a **manual-UAT closure model**. Plans 76-01 through 76-04 land the code (subprocess + AccountsDialog wiring + cookie-write path + provider-aware failure dialog), and Plan 76-05 is a pure manual-UAT plan that gates closure on 4 live scenarios requiring a real Linux Wayland session + valid gbs.fm credentials.

Plans 76-01..76-04 all carry `status: passed`. Plan 76-05 carries `status: passed` with `uat_verified: 2026-05-23T23:05:00Z`. The 4 live scenarios (76-05-HUMAN-UAT.md) all returned `result: pass`. Test 5 (automated portion: full suite + grep gates) completed inline at plan landing with 61/61 Phase 76 tests green and a documented Rule-3 deviation on one grep gate (audit comment, not a test assertion).

## Goal Achievement

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `--mode gbs` accepted by `oauth_helper.py` argparse | VERIFIED | `musicstreamer/oauth_helper.py:449` — `choices=["twitch", "google", "gbs"]` |
| 2 | `_GbsLoginWindow` class exists; mirrors `_TwitchCookieWindow` (auto-detect on cookie observed, no Done button, 120s timeout) | VERIFIED | `musicstreamer/oauth_helper.py:239` |
| 3 | Auto-complete fires when BOTH `sessionid` AND `csrftoken` cookies observed on `gbs.fm` / `.gbs.fm`; lookalikes rejected | VERIFIED | `musicstreamer/oauth_helper.py:130-144` — `_cookie_domain_matches_gbs()` rejects `fakegbs.fm` / `gbs.fm.evil.com` |
| 4 | Full Netscape cookie dump (every cookie on `gbs.fm` domain) emitted on stdout | VERIFIED | `_GbsLoginWindow._flush_cookies` mirrors `_GoogleWindow` shape |
| 5 | `_PROVIDER` module-level constant, set by `main()` after argparse — guards against hardcoded `"twitch"` in `_emit_event` | VERIFIED | `musicstreamer/oauth_helper.py:59` + `:456`; `tests/test_oauth_helper_gbs.py::test_gbs_emits_provider_gbs_field` GREEN |
| 6 | AccountsDialog GBS group: `[Connect to GBS.FM…]` primary + `[Disconnect]` + secondary `[Import cookies file…]` (Phase 60 CookieImportDialog reachable) | VERIFIED | `musicstreamer/ui_qt/accounts_dialog.py:105-120` + `:359` |
| 7 | Cookies written via `paths.gbs_cookies_path()` with `os.chmod(0o600)`; `gbs_api._validate_gbs_cookies` gates the write | VERIFIED | `musicstreamer/ui_qt/accounts_dialog.py:569-583`; `musicstreamer/paths.py:54`; `musicstreamer/gbs_api.py:116` |
| 8 | Status label enumeration (`Not connected` / `Connecting...` / `Connected`) | VERIFIED | `musicstreamer/ui_qt/accounts_dialog.py:229-247` |
| 9 | Provider-aware failure dialog (extracted `_classify_and_show_failure(provider="gbs", ...)`) shared with Twitch | VERIFIED | 76-05-HUMAN-UAT.md Test 3 confirmed dialog title `"GBS.FM Connection Failed"` + `[Retry]` correctly relaunches GBS subprocess + oauth.log entry carries `provider="gbs"` |
| 10 | Pre-Phase-76 cookies still authenticate; no `gbs_api_token` SQLite key | VERIFIED | 76-05-HUMAN-UAT.md Test 4 confirmed (additive feature, D-03) |

## Live UAT Results (Plan 76-05)

All 4 live scenarios passed 2026-05-23:

1. **Live happy-path login** — `[Connect to GBS.FM…]` → QtWebEngine subprocess → user logs in → cookies file at `~/.local/share/musicstreamer/gbs-cookies.txt` with mode `0o600`, contains `sessionid` + `csrftoken`; `oauth.log` entry `{"category":"Success","provider":"gbs"}` observed.
2. **Disconnect flow + secondary-button reachability** — All 13 numbered steps confirmed; informal step 14 (WR-02 closeEvent / mid-login close) also confirmed.
3. **120s timeout failure path + category-aware dialog** — CR-01 fix verified live; dialog title `"GBS.FM Connection Failed"` (not Twitch); `[Retry]` correctly relaunches GBS subprocess; oauth.log entry carries `provider="gbs"`.
4. **Existing-user invariant** — Pre-Phase-76 cookies authenticate; no `gbs_api_token` SQLite key.

Test 5 (automated portion): 1780 passed / 2 pre-existing failures (not Phase 76); 61/61 Phase 76 tests green; 3/4 grep gates clean + 1 documented Rule-3 deviation (audit comment).

## Requirements Coverage

| REQ | Description | Status | Evidence |
|-----|-------------|--------|----------|
| GBS-AUTH-01 | User can log in to GBS.FM via in-app subprocess | **satisfied** | All 4 live UAT scenarios + 61/61 automated tests; REQUIREMENTS.md L222 traceability row `Complete`; L124 checkbox `[x]` |

## Anti-Pitfall Source-Grep Gates

| Gate | Expected | Actual | Status |
|------|----------|--------|--------|
| `_emit_event` provider hardcode (`"provider": "twitch"`) | 0 | 0 | PASS — `_PROVIDER` constant pattern |
| `_on_gbs_login_finished` provider=twitch | 0 | 0 | PASS |
| `_on_gbs_login_finished` netscape strip | 0 | 0 | PASS |
| Test asserts old `"Import GBS.FM Cookies..."` button text | 0 | 1 | DEVIATION (documented — Plan 76-04 audit comment per `feedback_mirror_decisions_cite_source.md`; not a test body assertion) |

## Out-of-Scope / Deferred

- **Token-paste auth path** — dropped per Phase 76 D-03 (Phase 60 + Phase 76 re-probe both confirmed 403/302 across all 8 auth vectors on `/api/vote`, `/ajax`, `/add/`, `/search`).

## Known Pre-Existing Failures (Not Phase 76)

- `tests/test_main_window_integration.py::test_hamburger_menu_actions` — Qt teardown noise; Phase 77 INFRA-01 scope.
- `tests/test_media_keys_smtc.py::test_end_to_end_factory_fallback_on_win32_without_winrt` — Windows-only test on Linux Wayland deployment target.
