# Phase 77: Test infrastructure stabilization — Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 18 (3 new + 12 FakePlayer-migration sites + 3 test↔impl drift sites)
**Analogs found:** 18 / 18 (every new/modified file has a strong same-project precedent)
**Note:** RESEARCH.md (764 lines, HIGH confidence) already contains complete code drafts at
§Canonical FakePlayer signal list (L350–371), §D-16 drift-guard (L375–435), §D-17 drift-guard
(L440–469), §Pattern 2 MPRIS2 fixture (L191–220), §Pattern 3 network-block fixture (L234–249),
§D-15 fix (L490–506), §Cluster 5a fix (L523–541), §Cluster 6 fix (L555–578). **This PATTERNS.md
references those drafts by line number rather than duplicating them.** What this file adds is the
*site-level* drift evidence — the actual `class FakePlayer` declarations in each of the 12 test
files — plus role/data-flow classification and pattern selection per file.

## File Classification

### New files (Wave 0 — drift-guards + shared module)

| File | Role | Data Flow | Closest Analog | Match Quality |
|------|------|-----------|----------------|---------------|
| `tests/_fake_player.py` | test-helper module (test double) | n/a (class-level QObject Signal mirroring) | `tests/conftest.py` `_FakeRepo`/`_FakeStation`/`_FakeStream` (lines 102–207) — module-level underscore-prefix shared doubles | exact (role) |
| `tests/test_fake_player_signal_parity.py` | drift-guard test | source-introspection | `tests/test_yt_dlp_opts_drift.py` (Phase 79) — source-grep call-count drift-guard | role-match (source-introspection vs source-grep) |
| `tests/test_fake_player_no_inline.py` | drift-guard test | source-grep | `tests/test_constants_drift.py:48–60` `test_no_org_example_literal_remains_in_python_sources` — rglob + literal-search ban-pattern | exact (rglob + ban-list shape) |

### Modified files — FakePlayer migration (12 sites)

| File | Role | Data Flow | Current State | Closest Analog | Match Quality |
|------|------|-----------|---------------|----------------|---------------|
| `tests/test_main_window_integration.py:31` | UI test | request-response (Qt) | **SEED**: most complete FakePlayer (10 Signals + 7 methods incl. `shutdown_underrun_tracker`, `restore_eq_from_settings`, `set_eq_*`); CORRECT `audio_caps_detected = Signal(int, int, int)` at L42 | self (seed for shared module) | exact |
| `tests/test_main_window_gbs.py:25` | UI test | request-response (Qt) | **DRIFT**: 9 Signals; `audio_caps_detected = Signal(object)` at L34 (WRONG arity); missing `shutdown_underrun_tracker` | seed = integration | role-match (must accept arity fix on migration) |
| `tests/test_main_window_soma.py:33` | UI test | request-response (Qt) | **DRIFT**: copy-paste of gbs verbatim; same arity bug at L42; missing `shutdown_underrun_tracker` | seed = integration | role-match (must accept arity fix on migration) |
| `tests/test_now_playing_panel.py:29` | UI test | request-response (Qt) | **PARTIAL**: 6 Signals only (no `cookies_cleared`, `underrun_recovery_started`, `audio_caps_detected`); 9 methods incl. `set_eq_*` | seed = integration | role-match (gains 4 signals on migration; safe — connect-to-unused signal is a no-op in Qt) |
| `tests/test_phase72_now_playing_panel.py:34` | UI test | request-response (Qt) | **PARTIAL**: 6 Signals (same as now_playing_panel) | seed = integration | role-match |
| `tests/test_ui_qt_scaffold.py:16` | UI smoke test | request-response (Qt) | partial (cannot construct MainWindow without `underrun_recovery_started`) | seed = integration | exact |
| `tests/test_main_window_media_keys.py:54` | UI test | request-response (Qt) | partial | seed = integration | exact |
| `tests/test_discovery_dialog.py:39` | UI test | request-response (Qt) | partial — dialog only, not full MainWindow | seed = integration | role-match (FakePlayer used only for `discovery_dialog`; over-signaling is harmless) |
| `tests/test_stream_picker.py:32` | UI test | request-response (Qt) | partial | seed = integration | role-match |
| `tests/test_phase72_1_stream_picker_reflow.py:79` | UI test | request-response (Qt) | partial | seed = integration | role-match |
| `tests/ui_qt/test_main_window_node_indicator.py:35` | UI test | request-response (Qt) | partial (subdirectory site — grep target for D-17 must rglob) | seed = integration | exact (CONTEXT.md `<code_context>` cites this as a precedent for `_FakePlayer` shape) |
| `tests/test_equalizer_dialog.py:40` | UI dialog test | request-response (Qt) | **AMBIGUOUS**: declares `class FakePlayer:` WITHOUT `(QObject)` — no Signals, only 3 EQ method stubs (`set_eq_enabled`, `set_eq_profile`, `set_eq_preamp`); never constructs `MainWindow` (only `EqualizerDialog`) | seed = integration OR keep as-is | **decision deferred to planner** — see §Ambiguous Classification below |

### Modified files — test↔impl drift fixes (per-cluster, not FakePlayer)

| File | Role | Data Flow | Cluster | Closest Analog | Match Quality |
|------|------|-----------|---------|----------------|---------------|
| `tests/test_twitch_auth.py` | unit test (player API) | request-response | **6** (D-05 INVERTED — test follows impl per RESEARCH §Summary 1) | RESEARCH.md L555–578 contains the full rewrite draft | exact (draft already in research) |
| `tests/test_import_dialog_qt.py` (lines 141–154) | UI test (delete orphans) | n/a | **4** (D-04 — Phase 56 widget already removed) | RESEARCH.md L511–518 (deletion lines specified) | exact |
| `tests/test_station_list_panel.py:318` | UI test (rewrite assertion) | request-response (Qt) | **5b** (D-15 — replace `isVisibleTo` with `_stack.currentIndex`) | RESEARCH.md L490–506 contains the rewrite draft | exact (draft already in research) |
| `tests/test_station_list_panel.py:504` | UI test (update count) | request-response (Qt) | **5a** (D-06 — production calls `list_recently_played(5)`) | RESEARCH.md L523–541 contains the rewrite draft | exact (draft already in research) |

### Modified files — MPRIS2 + network-block + Qt-teardown

| File | Role | Data Flow | Cluster | Closest Analog | Match Quality |
|------|------|-----------|---------|----------------|---------------|
| `tests/test_media_keys_mpris2.py` (Tests 6–12, lines ~128–270) | integration test (D-Bus) | event-driven (registerService) | **2** (D-10/D-11/D-18 — per-test unique-suffix fixture) | RESEARCH.md L191–220 contains the `unique_mpris_service_name` fixture draft | exact |
| `tests/conftest.py` (NEW additions OR new helper file) | shared fixtures | n/a | **2** + **3** (host the MPRIS2 fixture AND the network-block fixture) | self (existing `_FakeRepo`/`mock_gbs_api` fixtures at lines 42–224 are the layout precedent) | exact (additive only) |
| `tests/test_main_window_underrun.py::test_first_call_shows_toast` | integration test (Qt + network) | event-driven (urllib.urlretrieve race) | **3** (D-12 OPTION A — monkeypatch BOTH `urlretrieve` AND `urlopen` per RESEARCH §Summary 5) | RESEARCH.md L234–249 contains the `block_real_network` fixture draft | exact (draft already in research) |
| `tests/test_import_dialog_qt.py::test_yt_scan_passes_through` | integration test (QThread teardown) | event-driven (worker.finished) | **3** (D-14 — `qtbot.waitSignal` + `worker.wait()`) | existing pattern: `tests/test_main_window_integration.py` worker-fixture usage (see RESEARCH §Don't Hand-Roll worker.wait precedent at `edit_station_dialog.py:1342`) | role-match |

## Pattern Assignments

### `tests/_fake_player.py` — shared FakePlayer base

**Role:** test-helper module (test double).
**Data flow:** n/a (declarative — class-level Signal mirroring of `musicstreamer.player.Player`).

**Analog:** `tests/conftest.py` `_FakeRepo`/`_FakeStation`/`_FakeStream` (lines 102–207) — the *only* same-project precedent for module-level underscore-prefix shared test doubles. **Seed body:** `tests/test_main_window_integration.py:31–84` (most complete FakePlayer in the tree, CORRECT arity for `audio_caps_detected`).

**Concrete excerpts:**

**Imports + module-level class (mirror this shape):**
```python
# Source: tests/conftest.py:102-115 — established shape for underscore-prefix shared doubles
class _FakeStation:
    """Mirrors the real musicstreamer.models.Station attribute surface
    that Phase 60 touches. HIGH 1 fix: attribute is `station_art_path`
    (matching models.py:31) — NOT `station_art`. _FakeRepo.update_station_art
    writes through to this canonical attribute name.
    """
    def __init__(self, station_id, name, url, provider_name, tags=""):
        self.id = station_id
        ...
```

**Seed Signal block** (cite verbatim — `tests/test_main_window_integration.py:31–42`):
```python
class FakePlayer(QObject):
    """Minimal Player surface — exposes the same Signals as the real Player."""

    title_changed = Signal(str)
    failover = Signal(object)
    offline = Signal(str)
    playback_error = Signal(str)
    cookies_cleared = Signal(str)  # Phase 999.7
    elapsed_updated = Signal(int)
    buffer_percent = Signal(int)  # Phase 47.1 D-12
    underrun_recovery_started = Signal()  # Phase 62 / D-07 — main→MainWindow toast trigger
    audio_caps_detected = Signal(int, int, int)  # Phase 70 / DS-01: stream_id, rate_hz, bit_depth
```

**Method stub pattern** (cite verbatim — `tests/test_main_window_integration.py:44–84`):
```python
def __init__(self):
    super().__init__()
    self.play_calls: list[Station] = []
    self.pause_calls: int = 0
    self.stop_calls: int = 0
    self.volume: Optional[float] = None

def set_volume(self, value: float) -> None:
    self.volume = value

def play(self, station: Station, **kwargs) -> None:
    self.play_calls.append(station)

def pause(self) -> None:
    self.pause_calls += 1

def stop(self) -> None:
    self.stop_calls += 1

# Phase 47.2: EQ API stubs — MainWindow calls restore_eq_from_settings
# from __init__; the other methods are referenced by EqualizerDialog
# and included here for completeness.
def restore_eq_from_settings(self, repo) -> None:
    pass

def set_eq_enabled(self, enabled: bool) -> None:
    pass

def set_eq_profile(self, profile) -> None:
    pass

def set_eq_preamp(self, db: float) -> None:
    pass

def shutdown_underrun_tracker(self) -> None:
    """Phase 62 / D-03: no-op stub — real Player force-closes any open cycle."""
    pass
```

**Required Signal expansion (CONTEXT.md `<canonical_refs>` says 18 Player signals; seed declares only 10):**
The integration-test seed is missing 8 Player-internal signals that test code never connects to but the
drift-guard (D-16) WILL enumerate. RESEARCH.md L350–371 lists all 18. The shared `_fake_player.py` MUST
include all 18 to satisfy the parity test. Specifically add the missing 8 from `musicstreamer/player.py:244–276`:
```python
# Cite musicstreamer/player.py:244-276 verbatim — internal signals MainWindow does NOT use
twitch_resolved            = Signal(str)
youtube_resolved           = Signal(str)
youtube_resolution_failed  = Signal(str)
_cancel_timers_requested   = Signal()
_error_recovery_requested  = Signal()
_try_next_stream_requested = Signal()
_playbin_playing_state_reached = Signal()
_underrun_cycle_opened     = Signal()
_underrun_cycle_closed     = Signal(object)
```
*(That's 9; CONTEXT.md cites 18 total — production line 282 has `audio_caps_detected` = signal 18; seed has 10, so 8 to add. Source-of-truth count comes from RESEARCH.md L350–371 — planner MUST regenerate from production at plan time using the §Pattern 1 introspection probe.)*

---

### `tests/test_fake_player_signal_parity.py` — D-16 drift-guard

**Role:** drift-guard test (source-introspection).
**Data flow:** source-introspection (read both production and test-double source files; assert parity).

**Analog:** `tests/test_yt_dlp_opts_drift.py` (Phase 79) — same role (drift-guard) with same-project's
established source-grep convention. **Body draft already exists in RESEARCH.md L375–435.**

**Imports pattern** (mirror `tests/test_yt_dlp_opts_drift.py:1–10`):
```python
"""Phase 79 / BUG-11 drift-guard: both yt-dlp call sites must use the shared
`yt_dlp_opts.build_js_runtimes(` helper. A regression that re-introduces the
inline `{'node': {'path': None}}` literal at either site is the exact bug
Phase 79 fixed — see commit `a06549f` context."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "musicstreamer"
```

**Apply to Phase 77 D-16** (full body in RESEARCH.md L375–435 — reference directly, do not rewrite).

**Two assertion functions** (per RESEARCH.md):
1. `test_fake_player_mirrors_every_player_signal()` — name parity via `Player.__dict__` walk + `isinstance(v, Signal)`.
2. `test_fake_player_signal_arity_matches_player()` — arity parity via regex source-parse of both files (`^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*Signal\(([^)]*)\)`).

**Why `Player.__dict__` not `dir(Player)`** — RESEARCH.md Pitfall 3 (L300–310): `__dict__` excludes inherited
QObject Signals (`destroyed`, `objectNameChanged`) which FakePlayer should NOT need to mirror. Verified probe: 18 vs 20 Signal-typed attrs.

---

### `tests/test_fake_player_no_inline.py` — D-17 drift-guard

**Role:** drift-guard test (source-grep).
**Data flow:** source-grep — rglob `tests/*.py` + regex match + allow-list of `{"_fake_player.py"}`.

**Analog:** `tests/test_constants_drift.py:48–60` — same shape (rglob + literal-search + ban-list) for
the `org.example.MusicStreamer` placeholder.

**Pattern excerpt** (cite verbatim — `tests/test_constants_drift.py:48–60`):
```python
def test_no_org_example_literal_remains_in_python_sources():
    """No code under musicstreamer/ should reference the old placeholder."""
    pkg_root = Path(__file__).parent.parent / "musicstreamer"
    needle = "org.example.MusicStreamer"
    hits = []
    for py in pkg_root.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if needle in text:
            hits.append(str(py.relative_to(pkg_root.parent)))
    assert not hits, f"Phase 61 left placeholder behind in: {hits}"
```

**Apply to Phase 77 D-17** (full body in RESEARCH.md L440–469 — reference directly):
- Regex: `r'^\s*class\s+_?FakePlayer\s*\(QObject\)'` with `re.M`.
- Allow-list: `{"_fake_player.py"}` (single file).
- rglob target: `tests/` (must include `tests/ui_qt/` subdirectory — the `tests/ui_qt/test_main_window_node_indicator.py:35` site lives there).

**Note:** the `class FakePlayer:` at `tests/test_equalizer_dialog.py:40` (no `(QObject)`) does NOT match
the regex per design — see §Ambiguous Classification.

---

### FakePlayer migration sites (12 files) — apply identical 4-line diff per file

**Migration pattern** (apply to all 12 sites):

```diff
-from PySide6.QtCore import QObject, Signal
-...
-class FakePlayer(QObject):   # OR class _FakePlayer(QObject)
-    title_changed = Signal(str)
-    ...
-    def __init__(self):
-        super().__init__()
-        ...
+from tests._fake_player import FakePlayer
```

**Site-specific notes:**

1. **`tests/test_main_window_integration.py:31` — SEED.**
   This file's FakePlayer (lines 31–84) is the seed body for `tests/_fake_player.py`. Migration here is "delete inline class; add import." Note: `tests/test_main_window_underrun.py:18` currently does `from tests.test_main_window_integration import FakePlayer, FakeRepo` — this transitive import must be re-pointed to `from tests._fake_player import FakePlayer` during the migration.

2. **`tests/test_main_window_gbs.py:25` + `tests/test_main_window_soma.py:33` — ARITY FIX.**
   Both currently declare `audio_caps_detected = Signal(object)` (1-arg) at `:34` and `:42` respectively.
   The shared module uses `Signal(int, int, int)` (production arity). **Migration AUTO-FIXES the drift.**
   No additional change needed beyond the import swap. The drift-guard D-16 (arity check) is what would
   catch any future regression.

3. **`tests/test_now_playing_panel.py:29` + `tests/test_phase72_now_playing_panel.py:34` — SIGNAL EXPANSION.**
   These currently declare only 6 Signals. After migration they gain ~12 more (the shared module's full set).
   This is **safe**: Qt does NOT raise on connecting to a never-emitted Signal, and the panel only `.connect()`s
   to signals it cares about. **No test logic changes required beyond the import swap.**

4. **`tests/test_equalizer_dialog.py:40` — AMBIGUOUS** (see §Ambiguous Classification below).

5. **`tests/ui_qt/test_main_window_node_indicator.py:35` — SUBDIRECTORY SITE.**
   Lives in `tests/ui_qt/`, so the D-17 drift-guard's `rglob("*.py")` (not just `glob`) is required to detect it.

**FakeRepo NOT in scope:** Each of the 12 FakePlayer migration sites also declares an inline `FakeRepo` (10 confirmed via grep). Phase 77 D-09 only canonicalizes FakePlayer; FakeRepo migration is OUT OF SCOPE (no recurring-drift evidence). The shared `_FakeRepo` already exists at `tests/conftest.py:132` for newer tests but no migration mandate.

---

### `tests/test_twitch_auth.py` — Cluster 6 (D-05 INVERTED)

**Role:** unit test rewrite + module docstring update.
**Data flow:** request-response (worker calls `session.set_option(...)`).
**Direction:** **test follows impl** (REVISED per RESEARCH §Summary 1).

**Analog:** RESEARCH.md L555–578 contains the complete rewrite. **Reference that draft.**

**Key changes:**
1. Function rename: `test_play_twitch_sets_plugin_option_when_token_present` → `test_play_twitch_sets_option_when_token_present`.
2. Assertion swap:
   - OLD (`tests/test_twitch_auth.py:84–86`): `session.set_plugin_option.assert_called_once_with("twitch", "api-header", [("Authorization", "OAuth abc123")])`
   - NEW: `session.set_option.assert_called_once_with("twitch-api-header", [("Authorization", "OAuth abc123")])`
3. Add `from streamlink.session import Streamlink` import + use `MagicMock(spec=Streamlink)` so any future reintroduction of `set_plugin_option` raises `AttributeError` at test time (drift-guard via spec — see RESEARCH Pitfall 1).
4. Update module docstring at lines 1–9: delete the stale Phase 31 paragraph referencing `session.set_plugin_option("twitch", "api-header", ...)`; replace with current API per `musicstreamer/player.py:1156`.
5. **Sibling test (`test_play_twitch_no_header_when_token_absent` at `:89`) likely has same `set_plugin_option` reference** — planner verifies and applies same change.

**No production-code change.** `musicstreamer/player.py:1156` already calls `session.set_option("twitch-api-header", ...)` per CONTEXT.md `<canonical_refs>`.

---

### `tests/test_import_dialog_qt.py` (lines 141–154) — Cluster 4 (D-04)

**Role:** UI test (delete orphan assertions).
**Data flow:** n/a — pure deletion.

**Analog:** RESEARCH.md L511–518 (deletion specification).

**Concrete diff** (cite `tests/test_import_dialog_qt.py:141–154`):
```python
# DELETE THIS BLOCK (test_audioaddict_tab_widgets) — lines 141–144
def test_audioaddict_tab_widgets(dialog):
    assert dialog._aa_key is not None
    assert dialog._aa_quality is not None      # ← orphan; widget removed in Phase 56 commit 414e236
    assert dialog._aa_import_btn is not None

# DELETE THIS BLOCK (test_audioaddict_quality_combo) — lines 152–154
def test_audioaddict_quality_combo(dialog):
    items = [dialog._aa_quality.itemText(i) for i in range(dialog._aa_quality.count())]
    assert items == ["hi", "med", "low"]
```

**Decision (D-04):** Delete both functions wholesale. If AudioAddict Quality dropdown UX is wanted back, file a new feature phase. The two remaining assertions in `test_audioaddict_tab_widgets` (`_aa_key`, `_aa_import_btn`) are still valid — but the function is mixed-orphan, so per D-04 the entire two functions go. If the planner prefers to preserve `_aa_key`/`_aa_import_btn` checks they can be inlined elsewhere; otherwise dropping both is simplest.

---

### `tests/test_station_list_panel.py:318,326,332` — Cluster 5b (D-15)

**Role:** UI test (rewrite assertion).
**Data flow:** request-response (Qt page-switch).

**Analog:** RESEARCH.md L490–506 contains the complete rewrite.

**Concrete diff** (current code at `tests/test_station_list_panel.py:318–333`):
```python
def test_filter_strip_hidden_in_favorites_mode(qtbot):
    """Search box and chip rows are on page 0; not visible when page 1 is active."""
    from PySide6.QtWidgets import QStackedWidget
    panel = StationListPanel(_sample_repo_with_favorites())
    qtbot.addWidget(panel)

    # In Stations mode, search box is on page 0
    assert panel._stack.currentIndex() == 0
-   assert panel._search_box.isVisibleTo(panel), "search box should be visible in Stations mode"
+   # D-15 (Phase 77): isVisibleTo() returns False on widgets whose top-level
+   # was never show()-n. Stack-page-active is the semantic equivalent.

    # Switch to Favorites
    panel._favorites_btn.click()
    assert panel._stack.currentIndex() == 1
    # Search box is on page 0 of the stack, so it's not visible
-   assert not panel._search_box.isVisibleTo(panel), "search box should not be visible in Favorites mode"
+   # D-15 (Phase 77): page-1-active ⇒ page-0 search box is on inactive page.
```

Or simpler — delete the two `isVisibleTo` lines entirely. The two `currentIndex()` assertions at L325/330 already cover the semantic.

---

### `tests/test_station_list_panel.py:504–520` — Cluster 5a (D-06)

**Role:** UI test (update count).
**Data flow:** request-response (Qt model rowCount).

**Analog:** RESEARCH.md L523–541 contains the complete rewrite.

**Concrete diff:**
```python
-    assert panel.recent_view.model().rowCount() == 3
+    # D-06 (Phase 77): production calls list_recently_played(5); test must follow.
+    expected = min(5, len(repo._recent))
+    assert panel.recent_view.model().rowCount() == expected
```

Note: prefer `min(5, len(repo._recent))` over a hardcoded `== 5` — robust if the fake repo's seed data changes. Production reference: `musicstreamer/ui_qt/station_list_panel.py:492` calls `list_recently_played(5)` (DO NOT change).

---

### `tests/test_media_keys_mpris2.py` — Cluster 2 (D-10/D-11/D-18)

**Role:** integration test (D-Bus).
**Data flow:** event-driven (registerService side effect on shared session bus).

**Analog:** RESEARCH.md L191–220 contains the `unique_mpris_service_name` fixture draft.

**Migration shape per test** (Tests 6–12, lines ~128–270):
```diff
 @skip_if_no_bus
-def test_linux_mpris_backend_constructs(tmp_path, monkeypatch, qapp):
+def test_linux_mpris_backend_constructs(tmp_path, monkeypatch, qapp, unique_mpris_service_name):
     """Test 6: LinuxMprisBackend constructs and registers the MPRIS2 service."""
     monkeypatch.setattr(paths, "_root_override", str(tmp_path))
     from musicstreamer.media_keys.mpris2 import LinuxMprisBackend

     backend = LinuxMprisBackend(None, None)
     try:
         # Service should be registered on the bus
         bus = QDBusConnection.sessionBus()
         registered = bus.interface().registeredServiceNames().value()
-        assert "org.mpris.MediaPlayer2.musicstreamer" in registered
+        assert unique_mpris_service_name in registered
     finally:
         backend.shutdown()
```

**Fixture location:** `tests/conftest.py` is the established host for shared MPRIS-style fixtures (precedent: `mock_gbs_api` at L42–99, `fake_repo` at L209). Alternative per CONTEXT.md `<discretion>`: a new `tests/_mpris_helpers.py` module — planner picks. **Recommendation: extend `conftest.py`** to match the established multi-fixture-per-conftest pattern. Only Test 6's assertion at L139 (`"org.mpris.MediaPlayer2.musicstreamer" in registered`) needs the string-comparison swap; Tests 7–12 only need the fixture injection to ensure no collision during construction.

---

### `tests/test_main_window_underrun.py::test_first_call_shows_toast` — Cluster 3 (D-12)

**Role:** integration test (Qt + EditStationDialog logo-fetch worker).
**Data flow:** event-driven (worker thread races widget GC during logo fetch).

**Analog:** RESEARCH.md L234–249 contains the `block_real_network` fixture draft.

**Migration shape** — add the fixture to `tests/conftest.py` (or as a local fixture in the affected file) and inject it into the four cluster-3 reproducer sites:

```python
# Source: tests/conftest.py — proposed addition per RESEARCH §Pattern 3 (L234-249)
@pytest.fixture
def block_real_network(monkeypatch):
    """Phase 77 D-12: replace urlretrieve and urlopen with stubs so EditStationDialog
    logo-fetch worker (and cover_art._itunes_attempt daemon thread) cannot make
    real network calls. Covers both urlretrieve (logo fetch — edit_station_dialog.py:94,125)
    AND urlopen (iTunes Search API — cover_art.py:111,119)."""
    def _stub_urlretrieve(url, filename=None, *a, **kw):
        if filename:
            with open(filename, "wb") as fh:
                fh.write(b"")
        return (filename or "/tmp/stub", {})

    monkeypatch.setattr("urllib.request.urlretrieve", _stub_urlretrieve)
    from unittest.mock import MagicMock
    monkeypatch.setattr("urllib.request.urlopen",
                        MagicMock(side_effect=OSError("blocked in test")))
```

**Injection sites:**
- `tests/test_main_window_underrun.py::test_first_call_shows_toast` (line 31) — add `block_real_network` to fixture list.
- `tests/test_main_window_integration.py` + `tests/test_now_playing_panel.py` cross-file pair — add the fixture autouse-style or inject per-test. Per RESEARCH §Open Questions Q2: **per-file opt-in** preferred over session-wide autouse.
- `tests/test_phase72_now_playing_panel.py` + `tests/test_phase72_assumptions.py` cross-file pair — same.

**Daemon-thread context** (cite `musicstreamer/cover_art.py:91–128`):
```python
def _itunes_attempt(icy_string, on_done):
    """Spawns the same daemon-thread worker as the historic single-source path.
    All exception handling is intentionally inside the worker: per D-20 the
    worker NEVER raises out."""
    ...
    def _worker():
        try:
            with urllib.request.urlopen(query_url, timeout=5) as resp:
                ...
        except Exception:
            on_done(None)
    threading.Thread(target=_worker, daemon=True).start()  # ← line 128: daemon, no join
```
This is why `urlopen` must be patched alongside `urlretrieve` per RESEARCH §Summary 5 / §Pitfall 5.

---

### `tests/test_import_dialog_qt.py::test_yt_scan_passes_through` — Cluster 3 (D-14)

**Role:** integration test (QThread teardown).
**Data flow:** event-driven (`worker.finished` signal + thread exit).

**Analog:** Existing pattern at `musicstreamer/ui_qt/edit_station_dialog.py:1327–1342` — `_shutdown_logo_fetch_worker` calls `worker.wait(N)` per RESEARCH §Don't Hand-Roll. The current test at `tests/test_import_dialog_qt.py:213–235` already uses `with qtbot.waitSignal(worker.finished, timeout=3000)`. Per RESEARCH §Open Question 3, the planner reads `musicstreamer/ui_qt/import_dialog.py` end-to-end to determine whether a `_shutdown_yt_scan_worker` helper exists in production code. If absent, planner adds one mirroring `edit_station_dialog.py:1327–1342`. If present, the fix is test-side `worker.wait(2000)` after `qtbot.waitSignal`.

**No concrete code excerpt here** — RESEARCH §Open Question 3 explicitly defers to plan-time investigation.

## Shared Patterns

### Source-introspection drift-guard
**Source:** `tests/test_yt_dlp_opts_drift.py:1–45` (Phase 79) + `tests/test_constants_drift.py:48–60` (Phase 61).
**Apply to:** `tests/test_fake_player_signal_parity.py` (D-16) AND `tests/test_fake_player_no_inline.py` (D-17).

**Common shape:**
1. `from pathlib import Path` + module-level `ROOT = Path(__file__).resolve().parent.parent`.
2. Read source file as text via `path.read_text(encoding="utf-8")` (with `try/except UnicodeDecodeError`).
3. Apply regex (`re.compile(..., re.M)`) or substring `count()` check.
4. `assert` on the result with descriptive failure message that names the expected fix.

### Underscore-prefix shared test doubles
**Source:** `tests/conftest.py:102–207` (`_FakeStation`, `_FakeStream`, `_FakeRepo`).
**Apply to:** `tests/_fake_player.py`.

**Conventions:**
- Underscore-prefix on module name AND on class name (CONTEXT.md `<canonical_refs>` line 164).
- Module-level class definition with sensible defaults; opt-in via `@pytest.fixture` wrapper OR direct import.
- Mirrors real production attribute names (CONTEXT.md memory: `reference_musicstreamer_db_schema.md` — schema accuracy matters for fakes).
- Comments cite the production source line being mirrored (per `conftest.py:102` style).

### Test-time monkeypatch over env-var contract
**Source:** `tests/test_cookies.py` `paths._root_override` pattern (CONTEXT.md `<code_context>`) + `tests/conftest.py:20–30` `_stub_bus_bridge`.
**Apply to:** `unique_mpris_service_name` fixture (D-10) AND `block_real_network` fixture (D-12).

**Conventions:**
- `monkeypatch.setattr(module, "CONSTANT", value)` for module-level constants.
- `monkeypatch.setattr("dotted.path.func", stub)` for callable replacement.
- Best-effort teardown in `yield` fixture (try/except guard).

### Qt fixture lifecycle
**Source:** Established throughout `tests/` — `qtbot.addWidget(w)` after construction; never call `.show()` unless `qtbot.waitExposed(w)` follows.
**Apply to:** All 12 FakePlayer migration sites (no change — existing usage is correct).

**Conventions:**
- `qtbot.addWidget(w)` registers for automatic cleanup at test end.
- `qtbot.waitSignal(...)` for cross-thread/async signal completion (timeout in ms).
- `panel.show()` is ONLY needed if assertions depend on `isVisibleTo()` — Phase 77 D-15 specifically avoids this by switching to `_stack.currentIndex()`.

## Ambiguous Classification

### `tests/test_equalizer_dialog.py:40` — non-QObject FakePlayer

**Current state** (`tests/test_equalizer_dialog.py:40–51`):
```python
class FakePlayer:
    def __init__(self):
        self.calls: list = []

    def set_eq_enabled(self, v):
        self.calls.append(("enabled", v))

    def set_eq_profile(self, p):
        self.calls.append(("profile", p))

    def set_eq_preamp(self, db):
        self.calls.append(("preamp", db))
```

**Why ambiguous:**
- **Not a `QObject` subclass** — no Signals declared.
- Only used to construct `EqualizerDialog`, not `MainWindow`.
- `EqualizerDialog` likely calls `player.set_eq_*()` but does NOT `.connect()` to player signals.
- D-17 drift-guard regex `^\s*class\s+_?FakePlayer\s*\(QObject\)` does NOT match this declaration → it stays GREEN even if this stays inline.
- D-09 explicitly defers: "planner decides whether to migrate it; if the equalizer dialog never connects Qt signals on the player it may stay non-QObject."

**Recommendation for planner:**
- **Option A (recommended):** Leave inline. Adds a `.calls` instance attribute the shared FakePlayer doesn't have, used only by this dialog's test assertions. Migration would require either subclassing the shared base or adding a `.calls` list — both add coupling for zero drift-prevention benefit (the D-17 regex skips it).
- **Option B:** Migrate anyway for consistency. Shared `FakePlayer` already has `set_eq_enabled` / `set_eq_profile` / `set_eq_preamp` as no-op methods; this test would lose the `.calls` log. Rewrite test assertions to use `MagicMock(wraps=...)` or counter attributes instead.

**If Option A:** Planner adds a one-line comment at `:40` documenting the intentional non-migration: `# Phase 77 D-09: intentionally non-QObject; no Signal connect → drift-guard regex skips this site.`

## No Analog Found

**None.** Every new/modified file in Phase 77 has at least a "role-match" precedent in `tests/`.

## Metadata

**Analog search scope:**
- `tests/*.py` (12 FakePlayer sites + 5 drift-guard / fixture precedents)
- `tests/ui_qt/*.py` (1 sub-directory FakePlayer site)
- `tests/conftest.py` (shared-double pattern source)
- `musicstreamer/player.py` lines 241–282 (Signal source-of-truth, 18 Player-specific signals per RESEARCH probe)
- `musicstreamer/cover_art.py` lines 91–128 (daemon-thread context for D-12)
- `musicstreamer/media_keys/mpris2.py` lines 56, 254–261, 295–302 (SERVICE_NAME constant + lifecycle)

**Files scanned:** 18 files read directly during pattern extraction; ~30 additional files surveyed via grep for `class _?FakePlayer` and `class _?FakeRepo` declarations.

**Pattern extraction date:** 2026-05-17

**Cross-references:**
- RESEARCH.md L139–222 (Pattern 1/2) — drift-guard + monkeypatch patterns
- RESEARCH.md L224–249 (Pattern 3) — network-block fixture
- RESEARCH.md L348–578 (Code Examples) — full code drafts for all six clusters
- CONTEXT.md `<code_context>` L173–193 — established patterns + integration points
- CONTEXT.md `<canonical_refs>` L141–166 — production-code sites + project conventions
