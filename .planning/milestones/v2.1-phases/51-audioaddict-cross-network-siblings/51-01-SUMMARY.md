---
phase: 51-audioaddict-cross-network-siblings
plan: 01
subsystem: ui-helpers
tags: [audioaddict, url-parsing, sibling-detection, pure-helper, tdd]

# Dependency graph
requires:
  - phase: 17-audioaddict-import
    provides: NETWORKS catalog (slug/domain/name) — sort-order source
  - phase: 36-gtk-cutover
    provides: musicstreamer/url_helpers.py module (extracted, Qt-free)
  - phase: 39-aa-channel-key-prefix-strip
    provides: _aa_channel_key_from_url strips zr-prefix and _hi/_med/_low suffix
provides:
  - find_aa_siblings(stations, current_station_id, current_first_url) -> list[tuple[str, int, str]]
  - 12 unit tests pinning the cross-network sibling-detection contract
affects:
  - 51-03 (renderer — consumes the tuple list to build the "Also on:" QLabel HTML)
  - 51-04 (dialog wiring — calls find_aa_siblings from EditStationDialog._populate)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure data helper extending url_helpers.py (no new module — D-01, no DB schema)"
    - "Tuple shape (network_slug, station_id, station_name) for cheap unpacking by renderers"
    - "Internal sort-by-NETWORKS-index via {slug: i} dict — O(1) lookup"

key-files:
  created:
    - tests/test_aa_siblings.py
  modified:
    - musicstreamer/url_helpers.py

key-decisions:
  - "Extended url_helpers.py rather than creating aa_siblings.py (rejected: would duplicate dependencies on _is_aa_url/_aa_slug_from_url/NETWORKS)"
  - "Return tuple[str, int, str] (network_slug, station_id, station_name) over dict — cheaper unpacking in Plan 03's QLabel renderer; renderer handles HTML escaping"
  - "Sort key is enumerate(NETWORKS) into a {slug: i} dict — O(1) per-candidate lookup, deterministic across opens"
  - "Empty-streams candidates filtered defensively (Repo populates streams, but tests construct Station(streams=[]) directly — must not IndexError)"
  - "Same-network filter applied BEFORE channel_key comparison (cheaper short-circuit)"

patterns-established:
  - "AA helper functions stay in url_helpers.py — single module for all AA URL/data transforms"
  - "find_aa_siblings inherits the existing 'return None / return []' silent-failure convention from _aa_channel_key_from_url"

requirements-completed: []  # BUG-02 advanced but not closed — Plans 03/04 ship the user-visible UI surface

# Metrics
duration: 4min
completed: 2026-04-28
---

# Phase 51 Plan 01: find_aa_siblings cross-network sibling helper Summary

**Pure helper find_aa_siblings() that derives AA siblings from channel_key on-demand — no DB schema change, no Qt coupling, 12 unit tests pinning the cross-network contract.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-28T14:55:28Z
- **Completed:** 2026-04-28T14:59:15Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 2 (1 created, 1 extended)

## Accomplishments

- `find_aa_siblings(stations, current_station_id, current_first_url) -> list[tuple[network_slug, station_id, station_name]]` added to `musicstreamer/url_helpers.py`
- 12 unit tests in `tests/test_aa_siblings.py` covering: cross-network match (DI.fm + ZenRadio), zr-prefix stripping, self-by-id exclusion, same-network exclusion, non-AA filtering (current and candidates), unparseable-URL filtering, empty-streams defense, NETWORKS-order sort, station-name passthrough
- Zero Qt/UI imports — helper is fully testable via pure data in/out (`grep` on actual import lines confirms 0)
- Sort order matches NETWORKS declaration: di → radiotunes → jazzradio → rockradio → classicalradio → zenradio
- All 27 tests pass (12 new + 15 existing `test_aa_url_detection`); pre-existing unrelated failures in mpris2/smtc/twitch/station_list_panel reproduce on the prior commit and are documented in `deferred-items.md`

## Task Commits

1. **Task 1: RED — failing unit tests for find_aa_siblings** — `66d0b9b` (test)
2. **Task 2: GREEN — implement find_aa_siblings** — `2996553` (feat)

_Plan metadata commit follows separately._

## Files Created/Modified

- `tests/test_aa_siblings.py` (created, 129 lines) — 12 pure unit tests, modeled exactly on `tests/test_aa_url_detection.py`. One assertion per test, no Qt fixtures, no MagicMock. Module-level `_mk(id_, name, url)` factory for minimal Station+StationStream construction.
- `musicstreamer/url_helpers.py` (extended, +63 lines) — appended `find_aa_siblings` after `_aa_slug_from_url`. No new imports — reuses `_is_aa_url`, `_aa_slug_from_url`, `_aa_channel_key_from_url`, and `NETWORKS` already in module scope.
- `.planning/phases/51-audioaddict-cross-network-siblings/deferred-items.md` (created) — logs 9 pre-existing test failures discovered during the regression run, none related to Phase 51 changes.

## Decisions Made

- **Extended url_helpers.py over creating `aa_siblings.py`** — All four dependencies (`_is_aa_url`, `_aa_slug_from_url`, `_aa_channel_key_from_url`, `NETWORKS`) already live in `url_helpers.py`. A new module would have forced either circular imports or duplicated re-exports. Three lines of new public surface in one existing module is cleaner.
- **Tuple shape `(network_slug, station_id, station_name)`** — picked over a dict for cheaper unpacking in Plan 03's renderer (`for slug, sid, name in siblings:` reads cleaner than `for s in siblings: s["slug"], s["id"], s["name"]`). Indexed access in tests (`siblings[0][0] == "zenradio"`) is also concise.
- **Sort key via `{slug: i for i, n in enumerate(NETWORKS)}`** — O(1) per-candidate lookup, single computation per call. Internal 4-tuple `(sort_index, slug, id, name)` is collected, sorted, then projected back to the public 3-tuple shape.
- **Same-network exclusion before channel_key comparison** — same-network match is a single `==` against the already-computed `current_slug`; channel_key derivation is a `urllib.parse.urlparse`. Cheaper to short-circuit on the slug.
- **HTML escaping is Plan 03's responsibility** — `find_aa_siblings` returns raw `Station.name` strings. Per the threat-model row T-51-01-02, names are local-only data and the rendering boundary (Plan 03's `setTextFormat(Qt.RichText)` QLabel) owns the `html.escape` call.

## Deviations from Plan

None — plan executed exactly as written.

The acceptance criterion `grep -c 'from PySide6\|from PyQt\|from musicstreamer.ui' musicstreamer/url_helpers.py returns 0` matched a pre-existing **docstring** reference to `musicstreamer/ui/edit_dialog.py` (line 3, a Phase 36 GTK-cutover comment) — not an actual import. A stricter regex on import statements only (`grep -E '^(import|from).*PySide6|...'`) returns 0 actual imports. The "zero Qt coupling" truth predicate is satisfied. No code change needed.

## Issues Encountered

- **Pre-existing test failures during full-suite regression run** — `tests/test_media_keys_mpris2.py`, `tests/test_media_keys_smtc.py`, `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode`, `tests/test_twitch_auth.py` and 4 others fail in this environment. Confirmed pre-existing by re-running on the prior commit (66d0b9b, RED-only state) with the GREEN implementation stashed — same failures reproduce. None touch `url_helpers.py` or Phase 51 code paths. Logged to `deferred-items.md` per executor scope-boundary rule.
- **`uv.lock` modified by `uv run`** — running `uv run --with pytest pytest …` updated `uv.lock` (lock-file refresh from the `--with pytest` install). Reverted with `git checkout -- uv.lock` between operations; not committed as part of this plan.

## User Setup Required

None — pure helper, no external service configuration.

## Next Phase Readiness

**Plan 51-02 (sort-order helper / display-name resolver, parallel with 51-01):** independent — no dependency.

**Plan 51-03 (HTML renderer for the "Also on:" QLabel):** ready — consumes `find_aa_siblings` directly. The renderer must `html.escape` station names per the threat model T-51-01-02 (Plan 51-03's responsibility — this helper returns raw strings).

**Plan 51-04 (EditStationDialog wiring):** ready — call `find_aa_siblings(self._repo.list_stations(), self._station.id, streams[0].url)` in `_populate` after the existing logo refresh. Returns `[]` for non-AA stations / no siblings, which the renderer can use as the "hide section" signal (D-04 / D-06).

## Self-Check: PASSED

- **Files:** `tests/test_aa_siblings.py` FOUND, `musicstreamer/url_helpers.py::find_aa_siblings` FOUND
- **Commits:** `66d0b9b` (test) FOUND, `2996553` (feat) FOUND in git log
- **Tests:** `pytest tests/test_aa_siblings.py tests/test_aa_url_detection.py` → 27 passed, 0 failed

---
*Phase: 51-audioaddict-cross-network-siblings*
*Completed: 2026-04-28*
