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

## Cross-Milestone Trends

| Metric | v1.0 | v1.1 | v1.2 | v1.3 |
|--------|------|------|------|------|
| Phases | 4 | 2 | 5 | 4 |
| Plans | 8 | 4 | 12 | 8 |
| Tests | 43 | 58 (+15) | 85 (+27) | 127 (+42) |
| LOC source (Python) | 1,409 | 1,782 (+373) | ~2,200 | 3,150 (+950) |
| Gap closure plans | 1 | 0 | 0 | 0 |
| Days | 35 | 1 | 3 | 8 |

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
