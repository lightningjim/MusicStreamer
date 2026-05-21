---
phase: 81-station-list-alphabetical-sorting-is-case-sensitive-a-z-then
reviewed: 2026-05-21T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - musicstreamer/repo.py
  - tests/test_repo.py
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 81: Code Review Report

**Reviewed:** 2026-05-21
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Phase 81 is a tightly-scoped fix: append `COLLATE NOCASE` to two ORDER BY clauses
(`list_stations` line 441, `list_favorite_stations` line 678) and add three tests
(two behavioral interleave checks + a source-grep drift-guard). The production
change is correct standard SQLite syntax and carries no security or correctness
risk for ASCII station names. The phase decision D-05 explicitly accepts SQLite
NOCASE's ASCII-only folding as a known limitation.

Findings are all in the test layer or quality observations on the drift-guard
pattern — no production-code defects were found. Severity: 0 Critical, 1 Warning,
3 Info.

## Warnings

### WR-01: Provider-name COLLATE branch is not exercised by behavioral tests

**File:** `tests/test_repo.py:838-857`
**Issue:** Both `test_list_stations_case_insensitive_order` and
`test_list_favorite_stations_case_insensitive_order` seed stations via
`_seed_mixed_case_stations`, which calls `update_station(sid, n, None, "", None, None)`
with `provider_id=None`. The LEFT JOIN therefore produces `p.name = NULL` for every
row, `COALESCE(p.name,'')` collapses to `''` uniformly, and the *first* ORDER BY key
contributes nothing to the test's expected ordering. Only the second key
(`s.name COLLATE NOCASE`) is actually exercised behaviorally.

Consequence: if a future change accidentally removed `COLLATE NOCASE` from the
`COALESCE(p.name,'')` expression (e.g., from a refactor or a mis-merge), the two
behavioral tests would still pass green. The source-grep drift-guard (TR-03) would
catch the exact-string regression, but a near-equivalent regression (e.g., trailing
whitespace difference, or splitting onto two lines) would slip past the grep AND
the behavioral tests simultaneously.

**Fix:** Add at least one test that seeds two providers whose names differ only by
case (e.g., `"Alpha"` and `"alpha"`), each owning a station, and asserts the
expected interleaved order. Sketch:

```python
def test_list_stations_case_insensitive_provider_order(repo):
    p1 = repo.ensure_provider("Zebra")
    p2 = repo.ensure_provider("alpha")
    s1 = repo.create_station(); repo.update_station(s1, "A", p1, "", None, None)
    s2 = repo.create_station(); repo.update_station(s2, "B", p2, "", None, None)
    result = repo.list_stations()
    # alpha < Zebra under NOCASE
    assert [s.provider_name for s in result] == ["alpha", "Zebra"]
```

This closes the gap so both ORDER BY columns are behaviorally locked, not just
the second one.

## Info

### IN-01: `str.casefold` oracle diverges from SQLite NOCASE for non-ASCII names

**File:** `tests/test_repo.py:856`
**Issue:** `test_list_favorite_stations_case_insensitive_order` computes its
expected ordering via `sorted(favorite_names, key=str.casefold)`. SQLite's
`COLLATE NOCASE` is ASCII-only (per phase decision D-05) — it folds only `A-Z` ↔
`a-z`. Python's `str.casefold` is Unicode-aware and additionally folds many
non-ASCII characters (e.g., German ß → ss, Greek Σ/σ/ς).

For the current ASCII-only seed list the two definitions agree, so the test passes
correctly today. The latent risk: if a future contributor extends the seed list
with a non-ASCII name (e.g., `"Café del Mar"`, `"Ärger"`), the test would fail not
because the production code is broken but because the test oracle is more
permissive than the production collation.

**Fix:** Either (a) hardcode the expected list literally like sibling test
`test_list_stations_case_insensitive_order` does, or (b) add an inline comment
warning future editors that the seed list MUST remain ASCII-only while the oracle
is `str.casefold`. Sketch (option a):

```python
expected = ["aardvark", "Drone Zone", "Zenith"]
assert [s.name for s in result] == expected
```

### IN-02: Drift-guard `count == 2` is brittle for the +1 direction

**File:** `tests/test_repo.py:866-868`
**Issue:** The drift-guard asserts the exact phrase appears EXACTLY twice in
`repo.py`. This catches the −1 case (someone removed COLLATE NOCASE from one
clause) but also fails on the +1 case — i.e., a legitimate future addition of a
third ordered station query (e.g., a "browse by name" list) that correctly uses
the same `COLLATE NOCASE` phrase. The failure mode would be a confusing
"Phase 81 D-03: both list_stations and list_favorite_stations must keep
COLLATE NOCASE..." error that doesn't describe the actual situation (a third
correct usage was added).

Phase 51/55/61/63 precedent uses the same `== N` pattern, so this is consistent
with house style — but worth flagging because the failure message will mislead
the next person who legitimately needs a third sorted query.

**Fix:** Optional — change to `>= 2` and adjust the message to "at least both…",
OR leave as-is and accept that the next addition will require updating both the
ORDER BY phrase count AND the assertion. Either is defensible; flagging for
awareness.

### IN-03: Drift-guard whitespace fragility

**File:** `tests/test_repo.py:866`
**Issue:** The matched string includes exact spacing:
`"ORDER BY COALESCE(p.name,'') COLLATE NOCASE, s.name COLLATE NOCASE"`. Any
whitespace normalization (autoformatter applied to triple-quoted SQL, or a
reviewer reflowing the SQL onto two lines for readability) would silently drop
the count to 0 and trigger the assertion — without any actual behavioral
regression in the production code.

The two production occurrences live inside triple-quoted SQL string literals
(lines 437-442, 673-679), which Python autoformatters generally leave alone, so
the risk is low. But if anyone ever reformats the SQL (e.g., uppercasing
`coalesce`, or splitting the ORDER BY onto its own line), the guard breaks.

**Fix:** Optional hardening — use a regex with `\s+` between tokens, or rely on
counting `"COLLATE NOCASE"` occurrences (expecting 4 in ORDER BY context).
Acceptable as-is given the current code shape; flagging so a future SQL
reformat doesn't surprise anyone.

---

_Reviewed: 2026-05-21_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
