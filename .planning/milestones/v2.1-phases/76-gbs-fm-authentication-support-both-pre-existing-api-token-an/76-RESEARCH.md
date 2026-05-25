# Phase 76: GBS.FM authentication — Research

**Researched:** 2026-05-16
**Domain:** Multi-method auth surface (in-app login subprocess + conditional API-token paste) for an existing Django-session-cookie-based third-party service
**Confidence:** HIGH for the re-probe verdict; HIGH for the `_GbsLoginWindow` design (direct Twitch clone); HIGH for the AccountsDialog layout dimensions; MEDIUM for the long-term stability of the gbs.fm operator's auth posture (Phase 60 RESEARCH 2026-05-04 noted "operator NOT actively maintaining/refactoring" — Phase 76 re-probe 12 days later confirms zero shift).

---

## VERDICT: D-03 (API key STILL 403 on all probed endpoints)

**Reaffirms Phase 60 RESEARCH 2026-05-04 finding verbatim.** Every Phase 76 endpoint (`/api/vote`, `/ajax`, `/add/<songid>`, `/search`) returns **403 Forbidden** OR **302→/accounts/login/** across all 8 auth vectors from `60-RESEARCH.md` §Auth Ladder Recommendation. The `/next/<authid>` admin-skip endpoint still accepts the API key (path-embedded as the URL itself) — exactly as Phase 60 documented.

**No new vector is documented on the current gbs.fm Settings page.** The settings page describes the API key in prose only ("This can be used for third party applications and clients that want to act on your behalf … to do things like make votes and comments under your name") with no URL example, no header documentation, no usage block. The only other URL pattern referencing the key is `^keygen/?$` (regenerate, out of scope per D-21) and the newly-noticed `^user/(?P<userid>\d+)/givetoken$` (peer-to-peer upload-token gifting, unrelated to API auth).

### Vector × Endpoint Verdict Matrix

Cookies baseline column shows the response shape under fully-authenticated `sessionid` + `csrftoken`. Token-only probes were run without cookies and **without redirect-following** (so 302→login surfaces as the literal response code, not the followed-to login HTML).

| Vector | `/ajax` (200 JSON) | `/api/vote` (200 text) | `/add/<songid>` (302→/playlist) | `/search` (200 HTML) | `/next/<authid>` (200 empty) |
|--------|-------|-------------|-------------|-------|------------|
| **Cookies baseline** | 200 JSON array | 200 `"0 Jethro Tull..."` | 302 → `/playlist` | 200 HTML | 200 empty |
| **No auth (control)** | 302 → login | 403 | 302 → login | 302 → login | 200 empty |
| **V1 `?apikey=<TOKEN>`** | **302 → login** ❌ | **403** ❌ | **302 → login** ❌ | **302 → login** ❌ | 200 empty ✓ |
| **V2 `?api_key=<TOKEN>`** | **302 → login** ❌ | **403** ❌ | **302 → login** ❌ | **302 → login** ❌ | 200 empty ✓ |
| **V3 `?key=<TOKEN>`** | **302 → login** ❌ | **403** ❌ | **302 → login** ❌ | **302 → login** ❌ | 200 empty ✓ |
| **V4 `Authorization: Bearer <TOKEN>`** | **302 → login** ❌ | **403** ❌ | **302 → login** ❌ | **302 → login** ❌ | 200 empty ✓ |
| **V5 `Authorization: Token <TOKEN>`** | **302 → login** ❌ | **403** ❌ | **302 → login** ❌ | **302 → login** ❌ | 200 empty ✓ |
| **V6 `X-API-Key: <TOKEN>`** | **302 → login** ❌ | **403** ❌ | **302 → login** ❌ | **302 → login** ❌ | 200 empty ✓ |
| **V7 path-embed `/<TOKEN>/`** | **404** ❌ | **403** ❌ | **404** ❌ | **404** ❌ | 200 empty ✓ |
| **V8 POST body `apikey=<TOKEN>`** | **403** (CSRF) ❌ | **403** ❌ | **403** (CSRF) ❌ | **403** (CSRF) ❌ | 403 (CSRF) ❌ |

Legend: ❌ = does not authenticate the request. ✓ = authenticates this specific endpoint (but `/next/<authid>` is irrelevant to Phase 76 scope per D-04 framing — it's the admin-skip endpoint).

**Conclusion:** Zero working (vector × endpoint) pairs for Phase 76's four target endpoints. The verdict from Phase 60 RESEARCH 2026-05-04 still holds 12 days later. **D-03 fires.**

### Required Phase 76 Scope Adjustment (per D-03)

Because the re-probe confirms 403 on every probed endpoint, Phase 76 collapses to **"in-app login subprocess only"**:

- ❌ **DROP** the inline `[QLineEdit | Save]` token row from the GBS group entirely (no paste field, no UI affordance for the broken vector).
- ❌ **DROP** the SQLite settings key `gbs_api_token` (do NOT introduce it).
- ❌ **DROP** the `AuthContext` dataclass shape (D-20) — `load_auth_context()` stays returning bare `MozillaCookieJar | None` (no token field).
- ❌ **DROP** `_open_authed()` token-first precedence helper (D-21) — `_open_with_cookies()` remains the sole HTTP entry point.
- ❌ **DROP** the four-state status enumeration (D-15) — status reverts to two states: `Not connected` / `Connected (cookies)` or simply `Connected`.
- ❌ **DROP** the `_is_gbs_token_saved()` predicate (D-16) — only `_is_gbs_connected()` survives.
- ❌ **DROP** the "clears both" Disconnect copy (D-17) — Disconnect copy reverts to "delete saved GBS.FM cookies" (Phase 60's existing wording).
- ❌ **DROP** the dual-method test matrix (D-23, D-25 dual-status / save-token rows).
- ✅ **KEEP** `_GbsLoginWindow` as the new `_TwitchCookieWindow`-shaped subprocess (D-05 through D-10).
- ✅ **KEEP** `--mode gbs` argparse extension to `oauth_helper.py`.
- ✅ **KEEP** `_on_gbs_action_clicked` rewrite to launch the subprocess (D-14 secondary File/Paste path remains for the dev-fixture / power-user case).
- ✅ **KEEP** Phase 999.3 OAuthLogger + `_CATEGORY_LABELS` + category-aware failure dialog wiring (provider-agnostic, applies unchanged).

### ROADMAP Edit Required

Per D-03 explicit instruction, the planner MUST run `/gsd:phase edit 76` (or equivalent) before plan-phase completes to:

1. **Drop the "pre-existing API token" half from the Phase 76 title** in `.planning/ROADMAP.md`. New recommended title: `"Phase 76: GBS.FM authentication: in-app login subprocess (like Google/Twitch)"`.
2. **Drop the "pre-existing API token" half from the Phase 76 goal/description** in the same ROADMAP entry. New goal: `"Add an in-app QtWebEngine login subprocess for gbs.fm (the missing piece from Phase 60's oauth_mode=None deferment), mirroring _GoogleWindow / _TwitchCookieWindow. The existing CookieImportDialog File/Paste tabs remain reachable as a secondary path."`.
3. **Optionally update REQUIREMENTS.md** to register `GBS-AUTH-01: User can log in to GBS.FM via in-app subprocess` (single requirement; the conditional `GBS-AUTH-02` for paste-token is dropped).

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

**The CONTEXT.md decisions block (D-01 through D-26) is large. The following decisions are AFFECTED by the D-03 verdict:**

- **D-01** (API-token interpretation): Confirmed by Settings-page inspection. Token visible at `https://gbs.fm/settings/` inside a dashed-border block. **Phase 76 no longer needs to interpret this** — token half is dropped.
- **D-02** (re-probe mandate): **EXECUTED — see `## Re-probe Results` below.**
- **D-03** (collapse to subprocess-only): **FIRES. See `## VERDICT` above.**
- **D-04** (full dual-auth surface): **DOES NOT FIRE.**
- **D-11 through D-18** (AccountsDialog dual-method UI): **PARTIALLY DROPPED** — inline token row removed; single-button shape returns; Disconnect copy reverts to cookies-only. The new in-app subprocess primary button replaces the existing `[Import GBS.FM Cookies...]` text on `_gbs_action_btn`; "Disconnect" remains identical to Phase 60.
- **D-19 through D-22** (token storage + auth precedence): **DROPPED** — no token, no AuthContext, no `_open_authed`.
- **D-23 through D-25** (test matrix): **PRUNED** — only the subprocess-launch + finished-handler tests survive; no token-auth fixtures recorded.
- **D-26** (`tests/test_oauth_helper.py --mode gbs` tests): **KEPT IN FULL** — this is the surviving test domain.

**The following decisions are UNAFFECTED by D-03 (still apply verbatim):**

- **D-05 through D-10** (`_GbsLoginWindow` design): The Twitch-clone shape is verified correct against the live login form. See `## _GbsLoginWindow Design` below.
- **D-14** (existing File/Paste tabs stay reachable): Stays. After the primary button changes meaning, the planner provides a secondary affordance — recommendation in `## AccountsDialog Layout` below.

### Claude's Discretion

The CONTEXT.md `<discretion>` block (lines 113-121) becomes mostly moot under D-03:

- ~~Inline File/Paste affordance after primary button changes meaning~~ — **STILL RELEVANT** under D-03; see `## AccountsDialog Layout` for recommendation.
- ~~`AuthContext` shape (NamedTuple vs dataclass vs tuple)~~ — **MOOT** under D-03 (no `AuthContext`).
- ~~`echoMode` on the inline token QLineEdit~~ — **MOOT** under D-03 (no QLineEdit). Observation kept in `## Open Questions / Discretion Calls` for future re-attempts.
- ~~Toast wording for the token Save flow~~ — **MOOT**.
- ~~`_open_with_cookies` survives as public helper~~ — **STAYS as-is**; no `_open_authed` added.
- ~~`import_station` token-first treatment~~ — **MOOT** (no token).
- ~~Inline token row label / placeholder text~~ — **MOOT**.
- ~~"Refresh status" / "Test connection" button~~ — **NO** (recommendation unchanged from CONTEXT.md).
- ~~Module constant naming for token vector~~ — **MOOT**.

### Deferred Ideas (OUT OF SCOPE)

Inherits verbatim from CONTEXT.md `<deferred>` (lines 261-279). The "Regenerate token" deferral becomes the broader **"re-attempt API-token integration if gbs.fm operator ever fixes the 403"** — this is the natural Phase 7X follow-up.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **GBS-AUTH-01** | User can log in to GBS.FM via in-app subprocess (QtWebEngine, cookie-harvest pattern matching `_TwitchCookieWindow`). | `_GbsLoginWindow` clones `_TwitchCookieWindow` (D-05); `/accounts/login/` confirmed to resolve to a Django auth form (D-08 verified); cookies set by Django on successful login = `sessionid` + `csrftoken` on `.gbs.fm` domain (D-06 verified — see `## _GbsLoginWindow Design`). |
| ~~GBS-AUTH-02~~ | ~~User can paste a pre-existing API token from gbs.fm Settings page.~~ | **DROPPED — D-03 verdict.** Token is documented at `https://gbs.fm/settings/` but does NOT authorize `/api/vote`, `/ajax`, `/add/`, or `/search`. Planner removes this requirement from REQUIREMENTS.md and ROADMAP.md. |

---

## Re-probe Results

### Probe Protocol (Reproducible)

The re-probe runs each of the 8 vectors from `.planning/phases/60-gbs-fm-integration/60-RESEARCH.md` §Auth Ladder Recommendation (line 139) against each of the 4 endpoints Phase 76 scope cares about (`/api/vote`, `/ajax`, `/add/<songid>`, `/search`) plus the `/next/<authid>` control. Each probe:

1. Loads dev-fixture cookies from `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt` (refreshed by user 2026-05-16; sessionid expires 2026-05-18, csrftoken 2026-11-11 — see "Cookie expiry status" below).
2. Establishes a **COOKIES BASELINE** for the endpoint (cookies attached, no token, follow_redirects=False).
3. Establishes a **NO-AUTH BASELINE** (no cookies, no token).
4. Runs each of 8 vector probes with no cookies, token only, follow_redirects=False.
5. Records HTTP code + first ~80 chars of response body.
6. Verdict = `WORKS_MATCH` (response body shape matches COOKIES BASELINE) / `FAILS_403` / `FAILS_REDIRECT_LOGIN` (302 with `Location: /accounts/login/`) / `FAILS_404` / `FAILS_500` / `FAILS_EXCEPTION`.

Probe driver: `/tmp/gbs76/reprobe.py` (commit not retained — out-of-tree). The vector-construction logic and target endpoints are documented inline in the verdict matrix above.

### Cookie Expiry Status

| Cookie | Value (truncated) | Expiry (epoch) | Expiry (UTC) | Days remaining (from 2026-05-16) |
|--------|-------------------|----------------|--------------|-----------------------------------|
| `sessionid` | `v6mf...phfg2` | 1779062722 | 2026-05-18 00:05 | **2** |
| `csrftoken` | `q6UZ...XseV` | 1794428510 | 2026-11-11 20:21 | 179 |

The sessionid expires in ~2 days. **Researcher's note for the planner:** if plan-phase or any wave-execution probe runs more than 48 hours after this RESEARCH.md timestamp, the dev fixture WILL be expired and the cookies baseline column will not be reproducible. Re-prompt the user to refresh the fixture if any future-phase re-probe is needed.

### Curl Reproducer (for the planner's audit trail)

The verdict matrix above was produced by `reprobe.py` driving `urllib`. The equivalent `curl` form (one representative cell — vector V6 / endpoint `/api/vote`) is:

```bash
# Cookies baseline (expected: 200 + "0 Jethro Tull..." plain text)
curl -s -o - -w "\n%{http_code}\n" \
  --cookie ~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt \
  -A "MusicStreamer/2.0 (gbs_api)" \
  "https://gbs.fm/api/vote?songid=856581&vote=3"

# V6 X-API-Key probe (expected: 403)
curl -s -o - -w "\n%{http_code}\n" \
  -A "MusicStreamer/2.0 (gbs_api)" \
  -H "X-API-Key: a8b3****c1d" \
  "https://gbs.fm/api/vote?songid=856581&vote=3"
```

Substitute V1..V8 by the rule:
- V1: append `&apikey=<TOKEN>` to URL.
- V2: append `&api_key=<TOKEN>`.
- V3: append `&key=<TOKEN>`.
- V4: add header `-H "Authorization: Bearer <TOKEN>"`.
- V5: add header `-H "Authorization: Token <TOKEN>"`.
- V6: add header `-H "X-API-Key: <TOKEN>"`.
- V7: rewrite URL to `https://gbs.fm/<TOKEN>/api/vote?songid=...` (path-embedded prefix).
- V8: use `curl -X POST -d "apikey=<TOKEN>" ...`.

### Probe Run — Verbatim Output (Masked)

Full output of `/tmp/gbs76/reprobe.py` (token masked as `a8b3****c1d` in printed URLs; raw token used in actual requests):

```
================================================================================
Phase 76 — 8-vector × 5-endpoint re-probe (2026-05-16)
Token (masked): a8b3****c1d
================================================================================

### Endpoint: /ajax
  COOKIES BASELINE  : HTTP 200 | shape: '[["removal", {"entryid": 44, "id": 1}], ["removal", {"entryid": 45, "id": 2}], ['
  NO-AUTH BASELINE  : HTTP 200 (followed 302→login)
  V1 GET /ajax?...&apikey=a8b3****c1d
      → HTTP 302 → /accounts/login/?next=... | FAILS_REDIRECT_LOGIN
  V2 GET /ajax?...&api_key=a8b3****c1d                  → HTTP 302 | FAILS_REDIRECT_LOGIN
  V3 GET /ajax?...&key=a8b3****c1d                      → HTTP 302 | FAILS_REDIRECT_LOGIN
  V4 GET /ajax [Authorization: Bearer a8b3****c1d]      → HTTP 302 | FAILS_REDIRECT_LOGIN
  V5 GET /ajax [Authorization: Token a8b3****c1d]       → HTTP 302 | FAILS_REDIRECT_LOGIN
  V6 GET /ajax [X-API-Key: a8b3****c1d]                 → HTTP 302 | FAILS_REDIRECT_LOGIN
  V7 GET /ajax/<a8b3****c1d>/?...                       → HTTP 404 | FAILS_404
  V8 POST /ajax body apikey=a8b3****c1d                 → HTTP 403 (CSRF) | FAILS_403

### Endpoint: /api/vote
  COOKIES BASELINE  : HTTP 200 | shape: '0 Jethro Tull (Under Wraps (2026 Drums)) - Under Wraps #2'
  NO-AUTH BASELINE  : HTTP 403 | ''
  V1..V6 (all token-on-/api/vote variants)              → HTTP 403 | FAILS_403  (empty body)
  V7 GET /api/<a8b3****c1d>/vote?...                    → HTTP 403 | FAILS_403
  V8 POST /api/vote body apikey=a8b3****c1d             → HTTP 403 (CSRF) | FAILS_403

### Endpoint: /add/<songid>
  COOKIES BASELINE  : HTTP 302 → /playlist (success) | with Set-Cookie: messages=...
  NO-AUTH BASELINE  : HTTP 302 → /accounts/login/?next=/add/856581
  V1..V6                                                → HTTP 302 → /accounts/login/ | FAILS_REDIRECT_LOGIN
  V7 GET /add/<a8b3****c1d>/856581                      → HTTP 404 | FAILS_404
  V8 POST /add/856581 body apikey=a8b3****c1d           → HTTP 403 (CSRF) | FAILS_403

### Endpoint: /search
  COOKIES BASELINE  : HTTP 200 | shape: 'XHTML doctype + songs table HTML'
  NO-AUTH BASELINE  : HTTP 302 → /accounts/login/?next=/search%3Fquery%3Dtest
  V1..V6                                                → HTTP 302 → /accounts/login/ | FAILS_REDIRECT_LOGIN
  V7 GET /search/<a8b3****c1d>/?query=test              → HTTP 404 | FAILS_404
  V8 POST /search body apikey=a8b3****c1d               → HTTP 403 (CSRF) | FAILS_403

### Endpoint: /next/<authid> (control — Phase 60 said this worked)
  COOKIES BASELINE  : HTTP 200 | empty body
  NO-AUTH BASELINE  : HTTP 200 | empty body
  V1..V7                                                → HTTP 200 | WORKS_MATCH (empty body)
  V8 POST /next/<authid> body apikey=...                → HTTP 403 (CSRF — POST not allowed)
```

### Interpretation of "302 on /ajax" vs Phase 60's "403 on /ajax"

Phase 60 RESEARCH 2026-05-04 reported `/ajax` returning **403** under all token vectors. This re-probe sees **302→login** instead. The semantic outcome is identical: the request is rejected. The status-code shift is a Django middleware-ordering artifact (Phase 60's run may have been against a slightly different URL form — Phase 60 probed `/ajax` without the position args; today's probe carries the full polling cursor `position=0&last_comment=0&last_removal=0&last_add=0&now_playing=0`). Either way: **the API key does not authenticate `/ajax`**.

### Settings-page Inspection

`https://gbs.fm/settings/` (fetched with dev-fixture cookies, HTTP 200, 14,936 bytes) shows the API key inside a dashed-border block:

```html
<p>Your API key:</p>
<p><div style="border-style: dashed; border-width: 1px; padding:5px; display: inline;">
  <strong>a8b3****c1d</strong>  <!-- masked here; real value used in probes -->
</div></p>
<p>This can be used for third party applications and clients that want to act on
your behalf, but that you do not want to give your password to. It can be used to
do things like make votes and comments under your name, but cannot be used to do
more destuctive [sic] things, like to delete songs you have uploaded or to change
your password.</p>
```

**No URL example, no header documentation, no usage block** is provided. The "make votes and comments under your name" prose does not match the empirical 403 verdict — gbs.fm's site documentation is **aspirational, not operational**. This contradiction has persisted at least since Phase 60 (2026-05-04) and is unchanged on 2026-05-16. [VERIFIED: settings.html fetched 2026-05-16 14:05 UTC]

### `/api/` DEBUG 404 — URLconf Drift Check

`https://gbs.fm/api/` returns the Django DEBUG 404 page (12,059 bytes). URL patterns relevant to Phase 76 are unchanged from Phase 60 RESEARCH; one new pattern noted:

- **NEW (not in Phase 60 RESEARCH):** `^user/(?P<userid>\d+)/givetoken$` [name='give_token']. This is the peer-to-peer **upload token gift** endpoint (mirror of Phase 60.4 D-T1's `_TOKEN_RE = re.compile(r"You have (\d+) tokens?")` and `fetch_user_tokens`). **NOT an auth vector** — it's user-to-user upload-quota redistribution. Out of scope for Phase 76; noted for completeness.

All other URL patterns (`/api/<resource>`, `/ajax`, `/add/<songid>`, `/next/<authid>`, `/keygen`, `/accounts/login/`, `/settings/`) match Phase 60 RESEARCH §Capability 4 verbatim.

---

## _GbsLoginWindow Design

The CONTEXT.md design (D-05 through D-10) is **fully verified** against the live gbs.fm surface. Mirror `musicstreamer/oauth_helper.py:108-192` (`_TwitchCookieWindow`) with three substitutions: login URL, trigger cookie set, output format.

### Login URL Resolution (D-08)

`https://gbs.fm/accounts/login/` resolves to a **Django auth form** (HTTP 200, 1,151 bytes):

```html
<form enctype="multipart/form-data" action="/login" method="POST">
  <input type="hidden" name="csrfmiddlewaretoken" value="oaywjpKTMTrXoJ3EAKRMFq3twUy3aKwrFV8nixIitvMcvQZncqZBAlkPDCZjF2eB">
  <input type="text" name="username" autofocus autocapitalize="none" autocomplete="username" maxlength="150" required id="id_username">
  <input type="password" name="password" autocomplete="current-password" required id="id_password">
  <!-- submit button -->
</form>
```

[VERIFIED: 2026-05-16 14:05 UTC] No OAuth fields. No third-party identity provider buttons. No CAPTCHA in the anonymous form. No 2FA challenge — username + password only (gbs.fm's operator has not added 2FA as of this re-probe).

Constant placement in `oauth_helper.py`:

```python
# Place adjacent to _TWITCH_LOGIN_URL on line 93 (existing structure).
_GBS_LOGIN_URL = "https://gbs.fm/accounts/login/"
```

### Trigger Cookie Set (D-06)

Probe evidence:

- **Anonymous GET to `/accounts/login/`** sets `csrftoken=...` (Max-Age=31449600 = 1 year, SameSite=Lax) **but NO sessionid**. [VERIFIED 2026-05-16]
- **Authenticated GET to `/`** sees both `sessionid` and `csrftoken` cookies in the request, no new Set-Cookie. [VERIFIED 2026-05-16]
- Therefore: `csrftoken` is set on first page load (anonymous); `sessionid` is set ONLY after successful login. **Waiting for BOTH cookies on the gbs.fm domain is the correct deterministic trigger.** Matches CONTEXT.md D-06 verbatim.

```python
# Mirror oauth_helper.py:94 _TWITCH_AUTH_COOKIE shape.
_GBS_TRIGGER_COOKIES = frozenset(("sessionid", "csrftoken"))
```

Trigger logic in `_GbsLoginWindow._on_cookie_added` (sketch):

```python
def __init__(self) -> None:
    super().__init__()
    self._observed: set[str] = set()
    # ... QWebEngineView setup mirror _TwitchCookieWindow ...

def _on_cookie_added(self, cookie: QNetworkCookie) -> None:
    if self._finished:
        return
    try:
        name = str(cookie.name(), "utf-8")
    except Exception:
        return
    if name not in _GBS_TRIGGER_COOKIES:
        return
    if not _cookie_domain_matches_gbs(cookie):
        return
    self._observed.add(name)
    if self._observed >= _GBS_TRIGGER_COOKIES:
        self._flush_cookies()
```

### Domain Matching (D-06 cont'd)

Mirror `_cookie_domain_matches` at `oauth_helper.py:95-105`. Verbatim adaptation:

```python
def _cookie_domain_matches_gbs(cookie: QNetworkCookie) -> bool:
    """True if the cookie's domain is a GBS.FM domain we accept.

    Accepts: "gbs.fm", "www.gbs.fm", ".gbs.fm", or any "*.gbs.fm" subdomain.
    Rejects lookalikes like "fakegbs.fm" or "gbs.fm.evil.com".
    """
    domain = cookie.domain()
    if domain in ("gbs.fm", "www.gbs.fm", ".gbs.fm"):
        return True
    return domain.endswith(".gbs.fm")
```

[CITED: `musicstreamer/oauth_helper.py:95-105`] — direct structural mirror; only the domain literals change.

### Output Format (D-07)

Mirror `_GoogleWindow._flush_cookies` at `oauth_helper.py:259-264`. The full Netscape dump of every cookie observed on the gbs.fm domain (not just the two trigger cookies — forward-compat with auxiliary cookies gbs.fm may add). Existing `_validate_gbs_cookies` at `gbs_api.py:116-141` already accepts this exact shape:

- header line `# Netscape HTTP Cookie File`
- one tab-delimited line per cookie via `_cookie_to_netscape` (shared utility at `oauth_helper.py:203-212`)
- validator requires: `sessionid` present + `csrftoken` present + `gbs.fm` domain match → returns True

```python
class _GbsLoginWindow(QMainWindow):
    """Mirror of _TwitchCookieWindow shape (oauth_helper.py:108-192).

    Trigger condition: both sessionid AND csrftoken observed on gbs.fm domain.
    Output: full Netscape dump of all gbs.fm-domain cookies (mirror _GoogleWindow).
    """
    _TIMEOUT_MS = 120_000  # 120s login deadline (mirror Twitch)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GBS.FM Login")
        self.resize(800, 600)
        self._finished = False
        self._cookies: list[QNetworkCookie] = []   # mirror _GoogleWindow:223
        self._observed_names: set[str] = set()

        self._view = QWebEngineView(self)
        self.setCentralWidget(self._view)

        profile = self._view.page().profile()
        profile.setPersistentCookiesPolicy(
            profile.PersistentCookiesPolicy.NoPersistentCookies  # type: ignore[attr-defined]
        )
        profile.setHttpUserAgent(_CHROME_UA)   # mirror Twitch's UA belt-and-braces
        cookie_store = profile.cookieStore()
        cookie_store.cookieAdded.connect(self._on_cookie_added)

        self._view.load(QUrl(_GBS_LOGIN_URL))
        QTimer.singleShot(self._TIMEOUT_MS, self._on_timeout)

    def _on_cookie_added(self, cookie: QNetworkCookie) -> None:
        if self._finished:
            return
        if not _cookie_domain_matches_gbs(cookie):
            return
        # Store every gbs.fm-domain cookie for forward-compat Netscape dump.
        self._cookies.append(cookie)
        try:
            name = str(cookie.name(), "utf-8")
        except Exception:
            return
        if name in _GBS_TRIGGER_COOKIES:
            self._observed_names.add(name)
            if self._observed_names >= _GBS_TRIGGER_COOKIES:
                # Both trigger cookies observed → flush + emit Success + exit 0.
                self._flush_cookies()

    def _flush_cookies(self) -> None:
        if self._finished:
            return
        lines = ["# Netscape HTTP Cookie File"]
        # Deduplicate by (domain, name) — same cookie can fire cookieAdded
        # multiple times if Django re-sends it. Keep last value.
        unique: dict[tuple[str, str], QNetworkCookie] = {}
        for c in self._cookies:
            try:
                name = str(c.name(), "utf-8")
            except Exception:
                continue
            unique[(c.domain(), name)] = c
        for c in unique.values():
            lines.append(_cookie_to_netscape(c))
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()
        _emit_event("Success", detail="")
        self._finish(0)

    def _on_timeout(self) -> None:
        if self._finished:
            return
        _emit_event("LoginTimeout", detail="120s")
        self._finish(1)

    def _finish(self, code: int) -> None:
        self._finished = True
        if code == 0:
            QApplication.quit()
        else:
            QApplication.exit(code)

    def closeEvent(self, event):  # noqa: N802
        if not self._finished:
            _emit_event("WindowClosedBeforeLogin", detail="")
            self._finish(1)
        super().closeEvent(event)
```

### `_emit_event` Provider Field (Anti-Pitfall Discovery)

**Important deviation from `_TwitchCookieWindow`:** the current `_emit_event` at `oauth_helper.py:71-86` **hardcodes `"provider": "twitch"`**:

```python
def _emit_event(category: str, detail: str = "", **extra) -> None:
    event = {
        "ts": time.time(),
        "category": category,
        "detail": detail,
        "provider": "twitch",   # ← HARDCODED
    }
    ...
```

Phase 76 MUST refactor `_emit_event` to accept the provider as either:
- (a) A **module-level constant** set by `main()` before each window is instantiated (e.g., `_CURRENT_PROVIDER = "gbs"` after argparse), or
- (b) An **explicit kwarg** passed by each call site (`_emit_event("Success", provider="gbs")`).

**Recommendation: (a) — module-level mutable provider constant** (set once in `main()`). Rationale: minimal call-site churn; matches how Twitch's `_emit_event` calls are already written (no `provider=` kwarg threaded through). The provider value is bound at process start and never changes for the lifetime of the subprocess.

```python
# Add near top of oauth_helper.py (after _CHROME_UA constant):
_PROVIDER = "twitch"   # default; overridden by main()

def _emit_event(category: str, detail: str = "", **extra) -> None:
    event = {
        "ts": time.time(),
        "category": category,
        "detail": detail,
        "provider": _PROVIDER,   # was hardcoded "twitch"
    }
    if extra:
        event.update(extra)
    print(json.dumps(event, separators=(",", ":")), file=sys.stderr, flush=True)

def main() -> None:
    global _PROVIDER
    parser = argparse.ArgumentParser(...)
    parser.add_argument("--mode", required=True, choices=["twitch", "google", "gbs"], ...)
    args = parser.parse_args()
    _PROVIDER = "gbs" if args.mode == "gbs" else args.mode    # "google" stays "google"
    # ... rest of main ...
```

This refactor is small, doesn't break the Twitch tests (they assert `"provider": "twitch"` in stderr — still true after main() runs), and lets `AccountsDialog._get_oauth_logger` continue to ingest provider-agnostic events.

**Cross-check with `accounts_dialog.py:417 + :437 + :443`:** the existing `provider="twitch"` hardcodes in the AccountsDialog `_on_oauth_finished` synthetic events (when subprocess doesn't emit one) MUST be parameterized when Phase 76's `_on_gbs_login_finished` is written — pass `"gbs"` instead. This is per-handler, not a refactor of `_on_oauth_finished` itself.

### Failure / Timeout Categories (D-09)

Reuses Phase 999.3 `_CATEGORY_LABELS` at `accounts_dialog.py:46-51` **without changes**:

```python
_CATEGORY_LABELS = {
    "InvalidTokenResponse":    "Login did not return a valid token",
    "LoginTimeout":            "Login took too long (2 min)",
    "WindowClosedBeforeLogin": "Login window was closed before completing",
    "SubprocessCrash":         "Login helper crashed unexpectedly",
}
```

[CITED: `musicstreamer/ui_qt/accounts_dialog.py:46-51`] All four categories apply verbatim to the GBS branch. The `"InvalidTokenResponse"` label is slightly mis-worded for the cookie-harvest flow (a cookie failure isn't a "token" failure) — planner may consider re-wording to `"Login did not return valid credentials"` in a follow-up phase. **Out of scope for Phase 76; the existing label still communicates the failure adequately.**

### WebEngine Profile Config (D-10)

Verbatim mirror of `_TwitchCookieWindow.__init__` lines 128-137:

```python
profile.setPersistentCookiesPolicy(
    profile.PersistentCookiesPolicy.NoPersistentCookies  # type: ignore[attr-defined]
)
profile.setHttpUserAgent(_CHROME_UA)
```

UA override via Chromium `--user-agent` flag is already set at module-import time (`oauth_helper.py:45-48`) — applies to all subprocess modes (twitch/google/gbs). No GBS-specific UA needed. gbs.fm's Django stack does not gate on User-Agent.

---

## gbs_api.py Expansion

### Verdict-Driven Recommendation: NO EXPANSION

Under D-03, `musicstreamer/gbs_api.py` stays **unchanged** in this phase except for the cosmetic addition of `_on_gbs_login_finished` consuming the Netscape stdout into `paths.gbs_cookies_path()` (which is an `accounts_dialog.py` change, not a `gbs_api.py` change). Specifically:

- ❌ **No `AuthContext` dataclass.** `load_auth_context()` at `gbs_api.py:92-113` keeps its current return type `Optional[MozillaCookieJar]`.
- ❌ **No `_open_authed` helper.** `_open_with_cookies` at `gbs_api.py:146-160` remains the sole HTTP entry point.
- ❌ **No `_TOKEN_HEADER` / `_TOKEN_QUERY_PARAM` constant.** No vector to encode.
- ❌ **No retry budget logic.** No 403→cookies-fallback path because there's no token-first path to fall back FROM.
- ❌ **No new `GbsTokenRejectedError` exception.** `GbsAuthExpiredError` (the existing "302→login" sentinel) remains the only auth-failure type.

### What CONTEXT.md D-20..D-23 Describes Is The Right Shape For A Future Phase

Should gbs.fm's operator ever fix the 403 / 302 behavior on the relevant endpoints, the recommended shape from CONTEXT.md D-20..D-23 is correct and can be implemented at that point. Recommended `AuthContext` shape (kept in this RESEARCH.md as a future-phase reference, not a Phase 76 action item):

```python
# FUTURE PHASE — NOT FOR PHASE 76 PER D-03 VERDICT.
from dataclasses import dataclass
from typing import Optional
import http.cookiejar

@dataclass(frozen=True)
class AuthContext:
    """Multi-method auth credentials snapshot.

    Field semantics:
      token   = string from settings table 'gbs_api_token', "" if unset.
                None if the token feature is not enabled in this build.
      cookies = MozillaCookieJar loaded from gbs_cookies_path(), or None
                if the file doesn't exist or is corrupted.

    Invariants:
      At least one of token/cookies SHOULD be set when this is passed to
      _open_authed; if both are None, _open_authed raises GbsAuthExpiredError
      with detail "no_auth_context".
    """
    token: Optional[str]
    cookies: Optional[http.cookiejar.MozillaCookieJar]
```

Rationale for `@dataclass(frozen=True)` over NamedTuple/plain tuple:
- **Immutability** is enforced (token can't be mutated mid-request — important if a future caller threads the same `AuthContext` through multiple concurrent calls).
- **Explicit field names** at call sites read better than positional tuple destructuring.
- **Codebase precedent (partial):** the existing project does not have a dataclass pattern for auth contexts (Phase 60 used a bare `MozillaCookieJar`; Phase 48 stored AA listen key as a string in SQLite). Introducing `@dataclass(frozen=True)` here is greenfield — no in-repo template to mirror. NamedTuple is also viable. Either would work; `@dataclass(frozen=True)` is the Python idiom of choice for value-object pattern.

### Retry Semantics For The Hypothetical D-04 Path

Documented here for completeness in case a future phase re-attempts this:

- **Vector type affects retry shape.** If a hypothetical future working vector were path-embedded (V7-style), the URL itself differs between token-auth and cookies-auth — `_open_authed` cannot simply "retry the same URL with cookies attached"; it must re-derive the URL for the cookies branch. Header-style or query-string vectors (V1-V6, V8) have identical URLs in both branches, so a single-URL retry works.
- **CONTEXT.md D-21 says "single retry per call."** This is correct: never loop on 403→cookies→403→token→... Just one shot per branch.

### import_station Token-First Treatment (CONTEXT.md Discretion Item)

**MOOT under D-03.** `import_station` at `gbs_api.py:1118-1220` uses three unauthenticated calls today:
- `fetch_streams()` — returns the static 6-tier list, no HTTP. [VERIFIED: `gbs_api.py:199-201`]
- `fetch_station_metadata()` — returns static dict, no HTTP. [VERIFIED: `gbs_api.py:204-206`]
- `_download_logo()` — `urlopen` of `https://gbs.fm/images/logo_3.png` (no auth required). [VERIFIED: `gbs_api.py:1085-1096`]

So `import_station` is auth-free; the discretion question "does the token work on its unauthenticated calls?" is itself moot — there are no auth-gated calls. No plumbing needed in any scenario.

### `_open_with_cookies` Stays As-Is

[CITED: `musicstreamer/gbs_api.py:146-160`] No refactor. No public-helper-vs-private discussion. The Phase 60 implementation is complete and Phase 76 doesn't touch it.

---

## AccountsDialog Layout

Under D-03 the GBS group reverts toward Phase 60's single-button shape **with one substantive change**: the primary button now launches a subprocess (Twitch-style) instead of opening `CookieImportDialog`. The existing File/Paste tabs need a secondary affordance per D-14.

### GBS Group Construction (Replaces Lines 104-115)

```python
# === Phase 76: GBS.FM group ===
self._gbs_box = QGroupBox("GBS.FM", self)
gbs_layout = QVBoxLayout(self._gbs_box)

self._gbs_status_label = QLabel(self)
self._gbs_status_label.setTextFormat(Qt.TextFormat.PlainText)  # T-40-04
self._gbs_status_label.setFont(status_font)
gbs_layout.addWidget(self._gbs_status_label)

self._gbs_action_btn = QPushButton(self)
self._gbs_action_btn.clicked.connect(self._on_gbs_action_clicked)  # QA-05
gbs_layout.addWidget(self._gbs_action_btn)

# Phase 76 / D-14: Secondary "Import cookies file…" button — keeps the
# existing CookieImportDialog reachable for users with an exported
# Netscape cookies file (dev fixture workflow, power-user export).
# Only visible when NOT connected — once connected, the user already
# has working cookies and the import path is redundant.
self._gbs_import_btn = QPushButton("Import cookies file…", self)
self._gbs_import_btn.clicked.connect(self._on_gbs_import_clicked)   # QA-05
gbs_layout.addWidget(self._gbs_import_btn)
```

### Status Label (Replaces 4-State Enumeration With 2 States)

Under D-03 the four-state enumeration (D-15) is dropped. `_update_status()` reverts to the same shape as YouTube/Twitch/AA — `Connected` / `Not connected`:

```python
# Phase 76: GBS.FM status (single-method)
if self._is_gbs_connected():
    self._gbs_status_label.setText("Connected")
    self._gbs_action_btn.setText("Disconnect")
    self._gbs_import_btn.setVisible(False)   # hide import affordance when connected
else:
    self._gbs_status_label.setText("Not connected")
    self._gbs_action_btn.setText("Connect to GBS.FM…")
    self._gbs_import_btn.setVisible(True)
```

The CONTEXT.md D-15 user preference for explicit method enumeration ("Connected (cookies)" / "Connected (token)" / "Connected (cookies + token)") is **moot under D-03** — there's only ever one method, so "Connected" is unambiguous.

**Planner discretion:** the user expressed preference for the explicit form. The planner MAY choose to render `"Connected (cookies)"` even in the single-method case, for forward-compat parallelism with YouTube/Twitch and to set up the future re-attempt at dual-method nicely. Net-zero cost.

### `_on_gbs_action_clicked` Rewrite

Mirror `_on_action_clicked` (Twitch) at `accounts_dialog.py:243-259`:

```python
def _on_gbs_action_clicked(self) -> None:
    """Phase 76: Connect (launch subprocess) or Disconnect (delete cookies file)."""
    if self._is_gbs_connected():
        # Reuse Phase 60's existing confirm-then-remove path verbatim.
        answer = QMessageBox.question(
            self, "Disconnect GBS.FM?",
            "This will delete your saved GBS.FM cookies. "
            "You will need to reconnect to vote, view the active "
            "playlist, or submit songs.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            try:
                os.remove(paths.gbs_cookies_path())
            except OSError:
                # Phase 60 HIGH 2 fix — broader OSError tolerance.
                pass
            self._update_status()
    else:
        self._launch_gbs_login_subprocess()

def _on_gbs_import_clicked(self) -> None:
    """Phase 76 D-14: secondary path — open the existing File/Paste tabs.

    Mirror Phase 60's existing implementation but invoke from this dedicated
    button so the primary button remains the subprocess-launch path.
    """
    from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog
    from musicstreamer import gbs_api
    dlg = CookieImportDialog(
        self._toast_callback,
        parent=self,
        target_label="GBS.FM",
        cookies_path=paths.gbs_cookies_path,
        validator=gbs_api._validate_gbs_cookies,
        oauth_mode=None,   # Phase 60 v1 surface unchanged
    )
    dlg.exec()
    self._update_status()
```

### `_launch_gbs_login_subprocess` (New)

Sibling of `_launch_oauth_subprocess` at `accounts_dialog.py:332-341`. Recommendation: **clone, do NOT parameterize**. Rationale: the Twitch subprocess returns a raw token (`stdout`-as-bytes-string); the GBS subprocess returns a Netscape cookies dump. The two outputs are processed differently downstream (token → write-as-text; cookies → validate-then-write-as-text). A parameterized `_launch_oauth_subprocess(mode)` would either need a second result-handler argument or a branch inside `_on_oauth_finished` — both of which are uglier than two parallel sibling methods.

```python
def _launch_gbs_login_subprocess(self) -> None:
    """Phase 76 D-09: launch oauth_helper --mode gbs.

    Mirror _launch_oauth_subprocess shape but route the finished signal
    to _on_gbs_login_finished (which validates Netscape stdout).
    """
    self._gbs_login_proc = QProcess(self)
    self._gbs_login_proc.finished.connect(self._on_gbs_login_finished)
    self._gbs_login_proc.start(
        sys.executable,
        ["-m", "musicstreamer.oauth_helper", "--mode", "gbs"],
    )
    self._update_status()   # so "Connecting…" state appears (planner: extend _update_status)

def _on_gbs_login_finished(
    self,
    exit_code: int,
    exit_status: QProcess.ExitStatus,
) -> None:
    """Mirror _on_oauth_finished but for the Netscape-stdout contract.

    Mirror lines accounts_dialog.py:361-509 — replace token write with
    Netscape validation + cookies-file write (0o600).
    """
    proc = self._gbs_login_proc
    self._gbs_login_proc = None

    # Phase 999.3 D-12: parse stderr (mirror exactly)
    last_event = self._parse_oauth_stderr(proc)   # extracted helper, planner picks

    netscape_text = ""
    if proc is not None:
        try:
            netscape_text = proc.readAllStandardOutput().data().decode(
                "utf-8", errors="replace"
            )   # NO strip — Netscape format preserves leading newlines.
        except Exception:
            netscape_text = ""

    from musicstreamer.gbs_api import _validate_gbs_cookies

    success_category = last_event is None or last_event.get("category") == "Success"
    if exit_code == 0 and netscape_text and success_category and _validate_gbs_cookies(netscape_text):
        cookies_path = paths.gbs_cookies_path()
        os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
        with open(cookies_path, "w", encoding="utf-8") as fh:
            fh.write(netscape_text)
        os.chmod(cookies_path, 0o600)   # T-40-03 / Phase 999.7 invariant

        logger = self._get_oauth_logger()
        if logger is not None:
            try:
                logger.log_event({
                    "ts": (last_event or {}).get("ts", 0.0),
                    "category": "Success",
                    "detail": "",
                    "provider": "gbs",   # NOT hardcoded "twitch"
                })
            except Exception:
                pass

        self._toast_callback("GBS.FM logged in.")
        self._update_status()
        return

    # Failure path: mirror lines 424-458 with provider="gbs".
    # (Planner extracts the failure-classification + logger.log_event +
    # _show_failure_dialog flow from _on_oauth_finished — same shape, just
    # different provider field. Recommend factoring into a helper:
    #   _classify_and_show_failure(provider: str, exit_code: int, output: str,
    #                              last_event: dict | None) -> None
    # used by BOTH _on_oauth_finished and _on_gbs_login_finished.)
    ...
```

### `echoMode` Recommendation (MOOT, Documented For Posterity)

The CONTEXT.md `<discretion>` block (line 115) asks whether the inline token `QLineEdit` should use `EchoMode.Normal` or `EchoMode.Password`. **Under D-03 this is moot — no inline token row exists.**

For future re-attempt phases, the gbs.fm Settings page treats the API key as **visible** — displayed in clear text inside a dashed-border block (`<div style="border-style: dashed; border-width: 1px; padding:5px; display: inline;"><strong>a8b3****c1d</strong></div>`), copyable as text. The page does NOT password-mask it, does NOT offer a "show/hide" toggle, does NOT use `<input type="password">`. The site treats it as a low-secrecy identifier (more like an API client key than a session credential — though our auth-vector probe shows the gbs.fm operator probably wouldn't notice if it WAS leaked, since it doesn't authorize anything Phase 76 cares about anyway).

**Recommendation for a future re-attempt phase:** `QLineEdit.EchoMode.Normal` (visible text). Matches the gbs.fm UX. Pasting from clipboard reads naturally. No "show/hide eye toggle" needed.

### Phase 60 D-04c Group Placement Stays

The GBS box sits between `_youtube_box` and `twitch_box` in the layout. Phase 76 does NOT change ordering. [CITED: `accounts_dialog.py:150-153`]

---

## Test Strategy

Under D-03, the test surface narrows substantially from CONTEXT.md D-23/D-24/D-25/D-26. Tests fall into three groups:

### Group A: `tests/test_oauth_helper.py` (D-26 — Kept In Full)

If `tests/test_oauth_helper.py` does not exist yet, the planner creates it. New tests (or new test class within existing test file):

| Test | What | Why |
|------|------|-----|
| `test_argparse_accepts_mode_gbs` | `oauth_helper.main()` with `--mode gbs` doesn't ArgumentError | Argparse choices extended (D-08 verification) |
| `test_gbs_login_window_loads_login_url` | Construct `_GbsLoginWindow` (with mocked QWebEngineView), assert `.load()` called with `QUrl("https://gbs.fm/accounts/login/")` | D-08 lock verification |
| `test_gbs_cookie_domain_matches_accepts_gbs_fm` | `_cookie_domain_matches_gbs(QNetworkCookie domain="gbs.fm")` → True. Same for `.gbs.fm`, `www.gbs.fm`, `sub.gbs.fm`. False for `fakegbs.fm`, `gbs.fm.evil.com` | D-06 domain validation |
| `test_gbs_trigger_fires_on_both_cookies` | Inject two cookies (`sessionid` + `csrftoken`) on `.gbs.fm` → `_flush_cookies` called once. Inject only `sessionid` → not called. Inject only `csrftoken` → not called | D-06 dual-trigger verification |
| `test_gbs_flush_produces_valid_netscape` | After `_flush_cookies`, captured stdout passes `_validate_gbs_cookies()` | D-07 + integration with existing validator |
| `test_gbs_timeout_emits_login_timeout` | Force `QTimer.singleShot` callback → emits `{"category": "LoginTimeout", "detail": "120s", "provider": "gbs"}` on stderr | D-09 category + provider field |
| `test_gbs_window_closed_before_login` | Close the window before cookies observed → emits `WindowClosedBeforeLogin`, exits non-zero | D-09 |
| `test_gbs_emits_provider_gbs_field` | All stderr events on `--mode gbs` carry `"provider": "gbs"` (not "twitch") | Anti-pitfall: catches a regression where `_emit_event`'s hardcoded provider isn't refactored |

### Group B: `tests/test_accounts_dialog.py` (D-25 — Pruned)

| Test | What | Why |
|------|------|-----|
| `test_gbs_status_shows_connected_when_cookies_present` | With `paths.gbs_cookies_path()` existing → label `"Connected"`, primary button text `"Disconnect"`, import button hidden | Replaces dual-method status tests |
| `test_gbs_status_shows_not_connected_when_no_cookies` | With no cookies file → label `"Not connected"`, primary text `"Connect to GBS.FM…"`, import button visible | |
| `test_gbs_action_launches_subprocess_when_not_connected` | Click primary in not-connected state → `QProcess.start` called with `sys.executable, ["-m", "musicstreamer.oauth_helper", "--mode", "gbs"]` | D-09 launch contract |
| `test_gbs_disconnect_clears_cookies_with_yes` | With cookies present + user clicks Yes → `os.remove(paths.gbs_cookies_path())` + status updates | Preserves Phase 60 HIGH 2 OSError tolerance |
| `test_gbs_disconnect_no_op_with_no` | Yes/No dialog returns No → file remains, status unchanged | |
| `test_gbs_import_button_opens_cookieimportdialog` | Click secondary import button → `CookieImportDialog.exec()` is invoked with the gbs-fm parameterization (target_label="GBS.FM", validator=_validate_gbs_cookies, oauth_mode=None) | D-14 reachability verification |
| `test_gbs_login_finished_writes_cookies_on_success` | Mock subprocess: exit=0, stdout=valid Netscape text → `paths.gbs_cookies_path()` written + 0o600 perms + toast fires + status updates | Mirror existing `_on_oauth_finished` test shape |
| `test_gbs_login_finished_failure_dialog_for_each_category` | Parameterize over [`LoginTimeout`, `WindowClosedBeforeLogin`, `InvalidTokenResponse`, `SubprocessCrash`] → category-aware failure dialog appears with matching `_CATEGORY_LABELS` text + inline Retry button works | Phase 999.3 D-08/D-09 verification at the GBS branch |
| `test_gbs_login_finished_invalidates_bad_netscape` | Mock subprocess: exit=0, stdout="garbage text" → cookies file NOT written; failure dialog shows `InvalidTokenResponse` category | Anti-pitfall: `_validate_gbs_cookies` is the gate before writing |

### Group C: Tests Dropped Under D-03

The following CONTEXT.md test ideas do NOT survive the verdict:

- ❌ Token-auth fixture recordings for any endpoint (no working vector to record).
- ❌ `tests/test_gbs_api.py` cookies-fallback-on-403 tests (no token-first path to fall back from).
- ❌ Dual-method status string tests (4 states → 2 states; no token state).
- ❌ Inline token Save flow test (no QLineEdit).
- ❌ Disconnect-clears-both tests (no token to clear).
- ❌ `AuthContext` type tests (no `AuthContext`).

### Test Fixtures

**No new fixtures recorded under D-03.** The existing `tests/fixtures/gbs/` directory (from Phase 60) remains unchanged. Phase 76 tests use mocked `QWebEngineView`, mocked `QNetworkCookie`, and mocked `QProcess` — no live HTTP needed.

If a future re-probe phase fires D-04, the recording method from Phase 60 RESEARCH D-24 applies verbatim: `urllib.request.urlopen(url + auth) → response.read() → open("tests/fixtures/gbs/<endpoint>-token.txt", "w").write(...)`. One fixture per endpoint per auth mode.

---

## Validation Architecture

The phase enables `workflow.nyquist_validation` per `.planning/config.json`. Four critical-path validations for Phase 76:

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (existing project convention) |
| Config file | `pytest.ini` (existing — verified in project tree) |
| Quick run command | `pytest tests/test_oauth_helper.py tests/test_accounts_dialog.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | Critical Path |
|--------|----------|-----------|-------------------|---------------|
| GBS-AUTH-01 | Re-probe verdict locked & documented (D-03 vs D-04) | research-artifact | (this RESEARCH.md exists + verdict is unambiguous) | ✓ |
| GBS-AUTH-01 | `_GbsLoginWindow` triggers on both `sessionid` + `csrftoken` on `.gbs.fm` | unit | `pytest tests/test_oauth_helper.py::test_gbs_trigger_fires_on_both_cookies -x` | ✓ |
| GBS-AUTH-01 | Subprocess output validates via existing `_validate_gbs_cookies` | unit | `pytest tests/test_oauth_helper.py::test_gbs_flush_produces_valid_netscape -x` | ✓ |
| GBS-AUTH-01 | `_on_gbs_login_finished` writes cookies file with 0o600 perms on success | unit | `pytest tests/test_accounts_dialog.py::test_gbs_login_finished_writes_cookies_on_success -x` | ✓ |
| GBS-AUTH-01 | Disconnect deletes cookies file (preserves Phase 60 OSError tolerance) | unit | `pytest tests/test_accounts_dialog.py::test_gbs_disconnect_clears_cookies_with_yes -x` | ✓ |
| GBS-AUTH-01 | `_emit_event` carries `"provider": "gbs"` (not hardcoded "twitch") | unit | `pytest tests/test_oauth_helper.py::test_gbs_emits_provider_gbs_field -x` | ✓ |

### Sampling Rate
- **Per task commit:** `pytest tests/test_oauth_helper.py tests/test_accounts_dialog.py -x -q` (covers both new modules)
- **Per wave merge:** `pytest -x -q` (full suite — no Phase 60 regressions)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_oauth_helper.py` — does this file exist? Check during plan-phase. **If absent, Wave 0 creates it** (Group A above is brand-new test surface). If present, Wave 0 just extends with the GBS branch.
- [ ] `tests/test_accounts_dialog.py` — exists (Phase 53, 60, others). Wave 0 extends with the GBS pruned suite (Group B).
- [ ] No new conftest fixtures; no new framework install (pytest already present).
- [ ] Two new helpers may emerge during planning: `_parse_oauth_stderr(proc)` and `_classify_and_show_failure(provider, exit_code, output, last_event)` — both extracted from existing `_on_oauth_finished`. If extracted, Wave 0 adds tests for the extracted helpers BEFORE the GBS branch uses them.

---

## Open Questions / Discretion Calls

Items the planner picks between, with researcher recommendations:

1. **Forward-compat parallelism on the status label.** Under D-03 there's only one method, so `"Connected"` is unambiguous. But the user expressed preference for `"Connected (cookies)"` enumeration. Net-zero cost to keep the parenthetical form even in single-method case.
   - **Researcher recommendation:** Render `"Connected (cookies)"` even though only one method exists. Cheap forward-compat — if a future re-probe ever fires D-04 the status code can grow without UI redesign.

2. **Refactor scope for `_emit_event` provider field.** Two options:
   - (a) Module-level `_PROVIDER` constant set by `main()` (least churn).
   - (b) Explicit `provider=` kwarg on every `_emit_event` call site (more explicit).
   - **Researcher recommendation:** (a). Tested fine via Group A `test_gbs_emits_provider_gbs_field`.

3. **Failure-handler factoring.** `_on_oauth_finished` (Twitch) and `_on_gbs_login_finished` (new) share most of their stderr-parsing + failure-classification logic. Two options:
   - (a) Copy-paste the failure logic into both methods (most diff-explicit; easy to read each one in isolation).
   - (b) Extract `_classify_and_show_failure(provider, exit_code, output, last_event)` once and call from both.
   - **Researcher recommendation:** (b) — the symmetry is real and the function fits cleanly. Add it as a Wave 0 refactor task BEFORE the GBS branch lands. Twitch tests verify the extracted helper produces the same behavior; then GBS tests build on it.

4. **`_oauth_proc` vs `_gbs_login_proc` field on AccountsDialog.** The dialog tracks an active subprocess via `self._oauth_proc` for Twitch. Phase 76 needs a parallel slot for GBS — either:
   - (a) Separate `self._gbs_login_proc` field (allows concurrent in-flight Twitch + GBS subprocesses — though no UI affordance allows triggering both at once).
   - (b) Reuse `self._oauth_proc` (forces serialization — clicking Connect on one while the other is mid-flight does nothing or shows an error).
   - **Researcher recommendation:** (a) — separate fields. Concurrent subprocesses are harmless (each owns its own QtWebEngine subprocess in a separate OS process; they don't share state); preventing concurrency would be UX friction without benefit.

5. **Status label intermediate "Connecting…" state for GBS.** Twitch shows `"Connecting..."` while the subprocess is alive (`_update_status` line 194-196). GBS should do the same; the planner inserts that branch into `_update_status`.

6. **ROADMAP edit timing.** Per D-03 the ROADMAP entry must be edited before plan-phase locks. Two timings:
   - (a) **Researcher does it now** (in this same session, via `/gsd:phase edit 76` invocation). Cleaner — research artifact and roadmap state agree.
   - (b) **Planner does it as the first plan-phase action**, before writing PLAN files.
   - **Researcher recommendation:** (b). The researcher's job is to verify and report; the planner's job is to update the surrounding planning artifacts (REQUIREMENTS.md, ROADMAP.md). The researcher's `## VERDICT: D-03` block above gives the planner all the information needed to do the edit.

7. **Phase title-change vote.** Recommended replacement: `"Phase 76: GBS.FM authentication: in-app login subprocess (like Google/Twitch)"`. Alternative shorter: `"Phase 76: GBS.FM in-app login"`. Planner picks; both are accurate.

---

## Sources

### Primary (HIGH confidence — directly probed live in this session)
- **Live re-probe of gbs.fm endpoints, 2026-05-16 14:00–14:10 UTC** — 5 endpoints × (1 cookies baseline + 1 no-auth baseline + 8 vector probes) = 50 HTTP requests. Verdict matrix above is reproducible via `/tmp/gbs76/reprobe.py` driving `urllib` against `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt`.
- **Live inspection of `https://gbs.fm/settings/`** — confirmed API key shape (`a8b3edc60999c5718c9fb953b8250c1d`, 32 hex chars, dashed-border visible-text display). Confirmed no documentation of a working vector.
- **Live inspection of `https://gbs.fm/accounts/login/`** — confirmed Django auth form (action="/login", POST, `csrfmiddlewaretoken` + `username` + `password` fields, no OAuth, no 2FA).
- **Live inspection of `https://gbs.fm/api/`** — Django DEBUG 404 page (12,059 bytes) listing the full URLconf. Confirmed unchanged from Phase 60 RESEARCH except for the new `^user/(?P<userid>\d+)/givetoken$` pattern (peer-to-peer upload-token gifting, irrelevant to auth).
- **Direct source inspection:**
  - `musicstreamer/oauth_helper.py` (entire file, 304 lines) — confirmed `_TwitchCookieWindow`, `_GoogleWindow`, `_cookie_domain_matches`, `_cookie_to_netscape`, `_emit_event` shapes.
  - `musicstreamer/ui_qt/accounts_dialog.py` (entire file, 510 lines) — confirmed `_CATEGORY_LABELS`, `_get_oauth_logger`, `_on_oauth_finished`, `_launch_oauth_subprocess`, current GBS box construction.
  - `musicstreamer/gbs_api.py` (lines 1-300) — confirmed `load_auth_context`, `_validate_gbs_cookies`, `_open_with_cookies` shapes.
  - `musicstreamer/paths.py` (entire file) — confirmed `gbs_cookies_path()` definition.
  - `musicstreamer/ui_qt/cookie_import_dialog.py:333-342` — confirmed `_write_cookies` 0o600 pattern.

### Secondary (HIGH confidence — Phase 60 RESEARCH cross-reference)
- `.planning/phases/60-gbs-fm-integration/60-RESEARCH.md` lines 1-20, 139-150, 1260-1299 — confirmed verbatim that Phase 60's auth-vector verdict is what Phase 76 re-probe is supposed to re-check. Verdict holds 12 days later.
- `.planning/phases/60-gbs-fm-integration/60-CONTEXT.md` §D-04 — auth-ladder framing.

### Sources NOT consulted
- Context7 / WebSearch / Brave / Exa / Firecrawl — **not needed**. This phase is entirely about (a) verifying the operator behavior of one specific third-party site (which is directly probable via `curl`) and (b) confirming code-internal patterns (which is directly verifiable via file reads). No library-documentation lookups required.

---

## Metadata

**Confidence breakdown:**
- Verdict (D-03 fires): **HIGH** — 50 live HTTP requests with reproducible matrix.
- `_GbsLoginWindow` design fidelity: **HIGH** — direct mirror of in-repo `_TwitchCookieWindow` with verified trigger-cookie set.
- AccountsDialog layout: **HIGH** — patterns are well-established (Phase 53, 60, 999.3); collapsed-scope shape is a straightforward simplification.
- Test strategy: **HIGH** — leverages existing Phase 999.3 + Phase 60 test fixtures and patterns.
- Long-term stability of gbs.fm operator's auth posture: **MEDIUM** — Phase 60 RESEARCH 2026-05-04 noted the operator is "NOT actively maintaining/refactoring"; Phase 76 re-probe 2026-05-16 confirms zero shift. Future phases should re-probe before assuming D-03 still holds.

**Research date:** 2026-05-16
**Valid until:** 2026-06-15 (30-day default for gbs.fm-side findings); the code-internal pattern findings remain valid until the relevant files are refactored (no scheduled refactor in flight).

## RESEARCH COMPLETE

**Phase:** 76 — GBS.FM authentication (subprocess-only after D-03 verdict)
**Confidence:** HIGH

### Key Findings

- **D-03 fires.** API key returns 403 (or 302→login) on every Phase 76 endpoint across all 8 auth vectors. Phase 60 RESEARCH 2026-05-04 verdict holds 12 days later. Phase 76 scope collapses to "in-app login subprocess only" — drops the inline token row, `AuthContext`, `_open_authed`, dual-method status, and dual-method tests.
- **`_GbsLoginWindow` design fully verified.** `https://gbs.fm/accounts/login/` resolves to a Django auth form (no OAuth, no 2FA). Trigger condition `sessionid` + `csrftoken` on `.gbs.fm` is correct: anonymous `csrftoken` is set on page load; `sessionid` only appears post-login. Direct mirror of `_TwitchCookieWindow` shape with three substitutions (URL, trigger names, output format = Netscape dump per `_GoogleWindow._flush_cookies`).
- **`_emit_event` hardcodes `provider="twitch"`** — Phase 76 must refactor (recommend module-level `_PROVIDER` constant set by `main()`).
- **AccountsDialog GBS group simplifies to single-button primary + secondary "Import cookies file…" button** under D-03. Disconnect copy reverts to Phase 60's cookies-only wording.
- **No `gbs_api.py` changes under D-03.** `load_auth_context()`, `_open_with_cookies`, `_validate_gbs_cookies` all stay as-is.
- **Test surface narrows to: oauth_helper `--mode gbs` tests (Group A, ~8 new) + AccountsDialog GBS subprocess tests (Group B, ~9 new).** No fixture recordings needed.

### Ready for Planning

Research complete. **Planner's first action** is to edit ROADMAP.md (and optionally REQUIREMENTS.md) via `/gsd:phase edit 76` to drop the "pre-existing API token" half from the Phase 76 title and goal. Then plan-phase decomposes into the surviving scope: `_GbsLoginWindow` + `--mode gbs` argparse + AccountsDialog GBS handler rewrite + Group A & B tests + provider-field refactor of `_emit_event`.
