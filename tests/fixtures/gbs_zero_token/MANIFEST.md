# GBS Zero-Token Add — Fixture MANIFEST

Phase 87B provisional `/add/<songid>` response fixtures. The `add_redirect_response_48tokens.txt`
fixture captures the observable shape at 48 tokens (normal-token add). The real `tokens==0`
fixture is captured on first live use via the no-PII capture hook in `gbs_api._capture_add_shape()`
and committed as the PLACEHOLDER row (resolves_phase: 87B — per 87B-CONTEXT D-02/D-03).

## Schema

| Column | Meaning |
|--------|---------|
| `filename` | Filename within this directory |
| `capture_date` | ISO-8601 date the fixture was captured |
| `sha256` | `hashlib.sha256(file_bytes).hexdigest()` of file bytes |
| `source_url` | URL the bytes were fetched from |
| `capture_method` | `cookies` (Phase 76 dev cookies used) / `synthetic` / `pending-capture` |
| `provenance` | `real-captured` / `synthetic` / `pending-capture` |
| `notes` | Observed response shape / parser hints / provenance notes |

## Entries

| filename | capture_date | sha256 | source_url | capture_method | provenance | notes |
|----------|--------------|--------|------------|----------------|------------|-------|
| `add_redirect_response_48tokens.txt` | 2026-06-18 | `n/a-verbatim-copy` | https://gbs.fm/add/<songid> | cookies | real-captured | Observable /add shape at 48 tokens; provisional for zero-token contract per 87B-CONTEXT D-02. HTTP/2 302 + location: /playlist + set-cookie: messages= line. Fixture-locks the GBS-TOKEN-05 observable shape for unit tests in tests/test_gbs_api.py. |
| `add_redirect_zero_token_PLACEHOLDER.txt` | — | — | https://gbs.fm/add/<songid> | pending-capture | pending-capture | resolves_phase: 87B — to be populated on first live tokens==0 add per D-03. The no-PII capture hook (_capture_add_shape in gbs_api.py) records message_len/message_category on each add; the real response fixture should be committed here once observed in the wild. |
