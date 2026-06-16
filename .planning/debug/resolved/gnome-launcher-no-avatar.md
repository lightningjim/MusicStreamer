---
slug: gnome-launcher-no-avatar
status: resolved
trigger: "When I run either dev_launch or the musicstreamer pipx install it's fine, but when I run the GNOME desktop launcher the avatar fetch shows 'No avatar found - cover will use the station thumbnail'"
created: 2026-06-16
updated: 2026-06-16
---

# Debug: Avatar fetch fails only from the GNOME desktop launcher

## Symptoms

- **Expected:** Pasting a YouTube channel URL in EditStationDialog fetches the channel avatar ("Fetching avatar…" → "Avatar found"), regardless of how the app was launched.
- **Actual:** From the GNOME desktop launcher only, the avatar fetch fails with the inline message "No avatar found - cover will use the station thumbnail". From `./scripts/dev-launch.sh` and from the `musicstreamer` pipx install (both terminal launches) it works fine.
- **Error:** No crash; the failure is the non-blocking inline message. (`_AvatarFetchWorker.run()` emits an empty rel_path on ANY exception → `_on_avatar_fetched` shows the D-03 "No avatar found" message.)
- **Scope (user-confirmed):** ONLY the avatar fetch fails from the launcher. YouTube streams still play and the logo/thumbnail fetch (also yt-dlp) works from the same GNOME launcher.
- **Launcher (user-confirmed):** Hand-made `.desktop` file created in a prior session, under `~/.local/share/applications`.
- **Timeline:** Noticed right after Phase 89 (the avatar feature) shipped.

## Current Focus

hypothesis: |
  fetch_channel_avatar() hardcodes yt_dlp_opts.build_js_runtimes(None)
  (yt_import.py:199), so the avatar's channel-page extraction relies on yt-dlp's
  own PATH lookup to find the node JS runtime (EarlyJS / ejs:github challenge
  solving). A GNOME .desktop launcher starts the app with a minimal PATH (no
  shell profile sourced), so node is not on PATH and the JS challenge fails →
  RuntimeError → worker emits "" → "No avatar found". Terminal/pipx launches have
  a rich PATH where yt-dlp finds node, so they work. Logo fetch and HLS playback
  succeed because (per build_js_runtimes docstring / D-02) those paths resolve
  WITHOUT invoking the JS runtime — only the channel extraction needs it.
test: |
  1. Confirm node is absent from the .desktop launcher's effective PATH (the
     .desktop Exec= line / GNOME session env vs. the terminal env).
  2. Confirm runtime_check.check_node() resolves an ABSOLUTE node path on this
     machine (it searches fnm/nvm/volta/asdf locations beyond PATH — see
     yt_dlp_opts.py:20) and that threading it into fetch_channel_avatar makes the
     avatar fetch succeed under the minimal-PATH launcher environment.
expecting: |
  With js_runtimes carrying the resolved absolute node path, the channel
  extraction succeeds even when PATH lacks node — matching how scan_playlist
  (yt_import.py:86) and the player (player.py:1866) already behave.
next_action: |
  Fix applied. Verifying with scoped pytest run.
reasoning_checkpoint:
  hypothesis: "fetch_channel_avatar() hardcodes build_js_runtimes(None) at yt_import.py:199,
    so under the GNOME .desktop launcher's minimal PATH (no shell profile) yt-dlp
    falls back to its own PATH-lookup for node, finds nothing, and the EarlyJS
    challenge fails → RuntimeError → _AvatarFetchWorker emits '' → 'No avatar found'."
  confirming_evidence:
    - "grep of all build_js_runtimes call sites: scan_playlist:86 and player.py:1866
      both pass the threaded node_runtime; ONLY fetch_channel_avatar:199 hardcodes None."
    - "player.py:23 docstring explicitly names '.desktop launchers' as the motivation
      for threading the resolved absolute node path — identical bug class."
    - "build_js_runtimes(None) docstring: 'preserves yt-dlp own PATH-lookup fallback' —
      that fallback fails under .desktop minimal PATH."
    - "User confirmed: logo fetch and HLS playback (also yt-dlp) work from the GNOME
      launcher; only avatar fails — consistent with only channel extraction needing JS."
    - "Session already surfaced yt-dlp 'see yt-dlp/wiki/EJS for details on installing
      one' message from the avatar path — JS runtime is exercised by avatar fetch."
  falsification_test: "If the JS runtime were NOT the cause, threading an absolute node
    path should make no difference. But the identical fix applied to scan_playlist and
    player.py resolves exactly the same symptom for those paths."
  fix_rationale: "Add node_runtime param (default None, back-compat) to fetch_channel_avatar,
    pass to build_js_runtimes. Thread the startup-resolved NodeRuntime from MainWindow
    through EditStationDialog constructor → _AvatarFetchWorker.run(). This is the exact
    same pattern already working for scan_playlist and player."
  blind_spots: "write_channel_avatar filesystem failure is a separate secondary hypothesis
    (already listed in Eliminated as lower-priority); this fix addresses the primary
    and sufficient root cause."

## Evidence

- timestamp: 2026-06-16
  observation: "grep of all build_js_runtimes call sites: scan_playlist (yt_import.py:86) passes the threaded `node_runtime` param; player.py:1866 passes self._node_runtime; ONLY fetch_channel_avatar (yt_import.py:199) hardcodes build_js_runtimes(None)."
- timestamp: 2026-06-16
  observation: "player.py:23 docstring: resolved absolute path is threaded through build_js_runtimes 'so .desktop [launchers work]' — the codebase already encountered and fixed this exact minimal-PATH .desktop class of bug for playback."
- timestamp: 2026-06-16
  observation: "build_js_runtimes(None) returns {'node': {'path': None}}, which the docstring says 'preserves yt-dlp's own PATH-lookup fallback'. Under a .desktop minimal PATH that fallback finds no node."
- timestamp: 2026-06-16
  observation: "runtime_check.check_node() (runtime_check.py:109-116) returns an absolute node path resolved from fnm/nvm/volta/asdf locations beyond PATH; __main__.py:303 already calls it at startup and threads it into the player."
- timestamp: 2026-06-16
  observation: "User confirmed: from the GNOME launcher only the avatar fails; YouTube playback + logo fetch (both yt-dlp) work — consistent with only the channel extraction needing the JS runtime (D-02)."
- timestamp: 2026-06-16
  observation: "Earlier in this session, the avatar fetch surfaced a yt-dlp 'see yt-dlp/wiki/EJS for details on installing one' message — i.e. the EarlyJS/JS runtime path is exercised by the avatar's channel extraction."

## Eliminated

- hypothesis: "General yt-dlp / cookies / network failure under the launcher"
  reason: "User confirmed YouTube playback and logo fetch (both yt-dlp, both use cookies/network) work from the GNOME launcher; only the avatar fails."
- hypothesis: "Filesystem/data-dir write failure (write_channel_avatar) under the launcher"
  reason: "Possible but secondary — the failure would have to occur before any avatar bytes are fetched; the JS-runtime extraction failure occurs earlier in run() and fully explains the symptom. To be ruled in/out only if the node-path fix does not resolve it."

## Resolution

root_cause: |
  fetch_channel_avatar() (yt_import.py) hardcoded build_js_runtimes(None), so
  yt-dlp used PATH-lookup to find the node JS runtime. GNOME .desktop launchers
  run with a minimal PATH (no shell profile), so node was not found, the
  EarlyJS/ejs:github challenge failed, _AvatarFetchWorker caught the exception
  and emitted an empty rel_path, and the dialog showed "No avatar found".
  Terminal/pipx launches had node on PATH so they worked. Logo fetch and HLS
  playback were unaffected because those code paths never invoke the JS runtime.
fix: |
  1. Added node_runtime: NodeRuntime | None = None keyword parameter to
     fetch_channel_avatar() and passed it to build_js_runtimes() instead of None.
  2. Added node_runtime param to _AvatarFetchWorker.__init__ and forwarded it to
     fetch_channel_avatar(node_runtime=self._node_runtime) in run().
  3. Added node_runtime param to EditStationDialog.__init__ and stored it as
     self._node_runtime; passed it to _AvatarFetchWorker at construction time.
  4. Updated MainWindow._on_new_station_clicked and _on_edit_requested to pass
     node_runtime=self._node_runtime when constructing EditStationDialog.
  5. Added three regression tests in tests/test_yt_import_library.py asserting
     the avatar opts carry the threaded node path (mirrors scan_playlist tests
     B-79-07/08/09). All 25 tests pass.
verification: "25/25 tests pass in tests/test_yt_import_library.py (scoped run). Human-verified 2026-06-16: user launched from the GNOME .desktop launcher and confirmed the avatar fetch now succeeds ('Avatar found'), where it previously showed 'No avatar found'."
files_changed:
  - musicstreamer/yt_import.py
  - musicstreamer/ui_qt/edit_station_dialog.py
  - musicstreamer/ui_qt/main_window.py
  - tests/test_yt_import_library.py
