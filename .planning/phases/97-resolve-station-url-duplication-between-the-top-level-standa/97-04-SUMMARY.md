---
phase: 97-resolve-station-url-duplication-between-the-top-level-standa
plan: "04"
subsystem: data-consumers
tags: [wave-3, canonical, d-07, url-helpers, aa-live, station-filter-proxy, now-playing-panel, add-sibling-dialog]
dependency_graph:
  requires:
    - "97-01 (Wave-0 RED tests — test_canonical_url_drives_aa_sibling_detection)"
    - "97-02 (Station.canonical_url property)"
    - "97-03 (EditStationDialog canonical rewire)"
  provides:
    - "All 5 D-07 metadata/derivation consumers keyed off Station.canonical_url"
    - "url_helpers.find_aa_siblings candidate check uses canonical_url"
    - "url_helpers.suggest_similar current_first_url uses canonical_url"
    - "aa_live.get_di_channel_key uses canonical_url"
    - "station_filter_proxy.filterAcceptsRow uses canonical_url"
    - "now_playing_panel._refresh_siblings uses canonical_url"
    - "add_sibling_dialog fallback uses canonical_url"
  affects:
    - musicstreamer/url_helpers.py
    - musicstreamer/aa_live.py
    - musicstreamer/ui_qt/station_filter_proxy.py
    - musicstreamer/ui_qt/now_playing_panel.py
    - musicstreamer/ui_qt/add_sibling_dialog.py
tech_stack:
  added: []
  patterns:
    - "Phase 97 D-07: all metadata/derivation consumers key off Station.canonical_url property"
    - "D-05: playback (preferred_stream_id / order_streams in player.py) deliberately untouched"
key_files:
  created: []
  modified:
    - path: musicstreamer/url_helpers.py
      purpose: "find_aa_siblings candidate check + suggest_similar current_first_url → canonical_url"
    - path: musicstreamer/aa_live.py
      purpose: "get_di_channel_key → canonical_url; removed streams getattr guard (canonical_url handles empty)"
    - path: musicstreamer/ui_qt/station_filter_proxy.py
      purpose: "filterAcceptsRow: streams[0].url → canonical_url; simplified guard (url && _is_aa_url)"
    - path: musicstreamer/ui_qt/now_playing_panel.py
      purpose: "_refresh_siblings: streams[0].url → canonical_url with empty-string visibility guard; stale comments updated"
    - path: musicstreamer/ui_qt/add_sibling_dialog.py
      purpose: "fallback: streams[0].url → canonical_url; stale comments updated"
decisions:
  - "Phase 97 D-07: all 5 external metadata/derivation consumers use canonical_url — one rule, one source"
  - "Phase 97 D-05: player.py (order_streams + preferred_stream_id) deliberately not modified"
  - "Stale streams[0].url comment references in docstrings updated to canonical_url to avoid future confusion"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-24"
  tasks_completed: 3
  tasks_total: 3
  files_created: 0
  files_modified: 5
---

# Phase 97 Plan 04: External Consumer canonical_url Repoint Summary

**One-liner:** All 5 D-07 metadata/derivation consumers (url_helpers, aa_live, station_filter_proxy, now_playing_panel, add_sibling_dialog) switched from positional streams[0].url to Station.canonical_url — playback (player.py) untouched, all 173 tests green.

## What Was Built

Completed the single-source-of-truth read side for Phase 97: every metadata consumer now keys off the canonical stream URL as determined by `Station.canonical_url` (built in Plan 02). This is the final wave of Phase 97, closing all D-07 call sites.

### Task 1 — url_helpers.py + aa_live.py (commit `07038beb`)

Two changes in `musicstreamer/url_helpers.py`:
- `find_aa_siblings` (line ~216): `cand_url = st.streams[0].url` → `cand_url = st.canonical_url`
- `suggest_similar` (line ~358): `current_first_url=current_station.streams[0].url` → `current_first_url=current_station.canonical_url`

One change in `musicstreamer/aa_live.py` (get_di_channel_key):
- Replaced the `streams = getattr(station, "streams", None) or []` + `if not streams:` + `url = streams[0].url` block with `url = station.canonical_url` and updated the guard to `if not url or not _is_aa_url(url): return None` (the `canonical_url` property handles the empty-streams case internally).

All 24 aa-siblings + url-helpers canonical/sibling tests GREEN.

### Task 2 — station_filter_proxy.py + now_playing_panel.py + add_sibling_dialog.py (commit `d9b9ea28`)

`musicstreamer/ui_qt/station_filter_proxy.py` (filterAcceptsRow ~179):
- Replaced `streams = getattr(station, "streams", None) or []; if streams: url = streams[0].url` with `url = station.canonical_url` and updated gate to `if url and _is_aa_url(url):`

`musicstreamer/ui_qt/now_playing_panel.py` (_refresh_siblings ~2433):
- Replaced `if self._station is None or not self._station.streams:` guard + `current_url = self._station.streams[0].url` with `if self._station is None:` guard + `current_url = self._station.canonical_url` + `if not current_url: self._sibling_label.setVisible(False); return`
- Lines 2796/2803 (playback `_streams[0]` and `station_streams[0]`) left untouched (D-05)

`musicstreamer/ui_qt/add_sibling_dialog.py` (fallback ~286):
- Replaced `elif self._current_station.streams: current_url = self._current_station.streams[0].url or ""` with `else: current_url = self._current_station.canonical_url`

196 station_filter_proxy + now_playing_panel + add_sibling_dialog tests GREEN.

### Task 3 — Regression guard + stale comment cleanup (commit `203418cf`)

- Ran player suite: 173 tests pass, player.py unmodified (D-05 confirmed)
- All `streams[0].url` hits in musicstreamer/ now limited to: zero — all D-07 sites clean
- Stale comment references to `streams[0].url` in add_sibling_dialog.py (3 comments), now_playing_panel.py (2 comments), and edit_station_dialog.py (1 comment) updated to reference `canonical_url` to avoid future confusion

## Deviations from Plan

None — plan executed exactly as written.

## Threat Mitigations Applied

| Threat | Applied |
|--------|---------|
| T-97-08: Input validation (canonical_url feeding _is_aa_url / _aa_slug_from_url) | Same URL parsing as before; only value source changed |
| T-97-09: Integrity (risk of accidentally repointing playback to canonical) | Task 3 confirms player.py unmodified; git diff empty; 173 player tests pass |

## Known Stubs

None — all 5 D-07 consumers are fully wired to canonical_url. No placeholder logic remains.

## Self-Check: PASSED

### Files exist:
- FOUND: musicstreamer/url_helpers.py
- FOUND: musicstreamer/aa_live.py
- FOUND: musicstreamer/ui_qt/station_filter_proxy.py
- FOUND: musicstreamer/ui_qt/now_playing_panel.py
- FOUND: musicstreamer/ui_qt/add_sibling_dialog.py

### Commits exist:
- FOUND: `07038beb` — feat(97-04): repoint AA-derivation consumers to canonical_url
- FOUND: `d9b9ea28` — feat(97-04): repoint UI consumers to canonical_url
- FOUND: `203418cf` — refactor(97-04): update stale streams[0].url references in comments

### Acceptance criteria verified:
- `grep -c "canonical_url" musicstreamer/url_helpers.py` = 2 (>= 2)
- `grep -c "canonical_url" musicstreamer/aa_live.py` = 1 (>= 1)
- `grep -c "streams\[0\].url" musicstreamer/url_helpers.py` = 0
- `grep -c "streams\[0\].url" musicstreamer/aa_live.py` = 0
- `grep -c "canonical_url" musicstreamer/ui_qt/station_filter_proxy.py` = 1 (>= 1)
- `grep -c "canonical_url" musicstreamer/ui_qt/now_playing_panel.py` = 1 (>= 1)
- `grep -c "canonical_url" musicstreamer/ui_qt/add_sibling_dialog.py` = 1 (>= 1)
- `grep -c "streams\[0\]" musicstreamer/ui_qt/now_playing_panel.py` = 4 (>= 1 — playback reads preserved)
- `git diff --name-only -- musicstreamer/player.py` = empty (D-05 playback unchanged)
- 173 player + aa-siblings + url-helpers tests GREEN
- 196 station_filter_proxy + now_playing_panel + add_sibling_dialog tests GREEN
