
## Pre-existing failures observed during Phase 55-01 execution (2026-05-01)

Discovered while running the Plan 55-01 acceptance gates. Both failures exist on
the un-edited base (`72bf899`) and are unrelated to the BUG-06 capture/restore fix
(neither Task 1 nor Task 2 touch the code paths under test). NOT auto-fixed per
the executor scope-boundary rule.

- `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode` —
  asserts the search box becomes hidden when switching to Favorites mode; today
  the search box stays visible (Phase 38-02 layout placed it as a child of the
  stations page, but `setVisible` propagation appears stale on this PySide6
  version). Out of scope for Phase 55.

- `tests/test_station_list_panel.py::test_refresh_recent_updates_list` —
  asserts `recent_view.model().rowCount() == 3`; the implementation calls
  `list_recently_played(5)` so up to 5 rows can render. Test invariant is wrong
  about the cap (or the Phase 50 implementation widened it). Out of scope for
  Phase 55.
