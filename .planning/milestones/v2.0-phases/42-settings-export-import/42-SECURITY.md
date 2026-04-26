---
phase: 42
slug: settings-export-import
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-16
---

# Phase 42 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| ZIP file -> app (preview_import) | Untrusted archive content from user-selected file | Station/stream metadata, settings, logo bytes |
| JSON payload -> SQLite (commit_import) | Deserialized data written to DB in a single transaction | Station rows, stream rows, favorites, settings |
| Dialog user input -> commit worker | Mode selection (merge vs replace_all) drives DB mutation | Radio-button choice |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-42-01 | Tampering | settings_export.preview_import | mitigate | Path-traversal guard: `fname.startswith("/") or ".." in fname` raises `ValueError` — musicstreamer/settings_export.py:180-183 | closed |
| T-42-02 | Denial of Service | settings_export.preview_import | accept | ZIP-bomb risk accepted for personal-use single-user app; stdlib `zipfile` already streams — see Accepted Risks Log | closed |
| T-42-03 | Information Disclosure | settings_export.build_zip | mitigate | `_EXCLUDED_SETTINGS = {"audioaddict_listen_key"}` filters credentials from export — musicstreamer/settings_export.py:28, applied at :119-123 | closed |
| T-42-04 | Tampering | settings_export.commit_import | mitigate | All DB writes use parameterized `repo.con.execute(sql, (?, ...))` — see musicstreamer/settings_export.py:242-296, :304-342, :367-397 | closed |
| T-42-05 | Tampering | SettingsImportDialog._on_import | mitigate | `QMessageBox.warning` confirmation before Replace All commit — musicstreamer/ui_qt/settings_import_dialog.py:196-205 | closed |
| T-42-06 | Denial of Service | _ExportWorker / _ImportPreviewWorker / _ImportCommitWorker | mitigate | All ZIP/DB I/O runs on `QThread` subclasses with `Qt.QueuedConnection` result signals — main_window.py:63, 81; settings_import_dialog.py:48 | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

### Evidence Summary

| Threat ID | Evidence Location |
|-----------|-------------------|
| T-42-01 | musicstreamer/settings_export.py:180-183 |
| T-42-02 | Accepted Risks Log entry R-42-01 below |
| T-42-03 | musicstreamer/settings_export.py:28, :119-123 |
| T-42-04 | musicstreamer/settings_export.py:242-296, :304-342, :367-397 |
| T-42-05 | musicstreamer/ui_qt/settings_import_dialog.py:196-205 |
| T-42-06 | musicstreamer/ui_qt/main_window.py:63-95, :401-430; musicstreamer/ui_qt/settings_import_dialog.py:48-65, :207-215 |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-42-01 | T-42-02 | ZIP-bomb (decompression-ratio DoS) is low risk for a single-user personal-use desktop app where the user chooses the archive themselves. Python stdlib `zipfile` streams members rather than loading the full archive into memory, bounding the attack. No explicit size cap added. | Kyle Creasey | 2026-04-16 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-16 | 6 | 6 | 0 | gsd-security-auditor |

---

## Unregistered Threat Flags

None — both phase summaries (42-01-SUMMARY.md, 42-02-SUMMARY.md) report "None" in their `## Threat Flags` sections. No new network endpoints, auth paths, or trust-boundary changes beyond the registered ZIP-import surface.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-16
