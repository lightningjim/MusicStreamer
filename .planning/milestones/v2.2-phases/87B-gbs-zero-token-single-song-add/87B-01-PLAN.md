---
phase: 87B-gbs-zero-token-single-song-add
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - musicstreamer/gbs_api.py
  - tests/test_gbs_api.py
  - tests/test_gbs_zero_token_drift_guard.py
  - tests/fixtures/gbs_zero_token/add_redirect_response_48tokens.txt
  - tests/fixtures/gbs_zero_token/add_redirect_zero_token_PLACEHOLDER.txt
  - tests/fixtures/gbs_zero_token/MANIFEST.md
autonomous: true
requirements:
  - GBS-TOKEN-02
  - GBS-TOKEN-03
  - GBS-TOKEN-05

user_setup: []

must_haves:
  truths:
    - "D-01: zero-token POST spec does not exist / cannot be captured at 48 tokens — no live capture is attempted in this plan"
    - "D-02: add_song_zero_token() is a thin wrapper over submit() (provisional /add reuse) + a no-PII capture hook; HTTP logic is NOT duplicated"
    - "D-03: GBS-TOKEN-05 is relaxed — the observable /add shape is fixture-locked now; the real tokens==0 fixture is captured on first live use (placeholder reserved)"
    - "T-87B-01: the capture hook NEVER writes cookies / sessionid / csrftoken / Authorization / raw Set-Cookie values — only method+path+songid and the decoded message length/category"
    - "GBS-TOKEN-03: gbs_api.add_song_zero_token(songid, cookies) exists, calls submit(), and propagates GbsAuthExpiredError unchanged"
    - "GBS-TOKEN-02: no 'token' word appears in any string literal inside the add_song_zero_token() function body (identifier name is allowed)"
  artifacts:
    - path: "musicstreamer/gbs_api.py"
      provides: "add_song_zero_token() wrapper + _capture_add_shape() no-PII hook"
      contains: "def add_song_zero_token("
    - path: "tests/test_gbs_zero_token_drift_guard.py"
      provides: "GBS-TOKEN-02 source-grep drift-guard"
      contains: "def test_add_song_zero_token_has_no_token_wording"
    - path: "tests/fixtures/gbs_zero_token/MANIFEST.md"
      provides: "Provisional fixture provenance + capture-on-use placeholder row"
      contains: "resolves_phase"
  key_links:
    - from: "musicstreamer/gbs_api.py::add_song_zero_token"
      to: "musicstreamer/gbs_api.py::submit"
      via: "direct call, no HTTP duplication"
      pattern: "result = submit\\(songid, cookies\\)"
    - from: "musicstreamer/gbs_api.py::_capture_add_shape"
      to: "logging.getLogger('musicstreamer.gbs_api')"
      via: "_log.warning structured no-PII line"
      pattern: "_log\\.warning\\("
---

<objective>
Add the named provisional song-add path `gbs_api.add_song_zero_token()` — a thin wrapper over the existing `submit()` (GET `/add/<songid>`) plus a no-PII capture hook that fixture-locks the real `tokens==0` request/response on first live use. Create the provisional fixture directory, the GBS-TOKEN-02 "no token word" source-grep drift-guard, and unit tests.

Purpose: Satisfy GBS-TOKEN-03 (named add function) and GBS-TOKEN-05 (provisional fixture + capture-on-use) without duplicating HTTP logic and without leaking session secrets (T-87B-01). This is the backend that the Wave-2 UI plan wires into the existing GBSSearchDialog submit worker.
Output: `add_song_zero_token()` + `_capture_add_shape()` in `gbs_api.py`; `tests/fixtures/gbs_zero_token/` (provisional fixture + placeholder + MANIFEST); `tests/test_gbs_zero_token_drift_guard.py`; new unit tests in `tests/test_gbs_api.py`.
</objective>

<execution_context>
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.5.0/workflows/execute-plan.md
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.5.0/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/87B-gbs-zero-token-single-song-add/87B-CONTEXT.md
@.planning/phases/87B-gbs-zero-token-single-song-add/87B-RESEARCH.md
@.planning/phases/87B-gbs-zero-token-single-song-add/87B-PATTERNS.md

<interfaces>
<!-- Extracted from codebase. Use directly — no exploration. -->

From musicstreamer/gbs_api.py (the analog this plan extends):
- `_log = logging.getLogger(__name__)`  (__name__ == "musicstreamer.gbs_api")
- `class GbsApiError(Exception)` / `class GbsAuthExpiredError(GbsApiError)`  (lines 82-87)
- `def submit(songid: int, cookies: http.cookiejar.MozillaCookieJar) -> str`  (line 1129)
    - builds `url = f"{GBS_BASE}/add/{int(songid)}"`, calls `_open_no_redirect(...)`,
      raises GbsAuthExpiredError on 302→/accounts/login/, decodes the `messages=` Set-Cookie
      via `_decode_django_messages(...)`, returns "; ".join(msgs) or "" (no messages = success).

From tests/test_gbs_api.py (the test analogs to copy):
- `test_submit_success_decodes_messages(gbs_fixtures_dir, fake_cookies_jar, monkeypatch)` (line 297)
    - monkeypatches `gbs_api._open_no_redirect` with a `fake_open` that returns a MagicMock
      whose `.headers.get_all` yields the `set-cookie:` lines from the fixture text.
- `test_submit_auth_expired(fake_cookies_jar, monkeypatch)` (line 325)
    - fake_open returns headers.get -> "/accounts/login/?next=/add/123"; expects GbsAuthExpiredError.

From tests/test_gbs_marquee_drift_guard.py (the drift-guard template):
- module-level `SRC = Path(__file__).resolve().parent.parent / "musicstreamer" / "..."`
- `def _strip_comments(text: str) -> str` — drops `#`-tail from each line.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Provisional fixtures + GBS-TOKEN-02 drift-guard (Wave 0 scaffolding)</name>
  <files>tests/fixtures/gbs_zero_token/add_redirect_response_48tokens.txt, tests/fixtures/gbs_zero_token/add_redirect_zero_token_PLACEHOLDER.txt, tests/fixtures/gbs_zero_token/MANIFEST.md, tests/test_gbs_zero_token_drift_guard.py</files>
  <read_first>
    - tests/fixtures/gbs/add_redirect_response.txt (source content to copy verbatim)
    - tests/fixtures/gbs_marquee/MANIFEST.md (MANIFEST schema to mirror)
    - tests/test_gbs_marquee_drift_guard.py (drift-guard template: _strip_comments + banned-pattern loop)
    - 87B-PATTERNS.md §"tests/fixtures/gbs_zero_token/" and §"tests/test_gbs_zero_token_drift_guard.py"
  </read_first>
  <behavior>
    - test_add_song_zero_token_has_no_token_wording: extracts the `add_song_zero_token` function body from gbs_api.py (regex `def add_song_zero_token\b.*?(?=\ndef |\Z)` on comment-stripped source) and asserts NO double- or single-quoted string literal in that body contains the bare word `token` (case-insensitive). The function-name identifier is allowed. This test FAILS now (function absent → assertion message "must exist") and turns GREEN after Task 2.
    - Fixture existence: `tests/fixtures/gbs_zero_token/add_redirect_response_48tokens.txt` exists and contains a `set-cookie: messages=` line; the unit tests in Task 3 read it.
  </behavior>
  <action>
    Create `tests/fixtures/gbs_zero_token/` with three files. (1) `add_redirect_response_48tokens.txt` — copy the content of `tests/fixtures/gbs/add_redirect_response.txt` VERBATIM (HTTP/2 302 + `location: /playlist` + the `set-cookie: messages=...` line). (2) `add_redirect_zero_token_PLACEHOLDER.txt` — a single comment line reserving the slot for first-live-use capture (no real data — D-01: cannot capture at 48 tokens). (3) `MANIFEST.md` — mirror the `tests/fixtures/gbs_marquee/MANIFEST.md` column schema; add a row for the 48-token file (capture_date 2026-06-18, capture_method cookies, provenance real-captured, notes cite "observable /add shape; provisional for the zero-token contract per 87B-CONTEXT D-02") and a placeholder row for the PLACEHOLDER file (provenance pending-capture, notes "resolves_phase: 87B — populated on first live tokens==0 add per D-03"). Do NOT put the word that names the affordance economics (forbidden by GBS-TOKEN-02) in any fixture string that the drift-guard scopes; the MANIFEST is outside the gbs_api.py drift-guard scope and may reference the contract by its requirement IDs.
    Create `tests/test_gbs_zero_token_drift_guard.py` by cloning the structure of `tests/test_gbs_marquee_drift_guard.py`: module-level `GBS_API_SRC = Path(__file__).resolve().parent.parent / "musicstreamer" / "gbs_api.py"`, copy `_strip_comments()` verbatim, and add `test_add_song_zero_token_has_no_token_wording()` per the behavior block (regex-extract the function body from the comment-stripped source, then assert neither `r'"[^"]*\btoken\b[^"]*"'` nor `r"'[^']*\btoken\b[^']*'"` matches, case-insensitive). The first assertion (`assert m, "add_song_zero_token() must exist ..."`) doubles as the GBS-TOKEN-03 existence guard.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_gbs_zero_token_drift_guard.py -x 2>&1 | tail -5; test -f tests/fixtures/gbs_zero_token/add_redirect_response_48tokens.txt && grep -q "set-cookie: messages=" tests/fixtures/gbs_zero_token/add_redirect_response_48tokens.txt && echo FIXTURE_OK</automated>
  </verify>
  <acceptance_criteria>
    - `tests/fixtures/gbs_zero_token/add_redirect_response_48tokens.txt` exists and contains `set-cookie: messages=`.
    - `tests/fixtures/gbs_zero_token/MANIFEST.md` contains the string `resolves_phase` and a `pending-capture` row for the PLACEHOLDER file.
    - `tests/test_gbs_zero_token_drift_guard.py` defines `def test_add_song_zero_token_has_no_token_wording`.
    - Before Task 2: the drift-guard test FAILS with the "must exist" assertion (RED — function absent). This proves the guard is wired, not vacuous.
  </acceptance_criteria>
  <done>Fixture directory + MANIFEST + placeholder created; drift-guard test file exists and is RED pending the function (GBS-TOKEN-02/03/05 scaffolding in place).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: add_song_zero_token() wrapper + _capture_add_shape() no-PII hook</name>
  <files>musicstreamer/gbs_api.py</files>
  <read_first>
    - musicstreamer/gbs_api.py lines 1-45 (module docstring public-API list + `_log` logger) and lines 82-87 (exception types) and lines 1129-1153 (`submit()` analog + the insertion point after it)
    - musicstreamer/gbs_api.py lines 227-230 (the existing structured no-PII `_log.warning` shape in `_open_with_cookies`)
    - 87B-RESEARCH.md §"Pattern 1" and §Security Domain "Known Threat Patterns" (PII-in-capture-hook row)
    - 87B-CONTEXT.md D-02 (wrapper + hook), and 87-CONTEXT.md D-18 logging discipline (structured key=value, no cookie/session values)
  </read_first>
  <behavior>
    - add_song_zero_token(songid, cookies) returns the same string submit() returns (decoded messages text, or "" on success-with-no-message).
    - add_song_zero_token() propagates GbsAuthExpiredError unchanged when submit() raises it (does NOT catch it — the hook does not fire on the auth-expiry path).
    - _capture_add_shape() emits exactly one `_log.warning(...)` whose format string + positional args contain ONLY: the endpoint path `/add/<int songid>`, the message length (int), and a coarse message category (empty/error/success). It contains NONE of: the `cookies` object, `sessionid`, `csrftoken`, `Authorization`, or any raw `Set-Cookie` / `messages=` value (T-87B-01).
  </behavior>
  <action>
    Insert `add_song_zero_token(songid: int, cookies: http.cookiejar.MozillaCookieJar) -> str` and the private `_capture_add_shape(songid: int, message: str) -> None` into `gbs_api.py` immediately after `submit()` (after line 1153, before the next module section comment), per 87B-PATTERNS.md §gbs_api Pattern 1. `add_song_zero_token` body is exactly three statements: `result = submit(songid, cookies)`; `_capture_add_shape(songid=songid, message=result)`; `return result`. Do NOT reference `_open_no_redirect`, `_decode_django_messages`, `GBS_BASE`, or `_TIMEOUT_WRITE` inside the wrapper (Pitfall 4 — no HTTP duplication). `_capture_add_shape` emits one `_log.warning("gbs.add.zero_token_capture endpoint=/add/%s message_len=%d message_category=%s", int(songid), len(message), <category>)` where `<category>` is `"empty"` if not message else `"error"` if `"not enough" in message.lower()` else `"success"`. Add `add_song_zero_token` to the module docstring's public-API list. CRITICAL (GBS-TOKEN-02): write both docstrings to describe the HTTP contract + provisional status using requirement IDs (D-02 / GBS-TOKEN-03) — NEVER write the bare affordance-economics word as a string literal inside either function body, or the Task-1 drift-guard fails (Pitfall 6). The identifier `add_song_zero_token` itself is fine; quoted strings are not. Do not log any PII (T-87B-01).
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_gbs_zero_token_drift_guard.py -x 2>&1 | tail -5</automated>
  </verify>
  <acceptance_criteria>
    - `gbs_api.py` contains `def add_song_zero_token(` and `def _capture_add_shape(`.
    - `grep -A4 "def add_song_zero_token" musicstreamer/gbs_api.py` shows `result = submit(songid, cookies)` and `return result` and no `_open_no_redirect` / `_decode_django_messages`.
    - `.venv/bin/python -m pytest tests/test_gbs_zero_token_drift_guard.py -x` exits 0 (drift-guard now GREEN — function exists AND no token-word string literal in its body).
    - `.venv/bin/python -c "import musicstreamer.gbs_api as g; assert callable(g.add_song_zero_token)"` exits 0.
  </acceptance_criteria>
  <done>add_song_zero_token() wraps submit() with no HTTP duplication; _capture_add_shape() logs a structured no-PII line; GBS-TOKEN-02 drift-guard is GREEN; GBS-TOKEN-03 named function exists.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Unit tests — wrapper reuses submit, propagates auth-expiry, capture hook is PII-free</name>
  <files>tests/test_gbs_api.py</files>
  <read_first>
    - tests/test_gbs_api.py lines 1-40 (import block + named-import list) and lines 297-338 (`test_submit_success_decodes_messages` + `test_submit_auth_expired` — the `fake_open` MagicMock shape to copy)
    - tests/fixtures/gbs_zero_token/add_redirect_response_48tokens.txt (created in Task 1)
    - 87B-PATTERNS.md §"tests/test_gbs_api.py" (the three test shapes, incl. test_capture_hook_no_pii)
    - 87B-RESEARCH.md §"Research Target 7" (test conventions) and §Security Domain
  </read_first>
  <behavior>
    - test_add_song_zero_token_calls_submit: with `_open_no_redirect` monkeypatched to return the 48-token fixture's 302+messages cookie, `add_song_zero_token(88135, fake_cookies_jar)` returns a non-empty string containing "added" or "track" (case-insensitive) — proving it routed through submit()'s decode path.
    - test_add_song_zero_token_raises_auth_expired: with `_open_no_redirect` returning a 302 → `/accounts/login/`, `add_song_zero_token(123, fake_cookies_jar)` raises `GbsAuthExpiredError` (propagated from submit()).
    - test_capture_hook_no_pii: with `_log.warning` captured, a successful `add_song_zero_token(...)` emits >=1 log call, and across all captured (msg, args) the joined text contains none of `sessionid`, `csrftoken`, `Set-Cookie`, `Authorization` (T-87B-01).
    - test_zero_token_fixture_exists: the provisional fixture path is loadable and non-empty (GBS-TOKEN-05).
  </behavior>
  <action>
    Add four tests to `tests/test_gbs_api.py`. Add `add_song_zero_token` to the named-import list alongside `submit`. Add a `gbs_zero_token_fixtures_dir` path fixture (inline or via the existing conftest pattern) pointing at `tests/fixtures/gbs_zero_token/`, mirroring the existing `gbs_fixtures_dir`. Copy the `fake_open` MagicMock builder from `test_submit_success_decodes_messages` verbatim and reuse it. (1) `test_add_song_zero_token_calls_submit` — monkeypatch `gbs_api._open_no_redirect` with the 48-token fixture-driven `fake_open`, call `gbs_api.add_song_zero_token(88135, fake_cookies_jar)`, assert non-empty and "added"/"track" in result.lower(). (2) `test_add_song_zero_token_raises_auth_expired` — copy `test_submit_auth_expired`'s login-redirect `fake_open`, assert `pytest.raises(GbsAuthExpiredError)` around `gbs_api.add_song_zero_token(123, fake_cookies_jar)`. (3) `test_capture_hook_no_pii` — monkeypatch `gbs_api._log.warning` to append `(msg, args)` to a list, run a successful add via the 48-token fake_open, assert the list is non-empty and that for every captured entry the joined `msg + " ".join(map(str,args))` contains none of `"sessionid"`, `"csrftoken"`, `"Set-Cookie"`, `"Authorization"`. (4) `test_zero_token_fixture_exists` — assert the 48-token fixture file exists and is non-empty. Use `.venv/bin/python` for all runs (system python3 lacks PySide6).
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_gbs_api.py -k zero_token -x 2>&1 | tail -8</automated>
  </verify>
  <acceptance_criteria>
    - `.venv/bin/python -m pytest tests/test_gbs_api.py -k zero_token -x` exits 0 (all four new tests pass).
    - `.venv/bin/python -m pytest tests/test_gbs_api.py -k zero_token_capture -x` exits 0 (the no-PII test specifically passes — T-87B-01).
    - The auth-expiry test proves `add_song_zero_token` does not swallow `GbsAuthExpiredError`.
    - No regression: `.venv/bin/python -m pytest tests/test_gbs_api.py -x` exits 0.
  </acceptance_criteria>
  <done>Four unit tests green: wrapper reuses submit() decode path, propagates auth-expiry, the capture hook writes no PII (T-87B-01), and the provisional fixture is present (GBS-TOKEN-05).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MusicStreamer → gbs.fm `/add/<songid>` | Authenticated GET carrying Phase 76 session cookies (sessionid/csrftoken) crosses to the GBS server. |
| gbs_api → local logs (buffer_log / stderr) | The capture hook writes diagnostic text to a local sink that may be shared/exported. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-87B-01 | Information Disclosure | `_capture_add_shape()` no-PII capture hook | mitigate | Hook logs ONLY `endpoint=/add/<int songid>`, `message_len`, `message_category`. NEVER logs `cookies`, `sessionid`, `csrftoken`, `Authorization`, or raw `Set-Cookie`/`messages=` values. Enforced by `test_capture_hook_no_pii` (Task 3). Gated HIGH — blocks on failure. |
| T-87B-02 | Tampering | songid in `/add/<songid>` URL | accept | Already mitigated upstream: `submit()` casts `f"{GBS_BASE}/add/{int(songid)}"`; non-int songid raises before any request. No new surface. |
| T-87B-03 | Spoofing/Repudiation | session-expiry on the add path | accept | `add_song_zero_token()` propagates `GbsAuthExpiredError` unchanged; surfaced via the existing dialog path in Wave 2. No new auth surface. |
| T-87B-SC | Tampering | npm/pip/cargo installs | accept | No package installs in this plan (pure stdlib + existing imports per RESEARCH §"No new dependencies"). N/A. |
</threat_model>

<verification>
- `.venv/bin/python -m pytest tests/test_gbs_api.py tests/test_gbs_zero_token_drift_guard.py -x` is green.
- `add_song_zero_token` importable and callable; drift-guard confirms no token-word string literal in its body.
- Capture hook proven PII-free by `test_capture_hook_no_pii`.
</verification>

<success_criteria>
- GBS-TOKEN-03: `gbs_api.add_song_zero_token()` exists, wraps `submit()`, propagates `GbsAuthExpiredError`.
- GBS-TOKEN-05: provisional fixture committed under `tests/fixtures/gbs_zero_token/` with capture-on-use placeholder + MANIFEST.
- GBS-TOKEN-02: drift-guard green — no token-word string literal in `add_song_zero_token()`.
- T-87B-01: capture hook writes no cookie/session values (unit-test-enforced).
</success_criteria>

<output>
Create `.planning/phases/87B-gbs-zero-token-single-song-add/87B-01-SUMMARY.md` when done.
</output>
</content>
</invoke>
