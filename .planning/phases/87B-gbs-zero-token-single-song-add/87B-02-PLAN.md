---
phase: 87B-gbs-zero-token-single-song-add
plan: 02
type: execute
wave: 2
depends_on:
  - 87B-01
files_modified:
  - musicstreamer/ui_qt/now_playing_panel.py
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/ui_qt/gbs_search_dialog.py
  - tests/test_now_playing_panel.py
  - tests/test_main_window_gbs.py
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
  - .planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md
autonomous: true
requirements:
  - GBS-TOKEN-01
  - GBS-TOKEN-03
  - GBS-TOKEN-04

user_setup: []

must_haves:
  truths:
    - "D-04: persistent 'Add a song' QPushButton placed after _gbs_expiry_widget and before _gbs_vote_row in the now_playing_panel GBS cluster"
    - "D-05: button visibility uses should_show = is_gbs and logged_in — NOT gated on token count or queue state (any token count shows it)"
    - "D-06: button label is exactly 'Add a song'; tooltip is exactly 'Add a song to the GBS.FM queue'; neither contains the affordance-economics word"
    - "D-07: server is truth — no local pre-gating; the /add rejection text surfaces verbatim via the existing GBSSearchDialog inline path"
    - "D-08: GBS-TOKEN-04 is obsolete — the button persists after add (no hide); post-add behavior is dialog-close + playlist re-poll"
    - "D-09: after a successful add, GBSSearchDialog.submission_completed → panel.trigger_gbs_repoll() resets _gbs_poll_cursor and calls _on_gbs_poll_tick()"
    - "D-10: the button reuses the existing _open_gbs_search_dialog() launch path and GBSSearchDialog as-is — no new dialog"
    - "GBS-TOKEN-01: 'Add a song' affordance is visible whenever the bound station is GBS.FM and logged in (amended from tokens==0+queue==0)"
    - "GBS-TOKEN-03: the dialog's submit worker calls gbs_api.add_song_zero_token() so the capture hook fires on every GBS add"
  artifacts:
    - path: "musicstreamer/ui_qt/now_playing_panel.py"
      provides: "_gbs_add_btn widget, _on_add_song_clicked slot, add_song_requested signal, trigger_gbs_repoll() public method, visibility wiring"
      contains: "Add a song"
    - path: "musicstreamer/ui_qt/main_window.py"
      provides: "submission_completed → trigger_gbs_repoll wiring + add_song_requested → _open_gbs_search_dialog wiring"
      contains: "trigger_gbs_repoll"
    - path: ".planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md"
      provides: "Follow-up todo to confirm the provisional contract on first live tokens==0 add"
      contains: "resolves_phase: 87B"
  key_links:
    - from: "musicstreamer/ui_qt/now_playing_panel.py::_gbs_add_btn"
      to: "musicstreamer/ui_qt/main_window.py::_open_gbs_search_dialog"
      via: "add_song_requested signal connected in main_window"
      pattern: "add_song_requested"
    - from: "musicstreamer/ui_qt/gbs_search_dialog.py::submission_completed"
      to: "musicstreamer/ui_qt/now_playing_panel.py::trigger_gbs_repoll"
      via: "connect() in _open_gbs_search_dialog"
      pattern: "submission_completed\\.connect"
    - from: "musicstreamer/ui_qt/gbs_search_dialog.py::_GbsSubmitWorker.run"
      to: "musicstreamer/gbs_api.py::add_song_zero_token"
      via: "call-site change from submit() to add_song_zero_token()"
      pattern: "add_song_zero_token"
---

<objective>
Add the persistent "Add a song" QPushButton to the now-playing GBS widget cluster (visible whenever GBS.FM is bound + logged in, any token count), wire its click to the existing GBSSearchDialog launch path, wire the dialog's `submission_completed` to a new `trigger_gbs_repoll()` panel method, route the dialog's submit worker through `add_song_zero_token()` (so the capture hook fires), amend the stale planning docs to match the session reframe, and emit the capture-on-use follow-up todo.

Purpose: Deliver GBS-TOKEN-01 (always-visible affordance — amended per D-05), GBS-TOKEN-03 (opens existing dialog + named add path), and the GBS-TOKEN-04 obsolescence (button persists; post-add = dialog-close + re-poll, per D-08/D-09). Server remains truth (D-07).
Output: button + visibility + re-poll wiring in `now_playing_panel.py`; dialog/signal wiring in `main_window.py`; worker call-site change in `gbs_search_dialog.py`; amended `REQUIREMENTS.md` + `ROADMAP.md`; follow-up todo; new UI tests.
</objective>

<execution_context>
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.5.0/workflows/execute-plan.md
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.5.0/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/87B-gbs-zero-token-single-song-add/87B-CONTEXT.md
@.planning/phases/87B-gbs-zero-token-single-song-add/87B-RESEARCH.md
@.planning/phases/87B-gbs-zero-token-single-song-add/87B-PATTERNS.md
@.planning/phases/87B-gbs-zero-token-single-song-add/87B-UI-SPEC.md
@.planning/phases/87B-gbs-zero-token-single-song-add/87B-01-SUMMARY.md

<interfaces>
<!-- Extracted from codebase. Use directly — no exploration. -->

From musicstreamer/ui_qt/now_playing_panel.py:
- center column QVBoxLayout: _gbs_playlist_widget (~695) -> _gbs_expiry_widget (~722) -> [INSERT _gbs_add_btn] -> _gbs_vote_row (~767)
- _gbs_relogin_btn = QPushButton("Log in again", self._gbs_expiry_widget) (~717) — construction analog
- self._gbs_poll_cursor: dict = {} (746) ; self._gbs_vote_buttons: list (754)
- def _is_gbs_logged_in(self) -> bool (2957)
- def _refresh_gbs_visibility(self) (2962): builds is_gbs = station.provider_name == "GBS.FM", logged_in = _is_gbs_logged_in(), should_show = is_gbs and logged_in; sets _gbs_playlist_widget.setVisible(should_show) and loops for btn in self._gbs_vote_buttons: btn.setVisible(should_show)
- def _gbs_poll_in_flight(self) -> bool (3015)
- def _on_gbs_poll_tick(self) -> None (3032) — the re-poll engine (already called from _refresh_gbs_visibility, on_title_changed, _on_gbs_relogin_succeeded)

From musicstreamer/ui_qt/main_window.py:
- def _open_gbs_search_dialog(self) -> None (1542): dlg = GBSSearchDialog(self._repo, self.show_toast, parent=self); dlg.exec() — docstring currently states "submission_completed is not connected here"
- panel reference attribute used elsewhere as self._now_playing_panel

From musicstreamer/ui_qt/gbs_search_dialog.py:
- submission_completed = Signal() (274) — emits at 1093 on successful _on_submit_finished
- _GbsSubmitWorker.run() (139): msg = gbs_api.submit(self._songid, self._cookies) — the call-site to change to add_song_zero_token
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: "Add a song" button + visibility + trigger_gbs_repoll() in now_playing_panel.py</name>
  <files>musicstreamer/ui_qt/now_playing_panel.py, tests/test_now_playing_panel.py</files>
  <read_first>
    - musicstreamer/ui_qt/now_playing_panel.py lines 689-767 (GBS cluster layout, _gbs_relogin_btn construction at 717-722, _gbs_vote_row at 748-767)
    - musicstreamer/ui_qt/now_playing_panel.py lines 2957-3013 (_is_gbs_logged_in, _refresh_gbs_visibility, _gbs_poll_in_flight) and 3032 (_on_gbs_poll_tick) and 3181-3194 (_on_gbs_relogin_succeeded direct-call analog)
    - 87B-UI-SPEC.md section "Widget Placement Contract" + "Visibility and State Matrix" (exact label/tooltip/no-stylesheet/no-width rules)
    - 87B-PATTERNS.md now_playing_panel.py section (Analog A/B/C)
  </read_first>
  <behavior>
    - test_add_song_visibility: when station.provider_name == "GBS.FM" and _is_gbs_logged_in() is True -> _gbs_add_btn visible is True; when station is non-GBS OR not logged in -> False. Visibility does NOT call fetch_user_tokens and is independent of token count / queue state (D-05).
    - test_add_song_button_label: _gbs_add_btn.text() == "Add a song" and _gbs_add_btn.toolTip() == "Add a song to the GBS.FM queue".
    - test_repoll: trigger_gbs_repoll() on a GBS-bound idle panel resets _gbs_poll_cursor to {} and invokes _on_gbs_poll_tick(); on a non-GBS panel or in-flight poll it is a no-op.
  </behavior>
  <action>
    In __init__, immediately AFTER center.addWidget(self._gbs_expiry_widget) (~line 722) and BEFORE self._gbs_vote_row = QHBoxLayout() (~line 748), construct self._gbs_add_btn = QPushButton("Add a song", self); self._gbs_add_btn.setToolTip("Add a song to the GBS.FM queue"); self._gbs_add_btn.setVisible(False); self._gbs_add_btn.clicked.connect(self._on_add_song_clicked) with a QA-05 bound-method comment; center.addWidget(self._gbs_add_btn). Order is load-bearing (Pitfall 3 — must precede the vote row). Do NOT set a stylesheet, custom color, flat style, or min/max width (87B-UI-SPEC Color / No sizing overrides). The label and tooltip strings are exact and MUST NOT contain the affordance-economics word (D-06 / GBS-TOKEN-02). Declare a class-level signal add_song_requested = Signal() (mirror the submission_completed declaration style). Add slot def _on_add_song_clicked(self) -> None that emits self.add_song_requested (Option A from RESEARCH Pattern 2 — keeps the panel from importing GBSSearchDialog; main_window owns the dialog). In _refresh_gbs_visibility(), add self._gbs_add_btn.setVisible(should_show) alongside the existing _gbs_vote_buttons visibility loop, using the same should_show = is_gbs and logged_in predicate (D-05). Add public method def trigger_gbs_repoll(self) -> None: guard if self._station is not None and self._station.provider_name == "GBS.FM" and not self._gbs_poll_in_flight(): then self._gbs_poll_cursor = {} (force full re-fetch so the new song appears — Pitfall 5) then self._on_gbs_poll_tick(). Write all docstrings without the affordance-economics word.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_now_playing_panel.py -k "add_song or repoll" -x 2>&1 | tail -8; .venv/bin/python -m pytest tests/test_gbs_zero_token_drift_guard.py -x 2>&1 | tail -3</automated>
  </verify>
  <acceptance_criteria>
    - now_playing_panel.py contains the literal "Add a song" and "Add a song to the GBS.FM queue".
    - _gbs_add_btn is constructed after _gbs_expiry_widget and before _gbs_vote_row (grep line order).
    - now_playing_panel.py defines add_song_requested, def _on_add_song_clicked, and def trigger_gbs_repoll.
    - No fetch_user_tokens call appears in the button-visibility path (D-05; Pitfall 2).
    - .venv/bin/python -m pytest tests/test_now_playing_panel.py -k "add_song or repoll" -x exits 0.
    - The Plan-01 drift-guard still passes.
  </acceptance_criteria>
  <done>Persistent "Add a song" button (exact label + tooltip) renders when GBS.FM bound + logged in; emits add_song_requested on click; trigger_gbs_repoll() resets the cursor and re-polls; visibility is token-count-independent (D-04/D-05/D-06/D-09).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wire dialog launch + re-poll in main_window.py; route worker through add_song_zero_token()</name>
  <files>musicstreamer/ui_qt/main_window.py, musicstreamer/ui_qt/gbs_search_dialog.py, tests/test_main_window_gbs.py</files>
  <read_first>
    - musicstreamer/ui_qt/main_window.py lines 1542-1552 (_open_gbs_search_dialog) and the method where the panel is constructed/referenced (search self._now_playing_panel)
    - musicstreamer/ui_qt/gbs_search_dialog.py lines 116-145 (_GbsSubmitWorker.run, the submit() call-site at ~139) and lines 274, 1093 (submission_completed declaration + emit)
    - tests/test_main_window_gbs.py (existing GBS wiring tests — extend)
    - 87B-PATTERNS.md main_window.py + gbs_search_dialog.py + "Shared Patterns"; 87B-RESEARCH.md Open Question 1 (recommends changing the worker call-site)
  </read_first>
  <behavior>
    - test_submission_completed_wired_to_repoll: opening the GBS search dialog connects dlg.submission_completed to self._now_playing_panel.trigger_gbs_repoll (assert the connection exists / a stub trigger_gbs_repoll is invoked when the signal is emitted).
    - test_add_song_requested_opens_dialog: emitting the panel's add_song_requested invokes _open_gbs_search_dialog.
    - The submit worker calls gbs_api.add_song_zero_token(...) (not bare submit) so the capture hook fires on every GBS add (GBS-TOKEN-03).
  </behavior>
  <action>
    In main_window._open_gbs_search_dialog(), after constructing dlg = GBSSearchDialog(...) and BEFORE dlg.exec(), add dlg.submission_completed.connect(self._now_playing_panel.trigger_gbs_repoll) with a QA-05 bound-method comment (D-09). Update the method docstring to remove the stale "submission_completed is not connected here" line and note it now drives the post-add GBS re-poll (D-08/D-09). In the method that sets up the panel (where self._now_playing_panel is created/owned), connect self._now_playing_panel.add_song_requested.connect(self._open_gbs_search_dialog) with a QA-05 comment (D-10 — reuse the existing launch path; no new dialog). In gbs_search_dialog.py::_GbsSubmitWorker.run(), change the call gbs_api.submit(self._songid, self._cookies) to gbs_api.add_song_zero_token(self._songid, self._cookies) (RESEARCH Open Question 1 recommendation — makes the wrapper the live path so the capture hook always fires; GbsAuthExpiredError still propagates through the existing except block unchanged). Do NOT add any local token pre-gating anywhere (D-07 — server is truth); the dialog's existing inline messages-cookie display already surfaces server rejections verbatim. Extend tests/test_main_window_gbs.py with test_submission_completed_wired_to_repoll and test_add_song_requested_opens_dialog per the behavior block (use a stub/mock panel exposing trigger_gbs_repoll; assert the wiring fires). Run with .venv/bin/python.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_main_window_gbs.py -k "repoll or add_song or submission" -x 2>&1 | tail -8</automated>
  </verify>
  <acceptance_criteria>
    - main_window.py contains submission_completed.connect targeting trigger_gbs_repoll and add_song_requested.connect targeting _open_gbs_search_dialog.
    - The "submission_completed is not connected here" docstring line is gone from _open_gbs_search_dialog.
    - grep -n "add_song_zero_token" musicstreamer/ui_qt/gbs_search_dialog.py shows the worker now calls the wrapper; no bare gbs_api.submit( remains in _GbsSubmitWorker.run.
    - No new fetch_user_tokens / token pre-gating in the add path (D-07).
    - .venv/bin/python -m pytest tests/test_main_window_gbs.py -k "repoll or add_song or submission" -x exits 0.
  </acceptance_criteria>
  <done>Button click opens the existing GBSSearchDialog; a successful add re-polls the playlist via trigger_gbs_repoll(); the submit worker routes through add_song_zero_token() so the capture hook fires; no client-side gating (GBS-TOKEN-03 / D-07/D-08/D-09/D-10).</done>
</task>

<task type="auto">
  <name>Task 3: Amend stale planning docs + emit capture-on-use follow-up todo</name>
  <files>.planning/REQUIREMENTS.md, .planning/ROADMAP.md, .planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md</files>
  <read_first>
    - .planning/REQUIREMENTS.md GBS-TOKEN section (GBS-TOKEN-01..05, lines ~67-73)
    - .planning/ROADMAP.md line 45 (one-line phase entry) and lines 425-440 (Phase 87b block: Goal + Success Criteria SC#1..#5)
    - .planning/phases/87B-gbs-zero-token-single-song-add/87B-CONTEXT.md canonical_refs (the exact amendment instructions) + D-03/D-05/D-08
    - an existing todo file under .planning/todos/pending/ for the front-matter shape
  </read_first>
  <action>
    Amend .planning/REQUIREMENTS.md GBS-TOKEN block (leave GBS-TOKEN-02 and GBS-TOKEN-03 intact). Rewrite GBS-TOKEN-01 to: "When the bound station is GBS.FM AND the user is logged in, the now-playing panel renders a persistent 'Add a song' affordance regardless of token count or queue state (AMENDED per 87B-CONTEXT D-05 — supersedes the original tokens==0 AND queue==0 gating)." Rewrite GBS-TOKEN-04 to: "The 'Add a song' button persists (no hide-after-add); after a successful add the dialog closes and the now-playing GBS playlist widget re-polls (AMENDED per 87B-CONTEXT D-08 — supersedes the original hide/re-appear behavior)." Rewrite GBS-TOKEN-05 to: "The observable /add request/response shape is fixture-locked now under tests/fixtures/gbs_zero_token/; the real tokens==0 payload is captured on first live use via the no-PII capture hook (RELAXED per 87B-CONTEXT D-03 — the original 'live tokens==0 POST observed via spike' is deferred to capture-on-use)." Amend .planning/ROADMAP.md: update the line-45 one-liner to drop the "gated on tokens==0 AND queue empty" framing (persistent button; UX never frames as a token grant). In the Phase 87b Success Criteria block, rewrite SC#1 (visible when GBS.FM bound + logged in, any token count — D-05), SC#3 (named add path posts to the provisional /add reuse, not a separately-observed one-shot endpoint — D-02), SC#4 (button persists; post-add = dialog-close + re-poll — D-08), and SC#5 (provisional fixture now + capture-on-first-use — D-03). Leave SC#2 intact. Create .planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md mirroring an existing pending-todo's front-matter, with resolves_phase: 87B, a clear condition ("first observed tokens==0 add — the no-PII capture hook records the real request/response"), and the action: confirm/adjust the provisional /add contract and replace the add_redirect_zero_token_PLACEHOLDER.txt fixture with the captured payload (quote-don't-paraphrase per feedback_mirror_decisions_cite_source.md). This is a docs/config task — no production code changes.
  </action>
  <verify>
    <automated>grep -q "AMENDED per 87B-CONTEXT D-05" .planning/REQUIREMENTS.md && grep -q "AMENDED per 87B-CONTEXT D-08" .planning/REQUIREMENTS.md && grep -q "RELAXED per 87B-CONTEXT D-03" .planning/REQUIREMENTS.md && grep -q "resolves_phase: 87B" .planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md && echo DOCS_OK</automated>
  </verify>
  <acceptance_criteria>
    - GBS-TOKEN-01/04/05 in REQUIREMENTS.md carry the AMENDED/RELAXED citations to D-05/D-08/D-03; GBS-TOKEN-02/03 unchanged.
    - ROADMAP.md line 45 no longer frames the phase as tokens==0+queue-gated; SC#1/#3/#4/#5 are rewritten per the reframe; SC#2 intact.
    - .planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md exists with resolves_phase: 87B and the capture-on-use condition.
    - Verify command prints DOCS_OK.
  </acceptance_criteria>
  <done>Planning docs match the session reframe (GBS-TOKEN-01/04/05 + ROADMAP SC#1/#3/#4/#5 amended per D-03/D-05/D-08); the capture-on-use follow-up todo is filed.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| User click (panel) → GBSSearchDialog → gbs.fm /add | User-initiated add crosses into the authenticated GBS request path (reused, unchanged HTTP). |
| gbs.fm server → GBSSearchDialog inline display | Server messages-cookie text is rendered to the user verbatim (server is truth, D-07). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-87B-01 | Information Disclosure | capture hook (fires via add_song_zero_token in the worker) | mitigate | The hook itself is implemented + PII-tested in Plan 01 (T-87B-01 gated HIGH there). This plan only routes the worker through add_song_zero_token(); it adds no new logging. No PII surface introduced here. |
| T-87B-04 | Tampering / Injection | server messages-cookie text rendered in the dialog | accept | Existing GBSSearchDialog renders this via Qt.TextFormat.PlainText (convention T-40-04); no HTML interpretation. Reused as-is (D-10), no new render surface. |
| T-87B-05 | Spoofing | double-submit (fast double-click "Add a song") | accept | dlg.exec() is modal — the panel button cannot re-fire while the dialog is open; the dialog already disables its own submit button in-flight (87B-UI-SPEC In-flight state). No new debounce needed. |
| T-87B-03 | Repudiation | auth-expiry from the add path | accept | GbsAuthExpiredError propagates through add_song_zero_token() to the existing dialog _on_submit_error("auth_expired") path (toast + login-gate refresh). Unchanged surface (RESEARCH Open Question 3 — leave as-is). |
| T-87B-SC | Tampering | npm/pip/cargo installs | accept | No package installs in this plan (pure Qt wiring + existing imports). N/A. |
</threat_model>

<verification>
- .venv/bin/python -m pytest tests/test_now_playing_panel.py -k "add_song or repoll" tests/test_main_window_gbs.py -k "repoll or add_song or submission" tests/test_gbs_zero_token_drift_guard.py -x is green.
- Button visible only when GBS.FM bound + logged in (token-count-independent); click opens the existing dialog; successful add re-polls; worker routes through add_song_zero_token().
- REQUIREMENTS.md + ROADMAP.md amended; follow-up todo filed.
</verification>

<success_criteria>
- GBS-TOKEN-01: persistent "Add a song" button visible whenever GBS.FM bound + logged in (D-05 amendment).
- GBS-TOKEN-03: button reuses _open_gbs_search_dialog()/GBSSearchDialog (D-10); worker calls add_song_zero_token() (capture hook fires).
- GBS-TOKEN-04 (obsolete): button persists; post-add = dialog-close + re-poll via trigger_gbs_repoll() (D-08/D-09).
- D-07: no client-side gating; server messages-cookie text surfaced verbatim by the existing dialog.
- Docs reframed (REQUIREMENTS GBS-TOKEN-01/04/05 + ROADMAP SC#1/#3/#4/#5); capture-on-use todo filed.
</success_criteria>

<output>
Create `.planning/phases/87B-gbs-zero-token-single-song-add/87B-02-SUMMARY.md` when done.
</output>
</content>
