# Phase 85: linux-common-appimage-build — Pattern Map

**Mapped:** 2026-05-27
**Files analyzed:** 9 new/modified
**Analogs found:** 8 / 9 (one greenfield — `.github/workflows/linux-appimage.yml` has no in-repo analog because `.github/` does not yet exist)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tools/linux-build/build.sh` | build script (shell driver) | batch / build-pipeline | `.planning/spikes/85a-linux-packaging-spike/build.sh` | **exact** (refactor target) |
| `tools/linux-build/environment.yml` | env / pin-manifest (conda) | config | `.planning/spikes/85a-linux-packaging-spike/environment-spike.yml` | **exact** (fork) |
| `tools/linux-build/AppRun` | runtime launcher (shell) | request-response (env-export + exec) | `.planning/spikes/85a-linux-packaging-spike/AppRun` | **exact** (verbatim + 2 edits per Pitfall 19/20) |
| `tools/linux-build/Dockerfile` | container build spec | config | `.planning/spikes/85a-linux-packaging-spike/Dockerfile` | **exact** (verbatim copy per hand-off item 2) |
| `tools/linux-build/pins.env` + `verify-pins.sh` | supply-chain pin manifest + guard | config + drift-guard | `.planning/spikes/85a-linux-packaging-spike/{pins.env,verify-pins.sh}` | **exact** (verbatim copy per hand-off item 4) |
| `tools/linux-build/smoke_test.py` | smoke test driver (python) | request-response (pipeline assertion) | `.planning/spikes/85a-linux-packaging-spike/smoke_test.py` | **role-match**; D-05 changes from spike copy-paste to `import musicstreamer.url_helpers` |
| `.github/workflows/linux-appimage.yml` | CI workflow (YAML) | event-driven (`workflow_dispatch`) | (greenfield — no `.github/` in repo) — shape inferred from spike `build.sh` + 85A-SPIKE-FINDINGS hand-off | **no analog** |
| `tools/check_linux_bundle.py` (optional drift-guard) | drift-guard (python CLI + pytest) | batch / static-assertion | `tools/check_bundle_plugins.py` + `tests/test_packaging_spec.py` | **role-match** (Windows analog cross-platform) |
| `tools/linux-build/README.md` (or repo-root pointer) | docs | static | `packaging/windows/README.md` | **role-match** (cross-platform docs sibling) |

## Pattern Assignments

### `tools/linux-build/build.sh` (build script, batch/build-pipeline)

**Analog:** `.planning/spikes/85a-linux-packaging-spike/build.sh` (270 lines, working build)

**Exit-code preamble + `set -euo pipefail` shape** (lines 1-72):
```bash
#!/usr/bin/env bash
# Phase 85a build driver. Mirrors Phase 43 build.ps1 shape on Linux.
# Exit codes (matching Phase 43 + RESEARCH.md §Pattern 2):
#   0 = AppImage produced + GLIBC <= 2.35
#   1 = env missing (Docker not available, pins.env malformed, etc.)
#   2 = linuxdeploy/bundle failed
#   3 = smoke failed (reserved; smoke runs in Plan 06 / run-smoke.sh)
#   4 = GLIBC > 2.35 (Pitfall 1 negative pivot trigger)
# [Phase 85 extends: 5 = GPG_KEY_ID unset and SKIP_SIGN != 1 (D-09);
#                    6 = gpg2 sign failed]
...
set -euo pipefail
```

**Phase 85 refactor (D-01) — YAML→CONDA_PACKAGES synthesis** replaces the hardcoded enumeration at spike `build.sh` lines 105-106:
```bash
# CURRENT (spike) — hardcoded; Phase 85 replaces with yq parse of environment.yml
export CONDA_CHANNELS="conda-forge"
export CONDA_PACKAGES="python=3.12;pyside6;pygobject;gst-python;gstreamer;gst-plugins-base;gst-plugins-good;gst-plugins-bad;gst-plugins-ugly;gst-libav;glib-networking"
```
D-01 replacement (CONTEXT.md §Specifics line 116):
```bash
# Phase 85 D-01: parse environment.yml; pip:-sublist becomes pip --no-deps source (D-03).
CONDA_PACKAGES="$(yq -r '.dependencies[] | select(type=="string")' tools/linux-build/environment.yml | tr '\n' ';')"
export CONDA_PACKAGES
```

**Pin-source + drift-verify pattern** (lines 78-88; copy verbatim):
```bash
# Step 1: source pins, verify upstream hasn't drifted
# `set -a` auto-exports every variable assigned in pins.env so that the
# `docker run -e LINUXDEPLOY_URL` (value-less) flag below can forward them
# into the container.
set -a
# shellcheck source=./pins.env
source "${HERE}/pins.env"
set +a
bash "${HERE}/verify-pins.sh"  # exits 2 on drift; set -e propagates
```

**`docker run` flag block — every flag load-bearing** (lines 116-132; copy verbatim, all flags justified in spike comments lines 14-71):
```bash
docker run --rm --privileged \
  --network=host \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp/_home \
  -e XDG_CACHE_HOME=/tmp/_cache \
  -e CONDA_FETCH_THREADS=1 \
  -e CONDA_SKIP_CLEANUP=strip \
  -v "${HERE}":/work \
  -v "${ARTIFACTS}":/work/artifacts \
  -e LINUXDEPLOY_URL -e LINUXDEPLOY_SHA256 \
  -e LINUXDEPLOY_PLUGIN_CONDA_URL -e LINUXDEPLOY_PLUGIN_CONDA_SHA256 \
  -e LINUXDEPLOY_PLUGIN_CONDA_PATCHED_SHA256 \
  ...
```

**Approach P sed-patch (Pitfalls 13/13b)** (lines 152-156; copy verbatim):
```bash
sed -i \
  -e "s|Miniconda3-latest-Linux-x86_64\.sh|Miniforge3-${MINIFORGE_TAG}-Linux-x86_64.sh|g" \
  -e "s|https://repo\.anaconda\.com/miniconda/|https://github.com/conda-forge/miniforge/releases/download/${MINIFORGE_TAG}/|g" \
  /tmp/linuxdeploy-plugin-conda.sh
echo "$LINUXDEPLOY_PLUGIN_CONDA_PATCHED_SHA256  /tmp/linuxdeploy-plugin-conda.sh" | sha256sum --check
```

**Build-time env exports (Pitfalls 2 + 14)** (lines 181-198; copy verbatim):
```bash
export GSTREAMER_PLUGINS_DIR="$APPDIR/usr/conda/lib/gstreamer-1.0"
export GSTREAMER_HELPERS_DIR="$APPDIR/usr/conda/libexec/gstreamer-1.0"
export LD_LIBRARY_PATH="$APPDIR/usr/conda/lib:$APPDIR/usr/conda/lib/gstreamer-1.0:${LD_LIBRARY_PATH:-}"
```

**linuxdeploy invocation with `--appimage-extract-and-run`** (lines 206-211; copy verbatim, adapt to add `--updateinformation` per D-11 and post-step sign per D-08):
```bash
/tmp/linuxdeploy.AppImage --appimage-extract-and-run --appdir "$APPDIR" \
  --plugin conda \
  --plugin gstreamer \
  --desktop-file "$APPDIR/musicstreamer-spike.desktop" \
  --icon-file "$APPDIR/musicstreamer-spike.svg" \
  --output appimage
```

**D-11 zsync embedding** (CONTEXT.md §Specifics line 118) — add flag to the above:
```bash
  --updateinformation "gh-releases-zsync|kcreasey|MusicStreamer|latest|MusicStreamer-*-x86_64.AppImage.zsync"
```

**D-08/D-09 GPG signing** (CONTEXT.md §Specifics line 117) — new step after linuxdeploy + before final mv:
```bash
# D-09 fail-fast guard
if [[ -z "${GPG_KEY_ID:-}" && "${SKIP_SIGN:-0}" != "1" ]]; then
  echo "BUILD_FAIL: GPG_KEY_ID unset and SKIP_SIGN!=1 (D-09)" >&2; exit 5
fi
if [[ "${SKIP_SIGN:-0}" != "1" ]]; then
  gpg2 --detach-sign --armor --local-user "$GPG_KEY_ID" "$APPIMAGE_PATH" \
    || { echo "BUILD_FAIL: gpg2 sign failed" >&2; exit 6; }
fi
```

**objdump DT_VERNEED scan (Pitfall 16)** (lines 233-267; copy verbatim — replaces strings-grep):
```bash
TMPEXTRACT="$(mktemp -d "${TMPDIR:-/tmp}/85a-glibc-scan.XXXXXX")"
trap 'rm -rf "$TMPEXTRACT"' EXIT INT TERM
GLIBC_MAX="$(find -L "$TMPEXTRACT/squashfs-root" -type f \
    \( -name '*.so' -o -name '*.so.*' -o -perm /u+x \) \
    -exec objdump -T {} \; 2>/dev/null \
  | grep -oE 'GLIBC_[0-9]+\.[0-9]+' | sort -V -u | tail -1)"
case "$GLIBC_MAX" in
  GLIBC_2.[0-9]|GLIBC_2.1?|GLIBC_2.2?|GLIBC_2.3[0-5]) echo "GLIBC_OK $GLIBC_MAX <= 2.35" ;;
  *) echo "GLIBC_FAIL $GLIBC_MAX > 2.35  (Pitfall 1 negative pivot trigger)" >&2; exit 4 ;;
esac
```

---

### `tools/linux-build/environment.yml` (env file, config)

**Analog:** `.planning/spikes/85a-linux-packaging-spike/environment-spike.yml` (46 lines)

**Header rationale block** (lines 1-30; preserve verbatim — Phase 43 stack lock + Pitfall 7 cross-link):
```yaml
# Channel pinning rationale:
#   conda-forge is the ONLY viable bridge between PyGObject + GStreamer 1.28+
#   and the AppImage. Phase 43 (Windows spike) proved this channel; PKG-LIN-APP-03
#   ("same plugin set as the Windows installer") inherits the channel choice.
#   No `defaults` channel — package squatting risk + Phase 43 stack lock.
#
# Linux-specific divergences from Phase 43's Windows env (RESEARCH.md §Pitfall 7):
#   - gst-libav        : Linux conda-forge ships AAC/H.264 decoders here
#   - gst-python       : Linux must list explicitly
#   - glib-networking  : Linux must list explicitly for TLS modules
```

**Base 11-package list (verbatim from spike, lines 31-45):**
```yaml
name: spike-linux   # Phase 85: rename to e.g. "musicstreamer-build"
channels:
  - conda-forge
dependencies:
  - python=3.12
  - pyside6
  - pygobject
  - gst-python
  - gstreamer
  - gst-plugins-base
  - gst-plugins-good
  - gst-plugins-bad
  - gst-plugins-ugly
  - gst-libav
  - glib-networking
```

**Phase 85 extensions per spike hand-off item 3** (add MusicStreamer v2.2 deps via `pip:` sublist to enable D-03 `pip install --no-deps` post-step):
```yaml
  - pip
  - pip:
      - mutagen
      - pillow
      - requests
      - yt-dlp
      - streamlink
      - platformdirs
      - chardet<6
  # `musicstreamer` itself installed via D-03 `pip install --no-deps .` AFTER plugin-conda
```

---

### `tools/linux-build/AppRun` (runtime launcher, request-response)

**Analog:** `.planning/spikes/85a-linux-packaging-spike/AppRun` (90 lines)

**Header rationale + APPDIR resolution** (lines 1-45; copy verbatim including pitfall cross-references):
```bash
#!/bin/bash
# CRITICAL: GST_REGISTRY_FORK="no" is NOT the same flag as GST_REGISTRY_REUSE_PLUGIN_SCANNER="no" (Pitfall 3).
# CRITICAL: GIO_EXTRA_MODULES is required for HTTPS support (Pitfall 4).
# CRITICAL: SSL_CERT_FILE is required for HTTPS cert validation (Pitfall 17 — spike-discovered).
HERE="$(dirname "$(readlink -f "${0}")")"
export APPDIR="${HERE}"
```

**GStreamer + GIO + SSL env block** (lines 47-83; copy verbatim — all 10 exports load-bearing):
```bash
export GST_PLUGIN_SYSTEM_PATH_1_0="${APPDIR}/usr/conda/lib/gstreamer-1.0"
export GST_PLUGIN_PATH_1_0="${APPDIR}/usr/conda/lib/gstreamer-1.0"
export GST_PLUGIN_SCANNER="${APPDIR}/usr/conda/libexec/gstreamer-1.0/gst-plugin-scanner"
export GST_PLUGIN_SCANNER_1_0="${APPDIR}/usr/conda/libexec/gstreamer-1.0/gst-plugin-scanner"
export GST_REGISTRY_FORK="no"                                                    # Pitfall 3
export GIO_EXTRA_MODULES="${APPDIR}/usr/conda/lib/gio/modules"                   # Pitfall 4
export SSL_CERT_FILE="${APPDIR}/usr/conda/ssl/cacert.pem"                        # Pitfall 17 (spike-discovered)
export GI_TYPELIB_PATH="${APPDIR}/usr/conda/lib/girepository-1.0"
export PYTHONHOME="${APPDIR}/usr/conda"
export PATH="${APPDIR}/usr/conda/bin:${PATH}"
```

**Phase 85 edit 1 (Pitfall 19; CONTEXT.md code_insights line 91)** — add BEFORE the final exec:
```bash
# Pitfall 19 mitigation: deterministic PipeWire app identity so Wireplumber
# stream-restore state doesn't bounce per --appimage-extract-and-run random tmpdir.
export PULSE_PROP="application.name=MusicStreamer application.id=org.musicstreamer.app"
```

**Phase 85 edit 2 (Pitfall 20; spike findings hand-off item 5)** — replace spike's final line:
```bash
# WAS (spike):  exec "${APPDIR}/usr/conda/bin/python" "${APPDIR}/hello_world.py" "$@"
exec "${APPDIR}/usr/conda/bin/python" -m musicstreamer "$@"
```

---

### `tools/linux-build/Dockerfile` (container spec, config)

**Analog:** `.planning/spikes/85a-linux-packaging-spike/Dockerfile` (65 lines)

**Verbatim per spike hand-off item 2** — `FROM ubuntu:22.04` + 9-package apt install locks the GLIBC ≤ 2.35 baseline. Notable comments cross-reference Pitfall 1 (GLIBC ceiling) and document why each apt package is load-bearing:
```dockerfile
FROM ubuntu:22.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates curl wget bzip2 file \
      libfuse2 desktop-file-utils patchelf binutils && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
WORKDIR /work
```

---

### `tools/linux-build/{pins.env,verify-pins.sh}` (pin manifest + drift-guard, config)

**Analog:** `.planning/spikes/85a-linux-packaging-spike/{pins.env,verify-pins.sh}` (47 + 32 lines)

**pins.env — KEY=VALUE shape (no quotes, no spaces)** matters because `build.sh` uses `set -a; source pins.env; set +a` to auto-export:
```
LINUXDEPLOY_URL=https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
LINUXDEPLOY_SHA256=f2aa8e8bb6265d0edc0b0c666c494dc8975650af589408748d75c9b99434b570
...
MINIFORGE_TAG=26.3.2-2
MINIFORGE_URL=https://github.com/conda-forge/miniforge/releases/download/26.3.2-2/Miniforge3-26.3.2-2-Linux-x86_64.sh
MINIFORGE_SHA256=42260ffe3830fb953d5eee1bbb32229ff06aa7c3833c1ed7a9a0420a95685d94
LINUXDEPLOY_PLUGIN_CONDA_PATCHED_SHA256=49bf6cddfc2b9c2f70bd80b22ba030621c19532f2bd7df26a40bf624afdbdc26
```

**verify-pins.sh — exit-2-on-drift function** (lines 11-24):
```bash
check_pin() {
  local name="$1" url="$2" expected="$3"
  local tmp; tmp="$(mktemp "${TMPDIR:-/tmp}/${name}.XXXXXX")"
  trap 'rm -f "$tmp"' RETURN
  curl -fsSL --retry 3 --retry-delay 2 -o "$tmp" "$url"
  local actual; actual="$(sha256sum "$tmp" | awk '{print $1}')"
  if [[ "$actual" != "$expected" ]]; then
    printf 'PIN_DRIFT %s\n  expected=%s\n  actual=%s\n' "$name" "$expected" "$actual" >&2
    return 2
  fi
  printf 'PIN_OK %s\n' "$name"
}
```

---

### `tools/linux-build/smoke_test.py` (smoke driver, request-response)

**Analog:** `.planning/spikes/85a-linux-packaging-spike/smoke_test.py` (454 lines)

**Stable stdout marker contract** (lines 23-32) — preserve verbatim; downstream grep gates depend on `SPIKE_OK` / `SPIKE_FAIL` / `SPIKE_DIAG` / `plugin_resolved=`:
```python
# Stable stdout markers (grep contract — DO NOT change):
#   SPIKE_OK     — final success line
#   SPIKE_FAIL   — final failure line (with step=... reason=...)
#   SPIKE_DIAG   — intermediate diagnostic line
#   plugin_resolved=<name>  — REQUIRED literal substring under SPIKE_DIAG
```

**Argparse modes** (lines 402-423) — inherit `--uri / --timeout / --assert-tls / --check-glibc / --check-plugins`; Phase 85 may add `--check-mp3 / --check-aac / --check-aacp / --check-pls` per D-04 codec sweep.

**TAG-event + sink-election pattern** (Pitfalls 9 + 10; lines 274-326) — copy verbatim:
```python
def _log_sink_election():
    elected = None
    sink_prop = pipeline.get_property("audio-sink")
    if sink_prop is not None:
        elected = sink_prop.get_factory().get_name() ...
    _emit("SPIKE_DIAG", sink_elected=str(elected) if elected else "unknown")
```

**D-05 production-import change** (CONTEXT.md decisions §Smoke-test codec/URL surface) — the spike smoke is self-contained; Phase 85 replaces playback bootstrap with the production resolver:
```python
# Spike (verbatim from smoke_test.py): pipeline built via Gst.parse_launch(playbin3 uri=...)
# Phase 85 D-05 change:
from musicstreamer import url_helpers  # production resolver (read-only per CONTEXT.md deferred)
resolved = url_helpers.resolve(input_url)  # exercises real import path + dependency graph
pipeline = Gst.parse_launch(f'playbin3 uri="{resolved}"')
```

**SomaFM URL gate** (lines 66-82) — keep verbatim (T-85A-04-IV mitigation).

---

### `.github/workflows/linux-appimage.yml` (CI workflow, event-driven)

**Analog:** none (no `.github/` directory in repo). Shape is synthesized from CONTEXT.md D-13/D-14/D-15/D-16 + spike `build.sh` flag inventory.

**Skeleton derived from CONTEXT.md §Specifics line 119:**
```yaml
name: Linux AppImage Build
on:
  workflow_dispatch:
jobs:
  build:
    runs-on: ubuntu-22.04                       # D-13 GLIBC baseline
    steps:
      - uses: actions/checkout@v4
      - name: Import GPG signing key            # D-16
        env:
          LINUX_SIGNING_KEY: ${{ secrets.LINUX_SIGNING_KEY }}
          GPG_KEY_ID: ${{ secrets.LINUX_SIGNING_KEY_ID }}
        run: |
          [[ -n "$LINUX_SIGNING_KEY" && -n "$GPG_KEY_ID" ]] \
            || { echo "WORKFLOW_FAIL: signing secrets missing"; exit 1; }
          export GNUPGHOME=$(mktemp -d)
          echo "GNUPGHOME=$GNUPGHOME" >> $GITHUB_ENV
          echo "GPG_KEY_ID=$GPG_KEY_ID" >> $GITHUB_ENV
          echo "$LINUX_SIGNING_KEY" | gpg --batch --import
      - name: Build AppImage
        run: bash tools/linux-build/build.sh    # inherits all spike build.sh flags incl. --appimage-extract-and-run (D-14)
      - name: Smoke (single-distro parity)      # D-15: AppImage --appimage-extract-and-run smoke_test.py exits 0
        run: |
          ./tools/linux-build/artifacts/MusicStreamer-*-x86_64.AppImage \
            --appimage-extract-and-run python -m smoke_test
      - uses: actions/upload-artifact@v4
        with:
          name: MusicStreamer-AppImage
          path: tools/linux-build/artifacts/MusicStreamer-*.AppImage*
```

**D-14 reminder:** the produced AppImage inherits the FUSE constraint when consumed in containers; README must document `--appimage-extract-and-run` for downstream CI users (spike findings Pitfall 11 / line 448).

---

### `tools/check_linux_bundle.py` (optional drift-guard, batch/static)

**Analog 1 (CLI shape):** `tools/check_bundle_plugins.py` (105 lines)

**Required-plugin dict pattern** (lines 38-41) — copy shape; Phase 85 Linux equivalent uses `.so` filenames:
```python
REQUIRED_PLUGIN_DLLS: dict[str, tuple[str, str]] = {
    "gstlibav.dll":         ("avdec_aac", "gst-libav"),
    "gstaudioparsers.dll":  ("aacparse",  "gst-plugins-good"),
}
```
Linux mirror would key on `.so` names under `usr/conda/lib/gstreamer-1.0/` (spike captured 188-plugin BOM per findings line 242 / hand-off item 10):
```python
REQUIRED_PLUGIN_SOS: dict[str, tuple[str, str]] = {
    "libgstlibav.so":         ("avdec_aac", "gst-libav"),
    "libgstaudioparsers.so":  ("aacparse",  "gst-plugins-good"),
}
```

**Exit-code pattern** (lines 67-94) — `exit 10` on missing; preserve so test_packaging_spec.py can mirror.

**Analog 2 (pytest drift-guard shape):** `tests/test_packaging_spec.py` (551 lines)

**`Path(__file__).resolve().parent.parent / ...` fixture pattern** (lines 31-50):
```python
_BUILD_SH = (
    Path(__file__).resolve().parent.parent / "tools" / "linux-build" / "build.sh"
)

@pytest.fixture(scope="module")
def build_sh_source() -> str:
    assert _BUILD_SH.is_file(), f"expected build.sh at {_BUILD_SH}"
    return _BUILD_SH.read_text(encoding="utf-8")
```

**Literal-in-source assertion pattern** (lines 71-105; e.g., `test_spec_imports_copy_metadata`) — Phase 85 mirror for GLIBC_2.35 literal per spike hand-off item 8:
```python
def test_build_sh_pins_glibc_ceiling_at_2_35(build_sh_source: str) -> None:
    """PKG-LIN-APP-08: build.sh must pin the GLIBC ceiling at GLIBC_2.35."""
    assert "GLIBC_2.3[0-5]" in build_sh_source, (
        "build.sh's case statement must accept GLIBC_2.30..2.35 as the ≤2.35 set"
    )
    assert "GLIBC_FAIL" in build_sh_source, "build.sh must emit GLIBC_FAIL on drift"
```

**Comment-line stripping for negative drift-guards** (lines 286-289) — useful if Phase 85 wants to assert old patterns are gone from executable lines:
```python
executable_lines = "\n".join(
    line for line in build_sh_source.splitlines()
    if not line.lstrip().startswith("#")
)
```

---

### `tools/linux-build/README.md` (docs)

**Analog:** `packaging/windows/README.md` (80+ lines; same role on Windows side)

**Front-matter shape** (lines 1-12):
```markdown
# MusicStreamer — Linux Packaging

This directory contains the Linux AppImage build pipeline: a pinned
Dockerfile (Ubuntu 22.04 LTS for GLIBC ≤ 2.35), a conda-forge environment
manifest, an AppRun launcher, and a Bash driver (`build.sh`) that ties them
together. Running `bash build.sh` on a configured Linux host produces a
single GPG-signed `MusicStreamer-<version>-x86_64.AppImage` under
`artifacts/`.

The pipeline is the production implementation of the patterns proven in
Phase 85a's AppImage spike. See
`.planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md` for the
canonical findings (20 pitfalls with documented mitigations).
```

**Prerequisites section pattern** (lines 14-52) — numbered list of host requirements; D-17 folds in `docker info` daemon probe note:
```markdown
1. **Docker engine OR rootless podman + distrobox** — the build runs in a
   pinned `ubuntu:22.04` container. `docker info` (NOT just `docker --version`)
   must report a reachable daemon; distrobox autodetects backend per
   invocation (see `reference_distrobox_backend_autodetect.md`).
2. **yq** — `build.sh` parses `environment.yml` to synthesize CONDA_PACKAGES.
3. **GPG with key for signing** — `GPG_KEY_ID` env var must reference an
   importable secret key; set `SKIP_SIGN=1` to skip signing during local
   iteration (CI never sets SKIP_SIGN).
```

**Build command table pattern** (lines 53-73; copy shape):
```markdown
| Step                        | Output                                                   |
| --------------------------- | -------------------------------------------------------- |
| Pin verification            | `verify-pins.sh` exits 2 on drift                       |
| Docker build (ubuntu:22.04) | `ms-linux-build:22.04` image                            |
| linuxdeploy + plugin-conda  | `AppDir/` populated                                     |
| linuxdeploy --output appimage + --updateinformation | `MusicStreamer-<version>-x86_64.AppImage` |
| `gpg2 --detach-sign`        | `MusicStreamer-<version>-x86_64.AppImage.sig`           |
| objdump DT_VERNEED scan     | `GLIBC_OK GLIBC_<≤2.35>` (exit 4 on drift)              |
```

## Shared Patterns

### Build-script exit-code discipline
**Source:** spike `build.sh` lines 1-9 + `packaging/windows/build.ps1` lines 2-9
**Apply to:** `tools/linux-build/build.sh`
**Pattern:** numeric exit codes documented in header comment, branching `BUILD_FAIL reason=<token>` grep contract on stderr so CI / wrapper scripts can branch on `$?`. Phase 85 extends spike codes 0-4 with 5 (`GPG_KEY_ID` unset) and 6 (signing failed).

### `set -euo pipefail` + `HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"` preamble
**Source:** spike `build.sh` lines 72-76 / `verify-pins.sh` lines 5-7 / `run-smoke.sh` lines 4-7 (uniform across all 3 spike shell scripts)
**Apply to:** every new Phase 85 shell script (`build.sh`, optional CI shim, any wrapper).

### `set -a; source pins.env; set +a` auto-export
**Source:** spike `build.sh` lines 83-87
**Apply to:** `tools/linux-build/build.sh`
**Why load-bearing:** pins.env uses bare `KEY=VALUE` (no `export`); without `set -a`, downstream `docker run -e LINUXDEPLOY_URL` (value-less forwarding form) fails with `unbound variable` under `set -u` inside the container.

### Drift-guard via static source-grep, not runtime introspection
**Source:** `tests/test_packaging_spec.py` (entire file) + `tools/check_bundle_plugins.py`
**Apply to:** optional `tests/test_packaging_linux_spec.py` and/or `tools/check_linux_bundle.py`
**Pattern:** read the file as text in a pytest fixture (`Path(__file__).resolve().parent.parent / ...`), assert substring literals are present, document the rationale tag in the assertion message so a grep-from-source-code maintainer can trace why the test exists. Cross-references CONTEXT.md code_context "Drift-guards programmatic, not text-anchored" — both forms are programmatic; text-anchored means hand-counted line numbers (avoid), substring-on-read is acceptable.

### Pitfall cross-reference comments in source
**Source:** spike `build.sh` lines 10-71 (pitfall header block) + spike `AppRun` lines 1-42 (CRITICAL: ... comments inline)
**Apply to:** `tools/linux-build/build.sh`, `tools/linux-build/AppRun`
**Pattern:** every load-bearing line carries a comment naming the pitfall number from `85A-SPIKE-FINDINGS.md`. This is the canonical project pattern for "why is this line here" — a future maintainer can `grep -n 'Pitfall' build.sh` and walk all the mitigations.

### Single-source-of-truth + build-time parsing (CONTEXT.md "Established Patterns")
**Source:** project convention; D-01 explicitly cites
**Apply to:** `tools/linux-build/build.sh` parsing `tools/linux-build/environment.yml` (NOT maintaining a duplicate CONDA_PACKAGES list).
**Anti-pattern to avoid:** spike `build.sh` lines 105-106 hardcoded the list as a workaround per Pitfall 8 finding that plugin-conda doesn't honor environment.yml; Phase 85 closes the workaround by parsing the YAML at build start (D-01 Approach B).

### FUSE-escape flag mandatory in containers (Pitfall 11)
**Source:** spike `build.sh` line 206 + findings line 448
**Apply to:** `tools/linux-build/build.sh` linuxdeploy invocation AND `.github/workflows/linux-appimage.yml` smoke step AND README documentation.
**Pattern:** every container-context invocation of an AppImage MUST use `--appimage-extract-and-run`; this includes both the build-time `linuxdeploy.AppImage` call and the produced AppImage when consumed downstream in CI containers.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.github/workflows/linux-appimage.yml` | CI workflow YAML | event-driven (`workflow_dispatch`) | No `.github/` directory exists in repo; this is the first GitHub Actions workflow. Shape synthesized from CONTEXT.md D-13/D-14/D-15/D-16 + spike build.sh flag inventory + spike findings hand-off item 13. Planner should keep skeleton ≤40 lines per CONTEXT.md §Specifics. |

## Metadata

**Analog search scope:**
- `.planning/spikes/85a-linux-packaging-spike/` (build.sh, AppRun, Dockerfile, environment-spike.yml, pins.env, verify-pins.sh, smoke_test.py — all primary analogs)
- `tools/linux-spike/` (distrobox harness — create/run/teardown)
- `tools/` (Windows drift-guard analogs: check_bundle_plugins.py, check_spec_entry.py, check_subprocess_guard.py)
- `tests/test_packaging_spec.py` (pytest static-assertion drift-guard analog)
- `packaging/windows/` (cross-platform docs analog: README.md + build.ps1 exit-code shape)
- `.github/` (does not exist — workflow file is greenfield)

**Files scanned:** 14
**Pattern extraction date:** 2026-05-27
