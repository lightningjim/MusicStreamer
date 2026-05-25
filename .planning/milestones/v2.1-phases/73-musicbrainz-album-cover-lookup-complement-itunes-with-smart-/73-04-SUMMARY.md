---
phase: 73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-
plan: 04
subsystem: ui
tags: [edit-station-dialog, settings-export, now-playing-panel, qcombobox, cover-art-source, round-trip]

# Dependency graph
requires:
  - phase: 73
    provides: Station.cover_art_source field (Plan 01), MB+CAA worker module (Plan 02), source-aware fetch_cover_art router + Repo.update_station kwarg (Plan 03)
provides:
  - EditStationDialog cover_art_source_combo (3 entries; non-editable) reading station.cover_art_source on open
  - Save path passes cover_art_source kwarg to repo.update_station — single call site, gated by source-grep test
  - settings_export round-trips cover_art_source on export, INSERT, and REPLACE
  - Forward-compat: pre-Phase-73 ZIPs (missing key) default to 'auto' on both INSERT and REPLACE
  - NowPlayingPanel._fetch_cover_art_async forwards self._station.cover_art_source as source kwarg
  - Defensive 'auto' default for None station / station-lacks-attribute / attribute-is-None
affects: [73-05 (UAT script — selector visible, ZIP round-trips), future phase ART-04 (station-art expansion may reuse selector pattern)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "QComboBox enum-selector idiom for fixed-vocabulary per-station prefs (mirrors provider_combo shape but non-editable)"
    - "Source-grep test gate for kwarg-must-be-passed contracts (mirrors ART-MB-15/16 pattern)"
    - "Forward-compat additive-field default via data.get(key) or default in settings_export"

key-files:
  created: []
  modified:
    - musicstreamer/ui_qt/edit_station_dialog.py — combo widget + populate + save kwarg + dirty-snapshot key
    - musicstreamer/ui_qt/now_playing_panel.py — _fetch_cover_art_async pass-through source kwarg
    - musicstreamer/settings_export.py — _station_to_dict + _insert_station + _replace_station extended
    - tests/test_edit_station_dialog.py — 6 new tests
    - tests/test_settings_export.py — 5 new tests
    - tests/test_now_playing_panel.py — 4 new tests

key-decisions:
  - "Combo placement: immediately after icy_checkbox in the QFormLayout (D-06)"
  - "Non-editable combo (3 fixed values per D-01) — contrast with editable provider_combo"
  - "currentData() returns the persisted string form ('auto' | 'itunes_only' | 'mb_only') directly — no display→storage translation table needed"
  - "cover_art_source passed as kwarg to repo.update_station, not positional — Plan 03's signature explicitly added it as keyword-default; positional would break the test_update_station_omitting_cover_art_source_resets_to_auto lock contract"
  - "Pitfall 9 REPLACE side: missing key resets to 'auto' (not preserves existing). Uniform with how icy_disabled is treated — `data.get(field, default)` applies on both INSERT and REPLACE. Documented behavior for pre-73 ZIPs."
  - "cover_art_ready Signal kept as Signal(str) per RESEARCH OQ-3 — no widening to dict; matches existing pattern, no race regression"
  - "Defensive `or 'auto'` after currentData() in _on_save (guards against currentData returning None if combo is unexpectedly empty)"

patterns-established:
  - "Source-grep kwarg-gate test: scan source file for every `target(`, scan forward up to N lines tracking paren depth, assert required kwarg substring appears in the call's argument span. Defense-in-depth against future copy-paste regression."
  - "Defensive station-attribute access in _fetch_cover_art_async: `getattr(self._station, 'cover_art_source', 'auto') if self._station else 'auto'` covers None station + missing attribute + None value with one expression"

requirements-completed: [ART-MB-10, ART-MB-12]

# Metrics
duration: ~30min
completed: 2026-05-13
---

# Phase 73 Plan 04: UI + settings round-trip Summary

**Per-station cover-art-source preference wired end-to-end via QComboBox in EditStationDialog, round-tripped through settings_export ZIP, and forwarded from NowPlayingPanel to the Plan 03 source-aware router.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-05-14T00:29:00Z (approx)
- **Completed:** 2026-05-14T00:59:43Z
- **Tasks:** 3 (each TDD: RED then GREEN — 6 commits total)
- **Files modified:** 6 (3 production + 3 test)
- **New tests:** 15 (6 dialog + 5 settings + 4 panel)

## Accomplishments

- EditStationDialog now exposes a 3-entry QComboBox labeled "Cover art source:" immediately after the ICY checkbox, with display strings "Auto (iTunes → MusicBrainz fallback)" / "iTunes only" / "MusicBrainz only" mapping to storage values `auto` / `itunes_only` / `mb_only`. Dialog reads `station.cover_art_source` to set initial index, includes the combo in dirty-snapshot, and passes `cover_art_source=` as a kwarg to `repo.update_station` on save.
- Defense-in-depth source-grep test (`test_every_update_station_call_passes_cover_art_source_kwarg`) enumerates every `repo.update_station(` call site in `edit_station_dialog.py` and asserts each is followed within 30 lines by `cover_art_source=` inside the same parenthesis group. Guards against future copy-paste of an update_station call that would silently regress to 'auto' via Plan 03's lock-test contract.
- `settings_export.py` round-trips the field through three sites: `_station_to_dict` emits the key (with getattr defensive default), `_insert_station` extends INSERT with the column, `_replace_station` extends UPDATE SET. Both import paths apply `data.get('cover_art_source') or 'auto'` for Pitfall 9 forward-compat — pre-Phase-73 ZIPs default to 'auto' on both INSERT and REPLACE.
- `NowPlayingPanel._fetch_cover_art_async` widens its `fetch_cover_art(...)` call to forward `source=` derived from `self._station.cover_art_source`. Defensive default 'auto' covers (a) no bound station, (b) station object lacking the attribute (legacy in-memory Station), (c) explicit None value.

## Task Commits

Each task was committed atomically as TDD RED/GREEN pairs:

1. **Task 1 RED:** add failing dialog tests — `d29a3e8` (test)
2. **Task 1 GREEN:** add cover_art_source QComboBox to EditStationDialog — `cf64e78` (feat)
3. **Task 2 RED:** add failing settings_export tests — `456d9f3` (test)
4. **Task 2 GREEN:** round-trip cover_art_source through settings_export ZIP — `0dee56a` (feat)
5. **Task 3 RED:** add failing NowPlayingPanel tests — `c18c18d` (test)
6. **Task 3 GREEN:** pass station.cover_art_source through _fetch_cover_art_async — `fb73677` (feat)

## Files Created/Modified

- `musicstreamer/ui_qt/edit_station_dialog.py` — 3-entry QComboBox `cover_art_source_combo` created after icy_checkbox row (line ~406); `_populate` reads `station.cover_art_source` (line ~533) with getattr default; `_snapshot_form_state` includes the combo's currentData (line ~603) so dirty detection covers flips; `_on_save` reads currentData (line ~1389) and passes `cover_art_source=` as kwarg to repo.update_station (line ~1409). Single call site verified.
- `musicstreamer/ui_qt/now_playing_panel.py` — `_fetch_cover_art_async` (lines 1176-1196) reads `self._station.cover_art_source` with getattr defensive default 'auto', forwards as `source=source` kwarg to `fetch_cover_art`. Token-guard, signal payload, and `_on_cover_art_ready` slot unchanged.
- `musicstreamer/settings_export.py` — `_station_to_dict` emits `cover_art_source` with getattr default; `_insert_station` extends INSERT column list and values tuple (Pitfall 9 default); `_replace_station` extends UPDATE SET (Pitfall 9 default).
- `tests/test_edit_station_dialog.py` — 6 new tests: combo exists / shape, populate from mb_only Station, populate auto default, save passes kwarg, dirty when flipped, every-update_station-passes-kwarg source-grep gate.
- `tests/test_settings_export.py` — 5 new tests: export payload contains key, INSERT persists, REPLACE persists, missing-key on INSERT defaults to auto, missing-key on REPLACE defaults to auto.
- `tests/test_now_playing_panel.py` — 4 new tests: source kwarg=mb_only, source kwarg=itunes_only, defaults to auto when no station, defaults to auto when station lacks attribute (SimpleNamespace).

## Decisions Made

- **Non-editable combo (D-01 strictness):** The 3 cover-art-source values are fixed enums; an editable combo would allow arbitrary string entry and pollute the storage column. Mirrors how a typical settings dropdown should behave for a closed vocabulary. Contrast with `provider_combo` (editable for free-text providers like new SomaFM stations).
- **Storage-string-as-itemData:** Combo `addItem(displayString, dataValue)` stores `"auto" | "itunes_only" | "mb_only"` as itemData — exactly the strings the DB schema accepts. `currentData()` returns the persisted form directly. No display→storage lookup table; simpler than a parallel dict.
- **Pitfall 9 REPLACE-side default = 'auto' (not preserve-existing):** Uniform with how `icy_disabled` is treated when its key is absent from the payload (`data.get('icy_disabled', False)`). A pre-73 export does not carry the field, so import always resets the column to 'auto' on REPLACE. Documented as expected behavior; alternative (preserve-on-missing) would require detecting pre-73 vs 73+ payloads which is out of scope for an additive-field design.
- **`or "auto"` after `currentData()` in _on_save:** Belt-and-suspenders defensive default. `currentData()` could theoretically return `None` if the combo is empty (which shouldn't happen given widget creation always addItems three entries, but defensive coding is cheap and the Plan 03 router will validate anyway).

## Deviations from Plan

None — plan executed exactly as written. Each task's action section was followed verbatim:

- Task 1: combo widget at the documented line (after icy_checkbox row), populate at line ~533, save read + kwarg pass-through at line ~1393, dirty-snapshot key added between `icy` and `tags`, all 5 new tests + the source-grep gate test added.
- Task 2: `_station_to_dict` extended, INSERT column list + values extended, REPLACE UPDATE SET extended. All 5 new tests added.
- Task 3: `_fetch_cover_art_async` widened with no other changes — token-guard, signal payload, slot, `on_title_changed` all untouched. 4 new tests added.

**Total deviations:** 0 — no auto-fixes needed; no architectural decisions surfaced.

## Issues Encountered

- **Pre-existing unrelated test failures:** The full `pytest tests/` run shows 18 failures + 18 errors in files I did not touch: `test_main_window_media_keys`, `test_ui_qt_scaffold`, `test_media_keys_mpris2`, `test_main_window_gbs`, `test_import_dialog_qt`, `test_station_list_panel`, `test_twitch_auth`, `tests/ui_qt/test_main_window_node_indicator`. Confirmed pre-existing via stash-and-rerun: same failures without my Plan 04 changes. Out of scope per scope-boundary rule (only auto-fix issues directly caused by current task's changes). Not logged to deferred-items.md because they are not new discoveries — they are existing background-noise failures the project has been tolerating.
- **Signal-source-deleted thread-cleanup warning:** A pre-existing test-teardown warning (panel goes out of scope while a real iTunes worker thread is still in flight, callback fires after QObject destruction) appears in `test_now_playing_panel.py` runs both before and after my changes. Pre-existing; not introduced by Plan 04.

## User Setup Required

None — no external service configuration required. All changes are internal (UI widget + serialization + signal wiring).

## Next Phase Readiness

- ART-MB-10 ✅ (settings_export round-trip on all three paths + Pitfall 9 forward-compat both directions)
- ART-MB-12 ✅ (EditStationDialog selector reads + writes + dirty-detection)
- All 16 ART-MB-NN requirements now have an automated test surface; Plan 05 covers the manual UAT (visual checks, cross-machine ZIP transport, etc.)
- Full Phase 73 test surface: 345 / 345 pass across `test_cover_art*`, `test_repo.py`, `test_edit_station_dialog.py`, `test_settings_export.py`, `test_now_playing_panel.py`
- Plan 05 (UAT script) can proceed. The user-visible feature is live end-to-end: user opens EditStationDialog → flips combo → saves → DB persists → next ICY title change drives a fetch through the Plan 03 router → MB or iTunes path selected per the saved preference. ZIP export carries the preference; import on another machine restores it.

## Self-Check: PASSED

Files verified to exist:
- `musicstreamer/ui_qt/edit_station_dialog.py` ✅
- `musicstreamer/ui_qt/now_playing_panel.py` ✅
- `musicstreamer/settings_export.py` ✅
- `tests/test_edit_station_dialog.py` ✅
- `tests/test_settings_export.py` ✅
- `tests/test_now_playing_panel.py` ✅

Commits verified in git log:
- `d29a3e8` test(73-04): add failing tests for EditStationDialog cover_art_source combo ✅
- `cf64e78` feat(73-04): add cover_art_source QComboBox to EditStationDialog ✅
- `456d9f3` test(73-04): add failing tests for settings_export cover_art_source round-trip ✅
- `0dee56a` feat(73-04): round-trip cover_art_source through settings_export ZIP ✅
- `c18c18d` test(73-04): add failing tests for NowPlayingPanel source kwarg pass-through ✅
- `fb73677` feat(73-04): pass station.cover_art_source through _fetch_cover_art_async ✅

Grep gates verified:
- `cover_art_source` count in `edit_station_dialog.py`: 13 ✅ (combo + populate + save + snapshot + comments)
- `source=source` in `now_playing_panel.py`: 1 ✅
- `cover_art_source` count in `settings_export.py`: 6 ✅ (≥3 required: export + INSERT + REPLACE + comments)

Test gate verified:
- `pytest tests/test_cover_art*.py tests/test_repo.py tests/test_edit_station_dialog.py tests/test_settings_export.py tests/test_now_playing_panel.py` → 345 passed ✅

---
*Phase: 73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-*
*Completed: 2026-05-13*
