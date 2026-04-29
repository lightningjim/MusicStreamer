# Phase 53: YouTube Cookies into Accounts Menu — Pattern Map

**Mapped:** 2026-04-28
**Files analyzed:** 4 (2 source, 2 test)
**Analogs found:** 4 / 4 (100% coverage — all patterns exist in same files being modified)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/ui_qt/accounts_dialog.py` | dialog (Qt widget) | request-response (file-existence) + child-dialog launch | self (Twitch + AA groups in same file) | exact — third instance of an established 2-instance pattern |
| `musicstreamer/ui_qt/main_window.py` | menu/dialog launcher | request-response | self (existing `_open_accounts_dialog` + sibling launchers) | exact |
| `tests/test_accounts_dialog.py` | unit test | pytest-qt fixture + monkeypatch | self (existing `TestAccountsDialogStatus` class) | exact |
| `tests/test_main_window_integration.py` | unit test | pytest-qt fixture + monkeypatch | self (existing `test_discover_action_opens_dialog`) | role-match |

**Key meta-pattern:** Every analog Phase 53 needs already lives in the file being modified. This is composition, not invention.

---

## Pattern Assignments

### `musicstreamer/ui_qt/accounts_dialog.py` (dialog, request-response)

**Analog:** Same file — Twitch group (lines 78–90) + AA group (lines 92–103). YouTube is the third instance.

#### Pattern 1A — QGroupBox construction (lines 78–90, Twitch group as exact template)

```python
# Twitch group box
twitch_box = QGroupBox("Twitch", self)
twitch_layout = QVBoxLayout(twitch_box)

self._status_label = QLabel(self)
self._status_label.setTextFormat(Qt.TextFormat.PlainText)  # T-40-04: no rich-text injection
status_font = QFont()
status_font.setPointSize(10)
self._status_label.setFont(status_font)
twitch_layout.addWidget(self._status_label)

self._action_btn = QPushButton(self)
self._action_btn.clicked.connect(self._on_action_clicked)
twitch_layout.addWidget(self._action_btn)
```

**Copy verbatim, substitute:**
- `twitch_box` → `youtube_box` (or planner's choice from D-discretion: `_youtube_box` if stored)
- `"Twitch"` → `"YouTube"`
- `self._status_label` → `self._youtube_status_label`
- `self._action_btn` → `self._youtube_action_btn`
- `self._on_action_clicked` → `self._on_youtube_action_clicked`
- `status_font` is already defined for Twitch — REUSE the same `QFont` instance (D-discretion confirmed: "Reusing is fine"). The AA group already does this at line 98 (`self._aa_status_label.setFont(status_font)`), so YouTube follows AA's precedent: declare `status_font` once for the whole dialog, share across all three groups.

#### Pattern 1B — `__init__` signature extension (D-06 keyword default for back-compat)

**Current signature (line 68):**
```python
def __init__(self, repo, parent: QWidget | None = None) -> None:
```

**New signature:**
```python
def __init__(
    self,
    repo,
    toast_callback: Callable[[str], None] | None = None,
    parent: QWidget | None = None,
) -> None:
    super().__init__(parent)
    self._repo = repo
    self._toast_callback = toast_callback or (lambda _msg: None)  # defensive no-op
    ...
```

**Why `Callable | None = None` defaulted:** 24 existing positional `AccountsDialog(fake_repo)` test sites must continue to work without churn. Verified by RESEARCH.md.

**Add to imports at top of file (after line 23):**
```python
from typing import Callable
```

#### Pattern 1C — Layout ordering (lines 109–114, current 3-widget layout)

**Current (lines 109–114):**
```python
layout = QVBoxLayout(self)
layout.setContentsMargins(16, 16, 16, 16)
layout.setSpacing(8)
layout.addWidget(twitch_box)
layout.addWidget(aa_box)
layout.addWidget(btn_box)
```

**New (D-09: YouTube → Twitch → AudioAddict):**
```python
layout = QVBoxLayout(self)
layout.setContentsMargins(16, 16, 16, 16)
layout.setSpacing(8)
layout.addWidget(youtube_box)   # NEW — first
layout.addWidget(twitch_box)
layout.addWidget(aa_box)
layout.addWidget(btn_box)
```

#### Pattern 1D — `_is_connected` style file-existence check (lines 122–123 verbatim)

```python
def _is_connected(self) -> bool:
    return os.path.exists(paths.twitch_token_path())
```

**New mirror:**
```python
def _is_youtube_connected(self) -> bool:
    return os.path.exists(paths.cookies_path())
```

`os` and `paths` are already imported (lines 22, 39). No new imports.

#### Pattern 1E — `_update_status` branch (lines 129–150, extend with YouTube block)

**Existing structure:**
```python
def _update_status(self) -> None:
    if self._oauth_proc is not None:
        self._status_label.setText("Connecting...")
        self._action_btn.setEnabled(False)
    elif self._is_connected():
        self._status_label.setText("Connected")
        self._action_btn.setText("Disconnect")
        self._action_btn.setEnabled(True)
    else:
        self._status_label.setText("Not connected")
        self._action_btn.setText("Connect Twitch")
        self._action_btn.setEnabled(True)

    # AA group status (Phase 48 D-07)
    if self._is_aa_key_saved():
        ...
```

**Add YouTube branch — recommendation: insert AT THE TOP of `_update_status` to mirror D-09 visual order:**
```python
# YouTube group status (Phase 53 D-02, D-07, D-08)
if self._is_youtube_connected():
    self._youtube_status_label.setText("Connected")
    self._youtube_action_btn.setText("Disconnect")
else:
    self._youtube_status_label.setText("Not connected")
    self._youtube_action_btn.setText("Import YouTube Cookies...")
```

**No `Connecting...` intermediate state for YouTube** — there's no in-process subprocess on the YouTube path (CookieImportDialog is exec'd as a child dialog, not a QProcess started by AccountsDialog). Confirmed by RESEARCH.md.

**No `setEnabled` toggling** — YouTube button is always enabled (Twitch needs it because of the OAuth subprocess; YouTube's modal child dialog blocks reentry naturally).

#### Pattern 1F — Disconnect confirm + delete (lines 179–195, Twitch precedent)

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

**New mirror — `_on_youtube_action_clicked`:**
```python
def _on_youtube_action_clicked(self) -> None:
    if self._is_youtube_connected():
        # Phase 53 D-03: confirm before disconnect
        answer = QMessageBox.question(
            self,
            "Disconnect YouTube?",
            "This will delete your saved YouTube cookies. "
            "You will need to re-import to play cookie-protected YouTube streams.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            try:
                os.remove(paths.cookies_path())
            except FileNotFoundError:
                # Race with Phase 999.7 auto-clear — file already gone.
                pass
            self._update_status()
    else:
        # Phase 53 D-05: launch CookieImportDialog as child
        from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog
        dlg = CookieImportDialog(self._toast_callback, parent=self)
        dlg.exec()
        # D-discretion: call _update_status unconditionally — idempotent.
        self._update_status()
```

**Notes for the planner:**
- The `try/except FileNotFoundError` pattern matches the spirit of `constants.clear_twitch_token()` (which uses `os.path.exists` guard before `os.remove` — same race-safety, different style). RESEARCH.md OQ#2 calls out either is fine; CONTEXT.md D-03 explicitly says `try/except FileNotFoundError`.
- The `from ... import CookieImportDialog` is at slot-call time (not module top) per CONTEXT.md D-12 (the `main_window.py` import is being removed; AccountsDialog does its own import).

#### Pattern 1G — AA Yes/No precedent (lines 208–220, alternate confirm style)

```python
def _on_aa_clear_clicked(self) -> None:
    """Phase 48 D-06: confirm then clear the saved AudioAddict listen key."""
    answer = QMessageBox.question(
        self,
        "Clear AudioAddict key?",
        "This will delete your saved AudioAddict listen key. "
        "You will need to re-enter it from Import Stations.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if answer == QMessageBox.StandardButton.Yes:
        self._repo.set_setting("audioaddict_listen_key", "")
        self._update_status()
```

This is a secondary reference — Pattern 1F (Twitch) is the closer template since it deletes a file (matching YouTube's `os.remove(paths.cookies_path())`) rather than clearing a setting. Use AA only as a tone-consistency reference for the confirm-message wording style.

#### Pattern 1H — Bound-method signal connections (QA-05, lines 89, 102)

```python
self._action_btn.clicked.connect(self._on_action_clicked)         # Twitch (line 89)
self._aa_clear_btn.clicked.connect(self._on_aa_clear_clicked)     # AA (line 102)
```

**Mirror:**
```python
self._youtube_action_btn.clicked.connect(self._on_youtube_action_clicked)
```

**Anti-pattern (NEVER):** `self._youtube_action_btn.clicked.connect(lambda: self._on_youtube_action_clicked())` — QA-05 forbids self-capturing lambdas in signal connections.

---

### `musicstreamer/ui_qt/main_window.py` (menu/dialog launcher, request-response)

**Analog:** Same file — `_open_accounts_dialog` (lines 670–677) + sibling launcher methods.

#### Pattern 2A — Remove menu action + slot wiring (lines 148–149)

**Current:**
```python
act_cookies = self._menu.addAction("YouTube Cookies")
act_cookies.triggered.connect(self._open_cookie_dialog)
```

**Action:** DELETE both lines (CONTEXT.md D-12). Adjacent group structure (separator at line 142, separator at line 158) is preserved — verified by RESEARCH.md Pitfall 3.

#### Pattern 2B — Remove import (line 55)

**Current:**
```python
from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog
```

**Action:** DELETE this line. AccountsDialog does its own import inside `_on_youtube_action_clicked` (Pattern 1F).

#### Pattern 2C — Remove slot definition (lines 665–668)

**Current:**
```python
def _open_cookie_dialog(self) -> None:
    """D-17: Open CookieImportDialog from hamburger menu."""
    dlg = CookieImportDialog(self.show_toast, parent=self)
    dlg.exec()
```

**Action:** DELETE the entire method (4 lines including docstring).

#### Pattern 2D — Update `_open_accounts_dialog` (lines 670–677)

**Current:**
```python
def _open_accounts_dialog(self) -> None:
    """D-18: Open AccountsDialog from hamburger menu.

    Phase 48 D-04: pass ``self._repo`` so the AA group can read/clear
    the ``audioaddict_listen_key`` setting.
    """
    dlg = AccountsDialog(self._repo, parent=self)
    dlg.exec()
```

**New (D-14):**
```python
def _open_accounts_dialog(self) -> None:
    """D-18: Open AccountsDialog from hamburger menu.

    Phase 48 D-04: pass ``self._repo`` so the AA group can read/clear
    the ``audioaddict_listen_key`` setting.
    Phase 53 D-14: pass ``self.show_toast`` so the YouTube cookie import
    flow can surface its success toast through the same overlay.
    """
    dlg = AccountsDialog(self._repo, toast_callback=self.show_toast, parent=self)
    dlg.exec()
```

**Note:** `self.show_toast` is a bound method at line 304 with signature `(text: str, duration_ms: int = 3000) -> None`. The second arg is defaulted, so it passes cleanly as a `Callable[[str], None]`. Verified by RESEARCH.md.

---

### `tests/test_accounts_dialog.py` (unit test, pytest-qt + monkeypatch)

**Analog:** Same file — existing `TestAccountsDialogStatus` class (line 86) and adjacent test classes use the same fixture pattern.

#### Pattern 3A — Test class boilerplate (lines 86–89, existing template)

```python
class TestAccountsDialogStatus:
    """Status label and button text reflect token file presence."""

    def test_status_not_connected(self, tmp_data_dir, qtbot, fake_repo):
        """When token file does not exist: label 'Not connected', button 'Connect Twitch'."""
```

**New mirror:**
```python
class TestAccountsDialogYouTube:
    """Phase 53: YouTube cookie group — status, button toggle, disconnect, post-import refresh."""

    def test_youtube_group_present(self, tmp_data_dir, qtbot, fake_repo):
        """AccountsDialog has a YouTube QGroupBox with status label + action button."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        # Walk dlg.children() / dlg.findChildren(QGroupBox) and assert title()=="YouTube"
        ...
```

#### Pattern 3B — Existing fixtures (lines 31–58) — REUSE AS-IS

```python
class FakeRepo:
    def __init__(self) -> None:
        self._settings: dict[str, str] = {}
    def get_setting(self, key: str, default: str = "") -> str:
        return self._settings.get(key, default)
    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value


@pytest.fixture()
def fake_repo():
    return FakeRepo()


@pytest.fixture()
def tmp_data_dir(tmp_path, monkeypatch):
    """Redirect all paths.* accessors to tmp_path."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    return tmp_path
```

**Use cases for new tests:**
- **Pattern A — default None toast** (status read tests): `dlg = AccountsDialog(fake_repo)`
- **Pattern B — explicit None** (clarity): `dlg = AccountsDialog(fake_repo, toast_callback=None)`
- **Pattern C — capturing toast** (post-import + Disconnect tests):
  ```python
  toasts: list[str] = []
  dlg = AccountsDialog(fake_repo, toast_callback=toasts.append)
  ```

#### Pattern 3C — File-existence simulation (canonical for tmp_data_dir)

To simulate "Connected" state, write a file at `paths.cookies_path()`:
```python
def test_status_connected(self, tmp_data_dir, qtbot, fake_repo):
    cookies_path = paths.cookies_path()
    os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
    Path(cookies_path).write_text("# dummy cookie content")
    dlg = AccountsDialog(fake_repo)
    qtbot.addWidget(dlg)
    # assert dlg._youtube_status_label.text() == "Connected"
    # assert dlg._youtube_action_btn.text() == "Disconnect"
```

**Existing precedent for this pattern in same file:** `TestAccountsDialogStatus.test_status_connected` (search by name in test_accounts_dialog.py — uses identical write-to-tmp + reconstruct dialog approach).

#### Pattern 3D — Patching CookieImportDialog with MagicMock (post-import flow tests)

**Pattern reference:** `unittest.mock.patch` is already imported (line 18). The test should patch the CookieImportDialog symbol used inside `_on_youtube_action_clicked` (which does an in-slot import — patch the module-level name in `cookie_import_dialog`).

```python
def test_post_import_refreshes_status(self, tmp_data_dir, qtbot, fake_repo, monkeypatch):
    from musicstreamer.ui_qt import cookie_import_dialog as cid_mod
    captured = {}
    class FakeCookieDlg:
        def __init__(self, toast_cb, parent=None):
            captured["toast_cb"] = toast_cb
            captured["parent"] = parent
        def exec(self):
            # Simulate import success: write cookies file, then return Accepted.
            cookies_path = paths.cookies_path()
            os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
            Path(cookies_path).write_text("# imported")
            return QDialog.DialogCode.Accepted
    monkeypatch.setattr(cid_mod, "CookieImportDialog", FakeCookieDlg)
    ...
```

#### Pattern 3E — Disconnect confirm intercept (existing precedent — Twitch test)

The Twitch Disconnect tests in this file already monkeypatch `QMessageBox.question` to return Yes. Search the file for `monkeypatch.setattr(QMessageBox, "question", ...)` — that exact idiom applies to YouTube Disconnect tests:

```python
def test_disconnect_removes_cookies(self, tmp_data_dir, qtbot, fake_repo, monkeypatch):
    cookies_path = paths.cookies_path()
    os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
    Path(cookies_path).write_text("# dummy")
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *_args, **_kw: QMessageBox.StandardButton.Yes,
    )
    dlg = AccountsDialog(fake_repo)
    qtbot.addWidget(dlg)
    dlg._on_youtube_action_clicked()
    assert not os.path.exists(cookies_path)
    assert dlg._youtube_status_label.text() == "Not connected"
```

---

### `tests/test_main_window_integration.py` (unit test, pytest-qt + monkeypatch)

**Analog:** Same file — `test_discover_action_opens_dialog` (line 454) is the closest template for the new `test_open_accounts_passes_toast` test.

#### Pattern 4A — Update `EXPECTED_ACTION_TEXTS` (lines 395–406)

**Current (10 entries):**
```python
EXPECTED_ACTION_TEXTS = [
    "New Station",         # Phase 999.1 D-01 (Plan 03)
    "Discover Stations",
    "Import Stations",
    "Accent Color",
    "YouTube Cookies",     # ← Phase 53: REMOVE this line
    "Accounts",
    "Equalizer",           # Phase 47.2 D-07
    "Stats for Nerds",
    "Export Settings",
    "Import Settings",
]
```

**New (9 entries):**
```python
EXPECTED_ACTION_TEXTS = [
    "New Station",         # Phase 999.1 D-01 (Plan 03)
    "Discover Stations",
    "Import Stations",
    "Accent Color",
    "Accounts",            # Phase 53 D-12: "YouTube Cookies" entry removed; cookie management consolidated into Accounts dialog
    "Equalizer",           # Phase 47.2 D-07
    "Stats for Nerds",
    "Export Settings",
    "Import Settings",
]
```

**Note for planner:** The docstring at line 410 says `"exactly 9 non-separator actions"` but currently asserts against a 10-item list. Phase 53 incidentally fixes this drift — the docstring becomes accurate post-edit. No separate task.

**Separator count test (lines 417–421) is UNCHANGED.** The assertion `len(separators) == 3` continues to hold because removing "YouTube Cookies" from inside Group 2 does not change group boundaries. Verified by RESEARCH.md Pitfall 3.

#### Pattern 4B — `test_open_accounts_passes_toast` (mirror of `test_discover_action_opens_dialog` lines 454–467)

**Existing template (Discover action test, lines 454–467):**
```python
def test_discover_action_opens_dialog(qtbot, window, monkeypatch):
    """Triggering Discover Stations opens DiscoveryDialog."""
    from musicstreamer.ui_qt import discovery_dialog
    called = []

    def fake_exec(self):
        called.append(True)
        return 0

    monkeypatch.setattr(discovery_dialog.DiscoveryDialog, "exec", fake_exec)
    menu = window._menu
    actions = {a.text(): a for a in menu.actions() if not a.isSeparator()}
    actions["Discover Stations"].trigger()
    assert called == [True]
```

**New mirror — `test_open_accounts_passes_toast`:**
```python
def test_open_accounts_passes_toast(qtbot, window, monkeypatch):
    """Phase 53 D-14: triggering Accounts passes show_toast as toast_callback kwarg."""
    from musicstreamer.ui_qt import accounts_dialog
    captured = {}

    class FakeAccountsDialog:
        def __init__(self, repo, toast_callback=None, parent=None):
            captured["repo"] = repo
            captured["toast_callback"] = toast_callback
            captured["parent"] = parent
        def exec(self):
            return 0

    monkeypatch.setattr(accounts_dialog, "AccountsDialog", FakeAccountsDialog)
    menu = window._menu
    actions = {a.text(): a for a in menu.actions() if not a.isSeparator()}
    actions["Accounts"].trigger()

    assert captured["toast_callback"] == window.show_toast
    assert captured["parent"] is window
```

**Caveat for planner:** `main_window.py` imports `AccountsDialog` at module top (line 54), so `monkeypatch.setattr(accounts_dialog, "AccountsDialog", ...)` may NOT intercept the bound name in `main_window`. Two safer options:
1. `monkeypatch.setattr("musicstreamer.ui_qt.main_window.AccountsDialog", FakeAccountsDialog)` — patches the imported name in main_window's namespace directly. This is the canonical pattern for this codebase (search the file for `monkeypatch.setattr("musicstreamer.ui_qt.main_window.QMessageBox"` at line 830 — same idiom).
2. Patch the class's `__init__` and `exec` instead of replacing the symbol.

Option 1 is the precedent in this file; recommend that path.

---

## Shared Patterns

### T-40-04: PlainText format on all status QLabels

**Source:** `accounts_dialog.py:82` (Twitch) and `accounts_dialog.py:97` (AA)
**Apply to:** New YouTube status label.

```python
self._youtube_status_label.setTextFormat(Qt.TextFormat.PlainText)
```

Even though "Connected" / "Not connected" are static literals with no user-derived content, the rule is uniform across the codebase. Apply unconditionally.

### QA-05: Bound-method signal connections (no self-capturing lambdas)

**Source:** `accounts_dialog.py:89, 102`
**Apply to:** New YouTube button click connection.

```python
self._youtube_action_btn.clicked.connect(self._on_youtube_action_clicked)
```

### Status font sharing convention

**Source:** `accounts_dialog.py:83–85` (declared once for Twitch) → `accounts_dialog.py:98` (reused for AA)
**Apply to:** New YouTube label — reuse the same `status_font` variable created in the constructor for Twitch.

```python
status_font = QFont()
status_font.setPointSize(10)
self._status_label.setFont(status_font)            # Twitch
# ...
self._aa_status_label.setFont(status_font)         # AA reuses
self._youtube_status_label.setFont(status_font)    # YouTube reuses (NEW)
```

### Defaulted-keyword parameter for back-compat constructor extension

**Source:** No prior precedent in this codebase, but RESEARCH.md Pattern 3 mandates this approach to avoid 24 test-site updates.

```python
def __init__(
    self,
    repo,
    toast_callback: Callable[[str], None] | None = None,  # ← defaulted
    parent: QWidget | None = None,
) -> None:
    self._toast_callback = toast_callback or (lambda _msg: None)
```

The `or (lambda _msg: None)` defensive pattern ensures `self._toast_callback("...")` never raises even if caller passes `None` explicitly.

### File-existence Disconnect with race-tolerant deletion

**Source primary (style precedent):** `constants.clear_twitch_token()` at `constants.py:45–51` (uses `os.path.exists` guard)
**Source secondary (CONTEXT.md D-03 directive):** `try/except FileNotFoundError`

```python
try:
    os.remove(paths.cookies_path())
except FileNotFoundError:
    pass  # Race with Phase 999.7 auto-clear — file already gone.
```

Either style satisfies D-04 (Disconnect strictly limited to `cookies_path()` removal). CONTEXT.md D-03 picks `try/except`; either is fine — planner's call.

### Child-dialog launch + post-exec status refresh

**Source:** `accounts_dialog.py:373–374` (failure dialog Retry pattern uses `dlg.exec()` and acts on the return code).

For YouTube, the recommendation per CONTEXT.md D-discretion is to call `_update_status()` UNCONDITIONALLY after `dlg.exec()` (idempotent — if user cancels, status was already correct):

```python
dlg = CookieImportDialog(self._toast_callback, parent=self)
dlg.exec()
self._update_status()  # unconditional refresh — idempotent
```

### Existing toast surface — `MainWindow.show_toast`

**Source:** `main_window.py:304–306`

```python
def show_toast(self, text: str, duration_ms: int = 3000) -> None:
    """Show a toast notification on the centralWidget bottom-centre."""
    self._toast.show_toast(text, duration_ms)
```

Bound method passes cleanly as `Callable[[str], None]` (second arg defaulted). Pass `self.show_toast` directly — no wrapper needed.

---

## No Analog Found

**None.** All four files modified by Phase 53 have direct in-file analogs for every new code block. This is the cleanest possible pattern coverage — Phase 53 is composition by mirroring established 2-instance patterns to a 3rd instance.

---

## Metadata

**Analog search scope:**
- `musicstreamer/ui_qt/accounts_dialog.py` (374 lines, fully read)
- `musicstreamer/ui_qt/main_window.py` (684 lines; targeted reads at 45–225, 295–319, 655–684)
- `musicstreamer/ui_qt/cookie_import_dialog.py` (316 lines; targeted reads at 1–120, 280–316)
- `musicstreamer/constants.py` (targeted read at 30–60)
- `tests/test_accounts_dialog.py` (targeted read at 1–90 + grep for fixture/mock patterns)
- `tests/test_main_window_integration.py` (targeted reads at 385–435, 454–488 + grep for fixture/mock patterns)

**Files scanned:** 6 (4 source, 2 test)
**Pattern extraction date:** 2026-04-28
**Phase:** 53-youtube-cookies-into-accounts-menu
