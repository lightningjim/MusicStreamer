# Phase 35 Deferred Items

*No deferred items. The previously recorded issue has been retracted after verification.*

---

## Retracted 2026-04-11

### ~~Bus signal watch context mismatch~~ — NOT A REAL DEFECT

**Original claim (Plan 35-05 executor):** Live ICY title dispatch was
blocked by a `GLib.MainContext` attachment bug where
`bus.add_signal_watch()` in `Player.__init__` supposedly bound the bus
watch to the wrong thread-default context under `QCoreApplication`.

**Status:** RETRACTED after `35-VERIFICATION.md` review.

During verification the reviewer reproduced live playback against
SomaFM Groove Salad (`https://ice1.somafm.com/groovesalad-128-mp3`)
and confirmed ICY titles DO flow through to stdout correctly. The bus
bridge dispatches messages to the Qt main thread under
`QCoreApplication` exactly as designed, and the `playback_error` Qt
signal fires correctly on dead streams — proving the bus bridge is
sound on both success and error paths.

**True root cause of the false alarm:** The Plan 35-05 executor only
tested with the hardcoded default URL
`https://streams.chillhop.com/live?type=.mp3`, which currently returns
HTTP `-5` from `souphttpsrc` — a dead stream, not a Qt/GLib
integration bug. The executor attributed the lack of ICY output to a
context-mismatch theory when the real cause was "the test stream is
offline."

**Fix applied in this same session:** Default URL in
`musicstreamer/__main__.py` changed from the dead chillhop endpoint
to SomaFM Groove Salad so naive `python -m musicstreamer` produces
visible ICY output.

**No action needed in Phase 36.** The bus bridge works as designed.
</content>
</invoke>
