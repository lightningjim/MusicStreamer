# Phase 43: GStreamer Windows Spike - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Throwaway spike to validate that HTTP + HTTPS GStreamer playback works inside a PyInstaller `--onedir` bundle on a clean Windows 11 VM with no system GStreamer installed. Deliverable is a findings doc + draft `.spec` + a wrap-up skill that Phase 44 (Windows Packaging + Installer) inherits. Not the real installer, not NSIS, not single-instance, not SMTC — those belong to Phase 44 and Phase 43.1.

</domain>

<decisions>
## Implementation Decisions

### VM target
- **D-01:** Spike runs on a clean snapshot of the user's existing Windows 11 VM with no system-wide GStreamer installation on PATH. User takes/restores the snapshot around each build attempt; Claude does not drive the VM.
- **D-02:** Windows 11 only. Windows 10 coverage is explicitly out of scope for this spike — revisit if Phase 44 packaging surfaces a 10-specific issue.

### GStreamer distribution
- **D-03:** Use the official MSVC runtime build from gstreamer.freedesktop.org, latest 1.24.x release. Planner pins the exact version during research and records it in findings.
- **D-04:** Install both the `gstreamer-1.0-msvc-x86_64` runtime and the matching `gstreamer-1.0-devel` package — devel provides `gst-inspect-1.0.exe` needed to enumerate the plugin set the spike actually loads.

### Spike fidelity
- **D-05:** Minimal scope — one `playbin3` pipeline, one HTTPS ShoutCast-style source via `souphttpsrc`, one audio sink (sink choice is Claude's discretion — `wasapisink` is the likely winner on Win11; fall back to `autoaudiosink` / `directsoundsink` if wasapi glitches). HLS, yt-dlp integration, Twitch, cover art HTTP, ICY TAG propagation are explicitly deferred to Phase 44 smoke-test.
- **D-06:** The validated TLS path MUST exercise `libgiognutls.dll` (or whichever GIO TLS backend GStreamer ships on Windows) — that DLL is the historical miss that Success Criterion 2 calls out.

### Test URL
- **D-07:** Primary test URL is a live AudioAddict HTTPS channel pulled from the user's own library (real listen key, real AA cert chain). Planner extracts the URL via the Phase 42 settings-export tooling so the spike doesn't hard-code the listen key into committed artifacts.
- **D-08:** Public ShoutCast HTTPS URL is not required for this spike. If the AA URL fails in a way that points to listen-key auth rather than TLS/souphttpsrc, add a public URL at that point.

### Execution model
- **D-09:** Claude produces the build assets: `build.ps1` (or equivalent), a draft `spike.spec` with explicit `Tree()` / `binaries=` / `datas=` blocks, and `smoke_test.py` that exits 0 on first audio sample arriving. User runs them on the Windows VM snapshot and pastes stdout/stderr back into the chat.
- **D-10:** Iteration loop: Claude updates the `.spec` based on the paste-back (missing DLL, missing plugin, wrong giomodules path), user re-runs, repeat until HTTPS audio plays for ≥5s and the smoke test exits 0.

### Deliverables
- **D-11:** `43-SPIKE-FINDINGS.md` — captures exact GStreamer version, required DLL list (full filenames), required plugin list (full filenames from `gstreamer-1.0/`), `gio/modules/` contents needed for SSL, environment variables the bundle must set (`GST_PLUGIN_PATH`, `GIO_MODULE_DIR`, `GST_PLUGIN_SCANNER`), and any PATH / CWD gotchas discovered.
- **D-12:** `43-spike.spec` (draft) — a PyInstaller `.spec` Phase 44 can copy and extend. Lives in the phase directory, not at repo root; Phase 44 produces the canonical production spec elsewhere.
- **D-13:** Run `/gsd-spike-wrap-up` at phase close to persist findings as a project-local skill so future Windows packaging conversations load the DLL/plugin table automatically.
- **D-14:** No changes to `musicstreamer/` source code during the spike. If anything breaks the bundle that requires a source change (e.g., hard-coded Linux path), record it in findings and defer the source fix to Phase 44.

### Claude's Discretion
- Exact `wasapisink` vs `directsoundsink` vs `autoaudiosink` choice — whichever ships a clean first sample from HTTPS ShoutCast wins.
- Whether to invoke PyInstaller via CLI or via the `.spec` file directly in `build.ps1` (spec-file invocation is the standard path for non-trivial trees).
- Plugin blacklist strategy — start from `gst-inspect-1.0.exe` output and prune to the minimum that keeps the pipeline running.
- Script language for the build driver (PowerShell vs .bat vs a `uv run` shim) — planner picks based on what's lowest-friction for the user to paste results from.

### Folded Todos
None — no pending todos matched this phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase goal + acceptance
- `.planning/ROADMAP.md` §"Phase 43: GStreamer Windows Spike" — goal, dependencies, three success criteria
- `.planning/REQUIREMENTS.md` PKG-06 — dedicated GStreamer Windows bundling spike requirement
- `.planning/REQUIREMENTS.md` PKG-01 — downstream target that this spike unblocks (Phase 44 installer needs the DLL/plugin list this spike produces)

### Stack + prior decisions
- `.planning/PROJECT.md` §"Current Milestone: v2.0 OS Agnostic" — stack overview
- `.planning/PROJECT.md` Key Decisions row "Dropped mpv subprocess fallback (Plan 35-06)" — why there is no mpv.exe to bundle
- `.planning/STATE.md` §"Accumulated Context > Decisions" — v2.0 stack decisions (platformdirs, Node.js host prerequisite, etc.)

### Precedent spike (reference only — different tech)
- `.planning/phases/35-backend-isolation/35-SPIKE-MPV.md` — structure/template for spike findings docs in this project
- `.planning/phases/35-backend-isolation/35-CONTEXT.md` — example of how a prior spike was scoped

### External docs (fetch during research)
- gstreamer.freedesktop.org Windows install docs — identify current 1.24.x MSVC installer URL and bundled plugin set
- PyInstaller docs — `.spec` file `Tree()`, `binaries`, `datas`, `hiddenimports`, runtime hooks for non-Python data trees
- PyGObject (gi) Windows bundling notes — `gi.repository` + GIRepository on Windows has known `girepository-1.0` + `typelibs/` bundling requirements that intersect with GStreamer

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `musicstreamer/player.py` — current GStreamer pipeline (playbin3 + souphttpsrc path). The spike's smoke test imports the minimum of this to exercise the same code path.
- `musicstreamer/paths.py` — `platformdirs.user_data_dir("musicstreamer")` already resolves `%APPDATA%\musicstreamer` on Windows (Phase 35). Spike does not re-solve path handling.
- `musicstreamer/aa_import.py` / `musicstreamer/repo.py` — settings-export tooling used to pull the AA test URL + listen key out of the local DB without committing secrets.

### Established Patterns
- `uv run --with pytest` for test invocation — the spike's `smoke_test.py` can be invoked the same way if needed.
- GStreamer bus messages dispatched via Qt queued signals (not GLib.MainLoop under Qt) — STATE.md decisions note this is settled; spike uses a minimal `Gst.ElementFactory.make` path without the QObject wrapper to keep the test surface small.
- Phase 35 spike pattern: SPIKE-*.md findings doc + SUMMARY docs per plan + wrap-up at phase close.

### Integration Points
- Phase 44 reads `43-SPIKE-FINDINGS.md` + copies `43-spike.spec` as the starting point for the production installer.
- Phase 43.1 (Windows Media Keys / SMTC) depends on this phase's "confirmed Windows runtime" — it needs the PyInstaller bundle to actually run before winrt `button_pressed` can be validated live.

</code_context>

<specifics>
## Specific Ideas

- "Minimal first" — the spike should not try to prove the whole app works in a bundle. One HTTPS stream playing audio for 5+ seconds on a clean snapshot is the success bar.
- Treat `libgiognutls.dll` as a first-class deliverable — it's the specific DLL the ROADMAP calls out, and historically the miss that makes souphttpsrc fail silently on Windows.
- Iteration loop is paste-driven: Claude updates the `.spec`, user runs on the VM, pastes stdout/stderr. Target ≤5 iterations before the spike is considered "stuck" and needs a scope revisit.

</specifics>

<deferred>
## Deferred Ideas

- Windows 10 validation — revisit if Phase 44 surfaces a Win10-specific issue
- HLS / Twitch / yt-dlp / cover-art / ICY-tag smoke coverage on Windows — Phase 44 smoke test scope
- NSIS or Inno Setup installer authoring — Phase 44 (PKG-02)
- Single-instance enforcement on Windows — Phase 44 (PKG-04)
- Windows SMTC media keys — Phase 43.1 (depends on this spike's confirmed runtime)
- Linux ↔ Windows settings-export round-trip UAT — Phase 44 amended success criterion
- `CREATE_NO_WINDOW` subprocess helper — Phase 44 (PKG-03), current state is zero subprocess launches so may be retired
- Auto-updater / code signing / Start Menu + Desktop shortcut polish — post-v2.0

</deferred>

---

*Phase: 43-gstreamer-windows-spike*
*Context gathered: 2026-04-19*
