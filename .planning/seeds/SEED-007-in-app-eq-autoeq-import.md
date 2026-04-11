---
id: SEED-007
status: dormant
planted: 2026-04-11
planted_during: v2.0 Phase 35 — Backend Isolation (discuss-phase context for 35-06)
trigger_when: v2.0 Windows build ships OR user starts a "quality-of-life / audio enhancement" milestone OR Plan 35-06 lands and user wants to test the new GStreamer-only audio path with a system EQ substitute
scope: medium
---

# SEED-007: In-app parametric EQ with AutoEQ profile import

## Why This Matters

The user's work laptop has IT restrictions that prevent installing
`Equalizer APO` (the standard Windows system-wide equalizer). That
means MusicStreamer on the work PC currently plays headphone audio
flat — no per-headphone correction curve.

The user maintains AutoEQ-generated parametric EQ profiles for their
headphones (AutoEQ is the well-known community project at
`https://github.com/jaakkopasanen/AutoEQ` that publishes
measurement-based correction curves as parametric EQ configs).
Without Equalizer APO there is no way to apply these profiles on the
work PC — unless MusicStreamer itself provides an in-app EQ that can
ingest the AutoEQ `ParametricEQ.txt` format.

This is the **only** path to equalized headphone audio on the
restricted work machine. It also unlocks profile-per-headphone
switching regardless of platform, which is useful on the Linux
dev machine too.

## When to Surface

**Trigger:** Post-v2.0 Windows port, when the user scopes a
quality-of-life or audio-enhancement milestone. Specifically, surface
this seed during `/gsd-new-milestone` if the new milestone scope
includes any of:

- "Audio quality" / "audio enhancement" / "headphone" / "EQ"
- "Windows quality of life" / "work PC features"
- "DSP" / "filters" / "sound processing"
- Any v2.1+ milestone that is NOT strictly bug-fix

Do NOT surface during v2.0 itself — v2.0 is explicitly "port-only, no
new user-facing features" per REQUIREMENTS.md scope principle.

## Scope Estimate

**Medium** — one focused phase, probably 3-4 plans:

1. **GStreamer pipeline integration:** Insert an `equalizer-nbands`
   element (or a chain of `audiocheblimit` / `audiocheblband` /
   `biquad` filters for true parametric EQ) into the `playbin3`
   `audio-filter` property. `equalizer-10bands` and `equalizer-nbands`
   are part of gstreamer-plugins-good and work with the existing
   `pulsesink`/`wasapisink` output. Phase 35's new Player QObject
   architecture makes this a clean insertion — no more "mpv handles
   audio, we don't touch it" excuse.

2. **AutoEQ format parser:** Read the AutoEQ `ParametricEQ.txt` format
   (one row per filter: `Filter N: ON PK Fc 62 Hz Gain 4.0 dB Q 1.41`)
   and map each row to either a GStreamer `equalizer-nbands` band or
   a `biquad` element configuration. AutoEQ publishes ~3000 headphone
   profiles — no need to run measurement ourselves.

3. **UI: EQ panel:** A small dialog (hamburger menu entry) with:
   - Master EQ enable/disable toggle
   - Import button (file picker for `ParametricEQ.txt`)
   - Current profile name display
   - Preamp gain slider (AutoEQ files include a preamp offset)
   - Band-by-band sliders for manual tweaking (read-only when an
     AutoEQ profile is loaded, to keep the correction curve honest)
   - Per-station toggle (optional — "disable EQ for this station")

4. **Persistence:** Store selected profile path + preamp + enable
   flag in SQLite settings. Survive app restarts.

Out of scope for the seed: auto-selecting profile by connected
headphone (USB/Bluetooth detection), multi-profile A/B switching,
convolution FIR (impulse-response) filters, spatial audio. Those are
further seeds if the core EQ lands.

## Breadcrumbs

Related code and decisions:

- `musicstreamer/player.py` — playbin3 audio sink configuration
  (post-Phase 35 QObject Player). `pulsesink` is wired on
  Linux; Windows will use `wasapisink` in Phase 44. The
  `audio-filter` property on playbin3 is the insertion point for the
  EQ element chain — must be set BEFORE `set_state(PLAYING)`.
- `.planning/notes/2026-04-10-mpv-vs-vlc-work-laptop-constraint.md` —
  documents the work-laptop IT restriction that motivates this seed.
  Same restriction blocks Equalizer APO and justifies an in-app EQ.
- `.planning/phases/35-backend-isolation/35-06-drop-mpv-yt-dlp-ejs-PLAN.md` —
  the plan that removed mpv and locked in GStreamer as the sole
  playback backend, making audio-filter insertion architecturally
  clean. Without this plan, mpv's separate audio path would bypass
  any in-app EQ for YouTube streams.
- `.planning/REQUIREMENTS.md` PORT-05/PORT-06 — platformdirs paths
  are the right home for a user-supplied profile directory
  (`{user_data_dir}/eq-profiles/`).
- AutoEQ project (external): `https://github.com/jaakkopasanen/AutoEQ`
  — reference for the `ParametricEQ.txt` format and the published
  profile corpus.
- GStreamer docs (external): `gstreamer-plugins-good` →
  `equalizer-nbands` and `equalizer-10bands` elements.

## Notes

- User's primary motivation is the **work PC specifically**: Equalizer
  APO is blocked, so the in-app EQ becomes the only lever. Prioritize
  Windows parity testing once the feature lands.
- The existing volume slider (AUDIO-01) is set via `playbin3` volume
  property at the sink level — the EQ inserts upstream of that at the
  `audio-filter` slot, so volume and EQ compose correctly without
  conflict.
- Consider exposing an "EQ off" one-click toggle in the now-playing
  panel (not just in the dialog) so users can A/B compare quickly
  when testing a new profile.
- AutoEQ files are plain text, so parsing is a small regex job — no
  new library dep. Might add `scipy` *only* if biquad coefficient
  computation gets unwieldy; prefer `equalizer-nbands` first (no
  extra deps) and only escalate to biquads if the sound quality
  justifies it.
- This seed is compatible with both Linux and Windows from day one
  because GStreamer's equalizer elements are cross-platform. No
  extra Windows bundling work beyond what PKG-01 already does.
</content>
</invoke>
