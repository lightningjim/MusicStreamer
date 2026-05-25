# Phase 56: Windows DI.fm + SMTC Start Menu - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Two independent Windows-side fixes that Phase 44 attempted but did not fully deliver:

1. **WIN-01 — DI.fm HTTPS-fallback policy.** Phase 43 confirmed DI.fm premium URLs reject HTTPS server-side (TLS handshake succeeds, `souphttpsrc` returns `streaming stopped, reason error (-5)` mid-stream). Phase 44 D-15 chose "accept as server-side issue, document only." This phase reverses that and ships a transparent HTTPS→HTTP rewrite in the player URI boundary.
2. **WIN-02 — SMTC Start Menu shortcut + AUMID display.** The Phase 44 installer (`packaging/windows/MusicStreamer.iss:71`) already declares `AppUserModelID: "org.lightningjim.MusicStreamer"` on the Start Menu shortcut, and `__main__.py::_set_windows_aumid` calls `SetCurrentProcessExplicitAppUserModelID` before `QApplication()`. Yet the SMTC overlay still shows "Unknown app" in practice — phase delivers a diagnose-then-fix cycle on the Win11 VM until the overlay shows "MusicStreamer".

**In scope:**
- A pure URL helper in `musicstreamer/url_helpers.py` that rewrites `https://` → `http://` for DI.fm-network URLs, applied at the playback URI boundary.
- Wiring that helper into `musicstreamer/player.py::_set_uri` so every `set_uri` call (play, YouTube/Twitch resolved, failover) goes through it.
- Unit tests for the helper and a player-level test that asserts the rewrite reaches `playbin3`.
- Win11 VM diagnostic + fix cycle for SMTC: verify shortcut `System.AppUserModel.ID` property; verify in-process AUMID via `GetCurrentProcessExplicitAppUserModelID` readback; reinstall from fresh installer; iterate until SMTC overlay reads "MusicStreamer".
- UAT on Win11 VM covering both WIN-01 (DI.fm plays end-to-end) and WIN-02 (SMTC overlay shows app name).

**Out of scope:**
- Windows audio pause/resume glitch + ignored volume slider — Phase 57 (WIN-03).
- `test_thumbnail_from_in_memory_stream` AsyncMock fix — Phase 57 (WIN-04).
- Per-network HTTPS workarounds for other AA networks (RadioTunes, JazzRadio, ZenRadio, etc.) — only DI.fm is known-broken per Phase 43.
- Try-then-fallback retry logic in the player — overkill given Phase 43 confirmed stable server-side rejection.
- Migrating existing DB rows (rewriting stored `https://` URLs) — rewrite happens at the play-time URI boundary, so stored data is irrelevant.
- Code signing / MSIX / auto-update — still deferred to v2.1+ per Phase 44 disposition.
- Aggressive GStreamer plugin pruning — still deferred per Phase 44 D-16.

</domain>

<decisions>
## Implementation Decisions

### DI.fm HTTPS→HTTP rewrite (WIN-01)

- **D-01: Fix site = Player URI boundary.** Rewrite happens in `musicstreamer/player.py::_set_uri()` (or via a one-line helper call at the top of it). Universal coverage — every URL handed to `playbin3` is normalized, regardless of source (manual edit, AA import, settings-import ZIP, multi-stream failover, YouTube resolved, Twitch resolved). No DB schema change. No `aa_import.py` change. No migration step needed.
- **D-02: Detection via existing `_aa_slug_from_url`.** Reuse `musicstreamer/url_helpers.py::_aa_slug_from_url(url) == "di"` to classify a URL as DI.fm. Same canonical detection used by Phase 51 (siblings) and Phase 64 (now-playing siblings). Keeps the network-membership predicate single-sourced via the `NETWORKS` table.
- **D-03: Always rewrite, regardless of platform.** Unconditional `https://` → `http://` swap when the slug check fires. Phase 43 finding is server-side: DI.fm rejects HTTPS for everyone, not just Windows. Cross-platform symmetry over a `sys.platform == "win32"` branch — fewer code paths, no "works on my Linux" surprises if the user ever pulls fresh AA imports onto Linux. If DI.fm ever fixes their server, the rewrite becomes a manual one-line revert.
- **D-04: Helper lives in `url_helpers.py` as a free function.** New `aa_normalize_stream_url(url: str) -> str` next to `_aa_slug_from_url` / `_is_aa_url` / `_aa_channel_key_from_url`. Pure string transform, independently unit-testable, discoverable for future per-network workarounds. `_set_uri` becomes a one-line call: `uri = aa_normalize_stream_url(uri)`.

### DI.fm rewrite — silent (Claude's discretion)

- **D-05:** Rewrite is silent. No toast, no info-level log spam at every `_set_uri` call — this is a workaround for a known stable server bug, not a user-visible event. Single `logging.debug` line at the rewrite site is sufficient for forensic visibility if a future regression suspect surfaces.
- **D-06:** Helper is idempotent. Already-`http://` DI.fm URLs pass through unchanged. Non-DI.fm URLs pass through unchanged. Empty / malformed URLs pass through (the existing GStreamer error path handles them).

### SMTC Start Menu / AUMID display (WIN-02) — diagnose-first

- **D-07: Diagnose before changing code.** The wiring already exists in code (`__main__.py::_set_windows_aumid` runs before `QApplication()` with explicit `LPCWSTR` argtypes; `MusicStreamer.iss` declares `AppUserModelID: "org.lightningjim.MusicStreamer"` on the Start Menu shortcut). The fact that SMTC still says "Unknown app" means the wiring is technically correct but operationally broken — likely environmental (stale install, launching via wrong path, Windows shortcut-property cache). First action is a Win11 VM session that reads back the actual state, not speculative refactoring.
- **D-08: Diagnostic checklist (run on the VM, in order):**
  1. From an elevated PowerShell, read the actual AUMID property on the installed shortcut: `(New-Object -ComObject Shell.Application).Namespace("$env:APPDATA\Microsoft\Windows\Start Menu\Programs").ParseName('MusicStreamer.lnk').ExtendedProperty('System.AppUserModel.ID')`. Expected: `org.lightningjim.MusicStreamer`. If empty → installer is not setting the property correctly; revisit `.iss`. If different string → AUMID drift between `.iss` and `__main__.py`; align them.
  2. Launch via the Start Menu shortcut. From a separate console, attach `Get-Process MusicStreamer | Select-Object Id` then read the in-process AUMID via a small helper (PowerShell + `[System.Runtime.InteropServices.Marshal]::PtrToStringUni` over `GetCurrentProcessExplicitAppUserModelID`). Expected: matches the shortcut property.
  3. Inspect the live SMTC binding: open Windows Settings → System → Notifications & actions, find "MusicStreamer" and confirm it lists the friendly name; OR open `Get-StartApps | Where-Object Name -like 'MusicStreamer*'` and confirm the AppID column.
  4. Force a fresh install: uninstall via Settings → Apps; delete `%LOCALAPPDATA%\Programs\MusicStreamer` if it lingers; clear the Start Menu shortcut cache (`Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk"`); reinstall from a freshly built `dist/installer/...exe`. Re-run the playback test and check SMTC.
- **D-09: Likely root-cause shortlist (in order of probability), driven by D-08 readouts:**
  1. **Stale shortcut from an earlier installer iteration** that did not carry `AppUserModelID`. Windows caches the `IShellLink` AUMID property; reinstalling over the top doesn't always re-read it. Fix: force-delete shortcut + reinstall (already in D-08 step 4).
  2. **User launched via `python -m musicstreamer` or the post-install checkbox** (`MusicStreamer.iss:79` `Run` section), which Phase 43.1 documented as bypassing the shortcut-AUMID binding. Fix: post-install Run checkbox stays unchecked (already configured); update README to point users at the Start Menu launch path explicitly.
  3. **AUMID-string drift** between `__main__.py` (`org.lightningjim.MusicStreamer`) and `MusicStreamer.iss` (`org.lightningjim.MusicStreamer`). Currently aligned — but a future copy-paste could drift them; add a build-time `iscc` constant or a smoke-test grep that fails if they don't match.
- **D-10: Code change scope (decided post-diagnostic).** If D-08 reveals an environmental cause (D-09 #1 or #2), no code change — phase ships a documentation update + UAT confirmation. If D-08 reveals a wiring bug (D-09 #3 or unknown), patch the offending site and re-run UAT. Either way, the phase is gated on the SMTC overlay reading "MusicStreamer" on a fresh install of the freshly-built installer.

### Verification scope

- **D-11: Win11 VM UAT, no automated cross-platform tests for SMTC.** Same UAT pattern as Phase 43.1 / Phase 44. SMTC overlay rendering is shell-mediated and not unit-testable without a Windows host. The DI.fm URL helper and `_set_uri` integration get pytest unit + player-level tests on Linux CI; the SMTC half is human-UAT-only.
- **D-12: DI.fm UAT trial set.** On Win11 VM: at least one DI.fm channel (e.g., DI.fm Lounge) plays from a fresh AA import, and at least one DI.fm channel plays from an existing DB row already migrated from a Linux DB via the Phase 42 settings-import ZIP. Both must reach audible audio + ICY title display. Confirms the rewrite covers both "fresh import" and "settings-import roundtrip" paths.

### Claude's Discretion

- Exact name of the helper — `aa_normalize_stream_url` is the proposal; planner can adjust if a better name emerges (e.g., `normalize_aa_stream_url` for symmetry with other `aa_*` helpers in `aa_import.py`).
- Whether the helper is also called from `aa_import.py` at insert time (defensive belt-and-suspenders) or only from `_set_uri` (single source of truth). Lean toward the latter — fewer call sites, lower risk of a future contributor adding a third invocation that diverges.
- Phrasing of the README / packaging note that reminds users to launch via the Start Menu shortcut, not `python -m musicstreamer`.
- Whether the build-time AUMID-string drift guard (D-09 #3 prevention) is a `pytest` test that reads the `.iss`, a `build.ps1` ripgrep, or skipped entirely as YAGNI.

### Folded Todos

None — the three pending todos (`.planning/notes/2026-03-21-sdr-live-radio-support.md`, `.planning/notes/2026-04-03-station-art-fetching-beyond-youtube.md`) and the current STATE.md `Pending Todos` are unrelated to Windows DI.fm or SMTC.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spike findings — Windows GStreamer / DI.fm / AUMID
- `.claude/skills/spike-findings-musicstreamer/SKILL.md` — Auto-load triggers; index of validated patterns.
- `.claude/skills/spike-findings-musicstreamer/references/windows-gstreamer-bundling.md` — DI.fm HTTPS rejection finding (the "Landmines" section names the exact symptom: TLS handshake succeeds, `error (-5)` follows). conda-forge build env, OpenSSL TLS backend (1.28.x), runtime hook env vars.
- `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md` — Cross-platform Qt/GLib bus rules (locked, relevant if any player wiring around `_set_uri` changes).

### Phase 43 — GStreamer Windows spike (HTTPS finding origin)
- `.planning/milestones/v2.0-phases/43-gstreamer-windows-spike/43-SPIKE-FINDINGS.md` — Full findings; "Known Gotchas" table includes the DI.fm HTTPS rejection.

### Phase 43.1 — Windows Media Keys + AUMID handoff
- `.planning/milestones/v2.0-phases/43.1-windows-media-keys-smtc/43.1-CONTEXT.md` — AUMID must precede `QApplication()`; `LPCWSTR` argtypes required; readback via `GetCurrentProcessExplicitAppUserModelID`; SMTC display name requires a registered shortcut with matching AUMID.

### Phase 44 — Installer (the Start Menu shortcut + AUMID wiring this phase has to verify)
- `.planning/milestones/v2.0-phases/44-windows-packaging-installer/44-CONTEXT.md` — D-04 (Start Menu shortcut mandatory + AUMID), D-15 (DI.fm "accept server-side" — the policy this phase reverses), D-21 step 7 (the original UAT criterion: SMTC must show "MusicStreamer").
- `packaging/windows/MusicStreamer.iss` — Lines 64–71 declare `AppUserModelID: "org.lightningjim.MusicStreamer"` on the Start Menu icon. Line 79 declares the post-install `Run` flag (`unchecked` per Phase 44 D-04 — confirm during diagnostic).

### Source files this phase touches
- `musicstreamer/__main__.py` — `_set_windows_aumid` (lines 99–125); ordering vs. `QApplication()` at line 142 already correct per Phase 43.1.
- `musicstreamer/player.py` — `_set_uri` at line 484; called from `play()`, `_on_youtube_resolved` (line 590-ish), `_on_twitch_resolved` (line 669-ish), `_try_next_stream`. All paths must go through the rewrite.
- `musicstreamer/url_helpers.py` — `_aa_slug_from_url` (line 123); `NETWORKS` import from `aa_import` (line 13). New helper lands here.
- `musicstreamer/aa_import.py` — `NETWORKS` table (line 89); `fetch_channels` and `fetch_channels_multi` for context (no edit needed under D-01).

### Project-level
- `.planning/REQUIREMENTS.md` — WIN-01, WIN-02 (both pending, both this phase).
- `.planning/ROADMAP.md` — Phase 56 entry: 4 success criteria (DI.fm policy chosen + implemented, Start Menu shortcut carries AUMID, SMTC shows "MusicStreamer", AUMID parity).
- `.planning/STATE.md` — Blockers/Concerns: "Phase 56: DI.fm HTTPS-fallback policy not yet decided" — resolved by D-01..D-04.
- `.planning/PROJECT.md` — v2.1 milestone shape; Phase 44 carry-forward Windows polish bullet list.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`musicstreamer/url_helpers.py::_aa_slug_from_url`** — exact predicate for D-02. Returns `"di"` for any DI.fm URL (premium or public, any host like `prem1.di.fm`, `prem2.di.fm`, `listen.di.fm`).
- **`musicstreamer/url_helpers.py::NETWORKS` (re-exported from `aa_import.py`)** — domain table; `_aa_slug_from_url` already iterates it. New helper inherits the same source-of-truth.
- **`musicstreamer/__main__.py::_set_windows_aumid`** — already-correct AUMID setup; Phase 43.1 verified the readback. Don't refactor; just verify in the field.
- **`packaging/windows/MusicStreamer.iss`** — already-correct shortcut declaration with `AppUserModelID:` clause; Phase 44 already shipped this. Diagnostic confirms it's effective on the user's actual install.
- **Phase 51/64 sibling logic in `url_helpers.py`** — same network-detection helper pattern; new helper drops in alongside without churn.

### Established Patterns
- **Pure-function helpers in `url_helpers.py`** — every URL classification helper (`_is_youtube_url`, `_is_aa_url`, `_aa_slug_from_url`, `_aa_channel_key_from_url`, `find_aa_siblings`) is a pure function with no Qt/GLib/GStreamer coupling, unit-tested in isolation. New `aa_normalize_stream_url` follows the same shape.
- **Single transform at URI boundary** — `_set_uri` is the universal funnel for everything `playbin3` ever sees. Wrapping the input there matches Phase 47-01's "transform once at the boundary" pattern (stream ordering happens at `play()` entry, not at every call site).
- **Platform split via `sys.platform == "win32"` guards** — used throughout `media_keys/` and `subprocess_utils.py`. WIN-02 fix (if needed) follows the same idiom; DI.fm fix deliberately does NOT (D-03 — server-side issue is platform-agnostic).
- **Phase 43.1 ctypes pattern** (`LPCWSTR` argtypes for Win32 string-receiving APIs) — already applied in `_set_windows_aumid`; if the diagnostic shortlist points at `GetCurrentProcessExplicitAppUserModelID` readback as a smoke-test asset, follow the same explicit-argtypes pattern.

### Integration Points
- **`_set_uri` call sites** — `play()` (initial stream), `_on_youtube_resolved` (post-yt-dlp), `_on_twitch_resolved` (post-streamlink), `_try_next_stream` (failover). All four go through the same `_set_uri`, so a single point of insertion covers them all.
- **`_set_uri` is on the Qt main thread** — D-04 helper is pure synchronous string work, no thread concern.
- **No DB / persistence touch** — the rewrite is stateless. Existing rows, settings ZIPs, and manual edits are unaffected. A user examining the DB still sees the original `https://` URL; only `playbin3` ever sees the `http://` form.

</code_context>

<specifics>
## Specific Ideas

- **AUMID string is `org.lightningjim.MusicStreamer`** — locked across `__main__.py`, `MusicStreamer.iss`, and SMTC reads. Any change in any of those three places must be made in lockstep or SMTC reverts to "Unknown app".
- **DI.fm rejects HTTPS server-side regardless of platform** — Phase 43 finding. The fix is global, not Windows-only (D-03). The phase is "Windows" only because that's the surface the bug was first observed on; the implementation is OS-neutral.
- **Start Menu shortcut is the only AUMID anchor** — `python -m musicstreamer` continues to show "Unknown app" by design (Phase 43.1 finding). README + UAT must specify "launch via Start Menu shortcut" explicitly; do not encourage shell-launch as an equivalent path.
- **Phase 44 D-21 step 7 already specifies the SMTC UAT criterion** — "SMTC overlay shows **'MusicStreamer'**". This phase is the close-out of that UAT step that didn't pass cleanly.
- **No DB migration, no data touch** — the rewrite is at the playback boundary. A future user inspecting the SQLite DB will see whatever URL was originally stored (probably `https://` from AA imports). That's intentional; the rewrite is a server-bug workaround, not a data-correctness fix.

</specifics>

<deferred>
## Deferred Ideas

### Deferred to future phases / re-visit later
- **Per-network HTTPS workarounds for other AA networks** — only DI.fm is known-broken (Phase 43). If RadioTunes / JazzRadio / ClassicalRadio / RockRadio / ZenRadio ever surface the same `error (-5)` symptom, extend `aa_normalize_stream_url` to cover those slugs with the same one-line predicate. No anticipatory work this phase.
- **Try-then-fallback retry logic in the player** — preserves HTTPS if DI.fm ever fixes their server. Overkill given the stable Phase 43 finding. Re-evaluate only if external evidence appears that DI.fm has fixed the issue.
- **Build-time AUMID-string drift guard** — pytest assertion or `build.ps1` ripgrep that fails if `__main__.py`'s AUMID literal disagrees with `MusicStreamer.iss`'s `AppUserModelID:` clause. Listed as Claude's discretion (D-09 #3 prevention) but probably YAGNI for a single-author personal project.
- **Code signing / MSIX / auto-update** — still deferred to v2.1+ per Phase 44 disposition; unchanged.

### Out-of-phase (already roadmapped)
- **WIN-03 / WIN-04** — Phase 57 (audio pause/resume glitch + AsyncMock test fix).
- **BUG-08** — Phase 61 (Linux WM display name; Linux parallel to WIN-02).
- **VER-01** — Phase 63 (auto-bump pyproject version on phase completion).

### Reviewed Todos (not folded)
None reviewed.

</deferred>

---

*Phase: 56-windows-di-fm-smtc-start-menu*
*Context gathered: 2026-05-01*
