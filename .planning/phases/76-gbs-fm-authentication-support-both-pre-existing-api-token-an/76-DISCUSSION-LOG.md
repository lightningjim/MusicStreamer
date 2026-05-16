# Phase 76: GBS.FM authentication — support both pre-existing API token and login-page cookie capture (like Google/Twitch) — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-15
**Phase:** 76-gbs-fm-authentication-support-both-pre-existing-api-token-an
**Areas discussed:** API-token meaning + functional status, In-app login subprocess shape, AccountsDialog GBS group layout, Token storage + auth precedence

---

## Gray area selection

Presented at session start; user selected ALL 4.

| Option | Description | Selected |
|--------|-------------|----------|
| API-token meaning + functional status | Phase 60 verified the gbs.fm-advertised API key returns 403 on /api/vote, /ajax, /add/, /search; only /next/<authid> admin-skip accepts it. Skip ladder #1? Re-verify? Ship paste-field anyway with caveat? Or 'API token' here means something else (e.g. raw sessionid)? | ✓ |
| In-app login subprocess shape | Add oauth_helper --mode gbs opening https://gbs.fm/accounts/login/ in QWebEngineView. Auto-detect on sessionid cookie (Twitch shape) vs. user clicks Done (Google shape). | ✓ |
| AccountsDialog GBS group layout | Today: one button. After: two paths. Expand to two stacked buttons or unified dialog with 3 tabs (File / Paste / Login)? | ✓ |
| Token storage + auth precedence | If API token coexists with cookies: SQLite setting vs. 0o600 file? When both present, which auth gets sent per endpoint? | ✓ |

---

## API-token meaning + functional status

### Q1 — Token interpretation

| Option | Description | Selected |
|--------|-------------|----------|
| The Settings-page key — worth re-verifying | Researcher re-probes /api/vote, /ajax, /add/, /search with the user's API token before we ship the paste field. Site state may have changed since 2026-05-04. | ✓ |
| Raw sessionid value, not the Settings 'API key' | User pastes just the sessionid cookie value; we construct a minimal Netscape cookies.txt internally. | |
| Ship paste-field as-is with a 'not validated' caveat | Add the paste field; store the token; let gbs_api.py opportunistically try Bearer/X-API-Key. | |
| Drop ladder #1 — only ship login-page cookie capture | Forget the API token entirely; Phase 76 only adds the login subprocess. | |

**User's choice:** Re-verify with the researcher first.
**Notes:** Default to "test before commit" — site state changes, Phase 60 data is 11 days old.

### Q2 — Fallback if re-probe still 403

| Option | Description | Selected |
|--------|-------------|----------|
| Drop the paste field; ship login subprocess only | Stop investing in non-functional surface. ROADMAP entry edited via /gsd-phase edit 76. | ✓ |
| Ship paste field with explicit 'not validated' caveat | Add the paste field anyway as forward-looking surface. | |
| Repurpose paste field for raw sessionid | If API key is dead, paste field becomes a 'paste sessionid' shortcut. | |

**User's choice:** Drop the paste field; edit ROADMAP.
**Notes:** No dead UI. Conditional scope formalized as D-03 in CONTEXT.md.

### Q3 — Storage location if re-probe succeeds

| Option | Description | Selected |
|--------|-------------|----------|
| SQLite setting 'gbs_api_token' (mirror AA listen_key) | Stored in existing settings table; settings export ZIP picks it up automatically. | ✓ |
| 0o600 file 'gbs-token.txt' (mirror Twitch token path) | New paths.gbs_token_path() helper; symmetric with Twitch. | |
| Both (token in SQLite, cookies file unchanged) | Token in SQLite; cookies in file; both coexist. | |

**User's choice:** SQLite setting `gbs_api_token`.
**Notes:** Mirrors AA listen_key (Phase 48). No new file, no migration.

### Q4 — Auth precedence when both configured

| Option | Description | Selected |
|--------|-------------|----------|
| Prefer token; fall back to cookies on 403 | gbs_api.load_auth_context() returns (token, cookies); requests try token first; on 403 retry with cookies once. | ✓ |
| Prefer cookies; token is admin-only fallback | Keep cookies as primary; token only for /next/<authid> admin-skip. | |
| User picks per-session via a radio in the GBS group | Radio button: 'Use token' vs 'Use cookies'. More UI complexity. | |

**User's choice:** Token-first with cookies fallback on 403.
**Notes:** Centralizes precedence in a new `_open_authed` helper in gbs_api.py. Single retry budget per call.

---

## In-app login subprocess shape

### Q1 — Detection mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-detect on sessionid + csrftoken (Twitch shape) | No Done button; cookieAdded watches for both cookies on .gbs.fm. | ✓ |
| User clicks 'Done — save cookies' (Google shape) | Manual confirmation button. | |
| Hybrid — auto on sessionid, manual Done as fallback | Auto-complete with manual fallback after 60s. | |

**User's choice:** Auto-detect (Twitch shape).
**Notes:** Django session cookie completion is deterministic — no need for manual confirm.

### Q2 — Output format

| Option | Description | Selected |
|--------|-------------|----------|
| Full Netscape dump (mirror Google) | Harvest ALL cookies on gbs.fm domain; write Netscape file with header. | ✓ |
| Minimal: sessionid + csrftoken only | Write only the two cookies Phase 60 needs. | |

**User's choice:** Full Netscape dump.
**Notes:** Forward-compat with site changes; matches what file/paste output already produces.

### Q3 — Timeout + failure handling

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse Twitch's 120s + Phase 999.3 categories | _GbsLoginWindow mirrors _TwitchCookieWindow exactly. | ✓ |
| 120s timeout but skip the structured JSON event stream | Simpler subprocess; loses category-aware failure UI. | |
| Skip timeout — user closes window when ready | No deadline. | |

**User's choice:** Reuse Twitch's 120s + Phase 999.3 category contract.
**Notes:** Phase 999.3 failure UI is provider-agnostic; reused with zero changes.

### Q4 — Login URL

| Option | Description | Selected |
|--------|-------------|----------|
| https://gbs.fm/accounts/login/ (direct) | Canonical login surface (Phase 60 identified as auth-expired redirect target). | ✓ |
| https://gbs.fm/ (homepage; click Login manually) | Land on homepage; user navigates. | |
| Researcher confirms the canonical URL | Don't commit yet; planner sets URL after research. | |

**User's choice:** Direct to `/accounts/login/`.
**Notes:** Mirrors `_TWITCH_LOGIN_URL` pattern.

### Q5 — Continue / next area

User selected "Next area".

---

## AccountsDialog GBS group layout

### Q1 — Group layout shape

| Option | Description | Selected |
|--------|-------------|----------|
| Two stacked buttons in the GroupBox | Status + [Connect with GBS.FM…] + [Paste API token…] (inline). Asymmetric vs YouTube/Twitch/AA but appropriate. | ✓ |
| Single button → unified dialog with 3 tabs (File / Paste cookies / Login) | More compact; buries the login option. | |
| Single button → unified dialog with 4 tabs (File / Paste cookies / Paste token / Login) | Requires generalizing CookieImportDialog beyond cookies. | |

**User's choice:** Two stacked buttons.
**Notes:** Each method visible up-front. Preview confirmed the layout intent.

### Q2 — Status label when both methods configured

| Option | Description | Selected |
|--------|-------------|----------|
| 'Connected (cookies + token)' (single label, enumerates methods) | Single line per other groups; explicit about which auth is live. | ✓ |
| Two status lines (one per method) | Cookies: Connected | Token: Saved. Heavier visually. | |
| 'Connected' only — don't enumerate methods | Cleanest visually but loses info. | |

**User's choice:** Single enumerated label.
**Notes:** User wants to see WHICH method is live, not just connected/not.

### Q3 — Inline token row UX shape

| Option | Description | Selected |
|--------|-------------|----------|
| Inline single-line in the GroupBox | [QLineEdit + Save] inside the GBS GroupBox. Less ceremony. | ✓ |
| Tiny modal QDialog — label + QLineEdit + Save/Cancel | Separate dialog. | |
| Repurpose CookieImportDialog with a fourth tab | Reuses validator pattern; adds dialog complexity. | |

**User's choice:** Inline single-line.
**Notes:** Mirrors AA's listen_key inline shape from ImportDialog.

### Q4 — Density vs sibling groups

| Option | Description | Selected |
|--------|-------------|----------|
| Accept the asymmetry — GBS is denser by necessity | GBS has two functional auth paths; sibling groups have one each. Reflects real functional difference. | ✓ |
| Hide the token row until researcher confirms it works | Feature-flag gate. | |
| Collapse token row behind a 'Show advanced' disclosure | More UX complexity. | |

**User's choice:** Accept asymmetry.
**Notes:** No symmetry-for-symmetry's-sake refactor of YouTube/Twitch/AA groups.

### Q5 — Continue / next area

User selected "Next area".

---

## Token storage + auth precedence

### Q1 — Auth vector selection strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Researcher picks based on what the gbs.fm site does now | Re-probes ALL 8 vectors; reports working ones. | ✓ |
| Default to X-API-Key header, fail if rejected | Most modern API-key convention; test that first. | |
| Mirror what gbs.fm's Settings-page documentation says verbatim | Read the Settings page; do exactly what it says. | |

**User's choice:** Researcher comprehensively re-probes.
**Notes:** Don't miss a working vector by short-circuiting.

### Q2 — Where the precedence logic lives in gbs_api.py

| Option | Description | Selected |
|--------|-------------|----------|
| Expand load_auth_context() to return (token, cookies); each endpoint helper picks | _open_authed(url, auth) tries token-auth first; on 403 retries with cookies. Single retry budget. | ✓ |
| Per-endpoint explicit pick | Each endpoint knows which auth method based on research findings. Less DRY. | |
| Always try both in parallel; first 200 wins | Wasteful and rate-limit risky. | |

**User's choice:** Centralized `_open_authed` helper with token-first precedence.
**Notes:** All call sites get the fallback for free.

### Q3 — Disconnect semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Disconnect removes BOTH | Single confirmation; clears cookies AND token. Symmetric with YouTube/Twitch/AA. | ✓ |
| Two independent Disconnect actions (one per method) | Cookies and token each have own clear action. | |
| Cookies primary; token row has its own Clear button | Top-row Disconnect clears cookies; small Clear next to token. | |

**User's choice:** Single Disconnect clears both.
**Notes:** Matches existing single-button disconnect pattern across all groups.

### Q4 — Test strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Extend Phase 60 fixture-based tests with token-vector cases | Add token-auth recordings if re-probe succeeds; test cases for token, cookies-fallback, both-fail. | ✓ |
| Mock-based tests — don't add new fixtures | Faster but no real-world contract guard. | |
| Skip token tests if re-probe still 403 | Phase 76 branches based on D-03. | |

**User's choice:** Extend Phase 60 fixture pattern with token-vector cases.
**Notes:** Three test cases per public endpoint (a) token success, (b) token-403 → cookies-success, (c) both-fail.

### Q5 — Continue / done

User selected "I'm ready for context".

---

## Claude's Discretion

Captured in CONTEXT.md under "Claude's Discretion":
- Where existing File/Paste tabs are reached after primary button repurposes.
- AuthContext shape (named tuple vs dataclass).
- `echoMode` on inline token QLineEdit (normal vs Password).
- Toast wording.
- Whether `_open_with_cookies` survives as public helper.
- Whether `import_station` participates in token-first precedence.
- Inline token row label exact wording.
- Whether to add a "Refresh status" / "Test connection" button (recommendation: NO).
- Module constant naming in `gbs_api.py` for the token vector.

## Deferred Ideas

Captured in CONTEXT.md `<deferred>`:
- "Regenerate token" button (`/keygen/` POST) — user out of scope.
- Show/hide token eye toggle (if echoMode=Password).
- Per-endpoint auth-method override (no justification yet).
- Multi-account / profile switching (single-user scope).
- OAuth proper (gbs.fm has no OAuth endpoints).
- Token caching with TTL (premature optimization).
- `AuthContext` extraction to shared module (only relevant if other providers adopt multi-method).
- Removing existing Paste/File tabs from `CookieImportDialog` (cleanup, defer).
- Token migration / auto-detection (net new if user feedback asks).
