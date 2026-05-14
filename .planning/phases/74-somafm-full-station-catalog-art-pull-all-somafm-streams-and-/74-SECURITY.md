---
phase: 74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-
audited_at: 2026-05-14
auditor: gsd-security-auditor
asvs_level: 1
block_on: critical
threats_total: 13
threats_closed: 13
threats_open: 0
status: secured
implementation_files:
  - musicstreamer/soma_import.py
  - musicstreamer/ui_qt/main_window.py
  - tests/test_soma_import.py
  - tests/test_main_window_soma.py
---

# Phase 74: Security Audit Report

**Phase:** 74 — SomaFM full station catalog (art + pull all SomaFM streams)
**ASVS Level:** 1
**Block-on:** critical
**Threats Closed:** 13 / 13
**Status:** SECURED

## Audit Method

The threat register was authored at plan time (PLAN.md `<threat_model>` block,
Plans 02 / 03 / 04 / 05 / 06) and merged here as the canonical Phase 74 view.
Each threat was verified by its declared disposition:

- `mitigate` — verified by grep / read of the cited implementation file(s)
  for the declared mitigation pattern.
- `accept` — verified that the rationale (from the PLAN.md threat row) is
  recorded in the Accepted Risks section below.
- `transfer` — N/A (no threats in this phase carry the `transfer` disposition).

A post-implementation code-review fix pass (commits `0cdb767..11e70da`,
documented in `74-REVIEW-FIX.md`) strengthened five of the mitigations and
introduced three additional hardening items not present in the original
register. These deltas are captured in the Hardening Delta section below;
they do not change a `CLOSED` disposition but increase defense-in-depth.

## Threat Verification

| Threat ID  | Category | Disposition | Evidence (file:line) | Status |
|------------|----------|-------------|----------------------|--------|
| T-74-01    | I (info disclosure / fingerprinting on outbound HTTP) | mitigate | `musicstreamer/soma_import.py:50-53` (`_USER_AGENT` constant carries `MusicStreamer/{ver}` + `https://github.com/lightningjim/MusicStreamer`); `musicstreamer/soma_import.py:101` (`Request(..., headers={"User-Agent": _USER_AGENT})` in `_safe_urlopen_request`); applied at all three call sites: `fetch_channels` (line 192), `_resolve_pls` (line 162), `_download_logo` (line 383). Source-grep gate enforced by `tests/test_soma_import.py::test_user_agent_literal_present_in_source`. | CLOSED |
| T-74-02    | T (data integrity — codec literal regression) | mitigate | `musicstreamer/soma_import.py:72-77` `_TIER_BY_FORMAT_QUALITY` maps `aacp` → `"AAC"` (NOT `"AAC+"`); `tests/test_soma_import.py::test_aacp_codec_maps_to_AAC_not_aacplus` (behavioral) + `tests/test_soma_import.py::test_no_aacplus_codec_literal_in_source` (source-grep gate with comment-strip per project memory `feedback_gstreamer_mock_blind_spot.md`). | CLOSED |
| T-74-03    | T (PLS-as-stream silent data corruption) | mitigate | `musicstreamer/soma_import.py:143-171` `_resolve_pls` parses via `parse_playlist` and returns the list of direct `ice*.somafm.com` URLs; on failure returns `[]` (Phase 74 REVIEW CR-01 strengthening — see Hardening Delta below). Verified by `tests/test_soma_import.py::test_resolve_pls_returns_all_five_direct_urls`. | CLOSED |
| T-74-04    | D (logo failure cascading to station insert loss) | mitigate | `musicstreamer/soma_import.py:381-415` `_download_logo` wraps the entire body (Request build → urlopen → tempfile → copy_asset → Repo.update_station_art) in `try/except Exception` (line 408). Station + streams remain inserted on any logo failure; `update_station_art` is not reached. Verified by `tests/test_soma_import.py::test_logo_failure_is_non_fatal`. | CLOSED |
| T-74-05    | D (cross-channel exception aborts entire batch) | mitigate | `musicstreamer/soma_import.py:273-361` `import_stations` wraps the per-channel loop body in `try/except Exception` (line 283 / 342); `skipped += 1` on failure (line 361); loop continues. AST-scan and `tests/test_soma_import.py::test_per_channel_exception_skips_only_that_channel` confirm the structure. Mirror try/except also present in `fetch_channels` (line 243). | CLOSED |
| T-74-06    | I (info disclosure via toast text) | accept | See Accepted Risks below. Truncation present at `musicstreamer/ui_qt/main_window.py:1547` (`msg[:80] + "…"`); toast uses `show_toast` (plain text, no `setTextFormat(Qt.RichText)`). | CLOSED |
| T-74-07    | D (worker GC mid-flight) | mitigate | `musicstreamer/ui_qt/main_window.py:1522` `self._soma_import_worker = _SomaImportWorker(parent=self)` retains the worker; `parent=self` adds Qt parent-child anchoring. Cleared to `None` in `_on_soma_import_done` (line 1534) and `_on_soma_import_error` (line 1550). Verified by `tests/test_main_window_soma.py::test_import_soma_triggers_worker_start_and_retains_reference`. | CLOSED |
| T-74-08    | D (live network failure during UAT) | accept | See Accepted Risks below. UAT 74-04 walked under live `api.somafm.com:443`; net reachable; no `pending` row recorded. | CLOSED |
| T-74-09    | T (library DB pollution from flawed import) | accept | See Accepted Risks below. User instructed to back up `~/.local/share/musicstreamer/library.db` in `74-04-UAT-LOG.md`. D-05 dedup-by-URL makes re-import safe. | CLOSED |
| T-74.1-01  | T (upstream-controlled bitrate field) | accept | See Accepted Risks below. Field is an `int` used only for sort-order; SQL inserts are parameterised; range now bounded `[8, 9999]` by WR-03 hardening. | CLOSED |
| T-74.1-02  | D (regex engine on adversarial input) | mitigate | `musicstreamer/soma_import.py:110` `_BITRATE_FROM_URL_RE = re.compile(r"-(\d{1,5})-(?:mp3\|aac\|aacp)\b")` — linear NFA, no nested quantifiers, digit-run capped at 5 chars (WR-03 strengthening from `\d+` → `\d{1,5}`). | CLOSED |
| T-74.1-03  | T (Qt signal name shadows `QThread.finished`) | mitigate | `musicstreamer/ui_qt/main_window.py:89` (`_ExportWorker.export_finished`), `:107` (`_ImportPreviewWorker.preview_finished`), `:135` (`_GbsImportWorker.import_finished`), `:162` (`_SomaImportWorker.import_finished`). Source-grep gate: `grep -E '^\s+finished\s*=\s*Signal' musicstreamer/ui_qt/main_window.py` returns zero matches. Verified by `tests/test_main_window_soma.py::test_re_import_emits_no_changes_toast_via_real_thread` (live qtbot regression). | CLOSED |
| T-74.1-04  | D (qtbot waitUntil 5s timeout in regression test) | accept | See Accepted Risks below. `tests/test_main_window_soma.py:371-373` uses `qtbot.waitUntil(..., timeout=5000)`; loud failure is preferred over a silent regression. | CLOSED |

## Accepted Risks

The following dispositions are `accept` rather than `mitigate`. Each entry
records the rationale verbatim from the PLAN.md threat row so the audit trail
shows what was knowingly carried forward.

### T-74-06 — Toast text may include stack-trace-like content from `str(exc)`

> Rationale: `str(exc)` may contain stack-trace-like content from arbitrary
> stdlib exceptions. Truncation to 80 chars + `"…"` mitigates the worst case;
> a future hardening phase could scrub stack frames, but for a public-API
> importer the user-actionable signal trumps the disclosure risk.

Truncation evidence: `musicstreamer/ui_qt/main_window.py:1547`
(`truncated = (msg[:80] + "…") if len(msg) > 80 else msg`). Toast surface is
plain text via `show_toast()` — no `setTextFormat(Qt.RichText)` invocation;
T-40-04 RichText invariant remains at the pre-Phase-74 baseline.

### T-74-08 — Live `api.somafm.com` reachability during UAT

> Rationale: If `api.somafm.com` is unreachable during the UAT window, the
> user marks UAT-01..UAT-03 as `pending — retry when net stable`; the import
> is purely manual so there is no urgency.

UAT walked successfully on 2026-05-14 against live catalog (39 + 7 baseline
= 46 channels). No `pending` rows recorded in `74-04-UAT-LOG.md`.

### T-74-09 — Library DB pollution from a flawed import

> Rationale: The user is instructed to back up `library.db` before running
> UAT, mitigating accidental data loss. D-05 dedup means a re-import on a
> partially-imported library is safe.

`74-04-UAT-LOG.md` includes the pre-test instruction
`cp ~/.local/share/musicstreamer/library.db
~/.local/share/musicstreamer/library.db.pre-phase74`. Additionally, the
Phase 74 REVIEW CR-04 hardening below adds active rollback of partial
station rows on mid-loop failure, so the dedup-only safety net is now
supplemented by transactional cleanup.

### T-74.1-01 — Upstream SomaFM URL slug parsed into bitrate field

> Rationale: The bitrate field is an `int` used only for sort-order in
> `stream_ordering.py` and display labels; an arbitrarily large value cannot
> cause memory exhaustion (single int) or SQL injection (parameterised
> inserts). Upstream SomaFM is the existing trust anchor for this phase;
> the same trust applies to the catalog title, description, and image URL
> fields. Worst case: a single station ranks oddly until the user deletes it.

Range now bounded `[8, 9999]` in `musicstreamer/soma_import.py:132`
(`if 8 <= value <= 9999: return value`) per Phase 74 REVIEW WR-03 hardening.
Out-of-range slugs fall through to the table default, so the "arbitrarily
large int" worst case is no longer reachable from a malicious slug.

### T-74.1-04 — `qtbot.waitUntil(timeout=5000)` in the regression test

> Rationale: 5 s is generous for a worker that does only patched in-memory
> work (no real network). If CI is slow, the test will time out and FAIL
> loudly — preferable to a silent re-shadowing regression.

Code site: `tests/test_main_window_soma.py:371-373`.

## Hardening Delta (Post-Implementation Fix Pass)

The code-review fix pass (commits `0cdb767..11e70da`, `74-REVIEW-FIX.md`)
applied seven security-relevant changes after Phase 74 was originally
closed. None of these are required by the PLAN.md threat register, but they
strengthen the corresponding mitigations or add new defenses not previously
in scope.

| CR/WR ID | Threat strengthened / added | Change | File:line |
|----------|------------------------------|--------|-----------|
| CR-01    | T-74-03 strengthened          | `_resolve_pls` now returns `[]` on failure (was `[pls_url]`). Eliminates the path that persists a `.pls` URL as a stream row and dedups against it on re-import. | `musicstreamer/soma_import.py:171` |
| CR-02    | New defense (file:///ftp:// SSRF) | Added `_ALLOWED_SCHEMES = frozenset({"https", "http"})` + `_safe_urlopen_request` helper. All three urlopen call sites (`fetch_channels`, `_resolve_pls`, `_download_logo`) now reject non-HTTP(S) schemes and empty netlocs before any network/filesystem touch. Closes a local-file-read pivot from a compromised `api.somafm.com` or MitM. | `musicstreamer/soma_import.py:86-101, 162, 192, 383` |
| CR-03    | New defense (SQLite WAL connection leak) | `_download_logo` now wraps `db_connect()` in `try/finally` so the per-logo connection is closed deterministically. Eliminates the dozens-of-WAL-locked-connections accumulation under `ThreadPoolExecutor(max_workers=8)`. | `musicstreamer/soma_import.py:398-402` |
| CR-04    | T-74-05 strengthened          | `import_stations` now tracks `inserted_station_id` per channel and calls `repo.delete_station(...)` on per-channel failure. Half-imported stations are rolled back atomically via `ON DELETE CASCADE` on `station_streams.station_id`. Removes the "silent permanent data corruption" path where a UNIQUE-constraint failure on stream N + dedup-by-URL would pin a broken partial row forever. | `musicstreamer/soma_import.py:282, 339, 342-353` |
| CR-05    | New defense (UI state consistency) | `_on_soma_import_error` now calls `self._refresh_station_list()` so the StationListPanel reflects any rows committed before the failure propagated. | `musicstreamer/ui_qt/main_window.py:1549` |
| WR-02    | T-74-07 strengthened          | Both `_on_soma_import_clicked` and `_on_gbs_add_clicked` now guard against double-spawn via `if self._<x>_import_worker is not None: return`. Prevents racing workers on `station_exists_by_url` checks and prevents the first worker's done-slot from clearing the retention attribute while the second is still running. | `musicstreamer/ui_qt/main_window.py:1464, 1518-1520` |
| WR-03    | T-74.1-02 strengthened        | `_BITRATE_FROM_URL_RE` digit run capped at 5 chars (`\d{1,5}`); parsed value validated in `[8, 9999]` before persistence. Closes the quadratic-time `int()` DoS surface from pre-3.11 CPython (CVE-2020-10735 territory) and the silent-1e12-bitrate UI corruption surface. | `musicstreamer/soma_import.py:110, 132` |
| WR-07    | Diagnostic hardening          | `fetch_channels` distinguishes HTTPError 5xx ("temporarily unavailable") from 4xx ("API rejected the request") so recoverable blips surface a user-actionable toast instead of an opaque "SomaFM import failed: HTTP Error 503". | `musicstreamer/soma_import.py:196-203` |

The other WR / IN findings closed by the fix pass (WR-01 logo log diagnostic,
WR-04 test-side DB monkeypatch, WR-05 file-handle leak in source-grep test,
WR-06 codec precision TODO, IN-01 dead `__init__`, IN-02 `_bitrate_from_url`
→ `bitrate_from_url`, IN-05 log-line `title` correlation) are
non-security-relevant code-quality or test-hygiene fixes; they appear in
`74-REVIEW-FIX.md` for completeness but do not strengthen any threat in this
register.

## Unregistered Flags

None.

All four post-Plan-01 SUMMARY files (74-02, 74-03, 74-05, 74-06) explicitly
record their `## Threat Flags` sections as either "No new network endpoints,
auth paths, file access patterns, or schema changes" or as confirmed
inheritance of the already-registered threats. No new attack surface was
introduced during implementation that lacks a threat-register mapping.

## Audit Trail

- Plan-time threat register: 9 threats in 74-02-PLAN / 74-03-PLAN
  (T-74-01 .. T-74-09); 4 threats added in the gap-closure plans
  (T-74.1-01 .. T-74.1-04 in 74-05-PLAN / 74-06-PLAN). Total: 13.
- All 17 + 2 RED tests from Wave 0 (`tests/test_soma_import.py`,
  `tests/test_main_window_soma.py`, `tests/test_constants_drift.py`)
  turned GREEN by Wave 2 (Plans 74-02 + 74-03).
- Gap-closure Plans 74-05 + 74-06 added 4 new RED tests (bitrate
  parser + live-thread re-import regression) and turned them GREEN.
- Live UAT (74-04 + re-verification 74-07) walked the full import path
  against `api.somafm.com:443` and confirmed UAT-07 (re-import idempotence)
  + UAT F-01 (Synphaera 256 kbps) both closed.
- Code-review fix pass (74-REVIEW + 74-REVIEW-FIX) closed 5 BLOCKER and
  7 WARNING findings; 2 INFO findings explicitly deferred as out-of-scope.

## References

- `74-CONTEXT.md` — D-01 .. D-16 decisions (the canonical phase decisions)
- `74-RESEARCH.md` — STRIDE threat origins + 17-test validation matrix
- `74-VERIFICATION.md` — Gap closure source-of-truth (G-01 + G-02)
- `74-REVIEW.md` — 5 Critical + 7 Warning + 5 Info code review findings
- `74-REVIEW-FIX.md` — 15 of 17 findings closed; 2 INFO deferred
- `74-04-UAT-LOG.md` — Initial live UAT (9 PASS / 1 FAIL — UAT-07)
- `74-07-UAT-LOG.md` — Re-verification UAT (3/3 PASS, both gaps closed)
