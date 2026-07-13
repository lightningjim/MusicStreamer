---
phase: 87B-gbs-zero-token-single-song-add
verified: 2026-06-18T00:00:00Z
status: human_needed
score: 9/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Perform a live song add via the 'Add a song' button on a GBS.FM station with tokens>0"
    expected: "Button is visible, clicking opens GBSSearchDialog, selecting a song and confirming triggers the no-PII capture hook log line (check buffer_log or stderr for 'gbs.add.zero_token_capture'), the dialog closes, and the GBS playlist widget re-polls with the newly queued song visible"
    why_human: "Full UI flow requires a live GBS.FM session; tokens==0 path cannot be reached at 48 tokens, so only the tokens>0 path can be exercised now. The zero-token fixture is intentionally a placeholder per D-01/D-03."
  - test: "Verify the real tokens==0 add behavior on first live use"
    expected: "The _capture_add_shape() hook emits a structured WARN log line with message_len/message_category; the PLACEHOLDER fixture (tests/fixtures/gbs_zero_token/add_redirect_zero_token_PLACEHOLDER.txt) is replaced with the captured real response; the capture-on-use todo is resolved"
    why_human: "Cannot reach tokens==0 state on demand (user is at 48 tokens per D-01). This is the documented deferred item per D-02/D-03 — expected to remain human-only until the first live occurrence."
---

# Phase 87B: GBS Zero-Token Single-Song Add — Verification Report

**Phase Goal:** Deliver a persistent "Add a song" affordance in the now-playing panel for the bound GBS.FM station, visible whenever GBS.FM is bound + logged in (ANY token count), that opens the existing GBSSearchDialog; confirming a song adds exactly one via the GBS song-add endpoint including the zero-token free case. The zero-token endpoint is PROVISIONAL (reuses GET /add/<songid> via add_song_zero_token()) with capture-on-first-use.

**Verified:** 2026-06-18

**Status:** human_needed

**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Button is ALWAYS visible when GBS bound+logged-in (should_show = is_gbs and logged_in); NOT gated on token count | VERIFIED | `now_playing_panel.py:2985-3017` — `should_show = is_gbs and logged_in`; `self._gbs_add_btn.setVisible(should_show)` at line 3017; no `fetch_user_tokens` call in visibility path (grep returns 0 hits) |
| 2 | Button label is exactly "Add a song"; tooltip is exactly "Add a song to the GBS.FM queue"; neither contains the word "token" | VERIFIED | `now_playing_panel.py:735-736`; drift-guard test `test_add_song_zero_token_has_no_token_wording` GREEN (63 passed); no `token` string literals in add-song affordance copy |
| 3 | `gbs_api.add_song_zero_token()` exists as a thin wrapper over `submit()` with no HTTP duplication | VERIFIED | `gbs_api.py:1156-1165` — three-statement body: `result = submit(songid, cookies)`, `_capture_add_shape(...)`, `return result`; no `_open_no_redirect`/`_decode_django_messages`/`GBS_BASE` in body |
| 4 | Button opens the existing GBSSearchDialog via the existing `_open_gbs_search_dialog()` launch path | VERIFIED | `now_playing_panel.py:321` declares `add_song_requested = Signal()`; `main_window.py:437-439` connects `now_playing.add_song_requested` to `_open_gbs_search_dialog`; `main_window.py:1547-1561` implements the method |
| 5 | Dialog submit worker calls `add_song_zero_token()`, NOT bare `submit()` | VERIFIED | `gbs_search_dialog.py:142` — `msg = gbs_api.add_song_zero_token(self._songid, self._cookies)`; test `test_submit_worker_calls_add_song_zero_token` PASSED |
| 6 | Post-add: button persists (no hide-after-add); dialog closes and GBS playlist re-polls via `trigger_gbs_repoll()` | VERIFIED | `main_window.py:1558-1560` — `dlg.submission_completed.connect(self.now_playing.trigger_gbs_repoll)`; `now_playing_panel.py:3236-3248` — `trigger_gbs_repoll()` resets `_gbs_poll_cursor = {}` and calls `_on_gbs_poll_tick()`; no hide-after-add logic found in panel or dialog |
| 7 | `_capture_add_shape()` no-PII hook exists and emits only method+path+songid+message_len+message_category — no cookies/sessionid/csrftoken | VERIFIED | `gbs_api.py:1168-1177`; `test_capture_hook_no_pii` PASSED (63 passed, 0 failed); log format string contains only `endpoint=/add/%s message_len=%d message_category=%s` |
| 8 | REQUIREMENTS.md GBS-TOKEN-01/04/05 and ROADMAP.md SC#1/#3/#4/#5 were amended to match the reframe | VERIFIED | REQUIREMENTS.md lines 69/72/73: AMENDED D-05 / AMENDED D-08 / RELAXED D-03 citations confirmed; ROADMAP.md lines 432/434/435/436: all four SCs carry matching amendment text |
| 9 | Provisional fixture + placeholder + MANIFEST exist; placeholder is documented pending-capture; follow-up todo exists with `resolves_phase: 87B` | VERIFIED | `tests/fixtures/gbs_zero_token/` contains all three files; MANIFEST.md has `resolves_phase: 87B` row; `add_redirect_zero_token_PLACEHOLDER.txt` is comment-only placeholder; `.planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md` exists with `resolves_phase: 87B` |

**Score:** 9/9 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/gbs_api.py` | `add_song_zero_token()` + `_capture_add_shape()` | VERIFIED | Lines 1156-1177; wrapper wraps `submit()` only; hook logs structured no-PII WARN |
| `musicstreamer/ui_qt/now_playing_panel.py` | `_gbs_add_btn`, `add_song_requested`, `_on_add_song_clicked`, `trigger_gbs_repoll()` | VERIFIED | Lines 321, 730-739, 3017, 3227-3248 |
| `musicstreamer/ui_qt/main_window.py` | `add_song_requested.connect(_open_gbs_search_dialog)`, `submission_completed.connect(trigger_gbs_repoll)` | VERIFIED | Lines 437-439 (init wiring); lines 1558-1560 (dialog wiring) |
| `musicstreamer/ui_qt/gbs_search_dialog.py` | `_GbsSubmitWorker.run()` calls `add_song_zero_token()` not bare `submit()` | VERIFIED | Line 142 |
| `tests/fixtures/gbs_zero_token/add_redirect_response_48tokens.txt` | Provisional fixture with `set-cookie: messages=` line | VERIFIED | File exists; confirmed contains `set-cookie: messages=` |
| `tests/fixtures/gbs_zero_token/add_redirect_zero_token_PLACEHOLDER.txt` | Comment-only placeholder (D-01: cannot capture at 48 tokens) | VERIFIED | File is three comment lines reserving slot for first live capture |
| `tests/fixtures/gbs_zero_token/MANIFEST.md` | Provenance table with `resolves_phase: 87B` placeholder row | VERIFIED | Both rows present: `real-captured` 48-token row and `pending-capture` placeholder row |
| `tests/test_gbs_zero_token_drift_guard.py` | GBS-TOKEN-02 drift-guard; `test_add_song_zero_token_has_no_token_wording` | VERIFIED | File exists; function at line 37; PASSED in test run |
| `tests/test_gbs_api.py` | Four new tests: submit reuse, auth-expiry propagation, PII-free capture hook, fixture exists | VERIFIED | Lines 1264-1315; all 4 PASSED |
| `tests/test_now_playing_panel.py` | Visibility tests (GBS logged-in, non-GBS, not-logged-in, no-fetch_user_tokens), label/tooltip, repoll tests | VERIFIED | 7 functions found at lines 3830-4031; all PASSED (14 tests total in Wave 2 run) |
| `tests/test_main_window_gbs.py` | `test_submission_completed_wired_to_repoll`, `test_add_song_requested_opens_dialog`, `test_submit_worker_calls_add_song_zero_token`, `test_stale_submission_docstring_gone` | VERIFIED | Lines 208, 238, 259, 250; all PASSED |
| `.planning/REQUIREMENTS.md` | GBS-TOKEN-01/04/05 amended; GBS-TOKEN-02/03 unchanged | VERIFIED | Correct amendment citations present |
| `.planning/ROADMAP.md` | SC#1/#3/#4/#5 rewritten; SC#2 intact; line-45 one-liner updated | VERIFIED | Lines 432-436 carry all four amendment markers |
| `.planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md` | Capture-on-use todo with `resolves_phase: 87B` | VERIFIED | File exists; `resolves_phase: 87B` confirmed |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `now_playing_panel._gbs_add_btn` | `main_window._open_gbs_search_dialog` | `add_song_requested` Signal connected in `main_window.__init__` | WIRED | `now_playing_panel.py:437-439` connects `add_song_requested` to `_open_gbs_search_dialog` |
| `gbs_search_dialog.submission_completed` | `now_playing_panel.trigger_gbs_repoll` | `submission_completed.connect(...)` in `_open_gbs_search_dialog` | WIRED | `main_window.py:1558-1560`; also covered by `test_submission_completed_wired_to_repoll` |
| `gbs_search_dialog._GbsSubmitWorker.run` | `gbs_api.add_song_zero_token` | Call-site change from bare `submit()` | WIRED | `gbs_search_dialog.py:142`; confirmed by `test_submit_worker_calls_add_song_zero_token` |
| `gbs_api.add_song_zero_token` | `gbs_api.submit` | Direct call; no HTTP duplication | WIRED | `gbs_api.py:1163` — `result = submit(songid, cookies)` |
| `gbs_api._capture_add_shape` | `logging.getLogger("musicstreamer.gbs_api")` | `_log.warning(...)` structured no-PII line | WIRED | `gbs_api.py:1172` — `_log.warning(...)` with `gbs.add.zero_token_capture` prefix |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `now_playing_panel._gbs_add_btn` visibility | `should_show` | `_refresh_gbs_visibility()` — `is_gbs and logged_in` Boolean; no token fetch | Yes (live station/auth state) | FLOWING |
| `gbs_search_dialog._GbsSubmitWorker` result | `msg` from `add_song_zero_token()` | `gbs_api.submit()` → GET `/add/<songid>` → `_decode_django_messages()` from `messages` cookie | Yes (real HTTP response via existing submit path) | FLOWING |
| `trigger_gbs_repoll()` re-poll | `_gbs_poll_cursor` reset to `{}` → `_on_gbs_poll_tick()` | Existing `_GbsPlaylistWorker` / `playlist_ready` pipeline (Phase 60) | Yes (reuses established poll machinery) | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Wave 1 tests: add_song_zero_token wrapper, drift-guard, PII-free hook, fixture | `.venv/bin/python -m pytest tests/test_gbs_api.py tests/test_gbs_zero_token_drift_guard.py -x` | 63 passed, 1 warning | PASS |
| Wave 2 tests: button visibility, label, repoll, dialog wiring, worker call-site | `.venv/bin/python -m pytest tests/test_now_playing_panel.py -k "add_song or repoll" tests/test_main_window_gbs.py -k "repoll or add_song or submission" -x` | 14 passed, 0 failed | PASS |
| Submit worker calls add_song_zero_token (not bare submit) | `.venv/bin/python -m pytest tests/test_main_window_gbs.py -k "submit_worker" -x` | 1 passed | PASS |
| add_song_zero_token importable and callable | `.venv/bin/python -c "import musicstreamer.gbs_api as g; assert callable(g.add_song_zero_token)"` | (implied by 63 test passes; function confirmed at gbs_api.py:1156) | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| GBS-TOKEN-01 | 87B-02-PLAN | Persistent "Add a song" visible whenever GBS.FM bound + logged in (AMENDED: any token count) | SATISFIED | `should_show = is_gbs and logged_in` in `_refresh_gbs_visibility()`; no token gating; `test_add_song_visibility_gbs_logged_in` PASSED |
| GBS-TOKEN-02 | 87B-01-PLAN | UI never uses word "token" in button label, tooltip, or surrounding affordance text | SATISFIED | Button label "Add a song", tooltip "Add a song to the GBS.FM queue" confirmed in source; drift-guard `test_add_song_zero_token_has_no_token_wording` GREEN; no token string literal in add-song affordance copy |
| GBS-TOKEN-03 | 87B-01-PLAN + 87B-02-PLAN | Activating affordance opens existing GBSSearchDialog; confirming calls `gbs_api.add_song_zero_token()` | SATISFIED | Worker call-site at `gbs_search_dialog.py:142`; panel signal → `_open_gbs_search_dialog()` wired in `main_window.py:437-439` |
| GBS-TOKEN-04 | 87B-02-PLAN | Button persists (no hide-after-add); post-add = dialog-close + re-poll (AMENDED: supersedes original hide/re-appear) | SATISFIED | No hide-after-add logic found; `submission_completed` → `trigger_gbs_repoll()` wired; REQUIREMENTS.md carries AMENDED D-08 citation |
| GBS-TOKEN-05 | 87B-01-PLAN | Observable /add shape fixture-locked; real tokens==0 payload captured on first live use (RELAXED: deferred to capture-on-use) | SATISFIED (provisional) | Fixture directory exists with 48-token fixture, PLACEHOLDER, and MANIFEST; follow-up todo `2026-06-18-gbs-zero-token-endpoint-confirm.md` filed with `resolves_phase: 87B` |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `gbs_api.py` | 1157-1162 | `# comment` docstrings instead of triple-quoted docstrings | Info | Intentional deviation documented in 87B-01-SUMMARY decisions: triple-quoted strings would trigger the GBS-TOKEN-02 drift-guard regex through "GBS-TOKEN-03" references; # comments are stripped by `_strip_comments()`. Not a stub. |
| `tests/fixtures/gbs_zero_token/add_redirect_zero_token_PLACEHOLDER.txt` | 1-3 | Placeholder fixture (three comment lines, no real data) | Info | Intentional per D-01/D-03; user is at 48 tokens with no path to zero; `MANIFEST.md` documents `pending-capture` with `resolves_phase: 87B`; follow-up todo filed. Expected behavior, not a gap. |

No `TBD`, `FIXME`, or `XXX` debt markers found in files modified by this phase.

---

### Deferred Items

Items not yet met but explicitly addressed in the capture-on-use follow-up mechanism:

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Real `tokens==0` fixture — capture the actual GBS.FM response when tokens reach zero | Capture-on-use (.planning/todos/pending/2026-06-18-gbs-zero-token-endpoint-confirm.md) | `resolves_phase: 87B`; `_capture_add_shape()` hook fires on every add and will record the real response shape on first live zero-token add; PLACEHOLDER reserved in fixture dir |

---

### Human Verification Required

#### 1. Live "Add a song" flow (tokens>0 path)

**Test:** On a live GBS.FM session (any token count), click the "Add a song" button in the now-playing panel. Search for a song, select it, and confirm the add.

**Expected:** The GBSSearchDialog opens; the submit button triggers the add; the dialog shows the server's inline message (empty = success, or the server's messages-cookie text verbatim if a limit fires); the dialog closes; the GBS playlist widget in the now-playing panel re-polls and shows the newly queued song. Check stderr/buffer_log for the `gbs.add.zero_token_capture endpoint=/add/... message_len=... message_category=...` WARN line to confirm the capture hook fired.

**Why human:** Full UI flow requires a live GBS.FM session and cannot be exercised in the headless test environment. Button visibility, click, dialog modal, server round-trip, and playlist re-poll are all live-only behaviors.

#### 2. Zero-token add confirmation (deferred — tokens==0 capture)

**Test:** When tokens reach 0 via natural depletion, trigger "Add a song." Check the capture hook log line (`gbs.add.zero_token_capture`) for the zero-token case, compare the server response to the provisional 48-token fixture, and replace the PLACEHOLDER fixture with the captured payload.

**Expected:** The button remains visible (token-count-independent), the add proceeds, the server enforces its one-at-a-time rule via the messages cookie surfaced verbatim in the dialog. The capture hook records the real endpoint shape for fixture-locking.

**Why human:** Cannot reach tokens==0 state on demand (user is at 48 tokens per D-01). This is the documented deferred item per D-02/D-03 with `resolves_phase: 87B` todo filed.

---

### Gaps Summary

No automatable gaps. All 9 must-haves are verified in the codebase. The two human-verification items are:

1. Live UI smoke test of the full add-song flow (tokens>0) — cannot exercise in headless pytest.
2. Zero-token endpoint confirmation — blocked by the physical constraint that the user is at 48 tokens; this is the intentional capture-on-use deferral per D-01/D-02/D-03, not a phase failure.

The `status: human_needed` reflects that item 1 (live smoke test) is a standard end-of-phase UAT check, not a gap in the implementation.

---

_Verified: 2026-06-18_
_Verifier: Claude (gsd-verifier)_
