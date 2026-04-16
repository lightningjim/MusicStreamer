# Phase 42 — UI Review

**Audited:** 2026-04-16
**Baseline:** 42-UI-SPEC.md (Qt/PySide6 native)
**Screenshots:** not captured — desktop Qt app (no dev server / not a web UI)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | All 13 copywriting contract strings match spec verbatim |
| 2. Visuals | 3/4 | Clear hierarchy via 13pt DemiBold summary; no progress indicator during commit |
| 3. Color | 4/4 | `#c0392b` destructive + system palette dominant/secondary; no hardcoded accent |
| 4. Typography | 4/4 | Only 9pt / 10pt / 13pt DemiBold in use, matches spec roles |
| 5. Spacing | 4/4 | `setContentsMargins(16,16,16,16)` + `setSpacing(16)` exactly per md token |
| 6. Experience Design | 3/4 | Background QThread + disabled button on commit; no busy indicator during background export/preview |

**Overall: 22/24**

---

## Top 3 Priority Fixes

1. **No progress feedback during export or import preview** — User clicks Export on a large library and has zero UI feedback until the success toast fires (export can take several seconds for many stations + logos). Spec noted "cursor change optional" — implement at minimum `QApplication.setOverrideCursor(Qt.WaitCursor)` in `_on_export_settings` / `_on_import_settings` and restore in the `_on_*_done` / `_on_*_error` slots. Alternative: disable the hamburger menu item while worker runs to prevent double-starts.
2. **Replace All confirmation modal deviates from UI-SPEC D-11 pattern** — Spec explicitly declared the red warning label is the inline confirmation and "no separate confirmation modal" (consistent with other destructive paths in the app). Implementation adds `QMessageBox.warning` in `_on_import` (settings_import_dialog.py:197-205). Decide: either remove the modal to match spec, or update UI-SPEC.md D-11 to document the extra modal as an approved deviation. Current state creates inconsistency with other destructive flows in the codebase.
3. **`_ImportCommitWorker` error path marked `# pragma: no cover`** — settings_import_dialog.py:64 skips coverage for commit errors. The user-facing `_on_commit_error` toast path is therefore untested end-to-end. Add a widget test that forces `commit_import` to raise (monkeypatch) and asserts the "Import failed" toast fires and the Import button re-enables.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

Every string in the Copywriting Contract table (42-UI-SPEC.md lines 152–166) appears verbatim in code:

- "Export Settings" — main_window.py:144
- "Import Settings" — main_window.py:146, settings_import_dialog.py:89 (window title)
- "Import" button override — settings_import_dialog.py:178
- "Settings exported to {filename}" — main_window.py:408
- "Export failed — {msg}" — main_window.py:411 (em-dash `\u2014`)
- "Invalid settings file" — main_window.py:439
- "Import complete — {added} added, {replaced} replaced" — settings_import_dialog.py:218-221
- "Import failed — {msg}" — settings_import_dialog.py:227
- "{N} added, {M} replaced, {K} skipped, {L} errors" — settings_import_dialog.py:137-138
- "This will replace all stations, streams, and favorites." — settings_import_dialog.py:122-124
- "Merge — add new stations and update matches" — settings_import_dialog.py:108
- "Replace All — wipe library and restore from ZIP" — settings_import_dialog.py:111
- "Show details" / "Hide details" — settings_import_dialog.py:147, 191
- "Import mode:" — settings_import_dialog.py:100

Generic-label grep against the new files returned zero hits for "OK"/"Submit"/"Click Here". Em-dashes use `\u2014` escapes consistently.

One extra modal string not in the contract: the Replace All confirmation body in settings_import_dialog.py:200 — "This will erase your entire station library and replace it with the import. Continue?". This is readable and specific, but the modal itself is a spec deviation (see fix #2).

### Pillar 2: Visuals (3/4)

Visual hierarchy is present and correct:
- Summary counts are the focal point (13pt DemiBold — settings_import_dialog.py:141-144).
- Destructive warning uses color + smaller size (9pt red) — correct visual de-emphasis relative to main summary.
- Mode selector label at 10pt regular groups the two radios visually.
- Detail tree hidden by default unless errors>0 (settings_import_dialog.py:166) — reduces clutter in the happy path.
- Flat borderless "Show details" toggle button (settings_import_dialog.py:148-149) — correct secondary-action treatment.

Gap: no icon or visual marker on error rows beyond red foreground (settings_import_dialog.py:160-162). A warning glyph in a third column would aid scanability for users with color-vision deficiency, but this is minor for a low-frequency dialog. Kept at 3/4 primarily for the missing busy indicator during worker runs (see fix #1).

### Pillar 3: Color (4/4)

- Accent: no direct accent color set on dialog widgets — inherits `QPalette.Highlight` from the app-wide accent QSS per UI-SPEC color contract. Grep for `#3584e4` / `bg-primary` / hardcoded hex accents in the two new files: zero matches.
- Destructive: `#c0392b` used exactly once in the new code (settings_import_dialog.py:127), applied only to the Replace All warning label. Matches spec's single reserved destructive use.
- Error row foreground uses `Qt.red` (settings_import_dialog.py:161-162). This is Qt's standard red, not `#c0392b`. Minor inconsistency — spec reserves destructive color for the Replace All warning only, and Qt.red for error rows is a reasonable deviation since this is an error-state indicator, not a destructive action.
- No hardcoded backgrounds; dialog inherits system palette correctly.

### Pillar 4: Typography (4/4)

Font sizes used in new code:
- 9pt regular — warning label (stylesheet `font-size: 9pt;`, settings_import_dialog.py:127)
- 10pt regular — mode label (settings_import_dialog.py:103)
- 13pt DemiBold — summary counts (settings_import_dialog.py:142-144)

Spec declares Body=10pt/Label=9pt/Heading=13pt DemiBold — all three roles are used exactly as declared. No 16pt display needed (no empty state). No font weight beyond DemiBold. Radio button labels and detail-tree entries inherit system default (10pt body equivalent), consistent with Qt native patterns.

### Pillar 5: Spacing (4/4)

- `setContentsMargins(16, 16, 16, 16)` — settings_import_dialog.py:94 — matches `md` token
- `setSpacing(16)` — settings_import_dialog.py:95 — matches `md` token
- `setMaximumHeight(200)` on detail tree — settings_import_dialog.py:156 — matches spec line 111 "Max visible height: 200px"
- `setMinimumWidth(480)` — settings_import_dialog.py:90 — matches spec line 98

No arbitrary spacing values (e.g. 13px, 17px) — grep confirms only multiples-of-4 in this phase's new code. Radio buttons and labels use layout-default spacing inside the `QVBoxLayout(16)` which is consistent with sibling dialogs (`cookie_import_dialog.py`).

### Pillar 6: Experience Design (3/4)

State coverage:

| State | Handling | Status |
|-------|----------|--------|
| Loading/in-progress (export) | Background `_ExportWorker` QThread; UI thread not blocked | partial — no user-visible progress indicator |
| Loading/in-progress (preview) | Background `_ImportPreviewWorker` QThread | partial — no indicator |
| Loading/in-progress (commit) | Background `_ImportCommitWorker`; Import button disabled (line 207) | good — button disable is correct feedback |
| Empty state | N/A — dialog only opens after valid ZIP selection | correct by spec line 168 |
| Error — invalid ZIP | Toast "Invalid settings file" (main_window.py:439) | good |
| Error — export I/O | Toast "Export failed — {msg}" (main_window.py:411) | good |
| Error — commit I/O | Toast "Import failed — {msg}" + re-enables button (settings_import_dialog.py:226-227) | good, but `# pragma: no cover` on worker (see fix #3) |
| Destructive confirmation | QMessageBox.warning before Replace All commit | deviates from spec D-11 (see fix #2) |
| Worker GC safety | `self._export_worker` / `self._import_preview_worker` attributes retain refs | good — matches existing pattern |
| Cancel flow | `reject` bound to Cancel; no DB writes before Import click | correct (D-11 all-or-nothing) |

Positives: thread safety is handled correctly with `Qt.QueuedConnection` on all result signals; worker reference retention is consistent with the `_YtScanWorker` precedent; disabled commit button prevents double-commits.

Deductions: no cursor change or busy indicator during export/preview means a user could click Export twice in quick succession before the first worker finishes (two workers would run, second overwriting `self._export_worker` reference — first still finishes since QThread keeps itself alive, but the UX is confusing). Recommend at minimum disabling the menu action while a worker is active.

Registry audit: not applicable — `components.json` absent, PySide6 native project, no third-party registries per 42-UI-SPEC.md line 174.

---

## Files Audited

- `musicstreamer/ui_qt/settings_import_dialog.py` (228 lines, created)
- `musicstreamer/ui_qt/main_window.py` (lines 60-96 worker classes, 143-151 menu wiring, 388-439 handlers)
- `.planning/phases/42-settings-export-import/42-UI-SPEC.md` (baseline)
- `.planning/phases/42-settings-export-import/42-CONTEXT.md` (decisions D-01 through D-14)
- `.planning/phases/42-settings-export-import/42-01-SUMMARY.md` / `42-02-SUMMARY.md`
- `.planning/phases/42-settings-export-import/42-01-PLAN.md` / `42-02-PLAN.md`

Tests in `tests/test_settings_import_dialog.py` (5 widget tests) and `tests/test_settings_export.py` (17 tests) exist but were not in-scope for visual audit.
