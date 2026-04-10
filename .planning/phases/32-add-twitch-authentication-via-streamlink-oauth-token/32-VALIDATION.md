---
phase: 32
slug: add-twitch-authentication-via-streamlink-oauth-token
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 32 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pyproject.toml |
| **Quick run command** | `pytest tests/test_twitch_auth.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~3 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_twitch_auth.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 32-01-01 | 01 | 0 | — | — | N/A | unit | `pytest tests/test_twitch_auth.py -x -q` | ❌ W0 | ⬜ pending |
| 32-01-02 | 01 | 1 | — | T-32-01 | Token file 0o600 permissions | unit | `pytest tests/test_twitch_auth.py::test_twitch_token_path_constant -x -q` | ❌ W0 | ⬜ pending |
| 32-01-03 | 01 | 1 | — | — | N/A | unit | `pytest tests/test_twitch_auth.py::test_clear_twitch_token_removes_file -x -q` | ❌ W0 | ⬜ pending |
| 32-01-04 | 01 | 1 | — | — | N/A | unit | `pytest tests/test_twitch_auth.py::test_play_twitch_includes_auth_header -x -q` | ❌ W0 | ⬜ pending |
| 32-01-05 | 01 | 1 | — | — | N/A | unit | `pytest tests/test_twitch_auth.py::test_play_twitch_no_header_when_absent -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_twitch_auth.py` — stubs for all Twitch auth behaviors (constant, clear, player header injection)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| WebKit2 Twitch login flow works | D-01 | Requires live Twitch account + WebKit runtime | 1. Open Accounts dialog 2. Click Twitch tab 3. Click "Log in to Twitch" 4. Complete login 5. Verify status shows "Logged in" |
| Authenticated stream has no pre-roll ads | D-02 | Requires live Twitch channel + audio | 1. Log in via Accounts 2. Play a live Twitch channel 3. Verify no pre-stream promo |
| Log out clears token and updates status | D-07 | Requires UI interaction | 1. While logged in, click "Log out" 2. Verify status changes to "Not logged in" 3. Verify token file deleted |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
