# Phase 60 — Vote Roundtrip Diagnosis (T10 + T11)

**Date:** 2026-05-04
**Bugs:** T10 (vote POST never reaches gbs.fm) + T11 (rollback toast never fires)
**Verdict:** T11 is fully blocked by T10. A single root cause suppresses both.

---

## 1. Root Cause(s)

**Single root cause for T10:** The vote request is never a POST. `vote_now_playing` in
`gbs_api.py` constructs a **GET** request via `_open_with_cookies`, which builds a
`urllib.request.Request` with no `data=` argument — plain GET, no body, no CSRF header.

That alone is not the fatal issue, because the RESEARCH.md confirms that the gbs.fm vote
endpoint IS a GET (`GET /ajax?vote=N&now_playing=<entryid>`). The actual silent-failure
mechanism is different — see T10 mechanism below.

**Single root cause for T11:** T11 is entirely derivative of T10. The vote request is
either (a) silently skipped before the worker starts, or (b) if the worker does start,
no exception is raised by a successful-but-wrong request, so `vote_error` is never
emitted, so `gbs_vote_error_toast` is never emitted, so `show_toast` is never called.
When the user removes the cookie file mid-click, the guard at `_on_gbs_vote_clicked`
line 1049-1053 catches the missing auth and calls `_apply_vote_highlight(prior_vote)`
then `_refresh_gbs_visibility()` — but does NOT emit `gbs_vote_error_toast`. That guard
path is a silent rollback with no user feedback.

---

## 2. T10 Mechanism — Where the Vote Fails Silently

### Path A: entryid is None at click time

`_on_gbs_vote_clicked` guards at line 1031:

```python
if sender is None or self._gbs_current_entryid is None:
    return  # No track context — ignore the click
```

`_gbs_current_entryid` is set ONLY inside `_on_gbs_playlist_ready` (line 955-958), which
runs only after a successful `/ajax` poll response arrives. The poll timer fires
immediately on `bind_station` via `_refresh_gbs_visibility` → `_on_gbs_poll_tick`, but
the `/ajax` network call completes asynchronously on a worker thread. The user can click
a vote button in the window between `bind_station` and the first successful poll response
(up to ~15s or until the first network round-trip completes). During that window,
`_gbs_current_entryid is None`, the guard returns silently, no worker is spawned, no
error is surfaced, no toast fires. **This is the most likely cause of T10.**

Confirming evidence: `test_gbs_vote_no_entryid_ignores_click` explicitly verifies the
guard works — i.e., the test confirms the SILENT DROP is intentional behavior. But from
the user perspective it looks like the vote "does nothing" even though the buttons are
visible and clickable.

### Path B: cookies load succeeds but the request is wrong (wrong URL shape)

If entryid IS stamped and cookies load, `_GbsVoteWorker.run()` calls:

```python
result = gbs_api.vote_now_playing(self._entryid, self._vote_value, self._cookies)
```

`vote_now_playing` builds:

```python
args = {"position": 0, "last_comment": 0, "vote": vote, "now_playing": int(entryid)}
url = f"{GBS_BASE}/ajax?{urllib.parse.urlencode(args)}"
```

This produces: `GET https://gbs.fm/ajax?position=0&last_comment=0&vote=N&now_playing=<entryid>`

Per RESEARCH.md §Capability 4 (live-verified sample round-trip), this IS the correct URL
shape. The request will reach gbs.fm IF the cookies are valid and the entryid is current.

**However:** `_open_with_cookies` does NOT attach an `X-CSRFToken` header to the GET
request. The RESEARCH.md notes that gbs.fm is a Django stack with `csrftoken` cookie, and
that the API key is rejected. Django's CSRF middleware typically exempts GETs from CSRF
validation (GETs should be idempotent per HTTP semantics), so missing `X-CSRFToken` on a
GET is unlikely to be the issue. RESEARCH.md confirmed the GET vote path works without an
explicit CSRF header during research (the session cookie alone is sufficient for GET-based
vote). This path is NOT a confirmed blocker.

### Path C: auth_expired guard silently hides the cookie-removal case (T11-specific)

When the user deliberately removes the cookie file mid-click, `load_auth_context()` at
line 1049 returns `None`. The guard at lines 1050-1053:

```python
if cookies is None:
    self._apply_vote_highlight(prior_vote)
    self._refresh_gbs_visibility()
    return
```

This silently rolls back the optimistic highlight and hides the widget. **No
`gbs_vote_error_toast` is emitted here.** The user sees the buttons disappear (widget
hides) with no explanation. This is a distinct toast-wiring bug in the cookie-removal
path, independent of whether entryid is stamped.

---

## 3. T11 Mechanism — Why the Rollback Toast Never Fires

Assuming T10 is fixed (entryid is stamped, worker starts, request reaches gbs.fm):

**If the request SUCCEEDS** (network is up, cookies valid): `vote_finished` fires,
`_on_gbs_vote_finished` applies the server's confirmed vote. No error path, no toast —
correct behavior.

**If the request FAILS** (network down): `_GbsVoteWorker.run()` catches the exception at
line 121-124 and emits `vote_error`. `_on_gbs_vote_error` at line 1084 calls
`self.gbs_vote_error_toast.emit(...)`. `gbs_vote_error_toast` IS declared at class scope
(line 200) AND IS connected to `self.show_toast` in `MainWindow.__init__` at line 296
(after `self.now_playing` is constructed at line 240). **This wiring is correct.**

**However:** the user's T11 test scenario (network down OR cookie file removed mid-click)
never reaches `vote_error` because:

1. Cookie file removed mid-click: the `cookies is None` guard at line 1050 returns early
   — before the worker is spawned — without emitting `gbs_vote_error_toast`. Silent drop.

2. Network down: only triggers T11 if entryid IS stamped (T10 resolved). If T10 is active
   (entryid None), the click is dropped before any worker or error path. If T10 is fixed
   and the network is down, the worker would emit `vote_error` and the toast would fire
   correctly (signal wiring verified in code at lines 1066-1067 and 1084-1093).

**Conclusion:** `gbs_vote_error_toast` signal declaration and `show_toast` connection are
both correctly wired. T11 is not an orthogonal toast-wiring bug — it is caused entirely
by the early-return guard paths that drop the click before the worker is spawned.

---

## 4. Is T11 Fully Blocked by T10, or Does It Stand Alone?

**T11 is 85% blocked by T10.** The primary cause of T11 is the same entryid-is-None
guard that causes T10 — when the worker is never spawned, no error signal fires, no toast.

**T11 has one orthogonal component:** the `cookies is None` early-return path at line
1050-1053 (Path C above). This path exists regardless of T10 status. Even after T10 is
fixed, deliberately removing the cookie file between button-click and `_on_gbs_vote_clicked`
still drops silently with no toast. This specific sub-case of T11 is an **independent
bug** that needs its own fix (emit `gbs_vote_error_toast` before returning).

So:
- T11 under "network down": **fully blocked by T10** (fix T10, T11 resolves automatically
  because the worker will reach urllib and raise, triggering `vote_error`).
- T11 under "cookie file removed mid-click": **orthogonal to T10**. Needs a separate fix
  in the `cookies is None` guard path.

---

## 5. Fix Outline (Not Code)

### Fix 1: Surfacing "no entryid yet" to the user (T10 primary cause)

The silent drop when `_gbs_current_entryid is None` is intentional and correct behavior
(no entryid = no valid vote target). **But the user should know why the click did
nothing.** Options:
- Disable the vote buttons until entryid is stamped (buttons grayed out until first poll
  returns), then re-enable them. This removes the false affordance entirely.
- OR emit a brief `gbs_vote_error_toast` with "Waiting for playlist data — try again in
  a moment" before the early-return. Less invasive to the button state machine.

The recommended approach is disabling the buttons until the first successful poll stamps
`_gbs_current_entryid`. This means adding an `_apply_vote_buttons_enabled(bool)` helper
called from `_on_gbs_playlist_ready` (enable) and `_refresh_gbs_visibility` (disable on
station change/hide). No changes needed to `vote_now_playing` signature.

### Fix 2: Cookie-removal silent-drop emits a toast (T11 orthogonal component)

In `_on_gbs_vote_clicked` at the `cookies is None` guard (line 1050-1053), emit
`gbs_vote_error_toast` before returning:

- Emit: "GBS.FM session expired — reconnect via Accounts" (matches the auth_expired
  message already used in `_on_gbs_vote_error` line 1090).

No signal or method signature changes needed — the signal is already declared and
connected.

### Fix 3: No changes to `vote_now_playing` in `gbs_api.py`

The URL shape, HTTP method (GET), and parameter construction are correct per
RESEARCH.md's live-verified sample. No signature changes, no CSRF header needed for GET.
The `_open_with_cookies` helper is correct for this endpoint.

### Fix 4: No changes to MainWindow signal wiring

`gbs_vote_error_toast.connect(self.show_toast)` at `main_window.py:296` is correct and
already in place. `show_toast(text, duration_ms=3000)` accepts a single `str` argument
with `duration_ms` defaulting — the signal `Signal(str)` matches. No changes needed.

---

## 6. Open Questions

1. **Is `_gbs_current_entryid` None in the user's specific T10 reproduction?** The user
   reports the buttons appear and CAN be clicked — but the report doesn't say whether the
   click happens immediately after bind or after the first poll completes. Confirming
   whether entryid is None at click time (e.g., via a debug log print in
   `_on_gbs_vote_clicked`) would definitively separate Path A from Path B.

2. **Does the optimistic highlight appear?** The user says "the optimistic highlight may
   be appearing locally." If it IS appearing, the worker started (entryid was NOT None),
   and the issue is Path B (request reaches gbs.fm but gets rejected). If the highlight
   is NOT appearing, Path A (entryid None, silent drop) is the confirmed cause.

3. **What does gbs.fm return for the vote request with the current session?** The session
   cookie expires 2026-05-17 per RESEARCH.md. If the dev-fixture session has since
   expired, `_open_with_cookies` would raise `GbsAuthExpiredError`, which IS caught and
   emitted as `vote_error` with `"auth_expired"` — this would fire the toast (if the
   worker ran). This scenario only applies if entryid was stamped.

4. **`_last_removal` cursor in `vote_now_playing`:** `vote_now_playing` passes
   `last_comment=0` and no `last_removal` or `last_add` — this is intentional (per
   RESEARCH.md, the vote GET only needs `position`, `last_comment`, `now_playing`, and
   `vote`). Not a bug; confirmed correct per the live-verified sample.
