---
phase: 85A-linux-packaging-spike
plan: 05
subsystem: linux-packaging-spike
tags:
  - spike
  - linux-packaging
  - build-driver
  - appimage-assembly
requires:
  - 85A-02 (pinned toolchain via pins.env + verify-pins.sh)
  - 85A-03 (Dockerfile ubuntu:22.04 base)
  - 85A-04 (AppRun + hello_world.py + smoke_test.py + environment-spike.yml)
provides:
  - End-to-end build driver (build.sh) that produces a functional AppImage
  - Validated AppImage at .planning/spikes/85a-linux-packaging-spike/artifacts/MusicStreamer-spike-x86_64.AppImage
  - 8 production-relevant pitfalls (Pitfalls 8, 11, 12, 13, 13b, 14, 15, 16) with documented mitigations for Phase 85
  - Functional input for Plan 06 distrobox smoke test
affects:
  - Phase 85 production packaging pipeline (build.sh + Dockerfile + pins.env are copy-forward ready)
tech-stack:
  added:
    - linuxdeploy + linuxdeploy-plugin-conda (Miniforge3-patched) + linuxdeploy-plugin-gstreamer
    - conda-forge environment with python 3.12, PySide6 6.11, gstreamer 1.28 stack
  patterns:
    - "Phase 43 build.ps1 -> Linux build.sh translation (same exit-code shape: 0/1/2/3/4)"
    - "Approach P: sed-patch hardcoded Miniconda3 URL in plugin-conda to Miniforge3 (avoids Anaconda ToS gate)"
    - "objdump -T DT_VERNEED scan for GLIBC verification (replaces unsafe strings-grep)"
key-files:
  created:
    - .planning/spikes/85a-linux-packaging-spike/build.sh
    - .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.desktop
    - .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.svg
  modified:
    - .planning/spikes/85a-linux-packaging-spike/pins.env (added MINIFORGE_TAG/URL/SHA + LINUXDEPLOY_PLUGIN_CONDA_PATCHED_SHA256)
    - .planning/spikes/85a-linux-packaging-spike/verify-pins.sh (extended to verify miniforge pin)
    - .planning/spikes/85a-linux-packaging-spike/Dockerfile (added patchelf + binutils)
decisions:
  - "GLIBC verification via objdump -T DT_VERNEED scan, not strings-grep (Pitfall 16)"
  - "Approach P (sed-patched plugin-conda) over Approach M (custom-vendored fork) for Miniforge3 substitution"
  - "CONDA_SKIP_CLEANUP=strip retained (larger AppImage acceptable; ubuntu:22.04 binutils 2.38 strip segfaults on newer conda .so files)"
  - "Per-build runs the AppImage extracted into a temp dir to enumerate ELFs; cleanup via trap + explicit rm"
metrics:
  duration: ~7 minutes (round 9 with full conda re-download)
  completed: 2026-05-26
  appimage_size_mb: 503
  glibc_max: GLIBC_2.34
  gst_plugins_bundled: 188
  python_version: 3.12.13
  pyside6_version: 6.11.1
  gstreamer_version: 1.28.3
  miniforge_tag: 26.3.2-2
  rounds_to_success: 9
---

# Phase 85A Plan 05: Build Driver Summary

End-to-end shell driver (`build.sh`) that orchestrates Docker-based AppImage assembly with full conda-forge GStreamer + PySide6 bundling, producing a 503 MB GLIBC_2.34 AppImage validated by objdump-based DT_VERNEED scan.

## Goal

Author the build driver that drives ubuntu:22.04 container -> conda env assembly -> linuxdeploy invocation -> AppImage production -> GLIBC verification, mitigating Pitfalls 1 + 2 from RESEARCH.md while remaining a faithful Linux analog of Phase 43's `build.ps1`.

## What was built

**AppImage:** `.planning/spikes/85a-linux-packaging-spike/artifacts/MusicStreamer-spike-x86_64.AppImage`
- **Size:** 503 MB (527,538,680 bytes)
- **GLIBC max (objdump DT_VERNEED scan):** `GLIBC_2.34` (well within 2.35 ceiling)
- **Architecture:** x86_64
- **Compression:** zstd squashfs (28.88% of uncompressed 1.78 GB)

**Functional validations (round-9 confirmation):**
- AppImage self-extracts via `--appimage-extract` (FUSE escape for rootless container)
- AppRun executable, 280 bytes (linuxdeploy template + apprun-hooks)
- Conda env: Python 3.12.13, PySide6 6.11.1, GStreamer 1.28.3
- 188 gst plugin .so files bundled at `usr/conda/lib/gstreamer-1.0/`
- `gst-inspect-1.0 avdec_aac` resolves (success criterion #1 — AAC decode chain available)
- `gst-inspect-1.0 aacparse` resolves (parser present)
- `gst-inspect-1.0 playbin3` resolves (playbin3 high-level element present)
- `import PySide6` OK
- `import gi; gi.require_version("Gst","1.0"); from gi.repository import Gst; Gst.init(None)` OK after setting `GI_TYPELIB_PATH` (AppRun sets this at runtime)

**Build script structural invariants enforced:**
- `set -euo pipefail` head, exit codes match Phase 43 (0/1/2/3/4)
- `verify-pins.sh` runs FIRST (after Dockerfile build) — fail-fast on upstream asset drift
- `GSTREAMER_PLUGINS_DIR` + `GSTREAMER_HELPERS_DIR` exported BEFORE `linuxdeploy --plugin gstreamer` (Pitfall 2 mitigation; awk-gate verified)
- AppImage discovery uses `find -not -name 'linuxdeploy*' -newer /work/AppRun` (Issue #5 fix; broad `./*.AppImage` glob removed)
- GLIBC verification via objdump -T (Pitfall 16; strings-grep removed)

## Key files

### Created
- **`build.sh`** (231 lines): Phase 43 `build.ps1` Linux analog. Full pipeline: source pins -> verify pins -> docker build -> docker run with non-root user mapping -> AppDir skeleton -> Approach P plugin-conda patch -> conda env assembly -> linuxdeploy bundle -> objdump GLIBC scan.
- **`desktop/musicstreamer-spike.desktop`**: Minimal Desktop Entry (Type=Application, Exec=AppRun, Icon=musicstreamer-spike, Categories=Audio;AudioVideo;Player;).
- **`desktop/musicstreamer-spike.svg`**: 5-line placeholder SVG (gray square + "MS-85a" text).

### Modified (during the 9-round saga, all committed in earlier plans / waves)
- **`pins.env`**: Added MINIFORGE_TAG=26.3.2-2, MINIFORGE_URL, MINIFORGE_SHA256, LINUXDEPLOY_PLUGIN_CONDA_PATCHED_SHA256 (after Approach P sed transformation).
- **`verify-pins.sh`**: Extended to verify miniforge installer SHA + patched plugin-conda SHA.
- **`Dockerfile`**: Added `patchelf` + `binutils` apt-get install lines (linuxdeploy / plugin-conda runtime deps).

## The 9-round journey

| Round | Attempted fix | Outcome | Pitfall surfaced |
|-------|---------------|---------|------------------|
| 1 | Initial plan-spec build.sh | linuxdeploy.AppImage FUSE-mount failed in container | **Pitfall 11**: rootless container + AppImage = FUSE setuid escape needed |
| 2 | Add `--appimage-extract-and-run` flag | conda plugin failed: `CONDA_PACKAGES` empty + plugin doesn't consume `environment.yml` | **Pitfall 8**: plugin-conda doesn't honor environment.yml (counter to plan-spec note) |
| 3 | Enumerate `CONDA_PACKAGES` from environment-spike.yml; add `--user $(id -u):$(id -g)` for ownership | Build progressed; conda downloads tripped intermittent SSL record-layer errors mid-fetch | **Pitfall 12**: Docker bridge MTU + parallel conda fetch over HTTPS = SSL errors |
| 4 | `--network=host` + `CONDA_FETCH_THREADS=1` | Plugin-conda hit `defaults` channel ToS gate from Miniconda3 base condarc | **Pitfall 13**: Miniconda3-latest base condarc declares Anaconda `defaults` channels |
| 5 | Try `CONDA_DOWNLOAD_DIR` hook to pre-stage Miniforge installer | Plugin's `touch -d '@0'` + `wget -N` forces re-download regardless of cache | **Pitfall 13b**: plugin-conda hook cannot be bypassed via cached file |
| 6 | **Approach P**: sed-patch hardcoded Miniconda3 URL to Miniforge3 + re-verify SHA | Linuxdeploy couldn't resolve `libgstbase-1.0.so.0` from conda layout | **Pitfall 14**: linuxdeploy ld-search ignores `$APPDIR/usr/conda/lib/` |
| 7 | Export `LD_LIBRARY_PATH=$APPDIR/usr/conda/lib:...` before linuxdeploy invocation | Plugin-conda cleanup-strip pass segfaulted on newer conda .so files | **Pitfall 15**: ubuntu:22.04 binutils 2.38 `strip` segfaults on conda-forge 2026.x .so |
| 8 | `CONDA_SKIP_CLEANUP=strip` (plugin-conda opt-out) | **AppImage produced (503 MB).** Functional validations passed. But host-side `strings | grep GLIBC_` returned false-positive `GLIBC_2.147` from random ASCII coincidence in compressed squashfs payload -> `exit 4`. | **Pitfall 16**: strings-grep on compressed AppImage payload yields false positives |
| 9 | **Pitfall 16 fix**: objdump-based DT_VERNEED scan (extract AppImage -> walk ELFs -> objdump -T -> aggregate GLIBC_* tokens -> sort -V -u -> max) | **SUCCESS.** `GLIBC_OBJDUMP GLIBC_2.34 (real DT_VERNEED scan)` + `GLIBC_OK GLIBC_2.34 <= 2.35` + `BUILD_OK`. Same functional AppImage as round 8. | (none — round 9 is the success state) |

## Pitfalls discovered (production-relevant for Phase 85)

In addition to the structurally-mitigated **Pitfall 1** (GLIBC <= 2.35 baseline) and **Pitfall 2** (GSTREAMER_PLUGINS_DIR redirect before plugin invocation) from RESEARCH.md, the spike surfaced **8 NEW pitfalls** that production builds must handle:

### Pitfall 8: plugin-conda does NOT consume environment.yml (spike-discovered)

**Surface:** Plan-spec instructed `cp environment-spike.yml /work/environment.yml` expecting plugin-conda to read it. Plugin-conda's source (line 74 of pinned commit) warns when CONDA_PACKAGES is empty; line 157 reads CONDA_PACKAGES with `;` as IFS. environment.yml is ignored entirely.

**Mitigation applied:** Enumerate `CONDA_PACKAGES="python=3.12;pyside6;pygobject;gst-python;gstreamer;gst-plugins-base;gst-plugins-good;gst-plugins-bad;gst-plugins-ugly;gst-libav;glib-networking"` matching environment-spike.yml exactly.

**Kyle's observation:** Production should "future-proof via variable substitution" — generate CONDA_PACKAGES from a single source-of-truth file (e.g., parse environment-spike.yml with yq/python at build-script start) rather than maintaining two parallel lists.

**Phase 85 recommendation:** Either (a) parse environment.yml at build.sh start and synthesize CONDA_PACKAGES, OR (b) skip plugin-conda entirely and run `conda env create -f environment.yml -p $APPDIR/usr/conda` directly (then layer linuxdeploy + plugin-gstreamer on top). Option (b) makes the yml the functional input and aligns with how Phase 43 uses environment specs.

### Pitfall 11: linuxdeploy.AppImage FUSE-mount fails in rootless container

**Surface:** `docker run --user $(id -u):$(id -g)` cannot use setuid FUSE; AppImage runtime aborts with "fuse: device not found" or "fusermount: failed to setup".

**Mitigation:** Pass `--appimage-extract-and-run` flag — the documented escape hatch. Unpacks to a tempdir and execs the inner binary directly.

**Phase 85 recommendation:** CI containers should always use `--appimage-extract-and-run`. The PRODUCED AppImage inherits the same FUSE constraint when consumed in CI — downstream users in CI/containers must also use this flag.

### Pitfall 12: Docker bridge network + parallel conda fetch = intermittent SSL errors

**Surface:** Mid-fetch `CondaSSLError: Error encountered during SSL/TLS record-layer write` on multi-MB conda-forge tarballs (qt6-main, libllvm22, etc.).

**Mitigation (both applied):**
- `--network=host`: bypass Docker bridge MTU/proxy
- `CONDA_FETCH_THREADS=1`: serialize downloads (env var overrides condarc)

**Phase 85 recommendation:** Both. Alternative: build natively on host (loses ubuntu:22.04 GLIBC <= 2.35 baseline if host is newer).

### Pitfalls 13 / 13b: Miniconda3 base condarc trips ToS gate, plugin-conda re-downloads despite cache

**Surface (13):** Miniconda3 24.x's base condarc declares Anaconda `defaults` channels (pkgs/main + pkgs/r). conda 24.x's ToS gate trips on channel **presence**, not channel usage — so even with `CONDA_CHANNELS=conda-forge`, install aborts asking for ToS acceptance.

**Surface (13b):** plugin-conda's documented `CONDA_DOWNLOAD_DIR` hook is useless: line 125 of pinned plugin runs `touch -d '@0'` + `wget -N`, forcing re-download regardless of cached mtime.

**Mitigation (Approach P):** Post-download SHA-verify upstream plugin-conda, apply deterministic sed transformation swapping Miniconda3 URL/filename for Miniforge3 (conda-forge only, no ToS), re-verify against `LINUXDEPLOY_PLUGIN_CONDA_PATCHED_SHA256` for audit. Narrow target — only the x86_64 path is swapped; dead x86/aarch64 branches left untouched.

**Phase 85 recommendation:** Either (a) re-derive patched SHA from the documented sed transformation as the spike does, OR (b) vendor a patched plugin-conda copy in-repo with its own pinned SHA. (b) is more auditable but adds maintenance burden when upstream plugin-conda updates.

### Pitfall 14: linuxdeploy ld-search ignores AppDir conda layout

**Surface:** linuxdeploy walks every .so file in the AppDir at invocation time and resolves DT_NEEDED entries via standard library search (`/etc/ld.so.cache`, `/usr/lib`, `/usr/lib/x86_64-linux-gnu`, `LD_LIBRARY_PATH`, `AppDir/usr/lib`). The conda layout puts all GStreamer libs at `$APPDIR/usr/conda/lib/` — NOT in any default search path. linuxdeploy fails with `Could not find dependency: libgstbase-1.0.so.0` even though the lib is sitting in the AppDir.

**Mitigation:** `export LD_LIBRARY_PATH="$APPDIR/usr/conda/lib:$APPDIR/usr/conda/lib/gstreamer-1.0:${LD_LIBRARY_PATH:-}"` BEFORE invoking linuxdeploy. (AppRun handles the same at runtime via its own env exports.)

**Phase 85 recommendation:** Standard practice for any AppDir layout where libs live outside `usr/lib`. Document as a "build vs runtime: both need the hint" pattern.

### Pitfall 15: ubuntu:22.04 binutils 2.38 strip segfaults on conda-forge .so

**Surface:** During plugin-conda cleanup-strip pass on newer conda-forge .so files (OpenVINO ~2026.0.0, absl ~2601.0.0, etc.), `strip` segfaults.

**Mitigation:** `CONDA_SKIP_CLEANUP=strip` (documented plugin-conda opt-out). Trade-off: larger AppImage (~503 MB vs estimated ~400 MB stripped). Conda-forge tarballs ship pre-stripped already, so cost is mostly cosmetic.

**Phase 85 recommendation:** Either (a) accept SKIP_CLEANUP (spike picks this — keeps GLIBC baseline at 2.35), OR (b) upgrade base to ubuntu:24.04 with binutils 2.42 (but pushes GLIBC baseline to 2.39 — Pitfall 1 regression, fewer distros supported). Spike's call: ship larger but more-portable AppImage.

### Pitfall 16: strings | grep ^GLIBC_ produces false positives on compressed AppImage payload

**Surface:** Round 8 produced a functional AppImage with real ELF symbols topping at `GLIBC_2.17`, but post-build verification `strings | grep ^GLIBC_ | sort -V | tail -1` returned `GLIBC_2.147` — a false positive from random ASCII coincidence in the zstd-compressed squashfs payload. `exit 4` triggered despite no actual GLIBC drift.

**Mitigation (Pitfall 16 fix, round 9):** Replace strings-grep with objdump-based ELF walk:
1. Extract AppImage to temp dir (`--appimage-extract`)
2. `find -L squashfs-root -type f \( -name '*.so' -o -name '*.so.*' -o -perm /u+x \)`
3. For each match: `objdump -T <file> 2>/dev/null` (silently skips non-ELFs)
4. `grep -oE 'GLIBC_[0-9]+\.[0-9]+' | sort -V -u | tail -1`
5. Compare against 2.35 via case statement

Cost: ~10-30s on top of build time. Eliminates the false-positive class entirely.

**Phase 85 recommendation:** Adopt objdump-based scan as production standard. Strings-on-compressed-archive is fundamentally unsafe — any byte sequence resembling `GLIBC_<digits>.<digits>` in compressed data trips the grep. Real GLIBC requirements live in `DT_VERNEED` sections only; objdump enumerates those explicitly.

## Final build.sh shape (8 in-script mitigations)

1. **Fix A — Enumerated CONDA_PACKAGES** (Pitfall 8): `python=3.12;pyside6;pygobject;gst-python;...` explicit list
2. **Option B — non-root user mapping**: `--user $(id -u):$(id -g) -e HOME=/tmp/_home -e XDG_CACHE_HOME=/tmp/_cache` — produces host-owned artifacts (no root residue)
3. **--appimage-extract-and-run** (Pitfall 11): FUSE escape for rootless container
4. **--network=host + CONDA_FETCH_THREADS=1** (Pitfall 12): SSL-error mitigation for conda downloads
5. **Approach P sed-patch plugin-conda -> Miniforge3** (Pitfalls 13/13b): pre-invocation deterministic transformation + SHA re-verification
6. **CONDA_SKIP_CLEANUP=strip** (Pitfall 15): binutils 2.38 segfault opt-out
7. **LD_LIBRARY_PATH export before linuxdeploy** (Pitfall 14): AppDir/usr/conda/lib in build-time ld search
8. **objdump DT_VERNEED GLIBC scan** (Pitfall 16): replaces strings-grep

Plus the Pitfalls 1 & 2 mitigations from RESEARCH.md that were the plan's original load-bearing structure:
- **Pitfall 1**: case-statement gate on GLIBC_2.[0-9] / GLIBC_2.1? / GLIBC_2.2? / GLIBC_2.3[0-5] -> `exit 4` on overflow
- **Pitfall 2**: `GSTREAMER_PLUGINS_DIR` + `GSTREAMER_HELPERS_DIR` exported BEFORE `linuxdeploy --plugin gstreamer` (awk-gate verified)

## Validated success criteria

- [x] **AppImage artifact present**: `artifacts/MusicStreamer-spike-x86_64.AppImage` (503 MB, x86_64, executable)
- [x] **Success criterion #2 (GLIBC <= 2.35)**: `GLIBC_OBJDUMP GLIBC_2.34` confirmed via objdump DT_VERNEED scan
- [x] **`gst-inspect-1.0 avdec_aac` resolves** from extracted AppImage (success criterion #1)
- [x] **`gst-inspect-1.0 aacparse` resolves** (parser chain complete)
- [x] **AppRun template present** at `squashfs-root/AppRun` (executable, 280 bytes)
- [x] **Plugin .so count > 20**: 188 gst plugins bundled (9.4x the minimum)
- [x] **AppImage self-mounts** via `--appimage-extract` (verified post-build)
- [x] **Pitfall 1 + Pitfall 2 mitigations enforced in script structure**: case-statement + awk-gate both verified

## Phase 85 recommendations

When promoting this spike to production packaging:

1. **Copy build.sh + Dockerfile + pins.env + verify-pins.sh verbatim** — all 8 in-script mitigations are production-relevant. Modify only:
   - Replace `cp /work/hello_world.py "$APPDIR/"` with `cp -r /work/src/musicstreamer "$APPDIR/"` (or equivalent vendored python package layout)
   - Replace AppRun's `Exec=` target with `python -m musicstreamer`
   - Update `.desktop` `Name=` and `Categories=` for production identity
   - Adjust `CONDA_PACKAGES` to add MusicStreamer-specific deps (mutagen, pillow, requests, etc.)

2. **Address Pitfall 8 properly** — choose either (a) parse environment.yml in build.sh to generate CONDA_PACKAGES (Kyle's "future-proof via variable substitution"), OR (b) bypass plugin-conda entirely with `conda env create -f environment.yml -p $APPDIR/usr/conda` followed by manual linuxdeploy invocation. Option (b) makes the yml the functional input — cleaner source-of-truth.

3. **Adopt Pitfall 16's objdump scan as production-grade GLIBC verification** — never trust strings-grep on compressed archives. The 10-30s cost is trivial vs the false-positive risk.

4. **Consider Approach P maintenance cost** — the sed-patched plugin-conda SHA breaks on every upstream plugin-conda release. Either vendor a forked copy in-repo OR codify the sed transformation in build.sh and re-derive the patched SHA on every plugin pin bump. Spike chose the latter; production might prefer the former for stability.

5. **Document the FUSE constraint downstream** — README + install docs must instruct CI users to invoke the AppImage with `--appimage-extract-and-run` in container/rootless environments.

6. **Note shebang absolute-path artifact** — `usr/conda/bin/python --appimage-version` shows the conda env's python expects `/work/AppDir/usr/conda/lib/python3.12` as `stdlib dir` (build-time path baked in). AppRun sidesteps this at runtime via `PYTHONHOME` export. Production should verify AppRun's PYTHONHOME path matches the runtime extraction layout.

## Deviations from Plan

### Rule 3 (auto-fix blocking issues) — applied across rounds 1-9

All 8 pitfalls listed above were blockers that were auto-fixed in-spike. Each fix was committed atomically with a descriptive `fix(85A-05): ... (Pitfall N)` message. None of the fixes required architectural changes (Rule 4 was not triggered — every pitfall had a localized mitigation that fit within the plan's `build.sh` + `pins.env` + `verify-pins.sh` surface).

### Rule 1 (auto-fix bugs) — round 9

The strings-grep false-positive was a genuine bug in the verification logic (not a flaky test). Real ELF symbols topped at GLIBC_2.17 (now GLIBC_2.34 after round-9 rebuild — same source tree, different conda-forge package versions resolved at fetch time). Fix replaces the unsafe scan with a correct one.

## Self-Check: PASSED

Verification:
- `[ -f .planning/spikes/85a-linux-packaging-spike/artifacts/MusicStreamer-spike-x86_64.AppImage ]` -> FOUND (503 MB)
- `[ -f .planning/spikes/85a-linux-packaging-spike/build.sh ]` -> FOUND
- `[ -f .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.desktop ]` -> FOUND
- `[ -f .planning/spikes/85a-linux-packaging-spike/desktop/musicstreamer-spike.svg ]` -> FOUND
- Round-9 build log shows `GLIBC_OBJDUMP GLIBC_2.34 (real DT_VERNEED scan)` and `GLIBC_OK GLIBC_2.34 <= 2.35`
- Build log shows `BUILD_OK appimage=... glibc=GLIBC_2.34`
- Pitfall 16 commit `1fcaad5` present in git log on `worktree-agent-a6237ba11fb6ff671`
- All 6 prior-round commits cherry-picked successfully (2e85e40, 1c1ce1e, e4e1aa9, b569577, 4965c60, ed9dea6)
- No root-owned residue in `.planning/spikes/85a-linux-packaging-spike/`
- gst plugins: 188 (>>20 minimum)
- Functional validations: avdec_aac, aacparse, playbin3 all resolve; PySide6 6.11.1 imports; gi+Gst init reaches GStreamer 1.28.3
