---
created: 2026-05-26T23:55:00.000Z
title: test_constants_drift::test_soma_nn_requirements_registered failing
area: tests
resolves_phase: TBD
files:
  - tests/test_constants_drift.py::test_soma_nn_requirements_registered
  - .planning/REQUIREMENTS.md (SOMA-NN-* rows likely)
---

## Problem

Surfaced during Phase 91 discuss-phase scout (2026-05-26). On commit `d2efdae`, `tests/test_constants_drift.py::test_soma_nn_requirements_registered` fails. The constants-drift guard family asserts that requirement IDs in source / docs match what's registered in `REQUIREMENTS.md`. A drift means either:

- A SOMA-NN-* requirement ID was introduced in code/docs but not added to `REQUIREMENTS.md`.
- A SOMA-NN-* row was added to `REQUIREMENTS.md` but never referenced in code/docs (false claim).

Likely tied to Phase 83 SomaFM next-now work or the conditional Phase 90/90b SomaFM preroll work.

## Solution (sketch)

1. Run `uv run pytest tests/test_constants_drift.py::test_soma_nn_requirements_registered -v --tb=long` to see which IDs drifted.
2. Cross-check the drift list against the most recent SomaFM-related phase (Phase 83 or Phase 90 area).
3. Either register the missing IDs in `REQUIREMENTS.md` (if code/docs introduced them) or remove the unused rows (if the IDs were renamed/dropped).
4. Re-run the drift-guard until green.

## Disposition

Capture for a constants-cleanup phase or fold into the next SomaFM phase. Not blocking; the failure is a documentation-coherence guard, not a runtime regression.
