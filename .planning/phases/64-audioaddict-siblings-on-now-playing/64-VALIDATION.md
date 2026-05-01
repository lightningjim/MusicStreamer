---
phase: 64
slug: audioaddict-siblings-on-now-playing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-01
---

# Phase 64 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=7 with `pytest-qt>=4` |
| **Config file** | `pyproject.toml` (test config), `tests/conftest.py` (sets `QT_QPA_PLATFORM=offscreen`) |
| **Quick run command** | `pytest tests/test_url_helpers.py tests/test_now_playing_panel.py tests/test_edit_station_dialog.py -x -q` |
| **Full suite command** | `pytest tests -q` |
| **Estimated runtime** | ~15s (panel + helpers); ~60s (full suite) |

---

## Sampling Rate

- **After every task commit:** Run the quick set above
- **After every plan wave:** Run the full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~15s quick / ~60s full

---

## Per-Task Verification Map

> Populated by the planner. Every `<task>` in PLAN.md must have either an `<automated>` verify command (per-task or via the plan's wave verification) or an explicit Wave 0 stub dependency listed in the task's acceptance criteria.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| _to be filled by planner — one row per task in 64-*-PLAN.md_ | | | BUG-02 | — | html.escape mitigation preserved (T-39-01 deviation) | unit/integration (pytest-qt) | `pytest tests/<file>::<test_name> -x -q` | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_now_playing_panel.py::FakeRepo` — extend with `list_stations(self) -> list[Station]` (returns `self._stations`) and `get_station(self, station_id: int) -> Station | None` (returns the matching station or None — note production raises `ValueError`; the panel handler must guard for both shapes per RESEARCH Pitfall #3).
- [ ] `tests/test_now_playing_panel.py::_sample_repo()` — extend the existing factory (or add a new `_sample_repo_with_aa_siblings()`) so that the bound station has at least one cross-network AA sibling. Mirror `tests/test_station_list_panel.py`'s shape.
- [ ] If `tests/test_now_playing_panel.py` lacks an `_aa_url(slug, channel_key, quality="hi")` helper, add a small one to the test module (private to that file) so each test can construct DI.fm / ZenRadio / JazzRadio URLs deterministically.
- [ ] `tests/test_aa_siblings.py` (new file, OR `tests/test_url_helpers.py` extended) — add tests for the promoted `render_sibling_html(siblings, current_name)` function: same-name format ("ZenRadio"), differing-name format ("ZenRadio — Foo"), html.escape mitigation (interpolated `<script>` is escaped), empty list returns "Also on: " or "" (planner picks; document the chosen contract).
- [ ] No framework install — `pytest-qt` already in `pyproject.toml`.

Test stubs covering each ROADMAP SC and CONTEXT decision:
- SC #1 — bound AA station with siblings → label visible, text matches `Also on: <network> [• <network>]`.
- SC #2 — clicking a sibling link emits `sibling_activated(Station)` carrying the right Station; MainWindow's connected handler invokes `Player.play(sibling)`.
- SC #3 — three hide-paths (non-AA bound station, AA-but-no-siblings, no-station-bound) all leave label `setVisible(False)` with empty text.
- SC #4 — grep-asserted: NowPlayingPanel imports `find_aa_siblings` (and `render_sibling_html`) from `url_helpers`; no parallel sibling-detection logic in the panel module.
- SC #5 — when the bound station's id is among the candidate set, it must NOT appear in the rendered list (already enforced by `find_aa_siblings`; assert via panel-level test).
- D-02 — `sibling_activated = Signal(object)` exists on the panel class.
- D-03 — `EditStationDialog._render_sibling_html` no longer exists; the dialog imports `render_sibling_html` from `url_helpers`.
- D-04 — spy on `_refresh_siblings`: called exactly once per `bind_station(...)` call; not called in response to any signal subscription.
- D-08 — defense-in-depth no-op: when `panel._station is None or panel._station.id == sibling_id`, click handler does NOT emit `sibling_activated`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end UX feel of "click switches playback smoothly" | BUG-02 (SC #2) | Automated tests prove the signal-handler chain fires; a human eye confirms the perceived transition (no audible glitch beyond the normal Connecting flow, no UI flicker, panel correctly re-binds to the sibling) | 1. Launch app. 2. Play a DI.fm station that has a known sibling (e.g. DI.fm "Ambient" with a ZenRadio "Ambient" station also imported). 3. Confirm "Also on: ZenRadio" appears under the station name. 4. Click ZenRadio. 5. Confirm: panel re-binds to ZenRadio's Ambient (name+logo update); audio transitions to the ZenRadio stream; "Connecting…" toast fires; Recently Played updates; OS media-keys metadata reflects the new station. |
| Label hidden for non-AA stations | SC #3 | Automated tests assert visibility; a human confirms there's no visual gap or layout shift | 1. Play a non-AA station (e.g., a YouTube or Radio-Browser station). 2. Confirm no "Also on:" line. 3. Switch to an AA station with siblings. 4. Confirm the line appears with no layout pop. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers FakeRepo extension + sibling-fixture factory + renderer test file
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
