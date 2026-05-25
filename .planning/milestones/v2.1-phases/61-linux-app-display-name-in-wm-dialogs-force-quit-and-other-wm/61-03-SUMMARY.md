---
phase: 61
plan: 03
status: complete
captured: 2026-05-05
---

# Phase 61 Plan 03 — Self-Install Module SUMMARY

## What shipped

A new Linux self-install routine (`musicstreamer/desktop_install.py`) wired into the GUI startup path before `QApplication(...)`, so the very first `uv run musicstreamer` after Plans 02+03 land writes the renamed `.desktop` file + icon into `~/.local/share/applications/` and `~/.local/share/icons/hicolor/256x256/apps/`. The routine is one-shot (marker-guarded), idempotent, atomic (`os.replace`), and platform-gated (no-op off Linux).

## Files created

| Path | LOC | Purpose |
|------|-----|---------|
| `musicstreamer/desktop_install.py` | ~165 | `ensure_installed()` entry point, `_do_install()`, `_atomic_copy()`, `_best_effort()`, `_write_marker()`, `_xdg_data_home()`, `_install_marker()` |
| `tests/test_desktop_install.py` | ~175 | 6 unit tests with `tmp_path` + `monkeypatch.setenv("XDG_DATA_HOME", ...)` |
| `tests/test_main_run_gui_ordering.py` | ~50 | 2 source-parsing tests asserting `Gst.init < ensure_installed < QApplication` ordering in `_run_gui` |

## Files modified

| Path | Change |
|------|--------|
| `musicstreamer/__main__.py` | Added `desktop_install` import + `ensure_installed()` call between `Gst.init(None)` and `migration.run_migration()` (lines 145–146) |
| `musicstreamer/subprocess_utils.py` | Added `_run(args, **kwargs)` Windows-aware mirror of `subprocess.run` (PKG-03 compliance hub now covers blocking calls too) |

## Commits

- `981048a` — `feat(61-03): add musicstreamer/desktop_install.py — XDG self-install for .desktop + icon`
- `892d5fb` — `test(61-03): unit tests for desktop_install — first-launch, idempotency, off-linux, preservation, hooks, missing-tool tolerance`
- `4d3cb3c` — `feat(61-03): wire desktop_install.ensure_installed() into _run_gui startup`
- `6c56909` — `refactor(61-03): route desktop_install subprocess calls through subprocess_utils._run (PKG-03)`

## Test results (Phase 61 surface — all green)

```
tests/test_desktop_install.py            6 passed
tests/test_constants_drift.py            4 passed (regression check — Plan 02 baseline preserved)
tests/test_main_run_gui_ordering.py      2 passed
tests/test_pkg03_compliance.py           green (subprocess routing through subprocess_utils._run)
                                        ─────────
                                         12 passed
```

## Deviations from PLAN.md

- **`subprocess_utils._run` added (not in original plan).** PLAN 03 Task 1 sketched `_best_effort` calling `subprocess.run` directly. The PKG-03 compliance test (`tests/test_pkg03_compliance.py::test_no_raw_subprocess_in_musicstreamer`) forbids that pattern anywhere in `musicstreamer/` outside `subprocess_utils.py`. Resolved by extending `subprocess_utils.py` with a `_run` helper (Windows-aware mirror of `subprocess.run`) and routing `desktop_install._best_effort` through it. Tests updated to `monkeypatch.setattr(desktop_install.subprocess_utils, "_run", ...)`. Captured in `deferred-items.md` Plan 03 deferrals.
- **PKG-03 docstring trap.** The compliance regex (`\bsubprocess\.(Popen|run|call)\b`) matched a docstring sentence that mentioned `subprocess.run` by name to explain the routing. Rephrased to avoid the literal token; future hardening of the regex (AST-based) is noted in `deferred-items.md` as low-priority.

## Notes for Plan 04 UAT

After Kyle launches `uv run musicstreamer` once on his Wayland rig (the run that triggers first-launch self-install):

1. **Marker file present:** `ls -la ~/.local/share/musicstreamer/.desktop-installed-v1` should show the file with content `desktop install v1 complete; app_id=org.lightningjim.MusicStreamer`. This is the layered-verification signal (RESEARCH §Pitfall 3) that distinguishes "fix worked" from "old `org.example.*` file coincidentally satisfied the lookup."
2. **Renamed `.desktop` installed:** `ls -la ~/.local/share/applications/org.lightningjim.MusicStreamer.desktop`. The OLD `org.example.MusicStreamer.desktop` will ALSO still be there (D-11 declined stale-file cleanup) — Kyle can `rm` it manually if desired.
3. **Icon in 256x256 bucket:** `ls -la ~/.local/share/icons/hicolor/256x256/apps/org.lightningjim.MusicStreamer.png`. Pre-existing icons from Kyle's manual install (per Plan 01 BEFORE diagnostic) are in 64/128/256 buckets — the install routine's `if not icon_dst.exists(): copy` guard will skip the 256 bucket cleanly.
4. **Force-quit dialog reads "MusicStreamer":** the canonical D-16 sign-off. Same provoke recipe as Plan 01: `kill -STOP $(pgrep -f musicstreamer)`, wait 5–15s, screenshot, `kill -CONT`. Save to `screenshots/61-04-post-fix-forcequit.png`.
5. **Activities/Alt-Tab show "MusicStreamer":** screenshot Activities (Super key) post-launch — the tile name should be "MusicStreamer", not the placeholder. Save to `screenshots/61-04-post-fix-activities.png`.
6. **MPRIS bus name unchanged:** `busctl --user list | grep musicstreamer` still shows `org.mpris.MediaPlayer2.musicstreamer` (D-04 invariant; Plan 02 confirmed; Plan 04 re-confirms post-rename).
7. **Step 9 grep clean:** `grep -rn 'org\.example' musicstreamer/ Makefile packaging/linux/` returns empty (Plan 02 closed all 5 drift sites; the orphan worktrees were pruned during Plan 01).

Plan 04 PLAN.md still has X11-isms (`xprop`, "X11 rig" framing, Wayland-as-side-effect notes) — those need to be flipped to Wayland-first before Wave 4 dispatches.

## Acceptance criteria status

- [x] `musicstreamer/desktop_install.py` exists with `ensure_installed()` entry point
- [x] No-op on non-Linux (test_no_op_off_linux green)
- [x] Idempotent via marker (test_idempotent_via_marker green)
- [x] Atomic write via tmp + `os.replace`
- [x] Existing user-modified files preserved (test_existing_files_preserved green)
- [x] Best-effort hooks invoked (test_cache_hooks_called_best_effort green)
- [x] Missing tool tolerated (test_missing_cache_tool_does_not_raise green)
- [x] Wired into `__main__.py::_run_gui` BEFORE `QApplication(...)`
- [x] Ordering sanity test in place (test_main_run_gui_ordering green)
- [x] PKG-03 compliance preserved (subprocess routing through `subprocess_utils._run`)
- [x] Drift-guard tests still pass (no regression on Plan 02 baseline)
- [x] No new `org.example.MusicStreamer` literals in `musicstreamer/`

## Next: Plan 04 patch + Wave 4 UAT

1. Patch `61-04-PLAN.md` to flip X11-isms to Wayland-native (drop `xprop`, replace with `gdbus`/Looking Glass/screenshots; remove "GNOME on Xorg" gate; flip the "Wayland is side-effect" memo to "X11 is out of scope").
2. Surface the Wave 4 UAT checkpoint to Kyle: launch `uv run musicstreamer`, run the POST-FIX diagnostic, capture screenshots, paste into `61-DIAGNOSTIC-LOG.md`'s `## POST-FIX` section, sign off.
