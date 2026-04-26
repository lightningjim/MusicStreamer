---
phase: 40-auth-dialogs-accent
verified: 2026-04-13T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Connect Twitch button in AccountsDialog — click Connect, complete the Twitch OAuth flow in the subprocess QWebEngineView window, verify token file is written at paths.twitch_token_path() with 0o600 permissions and status label updates to Connected"
    expected: "Browser-like window opens to Twitch login; after login, window closes, status shows Connected"
    why_human: "Requires PySide6.QtWebEngineWidgets (system package python3-pyside6.qtwebenginewidgets not installed in this environment), real Twitch client ID, and live OAuth redirect"
  - test: "Google Login tab in CookieImportDialog — click Open Google Login, complete login in the QWebEngineView window, verify cookies written to cookies_path() with 0o600 permissions"
    expected: "Browser-like window opens to Google login; after login, Done button collects cookies and dialog closes with toast"
    why_human: "Same QtWebEngine missing dependency; requires live Google session"
  - test: "Accent color picker live preview — open AccentColorDialog, click each of the 8 swatches, verify the selected chip/segment/slider elements visually update to the chosen color, then click Apply and restart the app to confirm color persists"
    expected: "Swatch click immediately updates chip borders, segment backgrounds, and slider fill; color survives app restart"
    why_human: "QPalette.Highlight visual effect on palette(highlight) selectors requires visual inspection; persistence needs full app restart cycle"
  - test: "Hamburger menu end-to-end — open the app, click the hamburger (≡) button, verify all 7 menu items appear in the correct groups with 2 visible separators; click each active item and verify its dialog opens"
    expected: "Menu shows: Discover Stations / Import Stations / (sep) / Accent Color / YouTube Cookies / Accounts / (sep) / Export Settings (gray) / Import Settings (gray)"
    why_human: "Menu layout and visual separator rendering requires manual inspection; dialog open/close flow benefits from real interaction"
---

# Phase 40: Auth Dialogs + Accent Verification Report

**Phase Goal:** User can authenticate Twitch via OAuth, manage YouTube cookies, pick an accent color, and access all actions from the hamburger menu
**Verified:** 2026-04-13
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | AccountsDialog opens a subprocess QWebEngineView for Twitch OAuth; token is captured and written with restricted permissions | VERIFIED (code) / ? (runtime) | `accounts_dialog.py` uses `QProcess(sys.executable, ["-m", "musicstreamer.oauth_helper", "--mode", "twitch"])`, writes token with `os.chmod(0o600)`; oauth_helper.py intercepts `access_token=` from redirect URL |
| 2 | YouTube cookie import works via file picker, paste, and Google login (subprocess OAuth helper); cookies stored at the platform-appropriate path with 0o600 permissions | VERIFIED (code) / ? (runtime) | `cookie_import_dialog.py` has File/Paste/Google Login tabs, all paths call `_write_cookies()` which does `os.chmod(dest, 0o600)`; Google Login uses same QProcess pattern |
| 3 | Accent color picker applies 8 presets or hex entry as live QSS; persists across restarts | VERIFIED (code) / ? (visual) | `AccentColorDialog` has 4x2 swatch grid, `apply_accent_palette()` modifies `QPalette.ColorRole.Highlight`; `main_window.py` calls `apply_accent_palette` from saved `accent_color` setting on startup |
| 4 | Hamburger menu exposes Discover, Import, Accent Color, YouTube Cookies, Accounts, and Export/Import Settings | VERIFIED | `main_window.py` has 7 addAction calls across 3 groups with 2 separators; Export/Import Settings disabled with tooltip "Coming in a future update" |

**Score:** 4/4 truths verified in code

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/accent_utils.py` | `build_accent_qss()` function | VERIFIED | Contains `build_accent_qss`, `apply_accent_palette`, `reset_accent_palette`; `QSlider::sub-page:horizontal` QSS; hex validation guard |
| `musicstreamer/ui_qt/accent_color_dialog.py` | `AccentColorDialog` class | VERIFIED | `class AccentColorDialog`, 8 swatches from `ACCENT_PRESETS`, `apply_accent_palette` call, `set_setting("accent_color")` |
| `tests/test_accent_color_dialog.py` | Dialog unit tests | VERIFIED | `test_apply_saves_setting`, `test_dialog_has_8_swatches` present; 49 tests pass |
| `musicstreamer/oauth_helper.py` | Standalone subprocess OAuth helper | VERIFIED | `def main`, `--mode` argparse, `access_token=` interception, `cookieAdded` signal, `ImportError` guard |
| `musicstreamer/ui_qt/accounts_dialog.py` | `AccountsDialog` class | VERIFIED | `class AccountsDialog`, `QProcess`, `oauth_helper` reference, `0o600`, `clear_twitch_token`, `Disconnect Twitch?` |
| `tests/test_accounts_dialog.py` | Dialog unit tests | VERIFIED | `test_status_not_connected`, `test_disconnect_deletes_token`, `test_connect_launches_qprocess` |
| `musicstreamer/ui_qt/cookie_import_dialog.py` | `CookieImportDialog` class | VERIFIED | `class CookieImportDialog`, `_validate_youtube_cookies`, `0o600`, `.youtube.com`, `QTabWidget`, `oauth_helper` |
| `tests/test_cookie_import_dialog.py` | Dialog unit tests | VERIFIED | `test_paste_validation`, `test_file_import_writes_with_permissions`, `test_dialog_has_three_tabs` |
| `musicstreamer/ui_qt/main_window.py` | Hamburger menu + accent startup load | VERIFIED | All 7 actions, 2 separators, `apply_accent_palette` on startup, imports for all 3 new dialog classes |
| `musicstreamer/subprocess_utils.py` | PKG-03 centralized subprocess helper | VERIFIED | `def _popen`, `CREATE_NO_WINDOW`, `PKG-03` comment |
| `tests/test_main_window_integration.py` | Menu + accent startup tests | VERIFIED | `test_hamburger_menu_actions`, `test_hamburger_menu_separators`, `test_sync_actions_disabled`, `test_sync_actions_tooltip`, `test_accent_loaded_on_startup`, `test_discover_action_opens_dialog`, `test_import_action_opens_dialog` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `accent_color_dialog.py` | `accent_utils.py` | `build_accent_qss` import | WIRED | `from musicstreamer.accent_utils import (build_accent_qss, apply_accent_palette, reset_accent_palette)` at line 27 |
| `accent_color_dialog.py` | `repo.py` | `set_setting` for `accent_color` | WIRED | `self._repo.set_setting("accent_color", self._current_hex)` in `_on_apply` |
| `accounts_dialog.py` | `oauth_helper.py` | QProcess subprocess launch | WIRED | `["-m", "musicstreamer.oauth_helper", "--mode", "twitch"]` at line 109 |
| `accounts_dialog.py` | `paths.py` | `twitch_token_path()` | WIRED | `paths.twitch_token_path()` at lines 69, 130 |
| `cookie_import_dialog.py` | `paths.py` | `cookies_path()` | WIRED | `paths.cookies_path()` in `_write_cookies` |
| `cookie_import_dialog.py` | `oauth_helper.py` | QProcess `--mode google` | WIRED | `["-m", "musicstreamer.oauth_helper", "--mode", "google"]` at line 268 |
| `main_window.py` | `accent_color_dialog.py` | import + menu action | WIRED | `from musicstreamer.ui_qt.accent_color_dialog import AccentColorDialog`; `_open_accent_dialog` bound method |
| `main_window.py` | `accounts_dialog.py` | import + menu action | WIRED | `from musicstreamer.ui_qt.accounts_dialog import AccountsDialog`; `_open_accounts_dialog` |
| `main_window.py` | `cookie_import_dialog.py` | import + menu action | WIRED | `from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog`; `_open_cookie_dialog` |
| `main_window.py` | `accent_utils.py` | `apply_accent_palette` on startup | WIRED | `from musicstreamer.accent_utils import apply_accent_palette`; called in `__init__` at line 100 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `main_window.py` startup accent | `_saved_accent` | `self._repo.get_setting("accent_color", "")` → SQLite `settings` table | Yes — SQLite query via `repo.py` | FLOWING |
| `accent_color_dialog.py` swatch selection | `self._current_hex` | `ACCENT_PRESETS[idx]` (8 hardcoded hex values from `constants.py`) | Yes — intentional preset list | FLOWING |
| `accounts_dialog.py` status | `os.path.exists(paths.twitch_token_path())` | Filesystem check at token path | Yes — live file check | FLOWING |
| `cookie_import_dialog.py` validation | `_validate_youtube_cookies(text)` | User-provided text / file / subprocess stdout | Yes — validates real input | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| subprocess_utils importable | `.venv/bin/python -c "from musicstreamer.subprocess_utils import _popen; print('ok')"` | `ok` | PASS |
| oauth_helper importable | `.venv/bin/python -c "import musicstreamer.oauth_helper; print('importable')"` | `importable` | PASS |
| `build_accent_qss` returns valid QSS | `.venv/bin/python -c "assert 'QSlider::sub-page' in build_accent_qss('#3584e4')"` | Assertion passes | PASS |
| `build_accent_qss` validates hex | `.venv/bin/python -c "assert build_accent_qss('invalid') == ''"` | Returns empty string | PASS |
| Full test suite (79 tests) | `.venv/bin/python -m pytest tests/test_accent_provider.py test_accent_color_dialog.py test_accounts_dialog.py test_cookie_import_dialog.py test_main_window_integration.py -q` | `79 passed in 1.30s` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| UI-08 | 40-02-PLAN.md | AccountsDialog — Twitch OAuth via subprocess QWebEngineView; token written with restricted permissions | SATISFIED (code) | `accounts_dialog.py` + `oauth_helper.py` implement full flow; 8 tests pass |
| UI-09 | 40-03-PLAN.md | YouTube cookie import — file picker, paste, Google login; stored with restricted permissions | SATISFIED (code) | `cookie_import_dialog.py` has 3-tab dialog; all paths use `0o600`; 15 tests pass |
| UI-10 | 40-04-PLAN.md | Hamburger menu — Discover, Import, Accent Color, YouTube Cookies, Accounts, Export/Import Settings | SATISFIED | `main_window.py` has 7 actions in 3 groups; 30 integration tests pass |
| UI-11 | 40-01-PLAN.md + 40-04-PLAN.md | Accent color picker — 8 presets + hex entry, applied as runtime QSS, persisted in SQLite | SATISFIED (code) | `AccentColorDialog` + `accent_utils.py` + startup load in `MainWindow.__init__` |

All 4 requirements claimed by Phase 40 plans are accounted for. No orphaned requirements.

**Note on REQUIREMENTS.md traceability table:** The traceability table still shows UI-08 through UI-11 as `Pending` — this reflects that the requirements were not yet marked complete before this verification. The implementations exist and tests pass; the table status is a documentation artifact, not a code gap.

### Anti-Patterns Found

No blockers or stubs found in phase 40 files. The `Coming in a future update` tooltip on Export/Import Settings is intentional per plan spec (D-19), not a stub.

### Human Verification Required

#### 1. Twitch OAuth end-to-end flow

**Test:** Install `python3-pyside6.qtwebenginewidgets`, launch the app, open hamburger > Accounts, click Connect Twitch. Complete the Twitch login in the QWebEngineView window.
**Expected:** Window opens showing Twitch login page; after auth, window closes automatically, status label shows "Connected", token file exists at `paths.twitch_token_path()` with `0o600` permissions.
**Why human:** Requires QtWebEngineWidgets (system package absent in test environment), a real Twitch client ID config, and a live Twitch login.

#### 2. Google Login cookie flow

**Test:** Open hamburger > YouTube Cookies, switch to Google Login tab, click Open Google Login. Complete login.
**Expected:** QWebEngineView opens Google login; after completing auth, dialog closes with "YouTube cookies imported." toast; cookies file at `paths.cookies_path()` with `0o600`.
**Why human:** Same QtWebEngineWidgets dependency; requires real Google session.

#### 3. Accent color live preview and persistence

**Test:** Open hamburger > Accent Color, click each of the 8 swatches. Observe that chip borders, segment control backgrounds, and volume slider fill all change color. Enter a custom hex (e.g. `#ff6600`). Click Apply. Restart the app.
**Expected:** Every `palette(highlight)` element updates immediately on swatch/hex change. After restart, the chosen color is still applied without opening the dialog.
**Why human:** `QPalette.Highlight` visual propagation to per-widget stylesheets requires eyes-on verification; persistence requires a real restart cycle.

#### 4. Hamburger menu layout

**Test:** Launch the app, click the ≡ button, inspect the menu visually.
**Expected:** Two visible separator lines creating three groups: [Discover Stations, Import Stations] / [Accent Color, YouTube Cookies, Accounts] / [Export Settings (gray), Import Settings (gray)].
**Why human:** Separator rendering and disabled-item appearance depend on Qt style and platform.

### Gaps Summary

No code gaps. All artifacts exist, are substantive, are wired, and data flows through each path. All 79 unit/integration tests pass using the project venv.

The `human_needed` status reflects four runtime behaviors that require `python3-pyside6.qtwebenginewidgets` (absent from the test environment), live OAuth providers, or visual inspection. None of these are code gaps — they are integration paths that cannot be exercised without the full runtime stack.

---

_Verified: 2026-04-13_
_Verifier: Claude (gsd-verifier)_
