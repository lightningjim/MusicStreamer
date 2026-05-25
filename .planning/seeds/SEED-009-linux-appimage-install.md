---
id: SEED-009
status: active
planted: 2026-05-05
planted_during: v2.1 Fixes and Tweaks (Phase 60)
activated: 2026-05-25
activated_during: v2.2 Package Building and QOL features/tweaks
trigger_when: any next milestone
scope: Large
---

# SEED-009: Build Linux distribution as an AppImage install

## Why This Matters

**Both parity AND friction-free distribution.** Windows already ships a packaged installer (Inno Setup via `packaging/windows/MusicStreamer.iss`), so Windows users get a one-click install. Linux users currently have to clone the repo, set up the conda environment, and run from source — there is no end-user install path.

AppImage closes that gap with a single self-contained file: any Linux user can download, mark executable, and double-click to run — no root, no package manager, no distro-specific build. That matches the Windows install experience and unlocks sharing builds with non-technical Linux users.

## When to Surface

**Trigger:** any next milestone

This seed should be presented during `/gsd-new-milestone` regardless of the milestone theme — the user explicitly asked for AppImage in the milestone immediately following v2.1. If the next milestone scope clearly excludes packaging (e.g., a pure-bugfix sprint), the user can dismiss it and the trigger remains active for the milestone after.

Re-surface conditions:
- New milestone planning session begins (any theme)
- Milestone scope mentions: packaging, install, distribution, Linux, cross-platform, end-user, parity

## Scope Estimate

**Large** — a full milestone.

Why large rather than a single phase:
- AppImage tooling on top of existing PyInstaller/conda-forge artifacts (the project's spike findings already document Windows GStreamer+PyInstaller+conda-forge patterns — Linux will need analogous work)
- GStreamer plugin bundling inside the AppImage (notoriously tricky — plugins, GIO modules, GLib schemas)
- `.desktop` file + icon integration (`packaging/linux/org.lightningjim.MusicStreamer.png` already exists)
- MPRIS2 / media-keys integration must keep working inside the AppImage sandbox (`musicstreamer/media_keys/mpris2.py`)
- yt-dlp + cookies storage path resolution inside the bundled filesystem
- Smoke tests across at least Ubuntu LTS + Fedora + one Arch-derived distro
- Possibly Flatpak/Snap as follow-on phases for distro-store distribution
- Signing / update channel decisions (zsync delta updates are AppImage-native)

Likely phase breakdown:
1. AppImage build pipeline (linuxdeploy / appimagetool integration with existing PyInstaller spec)
2. GStreamer plugin & runtime bundling
3. Desktop integration (.desktop, icon, MIME, MPRIS continuity)
4. Cross-distro smoke testing + CI artifact publishing
5. (Stretch) Auto-update via zsync, or Flatpak/Snap parity

## Breadcrumbs

Related code and prior art in the current codebase:

- `packaging/windows/` — full Windows install pipeline to mirror:
  - `MusicStreamer.spec` (PyInstaller spec — likely shareable structure for Linux)
  - `MusicStreamer.iss` (Inno Setup installer — Linux analogue is the AppImage recipe)
  - `runtime_hook.py` (PyInstaller runtime hook — same pattern needed for Linux)
  - `build.ps1` (Windows build script — Linux needs a `build.sh` counterpart)
  - `README.md` (Windows packaging doc — Linux needs sibling)
- `packaging/linux/` — currently only icon assets:
  - `org.lightningjim.MusicStreamer.png` (already in reverse-DNS form ready for `.desktop`)
  - `logodark.png`, `logo-bw.png`
- `musicstreamer/runtime_check.py` — runtime environment detection (Linux paths)
- `musicstreamer/media_keys/mpris2.py` — D-Bus MPRIS integration that must survive AppImage sandboxing
- `musicstreamer/__main__.py` — entry point referenced by PyInstaller spec
- `musicstreamer/ui_qt/main_window.py` — Qt main window (relevant for `.desktop` `StartupWMClass` matching, ties into deferred Phase 61 "Linux App Display Name in WM Dialogs")
- Spike findings skill: `Skill("spike-findings-musicstreamer")` — Windows packaging patterns documented; Linux AppImage spike will likely produce a parallel body of validated patterns

## Notes

- Phase 61 ("Linux App Display Name in WM Dialogs") is deferred in v2.1 ROADMAP.md; that work overlaps with `.desktop` file `StartupWMClass` and should be folded into the AppImage milestone rather than shipped separately.
- Per memory `project_deployment_target.md`: deployment target is Linux X11 DPR=1.0 — AppImage smoke testing should prioritize X11; Wayland-fractional is not a release blocker.
- Per memory `reference_qnap_github_mirror.md`: AppImage release artifacts published via QNAP push will mirror to GitHub — release-asset workflow needs to account for this.
- Cookie-storage paths inside AppImage need attention given recent v2.1 cookie-handling work (`yt-cookies.txt`, `gbs-cookies.txt`, `twitch-token.txt` are all `.gitignore`d but must persist on the user's machine outside the read-only AppImage filesystem — typically `$XDG_CONFIG_HOME/musicstreamer/`).
- Anthropic models used for codegen are out of scope, but `Skill("spike-findings-musicstreamer")` should be invoked when the milestone starts to surface relevant Windows-packaging lessons before designing the Linux pipeline.
