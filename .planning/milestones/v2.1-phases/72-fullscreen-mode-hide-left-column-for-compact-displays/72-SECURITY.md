# Phase 72 — Security Audit (SECURED)

**Phase:** 72 — fullscreen-mode-hide-left-column-for-compact-displays
**ASVS Level:** not_specified (UI-state-only phase; no I/O, auth, network, file, or IPC surface introduced)
**Audit date:** 2026-05-13
**Auditor mode:** verify-mitigations (register_authored_at_plan_time = true)
**Block-on:** not_specified
**Outcome:** SECURED — 7/7 threats CLOSED (5 mitigate, 2 accept). Zero open threats. Zero unregistered flags.

---

## Threat Register Verification

| ID | Category | Disposition | Status | Evidence |
|----|----------|-------------|--------|----------|
| T-72-01 | n/a | accept | CLOSED-by-disposition | Wave 0 spike tests are offscreen pytest-qt assertions only; no new I/O introduced. Confirmed by `tests/test_phase72_assumptions.py` (2 tests, both PASS) and SUMMARY 72-01 §Threat Flags = None. |
| T-72-02 | n/a | accept | CLOSED-by-disposition | `compact_mode_toggled = Signal(bool)` at `musicstreamer/ui_qt/now_playing_panel.py:272`; payload is bool only. Tooltip strings are plain text. SVG assets are project-local under `musicstreamer/ui_qt/icons/`. SUMMARY 72-02 §Threat Flags = None. |
| T-72-03 | Tampering | mitigate | CLOSED | See evidence block below. |
| T-72-04 | n/a (V5 degenerate) | accept | CLOSED-by-disposition | Slot signature `_on_compact_toggle(self, checked: bool)` at `musicstreamer/ui_qt/main_window.py` ~line 820. Payload type is `bool`; no string/path/SQL surface. |
| T-72-05 | DoS | mitigate | CLOSED | See evidence block below. |
| T-72-06 | Tampering | mitigate | CLOSED | See evidence block below. |
| T-72-07 | n/a | accept | CLOSED-by-disposition | UAT script `72-UAT-SCRIPT.md` (5 items, Wayland-only, `**Overall:** PENDING` gate). Manual UAT introduces no code or I/O. |

---

## Mitigate Threat Evidence

### T-72-03 — Modal-dialog Ctrl+B shortcut leak (Tampering)

**Mitigation plan:** Window-scope `Qt.WidgetWithChildrenShortcut` context so modal QDialogs block the shortcut.

**Evidence in implementation:**
- `musicstreamer/ui_qt/main_window.py:498-503` — QShortcut registered with `context=Qt.WidgetWithChildrenShortcut`:
  ```
  self._compact_shortcut = QShortcut(
      QKeySequence("Ctrl+B"),
      self,
      context=Qt.WidgetWithChildrenShortcut,
  )
  self._compact_shortcut.activated.connect(self._on_compact_shortcut_activated)
  ```

**Evidence in tests:**
- `tests/test_phase72_compact_toggle.py:255-266` — `test_modal_dialog_blocks_ctrl_b` asserts `window._compact_shortcut.context() == Qt.WidgetWithChildrenShortcut` (offscreen-safe fallback per plan body's allowed methodology).

**Strengthening — code-review WR-01 fix (post-`/gsd-code-review --fix --all`):**
The modal lock now extends beyond the Ctrl+B shortcut to the hover-peek MouseMove path. `main_window.py:1083-1097` adds a `QApplication.activeModalWidget()` guard inside the global eventFilter so a cursor bump near the left edge while a dialog is open will NOT silently open a peek behind the modal (which would be invisible and undismissible per D-14). This guard is the broader mitigation the original threat row prescribed and goes beyond the declared plan.

---

### T-72-05 — Event-filter starvation (DoS)

**Mitigation plan:** Filter MUST `return False` / call super to NOT consume MouseMove; keeps stock Qt mouse handling intact for the peeked panel's clicks and scrolls.

**Evidence in implementation:**
- `musicstreamer/ui_qt/main_window.py:1063-1139` — `MainWindow.eventFilter(self, obj, event)`. Every code path returns `super().eventFilter(obj, event)`; the filter never consumes the event. Confirmed at lines 1082, 1097, 1099, 1116, 1139 (every exit point). Docstring at line 1078-1079 explicitly cites T-72-05 mitigation.
- `musicstreamer/ui_qt/station_list_peek_overlay.py:145-162` — overlay's `eventFilter` also returns `super().eventFilter(obj, event)` (line 162) and only triggers `_close_peek_overlay()` as a side-effect on Leave, never consuming the event.

**Evidence in tests:**
- `tests/test_phase72_peek_overlay.py:302-313` — `test_click_station_keeps_overlay_open` (the threat-register-cited `test_clicking_station_in_peek_does_not_dismiss` was renamed by behavior preservation — same semantic check that clicking a station does not dismiss the peek).
- `tests/test_phase72_peek_overlay.py:316-325` — `test_peek_station_click_activates_playback` proves the click reaches `station_activated` and drives the player; the filter does not eat the click.

**Rename note:** The threat register names `test_clicking_station_in_peek_does_not_dismiss`. The actual implementation ships the equivalent test as `test_click_station_keeps_overlay_open`. The D-14 contract — clicking a station inside the peek does NOT dismiss the overlay — is verified by both the new test name and `test_peek_station_click_activates_playback`.

---

### T-72-06 — StationListPanel reparent corruption (Tampering)

**Mitigation plan:** Wave 0 spike validated round-trip preserves state (A2). Pitfall 6 lock uses `insertWidget(0, panel)` so visual order is preserved.

**Evidence in implementation:**
- `musicstreamer/ui_qt/station_list_peek_overlay.py:141` — `splitter.insertWidget(0, station_panel)` on the release path (NOT `addWidget`, which would swap visual order). Docstring at lines 126-138 cites Pitfall 6 and Wave 0 spike 72-01.

**Evidence in tests:**
- `tests/test_phase72_assumptions.py:156` — `test_station_panel_reparent_round_trip_preserves_state` (Wave 0 spike) locks A2 — `_search_box` state survives both legs of the round trip; `splitter.widget(0) is panel` asserted after `insertWidget(0, …)`.
- `tests/test_phase72_peek_overlay.py:379-391` — `test_station_panel_returns_to_splitter_index_0` asserts `window._splitter.indexOf(window.station_panel) == 0` after a peek open/close cycle in production code paths.

---

## Strengthening: closeEvent teardown (BL-01 fix)

Post-`/gsd-code-review --fix --all` added a hover-peek teardown block to `MainWindow.closeEvent`. This is not a declared threat row, but it closes a latent crash window: a MouseMove queued by Qt between `closeEvent` entry and `super().closeEvent()` could otherwise dispatch through a filter installed on a partially-destroyed MainWindow. Evidence:
- `musicstreamer/ui_qt/main_window.py:676-692` — release-overlay-first, then remove hover filter, BEFORE `super().closeEvent(event)` at line 709. Each step is wrapped in `try`/`except` so a peek-teardown failure cannot abort the rest of the shutdown sequence.

This strengthens (does not duplicate) T-72-05 mitigation by closing the use-after-free analogue at shutdown.

---

## Unregistered Flags

None. Every Plan SUMMARY's `## Threat Flags` section reports "None" with explicit mapping back to the threat register row authored at plan time:

| SUMMARY | Line | Reported flags | Mapping |
|---------|------|----------------|---------|
| 72-01-SUMMARY.md | 215 | None | Mirrors T-72-01 accept |
| 72-02-SUMMARY.md | 213 | None | Mirrors T-72-02 accept |
| 72-03-SUMMARY.md | 202 | T-72-03 mitigated; T-72-04 accepted | Direct mapping to register rows |
| 72-04-SUMMARY.md | 203 | T-72-05 mitigated; T-72-06 mitigated | Direct mapping to register rows |
| 72-05-SUMMARY.md | 253 | None | Mirrors T-72-07 accept |

No new attack surface appeared during implementation. The two post-plan strengthenings (BL-01 closeEvent teardown, WR-01 modal-aware mouse-event filter) reinforce existing register rows; they do not introduce new threats.

---

## Accepted Risks Log

No accepted risks beyond the declared `accept`-disposition rows in the plan-time threat register (T-72-01, T-72-02, T-72-04, T-72-07). All four cover degenerate or n/a STRIDE categories on a UI-state-only phase. No additional risks required deferral.

---

## ASVS Notes

ASVS level not specified. Per RESEARCH §Security Domain, V2-V6 do not apply to this phase (no auth, no session, no access control, no input-validation surface beyond the QKeySequence-bound `bool` Ctrl+B payload, no crypto). V5 (input validation) is degenerate per T-72-04.

The first QShortcut in the codebase (Ctrl+B, D-03 establishes the pattern) is correctly scoped at the window level via `Qt.WidgetWithChildrenShortcut` — future shortcut additions in the codebase should follow this precedent (modal-block-by-context).

---

## Audit Summary

- Implementation files: NOT modified (read-only audit).
- SECURITY.md: written at `.planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/SECURITY.md`.
- Threats open: 0.
- Phase 72 cleared for security from a declared-mitigation perspective; UAT human-verify gate (Plan 05 Task 3) is the only remaining checkpoint and is functional, not security-related.
