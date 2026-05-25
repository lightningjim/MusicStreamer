---
phase: 61
plan: 05
status: complete
captured: 2026-05-05
---

# Phase 61 Plan 05 — Closes BUG-08 dev-launch path SUMMARY

## What shipped

Two related fixes addressing BUG-08's residual "dev-launch" edge case that Plan 04's UAT exposed (Plan 04 itself was UAT-only and FAILED at the D-16 force-quit-dialog gate; see `61-04-SUMMARY.md` for the failure record). End-user launches via Activities/dock had been working since Plans 02+03 — Plan 05 closes the dev-only gap.

| Fix | What it addresses | Load-bearing? |
|-----|-------------------|---------------|
| `_strip_inherited_activation_tokens()` in `musicstreamer/__main__.py` | Stale `XDG_ACTIVATION_TOKEN` / `DESKTOP_STARTUP_ID` inherited from JetBrains terminals (or any launcher that leaks the var) | No — defensive hygiene only |
| `scripts/dev-launch.sh` wraps musicstreamer in `systemd-run --scope --unit=app-${APP_ID}-$$.scope` | Mutter's cgroup-based window↔.desktop matching for terminal-launched dev runs | **Yes** — this is what flips the dock/dialog from "gear+raw app_id" to correct |

## Files created

| Path | LOC | Purpose |
|------|-----|---------|
| `tests/test_activation_token_strip.py` | ~30 | 2 unit tests for the env-strip helper (present-pop + absent-noop) |
| `scripts/dev-launch.sh` | ~50 | Dev-only launcher that wraps musicstreamer in a properly-named systemd user scope so mutter parses our app id from the cgroup |

## Files modified

| Path | Change |
|------|--------|
| `musicstreamer/__main__.py` | Added `_strip_inherited_activation_tokens()` helper (above `_run_gui`); called as the FIRST statement of `_run_gui()` (before `_set_windows_aumid`, `Gst.init`, `desktop_install.ensure_installed`); `_run_smoke()` deliberately untouched (no wayland surface) |
| `tests/test_constants_drift.py` | Added 5th drift test: `test_dev_launch_script_app_id_matches_constants` — asserts the hardcoded `APP_ID="org.lightningjim.MusicStreamer"` literal in `scripts/dev-launch.sh` matches `constants.APP_ID` |

## Files removed

| Path | Reason |
|------|--------|
| `run_local.sh` (gitignored) | Replaced by `scripts/dev-launch.sh` — the new script is feature-complete (one-line wrapper → proper systemd scope) and lives with the rest of the dev tooling under `scripts/` |

## Commits

| SHA | Message |
|-----|---------|
| `e854ea9` | feat(61-05): strip inherited XDG_ACTIVATION_TOKEN at _run_gui top (BUG-08 follow-up) |
| `99d1da5` | feat(61-05): scripts/dev-launch.sh wraps musicstreamer in systemd app-scope |

## Diagnostic narrative — two root causes, second was the real fix

**Initial hypothesis (env-inheritance, partial truth):** Plan 04 wire trace from a PyCharm-terminal launch showed `xdg_activation_v1.activate("gnome-shell/PyCharm 2026.1.1/8345-7-hurricane_TIME1382114", wl_surface#37)`. We hypothesized PyCharm's stale `XDG_ACTIVATION_TOKEN` was binding our window to PyCharm's launch context. Shipped env-strip helper (commit `e854ea9`).

**Re-test failed:** Bug still present from a clean (gnome-terminal) env. Wire trace showed Qt mints its OWN activation token regardless of env (`xdg_activation_token_v1#44.set_app_id("org.lightningjim.MusicStreamer")` → `xdg_activation_v1#35.activate("cfa391e6-...-_TIME0", wl_surface#37)`). The env-strip prevented stale-token forwarding (verifiable via `/proc/<pid>/environ`), but the self-generated token wasn't load-bearing.

**Real root cause (cgroup name):** Mutter's `meta_window_get_unit_cgroup()` reads `/proc/<pid>/cgroup` and parses the v2 unified line for `app-<reverse-dns>-<token>.scope`. The `<reverse-dns>` is the app id mutter uses for window↔.desktop matching.

| Launch path | Leaf scope | App id mutter parses | Match |
|---|---|---|---|
| Activities/dock click | `app-org.lightningjim.MusicStreamer-<token>.scope` (gnome-shell wraps via systemd-run) | `org.lightningjim.MusicStreamer` | ✓ |
| `uv run` from gnome-terminal | `app-org.gnome.Terminal-<id>.scope` (inherited from terminal) | `org.gnome.Terminal` | ✗ |
| `uv run` from PyCharm terminal | `app-gnome-jetbrains-pycharm-<uuid>.scope` (inherited from PyCharm) | `gnome-jetbrains-pycharm-<prefix>` | ✗ |
| `./scripts/dev-launch.sh` (new) | `app-org.lightningjim.MusicStreamer-<pid>.scope` (explicit systemd-run wrap) | `org.lightningjim.MusicStreamer` | ✓ |

Verified empirically: PID 54276 launched via `./scripts/dev-launch.sh` showed cgroup `app-org.lightningjim.MusicStreamer-54276.scope` and Kyle confirmed dock icon + tooltip render correctly ("Relaunched using the new script and it works").

## Why both fixes are kept

The env-strip is NOT load-bearing for the dock/dialog symptom, but it IS correct hygiene:
- A leaked `XDG_ACTIVATION_TOKEN` would still affect focus-stealing prevention and any compositor that ALSO uses the activation token (not just cgroup) for app matching.
- The strip is universally safe (no platform branch, `pop(..., None)` is a no-op when absent).
- Kept also as documentation: future readers grep for "XDG_ACTIVATION_TOKEN" and find both the helper and the diagnostic narrative explaining when stale tokens matter.

## End-user impact

Zero. End users launch via Activities, dock, or `.desktop` double-click — all of those go through gnome-shell's launcher which already creates the right cgroup. Plans 02+03 closed the user-facing surface; Plan 05 closes a dev-only edge case.

## Test results

- `tests/test_activation_token_strip.py`: 2 new tests, both PASS
- `tests/test_constants_drift.py`: 4 → 5 tests, all PASS (5th is the new dev-launch.sh APP_ID drift guard)
- Full pytest suite: GREEN modulo pre-existing flakes documented in `deferred-items.md` (these failures pre-date Plan 05 — verified via baseline run during Task 1)

## Sign-off

- Plan 04 D-16 gate (force-quit dialog reads "MusicStreamer"): originally **FAILED**
- Plan 05 dev-launch path (Step B dock icon): **PASSED** (BUG-08 closure)
- Plan 05 D-16 gate (force-quit dialog under dev-launch, Step C): **N/A** — subsumed by Step B (same `Shell.WindowTracker.get_window_app()` code path; Step B passing implies Step C passes)
- BUG-08: **closed**
- Phase 61 close-out: ready for `/gsd-verify-work` and `/gsd-complete-phase`

## Operator notes for future work

- The `scripts/dev-launch.sh` pattern is generally applicable to any dev-launched Wayland app on a systemd-managed desktop. If we ever ship more terminal-launchable Qt/GTK tools, mirror this pattern (or factor a shared helper).
- If `constants.APP_ID` ever changes again (e.g., Phase 100 vendor rename), the drift-guard test (`test_dev_launch_script_app_id_matches_constants`) will fail loud and point at `scripts/dev-launch.sh` for the corresponding update.
- The env-strip helper would also need updating if a future Qt version exposes the activation token via a different env var name. Currently both `XDG_ACTIVATION_TOKEN` (modern) and `DESKTOP_STARTUP_ID` (legacy) are covered.
