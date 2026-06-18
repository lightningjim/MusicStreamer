---
status: partial
phase: 87B-gbs-zero-token-single-song-add
source: [87B-VERIFICATION.md]
started: 2026-06-18
updated: 2026-06-18
---

## Current Test

[awaiting human testing]

## Tests

### 1. "Add a song" button appears and opens the search dialog (live GBS.FM)
expected: Bind a GBS.FM station and ensure you are logged in (cookies present). The "Add a song" button appears in the now-playing panel (just below the GBS active-playlist / expiry widget area), regardless of your current token count. Its tooltip reads "Add a song to the GBS.FM queue". Clicking it opens the existing GBS search-and-submit dialog. Nowhere in the button label, tooltip, or surrounding copy does the word "token" appear.
result: [pending]

### 2. Normal-token add succeeds and the queue re-polls
expected: With tokens > 0, search for and confirm a song in the dialog. The dialog shows the server's success message and closes; the now-playing GBS playlist widget re-polls and the newly-added song appears (within one poll cycle). The button remains visible afterward (no hide-after-add).
result: [pending]

### 3. Server-rejection message surfaces verbatim
expected: Trigger a server rejection (e.g. attempt to add a duplicate, or a song that violates a server rule). The dialog surfaces the server's `messages`-cookie text verbatim (server-is-truth); the app does not pre-block the attempt with its own logic.
result: [pending]

### 4. [DEFERRED — capture-on-use] Zero-token free add when tokens reach 0
expected: When your GBS.FM token balance naturally reaches 0 (you are currently at 48; no on-demand path to 0), bind GBS.FM and use "Add a song" to add your one free song. Confirm: (a) the add succeeds via the provisional `/add/<songid>` path, (b) the no-PII capture hook records the real `tokens==0` request line + decoded message to the diagnostic log WITHOUT any cookie/session value, and (c) update `tests/fixtures/gbs_zero_token/` with the captured real response (replacing the PLACEHOLDER) and close the follow-up todo `.planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md`. This validates/adjusts the provisional contract (D-01/D-02/D-03). Until then this item stays deferred — it is NOT a phase gap.
result: [pending — deferred until tokens==0 occurs naturally]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
