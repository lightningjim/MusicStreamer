---
phase: 48-fix-audioaddict-listen-key-not-persisting-to-db-settings-aud
plan: 02
subsystem: ui_qt.import_dialog
tags: [pyside6, import-dialog, audioaddict, settings-persistence, regression-test, credentials-masking]
requires:
  - 48-01 (AccountsDialog repo threading — merged into base branch)
  - musicstreamer.repo.Repo.get_setting / set_setting
  - settings_export._EXCLUDED_SETTINGS guard (Phase 42)
provides:
  - ImportDialog with repo injection + AA key prefill + EchoMode.Password + show-toggle
  - _on_aa_fetch_complete success-gated persistence of audioaddict_listen_key
  - 6 AA widget tests (mask default, prefill, show toggle, persist-on-success, no-persist-on-failure, save-reopen-readback)
  - Extended test_credentials_excluded regression guard for non-empty value export exclusion
affects:
  - musicstreamer/ui_qt/main_window.py (caller at line 510 updated)
tech-stack:
  added:
    - QToolButton (PySide6.QtWidgets)
    - QIcon (PySide6.QtGui)
  patterns:
    - "Duck-typed repo parameter (no type annotation) matches AccentColorDialog convention"
    - "Mask-by-default credential input with QToolButton show-toggle → new pattern for future credential UIs"
    - "set_setting at TOP of success slot (before worker spawn) to avoid import-thread races"
key-files:
  modified:
    - musicstreamer/ui_qt/import_dialog.py
    - musicstreamer/ui_qt/main_window.py
    - tests/test_import_dialog_qt.py
    - tests/test_settings_export.py
  created:
    - .planning/phases/48-fix-audioaddict-listen-key-not-persisting-to-db-settings-aud/deferred-items.md
decisions:
  - "Place repo.set_setting at TOP of _on_aa_fetch_complete (before _AaImportWorker spawn) so regression tests see the write synchronously (Research Pitfall 3)"
  - "Duck-type repo param — no type annotation — consistent with AccentColorDialog and avoids circular imports"
  - "Show-toggle uses QToolButton.toggled signal (not pressed) so state is boolean-driven"
  - "dlg_mode helper defined BEFORE its first use in test_aa_key_show_toggle_flips_echo_mode per plan-checker warning"
metrics:
  duration: ~15 minutes
  completed: 2026-04-19
  tasks: 2
  tests_added: 6
  tests_extended: 1
---

# Phase 48 Plan 02: ImportDialog AA key persistence + mask/toggle + export guard Summary

## One-liner

Wired the missing `repo.set_setting("audioaddict_listen_key", key)` call that Phase 42 UAT test 7 surfaced; added mask-by-default + show-toggle UX for the first in-UI credential field; extended the export-exclusion regression test with a non-empty value case.

## What Changed

### `musicstreamer/ui_qt/import_dialog.py`
- `__init__` signature: `(toast_callback, repo, parent=None)` — breaking change per Research Pitfall 1.
- AA `QLineEdit._aa_key` now constructed with `setEchoMode(QLineEdit.EchoMode.Password)` (D-08).
- Prefill from `self._repo.get_setting("audioaddict_listen_key", "")` on construction (D-03).
- `QToolButton self._aa_show_btn` with `view-reveal-symbolic` icon (fallback `document-properties`) — toggles echo mode and tooltip ("Show key" ↔ "Hide key") via `_on_aa_show_toggled` slot (D-09/D-10).
- Field + toggle wrapped in `QWidget` + `QHBoxLayout` so `QFormLayout.addRow` can take a single container.
- `_on_aa_fetch_complete` gains a top-of-slot persistence block: `if key and channels: self._repo.set_setting("audioaddict_listen_key", key)` (D-01). Placed BEFORE `_AaImportWorker` construction so main-thread observers see the write before any further async work.
- Workers (`_AaFetchWorker`, `_AaImportWorker`) unchanged — they still build thread-local `Repo(db_connect())` per Research Anti-Patterns.

### `musicstreamer/ui_qt/main_window.py`
- Line 510 caller: `ImportDialog(self.show_toast, self._repo, parent=self)`.
- Line 530 (AccountsDialog caller) untouched — owned by 48-01.

### `tests/test_import_dialog_qt.py`
- Added `FakeRepo` class + `fake_repo` fixture (matches AccentColorDialog template).
- `dialog` fixture now takes `toast_cb + fake_repo`.
- Added section divider + 6 new AA widget tests (see plan D-01/D-03/D-08/D-09/D-11).
- `dlg_mode(dialog)` helper defined ABOVE the test that uses it (plan-checker warning 1).
- `test_aa_key_does_not_persist_on_failed_fetch` exercises both the error slot path AND the empty-channels defensive guard.

### `tests/test_settings_export.py`
- `test_credentials_excluded` extended: seeds `audioaddict_listen_key = "test-key-abc"` BEFORE `build_zip`, then asserts the literal value string does not appear anywhere in the serialized JSON payload (not just the key name).

## Verification

```
uv run --with pytest --with pytest-qt pytest tests/test_import_dialog_qt.py tests/test_settings_export.py::test_credentials_excluded -x
# => 26 passed in 0.41s

uv run --with pytest --with pytest-qt pytest tests/test_accounts_dialog.py tests/test_import_dialog_qt.py tests/test_settings_export.py -x
# => 59 passed in 0.50s
```

All 8 acceptance criteria in each task met. AccountsDialog regression guard (48-01) still green.

## Commits

| Task | Hash    | Subject                                                                          |
| ---- | ------- | -------------------------------------------------------------------------------- |
| 1    | 0b675bc | feat(48-02): thread repo through ImportDialog + mask/toggle + persist-on-success |
| 2    | 0b8a02a | test(48-02): retrofit ImportDialog fixture + 6 AA widget tests + export guard    |

## Deviations from Plan

None — plan executed as written.

Plan-checker warnings 1 + 2 heeded:
1. `dlg_mode` helper defined above `test_aa_key_show_toggle_flips_echo_mode` (not below first use).
2. Grep-confirmed `_on_aa_fetch_error` is the actual error slot name in `import_dialog.py:431` before referencing it in `test_aa_key_does_not_persist_on_failed_fetch`.

## Deferred Issues

Pre-existing test failures unrelated to this plan logged in `deferred-items.md` — `gi` module missing in sandboxed uv env (affects tests/test_player_*, tests/test_cookies.py, tests/test_twitch_*, tests/test_windows_palette.py, tests/test_headless_entry.py) and `test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode` (Qt visibility assertion failing at baseline 33d5205). Neither regressed; both out of plan scope.

## Known Stubs

None — all data paths wired end-to-end. The Show-toggle is the only new UI surface and it is fully functional.

## Threat Flags

None. All changes map to threats already in the plan's `<threat_model>`:
- T-48-05 mitigated by `EchoMode.Password` at construction
- T-48-06 mitigated by Phase 42 export exclusion (now regression-tested with non-empty value)
- T-48-07 mitigated by `if key and channels:` success gate
- T-48-10 mitigated by no logging/print/repr added to save path

No new network endpoints, no new auth paths, no new file access patterns, no schema changes.

## Success Criteria (plan-level)

1. ✅ `repo.get_setting("audioaddict_listen_key", "")` reads the value persisted by `_on_aa_fetch_complete`.
2. ✅ A successful AA fetch (non-empty channels) writes the listen key to SQLite exactly once.
3. ✅ A failed AA fetch (error slot, empty list via defensive guard) does NOT write the key.
4. ✅ Reopening the dialog populates `self._aa_key` from SQLite.
5. ✅ `self._aa_key.echoMode()` is `Password` at construction; Show toggle flips to `Normal` and back with tooltip updates.
6. ✅ `settings_export.build_zip` excludes the key even when populated with `"test-key-abc"` (payload contains neither the key nor the value string).
7. ✅ 6 new AA widget tests pass; extended `test_credentials_excluded` passes; full scoped suite (import + accounts + settings_export) green.

## Self-Check: PASSED

Files created/modified verified:
- FOUND: musicstreamer/ui_qt/import_dialog.py (modified)
- FOUND: musicstreamer/ui_qt/main_window.py (modified)
- FOUND: tests/test_import_dialog_qt.py (modified)
- FOUND: tests/test_settings_export.py (modified)
- FOUND: .planning/phases/48-fix-audioaddict-listen-key-not-persisting-to-db-settings-aud/deferred-items.md (created)

Commits verified:
- FOUND: 0b675bc (Task 1: feat)
- FOUND: 0b8a02a (Task 2: test)
