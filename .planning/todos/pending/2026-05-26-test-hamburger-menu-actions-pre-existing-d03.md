---
created: 2026-05-26T23:55:00.000Z
title: test_hamburger_menu_actions — pre-existing D-03 carry-over from Phase 74/76
area: tests
resolves_phase: TBD
files:
  - tests/test_main_window_integration.py::test_hamburger_menu_actions
  - musicstreamer/ui_qt/main_window.py (hamburger menu wiring)
---

## Problem

`tests/test_main_window_integration.py::test_hamburger_menu_actions` fails on the current `main` (`d2efdae`). Already documented in Phase 77-VERIFICATION.md "Deferred Items" row 2 as a Phase 74/76 menu-text carry-over — explicitly excluded from Phase 77 scope per Phase 77 CONTEXT D-03 ("pre-existing failures NOT in the six-cluster list stay deferred").

Surfaced again during Phase 91 discuss-phase scout (2026-05-26).

## Solution (sketch)

1. Inspect Phase 74 and Phase 76 SUMMARY/VERIFICATION docs for the menu-text rename that broke the assertion.
2. Either update the test assertion to match the renamed menu items (test follows impl — likely the right direction since the rename was deliberate UX work) or revert the rename (impl follows test — unlikely given Phase 74/76 intent).
3. Land in a future test-baseline cleanup phase.

## Disposition

Captured here so it shows up in `/gsd:list-todos` and a future cleanup phase can fold it. Cross-reference: Phase 77-VERIFICATION.md "Deferred Items" row 2.
