---
phase: 87
slug: gbs-fm-marquee-themed-day-detection
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-15
---

# Phase 87 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

**Audit type:** Declared-mitigation verification (FORCE stance — each mitigation proven by grep/code match, not by documentation/intent).
**ASVS level:** 1 (default — unset in config)
**block_on:** high, critical (default — unset in config)
**Register origin:** Authored at plan time (all 7 PLAN files carry a `<threat_model>` block). This audit VERIFIES declared dispositions only; it does not scan for new threats.

**Result:** SECURED — 48/48 threats closed. `threats_open: 0`. The lone open finding from the initial audit (T-87-01-04) was closed by adding the promised fixture-MANIFEST hash-parity test.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Operator → harvest script | Throwaway script reads Phase 76 dev cookies; one-shot ingress | Dev cookies (0o600, never committed) |
| gbs.fm → fixture files | Operator-controlled HTML/JSON/PNG bytes land on disk | Untrusted marquee/logo bytes |
| Repo → committed fixtures | Source-controlled bytes; downstream plans treat as canonical | Marquee text + logo PNGs (hash-pinned in MANIFEST) |
| Harvested bytes → parser | Operator-controlled text passes through `parse_marquee` | Untrusted marquee string |
| Parser → banner widget | Rendered as `Qt.TextFormat.PlainText` (T-40-04) — HTML/JS defused at UI | Plain str |
| Worker thread → main thread | Typed Signals (`marquee_ready`, `themed_logo_ready`) via Qt.QueuedConnection | str / raw bytes |
| Worker → gbs.fm | urllib over HTTPS; cookies flow outbound only | Session cookies (gbs.fm path only) |
| Resolved off-host URL → `_fetch_logo_bytes` | Themed-logo URL may point at third-party hosts; bytes fetched anonymously | Untrusted PNG bytes (no cookies) |
| Off-host PNG bytes → `QPixmap.loadFromData` (main thread) | Untrusted PNG parsed by Qt decoder on GUI thread | Image bytes; decode failure → canonical logo retained |

---

## Threat Register

### Closed (mitigate — mitigation present in code/tests)

| Threat ID | Category | Component | Mitigation / Evidence | Status |
|-----------|----------|-----------|-----------------------|--------|
| T-87-01-01 | InfoDisclosure | dev cookies file | No cookie/credential files committed (`git ls-files`); harvest is operator-side throwaway, reads only | closed |
| T-87-01-04 | Repudiation | MANIFEST SHA-256 parity | `test_fixture_manifest_sha256_parity` re-hashes every MANIFEST-declared fixture in BOTH manifests (`gbs_marquee` + `gbs_themed_logos`) and asserts parity; vacuous-pass floor of 11 entries (`tests/test_gbs_marquee.py`) | closed |
| T-87-01-05 | Spoofing | stale dev cookies | D-11 anonymous fallback (`gbs_marquee.py:338,345-354`); MANIFEST `capture_method` records `anonymous` (`MANIFEST.md:13`) | closed |
| T-87-02-01 | Tampering | marquee body injection | `parse_marquee` verbatim (`gbs_marquee.py:279-312`); rendered PlainText (T-87-05-01) | closed |
| T-87-02-03 | InfoDisclosure | marquee body in logs | D-18 structured logs, no body; `test_quiet_failure_logs_warn_no_toast` asserts `first_segment`/`full_text`/`raw_text` absent (`tests/test_gbs_marquee.py:267-269`; `gbs_marquee.py:359-363`) | closed |
| T-87-02-04 | Repudiation | synthetic vs real fixtures | `synthetic-` prefix + `provenance=synthetic` (`MANIFEST.md:55-67`; `synthetic-00{1..8}.txt`) | closed |
| T-87-03-01 | Tampering | Worker.exec_() omitted | `test_cadence_state_machine` asserts `current_interval_ms()` reflects `set_cadence` via QueuedConnection (`tests/test_gbs_marquee.py:153-185`) | closed |
| T-87-03-02 | InfoDisclosure | marquee body to disk | Log-leak grep test (`tests/test_gbs_marquee.py:265-269`); WARN logs carry event name + exception class only (`gbs_marquee.py:359-363`) | closed |
| T-87-03-05 | Tampering | auth-expired swallowed | `GbsAuthExpiredError` → `gbs.marquee.auth_expired` on buffer_log (`gbs_marquee.py:355-357`; `buffer_log.py:71-102`) | closed |
| T-87-03-06 | DoS | worker thread crash | Top-level try/except in `_fetch_marquee` (`gbs_marquee.py:365-371`) and `_on_tick` (`:612-621`); `finally` reschedules | closed |
| T-87-03-07 | Tampering | QtWebEngineProfile creep | Drift-guard bans `QWebEngineProfile`/`oauth_helper`/`GBS_WEB_PROFILE_NAME` (`tests/test_gbs_marquee_drift_guard.py:88-100`) | closed |
| T-87-04-01 | Tampering | malicious PNG crashes decoder | `QPixmap.loadFromData` failure → canonical kept (`now_playing_panel.py:1159-1162`); decode on GUI thread (CR-01) | closed |
| T-87-04-02 | InfoDisclosure | unknown_theme log leak | Logs hash only (`gbs_marquee.py:567-570`); drift-guard greps field names (`tests/test_gbs_marquee.py:267-269`) | closed |
| T-87-04-05 | DoS | busy loop on crash | `try/finally` flips `_themed_day_detected_this_session` (`gbs_marquee.py:546-574`); once-per-session test (`tests/test_gbs_marquee.py:481-484`) | closed |
| T-87-04-06 | Tampering | themed logo persisted | `test_themed_logo_never_persists` bans `.save(`, `open(`, `set_setting` (`tests/test_gbs_marquee_drift_guard.py:103-134`) | closed |
| T-87-04-07 | Tampering | writes to cover_label | Drift-guard bans `cover_label` (`tests/test_gbs_marquee_drift_guard.py:137-156`); behavioral test asserts cover_label unchanged (`tests/test_gbs_marquee.py:556-568`); slot touches `logo_label` only (`now_playing_panel.py:1176`) | closed |
| T-87-05-01 | Tampering | `<script>` in marquee | `setTextFormat(Qt.TextFormat.PlainText)` (`announcement_banner.py:67`); `test_banner_uses_plaintext_format` (`tests/test_announcement_banner.py:118`) | closed |
| T-87-05-06 | Tampering | banner becomes RichText | RichText baseline count == 3 pinned (`tests/test_constants_drift.py:95-106`) | closed |
| T-87-05-07 | Spoofing | non-gbs.fm content | `MARQUEE_URL` pinned to gbs.fm (`gbs_marquee.py:169`); `test_marquee_url_is_homepage` (`tests/test_gbs_marquee.py:122-128`); only worker emits `marquee_ready` (`:598`) | closed |
| T-87-06-03 | Tampering | comment-strip helper bug | Two-axis guard: comment-stripper + required-imports on raw text (`tests/test_gbs_marquee_drift_guard.py:44-85`) | closed |
| T-87-06-04 | Repudiation | follow-up todo misfiled | Todo `todos/2026-05-25-gbs-theme-hash-baseline-grow.md` referenced in code (`gbs_marquee.py:57,72`); STATE.md double-bookkeeping | closed |
| T-87-07-01 | Tampering | off-host PNG crashes decoder | `themed_logo_ready` emits raw bytes (`gbs_marquee.py:468,563`); decode on main thread (`now_playing_panel.py:1158-1162`); `test_set_themed_logo_override_accepts_bytes` (`tests/test_gbs_marquee.py:728-756`) | closed |
| T-87-07-04 | DoS | pathological URL stalls worker | `_TIMEOUT_READ` on fetch (`gbs_marquee.py:416`); quiet failure (`:418-431`); gate flips in `finally` (`:571-574`) | closed |
| T-87-07-05 | Tampering | regex over-matches rule | Resolver anchors on `#leftmenulogo` (`gbs_marquee.py:243-246`); `test_extract_leftmenulogo_url_selects_correct_rule` (`tests/test_gbs_marquee.py:614-628`) | closed |
| T-87-07-06 | InfoDisclosure | URL/body leaked into log | Logs only URL (public) + SHA-256 hash (`gbs_marquee.py:551,567-570,418-431`); drift-greps green | closed |

**Bonus mitigation (not in register):** WR-02 scheme guard — `_fetch_logo_bytes` rejects non-http(s) schemes (`file://`, `ftp://`) before urlopen (`gbs_marquee.py:406-412`); `test_fetch_logo_bytes_rejects_non_http_scheme` (`tests/test_gbs_marquee.py:861-880`). Closes a local-file-read surface on the off-host fetch.

### Closed (accept / n/a — rationale coherent, code consistent)

| Threat ID | Category | Disposition | Note | Status |
|-----------|----------|-------------|------|--------|
| T-87-01-02 | InfoDisclosure | accept | PII in captured ajax JSON — operator eyeball-and-redact + MANIFEST `notes`; procedural control | closed |
| T-87-01-03 | Tampering | accept | D-12 unknown_theme fallback present (`gbs_marquee.py:151,564`) | closed |
| T-87-02-02 | DoS | accept | urllib timeouts (`gbs_marquee.py:342,353`); parse O(n) | closed |
| T-87-03-03 | DoS | accept | No backoff by design (D-19); 60s/5min cadence (`now_playing_panel.py:1215-1218`) | closed |
| T-87-03-04 | Spoofing | accept | Marquee is public read-only; cookies do not change content | closed |
| T-87-04-03 | Tampering | accept | SHA-256 collision infeasible | closed |
| T-87-04-04 | Spoofing | accept | D-12 one-session anomaly, no data loss | closed |
| T-87-04-08 | Repudiation | accept | Acceptable noise per CONTEXT | closed |
| T-87-05-02 | Tampering | accept | QLabel wordWrap (`announcement_banner.py:68`); UTF-8 errors=replace (`gbs_marquee.py:344,354`) | closed |
| T-87-05-03 | InfoDisclosure | accept | Public read-only content | closed |
| T-87-05-04 | Repudiation | accept | SHA-256 dismissal-hash collision infeasible | closed |
| T-87-05-05 | DoS | accept | 60s cadence ceiling | closed |
| T-87-06-01 | Tampering | accept | Aliased-import bypass acknowledged unlikely | closed |
| T-87-06-02 | Tampering | accept | Banned patterns cover common surfaces | closed |
| T-87-06-05 | DoS | accept | Hard gate by design | closed |
| T-87-07-02 | Spoofing | accept | URL operator-chosen by design; anonymous fetch, no cookies; bytes decoded as image only (reinforced by WR-02) | closed |
| T-87-07-03 | InfoDisclosure | accept | Off-host fetch leaks IP same as loading gbs.fm in a browser; no credentials | closed |
| T-87-*-SC (×7) | — | n/a | Slopcheck self-check sentinels; zero new packages introduced; no code surface | closed |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-87-01 | T-87-01-02 | PII in captured ajax JSON mitigated by operator eyeball-and-redact process before commit + MANIFEST `notes` column. Procedural control — no in-repo automated guard possible for harvest-time redaction. | Kyle Creasey | 2026-06-15 |

*All other `accept`-disposition threats are documented in the register above with coherent rationale verified against code; they do not resurface in future audits. T-87-01-04 was NOT accepted — it was closed by adding the parity test.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-15 | 48 | 47 | 1 | gsd-security-auditor (initial — T-87-01-04 open) |
| 2026-06-15 | 48 | 48 | 0 | gsd:secure-phase (T-87-01-04 closed by `test_fixture_manifest_sha256_parity`) |

---

## Reproduction (audit-time evidence)

- Memorial Day logo: committed-file sha256 == code baseline (`gbs_marquee.py:76`) == MANIFEST (`gbs_themed_logos/MANIFEST.md:23`) == `bd2b83fb...881be3`. MATCH.
- All 11 MANIFEST-declared fixtures now machine-verified each run via `test_fixture_manifest_sha256_parity` (passing).
- No credential/cookie files tracked by git.
- Implementation files were NOT modified by this audit (only `tests/test_gbs_marquee.py` gained the parity guard).

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-15
