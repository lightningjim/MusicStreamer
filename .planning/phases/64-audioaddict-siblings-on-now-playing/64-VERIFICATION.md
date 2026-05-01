---
phase: 64-audioaddict-siblings-on-now-playing
verified: 2026-05-01T00:00:00Z
status: human_needed
score: 22/22 must-haves verified
overrides_applied: 0
human_verification:
  - test: "End-to-end UX feel of click-switches-playback"
    expected: "Click 'Also on: ZenRadio' on a playing DI.fm Ambient station — panel re-binds to ZenRadio Ambient, audio transitions to ZenRadio stream, 'Connecting…' toast fires, Recently Played updates, OS media-keys metadata reflects the new station, no audible glitch beyond normal Connecting flow, no UI flicker"
    why_human: "Automated tests prove the signal-handler chain fires (Player.play(sibling) + update_last_played(sibling.id) + bind_station(sibling)) but a human eye is required to confirm perceived audio transition smoothness and absence of UI flicker — these qualities are not observable from grep/pytest"
  - test: "Hidden-for-non-AA layout cleanliness"
    expected: "Play a non-AA station (YouTube or Radio-Browser) — confirm no 'Also on:' line, no visual gap, no layout shift; switch to AA station with siblings — line appears with no layout pop"
    why_human: "Automated tests assert isHidden() and zero-text state but visual layout pop / gap absence is a perceptual verdict not derivable from widget state checks"
---

# Phase 64: AudioAddict Siblings on Now Playing — Verification Report

**Phase Goal:** When an AudioAddict station is currently playing, the Now Playing panel surfaces same-channel-key siblings on other AA networks as one-click jumps. Continuation of Phase 51 — clicking a sibling DOES change playback (unlike Phase 51's edit-dialog flow).
**Verified:** 2026-05-01
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria + PLAN must-haves)

| #   | Truth                                                                                                                                              | Status     | Evidence                                                                                                                                                                                                                                  |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SC1 | While playing AA station with siblings, NowPlayingPanel renders "Also on:" line listing sibling networks                                            | ✓ VERIFIED | `now_playing_panel.py:183-189` constructs `_sibling_label` with Qt.RichText; `_refresh_siblings` (line 646) calls `find_aa_siblings` + `render_sibling_html`; locked by `test_sibling_label_visible_for_aa_station_with_siblings`        |
| SC2 | Clicking a sibling network switches active playback to that sibling station (DOES change playback — Phase 51 inversion)                            | ✓ VERIFIED | `main_window.py:254` connect line; `_on_sibling_activated` at line 330 delegates to `_on_station_activated`; integration test `test_sibling_click_switches_playback_via_main_window` asserts `fake_player.play_calls == [zen_station]` |
| SC3 | Line is hidden entirely when non-AA, no siblings, or no station playing                                                                           | ✓ VERIFIED | Three explicit `_sibling_label.setVisible(False)` paths in `_refresh_siblings` (lines 662, 673); locked by 4 panel tests (non-AA, no-siblings, no-station-bound, self-only)                                                              |
| SC4 | Detection reuses Phase 51's `find_aa_siblings` helper — no parallel detection logic                                                                | ✓ VERIFIED | `now_playing_panel.py:49` imports only `find_aa_siblings, render_sibling_html`; grep confirms NO imports of `_is_aa_url`, `_aa_slug_from_url`, `_aa_channel_key_from_url`, or `NETWORKS`; locked by `test_panel_does_not_reimplement_aa_detection` |
| SC5 | Currently-playing station's own row is not listed as a sibling of itself                                                                          | ✓ VERIFIED | Self-exclusion enforced at `url_helpers.py:122-123` (find_aa_siblings); D-08 belt-and-braces guard at `now_playing_panel.py:707`; locked by `test_sibling_label_excludes_self`                                                            |
| T01 | `render_sibling_html` exists as free function in url_helpers.py producing 'Also on: <a href="sibling://{id}">{label}</a>' (D-03)                  | ✓ VERIFIED | `url_helpers.py:150-179`; runtime check confirms `render_sibling_html([('zenradio', 2, 'Ambient')], 'Ambient')` returns `'Also on: <a href="sibling://2">ZenRadio</a>'`                                                                  |
| T02 | `html.escape(station_name, quote=True)` preserved in promoted renderer (T-39-01 mitigation)                                                       | ✓ VERIFIED | `url_helpers.py:176`; locked by `test_render_sibling_html_html_escapes_station_name`                                                                                                                                                     |
| T03 | EditStationDialog imports `render_sibling_html` from url_helpers and calls free function                                                          | ✓ VERIFIED | `edit_station_dialog.py:51` imports both helpers; line 563 calls `render_sibling_html(siblings, self._station.name)` (no `self.`)                                                                                                       |
| T04 | EditStationDialog._render_sibling_html no longer exists                                                                                            | ✓ VERIFIED | `grep -c "_render_sibling_html" musicstreamer/ui_qt/edit_station_dialog.py` returns 0                                                                                                                                                     |
| T05 | Phase 51 dialog sibling tests remain green after promotion                                                                                         | ✓ VERIFIED | `tests/test_edit_station_dialog.py` part of the 167-passed Wave 2 set; full dialog suite green                                                                                                                                            |
| T06 | U+2022 BULLET and U+2014 EM DASH preserved verbatim in promoted renderer                                                                          | ✓ VERIFIED | `url_helpers.py:177` (`—`) and line 179 (`•`); locked by `test_render_sibling_html_uses_em_dash_when_names_differ` and `test_render_sibling_html_uses_bullet_separator_for_multiple`                                                |
| T07 | href payload remains integer-only (`sibling://{id}`)                                                                                              | ✓ VERIFIED | `url_helpers.py:178`; click-side parsed with `int(...)` + `try/except ValueError` at `now_playing_panel.py:699-702`                                                                                                                       |
| T08 | Dead imports (`import html`, `from musicstreamer.aa_import import NETWORKS`) removed from EditStationDialog                                        | ✓ VERIFIED | grep `^import html$` and `^from musicstreamer.aa_import import NETWORKS$` on edit_station_dialog.py both return zero matches                                                                                                              |
| T09 | NowPlayingPanel exposes `sibling_activated = Signal(object)` (D-02)                                                                                | ✓ VERIFIED | `now_playing_panel.py:123`; runtime check `hasattr(NowPlayingPanel, 'sibling_activated')` returns True                                                                                                                                    |
| T10 | `_sibling_label` QLabel has Qt.RichText, setOpenExternalLinks(False), setVisible(False), bound-method linkActivated (D-01, D-05a, QA-05)         | ✓ VERIFIED | `now_playing_panel.py:183-188`; bound-method connection (no lambda) at line 188                                                                                                                                                          |
| T11 | `_refresh_siblings` is called ONLY from `bind_station` (D-04)                                                                                     | ✓ VERIFIED | `now_playing_panel.py:376`; only call site (verified by grep); locked by negative spy `test_refresh_siblings_runs_once_per_bind_station_call`                                                                                            |
| T12 | `_refresh_siblings` reads `self._station.streams[0].url` with empty-streams defensive fallback (D-06)                                              | ✓ VERIFIED | `now_playing_panel.py:661-665`; guard checks `self._station is None or not self._station.streams`                                                                                                                                         |
| T13 | `_on_sibling_link_activated` parses `sibling://{id}`, has D-08 self-id guard, wraps `repo.get_station` in try/except Exception                    | ✓ VERIFIED | `now_playing_panel.py:696-715`; D-08 guard at line 707; try/except Exception at line 709-712; locked by `test_sibling_link_handler_no_op_when_repo_get_station_raises` and `test_sibling_link_handler_no_op_on_malformed_href`         |
| T14 | MainWindow connects `now_playing.sibling_activated` to `_on_sibling_activated` (bound-method, QA-05)                                              | ✓ VERIFIED | `main_window.py:254`; bound-method connection (no lambda)                                                                                                                                                                                |
| T15 | `_on_sibling_activated(Station)` delegates to `self._on_station_activated(station)`                                                                | ✓ VERIFIED | `main_window.py:330-341`; one-line delegator                                                                                                                                                                                              |
| T16 | Connect line lands AFTER `now_playing.edit_requested` connect (RESEARCH Pitfall #4 connection ordering)                                            | ✓ VERIFIED | `main_window.py:252-254`; sibling_activated connect immediately follows edit_requested connect                                                                                                                                            |
| T17 | Toast wording is "Connecting…" (U+2026) — no separate "Switched to ZenRadio" toast                                                                | ✓ VERIFIED | `main_window.py:325` (in `_on_station_activated`, inherited via delegation)                                                                                                                                                                |

**Score:** 22/22 truths verified

### Required Artifacts

| Artifact                                          | Expected                                                                                     | Status     | Details                                                                                                  |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------- |
| `musicstreamer/url_helpers.py`                    | `render_sibling_html` free function next to `find_aa_siblings`; `import html` at module top | ✓ VERIFIED | Lines 10, 87, 150-179; both functions colocated                                                          |
| `musicstreamer/ui_qt/edit_station_dialog.py`      | Import line updated; private renderer deleted; dead imports removed                           | ✓ VERIFIED | Line 51 import; `_render_sibling_html` count = 0; `import html` count = 0; `import NETWORKS` count = 0   |
| `musicstreamer/ui_qt/now_playing_panel.py`        | sibling_activated Signal, _sibling_label QLabel, _refresh_siblings, _on_sibling_link_activated | ✓ VERIFIED | Lines 49, 123, 183-189, 376, 646-679, 681-715                                                            |
| `musicstreamer/ui_qt/main_window.py`              | sibling_activated connect line + `_on_sibling_activated` delegating slot                      | ✓ VERIFIED | Lines 254, 330-341                                                                                       |
| `tests/test_aa_siblings.py`                       | 5 new renderer tests appended                                                                | ✓ VERIFIED | Lines 137, 145, 155, 166, 177 — all 5 tests present                                                      |
| `tests/test_now_playing_panel.py`                 | FakeRepo extension + _make_aa_station factory + 11 panel tests                                | ✓ VERIFIED | All 11 sibling tests present at lines 774-920; FakeRepo extended; `_make_aa_station` defined           |
| `tests/test_main_window_integration.py`           | End-to-end click→play integration test                                                        | ✓ VERIFIED | `test_sibling_click_switches_playback_via_main_window` at line 1009                                      |

### Key Link Verification

| From                                                                  | To                                                                  | Via                                       | Status      | Details                                                                                                                                |
| --------------------------------------------------------------------- | ------------------------------------------------------------------- | ----------------------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `EditStationDialog._refresh_siblings`                                 | `musicstreamer.url_helpers.render_sibling_html`                     | free-function call                        | ✓ WIRED     | `edit_station_dialog.py:563` calls `render_sibling_html(siblings, self._station.name)` (no `self.`)                                    |
| `url_helpers.render_sibling_html`                                     | `html.escape(name, quote=True)`                                     | T-39-01 mitigation                         | ✓ WIRED     | `url_helpers.py:176`                                                                                                                    |
| `NowPlayingPanel.bind_station`                                        | `self._refresh_siblings`                                            | single call site after `_populate_stream_picker` | ✓ WIRED     | `now_playing_panel.py:372-376` — exact ordering matches PLAN pattern                                                                  |
| `NowPlayingPanel._refresh_siblings`                                   | `find_aa_siblings + render_sibling_html`                            | imported free functions                    | ✓ WIRED     | Line 49 imports both; lines 667 + 677 invoke                                                                                           |
| `self._sibling_label.linkActivated`                                   | `self._on_sibling_link_activated`                                   | bound-method connection (QA-05)            | ✓ WIRED     | `now_playing_panel.py:188`                                                                                                              |
| `NowPlayingPanel.sibling_activated`                                   | `MainWindow._on_sibling_activated`                                  | Qt Signal/Slot bound-method                 | ✓ WIRED     | `main_window.py:254`                                                                                                                    |
| `MainWindow._on_sibling_activated`                                    | `MainWindow._on_station_activated`                                  | thin delegator (D-02)                       | ✓ WIRED     | `main_window.py:341` — `self._on_station_activated(station)`                                                                           |
| `MainWindow._on_station_activated`                                    | Player.play + Repo.update_last_played + StationListPanel.refresh_recent + show_toast + media_keys.publish_metadata | existing canonical chain                    | ✓ WIRED     | Lines 318-328 — all six side effects fire                                                                                              |

### Data-Flow Trace (Level 4)

| Artifact                          | Data Variable                          | Source                                                              | Produces Real Data | Status     |
| --------------------------------- | -------------------------------------- | ------------------------------------------------------------------- | ------------------ | ---------- |
| `NowPlayingPanel._sibling_label`  | `siblings` (from `find_aa_siblings`)  | `self._repo.list_stations()` → real DB query in production Repo    | Yes                | ✓ FLOWING  |
| `NowPlayingPanel._sibling_label`  | label HTML text                        | `render_sibling_html(siblings, self._station.name)` — pure function | Yes                | ✓ FLOWING  |
| `MainWindow._on_sibling_activated`| `station` (Station instance)           | `self._repo.get_station(int_id)` via panel `_on_sibling_link_activated` | Yes                | ✓ FLOWING  |
| `Player.play(sibling)`            | sibling Station                        | resolved from repo, emitted via `sibling_activated(Station)` signal | Yes                | ✓ FLOWING  |

### Behavioral Spot-Checks

| Behavior                                                              | Command                                                                                                              | Result                                                                            | Status |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | ------ |
| Renderer produces correct HTML output                                 | `python -c "from musicstreamer.url_helpers import render_sibling_html; ..."`                                          | `'Also on: <a href="sibling://2">ZenRadio</a>'`                                  | ✓ PASS |
| NowPlayingPanel exposes sibling_activated Signal                      | `python -c "from ...now_playing_panel import NowPlayingPanel; print(hasattr(NowPlayingPanel, 'sibling_activated'))"` | `True`                                                                            | ✓ PASS |
| SC #2 integration test passes                                         | `pytest tests/test_main_window_integration.py::test_sibling_click_switches_playback_via_main_window -x`              | PASSED                                                                            | ✓ PASS |
| SC #4 negative-spy test passes                                        | `pytest tests/test_now_playing_panel.py::test_panel_does_not_reimplement_aa_detection -x`                            | PASSED                                                                            | ✓ PASS |
| SC #5 self-exclusion test passes                                      | `pytest tests/test_now_playing_panel.py::test_sibling_label_excludes_self -x`                                        | PASSED                                                                            | ✓ PASS |
| D-04 single-call-site negative spy                                    | `pytest tests/test_now_playing_panel.py::test_refresh_siblings_runs_once_per_bind_station_call -x`                   | PASSED                                                                            | ✓ PASS |
| Wave 2 test bundle (167 tests)                                        | `pytest tests/test_aa_siblings.py tests/test_now_playing_panel.py tests/test_main_window_integration.py tests/test_edit_station_dialog.py` | 167 passed                                                                        | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plans     | Description                                                                                                                                  | Status                  | Evidence                                                                                                                                                                                    |
| ----------- | ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| BUG-02      | 64-01, 64-02, 64-03 | Cross-network AudioAddict mirror/sibling streams surface as related streams when editing or playing a station (closure follow-up to Phase 51) | ✓ SATISFIED (follow-up) | All 5 ROADMAP SCs verified; integration test confirms playback switching; REQUIREMENTS.md maps BUG-02 → Phase 51 (closed); Phase 64 plans declare BUG-02 as a closure follow-up requirement |

**Note on REQUIREMENTS.md mapping:** REQUIREMENTS.md `Traceability` table lists BUG-02 against Phase 51 (Complete). Phase 64 is a "closure follow-up" extending the surface from edit dialog to Now Playing panel — declared in plan frontmatters but not (yet) in REQUIREMENTS.md. No orphaned requirement IDs. This is consistent with a continuation-phase pattern.

### Anti-Patterns Found

| File                                           | Line  | Pattern        | Severity | Impact                                                                                                                            |
| ---------------------------------------------- | ----- | -------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `musicstreamer/ui_qt/main_window.py`           | 449, 451 | "placeholder" | ℹ️ Info  | Pre-existing Phase 999.1 new-station flow ("placeholder station" pattern) — unrelated to phase 64; not introduced by this phase |

No phase-64-introduced anti-patterns. No TODO/FIXME/PLACEHOLDER markers. No stub returns. No empty handlers. No console.log-only implementations. The five logically empty-state branches in `_refresh_siblings` (`setVisible(False) + setText("")`) are intentional D-05 hide paths, not stubs.

### Code Review Status

`64-REVIEW.md`: 0 critical / 2 warning / 4 info — all classified non-blocking.

- **WR-01** (defense-in-depth): `_refresh_siblings` does not wrap `repo.list_stations()` in try/except — same slots-never-raise contract that was applied to `repo.get_station` in `_on_sibling_link_activated`. The phase considered this acceptable because the canonical activation chain is reached via slots; a transient DB error would propagate. This is a hardening suggestion, not a goal-blocker.
- **WR-02** (pre-existing in Phase 51): `_on_navigate_to_sibling` does not handle production `ValueError` from `repo.get_station`. Pre-existing code, not phase-64-introduced.
- **IN-01..IN-04**: Stale line-number references (IN-01, IN-02), defense-in-depth slug escape (IN-03), empty-input contract documentation (IN-04). All informational.

### Human Verification Required

Two manual UAT items per `64-VALIDATION.md` § "Manual-Only Verifications":

#### 1. End-to-end UX feel of click-switches-playback

**Test:** Launch app. Play a DI.fm station that has a known AA sibling (e.g. DI.fm "Ambient" with ZenRadio "Ambient" also imported). Confirm "Also on: ZenRadio" appears under the station name. Click ZenRadio.
**Expected:** Panel re-binds to ZenRadio Ambient (name+logo update); audio transitions to the ZenRadio stream; "Connecting…" toast fires; Recently Played updates; OS media-keys metadata reflects the new station; no audible glitch beyond normal Connecting flow; no UI flicker.
**Why human:** Automated tests prove the signal-handler chain fires (Player.play(sibling) + update_last_played(sibling.id) + bind_station(sibling)) but a human eye is required to confirm perceived audio transition smoothness and absence of UI flicker.

#### 2. Hidden-for-non-AA layout cleanliness

**Test:** Play a non-AA station (e.g. YouTube or Radio-Browser). Confirm no "Also on:" line. Switch to an AA station with siblings.
**Expected:** Line appears with no layout pop / no visual gap / no shift.
**Why human:** Automated tests assert `isHidden()` and zero-text state but visual layout pop / gap absence is a perceptual verdict not derivable from widget state checks.

### Gaps Summary

No goal-blocking gaps. All 5 ROADMAP success criteria are observable in the codebase, each locked by at least one automated test. All 22 must-have truths from Plan 01/02/03 frontmatter are verified. The renderer was promoted, the dialog was cleaned up, the panel surfaces the line, and the click chain drives playback end-to-end (verified by the load-bearing `Player.play(sibling)` integration assertion).

The status is `human_needed` (not `passed`) solely because two perceptual UAT items are documented in `64-VALIDATION.md` and require a developer to launch the app and observe transition smoothness / layout cleanliness. The decision tree mandates `human_needed` whenever non-empty human verification items exist, even with a perfect automated score.

---

_Verified: 2026-05-01_
_Verifier: Claude (gsd-verifier)_
