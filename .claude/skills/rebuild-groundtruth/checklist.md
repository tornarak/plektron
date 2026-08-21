# Reading checklist

Work this per page; this is what you tick, and the reasoning is R1–R10 in your
contract and the spec it cites. Items in **Settled** are closed rules — apply and
cite, never zoom to confirm. Items in **Evidence** are read off the glyph's own
ink; "confirmed at 4×" and "contrasted against" are not evidence.

## Before reading

- [ ] `ocr gaps PP-NNN` run; each `exempted` band read **with its `reason`** —
      `not_type` taken as settled, `covered` taken as "line `covered_by` is
      printed wider than its box, key all of it" — and the rest ruled
      line-or-not and **reported, never repaired**
- [ ] Every line's `text` describes only that line's own box — printed matter no
      index covers went into the report, never onto a neighbour and never into a
      field of its own
- [ ] Whole page image read once for orientation (heads, folio, footnotes, figures)
- [ ] All contact sheets read in full before any zoom

## Settled — apply and cite, do not go to the raster

- [ ] Quotation marks curly `“…”`, never straight — §1, R1
- [ ] Every raised mark keyed stress U+02CA, never U+0027 — §2.1, R4
- [ ] Footnote markers are superscript sorts `¹²³⁴⁵⁶⁷⁸⁹`, never ASCII digits — §2.10
- [ ] A note opener printing no marker, where the body reference is marked: the
      marker **supplied** and noted as supplied, not flagged as absent — §2.10
- [ ] Dashes are em U+2014 — §2.11
- [ ] Roman numerals and folio slots plain ASCII — §2.12
- [ ] Page number located by zone — `RunningTitleZone` (plain digits) **or**
      `QuireMarksZone` (bracketed, at the foot), never both — keyed with no interior
      space, box width checked for clipping, CATMuS's version corrected where it
      differs, and never sourced from the scan index or a neighbour
- [ ] No small-cap keyed but `ᴀ ᴇ ɪ ʟ` — §2.3, R5
- [ ] Dot-leader runs dropped, not reproduced
- [ ] Breve keyed only on `u`/`i`, never on the obscure-vowel series — §2.6
- [ ] No uncatalogued codepoint keyed; letter keyed as printed, mark flagged — R5
- [ ] Word-final `-gɪn`/`-gɪt` keyed dotted, without a note — §5.1

## Evidence — read from the glyph's own ink, never a comparison

- [ ] Every other Tier-1 `g` ruled from its own ink at 4× or keyed dotted on the
      prior and flagged — §5.1, R2
- [ ] Every bare `a` considered for `ä` — §5.3, R2
- [ ] Every `ɪ`/`i`/`r` read by what the letter has, not against another — R2
- [ ] Every word-initial capital-shape ruled by position, never by height — §5.4, R3
- [ ] Every multisyllabic Tier-1 word carries exactly one stress mark; any that
      does not is flagged, not accepted — §5.5, R4
- [ ] Lettered cross-references read as the series, not as the draft — R6
- [ ] A form the book glosses as another language keyed without the priors and
      noted — R8

## Mechanical — run these, read the output

- [ ] `proposal fix PP-NNN`, then re-run: zero output
- [ ] `proposal check PP-NNN`: verdict row reads **exit 0** — a defect is yours to fix, never to explain
- [ ] every `advisory` row read and answered in `note`
- [ ] `resolved/text mismatch` repeating down the page treated as systematic — R4
- [ ] `corpus normalize --commit review/PP-NNN/proposal.json`, then again without: verdict exit 0

## Before finalizing

- [ ] Every `note` re-read against its own `text` — R7
- [ ] Every `keying_spec.md` citation in a note quotes its sentence — R7
- [ ] No note claims what another witness said unless it was consulted — R7
- [ ] Notes written in codepoints, not glyphs — R7
- [ ] No note asserts a linguistic fact the page does not print — R7
- [ ] No line ends in punctuation the draft and the page lack — R9
- [ ] Every `note` carries a `class`: doubt / semantic / print / draft / layout /
      artifact — `print` is the compositor's error, `draft` the recognizer's
- [ ] Every `{handle}` names a form you *read* and would have retyped — never one
      the raster left in doubt, which is a flag and not a lookup
- [ ] …and the converse: no Tier-1 form retyped by hand that `lexicon lookup`
      offered a key for
- [ ] …and its precondition: every native term or proper name the page uses
      **without introducing it** was searched, in one call
- [ ] `contamination` block present; `blind: true` unless something nameable
- [ ] Every line index present, `text` non-empty on all of them
