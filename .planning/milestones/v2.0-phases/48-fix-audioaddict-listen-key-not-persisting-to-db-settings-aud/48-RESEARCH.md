# Phase 48: Fix AudioAddict listen key not persisting to DB - Research

**Researched:** 2026-04-19
**Domain:** PySide6 dialog persistence + small UX extension (no new framework adoption)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 (Save trigger — success only):** Write `repo.set_setting("audioaddict_listen_key", key)` in `_on_aa_fetch_complete` after `aa_import.fetch_channels_multi` returns a non-empty list. Invalid-key responses (empty list, ValueError, HTTP 401/403) do NOT persist.

**D-02:** No `textChanged` write, no explicit Save button.

**D-03:** `ImportDialog.__init__` prefills from `repo.get_setting("audioaddict_listen_key", "")` (one read on construction).

**D-04:** Dual surface — ImportDialog owns edit + auto-save; AccountsDialog gets view-status + clear only. AccountsDialog NEVER writes a key.

**D-05:** AA group in AccountsDialog mirrors the Twitch group at `accounts_dialog.py:44-56`:
- `QGroupBox("AudioAddict")` + `QLabel` (Qt.TextFormat.PlainText) + one `QPushButton`.
- Label: `"Saved"` when `get_setting("audioaddict_listen_key", "")` non-empty; `"Not saved"` otherwise.
- Button: `"Clear saved key"` enabled when saved; `"No key saved"` disabled when empty.

**D-06:** Clear prompts `QMessageBox.question` (Yes/No, default **No**). Yes → `set_setting("audioaddict_listen_key", "")` + refresh status. No → no-op.

**D-07:** `AccountsDialog._update_status()` extended to refresh BOTH groups; Twitch logic unchanged.

**D-08:** `QLineEdit.EchoMode.Password` at construction.

**D-09:** Icon-only Show toggle via `QToolButton.setCheckable(True)`. Checked → `EchoMode.Normal`; unchecked → `EchoMode.Password`. Icon: `QIcon.fromTheme("view-reveal-symbolic", QIcon.fromTheme("document-properties"))` with local fallback SVG only if neither theme icon is available.

**D-10:** Tooltip: `"Show key"` when unchecked, `"Hide key"` when checked.

**D-11:** Primary regression test — widget-level save → reopen → readback using pytest-qt + FakeRepo (full steps specified in CONTEXT.md).

**D-12:** Seven targeted tests — `test_import_dialog_prefills_key_on_open`, `test_import_dialog_does_not_persist_on_failed_fetch`, `test_accounts_dialog_aa_group_reflects_saved_status`, `test_accounts_dialog_clear_aa_key_requires_confirm`, `test_aa_key_field_masked_by_default`, `test_aa_key_show_toggle_flips_echo_mode`, `test_settings_export_still_excludes_aa_key` (extend existing test in `tests/test_settings_export.py`).

**D-13:** No subprocess/app-restart simulation — widget-level reopen with shared FakeRepo covers the failure path.

### Claude's Discretion

- **AA group layout in AccountsDialog** — copy the Twitch GroupBox/VBoxLayout/Label/Button geometry. Planner MAY add a small `QLabel` hint with the AA account-settings URL.
- **`ImportDialog` `repo` threading** — scout note in CONTEXT said "confirm during planning"; **VERIFIED** in research below that `ImportDialog.__init__` does NOT currently take a `repo` parameter. Planner MUST add `repo` as a required kwarg and update the sole caller.
- **Show-toggle icon choice** — try theme icon first (`view-reveal-symbolic` / `view-conceal-symbolic` are standard freedesktop symbolic names); add a bespoke SVG to `icons.qrc` only if theme lookup fails across GNOME + non-GNOME. Not worth a new SVG if a theme icon renders.
- **Save trigger placement in the fetch-success slot** — before `_set_aa_busy(False)` preferred, so regression test doesn't wait for UI polling. Either order is correct.

### Deferred Ideas (OUT OF SCOPE)

- AA key validation on edit (pre-fetch network call).
- OS keyring / DPAPI / Secret Service encrypted storage.
- "Remember my key" opt-out checkbox (persist-by-default is project convention).
- Multi-account AA (multiple keys, switcher).
- Masked-preview display (first/last 4 chars) in AccountsDialog.
- AudioAddict fetch/import logic changes in `aa_import.py` beyond the persistence hook.
- Phase 42 read-only-DB silent-import issue (owned by Phase 42).
</user_constraints>

## Summary

This is a narrowly-scoped bug fix: `ImportDialog._on_aa_import_clicked` never writes the AA listen key to SQLite, so the Phase 42 `_EXCLUDED_SETTINGS` contract reserves a key name that nothing populates. The fix is three surgical edits plus an AA group in `AccountsDialog` and seven pytest-qt tests.

Root cause verified at source level:
- `musicstreamer/ui_qt/import_dialog.py:397-412` — `_on_aa_import_clicked` reads `self._aa_key.text().strip()` and passes directly to `_AaFetchWorker`. No `set_setting` call exists in the file.
- `musicstreamer/ui_qt/import_dialog.py:166` — `ImportDialog.__init__(toast_callback, parent=None)` — **`repo` is NOT a current parameter**. CONTEXT's scout assumption was wrong; planner must add it.
- `musicstreamer/ui_qt/import_dialog.py:510` — sole caller in `main_window._open_import_dialog`: `ImportDialog(self.show_toast, parent=self)`. Update to `ImportDialog(self.show_toast, self._repo, parent=self)` (or keyword).

**Primary recommendation:** Add `repo: Repo` as the second positional parameter to `ImportDialog.__init__`, prefill in `__init__`, persist in `_on_aa_fetch_complete` before `_set_aa_busy(False)`, add AA group to `AccountsDialog` (which must also take `repo`), extend `accounts_dialog._update_status` to refresh both groups. Seven pytest-qt tests + one extended export test cover the behavior.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Listen-key persistence write | Qt dialog layer (`import_dialog.py`) | Repo (`set_setting`) | Gate is UI-level (successful fetch signal) — must live where the signal is bound |
| Listen-key persistence read | Qt dialog layer (prefill in `__init__`) | Repo (`get_setting`) | One-shot read at dialog construction; no event-driven refresh needed |
| Listen-key clear | Qt dialog layer (`accounts_dialog.py`) | Repo (`set_setting("", "")`) | Mirrors Twitch disconnect pattern (UI owns confirm + state refresh) |
| Display masking / show toggle | Qt widget layer (`QLineEdit` + `QToolButton`) | — | Pure view concern; no persistence interaction |
| Export exclusion | Pure python (`settings_export._EXCLUDED_SETTINGS`) | — | Already wired in Phase 42; just extend existing test |
| Status label reflection | Qt dialog layer (`_update_status`) | Repo (read-only) | Polled at `__init__` and after Clear — no long-lived watch |

All capabilities remain inside existing tiers. No new layer introduced.

## Phase Requirements

No dedicated REQ IDs were issued for this phase. Coverage is driven directly from CONTEXT D-01..D-13. The Validation Architecture section below maps each decision to its test.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | existing project pin | Qt widget layer | Already the project's UI framework — no change |
| pytest-qt | existing project pin | Widget-level tests | Already used in `test_accent_color_dialog.py` |

No new dependencies. This phase adds code only within the existing stack.

### Supporting (already in project, used here)
| Component | Purpose | File |
|-----------|---------|------|
| `Repo.get_setting` / `set_setting` | Settings persistence | `musicstreamer/repo.py:348-359` |
| `_EXCLUDED_SETTINGS = {"audioaddict_listen_key"}` | Export guard | `musicstreamer/settings_export.py:29` |
| Twitch group template | AA group layout model | `musicstreamer/ui_qt/accounts_dialog.py:44-107` |
| FakeRepo pattern | Test fixture | `tests/test_accent_color_dialog.py:19-27` |

### Alternatives Considered
Not applicable — no library choices to make. The fix rides existing project contracts.

## Architecture Patterns

### System Architecture Diagram

```
User types key in ImportDialog AA tab
          |
          v
  [_on_aa_import_clicked] --> spawn _AaFetchWorker(key) --> aa_import.fetch_channels_multi
                                                                          |
                                          +-- non-empty list --+          +-- raises / empty -+
                                          v                    |          v                   |
                            [_on_aa_fetch_complete]        [_on_aa_fetch_error]
                                          |                                |
                                          v                                v
                   repo.set_setting(                        (NO WRITE — key discarded)
                     "audioaddict_listen_key", key)
                                          |
                                          v
                          SQLite settings table
                                          ^
                                          |
                      +-------------------+-----------------------+
                      |                                           |
      [ImportDialog.__init__]                      [AccountsDialog AA group]
      get_setting("audioaddict_listen_key", "")    get_setting(...) → "Saved" / "Not saved"
         -> prefill _aa_key                            Clear btn → QMessageBox.question
         -> setEchoMode(Password)                      -> Yes: set_setting("audioaddict_listen_key", "")
                                                       -> refresh both Twitch + AA labels

      settings_export.build_zip
         -> excludes audioaddict_listen_key via _EXCLUDED_SETTINGS  (UNCHANGED — regression guard test)
```

### Recommended Code Touch Points

```
musicstreamer/ui_qt/
├── import_dialog.py        # __init__ add repo kwarg; prefill; Password echoMode;
│                           # Show toggle QToolButton; _on_aa_fetch_complete adds set_setting
├── accounts_dialog.py      # __init__ takes repo; add AA QGroupBox; extend _update_status
└── main_window.py          # update ImportDialog(...) call to pass self._repo;
                            # update AccountsDialog(...) call to pass self._repo

tests/
├── test_import_dialog.py         # currently yt_import library tests — ADD widget tests or split file
├── test_accounts_dialog.py       # add AA group tests
└── test_settings_export.py       # extend test_credentials_excluded with non-empty saved value
```

### Pattern 1: Constructor-time prefill + echoMode (from D-03 / D-08)

```python
# musicstreamer/ui_qt/import_dialog.py — inside _build_aa_tab()
# Source: verified pattern in test_accent_color_dialog.py:101-107
self._aa_key = QLineEdit()
self._aa_key.setPlaceholderText("AudioAddict listen key")
self._aa_key.setEchoMode(QLineEdit.EchoMode.Password)        # D-08
saved = self._repo.get_setting("audioaddict_listen_key", "")  # D-03
if saved:
    self._aa_key.setText(saved)
```

### Pattern 2: Show/hide toggle (D-09 / D-10)

```python
# Source: PySide6 QLineEdit docs — setEchoMode(QLineEdit.Normal | Password)
#         QIcon.fromTheme fallback is the project convention (see favorites_view.py:190)
from PySide6.QtWidgets import QToolButton
from PySide6.QtGui import QIcon

self._aa_show_btn = QToolButton()
self._aa_show_btn.setCheckable(True)
self._aa_show_btn.setChecked(False)
self._aa_show_btn.setIcon(
    QIcon.fromTheme(
        "view-reveal-symbolic",
        QIcon.fromTheme("document-properties"),
    )
)
self._aa_show_btn.setToolTip("Show key")
self._aa_show_btn.toggled.connect(self._on_aa_show_toggled)

def _on_aa_show_toggled(self, checked: bool) -> None:
    if checked:
        self._aa_key.setEchoMode(QLineEdit.EchoMode.Normal)
        self._aa_show_btn.setToolTip("Hide key")
    else:
        self._aa_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._aa_show_btn.setToolTip("Show key")
```

Layout: wrap `self._aa_key` + `self._aa_show_btn` in a `QHBoxLayout` and place that row in the form row (replacing the current raw `form.addRow("API Key:", self._aa_key)`). Project convention from existing dialogs is to combine widgets via a container `QWidget` with the HBox, then `form.addRow("API Key:", container)`.

### Pattern 3: Save on success (D-01)

```python
# musicstreamer/ui_qt/import_dialog.py — _on_aa_fetch_complete
def _on_aa_fetch_complete(self, channels: list):
    # D-01: persist BEFORE UI updates — regression test reads setting right after slot runs
    key = self._aa_key.text().strip()
    if key and channels:  # success gate: non-empty fetch result
        self._repo.set_setting("audioaddict_listen_key", key)

    self._aa_channels = channels
    total = len(channels)
    # ... existing body unchanged ...
```

Note: `_AaFetchWorker` emits `finished(list)` on success and `error(str)` on failure (invalid_key, no_channels, network) — `fetch_channels_multi` raising `ValueError("no_channels")` for an empty list is caught and routed to `error`, so `_on_aa_fetch_complete` only fires on genuinely successful fetch with `len(channels) > 0`. The `if key and channels` guard is defensive belt-and-suspenders against any future refactor that routes empty lists through success.

### Pattern 4: AA group in AccountsDialog (D-05 / D-06 / D-07)

```python
# musicstreamer/ui_qt/accounts_dialog.py — extend __init__
# Source: Twitch group template at lines 44-56, disconnect pattern at 94-107

def __init__(self, repo, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self._repo = repo
    # ... existing Twitch group construction ...

    # AudioAddict group (new)
    aa_box = QGroupBox("AudioAddict", self)
    aa_layout = QVBoxLayout(aa_box)
    self._aa_status_label = QLabel(self)
    self._aa_status_label.setTextFormat(Qt.TextFormat.PlainText)  # T-40-04 parity
    self._aa_status_label.setFont(status_font)
    aa_layout.addWidget(self._aa_status_label)

    self._aa_clear_btn = QPushButton(self)
    self._aa_clear_btn.clicked.connect(self._on_aa_clear_clicked)
    aa_layout.addWidget(self._aa_clear_btn)

    layout.insertWidget(layout.count() - 1, aa_box)  # above the Close button box
    self._update_status()

def _is_aa_key_saved(self) -> bool:
    return bool(self._repo.get_setting("audioaddict_listen_key", ""))

def _update_status(self) -> None:
    # Existing Twitch body unchanged
    # ... (keeps `_oauth_proc`, `_is_connected` branches) ...

    # AA branch (new)
    if self._is_aa_key_saved():
        self._aa_status_label.setText("Saved")
        self._aa_clear_btn.setText("Clear saved key")
        self._aa_clear_btn.setEnabled(True)
    else:
        self._aa_status_label.setText("Not saved")
        self._aa_clear_btn.setText("No key saved")
        self._aa_clear_btn.setEnabled(False)

def _on_aa_clear_clicked(self) -> None:
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

### Anti-Patterns to Avoid

- **Writing the key on `textChanged`** — persists every keystroke of typing, including half-typed/wrong keys. D-01 explicitly rules this out.
- **Writing the key in `_on_aa_import_clicked`** (before fetch) — persists unvalidated input; a typo gets saved and has to be manually cleared.
- **Constructing a new `Repo(db_connect())` inside dialog code** — violates the established pattern (dialogs receive `repo` from `MainWindow`). The existing workers (`_AaImportWorker`, `_YtImportWorker`) construct thread-local `Repo(db_connect())` **only because they run on `QThread.run()` and SQLite connections are not thread-safe** (Pitfall 3 note at `import_dialog.py:11-15`). The main-thread dialog code must use the injected `repo`.
- **Using plain string `"Password"`** for echoMode — always `QLineEdit.EchoMode.Password` (the enum). Legacy `QLineEdit.Password` also works but is the pre-Qt6 style; project already uses the `.EchoMode.*` qualified form in similar contexts.
- **Refreshing status on a timer** — status changes are event-driven (dialog open + after Clear). No polling.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Masked input | Custom `****` rendering | `QLineEdit.setEchoMode(Password)` | Native — handles paste, focus, IME, screen readers correctly |
| Confirm dialog | Custom QDialog subclass | `QMessageBox.question(..., Yes\|No, No)` | Already used for Twitch disconnect; default button semantics |
| Settings read/write | New JSON/config file | `repo.get_setting` / `set_setting` | Single-source-of-truth invariant; export contract already wired |
| Export exclusion list | New filter function | Extend `_EXCLUDED_SETTINGS` set | Phase 42 already owns this — the key is already listed |
| Show-toggle icon | New SVG from scratch | `QIcon.fromTheme("view-reveal-symbolic", fallback)` | Freedesktop standard; GNOME, KDE, others all ship it |

**Key insight:** This is an integration fix, not a feature. Every element of the solution — persistence, masking, confirm, export exclusion — has existing project infrastructure; we're just wiring them together.

## Common Pitfalls

### Pitfall 1: `ImportDialog` doesn't currently take `repo`
**What goes wrong:** CONTEXT's scout note said "confirm `repo` at line 161 during planning." It is NOT a parameter. Writing the fix assuming it's already threaded produces `AttributeError: 'ImportDialog' object has no attribute '_repo'`.
**Why it happens:** ImportDialog was built for a thread-isolated model (each worker creates its own `Repo(db_connect())`). Main-thread persistence is genuinely new.
**How to avoid:** Add `repo: Repo` as second positional parameter (after `toast_callback`), update `main_window.py:510` caller. The dialog stores `self._repo = repo` and uses it ONLY on the main thread (in `__init__` prefill and `_on_aa_fetch_complete`) — not inside `_AaFetchWorker.run()`.
**Warning signs:** Any test that instantiates `ImportDialog(lambda *_: None)` without a repo will `TypeError: missing required positional argument: 'repo'` — this is the desired failure mode for old call sites.

### Pitfall 2: `AccountsDialog` also doesn't currently take `repo`
**What goes wrong:** Same issue as Pitfall 1 — `AccountsDialog.__init__(self, parent: QWidget | None = None)` (`accounts_dialog.py:36`) has no `repo`. Twitch uses file-backed paths (`paths.twitch_token_path()`), so it never needed a repo. AA uses `settings` table, so it does.
**How to avoid:** Add `repo` as first positional kwarg (before `parent`). Update `main_window.py:526` caller (`AccountsDialog(parent=self)` → `AccountsDialog(self._repo, parent=self)`).
**Warning signs:** Existing `test_accounts_dialog.py` tests call `AccountsDialog()` with zero args (see lines 45, 57, 80, 100, 119, 141, 165, 194). ALL of these will break — planner must update them to pass a `FakeRepo()` or accept a default `repo=None` shim (NOT recommended — type safety is cheaper than retrofit later).

### Pitfall 3: QThread signal emission order and test timing
**What goes wrong:** D-11 test drives `_AaFetchWorker.finished` directly (stubbed worker) to assert the setting is saved. If the slot calls `set_setting` AFTER `_AaImportWorker.start()`, the test's `qtbot.wait()` may race with the import worker spawning a new thread.
**Why it happens:** `_on_aa_fetch_complete` currently spawns `_AaImportWorker` at the bottom of the slot. If persistence goes after that, the test has to wait for both threads.
**How to avoid:** Put the `set_setting` call at the TOP of `_on_aa_fetch_complete`, before any other work. CONTEXT's "either order is correct; prefer before" is the right call. Test then becomes a simple signal emit + immediate assert.
**Warning signs:** Flaky test — passes locally, fails in CI under load.

### Pitfall 4: Stubbing `_AaFetchWorker` in tests
**What goes wrong:** The worker runs real network I/O (`aa_import.fetch_channels_multi` → HTTP). Tests must not hit the network.
**How to avoid:** Patch `_AaFetchWorker` at the module level with `unittest.mock.patch("musicstreamer.ui_qt.import_dialog._AaFetchWorker", FakeWorker)`, or directly emit signals on a test-owned worker instance. The monkeypatch pattern already used in `test_accounts_dialog.py:73-76` for `QMessageBox.question` shows the project's preferred style.
**Warning signs:** Test takes > 1s; test fails offline; test hits AudioAddict servers.

### Pitfall 5: `test_import_dialog.py` is misleadingly named
**What goes wrong:** `tests/test_import_dialog.py` currently contains only `yt_import` library tests (`test_scan_filters_live_only`, `test_import_skips_duplicate`, etc.) — NOT widget tests. Adding widget tests to this file mixes two concerns; adding them to a new file is cleaner.
**How to avoid:** Planner decides: either (a) add widget tests to the same file with a clear section divider, or (b) rename existing file to `tests/test_yt_import.py` and create a fresh `tests/test_import_dialog.py` for widget tests. **Option (a)** is the smaller-diff path; recommended.
**Warning signs:** Test file grows past 400 lines; IDE test runner output becomes hard to scan.

### Pitfall 6: `QMessageBox.question` monkeypatch shape
**What goes wrong:** Using `monkeypatch.setattr(QMessageBox, "question", lambda *_: ...)` without `staticmethod(...)` or without matching the exact signature can raise `TypeError: question() takes 5 positional arguments but 6 were given`.
**How to avoid:** Follow the exact pattern at `test_accounts_dialog.py:73-76`:
```python
monkeypatch.setattr(
    QMessageBox, "question",
    staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes),
)
```
**Warning signs:** TypeError in test when the dialog's Clear button is clicked.

### Pitfall 7: `QIcon.fromTheme` returns a null icon silently
**What goes wrong:** On non-GNOME environments (Windows, bare KDE, X11 without a theme), `QIcon.fromTheme("view-reveal-symbolic")` returns a null `QIcon`. Button renders with no icon, not with the fallback.
**How to avoid:** Use the two-argument form `QIcon.fromTheme("view-reveal-symbolic", fallback_icon)` — Qt returns the fallback when the theme icon is null. Project's convention at `favorites_view.py:190` uses `QIcon(":/icons/...svg")` as the fallback. For Phase 48, if no existing icon in `icons.qrc` doubles as "show key", use `QIcon.fromTheme("document-properties")` as a secondary theme fallback (D-09). Adding a new SVG to `icons.qrc` is allowed but OUT OF SCOPE if the theme icons render on the dev's GNOME environment.
**Warning signs:** Show toggle button is blank on some machines.

## Runtime State Inventory

> Not applicable. This is a feature-extension phase — no rename/refactor/migration involved.

**Stored data:** None — `audioaddict_listen_key` is a new-ish value (reserved in Phase 42, never populated). No existing rows to migrate.
**Live service config:** None — no external services touch this string.
**OS-registered state:** None.
**Secrets/env vars:** None — key is user-owned data inside the SQLite DB.
**Build artifacts:** None.

## Common Pitfalls (extra)

Already covered above. Additional note on pytest-qt lane:

### Running the tests locally
```bash
pytest tests/test_import_dialog.py tests/test_accounts_dialog.py tests/test_settings_export.py -x
```
pytest-qt's `qtbot` fixture is provided automatically by the project's existing pytest setup (see `test_accent_color_dialog.py`). No new pytest plugin needed.

## Code Examples

### Prefill on construct
```python
# Source: CONTEXT D-03, verified against test_accent_color_dialog.py:101-107
saved = self._repo.get_setting("audioaddict_listen_key", "")
if saved:
    self._aa_key.setText(saved)
```

### Persist on success
```python
# Source: CONTEXT D-01; pattern matches aa_import.import_stations_multi semantics
def _on_aa_fetch_complete(self, channels: list):
    key = self._aa_key.text().strip()
    if key and channels:
        self._repo.set_setting("audioaddict_listen_key", key)
    # ... existing body ...
```

### Confirm-then-clear
```python
# Source: accounts_dialog.py:94-107 (verbatim structural copy with AA strings)
answer = QMessageBox.question(
    self, "Clear AudioAddict key?",
    "This will delete your saved AudioAddict listen key. "
    "You will need to re-enter it from Import Stations.",
    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    QMessageBox.StandardButton.No,
)
if answer == QMessageBox.StandardButton.Yes:
    self._repo.set_setting("audioaddict_listen_key", "")
    self._update_status()
```

### FakeRepo fixture for widget tests
```python
# Source: tests/test_accent_color_dialog.py:19-27
class FakeRepo:
    def __init__(self):
        self._settings: dict[str, str] = {}

    def get_setting(self, key: str, default: str = "") -> str:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `QLineEdit.Password` bare enum | `QLineEdit.EchoMode.Password` fully qualified | Qt6 / PySide6 | Project uses fully qualified form in new code; either renders identically |
| dbus-python for MPRIS | `PySide6.QtDBus` | Phase 36 | No impact here — no DBus in this phase |
| Polling timers for status | Event-driven `_update_status()` calls | Project convention | Already the AccountsDialog pattern; AA group follows suit |

**Deprecated/outdated:**
- Nothing deprecated is being touched.

## Environment Availability

> Skipped — this is a code-only change. PySide6, pytest-qt, SQLite, and Repo are already in the project; no new tools, services, or runtimes.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-qt (already in project) |
| Config file | `pytest.ini` / `pyproject.toml` (already present) |
| Quick run command | `pytest tests/test_import_dialog.py tests/test_accounts_dialog.py tests/test_settings_export.py -x` |
| Full suite command | `pytest -x` |

### Decision → Test Map

| D-ID | Behavior | Test Name | Test Type | Automated Command | File Exists? |
|------|----------|-----------|-----------|-------------------|-------------|
| D-01 | Save only on successful fetch | `test_import_dialog_persists_key_on_successful_fetch` | unit (pytest-qt) | `pytest tests/test_import_dialog.py::test_import_dialog_persists_key_on_successful_fetch -x` | Wave 0 (file exists but wrong scope — must add or split) |
| D-01 (negative) | No save on failed fetch | `test_import_dialog_does_not_persist_on_failed_fetch` | unit (pytest-qt) | `pytest tests/test_import_dialog.py::test_import_dialog_does_not_persist_on_failed_fetch -x` | Wave 0 |
| D-03 | Prefill on open | `test_import_dialog_prefills_key_on_open` | unit (pytest-qt) | `pytest tests/test_import_dialog.py::test_import_dialog_prefills_key_on_open -x` | Wave 0 |
| D-05 | AA group status reflects saved state | `test_accounts_dialog_aa_group_reflects_saved_status` | unit (pytest-qt) | `pytest tests/test_accounts_dialog.py::test_accounts_dialog_aa_group_reflects_saved_status -x` | Existing file — extend |
| D-06 | Clear requires confirm | `test_accounts_dialog_clear_aa_key_requires_confirm` | unit (pytest-qt) | `pytest tests/test_accounts_dialog.py::test_accounts_dialog_clear_aa_key_requires_confirm -x` | Existing file — extend |
| D-08 | Masked by default | `test_aa_key_field_masked_by_default` | unit (pytest-qt) | `pytest tests/test_import_dialog.py::test_aa_key_field_masked_by_default -x` | Wave 0 |
| D-09 | Show toggle flips echoMode | `test_aa_key_show_toggle_flips_echo_mode` | unit (pytest-qt) | `pytest tests/test_import_dialog.py::test_aa_key_show_toggle_flips_echo_mode -x` | Wave 0 |
| D-11 | Save → reopen → readback | `test_import_dialog_save_reopen_readback` | integration (pytest-qt, same process) | `pytest tests/test_import_dialog.py::test_import_dialog_save_reopen_readback -x` | Wave 0 |
| Phase 42 contract | Export still excludes AA key even when saved | `test_credentials_excluded` (extended) | unit | `pytest tests/test_settings_export.py::test_credentials_excluded -x` | Existing — extend |
| Phase 42 UAT 7 unblock | Round-trip test passes | manual (rerun `/gsd-verify-work 42` UAT 7) | manual | n/a | Tracked in Phase 42 UAT |

### Sampling Rate
- **Per task commit:** `pytest tests/test_import_dialog.py tests/test_accounts_dialog.py tests/test_settings_export.py -x` (runs in < 5 seconds)
- **Per wave merge:** Same targeted command (phase touches only three test files)
- **Phase gate:** `pytest -x` (full suite green) before `/gsd-verify-work 48`

### Wave 0 Gaps

- [ ] `tests/test_import_dialog.py` — currently contains only yt_import library tests; either add widget-test section at bottom with clear divider OR rename existing to `tests/test_yt_import.py` and create fresh widget test file. Planner picks; in-place addition is smaller-diff.
- [ ] `tests/test_accounts_dialog.py` — must update existing 8 instantiations of `AccountsDialog()` to pass a `FakeRepo` (planner side effect of adding `repo` parameter).
- [ ] FakeRepo class — duplicate the existing one from `test_accent_color_dialog.py` into the new/extended test files (project convention; no shared conftest fixture for this).
- [ ] No framework install needed — pytest-qt already on the project.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Listen key is a shared secret, not an auth credential. No login flow. |
| V3 Session Management | no | No sessions. |
| V4 Access Control | no | Single-user desktop app, no authz boundaries within. |
| V5 Input Validation | low | Key is an opaque string; validation is "did fetch succeed" (D-01 implicit). No injection vector — it's sent to AudioAddict's HTTP API only. |
| V6 Cryptography | partial | **Storage at rest: plaintext in SQLite** — explicit trust boundary per CONTEXT. Encrypted storage deferred to future phase. |
| V7 Error Handling | yes | `_on_aa_fetch_error` already handles 401/403/empty/network — this phase changes nothing there. |
| V8 Data Protection | yes | `_EXCLUDED_SETTINGS` guard (Phase 42 T-42-03) keeps key out of export ZIP. D-12's extended test guards the guard. |
| V13 API | n/a | No new APIs. |

### Known Threat Patterns for PySide6 credential UI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Shoulder-surfing of credential in plain text | Information Disclosure | `QLineEdit.EchoMode.Password` by default (D-08) |
| Credential leakage via export ZIP shared between machines | Information Disclosure | `_EXCLUDED_SETTINGS` set (Phase 42 contract; regression-tested in D-12 last bullet) |
| Credential-in-repr logs (accidental `print(repo.get_setting(...))`) | Information Disclosure | No logging of the key anywhere in scope; no `__repr__` work planned |
| Rich-text injection via status label | Tampering | `Qt.TextFormat.PlainText` on the AA status label (T-40-04 parity, per D-05) |
| Persistence of invalid credential (rejected key saved then resurfaces) | Tampering (implicit) | D-01 success-gate — only persist after non-empty channel list |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `view-reveal-symbolic` renders on the dev's GNOME 46+ and is available in the freedesktop icon spec on most Linux DEs | Architecture Patterns → Pattern 2 | Low — fallback chain (`document-properties` → optional bespoke SVG) prevents blank icon; visual polish regression only |
| A2 | pytest-qt's `qtbot` fixture is already auto-registered project-wide (implied by `test_accent_color_dialog.py` using it with no conftest import) | Validation Architecture | Low — if the plugin isn't actually auto-registered, existing test suite would already fail |

Both assumptions are low-risk. All other claims are VERIFIED against project source or CITED from existing patterns.

## Open Questions

None. The phase is fully scoped by D-01..D-13 plus the two constructor-threading items confirmed during research.

## Sources

### Primary (HIGH confidence — project source verified)
- `musicstreamer/ui_qt/import_dialog.py:111-157` — `_AaFetchWorker` / `_AaImportWorker` signal contract (VERIFIED: read file)
- `musicstreamer/ui_qt/import_dialog.py:166` — `ImportDialog.__init__` signature currently `(toast_callback, parent=None)` (VERIFIED: read file)
- `musicstreamer/ui_qt/import_dialog.py:397-429` — AA flow entry + success slot (VERIFIED: read file)
- `musicstreamer/ui_qt/accounts_dialog.py:36` — `AccountsDialog.__init__(self, parent)` (VERIFIED: read file)
- `musicstreamer/ui_qt/accounts_dialog.py:44-107` — Twitch group template + disconnect pattern (VERIFIED: read file)
- `musicstreamer/ui_qt/main_window.py:510, 526` — `ImportDialog` and `AccountsDialog` call sites (VERIFIED: read file)
- `musicstreamer/repo.py:348-359` — `get_setting` / `set_setting` signatures (VERIFIED: read file)
- `musicstreamer/settings_export.py:29` — `_EXCLUDED_SETTINGS = {"audioaddict_listen_key"}` (VERIFIED: read file)
- `tests/test_settings_export.py:194-206` — `test_credentials_excluded` current body, ready for extension (VERIFIED: grep + read)
- `tests/test_accent_color_dialog.py:19-27, 34-43` — FakeRepo + qtbot fixture pattern (VERIFIED: read file)
- `tests/test_accounts_dialog.py:42-201` — 8 instantiations of `AccountsDialog()` that will need updating (VERIFIED: read file)
- `tests/test_import_dialog.py:1-202` — currently `yt_import` library tests, not widget tests (VERIFIED: read file — misleadingly named)
- `musicstreamer/ui_qt/icons.qrc:3-16` — current icon resource list; no existing "show/reveal" icon (VERIFIED: read file)
- Grep `echoMode|EchoMode` across `musicstreamer/` — zero matches; this is a NEW pattern for the project (VERIFIED: grep)

### Secondary (MEDIUM confidence — project conventions observed in multiple files)
- `QIcon.fromTheme(name, fallback)` pattern in `favorites_view.py:190`, `main_window.py:112`, `now_playing_panel.py:191+` (CITED: grep results)
- `monkeypatch.setattr(QMessageBox, "question", staticmethod(...))` test pattern at `test_accounts_dialog.py:73-76` (CITED: read file)

### Tertiary (LOW confidence)
- None — no WebSearch or external-doc claims made in this research.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries
- Architecture: HIGH — all patterns verified against project source
- Pitfalls: HIGH — Pitfalls 1, 2, 3, 5, 6 all VERIFIED against actual file content

**Research date:** 2026-04-19
**Valid until:** 2026-05-19 (stable internal bug fix — no fast-moving dependency)
