---
phase: 32
slug: add-twitch-authentication-via-streamlink-oauth-token
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-10
---

# Phase 32 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| token file → subprocess args | OAuth token read from disk injected into streamlink CLI args | OAuth bearer token (secret) |
| WebKit2 subprocess → token file | Embedded browser process writes captured cookie to temp file; parent reads it | OAuth bearer token (secret) |
| Twitch login page → WebKit2 | User credentials entered in embedded browser; auth-token cookie captured | User credentials, session cookie |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-32-01 | Information Disclosure | TWITCH_TOKEN_PATH file | mitigate | `os.open(path, O_WRONLY\|O_CREAT\|O_TRUNC, 0o600)` then `os.fdopen` — mode atomic at creation. See `musicstreamer/ui/accounts_dialog.py:402-404`. | closed |
| T-32-02 | Tampering | subprocess cmd / script injection | mitigate | Player: token inserted as single list element `f"Authorization=OAuth {token}"` with `read().strip()`, no `shell=True` (`musicstreamer/player.py:284-294`). Dialog: subprocess script built via `{output_path!r}` Python repr formatting, no user input (`musicstreamer/ui/accounts_dialog.py:372`, template line 599). | closed |
| T-32-03 | Information Disclosure | token in process args (/proc) | accept | See Accepted Risks R-32-01. | closed |
| T-32-04 | Spoofing | WebKit2 login page | accept | See Accepted Risks R-32-02. | closed |
| T-32-05 | Information Disclosure | temp file between subprocess and parent | mitigate | `tempfile.NamedTemporaryFile(suffix=..., delete=False)` creates unique short-lived file; `os.unlink(tmp_path)` in `finally` guarantees deletion. See `musicstreamer/ui/accounts_dialog.py:361,388-392`. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-32-01 | T-32-03 | streamlink CLI args visible in /proc to same-uid processes on Linux. Desktop app, single-user system; same exposure as existing cookie-path arguments already used for YouTube. Low risk. | Kyle Creasey | 2026-04-10 |
| R-32-02 | T-32-04 | WebKit2 loads hardcoded `https://www.twitch.tv/login`; user visually verifies the URL bar in the embedded browser, and standard HTTPS/TLS protections apply. Spoofing would require compromising twitch.tv or the local TLS trust store. | Kyle Creasey | 2026-04-10 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-10 | 5 | 5 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-10
