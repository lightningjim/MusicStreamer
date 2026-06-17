---
phase: 89B-twitch-channel-avatar-fetch
reviewed: 2026-06-16T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - musicstreamer/twitch_helix.py
  - musicstreamer/yt_import.py
  - musicstreamer/ui_qt/edit_station_dialog.py
  - tests/test_twitch_helix.py
  - tests/test_edit_station_dialog_avatar.py
  - tests/test_twitch_provider_assign.py
  - tests/test_edit_station_dialog.py
  - tests/test_yt_import_library.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 89B: Code Review Report

**Reviewed:** 2026-06-16
**Depth:** standard (ultracode: all dimensions + adversarial pass)
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Phase 89B adds Twitch channel-avatar fetching via the Helix `/users` endpoint, registered
into the existing per-provider avatar fetcher registry. The implementation is structurally
sound: the authorization token is sent only to `api.twitch.tv` as a Bearer header on a scoped
`Request` object and never to the CDN download (which uses a plain URL string). The
`_AvatarFetchWorker.run()` correctly never re-raises, dispatches via the registry, and
forwards `node_runtime` only for the YouTube path. The provider-derivation guard in
`_on_save` is correct (blank-only, never overwrites a user value). The test suite is
comprehensive in its happy-path and registry coverage.

Two issues warrant attention before ship: a spec-mandated URL-encoding step is missing from
`fetch_channel_avatar`, which can corrupt the Helix request for any URL whose final path
segment contains a literal `&` character; and the security-critical CDN-header assertion in
`test_fetch_calls_helix_with_bearer_and_client_id` is dead code — the `if hasattr(cdn_req,
'get_header')` guard is always false because the CDN call uses a plain string, so the test
never actually asserts the security invariant it documents.

---

## Narrative Findings (AI reviewer)

### WR-01: Login value not URL-encoded before insertion into Helix query string

**File:** `musicstreamer/twitch_helix.py:102-107`

**Issue:** `_HELIX_USERS_URL.format(login=login)` performs a bare Python string
substitution. `_parse_login` strips the query string (`?`) and fragment (`#`) from the
input URL, but it does not strip or encode `&` or `=` characters that may appear in the
final path segment. A URL such as
`https://www.twitch.tv/gooduser&client_id=attacker` survives `_parse_login` as
`gooduser&client_id=attacker`, which is then inserted verbatim into the query string,
producing:

```
https://api.twitch.tv/helix/users?login=gooduser&client_id=attacker
```

The Helix host is hardcoded so there is no SSRF, and the only user who can type station
URLs is the local desktop user. However:

1. The phase design spec explicitly states "login is URL-encoded as a query param" as a
   required invariant to verify (phase_context). The encoding is absent.
2. Twitch's parsing of duplicate or injected query parameters is implementation-defined;
   a crafted URL could cause the Helix call to resolve a different user's login, displaying
   a wrong avatar silently.
3. The same unencoded login string is also stored as the provider name
   (`"Twitch: gooduser&client_id=attacker"`) in the database via `ensure_provider`, leaving
   corrupt data that persists across sessions.
4. The test suite has no case exercising a login string containing `&`, so this path is
   untested.

There are no adversarial-pass refutations: the gate in `_on_url_text_changed` checks only
for `"twitch.tv" in lower` (a substring match), so the code path is reachable from any
URL containing `twitch.tv`.

**Fix:**

```python
# musicstreamer/twitch_helix.py  — top of file, add import
import urllib.parse

# In fetch_channel_avatar, replace the format call:
helix_req = urllib.request.Request(
    _HELIX_USERS_URL.format(login=urllib.parse.quote(login, safe="")),
    ...
)
```

A complementary fix is to validate that `login` matches the Twitch login character set
(`^[a-zA-Z0-9_]{1,25}$`) and raise `ValueError` for invalid logins before the HTTP call.

---

### WR-02: CDN-header security assertion in test is always skipped (dead assertion)

**File:** `tests/test_twitch_helix.py:139-142`

**Issue:** The test `test_fetch_calls_helix_with_bearer_and_client_id` documents a
security-critical invariant — "The CDN download must NOT carry the Authorization header
(token scope, T-89b-01 / Pitfall 5)". The assertion is:

```python
cdn_req = captured_requests[1]
if hasattr(cdn_req, "get_header"):          # (A)
    assert cdn_req.get_header("Authorization") is None
```

The CDN download in `twitch_helix.fetch_channel_avatar` (line 119) is:

```python
with urllib.request.urlopen(image_url, timeout=10) as resp:
```

where `image_url` is a plain `str`. `urllib.request.urlopen` receives the raw string; the
`captured_requests[1]` value is therefore the string itself. A plain Python `str` does not
have `get_header`, so condition `(A)` is always `False`, the `assert` never executes, and
the test passes unconditionally regardless of whether the CDN call leaks the token.

The production code is currently correct (the CDN call uses a bare URL string with no
headers), but the test provides no evidence of that — it cannot catch a future regression
that wraps the CDN URL in a `Request` object and inadvertently copies the `Authorization`
header.

**Fix:** Replace the `if hasattr` guard with an unconditional assertion that the CDN call
is a plain string (proving no `Request` wrapper with headers was constructed):

```python
cdn_req = captured_requests[1]
# CDN download MUST be a plain URL string, not a Request object carrying auth headers.
# T-89b-01 / Pitfall 5: the token must never leave api.twitch.tv.
assert isinstance(cdn_req, str), (
    "CDN download must be a plain URL string, not a Request object "
    f"(T-89b-01 token-scope violation): got {type(cdn_req)}"
)
# Belt-and-suspenders: if this ever becomes a Request object, Authorization must be absent.
if hasattr(cdn_req, "get_header"):
    assert cdn_req.get_header("Authorization") is None
```

---

## Info

### IN-01: No test for worker failure path in new Twitch dispatch tests

**File:** `tests/test_edit_station_dialog_avatar.py:114-185`

**Issue:** `test_avatar_worker_dispatches_twitch` only exercises the happy path (fetcher
returns bytes, `write_provider_avatar` succeeds, worker emits non-empty path). There is no
test that verifies WR-04 compliance for the Twitch dispatch path: when `twitch_helix.fetch_channel_avatar` raises (e.g., `RuntimeError("No Twitch login")`), the worker
must emit `("", token)` rather than re-raising. The happy-path test for YouTube dispatch
has the same gap. The existing `except Exception` block at line 190-192 handles this
correctly in production, but the test file does not prove it.

**Fix:** Add a test case:

```python
def test_avatar_worker_twitch_fetcher_failure_emits_empty():
    """WR-04: if the Twitch fetcher raises, run() emits ('', token) — never re-raises."""
    from musicstreamer.ui_qt.edit_station_dialog import _AvatarFetchWorker
    from musicstreamer import yt_import

    def raising_fetcher(url):
        raise RuntimeError("No Twitch login — connect via Accounts to fetch avatar")

    with patch.object(yt_import, "get_avatar_fetcher", return_value=raising_fetcher):
        worker = _AvatarFetchWorker(
            url="https://www.twitch.tv/twitchdev",
            token=3, station_id=1, parent=None, provider_id=7,
        )
        emitted = []
        worker.finished.connect(lambda p, t: emitted.append((p, t)))
        worker.run()

    assert emitted == [("", 3)], "Worker must emit empty path on fetcher exception"
```

---

_Reviewed: 2026-06-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard (ultracode mode)_
