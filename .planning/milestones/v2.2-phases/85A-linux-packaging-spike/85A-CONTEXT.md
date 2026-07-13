# Phase 85a: Linux Packaging Spike - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

A throwaway spike that produces a hello-world Qt + GStreamer AppImage, built in an Ubuntu 22.04 LTS Docker container, that launches and plays a remote MP3 stream on Ubuntu 22.04, Fedora 40, and openSUSE Tumbleweed. Validates the `linuxdeploy-plugin-conda` + `linuxdeploy-plugin-gstreamer` toolchain end-to-end and produces the AppRun env-var template (`GST_PLUGIN_SYSTEM_PATH_1_0`, `GST_PLUGIN_PATH_1_0`, `GST_PLUGIN_SCANNER`, `GST_REGISTRY_FORK=no`) ready for Phase 85 copy-paste consumption.

**In scope:**

- Hello-world Qt + GStreamer app — minimal `playbin3` consumer of a SomaFM MP3 stream (HTTP + HTTPS), borrowing the Phase 43 `smoke_test.py` shape.
- `linuxdeploy-plugin-conda` + `linuxdeploy-plugin-gstreamer` toolchain wiring — proved by `gst-inspect-1.0 avdec_aac` and `aacparse` both resolving from inside the AppRun shell.
- AppRun env-var template captured as a reusable snippet for Phase 85.
- GLIBC baseline verification (≤ 2.35 via `strings AppRun_or_main_so | grep GLIBC_ | sort -V | tail -1`).
- Cross-distro empirical PASS via podman-backed distrobox sessions on the dev rig's Wayland host (no separate VMs).
- Spike findings document with embedded per-distro evidence (audible + screenshot + terminal transcript).
- Wrap-up: append a new "Linux AppImage Bundling" feature area to the existing `spike-findings-musicstreamer` project skill (mirrors Phase 43's `/gsd:spike-wrap-up` flow).

**Out of scope (deferred to Phase 85):**

- Real `musicstreamer/` app bundling (the full PySide6 + yt-dlp + Node.js stack) — spike intentionally avoids dragging the real app in to keep the AppImage minimal and the failure-surface narrow.
- `.desktop` registration / icon / `MIME=audio` integration (PKG-LIN-APP-05).
- zsync update-info embedding (PKG-LIN-APP-06).
- MPRIS2 D-Bus reachability test (PKG-LIN-APP-07).
- `.pls` / `.m3u` MIME-association NEGATIVE test (PKG-LIN-APP-09).
- AAC stream playback test (PKG-LIN-APP-03's AAC tier) — spike validates plugin resolution; Phase 85 validates AAC audibility.
- Drift-guard tests in `tests/test_packaging_spec.py` — spike output drives the constants Phase 85 then wires up.
- AppImage signing (Phase 85 surface).
- Flatpak (Phase 86 surface).

</domain>

<decisions>
## Implementation Decisions

### Cross-distro verification mechanism

- **D-01: Container engine is podman (rootless, no daemon).** Kyle installed podman during discuss-phase (Docker coexists fine; distrobox prefers podman when both are present). Locked as the spike's container engine — no probe-and-adapt branch.
- **D-02: Verification runs in distrobox sessions on the dev rig's Wayland host**, NOT in headless Docker containers and NOT in separate VMs. Distrobox shares the host's pipewire audio path, giving real audible-playback fidelity from a single rig. Single-host caveat (kernel + pipewire are the host's, not the target distro's) accepted — the AppImage's userspace is what's being de-risked, and the host kernel ≥ Ubuntu 22.04's is a safe assumption.
- **D-03: Three named distroboxes — `ms-spike-ubuntu22`, `ms-spike-fedora40`, `ms-spike-tumbleweed`** — created from upstream images (`ubuntu:22.04`, `fedora:40`, `opensuse/tumbleweed`). Created via `tools/linux-spike/create-distroboxes.sh` for reproducibility.
- **D-04: Containers are ephemeral — `distrobox rm ms-spike-ubuntu22 ms-spike-fedora40 ms-spike-tumbleweed` at the end of the spike.** Clean state. Phase 85 production work re-creates from the same script if it needs to re-verify.
- **D-05: Per-distro evidence is the full empirical bundle — audible + Wayland screenshot + terminal transcript.** For each distro:
  - Manual audible confirmation (Kyle hears the MP3 on host pipewire).
  - Wayland screenshot of the AppImage running (host-native tool — Claude picks `grim` or `gnome-screenshot` based on host session).
  - Terminal transcript: `gst-inspect-1.0 avdec_aac` output, `gst-inspect-1.0 aacparse` output, GLIBC grep output, AppImage launch stdout/stderr.
  - All three artifacts embedded inline (or linked) in `85A-SPIKE-FINDINGS.md` under a per-distro section.
- **D-06: Audible PASS protocol per distro = 30s play + pause/resume + stop + relaunch.** Sequence:
  1. Launch AppImage, confirm pipeline reaches PLAYING.
  2. Hear ~10s of clean audio.
  3. Hit pause; verify silence + state==PAUSED.
  4. Hit play; verify audio resumes + state==PLAYING.
  5. Hit stop.
  6. Close the AppImage process entirely.
  7. **Relaunch** the AppImage and confirm second launch also reaches PLAYING.
  Catches the `GST_REGISTRY_FORK=no` regression case (registry-rebuild on every launch is the AppRun-template footgun). Aligns with success criterion #4 (AppRun env-var template).

### Test stream URL pin

- **D-07: Primary stream is SomaFM Groove Salad MP3.** Project's known-good baseline (Phase 62 / 78 / 84 buffer instrumentation, `spike-findings-musicstreamer` smoke pattern). Matches actual user behavior — not synthetic.
- **D-08: HTTP AND HTTPS variants both exercised on at least one distro.**
  - HTTP: `http://ice1.somafm.com/groovesalad-128-mp3`
  - HTTPS: `https://ice6.somafm.com/groovesalad-128-mp3`
  HTTPS exercises the conda bundle's TLS path (`glib-networking` + `gio` modules) — a Phase 43-validated Windows footgun being re-validated on Linux. If HTTP works but HTTPS doesn't, Phase 85's bundle is incomplete and we want to know NOW. Aligns with PKG-LIN-APP-03's "same plugin set as Windows".
- **D-09: SomaFM-only fallback chain on upstream outage — Groove Salad → Drone Zone → Beat Blender → hard-fail.** All three are PROJECT.md-documented known-good Soma MP3 stations. If all three are unreachable, that's a real upstream story worth pausing the spike on — no QNAP-hosted fallback infrastructure needed for a one-off spike. Per-distro evidence records which channel won.

### Claude's Discretion

- **Spike artifact layout** — Mirror Phase 43: source under `.planning/spikes/85a-linux-packaging-spike/` (Dockerfile, hello-world Python source, `linuxdeploy.AppDir/` template, `AppRun` template, `smoke_test.py`, `build.sh`, `85A-SPIKE-FINDINGS.md`). Findings doc lives alongside the source, not in the phase directory, so it's portable into the wrap-up skill.
- **Wrap-up shape** — Run `/gsd:spike-wrap-up` after the spike's verification PASS to append a new "Linux AppImage Bundling" feature area to the existing `spike-findings-musicstreamer` project skill. Sources copied verbatim into `sources/85a-linux-packaging-spike/` inside the skill. (Phase 43's pattern is the proven analog — see references/windows-gstreamer-bundling.md inside the skill.)
- **Hello-world app scope** — Single-file Python script using `Gst.parse_launch("playbin3 uri=...")` with a minimal Qt event loop, mirroring Phase 43's `smoke_test.py` shape. Bus-bridge / `GstBusLoopThread` complexity stays OUT — Phase 43.1 already validated the cross-platform bus-handler threading contract (per CONCERNS.md tech-debt entry), and re-exercising it would expand the spike's surface area without de-risking anything Linux-specific.
- **Build container choice** — `ubuntu:22.04` Docker image (locked by success criterion #2: GLIBC ≤ 2.35). Pin a specific image SHA in `Dockerfile` for reproducibility; documented in findings.
- **linuxdeploy version pinning** — Pin specific `linuxdeploy`, `linuxdeploy-plugin-conda`, `linuxdeploy-plugin-gstreamer` AppImage URLs + SHA256 in `build.sh`; documented in findings.
- **Conda env shape** — Minimal: Python 3.10+, PySide6, gst-python, gst-plugins-{base,good,bad,ugly}, gst-libav, glib-networking. Channel: `conda-forge` only. Documented in `environment-spike.yml` next to the source.
- **GLIBC verification** — Wire `strings AppRun_or_main_so | grep GLIBC_ | sort -V | tail -1` into `smoke_test.py` (or `build.sh`); exit non-zero on > 2.35. Findings doc captures the actual top line per distro.
- **Plugin discovery harness** — `smoke_test.py` execs `gst-inspect-1.0 avdec_aac` and `gst-inspect-1.0 aacparse` from inside the AppRun shell, asserts both resolve, captures stdout for the findings transcript.
- **Wayland screenshot tool** — `grim` (Sway/wlroots) or `gnome-screenshot` (GNOME) — pick based on the host session at spike-execution time. Per `[[project_deployment_target]]`, host is Wayland GNOME Shell, so `gnome-screenshot --window` is the default.
- **Negative-pivot policy** — If `linuxdeploy-plugin-conda` is structurally broken on Ubuntu 22.04 + conda-forge GStreamer, the spike stops and reports the failure mode in findings (does not silently pivot to a different toolchain — that's a planning-phase decision). Same protocol if `linuxdeploy-plugin-gstreamer` doesn't discover the conda layout.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 85a scope + dependencies

- `.planning/ROADMAP.md` §"Phase 85a: Linux Packaging Spike" (lines 48–61) — Goal, success criteria, research flag = YES.
- `.planning/REQUIREMENTS.md` §"Linux Packaging — AppImage (PKG-LIN-APP)" (PKG-LIN-APP-01..09) — Phase 85 requirements that the spike de-risks (NOT consumed by 85a directly — spike output feeds Phase 85).
- `.planning/REQUIREMENTS.md` §"Pitfalls" rows mentioning Pitfall 1 (GLIBC) and Pitfall 2 (plugin discovery) — the two named risks the spike must verify mitigations for.

### Spike analog (proven Windows-side pattern)

- `.claude/skills/spike-findings-musicstreamer/SKILL.md` — Phase 43 Windows-spike outcome packaged as a project skill. Same shape, different toolchain. Read this BEFORE designing the Linux spike's source layout, build driver, and wrap-up flow.
- `.claude/skills/spike-findings-musicstreamer/references/windows-gstreamer-bundling.md` — Conda-forge findings; the "same plugin set as Windows" PKG-LIN-APP-03 clause means the Linux conda env should mirror this.
- `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md` — Two cross-platform threading rules already validated. **Spike does NOT re-exercise these** — out-of-scope rationale documented in D-Discretion above.
- `.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/smoke_test.py` — Pattern to mirror for the Linux `smoke_test.py`.
- `.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/runtime_hook.py` — Conceptual analog of the Linux AppRun env-var template (env vars set at app startup).
- `.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/build.ps1` — Conceptual analog of the Linux `build.sh` build driver.

### Codebase context

- `.planning/codebase/STACK.md` — Confirms GStreamer 1.0 + PyGObject + Node.js runtime requirements (Node.js NOT in spike scope but documented for Phase 85).
- `.planning/codebase/CONCERNS.md` §"GStreamer Bus-Loop Threading Model" — Why the spike intentionally avoids `bus.add_signal_watch()` complexity.

### External tooling docs (researcher will fetch deeper context)

- linuxdeploy: https://github.com/linuxdeploy/linuxdeploy — base AppDir/AppImage builder.
- linuxdeploy-plugin-conda: https://github.com/linuxdeploy/linuxdeploy-plugin-conda — bundles a conda env into an AppImage.
- linuxdeploy-plugin-gstreamer: https://github.com/linuxdeploy/linuxdeploy-plugin-gstreamer — bundles GStreamer plugins + sets `GST_PLUGIN_PATH_1_0` / `GST_PLUGIN_SCANNER` / `GST_REGISTRY_FORK`.
- distrobox: https://distrobox.it — podman-backed dev containers with host pipewire/Wayland sharing.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **Phase 43 `smoke_test.py` shape** — Self-contained HTTPS playback test (playbin3 + state==PLAYING assertion + state-machine driver). Drop-in pattern for the Linux spike's `smoke_test.py`. Located at `.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/smoke_test.py`.
- **Phase 43 `runtime_hook.py`** — Sets `GIO_EXTRA_MODULES`, `GI_TYPELIB_PATH`, `GST_PLUGIN_SCANNER` for the bundled conda env. Conceptual template for the Linux AppRun env-var snippet.
- **Phase 43 `build.ps1` `Invoke-Native` pattern** — Shell-driver that captures stderr and exit codes cleanly. Linux `build.sh` mirrors the same explicit error-handling discipline.
- **Phase 43 `environment.yml`** — Conda-forge channel pin + minimal GStreamer + Python set. Linux `environment-spike.yml` is a near-clone (subtract Windows-only bits, keep the cross-platform conda env shape).
- **PROJECT.md SomaFM channel names** — Groove Salad / Drone Zone / Beat Blender are documented known-good MP3 stations; spike's fallback chain reuses this list verbatim (D-09).

### Established Patterns

- **`.planning/spikes/<phase>-<slug>/` directory** for spike sources, with a sibling `<PHASE>-SPIKE-FINDINGS.md` (Phase 43 set the convention).
- **`/gsd:spike-wrap-up` flow** packages spike sources into a Claude-discoverable project skill (`spike-findings-musicstreamer` already exists; this spike appends a new feature area).
- **GLIBC + plugin-discovery verification via `strings` + `gst-inspect-1.0`** — two-step sanity check at the end of every bundle build, captured in findings transcripts.
- **Conda-forge channel only** — no `defaults`, no `nodefaults` (Phase 43 stack lock).

### Integration Points

- **Spike output → Phase 85 input.** Phase 85's plan-phase will read `85A-SPIKE-FINDINGS.md` + the wrapped skill's new feature area as its primary research input. Phase 85's `Research flag: NO` (per ROADMAP.md) depends on this spike doing the unknowns-elimination.
- **`tools/check_bundle_plugins.py` (Windows-side drift-guard)** — Phase 85 will add a Linux-equivalent drift-guard; spike's findings document the plugin list that drift-guard will assert against.
- **`tests/test_packaging_spec.py` GLIBC + MIME source-grep** — Phase 85 wires this up; spike confirms the GLIBC literal it should grep for (≤ 2.35).
- **`musicstreamer/player.py` + `musicstreamer/gst_bus_bridge.py`** — Not touched by the spike. Real-app bus-bridge integration is Phase 85's problem; spike validates the bundle layer only.

</code_context>

<specifics>
## Specific Ideas

- "Mirror Phase 43" is the recurring theme — the Windows spike's deliverable shape (sources + findings + wrap-up into project skill) is the analog Kyle wants reused for Linux. The skill `spike-findings-musicstreamer` already exists with that contract.
- HTTPS coverage in addition to HTTP is explicit: Kyle wants the TLS bundle path validated NOW because Phase 43 burned that footgun on Windows; the conda TLS bundling (`glib-networking` + gio modules) is the exact same surface on Linux.
- "30s play + pause/resume + stop + relaunch" is the audible-PASS protocol because the AppRun env-var template (`GST_REGISTRY_FORK=no` specifically) is one of the four explicit success criteria. Relaunch is the only protocol step that exercises the registry-fork flag.
- SomaFM-only fallback chain (no QNAP infrastructure): if Groove Salad + Drone Zone + Beat Blender are all down, that's a SomaFM-side outage worth pausing the spike on — not a workaround opportunity.

</specifics>

<deferred>
## Deferred Ideas

- **AAC stream playback test** — Phase 85 surface (PKG-LIN-APP-03 AAC tier verification).
- **MPRIS2 D-Bus test in the AppImage** — Phase 85 surface (PKG-LIN-APP-07).
- **`.desktop` + icon + `MIME=audio` integration** — Phase 85 surface (PKG-LIN-APP-05).
- **zsync update-info embedding** — Phase 85 surface (PKG-LIN-APP-06).
- **`.pls` / `.m3u` MIME-association NEGATIVE test** — Phase 85 surface (PKG-LIN-APP-09).
- **AppImage signing** — Phase 85 surface (out of all spike success criteria).
- **Real `musicstreamer/` app bundling** — Phase 85 surface; spike stays minimal to keep the failure-surface narrow.
- **CI-replicable headless verification** — A future infra phase could wire the `tools/linux-spike/` scripts into GitHub Actions; spike validates the LOCAL path only.
- **Flatpak parity** — Phase 86 surface (separate AppImage and Flatpak builds per ROADMAP.md / PROJECT.md milestone goal).

</deferred>

---

*Phase: 85A-linux-packaging-spike*
*Context gathered: 2026-05-25*
