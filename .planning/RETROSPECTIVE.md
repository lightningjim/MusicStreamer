# Retrospective: MusicStreamer

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-20
**Phases:** 4 | **Plans:** 8 | **Timeline:** 35 days (2026-02-13 → 2026-03-20)

### What Was Built

- Modular Python package from a ~512-line monolith (Phase 1)
- Live AND-composed search + provider/tag filtering with empty state (Phase 2)
- GStreamer ICY TAG bus → now-playing panel with live track titles and station logo (Phase 3)
- iTunes cover art with junk detection, session dedup, in-flight continuity (Phase 4)

### What Worked

- **TDD first on pure logic** — filter_utils.py and cover_art.py written test-first; caught edge cases (junk titles, encoding bugs) before wiring to GTK
- **Gtk.Stack pattern** — established in Phase 3 for logo slot, reused identically in Phase 4 for art slot; zero rethinking
- **GLib.idle_add pattern** — established Phase 3, copy-pasted Phase 4; cross-thread GTK updates are a solved problem now
- **Phase sequencing** — extracting the monolith first (Phase 1) made every subsequent phase a clean, well-scoped addition

### What Was Inefficient

- Phase 1 needed a gap-closure plan (01-03) for YouTube audio fix and edit button — could have been caught in planning
- Nyquist VALIDATION.md files created but never completed (`nyquist_compliant: false` on all phases) — overhead with no payoff for this project scale

### Patterns Established

- `GLib.idle_add` + daemon threading for any background → GTK UI update
- `Gtk.Stack("fallback"/"content")` for slot widgets that can show placeholder or real content
- `uv run --with pytest` as the test runner (no system pip, no venv activation)
- `_last_cover_icy`-style string dedup for avoiding redundant API calls on repeated signals

### Key Lessons

- ICY encoding (latin-1 mojibake) is real — the `_fix_icy_encoding` heuristic handles the common case
- iTunes Search API is keyless and fast enough for per-track cover art; rate limits not hit in practice
- GTK downscale artifacts are real — always pre-scale with GdkPixbuf before `set_from_pixbuf`

### Cost Observations

- Model mix: mostly sonnet (executor, checker, researcher); opus for planner
- Nyquist auditor never invoked — VALIDATION.md files were stubs only
- Sessions: ~8 across 35 days

## Milestone: v1.2 — Station UX & Polish

**Shipped:** 2026-03-27 (gap closure)
**Phases:** 5 | **Plans:** 12 | **Timeline:** 5 days (2026-03-22 → 2026-03-27)

### What Was Built

- Provider-grouped ExpanderRow station list with dual render modes and recently played section (Phase 7)
- Multi-select ToggleButton chip strips for provider/genre filters with OR-within/AND-between logic (Phase 8)
- Station editor upgraded to ComboRow provider picker + tag chip panel with inline creation + YouTube title auto-import (Phase 9)
- "Name · Provider" label in now-playing; Gtk.Scale volume slider wired to GStreamer + persisted in settings (Phase 10)
- CSS provider: gradient panel background, rounded art corners, improved spacing throughout (Phase 11)

### What Worked

- **GTK widget archaeology before coding** — Phase 7's ExpanderRow investigation (can't use set_filter_func) saved a false start; researching GTK behaviors upfront prevented mid-phase rewrites
- **TDD for filter logic** — matches_filter_multi written test-first in Phase 8; OR/AND semantics proven correct before touching GTK
- **Parallel fetches with independent flags** — Phase 9 split `_fetch_in_progress` into two independent flags; thumbnail and title fetch in parallel without coordination overhead
- **State machine discipline** — `_rebuilding` guard for chip rebuilds; `_current_station` for ICY suppression; these small guards prevent entire classes of spurious update bugs
- **user review mid-phase** — Phase 11 caught art border-radius (UAT) and text spacing issues before close; gap closure (11-02) confirmed GTK4 CSS overflow is insufficient alone

### What Was Inefficient

- Phase 10 ROADMAP not updated after plan completion — `roadmap_complete: false` for Phase 10 despite disk showing 2/2. Minor inconsistency survived into milestone close
- No milestone audit run before completion — skipped in yolo mode; all requirements were clean but audit would have caught ROADMAP inconsistency above

### Patterns Established

- `strftime` millisecond precision for timestamps used as sort keys — `datetime('now')` second granularity causes ordering failures
- `ListBox.insert(row, 0)` for in-place section refresh — preserves expand/collapse state; full reload does not
- Filter chips use `btn.set_active(False)` to dismiss — fires toggled signal; avoids double callback
- GTK4 `border-radius` clipping: CSS `overflow: hidden` alone does not clip child Gtk.Image paint nodes — must call `set_overflow(Gtk.Overflow.HIDDEN)` at the widget API level on the Gtk.Stack container

### Key Lessons

- ExpanderRow + set_filter_func is incompatible — filter_func cannot see children added via add_row(); must rewrite entire list to filter grouped layouts
- Row activation in nested ListBoxes: `row-activated` on outer ListBox does not fire for ExpanderRow children; use `activated` signal on each inner row
- Volume default matters — 100% on first launch feels like an attack; 80% is a sensible default

### Cost Observations

- Model mix: sonnet throughout
- Sessions: ~3-4 across 3 days
- Notable: 12 plans in 5 days; gap closure added 2 plans after UAT; GTK research front-loaded in phases 7-8 paid off in 9-11

## Milestone: v1.3 — Discovery & Favorites

**Shipped:** 2026-04-03
**Phases:** 4 (12–15) | **Plans:** 8 | **Timeline:** 8 days (2026-03-27 → 2026-04-03)

### What Was Built

- Favorites system: `Favorite` dataclass, SQLite table with UNIQUE dedup, star button gated on non-junk ICY title, Adw.ToggleGroup view switcher, trash removal, empty state (Phase 12)
- Radio-Browser.info API client + `DiscoveryDialog`: search, tag/country filters, per-row preview with prior-station resume, save to library (Phase 13)
- `yt_import.py` backend + `ImportDialog` two-stage scan→checklist flow with spinner and per-item selection; live-streams-only filter via `is_live is True` strict check (Phase 14)
- `aa_import.py` backend with PLS resolution at fetch time; `ImportDialog` refactored to `Gtk.Notebook` tabs for YouTube + AudioAddict; quality selector, per-network error skip (Phase 15)

### What Worked

- **Backend-first phase split** — each phase built pure-function backend module (plan 01) before GTK UI (plan 02); backends fully testable without display
- **Thread-local SQLite pattern** — established in Phase 14 for import worker; reused identically in Phase 15; prevented cross-thread SQLite errors
- **PLS resolution at import time** — catching the GStreamer/PLS incompatibility in aa_import.fetch_channels rather than at playback was the right place; silent failure at play time would have been confusing
- **Dedup consistency** — all three import paths (discovery save, yt_import, aa_import) independently call `repo.station_exists_by_url` before insert; no shared coordinator needed
- **Milestone audit before close** — caught Phase 12 VERIFICATION.md missing and stale REQUIREMENTS.md checkboxes; resolved before tagging

### What Was Inefficient

- Phase 12 REQUIREMENTS.md checkboxes not updated after Plan 02 completed — surfaced in audit; minor but required a correction commit
- DISC-03 cosmetic bug (stale now-playing after preview close when nothing was previously playing) deferred to tech debt — straightforward fix (`_stop()` instead of `player.stop()`) but not caught until integration check
- Nyquist compliance partial for phases 13–15 — VALIDATION.md files exist but wave_0 incomplete; overhead without payoff at this project scale

### Patterns Established

- `module-level result dict` (`last_itunes_result`) for caching cross-function state without extra HTTP calls
- `Adw.ToggleGroup` with `notify::active-name` for native Adwaita segmented control view switching
- `url_resolved` preferred over `url` from Radio-Browser API (url is often a PLS/M3U)
- `ch['key']` not `ch['name']` for URL slug construction — names have spaces, keys are lowercase slugs
- `ValueError('no_channels')` sentinel for detecting expired API keys that return 200+empty

### Key Lessons

- AudioAddict API key validation is implicit — a 200 response with empty channel lists is an expired key, not a network error
- Radio-Browser station URLs frequently resolve to PLS/M3U; always prefer `url_resolved`
- GTK `Gtk.Notebook` is the right tool for tabbed dialogs when content is completely independent between tabs
- SQLite cross-thread errors surface at runtime, not import time — always open a thread-local connection in worker threads

### Cost Observations

- Model mix: sonnet throughout
- Sessions: ~5-6 across 8 days
- Notable: 4 phases with clear API-backend + GTK-UI split made each phase predictable; research phases paid for themselves

---

## Milestone: v1.4 — Media & Art Polish

**Shipped:** 2026-04-05
**Phases:** 5 (16–20) | **Plans:** 8 | **Timeline:** 2 days (2026-04-03 → 2026-04-05)

### What Was Built

- GStreamer playbin3 buffer-duration/buffer-size tuned via TDD — ShoutCast drop-outs eliminated (Phase 16)
- AA channel logos downloaded at import time via ThreadPoolExecutor with thread-local DB connections; two-phase ImportDialog progress (Phase 17)
- Station editor auto-fetches AA logo on URL paste using daemon thread + GLib.idle_add; slug-prefix bug caught during verification (Phase 17)
- YouTube thumbnails displayed as full 16:9 using ContentFit.CONTAIN in logo slot; cover slot stays on fallback (Phase 18)
- Custom accent color picker: 8 GNOME presets + hex entry, CssProvider at PRIORITY_USER, persisted in SQLite settings (Phase 19)
- Player.pause() (GStreamer NULL state) + play/pause button with station-selection preserved on pause (Phase 20)
- MprisService D-Bus service via dbus-python; OS media keys fully wired to pause/resume/stop (Phase 20)

### What Worked

- **Shortest milestone yet (2 days)** — tight scope (7 requirements, all polish/UX) made planning and execution fast
- **TDD for hardware-adjacent code** — buffer tuning (Phase 16) and MPRIS2 (Phase 20) both used red→green TDD; unit tests confirmed behavior without needing live hardware at every step
- **Backend-first split** — Phase 17 (AA logo backend) and Phase 20 (pause backend) cleanly preceded UI plans; no rework between plans
- **Thread-local DB pattern** — established in v1.3, reused again in Phase 17 logo workers; zero friction
- **Research.md MPRIS pitfalls** — DBusGMainLoop set_as_default pitfall documented in RESEARCH.md before coding saved a non-obvious runtime error

### What Was Inefficient

- REQUIREMENTS.md checkboxes not updated after phases — ART-01, ART-03, ACCENT-01, CTRL-01, CTRL-02 all shipped complete but stayed `[ ]` until milestone close audit
- Nyquist VALIDATION.md files remain `nyquist_compliant: false` across all 5 phases — overhead without payoff at this scale; `/gsd-validate-phase` not worth running for this project
- MILESTONES.md auto-generation from gsd-tools extracted raw YAML field names ("One-liner:", "Task 1 (TDD):") — required manual correction post-archive

### Patterns Established

- `ContentFit.CONTAIN` for aspect-ratio-preserving images in fixed-size slots (letterbox behavior)
- `dbus.service.Object` subclass + `DBusGMainLoop(set_as_default=True)` at module import (before class definition) — required ordering for dbus-python
- `PRIORITY_USER` for accent CSS overrides (PRIORITY_APPLICATION is insufficient to override theme tokens)
- `Player.pause()` as thin wrapper (identical to stop()); "keep station selected" logic lives in the UI layer, not the player

### Key Lessons

- DBusGMainLoop must be called before dbus.service.Object subclass is defined — not just before instantiation
- CSS `PRIORITY_USER` vs `PRIORITY_APPLICATION` distinction matters when overriding Adwaita theme tokens
- 2-day milestone velocity is achievable when scope is well-defined polish (no new subsystems)

### Cost Observations

- Model mix: sonnet throughout
- Sessions: ~3 across 2 days
- Notable: fastest feature milestone — tight scope + established patterns = minimal research overhead

---

## Milestone: v1.5 — Further Polish

**Shipped:** 2026-04-10
**Phases:** 14 (21–34) | **Plans:** 21 | **Timeline:** 5 days (2026-04-06 → 2026-04-10)

### What Was Built

- **FIX-01 Panel layout (Phase 21)** — YouTube thumbnail inflation fixed by switching from `Gtk.Picture` + `ContentFit.CONTAIN` to pre-scaled `GdkPixbuf` + `Gtk.Image` with a 320×180 slot. Root cause: `Gtk.Picture.measure()` returns source natural size regardless of `set_size_request` (minimum, not cap) or `vexpand=False`.
- **COOKIE-01..06 YT cookie import (Phase 22)** — File picker, paste, and Google login via WebKit2 embedded browser; 0o600 perms; hamburger menu entry; yt-dlp always gets `--no-cookies-from-browser`; both yt-dlp and mpv use `--cookies=<path>` when present.
- **FIX-02/03 Cookie-safe playback (Phase 23)** — yt-dlp/mpv invocations use temp copies of cookies.txt (preserving the imported original); mpv fast-exit (~2s) with cookies triggers one retry without cookies to survive corrupted cookie files.
- **FIX-04/05/06 Layout fixes (Phases 24–26)** — Tag chips and filter chips wrap via `Gtk.FlowBox`; broken standalone Edit button replaced with a now-playing edit icon gated on play/pause state.
- **STR-01..14 Multi-stream model (Phase 27)** — `station_streams` table with quality/label/position, `stations.url` migrated and dropped, `ManageStreamsDialog` for CRUD/reorder, quality presets (hi/med/low/custom); Radio-Browser/YT/AudioAddict import integrated.
- **Stream failover D-01..08 (Phase 28)** — Server round-robin + quality fallback queue, toast notifications, stream-picker UI, 13 failover tests.
- **MENU-01..05 Hamburger consolidation (Phase 29)** — Discover, Import, Accent Color, YT Cookies moved from header bar to a two-section Gio menu driven by `SimpleAction`s; header bar reduced to search + hamburger.
- **TIMER-01..06 Elapsed counter (Phase 30)** — Now-playing time counter with pause/resume, station-change reset, failover-safe continuity, adaptive `M:SS` / `H:MM:SS` formatting.
- **TWITCH-01..08 Twitch streaming (Phase 31)** — `streamlink --stream-url` resolves HLS URL and feeds GStreamer playbin3; offline detection shows toast without triggering failover; `~/.local/bin` added to PATH.
- **TAUTH-01..07 Twitch OAuth (Phase 32)** — `CookiesDialog` renamed to `AccountsDialog` with `Gtk.Notebook` tabs; WebKit2 subprocess captures Twitch auth-token cookie and writes it to `TWITCH_TOKEN_PATH` with 0o600; `_play_twitch()` prepends `--twitch-api-header Authorization=OAuth <token>` when the token file is present.
- **FIX-07 YouTube 15s failover gate (Phase 33)** — YT streams get a 15-second minimum wait before `_try_next_stream` can fire; `_yt_attempt_start_ts` + `_yt_poll_timer_id` track the gate; cookie-retry re-seeds the timestamp; `Adw.Toast("Connecting…")` fires on all `play()` / `play_stream()` paths; `_cancel_failover_timer` clears the attempt timestamp.
- **Phase 34 cleanup** — Fixed deferred `test_streamlink_called_with_correct_args` by monkeypatching `musicstreamer.player.TWITCH_TOKEN_PATH` to force the no-token branch; annotated the stale cookies-test deferred item in Phase 33 as already resolved in commit `b3e066b` during 33-02. Production code untouched. 265/265 tests pass.

### What Worked

- **Pre-execution scope audits saved rework.** Phase 34's discuss step discovered the cookies-test deferred item was already fixed in Phase 33-02 (commit `b3e066b`), reducing the phase from "fix two tests" to "fix one test + annotate stale doc." Running the deferred tests BEFORE planning was the difference-maker.
- **Tight per-phase scoping.** Bundling FIX-01 alone into Phase 21, keeping the chip fixes (24/25/26) as separate phases, and splitting multi-stream (27) from failover (28) let each phase ship independently and audit cleanly.
- **Chain-mode (`--chain`) for trivial phases.** Phase 34 ran discuss → plan → execute → verify autonomously in one shot because scope was locked by the discussion. No mid-phase replanning.
- **Live UAT gate after FIX-01 regression.** The initial audit cleared FIX-01 via code inspection; a post-audit UAT found a real GTK layout regression. Re-audit + fix + live UAT closed the gap the same day, before ship.
- **Streamlink for Twitch instead of a new subsystem.** Feeding streamlink's resolved HLS URL to existing GStreamer playbin3 reused the whole failover/timer/metadata stack. Offline detection required only a toast path, not a new state machine.

### What Was Inefficient

- **Retroactive verification based on static code inspection missed a runtime GTK layout bug in FIX-01.** `Gtk.Picture.measure()` returns source natural size regardless of `set_size_request`/`vexpand`. The initial audit would have shipped a regression if the user hadn't run post-audit UAT. Added explicit "live-display UAT required" gate for any future phase touching GTK widget sizing.
- **51-of-53 REQUIREMENTS.md checkboxes drifted to milestone close.** Only FIX-01 and FIX-07 were flipped inline. A checkbox sweep at `/gsd-complete-milestone` handled it, but consider having `/gsd-execute-phase` flip checkboxes at phase-commit time in the future.
- **MILESTONES.md one-liner extraction broke again.** `gsd-tools summary-extract --pick one_liner` returned literal "One-liner:" header text instead of the content after it. Same issue flagged in v1.4; still needs a fix upstream. Manual correction required.
- **Nyquist VALIDATION.md artifacts still `nyquist_compliant: false` across v1.5 phases.** Same verdict as v1.4 — overhead without payoff at this scale for a single-user desktop app. Skipped `/gsd-validate-phase` for all 14 phases.

### Patterns Established

- **`GdkPixbuf.new_from_file_at_scale` + `Gtk.Image`** for aspect-ratio-aware image slots where `Gtk.Picture`'s natural-size measurement would inflate containers. Superset of v1.4's `ContentFit.CONTAIN` pattern.
- **`monkeypatch.setattr("module.PATH_CONSTANT", str(tmp_path / "nonexistent"))`** as the cleanest way to force no-token/no-file branches in subprocess tests without touching `builtins.open` or the subprocess mock.
- **WebKit2 subprocess for cookie capture** — same subprocess pattern reused from Phase 22 (YT cookies) in Phase 32 (Twitch token). Spawn, navigate, extract, write to 0o600 file, exit.
- **Streamlink-in-front-of-GStreamer** for non-direct-stream sources: resolve the HLS URL externally, feed the direct URL to existing `_set_uri` pipeline. Keeps failover/timer/metadata paths unchanged.
- **Elapsed timer uses `GLib.timeout_add_seconds(1, cb)`** with tracked source ID for cleanup; pause on stream pause, resume on unpause, reset only on station change (not failover).
- **Pre-execution scope audit during discuss-phase** — run the actual commands mentioned in deferred-items or acceptance criteria before planning. Saved an entire plan in Phase 34.

### Key Lessons

- **GTK measurement ≠ size constraints.** `set_size_request` is a minimum, `hexpand/vexpand=False` only govern extra-space allocation, and `Gtk.Picture.measure()` reports source natural size. For fixed-slot image containers, pre-scale the pixbuf and use `Gtk.Image`.
- **Retroactive verification without UAT is unsafe for runtime-layout code.** Static inspection of constraints can miss emergent runtime behavior. Require live UAT as a gate when code touches widget sizing or container allocation.
- **Deferred-items.md entries go stale fast.** Re-verify before planning a cleanup phase. One of the two Phase 33 deferred items was already fixed two commits later.
- **A "trivial" follow-up phase still benefits from the full discuss→plan→execute→verify cycle** when it's wrapped in `--chain`. Phase 34 shipped in one chain invocation with no manual intervention because the discussion locked the scope.
- **265/0 test ratio is achievable** when a cleanup phase explicitly forbids production-code touches and runs the full regression suite as the verification gate.

### Cost Observations

- Model mix: opus for plan-phase, sonnet for execute/verify/check — standard GSD defaults
- Sessions: ~6 across 5 days
- Notable: Phase 34 ran end-to-end (discuss → plan → execute → verify → audit) in a single `/gsd-discuss-phase 34 --chain` invocation followed by `/gsd-audit-milestone` → `/gsd-complete-milestone`. Fully autonomous pipeline for a bounded scope.

---

## Cross-Milestone Trends

| Metric | v1.0 | v1.1 | v1.2 | v1.3 | v1.4 | v1.5 |
|--------|------|------|------|------|------|------|
| Phases | 4 | 2 | 5 | 4 | 5 | 14 |
| Plans | 8 | 4 | 12 | 8 | 8 | 21 |
| Tests | 43 | 58 (+15) | 85 (+27) | 127 (+42) | 153 (+26) | 265 (+112) |
| LOC (Python total) | 1,409 | 1,782 (+373) | ~2,200 | 3,150 (+950) | ~3,500 (+350) | ~9,900 (+6,400) |
| Gap closure plans | 1 | 0 | 0 | 0 | 0 | 0 |
| Days | 35 | 1 | 3 | 8 | 2 | 5 |

## Milestone: v1.1 — Polish & Station Management

**Shipped:** 2026-03-21
**Phases:** 2 | **Plans:** 4 | **Timeline:** 1 day (2026-03-21)

### What Was Built

- GTK markup escaping fixed for ICY titles and Adw.ActionRow station names (Phase 5)
- Station logo pre-loaded into cover art slot as default; cover not cleared on junk ICY title (Phase 5)
- StationRow always shows 48px prefix widget — logo or generic icon placeholder (Phase 5)
- Station.icy_disabled field, migration, repo CRUD, MainWindow suppression guard (Phase 6)
- Delete Station dialog with playing guard, per-station ICY SwitchRow, YouTube thumbnail auto-fetch (Phase 6)

### What Worked

- **TDD red→green** — escaping tests and delete/icy_disabled repo tests written before implementation; caught edge cases early
- **Bug fix mid-execution** — `&amp;` display issue caught during Phase 6 checkpoint, fixed inline (two commits: set_text labels + ActionRow escaping). Checkpoints gave the right moment
- **Daemon thread + GLib.idle_add** — re-applied from v1.0 for YT thumbnail fetch; zero new problems
- **Audit → complete workflow** — running audit before complete-milestone surfaced SUMMARY frontmatter gaps early

### What Was Inefficient

- SUMMARY `requirements_completed` frontmatter incomplete across several plans — BUG-01, BUG-02, MGMT-02 missing
- Phase 5 VERIFICATION evidence for BUG-01 went stale after the bug fix changed the implementation — verification snapshots can be invalidated mid-session

### Patterns Established

- `set_text()` never needs escaping; `Adw.ActionRow(title=)` always needs `GLib.markup_escape_text`
- `Adw.SwitchRow` for boolean per-item toggles in edit dialogs
- `Gtk.Stack` (pic/spinner) to swap between image and spinner without re-parenting
- Playing guard: `is_playing=lambda: ...` passed into dialogs for live state check without MainWindow reference

### Key Lessons

- GTK markup context is per-widget — document which labels use set_text vs set_markup vs ActionRow
- Verification evidence can go stale within the same session if a bug fix lands after verify runs
- 27 commits in ~2 hours; checkpoints are load-bearing at this pace

### Cost Observations

- Model mix: sonnet throughout
- Sessions: 1 (completed same day started)
- Notable: fastest milestone yet — 1 day vs 35 days for v1.0
