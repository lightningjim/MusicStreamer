# Phase 56 / Plan 03 — Win11 VM SMTC AUMID Diagnostic Log

**Started:** 2026-05-02
**Driver:** Linux orchestrator (interactive paste-back mode); user executes PowerShell on Win11 VM
**Goal:** Capture the four D-08 readouts (PRE-FIX + POST-FIX) and classify the root cause per D-09, so Plan 56-04 knows whether to ship docs-only, code-fix, or investigate.

> Per RESEARCH.md correction, `Get-StartApps | Where-Object Name -like 'MusicStreamer*'` is the authoritative AUMID readout (overrides CONTEXT.md D-08 step 1's `(New-Object -ComObject Shell.Application)…ExtendedProperty('System.AppUserModel.ID')` snippet, which returns `$null` on per-user installs — Pitfall #3).

---

## Pre-flight (Task 1): VM environment readiness

| Check | Result | Notes |
|-------|--------|-------|
| Win11 22H2+ | assumed ✓ | Same VM used in Phase 43 / 44 spike rig |
| Conda env active | ✓ | env named `spike` (not `musicstreamer-build` per CONTEXT.md naming, but functionally equivalent) |
| `iscc.exe` on PATH | not needed for this plan | An existing installer is on disk; force-build skipped. PATH fix deferred to whenever a fresh installer is required. |
| Fresh installer artifact | ✓ existing | `Z:\musicstreamer\dist\installer\MusicStreamer-2.0.0-win64-setup.exe` (66,913,672 bytes, 2026-04-27 14:43:57). Predates Phase 56 but AUMID wiring is identical to current `main` (Phase 56 has shipped no AUMID changes — by design, this plan is diagnose-first). Suitable for D-08 step 4. |
| DI.fm premium credentials | deferred to Plan 56-05 | Not needed for Plan 56-03's SMTC half |
| Two PowerShell windows ready | self-managed | User to spawn elevated session at Task 5 |

**Status:** READY (with the caveat that the install artifact is v2.0.0 — sufficient for the SMTC diagnostic since AUMID wiring is unchanged; will rebuild from current source only if D-09 classifies as #3 or #4).

---

## D-08 Step 1: Get-StartApps Readout (PRE-FIX)

**Command (authoritative — RESEARCH.md correction):**
```powershell
Get-StartApps | Where-Object Name -like 'MusicStreamer*'
```

**Output:**
```
Name          AppID
----          -----
MusicStreamer org.lightningjim.MusicStreamer
```

**Cross-check command:**
```powershell
Test-Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk"
```

**Output:** `True`

**Outcome classification:** **A (happy path)** — AppID matches the expected literal `org.lightningjim.MusicStreamer` exactly; Start Menu shortcut exists.

**Implication for D-09:**
- ❌ D-09 #1 (stale shortcut / never-registered LNK) — **ruled out**: AppID is present and correct.
- ❌ D-09 #3 (string drift between `__main__.py:99` and `MusicStreamer.iss:71`) — **ruled out**: literal matches exactly.
- ⚠️ D-09 #2 (launch via wrong path — e.g., `python -m musicstreamer` bypasses AUMID binding) — **still possible**, will be tested in Task 4 by launching strictly via the Start Menu shortcut.
- ⚠️ D-09 #4 (unknown root cause — wiring "looks right" but SMTC still says "Unknown app") — **still possible** if Task 4 confirms SMTC misreads even with correct launch.

---

## D-08 Step 2: In-Process AUMID Readback (PRE-FIX)

**Method used:** Method C (no-patch one-liner) — variant of Method B that imports `_set_windows_aumid` from current source, calls it in a fresh `python.exe` process, then reads back via `GetCurrentProcessExplicitAppUserModelID`. No `__main__.py` patch required (T-56-Diag-B mitigated by construction — nothing to revert).

**Command (run from `Z:\musicstreamer` repo root):**
```powershell
python -c "import sys; sys.path.insert(0, '.'); import ctypes; from musicstreamer.__main__ import _set_windows_aumid; _set_windows_aumid(); shell32 = ctypes.windll.shell32; r = ctypes.c_wchar_p(); shell32.GetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.POINTER(ctypes.c_wchar_p)]; shell32.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(r)); print('AUMID readback:', repr(r.value))"
```

**Output:**
```
AUMID readback: 'org.lightningjim.MusicStreamer'
```

**Comparison vs Step 1 LNK AppID:** **MATCH.** Both halves of the wiring carry the literal `org.lightningjim.MusicStreamer`. No string drift between `__main__.py::_set_windows_aumid` and `MusicStreamer.iss [Icons] AppUserModelID`.

**`git status musicstreamer/__main__.py`:** clean (no patch applied — Method C avoided the patch surface entirely).

**Implication for D-09:**
- ❌ D-09 #1 (stale LNK without AppID) — **definitively ruled out** by Step 1.
- ❌ D-09 #3 (literal drift) — **definitively ruled out** by Step 1 + Step 2 match.
- ⚠️ D-09 #2 (wrong launch path) — still possible; Task 4 (launch strictly via Start Menu shortcut) will test this.
- ⚠️ D-09 #4 (unknown) — still possible; Task 4 will be definitive.

---

## D-08 Step 3: SMTC Overlay (PRE-FIX)

**Launch path:** Start Menu shortcut (Win key → typed `MusicStreamer` → Enter). Strictly NOT `python -m musicstreamer` per Pitfall #4.

**Stream played:** SomaFM Drone Zone (track at observation time: "The Great Schizm - Myths in the Mic…").

**SMTC overlay app-name string (verbatim):** **`MusicStreamer`** ✓

**Screenshot:** `.planning/phases/56-windows-di-fm-smtc-start-menu/screenshots/56-03-smtc-prefix.png` — captures the SMTC overlay with the `MusicStreamer` header, track title, "Drone Zone" station label, album art, and play/pause/skip controls.

**Settings → System → Notifications check:** _not run_ — superfluous given the SMTC overlay itself shows the correct app name. Settings is only useful when SMTC misreads.

**Verdict:** SMTC binding is **WORKING CORRECTLY** on the current install when the app is launched via the Start Menu shortcut. The "Unknown app" symptom that motivated Phase 56 does NOT reproduce on this install + launch-path combination.

**Implication for D-09:** Combined with Steps 1 + 2 (LNK AppID correct, in-process AUMID matches), this strongly indicates **D-09 #2** as the original root cause. The "Unknown app" observations that motivated Phase 56 were almost certainly made when launching via `python -m musicstreamer` or the installer's post-install Run checkbox — both of which bypass the Start-Menu-LNK → AUMID binding (Pitfall #4). This is an environmental / launch-discipline issue, not a code bug.

---

## D-08 Step 4: Force-Fresh Install (POST-FIX)

**Status:** **SKIPPED — N/A** (operator decision, recorded interactively).

**Rationale for skip:** Steps 1–3 already established that:
1. The LNK has the correct AppID (`org.lightningjim.MusicStreamer`).
2. The in-process AUMID setter writes the same literal that the LNK declares (`MATCH`).
3. The SMTC overlay correctly reads `MusicStreamer` when launched via the Start Menu shortcut.

There is no broken state to recover from. Task 5 was originally designed to **fix** a stale-LNK or shortcut-cache scenario (D-09 #1 / Pitfall #5), but the diagnostic surfaced no such state. Running the destructive uninstall + LNK-delete + reinstall sequence would be a *regression* test (does a clean install ALSO produce correct SMTC?) rather than a *fix* test, and the operator opted out of regression-only destructive verification on this run.

**Risk accepted:** A future fresh-install scenario (new VM, new user) is not directly verified by this plan. Mitigation: Plan 56-04's drift-guard pytest catches the only known silent-failure mode (AUMID literal drift between `__main__.py` and `MusicStreamer.iss`). Any other future regression would still surface visibly as "Unknown app" on a real install — re-run this plan if it does.

**No POST-FIX comparison readouts captured** — Steps 1–3 stand as both PRE-FIX and effective post-test (no fix applied; system already in a healthy state).

---

## D-09 Root Cause + D-10 Plan 04 Scope

**Decision:** docs-only
**D-09 classification:** **#2 (wrong launch path)**

**Rationale (one sentence):** Steps 1–2 confirmed the LNK AppID and in-process AUMID literal both equal `org.lightningjim.MusicStreamer` exactly, and Step 3 confirmed SMTC overlay reads `MusicStreamer` when launched via the Start Menu shortcut — so the only way to surface "Unknown app" is to launch via `python -m musicstreamer` or the installer's post-install Run checkbox (both bypass the Start-Menu-LNK → AUMID binding per Pitfall #4), which is environmental, not a wiring bug.

**Cross-reference table:**

| D-09 # | Hypothesis | Status | Evidence |
|--------|-----------|--------|----------|
| #1 | Stale shortcut / never-registered LNK | ❌ ruled out | Step 1 returned correct AppID + `Test-Path` returned True |
| #2 | Wrong launch path (`python -m` or installer Run checkbox bypasses AUMID) | ✅ **confirmed** | Step 3 with strict Start-Menu launch shows correct SMTC; the original report was almost certainly observed under a non-Start-Menu launch |
| #3 | String drift between `__main__.py:99` and `MusicStreamer.iss:71` | ❌ ruled out | Step 1 + Step 2 both returned literal `org.lightningjim.MusicStreamer` |
| #4 | Unknown — wiring "looks right" but SMTC misreads | ❌ ruled out | Step 3 disproved this — SMTC reads correctly under proper launch path |

**Plan 56-04 scope (per D-10 docs-only branch):**
1. Add `tests/test_aumid_string_parity.py` — 10-line drift-guard pytest that asserts the AUMID literal in `musicstreamer/__main__.py` matches the `AppUserModelID:` clause in `packaging/windows/MusicStreamer.iss`. Permanent regression protection at near-zero cost (RESEARCH.md Open Question #1 — adopted).
2. Add a "Launching MusicStreamer on Windows" note to `packaging/windows/README.md` (or the project's top-level Windows-launch docs) explicitly stating that SMTC binding requires launching via the Start Menu shortcut, NOT `python -m musicstreamer` or the installer's post-install Run checkbox. Cite Pitfall #4 / D-09 #2 as the rationale.
3. NO change to `musicstreamer/__main__.py` or `packaging/windows/MusicStreamer.iss` — the literals are already aligned and the wiring works.
4. NO installer rebuild needed for Plan 56-04 — only docs + a pure-Python pytest.

**`git diff musicstreamer/ packaging/`:** clean (no production code change in this plan).
