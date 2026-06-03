---
status: human_completed
phase: 86-linux-flatpak-build
plan: 86-05
source: [86-05-PLAN.md]
created: 2026-06-02
updated: 2026-06-03
result: SC1-SC4 PASS, SC5 FAIL (follow-up planned)
---

# Phase 86 — Flatpak In-Sandbox UAT Evidence Bundle

> **Status: UAT completed 2026-06-03.** SC1–SC4 PASS, SC5 FAIL (two app-logic defects → follow-up plan).
> Getting to a working bundle required fixing **6 packaging/manifest defects** invisible to the
> 52 automated tests (they only surface at runtime inside the sandbox) plus one environmental issue.
> See "UAT session findings" below.

## UAT session findings (2026-06-03)

### Defects found & fixed (build-blocking → BUILD_OK)
1. **python3-pillow** — only module pulling an sdist; pillow 12.x needs `pybind11` at build
   time, unavailable under `--no-build-isolation`. Pillow is unused (zero `import PIL`, not a
   transitive dep). Removed from `flatpak-requirements.txt` + `python3-modules.yaml`.
2. **musicstreamer module** — `pip3 install` lacked `--no-build-isolation`, so pip tried to
   fetch `setuptools` from PyPI in the network-less build sandbox. Added the flag (SDK ships
   setuptools≥68).
3. **appstreamcli gate** — `build.sh` ran full networked validation; metainfo URLs (repo +
   screenshot) aren't published yet → `url-not-reachable` failed the build. Added `--no-net`
   for `SKIP_SIGN=1` local builds; signed/CI/release keep full validation.

### Defects found & fixed (functional, in-sandbox UAT)
4. **SC4 MPRIS2 name case mismatch** — manifest/test/RESEARCH used `--own-name=…MediaPlayer2.MusicStreamer`
   (capital) but the app registers `…MediaPlayer2.musicstreamer` (lowercase, `mpris2.py:56`).
   Case-sensitive D-Bus ownership → media keys silently disabled in-sandbox. Fixed manifest +
   drift guard now cross-checks `--own-name` against source `SERVICE_NAME` (semantic, not presence).
5. **SC3 QtWebEngineProcess not found** — BaseApp ships `QtWebEngineProcess` under `/app/bin`,
   but runtime Qt searches `/usr/…` → OAuth helper aborts (SIGABRT, logged as `SubprocessCrash exit=6`).
   Added `--env=QTWEBENGINEPROCESS_PATH=/app/bin/QtWebEngineProcess` + new drift guard.
6. **SC1 no desktop integration** — manifest never installed the `.desktop`, metainfo, or icon
   into `/app/share`; no GNOME Software listing, no launcher/icon, "No appstream data" on export.
   Added install steps + pre-rendered 128/256/512 icons (flatpak rejects size≠dir) + drift guard.

### Environmental (not a code defect)
- **rofiles-fuse unmount busy** — `onedrive --monitor` watches `~/OneDrive/` (repo location) and
  grabbed files created by `appstreamcli compose` inside the rofiles overlay, blocking unmount.
  Resolved for this build by pausing OneDrive sync; project to be moved off OneDrive after phase.

### Minor / latent (noted, not fixed)
- **desktop_install retry noise** — Phase 61 `desktop_install.py` runs inside the Flatpak and
  fails looking for `packaging/linux/…desktop` (non-Flatpak path); harmless retry, but log noise.
- **"Stopped Receiving Updates"** in GNOME Software — expected for a local-bundle install with no
  update remote; disappears once published to a real Flatpak remote. Not a defect.

## Build + install (Plan 86-05 Task 1 — automatable, run first on the rig)

```bash
# From repo root. No GPG key in env → SKIP_SIGN=1 for local iteration
# (CI / release builds set GPG_KEY_ID and sign per FP-11).
SKIP_SIGN=1 bash tools/linux-flatpak/build.sh
# Expect: BUILD_OK + SIGN_SKIPPED, artifact at tools/linux-flatpak/artifacts/MusicStreamer-2.1.84.flatpak

# Install locally (--no-gpg-verify acceptable for a self-built local bundle):
flatpak install --user --no-gpg-verify tools/linux-flatpak/artifacts/MusicStreamer-2.1.84.flatpak

# Confirm AAC decoder + node resolve INSIDE the sandbox:
flatpak run --command=bash io.github.kcreasey.MusicStreamer -c "gst-inspect-1.0 avdec_aac"   # expect element printed, exit 0
flatpak run --command=bash io.github.kcreasey.MusicStreamer -c "which node"                   # expect /app/bin/node
```

- Build transcript (BUILD_OK / SIGN_SKIPPED): _paste_
- `flatpak install --user` transcript: _paste_
- `gst-inspect-1.0 avdec_aac` output: _paste_  → **Open Question 2/A7:** if this FAILS, uncomment `--env=GST_PLUGIN_PATH=/app/lib/ffmpeg` in `io.github.kcreasey.MusicStreamer.yaml` (left commented in Plan 01 Task 2), rebuild, retest, and record the resolution here.
- `which node` output (expect `/app/bin/node`): _paste_

---

## SC1 — Install / launch (PKG-LIN-FP-02, D-11) ✅ PASS
- [x] `io.github.kcreasey.MusicStreamer` appears in GNOME Software (listed; benign "Stopped
      Receiving Updates" note — expected for local-bundle install with no update remote)
- [x] appears in GNOME app grid with icon; launches the GUI
- [x] `flatpak run io.github.kcreasey.MusicStreamer` launches the GUI
- Evidence: `.desktop` + metainfo + icons (128/256/512) deployed to `/app/share` and exported to
  host; `appstreamcli compose` generates `io.github.kcreasey.MusicStreamer.xml.gz`. (Required fix #6.)
- Notes: native Wayland GNOME rig, DPR=1.0, single-host

## SC2 — AAC audio audible via ffmpeg-full (PKG-LIN-FP-07) ✅ PASS
- [x] AAC audible (YT / AAC / MP3 streams all play with sound on the rig)
- In-sandbox pre-checks: `avdec_aac` PRESENT, `aacparse` PRESENT, ffmpeg-full mounted
  (`libavcodec.so.61`), `node` → `/app/bin/node`. Open Question 2 resolved — no GST_PLUGIN_PATH
  fallback needed.

## SC3 — GBS.FM login + persistence (PKG-LIN-FP-05, D-12) ✅ PASS
- [x] In-app QtWebEngine login completes — `oauth.log` shows `Success` (gbs), no namespace error
- [x] Fully quit → relaunch → still logged in (gbs-cookies.txt persisted in `~/.var/app/...`)
- Evidence: required fix #5 (`QTWEBENGINEPROCESS_PATH`). Before the fix: `SubprocessCrash exit=6`
  (SIGABRT, "could not find Qt WebEngine Process"). After: helper opens, login succeeds, persists.

## SC4 — MPRIS2 media-key control (PKG-LIN-FP-08, D-10) ✅ PASS
```bash
busctl --user list | grep mpris            # expect org.mpris.MediaPlayer2.musicstreamer (SHORT, lowercase)
```
- [x] `busctl` shows `org.mpris.MediaPlayer2.musicstreamer` (short LOWERCASE name — matches
      SERVICE_NAME in mpris2.py:56; NOT the long `...io.github.kcreasey.MusicStreamer`)
- [x] OS media keys (play/pause/next) reach sandbox playback (confirmed by user)
- Evidence: required fix #4 (case mismatch). `PlaybackStatus`/`Identity` readable through the proxy.
  NOTE: earlier doc/RESEARCH said capital `MusicStreamer` — that was the bug; lowercase is correct.

## SC5 — First-launch import offer (PKG-LIN-FP-06 functional half, D-02/D-03) ❌ FAIL → follow-up
- Existing unsandboxed data present at `~/.local/share/musicstreamer/musicstreamer.sqlite3` ✓
- [ ] First launch OFFERS the import wizard — **FAILS: wizard never offered**
- [ ] Dismiss → relaunch → does NOT re-offer — **N/A (offer never fires)**
- [x] Original `~/.local/share/musicstreamer/` intact after launch (copy-don't-delete holds)
- **Root causes (two defects, captured as follow-up plan):**
  1. `FlatpakImportWizard` (Plan 86-02) is **never wired into startup** — no code path invokes
     `should_offer_import_wizard()` / instantiates the wizard.
  2. `migration.run_migration()` **mis-fires in the sandbox**: the `:ro` host mount makes
     `src ≠ dest`, so it silently copies ALL host data (incl. 0600 cookies/tokens) into the
     sandbox without consent, preempting the wizard. (No-op on native Linux where src == dest.)
- Test method: moved sandbox aside (reversible), launched fresh with host data present; library
  loaded silently, no wizard, no offer-once flag written. `should_offer_import_wizard()` returns
  True but is never called. Sandbox restored afterward; host data + GBS login intact.

---

## Summary
total: 5 (SC1–SC5)
passed: 4 (SC1, SC2, SC3, SC4)
failed: 1 (SC5 — import wizard unwired + migration auto-copy in sandbox)
pending: 0
build_defects_fixed: 6 (+1 environmental, OneDrive/rofiles)

## Gaps
- **SC5 / D-02 / D-03 (FOLLOW-UP):** wire FlatpakImportWizard into GUI startup AND make
  `migration.run_migration()` Flatpak-aware (skip auto-copy when sandboxed, detect via
  `/.flatpak-info`) so the offered, consent-based, offer-once import is the sole path. Includes
  a privacy concern: secrets are currently copied silently. Needs its own plan + tests.
