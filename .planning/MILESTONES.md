# Milestones

## v2.1 Fixes and Tweaks (Shipped: 2026-05-25)

**Phases completed:** 42 phases, 187 plans, 249 tasks

**Key accomplishments:**

- Wired StationListPanel.refresh_recent() into MainWindow._on_station_activated so the Recently Played list updates the moment a station is clicked — provider tree expand/collapse state preserved.
- Pure helper find_aa_siblings() that derives AA siblings from channel_key on-demand — no DB schema change, no Qt coupling, 12 unit tests pinning the cross-network contract.
- Snapshot-and-compare `_is_dirty()` predicate added to `EditStationDialog`, enabling Plan 51-04 to gate sibling-link clicks with a Save / Discard / Cancel confirm.
- Visible "Also on: ZenRadio • JazzRadio" RichText QLabel added to `EditStationDialog`, hidden when non-AA or no siblings, rendering hooked from `_populate` after the dirty-state baseline.
- Setup:
- 40ms 8-tick QTimer-driven dB-linear gain ramp on Player.set_eq_enabled — eliminates the IIR-coefficient-discontinuity click on EQ toggle while preserving graceful-degrade and the existing profile-load path
- Added `test_eq_toggle_fires_exactly_once_per_click` regression guard that locks SC #3 by asserting exact call-count delta (1 per click) on `FakePlayer.calls` — defends against future accidental double-wiring of `clicked` + `toggled` signals or programmatic `.click()` insertion in the toggle path.
- 1. [Rule 1 - Bug] Fixed bound method identity check in test_import_launches_cookie_dialog
- 1. [Rule 2 - Docstring CookieImportDialog ref] Removed CookieImportDialog name from _open_accounts_dialog docstring
- Two synthetic-pixmap pytest tests lock load_station_icon's existing aspect-preserving behavior (portrait 1:2 -> 16x32 pillarbox; landscape 2:1 -> 32x16 letterbox) without modifying any production code.
- Phase:
- Date:
- Date:
- StationListPanel.refresh_model() now preserves user-set per-provider expand/collapse state via a capture-then-restore pair keyed on raw provider-name strings — closing BUG-06 across all five _refresh_station_list() callers without changing a single call site.
- 8 pytest-qt tests appended to tests/test_station_list_panel.py that lock the entire BUG-06 contract — 5 behavioral assertions (SC #1, SC #2, D-04, D-06, D-07), 1 defensive guard (Pitfall #2 / filtered-out provider), and 2 Nyquist spy locks (D-03 negative + D-05 positive on _sync_tree_expansion).
- Pure helper `aa_normalize_stream_url(url)` rewrites DI.fm `https://` URLs to `http://` at the URL boundary, with 8 idempotency / passthrough unit tests guarding the predicate against future broadening.
- `aa_normalize_stream_url` is now wired into `Player._set_uri` as a single-funnel URI transform at the playbin3 boundary, with 3 player-level integration tests guarding the wire (Pitfall #1: tests assert on the underlying `_pipeline.set_property` MagicMock without mocking `_set_uri` itself).
- Diagnose-first surfaced the truth: the AUMID wiring was never broken — the bug was launch-discipline. Plan 04 ships docs + a drift-guard, no production code change.
- Smallest correct change for WIN-02: a 28-line README note + a 31-line drift-guard pytest. No production code change. The wiring was never broken — just under-documented and under-guarded.
- Both halves of Phase 56 attested PASS on a release-grade install. WIN-01 helper engages on stored https://di.fm rows at the play-time URI boundary as D-01 specifies; WIN-02 SMTC overlay reads "MusicStreamer" via the Start Menu launch path. Phase ready to ship.
- Replaced implicit `MagicMock` with `AsyncMock` for `DataWriter().store_async` in `tests/test_media_keys_smtc.py::_build_winrt_stubs` so `await writer.store_async()` resolves cleanly; production `smtc.py` untouched (D-10).
- Headline:
- One-liner:
- QTimer-driven 8-tick fade-down of playbin3.volume (self._volume -> 0) in pause(), with final tick performing set_state(NULL), and 3 structural guard tests locking ramp arming + target-zero + self._volume immutability.
- All four ROADMAP success criteria attested PASS. Phase 57 closes the WIN-03 (audible-glitch + volume-slider on Windows, plus the cross-platform buffer-drop auto-rebuffer surface from the in-session disclosure) and WIN-04 (AsyncMock test) requirements. Ready to ship.
- _resolve_pls refactored from inline re.match PLS parser to thin wrapper around playlist_parser.parse_playlist (D-10), preserving list[str] contract and [pls_url] fallback for both call sites
- New class: `_PlaylistFetchWorker(QThread)` (lines 126-186)
- TDD-RED contract for the QColorDialog-based AccentColorDialog rewrite: 9 tests targeting self._inner + self._current_hex, all FAILING against today's implementation by design.
- Rewrote AccentColorDialog as a wrapper QDialog hosting an embedded QColorDialog (NoButtons | DontUseNativeDialog) — full HSV wheel + sat/val square + R/G/B/H/S/V fields + hex field + screen-color eyedropper — with 8 ACCENT_PRESETS seeded into Custom Colors slots 0..7. Phase 19/40 snapshot/restore invariant preserved verbatim; public API unchanged so main_window.py is untouched.
- 17 live-captured and hand-crafted gbs.fm fixture files plus pytest shared fixtures (mock_gbs_api, fake_repo, fake_cookies_jar) pinning the test-data contract before any production gbs_api.py code ships
- Pure-urllib GBS.FM HTTP client with 6-tier static stream variants, FLAC 1411 kbps sentinel, Django session cookie auth, /ajax event-stream parser, HTML search parser, Django messages cookie decoder, typed exceptions, and 18 passing tests
- 'Add GBS.FM' hamburger menu entry wired to gbs_api.import_station via _GbsImportWorker QThread with idempotent insert/update toasts, auth-expired reconnect prompt, and 8 passing pytest-qt tests
- AccountsDialog GBS.FM QGroupBox (D-04c) with Connect/Disconnect flow, and CookieImportDialog refactored to accept per-instance provider config via keyword-only kwargs (target_label/cookies_path/validator/oauth_mode)
- GBS.FM active-playlist QListWidget added to NowPlayingPanel: 15s poll timer, _GbsPollWorker QThread with stale-token guard, auth-gated hide-when-not-GBS contract, HIGH 4 position-cursor reset on track change, and 9 passing pytest-qt tests
- GBS.FM vote control added to NowPlayingPanel: 5 checkable QPushButton widgets with optimistic UI, _GbsVoteWorker QThread round-trip, server-truth confirmation (Pitfall 2), _gbs_current_entryid stamped only from /ajax (Pitfall 1), and 10 passing pytest-qt tests
- GBSSearchDialog (D-08) with worker-thread search + per-row submit, full D-08c login gate, inline errors for duplicate/quota (D-08d), Prev/Next pagination (D-08e), and HIGH 5 stale-submit discard via monotonic search_version token
- One-liner:
- Vote buttons disabled at construction via setEnabled(False), re-enabled by _on_gbs_playlist_ready once entryid is known; cookies-None guard in _on_gbs_vote_clicked now emits gbs_vote_error_toast before rolling back (T10 + T11 closed)
- One-liner:
- One-liner:
- Multi-word foo+fighters search response captured (17.5 KB valid HTML), 6 RED parser tests authored against tests/test_gbs_api.py, and 7 RED dialog tests authored against tests/test_gbs_search_dialog.py — Phase 60.1 contracts pinned end-to-end before any production code is written.
- Two new HTMLParser subclasses (`_ArtistPageParser`, `_AlbumPageParser`) plus two top-level fetch helpers (`fetch_artist_songs`, `fetch_album_songs`) added to `musicstreamer/gbs_api.py`. All 6 RED parser tests from Plan 01 turn GREEN. D-04 multi-word triage closed as Hypothesis 1 REFUTED + documented (no parser change needed). Pitfall 7 stale `_SongRowParser` docstring corrected. `tests/test_gbs_api.py` is fully GREEN at 35/35 passing.
- Two new worker classes, two new widgets, three new dialog instance attributes, five new dialog slots, three new helpers, two click handlers rewritten, two render-path methods refactored with `clear_panels` kwarg, two module-level regexes for URL-injection defense — all landed in two atomic commits. The two D-07 Shape-4 tests were deleted in the same commit as the dialog GREEN per CONTEXT.md D-07. All seven Plan 01 RED dialog tests turn GREEN. UI-SPEC Layout Deltas 1-5 + Interaction States + Copywriting Contract are observable in tests. Pitfalls 8, 9, 10 all have permanent regression guards.
- Manual UAT executed end-to-end on Linux Wayland with real GBS.FM cookies. SC2/SC3/SC4 PASS, UI-SPEC Layout Deltas 1-5 and Pitfalls 8/9/10 all verified live; SC1 FAILS on the specific multi-word query `bad religion` (Issue A reproduces partially) and a new UI defect surfaced (artist drill-down flat-list rendering).
- Captured 5 GBS.FM /search fixtures, identified singular-vs-plural discriminator-text bug as root cause of bad-religion zero-panel response (H2 confirmed → D-06 routing), and pinned 9 RED tests (5 parametrize entries + 2 standalone parser + 4 dialog) for Wave 1/2 fix.
- Shipped both parser-tier obligations: (1) `_ArtistPageParser` now carries album state across rows and emits a per-row `"album"` field; (2) `_ArtistAlbumParser` discriminator gate relaxed to accept singular-form panel labels per TRIAGE D-06 — bad-religion + 4 probe fixtures all turn GREEN.
- Shipped both dialog-tier obligations: (1) `_render_results(group_by_album=True)` branch + 3 helpers (`_group_rows_by_album`, `_insert_album_section_header`, `_render_song_rows`) that insert span-row section headers between album groups in the artist drill-down view; (2) `_clear_table` defense-in-depth `clearSpans()` BEFORE `removeRows` ordering. All 6 Plan 01 dialog RED tests now GREEN; QA-05 invariant + Phase 60.1 7-test drill regression set preserved.
- Manual UAT executed end-to-end on Linux Wayland with real GBS.FM cookies. SC1/SC2/SC3/SC4 all PASS, Phase 60.1 UI-SPEC + Pitfalls 8/9/10 still binding, Phase 60.2's new UI-SPEC Layout Deltas (album-section-header rendering, Pitfalls 1/3/5/6/9 mitigations) all verified live.
- Tri-state `_gbs_label_source` flag and `_gbs_poll_in_flight()` predicate added to NowPlayingPanel as pure additive scaffolding; zero behaviour change shipped, contract pinned by 3 new tests for Plans 02/03 to layer onto.
- `_apply_gbs_icy_label` helper added to `NowPlayingPanel` and invoked from `_on_gbs_playlist_ready`; bound + logged-in GBS.FM stations now upgrade `icy_label` from bare ICY title to canonical `Artist - Title` once /ajax responds (D-01/D-06/D-07 closed; Open Question 1 locked).
- `on_title_changed` rewritten with no-downgrade guard (D-05), bridge-window cover-art suppression (D-07), post-write `_gbs_label_source = 'icy'` flip, and idle-worker kick (D-03/D-04); `_update_star_enabled` extended with bridge-window star-disable (D-07); `_on_gbs_playlist_error` auth_expired branch flips flag to 'icy' (D-08) — all eight CONTEXT decisions D-01..D-08 now implemented.
- Closes CR-01 and Verification Gap 1: split the D-03 kick out of the D-05 no-downgrade early-return so a stale 'ajax' flag from a prior track does not block the kick on a server-side track change; reset `_gbs_label_source = None` in the `if track_changed:` branch of `_on_gbs_playlist_ready` so the next ICY tag for the new track is treated as a fresh write. Combined fix (option (b) + option (c) from REVIEW.md) closes both halves of the gap with a minimal diff.
- Closes CR-02, WR-02, IN-01, and Verification Gap 2: introduce a panel-local `_gbs_ajax_disabled` boolean that distinguishes 'cookies-on-disk' (Phase 60 D-04 invariant) from '/ajax-is-impossible' (auth_expired received). Both bridge predicates (`_update_star_enabled` and `on_title_changed`'s `in_bridge_window`) gain a `not self._gbs_ajax_disabled` conjunct so star + cover-art come alive when /ajax dies mid-runtime — exactly the D-08 contract. Asymmetric lifecycle resets (bind_station + leaving-GBS clear; same-station re-entry preserves) close WR-02. Test cleanup replaces the IN-01 apology comment with real assertions.
- Single shared `_refresh_star_display` helper extracted; star icon now reflects canonical /ajax-stamped Artist - Title (CR-03); test factory explicit `icy_disabled=False` default closes silent MagicMock-truthy coverage hole (CR-04); plus four defensive-consistency / docstring fixes — all 10 REVIEW findings + 2 VERIFICATION gaps now closed.
- One-liner:
- One-liner:
- Production code
- Six orphan agent worktrees
- Renamed the placeholder `org.example.MusicStreamer` to `org.lightningjim.MusicStreamer` everywhere it leaked, single-sourced the literal through `constants.APP_ID`, added `setApplicationDisplayName`, fixed 4 Makefile drift sites (including a phantom `.svg` reference and a wrong-bucket `scalable` -> `256x256` correction), relocated the bundled `.desktop` file to `packaging/linux/` via `git mv`, and shipped 4 drift-guard tests that make silent rename-drift impossible.
- Initial hypothesis (env-inheritance, partial truth):
- Locked the Phase 62 / BUG-09 executable contract — 20 RED tests across 3 new files plus 1 fixture extension — encoding D-01..D-09, T-62-01 log-injection mitigation, T-62-02 force-close-before-bind ordering, and qt-glib-bus-threading Pitfalls 1/2/3/5 as machine-checkable assertions before any production code is written
- Pure-Python `_BufferUnderrunTracker` cycle state machine + frozen `_CycleClose` dataclass + module-level `_log` logger landed in `musicstreamer/player.py`; turns the Wave 0 / Plan 00 contract for the tracker tier from RED → GREEN (7/7) without touching the Player class body or the D-09 Phase 16 buffer constants
- Wave 1 GREEN Part 2 of 2: 12 insertion sites in `musicstreamer/player.py` (3 Signals + dwell QTimer + tracker instance + _current_station_id + 2 queued connects + play() station_id capture + play_stream() symmetric clear (W2) + pause()/stop() force-closes + _try_next_stream force_close-before-bind_url + _on_gst_error tracker hook + _on_gst_buffering observe-and-branch + 3 main-thread slots + shutdown_underrun_tracker public method) — all 8 RED integration tests in `tests/test_player_underrun.py` turned GREEN with zero regression in the 7-test tracker suite or the 80 pre-existing Player + MainWindow integration tests, T-62-01 and T-62-02 STRIDE mitigations live, D-09 invariant preserved
- Wave 2 GREEN closure for Phase 62 — wired MainWindow to consume Player.underrun_recovery_started with a 10s time.monotonic() cooldown gate, hooked Player.shutdown_underrun_tracker() into closeEvent BEFORE _media_keys.shutdown (Pitfall 4 ordering), and added per-logger INFO level for musicstreamer.player in __main__.py (Pitfall 5 — scoped, NOT global). All 5 RED MainWindow integration tests authored in Plan 00 now GREEN; 20/20 Phase 62 RED tests across the three new test files now GREEN; D-05 invariant (now_playing_panel.py 0-line diff) and D-09 invariant (constants.py 0-line diff) both preserved
- `tools/bump_version.py`
- `tools/bump_version.py` — new helper + gate (15 lines added):
- `.claude/hooks/bump-version-hook.sh`
- `.claude/hooks/bump-rollback-hook.sh`
- No Rule 1/2/3 auto-fixes were needed during implementation.
- Promoted Phase 51's private `EditStationDialog._render_sibling_html` to a shared free function `render_sibling_html` in `musicstreamer/url_helpers.py` so Plan 02's NowPlayingPanel can consume the same renderer; preserved html.escape mitigation and integer-only sibling://{id} href format verbatim.
- NowPlayingPanel exposes sibling_activated = Signal(object), renders the cross-network 'Also on:' line for AA stations with siblings via the shared render_sibling_html, hides cleanly otherwise, and locks the D-04 single-call-site invariant + SC #4 single-source-of-AA-detection invariant with negative-spy tests.
- MainWindow connects NowPlayingPanel.sibling_activated to a one-line delegating slot that routes through _on_station_activated, and an end-to-end integration test asserts Player.play(sibling) + Repo.update_last_played(sibling.id) fire on panel-side sibling click — closing BUG-02 by inverting Phase 51's no-playback-change semantics for the panel-flow.
- Runtime version-read path wired: `app.setApplicationVersion(_pkg_version('musicstreamer'))` in `_run_gui` plus disabled `v{version}` footer at the bottom of the hamburger menu, both sourced from `importlib.metadata` against `pyproject.toml [project].version`.
- Three-line PyInstaller spec edit (import extension + _ms_datas assignment + datas concat) plus 4-test source-text regression-lock (tests/test_packaging_spec.py) that closes the bundle promise — importlib.metadata.version("musicstreamer") will now resolve inside the bundled Windows exe.
- Single-file deletion (`git rm musicstreamer/__version__.py`) plus pre- and post-deletion D-06a grep gate runs (both GREP_GATE_OK) and plan-level pytest suite GREEN (56/56) — closes the Phase 65 single-source-of-truth promise. `pyproject.toml [project].version` is now the only literal version write site in the repo; everywhere else reads via `importlib.metadata.version("musicstreamer")`.
- One-liner:
- Positive
- `musicstreamer.theme` module with 7 presets (system / vaporwave / overrun / gbs / gbs_after_dark / dark / light), startup wiring in `_run_gui`, and THEME-01 requirement registered.
- ThemePickerDialog ships as a modal QDialog with a 4x2 tile grid (8 tiles in DISPLAY_ORDER), tile-click live preview, Apply-persist, Cancel-restore-snapshot, and a Customize... button that lazy-imports the (stubbed) Plan 03 editor.
- ThemeEditorDialog ships as a modal QDialog with 9 single-column color rows (one per editable QPalette role; Highlight excluded per D-08), per-row QColorDialog launchers, live-preview + accent re-imposition, snapshot-restore-on-Cancel, Reset-stays-open with source-preset reversion, and Save-persists-theme_custom-JSON + flips parent picker flags + accepts. Plan 02's 8-LOC stub at `musicstreamer/ui_qt/theme_editor_dialog.py` has been OVERWRITTEN with the 314-LOC full implementation.
- Wires the new "Theme" hamburger menu action to ThemePickerDialog (Plan 02) above the existing "Accent Color" entry, completes the Phase 66 ROADMAP entry, and auto-approves the manual UAT checkpoint under --chain — closing the Phase 66 wave-3 deliverable.
- 42 failing tests across 3 files lock the complete Phase 67 contract: pick_similar_stations/render_similar_html pure helpers (SIM-04/05/09), NowPlayingPanel.similar_activated + cache + collapse (SIM-02/03/06/07/08/10/11/12), and MainWindow._act_show_similar + QA-05 structural lambda-grep (SIM-01/02/08/QA-05)
- 1. [Rule 3 - Blocking] Created test file from Plan 01 dependency
- 1. [Rule 1 - Bug] Used isHidden() instead of isVisible() for collapse toggle
- 1. [Rule 3 - Blocking] Tasks 1+2 committed atomically (mirrors Plan 03 deviation #3)
- Found during:
- One-liner:
- 1. [Rule 1 - Bug] Fixed isVisible() headless assertion in 2 Plan 01 tests
- Live-only filter proxy predicate and 'Live now' chip wired into StationFilterProxyModel and StationListPanel, turning all 10 Phase 68 Plan 01 RED tests GREEN (7 proxy + 3 chip)
- AA poll lifecycle fully wired into MainWindow: startup, toast routing, B-02 fan-out, B-04 reactive dialog hooks, and closeEvent shutdown — turning all 6 Phase 68 RED integration tests GREEN
- Single-source-of-truth Python plugin guard (tools/check_bundle_plugins.py) wired into build.ps1 step 4b with exit code 10, conda recipe expanded with five explicit plugin packages including gst-libav, paired with two Linux-CI drift-guard pytests that lock README<->required-list parity and build.ps1<->exit-code-10 invocation parity.
- Win11 VM operator-driven UAT empirically proves AAC streams play on the post-fix installer — multiple DI.fm AAC tier + SomaFM HE-AAC streams confirmed working. New step 4b plugin-presence guard fired correctly during rebuild, validating the entire Phase 69 fix loop end-to-end.
- Locked the Phase 70 / HRES-01 executable contract — 11 RED test functions in 2 new files plus 29 RED functions appended to 8 existing modules — encoding D-01..D-05, DS-01..DS-05, T-01..T-06, and the full UI-SPEC copywriting + visibility contract as machine-checkable assertions before any production code is written
- `_FORMAT_BIT_DEPTH` dict (DS-02 mapping):
- order_streams sort key extended with -(sample_rate_hz or 0) / -(bit_depth or 0) tiebreak so FLAC-96/24 sorts above FLAC-44/16 within same codec rank (S-01), while lossless-over-lossy invariant (S-02) and GBS sentinel-bitrate regression remain intact.
- 1. [Rule 1 - Bug] Defensive tuple unpacking for `s.get_int("rate")`
- 1. [Rule 1 - Bug] Signal(dict) silently fails in PySide6 — changed to Signal(object)
- _quality_badge QLabel with Phase 68 LIVE QSS + _refresh_quality_badge slot + picker 'FLAC 1411 — HI-RES' format surfaced in NowPlayingPanel
- StationFilterProxyModel
- Landed the HRES-01 requirement row in REQUIREMENTS.md (Features, Traceability, coverage footer, Last-updated stamp) and replaced all Phase 70 ROADMAP.md placeholders with the locked goal prose, HRES-01 requirements citation, and full 12-plan checklist
- 1. [Rule 1 - Bug] Inverted dedup precedence on AA + manual sibling conflict
- Two-step picker QDialog (provider QComboBox → filtered station QListWidget) with outcome-named CTAs ('Link Station' / 'Don't Link') that excludes self + AA-auto-detected + already-manually-linked stations and persists the user's pick via Repo.add_sibling_link.
- Surfaced manual sibling links on NowPlaying's "Also on:" line by composing merge_siblings(find_aa_siblings(...), find_manual_siblings(...)) at the existing _refresh_siblings call site — zero widget changes, zero new HTML output paths.
- Routes `EditStationDialog.sibling_toast(str)` to `MainWindow.show_toast` at both EditStationDialog spawn sites (bound-method, QA-05), closing the user-feedback loop for every Phase 71 link/unlink action.
- ZIP export/import now carries sibling links by station NAME (per D-07 — survives ID renumbering across DBs) via a two-pass import: existing station-insert loop unchanged, second pass resolves names back to IDs from the live DB after all rows are inserted; old ZIPs missing the `siblings` key import cleanly.
- 1. [Rule 3 — blocking issue] REQUIREMENTS.md coverage rollup must update alongside SIB-01 row
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- LAYOUT-02 registered in REQUIREMENTS.md and 10-test TDD-RED scaffold landed at tests/test_phase72_1_stream_picker_reflow.py — 7 sample tests fail with AttributeError (Plan 02 will add panel.controls + panel._controls_row2), 3 invariant locks pass-by-accident as regression nets.
- Added resizeEvent + 4 reflow helpers to NowPlayingPanel; multi-stream picker now reparents between row 1 (Preferred 140px) and row 2 (Expanding fill) on width transitions, with idempotent insertWidget(snapshot_index, ...) row-1-return, threshold computed from row 1 + outer chrome, and isHidden()-gated D-02 single-stream early-return.
- Added 14-line extension hook to `_populate_stream_picker` (cache invalidation + multi→single re-home to row 1) + test-only show/waitExposed fix for the MainWindow-mounted compact-mode integration test; LAYOUT-02 production code is now complete and all 10 LAYOUT-02 sample/negative tests are GREEN.
- 1. [Rule 3 — Blocking issue] FakeRepo.list_streams missing
- None — plan executed exactly as written.
- Method replacement
- MANUAL UAT PENDING USER — `_controls_row3` construction + `_reflow_volume_cluster` predicate + `resizeEvent` three-call extension land LAYOUT-04; all 17 cluster-reflow tests GREEN; live 560px UAT on lower display deferred to /gsd-verify-work
- ART-MB requirement family registered + Station.cover_art_source dataclass field + idempotent SQLite migration (post-rebuild placement) + 6 MB JSON fixtures + 11 xfail-marked Wave 0 RED scaffolds pinning the `_spawn_worker` latest-wins seam for Plan 02.
- Self-contained MB+CAA worker module with 1-req/sec monotonic gate, Lucene-escaped recording search (T-73-01 mitigated), Official+Album release ladder, MB-tags-as-genre handoff, and a latest-wins single-spawn queue — all 10 Wave 0 RED scaffolds flipped to GREEN.
- Keyword-default rewrite:
- Per-station cover-art-source preference wired end-to-end via QComboBox in EditStationDialog, round-tripped through settings_export ZIP, and forwarded from NowPlayingPanel to the Plan 03 source-aware router.
- Three-scenario manual UAT script (73-UAT-SCRIPT.md) landed; the 16

automated ART-MB-NN tests are GREEN and the manual verification surface is
now staged for the user to run via `/gsd-verify-work 73`.

- One-liner:
- One-liner:
- One-liner:
- One-liner:
- 1. [Investigation] RED qtbot test passed unexpectedly against current code
- G-01 (SOMA-11 / UAT-07) — re-import toast suppressed by signal shadowing.
- Features section (THEME family):
- ToastOverlay now branches on `QApplication.property('theme_name')`: `system` (or unset) yields the IMMUTABLE legacy `rgba(40, 40, 40, 220)` + white QSS, every other theme yields palette-driven QSS interpolating ToolTipBase rgb (alpha 220) and ToolTipText.name(). A `changeEvent(QEvent.PaletteChange)` override (filter narrowed to PaletteChange ONLY as a recursion guard) retints live on theme flips.
- Test-surface coverage for the Phase 75 toast retint plumbing (PLAN-03) and theme.py 11-role foundation (PLAN-01) landed in two test files: 6 new toast tests + 1 rename gating the legacy QSS to theme='system'; 5 new theme tests + 1 rename for 11-role EDITABLE_ROLES coverage + 12 LOCKED ToolTipBase/ToolTipText hex pin assertions across 6 presets. All 45 tests (19 toast + 26 theme) pass.
- Added three tests to `tests/test_theme_picker_dialog.py`: two property-mirror locks for `QApplication.property('theme_name')` on vaporwave and system tile clicks (PLAN-04 mechanism), plus one end-to-end integration test that constructs a live `ToastOverlay` under a parent `QWidget`, clicks the vaporwave tile, flushes Qt's posted-events queue via `QApplication.sendPostedEvents()`, and asserts the toast's stylesheet contains `rgba(249, 214, 240, 220)` — locking the full Wave-1 + Wave-2 + Wave-3 retint chain (PLAN-01 `ToolTipBase` preset hex → PLAN-04 picker `setProperty` mirror → PLAN-03 toast `changeEvent(PaletteChange)` + `_rebuild_stylesheet`).
- `_GbsLoginWindow` (QWebEngine clone of `_TwitchCookieWindow`) + `--mode gbs` argparse arm + `_PROVIDER` module constant — refactored `_emit_event` so every event carries the correct provider, with the gbs.fm trigger gated on both `sessionid` AND `csrftoken` observed on `.gbs.fm`.
- 1. [Rule 3 - Blocking gate misalignment] Method-body acceptance grep windows tightened
- Migrations (2 tests):
- 1. [Rule 3 - Blocking] Used source-grep for name-parity check instead of Player.__dict__ introspection
- One-liner:
- Per-test unique D-Bus service name via conftest fixture eliminates the `registerService('org.mpris.MediaPlayer2.musicstreamer') failed: name already taken or bus error` cluster across all 8 LinuxMprisBackend tests
- Worktree venv missing `gi` module and `pytest-qt`
- One-liner:
- Full-suite verification revealed 6 of 6 planned clusters pass in per-cluster isolation; a new 7th-cluster MPRIS2 cross-file contamination (registerObject collision from MainWindow tests) was discovered and D-03-deferred; PROJECT.md Tests: line updated from stale "399 passing" to "1462 passing".
- Idempotent RotatingFileHandler on musicstreamer.player logger writing Phase 62 buffer_underrun INFO lines to ~/.local/share/musicstreamer/buffer-events.log, wired post-migration so DATA_DIR is guaranteed to exist; stderr parity preserved via propagate=True so the existing Pitfall-5 invariant holds byte-identical.
- Pre-existing — not caused by Phase 78 edits.
- No `gi` env-gap encountered for Plan 78-03 tests.
- Player now receives an absolute Node.js path from NodeRuntime and passes it to yt-dlp via yt_dlp_opts.build_js_runtimes — eliminating the .desktop-launch PATH-stripping bug for the YouTube playback path (BUG-11 player half).
- Source-grep drift-guard asserting both player.py and yt_import.py contain exactly one `build_js_runtimes(` call each — positive-form lock against re-introducing the inline `{"node": {"path": None}}` literal that is the BUG-11 root cause.
- Result:
- 1. [Rule 1 — Plan verification grep imprecision] Reworded `db_connect()` docstring to drop verbatim `PRAGMA foreign_keys = ON;` literal
- Pure-Python `pathlib.rglob` + `tokenize`-based source-grep gate asserting exactly one `sqlite3.connect(` callsite in the production tree, located in `musicstreamer/repo.py` — the static-analysis half of the D-09 defense-in-depth pair (Plan 80-01 owns the runtime half).
- One-liner:
- ALTER TABLE placement (Pitfall 2 mitigated):
- Exact line range of rewritten queue-build block in player.py:
- Exact line range of the 2-line insertion in now_playing_panel.py:
- 1. [Rule 1 - Bug] FakePlayer Signal parity drift-guard caught the new Signal
- Always-visible 'Buf duration' stats-for-nerds row with adaptive 'Ns (adapted)' label, driven by a bound-method DirectConnection wire from Player.buffer_duration_changed — 1:1 mirror of Phase 78 Commit A's Underruns row with always-visible D-12 override.
- Wrote the Phase 84 closure record documenting the WAIVED Phase 78 D-06 statistical gate, the 2-week post-ship monitor plan against the harvest-week baseline, and the three verbatim D-13 follow-up trigger thresholds. BUG-09 SC #3 (behavior side) CLOSES on the Phase 84 ship commit.

---

## v2.0 OS-Agnostic Revamp (Shipped: 2026-04-26)

**Phases completed:** 29 phases, 81 plans, 73 tasks

**Key accomplishments:**

- One-liner:
- One-liner:
- One-liner:
- KEEP_MPV.
- `musicstreamer/__main__.py`
- Completed:
- 1. [Rule 3 — Blocking issue] icons.qrc produced nested resource path `:/icons/icons/<name>.svg`
- 1. [Rule 3 — Blocking issue] Patched `PySide6.QtGui.QGuiApplication.styleHints` directly instead of the `musicstreamer.__main__` attribute path
- 1. [Rule 3 - Blocking] Test assertion `findChild(QFrame)` returned first QLabel
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- 1. [Rule 3 - Blocking] pytest-qt not installed in uv venv
- One-liner:
- 1. [Rule 1 - Bug] Actual yt_import/aa_import signatures differ from plan interfaces
- NowPlayingPanel additions:
- Task 1 — build_accent_qss + palette helpers
- One-liner:
- One-liner:
- One-liner:
- `musicstreamer/ui_qt/discovery_dialog.py`:
- Shared resolver (`musicstreamer/ui_qt/_art_paths.py`)
- +5 tests
- `musicstreamer/media_keys/` package scaffolded: abstract `MediaKeysBackend(QObject)` with D-02 signal+method surface, `NoOpMediaKeysBackend` fallback, `create()` platform factory, and Windows `smtc.py` stub — 9/9 pytest-qt tests passing
- `LinuxMprisBackend` implemented via PySide6.QtDBus with Root + Player MPRIS2 adaptors, cover-art PNG cache, and 11/12 pytest-qt tests passing — `playerctl` can target the service by name on any machine with a D-Bus session bus
- MainWindow wired to MediaKeysBackend via factory: title_changed bridges to publish_metadata, 4 state transitions call set_playback_state, closeEvent calls shutdown — 8/8 spy-backend tests passing
- Cleared MPRIS metadata on all five stop transitions and wired logging.basicConfig so media_keys warnings reach stderr
- 1. [Rule 1 - Bug] Fixed logo filename mismatch in test helper
- 1. [Rule 1 - Bug] Fixed replace warning visibility test — isVisible() vs isHidden()
- Renamed `_ImportCommitWorker.finished` → `commit_done` (and `error` → `commit_error`) so PySide6's C++ `QThread::finished` stops misrouting error-path thread exits through the success slot; added a real-filesystem chmod 0o444 regression test the previous monkeypatch test was blind to.
- Everything verbatim
- Completed:
- Completed:
- Renamed _art_cache.py cache subdir to media-art/ with module-sentinel migration helper, enabling shared cover-art path for MPRIS2 and SMTC backends
- [windows] optional-dep group declared in pyproject.toml, smtc.py deferred-import skeleton replacing NotImplementedError stub, and 4 Wave-0 unit tests confirming Linux importability and NoOp factory fallback
- WindowsMediaKeysBackend wired to SMTC via MediaPlayer conduit: button routing (play/pause/stop), state mapping (playing/paused/stopped->MediaPlaybackStatus), Pitfall #1 + #4 + T-43.1-04 mitigations, 14 unit tests green on Linux with mocked winrt
- 7 RED test scaffolds + 2 build-time guard tools land Wave 0 contracts (SERVER_NAME, NodeRuntime shape, "Node.js: Missing" QAction text, .spec hiddenimports list) so Plans 02–05 have a single feedback loop.
- QLocalServer-based single-instance helper with FlashWindowEx focus fallback, Node.js host-runtime detection with CPython #109590 Windows safety, and version 2.0.0 source-of-truth landed.
- 1. [Rule 1 - Bug] `runtime_check.show_missing_node_dialog` AttributeError under Plan 01 test fake
- Windows packaging pipeline lands: PyInstaller .spec + GStreamer runtime hook + PowerShell build driver (with Python-tool PKG-03 guard) + Inno Setup per-user installer + EULA + README + multi-resolution .ico, all wired to the AUMID `org.lightningjim.MusicStreamer` and the pinned AppId GUID `914e9cb6-f320-478a-a2c4-e104cd450c88`.
- QA-05 widget-lifetime audit clean (23 subclasses + 9 dialog launch sites + 13 signal connections + zero UAT-log regressions); 44-UAT.md template ready for Win11 VM execution with 16 pending checklist rows including the new UAT-21-1.5 AppId 3-brace acceptance check.
- Cache key parity.
- New `_theme.py` design-token module with ERROR_COLOR_HEX/QCOLOR + STATION_ICON_SIZE; 9 hex sites and all 3 icon-size sites migrated; `edit_station_dialog.py:131` deliberately deferred to Plan 46-02 Task 2 for Wave 1 parallel-execution disjointness
- Three-arg _LogoFetchWorker signal distinguishes AudioAddict-URL-but-no-key from generic unsupported URLs, a parented 3s auto-clear timer scrubs stale status, and a stack-balanced wait cursor covers the fetch window.
- Pure failover ordering module (`stream_ordering.py`) with `codec_rank` + `order_streams`, plus `StationStream.bitrate_kbps: int = 0` field — zero coupling to DB, Qt, or GStreamer, 18 tests green.
- Extended `station_streams` with `bitrate_kbps INTEGER NOT NULL DEFAULT 0` (CREATE TABLE + idempotent ALTER TABLE), widened `Repo.insert_stream` / `Repo.update_stream` / `Repo.list_streams` to carry it, and swapped `player.py::play`'s position-only sort for `order_streams(station.streams)` — failover now prioritizes (codec rank desc, bitrate desc).
- Wired `bitrate_kbps` end-to-end through the three user-facing surfaces: AudioAddict import (DI.fm tier -> 320/128/64 map), RadioBrowser discovery-save (post-insert update_stream fix-up), Edit Station dialog (5th column with QIntValidator delegate), and settings export/import roundtrip (8-column INSERT in both _insert_station and _replace_station with forward-compat defensive coerce).
- 1. [Rule 3 — Blocking] Updated 9 pre-existing `_resolve_pls` mock side_effects
- None.
- New Player.buffer_percent Signal(int) sourced from GStreamer message::buffering with defensive parse, sentinel de-dup, and per-stream reset — backend half of Phase 47.1 ready for UI wiring in plan 02.
- Live GStreamer buffer-fill percent surfaced in NowPlayingPanel as a mini QProgressBar + {N}% QLabel row inside a hidden-by-default QFormLayout wrapper, toggled via a new checkable hamburger-menu QAction with SQLite persistence, and wired end-to-end to Player.buffer_percent via a bound-method connect (no lambda).
- Write side
- Adds a right-aligned "+" QToolButton header row emitting `new_station_requested`, plus a `select_station(station_id)` helper that maps source-model indexes through `StationFilterProxyModel` before calling `setCurrentIndex`.
- Twitch OAuth token capture rebuilt on 127.0.0.1 loopback listener + self-contained HTML bounce page, replacing the broken urlChanged fragment capture with CSRF-validated POST /capture and structured JSON-line stderr diagnostics.
- One-liner:
- Date:
- Shared cookie_utils.py helper (is_cookie_file_corrupted + temp_cookies_copy @contextmanager) and 9 RED tests that drive FIX-02 restoration and corruption auto-recovery in Plans 02/03.
- Ported the v1.5 FIX-02 temp-copy protection to `yt_import.scan_playlist` (the playlist-scan read site), added corruption auto-recovery with toast-callback plumbing through `_YtScanWorker`, and turned 5 RED cookie tests green.
- Player._youtube_resolve_worker now routes cookies through cookie_utils.temp_cookies_copy with corruption auto-clear + cookies_cleared Signal wired to MainWindow.show_toast — yt-dlp's save_cookies() side effect can no longer overwrite canonical cookies.txt on the player path.
- Closed out Phase 999.7 with full-suite pytest green (764 passed, 10 pre-existing baseline failures unchanged), human UAT sign-off on byte-equality of canonical cookies.txt across real YouTube playback, and a PROJECT.md Key Decisions entry anchoring the FIX-02 restoration for future phases.
- Outcome:
- Real root cause: yt-dlp's library API does not auto-discover JS runtimes the way the CLI does.

---

## v1.5 Further Polish (Shipped: 2026-04-10)

**Phases completed:** 14 phases (21–34), 21 plans | **Stats:** 265/265 tests passing, ~9,900 LOC Python total | **Timeline:** 2026-04-06 → 2026-04-10 (5 days)

**Delivered:** Closed out v1.x with bug fixes discovered through daily use plus opportunistic feature polish — YouTube cookie import, multi-stream station model with failover and quality selection, Twitch streaming via streamlink + OAuth, hamburger-menu consolidation, elapsed-time counter, 15s YouTube failover gate with connecting-toast UX, and panel-layout sizing regression fix.

**Key accomplishments:**

- **FIX-01 (Phase 21):** YouTube thumbnail sizing regression fixed by switching from `Gtk.Picture` + `ContentFit.CONTAIN` to pre-scaled `GdkPixbuf` + `Gtk.Image` with 320×180 slot; root-caused to `Gtk.Picture.measure()` reporting source natural size regardless of `set_size_request`/`vexpand`. Live-UAT verified after the initial audit missed the regression.
- **Phase 22 (COOKIE-01..06):** YouTube cookie import via file picker, paste, or Google login (WebKit2 embedded browser); stored at `~/.local/share/musicstreamer/cookies.txt` with 0o600 permissions; yt-dlp always gets `--no-cookies-from-browser` and both yt-dlp/mpv use `--cookies=<path>` when present.
- **Phase 23 (FIX-02/03):** Cookie invocations use temp copies to preserve the imported original; mpv fast-exit (~2s) with cookies triggers one retry without cookies to survive corrupted cookie files.
- **Phases 24–26 (FIX-04/05/06):** Tag chips and filter chips wrap via `Gtk.FlowBox`; the broken standalone filter-bar Edit button was replaced with a now-playing edit icon gated on play/pause state.
- **Phase 27 (STR-01..14):** Multi-stream station model — `station_streams` table with quality/label/position, `stations.url` migrated and dropped, `ManageStreamsDialog` for CRUD/reorder, quality presets (hi/med/low/custom), Radio-Browser/YT/AudioAddict import integrated.
- **Phase 28 (D-01..08):** Stream failover engine with server round-robin, quality fallback queue, toast notifications, and stream-picker UI; 13 failover tests.
- **Phase 29 (MENU-01..05):** Hamburger menu consolidation — Discover, Import, Accent Color, and YouTube Cookies moved from the header bar into a two-section Gio menu driven by `SimpleAction`s.
- **Phase 30 (TIMER-01..06):** Elapsed-time counter in now-playing panel with pause/resume, station-change reset, failover-safe continuity, and adaptive `M:SS` / `H:MM:SS` formatting.
- **Phases 31–32 (TWITCH/TAUTH):** Twitch streaming via `streamlink --stream-url` feeding GStreamer playbin3; offline detection with toast (no failover); OAuth token auth via renamed `AccountsDialog` with WebKit2 subprocess that captures the Twitch auth-token cookie and writes it to `TWITCH_TOKEN_PATH` with 0o600 perms.
- **Phase 33 (FIX-07):** YouTube streams get a 15-second minimum wait window before `_try_next_stream` can fire; `_yt_attempt_start_ts` + `_yt_poll_timer_id` track the gate; cookie-retry re-seeds the timestamp; "Connecting…" `Adw.Toast` fires on all `play()` / `play_stream()` paths; `_cancel_failover_timer` clears the attempt timestamp. 264 tests pass after the phase.
- **Phase 34 (cleanup):** Fixed deferred `test_streamlink_called_with_correct_args` by monkeypatching `musicstreamer.player.TWITCH_TOKEN_PATH` to force the no-token branch; annotated the stale cookies-test deferred item in Phase 33 as already resolved in commit `b3e066b` during 33-02. Production code untouched. 265/265 tests pass.

**Tech debt carried forward:** panel-sizing has no automated regression test (GTK needs live display); `accounts_dialog.py` uses deprecated `tempfile.mktemp`; `~/.local/share/musicstreamer/mpv.log` has no rotation.

**Process lesson:** Retroactive verification based on static code inspection missed the FIX-01 runtime GTK-measure behavior. Future phases touching GTK widget sizing require live-display UAT as an explicit gate.

---

## v1.4 Media & Art Polish (Shipped: 2026-04-05)

**Phases completed:** 5 phases (16–20), 8 plans | **Stats:** 153 tests | 69 files changed, 8,484 insertions | 2 days

**Delivered:** Tuned GStreamer buffer to eliminate ShoutCast drop-outs, added AudioAddict logo fetch at import + editor, YouTube 16:9 thumbnail display, custom accent color picker, play/pause button, and MPRIS2 OS media key integration.

**Key accomplishments:**

- GStreamer playbin3 `buffer-duration` (10s) and `buffer-size` (10 MB) set via TDD — eliminates ShoutCast/HTTP audible drop-outs; constants live in `constants.py` per project pattern
- `ThreadPoolExecutor` workers with thread-local `db_connect()` download AA channel logos at bulk import time; two-phase progress in `ImportDialog`; silent failure on fetch error
- AA URL detection for all 6 network domains in station editor with daemon-thread logo fetch and API key popover; `_aa_channel_key_from_url` uses `urllib.parse` (not regex) to correctly strip network slug prefix
- YouTube thumbnails displayed as full 16:9 using `ContentFit.CONTAIN` in now-playing logo slot; cover slot stays on fallback to avoid duplication
- `AccentDialog` with 8 GNOME-preset swatches and hex entry — immediate CSS provider reload at `PRIORITY_USER`, inline error state on invalid hex, persisted via SQLite settings
- `Player.pause()` (GStreamer NULL state) + play/pause button between star and stop; station stays selected on pause; MPRIS2 D-Bus service wired via `dbus-python` — OS media keys fully functional

---

## v1.3 Discovery & Favorites (Shipped: 2026-04-03)

**Phases completed:** 4 phases (12–15), 8 plans | **Stats:** 127 tests | 3,150 source + 1,468 test Python LOC | 59 commits | 8 days

**Delivered:** Added favorites (star ICY tracks, Favorites list), Radio-Browser.info discovery dialog, YouTube playlist importer, and AudioAddict bulk importer with tabbed ImportDialog.

**Key accomplishments:**

- `Favorite` dataclass, SQLite table with UNIQUE(station_name, track_title) dedup, repo CRUD — `INSERT OR IGNORE` for silent dedup; `cover_art.last_itunes_result` caches genre for favorites without a second API call
- Star button in now-playing panel (gated on non-junk ICY title), `Adw.ToggleGroup` Stations/Favorites view switcher, favorites list with trash removal and empty state
- `radio_browser.py` API client (`search_stations`, `fetch_tags`, `fetch_countries`) using urllib + daemon threads; `repo.station_exists_by_url` and `repo.insert_station` for discovery save
- `DiscoveryDialog` modal: live search, tag/country dropdowns, per-row play buttons with prior-station resume, save to library — `url_resolved` preferred over `url` (avoids PLS/M3U)
- `yt_import.py` backend with `scan_playlist`/`import_stations`; `ImportDialog` two-stage scan→checklist flow with spinner, progress count, and per-item selection; thread-local SQLite for import worker
- `aa_import.py` backend: `fetch_channels`/`import_stations` across all AudioAddict networks, PLS→direct URL resolution at fetch time, quality tier selection; `ImportDialog` refactored to `Gtk.Notebook` tabs (YouTube + AudioAddict)

---

## v1.2 Station UX & Polish (Shipped: 2026-03-27)

**Phases completed:** 5 phases, 12 plans, 13 tasks

**Key accomplishments:**

- SQLite data layer for recently-played tracking (millisecond-precision timestamps) and key/value settings storage, with idempotent migrations and 10 new passing tests
- Adw.ExpanderRow provider groups replacing flat StationRow list, with dual render modes (grouped/flat) driven by filter state
- Recently Played section above provider groups using in-place ListBox insert to preserve ExpanderRow collapse state, wired to play hook and hidden during active filters
- `matches_filter_multi` added to filter_utils.py — set-based multi-select filter with OR-within-dimension, AND-between-dimension logic and case-insensitive tag matching
- Gtk.DropDown provider/tag filters replaced with scrollable Gtk.ToggleButton chip strips supporting OR-within-dimension, AND-between-dimensions multi-select
- Replaced freeform provider and tags text entries in EditStationDialog with Adw.ComboRow picker and scrollable ToggleButton chip panel, both supporting inline creation of new values
- YouTube URL focus-out now fetches stream title via yt-dlp and auto-populates empty name field, running in parallel with the existing thumbnail fetch using independent flags
- Player.set_volume clamps float to [0.0, 1.0], writes GStreamer pipeline volume property, stores for mpv subprocess launch — 4 TDD tests pass, 85-test suite green
- Provider name shown inline as "Name · Provider" in now-playing label; Gtk.Scale volume slider wired to GStreamer and persisted via settings — 85 tests green
- Rounded panel gradient, station art 5px border-radius (GTK4: set_overflow(HIDDEN) required on Gtk.Stack — CSS overflow alone insufficient), improved spacing throughout

---

## v1.1 Polish & Station Management (Shipped: 2026-03-21)

**Phases completed:** 2 phases, 4 plans | **Stats:** 58 tests | 1,782 Python LOC | 27 commits | 1 day

**Delivered:** Fixed GTK markup escaping for ICY titles, surfaced station logos in the list, added delete station, per-station ICY disable, and YouTube thumbnail auto-fetch.

**Key accomplishments:**

- GTK markup escaping: `&`, `<`, `>` in ICY titles and station names display as literal characters
- Station logo pre-loaded into cover art slot as default; junk ICY title no longer clears it
- Station list always shows 48px prefix widget — logo when available, generic icon otherwise
- `Station.icy_disabled` field, SQLite migration, repo CRUD, and MainWindow playback guard for per-station ICY suppression
- Delete Station in edit dialog with playing guard (blocks deletion while streaming) and confirmation dialog
- YouTube URL auto-fetch: entering a YT URL triggers yt-dlp thumbnail fetch with spinner feedback

---

## v1.0 MVP (Shipped: 2026-03-20)

**Phases completed:** 4 phases, 8 plans, 0 tasks

**Delivered:** Transformed a monolithic GTK4/Python radio player into a modular, feature-rich app with live search/filter, ICY metadata display, and iTunes cover art.

**Stats:** 4 phases | 8 plans | 43 tests | 1,409 Python LOC | 74 files changed | 35 days

**Key accomplishments:**

- Refactored ~512-line `main.py` monolith into clean `musicstreamer/` package (constants, models, repo, assets, player, UI)
- TDD filter engine with real-time AND-composed search + provider/tag dropdowns and empty-state handling
- GStreamer ICY TAG bus wired to now-playing panel — live track titles with latin-1 mojibake correction
- Three-column now-playing panel: station logo (left), track info + Stop (center), cover art (right)
- iTunes Search API cover art with junk title detection, session dedup, and smooth in-flight transitions
- 43 automated tests across 4 modules; zero regressions across all phases

---
