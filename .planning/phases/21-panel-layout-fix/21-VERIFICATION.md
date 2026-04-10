---
phase: 21
slug: panel-layout-fix
status: passed
verified: 2026-04-10
requirements_verified:
  - FIX-01
---

# Phase 21 Verification: Panel Layout Fix

## Goal
The now-playing panel maintains its intended dimensions at all window sizes.

## Must-Haves

| # | Requirement | Status | Evidence |
|---|-------------|--------|----------|
| 1 | YouTube maximized does not widen panel | passed | `panel.set_size_request(-1, 160)` + `set_vexpand(False)` (main_window.py:87-88) |
| 2 | YouTube fullscreen does not widen panel | passed | Same constraints as #1; fullscreen uses same sizing path |
| 3 | 16:9 thumbnails contained within logo slot | passed | `logo_stack.set_size_request(160, 160)` + `set_overflow(Gtk.Overflow.HIDDEN)` (main_window.py:102, 109); YouTube pic uses `ContentFit.CONTAIN` + `set_size_request(160, 160)` (main_window.py:898-899) |
| 4 | Non-YouTube layout unaffected | passed | Non-YouTube branch removes stale "yt" child from stack before switching (main_window.py:906-910) |

## Requirements Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| FIX-01 | 21 | Verified (retroactive — implemented as part of Phase 18 + v1.5 cumulative work) |

## Notes

This phase was retroactively verified against existing code. The layout constraints required by FIX-01 were already in place from Phase 18 (YouTube 16:9 ContentFit.CONTAIN) and cumulative v1.5 work. No new code was added for this phase — the phase documents the already-satisfied requirement.

## Test Suite

261 passing (full suite, post-v1.5 phases 22-32). No regression tests exist specifically for panel sizing because GTK layout requires a live display; relies on manual verification for the human_needed path common to v1.5 UI phases.
