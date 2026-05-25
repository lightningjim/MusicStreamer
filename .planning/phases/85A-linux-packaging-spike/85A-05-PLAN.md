---
phase: 85A-linux-packaging-spike
plan: 05
type: execute
wave: 3
depends_on:
  - 85A-02
  - 85A-03
  - 85A-04
files_modified:
  - .planning/spikes/85a-linux-packaging-spike/build.sh
  - .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.desktop
  - .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.svg
autonomous: false
requirements:
  - SPIKE-85A
tags:
  - spike
  - linux-packaging
  - build-driver
  - appimage-assembly

must_haves:
  truths:
    - "build.sh orchestrates the full pipeline: source pins.env -> verify pins -> docker build ubuntu:22.04 -> assemble conda env from environment-spike.yml -> set GSTREAMER_PLUGINS_DIR + GSTREAMER_HELPERS_DIR BEFORE linuxdeploy -> produce AppImage"
    - "GSTREAMER_PLUGINS_DIR + GSTREAMER_HELPERS_DIR exports happen INSIDE the Docker build context BEFORE ./linuxdeploy --plugin gstreamer (Pitfall 2 mitigation)"
    - "build.sh GLIBC-greps the produced AppImage and exits 4 if > GLIBC_2.35 (Pitfall 1 + success criterion #2)"
    - "Final AppImage lands at .planning/spikes/85a-linux-packaging-spike/artifacts/MusicStreamer-spike-x86_64.AppImage"
    - "Minimum viable .desktop + icon present so linuxdeploy accepts the AppDir as well-formed (no MIME=audio yet; that's Phase 85)"
  artifacts:
    - path: ".planning/spikes/85a-linux-packaging-spike/build.sh"
      provides: "End-to-end build driver: docker build + AppImage assembly"
      contains: "GSTREAMER_PLUGINS_DIR"
      min_lines: 80
    - path: ".planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.desktop"
      provides: "Minimal .desktop entry so linuxdeploy doesn't reject the AppDir"
      contains: "Exec=AppRun"
    - path: ".planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.svg"
      provides: "Placeholder icon (linuxdeploy requires an icon)"
      min_lines: 1
  key_links:
    - from: "build.sh"
      to: "MusicStreamer-spike-x86_64.AppImage"
      via: "docker run + linuxdeploy invocation produces the artifact"
      pattern: "appimage"
    - from: "build.sh"
      to: "Plan 06 run-smoke.sh"
      via: "Plan 06 invokes the produced .AppImage inside each distrobox"
      pattern: "MusicStreamer-spike-x86_64.AppImage"
---

<objective>
Write the build driver (`build.sh`) that performs end-to-end AppImage assembly inside an `ubuntu:22.04` Docker container — the load-bearing orchestration step that validates the toolchain's two LIVE risks (RESEARCH.md §Summary lines 7-12).

Purpose: Implements RESEARCH.md §Pattern 2 (build.sh "mirror Phase 43 build.ps1" shape, lines 251-259) + §Common Pitfalls Pitfall 1 (GLIBC baseline) and Pitfall 2 (GSTREAMER_PLUGINS_DIR redirect). The build script's two CRITICAL responsibilities: (a) exporting `GSTREAMER_PLUGINS_DIR=$APPDIR/usr/conda/lib/gstreamer-1.0` + `GSTREAMER_HELPERS_DIR=$APPDIR/usr/conda/libexec/gstreamer-1.0` BEFORE invoking `./linuxdeploy --plugin gstreamer` (otherwise the plugin scans Debian multiarch and bundles zero plugins per Pitfall 2); (b) GLIBC-grepping the produced AppImage and exiting 4 if > 2.35.
Output: 3 files (build.sh + desktop/.desktop + desktop/.svg) + the produced `artifacts/MusicStreamer-spike-x86_64.AppImage` (gitignored).
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md
@.planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md
@.planning/spikes/85a-linux-packaging-spike/pins.env
@.planning/spikes/85a-linux-packaging-spike/Dockerfile
@.planning/spikes/85a-linux-packaging-spike/environment-spike.yml
@.planning/spikes/85a-linux-packaging-spike/AppRun
@.planning/spikes/85a-linux-packaging-spike/hello_world.py
@.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/build.ps1

<interfaces>
<!-- The two CRITICAL env-var redirects (RESEARCH.md §Pitfall 2 lines 299-309 + Architecture diagram lines 153-160). -->

```bash
# INSIDE the Docker build container, BEFORE linuxdeploy --plugin gstreamer:
export GSTREAMER_PLUGINS_DIR="$APPDIR/usr/conda/lib/gstreamer-1.0"
export GSTREAMER_HELPERS_DIR="$APPDIR/usr/conda/libexec/gstreamer-1.0"

# Then:
./linuxdeploy-x86_64.AppImage --appdir "$APPDIR" \
  --plugin conda \
  --plugin gstreamer \
  --desktop-file "$APPDIR/musicstreamer-spike.desktop" \
  --icon-file "$APPDIR/musicstreamer-spike.svg" \
  --output appimage
```

<!-- Phase 43 build.ps1 exit-code conventions (RESEARCH.md lines 255-259): -->
# 0=ok, 1=env missing, 2=pyinstaller/bundle failed, 3=smoke failed, 4=GLIBC > 2.35
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| host shell -> Docker daemon | build.sh invokes `docker build` + `docker run` on host; standard Docker trust |
| docker container -> github asset CDN | Inside the container, curl downloads the 3 pinned toolchain assets over HTTPS; verify-pins.sh runs first to gate |
| docker container -> repo.anaconda.com (miniconda) | linuxdeploy-plugin-conda fetches miniconda installer; MINICONDA_VERSION pin prevents drift |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-85A-05-SC | Tampering | Toolchain asset drift between pin time and build time | mitigate | build.sh sources pins.env then calls `verify-pins.sh` as its FIRST step (after Dockerfile check); fail-fast on drift before any other side-effects |
| T-85A-05-SC2 | Tampering | conda solver pulls package that wasn't in environment-spike.yml | accept (low) | Channel-only conda-forge pin; environment-spike.yml is the deps source-of-truth; Phase 85 will pin specific versions |
| T-85A-05-EoP | EoP | Docker container running as root | accept | Docker container is throwaway; produces only an .AppImage file copied back to host workspace; no host filesystem modifications outside `.planning/spikes/85a-linux-packaging-spike/artifacts/` |
</threat_model>

<tasks>

<task type="auto">
  <name>Task 1: Author minimal .desktop entry + placeholder SVG icon</name>
  <files>.planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.desktop, .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.svg</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Recommended Project Structure (lines 187-205) — desktop/ subdir
    - .planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md "Out of scope" (lines 22-32) — .desktop + icon + MIME=audio integration is Phase 85; spike just needs linuxdeploy not to reject the AppDir
  </read_first>
  <acceptance_criteria>
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.desktop`
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.svg`
    - content-grep: `grep -q '^\[Desktop Entry\]' .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.desktop`
    - content-grep: `grep -q '^Type=Application' .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.desktop`
    - content-grep: `grep -q '^Exec=AppRun' .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.desktop`
    - content-grep: `grep -q '^Icon=musicstreamer-spike' .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.desktop`
    - shell-exit (desktop-file-validate clean): `desktop-file-validate .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.desktop 2>&1 | (! grep -E '^[^[:space:]].*error')` (no error lines)
    - content-grep (svg sanity): `head -1 .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.svg | grep -qiE '<\?xml|<svg'`
  </acceptance_criteria>
  <action>Create two files:

(1) `.planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.desktop`:
```
[Desktop Entry]
Type=Application
Name=MusicStreamer Spike
Comment=Phase 85a hello-world playbin3 spike
Exec=AppRun
Icon=musicstreamer-spike
Terminal=true
Categories=Audio;AudioVideo;Player;
```
(Terminal=true so spike output is visible during distrobox runs; Phase 85 changes to false.)

(2) `.planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.svg` — minimal valid SVG placeholder (10-20 lines max). Plain square + text "MS-85a" should suffice. linuxdeploy just needs a non-empty `Icon=musicstreamer-spike.svg` to accept the AppDir; pixel art is Phase 85's surface.

Example SVG body (gray square with monospace text):
```
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" fill="#444"/>
  <text x="32" y="36" font-family="monospace" font-size="10"
        fill="#fff" text-anchor="middle">MS-85a</text>
</svg>
```

If `desktop-file-validate` is not installed in the host shell, the test's `||true` clause is acceptable — the real validation is linuxdeploy accepting the AppDir, which Task 2 exercises.</action>
  <verify>
    <automated>test -f .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.desktop && test -f .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.svg && grep -q '^Exec=AppRun' .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.desktop && head -1 .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.svg | grep -qiE '<\?xml|<svg' && { command -v desktop-file-validate >/dev/null && desktop-file-validate .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.desktop || true; }</automated>
  </verify>
  <done>Both files present, `.desktop` has required keys (Type, Name, Exec, Icon, Categories), SVG is valid XML/SVG.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Author build.sh end-to-end driver + drive a successful build</name>
  <files>.planning/spikes/85a-linux-packaging-spike/build.sh</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Pattern 2 build.sh shape (lines 251-259)
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §System Architecture Diagram (lines 141-183) — the exact env-redirect-then-linuxdeploy step
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Pitfall 1 + §Pitfall 2 — the two non-negotiable mitigations build.sh enforces
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Anti-Patterns to Avoid (lines 262-266) — what build.sh MUST NOT do
    - .claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/build.ps1 (PowerShell analog; same shape, different shell)
  </read_first>
  <what-built>An end-to-end shell driver that drives the Docker container build, conda env assembly, AppDir layout, linuxdeploy invocation, AppImage production, and GLIBC verification. Kyle confirms the produced AppImage actually exists at artifacts/MusicStreamer-spike-x86_64.AppImage and the GLIBC grep reports <= GLIBC_2.35.</what-built>
  <how-to-verify>
    Run on host:
    ```
    bash .planning/spikes/85a-linux-packaging-spike/build.sh 2>&1 | tee /tmp/85a-build.log
    ls -lh .planning/spikes/85a-linux-packaging-spike/artifacts/MusicStreamer-spike-x86_64.AppImage
    strings .planning/spikes/85a-linux-packaging-spike/artifacts/MusicStreamer-spike-x86_64.AppImage | grep GLIBC_ | sort -V | tail -1
    ```
    Expected: build.sh exits 0 (or 4 if GLIBC drift detected — negative pivot per D-09); AppImage present; final GLIBC line is `GLIBC_2.35` or lower.

    NEGATIVE-PIVOT (per CONTEXT.md D-09): If `gst-inspect-1.0 avdec_aac` fails to resolve from inside the produced AppImage, STOP the spike and report — do NOT silently pivot to manual plugin copy. Same for GLIBC > 2.35.
  </how-to-verify>
  <acceptance_criteria>
    - file-exists: `test -x .planning/spikes/85a-linux-packaging-spike/build.sh`
    - shell-exit (syntax): `bash -n .planning/spikes/85a-linux-packaging-spike/build.sh`
    - content-grep: `grep -q 'set -euo pipefail' .planning/spikes/85a-linux-packaging-spike/build.sh`
    - content-grep: `grep -q 'verify-pins.sh' .planning/spikes/85a-linux-packaging-spike/build.sh` (calls drift-guard early)
    - content-grep: `grep -q 'GSTREAMER_PLUGINS_DIR' .planning/spikes/85a-linux-packaging-spike/build.sh`
    - content-grep: `grep -q 'GSTREAMER_HELPERS_DIR' .planning/spikes/85a-linux-packaging-spike/build.sh`
    - content-grep (order check): the line containing `GSTREAMER_PLUGINS_DIR=` MUST appear BEFORE the line containing `linuxdeploy.*--plugin gstreamer`: `awk '/GSTREAMER_PLUGINS_DIR=/{ord=NR} /linuxdeploy.*--plugin gstreamer/{if(NR<ord||ord==0){exit 1}} END{exit 0}' .planning/spikes/85a-linux-packaging-spike/build.sh`
    - content-grep: `grep -qE 'docker (build|run).*ubuntu' .planning/spikes/85a-linux-packaging-spike/build.sh`
    - content-grep: `grep -qE 'strings.*GLIBC_|GLIBC_2\\.35' .planning/spikes/85a-linux-packaging-spike/build.sh` (GLIBC grep present)
    - content-grep: `grep -qE 'exit 4' .planning/spikes/85a-linux-packaging-spike/build.sh` (GLIBC > 2.35 exit path present)
    - file-exists post-build: `test -f .planning/spikes/85a-linux-packaging-spike/artifacts/MusicStreamer-spike-x86_64.AppImage`
    - shell-exit GLIBC: `strings .planning/spikes/85a-linux-packaging-spike/artifacts/MusicStreamer-spike-x86_64.AppImage | grep -E 'GLIBC_[0-9]' | sort -V | tail -1 | grep -qE 'GLIBC_2\\.(1[0-9]|2[0-9]|3[0-5])$'`
    - shell-exit AppImage runs: `.planning/spikes/85a-linux-packaging-spike/artifacts/MusicStreamer-spike-x86_64.AppImage --appimage-extract-and-run --help` exits 0 or 1 (not 127/126 — the AppImage at least mounts and execs)
    - manual-checkpoint: Kyle confirms the build log shows successful linuxdeploy invocation + conda env materialization
  </acceptance_criteria>
  <action>Create `.planning/spikes/85a-linux-packaging-spike/build.sh` with the following structure (chmod +x after writing):

```
#!/usr/bin/env bash
# Phase 85a build driver. Mirrors Phase 43 build.ps1 shape on Linux.
# Exit codes (matching Phase 43 + RESEARCH.md §Pattern 2):
#   0 = AppImage produced + GLIBC <= 2.35
#   1 = env missing (Docker not available, pins.env malformed, etc.)
#   2 = linuxdeploy/bundle failed
#   3 = smoke failed (reserved; smoke runs in Plan 06 / run-smoke.sh)
#   4 = GLIBC > 2.35 (Pitfall 1 negative pivot trigger)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARTIFACTS="${HERE}/artifacts"
mkdir -p "${ARTIFACTS}"

# Step 1: source pins, verify upstream hasn't drifted
# shellcheck source=./pins.env
source "${HERE}/pins.env"
bash "${HERE}/verify-pins.sh"  # exits 2 on drift; set -e propagates

# Step 2: docker build the ubuntu:22.04 base
docker build -f "${HERE}/Dockerfile" -t ms-spike-build:22.04 "${HERE}"

# Step 3: run the build inside the container
#   - Mount HERE as /work
#   - Mount ARTIFACTS as /work/artifacts
#   - Pass through pins.env via -e LINUXDEPLOY_* (so the inner shell doesn't re-curl from raw URLs without the SHA gate)
docker run --rm --privileged \
  -v "${HERE}":/work \
  -v "${ARTIFACTS}":/work/artifacts \
  -e LINUXDEPLOY_URL -e LINUXDEPLOY_SHA256 \
  -e LINUXDEPLOY_PLUGIN_CONDA_URL -e LINUXDEPLOY_PLUGIN_CONDA_SHA256 \
  -e LINUXDEPLOY_PLUGIN_GSTREAMER_URL -e LINUXDEPLOY_PLUGIN_GSTREAMER_SHA256 \
  -e MINICONDA_VERSION \
  ms-spike-build:22.04 \
  bash -euo pipefail -c '
    set -x
    cd /work
    APPDIR=/work/AppDir
    rm -rf "$APPDIR" && mkdir -p "$APPDIR"

    # Download + SHA-verify pinned assets
    curl -fsSL -o /tmp/linuxdeploy.AppImage "$LINUXDEPLOY_URL"
    echo "$LINUXDEPLOY_SHA256  /tmp/linuxdeploy.AppImage" | sha256sum --check
    chmod +x /tmp/linuxdeploy.AppImage

    curl -fsSL -o /tmp/linuxdeploy-plugin-conda.sh "$LINUXDEPLOY_PLUGIN_CONDA_URL"
    echo "$LINUXDEPLOY_PLUGIN_CONDA_SHA256  /tmp/linuxdeploy-plugin-conda.sh" | sha256sum --check
    chmod +x /tmp/linuxdeploy-plugin-conda.sh

    curl -fsSL -o /tmp/linuxdeploy-plugin-gstreamer.sh "$LINUXDEPLOY_PLUGIN_GSTREAMER_URL"
    echo "$LINUXDEPLOY_PLUGIN_GSTREAMER_SHA256  /tmp/linuxdeploy-plugin-gstreamer.sh" | sha256sum --check
    chmod +x /tmp/linuxdeploy-plugin-gstreamer.sh

    # Place plugin scripts where linuxdeploy expects: PATH-resolved adjacent
    cp /tmp/linuxdeploy-plugin-conda.sh /usr/local/bin/
    cp /tmp/linuxdeploy-plugin-gstreamer.sh /usr/local/bin/

    # AppDir skeleton
    cp /work/AppRun "$APPDIR/AppRun"
    chmod +x "$APPDIR/AppRun"
    cp /work/hello_world.py "$APPDIR/"
    cp /work/smoke_test.py "$APPDIR/"
    cp /work/test_url.txt "$APPDIR/"
    cp /work/desktop/musicstreamer-spike.desktop "$APPDIR/"
    cp /work/desktop/musicstreamer-spike.svg "$APPDIR/"

    # CRITICAL: redirect plugin-gstreamer to the conda layout BEFORE linuxdeploy invocation
    # (Pitfall 2 mitigation; without this the plugin scans /usr/lib/$(uname -m)-linux-gnu/gstreamer-1.0 and bundles nothing)
    export GSTREAMER_PLUGINS_DIR="$APPDIR/usr/conda/lib/gstreamer-1.0"
    export GSTREAMER_HELPERS_DIR="$APPDIR/usr/conda/libexec/gstreamer-1.0"

    # conda env shape passed to plugin-conda
    export CONDA_PACKAGES=""   # empty; plugin-conda reads environment.yml when CONDA_CHANNELS unset
    export CONDA_CHANNELS=conda-forge
    cp /work/environment-spike.yml /work/environment.yml   # plugin-conda looks for this exact name

    # Bundle
    /tmp/linuxdeploy.AppImage --appdir "$APPDIR" \
      --plugin conda \
      --plugin gstreamer \
      --desktop-file "$APPDIR/musicstreamer-spike.desktop" \
      --icon-file "$APPDIR/musicstreamer-spike.svg" \
      --output appimage

    # Move output to artifacts/
    mv MusicStreamer*Spike*.AppImage /work/artifacts/MusicStreamer-spike-x86_64.AppImage 2>/dev/null \
      || mv ./*.AppImage /work/artifacts/MusicStreamer-spike-x86_64.AppImage
  ' || { echo "BUILD_FAIL exit=$?" >&2; exit 2; }

# Step 4: GLIBC grep on host (Pitfall 1 / success criterion #2)
APPIMG="${ARTIFACTS}/MusicStreamer-spike-x86_64.AppImage"
[[ -f "$APPIMG" ]] || { echo "BUILD_FAIL no_appimage=$APPIMG" >&2; exit 2; }

GLIBC_MAX="$(strings "$APPIMG" | grep -E '^GLIBC_[0-9]+\.[0-9]+$' | sort -V | tail -1 || echo "GLIBC_unknown")"
echo "GLIBC_GREP $GLIBC_MAX"

# Compare against 2.35
case "$GLIBC_MAX" in
  GLIBC_2.1?|GLIBC_2.2?|GLIBC_2.3[0-5]) echo "GLIBC_OK $GLIBC_MAX <= 2.35" ;;
  *) echo "GLIBC_FAIL $GLIBC_MAX > 2.35  (Pitfall 1 negative pivot trigger)" >&2; exit 4 ;;
esac

echo "BUILD_OK appimage=$APPIMG glibc=$GLIBC_MAX"
```

Pause and ASK Kyle to confirm the build ran to completion (or report any failure with the exact failure mode for negative-pivot per D-09).</action>
  <resume-signal>Kyle types "built" once the build.sh run produced the AppImage with GLIBC <= 2.35. If it failed, Kyle reports the failure mode verbatim so the spike can either (a) fix the build-script issue or (b) record the negative pivot in findings (per Pitfalls 1/2/8 trigger conditions).</resume-signal>
  <verify>
    <automated>test -x .planning/spikes/85a-linux-packaging-spike/build.sh && bash -n .planning/spikes/85a-linux-packaging-spike/build.sh && grep -q 'set -euo pipefail' .planning/spikes/85a-linux-packaging-spike/build.sh && grep -q 'GSTREAMER_PLUGINS_DIR' .planning/spikes/85a-linux-packaging-spike/build.sh && awk '/GSTREAMER_PLUGINS_DIR=/{ord=NR} /linuxdeploy.*--plugin gstreamer/{if(NR<ord||ord==0){exit 1}} END{exit 0}' .planning/spikes/85a-linux-packaging-spike/build.sh && test -f .planning/spikes/85a-linux-packaging-spike/artifacts/MusicStreamer-spike-x86_64.AppImage && strings .planning/spikes/85a-linux-packaging-spike/artifacts/MusicStreamer-spike-x86_64.AppImage | grep -E '^GLIBC_[0-9]+\.[0-9]+$' | sort -V | tail -1 | grep -qE 'GLIBC_2\.(1[0-9]|2[0-9]|3[0-5])$'</automated>
    <human-check>Kyle confirms build success.</human-check>
  </verify>
  <done>build.sh exists + is executable + syntax-valid + has the GSTREAMER_PLUGINS_DIR export BEFORE linuxdeploy invocation; running it produces artifacts/MusicStreamer-spike-x86_64.AppImage with GLIBC <= 2.35; Kyle approved.</done>
</task>

</tasks>

<verification>
- `build.sh` exists, is executable, passes `bash -n`
- The line setting `GSTREAMER_PLUGINS_DIR` appears BEFORE the line invoking `linuxdeploy --plugin gstreamer` (awk gate)
- `artifacts/MusicStreamer-spike-x86_64.AppImage` exists post-run
- GLIBC grep returns 2.35 or lower
- AppImage at least self-mounts (--appimage-extract-and-run --help exits 0)
</verification>

<success_criteria>
- AppImage artifact present
- Success criterion #2 (GLIBC <= 2.35) verified
- Pitfall 1 + Pitfall 2 mitigations both ENFORCED in script structure (GLIBC exit-4 trigger + GSTREAMER_PLUGINS_DIR ordering gate)
- Plan 06 (distrobox smoke) has the AppImage to verify against
</success_criteria>

<output>
Create `.planning/phases/85A-linux-packaging-spike/85A-05-SUMMARY.md` when done. Capture: final AppImage size, GLIBC max symbol observed, MINICONDA_VERSION used, build duration, any deviations or negative-pivot triggers hit.
</output>
