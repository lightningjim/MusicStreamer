---
phase: 89c
slug: provider-brand-avatar-cover-slot-fallback
status: secured
threats_open: 0
threats_total: 10
threats_closed: 10
asvs_level: 1
created: 2026-06-17
---

# Phase 89c — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> 10/10 threats closed (5 mitigations verified in code, 5 accepted risks documented). No HIGH-severity threats.

**Audit date:** 2026-06-17
**ASVS Level:** 1
**Plans audited:** 89c-01, 89c-02, 89c-03
**Auditor disposition:** adversarial (every mitigation assumed absent until grep-confirmed)

---

## Threat Verification

### Mitigate-disposition threats (code evidence required)

| Threat ID | Category | Component | Status | Evidence |
|-----------|----------|-----------|--------|----------|
| T-89c-02 | DoS | QPixmap decode of bundled PNG | CLOSED | `brand_avatars.py:50` — `os.path.isfile` guard before returning path; `now_playing_panel.py:2287` — `_set_brand_avatar_pixmap` guards `pix.isNull()` → clears `_last_brand_avatar` then calls `_show_station_logo_in_cover_slot()`. Both prongs confirmed. |
| T-89c-05 | Tampering | Provider-keyed avatar file write | CLOSED | `assets.py:73` — filename derived from `f"{provider_id}.png"` (int from DB PK, not user input; no path traversal surface). `assets.py:74-88` — atomic `tempfile.mkstemp` + `os.replace` in same directory. |
| T-89c-06 | DoS | QPixmap decode of user-picked image | CLOSED | `edit_station_dialog.py:1624` — `_refresh_avatar_preview` guards `pix.isNull()` → `self._avatar_preview.clear()`. Cover-slot path separately guarded: `now_playing_panel.py:2222` — `_set_avatar_pixmap_from_path` guards `isNull()` → clears `_last_avatar_path` then calls `_show_station_logo_in_cover_slot()`. |
| T-89c-07 | Tampering | providers.avatar_path UPDATE | CLOSED | `repo.py:972-975` — dedicated `UPDATE providers SET avatar_path = ? WHERE id = ?`; single-column, scoped by `provider_id` WHERE clause; no broad-save path; commit confirmed. |
| T-89c-08 | EoP | New/unsaved station provider_id None | CLOSED | `edit_station_dialog.py:1414` — `if self._station.provider_id is None:` early return with status message at the top of `_on_choose_brand_image`, before `write_provider_avatar` call at line 1434 and `update_provider_avatar_path` call at line 1438. Guard unambiguously precedes every write. |

### Accept-disposition threats (no code verification required — recorded per register)

| Threat ID | Category | Rationale |
|-----------|----------|-----------|
| T-89c-01 | Tampering — bundled asset write | Assets ship in repo/PyInstaller bundle at install-tree trust level; same exposure as icons/. Tampering requires write access to install tree (out of scope for local desktop app at ASVS L1). |
| T-89c-03 | Information Disclosure — lookup path resolution | Filename derived from a fixed static dict; no user input reaches the path. Accepted as structural (dict is the single normalization point). |
| T-89c-04 | Tampering — provider_avatar_path read (Plan 01) | Plan 01 only reads this column; write-side validation handled in Plan 02 (T-89c-05/07/08). No new write introduced in Plan 01. |
| T-89c-09 | Information Disclosure — Qt image decoder | Same decoder exposure as every existing logo/avatar picker (_on_choose_logo). Accepted at framework level; ASVS L1 local desktop app, no remote attacker on file picker. |
| T-89c-SC | Tampering — npm/pip/cargo installs | No new packages introduced across all three plans. Stdlib + existing project code only. |

---

## Unregistered Flags

**89c-01 SUMMARY.md `## Threat Flags`:** None — no new network endpoints or trust boundaries introduced.

**89c-02 SUMMARY.md `## Threat Flags`:** None — no new network endpoints, auth paths, or trust boundaries beyond T-89c-05/06/07/08 already in the register.

**89c-03 SUMMARY.md `## Threat Flags`:** None — one-line UI fix (`_refresh_avatar_preview` in `_populate`), no new file access patterns or schema changes. Covered structurally by T-89c-06 (isNull guard in `_refresh_avatar_preview` confirmed at `edit_station_dialog.py:1624`).

No unregistered flags require escalation.

---

## Accepted Risks Log

All accepted risks are register-documented in 89c-01-PLAN.md and 89c-02-PLAN.md `<threat_model>` sections. No additional risks accepted during implementation.

---

## Audit Notes

- `_on_choose_brand_image` wraps its write sequence in a `try/except Exception` (line 1430-1441) that surfaces errors to `_avatar_status` rather than propagating them. This is a slots-never-raise defensive pattern (WR-02) consistent with the project's existing Qt slot contract; it does not weaken the security posture of T-89c-05/07/08.
- The `_resolve_brand_avatar_fallback` method (now_playing_panel.py:2232) resets all three tier-replay trackers (`_last_cover_path`, `_last_avatar_path`, `_last_brand_avatar`) before branching. This prevents stale-station bleed across tier-replay calls and is a defense-in-depth reinforcement of T-89c-02.
- `brand_avatars.lookup` wraps the `importlib.resources.files()` call in a bare `except Exception` (line 48) to satisfy the never-raise contract (D-04 Pitfall 4). This is intentional and correct for a fallback registry lookup.
- No implementation files were modified during this audit.

---

## Security Audit 2026-06-17

| Metric | Count |
|--------|-------|
| Threats found | 10 |
| Closed | 10 |
| Open | 0 |
