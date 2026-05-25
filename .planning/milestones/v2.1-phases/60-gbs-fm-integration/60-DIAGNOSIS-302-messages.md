# Phase 60 — Diagnosis: 302-redirect + Django messages cookie parsing

**Date:** 2026-05-04
**Bugs covered:** T6 (wrong toast on redundant import), T13 (submit shows "HTTP Error 302: Found")
**Status:** Root cause confirmed by code inspection + urllib CPython source verification

---

## 1. Root Cause

`_open_no_redirect` does **not** return the 302 response — CPython's `urllib` raises `urllib.error.HTTPError(code=302)` when a redirect handler's `redirect_request` returns `None`, so neither the `Set-Cookie: messages=...` header nor the `Location` header is ever read by Python code; both bugs descend from this single mechanism failure.

---

## 2. T13 Mechanism — "Submit Failed: HTTP Error 302: Found"

### Intended flow (docstring claim vs. reality)

`_open_no_redirect` (gbs_api.py lines 163–177) installs `_NoRedirect`, a subclass of `urllib.request.HTTPRedirectHandler` whose `redirect_request` method returns `None`. The docstring says "The 302 response is returned directly so caller can read Set-Cookie." This is incorrect.

### What CPython actually does

When `opener.open(req)` receives a 302 response, it invokes the handler chain. `HTTPRedirectHandler.http_error_302` (stdlib) calls `self.redirect_request(...)`, receives `None`, and executes `return` (i.e. returns `None` from `http_error_302`). Control falls back to `OpenerDirector.error`, which checks the return value: because it is falsy, it falls through to `http_error_default`. `HTTPDefaultErrorHandler.http_error_default` then unconditionally raises:

```python
raise HTTPError(req.full_url, code, msg, hdrs, fp)
# code=302, msg="Found"
```

So `opener.open()` at line 177 raises `urllib.error.HTTPError(code=302)` instead of returning the response object.

### Propagation to the dialog

`submit()` at line 432 calls `_open_no_redirect(...)` without a try/except for `HTTPError`. The `HTTPError(302)` propagates up through `_GbsSubmitWorker.run()` at gbs_search_dialog.py line 104:

```python
msg = gbs_api.submit(self._songid, self._cookies)
```

`run()` catches `Exception` generically at line 107–110 but checks `isinstance(exc, gbs_api.GbsAuthExpiredError)` first. A raw `urllib.error.HTTPError(302)` is NOT a `GbsAuthExpiredError`, so it falls to the `else` branch and emits:

```python
self.error.emit(str(exc), self._row_idx)
# str(urllib.error.HTTPError(302)) == "HTTP Error 302: Found"
```

`_on_submit_error` at line 407–421 receives this. The `msg` is not `"auth_expired"`, so it hits the `else` branch at line 418:

```python
self._show_inline_error(f"Submit failed: {truncated}")
```

The user sees: **"Submit failed: HTTP Error 302: Found"** — even though the request reached gbs.fm, was processed, and the track was queued.

### Key lines

| File | Line(s) | What happens |
|------|---------|--------------|
| `gbs_api.py` | 170–172 | `_NoRedirect.redirect_request` returns `None` |
| `gbs_api.py` | 177 | `opener.open(req)` raises `HTTPError(302)` (not returned) |
| `gbs_api.py` | 432 | `submit()` receives the unhandled `HTTPError(302)` |
| `gbs_search_dialog.py` | 104 | `_GbsSubmitWorker.run()` re-raises it as generic exception |
| `gbs_search_dialog.py` | 109–110 | `str(exc)` = "HTTP Error 302: Found" emitted via `error` signal |
| `gbs_search_dialog.py` | 418–419 | `_on_submit_error` shows red inline error with that string |

### Why the request still succeeds

`_open_no_redirect` is called after the `HTTPCookieProcessor` has already attached valid session cookies to the request. The HTTP request reaches gbs.fm, is processed server-side (track is added to the queue), and the 302 response is sent back. Python raises on the 302 locally — but the server-side write has already committed. The track appears in the queue attributed to "Lightning Jim" even though the client never reads the success message.

---

## 3. T6 Mechanism — Toast always says "GBS.FM streams updated", never "no changes"

### The import flow

`import_station()` (gbs_api.py lines 485–562) uses a hard binary branch:

- If `existing_id is None` (station not in DB): performs insert path, sets `inserted, updated = 1, 0` (line 527).
- If `existing_id is not None` (station already in DB): performs update path, sets `inserted, updated = 0, 1` (line 548), **unconditionally**.

The update path at lines 530–547 always calls `repo.update_stream(...)` for every stream URL that already exists, regardless of whether any field values changed. It is not a dirty-check; it is always a write. The return value `(0, 1)` is therefore not "1 row actually changed" — it means "the station was found; update path was executed."

### The UI branch

`_on_gbs_import_finished` in main_window.py lines 761–768:

```python
def _on_gbs_import_finished(self, inserted: int, updated: int) -> None:
    if inserted:
        self.show_toast("GBS.FM added")
    elif updated:
        self.show_toast("GBS.FM streams updated")
    else:
        self.show_toast("GBS.FM import: no changes")
```

Because `import_station()` always returns `(0, 1)` on any re-import (updated=1, never 0), the `elif updated` branch is always taken. The `else` branch ("GBS.FM import: no changes") is structurally unreachable after the first import.

### Why this is a data model bug, not a UI bug

The `else` branch in the UI is correct per D-02a. The fault is in `import_station`'s return-value semantics: it conflates "the update path was executed" with "rows changed." The `(0, 0)` return that would trigger "no changes" can only occur if the code reaches neither the insert block nor the update block — which is impossible given the current binary if/else at lines 503 and 528.

### Why the DB is idempotent but the toast is not

`repo.update_stream(...)` calls through to a SQLite `UPDATE` statement. SQLite's `UPDATE` is idempotent at the data level (writing the same values changes nothing on disk), but it does not distinguish "nothing changed" from "row was touched." `import_station` counts execution of the update path, not actual field-level deltas. Result: zero actual DB changes, but `updated=1` is still returned.

### Key lines

| File | Line(s) | What happens |
|------|---------|--------------|
| `gbs_api.py` | 503 | `if existing_id is None:` — insert branch |
| `gbs_api.py` | 527 | `inserted, updated = 1, 0` — first call |
| `gbs_api.py` | 528 | `else:` — update branch (any subsequent call) |
| `gbs_api.py` | 548 | `inserted, updated = 0, 1` — always, no dirty-check |
| `main_window.py` | 763–768 | UI branches on `inserted` then `updated`; `else` unreachable |

---

## 4. Why Both Bugs Share a Root Cause

Both bugs are manifestations of the same architectural gap: **the 302-redirect response body (including Set-Cookie headers) is never parsed in Python code.**

For T13: the 302 carries a `Set-Cookie: messages=...` header containing the Django messages cookie that encodes the human-readable success/failure string ("Track added successfully!" or "You don't have enough tokens"). Because `_open_no_redirect` raises instead of returning the response, `submit()` never reads this header, never calls `_decode_django_messages`, and never returns meaningful text to the dialog. The dialog therefore has no signal to distinguish success from error and falls into the generic exception handler.

For T6: the connection is less direct but structurally related. `import_station` does not use the 302-intercept pattern (it calls `repo` methods, not HTTP), but both bugs stem from the same class of problem: the system produces a success signal (server-side write succeeded / DB row exists) but the client-side code lacks the ability to inspect the server's intent message and so falls back to the wrong branch. In T6 the "intent message" would be the dirty-check result (`updated=0` for a true no-op); in T13 it is the Django messages cookie. Neither is read.

The shared root cause is: **the 302-redirect response envelope — including both the `Location` header and the `Set-Cookie: messages=...` header — is discarded before any Python code inspects it.** The `_NoRedirect` handler strategy is architecturally correct (intercept the 302) but fails because CPython's `urllib` raises `HTTPError` rather than returning the response when `redirect_request` returns `None`.

---

## 5. Fix Outline (structural plan, not code)

### 5a. Make `_open_no_redirect` actually return the 302 response

The fix is to override `http_error_302` (the method that actually fires for 302s), not `redirect_request`. The correct approach: override `http_error_302` to return `fp` (the raw response file-object that urllib passes in) instead of raising or following. This makes `opener.open()` return the response object — with its headers intact — rather than raising.

Alternatively, use a lower-level approach: do not register `_NoRedirect` at all; instead, configure `urllib.request.build_opener` with no redirect handler and catch the response via a custom error handler that stores it on a container and returns it.

Either way, after the fix `_open_no_redirect` must return an object with:
- `.headers.get("Location")` → the redirect target
- `.headers.get_all("Set-Cookie")` → the list of Set-Cookie headers

### 5b. Where the messages-cookie decoder belongs (no change needed)

`_decode_django_messages` at gbs_api.py lines 401–421 is correct and already called by `submit()` at line 440. No relocation is needed. The gap is upstream: `submit()` never gets to call it because `_open_no_redirect` raises before returning any response object.

### 5c. How `submit` should map decoded message text to return values

`submit()` already returns the decoded message string to the caller. The existing `_on_submit_finished` disambiguation logic in gbs_search_dialog.py lines 393–404 (keyword scan for "duplicate", "already", "not enough tokens", etc.) is the correct place to distinguish success from quota/duplicate errors. This logic is sound and needs no changes once `submit()` can actually return the decoded message.

The mapping after the fix:
- 302 with `Location` containing `/accounts/login/` → raise `GbsAuthExpiredError` (already implemented)
- 302 with `Set-Cookie: messages=...` → decode, return text → caller disambiguates via keyword scan
- 302 with no messages cookie → return `""` → caller treats as generic success

### 5d. How `import_station` should handle the "no changes" case (T6)

Two options, in ascending complexity:

**Option A (minimal, recommended):** After performing `repo.update_stream(...)` calls in the update branch, compare the written values against what was already stored. If no field changed across all 6 streams, set `updated = 0` (and `inserted` remains 0), giving `(0, 0)` which triggers the "no changes" toast. This requires reading each existing stream's current values before the update and doing a field-level comparison.

**Option B (simpler heuristic):** Accept that a true "no changes" case is impossible to detect without a dirty-check, and change the design so that `import_station` only returns `(0, 1)` when at least one stream field actually differs from the stored value. This is semantically what D-02a intended.

Either option keeps `_on_gbs_import_finished` in main_window.py unchanged; the fix is wholly inside `import_station`.

### 5e. Which existing fixtures should drive new parser tests

The following fixtures are already present and correctly structured for new tests:

- `tests/fixtures/gbs/add_redirect_response.txt` — the full 302 HTTP response with the `Set-Cookie: messages=...` header. Should drive a test that exercises `_open_no_redirect` returning the response (not raising) and `submit()` decoding the cookie.
- `tests/fixtures/gbs/messages_cookie_track_added.txt` — the raw base64-url payload. Already exercises `_decode_django_messages` via `test_decode_django_messages`. No change needed for the decoder test itself.
- `tests/fixtures/gbs/ajax_login_redirect.txt` — the auth-expired 302 shape (`Location: /accounts/login/?next=/ajax`). Should drive a test that `_open_no_redirect` (after the fix) still raises `GbsAuthExpiredError` when `Location` contains `/accounts/login/`.

The existing `test_submit_success_decodes_messages` test (test_gbs_api.py lines 240–265) monkey-patches `_open_no_redirect` to return a MagicMock that bypasses the urllib layer entirely. This test passes today but provides false assurance: it does not exercise the real `_open_no_redirect` path that fails in production. After the fix, a new integration-level test should exercise the actual `_open_no_redirect` function with a mock HTTP server or a patched `opener.open` that returns a real `http.client.HTTPResponse`-shaped object (not a MagicMock), so the test would have caught the original bug.

---

## 6. Open Questions

1. **Which override point in `urllib.request.HTTPRedirectHandler` is safest?**
   Overriding `http_error_302` directly is the most targeted fix. However, the handler chain also invokes `http_error_301` and `http_error_307` for other redirect codes. If gbs.fm ever sends a 301 or 307 instead of 302 for the `/add/` response, the fix should cover those codes as well. A single override of `http_error_redirect` (which all 3xx codes delegate to) is more robust, but may interact with other opener handlers in unexpected ways. Needs a planner decision.

2. **Does `HTTPCookieProcessor` process `Set-Cookie` headers on 302 responses before `HTTPRedirectHandler` sees them?**
   In the standard opener chain, `HTTPCookieProcessor.http_response` runs after `do_open` returns but before redirect handling fires. The exact ordering of cookie extraction vs. redirect interception in CPython's opener chain needs verification to confirm the messages cookie is accessible on the response object that the fixed `_open_no_redirect` will return.

3. **T6 dirty-check: is `repo.update_stream` idempotent at the SQLite level?**
   The current `update_stream` always issues an `UPDATE` SQL statement. Whether SQLite counts this as a change (triggering WAL writes) even when values are unchanged affects performance on repeated imports, but does not affect correctness of the fix. Inspection of `repo.py` `update_stream` implementation would confirm.

4. **`_GbsImportWorker` does not pass `on_progress` to `import_station`** (main_window.py line 119). This means the "Importing GBS.FM…" progress callback in `import_station` (lines 494–498) is never called. This is a separate minor issue, not related to T6 or T13, but worth flagging during the fix pass.

5. **Test coverage gap:** `test_submit_success_decodes_messages` passes today despite the real code being broken, because it patches `_open_no_redirect` at the wrong level (replaces it with a context-manager mock rather than simulating actual urllib behavior). After the fix, this test should be strengthened so it would catch a regression to the broken behavior.
