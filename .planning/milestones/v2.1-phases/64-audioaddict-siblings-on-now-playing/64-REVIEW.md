---
phase: 64-audioaddict-siblings-on-now-playing
reviewed: 2026-05-01T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - musicstreamer/url_helpers.py
  - musicstreamer/ui_qt/edit_station_dialog.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - musicstreamer/ui_qt/main_window.py
  - tests/test_aa_siblings.py
  - tests/test_now_playing_panel.py
  - tests/test_main_window_integration.py
findings:
  critical: 0
  warning: 2
  info: 4
  total: 6
status: issues_found
---

# Phase 64: Code Review Report

**Reviewed:** 2026-05-01
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Phase 64 lands BUG-02 closure: cross-network "Also on:" siblings on `NowPlayingPanel` with a panel-side click handler that switches active playback through the canonical `_on_station_activated` chain. The implementation is well-scoped, faithful to the three-plan rollout, and covered by adequate tests.

The required invariants from the phase context all hold under inspection:

- **Renderer security mitigation preserved.** `render_sibling_html` calls `html.escape(station_name, quote=True)` on every interpolated `Station.name` (url_helpers.py:176). Network display names come from the compile-time `NETWORKS` constant; href payload is integer-only `sibling://{int}`.
- **D-04 invariant holds.** `_refresh_siblings` is called from exactly one site — `bind_station` (now_playing_panel.py:376). No subscription to `station_saved`, `station_deleted`, or discovery-import-complete signals. Confirmed by negative-spy test `test_refresh_siblings_runs_once_per_bind_station_call`.
- **D-08 self-id no-op guard present.** `_on_sibling_link_activated` returns early when `self._station is None or self._station.id == sibling_id` (now_playing_panel.py:707-708).
- **Dual-shape `repo.get_station` handling correct.** `try/except Exception` (line 709-712) + `is None` check (line 713-714) covers both production `ValueError` and FakeRepo `None`.
- **QA-05 bound-method connections.** All new Qt connections (`linkActivated`, `sibling_activated`) use bound methods. The two `lambda` lines in `main_window.py` (466, 483) are pre-existing Phase 51/999.1 patterns, not Phase 64 additions.
- **Cross-plan single-source enforcement.** `NowPlayingPanel` imports only `find_aa_siblings` and `render_sibling_html` from `url_helpers`; no parallel detection logic. Locked by `test_panel_does_not_reimplement_aa_detection`.
- **MainWindow handler delegation.** `_on_sibling_activated` is a one-liner that delegates to `_on_station_activated` (main_window.py:341) — single source of truth.
- **EditStationDialog cleanup complete.** Phase 51's private `_render_sibling_html` method is gone; `import html` and module-top `from musicstreamer.aa_import import NETWORKS` removed from the dialog. Only call site is the new free function (edit_station_dialog.py:563).
- **Renderer purity.** `render_sibling_html` is a pure function — no Qt, no DB, no logging, no `self`.

The findings below are defense-in-depth gaps and stale documentation. None are blockers.

## Warnings

### WR-01: `_refresh_siblings` does not guard against `repo.list_stations()` raising

**File:** `musicstreamer/ui_qt/now_playing_panel.py:666`
**Issue:** `_refresh_siblings` calls `self._repo.list_stations()` without a try/except. The method is reached transitively from a Qt slot chain (`station_activated` / `sibling_activated` → `_on_station_activated` → `bind_station` → `_refresh_siblings`). The companion sibling-click handler `_on_sibling_link_activated` carefully wraps `repo.get_station` in `try/except Exception` (line 709-712) for exactly this slots-never-raise contract — the same defense should apply here. A transient DB error (`sqlite3.OperationalError` from a locked DB, disk-full, mid-session disconnect, etc.) would propagate out of a Qt slot and be unhandled. With Phase 64 the panel now reads from the repo on every `bind_station`, which materially widens the exposure surface compared to before.

**Fix:**
```python
def _refresh_siblings(self) -> None:
    if self._station is None or not self._station.streams:
        self._sibling_label.setVisible(False)
        self._sibling_label.setText("")
        return
    current_url = self._station.streams[0].url
    try:
        all_stations = self._repo.list_stations()
    except Exception:
        # Slots-never-raise: treat repo failure as "no siblings".
        self._sibling_label.setVisible(False)
        self._sibling_label.setText("")
        return
    siblings = find_aa_siblings(...)
    ...
```

### WR-02: Pre-existing `_on_navigate_to_sibling` does not handle production `ValueError`

**File:** `musicstreamer/ui_qt/main_window.py:512`
**Issue:** Phase 51's `_on_navigate_to_sibling` calls `self._repo.get_station(sibling_id)` and checks `if sibling is None: return` (line 513-514). But production `Repo.get_station` (repo.py:271) raises `ValueError` on miss — it never returns `None`. If a sibling station were deleted in another window/tab between render and click, this slot would raise `ValueError` out of a Qt signal slot. The dialog test FakeRepo at `tests/test_main_window_integration.py:131-152` returns `None` on miss, masking the production behaviour. This is pre-existing Phase 51 code, but Phase 64's parallel panel handler (`_on_sibling_link_activated`) explicitly chose `try/except Exception` precisely to avoid this trap (RESEARCH Pitfall #2 — same dual-shape concern). The two handlers should be defensively symmetrical; the dialog flow has a latent crash path that Phase 64's panel flow successfully avoided.

Surfacing here because the same RESEARCH pitfall is documented for both flows and the asymmetry is a quality gap that Phase 64 had the chance to fix while it was already touching the area.

**Fix:**
```python
def _on_navigate_to_sibling(self, sibling_id: int) -> None:
    try:
        sibling = self._repo.get_station(sibling_id)
    except Exception:
        return  # sibling deleted between render and click — silent no-op
    if sibling is None:
        return
    self._on_edit_requested(sibling)
```

## Info

### IN-01: Stale line-number reference in `NowPlayingPanel._on_sibling_link_activated` docstring

**File:** `musicstreamer/ui_qt/now_playing_panel.py:685`
**Issue:** The docstring says `Mirrors EditStationDialog._on_sibling_link_activated (lines 1004-1051)`. The actual method in `edit_station_dialog.py` lives at lines 959-1006. Stale reference will mislead future readers chasing context.

**Fix:** Either update the line range to `959-1006` or drop the line reference entirely (method-name reference alone is more durable).

### IN-02: Stale line-number reference in `MainWindow._on_sibling_activated` docstring

**File:** `musicstreamer/ui_qt/main_window.py:337-338`
**Issue:** The docstring says `Phase 51's _on_navigate_to_sibling (lines 482-500)`. The actual method now starts at line 497 in this file. Same fragility as IN-01.

**Fix:** Replace numeric range with method-name reference, e.g. `Unlike Phase 51's _on_navigate_to_sibling — which re-opens EditStationDialog and avoids touching playback — this slot DOES change playback`.

### IN-03: `render_sibling_html` does not escape the slug fallback

**File:** `musicstreamer/url_helpers.py:172`
**Issue:** `network_display = name_for_slug.get(slug, slug)` falls back to the raw `slug` string if it is not in `NETWORKS`. The phase context documents this as acceptable because slugs always come from `NETWORKS` in production callers (`find_aa_siblings` only emits NETWORKS slugs). However, the function is a free pure function with no caller-shape contract enforcement — a future caller could pass user-controlled tuples, and the test `test_render_sibling_html_unknown_slug_falls_back_to_slug_literal` even exercises a non-NETWORKS slug literal. For defense-in-depth (matching the explicit `html.escape` on `station_name`), the slug fallback should also be escaped.

**Fix:**
```python
network_display_raw = name_for_slug.get(slug, slug)
# Defense-in-depth: escape even when slug is the fallback. Real NETWORKS names
# need no escape but a future caller passing non-NETWORKS tuples must not
# punch a hole in the security mitigation.
network_display = html.escape(network_display_raw, quote=True)
```

### IN-04: `render_sibling_html` returns a half-empty string when called with empty siblings

**File:** `musicstreamer/url_helpers.py:179`
**Issue:** When `siblings == []`, the function returns `"Also on: "` (literal trailing space, no links). All current production callers (`EditStationDialog._refresh_siblings` and `NowPlayingPanel._refresh_siblings`) guard with `if not siblings:` before calling, so this is unreachable in practice — but the renderer is presented as a pure free function and could be called from a future site without the guard. Returning an empty string for the empty input would be a more robust contract.

**Fix:**
```python
def render_sibling_html(siblings, current_name) -> str:
    if not siblings:
        return ""
    name_for_slug = {n["slug"]: n["name"] for n in NETWORKS}
    ...
```

---

_Reviewed: 2026-05-01_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
