# Phase 35: Backend Isolation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-11
**Phase:** 35-backend-isolation
**Areas discussed:** Phase scope framing, Spike ordering, Headless Qt entry point, mpris disposition, Test port strategy, Data migration, Qt timing

---

## Round 1 — Initial gray areas

### Phase ordering / spike timing

| Option | Description | Selected |
|--------|-------------|----------|
| Spike first | Run mpv-drop validation first so yt-dlp library port knows whether mpv paths stay | ✓ |
| Spike last | Sequence spike at the end as a final validation gate | |

**User's choice:** Spike first
**Notes:** Result informs the yt-dlp library API port surface area.

### Qt event loop availability in Phase 35

| Option | Description | Selected |
|--------|-------------|----------|
| QCoreApplication in Phase 35 | Install a headless Qt event loop so QTimer works | |
| Keep GLib.timeout_add, migrate in Phase 36 | Defer Qt timers to Phase 36 | ✓ (initial) |
| threading.Timer abstraction | Platform-neutral timers | |

**User's choice:** (initial) "let's do QT in phase 36" — interpreted as deferring Qt conversion
**Notes:** Later revised — see Round 2.

### Linux data migration semantics

| Option | Description | Selected |
|--------|-------------|----------|
| No-op helper on Linux | Migration helper runs but is a no-op since Linux path matches platformdirs | ✓ |
| Real cross-directory only when paths differ | Skip migration code entirely on Linux | |
| Generic non-destructive copy regardless | Always copy even when paths match | |

**User's choice:** No-op helper on Linux
**Notes:** Real cross-path logic deferred until Windows exists.

### Test infrastructure ordering

| Option | Description | Selected |
|--------|-------------|----------|
| pytest-qt in Phase 35 | Port tests to pytest-qt this phase | |
| Keep GTK test harness in 35, move 265-pass gate to Phase 36 | Defer Qt test port | ✓ (initial) |
| pytest-qt with GTK tests coexisting | Hybrid conftest | |

**User's choice:** (initial) "pause QT until phase 36"
**Notes:** Later revised — see Round 2.

### mpris.py disposition

| Option | Description | Selected |
|--------|-------------|----------|
| Leave untouched | Keep mpris.py alive | |
| Stub out / disconnect | Replace with no-op | ✓ |
| Pull MEDIA-02 forward | Rewrite to QtDBus now | |

**User's choice:** "We can do without media keys for now" → stub
**Notes:** Real QtDBus rewrite remains scheduled for Phase 41.

---

## Round 2 — Reframed after user requested a restart

After clarifying the tension between "Qt in Phase 35" (per roadmap) and "Qt in Phase 36" (user's initial read), two coherent options were presented:

### Phase scope framing

| Option | Description | Selected |
|--------|-------------|----------|
| **Option A — Qt-first backend** | Phase 35 does the QObject conversion with a headless QCoreApplication, pytest-qt installed, mpris stubbed, 265-test gate lands at end of Phase 35. Matches roadmap + REQUIREMENTS.md as written. | ✓ |
| Option B — Backend prep, Qt in 36 | Phase 35 stays non-Qt (spike + yt-dlp library port + platformdirs only); PORT-01/02/QA-02 shift to Phase 36. | |

**User's choice:** Option A

---

## Round 3 — Remaining gray areas under Option A

### A. Headless QCoreApplication entry point

| Option | Description | Selected |
|--------|-------------|----------|
| (a) New `musicstreamer/__main__.py` + script harness | Instantiate QCoreApplication, construct Player, tiny REPL/script that plays a URL to satisfy success criterion #1 | ✓ |
| (b) pytest fixture only | Verify via test, no runnable app | |
| (c) Bolt QCoreApplication onto existing GTK main.py | Minimal churn, ugly | |

**User's choice:** (a)

### B. mpris.py disposition (under Option A)

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Stub as no-op class | Same public interface, silent | ✓ |
| (b) Disconnect behind dead-code flag | Leave on disk, never constructed | |
| (c) Pull MEDIA-02 forward | Rewrite to QtDBus in Phase 35 | |

**User's choice:** (a)

### C. Test port strategy

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Big-bang port | Single plan task converts all 265 tests | ✓ |
| (b) Incremental | Port tests file-by-file alongside code they cover | |
| (c) Shim | Hybrid conftest with both GTK and Qt fixtures | |

**User's choice:** (a)

---

## Claude's Discretion

- QObject signal signatures (`Signal(str)` vs `Signal(object)`) for title, failover, offline, elapsed-timer events
- Exact module layout for `paths.py`
- Whether `__main__.py` takes a URL CLI arg or hard-codes a known-good smoke URL
- Whether spike runs in CI or local-only

## Deferred Ideas

- QtDBus MPRIS2 rewrite → Phase 41
- Qt UI scaffold + GTK delete + icon bundling → Phase 36
- Real Windows platformdirs migration path → Phase 44
- `_popen()` CREATE_NO_WINDOW helper → Phase 44 (unless mpv spike fails)
</content>
</invoke>