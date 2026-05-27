---
created: 2026-05-26T23:55:00.000Z
title: test_media_keys_smtc::test_end_to_end_factory_fallback_on_win32_without_winrt failing on Linux
area: tests
resolves_phase: TBD
files:
  - tests/test_media_keys_smtc.py::test_end_to_end_factory_fallback_on_win32_without_winrt
  - musicstreamer/media_keys/smtc.py (likely)
  - musicstreamer/media_keys/__init__.py (factory)
---

## Problem

`tests/test_media_keys_smtc.py::test_end_to_end_factory_fallback_on_win32_without_winrt` fails on Linux when the SMTC factory's fallback path is exercised without `winrt` installed. The test is presumably trying to simulate `sys.platform == "win32"` with no winrt available, and the assertion or stub setup is incorrect on the Linux dev host.

Surfaced during Phase 91 discuss-phase scout (2026-05-26).

## Solution (sketch)

1. Reproduce: `uv run pytest tests/test_media_keys_smtc.py::test_end_to_end_factory_fallback_on_win32_without_winrt -v --tb=long`.
2. Likely fixes:
   - Monkeypatch `sys.platform` with `pytest.MonkeyPatch.setattr` rather than via env or `unittest.mock.patch`, to survive the factory's import-time platform check.
   - Stub the `winrt` module via `sys.modules["winrt"] = None` (or an `ImportError`-raising sentinel) at the test boundary.
3. Add a `@pytest.mark.skipif(sys.platform != "linux", reason="Linux-only SMTC fallback test")` if the failure is intrinsic to running on Windows hosts.
4. Cross-check that the test still exercises the intended factory branch.

## Disposition

Capture for a test-baseline cleanup phase. SMTC is Windows-only at runtime; this is purely a test-design issue surfaced when running the suite on Linux.
