# Phase 48: Fix AudioAddict listen key not persisting to DB - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Persist the AudioAddict listen key to SQLite so it survives app restarts and auto-populates on next use. Expose view/clear controls in `AccountsDialog` alongside the existing Twitch group. Mask the key by default with a show toggle. Regression test covers set → reopen → readback end-to-end.

**Root cause (scouted during discussion):** `musicstreamer/ui_qt/import_dialog.py:397 _on_aa_import_clicked` reads `self._aa_key.text().strip()` and passes it directly to `_AaImportWorker` — there is NO `repo.set_setting("audioaddict_listen_key", key)` call anywhere. Phase 42's `settings_export.py:29 _EXCLUDED_SETTINGS = {"audioaddict_listen_key"}` reserves the key name for export exclusion but nothing actually writes it. The DB already has the generic `settings` table with `get_setting`/`set_setting` at `repo.py:348/354` — no migration needed.

**Carrying forward (decided in prior phases):**
- Setting key name: `audioaddict_listen_key` (already reserved in Phase 42).
- Persistence via existing `repo.set_setting`/`repo.get_setting` string round-trip — no schema change.
- Must stay out of the settings export ZIP — Phase 42 threat T-42-03 still in force.
- AccountsDialog Twitch pattern (accounts_dialog.py:94-107) is the template for the AA group.

**Out of scope** (deferred):
- Key validation at edit time — keep the "proved valid by successful fetch" model; no extra network calls from UI events.
- AudioAddict OAuth / account-based auth — listen key is a static credential from the user's AA account settings page.
- Encrypted-at-rest storage — SQLite DB is user-owned at `~/.local/share/musicstreamer/` (0700 dir, 0o600 DB file through platformdirs conventions); adding OS keyring belongs in a later security-hardening phase.
- Changes to AudioAddict fetch/import logic (`aa_import.py`) beyond the persistence hook.
- The Phase 42 read-only-DB silent-import issue (explicitly roadmap'd as owned by Phase 42).

</domain>

<decisions>
## Implementation Decisions

### Save Trigger
- **D-01:** Write the listen key to `settings` via `repo.set_setting("audioaddict_listen_key", key)` **only on successful fetch** — in `_on_aa_fetch_complete` (or equivalent success slot of `_AaFetchWorker.finished`), after `aa_import.fetch_channels_multi` returns a non-empty channel list. Guarantees we never persist a bad/expired key. Invalid-key responses (empty list, ValueError, HTTP 401/403) do NOT persist.
- **D-02:** No write on every `textChanged` and no explicit Save button — matches the existing auto-persist patterns (volume slider, accent color, stats toggle).
- **D-03:** `ImportDialog.__init__` pre-populates `self._aa_key.setText(repo.get_setting("audioaddict_listen_key", ""))`. One read at dialog construction.

### Management Surface
- **D-04:** Dual surface: ImportDialog owns editing + auto-save (D-01/D-03). AccountsDialog gets a new **AudioAddict group** for view-status + clear only. Editing stays in Import (where the successful-fetch gate lives) — AccountsDialog never writes a key.
- **D-05:** AA group mirrors the Twitch group layout in `accounts_dialog.py:44-56`:
  - `QGroupBox("AudioAddict")`
  - Status `QLabel` — shows `"Saved"` when `get_setting("audioaddict_listen_key", "")` is non-empty, `"Not saved"` otherwise. `Qt.TextFormat.PlainText` per T-40-04 pattern.
  - Single `QPushButton` — label `"Clear saved key"` when saved (enabled), grayed `"No key saved"` when empty (disabled). Follows the Twitch single-action pattern.
- **D-06:** Clicking Clear prompts via `QMessageBox.question` (Yes/No, default No), message: `"This will delete your saved AudioAddict listen key. You will need to re-enter it from Import Stations."`. On Yes → `repo.set_setting("audioaddict_listen_key", "")` + `_update_status()` + status label flips. On No → no-op. Mirrors `_on_action_clicked` Twitch disconnect flow (accounts_dialog.py:94-107).
- **D-07:** AccountsDialog's `_update_status()` helper is extended to refresh BOTH groups. Twitch logic unchanged.

### Display Security
- **D-08:** `self._aa_key.setEchoMode(QLineEdit.EchoMode.Password)` at construction — prefilled keys display as dots.
- **D-09:** Add an icon-only "Show" toggle button next to the field. `QToolButton.setCheckable(True)`. When checked → `EchoMode.Normal`; when unchecked → `EchoMode.Password`. Use `QIcon.fromTheme("view-reveal-symbolic", QIcon.fromTheme("document-properties"))` with a local fallback SVG if neither theme icon is available. Keep monochrome/symbolic style consistent with existing icons in `musicstreamer/ui_qt/icons/`.
- **D-10:** Tooltip on the Show button: `"Show key"` when unchecked, `"Hide key"` when checked. Update in the toggle slot.

### Regression Test Shape
- **D-11:** Primary test is a **widget-level save → reopen → readback** using pytest-qt and a FakeRepo:
  1. Instantiate `ImportDialog(repo=fake_repo, …)` with `audioaddict_listen_key` setting empty.
  2. Set `self._aa_key.setText("test-key-abc")`, click Import, drive `_AaFetchWorker.finished` with a non-empty channel list (can stub the worker).
  3. Assert `fake_repo.settings["audioaddict_listen_key"] == "test-key-abc"`.
  4. Close dialog, instantiate a new `ImportDialog(repo=fake_repo, …)` with the same repo.
  5. Assert `dialog._aa_key.text() == "test-key-abc"` on open.
- **D-12:** Additional targeted tests:
  - **`test_import_dialog_prefills_key_on_open`** — set setting, open dialog, assert field prefilled.
  - **`test_import_dialog_does_not_persist_on_failed_fetch`** — drive `_AaFetchWorker.error` (invalid_key, no_channels, network), assert setting UNCHANGED.
  - **`test_accounts_dialog_aa_group_reflects_saved_status`** — status label flips based on `get_setting` value at open + after Clear.
  - **`test_accounts_dialog_clear_aa_key_requires_confirm`** — monkeypatch `QMessageBox.question` to return No, assert setting unchanged; monkeypatch to Yes, assert cleared + status updates.
  - **`test_aa_key_field_masked_by_default`** — assert `echoMode() == Password` at construction when key is prefilled.
  - **`test_aa_key_show_toggle_flips_echo_mode`** — click the toggle, assert `echoMode()` is `Normal`; click again, assert `Password`.
  - **`test_settings_export_still_excludes_aa_key`** — regression guard on Phase 42 T-42-03: set the key, run `build_zip`, extract settings.json, assert `audioaddict_listen_key` is absent. (Extend the existing `test_credentials_excluded` in `tests/test_settings_export.py` with a non-empty saved value case.)
- **D-13:** No subprocess/app-restart simulation — widget-level reopen with shared FakeRepo covers the failure path faithfully and runs in the existing pytest-qt lane.

### Claude's Discretion
- Exact widget layout of the AA group in AccountsDialog — copy the Twitch group geometry (GroupBox + VBoxLayout + Label + Button). Planner may add/omit a small `QLabel` with the AA account-settings URL as a hint.
- Whether `ImportDialog` needs a `repo` constructor argument (new) or reads repo via an existing mechanism. Scout: `ImportDialog.__init__` currently takes `repo` at `import_dialog.py:161` — confirm during planning and pass through if so; otherwise add `repo` as a new required kwarg.
- Show-toggle icon choice — pick an existing theme icon (`view-reveal-symbolic` / `view-conceal-symbolic`) first; add a bespoke SVG to `icons.qrc` only if theme lookup fails across GNOME + non-GNOME envs. Not worth a new SVG if a theme icon renders.
- Save trigger placement within the fetch-success slot — before or after `_set_aa_busy(False)`. Either order is correct; prefer before (write first, then UI updates) so the regression test doesn't have to wait for UI polling.

### Folded Todos
None.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior context
- `.planning/phases/42-settings-export-import/42-CONTEXT.md` — Phase 42 decisions, especially T-42-03 (credential exclusion contract).
- `.planning/phases/42-settings-export-import/42-UAT.md:43-46` — the skipped Round-Trip test that this phase unblocks.
- `.planning/phases/42-settings-export-import/42-VERIFICATION.md:107` — Phase 42's SYNC-02 exclusion note; Phase 48 must not regress this.
- `.planning/phases/40-auth-dialogs-accent/40-CONTEXT.md` — original AccountsDialog design decisions (Twitch scope, dialog conventions).

### Bug site
- `musicstreamer/ui_qt/import_dialog.py:248-250` — `_aa_key` QLineEdit construction (placeholder only, no EchoMode, no prefill).
- `musicstreamer/ui_qt/import_dialog.py:397-424` — `_on_aa_import_clicked` flow; the success path is where D-01 save writes belong.
- `musicstreamer/ui_qt/import_dialog.py:113-157` — `_AaFetchWorker` and `_AaImportWorker` classes; confirm which emits the "successful fetch" signal that the save handler listens to.

### Persistence surface
- `musicstreamer/repo.py:348` — `get_setting(key, default)`.
- `musicstreamer/repo.py:354` — `set_setting(key, value)`.
- `musicstreamer/settings_export.py:29` — `_EXCLUDED_SETTINGS = {"audioaddict_listen_key"}` (DO NOT REMOVE — Phase 42 contract).

### Accounts UI
- `musicstreamer/ui_qt/accounts_dialog.py:44-56` — Twitch `QGroupBox` layout template for the new AA group.
- `musicstreamer/ui_qt/accounts_dialog.py:74-88` — `_is_connected` + `_update_status` helper pattern; extend with `_is_aa_key_saved` + combined status refresh (D-07).
- `musicstreamer/ui_qt/accounts_dialog.py:94-107` — `_on_action_clicked` Twitch disconnect confirmation pattern (D-06).

### Test anchors
- `tests/test_settings_export.py::test_credentials_excluded` — existing Phase 42 regression guard to extend per D-12's last bullet.
- `tests/test_accent_color_dialog.py` — pytest-qt dialog-test shape reference (qtbot.addWidget, FakeRepo pattern).

### External
- None — pure bug fix + small UX extension; no new framework docs needed.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`repo.get_setting`/`set_setting`** — three-line write + one-line read. All three setting operations (save on fetch, prefill on open, clear from Accounts) ride this contract.
- **AccountsDialog Twitch group template** — copy the GroupBox/Label/Button structure verbatim; swap the state machine to read `get_setting("audioaddict_listen_key", "")` instead of `twitch_token_path()` existence.
- **QMessageBox confirm pattern** at `accounts_dialog.py:97-104` — identical shape for the Clear confirm in D-06.
- **FakeRepo pattern in existing widget tests** — use the same `fake_repo.settings` dict approach for Phase 48 tests.
- **`_EXCLUDED_SETTINGS` export guard** — already in place; D-12's last test just extends coverage with a non-empty stored value.

### Established Patterns
- Single-source-of-truth DB write: settings table via `set_setting(key, str)`. No sharded config files.
- Dialogs take `repo` as a constructor argument where settings interaction is needed (see DiscoveryDialog, EditStationDialog). Passing `repo` to ImportDialog if not already threaded follows convention.
- Status-driven single action button: Twitch pattern (one button whose label/action changes with state). AA group mirrors this.
- Password-style masked QLineEdit for credentials: **new pattern for this project** — the Twitch token is file-backed so the UI never exposes it; AA listen key is the first credential shown in a QLineEdit, so D-08/D-09 establish the mask-by-default convention for future credentials.

### Integration Points
- **ImportDialog `__init__`:** one `setText(get_setting(…))` call for prefill + `setEchoMode(Password)` + Show toggle wiring.
- **ImportDialog fetch-success slot:** one `set_setting(…)` call before UI update.
- **AccountsDialog `__init__`:** one new `QGroupBox("AudioAddict")` added to the main layout above the Close button box; `_update_status()` extended to cover the new group.
- **Test files:** extend `tests/test_import_dialog.py` (if exists; grep first) and `tests/test_accounts_dialog.py` (if exists); extend `tests/test_settings_export.py::test_credentials_excluded`.

</code_context>

<specifics>
## Specific Ideas

- **No encryption at rest** is explicit (out-of-scope) — SQLite DB is user-owned and treated as a trust boundary. Future security phase can add OS keyring if needed.
- **Masked-by-default** (D-08) aligns with how `_EXCLUDED_SETTINGS` treats the key: it's a secret at the file-sync layer, so it should look like a secret in the UI too.
- **Regression test at widget level** (D-11) matches the actual failure surface — the bug is "UI never calls set_setting", so testing the UI's persistence hook is exactly the right level.
- **Phase 42 Round-Trip UAT test 7** (currently skipped) becomes unblocked once this lands — no separate task; just rerun `/gsd-verify-work 42` and flip test 7 from skipped to passing.

</specifics>

<deferred>
## Deferred Ideas

- **AA key validation on edit** — network call to verify before saving. Rejected; "successful fetch" is an implicit validator.
- **OS keyring / DPAPI / Secret Service** encrypted storage for credentials. Future security-hardening phase.
- **"Remember my key" checkbox opt-out** — explicit user consent for persistence. Not requested; the persist-by-default is standard for this app (volume, accent, favorites all auto-persist).
- **Multi-account AA** support (multiple listen keys, switcher). Out of scope — single-user desktop app, one key max.
- **Display a masked preview of the stored key** (first 4 / last 4 chars) in AccountsDialog without a Show toggle. Maybe useful as a future polish; D-05 keeps AccountsDialog simple with just a "Saved"/"Not saved" string.

</deferred>

---

*Phase: 48-fix-audioaddict-listen-key-not-persisting-to-db-settings-aud*
*Context gathered: 2026-04-19*
