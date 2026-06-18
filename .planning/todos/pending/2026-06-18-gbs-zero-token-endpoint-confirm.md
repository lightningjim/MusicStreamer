---
created: 2026-06-18T00:00:00.000Z
title: Confirm provisional GBS /add contract on first live tokens==0 add
area: gbs
resolves_phase: 87B
files:
  - tests/fixtures/gbs_zero_token/add_redirect_zero_token_PLACEHOLDER.txt — replace with real captured payload
  - tests/fixtures/gbs_zero_token/MANIFEST.md — update placeholder row with capture_date, sha256, provenance=real-captured
  - musicstreamer/gbs_api.py — adjust add_song_zero_token() if the real endpoint differs from the provisional /add/<songid> assumption
---

## Condition

First observed tokens==0 add: the no-PII capture hook (`_capture_add_shape()` in `musicstreamer/gbs_api.py`) emits a structured WARN log entry on every `add_song_zero_token()` call. When the user successfully adds a song while at 0 tokens, the hook records the real request/response shape (endpoint path, message_len, message_category — no cookies, no session values per D-18).

## Action

After the first live tokens==0 add is observed in the `_log.warning` output:

1. Confirm the actual endpoint path matches the provisional assumption (`GET /add/<songid>` reuse, server-gated when tokens==0). If it differs (e.g., a separate endpoint or different HTTP method), update `add_song_zero_token()` and adjust the provisional fixture accordingly.
2. Capture the verbatim HTTP/2 response (status line + headers + messages-cookie Set-Cookie value) and write it to `tests/fixtures/gbs_zero_token/add_redirect_zero_token_PLACEHOLDER.txt`. Quote the captured payload exactly — do not paraphrase (per `feedback_mirror_decisions_cite_source.md`).
3. Update `tests/fixtures/gbs_zero_token/MANIFEST.md`: fill in the placeholder row's `capture_date`, `sha256` (of the written file), and change `provenance` from `pending-capture` to `real-captured`. Add a `notes` entry: "Captured on first live tokens==0 add — confirms (or amends) 87B-CONTEXT D-02 provisional contract."
4. If the server's rejection message for the one-at-a-time limit differs from what the existing 48-token fixture implied (e.g., a different messages-cookie text), update `_capture_add_shape()` category logic accordingly and re-run `tests/test_gbs_api.py`.

## Notes

- The capture hook fires on EVERY `add_song_zero_token()` call (not only at tokens==0) — the first tokens==0 entry is identifiable by `message_category=empty` (server allowed add, no error message) OR `message_category=error` (server rejected with a queue/limit message).
- Per D-07 (server is truth), no client-side pre-gating was added; the server's messages-cookie text surfaces verbatim in the dialog. The capture confirms what that text actually says at tokens==0.
- This todo does NOT require code changes unless the provisional endpoint contract (D-02) turns out to be wrong. The common case is: confirm the contract holds, replace the placeholder fixture, close this todo.
- resolves_phase: 87B
