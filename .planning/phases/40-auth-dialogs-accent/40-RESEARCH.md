# Phase 40: Auth Dialogs + Accent — Research

**Researched:** 2026-04-13
**Domain:** PySide6 dialogs, subprocess OAuth, QSS accent, QMenu wiring
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Twitch OAuth (AccountsDialog)**
- D-01: `AccountsDialog(QDialog)` showing connection status + Connect/Disconnect button. Status via `os.path.exists(paths.twitch_token_path())`.
- D-02: "Connect Twitch" launches subprocess `oauth_helper.py` that opens `QWebEngineView` to Twitch OAuth URL, captures token, writes to `twitch_token_path()` with `0o600`.
- D-03: "Disconnect" deletes `twitch_token_path()` with confirmation prompt.
- D-04: Subprocess communicates token back via stdout or temp file; main process reads after subprocess exits.

**YouTube Cookie Import (CookieImportDialog)**
- D-05: `CookieImportDialog(QDialog)` with three sections/tabs: File (QFileDialog), Paste (QTextEdit), Google Login (subprocess QWebEngineView).
- D-06: All three paths write to `paths.cookies_path()` with `0o600`; existing cookies overwritten (no merge).
- D-07: Google Login uses same subprocess helper pattern (`oauth_helper.py` with different URL/mode); extracts cookies from `QWebEngineCookieStore.cookieAdded`, writes Netscape format.
- D-08: Validation: check file non-empty + contains `.youtube.com` domain line. Show success/error toast.

**Accent Color Picker (AccentColorDialog)**
- D-09: `AccentColorDialog(QDialog)` with 8 preset swatches (grid) + `QLineEdit` hex entry. Live QSS preview on valid hex.
- D-10: "Apply" saves to `repo.set_setting("accent_color", hex)` and writes QSS to `paths.accent_css_path()`. "Reset" clears setting and removes override.
- D-11: `accent_utils.py` gets new `build_accent_qss(hex_value)` function targeting Qt QSS selectors (not GTK CSS). Targets: `QPushButton` highlight states, `QSlider::sub-page`, chip selected states, segmented control active state.
- D-12: `MainWindow.__init__` checks saved accent color on startup and applies QSS if present.

**Hamburger Menu (UI-10)**
- D-13: Replace placeholder with real `QMenu`, flat actions with `addSeparator()` grouping.
  - Group 1: "Discover Stations", "Import Stations"
  - Separator
  - Group 2: "Accent Color", "YouTube Cookies", "Accounts"
  - Separator
  - Group 3: "Export Settings" (disabled), "Import Settings" (disabled)
- D-14..D-19: Action-to-dialog wiring as specified.

### Claude's Discretion

- Exact 8 accent color presets (suggest matching v1.5's palette)
- AccentColorDialog dimensions and swatch button sizes
- Whether the subprocess helper is a single `oauth_helper.py` with mode flags or two separate scripts
- QSS selector specificity for accent override
- CookieImportDialog tab vs stacked section layout
- Whether AccountsDialog is modal or non-modal

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
Out of phase scope: MEDIA-01..05 (Phase 41), SYNC-01..05 (Phase 42), GStreamer Windows spike (Phase 43).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-08 | `AccountsDialog` — Twitch OAuth via subprocess QWebEngineView; token written with restricted permissions | Subprocess isolation pattern documented; `QProcess` vs `subprocess` tradeoffs covered; PKG-03 `_popen()` impact assessed |
| UI-09 | YouTube cookie import — file picker, paste, Google login; stored with restricted permissions | Cookie file format (Netscape) and validation approach documented; QWebEngineCookieStore.cookieAdded proof-of-concept concern addressed |
| UI-10 | Hamburger menu — Discover, Import, Accent Color, YouTube Cookies, Accounts, Export/Import Settings | `QMenu` from `QMenuBar` wiring pattern documented; existing Phase 39 dialog constructors audited for required args |
| UI-11 | Accent color picker — 8 presets + hex entry, runtime QSS, persisted in SQLite | `build_accent_qss()` QSS selectors identified from existing codebase; startup load pattern documented |
</phase_requirements>

---

## Summary

Phase 40 introduces three new dialogs (AccountsDialog, CookieImportDialog, AccentColorDialog) and wires the hamburger menu. All foundation is in place: `paths.py` exposes all three file paths, `constants.py` has `ACCENT_PRESETS` (8 colors) and `clear_twitch_token()`, `accent_utils._is_valid_hex()` is reusable, and `repo.get_setting`/`set_setting` handles accent persistence. The v1.5 accent presets are already defined exactly as needed.

The one critical environmental finding is that `PySide6.QtWebEngineWidgets` is not currently installed — it is a separate apt package (`python3-pyside6.qtwebenginewidgets`) that must be installed before oauth_helper.py can run. This package is available in the distro. The subprocess OAuth pattern was already decided in STATE.md; `QWebEngineCookieStore.cookieAdded` in subprocess context is flagged as a concern requiring a proof-of-concept — this research documents what needs to be proven.

Phase 40 reintroduces subprocess usage (`oauth_helper.py`). PKG-03 in REQUIREMENTS.md requires all subprocess launches go through a centralized `_popen()` helper with `CREATE_NO_WINDOW` on Windows. That helper does not yet exist; the plan must create it.

**Primary recommendation:** Single `oauth_helper.py` with `--mode` flag (`twitch` / `google`). Implement `_popen()` helper in `musicstreamer/subprocess_utils.py`. Install `python3-pyside6.qtwebenginewidgets` as Wave 0 step. Use `QProcess` (not `subprocess`) for subprocess launch from Qt main thread to avoid threading complications.

---

## Standard Stack

### Core (all existing dependencies)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| PySide6 | 6.9.2 | Qt dialogs, QMenu, QSS | Installed [VERIFIED: pip show] |
| PySide6.QtWebEngineWidgets | 6.9.2 | QWebEngineView for OAuth | NOT installed — available via apt [VERIFIED: apt list] |
| platformdirs | >=4.3 | paths.py root resolution | Installed [VERIFIED: pyproject.toml] |
| sqlite3 (stdlib) | — | accent_color setting persistence | In use via repo.py |

### Subprocess Helper Runtime
| Component | Notes |
|-----------|-------|
| `oauth_helper.py` | New script in `musicstreamer/` or project root; must be launchable as `python -m musicstreamer.oauth_helper --mode twitch` |
| `QProcess` | Use over `subprocess.Popen` for subprocess launch from Qt main thread — no threading complications, integrates with Qt event loop |
| `python3-pyside6.qtwebenginewidgets` | Must be installed: `sudo apt install python3-pyside6.qtwebenginewidgets` |

**Installation (new):**
```bash
sudo apt install python3-pyside6.qtwebenginewidgets
```

**Version verification:** PySide6 6.9.2 confirmed [VERIFIED: pip show PySide6 on target machine]

---

## Architecture Patterns

### New Files This Phase
```
musicstreamer/
├── oauth_helper.py          # Standalone OAuth subprocess (Twitch + Google modes)
├── subprocess_utils.py      # _popen() helper — PKG-03 centralized launcher
├── ui_qt/
│   ├── accounts_dialog.py   # AccountsDialog (UI-08)
│   ├── cookie_import_dialog.py  # CookieImportDialog (UI-09)
│   └── accent_color_dialog.py  # AccentColorDialog (UI-11)
tests/
├── test_accounts_dialog.py
├── test_cookie_import_dialog.py
└── test_accent_color_dialog.py
```

### Pattern 1: QMenu from QMenuBar (Hamburger)
**What:** Replace placeholder `menubar.addMenu("≡")` with a populated `QMenu`.
**Current state:** `main_window.py` line 61 does `menubar.addMenu("≡")` and discards the return value — it's a true placeholder.

```python
# Source: [ASSUMED] — standard PySide6 QMenu wiring pattern
menubar = self.menuBar()
menu = menubar.addMenu("\u2261")  # returns QMenu

act_discover = menu.addAction("Discover Stations")
act_discover.triggered.connect(self._open_discovery_dialog)

act_import = menu.addAction("Import Stations")
act_import.triggered.connect(self._open_import_dialog)

menu.addSeparator()

act_accent = menu.addAction("Accent Color")
act_accent.triggered.connect(self._open_accent_dialog)
# ... etc

act_export = menu.addAction("Export Settings")
act_export.setEnabled(False)
act_export.setToolTip("Coming in a future update")
```

**DiscoveryDialog constructor requires:** `(player, repo, toast_callback, parent)` — `toast_callback` must be `self.show_toast` [VERIFIED: discovery_dialog.py line 144].
**ImportDialog** — must check constructor signature before wiring (see Open Questions).

### Pattern 2: QProcess for Subprocess OAuth Helper
**What:** Launch `oauth_helper.py` from main process, wait for exit, read result from stdout or a temp file.
**Why QProcess over subprocess:** Integrates with Qt event loop; `finished` signal fires on the main thread; no thread-safety concerns.

```python
# Source: [ASSUMED] — standard QProcess pattern
from PySide6.QtCore import QProcess

self._oauth_proc = QProcess(self)
self._oauth_proc.finished.connect(self._on_oauth_finished)
self._oauth_proc.start(sys.executable, ["-m", "musicstreamer.oauth_helper", "--mode", "twitch"])
```

**Token readback:** Read from stdout via `self._oauth_proc.readAllStandardOutput()` in the `finished` slot. This avoids temp file cleanup. [ASSUMED]

### Pattern 3: subprocess_utils._popen() (PKG-03)
**What:** Centralized subprocess launcher that adds `CREATE_NO_WINDOW` on Windows.

```python
# Source: [ASSUMED]
import subprocess, sys

def _popen(args, **kwargs):
    """Launch subprocess. Adds CREATE_NO_WINDOW on Windows (PKG-03)."""
    if sys.platform == "win32":
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    return subprocess.Popen(args, **kwargs)
```

Note: Since this phase uses `QProcess` (not `subprocess.Popen`) for OAuth, `_popen()` is needed for completeness per PKG-03 but `QProcess` handles `CREATE_NO_WINDOW` equivalent via `QProcess.setCreateProcessArgumentsModifier` on Windows — or QProcess naturally handles this via Qt's process spawning. [ASSUMED — verify on Windows later] Either way, creating `subprocess_utils.py` now satisfies the PKG-03 "centralized helper" requirement.

### Pattern 4: build_accent_qss() — Qt QSS vs GTK CSS
**What:** `accent_utils.build_accent_css()` generates GTK CSS (targets `button.suggested-action`, `scale trough highlight`). A new `build_accent_qss()` function is needed targeting Qt QSS selectors.

**Existing selectors to target** (identified from codebase grep):
- `_CHIP_QSS` in `edit_station_dialog.py` and `station_list_panel.py` uses `palette(highlight)` — accent color should override this
- `now_playing_panel.py` uses `palette(highlight)` for the star/play buttons — check

```python
# Source: [ASSUMED] — QSS selector pattern based on existing _CHIP_QSS patterns
def build_accent_qss(hex_value: str) -> str:
    """Return Qt QSS overriding accent-colored widgets with hex_value."""
    return (
        f"QPushButton[chipState='selected'] {{\n"
        f"    background-color: {hex_value};\n"
        f"    border-color: {hex_value};\n"
        f"    color: white;\n"
        f"}}\n"
        f"QSlider::sub-page:horizontal {{\n"
        f"    background-color: {hex_value};\n"
        f"}}\n"
    )
```

D-11 specifies targeting: `QPushButton` highlight states, `QSlider::sub-page`, chip selected states, segmented control active state. The planner should verify actual selectors in `station_list_panel.py`, `now_playing_panel.py`, and `edit_station_dialog.py` before writing the function.

**Application:** `QApplication.instance().setStyleSheet(qss)` applies globally. On Reset, call `QApplication.instance().setStyleSheet("")`.

### Pattern 5: AccentDialog Live Preview
**What:** On swatch click or valid hex entry, immediately preview by calling `QApplication.instance().setStyleSheet(build_accent_qss(hex))`. On Cancel, restore previous QSS.

```python
# Pattern: save_original_qss in __init__, restore on reject
def __init__(self, ...):
    self._original_qss = QApplication.instance().styleSheet()

def reject(self):
    QApplication.instance().setStyleSheet(self._original_qss)
    super().reject()
```
[ASSUMED]

### Pattern 6: Netscape Cookie Format Validation
**What:** After file import or paste, validate before writing to `cookies_path()`.

```python
# Netscape cookie format: tab-separated, lines starting with # are comments
# Required: at least one line with .youtube.com domain
def _validate_youtube_cookies(text: str) -> bool:
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 6 and ".youtube.com" in parts[0]:
            return True
    return False
```
[ASSUMED]

### Anti-Patterns to Avoid

- **Calling `QWebEngineView` in main process:** Adds 130MB to startup. Always use subprocess (D-02, D-07).
- **Lambda slots for QProcess.finished:** Lifetime risk (QA-05). Use bound methods.
- **Setting `QApplication.styleSheet()` directly without saving original:** Breaks Reset. Save before applying preview.
- **Writing cookies before validation:** D-08 requires validation first — check non-empty + `.youtube.com` domain line before `open(..., 'w')`.
- **Modal `QProcess.waitForFinished()` blocking the event loop:** Use `QProcess.finished` signal instead.
- **Importing `QtWebEngineWidgets` at module top of oauth_helper.py before ensuring the package is installed:** The import error surfaces clearly, but the plan must include the apt install step.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Hex color validation | Custom regex | `accent_utils._is_valid_hex()` | Already exists, tested |
| Accent presets | Hardcode in dialog | `constants.ACCENT_PRESETS` | Already defined with correct 8 colors |
| Token/cookie delete | Custom file ops | `constants.clear_twitch_token()`, `constants.clear_cookies()` | Already exist |
| Setting persistence | Direct file write | `repo.set_setting() / get_setting()` | Already used for accent_color |
| File paths | Hardcode | `paths.twitch_token_path()`, `paths.cookies_path()`, `paths.accent_css_path()` | platformdirs-rooted, test-hookable |
| Toast feedback | Custom notification | `main_window.show_toast()` | Standard pattern in this codebase |

---

## Common Pitfalls

### Pitfall 1: QWebEngineCookieStore.cookieAdded in subprocess
**What goes wrong:** `cookieAdded` signal is emitted during page load, but it fires for ALL cookies including session cookies. It does not fire for cookies set via JavaScript after the page loads. Some Google login flows set cookies post-JS-execution which may not appear in `cookieAdded`.
**Why it happens:** Qt WebEngine's cookie store events are tied to the render process lifecycle.
**How to avoid:** The STATE.md note says "needs proof-of-concept before planning." The plan should include a Wave 0 spike task: launch `oauth_helper.py --mode google` manually and confirm that `cookieAdded` fires for the relevant `.youtube.com` and `.google.com` cookies after login.
**Warning signs:** Cookie file written but empty or missing `.youtube.com` lines → D-08 validation catches this.
**Confidence:** LOW — this is the known blocker from STATE.md. The plan should account for fallback (e.g., dump all cookies from `QNetworkCookieStore` on page load complete, or use a different extraction approach).

### Pitfall 2: QProcess vs subprocess for OAuth
**What goes wrong:** Using `subprocess.Popen` from Qt main thread is fine, but reading stdout synchronously blocks the event loop.
**How to avoid:** Use `QProcess` with the `finished` signal. Read stdout in the finished slot via `proc.readAllStandardOutput().data().decode()`.

### Pitfall 3: oauth_helper.py import path
**What goes wrong:** `python -m musicstreamer.oauth_helper` fails if oauth_helper.py is not in the package (no `__init__` registration needed but must be importable).
**How to avoid:** Place `oauth_helper.py` inside `musicstreamer/` package. Launch via `sys.executable + ["-m", "musicstreamer.oauth_helper", "--mode", "..."]`.

### Pitfall 4: AccentColorDialog swatch lifetime (QA-05)
**What goes wrong:** Connecting swatch QPushButton.clicked with a lambda that captures `hex_value` — lambda holds no reference to the button, button gets GC'd if stored only in a layout.
**How to avoid:** Keep swatch buttons as instance attributes list (e.g., `self._swatches`). Use `functools.partial` or an indexed bound method rather than closures. [ASSUMED]

### Pitfall 5: pytest-qt INTERNALERROR (current state)
**What goes wrong:** `python -m pytest` currently fails with `INTERNALERROR: PySide6 has no attribute QtTest`. This is a `pytest-qt` version compatibility issue with the system-installed PySide6 6.9.2 vs the pip-installed `pytest-qt 4.4.0`.
**Impact:** Tests cannot run as-is. All new tests for Phase 40 will have the same issue.
**How to avoid:** Wave 0 must investigate and fix the pytest-qt compatibility problem. Options: upgrade pytest-qt (`pip install pytest-qt --upgrade`), or patch conftest to avoid QtTest dependency. [VERIFIED: reproduced on machine]

### Pitfall 6: Reintroducing subprocess — PKG-03 compliance
**What goes wrong:** Phase 40 reintroduces subprocess usage after Plan 35-06 eliminated it. PKG-03 requires all subprocess launches use a centralized `_popen()` helper with `CREATE_NO_WINDOW` on Windows.
**How to avoid:** Create `musicstreamer/subprocess_utils.py` with `_popen()`. However: since this phase uses `QProcess` (not raw subprocess) to launch `oauth_helper.py`, `QProcess` inherently handles the Windows console window issue. The plan should note this and create the `subprocess_utils.py` stub for PKG-03 compliance while using `QProcess` for the actual OAuth launches.

---

## Code Examples

### Hamburger QMenu wiring
```python
# Source: [ASSUMED] — extends existing main_window.py line 61
menubar = self.menuBar()
# Remove the placeholder menu first — or replace addMenu return value usage
# Current code: menubar.addMenu("\u2261") — returns QMenu, currently unused
# Fix: capture the return value
_menu = menubar.addMenu("\u2261")
act = _menu.addAction("Discover Stations")
act.triggered.connect(self._open_discovery_dialog)
```

### AccentColorDialog startup load in MainWindow.__init__
```python
# Source: [ASSUMED] — D-12 pattern
from musicstreamer import paths, repo as repo_mod

saved = self._repo.get_setting("accent_color", None)
if saved:
    from musicstreamer.accent_utils import build_accent_qss
    from PySide6.QtWidgets import QApplication
    QApplication.instance().setStyleSheet(build_accent_qss(saved))
```

### QProcess OAuth launch
```python
# Source: [ASSUMED]
from PySide6.QtCore import QProcess
import sys

self._oauth_proc = QProcess(self)
self._oauth_proc.setProcessChannelMode(QProcess.MergedChannels)
self._oauth_proc.finished.connect(self._on_twitch_oauth_finished)
self._oauth_proc.start(sys.executable, ["-m", "musicstreamer.oauth_helper", "--mode", "twitch"])

def _on_twitch_oauth_finished(self, exit_code, exit_status):
    token = self._oauth_proc.readAllStandardOutput().data().decode().strip()
    if token:
        import os
        with open(paths.twitch_token_path(), "w") as f:
            f.write(token)
        os.chmod(paths.twitch_token_path(), 0o600)
        self._update_status()
```

### Cookie file write with permissions
```python
# Source: [ASSUMED]
import os
from musicstreamer import paths

def _write_cookies(text: str) -> None:
    p = paths.cookies_path()
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(p, 0o600)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| GTK CSS `build_accent_css()` | Qt QSS `build_accent_qss()` (new) | Phase 40 | New function alongside old one |
| No subprocess in musicstreamer/ | `oauth_helper.py` subprocess | Phase 40 | PKG-03 `_popen()` helper required |
| Hamburger menu placeholder | Real QMenu with actions | Phase 40 | Replaces empty `addMenu("≡")` at line 61 |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `QProcess.readAllStandardOutput()` in `finished` slot returns complete stdout | Architecture Patterns, Pattern 2 | Token not captured; subprocess could be switched to temp file approach instead |
| A2 | `QProcess` on Windows avoids console window without `CREATE_NO_WINDOW` flag | Pitfall 6 | Need explicit flag in subprocess_utils.py; QProcess may still show console |
| A3 | `functools.partial` or indexed bound method avoids QA-05 lifetime issue for swatch buttons | Pitfall 4 | Widget GC'd; swatch clicks stop working |
| A4 | `QApplication.instance().setStyleSheet("")` on Reset restores all styling without visual regression | Pattern 5 | Wiped stylesheet removes other QSS (e.g., chip styles) — may need to selectively remove accent rules |
| A5 | Google cookies for YouTube are captured by `QWebEngineCookieStore.cookieAdded` after login | Pitfall 1 | Core feature broken; need alternate extraction approach |
| A6 | `build_accent_qss()` targeting `QPushButton[chipState='selected']` and `QSlider::sub-page:horizontal` is sufficient for full accent coverage | Pattern 4 | Some accent-colored widgets missed; need broader selector audit |

---

## Open Questions

1. **ImportDialog constructor signature**
   - What we know: `ImportDialog` exists in `musicstreamer/ui_qt/import_dialog.py` (from Phase 39)
   - What's unclear: constructor args — does it take `(repo, toast_callback, parent)` or `(player, repo, toast_callback, parent)`?
   - Recommendation: Read `import_dialog.py` header before writing the hamburger wiring. The planner should check this file.

2. **pytest-qt INTERNALERROR fix**
   - What we know: `pytest-qt 4.4.0` fails with `PySide6 has no attribute QtTest` on PySide6 6.9.2
   - What's unclear: whether upgrading pytest-qt resolves it or requires a conftest workaround
   - Recommendation: Wave 0 task to run `pip install --upgrade pytest-qt` (in venv or user-level install) and verify tests run. If `pip install` is blocked by externally-managed-environment, check if a newer apt package exists or use `--break-system-packages` flag.

3. **Hamburger menu — replace vs reconfigure placeholder**
   - What we know: `menubar.addMenu("≡")` currently discards the return value
   - What's unclear: whether to clear `menuBar()` and re-add, or capture return value and populate on init
   - Recommendation: Capture the return value in `__init__` and call `addAction()` / `addSeparator()` on it. No need to remove the placeholder menu since it IS the hamburger menu — just populate it.

4. **Global QSS reset on AccentDialog Reset action**
   - What we know: D-10 says "Reset clears the setting and removes the QSS override, returning to system default palette"
   - What's unclear: `setStyleSheet("")` clears ALL app-level QSS including any non-accent rules set elsewhere
   - Recommendation: Check whether any other QSS is set globally via `QApplication.setStyleSheet()`. If not, `setStyleSheet("")` is safe. If chip QSS or other styles are applied globally, the planner must scope the reset more carefully.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PySide6 | All dialogs | Yes | 6.9.2 | — |
| PySide6.QtWebEngineWidgets | oauth_helper.py | No | — | Install via apt: `sudo apt install python3-pyside6.qtwebenginewidgets` |
| python3-pyside6.qtwebenginewidgets (apt) | oauth_helper.py | Available in repo | 6.9.2 | — |
| pytest-qt | Tests | Broken (4.4.0 incompat) | 4.4.0 | Upgrade or patch |

**Missing dependencies with no fallback:**
- `python3-pyside6.qtwebenginewidgets` — blocks oauth_helper.py; must install before Wave 1 (oauth dialogs)

**Missing dependencies with fallback:**
- pytest-qt version incompatibility — needs upgrade; all phases blocked until fixed

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-qt 4.4.0 (BROKEN — needs fix) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_accent_color_dialog.py -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-08 | AccountsDialog shows Connected/Not connected based on token file | unit | `pytest tests/test_accounts_dialog.py::test_status_display -x` | No — Wave 0 |
| UI-08 | Disconnect deletes token file + shows confirmation | unit | `pytest tests/test_accounts_dialog.py::test_disconnect_deletes_token -x` | No — Wave 0 |
| UI-09 | Cookie file import writes to cookies_path() with 0o600 | unit | `pytest tests/test_cookie_import_dialog.py::test_file_import_writes_with_permissions -x` | No — Wave 0 |
| UI-09 | Cookie paste validates .youtube.com domain line | unit | `pytest tests/test_cookie_import_dialog.py::test_paste_validation -x` | No — Wave 0 |
| UI-10 | Hamburger menu has all 6 action groups | unit | `pytest tests/test_main_window_integration.py::test_hamburger_menu_actions -x` | No — Wave 0 |
| UI-10 | Export/Import Settings actions are disabled | unit | `pytest tests/test_main_window_integration.py::test_sync_actions_disabled -x` | No — Wave 0 |
| UI-11 | AccentColorDialog apply saves to repo + writes accent.css | unit | `pytest tests/test_accent_color_dialog.py::test_apply_saves_setting -x` | No — Wave 0 |
| UI-11 | Accent color loaded on MainWindow startup | unit | `pytest tests/test_main_window_integration.py::test_accent_loaded_on_startup -x` | No — Wave 0 |
| UI-11 | build_accent_qss() produces valid QSS for all presets | unit | `pytest tests/test_accent_provider.py::test_build_accent_qss -x` | No — extend existing file |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_accent_provider.py tests/test_accounts_dialog.py tests/test_cookie_import_dialog.py tests/test_accent_color_dialog.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] Fix pytest-qt: `pip install --upgrade pytest-qt` (or apt equivalent)
- [ ] `sudo apt install python3-pyside6.qtwebenginewidgets` (required for oauth_helper.py)
- [ ] `tests/test_accounts_dialog.py` — covers UI-08 (no QWebEngineView in tests; mock the QProcess)
- [ ] `tests/test_cookie_import_dialog.py` — covers UI-09 (file/paste paths; Google Login is manual-only)
- [ ] `tests/test_accent_color_dialog.py` — covers UI-11
- [ ] Add `test_build_accent_qss` to `tests/test_accent_provider.py`
- [ ] Add `test_hamburger_menu_actions`, `test_sync_actions_disabled`, `test_accent_loaded_on_startup` to `tests/test_main_window_integration.py`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes (Twitch OAuth token) | Token written with `0o600`; subprocess isolation; no token in logs |
| V3 Session Management | No | — |
| V4 Access Control | No | — |
| V5 Input Validation | Yes | `_is_valid_hex()` for accent; `.youtube.com` domain check for cookies; `QLabel.setTextFormat(Qt.PlainText)` for any untrusted text |
| V6 Cryptography | No | Tokens stored as plaintext files with restricted permissions — consistent with v1.5 approach |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Token written to world-readable file | Information disclosure | `os.chmod(path, 0o600)` immediately after write |
| Cookie file pasted with malicious content | Tampering | Validate Netscape format + `.youtube.com` domain before accepting |
| Subprocess PATH injection | Elevation of privilege | Use `sys.executable` (absolute path) as the interpreter; avoid `shell=True` |
| QLabel rich-text injection from station names in dialogs | Spoofing | `setTextFormat(Qt.PlainText)` on all QLabel instances showing external data (established pattern from Phase 39) |
| OAuth token visible in process stdout | Information disclosure | Token printed to stdout is only read by the parent process via QProcess; no logging of stdout content |

---

## Sources

### Primary (HIGH confidence)
- Codebase: `musicstreamer/accent_utils.py` — existing `_is_valid_hex()`, `build_accent_css()` [VERIFIED: Read]
- Codebase: `musicstreamer/constants.py` — `ACCENT_PRESETS` (8 colors), `clear_twitch_token()`, `clear_cookies()` [VERIFIED: Read]
- Codebase: `musicstreamer/paths.py` — all three file path accessors [VERIFIED: Read]
- Codebase: `musicstreamer/ui_qt/main_window.py` line 61 — hamburger placeholder [VERIFIED: Read]
- Codebase: `musicstreamer/ui_qt/discovery_dialog.py` — constructor signature `(player, repo, toast_callback, parent)` [VERIFIED: Read]
- System: `python -c "from PySide6.QtWebEngineWidgets import QWebEngineView"` → `ModuleNotFoundError` [VERIFIED: Bash]
- System: `apt list | grep pyside6` → `python3-pyside6.qtwebenginewidgets` available [VERIFIED: Bash]
- System: `pip show PySide6` → 6.9.2 [VERIFIED: Bash]
- System: pytest-qt INTERNALERROR on PySide6 6.9.2 [VERIFIED: Bash]
- `.planning/phases/40-auth-dialogs-accent/40-CONTEXT.md` — all locked decisions [VERIFIED: Read]

### Tertiary (LOW confidence / ASSUMED)
- `QProcess.readAllStandardOutput()` for token readback — standard Qt pattern, not verified against PySide6 6.9.2 docs in this session
- `QWebEngineCookieStore.cookieAdded` behavior for Google login cookies — unverified, flagged in STATE.md
- Global `QApplication.setStyleSheet("")` safety for Reset — not verified against current stylesheet usage

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PySide6 version verified, WebEngine availability verified
- Architecture: MEDIUM — patterns established from Phase 39 codebase; subprocess/QProcess patterns assumed
- Pitfalls: HIGH for QtWebEngine absence and pytest-qt breakage (verified); LOW for QWebEngineCookieStore.cookieAdded behavior (known unknowns)
- Security: HIGH — 0o600 permissions and `sys.executable` patterns are established in this codebase

**Research date:** 2026-04-13
**Valid until:** 2026-05-13 (30 days — PySide6 6.9.2 is stable)
