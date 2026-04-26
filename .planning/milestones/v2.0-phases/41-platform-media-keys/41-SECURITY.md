# Phase 41 Security Audit — Platform Media Keys (MPRIS2)

**Audited:** 2026-04-15
**ASVS Level:** L1
**block_on:** critical

---

## Threat Verification Summary

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-41-01 | Denial-of-Service | mitigate | CLOSED | `media_keys/__init__.py` lines 38-43, 46-51, 53-54: all three dispatch branches wrapped in try/except Exception → NoOpMediaKeysBackend; Tests 5-7 in test_media_keys_scaffold.py |
| T-41-02 | Tampering | mitigate | CLOSED | `media_keys/smtc.py`: no `import winrt` / `from winrt` at module scope (only comments); test_media_keys_scaffold.py Test 9 asserts no winrt key in sys.modules |
| T-41-03 | Information Disclosure | accept | CLOSED | See accepted risks log below |
| T-41-04 | Tampering | accept | CLOSED | See accepted risks log below |
| T-41-05 | Information Disclosure | accept | CLOSED | See accepted risks log below |
| T-41-06 | Injection (rich-text/markup) | mitigate | OPEN | Structural mitigation present: xesam:title is a plain string passed verbatim to MPRIS dict (_build_metadata_dict in mpris2.py line 317). No HTML-escape applied. However, the declared verification artifact — a unit test asserting `"<script>alert(1)</script>"` passes through exactly — is absent from test_media_keys_mpris2.py. |
| T-41-07 | Information Disclosure | accept | CLOSED | See accepted risks log below |
| T-41-08 | Denial-of-Service | mitigate | CLOSED | `_art_cache.py` lines 36-38: stable per-station path, overwrite in place (D-04). No tmp-file churn. Pathological ICY streams bounded to single-file writes. Caller-side dedup guard (last station.id + pixmap identity) was described as optional in the plan and is absent, but the core D-04 structural mitigation is present. |
| T-41-09 | Path Traversal | mitigate | OPEN | Structural mitigation present: `write_cover_png(pixmap, station_id: int)` in `_art_cache.py` line 41 — station_id is typed int (SQLite primary key, not user text); f-string `f"{station_id}.png"` produces safe filenames. However, the declared verification artifact — a unit test confirming non-int station_id fails explicitly — is absent from test_media_keys_mpris2.py. |
| T-41-10 | Service name squatting | accept | CLOSED | See accepted risks log below |
| T-41-11 | Denial-of-Service | accept | CLOSED | See accepted risks log below |
| T-41-12 | Tampering | accept | CLOSED | See accepted risks log below |
| T-41-13 | Race Condition | mitigate | CLOSED | `main_window.py` lines 212-218: closeEvent calls `self._media_keys.shutdown()` before `super().closeEvent(event)`. Shutdown wrapped in try/except. test_media_keys_mpris2.py Test 12 confirms idempotency. |
| T-41-14 | Information Disclosure | accept | CLOSED | See accepted risks log below |

**Closed:** 12/14 | **Open:** 2/14

---

## Open Threats

### T-41-06 — Injection (rich-text/markup) — OPEN (missing test artifact)

- **Mitigation expected:** Unit test in test_media_keys_mpris2.py passing `"<script>alert(1)</script>"` as xesam:title and asserting the metadata dict contains that exact string (no escaping, no stripping).
- **Files searched:** `tests/test_media_keys_mpris2.py`, `tests/test_media_keys_scaffold.py`
- **Structural mitigation present:** `_build_metadata_dict()` in `mpris2.py` assigns `self._title or self._station.name` directly to `xesam:title` with no modification. MPRIS consumers render as plain text.
- **Gap:** The declared verification test is absent. The structural mitigation is sound for L1, but the test contract is unmet per the plan.
- **Severity:** Low (MPRIS plain-text rendering, L1 scope). Not critical per `block_on: critical`.

### T-41-09 — Path Traversal — OPEN (missing test artifact)

- **Mitigation expected:** Unit test confirming `write_cover_png` rejects non-int station_id (raises TypeError or similar).
- **Files searched:** `tests/test_media_keys_mpris2.py`
- **Structural mitigation present:** `cover_path_for_station(station_id: int)` and `write_cover_png(pixmap, station_id: int)` in `_art_cache.py` — station_id derives from `station.id`, an integer SQLite primary key. No user-controlled text enters the filename path.
- **Gap:** The declared verification test is absent. Python type hints are not enforced at runtime; a caller passing a string station_id would silently produce a different filename rather than failing. No current call sites do this.
- **Severity:** Low (all call sites use integer PKs). Not critical per `block_on: critical`.

---

## Accepted Risks Log

| Threat ID | Category | Rationale |
|-----------|----------|-----------|
| T-41-03 | Information Disclosure | Warning log on create() fallback contains only the exception message — no station data, no user identifiers. Low-value target. |
| T-41-04 | Tampering | Any local session-bus client can trigger PlayPause/Stop/Next/Previous. Worst outcome: stream toggle. No data exfiltration, no privilege escalation. Single-user desktop app threat model. |
| T-41-05 | Information Disclosure | Station name + ICY title already visible in app UI; publishing them to the session bus exposes nothing beyond what any process with X/Wayland session access can already see. artUrl is in user cache — same trust zone as the app SQLite db. |
| T-41-07 | Information Disclosure | Introspectable XML matches the public MPRIS2 spec. No proprietary method names, no internal data structures exposed. |
| T-41-10 | Service name squatting | Second-instance registerService fails; factory raises; Plan 01 create() returns NoOpMediaKeysBackend (D-06). User-visible effect: second instance has no media keys. Out of scope per 41-CONTEXT.md. |
| T-41-11 | Denial-of-Service | ICY title_changed emissions rare (2-5 min typical). Cover-art write to stable per-station path (D-04). No debouncing needed. |
| T-41-12 | Tampering | _on_media_key_stop callable by any session-bus client. Single-user desktop. Worst outcome is stream stopping — user can resume. |
| T-41-14 | Information Disclosure | Cover-art PNG in user cache dir (same trust zone as app SQLite db). Not a credential or secret. File permissions follow user umask. |

---

## Unregistered Flags

None — no `## Threat Flags` sections present in 41-01-SUMMARY.md, 41-02-SUMMARY.md, or 41-03-SUMMARY.md.

---

## Remediation Guidance

Both open threats are non-critical (structural mitigations are in place; only the declared test artifacts are absent). To close them:

**T-41-06:** Add to `tests/test_media_keys_mpris2.py` (requires session bus):
```python
@skip_if_no_bus
def test_xesam_title_passthrough_verbatim(tmp_path, monkeypatch, qapp):
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.media_keys.mpris2 import LinuxMprisBackend
    station = _make_station()
    backend = LinuxMprisBackend(None, None)
    try:
        backend.publish_metadata(station, "<script>alert(1)</script>", None)
        meta = backend._build_metadata_dict()
        assert meta["xesam:title"] == "<script>alert(1)</script>"
    finally:
        backend.shutdown()
```

**T-41-09:** Add to `tests/test_media_keys_mpris2.py`:
```python
def test_write_cover_png_rejects_non_int_station_id(tmp_path, monkeypatch, qapp):
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.media_keys._art_cache import write_cover_png
    px = _red_pixmap()
    with pytest.raises((TypeError, ValueError)):
        write_cover_png(px, "../evil")
```
Note: Python type hints are advisory. To enforce at runtime, add `if not isinstance(station_id, int): raise TypeError(...)` to `cover_path_for_station`.
