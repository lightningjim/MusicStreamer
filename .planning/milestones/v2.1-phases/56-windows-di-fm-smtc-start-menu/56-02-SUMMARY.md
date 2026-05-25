---
phase: 56-windows-di-fm-smtc-start-menu
plan: 02
subsystem: player

tags: [player, set-uri, di-fm, https-rewrite, integration-test, win-01]

requires:
  - phase: 56-windows-di-fm-smtc-start-menu/56-01
    provides: aa_normalize_stream_url(url) helper at musicstreamer/url_helpers.py:140 (D-04 — pure free function, idempotent, slug-gated via _aa_slug_from_url(url) == "di")
  - phase: 35-qt-port
    provides: Player class with _set_uri URI funnel at musicstreamer/player.py:484 (single insertion point per D-01)
provides:
  - "musicstreamer/player.py::_set_uri now prepends aa_normalize_stream_url(uri) before pipeline.set_property — every URI handed to playbin3 is normalized at the funnel"
  - "3 player-level integration tests in tests/test_player_failover.py exercising the REAL _set_uri body (Pitfall #1 — no patch.object) and asserting on _pipeline.set_property MagicMock capture"
  - "WIN-01 wire-in is COMPLETE on Linux CI surface — Win11 VM UAT (D-12) is the remaining gate"
affects:
  - "All 4 _set_uri call sites inherit normalization without per-call-site changes: play() line 480 (direct streams), _on_youtube_resolved line 591 (post-yt-dlp), _on_twitch_resolved line 669 (post-streamlink), _try_next_stream line 480 (failover)"
  - "Existing 14+ tests in test_player_failover.py that mock _set_uri continue to pass — mock placement intercepts BEFORE normalization (T-56-Test-A confirmed)"
  - "Phase 56 Plan 03+ (SMTC diagnose / drift guard / UAT) — orthogonal, unblocked"

tech-stack:
  added: []
  patterns:
    - "Single funnel for cross-cutting URL transform: one-line helper call at the URI boundary (_set_uri), not at every upstream caller (D-01 — matches Phase 47-01 stream-ordering precedent)"
    - "Mock-inversion safety: integration tests for funnel-level transforms must NOT mock the funnel itself — they must exercise the real method body and assert on the OUTPUT side of the mock (here: _pipeline.set_property MagicMock via assert_any_call)"
    - "T-56-01 mitigation via passthrough lock: a YouTube-HLS test specifically asserts NON-DI.fm HTTPS reaches playbin3 unchanged — broadening the predicate would fail this test immediately and prevent silent TLS-strip on arbitrary streams"

key-files:
  created: []
  modified:
    - musicstreamer/player.py
    - tests/test_player_failover.py

key-decisions:
  - "Wire-in placed at TOP of _set_uri body (before pipeline.set_state(NULL)) per RESEARCH.md Example 2 and PATTERNS.md verbatim wire-in pattern"
  - "Import inserted alphabetically after 'from musicstreamer.stream_ordering import order_streams' per existing intra-package import convention (PATTERNS.md import-section pattern)"
  - "3 new tests use assert_any_call (not assert_called_once_with) because _set_uri triggers multiple MagicMock calls on _pipeline (set_state NULL/PLAYING, get_state, set_property) — only the URI-property call matters for the rewrite contract"
  - "Pitfall #1 enforced literally: grep gate confirmed 0 occurrences of patch.object(p, '_set_uri') inside any of the 3 new test bodies"
  - "T-56-01 mitigation test (YouTube HLS passthrough) selected over a SomaFM-only passthrough because YouTube HLS is the highest-stakes false-positive surface — playbin3 receiving an http://manifest.googlevideo.com/... URL would degrade to plaintext on a TLS-required CDN endpoint"
  - "Section divider placed AFTER existing Phase 47-02 + gap-closure block at end of file (matches existing convention at lines 53/101/186/222/238/334/383)"

requirements-completed: [WIN-01]

duration: 3min
completed: 2026-05-02
---

# Phase 56 Plan 02: DI.fm Player Wire-in Summary

**`aa_normalize_stream_url` is now wired into `Player._set_uri` as a single-funnel URI transform at the playbin3 boundary, with 3 player-level integration tests guarding the wire (Pitfall #1: tests assert on the underlying `_pipeline.set_property` MagicMock without mocking `_set_uri` itself).**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-02T18:11:33Z
- **Completed:** 2026-05-02T18:14:48Z
- **Tasks:** 2
- **Files modified:** 2

## Final `_set_uri` Body

```python
# musicstreamer/player.py:484-489
def _set_uri(self, uri: str) -> None:
    uri = aa_normalize_stream_url(uri)  # WIN-01 / D-01: DI.fm HTTPS->HTTP at URI funnel
    self._pipeline.set_state(Gst.State.NULL)
    self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
    self._pipeline.set_property("uri", uri)
    self._pipeline.set_state(Gst.State.PLAYING)
```

## Import Added

```python
# musicstreamer/player.py:48 (alphabetical, immediately after stream_ordering)
from musicstreamer.url_helpers import aa_normalize_stream_url
```

## New Tests (3)

All in `tests/test_player_failover.py` after the divider `# Phase 56 / WIN-01: _set_uri normalizes DI.fm HTTPS -> HTTP (D-01)`:

### `test_set_uri_normalizes_difm_https_to_http` — core rewrite

```python
def test_set_uri_normalizes_difm_https_to_http(qtbot):
    """WIN-01 / D-01: _set_uri rewrites DI.fm https:// to http:// before
    handing the URL to playbin3."""
    p = make_player(qtbot)
    p._set_uri("https://prem1.di.fm/lounge?listen_key=abc")
    p._pipeline.set_property.assert_any_call(
        "uri", "http://prem1.di.fm/lounge?listen_key=abc"
    )
```

### `test_set_uri_passes_through_non_difm` — D-06 idempotency at player layer

```python
def test_set_uri_passes_through_non_difm(qtbot):
    """D-06 idempotency at player layer: non-DI.fm URLs reach playbin3
    unchanged (no scheme rewrite)."""
    p = make_player(qtbot)
    p._set_uri("https://ice4.somafm.com/dronezone-256-mp3")
    p._pipeline.set_property.assert_any_call(
        "uri", "https://ice4.somafm.com/dronezone-256-mp3"
    )
```

### `test_set_uri_passes_through_youtube_hls` — T-56-01 mitigation

```python
def test_set_uri_passes_through_youtube_hls(qtbot):
    """T-56-01 mitigation: YouTube-resolved HLS manifests must NEVER be
    downgraded to http -- broadening the predicate would strip TLS from
    arbitrary streams (active-MITM exposure). Locks the predicate scope."""
    p = make_player(qtbot)
    url = "https://manifest.googlevideo.com/api/manifest/hls_playlist/abc/playlist.m3u8"
    p._set_uri(url)
    p._pipeline.set_property.assert_any_call("uri", url)
```

## Task Commits

Each task was committed atomically (sequential single-plan execution on main):

1. **Task 1: Wire aa_normalize_stream_url into player.py::_set_uri** — `e1077a8` (feat)
2. **Task 2: Add 3 player-level integration tests for _set_uri normalization** — `4354285` (test)

## Verification Gates — All Green

- `grep -c '^from musicstreamer.url_helpers import aa_normalize_stream_url$' musicstreamer/player.py` → **1**
- `grep -c 'uri = aa_normalize_stream_url(uri)' musicstreamer/player.py` → **1**
- `grep -c 'aa_normalize_stream_url' musicstreamer/player.py` → **2** (1 import + 1 call site, Pitfall #2 guard)
- `grep -c 'aa_normalize_stream_url' musicstreamer/aa_import.py` → **0** (D-04 single-source-of-truth)
- `grep -c 'patch.object(p, "_set_uri")'` inside each of the 3 new test bodies → **0** (Pitfall #1 mitigation)
- `uv run pytest tests/test_player_failover.py -x` → **23/23 passed** (20 pre-existing + 3 new)
- `uv run pytest tests/test_aa_url_detection.py tests/test_player_failover.py -x` (VALIDATION.md quick sample) → **59/59 passed in 0.67s**

## Files Modified

- **`musicstreamer/player.py`** — Added 1 import line at line 48 (`from musicstreamer.url_helpers import aa_normalize_stream_url`), prepended 1 line at the top of `_set_uri` body (`uri = aa_normalize_stream_url(uri)  # WIN-01 / D-01: DI.fm HTTPS->HTTP at URI funnel`). Total +2 lines, no deletions, no other edits.
- **`tests/test_player_failover.py`** — Appended 1 section-divider comment block + 3 new test functions at the end of the file (after the existing Phase 47-02 gap-closure block at line 442). Total +41 lines, no deletions.

## Decisions Made

- **Import grouping:** placed alphabetically AFTER `from musicstreamer.stream_ordering import order_streams` (alphabetical: `stream_ordering` < `url_helpers`) per PATTERNS.md import-section pattern. The intra-package import group already existed; no new section header was needed.
- **Wire-in placement:** at the TOP of `_set_uri` body, BEFORE the existing `pipeline.set_state(Gst.State.NULL)` line. This matches RESEARCH.md Example 2 verbatim and ensures the rewrite happens before the pipeline state machine begins its NULL→PLAYING transition (so the URI written into `set_property("uri", ...)` is the rewritten one, never the original).
- **Tests assert with `assert_any_call`, not `assert_called_once_with`:** `_set_uri` triggers multiple MagicMock calls on `_pipeline` (set_state NULL, get_state, set_property, set_state PLAYING) and `_pipeline.set_property` itself is called for `volume` elsewhere in `Player.__init__` setup chains. Only the `("uri", <rewritten>)` call is contract-relevant for these tests; `assert_any_call` is the correct selector. PLAN.md explicitly mandated this idiom.
- **T-56-01 mitigation chose YouTube HLS over generic non-DI.fm URL:** the YouTube HLS test (`test_set_uri_passes_through_youtube_hls`) is the strongest active-MITM regression guard because YouTube-resolved CDN manifests are a common downstream use of `_set_uri` (via `_on_youtube_resolved`) — a buggy predicate broadening to `_aa_slug_from_url(url) is not None` would incorrectly route those through the rewrite and strip TLS from a TLS-required CDN. SomaFM HTTPS-passthrough was kept as a second test for the AA-network-but-not-DI.fm case (D-06 idempotency anchor).

## Deviations from Plan

None — plan executed exactly as written. No deviation rules (1, 2, 3, or 4) triggered.

## Issues Encountered

- **Pre-existing full-suite failure unrelated to this plan:** `tests/test_media_keys_mpris2.py::test_linux_mpris_backend_constructs` fails with `RuntimeError: registerObject failed:` (musicstreamer/media_keys/mpris2.py:249). **Confirmed pre-existing** by reverting `musicstreamer/player.py`, `musicstreamer/url_helpers.py`, `tests/test_player_failover.py`, and `tests/test_aa_url_detection.py` to commit `5e3b710` (the commit immediately before Phase 56 work began) and re-running just that test — same `RuntimeError: registerObject failed:` occurs. This is an environment-level D-Bus session-bus issue completely orthogonal to URL helper / player wire-in work, and was already documented as a known issue in 56-01-SUMMARY.md "Issues Encountered". This plan's `<verification>` block targets `uv run pytest tests/test_aa_url_detection.py tests/test_player_failover.py -x` (the quick sample), and that quick sample is **59/59 green in 0.67s**. The full-suite failure falls outside this plan's scope per the executor SCOPE BOUNDARY rule (this plan touches `player.py` and `test_player_failover.py`; the failing test is in `media_keys/mpris2.py` and `test_media_keys_mpris2.py`).

## Deferred Issues

- **`test_linux_mpris_backend_constructs` MPRIS2 D-Bus test failure** — pre-existing on the dev machine, not caused by this plan. Same status as documented in 56-01-SUMMARY.md. Suggested follow-up: investigate session-bus availability on the dev environment OR add a skip-marker for environments lacking a usable session DBus. Out of scope for Phase 56 Plan 02.

## Threat Flags

None. The 3 new files / surface introduced (1 import line + 1 call line in `player.py`, 3 test functions in `test_player_failover.py`) match the threat surface enumerated in the plan's `<threat_model>`:

- **T-56-01 (Tampering — predicate broadening downgrades non-DI.fm HTTPS):** mitigated via `test_set_uri_passes_through_youtube_hls` (T-56-01 specifically locked) + `test_set_uri_passes_through_non_difm` (SomaFM passthrough). Plan 56-01's 8 unit tests already covered RadioTunes/JazzRadio at the helper layer.
- **T-56-Test-A (Repudiation — future tester copies patch.object pattern, normalization regression silently passes):** mitigated via the explicit section-divider comment that documents the inversion trap, AND the 3 new test bodies have 0 occurrences of `patch.object(p, "_set_uri")` (grep gate verified).
- **T-56-Wire-A (Tampering — future direct pipeline.set_property("uri", ...) bypass):** accepted per plan; `grep set_property.\"uri\"` in `player.py` confirms `_set_uri` remains the sole call site.
- **T-56-A (Information Disclosure — listen_key in test output):** test uses synthetic `?listen_key=abc`, no real key.

No new security-relevant surface introduced; no threat flags raised.

## Next Phase Readiness

- **Plan 56-03 (SMTC diagnose-then-fix / drift guard / UAT) ready to execute.** Plan 56-02 is fully orthogonal to the SMTC half (WIN-02) — no shared code paths, no shared test files. The DI.fm side of the phase is now Linux-CI-complete; the only remaining DI.fm-side gate is the Win11 VM UAT (D-12: DI.fm Lounge plays end-to-end from fresh AA import + from settings-import ZIP roundtrip), which is human-only and bracketed by the WIN-02 SMTC UAT in Plan 03.
- **WIN-01 implementation surface now complete** (helper + wire-in + unit tests + integration tests). Phase verifier can run the full quick sample (`uv run pytest tests/test_aa_url_detection.py tests/test_player_failover.py -x` — 59 tests in <1s) as the Linux-CI gate before signing off WIN-01 pending VM UAT.

## Self-Check: PASSED

- [x] `musicstreamer/player.py` exists and contains `from musicstreamer.url_helpers import aa_normalize_stream_url` (line 48) and `uri = aa_normalize_stream_url(uri)` (line 486) — verified via `grep -n`.
- [x] `tests/test_player_failover.py` exists and contains 3 new `def test_set_uri_*` functions at end of file — verified via `tail -50` and `grep -c`.
- [x] Commit `e1077a8` (feat — Task 1 wire-in) exists in `git log` — verified.
- [x] Commit `4354285` (test — Task 2 integration tests) exists in `git log` — verified.
- [x] `uv run pytest tests/test_player_failover.py -x` exits 0 with 23/23 passing.
- [x] `uv run pytest tests/test_aa_url_detection.py tests/test_player_failover.py -x` exits 0 with 59/59 passing in 0.67s.
- [x] None of the 3 new tests use `patch.object(p, "_set_uri")` (grep gate Pitfall #1 — verified per-test via `awk` range scan).

---
*Phase: 56-windows-di-fm-smtc-start-menu*
*Completed: 2026-05-02*
