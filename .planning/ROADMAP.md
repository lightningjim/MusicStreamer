# Roadmap: MusicStreamer

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2024-03-20)
- ✅ **v1.1 Polish & Station Management** — Phases 5–6 (shipped 2024-03-21)
- ✅ **v1.2 Station UX & Polish** — Phases 7–11 (shipped 2024-03-25)
- ✅ **v1.3 Discovery & Favorites** — Phases 12–15 (shipped 2024-04-03)
- ✅ **v1.4 Media & Art Polish** — Phases 16–20 (shipped 2024-04-05)
- ✅ **v1.5 Further Polish** — Phases 21–34 (shipped 2026-04-10)
- ✅ **v2.0 OS-Agnostic Revamp** — Phases 35–48 (shipped 2026-04-25)
- ✅ **v2.1 Fixes and Tweaks** — Phases 49–84 (shipped 2026-05-25)
- 🚧 **v2.2 Package Building and QOL features/tweaks** — Phases 85–95 (planning, started 2026-05-25)

Earlier milestone details collapsed for brevity; full ROADMAPs preserved under `.planning/milestones/v{X.Y}-ROADMAP.md`.

---

## Current Milestone: v2.2 Package Building and QOL features/tweaks

**Created:** 2026-05-25
**Core Value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.
**Milestone Goal:** Close packaging parity across Linux (AppImage + Flatpak) and Windows (SMTC AUMID + Win11 packaging UAT), and deliver a focused QOL polish pass across GBS.FM integration, SomaFM preroll consistency, ICY-disabled cover visuals, and Phase 77 test debt.
**Granularity:** standard (config.json)
**Phase numbering:** continues from v2.1 Phase 84; first v2.2 phase is Phase 85.

### Phases

- [x] **Phase 85a: Linux Packaging Spike** — De-risk linuxdeploy + conda + GStreamer plugin discovery before locking the AppImage recipe
- [x] **Phase 91: FIX-MPRIS (Phase 77 deferred MPRIS2 tests)** — Repair the 7 D-03-deferred MPRIS2 cross-file test failures so the test-clean baseline holds before Flatpak in-sandbox MPRIS verification
- [x] **Phase 85: Linux Common + AppImage Build** — Ship a portable `MusicStreamer-<version>-x86_64.AppImage` with conda's GStreamer/Qt/Node bundle, `.desktop` integration, MPRIS2, and zsync update metadata
- [x] **Phase 86: Linux Flatpak Build** — Ship `io.github.kcreasey.MusicStreamer.flatpak` via `flatpak-builder` on KDE 6.8 + PySide BaseApp + ffmpeg-full, with minimal finish-args and in-sandbox MPRIS2 verified
- [x] **Phase 86.1: SC5 Failure Follow-up from Phase 86 (INSERTED)** — Make the Flatpak first-launch import the SOLE consent-based path host data enters the sandbox: wire the offer-once import wizard into startup and fix the silent host-secret copy under the `:ro` mount
- [x] **Phase 88: Windows Packaging Bundle (WIN-02 + VER-02-J + WIN-05)** — One Win11 VM session: Inno Setup AUMID polish + `.lnk` cleanup, full v2.2-installer UAT against a previously-v2.1 VM, and AAC stream retest
- [x] **Phase 88.3: Bundle QtWebEngine in Frozen Windows Build (Phase 88 UAT G6) (INSERTED)** — In-app OAuth logins (GBS/Twitch/Google) open the WebEngine window from the frozen build via an isolated-helper-bundle (`oauth_helper.exe` as its own pip-PySide6 PyInstaller exe); closed via the consolidated 88-03 VM UAT
- [x] **Phase 88.2: Fix GBS.FM In-App Login Dialog Fails to Start (Phase 88 UAT G3) (INSERTED)** — argv-dispatch + frozen-safe re-exec so the in-app GBS/Twitch/Google login helper starts on the frozen Windows build; FailedToStart falls back to cookie import. VM UAT closed via 88-03
- [x] **Phase 88.1: Fix SMTC Media Overlay Absent + Dead Media Keys (Phase 88 UAT G2) (INSERTED)** — Bundle the winrt `.pyd` extensions via `collect_all` so the frozen build's SMTC media session registers; backend selection logged, build/CI guards prevent regression. VM UAT closed via 88-03
- [x] **Phase 89a: Channel-Avatar DB Migration + Storage Layout** — Foundation column + filesystem layout for YT and Twitch avatars; idempotent additive migration in `repo.py:db_init()`
- [x] **Phase 87: GBS.FM Marquee + Themed-Day Detection** — Banner widget + themed-logo session swap; establishes the QtWebEngine cookie-persistence-cross-process pattern reused by Phase 89
- [x] **Phase 87.1: GBS.FM Session-Expiry Re-login Prompt (INSERTED)** — Surface a clear "GBS session expired — please log in again" prompt that launches the in-app GBS login and refreshes on success, instead of the active playlist silently failing to load (5 plans, complete 2026-06-18)
- [x] **Phase 89: YouTube Channel-Avatar Fetch + Cover-Slot Swap** — ICY-disabled YT stations show the channel avatar (circular) in the cover slot; cover-resolver precedence keeps MB-CAA above avatar
- [x] **Phase 89.1: Re-key Channel Avatar from Per-Station to Per-Provider (INSERTED)** — Move the YT/Twitch avatar from Station to Provider (add `providers.avatar_path`, key the cached PNG by `provider_id`) so sibling streams of one channel share one fetch + one file; migrate existing per-station avatars and deprecate the old column
- [x] **Phase 89b: Twitch Channel-Avatar Fetch** — Twitch GQL `profileImageURL` fetch reusing the Phase 32 user token (Helix 404s for this token — pivoted to gql.twitch.tv); shares storage + cover-slot path with Phase 89. Add-path first-save fetch closed via 89B-03 (2026-06-17)
- [x] **Phase 89c: Provider Brand-Avatar Cover-Slot Fallback (INSERTED)** — SomaFM/AudioAddict brand mark (circular) in the cover slot on cover-resolution-exhausted (distinct from the duplicated station logo); bundled per-provider PNGs + EditStationDialog upload override. Verified + secured 2026-06-17
- [ ] **Phase 87b: GBS Zero-Token Single-Song Add** — Persistent "Add a song" button visible whenever GBS.FM is bound and logged in (any token count); UX never frames as a token grant
- [x] **Phase 90: SomaFM Preroll Instrumentation** — Size-rotated `preroll-events.log` + "Open preroll log" + re-fetch lever; no behavior change. Verified 2026-06-18 (human UAT): Boot Liquor + others that previously missed prerolls now play them with intended random rotation. Reframed verify-first — the symptom was incidentally fixed by unrelated changes between phase creation and execution.
- [x] **Phase 90b (CONDITIONAL): SomaFM Preroll Fix** — CONDITION DID NOT FIRE — not needed (closed 2026-06-18). Phase 90's human UAT found no station truly still broken; the missing-preroll symptom self-resolved, so there is no atomic root cause to fix. SOMA-PRE-03 (probe) + the passive-harvest half are closed-as-unnecessary, not pending.
- [x] **Phase 92: FIX-PLS — PLS URL-Fallback for Codec/Bitrate** — Carry-over from Phase 58 pending-todo: detect codec/bitrate from resolved URL pattern when PLS title metadata is missing
- [x] **Phase 93 (CONDITIONAL): BUFFER-MONITOR Follow-Up** — Condition FIRED (all 3 triggers); closed-via-deviation 2026-06-15. YouTube live-edge starvation fixed out-of-band (commit f716f083, DVR seek); SomaFM/network residual closed as no-action. See 93-VERIFICATION.md
- [x] **Phase 94: Sidebar Logo Thumbnail Optimization** — Investigate sidebar scroll slowdown on large lists (e.g., DI.fm); generate pre-scaled small logo variants for sidebar use while preserving full-res for Now Playing
- [ ] **Phase 95: YT URL-Change Replay Bug** — After editing a YT stream with a changed URL, first play fails with "stream exhausted"; replay picks up the new URL. Diagnose stale cached resolution post-edit, fix to invalidate on station update

### Phase Details

#### Phase 85a: Linux Packaging Spike

**Goal**: De-risk the linuxdeploy-plugin-conda + linuxdeploy-plugin-gstreamer toolchain before committing to the full Linux build recipe; produce a working hello-world AppImage that plays a remote MP3 stream on all three target distros.
**Depends on**: Nothing (Tier 1, parallel-eligible with Phase 91)
**Requirements**: (spike — no requirements consumed; outputs feed Phase 85)
**Success Criteria** (what must be TRUE):

  1. A hello-world Qt + GStreamer AppImage built in an Ubuntu 22.04 LTS Docker container launches and plays a remote MP3 stream on Ubuntu 22.04, Fedora 40, and openSUSE Tumbleweed (cross-distro empirical PASS).
  2. `strings AppRun_or_main_so | grep GLIBC_ | sort -V | tail -1` reports a GLIBC requirement of 2.35 or lower (Pitfall 1 mitigation verified).
  3. `linuxdeploy-plugin-gstreamer` against conda's `$CONDA_PREFIX/lib/gstreamer-1.0` produces an AppDir where `gst-inspect-1.0 avdec_aac` and `aacparse` both resolve from inside the AppRun shell (Pitfall 2 verified).
  4. Spike outcome document captures the AppRun env-var template (`GST_PLUGIN_SYSTEM_PATH_1_0`, `GST_PLUGIN_PATH_1_0`, `GST_PLUGIN_SCANNER`, `GST_REGISTRY_FORK=no`) ready for Phase 85 consumption.

**Plans**: 8 plans across 6 waves

- [x] 85A-01-PLAN.md — Host tooling install + environment manifest (Wave 0)
- [x] 85A-02-PLAN.md — Dockerfile + environment-spike.yml (Wave 1, parallel with 03)
- [x] 85A-03-PLAN.md — Toolchain SHA256 pins + verify-pins.sh drift-guard (Wave 1, parallel with 02)
- [x] 85A-04-PLAN.md — hello_world.py + AppRun template + smoke_test.py (Wave 2)
- [x] 85A-05-PLAN.md — build.sh end-to-end AppImage assembly (Wave 3)
- [x] 85A-06-PLAN.md — Distrobox scripts + per-distro programmatic smoke (Wave 4)
- [x] 85A-07-PLAN.md — Audible-PASS protocol per distro + screenshots (Wave 5, manual)
- [x] 85A-08-PLAN.md — SPIKE-FINDINGS.md + skill APPEND wrap-up + teardown (Wave 6)

**Research flag**: YES — `/gsd:plan-phase --research-phase 85a` recommended.

#### Phase 91: FIX-MPRIS (Phase 77 Deferred MPRIS2 Tests)

**Goal**: The 7 D-03-deferred MPRIS2 cross-file test failures from Phase 77 turn green, restoring the 100%-pass baseline before Flatpak in-sandbox MPRIS2 verification depends on it.
**Depends on**: Nothing (Tier 1, parallel-eligible with Phase 85a; tests-only, no production code dependency)
**Requirements**: FIX-MPRIS-01, FIX-MPRIS-02, FIX-MPRIS-03
**Success Criteria** (what must be TRUE):

  1. `grep -rnP '^\s*class\s+FakePlayer\s*\(\s*QObject\s*\)\s*:' tests/ | wc -l` returns exactly 1 and the only declaration site is `tests/_fake_player.py:37` (Pitfall 15 verified at source level; anchored to a real class declaration so the docstring literal in `tests/test_fake_player_no_inline.py:28` no longer false-positives — D-04).
  2. All 7 previously-deferred MPRIS2 cross-file tests pass via `uv run --with pytest pytest tests/test_media_keys_mpris2*.py`; no test-runtime regressions vs. the Phase 91 pre-phase baseline of 1838 passed (captured 2026-06-02); verification asserts passed >= 1838, never shrinkage.
  3. Phase 77's `test_richtext_baseline_unchanged_by_phase_71` drift-guard remains green; no source-introspection regressions introduced by the repair.

**Plans**: 1 plan, 1 wave

- [x] 91-01-PLAN.md — Bookkeeping close-out: verify Phase 77 MPRIS2 closure (378440c) holds, fix the miswritten SC1 grep to the anchored PCRE form, refresh the SC2 baseline, flip FIX-MPRIS-01/02/03 to Complete

**Research flag**: NO — pattern is well-established (Phase 77 D-04 + shared FakePlayer convention).

#### Phase 85: Linux Common + AppImage Build

**Goal**: Users can download a single `MusicStreamer-<version>-x86_64.AppImage`, mark executable, and run it portably on Ubuntu 22.04 LTS, Fedora 40, and openSUSE Tumbleweed with full audio, MPRIS2, and YouTube playback working out of the box.
**Depends on**: Phase 85a (spike outcome consumed: AppRun template + conda-plugin compatibility verified)
**Requirements**: PKG-LIN-APP-01, PKG-LIN-APP-02, PKG-LIN-APP-03, PKG-LIN-APP-04, PKG-LIN-APP-05, PKG-LIN-APP-06, PKG-LIN-APP-07, PKG-LIN-APP-08, PKG-LIN-APP-09, PKG-LIN-APP-10
**Success Criteria** (what must be TRUE):

  1. User downloads the AppImage, runs `chmod +x` and double-clicks; the app launches with no install step and plays a stream within seconds.
  2. The same AppImage launches and plays an AAC stream (DI.fm or SomaFM AAC tier) on Ubuntu 22.04 LTS, Fedora 40, and openSUSE Tumbleweed (cross-distro empirical PASS via the conda-bundled gst-libav).
  3. After running once via AppImageLauncher, a `.desktop` entry with icon and `MIME=audio` appears in the user's GNOME apps grid; standalone execution without AppImageLauncher still launches the app.
  4. OS media keys (play/pause/stop) control the AppImage's playback via MPRIS2 from the host session, and the Windows packaging drift-guards (`tools/check_bundle_plugins.py`, `tests/test_packaging_spec.py`) still pass after the Linux PR lands (Pitfall 16 mitigation).
  5. `tests/test_packaging_spec.py` source-grep checks confirm GLIBC baseline ≤ 2.35, no `.pls`/`.m3u` MIME associations registered, and zsync update info is embedded in the AppImage payload.

**Plans:** 4 plans across 3 waves
Plans:
**Wave 1**

- [x] 85-01-PLAN.md — environment.yml + build.sh refactor + production AppRun (D-01/D-02/D-03 single-source-of-truth bundle; Pitfalls 19/20)

**Wave 2** *(parallel; both depend on 85-01)*

- [x] 85-02-PLAN.md — GPG signing + zsync embedding + REQUIREMENTS PKG-LIN-APP-10 row (D-08/D-09/D-10/D-11/D-12)
- [x] 85-03-PLAN.md — .github/workflows/linux-appimage.yml workflow_dispatch CI scaffold (D-13/D-14/D-15/D-16)

**Wave 3** *(blocked on Waves 1+2)*

- [x] 85-04-PLAN.md — Cross-distro smoke harness + Linux drift-guard pytest + README + REQUIREMENTS bookkeeping (D-04/D-05/D-06/D-07/D-17 + close)

**Research flag**: NO — spike consumed in Phase 85a; standard pattern in Phase 85.

#### Phase 86: Linux Flatpak Build

**Goal**: Users can install `io.github.kcreasey.MusicStreamer.flatpak` via `flatpak install --user` or sideload through GNOME Software, launch via Activities, and use the app with full audio + MPRIS2 + GBS.FM login working inside the sandbox.
**Depends on**: Phase 91 (FIX-MPRIS — Flatpak in-sandbox MPRIS2 verification of PKG-LIN-FP-08 requires the test baseline clean)
**Requirements**: PKG-LIN-FP-01, PKG-LIN-FP-02, PKG-LIN-FP-03, PKG-LIN-FP-04, PKG-LIN-FP-05, PKG-LIN-FP-06, PKG-LIN-FP-07, PKG-LIN-FP-08, PKG-LIN-FP-09, PKG-LIN-FP-10
**Success Criteria** (what must be TRUE):

  1. `flatpak install --user io.github.kcreasey.MusicStreamer.flatpak` succeeds against a clean sideload host; the app appears in GNOME Software and launches via `flatpak run`.
  2. Inside the sandbox, AAC streams (DI.fm, AudioAddict, SomaFM AAC tiers) play audibly via the `org.freedesktop.Platform.ffmpeg-full//24.08` extension (Phase 69 lesson re-applied to Linux).
  3. GBS.FM in-app login subprocess (Phase 76 QtWebEngine flow) completes without a namespace error and cookies persist across subprocess restart (Pitfall 4 mitigated via `QTWEBENGINE_DISABLE_SANDBOX=1` in finish-args, verbatim spelling per Flathub `io.qt.qtwebengine.BaseApp`).
  4. OS media keys via MPRIS2 control sandbox playback (`--own-name=org.mpris.MediaPlayer2.MusicStreamer`); no broad `--socket=session-bus` in the manifest.
  5. First launch on a host with existing `~/.local/share/musicstreamer/` offers the in-app import wizard (Phase 25 settings-export ZIP flow); manifest declares zero broad filesystem permissions; `appstreamcli validate` and `desktop-file-validate` both pass pre-flight.

**Plans**: 5 plans (3 waves)

- [x] 86-01-PLAN.md — Manifest + python3-modules.yaml + .desktop/metainfo artifacts (FP-01/03/04/05/09/10)
- [x] 86-02-PLAN.md — First-launch import wizard reusing Phase 25 ZIP flow (FP-06)
- [x] 86-03-PLAN.md — Manifest allow/deny-list + runtime-pin + validator + first-launch drift-guards (FP-01/03/04/05/06/08/09/10)
- [x] 86-04-PLAN.md — build.sh + workflow_dispatch CI + GPG signing + REQUIREMENTS signing row (FP-02/04/10/11)
- [x] 86-05-PLAN.md — UAT evidence bundle: install/launch, AAC, GBS.FM login, MPRIS2 (FP-02/05/07/08)

**Research flag**: YES — `/gsd:plan-phase --research-phase 86` recommended (QtWebEngine sandbox-in-sandbox, BaseApp version pinning, Flathub policy nuances).

### Phase 86.1: SC5 failure followup from phase 86 (INSERTED)

**Goal:** Make the Flatpak first-launch import path correct and safe: the offered, consent-based, offer-once import wizard is the SOLE path by which unsandboxed host data enters the sandbox. Fix two coupled SC5 defects — (1) the wizard is never wired into startup, and (2) `migration.run_migration()` silently copies host secrets into the sandbox without consent because the :ro mount makes src != dest.
**Requirements**: PKG-LIN-FP-06
**Depends on:** Phase 86
**Plans:** 2 plans

Plans:

- [x] 86.1-01-PLAN.md — Add is_sandboxed() helper + make run_migration() sandbox-aware (skip auto-copy, keep marker/dest dir); secrets never copied without consent
- [x] 86.1-02-PLAN.md — Wire FlatpakImportWizard into _run_gui (gated on is_sandboxed AND should_offer, deferred via singleShot after window.show()); gate-logic tests

#### Phase 88: Windows Packaging Bundle (WIN-02 + VER-02-J + WIN-05)

**Goal**: One Win11 VM session delivers v2.2 installer parity: SMTC media controls bind correctly via Start Menu launch, old `.lnk` shortcuts get cleaned up on upgrade, full golden-path UAT signs off, and AAC streams retest clean.
**Depends on**: Nothing inside v2.2 (parallel-eligible with Tiers 1–2; carry-over from v2.1)
**Requirements**: WIN-02, WIN-02-A, WIN-02-B, VER-02-J, WIN-05
**Success Criteria** (what must be TRUE):

  1. After installing v2.2 from the new installer, the Start Menu `MusicStreamer.lnk` carries `AppUserModelID = org.lightningjim.MusicStreamer` (verified via `(New-Object -ComObject Shell.Application).Namespace(0).ParseName('shortcut.lnk').ExtendedProperty('System.AppUserModel.ID')`) and the SMTC overlay shows "MusicStreamer" (not "Unknown app") on play.
  2. Upgrading a Win11 VM that had v2.1 installed first to v2.2 deletes the old `.lnk` via Inno `[InstallDelete]` BEFORE creating the new one; release-notes "unpin from taskbar before upgrading" footnote documented (Pitfall 6).
  3. `tests/test_aumid_string_parity.py` greps the installed `.lnk`'s AUMID property and asserts identity with the `SetCurrentProcessExplicitAppUserModelID` literal in `__main__.py` plus the Inno `[Icons]` directive.
  4. Win11 VM full-UAT script (launch, station play, ICY metadata, media keys, AAC stream playback, cover art, MB-CAA fallback, GBS.FM, SomaFM preroll) signs off all golden-path checks.
  5. DI.fm + AudioAddict + SomaFM AAC tier streams play audibly on the v2.2 installer (Phase 69 WIN-05 acceptance re-confirmed; `tools/check_bundle_plugins.py` exit code 10 guard fires correctly on missing gst-libav rebuild).

**Plans**: 4 plans across 3 waves
Plans:
**Wave 1** *(parallel; disjoint files)*

- [x] 88-01-PLAN.md — Inno [InstallDelete] old-.lnk cleanup + RELEASE-NOTES.md taskbar-unpin footnote (WIN-02-A)
- [x] 88-02-PLAN.md — Static 3-way AUMID parity test + AAC plugin-guard regression assertions, Linux-CI runnable (WIN-02-B, WIN-05)

**Wave 2** *(blocked on Waves 1; human at Win11 VM)*

- [ ] 88-03-PLAN.md — Win11 VM UAT script: installed-.lnk AUMID readback + SMTC overlay + golden-path + audible AAC + exit-10 guard confirmation (WIN-02, VER-02-J, WIN-05)

**Wave 3** *(gap closure — G1; disjoint files from Waves 1-2)*

- [x] 88-04-PLAN.md — Installer [InstallDelete] dist-info cleanup: scoped `{app}\_internal\musicstreamer-*.dist-info` wildcard fixes stale-version mislabel + VM-only UAT-17 row (WIN-02-A, VER-02-J)

**Research flag**: NO — spike-style first-plan (WPR trace + `Get-StartApps` PowerShell verification) lives inside the phase but no `--research-phase` needed.

### Phase 88.3: Bundle QtWebEngine in frozen Windows build so OAuth logins run — Phase 88 UAT G6 (INSERTED)

**Goal:** GBS.FM, Twitch, and Google/YouTube in-app OAuth logins open the QtWebEngine login window from the frozen Windows build instead of crashing the helper subprocess exit=2. **Approach: B1 isolated-helper-bundle** (spike-validated, [[spike-001]] VALIDATED 2026-06-12). The original same-bundle approach (88.3-01, executed) was INVALIDATED at G6 UAT: conda-forge ships zero PySide6 WebEngine bindings at any version, and pip PySide6-Addons WebEngine is ABI-incompatible with conda qt6-main/GStreamer in one process (conda Qt6Core on PATH shadows pip's → DLL load failure); all-pip breaks GStreamer audio (ICU). B1 freezes `oauth_helper.py` as its OWN PyInstaller exe from an isolated pip-PySide6-Essentials+Addons==6.10.1 env (no conda, no GStreamer); the conda main exe launches that separate `oauth_helper.exe`. Spike proved: WebEngine imports cleanly when frozen, QtWebEngineProcess.exe bundles via the hook, GBS+Google logins complete, and the bundle's Qt beats qt6-main's Library\bin on PATH by adjacency (safe to spawn from the conda exe, no PATH mitigation). Replan reverts the stale 88.3-01 same-bundle changes (spec hiddenimports, __main__ --check-webengine on the conda exe, build.ps1 step-4e, webengine spec tests), adds the 2nd isolated-pip build, ships both artifacts via Inno, fixes the Twitch platform-aware UA, and closes with a Win11 VM UAT.
**Requirements**: G6-T1, G6-T2, G6-T3, G6-T4, G6-T5 (automated source-text drift guards); G6-T6, G6-T7, G6-T8 (manual VM UAT)
**Depends on:** Phase 88
**Plans:** 5 plans (88.3-01 HISTORICAL same-bundle, retained + reverted; 88.3-02..05 are the B1 replan)

Plans:

- [x] 88.3-01-PLAN.md — (HISTORICAL — same-bundle attempt, INVALIDATED at G6 UAT; its changes are reverted by the B1 replan) Wave 0 drift-guard tests + spec WebEngine hiddenimports + __main__.py --check-webengine guard + build.ps1 step-4e/preflight + README precondition
- [x] 88.3-02-PLAN.md — [wave 1] Revert the same-bundle changes: strip WebEngine hiddenimports from the conda spec, remove --check-webengine from __main__.py, drop build.ps1 step-0 preflight + step-4e, re-point the 5 drift-guards at B1 invariants (G6-T1..T5)
- [x] 88.3-03-PLAN.md — [wave 1] Rewire the frozen launch path to spawn the SEPARATE oauth_helper.exe (replacing 88.2's self-re-exec) + platform-aware _CHROME_UA so Twitch accepts the Windows login
- [x] 88.3-04-PLAN.md — [wave 2] Add the 2nd isolated-pip PyInstaller build (oauth-helper-requirements.txt + oauth_helper_standalone.spec), build.ps1 helper-build step + WebEngine assertion (exit 14), Inno ships both artifacts to {app}\oauth_helper\, README conda-free-Python-3.12 prereq
- [x] 88.3-05-PLAN.md — [wave 3, manual VM UAT] Build both artifacts on the Win11 VM, install via Inno, verify GBS.FM + Twitch + Google/YouTube logins open from the installed two-artifact build (G6-T6/T7/T8)

### Phase 88.2: Fix GBS.FM in-app login dialog fails to start (Phase 88 UAT G3) (INSERTED)

**Goal:** The in-app GBS.FM login (and identically Twitch + Google/YouTube) starts on the PyInstaller-frozen Windows build. Root cause fixed: the shared `sys.executable -m musicstreamer.oauth_helper` QProcess launch is silently ignored by the frozen exe; a `--oauth-helper` argv-dispatch in `__main__.py` + a frozen-safe `_make_oauth_launch_args` helper re-exec the login helper correctly. A FailedToStart never dead-ends (errorOccurred → log + cookie-import fallback), and a Linux static test + `build.ps1` exit-12 smoke guard lock the fix. (Linux/CI side; frozen-exe `--self-test` smoke + UAT-10 GBS.FM login re-test deferred to the consolidated 88-03 VM session per D-06/D-07.)
**Requirements**: VER-02-J
**Depends on:** Phase 88
**Plans:** 2 plans

Plans:
**Wave 1**

- [x] 88.2-01-PLAN.md — D-01 shared frozen-safe launcher (`_make_oauth_launch_args` + `__main__.py --oauth-helper` dispatch + 3 call-site rewires) + D-04 Linux frozen-dispatch test

**Wave 2** *(depends on 88.2-01)*

- [x] 88.2-02-PLAN.md — D-02/D-03 errorOccurred handlers (WR-03 reset + log + cookie-import fallback) + D-05 build.ps1 oauth-helper smoke guard (exit 12) + source-text drift-guard

### Phase 88.1: Fix SMTC media overlay absent and dead media keys on bundled Windows build (Phase 88 UAT G2) (INSERTED)

**Goal:** The bundled (PyInstaller-frozen) Windows build's SMTC media session registers correctly — the winrt compiled .pyd extensions are bundled via collect_all, backend selection is logged (no more silent NoOp degradation), and build-time + CI guards prevent regression. (Linux/CI side; frozen-exe smoke + UAT-3/UAT-7 re-test deferred to the consolidated 88-03 VM session per D-06/D-07.)
**Requirements**: WIN-02, VER-02-J
**Depends on:** Phase 88
**Plans:** 2 plans

Plans:

- [x] 88.1-01-PLAN.md — D-03 factory backend-selection logging + `--check-mediakeys` headless harness + SMTC factory-log test extensions
- [x] 88.1-02-PLAN.md — D-01/D-02 spec collect_all for 5 winrt distributions + D-05 build.ps1 SMTC smoke guard (exit 11) + D-04 Linux static drift-guard test

#### Phase 89a: Channel-Avatar DB Migration + Storage Layout

**Goal**: Foundation for both YT and Twitch avatar work — additive SQLite column + filesystem layout in place, idempotent and rollback-safe, with zero behavior change.
**Depends on**: Nothing inside v2.2 (parallel-eligible; Phase 89/89b consume it)
**Requirements**: ART-AVATAR-01, ART-AVATAR-02
**Success Criteria** (what must be TRUE):

  1. After upgrade, `PRAGMA table_info(stations)` shows the new `channel_avatar_path TEXT` column with NULL default for all existing rows; existing data unchanged.
  2. Migration is idempotent — running `db_init()` twice does not raise; rollback test confirms reverting + re-applying produces identical schema.
  3. `~/.local/share/musicstreamer/assets/channel-avatars/` directory exists with appropriate permissions and layout matching the existing `assets/` station-logo precedent.

**Plans**: 2 plans across 2 waves
Plans:
**Wave 1**

- [x] 89A-01-PLAN.md — paths.channel_avatars_dir() accessor + eager ensure_dirs() makedirs + accessor/purity/creation tests (ART-AVATAR-02)

**Wave 2** *(depends on 89A-01)*

- [x] 89A-02-PLAN.md — repo.py:db_init() additive channel_avatar_path TEXT ALTER after the stations_new rebuild + idempotency + schema-convergence tests (ART-AVATAR-01)

**Research flag**: NO — direct mirror of existing `station_art_path` / `album_fallback_path` migration pattern in `repo.py`.

#### Phase 87: GBS.FM Marquee + Themed-Day Detection

**Goal**: When the bound station is GBS.FM, the user sees the current themed logo (if any), a dismissible top-of-panel announcement banner, and a live updating marquee — all backed by the Phase 76 QtWebEngine cookie-persistence pattern that Phase 89 reuses for channel avatars.
**Depends on**: Nothing inside v2.2 (Phase 76 is the v2.1 keystone; this phase establishes the cookie-persistence pattern that Phase 89's cover-slot UI swap depends on)
**Requirements**: GBS-THEME-01, GBS-THEME-02, GBS-THEME-03, GBS-THEME-04, GBS-THEME-05, GBS-THEME-06, GBS-MARQ-01, GBS-MARQ-02, GBS-MARQ-03, GBS-MARQ-04, GBS-MARQ-05, GBS-MARQ-06, GBS-MARQ-07
**Success Criteria** (what must be TRUE):

  1. When the user binds a GBS.FM station on a known themed day (Halloween / Christmas / "da troops" / spooky / etc.), the now-playing logo slot displays the themed logo for the session — never the cover slot, never the station-list row, never a libnotify toast (GBS-THEME-05).
  2. Next app launch re-evaluates themed-day detection from scratch; the themed logo does NOT persist to SQLite or carry past a session boundary (GBS-THEME-04).
  3. When GBS.FM marquee text contains a new first pipe-segment announcement (hash-different from last-seen), a top-of-NowPlayingPanel banner appears with the announcement preserving `|` pipe wrap hints; user can dismiss with × and the same banner does not re-appear until the marquee changes.
  4. Marquee fetcher imports `paths.gbs_cookies_path()` + `musicstreamer.gbs_api.load_auth_context()`; source-grep drift-guard confirms no parallel cookie file is written and no QtWebEngine session is instantiated.
  5. 60-second poll cadence while GBS station bound + playing; 5-minute slow cadence otherwise; 10+ committed marquee fixtures plus 3+ themed-day / 5+ non-themed-day logo SHA-256 samples lock the parser and the canonical-hash table.

**Plans:** 7 plans (6 + 1 gap-closure)
Plans:
**Wave 1**

- [x] 87-01-PLAN.md — Live themed-day fixture harvest (Memorial Day window) + REQUIREMENTS/ROADMAP D-07/D-08 edits

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 87-02-PLAN.md — Marquee endpoint lock + parse_marquee + synthetic fixture corpus (GBS-MARQ-02/07)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 87-03-PLAN.md — GbsMarqueeWorker (QThread + cadence state machine + D-18 quiet-failure log sink, GBS-MARQ-01)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 87-04-PLAN.md — Themed-day correlator + logo slot override + MainWindow worker construction (GBS-THEME-01..05)

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 87-05-PLAN.md — AnnouncementBanner widget + dismissal-hash set + outer-VBox panel wrap (GBS-MARQ-03/04/05)

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 87-06-PLAN.md — Source-grep drift-guards + GBS-THEME-06 follow-up todo (GBS-MARQ-06 enforce, GBS-THEME-06 accrete)

**Wave 7** *(gap closure — UAT Test 2 fix)*

- [x] 87-07-PLAN.md — Resolve dynamic #leftmenulogo logo URL (imgur + img.gbs.fm/.../raw) from reused homepage bytes; re-baseline + CR-01 main-thread QPixmap (GBS-THEME-01..05)

**Research flag**: YES — `/gsd:plan-phase --research-phase 87` recommended (QtWebEngine cookie persistence cross-process, marquee delimiter ambiguity, themed-day hash baseline harvest).
**UI hint**: yes

### Phase 87.1: GBS.FM Session-Expiry Re-login Prompt (INSERTED)

**Goal:** When a GBS.FM session cookie has expired, the app surfaces a clear, actionable "GBS session expired — please log in again" prompt that launches the existing in-app GBS login (`oauth_helper --mode gbs`) and refreshes on success, instead of silently failing. **Observed symptom:** the active playlist would not load with no indication why; the user had to manually log out and back in to recover.

**Root cause / existing state:** Detection ALREADY exists — `gbs_api.py` raises `GbsAuthExpiredError` (`gbs_api.py:86`) on a `302 → /accounts/login/` redirect ("session cookie no longer authorizes"). The gap is HANDLING/UX: that exception is not surfaced to the user as a re-login prompt, so callers experience a silent load failure. This phase is NOT about detecting expiry (done) — it catches `GbsAuthExpiredError` at the GBS call sites and routes to a re-login affordance.

**Scope:**

- Catch `GbsAuthExpiredError` at the existing GBS call sites — primarily the active-playlist loader (`fetch_active_playlist`), plus vote/search/submit — and present a non-dismissive "session expired, re-login" prompt that launches the existing GBS login flow, then retries/refreshes on success.
- Provide a SHARED expiry→re-login handler that the Phase 87 `GbsMarqueeWorker` poller and the Phase 87b zero-token add can reuse (both call `gbs_api` with the same cookies and can hit the same `GbsAuthExpiredError`) — avoid each call site re-implementing error handling.
- No silent dead-ends: if the user cancels re-login, show a clear inline state, not an empty/failed load.

**Depends on:** Phase 87 (reuse by the marquee poller; the shared handler should be available to 87's `GbsMarqueeWorker`). GBS auth infra (`gbs_api`, `oauth_helper --mode gbs`, `paths.gbs_cookies_path`) already exists, so the playlist-load symptom fix can land independently. GBS cluster (Tier 5), pairs with 87/87b.
**Requirements**: GBS-AUTH-EXP-01 (surface expiry as re-login prompt at playlist load), GBS-AUTH-EXP-02 (shared handler reused by marquee + zero-token), GBS-AUTH-EXP-03 (no silent dead-end on cancel) — finalize during discuss/plan.
**Note:** Planned milestone feature (not a hotfix); the `(INSERTED)` marker is the tool default. Origin: user-reported symptom 2026-06-12.
**Plans:** 5 plans across 4 waves

Plans:
**Wave 1** *(parallel — disjoint files)*

- [x] 87.1-01-PLAN.md — Shared GbsReloginHandler QObject: single-flight oauth_helper launch + cookie write (0o600) + relogin_succeeded/relogin_failed signals (GBS-AUTH-EXP-02)
- [x] 87.1-02-PLAN.md — GbsMarqueeWorker.auth_expired signal feeding the shared handler (GBS-AUTH-EXP-02)

**Wave 2** *(blocked on Wave 1)*

- [x] 87.1-03-PLAN.md — Inline non-dismissive expiry prompt in now_playing_panel + relogin slots + poll resume + marquee QueuedConnection wiring (GBS-AUTH-EXP-01/02/03)

**Wave 3** *(GAP CLOSURE — fixes detection that the inline prompt depends on; blocked on Waves 1-2)*

- [x] 87.1-04-PLAN.md — Fix _open_with_cookies to actually raise GbsAuthExpiredError on 302→/accounts/login/ (default redirect handler was auto-following it → dead-code detection); real-redirect regression test + marquee audit (GBS-AUTH-EXP-01, gap closure from 87.1-HUMAN-UAT)

**Wave 4** *(GAP CLOSURE — gates the oauth_helper launch behind the user's button click; blocked on Waves 1-3)*

- [x] 87.1-05-PLAN.md — Separate detection from launch: detection (playlist error + marquee auth_expired) reveals the inline prompt only; oauth_helper launches solely on the "Log in again" click; dual-path no-auto-launch regression test (GBS-AUTH-EXP-01/02/03, gap closure from 87.1-HUMAN-UAT Test 1)

#### Phase 89: YouTube Channel-Avatar Fetch + Cover-Slot Swap

**Goal**: ICY-disabled YouTube stations (e.g., Lofi Girl) show the channel avatar (circular crop) in the cover slot instead of duplicating the station thumbnail; cover-resolver precedence keeps Phase 73 MB-CAA above the new avatar fallback.
**Depends on**: Phase 89a (DB migration + storage layout), Phase 87 (QtWebEngine cookie-persistence pattern established for cover-slot UI swap)
**Requirements**: ART-AVATAR-03, ART-AVATAR-05, ART-AVATAR-06, ART-AVATAR-07, ART-AVATAR-08, ART-AVATAR-09, ART-AVATAR-10
**Success Criteria** (what must be TRUE):

  1. When the user pastes a YouTube channel/video URL into `EditStationDialog`, `yt_import.fetch_channel_avatar()` populates a square channel avatar (filtered to `thumbnails[].id == 'avatar_uncropped'` or `'avatar'`, rejecting `width != height` entries) within 1 second of station-bind on a cached station (Pitfall 7 mitigated).
  2. When ICY metadata is disabled for a YT station with a stored channel avatar, the now-playing cover slot displays the avatar with circular crop instead of duplicating the station thumbnail; failure-to-fetch falls back cleanly to placeholder or station thumbnail (Pitfall 8 mitigated).
  3. Cover-resolver source order is `ICY → iTunes → MB-CAA → channel-avatar → placeholder`; source-grep drift-guard `test_cover_resolution_precedence::test_mb_caa_runs_before_channel_avatar` confirms `_mb_caa_lookup` appears in source before `_channel_avatar_lookup` (Pitfall 8 / Vaporwave-niche-electronic coverage preserved).
  4. Phase 71 sibling-line rendering parity preserved — drift-guard `test_richtext_baseline_unchanged_by_phase_89` mirrors the existing Phase 71 baseline test (Pitfall 13 mitigated).
  5. `EditStationDialog` surfaces a "Refresh avatar" button so the user can manually re-fetch after a channel rebrand; auto-fetch on URL paste matches the Phase 6/17 YT-thumbnail UX precedent.

**Plans**: 5 plans

Plans:
**Wave 1**

- [x] 89-01-PLAN.md — Thread channel_avatar_path through models/repo + atomic avatar PNG writer (D-12/D-13)
- [x] 89-02-PLAN.md — yt_import.fetch_channel_avatar (avatar_uncropped filter) + per-provider registry (D-04)
- [x] 89-03-PLAN.md — cover_art.py named precedence wrappers + source-grep drift-guards (ART-AVATAR-07/09/10)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 89-04-PLAN.md — now_playing_panel circular-avatar render path + tier-replay + bind-time load (ART-AVATAR-06/08)
- [x] 89-05-PLAN.md — EditStationDialog debounced auto-fetch + Refresh button + atomic persist (ART-AVATAR-05)

**Research flag**: YES — `/gsd:plan-phase --research-phase 89` recommended (yt-dlp channel-avatar field stability spike, sibling-rendering regression risk).
**UI hint**: yes

### Phase 89.1: Re-key channel avatar from per-station to per-provider (INSERTED)

**Goal:** Phase 89 stores `channel_avatar_path` on each Station row (`assets/channel-avatars/{station_id}.png`), so every stream of the same YouTube channel (e.g. multiple Lofi Girl streams) fetches and stores the identical avatar. For YouTube imports the provider IS the channel (`yt_import.py:120` sets provider = `playlist_channel`/`playlist_uploader`/`uploader`; `providers.name` is UNIQUE). Move the avatar to the Provider: add `avatar_path` to the `providers` table, key the cached PNG by `provider_id`, persist via a provider-keyed update method, and resolve it in `now_playing_panel.bind_station` and `EditStationDialog` via the station's `provider_id` so all sibling streams reuse one fetch and one file. Fall back to the station thumbnail when `provider_id` is null. Migrate the existing per-station avatars and deprecate the old `stations.channel_avatar_path` column. Goal: one avatar fetch + one cached file per channel instead of per station.
**Requirements**: D-01..D-11 (CONTEXT.md locked decisions; no formal ROADMAP requirement IDs assigned — decisions are the authoritative requirement set)
**Depends on:** Phase 89
**Plans:** 2 plans across 2 waves

Plans:
**Wave 1** *(data layer)*

- [x] 89.1-01-PLAN.md — providers.avatar_path ALTER + idempotent crash-safe backfill (D-01/02/03/11) + write_provider_avatar + update_provider_avatar_path (D-09/10) + Station.provider_avatar_path field + four-mapper carry + write-path cutover (D-04) + Wave-0 migration/backfill/persist tests

**Wave 2** *(consumers — blocked on 89.1-01)*

- [x] 89.1-02-PLAN.md — cover_art._channel_avatar_lookup + now_playing_panel.bind_station repoint to provider_avatar_path with file-existence guard (D-04/05/06) + EditStationDialog reuse-on-open / force-refresh bypass / provider-keyed persist+write / shared-effect hint (D-07/08) + lookup-test re-point

**Research flag**: NO — direct re-key of the existing Phase 89 mechanism mirroring Phase 89A/89 patterns; RESEARCH/PATTERNS already mapped every analog.

#### Phase 89b: Twitch Channel-Avatar Fetch

**Goal**: ICY-disabled Twitch stations show the streamer's Helix `profile_image_url` (circular crop) in the cover slot, sharing the Phase 89 cover-slot integration and the Phase 89a storage layout.
**Depends on**: Phase 89a (DB migration + storage layout), Phase 89 (cover-slot UI swap path)
**Requirements**: ART-AVATAR-04
**Success Criteria** (what must be TRUE):

  1. `musicstreamer/twitch_helix.py` calls `GET https://api.twitch.tv/helix/users?login=<x>` with the existing Phase 32 `twitch-token.txt` user token (no new OAuth scopes) and stores `profile_image_url` bytes to `~/.local/share/musicstreamer/assets/channel-avatars/<provider-id>.png` (per-provider key — supersedes the original `<station-id>.png` wording per Phase 89.1 / CONTEXT D-01).
  2. When a Twitch station has ICY disabled and a stored Twitch avatar, the cover slot displays the avatar via the same circular-crop path as Phase 89 (zero new UI code; integration is a per-provider auto-fetch trigger only).
  3. Helix rate-limit budget is preserved — avatar fetched once per station-create/edit, then cached indefinitely with a manual "Refresh avatar" affordance (no per-play refresh).

**Plans**: 3 plans

- [x] 89B-01-PLAN.md — New `musicstreamer/twitch_helix.py` (`fetch_channel_avatar` via Helix `/users`, Bearer + Client-Id, login parse) + register into the per-provider avatar registry (Wave 1)
- [x] 89B-02-PLAN.md — EditStationDialog: twitch.tv URL detection + Refresh gate, `_AvatarFetchWorker` registry dispatch, blank-only `Twitch: <login>` provider derivation on save (Wave 2)
- [x] 89B-03-PLAN.md — Gap closure: refresh in-memory provider_id/provider_name + synchronous fetch-and-persist of the Twitch avatar in `_on_save` before `accept()` so a NEW Twitch station fetches its avatar on FIRST save (UAT add-path gap) (Wave 1)

**Research flag**: NO — Helix `/users` is a single GET, pattern is well-established in `aa_live.py` and elsewhere.

#### Phase 89c (INSERTED): Provider Brand-Avatar Cover-Slot Fallback (SomaFM, AudioAddict)

**Goal**: When per-track cover-art resolution is exhausted for an ICY-metadata provider whose track art frequently misses (SomaFM, AudioAddict/DI.FM), the now-playing cover slot shows a distinct provider brand avatar (circular crop) instead of duplicating the station logo already shown in the left logo slot. Trigger is **cover-resolution-exhausted** — the `if not path:` fallback branch in `now_playing_panel.py:2136` that currently calls `_show_station_logo_in_cover_slot` — **NOT `icy_disabled`**; this is the defining difference from Phase 89/89b, which swap on `icy_disabled`.
**Depends on**: Phase 89 (cover-slot swap + circular-crop rendering + cover-resolver precedence)
**Requirements**: ART-AVATAR-11, ART-AVATAR-12
**Success Criteria** (what must be TRUE):

  1. A provider brand-avatar registry keyed on `provider_name` (bundled assets for SomaFM and AudioAddict; no per-station DB fetch like Phase 89a) resolves a distinct brand image for stations of those providers.
  2. When per-track cover-art resolution is exhausted (the `now_playing_panel.py:2136` `if not path:` branch) for a station whose `provider_name` has a registered brand avatar, the cover slot renders the provider brand avatar with circular crop instead of the station logo; the left logo slot is unchanged, so the same image is never shown on both panels (the Drone Zone duplicate-logo complaint).
  3. GBS.FM is excluded by intent — it is a single-station provider where the duplicated logo (left + cover slot) reads as goofy-but-on-brand for the GBS aesthetic, so it keeps current behavior and no brand avatar is registered for it. (Note: the Phase 87 themed-logo override only touches `logo_label`, NOT the cover slot, so GBS would otherwise duplicate too — exclusion is a deliberate vibe choice, not because GBS is already distinct.)
  4. Stations of providers WITHOUT a registered brand avatar keep current behavior (station logo → generic icon); no regression to the `_show_station_logo_in_cover_slot` path.
  5. Source-grep drift-guard pins that the provider-avatar lookup fires only on the resolution-exhausted branch (after iTunes/MB-CAA), never short-circuiting Phase 73 MB-CAA per-track coverage.

**Plans**: 3 plans
Plans:

- [x] 89c-01-PLAN.md — Registry module + asset dir + now_playing_panel wiring + drift-guards + PyInstaller datas
- [x] 89c-02-PLAN.md — EditStationDialog "Choose brand image…" upload override (D-09/D-09a)
- [x] 89c-03-PLAN.md — Gap closure: _populate() refresh avatar preview on dialog open (reuse-on-open, D-07; UAT Test 5)

**Research flag**: NO — reuses Phase 89 cover-slot swap + circular-crop rendering; source is bundled provider assets, no new network fetch.
**UI hint**: yes

#### Phase 87b: GBS Zero-Token Single-Song Add

**Goal**: The now-playing panel renders a persistent "Add a song" button whenever the bound station is GBS.FM and the user is logged in (any token count). The button opens the existing GBS search-drill-down dialog; confirming a song adds it via `gbs_api.add_song_zero_token()`. UX never frames the action as a token grant.
**Depends on**: Phase 87 (GBS marquee infrastructure; zero-token UI is independent of token-count state — D-05 reframe)
**Requirements**: GBS-TOKEN-01, GBS-TOKEN-02, GBS-TOKEN-03, GBS-TOKEN-04, GBS-TOKEN-05
**Success Criteria** (what must be TRUE):

  1. Button renders whenever `provider_name == "GBS.FM"` AND the user is logged in, regardless of token count or queue state (AMENDED per 87B-CONTEXT D-05 — supersedes the original tokens==0+queue==0 gating).
  2. UI text (label, tooltip, surrounding copy) never contains the word "token" — source-grep test on the new module enforces this; exact wording is "Add a song" / "Add a song to the GBS.FM queue".
  3. Activating the button opens the existing Phase 60.1/60.2 GBS search-drill-down dialog; confirming a song calls `gbs_api.add_song_zero_token()` which posts to the provisional /add reuse endpoint (server-gated per D-02 — not a separately-observed one-shot endpoint).
  4. The button persists after a successful add (no hide); post-add behavior is dialog-close + now-playing GBS playlist re-poll via `trigger_gbs_repoll()` (AMENDED per 87B-CONTEXT D-08 — supersedes the original hide/re-appear gating).
  5. The observable /add shape is fixture-locked under `tests/fixtures/gbs_zero_token/` now (provisional 48-token capture); the real tokens==0 fixture is captured on first live use via the no-PII capture hook and confirmed via the capture-on-use follow-up todo (AMENDED per 87B-CONTEXT D-03 — defers live tokens==0 observation to capture-on-use).

**Plans**: 2 plans

- [x] 87B-01-PLAN.md — Backend: add_song_zero_token() wrapper + no-PII capture hook + provisional fixtures + GBS-TOKEN-02 drift-guard + unit tests (Wave 1)
- [x] 87B-02-PLAN.md — UI: persistent 'Add a song' button + visibility + trigger_gbs_repoll wiring + worker call-site + docs amendment + capture-on-use todo (Wave 2)

**Research flag**: NO — research happens inside Phase 87 spike; Phase 87b consumes it.
**UI hint**: yes

#### Phase 90: SomaFM Preroll Instrumentation

**Goal**: Wire a non-destructive structured preroll event log + a prerolls re-fetch lever through `player.py`'s SomaFM preroll path so the user can confirm — via a manual all-stations run-through cross-checked against `preroll-events.log` — that the reported missing-preroll symptom (Boot Liquor) is resolved, and so any future recurrence is both legible (logged) and recoverable (re-fetch). REFRAMED 2026-06-18 (see 90-CONTEXT.md, authoritative): empirical verification showed Boot Liquor already resolved at the data+logic layer; the opt-in 30s network probe (SOMA-PRE-03) and the 1-2 day passive harvest (SOMA-PRE-04 harvest half) are DEFERRED to conditional Phase 90b. Building the fix for a still-broken station is Phase 90b, not this phase.
**Depends on**: Nothing inside v2.2 (parallel-eligible; carry-over investigation)
**Requirements**: SOMA-PRE-01, SOMA-PRE-02, SOMA-PRE-03, SOMA-PRE-04, SOMA-PRE-05
**Success Criteria** (what must be TRUE — REFRAMED per 90-CONTEXT.md; supersedes original probe/harvest criteria):

  1. New `musicstreamer/preroll_log.py` writes size-rotated structured events (`preroll_start` incl. chosen URL, `preroll_skipped_throttle`, `preroll_skipped_empty`, `preroll_handoff_complete`; `preroll_error` reserved) to `~/.local/share/musicstreamer/preroll-events.log`; hamburger-menu "Open preroll log" surfaces it (net-new UI — no existing buffer-log entry to mirror).
  2. Instrumentation adds at `_try_next_stream` + `_on_preroll_about_to_finish` decision boundaries with zero behavior change; Phase 84 D-11 acceptance test (12-event replay, `tests/test_player_buffer_growth.py`) re-runs clean before merge; source drift-guard pins `_set_uri` ordering (SOMA-PRE-05).
  3. Recovery lever (D-07/D-08): a manual "Re-fetch SomaFM prerolls" hamburger action + automatic staleness re-fetch close the latent "fetched-with-0 never re-fetches" trap; re-fetch reuses single-flight + Pattern-4 thread-local Repo + scheme-validated `insert_preroll`.
  4. `random.choice(urls)` selection is UNCHANGED (D-06); the logged chosen-URL is the run-through's per-bind rotation/reachability evidence.
  5. SOMA-PRE-04 verify half is satisfied by the structured log + a user-owned manual all-stations run-through; SOMA-PRE-03 (30s probe) + the passive harvest half are DEFERRED to conditional Phase 90b.

**Plans**: 3 plans
Plans:
**Wave 1**

- [x] 90-01-PLAN.md — Logging substrate: preroll_log.py + paths.preroll_events_log_path() + __main__ install + test mirror (Wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 90-02-PLAN.md — Wire additive preroll log calls into player.py gate+handoff + D-08 auto-staleness re-fetch; D-11 regression gate (Wave 2)
- [x] 90-03-PLAN.md — Hamburger UI: "Open preroll log" + "Re-fetch SomaFM prerolls" (_PrerollRefetchWorker) (Wave 2)

**Research flag**: NO — Phase 78/84 ship+monitor pattern is the established template.

#### Phase 90b (CONDITIONAL): SomaFM Preroll Fix

**Goal**: Ship the fix Phase 90's harvest identified — only if the root cause is clear, atomic, and within the v2.2 dev window.
**Depends on**: Phase 90 (harvest data — fires only if root cause clear)
**Requirements**: (closes the SOMA-PRE-04 trigger half; no requirements unique to this phase)
**Success Criteria** (what must be TRUE):

  1. The fix targets exactly one root cause from Phase 90's hypothesis space (catalog gap, stream-URL pattern mismatch, `_preroll_in_flight` flag race, 10-minute throttle window cross-station leakage) — never speculative multi-cause refactor.
  2. After the fix, the target station (Boot Liquor) plays a preroll on bind via the same harvest probe that previously logged the miss; Groove Salad / Drone Zone / Beat Blender continue to play prerolls (no regression).
  3. Phase 90 instrumentation remains in place post-fix for at least one further monitor week so a re-occurrence would surface.

**Plans**: TBD
**Research flag**: NO — fix scope is constrained by the harvest data.
**Condition**: Fires only if Phase 90's harvest identifies a clear, atomic root cause for at least one missing-preroll station per SOMA-PRE-04 criterion.

#### Phase 92: FIX-PLS — PLS URL-Fallback for Codec/Bitrate

**Goal**: When a PLS file's title field lacks codec/bitrate info, the resolver inspects the resolved stream URL pattern (e.g., AudioAddict `_aac` / `_mp3` suffixes) to populate the missing fields — closing the Phase 58 pending-todo carry-over.
**Depends on**: Nothing inside v2.2 (small, slot-in any week)
**Requirements**: FIX-PLS-01
**Success Criteria** (what must be TRUE):

  1. When `pls.resolve()` returns a stream with empty codec/bitrate AND the resolved URL contains a recognized suffix (`_aac`, `_mp3`, `_aacp`, etc.), the resolver populates the missing fields from the URL pattern; existing PLS-title-derived metadata still wins when present.
  2. AudioAddict + Radio-Browser + other PLS-sourced stations that previously had blank codec/bitrate now show populated values in `station_streams` after a re-import or refresh.
  3. Stream-ordering correctness (`stream_ordering._CODEC_RANK`) is preserved — codec rank still wins over bitrate, lossless stays above lossy.

**Plans**: 1 plan
**Research flag**: NO — direct extension of Phase 58 logic.

Plans:
- [x] 92-01-PLAN.md — URL-fallback for _extract_codec/_extract_bitrate (title miss -> scan entry URL) + 3 call sites + 4 RED->GREEN tests

#### Phase 93 (CONDITIONAL): BUFFER-MONITOR Follow-Up

**Goal**: Resolve any of Phase 84-VERIFICATION.md's 3 Follow-Up Triggers that fire during the v2.2 development window — diagnose, tune, or formally close as "no action".
**Depends on**: Phase 84 (v2.1) — fires only on trigger
**Requirements**: MON-BUFFER-01
**Success Criteria** (what must be TRUE):

  1. Which of the 3 Follow-Up Triggers (BUG-09 recurrence, statistical-gate signal change, user-reported drop-out) fired is documented with timestamps + observed evidence; non-fired triggers are explicitly noted as "no action required".
  2. Phase outcome is one of: (a) adaptive-buffer regression diagnosis + fix, (b) further state-machine tuning of the 30→60→120s growth ladder, (c) explicit "no action — closed" verification with evidence.
  3. If a fix ships, Phase 84 D-11 acceptance test (12-event harvest replay) re-runs clean post-fix; if "no action — closed", the buffer-events.log monitor concludes with the documented baseline preserved.

**Plans**: TBD
**Research flag**: NO — Phase 84 closure record + 84-VERIFICATION.md are the canonical reference.
**Condition**: Fires only if any of Phase 84-VERIFICATION.md's 3 Follow-Up Triggers fires during the v2.2 dev window. Skips entirely otherwise.

### Progress Table (v2.2)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 85a. Linux Packaging Spike | 8/8 | Complete    | 2026-05-26 |
| 91. FIX-MPRIS | 1/1 | Complete | 2026-06-02 |
| 85. Linux Common + AppImage Build | 4/4 | Complete   | 2026-06-01 |
| 86. Linux Flatpak Build | 5/5 | Complete   | 2026-06-09 |
| 86.1. SC5 Failure Follow-up (INSERTED) | 2/2 | Complete   | 2026-06-04 |
| 88. Windows Packaging Bundle | 4/4 | Complete | 2026-06-13 |
| 88.3. Bundle QtWebEngine (G6) (INSERTED) | 5/5 | Complete   | 2026-06-13 |
| 88.2. Fix GBS Login Start (G3) (INSERTED) | 2/2 | Complete   | 2026-06-09 |
| 88.1. Fix SMTC + Media Keys (G2) (INSERTED) | 2/2 | Complete   | 2026-06-09 |
| 89a. Channel-Avatar DB Migration | 2/2 | Complete   | 2026-06-13 |
| 87. GBS Marquee + Themed-Day | 7/7 | Complete    | 2026-06-15 |
| 87.1. GBS Session-Expiry Re-login (INSERTED) | 5/5 | Complete    | 2026-06-18 |
| 89. YT Channel-Avatar | 5/5 | Complete    | 2026-06-16 |
| 89.1. Re-key Avatar Per-Provider (INSERTED) | 2/2 | Complete    | 2026-06-16 |
| 89b. Twitch Channel-Avatar | 3/3 | Complete   | 2026-06-17 |
| 89c. Provider Brand-Avatar Fallback (INSERTED) | 3/3 | Complete   | 2026-06-17 |
| 87b. GBS Zero-Token Add | 2/2 | Complete   | 2026-06-18 |
| 90. SomaFM Preroll Instrumentation | 3/3 | Complete    | 2026-06-18 |
| 90b. SomaFM Preroll Fix (CONDITIONAL) | 0/? | Not started | - |
| 92. FIX-PLS | 1/1 | Complete   | 2026-06-18 |
| 93. BUFFER-MONITOR (CONDITIONAL) | 1/1 | Complete (deviation close) | 2026-06-15 |
| 94. Sidebar Logo Thumbnail Optimization | 3/3 | Complete    | 2026-06-15 |
| 95. YT URL-Change Replay Bug | 2/2 | Complete   | 2026-06-19 |

### Dependency Graph (Tier Summary)

```
Tier 1 (parallel-eligible, Week 1):
  Phase 85a (Linux Spike)  ────┐
  Phase 91 (FIX-MPRIS)     ────┤
                                │
Tier 2 (sequential, Weeks 2-3): │
  Phase 85a ──> Phase 85 (Linux Common + AppImage)
  Phase 91  ──> Phase 86 (Linux Flatpak — needs MPRIS baseline clean)

Tier 3 (Week 4, one Win11 VM session):
  Phase 88 (Windows Bundle — parallel-eligible w/ Tiers 1-2)

Tier 4 (Week 5+, channel-avatar infrastructure):
  Phase 89a (DB Migration) ──> Phase 89 (YT Avatar) ──> Phase 89.1 (Re-key Per-Provider) ──> Phase 89b (Twitch Avatar)
                                  ▲
                                  └── Phase 87 also precedes Phase 89 (cookie-persistence pattern)

Tier 5 (Week 6, GBS polish):
  Phase 87 (GBS Marquee/Themed) ──> Phase 87b (Zero-Token Add)

Tier 6 (Week 7, SomaFM):
  Phase 90 (Preroll Instrumentation) ──> Phase 90b (CONDITIONAL Fix)

Tier 7 (carry-overs, slot-in):
  Phase 92 (FIX-PLS) — independent
  Phase 93 (CONDITIONAL BUFFER-MONITOR) — trigger-gated; FIRED + closed 2026-06-15
```

### Coverage Summary (v2.2)

| Requirement Family | Count | Phase Assignment |
|--------------------|-------|------------------|
| PKG-LIN-APP (AppImage) | 9 | Phase 85 |
| PKG-LIN-FP (Flatpak) | 10 | Phase 86 |
| WIN bundle (WIN-02 + variants + VER-02-J + WIN-05) | 5 | Phase 88 |
| GBS-THEME | 6 | Phase 87 |
| GBS-MARQ | 7 | Phase 87 |
| GBS-TOKEN | 5 | Phase 87b |
| ART-AVATAR | 10 | Phase 89a (01–02), Phase 89 (03, 05–10), Phase 89b (04) |
| SOMA-PRE | 5 | Phase 90 |
| FIX-MPRIS | 3 | Phase 91 |
| FIX-PLS | 1 | Phase 92 |
| MON-BUFFER (CONDITIONAL) | 1 | Phase 93 |

**Total v2.2 requirements:** 62 (61 unconditional + 1 conditional)
**Mapped:** 62/62 ✓
**Orphans:** 0 ✓
**Double-mapped:** 0 ✓

### Phase 94: Optimize sidebar logo loading with pre-scaled thumbnails for large station lists

**Goal:** Sidebar scrolling on large station lists (DI.fm-scale) stays smooth on the first pass by rendering pre-scaled 96px logo thumbnails, generated lazily off the UI thread on cache/file miss, while the full-res station_art continues to feed the Now Playing panel unchanged.
**Requirements**: D-01, D-02, D-03, D-04, D-05, D-06 (CONTEXT.md locked decisions)
**Depends on:** Phase 92
**Plans:** 3 plans

Plans:

**Wave 1**

- [x] 94-01-PLAN.md — Wave 0 test scaffolding: 9 RED tests across test_art_paths.py + test_station_thumb_async.py encoding D-01..D-06

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 94-02-PLAN.md — _art_paths.py: thumb helpers + off-UI-thread _generate_thumb worker + load_station_icon fast path (D-02/D-04/D-05/D-06)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 94-03-PLAN.md — station_tree_model.py: Signal + dedup + index lookup + _on_thumb_landing slot + data() wiring (D-01/D-03)

### Phase 95: YT URL-change replay bug: post-edit 'stream exhausted' on first play, second play picks up new URL

**Goal:** First play after editing a station's stream URL always uses the saved URL (no "stream exhausted"), by invalidating the Player's stale cached state (`_streams_queue`/`_current_stream`/loaded URI/in-flight YouTube resolution) on edit and restarting immediately when the actively-playing stream's URL changed (D-01..D-05). No spurious "Stream exhausted" toast flashes during the edit->restart transition (a stale pre-restart error-recovery from the OLD exhausted stream is suppressed).
**Requirements**: none mapped (TBD); behavior contract is D-01..D-05 in 95-CONTEXT.md
**Depends on:** Phase 94
**Plans:** 2 plans

Plans:

- [x] 95-01-PLAN.md — Player.invalidate_for_edit + YT resolve-seq guard + MainWindow edit-junction wiring (TDD, 3 tasks)
- [x] 95-02-PLAN.md — gap closure: _recovery_seq generation guard on the error-recovery path, suppressing the stale pre-restart "Stream exhausted" toast (TDD, 2 tasks)

### Phase 97: Resolve station URL duplication between the top-level standard URL (originally THE stream URL, now used for fetching/metadata) and the first StationStream URL — the two are expected to always be identical, causing the same URL to be maintained in two places and forcing duplicate edits. Investigate the data model and edit flow and unify to a single source of truth.

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 96
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 97 to break down)

---

## Historical Phases (Collapsed)

<details>
<summary>✅ v1.0 MVP (Phases 1–4) — SHIPPED 2024-03-20</summary>

- [x] Phase 1: Module Extraction (3/3 plans) — completed 2024-03-18
- [x] Phase 2: Search and Filter (2/2 plans) — completed 2024-03-19
- [x] Phase 3: ICY Metadata Display (2/2 plans) — completed 2024-03-20
- [x] Phase 4: Cover Art (1/1 plan) — completed 2024-03-20

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Polish & Station Management (Phases 5–6) — SHIPPED 2024-03-21</summary>

- [x] Phase 5: Display Polish (2/2 plans) — completed 2024-03-21
- [x] Phase 6: Station Management (2/2 plans) — completed 2024-03-21

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2 Station UX & Polish (Phases 7–11) — SHIPPED 2024-03-25</summary>

- [x] Phase 7: Station List Restructuring (3/3 plans) — completed 2024-03-22
- [x] Phase 8: Filter Bar Multi-Select (2/2 plans) — completed 2024-03-22
- [x] Phase 9: Station Editor Improvements (2/2 plans) — completed 2024-03-23
- [x] Phase 10: Now Playing & Audio (2/2 plans) — completed 2024-03-24
- [x] Phase 11: UI Polish (1/1 plan) — completed 2024-03-25

Full details: `.planning/milestones/v1.2-ROADMAP.md`

</details>

<details>
<summary>✅ v1.3 Discovery & Favorites (Phases 12–15) — SHIPPED 2024-04-03</summary>

- [x] Phase 12: Favorites (2/2 plans) — completed 2024-03-31
- [x] Phase 13: Radio-Browser Discovery (2/2 plans) — completed 2024-04-01
- [x] Phase 14: YouTube Playlist Import (2/2 plans) — completed 2024-04-02
- [x] Phase 15: AudioAddict Import (2/2 plans) — completed 2024-04-03

Full details: `.planning/milestones/v1.3-ROADMAP.md`

</details>

<details>
<summary>✅ v1.4 Media & Art Polish (Phases 16–20) — SHIPPED 2024-04-05</summary>

- [x] Phase 16: GStreamer Buffer Tuning (1/1 plan) — completed 2024-04-03
- [x] Phase 17: AudioAddict Station Art (2/2 plans) — completed 2024-04-03
- [x] Phase 18: YouTube Thumbnail 16:9 (1/1 plan) — completed 2024-04-05
- [x] Phase 19: Custom Accent Color (2/2 plans) — completed 2024-04-05
- [x] Phase 20: Playback Controls & Media Keys (2/2 plans) — completed 2024-04-05

Full details: `.planning/milestones/v1.4-ROADMAP.md`

</details>

<details>
<summary>✅ v1.5 Further Polish (Phases 21–34) — SHIPPED 2026-04-10</summary>

- [x] Phase 21: Panel Layout Fix (1/1 plan) — completed 2026-04-10
- [x] Phase 22: Import YT Cookies (3/3 plans) — completed 2026-04-07
- [x] Phase 23: Fix YT Playback (cookies) (1/1 plan) — completed 2026-04-07
- [x] Phase 24: Tag Chip FlowBox (1/1 plan) — completed 2026-04-08
- [x] Phase 25: Filter Chip Overflow (1/1 plan) — completed 2026-04-08
- [x] Phase 26: Edit Button Fix (1/1 plan) — completed 2026-04-08
- [x] Phase 27: Multi-Stream Model (3/3 plans) — completed 2026-04-08
- [x] Phase 28: Stream Failover (2/2 plans) — completed 2026-04-09
- [x] Phase 29: Hamburger Menu Consolidation (1/1 plan) — completed 2026-04-09
- [x] Phase 30: Elapsed Time Counter (1/1 plan) — completed 2026-04-09
- [x] Phase 31: Twitch via Streamlink (2/2 plans) — completed 2026-04-09
- [x] Phase 32: Twitch OAuth Token (2/2 plans) — completed 2026-04-10
- [x] Phase 33: YT 15s Wait + Toast (2/2 plans) — completed 2026-04-10
- [x] Phase 34: Deferred Items from Phase 33 (1/1 plan) — completed 2026-04-10

Full details: `.planning/milestones/v1.5-ROADMAP.md`

</details>

<details>
<summary>✅ v2.0 OS-Agnostic Revamp (Phases 35–48) — SHIPPED 2026-04-25</summary>

Full details: `.planning/milestones/v2.0-ROADMAP.md`
Audit: `.planning/milestones/v2.0-MILESTONE-AUDIT.md`

</details>

<details>
<summary>✅ v2.1 Fixes and Tweaks (Phases 49–84) — SHIPPED 2026-05-25</summary>

Full details: `.planning/milestones/v2.1-ROADMAP.md`
Audit: `.planning/milestones/v2.1-MILESTONE-AUDIT.md`
Phase directories: `.planning/milestones/v2.1-phases/`

</details>

## Backlog

(Items deferred during v2.1, awaiting promotion via `/gsd:review-backlog` if/when scope opens.)

### Phase 999.1: Friendlier settings-import error for text-mode-corrupted zips (BACKLOG)

**Goal:** When a settings backup `.zip` fails to open (`zipfile.BadZipFile` in `settings_export.preview_import`, currently the generic "Not a valid ZIP archive"), detect the signature of a text-mode/CRLF-corrupted transfer (starts with `PK` zip magic but raises `BadZipFile`, with injected `0x0D 0x0A` runs) and surface an actionable message: "This backup looks corrupted by a text-mode file transfer. Re-copy it in binary mode and try again." Scope is DETECTION + GUIDANCE ONLY — no auto-repair (collapsing `0x0D0A`→`0x0A` would clobber legitimate binary byte pairs = data-loss footgun). Origin: Phase 88 Win11 VM UAT Gap G4 (Linux→Windows backup failed import; root cause was the VM share transferring in text mode, not a build defect). Export/import code is OS-agnostic stdlib `zipfile`; this is purely UX/error-clarity. Likely a small change in `musicstreamer/settings_export.py:256-258`. Non-blocking enhancement.
**Requirements:** TBD
**Plans:** 0 plans

Plans:

- [ ] TBD (promote with /gsd:review-backlog when ready)
