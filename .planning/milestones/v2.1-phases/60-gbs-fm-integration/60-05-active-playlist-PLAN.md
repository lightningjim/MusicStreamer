---
phase: 60
plan: 05
type: execute
wave: 3
depends_on: ["60-02", "60-04"]
files_modified:
  - musicstreamer/ui_qt/now_playing_panel.py
  - tests/test_now_playing_panel.py
autonomous: true
requirements: [GBS-01c]
tags: [phase60, now-playing, active-playlist, gbs-fm]

must_haves:
  truths:
    - "When the bound station's provider_name == 'GBS.FM' AND the user is logged in (cookies file exists), NowPlayingPanel shows an active-playlist widget below the existing controls row"
    - "When provider_name is non-GBS.FM OR no station bound OR not logged in, the playlist widget is hidden (Phase 51 / Phase 64 hide-when-empty contract)"
    - "Active-playlist widget is populated from gbs_api.fetch_active_playlist() responses"
    - "QTimer polls /ajax every 15 seconds (D-06a RESOLVED — matches gbs.fm web UI cadence DELAY=15000) only while the widget is visible AND a GBS.FM station is bound"
    - "QTimer pauses when the widget is hidden (Pitfall 5 — polling × token expiry × rate-limit interaction)"
    - "Stale-response token guard: when station re-binds mid-poll, in-flight responses are discarded (Pitfall 1 race + cover_art precedent)"
    - "Auth-expired during poll surfaces gracefully — widget hides itself, no crash, no toast spam"
    - "Track list rendered with Qt.TextFormat.PlainText (Pitfall 11 — gbs.fm-side artist/title strings could contain HTML)"
    - "_refresh_gbs_visibility is called as the LAST line of bind_station (Phase 64 D-04 invariant — only call site)"
  artifacts:
    - path: "musicstreamer/ui_qt/now_playing_panel.py"
      provides: "_gbs_playlist_widget (QListWidget), _gbs_poll_timer, _gbs_poll_token, _gbs_poll_worker, _refresh_gbs_visibility, _on_gbs_poll_tick, _on_gbs_playlist_ready, _on_gbs_playlist_error"
      contains: "_gbs_playlist_widget"
    - path: "tests/test_now_playing_panel.py"
      provides: "Phase 60 active-playlist tests added — hide-when-non-gbs, populate-from-mock, timer-pauses, stale-token-discard, auth-expired-hides"
      min_lines: 200
  key_links:
    - from: "NowPlayingPanel.bind_station(station)"
      to: "NowPlayingPanel._refresh_gbs_visibility"
      via: "Single call site (Phase 64 D-04 invariant)"
      pattern: "_refresh_gbs_visibility\\(\\)"
    - from: "NowPlayingPanel._gbs_poll_timer.timeout"
      to: "NowPlayingPanel._on_gbs_poll_tick"
      via: "QA-05 bound-method connection; QTimer 15000ms cadence"
      pattern: "_gbs_poll_timer\\.timeout\\.connect\\(self\\._on_gbs_poll_tick\\)|setInterval\\(15000\\)"
    - from: "NowPlayingPanel._on_gbs_poll_tick"
      to: "musicstreamer.gbs_api.fetch_active_playlist"
      via: "Worker thread (mirror cover_art pattern); Qt.QueuedConnection signal completion"
      pattern: "fetch_active_playlist|_GbsPollWorker"
    - from: "NowPlayingPanel._on_gbs_playlist_ready"
      to: "_gbs_playlist_widget.addItem"
      via: "Render queue rows; PlainText only"
      pattern: "_gbs_playlist_widget\\.(addItem|clear)"
---

<objective>
Add the GBS.FM active-playlist widget to `NowPlayingPanel` (D-06): a hide-when-not-GBS QListWidget that polls `/ajax` every 15 seconds via a worker thread to display the current track + upcoming queue. Auth-gated (D-06b RESOLVED — login-required).

Purpose: Closes SC #3 of ROADMAP §Phase 60 ("the Now Playing surface shows the active GBS.FM playlist").

Output: ~150 LOC added to now_playing_panel.py (1 widget + 1 timer + 1 poll-token + 1 worker class + 4 handler methods) + ~150 LOC test extensions.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/60-gbs-fm-integration/60-CONTEXT.md
@.planning/phases/60-gbs-fm-integration/60-RESEARCH.md
@.planning/phases/60-gbs-fm-integration/60-PATTERNS.md
@.planning/phases/60-gbs-fm-integration/60-VALIDATION.md
@.planning/phases/60-gbs-fm-integration/60-02-SUMMARY.md
@.planning/phases/60-gbs-fm-integration/60-04-SUMMARY.md
@musicstreamer/ui_qt/now_playing_panel.py
@musicstreamer/gbs_api.py

<interfaces>
From now_playing_panel.py (Phase 64 + cover_art precedents):
```python
class NowPlayingPanel(QWidget):
    def __init__(self, player, repo, parent=None) -> None:
        # Construction at line 125+
        # Layout: vertical with center column (name_provider_label, icy_label, controls row,
        #   then optional widgets: _sibling_label (Phase 64 hide-when-empty), _stats_widget)

    def bind_station(self, station: Station) -> None:
        """Called when active station changes (line 353).
        LAST line: self._refresh_siblings() — Phase 64 D-04 single-call-site invariant.
        Phase 60: APPEND self._refresh_gbs_visibility() as the new last line.
        """

    # Phase 64 sibling label (analog for hide-when-empty):
    self._sibling_label = QLabel("", self)
    self._sibling_label.setVisible(False)

    # Cover art async pattern (analog for worker-thread + token guard):
    self._cover_fetch_token: int = 0
    def _fetch_cover_art_async(self, icy_title: str) -> None:
        self._cover_fetch_token += 1
        token = self._cover_fetch_token
        emit = self.cover_art_ready.emit  # bound Signal.emit
        def _cb(path_or_none):
            emit(f"{token}:{path_or_none or ''}")
        fetch_cover_art(icy_title, _cb)

    def _on_cover_art_ready(self, payload: str) -> None:
        token_str, _, path = payload.partition(":")
        try: token = int(token_str)
        except ValueError: return
        if token != self._cover_fetch_token: return  # stale — discard
        ...
```

From musicstreamer/gbs_api.py (Plan 60-02):
```python
def fetch_active_playlist(cookies: MozillaCookieJar, cursor: dict | None = None) -> dict:
    """Returns: {now_playing_entryid?, now_playing_songid?, icy_title?, song_length?,
       song_position?, user_vote=0, score, queue_html_snippets=[], removed_ids=[],
       last_add_entryid?, last_removal_id?, queue_summary?}
    Raises GbsAuthExpiredError on 302→/accounts/login/."""

def load_auth_context() -> Optional[MozillaCookieJar]:
    """Returns loaded jar from paths.gbs_cookies_path() or None."""

class GbsAuthExpiredError(GbsApiError): ...
```

From musicstreamer/paths.py (Plan 60-02):
```python
def gbs_cookies_path() -> str: ...
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add _gbs_playlist_widget + _gbs_poll_timer + _GbsPollWorker + visibility/poll/render handlers to now_playing_panel.py</name>
  <read_first>
    - musicstreamer/ui_qt/now_playing_panel.py (read in full — focus on lines 125-340 __init__/layout, 353-381 bind_station, 575-601 cover_art async pattern, 661-688 _refresh_siblings hide-when-empty pattern)
    - musicstreamer/gbs_api.py (verify Plan 60-02 surface — fetch_active_playlist, load_auth_context, GbsAuthExpiredError)
    - musicstreamer/paths.py (gbs_cookies_path)
    - .planning/phases/60-gbs-fm-integration/60-PATTERNS.md (§"musicstreamer/ui_qt/now_playing_panel.py modifications" — exact insertion shape)
    - .planning/phases/60-gbs-fm-integration/60-RESEARCH.md (§Pitfalls 1, 5, 11; §Code Examples §Example 5 hide-when-empty shape)
  </read_first>
  <behavior>
    - New `_gbs_playlist_widget` QListWidget child added to layout below the existing center column (after _stats_widget if present, otherwise at the end of the central layout)
    - Widget initially `setVisible(False)`; only shown when bound station is GBS.FM AND user logged in
    - New `_gbs_poll_timer` QTimer with 15000ms interval; bound-method connection to `_on_gbs_poll_tick` (QA-05)
    - New `_gbs_poll_token: int = 0` counter incremented on each poll tick (cover_art precedent for stale-response discard)
    - New `_gbs_poll_worker` reference for QThread retention (SYNC-05)
    - `_refresh_gbs_visibility(self) -> None`: predicate gates visibility; starts/stops the timer. Inputs: `self._station` + `os.path.exists(paths.gbs_cookies_path())`
    - `_on_gbs_poll_tick`: increments token, captures token snapshot, kicks off `_GbsPollWorker(token, cookies)` thread, retains worker; thread emits Qt-queued signal on completion
    - `_GbsPollWorker(QThread)`: in run() calls `gbs_api.fetch_active_playlist(self._cookies)`, emits `playlist_ready(int, dict)` (token + state) on success, `playlist_error(int, str)` on failure (string "auth_expired" sentinel for GbsAuthExpiredError)
    - `_on_gbs_playlist_ready(token, state)`: discards if token != current; clears widget; appends one item per parsed queue row (PlainText), prepends current track item with marker
    - `_on_gbs_playlist_error(token, msg)`: discards if token != current; if msg=="auth_expired" → hides widget + stops timer (no toast spam); else logs warning silently
    - `bind_station(self, station)`: appends `self._refresh_gbs_visibility()` AS THE LAST LINE (Phase 64 D-04 single-call-site invariant)
  </behavior>
  <action>
**Step A — top of file (imports):**

Add (alongside existing imports):
```python
import logging
from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtWidgets import QListWidget, QListWidgetItem
```
(Most of these are likely already imported — verify and only add what's missing.)

**Step B — _GbsPollWorker class** (insert at module top, before `class _MutedLabel` at line 55, OR before `class NowPlayingPanel` at line 95 — wherever sibling worker classes live):

```python
class _GbsPollWorker(QThread):
    """Phase 60 D-06a / GBS-01c: poll gbs_api.fetch_active_playlist on a worker thread.

    Mirrors cover_art's worker-thread + Qt-queued signal pattern. Pitfall 1
    + Pitfall 5: token guard on the consuming side discards stale responses
    when station re-binds mid-poll.
    """
    playlist_ready = Signal(int, object)   # (token, state_dict)
    playlist_error = Signal(int, str)      # (token, msg or sentinel)

    def __init__(self, token: int, cookies, cursor=None, parent=None):
        super().__init__(parent)
        self._token = token
        self._cookies = cookies
        self._cursor = cursor

    def run(self):
        from musicstreamer import gbs_api
        try:
            state = gbs_api.fetch_active_playlist(self._cookies, cursor=self._cursor)
            self.playlist_ready.emit(self._token, state)
        except Exception as exc:
            if isinstance(exc, gbs_api.GbsAuthExpiredError):
                self.playlist_error.emit(self._token, "auth_expired")
            else:
                self.playlist_error.emit(self._token, str(exc))
```

**Step C — extend `NowPlayingPanel.__init__`** (around the layout-builder section near line 250-310 — after `_sibling_label` and before/alongside `_stats_widget`):

```python
        # === Phase 60 D-06: GBS.FM active-playlist widget (hide-when-empty) ===
        # Phase 64 _sibling_label precedent — invisible until populated.
        # Pitfall 11: PlainText for gbs.fm-side strings (artist/title/score).
        self._gbs_playlist_widget = QListWidget(self)
        self._gbs_playlist_widget.setVisible(False)
        self._gbs_playlist_widget.setMaximumHeight(180)  # ~6 rows; lets controls keep prominence
        center.addWidget(self._gbs_playlist_widget)
        # NOTE: identifier `center` is the central QVBoxLayout used by other optional widgets
        # (sibling_label, stats_widget). If your file uses a different name, follow the
        # existing convention used at the _sibling_label addWidget call.

        # Phase 60 D-06a RESOLVED: 15s poll cadence (matches gbs.fm web UI DELAY=15000)
        self._gbs_poll_timer = QTimer(self)
        self._gbs_poll_timer.setInterval(15000)
        self._gbs_poll_timer.timeout.connect(self._on_gbs_poll_tick)  # QA-05

        # Pitfall 1 + cover_art precedent: stale-response token guard
        self._gbs_poll_token: int = 0
        self._gbs_poll_worker = None  # SYNC-05 retention slot

        # Cursor for the /ajax endpoint — advanced by every successful poll.
        # See gbs_api.fetch_active_playlist signature: cursor keys are position,
        # last_comment, last_removal, last_add, now_playing.
        self._gbs_poll_cursor: dict = {}
```

**Step D — extend `bind_station`** (line 353-381). Append this AS THE LAST LINE inside `bind_station`:

```python
        # Phase 60 D-06: re-derive GBS active-playlist visibility for the
        # newly bound station. Phase 64 D-04 invariant — _refresh_gbs_visibility
        # is the ONLY call site (test_refresh_gbs_visibility_runs_once_per_bind_station_call
        # locks this).
        self._refresh_gbs_visibility()
```

(Place AFTER `self._refresh_siblings()` — both run last; ordering between them does not matter, but the test for D-06 single-call-site invariant must remain green.)

**Step E — Add the three handler methods** (place near _refresh_siblings around line 646-690):

```python
    def _is_gbs_logged_in(self) -> bool:
        """Phase 60 D-04 ladder #3: true if cookies file exists."""
        from musicstreamer import paths
        return os.path.exists(paths.gbs_cookies_path())

    def _refresh_gbs_visibility(self) -> None:
        """Phase 60 D-06: show widget iff GBS.FM station bound AND logged in.

        Side effect: starts the 15s poll timer when shown; stops when hidden.
        Pitfall 5 — pause polling when not visible.
        """
        is_gbs = (self._station is not None
                 and self._station.provider_name == "GBS.FM")
        logged_in = self._is_gbs_logged_in()
        should_show = is_gbs and logged_in

        self._gbs_playlist_widget.setVisible(should_show)

        if should_show:
            # Reset cursor on station change — fresh start
            self._gbs_poll_cursor = {}
            self._gbs_playlist_widget.clear()
            placeholder = QListWidgetItem("Loading playlist…")
            self._gbs_playlist_widget.addItem(placeholder)
            # Trigger an immediate first poll (don't wait 15s)
            self._on_gbs_poll_tick()
            if not self._gbs_poll_timer.isActive():
                self._gbs_poll_timer.start()
        else:
            self._gbs_poll_timer.stop()
            self._gbs_playlist_widget.clear()

    def _on_gbs_poll_tick(self) -> None:
        """Phase 60 D-06a: kick a worker that hits /ajax with the cursor."""
        from musicstreamer import gbs_api
        cookies = gbs_api.load_auth_context()
        if cookies is None:
            # Auth disappeared mid-poll — refresh visibility (which will stop timer)
            self._refresh_gbs_visibility()
            return
        self._gbs_poll_token += 1
        token = self._gbs_poll_token
        worker = _GbsPollWorker(token, cookies, cursor=dict(self._gbs_poll_cursor), parent=self)
        worker.playlist_ready.connect(self._on_gbs_playlist_ready)  # QA-05
        worker.playlist_error.connect(self._on_gbs_playlist_error)  # QA-05
        self._gbs_poll_worker = worker  # SYNC-05 retain
        worker.start()

    def _on_gbs_playlist_ready(self, token: int, state) -> None:
        """Render the playlist state. Pitfall 1 — discard stale tokens.

        HIGH 4 fix: `position` is a seconds-into-current-song cursor, NOT a
        monotonic pagination cursor. When the `now_playing` entryid changes
        (track transition), we MUST reset position=0 — carrying the previous
        song's `song_position` into the next /ajax call gives gbs.fm a stale
        delta reference. Track changes detected by comparing new entryid
        against the previously-seen one.
        """
        if token != self._gbs_poll_token:
            return  # stale — newer poll in flight
        # Advance cursor for next tick
        new_entryid = state.get("now_playing_entryid")
        prev_entryid = self._gbs_poll_cursor.get("now_playing")
        track_changed = (
            new_entryid is not None and new_entryid != prev_entryid
        )
        if new_entryid is not None:
            self._gbs_poll_cursor["now_playing"] = new_entryid
        if state.get("last_removal_id") is not None:
            self._gbs_poll_cursor["last_removal"] = state["last_removal_id"]
        if track_changed:
            # HIGH 4 fix: reset position cursor on track transition.
            self._gbs_poll_cursor["position"] = 0
        elif state.get("song_position") is not None:
            try:
                self._gbs_poll_cursor["position"] = int(state["song_position"])
            except (TypeError, ValueError):
                pass
        # Render: clear + add now-playing row + parsed queue rows.
        # Pitfall 11 — PlainText for everything; QListWidgetItem default is PlainText.
        self._gbs_playlist_widget.clear()
        icy = state.get("icy_title")
        if icy:
            now_item = QListWidgetItem(f"▶ {icy}")
            self._gbs_playlist_widget.addItem(now_item)
        # Queue rows: each "adds" snippet is HTML; we use the queue_summary as a
        # single-line summary for v1 (Pitfall 6 — defensive HTML parsing happens
        # in gbs_api). Phase 60 v1 ships the simplest visible payload; richer
        # parsing of "adds" rows is a deferred polish (D-06c partial — no
        # click-to-favorite from rows; full row parsing in queue is also deferred
        # given v1's "show what's playing" minimum bar).
        summary = state.get("queue_summary")
        if summary:
            self._gbs_playlist_widget.addItem(QListWidgetItem(summary))
        score = state.get("score")
        if score:
            self._gbs_playlist_widget.addItem(QListWidgetItem(f"Score: {score}"))

    def _on_gbs_playlist_error(self, token: int, msg: str) -> None:
        """Auth expiry → hide widget + stop timer; other errors → silent log."""
        if token != self._gbs_poll_token:
            return
        if msg == "auth_expired":
            # Pitfall 3: don't toast-spam on every poll tick; just hide.
            self._gbs_playlist_widget.setVisible(False)
            self._gbs_poll_timer.stop()
            self._gbs_playlist_widget.clear()
        else:
            # Pitfall 5 + 7: don't retry; just log.
            logging.getLogger(__name__).warning("GBS.FM playlist poll failed: %s", msg)
```

Note about identifier `center`: the existing file uses a layout variable for the center column. Read lines 200-310 to find the actual variable name (likely `center` or similar) used in `center.addWidget(self._sibling_label)` at the matching line in current code. Use the SAME variable for `_gbs_playlist_widget`.

Decisions implemented: D-06 (widget on NowPlayingPanel hide-when-not-GBS), D-06a RESOLVED (15s polling), D-06b RESOLVED (login-only), D-06c (no click-to-favorite — explicit non-implementation), Pitfall 1 (token guard), Pitfall 3 (auth-expired no toast spam), Pitfall 5 (pause on hidden), Pitfall 11 (PlainText), QA-05.
  </action>
  <verify>
    <automated>grep -q '_gbs_playlist_widget' musicstreamer/ui_qt/now_playing_panel.py &amp;&amp; grep -q '_GbsPollWorker' musicstreamer/ui_qt/now_playing_panel.py &amp;&amp; grep -q '_refresh_gbs_visibility' musicstreamer/ui_qt/now_playing_panel.py &amp;&amp; grep -q 'setInterval(15000)' musicstreamer/ui_qt/now_playing_panel.py &amp;&amp; grep -q '_gbs_poll_token' musicstreamer/ui_qt/now_playing_panel.py &amp;&amp; grep -q 'auth_expired' musicstreamer/ui_qt/now_playing_panel.py &amp;&amp; ! grep -E 'timeout\.connect\(lambda' musicstreamer/ui_qt/now_playing_panel.py &amp;&amp; python -c "import ast; ast.parse(open('musicstreamer/ui_qt/now_playing_panel.py').read())"</automated>
  </verify>
  <done>
- _gbs_playlist_widget (QListWidget) attribute exists, initially invisible
- _gbs_poll_timer with 15000ms interval, bound-method timeout connection
- _gbs_poll_token counter for stale-response guard
- _GbsPollWorker class exists with playlist_ready(int, object) + playlist_error(int, str) signals
- _refresh_gbs_visibility called as last line of bind_station
- _is_gbs_logged_in returns os.path.exists(paths.gbs_cookies_path())
- auth_expired path hides widget + stops timer (no toast spam)
- Module parses cleanly
- No QA-05 lambda violations
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add Phase 60 active-playlist tests to tests/test_now_playing_panel.py</name>
  <read_first>
    - tests/test_now_playing_panel.py (read full — Phase 64 hide-when-empty test pattern, FakePlayer/FakeRepo construction)
    - musicstreamer/ui_qt/now_playing_panel.py (post-Task-1 state)
    - .planning/phases/60-gbs-fm-integration/60-PATTERNS.md (§"tests/ui_qt/test_now_playing_panel_gbs.py")
    - .planning/phases/60-gbs-fm-integration/60-VALIDATION.md (§"Per-Task Verification Map" GBS-01c rows)
  </read_first>
  <behavior>
    Append at the end of `tests/test_now_playing_panel.py` (do NOT touch existing tests):
      - test_gbs_playlist_hidden_for_non_gbs (GBS-01c): bind a station with provider_name="DI.fm" → widget invisible
      - test_gbs_playlist_hidden_when_logged_out (D-06b): GBS station, no cookies file → widget invisible + timer stopped
      - test_gbs_playlist_visible_when_gbs_and_logged_in: GBS station + cookies file → widget visible + timer started
      - test_gbs_playlist_populates_from_mock_state: emit playlist_ready signal directly with a fixture state → widget contains 3 items (now-playing + queue summary + score)
      - test_gbs_poll_timer_pauses_when_widget_hidden (D-06a / Pitfall 5): bind GBS+logged-in then bind non-GBS → timer is stopped
      - test_gbs_stale_token_discarded (Pitfall 1): two ticks; first response arrives with old token → render is no-op
      - test_gbs_auth_expired_hides_widget_no_toast (Pitfall 3): emit playlist_error(token, "auth_expired") → widget invisible + timer stopped + no toast emitted
      - test_refresh_gbs_visibility_runs_once_per_bind_station (Phase 64 D-04 invariant): mock _refresh_gbs_visibility, call bind_station once → method called exactly once
      - **test_gbs_playlist_resets_position_on_track_change (HIGH 4 fix):** two consecutive _on_gbs_playlist_ready calls with DIFFERENT now_playing_entryid; first call has song_position=200, second call has different entryid + song_position=15; assert `panel._gbs_poll_cursor["position"] == 0` after the second call (reset on track change), NOT 15 or 200. Then a third call with the SAME entryid as the second + song_position=42 → assert `position == 42` (advances normally when entryid is stable).
  </behavior>
  <action>
Append the following at the end of `tests/test_now_playing_panel.py`:

```python
# ===========================================================================
# Phase 60 / GBS-01c: active-playlist widget on NowPlayingPanel
# Pattern source: 60-PATTERNS.md §"tests/ui_qt/test_now_playing_panel_gbs.py"
# Hide-when-empty contract from Phase 64 / Phase 51.
# ===========================================================================

import os
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QTimer
from musicstreamer import paths
from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel


def _make_station(provider_name: str = "GBS.FM", name: str = "GBS.FM"):
    """Lightweight Station-shaped object for bind_station tests."""
    s = MagicMock()
    s.id = 1
    s.name = name
    s.provider_name = provider_name
    s.tags = ""
    s.streams = []
    return s


def _construct_panel(qtbot, fake_repo):
    """Match the existing test_now_playing_panel.py construction idiom."""
    fake_player = MagicMock()
    fake_player.title_changed = MagicMock(); fake_player.title_changed.connect = MagicMock()
    fake_player.elapsed_updated = MagicMock(); fake_player.elapsed_updated.connect = MagicMock()
    fake_player.playing_state_changed = MagicMock(); fake_player.playing_state_changed.connect = MagicMock()
    fake_player.buffer_progress = MagicMock(); fake_player.buffer_progress.connect = MagicMock()
    panel = NowPlayingPanel(fake_player, fake_repo)
    qtbot.addWidget(panel)
    return panel


def test_gbs_playlist_hidden_for_non_gbs(qtbot, fake_repo, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_panel(qtbot, fake_repo)
    panel.bind_station(_make_station(provider_name="DI.fm"))
    assert panel._gbs_playlist_widget.isVisible() is False


def test_gbs_playlist_hidden_when_logged_out(qtbot, fake_repo, tmp_path, monkeypatch):
    """D-06b: cookies file absent → widget hidden, timer stopped."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_panel(qtbot, fake_repo)
    panel.bind_station(_make_station())
    assert panel._gbs_playlist_widget.isVisible() is False
    assert panel._gbs_poll_timer.isActive() is False


def test_gbs_playlist_visible_when_gbs_and_logged_in(qtbot, fake_repo, tmp_path, monkeypatch):
    """D-06: GBS + logged-in → widget visible + timer started."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_panel(qtbot, fake_repo)
    # Stub the worker construction so bind_station doesn't actually hit network
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_station())
    assert panel._gbs_playlist_widget.isVisible() is True
    assert panel._gbs_poll_timer.isActive() is True


def test_gbs_playlist_populates_from_mock_state(qtbot, fake_repo, tmp_path, monkeypatch):
    """Emitting playlist_ready directly populates the widget."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_panel(qtbot, fake_repo)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_station())
    panel._gbs_poll_token = 5  # set known token
    state = {
        "now_playing_entryid": 1810736,
        "now_playing_songid": 782491,
        "icy_title": "Crippling Alcoholism - Templeton",
        "queue_summary": "Playlist is 11:21 long with 3 dongs",
        "score": "5.0 (1 vote)",
        "user_vote": 0,
        "queue_html_snippets": [],
        "removed_ids": [],
    }
    panel._on_gbs_playlist_ready(5, state)
    items = [panel._gbs_playlist_widget.item(i).text()
            for i in range(panel._gbs_playlist_widget.count())]
    # Now-playing prefixed
    assert any("Crippling Alcoholism - Templeton" in t for t in items)
    # Queue summary
    assert any("Playlist is 11:21" in t for t in items)
    # Score
    assert any("5.0 (1 vote)" in t for t in items)


def test_gbs_poll_timer_pauses_when_widget_hidden(qtbot, fake_repo, tmp_path, monkeypatch):
    """Pitfall 5 / D-06a: rebinding to a non-GBS station must stop the timer."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_panel(qtbot, fake_repo)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_station())
    assert panel._gbs_poll_timer.isActive() is True
    # Re-bind to non-GBS
    panel.bind_station(_make_station(provider_name="DI.fm"))
    assert panel._gbs_poll_timer.isActive() is False
    assert panel._gbs_playlist_widget.isVisible() is False


def test_gbs_stale_token_discarded(qtbot, fake_repo, tmp_path, monkeypatch):
    """Pitfall 1: an old-token playlist_ready must NOT mutate the widget."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_panel(qtbot, fake_repo)
    panel._gbs_poll_token = 10
    # Pre-populate so we can detect mutation
    panel._gbs_playlist_widget.addItem("BASELINE")
    assert panel._gbs_playlist_widget.count() == 1
    # Emit with stale token
    panel._on_gbs_playlist_ready(3, {"icy_title": "should not render"})
    assert panel._gbs_playlist_widget.count() == 1
    assert panel._gbs_playlist_widget.item(0).text() == "BASELINE"


def test_gbs_auth_expired_hides_widget_no_toast(qtbot, fake_repo, tmp_path, monkeypatch):
    """Pitfall 3: auth_expired error → widget hidden + timer stopped, no toast spam."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_panel(qtbot, fake_repo)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_station())
    panel._gbs_poll_token = 5
    panel._gbs_playlist_widget.setVisible(True)
    panel._gbs_poll_timer.start()
    panel._on_gbs_playlist_error(5, "auth_expired")
    assert panel._gbs_playlist_widget.isVisible() is False
    assert panel._gbs_poll_timer.isActive() is False


def test_refresh_gbs_visibility_runs_once_per_bind_station(qtbot, fake_repo, tmp_path, monkeypatch):
    """Phase 64 D-04 invariant: _refresh_gbs_visibility is called EXACTLY once per bind_station."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_panel(qtbot, fake_repo)
    counter = {"n": 0}
    original = panel._refresh_gbs_visibility
    def counting_refresh():
        counter["n"] += 1
        original()
    monkeypatch.setattr(panel, "_refresh_gbs_visibility", counting_refresh)
    panel.bind_station(_make_station(provider_name="DI.fm"))
    assert counter["n"] == 1
```

Decisions implemented: VALIDATION.md §Per-Task Verification Map GBS-01c rows; Pitfalls 1/3/5/11; D-06/D-06a/D-06b/D-06c.
  </action>
  <verify>
    <automated>pytest tests/test_now_playing_panel.py -x -q -k 'gbs or refresh_gbs' 2>&amp;1 | tail -15 &amp;&amp; pytest tests/test_now_playing_panel.py -x -q 2>&amp;1 | tail -5</automated>
  </verify>
  <done>
- 8 new tests in tests/test_now_playing_panel.py covering: hide for non-GBS, hide when logged out, visible when both, populate from mock state, timer pauses on rebind, stale-token discard, auth-expired hide, single-call-site invariant
- All existing tests in tests/test_now_playing_panel.py still pass (regression)
- pytest -x runs green
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| UI thread ↔ Worker thread | _GbsPollWorker runs every 15s; results cross via Signal/Slot Qt.QueuedConnection |
| gbs.fm /ajax response ↔ NowPlayingPanel widget | JSON event-array is parsed in gbs_api; widget renders folded state strings |
| AccountsDialog cookies file ↔ NowPlayingPanel auth gate | _is_gbs_logged_in checks os.path.exists(paths.gbs_cookies_path()) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-60-23 | DoS (3rd-party) | /ajax polling cumulative load | mitigate | 15s cadence (D-06a RESOLVED — matches gbs.fm web UI DELAY=15000); timer paused when widget hidden (Pitfall 5). |
| T-60-24 | Tampering | Stale-poll response renders against new station | mitigate | _gbs_poll_token incremented on each tick; consumer discards on token mismatch (Pitfall 1 + cover_art precedent). |
| T-60-25 | Information Disclosure | Score / icy_title rendered with HTML formatting | mitigate | Qt.TextFormat.PlainText via QListWidgetItem default; no Qt.RichText anywhere in this widget (Pitfall 11). |
| T-60-26 | Repudiation | Auth-expired surfaces as silent failure | mitigate | First auth_expired hides the widget + stops timer; user sees "playlist disappeared" naturally; AccountsDialog status (Plan 60-04) reflects "Not connected" via _is_gbs_connected; explicit reconnect via Accounts. Pitfall 3. |
| T-60-27 | DoS (UX) | Toast spam on every poll-tick error | mitigate | _on_gbs_playlist_error does NOT toast for auth_expired or generic errors — silent log only. Plan 60-03 import flow IS allowed to toast on auth-expired since it's a user-initiated action; passive polling is not. |

Citations: Pitfalls 1, 3, 5, 11 from RESEARCH.md.
</threat_model>

<verification>
```bash
pytest tests/test_now_playing_panel.py -x -q
pytest tests/test_gbs_api.py -x -q  # regression check
python -c "from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel, _GbsPollWorker; print('OK')"
pytest -x   # full suite green
```
</verification>

<success_criteria>
- _gbs_playlist_widget renders below the existing controls when GBS.FM bound + logged in
- Widget hides automatically when station changes to non-GBS or user logs out
- _gbs_poll_timer with 15000ms interval; only active while widget visible
- _GbsPollWorker emits Qt-queued signals on completion (Pitfall 1 token guard active)
- Auth-expired hides widget + stops timer (no toast spam)
- 8 new pytest-qt tests pass; existing tests unaffected
- Full pytest -x runs green
</success_criteria>

<output>
After completion, create `.planning/phases/60-gbs-fm-integration/60-05-SUMMARY.md`
</output>
