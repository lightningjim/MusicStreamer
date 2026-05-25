---
phase: 60-gbs-fm-integration
plan: 08
type: execute
wave: 5
depends_on: []
files_modified:
  - musicstreamer/gbs_api.py
  - tests/test_gbs_api.py
autonomous: true
gap_closure: true
requirements: [GBS-01a, GBS-01e]
tags: [phase60, gap-closure, urllib, redirect-handler, django-messages, idempotent-import]
revision: 2
revision_notes: "Iteration-2 plan-check fixes: (1) added Task 1.5 to update existing test_import_idempotent for new (0,0) semantics, (2) updated success_criteria test count, (3) pinned patching layer for _NoRedirect test to urllib.request.AbstractHTTPHandler.do_open with concrete code sketch. Wave/depends_on unchanged (no overlap with 60-09)."

must_haves:
  truths:
    - "submit() returns the decoded Django messages text on a 302 (success path) instead of raising urllib.error.HTTPError(302)"
    - "submit() still raises GbsAuthExpiredError when the 302 Location targets /accounts/login/"
    - "_open_no_redirect returns a response object whose .headers exposes both Location and all Set-Cookie headers"
    - "On a redundant Add GBS.FM (no field-level change to any of the 6 streams), import_station returns (0, 0) so MainWindow shows 'GBS.FM import: no changes' instead of 'GBS.FM streams updated'"
    - "On a real refresh (any stream field differs from stored values), import_station still returns (0, 1) so the existing 'GBS.FM streams updated' toast still fires"
    - "On a fresh insert, import_station still returns (1, 0) so 'GBS.FM added' fires"
  artifacts:
    - path: "musicstreamer/gbs_api.py"
      provides: "Fixed _NoRedirect override + dirty-checking import_station"
      contains: "http_error_302"
    - path: "tests/test_gbs_api.py"
      provides: "Regression tests for 302 capture, redirect-as-error path, dirty-check no-op"
      contains: "test_open_no_redirect_returns_response"
  key_links:
    - from: "musicstreamer/gbs_api.py::submit"
      to: "_open_no_redirect (returns response, never raises HTTPError(302))"
      via: "opener.open via patched _NoRedirect handler"
      pattern: "http_error_302"
    - from: "musicstreamer/gbs_api.py::import_station"
      to: "repo.list_streams + field-level comparison"
      via: "dirty-check before counting as updated"
      pattern: "inserted, updated = 0, 0"
---

<objective>
Close UAT issue T13 (Test 13: "Submit Failed: HTTP Error 302: Found" toast) and T6 (Test 6: idempotent re-import always toasts "streams updated", never "no changes"). Both bugs trace to the same architectural pattern — a server response is generated but never inspected. Fix the urllib redirect handler so the 302 envelope is returned to caller, then add field-level dirty-checking to import_station.

Purpose: User can submit songs successfully (no false-positive HTTP-error toast) and gets correct feedback on idempotent re-import.

Output: Patched `gbs_api.py` (_NoRedirect override + import_station dirty-check) + regression tests in `tests/test_gbs_api.py` covering both bugs.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/60-gbs-fm-integration/60-CONTEXT.md
@.planning/phases/60-gbs-fm-integration/60-DIAGNOSIS-302-messages.md
@.planning/phases/60-gbs-fm-integration/60-UAT.md
@.planning/phases/60-gbs-fm-integration/60-02-api-client-SUMMARY.md
@./CLAUDE.md
@musicstreamer/gbs_api.py
@tests/test_gbs_api.py
@tests/conftest.py
@tests/fixtures/gbs/add_redirect_response.txt
@tests/fixtures/gbs/messages_cookie_track_added.txt
@tests/fixtures/gbs/ajax_login_redirect.txt

<interfaces>
<!-- Existing public surface from gbs_api.py — DO NOT change signatures -->

```python
# musicstreamer/gbs_api.py — current shapes (keep stable)
def _open_no_redirect(url: str, cookies: http.cookiejar.MozillaCookieJar,
                     timeout: int = _TIMEOUT_WRITE):
    """GET that does NOT follow redirects — used for /add/<songid> submit."""
    # Returns response object with .headers.get('Location') + .headers.get_all('Set-Cookie')

def submit(songid: int, cookies: http.cookiejar.MozillaCookieJar) -> str:
    """GET /add/<songid>; intercept 302; decode messages cookie; return text.
    Raises GbsAuthExpiredError on 302 -> /accounts/login/."""

def import_station(repo: Repo, on_progress=None) -> tuple:
    """Idempotent multi-quality import per D-01 / D-02a.
    Returns (inserted, updated)."""

def _decode_django_messages(cookie_value: str) -> list:
    """Already correct — no changes needed."""

class GbsAuthExpiredError(GbsApiError): ...
```

```python
# musicstreamer/repo.py (existing — read-only here)
class StationStream:
    id: int
    url: str
    label: str
    quality: str
    position: int
    stream_type: str
    codec: str
    bitrate_kbps: int

def list_streams(self, station_id: int) -> list[StationStream]: ...
def update_stream(self, stream_id, url, label, quality, position, stream_type, codec, *, bitrate_kbps): ...
```
</interfaces>

<diagnoses_to_apply>
**T13 root cause (60-DIAGNOSIS-302-messages.md §2):** `_NoRedirect.redirect_request` returning `None` makes CPython's `OpenerDirector.error` fall through to `http_error_default`, which unconditionally raises `HTTPError(code=302)`. The fix is to override `http_error_302` directly to return `fp` (the raw response file-object).

**T6 root cause (60-DIAGNOSIS-302-messages.md §3):** `import_station`'s update branch unconditionally returns `(0, 1)` for any matching station, regardless of whether any field actually changed. Fix: read existing streams BEFORE updating, compare each field tuple, count `updated=0` if and only if zero fields changed across all 6 streams.
</diagnoses_to_apply>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1 (TDD-RED): Write 4 failing regression tests in tests/test_gbs_api.py</name>
  <files>tests/test_gbs_api.py</files>
  <behavior>
    - test_open_no_redirect_returns_302_response_not_raises: Patch the LOWER-level transport (`urllib.request.AbstractHTTPHandler.do_open`) to return a fake `http.client.HTTPResponse`-shaped object with status=302, headers containing 'Location: /playlist' + 'Set-Cookie: messages=...'. The patch MUST be lower than `OpenerDirector.open` so the real `_NoRedirect` handler chain is exercised. Call `_open_no_redirect`; assert it returns an object with `.headers.get('Location') == '/playlist'` AND `.headers.get_all('Set-Cookie')` is non-empty. MUST NOT raise `urllib.error.HTTPError`. (Currently fails: raises HTTPError(302) per CPython opener chain.)
    - test_submit_success_via_real_redirect_handler: Same low-level transport patching strategy: build a fake `http.client.HTTPResponse` carrying the contents of `tests/fixtures/gbs/add_redirect_response.txt` (302 + messages cookie). Patch `urllib.request.AbstractHTTPHandler.do_open` (NOT `_open_no_redirect` itself — that bypasses the bug). Assert `submit()` returns "Track added successfully!" string (decoded from the messages cookie). (Currently fails: HTTPError(302) bubbles out before _decode_django_messages runs.)
    - test_submit_auth_expired_still_raises: Same patching strategy: return a 302 with Location: /accounts/login/?next=/add/123. Assert `submit()` raises `GbsAuthExpiredError`. (Currently passes but must not regress after Task 2.)
    - test_import_no_field_changes_returns_zero_updated: Use fake_repo fixture; pre-populate it with a GBS.FM station whose 6 streams already match the canonical _GBS_QUALITY_TIERS (same url/quality/position/codec/bitrate_kbps for each). Call import_station(fake_repo); assert the return value is `(0, 0)`. (Currently fails: returns (0, 1) regardless of actual changes.)
    - test_import_one_field_changes_returns_one_updated: Use fake_repo; pre-populate with a GBS.FM station whose streams match canonical EXCEPT one stream's bitrate_kbps differs by 1. Call import_station; assert return is `(0, 1)`. (Currently passes — must not regress.)
    - test_import_fresh_insert_returns_one_zero: Empty fake_repo. Call import_station; assert return is `(1, 0)`. (Currently passes — must not regress.)
  </behavior>
  <action>
    Append 6 new test functions to tests/test_gbs_api.py (after the existing test_decode_django_messages_garbage_returns_empty at the bottom). Use the fixtures already in conftest.py: `gbs_fixtures_dir`, `fake_cookies_jar`, `fake_repo`, `monkeypatch`. Existing tests use these — copy the patterns at the top of test_gbs_api.py.

    **Patching layer for `_NoRedirect` real-path tests — pinned concretely:**

    The existing `test_submit_success_decodes_messages` patches `_open_no_redirect` directly, which bypasses the very class under test. The plan-check (iter 1) flagged this as the false-assurance pattern that masked T13 in production. Per 60-DIAGNOSIS-302-messages.md §5e, the new tests MUST patch lower so the real `OpenerDirector.error` chain runs through `_NoRedirect.http_error_302`.

    **Pinned approach: patch `urllib.request.AbstractHTTPHandler.do_open`.** This is the function that actually reads from a socket and constructs the `http.client.HTTPResponse`. By replacing it with a stub that returns a pre-built fake response, the entire opener chain — including `HTTPRedirectHandler` / our `_NoRedirect` subclass — runs against the real CPython code paths. This is the deepest sensible mock layer: it doesn't require a real TCP socket, and it doesn't bypass any urllib internals.

    Concrete code sketch (copy this shape into tests/test_gbs_api.py):
    ```python
    import io
    import http.client
    import urllib.request
    import urllib.error

    def _make_fake_302_response(location: str, set_cookie: str | None = None,
                                body: bytes = b"") -> http.client.HTTPResponse:
        """Build an http.client.HTTPResponse-shaped object for a fake 302.

        We construct it from a synthetic raw-HTTP byte stream parsed back through
        http.client so the resulting object exposes the same .status / .headers /
        .read() surface that AbstractHTTPHandler.do_open would produce.
        """
        raw = b"HTTP/1.1 302 Found\r\n"
        raw += f"Location: {location}\r\n".encode()
        if set_cookie:
            raw += f"Set-Cookie: {set_cookie}\r\n".encode()
        raw += b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        raw += b"\r\n"
        raw += body

        class _FakeSock:
            def __init__(self, data: bytes):
                self._buf = io.BytesIO(data)
            def makefile(self, *a, **kw):
                return self._buf
            def sendall(self, *a, **kw):
                pass
            def close(self):
                pass

        sock = _FakeSock(raw)
        resp = http.client.HTTPResponse(sock)
        resp.begin()
        return resp


    def test_open_no_redirect_returns_302_response_not_raises(monkeypatch, fake_cookies_jar):
        """T13 RED: real _NoRedirect chain returns the response, never raises."""
        fake_resp = _make_fake_302_response(
            location="/playlist",
            set_cookie="messages=eyJfX2pzb25fbWVzc2FnZXNfXyI6W119; Path=/",
        )
        # Patch the LOW-level transport — opener chain (incl. _NoRedirect.http_error_302) runs for real.
        def _fake_do_open(self, http_class, req, **kwargs):
            return fake_resp
        monkeypatch.setattr(
            urllib.request.AbstractHTTPHandler, "do_open", _fake_do_open
        )
        resp = gbs_api._open_no_redirect("https://gbs.fm/add/123", fake_cookies_jar)
        assert resp.headers.get("Location") == "/playlist"
        assert resp.headers.get_all("Set-Cookie")  # non-empty


    def test_submit_success_via_real_redirect_handler(monkeypatch, fake_cookies_jar, gbs_fixtures_dir):
        """T13 RED: submit() returns decoded messages text, not HTTPError(302)."""
        # Read the canonical Set-Cookie value from the fixture. The fixture file is
        # a raw cookie value (base64url-encoded JSON); embed it in the fake response.
        cookie_path = os.path.join(gbs_fixtures_dir, "messages_cookie_track_added.txt")
        with open(cookie_path) as f:
            cookie_value = f.read().strip()
        fake_resp = _make_fake_302_response(
            location="/playlist",
            set_cookie=f"messages={cookie_value}; Path=/",
        )
        def _fake_do_open(self, http_class, req, **kwargs):
            return fake_resp
        monkeypatch.setattr(urllib.request.AbstractHTTPHandler, "do_open", _fake_do_open)
        text = gbs_api.submit(123, fake_cookies_jar)
        assert "Track added successfully!" in text


    def test_submit_auth_expired_still_raises(monkeypatch, fake_cookies_jar):
        """T13 GREEN-must-not-regress: 302 -> /accounts/login/ still raises GbsAuthExpiredError."""
        fake_resp = _make_fake_302_response(location="/accounts/login/?next=/add/123")
        def _fake_do_open(self, http_class, req, **kwargs):
            return fake_resp
        monkeypatch.setattr(urllib.request.AbstractHTTPHandler, "do_open", _fake_do_open)
        with pytest.raises(gbs_api.GbsAuthExpiredError):
            gbs_api.submit(123, fake_cookies_jar)
    ```

    Note: `_make_fake_302_response` may need minor adjustment depending on whether the existing test file already has a similar helper — search for `_FakeSock` / `HTTPResponse` first; if a similar helper exists, reuse it.

    Note on aliased redirect codes: Task 2 also overrides `http_error_301`, `http_error_303`, and `http_error_307` for belt-and-braces resilience (per diagnosis §6 Open Question 1). These aliases are NOT covered by Task 1 tests — they are defensive/aspirational. This is intentional and acceptable; the gbs.fm production response uses 302. If gbs.fm changes its redirect code in the future, the override will continue to work without code changes; if a regression test for the aliases is desired later, it can be added in a follow-up plan.

    For the dirty-check tests: read fake_repo's _FakeRepo class in tests/conftest.py (extended in Plan 60-01) — it already has `insert_station`, `insert_stream`, `update_stream`, `list_streams`. The test pre-populates the repo by calling `import_station` once (which produces the canonical state), then calls `import_station` again and asserts the second call's return value is `(0, 0)`. For the "one field changes" variant, mutate one stream after the first import (e.g. via `fake_repo.update_stream(stream.id, ..., bitrate_kbps=stream.bitrate_kbps + 1)`) before the second import_station call.

    Run pytest -x tests/test_gbs_api.py — confirm exactly 4 new tests fail (the 3 must-not-regress tests pass, the 4th already-correct one is the fresh-insert test). Commit RED:
    ```
    git add tests/test_gbs_api.py
    git commit -m "test(60-08): add failing regression tests for T13 (302 response capture) + T6 (import dirty-check)"
    ```

    NOTE: this commit MUST be RED. If a test passes that the diagnoses say should fail, re-read the diagnosis — you may have written the test against the broken behavior instead of the desired behavior.
  </action>
  <verify>
    <automated>cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/test_gbs_api.py -x 2>&1 | tail -30 | grep -v '^#' | grep -E 'FAILED|PASSED|test_open_no_redirect_returns_302|test_submit_success_via_real_redirect|test_import_no_field_changes'</automated>
  </verify>
  <done>4 of 6 new tests fail (T13 + T6 paths); 2 already-correct tests pass (auth-expired, fresh-insert). RED commit recorded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 1.5 (TDD-RED-update): Update existing test_import_idempotent for new (0, 0) semantics</name>
  <files>tests/test_gbs_api.py</files>
  <behavior>
    - The existing `test_import_idempotent` (tests/test_gbs_api.py:80-101) currently asserts `(inserted_2, updated_2) == (0, 1)` on the second `import_station` call. After Task 2's field-level dirty-check lands, the second call legitimately returns `(0, 0)` — so the assertion will fail.
    - Update the existing assertion to `(inserted_2, updated_2) == (0, 0)` to reflect the new field-level dirty-check semantic. The test's name and intent ("idempotent re-call") are preserved; only the expected counter changes.
    - The "one field changed → (0, 1)" semantic is covered separately by `test_import_one_field_changes_returns_one_updated` (Task 1) — no test coverage gap is introduced.
  </behavior>
  <action>
    **Why this task exists:** the iter-1 plan-check flagged that Task 2's field-level dirty-check fix would silently break `test_import_idempotent` because the test asserts `(0, 1)` on a no-op re-import — the OLD broken behavior. Updating the existing test in a separate, explicitly-RED commit makes the semantic shift visible in git history.

    **Resolution chosen (per iter-2 plan-check directive):** "Update the assertion to (0, 0) (idempotent re-call returns no-op)" — this is the natural and correct match for field-level dirty-check semantics. (The alternative — mutate state between calls — is already covered by `test_import_one_field_changes_returns_one_updated`; doing both would be redundant.)

    **Concrete edit in tests/test_gbs_api.py at line 95:**

    Change:
    ```python
        assert (inserted_2, updated_2) == (0, 1)
    ```

    To:
    ```python
        # 60-08 / T6 (Plan 60-08 revision 2): after field-level dirty-check, an
        # idempotent re-import (no field changes anywhere) returns (0, 0). The
        # "(0, 1) on real refresh" path is separately covered by
        # test_import_one_field_changes_returns_one_updated.
        assert (inserted_2, updated_2) == (0, 0)
    ```

    The rest of the test (sid stability, stream count, qualities) is unchanged.

    **Commit ordering with Task 1:** Combine this update with the Task 1 RED commit so both the new failing tests and the updated existing test are in the SAME RED commit. This keeps the RED→GREEN cycle clean: one RED commit captures all tests that must pass after Task 2, then Task 2 is the single GREEN commit for the dirty-check fix.

    Concretely, the RED commit at the end of Task 1 should:
    ```bash
    git add tests/test_gbs_api.py  # contains both new tests (Task 1) and updated test_import_idempotent (Task 1.5)
    git commit -m "test(60-08): add failing regression tests for T13/T6 + update test_import_idempotent for new (0,0) idempotent semantic"
    ```

    Run pytest -x tests/test_gbs_api.py — confirm `test_import_idempotent` now also fails (in addition to the 4 new failing tests), bringing the failing-test total to 5 of 6 new + 1 updated = 5 RED tests. The pre-existing `test_import_logo_download` and others are still PASSING.
  </action>
  <verify>
    <automated>cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/test_gbs_api.py -x -k "test_import_idempotent" 2>&1 | tail -10 | grep -v '^#' | grep -E 'FAILED|PASSED'</automated>
  </verify>
  <done>test_import_idempotent now fails with the new (0, 0) assertion (matches the desired GREEN semantic). The RED commit (combined with Task 1's tests) is recorded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2 (TDD-GREEN): Patch _NoRedirect to override http_error_302; add field-level dirty-check to import_station</name>
  <files>musicstreamer/gbs_api.py</files>
  <behavior>
    - _open_no_redirect now returns the 302 response object directly, exposing .headers.get('Location') and .headers.get_all('Set-Cookie')
    - submit() unchanged in signature — internally now reads the response object instead of catching HTTPError
    - import_station detects no-op refresh (zero field changes across all streams) and returns (0, 0); single-or-more field changes still return (0, 1)
    - All 6 new tests from Task 1 pass; the updated test_import_idempotent (Task 1.5) passes; all other 17 pre-existing test_gbs_api.py tests still pass; 1 pre-existing test_stream_ordering.py GBS test still passes
  </behavior>
  <action>
    **Step 2a: Fix `_NoRedirect`** at gbs_api.py:170-172.

    Replace the inner `_NoRedirect` class with one that overrides `http_error_302` directly. The override returns `fp` (the response file-object urllib passes in) rather than raising. Per 60-DIAGNOSIS-302-messages.md §5a recommendation: override `http_error_302`, NOT `redirect_request`. For belt-and-braces resilience against gbs.fm changing its redirect code, also override `http_error_301`, `http_error_303`, and `http_error_307` to do the same — this matches diagnosis §6 Open Question 1's recommendation.

    Concretely, the new class shape (final code is yours to write):
    ```python
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        # http_error_302 returns fp (the raw response) instead of following the
        # redirect. The default urllib chain (redirect_request -> None ->
        # http_error_default) raises HTTPError(302) — which is what broke T13.
        def http_error_302(self, req, fp, code, msg, headers):
            return fp
        http_error_301 = http_error_307 = http_error_303 = http_error_302
    ```
    Add a comment block referencing CPython's `urllib/request.py` (HTTPDefaultErrorHandler.http_error_default raises HTTPError unconditionally when the redirect chain returns falsy) so future maintainers don't revert the fix.

    Verify `submit()` at line 424-447 still works correctly: `resp.headers.get("Location")` and `resp.headers.get_all("Set-Cookie")` should now both be live (they were never reached before because the function never returned). The rest of submit() (auth-expired branch, _decode_django_messages call, return text) is correct per the diagnosis §5b/5c.

    Commit GREEN for the redirect fix:
    ```
    git add musicstreamer/gbs_api.py
    git commit -m "fix(60-08): override http_error_302 in _NoRedirect to return 302 response (T13)

    CPython's urllib chain calls redirect_request -> None -> http_error_default
    which unconditionally raises HTTPError(302). Returning fp from
    http_error_302 directly stops the chain at the response and lets submit()
    read Location + Set-Cookie: messages headers. Closes T13.

    Refs: .planning/phases/60-gbs-fm-integration/60-DIAGNOSIS-302-messages.md"
    ```

    **Step 2b: Add field-level dirty-check to `import_station`** at gbs_api.py:528-548.

    In the update branch (the `else` block at line 528), BEFORE calling `repo.update_stream(...)` for each stream, compute a dirty flag: compare the existing stream's `(url, quality, position, codec, bitrate_kbps)` against the canonical tier dict. Track a single `any_field_changed: bool` initialized to False; set to True the first time any field differs.

    For streams in `streams` that aren't in `existing_streams` (rare — would mean GBS.FM added a tier), the insert path runs; that counts as a change. For existing streams that match exactly, still call `repo.update_stream(...)` (so SQLite stays in sync if anything ELSE drifted) but don't flip the dirty flag.

    After the loop, set:
    ```python
    inserted = 0
    updated = 1 if any_field_changed else 0
    ```
    Return `(0, 0)` is now reachable when nothing changed; `(0, 1)` reachable when at least one field differs; `(1, 0)` from the insert branch is unchanged.

    Field comparison shape (concrete):
    ```python
    # for each stream in canonical tier list:
    target = (s["url"], s["quality"], s["position"], s["codec"], int(s["bitrate_kbps"]))
    existing = (row.url, row.quality, row.position, row.codec, int(row.bitrate_kbps or 0))
    if target != existing:
        any_field_changed = True
    ```
    Use the existing `repo.list_streams` rows (already loaded into `existing_streams`). Don't compare `label` or `stream_type` — those aren't part of the canonical tier list and will always carry whatever was stored.

    Run pytest -x tests/test_gbs_api.py — all 6 new tests now pass; the updated `test_import_idempotent` (Task 1.5) now passes; all other pre-existing tests still pass.

    Commit GREEN for the dirty-check fix:
    ```
    git add musicstreamer/gbs_api.py
    git commit -m "fix(60-08): import_station returns (0,0) when no stream field changed (T6)

    Adds field-level dirty-check across (url, quality, position, codec,
    bitrate_kbps). Update path still calls repo.update_stream for SQLite
    consistency, but only counts as updated when at least one field differs
    from stored values. Closes T6.

    Refs: .planning/phases/60-gbs-fm-integration/60-DIAGNOSIS-302-messages.md §3"
    ```
  </action>
  <verify>
    <automated>cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/test_gbs_api.py tests/test_stream_ordering.py 2>&1 | tail -10 | grep -v '^#' | grep -E 'passed|failed'</automated>
  </verify>
  <done>All 24 tests in test_gbs_api.py pass (17 pre-existing untouched + 1 updated test_import_idempotent + 6 new); test_gbs_flac_ordering still passes; both GREEN commits recorded.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client → gbs.fm | HTTP 302 response carries Set-Cookie: messages payload (untrusted) |
| gbs.fm → _decode_django_messages | base64url + JSON parse of messages cookie value (untrusted) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-60-08-01 | Tampering | _NoRedirect.http_error_302 returning attacker-controlled fp | accept | Cookies attached to GET via existing HTTPCookieProcessor; same-origin policy enforced by urllib + connection-level TLS via gbs.fm. Risk equivalent to existing _open_with_cookies path; no new attack surface introduced by the fix. |
| T-60-08-02 | Information Disclosure | Decoded messages text logged or surfaced | mitigate | Existing `_decode_django_messages` is idempotent and graceful (returns [] on any decode failure per gbs_api.py:412-416). Caller `submit()` returns the joined text directly; UI dialog renders via QStandardItem PlainText (T-40-04). No regression. |
| T-60-08-03 | Denial of Service | Caller retries on 302 if response body large | accept | Fix is a single response read; gbs.fm 302 bodies are empty (Location header only). No retry loop introduced. |
| T-60-08-04 | Tampering | import_station dirty-check skips writes | mitigate | The fix changes return value semantics, not write semantics — `repo.update_stream` is still called for every existing stream (preserves SQLite WAL invariants). The dirty flag only changes the return tuple. |
</threat_model>

<verification>
- pytest tests/test_gbs_api.py shows 24 tests pass (17 pre-existing untouched + 1 updated test_import_idempotent + 6 new); 0 fail.
- pytest tests/test_stream_ordering.py::test_gbs_flac_ordering still passes.
- pytest tests/test_now_playing_panel.py shows 71 tests pass (no regression in vote/playlist tests that depend on gbs_api).
- Manual reproduction (run app, click "Add GBS.FM" twice in succession): second toast says "GBS.FM import: no changes" instead of "GBS.FM streams updated".
- Manual reproduction (run app, search a track in GBSSearchDialog, click Add!): row shows the success message text (e.g. "Track added successfully!") instead of "Submit failed: HTTP Error 302: Found".
- grep -c 'http_error_302' musicstreamer/gbs_api.py >= 1 — confirms the new override is present.
- grep -c 'any_field_changed' musicstreamer/gbs_api.py >= 1 — confirms dirty-check landed.
- grep -E 'redirect_request.*return None' musicstreamer/gbs_api.py is empty — confirms broken pattern removed.
</verification>

<success_criteria>
- T13 closed: submit() returns the messages text (e.g. "Track added successfully!") for the success path; auth-expired still raises GbsAuthExpiredError; gbs_search_dialog inline error is the decoded message, not "HTTP Error 302: Found".
- T6 closed: re-clicking "Add GBS.FM" with no actual upstream changes shows "GBS.FM import: no changes" toast.
- All 24 tests in tests/test_gbs_api.py pass — broken down as: 17 pre-existing (untouched) + 1 pre-existing UPDATED (`test_import_idempotent`, second-call assertion changed from `(0, 1)` to `(0, 0)` per Task 1.5) + 6 new (Task 1).
- No regression in tests/test_stream_ordering.py, tests/test_now_playing_panel.py, or tests/test_gbs_search_dialog.py.
- Two atomic commits: 1 RED (failing tests + updated test_import_idempotent), 2 GREEN (one per fix). Total 3 commits.
</success_criteria>

<output>
After completion, create `.planning/phases/60-gbs-fm-integration/60-08-fix-302-messages-SUMMARY.md` per the standard summary template, including:
- Frontmatter: requires=[60-02], provides=["fixed _NoRedirect override", "import_station dirty-check"], requirements-completed=[GBS-01a, GBS-01e]
- Sections: Performance / Accomplishments / Task Commits / Files Modified / Decisions Made / TDD Gate Compliance / Deviations / Threat Flags / Self-Check
- Note in Deviations section: test_import_idempotent semantic was updated (0,1) → (0,0) to match field-level dirty-check fix; documented in revision-2 of this plan.
</output>
