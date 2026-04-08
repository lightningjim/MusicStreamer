# Phase 25: Fix Filter Chip Overflow in Station Filter Section - Research

**Researched:** 2026-04-08
**Domain:** GTK4 layout — Gtk.FlowBox replacing Gtk.ScrolledWindow in main window filter bar
**Confidence:** HIGH

## Summary

This phase is a direct application of the Phase 24 FlowBox pattern to the main window filter bar. The change is mechanically identical: two `Gtk.ScrolledWindow` + `Gtk.Box` pairs are replaced with two `Gtk.FlowBox` instances using the same configuration that was proven in the edit dialog.

The existing code in `main_window.py` is well-structured and the rebuild methods (`_rebuild_provider_chips`, `_rebuild_tag_chips`) only need reference targets updated from `_provider_chip_box`/`_tag_chip_box` to `_provider_flow`/`_tag_flow`. No signal handler changes, no logic changes.

**Primary recommendation:** Copy the Phase 24 FlowBox configuration verbatim, rename the instance attributes to `_provider_flow` / `_tag_flow`, and update the two rebuild methods' clear/append targets.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use FlowBox wrapping (same pattern as phase 24 edit dialog fix). Replace both `ScrolledWindow` + horizontal `Gtk.Box` containers with `Gtk.FlowBox`. No max height constraint — chips wrap freely.
- **D-02:** Keep provider chips and tag chips in separate FlowBoxes. Maintains the current two-row visual grouping but with wrapping instead of horizontal scroll.

### Claude's Discretion
- **D-03:** Match the existing chip style (ToggleButtons) and spacing. Follow the phase 24 FlowBox configuration (8px column spacing, 4px row spacing, hexpand=False).

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

## Standard Stack

### Core (no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GTK4 | system | UI framework — `Gtk.FlowBox` | Project baseline; already imported |
| libadwaita | system | Adwaita theme tokens | Project baseline |

No new packages to install. `Gtk.FlowBox` is part of GTK4 core. [VERIFIED: codebase — edit_dialog.py uses it already]

---

## Architecture Patterns

### Existing Filter Bar Structure (confirmed from main_window.py:193–240)

```
filter_box (Gtk.Box, HORIZONTAL)
├── add_btn (Gtk.Button)
├── edit_btn (Gtk.Button)
├── chip_container (Gtk.Box, VERTICAL, hexpand=True)
│   ├── _provider_scroll (Gtk.ScrolledWindow)  ← REPLACE
│   │   └── _provider_chip_box (Gtk.Box, HORIZONTAL)  ← REPLACE
│   └── _tag_scroll (Gtk.ScrolledWindow)  ← REPLACE
│       └── _tag_chip_box (Gtk.Box, HORIZONTAL)  ← REPLACE
└── clear_btn (Gtk.Button)
```

### Target Structure (after Phase 25)

```
filter_box (Gtk.Box, HORIZONTAL)
├── add_btn (Gtk.Button)
├── edit_btn (Gtk.Button)
├── chip_container (Gtk.Box, VERTICAL, hexpand=True)
│   ├── _provider_flow (Gtk.FlowBox)  ← NEW
│   └── _tag_flow (Gtk.FlowBox)  ← NEW
└── clear_btn (Gtk.Button)
```

### Pattern: FlowBox Configuration (verified from edit_dialog.py:234–244)

The exact configuration to replicate for both `_provider_flow` and `_tag_flow`:

```python
# Source: musicstreamer/ui/edit_dialog.py:234-244 (Phase 24 implementation)
self._provider_flow = Gtk.FlowBox()
self._provider_flow.set_orientation(Gtk.Orientation.HORIZONTAL)
self._provider_flow.set_selection_mode(Gtk.SelectionMode.NONE)
self._provider_flow.set_column_spacing(8)
self._provider_flow.set_row_spacing(4)
self._provider_flow.set_homogeneous(False)
self._provider_flow.set_hexpand(False)  # CRITICAL — prevents overflow
self._provider_flow.set_margin_top(4)
self._provider_flow.set_margin_bottom(4)
self._provider_flow.set_margin_start(8)
self._provider_flow.set_margin_end(8)
chip_container.append(self._provider_flow)

# Repeat identically for self._tag_flow
```

### Pattern: Rebuild Method Update (verified from main_window.py:385–418)

Both rebuild methods iterate children via `get_first_child` / `get_next_sibling` / `remove`, then `append`. The only change is the target attribute name:

```python
# BEFORE (line 385)
child = self._provider_chip_box.get_first_child()
...
self._provider_chip_box.remove(child)
...
self._provider_chip_box.append(btn)

# AFTER
child = self._provider_flow.get_first_child()
...
self._provider_flow.remove(child)
...
self._provider_flow.append(btn)
```

Same substitution for `_tag_chip_box` → `_tag_flow` in the tag section (lines 401–418).

### Anti-Patterns to Avoid

- **Keeping ScrolledWindow as wrapper around FlowBox:** Defeats the purpose — FlowBox needs to size freely within chip_container.
- **Setting `hexpand=True` on FlowBox:** Causes overflow past adjacent buttons. `hexpand=False` is critical per Phase 24 summary.
- **Touching `chip_container` outer structure:** `chip_container` stays as a vertical `Gtk.Box` with `hexpand=True` — no changes needed there.
- **Touching signal handlers:** `_on_provider_chip_toggled`, `_on_tag_chip_toggled`, `_make_chip`, `_make_provider_toggle_cb`, `_make_tag_toggle_cb` — all unchanged.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Chip wrapping layout | Custom size-allocate logic | `Gtk.FlowBox` | Native GTK widget; handles wrap, spacing, resize automatically |
| Selection tracking | FlowBox selection mode | `Gtk.SelectionMode.NONE` + ToggleButton state | FlowBox selection is separate from ToggleButton toggle state; don't mix them |

---

## Common Pitfalls

### Pitfall 1: hexpand=True on FlowBox
**What goes wrong:** FlowBox expands to fill available space, overflowing past the Clear button.
**Why it happens:** Default GTK box packing — child hexpand propagates.
**How to avoid:** Explicitly `set_hexpand(False)` on both FlowBoxes.
**Warning signs:** Chips appear but Clear button disappears or shifts off-screen.

### Pitfall 2: Stale attribute references after rename
**What goes wrong:** Rebuild methods or other code still references `_provider_scroll`, `_tag_scroll`, `_provider_chip_box`, `_tag_chip_box` after they are removed.
**Why it happens:** grep for all usages before removing — there may be references outside the build and rebuild sections.
**How to avoid:** Search for all four attribute names in main_window.py before removing.
**Warning signs:** `AttributeError` at runtime on chip rebuild.

### Pitfall 3: FlowBox child wrapping vs Gtk.Box child
**What goes wrong:** When appending a ToggleButton to FlowBox, GTK wraps it in a `Gtk.FlowBoxChild` automatically. The `get_first_child()` loop iterates `FlowBoxChild` wrappers, not ToggleButtons directly.
**Why it happens:** FlowBox always wraps children in FlowBoxChild internally.
**How to avoid:** The existing remove loop calls `.remove(child)` on the container — this works correctly whether child is FlowBoxChild or not. The `_provider_chip_btns` list holds direct ToggleButton refs, which is correct. Phase 24 confirmed this pattern works.
**Warning signs:** Remove loop fails or chips aren't cleared on rebuild.

---

## Code Examples

### Full build section replacement (lines 210–230)

```python
# Source: main_window.py:210-230 (BEFORE) + edit_dialog.py:234-259 (Phase 24 pattern)

# Provider chip FlowBox
self._provider_flow = Gtk.FlowBox()
self._provider_flow.set_orientation(Gtk.Orientation.HORIZONTAL)
self._provider_flow.set_selection_mode(Gtk.SelectionMode.NONE)
self._provider_flow.set_column_spacing(8)
self._provider_flow.set_row_spacing(4)
self._provider_flow.set_homogeneous(False)
self._provider_flow.set_hexpand(False)
self._provider_flow.set_margin_top(4)
self._provider_flow.set_margin_bottom(4)
self._provider_flow.set_margin_start(8)
self._provider_flow.set_margin_end(8)
chip_container.append(self._provider_flow)

# Tag chip FlowBox
self._tag_flow = Gtk.FlowBox()
self._tag_flow.set_orientation(Gtk.Orientation.HORIZONTAL)
self._tag_flow.set_selection_mode(Gtk.SelectionMode.NONE)
self._tag_flow.set_column_spacing(8)
self._tag_flow.set_row_spacing(4)
self._tag_flow.set_homogeneous(False)
self._tag_flow.set_hexpand(False)
self._tag_flow.set_margin_top(4)
self._tag_flow.set_margin_bottom(4)
self._tag_flow.set_margin_start(8)
self._tag_flow.set_margin_end(8)
chip_container.append(self._tag_flow)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Gtk.ScrolledWindow` + `Gtk.Box` for chip rows | `Gtk.FlowBox` with wrapping | Phase 24 (edit dialog) | Chips wrap at column boundary instead of scrolling off-screen |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `get_first_child()` / `get_next_sibling()` / `remove()` loop works correctly on FlowBox (iterates FlowBoxChild wrappers) | Code Examples | Rebuild loop fails; chips not cleared — LOW risk, Phase 24 confirmed this pattern works in edit_dialog.py |

---

## Open Questions

None — all decisions are locked, existing pattern is confirmed, code locations are exact.

---

## Environment Availability

Step 2.6: SKIPPED — no external dependencies. Pure code change within existing GTK4 stack.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Manual visual verification (no automated UI tests in project) |
| Config file | none |
| Quick run command | `python -m musicstreamer` |
| Full suite command | `python -m musicstreamer` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| D-01 | Provider + tag chips wrap instead of scroll | manual-only | `python -m musicstreamer` | N/A |
| D-02 | Provider and tag chips in separate FlowBoxes | manual-only | `python -m musicstreamer` | N/A |

Manual verification checklist:
- Chips wrap to multiple lines when many providers/tags exist
- Add Station, Edit, Clear buttons remain at expected positions (not pushed off-screen)
- Clicking chips still toggles filter correctly
- `_rebuild_provider_chips` and `_rebuild_tag_chips` clear and repopulate without errors

### Wave 0 Gaps

None — no new test infrastructure required for this layout-only fix.

---

## Security Domain

Not applicable — layout-only change, no new data paths, no new trust boundaries.

---

## Sources

### Primary (HIGH confidence)
- `musicstreamer/ui/main_window.py:195–240` — exact code to replace (VERIFIED: Read tool)
- `musicstreamer/ui/main_window.py:380–418` — rebuild methods to update (VERIFIED: Read tool)
- `musicstreamer/ui/edit_dialog.py:234–259` — Phase 24 FlowBox pattern to replicate (VERIFIED: Read tool + Grep)
- `.planning/phases/24.../24-01-SUMMARY.md` — Phase 24 execution notes confirming `hexpand=False` criticality (VERIFIED: Read tool)
- `.planning/phases/25.../25-UI-SPEC.md` — UI design contract for this phase (VERIFIED: Read tool)
- `.planning/phases/25.../25-CONTEXT.md` — locked decisions (VERIFIED: Read tool)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, reusing proven pattern
- Architecture: HIGH — exact code locations confirmed, Phase 24 pattern verified
- Pitfalls: HIGH — derived from Phase 24 summary and GTK4 FlowBox behavior

**Research date:** 2026-04-08
**Valid until:** Stable — GTK4 API does not change frequently
