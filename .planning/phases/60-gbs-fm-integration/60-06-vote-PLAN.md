---
phase: 60
plan: 06
type: execute
wave: 4
depends_on: ["60-02", "60-04", "60-05"]
files_modified:
  - musicstreamer/ui_qt/now_playing_panel.py
  - tests/test_now_playing_panel.py
autonomous: true
requirements: [GBS-01d]
tags: [phase60, now-playing, vote, optimistic-ui, gbs-fm]

must_haves:
  truths:
    - "NowPlayingPanel renders 5 vote buttons (labeled '1' through '5') near the controls row when bound station is GBS.FM AND user is logged in"
    - "Vote buttons hidden when station is non-GBS OR no station bound OR user logged out (mirrors playlist-widget hide-when-empty contract)"
    - "Click → button visually highlights immediately (optimistic UI per D-07a / Pitfall 2); worker thread sends GET /ajax?vote=N&now_playing=<entryid>; on success the API-returned user_vote drives the FINAL highlighted button (server is source of truth)"
    - "Click → API failure (network down, 5xx, etc) → button reverts to prior state + show_toast surfaces error; no silent inconsistency"
    - "Auth-expired during vote → toast 'GBS.FM session expired — reconnect via Accounts' + button reverts; widget DOES NOT hide (vote is user-initiated; D-06 already handles passive auth-expiry)"
    - "Vote button entryid stamps from the latest /ajax now_playing event ONLY (Pitfall 1 — never from ICY title)"
    - "Re-binding to a non-GBS station mid-vote: stale response is discarded via _gbs_vote_token guard"
    - "Vote=0 (clear) is a valid submission — clicking the same button that's already highlighted clears the vote"
    - "All connections are bound methods (QA-05); button vote_value carried via QPushButton.setProperty('vote_value', N)"
  artifacts:
    - path: "musicstreamer/ui_qt/now_playing_panel.py"
      provides: "5 _gbs_vote_buttons + _gbs_vote_token + _gbs_vote_worker + _GbsVoteWorker class + _on_gbs_vote_clicked + _on_gbs_vote_finished + _on_gbs_vote_error + _gbs_current_entryid sourced from /ajax"
      contains: "_gbs_vote_buttons"
    - path: "tests/test_now_playing_panel.py"
      provides: "Phase 60 vote tests appended — hide-when-logged-out, optimistic-success, optimistic-rollback, entryid-from-ajax, stale-token, vote-zero-clear"
      min_lines: 200
  key_links:
    - from: "NowPlayingPanel._gbs_vote_buttons[i].clicked"
      to: "NowPlayingPanel._on_gbs_vote_clicked"
      via: "QA-05 bound-method connection; vote_value property carries 1..5"
      pattern: "clicked\\.connect\\(self\\._on_gbs_vote_clicked\\)|setProperty\\(.vote_value."
    - from: "NowPlayingPanel._on_gbs_vote_clicked"
      to: "musicstreamer.gbs_api.vote_now_playing"
      via: "_GbsVoteWorker on a QThread; entryid comes from self._gbs_current_entryid (set by /ajax poll)"
      pattern: "vote_now_playing|_GbsVoteWorker"
    - from: "NowPlayingPanel._on_gbs_vote_finished"
      to: "_gbs_vote_buttons highlight reflects API-returned user_vote (not optimistic guess)"
      via: "Pitfall 2 — server is source of truth"
      pattern: "user_vote.*setChecked|_apply_vote_highlight"
    - from: "NowPlayingPanel._on_gbs_playlist_ready (Plan 60-05)"
      to: "self._gbs_current_entryid = state['now_playing_entryid']"
      via: "Pitfall 1 — entryid only updates from /ajax now_playing event"
      pattern: "_gbs_current_entryid.*now_playing_entryid|now_playing_entryid.*_gbs_current_entryid"
---

<objective>
Add the GBS.FM vote control to `NowPlayingPanel` (D-07): five 1–5 buttons with optimistic UI + worker-thread round-trip + rollback on error, integrated with the active-playlist poll from Plan 60-05 so the entryid is always sourced from the latest `/ajax` `now_playing` event (Pitfall 1).

Purpose: Closes SC #4 of ROADMAP §Phase 60 ("the user can vote on the currently-playing track via a Now Playing control; votes round-trip to the GBS.FM API with optimistic UI").

Output: ~120 LOC added to now_playing_panel.py (5 button construction + 1 worker class + 4 handler methods + entryid stamping in playlist-ready) + ~200 LOC test extensions.
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
@.planning/phases/60-gbs-fm-integration/60-05-SUMMARY.md
@musicstreamer/ui_qt/now_playing_panel.py
@musicstreamer/gbs_api.py

<interfaces>
From now_playing_panel.py (Plan 60-05 added the active-playlist poll):
```python
class _GbsPollWorker(QThread): ...   # Plan 60-05
class NowPlayingPanel(QWidget):
    self._gbs_playlist_widget: QListWidget
    self._gbs_poll_timer: QTimer (15000ms)
    self._gbs_poll_token: int
    def _refresh_gbs_visibility(self): ...
    def _is_gbs_logged_in(self) -> bool: ...   # checks paths.gbs_cookies_path()
    def _on_gbs_playlist_ready(self, token, state): ...
    # State carries 'now_playing_entryid' and 'user_vote' fields
```

From musicstreamer/gbs_api.py (Plan 60-02):
```python
def vote_now_playing(entryid: int, vote: int, cookies) -> dict:
    """vote in {0,1,2,3,4,5}. Returns {user_vote, score}.
    Raises GbsAuthExpiredError on 302→/accounts/login/.
    Raises ValueError on invalid vote value."""

class GbsAuthExpiredError(GbsApiError): ...
def load_auth_context() -> Optional[MozillaCookieJar]: ...
```

From now_playing_panel.py (existing star-button precedent — line 491-519):
```python
def _on_star_clicked(self) -> None:
    if self._station is None or not self._last_icy_title:
        return
    is_fav = self._repo.is_favorited(self._station.name, self._last_icy_title)
    if is_fav:
        ...
        self.star_btn.setIcon(...)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add 5 vote buttons + _GbsVoteWorker + click/finished/error handlers + entryid stamping to now_playing_panel.py</name>
  <read_first>
    - musicstreamer/ui_qt/now_playing_panel.py (post Plan 60-05 state — read sections: __init__ around line 250-310 (where _gbs_playlist_widget was added in 60-05); _refresh_gbs_visibility (added in 60-05); _on_gbs_playlist_ready (60-05); existing star button precedent lines 261-271 + 491-519)
    - musicstreamer/gbs_api.py (vote_now_playing signature + return shape)
    - .planning/phases/60-gbs-fm-integration/60-PATTERNS.md (§"musicstreamer/ui_qt/now_playing_panel.py modifications" — vote button section with optimistic UI + bound-method click pattern)
    - .planning/phases/60-gbs-fm-integration/60-RESEARCH.md (§Code Examples §Example 5 — vote-button hide-when-empty + setProperty('vote_value', v); §Pitfalls 1, 2, 7)
  </read_first>
  <behavior>
    - 5 QPushButton widgets `_gbs_vote_buttons[0..4]` labeled "1".."5", initially `setVisible(False)`
    - Buttons added to a horizontal QHBoxLayout `_gbs_vote_row`, inserted AFTER the existing controls row but BEFORE `_gbs_playlist_widget` (or wherever the panel's central layout makes it most discoverable per D-07 "near the existing star/pause/stop/stream-picker row")
    - Each button: `setProperty("vote_value", i+1)`; `clicked.connect(self._on_gbs_vote_clicked)` (QA-05 bound method)
    - `_gbs_current_entryid: Optional[int] = None` — updated ONLY by `_on_gbs_playlist_ready` from Plan 60-05's poll
    - `_gbs_vote_token: int = 0` — guards stale vote responses
    - `_gbs_vote_worker = None` — SYNC-05 retention slot
    - `_refresh_gbs_visibility` (existing from 60-05) extends to ALSO show/hide vote buttons via the SAME predicate (is_gbs AND logged_in)
    - `_on_gbs_playlist_ready` (existing from 60-05) extends to also: (a) capture `now_playing_entryid` into `self._gbs_current_entryid`, (b) call a new helper `_apply_vote_highlight(state.get('user_vote', 0))`
    - `_apply_vote_highlight(vote_value)`: sets `setChecked(True)` only on the button matching vote_value; all others setChecked(False); use `QPushButton.setCheckable(True)` on each button at construction
    - `_on_gbs_vote_clicked` (slot for ALL 5 buttons; uses sender + property): determines the clicked vote value via `self.sender().property("vote_value")`; ignores click if `self._gbs_current_entryid is None` (no track context); captures `prior_vote = current_highlighted_vote_or_0` for rollback; OPTIMISTICALLY highlights the clicked button; kicks _GbsVoteWorker(entryid, vote_value, cookies, token, prior_vote) on a thread
    - `_GbsVoteWorker(QThread)`: `vote_finished = Signal(int, int, int, str)` (token, server_user_vote, prior_vote_for_rollback_on_error_path_only, score_str); `vote_error = Signal(int, int, str)` (token, prior_vote, msg_or_'auth_expired'); calls `gbs_api.vote_now_playing(entryid, vote, cookies)` returning {user_vote, score}; emits accordingly
    - `_on_gbs_vote_finished`: if token stale → ignore; else apply server-returned user_vote via `_apply_vote_highlight` (Pitfall 2 — server is truth)
    - `_on_gbs_vote_error`: if token stale → ignore; rollback to prior_vote via `_apply_vote_highlight`; if msg=="auth_expired" → toast "GBS.FM session expired — reconnect via Accounts"; else toast "Vote failed: {msg}"
  </behavior>
  <action>
**Step A — Add `_GbsVoteWorker` class** alongside `_GbsPollWorker` (added in 60-05). Place near the top of `now_playing_panel.py` with the other QThread classes:

```python
class _GbsVoteWorker(QThread):
    """Phase 60 D-07a / GBS-01d: send a vote off the UI thread.

    Mirrors _GbsPollWorker shape (Plan 60-05). Pitfall 2: server is truth —
    payload includes the API-returned user_vote so the consumer can confirm
    or rollback the optimistic highlight.
    """
    # finished payload: (token, server_user_vote, prior_vote_for_rollback_record, score_str)
    vote_finished = Signal(int, int, int, str)
    # error payload: (token, prior_vote_for_rollback, msg_or_'auth_expired')
    vote_error = Signal(int, int, str)

    def __init__(self, token: int, entryid: int, vote_value: int,
                cookies, prior_vote: int, parent=None):
        super().__init__(parent)
        self._token = token
        self._entryid = entryid
        self._vote_value = vote_value
        self._cookies = cookies
        self._prior_vote = prior_vote

    def run(self):
        from musicstreamer import gbs_api
        try:
            result = gbs_api.vote_now_playing(self._entryid, self._vote_value, self._cookies)
            server_vote = int(result.get("user_vote", 0))
            score = str(result.get("score", ""))
            self.vote_finished.emit(self._token, server_vote, self._prior_vote, score)
        except Exception as exc:
            if isinstance(exc, gbs_api.GbsAuthExpiredError):
                self.vote_error.emit(self._token, self._prior_vote, "auth_expired")
            else:
                self.vote_error.emit(self._token, self._prior_vote, str(exc))
```

**Step B — Extend `NowPlayingPanel.__init__`**: insert vote-button construction near where `_gbs_playlist_widget` is built (Plan 60-05). Add this block BEFORE the `_gbs_playlist_widget` add (so buttons sit above the playlist, near the controls):

```python
        # === Phase 60 D-07: GBS.FM vote control (5 buttons, 1-5 score) ===
        # RESEARCH §Claude's Discretion: 5 separate buttons (NOT thumb-up/down) —
        # gbs.fm uses a 1-5 score system. setCheckable(True) lets us highlight
        # the user's current vote. Pitfall 11: PlainText on the labels (default).
        from PySide6.QtWidgets import QHBoxLayout, QPushButton

        self._gbs_vote_row = QHBoxLayout()
        self._gbs_vote_row.setSpacing(4)
        self._gbs_vote_buttons: list[QPushButton] = []
        for v in range(1, 6):
            btn = QPushButton(str(v), self)
            btn.setCheckable(True)
            btn.setVisible(False)
            btn.setProperty("vote_value", v)
            btn.setMinimumWidth(32)
            btn.setMaximumWidth(48)
            btn.clicked.connect(self._on_gbs_vote_clicked)  # QA-05 bound method
            self._gbs_vote_row.addWidget(btn)
            self._gbs_vote_buttons.append(btn)
        # Add the row to the central layout. Use the same `center` variable
        # the active-playlist widget uses (Plan 60-05).
        center.addLayout(self._gbs_vote_row)

        # Pitfall 1: entryid stamps ONLY from /ajax now_playing event
        self._gbs_current_entryid = None

        # Pitfall 2 + cover_art precedent: stale-vote-response token guard
        self._gbs_vote_token: int = 0
        self._gbs_vote_worker = None  # SYNC-05 retain
```

**Step C — Extend `_refresh_gbs_visibility`** (defined in 60-05) to ALSO toggle the vote buttons. Modify the method to add at the end:

```python
        # Phase 60 D-07: vote buttons share the same auth+provider gate.
        for btn in self._gbs_vote_buttons:
            btn.setVisible(should_show)
        if not should_show:
            # Reset highlighting when leaving GBS context
            for btn in self._gbs_vote_buttons:
                btn.setChecked(False)
            self._gbs_current_entryid = None
```

**Step D — Extend `_on_gbs_playlist_ready`** (defined in 60-05) to capture entryid + apply server-side vote highlight. Add inside the existing method (after the cursor advancement, before/alongside the render block):

```python
        # Phase 60 D-07 / Pitfall 1: entryid captured ONLY from /ajax response
        if state.get("now_playing_entryid") is not None:
            new_entryid = int(state["now_playing_entryid"])
            if new_entryid != self._gbs_current_entryid:
                self._gbs_current_entryid = new_entryid
        # Pitfall 2 / D-07d: server's userVote is the source of truth
        self._apply_vote_highlight(int(state.get("user_vote", 0) or 0))
```

**Step E — Add helper + click + result + error handlers** (place near the existing _on_gbs_playlist_* handlers from 60-05):

```python
    def _apply_vote_highlight(self, vote_value: int) -> None:
        """Highlight the button matching vote_value; clear all others.

        vote_value=0 means no vote — all buttons unchecked.
        """
        for btn in self._gbs_vote_buttons:
            btn.setChecked(int(btn.property("vote_value") or 0) == int(vote_value))

    def _current_highlighted_vote(self) -> int:
        """Return the currently-highlighted vote value, or 0 if none."""
        for btn in self._gbs_vote_buttons:
            if btn.isChecked():
                v = btn.property("vote_value")
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return 0
        return 0

    def _on_gbs_vote_clicked(self) -> None:
        """D-07 / D-07a: optimistic UI + worker-thread vote round-trip.

        Pitfall 1: requires self._gbs_current_entryid (sourced from /ajax).
        Pitfall 2: optimistic highlight will be CONFIRMED or ROLLED BACK
        by the worker's signal handlers — server is truth.
        """
        from musicstreamer import gbs_api
        sender = self.sender()
        if sender is None or self._gbs_current_entryid is None:
            return  # No track context — ignore the click
        try:
            vote_value = int(sender.property("vote_value"))
        except (TypeError, ValueError):
            return
        prior_vote = self._current_highlighted_vote()
        # If clicking the SAME button that's already highlighted, this is
        # a vote-0 (clear) per RESEARCH §Capability 4 — sender is highlighted,
        # but Qt emitted clicked AFTER toggling, so isChecked is now False.
        # We treat that as: if vote_value == prior_vote → submit vote=0 (clear).
        if vote_value == prior_vote:
            submit_value = 0
            optimistic_value = 0
        else:
            submit_value = vote_value
            optimistic_value = vote_value
        # OPTIMISTIC highlight (will be confirmed by server response)
        self._apply_vote_highlight(optimistic_value)

        cookies = gbs_api.load_auth_context()
        if cookies is None:
            # Auth disappeared — rollback + refresh visibility
            self._apply_vote_highlight(prior_vote)
            self._refresh_gbs_visibility()
            return

        self._gbs_vote_token += 1
        token = self._gbs_vote_token
        worker = _GbsVoteWorker(
            token=token,
            entryid=int(self._gbs_current_entryid),
            vote_value=submit_value,
            cookies=cookies,
            prior_vote=prior_vote,
            parent=self,
        )
        worker.vote_finished.connect(self._on_gbs_vote_finished)  # QA-05
        worker.vote_error.connect(self._on_gbs_vote_error)        # QA-05
        self._gbs_vote_worker = worker  # SYNC-05 retain
        worker.start()

    def _on_gbs_vote_finished(self, token: int, server_user_vote: int,
                              prior_vote: int, score: str) -> None:
        """Pitfall 2: server is source of truth; apply server-returned vote."""
        if token != self._gbs_vote_token:
            return
        self._apply_vote_highlight(int(server_user_vote))
        # Optionally refresh score display in the playlist widget; v1 shows
        # the score in the playlist QListWidget on the next /ajax tick.

    def _on_gbs_vote_error(self, token: int, prior_vote: int, msg: str) -> None:
        """Pitfall 2 + Pitfall 7: rollback to prior_vote; surface error."""
        if token != self._gbs_vote_token:
            return
        self._apply_vote_highlight(int(prior_vote))
        # Find a toast surface — NowPlayingPanel doesn't own one; the parent
        # (MainWindow) does. Use the existing track_starred-style pattern OR
        # a new Signal. For minimum-diff, expose via an existing pattern: read
        # how `_on_star_clicked` / `track_starred` signal forwards. The cleanest
        # approach: add a new Signal `gbs_vote_error_toast = Signal(str)` and
        # connect it from MainWindow to show_toast (mirrors Phase 64
        # navigate_to_sibling pattern).
        if hasattr(self, "gbs_vote_error_toast"):
            if msg == "auth_expired":
                self.gbs_vote_error_toast.emit("GBS.FM session expired — reconnect via Accounts")
            else:
                truncated = (msg[:60] + "…") if len(msg) > 60 else msg
                self.gbs_vote_error_toast.emit(f"Vote failed: {truncated}")
```

**Step F — Add the toast Signal + main_window wiring:**

In `now_playing_panel.py` near the other panel-level Signal declarations (around line 95-125 where the class is defined):

```python
class NowPlayingPanel(QWidget):
    # ... existing Signals ...
    gbs_vote_error_toast = Signal(str)  # Phase 60 D-07a — fire on vote failure
```

In `musicstreamer/ui_qt/main_window.py`, add ONE line in `__init__` after the panel is constructed and connected (find the existing `self.now_playing_panel` construction site):

```python
        # Phase 60 D-07a: forward NowPlayingPanel vote-error toasts
        self.now_playing_panel.gbs_vote_error_toast.connect(self.show_toast)  # QA-05
```

(Read main_window.py around line 200-250 for where now_playing_panel signals are connected; mirror that pattern.)

Decisions implemented: D-07 (vote control on NowPlayingPanel), D-07a (optimistic UI + rollback), D-07b RESOLVED (entryid from /ajax — captured in _on_gbs_playlist_ready), D-07c (rate-limit handled via rollback toast), D-07d RESOLVED (server userVote drives highlight), Pitfalls 1/2/7/11, QA-05.
  </action>
  <verify>
    <automated>grep -q '_gbs_vote_buttons' musicstreamer/ui_qt/now_playing_panel.py &amp;&amp; grep -q '_GbsVoteWorker' musicstreamer/ui_qt/now_playing_panel.py &amp;&amp; grep -q '_apply_vote_highlight' musicstreamer/ui_qt/now_playing_panel.py &amp;&amp; grep -q '_gbs_current_entryid' musicstreamer/ui_qt/now_playing_panel.py &amp;&amp; grep -q '_gbs_vote_token' musicstreamer/ui_qt/now_playing_panel.py &amp;&amp; grep -q "setProperty(.vote_value" musicstreamer/ui_qt/now_playing_panel.py &amp;&amp; grep -q 'gbs_vote_error_toast' musicstreamer/ui_qt/now_playing_panel.py &amp;&amp; grep -q 'gbs_vote_error_toast.connect' musicstreamer/ui_qt/main_window.py &amp;&amp; ! grep -E 'clicked\.connect\(lambda' musicstreamer/ui_qt/now_playing_panel.py | grep -i 'gbs_vote' &amp;&amp; python -c "import ast; ast.parse(open('musicstreamer/ui_qt/now_playing_panel.py').read())"</automated>
  </verify>
  <done>
- 5 _gbs_vote_buttons (QPushButton, checkable, labels '1'..'5') in _gbs_vote_row
- Buttons hidden when not GBS or logged out (shared predicate with _gbs_playlist_widget)
- _GbsVoteWorker class with vote_finished + vote_error signals
- _on_gbs_vote_clicked uses sender().property('vote_value') (NOT a closure capture)
- _gbs_current_entryid sourced ONLY from _on_gbs_playlist_ready (Pitfall 1)
- _apply_vote_highlight + server-driven confirmation (Pitfall 2)
- gbs_vote_error_toast Signal + MainWindow connection
- Module parses cleanly; no QA-05 lambda violations
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add Phase 60 vote tests to tests/test_now_playing_panel.py</name>
  <read_first>
    - tests/test_now_playing_panel.py (Phase 60 active-playlist tests appended in 60-05; vote tests append after them)
    - musicstreamer/ui_qt/now_playing_panel.py (post-Task-1 state)
    - .planning/phases/60-gbs-fm-integration/60-PATTERNS.md (§"tests/ui_qt/test_now_playing_panel_gbs.py" — vote test list)
    - .planning/phases/60-gbs-fm-integration/60-VALIDATION.md (§"Per-Task Verification Map" GBS-01d rows)
  </read_first>
  <behavior>
    - test_gbs_vote_buttons_hidden_for_non_gbs (D-07): non-GBS station bound → all 5 buttons invisible
    - test_gbs_vote_buttons_hidden_when_logged_out (D-07 / D-04 ladder #3): GBS station, no cookies file → buttons invisible
    - test_gbs_vote_buttons_visible_when_gbs_and_logged_in: GBS + cookies → buttons visible
    - test_gbs_vote_optimistic_success: click button 3 with entryid set → optimistic highlight on '3' → emit vote_finished(token, 3, 0, "...") → button '3' remains highlighted
    - test_gbs_vote_optimistic_rollback_on_error: click button 3 → emit vote_error(token, prior_vote=0, "boom") → button '3' unchecked, no highlights, gbs_vote_error_toast emitted
    - test_gbs_vote_optimistic_rollback_on_auth_expired: emit vote_error(token, prior_vote=0, "auth_expired") → toast contains "session expired"
    - test_gbs_vote_entryid_only_from_ajax (Pitfall 1): _gbs_current_entryid starts None; ICY title change does NOT update it; only _on_gbs_playlist_ready does
    - test_gbs_vote_clicking_same_value_clears (RESEARCH §Capability 4): button '3' highlighted → click '3' → submit_value=0 sent
    - test_gbs_vote_stale_token_discarded: emit vote_finished with old token → button highlight unchanged
    - test_gbs_vote_no_entryid_ignores_click: _gbs_current_entryid is None → click button → no worker spawned
  </behavior>
  <action>
Append to `tests/test_now_playing_panel.py` AFTER the 60-05 active-playlist tests:

```python
# ===========================================================================
# Phase 60 / GBS-01d: vote control on NowPlayingPanel
# ===========================================================================

def _make_state(entryid: int = 1810736, user_vote: int = 0,
               icy_title: str = "Test Artist - Test Title"):
    """Folded /ajax state shape from gbs_api.fetch_active_playlist."""
    return {
        "now_playing_entryid": entryid,
        "now_playing_songid": 1,
        "icy_title": icy_title,
        "user_vote": user_vote,
        "score": "5.0 (1 vote)" if user_vote == 0 else f"{user_vote}.0 (1 vote)",
        "queue_html_snippets": [],
        "removed_ids": [],
    }


def test_gbs_vote_buttons_hidden_for_non_gbs(qtbot, fake_repo, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_panel(qtbot, fake_repo)
    panel.bind_station(_make_station(provider_name="DI.fm"))
    for btn in panel._gbs_vote_buttons:
        assert btn.isVisible() is False


def test_gbs_vote_buttons_hidden_when_logged_out(qtbot, fake_repo, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_panel(qtbot, fake_repo)
    panel.bind_station(_make_station())  # GBS but no cookies file
    for btn in panel._gbs_vote_buttons:
        assert btn.isVisible() is False


def test_gbs_vote_buttons_visible_when_gbs_and_logged_in(qtbot, fake_repo, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_panel(qtbot, fake_repo)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_station())
    for btn in panel._gbs_vote_buttons:
        assert btn.isVisible() is True
    assert len(panel._gbs_vote_buttons) == 5


def test_gbs_vote_optimistic_success(qtbot, fake_repo, tmp_path, monkeypatch):
    """Pitfall 2: server-returned user_vote is the FINAL highlighted state."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_panel(qtbot, fake_repo)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsVoteWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_station())
    # Stamp entryid via the playlist-ready hook (Pitfall 1)
    panel._gbs_poll_token = 1
    panel._on_gbs_playlist_ready(1, _make_state(entryid=999, user_vote=0))
    assert panel._gbs_current_entryid == 999
    # Simulate a click on button 3
    btn3 = panel._gbs_vote_buttons[2]  # vote_value=3
    btn3.click()
    # Optimistic: button 3 highlighted
    assert btn3.isChecked() is True
    assert panel._current_highlighted_vote() == 3
    # Worker emits server-confirmed user_vote=3
    panel._on_gbs_vote_finished(panel._gbs_vote_token, 3, 0, "4.0 (2 votes)")
    assert panel._current_highlighted_vote() == 3


def test_gbs_vote_optimistic_rollback_on_error(qtbot, fake_repo, tmp_path, monkeypatch):
    """Worker error → button reverts to prior_vote, toast emitted."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_panel(qtbot, fake_repo)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsVoteWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_station())
    panel._gbs_poll_token = 1
    panel._on_gbs_playlist_ready(1, _make_state(entryid=999, user_vote=0))
    captured_toasts = []
    panel.gbs_vote_error_toast.connect(captured_toasts.append)
    panel._gbs_vote_buttons[2].click()  # click button 3
    panel._on_gbs_vote_error(panel._gbs_vote_token, 0, "Connection refused")
    # Highlight reverts to prior_vote=0 (no button highlighted)
    assert panel._current_highlighted_vote() == 0
    assert any("Vote failed" in t and "Connection refused" in t for t in captured_toasts)


def test_gbs_vote_optimistic_rollback_on_auth_expired(qtbot, fake_repo, tmp_path, monkeypatch):
    """auth_expired path → 'session expired' toast + rollback."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_panel(qtbot, fake_repo)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsVoteWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_station())
    panel._gbs_poll_token = 1
    panel._on_gbs_playlist_ready(1, _make_state(entryid=999, user_vote=0))
    captured_toasts = []
    panel.gbs_vote_error_toast.connect(captured_toasts.append)
    panel._gbs_vote_buttons[2].click()
    panel._on_gbs_vote_error(panel._gbs_vote_token, 0, "auth_expired")
    assert panel._current_highlighted_vote() == 0
    assert any("session expired" in t.lower() and "Accounts" in t for t in captured_toasts)


def test_gbs_vote_entryid_only_from_ajax(qtbot, fake_repo, tmp_path, monkeypatch):
    """Pitfall 1: ICY title change does NOT update _gbs_current_entryid."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_panel(qtbot, fake_repo)
    assert panel._gbs_current_entryid is None
    # Simulate ICY title change (e.g. via on_title_changed if present)
    if hasattr(panel, "on_title_changed"):
        panel.on_title_changed("New Track - New Title")
    # _gbs_current_entryid still None
    assert panel._gbs_current_entryid is None
    # Now simulate /ajax response
    panel._gbs_poll_token = 1
    panel._on_gbs_playlist_ready(1, _make_state(entryid=12345))
    assert panel._gbs_current_entryid == 12345


def test_gbs_vote_clicking_same_value_clears(qtbot, fake_repo, tmp_path, monkeypatch):
    """RESEARCH §Capability 4: re-clicking the same vote value submits vote=0 (clear)."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_panel(qtbot, fake_repo)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    captured_worker_args = {}
    class FakeVoteWorker(MagicMock):
        def __init__(self, *args, **kwargs):
            captured_worker_args["kwargs"] = kwargs
            super().__init__()
        def start(self): pass
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsVoteWorker", FakeVoteWorker)
    panel.bind_station(_make_station())
    panel._gbs_poll_token = 1
    # Pre-set highlight to 3 via server-confirmed vote
    panel._on_gbs_playlist_ready(1, _make_state(entryid=999, user_vote=3))
    assert panel._current_highlighted_vote() == 3
    # Click button '3' again → should submit vote=0
    panel._gbs_vote_buttons[2].click()
    assert captured_worker_args["kwargs"]["vote_value"] == 0


def test_gbs_vote_stale_token_discarded(qtbot, fake_repo, tmp_path, monkeypatch):
    """Stale vote_finished from a stale token must NOT mutate the highlight."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    panel = _construct_panel(qtbot, fake_repo)
    panel._gbs_vote_token = 10
    panel._apply_vote_highlight(2)  # Set baseline highlight
    panel._on_gbs_vote_finished(3, 5, 0, "5.0 (1 vote)")  # stale token=3
    assert panel._current_highlighted_vote() == 2


def test_gbs_vote_no_entryid_ignores_click(qtbot, fake_repo, tmp_path, monkeypatch):
    """No entryid stamped → click is a no-op (no worker spawned)."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")
    panel = _construct_panel(qtbot, fake_repo)
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsPollWorker.start",
                        lambda self: None)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: MagicMock())
    panel.bind_station(_make_station())
    assert panel._gbs_current_entryid is None
    started = []
    monkeypatch.setattr("musicstreamer.ui_qt.now_playing_panel._GbsVoteWorker.start",
                        lambda self: started.append(True))
    panel._gbs_vote_buttons[2].click()
    assert started == []
```

Decisions implemented: VALIDATION.md GBS-01d rows; Pitfalls 1, 2, 7, 11.
  </action>
  <verify>
    <automated>pytest tests/test_now_playing_panel.py -x -q -k 'gbs_vote' 2>&amp;1 | tail -15 &amp;&amp; pytest tests/test_now_playing_panel.py -x -q 2>&amp;1 | tail -5</automated>
  </verify>
  <done>
- 10 new vote tests appended to tests/test_now_playing_panel.py
- All vote tests pass + all 60-05 active-playlist tests still pass
- Pitfall 1 (entryid only from /ajax) verified
- Pitfall 2 (server-truth) verified via test_gbs_vote_optimistic_success
- Rollback path verified for both generic and auth_expired errors
- Re-click-clears verified (vote=0 submitted on second click)
- Stale-token discard verified
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| UI thread (click) ↔ Worker thread (vote) | _GbsVoteWorker bridges click to gbs_api.vote_now_playing; results cross via Signal/Slot |
| /ajax response ↔ entryid stamping | _gbs_current_entryid is set ONLY by _on_gbs_playlist_ready (Pitfall 1) — never by ICY title |
| NowPlayingPanel ↔ MainWindow toast | gbs_vote_error_toast Signal forwards to show_toast; QA-05 bound connection |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-60-28 | Tampering | Vote-on-stale-track (ICY changed mid-vote) | mitigate | _gbs_current_entryid stamps ONLY from /ajax now_playing event; ICY title changes do NOT update it (Pitfall 1). Test test_gbs_vote_entryid_only_from_ajax locks this. |
| T-60-29 | Repudiation | Optimistic UI desync from server | mitigate | _on_gbs_vote_finished applies the SERVER-returned user_vote to the highlight, NOT the optimistic guess (Pitfall 2). Test test_gbs_vote_optimistic_success verifies. |
| T-60-30 | DoS / UX | Vote spam during spotty network → state corruption | mitigate | NO retries on transient failure (Pitfall 7) — error rolls back optimistic UI + toasts; user must re-click. _gbs_vote_token guards stale responses. |
| T-60-31 | Spoofing | Auth expiry mid-vote silently fails | mitigate | "auth_expired" sentinel string emits a "GBS.FM session expired — reconnect via Accounts" toast (Pitfall 3). Vote highlight rolls back. |
| T-60-32 | Information Disclosure | Self-capturing lambda in vote button connection | mitigate | All 5 buttons connect to `self._on_gbs_vote_clicked` via bound method; vote value carried via setProperty('vote_value', N) and read via self.sender().property() in the slot. QA-05 grep guard in verify command. |
| T-60-33 | Information Disclosure | Vote button label rendered with HTML injection | accept | Button labels are hard-coded "1".."5" — never user-controlled. PlainText defaults apply. |

Citations: Pitfalls 1, 2, 3, 7, 10, 11 from RESEARCH.md.
</threat_model>

<verification>
```bash
pytest tests/test_now_playing_panel.py -x -q
pytest tests/test_gbs_api.py -x -q   # regression
python -c "from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel, _GbsVoteWorker; print('OK')"
pytest -x  # full suite green
```
</verification>

<success_criteria>
- 5 vote buttons render in NowPlayingPanel when GBS+logged-in (hidden otherwise)
- Click → optimistic highlight → API round-trip → server-truth confirmation OR rollback
- Re-click same button submits vote=0 (clear)
- Stale-token guard active (concurrent clicks don't corrupt highlight)
- _gbs_current_entryid sourced only from /ajax (Pitfall 1)
- gbs_vote_error_toast Signal forwarded to MainWindow.show_toast
- 10 new pytest-qt tests pass; existing tests unaffected
- No QA-05 violations
- Full pytest -x runs green
</success_criteria>

<output>
After completion, create `.planning/phases/60-gbs-fm-integration/60-06-SUMMARY.md`
</output>
