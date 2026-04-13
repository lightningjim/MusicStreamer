---
phase: 40
slug: auth-dialogs-accent
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-13
---

# Phase 40 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-qt |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` |
| **Quick run command** | `python -m pytest tests/test_accounts_dialog.py tests/test_cookie_import_dialog.py tests/test_accent_color_dialog.py -x` |
| **Full suite command** | `python -m pytest --ignore=tests/test_yt_import_library.py` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 40-01-01 | 01 | 1 | UI-10 | — | N/A | unit | `pytest tests/test_main_window_integration.py -x` | Partial | ⬜ pending |
| 40-02-01 | 02 | 1 | UI-11 | — | N/A | unit | `pytest tests/test_accent_color_dialog.py -x` | ❌ W0 | ⬜ pending |
| 40-03-01 | 03 | 1 | UI-08 | — | Token 0o600 perms | unit | `pytest tests/test_accounts_dialog.py -x` | ❌ W0 | ⬜ pending |
| 40-04-01 | 04 | 1 | UI-09 | — | Cookie 0o600 perms | unit | `pytest tests/test_cookie_import_dialog.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_accounts_dialog.py` — stubs for UI-08 (mock QProcess, test status display + disconnect)
- [ ] `tests/test_cookie_import_dialog.py` — stubs for UI-09 (file/paste import, validation)
- [ ] `tests/test_accent_color_dialog.py` — stubs for UI-11 (apply/reset, preset selection)
- [ ] Add hamburger menu tests to `tests/test_main_window_integration.py`
- [ ] Add `test_build_accent_qss` to existing accent test file

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Twitch OAuth flow end-to-end | UI-08 | Requires real Twitch credentials + browser interaction | Open Accounts, click Connect, complete OAuth, verify token written |
| Google Login cookie extraction | UI-09 | Requires real Google credentials + QWebEngine subprocess | Open Cookie Import, click Google Login, complete login, verify cookies written |
| Live QSS accent preview | UI-11 | Visual color change requires human eye | Open Accent Color, click a preset, verify UI color changes in real-time |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
