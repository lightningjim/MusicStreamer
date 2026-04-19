# Phase 48: Fix AudioAddict listen key not persisting to DB - Discussion Log

> Audit trail only. Decisions live in CONTEXT.md.

**Date:** 2026-04-19
**Phase:** 48-fix-audioaddict-listen-key-not-persisting-to-db-settings-aud
**Areas discussed:** Save trigger, Management surface, Display security, Regression test shape

---

## Save Trigger

### Q: When should the listen key be written to the DB?
| Option | Selected |
|--------|----------|
| On successful fetch (Recommended) | ✓ |
| On every edit (textChanged) | |
| Explicit Save button | |

### Q: Should ImportDialog pre-populate from saved setting on open?
| Option | Selected |
|--------|----------|
| Yes, always pre-fill (Recommended) | ✓ |
| No, always start blank | |

---

## Management Surface

### Q: Where can users see/clear the saved AA listen key?
| Option | Selected |
|--------|----------|
| ImportDialog only | |
| AccountsDialog only | |
| Both — Import auto-saves, Accounts shows + clears | ✓ |

### Q: How should the AudioAddict group in AccountsDialog behave?
| Option | Selected |
|--------|----------|
| Status + Clear only (Recommended) | ✓ |
| Status + Edit + Clear | |

### Q: Should clearing the saved key require confirmation?
| Option | Selected |
|--------|----------|
| Yes, QMessageBox confirm (Recommended) | ✓ |
| No, single click clears | |

---

## Display Security

### Q: How should the AA key field display the key?
| Option | Selected |
|--------|----------|
| Masked with Show toggle (Recommended) | ✓ |
| Masked only, no toggle | |
| Plain text | |

---

## Regression Test Shape

### Q: How deep should the regression test go?
| Option | Selected |
|--------|----------|
| Widget test save-reopen-readback (Recommended) | ✓ |
| Unit test only (repo round-trip) | |
| Full app-restart simulation | |

### Q: Which additional code paths need tests? (multi-select)
| Option | Selected |
|--------|----------|
| ImportDialog prefills on open from saved setting | ✓ |
| AccountsDialog AA group reflects saved status + clear works | ✓ |
| Password mode + Show toggle behavior | ✓ |
| Export ZIP still excludes the key (Phase 42 regression guard) | ✓ |

---

## Claude's Discretion

- AA group exact widget layout (copy Twitch)
- ImportDialog `repo` kwarg threading (confirm during planning)
- Show-toggle icon (prefer theme icon; bespoke SVG only as fallback)
- Save call placement within success slot (prefer before UI update)

## Deferred Ideas

- AA key validation on edit
- OS keyring / encrypted-at-rest storage
- "Remember my key" opt-out checkbox
- Multi-account AA support
- Partial masked preview (first/last 4 chars) in AccountsDialog
