---
phase: 61
plan: 01
status: complete
captured: 2026-05-05
---

# Phase 61 Plan 01 — BEFORE Diagnostic SUMMARY

## What was captured

Kyle ran the 10-step Wayland-native diagnostic on his GNOME Shell 50.1 rig (`XDG_SESSION_TYPE=wayland`) and pasted output into `61-DIAGNOSTIC-LOG.md`. The artifact freezes the BEFORE state of every surface Plans 02/03 will mutate — placeholder `org.example.MusicStreamer` everywhere, `.desktop` lookup-chain misses, install marker absent, MPRIS bus name baseline `org.mpris.MediaPlayer2.musicstreamer` (the value Plan 02 must NOT rename).

**Headline artifact:** `screenshots/61-01-pre-fix-forcequit.png` — the GNOME hung-app dialog literally reads **`"org.example.MusicStreamer" Is Not Responding`** while the window title bar above it correctly shows "MusicStreamer". This is the textbook BUG-08 surface; the asymmetry exists because GNOME Shell's force-quit dialog reads `_GTK_APPLICATION_ID` (set by `setDesktopFileName`) not `WM_NAME`. Plan 04's AFTER shot of the same dialog will read `"MusicStreamer" Is Not Responding`.

## Confirmed predictions

| Prediction (RESEARCH §) | Result |
|-------------------------|--------|
| `_GTK_APPLICATION_ID` reads placeholder | ✓ Confirmed via force-quit dialog (gdbus `Eval` was disabled on GNOME 50.1; fallback evidence is more direct anyway) |
| Stale `org.example.MusicStreamer.desktop` in `~/.local/share/applications/` | ✓ |
| No `org.lightningjim.MusicStreamer.desktop` installed | ✓ |
| Icons present in hicolor buckets from prior manual install | ✓ Three `org.lightningjim.MusicStreamer.png` files in different size buckets |
| Install marker `~/.local/share/musicstreamer/.desktop-installed-v1` absent | ✓ |
| MPRIS bus name `org.mpris.MediaPlayer2.musicstreamer` present | ✓ Baseline locked for D-04 unchanged-bus-name verification |
| 5 drift sites matching RESEARCH §Open Question #10 | ✓ All 5 found: `Makefile` ×4, `__main__.py:144`, `mpris2.py:104`, `constants.py:17` |

## Refuted / unexpected findings

**Six orphan agent worktrees** under `.claude/worktrees/agent-*/` each carried a frozen copy of `musicstreamer/constants.py:3` with the old `APP_ID = "org.example.MusicStreamer"`. Not in RESEARCH's drift-site enumeration — these were leftover GSD parallel-agent isolation directories from prior phase executions, never registered with `git worktree`.

**Remediation:** pruned with `rm -rf .claude/worktrees/agent-*` (7.8 MB reclaimed; `git worktree list` confirmed they were not registered). Post-prune Step 9 grep is clean to the 5 canonical drift sites.

**Implication for Plan 02:** none — `tests/test_constants_drift.py::test_no_org_example_literal_remains_in_python_sources` scans `musicstreamer/` only (per VALIDATION.md), so the worktrees would never have false-positived the test. But the visual baseline is now consistent.

**Implication for Plan 04:** the post-fix Step 9 grep won't see the worktree noise. Acceptance criterion "Step 9 returns empty" applies cleanly.

**GNOME 50.1 `Shell.Eval` is disabled** (returned `(false, '')`) — Activities screenshot was used as fallback per Option B in the diagnostic skeleton. Future Wayland-native readbacks on this rig should default to screenshots / Looking Glass rather than `gdbus Eval`.

## Notes for Plan 02

- All 5 drift sites confirmed, no surprises. Plan 02's task list (constants.py, __main__.py × 2, mpris2.py, Makefile × 4, .desktop rename) covers them all.
- The `Makefile` icon paths reference `musicstreamer/assets/org.example.MusicStreamer.svg` — a file that doesn't exist (per RESEARCH Pitfall 1). Plan 02's Makefile fix should also correct the path to point at the real `packaging/linux/org.lightningjim.MusicStreamer.png` (and switch the install command from `.svg` to `.png` accordingly).

## Notes for Plan 04 UAT

- Force-quit BEFORE screenshot exists at `screenshots/61-01-pre-fix-forcequit.png` — Plan 04's AFTER shot of the same dialog is the canonical D-16 sign-off.
- Provoke method that worked: `kill -STOP $(pgrep -f musicstreamer)`, wait 5–15s for shell detection, screenshot, `kill -CONT` to resume. Plan 04 should reuse this exact recipe.
- Activities BEFORE screenshot at `screenshots/61-01-pre-fix-activities.png` — Plan 04's AFTER shot of Activities is the SC #2 sign-off.
- GNOME 50.1's `Shell.Eval` lockout means Plan 04's `gdbus`-based POST-FIX readback (if attempted) will return `(false, '')`. The screenshots are the binding evidence; gdbus is optional/skippable on this rig.

## Acceptance criteria status

- [x] `61-DIAGNOSTIC-LOG.md` exists with `## PRE-FIX` section
- [x] Steps 1–10 have output / screenshot references
- [x] Session type recorded (`wayland`, informational)
- [x] `_GTK_APPLICATION_ID` placeholder confirmed via force-quit screenshot
- [x] `ls ~/.local/share/applications/` + icons recorded
- [x] Install marker absence confirmed
- [x] MPRIS bus name baseline recorded
- [x] Step 9 drift-site grep returns predicted set
- [x] Kyle approved → resume signal received

## Next: Wave 2 — Plan 02

Dispatching the autonomous executor for the rename + drift-guard test plan.
