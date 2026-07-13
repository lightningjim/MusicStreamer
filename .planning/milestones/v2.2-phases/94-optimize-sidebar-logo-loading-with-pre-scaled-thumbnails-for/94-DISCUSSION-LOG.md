# Phase 94: Sidebar Logo Thumbnail Optimization - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-15
**Phase:** 94-optimize-sidebar-logo-loading-with-pre-scaled-thumbnails-for
**Areas discussed:** Generation strategy & timing, Existing-library backfill / warming, Thumbnail size & HiDPI, Staleness / invalidation

---

## Generation strategy & timing

| Option | Description | Selected |
|--------|-------------|----------|
| Lazy on-miss + write to disk | Sidebar checks for a thumb file; if missing, generate from full-res once, write next to the logo, then use. No migration, self-healing, covers all import sources. | ✓ |
| Eager at import + backfill | Generate in the import workers + one-time migration to backfill existing stations. | |
| Hybrid: lazy + opportunistic | Lazy-on-miss as source of truth, plus eager generation at import. | |

**User's choice:** Lazy on-miss + write to disk
**Notes:** Self-healing and migration-free; automatically covers aa/soma/gbs imports and manual edits.

---

## Existing-library backfill / warming

| Option | Description | Selected |
|--------|-------------|----------|
| Background warmer on startup | Startup thread walks stations generating missing thumbs; sidebar shows fallback until ready. | |
| Async generate-on-miss | Demand-driven but off the UI thread: miss paints fallback, worker generates+caches, row repaints. No startup scan. | ✓ |
| Pure lazy, accept one slow first pass | Generate synchronously on first paint, just persist the result. First scroll still stutters once. | |

**User's choice:** Async generate-on-miss
**Notes:** Reframed for the lazy decision — pure lazy still stutters on the first pass because generation would run on the UI thread. Moving generation off-thread keeps even the first DI.fm scroll smooth. Planner must build a QImage in the worker (QPixmap is main-thread-only) and emit dataChanged to repaint.

---

## Thumbnail size & HiDPI

| Option | Description | Selected |
|--------|-------------|----------|
| 96px (covers up to 3x) | One file, sharp 1x–3x (Wayland fractional, Retina 2x, Windows 1.5/2x); still tiny. | ✓ |
| 64px (covers up to 2x) | Smallest useful; soft on 3x fractional Wayland. | |
| DPR-aware multiple sizes | @1x/@2x/@3x variants; sharpest but more files and cache complexity. | |

**User's choice:** 96px (covers up to 3x)
**Notes:** Single artifact covering all realistic DPRs; reuses existing devicePixelRatio canvas logic in load_station_icon.

---

## Staleness / invalidation

| Option | Description | Selected |
|--------|-------------|----------|
| mtime check on load | Fixed thumb name; regenerate if missing OR older than source logo. One stat() per load, self-healing, no orphans. | ✓ |
| Regenerate on update_station_art | Explicit invalidation at the DB choke point; relies on every art-change path routing through it. | |
| Content-hash filename | Hash-named thumb; changed logo = new name = auto-miss. Self-healing but leaves orphans. | |

**User's choice:** mtime check on load
**Notes:** Robust even if a future art-change path forgets to invalidate; re-import and edit-dialog both bump station_art.png's mtime. GBS themed override is in-memory only, doesn't touch the disk thumb.

---

## Claude's Discretion

- Exact worker/threading mechanism (thread pool vs QThread vs existing worker pattern).
- Placeholder icon during the async gap (FALLBACK_ICON is the natural default).
- Precise QPixmapCache key scheme and PNG encoding parameters.

## Deferred Ideas

- DPR-aware multi-size thumbnails — rejected as overkill for a 32px icon; revisit only if 96px looks soft on extreme fractional scaling.
- Eager import-time generation + startup backfill warmer — not chosen (lazy async is self-healing/migration-free); revisit only if the async placeholder flash is distracting in practice.
- The 6 todos from `todo.match-phase 94` were false positives (matched ROADMAP placeholder keywords, not domain) — reviewed, none folded.
