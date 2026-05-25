# Phase 61: Linux App Display Name in WM Dialogs - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Linux parallel to Phase 56 WIN-02. Make the GNOME force-quit dialog, Activities/Alt-Tab overview, and other shell surfaces that read the application's identity show **"MusicStreamer"** instead of the reverse-DNS app ID currently shown (`org.example.MusicStreamer`).

The bug surface is read-only — the shell consults the running window's app_id / WM_CLASS, looks up the matching `.desktop` file in XDG paths, and shows the file's `Name=` field. Today the lookup fails because (a) the placeholder `org.example` ID isn't a real registered identity, and (b) the bundled `.desktop` file lives only at the repo root, never installed where GNOME Shell can find it. Fix is two halves: rename the placeholder to the real ID and self-install the `.desktop` file + icon on first launch.

**In scope:**
- Rename the reverse-DNS app ID from `org.example.MusicStreamer` → `org.lightningjim.MusicStreamer` (matches the Phase 56 Windows AUMID and the existing `packaging/linux/org.lightningjim.MusicStreamer.png` icon filename).
- Single source of truth via `musicstreamer.constants.APP_ID`; `__main__.py::_set_windows_aumid` and `setDesktopFileName` both read from it.
- Update Qt wiring: `app.setApplicationName("MusicStreamer")` (already present), `app.setDesktopFileName(constants.APP_ID)`, add `app.setApplicationDisplayName("MusicStreamer")`.
- Update `musicstreamer/media_keys/mpris2.py::DesktopEntry` property to return `constants.APP_ID`.
- Rename `org.example.MusicStreamer.desktop` → `org.lightningjim.MusicStreamer.desktop` at the repo root (or move into `packaging/linux/`); ensure `Name=MusicStreamer`, `StartupWMClass=MusicStreamer`, `Icon=org.lightningjim.MusicStreamer`, `Exec=` correct.
- New self-install routine in `musicstreamer/migration.py` (or sibling slot, called from `__main__.py::_run_gui` between `Gst.init()` and `migration.run_migration()`): copy bundled `.desktop` file into `~/.local/share/applications/<app_id>.desktop` and the 1024×1024 PNG into `~/.local/share/icons/hicolor/<size>/apps/<app_id>.png` if not already present. One-shot install marker (idempotent; no every-launch refresh).
- Diagnose-first artifact: a `61-DIAGNOSTIC-LOG.md` (Phase 56-03 convention) capturing the *before* state on Kyle's Wayland rig (Wayland-native window-property readback, screenshots of Activities + force-quit dialog showing the placeholder name, `ls ~/.local/share/applications/`, session type) and the *after* state once the fix is shipped.
- UAT on Kyle's Wayland (GNOME Shell) rig: trigger the GNOME force-quit dialog (or equivalent surface), confirm the dialog shows "MusicStreamer" with the correct icon, confirm Activities/Alt-Tab consistency.

**Out of scope:**
- Linux installer / packaging (deb / rpm / Flatpak / AppImage) — deferred. The self-install on first launch covers the dev-rig case; proper packaging is a future Linux-packaging phase.
- X11-specific behavior. Kyle's deployment is Wayland (GNOME Shell), never X11. X11-only surfaces (e.g., `xprop`-readable WM_CLASS without a Wayland-native equivalent) are out of scope.
- Migrating SQLite data, settings ZIPs, or D-Bus interface names. The MPRIS bus name (`org.mpris.MediaPlayer2.musicstreamer`) is unchanged — it follows the MPRIS spec convention, not the reverse-DNS app ID. Only the MPRIS `DesktopEntry` *property value* changes.
- Stale-file cleanup (removing any orphan `org.example.MusicStreamer.desktop` from `~/.local/share/applications/`). Discussed and explicitly declined — install routine is additive only.
- Re-running the install routine on every launch. Single one-shot install marker; user is trusted not to muck with the installed file.
- Per-DE behavior matrices (KDE Plasma, XFCE, Cinnamon). Target is GNOME Shell on X11 only.
- Code signing / sandboxing / Flatpak manifest work — far out of scope.

### ROADMAP Amendment

ROADMAP.md Phase 61 success criterion #3 reads:
> *"The app ID used for D-Bus / MPRIS / desktop integration is unchanged (only the user-facing display name changes)."*

This is **amended** by D-01..D-04. Replacement criterion:
> *"The app ID is migrated from the placeholder `org.example.MusicStreamer` to `org.lightningjim.MusicStreamer` (matching the Phase 56 Windows AUMID). The MPRIS bus name (`org.mpris.MediaPlayer2.musicstreamer`) and the D-Bus interface names (`org.mpris.MediaPlayer2`, `org.mpris.MediaPlayer2.Player`) are unchanged. No external client depends on the old `org.example.*` literal — it was a placeholder shipped only in dev runs."*

Rationale: the spirit of #3 was "don't break integrations." The rename does not break any integration; it fixes brand drift between Linux and Windows. Re-confirmed during discussion (Area 4 follow-up).

</domain>

<decisions>
## Implementation Decisions

### App ID branding (Area 1)

- **D-01: Reverse-DNS app ID is `org.lightningjim.MusicStreamer`.** Same string as the Phase 56 Windows AUMID; matches the existing `packaging/linux/org.lightningjim.MusicStreamer.png` icon filename. The `org.example.*` literal is a placeholder being retired everywhere it appears.
- **D-02: `musicstreamer.constants.APP_ID` is the single source of truth.** All call sites read from it: `__main__.py::_run_gui` (`setDesktopFileName(constants.APP_ID)`), `__main__.py::_set_windows_aumid` (drop the hardcoded default arg, read `constants.APP_ID`), `media_keys/mpris2.py::_MprisRootAdaptor.DesktopEntry` (return `constants.APP_ID`). One literal in the codebase, no drift possible.
- **D-03: Rename the bundled `.desktop` file in lockstep.** `org.example.MusicStreamer.desktop` → `org.lightningjim.MusicStreamer.desktop`. Inside the file: `Name=MusicStreamer` (already correct), `StartupWMClass=MusicStreamer` (already correct), `Icon=org.lightningjim.MusicStreamer` (already correct), `Exec=` (planner audits to make sure it points at the actual binary entry).
- **D-04: MPRIS bus name is NOT renamed.** `org.mpris.MediaPlayer2.musicstreamer` is the MPRIS spec-mandated busname pattern (`org.mpris.MediaPlayer2.<lowercase-friendly-suffix>`); it is not a reverse-DNS ID. Only the MPRIS `DesktopEntry` *property value* changes (D-02). All `IFACE_*` constants stay.

### Display-name lever (Area 2)

- **D-05: `.desktop` file lookup is the binding mechanism.** GNOME Shell force-quit reads `Name=` from the matching `.desktop` file (resolved via app_id / WM_CLASS → XDG search path). No Qt API can substitute for this. The phase MUST install the `.desktop` file in a discoverable location.
- **D-06: Add `app.setApplicationDisplayName("MusicStreamer")` next to the existing `setApplicationName` call.** Belt-and-suspenders for any Qt-internal surface that reads `applicationDisplayName` (window-title default, accessibility readouts). Does not change WM-class behavior; harmless one-liner.
- **D-07: Keep the existing `setApplicationName("MusicStreamer")`.** Already in place at `__main__.py:143`. Required by Qt convention; not removed.
- **D-08: Wayland app_id is the binding mechanism.** `setDesktopFileName(constants.APP_ID)` sets `xdg_toplevel.app_id` directly on Wayland; GNOME Shell reads that to look up the matching `.desktop` file. Researcher resolved (RESEARCH §Open Question #1): no `-name argv` injection needed; `_GTK_APPLICATION_ID` is the highest-priority match key and `setDesktopFileName` populates it. WM_CLASS is X11-only and is not a code-path this phase needs to defend.

### .desktop install strategy (Area 3)

- **D-09: Self-install on first launch.** Routine lives in `musicstreamer/migration.py` (or a sibling module called from `__main__.py::_run_gui` between `Gst.init()` and the existing `migration.run_migration()` call). Pattern mirrors `migration.run_migration()` — one-shot guarded by an install marker file (e.g., `~/.local/share/musicstreamer/.desktop-installed-v1`). Idempotent: no-op if marker present, copies + creates marker on first run.
- **D-10: Install both the `.desktop` file AND the icon.** Without the icon, force-quit shows a generic placeholder even with the right name. Source: `packaging/linux/org.lightningjim.MusicStreamer.png` (1024×1024). Target: `~/.local/share/icons/hicolor/<size>/apps/org.lightningjim.MusicStreamer.png` — planner picks the size bucket (256×256 or 512×512 are both reasonable).
- **D-11: No stale-file cleanup.** Install routine is additive only — does not remove any orphan `org.example.MusicStreamer.desktop` that earlier dev runs may have left in `~/.local/share/applications/`. User can clean those up manually if needed; not a phase responsibility. (Reviewed and declined during discussion.)
- **D-12: One-shot, not every-launch.** The install marker is checked once on first launch; subsequent launches skip the routine entirely. Trade-off: if the user manually edits the installed `.desktop`, the app won't refresh it. Acceptable — low-probability event, simple model. (Reviewed and declined during discussion.)
- **D-13: Run `update-desktop-database` / `gtk-update-icon-cache` if available.** Best-effort post-install hook so the shell picks up the new `.desktop` file without a relogin. Both tools are no-ops on systems where they're missing; wrap calls in try/except to keep them optional. (Claude's discretion — planner may choose to skip if it complicates the install routine.)

### Diagnose-first vs fix-first (Area 4)

- **D-14: Diagnose-first, Phase 56 pattern (Wayland-native).** First plan in the phase produces `61-DIAGNOSTIC-LOG.md` capturing the *before* state on Kyle's Wayland (GNOME Shell) rig:
  1. Session type — `echo $XDG_SESSION_TYPE` (expect `wayland`; this is informational, NOT a gate).
  2. GNOME Shell version — `gnome-shell --version`.
  3. Running window app_id readback — `gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval` against `global.get_window_actors()` to read `wm_class`, `gtk_application_id`, `sandboxed_app_id` (Wayland-native). Falls back to a screenshot of Activities showing the placeholder name if `Eval` is disabled on the user's GNOME (it's restricted on stock builds for security).
  4. Installed `.desktop` files — `ls ~/.local/share/applications/ | grep -i music` and `/usr/share/applications/ | grep -i music`.
  5. Installed icons — `ls ~/.local/share/icons/hicolor/*/apps/ | grep -i music`.
  6. Install marker presence — `ls ~/.local/share/musicstreamer/.desktop-installed-v1`.
  7. MPRIS bus name baseline — `busctl --user list | grep musicstreamer` (D-04 unchanged-bus-name verification).
  8. Repo grep for `org.example` literal — drift baseline.
  9. Screenshots — Activities thumbnail showing the placeholder name + force-quit dialog (provoke via `kill -STOP $(pgrep -f musicstreamer)` on a Wayland-native window, since `xkill` doesn't apply).
- **D-15: Code change ships in the same phase.** Unlike Phase 56 D-10 where the code change was contingent on the diagnostic, Phase 61's diagnostic is expected to confirm two known-broken conditions (placeholder app ID + missing install). The fix (rename + self-install) ships regardless.
- **D-16: UAT gate.** Phase is gated on Kyle's Wayland rig showing **"MusicStreamer"** in the GNOME force-quit dialog after a fresh `uv run musicstreamer` launch (which triggers the self-install on first run). Activities/Alt-Tab consistency check is included in the UAT script. Screenshots are valid evidence; `gdbus` window-property readback is the preferred quantitative signal when available.

### Claude's Discretion

- Exact name and module location of the install routine (e.g., `desktop_install.py` next to `migration.py`, or a new function in `migration.py` itself, or `musicstreamer/linux_install.py`). Planner picks; pure mechanism, no policy.
- Icon size bucket (256×256 vs 512×512 vs both). 256×256 is the common GNOME Shell default; 512×512 is fine if a single-bucket install is preferred.
- Whether the install marker is a sentinel file under `~/.local/share/musicstreamer/` or a per-feature marker (e.g., `desktop_installed_v1.flag`). Either works; `migration.py` already writes a marker for first-launch data migration so the pattern is established.
- Whether to run `update-desktop-database` and `gtk-update-icon-cache` after install (D-13). Best-effort hook; planner may skip if it adds noise.
- Where the `.desktop` file source lives — current location is repo root, but `packaging/linux/org.lightningjim.MusicStreamer.desktop` (next to the icon) reads cleaner. Planner picks during the rename plan.
- Whether to inject `-name MusicStreamer` into argv before `QApplication(...)` to force the X11 WM_CLASS to match `StartupWMClass=MusicStreamer`. Researcher confirms necessity; planner adds if needed.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 56 — Windows AUMID parallel (the precedent for this phase's structure)
- `.planning/phases/56-windows-di-fm-smtc-start-menu/56-CONTEXT.md` — Diagnose-first pattern (D-07/D-08), AUMID single-source intent (D-09 #3), the Phase 56 fix shape that this Linux parallel mirrors.
- `.planning/phases/56-windows-di-fm-smtc-start-menu/56-RESEARCH.md` — How the Phase 56 researcher resolved the diagnostic + Microsoft documentation references; same depth expected here for GNOME Shell / XDG specs.
- `.planning/phases/56-windows-di-fm-smtc-start-menu/56-03-DIAGNOSTIC-LOG.md` — The on-rig diagnostic-log artifact convention this phase follows.

### Source files this phase touches
- `musicstreamer/__main__.py` — `_set_windows_aumid` (lines 99–125, default-arg drops in favor of `constants.APP_ID` read), `_run_gui` (lines 142–144, `setDesktopFileName` reads `constants.APP_ID`, `setApplicationDisplayName` added). Also the call site for the new self-install routine.
- `musicstreamer/constants.py` — line 17, `APP_ID = "org.example.MusicStreamer"` → `APP_ID = "org.lightningjim.MusicStreamer"`. Single literal change; everything else reads from here.
- `musicstreamer/media_keys/mpris2.py` — line 104, `DesktopEntry` property hardcoded `"org.example.MusicStreamer"` → `return constants.APP_ID`. Bus name (`org.mpris.MediaPlayer2.musicstreamer`) and interface constants (`IFACE_*`) unchanged.
- `musicstreamer/migration.py` — pattern reference for the new self-install routine (one-shot, install-marker guarded).
- `musicstreamer/single_instance.py` — line 29, `SERVER_NAME = "org.lightningjim.MusicStreamer.single-instance"` is already on the new ID; reference only, no change.
- `org.example.MusicStreamer.desktop` (repo root) — renamed to `org.lightningjim.MusicStreamer.desktop`; planner may relocate into `packaging/linux/`.
- `packaging/linux/org.lightningjim.MusicStreamer.png` — icon source for self-install.

### Project-level
- `.planning/REQUIREMENTS.md` — `BUG-08` (this phase). Surfaced during Phase 50 UAT 2026-04-28.
- `.planning/ROADMAP.md` — Phase 61 entry. Success criteria #3 amended (see ROADMAP Amendment in domain section above).
- `.planning/PROJECT.md` — v2.1 milestone shape.
- `.planning/STATE.md` — current milestone progress.

### Reference docs the researcher should consult
- XDG Desktop Entry Specification — `Name`, `StartupWMClass`, `Icon` field semantics, XDG search path order.
- XDG Icon Theme Specification — `hicolor` bucket sizes, lookup chain.
- Qt 6 documentation — `QGuiApplication::setApplicationName`, `setApplicationDisplayName`, `setDesktopFileName` behavior on X11 vs. Wayland; whether Qt sets `WM_CLASS` from `applicationName` or `argv[0]` and how `-name` argv flag interacts.
- GNOME Shell — how the force-quit dialog resolves a window's display name from `WM_CLASS` / app_id.
- `update-desktop-database(1)` and `gtk-update-icon-cache(1)` — when (if ever) needed for shell to notice newly-installed entries.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`musicstreamer/migration.py::run_migration`** — established pattern for a one-shot first-launch routine guarded by a marker file. The `.desktop` self-install (D-09) clones the same shape: marker file under `~/.local/share/musicstreamer/`, idempotent, called from `__main__.py::_run_gui` before the GUI comes up.
- **`musicstreamer/__main__.py::_set_windows_aumid`** — already on `org.lightningjim.MusicStreamer` (default arg). Conversion to read `constants.APP_ID` is a one-line edit; the readback verification logic stays.
- **`musicstreamer/single_instance.py::SERVER_NAME`** — already on the new app ID (with the `.single-instance` suffix). Codebase already drifted toward `org.lightningjim`; this phase consolidates the rest.
- **`packaging/linux/org.lightningjim.MusicStreamer.png`** — 1024×1024 PNG, ready for install. No new icon authoring needed.
- **Existing `org.example.MusicStreamer.desktop`** — almost-correct content (`Name=MusicStreamer`, `StartupWMClass=MusicStreamer`, `Icon=org.lightningjim.MusicStreamer`); only the basename and the inferred `Exec=`/`Categories=` need an audit during the rename.

### Established Patterns
- **First-launch one-shot routine guarded by marker file** — `migration.run_migration()` (musicstreamer/migration.py). Self-install (D-09) reuses this idiom verbatim.
- **`sys.platform == "win32"` guards** — used throughout `media_keys/`, `subprocess_utils.py`, `__main__.py::_set_windows_aumid`. The Linux self-install routine uses the inverse guard (`sys.platform != "win32"` or `sys.platform.startswith("linux")` — planner picks).
- **Constants single-sourced in `constants.py`** — `APP_ID`, buffer constants (Phase 16), data paths, etc. Reading `constants.APP_ID` from `__main__.py` and `mpris2.py` follows the established discipline.
- **Phase 56 D-09 #3 AUMID-drift pattern** — Phase 56 explicitly flagged AUMID drift between `__main__.py` and `MusicStreamer.iss` as a future risk; D-02 here closes that risk by single-sourcing.

### Integration Points
- **`__main__.py::_run_gui` order matters.** `_set_windows_aumid()` MUST stay before `QApplication(...)` (Phase 43.1). The new self-install routine should run BEFORE `QApplication(...)` too (no Qt dependency, no need to wait), but AFTER `Gst.init(...)` is fine. Slot: between `Gst.init(None)` (line 131) and `migration.run_migration()` (line 134), or as a sibling call after `run_migration()` — both work.
- **`setDesktopFileName(...)` MUST run before any window is created.** Already correct in current code; just changes which constant is read.
- **MPRIS `DesktopEntry` property is queried by clients on demand.** No init-order constraint; the rename takes effect on the next `Properties.Get` call.
- **No DB / persistence touch.** Pure code rename + new install routine. SQLite untouched.

</code_context>

<specifics>
## Specific Ideas

- **The placeholder pattern `org.example.*` was always wrong** — it was a copy-paste artifact from Qt/PySide6 docs that never got updated when the app got a real owner identity. The rename is overdue, not just a Phase 61 fix.
- **`org.lightningjim.*` is the canonical brand** for everything: GitHub handle, Phase 56 Windows AUMID, existing icon filename, existing single-instance server name. The codebase has already been drifting toward this string; Phase 61 finishes the drift and locks `constants.APP_ID` as the single source.
- **GNOME Shell on X11 is the only UAT target** (per memory: "Linux X11 DPR=1.0"). Wayland coverage is incidental — `setDesktopFileName` sets the Wayland app_id for free, but no Wayland UAT step.
- **The diagnostic is expected to be a formality.** Two failure modes are already known by inspection (placeholder ID, missing install). The diagnostic captures concrete *before* readouts (xprop output, ls of `~/.local/share/applications/`) so the SUMMARY can show a clean before/after delta. Unlike Phase 56 where the diagnostic might pivot the fix, here it just documents.
- **Force-quit dialog is the binding UAT surface.** Activities/Alt-Tab consistency is a checked secondary surface. Anything else (per-DE, KDE Plasma, etc.) is out of scope.
- **No external client depends on `org.example.MusicStreamer`.** It was a placeholder shipped only in dev runs of a single-user app on Kyle's machine; the rename is safe by inspection.

</specifics>

<deferred>
## Deferred Ideas

### Deferred to future phases / re-visit later
- **Proper Linux installer / packaging** (deb / rpm / Flatpak / AppImage). The self-install on first launch covers the dev-rig case, but a packaged install would (a) put the `.desktop` file under `/usr/share/applications/` system-wide and (b) ship a binary symlink so `Exec=` resolves cleanly without `uv run`. Future Linux-packaging phase.
- **Stale-file cleanup** (remove orphan `org.example.MusicStreamer.desktop` from `~/.local/share/applications/`). Reviewed and declined for this phase — additive-only install. If it becomes a real annoyance, add a one-shot cleanup pass behind a separate marker.
- **Self-healing install** (refresh `.desktop` and icon on every launch if content drifts). Reviewed and declined — one-shot install is simpler and the user is trusted not to muck with the installed file.
- **X11 UAT coverage**. Kyle's deployment is Wayland; no X11 rig is in scope. If an X11 setup ever joins the test matrix, add an explicit UAT step there (would also need an `xprop`-based diagnostic readback path that the current Wayland-only diagnostic skips).
- **Per-DE matrix** (KDE Plasma `kquitapp5` dialog, XFCE `xfwm4` close dialog, etc.). Out of scope; GNOME-only.
- **Build-time AUMID/APP_ID drift guard** (analog of Phase 56 D-09 #3). With `constants.APP_ID` as the single source (D-02), drift is structurally impossible — no separate guard needed.

### Out-of-phase (already roadmapped)
- **BUG-09 — Audio buffer underrun resilience** — Phase 62.
- **VER-01 — Auto-bump pyproject version on phase completion** — Phase 63.

### Reviewed Todos (not folded)
None — todo list is unrelated to Linux WM display name (SDR support and station art beyond YouTube).

</deferred>

---

*Phase: 61-linux-app-display-name-in-wm-dialogs-force-quit-and-other-wm*
*Context gathered: 2026-05-05*
