---
name: transcribe-page
description: Collate one page of Bogoras into TEI from its draft transcript and scan, and record the seam it shares with the previous page. Use when asked to transcribe, collate, or "do" a page, or on /transcribe-page PP-NNN. Carries the full rule set — output contract, the firewall, language spans, ids, seams. Not the raster→ALTO reading loop; that is rebuild-groundtruth.
---

# Collate one page (OCR → TEI)

You are the driver. The scripts are your instruments and your gate; the human is
your court of appeal.

This pass produces the base page file — structure, foreign-span marking,
uncertainty markup — and the seam it shares with its predecessor. It is **not**
the annotation pass (persons, places, taxa, run later over finished TEI), and it
mints no authority-file ids. Language-span marking happens here out of necessity:
you cannot decide the apostrophe encoding without knowing what is Chukchi. Treat
every `xml:lang` boundary you draw as a fast draft for a dedicated language-spans
pass to confirm, not a final answer.

**References in this file are by section title, never by line number.** A page's
adjudication record in `review/` still cites a rule of the old collation doc by
line number; that document has since been folded into this one and the citation
now points at nothing. A reference that cannot survive its target being edited was
never a reference.

## Before your first page of a session

**Read `keying_spec.md` in full with the Read tool — not `grep`.** It governs the
Tier-1 character inventory, which you read off the raster exactly as the
ground-truth loop does. It is short enough to read whole and dense enough that a
grep for a term you already suspect finds that term and misses the rest of the
inventory beside it: the mark you did not know to search for, the licensing note
that would have overridden your first guess, the changelog entry recording that
someone already made your mistake. Its **§5 is a checklist of misreading classes
measured across both passes** — a dropped mark under a `g`, `ɪ` vs `i`, `ä` vs
plain `a`, stress mark vs plain apostrophe. Run it per line against every Tier-1
span before emitting it.

`CLAUDE.md` governs project invariants and outranks this file on them.

## The loop, per page ref PP-NNN

Refs are part + scan index (`1-100`), never a bare page number. NNN is a scan
index, not a printed folio, and neither is derivable from the other — so the CLI
rejects a bare integer rather than guess which of the three parts you meant.

    uv run harness context PP-NNN                  the input contract
    (read the page image with the Read tool)       the only witness that matters
    uv run harness zoom PP-NNN --only 7,20 --from gt/ocr    the closer look
    (author tei/chukchi-PP-NNN.xml)                your reading
    uv run harness normalize --path tei/chukchi-PP-NNN.xml  NFD + spacing
    uv run harness ids PP-NNN                      the id scheme
    uv run harness validate PP-NNN                 the gate; exit 1 on FAIL
    uv run harness seam PP-NNN --continues|--fresh --commit   the gap behind you

Then re-read your own output once against the image before declaring done.

`--from gt/ocr` on `zoom` matters: its default store is a different ALTO from the
one `ocr_lines` ids come from.

# The input contract

`harness context PP-NNN`, emitted as TOON. Everything in it is **precomputed by
deterministic script**. You consume it; you never re-derive it. Do not
recalculate a ToC id, a figure zone, or a detector flag that was handed to you.

## `catmus_draft` — and the tautology hazard in it

Read the draft and the image together. The draft is a starting point and not a
source of truth; on any non-ASCII character it is not even that.

Two facts about it, both live, and they must not be conflated:

- **What CATMuS produces is 0% of the inventory.** Measured against a human key:
  of 41 non-ASCII characters on a page it produced 13, not one of them an
  inventory glyph — all the U+02CA, all the `ɪ`, the `ᵋ`, all the Cyrillic, lost.
  That measurement is why the old "reproduce the draft verbatim" firewall died:
  it was unsatisfiable over real recognizer output.
- **What you receive today is usually restored *human* ground truth.** `ocr/`
  symlinks into `gt/ocr/`, and all 20 workable pages have been through a human.
  So the draft's Tier-1 characters may be a careful editor's reading arriving
  under a machine label.

The second is the trap. Reading them as confirmation of your own reading compares
a file against something that already agrees with it — the same shape as `harness
review`'s span diff, which now refuses rather than report a clean 40/40 when its
two witnesses resolve to one file. **A comparison whose witnesses may be one
witness must say so.** So the rule is unchanged and now carries more weight: read
the image, and let the draft have no vote on any non-ASCII character.

## `prev_tail` — the previous page's last element

Markup, not a text excerpt, because the markup is where the witnesses are:
`<item n="14">` is what settles whether the list resuming at 15 on this page is
the same list, and a flattened tail throws that away along with every `xml:lang`
and `@resp` in play at the seam. Trimmed by dropping whole leading children so it
always parses, with `elided_children` saying how many went.

`null` when the predecessor is not collated — the same case `harness seam`
refuses. `part` on it is a verdict already recorded for this gap, if `seam` has
run.

`ends_sentence` is **a hint and never a verdict**. `1-100` closes its numbered
list at item 14 with a full stop and `1-101` resumes it at 15. Absence of a
terminal stop is positive evidence; presence of one is only the lack of it.

**`prev_tail` is read-only reference in exactly the way `foreign_terms_nearby`
is.** Never a source to copy a Tier-1 form from, and — now that it hands you real
markup — never a source to copy an `xml:id` from either. An id names the page it
lives on, and the gate checks it.

## The other fields

- **`expected_folio`** is a prediction, not an instruction, and is routinely
  `null`: it is the last *numbered* predecessor's folio plus one, and null
  wherever that chain breaks. Null is not a defect. It means read the folio off
  the image and do not guess, which is what you do either way.
- **`toc_window`** is a neighbourhood, not a resolution — entries near the
  expected folio plus any the milestone fold believes open, each marked
  `open`/`starts_here`/`distance`. The marks derive from a prediction and inherit
  its errors. They tell you which entry to look at first; the page decides.
- **`figures_on_page`** carries zone ids verbatim from the segmented ALTO
  (`eSc_textblock_…`, never minted here), with bbox and caption text. A
  `GraphicZone` is geometry and never carries text; a `GraphicZone-FigDesc`
  carries the printed caption.
- **`ocr_lines`** is every `TextLine` from the same ALTO the draft was built
  from, in document order, empties included, each with its real ALTO `@ID`. It
  exists so a Tier-1 span can cite which line it was read from. Never use these
  ids for anything else, and never infer text from a `line_id`.
- **`foreign_terms_nearby`** is recomputed each call from committed TEI on the
  physically neighbouring pages, and carries each term's gloss plus the `scope`
  its gloss list supplies — without which "white mixed with brown" says nothing
  about what is white. It exists so
  a term keyed two ways across a spread is *visible*. It licenses nothing: this
  page's Tier-1 content comes from this page, and a form on a neighbour is never
  a target to harmonize toward.
- **`detector_flags`** and **`balance_flags`** are mechanical triage, run before
  the call. A flag means "worth a look", never "this is wrong".

# The seam

**About 70% of text pages open mid-paragraph** — 69.8% measured over the keyed
zone corpus. So *continues* is the ordinary case and *fresh* is the exception,
which is the opposite of what a page-at-a-time reading suggests.

Read three things together:

1. **`prev_tail`'s markup** — how the previous page's last element ends, what
   kind it is, and for a list, what `@n` its last item carries.
2. **This page's own opening text.** `1-100` opens `come to the herd` — lowercase,
   mid-sentence, and decisive on its own.
3. **The first line's indent on the image.** A paragraph opening indented is a
   new paragraph; running flush to the measure, it continues one. This is the
   positive witness and you already have the image in front of you.

Then record it:

    uv run harness seam PP-NNN --continues --commit
    uv run harness seam PP-NNN --fresh --commit

**You do not write `@part`, `@prev` or `@next` by hand.** The verb writes both
ends of the gap — this page's first top-level element and the previous page's
last — because a gap is one fact landing on two elements, and this page is the
only place both witnesses exist. Where the elements are not fragmentable (a
`<list>` or `<table>` running on) it mints ids and links them instead; where the
two sides are different kinds it refuses, because a `<p>` ending one page and a
`<list>` opening the next are two elements, not one carrying across.

There is no `boundaries.json` and no geometry pass. The committed TEI is the
record.

**If the predecessor is not collated, `seam` refuses and that is correct.** Work
in scan order or within a chapter.

# Output contract

One TEI page file at `output_path`. `<pb>` first, no `<div>`, no `<lb/>` anywhere
— the line record lives in the ALTO committed alongside; the TEI carries the
reading text.

Use this teiHeader exactly, changing only the page number (omitted where the page
has none, and then the sourceDesc reads "see corpus teiHeader" alone):

      <teiHeader>
        <fileDesc>
          <titleStmt>
            <title>see corpus teiHeader</title>
          </titleStmt>
          <publicationStmt>
            <p>see corpus teiHeader</p>
          </publicationStmt>
          <sourceDesc>
            <p>see corpus teiHeader; page {folio}</p>
          </sourceDesc>
        </fileDesc>
      </teiHeader>

**No `respStmt` here.** The provenance ranks are declared once, in
`tei/corpus-header.xml`, and never repeated per page. That file exists and
`harness header` gates it, holding it and `validate.RESP_RANKS` to each other. A
page file remains a *fragment*: it defers title, publication and source the same
way, so `resp="#llm"` resolves against the assembled document and not against the
page read alone. That is not a defect to fix here. One declaration cannot drift
from itself; 730 copies can.

## Page furniture and the folio

- **The printed folio is content.** Transcribe it into `<pb n="{folio}"/>`, the
  first element in `<body>`. Read it off the image. Never copy `expected_folio`
  into `@n` because it was supplied — it is the value your folio is *checked
  against*, and a folio invented here is one the rest of the volume inherits
  through the ledger.
- **Folio disagrees with a non-null `expected_folio`**: the printed folio wins.
  Add immediately after `<pb>`:
  `<!-- printed folio {folio} disagrees with expected {expected_folio} (predicted
  from {basis_ref}): check ToC alignment -->`. With `expected_folio` null there is
  nothing to disagree with and no comment is needed.
- **No folio printed** (plates, some chapter openings, blanks): `<pb/>` with no
  `@n`, plus `<!-- no printed folio on this page -->`. This is a positive
  assertion — nothing was printed here — and the ledger reads it as one, so an
  unpaginated page does not advance the count.
- **A folio present but unreadable** is neither. Do not encode it as `<pb/>`,
  which asserts the page was never numbered. Comment and ask.
- **Running heads and series titles** ("BOGORAS, THE CHUKCHEE.", "JESUP NORTH
  PACIFIC EXPEDITION, VOL. VII.") are discarded silently — not `<fw>`, not a
  comment, nothing. They are identifiable by position and by fixed, textually
  redundant content, and must never reach the heading logic.

## Headings — milestone vs. local caption

You do not construct milestone content. Heading-shaped text (isolated line,
capitalized or small-capped, no terminal punctuation) that matches a `toc_window`
entry becomes exactly:

    <milestone unit="{unit}" n="{id}"/>

`{id}` copied verbatim from that entry's `id` — never the title, never a number
you construct. `{unit}` is fixed by the entry's `level`: 1 chapter, 2 section,
3 subsection, 4 subsubsection. Level 0 is front matter and never produces a
milestone. Nothing else goes on the element.

**The match is to the text on the page, not to the marks.** `starts_here` and
`open` are keyed to a predicted folio and are wrong often enough that they may
never be the reason a milestone is or is not emitted. Heading-shaped text
matching an entry marked `starts_here: false` is still that milestone.

If heading-shaped text matches nothing in `toc_window`:

- immediately followed by a `<list>` or `<table>` → attach as that element's
  `<head>`, copying the text exactly, no correction, no retitling;
- otherwise → leave it as plain text where it sits and add
  `<!-- heading-shaped text, no ToC match, no list/table follows: needs a human
  call on where this attaches -->`. Never force a `<head>` onto something it does
  not caption, and never let a non-ToC heading enter chapter state.

If an entry is marked `starts_here: true` and nothing matches it, do not force a
milestone. Comment instead: `<!-- expected milestone for {id} ({title}) not found
on this page: check for a missed milestone or a heading straddling the page
boundary -->`.

## Footnotes

- `<note n="{marker}" place="bottom">`, the marker exactly as printed (an integer
  in this book). Copy it; do not renumber, do not infer it from position.
- **Anchor every note at its exact marker position** in the running text — not
  gathered at the foot, not moved to the nearest sentence boundary. If the marker
  falls mid-clause or inside a parenthetical, the note goes there, however awkward
  the nesting.
- **No whitespace immediately before a `<note>`.** The element stands in for the
  printed marker, and the book sets a thin space before the raised digit
  (`1-100`: `[albino] ¹)`). That is the same class of thing as the French spacing
  before `;` and `:` that keying spec §2.9 already overrides — typesetting with no
  lexical content, which leaves a stray space in the reading text of anything that
  strips the marker. Key it tight. The gate errors on it.
- **Orphan foot-text** (a note run over from the previous page, no marker here):
  emit as `<note>` with **no** `@n`, after the last `<p>`, preceded by exactly
  `<!-- footnote continuation, no marker on this page: the note it continues is
  unresolved -->`. Do not guess which note it continues. A note running across a
  seam has no markup yet and is deliberately left unresolved.

## Figures

Anchor `<figure>` at the first textual reference ("Fig. 291"), pointing at the
matching zone with `facs="#{zone_id}"` from `figures_on_page`. Match reference to
zone by figure number. **Never invent a zone id.** If a textual reference matches
no supplied zone, or a supplied zone is never referenced, comment naming the
orphan and emit nothing else for it.

## Content shape — prose vs. gloss list vs. table

- Default is `<p>`, one per visible paragraph break.
- **`<list type="gloss">`** when the body is a run of `[term] [gloss]` entries —
  this book's dictionary-style vocabulary tables. One `<item>` per entry holding a
  `<term>` (with the Tier-1 rules below, or plain text if the term is English)
  followed by a `<gloss>`. An entry indented further right than its neighbours is
  a sub-entry: nest it in its own `<list type="gloss">` inside the parent
  `<item>`, one nesting level per visible indent level, never flattened, never
  invented.
- **`<table>`** only for genuine multi-column tabular data with column headers —
  not for the term/gloss pattern above, even where it uses dot leaders.
- If the shape matches neither cleanly, default to `<p>` and comment the
  ambiguity rather than forcing a structure onto it.

### Glosses, and linking them to their terms

`<gloss>` associates with its `<term>` by an explicit `@target`, not by sitting in
the same `<item>`. Containment is not enough and demonstrably fails: `1-100`'s
item 4 holds two term/gloss pairs, and nothing about the nesting says which
belongs to which.

    <term xml:id="term-1-100-1" xml:lang="ckt" resp="#llm">Teñ-uweˊlᴇ</term>
      (<gloss target="#term-1-100-1">“quite black” [chestnut brown]</gloss>)

Link every glossed term, so the corpus is uniformly queryable rather than linked
only where containment happened to be ambiguous. `harness lexicon --glosses` is
what reads them.

**A gloss may also be supplied rather than printed.** Where the surrounding prose
explains a form the page does not gloss in place, you may write one — but it must
say so, because it is authored English rather than transcribed English:

    <gloss type="supplied" resp="#llm" target="#term-1-100-1">…</gloss>

`type="supplied"` **requires** `@resp`; a gloss with no `@type` is transcription
and **must not** carry one. Two states, each marked by a *present* attribute, so
neither is reachable by omission.

`@resp` means something different here than on a Tier-1 span: "a model authored
this English sentence", not "a model read this glyph off the scan". The firewall's
subject is glyph identity and does not reach English. What does carry over is the
**origination** rule: a supplied gloss is drawn from *this page's prose* or from
book-internal apparatus, never from world knowledge about Chukchi.

### The frame a gloss list shares — write it once, on the list

A gloss list's entries routinely share a frame their glosses never repeat, because
the prose introducing the list already said it. `1-100` announces "the following
colors of reindeer-skin" and then glosses `Qeˊñu` as `“white mixed with brown”` —
which, standing alone in a dictionary, says nothing about what is white.

Write that frame **once, as a supplied `<head>` on the list**:

    <list type="gloss">
      <head><supplied reason="context" resp="#llm">of a reindeer</supplied></head>

Never into the individual glosses. Twenty-seven copies of one fact is twenty-seven
things to drift, and `harness lexicon --glosses` resolves the head for every entry
anyway — it is what puts the `scope` column beside each gloss.

- **A continuation list inherits and must not restate it.** `1-101`'s colour list
  carries no head; the scope resolves back through the `@prev` the seam wrote. If
  you find yourself typing the same frame onto a second page, the link is doing its
  job and you are undoing it.
- **Same origination rule as a supplied gloss**: from this page's prose or from
  book-internal apparatus, never from world knowledge. And it is a judgement, so it
  is `#llm` — `1-100`'s lead-in says *reindeer-skin* while the entries gloss leg
  stockings and a neck pattern, i.e. the animal; choosing "of a reindeer" over the
  print's own phrase is exactly the sort of call that has to stay findable.
- **`@reason` is required and closed**: `context` for a frame the surrounding prose
  supplies, `ellipsis` for a word the sentence itself omits. The gate errors on
  anything else, and on a `<supplied>` with no `@resp`.
- Most gloss lists need none of this. A list whose glosses stand on their own gets
  no head, and that is the ordinary case.

# Language spans and the firewall — read this twice

Non-English content splits into two tiers, treated differently, because the risk
differs by language and not just by "is it English".

## Tier 1 — the Americanist apparatus

Chukchi's firewall, because these are transcribed in the same ambiguous phonetic
notation the whole project exists to protect. Closed set:

- **`ckt`** — Chukchi. The default. Use it unless the English *immediately
  surrounding the span* names otherwise — not the chapter, not the section, the
  actual sentence the form sits in.
- **`kpy`** — Koryak. Only when the adjacent English names Koryak specifically.
- **`ypk`** — Eskimo/Yupik. Only when the adjacent English names Eskimo or Yupik.
  The only code for this family in the set: the book does not distinguish Naukan
  from Central Siberian Yupik anywhere checked so far, and inventing that
  distinction because ISO 639-3 offers `ess` and `ynk` would assume precision the
  source does not carry.

There is **no section- or chapter-level signal for any of this**. A comparative
citation can appear anywhere the author finds it useful. The Koryak gloss for
"grandmother" on p. 538 sits inside "System of Relationship", nowhere near
anything labelled Koryak — the signal was in the sentence ("belongs rather to the
Koryak language"), not in where the sentence fell. Do not weight the default by
chapter or section at all. If the immediate sentence names no language, the span
is `ckt`, full stop. If you are genuinely unsure after reading the local sentence,
that is an `<unclear>` case, not a guessing-with-more-steps case.

## Tier 2 — standard European languages

Russian, Latin, French, German and others as they turn up. Use the ordinary code
with normal confidence. This tier is **not closed**: these orthographies are not
ambiguous the way Americanist notation is, so misidentifying French as Latin is a
low-consequence error, not a firewall breach.

**Correction authority.** Fidelity matters for idiosyncratic transcription of
languages you do not know; Tier 2 is by definition languages you do.

- Confirmed OCR slips in Tier-2 text are corrected under the same rules as English
  prose below.
- **Russian carries a modernization licence.** The book is 1904–1909, so all its
  Russian is pre-1918 orthography. You may replace it with post-reform spelling
  **provided** (a) the word is glossed or its sense is explicit in the surrounding
  English, and (b) you are certain of the meaning. If either fails, reproduce what
  is printed; unmodernized Russian is not an error and needs no flag.

  The closed list, because you cannot decide to modernize a character you did not
  notice:

      і U+0456 -> и      decimal i; before a vowel or й (Россія)
      ѣ U+0463 -> е      yat; frequent — хлѣбъ, бѣлый, дѣло
      ѳ U+0473 -> ф      fita; Greek loans only — ариѳметика
      ѵ U+0475 -> и      izhitsa; church-Greek only, very rare — мѵро
      ъ U+044A -> ---    hard sign, WORD-FINAL ONLY (лахтакъ -> лахтак)

  Uppercase: U+0406 U+0462 U+0472 U+0474 U+042A. The hard sign is the one to be
  careful with — U+044A is live modern Russian as a separator, so only its
  word-final position is pre-reform and only that position is dropped.

  **Three are cross-script lookalikes** — і against Latin `i`, ѵ against `v`, ѳ
  against `o` — and і/`i` are the same letterform in a serif face. Inside a
  Cyrillic word the Cyrillic codepoint is always right; a Latin letter mixed into
  Cyrillic is a defect no grep catches, since the lookalike census is scoped to
  Tier-1.

  The draft cannot help: CATMuS lost every one of the 29 Cyrillic characters on
  the page where this was measured. Russian is read off the image exactly as
  Tier-1 is, even though it carries no `@resp`. What Russian has that Tier-1 lacks
  is a competent reader downstream and a dictionary — which is why the licence
  exists at all, and why it stops at "certain of the meaning".
- **Latin stays as printed.** Era-standard usage and the author's idiosyncrasies
  are not mistakes. Latin excerpts translating brief passages are doing the
  era-standard job of moving explicit material out of English for propriety —
  expect this around ch. XV. Preserve exactly, do not translate, do not flag.

## The firewall, restated wide

Inside **any** element bearing a Tier-1 `xml:lang` — `<foreign>`, `<term>`,
`<unclear>`, anything a later pass wraps a form in — what you emit is a **proposal**
and is marked as one. It is never an adopted glyph identity, no matter how
confident the reading or how clean the image.

**"Proposal" describes its authority, not the care owed to it.** It is not a
licence to guess, to approximate, or to leave a mark for someone else to catch.
The standard is every mark on the form read and accounted for, character by
character, at magnification where the letterform is small or the mark sits under
a descender.

There **is** a repair pass — that is what marking the span `#llm` is for, since a
query over the corpus returns precisely the forms awaiting a human. But it finds
the span, not the error. Repair is one editor back at the raster with no second
witness available: the recognizer reads none of this notation, there is no
dictionary and no fluent reader to check a Chukchee form against. The pass is
single-witness and paid for in the scarcest resource on the project, and every
avoidable slip is a line of it spent for nothing.

The slips that survive are the ones with no internal signal. A dropped mark inside
an otherwise plausible form reads as correct in the TEI, so nothing draws the eye
to it. `1-074` is the measurement: two dropped U+0323 under a `g`, both missed by
the reader's own second look, both caught only by the editor at the page. Where
you cannot settle a letterform, `<unclear>` is the answer; the likelier form never
is.

**The firewall is a rule about hierarchies of provenance, not about matching an
upstream file.** It used to be stated as "reproduce the draft's characters
exactly", and that was wrong in a way worth knowing, because it reads as the safe
formulation. Obeying it literally meant emitting Tier-1 spans you could see were
wrong. Both it and the validator check that enforced it are gone.

## Provenance is an attribute, and it is not optional

Every element bearing a Tier-1 `xml:lang` carries `@resp`. Three ranks, strictly
ordered:

| `@resp` | rank | meaning | who may create it |
|---|---|---|---|
| `#ed`  | ratified | a human keyed or confirmed this against the page; an ADOPTED glyph identity | a human, by an explicit act |
| `#llm` | proposed | a model read this off the page image; a reading, not an identity | this pass |
| `#htr` | unexamined | recognizer output nobody has looked at | the import that made the draft |

**You emit `resp="#llm"`.** Always, on every Tier-1 element, `<unclear>` included,
including a span you consider beyond doubt, including a bare ASCII form with no
inventory glyph in it. You never emit `#ed` and you never emit `#htr`.

Emitting `#ed` is precisely the promotion this firewall exists to prevent, and it
is the one breach that is mechanically detectable rather than a matter of
judgment — so the gate detects it. A Tier-1 element with **no** `@resp` is an
error too, and the more dangerous of the two: to anything downstream that does not
check, an unmarked span is indistinguishable from a ratified one, which is the
fluent-nonsense failure with the error signal filed off.

Rank only ever rises by a human act. Nothing this pass does moves `#llm` to `#ed`.

**`@resp` and `<unclear>` are orthogonal.** `@resp` says who read it; `<unclear>`
says whether the image decided. So `<unclear xml:lang="ckt" resp="#llm"
reason="…">` is the ordinary case for an ambiguous letterform, and a confident
reading is still `resp="#llm"` without `<unclear>`. Certainty is not authority.

Tier-2 spans do not require `@resp`. The asymmetry is the point of calling this a
hierarchy: a misread Russian or Latin word is an ordinary error any reader of the
language catches, whereas a misread Chukchee form is unfalsifiable.

## `@facs` — flagging a span worth a second look

Set it on any Tier-1 element whose reading took real deliberation — a hard
letterform, a mark you went back to the image to settle — pointing at the
`line_id`(s) in `ocr_lines` you actually read from: `facs="#eSc_line_e5fa4af8"`,
or several ids for a reading checked against how the same mark prints on a
neighbouring line. It turns a flagged span into a one-command raster lookup:
`harness zoom PP-NNN --only <index> --from gt/ocr`.

Reserve it for spans that earned it — a `@facs` on every span stops meaning
anything. It is a pointer, not a rank: it never substitutes for `@resp`, and
citing a line does not make a reading more authoritative. Never invent a
`line_id`; omit `@facs` rather than guess.

## What the rule forbids

- **Promotion.** A reading of yours may not be presented as ratified.
- **Origination by inference.** You do not derive a glyph from what the notation
  "should" contain, from a form on an adjacent page, from `foreign_terms_nearby`,
  from `prev_tail`, or from any corpus-wide pattern. Only the image in front of
  you, plus book-internal apparatus — the p. 10 key, the List of Illustrations,
  the printed ToC — which **is** evidence and binds.
- **Normalization.** You do not correct a Tier-1 spelling, regularize a mark, fix
  what looks like a typo, or harmonize a variant. If you notice a possible
  variant, note it in a comment.

## Small caps and hyphens, two regimes each

**Small caps.** Inside Tier-1 spans, `ᴀ ᴇ ɪ ʟ` are **characters** of the notation
— the schwa class and a lateral sort — reproduced at their codepoints, never
case-folded, never rendered as `<hi>`. The word-medial-caps detector is the alarm
at exactly this boundary. In English prose, small caps are rendition only:
normalize silently to ordinary case, or `<hi rend="smallcaps">` where the emphasis
is evidently deliberate. Never let one regime leak into the other.

**Hyphens.** In English and Tier-2 text a line-end hyphen is a printing artifact:
join the word and discard it, silently. Retain a hyphen only where it is evidently
lexical. Inside Tier-1 spans the hyphen is a **sort** (U+002D, the connector) and
forms essentially never break across lines: never join, never discard. A line-end
hyphen inside a Tier-1 span is an anomaly — reproduce it and comment.

## Codepoint hygiene, two scopes

In English and Tier-2 prose, **reproduce the print, curly quotes included**. The
book sets them, nothing there is load-bearing, and normalizing would discard a real
feature of the setting. What stays forbidden in prose is the set with no
legitimate English use at all: U+00B4, U+02BC, U+02BB, U+2010.

**One bounded exception**: the book sets French spacing, a thin space before `;`
and `:` (`purpose ; but`). Key English spacing — `purpose; but`. It is the only
such override and it is narrow: a thin space has no lexical content and would put
a space inside a token for every tokenizer downstream, whereas a curly quote
carries a distinction the notation uses. This licenses nothing else about spacing.
An interword space that is present is keyed; `i. e.,` keeps its space.

Inside Tier-1 spans, U+0027 and U+002D are the only apostrophe and hyphen, because
there U+0027 **is** the spirant and pause mark. A curly quote inside a Tier-1 span
is a lookalike and lands in the WORKLIST for a human ruling — do not resolve it
yourself, and do not import one from the draft.

# English prose — where fixing is licensed

Confirmed OCR slips in ordinary English may be corrected directly, no `<unclear>`
needed, **provided** (a) the fix is confirmed against the page image, not merely
inferred from the draft looking wrong, and (b) the corrected reading is not itself
in doubt. A dropped quote or bracket flagged by `balance_flags` may be restored
**only** if the image confirms it — the parity check tells you where to look, not
what was there. If you cannot confirm a reading against the image, leave it and
flag it in a comment. Do not guess at English any more than you would at Chukchi.

## At a page edge, never complete, capitalize, or punctuate

The licence above reads as permitting exactly this, and it must not. A page
opening lowercase looks like an OCR slip; a last paragraph with no terminal stop
looks like a dropped period; and both "fixes" are confirmable against the image
*in the licence's own terms*.

**The first character of the page's first element and the last character of its
last element are transcription, not prose to be repaired.** They are the seam's
own text witness, and completing either destroys it invisibly and unrecoverably —
which puts it in the same class as a dropped mark inside a plausible form. `1-100`
opens `come to the herd`, and it stays that way.

No balance flag, no capitalization instinct and no confirmed reading licenses
touching them.

# Structural ids

You mint `xml:id` on elements something points at. The scheme is
`{kind}-{PP-NNN}-{ordinal}` — `term-1-100-4`, `list-1-100-1` — and `harness ids`
checks it, so it is a rule the gate enforces rather than one you have to be
careful about.

- **Kinds are `term`, `list`, `table`** — exactly what something can point at.
- **The ordinal is a position, not a counter**: the element's 1-based index among
  *all* same-kind elements on the page in document order, whether or not that
  element carries an id. So ids are sparse, and adding one never renumbers
  another.
- **The ordinal is not the printed item number.** `1-100`'s item 4 holds two
  `<term>`s, so its terms are `term-1-100-4` and `term-1-100-5`, and item 5's term
  is `term-1-100-6`. Count elements, not labels.
- **No id without a referrer** — an in-file `@target`, or a `@prev`/`@next` a seam
  wrote. Do not mint in advance.
- **An id names the page it lives on.** `prev_tail` hands you the previous page's
  markup with its ids in it; copying one in is an error the gate catches.

`harness ids PP-NNN --pair` links glosses to terms where containment decides, and
refuses where it does not — useful for a dense gloss list, but the ambiguous items
are yours to write.

**These ids are stable within a page file's current version and nothing outside
the corpus may cite one.** Ordinals move when content is inserted. Corpus-stable
identity is a different scheme and does not exist yet.

# Self-check before emitting

- Is `<pb n=>` the printed folio as it appears on the page, checked against
  `expected_folio` where non-null, with a comment on mismatch? If the page carries
  no printed folio, is it `<pb/>` with no `@n`?
- Did any running head or series title survive into the output? (Always no.)
- Did I complete, capitalize or punctuate anything at either page edge? (Always
  no.)
- Did I modify a single character inside any element bearing a Tier-1 `xml:lang`?
  Case-fold a small cap there? Join or discard a hyphen there? (All: always no.)
- Does every Tier-1 element carry `resp="#llm"` — `<unclear>` included, confident
  spans included?
- Does English/Tier-2 prose reproduce the print's quotation marks, curly ones
  included, with English spacing before `;` and `:`?
- Every Russian modernization: was the word glossed or its sense explicit, and the
  meaning certain? If either was doubtful, did it stay verbatim?
- Every `<milestone>`: is its `@n` copied verbatim from a `toc_window` id, with no
  title text, invented number, or extra attribute?
- Every Tier-1 `xml:lang`: is it `ckt` unless the *immediate sentence* names Koryak
  or Eskimo/Yupik?
- Does every heading-shaped run end up as a milestone, a `<head>` on a local
  list/table, or an explicit comment — never bare, never silently dropped?
- Is every footnote anchored at its marker with no space before it, and every
  orphan foot-text a `<note>` without `@n` plus the fixed comment?
- Does every `<figure>` point at a supplied zone id, with orphans commented?
- Does every `@facs` point at a real `line_id`, and only on spans that earned it?
- Does every `<gloss>` carry a `@target`, and every supplied one a `@resp`?
- Every `<supplied>`: `@resp` and a declared `@reason`? A frame shared by a gloss
  list written once on the list, and never restated on a continuation?
- Is there any `<lb/>`? Any hand-written `@part`/`@prev`/`@next`? (Always no.)
- For every `detector_flags` entry: did I confirm-and-fix against the image, or
  leave it untouched and note why?
- Would running this again on the same input produce a byte-identical file?

# Questions and reservations

You are encouraged to ask, and required to in these cases:

- Any unresolved-comment situation above — a heading with no ToC match and no
  list/table, an expected milestone not found, a content shape fitting neither
  pattern, a likely foreign-term variant.
- A folio disagreeing with a non-null `expected_folio`. The printed folio wins,
  but the mismatch is still a question.
- A folio you cannot read at all.
- A seam you cannot settle from `prev_tail`, the opening text and the indent
  together.
- Anything where these rules would have you guess.

Ask **batched, at the end of a drafting pass**, not one interruption per doubt.
Emit the file with the comment forms in place, then present a numbered list of the
open comments with your reading of each and what you would need to resolve it.
Apply the answers, note each resolution inside the relevant comment (`resolved:
<answer> per editor`), re-validate. **A reservation the human has not answered
stays a comment** — durable in the file — never a silent decision.

# What you never do

- Answer your own question by picking the plausible option. Fluent nonsense is the
  failure mode that matters; "unresolved" is a valid deliverable.
- Write `@part`, `@prev` or `@next` by hand — `harness seam` writes those, from
  the page that holds both witnesses.
- Mint an entity id, or emit `<lb/>`, or a `<div>`.
- Edit anything under `ocr/`, `scans/`, `gt/`, or `data/`.
- Copy `expected_folio` into `<pb n=>` because it was supplied.
- Copy a Tier-1 form or an `xml:id` out of `prev_tail` or `foreign_terms_nearby`.
- Proceed past a FAILing validator. If you believe the gate itself is wrong, that
  is a question for the human, not a licence.

# Session hygiene

One page per task. After a page passes, its questions are settled and its seam is
recorded, commit and clear context before the next — a fresh read of each page is
a feature; carried impressions from the previous page are not context, they are
contamination.

    git add tei/chukchi-PP-NNN.xml && git commit -m "tei: PP-NNN collation pass"

What *does* carry across pages carries through the committed file, not through
your head. `harness ledger` folds every committed `<pb>`, milestone and seam mark
into the table the next page's context is built from, and `harness seam` wrote
into the previous page's file directly. **So the commit is the handoff.**

Working in scan order gives each page a live `expected_folio` and a resolvable
seam. Jumping around gives nulls until the gaps fill, and `seam` will refuse. Both
are fine; the first is faster.

# What this pass deliberately does not do

- **Resolve open F-numbered flags** from the keying-spec residue (F4 lateral and
  rhotic sorts, F10). Those are corpus-wide policy questions, and a per-page pass
  resolving them independently would produce 730 inconsistent answers.
- **Produce figure zones.** A separate headless pipeline does; this pass only
  anchors `<figure>` at first textual reference against zones it is handed.
- **Mint entity ids or corpus-stable ids.** Persons, places and taxa are later
  passes over finished TEI.
- **Link a note across a page seam.** Unattested, and deliberately unresolved.
- **Require Chukchi ground truth to exist.** It runs on whatever draft is current.
