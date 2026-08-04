# Reading checklist

Work this per page. `keying_spec.md` §5 is why each item is here; this is what you
tick. Items in **Settled** are closed rules — apply and cite, never zoom to confirm.
Items in **Evidence** need a named contrast word in `note`; "confirmed at 4×" is not
evidence, it is what both readings that were wrong said.

## Before reading

- [ ] `ocr gaps PP-NNN` run; every band ruled line-or-not, `adopt-gap` if a line
- [ ] Whole page image read once for orientation (heads, folio, footnotes, figures)
- [ ] All contact sheets read in full before any zoom

## Settled — apply and cite, do not go to the raster

- [ ] Quotation marks curly `“…”`, never straight — §1, §5.6
- [ ] Every raised mark keyed stress U+02CA, never apostrophe U+0027 — §5.8
- [ ] Footnote markers are superscript sorts `¹²³⁴⁵⁶⁷⁸⁹`, never ASCII digits — §2.10
- [ ] Dashes are em U+2014 — §2.11
- [ ] Roman numerals and folio slots plain ASCII — §2.12
- [ ] No small-cap `o` keyed (bases are `ᴀ ᴇ ɪ ʟ` only) — §2.3, §5.10
- [ ] Dot-leader runs dropped, not reproduced
- [ ] Breve keyed only on `u`/`i`, never on the obscure-vowel series — §2.6
- [ ] No uncatalogued codepoint keyed; letter keyed as printed, mark flagged — §5.0, §5.9

## Evidence — absence-shaped, no tool settles these

- [ ] Every Tier-1 `g` ruled dotted or bare, with a contrast word named in `note`
      or "no contrast on this line" — prior is 93.9% dotted — §5.1
- [ ] No word left ending bare `-git`/`-gin`/`-gɪn` without a stated reason — §5.1
- [ ] Every word-initial capital-shaped letter ruled ASCII or small-cap
      (63:55 — nothing mechanical settles it) — §5.2
- [ ] Every bare `a` considered for `ä` (14.0% of Tier-1 `a`) — §5.3
- [ ] Every `ɪ`/`i`/`r` call made against a real `r` on the line — §5.2
- [ ] Every multisyllabic Tier-1 word carries exactly one stress mark; any that
      does not is flagged, not accepted — §2.1, §5.5
- [ ] Old-style figures checked: `1` is x-height and dotless, `0` small and round — §5.4

## Mechanical — run these, read the output

- [ ] `proposal fix PP-NNN`, then re-run: zero output
- [ ] `proposal check PP-NNN`: exit 0, or every issue read and answered
- [ ] `resolved/text mismatch` repeating down the page treated as systematic — §5.5
- [ ] `corpus normalize --commit review/PP-NNN/proposal.json`, then again without: exit 0

## Before finalizing

- [ ] Every `note` re-read against its own `text` — §5.11
- [ ] Every `keying_spec.md` citation in a note quotes its sentence — §5.11
- [ ] No note claims what another witness said unless it was consulted — §5.12
- [ ] Notes written in codepoints, not glyphs — §5.12
- [ ] `contamination` block present; `blind: true` unless something nameable
- [ ] Every line index present, `text` non-empty on all of them
