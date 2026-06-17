# Phase 89B: Twitch Channel-Avatar Fetch - Research

**Researched:** 2026-06-16
**Domain:** Twitch Helix REST API + per-provider avatar fetcher registry + EditStationDialog Twitch URL detection
**Confidence:** HIGH (all six research questions answered directly from codebase reads + official Twitch docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Avatar key & provider derivation**
- D-01: Avatar is keyed per-provider (89.1 model). Store as `assets/channel-avatars/{provider_id}.png` via `assets.write_provider_avatar(provider_id, data)` + `repo.update_provider_avatar_path(provider_id, path)`.
- D-02: Provider derived from Twitch login — `url.rstrip("/").split("/")[-1]`, case-folded — `ensure_provider("Twitch: <login>")`, set station `provider_id`. Only when the Provider field is blank (D-04).
- D-03: Provider name = `"Twitch: <login>"` (lowercase login, not display_name; `"Twitch: "` prefix disambiguates).
- D-04: Auto-assign provider only when the station's Provider field is blank.

**Helix fetch & authentication**
- D-05: New `musicstreamer/twitch_helix.py` exposes `fetch_channel_avatar(twitch_url_or_login) -> bytes`. Registered via `register_avatar_fetcher("twitch", twitch_helix.fetch_channel_avatar)`.
- D-06: Reuse the existing Phase 32 `auth-token` cookie token. Send to Helix as `Authorization: Bearer <auth-token>` + `Client-Id: kimne78kx3ncx6brgo4mv6wki5h1ko`. (Same secret, different transport from streamlink's `OAuth` prefix.)
- D-07: All failure modes fall back non-blocking. No token / Helix 401 / empty `data` / network error → no-op, cover slot uses station thumbnail. Save always allowed. Failed fetch shows inline note; consider "connect Twitch" hint when cause is missing/expired token.

**Fetch trigger & refresh cadence**
- D-08: Reuse Phase 89/89.1 fetch trigger unchanged. Debounced auto-fetch on `twitch.tv` URL; reuse-on-open skip; manual Refresh button. No new dialog widgets.
- D-09: Manual Refresh only — no TTL, no per-play refetch.
- D-10: Refresh is shared-effect (per-provider); reuse existing 89.1 D-08 hint text.

**Rendering & precedence**
- D-11: Cover-slot swap, circular-crop, ICY-disabled trigger — all unchanged. `bind_station` already resolves via `station.provider_id` → `providers.avatar_path` (89.1 D-05). A stored Twitch avatar flows through automatically.

### Claude's Discretion
- Exact `fetch_channel_avatar` signature (accept URL and parse vs. accept login) — match `Callable[[str], bytes]` registry shape and YouTube fetcher style.
- Request timeout / error-class handling (mirror `yt_import` urlopen timeout and WR-01 daemon-worker backstop discipline).
- Exact wording/placement of no-token "connect Twitch" hint (D-07).
- Whether to add a tiny login-parse helper or inline the `split("/")[-1]` derivation (D-02).

### Deferred Ideas (OUT OF SCOPE)
- Provider brand-avatar cover-slot fallback (SomaFM, AudioAddict) — Phase 89c (ART-AVATAR-11/12).
- Separate `display_name` column — rejected as schema scope creep.
- Staleness TTL / background refresh — rejected (D-09).
- Twitch avatar in the logo slot — rejected by REQUIREMENTS anti-goal.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ART-AVATAR-04 | For Twitch stations, `musicstreamer/twitch_helix.py` fetches the channel `profile_image_url` from `GET https://api.twitch.tv/helix/users?login=<x>` using the existing Phase 32 `twitch-token.txt` user token (no new OAuth scopes) | Helix /users endpoint contract verified; token feasibility assessed (see Critical Finding #1 below) |

</phase_requirements>

---

## Summary

Phase 89b is a narrow integration: create `musicstreamer/twitch_helix.py` with `fetch_channel_avatar(url_or_login) -> bytes`, register it at module load, expand the URL-detection gate in `edit_station_dialog.py` to include `twitch.tv` URLs, and add login-to-provider derivation + blank-provider assignment in the save path. Every other moving part (storage, rendering, circular-crop, cover-slot swap, DB persist, worker thread) was already built by Phases 89, 89.1, and 89a.

The six research questions raised in the brief are answered below. The highest-value finding is on token feasibility (#1): the official Twitch documentation explicitly states "You may also use the Bearer prefix in place of OAuth in the Authorization header," directly confirming that the harvested `auth-token` cookie — already accepted as `OAuth <token>` by the GQL endpoint — is the same credential and can be presented as `Bearer <token>` to the Helix REST endpoint. This eliminates the primary risk. The secondary risk (URL parsing edge cases) has three guarded cases the planner must handle.

**Primary recommendation:** Proceed as designed. Token feasibility is confirmed. Twitch profile images are square CDN URLs downloadable without auth. No new dialog code, no new storage primitives, no new render primitives needed.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Helix HTTP fetch (Bearer + Client-Id) | `twitch_helix.py` module | — | New module, pure sync function, no Qt deps |
| Registry registration | `twitch_helix.py` module load | `yt_import._AVATAR_FETCHERS` | One `register_avatar_fetcher("twitch", ...)` call at module import |
| URL detection + worker dispatch | `EditStationDialog._on_url_timer_timeout` | `_on_url_text_changed` | Existing gate currently gated to YouTube; needs `twitch.tv` added in parallel |
| Login → provider derivation + assignment | `EditStationDialog._on_save` | `repo.ensure_provider` | New logic: parse login from URL, ensure_provider, assign if blank |
| Avatar file write + DB persist | `assets.write_provider_avatar` + `repo.update_provider_avatar_path` | — | Reused unchanged from 89.1 |
| Cover-slot swap + circular crop | `now_playing_panel.bind_station` + `_set_avatar_pixmap_from_path` | — | Reused unchanged from 89/89.1 |

---

## Critical Research Findings

### Finding #1 (Token Feasibility) — CONFIRMED, NO BLOCKER

**Question:** Does the harvested web `auth-token` cookie work against the Helix REST endpoint with `Bearer` + `Client-Id: kimne78kx3ncx6brgo4mv6wki5h1ko`?

**Verdict: YES — confirmed by official Twitch documentation.**

The Twitch developer authentication docs state verbatim:
> "You may also use the Bearer prefix in place of OAuth in the Authorization header."
[CITED: https://dev.twitch.tv/docs/authentication/validate-tokens/]

The `auth-token` cookie is Twitch's own user access token (a 30-character alphanumeric OAuth token) issued by the Twitch web SPA. The Helix API accepts user access tokens as Bearer tokens. The only change between the GQL path and the Helix path is the prefix word and the addition of `Client-Id`. This is exactly what CONTEXT D-06 describes.

**Exact required headers for Helix /users:**
```
GET https://api.twitch.tv/helix/users?login=<login>
Authorization: Bearer <auth-token-cookie-value>
Client-Id: kimne78kx3ncx6brgo4mv6wki5h1ko
```
[CITED: https://dev.twitch.tv/docs/api/reference/#get-users]

**Response shape (success, HTTP 200):**
```json
{
  "data": [
    {
      "id": "141981764",
      "login": "twitchdev",
      "display_name": "TwitchDev",
      "type": "",
      "broadcaster_type": "partner",
      "description": "Supporting third-party...",
      "profile_image_url": "https://static-cdn.jtvnw.net/jtv_user_pictures/...-300x300.png",
      "offline_image_url": "https://static-cdn.jtvnw.net/jtv_user_pictures/...",
      "created_at": "2016-12-14T20:32:28Z"
    }
  ]
}
```
[CITED: https://dev.twitch.tv/docs/api/reference/#get-users]

**Failure modes and exact HTTP codes:**

| Failure | HTTP Code | Condition | `twitch_helix.py` action |
|---------|-----------|-----------|--------------------------|
| No token file | n/a | `twitch-token.txt` absent | raise `RuntimeError("no twitch token")` before HTTP call |
| Expired / invalid token | 401 | Token rejected by Helix | raise (worker catches → empty emit) |
| Login not found | 200 | `data: []` (empty array) | raise `ValueError("no user data for login")` |
| Malformed/empty login | 400 | Bad request | raise on HTTP error |
| Network error | n/a | `URLError`/timeout | raise (worker catches) |

**Confidence: HIGH** — directly confirmed by official Twitch developer docs.

---

### Finding #2 (Login Parsing) — CONFIRMED WITH EDGE CASES

**Question:** Is `url.rstrip("/").split("/")[-1]` robust for Twitch station URLs?

**Verdict: Robust for the common case; three edge cases need guards.**

The production pattern in `player.py:_twitch_resolve_worker` (L1972) uses:
```python
channel = url.rstrip("/").split("/")[-1]
```
[VERIFIED: codebase read at `/musicstreamer/player.py:1972`]

This handles:
- `https://www.twitch.tv/twitchdev` → `"twitchdev"` (correct)
- `https://www.twitch.tv/twitchdev/` → `"twitchdev"` (trailing slash stripped)

**Edge cases the planner must address:**

1. **Extra path segments (e.g. `/videos`, `/clips`):** A URL like `https://www.twitch.tv/twitchdev/videos` would yield `"videos"`, not the login. Mitigation: apply case-folding + optionally guard against known sub-paths, or accept that `GET /users?login=videos` will return `data: []` and fall through to the non-blocking no-avatar path. The registry is only triggered for `twitch.tv` URLs anyway — only the login page form matters.

2. **Query strings:** `url.rstrip("/").split("/")[-1]` preserves any `?...` suffix — `https://www.twitch.tv/twitchdev?ref=header` yields `"twitchdev?ref=header"`. The login must be further cleaned: `split("?")[0]` or similar before sending to Helix. [ASSUMED — needs guard in `fetch_channel_avatar`]

3. **Case folding:** Helix `login` parameter is case-insensitive (Helix normalizes internally). However, D-03 specifies lowercase login for the provider name to survive display-name rebrands. Apply `.lower()` to the derived segment before building the `"Twitch: <login>"` provider name string. [ASSUMED based on Helix behavior documented at dev.twitch.tv]

**Recommended login-parse idiom for `twitch_helix.py`:**
```python
def _parse_login(url_or_login: str) -> str:
    """Derive Twitch login from a twitch.tv URL or bare login string."""
    s = url_or_login.rstrip("/")
    if "/" in s:
        s = s.split("/")[-1]
    s = s.split("?")[0].split("#")[0].strip()
    return s.lower()
```

**Confidence: HIGH for the core case; ASSUMED for query-string / hash guard (low-risk; defensive).**

---

### Finding #3 (profile_image_url Characteristics) — CONFIRMED

**Question:** Is `profile_image_url` a square, auth-free, directly downloadable URL?

**Verdict: YES on all three counts.**

- **Square:** Twitch profile images are always square (300×300 px in the default API response). The CDN URL encodes the size: `...-profile_image-300x300.png`. No `width != height` guard needed (unlike YouTube's ART-AVATAR-03 guard). [CITED: Twitch CDN URL pattern; multiple community confirmations]
- **No auth on image download:** The `profile_image_url` points to `https://static-cdn.jtvnw.net/jtv_user_pictures/...` — a plain public CDN URL. A direct `urllib.request.urlopen(profile_image_url, timeout=10)` suffices. No `Authorization` or `Client-Id` header on the image download request. [ASSUMED from CDN pattern; consistent with community usage]
- **HTTPS:** The URL is always HTTPS. Standard `urlopen` with `timeout=10` mirrors the pattern used for YouTube avatar download in `yt_import.py:258`. [VERIFIED: codebase read + CDN URL format from docs]

**Implication for `twitch_helix.py`:** No non-square guard; no special download auth; 10s timeout on both the Helix API call and the CDN image download. This mirrors `yt_import.fetch_channel_avatar`'s `urlopen(url, timeout=10)` pattern exactly.

**Confidence: HIGH** for square shape (CDN URL encodes dimensions); ASSUMED for "no auth on image download" (consistent with public CDN behavior but not explicitly documented).

---

### Finding #4 (Reuse Map — Symbol Verification) — ALL CONFIRMED

**Question:** Do the named symbols exist with the expected signatures?

All verified by direct codebase read. Exact line numbers given for `read_first` fields.

#### `yt_import.register_avatar_fetcher` / `get_avatar_fetcher` / `_AVATAR_FETCHERS`
[VERIFIED: `/musicstreamer/yt_import.py:L262–287`]

```python
_AVATAR_FETCHERS: dict[str, Callable[[str], bytes]] = {}   # L269

def register_avatar_fetcher(provider: str, fetcher: Callable[[str], bytes]) -> None: ...  # L272
def get_avatar_fetcher(provider: str) -> Optional[Callable[[str], bytes]]: ...             # L281
# Stub comment at L266: "register_avatar_fetcher("twitch", twitch_helix.fetch_channel_avatar)"
register_avatar_fetcher("youtube", fetch_channel_avatar)   # L287 — YouTube already registered
```

The fetcher is invoked with a **URL string** (the dialog passes `url` from `url_edit.text()` directly — see `_AvatarFetchWorker.__init__` `self._url = url` and `run()` which calls `yt_import.fetch_channel_avatar(self._url, ...)`).

**Implication:** `twitch_helix.fetch_channel_avatar` receives the full `twitch.tv` URL, must parse the login internally. Signature: `fetch_channel_avatar(url: str) -> bytes`.

However, the `_AvatarFetchWorker.run()` at L173 currently hard-codes the YouTube path:
```python
data = yt_import.fetch_channel_avatar(self._url, node_runtime=self._node_runtime)
```
**This must change for 89b:** The worker needs to dispatch through the registry (`get_avatar_fetcher`) rather than calling the YouTube-specific function directly, OR a new provider-aware dispatch is added. The CONTEXT D-08 says the Twitch fetcher "plugs into the existing `_AvatarFetchWorker` / registry path" — the planner must add registry-based dispatch in `_AvatarFetchWorker.run()`.

#### `assets.write_provider_avatar(provider_id, data)`
[VERIFIED: `/musicstreamer/assets.py:L63–89`]

```python
def write_provider_avatar(provider_id: int, data: bytes) -> str:
    """Returns path relative to paths.data_dir(), e.g. 'assets/channel-avatars/7.png'."""
```
Uses `tempfile.mkstemp + os.replace` atomicity. Identical pattern to `write_channel_avatar`. Already called by `_AvatarFetchWorker.run()` (L176).

#### `repo.update_provider_avatar_path(provider_id, path)`
[VERIFIED: `/musicstreamer/repo.py:L965–976`]

```python
def update_provider_avatar_path(self, provider_id: int, path: Optional[str]) -> None:
    """Phase 89.1 D-09: dedicated single-column UPDATE for providers.avatar_path."""
```
Non-silent-reset pattern — single-column UPDATE only.

#### `repo.ensure_provider(name)`
[VERIFIED: `/musicstreamer/repo.py:L481–488`]

```python
def ensure_provider(self, name: str) -> Optional[int]:
    """INSERT OR IGNORE into providers; returns provider_id int or None if name is blank."""
```
Returns `None` for blank/empty name. Called from `_on_save` (L1675). 89b's login→provider assignment (`"Twitch: <login>"`) passes through this.

#### `cover_art._channel_avatar_lookup`
[VERIFIED: `/musicstreamer/cover_art.py:L159–187`]

```python
def _channel_avatar_lookup(station, callback) -> None:
    """Synchronous path-returner. NEVER raises (WR-04 contract). No thread launch.
    Reads station.provider_avatar_path (Phase 89.1 D-05)."""
```
Reads `station.provider_avatar_path` via `getattr` (safe for None). A Twitch provider avatar stored in `providers.avatar_path` is exposed on `Station.provider_avatar_path` (via the LEFT JOIN mapper — verified at `models.py:L44`). The lookup already resolves it correctly. **Zero changes needed to `cover_art.py`.**

#### `now_playing_panel.bind_station` provider-keyed avatar swap
[VERIFIED: `/musicstreamer/ui_qt/now_playing_panel.py:L937–943`]

```python
if getattr(station, "icy_disabled", False):
    _provider_rel = getattr(station, "provider_avatar_path", None)
    if _provider_rel:
        if _os.path.isfile(_os.path.join(_p.data_dir(), _provider_rel)):
            self._set_avatar_pixmap_from_path(_provider_rel)
```
Already reads `provider_avatar_path`. A stored Twitch provider avatar (same `providers.avatar_path` column, same `Station.provider_avatar_path` field) flows through this path automatically. **Zero changes needed to `now_playing_panel.py`.**

#### `edit_station_dialog.py` — `_AvatarFetchWorker`, `provider_combo`, `_on_refresh_avatar_clicked`
[VERIFIED: `/musicstreamer/ui_qt/edit_station_dialog.py` multiple reads]

- `_AvatarFetchWorker` — L134–180. Constructor: `(url, token, station_id, parent, node_runtime, provider_id)`. `run()` currently calls `yt_import.fetch_channel_avatar(self._url, node_runtime=...)` directly — **must be updated to use registry dispatch for 89b**.
- `provider_combo` — L435–437. Editable `QComboBox`; `currentText()` on save at L1658.
- `_on_refresh_avatar_clicked` — L1565–1583. Sets `_force_avatar_refresh = True` in a `try/finally`, then calls `_on_url_timer_timeout()`.
- `_refresh_avatar_btn.setEnabled(is_yt)` — L1275 in `_on_url_text_changed`: currently only enabled for YouTube URLs. **Must add `"twitch.tv" in lower` to this gate.**

#### `paths.twitch_token_path()` / `constants.TWITCH_TOKEN_PATH`
[VERIFIED: `/musicstreamer/paths.py:L50–51`; `/musicstreamer/constants.py:L29–31`]

```python
# paths.py
def twitch_token_path() -> str:
    return os.path.join(_root(), "twitch-token.txt")

# constants.py (PEP 562 __getattr__ shim — delegates to paths)
if name == "TWITCH_TOKEN_PATH":
    return paths.twitch_token_path()
```

Read the token with:
```python
try:
    with open(paths.twitch_token_path()) as fh:
        token = fh.read().strip()
except OSError:
    token = ""
```
This is the exact pattern from `player.py:_twitch_resolve_worker` (L1951–1954). Mirrors WR-01 error backstop.

**Confidence: HIGH** — all symbols verified by direct source read.

---

### Finding #5 (Dialog Dispatch — Twitch vs YouTube Detection) — CONFIRMED, GAP IDENTIFIED

**Question:** How does `edit_station_dialog.py` currently gate the avatar fetch UI, and what must 89b change?

**Current state** (post Phase 89/89.1):

1. `_on_url_text_changed` (L1263–1275): gates `_refresh_avatar_btn.setEnabled(is_yt)` where `is_yt = "youtube.com" in lower or "youtu.be" in lower`. Twitch URLs get `setEnabled(False)`.

2. `_on_url_timer_timeout` (L1277–1337): at L1306, the avatar-fetch branch is gated `if "youtube.com" in lower or "youtu.be" in lower`. Twitch URLs skip the branch entirely.

3. `_AvatarFetchWorker.run()` (L169–180): calls `yt_import.fetch_channel_avatar(self._url, node_runtime=self._node_runtime)` directly — no registry dispatch.

**Three specific changes 89b must make:**

| Location | Current Code | Required Change |
|----------|-------------|-----------------|
| `_on_url_text_changed` L1274–1275 | `is_yt = "youtube.com" in lower or "youtu.be" in lower` then `setEnabled(is_yt)` | Add `is_twitch = "twitch.tv" in lower`; enable Refresh for `is_yt or is_twitch` |
| `_on_url_timer_timeout` L1306 | `if "youtube.com" in lower or "youtu.be" in lower:` | Add `elif "twitch.tv" in lower:` branch (mirroring the YouTube branch: same worker path, same provider_id guard, same reuse-on-open skip) |
| `_AvatarFetchWorker.run()` L172–176 | `data = yt_import.fetch_channel_avatar(self._url, node_runtime=...)` | Dispatch through registry: `fetcher = yt_import.get_avatar_fetcher(provider_key); data = fetcher(self._url)` where `provider_key` is determined from URL type |

**D-02/D-04 provider assignment location:** The login-to-provider derivation and blank-provider assignment fires in `_on_save` (L1648–1686). When a `twitch.tv` URL is detected at save time and `provider_combo.currentText()` is empty, derive the login, call `ensure_provider("Twitch: <login>")`, and write `provider_id` to the station. This is the same flow `_on_save` already uses via `repo.ensure_provider(provider_name)` at L1675 — 89b adds the login-derivation step when the URL is Twitch and the provider field is blank.

**Confidence: HIGH** — verified by direct source read of exact line numbers.

---

### Finding #6 (Threading / Error Contract) — CONFIRMED

**Question:** What is the correct threading and error contract for `twitch_helix.fetch_channel_avatar`?

**Verdict: Plain synchronous `(url: str) -> bytes`, raises on all failure, consistent with `yt_import.fetch_channel_avatar`.**

The `_AvatarFetchWorker.run()` follows the WR-04 contract: it calls the fetcher inside a `try/except Exception`, and on any exception emits `self.finished.emit("", token)` (empty path = failure). The worker thread handles the async isolation. The fetcher itself MUST raise on failure (not return empty bytes or None) so the worker's except clause correctly signals failure to the Qt main thread.

**`yt_import.fetch_channel_avatar` as the template:**
[VERIFIED: `/musicstreamer/yt_import.py:L258`]
```python
with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310  # T-89-06 timeout
    return resp.read()
```
- 10-second timeout (T-89-06 convention)
- Raises on failure (urllib.error.HTTPError, URLError, ValueError, etc.)
- No try/except — the caller (worker) handles exceptions

**`twitch_helix.fetch_channel_avatar` should follow the same shape:**
```python
import urllib.request, urllib.error, json
from musicstreamer import paths

def fetch_channel_avatar(url: str) -> bytes:
    """Fetch Twitch channel avatar. Raises on any failure (worker catches)."""
    login = _parse_login(url)
    if not login:
        raise ValueError(f"Cannot derive Twitch login from: {url!r}")
    token_path = paths.twitch_token_path()
    try:
        with open(token_path) as fh:
            token = fh.read().strip()
    except OSError:
        token = ""
    if not token:
        raise RuntimeError("No Twitch token — log in via Accounts to fetch avatar")
    req = urllib.request.Request(
        f"https://api.twitch.tv/helix/users?login={login}",
        headers={
            "Authorization": f"Bearer {token}",
            "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:   # T-89-06 timeout convention
        body = json.loads(resp.read())
    data = body.get("data", [])
    if not data:
        raise ValueError(f"No Twitch user found for login: {login!r}")
    image_url = data[0]["profile_image_url"]
    with urllib.request.urlopen(image_url, timeout=10) as resp:  # plain CDN, no auth
        return resp.read()
```

**Token scoping note (Pitfall 6 from existing RESEARCH):** Scope `Authorization` to the Helix request only. Do NOT set a global header (contrast with `player.py`'s `session.set_option("twitch-api-header", ...)` which scopes to the streamlink session). The header is set on the individual `urllib.request.Request` object, so scoping is automatic.

**WR-01 backstop:** `twitch_helix.fetch_channel_avatar` should NOT have a top-level `try/except` — let all exceptions propagate. The `_AvatarFetchWorker.run()` at L178–180 already catches them:
```python
except Exception:
    self.finished.emit("", token)  # WR-04: never raise out of run()
```

**Confidence: HIGH** — verified by direct source read of both `yt_import.fetch_channel_avatar` and `_AvatarFetchWorker.run()`.

---

## Architecture Patterns

### System Architecture Diagram

```
Edit Station Dialog
  url_edit (twitch.tv URL)
      |
      | textChanged → _on_url_text_changed
      |   - sets _refresh_avatar_btn.setEnabled(is_yt OR is_twitch)   [NEW]
      |
      | 500ms debounce → _on_url_timer_timeout
      |   - existing YouTube branch (unchanged)
      |   - NEW twitch.tv branch:                                       [NEW]
      |       provider_id None guard → skip + status
      |       reuse-on-open skip (D-07)
      |       launch _AvatarFetchWorker(url, token, station_id, provider_id)
      |
      v
  _AvatarFetchWorker.run() [worker thread]
      |
      | dispatch via get_avatar_fetcher(provider_key)                   [CHANGE]
      v
  twitch_helix.fetch_channel_avatar(url)                                [NEW MODULE]
      |-- _parse_login(url) → login
      |-- read paths.twitch_token_path()
      |-- GET https://api.twitch.tv/helix/users?login=<login>
      |     Headers: Authorization: Bearer <token>
      |               Client-Id: kimne78kx3ncx6brgo4mv6wki5h1ko
      |-- parse data[0].profile_image_url
      |-- GET <CDN URL> (no auth)
      |-- return bytes
      |
      | on error → raises (worker catches)
      |
      v
  _AvatarFetchWorker.finished.emit(rel_path_or_empty, token)
      |
      v
  _on_avatar_fetched [main thread, queued signal]
      |-- stale-token guard
      |-- write provider_avatar_path in-memory
      |-- repo.update_provider_avatar_path(provider_id, rel_path)   [reused]
      |-- update _avatar_preview                                      [reused]
      |-- status text                                                  [reused]

  _on_save [main thread]
      |-- provider_combo blank + twitch.tv URL?                       [NEW check]
      |-- derive login, ensure_provider("Twitch: <login>")            [NEW]
      |-- update_station with derived provider_id                      [reused]

  now_playing_panel.bind_station [main thread, ICY-disabled]
      |-- station.provider_avatar_path set?                           [reused, no change]
      |-- _set_avatar_pixmap_from_path(provider_rel)                  [reused, no change]

  yt_import.py (module load)
      register_avatar_fetcher("twitch", twitch_helix.fetch_channel_avatar)  [NEW line]
```

### Recommended Project Structure
```
musicstreamer/
├── twitch_helix.py              # NEW — fetch_channel_avatar(), _parse_login(), registration
├── yt_import.py                 # CHANGE — add import + register_avatar_fetcher("twitch", ...)
└── ui_qt/
    └── edit_station_dialog.py   # CHANGE — Twitch URL detection gate + worker dispatch + save path
tests/
└── test_twitch_helix.py         # NEW — unit tests for twitch_helix module
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async HTTP off main thread | Custom QThread subclass | `_AvatarFetchWorker` (already exists) | WR-04 contract, stale-token guard, shutdown handling already built |
| Atomic PNG write | Direct `open(path, "wb")` | `assets.write_provider_avatar(provider_id, data)` | `mkstemp + os.replace` atomicity; returns relative path |
| Provider DB upsert | Raw SQL INSERT | `repo.ensure_provider(name)` | INSERT OR IGNORE + SELECT pattern; handles blank name |
| Provider avatar DB persist | `repo.update_station()` (broad) | `repo.update_provider_avatar_path(provider_id, path)` | Non-silent-reset discipline (Pitfall 5) |
| Cover-slot circular avatar render | New QLabel/QPainter path | `now_playing_panel._set_avatar_pixmap_from_path` | Already handles the circular crop + ICY-disabled gate |
| Avatar registry | `dict` in `twitch_helix.py` | `yt_import._AVATAR_FETCHERS` + `register_avatar_fetcher` | Shared registry; `get_avatar_fetcher("twitch")` already the dispatch point |

---

## Common Pitfalls

### Pitfall 1: _AvatarFetchWorker Calling YouTube Fetcher Directly
**What goes wrong:** `_AvatarFetchWorker.run()` currently calls `yt_import.fetch_channel_avatar(self._url, node_runtime=...)` directly. If 89b wires Twitch into the same worker without updating `run()`, the worker calls the YouTube function on a Twitch URL — which passes it to yt-dlp, which fails or returns wrong data.
**Why it happens:** The worker was built YouTube-only in Phase 89 and not updated for the registry in 89.1.
**How to avoid:** Update `_AvatarFetchWorker.run()` to dispatch via `yt_import.get_avatar_fetcher(provider_key)` where `provider_key` is derived from the URL (`"youtube"` for YT, `"twitch"` for twitch.tv). The `node_runtime` arg is YouTube-specific; pass it only when `provider_key == "youtube"` or make it optional.
**Warning signs:** `test_avatar_fetch_worker_emit_shape` will fail or the avatar preview will show a YouTube error for a Twitch URL.

### Pitfall 2: Refresh Button Not Enabled for Twitch URLs
**What goes wrong:** `_on_url_text_changed` (L1274–1275) currently only enables the Refresh button for YouTube. A Twitch URL shows the avatar but the user cannot manually refresh.
**How to avoid:** Extend `is_yt` check to `is_avatar_capable = is_yt or "twitch.tv" in lower` in `_on_url_text_changed`. Apply the same to the label/status logic.
**Warning signs:** `_refresh_avatar_btn.isEnabled()` returns False after pasting a twitch.tv URL.

### Pitfall 3: Provider Assigned Even When Field Is Not Blank (D-04 Violation)
**What goes wrong:** Deriving and assigning `"Twitch: <login>"` unconditionally on save overwrites a manually-set provider name, violating D-04.
**How to avoid:** Gate the derivation: `if not provider_combo.currentText().strip()` before calling `ensure_provider("Twitch: <login>")`. When the provider field has content, use `provider_combo.currentText()` as-is (the existing save path already does this at L1675).
**Warning signs:** A station with `provider_combo` set to `"Live Sports Twitch"` gets silently reassigned to `"Twitch: twitchdev"` on save.

### Pitfall 4: Login Parse Returns Query String or Sub-path
**What goes wrong:** `url.rstrip("/").split("/")[-1]` on `https://www.twitch.tv/login?ref=header` returns `"login?ref=header"`. Sending this to Helix returns HTTP 400 or `data: []`.
**How to avoid:** Apply `.split("?")[0].split("#")[0]` after the path segment extraction. Use the `_parse_login()` helper idiom shown in Finding #2.
**Warning signs:** Helix returns `data: []` or 400 for valid Twitch station URLs.

### Pitfall 5: Token Header Scope Leak (Pitfall 6 from Prior RESEARCH)
**What goes wrong:** Setting a global header on a `urllib` opener or session object causes every subsequent HTTP request in the process to include `Authorization: Bearer <twitch-token>` — including image CDN downloads, iTunes cover art requests, etc.
**How to avoid:** Set the `Authorization` and `Client-Id` headers only on the individual `urllib.request.Request(url, headers={...})` for the Helix call. The CDN image download uses a plain `urllib.request.urlopen(image_url, timeout=10)` with no auth headers.
**Warning signs:** iTunes cover art requests start returning 401; or CDN image download fails with 401.

### Pitfall 6: `_parse_login` Returns Empty String for Non-URL Logins
**What goes wrong:** If the registry ever calls `fetch_channel_avatar("twitchdev")` (bare login, no `/`), `split("/")[-1]` returns `"twitchdev"` correctly but the `"/" in s` guard incorrectly skips the split. Both code paths (URL and bare login) must land on the same lowercase strip.
**How to avoid:** The `_parse_login` helper handles both: if `"/" not in s` after stripping, treat the whole string as the login (apply `.lower()` and strip). This makes the function handle bare logins gracefully in tests or future callers.

### Pitfall 7: `provider_id` None Guard Missing for Twitch Branch
**What goes wrong:** Phase 89.1 CR-01 added a `provider_id is None` guard to the YouTube branch (L1312–1316): a station with no provider cannot have an avatar keyed. If the Twitch branch in `_on_url_timer_timeout` omits this guard, a Twitch URL on a station with no provider writes `None.png` and silently no-ops the DB UPDATE.
**How to avoid:** Apply the same `if self._station.provider_id is None: self._avatar_status.setText(...); return` guard at the top of the Twitch branch — OR structure the guard once before the `if "youtube" / elif "twitch"` branching.

---

## Code Examples

### Helix /users Request
```python
# Source: https://dev.twitch.tv/docs/api/reference/#get-users
import urllib.request, json

req = urllib.request.Request(
    f"https://api.twitch.tv/helix/users?login={login}",
    headers={
        "Authorization": f"Bearer {token}",
        "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
    },
)
with urllib.request.urlopen(req, timeout=10) as resp:
    body = json.loads(resp.read())
profile_image_url = body["data"][0]["profile_image_url"]
```

### Registry Registration (replace stub comment at yt_import.py L266)
```python
# Source: verified at yt_import.py:L262–287
# Replace the stub comment with:
from musicstreamer import twitch_helix as _twitch_helix
register_avatar_fetcher("twitch", _twitch_helix.fetch_channel_avatar)
```

### Worker Dispatch Update
```python
# Source: edit_station_dialog.py _AvatarFetchWorker.run(), current L172–176
# Before (YouTube-only):
data = yt_import.fetch_channel_avatar(self._url, node_runtime=self._node_runtime)

# After (registry dispatch for 89b):
lower = (self._url or "").lower()
if "twitch.tv" in lower:
    fetcher = yt_import.get_avatar_fetcher("twitch")
else:
    fetcher = yt_import.get_avatar_fetcher("youtube")
if fetcher is None:
    raise ValueError(f"No avatar fetcher registered for URL: {self._url!r}")
if "youtube" in lower:
    data = fetcher(self._url, node_runtime=self._node_runtime)
else:
    data = fetcher(self._url)
```

### Token Read Pattern (mirror player.py:1951–1954)
```python
# Source: verified at player.py:L1951–1954
try:
    with open(paths.twitch_token_path()) as fh:
        token = fh.read().strip()
except OSError:
    token = ""
if not token:
    raise RuntimeError("No Twitch token — log in via Accounts to fetch avatar")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-station avatar (`station_id.png`) | Per-provider avatar (`provider_id.png`) | Phase 89.1 | Dedup across sibling stations; Twitch joins same model |
| `write_channel_avatar(station_id, data)` | `write_provider_avatar(provider_id, data)` | Phase 89.1 | 89b uses `write_provider_avatar`; old function deprecated for new callers |
| `Authorization: OAuth <token>` (streamlink GQL) | `Authorization: Bearer <token>` (Helix REST) | Always distinct — D-06 formalizes it | Same token value, different prefix per endpoint type |
| YouTube-only avatar fetch gate in dialog | Per-provider registry dispatch | 89b adds | Twitch plugs in via `register_avatar_fetcher("twitch", ...)` |

**Deprecated/outdated in scope of 89b:**
- `update_channel_avatar_path` — deprecated for new callers as of Phase 89.1; 89b never calls it.
- `Station.channel_avatar_path` — deprecated field; 89b reads `provider_avatar_path` only.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `profile_image_url` CDN URL is publicly accessible without `Authorization` header | Finding #3 | Worker fails on image download; fallback to no-avatar is clean |
| A2 | Helix `login` parameter is case-insensitive (Helix normalizes) | Finding #2 | Login lookup fails if case matters and we lowercase before sending; risk is LOW because lowercasing is the safe direction |
| A3 | Query-string / hash fragment in twitch.tv URL would corrupt the login string | Finding #2 | Parsing `?ref=header` as login → Helix 400 or `data: []`; guarded by `_parse_login` helper |

**Entries A1 and A3 are LOW risk** — A1 because Twitch CDN URLs are universally treated as public, and A3 because the guard is trivial to add. A2 is also LOW risk because lowercasing before comparing is the documented D-03 requirement (stable login key).

---

## Open Questions (RESOLVED)

1. **Should `_AvatarFetchWorker.run()` determine provider by URL-sniffing or carry a provider-key field?**
   - What we know: the constructor receives `url`; the Twitch branch can be detected via `"twitch.tv" in url.lower()`.
   - What's unclear: whether a `provider_key` string param on `_AvatarFetchWorker` would be cleaner for future providers.
   - Recommendation: URL-sniffing in `run()` is sufficient for 89b (only two providers) and requires no constructor change. Future providers (89c brand avatars) may not have a URL-based key at all — defer the `provider_key` param to that phase.

2. **No-token hint phrasing (D-07 discretion)**
   - What we know: failure shows inline `_avatar_status` text; D-07 says "consider a hint pointing to the Accounts dialog."
   - Recommendation: Use `"No Twitch login — connect via Accounts to fetch avatar"` as the no-token status text. This matches the wording of the existing Twitch login affordance and avoids introducing a new UI element.

---

## Environment Availability

Step 2.6: SKIPPED for environment probe — this phase installs no new packages and has no external CLI dependencies beyond `urllib.request` (stdlib) and the already-installed `musicstreamer` runtime. The Helix API is a network dependency; network availability is assumed.

---

## Package Legitimacy Audit

Step skipped — Phase 89b installs **zero new external packages**. `twitch_helix.py` uses only Python stdlib (`urllib.request`, `json`, `os`) and project-internal modules (`paths`, `yt_import`).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/python -m pytest tests/test_twitch_helix.py -x` |
| Full suite command | `.venv/bin/python -m pytest tests/ -x --timeout=30` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ART-AVATAR-04 | `twitch_helix.fetch_channel_avatar` calls Helix `/users` with correct headers | unit | `pytest tests/test_twitch_helix.py::test_fetch_calls_helix_with_bearer_and_client_id -x` | ❌ Wave 0 |
| ART-AVATAR-04 | Empty `data` array → raises (worker falls back to thumbnail) | unit | `pytest tests/test_twitch_helix.py::test_fetch_raises_on_empty_data -x` | ❌ Wave 0 |
| ART-AVATAR-04 | No token file → raises | unit | `pytest tests/test_twitch_helix.py::test_fetch_raises_on_missing_token -x` | ❌ Wave 0 |
| ART-AVATAR-04 | Login parsed from URL (with query string, trailing slash guards) | unit | `pytest tests/test_twitch_helix.py::test_parse_login -x` | ❌ Wave 0 |
| ART-AVATAR-04 | `register_avatar_fetcher("twitch", ...)` registers at module import | unit | `pytest tests/test_twitch_helix.py::test_registry_registers_twitch -x` | ❌ Wave 0 |
| ART-AVATAR-04 | `_AvatarFetchWorker` dispatches Twitch URL to twitch fetcher (not yt fetcher) | unit | `pytest tests/test_edit_station_dialog.py::test_avatar_worker_dispatches_twitch -x` | ❌ Wave 0 |
| ART-AVATAR-04 | Twitch URL enables Refresh button | unit | `pytest tests/test_edit_station_dialog.py::test_twitch_url_enables_refresh_btn -x` | ❌ Wave 0 |
| ART-AVATAR-04 | Blank provider + twitch.tv URL → derive login, ensure_provider on save | unit | `pytest tests/test_edit_station_dialog.py::test_save_derives_provider_for_blank_twitch -x` | ❌ Wave 0 |
| ART-AVATAR-04 | Non-blank provider + twitch.tv URL → provider field respected (D-04) | unit | `pytest tests/test_edit_station_dialog.py::test_save_preserves_manual_provider_for_twitch -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_twitch_helix.py -x`
- **Per wave merge:** `pytest tests/test_twitch_helix.py tests/test_edit_station_dialog.py tests/test_yt_import_library.py -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_twitch_helix.py` — covers ART-AVATAR-04 (all Helix fetch + login parse tests)
- [ ] New test methods in `tests/test_edit_station_dialog.py` — covers ART-AVATAR-04 (dialog dispatch + save path)

*(Framework and conftest already exist — no new infrastructure needed.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No user auth flow — reads existing stored token |
| V3 Session Management | No | No session state; stateless token read |
| V4 Access Control | No | Internal local-file read |
| V5 Input Validation | Yes | Login string derived from user-supplied URL — strip query/hash/path fragments |
| V6 Cryptography | No | Token transmitted over HTTPS (no local crypto) |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Login path traversal (`../etc/passwd`) | Tampering | `provider_id` is a SQLite `int` from PK AUTOINCREMENT (not user-controlled string); file path = `{int}.png` (T-89.1-01 / `write_provider_avatar` docstring confirms). Login string goes into a URL query parameter only — not a filesystem path. |
| Token scope leak (header on wrong request) | Information Disclosure | Set `Authorization` header only on the individual `urllib.request.Request` for the Helix call (Pitfall 5). Do NOT modify a global opener. |
| SSRF via `profile_image_url` | Spoofing | The URL is returned by the Helix API from Twitch's own servers and points to `static-cdn.jtvnw.net`. Low risk in this desktop context. |

---

## Sources

### Primary (HIGH confidence)
- Twitch Developer Docs `/helix/users` endpoint — required headers, response shape, error codes [https://dev.twitch.tv/docs/api/reference/#get-users]
- Twitch Developer Docs authentication validate-tokens — "Bearer prefix in place of OAuth" confirmation [https://dev.twitch.tv/docs/authentication/validate-tokens/]
- `/musicstreamer/yt_import.py` — `_AVATAR_FETCHERS` registry, `register_avatar_fetcher`, `fetch_channel_avatar` template (urlopen timeout pattern)
- `/musicstreamer/assets.py` — `write_provider_avatar(provider_id, data)` exact signature + return value
- `/musicstreamer/repo.py` — `update_provider_avatar_path`, `ensure_provider` exact signatures
- `/musicstreamer/cover_art.py` — `_channel_avatar_lookup` WR-04 contract + `provider_avatar_path` field read
- `/musicstreamer/ui_qt/now_playing_panel.py` — `bind_station` ICY-disabled avatar swap reads `provider_avatar_path`
- `/musicstreamer/ui_qt/edit_station_dialog.py` — `_AvatarFetchWorker`, `_on_url_timer_timeout`, `_on_url_text_changed`, `_on_save` exact line numbers
- `/musicstreamer/player.py` — `_twitch_resolve_worker` token-read + `OAuth` header pattern + login-parse idiom
- `/musicstreamer/paths.py` — `twitch_token_path()`, `channel_avatars_dir()`
- `/musicstreamer/models.py` — `Station` dataclass fields `provider_avatar_path`, `channel_avatar_path`

### Secondary (MEDIUM confidence)
- Streamlink docs (streamlink.github.io) — confirms `auth-token` cookie = 30-char alphanumeric token, `Authorization: OAuth` format

### Tertiary (LOW confidence)
- Community sources confirming `static-cdn.jtvnw.net` URLs are public CDN (no auth on image download)

---

## Metadata

**Confidence breakdown:**
- Token feasibility: HIGH — official Twitch auth docs confirm `Bearer` is valid prefix for OAuth tokens
- Helix /users contract: HIGH — official reference docs
- Symbol verification: HIGH — direct codebase read of all named functions
- Dialog dispatch gap: HIGH — exact line numbers from source
- Profile image characteristics: HIGH (square) / ASSUMED (no auth on CDN) — CDN URL format confirmed, auth-free nature per community pattern
- Login parsing edge cases: HIGH (query string guard is standard defensive practice)

**Research date:** 2026-06-16
**Valid until:** 2026-07-16 (Helix /users is a stable endpoint; avatar registry symbols are codebase-internal)
