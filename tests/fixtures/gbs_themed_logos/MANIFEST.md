# GBS Themed Logos — Fixture MANIFEST

Phase 87 themed-day logo fixtures harvested for the SHA-256 baseline table (CONTEXT D-04, D-06; GBS-THEME-06).

The baseline structure ships today; per D-04 the "3+ themed / 5+ non-themed" rule (GBS-THEME-06 literal) is relaxed — entries accrete over time as future themed days fire (Halloween 2026, Christmas 2026, etc.). See `todos/2026-05-25-gbs-theme-hash-baseline-grow.md` (created by Plan 87-06) for the follow-up.

## Schema

| Column | Meaning |
|--------|---------|
| `filename` | Filename within this directory |
| `capture_date` | ISO-8601 date the fixture was captured (or `unknown` for browser-cache copies) |
| `sha256` | `hashlib.sha256(file_bytes).hexdigest()` — reproducible by re-hashing the file |
| `theme_label` | Free-text label for the theme; `canonical` for non-themed baseline |
| `source_url` | URL the bytes were fetched from |
| `capture_method` | `cookies` (Phase 76 dev cookies used) / `anonymous` (D-11 fallback) / `browser-cache` |
| `notes` | Any caveats — operator observation, redactions, freshness flags |

## Entries

| filename | capture_date | sha256 | theme_label | source_url | capture_method | notes |
|----------|--------------|--------|-------------|------------|-----------------|-------|
| `2026-05-25_memorial-day_da-troops.png` | 2026-05-25 | `bd2b83fbe2b4bfe9baf8237a8919494e10cc7cf42ad3c42b1fcd605942881be3` | da troops (Memorial Day) | https://gbs.fm/images/logo_3.png | cookies | Live harvest during the 2026-05-25 Memorial Day window. Homepage marquee first pipe-segment was `da troops*` (trailing `*` = "LATEST FAD" marker). |

## Open canonical-baseline entry

No `canonical-001.png` was captured in this harvest — the operator did not have a non-themed `logo_3.png` available from a prior browser cache, and the live URL today serves the themed asset. Plan 87-04's `GBS_LOGO_BASELINE_HASHES` should therefore ship empty or with a placeholder entry; canonical entries will accrete as the operator captures non-themed states in future sessions (the next non-themed window starts whenever "da troops" rolls off gbs.fm's homepage).

## Phase 76 cookie status at harvest time

- `sessionid`: refreshed via `python -m musicstreamer.oauth_helper --mode gbs` at 13:38 local on 2026-05-25; expires 2026-06-08 13:38:35 UTC.
- `csrftoken`: refreshed same call; expires 2027-05-24 13:38:35 UTC.

Cookies remain at `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt` with 0o600 perms — not committed to the repo.
