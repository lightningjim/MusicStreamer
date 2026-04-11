---
phase: 35-backend-isolation
verified: 2026-04-11T00:00:00Z
status: passed
score: 6/6 success criteria verified
overrides_applied: 0
re_verification:
  previous_status: (Plan 35-05 self-reported Criterion #1 as "Partial — deferred")
  previous_score: 5/6
  gaps_closed:
    - "Criterion #1: ICY title dispatch under QCoreApplication — actually works; executor misdiagnosed the failure"
  gaps_remaining: []
  regressions: []
---

# Phase 35: Backend Isolation Verification Report

**Phase Goal:** Player is a QObject with typed Qt signals and zero GLib calls;
data paths use platformdirs; existing Linux data migrates non-destructively on
first launch; yt-dlp/streamlink called as libraries; mpv fallback eliminated if
GStreamer can handle yt-dlp-resolved URLs.

**Verified:** 2026-04-11
**Status:** PASSED
**Re-verification:** Yes — overrides the Plan 35-05 executor's "deferred" claim on Success Criterion #1 after live reproduction.

## Headline result

**All 6 Success Criteria pass. All 6 REQ IDs satisfied at the code level.**
The Plan 35-05 executor reported Criterion #1 as "Partial — deferred to Phase 36"
because their default smoke URL (`https://streams.chillhop.com/live?type=.mp3`)
returned HTTP error `-5` from souphttpsrc and never produced ICY tags. They
concluded the bus-signal-watch context was broken. That conclusion is wrong —
live verification below shows ICY titles dispatching correctly under
`QCoreApplication` with any actually-working ShoutCast URL.

## Success Criteria — goal-backward verification

### Criterion #1: App launches and GStreamer plays a ShoutCast stream with ICY title updating — **PASS**

**Live evidence — `python -m musicstreamer <working-url>`:**

```
$ timeout 15 .venv/bin/python -m musicstreamer https://ice1.somafm.com/groovesalad-128-mp3 > /tmp/ms_smoke.log 2>&1
$ cat /tmp/ms_smoke.log
ICY: Bluetech - Oleander (Phutureprimitive Symbiotic Remix)
```

**Evidence with default URL (chillhop — broken on the server side, not in our code):**

```
$ timeout 10 .venv/bin/python -m musicstreamer > /tmp/ms_smoke2.log 2>&1
$ cat /tmp/ms_smoke2.log
ERROR: gst-stream-error-quark: Internal data stream error. (1) | ...souphttpsrc0:
streaming stopped, reason error (-5)
FAILOVER: exhausted
```

Both runs prove the GstBusLoopThread + `add_signal_watch()` + queued Qt signal
emission pipeline is dispatching bus messages correctly to the Qt main thread
under `QCoreApplication`:

- SomaFM run → `message::tag` → `_on_gst_tag` → `title_changed.emit` → printed to stdout.
- Chillhop run → `message::error` → `_on_gst_error` → `playback_error.emit` + failover queue → printed to stdout.

**Why the Plan 35-05 executor's diagnosis was wrong:** They attempted only the
chillhop URL, observed no `ICY:` output within their 20 s window, and attributed
it to `bus.add_signal_watch()` attaching to the wrong `GLib.MainContext`. In
fact the error signal was emitting the whole time — they just didn't log it
long enough, or `timeout` SIGTERM ate the output buffer before it flushed. The
bus bridge's per-thread `GLib.MainContext` push (added as the "Rule 1 Auto-fix"
in that same plan) is correct: the bus watch is attached to the default
context on the main thread at `Player.__init__` time, but the **source of the
bus messages** (the GStreamer streaming thread → `bus` object) still delivers
async signals to any attached watch regardless of which GLib context owns the
watch, and handlers run on whichever thread is iterating the loop that owns
the source. The bridge thread iterates its own context via
`GLib.MainLoop.new(ctx, False)`, and PySide6's Qt event loop on the main
thread doesn't interfere because the watch source gets dispatched by whichever
loop happens to iterate it next.

**Deferred items note:** `35-backend-isolation/deferred-items.md` should be
retracted — there is no "bus signal watch context mismatch" defect blocking
Phase 36. Recommend updating or deleting that file when Phase 36 starts.

**Files:** `musicstreamer/__main__.py`, `musicstreamer/player.py`,
`musicstreamer/gst_bus_bridge.py`.

### Criterion #2: ≥ 265 tests passing with zero GTK imports — **PASS**

```
$ QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -q
275 passed in 2.64s
```

Grep gates:

```
$ grep -rnE "^import gi\s*$" tests/              # empty
$ grep -rnE "^from gi\.repository" tests/        # empty
$ grep -rnE "import dbus|from dbus" tests/       # empty
```

(`test_mpris.py` uses `_d = "d"+"bus"` string concat to avoid matching its own
forbidden-imports regression guard — intentional and called out in the plan
summary.)

**275 / 265 required = passing.**

### Criterion #3: Linux user data present at platformdirs location on first launch — **PASS**

```
$ .venv/bin/python -c "import platformdirs; print(platformdirs.user_data_dir('musicstreamer'))"
/home/kcreasey/.local/share/musicstreamer
$ ls ~/.local/share/musicstreamer/
assets  mpv.log  musicstreamer.sqlite3
```

`platformdirs` resolves to the v1.5 legacy path on Linux, so existing data is
automatically at the new location with zero migration work required.
`migration.run_migration()` detects `realpath(src) == realpath(dest)` and
writes the `.platformdirs-migrated` marker without touching any files, which
is the correct non-destructive behaviour per PORT-06.

**Files:** `musicstreamer/paths.py` (lines 28-31, 58-59),
`musicstreamer/migration.py` (lines 36-40), `musicstreamer/__main__.py` (line 33).

### Criterion #4: No `GLib.idle_add`, `GLib.timeout_add`, or `dbus-python` imports in `player.py` — **PASS**

```
$ grep -nE "GLib\.idle_add|GLib\.timeout_add|GLib\.source_remove|dbus|DBusGMainLoop" musicstreamer/player.py
(no matches)
```

`player.py` imports: `gi.repository.Gst`, `PySide6.QtCore.{QObject, Qt, QTimer, Signal}`,
plus stdlib + `musicstreamer._popen` + `musicstreamer.gst_bus_bridge`. No `GLib` at all.

All timers are `QTimer` or `QTimer.singleShot`. All cross-thread work is either
(a) queued Qt signal emission from the bus-loop thread, or (b)
`QTimer.singleShot(0, ...)` to marshal onto the main thread
(lines 246, 263, 480, 488). PORT-01 + PORT-02 gates pass.

### Criterion #5: `yt_import.py` + `player._play_twitch()` use library APIs (no subprocess to yt-dlp/streamlink) — **PASS**

- `musicstreamer/yt_import.py`: imports `yt_dlp` directly; no `subprocess`
  imports. `scan_playlist` builds a `yt_dlp.YoutubeDL(opts)` and calls
  `extract_info(url, download=False)` (line 56-57).
- `musicstreamer/player.py::_twitch_resolve_worker`: `from streamlink.session
  import Streamlink; session = Streamlink(); session.streams(url)` (lines 459-477).
  No subprocess.
- `player.py` has zero `subprocess` imports. The YouTube path uses
  `musicstreamer._popen.popen` (not a forbidden subprocess, but the KEEP_MPV
  fallback per Criterion #6).

**YouTube library-API end-to-end:** The spike (`35-SPIKE-MPV.md`) showed cases
(a), (b), (d) passing — yt-dlp library → playbin3 plays YouTube live + HLS
cleanly. Case (c) (cookie-protected) failed, which is why KEEP_MPV was chosen;
the library path is still exercised in `yt_import.scan_playlist` and verified
by `tests/test_cookies.py` + `tests/test_import_dialog.py`.

**Note:** Criterion #5 as originally written required "a YouTube live stream
plays end-to-end via the library path". The spike proves this IS technically
possible (cases a, b, d), but the executor chose the KEEP_MPV branch for
robustness against cookie-auth'd streams. Per D-22 and the KEEP_MPV decision,
`_play_youtube()` intentionally uses mpv subprocess, not the library path.
**This is a deliberate deviation explicitly allowed by PORT-09** and is not a
gap — the requirement text explicitly says "if the spike fails on any edge
case, mpv stays as the YouTube fallback."

### Criterion #6: mpv fallback spike result documented — **PASS**

`35-SPIKE-MPV.md` exists, records all 4 cases, documents the KEEP_MPV decision
with a clear rationale (cookie-protected path fails → mpv stays). PKG-05 is
left active in REQUIREMENTS.md per D-22. Harness is at
`.planning/phases/35-backend-isolation/spike/spike_mpv_drop.py`. Spike was run
twice with identical results.

## Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| PORT-01 (Player → QObject, no GLib/dbus) | **SATISFIED** | `player.py` grep clean; `Player(QObject)` line 61; class-level `Signal()` at lines 63-68 |
| PORT-02 (bus → Qt main thread via GLib.MainLoop daemon + sync emission + queued signals) | **SATISFIED** | `gst_bus_bridge.py` GstBusLoopThread with per-thread MainContext; `player.py` line 89-90 `enable_sync_message_emission()` then `add_signal_watch()`; queued connection on `twitch_resolved` line 109 |
| PORT-05 (platformdirs for data dir) | **SATISFIED** | `paths.py` line 31 `platformdirs.user_data_dir("musicstreamer")`; grep for hardcoded `~/.local/share/musicstreamer` returns only the intentional legacy reference in `migration.py` |
| PORT-06 (non-destructive first-launch migration) | **SATISFIED** | `migration.py::run_migration()` with marker-file idempotency + same-path short-circuit + `copy2` non-destructive walk; wired into `__main__.py` line 33 |
| PORT-09 (yt-dlp + streamlink library APIs) | **SATISFIED** | `yt_import.py` uses `yt_dlp.YoutubeDL`; `player._twitch_resolve_worker` uses `streamlink.session.Streamlink`; mpv retained on YouTube per explicit spike failure clause in the requirement |
| QA-02 (≥ 265 tests passing, zero GTK imports in tests) | **SATISFIED** | 275 / 265; grep gates clean |

## Anti-patterns scan

| File | Concern | Severity | Notes |
|------|---------|----------|-------|
| `musicstreamer/__main__.py:23` | `DEFAULT_SMOKE_URL = "https://streams.chillhop.com/live?type=.mp3"` returns HTTP `-5` error currently | ℹ Info | Not a code defect, an external URL rot issue. Suggest swapping default to a SomaFM URL (e.g. `groovesalad-128-mp3`) so naive `python -m musicstreamer` runs produce visible ICY output. Non-blocking. |
| `deferred-items.md` | Claims a "bus signal watch context mismatch" defect that does not actually exist (verified by live repro) | ⚠ Warning | Should be retracted when Phase 36 starts so the planner doesn't waste time hunting a non-bug. |

No blockers. No stub implementations. No TODO/FIXME markers in shipped code.

## Behavioral spot-checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Test suite passes offscreen | `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -q` | `275 passed in 2.64s` | ✓ PASS |
| Headless entry produces ICY titles on working stream | `.venv/bin/python -m musicstreamer https://ice1.somafm.com/groovesalad-128-mp3` | `ICY: Bluetech - Oleander (Phutureprimitive Symbiotic Remix)` | ✓ PASS |
| Headless entry dispatches error signal on broken stream | `.venv/bin/python -m musicstreamer` (default chillhop URL) | `ERROR: ... streaming stopped, reason error (-5)` + `FAILOVER: exhausted` | ✓ PASS |
| platformdirs Linux path | `python -c "import platformdirs; print(platformdirs.user_data_dir('musicstreamer'))"` | `/home/kcreasey/.local/share/musicstreamer` | ✓ PASS |
| player.py forbidden imports | `grep -E "GLib\.idle_add\|GLib\.timeout_add\|GLib\.source_remove\|dbus\|DBusGMainLoop" musicstreamer/player.py` | (no matches) | ✓ PASS |
| tests forbidden imports | `grep -rnE "^import gi\|^from gi\.repository\|import dbus\|from dbus" tests/` | (no matches) | ✓ PASS |

## Notes for the planner

1. **Retract `deferred-items.md`.** The bus-signal-watch context mismatch
   described there is not a real defect. The Plan 35-05 executor misread a
   URL-rot symptom as a Qt/GLib integration bug. Live repro proves ICY
   dispatch works under `QCoreApplication` + GstBusLoopThread today.

2. **Consider swapping `DEFAULT_SMOKE_URL`** in `musicstreamer/__main__.py`
   from the dead chillhop URL to `https://ice1.somafm.com/groovesalad-128-mp3`
   so a naive `python -m musicstreamer` run produces a visible ICY title in
   the log. Tiny one-line change; optional since Phase 36 replaces
   `__main__.py` entirely.

3. **Phase 36 can proceed unblocked.** Phase 35 delivers a working headless
   Qt backend with ICY dispatch, failover, error recovery, and 275 passing
   tests. The Qt UI scaffold (PORT-03, PORT-04, QA-01) has no hidden player
   regressions waiting to ambush it.

---

_Verified: 2026-04-11_
_Verifier: Claude (gsd-verifier)_
