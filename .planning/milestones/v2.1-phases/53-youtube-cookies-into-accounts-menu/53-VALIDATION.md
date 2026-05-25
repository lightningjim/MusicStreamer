---
phase: 53
slug: youtube-cookies-into-accounts-menu
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-28
---

# Phase 53 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-qt (existing project setup) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run --with pytest --with pytest-qt pytest tests/test_accounts_dialog.py tests/test_main_window_integration.py -x -q` |
| **Full suite command** | `uv run --with pytest --with pytest-qt pytest -q` |
| **Estimated runtime** | ~30s (quick), ~3min (full) |

---

## Sampling Rate

- **After every task commit:** Run quick (`pytest tests/test_accounts_dialog.py tests/test_main_window_integration.py -x -q`)
- **After every plan wave:** Run full suite (`pytest -q`)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds (quick) / 3 minutes (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 53-01-W0 | 01 | 1 | BUG-04 / SC-2 | T-40-04 | YouTube status label uses Qt.TextFormat.PlainText | wave-0 | `grep -n "setTextFormat(Qt.TextFormat.PlainText)" musicstreamer/ui_qt/accounts_dialog.py \| wc -l` should yield ≥3 | ❌ W0 | ⬜ pending |
| 53-01-01 | 01 | 1 | BUG-04 / SC-2 | — | YouTube QGroupBox titled "YouTube" present in AccountsDialog | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_youtube_group_present -x` | ❌ W0 | ⬜ pending |
| 53-01-02 | 01 | 1 | BUG-04 / SC-2 | — | Status label reads "Not connected" when cookies.txt missing | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_status_not_connected -x` | ❌ W0 | ⬜ pending |
| 53-01-03 | 01 | 1 | BUG-04 / SC-2 | — | Status label reads "Connected" when cookies.txt exists | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_status_connected -x` | ❌ W0 | ⬜ pending |
| 53-01-04 | 01 | 1 | BUG-04 / SC-2 | — | Action button label is "Import YouTube Cookies..." when not connected | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_button_label_not_connected -x` | ❌ W0 | ⬜ pending |
| 53-01-05 | 01 | 1 | BUG-04 / SC-2 | — | Action button label is "Disconnect" when connected | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_button_label_connected -x` | ❌ W0 | ⬜ pending |
| 53-01-06 | 01 | 1 | BUG-04 / SC-2 | — | Click "Import..." → CookieImportDialog constructed with forwarded toast | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_import_launches_cookie_dialog -x` | ❌ W0 | ⬜ pending |
| 53-01-07 | 01 | 1 | BUG-04 / SC-2 | — | After Accepted exec, _update_status re-runs → flips to "Connected" | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_post_import_refreshes_status -x` | ❌ W0 | ⬜ pending |
| 53-01-08 | 01 | 1 | BUG-04 / SC-2 | — | After Rejected exec, _update_status still called (idempotent) | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_post_cancel_status_unchanged -x` | ❌ W0 | ⬜ pending |
| 53-01-09 | 01 | 1 | BUG-04 / SC-2 | — | Disconnect → Yes → os.remove(cookies_path) + status refresh | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_disconnect_removes_cookies -x` | ❌ W0 | ⬜ pending |
| 53-01-10 | 01 | 1 | BUG-04 / SC-2 | — | Disconnect → No → cookies file untouched | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_disconnect_cancel_keeps_cookies -x` | ❌ W0 | ⬜ pending |
| 53-01-11 | 01 | 1 | BUG-04 / SC-2 | — | Disconnect handles FileNotFoundError gracefully (race) | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_disconnect_file_already_gone -x` | ❌ W0 | ⬜ pending |
| 53-01-12 | 01 | 1 | BUG-04 / SC-2 | — | Disconnect does NOT touch Twitch token or AA key | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_disconnect_isolates_youtube -x` | ❌ W0 | ⬜ pending |
| 53-01-13 | 01 | 1 | BUG-04 / SC-3 | — | Group order is [YouTube, Twitch, AudioAddict] | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_group_order -x` | ❌ W0 | ⬜ pending |
| 53-02-01 | 02 | 2 | BUG-04 / SC-1 | — | EXPECTED_ACTION_TEXTS length 9, "YouTube Cookies" absent | unit | `pytest tests/test_main_window_integration.py::test_hamburger_menu_actions -x` | ✅ exists | ⬜ pending |
| 53-02-02 | 02 | 2 | BUG-04 / SC-1 | — | Hamburger separator count remains 3 | unit | `pytest tests/test_main_window_integration.py::test_hamburger_menu_separators -x` | ✅ exists | ⬜ pending |
| 53-02-03 | 02 | 2 | BUG-04 / SC-3 | — | _open_accounts_dialog passes show_toast as toast_callback | unit | `pytest tests/test_main_window_integration.py::test_open_accounts_passes_toast -x` | ❌ W0 | ⬜ pending |
| 53-02-04 | 02 | 2 | BUG-04 / SC-1 | — | _open_cookie_dialog method removed from MainWindow | unit | `grep -n "_open_cookie_dialog" musicstreamer/ui_qt/main_window.py` returns no matches | ✅ grep | ⬜ pending |
| 53-02-05 | 02 | 2 | BUG-04 / SC-1 | — | CookieImportDialog import removed from main_window.py | unit | `grep -n "from musicstreamer.ui_qt.cookie_import_dialog" musicstreamer/ui_qt/main_window.py` returns no matches | ✅ grep | ⬜ pending |
| 53-R-01 | * | * | regression | — | Existing 24 AccountsDialog(fake_repo) test sites still pass | regression | `pytest tests/test_accounts_dialog.py -x` | ✅ existing | ⬜ pending |
| 53-R-02 | * | * | regression | — | Existing CookieImportDialog test suite passes unchanged | regression | `pytest tests/test_cookie_import_dialog.py -x` | ✅ existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] **NEW class `TestAccountsDialogYouTube` in `tests/test_accounts_dialog.py`** — covers SC-2/SC-3 invariants (13 unit tests). Add as new class; do NOT touch existing 24 construction sites.
- [ ] **NEW test `test_open_accounts_passes_toast` in `tests/test_main_window_integration.py`** — patches AccountsDialog constructor with MagicMock to verify D-14 kwarg wiring. ~10 lines.
- [x] `tests/test_accounts_dialog.py::FakeRepo` — already exists, reusable as-is
- [x] `tests/test_accounts_dialog.py::tmp_data_dir` fixture — already redirects `paths._root_override`; reusable for `cookies_path()` testing
- [x] pytest-qt `qtbot` and `qapp` — already integrated

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end Google Login → cookies imported → toast → Connected → Disconnect → confirm Yes → Not connected | BUG-04 / SC-2 | Google Login subprocess opens a real browser window — automation requires WebKit harness, out of scope for this phase | 1) Open Accounts from hamburger menu. 2) YouTube row shows "Not connected" + "Import YouTube Cookies...". 3) Click → CookieImportDialog opens. 4) Choose Google Login tab → Open Google Login → complete login. 5) Toast "YouTube cookies imported." appears. 6) AccountsDialog now shows "Connected" + "Disconnect". 7) Click Disconnect → Yes. 8) Status flips to "Not connected". |
| Visual verification of "no crowding" | BUG-04 / SC-3 | Subjective visual check | Open Accounts dialog. Confirm three groups (YouTube, Twitch, AudioAddict in that order) read cleanly with no widget overlap, sufficient spacing, all text legible at default font sizes. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (quick) / 3min (full)
- [ ] `nyquist_compliant: true` set in frontmatter (set by planner once Wave 0 lands)

**Approval:** pending
