# GBS Marquee — Fixture MANIFEST

Phase 87 marquee text snapshots harvested for parser-lock (Plan 87-02) + GBS-MARQ-07 fixture corpus (≥10 samples required; Pitfall #8 relaxation allows synthetic top-up by Plan 87-02).

## Schema

| Column | Meaning |
|--------|---------|
| `filename` | Filename within this directory |
| `capture_date` | ISO-8601 date the fixture was captured |
| `sha256` | `hashlib.sha256(file_bytes).hexdigest()` of file bytes |
| `source_url` | URL the bytes were fetched from |
| `capture_method` | `cookies` (Phase 76 dev cookies used) / `anonymous` (D-11 fallback) / `synthetic` (constructed for parser robustness, Pitfall #8) |
| `provenance` | `real-captured` / `synthetic` — locked-by-Pitfall-#8 audit column |
| `notes` | Observed marquee text / parser hints / redactions |

## Entries (real-captured — Plan 87-01)

| filename | capture_date | sha256 | source_url | capture_method | provenance | notes |
|----------|--------------|--------|------------|----------------|------------|-------|
| `2026-05-25_homepage.html` | 2026-05-25 | `f5f9c3fdaedf8b613b716d9a15629e771e073f99e39db82cf9aa27ec8ccd0d67` | https://gbs.fm/ | cookies | real-captured | **Marquee lives in `<p id="noticearea">` element.** First pipe-segment text: `da troops*` (with `[*LATEST FAD]` marker in trailing segment). Subsequent perpetual segments include show plug + RIP notice + AI-upload warning. Inner `<b>` and `<br>` tags interspersed — parser MUST strip HTML. |
| `2026-05-25_ajax_cold.json` | 2026-05-25 | `71c3cbdba230f178f3d6eb5ab4e15defb58260cff34779eb5420107599e9d8e0` | https://gbs.fm/ajax?position=0&last_comment=0&last_removal=0&last_add=0&now_playing=0 | cookies | real-captured | Cold /ajax stream — does NOT contain themed-day keywords. Marquee text is NOT carried in this endpoint. Plan 87-02 should lock the marquee URL to `https://gbs.fm/` (homepage HTML) with `<p id="noticearea">` selector. |

## Parser hint (for Plan 87-02)

The marquee text structure observed today:

```html
<p id="noticearea"><b>GBS-FM</b>: da troops* | Tune in to <b>A Queerdo's Storytime</b> hosted by Venomous at <b>4pm BST/10am CDT/8am PDT FRIDAY</b>! | RIP Rob Base & Dick Parry & Dennis Locorriere<br><b>DO NOT UPLOAD AI GARBAGE LIKE <a href="/song/726310">THIS</a>. WE WILL BAN IT AND NOT LIKE YOU.</b> Please only upload human-created music, and also, please report any AI dongs you find.</br>Hit us up on the Discord. [*LATEST FAD]</p>
```

Recommended `parse_marquee()` algorithm (Plan 87-02 will refine):

1. Extract `<p id="noticearea">…</p>` content via regex or BeautifulSoup
2. Strip inner HTML tags (`<b>`, `<br>`, `<a>`, etc.) to plain text
3. Drop the leading `GBS-FM: ` prefix if present
4. Split on `|` per GBS-MARQ-02 (literal) + D-13
5. `.strip()` each segment per Pitfall #6
6. First non-empty segment = changeable announcement (e.g., `da troops*` today)
7. Subsequent segments = perpetual (ignored for banner display; full text retained for themed-day keyword search per D-12)

The trailing `*` on `da troops*` correlates with `[*LATEST FAD]` marker in a later segment — GBS.FM operator convention for "newest thing." Phase 87 ignores this; the trigger text matched by the themed-day keyword set is still the substring `da troops`.

## Synthetic Samples (Pitfall #8 — parser robustness)

Plan 87-02 added 8 synthetic samples to satisfy GBS-MARQ-07's ≥ 10 fixture count
(2 real-captured + 8 synthetic = 10 total data files).  Each synthetic file contains
a single line of marquee plain text exercising a specific parser-robustness scenario.
Synthetic files are distinguished from real-captured entries by filename prefix
(`synthetic-`) and `provenance = synthetic` in this table.

| filename | capture_date | sha256 | capture_method | provenance | notes |
|----------|--------------|--------|----------------|------------|-------|
| `synthetic-001.txt` | 2026-06-15 | `47210d49290f3164be3e62ab16c57afb74866b1f78da15b40e4022ac6a6576aa` | synthetic | synthetic | Single segment, no pipes ("Welcome to GBS.FM") |
| `synthetic-002.txt` | 2026-06-15 | `72f48a2faf625b1d9de1386416424c767d1354485aa3c8cdccfab92f8b52f74e` | synthetic | synthetic | Bare-pipe delimiter, two segments ("Announcement\|Tagline") |
| `synthetic-003.txt` | 2026-06-15 | `5fe9d1196678a7573d0c176aa6b53a9ab86cc18978980dc2fdc9841342acfb85` | synthetic | synthetic | Space-padded delimiter, three segments ("Special event \| Tip jar \| Schedule") |
| `synthetic-004.txt` | 2026-06-15 | `663e451570c7567b79e8a7ece208cb47d81d305d55075dd93a3884a7ad868012` | synthetic | synthetic | Announcement with internal punctuation + pipe-padded perpetuals (Memorial Day specimen) |
| `synthetic-005.txt` | 2026-06-15 | `eae1591a5e9c8635e0e664868b56d24930c1ed5367a1713959d6ac2bca9062f1` | synthetic | synthetic | Unicode in announcement (🎄 emoji) |
| `synthetic-006.txt` | 2026-06-15 | `18bd79db964fb71af81bf764ec5f19747ee7c6274c103013f715720682b096c5` | synthetic | synthetic | Leading empty segment ("\|leading-empty-stripped\|Real announcement") |
| `synthetic-007.txt` | 2026-06-15 | `7c68d2306e3d9616c80b354d42af3d5f736d2376ebd1220da1ca2d6bed7fc8d4` | synthetic | synthetic | Leading + trailing whitespace, mixed delimiter spacing (long multi-pipe line) |
| `synthetic-008.txt` | 2026-06-15 | `ae23747a2fd8843bd201e6f474b3d6f7fe220123baeaa8371999dbe564c29635` | synthetic | synthetic | 4-segment line with unicode emoji (🍀), verifies multi-pipe + unicode together |
