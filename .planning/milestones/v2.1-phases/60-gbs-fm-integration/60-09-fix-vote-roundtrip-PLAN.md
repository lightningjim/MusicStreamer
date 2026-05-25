---
phase: 60-gbs-fm-integration
plan: 09
type: execute
wave: 5
depends_on: []
files_modified:
  - musicstreamer/ui_qt/now_playing_panel.py
  - tests/test_now_playing_panel.py
autonomous: true
gap_closure: true
requirements: [GBS-01d]
tags: [phase60, gap-closure, vote, optimistic-ui, ui-affordance, qa-05]
revision: 2
revision_notes: "Iteration-2 plan-check fixes: (1) added Step 2f to update existing test_gbs_vote_no_entryid_ignores_click so the in-handler guard remains tested via direct _on_gbs_vote_clicked() call (bypassing the new disabled-button gate), (2) pinned setEnabled(False) placement in constructor loop (immediately after btn.clicked.connect, before append). Wave/depends_on unchanged (no overlap with 60-08)."

must_haves:
  truths:
    - "Vote buttons are visually disabled (greyed out / setEnabled(False)) until _gbs_current_entryid is stamped from a successful /ajax poll"
    - "Vote buttons re-enable as soon as _gbs_current_entryid is set in _on_gbs_playlist_ready"
    - "Vote buttons re-disable when leaving GBS context (provider != GBS.FM, logged out, or auth disappears mid-session)"
    - "Clicking a vote button while the cookie file was deleted mid-session emits gbs_vote_error_toast (no longer silent)"
    - "The auth-disappeared toast text matches the existing auth-expired UX: 'GBS.FM session expired — reconnect via Accounts'"
    - "The in-handler entryid-None guard at _on_gbs_vote_clicked remains exercised by tests (via direct call, bypassing the disabled-button Qt gate)"
  artifacts:
    - path: "musicstreamer/ui_qt/now_playing_panel.py"
      provides: "Vote button enable/disable gate + cookies-None toast emission"
      contains: "_apply_vote_buttons_enabled"
    - path: "tests/test_now_playing_panel.py"
      provides: "3 new tests (disabled-before-entryid, re-enabled-after-ajax, toast-on-cookies-disappeared) + 1 updated test (in-handler guard via direct call)"
  key_links:
    - from: "_on_gbs_playlist_ready"
      to: "_apply_vote_buttons_enabled(True) when entryid stamped"
      via: "called after self._gbs_current_entryid is set"
      pattern: "_apply_vote_buttons_enabled"
    - from: "_on_gbs_vote_clicked"
      to: "gbs_vote_error_toast.emit before early-return on cookies is None"
      via: "auth-expired UX-matching message"
      pattern: 'gbs_vote_error_toast.emit\\("GBS.FM session expired'
---

<objective>
Close UAT issues T10 (vote click silently dropped — no server response, no UI feedback) and T11 (vote rollback toast never fires when network down or cookies removed mid-click). Diagnosis confirms both are guard-path bugs in `now_playing_panel.py`: the entryid-is-None guard silently drops valid clicks (T10 primary cause), and the cookies-is-None guard silently rolls back without toasting (T11 orthogonal component). The vote URL/method/CSRF in gbs_api.py is correct per RESEARCH and needs no changes.

Purpose: User can vote (the request actually reaches the server) AND knows when a click was dropped (no false-affordance silent button).

Output: Two defensive guards added to `now_playing_panel.py` — vote buttons disabled until entryid is stamped, and the cookies-None guard emits the existing `gbs_vote_error_toast` Signal before returning. 3 new pytest-qt tests in `tests/test_now_playing_panel.py`, plus 1 updated existing test (`test_gbs_vote_no_entryid_ignores_click`) so the in-handler entryid-None guard remains exercised after the disabled-button gate is added.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/60-gbs-fm-integration/60-CONTEXT.md
@.planning/phases/60-gbs-fm-integration/60-DIAGNOSIS-vote-roundtrip.md
@.planning/phases/60-gbs-fm-integration/60-UAT.md
@.planning/phases/60-gbs-fm-integration/60-06-vote-SUMMARY.md
@.planning/phases/60-gbs-fm-integration/60-05-active-playlist-SUMMARY.md
@./CLAUDE.md
@musicstreamer/ui_qt/now_playing_panel.py
@tests/test_now_playing_panel.py

<interfaces>
<!-- Existing now_playing_panel.py surface (current behavior to be patched) -->

```python
# musicstreamer/ui_qt/now_playing_panel.py — current shapes

class NowPlayingPanel(QWidget):
    gbs_vote_error_toast = Signal(str)   # already declared at line 200
    # already wired in main_window.py:296: self.now_playing.gbs_vote_error_toast.connect(self.show_toast)

    # Existing attributes (line ~410-435):
    _gbs_vote_buttons: list[QPushButton]   # 5 buttons, labels "1".."5", checkable
    _gbs_current_entryid: Optional[int]    # set ONLY by _on_gbs_playlist_ready
    _last_confirmed_vote: int               # server-confirmed vote tracking

    # Existing methods relevant to this fix:
    def _on_gbs_playlist_ready(self, token: int, state) -> None:
        # Sets self._gbs_current_entryid from /ajax response (line ~957-958).
        # Currently DOES NOT toggle vote button enabled state.

    def _refresh_gbs_visibility(self) -> None:
        # Shows/hides vote buttons based on provider + auth (lines 897-904).
        # Currently sets visibility but DOES NOT manage enabled state.

    def _on_gbs_vote_clicked(self) -> None:
        # Currently at line 1014-1069. Two early-return guards:
        #   line 1031: if sender is None or self._gbs_current_entryid is None: return  (T10 silent drop)
        #   line 1050: if cookies is None: rollback + refresh_visibility + return    (T11 silent rollback)
        # The cookies-None guard MUST emit gbs_vote_error_toast before returning.
```

```python
# Constructor pattern at lines 411-420 (final shape — pinned per iter-2 plan-check):
for v in range(1, 6):
    btn = QPushButton(str(v), self)
    btn.setCheckable(True)
    btn.setVisible(False)
    btn.setProperty("vote_value", v)
    btn.setMinimumWidth(32)
    btn.setMaximumWidth(48)
    btn.clicked.connect(self._on_gbs_vote_clicked)
    btn.setEnabled(False)  # 60-09 / T10: PINNED placement — AFTER connect, BEFORE append.
                            # Disabled state and signal-wiring are independent in Qt; placing
                            # setEnabled(False) after connect documents that the wiring is intact
                            # and the button is intentionally not yet usable.
    self._gbs_vote_row.addWidget(btn)
    self._gbs_vote_buttons.append(btn)
```
</interfaces>

<diagnoses_to_apply>
**T10 root cause (60-DIAGNOSIS-vote-roundtrip.md §2 Path A):** `_on_gbs_vote_clicked` returns silently when `_gbs_current_entryid is None`. This happens during the window between `bind_station` and the first successful `/ajax` poll response (up to ~15s). User sees clickable buttons (false affordance) but clicks do nothing. Fix per §5 Fix 1: disable the buttons until `_gbs_current_entryid` is stamped.

**T11 orthogonal component (60-DIAGNOSIS-vote-roundtrip.md §2 Path C):** When `cookies is None` at click time (cookie file removed mid-session), `_on_gbs_vote_clicked` at line 1050-1053 calls `_apply_vote_highlight(prior_vote)` + `_refresh_gbs_visibility()` + `return` — but does NOT emit `gbs_vote_error_toast`. Fix per §5 Fix 2: emit `gbs_vote_error_toast` with the existing auth-expired message before returning.

**No changes to vote_now_playing or gbs_api.py** — RESEARCH and the diagnosis confirmed the URL/method/CSRF are correct. T11 under "network down" resolves automatically once T10 unblocks worker spawning.

**Test-quality consideration (iter-1 plan-check WARNING):** The existing test `test_gbs_vote_no_entryid_ignores_click` (tests/test_now_playing_panel.py:1367) currently exercises the in-handler entryid-None guard by clicking a vote button when `_gbs_current_entryid is None`. After this plan's fix, the buttons will be DISABLED in that state — Qt blocks the `clicked` signal on disabled buttons, so the in-handler guard at line 1031 is never reached. The test still passes, but for the wrong reason (Qt-level block, not the in-handler guard). Step 2f below updates this test to bypass the disabled-button gate (call `_on_gbs_vote_clicked()` directly with a synthetic sender) so the in-handler guard remains exercised by the test suite. This is defensive — if a future refactor removes the disabled-button gate, the in-handler guard's coverage stays intact.
</diagnoses_to_apply>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1 (TDD-RED): Write 3 failing tests in tests/test_now_playing_panel.py</name>
  <files>tests/test_now_playing_panel.py</files>
  <behavior>
    - test_gbs_vote_buttons_disabled_until_entryid_stamped: Use the existing _construct_gbs_panel(qtbot) helper. Patch monkeypatch on `paths._root_override` and `gbs_api.load_auth_context` (return MagicMock for "logged in"). Bind a GBS.FM station. Call `_refresh_gbs_visibility()` to make buttons visible. Assert that `panel._gbs_vote_buttons[0].isEnabled() is False` for all 5 buttons (visible but disabled — not clickable). (Currently fails: buttons are enabled by default after setVisible(True).)
    - test_gbs_vote_buttons_enabled_after_first_ajax: Continuing from same setup, call `panel._on_gbs_playlist_ready(token, state)` with `state = {"now_playing_entryid": 1810809, "user_vote": 0, "score": "0", ...}` (use a token matching `panel._gbs_poll_token`). Assert `panel._gbs_vote_buttons[0].isEnabled() is True` for all 5 buttons. (Currently fails: enabled state is never managed by _on_gbs_playlist_ready.)
    - test_gbs_vote_emits_toast_when_cookies_disappear_mid_click: Use _construct_gbs_panel; bind GBS.FM station; stamp `panel._gbs_current_entryid = 1810809` directly (simulating successful poll); patch `gbs_api.load_auth_context` to return None on the click path; capture the `gbs_vote_error_toast` signal via qtbot.waitSignal. Click button "3" (call `panel._gbs_vote_buttons[2].click()` or invoke `_on_gbs_vote_clicked` after setting sender via setProperty). Assert qtbot.waitSignal fires with text containing "session expired". (Currently fails: signal is never emitted in the cookies-None branch.)

    Use the EXISTING test patterns at lines 1234-1380 of tests/test_now_playing_panel.py — same fixtures (qtbot, tmp_path, monkeypatch), same helpers (_construct_gbs_panel), same patching style for paths and gbs_api.load_auth_context.
  </behavior>
  <action>
    Append 3 new test functions to tests/test_now_playing_panel.py (after the last existing GBS test, near line 1380+).

    For test_gbs_vote_emits_toast_when_cookies_disappear_mid_click, the cleanest pattern is:
    ```python
    def test_gbs_vote_emits_toast_when_cookies_disappear_mid_click(qtbot, tmp_path, monkeypatch):
        from musicstreamer import paths, gbs_api
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        # Pre-create cookie file so _refresh_gbs_visibility shows buttons
        cookies_path = paths.gbs_cookies_path()
        os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
        with open(cookies_path, "w") as f:
            f.write("# Netscape HTTP Cookie File\n")
        panel = _construct_gbs_panel(qtbot)
        # Bind a GBS.FM station so visibility is on
        ...  # use existing pattern
        # Stamp entryid directly to simulate successful poll
        panel._gbs_current_entryid = 1810809
        panel._last_confirmed_vote = 0
        # Now simulate cookies disappearing
        monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: None)
        # Use waitSignal to capture
        with qtbot.waitSignal(panel.gbs_vote_error_toast, timeout=1000) as blocker:
            panel._gbs_vote_buttons[2].click()
        assert "session expired" in blocker.args[0].lower()
    ```

    Run pytest -x tests/test_now_playing_panel.py — confirm exactly 3 new tests fail. Commit RED:
    ```
    git add tests/test_now_playing_panel.py
    git commit -m "test(60-09): add failing tests for T10 (vote button enable gate) + T11 (cookies-None toast)"
    ```

    NOTE: this commit MUST be RED. If a test passes that the diagnosis says should fail, the test is wrong, not the production code.
  </action>
  <verify>
    <automated>cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/test_now_playing_panel.py -x -k "vote_buttons_disabled_until_entryid or vote_buttons_enabled_after_first_ajax or vote_emits_toast_when_cookies_disappear" 2>&1 | tail -20 | grep -v '^#' | grep -E 'FAILED|PASSED|test_gbs'</automated>
  </verify>
  <done>3 new tests fail with the expected assertion failure shapes (vote button isEnabled is True when it should be False / signal not emitted). RED commit recorded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2 (TDD-GREEN): Add _apply_vote_buttons_enabled helper + cookies-None toast emission + update test_gbs_vote_no_entryid_ignores_click</name>
  <files>musicstreamer/ui_qt/now_playing_panel.py, tests/test_now_playing_panel.py</files>
  <behavior>
    - Vote buttons constructed disabled (setEnabled(False) at construction time, immediately after btn.clicked.connect — pinned placement)
    - New method _apply_vote_buttons_enabled(enabled: bool) toggles enabled state across all 5 buttons
    - _refresh_gbs_visibility calls _apply_vote_buttons_enabled(False) on the hide path
    - _on_gbs_playlist_ready calls _apply_vote_buttons_enabled(True) AFTER stamping _gbs_current_entryid (in the same conditional block)
    - _on_gbs_vote_clicked emits gbs_vote_error_toast with "GBS.FM session expired — reconnect via Accounts" before the existing rollback path on cookies-None
    - Existing test_gbs_vote_no_entryid_ignores_click is updated to bypass the disabled-button Qt gate (calls panel._on_gbs_vote_clicked() directly with a synthetic sender) so the in-handler guard remains exercised
    - All 3 new tests pass; all 71 pre-existing now_playing_panel.py tests still pass (with test_gbs_vote_no_entryid_ignores_click updated, not removed); QA-05 grep guard still passes (no lambda self-capture in connect calls)
  </behavior>
  <action>
    **Step 2a: Construct buttons disabled — PINNED placement.** At lines 411-420 of `now_playing_panel.py`, add `btn.setEnabled(False)` to the construction loop. Place it **immediately after `btn.clicked.connect(self._on_gbs_vote_clicked)` and BEFORE `self._gbs_vote_row.addWidget(btn)`** (i.e. between connect and append). Final loop body:
    ```python
    for v in range(1, 6):
        btn = QPushButton(str(v), self)
        btn.setCheckable(True)
        btn.setVisible(False)
        btn.setProperty("vote_value", v)
        btn.setMinimumWidth(32)
        btn.setMaximumWidth(48)
        btn.clicked.connect(self._on_gbs_vote_clicked)
        btn.setEnabled(False)  # 60-09 / T10: disabled until /ajax stamps entryid (after connect — wiring intact, button intentionally not yet usable)
        self._gbs_vote_row.addWidget(btn)
        self._gbs_vote_buttons.append(btn)
    ```
    Buttons start hidden AND disabled — they only become enabled after `_on_gbs_playlist_ready` stamps an entryid. The placement (after connect, before append) is functionally equivalent to other orderings (Qt's `setEnabled` and signal-wiring are independent attributes), but pinning the placement removes future ambiguity for anyone editing this loop.

    **Step 2b: Add `_apply_vote_buttons_enabled(self, enabled: bool)` helper.** Place it next to `_apply_vote_highlight` at line 995. Single-purpose:
    ```python
    def _apply_vote_buttons_enabled(self, enabled: bool) -> None:
        """Phase 60 60-09 / T10: gate vote-button affordance behind entryid stamp.

        Disabled when no entryid is known (no successful /ajax poll yet) or
        when leaving GBS context entirely. Enabled once /ajax confirms the
        current playing entryid.
        """
        for btn in self._gbs_vote_buttons:
            btn.setEnabled(bool(enabled))
    ```

    **Step 2c: Wire enable in `_on_gbs_playlist_ready`.** At line 957-958 (where `_gbs_current_entryid` is set), add:
    ```python
    if new_entryid is not None:
        new_entryid_int = int(new_entryid)
        if new_entryid_int != self._gbs_current_entryid:
            self._gbs_current_entryid = new_entryid_int
        self._apply_vote_buttons_enabled(True)  # 60-09 / T10: entryid known, buttons usable
    ```
    The `_apply_vote_buttons_enabled(True)` call goes INSIDE the `if new_entryid is not None:` block (so we only enable when we actually have an entryid).

    **Step 2d: Wire disable in `_refresh_gbs_visibility`.** At line 900-904 (the `if not should_show:` branch), add `self._apply_vote_buttons_enabled(False)` so leaving GBS context (or losing auth) re-disables the buttons. The existing `self._gbs_current_entryid = None` reset stays.

    **Step 2e: Emit toast on cookies-None at click time.** At line 1050-1054 of `_on_gbs_vote_clicked`:
    ```python
    cookies = gbs_api.load_auth_context()
    if cookies is None:
        # 60-09 / T11: surface the silent auth-disappeared rollback as a toast
        # so the user knows why the optimistic highlight reverted.
        self.gbs_vote_error_toast.emit("GBS.FM session expired — reconnect via Accounts")
        # Auth disappeared — rollback + refresh visibility
        self._apply_vote_highlight(prior_vote)
        self._refresh_gbs_visibility()
        return
    ```
    The toast message must match exactly the auth-expired message used by `_on_gbs_vote_error` at line 1090 ("GBS.FM session expired — reconnect via Accounts") so the user UX is consistent across all auth-disappeared paths.

    **Step 2f: Update existing `test_gbs_vote_no_entryid_ignores_click` (tests/test_now_playing_panel.py:1367) to bypass the disabled-button Qt gate.**

    *Why:* After Step 2a, vote buttons are DISABLED when `_gbs_current_entryid is None`. Qt blocks the `clicked` signal on disabled buttons, so the in-handler guard at `_on_gbs_vote_clicked` line 1031 (`if sender is None or self._gbs_current_entryid is None: return`) is never reached when the test does `panel._gbs_vote_buttons[2].click()`. The test still passes — but for the wrong reason (Qt-level block, not in-handler guard). The original test's semantic intent (proving the in-handler guard catches None) becomes meaningless.

    *Resolution chosen (per iter-2 plan-check directive):* "Update `test_gbs_vote_no_entryid_ignores_click` to bypass the disabled-button gate (call `panel._on_gbs_vote_clicked()` directly) so the in-handler guard remains tested." (The alternative — delete the test as superseded — is rejected because the in-handler guard is still real defensive code worth covering; if a future refactor removes the disabled-button gate, this test must still catch the regression.)

    *Concrete edit:* in tests/test_now_playing_panel.py at the body of `test_gbs_vote_no_entryid_ignores_click` (currently line ~1367-1395), replace the `panel._gbs_vote_buttons[2].click()` line with a direct call to `_on_gbs_vote_clicked()` that supplies a synthetic sender (so the `sender is None` early-return doesn't fire — we want the test to specifically exercise the `_gbs_current_entryid is None` branch):

    ```python
    def test_gbs_vote_no_entryid_ignores_click(qtbot, tmp_path, monkeypatch):
        """In-handler entryid-None guard returns silently with no worker started.

        60-09 / T10: after this plan, the vote buttons are also DISABLED at the
        Qt level when entryid is None. This test bypasses the Qt gate via a
        direct _on_gbs_vote_clicked call so the IN-HANDLER guard at line 1031
        remains exercised — defense-in-depth coverage.
        """
        # ...existing setup (paths, _construct_gbs_panel, bind station)...
        panel = _construct_gbs_panel(qtbot)
        # ...bind GBS.FM station per existing pattern...
        # Confirm precondition: entryid is None (no /ajax poll has stamped it yet)
        assert panel._gbs_current_entryid is None
        # Bypass the disabled-button Qt gate by calling the handler directly with
        # a synthetic sender. This proves the IN-HANDLER guard catches the None
        # case independently of the Qt-level disabled-button block.
        # The handler reads `self.sender()` for the button reference; we
        # simulate by invoking the handler with the button's vote_value already
        # accessible via the signal-emit machinery. The simplest faithful
        # bypass is to manually emit `clicked` from a temporarily-enabled button:
        panel._gbs_vote_buttons[2].setEnabled(True)  # bypass Qt gate
        # Spy on _spawn_vote_worker (existing pattern from other tests)
        spawn_calls: list = []
        monkeypatch.setattr(panel, "_spawn_vote_worker", lambda *a, **kw: spawn_calls.append((a, kw)))
        panel._gbs_vote_buttons[2].click()  # now reaches handler; in-handler guard catches None
        assert spawn_calls == [], "in-handler guard must drop click when _gbs_current_entryid is None"
    ```

    Note: the exact mechanism for "supply a synthetic sender" depends on how the existing test currently exercises the click. If the existing test already uses `_spawn_vote_worker` interception (or `gbs_api.vote_now_playing` interception), keep that interception; only the `setEnabled(True)` bypass + the comment are added.

    Run pytest -x tests/test_now_playing_panel.py — all 71 pre-existing tests + 3 new tests pass (test_gbs_vote_no_entryid_ignores_click is now updated, not regressed).

    Commit GREEN:
    ```
    git add musicstreamer/ui_qt/now_playing_panel.py tests/test_now_playing_panel.py
    git commit -m "fix(60-09): disable vote buttons until /ajax stamps entryid + toast on cookies-disappeared (T10 + T11)

    T10: buttons start disabled at construction, enabled by _on_gbs_playlist_ready
    once _gbs_current_entryid is known, re-disabled when leaving GBS context.
    Removes false affordance during the bind→first-poll window. setEnabled(False)
    placed AFTER btn.clicked.connect (PINNED placement — wiring intact, button
    intentionally not yet usable).

    T11: cookies-None guard at click time now emits gbs_vote_error_toast with
    the existing auth-expired message before rolling back. Matches the toast
    UX surfaced by _on_gbs_vote_error.

    Test update: test_gbs_vote_no_entryid_ignores_click now bypasses the new
    disabled-button Qt gate via setEnabled(True) before the click, so the
    in-handler entryid-None guard remains exercised (defense-in-depth).

    Refs: .planning/phases/60-gbs-fm-integration/60-DIAGNOSIS-vote-roundtrip.md"
    ```
  </action>
  <verify>
    <automated>cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/test_now_playing_panel.py 2>&1 | tail -10 | grep -v '^#' | grep -E 'passed|failed' && grep -v '^#' musicstreamer/ui_qt/now_playing_panel.py | grep -c '_apply_vote_buttons_enabled'</automated>
  </verify>
  <done>All 74 tests pass (71 pre-existing — including updated test_gbs_vote_no_entryid_ignores_click — + 3 new). _apply_vote_buttons_enabled appears at least 3 times in source (definition + 2 call sites). GREEN commit recorded.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| UI thread → Qt event queue | Vote button clicked signal fires synchronously |
| Qt button enable state → user expectation | Disabled = "you cannot click this yet" |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-60-09-01 | Repudiation | User claims they voted but no server-side change | mitigate | Disabled-until-entryid removes the false affordance — clicks during the load window are visibly impossible (button greyed) instead of silently dropped. |
| T-60-09-02 | Information Disclosure | Toast message text reveals auth state | accept | Single-user app per project memory; no multi-tenant concern. Message reuses the existing auth-expired phrasing in _on_gbs_vote_error. |
| T-60-09-03 | DoS | User mashes vote button rapidly | mitigate | Existing _gbs_vote_token monotonic counter (Plan 60-06) discards stale callbacks; no new attack surface. |
| T-60-09-04 | Tampering | _apply_vote_buttons_enabled called from worker thread | mitigate | Both call sites (_on_gbs_playlist_ready, _refresh_gbs_visibility) execute on the UI thread per existing Qt signal-routing in Plans 60-05/06; no new threading boundary. |
</threat_model>

<verification>
- pytest tests/test_now_playing_panel.py shows 74 tests pass.
- pytest tests/test_gbs_api.py still shows all tests pass (no cross-file regression).
- grep -v '^#' musicstreamer/ui_qt/now_playing_panel.py | grep -c '_apply_vote_buttons_enabled' >= 3 (definition + 2 call sites).
- grep -v '^#' musicstreamer/ui_qt/now_playing_panel.py | grep -c 'gbs_vote_error_toast.emit' >= 3 (existing auth-expired path + new cookies-None path + existing generic-error path).
- grep -E 'btn.clicked.connect\\(lambda' musicstreamer/ui_qt/now_playing_panel.py is empty (QA-05 compliance).
- Manual reproduction (run app, switch to GBS.FM station, observe buttons appear visible but greyed for ~1s before /ajax response, then enable). Click during disabled window: nothing happens but no false affordance.
- Manual reproduction (run app, switch to GBS.FM, wait for poll, then `rm ~/.local/share/musicstreamer/gbs-cookies.txt`, click vote): toast says "GBS.FM session expired — reconnect via Accounts".
</verification>

<success_criteria>
- T10 closed: vote buttons are visibly disabled until first /ajax response stamps entryid; clicks during the disabled window are physically blocked (no silent drop).
- T11 closed: deleting cookies mid-session and clicking a vote button surfaces the toast.
- All 74 tests in tests/test_now_playing_panel.py pass — broken down as: 70 pre-existing untouched + 1 pre-existing UPDATED (`test_gbs_vote_no_entryid_ignores_click`, now bypasses Qt-level disabled-button gate via setEnabled(True) so the in-handler guard remains tested) + 3 new (Task 1).
- 18 tests in tests/test_gbs_api.py + 16 tests in tests/test_gbs_search_dialog.py + 46 tests in tests/test_main_window_integration.py still pass.
- Two atomic commits: 1 RED (failing tests), 1 GREEN (paired enable-gate + toast emission + test_gbs_vote_no_entryid_ignores_click update — they share the diagnosis cluster and ship together).
</success_criteria>

<output>
After completion, create `.planning/phases/60-gbs-fm-integration/60-09-fix-vote-roundtrip-SUMMARY.md` per the standard summary template, including:
- Frontmatter: requires=[60-05, 60-06], provides=["vote button enable gate", "cookies-None toast emission"], requirements-completed=[GBS-01d]
- Sections: Performance / Accomplishments / Task Commits / Files Modified / Decisions Made / TDD Gate Compliance / Deviations / Threat Flags / Self-Check
- Note in Deviations section: test_gbs_vote_no_entryid_ignores_click updated to bypass the new disabled-button Qt gate so the in-handler guard remains exercised (defense-in-depth, per revision-2 of this plan).
</output>
