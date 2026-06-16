---
phase: 89-youtube-channel-avatar-fetch-cover-slot-swap
verified: 2026-06-16T16:24:17Z
status: verified
human_verified: "2026-06-16 — all 3 human-verification items passed in UAT (see 89-HUMAN-UAT.md); 3 follow-up bugs found+fixed (channel-walk hang, QThread shutdown abort, .desktop node-runtime); security verified 16/16 (89-SECURITY.md)"
score: 7/7 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Bind a real ICY-disabled YouTube station (e.g., Lofi Girl) that has a stored channel_avatar_path. Observe the cover slot."
    expected: "Station thumbnail appears first, then swaps to a clean circular-cropped channel avatar; antialiased, no border ring, centered. Resize the Now Playing panel and confirm the circular avatar re-renders at the new tier."
    why_human: "Circular-crop visual quality (D-06/D-07) — antialiasing, center-balance, and size-vs-adjacent-squares are subjective and cannot be asserted by QPixmap pixel inspection in a headless test."
  - test: "In EditStationDialog, paste a YouTube channel URL and observe the avatar section."
    expected: "Status changes to 'Fetching avatar…', then 'Avatar found'; the 64x64 preview populates with the channel avatar within a few seconds (network-dependent). 'Refresh avatar' button is enabled for YouTube URLs and disabled for non-YouTube URLs."
    why_human: "Live network fetch behavior (yt-dlp against real YouTube CDN) — cannot be tested without a live connection; stub tests cover the logic but not the real roundtrip."
  - test: "After avatar fetch succeeds in EditStationDialog, close the dialog and re-open it for the same station."
    expected: "The avatar preview is populated from the cached PNG (no re-fetch); the Refresh button triggers a new fetch."
    why_human: "Persistence and cache-load correctness across dialog open/close requires live state from SQLite and the real filesystem path."
---

# Phase 89: YouTube Channel-Avatar Fetch + Cover-Slot Swap — Verification Report

**Phase Goal:** ICY-disabled YouTube stations (e.g., Lofi Girl) show the channel avatar (circular crop) in the cover slot instead of duplicating the station thumbnail; cover-resolver precedence keeps Phase 73 MB-CAA above the new avatar fallback.
**Verified:** 2026-06-16T16:24:17Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `fetch_channel_avatar()` populates avatar via `avatar_uncropped` filter; cached load < 1s | VERIFIED | `def fetch_channel_avatar` at yt_import.py:155; `avatar_uncropped` filter at L216; `elapsed < 1.0` assertion in `test_set_avatar_pixmap_from_path_cached_load_under_1s` — PASSED |
| 2 | ICY-disabled YT station with stored avatar shows circular crop in cover slot; failure falls back to thumbnail | VERIFIED | `bind_station` at now_playing_panel.py:937 gates on `icy_disabled AND channel_avatar_path`; `_set_avatar_pixmap_from_path` at L2198; `QPixmap.isNull()` fallback at L2213; 9 avatar tests in test_now_playing_panel.py — all PASSED |
| 3 | Cover-resolver source order: `ICY → iTunes → MB-CAA → channel-avatar → placeholder`; `test_mb_caa_runs_before_channel_avatar` confirms `_mb_caa_lookup` before `_channel_avatar_lookup` in source | VERIFIED | `def _mb_caa_lookup` at cover_art.py:148; `def _channel_avatar_lookup` at L159; `mb_pos < avatar_pos` assertion in test_cover_art_avatar.py:34 — PASSED |
| 4 | Phase 71 sibling-line rendering parity preserved; `test_richtext_baseline_unchanged_by_phase_89` mirrors Phase 71 baseline at count=3 | VERIFIED | `def test_richtext_baseline_unchanged_by_phase_89` at test_constants_drift.py:163; asserts `count == EXPECTED_RICHTEXT_COUNT` (3) — PASSED |
| 5 | `EditStationDialog` surfaces "Refresh avatar" button; auto-fetch on URL paste matches YT-thumbnail UX | VERIFIED | `_refresh_avatar_btn` at edit_station_dialog.py:474; `_AvatarFetchWorker` at L134; 12 avatar dialog tests — all PASSED |

**Score:** 5/5 ROADMAP success criteria verified

---

### Plan Must-Haves Verification

#### Plan 89-01 (ART-AVATAR-05 storage plumbing)

| Truth | Status | Evidence |
|-------|--------|----------|
| Station dataclass carries `channel_avatar_path` through every read mapper (D-13) | VERIFIED | `channel_avatar_path: Optional[str] = None  # Phase 89 D-13` at models.py:43; `grep -c "channel_avatar_path=r\["` returns 4 |
| `repo.update_channel_avatar_path` writes the column without touching other fields | VERIFIED | `def update_channel_avatar_path` at repo.py:850; uses standalone `UPDATE stations SET channel_avatar_path = ?`; `update_station` body does NOT reference `channel_avatar_path` |
| `assets.write_channel_avatar` persists PNG bytes atomically and returns a data_dir-relative path (D-12) | VERIFIED | `def write_channel_avatar` at assets.py:32; contains `tempfile.mkstemp` and `os.replace`; test_assets_avatar.py: 3 tests PASSED |

#### Plan 89-02 (ART-AVATAR-03)

| Truth | Status | Evidence |
|-------|--------|----------|
| `fetch_channel_avatar` selects the `avatar_uncropped` thumbnail and downloads its bytes | VERIFIED | yt_import.py:216 prefers `id == "avatar_uncropped"`; 10 avatar tests in test_yt_import_library.py — PASSED |
| Non-square avatar entries (width != height both present) are rejected | VERIFIED | Null-safe guard at yt_import.py ~L225: `if w is not None and h is not None and w != h`; `test_avatar_rejects_non_square_entry` — PASSED |
| A YouTube video URL resolves to its channel before re-fetching the avatar | VERIFIED | Two-step resolution via `channel_url` / `uploader_url` from info dict; `test_avatar_video_url_two_step_resolution` — PASSED |
| Per-provider fetcher registry exposes `youtube` and accepts future `twitch` registration (D-04) | VERIFIED | `_AVATAR_FETCHERS` dict + `register_avatar_fetcher("youtube", fetch_channel_avatar)` at yt_import.py:261; `test_avatar_registry_youtube_registered`, `test_avatar_registry_twitch_absent_by_default` — PASSED |

#### Plan 89-03 (ART-AVATAR-07, ART-AVATAR-09, ART-AVATAR-10)

| Truth | Status | Evidence |
|-------|--------|----------|
| `cover_art.py` defines `_mb_caa_lookup` then `_channel_avatar_lookup` in that source order (D-14) | VERIFIED | `def _mb_caa_lookup` at L148; `def _channel_avatar_lookup` at L159 — position confirmed |
| `fetch_cover_art` routes its MB-CAA call through `_mb_caa_lookup` (precedence preserved) | VERIFIED | `_mb_caa_lookup(artist, title, callback)` at cover_art.py:240 and L267; no bare `_cover_art_mb.fetch_mb_cover` in dispatch branches |
| `_channel_avatar_lookup` is synchronous, reads `channel_avatar_path`, never raises, never touches Qt | VERIFIED | cover_art.py:159–175: synchronous path-reader with `os.path.exists` guard; `try/except` wrapper; no QPixmap/QThread; `test_channel_avatar_lookup_*` tests — PASSED |
| Phase 71 RichText baseline count (3) unchanged by Phase 89 (D-15) | VERIFIED | `test_richtext_baseline_unchanged_by_phase_89` at test_constants_drift.py:163 — PASSED |

#### Plan 89-04 (ART-AVATAR-06, ART-AVATAR-08)

| Truth | Status | Evidence |
|-------|--------|----------|
| ICY-disabled YT station with stored avatar shows circular-cropped avatar in cover slot; thumbnail shows first then swaps (D-05, D-09) | VERIFIED | now_playing_panel.py:932 calls `_show_station_logo_in_cover_slot()` first; L936 resets `_last_avatar_path = None`; L937 conditional swap; `test_avatar_bind_station_icy_disabled_with_avatar_sets_last_avatar_path` — PASSED |
| Circular crop is center-cropped, antialiased, borderless, sized to the current art tier (D-06) | VERIFIED | `_make_circular_pixmap` at now_playing_panel.py:219 uses `QPainterPath.addEllipse` + `RenderHint.Antialiasing`; `test_avatar_make_circular_pixmap_produces_opaque_center_transparent_corners` — PASSED (automated). Visual quality: HUMAN NEEDED (D-07) |
| On panel resize the circular avatar re-renders at the new tier (does not revert to thumbnail) | VERIFIED | `elif self._last_avatar_path is not None:` at now_playing_panel.py:2122; `test_avatar_apply_art_tier_replays_circle` — PASSED |
| When no avatar is stored or the PNG fails to load, the slot stays on the station thumbnail (D-08) | VERIFIED | `QPixmap.isNull()` guard at L2213 clears `_last_avatar_path = None` then calls `_show_station_logo_in_cover_slot()`; `test_set_avatar_pixmap_from_path_null_png_clears_last_avatar_path` — PASSED |
| Cached avatar load from station-bind completes well under 1 second | VERIFIED | `test_set_avatar_pixmap_from_path_cached_load_under_1s` asserts `elapsed < 1.0` — PASSED |

#### Plan 89-05 (ART-AVATAR-05)

| Truth | Status | Evidence |
|-------|--------|----------|
| Pasting/editing a YouTube URL auto-fetches the avatar on the 500ms debounce (D-01) | VERIFIED | `_on_url_timer_timeout` at edit_station_dialog.py:~L1288 increments `_avatar_fetch_token` and starts `_AvatarFetchWorker`; `test_debounce_launches_avatar_worker_on_yt_url` — PASSED |
| "Refresh avatar" button present and enabled only for avatar-capable (YouTube) URLs (D-04, D-10) | VERIFIED | `_refresh_avatar_btn` at L474; gating via inline `youtube.com`/`youtu.be` check at L1256; `test_refresh_avatar_btn_enabled_for_youtube_url`, `test_refresh_avatar_btn_disabled_for_non_yt_url` — PASSED |
| Avatar fetch runs on a worker thread and marshals result to main thread via queued Signal (D-02) | VERIFIED | `class _AvatarFetchWorker(QThread)` at L134; `finished = Signal(str, int)`; `run()` never touches widgets; `_on_avatar_fetched` slot on main thread; `test_avatar_fetch_worker_emit_shape` — PASSED |
| On fetch failure Save is still allowed; old cached avatar kept; inline message shown (D-03, D-11) | VERIFIED | `_on_avatar_fetched` at L1420: empty `rel_path` branch sets status text, does NOT call `update_channel_avatar_path`; `test_on_avatar_fetched_failure_non_blocking` — PASSED |
| Stale (superseded) avatar fetch result is discarded via monotonic token | VERIFIED | `_avatar_fetch_token` at L368; stale-token guard at L1432; `test_on_avatar_fetched_stale_token_discarded` — PASSED |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/models.py` | `channel_avatar_path` field on Station | VERIFIED | L43: `channel_avatar_path: Optional[str] = None  # Phase 89 D-13` |
| `musicstreamer/repo.py` | 4 mappers + `update_channel_avatar_path` write method | VERIFIED | 4 mapper wirings confirmed; `def update_channel_avatar_path` at L850 |
| `musicstreamer/assets.py` | Atomic avatar PNG writer | VERIFIED | `def write_channel_avatar` at L32; `tempfile.mkstemp` + `os.replace` |
| `musicstreamer/yt_import.py` | `fetch_channel_avatar` + per-provider registry | VERIFIED | `def fetch_channel_avatar` at L155; `_AVATAR_FETCHERS` + `register_avatar_fetcher("youtube", ...)` at L261 |
| `musicstreamer/cover_art.py` | Named precedence wrappers for drift-guard | VERIFIED | `def _mb_caa_lookup` at L148; `def _channel_avatar_lookup` at L159 |
| `musicstreamer/ui_qt/now_playing_panel.py` | Circular-avatar render path + `_last_avatar_path` tier-replay + bind-time load | VERIFIED | `_make_circular_pixmap` at L219; `_set_avatar_pixmap_from_path` at L2198; `_last_avatar_path` at L347; `elif` at L2122 |
| `musicstreamer/ui_qt/edit_station_dialog.py` | Avatar preview row, `_AvatarFetchWorker`, debounce + refresh wiring, YT gating | VERIFIED | `class _AvatarFetchWorker` at L134; `_refresh_avatar_btn` at L474; `_avatar_fetch_token` at L368; `_on_avatar_fetched` at L1420 |
| `tests/test_repo.py` | Round-trip + clear + no-reset tests | VERIFIED | 7 new Phase 89 tests; 98 total passed |
| `tests/test_assets_avatar.py` | Atomic write, overwrite, cleanup tests | VERIFIED | 3 tests; all PASSED |
| `tests/test_yt_import_library.py` | 10 avatar tests (filter + registry) | VERIFIED | All 10 PASSED |
| `tests/test_cover_art_avatar.py` | Source-grep precedence drift-guard + field-filter tests | VERIFIED | `test_mb_caa_runs_before_channel_avatar` + 8 others; all PASSED |
| `tests/test_constants_drift.py` | Phase 89 RichText parity guard | VERIFIED | `test_richtext_baseline_unchanged_by_phase_89` — PASSED |
| `tests/test_now_playing_panel.py` | 9 avatar render + timing tests | VERIFIED | All 9 PASSED including `elapsed < 1.0` |
| `tests/test_edit_station_dialog.py` | 12 avatar dialog tests | VERIFIED | All 12 PASSED |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `repo.py` | `stations.channel_avatar_path` column | `UPDATE` + row mapper | VERIFIED | 4 mapper reads + 1 dedicated write; `update_station` body is clean |
| `assets.py` | `paths.channel_avatars_dir()` | `tempfile.mkstemp + os.replace` | VERIFIED | `os.replace` at L49; same-filesystem atomicity guaranteed |
| `yt_import.py fetch_channel_avatar` | yt-dlp channel thumbnails `avatar_uncropped` | `extract_info(download=False)` without `extract_flat` | VERIFIED | `extract_flat` absent from avatar opts; `avatar_uncropped` filter at L216 |
| `yt_import.py register_avatar_fetcher` | `_AVATAR_FETCHERS` registry | Module-load registration | VERIFIED | `register_avatar_fetcher("youtube", fetch_channel_avatar)` at L261 |
| `cover_art.py fetch_cover_art` | `_mb_caa_lookup` | Replaces inline `_cover_art_mb.fetch_mb_cover` call | VERIFIED | Both dispatch sites (L240, L267) use `_mb_caa_lookup`; no bare inline calls remain |
| `tests/test_cover_art_avatar.py` | `cover_art.py` source order | `src.find` positions; `mb_pos < avatar_pos` | VERIFIED | Assertion at test_cover_art_avatar.py:34 — PASSED |
| `now_playing_panel.bind_station` | `_set_avatar_pixmap_from_path` | `icy_disabled and station.channel_avatar_path` | VERIFIED | L937 conditional gate confirmed |
| `now_playing_panel._apply_art_tier` | `_last_avatar_path` | `elif` branch between real-cover and station-logo fallback | VERIFIED | `elif self._last_avatar_path is not None:` at L2122, in correct position |
| `edit_station_dialog._on_url_timer_timeout` | `_AvatarFetchWorker` | YouTube-URL gate on 500ms debounce | VERIFIED | `_avatar_fetch_token += 1` and worker start at L1288–1297 |
| `_AvatarFetchWorker.run` | `fetch_channel_avatar + write_channel_avatar + update_channel_avatar_path` | Worker fetch → atomic write → queued Signal → main-thread persist | VERIFIED | L164 calls `fetch_channel_avatar`; L165 calls `write_channel_avatar`; `update_channel_avatar_path` called in `_on_avatar_fetched` at L1450 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `now_playing_panel._set_avatar_pixmap_from_path` | `pix = QPixmap(abs_path)` | `os.path.join(paths.data_dir(), rel_path)` → disk PNG | Yes — reads from real filesystem path written by `write_channel_avatar` | FLOWING |
| `edit_station_dialog._on_avatar_fetched` | `rel_path` from `_AvatarFetchWorker.finished` | `yt_import.fetch_channel_avatar` → `assets.write_channel_avatar` → Signal | Yes — network bytes persisted atomically; path emitted | FLOWING |
| `repo.update_channel_avatar_path` | `channel_avatar_path` column | `UPDATE stations SET channel_avatar_path = ?` | Yes — real SQLite write via `Repo.con` | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `test_mb_caa_runs_before_channel_avatar` passes | `.venv/bin/python -m pytest tests/test_cover_art_avatar.py::test_mb_caa_runs_before_channel_avatar -x` | PASSED | PASS |
| `test_richtext_baseline_unchanged_by_phase_89` passes | `.venv/bin/python -m pytest tests/test_constants_drift.py::test_richtext_baseline_unchanged_by_phase_89 -x` | PASSED | PASS |
| `elapsed < 1.0` timing assertion (ART-AVATAR-08) | `.venv/bin/python -m pytest tests/test_now_playing_panel.py -k "cached_load_under_1s"` | PASSED | PASS |
| Full scoped suite (excluding known pre-existing failure) | `.venv/bin/python -m pytest tests/test_repo.py tests/test_assets_avatar.py tests/test_yt_import_library.py tests/test_cover_art.py tests/test_cover_art_avatar.py tests/test_constants_drift.py tests/test_now_playing_panel.py tests/test_edit_station_dialog.py tests/test_paths.py --deselect tests/test_constants_drift.py::test_soma_nn_requirements_registered` | 413 passed, 1 deselected | PASS |
| D-05 anti-regression: `_set_cover_pixmap` unchanged | `grep -n "def _set_cover_pixmap" now_playing_panel.py` → L2181 (present, body unaltered) | Present; body contains original Phase 72.3 logic | PASS |
| D-05 anti-regression: `_show_station_logo_in_cover_slot` unchanged | `grep -n "def _show_station_logo_in_cover_slot" now_playing_panel.py` → L2260 (present) | Present; body contains original Phase 72.3 logic | PASS |

---

### Probe Execution

No `probe-*.sh` scripts declared or found for Phase 89. Step 7c: SKIPPED.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ART-AVATAR-03 | 89-02 | `fetch_channel_avatar` with `avatar_uncropped` filter, rejects non-square | SATISFIED | `def fetch_channel_avatar` at yt_import.py:155; 10 tests PASSED; REQUIREMENTS.md checkbox [x] |
| ART-AVATAR-05 | 89-01, 89-05 | Avatar auto-fetches in EditStationDialog + Refresh button | SATISFIED | `_AvatarFetchWorker` + debounce + Refresh button; 12 tests PASSED; REQUIREMENTS.md checkbox [x] |
| ART-AVATAR-06 | 89-04 | ICY-disabled YT station shows circular avatar in cover slot | SATISFIED | `bind_station` conditional at now_playing_panel.py:937; 9 tests PASSED; REQUIREMENTS.md checkbox [ ] — documentation not updated post-Phase 89 (WARNING: see below) |
| ART-AVATAR-07 | 89-03 | Cover-resolver precedence: ICY → iTunes → MB-CAA → channel-avatar → placeholder | SATISFIED | `_mb_caa_lookup` before `_channel_avatar_lookup` in source; drift-guard PASSED; REQUIREMENTS.md checkbox [x] |
| ART-AVATAR-08 | 89-04 | Avatar load < 1s cached; reverts to thumbnail on failure | SATISFIED | `elapsed < 1.0` timing test PASSED; null-PNG fallback test PASSED; REQUIREMENTS.md checkbox [ ] — documentation not updated post-Phase 89 (WARNING: see below) |
| ART-AVATAR-09 | 89-03 | Source-grep drift-guard `test_mb_caa_runs_before_channel_avatar` | SATISFIED | PASSED; REQUIREMENTS.md checkbox [x] |
| ART-AVATAR-10 | 89-03 | Phase 71 RichText parity preserved via `test_richtext_baseline_unchanged_by_phase_89` | SATISFIED | PASSED; REQUIREMENTS.md checkbox [x] |

**Orphaned requirements check:** No phase 89 requirements found in REQUIREMENTS.md that are not claimed by a plan.

**REQUIREMENTS.md documentation discrepancy (WARNING, not BLOCKER):** ART-AVATAR-06 and ART-AVATAR-08 are shown as `[ ]` (unchecked) in the requirement body and as `Pending` in the traceability table. The implementation is fully present and tested in the codebase. This is a documentation update that was not applied after Phase 89 completed. The traceability table notes `Phase 89 | Pending` for both — these should be flipped to `Complete` and the requirement body checkboxes should be set to `[x]`. This does not block the phase goal; it is a tracking hygiene issue.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | — |

No TBD/FIXME/XXX debt markers found in any Phase 89 modified files. No unreferenced stubs or empty implementations detected.

**Note on `_channel_avatar_lookup` not wired into `fetch_cover_art` auto dispatch:** This is intentional (documented in RESEARCH.md Q2 RESOLVED and confirmed in the 89-03 SUMMARY). The function is a synchronous stub positioned for the ART-AVATAR-09 precedence drift-guard. The live ICY-disabled trigger fires from `bind_station` in `now_playing_panel.py`, not through `fetch_cover_art`. This is design, not a stub.

---

### Human Verification Required

#### 1. Circular-crop visual quality (D-06/D-07)

**Test:** Bind a real ICY-disabled YouTube station (e.g., Lofi Girl) that has a stored channel avatar. Observe the cover slot in the Now Playing panel at multiple panel sizes.
**Expected:** Station thumbnail appears first, then swaps to a clean antialiased circular-cropped channel avatar. No border ring. Avatar is centered, not offset. Resize the panel to trigger tier-replay and confirm the circular crop re-renders at the new size.
**Why human:** `_make_circular_pixmap` uses `QPainter` antialiasing and center-crop, but visual balance and aesthetic quality (D-07 "circular-crop visual balance") are subjective and cannot be adequately asserted by headless pixel inspection.

#### 2. Live avatar fetch roundtrip in EditStationDialog

**Test:** Open EditStationDialog for a new station or an existing YouTube station. Paste or type a YouTube channel URL (e.g., `https://www.youtube.com/@lofigirl`). Wait for the debounce.
**Expected:** `_avatar_status` label changes to "Fetching avatar…", then "Avatar found". The 64×64 preview populates with the channel avatar. The avatar persists across dialog close/re-open (database write confirmed).
**Why human:** Live YouTube network fetch via yt-dlp — tests mock `fetch_channel_avatar`; the real YouTube CDN response and actual cookie handling cannot be verified without live network.

#### 3. Cached load after initial fetch (persistence + re-open)

**Test:** After completing test 2, close EditStationDialog. Re-open it for the same station.
**Expected:** The avatar preview is already populated from the cached PNG on disk (no new fetch); the column `channel_avatar_path` in the SQLite DB shows a non-null relative path.
**Why human:** Requires live SQLite state and filesystem state across a dialog lifecycle; not feasible to replicate reliably in the test harness without a full integration environment.

---

### Gaps Summary

No gaps. All 7 requirement IDs (ART-AVATAR-03, 05, 06, 07, 08, 09, 10) are fully implemented and tested. The only outstanding item is documentation hygiene in REQUIREMENTS.md (ART-AVATAR-06 and ART-AVATAR-08 checkboxes not updated to `[x]` / traceability not flipped to `Complete`) — this does not block the phase goal.

The pre-existing failure `tests/test_constants_drift.py::test_soma_nn_requirements_registered` is a Phase 74 SOMA drift-guard confirmed out-of-scope for Phase 89 (SOMA-01 was absent from REQUIREMENTS.md before Phase 89 and is unchanged by it).

---

_Verified: 2026-06-16T16:24:17Z_
_Verifier: Claude (gsd-verifier)_
