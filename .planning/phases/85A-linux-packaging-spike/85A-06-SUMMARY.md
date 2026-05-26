---
phase: 85A-linux-packaging-spike
plan: 06
subsystem: linux-packaging-spike
tags: [spike, linux-packaging, distrobox, programmatic-smoke]
requires:
  - 85A-01-SUMMARY.md (host distrobox install)
  - 85A-04-SUMMARY.md (smoke_test.py harness + plugin_resolved= marker)
  - 85A-05-SUMMARY.md (AppImage produced by build.sh)
provides:
  - tools/linux-spike/create-distroboxes.sh (idempotent 3-distro creation)
  - tools/linux-spike/teardown-distroboxes.sh (ephemeral cleanup, D-04)
  - tools/linux-spike/run-smoke.sh (cross-distro smoke driver)
  - artifacts/{ubuntu22,fedora40,tumbleweed}-transcript.log (gitignored)
affects:
  - Plan 07 audible-PASS gate (programmatic baseline now green for HTTP)
  - Plan 08 SPIKE-FINDINGS.md will embed transcript excerpts verbatim
tech-stack:
  added: [distrobox 1.8.2.4, podman 5.7.0 (host)]
  patterns: [unshare-devsys, --additional-packages binutils, --pre-init-hooks zypp shim]
key-files:
  created:
    - tools/linux-spike/create-distroboxes.sh
    - tools/linux-spike/teardown-distroboxes.sh
    - tools/linux-spike/run-smoke.sh
    - .planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-transcript.log (gitignored)
    - .planning/spikes/85a-linux-packaging-spike/artifacts/fedora40-transcript.log (gitignored)
    - .planning/spikes/85a-linux-packaging-spike/artifacts/tumbleweed-transcript.log (gitignored)
  modified: []
decisions:
  - "Added --unshare-devsys to all distrobox create commands. Host has VirtualBox USB devices at /dev/vboxusb/* that rootless podman cannot remap into containers via user-NS; the default --volume /dev:/dev:rslave bind-mount fails OCI-side. Skipping /dev share does NOT break audio (PipeWire socket lives at $XDG_RUNTIME_DIR, separate bind)."
  - "Added --additional-packages \"binutils\" so smoke_test.py --check-glibc has `strings` available. Base images for all three distros omit binutils."
  - "Added --pre-init-hooks for Tumbleweed only: 2026-05 Tumbleweed image ships /usr/etc/zypp/zypp.conf (vendor path) but distrobox-init's setup_zypper sed's /etc/zypp/zypp.conf (admin path) and fails when missing. Hook copies vendor → admin pre-init."
  - "Inner-body script piped to bash via stdin (not bash -c \"...\") because the body contains literal double-quotes around $APPIMG/$SMOKE_PY that would terminate any outer double-quoted -c argument. The env APPIMG=\"$APPIMG\" passthrough (Issue #3 contract) is preserved at the distrobox enter boundary."
  - "smoke_test.py invoked via $APPDIR/usr/conda/bin/python after --appimage-extract + manual env-export, NOT via --appimage-extract-and-run. The spike's AppRun line 80 hard-codes `exec ... hello_world.py \"$@\"`, so anything after `python` would be forwarded to hello_world.py."
  - "Mode 1 (--check-glibc) scans the EXTRACTED bundled python binary, not the raw AppImage blob. strings on the squashfs-compressed AppImage matched symbol-version-shaped noise (e.g. fake \"GLIBC_2.7143\") that doesn't correspond to any real linker reference."
metrics:
  duration: "~27m wall (includes 3 distrobox cold-pull, 3 first-time inits, 4 smoke re-runs as deviations were resolved)"
  completed: 2026-05-26
---

# Phase 85A Plan 06: Programmatic cross-distro smoke

## Goal

Author the three distrobox-driver scripts (`create-distroboxes.sh`, `teardown-distroboxes.sh`, `run-smoke.sh`) and execute the programmatic per-distro smoke — GLIBC ceiling, plugin resolution (avdec_aac + aacparse), TLS backend, HTTP playback, HTTPS playback — across Ubuntu 22.04, Fedora 40, and openSUSE Tumbleweed. This is success criterion #1's empirical foundation; Plan 07 layers audible verification on top.

## What was built

Three executable shell scripts under `tools/linux-spike/`:

1. **`create-distroboxes.sh`** — Idempotent creation of three named distroboxes (`ms-spike-ubuntu22`, `ms-spike-fedora40`, `ms-spike-tumbleweed`). Loops over an associative array of name → image-ref. RESEARCH.md anti-pattern (line 266) honored: no `--init` flag. Runtime hardening (see Deviations) added `--unshare-devsys`, `--additional-packages "binutils"`, and a Tumbleweed-only `--pre-init-hooks` shim.

2. **`teardown-distroboxes.sh`** — Reversible-pair `distrobox rm --force` for all three. CONTEXT.md D-04 (containers are ephemeral) honored.

3. **`run-smoke.sh`** — Drives smoke_test.py inside each named distrobox via `distrobox enter ... --no-tty -- env APPIMG="$APPIMG" bash` with the inner-body script piped via stdin. Captures `script -q` transcripts at `.planning/spikes/85a-linux-packaging-spike/artifacts/{distro}-transcript.log` (gitignored runtime artifacts). Five modes per distro: GLIBC ceiling, plugin resolution (avdec_aac + aacparse), TLS backend assertion, HTTP playback (D-07), HTTPS playback (D-08).

Three per-distro transcripts produced (gitignored; lifetimes runtime-only):
- `.planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-transcript.log` (10,913 bytes)
- `.planning/spikes/85a-linux-packaging-spike/artifacts/fedora40-transcript.log` (11,258 bytes)
- `.planning/spikes/85a-linux-packaging-spike/artifacts/tumbleweed-transcript.log` (11,082 bytes)

## Distroboxes created

```
ID           | NAME                 | STATUS             | IMAGE
bff90262a4c8 | ms-spike-fedora40    | Up 11 minutes      | quay.io/fedora/fedora:40
b7ad4ff7fbe3 | ms-spike-ubuntu22    | Up  8 minutes      | docker.io/library/ubuntu:22.04
171e3628834d | ms-spike-tumbleweed  | Up 10 minutes      | registry.opensuse.org/opensuse/tumbleweed:latest
```

Container manager: rootless **podman 5.7.0** (distrobox 1.8.2.4 auto-selected podman over docker even though both are installed).

## Per-distro results table

| Distro            | OS-release first line                          | GLIBC max  | avdec_aac | aacparse | TLS backend                       | HTTP playback (D-07) | HTTPS playback (D-08) | Audio sink elected |
|-------------------|------------------------------------------------|------------|-----------|----------|-----------------------------------|----------------------|----------------------|--------------------|
| ms-spike-ubuntu22 | `Ubuntu 22.04.5 LTS` (jammy)                   | GLIBC_2.17 | ✅ ok      | ✅ ok     | GTlsBackendOpenssl + DB present   | ✅ SPIKE_OK 35.02s    | ❌ typefinder error   | autoaudiosink      |
| ms-spike-fedora40 | `Fedora Linux 40 (Container Image)`            | GLIBC_2.17 | ✅ ok      | ✅ ok     | GTlsBackendOpenssl + DB present   | ✅ SPIKE_OK 35.05s    | ❌ typefinder error   | autoaudiosink      |
| ms-spike-tumbleweed | `openSUSE Tumbleweed` (20260524)             | GLIBC_2.17 | ✅ ok      | ✅ ok     | GTlsBackendOpenssl + DB present   | ✅ SPIKE_OK 35.02s    | ❌ typefinder error   | autoaudiosink      |

GLIBC ceiling of 2.17 is far below the 2.35 cap (success criterion #2). All three distros register identical GLIBC + TLS module paths, since the bundled `usr/conda/bin/python` is the same blob — the per-distro variability lives at the **host kernel + container userspace** boundary (D-02 single-host caveat acknowledged).

## Cross-distro deviations

- **All three distros uniformly fail HTTPS playback** with the same souphttpsrc typefinder error. This is reproducible on the bare host (no distrobox) using the same extracted AppImage and env vars, so it is **not** a per-distro / cross-distro variability finding — it is a bundle-level defect surfaced uniformly. See `## Threat Flags` below.
- **No per-distro audio-sink differences observed**: all three elected `autoaudiosink` (Pitfall 10 logging). With `--unshare-devsys`, the container's `/dev` is its own ephemeral mount, so the host's PulseAudio/PipeWire devices are NOT visible through `/dev/snd/*`. Audio routing during HTTP playback succeeded via the autoaudiosink → fakesink fallback (no actual audio rendered in programmatic mode; Plan 07 audible-PASS will validate that PipeWire delivery still works under `--unshare-devsys` via $XDG_RUNTIME_DIR socket).
- **Tumbleweed first-init quirk**: `setup_zypper` in distrobox-init 1.8.2.4 assumes `/etc/zypp/zypp.conf` exists and `sed -i`'s it; the 2026-05 Tumbleweed image ships only `/usr/etc/zypp/zypp.conf` (vendor path). Added a Tumbleweed-only `--pre-init-hooks` to copy vendor → admin before init proceeds.

## Key files (created)

```
tools/linux-spike/create-distroboxes.sh           (1.6K, executable)
tools/linux-spike/teardown-distroboxes.sh         (445B, executable)
tools/linux-spike/run-smoke.sh                    (4.0K, executable)
.planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-transcript.log   (gitignored)
.planning/spikes/85a-linux-packaging-spike/artifacts/fedora40-transcript.log   (gitignored)
.planning/spikes/85a-linux-packaging-spike/artifacts/tumbleweed-transcript.log (gitignored)
```

## Transcript excerpts

### Ubuntu 22.04 (SPIKE_DIAG + SPIKE_OK + SPIKE_FAIL lines)

```
SPIKE_DIAG glibc_max='GLIBC_2.17' path='/tmp/ms-spike-qf4GFF/squashfs-root/usr/conda/bin/python'
SPIKE_DIAG plugin_resolved='avdec_aac' status='ok'
SPIKE_DIAG plugin_resolved='aacparse' status='ok'
SPIKE_DIAG tls_backend='GTlsBackendOpenssl' has_default_database=True gio_modules='/tmp/ms-spike-qf4GFF/squashfs-root/usr/conda/lib/gio/modules'
SPIKE_DIAG gst_version='GStreamer 1.28.3' plugin_count=189 url_scheme='http'
SPIKE_DIAG event='reached_playing'
SPIKE_DIAG sink_elected='autoaudiosink'
SPIKE_OK url='http://ice1.somafm.com/groovesalad-128-mp3' time_to_play_s=0.22 first_tag_s=0.22 played_for_s=35.02
SPIKE_DIAG gst_version='GStreamer 1.28.3' plugin_count=189 url_scheme='https'
SPIKE_FAIL step='pipeline' errors=[...typefinder error...] url='https://ice6.somafm.com/groovesalad-128-mp3'
```

### Fedora 40 (same shape; identical GLIBC + TLS + plugin resolution)

```
SPIKE_DIAG glibc_max='GLIBC_2.17' path='/tmp/ms-spike-ntWnJi/squashfs-root/usr/conda/bin/python'
SPIKE_DIAG plugin_resolved='avdec_aac' status='ok'
SPIKE_DIAG plugin_resolved='aacparse' status='ok'
SPIKE_DIAG tls_backend='GTlsBackendOpenssl' has_default_database=True ...
SPIKE_OK url='http://ice1.somafm.com/groovesalad-128-mp3' time_to_play_s=0.22 first_tag_s=0.22 played_for_s=35.02
```

### openSUSE Tumbleweed (same shape; identical GLIBC + TLS + plugin resolution)

```
SPIKE_DIAG glibc_max='GLIBC_2.17' path='/tmp/ms-spike-tBTcZb/squashfs-root/usr/conda/bin/python'
SPIKE_DIAG plugin_resolved='avdec_aac' status='ok'
SPIKE_DIAG plugin_resolved='aacparse' status='ok'
SPIKE_DIAG tls_backend='GTlsBackendOpenssl' has_default_database=True ...
SPIKE_OK url='http://ice1.somafm.com/groovesalad-128-mp3' time_to_play_s=0.23 first_tag_s=0.22 played_for_s=35.02
```

## Deviations from Plan

### Auto-fixed Issues (Rule 1 / Rule 3)

**1. [Rule 3 — Blocker] Distrobox `/dev` bind-mount fails on this host**

- **Found during:** Task 1 first invocation
- **Issue:** `runc create failed: ... error mounting "/dev/vboxusb/001/006" ... openat2 ... permission denied: OCI permission denied`. Distrobox's default `--volume /dev:/dev:rslave` recursive bind tries to remap the host's VirtualBox USB character devices into the container; rootless podman + user namespace cannot recreate them.
- **Fix:** Added `--unshare-devsys` to all three `distrobox create` invocations. Distrobox source (`/usr/bin/distrobox-create` line 753-757) shows this flag skips the `/dev` and `/sys` recursive bind mounts. Audio via PipeWire socket lives at `$XDG_RUNTIME_DIR/pipewire-0` (separate `/run/user/1000` bind), so Plan 07 audible-PASS is unaffected.
- **Files modified:** `tools/linux-spike/create-distroboxes.sh`
- **Commit:** `53255c7` (fix(85A-06): harden create-distroboxes.sh for host-specific runtime blockers)

**2. [Rule 3 — Blocker] Tumbleweed distrobox-init `setup_zypper` failure**

- **Found during:** Task 2 first invocation
- **Issue:** distrobox-init line 1627 runs `sed -i 's/.*solver.onlyRequires.*/.../g' /etc/zypp/zypp.conf`. The 2026-05 Tumbleweed base image ships `/usr/etc/zypp/zypp.conf` (vendor path) but NOT `/etc/zypp/zypp.conf` (admin path). sed fails → init aborts → `Error: An error occurred`.
- **Fix:** Tumbleweed-only `--pre-init-hooks "mkdir -p /etc/zypp && [ -f /etc/zypp/zypp.conf ] || cp -p /usr/etc/zypp/zypp.conf /etc/zypp/zypp.conf"`. Copies vendor → admin before distrobox-init proceeds.
- **Files modified:** `tools/linux-spike/create-distroboxes.sh`
- **Commit:** `53255c7`

**3. [Rule 3 — Blocker] `strings` missing in minimal distrobox images**

- **Found during:** Task 2 GLIBC mode execution
- **Issue:** `smoke_test.py --check-glibc` invokes `subprocess.run(["strings", path], ...)`. The minimal Ubuntu/Fedora/Tumbleweed base images omit binutils → `FileNotFoundError` → `SPIKE_FAIL reason='strings_missing'`. Host's `/run/host/usr/bin/strings` is available but depends on libbfd inside `/usr`, not `/run/host/usr`, so it cannot be used directly.
- **Fix:** Added `--additional-packages "binutils"` to all three creates. distrobox-init's `setup_apt` / `setup_dnf` / `setup_zypper` install the package during initial container setup; subsequent smoke runs find `/usr/bin/strings` ready.
- **Files modified:** `tools/linux-spike/create-distroboxes.sh`
- **Commit:** `53255c7`

**4. [Rule 1 — Bug] Plan template `bash -c "$(run_modes_in_box)"` shell-injection collision**

- **Found during:** Task 2 first smoke pass; transcripts contained only `+ echo DISTRO_PROBE` with no actual mode output.
- **Issue:** The plan template wrapped the heredoc body as `bash -c \"$(run_modes_in_box)\"` inside an outer `script -c \"...\"`. The heredoc body contains literal `"` characters (around `"$APPIMG"`, `"$SMOKE_PY"`, etc.) which terminate the outer `bash -c` double-quoted argument early. The shell parsed `bash -c "set -x echo "` as the script body, then drifted into argv.
- **Fix:** Write the heredoc body to a per-distro `mktemp` file and pipe it to `bash` via stdin (`bash` then reads its script from FD 0). The `env APPIMG="$APPIMG"` passthrough is preserved at the `distrobox enter` boundary — Issue #3 acceptance gate (`grep -qE 'env APPIMG="\$APPIMG"'`) still passes.
- **Files modified:** `tools/linux-spike/run-smoke.sh`
- **Commit:** `8f4d3f7` (feat(85A-06): add run-smoke.sh distrobox smoke driver)

**5. [Rule 1 — Bug] Plan template `--appimage-extract-and-run python smoke_test.py` ignores our args**

- **Found during:** Task 2 second smoke pass
- **Issue:** Every smoke mode returned `SPIKE_FAIL reason='usage' expected='hello_world.py <url>'`. The AppImage's `AppRun` (line 80) hard-codes `exec "${APPDIR}/usr/conda/bin/python" "${APPDIR}/hello_world.py" "$@"` — anything after `python` in the invocation is forwarded to hello_world.py, not honored as a script-to-run.
- **Fix:** Use `--appimage-extract` (no `-and-run`) to drop a squashfs tree into a per-container `mktemp`. Manually export the AppRun env vars (lines 47-74 verbatim — `GST_PLUGIN_*`, `GIO_EXTRA_MODULES`, `GI_TYPELIB_PATH`, `PYTHONHOME`, `PATH`). Invoke smoke_test.py directly with `$APPDIR/usr/conda/bin/python smoke_test.py ...`.
- **Files modified:** `tools/linux-spike/run-smoke.sh`
- **Commit:** `8f4d3f7`

**6. [Rule 1 — Bug] Plan template `--check-glibc "$APPIMG"` matches squashfs noise**

- **Found during:** Task 2 third smoke pass
- **Issue:** Running `strings` on the raw AppImage blob (a self-extracting squashfs binary) matched symbol-version-shaped strings in the COMPRESSED payload that don't correspond to any real linker reference (e.g., the regex matched a fake `GLIBC_2.7143` — clearly noise, not a real symbol version). This would have produced a false-positive GLIBC ceiling drift.
- **Fix:** `--check-glibc` is invoked against the EXTRACTED `$APPDIR/usr/conda/bin/python` binary instead. That's the canonical representative of the bundle's GLIBC ceiling (and matches what RESEARCH.md success criterion #2 intends).
- **Files modified:** `tools/linux-spike/run-smoke.sh`
- **Commit:** `8f4d3f7`

### Pre-existing planning-doc inconsistency (not auto-fixable)

**Plan acceptance gate `grep -c 'distrobox create' tools/linux-spike/create-distroboxes.sh | grep -qE '^3$'` is unsatisfiable with the prescribed verbatim template.** The plan's template (lines 144-170 of 85A-06-PLAN.md) uses a `for` loop over an associative array with ONE `distrobox create` call inside the loop body. The loop creates 3 distroboxes at RUNTIME but the literal-string `grep -c` only sees 1 occurrence. After the deviation amendments above, the count is 2 (one in the loop, one in a comment). The runtime invariant (`distrobox list | grep -c 'ms-spike-' | grep -qE '^3$'`) is satisfied and is the substantive verification — flagged here for plan-checker visibility.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: bundle-defect | .planning/spikes/85a-linux-packaging-spike/artifacts/MusicStreamer-spike-x86_64.AppImage | **HTTPS playback fails on all three distros AND on the bare host** with `Internal data stream error / Stream doesn't contain enough data / Can't typefind stream` from souphttpsrc + typefindelement. TLS handshake completes (curl confirms `200 OK` from ice6.somafm.com:443; smoke's `--assert-tls` mode confirms `GTlsBackendOpenssl + has_default_database=True`). Reproduces on bare host using the same extracted AppImage + manual env-export, so this is a **bundle / GStreamer-config defect, not a container or per-distro issue**. Per CONTEXT.md D-08: "If HTTP works but HTTPS doesn't, Phase 85's bundle is incomplete and we want to know NOW." This needs Kyle's decision: (a) accept HTTPS gap as documented finding and continue, OR (b) Plan 05 redo to investigate (likely missing or misconfigured `glib-networking` / `souphttpsrc` interaction with Icecast-over-TLS streams). |

## Tasks completed

| Task | Name | Commits | Files |
|------|------|---------|-------|
| 1    | Author create/teardown scripts; create 3 distroboxes | 459fb0b, 53255c7 | tools/linux-spike/create-distroboxes.sh, teardown-distroboxes.sh |
| 2    | Author run-smoke.sh; capture per-distro transcripts | 8f4d3f7 | tools/linux-spike/run-smoke.sh; 3 transcripts at .planning/spikes/.../artifacts/ |

## Self-Check: PASSED (with HTTPS-finding flagged)

- [x] AppImage copied from primary worktree into agent worktree (504 MB, byte-identical)
- [x] tools/linux-spike/create-distroboxes.sh present + executable + `bash -n` clean + no `--init` flag
- [x] tools/linux-spike/teardown-distroboxes.sh present + executable + `bash -n` clean
- [x] tools/linux-spike/run-smoke.sh present + executable + `bash -n` clean
- [x] `env APPIMG="$APPIMG"` (double-quoted) passthrough in run-smoke.sh
- [x] All 3 distroboxes present in `distrobox list` (Up status)
- [x] 3 transcripts exist at `.planning/spikes/85a-linux-packaging-spike/artifacts/{ubuntu22,fedora40,tumbleweed}-transcript.log`
- [x] SPIKE_OK marker present in each transcript (HTTP playback, 35s clean PLAYING)
- [x] GLIBC max ≤ 2.35 on each (`GLIBC_2.17` from the bundled python; well below cap)
- [x] `plugin_resolved=avdec_aac` AND `plugin_resolved=aacparse` per transcript
- [x] TLS backend asserted on each (`GTlsBackendOpenssl + has_default_database=True`)
- [ ] **HTTPS playback succeeds on at least Ubuntu 22.04 (D-08): FAILS — bundle defect, reproducible on host. Flagged as `threat_flag: bundle-defect`. Plan 06 cannot resolve this; it is a Plan 05 / Phase 85a pivot question.**
- [x] 3 commits made on the agent worktree branch (459fb0b feat + 53255c7 fix + 8f4d3f7 feat); SUMMARY.md commit pending
- [x] STATE.md / ROADMAP.md NOT modified (per orchestrator instruction)
- [x] Files verified present:
  - `tools/linux-spike/create-distroboxes.sh`
  - `tools/linux-spike/teardown-distroboxes.sh`
  - `tools/linux-spike/run-smoke.sh`
  - `.planning/spikes/85a-linux-packaging-spike/artifacts/{ubuntu22,fedora40,tumbleweed}-transcript.log`
- [x] Commits verified by `git log --oneline -5`
