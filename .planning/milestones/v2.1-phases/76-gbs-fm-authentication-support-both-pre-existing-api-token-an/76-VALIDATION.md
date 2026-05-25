---
phase: 76
slug: gbs-fm-authentication-support-both-pre-existing-api-token-an
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-16
---

# Phase 76 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `python -m pytest tests/test_oauth_helper.py tests/test_accounts_dialog.py -x -q` |
| **Full suite command** | `python -m pytest -x` |
| **Estimated runtime** | ~10 s quick · ~45 s full |

---

## Sampling Rate

- **After every task commit:** Run quick command (oauth_helper + accounts_dialog tests)
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 s (quick), 45 s (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | GBS-AUTH-01 | T-76-* | Filled by planner | unit/integration | filled by planner | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*This table is a stub. Planner populates rows from PLAN.md tasks; auditor verifies each row maps to either an `<automated>` block or a Wave 0 stub.*

---

## Wave 0 Requirements

- [ ] `tests/test_oauth_helper.py` — new module (if not exists) — stubs for `--mode gbs` argparse + `_GbsLoginWindow` + cookie-trigger fixtures (GBS-AUTH-01)
- [ ] `tests/test_accounts_dialog.py` — extend existing — stubs for 2-state GBS status enumeration + subprocess launch/finished + Disconnect-clears-cookies
- [ ] `tests/fixtures/oauth_helper/` — if not exists — gbs cookie payload fixtures (sessionid + csrftoken Netscape dumps)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Critical-Path Validations (from RESEARCH.md §Validation Architecture)

Per RESEARCH.md §Validation Architecture — these four validations gate phase verification:

1. **D-03 verdict locked** — RESEARCH.md §VERDICT block unambiguously selects D-03 (subprocess-only). No `gbs_api.py` `AuthContext` work, no inline token row in `AccountsDialog`, no `gbs_api_token` SQLite key. *Verified by:* PLAN.md scope matches D-03 collapse; planner exit gate.
2. **`_GbsLoginWindow` cookie-detection trigger** — Cookie-added handler fires only when BOTH `sessionid` AND `csrftoken` are observed on `gbs.fm` / `.gbs.fm` / `*.gbs.fm`. Lookalike domains (`fakegbs.fm`, `gbs.fm.evil.com`) MUST NOT trigger. *Verified by:* `tests/test_oauth_helper.py::test_gbs_cookie_trigger_*` (positive + negative domain cases).
3. **Netscape output format** — `_GbsLoginWindow._flush_cookies` produces output that `gbs_api._validate_gbs_cookies` accepts (sessionid + csrftoken + gbs.fm domain). *Verified by:* `tests/test_oauth_helper.py::test_gbs_flush_validates` (round-trip test).
4. **Disconnect clears cookies file** — `AccountsDialog._on_gbs_action_clicked` disconnect branch deletes `paths.gbs_cookies_path()` with broader-OSError tolerance. (Token half removed by D-03 — only cookies file is cleared.) *Verified by:* `tests/test_accounts_dialog.py::test_gbs_disconnect_clears_cookies`.

Anti-pitfall validation (RESEARCH.md anti-pitfall): `oauth_helper._emit_event` provider hardcoding refactor (`_PROVIDER` module-level constant) MUST NOT break existing Twitch tests. *Verified by:* `tests/test_oauth_helper.py` full pass before/after refactor.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real gbs.fm login flow | GBS-AUTH-01 | Requires real Django session + WebEngine GUI + live network | 1. Launch app. 2. Open Accounts dialog. 3. Click `[Connect with GBS.FM…]`. 4. Subprocess WebView opens `gbs.fm/accounts/login/`. 5. Log in with real credentials. 6. Window auto-closes; status flips to `Connected (cookies)`. 7. Verify `~/.local/share/musicstreamer/gbs-cookies.txt` written with 0o600. 8. Click `[Disconnect]` → confirm dialog → cookies file removed; status `Not connected`. |
| 120 s timeout path | GBS-AUTH-01 | Requires real user interaction (user does NOT log in within 120 s) | 1. Click `[Connect with GBS.FM…]`. 2. Wait 120 s without logging in. 3. Subprocess emits `LoginTimeout` category. 4. AccountsDialog shows category-aware failure dialog with inline Retry. |
| Phase 999.3 failure UI provider-agnostic re-use | GBS-AUTH-01 | Provider-agnostic by design; verify visually that no Twitch-specific copy leaks into GBS failure dialog | After triggering any `_emit_event` failure mode for GBS, confirm dialog title/body says "GBS" not "Twitch" (regression check for `_PROVIDER` constant refactor). |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10 s (quick), 45 s (full)
- [ ] `_emit_event` provider refactor leaves existing Twitch tests green
- [ ] `nyquist_compliant: true` set in frontmatter after planner populates the per-task table

**Approval:** pending
