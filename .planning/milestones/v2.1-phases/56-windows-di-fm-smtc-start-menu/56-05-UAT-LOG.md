# Phase 56 / Plan 05 — UAT Log

**Started:** 2026-05-02
**Path chosen:** **Path C** (python-m direct from current source) — operator decision per discussion in chat. Skips installer rebuild + force-fresh-install since:
- WIN-02 SMTC overlay is already PASS-attested in `56-03-DIAGNOSTIC-LOG.md` Step 3 (screenshot at `screenshots/56-03-smtc-prefix.png` shows "MusicStreamer" header).
- The v2.0.0 installer on the VM doesn't contain Phase 56-01/02's WIN-01 changes; only the current source tree does.
- `iscc` is not currently on PATH on the VM, so building a 2.1.56-tagged installer would be extra setup.
- Path C tests the actual code path (helper + wire-in + Windows GStreamer TLS stack) without needing a packaged install.

**Trade-off accepted:** Path C runs MusicStreamer outside the Start-Menu launch (so SMTC binding is intentionally bypassed for this run — not a regression). WIN-02 attestation is cited from 56-03 evidence rather than re-verified here.

---

## WIN-02: SMTC overlay reads "MusicStreamer"

**Status:** **PASS** (cited from 56-03)

**Source of attestation:**
- `56-03-DIAGNOSTIC-LOG.md` § "D-08 Step 3: SMTC Overlay (PRE-FIX)" — the SMTC overlay read literally `MusicStreamer` while SomaFM Drone Zone was playing on a Start-Menu-launched session.
- `Get-StartApps` AppID = `org.lightningjim.MusicStreamer` (56-03 § "D-08 Step 1").
- In-process AUMID readback = `'org.lightningjim.MusicStreamer'` (56-03 § "D-08 Step 2") — MATCHES `Get-StartApps` AppID.
- Screenshot: `.planning/phases/56-windows-di-fm-smtc-start-menu/screenshots/56-03-smtc-prefix.png`.

**ROADMAP SC coverage:**
- ✓ SC #2: Start Menu shortcut carries `System.AppUserModel.ID=org.lightningjim.MusicStreamer` (56-03 Step 1)
- ✓ SC #3: SMTC overlay shows "MusicStreamer" not "Unknown app" (56-03 Step 3)
- ✓ SC #4: AUMID on shortcut matches in-process AUMID (56-03 Step 1 + Step 2)

**Why this re-attestation isn't redundant:** The 56-03 diagnostic captured the same conditions Plan 56-05's UAT script asks for. Re-running here would produce the same screenshot. Drift-guard pytest (Plan 56-04 `tests/test_aumid_string_parity.py`) provides ongoing protection against future regression of SC #2/#4 (AUMID literal divergence).

---

## WIN-01a: DI.fm Lounge fresh AA import

**Status:** **PASS**

**Test path:** Path C — `python -m musicstreamer` from `(spike) PS Z:\musicstreamer>` against current source tree (commits `eccbdf7` and `2788351` confirmed present, so Phase 56-01 helper + 56-02 wire-in are exercised).

**Procedure:**
1. Stopped any existing MusicStreamer process.
2. Launched `python -m musicstreamer` from spike conda env.
3. Settings → AudioAddict → entered DI.fm premium credentials → triggered fresh AA import (D-12 part a path).
4. Selected DI.fm channel **Afro House** (canonical-equivalent test channel — D-12 names DI.fm Lounge as the canonical example but ANY DI.fm channel exercises the same `_set_uri` + `aa_normalize_stream_url` code path).
5. Clicked Play.

**Observations:**
- Channel: **Afro House** (DI.fm)
- Time to first audio: **~3 seconds** (well under the 10-second PASS bar)
- First ICY title displayed: **"Ame, Busiswa - Pha Na Pha (Original Mix)"** (PASS bar requires title within 30s; observed in seconds)
- GStreamer error: **none** — the `error (-5)` symptom that motivated this phase did NOT recur, confirming the `https://` → `http://` rewrite at the URI boundary engaged correctly on the freshly-imported DI.fm row

**Implication:** The Phase 56-01 helper (`aa_normalize_stream_url`) + Phase 56-02 wire-in at `musicstreamer/player.py::_set_uri` are working correctly against the actual Win11 GStreamer pipeline + OpenSSL TLS backend (conda-forge gstreamer 1.28). The Linux unit + integration tests (59 passing) translated cleanly to Windows runtime.

**ROADMAP SC coverage:** ✓ SC #1 (DI.fm premium stream plays on Windows).

---

## WIN-01b: DI.fm settings-import ZIP roundtrip

**Status:** **PASS** (with a planning-level surprise — see "Findings" below)

**Test path:** Operator-driven manual roundtrip. On the Linux build host, the operator edited a station to use `https://prem*.di.fm/...`, exported via Settings → Export, transferred the ZIP to the VM, and imported via Settings → Import. The imported row stayed `https://` in the DB (rewrite is at play-time URI boundary, not at insert-time, exactly per D-01). On the VM the operator pressed Play on that imported https-DI.fm row.

**Result:** Played fine. No `error (-5)`. The Phase 56-02 wire at `musicstreamer/player.py::_set_uri` engaged the Phase 56-01 helper, normalized the URL from `https://` → `http://`, and `playbin3`/`souphttpsrc` accepted the rewritten URL.

**This is the strict, meaningful proof of D-01** — see Findings below for why WIN-01a was actually a weaker test.

**ROADMAP SC coverage:** ✓ SC #1 (DI.fm premium stream plays on Windows — strict version: stored `https://` row in the DB plays via play-time rewrite).

---

## Findings (Surprises during UAT)

### F1 — AA import on Windows produces `http://` rows natively

**CONTEXT.md / RESEARCH.md premise (now superseded by empirical evidence):** AA import inserts DI.fm rows with the `https://` scheme; the Phase 56-01/02 rewrite normalizes them at play time.

**Empirical reality (observed during WIN-01a):** AA import on the Win11 VM inserts DI.fm rows with the `http://` scheme directly. The Phase 56-01 helper is therefore a **no-op** for the fresh-AA-import path — there's nothing for it to rewrite.

**Implication:** WIN-01a (Afro House fresh-import play test) confirmed only that the wire-in didn't *break* the existing happy path. It did NOT exercise the rewrite logic. WIN-01b is the only test where the helper actually does work — it normalized a stored `https://` row to `http://` at `_set_uri` and let `playbin3` succeed.

**Why this isn't a problem:** D-06 (idempotency) means the helper is a safe pass-through for already-`http://` URLs. The wire is correct. The only thing that's "wrong" is CONTEXT.md's premise about how AA inserts URLs on Windows — which is documentation drift, not a code bug.

**Disposition:** Note in Phase 56 SUMMARY for future reference. Not a blocker for shipping — both halves of D-12 (fresh import + roundtrip) play correctly; the strict roundtrip test (WIN-01b) is the one that proves the rewrite engages.

### F2 — AAC streams don't play on Windows (Phase 57+ candidate)

**Symptom:** AAC-encoded streams don't play on the Win11 VM (operator note during UAT).

**Suspected cause:** Missing or misbundled GStreamer AAC decoder plugin (`faad`, `avdec_aac` via gst-libav, or similar). Phase 43's bundle audit covered MP3/Opus/Vorbis but AAC may not have been verified end-to-end. Out of scope for Phase 56.

**Disposition:** Capture as a new bug (e.g., `WIN-05` or similar) in REQUIREMENTS.md / next milestone, target Phase 57 or later. Do NOT fold into Phase 56.

### F3 — Pre-edit-fetch crash fixed in main but not in Windows installer

**Symptom (operator note):** A bug where saving an edit while a fetch is loading crashes the app has been fixed in `main` but the current Win11 install (v2.0.0) doesn't have the fix.

**Disposition:** Operational, not a Phase 56 issue. A fresh installer rebuild (Path A from the UAT discussion) would bake in this fix along with Phase 56-01/02. Operator may choose to rebuild now (closes both Phase 56's WIN-01 release-attestation and the operational bug fix) or later (Phase 56 ships on Path C evidence; rebuild is independent).

---

## Release-Grade Re-attestation (post `build.ps1` rebuild)

After the operator rebuilt the installer via `build.ps1` and force-fresh-installed (uninstall → delete `%LOCALAPPDATA%\Programs\MusicStreamer` + LNK → reinstall with Run checkbox UNCHECKED, preserving `%APPDATA%\musicstreamer` and `%LOCALAPPDATA%\musicstreamer`), the operator confirmed all three ROADMAP success criteria pass on the **installed binary** (not just the `python -m` source-tree run from Path C).

**Operator confirmation:** "All confirmed on this side of the testing."

This converts each Path C / cited attestation above into a release-grade attestation:
- ✓ **WIN-01 release-grade:** DI.fm playback works in the installed binary on Win11.
- ✓ **WIN-02 release-grade:** SMTC overlay reads "MusicStreamer" with the freshly-installed binary launched via Start Menu shortcut.
- ✓ **F3 release-grade bonus:** the edit-while-fetching crash fix (already in main, previously absent from the v2.0.0 install) is now baked in.

User data (`%APPDATA%\musicstreamer\musicstreamer.sqlite3`) and cache (`%LOCALAPPDATA%\musicstreamer`) preserved across the reinstall as designed (D-03).

---

## Phase Completion Decision

**Decision:** **ship-phase**

**Rationale:** All four ROADMAP success criteria are PASS on a release-grade install:
- ✓ SC #1 (DI.fm premium plays on Windows) — WIN-01a + WIN-01b both PASS, helper engages at the URI boundary as D-01 specifies, release-grade re-attestation in installed binary.
- ✓ SC #2 (Start Menu shortcut carries `System.AppUserModel.ID=org.lightningjim.MusicStreamer`) — confirmed by `Get-StartApps` in 56-03 Step 1 + post-rebuild re-attestation.
- ✓ SC #3 (SMTC overlay shows "MusicStreamer", not "Unknown app") — confirmed by 56-03 Step 3 screenshot + post-rebuild re-attestation.
- ✓ SC #4 (AUMID on shortcut matches in-process AUMID) — confirmed by 56-03 Step 1 + Step 2 match + post-rebuild re-attestation.

**Follow-up actions (NOT blocking phase complete):**
1. **Capture F2 (AAC streams don't play on Windows)** as a new requirement (e.g., `WIN-05`) in `.planning/REQUIREMENTS.md`, target Phase 57 or later. Out of scope for Phase 56.
2. **Note F1 (AA import inserts http natively on Windows, not https as CONTEXT.md assumed)** — documentation drift only; the helper is still correct (idempotent passthrough for already-http) and the strict roundtrip test (WIN-01b) proves the rewrite engages on stored https rows. No code change needed.
3. **Next steps:** `/gsd-verify-work 56` for goal-backward verification, then `/gsd-complete-phase` (or `/gsd-ship`) to close.
