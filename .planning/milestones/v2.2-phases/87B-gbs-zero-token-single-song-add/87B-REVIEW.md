---
phase: 87B-gbs-zero-token-single-song-add
reviewed: 2026-06-18T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - musicstreamer/gbs_api.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/ui_qt/gbs_search_dialog.py
  - tests/test_gbs_api.py
  - tests/test_gbs_zero_token_drift_guard.py
  - tests/test_now_playing_panel.py
  - tests/test_main_window_gbs.py
findings:
  critical: 0
  blocker: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 87B: Code Review Report

**Reviewed:** 2026-06-18
**Depth:** standard (ultracode: all dimensions + adversarial refutation)
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Reviewed the additive diff against `bc30a9a3` for the GBS.FM "zero-token single-song add"
feature: `add_song_zero_token()` + `_capture_add_shape()` capture hook in `gbs_api.py`, the
persistent "Add a song" button + `add_song_requested` signal + `trigger_gbs_repoll()` in
`now_playing_panel.py`, the two signal-wiring lines in `main_window.py`, and the worker
call-site swap in `gbs_search_dialog.py`.

Security posture is sound. The T-87B-01 (HIGH) requirement — the capture hook must never log
cookie/session/csrftoken/Authorization/Set-Cookie values or response bodies — is met:
`_capture_add_shape` logs only the songid (an integer), the message *length*, and a derived
category string. The decoded `message` body is never passed to the logger, and the hook
receives nothing else (no cookies, no headers). The dedicated `test_capture_hook_no_pii`
pins the PII-absence contract.

Thread-safety is correct. `submission_completed` is emitted from `_on_submit_finished`, a
main-thread slot reached via the worker's queued `finished` Qt signal — so the chained
`trigger_gbs_repoll()` runs on the GUI thread and its widget touches (`_gbs_poll_cursor`
reset, `_on_gbs_poll_tick`) are safe. The error-path / auth-expiry semantics of the
`submit()` → `add_song_zero_token()` call-site swap are preserved verbatim
(`GbsAuthExpiredError` propagates unchanged; the thin wrapper adds no new catch).

Two WARNING-level findings (a capture-hook category that disagrees with the real consumer's
error taxonomy, and a silently-dropped post-add refresh when a poll is in flight) and two
INFO items follow. No BLOCKER/Critical issues.

## Warnings

### WR-01: Capture-hook `message_category` misclassifies server rejections as "success"

**File:** `musicstreamer/gbs_api.py:1168-1177`
**Issue:** `_capture_add_shape` derives its `message_category` field with a single substring
test: `"error" if "not enough" in message.lower() else "success"`. The actual consumer of
the same `messages`-cookie text, `_on_submit_finished` in `gbs_search_dialog.py:1086-1090`,
treats a much broader set as errors:

```python
is_error = any(kw in msg_lower for kw in (
    "duplicate", "already", "not enough tokens", "enough tokens",
    "quota", "limit", "rate",
)) or "error" in msg_lower
```

So a duplicate-song rejection ("Song already in queue"), a quota/limit/rate rejection, or any
message containing "error" will be recorded by the diagnostic hook as
`message_category=success` while the UI correctly surfaces it as an error. Since the entire
stated purpose of this hook is to capture the add-shape for later diagnosis (D-02/D-18),
a category that disagrees with production's own error taxonomy actively misleads the diagnosis
it exists to support. This is a log-accuracy defect, not a behavior bug — the UI is unaffected.
**Fix:** Reuse the same keyword set as the consumer so the captured category cannot drift from
the displayed outcome:

```python
def _capture_add_shape(songid: int, message: str) -> None:
    msg_lower = message.lower()
    if not message:
        category = "empty"
    elif (any(kw in msg_lower for kw in (
            "duplicate", "already", "not enough", "enough tokens",
            "quota", "limit", "rate")) or "error" in msg_lower):
        category = "error"
    else:
        category = "success"
    _log.warning(
        "gbs.add.zero_token_capture endpoint=/add/%s message_len=%d message_category=%s",
        int(songid), len(message), category,
    )
```

Better still, factor the keyword list into a shared module-level constant so the hook and
`_on_submit_finished` cannot diverge again.

### WR-02: `trigger_gbs_repoll` silently no-ops the post-add refresh when a poll is in flight

**File:** `musicstreamer/ui_qt/now_playing_panel.py:3236-3248`
**Issue:** The guard `and not self._gbs_poll_in_flight()` makes the entire re-poll (including
the `_gbs_poll_cursor = {}` reset) a silent no-op whenever a routine 15s poll happens to be
running at the moment the user's add completes. In that race the cursor is never reset and
no fresh tick is kicked, so the "force full re-fetch so the new song appears" guarantee the
docstring promises does not hold — the just-added song only shows up on the *next* scheduled
tick (up to ~15s later), and only because the normal `adds` event eventually carries it.
The drop is unobservable (no log, no deferred retry), which makes the intermittent latency
hard to diagnose if a user reports it. The in-flight worker that "wins" the race was launched
*before* the add and cannot include the new song.
**Fix:** Set a "repoll pending" flag when the guard rejects, and honor it from
`_on_gbs_playlist_ready` once the in-flight worker completes (reset cursor + kick one more
tick). Minimal alternative — at least log the skipped repoll so the latency is diagnosable:

```python
if self._gbs_poll_in_flight():
    self._gbs_repoll_pending = True   # drained in _on_gbs_playlist_ready
    return
self._gbs_poll_cursor = {}
self._on_gbs_poll_tick()
```

## Info

### IN-01: `add_song_zero_token`/`_capture_add_shape` use only leading-comment docstrings

**File:** `musicstreamer/gbs_api.py:1156-1177`
**Issue:** Every other public function in `gbs_api.py` documents its contract with a triple-
quoted docstring (e.g. `submit()` at 1130, `vote_now_playing()` at 418). The two new functions
use leading `#` comments instead. This is a deliberate trade-off — the GBS-TOKEN-02 drift guard
(`test_gbs_zero_token_drift_guard.py`) bans the word "token" in *string literals* inside the
function body, and a docstring is a string literal, so a docstring mentioning "zero-token"
would trip the guard. The comment form is defensible, but it leaves the public surface
inconsistent and means `help(add_song_zero_token)` yields no docstring.
**Fix:** Optional. If a docstring is wanted, phrase it without the banned word (the function
*name* containing "token" is explicitly allowed by the guard), e.g. `"""Named add path over
submit(); fires the no-PII capture hook. Raises GbsAuthExpiredError on expiry."""`.

### IN-02: Capture-hook category logic is duplicated knowledge with no shared source

**File:** `musicstreamer/gbs_api.py:1176` and `musicstreamer/ui_qt/gbs_search_dialog.py:1087-1090`
**Issue:** The error-vs-success determination for a GBS `messages`-cookie string now lives in
two places with two different implementations (see WR-01). Even after WR-01 is fixed by copying
the keyword set, the two copies will drift again on the next change. This is the underlying
duplication that produced WR-01.
**Fix:** Extract the keyword tuple (and ideally a `_classify_add_message(message) -> str`
helper) into `gbs_api.py` and have both `_capture_add_shape` and `_on_submit_finished` call it.

---

_Reviewed: 2026-06-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard (ultracode)_
