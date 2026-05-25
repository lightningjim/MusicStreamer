# Phase 53: YouTube Cookies into Accounts Menu — Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Move YouTube-cookie management from a standalone hamburger-menu entry into `AccountsDialog`, so all third-party account-style integrations (Twitch, AudioAddict, YouTube) live in one consolidated dialog. The cookie *import mechanism* (file picker, paste, Google login subprocess) is unchanged — `CookieImportDialog` is reused as a child dialog launched from inside `AccountsDialog`.

In scope:
- Add a "YouTube" `QGroupBox` to `AccountsDialog` mirroring the Twitch/AudioAddict pattern: PlainText status label + single action button.
- Status reflects whether `paths.cookies_path()` exists ("Connected" vs. "Not connected").
- Action button toggles by state: "Import YouTube Cookies..." (when not connected, opens `CookieImportDialog`) vs. "Disconnect" (when connected, confirm + delete cookies.txt).
- Post-import wiring: `CookieImportDialog` close → `AccountsDialog._update_status()` re-runs → toast fires through `MainWindow.show_toast`.
- Remove `act_cookies` from the hamburger menu (`main_window.py:148–149`) and delete `_open_cookie_dialog` (`main_window.py:665–668`).
- Update `tests/test_main_window_integration.py` `EXPECTED_ACTION_TEXTS` (remove "YouTube Cookies"; length goes 10 → 9) and re-evaluate separator count (Phase 47.2 added a separator after the Settings group; current separator count is 3 — verify after removal).
- Group order in `AccountsDialog` (top → bottom): **YouTube → Twitch → AudioAddict**.

Explicitly NOT in scope:
- Adding the ability to *set* an AudioAddict listen key from `AccountsDialog` (reverses Phase 48 D-04). Deferred to a follow-up phase.
- Refactoring `CookieImportDialog` (the 3-tab File/Paste/Google widget). Stays as-is, reused as a child dialog.
- Changing the cookie write path, 0o600 permissions, `cookie_utils.temp_cookies_copy()` integration, or `oauth_helper.py --mode google` subprocess flow. All preserved.
- Adding a third "Corrupted" status state. Phase 999.7's auto-clear-on-read + toast remains the corruption recovery path.
- Visual polish on `AccountsDialog` beyond adding the YouTube group + reordering existing groups.
- Surfacing "Connected" status anywhere outside `AccountsDialog` (Now Playing panel, station tree, etc.).

</domain>

<decisions>
## Implementation Decisions

### YouTube section shape

- **D-01:** The YouTube row inside `AccountsDialog` is a `QGroupBox` titled "YouTube" with the same shape as the existing Twitch group: a PlainText `QLabel` for status ("Connected" / "Not connected") + a single `QPushButton` whose label and click handler swap based on connection state. Mirrors `accounts_dialog.py:78–90` (Twitch group). Adds ~15 lines and follows the pattern verbatim — including `setTextFormat(Qt.TextFormat.PlainText)` (T-40-04: no rich-text injection on the status label) and reusing the existing `status_font` (10pt) at `accounts_dialog.py:83–84`.

- **D-02:** "Connected" / "Not connected" is decided by `os.path.exists(paths.cookies_path())` — a direct parallel to the Twitch check `os.path.exists(paths.twitch_token_path())` in `accounts_dialog.py:122–123`. No corruption check at status-display time. Phase 999.7's `cookie_utils.is_cookie_file_corrupted()` + auto-clear-on-read remains the recovery path: if a corrupted file is "Connected" in the dialog, the next playback attempt auto-clears it and toasts. Status display lying briefly is acceptable; refreshing `AccountsDialog` after the auto-clear will then show "Not connected" correctly.

### Disconnect behavior

- **D-03:** When connected, the YouTube action button reads "Disconnect". On click, a `QMessageBox.question` Yes/No confirm prompts: "Disconnect YouTube? This will delete your saved YouTube cookies. You will need to re-import to play cookie-protected YouTube streams." Default button: No (consistent with Twitch's `QMessageBox.StandardButton.No` default at `accounts_dialog.py:188`). On Yes → `os.remove(paths.cookies_path())` (with `try/except FileNotFoundError` for race safety — file may have been auto-cleared between status check and click) → `_update_status()` to flip the row back to "Not connected" / "Import YouTube Cookies...".

  Confirm dialog title: "Disconnect YouTube?" (mirrors Twitch's "Disconnect Twitch?" at `accounts_dialog.py:184`).

- **D-04:** The Disconnect handler does NOT clear/touch `paths.twitch_token_path()`, the AA listen key, or any other Player state. It is strictly limited to `cookies_path()` removal + status refresh.

### Post-import flow

- **D-05:** `CookieImportDialog` is launched via `dlg.exec()` from inside `AccountsDialog._on_youtube_action_clicked` (or equivalent slot — name is planner's call). On successful import, `CookieImportDialog._write_cookies()` already calls `self._toast(...)` then `self.accept()` (`cookie_import_dialog.py:307–308`). After `dlg.exec()` returns, `AccountsDialog` calls `self._update_status()` to refresh the YouTube row. The cookie-import toast fires through the same `toast_callback` path that the hamburger entry uses today.

- **D-06:** `AccountsDialog.__init__` gains a `toast_callback: Callable[[str], None]` parameter (default `None` for back-compat with any caller that doesn't have one — but the only caller is `MainWindow._open_accounts_dialog` at `main_window.py:670–677`, which passes `self.show_toast` as the new arg). When the user clicks "Import YouTube Cookies...", `AccountsDialog` constructs `CookieImportDialog(self._toast_callback, parent=self)`. If `toast_callback` is `None`, a no-op lambda is used (defensive — never raises).

  Signature change is propagated to `tests/test_accounts_dialog.py` fixtures (existing tests must continue to pass — pass a `Mock()` or `lambda _: None` for the new arg).

### Button labels

- **D-07:** Button text varies by connection state:
  - **Not connected:** "Import YouTube Cookies..." — trailing ellipsis is a Qt convention signaling "opens another dialog" (matches Qt HIG); the verb "Import" matches `CookieImportDialog`'s window title `setWindowTitle("YouTube Cookies")` and the existing hamburger entry text.
  - **Connected:** "Disconnect" — exact mirror of Twitch's connected-state label (`accounts_dialog.py:135`).

- **D-08:** Status label text is the literal English strings "Connected" and "Not connected" (no extra context, no path hint, no detail). Mirrors Twitch group exactly. The label is the only signal of file presence; the button label provides the action verb.

### Group ordering

- **D-09:** Top-to-bottom order inside `AccountsDialog`: **YouTube → Twitch → AudioAddict**. Reverses the existing layout (Twitch → AudioAddict from Phase 48). Implementation: in `AccountsDialog.__init__`, the `layout.addWidget(...)` calls go YouTube box → Twitch box → AudioAddict box → close button (`accounts_dialog.py:109–114`).

  Why this order (user choice): YouTube first matches its newly-elevated position in the user's mental model (just moved here); Twitch second preserves it as the established account surface; AudioAddict third.

  Tests in `tests/test_accounts_dialog.py` that assert group presence/ordering (if any) need updating. Initial scan shows assertions are by widget reference, not positional order — verify during planning.

### Standalone dialog disposition

- **D-10:** `CookieImportDialog` (the 3-tab File/Paste/Google widget) stays in place — file unchanged. It loses one caller (`main_window._open_cookie_dialog` is removed) and gains one new caller (`AccountsDialog._on_youtube_action_clicked` or equivalent). Constructor signature `CookieImportDialog(toast_callback, parent)` is preserved.

- **D-11:** `tests/test_cookie_import_dialog.py` is unchanged — the dialog's behavior is identical, only its launch site moves.

### Hamburger menu changes

- **D-12:** Remove from `main_window.py`:
  - Line 148–149: `act_cookies = self._menu.addAction("YouTube Cookies")` + `triggered.connect(self._open_cookie_dialog)`.
  - Lines 665–668: `_open_cookie_dialog` method definition.
  - Line 55: import `from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog` (no longer used in `main_window.py` after the remove; `AccountsDialog` does its own import).

- **D-13:** Update `tests/test_main_window_integration.py`:
  - Line 395–406 `EXPECTED_ACTION_TEXTS` — remove "YouTube Cookies", length goes 10 → 9.
  - Line 410 `test_hamburger_menu_actions` — assertion text is computed against `EXPECTED_ACTION_TEXTS`, just the list change carries through.
  - Line 417–421 `test_hamburger_menu_separators` — separator count expectation is 3; verify whether removing "YouTube Cookies" leaves any orphan separator (it sits between "Accent Color" and "Accounts" in Group 2, so removing it does NOT affect the separator structure — still 3 separators between 4 groups).

### AccountsDialog signature wiring

- **D-14:** `MainWindow._open_accounts_dialog` (`main_window.py:670–677`) is updated to pass `self.show_toast` as the new `toast_callback` arg. The `_repo` and `parent=self` args are unchanged.

### Claude's Discretion

- Slot/handler attribute names: `_on_youtube_action_clicked`, `_on_youtube_disconnect`, `_youtube_status_label`, `_youtube_action_btn`, `_youtube_box` — planner picks names following the existing `_status_label` / `_action_btn` / `_aa_status_label` / `_aa_clear_btn` convention.
- Whether the YouTube `QGroupBox` body uses the same `status_font` instance as Twitch (currently shared) or constructs its own. Reusing is fine (font is read-only after `setPointSize`).
- Whether the Disconnect confirm message wording exactly matches my draft above or is reworded for tone consistency. Recommendation: stay close to the Twitch "This will delete your saved Twitch token..." wording, swap "token" → "cookies" + add the YouTube-specific re-import note.
- Whether `AccountsDialog._toast_callback` is stored as `self._toast` (matching `CookieImportDialog`) or as `self._toast_callback` (more explicit). Either works.
- Whether the `os.remove(paths.cookies_path())` call is wrapped in try/except `FileNotFoundError` defensively. Recommendation: yes, match Twitch precedent in `constants.clear_twitch_token`.
- Whether `_update_status()` is called inside `_on_youtube_action_clicked` after `dlg.exec()` returns regardless of the dialog's exit code, or only on `QDialog.DialogCode.Accepted`. Recommendation: call it unconditionally — if the user cancels the import dialog, the status was already correct and `_update_status()` is idempotent.
- Whether the new YouTube group is created via a small private builder method `_build_youtube_group()` or inline in `__init__`. Existing Twitch + AA groups are inline; staying inline is consistent.

</decisions>

<specifics>
## Specific Ideas

- The user's note that drove this — "we need a proper indication that there is a cookie saved for YT. Right now it just is assumed when saved it's there." — is the core UX argument for D-02 (file-existence status check). Mirrors the Twitch parity that already works.
- "Cookie auth" providers (Twitch + YouTube) and "key auth" providers (AudioAddict) is a real distinction — both Twitch and YouTube use cookie-based authentication harvested via `oauth_helper.py` subprocess (Twitch via `--mode twitch`, YouTube via `--mode google`), while AudioAddict uses a typed listen key. User-chosen group order (YouTube → Twitch → AudioAddict) doesn't strictly group by this dimension but keeps the two cookie-auth providers adjacent.
- Phase 48 D-04 explicitly carved AccountsDialog as read-only for AA; Phase 53 preserves that constraint. The follow-up phase (deferred below) is the right place to revisit it with full discussion.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements

- `.planning/ROADMAP.md` §"Phase 53: YouTube Cookies into Accounts Menu" — goal, dependencies (none), three success criteria.
- `.planning/REQUIREMENTS.md` §BUG-04 — the underlying bug requirement.
- `.planning/PROJECT.md` Key Decisions table — Phase 22 (cookie import via file/paste/Google login, 0o600 perms, hamburger menu entry — the entry being removed by Phase 53); Phase 999.7 (cookie_utils temp-copy + corruption auto-clear); Phase 48 D-04 ("AccountsDialog never writes a new AA key" — preserved by Phase 53).

### Code touch points (load these to understand current state)

#### AccountsDialog (the surface being extended)

- `musicstreamer/ui_qt/accounts_dialog.py:53–117` — class `AccountsDialog` constructor — Twitch + AudioAddict groups + close button. Phase 53 inserts the YouTube group, reorders, and adds `toast_callback` param.
- `musicstreamer/ui_qt/accounts_dialog.py:122–123` — `_is_connected()` — exact pattern Phase 53 mirrors for `_is_youtube_connected()`.
- `musicstreamer/ui_qt/accounts_dialog.py:129–150` — `_update_status()` — extends to also update the YouTube row.
- `musicstreamer/ui_qt/accounts_dialog.py:179–195` — `_on_action_clicked()` — Twitch action handler precedent.
- `musicstreamer/ui_qt/accounts_dialog.py:208–220` — `_on_aa_clear_clicked()` — Yes/No confirm precedent for Disconnect.

#### Hamburger menu (the surface being trimmed)

- `musicstreamer/ui_qt/main_window.py:54–55` — imports of `AccountsDialog` and `CookieImportDialog`. The `CookieImportDialog` import is removed by Phase 53 (`AccountsDialog` does its own import inside `_on_youtube_action_clicked` or at module top).
- `musicstreamer/ui_qt/main_window.py:148–149` — `act_cookies = self._menu.addAction("YouTube Cookies")` + connect. Removed.
- `musicstreamer/ui_qt/main_window.py:151–152` — `act_accounts = self._menu.addAction("Accounts")` + connect. UNCHANGED — this is the new (and only) launch point for cookie management.
- `musicstreamer/ui_qt/main_window.py:665–668` — `_open_cookie_dialog()` — removed.
- `musicstreamer/ui_qt/main_window.py:670–677` — `_open_accounts_dialog()` — updated to pass `self.show_toast` as the new `toast_callback` arg.

#### CookieImportDialog (the child dialog, unchanged)

- `musicstreamer/ui_qt/cookie_import_dialog.py:70–115` — class `CookieImportDialog` constructor. Constructor signature `(toast_callback, parent)` preserved.
- `musicstreamer/ui_qt/cookie_import_dialog.py:299–308` — `_write_cookies()` — already calls `self._toast(...)` then `self.accept()` on success. Phase 53 relies on `accept()` returning so the parent dialog can call `_update_status()`.

#### Path + corruption helpers (read-only reference)

- `musicstreamer/paths.py:46` — `cookies_path()` — returns the canonical YouTube cookie file path. Used by Phase 53 for both status check (`os.path.exists`) and Disconnect (`os.remove`).
- `musicstreamer/cookie_utils.py:8–65` — `temp_cookies_copy()` and `is_cookie_file_corrupted()` — NOT called directly by Phase 53 status logic, but their existence is why D-02 (existence-only status check) is safe. Auto-clear path remains the corruption recovery.
- `musicstreamer/constants.py` — `clear_twitch_token()` — Twitch precedent for "delete the auth file"; YouTube Disconnect mirrors the structure.

#### Tests (must update + add)

- `tests/test_main_window_integration.py:395–421` — `EXPECTED_ACTION_TEXTS` list update + assertions (`test_hamburger_menu_actions`, `test_hamburger_menu_separators`).
- `tests/test_accounts_dialog.py` — fixture(s) need the new `toast_callback` arg; new tests for the YouTube group: status reflects file existence, button label toggles with state, Disconnect confirm + os.remove call, post-import `_update_status()` re-runs, group order is `[YouTube, Twitch, AudioAddict]`.
- `tests/test_cookie_import_dialog.py` — UNCHANGED. Dialog behavior is identical.

### Project conventions (apply during planning)

- **T-40-04:** All `QLabel` instances rendering user-derived text must `setTextFormat(Qt.TextFormat.PlainText)`. Applies to the new YouTube status label.
- **T-40-08:** 0o600 permissions immediately after cookie write — preserved by `CookieImportDialog._write_cookies` (unchanged).
- **QA-05:** Bound-method connections, no self-capturing lambdas. Applies to all new signal connections (`_action_btn.clicked`, `_youtube_action_btn.clicked`).
- **Phase 48 D-04:** AccountsDialog never *writes* a new AudioAddict listen key. Preserved by Phase 53. Reversal is deferred (see below).
- **Phase 999.7:** Cookie corruption recovery is `cookie_utils.is_cookie_file_corrupted()` + auto-clear on read + toast. Phase 53 does not duplicate or override this path; the AccountsDialog status check intentionally trusts file existence.

### No external specs

No ADRs or external design docs. The bug is fully captured by the three ROADMAP success criteria + decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`AccountsDialog` group-box pattern** — Twitch and AA groups already implement the exact (status label + action button + confirm dialog + status-refresh) pattern. The YouTube group is the third instance.
- **`paths.cookies_path()`** — single source for the canonical cookie file path. Used by both the status check (`os.path.exists`) and Disconnect (`os.remove`).
- **`CookieImportDialog`** — existing 3-tab dialog (`cookie_import_dialog.py`) reused unchanged as the child dialog. Constructor `(toast_callback, parent)` already accepts the toast callback we need to forward from MainWindow.
- **`constants.clear_twitch_token`** — precedent for "remove the persisted auth file with try/except FileNotFoundError" — YouTube Disconnect mirrors the structure (or simply uses `os.remove(paths.cookies_path())` directly with try/except).
- **`MainWindow.show_toast`** — existing toast surface; AccountsDialog gains a `toast_callback` arg that defaults to a no-op lambda but is wired to `self.show_toast` at the call site.
- **`QMessageBox.question` Yes/No confirm with default=No** — established pattern at `accounts_dialog.py:182–189` (Twitch Disconnect) and `accounts_dialog.py:210–217` (AA Clear). YouTube Disconnect uses the same idiom.

### Established Patterns

- **`setTextFormat(Qt.TextFormat.PlainText)` on every status label** (T-40-04) — applied to new YouTube status label.
- **Bound-method signal connections** (QA-05) — `_action_btn.clicked.connect(self._on_action_clicked)` style; no self-capturing lambdas.
- **Single button toggles label by state** — Twitch precedent: same `QPushButton` reads "Connect Twitch" or "Disconnect" depending on `_is_connected()`. YouTube mirrors this with "Import YouTube Cookies..." / "Disconnect".
- **Status updated after every state-changing action** — `_update_status()` runs after Connect, Disconnect, AA Clear, and now after YouTube Disconnect + post-import.
- **Hamburger menu group structure** — 4 groups separated by `_menu.addSeparator()`. Removing "YouTube Cookies" from Group 2 (Settings) does not break the group structure (separators remain at the same boundaries).

### Integration Points

- **`AccountsDialog.__init__` signature** — gains `toast_callback: Callable[[str], None] | None = None` (defaulting None for back-compat). Caller (`MainWindow._open_accounts_dialog`) passes `self.show_toast`.
- **AccountsDialog ↔ CookieImportDialog** — AccountsDialog constructs `CookieImportDialog(self._toast_callback, parent=self)` inside the YouTube action slot. Reuses the existing dialog file unchanged.
- **MainWindow ↔ AccountsDialog** — only two changes: drop `act_cookies` action + slot; pass `self.show_toast` into `AccountsDialog(self._repo, toast_callback=self.show_toast, parent=self)`.
- **No new state, no new DB column, no new SQLite migration** — file existence is the source of truth for "Connected".
- **No Player API change** — Phase 53 is purely UI surgery on the menu + dialog.

</code_context>

<deferred>
## Deferred Ideas

- **Set/update AudioAddict listen key from `AccountsDialog`.** User raised this during discussion: "is there a way we can include the ability to set the AA streamkey from here?" The current AA group is read-only (Phase 48 D-04); the only path to *set* a key is `ImportDialog` → AudioAddict tab. Reversing Phase 48 D-04 is a legitimate symmetric polish — if Accounts is the unified account surface, AA should accept writes too. Out of scope for Phase 53 because: (1) it adds new write semantics + validation decisions, (2) Phase 48's narrowing was deliberate, (3) the ROADMAP success criteria are scoped to YouTube-cookie consolidation only. **Recommendation:** call `/gsd-add-phase` after Phase 53 ships to add a dedicated "AA key entry in Accounts" phase. Open questions for that phase: inline `QLineEdit` vs. small modal entry dialog vs. opening `ImportDialog` focused on the AA tab; how the new write interacts with in-flight `ImportDialog` flows; whether "Set" replaces or augments "Clear" (button group vs. button toggle).
- **Surfacing YouTube "Connected" status outside `AccountsDialog`** — e.g. a small badge in the Now Playing panel, a toast on app startup if cookies are missing, or a persistent indicator near YouTube stations in the tree. Not requested. Out of scope.
- **Three explicit cookie-status states ("Connected" / "Corrupted (will auto-clear)" / "Not connected")** — surfacing the Phase 999.7 auto-clear behavior as a permanent indicator. Considered and rejected (D-02): two-state status mirrors Twitch/AA, and the existing toast-on-auto-clear is sufficient feedback.
- **Refactoring `CookieImportDialog` into a reusable embeddable widget** — would let the Accounts-AA pattern (inline 3-tab UI inside the QGroupBox) work, but rejected (D-10) in favor of the simpler "open as child dialog" approach. If the Accounts UI ever needs to surface the import flow without a modal, this becomes relevant.
- **Generalized "any cookie-auth provider" abstraction** in `accounts_dialog.py` (a base class or factory for groupboxes that have status + connect + disconnect). Three providers is not yet enough to abstract; revisit if a fourth cookie-auth provider lands.

</deferred>

---

*Phase: 53-youtube-cookies-into-accounts-menu*
*Context gathered: 2026-04-28*
