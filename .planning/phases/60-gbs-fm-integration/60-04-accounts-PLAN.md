---
phase: 60
plan: 04
type: execute
wave: 2
depends_on: ["60-02"]
files_modified:
  - musicstreamer/ui_qt/cookie_import_dialog.py
  - musicstreamer/ui_qt/accounts_dialog.py
  - tests/test_cookie_import_dialog.py
  - tests/test_accounts_dialog.py
autonomous: true
requirements: [GBS-01b]
tags: [phase60, accounts, cookies, gbs-fm]

must_haves:
  truths:
    - "AccountsDialog renders a 'GBS.FM' QGroupBox with status label + Connect/Disconnect button between the YouTube group (line 91-103) and the Twitch group (line 104-115) per D-04c"
    - "Status label uses Qt.TextFormat.PlainText (T-40-04) and the shared status_font (T-11-A consistent typography)"
    - "Connect button: when not connected, opens the parameterized CookieImportDialog configured for gbs.fm (target_label='GBS.FM', cookies_path=paths.gbs_cookies_path, validator=gbs_api._validate_gbs_cookies, oauth_mode=None — file+paste tabs only per RESEARCH §Open Question Q3)"
    - "Disconnect button: shows QMessageBox confirmation; on Yes, deletes paths.gbs_cookies_path() (FileNotFoundError tolerant) and refreshes status"
    - "Status detection: _is_gbs_connected() returns True iff os.path.exists(paths.gbs_cookies_path())"
    - "CookieImportDialog refactored to accept config kwargs (target_label, cookies_path, validator, oauth_mode) with default values that preserve YouTube behavior — no behavioral regression for Phase 53 callers"
    - "Cookie file written with 0o600 perms (Phase 999.7 convention) at paths.gbs_cookies_path() = '~/.local/share/musicstreamer/gbs-cookies.txt'"
    - "All connections are bound methods (QA-05)"
  artifacts:
    - path: "musicstreamer/ui_qt/cookie_import_dialog.py"
      provides: "Parameterized constructor + per-instance config + parameterized toast/error messages"
      contains: "target_label"
    - path: "musicstreamer/ui_qt/accounts_dialog.py"
      provides: "_gbs_box QGroupBox with status_label + action_btn + _on_gbs_action_clicked + _is_gbs_connected"
      contains: "_gbs_box"
    - path: "tests/test_cookie_import_dialog.py"
      provides: "Regression tests for YouTube default behavior + new tests for gbs.fm config path"
    - path: "tests/test_accounts_dialog.py"
      provides: "New TestAccountsDialogGBS test class — group position, connect, disconnect, status, 0o600 perms"
  key_links:
    - from: "AccountsDialog._gbs_action_btn.clicked"
      to: "AccountsDialog._on_gbs_action_clicked"
      via: "QA-05 bound-method connection"
      pattern: "_gbs_action_btn\\.clicked\\.connect\\(self\\._on_gbs_action_clicked\\)"
    - from: "AccountsDialog._on_gbs_action_clicked (Connect path)"
      to: "CookieImportDialog(target_label='GBS.FM', cookies_path=paths.gbs_cookies_path, validator=gbs_api._validate_gbs_cookies, oauth_mode=None)"
      via: "Parameterized dialog config (Refactor Option 1 from RESEARCH §Pattern 4)"
      pattern: "CookieImportDialog.*target_label.*GBS\\.FM|target_label=\"GBS"
    - from: "AccountsDialog._on_gbs_action_clicked (Disconnect path)"
      to: "os.remove(paths.gbs_cookies_path())"
      via: "FileNotFoundError-tolerant unlink"
      pattern: "os\\.remove\\(paths\\.gbs_cookies_path"
---

<objective>
Land the AccountsDialog "GBS.FM" QGroupBox (D-04c) with a working Connect/Disconnect flow, AND refactor `cookie_import_dialog.py` to accept per-instance configuration so the same dialog class serves YouTube AND GBS.FM (RESEARCH §Pattern 4 — refactor Option 1; CONTEXT.md "Critical decisions to LOCK" item 2).

Purpose: Closes SC #2 of ROADMAP §Phase 60 (AccountsDialog "GBS.FM" group with status + Connect/Disconnect). D-04 ladder #3 LOCKED — cookies-import dialog is the ONLY auth UX surface; ladders #1/#2/#4 are rejected per RESEARCH §Auth Ladder Recommendation.

Output: ~30 LOC refactor in cookie_import_dialog.py (3 new constructor kwargs + parameterized strings), ~80 LOC added to accounts_dialog.py (1 group block + 3 helper methods + 1 layout insert), test extensions.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/60-gbs-fm-integration/60-CONTEXT.md
@.planning/phases/60-gbs-fm-integration/60-RESEARCH.md
@.planning/phases/60-gbs-fm-integration/60-PATTERNS.md
@.planning/phases/60-gbs-fm-integration/60-VALIDATION.md
@.planning/phases/60-gbs-fm-integration/60-02-SUMMARY.md
@musicstreamer/ui_qt/accounts_dialog.py
@musicstreamer/ui_qt/cookie_import_dialog.py
@musicstreamer/gbs_api.py
@musicstreamer/paths.py

<interfaces>
From musicstreamer/ui_qt/accounts_dialog.py:91-115 (YouTube + Twitch precedent — copy shape):
```python
# YouTube group
self._youtube_box = QGroupBox("YouTube", self)
youtube_layout = QVBoxLayout(self._youtube_box)
self._youtube_status_label = QLabel(self)
self._youtube_status_label.setTextFormat(Qt.TextFormat.PlainText)  # T-40-04
self._youtube_status_label.setFont(status_font)
youtube_layout.addWidget(self._youtube_status_label)
self._youtube_action_btn = QPushButton(self)
self._youtube_action_btn.clicked.connect(self._on_youtube_action_clicked)  # QA-05
youtube_layout.addWidget(self._youtube_action_btn)
```

From accounts_dialog.py:137-138 (layout ordering — INSERT _gbs_box AFTER _youtube_box):
```python
layout.addWidget(self._youtube_box)
# INSERT: layout.addWidget(self._gbs_box)  ← Phase 60
layout.addWidget(twitch_box)
```

From accounts_dialog.py:148-157 (status detection pattern):
```python
def _is_youtube_connected(self) -> bool:
    return os.path.exists(paths.cookies_path())
def _is_aa_key_saved(self) -> bool:
    return bool(self._repo.get_setting("audioaddict_listen_key", ""))
```

From accounts_dialog.py:235-270 (YouTube Connect/Disconnect handler):
```python
def _on_youtube_action_clicked(self) -> None:
    if self._is_youtube_connected():
        answer = QMessageBox.question(self, "Disconnect YouTube?", ...)
        if answer == QMessageBox.StandardButton.Yes:
            try:
                os.remove(paths.cookies_path())
            except FileNotFoundError:
                pass
            self._update_status()
    else:
        from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog
        dlg = CookieImportDialog(self._toast_callback, parent=self)
        dlg.exec()
        self._update_status()
```

From musicstreamer/ui_qt/cookie_import_dialog.py:70-115 (current YouTube-hardcoded constructor):
```python
class CookieImportDialog(QDialog):
    def __init__(self, toast_callback: Callable[[str], None],
                 parent: QWidget | None = None) -> None:
        # Hard-codes: setWindowTitle("YouTube Cookies"), oauth_helper --mode google,
        # paths.cookies_path(), _validate_youtube_cookies(), toast "YouTube cookies imported."
        # All three tabs ALWAYS created.
```

From musicstreamer/gbs_api.py (Plan 60-02):
```python
def _validate_gbs_cookies(text: str) -> bool: ...
```

From musicstreamer/paths.py (Plan 60-02):
```python
def gbs_cookies_path() -> str:
    return os.path.join(_root(), "gbs-cookies.txt")
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Refactor cookie_import_dialog.py to accept (target_label, cookies_path, validator, oauth_mode) kwargs</name>
  <read_first>
    - musicstreamer/ui_qt/cookie_import_dialog.py (read in full — 316 lines — current YouTube-hardcoded constructor + 3 tab builders + _on_*_import + _write_cookies)
    - tests/test_cookie_import_dialog.py (read in full — test fixtures, monkeypatching pattern)
    - musicstreamer/paths.py (verify gbs_cookies_path exists from Plan 60-02)
    - musicstreamer/gbs_api.py (verify _validate_gbs_cookies exists from Plan 60-02)
    - .planning/phases/60-gbs-fm-integration/60-PATTERNS.md (§"musicstreamer/ui_qt/cookie_import_dialog.py modifications" — refactor approach)
  </read_first>
  <behavior>
    - Constructor signature: `__init__(self, toast_callback, parent=None, *, target_label="YouTube", cookies_path=paths.cookies_path, validator=_validate_youtube_cookies, oauth_mode="google")` — kwargs are keyword-only with YouTube-preserving defaults
    - All previously-hardcoded YouTube strings/paths/validators replaced with self-stored config: window title `f"{target_label} Cookies"`, tab label `f"{target_label.split()[0]} Login"` for OAuth tab, validator+cookies_path+oauth_mode used wherever they appear
    - When `oauth_mode is None`: the 3rd tab ("Google Login" / "<oauth_mode> Login") is NOT added — only File and Paste tabs render. Phase 60 v1 ships with oauth_mode=None per RESEARCH §Open Question Q3.
    - All error messages parameterized: e.g. `f"Invalid cookies: no entries for {target_label} found."`
    - All toast messages parameterized: e.g. `f"{target_label} cookies imported."`
    - Existing YouTube behavior preserved when called with only positional args (default kwargs match Phase 53 / Phase 22 expected behavior — regression-tested)
    - `_validate_youtube_cookies` remains a top-level function in the module (don't rename — Plan 60-02's reference assumes module-level visibility)
  </behavior>
  <action>
**Step A — refactor `__init__`:**

```python
class CookieImportDialog(QDialog):
    """Multi-tab dialog for importing third-party cookies (YouTube/GBS.FM/...).

    Phase 40 introduced YouTube; Phase 60 parameterized for GBS.FM (D-04 ladder #3).

    Args:
      toast_callback: Forwarded to main-window toast on success.
      parent: Optional parent widget.

    Keyword args (Phase 60 — defaults preserve YouTube behavior):
      target_label: Display name (e.g. "YouTube", "GBS.FM"). Defaults to "YouTube".
      cookies_path: Callable returning the destination cookies file path.
      validator: Callable(text) -> bool — content validation.
      oauth_mode: --mode argument for oauth_helper subprocess; None disables the OAuth tab entirely.

    Phase 60 v1 ships gbs.fm with oauth_mode=None (file + paste tabs only).
    Future phase can add a gbs OAuth helper.
    """

    def __init__(
        self,
        toast_callback: Callable[[str], None],
        parent: QWidget | None = None,
        *,
        target_label: str = "YouTube",
        cookies_path: Callable[[], str] = paths.cookies_path,
        validator: Callable[[str], bool] = _validate_youtube_cookies,
        oauth_mode: str | None = "google",
    ) -> None:
        super().__init__(parent)
        self._toast = toast_callback
        self._selected_file_path: str | None = None
        self._google_process: QProcess | None = None
        # Phase 60 D-04: per-instance config
        self._target_label = target_label
        self._cookies_path = cookies_path
        self._validator = validator
        self._oauth_mode = oauth_mode

        self.setWindowTitle(f"{target_label} Cookies")
        self.setMinimumWidth(480)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_file_tab(), "File")
        self._tabs.addTab(self._build_paste_tab(), "Paste")
        if oauth_mode is not None:
            # Tab label uses the YouTube-specific "Google Login" name when
            # the legacy oauth_mode="google" is requested; otherwise generic.
            tab_label = "Google Login" if oauth_mode == "google" else f"{target_label} Login"
            self._tabs.addTab(self._build_google_tab(), tab_label)
        root.addWidget(self._tabs)

        self._error_label = QLabel()
        self._error_label.setTextFormat(Qt.PlainText)
        error_font = QFont()
        error_font.setPointSize(9)
        self._error_label.setFont(error_font)
        self._error_label.setStyleSheet(f"color: {ERROR_COLOR_HEX};")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        root.addWidget(button_box)
```

**Step B — replace hard-coded `_validate_youtube_cookies` calls with `self._validator(text)`** in 3 sites:

In `_on_paste_import` (line 199-205):
```python
def _on_paste_import(self) -> None:
    self._hide_error()
    text = self._paste_edit.toPlainText()
    if not self._validator(text):
        self._show_error(f"Invalid cookies: no entries for {self._target_label} found.")
        return
    self._write_cookies(text)
```

In `_on_file_import` (line 232-252):
```python
def _on_file_import(self) -> None:
    self._hide_error()
    if not self._selected_file_path:
        return
    try:
        with open(self._selected_file_path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        self._show_error(f"Could not read file: {exc}")
        return
    if not text.strip():
        self._show_error("File is empty.")
        return
    if not self._validator(text):
        self._show_error(f"Invalid cookies: no entries for {self._target_label} found.")
        return
    self._write_cookies(text)
```

In `_on_google_login` (line 258-270):
```python
def _on_google_login(self) -> None:
    self._hide_error()
    self._google_btn.setEnabled(False)
    self._google_status_label.setText("Logging in...")
    self._google_status_label.setVisible(True)
    process = QProcess(self)
    self._google_process = process
    process.finished.connect(self._on_google_process_finished)
    process.start(
        sys.executable,
        ["-m", "musicstreamer.oauth_helper", "--mode", self._oauth_mode or "google"],
    )
```

In `_on_google_process_finished` (line 272-293):
```python
        if not self._validator(text):
            self._show_error(f"Invalid cookies: no entries for {self._target_label} found.")
            return
        self._write_cookies(text)
```

**Step C — replace `paths.cookies_path()` and the toast text in `_write_cookies`:**

```python
    def _write_cookies(self, text: str) -> None:
        """Write cookie text to self._cookies_path() with 0o600 permissions."""
        dest = self._cookies_path()
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(dest, 0o600)
        self._toast(f"{self._target_label} cookies imported.")
        self.accept()
```

**Step D — extend `tests/test_cookie_import_dialog.py`** with regression + GBS coverage:

```python
# Add to existing tests/test_cookie_import_dialog.py — append at end of file

# Phase 60 / GBS-01b: parameterization regression + new coverage
def test_dialog_default_construction_preserves_youtube_behavior(qtbot, tmp_path, monkeypatch):
    """Regression — passing only the legacy positional args still configures YouTube."""
    from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog
    from musicstreamer import paths
    captured_toasts = []
    dlg = CookieImportDialog(toast_callback=captured_toasts.append)
    qtbot.addWidget(dlg)
    assert dlg.windowTitle() == "YouTube Cookies"
    assert dlg._target_label == "YouTube"
    assert dlg._cookies_path is paths.cookies_path
    assert dlg._oauth_mode == "google"
    # 3 tabs: File / Paste / Google Login
    assert dlg._tabs.count() == 3


def test_dialog_gbs_construction_omits_oauth_tab(qtbot, tmp_path, monkeypatch):
    """Phase 60 D-04: GBS dialog has File + Paste tabs only when oauth_mode=None."""
    from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog
    from musicstreamer import paths, gbs_api
    captured_toasts = []
    dlg = CookieImportDialog(
        toast_callback=captured_toasts.append,
        target_label="GBS.FM",
        cookies_path=paths.gbs_cookies_path,
        validator=gbs_api._validate_gbs_cookies,
        oauth_mode=None,
    )
    qtbot.addWidget(dlg)
    assert dlg.windowTitle() == "GBS.FM Cookies"
    assert dlg._target_label == "GBS.FM"
    assert dlg._cookies_path is paths.gbs_cookies_path
    assert dlg._oauth_mode is None
    # 2 tabs only — no OAuth tab
    assert dlg._tabs.count() == 2


def test_gbs_paste_invalid_shows_target_specific_error(qtbot, monkeypatch):
    """Validator + error string parameterized for GBS.FM."""
    from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog
    from musicstreamer import paths, gbs_api
    captured_toasts = []
    dlg = CookieImportDialog(
        toast_callback=captured_toasts.append,
        target_label="GBS.FM",
        cookies_path=paths.gbs_cookies_path,
        validator=gbs_api._validate_gbs_cookies,
        oauth_mode=None,
    )
    qtbot.addWidget(dlg)
    # Paste plainly invalid content
    dlg._paste_edit.setPlainText("# garbage")
    dlg._on_paste_import()
    assert dlg._error_label.isVisible()
    assert "GBS.FM" in dlg._error_label.text()


def test_gbs_paste_valid_writes_to_gbs_cookies_path(qtbot, tmp_path, monkeypatch):
    """Phase 60 D-04 + Phase 999.7 0o600: write goes to gbs_cookies_path; perms are 0o600."""
    import os
    from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog
    from musicstreamer import paths, gbs_api
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    captured_toasts = []
    dlg = CookieImportDialog(
        toast_callback=captured_toasts.append,
        target_label="GBS.FM",
        cookies_path=paths.gbs_cookies_path,
        validator=gbs_api._validate_gbs_cookies,
        oauth_mode=None,
    )
    qtbot.addWidget(dlg)
    valid_cookies = (
        "# Netscape HTTP Cookie File\n"
        ".gbs.fm\tTRUE\t/\tTRUE\t9999999999\tcsrftoken\tabc123\n"
        "gbs.fm\tFALSE\t/\tTRUE\t9999999999\tsessionid\txyz789\n"
    )
    dlg._paste_edit.setPlainText(valid_cookies)
    dlg._on_paste_import()
    target = paths.gbs_cookies_path()
    assert os.path.exists(target)
    # Content matches
    with open(target) as f:
        assert "sessionid" in f.read()
    # 0o600 perms (Phase 999.7 convention)
    mode = os.stat(target).st_mode & 0o777
    assert mode == 0o600
    # Toast text uses target_label
    assert any("GBS.FM cookies imported" in t for t in captured_toasts)
```

Decisions implemented: D-04 ladder #3 LOCKED (cookies-import dialog refactor — Option 1 parameterize per RESEARCH §Pattern 4 + RESEARCH §Open Q4), Phase 999.7 0o600, T-40-04 PlainText, QA-05.
  </action>
  <verify>
    <automated>python -c "import inspect; from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog; sig = inspect.signature(CookieImportDialog.__init__); params = sig.parameters; assert 'target_label' in params and 'cookies_path' in params and 'validator' in params and 'oauth_mode' in params, 'Missing kwargs: ' + str(list(params)); print('OK')" &amp;&amp; pytest tests/test_cookie_import_dialog.py -x -q 2>&amp;1 | tail -10</automated>
  </verify>
  <done>
- CookieImportDialog.__init__ has 4 keyword-only args: target_label, cookies_path, validator, oauth_mode
- Default values preserve YouTube behavior (regression test passes)
- oauth_mode=None disables the 3rd tab (only 2 tabs render)
- All hardcoded "YouTube"/".youtube.com"/paths.cookies_path() references replaced with self._target_label/self._validator/self._cookies_path
- 0o600 perms enforced on every write path
- All existing tests in tests/test_cookie_import_dialog.py still pass (regression)
- 4 new tests added (default-preserves-youtube, gbs-construction, gbs-error-message, gbs-write+0o600)
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add _gbs_box QGroupBox + _on_gbs_action_clicked + _is_gbs_connected to AccountsDialog</name>
  <read_first>
    - musicstreamer/ui_qt/accounts_dialog.py (read full — 449 lines — focus on lines 88-138 group construction + 148-170 status detection + 235-270 YouTube handler precedent)
    - tests/test_accounts_dialog.py (read full — TestAccountsDialogYouTube class is the analog for Phase 60's TestAccountsDialogGBS)
    - musicstreamer/ui_qt/cookie_import_dialog.py (post-Task-1 state — verify new constructor signature)
    - musicstreamer/paths.py (verify gbs_cookies_path exists)
    - musicstreamer/gbs_api.py (verify _validate_gbs_cookies exists)
    - .planning/phases/60-gbs-fm-integration/60-PATTERNS.md (§"musicstreamer/ui_qt/accounts_dialog.py modifications")
  </read_first>
  <behavior>
    - Inserts `_gbs_box` group (QGroupBox titled "GBS.FM") with `_gbs_status_label` (PlainText) + `_gbs_action_btn` (QPushButton)
    - status_label uses the SAME shared status_font defined at line 88-89 (T-11-A typography consistency)
    - layout.addWidget(self._gbs_box) inserted between line 137 (YouTube) and the Twitch box add (line 138)
    - _is_gbs_connected: returns os.path.exists(paths.gbs_cookies_path())
    - _update_status: extended to set _gbs_status_label text + _gbs_action_btn text (mirroring YouTube block at lines 161-166)
    - _on_gbs_action_clicked: Connect path opens parameterized CookieImportDialog with target_label="GBS.FM", cookies_path=paths.gbs_cookies_path, validator=gbs_api._validate_gbs_cookies, oauth_mode=None; calls dlg.exec() then self._update_status()
    - _on_gbs_action_clicked: Disconnect path shows QMessageBox.question, on Yes calls os.remove(paths.gbs_cookies_path()) (FileNotFoundError tolerant) and self._update_status()
    - All connections bound methods (QA-05)
  </behavior>
  <action>
**Step A — Insert `_gbs_box` block** in AccountsDialog `__init__` AFTER the YouTube block (line 91-103) and BEFORE the Twitch block (line 104+):

```python
        # === Phase 60 D-04c: GBS.FM group (between YouTube and Twitch) ===
        self._gbs_box = QGroupBox("GBS.FM", self)
        gbs_layout = QVBoxLayout(self._gbs_box)

        self._gbs_status_label = QLabel(self)
        self._gbs_status_label.setTextFormat(Qt.TextFormat.PlainText)  # T-40-04
        self._gbs_status_label.setFont(status_font)
        gbs_layout.addWidget(self._gbs_status_label)

        self._gbs_action_btn = QPushButton(self)
        self._gbs_action_btn.clicked.connect(self._on_gbs_action_clicked)  # QA-05
        gbs_layout.addWidget(self._gbs_action_btn)
```

**Step B — Insert into the layout ordering** (line 137-138):

Current:
```python
layout.addWidget(self._youtube_box)
layout.addWidget(twitch_box)    # ← need to find the actual variable; may be _twitch_box
layout.addWidget(aa_box)
layout.addWidget(btn_box)
```

New:
```python
layout.addWidget(self._youtube_box)
layout.addWidget(self._gbs_box)         # Phase 60 D-04c
layout.addWidget(twitch_box)
layout.addWidget(aa_box)
layout.addWidget(btn_box)
```

(Read accounts_dialog.py:130-145 for exact variable names — `twitch_box` may be a local variable; `aa_box` may be `self._aa_box` etc. Match the existing pattern.)

**Step C — Add `_is_gbs_connected` helper** alongside `_is_youtube_connected` (around line 151):

```python
    def _is_gbs_connected(self) -> bool:
        """Phase 60 D-04 ladder #3: True when paths.gbs_cookies_path() exists on disk."""
        return os.path.exists(paths.gbs_cookies_path())
```

**Step D — Extend `_update_status`** (around lines 159-170 — mirror the existing YouTube block):

Add a sibling block (same shape as YouTube):

```python
        # Phase 60 D-04c: GBS.FM status (mirror YouTube block)
        if self._is_gbs_connected():
            self._gbs_status_label.setText("Connected")
            self._gbs_action_btn.setText("Disconnect")
        else:
            self._gbs_status_label.setText("Not connected")
            self._gbs_action_btn.setText("Import GBS.FM Cookies...")
```

**Step E — Add `_on_gbs_action_clicked` handler** (mirror YouTube handler at lines 235-270):

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
                except FileNotFoundError:
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

**Step F — Add tests** to `tests/test_accounts_dialog.py`. Add a new class `TestAccountsDialogGBS` mirroring `TestAccountsDialogYouTube`:

```python
class TestAccountsDialogGBS:
    """Phase 60 / GBS-01b: AccountsDialog _gbs_box group."""

    def test_gbs_box_position_between_youtube_and_twitch(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """D-04c: _gbs_box must render BETWEEN YouTube and Twitch."""
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        # _gbs_box exists with correct title
        assert hasattr(dlg, "_gbs_box")
        assert dlg._gbs_box.title() == "GBS.FM"
        # Status label uses PlainText (T-40-04)
        from PySide6.QtCore import Qt
        assert dlg._gbs_status_label.textFormat() == Qt.TextFormat.PlainText
        # Layout: _youtube_box appears before _gbs_box appears before twitch group
        layout = dlg.layout()
        widgets = [layout.itemAt(i).widget() for i in range(layout.count())]
        # Filter to QGroupBoxes only
        from PySide6.QtWidgets import QGroupBox
        groups = [w for w in widgets if isinstance(w, QGroupBox)]
        titles = [g.title() for g in groups]
        # Expect YouTube, GBS.FM, Twitch in that order (followed by AudioAddict + maybe close button container)
        assert "YouTube" in titles
        assert "GBS.FM" in titles
        assert titles.index("YouTube") < titles.index("GBS.FM")
        # Twitch group title may be e.g. "Twitch" — just assert _gbs_box appears before whatever comes next
        if "Twitch" in titles:
            assert titles.index("GBS.FM") < titles.index("Twitch")

    def test_gbs_status_initial_not_connected(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Fresh state: cookies file missing → 'Not connected' label + 'Import GBS.FM Cookies...' button."""
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        assert dlg._gbs_status_label.text() == "Not connected"
        assert "Import GBS.FM Cookies" in dlg._gbs_action_btn.text()

    def test_gbs_status_connected_when_cookies_present(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Cookies file exists → 'Connected' label + 'Disconnect' button."""
        import os
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        # Create the gbs cookies file
        os.makedirs(str(tmp_path), exist_ok=True)
        with open(paths.gbs_cookies_path(), "w") as f:
            f.write("# fake")
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        assert dlg._gbs_status_label.text() == "Connected"
        assert dlg._gbs_action_btn.text() == "Disconnect"

    def test_gbs_disconnect_removes_file_and_updates_status(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Disconnect path: confirm Yes → os.remove → status flips to 'Not connected'."""
        import os
        from PySide6.QtWidgets import QMessageBox
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)
        with open(paths.gbs_cookies_path(), "w") as f:
            f.write("# fake")
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        # Stub QMessageBox.question to return Yes
        monkeypatch.setattr(QMessageBox, "question",
                            staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Yes))
        dlg._on_gbs_action_clicked()
        assert not os.path.exists(paths.gbs_cookies_path())
        assert dlg._gbs_status_label.text() == "Not connected"

    def test_gbs_disconnect_filenotfound_tolerated(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Race: cookie removed externally between is_connected and remove() — must not raise."""
        from PySide6.QtWidgets import QMessageBox
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        # Stub _is_gbs_connected → True so we take the disconnect branch
        monkeypatch.setattr(dlg, "_is_gbs_connected", lambda: True)
        monkeypatch.setattr(QMessageBox, "question",
                            staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Yes))
        # File doesn't actually exist — must tolerate FileNotFoundError silently
        dlg._on_gbs_action_clicked()  # No exception expected

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

Decisions implemented: D-04c (group placement), D-04 ladder #3 LOCKED (CookieImportDialog kwargs), Phase 999.7 (0o600 inherited via Task 1), T-40-04 PlainText, QA-05 bound methods.
  </action>
  <verify>
    <automated>pytest tests/test_accounts_dialog.py -x -q 2>&amp;1 | tail -15 &amp;&amp; grep -q '_gbs_box' musicstreamer/ui_qt/accounts_dialog.py &amp;&amp; grep -q '_on_gbs_action_clicked' musicstreamer/ui_qt/accounts_dialog.py &amp;&amp; grep -q '_is_gbs_connected' musicstreamer/ui_qt/accounts_dialog.py &amp;&amp; grep -q 'gbs_cookies_path' musicstreamer/ui_qt/accounts_dialog.py &amp;&amp; ! grep -E '_gbs_action_btn\.clicked\.connect\(lambda' musicstreamer/ui_qt/accounts_dialog.py</automated>
  </verify>
  <done>
- AccountsDialog has self._gbs_box, self._gbs_status_label, self._gbs_action_btn attributes
- _gbs_box renders between YouTube and Twitch groups (verified by group-title ordering test)
- _is_gbs_connected returns os.path.exists(paths.gbs_cookies_path())
- _on_gbs_action_clicked Connect path passes target_label='GBS.FM', oauth_mode=None to CookieImportDialog
- Disconnect path uses QMessageBox.question + os.remove + FileNotFoundError tolerance
- Status flips correctly between Connected/Not connected as the cookies file appears/disappears
- 6 tests in TestAccountsDialogGBS class all pass
- No QA-05 violations (no `lambda` in _gbs_action_btn connection)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| User input ↔ Cookies file (file picker / paste) | Untrusted text crosses here; validator gates content before write |
| File ↔ FS perms (0o600) | Cookies file is a sensitive secret; chmod immediately after write (Phase 999.7) |
| AccountsDialog ↔ CookieImportDialog | Per-instance config (validator/path/oauth_mode); ladder #3 LOCKED, no other ladders |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-60-17 | Information Disclosure | gbs-cookies.txt world-readable | mitigate | 0o600 enforced post-write in `_write_cookies` (inherited from Phase 999.7 / Phase 22 convention; preserved in Task 1 refactor). |
| T-60-18 | Tampering | Cookie content validates as YouTube but written to GBS path | mitigate | Validator + path are paired in the same constructor call; cross-test asserts both `validator is gbs_api._validate_gbs_cookies` AND `cookies_path is paths.gbs_cookies_path` (Test 6). |
| T-60-19 | Repudiation | User accidentally clicks Disconnect | mitigate | QMessageBox.question with explicit Yes/No (default No); only Yes proceeds with os.remove. Mirrors YouTube precedent. |
| T-60-20 | DoS (UX) | os.remove fails on missing file (race with Disconnect path) | mitigate | FileNotFoundError caught and silently passed; status refreshes regardless. |
| T-60-21 | Information Disclosure | Status label renders gbs.fm-side string with HTML formatting | mitigate | Qt.TextFormat.PlainText (T-40-04) on `_gbs_status_label`. Pitfall 11. |
| T-60-22 | Tampering | Self-capturing lambda in _gbs_action_btn connection | mitigate | QA-05 bound-method connection enforced by grep guard in verify command. Pitfall 10. |

Citations: Pitfalls 10, 11 from RESEARCH.md.
</threat_model>

<verification>
```bash
# Targeted subset (per VALIDATION.md)
pytest tests/test_cookie_import_dialog.py tests/test_accounts_dialog.py -x -q

# Module imports / regression
python -c "from musicstreamer.ui_qt.accounts_dialog import AccountsDialog; from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog; print('OK')"

# 0o600 invariant grep gate (Plan 60-04 inherits from Phase 999.7)
grep -n "os.chmod.*0o600" musicstreamer/ui_qt/cookie_import_dialog.py

# Group title ordering grep gate
grep -n "QGroupBox(\"GBS.FM\"" musicstreamer/ui_qt/accounts_dialog.py

# Full suite regression
pytest -x
```
</verification>

<success_criteria>
- CookieImportDialog accepts target_label/cookies_path/validator/oauth_mode kwargs with YouTube-preserving defaults
- oauth_mode=None disables the OAuth tab (gbs.fm uses only File + Paste)
- AccountsDialog has a "GBS.FM" QGroupBox between YouTube and Twitch
- Connect button opens parameterized CookieImportDialog with GBS.FM config
- Disconnect button confirms via QMessageBox + removes file + refreshes status
- Status label uses PlainText (T-40-04) and shared status_font
- Cookie file written with 0o600 perms at paths.gbs_cookies_path()
- All existing test files in tests/ still pass (regression)
- 4 new tests in tests/test_cookie_import_dialog.py + 6 new tests in tests/test_accounts_dialog.py all pass
</success_criteria>

<output>
After completion, create `.planning/phases/60-gbs-fm-integration/60-04-SUMMARY.md`
</output>
