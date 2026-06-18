---
phase: 87B
slug: gbs-zero-token-single-song-add
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-18
---

# Phase 87B — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

**Auditor:** gsd-security-auditor (automated) · **block_on:** high · **register_authored_at_plan_time:** true

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| MusicStreamer → gbs.fm `/add/<songid>` | Authenticated GET carrying Phase 76 session cookies crosses to the GBS server. | sessionid / csrftoken (sensitive) |
| gbs_api → local logs (buffer_log / stderr) | Capture hook writes diagnostic text to a local sink that may be shared/exported. | log diagnostics (must be PII-free) |
| User click (panel) → GBSSearchDialog → gbs.fm `/add` | User-initiated add crosses into the authenticated GBS request path (reused HTTP). | songid (low sensitivity) |
| gbs.fm server → GBSSearchDialog inline display | Server messages-cookie text rendered to the user verbatim (server is truth, D-07). | server-controlled text (untrusted) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-87B-01 | Information Disclosure | `_capture_add_shape()` no-PII capture hook | mitigate | Hook logs only `endpoint=/add/<int songid>`, `message_len`, `message_category`; never cookies/sessionid/csrftoken/Authorization/raw values. Enforced by `test_capture_hook_no_pii`. — `musicstreamer/gbs_api.py:1168-1177`, `tests/test_gbs_api.py:1291-1307` | closed |
| T-87B-02 | Tampering | songid in `/add/<songid>` URL | accept | `submit()` casts `int(songid)`; non-int raises before any request. — `musicstreamer/gbs_api.py:1137` | closed |
| T-87B-03 | Spoofing/Repudiation | session-expiry on add path | accept | `add_song_zero_token()` propagates `GbsAuthExpiredError` unchanged to existing auth_expired path. — `musicstreamer/gbs_api.py:1156-1165`, `gbs_search_dialog.py:145-146` | closed |
| T-87B-04 | Tampering/Injection | server messages-cookie text rendered in dialog | accept | `_error_label` uses `Qt.TextFormat.PlainText`; no HTML interpretation. — `gbs_search_dialog.py:416, 1145` | closed |
| T-87B-05 | Spoofing | double-submit (fast double-click) | accept | Modal `dlg.exec()` blocks panel re-fire; submit button `setEnabled(False)` in-flight. — `main_window.py:1561`, `gbs_search_dialog.py:1059-1060` | closed |
| T-87B-SC | Tampering | npm/pip/cargo installs | accept | No package installs in this phase (`tech_stack.added: []` in both SUMMARYs). | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## T-87B-01 Detail (gated HIGH — mitigate disposition)

**Hook implementation** (`musicstreamer/gbs_api.py:1168-1177`):
`_capture_add_shape()` emits exactly one log call with arguments:
- `endpoint=/add/%s` ← `int(songid)` (integer, not cookie data)
- `message_len=%d` ← `len(message)` (integer byte count)
- `message_category=%s` ← one of three literals: `"empty"`, `"error"`, `"success"`

No cookies, sessionid, csrftoken, Set-Cookie, Authorization, or raw message values appear in any argument position.

**Test enforcement** (`tests/test_gbs_api.py:1291-1307`):
`test_capture_hook_no_pii` monkeypatches `gbs_api._log.warning`, calls `add_song_zero_token(...)` with a real fixture response, then asserts no logged string contains `sessionid`, `csrftoken`, `Set-Cookie`, or `Authorization`, and that at least one log call fired (confirms hook executes). Cited in Plan 01 acceptance criteria as the gate for T-87B-01.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-87B-02 | T-87B-02 | `int(songid)` coercion already present in `submit()` (called by `add_song_zero_token()`); cast predates this phase and covers all callers. | gsd-security-auditor | 2026-06-18 |
| AR-87B-03 | T-87B-03 | Session expiry is a known operational condition; surfaces via existing dialog toast + login-gate refresh. | gsd-security-auditor | 2026-06-18 |
| AR-87B-04 | T-87B-04 | `Qt.TextFormat.PlainText` is a project-wide defense-in-depth control (T-40-04); server text has no HTML injection path. | gsd-security-auditor | 2026-06-18 |
| AR-87B-05 | T-87B-05 | Per-button `setEnabled(False)` plus modal `dlg.exec()` provide sufficient double-submit protection at ASVS L1. | gsd-security-auditor | 2026-06-18 |
| AR-87B-SC | T-87B-SC | Phase introduces no new package dependencies. | gsd-security-auditor | 2026-06-18 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-18 | 6 | 6 | 0 | gsd-security-auditor (automated) |

---

## Unregistered Flags

Both SUMMARY.md `## Threat Flags` sections explicitly state no new threat surface beyond the registered threats. No unregistered flags to log.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-18
