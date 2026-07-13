---
phase: 89B-twitch-channel-avatar-fetch
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - musicstreamer/twitch_helix.py
  - musicstreamer/yt_import.py
  - tests/test_twitch_helix.py
autonomous: true
requirements: [ART-AVATAR-04]
must_haves:
  truths:
    - "twitch_helix.fetch_channel_avatar(url) calls GET https://api.twitch.tv/helix/users?login=<login> with Authorization: Bearer <token> and Client-Id: kimne78kx3ncx6brgo4mv6wki5h1ko (D-05, D-06)"
    - "The login is parsed from a twitch.tv URL by taking the last path segment then stripping query (?...) and fragment (#...) and case-folding (D-02, RESEARCH #2/Pitfall 4)"
    - "Missing twitch-token.txt raises before any HTTP call; HTTP 401 and empty data:[] both raise; all failures propagate (worker catches) (D-07, RESEARCH #1/#6)"
    - "No non-square guard is present — Twitch profile images are always square (D-05, RESEARCH #3)"
    - "The token value is never logged and is sent only to api.twitch.tv over https; Authorization is scoped to the Helix Request object only, not the CDN image download (T-89b-01, Pitfall 5)"
    - "register_avatar_fetcher('twitch', twitch_helix.fetch_channel_avatar) is wired so get_avatar_fetcher('twitch') returns the Twitch fetcher at module load (D-05)"
  artifacts:
    - path: "musicstreamer/twitch_helix.py"
      provides: "fetch_channel_avatar(url) -> bytes via Helix /users; login parse helper"
      exports: ["fetch_channel_avatar"]
      min_lines: 40
    - path: "tests/test_twitch_helix.py"
      provides: "Wave 0 unit tests: request shape, login parse, 401/empty-data/missing-token raises, registry registration"
      min_lines: 60
  key_links:
    - from: "musicstreamer/yt_import.py"
      to: "musicstreamer/twitch_helix.fetch_channel_avatar"
      via: "register_avatar_fetcher('twitch', ...)"
      pattern: "register_avatar_fetcher\\(\\\"twitch\\\""
    - from: "musicstreamer/twitch_helix.py"
      to: "musicstreamer/paths.twitch_token_path"
      via: "token read"
      pattern: "twitch_token_path"
---

<objective>
Create `musicstreamer/twitch_helix.py` with `fetch_channel_avatar(url) -> bytes` that fetches a Twitch streamer's `profile_image_url` from the Helix `/users` endpoint using the existing Phase 32 `twitch-token.txt` token, and register it into the Phase 89 per-provider avatar registry so `get_avatar_fetcher("twitch")` resolves it.

Purpose: Delivers the Twitch half of ART-AVATAR-04. The fetcher is a thin, pure-stdlib synchronous function that mirrors `yt_import.fetch_channel_avatar` (raises on all failure; the existing `_AvatarFetchWorker` catches). Storage, persist, and render are reused unchanged from Phases 89/89.1 (NOT touched here).

Output: New `twitch_helix.py` module, one registration line in `yt_import.py`, and Wave 0 unit tests in `tests/test_twitch_helix.py` (network mocked — no live Helix calls).
</objective>

<execution_context>
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.5.0/workflows/execute-plan.md
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.5.0/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/89B-twitch-channel-avatar-fetch/89B-CONTEXT.md
@.planning/phases/89B-twitch-channel-avatar-fetch/89B-RESEARCH.md
@.planning/phases/89B-twitch-channel-avatar-fetch/89B-VALIDATION.md

<interfaces>
<!-- Verified from codebase. Use directly — no exploration needed. -->

From musicstreamer/yt_import.py (L262-287):
- `_AVATAR_FETCHERS: dict[str, Callable[[str], bytes]] = {}`
- `register_avatar_fetcher(provider: str, fetcher: Callable[[str], bytes]) -> None`
- `get_avatar_fetcher(provider: str) -> Optional[Callable[[str], bytes]]`
- L266: stub comment `# rework: register_avatar_fetcher("twitch", twitch_helix.fetch_channel_avatar)`
- L287: `register_avatar_fetcher("youtube", fetch_channel_avatar)` (the existing analog)
- `fetch_channel_avatar` (~L240) is the fetcher-style TEMPLATE: ends with
  `with urllib.request.urlopen(url, timeout=10) as resp: return resp.read()` (T-89-06 timeout convention).

From musicstreamer/paths.py (L50-51):
- `twitch_token_path() -> str` returns `<root>/twitch-token.txt`

From musicstreamer/player.py (L1951-1972) — token-read + login-parse precedent:
- token read: `try: open(paths.twitch_token_path()) as fh: token = fh.read().strip(); except OSError: token = ""`
- login parse: `channel = url.rstrip("/").split("/")[-1]` (NOTE: this does NOT strip query/fragment — 89b must add `.split("?")[0].split("#")[0]`)
- header framing for GQL is `Authorization: OAuth <token>` — Helix needs `Bearer` + `Client-Id` instead (same secret, different transport — D-06)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Wave 0 — failing unit tests for twitch_helix</name>
  <files>tests/test_twitch_helix.py</files>
  <read_first>
    - musicstreamer/yt_import.py (L240-287) — fetch_channel_avatar template + registry functions
    - musicstreamer/player.py (L1951-1972) — token-read + login-parse precedent
    - tests/ — find an existing test that monkeypatches urllib.request.urlopen / open to mirror the project's no-live-network mocking convention (grep `urlopen` and `monkeypatch` under tests/); reuse that fixture style
    - .planning/phases/89B-twitch-channel-avatar-fetch/89B-VALIDATION.md — exact test names
  </read_first>
  <behavior>
    Write these tests RED (twitch_helix does not exist yet). Mock the network — no live Helix calls.
    - test_parse_login: `https://www.twitch.tv/twitchdev` → "twitchdev"; trailing slash `.../twitchdev/` → "twitchdev"; query string `.../twitchdev?ref=header` → "twitchdev"; fragment `.../twitchdev#x` → "twitchdev"; mixed case `.../TwitchDev` → "twitchdev"; bare login "twitchdev" (no slash) → "twitchdev".
    - test_fetch_calls_helix_with_bearer_and_client_id: monkeypatch the token read to a known value and urlopen to capture the Request; assert URL is `https://api.twitch.tv/helix/users?login=twitchdev`, header `Authorization` == `Bearer <token>`, header `Client-Id` == `kimne78kx3ncx6brgo4mv6wki5h1ko`; assert the returned bytes equal the mocked CDN image bytes.
    - test_fetch_raises_on_missing_token: monkeypatch token read to raise OSError (or return "") → fetch_channel_avatar raises BEFORE any urlopen (assert urlopen not called).
    - test_fetch_raises_on_empty_data: Helix returns 200 with `{"data": []}` → raises.
    - test_fetch_raises_on_401: Helix urlopen raises urllib.error.HTTPError(code=401) → propagates (assert raises).
    - test_no_square_guard: confirm source has no `width != height` / "not square" reject — use a source-grep drift-guard (read twitch_helix.py source, assert "not square" not present and "profile_image_url" present).
    - test_token_never_logged: source-grep drift-guard — assert no `print(`/`logging`/`logger` line in twitch_helix.py emits the token variable (scan that no log/print call includes the token identifier).
    - test_registry_registers_twitch: import yt_import; assert `yt_import.get_avatar_fetcher("twitch") is twitch_helix.fetch_channel_avatar`.
  </behavior>
  <action>
    Create tests/test_twitch_helix.py. Run with `.venv/bin/python` (system python3 lacks PySide6.QtWidgets — false failures). Mock network by monkeypatching `urllib.request.urlopen` (return an object with a `.read()` returning the fixture-locked Helix JSON bytes for the /users call, and the image bytes for the CDN call — distinguish by inspecting the Request URL or call order) and monkeypatch the token read (patch `builtins.open` for the token path or `paths.twitch_token_path`). Fixture-lock the Helix 200 response body to the shape in RESEARCH Finding #1 (data[0].profile_image_url). For the 401 case, raise `urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)`. Prefer source-grep drift-guards for the no-square-guard and token-not-logged assertions (project convention for ordering/precedence invariants). Do NOT hit the real network. These tests MUST fail now (module absent) and pass after Task 2.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_twitch_helix.py -q 2>&1 | grep -E "error|ModuleNotFoundError|failed" </automated>
  </verify>
  <acceptance_criteria>
    - tests/test_twitch_helix.py exists with test functions named: test_parse_login, test_fetch_calls_helix_with_bearer_and_client_id, test_fetch_raises_on_missing_token, test_fetch_raises_on_empty_data, test_fetch_raises_on_401, test_no_square_guard, test_token_never_logged, test_registry_registers_twitch.
    - `.venv/bin/python -m pytest tests/test_twitch_helix.py -q` collects the tests and they FAIL/ERROR (RED — module not yet created). No live network is contacted (urlopen is monkeypatched in every network test).
    - The Helix 200 fixture body matches RESEARCH Finding #1 (contains `data[0].profile_image_url`).
  </acceptance_criteria>
  <done>The eight named tests exist and run RED against the absent module; no test performs a live network call.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement twitch_helix.fetch_channel_avatar + register fetcher</name>
  <files>musicstreamer/twitch_helix.py, musicstreamer/yt_import.py</files>
  <read_first>
    - musicstreamer/yt_import.py (L240-287) — fetch_channel_avatar template (urlopen timeout=10, raises on failure) + L266 stub + L287 youtube registration line
    - musicstreamer/player.py (L1951-1972) — token read + login parse precedent
    - musicstreamer/paths.py (L50-51) — twitch_token_path()
    - tests/test_twitch_helix.py — the contract from Task 1
    - .claude/skills/spike-findings-musicstreamer/SKILL.md — Twitch token / threading notes
  </read_first>
  <action>
    Create musicstreamer/twitch_helix.py exporting `fetch_channel_avatar(url: str) -> bytes` (matches the registry `Callable[[str], bytes]` shape — accepts a URL, parses the login internally). Add a private `_parse_login(url_or_login)` helper: take `s = url_or_login.rstrip("/")`; if `/` in s take `s.split("/")[-1]`; then `s.split("?")[0].split("#")[0].strip().lower()` (handles trailing slash, query string, fragment, mixed case, and bare logins — RESEARCH #2 / Pitfalls 4 and 6). fetch_channel_avatar: derive the login, raise ValueError if empty; read the token via `paths.twitch_token_path()` using the player.py try/open/except-OSError idiom, raise RuntimeError (message like "No Twitch login — connect via Accounts to fetch avatar") if the token is empty/absent BEFORE any HTTP call; build `urllib.request.Request(f"https://api.twitch.tv/helix/users?login={login}", headers={"Authorization": f"Bearer {token}", "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko"})`; `urlopen(req, timeout=10)`, `json.loads` the body; if `data` is empty raise ValueError; read `data[0]["profile_image_url"]`; `urlopen(image_url, timeout=10)` with NO auth headers (plain CDN) and return `resp.read()`. Use `# noqa: S310` on the urlopen calls mirroring yt_import. Do NOT add a non-square guard (Twitch images are always square — D-05). Do NOT add a top-level try/except — let exceptions propagate to the worker (WR-01/WR-04). NEVER log/print the token value, and set the Authorization header ONLY on the Helix Request (not the CDN download) — token scope (T-89b-01, Pitfall 5). NO fenced code in the module beyond what the contract requires.
    Then in musicstreamer/yt_import.py, replace the L266 stub comment by registering the Twitch fetcher: add a module-load `register_avatar_fetcher("twitch", twitch_helix.fetch_channel_avatar)` call, importing twitch_helix in a way that avoids an import cycle. Because twitch_helix imports `paths` (not yt_import), there is no cycle from twitch_helix→yt_import; the safe location is yt_import importing twitch_helix at the registration site (near L287, after `_AVATAR_FETCHERS` and the youtube registration are defined). Use a late/local import inside a small registration block (e.g. `from musicstreamer import twitch_helix as _twitch_helix` immediately before the register call) so twitch_helix is imported only after yt_import's registry functions exist — documenting WHY (cycle-avoidance) in a one-line comment.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_twitch_helix.py -q</automated>
  </verify>
  <acceptance_criteria>
    - musicstreamer/twitch_helix.py exists and exports `fetch_channel_avatar`; source contains the literal `kimne78kx3ncx6brgo4mv6wki5h1ko`, `Authorization`, `Bearer`, `Client-Id`, `https://api.twitch.tv/helix/users?login=`, and `profile_image_url`.
    - Source contains NO `not square` / `width != height` guard and NO log/print statement that includes the token variable.
    - musicstreamer/yt_import.py contains `register_avatar_fetcher("twitch"` and imports twitch_helix at a location that does not create an import cycle (`.venv/bin/python -c "import musicstreamer.yt_import"` succeeds).
    - All eight tests in tests/test_twitch_helix.py PASS (GREEN): `.venv/bin/python -m pytest tests/test_twitch_helix.py -q` exits 0.
    - `.venv/bin/python -c "import musicstreamer.yt_import as y, musicstreamer.twitch_helix as t; assert y.get_avatar_fetcher('twitch') is t.fetch_channel_avatar"` exits 0.
  </acceptance_criteria>
  <done>fetch_channel_avatar is implemented to the test contract, the Twitch fetcher is registered without an import cycle, and all Task 1 tests pass.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| user URL input → login string | The twitch.tv URL is user-typed; the derived login is placed into a Helix query parameter |
| local token file → api.twitch.tv | The Phase 32 `auth-token` cookie (sensitive credential) is read from disk and sent over the network |
| Helix-returned image URL → CDN fetch | `profile_image_url` is returned by Twitch and fetched from static-cdn.jtvnw.net |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-89b-01 | Information Disclosure | twitch_helix.fetch_channel_avatar token handling | mitigate | Read token only from `paths.twitch_token_path()`; send it only to `https://api.twitch.tv` as the `Authorization: Bearer` header on the Helix Request object; NEVER log/print the token value; do NOT attach the header to the CDN image download (scope leak — Pitfall 5). Source-grep drift-guard test asserts no log/print of the token var. |
| T-89b-02 | Tampering / Spoofing (SSRF) | _parse_login + Helix URL construction | mitigate | The Helix host is a fixed literal (`api.twitch.tv`) — login is a query-param value only, never a host or path segment. `_parse_login` strips `?`, `#`, and path segments before use, so a crafted URL cannot redirect the request. Login is never used as a filesystem path (the avatar file is keyed on the integer provider_id, not the login — handled in Plan 02). |
| T-89b-SC | Tampering | npm/pip/cargo installs | accept | No new packages installed this phase (RESEARCH Package Legitimacy Audit: stdlib only — urllib, json, os). No install task, no legitimacy gate required. |
</threat_model>

<verification>
- `.venv/bin/python -m pytest tests/test_twitch_helix.py -q` is green.
- `.venv/bin/python -c "import musicstreamer.yt_import"` succeeds (no import cycle).
- `get_avatar_fetcher("twitch")` returns `twitch_helix.fetch_channel_avatar`.
- Source-grep: twitch_helix.py contains the Helix URL, Bearer, Client-Id literal, and no square guard; no token logging.
</verification>

<success_criteria>
- ART-AVATAR-04 (fetch half): `twitch_helix.fetch_channel_avatar` calls Helix `/users` with Bearer + Client-Id and returns the profile image bytes; all failure modes raise.
- The fetcher is registered into the per-provider registry at module load.
- Token is never logged and scoped to the Helix request (T-89b-01); login is query-param-only with stripping (T-89b-02).
</success_criteria>

<output>
Create `.planning/phases/89B-twitch-channel-avatar-fetch/89B-01-SUMMARY.md` when done.
</output>
