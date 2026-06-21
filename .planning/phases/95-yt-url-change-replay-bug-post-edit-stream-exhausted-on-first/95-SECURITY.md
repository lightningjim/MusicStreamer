---
phase: 95
slug: yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
status: secured
threats_open: 0
threats_closed: 10
risks_accepted: 4
asvs_level: 1
created: 2026-06-20
---

# SECURITY.md — Phase 95: yt-url-change-replay-bug-post-edit-stream-exhausted-on-first

**Generated:** 2026-06-20
**ASVS Level:** 1
**Phase Plans Covered:** 95-01, 95-02, 95-03, 95-04
**Code Review Status:** clean (CR-01 closed, 95-REVIEW.md re-review 2026-06-20T19:29:23Z)

---

## Threat Verification Register

| Threat ID | Category | Disposition | Verification Evidence |
|-----------|----------|-------------|----------------------|
| T-95-01 (95-01) | Tampering / DoS | accept | Restart re-feeds an already-user-controlled URL through the existing `play()`→`_set_uri` path — no new input parsing. Accepted: no new external surface introduced. |
| T-95-02 (95-01) | Correctness | mitigate | `_youtube_resolve_seq` cross-thread int read/write: VERIFIED. Declared at `player.py:591` alongside `_preroll_seq`; CPython-atomic int rationale documented at `:584-591`. Worker→main hop uses the queued `youtube_resolved Signal(str, bool, int)` (`:273`). |
| T-95-SC (95-01) | Tampering/supply-chain | accept/n/a | No new npm/pip/cargo installs. VERIFIED: `player.py` imports unchanged vs pre-phase; no requirements file diff. |
| T-95-03 (95-02) | Correctness | mitigate | `_recovery_seq` cross-thread int read/write: VERIFIED. Declared at `player.py:604`; bus-thread reads the int atomically at `_on_gst_error:1049` and carries it on `_error_recovery_requested = Signal(int)` (`:286`). Main-thread slot compares at run time. |
| T-95-04 (95-02) | DoS (self) | mitigate | Over-suppression of genuine exhaustion by the `-1` sentinel: VERIFIED. `_handle_gst_error_recovery` guard at `:1071` — `if recovery_seq != -1 and recovery_seq != self._recovery_seq: return`. Only explicitly-stamped stale deliveries are rejected; the `-1` default and current-generation deliveries both fall through to `_try_next_stream`. |
| T-95-SC (95-02) | Tampering/supply-chain | accept/n/a | No new dependencies. VERIFIED: same evidence as T-95-SC (95-01). |
| T-95-01 (95-03 — stuck gate DoS) | DoS | mitigate | `_youtube_resolve_in_flight` never cleared: VERIFIED. Gate cleared in `_on_youtube_resolved` (`:2099`) AFTER seq guard, in `_on_youtube_resolution_failed` (`:2135`) AFTER carried-seq guard, in `_set_uri` (`:1614`), and in `stop()` (`:935`). Five clear sites total (init default + four runtime sites). |
| T-95-02 (95-03 — stale failure clears fresh gate) | Tampering | mitigate | Stale `_on_youtube_resolution_failed` delivery clears a fresh gate: VERIFIED. `_on_youtube_resolution_failed(self, msg, seq=-1)` at `:2104` carries per-worker seq on `Signal(str, int)` (`:274`); staleness guard at `:2131` — `if seq != -1 and seq != self._youtube_resolve_seq: return`. Stale delivery early-returns without clearing gate or calling `_try_next_stream`. |
| T-95-03 (95-03 — genuine exhaustion over-suppressed) | Tampering | mitigate | Gate over-suppresses genuine exhaustion: VERIFIED. Gate consulted at `_try_next_stream:1553` ONLY on empty queue; genuine exhaustion (gate=False, empty queue) reaches `failover.emit(None)` at `:1556`. Pinned by V15 (gate=False + empty queue → toast). |
| T-95-SC (95-03) | Tampering/supply-chain | accept | No new dependencies; pure edit to `player.py` + test files. |
| T-95-04-01 (95-04 — gate stranded, CR-01 leak) | DoS | mitigate | `_youtube_resolve_in_flight` stranded True after YouTube→direct restart: VERIFIED. `_set_uri` clears gate at `:1614`; stale failure rejected via carried seq (`_on_youtube_resolution_failed:2131`). Regression-locked by V17. |
| T-95-04-02 (95-04 — stale failure mis-classified) | Tampering | mitigate | Stale (old-generation) failure mis-classified as current — spurious `failover(None)`: VERIFIED. `youtube_resolution_failed = Signal(str, int)` at `:274`; all three worker failure emits carry `seq` (`:2063`, `:2072`, `:2077`); `play()` bumps `_youtube_resolve_seq` at `:731` so every restart invalidates in-flight resolves; `stop()` bumps at `:936`. Regression-locked by V16d and V18. Dead instance attribute `_youtube_resolve_in_flight_seq` removed — no executable references remain (verified: `grep -v '^.*#' player.py \| grep _youtube_resolve_in_flight_seq` returns no matches). |
| T-95-04-03 (95-04 — over-suppression of genuine exhaustion) | Tampering | mitigate | Gate over-suppresses genuine exhaustion (regresses D-03 / V15): VERIFIED. Same mechanism as T-95-03 (95-03): gate=False + empty queue → `failover.emit(None)`. V15 and V17 genuine-exhaustion leg assert this path. |
| T-95-04-04 (95-04 — FakePlayer Signal arity drift) | Tampering | mitigate | `youtube_resolution_failed` arity drift between Player and FakePlayer: VERIFIED. `tests/_fake_player.py:65` — `youtube_resolution_failed = Signal(str, int)` mirrors `player.py:274`. `tests/test_fake_player_signal_parity.py` source-parses both files; parity guard GREEN (23 edit-invalidation tests + 2 parity tests passed). |
| T-95-04-SC (95-04) | Tampering/supply-chain | accept | No new dependencies. VERIFIED: same evidence as prior SC entries. |

---

## Accepted Risks Log

| Risk ID | Description | Accepted By | Rationale |
|---------|-------------|-------------|-----------|
| T-95-01 | Restart re-feeds a user-controlled URL through existing `play()`→`_set_uri`/yt-dlp path | 95-01 threat model | No new input surface: the URL was already user-controlled and traverses the identical code path as a first-play. yt-dlp resolution is sandboxed to a daemon worker with a try/except backstop. |
| T-95-SC (all plans) | npm/pip/cargo supply-chain | 95-01/02/03/04 threat models | Phase 95 modified only `musicstreamer/player.py`, `tests/_fake_player.py`, and `tests/test_player_edit_invalidation.py`. No package manager installs of any kind were performed. |

---

## Unregistered Threat Flags

None. The 95-04 SUMMARY.md Threat Surface Scan confirms no new network endpoints, auth paths, file access patterns, or schema changes. The two carried-forward code review items (WR-05 partial gate consult in `_try_next_stream`; IN-02 default-sentinel asymmetry between settle handlers) are maintainability/cosmetic notes, not security threats, and are documented in 95-REVIEW.md.

---

## Verification Summary

**Plans audited:** 4 (95-01, 95-02, 95-03, 95-04)
**Threats in consolidated register:** 14 unique threat entries
**Threats closed (mitigate verified in code):** 10
**Risks accepted (per plan threat models):** 4
**Threats open (mitigations absent):** 0
**Unregistered flags:** 0

**Key implementation checkpoints (grep-verified against shipped source):**

- `player.py:274` — `youtube_resolution_failed = Signal(str, int)` (95-04)
- `player.py:286` — `_error_recovery_requested = Signal(int)` (95-02)
- `player.py:591` — `self._youtube_resolve_seq: int = 0` (95-01)
- `player.py:604` — `self._recovery_seq: int = 0` (95-02)
- `player.py:615` — `self._youtube_resolve_in_flight: bool = False` (95-03)
- `player.py:723` — `self._recovery_seq += 1` in `play()` entry (95-02)
- `player.py:731` — `self._youtube_resolve_seq += 1` in `play()` entry (95-04)
- `player.py:935-936` — `_youtube_resolve_in_flight = False` + `_youtube_resolve_seq += 1` in `stop()` (95-04)
- `player.py:1049` — `self._error_recovery_requested.emit(self._recovery_seq)` (95-02)
- `player.py:1071` — recovery staleness guard `if recovery_seq != -1 and recovery_seq != self._recovery_seq: return` (95-02)
- `player.py:1090` — `if self._youtube_resolve_in_flight: return` in `_handle_gst_error_recovery` (95-03)
- `player.py:1553` — `if self._youtube_resolve_in_flight: return` in `_try_next_stream` empty-queue branch (95-03)
- `player.py:1614` — `self._youtube_resolve_in_flight = False` in `_set_uri` (95-04)
- `player.py:1989` — `self._youtube_resolve_in_flight = True` in `_play_youtube` (95-03)
- `player.py:2063,2072,2077` — all three worker failure emits carry `seq` (95-04)
- `player.py:2095` — `_on_youtube_resolved` seq guard (95-01)
- `player.py:2099` — gate clear in `_on_youtube_resolved` after seq guard (95-03)
- `player.py:2131` — `_on_youtube_resolution_failed` carried-seq guard (95-04)
- `player.py:2135` — gate clear in `_on_youtube_resolution_failed` before `_try_next_stream` (95-03/04)
- `player.py:2171` — `self._youtube_resolve_seq += 1` in `invalidate_for_edit` (95-01)
- No executable `self._youtube_resolve_in_flight_seq` references in `player.py` (95-04 removal verified)
- `tests/_fake_player.py:65` — `youtube_resolution_failed = Signal(str, int)` parity (95-04)
- `tests/_fake_player.py:79` — `_error_recovery_requested = Signal(int)` parity (95-02)
- `musicstreamer/ui_qt/main_window.py:1451-1453` — `self._player.invalidate_for_edit(updated_station, is_playing=self.now_playing.is_playing)` wiring (95-01)
