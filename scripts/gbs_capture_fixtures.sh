#!/usr/bin/env bash
# Phase 60 — Capture gbs.fm response fixtures for tests/fixtures/gbs/.
# Re-runnable; reads the dev cookies fixture from ~/.local/share/musicstreamer/dev-fixtures/.
# Outputs are sanitized: real csrftoken/sessionid values replaced with PLACEHOLDERs in cookies_valid.txt.
#
# Usage: bash scripts/gbs_capture_fixtures.sh
set -euo pipefail

COOKIES="${HOME}/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt"
OUT="tests/fixtures/gbs"
BASE="https://gbs.fm"

if [[ ! -f "$COOKIES" ]]; then
  echo "ERROR: dev cookies missing at $COOKIES — see 60-CONTEXT.md D-04a." >&2
  exit 1
fi

mkdir -p "$OUT"

# Pick a stable now_playing entryid by reading /api/nowplaying first.
ENTRYID="$(curl -sS -b "$COOKIES" "$BASE/api/nowplaying")"
echo "Captured entryid: $ENTRYID"

# 1. /ajax cold-start
curl -sS -b "$COOKIES" "$BASE/ajax?position=0&last_comment=0&last_removal=0&last_add=0&now_playing=0" > "$OUT/ajax_cold_start.json"

# 2. /ajax steady-state
curl -sS -b "$COOKIES" "$BASE/ajax?position=200&last_comment=0&last_removal=0&last_add=0&now_playing=$ENTRYID" > "$OUT/ajax_steady_state.json"

# 3. /ajax vote=3 (set)
curl -sS -b "$COOKIES" "$BASE/ajax?vote=3&now_playing=$ENTRYID&position=0&last_comment=0" > "$OUT/ajax_vote_set.json"

# 4. /ajax vote=0 (clear)
curl -sS -b "$COOKIES" "$BASE/ajax?vote=0&now_playing=$ENTRYID&position=0&last_comment=0" > "$OUT/ajax_vote_clear.json"

# 5. /ajax with no cookies → 302 to /accounts/login/
curl -sS -i "$BASE/ajax" | head -20 > "$OUT/ajax_login_redirect.txt"

# 6. Home page playlist table (just the relevant block)
curl -sS -b "$COOKIES" "$BASE/" > "$OUT/home_playlist_table.html"

# 7-9. Search (p1, p2, empty)
curl -sS -b "$COOKIES" "$BASE/search?query=test&page=1" > "$OUT/search_test_p1.html"
curl -sS -b "$COOKIES" "$BASE/search?query=test&page=2" > "$OUT/search_test_p2.html"
curl -sS -b "$COOKIES" "$BASE/search?query=zzzzzzzzznoresults&page=1" > "$OUT/search_empty.html"

# 10. /add/<id> redirect with messages cookie (DESTRUCTIVE — adds song 88135 to live playlist).
# Skip by default; uncomment the next line and pick a fresh songid to capture.
# curl -sS -i -b "$COOKIES" "$BASE/add/88135" | head -30 > "$OUT/add_redirect_response.txt"

# 11-13. Auxiliary plain-text endpoints
curl -sS -b "$COOKIES" "$BASE/api/nowplaying" > "$OUT/api_nowplaying.txt"
curl -sS -b "$COOKIES" "$BASE/api/metadata" > "$OUT/api_metadata.txt"
curl -sS -b "$COOKIES" "$BASE/api/vote?songid=88135&vote=0" > "$OUT/api_vote_legacy.txt" || true

echo "Done. Fixtures written to $OUT/"
echo "REMEMBER: sanitize cookies_valid.txt manually — replace real sessionid/csrftoken values with PLACEHOLDERs."
echo "REMEMBER: hand-create the 2 validator-rejection cookie fixtures (cookies_invalid_no_sessionid.txt, cookies_invalid_wrong_domain.txt) — these are NOT captured because they're hand-crafted error cases for GBS-01b."
