# Phase 61: Linux App Display Name in WM Dialogs - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-05
**Phase:** 61-linux-app-display-name-in-wm-dialogs-force-quit-and-other-wm
**Areas discussed:** App ID branding, Display-name lever choice, .desktop install strategy, Diagnose-first vs fix-first

---

## Initial Area Selection

User selected all four candidate gray areas.

| Option | Description | Selected |
|--------|-------------|----------|
| App ID branding | Keep `org.example.MusicStreamer` or migrate to `org.lightningjim.MusicStreamer` | ✓ |
| Display-name lever choice | `setApplicationDisplayName` vs. `.desktop` lookup vs. both | ✓ |
| .desktop install strategy | Self-install / manual install / docs only / defer | ✓ |
| Diagnose-first vs fix-first | Diagnose before patch vs. ship and verify | ✓ |

---

## App ID branding

### Q1: Which reverse-DNS app ID should the Linux build use going forward?

| Option | Description | Selected |
|--------|-------------|----------|
| `org.lightningjim.MusicStreamer` (Recommended) | Matches Windows AUMID (Phase 56), matches existing icon filename, removes the 'example' placeholder smell | ✓ |
| `org.example.MusicStreamer` (status quo) | No churn — keep the current Qt setDesktopFileName + .desktop basename | |
| You decide | Pick whichever has the cleanest blast radius | |

**User's choice:** `org.lightningjim.MusicStreamer`
**Notes:** Locked. Implies renaming `org.example.MusicStreamer.desktop` and updating Qt's `setDesktopFileName(...)` call.

### Q2: How aggressive should the rename be?

| Option | Description | Selected |
|--------|-------------|----------|
| Full rename, single source (Recommended) | Update `constants.APP_ID`, the Qt setDesktopFileName call, the MPRIS DesktopEntry property, and rename the .desktop file. All sites read from `constants.APP_ID` | ✓ |
| Minimal rename, just what the WM reads | Only change `setDesktopFileName` + .desktop filename + `constants.APP_ID`; leave MPRIS DesktopEntry as `org.example.*` | |
| You decide | Pick whichever keeps the change reviewable while killing the brand drift permanently | |

**User's choice:** Full rename, single source
**Notes:** Codebase already drifted (`single_instance.py:29` uses the new ID). MPRIS bus name pattern (`org.mpris.MediaPlayer2.musicstreamer`) is spec-mandated and stays.

### Q3: Should `constants.APP_ID` become the single source for the Windows AUMID too?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, unify both platforms (Recommended) | Drop the hardcoded default in `_set_windows_aumid` and read `constants.APP_ID`; closes Phase 56 D-09 #3 AUMID-drift risk | ✓ |
| No, keep them independent | Linux and Windows keep separate literals | |
| You decide | Pick based on whether the unified path passes Phase 56's diagnostic checks unchanged | |

**User's choice:** Yes, unify both platforms
**Notes:** Closes the Phase 56 D-09 #3 future drift risk for free.

---

## Display-name lever choice

### Q1: Beyond the .desktop file lookup (which is mandatory), should we also set `app.setApplicationDisplayName('MusicStreamer')`?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, add it (Recommended) | Belt-and-suspenders. One-line addition next to the existing `setApplicationName` call | ✓ |
| No, .desktop only | Keep the surface area minimal. .desktop lookup is the single mechanism the WM force-quit dialog uses | |
| You decide | Skip the lever question and let the planner add it (or not) | |

**User's choice:** Yes, add it
**Notes:** WM_CLASS mechanics (whether Qt needs `-name MusicStreamer` argv injection on X11) deferred to researcher; planner picks the implementation.

---

## .desktop install strategy

### Q1: How should `org.lightningjim.MusicStreamer.desktop` get into `~/.local/share/applications/` so the WM can find it?

| Option | Description | Selected |
|--------|-------------|----------|
| Self-install on first launch (Recommended) | App copies the bundled .desktop file (and icon) into XDG dirs on startup if the install marker is missing. Idempotent. Pattern: `migration.run_migration()` already exists | ✓ |
| Manual `make install` / shell script | Ship a `packaging/linux/install.sh`; user runs once. Simple but easy to forget | |
| Document only, no install | Tell user to copy the file themselves | |
| Defer to a future Linux packaging phase | Out of scope for this phase; Phase 61 only fixes the Qt/code half | |

**User's choice:** Self-install on first launch
**Notes:** Reuses `migration.run_migration()` shape. Slot in `__main__.py::_run_gui` between `Gst.init()` and existing migration call.

### Q2: What should the self-install routine handle alongside the .desktop file? (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| Install the icon too | Copy `packaging/linux/org.lightningjim.MusicStreamer.png` into `~/.local/share/icons/hicolor/<size>/apps/`. Without this, force-quit shows a generic icon | ✓ |
| Clean up stale `org.example.*` files | On install, remove any orphan `org.example.MusicStreamer.desktop` and matching icons | |
| Re-run on every launch (idempotent) | Don't use a one-shot install marker; refresh on startup if installed file content drifts | |

**User's choice:** Install the icon too (only)
**Notes:** Stale cleanup explicitly declined — additive-only install. One-shot install (not every launch) — user trusted not to muck with installed file.

---

## Diagnose-first vs fix-first

### Q1: Should research/execution run a diagnostic before patching?

| Option | Description | Selected |
|--------|-------------|----------|
| Diagnose-first, like Phase 56 (Recommended) | Researcher / first plan runs xprop/busctl/ls on Kyle's X11 rig. Captures failing state in DIAGNOSTIC-LOG.md. Then implementation proceeds with concrete root-cause attribution | ✓ |
| Fix-first, UAT proves it | Skip the diagnostic. Ship the rename + .desktop self-install and verify with force-quit | |
| You decide | Pick whichever produces a useful SUMMARY artifact without bloating the phase | |

**User's choice:** Diagnose-first, like Phase 56
**Notes:** Diagnostic is expected to be a formality (two failure modes are already known by inspection); captures concrete before/after for the SUMMARY artifact. Code change ships in the same phase — D-15 in CONTEXT.md.

### Q2: Should CONTEXT.md amend ROADMAP success criterion #3 to reflect the rename?

| Option | Description | Selected |
|--------|-------------|----------|
| Amend it (Recommended) | Replace #3 with: "The app ID is migrated from the placeholder `org.example.MusicStreamer` to `org.lightningjim.MusicStreamer` (matching the Phase 56 Windows AUMID); D-Bus interfaces and MPRIS bus name are unchanged." | ✓ |
| Keep #3 strict, don't rename | Reverse the App ID decision — keep `org.example.MusicStreamer` everywhere on Linux | |
| You decide | Pick whichever keeps the phase shippable | |

**User's choice:** Amend it
**Notes:** Spirit of #3 was "don't break integrations" — the rename does not break any integration; it fixes brand drift. ROADMAP Amendment captured in CONTEXT.md domain section.

---

## Claude's Discretion

Items the user explicitly deferred to Claude / the planner:

- Exact name and module location of the install routine (e.g., `desktop_install.py` next to `migration.py`, or a new function in `migration.py` itself, or `musicstreamer/linux_install.py`).
- Icon size bucket (256×256 vs 512×512 vs both) under `hicolor/<size>/apps/`.
- Install marker file location and naming (sentinel under `~/.local/share/musicstreamer/` vs. per-feature flag).
- Whether to run `update-desktop-database(1)` and `gtk-update-icon-cache(1)` after install (D-13 in CONTEXT.md).
- Whether to relocate the source `.desktop` file from repo root into `packaging/linux/` during the rename.
- Whether to inject `-name MusicStreamer` into argv before `QApplication(...)` to force X11 WM_CLASS — research determines necessity.

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section:

- Proper Linux installer / packaging (deb / rpm / Flatpak / AppImage) — future Linux-packaging phase.
- Stale-file cleanup (remove orphan `org.example.MusicStreamer.desktop` from `~/.local/share/applications/`) — reviewed and declined for this phase.
- Self-healing install (refresh `.desktop` on every launch) — reviewed and declined.
- Wayland-specific UAT step — memory locks deployment as X11; no Wayland rig today.
- Per-DE matrix (KDE Plasma, XFCE, Cinnamon) — out of scope; GNOME-only.
- Build-time AUMID/APP_ID drift guard — structurally impossible with `constants.APP_ID` single source.

Out-of-phase (already roadmapped):

- BUG-09 — Audio buffer underrun resilience — Phase 62.
- VER-01 — Auto-bump pyproject version on phase completion — Phase 63.
