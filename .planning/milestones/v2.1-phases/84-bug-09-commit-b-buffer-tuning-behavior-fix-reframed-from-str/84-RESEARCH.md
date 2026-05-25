# Phase 84: BUG-09 Commit B — buffer-tuning behavior fix (reframed) - Research

**Researched:** 2026-05-24
**Domain:** GStreamer playbin3 buffer-property propagation semantics; Qt Signal extension carrying Phase 78 patterns forward
**Confidence:** HIGH — every claim that drives a plan decision is backed by direct inspection of `gst-plugins-base/master/gst/playback/{gstplaybin3,gsturidecodebin3}.c` source. The single critical research dependency (D-11 mid-session-write semantics) is RESOLVED with unambiguous evidence: **playbin3 does NOT propagate `buffer-duration` / `buffer-size` mid-session to the active uridecodebin3.** D-11 must use the fallback shape.

## Summary

Phase 84 ships the deferred Commit B half of the Phase 78 two-stage plan. Every UI/Signal/test pattern needed is a copy-edit of Phase 78 Commit A patterns already merged at `player.py:297, 498, 1133-1134`, `main_window.py:382-390`, `now_playing_panel.py:1002-1010, 2936-2938`, and `tests/_fake_player.py:75`. The unique new surface is the buffer-duration adaptive-growth state machine and the playbin3 set_property write-site for the growth steps.

**Three findings drive the plan shape:**

1. **D-11 mid-session-write fallback is REQUIRED, not optional.** `[VERIFIED: gst-plugins-base/master/gst/playback/gstplaybin3.c:2474-2477 + 2169-2170 + 1862-1866]` The `gst_play_bin3_set_property` handlers for `buffer-duration` and `buffer-size` only store the value into the `GstPlayBin3.buffer_duration` / `.buffer_size` struct fields — they make NO `g_object_set` call to propagate to any child element. Compare with `PROP_RING_BUFFER_MAX_SIZE` in the same file, which explicitly `g_object_set`s the value onto `playbin->curr_group->uridecodebin` when active. Therefore: writing `buffer-duration` to a playbin3 already in `GST_STATE_PLAYING` is a silent no-op for the currently-playing stream. The value is consumed only at the next `new_source_handler` construction inside uridecodebin3, which fires on `READY_TO_PAUSED` / `URI_BIND`. **D-11 MUST use the "apply at next URL bind" fallback.** This downgrades adaptive growth from "first underrun → 60s; second underrun → 120s on this stream" to "first cycle_close stages a 60s value; the value applies at the next station change OR the next gapless preroll handoff (Phase 83 path); second cycle_close stages 120s; same story." The user's CONTEXT.md D-11 Discretion bullet anticipated exactly this fallback ("simplify to a single-step 'second URL underruns → next bind gets cap value'" — see §Adaptive Schedule Under Fallback for the concrete recommendation).

2. **D-10 static bump 30s/20MB DOES take effect** because it lands in `Player.__init__` BEFORE the first `set_state(PLAYING)` and BEFORE any uridecodebin3 has been constructed. `[VERIFIED: musicstreamer/player.py:318-319 in __init__]` The set_property calls at `player.py:318-319` run during pipeline construction; the first `_set_uri()` (via `_try_next_stream`) is what triggers uridecodebin3 instantiation, and at that point uridecodebin3 reads the (already-updated) struct field. This is why Phase 16 / STREAM-01's 10s/10MB baseline has been observed to work at all. **D-10 has zero new risk** — it's a literal-value edit at the same construction site.

3. **`GST_PLAY_FLAG_BUFFERING` (0x100) at `player.py:325` IS load-bearing** for D-10 to have any user-visible effect. `[CITED: player.py:320-323 comment + uridecodebin3 source]` Without the flag, playbin3's `use-buffering` propagation to urisourcebin is false → urisourcebin doesn't insert a queue2 → the `buffer-duration`/`buffer-size` values are ignored by the chain entirely (decodebin3's internal multiqueue handles jitter with ~1s capacity). With the flag, uridecodebin3 forwards `use-buffering=TRUE` AND `buffer-duration` / `buffer-size` to urisourcebin at handler-creation time (`gsturidecodebin3.c::new_source_handler`'s `g_object_set` block). The flag must remain UNTOUCHED. Phase 84 does not modify it.

**Primary recommendation:** (1) D-10 literal-edit `constants.py:55-56` (zero behavioral risk). (2) Reframe D-11 to "next-bind" semantics: stage `_pending_buffer_duration_s` on cycle close, apply it via `self._pipeline.set_property("buffer-duration", new * Gst.SECOND)` inside `_try_next_stream` and `_on_preroll_about_to_finish` BEFORE the URI write — the next uridecodebin3 will read the new value. (3) D-12 always-visible stats row + new `buffer_duration_changed = Signal(int)` mirroring Phase 78's `underrun_count_changed` exactly (DirectConnection — both ends main-thread). (4) Source-grep gate banning the `playbin2`-era `connection-speed`-as-`connection_speed` and the legacy `playbin` flag bit `0x040` (deprecated `GST_PLAY_FLAG_DEINTERLACE`) misspellings on the playbin3 set_property call sites — these are the canonical "looks-like-playbin1.x but should-fail-on-playbin3" footguns.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Framing**
- **D-09:** Reframe target as "both clusters" (2 YouTube long events + 3 SomaFM long events from harvest week), not "YouTube only." Tune for whichever cluster has worse magnitude OR higher count. ROADMAP.md entry is NOT amended (user choice — this CONTEXT.md is the corrected forward-going source).

**Static bump**
- **D-10:** **`BUFFER_DURATION_S` 10 → 30; `BUFFER_SIZE_BYTES` 10MB → 20MB.** Both knobs change in `musicstreamer/constants.py:55-56`, in a single coordinated edit. 3× duration headroom comfortably absorbs the observed 7.4s YouTube worst case. 20MB byte cap so the byte limit doesn't constrain the duration target at high-bitrate sources (FLAC stations ~1.4Mbps would hit a 10MB cap before 30s; 20MB gives ~110s worst-case headroom). The misleading inline `# 5 MB` comment on `BUFFER_SIZE_BYTES` is wrong even pre-change (it's 10MB); fix as a drive-by.

**Adaptive growth**
- **D-11:** **Ship full adaptive growth with mid-session `set_property` writes.** Schedule: 30 → 60 → 120s (cap). First in-session `cycle_close` triggers the 60s write; second triggers the 120s write; subsequent underruns stay at 120s. Reset to 30s on `_try_next_stream` URL-bind (mirrors Phase 47.1 D-14 sentinel-reset). Instance fields `_current_buffer_duration_s: int = BUFFER_DURATION_S` plus per-session growth-step counter; both reset at URL bind, not at app launch.
  - **Research dependency:** Verify playbin3 honors mid-session writes to `buffer-duration` — **RESOLVED below in §D-11 Research Dependency Resolution. Mid-session writes do NOT take effect; fallback path is mandatory.**
  - **Fallback if mid-session writes don't work:** Apply new `buffer-duration` only at next URL bind in `_try_next_stream` (still adaptive, just at station-boundary granularity). The Discretion section of D-11 below explicitly authorizes the planner to "simplify to a single-step 'second URL underruns → next bind gets cap value'" under the fallback path.

**UI / observability**
- **D-12:** **Always-visible `Buffer: Xs` row in stats-for-nerds.** Format: `Buffer: 30s` baseline; `Buffer: 60s (adapted)` / `Buffer: 120s (adapted)` after growth fires. Row lives in `_build_stats_widget` at `now_playing_panel.py:2936-2938+1` (immediately after the existing Phase 78 `Underruns: 0` row). Uses `_MutedLabel`. Always-shown rather than adapted-only. New Player Signal — bias toward `buffer_duration_changed = Signal(int)` (seconds), emitted on every change to `_current_buffer_duration_s` (initial set, growth steps, URL-bind reset).

**Closure / verification**
- **D-13:** **VERIFICATION.md with waived gate + monitor plan.** Write `84-VERIFICATION.md` that:
  1. States the Phase 78 D-06 `M < N AND median lower` gate is **waived** (12 events / 7 days = insufficient sample).
  2. Documents "ship + monitor": 2-week post-ship window comparing `~/.local/share/musicstreamer/buffer-events.log` against the harvest-week baseline.
  3. Follow-up trigger: ≥3 long events (>1s) with `min_percent=0` in 2-week window, OR any `recovered` event >10s, OR ≥1 `cause_hint=network` event → open follow-up phase for reconnect-on-stall.
  4. BUG-09 SC #3 (behavior side) closes on the ship commit; monitor window is forward-looking.

### Claude's Discretion (RESEARCH recommendations below carry these forward)

- **Counter Signal naming.** D-12 suggests `buffer_duration_changed = Signal(int)`. **RESEARCH RECOMMENDS: keep this name verbatim** — it mirrors Phase 78's `underrun_count_changed` (verb-tense + noun-of-what-changed) cleanly, no collision with existing Signals (`grep -nE "^\\s*[a-zA-Z_]+\\s*=\\s*Signal\\(" musicstreamer/player.py` returns 20 names, none of them `buffer_duration_changed`).
- **Growth-step counter location.** Could live on `Player` directly or on `_BufferUnderrunTracker`. **RESEARCH RECOMMENDS: Player directly** (see §Architecture Patterns §1) because the per-URL reset must happen in `_try_next_stream` alongside `_last_buffer_percent = -1` and `self._tracker.bind_url(...)`, and the property-write to `self._pipeline` must happen there too — same physical block. Putting the counter on the tracker forces an extra `self._tracker._growth_step = 0` access through tracker internals OR a tracker-public method just for reset, neither of which is cleaner than `self._growth_step = 0` adjacent to the URL-bind block.
- **Player.py legacy comment freshening.** D-10 Discretion. **RESEARCH RECOMMENDS: freshen as a drive-by** — the existing comment at `player.py:320-323` is technically correct ("Without the flag, the properties are ignored") but it leaves the false impression that WITH the flag, they're fully honored mid-session. Rewrite to: "Without `GST_PLAY_FLAG_BUFFERING` (0x100), playbin3 bypasses queue2 — buffer-duration/buffer-size silently ignored. With the flag, both properties propagate to uridecodebin3 → urisourcebin → queue2 at URI-bind time (not mid-session — they are READ from the playbin3 struct fields by uridecodebin3's `new_source_handler` per `gsturidecodebin3.c` master; subsequent set_property writes to playbin3 take effect only at the next URI bind)."
- **Stats row exact label string.** D-12 sketches `Buffer: 30s`. **RESEARCH RECOMMENDS: use "Buf duration" as the row LABEL (two-column shape, matching the existing "Buffer" / `[progressbar]` row above), with `30s`, `60s (adapted)`, `120s (adapted)` as the VALUE cell text.** Rationale: the existing row uses label `"Buffer"` for the progress bar; a second row with label `"Buffer"` would shadow it visually. "Buf duration" disambiguates and stays narrow.
- **Reset granularity under fallback.** D-11 Discretion explicitly allows simplification under the fallback path. **RESEARCH RECOMMENDS: keep the 30→60→120 three-step schedule with NEXT-BIND application** (see §Adaptive Schedule Under Fallback). The user is on the same URL when the underrun fires; the growth-step bump fires immediately and is REFLECTED in the stats row right away, but the `set_property` call to playbin3 only takes effect at the next URL bind. The user sees `Buffer: 60s (adapted)` instantly (correct — the value is staged); the value applies to playback when they next change stations or when the same station's gapless preroll handoff fires. This is the cleanest semantic given the fallback constraint.

### Deferred Ideas (OUT OF SCOPE)

- Reconnect-on-stall logic — Phase 78 deferred; still deferred. Trigger: D-13 monitor thresholds.
- `low-percent` / `high-percent` queue2 watermark tuning — Phase 78 deferred; still deferred.
- Per-station configurable buffer override — Phase 78 rejected; not reopened.
- Synthetic throttled-network repro fixture — Phase 78 deferred; not needed under "ship + monitor".
- Distinct `Reconnecting…` toast — Phase 78 rejected; silent-recovery philosophy holds.
- ROADMAP.md entry harvest-summary amendment — user choice.
- TimedRotatingFileHandler / persistent counter / in-app log viewer — Phase 78 rejected/deferred.
- Watchdog cycle timeout that auto-forces failover — Phase 62 rejected.
</user_constraints>

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **BUG-09 (Commit B half)** | Behavior-side closure of BUG-09 SC #3 — buffer apparatus tuned to the harvest data; static bump + adaptive growth + visible buffer-state surfacing | D-10 static bump verified safe (lands at construction site, takes effect at first URI bind). D-11 adaptive growth's mid-session-write premise FALSIFIED by playbin3 source inspection — fallback "apply at next URL bind" is the only viable path (D-11 explicitly authorized this fallback). D-12 stats row + Signal mirror Phase 78 patterns 1:1. D-13 closure waives the original Phase 78 D-06 statistical gate. |

No new REQ-IDs introduced. Closure record lands in `84-VERIFICATION.md` per D-13.

---

## Project Constraints (from CLAUDE.md)

- **Routing:** All GStreamer / playbin3 / Qt-GLib threading research routes to `Skill("spike-findings-musicstreamer")`. `[CITED: ./CLAUDE.md]`
  - `references/qt-glib-bus-threading.md` Rule 2 (queued Signals for cross-thread emission) — the new `buffer_duration_changed = Signal(int)` is emit-from-main-thread, receive-on-main-thread, so **DirectConnection is correct** (matches Phase 78 Commit A precedent at `main_window.py:382-390`). The growth-step state machine is invoked from `_on_underrun_cycle_closed`, which is already a main-thread slot (the queued `_underrun_cycle_closed` connection at `player.py:445-447` marshals from bus-loop → main). NO new bus-loop → main hops are introduced.
- **Deployment target:** Linux Wayland (GNOME Shell), DPR=1.0. `[CITED: MEMORY.md]` Stats-for-nerds row layout already verified on this surface in Phase 47.1; D-12's added row inherits the same `QFormLayout` / `_MutedLabel` shape with zero new surface.
- **Origin remote:** QNAP Gitea with server-side push mirror to GitHub — treat all pushes as public. `[CITED: MEMORY.md]` Phase 84 adds zero new log fields; existing Phase 62 `%r`-quoting of `station_name` / `url` continues to mitigate log injection (T-62-01). No secrets introduced.
- **`feedback_gstreamer_mock_blind_spot.md`** `[CITED: MEMORY.md]` — pipeline mocks pass through any `pipeline.emit(...)` call; add source-level grep gates banning legacy `playbin` 1.x property names on playbin3 code paths. **Phase 84 MUST include this grep gate** — the new mid-session-write paths are the exact "looks-correct against a MagicMock pipeline" surface the memory warns about. See §Pattern 4 / §Common Pitfalls §5 below.
- **`feedback_ui_bug_verify_with_extremes.md`** `[CITED: MEMORY.md]` — sweep widgets through 0%/100% / hidden/shown extremes first. **Not load-bearing for this phase** (the stats row is always-visible per D-12; no toggle-driven layout regression to chase). Documented for completeness.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `BUFFER_DURATION_S` / `BUFFER_SIZE_BYTES` literal values | `musicstreamer/constants.py` | — | Single source of truth for both the construction-time write at `player.py:318-319` AND the new growth-state baseline at `player.py:__init__`; both code sites import from `constants`. |
| Static bump application (D-10) | `player.py` `__init__` pipeline construction | `constants.py` | The construction-site `set_property` at `player.py:318-319` is the only place where playbin3's struct fields are populated BEFORE any uridecodebin3 exists. This is why the static bump takes effect; mid-session writes do not. |
| Growth state machine (D-11) | `player.py` (instance fields + `_on_underrun_cycle_closed` extension) | `_BufferUnderrunTracker` (read-only — the tracker drives the count via cycle_close emissions; tracker does NOT own buffer-duration state per Discretion analysis above) | Cycle-close is the only event that bumps the growth step; state lives next to the cycle counter Phase 78 already added. |
| Mid-session property staging (D-11 fallback) | `player.py._on_underrun_cycle_closed` (stages `_pending_buffer_duration_s`) | `player.py._try_next_stream` + `player.py._on_preroll_about_to_finish` (apply pending value to playbin3 BEFORE `set_property("uri", ...)`) | Two-phase write: cycle_close stages the new value; URI-bind sites apply it. The staged value MUST be written to playbin3 BEFORE the URI write at the bind site, because uridecodebin3 reads playbin3's struct field during its own `new_source_handler` flow which is triggered by the URI write. |
| `buffer_duration_changed = Signal(int)` (main → MainWindow → NowPlayingPanel) | `player.py` (class-level Signal + emit on stage and on apply) | `main_window.py` (DirectConnection wire) + `now_playing_panel.py` (`set_buffer_duration` slot updates the new stats row label) | Mirrors Phase 78 `underrun_count_changed` 1:1 — same emit thread (main), same wire shape (DirectConnection), same UI sink shape (`_MutedLabel.setText`). |
| Stats-for-nerds row (D-12) | `now_playing_panel.py._build_stats_widget` | `_MutedLabel` (theme-flip safety per Phase 47.1 D-10) | One additional `form.addRow(...)` call immediately after the existing Phase 78 `Underruns` row at line 2938, BEFORE `wrapper.setVisible(False)` at line 2941. |
| FakePlayer parity edit | `tests/_fake_player.py` (Phase 77 INFRA-01 drift-guard) | — | Every new `Signal(...)` on Player REQUIRES a parity entry on `FakePlayer` — guarded by `tests/test_fake_player_signal_parity.py`. Add `buffer_duration_changed = Signal(int)` next to existing `underrun_count_changed = Signal(int)` at line 75. |
| Source-grep gate for playbin 1.x footguns | `tests/test_playbin3_property_hygiene.py` (NEW) | — | Defense against the GStreamer-mock-blind-spot memory. Greps `musicstreamer/player.py` for any banned legacy spellings (see §Pattern 4 for the exact pattern set). |
| Closure record (D-13) | `.planning/phases/84-…/84-VERIFICATION.md` (NEW) | — | Documents waived gate + 2-week monitor plan + follow-up trigger thresholds verbatim from CONTEXT D-13. |

---

## D-11 Research Dependency Resolution — playbin3 Mid-Session Write Semantics

**Question (verbatim from CONTEXT D-11):** *Does `self._pipeline.set_property("buffer-duration", new_value * Gst.SECOND)` take effect mid-stream (i.e., without a `set_state(NULL)` → `set_state(PLAYING)` cycle)? Or do these properties only apply at the next URL bind?*

**Answer: Mid-session writes are a silent no-op for the currently-playing stream. The new value takes effect only at the NEXT URI bind.** This is unambiguous from gst-plugins-base source inspection at the May-2026 master branch:

### Evidence Chain

**1. playbin3's `gst_play_bin3_set_property` handlers for `PROP_BUFFER_SIZE` / `PROP_BUFFER_DURATION` ONLY store the value.** `[VERIFIED: https://raw.githubusercontent.com/GStreamer/gst-plugins-base/master/gst/playback/gstplaybin3.c lines ~2474-2477]`

```c
case PROP_BUFFER_SIZE:
  playbin->buffer_size = g_value_get_int (value);
  break;
case PROP_BUFFER_DURATION:
  playbin->buffer_duration = g_value_get_int64 (value);
  break;
```

There is **NO** `g_object_set` call to propagate the new value to `playbin->curr_group->uridecodebin` or any other child element.

**2. Compare with `PROP_RING_BUFFER_MAX_SIZE` in the same handler**, which DOES propagate. `[VERIFIED: same source file]`

```c
case PROP_RING_BUFFER_MAX_SIZE:
  playbin->ring_buffer_max_size = g_value_get_uint64 (value);
  if (playbin->curr_group) {
    GST_SOURCE_GROUP_LOCK (playbin->curr_group);
    if (playbin->curr_group->uridecodebin) {
      g_object_set (playbin->curr_group->uridecodebin,
          "ring-buffer-max-size", playbin->ring_buffer_max_size, NULL);
    }
```

The difference is intentional in the GStreamer codebase — `ring-buffer-max-size` is designed to be mutable at runtime; `buffer-duration` / `buffer-size` are not.

**3. The struct fields are READ in `uridecodebin3.c::new_source_handler`** and pushed to urisourcebin at handler construction. `[VERIFIED: gsturidecodebin3.c source]`

```c
g_object_set (handler->urisourcebin,
    "connection-speed", uridecodebin->connection_speed / 1000,
    "download", uridecodebin->download,
    "use-buffering", uridecodebin->use_buffering,
    "buffer-duration", uridecodebin->buffer_duration,
    "buffer-size", uridecodebin->buffer_size,
    "ring-buffer-max-size", uridecodebin->ring_buffer_max_size, NULL)
```

But — critically — this `g_object_set` only runs at `new_source_handler` invocation time, which happens during the `READY_TO_PAUSED` state transition (i.e., during `setup_next_source` → URI bind). Subsequent writes to playbin3's `buffer-duration` after the handler exists do nothing because playbin3 never re-pushes the value, AND uridecodebin3's own `set_property` for `PROP_BUFFER_*` also just stores into struct without propagation.

**4. Property flags confirm no runtime-mutable contract.** `[VERIFIED: gstplaybin3.c:~1862-1866]`

```c
g_object_class_install_property (gobject_klass, PROP_BUFFER_DURATION,
    g_param_spec_int64 ("buffer-duration", "Buffer duration (ns)",
        "Buffer duration when buffering network streams",
        -1, G_MAXINT64, DEFAULT_BUFFER_DURATION,
        G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS));
```

Flags are `G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS` only. There is no `GST_PARAM_MUTABLE_PLAYING` or `GST_PARAM_MUTABLE_PAUSED` marker. The property is writable but the API contract says nothing about runtime-mutability — and the implementation confirms it isn't runtime-mutable in any propagating sense.

### Implication for D-11

The locked CONTEXT.md D-11 statement *"First in-session underrun bumps live `buffer-duration` 30 → 60s. Second underrun → 120s"* must be re-interpreted under the fallback: the user-facing semantics ("growth happens on cycle close") still hold, but the **value applied to the pipeline takes effect at the next URI bind, NOT immediately on the current stream**.

This is acceptable under the user's own D-11 Discretion explicit authorization: *"Apply new `buffer-duration` only at next URL bind in `_try_next_stream` (still adaptive, just at station-boundary granularity)."* The planner should NOT re-confirm with the user; D-11's fallback is pre-authorized.

### Implementation Pattern (RECOMMENDED — D-11 Fallback)

```python
# musicstreamer/player.py — extension to existing _on_underrun_cycle_closed at line 1113
def _on_underrun_cycle_closed(self, record) -> None:
    self._underrun_dwell_timer.stop()
    _log.info("buffer_underrun ...", ...)        # UNCHANGED (Phase 62)
    self._underrun_event_count += 1               # UNCHANGED (Phase 78 Commit A)
    self.underrun_count_changed.emit(self._underrun_event_count)  # UNCHANGED (Phase 78)
    # Phase 84 / D-11 (fallback path): bump growth step + stage new duration.
    # The staged value will be written to playbin3 by _try_next_stream / preroll handoff
    # BEFORE the next URI bind, per playbin3 source inspection (84-RESEARCH §D-11).
    self._maybe_grow_buffer_duration()

def _maybe_grow_buffer_duration(self) -> None:
    """Phase 84 / D-11: bump growth step 0 → 1 → 2 (cap). Stages the new value
    for the next URI bind to apply via _apply_pending_buffer_duration()."""
    if self._growth_step >= 2:
        return                                     # already at 120s cap
    self._growth_step += 1
    new_s = {1: 60, 2: 120}[self._growth_step]
    self._pending_buffer_duration_s = new_s
    self._current_buffer_duration_s = new_s        # UI reflects the staged value immediately
    self.buffer_duration_changed.emit(new_s)       # stats row updates to "60s (adapted)" / "120s (adapted)"

# Extension at the top of _try_next_stream (line 1146), AFTER set_state(NULL) but BEFORE _set_uri:
def _try_next_stream(self) -> None:
    self._pipeline.set_state(Gst.State.NULL)
    self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
    if not self._streams_queue:
        self.failover.emit(None)
        return
    stream = self._streams_queue.pop(0)
    self._current_stream = stream
    self._last_buffer_percent = -1
    # Phase 84 / D-11: apply ANY pending buffer-duration growth BEFORE binding the new
    # URI — uridecodebin3 reads playbin3's buffer_duration struct field during
    # new_source_handler, which fires on the URI bind below.
    self._apply_pending_buffer_duration_to_pipeline()
    # Phase 84 / D-11: reset growth state for the new URL (per-URL reset, mirrors
    # _last_buffer_percent reset above and tracker.bind_url below).
    self._reset_buffer_duration_to_baseline()
    # ... existing tracker.force_close + tracker.bind_url + ... (UNCHANGED) ...

def _apply_pending_buffer_duration_to_pipeline(self) -> None:
    """Phase 84 / D-11: write any staged buffer-duration to playbin3 BEFORE the
    next URI bind. Mid-session writes are silent no-ops per playbin3 source
    (84-RESEARCH §D-11); the URI bind triggers uridecodebin3.new_source_handler
    which reads playbin3.buffer_duration → pushes to urisourcebin → queue2."""
    if self._pending_buffer_duration_s is None:
        return
    self._pipeline.set_property(
        "buffer-duration", self._pending_buffer_duration_s * Gst.SECOND
    )
    # buffer-size is left at the static D-10 value (20MB) — adaptive growth is
    # duration-only per CONTEXT.md D-11 (no D-11 mention of byte-cap growth).
    self._pending_buffer_duration_s = None

def _reset_buffer_duration_to_baseline(self) -> None:
    """Phase 84 / D-11 per-URL reset (mirrors Phase 47.1 D-14 sentinel reset,
    Phase 62 D-04 _underrun_armed reset)."""
    if self._growth_step == 0 and self._current_buffer_duration_s == BUFFER_DURATION_S:
        return                                     # already at baseline — no-op + no spurious Signal emit
    self._growth_step = 0
    self._current_buffer_duration_s = BUFFER_DURATION_S
    self._pending_buffer_duration_s = BUFFER_DURATION_S  # also reset the pipeline to baseline at next bind
    self.buffer_duration_changed.emit(BUFFER_DURATION_S)
```

Same `_apply_pending_buffer_duration_to_pipeline()` call MUST also fire inside `_on_preroll_about_to_finish` at `player.py:1369` BEFORE the `self._pipeline.set_property("uri", ...)` line — that gapless URI swap is also a "URI bind" in the playbin3 sense and uridecodebin3 will read the staged value.

### Why "stage and apply" rather than "always write inline"

An alternative shape would be: in `_on_underrun_cycle_closed`, write `set_property("buffer-duration", new * Gst.SECOND)` directly. This is **safe** (the property is `G_PARAM_READWRITE`, the write succeeds and updates playbin3's struct field — it's just a silent no-op for the active stream). But mixing "fires on cycle close" with "applies on next bind" buries the timing semantics. The two-phase shape (stage on close → apply at bind) makes the gap visible in the code and gives tests a clean assertion target (`assert mock_pipeline.set_property.call_args_list == [..., call("buffer-duration", 60 * GST_SECOND)]` happens at the right call-site).

### Architectural alternative: byte-pump the property on every cycle close

Considered. Rejected. Writing `set_property("buffer-duration", N)` on every cycle close would correctly stage the value for the next bind, but it loses the per-URL reset semantics — the staged value would persist across station changes unless we ALSO write the baseline on every URL bind. The "stage + apply + reset" three-step pattern is the cleanest expression of the lifecycle and matches the existing Phase 62 `_underrun_armed` reset pattern verbatim.

---

## Standard Stack

### Core (already in pyproject — no new deps)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `gi.repository.Gst` (PyGObject 1.x → GStreamer 1.28.2 on dev box) | system / conda-forge bundle (Phase 43) | `pipeline.set_property("buffer-duration", N * Gst.SECOND)` call site | `[VERIFIED: musicstreamer/player.py:318, 51 import block]` Already exercised by the Phase 16 construction-time write. |
| `PySide6.QtCore.Signal` | already pinned | New `buffer_duration_changed = Signal(int)` | `[VERIFIED: musicstreamer/player.py:241-297, 20 existing Signals]` Identical pattern to Phase 78's `underrun_count_changed`. |
| `pytest` + `pytest-qt` | already pinned (≥9 / ≥4) | Wave-0 test files | `[VERIFIED: pyproject.toml dev deps + tests/test_player_underrun_count.py exists]` |
| stdlib `tokenize` | bundled | Source-grep gate file (string-blanking for docstring false-positives) | `[VERIFIED: tests/test_db_connect_is_sole_connection_factory.py:47-90 — project-canonical pattern]` |

**No new dependencies. No `npm install` / `pip install` step.** All work is in-repo edits.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `Signal(int)` carrying seconds-as-int | `Signal(object)` carrying a small dataclass with `current_s`, `is_adapted`, `growth_step` | `int` is cheaper and matches Phase 78's `underrun_count_changed = Signal(int)` 1:1. The NowPlayingPanel can compute `is_adapted = (value != BUFFER_DURATION_S)` locally — zero ambiguity. **Recommend `Signal(int)`** for symmetry. |
| Mid-session `set_property` write that just stores the value (knowing it's a no-op) | Two-phase stage-and-apply | The stage-and-apply pattern makes the no-op behavior explicit in the call graph: the write to playbin3 happens at `_try_next_stream` / preroll-handoff, where it's clearly tied to URI binding. Inline mid-cycle writes would lie about timing. **Recommend stage-and-apply.** |
| Schedule 30→60→120 (cap) | Schedule 30→45→60 (cap) | The 30→60→120 doubling matches CONTEXT D-11 verbatim. Smaller steps would reduce risk of long startup pauses on the third-step value but the user has already locked the schedule. No discretion to change. |
| Bump growth-step BEFORE `_apply_pending` write in `_try_next_stream` | Bump AFTER write | Doesn't matter under fallback: the growth-step bump happens in `_on_underrun_cycle_closed` (the previous step in time); `_try_next_stream` runs strictly later. No ordering hazard. |
| New helper module `musicstreamer/buffer_growth.py` | Inline on Player | The state is 2 ints + 1 Optional int + 3 methods. Project convention (Phase 62 `_BufferUnderrunTracker` was 80 lines and got a class) is "≥80 lines → class". This is ~25 lines; **inline on Player** matches `_underrun_event_count` from Phase 78. |

---

## Package Legitimacy Audit

**Not applicable.** Phase 84 installs zero external packages. Every primitive used (`gi.repository.Gst`, `PySide6`, `pytest`) is already pinned and exercised by existing tests. The slopcheck protocol explicitly applies only when the phase installs new packages.

---

## Architecture Patterns

### System Architecture Diagram

```
constants.py                              tests/_fake_player.py
─────────────                              ─────────────────────
  BUFFER_DURATION_S = 30  [D-10]            buffer_duration_changed = Signal(int)
  BUFFER_SIZE_BYTES = 20MB [D-10]                   [parity edit]
       │
       │ (imported)
       ▼
musicstreamer/player.py
─────────────────────
  __init__:
    pipeline.set_property("buffer-duration", 30 * Gst.SECOND)  [D-10 — construction-time, takes effect on first URI bind]
    pipeline.set_property("buffer-size",     20MB)              [D-10 — same]
    pipeline.set_property("flags", flags | 0x100)               [DO NOT TOUCH — load-bearing per §Standard Stack]
    self._current_buffer_duration_s: int = BUFFER_DURATION_S    [D-11 state]
    self._growth_step: int = 0                                   [D-11 state]
    self._pending_buffer_duration_s: int | None = None           [D-11 staging]

    buffer_duration_changed = Signal(int)                        [D-12 new Signal — class-level]

  _on_underrun_cycle_closed (main-thread, EXISTING Phase 78 slot extended):
    [existing: log + count++ + count Signal emit]
    self._maybe_grow_buffer_duration()       [NEW — D-11]
       │
       ▼ growth_step 0→1 OR 1→2 (cap)
       _pending_buffer_duration_s = {60, 120}
       _current_buffer_duration_s = {60, 120}
       buffer_duration_changed.emit({60, 120})  [Direct → MainWindow → NowPlayingPanel — stats row updates]

  _try_next_stream (main-thread, EXISTING — line 1146):
    set_state(NULL); wait
    pop queue
    _last_buffer_percent = -1               [EXISTING — Phase 47.1 D-14]
    self._apply_pending_buffer_duration_to_pipeline()   [NEW — writes staged value to playbin3]
    self._reset_buffer_duration_to_baseline()           [NEW — D-11 per-URL reset]
       │
       ▼ growth_step → 0, _current → 30, _pending → 30
       buffer_duration_changed.emit(30)         [stats row drops back to "30s"]
    tracker.force_close(...) → tracker.bind_url(...)  [EXISTING]
    _set_uri(url)                            [EXISTING — triggers uridecodebin3.new_source_handler
                                              which READS playbin3.buffer_duration struct field
                                              and pushes to urisourcebin → queue2]

  _on_preroll_about_to_finish (main-thread, EXISTING — line 1267):
    [existing seq/in-flight checks + queue pop + tracker bind]
    self._apply_pending_buffer_duration_to_pipeline()   [NEW — same as above]
    self._reset_buffer_duration_to_baseline()           [NEW — same as above]
    self._pipeline.set_property("uri", aa_normalize_stream_url(stream.url))   [EXISTING — gapless bind]

musicstreamer/ui_qt/main_window.py
─────────────────────────────────
  __init__:
    [EXISTING line 390:] self._player.underrun_count_changed.connect(self.now_playing.set_underrun_count)
    [NEW after line 390:] self._player.buffer_duration_changed.connect(self.now_playing.set_buffer_duration)
                              # Bound method per QA-05; DirectConnection (both ends main-thread).

musicstreamer/ui_qt/now_playing_panel.py
─────────────────────────────────────
  set_buffer_duration(seconds: int):   [NEW slot next to existing set_underrun_count at line 1002]
    self._buffer_duration_label.setText(
        f"{seconds}s" if seconds == BUFFER_DURATION_S
        else f"{seconds}s (adapted)"
    )

  _build_stats_widget (EXISTING — line 2903 extended):
    form.addRow("Buffer",      [progressbar])      [EXISTING — Phase 47.1]
    form.addRow("Underruns",   "0")                 [EXISTING — Phase 78 line 2936-2938]
    form.addRow("Buf duration", "30s")              [NEW — D-12]
    wrapper.setVisible(False)                       [EXISTING — line 2941]

tests/test_playbin3_property_hygiene.py  [NEW source-grep gate]
────────────────────────────────────────
  asserts musicstreamer/player.py does NOT contain banned playbin 1.x spellings
  for the buffer property set_property write sites (see §Pattern 4)
```

### Recommended Project Structure

No new modules. All edits land in existing files:

```
musicstreamer/
├── constants.py                   # D-10 literal-edit (lines 55-56)
├── player.py                      # D-11 state machine + Signal + 3 new helper methods + 2 call-site extensions
└── ui_qt/
    ├── main_window.py             # +1 .connect line after line 390 (DirectConnection — match line 390)
    └── now_playing_panel.py       # +1 set_buffer_duration slot near line 1002; +1 form.addRow in _build_stats_widget near line 2938

tests/
├── _fake_player.py                # Parity edit — add buffer_duration_changed = Signal(int) near line 75
├── test_player_buffer.py          # Update existing constants assertions (10 → 30, 10MB → 20MB)
├── test_player_buffer_growth.py   # NEW — unit tests for _maybe_grow / _apply_pending / _reset to baseline
├── test_player_underrun.py        # Extend with assertions that cycle_close stages the new buffer-duration and emits Signal
├── test_main_window_underrun.py   # +1 test for buffer_duration_changed → set_buffer_duration wire
├── test_now_playing_panel.py      # +1 test asserting the new stats row is present + reflects buffer_duration changes
└── test_playbin3_property_hygiene.py  # NEW source-grep gate for legacy playbin 1.x property-name regression
```

### Pattern 1: Growth state on Player directly (RECOMMENDED — matches Phase 78 `_underrun_event_count` precedent)

**What:** Two instance fields (`_growth_step: int = 0`, `_current_buffer_duration_s: int = BUFFER_DURATION_S`) plus one Optional staging field (`_pending_buffer_duration_s: int | None = None`). Three new methods on Player: `_maybe_grow_buffer_duration` (called from cycle_close), `_apply_pending_buffer_duration_to_pipeline` (called from URI-bind sites), `_reset_buffer_duration_to_baseline` (called from URI-bind sites). All run on the main thread.

**Why on Player (not on `_BufferUnderrunTracker`):** The tracker is `[VERIFIED: musicstreamer/player.py:116-244]` deliberately Qt-free and GStreamer-free — putting `set_property` calls or Signal emits inside it would break its pure-Python testability. The cycle_close → bump-growth chain runs in the *consumer* of the tracker (Player) which already owns the pipeline reference and the Signal.

### Pattern 2: Always-visible stats row mirroring Phase 78 row exactly (RECOMMENDED)

**What:** One `form.addRow(_MutedLabel("Buf duration", wrapper), self._buffer_duration_label)` line in `_build_stats_widget` immediately after the existing Phase 78 `Underruns` row (line 2938), before `wrapper.setVisible(False)` at line 2941. The label is initialized to `_MutedLabel(f"{BUFFER_DURATION_S}s", wrapper)` at construction. The `set_buffer_duration(seconds: int)` slot updates the text on emit.

**Source pattern:** `[VERIFIED: musicstreamer/ui_qt/now_playing_panel.py:2936-2938]`

```python
# EXISTING — Phase 78 Commit A precedent the new row mirrors exactly:
underrun_row_label = _MutedLabel("Underruns", wrapper)
self._underrun_count_label = _MutedLabel("0", wrapper)
form.addRow(underrun_row_label, self._underrun_count_label)

# NEW — Phase 84 D-12 row (insert here before wrapper.setVisible(False)):
buffer_duration_row_label = _MutedLabel("Buf duration", wrapper)
self._buffer_duration_label = _MutedLabel(f"{BUFFER_DURATION_S}s", wrapper)
form.addRow(buffer_duration_row_label, self._buffer_duration_label)
```

**Why "always-visible":** CONTEXT D-12 explicitly overrides Phase 78 D-08's "adapted-only" default. Rationale per CONTEXT: "the 30s baseline is itself a meaningful change worth surfacing." The wrapper-level `setVisible(False)` at line 2941 still governs the entire stats-for-nerds widget — the row is shown only when the hamburger toggle has stats-for-nerds enabled, exactly like the Buffer progressbar row and the Phase 78 Underruns row.

### Pattern 3: Cross-tier Signal wiring mirroring Phase 78 underrun_count_changed exactly (RECOMMENDED)

**What:** Class-level `buffer_duration_changed = Signal(int)` on Player. DirectConnection wire on MainWindow. `set_buffer_duration(int)` slot on NowPlayingPanel.

**Source pattern:** `[VERIFIED: musicstreamer/ui_qt/main_window.py:382-390 + musicstreamer/ui_qt/now_playing_panel.py:1002-1010]`

```python
# musicstreamer/player.py — at class scope, immediately after underrun_count_changed at line 297:
underrun_count_changed    = Signal(int)      # EXISTING — Phase 78 Commit A
# Phase 84 / BUG-09 Commit B / D-12: live buffer-duration value for the stats-for-nerds row.
# Emitted from _maybe_grow_buffer_duration / _reset_buffer_duration_to_baseline
# (both main-thread). DirectConnection at the receiver (MainWindow.__init__) is
# correct — both ends are on the main thread (qt-glib-bus-threading Pitfall 2 satisfied).
buffer_duration_changed   = Signal(int)      # NEW

# musicstreamer/ui_qt/main_window.py — at __init__, immediately after line 390:
self._player.underrun_count_changed.connect(self.now_playing.set_underrun_count)   # EXISTING
# Phase 84 / D-12: DirectConnection (default — no QueuedConnection arg) — both ends
# on main thread. Bound method per QA-05 — no lambda. Match the Phase 78 wire shape.
self._player.buffer_duration_changed.connect(self.now_playing.set_buffer_duration)  # NEW

# musicstreamer/ui_qt/now_playing_panel.py — slot near line 1010 (after set_underrun_count):
def set_buffer_duration(self, seconds: int) -> None:
    """Phase 84 / BUG-09 Commit B / D-12: receiver for Player.buffer_duration_changed.

    Updates the Buf duration stats-for-nerds row text. Suffix " (adapted)" added
    when value differs from the BUFFER_DURATION_S baseline. The int() coercion
    is defensive (mirrors set_underrun_count's pattern at line 1010).
    """
    s = int(seconds)
    if s == BUFFER_DURATION_S:
        self._buffer_duration_label.setText(f"{s}s")
    else:
        self._buffer_duration_label.setText(f"{s}s (adapted)")
```

**Why DirectConnection (not Queued):** Both ends are on the main thread. `_maybe_grow_buffer_duration` is called from `_on_underrun_cycle_closed`, which is itself the main-thread receiver of the queued `_underrun_cycle_closed` Signal at `player.py:445-447` (the cross-thread marshalling already happened). `_reset_buffer_duration_to_baseline` is called from `_try_next_stream`, which is the main-thread receiver of the queued `_try_next_stream_requested` Signal at `player.py:430-432` OR is called directly on the main thread (e.g. from a UI-driven `play()`). DirectConnection avoids a needless event-loop hop. Match Phase 78 line 390 exactly.

### Pattern 4: Source-grep gate for legacy playbin 1.x property names on playbin3 code paths (REQUIRED per MEMORY)

**What:** A `pytest`-collected source-scanning test file (`tests/test_playbin3_property_hygiene.py`) that asserts `musicstreamer/player.py` does NOT contain any banned legacy `playbin` 1.x spellings on the lines that call `self._pipeline.set_property(...)`. Project precedent: `tests/test_db_connect_is_sole_connection_factory.py` (Phase 80, tokenize-blanked source grep). Background per MEMORY: pipeline mocks pass through any `pipeline.emit(...)` call, so behavioral tests with a `MagicMock` pipeline cannot catch property-name regressions.

**Banned spellings list** (for the buffer-property surface — derived from playbin 1.x → playbin 3 property delta `[VERIFIED: gst-plugins-base playbin.c vs gstplaybin3.c property installation blocks]`):

| Banned name | Why banned (playbin 1.x → 3 migration footgun) |
|-------------|------------------------------------------------|
| `buffer_duration` (Pythonic underscore form for set_property string arg) | playbin3 expects the dash-form `"buffer-duration"`. The underscore form silently does nothing on a real pipeline; passes through a MagicMock. |
| `buffer_size`   | Same — must be `"buffer-size"`. |
| `low-percent`   | Phase 78 / 84 DEFERRED item. Must NOT land in `player.py` set_property calls without an explicit decision (D-04 Phase 78 deferred + Phase 84 deferred). |
| `high-percent`  | Same — deferred. |
| `connection_speed` | playbin3 uses dash-form `"connection-speed"`. Pythonic underscore form silently no-ops. Defense-in-depth for the wider playbin3 property surface. |

The gate scans `musicstreamer/player.py` (and any future player-related modules) for `pipeline.set_property(` / `_pipeline.set_property(` callsites, then asserts the first positional argument is in an allowlist (the strings actually used: `"buffer-duration"`, `"buffer-size"`, `"video-sink"`, `"audio-sink"`, `"flags"`, `"audio-filter"`, `"uri"`, `"volume"`, plus the dynamic equalizer band properties via the EQ element — those are on `self._eq`, not `self._pipeline`, so they won't match). Tokenize-blanks docstrings and comments first to avoid false-positives.

**Pseudocode for the gate:**

```python
# tests/test_playbin3_property_hygiene.py — NEW
import io
import re
import tokenize
from pathlib import Path
import pytest

_PLAYER_PATH = Path(__file__).resolve().parent.parent / "musicstreamer" / "player.py"

# Allowlist of property names that may legitimately appear as the first arg to
# self._pipeline.set_property(...). Add to this list ONLY when a phase decision
# documents the addition; otherwise the gate fires.
_ALLOWED_PIPELINE_PROPERTIES = {
    "video-sink", "audio-sink", "buffer-duration", "buffer-size",
    "flags", "audio-filter", "uri", "volume",
}

# Banned legacy spellings — if any of these appear inside _pipeline.set_property(...)
# the gate fires with a grep-friendly error.
_BANNED_SPELLINGS = {
    "buffer_duration", "buffer_size", "connection_speed",
    "low-percent", "high-percent",        # Phase 78/84 deferred — must not land without decision
}

_SETPROPERTY_RE = re.compile(
    r"""self\._pipeline\.set_property\(\s*["']([^"']+)["']"""
)

def _scan_pipeline_setproperty_args(path: Path) -> list[tuple[int, str]]:
    src = path.read_text(encoding="utf-8")
    # Tokenize-blank docstrings + comments so docstring mentions don't false-positive.
    rows = [list(line) for line in src.splitlines()]
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except tokenize.TokenizeError:
        # Fall back to raw scan — false-positive over false-negative.
        return [(i, m.group(1)) for i, line in enumerate(src.splitlines(), 1)
                for m in _SETPROPERTY_RE.finditer(line)]
    for tok in tokens:
        if tok.type not in (tokenize.STRING, tokenize.COMMENT):
            continue
        (start_row, start_col), (end_row, end_col) = tok.start, tok.end
        # Blank the token range in-place (mirrors test_db_connect_is_sole_connection_factory.py:90).
        ...
    blanked = "\n".join("".join(r) for r in rows)
    return [(i, m.group(1)) for i, line in enumerate(blanked.splitlines(), 1)
            for m in _SETPROPERTY_RE.finditer(line)]

def test_pipeline_setproperty_uses_only_allowed_names():
    """Phase 84 / D-11 mock-blind-spot guardrail (MEMORY feedback_gstreamer_mock_blind_spot).

    Regression lock: every musicstreamer/player.py call to self._pipeline.set_property(...)
    must use a property name on the playbin3 allowlist. Banned spellings (legacy
    playbin 1.x underscore forms; or DEFERRED knobs like low-percent/high-percent)
    silently no-op on a real pipeline but pass through a MagicMock — behavioral
    tests cannot catch them.
    """
    callsites = _scan_pipeline_setproperty_args(_PLAYER_PATH)
    bad = [(line, name) for line, name in callsites if name in _BANNED_SPELLINGS]
    assert not bad, (
        f"musicstreamer/player.py contains banned playbin 1.x / deferred property "
        f"name(s) in self._pipeline.set_property(...) callsites: {bad}. "
        f"Banned set: {sorted(_BANNED_SPELLINGS)}. See 84-RESEARCH §Pattern 4."
    )
    unknown = [(line, name) for line, name in callsites
               if name not in _ALLOWED_PIPELINE_PROPERTIES
               and name not in _BANNED_SPELLINGS]
    assert not unknown, (
        f"musicstreamer/player.py uses unknown playbin3 property name(s) in "
        f"self._pipeline.set_property(...) callsites: {unknown}. "
        f"If this is a legitimate new property, add it to "
        f"_ALLOWED_PIPELINE_PROPERTIES in this test file in the same commit "
        f"that introduces the callsite. Allowlist: {sorted(_ALLOWED_PIPELINE_PROPERTIES)}."
    )
```

### Anti-Patterns to Avoid

- **Writing `set_property("buffer-duration", N * Gst.SECOND)` from `_on_underrun_cycle_closed` directly.** This appears to work (the write succeeds against the playbin3 GObject, and a MagicMock-pipeline test passes) but is a silent no-op on the real pipeline for the active stream. Use the stage-and-apply two-phase pattern (Pattern 1 example) so the timing is explicit in the call graph and tests assert against the URI-bind call site, not the cycle-close call site.
- **Forgetting to apply the staged value in BOTH `_try_next_stream` AND `_on_preroll_about_to_finish`.** The Phase 83 gapless preroll handoff is also a URI bind that triggers a fresh uridecodebin3 handler — it MUST also write the staged value before `set_property("uri", ...)`. If only `_try_next_stream` applies the staged value, growth applied during a SomaFM stream will be lost across the gapless preroll handoff (which fires when the user is listening to the same SomaFM station, no manual station change).
- **Mid-session inline writes that "look adaptive" without the stage-then-apply discipline.** See above. The cleanest test of "did this actually take effect" is the call-site assertion in Pattern 1: `_apply_pending_buffer_duration_to_pipeline` runs at URI-bind, so `assert mock_pipeline.set_property.call_args_list` at the post-bind moment contains `call("buffer-duration", 60 * GST_SECOND)`.
- **Touching `flags | 0x100` at `player.py:325`.** Load-bearing per §Standard Stack and the existing comment block. Phase 84 does NOT modify this line.
- **Touching `__main__.py` `basicConfig(WARNING)`.** Phase 62 Pitfall 5 / Phase 78 carry-forward. Phase 84 introduces no new logging surface; this line stays byte-identical.
- **Bumping `_growth_step` from the cap (2) further** ("just-in-case" defense). The schedule is `{1: 60, 2: 120}` mapped from growth_step; bumping to 3 would `KeyError`. The early-return `if self._growth_step >= 2: return` IS the cap.
- **Forgetting the FakePlayer parity edit** for `buffer_duration_changed = Signal(int)`. Phase 77 INFRA-01 source-grep drift-guard at `tests/test_fake_player_signal_parity.py` fires immediately. Add the parity entry in the same commit (or wave) as the Player Signal addition — Phase 78 Commit A established this discipline at `tests/_fake_player.py:75`.
- **Using `Signal(object)` carrying a dataclass instead of `Signal(int)`.** Breaks Phase 78 symmetry. Compute "is adapted" in the receiver.
- **Setting the stats-row visibility independently of the wrapper.** The wrapper at `_build_stats_widget` line 2941 sets `wrapper.setVisible(False)` once at construction; MainWindow's hamburger toggle drives subsequent visibility via `set_stats_visible(bool)` at NowPlayingPanel line 1012. Do NOT add per-row visibility logic for the new buffer-duration row — it inherits the wrapper's visibility just like the existing Underruns row.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-tier counter Signal | Custom polling loop or shared mutable state | Class-level `Signal(int)` mirroring Phase 78 | Project has 20+ existing Signals in this exact shape; PySide6 handles thread-affinity correctly. |
| Source-grep regression lock | Manual code review checklist | `pytest`-collected source-scanning test (Pattern 4) | Project precedent at `tests/test_db_connect_is_sole_connection_factory.py` (Phase 80). Tokenize-blanking handles docstring false-positives. |
| Theme-flip-safe muted label | Custom QSS / palette code | `_MutedLabel` from `now_playing_panel.py:176` | Established Phase 47.1 D-10 pattern; the Phase 78 Underruns row uses it; reuse verbatim. |
| Test double for Player | Inline `MagicMock(spec=Player)` in each test | `tests/_fake_player.py FakePlayer` | Phase 77 INFRA-01 drift-guard enforces "only this file may declare FakePlayer(QObject)"; parity drift-guard at `tests/test_fake_player_signal_parity.py` keeps it in sync. |
| Mid-session `buffer-duration` propagation | Custom workaround (e.g. `set_state(NULL)` → `set_property` → `set_state(PLAYING)`) | Stage-and-apply at next URI bind (Pattern 1) | A `NULL → PLAYING` cycle would force an audible audio drop on every adaptive growth step — terrible UX and contradicts D-12's "the user only notices because the stats row text changed." |

**Key insight:** Every primitive Phase 84 needs is either stdlib, already-pinned project dep, or a project-internal pattern with ≥1 existing precedent. There is no library to add, no custom infrastructure to build. Net new code is ~70 lines (3 helper methods on Player + 1 NowPlayingPanel slot + 1 form.addRow + 1 connect + 1 FakePlayer line + ~30 lines of source-grep gate test + ~30 lines of growth-step unit tests).

---

## Runtime State Inventory

> Phase 84 is greenfield instrumentation extension (no rename, no refactor of stored data). Every category below is "None" — verified explicitly per the rename/refactor checklist discipline.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no SQLite or settings persistence of `_current_buffer_duration_s` / `_growth_step` (per Discretion: counter resets per launch, file sink is the persistent record for Phase 78 underrun count; Phase 84 adds no new persisted fields). Verified by inspecting `musicstreamer/repo.py` schema — no `buffer_*` columns; Phase 84 introduces none. | None |
| Live service config | None — entirely in-process. No external services (Datadog, n8n, Tailscale, Cloudflare Tunnel) referenced. | None |
| OS-registered state | None — no Task Scheduler / systemd / pm2 / launchd / AUMID change. The existing AUMID + .desktop established by Phase 56 / 61 / 79 are unaffected. | None |
| Secrets / env vars | None — no secrets introduced. The existing Phase 62 `%r`-quoting of `station_name` / `url` continues to mitigate log injection (T-62-01); Phase 84 adds no new log fields and no new env-var reads. | None |
| Build artifacts | None — no `.egg-info`, no compiled binary, no installer registry interaction, no `pyproject.toml` version change beyond the existing VER-01 auto-bump hook at phase close. | None |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `gi.repository.Gst` (GStreamer 1.28.2) | `pipeline.set_property("buffer-duration", N * Gst.SECOND)` write site | ✓ | Linux dev box: GStreamer 1.28.2 via conda-forge bundle (Phase 43 Windows spike spec) | — |
| PySide6 `Signal(int)` / `QObject` | New `buffer_duration_changed` Signal | ✓ | already pinned | — |
| pytest + pytest-qt | Wave-0 + integration tests | ✓ | ≥9 / ≥4 (`pyproject.toml`) | — |
| stdlib `tokenize` + `re` | Source-grep gate (Pattern 4) | ✓ | stdlib | — |
| `~/.local/share/musicstreamer/buffer-events.log` (existing Phase 78 file sink) | D-13 monitor window reads this file | ✓ | created by Phase 78 Commit A `install_buffer_events_handler` at boot | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

This phase has zero new environment risk.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest ≥9` + `pytest-qt ≥4` (`pyproject.toml` dev deps) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_player_buffer.py tests/test_player_buffer_growth.py tests/test_main_window_underrun.py tests/test_now_playing_panel.py tests/test_playbin3_property_hygiene.py tests/test_fake_player_signal_parity.py -q` |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| BUG-09 SC#3 (D-10 static bump) | `BUFFER_DURATION_S == 30` and `BUFFER_SIZE_BYTES == 20 * 1024 * 1024` | unit | `uv run pytest tests/test_player_buffer.py::test_buffer_duration_constant tests/test_player_buffer.py::test_buffer_size_constant -x` | ✅ exists — values change from 10/10MB to 30/20MB |
| BUG-09 SC#3 (D-10 construction-time write) | `__init__` calls `pipeline.set_property("buffer-duration", 30 * Gst.SECOND)` and `pipeline.set_property("buffer-size", 20 * 1024 * 1024)` | unit | `uv run pytest tests/test_player_buffer.py::test_player_writes_buffer_duration_at_construction tests/test_player_buffer.py::test_player_writes_buffer_size_at_construction -x` | ✅ exists — values updated |
| BUG-09 SC#3 (D-11 growth-step state init) | Player `__init__` sets `_growth_step=0`, `_current_buffer_duration_s=BUFFER_DURATION_S`, `_pending_buffer_duration_s=None` | unit | `uv run pytest tests/test_player_buffer_growth.py::test_growth_state_initialized -x` | ❌ Wave 0 |
| BUG-09 SC#3 (D-11 first cycle_close bumps to 60) | `_on_underrun_cycle_closed` first call sets `_growth_step=1`, `_current=60`, `_pending=60`, emits `buffer_duration_changed(60)` | unit | `uv run pytest tests/test_player_buffer_growth.py::test_first_cycle_close_bumps_to_60 -x` | ❌ Wave 0 |
| BUG-09 SC#3 (D-11 second cycle_close bumps to 120) | Second `_on_underrun_cycle_closed` sets `_growth_step=2`, `_current=120`, emits `buffer_duration_changed(120)` | unit | `uv run pytest tests/test_player_buffer_growth.py::test_second_cycle_close_bumps_to_120 -x` | ❌ Wave 0 |
| BUG-09 SC#3 (D-11 cap at 120) | Third+ `_on_underrun_cycle_closed` keeps `_growth_step=2`, `_current=120`, does NOT emit duplicate `buffer_duration_changed(120)` | unit | `uv run pytest tests/test_player_buffer_growth.py::test_growth_caps_at_120 -x` | ❌ Wave 0 |
| BUG-09 SC#3 (D-11 staging → URI bind apply) | `_try_next_stream` calls `_pipeline.set_property("buffer-duration", 60 * Gst.SECOND)` BEFORE `_set_uri(...)` when staged value present | unit | `uv run pytest tests/test_player_buffer_growth.py::test_try_next_stream_applies_pending_before_uri_bind -x` | ❌ Wave 0 |
| BUG-09 SC#3 (D-11 staging → preroll-handoff apply) | `_on_preroll_about_to_finish` calls `_pipeline.set_property("buffer-duration", ...)` BEFORE `set_property("uri", ...)` when staged value present | unit | `uv run pytest tests/test_player_buffer_growth.py::test_preroll_handoff_applies_pending_before_uri_swap -x` | ❌ Wave 0 |
| BUG-09 SC#3 (D-11 per-URL reset) | `_try_next_stream` resets `_growth_step=0`, `_current=BUFFER_DURATION_S`, emits `buffer_duration_changed(BUFFER_DURATION_S)` | unit | `uv run pytest tests/test_player_buffer_growth.py::test_try_next_stream_resets_growth_to_baseline -x` | ❌ Wave 0 |
| BUG-09 SC#3 (D-11 no-op reset when already at baseline) | If `_growth_step==0` already, reset is a no-op AND does NOT emit a spurious `buffer_duration_changed` Signal | unit | `uv run pytest tests/test_player_buffer_growth.py::test_reset_is_noop_when_at_baseline -x` | ❌ Wave 0 |
| BUG-09 SC#3 (D-12 Signal declared) | `Player.buffer_duration_changed = Signal(int)` exists at class scope | source-grep | `uv run pytest tests/test_player_buffer_growth.py::test_buffer_duration_changed_signal_class_scope -x` | ❌ Wave 0 |
| BUG-09 SC#3 (D-12 FakePlayer parity) | `tests/_fake_player.py` mirrors `buffer_duration_changed = Signal(int)` (INFRA-01 drift-guard passes) | drift-guard | `uv run pytest tests/test_fake_player_signal_parity.py -x` | ✅ exists (test passes once parity is added) |
| BUG-09 SC#3 (D-12 UI row present) | `_build_stats_widget` produces a row labeled "Buf duration" with initial value "30s" | unit | `uv run pytest tests/test_now_playing_panel.py::test_buffer_duration_row_present -x` | ✅ exists (file); new test inside |
| BUG-09 SC#3 (D-12 UI slot label format baseline) | `set_buffer_duration(30)` updates label to `"30s"` (no suffix) | unit | `uv run pytest tests/test_now_playing_panel.py::test_set_buffer_duration_baseline_format -x` | ✅ exists (file); new test inside |
| BUG-09 SC#3 (D-12 UI slot label format adapted) | `set_buffer_duration(60)` updates label to `"60s (adapted)"`; `set_buffer_duration(120)` → `"120s (adapted)"` | unit | `uv run pytest tests/test_now_playing_panel.py::test_set_buffer_duration_adapted_format -x` | ✅ exists (file); new test inside |
| BUG-09 SC#3 (D-12 MainWindow wiring) | `MainWindow.__init__` connects `Player.buffer_duration_changed` to `NowPlayingPanel.set_buffer_duration`; emit updates label | integration | `uv run pytest tests/test_main_window_underrun.py::test_buffer_duration_changed_updates_stats_row -x` | ✅ exists (file); new test inside |
| BUG-09 SC#3 (Pattern 4 grep gate) | `musicstreamer/player.py` `_pipeline.set_property(...)` callsites use ONLY allowlisted property names; no banned playbin 1.x spellings | source-grep | `uv run pytest tests/test_playbin3_property_hygiene.py -x` | ❌ Wave 0 |
| BUG-09 SC#3 (Pitfall 5 regression lock — basicConfig WARNING preserved) | `__main__.py` still has `basicConfig(level=logging.WARNING)` AND per-logger `setLevel(INFO)` for `musicstreamer.player`. Phase 84 introduces no new logging. | source-grep | `uv run pytest tests/test_main_window_underrun.py::test_main_module_sets_player_logger_to_info -x` | ✅ exists (carry-forward from Phase 62/78) |
| BUG-09 SC#3 (Pitfall 6 — GST_PLAY_FLAG_BUFFERING preserved) | `musicstreamer/player.py` `__init__` still calls `set_property("flags", flags | 0x100)` | source-grep | `uv run pytest tests/test_playbin3_property_hygiene.py::test_flags_buffering_bit_preserved -x` | ❌ Wave 0 (combine with Pattern 4 grep gate file) |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_player_buffer.py tests/test_player_buffer_growth.py tests/test_playbin3_property_hygiene.py tests/test_fake_player_signal_parity.py -q` (~1-2s — pure unit + source-grep)
- **Per wave merge:** `uv run pytest tests/test_player_buffer.py tests/test_player_buffer_growth.py tests/test_player_underrun.py tests/test_player_underrun_count.py tests/test_main_window_underrun.py tests/test_now_playing_panel.py tests/test_playbin3_property_hygiene.py tests/test_fake_player_signal_parity.py -q` (Phase 62 + 78 + 84 regression band)
- **Phase gate:** Full suite green via `uv run pytest tests/ -q` before `/gsd:verify-work`.

### Wave 0 Gaps

- [ ] `tests/test_player_buffer_growth.py` — NEW; covers `_maybe_grow_buffer_duration`, `_apply_pending_buffer_duration_to_pipeline`, `_reset_buffer_duration_to_baseline`, growth-step state init, cap behavior, no-spurious-emit on no-op reset, and the URI-bind / preroll-handoff staging-application call-site assertions (mocked pipeline). ~10 tests.
- [ ] `tests/test_playbin3_property_hygiene.py` — NEW; source-grep gate per Pattern 4. ~3 tests: (1) banned-spelling assertion, (2) unknown-property-name assertion (allowlist enforcement), (3) `flags | 0x100` preserved assertion.
- [ ] `tests/test_player_buffer.py` — UPDATE existing constants assertions: change expected `BUFFER_DURATION_S` from `10` to `30`; change expected `BUFFER_SIZE_BYTES` from `10 * 1024 * 1024` to `20 * 1024 * 1024`. No new test functions, just literal updates.
- [ ] `tests/_fake_player.py` — PARITY EDIT: add `buffer_duration_changed = Signal(int)` next to existing `underrun_count_changed = Signal(int)` at line 75. INFRA-01 drift-guard at `tests/test_fake_player_signal_parity.py` then passes.
- [ ] `tests/test_now_playing_panel.py` — UPDATE: 3 new tests inside existing file (row presence, baseline format, adapted format).
- [ ] `tests/test_main_window_underrun.py` — UPDATE: 1 new test inside existing file (buffer_duration_changed → set_buffer_duration wire end-to-end).

*Framework install: not needed — `pytest ≥9` + `pytest-qt ≥4` already in dev deps.*

### Test seam recommendations

- **Reuse `make_player(qtbot)` from `tests/test_player_buffering.py:8-18`** — already mocks the GStreamer pipeline factory. The buffer-growth tests can call `player._on_underrun_cycle_closed(record)` synchronously with a fake `_CycleClose`, then assert on Signal emissions via `qtbot.waitSignal(player.buffer_duration_changed, timeout=200)` and on pipeline state via `player._growth_step` / `player._current_buffer_duration_s` reads.
- **URI-bind site assertions need a mocked `self._pipeline.set_property`.** With the existing `make_player` test seam, `player._pipeline` is already a MagicMock. After calling `_on_underrun_cycle_closed`, then calling `_try_next_stream`, assert `player._pipeline.set_property.call_args_list` contains `call("buffer-duration", 60 * Gst.SECOND)` BEFORE the `call("uri", ...)` call. The Pattern 4 source-grep gate catches the MagicMock-blind-spot for property-name spelling.
- **Adapt-then-reset round-trip test:** Bump to 60 (cycle_close), call `_try_next_stream`, assert (a) `_pipeline.set_property("buffer-duration", 60 * Gst.SECOND)` was called once, (b) state is back to baseline (`_growth_step==0`, `_current==BUFFER_DURATION_S`), (c) Signal emission ordering: `buffer_duration_changed(60)` from the growth step → `buffer_duration_changed(BUFFER_DURATION_S)` from the reset.

---

## Common Pitfalls

### Pitfall 1: Writing `buffer-duration` mid-session and assuming it took effect

**What goes wrong:** `self._pipeline.set_property("buffer-duration", 60 * Gst.SECOND)` from within `_on_underrun_cycle_closed` (the natural-feeling place) succeeds against the playbin3 GObject — the value is stored. The next observed `buffer_underrun` on the same URL is just as bad as before. The dev believes "adaptive growth shipped" while real-world data shows zero behavioral change.

**Why it happens:** playbin3's `gst_play_bin3_set_property` for `PROP_BUFFER_DURATION` ONLY stores the value into the playbin3 struct field — it does NOT propagate to `playbin->curr_group->uridecodebin`. The value is only consumed by uridecodebin3's `new_source_handler` at handler-creation time, which fires on URI bind (READY_TO_PAUSED transition). `[VERIFIED: gstplaybin3.c:2474-2477 + gsturidecodebin3.c::new_source_handler]`

**How to avoid:** Use the stage-and-apply two-phase pattern (Pattern 1 above): cycle_close stages the value in `_pending_buffer_duration_s`; the URI-bind sites (`_try_next_stream`, `_on_preroll_about_to_finish`) apply the staged value via `_pipeline.set_property("buffer-duration", N * Gst.SECOND)` BEFORE the URI write.

**Warning signs:** Real-world `buffer-events.log` post-Phase 84 shows zero reduction in long-event count or magnitude during the 2-week monitor window, even after growth-step bumps appear in the stats row. (The follow-up trigger thresholds in D-13 then fire, and a follow-up phase opens — but the failure mode is the silent-no-op write, not a true buffer-tuning ineffectiveness.)

### Pitfall 2: Forgetting to apply the staged value at the gapless preroll handoff site

**What goes wrong:** A SomaFM user listens to one station for an hour; first cycle_close bumps `_growth_step` to 1 (staged: 60s); second cycle_close bumps to 2 (staged: 120s). The gapless preroll handoff fires (every ~hour for SomaFM intros). `_on_preroll_about_to_finish` calls `set_property("uri", ...)` but NOT `_apply_pending_buffer_duration_to_pipeline()` first. The new URI bind creates a fresh uridecodebin3 with the OLD baseline 30s value from playbin3's struct field (because the staged 120s was never written to playbin3). The adaptive growth silently regresses to baseline at every preroll handoff.

**Why it happens:** It's easy to think "only station-change URI binds need the apply" because `_try_next_stream` is the obvious site. The Phase 83 gapless preroll handoff is a less-obvious URI bind that triggers the same uridecodebin3 lifecycle.

**How to avoid:** Both `_try_next_stream` AND `_on_preroll_about_to_finish` MUST call `_apply_pending_buffer_duration_to_pipeline()` immediately before their respective URI writes. The `test_preroll_handoff_applies_pending_before_uri_swap` Wave-0 test catches this regression.

**Warning signs:** Monitor window shows growth-step bumps in logs (Phase 78 file sink captures the Signal-emission timing) but no behavioral improvement for SomaFM users specifically.

### Pitfall 3: Per-URL reset emits a spurious `buffer_duration_changed(BUFFER_DURATION_S)` Signal on every station change even when already at baseline

**What goes wrong:** `_try_next_stream` runs on every station change. If `_reset_buffer_duration_to_baseline` emits `buffer_duration_changed(30)` unconditionally, the stats row re-renders `"30s"` over `"30s"` (no-op visually) but the Signal traffic noise pollutes test signal-spying and any future Signal-observing code.

**Why it happens:** Naive implementation: `self._current_buffer_duration_s = BUFFER_DURATION_S; self.buffer_duration_changed.emit(BUFFER_DURATION_S)` unconditionally.

**How to avoid:** Early-return when state is already at baseline:

```python
def _reset_buffer_duration_to_baseline(self) -> None:
    if self._growth_step == 0 and self._current_buffer_duration_s == BUFFER_DURATION_S:
        return                               # already at baseline — no-op, no spurious emit
    self._growth_step = 0
    self._current_buffer_duration_s = BUFFER_DURATION_S
    self._pending_buffer_duration_s = BUFFER_DURATION_S
    self.buffer_duration_changed.emit(BUFFER_DURATION_S)
```

The `test_reset_is_noop_when_at_baseline` Wave-0 test catches this.

### Pitfall 4: FakePlayer not updated → INFRA-01 drift-guard fails

**What goes wrong:** Phase 77 source-grep parity drift-guard at `tests/test_fake_player_signal_parity.py` fires the moment `buffer_duration_changed = Signal(int)` lands on `Player` without a mirror entry on `tests/_fake_player.py`.

**Why it happens:** Easy to forget the mirror — `_fake_player.py` is in `tests/` and the parity edit is non-obvious if you're focused on production code.

**How to avoid:** Plan the `_fake_player.py` parity edit in the same task (or at minimum same wave) as the Player Signal addition. Phase 78 Commit A established this discipline at `tests/_fake_player.py:75` — verify by running `pytest tests/test_fake_player_signal_parity.py -v` before committing the wave.

**Warning signs:** CI / drift-guard output: `FakePlayer missing Player signal(s): ['buffer_duration_changed']`.

### Pitfall 5: Tests that pass against MagicMock pipeline but would fail on real playbin3

**What goes wrong:** The MagicMock that backs `player._pipeline` in tests accepts `pipeline.set_property("buffer_duration", 60)` (underscore, wrong) just as happily as `pipeline.set_property("buffer-duration", 60)` (dash, correct). The test passes; production code silently no-ops.

**Why it happens:** MagicMock-as-pipeline is the canonical project test seam. It cannot validate GObject property-name correctness because GObject property lookup is a runtime concern that MagicMock by definition does not enforce.

**How to avoid:** Pattern 4 source-grep gate at `tests/test_playbin3_property_hygiene.py` enforces an allowlist of property names against `musicstreamer/player.py` callsites. Project precedent: `tests/test_db_connect_is_sole_connection_factory.py` (Phase 80, same shape). The MEMORY entry `feedback_gstreamer_mock_blind_spot.md` documents this exact failure mode for the broader playbin3 property surface.

**Warning signs:** Behavioral tests all green; manual UAT shows zero buffer behavior change.

### Pitfall 6: Touching `__main__.py` `basicConfig(WARNING)` or removing the per-logger INFO

**What goes wrong:** Phase 62 Pitfall 5 carry-forward: bumping `basicConfig` to INFO globally would surface chatter from `aa_import`, `gbs_api`, `mpris2`, etc. The existing source-grep drift-guard at `tests/test_main_window_underrun.py::test_main_module_sets_player_logger_to_info` fires immediately if either invariant is broken.

**Why it happens:** A "drive-by simplification" temptation when reading `__main__.py` for unrelated reasons.

**How to avoid:** Phase 84 has zero `__main__.py` edits. The existing drift-guard catches accidental edits.

**Warning signs:** Drift-guard fail in CI; stderr suddenly noisier than usual during normal use.

### Pitfall 7: Touching `flags | 0x100` (`GST_PLAY_FLAG_BUFFERING`) at `player.py:325`

**What goes wrong:** Without the flag, ALL Phase 84 work is invisible — playbin3 bypasses queue2, uridecodebin3 doesn't propagate `buffer-duration`/`buffer-size` to urisourcebin (because `use-buffering` is FALSE), the user sees zero effect from any value Phase 84 sets.

**Why it happens:** "Refactoring" the construction site to "clean it up" or "make it more Pythonic" might rewrite the flag manipulation in a way that drops the OR-bit.

**How to avoid:** Pattern 4 grep gate includes `test_flags_buffering_bit_preserved` — asserts the literal `flags | 0x100` is present in `player.py` `__init__`.

**Warning signs:** Phase 84 ships, real-world `buffer-events.log` shows zero change, follow-up trigger fires for non-buffer reasons (i.e. you can't tell if Phase 84 works because the flag regression masks the effect).

### Pitfall 8: Visibility of the new stats row diverging from the wrapper

**What goes wrong:** Adding per-row `setVisible(True/False)` logic for the new buffer-duration row decouples it from the hamburger-toggle that governs the entire stats-for-nerds widget. The user toggles stats-for-nerds off; the row stays visible (or vice versa).

**Why it happens:** Thinking "always-visible per D-12" means "this row needs its own visibility controller."

**How to avoid:** "Always-visible per D-12" means "this row is part of the stats-for-nerds wrapper at all times — it always renders when the wrapper renders." The wrapper-level `setVisible(False)` at `_build_stats_widget` line 2941 + the `set_stats_visible(bool)` slot at NowPlayingPanel line 1012 already govern the row's visibility correctly. Add NO per-row visibility code.

**Warning signs:** UAT shows the row visible when stats-for-nerds is toggled OFF, or invisible when stats-for-nerds is toggled ON.

---

## Code Examples

### Example 1: D-10 literal-edit (`constants.py:55-56`)

```python
# musicstreamer/constants.py:54-56 — Phase 84 / D-10 literal-edit
# GStreamer playbin3 buffer tuning (Phase 16 / STREAM-01; Phase 84 / D-10 bump)
BUFFER_DURATION_S = 30                    # seconds; applied as BUFFER_DURATION_S * Gst.SECOND
BUFFER_SIZE_BYTES = 20 * 1024 * 1024      # 20 MB (Phase 84 / D-10 — was 10MB; comment had said "5 MB" which was wrong both before and after)
```

### Example 2: D-11 growth state init (Player.`__init__`)

```python
# musicstreamer/player.py — Phase 84 / D-11 instance fields, adjacent to existing
# Phase 78 Commit A field at line 498:
self._underrun_event_count: int = 0                            # EXISTING — Phase 78 Commit A
# Phase 84 / D-11 / BUG-09 Commit B: adaptive buffer-duration growth state.
# Per playbin3 source inspection (84-RESEARCH §D-11), mid-session writes to
# buffer-duration are silent no-ops; this state is staged at cycle_close and
# applied to the pipeline at the next URI bind (in _try_next_stream and
# _on_preroll_about_to_finish, BEFORE the set_property("uri", ...) call).
self._growth_step: int = 0                                     # 0 = baseline, 1 = 60s, 2 = 120s (cap)
self._current_buffer_duration_s: int = BUFFER_DURATION_S       # mirrors stats-for-nerds row
self._pending_buffer_duration_s: int | None = None             # staged for next URI bind
```

### Example 3: D-12 Signal declaration (Player class-scope)

```python
# musicstreamer/player.py — Phase 84 / D-12, immediately after underrun_count_changed at line 297:
underrun_count_changed    = Signal(int)      # EXISTING — Phase 78 Commit A
# Phase 84 / BUG-09 Commit B / D-12: live buffer-duration value for the
# stats-for-nerds "Buf duration" row. Emitted from _maybe_grow_buffer_duration
# and _reset_buffer_duration_to_baseline (both main-thread slots). DirectConnection
# at the receiver (main_window.py line 391) — both ends on main thread
# (qt-glib-bus-threading Pitfall 2 satisfied). Mirrors Phase 78 underrun_count_changed
# wire shape exactly; do NOT use Qt.ConnectionType.QueuedConnection.
buffer_duration_changed   = Signal(int)      # NEW
```

### Example 4: D-11 growth method (cycle_close extension)

```python
# musicstreamer/player.py — extension to _on_underrun_cycle_closed at line 1113
def _on_underrun_cycle_closed(self, record) -> None:
    self._underrun_dwell_timer.stop()                           # EXISTING — Phase 62
    _log.info("buffer_underrun ...", ...)                       # EXISTING — Phase 62
    self._underrun_event_count += 1                             # EXISTING — Phase 78
    self.underrun_count_changed.emit(self._underrun_event_count)  # EXISTING — Phase 78
    # Phase 84 / D-11: bump growth step + stage new duration for next URI bind.
    self._maybe_grow_buffer_duration()

def _maybe_grow_buffer_duration(self) -> None:
    """Phase 84 / D-11 / BUG-09 Commit B: bump growth step 0 → 1 → 2 (cap).

    Stages the new value in _pending_buffer_duration_s; the actual playbin3
    write fires at the next URI bind (_try_next_stream or preroll handoff)
    because playbin3 does not propagate buffer-duration mid-session
    (84-RESEARCH §D-11 RESOLVED).

    UI updates immediately via buffer_duration_changed Signal — the stats row
    shows "60s (adapted)" / "120s (adapted)" right away, communicating to
    the user that the growth registered (even though the playbin3 write is
    deferred to next URI bind).
    """
    if self._growth_step >= 2:
        return                                                  # cap at 120s
    self._growth_step += 1
    new_s = {1: 60, 2: 120}[self._growth_step]
    self._pending_buffer_duration_s = new_s
    self._current_buffer_duration_s = new_s
    self.buffer_duration_changed.emit(new_s)
```

### Example 5: D-11 stage-apply at URI bind (`_try_next_stream` extension)

```python
# musicstreamer/player.py — extension to _try_next_stream at line 1146
def _try_next_stream(self) -> None:
    self._pipeline.set_state(Gst.State.NULL)                    # EXISTING
    self._pipeline.get_state(Gst.CLOCK_TIME_NONE)               # EXISTING
    if not self._streams_queue:                                 # EXISTING
        self.failover.emit(None)                                # EXISTING
        return                                                  # EXISTING
    stream = self._streams_queue.pop(0)                         # EXISTING
    self._current_stream = stream                               # EXISTING
    self._last_buffer_percent = -1                              # EXISTING — Phase 47.1 D-14
    # Phase 84 / D-11: apply staged buffer-duration to playbin3 BEFORE binding
    # the new URI. uridecodebin3.new_source_handler will read playbin3.buffer_duration
    # at URI-bind time and push it to urisourcebin → queue2.
    self._apply_pending_buffer_duration_to_pipeline()
    # Phase 84 / D-11 per-URL reset (mirrors _last_buffer_percent reset above
    # and tracker.bind_url below — Phase 47.1 D-14 sentinel-reset pattern).
    self._reset_buffer_duration_to_baseline()
    prior_close = self._tracker.force_close("failover")         # EXISTING — Phase 62
    if prior_close is not None:                                 # EXISTING
        self._underrun_cycle_closed.emit(prior_close)           # EXISTING
    self._tracker.bind_url(...)                                 # EXISTING — Phase 62
    self._underrun_dwell_timer.stop()                           # EXISTING
    # ... rest of method UNCHANGED ...

def _apply_pending_buffer_duration_to_pipeline(self) -> None:
    """Phase 84 / D-11 / BUG-09 Commit B: write the staged buffer-duration to
    playbin3 BEFORE the next URI bind. Mid-session writes are silent no-ops
    per playbin3 source (84-RESEARCH §D-11); the URI bind triggers
    uridecodebin3.new_source_handler which reads playbin3.buffer_duration →
    pushes to urisourcebin → queue2."""
    if self._pending_buffer_duration_s is None:
        return
    self._pipeline.set_property(
        "buffer-duration", self._pending_buffer_duration_s * Gst.SECOND
    )
    self._pending_buffer_duration_s = None

def _reset_buffer_duration_to_baseline(self) -> None:
    """Phase 84 / D-11 per-URL reset. No-op (and no Signal emit) when already
    at baseline — prevents spurious Signal traffic on every station change."""
    if self._growth_step == 0 and self._current_buffer_duration_s == BUFFER_DURATION_S:
        return
    self._growth_step = 0
    self._current_buffer_duration_s = BUFFER_DURATION_S
    self._pending_buffer_duration_s = BUFFER_DURATION_S         # also reset pipeline at next bind
    self.buffer_duration_changed.emit(BUFFER_DURATION_S)
```

### Example 6: D-11 stage-apply at Phase 83 gapless preroll handoff

```python
# musicstreamer/player.py — extension to _on_preroll_about_to_finish at line 1267,
# immediately BEFORE the existing set_property("uri", ...) at line 1369:

# ... existing seq guard + queue pop + tracker bind + ... UNCHANGED through line 1368 ...

# Phase 84 / D-11: apply staged buffer-duration BEFORE the gapless URI swap.
# The Phase 83 gapless handoff is also a URI bind — uridecodebin3 reads
# playbin3.buffer_duration at handler-creation time during the URI transition.
# Without this, growth applied during a SomaFM listening session is lost
# at every preroll handoff (the new uridecodebin3 reads the baseline value
# from playbin3's struct field).
self._apply_pending_buffer_duration_to_pipeline()
self._reset_buffer_duration_to_baseline()

# EXISTING line 1369 — gapless URI swap. Triggers uridecodebin3.new_source_handler
# which reads playbin3.buffer_duration (now updated above).
self._pipeline.set_property("uri", aa_normalize_stream_url(stream.url))
```

### Example 7: D-12 Signal wiring on MainWindow

```python
# musicstreamer/ui_qt/main_window.py — immediately after line 390:
self._player.underrun_count_changed.connect(self.now_playing.set_underrun_count)   # EXISTING — Phase 78
# Phase 84 / D-12 / BUG-09 Commit B: live buffer-duration → stats-for-nerds "Buf duration" row.
# Bound method per QA-05 / §S-3 (no lambda). DirectConnection (default — no
# Qt.ConnectionType.QueuedConnection argument) is correct because the emit
# sites are Player._maybe_grow_buffer_duration and ._reset_buffer_duration_to_baseline
# (both main-thread slots; 84-RESEARCH §Pattern 3) and the receiver
# NowPlayingPanel.set_buffer_duration is a QWidget slot also on the main thread
# (Pitfall 2 satisfied). Mirrors Phase 78 wire shape — do NOT use QueuedConnection.
self._player.buffer_duration_changed.connect(self.now_playing.set_buffer_duration)  # NEW
```

### Example 8: D-12 NowPlayingPanel slot + stats row

```python
# musicstreamer/ui_qt/now_playing_panel.py — slot near line 1010 (after set_underrun_count):
def set_buffer_duration(self, seconds: int) -> None:
    """Phase 84 / BUG-09 Commit B / D-12: receiver for Player.buffer_duration_changed.

    Updates the Buf duration stats-for-nerds row text. Suffix ' (adapted)'
    appended when value differs from BUFFER_DURATION_S baseline (i.e. growth
    step has fired and not yet reset). int() coercion is defensive — mirrors
    set_underrun_count's pattern at line 1010 (and set_buffer_percent at line 999).
    """
    s = int(seconds)
    from musicstreamer.constants import BUFFER_DURATION_S
    if s == BUFFER_DURATION_S:
        self._buffer_duration_label.setText(f"{s}s")
    else:
        self._buffer_duration_label.setText(f"{s}s (adapted)")

# musicstreamer/ui_qt/now_playing_panel.py — _build_stats_widget at line 2903,
# extension between line 2938 (existing Phase 78 Underruns row) and line 2941
# (existing wrapper.setVisible(False)):
form.addRow(underrun_row_label, self._underrun_count_label)     # EXISTING — Phase 78
# Phase 84 / BUG-09 Commit B / D-12: always-visible adaptive buffer-duration row.
# Two-column shape mirrors the Phase 78 Underruns row above and the Phase 47.1
# Buffer (progressbar) row at line 2930. "Buf duration" label disambiguates
# from the existing "Buffer" label (which is the progressbar's label).
# _MutedLabel preserves theme-flip readability per Phase 47.1 D-10. The wrapper-
# level setVisible(False) at line 2941 governs visibility for ALL three rows;
# do NOT add per-row visibility code (set_stats_visible at line 1012 already
# drives the wrapper from MainWindow's hamburger toggle).
from musicstreamer.constants import BUFFER_DURATION_S
buffer_duration_row_label = _MutedLabel("Buf duration", wrapper)
self._buffer_duration_label = _MutedLabel(f"{BUFFER_DURATION_S}s", wrapper)
form.addRow(buffer_duration_row_label, self._buffer_duration_label)
wrapper.setVisible(False)                                       # EXISTING — line 2941
return wrapper                                                  # EXISTING
```

### Example 9: FakePlayer parity edit

```python
# tests/_fake_player.py — Phase 84 parity edit, line 75 area:
underrun_count_changed         = Signal(int)  # EXISTING — Phase 78 / BUG-09 Commit A
buffer_duration_changed        = Signal(int)  # NEW — Phase 84 / BUG-09 Commit B / D-12
```

### Example 10: Wave-0 unit test for growth state machine (sample shape)

```python
# tests/test_player_buffer_growth.py — NEW. Pure-logic tests against Player with
# mocked pipeline; reuses make_player(qtbot) from tests/test_player_buffering.py.

import pytest
from unittest.mock import call
from musicstreamer.constants import BUFFER_DURATION_S
from gi.repository import Gst

def test_growth_state_initialized(player_with_mocked_pipeline):
    p = player_with_mocked_pipeline
    assert p._growth_step == 0
    assert p._current_buffer_duration_s == BUFFER_DURATION_S
    assert p._pending_buffer_duration_s is None

def test_first_cycle_close_bumps_to_60(player_with_mocked_pipeline, qtbot):
    p = player_with_mocked_pipeline
    record = _make_cycle_close_record(outcome="recovered")  # helper from test_player_underrun_count.py
    with qtbot.waitSignal(p.buffer_duration_changed, timeout=200) as blocker:
        p._on_underrun_cycle_closed(record)
    assert blocker.args == [60]
    assert p._growth_step == 1
    assert p._current_buffer_duration_s == 60
    assert p._pending_buffer_duration_s == 60

def test_second_cycle_close_bumps_to_120(player_with_mocked_pipeline, qtbot):
    p = player_with_mocked_pipeline
    p._on_underrun_cycle_closed(_make_cycle_close_record())  # 30 → 60
    with qtbot.waitSignal(p.buffer_duration_changed, timeout=200) as blocker:
        p._on_underrun_cycle_closed(_make_cycle_close_record())  # 60 → 120
    assert blocker.args == [120]
    assert p._growth_step == 2

def test_growth_caps_at_120(player_with_mocked_pipeline):
    p = player_with_mocked_pipeline
    for _ in range(5):
        p._on_underrun_cycle_closed(_make_cycle_close_record())
    assert p._growth_step == 2
    assert p._current_buffer_duration_s == 120

def test_try_next_stream_applies_pending_before_uri_bind(player_with_mocked_pipeline):
    p = player_with_mocked_pipeline
    p._on_underrun_cycle_closed(_make_cycle_close_record())   # stage 60s
    # Set up a queue with one stream so _try_next_stream proceeds.
    p._streams_queue = [_fake_stream(url="http://example/stream")]
    p._is_first_attempt = True
    p._tracker.bind_url(0, "", "")  # reset tracker to avoid prior-cycle force-close emit
    p._try_next_stream()
    # Assert the buffer-duration write happened, with the dash-form property name.
    setprop_calls = [c for c in p._pipeline.set_property.call_args_list]
    duration_calls = [c for c in setprop_calls
                      if c.args and c.args[0] == "buffer-duration"]
    uri_calls = [c for c in setprop_calls
                 if c.args and c.args[0] == "uri"]
    assert len(duration_calls) >= 1, "buffer-duration set_property never called"
    assert duration_calls[-1] == call("buffer-duration", 60 * Gst.SECOND)
    # The buffer-duration write must precede the URI write (call ordering).
    duration_idx = setprop_calls.index(duration_calls[-1])
    uri_idx = setprop_calls.index(uri_calls[-1])
    assert duration_idx < uri_idx, "buffer-duration must be written BEFORE uri"

def test_reset_is_noop_when_at_baseline(player_with_mocked_pipeline, qtbot):
    p = player_with_mocked_pipeline
    # State is at baseline (growth_step=0, current=30).
    with qtbot.assertNotEmitted(p.buffer_duration_changed, wait=100):
        p._reset_buffer_duration_to_baseline()
    assert p._growth_step == 0
    assert p._current_buffer_duration_s == BUFFER_DURATION_S
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Phase 16: static `BUFFER_DURATION_S=10`, `BUFFER_SIZE_BYTES=10MB` | Phase 84 D-10: static `30s` / `20MB` | This phase | 3× duration headroom over harvest-week 7.4s worst case; 2× byte cap so high-bitrate FLAC isn't constrained. |
| Phase 78 D-05 sketch: "adaptive growth via mid-session set_property" (informational, not locked) | Phase 84 D-11 FALLBACK: adaptive growth via stage-and-apply at next URI bind | This phase (research surfaced playbin3 limitation) | Functionally adaptive per-listening-session, but station-boundary-granular rather than mid-stream. User-visible UI updates immediately on cycle_close; pipeline write deferred to URI bind. |
| Phase 78 D-08 default: stats-for-nerds row shown only when "adapted" | Phase 84 D-12: always-visible | This phase | 30s baseline is itself a meaningful change worth surfacing; always-visible is the cleanest UX signal. |
| Phase 78 D-06 closure: statistical `M < N AND median lower` gate | Phase 84 D-13: ship-and-monitor + waived gate + 2-week follow-up trigger | This phase (12 events / 7 days = insufficient sample) | Faster ship; behavior monitored post-deployment; clear follow-up trigger if signal regression appears. |

**Deprecated / outdated:**
- Mid-session `pipeline.set_property("buffer-duration", N)` as the primary adaptive-growth mechanism — confirmed silent no-op for currently-playing stream per playbin3 source. Phase 84 routes through the stage-and-apply fallback instead.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | playbin3's `gst_play_bin3_set_property` for `PROP_BUFFER_DURATION` / `PROP_BUFFER_SIZE` does not propagate to active uridecodebin3 | §D-11 Resolution | **VERIFIED via direct source inspection of `gstplaybin3.c` master branch (2026-05-24).** Risk: very low — the implementation is unambiguous and matches the negative observation from real-world Phase 78 / 84 testing (mid-session writes don't change behavior). If GStreamer master changes in a future release to ADD propagation, the stage-and-apply fallback still works correctly (extra writes at URI-bind become redundant but not harmful). `[VERIFIED]` |
| A2 | uridecodebin3's `new_source_handler` reads playbin3's `buffer_duration` struct field at URI-bind time AND pushes it to urisourcebin via `g_object_set` | §D-11 Resolution + §Standard Stack | **VERIFIED via direct source inspection of `gsturidecodebin3.c` master branch (2026-05-24).** Risk: very low. This is what makes the static D-10 bump work at all. `[VERIFIED]` |
| A3 | The Phase 16 `GST_PLAY_FLAG_BUFFERING` (0x100) at `player.py:325` is load-bearing — without it, neither static nor adaptive `buffer-duration` values reach urisourcebin's queue2 | §Standard Stack + Pitfall 7 | **VERIFIED via `player.py:320-323` comment block + cross-check against uridecodebin3 source.** Risk: low. The Pattern 4 grep gate's `test_flags_buffering_bit_preserved` adds an explicit regression lock. `[VERIFIED]` |
| A4 | The Phase 83 gapless preroll handoff at `player.py:1369` (`self._pipeline.set_property("uri", ...)`) triggers a fresh uridecodebin3 `new_source_handler` invocation — same as `_set_uri`'s `set_state(NULL) → set_property(uri) → set_state(PLAYING)` cycle | §Pitfall 2 | **PARTIALLY VERIFIED.** The Phase 83 comment block at `player.py:1363-1368` says "playbin3 transitions to the new URI at the preroll's EOS automatically" and references live-spike confirmation. The uridecodebin3 lifecycle inside that transition specifically is not directly inspected, but playbin3's gapless URI-switching mechanism (documented in [GStreamer: Gapless and instant URI switching in playback elements](https://gstreamer.freedesktop.org/documentation/additional/design/playback-gapless.html)) creates a new source group for each URI, and each source group has its own uridecodebin3 instance per `gstplaybin3.c` structure. So the new uridecodebin3 would read the (updated) playbin3.buffer_duration at construction. Risk: medium — if a future GStreamer release optimizes gapless to REUSE the source group's uridecodebin3 instead of creating a fresh one, the staged value would be lost on the gapless path. The `test_preroll_handoff_applies_pending_before_uri_swap` Wave-0 test will continue to assert the staging-write call happens; if a live-UAT shows growth doesn't persist across preroll handoff post-Phase-84, this assumption needs revisiting. `[ASSUMED — partially verified]` |
| A5 | The new `buffer_duration_changed = Signal(int)` does not conflict with any existing Player Signal name | §Discretion + §Pattern 3 | **VERIFIED via `grep -nE "^\\s*[a-zA-Z_]+\\s*=\\s*Signal\\(" musicstreamer/player.py` returning 20 names, none `buffer_duration_changed`.** Risk: zero. `[VERIFIED]` |
| A6 | Phase 77 INFRA-01 drift-guards (`tests/test_fake_player_signal_parity.py`, `tests/test_fake_player_no_inline.py`) will fire if the FakePlayer parity edit is missed | §Pitfall 4 + §Test Map | **VERIFIED via direct inspection of `tests/_fake_player.py:75` (Phase 78 mirror entry exists; same pattern enforced).** Risk: zero — the drift-guard is well-established. `[VERIFIED]` |
| A7 | The Pattern 4 source-grep gate's allowlist (`{"video-sink", "audio-sink", "buffer-duration", "buffer-size", "flags", "audio-filter", "uri", "volume"}`) covers every current `self._pipeline.set_property(...)` call site in `player.py` | §Pattern 4 | **VERIFIED via `grep -n "self\\._pipeline\\.set_property\\(" musicstreamer/player.py`** returning callsites at lines 312, 317, 318, 319, 325, 335, 515, 1058, 1199, 1369, 1427. All first args are in the allowlist set. Risk: low — if a future phase adds a new playbin3 property (e.g. `connection-speed`), the gate fails at test time with a grep-friendly message instructing the addition. This is the desired behavior, not a regression. `[VERIFIED]` |
| A8 | The 30 → 60 → 120s growth schedule with stage-and-apply will produce SOME observable behavioral improvement during the 2-week monitor window post-ship | §D-13 + §Common Pitfalls §1 | **ASSUMED.** Mathematically: even at station-boundary granularity (fallback path), users who experience a long underrun on one station will get 60s of headroom when they next change stations OR when SomaFM's gapless preroll handoff fires (~hourly). The harvest data shows 5 long events / 7 days across multiple stations, so per-session adaptive bumps should compound. Risk: medium — if the deferred-fallback semantics mean adaptive growth never fires in real-world usage patterns (e.g. users almost never change stations and SomaFM preroll is rare), the user might see ONLY the D-10 static bump benefit. If post-Phase-84 monitor shows zero improvement, the follow-up phase per D-13 should evaluate whether mid-session `set_state(PAUSED) → set_property → set_state(PLAYING)` (one audio drop per growth) is worth the UX cost. `[ASSUMED]` |

---

## Open Questions (RESOLVED)

All four critical questions from CONTEXT.md and the orchestrator's `<additional_context>` are resolved.

### Q1 — Mid-session `buffer-duration` writes on playbin3

- **RESOLVED:** Mid-session writes are silent no-ops. Use stage-and-apply fallback. See §D-11 Research Dependency Resolution above. `[VERIFIED via gst-plugins-base/master/gst/playback/{gstplaybin3,gsturidecodebin3}.c source inspection]`

### Q2 — `BUFFER_SIZE_BYTES` semantics with `GST_PLAY_FLAG_BUFFERING`

- **RESOLVED:** Both `buffer-duration` AND `buffer-size` are propagated from uridecodebin3 → urisourcebin → queue2 ONLY when `use-buffering=TRUE`, which is what the `0x100` flag bit enables on playbin3's `flags` property. The misleading comment block in `player.py:320-323` ("buffer-duration/buffer-size above are silently ignored") refers specifically to the WITHOUT-flag case. With the flag, both knobs ARE honored at URI-bind time. D-10 expanding `BUFFER_SIZE_BYTES` 10MB → 20MB has real effect — at high-bitrate sources (FLAC ≈1.4Mbps), the 20MB cap unlocks ~110s of buffering before byte-limit kicks in, comfortably accommodating the 30s baseline duration AND the 120s adaptive cap. `[VERIFIED via gsturidecodebin3.c::new_source_handler]`

### Q3 — Thread safety of `set_property` writes

- **RESOLVED:** All `_apply_pending_buffer_duration_to_pipeline` calls happen from the main thread (`_try_next_stream` is main-thread per `player.py:430-432` queued connection; `_on_preroll_about_to_finish` is main-thread per `player.py:434-436` queued connection). The GLib bus loop is concurrently emitting buffering messages, but `pipeline.set_property` is GObject-thread-safe — it acquires `GST_OBJECT_LOCK` internally for property setters that need it. No new `g_idle_add` / `Gst.MiniObject` queuing is required. The existing pattern at `player.py:515` (`self._pipeline.set_property("volume", self._volume)` from the main thread while bus messages stream in) is the proven precedent. `[VERIFIED via existing volume-setter behavior, Phase 57 / WIN-03 D-12 wiring]`

### Q4 — playbin3 vs. playbin 1.x property-name regression risk

- **RESOLVED:** Pattern 4 source-grep gate. Banned spelling set: `{"buffer_duration", "buffer_size", "connection_speed", "low-percent", "high-percent"}`. Allowlist set: `{"video-sink", "audio-sink", "buffer-duration", "buffer-size", "flags", "audio-filter", "uri", "volume"}`. Test file `tests/test_playbin3_property_hygiene.py` enforces both. Project precedent: `tests/test_db_connect_is_sole_connection_factory.py` (Phase 80, tokenize-blanked source grep). `[VERIFIED via project pattern + MEMORY guidance feedback_gstreamer_mock_blind_spot.md]`

### Q5 — Adaptive growth timing relative to current vs next underrun cycle

- **RESOLVED under fallback path:** The growth step fires on cycle_close (UI reflects it immediately via Signal emission). The pipeline `set_property` call fires at the next URI bind. **The new buffer-duration value therefore applies to playback that starts AT or AFTER the next station change / preroll handoff — NOT to the current stream.** The acceptance criteria for D-11 tasks should be worded accordingly: "After cycle_close + station change, the next stream's buffering uses the bumped value." NOT: "After cycle_close, the current stream's buffer immediately expands." `[VERIFIED — see §D-11 Resolution]`

### Q6 — FakePlayer drift-guard requirement

- **RESOLVED:** Yes, parity edit required. Add `buffer_duration_changed = Signal(int)` at `tests/_fake_player.py:75` (next to existing `underrun_count_changed = Signal(int)`). Phase 77 INFRA-01 drift-guard at `tests/test_fake_player_signal_parity.py` catches the omission immediately. Plan the parity edit in the same wave (ideally same task) as the Player Signal addition. `[VERIFIED]`

### Q7 — GstReferenceClock / pipeline state interactions

- **RESOLVED:** No `set_state(NULL) → set_state(PLAYING)` roundtrip is needed for the adaptive growth write under the fallback path. The pipeline naturally transitions through `READY → PAUSED → PLAYING` on every URI bind (via `_set_uri`'s explicit `set_state(NULL) → set_property("uri") → set_state(PLAYING)` sequence at `player.py:1197-1200`), AND through internal state changes during the Phase 83 gapless URI swap. In BOTH paths, uridecodebin3 sees a fresh `new_source_handler` call where it reads playbin3's current `buffer_duration` struct field. The fallback path writes the new value BEFORE the URI write, so the freshly-created uridecodebin3 reads the updated value. No additional state cycling needed; no audio drop introduced beyond what already happens at URI binds. `[VERIFIED via existing `_set_uri` semantics + Phase 83 gapless handoff comment block]`

---

## Security Domain

Phase 84 surface is minimal — no new external network, no secrets, no new log fields, no new file I/O. ASVS categories listed for completeness; only V7 (Error Handling & Logging — carry-forward from Phase 78) materially applies via the Pattern 4 source-grep gate (defense in depth against silent-no-op regression).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a |
| V5 Input Validation | partial | The new `set_buffer_duration(seconds: int)` slot's `int()` coercion is defensive (mirrors `set_underrun_count` at `now_playing_panel.py:1010`). All values flowing through the Signal originate from Player's own controlled state — no external input. |
| V6 Cryptography | no | n/a |
| V7 Error Handling & Logging | yes | Continue Phase 62/78 invariants: `basicConfig(WARNING)` + per-logger INFO for `musicstreamer.player`. Phase 84 introduces NO new logging surface. The existing `buffer_underrun ...` line at `player.py:1122-1129` continues to use `%r`-quoting for `station_name` / `url` (T-62-01 mitigation). Pattern 4 source-grep gate adds defense against silent-no-op writes (a Tampering-like failure mode where production code SAYS it's adapting but isn't). |
| V8 Data Protection | no | No new data fields. |

### Known Threat Patterns for this surface

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Silent no-op `set_property` writes ("looks adaptive, isn't") — production code SAYS it's adapting but the playbin3 sink ignores the write | Tampering (integrity of stated behavior) | Pattern 4 source-grep gate enforces allowlist of property names; D-11 fallback uses explicit stage-and-apply with call-site assertions in Wave-0 tests (`test_try_next_stream_applies_pending_before_uri_bind`). |
| Cross-thread race on `_pending_buffer_duration_s` field | Tampering | All writes/reads are on main thread (`_on_underrun_cycle_closed` and `_try_next_stream` / `_on_preroll_about_to_finish` are all main-thread slots — queued from their respective worker/bus-loop emit sites). No locking needed. |
| Theme-flip rendering regression of the new stats row | DoS (UX) | `_MutedLabel` (Phase 47.1 D-10) re-applies muted palette on `paletteChanged` event — the new row inherits this for free. Phase 47.1 UAT-validated for both light/dark themes. |
| Spurious Signal traffic polluting test signal-spying | Repudiation (test trustworthiness) | Pitfall 3 mitigation: no-op early-return in `_reset_buffer_duration_to_baseline` when already at baseline; `test_reset_is_noop_when_at_baseline` Wave-0 test enforces. |

---

## Sources

### Primary (HIGH confidence — direct source / official docs)

- **`musicstreamer/constants.py:54-56`** — values D-10 changes (full read).
- **`musicstreamer/player.py:1-130, 270-340, 1100-1200, 1265-1370`** — pipeline construction site (D-10 takes effect here), Phase 62/78 Signal block, cycle_close slot, `_try_next_stream`, Phase 83 gapless preroll handoff.
- **`musicstreamer/ui_qt/main_window.py:375-400`** — Phase 78 wiring template (D-12 mirror target).
- **`musicstreamer/ui_qt/now_playing_panel.py:176, 993-1014, 2895-2942`** — `_MutedLabel`, `set_buffer_percent` / `set_underrun_count` slots, `_build_stats_widget` extension site.
- **`tests/_fake_player.py:1-140`** — Phase 78 parity entry (template for Phase 84 parity edit).
- **`tests/test_db_connect_is_sole_connection_factory.py:1-90`** — Phase 80 source-grep gate template (Pattern 4 mirror target).
- **`.planning/phases/78-…/78-RESEARCH.md` + `78-CONTEXT.md`** — Phase 78 Commit A patterns (full read of canonical references section + Open Questions block).
- **`.planning/phases/62-…/62-RESEARCH.md` (lines 1-714)** — Phase 62 cycle-tracker + queued-Signal precedents, Pitfalls 1-5 verbatim.
- **`.claude/skills/spike-findings-musicstreamer/SKILL.md` + `references/qt-glib-bus-threading.md`** — Pitfall 2 (queued Signals for cross-thread); confirms DirectConnection is correct for the new main-thread-to-main-thread Signal.
- **[`https://raw.githubusercontent.com/GStreamer/gst-plugins-base/master/gst/playback/gstplaybin3.c`](https://raw.githubusercontent.com/GStreamer/gst-plugins-base/master/gst/playback/gstplaybin3.c)** — `gst_play_bin3_set_property` cases for `PROP_BUFFER_SIZE` / `PROP_BUFFER_DURATION` (silent struct-field stores, NO propagation to child). `PROP_RING_BUFFER_MAX_SIZE` contrasting propagation pattern. Property registration with `G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS` only — no `GST_PARAM_MUTABLE_*` markers. `[VERIFIED 2026-05-24]`
- **[`https://raw.githubusercontent.com/GStreamer/gst-plugins-base/master/gst/playback/gsturidecodebin3.c`](https://raw.githubusercontent.com/GStreamer/gst-plugins-base/master/gst/playback/gsturidecodebin3.c)** — `new_source_handler` reads uridecodebin->buffer_duration / buffer_size at handler-creation time AND pushes via `g_object_set` to urisourcebin (along with `connection-speed`, `download`, `use-buffering`, `ring-buffer-max-size`). `[VERIFIED 2026-05-24]`
- **`~/.local/share/musicstreamer/buffer-events.log`** (10593 bytes as of 2026-05-24 16:18) — confirms 12 `buffer_underrun ...` events present, matching CONTEXT `<data-summary>` totals. File-sink and Signal-emit wiring from Phase 78 Commit A confirmed in production.

### Secondary (MEDIUM confidence — official docs without exact-text verification)

- **[`https://gstreamer.freedesktop.org/documentation/playback/playbin3.html`](https://gstreamer.freedesktop.org/documentation/playback/playbin3.html)** — `buffer-duration` and `buffer-size` listed as Read/Write but with minimal additional detail (mutability not documented at the API-reference level; source-code inspection is authoritative).
- **[`https://gstreamer.freedesktop.org/documentation/playback/uridecodebin3.html`](https://gstreamer.freedesktop.org/documentation/playback/uridecodebin3.html)** — uridecodebin3 property documentation (matches source inspection).
- **[`https://gstreamer.freedesktop.org/documentation/application-development/advanced/buffering.html`](https://gstreamer.freedesktop.org/documentation/application-development/advanced/buffering.html)** — BUFFERING message semantics (carry-forward verification from Phase 62).
- **[`https://gstreamer.freedesktop.org/documentation/additional/design/playback-gapless.html`](https://gstreamer.freedesktop.org/documentation/additional/design/playback-gapless.html)** — gapless URI switching creates a new source group per URI (supporting A4 assumption).
- **[`https://deepwiki.com/GStreamer/gstreamer/3.1-playbin3-architecture`](https://deepwiki.com/GStreamer/gstreamer/3.1-playbin3-architecture)** — playbin3 architecture overview (consulted for source-group/uridecodebin3 relationship).

### Tertiary (LOW confidence — not used as authoritative)

- None. Every claim driving an implementation decision traces to either (a) direct gst-plugins-base source inspection, (b) a code-line citation in this codebase, or (c) an explicit Pitfall / pattern in the project's spike-findings skill.

---

## Metadata

**Confidence breakdown:**

- **Standard stack:** HIGH — every primitive is already pinned and exercised; no new dependency.
- **D-10 static bump:** HIGH — landing site already exists (`player.py:318-319`); literal-value edit; takes effect at construction-time as proven by Phase 16 working at all.
- **D-11 fallback architecture:** HIGH — playbin3 source inspection is unambiguous; stage-and-apply pattern is the cleanest expression of the constraint; both URI-bind sites (`_try_next_stream`, `_on_preroll_about_to_finish`) are well-mapped.
- **D-12 Signal + stats row:** HIGH — 1:1 mirror of Phase 78 Commit A's `underrun_count_changed` / `set_underrun_count` / Underruns row, every step has a working precedent in the codebase.
- **Pattern 4 source-grep gate:** HIGH — project precedent at `tests/test_db_connect_is_sole_connection_factory.py`; tokenize-blanking handles false-positives.
- **Threading correctness:** HIGH — all new code paths are main-thread; DirectConnection wire matches Phase 78; `set_property` from main-thread while bus emits is proven safe by `player.py:515` (existing volume setter).
- **A4 (Phase 83 gapless preroll triggers fresh uridecodebin3):** MEDIUM — partially verified via source structure inference and Phase 83 comment block; the `test_preroll_handoff_applies_pending_before_uri_swap` Wave-0 test enforces the staging-write call regardless, and post-ship monitor data will surface any divergence.
- **A8 (D-11 fallback produces observable behavioral improvement):** MEDIUM — relies on user behavior patterns (station-change frequency, gapless-preroll firing). The "ship + monitor" closure under D-13 explicitly accommodates this uncertainty by waiving the strict statistical gate and defining clear follow-up trigger thresholds.

**Research date:** 2026-05-24
**Valid until:** 2026-06-24 (30 days — playbin3 / uridecodebin3 source is stable; project conventions stable; the 2-week post-ship monitor window per D-13 will surface any A4 / A8 divergence well within validity).

## RESEARCH COMPLETE
