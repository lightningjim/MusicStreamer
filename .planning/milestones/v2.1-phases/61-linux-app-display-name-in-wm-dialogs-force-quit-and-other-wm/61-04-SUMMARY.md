---
phase: 61
plan: 04
status: complete
outcome: failed-uat-routed-to-plan-05
captured: 2026-05-05
---

# Phase 61 Plan 04 — UAT SUMMARY (FAILED → routed to Plan 05)

## What ran

Kyle executed Plan 04's POST-FIX UAT on his Wayland (GNOME Shell) rig. All 13 numbered diagnostic steps were captured verbatim in `61-DIAGNOSTIC-LOG.md` under `## POST-FIX`. The phase-gating D-16 step (force-quit dialog reads "MusicStreamer") FAILED.

## Result vs expectation

| Step / SC | Expected | Observed |
|-----------|----------|----------|
| Step 9 — Force-quit dialog (D-16 gate, SC #1) | "MusicStreamer is not responding" | **"org.lightningjim.MusicStreamer is not responding"** — FAIL |
| Step 10 — Activities + Alt-Tab (SC #2) | "MusicStreamer" | "MusicStreamer" — PASS (red herring; window-title fallback masked the failed app match) |
| Step 8 — MPRIS bus name (SC #3 amended) | `org.mpris.MediaPlayer2.musicstreamer` unchanged | unchanged — PASS |
| Step 7 — Install marker | present, content `desktop install v1 complete; app_id=org.lightningjim.MusicStreamer` | present — PASS |
| Step 4 — `~/.local/share/applications/` | both `org.example.*` and `org.lightningjim.*` `.desktop` files present | both present — PASS |
| Step 13 — Repo drift grep `org.example` | 0 hits in canonical sources | 0 hits — PASS |
| POST-FIX notes | — | "Also seeing the org.lightningjim.MusicStreamer as the toolbar and has the gear icon instead of the installed icon for it" |

## Diagnostic addendum (root cause discovered post-UAT)

Follow-up diagnostic captured 2026-05-05 (interactive session before Plan 05 was authored):

- **Qt is innocent.** `WAYLAND_DEBUG=client uv run python -m musicstreamer` produces `xdg_toplevel#42.set_title("MusicStreamer")` and `xdg_toplevel#42.set_app_id("org.lightningjim.MusicStreamer")` — exactly the right values; Plan 02's wiring is intact.
- **The .desktop install is correct.** `Gio.DesktopAppInfo.new("org.lightningjim.MusicStreamer.desktop")` finds the file; icon resolves to `~/.local/share/icons/hicolor/256x256/apps/org.lightningjim.MusicStreamer.png`; mode 0644.
- **The smoking gun is in the wayland trace's third line:**
  ```
  xdg_activation_v1#35.activate("gnome-shell/PyCharm 2026.1.1/8345-7-hurricane_TIME1382114", wl_surface#37)
  ```
  Qt forwarded a stale `XDG_ACTIVATION_TOKEN` inherited from PyCharm's terminal env. Mutter bound the new MusicStreamer surface to PyCharm's launch context, short-circuiting wayland-app-id → .desktop basename matching. Result: dock shows gear + raw app_id, force-quit dialog same.
- **Confirmed by experiment c2:** `gtk-launch org.lightningjim.MusicStreamer` (gnome-shell mints a fresh, scoped token) renders correct icon and name. So the .desktop and app_id wiring are fine; the bug is purely env-inheritance.
- **Confirmed by env probe:** PyCharm exports `XDG_ACTIVATION_TOKEN=gnome-shell/PyCharm 2026.1.1/...` and `DESKTOP_STARTUP_ID=<same>` into every child shell.

## Why Step 10 (Activities/Alt-Tab) "PASSED" despite the same underlying failure

Activities tile labels and Alt-Tab switcher labels fall back to `meta_window_get_title()` when app matching fails. Qt set the window title to "MusicStreamer" via `setApplicationDisplayName`, so those surfaces look correct even though mutter's app↔.desktop match failed. Only the dock and force-quit dialog reveal the bug because they show app name + icon directly (not window title). Step 10's PASS was a false positive driven by title-vs-app-name conflation; the real app match was failing across all surfaces.

## Why Plan 04 alone could not close BUG-08

Plan 04 was scoped as UAT-only — no code change, just confirm Plans 02+03 produced the expected user-visible behavior. The failure is not in Plans 02/03 (those shipped correctly); it is a separate inheritance bug that Plans 02/03 did not address because the diagnostic that would have surfaced it was not run until Plan 04 UAT.

## Routing

A new plan was authored: `61-05-PLAN.md` — strip `XDG_ACTIVATION_TOKEN` and `DESKTOP_STARTUP_ID` from `os.environ` at the top of `_run_gui()` before any Qt code runs, plus 2 unit tests, plus a UAT re-run from the previously-failing PyCharm-terminal launch path. Plan 05 will append a `## POST-FIX-2` section to `61-DIAGNOSTIC-LOG.md` with Kyle's confirmation that the D-16 gate flips PASS.

## Sign-off

- D-16 gate (Step 9 force-quit dialog reads "MusicStreamer"): **FAIL**
- SC #2 (Activities/Alt-Tab consistency): PASS (but red herring — see analysis above)
- SC #3 amended (MPRIS bus name unchanged): PASS
- Pitfall 3 layered verification (Step 11): FAIL (D-16 gate failure invalidates the layered pass)
- ROADMAP entry updated: 61-04 annotated with failure cause; 61-05 added as gap-closure
- Side-discovery (housekeeping): `~/.local/share/applications/org.example.MusicStreamer.desktop` removed by user during diagnostic (was redundant; not the cause of the bug)

**Overall:** Phase 61 / BUG-08 → **NOT CLOSED — gap-closure routed to Plan 05**

## Commits

No commits — Plan 04 was UAT-only. The diagnostic addendum captured here came from an interactive ad-hoc session, not from a tracked plan run; it is preserved in `61-DIAGNOSTIC-LOG.md` POST-FIX and in this SUMMARY for traceability.
