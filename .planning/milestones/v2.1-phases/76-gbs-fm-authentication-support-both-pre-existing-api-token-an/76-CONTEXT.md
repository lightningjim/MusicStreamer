# Phase 76: GBS.FM authentication — support both pre-existing API token and login-page cookie capture (like Google/Twitch) — Context

**Gathered:** 2026-05-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 76 expands GBS.FM authentication in `AccountsDialog` beyond Phase 60's cookies-file-only path (D-04 ladder #3) to also support **in-app login-page cookie capture** (the missing piece from Phase 60's `oauth_mode=None` deferment) and — conditionally on researcher re-verification — a **paste-API-token** path.

The roadmap framing ("like Google/Twitch") refers to the existing `_GoogleWindow` / `_TwitchCookieWindow` subprocess shapes in `musicstreamer/oauth_helper.py`: a `QWebEngineView` opens the provider's login URL in a subprocess, captures cookies on success, and writes them via the existing Netscape-cookies pipeline. Phase 76 adds the third such window (`_GbsLoginWindow`) plus a new `--mode gbs` to `oauth_helper.py`'s argparse.

The "API token" half is **gated on a researcher re-probe**. Phase 60 RESEARCH (2026-05-04) verified the gbs.fm Settings-page API key returns 403 on `/api/vote`, `/ajax`, `/add/`, `/search` across 8+ auth vectors (Bearer, X-API-Key, query-string variants, body POST, path-embedded). Only `/next/<authid>` admin-skip accepted it. Phase 76's researcher MUST re-probe before plan-phase locks the paste-field decision (site state may have changed in the 11 days since).

**In scope:**

- **New `_GbsLoginWindow` in `musicstreamer/oauth_helper.py`**, mirroring `_TwitchCookieWindow` (auto-detect on cookie observed, no Done button, 120s timeout, Phase 999.3 structured-event categories). Loads `https://gbs.fm/accounts/login/`; auto-completes when **both** `sessionid` AND `csrftoken` cookies appear on the `gbs.fm` / `.gbs.fm` domain. On success, emits a Netscape-format full cookie dump on stdout (mirror `_GoogleWindow._flush_cookies` shape — every cookie on the gbs.fm domain, not just the two trigger names) for forward-compatibility with any helper cookies (`messages`, future CSRF rotation, etc.). The existing `_validate_gbs_cookies` validator (sessionid + csrftoken + gbs.fm domain) already accepts this output.
- **New `--mode gbs` in `oauth_helper.py:main()`** — extend the argparse `choices` list to include `gbs`; wire the gbs branch to instantiate `_GbsLoginWindow`. UA profile + persistent-cookies policy mirror `_TwitchCookieWindow` (NoPersistentCookies, profile-level UA override).
- **`AccountsDialog` GBS group layout (D-04c expansion)** — replace the single `_gbs_action_btn` with: status label + **`[Connect with GBS.FM…]`** button (primary, opens the login subprocess) + **`[Disconnect]`** when connected (replaces primary on connect) + **inline `[QLineEdit | Save]` token row** below the primary button. Inline token row is always rendered (no disclosure / no hide-until-research) — accepts the visual asymmetry vs YouTube/Twitch/AA's single-button shape.
- **Status label enumeration** — `_update_status()` reports the saved methods explicitly: `Not connected` / `Connected (cookies)` / `Connected (token)` / `Connected (cookies + token)`. New `_is_gbs_token_saved()` helper alongside `_is_gbs_connected()`.
- **Disconnect semantics** — single confirmation dialog clears **both** cookies and token in one action: "This will delete saved GBS.FM cookies AND clear saved API token. You will need to reconnect..." Matches YouTube/Twitch/AA's single-button disconnect ergonomics. The inline token row's Save button writes the token; clearing is via Disconnect (no per-row Clear button).
- **Token storage in SQLite** — `_repo.set_setting("gbs_api_token", "")` / `get_setting(...)` (mirror AA `audioaddict_listen_key` at `accounts_dialog.py:157`). No new file path. Settings export ZIP (Phase 999.x) picks it up automatically because it round-trips the `settings` table.
- **`musicstreamer/gbs_api.py` auth-context expansion** — `load_auth_context()` grows from returning `MozillaCookieJar | None` to returning a typed `AuthContext` (or `tuple[str | None, MozillaCookieJar | None]`) with `.token` and `.cookies` fields. New internal helper `_open_authed(url, auth, ...)` tries token-auth first (if `auth.token`); on 403 retries once with cookies (if `auth.cookies`); raises `GbsAuthExpiredError` if both fail or both absent. Single retry budget per call — no infinite loops. All public functions (`fetch_active_playlist`, `vote_now_playing`, `search`, `submit`, plus any new ones) accept `AuthContext` and delegate to `_open_authed`. Existing `_open_with_cookies` becomes either the cookies branch of `_open_authed` or stays as a backwards-compat wrapper — planner's call.
- **Auth-vector selection** — researcher re-probes ALL 8 vectors from Phase 60 RESEARCH against `/api/vote`, `/ajax`, `/add/`, `/search` (plus any new vector hinted by the current gbs.fm Settings page documentation). Plan-phase locks the working vector based on findings.
- **`_on_gbs_action_clicked` rewrite** — current shape (open `CookieImportDialog` with `oauth_mode=None`) replaced by: launch `oauth_helper --mode gbs` subprocess (mirror `_launch_oauth_subprocess` for Twitch, including `_oauth_proc: QProcess` lifecycle + Phase 999.3 `OAuthLogger` + category-aware failure dialog with inline Retry). The existing `CookieImportDialog` File + Paste tabs **remain available** as a secondary path — accessed how (separate "Import cookies file…" button? menu item? hidden under disclosure?) is in `<discretion>`.
- **Test extensions** — `tests/test_gbs_api.py` gets fixture-recorded token-auth cases + cookies-fallback-on-403 cases + both-fail-raises-GbsAuthExpiredError. `tests/test_accounts_dialog.py` gets dual-method status string tests (4 status strings × connected combinations), Disconnect-clears-both test, inline token Save flow, login-subprocess launch + finished path. `tests/test_oauth_helper.py` (if exists; otherwise new) gets `--mode gbs` argparse + URL load + cookie-detection-on-sessionid+csrftoken tests. Phase 60 fixture pattern in `tests/fixtures/gbs/` extends with token-auth response recordings (only if re-probe shows token works; otherwise skip).

**Conditional scope (gated on researcher re-probe of API-key auth vectors):**

- **If re-probe confirms the gbs.fm API key NOW authorizes `/api/vote` + `/ajax` + `/add/` + `/search`** (or some functional subset): Phase 76 ships the full dual-auth surface above. Inline token row is functional; storage in SQLite is live; `_open_authed` token-first precedence is wired.
- **If re-probe confirms the API key is STILL 403 on all probed endpoints**: Phase 76 **drops the inline token row entirely** (no paste field, no SQLite key, no `AuthContext.token` field) and ships only the in-app login subprocess + `AccountsDialog` simplification. ROADMAP entry for Phase 76 gets edited via `/gsd-phase edit 76` to drop the "pre-existing API token" half from the phase title and goal. The new phase title becomes something like "GBS.FM authentication: in-app login subprocess (like Google/Twitch)". `AccountsDialog` GBS group reverts to single-button shape (status + `[Connect with GBS.FM…] / [Disconnect]`).

**Out of scope:**

- **Username/password form auth** — Phase 60 D-04 ladder #4 stays rejected. No new pattern, no CSRF/2FA/captcha handling in MusicStreamer.
- **OAuth proper** — gbs.fm has no OAuth endpoints per Phase 60 RESEARCH §Auth Ladder Recommendation. The "login subprocess" here is cookie-harvest, not OAuth.
- **Multi-account / profile switching** — single-user scope per `project_single_user_scope.md`. One token, one cookies file, one gbs.fm identity.
- **Token rotation / refresh** — gbs.fm exposes a `/keygen/` POST endpoint that regenerates the API key. Phase 76 does NOT add a "Regenerate token" button. User regenerates on gbs.fm directly and re-pastes.
- **Removing the existing Paste / File tabs from CookieImportDialog** — those stay. Phase 76 only adds the subprocess path; doesn't take anything away. Existing GBS users with a working `gbs-cookies.txt` are not migrated, not invalidated.
- **Wiring the API token into endpoints outside `gbs_api.py`** — `gbs_search_dialog.py` and the now-playing vote control consume `gbs_api` via its existing public surface; they don't see `AuthContext` directly.
- **Changing `_validate_gbs_cookies`** — the existing validator (sessionid + csrftoken + gbs.fm domain) handles both the manual paste/file flow AND the subprocess output. No new validator needed.

</domain>

<decisions>
## Implementation Decisions

### API-token interpretation + functional verification

- **D-01:** **API-token meaning = the gbs.fm Settings-page API key** (e.g. `a8b3edc60999c5718c9fb953b8250c1d`), the same artifact Phase 60 RESEARCH probed in 2026-05-04. NOT a raw sessionid value, NOT an OAuth bearer, NOT a Twitch-style auth-token. The roadmap entry's "pre-existing API token" matches the gbs.fm-advertised user-page API key.
- **D-02:** **Researcher MUST re-probe the API key against all 8 vectors before plan-phase locks the inline-token-row decision.** Phase 60 RESEARCH (2026-05-04, see `.planning/phases/60-gbs-fm-integration/60-RESEARCH.md` §Auth Ladder Recommendation lines 139, 513, 1282) verified 403 on `?apikey=`, `?api_key=`, `?key=`, `Authorization: Bearer`, `Authorization: Token`, `X-API-Key:`, path-embedded `/api/vote/<key>/<args>`, and body POST `apikey=`. Phase 76 researcher re-runs ALL of these against `/api/vote`, `/ajax`, `/add/`, `/search` plus checks the current gbs.fm Settings page for any new documented vector. Reports verbatim: which vector returns 200, response body shape, whether the response matches what cookies-auth returns.
- **D-03:** **If re-probe confirms 403 on every probed endpoint:** Phase 76 scope collapses to "in-app login subprocess only." Inline token row is removed from the AccountsDialog plan; SQLite key `gbs_api_token` is not introduced; `gbs_api.load_auth_context()` is not expanded (stays cookie-only). ROADMAP entry for Phase 76 gets edited via `/gsd-phase edit 76` to drop the API-token half from title + goal. Plan-phase notes the re-probe results in `76-RESEARCH.md` regardless (audit trail for future re-attempts).
- **D-04:** **If re-probe confirms the API key NOW authorizes one or more of `/api/vote`, `/ajax`, `/add/`, `/search`:** Phase 76 ships the dual-auth surface in full. The working vector becomes a constant in `gbs_api.py` (e.g. `_TOKEN_VECTOR = "X-API-Key"` or `_TOKEN_QUERY_PARAM = "apikey"`); planner picks the most idiomatic vector if multiple work. Test fixtures record both token-auth and cookies-auth response shapes for each endpoint.

### Login subprocess shape

- **D-05:** **`_GbsLoginWindow` mirrors `_TwitchCookieWindow`** (auto-detect, no Done button, 120s deadline, Phase 999.3 event-emission contract). Rejects `_GoogleWindow` shape (manual Done button) because gbs.fm's Django session-cookie completion is observable as a discrete event (both `sessionid` and `csrftoken` appearing on the gbs.fm domain). The Done-button hybrid was considered and rejected (added UX complexity without a real failure mode the auto-detect can't handle within 120s).
- **D-06:** **Trigger condition = BOTH `sessionid` AND `csrftoken` observed on `gbs.fm` / `.gbs.fm` domain.** Domain-matching helper `_cookie_domain_matches_gbs(cookie)` accepts `gbs.fm`, `www.gbs.fm`, `.gbs.fm`, and any `*.gbs.fm` subdomain (mirror `_cookie_domain_matches` at `oauth_helper.py:95-105`). Rejects lookalikes (`fakegbs.fm`, `gbs.fm.evil.com`). The `csrftoken` cookie is set by Django on first page-load (anonymous); the `sessionid` cookie is set only on successful authentication — so waiting for BOTH ensures the user actually completed login before the subprocess flushes.
- **D-07:** **Output format = full Netscape dump of all gbs.fm-domain cookies on success** (mirror `_GoogleWindow._flush_cookies`: `lines = ["# Netscape HTTP Cookie File"]` + one line per cookie via `_cookie_to_netscape(cookie)`). Includes the two trigger cookies (`sessionid`, `csrftoken`) PLUS any auxiliary cookies gbs.fm sets (e.g. `messages`, future CSRF rotation). Forward-compat with site changes; matches the shape `_validate_gbs_cookies` already validates; matches the shape `gbs-cookies.txt` paste/file imports already produce.
- **D-08:** **Login URL = `https://gbs.fm/accounts/login/`** (canonical login page, identified by Phase 60 RESEARCH as the auth-expired redirect target — see `gbs_api.py:158-159` and `GbsAuthExpiredError`). Constant `_GBS_LOGIN_URL = "https://gbs.fm/accounts/login/"` next to `_TWITCH_LOGIN_URL` in `oauth_helper.py`. Researcher confirms the URL still resolves to a login form at plan-phase time (defensive check; not blocking).
- **D-09:** **Failure / timeout reuses Phase 999.3 contract.** `_GbsLoginWindow._emit_event` emits the same `{"category": ..., "detail": ..., "provider": "gbs"}` JSON-line shape as `_TwitchCookieWindow`. Categories: `Success`, `LoginTimeout` (120s), `WindowClosedBeforeLogin`, `InvalidTokenResponse` (cookie decode failure / empty value), `SubprocessCrash`. `provider` field changes from `"twitch"` to `"gbs"` — `accounts_dialog._CATEGORY_LABELS` is provider-agnostic so it works as-is. `OAuthLogger` (Phase 999.3 D-11) appends to the same `paths.oauth_log_path()` — log is multi-provider already.
- **D-10:** **WebEngine profile config = mirror `_TwitchCookieWindow`.** `profile.setPersistentCookiesPolicy(NoPersistentCookies)` so the subprocess's own profile never persists state across runs. UA override via Chromium `--user-agent` flag at module-import time + `profile.setHttpUserAgent(_CHROME_UA)` belt-and-braces. The actual cookie value MusicStreamer writes to `gbs-cookies.txt` is independent of the WebEngine profile's persistence policy — `cookieAdded` fires regardless.

### AccountsDialog GBS group layout

- **D-11:** **GBS group expands to: status label + `[Connect with GBS.FM…]` button + inline `[QLineEdit | Save]` token row.** Connected state replaces `[Connect with GBS.FM…]` with `[Disconnect]`. Inline token row is always rendered (not disclosed, not hidden behind a feature flag, not deferred-until-research). If D-03 fires (re-probe still 403), the inline token row is REMOVED from the plan entirely — not "hidden" or "feature-flagged off"; just not built.
- **D-12:** **Inline token row sits inside the same `QGroupBox` as the primary button, below it.** Single horizontal `QHBoxLayout` with `QLabel("API token:")` + `QLineEdit` (echoMode=Normal — token is not a password per gbs.fm convention; researcher confirms if echoMode should be `Password` instead) + `QPushButton("Save")`. On Save: validate non-empty, `_repo.set_setting("gbs_api_token", text)`, call `_update_status()`, clear the QLineEdit, toast `"GBS.FM API token saved."` Mirrors `accounts_dialog._on_aa_clear_clicked` confirmation-then-update pattern (Phase 48 D-06), inverted to write-instead-of-clear.
- **D-13:** **Asymmetry with YouTube/Twitch/AA is accepted.** Each of those groups has status + 1 button. GBS has status + 1-2 buttons + (conditionally) 1 inline row. The asymmetry is intentional — GBS legitimately has two functional auth paths once Phase 76 ships. No symmetry-for-symmetry's-sake refactor of the other groups.
- **D-14:** **Existing `CookieImportDialog` File + Paste tabs remain reachable.** Phase 76 does NOT delete or hide them. How they're reached after the GBS group's primary button changes meaning (from "Import cookies" to "Connect with GBS.FM…") is in `<discretion>` — options include a secondary `[Import cookies file…]` button beneath the primary, a hamburger-menu entry, or context-menu access. Default recommendation: secondary button if vertical density allows.

### Status label enumeration

- **D-15:** **Status label enumerates saved methods.** Four states:
  - `Not connected` — neither cookies nor token saved.
  - `Connected (cookies)` — cookies file exists, no token.
  - `Connected (token)` — token saved in SQLite, no cookies file.
  - `Connected (cookies + token)` — both saved.

  `_update_status()` calls a new `_gbs_methods()` helper returning a list (`["cookies"]`, `["token"]`, `["cookies", "token"]`, or `[]`) and joins them: `f"Connected ({' + '.join(methods)})" if methods else "Not connected"`. Token text in the label is intentional — the user wants to see which auth surface is live (matches user choice on the status enumeration question).
- **D-16:** **`_is_gbs_token_saved()` predicate added** alongside `_is_gbs_connected()` at `accounts_dialog.py:173-175`. Returns `bool(self._repo.get_setting("gbs_api_token", ""))` — mirrors `_is_aa_key_saved()` at `accounts_dialog.py:169-171`. Functions are independent — `_is_gbs_connected()` keeps its file-existence semantics.

### Disconnect semantics

- **D-17:** **Single Disconnect clears both cookies and token in one action.** Confirmation: `"This will delete your saved GBS.FM cookies AND clear your saved API token. You will need to reconnect to vote, view the active playlist, or submit songs."` On Yes: `os.remove(paths.gbs_cookies_path())` (with the broader `OSError` tolerance Phase 60 HIGH 2 fix established at `accounts_dialog.py:312-316`) + `self._repo.set_setting("gbs_api_token", "")`. Then `_update_status()`.
- **D-18:** **No per-row Clear button on the inline token row.** Clear happens via Disconnect. Inline row's Save button is the only token action in connected state — it overwrites the saved token if the user pastes a new one. Avoids button proliferation in the GroupBox.

### Token storage + auth precedence

- **D-19:** **API token storage = `_repo.set_setting("gbs_api_token", "")` in the existing SQLite `settings` table.** No new file path, no new helper in `paths.py`. Mirrors AA `audioaddict_listen_key` exactly (Phase 48 D-04 / `accounts_dialog.py:157`). Settings export ZIP (Phase 999.x) round-trips the entire `settings` table, so token survives backup/restore automatically.
- **D-20:** **`gbs_api.load_auth_context()` grows to return a typed `AuthContext`** (named tuple or `@dataclass(frozen=True)` — planner's call) with two fields: `.token: str | None` and `.cookies: http.cookiejar.MozillaCookieJar | None`. Callable from any context with access to the `Repo` (subset of call sites may need a `repo` param threaded through). If neither field is set, callers raise / surface "not connected" toast at their call site (existing pattern). Backwards compat: if returning bare `MozillaCookieJar` is preserved as a legacy alias, tests check both paths.
- **D-21:** **Auth precedence = token first, cookies fallback on 403.** New helper `_open_authed(url, auth, write=False)` in `gbs_api.py`:
  1. If `auth.token` is set: try request with token-auth (vector locked by D-04 researcher finding).
  2. On 403 response: if `auth.cookies` is also set, retry once with cookies (`_open_with_cookies` shape). Otherwise raise `GbsAuthExpiredError`.
  3. Single retry budget per call. No infinite loops on rotating 403s.
  4. If both unset: raise `GbsAuthExpiredError("no auth context — saved cookies/token cleared")`.
- **D-22:** **Auth vector for token = researcher-locked.** D-04 researcher reports the working vector from re-probing all 8 from Phase 60. Planner exposes it as a single module-level constant in `gbs_api.py` (e.g. `_TOKEN_HEADER = "X-API-Key"` or `_TOKEN_QUERY_PARAM = "apikey"`). Header-style vectors go in `Request.headers`; query-string vectors get appended via `urllib.parse.urlencode` before opener.open. Path-embedded vectors (`/api/vote/<key>/<args>`) would need per-endpoint URL construction — researcher flags if this is the only working vector so planner widens the helper.
- **D-23:** **Endpoint-by-endpoint test matrix.** Each `gbs_api.py` public function (`fetch_active_playlist`, `vote_now_playing`, `search`, `submit`) gets THREE fixture-backed test cases under the conditional scope of D-04: (a) token-auth success path returns expected payload; (b) token returns 403 → cookies fallback succeeds → returns expected payload; (c) both fail → `GbsAuthExpiredError` raised. If D-03 fires, only path (b)-without-token (= existing cookies path) survives — token cases not added.

### Tests

- **D-24:** **Phase 60 fixture-based testing pattern extends.** `tests/fixtures/gbs/` already has cookie-auth response recordings (Phase 60 D-03). Add token-auth recordings if D-04 fires positively. Recording method: same `urllib.request.urlopen` + `with open(fixture_path, "w") as f: f.write(response.read().decode())` shape Phase 60 used. Each fixture file is committed; tests load with `open(fixture_path).read()` and assert response equality.
- **D-25:** **`tests/test_accounts_dialog.py` gets:**
  - 4 status-string tests (one per `_gbs_methods()` output state).
  - Inline token Save flow test (paste → click Save → `_repo.set_setting` called → `_update_status` fires → toast fires → QLineEdit cleared).
  - Disconnect-clears-both test (cookies file + token setting both present → Yes → both gone, status `Not connected`).
  - Login subprocess launch test (`_on_gbs_action_clicked` not-connected branch → `QProcess.start` called with `sys.executable -m musicstreamer.oauth_helper --mode gbs`).
  - Login subprocess finished test (mirror `_on_oauth_finished` shape — exit 0 + valid Netscape stdout writes file + 0o600 perms + `_update_status` fires).
  - Phase 999.3 category-dialog test for gbs failure paths (LoginTimeout / WindowClosedBeforeLogin / etc.) — likely parameterized over the Twitch test cases.
- **D-26:** **`tests/test_oauth_helper.py` gets `--mode gbs` tests** (or new file if Twitch tests live in test_accounts_dialog instead): argparse accepts `gbs`; `_GbsLoginWindow.__init__` loads `_GBS_LOGIN_URL`; `_on_cookie_added` triggers on `sessionid` + `csrftoken` on `.gbs.fm` and NOT on lookalike domains; 120s timeout fires; flush produces valid Netscape format that `_validate_gbs_cookies` accepts.

### Claude's Discretion

- **Where the existing File/Paste tabs are reached** after `[Connect with GBS.FM…]` repurposes the primary button. Default recommendation: secondary `[Import cookies file…]` button below the primary, only visible in not-connected state (becomes redundant once connected). Alternative: drop the File/Paste tabs entirely if the subprocess covers all common cases (the dev-fixture path becomes the only paste-from-disk surface, accessed only by researchers). Planner picks.
- **`AuthContext` shape** — named tuple vs `@dataclass(frozen=True)` vs plain `tuple[str | None, MozillaCookieJar | None]`. Recommendation: `@dataclass(frozen=True)` for explicit field names + immutability + serialization clarity in tests.
- **`echoMode` on the inline token `QLineEdit`** — normal echo vs `QLineEdit.EchoMode.Password`. If the token is treated like a credential, Password mode + a small "show/hide" eye toggle is the safe default. Researcher confirms from the gbs.fm Settings page UX (do they treat it as visible / hidden?).
- **Toast wording** — `"GBS.FM API token saved."` / `"GBS.FM logged in."` / `"GBS.FM disconnected."` Planner can adjust.
- **Whether `_open_with_cookies` survives as a public helper** or becomes the cookies-only branch of `_open_authed` (eliminated by inlining). Recommendation: keep `_open_with_cookies` as the cookies branch (minimal diff, eight existing call sites stay) and add `_open_authed` as the new entry point for endpoints that participate in the token-first precedence.
- **Whether `import_station` (Phase 60 D-03) gets the same token-first treatment.** The import path uses unauthenticated metadata fetches today (the streams + station-metadata endpoints are public). If researcher confirms those endpoints accept the token without changes, no plumbing required. If they don't, `import_station` stays cookie-less.
- **Inline token row label** — `"API token:"` vs `"GBS.FM API token:"` vs no label (placeholder text in QLineEdit instead). Default: short `"API token:"` since context (the GBS GroupBox) already implies the provider.
- **Whether to add a "Refresh status" / "Test connection" button.** Recommendation: NO. Status reflects on-disk + DB state; "test" would require a live request to gbs.fm which adds another failure mode in the dialog. Existing behavior (status updates on dialog open + after Connect/Disconnect/Save) is sufficient.
- **Module constant naming** in `gbs_api.py` for the token vector. Recommendation: name reflects the form — `_TOKEN_HEADER = "X-API-Key"` if header-based; `_TOKEN_QUERY_PARAM = "apikey"` if query-string-based; comment cross-references Phase 76 RESEARCH §Re-probe Results.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements

- `.planning/ROADMAP.md` §"Phase 76: GBS.FM authentication: support both pre-existing API token and login-page cookie capture (like Google/Twitch)" — phase title and goal. **Note:** if D-03 fires (re-probe still 403), the planner MUST run `/gsd-phase edit 76` to drop the "pre-existing API token" half from the title and goal before plan-phase completes.
- `.planning/PROJECT.md` §Constraints — single-user scope; no multi-account.
- `.planning/REQUIREMENTS.md` — no Phase 76 requirement entry yet; planner adds one (e.g. `GBS-AUTH-01: User can log in to GBS.FM via in-app subprocess` + conditionally `GBS-AUTH-02: User can paste a pre-existing API token from gbs.fm Settings page`).

### CRITICAL prior research (READ FIRST)

- **`.planning/phases/60-gbs-fm-integration/60-RESEARCH.md` §Auth Ladder Recommendation, §Capability 4 (lines 139, 513, 1282)** — Phase 60 RESEARCH verified the gbs.fm Settings-page API key returns 403 on `/api/vote`, `/ajax`, `/add/`, `/search` across 8+ auth vectors (2026-05-04). Only `/next/<authid>` admin-skip accepted it. Phase 76 researcher MUST cite this report verbatim and explain what re-probing finds (still 403 → D-03; now 200 → D-04). Documents the EXACT 8 vectors probed: `?apikey=`, `?api_key=`, `?key=`, `Authorization: Bearer`, `Authorization: Token`, `X-API-Key:`, path-embedded `/api/vote/<key>/<args>`, body POST `apikey=`.
- `.planning/phases/60-gbs-fm-integration/60-CONTEXT.md` §D-04 (lines 89-103) — the ladder framing (#1 API key paste / #2 OAuth / #3 cookies-import / #4 username-password) Phase 60 locked at ladder #3. Phase 76 attempts to add ladder #1 contingent on D-02 re-probe and re-adds ladder #2-shape via the subprocess (cookie-harvest, not OAuth proper).
- `.planning/phases/60-gbs-fm-integration/60-RESEARCH.md` §Capability 4 — full URL pattern listing extracted from `https://gbs.fm/api/` DEBUG 404 page. Identifies `/next/<authid>` as the only endpoint accepting the API key, and `/keygen/` POST as the regenerate endpoint (out of scope per Phase 76 D-21).
- `.planning/phases/60-gbs-fm-integration/60-RESEARCH.md` line 15 — verified expiry: dev fixture sessionid expires 2026-05-17 (TWO DAYS after today, 2026-05-15), csrftoken 2026-10-30. Researcher MUST re-prompt user to drop fresh cookies at `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt` before re-probing.

### Closest existing patterns (READ FIRST — Phase 76 mirrors these)

- **`musicstreamer/oauth_helper.py:108-192` — `_TwitchCookieWindow`** — the EXACT shape `_GbsLoginWindow` mirrors. Auto-detect on `auth-token` cookie observed for `.twitch.tv`; no Done button; 120s timeout; `_emit_event` structured JSON-line shape; `closeEvent` handling. Phase 76 changes the trigger cookie set (sessionid+csrftoken instead of auth-token), the domain (gbs.fm instead of twitch.tv), and the output format (full Netscape dump instead of raw token).
- **`musicstreamer/oauth_helper.py:215-269` — `_GoogleWindow._flush_cookies`** — the Netscape-output shape. `lines = ["# Netscape HTTP Cookie File"]` + one `_cookie_to_netscape(cookie)` line per cookie. Phase 76's `_GbsLoginWindow` borrows this exact format.
- **`musicstreamer/oauth_helper.py:95-105` — `_cookie_domain_matches`** — domain-validation pattern. Phase 76 adds `_cookie_domain_matches_gbs` with the same shape.
- **`musicstreamer/oauth_helper.py:276-299` — `main()`** — argparse `choices=["twitch", "google"]` extends to `["twitch", "google", "gbs"]`. The `if args.mode == ...` branch adds a third arm.
- **`musicstreamer/ui_qt/accounts_dialog.py:104-115` — current GBS group construction** — the QGroupBox + QLabel + QPushButton shape Phase 76 expands.
- **`musicstreamer/ui_qt/accounts_dialog.py:117-128` — Twitch group + `_status_label` + `_action_btn` pair** — pattern Phase 76's expanded `[Connect with GBS.FM…] / [Disconnect]` primary button mirrors.
- **`musicstreamer/ui_qt/accounts_dialog.py:131-141` — AudioAddict group with `_aa_status_label` + `_aa_clear_btn`** — the closest precedent for the inline token row (AA stores a key in SQLite; GBS will mirror the storage + provide a Save inline instead of Clear).
- **`musicstreamer/ui_qt/accounts_dialog.py:165-175` — `_is_youtube_connected`, `_is_aa_key_saved`, `_is_gbs_connected`** — predicate naming + body shape Phase 76's new `_is_gbs_token_saved()` mirrors.
- **`musicstreamer/ui_qt/accounts_dialog.py:177-214` — `_update_status()`** — the status-label-update flow Phase 76 extends with the four-state GBS enumeration.
- **`musicstreamer/ui_qt/accounts_dialog.py:298-330` — current `_on_gbs_action_clicked`** — the Connect/Disconnect handler shape. Phase 76 rewrites this: connect branch launches `oauth_helper --mode gbs` subprocess (mirror `_launch_oauth_subprocess` at `accounts_dialog.py:332-341`); disconnect branch widens to clear BOTH cookies file AND token SQLite key.
- **`musicstreamer/ui_qt/accounts_dialog.py:243-259` — `_on_action_clicked` (Twitch) + `_launch_oauth_subprocess`** — exact subprocess-launch pattern Phase 76 reuses for GBS (different `--mode` arg).
- **`musicstreamer/ui_qt/accounts_dialog.py:332-341` — `_launch_oauth_subprocess`** — `QProcess(self)`, `finished.connect(self._on_oauth_finished)`, `start(sys.executable, ["-m", "musicstreamer.oauth_helper", "--mode", "twitch"])`. Phase 76 adds a sibling `_launch_gbs_login_subprocess` OR parameterizes `_launch_oauth_subprocess` by mode (planner's call — see `<discretion>`).
- **`musicstreamer/ui_qt/accounts_dialog.py:46-51` — `_CATEGORY_LABELS`** — Phase 999.3 categories. Provider-agnostic; Phase 76 GBS uses the same labels (LoginTimeout, WindowClosedBeforeLogin, etc.).
- **`musicstreamer/ui_qt/accounts_dialog.py:220-237` — `_get_oauth_logger`** — Phase 999.3 lazy-init logger. Phase 76 reuses the same logger across all providers.

### Closest existing patterns — gbs_api.py expansion

- **`musicstreamer/gbs_api.py:92-113` — current `load_auth_context()`** — returns `MozillaCookieJar | None`. Phase 76 changes to return `AuthContext` (dataclass with `.token` and `.cookies` fields).
- **`musicstreamer/gbs_api.py:146-160` — `_open_with_cookies`** — the cookies-auth call helper. Phase 76 either: (a) keeps it and adds `_open_authed(url, auth)` that calls `_open_with_cookies` as its cookies branch; or (b) inlines + replaces with `_open_authed`. Recommendation: (a) — minimal diff, eight existing call sites stay.
- **`musicstreamer/gbs_api.py:82-87` — `GbsApiError` + `GbsAuthExpiredError`** — typed exceptions. Phase 76 may add `GbsTokenRejectedError` (subclass of `GbsAuthExpiredError`?) for the token-403 path before cookies retry. Default: reuse `GbsAuthExpiredError` for the "both failed" case; the "token failed, retrying with cookies" case is internal to `_open_authed` and doesn't raise.

### Existing surface that stays

- **`musicstreamer/ui_qt/cookie_import_dialog.py`** — Phase 60 D-04 ladder #3 dialog. Phase 76 keeps it accessible (D-14) — either via a secondary button in the GBS group or via menu access. The dialog itself is unchanged.
- **`musicstreamer/gbs_api.py:116-141` — `_validate_gbs_cookies`** — already accepts the Netscape dump shape `_GbsLoginWindow` will produce. No changes needed.
- **`musicstreamer/cookie_utils.py:temp_cookies_copy` + `is_cookie_file_corrupted`** — Phase 999.7 hardening for the cookies file. Continues to apply to the subprocess output exactly as it does to file/paste output.

### Dev fixture (out of repo AND out of OneDrive sync)

- `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt` — Kyle's session cookies (Netscape format). Phase 60 RESEARCH uses this. **Phase 76 researcher: the Phase 60 fixture's sessionid expires 2026-05-17 — TWO days from today. Prompt the user to refresh the fixture before re-probing.** Never commit — `.local/` is in the project `.gitignore`.

### Paths convention

- **`musicstreamer/paths.py:54-60` — `gbs_cookies_path()`** — Phase 60 D-04 LOCKED path. Phase 76 does NOT add a new `gbs_token_path()` because token lives in SQLite (D-19), not on disk.
- `musicstreamer/paths.py:50-51` — `twitch_token_path()` — kept for symmetry comparison only; not extended.

### Project conventions (apply during planning)

- **Bound-method signal connections, no self-capturing lambdas (QA-05)** — all new QPushButton clicked / QLineEdit returnPressed connections.
- **`Qt.TextFormat.PlainText` (T-40-04)** — applies to the new status label format and any QLabel additions.
- **snake_case + type hints throughout, no formatter** — per `.planning/codebase/CONVENTIONS.md`.
- **Pure `urllib`, no SDK for HTTP clients** — `gbs_api.py` token-auth retry path uses `urllib.request.Request` with custom headers.
- **10s timeout per HTTP read; 15s for writes** — existing `_TIMEOUT_READ` / `_TIMEOUT_WRITE` in `gbs_api.py:74-75`.
- **0o600 file mode for sensitive data** — the cookies file written from subprocess output gets `os.chmod(0o600)` (existing `CookieImportDialog._write_cookies` pattern at `cookie_import_dialog.py:333-342`).
- **Token NOT logged** — `oauth_helper._emit_event` doc-comment warns "NEVER pass token values, cookie values, or URL fragments as `detail`" (`oauth_helper.py:75-77`). Applies verbatim to Phase 76's GBS branch.
- **Single-user scope** — per project memory `project_single_user_scope.md`. One token, one cookies file, one identity.
- **Linux Wayland DPR=1.0 deployment target** — per memory `project_deployment_target.md`. Visual audits downgrade HiDPI/Retina/X11 findings.

### Cross-AI / external

- **GBS.FM Settings page** (`https://gbs.fm/settings/` — requires login) — researcher reads it to extract the documented auth-vector recommendation (D-22) and to confirm whether the API key is visible / hidden / regenerable. Researcher visits with the dev fixture cookies.
- **GBS.FM `/api/` DEBUG 404 page** (`https://gbs.fm/api/`) — Phase 60 RESEARCH captured the full Django URLconf. Re-fetch to confirm URL patterns haven't shifted (Phase 60 noted "operator NOT actively maintaining/refactoring" — but verify).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`oauth_helper._TwitchCookieWindow`** — entire class shape (auto-detect cookie + 120s timeout + event emission + close handling) cloneable for `_GbsLoginWindow` with three substitutions: login URL, trigger cookies, output format.
- **`oauth_helper._GoogleWindow._flush_cookies`** — Netscape-dump output shape. Direct lift into `_GbsLoginWindow._flush_cookies`.
- **`oauth_helper._cookie_domain_matches`** — domain validation pattern; cloneable as `_cookie_domain_matches_gbs`.
- **`oauth_helper._cookie_to_netscape`** — per-cookie Netscape serialization. Shared utility; used as-is by `_GbsLoginWindow`.
- **`AccountsDialog._launch_oauth_subprocess`** — `QProcess.start(sys.executable, ["-m", "musicstreamer.oauth_helper", "--mode", "twitch"])` shape. Phase 76 either clones (recommended, mirrors Twitch's single-helper pattern) or parameterizes by mode.
- **`AccountsDialog._on_oauth_finished`** (not shown in excerpt but implied by `finished.connect`) — subprocess-finished handler that reads stdout for the auth artifact. Phase 76 mirrors with a `_on_gbs_login_finished` that reads the Netscape cookies dump from stdout, validates via `_validate_gbs_cookies`, writes to `gbs_cookies_path()` with 0o600 perms.
- **`AccountsDialog._aa_status_label` + `_aa_clear_btn` shape** — closest precedent for the inline-token row's storage + status reflection.
- **`AccountsDialog._update_status` AA branch (lines ~207-214)** — `_is_aa_key_saved()` predicate + Saved/Not saved label + Clear-vs-No-key-saved button text. Mirror for `_is_gbs_token_saved()` flavor (though Phase 76 uses a different button shape — inline Save instead of standalone Clear).
- **`Repo.set_setting / get_setting`** — SQLite settings table accessor. AA listen_key uses this; GBS API token mirrors.
- **`CookieImportDialog._write_cookies`** (`cookie_import_dialog.py:333-342`) — Netscape-text-to-`gbs_cookies_path()` writer with 0o600 chmod. Phase 76's `_on_gbs_login_finished` reuses this exact pattern (or shares it via refactor — planner's call; minimal-diff path is to inline).
- **Phase 999.3 `OAuthLogger` + `_CATEGORY_LABELS` + category-aware failure dialog** — entire failure UI plumbing reused for GBS branch with no changes (provider-agnostic by design).

### Established Patterns

- **Subprocess-isolated WebEngineView via `oauth_helper.py`** — avoids 130MB QtWebEngine in main process startup. Established by Phase 32 (Twitch) and Phase 22 (YouTube). Phase 76 adds a third client; pattern carries.
- **Auto-detect-on-cookie vs. user-Done-button** — Phase 999.3 settled this: auto-detect is preferred when the trigger is deterministic (Twitch's `auth-token`). Phase 76 inherits — Django's `sessionid` + `csrftoken` is similarly deterministic.
- **Phase 999.3 structured JSON-line stderr from oauth_helper** — every new mode emits the same event shape; AccountsDialog ingests provider-agnostic.
- **SQLite settings table for tokens/keys** — AA listen_key (Phase 48) precedent. Phase 76's `gbs_api_token` mirrors.
- **0o600 file mode for any cookies/token on disk** — Phase 999.7 invariant. Applies to the subprocess output written to `gbs_cookies_path()`.
- **Phase 60 D-04c group placement** — `_gbs_box` sits between `_youtube_box` and Twitch in `AccountsDialog.layout`. Phase 76 keeps that ordering unchanged.
- **Multi-method auth precedence** — new pattern introduced by Phase 76 (no project precedent). `AuthContext` + `_open_authed` is the canonical shape; other future multi-method providers (if any) inherit.

### Integration Points

- **`musicstreamer/oauth_helper.py:276-299` — `main()` argparse** — extend `choices=["twitch", "google"]` to include `"gbs"`; add the `if args.mode == "gbs": window = _GbsLoginWindow()` arm.
- **`musicstreamer/oauth_helper.py` — new `_GBS_LOGIN_URL` constant + new `_GbsLoginWindow` class** — sandwiched between `_TwitchCookieWindow` and `_GoogleWindow` definitions (alphabetical by provider would put it first; mirror existing ordering instead).
- **`musicstreamer/ui_qt/accounts_dialog.py:104-115` — GBS group construction** — expand to include inline token row (`QHBoxLayout` with `QLabel("API token:") + QLineEdit + QPushButton("Save")` inside the `_gbs_box`).
- **`musicstreamer/ui_qt/accounts_dialog.py:173-175` — new `_is_gbs_token_saved()` predicate** — mirror `_is_aa_key_saved()`.
- **`musicstreamer/ui_qt/accounts_dialog.py:186-192` — GBS status update branch** — replace with 4-state enumeration using new `_gbs_methods()` helper.
- **`musicstreamer/ui_qt/accounts_dialog.py:298-330` — `_on_gbs_action_clicked` rewrite** — connect branch launches subprocess instead of opening `CookieImportDialog`; disconnect branch clears both cookies file AND token.
- **New `AccountsDialog._on_gbs_token_save_clicked`** — inline token Save handler. Validates non-empty, calls `_repo.set_setting("gbs_api_token", text)`, fires `_update_status`, clears QLineEdit, toasts.
- **New `AccountsDialog._launch_gbs_login_subprocess`** — sibling of `_launch_oauth_subprocess(twitch)`. Either clone the Twitch method with a `--mode gbs` arg, or parameterize the existing method by mode.
- **New `AccountsDialog._on_gbs_login_finished`** — sibling of `_on_oauth_finished`. Reads Netscape stdout, validates via `_validate_gbs_cookies`, writes to `paths.gbs_cookies_path()` with 0o600, updates status, toasts.
- **`musicstreamer/gbs_api.py:92-113` — `load_auth_context()` signature change** — return type widens from `MozillaCookieJar | None` to `AuthContext`. Existing eight call sites get a thin update (likely just unpacking).
- **`musicstreamer/gbs_api.py:146-160` — new `_open_authed` helper** — wraps `_open_with_cookies` with token-auth-first fallback semantics.
- **No new `paths.py` helpers** — token lives in SQLite (D-19).
- **No schema changes** — `settings` table reused.

</code_context>

<specifics>
## Specific Ideas

- **"Like Google/Twitch"** in the roadmap title refers to the in-app subprocess WebView pattern (`_GoogleWindow` / `_TwitchCookieWindow`), not the cookies-import dialog. Phase 76 is the third such window — `_GbsLoginWindow`. The user wants gbs.fm login to feel as native as the existing two providers.
- **The roadmap title's "support both" framing is conditional on Phase 60 RESEARCH's API-key 403 finding being out of date.** This was the gating question in discussion. The user wants the researcher to RE-VERIFY before locking the paste-field decision — not skip ladder #1 outright, not ship a dead field. The roadmap entry edit (via `/gsd-phase edit 76`) is the user-approved fallback if research still confirms 403.
- **"Connected (cookies + token)"** status-label enumeration was the user's explicit preference over "Connected" alone or two-line stacked status — they want the dialog to surface WHICH method is live.
- **Inline single-line token row, not a separate modal** — closer to AA's inline pattern (key entered in ImportDialog when fetching channels) than to Twitch's modal-style subprocess launch. Adds vertical density to the GBS group but keeps the click count low.
- **Disconnect = "remove both" in one click** — user explicitly preferred single-button symmetry with YouTube/Twitch/AA over per-row Clear buttons. Confirmation dialog wording must enumerate "cookies AND token" so the user knows what's being cleared.
- **Token-first auth precedence with cookies fallback on 403** — user picked this over cookies-primary or user-radio. The token is preferred because (per the user's framing) it's portable and survives session expiry; cookies are the safety net for endpoints the token can't reach.
- **`_open_authed(url, auth)` is the right level for the precedence logic** — user chose "expand `load_auth_context()` to return both + each endpoint delegates" over per-endpoint explicit pick (less DRY) or parallel-fire (wasteful). Implications: every call site needs the `AuthContext` passed in (planner threads `repo` through), and the 403→retry-once budget is centralized in one helper.
- **Researcher re-probes ALL 8 vectors, not just X-API-Key** — user wants comprehensive coverage. The "default to X-API-Key" option was rejected to avoid missing a working vector the gbs.fm site might document elsewhere.
- **Phase 999.3 failure UI is provider-agnostic and gets reused with zero changes** — the user-facing failure dialog with category-aware copy + inline Retry already handles whatever `--mode gbs` emits, because `_CATEGORY_LABELS` is keyed on the category, not the provider. Less work for Phase 76; verifies a Phase 999.3 invariant.
- **Existing GBS users with a working `gbs-cookies.txt` are not migrated, not invalidated, not asked to re-auth.** The new login subprocess is purely additive — they keep playing voting/etc. as before.

</specifics>

<deferred>
## Deferred Ideas

### Future phases (if needs surface)

- **"Regenerate token" button** in the GBS group, calling `/keygen/` POST. User explicitly out of scope per D-21 — they regenerate on gbs.fm directly. Revisit if token rotation becomes a frequent flow.
- **"Show/hide token" eye toggle** on the inline token QLineEdit (if echoMode is Password by default). Phase 76 picks one default; toggle is a future polish if the choice turns out wrong.
- **Per-endpoint auth-method override** — e.g. user setting "force cookies for vote, token for everything else" because a specific endpoint authorizes inconsistently. Adds UI knobs that aren't justified yet.
- **Multi-account / profile switching** for GBS.FM. Single-user scope keeps this out indefinitely.
- **OAuth proper** if gbs.fm ever adds OAuth endpoints. Phase 76's `_GbsLoginWindow` is cookie-harvest only.
- **Token caching with TTL** — currently the token is read on every `load_auth_context()` call. If profiling shows DB hit cost, an in-memory cache is a future optimization.
- **`AuthContext` extracted to a shared module** for other providers if any future provider adopts multi-method auth. Phase 76 keeps it inside `gbs_api.py`.

### Scope boundary edges to revisit if user feedback says otherwise

- **Removing the existing Paste / File tabs from `CookieImportDialog`** entirely (cleanup) once the subprocess covers all cases. Phase 76 keeps them. Revisit after a milestone of use if no one needs them.
- **`AccountsDialog` symmetry refactor** — Phase 76 accepts asymmetry. If three sibling groups end up needing dual-method, normalize the layout pattern then.
- **Token migration / detection** — Phase 76 doesn't try to detect users who already have an API key saved somewhere. If a future phase wants to auto-import, it's net new.

</deferred>

---

*Phase: 76-gbs-fm-authentication-support-both-pre-existing-api-token-an*
*Context gathered: 2026-05-15*
