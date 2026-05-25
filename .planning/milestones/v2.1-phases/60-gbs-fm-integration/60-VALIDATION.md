---
phase: 60
slug: gbs-fm-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-04
---

# Phase 60 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Test map and fixture pinning derived from `60-RESEARCH.md §Validation Architecture` (live-verified 2026-05-04).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing — `pyproject.toml [tool.pytest.ini_options]`) |
| **UI test framework** | pytest-qt (existing) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/test_gbs_api.py tests/ui_qt/test_gbs_search_dialog.py tests/ui_qt/test_now_playing_panel_gbs.py tests/ui_qt/test_accounts_dialog.py -x` |
| **Full suite command** | `pytest -x` |
| **Estimated runtime (quick)** | ~10 s |
| **Estimated runtime (full)** | per existing baseline |

---

## Sampling Rate

- **After every task commit:** Run the **quick** command above (focused subset for the task's plan).
- **After every plan wave:** Run `pytest -x` (full suite green).
- **Before `/gsd-verify-work`:** Full suite green + manual live smoke pass (`scripts/gbs_live_smoke.py`, opt-in).
- **Max feedback latency:** 10 s for the quick subset.

---

## Per-Task Verification Map

> Plan filenames are TBD until `/gsd-plan-phase 60` runs. The Plan / Wave / Task ID columns will be filled in by the planner; rows below are pre-pinned to requirement IDs (GBS-01a..f) so the planner can map them.

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| GBS-01a | `fetch_streams()` returns 6 hard-coded quality variants | unit | `pytest tests/test_gbs_api.py::test_fetch_streams_returns_six_qualities -x` | ❌ W0 | ⬜ pending |
| GBS-01a | `fetch_station_metadata()` returns name+description+logo_url | unit | `pytest tests/test_gbs_api.py::test_fetch_station_metadata -x` | ❌ W0 | ⬜ pending |
| GBS-01a | `import_station()` inserts new row first time, updates in-place second time | integration | `pytest tests/test_gbs_api.py::test_import_idempotent -x` | ❌ W0 | ⬜ pending |
| GBS-01a | Logo download wires through `assets.copy_asset_for_station` | integration | `pytest tests/test_gbs_api.py::test_logo_download -x` | ❌ W0 | ⬜ pending |
| GBS-01a | FLAC `bitrate_kbps` sentinel sorts via `stream_ordering.order_streams` | regression | `pytest tests/test_stream_ordering.py::test_gbs_flac_ordering -x` | ❌ W0 (extends existing) | ⬜ pending |
| GBS-01b | `_validate_gbs_cookies` accepts dev fixture format | unit | `pytest tests/test_gbs_api.py::test_validate_cookies_accept -x` | ❌ W0 | ⬜ pending |
| GBS-01b | `_validate_gbs_cookies` rejects no-sessionid / wrong-domain | unit | `pytest tests/test_gbs_api.py::test_validate_cookies_reject -x` | ❌ W0 | ⬜ pending |
| GBS-01b | AccountsDialog `_gbs_box` renders between YouTube and Twitch | UI (pytest-qt) | `pytest tests/ui_qt/test_accounts_dialog.py::test_gbs_box_position -x` | ❌ W0 | ⬜ pending |
| GBS-01b | Connect button writes cookies to `paths.gbs_cookies_path()` with 0o600 perms | UI | `pytest tests/ui_qt/test_accounts_dialog.py::test_gbs_connect_writes_cookies -x` | ❌ W0 | ⬜ pending |
| GBS-01b | Disconnect clears the cookies file and updates label | UI | `pytest tests/ui_qt/test_accounts_dialog.py::test_gbs_disconnect_clears -x` | ❌ W0 | ⬜ pending |
| GBS-01c | `fetch_active_playlist()` parses cold-start fixture into expected state dict | unit | `pytest tests/test_gbs_api.py::test_fetch_playlist_cold_start -x` | ❌ W0 | ⬜ pending |
| GBS-01c | `fetch_active_playlist()` parses steady-state fixture | unit | `pytest tests/test_gbs_api.py::test_fetch_playlist_steady_state -x` | ❌ W0 | ⬜ pending |
| GBS-01c | `fetch_active_playlist()` raises `GbsAuthExpiredError` on 302 → /accounts/login/ | unit | `pytest tests/test_gbs_api.py::test_fetch_playlist_auth_expired -x` | ❌ W0 | ⬜ pending |
| GBS-01c | Active-playlist widget hidden for non-GBS.FM stations | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_playlist_hidden_for_non_gbs -x` | ❌ W0 | ⬜ pending |
| GBS-01c | Active-playlist widget populates from mock | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_playlist_populates -x` | ❌ W0 | ⬜ pending |
| GBS-01c | Active-playlist QTimer pauses when widget hidden | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_playlist_timer_pauses -x` | ❌ W0 | ⬜ pending |
| GBS-01c | Active-playlist resets cursor `position` on track change (HIGH 4) | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_gbs_playlist_resets_position_on_track_change -x` | ❌ W0 | ⬜ pending |
| GBS-01d | Vote button hidden when logged out | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_vote_hidden_when_logged_out -x` | ❌ W0 | ⬜ pending |
| GBS-01d | `vote_now_playing()` parses success fixture into `{user_vote, score}` | unit | `pytest tests/test_gbs_api.py::test_vote_now_playing_success -x` | ❌ W0 | ⬜ pending |
| GBS-01d | Vote click → optimistic UI → API success → confirmed state from response | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_vote_optimistic_success -x` | ❌ W0 | ⬜ pending |
| GBS-01d | Vote click → optimistic UI → API failure → rollback + toast | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_vote_optimistic_rollback -x` | ❌ W0 | ⬜ pending |
| GBS-01d | Vote button entryid updates only on `now_playing` event from `/ajax` (Pitfall 1 race) | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_vote_entryid_updates_from_ajax -x` | ❌ W0 | ⬜ pending |
| GBS-01d | Re-clicking the highlighted vote value submits vote=0 (clear; BLOCKER 1) | UI | `pytest tests/ui_qt/test_now_playing_panel_gbs.py::test_gbs_vote_clicking_same_value_clears -x` | ❌ W0 | ⬜ pending |
| GBS-01e | `search()` parses test_p1 fixture into result list with songid+artist+title | unit | `pytest tests/test_gbs_api.py::test_search_parses_results -x` | ❌ W0 | ⬜ pending |
| GBS-01e | `search()` extracts pagination from "page X of Y" text | unit | `pytest tests/test_gbs_api.py::test_search_pagination -x` | ❌ W0 | ⬜ pending |
| GBS-01e | `submit()` decodes Django messages cookie on success path | unit | `pytest tests/test_gbs_api.py::test_submit_success_decodes_messages -x` | ❌ W0 | ⬜ pending |
| GBS-01e | `submit()` raises `GbsAuthExpiredError` on 302 → /accounts/login/ | unit | `pytest tests/test_gbs_api.py::test_submit_auth_expired -x` | ❌ W0 | ⬜ pending |
| GBS-01e | GBSSearchDialog query → results list populated from `search()` mock | UI | `pytest tests/ui_qt/test_gbs_search_dialog.py::test_search_populates -x` | ❌ W0 | ⬜ pending |
| GBS-01e | GBSSearchDialog Submit → calls `submit(songid)` and toasts on success | UI | `pytest tests/ui_qt/test_gbs_search_dialog.py::test_submit_success -x` | ❌ W0 | ⬜ pending |
| GBS-01e | GBSSearchDialog Submit → inline error on duplicate / token-quota | UI | `pytest tests/ui_qt/test_gbs_search_dialog.py::test_submit_inline_error -x` | ❌ W0 | ⬜ pending |
| GBS-01e | GBSSearchDialog in-flight submit isolated across re-search (HIGH 5) | UI | `pytest tests/ui_qt/test_gbs_search_dialog.py::test_gbs_submit_in_flight_isolated_across_searches -x` | ❌ W0 | ⬜ pending |
| GBS-01f | `stream_ordering.order_streams` consumes Phase 60 output unchanged | regression | `pytest tests/test_stream_ordering.py -x` | ✅ exists | ⬜ pending |

*Status legend: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_gbs_api.py` — covers GBS-01a (HTTP layer + import) + GBS-01c (active playlist) + GBS-01d (vote unit) + GBS-01e (search/submit unit) + GBS-01b (validator)
- [ ] `tests/ui_qt/test_now_playing_panel_gbs.py` — covers GBS-01c (active playlist widget) + GBS-01d (vote UI)
- [ ] `tests/ui_qt/test_gbs_search_dialog.py` — covers GBS-01e (search/submit dialog UI)
- [ ] Extension to `tests/ui_qt/test_accounts_dialog.py` — covers GBS-01b (AccountsDialog group + Connect/Disconnect cookies write)
- [ ] `tests/conftest.py` shared fixtures: `mock_gbs_api` (with `spec=[...]` declared method names), `fake_repo` (with `_FakeStation.station_art_path` matching `models.Station`), `fake_cookies_jar`
- [ ] `tests/fixtures/gbs/*.{json,html,txt}` — **17 fixture files** (15 captured response payloads from the capture script + 2 hand-crafted validator-rejection cookie variants for GBS-01b: `cookies_invalid_no_sessionid.txt`, `cookies_invalid_wrong_domain.txt`). See `60-RESEARCH.md §Validation Architecture` table.
- [ ] `scripts/gbs_capture_fixtures.sh` — re-runnable capture script for refreshing the 15 captured fixtures when gbs.fm changes UI (does NOT generate the 2 validator-rejection cookies — those are hand-crafted error cases)
- [ ] Extension to `tests/test_stream_ordering.py` — `test_gbs_flac_ordering` regression for FLAC bitrate sentinel value
- [ ] (Optional) `scripts/gbs_live_smoke.py` — opt-in live-API smoke launcher (`pytest -m live`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `import_station` round-trip against real gbs.fm | GBS-01a | Network + auth required; not safe in CI | Drop cookies via AccountsDialog → "Add GBS.FM" → verify 6 streams + logo + "GBS.FM added" toast |
| Live `/ajax` event taxonomy unchanged | GBS-01c, GBS-01d | gbs.fm-side schema may shift | Run `pytest -m live tests/test_gbs_api.py::test_live_ajax_taxonomy` (skipped by default) |
| Live vote round-trip | GBS-01d | Side-effecting API call; user-visible state change | Login → play GBS.FM → click vote → verify score updates in UI and on gbs.fm web view |
| Live search/submit round-trip | GBS-01e | Burns one of the user's submission tokens | Login → "Search GBS.FM…" → query → submit → verify success toast and verify track is in user's playlist queue on gbs.fm web view. **Note:** may want to remove test pollution via `/playlist/remove/<id>`. |
| Auth-expired path | GBS-01b, GBS-01c, GBS-01d, GBS-01e | Requires waiting out cookie TTL or manually expiring sessionid | Wait for cookie expiry OR delete sessionid → verify graceful 302→/accounts/login/ → typed exception → toast + AccountsDialog flips to "Not connected" |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (**17 fixtures** + 4 test files + 1 capture script)
- [ ] No watch-mode flags
- [ ] Feedback latency < 10 s for quick subset
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
