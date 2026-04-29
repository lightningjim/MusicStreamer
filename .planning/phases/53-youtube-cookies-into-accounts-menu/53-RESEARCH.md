# Phase 53: YouTube Cookies into Accounts Menu — Research

**Researched:** 2026-04-28
**Domain:** PySide6/Qt UI surgery — dialog refactor (move launch site of an existing child dialog)
**Confidence:** HIGH (every CONTEXT.md line/signature reference verified against the live source)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** YouTube row is a `QGroupBox` titled "YouTube" mirroring the Twitch group shape: PlainText `QLabel` status + single `QPushButton`. Reuses existing `status_font` (10pt). T-40-04: `setTextFormat(Qt.TextFormat.PlainText)` on status label.
- **D-02:** Connection state = `os.path.exists(paths.cookies_path())`. No corruption check at status-display time. Phase 999.7's auto-clear-on-read remains the recovery path.
- **D-03:** Connected-state action button = "Disconnect". On click, `QMessageBox.question` Yes/No (default No) confirms with text: "Disconnect YouTube? This will delete your saved YouTube cookies. You will need to re-import to play cookie-protected YouTube streams." On Yes → `os.remove(paths.cookies_path())` with try/except `FileNotFoundError` → `_update_status()`. Confirm dialog title: "Disconnect YouTube?".
- **D-04:** Disconnect handler is strictly limited to `cookies_path()` removal + status refresh. Does NOT touch Twitch token, AA listen key, or other Player state.
- **D-05:** `CookieImportDialog` launched via `dlg.exec()` from inside AccountsDialog YouTube action slot. After exec returns, AccountsDialog calls `self._update_status()` to refresh.
- **D-06:** `AccountsDialog.__init__` gains `toast_callback: Callable[[str], None] | None = None` parameter (default None for back-compat). Construct `CookieImportDialog(self._toast_callback, parent=self)` from the YouTube slot. If callback is None, use no-op lambda defensively.
- **D-07:** Button text varies by state: "Import YouTube Cookies..." (not connected) / "Disconnect" (connected).
- **D-08:** Status label text: literal "Connected" / "Not connected".
- **D-09:** Group order top-to-bottom: **YouTube → Twitch → AudioAddict** (reverses Phase 48 ordering).
- **D-10:** `CookieImportDialog` file unchanged. Constructor signature `(toast_callback, parent)` preserved.
- **D-11:** `tests/test_cookie_import_dialog.py` unchanged.
- **D-12:** Remove from `main_window.py`: line 148–149 (`act_cookies` + connect), lines 665–668 (`_open_cookie_dialog`), line 55 (`from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog`).
- **D-13:** Update `tests/test_main_window_integration.py`: line 395–406 `EXPECTED_ACTION_TEXTS` (remove "YouTube Cookies", length 10 → 9). Separator count expectation stays at 3.
- **D-14:** `MainWindow._open_accounts_dialog` (line 670–677) updated to pass `self.show_toast` as the new `toast_callback` arg.

### Claude's Discretion

- Slot/handler attribute names (`_on_youtube_action_clicked`, `_youtube_status_label`, `_youtube_action_btn`, `_youtube_box`).
- Whether to share `status_font` with Twitch group (recommended: yes — read-only after `setPointSize`).
- Exact Disconnect confirm wording (recommendation: stay close to Twitch precedent, swap "token" → "cookies", add re-import note).
- `_toast_callback` vs. `_toast` attribute name.
- `try/except FileNotFoundError` defensive wrap on `os.remove` (recommendation: yes — match Twitch precedent).
- Whether `_update_status()` runs unconditionally after `dlg.exec()` (recommendation: yes — idempotent).
- Inline group construction vs. `_build_youtube_group()` helper (recommendation: stay inline, matching Twitch + AA precedent).

### Deferred Ideas (OUT OF SCOPE)

- Setting/updating AudioAddict listen key from AccountsDialog (reverses Phase 48 D-04). Defer to follow-up phase.
- Surfacing YouTube "Connected" status outside AccountsDialog (badges in Now Playing, station tree, startup toast).
- Three explicit cookie-status states ("Connected" / "Corrupted" / "Not connected") — rejected (D-02).
- Refactoring `CookieImportDialog` into an embeddable widget — rejected (D-10).
- Generalized "any cookie-auth provider" abstraction in accounts_dialog.py — too few providers to abstract.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BUG-04 | YouTube cookies entry is consolidated into the Accounts menu (single accounts surface for Twitch + YouTube) | Verified all three success criteria are implementable as locked: (1) hamburger menu trim is straightforward — only one production caller of `_open_cookie_dialog` exists; (2) AccountsDialog has clean group-box pattern (Twitch + AA) to mirror; (3) coexistence is a layout-ordering question — no visual conflict because both are vertically-stacked QGroupBox rows. |
</phase_requirements>

## Summary

Phase 53 is a small, surgical UI refactor with extremely thorough upstream context — CONTEXT.md is 14 numbered locked decisions citing exact line numbers, button labels, and group ordering. The phase mechanically:

1. Adds a YouTube `QGroupBox` to `AccountsDialog` (mirrors the existing Twitch group: status label + action button + Yes/No confirm Disconnect).
2. Wires `AccountsDialog._on_youtube_action_clicked` to construct the existing `CookieImportDialog` (unchanged) and call `_update_status()` after exec returns.
3. Threads `toast_callback` through `AccountsDialog.__init__` so the cookie-import success toast still reaches `MainWindow.show_toast`.
4. Removes the standalone "YouTube Cookies" hamburger entry, the `_open_cookie_dialog` slot, and the now-unused `CookieImportDialog` import in `main_window.py`.
5. Updates `tests/test_main_window_integration.py` `EXPECTED_ACTION_TEXTS` (drops "YouTube Cookies"; length 10 → 9). Separator count remains 3.

I verified every line reference in CONTEXT.md against the live source — all match exactly. The only meaningful planning ambiguity is **how to cope with the 24 existing positional `AccountsDialog(fake_repo)` test sites** when the constructor signature changes — the keyword-default-`None` strategy in D-06 is the right answer (zero test churn) and is verified safe.

**Primary recommendation:** Plan three small atomic units: (1) extend `AccountsDialog` (signature + YouTube group + slots + status update + group reordering), (2) trim `main_window.py` (remove menu entry, slot, import; pass `toast_callback`), (3) update `tests/test_main_window_integration.py` `EXPECTED_ACTION_TEXTS`. Existing AccountsDialog test fixtures need NO churn because `toast_callback` defaults to `None`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Hamburger menu structure | Qt MainWindow (`main_window.py`) | — | Menu is owned by MainWindow; only this class adds/removes actions. |
| Cookie status display ("Connected" / "Not connected") | Qt AccountsDialog (`accounts_dialog.py`) | Filesystem (`paths.cookies_path` via `os.path.exists`) | Status is derived UI state; truth lives on disk. Mirrors Twitch group exactly. |
| Cookie file write (3-tab File/Paste/Google) | Qt CookieImportDialog (`cookie_import_dialog.py`) | OAuth subprocess (`oauth_helper.py --mode google`) | Existing dialog — **unchanged**. AccountsDialog only changes the launch site. |
| Cookie file delete (Disconnect) | Qt AccountsDialog (`accounts_dialog.py`) | Filesystem (`os.remove(paths.cookies_path())`) | Disconnect is a destructive UI action; mirrors Twitch precedent in `constants.clear_twitch_token`. |
| Toast surfacing | Qt MainWindow (`main_window.py`) | AccountsDialog (forwards `toast_callback`) → CookieImportDialog (calls `self._toast(...)`) | Toast overlay is a MainWindow widget; AccountsDialog becomes a transparent forwarder. |
| Corruption recovery (auto-clear) | Player resolve worker (Phase 999.7, unchanged) | `cookie_utils.is_cookie_file_corrupted` + auto-clear + `cookies_cleared` signal → `MainWindow.show_toast` | Out of scope for Phase 53. AccountsDialog status display is permitted to lag briefly after auto-clear; refresh on next dialog open. |

## Standard Stack

This is a UI refactor inside an existing PySide6 application. No new libraries are introduced. The "stack" consists of patterns already established in the codebase.

### Core (already in use; phase reuses verbatim)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | 6.x (project pinned in pyproject.toml — not changed by this phase) | Qt bindings for AccountsDialog, QGroupBox, QPushButton, QMessageBox.question | The entire `ui_qt/` module is already PySide6. [VERIFIED: codebase grep — `from PySide6.QtWidgets import` in accounts_dialog.py and main_window.py] |
| `musicstreamer.paths` | internal | Source of truth for `cookies_path()`, `twitch_token_path()` (and the `_root_override` test hook) | Already used by both AccountsDialog (Twitch) and CookieImportDialog. [VERIFIED: paths.py:46 `cookies_path()`] |
| `musicstreamer.constants.clear_twitch_token` | internal | Precedent for "remove auth file with try/except"-style cleanup | YouTube Disconnect mirrors the structure. [VERIFIED: constants.py:45-51] |

### Supporting (already in use)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `unittest.mock` (MagicMock, patch) | stdlib | Mock QProcess in existing AccountsDialog tests | Pattern for any new YouTube-flow tests that need to intercept CookieImportDialog construction or `os.remove` |
| pytest-qt (`qtbot`, `qapp`) | already a project dev-dep | Headless Qt widget testing | Existing test fixture pattern in `tests/test_accounts_dialog.py` |

**No new packages installed.** No `pyproject.toml` edits expected.

## Architecture Patterns

### System Diagram (post-Phase 53)

```
User clicks hamburger menu (MainWindow._menu)
         │
         ▼
  ┌──────────────┐
  │ "Accounts"   │ (only path to YouTube cookie management after Phase 53)
  └──────┬───────┘
         │
         ▼
MainWindow._open_accounts_dialog()
  └─► AccountsDialog(repo, toast_callback=self.show_toast, parent=self).exec()
         │
         ▼
  ┌─────────────────────────────────────────────────┐
  │ AccountsDialog (top → bottom, D-09)             │
  │  ┌─────────────────────────────────────────┐    │
  │  │ YouTube group  (NEW)                    │    │
  │  │   Status: Connected / Not connected     │    │
  │  │   Button: "Import YouTube Cookies..."   │────┼──► CookieImportDialog(toast_callback, parent=self).exec()
  │  │           or "Disconnect"               │    │       │ (unchanged 3-tab File/Paste/Google)
  │  │                                         │    │       │ on success: self._toast("YouTube cookies imported."); self.accept()
  │  │                                         │    │       │
  │  │   On exec return → _update_status()     │◄───┼───────┘
  │  │                                         │    │
  │  │   On Disconnect Yes: os.remove(...)     │    │
  │  │     → _update_status()                  │    │
  │  └─────────────────────────────────────────┘    │
  │                                                 │
  │  ┌─────────────────────────────────────────┐    │
  │  │ Twitch group (existing, unchanged)      │    │
  │  └─────────────────────────────────────────┘    │
  │                                                 │
  │  ┌─────────────────────────────────────────┐    │
  │  │ AudioAddict group (existing, unchanged) │    │
  │  └─────────────────────────────────────────┘    │
  └─────────────────────────────────────────────────┘
```

### Recommended Project Structure (no change — surgery on existing files only)

```
musicstreamer/ui_qt/
├── accounts_dialog.py        # MODIFIED: + YouTube group, + toast_callback param, + slots
├── cookie_import_dialog.py   # UNCHANGED (D-10)
└── main_window.py            # MODIFIED: − act_cookies, − _open_cookie_dialog, − CookieImportDialog import, edit _open_accounts_dialog
tests/
├── test_accounts_dialog.py            # MODIFIED: + YouTube group tests (existing 24 sites need NO update — D-06 keyword default)
├── test_main_window_integration.py    # MODIFIED: EXPECTED_ACTION_TEXTS list (− "YouTube Cookies"); separator count UNCHANGED
└── test_cookie_import_dialog.py       # UNCHANGED (D-11)
```

### Pattern 1: Status-driven button toggle (Twitch precedent)

**What:** Single `QPushButton` whose label and click behavior swap based on a connection-state predicate. Status label is updated alongside button text in a single `_update_status()` method called after every state-changing action.

**When to use:** Any account/auth surface where two states (connected, not connected) drive both display and action.

**Example (Twitch — accounts_dialog.py:129–140):**
```python
# Source: /home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/accounts_dialog.py:129
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
```

YouTube mirrors this — but no `Connecting...` intermediate state because there's no in-process subprocess for YouTube on the Disconnect path. Import is a child dialog, not a QProcess started by AccountsDialog itself.

### Pattern 2: Yes/No confirm before destructive action (default No)

**What:** `QMessageBox.question` with `Yes | No` buttons, `No` as default. On `Yes`, perform the destructive action then refresh status.

**Example (Twitch Disconnect — accounts_dialog.py:179–192):**
```python
# Source: /home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/accounts_dialog.py:179
def _on_action_clicked(self) -> None:
    if self._is_connected():
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
        self._launch_oauth_subprocess()
```

YouTube mirrors structure exactly — substitute `os.remove(paths.cookies_path())` (with `try/except FileNotFoundError`) for `constants.clear_twitch_token()`.

### Pattern 3: Defaulted-keyword constructor extension for back-compat

**What:** When adding a new `__init__` parameter to a class with N test fixtures and one production caller, declare the new parameter with a defaulted value (`None` or no-op) so all existing positional callers continue to work without churn. Update only the production call site to pass the real value.

**Why this works for AccountsDialog:** 24 existing test sites (`tests/test_accounts_dialog.py`) construct `AccountsDialog(fake_repo)` positionally. The Twitch and AA tests do not exercise YouTube — they care about Twitch token files and AA listen keys. Passing `toast_callback=None` is harmless because nothing in the Twitch/AA flows reads `self._toast_callback`.

```python
# In AccountsDialog.__init__:
def __init__(
    self,
    repo,
    toast_callback: Callable[[str], None] | None = None,
    parent: QWidget | None = None,
) -> None:
    super().__init__(parent)
    self._repo = repo
    self._toast_callback = toast_callback or (lambda _msg: None)
    ...
```

### Anti-Patterns to Avoid

- **Self-capturing lambdas in signal connections (QA-05).** Use `self._youtube_action_btn.clicked.connect(self._on_youtube_action_clicked)`, never `clicked.connect(lambda: self._on_youtube_action_clicked())`.
- **Rich-text injection on status labels (T-40-04).** Always `setTextFormat(Qt.TextFormat.PlainText)` on the new YouTube status label, even though "Connected" / "Not connected" are static literals — the rule applies uniformly.
- **Calling `clear_cookies()` directly.** `constants.clear_cookies()` exists (constants.py:36-42) and is functionally what we want, but D-04 limits Disconnect to `os.remove(paths.cookies_path())`. Either call works; the recommended path is `os.remove` directly with `try/except FileNotFoundError` (matches the in-handler style of Twitch's `clear_twitch_token` precedent and avoids importing yet another module surface). Planner's call.
- **Skipping `_update_status()` after `CookieImportDialog.exec()` returns Rejected.** Idempotent — call it unconditionally per D-05 + the discretion recommendation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cookie file write | A new write path | Existing `CookieImportDialog._write_cookies` | Already enforces 0o600 (T-40-08) and Netscape validation (T-40-07). Untouched per D-10. |
| YouTube cookie validation | New parser | `cookie_import_dialog._validate_youtube_cookies` | Already handles Netscape format + `.youtube.com` domain check. |
| Cookie corruption detection | Three-state status | Phase 999.7 `cookie_utils.is_cookie_file_corrupted` + auto-clear-on-read | D-02: corruption is a Player-tier concern; AccountsDialog trusts file existence. |
| Toast plumbing | New signal/slot wiring | Existing `MainWindow.show_toast` (line 304) forwarded as `toast_callback` | Already wired to `ToastOverlay`; CookieImportDialog already calls `self._toast(...)` on success. |
| Twitch-style group structure | Custom layout | Mirror the Twitch QGroupBox pattern at `accounts_dialog.py:78–90` | Three lines of layout per group; copying is cheaper than abstracting. |

**Key insight:** Phase 53 is composition, not invention. Every primitive needed (status-driven button, Yes/No confirm, child-dialog launch via `dlg.exec()`, post-dialog status refresh, toast forwarding) already exists in the codebase. The phase is wiring three of them together in one new `QGroupBox`.

## Common Pitfalls

### Pitfall 1: Existing 24 positional `AccountsDialog(fake_repo)` test sites break on signature change

**What goes wrong:** If `toast_callback` is added as a positional parameter without a default, every line in `tests/test_accounts_dialog.py` that says `AccountsDialog(fake_repo)` becomes `AccountsDialog(fake_repo, mock_callback)` — 24 lines of mechanical churn that risks merge conflicts and review overhead.

**Why it happens:** New parameter inserted without back-compat default.

**How to avoid:** D-06 mandates `toast_callback: Callable[[str], None] | None = None` (defaulted). The internal handling MUST cope with `None` defensively (use a no-op lambda or `if self._toast_callback:` guards). [VERIFIED: I counted 24 `AccountsDialog(fake_repo)` sites in the test file via grep.]

**Warning signs:** A plan that asks the implementer to add the param positionally before `parent`, or that schedules a "test fixture cleanup" task. Reject — it's the wrong direction.

### Pitfall 2: Race between status check and Disconnect click via Phase 999.7 auto-clear

**What goes wrong:** User opens AccountsDialog, status reads "Connected" (file exists), then before the user clicks "Disconnect" the Player resolve worker auto-clears a corrupted cookies.txt. User clicks Disconnect → `os.remove(paths.cookies_path())` raises `FileNotFoundError`.

**Why it happens:** `_is_youtube_connected()` is a snapshot, not a lock. The auto-clear path runs on a worker thread. There IS a real (small) window.

**How to avoid:** Wrap `os.remove(paths.cookies_path())` in `try/except FileNotFoundError`. CONTEXT.md D-03 already calls this out explicitly. After the (caught) exception, call `_update_status()` regardless — the dialog will correctly flip to "Not connected".

**Warning signs:** A plan that uses `os.remove` without exception handling, or that adds a recheck of `os.path.exists` immediately before `os.remove` (TOCTOU — same race, slightly narrower window).

### Pitfall 3: Hamburger separator off-by-one if Group 2 is misread

**What goes wrong:** Removing "YouTube Cookies" appears to "remove an item from Group 2" (the Settings group), tempting an implementer to also remove a separator "to keep groups balanced". Doing so changes the menu structure unexpectedly.

**Why it doesn't actually happen here:** "YouTube Cookies" is the second of four entries in Group 2 (Accent Color, **YouTube Cookies**, Accounts, Equalizer). Removing it leaves three entries; Group 2 still has its terminating separator (line 158). Total separator count remains 3.

**How to avoid:** Verify by line-walking `main_window.py:128–177` after the edit. The separator at line 142 (between Group 1 and Group 2) and the separator at line 158 (between Group 2 and Group 3 — Stats for Nerds) and the separator at line 167 (between Stats and Group 4 — Export/Import) all remain. [VERIFIED: I traced the menu structure manually.]

**Warning signs:** A plan task that touches `addSeparator()` calls. Reject — none should be added or removed.

### Pitfall 4: `CookieImportDialog` parent semantics when launched from AccountsDialog

**What goes wrong:** CookieImportDialog used to be a top-level child of MainWindow. Phase 53 makes it a child of AccountsDialog (which is itself a child of MainWindow). Modal stacking on Linux/Wayland can behave surprisingly when grandchild dialogs are exec'd — but `QDialog.exec()` defaults to `Qt.WindowModal` semantics, which means the import dialog is modal to AccountsDialog (its parent), not application-modal.

**Why this is fine in practice:** AccountsDialog is itself modal (it was invoked via `dlg.exec()` from MainWindow). So the user can't interact with MainWindow anyway. The modal grandchild → modal child → modal parent stack works correctly under Qt's default modality.

**Verification:** [CITED: Qt 6 docs `QDialog.exec` — "Shows the dialog as a modal dialog, blocking until the user closes it. The function returns a DialogCode result."] No `setWindowModality(Qt.ApplicationModal)` is needed.

**Warning signs:** A plan task that explicitly sets `setWindowModality` on CookieImportDialog. Reject — out of scope (D-10) and unnecessary.

### Pitfall 5: Status display lying for a few hundred ms after auto-clear

**Acknowledged by D-02 — not a bug, but worth documenting in test expectations:**

Phase 999.7's auto-clear path runs on the YouTube resolve worker, then emits `cookies_cleared` to MainWindow which fires a toast. AccountsDialog has no signal subscription to `cookies_cleared` (and CONTEXT.md doesn't ask for one). So if AccountsDialog is open at the moment auto-clear fires, the YouTube status label still says "Connected" until the user closes and reopens the dialog (or triggers another `_update_status()`).

**Why this is acceptable:** D-02 explicitly states it. The toast tells the user; the next dialog open shows truth.

**Test implication:** Don't write a test that asserts AccountsDialog auto-refreshes on `Player.cookies_cleared`. That's a non-goal.

## Runtime State Inventory

> Phase 53 is a UI refactor with no rename/migration. This section is included for completeness but each category resolves to "nothing" — explicitly verified.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — verified by grep. The cookies.txt file at `paths.cookies_path()` is unchanged in location, format, and permissions. No DB writes, no settings table changes. | None |
| Live service config | None — the only "service" involved is `oauth_helper.py --mode google`, which is unchanged (D-10). No external service registrations. | None |
| OS-registered state | None — no Windows tasks, no systemd units, no MPRIS service name changes. The hamburger menu is in-process Qt state only. | None |
| Secrets/env vars | None — no SOPS keys, no env vars renamed. The cookies.txt file path is unchanged. | None |
| Build artifacts | None — pyproject.toml unchanged. No package rename. (Note: VER-01 phase-completion hook will bump version to 2.1.53 on phase ship — that's a project-level convention, not phase-specific work.) | None |

**The renamed/moved thing:** Only the *launch site* of `CookieImportDialog` moves from `main_window._open_cookie_dialog` to `accounts_dialog._on_youtube_action_clicked`. No persistent state references either method by name. No tests except the integration test reference the hamburger entry by text.

## Code Touchpoints (verified)

Every CONTEXT.md line reference cross-checked against live source on 2026-04-28.

### `musicstreamer/ui_qt/accounts_dialog.py` (374 lines total)

| CONTEXT.md ref | Verified | Notes |
|----------------|----------|-------|
| `:53–117` constructor (Twitch + AA + close) | ✓ matches | Constructor lives at 68–116. Layout adds at 109–114 are exactly 3 widgets (twitch_box, aa_box, btn_box). YouTube box becomes 4th. |
| `:78–90` Twitch group precedent | ✓ matches | QGroupBox + status_label + status_font + action_btn pattern. Mirror exactly. |
| `:122–123` `_is_connected()` | ✓ matches | `return os.path.exists(paths.twitch_token_path())`. YouTube version: substitute `cookies_path()`. |
| `:129–150` `_update_status()` | ✓ matches | Twitch + AA branches present. YouTube branch inserts at top or bottom of method — planner's choice; recommend at the start to mirror group order. |
| `:179–195` `_on_action_clicked()` Disconnect precedent | ✓ matches | Yes/No with default No. YouTube reuses the structure. |
| `:208–220` `_on_aa_clear_clicked()` confirm precedent | ✓ matches | Same Yes/No idiom. |

### `musicstreamer/ui_qt/main_window.py` (683 lines total)

| CONTEXT.md ref | Verified | Notes |
|----------------|----------|-------|
| `:54–55` imports | ✓ matches | `from musicstreamer.ui_qt.accounts_dialog import AccountsDialog` (line 54, kept) and `from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog` (line 55, removed). |
| `:148–149` `act_cookies` | ✓ matches | Exact text. Removed. |
| `:151–152` `act_accounts` | ✓ matches | Unchanged. |
| `:665–668` `_open_cookie_dialog` | ✓ matches | Method body is exactly `dlg = CookieImportDialog(self.show_toast, parent=self); dlg.exec()`. Removed. |
| `:670–677` `_open_accounts_dialog` | ✓ matches | Currently constructs `AccountsDialog(self._repo, parent=self)`. Updated to `AccountsDialog(self._repo, toast_callback=self.show_toast, parent=self)`. |
| `:304` `show_toast` method | ✓ exists | `def show_toast(self, text: str, duration_ms: int = 3000) -> None`. Bound method passes cleanly as a `Callable[[str], None]` (the second arg is defaulted). |

### `musicstreamer/ui_qt/cookie_import_dialog.py` (317 lines total — UNCHANGED)

| CONTEXT.md ref | Verified | Notes |
|----------------|----------|-------|
| `:70–115` constructor | ✓ matches | `CookieImportDialog(toast_callback, parent=None)`. Stores `self._toast = toast_callback`. |
| `:299–308` `_write_cookies` | ✓ matches | Calls `self._toast("YouTube cookies imported.")` then `self.accept()` on success. Phase 53 relies on `self.accept()` so AccountsDialog can call `_update_status()` after `dlg.exec()` returns. |

### `tests/test_main_window_integration.py`

| CONTEXT.md ref | Verified | Notes |
|----------------|----------|-------|
| `:395–406` `EXPECTED_ACTION_TEXTS` | ✓ matches | List has exactly 10 entries. After Phase 53: remove "YouTube Cookies" → 9 entries. |
| `:409–414` `test_hamburger_menu_actions` | ✓ matches | Computed against `EXPECTED_ACTION_TEXTS` directly; the docstring on line 410 says "exactly 9 non-separator actions" but the current list has 10. **DOCSTRING IS ALREADY WRONG** — appears to be a legacy artifact. After Phase 53 the docstring will be correct. (Worth flagging in plan as a "leave docstring as-is — it'll match reality post-Phase-53" note.) |
| `:417–421` `test_hamburger_menu_separators` | ✓ matches | Asserts `len(separators) == 3`. After Phase 53: still 3 (verified by line-walking the menu — separators at 142, 158, 167 are all between groups whose contents change but boundaries do not). |

**Pre-existing oddity worth noting:** `test_hamburger_menu_actions` docstring at line 410 already says "exactly 9" but the assertion compares against a 10-item list. This phase incidentally fixes the docstring drift — no separate task needed.

### `tests/test_accounts_dialog.py` (662 lines, 24 `AccountsDialog(fake_repo)` sites)

[VERIFIED: `grep -c "AccountsDialog(fake_repo)" tests/test_accounts_dialog.py` returns 24.]

All 24 sites use positional `AccountsDialog(fake_repo)`. With D-06's keyword-default-`None` strategy, **none of these sites need updating**. New YouTube-flow tests can use any of three patterns:

```python
# Pattern A — default None (status read tests, where toast doesn't fire):
dlg = AccountsDialog(fake_repo)

# Pattern B — explicit None (clarity):
dlg = AccountsDialog(fake_repo, toast_callback=None)

# Pattern C — capturing mock (post-import refresh + toast tests):
toasts: list[str] = []
dlg = AccountsDialog(fake_repo, toast_callback=toasts.append)
```

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-qt (existing project setup) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (project-standard) |
| Quick run command | `pytest tests/test_accounts_dialog.py tests/test_main_window_integration.py -x -q` |
| Full suite command | `pytest -q` |

### Phase Requirements → Test Map

Each ROADMAP success criterion (SC-1, SC-2, SC-3) gets at least one automated test. Test files marked ❌ are new or augmented; ✅ exist already.

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUG-04 / SC-1 | Hamburger menu has 9 entries, "YouTube Cookies" is NOT in the list | unit | `pytest tests/test_main_window_integration.py::test_hamburger_menu_actions -x` | ✅ exists; `EXPECTED_ACTION_TEXTS` updated |
| BUG-04 / SC-1 | Hamburger menu has exactly 3 separators (unchanged structure) | unit | `pytest tests/test_main_window_integration.py::test_hamburger_menu_separators -x` | ✅ exists; assertion unchanged but RE-RUN to confirm |
| BUG-04 / SC-2 | AccountsDialog has a YouTube QGroupBox (titled "YouTube") with status label + action button | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_youtube_group_present -x` | ❌ Wave 0 — new test class |
| BUG-04 / SC-2 | YouTube status label reads "Not connected" when `paths.cookies_path()` does not exist | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_status_not_connected -x` | ❌ Wave 0 |
| BUG-04 / SC-2 | YouTube status label reads "Connected" when `paths.cookies_path()` exists | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_status_connected -x` | ❌ Wave 0 |
| BUG-04 / SC-2 | YouTube action button reads "Import YouTube Cookies..." when not connected | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_button_label_not_connected -x` | ❌ Wave 0 |
| BUG-04 / SC-2 | YouTube action button reads "Disconnect" when connected | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_button_label_connected -x` | ❌ Wave 0 |
| BUG-04 / SC-2 | Clicking "Import YouTube Cookies..." constructs and execs CookieImportDialog with the forwarded toast callback | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_import_launches_cookie_dialog -x` | ❌ Wave 0 — patch `CookieImportDialog` constructor with a MagicMock |
| BUG-04 / SC-2 | After CookieImportDialog returns Accepted, `_update_status()` re-runs and YouTube row flips to "Connected" | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_post_import_refreshes_status -x` | ❌ Wave 0 |
| BUG-04 / SC-2 | After CookieImportDialog returns Rejected, `_update_status()` is still called (idempotent — no state change) | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_post_cancel_status_unchanged -x` | ❌ Wave 0 |
| BUG-04 / SC-2 | Clicking "Disconnect" → Yes confirm → `os.remove(paths.cookies_path())` → status flips to "Not connected" | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_disconnect_removes_cookies -x` | ❌ Wave 0 |
| BUG-04 / SC-2 | Clicking "Disconnect" → No confirm → cookies file untouched | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_disconnect_cancel_keeps_cookies -x` | ❌ Wave 0 |
| BUG-04 / SC-2 | Disconnect handles `FileNotFoundError` gracefully (race with Phase 999.7 auto-clear) | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_disconnect_file_already_gone -x` | ❌ Wave 0 — pre-call `os.remove`, then click Disconnect; no exception escapes |
| BUG-04 / SC-2 | Disconnect does NOT touch Twitch token or AA listen key (D-04) | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_disconnect_isolates_youtube -x` | ❌ Wave 0 |
| BUG-04 / SC-2 | YouTube status label uses `Qt.TextFormat.PlainText` (T-40-04) | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_status_label_plain_text -x` | ❌ Wave 0 |
| BUG-04 / SC-3 | AccountsDialog group order is YouTube → Twitch → AudioAddict (D-09) | unit | `pytest tests/test_accounts_dialog.py::TestAccountsDialogYouTube::test_group_order -x` | ❌ Wave 0 — walk `dlg.layout()` children, assert `windowTitle()` (or `title()`) order on the QGroupBox children |
| BUG-04 / SC-3 | MainWindow `_open_accounts_dialog` passes `self.show_toast` as `toast_callback` | unit | `pytest tests/test_main_window_integration.py::test_open_accounts_passes_toast -x` | ❌ Wave 0 — patch AccountsDialog constructor with MagicMock, assert kwargs on call |
| BUG-04 / SC-3 | Existing 24 `AccountsDialog(fake_repo)` test sites still pass without modification | regression | `pytest tests/test_accounts_dialog.py -x` (full file run) | ✅ existing — re-run, expect zero changes |
| BUG-04 (manual) | Open Accounts dialog → import cookies via Google Login → toast appears, status flips to Connected → Disconnect → confirm Yes → status flips to Not connected | smoke (manual UAT) | Manual checklist in PLAN.md UAT section | ❌ Plan artifact |

### Sampling Rate

- **Per task commit:** `pytest tests/test_accounts_dialog.py tests/test_main_window_integration.py -x -q` (under 30s on a typical dev machine for these two files)
- **Per wave merge:** `pytest -q` (full suite green)
- **Phase gate:** Full suite green before `/gsd-verify-work`; manual UAT smoke test before `/gsd-verify-phase`

### Wave 0 Gaps

Existing test infrastructure (FakeRepo, tmp_data_dir fixture, qtbot, qapp) covers everything needed. No new fixtures required.

- [x] `tests/test_accounts_dialog.py::FakeRepo` — already exists, reusable as-is
- [x] `tests/test_accounts_dialog.py::tmp_data_dir` fixture — already redirects `paths._root_override`; reusable for `cookies_path()` testing
- [x] pytest-qt `qtbot` and `qapp` — already integrated
- [ ] **NEW: `TestAccountsDialogYouTube` test class in `tests/test_accounts_dialog.py`** — covers SC-2 and SC-3 invariants. Add as new class; do NOT touch existing 24 construction sites.
- [ ] **NEW: `test_open_accounts_passes_toast` in `tests/test_main_window_integration.py`** — patches AccountsDialog constructor with MagicMock to verify the kwarg wiring (D-14). Tiny test, ~10 lines.

## Project Constraints (from CLAUDE.md)

CLAUDE.md is minimal — only one routing rule. No coding-convention directives.

- **Routing:** Spike findings for MusicStreamer (Windows packaging patterns, GStreamer+PyInstaller+conda-forge, PowerShell gotchas) → `Skill("spike-findings-musicstreamer")`. **Not relevant to Phase 53** (UI refactor on Linux; no Windows/PyInstaller/GStreamer concerns surface here).

## Established Project Conventions (apply during planning)

These come from CONTEXT.md `<canonical_refs>` and are reaffirmed here so the planner has a single referencable list:

- **T-40-04:** All `QLabel` instances rendering user-derived text → `setTextFormat(Qt.TextFormat.PlainText)`. Applies to the new YouTube status label (even though "Connected"/"Not connected" are static — uniformity rule).
- **T-40-08:** 0o600 permissions immediately after cookie write. Preserved by unchanged `CookieImportDialog._write_cookies` (cookie_import_dialog.py:306).
- **QA-05:** Bound-method signal connections, no self-capturing lambdas. Apply to `_youtube_action_btn.clicked.connect(self._on_youtube_action_clicked)`.
- **Phase 48 D-04:** AccountsDialog never *writes* a new AudioAddict listen key. Preserved by Phase 53; reversal deferred.
- **Phase 999.7:** Cookie corruption recovery is `cookie_utils.is_cookie_file_corrupted()` + auto-clear-on-read + `cookies_cleared` toast via Player. Phase 53 does not duplicate this path.

## State of the Art

This phase is purely internal — no library upgrades, no API surface changes. PySide6 6.x, pytest, pytest-qt are all already in use at versions the project pins. Skipping the broader "deprecated/outdated" comparison since nothing relevant changes.

## Assumptions Log

> All claims in this research are either verified against the live codebase or cited from project documentation (CONTEXT.md, CLAUDE.md, paths.py, etc.). No speculative claims.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | (none) | — | — |

**This table is empty:** Every line/signature reference was cross-checked against `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/accounts_dialog.py`, `main_window.py`, `cookie_import_dialog.py`, `paths.py`, `constants.py`, `cookie_utils.py`, `tests/test_accounts_dialog.py`, and `tests/test_main_window_integration.py` on 2026-04-28.

## Open Questions

1. **Should `_update_status()` add the YouTube branch at the top (matching D-09 visual order) or at the bottom (after AA)?**
   - What we know: The method order doesn't affect behavior — all branches always run. CONTEXT.md doesn't lock ordering inside `_update_status`.
   - What's unclear: A reader might find one ordering more obvious than the other.
   - Recommendation: Insert YouTube at the top of `_update_status()` to match D-09 layout order. Trivial preference; planner can pick either.

2. **`os.remove(paths.cookies_path())` directly, or call `constants.clear_cookies()`?**
   - What we know: Both are valid. `constants.clear_cookies()` already exists (constants.py:36-42) with the same try/exists-guard structure. Twitch precedent uses `constants.clear_twitch_token()` from inside the slot (accounts_dialog.py:191).
   - What's unclear: D-04 says "limited to `cookies_path()` removal"; either implementation satisfies the constraint.
   - Recommendation: Match the Twitch precedent — call `constants.clear_cookies()` (which already wraps `os.remove` with `os.path.exists` check, achieving the same race-safety as `try/except FileNotFoundError`). Symmetry with Twitch's `constants.clear_twitch_token()` is a small but real readability win. **Either is fine; planner's call.**

3. **Should there be a UAT-only manual test for visual crowding (SC-3)?**
   - What we know: SC-3 says "without visual crowding". This is subjective.
   - What's unclear: Is "without visual crowding" satisfied by the locked layout (3 vertically-stacked QGroupBox + Close button), or does it require subjective screenshot review?
   - Recommendation: Add a single manual UAT step to PLAN.md: "Open Accounts dialog. Confirm dialog fits cleanly with no scrollbar and no group title overlap. Take a screenshot for the phase completion record." That's sufficient.

## Sources

### Primary (HIGH confidence)
- Live source files (verified 2026-04-28):
  - `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/accounts_dialog.py`
  - `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/main_window.py`
  - `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/cookie_import_dialog.py`
  - `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/paths.py`
  - `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/constants.py`
  - `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/cookie_utils.py`
  - `/home/kcreasey/OneDrive/Projects/MusicStreamer/tests/test_accounts_dialog.py`
  - `/home/kcreasey/OneDrive/Projects/MusicStreamer/tests/test_main_window_integration.py`
- `.planning/phases/53-youtube-cookies-into-accounts-menu/53-CONTEXT.md` (authoritative locked decisions)
- `.planning/REQUIREMENTS.md` BUG-04 entry
- `.planning/config.json` (`workflow.nyquist_validation: true` confirmed)

### Secondary (MEDIUM confidence)
- Qt 6 official documentation for `QDialog.exec`, `QMessageBox.question`, `QGroupBox`, `QLabel.setTextFormat` (well-established, stable Qt 5/6 API; not separately fetched in this research because all usage patterns are already verified by precedent in `accounts_dialog.py`).

### Tertiary (LOW confidence)
- (none)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all components already in use; nothing new introduced.
- Architecture: HIGH — every line reference in CONTEXT.md verified against live source.
- Pitfalls: HIGH — race conditions and signature-change risks are surface-level Python/Qt semantics; mitigation is in CONTEXT.md or established precedent.
- Validation: HIGH — test framework already in place, fixture infrastructure already exists, only need new test class + one integration test.

**Research date:** 2026-04-28
**Valid until:** 2026-05-12 (14 days — short window because this is a small phase that should be planned and shipped within a day or two; staleness drifts only if intervening phases edit `accounts_dialog.py` or `main_window.py` menu structure)
