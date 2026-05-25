# Phase 57: Windows Audio Glitch + Test Fix - Context

**Gathered:** 2026-05-02
**Updated:** 2026-05-03 — post-diagnostic rescope (D-11..D-15 added; Phase Boundary "Volume half" reframed cross-platform; affected In Scope / Out of Scope bullets updated). See `57-DIAGNOSTIC-LOG.md` §"In-session scope expansion (2026-05-03)" for the source-of-truth narrative.
**Status:** Ready for planning (rescoped — Plans 57-03/04/05 to be regenerated; 57-01/02 already complete and preserved)

<domain>
## Phase Boundary

Two narrowly-scoped Windows-side fixes carried forward from Phase 44, parallel in shape to Phase 56:

1. **WIN-03 — Audio pause/resume glitch + ignored volume slider on Windows.**
   - **Glitch half (Windows-only):** Pressing Pause and then Resume on a playing stream on Windows currently produces an audible pop, gap, or restart artifact. Linux is clean. Phase produces parity (no audible artifact on Windows).
   - **Volume half (cross-platform — see D-11):** `playbin3.volume` resets on every PLAYING transition (NULL→PLAYING from pause/resume + failover, **and** the GStreamer-internal PAUSED→PLAYING auto-rebuffer recovery), silently dropping the slider's last value at the audio path. Windows hits it more often (buffer pressure); Linux exhibits on flaky-network buffer drops. The user-visible symptom is "slider doesn't take effect" on Windows and "audio jumps to 100% after a buffer drop" on both platforms. Phase ships a single bus-message `STATE_CHANGED` hook on `playbin3` that re-applies `self._volume` on every transition to PLAYING (D-12 hook site; D-13 resolves D-06 = Option A; D-14 expands the Linux regression-guard scope).

2. **WIN-04 — `test_thumbnail_from_in_memory_stream` is awaitable.** The test currently fails because `_build_winrt_stubs()` in `tests/test_media_keys_smtc.py` makes `DataWriter().store_async` a plain `MagicMock`, which is not awaitable. `_build_thumbnail_ref` runs `asyncio.run(_await_store(writer))` → `await writer.store_async()` → `TypeError: object MagicMock can't be used in 'await' expression`. Replace with `AsyncMock` so the test passes on Linux CI.

**In scope:**
- ✓ A Win11 VM diagnostic session to read back actual audio sink behavior + volume property persistence across `NULL → PLAYING` transitions, per D-04 / D-05. **COMPLETE 2026-05-03 — see `57-DIAGNOSTIC-LOG.md`. Sink confirmed `wasapi2sink`; `playbin3.volume` resets `0.5 → 1.0` on rebuild; D-13 resolves D-06 = Option A.**
- Code change for the cross-platform post-rebuild volume reset: bus-message `STATE_CHANGED` handler on `playbin3` (D-12 hook site) that re-applies `self._volume` to `playbin3.volume` on every transition to PLAYING. D-06 = Option A (D-13). Lives in shared `player.py`; ships cross-platform by design.
- Code change to fix the audible glitch on pause/resume on Windows — Phase 52 EQ ramp template (`musicstreamer/player.py:160-163, 683-685, 746-786`) wrapped around `playbin3.volume` (D-15). Single property surface (sink confirmed `wasapi2sink` honors `playbin3.volume` natively).
- A pytest regression guard on Linux CI for the volume-property-persistence half (D-07 + D-14): assert that `playbin3.volume == self._volume` after **every** transition to PLAYING (state-changed bus message), not just `_set_uri` — covers NULL→PLAYING, PAUSED→PLAYING, and any future PLAYING-arrival path. Audible-glitch half stays VM-UAT-only (perceptual, not unit-testable).
- Replace `MagicMock` with `AsyncMock` for `DataWriter().store_async` in `tests/test_media_keys_smtc.py::_build_winrt_stubs` so `test_thumbnail_from_in_memory_stream` passes (D-08).
- Win11 VM UAT covering both halves of WIN-03 (no audible artifact on pause/resume; slider takes effect immediately).
- Linux full test-suite green check post-WIN-04 patch.

**Out of scope:**
- DI.fm HTTPS-fallback policy + SMTC Start Menu / AUMID display — Phase 56 (just shipped 2026-05-01).
- Buffer-underrun resilience for intermittent dropouts — Phase 62 (separate roadmap entry).
- AAC playback debug on Windows — Phase 69.
- Hi-res indicator — Phase 70.
- Linux audio-path **refactoring**. The volume-reset fix (D-12 bus-message hook) DOES land cross-platform (D-11 scope), but is **additive** — a new `STATE_CHANGED` handler in shared `player.py`, not edits to existing Linux pause/resume / slider code paths. The Linux regression guard (D-14) verifies "no regression of pause/resume or steady-state slider behavior".
- Switching audio sinks on Windows. Diagnostic confirmed the conda-forge GStreamer 1.28.x sink is `wasapi2sink` (Step 1 readback) and that it honors `playbin3.volume` natively, so the fix writes to `playbin3.volume`; no sink change.
- Refactoring `pause()` to use `Gst.State.PAUSED` or `Gst.State.READY`. Live network streams cannot be true-paused (server keeps pushing data; buffer overflows). NULL-on-pause stays. The glitch fix is "make NULL→PLAYING not pop", not "stop using NULL".
- Audit / hardening of every winrt async-method mock in `_build_winrt_stubs`. WIN-04 fix is targeted at the one failing test (D-09 — minimal patch).

</domain>

<decisions>
## Implementation Decisions

### WIN-03 — Volume slider on Windows (diagnose-first)

- **D-01: Diagnose before changing code.** Like Phase 56 D-07, the wiring on the Linux side is correct — `set_volume()` writes `playbin3.volume` and the slider connects to it via `now_playing_panel.py:330`. The Windows-only failure means the cause is environmental (sink-selection, property-loss-on-NULL, or sink-internal-volume drift), not a Linux code bug. First action is a Win11 VM session that reads back actual state and picks the fix shape with evidence.
- **D-02: Linux behavior is the parity target, not a refactoring source.** `set_volume` on Linux is a single-line `pipeline.set_property("volume", v)` and works. Whatever ships on Windows must keep that one-line write working unchanged on Linux.
- **D-03: Phase 56 D-04 invariant preserved.** The DI.fm rewrite call at the top of `_set_uri` (`uri = aa_normalize_stream_url(uri)`) MUST remain the first line of `_set_uri` regardless of what the volume fix adds. Any WIN-03 patch that touches `_set_uri` keeps the rewrite call as the very first executable line.

### WIN-03 — Diagnostic checklist (run on Win11 VM, in order)

- **D-04: Minimal evidence set.** Three readbacks before picking the fix shape:
  1. **Which audio sink is selected.** Read `pipeline.get_property("audio-sink")` after `set_state(PLAYING)` reaches `GST_STATE_PLAYING`. Capture the sink's `gst-element-name` (e.g., `wasapi2sink`, `directsoundsink`, `autoaudiosink` chained to one of them). One log line is enough.
  2. **`playbin3.volume` property value before/after a NULL→PLAYING cycle.** Set volume to 0.5 via the slider. Log `pipeline.get_property("volume")`. Press Pause (NULL). Press Resume (rebuild → PLAYING). Log `pipeline.get_property("volume")` again. If the second readback is 1.0, the property is being lost on rebuild → fix is a one-line re-apply (D-06 option A). If it stays 0.5 but audio is still full-volume, the sink is not honoring `playbin3.volume` → fix is an explicit `volume` element (D-06 option B).
  3. **Slider effect mid-stream.** While playing, move the slider from 100% → 0% → 50%. Confirm whether the audible level changes. If yes, the property write reaches the audio path and the bug is "post-rebuild only"; if no, the property is being ignored entirely and the bug is "always" — same disambiguation but different prior between A and B.
- **D-05: Diagnostic log artifact.** Capture readbacks in `57-DIAGNOSTIC-LOG.md` (Phase 56-03 pattern). Even if the fix is one line, the log gives a future Windows-audio bug a starting point with data, not zero.

### WIN-03 — Code change scope (decided post-diagnostic)

- **D-06: Two candidate fix shapes; D-04 picks between them.**
  - **Option A — Re-apply volume after NULL transition.** If D-04 step 2 shows `playbin3.volume` resets to 1.0 across NULL→PLAYING: add `self._pipeline.set_property("volume", self._volume)` to the end of `_set_uri()` (after `set_state(PLAYING)`), so every rebuild reseats the slider's last value. One line, smallest blast radius, no Linux-side change in behavior (Linux already retains the property; the re-write is a no-op there).
  - **Option B — Explicit `volume` element in `playbin3.audio-filter`.** If D-04 step 2 shows `playbin3.volume` retains 0.5 but audio plays at full level on Windows (sink ignoring it): insert a `volume` GstElement in `playbin3.audio-filter`, mirror the Phase 47.2 EQ slot pattern, and have `set_volume()` write to that element instead of `playbin3.volume`. Larger change but durable across any sink choice.
  - Decision is data-driven, not anticipatory. Planner picks A or B (or a hybrid) after diagnostic readbacks land.

### WIN-03 — Pause/resume audible-glitch fix

- **Claude's discretion.** Glitch shape is sink-mediated and decided after D-04 step 1 names the actual sink. Most likely fix is a thin smoothing wrapper (short volume mute or fade across the NULL→PLAYING transition window in `_set_uri` / `pause()`), but the exact mechanism — sink-side, `playbin3.volume`-side, or `volume`-element-side — depends on which fix shape WIN-03 volume picks (A or B). Planner produces the smoothing shape that composes with the chosen volume fix without double-writing the volume property.
- **NULL stays.** `pause()` continues to use `Gst.State.NULL` (live streams can't be true-paused; buffer would overflow). The glitch fix smooths the rebuild, it does not avoid it.

### WIN-03 — Verification scope

- **D-07: VM UAT + Linux CI guard.** Two-pronged:
  - **Win11 VM UAT** for the perceptual / audible-glitch half AND the volume-slider-takes-effect half. Same UAT pattern as Phase 56 D-11.
  - **Linux pytest regression guard** for the volume-property-persistence half: a `tests/test_player_*.py` test that calls `Player.set_volume(0.5)`, drives `_set_uri("http://example.com/stream.mp3")` (via the existing `playbin3` mock pattern in the player tests), and asserts the player's volume value reaches the chosen target (Option A: `playbin3.volume == 0.5` after the rebuild; Option B: the `volume` element receives 0.5). Catches the future regression of "contributor adds another `set_state(NULL)` site and forgets to re-apply volume" without needing a Windows CI runner.

### WIN-04 — AsyncMock fix

- **D-08: Replace `MagicMock` with `AsyncMock` for `store_async`.** In `tests/test_media_keys_smtc.py::_build_winrt_stubs`, the `DataWriter` mock currently has `store_async` as an implicit `MagicMock` attribute. Make `DataWriter().store_async` an `AsyncMock` so `await writer.store_async()` resolves cleanly. Implementation choice (planner decides exact line): either change the `DataWriter` MagicMock to set `return_value.store_async = AsyncMock()`, or use `MagicMock(spec=...)` if a winrt-side spec exists. Either way the test asserts pass without changing the production code path.
- **D-09: Minimal patch — only `store_async`.** Do NOT audit or harden the rest of `_build_winrt_stubs` for hypothetical future async winrt methods. There is exactly one currently-awaited winrt method in `smtc.py` (`writer.store_async()` in `_await_store`); other winrt calls in `_build_thumbnail_ref` and `publish_metadata` are synchronous. Future async methods get AsyncMock as they're added; no anticipatory work this phase.
- **D-10: Production code unchanged.** WIN-04 is a test-only fix. `musicstreamer/media_keys/smtc.py` is not edited. The production `_await_store` + `asyncio.run(_await_store(writer))` path is correct (Phase 43.1 UAT validated it on real winrt).

### Post-diagnostic resolution (added 2026-05-03 — supersedes pre-diagnostic decisions where noted)

> **Source of truth:** `57-DIAGNOSTIC-LOG.md` (D-04 readbacks + §"In-session scope expansion (2026-05-03)"). The pre-diagnostic decisions D-01..D-10 above are preserved as audit trail; the items below resolve their open variables.

- **D-11: Bug scope is cross-platform — supersedes D-01's "Windows-only" framing.** The volume-reset surface manifests on the GStreamer-internal PAUSED→PLAYING auto-rebuffer recovery path on **both** Windows and Linux; D-01 audited application code correctness only, not per-state-transition runtime behavior. Windows hits the surface more frequently (heavier buffer pressure). Linux exhibits on flaky-network buffer drops. **Implication for plans:** drop "Windows-only" framing for the volume half across PLAN frontmatter, must_haves, and tags.

- **D-12: Hook site is bus-message `STATE_CHANGED` on the `playbin3` element — supersedes D-06 Option A's "tail of `_set_uri`" hook site.** The original Option A would have missed the GStreamer-internal PAUSED→PLAYING rebuffer path (it bypasses `_set_uri` entirely — `playbin3` auto-pauses when buffer drops below threshold and auto-resumes when refilled, without revisiting application code). The chosen hook joins the existing `message::error` / `message::tag` / `message::buffering` family at `player.py:134-136` and re-applies `self._volume` to `playbin3.volume` on every transition to PLAYING (catches NULL→PLAYING, PAUSED→PLAYING, and any future PLAYING-arrival path). **Implication for plans:** Plan 57-03 wires the new bus-message handler; do NOT add a tail-of-`_set_uri` re-apply (would double-write).

- **D-13: D-06 selected = Option A — single mechanism, re-apply property.** Diagnostic Step 2 readback `0.5 → 1.0` after NULL→PLAYING with audible half→full corroboration is decisive; Step 3 (slider always responsive mid-stream) confirms `wasapi2sink` honors the property in steady state — only the rebuild path drops it. **Option B (explicit `volume` GstElement in `playbin3.audio-filter`) and hybrid are ruled out.** **Implication for plans:** ship `self._pipeline.set_property("volume", self._volume)` in the bus-message handler; do NOT introduce a `volume` GstElement; do NOT establish `self._volume_element` invariant (it was Option B / hybrid scaffolding from the pre-diagnostic 57-03-PLAN.md and is no longer needed).

- **D-14: Linux regression-guard scope expands — supersedes D-07's "after `_set_uri`" assertion.** Test asserts `playbin3.volume == self._volume` after **every** transition to PLAYING (state-changed bus message), not just `_set_uri`. Mirror of D-12 hook site. Same shape as the original D-07 guard, broader assertion. **Implication for plans:** Plan 57-03's Linux pytest drives the bus-message dispatch (or directly invokes the handler) and asserts the re-apply for both NULL→PLAYING and PAUSED→PLAYING transitions.

- **D-15: Glitch-fix smoothing target = `playbin3.volume`, ramp template = Phase 52 EQ ramp — resolves the "Pause/resume glitch fix mechanism" Claude's Discretion item.** Sink confirmed `wasapi2sink` (Step 1) honors `playbin3.volume` natively — single property surface. Phase 52 EQ ramp template at `musicstreamer/player.py:160-163, 683-685, 746-786` (QTimer-driven 8-tick fade: current → 0 → state-bracket → 0 → current) wraps `playbin3.volume` writes. **Composes with D-12 without double-writing:** both target `playbin3.volume`; the smoothing wrapper writes ramped values during the transition window, the bus-message handler writes `self._volume` once on PLAYING arrival. Plan 57-04 picks the exact ramp shape (cycle count, tick interval) that matches Win11 sink latency.

### Claude's Discretion

- ~~**Pause/resume glitch fix mechanism.** User skipped this gray area in the discuss-phase selection. Planner chooses the smoothing approach (sink-volume mute window, `playbin3.volume`-side fade, or `volume`-element ramp) based on D-04 step 1 sink identity and the WIN-03 volume fix shape (A or B).~~ **Resolved by D-15** — sink = `wasapi2sink`, smoothing target = `playbin3.volume`, ramp = Phase 52 EQ ramp template. Plan 57-04 picks the exact ramp shape (cycle count, tick interval) that matches Win11 sink latency; that's the only sub-decision left.
- **Glitch fix verification.** Linux pytest of "no extra audible-glitch state" doesn't really exist — perceptual checks live on the VM. Planner may add a structural guard (e.g., a test that asserts the smoothing wrapper is invoked on `_set_uri`) but this is a nice-to-have, not a blocker.
- **Exact name + location of the diagnostic log.** `57-DIAGNOSTIC-LOG.md` next to `57-CONTEXT.md` is the proposed location, mirroring `56-03-DIAGNOSTIC-LOG.md`. Planner can adjust if a per-plan location fits better.
- **AsyncMock import location.** Top-of-file `from unittest.mock import AsyncMock` vs. inline import in `_build_winrt_stubs`. Either works; planner picks per existing conventions in `tests/test_media_keys_smtc.py`.

### Folded Todos

None — STATE.md `Pending Todos` lists three notes (`2026-03-21-sdr-live-radio-support.md`, `2026-04-03-station-art-fetching-beyond-youtube.md`, plus a third unrelated to Windows audio or SMTC tests).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-level
- `.planning/REQUIREMENTS.md` — WIN-03, WIN-04 (both pending, both this phase).
- `.planning/ROADMAP.md` — Phase 57 entry: 4 success criteria (no audible glitch on pause/resume on Windows; volume slider takes effect on Windows; `test_thumbnail_from_in_memory_stream` passes; full test suite passes).
- `.planning/PROJECT.md` — v2.1 milestone shape; "Phase 44 carry-forward (Windows polish)" bullet list explicitly names both bugs.
- `.planning/STATE.md` — current position (Phase 57 executing — Wave 1 complete: 57-01 done + 57-02 diagnostic done; 57-03/04/05 pending replan).

### Phase 57 — In-phase artifacts (rescope source of truth)
- `.planning/phases/57-windows-audio-glitch-test-fix/57-DIAGNOSTIC-LOG.md` — D-04 readbacks + D-06 decision (Option A) + glitch hypothesis + §"In-session scope expansion (2026-05-03)". Authoritative for D-11/D-12/D-13/D-14/D-15.
- `.planning/phases/57-windows-audio-glitch-test-fix/57-01-SUMMARY.md` — WIN-04 AsyncMock fix shipped (test passes on Linux CI). WIN-04 is **complete**; do not re-plan.
- `.planning/phases/57-windows-audio-glitch-test-fix/57-02-SUMMARY.md` — Diagnostic complete; concretely names sink (`wasapi2sink`), hook site (bus-message `STATE_CHANGED`), and scope (cross-platform). Names the affected files for downstream plans.
- `.planning/phases/57-windows-audio-glitch-test-fix/57-PATTERNS.md` — File-level analog map (still accurate; bus-message hook reuses existing handler-family idiom at `player.py:134-136`).

### Phase 56 — Sibling Windows phase (just shipped, locks invariants this phase MUST preserve)
- `.planning/phases/56-windows-di-fm-smtc-start-menu/56-CONTEXT.md` — D-04 (DI.fm rewrite at `_set_uri` top); D-11 (Win11 VM UAT pattern); D-08 (diagnostic checklist pattern).
- `.planning/phases/56-windows-di-fm-smtc-start-menu/56-03-DIAGNOSTIC-LOG.md` — diagnostic log format reference for D-05.

### Phase 43 — GStreamer Windows spike (Windows audio environment)
- `.planning/milestones/v2.0-phases/43-gstreamer-windows-spike/43-SPIKE-FINDINGS.md` — Windows GStreamer 1.28.x sink selection; conda-forge build env; OpenSSL TLS backend. "Known Gotchas" table is the starting point if the diagnostic surfaces unexpected sink behavior.
- `.claude/skills/spike-findings-musicstreamer/references/windows-gstreamer-bundling.md` — auto-loaded skill; Windows GStreamer plugin set + DLL bundling rules.
- `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md` — locked Qt/GLib bus rules; relevant if any pause/resume code adds bus-handler work.

### Phase 43.1 — Windows Media Keys + SMTC (winrt async pattern origin for WIN-04)
- `.planning/milestones/v2.0-phases/43.1-windows-media-keys-smtc/43.1-CONTEXT.md` — winrt async drives via `asyncio.run`, Pitfall #3 (STA + `store_async().get()` deadlock), AsyncMock as the natural mock for `IAsyncOperation`.

### Phase 47.2 — EQ in `playbin3.audio-filter` (precedent for WIN-03 Option B)
- `.planning/milestones/v2.0-phases/47.2-autoeq-parametric-eq/` — D-01 inserts the equalizer-nbands element in `playbin3.audio-filter`. Same slot pattern is the template if WIN-03 picks Option B (explicit `volume` element).
- `musicstreamer/player.py:113` — comment "Phase 47.2 D-01: equalizer-nbands in playbin3.audio-filter slot" — concrete reference for the pattern.

### Source files this phase touches
- `musicstreamer/player.py` — `set_volume` (line 218); `pause` (line 299); `_set_uri` (line 485); `_try_next_stream` (line 449); `play` (line 256); audio-filter slot setup (line 113).
- `musicstreamer/ui_qt/now_playing_panel.py` — `_on_volume_changed_live` (line 564); slider construction + connection (lines 326, 330).
- `musicstreamer/media_keys/smtc.py` — `_await_store` (line 52); `_build_thumbnail_ref` (line 210). NO production edits — WIN-04 is test-only.
- `tests/test_media_keys_smtc.py` — `_build_winrt_stubs` (line ~93); `test_thumbnail_from_in_memory_stream` (line 438). The `DataWriter = MagicMock(name="DataWriter")` line at 95 is the WIN-04 fix site.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`Player.set_volume`** (`musicstreamer/player.py:218`) — single-source-of-truth volume API. Already correct on Linux. Whatever WIN-03 ships keeps this signature unchanged.
- **`Player._volume`** (`musicstreamer/player.py:196`) — held on the player object, survives pipeline rebuilds. Option A in D-06 already has the value to re-apply; no extra state needed.
- **`playbin3.audio-filter` slot** (`musicstreamer/player.py:113`) — Phase 47.2 already pioneered this slot for the EQ element. Option B in D-06 inserts a `volume` GstElement in the same slot using the same idiom.
- **Player tests with mocked `playbin3`** — `tests/test_player_*.py` (multiple files) use a mocked pipeline. The D-07 Linux CI regression guard reuses the existing mock pattern; no new fixture work.
- **`unittest.mock.AsyncMock`** — stdlib, no new dependency. Already present in Python 3.8+; project runs 3.11+.
- **`_await_store(writer)`** (`musicstreamer/media_keys/smtc.py:52`) — production code already correct; D-10 leaves it untouched.

### Established Patterns
- **Diagnose-first on Win11 VM** — Phase 56 D-07/D-08 set the precedent: when a Windows-only bug has correct-looking Linux code, read back actual state on the VM before changing code. WIN-03 D-01/D-04 follows this verbatim.
- **Diagnostic log artifact** — `56-03-DIAGNOSTIC-LOG.md` captures the readbacks. WIN-03 D-05 produces `57-DIAGNOSTIC-LOG.md` in the same shape.
- **Pure-property writes at the playback boundary** — `_set_uri` is the universal funnel for `playbin3` (Phase 56 D-01). Any WIN-03 fix that touches the rebuild lives here, after the existing `aa_normalize_stream_url` rewrite (D-03 invariant).
- **AsyncMock for awaitable winrt methods** — Phase 43.1's winrt async pattern (`asyncio.run(_await_store(writer))`) implies `AsyncMock` is the right mock shape for any `IAsyncOperation`-returning method. WIN-04 D-08 applies this consistently.
- **VM-UAT-only for perceptual + Linux-CI for structural** — Phase 56 split SMTC display (perceptual) vs URL helper (CI-testable). WIN-03 D-07 splits audible glitch (perceptual) vs volume property persistence (CI-testable).

### Integration Points
- **`_set_uri` call sites** — `play` (initial), `_on_youtube_resolved`, `_on_twitch_resolved`, `_try_next_stream` (failover). All four already funnel through `_set_uri`, so any single-point fix in `_set_uri` covers them all (Phase 56 D-01 funnel argument carries over).
- **Slider → `set_volume` connection** — `now_playing_panel.py:330` (`valueChanged → _on_volume_changed_live → player.set_volume`). Bidirectional in spirit but write-only in code; WIN-03 does not change the UI side.
- **`tests/test_media_keys_smtc.py::_build_winrt_stubs`** — single fixture-builder for all 20+ SMTC tests. Touching only the `DataWriter` mock keeps blast radius minimal (D-09).
- **No DB / persistence touch** — WIN-03 is pure runtime audio behavior. WIN-04 is pure test-side. No schema changes, no settings export/import surface area.

</code_context>

<specifics>
## Specific Ideas

- **Linux is the parity target.** "Match Linux behavior" is the explicit success criterion in ROADMAP.md (#2 — "Moving the volume slider on Windows changes the playback volume immediately (matches Linux behavior)"). Planner should not invent new behavior, only close the gap.
- **NULL-on-pause is a deliberate constraint, not an accident.** Live network streams cannot be true-paused; the phase fixes the audible side-effect of NULL, not NULL itself.
- **Phase 56 D-04 first-line invariant** in `_set_uri` is non-negotiable — DI.fm rewrite happens before any WIN-03 work touches the rebuild path.
- **Phase 43.1's `_await_store` pattern is correct production code** — WIN-04 only fixes the mock, never touches `smtc.py`.
- **Diagnostic-first cadence** — same as Phase 56: VM session captures readbacks → planner picks fix shape → patch + UAT. No speculative refactoring.

</specifics>

<deferred>
## Deferred Ideas

### Deferred to future phases / re-visit later
- **Refactor `pause()` to use `Gst.State.READY` for a lighter teardown** — would retain caps negotiation and possibly avoid the audible glitch entirely without a smoothing wrapper. Skipped because (a) the user did not select this gray area for discussion, (b) it changes Linux behavior that already works, (c) live streams may still misbehave under READY (server keeps pushing). Re-visit only if the chosen smoothing wrapper proves insufficient.
- **Audit `_build_winrt_stubs` for all current and future awaitable winrt methods.** D-09 explicitly scopes WIN-04 to `store_async` only. If a second async winrt method enters production code later, it gets its own AsyncMock as it lands; no anticipatory hardening this phase.
- **Switch Windows audio sink** (e.g., from default `wasapi2sink` to `directsoundsink` or vice-versa) — out of scope per Phase 43 disposition; the diagnostic only reads the current sink, it does not change it.
- **Volume-slider regression guard on Windows CI** — would catch the bug on the actual platform, not via Linux mock. No Windows CI runner exists today; deferred until the project gains one (currently personal-project, no CI matrix planned).

### Out-of-phase (already roadmapped)
- **Phase 56** — DI.fm HTTPS rewrite + SMTC AUMID. Shipped 2026-05-01.
- **Phase 62** — Audio buffer-underrun resilience for intermittent dropouts (a different Windows audio bug class).
- **Phase 69** — AAC streams not playing in Windows (likely missing GStreamer plugin in the bundle).
- **Phase 70** — Hi-res indicator for streams.

### Reviewed Todos (not folded)
None reviewed — STATE.md `Pending Todos` are unrelated to Windows audio or SMTC tests.

</deferred>

---

*Phase: 57-windows-audio-glitch-test-fix*
*Context gathered: 2026-05-02*
