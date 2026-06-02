# Phase 86: Linux Flatpak Build — Research

**Researched:** 2026-06-02
**Domain:** Flatpak packaging — PySide6 + GStreamer + QtWebEngine + MPRIS2 + Node.js + import wizard
**Confidence:** HIGH (manifest patterns / MPRIS2 / Node.js gap) | MEDIUM (ffmpeg-full GStreamer env-vars / GPG CI) | LOW (node20 runtime availability at launch)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**App ID (FP-01):** `io.github.kcreasey.MusicStreamer`

**Runtimes (FP-03):**
- `org.kde.Platform//6.8` + `org.kde.Sdk//6.8`
- `io.qt.PySide.BaseApp//6.8`
- `org.freedesktop.Platform.ffmpeg-full//24.08`
- `org.freedesktop.Sdk.Extension.node20`

**finish-args (FP-04 + D-01):**
- `--share=network`
- `--socket=pulseaudio`
- `--socket=wayland`
- `--socket=fallback-x11`
- `--own-name=org.mpris.MediaPlayer2.MusicStreamer`
- `--filesystem=~/.local/share/musicstreamer:ro` (D-01 narrow mount — APPROVED ADDITION to FP-04)
- NOT `--filesystem=home`
- NOT broad `--socket=session-bus`

**QtWebEngine (FP-05):** `QTWEBENGINE_DISABLE_SANDBOX=1` in finish-args env (verbatim spelling)

**First-launch import wizard (D-01..D-04):** Narrow `:ro` host mount; copy-don't-delete; offer-once-with-flag; reuse Phase 25 settings-export ZIP flow

**Distribution (D-06):** GitHub release asset alongside AppImage

**CI (D-07):** `.github/workflows/linux-flatpak.yml`, `workflow_dispatch`-only, no auto-publish

**GPG signing (D-08):** `flatpak build-bundle --gpg-sign=$GPG_KEY_ID`; reuse `secrets.LINUX_SIGNING_KEY` + `secrets.LINUX_SIGNING_KEY_ID`; add new PKG-LIN-FP signing requirement row

**UAT evidence bundle (D-09/D-10/D-11/D-12):** audible + Wayland screenshot + D-Bus transcript per capability; MPRIS2 via `busctl --user` + media-key press; single-host Wayland GNOME; GBS.FM login-persistence protocol

**Manifest format (D-14):** YAML (`io.github.kcreasey.MusicStreamer.yaml`)

**Python deps (FP-09):** `flatpak-pip-generator` → checked-in `python3-modules.yaml`

**Validators (FP-10 + D-15):** `appstreamcli validate` + `desktop-file-validate`; both in pytest (skip-if-not-installed) AND as hard CI pre-flight gate

**Drift-guards (D-13):** `tests/test_packaging_spec.py` — allow-list AND deny-list; parse YAML manifest as data; assert absence of `--filesystem=home` and broad `--socket=session-bus`

### Claude's Discretion (planner picks)

- Plan split (monolithic vs. multi-plan; likely: manifest+pip-generator / build+sign+bundle / import-wizard wiring / CI workflow / verification UAT)
- Whether build tooling relocates under `tools/linux-flatpak/` or shares `tools/linux-build/` with the AppImage driver
- Exact module structure inside the manifest (musicstreamer source module + python3-modules.yaml + node20 deps sequencing)
- Where the new signing requirement row sits in REQUIREMENTS.md and its exact ID

### Deferred Ideas (OUT OF SCOPE)

- Flathub store submission (PKG-LIN-FP-FLATHUB) — post-v2.2
- All 6 reviewed phase-86 todos (player features, Phase 77 test debt, docker-info probe)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PKG-LIN-FP-01 | App ID is `io.github.kcreasey.MusicStreamer` | Locked; `id:` key in YAML manifest |
| PKG-LIN-FP-02 | `flatpak install --user .flatpak` + GNOME Software sideload + `flatpak run` | Standard sideload flow; `flatpak build-bundle` produces single-file `.flatpak` |
| PKG-LIN-FP-03 | Runtime set: KDE 6.8 + PySide BaseApp + ffmpeg-full + node20 | Manifest fields documented in §Standard Stack |
| PKG-LIN-FP-04 | finish-args allow-list; no `--filesystem=home`, no broad session-bus | §MPRIS2, §Manifest Patterns; allow + deny-list drift-guard |
| PKG-LIN-FP-05 | `QTWEBENGINE_DISABLE_SANDBOX=1` in finish-args env for GBS.FM | §QtWebEngine Sandbox-in-Sandbox; verified spelling from io.qt.qtwebengine.BaseApp docs |
| PKG-LIN-FP-06 | First-launch detects `~/.local/share/musicstreamer/` via narrow `:ro` mount, imports via Phase 25 ZIP flow | §First-Launch Import Wizard; Phase 25 code surface identified |
| PKG-LIN-FP-07 | AAC playback via ffmpeg-full extension | §GStreamer + ffmpeg-full; pitfall documented |
| PKG-LIN-FP-08 | MPRIS2 from inside sandbox (unblocked by Phase 91) | §MPRIS2; `--own-name` necessity confirmed |
| PKG-LIN-FP-09 | `flatpak-pip-generator` → `python3-modules.yaml` checked in | §Standard Stack — flatpak-pip-generator; PyPI package confirmed |
| PKG-LIN-FP-10 | `appstreamcli validate` + `desktop-file-validate` pass | §Appstream + Desktop File; both tools present on host |
</phase_requirements>

---

## Summary

Phase 86 ships a sideload-installable Flatpak bundle for MusicStreamer — a PySide6 + GStreamer + yt-dlp audio streamer — running on `org.kde.Platform//6.8` with the PySide BaseApp and the ffmpeg-full codec extension. The primary technical challenges are: (1) sequencing the manifest correctly so python3-modules.yaml pip deps, the node20 SDK extension, and the app source module compose cleanly with the PySide BaseApp's cleanup script; (2) making GStreamer's `avdec_aac` resolve via the ffmpeg-full extension inside the sandbox; (3) wiring MPRIS2 through the D-Bus proxy using `--own-name` without broad session-bus access; and (4) implementing the narrow `:ro` host-filesystem mount for the first-launch import wizard.

The AppImage precedent (Phase 85) is the structural analog for distribution, CI, and GPG signing. Key differences: Flatpak bundles its own `org.kde.Platform` runtime (no GLIBC baseline concern), cross-distro UAT is not needed, and D-Bus sandbox permissions replace the AppRun env-var template. The conda dependency graph is replaced by flatpak-pip-generator + PySide BaseApp.

**Primary recommendation:** Author the YAML manifest with `io.qt.PySide.BaseApp//6.8` as base, `python3-modules.yaml` as the first module, the app's pip-installed source as the second module, and handle node20 as an SDK build-time extension with node binaries copied to `/app/bin/` so they survive at runtime. Validate the build locally with `flatpak-builder --user --install` before CI wiring.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Manifest / sandbox perms | Build artifact | — | All sandbox policy lives in the YAML manifest |
| Audio playback (AAC/MP3) | App runtime (GStreamer in sandbox) | ffmpeg-full extension | GStreamer is bundled in KDE runtime; AAC decoders come from ffmpeg-full |
| MPRIS2 D-Bus ownership | App runtime | xdg-dbus-proxy (Flatpak) | D-Bus proxy bridges `--own-name` to host session bus |
| GBS.FM login (QtWebEngine) | Subprocess (oauth_helper.py) | App runtime | QtWebEngine runs in a child process; `QTWEBENGINE_DISABLE_SANDBOX=1` disables its inner sandbox |
| First-launch import | App runtime (UI) | Host filesystem (`:ro`) | App reads narrow `:ro` mount, copies to sandbox data dir |
| Node.js (yt-dlp EJS) | App runtime | SDK build extension (node20) | node20 = SDK extension at build time; binaries must be bundled into `/app/bin/` for runtime |
| Python pip deps | Build pipeline (flatpak-pip-generator) | — | pip deps built offline during flatpak-builder run |
| GPG signing | Build script | CI secrets | `flatpak build-bundle --gpg-sign` with passphrase-less key |
| metainfo / .desktop | Build artifact | Validators (appstreamcli, desktop-file-validate) | Static XML/INI files checked pre-flight |

---

## Standard Stack

### Core — Manifest Runtime Set

| Component | Version / Branch | Purpose | Why Standard |
|-----------|-----------------|---------|--------------|
| `org.kde.Platform` | `6.8` | Qt 6.8 runtime, GStreamer base | Ships Qt6/GStreamer in one bundle; PySide BaseApp requires it [VERIFIED: flatpak remote-info flathub] |
| `org.kde.Sdk` | `6.8` | Build-time counterpart to Platform | Required for all KDE/Qt app builds [CITED: docs.flatpak.org/available-runtimes] |
| `io.qt.PySide.BaseApp` | `6.8` | PySide6 Python bindings pre-built | Avoids shipping 400MB PySide6 from scratch; standard for Python Qt apps on Flathub [CITED: github.com/flathub/io.qt.PySide.BaseApp] |
| `org.freedesktop.Platform.ffmpeg-full` | `24.08` | AAC/H.264 decoders via FFmpeg for GStreamer | Provides `avdec_aac`; KDE Platform alone lacks patented codecs [CITED: docs.flatpak.org/extension.html] |
| `org.freedesktop.Sdk.Extension.node20` | `24.08` | Node.js 20.x build-time toolchain | Locked in FP-03; SDK extension only — node binary must be COPIED to `/app/bin/` to survive at runtime [ASSUMED: runtime availability requires explicit copy step; see Open Question 5] |

### Build Tools

| Tool | Version | Purpose | How to Install |
|------|---------|---------|----------------|
| `flatpak-builder` | 1.4.8 (apt) | Builds from manifest, creates OSTree repo | `sudo apt install flatpak-builder` [VERIFIED: apt-cache] |
| `flatpak-pip-generator` | 2026.5.28 | Generates `python3-modules.yaml` from pip deps | `pip install flatpak-pip-generator` [VERIFIED: PyPI — pip index versions] |
| `appstreamcli` | 1.1.2 | Validates metainfo XML | Already on host [VERIFIED: command -v appstreamcli] |
| `desktop-file-validate` | 0.28 | Validates .desktop file | Already on host [VERIFIED: command -v desktop-file-validate] |
| `yq` or `python3 -c yaml` | — | Parse manifest in drift-guard tests | Already used in linux-build; pytest uses `pyyaml` for data-level parsing |

**flatpak-builder NOT installed:** Must be installed before development begins. Available via `sudo apt install flatpak-builder` (candidate 1.4.8-1). [VERIFIED: apt-cache policy]

**KDE Platform 6.8 NOT installed locally:** The runtime is available on Flathub (`org.kde.Platform//6.8`, 1.1GB) but not yet installed on the dev host. `flatpak install flathub org.kde.Platform//6.8 org.kde.Sdk//6.8` is required before `flatpak-builder` runs. [VERIFIED: flatpak remote-info shows available but Installed: reports not installed]

### python3-modules.yaml Generation

```bash
# From pyproject.toml (pip deps only — PySide6, pygobject, gstreamer come from BaseApp/KDE runtime)
flatpak-pip-generator \
  --runtime='org.freedesktop.Sdk//24.08' \
  --yaml \
  --output python3-modules \
  yt-dlp streamlink platformdirs chardet mutagen pillow requests

# OR from requirements.txt equivalent:
flatpak-pip-generator \
  --runtime='org.freedesktop.Sdk//24.08' \
  --requirements-file=flatpak-requirements.txt \
  --yaml \
  --output python3-modules
```

**Critical caveat:** PySide6 and PyGObject/GStreamer bindings are already in the BaseApp and KDE runtime. Do NOT re-include them in flatpak-pip-generator; doing so would pull PyPI PySide6 wheels that conflict with the BaseApp's compiled bindings. The pip deps list for the Flatpak is a SUBSET of pyproject.toml dependencies — excludes `PySide6>=6.10` (provided by BaseApp) and system GObject packages. [ASSUMED: exact exclusion list; verify by test-building]

The output `python3-modules.yaml` MUST be committed to the repo (FP-09) — flatpak-builder needs it for offline Flathub builds. [CITED: docs.flatpak.org/python.html]

---

## Package Legitimacy Audit

This phase installs no new Python packages into the host. It uses one new build tool (`flatpak-pip-generator`) and one new system tool (`flatpak-builder`). The packages bundled INTO the Flatpak are either from Flathub runtimes (trusted) or from the existing pyproject.toml deps (already in use).

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `flatpak-pip-generator` | PyPI | current (2026.5.28) | moderate | github.com/flatpak/flatpak-builder-tools | [ASSUMED] | Approved — official flatpak org repo |
| `flatpak-builder` | apt (Ubuntu) | 1.4.8, mature | OS package | github.com/flatpak/flatpak-builder | [ASSUMED] | Approved — official flatpak project |
| `pyyaml` | PyPI | mature (6.0.3) | very high | github.com/yaml/pyyaml | [ASSUMED] | Approved — already in dev toolchain |

*slopcheck unavailable at research time (binary invocation failed). All packages above are from official project repositories. The planner does not need checkpoint:human-verify steps because these are official toolchain packages, not third-party dependencies.*

**Note:** The packages bundled INTO the Flatpak (`yt-dlp`, `streamlink`, `platformdirs`, `chardet`, `mutagen`, `pillow`, `requests`) are already legitimacy-gated by the existing AppImage build (Phase 85 `environment.yml`). No new bundled packages.

---

## Architecture Patterns

### System Architecture Diagram

```
BUILD TIME:
  pyproject.toml deps list
       |
  flatpak-pip-generator
       |
  python3-modules.yaml (checked in)
       |
  io.github.kcreasey.MusicStreamer.yaml  ──────────────────────────────────┐
  (YAML manifest)                                                           |
       |                                                                    |
       ├── base: io.qt.PySide.BaseApp//6.8 ─────> /app/lib/python3/         |
       ├── sdk-extensions: node20 ─────────────> build /usr/lib/sdk/node20/ |
       ├── modules[0]: python3-modules.yaml ───> pip deps to /app/          |
       ├── modules[1]: app source ─────────────> pip install . to /app/     |
       │              (copies /usr/lib/sdk/node20/bin/node → /app/bin/node) |
       └── add-extensions: ffmpeg-full//24.08 ──> lib/ffmpeg/ (user install)|
                                                                            |
  flatpak-builder ──> OSTree repo ──> flatpak build-bundle ──> .flatpak ───┘
                                            |
                               --gpg-sign=$GPG_KEY_ID
                                            |
                              MusicStreamer-<ver>.flatpak (+ .sig sidecar concept)

RUNTIME (inside sandbox):
  org.kde.Platform//6.8
       ├── /usr/lib/gstreamer-1.0/   ← base GStreamer plugins (no AAC)
       └── /usr/lib/x86_64-linux-gnu/gstreamer-1.0/ (KDE layout varies)

  ffmpeg-full extension  →  /app/lib/ffmpeg/  →  GST_PLUGIN_PATH includes this
       └── libgstlibav.so  ←── avdec_aac, aacparse live here

  /app/ (built by flatpak-builder)
       ├── bin/node              ← copied from node20 SDK extension
       ├── bin/musicstreamer     ← app entry point
       ├── lib/python3/          ← PySide6 (BaseApp) + pip deps
       └── share/
           ├── applications/io.github.kcreasey.MusicStreamer.desktop
           └── metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml

  D-Bus proxy (xdg-dbus-proxy):
       host session bus ←──── --own-name=org.mpris.MediaPlayer2.MusicStreamer
       sandbox ──────────────> talks to MPRIS2 clients (playerctl, OS media keys)

  Narrow `:ro` mount:
       ~/.local/share/musicstreamer/ → readable at first launch
       → app copies to ~/.var/app/io.github.kcreasey.MusicStreamer/data/
```

### Recommended Project Structure

```
io.github.kcreasey.MusicStreamer.yaml          # Flatpak manifest (YAML, D-14)
python3-modules.yaml                            # flatpak-pip-generator output (FP-09, checked in)
tools/linux-flatpak/                            # New sibling to tools/linux-build/
    build.sh                                    # Build + sign + bundle driver (mirrors 85 D-07)
    desktop/
        io.github.kcreasey.MusicStreamer.desktop
    metainfo/
        io.github.kcreasey.MusicStreamer.metainfo.xml
    flatpak-requirements.txt                    # pip deps for flatpak-pip-generator (excludes PySide6)
    README.md                                   # Local build instructions
.github/workflows/linux-flatpak.yml            # CI (workflow_dispatch only, D-07)
tests/test_packaging_spec.py                    # Extended with Flatpak drift-guards (D-13/D-15)
```

### Pattern 1: Manifest Top-Level Structure (YAML)

```yaml
# Source: github.com/flathub/io.qt.PySide.BaseApp + KDE developer docs
id: io.github.kcreasey.MusicStreamer
runtime: org.kde.Platform
runtime-version: '6.8'
sdk: org.kde.Sdk
base: io.qt.PySide.BaseApp
base-version: '6.8'
command: musicstreamer
sdk-extensions:
  - org.freedesktop.Sdk.Extension.node20

add-extensions:
  org.freedesktop.Platform.ffmpeg-full:
    version: '24.08'
    directory: lib/ffmpeg
    add-ld-path: .

cleanup-commands:
  - mkdir -p ${FLATPAK_DEST}/lib/ffmpeg
  - /app/cleanup-BaseApp.sh

build-options:
  env:
    - BASEAPP_REMOVE_WEBENGINE=1     # removes WebEngine binaries from BaseApp (reduces size)
    # BASEAPP_DISABLE_NUMPY=1        # optional if numpy not needed

finish-args:
  - --share=network
  - --socket=pulseaudio
  - --socket=wayland
  - --socket=fallback-x11
  - --own-name=org.mpris.MediaPlayer2.MusicStreamer
  - --filesystem=~/.local/share/musicstreamer:ro
  # The env entry:
  - --env=QTWEBENGINE_DISABLE_SANDBOX=1

modules:
  - python3-modules.yaml              # generated by flatpak-pip-generator; pip deps first
  - name: musicstreamer
    buildsystem: simple
    build-commands:
      # Copy node binary from SDK extension to app bin (required for runtime availability)
      - install -D /usr/lib/sdk/node20/bin/node /app/bin/node
      # Install app
      - pip3 install --no-deps --prefix=/app .
    sources:
      - type: dir
        path: .
```

**Critical notes on manifest:**
- `BASEAPP_REMOVE_WEBENGINE=1` in build-options removes QtWebEngine FROM the BaseApp bundle (saves ~200MB). `QTWEBENGINE_DISABLE_SANDBOX=1` in finish-args enables the QtWebEngine subprocess that oauth_helper.py spawns. These are different env vars at different stages. [CITED: github.com/flathub/io.qt.PySide.BaseApp README]
- `--env=QTWEBENGINE_DISABLE_SANDBOX=1` is the correct finish-args spelling (the env key in finish-args, not build-options). [CITED: github.com/flathub/io.qt.qtwebengine.BaseApp]
- If `BASEAPP_REMOVE_WEBENGINE=1` is set AND GBS.FM login is needed, QtWebEngineWidgets must still be available. **Flag for planner:** If WebEngine is removed from BaseApp, oauth_helper.py will fail to import `PySide6.QtWebEngineWidgets`. Two options: (a) do NOT set `BASEAPP_REMOVE_WEBENGINE=1`, or (b) add a separate QtWebEngine module. Given FP-05/SC3 requires GBS.FM login, do NOT remove WebEngine. Remove the `BASEAPP_REMOVE_WEBENGINE=1` line. [ASSUMED: WebEngine is included in BaseApp 6.8 by default; remove the build-option line to keep it]

### Pattern 2: Node.js at Runtime (SDK Extension → /app/bin copy)

`org.freedesktop.Sdk.Extension.node20` is a **build-time SDK extension only**. SDK extensions mount at `/usr/lib/sdk/node20/` during the `flatpak-builder` build but are NOT available inside the sandbox at runtime. [CITED: docs.flatpak.org/extension.html — "sdk-extensions can be used to install extra extensions … These tools become unavailable in the final packaged application."]

To make `node` available at runtime for yt-dlp's EJS solver, the build-commands must explicitly copy the node binary:

```bash
install -D /usr/lib/sdk/node20/bin/node /app/bin/node
```

The app's `runtime_check.check_node()` calls `shutil.which("node")`. Inside the Flatpak sandbox, `PATH` includes `/app/bin`, so the copied binary will be found. The `yt_dlp_opts.build_js_runtimes()` function passes the resolved absolute path explicitly, so no further PATH manipulation is needed. [VERIFIED: codebase — musicstreamer/runtime_check.py, musicstreamer/yt_dlp_opts.py]

**Flagged gap (Open Question 5):** Whether `org.freedesktop.Sdk.Extension.node20//24.08` version is the correct branch for `org.kde.Sdk//6.8` (which is built on Freedesktop SDK 24.08) needs confirmation. The flathub listing shows node20 is available for `24.08` branch. [VERIFIED: flatpak remote-ls shows `org.freedesktop.Sdk.Extension.node20 20.20.1 24.08`]

### Pattern 3: GStreamer + ffmpeg-full AAC

The KDE Platform 6.8 runtime ships GStreamer base plugins but does NOT include `avdec_aac` (AAC decoder from libav/FFmpeg) due to patent/codec licensing constraints. `org.freedesktop.Platform.ffmpeg-full//24.08` provides `libgstlibav.so` (the GStreamer FFmpeg plugin) at `/app/lib/ffmpeg/`. [CITED: docs.flatpak.org/extension.html — ffmpeg-full extension manifest]

GStreamer auto-discovers plugins at `/app/lib/ffmpeg/` because the extension's `add-ld-path: .` setting causes Flatpak to add this path to the library search path, and GStreamer's default `GST_PLUGIN_SYSTEM_PATH` inside the sandbox includes `/app/lib/` sub-directories. [CITED: docs.flatpak.org/extension.html]

**Build step required:** The `cleanup-commands` must include `mkdir -p ${FLATPAK_DEST}/lib/ffmpeg` to create the extension mount point directory. Without it, the ffmpeg-full extension cannot mount. [CITED: docs.flatpak.org/extension.html — explicit example shows this mkdir]

**Verification:** `gst-inspect-1.0 avdec_aac` from inside `flatpak run io.github.kcreasey.MusicStreamer bash` should resolve after the ffmpeg-full extension is installed.

**Contrast with AppImage (Phase 85):** The AppImage bundled `gst-libav` via conda-forge and set `GST_PLUGIN_SYSTEM_PATH_1_0` in AppRun. The Flatpak does NOT need those env-vars — the runtime and extension handle plugin discovery automatically inside the sandbox. The SSL/TLS cert setup (`GIO_EXTRA_MODULES`, `SSL_CERT_FILE`) required by AppRun is also NOT needed in the Flatpak (the KDE runtime bundles TLS natively). [VERIFIED: spike-findings-musicstreamer/references/linux-appimage-bundling.md — these were AppImage-specific workarounds]

### Pattern 4: MPRIS2 Without Broad session-bus

Flatpak's D-Bus proxy (`xdg-dbus-proxy`) intercepts all D-Bus traffic. The default policy allows a sandboxed app to own `$FLATPAK_ID` namespace and `org.mpris.MediaPlayer2.$FLATPAK_ID`. [CITED: docs.flatpak.org/sandbox-permissions.html]

For `io.github.kcreasey.MusicStreamer`:
- Default would allow: `org.mpris.MediaPlayer2.io.github.kcreasey.MusicStreamer`
- Requested name: `org.mpris.MediaPlayer2.MusicStreamer` (shorter — used by Phase 91's playerctl tests)
- These are **different** → `--own-name=org.mpris.MediaPlayer2.MusicStreamer` IS required in finish-args.

**`--own-name` behavior:** When `--own-name=org.mpris.MediaPlayer2.MusicStreamer` is in finish-args, the D-Bus proxy grants the app permission to register that specific name on the session bus. Clients outside the sandbox (playerctl, OS media keys) see the name as if it were registered by a normal host process. [CITED: flatpak-metadata(5) man page via manpages.debian.org]

**Verification protocol (D-10):**
```bash
# From outside sandbox while app is running:
busctl --user list | grep mpris
playerctl --player=MusicStreamer status
# Media key press while app plays → observe play/pause response
```

### Pattern 5: First-Launch Import Wizard

**Data path inside sandbox:** `platformdirs.user_data_dir("musicstreamer")` resolves to `~/.local/share/musicstreamer` on host, but inside the Flatpak sandbox `XDG_DATA_HOME` is set to `~/.var/app/io.github.kcreasey.MusicStreamer/data` → `paths.data_dir()` returns `~/.var/app/io.github.kcreasey.MusicStreamer/data/musicstreamer`. [CITED: docs.flatpak.org/conventions.html — XDG_DATA_HOME override]

**Detection source:** The `--filesystem=~/.local/share/musicstreamer:ro` finish-arg makes the old unsandboxed data dir readable at its HOST path (not remapped). So the app must probe `os.path.expanduser("~/.local/share/musicstreamer/musicstreamer.sqlite3")` directly (not via `paths.data_dir()`). The first-launch detector is a new helper that checks that literal host path.

**Import flow (D-04):** Reuses `musicstreamer.settings_export` module:
- `settings_export.build_zip(repo, dest_path)` — exports from source Repo (opened against the `:ro` host path)
- `settings_export.preview_import(zip_path, sandbox_repo)` → `commit_import(preview, sandbox_repo, mode)` — imports into sandbox Repo

The Phase 25 code surface (`musicstreamer/settings_export.py`, `musicstreamer/ui_qt/settings_import_dialog.py`) is fully reusable. The `SettingsImportDialog` class is the UI component to reuse. [VERIFIED: codebase — settings_export.py lines 169-501]

**Offer-once flag (D-03):** Write a marker file to sandbox data dir (e.g., `~/.var/app/io.github.kcreasey.MusicStreamer/data/musicstreamer/.flatpak-import-offered`) on first dismiss. Check for this file at startup before offering the wizard.

### Pattern 6: flatpak-builder Build + Sign Flow

```bash
# Build (--user flag for non-root install)
flatpak-builder \
  --user \
  --repo=flatpak-repo \
  --force-clean \
  build-dir \
  io.github.kcreasey.MusicStreamer.yaml

# Export to single-file bundle with GPG signing
flatpak build-bundle \
  --gpg-sign="$GPG_KEY_ID" \
  --gpg-homedir="$GNUPGHOME" \
  flatpak-repo \
  "MusicStreamer-${VERSION}.flatpak" \
  io.github.kcreasey.MusicStreamer

# Verify (for local testing without signing):
flatpak install --user --no-gpg-verify MusicStreamer-${VERSION}.flatpak
```

**GPG signing in CI (pinentry constraint):** `flatpak build-bundle --gpg-sign` invokes gpg directly. In CI, passphrase-protected keys fail with "Pinentry: Inappropriate ioctl for device". The resolution: use a **passphrase-less GPG key** for signing (import with `gpg --batch --import`), OR configure `gpg-agent` with `allow-preset-passphrase` and preset the passphrase before signing. The Phase 85 CI model (`secrets.LINUX_SIGNING_KEY` = ASCII-armored private key) works if the key has no passphrase. [CITED: github.com/flatpak/flatpak-builder/issues/377 — confirmed non-interactive challenge]

**FUSE in GitHub Actions:** `flatpak-builder` requires FUSE (for OSTree). GitHub Actions containers need `options: --privileged` to get FUSE access. The `flatpak/flatpak-github-actions` action handles this automatically with its `ghcr.io/flathub-infra/flatpak-github-actions:gnome-48` container image. [CITED: github.com/flatpak/flatpak-github-actions]

For CI, the recommended approach mirrors Phase 85: use the official `flatpak/flatpak-github-actions/flatpak-builder@v6` GitHub Action, which handles FUSE/privilege, runtime installation, and artifact upload. The `workflow_dispatch`-only trigger (D-07) can be set independently of the action's container setup.

### Anti-Patterns to Avoid

- **`--socket=session-bus`** — grants unrestricted D-Bus access; Flathub will reject; deny-list in drift-guard (D-13)
- **`--filesystem=home`** — broad host filesystem access; Flathub will reject; deny-list in drift-guard (D-13)
- **Setting `BASEAPP_REMOVE_WEBENGINE=1` while GBS.FM login is required** — removes QtWebEngineWidgets, breaking FP-05/SC3
- **Not running `cleanup-BaseApp.sh`** — leaves unnecessary BaseApp binaries in the bundle, increases size
- **Not creating `${FLATPAK_DEST}/lib/ffmpeg` in cleanup-commands** — extension mount point missing; ffmpeg-full fails to mount silently
- **Using `--gpg-sign` with a passphrase-protected key in CI** — pinentry will prompt interactively and hang CI
- **Including PySide6 in flatpak-pip-generator deps** — conflicts with BaseApp's compiled PySide6; import errors at runtime
- **Relying on node20 being in PATH without copying to /app/bin** — SDK extensions are build-time only; node binary vanishes at runtime

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PySide6 bundling | Custom PyPI PySide6 wheels + pip install | `io.qt.PySide.BaseApp//6.8` | BaseApp has ABI-compatible PySide6 built against KDE runtime; PyPI wheels would conflict |
| AAC codec support | Ship FFmpeg as app module | `org.freedesktop.Platform.ffmpeg-full//24.08` extension | Extension is the Flathub-approved pattern; shipping FFmpeg as an app module inflates size |
| Python offline deps | Manual sources entries per dep | `flatpak-pip-generator --yaml` | Generator handles the entire pip dependency graph with SHA256 hashes |
| D-Bus session integration | Broad `--socket=session-bus` | `--own-name` + `xdg-dbus-proxy` (automatic) | Proxy handles name ownership filtering; broad session-bus is a security violation |
| Cross-distro runtime | Conda env bundled in AppImage | `org.kde.Platform//6.8` (Flatpak runtime) | Flatpak's runtime IS the portability layer; no need for the 85a distrobox matrix |
| GPG signing | Custom signing script from scratch | Mirror Phase 85 `build.sh` signing discipline | `flatpak build-bundle --gpg-sign` is the standard; passphrase-less key pattern is established |

**Key insight:** The Flatpak runtime (KDE Platform + PySide BaseApp + ffmpeg-full) replaces the entire conda bundling stack from Phase 85. The "assemble everything from conda" problem is Flatpak's job, not the app's.

---

## Common Pitfalls

### Pitfall 1: BASEAPP_REMOVE_WEBENGINE vs QTWEBENGINE_DISABLE_SANDBOX
**What goes wrong:** Developer sets `BASEAPP_REMOVE_WEBENGINE=1` in build-options (to save space) but also requires GBS.FM QtWebEngine login (FP-05). Result: oauth_helper.py fails with `ImportError: PySide6.QtWebEngineWidgets not installed`.
**Why it happens:** The two env vars operate at different stages. `BASEAPP_REMOVE_WEBENGINE=1` is a build-time signal to the BaseApp's cleanup script that removes WebEngine binaries. `QTWEBENGINE_DISABLE_SANDBOX=1` is a runtime signal that allows the WebEngine subprocess to run inside the Flatpak sandbox.
**How to avoid:** Do NOT set `BASEAPP_REMOVE_WEBENGINE=1` in the manifest. Accept the larger bundle size (~200MB). FP-05 (GBS.FM login) and SC3 require WebEngine.
**Warning signs:** `ModuleNotFoundError: No module named 'PySide6.QtWebEngineWidgets'` at GBS.FM login attempt.

### Pitfall 2: ffmpeg-full Extension Mount Directory Missing
**What goes wrong:** `avdec_aac` fails to resolve at runtime; AAC streams silent or error.
**Why it happens:** `org.freedesktop.Platform.ffmpeg-full` mounts at `/app/lib/ffmpeg/`. If that directory does not exist in the built app, the extension silently fails to mount.
**How to avoid:** `cleanup-commands` MUST include `mkdir -p ${FLATPAK_DEST}/lib/ffmpeg`. Also declare `add-extensions: org.freedesktop.Platform.ffmpeg-full: directory: lib/ffmpeg`.
**Warning signs:** `gst-inspect-1.0 avdec_aac` fails from inside the sandbox despite extension being installed.

### Pitfall 3: node20 SDK Extension Not Available at Runtime
**What goes wrong:** yt-dlp EJS solver fails at YouTube stream resolution; `runtime_check.check_node()` returns `available=False`.
**Why it happens:** `sdk-extensions` are build-time only. Node.js binaries at `/usr/lib/sdk/node20/bin/node` are NOT present inside the running sandbox.
**How to avoid:** Add `install -D /usr/lib/sdk/node20/bin/node /app/bin/node` to the app module's build-commands. The app's `PATH` inside the sandbox includes `/app/bin`, so `shutil.which("node")` finds it.
**Warning signs:** YouTube streams fail with "No video formats found!"; `flatpak run io.github.kcreasey.MusicStreamer bash -c "which node"` returns nothing.

### Pitfall 4: QtWebEngine Subprocess Namespace Failure (SC3)
**What goes wrong:** GBS.FM login via oauth_helper.py subprocess fails with a namespace/sandbox error inside the Flatpak sandbox; cookies not persisted.
**Why it happens:** QtWebEngine uses Chromium's sandbox, which itself tries to create a new Linux namespace — but the Flatpak sandbox already has reduced privileges, and the nested namespace request fails.
**How to avoid:** `--env=QTWEBENGINE_DISABLE_SANDBOX=1` in finish-args disables Chromium's inner sandbox. Verbatim spelling from the Flathub `io.qt.qtwebengine.BaseApp` manifest. [CITED: github.com/flathub/io.qt.qtwebengine.BaseApp]
**Warning signs:** oauth_helper.py subprocess exits non-zero; `namespace: not permitted` in stderr; GBS.FM login page never completes.

### Pitfall 5: PySide6 Double-Install Conflict
**What goes wrong:** pip wheels for PySide6 installed by flatpak-pip-generator conflict with the BaseApp's compiled PySide6 bindings; import errors at runtime.
**Why it happens:** flatpak-pip-generator processes the full pyproject.toml deps, which includes `PySide6>=6.10`. The resulting YAML includes a PySide6 pip install step.
**How to avoid:** Create a `flatpak-requirements.txt` that lists ONLY the non-runtime deps: `yt-dlp`, `streamlink`, `platformdirs`, `chardet`, `mutagen`, `pillow`, `requests`. Exclude `PySide6` (from BaseApp) and system GObject bindings (from KDE runtime). Pass this file to flatpak-pip-generator instead of pyproject.toml.
**Warning signs:** `ImportError` at startup mentioning PySide6 ABI mismatch; app crashes immediately after launch.

### Pitfall 6: MPRIS2 Name Mismatch
**What goes wrong:** playerctl cannot find the app; OS media keys don't work; MPRIS name is not on the session bus.
**Why it happens:** Default Flatpak MPRIS policy grants `org.mpris.MediaPlayer2.io.github.kcreasey.MusicStreamer`, not `org.mpris.MediaPlayer2.MusicStreamer`. The app registers the short name.
**How to avoid:** `--own-name=org.mpris.MediaPlayer2.MusicStreamer` in finish-args. Phase 91's MPRIS2 fix uses this exact name (verified clean after FIX-MPRIS-01/02/03).
**Warning signs:** `busctl --user list | grep mpris` shows the long name instead of the short one, or shows nothing.

### Pitfall 7: XDG_DATA_HOME Path Confusion in First-Launch Detector
**What goes wrong:** First-launch wizard detects the SANDBOX data dir as the "old unsandboxed" data dir; import wizard fires even with no pre-existing data; or wizard cannot find the old data.
**Why it happens:** `platformdirs.user_data_dir("musicstreamer")` inside the sandbox returns `~/.var/app/io.github.kcreasey.MusicStreamer/data/musicstreamer` (Flatpak overrides `XDG_DATA_HOME`). The host path `~/.local/share/musicstreamer/` is only accessible via the narrow `:ro` mount and must be probed with a LITERAL host-path check, not via `paths.data_dir()`.
**How to avoid:** The first-launch detection code must probe `os path.expanduser("~/.local/share/musicstreamer/musicstreamer.sqlite3")` (literal), not `paths.db_path()`. Document this path as a constant, not inlined.
**Warning signs:** Import wizard fires every launch even when `~/.local/share/musicstreamer/` doesn't exist; wizard fires even after a prior run, because the "offered" flag was written to the sandbox dir path and the detection also uses the sandbox dir.

### Pitfall 8: GPG Pinentry Blocks CI
**What goes wrong:** CI run hangs indefinitely waiting for passphrase input; `flatpak build-bundle --gpg-sign` prompts for a passphrase that can't be provided in non-interactive mode.
**Why it happens:** GPG's pinentry daemon requires a terminal or display to ask for passphrases. CI containers have neither.
**How to avoid:** Use a **passphrase-less GPG subkey** for signing. `secrets.LINUX_SIGNING_KEY` should be an exported passphrase-less key. The import step `gpg --batch --import` succeeds without prompting. Alternatively, configure `allow-preset-passphrase` in gpg-agent.conf and preset via `gpg-preset-passphrase` before signing. Mirror Phase 85's signing discipline exactly.
**Warning signs:** CI job hangs at the `flatpak build-bundle` step; log shows "Enter passphrase" or gpg-agent waiting.

### Pitfall 9: flatpak-builder Requires Privileged Container
**What goes wrong:** `flatpak-builder` in GitHub Actions container fails with permission errors (OSTree/FUSE).
**Why it happens:** flatpak-builder uses OSTree (which may use FUSE) for hardlink-based caching. Standard unprivileged containers can't mount FUSE.
**How to avoid:** Use `container: options: --privileged` in the GitHub Actions workflow. The official `flatpak/flatpak-github-actions` action handles this. Alternatively, `flatpak-builder --disable-rofiles-fuse` disables the rofiles-fuse optimization and may work in unprivileged containers (slower). [CITED: github.com/flatpak/flatpak-github-actions — container image requires --privileged]
**Warning signs:** `Failed to mount proc, Permission denied` or `OSError: [Errno 1] Operation not permitted` during build.

### Pitfall 10: Drift-Guard Tests Parse YAML, Not Text
**What goes wrong (from project memory):** Source-grep guards assert a line exists, not that it runs correctly or in the right order. A permission added in a comment passes a text-grep check.
**How to avoid:** Drift-guards for the Flatpak manifest MUST load `io.github.kcreasey.MusicStreamer.yaml` with `yaml.safe_load()` and assert on the parsed Python structure (lists, dicts) — not `in manifest_text`. The deny-list (`--filesystem=home`, broad `--socket=session-bus`) is the security-critical half. [VERIFIED: project memory `feedback_drift_guard_presence_not_semantics.md` + CONTEXT.md D-13]

---

## Code Examples

### Manifest: finish-args section (verbatim)

```yaml
# Source: CONTEXT.md D-01/FP-04/FP-05; io.qt.qtwebengine.BaseApp docs
finish-args:
  - --share=network
  - --socket=pulseaudio
  - --socket=wayland
  - --socket=fallback-x11
  - --own-name=org.mpris.MediaPlayer2.MusicStreamer
  - --filesystem=~/.local/share/musicstreamer:ro
  - --env=QTWEBENGINE_DISABLE_SANDBOX=1
```

### Drift-guard test skeleton (YAML-parsed assertions)

```python
# Source: CONTEXT.md D-13; project pattern from tests/test_packaging_linux_spec.py
import yaml
from pathlib import Path

_MANIFEST = Path(__file__).resolve().parent.parent / "io.github.kcreasey.MusicStreamer.yaml"

@pytest.fixture(scope="module")
def manifest_data():
    return yaml.safe_load(_MANIFEST.read_text())

def test_flatpak_finish_args_allow_list(manifest_data):
    args = manifest_data["finish-args"]
    assert "--share=network" in args
    assert "--socket=pulseaudio" in args
    assert "--socket=wayland" in args
    assert "--socket=fallback-x11" in args
    assert "--own-name=org.mpris.MediaPlayer2.MusicStreamer" in args
    assert "--filesystem=~/.local/share/musicstreamer:ro" in args
    assert "--env=QTWEBENGINE_DISABLE_SANDBOX=1" in args

def test_flatpak_finish_args_deny_list(manifest_data):
    """Security-critical: absence of forbidden permissions."""
    args = manifest_data["finish-args"]
    assert "--filesystem=home" not in args, "broad home filesystem NOT permitted"
    assert "--filesystem=home:rw" not in args
    assert "--socket=session-bus" not in args, "broad session-bus NOT permitted"

def test_flatpak_runtime_version_pins(manifest_data):
    assert manifest_data["runtime-version"] == "6.8"
    assert manifest_data["base-version"] == "6.8"
    extensions = manifest_data.get("add-extensions", {})
    ffmpeg = extensions.get("org.freedesktop.Platform.ffmpeg-full", {})
    assert ffmpeg.get("version") == "24.08"
```

### First-launch detection skeleton

```python
# Source: CONTEXT.md D-01/D-03; paths.py analysis
import os

_HOST_DATA_DIR = os.path.expanduser("~/.local/share/musicstreamer")
_HOST_DB = os.path.join(_HOST_DATA_DIR, "musicstreamer.sqlite3")

def has_unsandboxed_data() -> bool:
    """True if old unsandboxed data exists at the narrow :ro mount."""
    return os.path.isfile(_HOST_DB)

def import_offered_flag_path() -> str:
    """Flag file in sandbox data dir — presence means wizard was already offered."""
    from musicstreamer import paths
    return os.path.join(paths.data_dir(), ".flatpak-import-offered")

def should_offer_import_wizard() -> bool:
    return has_unsandboxed_data() and not os.path.isfile(import_offered_flag_path())
```

### appstreamcli validate / desktop-file-validate pytest test

```python
# Source: CONTEXT.md D-15; FP-10
import subprocess, shutil, pytest
from pathlib import Path

_METAINFO = Path(__file__).resolve().parent.parent / "tools/linux-flatpak/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml"
_DESKTOP = Path(__file__).resolve().parent.parent / "tools/linux-flatpak/desktop/io.github.kcreasey.MusicStreamer.desktop"

@pytest.mark.skipif(not shutil.which("appstreamcli"), reason="appstreamcli not installed")
def test_appstreamcli_validate_passes():
    result = subprocess.run(
        ["appstreamcli", "validate", "--explain", str(_METAINFO)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"appstreamcli validate failed:\n{result.stdout}\n{result.stderr}"

@pytest.mark.skipif(not shutil.which("desktop-file-validate"), reason="desktop-file-validate not installed")
def test_desktop_file_validate_passes():
    result = subprocess.run(
        ["desktop-file-validate", str(_DESKTOP)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"desktop-file-validate failed:\n{result.stdout}\n{result.stderr}"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ffmpeg-full extension supported | `org.freedesktop.Platform.ffmpeg-full` discontinued in favor of `org.freedesktop.Platform.codecs-extra` (auto-installed by runtime) | Freedesktop SDK 25.08 (after 24.08) | Phase 86 targets 24.08 — ffmpeg-full is correct. If a future Flatpak update bumps to 25.08, codecs-extra replaces ffmpeg-full |
| YAML manifests less common | YAML is now the Flathub convention | ~2022 | JSON still works but YAML is idiomatic; project locks YAML per D-14 |
| QtWebEngine required special BaseApp | Qt6-native sandbox support added; `QTWEBENGINE_DISABLE_SANDBOX=1` still needed inside Flatpak | Qt 6.x | Flatpak sandbox-in-sandbox is solved at the Chromium level for Qt6 but still requires the env var |
| flatpak-pip-generator output JSON only | `--yaml` flag added | ~2023 | Use `--yaml` for YAML manifest consistency |

**Deprecated/outdated:**
- `--updateinformation` flag for linuxdeploy (Phase 85 pitfall) — NOT applicable to Flatpak; Flatpak uses OSTree for updates, not zsync
- conda-based GStreamer bundling (AppImage path) — not needed in Flatpak; runtime bundles GStreamer
- `GST_PLUGIN_SYSTEM_PATH_1_0`, `GIO_EXTRA_MODULES`, `SSL_CERT_FILE` in AppRun — AppImage-only workarounds; Flatpak runtime handles these natively

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `BASEAPP_REMOVE_WEBENGINE=1` removes `PySide6.QtWebEngineWidgets`, breaking FP-05 | Pitfall 1 / Manifest Pattern | If BaseApp keeps a stub, FP-05 might still work; but size would be larger; verdict: safe to NOT set the flag |
| A2 | node20 SDK extension is build-time only; node binary must be copied to `/app/bin/` | Pitfall 3 / Architecture | If node20 IS available at runtime via a separate mechanism, the explicit copy is redundant but harmless; fail mode is worse (no copy = no node at runtime) |
| A3 | `flatpak-pip-generator` with `--runtime='org.freedesktop.Sdk//24.08'` correctly excludes packages already in the KDE Platform/PySide BaseApp | Standard Stack | If generator includes PySide6, Pitfall 5 fires; mitigation is using a curated flatpak-requirements.txt instead of pyproject.toml |
| A4 | `org.freedesktop.Platform.ffmpeg-full//24.08` version aligns with `org.kde.Platform//6.8` (which is built on Freedesktop SDK 24.08) | ffmpeg-full Pattern | If KDE 6.8 is actually built on a different SDK version, extension version mismatch causes silent failure; planner should verify via `flatpak info org.kde.Platform//6.8` |
| A5 | GPG signing key in `secrets.LINUX_SIGNING_KEY` is passphrase-less | GPG Pitfall 8 | If key has a passphrase, CI will hang; mitigation: document CI key requirement clearly in build README |
| A6 | `org.freedesktop.Sdk.Extension.node20//24.08` branch number is correct for building against `org.kde.Sdk//6.8` | Node.js section | node20 is confirmed available for 24.08 branch in flathub remote-ls; but KDE Sdk//6.8 may use a different internal Freedesktop SDK version |
| A7 | GStreamer inside the KDE 6.8 runtime automatically discovers plugins at `/app/lib/ffmpeg/` when the extension mounts there | ffmpeg-full GStreamer integration | If GST_PLUGIN_PATH needs explicit env-var for the extension path, add `--env=GST_PLUGIN_PATH=/app/lib/ffmpeg` to finish-args as a fallback; verify by UAT |
| A8 | `io.qt.PySide.BaseApp//6.8` includes `PySide6.QtWebEngineWidgets` by default (i.e., without setting BASEAPP_REMOVE_WEBENGINE) | Manifest Pattern 1 | If BaseApp 6.8 ships WITHOUT WebEngine by default, a separate QtWebEngine module or the `io.qt.qtwebengine.BaseApp` must be layered; but current docs indicate it's included by default |

---

## Open Questions (RESOLVED)

1. **Does `org.kde.Platform//6.8` use Freedesktop SDK 24.08 internally?**
   - What we know: KDE Platform branches track Freedesktop SDK; 6.7 used 23.08. 6.8 likely uses 24.08.
   - What's unclear: Exact internal SDK version not confirmed from available data.
   - Recommendation: Verify with `flatpak run --command=bash org.kde.Platform//6.8 -c "cat /usr/manifest.json | grep freedesktop"` after installing the runtime. If 24.08 confirmed, `ffmpeg-full//24.08` and `node20//24.08` are correctly versioned.
   - RESOLVED: Verify empirically in Plan 01 Task 1 (run the `cat /usr/manifest.json | grep -i freedesktop` probe and record the internal SDK version in the README). Accept `//24.08` alignment for `ffmpeg-full` and `node20` pending that empirical confirmation; if the probe shows a different SDK branch, adjust the extension versions to match.

2. **Does GStreamer inside the KDE runtime auto-discover `/app/lib/ffmpeg/` without a GST_PLUGIN_PATH env-var?**
   - What we know: Flatpak extensions with `add-ld-path: .` affect library search but not necessarily `GST_PLUGIN_PATH`.
   - What's unclear: Whether the KDE runtime's GStreamer is configured to scan `/app/lib/` subdirectories, or whether an explicit `--env=GST_PLUGIN_PATH=/app/lib/ffmpeg` is needed in finish-args.
   - Recommendation: Add `--env=GST_PLUGIN_PATH=/app/lib/ffmpeg` to finish-args as a defensive measure. Test with `gst-inspect-1.0 avdec_aac` from inside the running sandbox. Remove the env-var if it proves unnecessary.
   - RESOLVED: Ship a defensive **commented-out** `# --env=GST_PLUGIN_PATH=/app/lib/ffmpeg` fallback in the manifest finish-args (Plan 01 Task 2) so the allow/deny-list drift-guard still sees a clean allow-list. Confirm auto-discovery live in Plan 05 UAT via `gst-inspect-1.0 avdec_aac`; uncomment the env-var only if AAC decode fails there.

3. **What is the correct `--runtime` flag for flatpak-pip-generator when targeting KDE Platform 6.8?**
   - What we know: The flag is `--runtime='org.freedesktop.Sdk//24.08'` per the tool's docs.
   - What's unclear: Whether using the Freedesktop Sdk vs the KDE Sdk produces different python version or ABI mismatches.
   - Recommendation: Use `--runtime='org.kde.Sdk//6.8'` instead, since the app actually builds against KDE Platform. If that runtime isn't installed locally, fall back to `--runtime='org.freedesktop.Sdk//24.08'`.
   - RESOLVED: Plan 01 Task 1 runs `flatpak-pip-generator --runtime='org.kde.Sdk//6.8'` first (the app builds against KDE Platform); if that SDK is not resolvable locally, fall back to `--runtime='org.freedesktop.Sdk//24.08'` and note the fallback in the README.

4. **Exact module source-type for the app in the manifest?**
   - What we know: During development, `type: dir` (local path `.`) works; for CI/release, the source should be a `type: archive` or `type: git` pointing at the repo.
   - What's unclear: Whether CI clones the repo or mounts it; whether `type: dir` is acceptable for a non-Flathub sideload build.
   - Recommendation: Use `type: dir, path: .` for local builds. For CI, the `flatpak/flatpak-github-actions` action automatically handles the source as a git checkout; no special source entry needed.
   - RESOLVED: Use `type: dir, path: .` for the app module (Plan 01 Task 2 local builds). For CI, `flatpak/flatpak-github-actions` handles the source as a git checkout (Plan 04) — no separate `type: git`/`type: archive` source entry is added.

5. **node20 SDK extension branch: `24.08` vs another?**
   - What we know: `flatpak remote-ls` confirms `org.freedesktop.Sdk.Extension.node20 20.20.1 24.08` is available in Flathub.
   - What's unclear: Whether `sdk-extensions: [org.freedesktop.Sdk.Extension.node20]` automatically resolves to the correct branch version, or whether a branch qualifier like `//24.08` is needed.
   - Recommendation: Planner should test both `org.freedesktop.Sdk.Extension.node20` and `org.freedesktop.Sdk.Extension.node20//24.08` in the `sdk-extensions` list; if branch is not specified, flatpak-builder uses the SDK's branch by default.
   - RESOLVED: Declare `sdk-extensions: [org.freedesktop.Sdk.Extension.node20]` without an explicit branch and let flatpak-builder inherit the SDK's branch (expected `//24.08`); verify empirically alongside OQ1 in Plan 01 Task 1 and pin the branch only if the inherited default does not resolve.

6. **Metainfo XML screenshots requirement for sideload (non-Flathub)?**
   - What we know: Flathub requires screenshots in metainfo. `appstreamcli validate` may issue warnings (not errors) for missing screenshots.
   - What's unclear: Whether `appstreamcli validate --strict` mode is used in FP-10's pre-flight check, and whether missing screenshots are errors or warnings.
   - Recommendation: Include at least one screenshot in metainfo.xml to pass `appstreamcli validate` cleanly. Use the current app Wayland screenshot from Phase 85's evidence bundle.
   - RESOLVED: Include one screenshot in metainfo.xml (Plan 01 Task 3) so `appstreamcli validate` passes cleanly. Screenshots are not strictly required for an off-Flathub sideload build, so a single Phase 85 Wayland evidence-bundle screenshot (or placeholder caption) is sufficient.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `flatpak` | Bundle install + test | ✓ | 1.16.6 | — |
| `flatpak-builder` | Manifest build | ✗ | — | `sudo apt install flatpak-builder` (candidate 1.4.8-1) |
| `org.kde.Platform//6.8` | flatpak-builder runtime | ✗ | — | `flatpak install flathub org.kde.Platform//6.8 org.kde.Sdk//6.8` |
| `io.qt.PySide.BaseApp//6.8` | flatpak-builder base | ✗ | — | `flatpak install flathub io.qt.PySide.BaseApp//6.8` |
| `org.freedesktop.Platform.ffmpeg-full//24.08` | AAC codec UAT | ✗ | — | `flatpak install flathub org.freedesktop.Platform.ffmpeg-full//24.08` (user) |
| `appstreamcli` | Metainfo validation | ✓ | 1.1.2 | — |
| `desktop-file-validate` | .desktop validation | ✓ | 0.28 | — |
| `flatpak-pip-generator` | python3-modules.yaml | ✗ | — | `pip install flatpak-pip-generator` (PyPI 2026.5.28) |
| `gpg` | GPG signing | ✓ | (system) | — |

**Missing dependencies with no fallback:**
- `flatpak-builder` — blocks all local build work; must be installed in Wave 0.
- `org.kde.Platform//6.8` + `org.kde.Sdk//6.8` — flatpak-builder cannot run without the runtimes.
- `io.qt.PySide.BaseApp//6.8` — required as `base:` in manifest.

**Missing dependencies with fallback:**
- `flatpak-pip-generator` — install via pip; ~1 min; blocks python3-modules.yaml generation but not manifest authoring.
- `org.freedesktop.Platform.ffmpeg-full//24.08` — install before AAC UAT only; does not block build.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (already in project) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `uv run --with pytest pytest tests/test_packaging_linux_spec.py tests/test_packaging_spec.py -x` |
| Full suite command | `uv run --with pytest pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PKG-LIN-FP-01 | App ID = `io.github.kcreasey.MusicStreamer` | source-text / YAML parse | `pytest tests/test_packaging_spec.py::test_flatpak_manifest_id` | ❌ Wave 0 |
| PKG-LIN-FP-03 | Runtime/base version pins | YAML parse | `pytest tests/test_packaging_spec.py::test_flatpak_runtime_version_pins` | ❌ Wave 0 |
| PKG-LIN-FP-04 | finish-args allow-list AND deny-list | YAML parse | `pytest tests/test_packaging_spec.py::test_flatpak_finish_args_allow_list` + `test_flatpak_finish_args_deny_list` | ❌ Wave 0 |
| PKG-LIN-FP-05 | `QTWEBENGINE_DISABLE_SANDBOX=1` in finish-args | YAML parse | `pytest tests/test_packaging_spec.py::test_flatpak_qtwebengine_disable_sandbox` | ❌ Wave 0 |
| PKG-LIN-FP-06 | `~/.local/share/musicstreamer:ro` in finish-args; import wizard detects and offers | YAML parse + unit | YAML: `test_flatpak_narrow_ro_mount`; unit: `test_first_launch_detection` | ❌ Wave 0 |
| PKG-LIN-FP-08 | MPRIS2 name in finish-args | YAML parse | `pytest tests/test_packaging_spec.py::test_flatpak_mpris2_own_name` | ❌ Wave 0 |
| PKG-LIN-FP-09 | `python3-modules.yaml` exists and is valid YAML | file existence + parse | `pytest tests/test_packaging_spec.py::test_python3_modules_yaml_exists` | ❌ Wave 0 |
| PKG-LIN-FP-10 | appstreamcli + desktop-file-validate pass | subprocess (skip-if-not-installed) | `pytest tests/test_packaging_spec.py::test_appstreamcli_validate_passes` + `test_desktop_file_validate_passes` | ❌ Wave 0 |
| signing | build.sh GPG signing discipline | source-text | `pytest tests/test_packaging_linux_spec.py::test_flatpak_build_sh_gpg_*` | ❌ Wave 0 |

All new tests extend `tests/test_packaging_spec.py` (per D-13/D-15 — the existing file is extended, not replaced, and covers both Windows + AppImage + Flatpak guards). The `tests/test_packaging_linux_spec.py` file already exists for AppImage-specific guards; Flatpak guards go into `test_packaging_spec.py` so the combined suite covers all packaging artifacts.

### Sampling Rate
- **Per task commit:** `uv run --with pytest pytest tests/test_packaging_spec.py tests/test_packaging_linux_spec.py -x`
- **Per wave merge:** `uv run --with pytest pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] Flatpak-specific drift-guard tests in `tests/test_packaging_spec.py` — covers FP-01/03/04/05/06/08/09/10
- [ ] `io.github.kcreasey.MusicStreamer.yaml` — the manifest itself (must exist before tests can parse it)
- [ ] `python3-modules.yaml` — pip deps manifest (must exist for FP-09 test)
- [ ] `tools/linux-flatpak/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml` — appstreamcli test target
- [ ] `tools/linux-flatpak/desktop/io.github.kcreasey.MusicStreamer.desktop` — desktop-file-validate test target
- [ ] Install: `sudo apt install flatpak-builder` + `flatpak install flathub org.kde.Platform//6.8 org.kde.Sdk//6.8 io.qt.PySide.BaseApp//6.8`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Not applicable (no new auth surface) |
| V3 Session Management | partial | GBS.FM cookies at `~/.var/app/.../gbs-cookies.txt` — existing Phase 76 pattern; sandbox data dir |
| V4 Access Control | yes | Flatpak sandbox permissions — drift-guard deny-list (no `--filesystem=home`, no broad session-bus) |
| V5 Input Validation | yes | Narrow `:ro` mount + existing `_validate_zip_members()` in settings_export.py for import security |
| V6 Cryptography | yes | GPG signing of `.flatpak` bundle — `flatpak build-bundle --gpg-sign` |

### Known Threat Patterns for Flatpak

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Overly broad `--filesystem=home` | Privilege escalation | Deny-list drift-guard; narrow `:ro` mount only (D-01) |
| `--socket=session-bus` leaking host services | Information disclosure | Deny-list drift-guard (D-13) |
| Import wizard path traversal via crafted ZIP | Tampering | Existing `_validate_zip_members()` in settings_export.py re-validates at commit time (WR-02 TOCTOU) |
| Unsigned bundle tampered in transit | Tampering | `flatpak build-bundle --gpg-sign` + user verifies with `gpg --verify` |
| QtWebEngine subprocess escaping Flatpak sandbox | Elevation of privilege | `QTWEBENGINE_DISABLE_SANDBOX=1` disables inner sandbox; outer Flatpak sandbox still constrains (acceptable per FP-05) |

---

## Project Constraints (from CLAUDE.md)

The project's CLAUDE.md contains a single directive:
- **Spike findings routing:** MusicStreamer spike findings → `Skill("spike-findings-musicstreamer")`. This phase does not produce a spike; it consumes the Phase 85a spike findings from `references/linux-appimage-bundling.md`.

No additional code conventions, forbidden patterns, or testing rules are specified in CLAUDE.md beyond the routing note. All drift-guard, test, and coding conventions used in this phase follow the established project patterns from Phase 85 and `tests/test_packaging_linux_spec.py`.

---

## Sources

### Primary (HIGH confidence)
- `github.com/flathub/io.qt.PySide.BaseApp` — BaseApp manifest structure, BASEAPP_REMOVE_WEBENGINE, cleanup-BaseApp.sh [CITED]
- `github.com/flathub/io.qt.qtwebengine.BaseApp` — `QTWEBENGINE_DISABLE_SANDBOX=1` verbatim spelling, sandbox-in-sandbox [CITED]
- `docs.flatpak.org/en/latest/extension.html` — ffmpeg-full add-extensions manifest syntax, mkdir cleanup-commands, sdk-extensions vs add-extensions [CITED]
- `docs.flatpak.org/en/latest/sandbox-permissions.html` — `--own-name` vs `--socket=session-bus`; default MPRIS2 name policy [CITED]
- `docs.flatpak.org/en/latest/conventions.html` — XDG_DATA_HOME → `~/.var/app/` override; .desktop + metainfo placement [CITED]
- `docs.flatpak.org/en/latest/python.html` — flatpak-pip-generator usage, YAML flag, module include pattern [CITED]
- `docs.flathub.org/docs/for-app-authors/metainfo-guidelines` — required metainfo XML fields, OARS format, releases tag, appstreamcli failures [CITED]
- `develop.kde.org/docs/getting-started/python/python-flatpak/` — KDE Platform 6.8 full manifest YAML, module ordering, cleanup-commands [CITED]
- `github.com/flatpak/flatpak-github-actions` — GitHub Actions container structure, --privileged requirement, gpg-sign input [CITED]
- **Codebase** — `musicstreamer/paths.py`, `musicstreamer/settings_export.py`, `musicstreamer/settings_import_dialog.py`, `musicstreamer/runtime_check.py`, `musicstreamer/yt_dlp_opts.py`, `musicstreamer/oauth_helper.py` — all verified by direct read [VERIFIED: codebase]
- **Phase 85a skill** — `references/linux-appimage-bundling.md` — AppImage vs Flatpak pattern contrasts [VERIFIED: file read]
- **Environment probes** — flatpak 1.16.6 installed; flatpak-builder 1.4.8 available via apt; appstreamcli 1.1.2; desktop-file-validate 0.28; node20//24.08 confirmed in Flathub; KDE Platform 6.8 confirmed in Flathub [VERIFIED: command outputs]
- **PyPI** — flatpak-pip-generator 2026.5.28 confirmed [VERIFIED: pip index versions]

### Secondary (MEDIUM confidence)
- `github.com/flatpak/flatpak-builder/issues/377` — GPG non-interactive CI challenge; passphrase-less key as solution [CITED]
- `manpages.debian.org/testing/flatpak/flatpak-metadata.5.en.html` — --own-name policy details [CITED]
- `github.com/flatpak/flatpak-builder-tools/blob/master/pip/readme.md` — flatpak-pip-generator --yaml flag, module include [CITED]

### Tertiary (LOW confidence)
- `discourse.flathub.org/t/help-in-building-flatpak-for-pyside6-python-app/4875` — offline build constraint context [WebSearch]

---

## Metadata

**Confidence breakdown:**
- Manifest structure (runtimes, finish-args, extensions, BaseApp): HIGH — verified against official Flathub documentation and KDE developer guides
- Node.js at runtime (copy-to-/app/bin pattern): HIGH — confirmed by Flatpak extension docs; sdk-extensions = build-time only is explicitly documented
- GStreamer + ffmpeg-full (avdec_aac path and auto-discovery): MEDIUM — extension syntax confirmed; exact GST_PLUGIN_PATH behavior inside KDE runtime is ASSUMED (A7)
- GPG CI signing (passphrase-less requirement): MEDIUM — confirmed challenge; passphrase-less solution is standard practice; exact CI workflow structure from official action
- First-launch import wizard (XDG_DATA_HOME path logic): HIGH — platformdirs + Flatpak XDG override is documented; codebase surface (settings_export.py) is verified
- MPRIS2 --own-name necessity: HIGH — FLATPAK_ID vs MusicStreamer name mismatch confirmed by analysis
- Pitfalls: HIGH — several confirmed against official docs; A1/A2/A3/A4/A7/A8 remain ASSUMED

**Research date:** 2026-06-02
**Valid until:** 2026-07-02 (30 days; KDE Platform 6.8 and Flathub BaseApp are stable branches)
