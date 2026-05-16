# Phase 76: GBS.FM authentication (subprocess-only, post-D-03) - Pattern Map

**Mapped:** 2026-05-16
**Files analyzed:** 4 in-scope (2 source + 2 test)
**Analogs found:** 4 / 4 (all exact mirrors inside `musicstreamer/oauth_helper.py` + `musicstreamer/ui_qt/accounts_dialog.py`)
**Scope verdict:** D-03 FIRES — Phase 76 collapses to subprocess-only. `gbs_api.py`, `AuthContext`, inline token row, 4-state status, and `tests/test_gbs_api.py` are **OUT OF SCOPE** and are NOT pattern-mapped here.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/oauth_helper.py` (MODIFY) | subprocess helper / QWebEngine cookie-harvester | event-driven (`cookieAdded` signal) → stdout (Netscape dump) + stderr (JSON-line) | `_TwitchCookieWindow` at lines 108-192 (same file) | **exact** — D-05 locks Twitch clone |
| `musicstreamer/ui_qt/accounts_dialog.py` (MODIFY) | Qt dialog / subprocess orchestrator | request-response (QProcess finished → file write) | `_on_action_clicked` + `_launch_oauth_subprocess` + `_on_oauth_finished` (Twitch trio at lines 243-259, 332-341, 361-458) | **exact** — D-05/D-09/D-14 mirror Twitch |
| `tests/test_oauth_helper.py` (NEW or EXTEND) | unit test | mock `QNetworkCookie` + `capsys` for stderr | `tests/test_oauth_helper_twitch.py` (entire file, 154 lines) | **exact** — clone shape with provider="gbs" substitution |
| `tests/test_accounts_dialog.py` (MODIFY — extend `TestAccountsDialogGBS`) | unit test | `MagicMock(spec=QProcess)` + `_mock_proc_with_stderr` helper | `TestAccountsDialogOAuthFinished` at lines 196-251 + existing `TestAccountsDialogGBS` at lines 886-1020 | **exact** |

---

## Project Conventions (apply to ALL files below)

These are not file-specific patterns; they apply repository-wide and the planner MUST cite them in every plan that touches a new connection / signal / write.

| Convention | Origin | Application in Phase 76 |
|-----------|--------|-------------------------|
| **Bound-method signal connections, no self-capturing lambdas** | QA-05 | Every new `clicked.connect` / `finished.connect` in `accounts_dialog.py` connects to `self._on_xxx` (NOT `lambda: self._on_xxx(arg)`). |
| **`Qt.TextFormat.PlainText` on every QLabel showing user-visible text** | T-40-04 | Already enforced on `_gbs_status_label` (line 109) — keep when re-writing the status branch. New title/detail labels in any new failure dialog must set this too. |
| **snake_case + type hints throughout, no formatter** | `.planning/codebase/CONVENTIONS.md` | All new helpers (`_GbsLoginWindow`, `_cookie_domain_matches_gbs`, `_launch_gbs_login_subprocess`, `_on_gbs_login_finished`) use snake_case and full type hints. |
| **Pure `urllib`, no SDK for HTTP clients** | project convention | N/A under D-03 (no new HTTP — subprocess uses QWebEngine; no `gbs_api.py` changes). |
| **0o600 file mode for sensitive data** | Phase 999.7 invariant | `_on_gbs_login_finished` MUST `os.chmod(0o600)` the cookies file after writing — verbatim mirror of `cookie_import_dialog.py:340` and `accounts_dialog.py:409`. |
| **Tokens/cookie VALUES NEVER logged** | `oauth_helper.py:75-77` docstring | `_emit_event(category, detail=...)` callers in `_GbsLoginWindow` pass enum-like short strings (`"120s"`, `"empty_auth_token"`, `"cookie_decode_error"`) — NEVER cookie values, NEVER URL fragments. |
| **Single-user scope** | `project_single_user_scope.md` | One cookies file (`paths.gbs_cookies_path()`); no multi-account branching. |

---

## Pattern Assignments

### File 1: `musicstreamer/oauth_helper.py` (MODIFY — add `_GbsLoginWindow` + extend `main()` + refactor `_emit_event`)

**Role:** subprocess helper class
**Data flow:** event-driven (QWebEngine `cookieAdded` signal) → success path writes Netscape dump to stdout + JSON-line "Success" to stderr; failure paths write JSON-line "LoginTimeout" / "WindowClosedBeforeLogin" / "SubprocessCrash" to stderr.
**Analog:** `_TwitchCookieWindow` at `musicstreamer/oauth_helper.py:108-192` (same file). Direct structural clone with **three substitutions**: URL constant, trigger cookie set, output format.
**Secondary analog:** `_GoogleWindow._flush_cookies` at `musicstreamer/oauth_helper.py:259-264` for the Netscape-dump output shape.

---

#### Excerpt 1A — `_TwitchCookieWindow` (PRIMARY MIRROR — `oauth_helper.py:108-192`, full class verbatim)

> **CITED:** `musicstreamer/oauth_helper.py:108-192`. Per project memory `feedback_mirror_decisions_cite_source.md`, this is the verbatim source — no paraphrase. The planner MUST clone this shape and apply exactly the three substitutions documented after the excerpt.

```python
class _TwitchCookieWindow(QMainWindow):
    """Log in to twitch.tv; capture the auth-token cookie streamlink needs.

    Uses QWebEngineCookieStore.cookieAdded — the same pattern as _GoogleWindow —
    but auto-completes as soon as the auth-token cookie is observed (no "Done"
    button). The auth-token cookie is set by twitch.tv the moment the login
    form completes successfully.
    """

    _TIMEOUT_MS = 120_000  # 120s login deadline

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Twitch Login")
        self.resize(800, 600)
        self._finished = False

        self._view = QWebEngineView(self)
        self.setCentralWidget(self._view)

        # Session-only cookies — never persist to disk in the subprocess profile.
        profile = self._view.page().profile()
        profile.setPersistentCookiesPolicy(
            profile.PersistentCookiesPolicy.NoPersistentCookies  # type: ignore[attr-defined]
        )
        # Belt-and-suspenders UA override at the profile level.
        # Primary UA override is the --user-agent Chromium flag set at module
        # import time (above); this profile-level call keeps the two in sync
        # so any later page() → profile() inspection shows the same string.
        profile.setHttpUserAgent(_CHROME_UA)
        cookie_store = profile.cookieStore()
        cookie_store.cookieAdded.connect(self._on_cookie_added)

        self._view.load(QUrl(_TWITCH_LOGIN_URL))

        # Login timeout watchdog.
        QTimer.singleShot(self._TIMEOUT_MS, self._on_timeout)

    def _on_cookie_added(self, cookie: QNetworkCookie) -> None:
        if self._finished:
            return
        try:
            name = str(cookie.name(), "utf-8")
        except Exception:
            return
        if name != _TWITCH_AUTH_COOKIE:
            return
        if not _cookie_domain_matches(cookie):
            return
        try:
            value = str(cookie.value(), "utf-8").strip()
        except Exception:
            _emit_event("InvalidTokenResponse", detail="cookie_decode_error")
            self._finish(1)
            return
        if not value:
            # Empty cookie value — treat as invalid.
            _emit_event("InvalidTokenResponse", detail="empty_auth_token")
            self._finish(1)
            return
        # Success: stdout contract = raw token, no newline (matches Google path
        # and what AccountsDialog._on_oauth_finished expects).
        sys.stdout.write(value)
        sys.stdout.flush()
        _emit_event("Success", detail="")
        self._finish(0)

    def _on_timeout(self) -> None:
        if self._finished:
            return
        _emit_event("LoginTimeout", detail="120s")
        self._finish(1)

    def _finish(self, code: int) -> None:
        self._finished = True
        if code == 0:
            QApplication.quit()
        else:
            QApplication.exit(code)

    def closeEvent(self, event):  # noqa: N802
        if not self._finished:
            _emit_event("WindowClosedBeforeLogin", detail="")
            self._finish(1)
        super().closeEvent(event)
```

**Three substitutions for `_GbsLoginWindow` (per RESEARCH §_GbsLoginWindow Design lines 247-423):**

| # | Substitution | Twitch value | GBS value |
|---|--------------|--------------|-----------|
| 1 | Login URL constant | `_TWITCH_LOGIN_URL = "https://www.twitch.tv/login"` at line 93 | `_GBS_LOGIN_URL = "https://gbs.fm/accounts/login/"` (D-08 + RESEARCH §Login URL Resolution VERIFIED 2026-05-16 14:05 UTC) |
| 2 | Trigger cookie predicate | Single name check: `if name != _TWITCH_AUTH_COOKIE` (line 153) | Set-based: maintain `self._observed_names: set[str]`, trigger when `self._observed_names >= _GBS_TRIGGER_COOKIES` where `_GBS_TRIGGER_COOKIES = frozenset(("sessionid", "csrftoken"))` (D-06) |
| 3 | Output format | Raw token written via `sys.stdout.write(value)` (line 170) | Netscape dump per `_GoogleWindow._flush_cookies` shape — see Excerpt 1B below |

**Anti-pitfall: collect EVERY gbs.fm-domain cookie (not just the two trigger names).** Per RESEARCH lines 368-374, `_on_cookie_added` appends to `self._cookies` for every cookie passing the domain match; the trigger-name check only gates when to **flush**, not what to **collect**. This is forward-compat with auxiliary cookies (e.g. Django `messages`, future CSRF rotation) and matches what `_validate_gbs_cookies` already accepts.

**Verbatim `_GbsLoginWindow` design (RESEARCH §Output Format lines 338-423 — clone as-is into `oauth_helper.py`):**

```python
class _GbsLoginWindow(QMainWindow):
    """Mirror of _TwitchCookieWindow shape (oauth_helper.py:108-192).

    Trigger condition: both sessionid AND csrftoken observed on gbs.fm domain.
    Output: full Netscape dump of all gbs.fm-domain cookies (mirror _GoogleWindow).
    """
    _TIMEOUT_MS = 120_000  # 120s login deadline (mirror Twitch)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GBS.FM Login")
        self.resize(800, 600)
        self._finished = False
        self._cookies: list[QNetworkCookie] = []   # mirror _GoogleWindow:223
        self._observed_names: set[str] = set()

        self._view = QWebEngineView(self)
        self.setCentralWidget(self._view)

        profile = self._view.page().profile()
        profile.setPersistentCookiesPolicy(
            profile.PersistentCookiesPolicy.NoPersistentCookies  # type: ignore[attr-defined]
        )
        profile.setHttpUserAgent(_CHROME_UA)   # mirror Twitch's UA belt-and-braces
        cookie_store = profile.cookieStore()
        cookie_store.cookieAdded.connect(self._on_cookie_added)

        self._view.load(QUrl(_GBS_LOGIN_URL))
        QTimer.singleShot(self._TIMEOUT_MS, self._on_timeout)

    def _on_cookie_added(self, cookie: QNetworkCookie) -> None:
        if self._finished:
            return
        if not _cookie_domain_matches_gbs(cookie):
            return
        # Store every gbs.fm-domain cookie for forward-compat Netscape dump.
        self._cookies.append(cookie)
        try:
            name = str(cookie.name(), "utf-8")
        except Exception:
            return
        if name in _GBS_TRIGGER_COOKIES:
            self._observed_names.add(name)
            if self._observed_names >= _GBS_TRIGGER_COOKIES:
                # Both trigger cookies observed → flush + emit Success + exit 0.
                self._flush_cookies()

    def _flush_cookies(self) -> None:
        if self._finished:
            return
        lines = ["# Netscape HTTP Cookie File"]
        # Deduplicate by (domain, name) — same cookie can fire cookieAdded
        # multiple times if Django re-sends it. Keep last value.
        unique: dict[tuple[str, str], QNetworkCookie] = {}
        for c in self._cookies:
            try:
                name = str(c.name(), "utf-8")
            except Exception:
                continue
            unique[(c.domain(), name)] = c
        for c in unique.values():
            lines.append(_cookie_to_netscape(c))
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()
        _emit_event("Success", detail="")
        self._finish(0)

    def _on_timeout(self) -> None:
        if self._finished:
            return
        _emit_event("LoginTimeout", detail="120s")
        self._finish(1)

    def _finish(self, code: int) -> None:
        self._finished = True
        if code == 0:
            QApplication.quit()
        else:
            QApplication.exit(code)

    def closeEvent(self, event):  # noqa: N802
        if not self._finished:
            _emit_event("WindowClosedBeforeLogin", detail="")
            self._finish(1)
        super().closeEvent(event)
```

---

#### Excerpt 1B — `_GoogleWindow._flush_cookies` Netscape-output shape (`oauth_helper.py:259-264`)

> **CITED:** `musicstreamer/oauth_helper.py:259-264`. The Netscape-dump shape `_GbsLoginWindow._flush_cookies` mirrors — header line + one `_cookie_to_netscape(c)` line per cookie. The existing `_validate_gbs_cookies` (`gbs_api.py:116-141`) already accepts this exact shape; no validator changes.

```python
    def _flush_cookies(self) -> None:
        lines = ["# Netscape HTTP Cookie File"]
        for c in self._cookies:
            lines.append(_cookie_to_netscape(c))
        print("\n".join(lines), end="")
        QApplication.quit()
```

**Difference for Phase 76:** GBS variant uses `sys.stdout.write(...) + sys.stdout.flush()` (matches `_TwitchCookieWindow:170-171` style for explicit flush ordering before `_emit_event` and `_finish`), and adds a `dict[(domain, name)]` dedup pass before writing (Django can re-send the same cookie). See Excerpt 1A `_flush_cookies` for the merged shape.

---

#### Excerpt 1C — `_cookie_domain_matches` (PRIMARY MIRROR — `oauth_helper.py:95-105`)

> **CITED:** `musicstreamer/oauth_helper.py:95-105`. Clone-and-rename to `_cookie_domain_matches_gbs`; only the domain literals change. Rejects lookalikes (`fakegbs.fm`, `gbs.fm.evil.com`).

```python
def _cookie_domain_matches(cookie: QNetworkCookie) -> bool:
    """True if the cookie's domain is a Twitch domain we accept.

    Accepts: "twitch.tv", "www.twitch.tv", ".twitch.tv", or any "*.twitch.tv"
    subdomain. Rejects lookalikes like "faketwitch.tv" or "twitch.tv.evil.com".
    """
    domain = cookie.domain()
    if domain in ("twitch.tv", "www.twitch.tv", ".twitch.tv"):
        return True
    # "*.twitch.tv" — must have at least one additional label before ".twitch.tv"
    return domain.endswith(".twitch.tv")
```

**Adapted excerpt (per RESEARCH lines 315-325 — VERBATIM):**

```python
def _cookie_domain_matches_gbs(cookie: QNetworkCookie) -> bool:
    """True if the cookie's domain is a GBS.FM domain we accept.

    Accepts: "gbs.fm", "www.gbs.fm", ".gbs.fm", or any "*.gbs.fm" subdomain.
    Rejects lookalikes like "fakegbs.fm" or "gbs.fm.evil.com".
    """
    domain = cookie.domain()
    if domain in ("gbs.fm", "www.gbs.fm", ".gbs.fm"):
        return True
    return domain.endswith(".gbs.fm")
```

---

#### Excerpt 1D — `main()` argparse extension (`oauth_helper.py:276-299`)

> **CITED:** `musicstreamer/oauth_helper.py:276-299`. Phase 76 extends `choices=["twitch", "google"]` to include `"gbs"` and adds a third dispatch arm. Note that this is where the `_PROVIDER` global gets set per the `_emit_event` refactor (Excerpt 1E).

```python
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="musicstreamer.oauth_helper",
        description="Subprocess OAuth helper for MusicStreamer",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["twitch", "google"],
        help="OAuth mode: twitch (cookie-harvest) or google (YouTube cookies)",
    )
    args = parser.parse_args()

    # Create standalone QApplication — this is a separate process
    app = QApplication(sys.argv)

    if args.mode == "twitch":
        window: QMainWindow = _TwitchCookieWindow()
    else:
        window = _GoogleWindow()

    window.show()
    exit_code = app.exec()
    sys.exit(exit_code)
```

**Adapted excerpt for Phase 76 (per RESEARCH lines 461-468):**

```python
def main() -> None:
    global _PROVIDER
    parser = argparse.ArgumentParser(
        prog="musicstreamer.oauth_helper",
        description="Subprocess OAuth helper for MusicStreamer",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["twitch", "google", "gbs"],
        help="OAuth mode: twitch (cookie-harvest) or google/gbs (cookies)",
    )
    args = parser.parse_args()
    _PROVIDER = args.mode    # sets module-level provider used by _emit_event

    app = QApplication(sys.argv)

    if args.mode == "twitch":
        window: QMainWindow = _TwitchCookieWindow()
    elif args.mode == "gbs":
        window = _GbsLoginWindow()
    else:
        window = _GoogleWindow()

    window.show()
    exit_code = app.exec()
    sys.exit(exit_code)
```

---

#### Excerpt 1E — `_emit_event` ANTI-PITFALL (`oauth_helper.py:71-86`)

> **CITED:** `musicstreamer/oauth_helper.py:71-86`. RESEARCH §_emit_event Provider Field (lines 425-472) flagged this as an anti-pitfall: **the current implementation hardcodes `"provider": "twitch"`**. Without the refactor below, every `--mode gbs` event would carry `provider="twitch"` and the regression test `test_gbs_emits_provider_gbs_field` (RESEARCH line 780) would fail. The Twitch tests still pass because `main()` sets `_PROVIDER = "twitch"` first.

**Current implementation (verbatim):**

```python
def _emit_event(category: str, detail: str = "", **extra) -> None:
    """Emit a single JSON-line diagnostic event on stderr.

    Schema (fixed keys): {ts, category, detail, provider}.
    NEVER pass token values, cookie values, or URL fragments as `detail`.
    Callers pass short enum-like strings (e.g. "no_auth_token", "120s").
    """
    event = {
        "ts": time.time(),
        "category": category,
        "detail": detail,
        "provider": "twitch",
    }
    if extra:
        event.update(extra)
    print(json.dumps(event, separators=(",", ":")), file=sys.stderr, flush=True)
```

**Refactored implementation (RESEARCH lines 446-459 — VERBATIM, recommended option (a)):**

```python
# Add near top of oauth_helper.py (after _CHROME_UA constant ~line 48):
_PROVIDER = "twitch"   # default; overridden by main()

def _emit_event(category: str, detail: str = "", **extra) -> None:
    event = {
        "ts": time.time(),
        "category": category,
        "detail": detail,
        "provider": _PROVIDER,   # was hardcoded "twitch"
    }
    if extra:
        event.update(extra)
    print(json.dumps(event, separators=(",", ":")), file=sys.stderr, flush=True)
```

**Rationale (RESEARCH line 444):** minimal call-site churn; the Twitch tests asserting `"provider": "twitch"` still pass because `main()` sets `_PROVIDER = "twitch"` before any window is instantiated; the docstring `NEVER pass token values...` warning at lines 74-76 stays unchanged.

---

#### File 1 Summary Table — `oauth_helper.py` Action Items

| # | Action | Source location | New location / line range |
|---|--------|-----------------|---------------------------|
| 1 | Add `_PROVIDER = "twitch"` module constant | new | after `_CHROME_UA` (~line 48) |
| 2 | Refactor `_emit_event` to read `_PROVIDER` | `oauth_helper.py:71-86` | replace lines 71-86 |
| 3 | Add `_GBS_LOGIN_URL = "https://gbs.fm/accounts/login/"` | new | adjacent to `_TWITCH_LOGIN_URL` at line 93 |
| 4 | Add `_GBS_TRIGGER_COOKIES = frozenset(("sessionid", "csrftoken"))` | new | adjacent to `_TWITCH_AUTH_COOKIE` at line 94 |
| 5 | Add `_cookie_domain_matches_gbs` clone of `_cookie_domain_matches` | `oauth_helper.py:95-105` | new function, place after `_cookie_domain_matches` |
| 6 | Add `_GbsLoginWindow` class (mirror `_TwitchCookieWindow`) | `oauth_helper.py:108-192` (shape) + `oauth_helper.py:259-264` (flush) | new class, place between `_TwitchCookieWindow` and `_GoogleWindow` (matches "mirror existing ordering" — RESEARCH line 230) |
| 7 | Extend `main()` argparse `choices` + dispatch arm + set `_PROVIDER` | `oauth_helper.py:276-299` | replace lines 276-299 |

---

### File 2: `musicstreamer/ui_qt/accounts_dialog.py` (MODIFY — rewrite `_on_gbs_action_clicked` connect branch + add `_launch_gbs_login_subprocess` + add `_on_gbs_login_finished` + extract `_classify_and_show_failure` helper)

**Role:** Qt dialog / subprocess orchestrator
**Data flow:** click → spawn `QProcess` → on `finished` signal: parse stderr (JSON-line events), read stdout (Netscape dump), validate via `_validate_gbs_cookies`, write to `paths.gbs_cookies_path()` with `0o600`, toast, refresh status.
**Analog (PRIMARY):** Twitch trio at `accounts_dialog.py:243-259` (`_on_action_clicked`) + `332-341` (`_launch_oauth_subprocess`) + `361-458` (`_on_oauth_finished`).
**Analog (SECONDARY):** `cookie_import_dialog.py:333-342` (`_write_cookies` for the `0o600` write).

---

#### Excerpt 2A — `_on_action_clicked` (Twitch — `accounts_dialog.py:243-259`)

> **CITED:** `musicstreamer/ui_qt/accounts_dialog.py:243-259`. The connect/disconnect dispatch shape Phase 76's rewritten `_on_gbs_action_clicked` mirrors.

```python
    def _on_action_clicked(self) -> None:
        if self._is_connected():
            # D-03: confirm before disconnect
            answer = QMessageBox.question(
                self,
                "Disconnect Twitch?",
                "This will delete your saved Twitch token. "
                "You will need to reconnect to stream Twitch channels.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                constants.clear_twitch_token()
                self._update_status()
        else:
            # D-02: launch OAuth subprocess
            self._launch_oauth_subprocess()
```

---

#### Excerpt 2B — Current `_on_gbs_action_clicked` (what GETS REWRITTEN — `accounts_dialog.py:298-330`)

> **CITED:** `musicstreamer/ui_qt/accounts_dialog.py:298-330`. The connect branch (lines 318-330) is what Phase 76 replaces. The disconnect branch (lines 300-317) stays mostly verbatim — confirmation copy can be kept as-is per RESEARCH lines 631-639.

```python
    def _on_gbs_action_clicked(self) -> None:
        """Phase 60 D-04c: Connect (open parameterized CookieImportDialog) or Disconnect."""
        if self._is_gbs_connected():
            answer = QMessageBox.question(
                self, "Disconnect GBS.FM?",
                "This will delete your saved GBS.FM cookies. "
                "You will need to import them again to vote, view the active "
                "playlist, or submit songs.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                try:
                    os.remove(paths.gbs_cookies_path())
                except OSError:
                    # HIGH 2 fix: tolerate broader OSError tree
                    # (FileNotFoundError, PermissionError, IsADirectoryError, ...).
                    # Status update fires regardless so UI stays consistent.
                    pass
                self._update_status()
        else:
            from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog
            from musicstreamer import gbs_api
            dlg = CookieImportDialog(
                self._toast_callback,
                parent=self,
                target_label="GBS.FM",
                cookies_path=paths.gbs_cookies_path,
                validator=gbs_api._validate_gbs_cookies,
                oauth_mode=None,   # Phase 60 v1: file + paste tabs only (RESEARCH Q3)
            )
            dlg.exec()
            self._update_status()
```

**Adapted excerpt for Phase 76 (per RESEARCH §`_on_gbs_action_clicked` Rewrite lines 626-666 — VERBATIM):**

```python
    def _on_gbs_action_clicked(self) -> None:
        """Phase 76: Connect (launch subprocess) or Disconnect (delete cookies file)."""
        if self._is_gbs_connected():
            # Reuse Phase 60's existing confirm-then-remove path verbatim.
            answer = QMessageBox.question(
                self, "Disconnect GBS.FM?",
                "This will delete your saved GBS.FM cookies. "
                "You will need to reconnect to vote, view the active "
                "playlist, or submit songs.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                try:
                    os.remove(paths.gbs_cookies_path())
                except OSError:
                    # Phase 60 HIGH 2 fix — broader OSError tolerance.
                    pass
                self._update_status()
        else:
            self._launch_gbs_login_subprocess()

    def _on_gbs_import_clicked(self) -> None:
        """Phase 76 D-14: secondary path — open the existing File/Paste tabs.

        Mirror Phase 60's existing implementation but invoke from this dedicated
        button so the primary button remains the subprocess-launch path.
        """
        from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog
        from musicstreamer import gbs_api
        dlg = CookieImportDialog(
            self._toast_callback,
            parent=self,
            target_label="GBS.FM",
            cookies_path=paths.gbs_cookies_path,
            validator=gbs_api._validate_gbs_cookies,
            oauth_mode=None,   # Phase 60 v1 surface unchanged
        )
        dlg.exec()
        self._update_status()
```

---

#### Excerpt 2C — `_launch_oauth_subprocess` (Twitch — `accounts_dialog.py:332-341`)

> **CITED:** `musicstreamer/ui_qt/accounts_dialog.py:332-341`. The exact QProcess.start pattern Phase 76 clones (NOT parameterizes — RESEARCH line 671 explicitly rejects parameterization because the two output contracts differ: Twitch returns a raw token, GBS returns a Netscape dump).

```python
    def _launch_oauth_subprocess(self) -> None:
        """Phase 999.3 D-09: extracted helper so Retry can reuse the launch path."""
        self._oauth_proc = QProcess(self)
        self._oauth_proc.finished.connect(self._on_oauth_finished)
        # T-40-05: use sys.executable — no PATH injection; never shell=True
        self._oauth_proc.start(
            sys.executable,
            ["-m", "musicstreamer.oauth_helper", "--mode", "twitch"],
        )
        self._update_status()
```

**Adapted excerpt for Phase 76 (per RESEARCH §`_launch_gbs_login_subprocess` lines 673-686 — VERBATIM):**

```python
    def _launch_gbs_login_subprocess(self) -> None:
        """Phase 76 D-09: launch oauth_helper --mode gbs.

        Mirror _launch_oauth_subprocess shape but route the finished signal
        to _on_gbs_login_finished (which validates Netscape stdout).
        """
        self._gbs_login_proc = QProcess(self)
        self._gbs_login_proc.finished.connect(self._on_gbs_login_finished)
        self._gbs_login_proc.start(
            sys.executable,
            ["-m", "musicstreamer.oauth_helper", "--mode", "gbs"],
        )
        self._update_status()
```

**Init-time addition:** add `self._gbs_login_proc: QProcess | None = None` adjacent to `self._oauth_proc` at `accounts_dialog.py:84` (line 84 currently sets `self._oauth_proc = None`).

---

#### Excerpt 2D — `_on_oauth_finished` (Twitch — `accounts_dialog.py:361-458`, full method verbatim)

> **CITED:** `musicstreamer/ui_qt/accounts_dialog.py:361-458`. Phase 76's `_on_gbs_login_finished` mirrors lines 361-422 (stderr parse + stdout read + success-path write) with three substitutions: `token` → `netscape_text`, `paths.twitch_token_path()` → `paths.gbs_cookies_path()`, `"provider": "twitch"` → `"provider": "gbs"`. The failure path (lines 424-458) is structurally identical; RESEARCH lines 741-746 recommends extracting `_classify_and_show_failure(provider, exit_code, output, last_event)` shared by both handlers.

```python
    def _on_oauth_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        proc = self._oauth_proc
        self._oauth_proc = None

        # Phase 999.3 D-12: parse stderr line-by-line, keep last valid event.
        last_event: dict | None = None
        if proc is not None:
            try:
                stderr_bytes = proc.readAllStandardError().data()
            except Exception:
                stderr_bytes = b""
            try:
                stderr_text = stderr_bytes.decode("utf-8", errors="replace")
            except Exception:
                stderr_text = ""
            for line in stderr_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    # T-999.3-05: malformed line → skip, no eval/no code path.
                    continue
                if isinstance(obj, dict) and "category" in obj:
                    last_event = obj

        # Read stdout (token on success)
        token = ""
        if proc is not None:
            try:
                token = (
                    proc.readAllStandardOutput().data().decode("utf-8", errors="replace").strip()
                )
            except Exception:
                token = ""

        # ---- Success path --------------------------------------------
        success_category = last_event is None or last_event.get("category") == "Success"
        if exit_code == 0 and token and success_category:
            token_path = paths.twitch_token_path()
            os.makedirs(os.path.dirname(token_path), exist_ok=True)
            with open(token_path, "w") as fh:
                fh.write(token)
            os.chmod(token_path, 0o600)  # T-40-03: restrict permissions immediately
            logger = self._get_oauth_logger()
            if logger is not None:
                try:
                    logger.log_event({
                        "ts": (last_event or {}).get("ts", 0.0),
                        "category": "Success",
                        "detail": "",
                        "provider": "twitch",
                    })
                except Exception:
                    pass
            self._update_status()
            return

        # ---- Failure path --------------------------------------------
        # Defensive classification precedence:
        # 1. exit_code==0 with empty token → InvalidTokenResponse empty_stdout
        #    (takes precedence over missing event; subprocess exited cleanly
        #    but produced no token — semantically an invalid response, not a crash)
        # 2. No parseable event at all → SubprocessCrash exit=<code>
        # 3. Event present and exit_code==0 but empty token → upgrade to
        #    InvalidTokenResponse empty_stdout
        if exit_code == 0 and not token:
            last_event = {
                "ts": (last_event or {}).get("ts", 0.0),
                "category": "InvalidTokenResponse",
                "detail": "empty_stdout",
                "provider": "twitch",
            }
        elif last_event is None:
            last_event = {
                "ts": 0.0,
                "category": "SubprocessCrash",
                "detail": f"exit={exit_code}",
                "provider": "twitch",
            }

        logger = self._get_oauth_logger()
        if logger is not None:
            try:
                logger.log_event(last_event)
            except Exception:
                pass

        self._update_status()
        # T-999.3-05: coerce category/detail to str before UI consumption.
        category = str(last_event.get("category", "SubprocessCrash"))
        detail = str(last_event.get("detail", ""))
        self._show_failure_dialog(category, detail)
```

**Adapted excerpt for Phase 76 (per RESEARCH §`_on_gbs_login_finished` lines 688-746 — VERBATIM with planner finishing the failure-path helper extraction):**

```python
    def _on_gbs_login_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        """Mirror _on_oauth_finished but for the Netscape-stdout contract.

        Mirror lines accounts_dialog.py:361-509 — replace token write with
        Netscape validation + cookies-file write (0o600).
        """
        proc = self._gbs_login_proc
        self._gbs_login_proc = None

        # Phase 999.3 D-12: parse stderr (mirror exactly)
        last_event = self._parse_oauth_stderr(proc)   # extracted helper, planner picks

        netscape_text = ""
        if proc is not None:
            try:
                netscape_text = proc.readAllStandardOutput().data().decode(
                    "utf-8", errors="replace"
                )   # NO strip — Netscape format preserves leading newlines.
            except Exception:
                netscape_text = ""

        from musicstreamer.gbs_api import _validate_gbs_cookies

        success_category = last_event is None or last_event.get("category") == "Success"
        if exit_code == 0 and netscape_text and success_category and _validate_gbs_cookies(netscape_text):
            cookies_path = paths.gbs_cookies_path()
            os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
            with open(cookies_path, "w", encoding="utf-8") as fh:
                fh.write(netscape_text)
            os.chmod(cookies_path, 0o600)   # T-40-03 / Phase 999.7 invariant

            logger = self._get_oauth_logger()
            if logger is not None:
                try:
                    logger.log_event({
                        "ts": (last_event or {}).get("ts", 0.0),
                        "category": "Success",
                        "detail": "",
                        "provider": "gbs",   # NOT hardcoded "twitch"
                    })
                except Exception:
                    pass

            self._toast_callback("GBS.FM logged in.")
            self._update_status()
            return

        # Failure path: mirror lines 424-458 with provider="gbs".
        # Planner extracts the failure-classification + logger.log_event +
        # _show_failure_dialog flow from _on_oauth_finished — same shape, just
        # different provider field. Recommended helper signature:
        #   _classify_and_show_failure(provider: str, exit_code: int, output: str,
        #                              last_event: dict | None) -> None
        # used by BOTH _on_oauth_finished and _on_gbs_login_finished.
        self._classify_and_show_failure(
            provider="gbs",
            exit_code=exit_code,
            output=netscape_text,
            last_event=last_event,
        )
```

**Three substitutions vs `_on_oauth_finished` (and one structural extraction):**

| # | Substitution | Twitch value | GBS value |
|---|--------------|--------------|-----------|
| 1 | Output variable | `token` (stripped) | `netscape_text` (NOT stripped — preserves leading newlines per RESEARCH line 709) |
| 2 | Success-path validator | none (truthy check only) | `_validate_gbs_cookies(netscape_text)` (existing helper at `gbs_api.py:116-141`, no changes) |
| 3 | Provider field in `logger.log_event` + synthetic events | `"provider": "twitch"` (hardcoded at lines 417, 437, 444) | `"provider": "gbs"` |
| 4 | (Structural) Failure-path block | inline at lines 424-458 | extract to `_classify_and_show_failure(provider, exit_code, output, last_event)` helper; both `_on_oauth_finished` AND `_on_gbs_login_finished` call it (RESEARCH lines 741-746) |

**Anti-pitfall: do NOT `.strip()` the Netscape stdout.** Line 397's `.strip()` on `token` is OK for Twitch (raw token). For GBS, `.strip()` would corrupt the Netscape format if Django ever emits a trailing newline before the data. Per RESEARCH line 709: `# NO strip — Netscape format preserves leading newlines`.

---

#### Excerpt 2E — `CookieImportDialog._write_cookies` 0o600 pattern (`cookie_import_dialog.py:333-342`)

> **CITED:** `musicstreamer/ui_qt/cookie_import_dialog.py:333-342`. The canonical 0o600 cookies-write pattern. Phase 76's `_on_gbs_login_finished` success path inlines this exact shape (matching the Twitch `_on_oauth_finished` precedent at `accounts_dialog.py:405-409` which uses the same `os.makedirs` + `open(..., "w") + os.chmod(0o600)` triple).

```python
    def _write_cookies(self, text: str) -> None:
        """Write cookie text to self._cookies_path() with 0o600 permissions."""
        dest = self._cookies_path()
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(dest, 0o600)
        self._toast(f"{self._target_label} cookies imported.")
        self.accept()
```

Phase 76 reuses inline (NOT via call to `CookieImportDialog`) — the subprocess success path doesn't open a dialog. The relevant 6 lines (`dest = ... ; os.makedirs(...); with open ... fh.write(...); os.chmod(0o600)`) are inlined in `_on_gbs_login_finished` per Excerpt 2D adapted excerpt.

---

#### Excerpt 2F — `_CATEGORY_LABELS` (PROVIDER-AGNOSTIC — `accounts_dialog.py:46-51`)

> **CITED:** `musicstreamer/ui_qt/accounts_dialog.py:46-51`. Phase 76 reuses as-is — no entries added, no entries changed.

```python
_CATEGORY_LABELS = {
    "InvalidTokenResponse":    "Login did not return a valid token",
    "LoginTimeout":            "Login took too long (2 min)",
    "WindowClosedBeforeLogin": "Login window was closed before completing",
    "SubprocessCrash":         "Login helper crashed unexpectedly",
}
```

The `"InvalidTokenResponse"` label is slightly mis-worded for a cookie-harvest flow (per RESEARCH line 487 — "a cookie failure isn't a 'token' failure"). **Out of scope for Phase 76.** Planner may surface a follow-up note.

---

#### Excerpt 2G — `_get_oauth_logger` (PROVIDER-AGNOSTIC — `accounts_dialog.py:220-237`)

> **CITED:** `musicstreamer/ui_qt/accounts_dialog.py:220-237`. Phase 76 reuses as-is — the `OAuthLogger` and `paths.oauth_log_path()` are multi-provider by design (per RESEARCH line 470).

```python
    def _get_oauth_logger(self) -> OAuthLogger | None:
        """Phase 999.3 D-11: lazy-init OAuthLogger.

        Returns None on failure — logging is supplementary and MUST NOT
        block the user from seeing the failure dialog.
        """
        if self._oauth_logger is not None:
            return self._oauth_logger
        try:
            log_path = paths.oauth_log_path()
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            self._oauth_logger = OAuthLogger(log_path)
        except OSError:
            return None
        except Exception:
            # Defensive: any logger-init failure is swallowed (D-11 accept disposition).
            return None
        return self._oauth_logger
```

---

#### File 2 Summary Table — `accounts_dialog.py` Action Items

| # | Action | Source location | New / replacement line range |
|---|--------|-----------------|------------------------------|
| 1 | Add `self._gbs_login_proc: QProcess \| None = None` in `__init__` | mirror line 84 (`self._oauth_proc: QProcess \| None = None`) | adjacent to line 84 |
| 2 | Add `self._gbs_import_btn = QPushButton("Import cookies file…", self)` in GBS group construction | mirror existing `self._gbs_action_btn` at lines 113-115 | inside `_gbs_box`, after line 115 (per RESEARCH lines 597-599) |
| 3 | Wire `self._gbs_import_btn.clicked.connect(self._on_gbs_import_clicked)` | mirror line 114 (QA-05 bound-method, NO lambda) | adjacent to button construction |
| 4 | Extend `_update_status()` GBS branch to hide `_gbs_import_btn` when connected | mirror lines 187-192 (current 2-state GBS branch) | replace lines 186-192 (per RESEARCH lines 606-616); keep 2-state "Connected" / "Not connected" — D-15 4-state is MOOT under D-03 |
| 5 | Rewrite `_on_gbs_action_clicked` connect branch (lines 318-330) to call `_launch_gbs_login_subprocess()` | Excerpt 2A (Twitch dispatch shape) | replace lines 298-330 (per Excerpt 2B adapted) |
| 6 | Add new method `_on_gbs_import_clicked` (opens existing `CookieImportDialog`) | Excerpt 2B adapted (verbatim from RESEARCH) | new method after `_on_gbs_action_clicked` |
| 7 | Add new method `_launch_gbs_login_subprocess` (clone, NOT parameterize) | Excerpt 2C (`_launch_oauth_subprocess` shape) | new method, place near line 341 |
| 8 | Add new method `_on_gbs_login_finished` (mirror `_on_oauth_finished`) | Excerpt 2D (full method) | new method, place after `_on_oauth_finished` (which ends at line 458) |
| 9 | Extract `_classify_and_show_failure(provider, exit_code, output, last_event)` helper, used by BOTH `_on_oauth_finished` and `_on_gbs_login_finished` | Excerpt 2D failure-path block at lines 424-458 | new method; rewire `_on_oauth_finished:424-458` to call it with `provider="twitch"`, and `_on_gbs_login_finished` failure path calls it with `provider="gbs"` |
| 10 | (Optional, planner discretion) Extract `_parse_oauth_stderr(proc) -> dict \| None` helper from `_on_oauth_finished:369-390` to dedupe stderr parsing | Excerpt 2D stderr-parse block | new helper called from both finished handlers |

---

### File 3: `tests/test_oauth_helper.py` (NEW MODULE OR EXTEND — `--mode gbs` argparse + cookie-trigger + Netscape-output tests)

**Role:** unit test
**Data flow:** mocked `QNetworkCookie` (MagicMock with `name()` / `value()` / `domain()` byte-string returns) + `capsys` for stderr/stdout capture.
**Analog:** `tests/test_oauth_helper_twitch.py` (entire file, 154 lines).

> Per RESEARCH §Test Strategy lines 763-805, the test file for Phase 76 may either be a new `tests/test_oauth_helper_gbs.py` (mirroring `tests/test_oauth_helper_twitch.py` naming) OR extend the existing Twitch file. **Planner discretion;** the mirror-with-new-file approach matches the codebase precedent (`test_oauth_helper_twitch.py` is provider-specific).

---

#### Excerpt 3A — `_fake_cookie` MagicMock helper (`tests/test_oauth_helper_twitch.py:73-80`)

> **CITED:** `tests/test_oauth_helper_twitch.py:73-80`. The mock-cookie shape Phase 76 reuses verbatim — no changes needed; the test exercises the same `QNetworkCookie` surface (`name()` returns bytes, `value()` returns bytes, `domain()` returns str).

```python
def _fake_cookie(name: str, value: str, domain: str):
    """Construct a MagicMock that quacks like a QNetworkCookie for the narrow
    surface _on_cookie_added touches."""
    c = MagicMock()
    c.name.return_value = name.encode("utf-8")
    c.value.return_value = value.encode("utf-8")
    c.domain.return_value = domain
    return c
```

---

#### Excerpt 3B — Domain-match tests (`tests/test_oauth_helper_twitch.py:83-106`)

> **CITED:** `tests/test_oauth_helper_twitch.py:83-106`. Phase 76 clones five tests substituting `_cookie_domain_matches_gbs` and `gbs.fm` / `.gbs.fm` / `www.gbs.fm` / `fakegbs.fm`.

```python
def test_cookie_domain_matches_dot_twitch():
    from musicstreamer.oauth_helper import _cookie_domain_matches
    assert _cookie_domain_matches(_fake_cookie("auth-token", "tok", ".twitch.tv"))


def test_cookie_domain_matches_www_twitch():
    from musicstreamer.oauth_helper import _cookie_domain_matches
    assert _cookie_domain_matches(_fake_cookie("auth-token", "tok", "www.twitch.tv"))


def test_cookie_domain_matches_bare_twitch():
    from musicstreamer.oauth_helper import _cookie_domain_matches
    assert _cookie_domain_matches(_fake_cookie("auth-token", "tok", "twitch.tv"))


def test_cookie_domain_rejects_unrelated():
    from musicstreamer.oauth_helper import _cookie_domain_matches
    assert not _cookie_domain_matches(_fake_cookie("auth-token", "tok", "example.com"))


def test_cookie_domain_rejects_lookalike():
    from musicstreamer.oauth_helper import _cookie_domain_matches
    # "faketwitch.tv" does NOT end with ".twitch.tv" or equal any of our domains
    assert not _cookie_domain_matches(_fake_cookie("auth-token", "tok", "faketwitch.tv"))
```

**Adapted excerpt for Phase 76 (5 GBS variants — substitute `_cookie_domain_matches_gbs` + `gbs.fm` / `.gbs.fm` / `www.gbs.fm` / `fakegbs.fm`):**

```python
def test_cookie_domain_matches_gbs_dot():
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert _cookie_domain_matches_gbs(_fake_cookie("sessionid", "val", ".gbs.fm"))


def test_cookie_domain_matches_gbs_www():
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert _cookie_domain_matches_gbs(_fake_cookie("sessionid", "val", "www.gbs.fm"))


def test_cookie_domain_matches_gbs_bare():
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert _cookie_domain_matches_gbs(_fake_cookie("sessionid", "val", "gbs.fm"))


def test_cookie_domain_rejects_lookalike_gbs():
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    # "fakegbs.fm" does NOT end with ".gbs.fm" or equal any of our domains
    assert not _cookie_domain_matches_gbs(_fake_cookie("sessionid", "val", "fakegbs.fm"))


def test_cookie_domain_rejects_subdomain_attack():
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert not _cookie_domain_matches_gbs(_fake_cookie("sessionid", "val", "gbs.fm.evil.com"))
```

---

#### Excerpt 3C — `_emit_event` stderr contract test (`tests/test_oauth_helper_twitch.py:20-34`)

> **CITED:** `tests/test_oauth_helper_twitch.py:20-34`. The schema/`provider` regression test Phase 76 adapts to check `provider="gbs"`. Per RESEARCH line 780 + §Anti-Pitfall lines 425-472, this is the most important new test because it guards against the `_emit_event` provider-hardcode regression.

```python
def test_emit_event_writes_json_line_to_stderr(capsys):
    from musicstreamer.oauth_helper import _emit_event

    _emit_event("Success", detail="")
    captured = capsys.readouterr()
    # stdout untouched
    assert captured.out == ""
    # stderr: exactly one JSON line
    lines = captured.err.strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["category"] == "Success"
    assert event["detail"] == ""
    assert event["provider"] == "twitch"
    assert isinstance(event["ts"], (int, float))
```

**Adapted excerpt for Phase 76 — provider regression test:**

```python
def test_gbs_emits_provider_gbs_field(monkeypatch, capsys):
    """Anti-pitfall guard: after _PROVIDER refactor, --mode gbs events MUST
    carry provider="gbs" (not the hardcoded "twitch" default)."""
    from musicstreamer import oauth_helper

    # Simulate main() having set the provider for the GBS subprocess
    monkeypatch.setattr(oauth_helper, "_PROVIDER", "gbs")

    oauth_helper._emit_event("Success", detail="")

    lines = capsys.readouterr().err.strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["provider"] == "gbs"   # ← regression guard
    assert event["category"] == "Success"
```

---

#### Excerpt 3D — Login URL constant test (`tests/test_oauth_helper_twitch.py:118-125`)

> **CITED:** `tests/test_oauth_helper_twitch.py:118-125`. D-08 lock verification — same shape for `_GBS_LOGIN_URL` and `_GBS_TRIGGER_COOKIES`.

```python
def test_oauth_helper_uses_same_login_url():
    from musicstreamer import oauth_helper
    assert oauth_helper._TWITCH_LOGIN_URL == "https://www.twitch.tv/login"


def test_auth_token_cookie_name_constant():
    from musicstreamer.oauth_helper import _TWITCH_AUTH_COOKIE
    assert _TWITCH_AUTH_COOKIE == "auth-token"
```

**Adapted excerpt for Phase 76:**

```python
def test_gbs_login_url_constant():
    from musicstreamer import oauth_helper
    assert oauth_helper._GBS_LOGIN_URL == "https://gbs.fm/accounts/login/"


def test_gbs_trigger_cookies_constant():
    from musicstreamer.oauth_helper import _GBS_TRIGGER_COOKIES
    assert _GBS_TRIGGER_COOKIES == frozenset(("sessionid", "csrftoken"))
```

---

#### File 3 Summary Table — `tests/test_oauth_helper.py` (or `test_oauth_helper_gbs.py`) Action Items

| # | Test | Source pattern | Verifies |
|---|------|---------------|----------|
| 1 | `test_gbs_login_url_constant` | Excerpt 3D | D-08 URL lock |
| 2 | `test_gbs_trigger_cookies_constant` | Excerpt 3D | D-06 trigger set lock |
| 3 | `test_cookie_domain_matches_gbs_{dot,www,bare}` | Excerpt 3B | D-06 domain match |
| 4 | `test_cookie_domain_rejects_{lookalike_gbs,subdomain_attack}` | Excerpt 3B | D-06 lookalike rejection |
| 5 | `test_gbs_emits_provider_gbs_field` | Excerpt 3C | **Anti-pitfall regression guard** (RESEARCH line 780) |
| 6 | `test_gbs_trigger_fires_on_both_cookies` | adapt Excerpt 1A `_on_cookie_added` logic | D-06 set-completion trigger |
| 7 | `test_gbs_trigger_not_fires_on_only_one_cookie` | adapt Excerpt 1A | Negative case: only `csrftoken` (anonymous page load) must NOT flush |
| 8 | `test_gbs_flush_emits_netscape_header` | Excerpt 1B | D-07 output format |

---

### File 4: `tests/test_accounts_dialog.py` (EXTEND `TestAccountsDialogGBS` class at line 886 with subprocess-launch / subprocess-finished / disconnect tests)

**Role:** unit test
**Data flow:** `MagicMock(spec=QProcess)` via `_mock_proc_with_stderr` helper + `monkeypatch.setattr` for `paths` and `QProcess`.
**Analog:** `TestAccountsDialogOAuthFinished` at `tests/test_accounts_dialog.py:196-251` (Twitch subprocess-finished test).
**Secondary analog:** `_mock_proc_with_stderr` at `tests/test_accounts_dialog.py:67-79`.

---

#### Excerpt 4A — `_mock_proc_with_stderr` helper (`tests/test_accounts_dialog.py:67-79`)

> **CITED:** `tests/test_accounts_dialog.py:67-79`. The QProcess mock helper. Phase 76 reuses as-is for GBS subprocess-finished tests — `stdout_bytes` becomes the Netscape dump, `stderr_bytes` becomes the JSON-line event(s).

```python
def _mock_proc_with_stderr(stderr_bytes: bytes = b"", stdout_bytes: bytes = b""):
    """Build a MagicMock QProcess whose readAll*Error/Output return given bytes."""
    from PySide6.QtCore import QProcess
    proc = MagicMock(spec=QProcess)
    # readAllStandardError().data() → bytes
    err_chunk = MagicMock()
    err_chunk.data.return_value = stderr_bytes
    proc.readAllStandardError.return_value = err_chunk
    # readAllStandardOutput().data() → bytes
    out_chunk = MagicMock()
    out_chunk.data.return_value = stdout_bytes
    proc.readAllStandardOutput.return_value = out_chunk
    return proc
```

---

#### Excerpt 4B — Twitch success-path test (`tests/test_accounts_dialog.py:199-224`)

> **CITED:** `tests/test_accounts_dialog.py:199-224`. The exact shape for the GBS success-path test. Three substitutions: `twitch_token_path()` → `gbs_cookies_path()`; `fake_token` token bytes → a Netscape-dump fixture string; provider `"twitch"` → `"gbs"`.

```python
    def test_oauth_finished_success_writes_token(self, tmp_data_dir, qtbot, fake_repo):
        """Exit code 0 with token in stdout: token written to twitch_token_path with 0o600."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        token_path = paths.twitch_token_path()
        os.makedirs(os.path.dirname(token_path), exist_ok=True)

        fake_token = "oauth-abc123"
        mock_proc = _mock_proc_with_stderr(
            stderr_bytes=b'{"ts":1.0,"category":"Success","detail":"","provider":"twitch"}\n',
            stdout_bytes=fake_token.encode(),
        )

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._on_action_clicked()
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(0, QProcess.ExitStatus.NormalExit)

        assert os.path.exists(token_path)
        assert Path(token_path).read_text() == fake_token
        perms = oct(os.stat(token_path).st_mode & 0o777)
        assert perms == oct(0o600)
        assert "connected" in dlg._status_label.text().lower()
```

**Adapted excerpt for Phase 76 — GBS subprocess-finished success path:**

```python
    def test_gbs_login_finished_success_writes_cookies_file(
        self, tmp_data_dir, qtbot, fake_repo, monkeypatch, tmp_path
    ):
        """Exit code 0 with Netscape dump in stdout: cookies written to
        gbs_cookies_path() with 0o600 perms; provider='gbs' logged."""
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        monkeypatch.setattr(paths, "_root_override", str(tmp_path))

        netscape_dump = (
            "# Netscape HTTP Cookie File\n"
            ".gbs.fm\tTRUE\t/\tTRUE\t0\tsessionid\tabc123\n"
            ".gbs.fm\tTRUE\t/\tTRUE\t0\tcsrftoken\txyz789"
        )
        mock_proc = _mock_proc_with_stderr(
            stderr_bytes=b'{"ts":1.0,"category":"Success","detail":"","provider":"gbs"}\n',
            stdout_bytes=netscape_dump.encode(),
        )

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._on_gbs_action_clicked()    # not_connected → _launch_gbs_login_subprocess
            dlg._gbs_login_proc = mock_proc
            dlg._on_gbs_login_finished(0, QProcess.ExitStatus.NormalExit)

        cookies_path = paths.gbs_cookies_path()
        assert os.path.exists(cookies_path)
        assert Path(cookies_path).read_text() == netscape_dump
        perms = oct(os.stat(cookies_path).st_mode & 0o777)
        assert perms == oct(0o600)
        assert "connected" in dlg._gbs_status_label.text().lower()
```

---

#### Excerpt 4C — Existing GBS class scaffold (`tests/test_accounts_dialog.py:886-1020`)

> **CITED:** `tests/test_accounts_dialog.py:886-1020`. Phase 76 EXTENDS this class. The existing test at line 1000 (`test_gbs_connect_opens_dialog_with_correct_kwargs`) must be REPLACED — its connect-branch assertion (opens `CookieImportDialog`) is what Phase 76 changes (now launches subprocess). The replacement assertion verifies `_launch_gbs_login_subprocess` was called.

**Test to REPLACE** (lines 1000-1020):

```python
    def test_gbs_connect_opens_dialog_with_correct_kwargs(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Connect path: opens CookieImportDialog with GBS.FM target_label + paths.gbs_cookies_path + gbs_api validator + oauth_mode=None."""
        from musicstreamer import paths, gbs_api
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        captured = {}
        class FakeDialog:
            def __init__(self, *args, **kwargs):
                captured["args"] = args
                captured["kwargs"] = kwargs
            def exec(self):
                return 0
        monkeypatch.setattr("musicstreamer.ui_qt.cookie_import_dialog.CookieImportDialog",
                            FakeDialog)
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        dlg._on_gbs_action_clicked()
        assert captured["kwargs"]["target_label"] == "GBS.FM"
        assert captured["kwargs"]["cookies_path"] is paths.gbs_cookies_path
        assert captured["kwargs"]["validator"] is gbs_api._validate_gbs_cookies
        assert captured["kwargs"]["oauth_mode"] is None
```

**Adapted replacement for Phase 76 — connect now launches subprocess; the secondary `_on_gbs_import_clicked` is what opens `CookieImportDialog`:**

```python
    def test_gbs_connect_launches_subprocess(
        self, qtbot, fake_repo, tmp_path, monkeypatch
    ):
        """Phase 76: Connect branch invokes _launch_gbs_login_subprocess
        (NOT the old CookieImportDialog path — that moved to _on_gbs_import_clicked)."""
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))

        launched = []
        monkeypatch.setattr(
            AccountsDialog,
            "_launch_gbs_login_subprocess",
            lambda self: launched.append(True),
        )
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        dlg._on_gbs_action_clicked()
        assert launched == [True]


    def test_gbs_import_button_opens_cookie_import_dialog(
        self, qtbot, fake_repo, tmp_path, monkeypatch
    ):
        """Phase 76 D-14: secondary [Import cookies file…] button still routes
        to CookieImportDialog with the GBS-specific kwargs (preserves Phase 60 surface)."""
        from musicstreamer import paths, gbs_api
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        captured = {}
        class FakeDialog:
            def __init__(self, *args, **kwargs):
                captured["args"] = args
                captured["kwargs"] = kwargs
            def exec(self):
                return 0
        monkeypatch.setattr("musicstreamer.ui_qt.cookie_import_dialog.CookieImportDialog",
                            FakeDialog)
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        dlg._on_gbs_import_clicked()
        assert captured["kwargs"]["target_label"] == "GBS.FM"
        assert captured["kwargs"]["cookies_path"] is paths.gbs_cookies_path
        assert captured["kwargs"]["validator"] is gbs_api._validate_gbs_cookies
        assert captured["kwargs"]["oauth_mode"] is None
```

---

#### File 4 Summary Table — `tests/test_accounts_dialog.py` `TestAccountsDialogGBS` Extensions

| # | Test | Source pattern | Verifies |
|---|------|---------------|----------|
| 1 | (REPLACE) `test_gbs_connect_launches_subprocess` | Excerpt 4C adapted | D-05 connect branch routes to subprocess |
| 2 | (NEW) `test_gbs_import_button_opens_cookie_import_dialog` | Excerpt 4C adapted | D-14 secondary affordance preserves Phase 60 surface |
| 3 | (NEW) `test_gbs_login_finished_success_writes_cookies_file` | Excerpt 4B adapted | D-07 + 0o600 invariant |
| 4 | (NEW) `test_gbs_login_finished_failure_calls_classify_and_show_failure` | adapt `test_oauth_finished_failure_calls_show_failure_dialog` (lines 226-251) | failure-path delegates to extracted helper |
| 5 | (KEEP existing) `test_gbs_disconnect_removes_file_and_updates_status` (line 946) | unchanged | D-17 simplified (cookies-only — no token clear under D-03) |
| 6 | (KEEP existing) `test_gbs_disconnect_oserror_tolerated` (line 965) | unchanged | Phase 60 HIGH 2 fix tolerance |
| 7 | (KEEP existing) `test_gbs_status_initial_not_connected` (line 919) | unchanged | 2-state status (D-03 simplification) |
| 8 | (KEEP existing) `test_gbs_status_connected_when_cookies_present` (line 931) | unchanged | 2-state status |
| 9 | (NEW) `test_gbs_login_finished_provider_field_is_gbs` | adapt Excerpt 4B + assert `logger.log_event` called with `"provider": "gbs"` | Anti-pitfall regression guard (mirror RESEARCH line 472 cross-check) |

**Tests OUT OF SCOPE under D-03 (per RESEARCH §Group C lines 796-805) — DO NOT add:**

- 4-state status enumeration tests (D-15 moot; only 2 states)
- Inline token Save flow test (D-12 dropped; no QLineEdit)
- Disconnect-clears-BOTH test (D-17 reverts to cookies-only)
- `_is_gbs_token_saved()` predicate test (D-16 not added)
- `gbs_api_token` SQLite settings test (D-19 not added)

---

## Shared Patterns

### Pattern S-1: QA-05 bound-method signal connections

**Source:** every `clicked.connect` / `finished.connect` in `accounts_dialog.py`. Example at `accounts_dialog.py:114`:
```python
self._gbs_action_btn.clicked.connect(self._on_gbs_action_clicked)  # QA-05
```
**Apply to:** every new signal wire-up in Phase 76 — `_gbs_import_btn.clicked.connect(self._on_gbs_import_clicked)`, `_gbs_login_proc.finished.connect(self._on_gbs_login_finished)`.
**Anti-pattern:** `clicked.connect(lambda: self._on_xxx())` — forbidden by QA-05.

### Pattern S-2: T-40-04 PlainText QLabel format

**Source:** `accounts_dialog.py:109`:
```python
self._gbs_status_label.setTextFormat(Qt.TextFormat.PlainText)  # T-40-04
```
**Apply to:** all QLabels in any new failure dialog inside `_classify_and_show_failure` helper (matching `_show_failure_dialog:476, 485` precedent).

### Pattern S-3: 0o600 cookies write

**Source:** `cookie_import_dialog.py:333-342` (canonical) + `accounts_dialog.py:405-409` (Twitch inline):
```python
token_path = paths.twitch_token_path()
os.makedirs(os.path.dirname(token_path), exist_ok=True)
with open(token_path, "w") as fh:
    fh.write(token)
os.chmod(token_path, 0o600)  # T-40-03: restrict permissions immediately
```
**Apply to:** `_on_gbs_login_finished` success path — substitute `paths.gbs_cookies_path()` and `netscape_text` (and add `encoding="utf-8"` to `open()` per Excerpt 2E).

### Pattern S-4: Structured stderr JSON-line event contract

**Source:** `oauth_helper.py:71-86` + `accounts_dialog.py:369-390` (consumer-side parse).
**Apply to:** every `_emit_event` call inside `_GbsLoginWindow` carries the same `{ts, category, detail, provider}` schema; `provider` is sourced from the new `_PROVIDER` module constant (NOT hardcoded — Excerpt 1E refactor). The consumer-side parse in `_on_gbs_login_finished` is verbatim from `_on_oauth_finished:369-390` (RESEARCH line 702 recommends extracting to `_parse_oauth_stderr(proc)` helper).

### Pattern S-5: NEVER log cookie/token VALUES

**Source:** `oauth_helper.py:75-77` docstring:
```python
"""...
NEVER pass token values, cookie values, or URL fragments as `detail`.
Callers pass short enum-like strings (e.g. "no_auth_token", "120s").
"""
```
**Apply to:** every `_emit_event` call in `_GbsLoginWindow`. Specifically:
- `_emit_event("LoginTimeout", detail="120s")` — fixed string OK
- `_emit_event("WindowClosedBeforeLogin", detail="")` — empty OK
- `_emit_event("Success", detail="")` — empty OK
- **Never** `_emit_event("Success", detail=f"sessionid={value}")` — would leak the session cookie to the rotating log.

### Pattern S-6: Single-user scope

**Source:** `project_single_user_scope.md` (user memory).
**Apply to:** one `gbs_cookies_path()`, no per-account branching, no "switch profile" affordances. Phase 76 has zero touchpoints on this — but the planner should not introduce any.

---

## No Analog Found

**None.** Every Phase 76 in-scope file has an exact or near-exact analog inside `musicstreamer/oauth_helper.py` and `musicstreamer/ui_qt/accounts_dialog.py`. This phase is essentially a structural clone of the Twitch login flow with three substitutions (URL, trigger cookies, output format) and one refactor (`_emit_event` provider-hardcode).

The `_classify_and_show_failure(provider, exit_code, output, last_event)` helper extraction (File 2, Action #9) is greenfield — no in-repo template — but it is mechanically derived from `_on_oauth_finished:424-458` by parameterizing the `provider` field. The planner has full freedom on the exact signature; the RESEARCH-recommended shape is documented in Excerpt 2D adapted excerpt.

---

## Metadata

**Analog search scope:**
- `musicstreamer/oauth_helper.py` (304 lines, read in full)
- `musicstreamer/ui_qt/accounts_dialog.py` (509 lines, key sections read: 1-260, 261-510)
- `musicstreamer/ui_qt/cookie_import_dialog.py` (lines 325-349 — `_write_cookies` only)
- `tests/test_oauth_helper_twitch.py` (154 lines, read in full)
- `tests/test_accounts_dialog.py` (1020 lines; key sections read: 60-85 helper, 196-280 OAuth finished, 1000-1020 GBS connect)

**Files scanned:** 5
**Analog sources extracted:** 7 verbatim code excerpts + 4 adapted excerpts
**Pattern extraction date:** 2026-05-16

---

## PATTERN MAPPING COMPLETE

**Phase:** 76 - GBS.FM authentication: in-app login subprocess (like Google/Twitch)
**Files classified:** 4 (2 source + 2 test, post-D-03 scope collapse)
**Analogs found:** 4 / 4 (all exact mirrors)

### Coverage
- Files with exact analog: 4
- Files with role-match analog: 0
- Files with no analog: 0

### Key Patterns Identified
1. **Subprocess clone-with-three-substitutions** — `_GbsLoginWindow` mirrors `_TwitchCookieWindow` (`oauth_helper.py:108-192`) verbatim, substituting only login URL, trigger cookie set, and output format (Netscape dump per `_GoogleWindow._flush_cookies:259-264`).
2. **Anti-pitfall refactor: `_emit_event` provider hardcode** — current implementation at `oauth_helper.py:71-86` hardcodes `"provider": "twitch"`; Phase 76 MUST refactor to a module-level `_PROVIDER` constant set by `main()`. Anti-pitfall guarded by new test `test_gbs_emits_provider_gbs_field`.
3. **AccountsDialog connect-branch rewrite** — `_on_gbs_action_clicked:298-330` connect arm replaced with `self._launch_gbs_login_subprocess()` call; existing `CookieImportDialog` path moves to a new secondary `_on_gbs_import_clicked` handler with a new `[Import cookies file…]` button (D-14).
4. **Failure-path helper extraction** — `_on_oauth_finished:424-458` failure block extracted to `_classify_and_show_failure(provider, exit_code, output, last_event)` and reused by both Twitch and GBS finished handlers (RESEARCH lines 741-746).
5. **0o600 invariant continues** — `_on_gbs_login_finished` success path inlines the canonical `os.makedirs + open("w") + os.chmod(0o600)` triple (matching `cookie_import_dialog.py:333-342` and `accounts_dialog.py:405-409`).

### File Created
`/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/phases/76-gbs-fm-authentication-support-both-pre-existing-api-token-an/76-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference verbatim analog excerpts in plan action sections for: `_GbsLoginWindow` class addition (File 1), `_on_gbs_action_clicked` rewrite + `_launch_gbs_login_subprocess` + `_on_gbs_login_finished` + `_classify_and_show_failure` helper (File 2), `tests/test_oauth_helper.py` GBS extensions (File 3), and `TestAccountsDialogGBS` extensions (File 4). All citations carry verbatim line ranges per project memory `feedback_mirror_decisions_cite_source.md`.
