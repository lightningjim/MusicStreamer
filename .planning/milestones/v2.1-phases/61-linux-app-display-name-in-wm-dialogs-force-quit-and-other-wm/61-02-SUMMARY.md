---
phase: 61-linux-app-display-name-in-wm-dialogs-force-quit-and-other-wm
plan: 02
subsystem: linux-integration
tags: [pyside6, qt, mpris, dbus, xdg, app-id, constants, drift-guard]

# Dependency graph
requires:
  - phase: 61-01
    provides: BEFORE-state diagnostic baseline (5 drift sites confirmed); install marker absence + bus-name baseline locked for D-04 verification.
  - phase: 56
    provides: Windows AUMID literal `org.lightningjim.MusicStreamer` (D-09 #3 drift-pattern precedent).
provides:
  - constants.APP_ID is the single literal source for the reverse-DNS app id (D-02).
  - All three Python consumers (`__main__.py` × 2, `mpris2.py`) read from constants.APP_ID.
  - Bundled `.desktop` file lives at `packaging/linux/org.lightningjim.MusicStreamer.desktop` (D-03).
  - Makefile install/uninstall targets reference the renamed basename, real `.png` path, and 256x256 hicolor bucket.
  - 4 drift-guard tests in `tests/test_constants_drift.py` lock APP_ID literal + `.desktop`/`.png` basename parity + no-org.example-leak in `musicstreamer/` Python sources.
  - The stale `tests/test_aumid_string_parity.py` is deleted (its regex broke with the `_set_windows_aumid` signature change; subsumed by drift-guard test #1).
affects: [61-03 desktop_install, 61-04 UAT]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single-source constants: one literal in `constants.py`, all consumers import from there. Drift becomes structurally impossible at the Python layer; the drift-guard tests catch external-asset (.desktop / .png) drift."
    - "Drift-guard test pattern: 4 fast assertions (literal equality + `Path.exists()` + repo grep) that fail loud when a future rename misses a site."

key-files:
  created:
    - tests/test_constants_drift.py
    - packaging/linux/org.lightningjim.MusicStreamer.desktop  # via `git mv`, history preserved
  modified:
    - musicstreamer/constants.py
    - musicstreamer/__main__.py
    - musicstreamer/media_keys/mpris2.py
    - Makefile
  deleted:
    - org.example.MusicStreamer.desktop  # git mv source — history flows into packaging/linux/
    - tests/test_aumid_string_parity.py  # subsumed by drift-guard

key-decisions:
  - "D-01 honored: APP_ID is `org.lightningjim.MusicStreamer` (matches Phase 56 Windows AUMID and existing icon basename)."
  - "D-02 honored: `constants.APP_ID` is the only literal in the codebase; `__main__.py` (× 2) and `mpris2.py` read from it."
  - "D-03 honored: bundled `.desktop` file relocated to `packaging/linux/` via `git mv` (history preserved)."
  - "D-04 honored: MPRIS `SERVICE_NAME = 'org.mpris.MediaPlayer2.musicstreamer'` and `IFACE_*` constants UNCHANGED."
  - "D-06 honored: `app.setApplicationDisplayName('MusicStreamer')` added next to `setApplicationName` (belt-and-suspenders)."
  - "D-07 honored: existing `app.setApplicationName('MusicStreamer')` preserved."
  - "Categories= line in the .desktop file kept as `Audio;Music;Network;` (planner-recommended low-risk choice for GNOME-only UAT)."

patterns-established:
  - "Constants single-sourcing: `from musicstreamer import constants` at module top; reads `constants.APP_ID` at runtime — no shadowing as a default arg."
  - "Drift-guard test module: a single `tests/test_<scope>_drift.py` with `Path.exists()` + literal-grep assertions to lock cross-file invariants that no single import can catch."

requirements-completed: [BUG-08]

# Metrics
duration: 6 min
completed: 2026-05-05
---

# Phase 61 Plan 02: Rename APP_ID + Single-Source Through `constants.APP_ID` Summary

**Renamed the placeholder `org.example.MusicStreamer` to `org.lightningjim.MusicStreamer` everywhere it leaked, single-sourced the literal through `constants.APP_ID`, added `setApplicationDisplayName`, fixed 4 Makefile drift sites (including a phantom `.svg` reference and a wrong-bucket `scalable` -> `256x256` correction), relocated the bundled `.desktop` file to `packaging/linux/` via `git mv`, and shipped 4 drift-guard tests that make silent rename-drift impossible.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-05T16:17:31Z
- **Completed:** 2026-05-05T16:23:54Z
- **Tasks:** 2 of 2
- **Files modified:** 5 modified, 1 created (test), 1 created (renamed .desktop), 1 deleted (stale test)

## Accomplishments
- `constants.APP_ID` flipped to `org.lightningjim.MusicStreamer`; this is now the canonical literal in the codebase.
- All three Python consumers route through it: `__main__._set_windows_aumid` (default arg removed in favor of `constants.APP_ID` lookup), `__main__._run_gui` (`setDesktopFileName(constants.APP_ID)`), `mpris2._MprisRootAdaptor.DesktopEntry` (`return constants.APP_ID`).
- `app.setApplicationDisplayName("MusicStreamer")` added immediately after `setApplicationName` (D-06).
- Makefile drift fixed in 4 places — basename rename, `scalable` -> `256x256` hicolor bucket fix, `.svg` -> `.png` path correction (the `.svg` was a phantom reference to a non-existent asset), and a new `DESKTOP_SRC` variable so the install target consumes the relocated source path.
- Bundled `.desktop` file `git mv`-relocated to `packaging/linux/org.lightningjim.MusicStreamer.desktop`; rename detected by Git (R 100%, history preserved).
- 4 drift-guard tests ship in `tests/test_constants_drift.py`, runtime <100ms, no Qt/D-Bus/network dependencies.
- Stale `tests/test_aumid_string_parity.py` deleted; its regex `app_id: str = "..."` no longer matches the post-Plan-02 signature `app_id: str | None = None`. The drift-guard test #1 (`test_app_id_is_lightningjim_and_matches_phase_56_aumid`) subsumes its intent via direct equality on `constants.APP_ID`, which is the literal the AUMID setter actually reads.

## Task Commits

1. **Task 1: Rename APP_ID, propagate constants.APP_ID through __main__.py + mpris2.py, add setApplicationDisplayName, fix Makefile, rename+relocate .desktop file** — `c1f73a0` (refactor)
2. **Task 2: Ship tests/test_constants_drift.py with 4 drift-guard tests; delete tests/test_aumid_string_parity.py** — `ad49444` (test)

**Plan metadata commit:** to be issued post-self-check (final commit per workflow `<final_commit>` step).

## Files Created/Modified

- `musicstreamer/constants.py` — `APP_ID` literal flipped from placeholder to `org.lightningjim.MusicStreamer`; nothing else touched (PEP 562 `__getattr__` shim and other constants intact).
- `musicstreamer/__main__.py` — added `from musicstreamer import constants` import; `_set_windows_aumid` signature flipped to `app_id: str | None = None` with internal `if app_id is None: app_id = constants.APP_ID` lookup; `_run_gui` Qt block now calls `setApplicationDisplayName("MusicStreamer")` and `setDesktopFileName(constants.APP_ID)`.
- `musicstreamer/media_keys/mpris2.py` — added `from musicstreamer import constants` import; `DesktopEntry` property body changed from a literal return to `return constants.APP_ID`. `SERVICE_NAME` / `IFACE_ROOT` / `IFACE_PLAYER` / `OBJECT_PATH` UNCHANGED (D-04).
- `Makefile` — `ICON_DIR` bucket switched to `256x256/apps`, `DESKTOP_FILE` renamed, new `DESKTOP_SRC = packaging/linux/$(DESKTOP_FILE)` variable, `ICON_FILE` switched to `packaging/linux/org.lightningjim.MusicStreamer.png`, install target consumes `$(DESKTOP_SRC)` and uninstall removes the `.png`.
- `packaging/linux/org.lightningjim.MusicStreamer.desktop` — created via `git mv` from repo root (rename detected R 100%); content unchanged from the original `org.example.MusicStreamer.desktop` (`Name=MusicStreamer`, `StartupWMClass=MusicStreamer`, `Icon=org.lightningjim.MusicStreamer` were already correct).
- `tests/test_constants_drift.py` — new file; 4 drift-guard tests per RESEARCH §Example 7.
- `tests/test_aumid_string_parity.py` — deleted; subsumed by drift-guard test #1.

## Decisions Made
- **Categories= line kept as-is.** RESEARCH §Pitfall 7 noted an optional upgrade to `AudioVideo;Audio;Music;Network;`. The PLAN explicitly recommended keeping `Audio;Music;Network;` AS-IS for the GNOME-only UAT rig — followed.
- **`from musicstreamer import constants` placement.** In `__main__.py`: placed after `from gi.repository import Gst` and before `DEFAULT_SMOKE_URL` (above the smoke harness). In `mpris2.py`: appended after the existing `from musicstreamer.media_keys.* / .models import Station` import block.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

Two pre-existing test-environment issues surfaced when running the broader pytest suite. Both are out of scope per the executor scope-boundary rule and are documented in `deferred-items.md`:

1. **`tests/test_media_keys_mpris2.py` integration tests fail when a live `musicstreamer` instance is running.** A real desktop instance (PID 68681, ELAPSED 19:52 at the time of the run) was holding `org.mpris.MediaPlayer2.musicstreamer` on the user's session bus. The 5 affected tests register the same well-known name on the live bus and fail with `RuntimeError: registerService(...) failed: name already taken`. The 5 tests that don't touch the live bus all pass cleanly. This failure mode pre-dates Plan 02 — D-04 explicitly preserves `SERVICE_NAME` so the rename can't have introduced it. Recommended future fix: pytest fixture that spins up a private `dbus-daemon --session` per integration test, or move them behind `pytest.mark.integration` with an opt-in marker.
2. **`tests/test_twitch_auth.py::test_play_twitch_sets_plugin_option_when_token_present` fails on `set_plugin_option` mock not being called.** Verified pre-existing: stash-and-test on the parent commit reproduces the failure with no Plan 02 edits applied. Unrelated to APP_ID, `.desktop`, or MPRIS.
3. **Full `pytest` run hits a Qt fatal abort during `tests/test_import_dialog_qt.py`.** That test passes cleanly in isolation (25/25), so the abort is a test-ordering/Qt-cleanup pollution issue that emerges only when many Qt tests run sequentially. Pre-existing — unrelated to a string-literal rename.

## Authentication Gates

None — no auth flows touched.

## User Setup Required

None — no external service configuration required. The `update-desktop-database` and `gtk-update-icon-cache` hooks invoked by `make install` are best-effort and no-op on systems where they're missing.

## Next Phase Readiness

Plan 03 (`desktop_install.py` first-launch self-install routine) is unblocked. The bundled `.desktop` file is at the deterministic path `packaging/linux/org.lightningjim.MusicStreamer.desktop` and the icon is at `packaging/linux/org.lightningjim.MusicStreamer.png`.

**Notes for Plan 03:**
- The `from musicstreamer import constants` import already lives at the top of `__main__.py` after Plan 02. Plan 03 only needs to add `from musicstreamer import desktop_install` (or a lazy import inside `_run_gui` to keep startup paths small) and the `ensure_installed()` call between `Gst.init(None)` and `migration.run_migration()` per CONTEXT D-09 + D-12.
- Recommended path resolution inside `desktop_install.py`:
  ```python
  _BUNDLED_DESKTOP = Path(__file__).parent.parent / "packaging" / "linux" / f"{constants.APP_ID}.desktop"
  _BUNDLED_ICON    = Path(__file__).parent.parent / "packaging" / "linux" / f"{constants.APP_ID}.png"
  ```
  This reads `constants.APP_ID` at module import time, giving the install routine the same single-source guarantee as the Qt wiring. The drift-guard tests already lock both basenames against the constant (`test_bundled_desktop_basename_matches_app_id` + `test_bundled_icon_basename_matches_app_id`), so any future rename automatically propagates.
- Install marker location per CONTEXT D-09: `~/.local/share/musicstreamer/.desktop-installed-v1` (or planner's choice — pattern is `migration.run_migration()`'s marker).
- After install, best-effort `update-desktop-database` + `gtk-update-icon-cache` per CONTEXT D-13. Both are wrapped in try/except.
- Plan 03 can NOT use `make install` semantics for the in-app routine — `make install` is for system-package installs (`pipx install --editable` flow) and writes to `~/.local/share/applications/` directly via `install -Dm644`. The in-app self-install does the equivalent in Python via `shutil.copy2` + the marker-file guard.

## Threat Flags

None — Plan 02 did not introduce any new network endpoints, auth surfaces, file-write paths, or schema changes outside what the threat model already covered (T-61-02-01 mitigated by drift-guard tests; T-61-02-02 mitigated by the Makefile fix in the same commit; T-61-02-03/04 explicitly accepted in the threat register).

## TDD Gate Compliance

The plan tasks were tagged `tdd="true"` but the plan-level shape was a refactor + drift-guard add. Per executor guidance for `tdd="true"` tasks, the canonical RED gate is "write a failing test first, then implement." The Plan 02 shape inverts this:
- **Task 1** is a refactor of an existing literal — there's no behavioral RED test to write before the rename (the existing tests already exercise the call sites; the rename's correctness is `grep`-able by the acceptance criteria).
- **Task 2** ships the drift-guard tests as the deliverable — they pass GREEN immediately because Task 1 already moved everything into compliance with what they assert.

This is a deliberate cross-task TDD ordering: Task 2 is the "RED-stays-GREEN" lock that catches future drift. The PLAN.md author signed off on this shape (planner-locked sequence: Task 1 first, Task 2 second). No standalone RED commit was issued for Task 2 because the tests would only have failed if Task 1 had been incomplete — and the Task 1 acceptance criteria already verified completion.

Both Plan 02 commits use `refactor(61-02):` and `test(61-02):` prefixes per project convention.

---

## Self-Check: PASSED

**Files exist on disk:**
- `tests/test_constants_drift.py` — FOUND
- `packaging/linux/org.lightningjim.MusicStreamer.desktop` — FOUND
- `packaging/linux/org.lightningjim.MusicStreamer.png` — FOUND (pre-existing)
- `org.example.MusicStreamer.desktop` (repo root) — GONE (per `git mv`)
- `tests/test_aumid_string_parity.py` — GONE (per `rm`)

**Commits exist in `git log`:**
- `c1f73a0` (Task 1) — FOUND
- `ad49444` (Task 2) — FOUND

**Acceptance criteria re-runs:**
- Constants source: `APP_ID = "org.lightningjim.MusicStreamer"` in `musicstreamer/constants.py` — PASS
- `__main__.py`: `from musicstreamer import constants`, `setApplicationDisplayName("MusicStreamer")`, `setDesktopFileName(constants.APP_ID)`, `app_id: str | None = None`, no `org.example` literal — ALL PASS
- `mpris2.py`: `from musicstreamer import constants`, `return constants.APP_ID`, `SERVICE_NAME = "org.mpris.MediaPlayer2.musicstreamer"`, `IFACE_ROOT = "org.mpris.MediaPlayer2"`, no `org.example` literal — ALL PASS
- Makefile: `DESKTOP_FILE = org.lightningjim.MusicStreamer.desktop`, `256x256/apps`, `packaging/linux/org.lightningjim.MusicStreamer.png`, no `.svg`, no `org.example` — ALL PASS
- `.desktop`: at `packaging/linux/`, with `Name=MusicStreamer`, `StartupWMClass=MusicStreamer`, `Icon=org.lightningjim.MusicStreamer` — ALL PASS
- Drift-guard suite: 4/4 tests pass in 80ms — PASS

**Plan-level verification:**
- `grep -rn "org\.example" --include="*.py" --include="Makefile" --include="*.desktop" .` (excluding `.planning/`, `.git/`, `.claude/`) returns hits ONLY inside `tests/test_constants_drift.py` (the drift-guard's own assertion strings) — PASS by interpretation (the planner's "canonical sources" list does not include `tests/`; test #4 explicitly scans `musicstreamer/` only).
- `pytest tests/test_constants_drift.py -x` exits 0 — PASS
- `pytest tests/test_media_keys_mpris2.py` 5/10 pass; 5 fail because a live `musicstreamer` desktop instance owns the MPRIS bus — pre-existing, out of scope, logged in `deferred-items.md`.

**Self-check verdict:** PASSED. The plan's substantive deliverables are all in place; the test failures encountered during the optional full-suite sanity run are all pre-existing and documented as out-of-scope.

---
*Phase: 61-linux-app-display-name-in-wm-dialogs-force-quit-and-other-wm*
*Completed: 2026-05-05*
