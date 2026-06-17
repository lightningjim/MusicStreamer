---
phase: 89B-twitch-channel-avatar-fetch
plan: "01"
subsystem: twitch-avatar-fetch
tags: [twitch, helix, avatar, registry, tdd]
dependency_graph:
  requires: [musicstreamer/paths.py, musicstreamer/yt_import.py]
  provides: [musicstreamer/twitch_helix.py, twitch avatar fetcher registration]
  affects: [yt_import._AVATAR_FETCHERS, get_avatar_fetcher("twitch")]
tech_stack:
  added: []
  patterns: [urllib.request.Request scoped headers, Bearer token framing, late import for cycle avoidance]
key_files:
  created:
    - musicstreamer/twitch_helix.py
    - tests/test_twitch_helix.py
  modified:
    - musicstreamer/yt_import.py
decisions:
  - "D-05: fetch_channel_avatar(url) accepts full twitch.tv URL, parses login internally"
  - "D-06: Authorization scoped to Helix Request object only, not global opener (T-89b-01)"
  - "Cycle avoidance: late import of twitch_helix in yt_import after registry functions defined"
  - "No non-square guard: Twitch profile images are always 300x300 (D-05 / RESEARCH Finding #3)"
metrics:
  duration: "6 minutes"
  completed: "2026-06-17"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 89B Plan 01: Twitch Helix Avatar Fetcher Summary

**One-liner:** Twitch channel avatar fetcher via Helix `/users` endpoint — Bearer+Client-Id auth, login parse, CDN download, registered into yt_import registry at module load.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wave 0 RED tests for twitch_helix | 58ed6bd6 | tests/test_twitch_helix.py |
| 2 | Implement twitch_helix + register fetcher | 85d179f2 | musicstreamer/twitch_helix.py, musicstreamer/yt_import.py |

## What Was Built

### musicstreamer/twitch_helix.py (new)

- `_parse_login(url_or_login)` — strips trailing slash, `?query`, `#fragment`, case-folds; handles bare logins and full URLs
- `fetch_channel_avatar(url) -> bytes` — reads `twitch-token.txt` via `paths.twitch_token_path()`, raises `RuntimeError` if absent/empty before any HTTP; builds `urllib.request.Request` with `Authorization: Bearer <token>` and `Client-Id: kimne78kx3ncx6brgo4mv6wki5h1ko` scoped to the Helix call only; fetches CDN image URL with plain `urlopen` (no auth headers); raises on HTTP 401, empty `data[]`, or empty login; no top-level try/except (WR-01 — worker catches)

### musicstreamer/yt_import.py (modified)

- Replaced stub comment at ~L266 with late import + registration:
  ```python
  from musicstreamer import twitch_helix as _twitch_helix
  register_avatar_fetcher("twitch", _twitch_helix.fetch_channel_avatar)
  ```
- Late import placed after `_AVATAR_FETCHERS` and `register_avatar_fetcher` are defined; `twitch_helix` imports only `paths` so no cycle exists

### tests/test_twitch_helix.py (new, 306 lines)

Eight named tests with fixture-locked Helix `/users` response (RESEARCH Finding #1 shape):

- `test_parse_login` — all URL edge cases
- `test_fetch_calls_helix_with_bearer_and_client_id` — request shape, Authorization/Client-Id headers, CDN bytes returned, token NOT on CDN request
- `test_fetch_raises_on_missing_token` — OSError → raise before urlopen
- `test_fetch_raises_on_empty_data` — `{"data": []}` → ValueError
- `test_fetch_raises_on_401` — `HTTPError(401)` propagates
- `test_no_square_guard` — source-grep drift-guard: no `not square`/`width != height`
- `test_token_never_logged` — source-grep drift-guard: no log/print of token variable
- `test_registry_registers_twitch` — `get_avatar_fetcher("twitch") is fetch_channel_avatar`

## Verification

All plan verification checks pass:

```
.venv/bin/python -m pytest tests/test_twitch_helix.py -q  →  8 passed
.venv/bin/python -c "import musicstreamer.yt_import"       →  exits 0
get_avatar_fetcher('twitch') is twitch_helix.fetch_channel_avatar → True
```

Source literals present in `twitch_helix.py`: `kimne78kx3ncx6brgo4mv6wki5h1ko`, `Authorization`, `Bearer`, `Client-Id`, `helix/users`, `profile_image_url`. No `not square` / `width != height` guard present.

## Security Compliance

| Threat | Status |
|--------|--------|
| T-89b-01 (token scope/non-logging) | MITIGATED — Authorization set on Helix Request object only; no global opener; source-grep test asserts no log/print of token var |
| T-89b-02 (SSRF via login parse) | MITIGATED — Helix host is fixed literal; login is query-param only; `_parse_login` strips `?`/`#`/path segments |
| T-89b-SC (no new packages) | ACCEPTED — stdlib only (urllib, json); no install task |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — `fetch_channel_avatar` is fully wired; the registry is live.

## Threat Flags

No new security-relevant surface beyond the plan's threat model.

## Self-Check: PASSED

- `musicstreamer/twitch_helix.py` exists: FOUND
- `tests/test_twitch_helix.py` exists: FOUND
- Commit 58ed6bd6 exists: FOUND
- Commit 85d179f2 exists: FOUND
