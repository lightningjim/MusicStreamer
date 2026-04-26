# Phase 999.1 — Deferred Items (out of scope for this phase)

## 2026-04-24 — Pre-existing failing test (Wave 0 scope boundary)

- **Test:** `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode`
- **Status:** Pre-existing failure — confirmed failing on `git stash` (main HEAD before Wave 0 changes).
- **Why deferred:** Not introduced by Phase 999.1 changes; out of scope per executor scope-boundary rule.
- **Recommended owner:** whichever phase owns StationListPanel _search_box visibility in favorites mode (likely a small regression from the 38-02 stack reshuffle).
- **Pre-existing test failure:** `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode` — asserts `panel._search_box.isVisibleTo(panel)` but filter strip starts collapsed (`self._filter_strip.setVisible(False)`). Confirmed failing on `main` at `fb5a733` before Plan 02 edits. Out of scope for 999.1-02.
