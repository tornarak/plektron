# Decisions and their reasoning

The record of what was settled the hard way — kept intact because the
reasoning is what stops a rule being "fixed" by someone who does not know
why it exists. Headings kept verbatim so citations resolve. Nothing here is
a rule a pass executes; those live in `CLAUDE.md`, the skills and the specs.

## What the firewall is not

**What the firewall is not** — stated because it was stated the other way for most of
this project's life: it is *not* "reproduce the draft verbatim". That version enforced
the canonicity of whatever `ocr/` happened to hold, and so was **unsatisfiable** over
real recognizer output (CATMuS emits 0% of the inventory, so every correct TEI failed)
and a **tautology** over a model's own reading, comparing a file against its own source
and rendering the result as a verified PASS. Removed from `validate.py` and from
the collation skill; the comment at the old check's site (`validate.py`, above
`RESP_RANKS`) records why, and `context.py` still carries what fed it.

## The ground-truth loss

Rebuilt and closed, but the design fault it exposed still governs the store layout.
An archive extraction over `gt/ocr/` replaced 17 of the 20 hand-keyed pages with
~1977-byte export shells, and there was no copy anywhere in the repo. **The cause
was that a file's role — machine output or human ground truth — lived only in the
directory name**, while `ocr/` symlinks into `gt/ocr/`, so anything written into
one wrote through to the other. Nothing in an ALTO says which it is: the
`Description` block of a hand-keyed page and of an empty shell are byte-identical.

Hence the current rule, which is the whole lesson: **`gt/` is what a human has been
through, `ocr/` is only a view over it, and nothing writes through a view.**

The rebuild ran as `/rebuild-groundtruth PP-NNN` and its skill remains normative
for the pass — which is now a *revision* loop rather than a restoration one, since
every page has text. `restore` reports which of the two it did.

The three line invariants that came out of the rebuild — `_lines_from_alto` drops
empty lines, a line polygon can exclude printed text, and `index` is an identity
rather than a position — bind anything touching lines and are stated in full in
`harness/README.md`'s caller invariants.

## The ground-truth rebuild, and what 2-030 settled

**The ground-truth rebuild is finished, and the store has outgrown it.** All 20
pilot pages carry text, and `gt/ocr/` now holds **30** — the balance restored
from `mz/ocr/` predictions rather than from eScriptorium shells, which is the
standing route now that the shells are gone. **The reading half now fans out to
a subagent per page** (`.claude/skills/rebuild-groundtruth/dispatch.md`), each
stopping at a normalized `proposal.json`, with one `harness ocr review` server
over the whole batch; `2-045`–`2-047` and `2-031`–`2-036` went that way.
**`2-030` was the one page with ground truth and no `proposal.json`**, and is
not any more — it was adjudicated by the eScriptorium route before the review
loop existed, which left it unrevisable: `restore` refuses a decision set that
does not cover every line, so there was no patch path and the whole of its text
predated every detector now in the loop. It was also the densest Tier-1 page in
the pilot set (fig. 213's 27-line gloss list), i.e. the worst page to have
unexamined. Read through in 2026-08 and corrected in six places. **Every page in
`gt/ocr/` now has a proposal**, so the state is closed rather than merely rare —
but the shape that produced it is not, and a `gt`-with-no-proposal page is
invisible to `ocr pages`, which reports the store rather than the review
directory.

What that page settled is worth more than its six corrections: **`gt/ocr/` and the
caption text are not independent witnesses on a figure page.** This
ground truth was hand-corrected from CATMuS and the caption block descends from
the same recognizer pass, so three commas the machine invented sat in both
corroborating each other, and only a fresh raster read separated them. Nothing
in either file records the shared ancestor. Same fault as the verbatim firewall,
`review`'s span diff and `train score zones`'s `unseen` row — two inputs that turn out
to be one — arriving through provenance nobody wrote down.

What that measured is worth carrying: **the residual error classes are
`keying_spec.md` §5.1's dropped `g̣` and §5.2's `ɪ`-as-`i`, they survive readers who explicitly report
checking them, and the only safeguard that does not depend on a reader
remembering anything is distributional** — `harness lexicon marks` puts `g̣` at
93.9% of Tier-1 `g` and `ɪ` at nearly 2:1 over `i`, so a page against the grain
is visible without opening a scan.

**That claim is now measured rather than asserted, and computed rather than
eyeballed.** `harness ocr corrections` aggregates what adjudicators actually
changed across all 29 reviewed pages: scoped past 2026-07-31 the only class
recurring across pages is `i`→`ɪ`. And `harness proposal marks` runs the
comparison `dispatch.md` used to ask a coordinator to do by eye — pass a whole
pass's refs, since most pages carry a handful of Tier-1 terms and one page is
rarely a sample worth a verdict. Its `scope: ALL` row against the per-ref rows
is what separates **one reader's slip from a lean every job shares**, and the
second is the dispatch prompt or the keying spec rather than anybody's reading
— the one finding nothing else in the loop can reach.

Two of its three arms are deterministic and also run inside `harness proposal
check`, so a reader meets them on its own page. Its prior is leave-one-out
(after `restore` a page's gt **is** the adjudicated descendant of its own
proposal, so including it would be the two-witnesses-that-are-one collapse in
a fourth place) and drawn from density-selected pages, which every report
states in `prior_note`.

## The 1-100/1-101 seam

`1-100`/`1-101` are the corpus's only **adjacent** pair, and adjacency is what makes
them worth more than two pages. The seam between them is a live run-on: `1-100` ends
`<item n="14">`, `1-101` opens at 15, and a `<list>` is not fragmentable, so `harness
seam --continues` linked `list-1-100-1` ↔ `list-1-101-1` rather than writing `@part`.
That is also the first time the ledger's `boundary` column has held a value other
than `unknown` — and it reads `open` off `@next`, which is exactly what a
`@part`-only derivation would have missed.

## Dropped lines

**The segmenter drops whole printed lines, and nothing text-level can see it.**
Whatever text is present is correct, so no lookalike grep, lexicon miss, mark
licence or CER figure disagrees with anything — the page simply has less on it than
the paper does. `1-053` reached restored ground truth missing a two-line closing
paragraph, found only because the footnote-marker check reported a marker whose
body reference did not exist.

`harness ocr gaps PP-NNN` is the detector: row-wise ink off the raster, masked
by the existing line boxes *and* by `gt/fig/` zones, contiguous bands reported with
measured geometry. It found **three** of the 20 restored pages and was silent on
the other seventeen. All three are now repaired and the corpus reports **zero**:

- `1-053` — two body lines, a whole closing paragraph. Its `¹` body reference was
  on one of them, which is why the footnote check saw an unpaired marker;
- `1-048` — the centred `CHUKCHEE.` heading, on a page that had been revised and
  restored the same day without anyone noticing;
- `3-005` — the centred `AFFINITY.` heading, 23 px of ink and the smallest
  confirmed dropped line in the corpus.

**The two headings are a class, not accidents** — short, centred, small-caps
section headings — so expect the same across the remaining 812 pages. Figure zones
must be masked or every illustrated page reports its own artwork (`3-006` gave 12
bands, `2-030` two; both go to zero). It is report-only and deliberately **not**
folded into `normalize`: reading rasters costs ~0.19 s/page against that gate's
0.83 s for the whole corpus, so it belongs in the per-page loop and in deliberate
sweeps. `--blot` is the visual counterpart — the page with every line box and zone
painted out, so what remains is uncovered by construction and no threshold can
hide it.

Repairing one *was* `harness ocr adopt-gap`, which appended an empty `TextLine`
to `gt/ocr/`. It is retired, and the reasoning is worth keeping because the
detector outgrew its repair.

**2026-08-05 — the census, and why the repair route changed.** Fixing the ink
detector's blind spot (it masked *rows* rather than boxes, so a line missed
horizontally inside an accounted-for row band was invisible) and sweeping the
book turned three known cases into dozens: ~35 unsegmented folio numerals, ~9
printed rules, a handful of unknowns. That is a different problem from the one
`adopt-gap` was built for.

Three things were wrong with it at that scale, and only the first is about
convenience. It resolved its target to `gt/ocr/` explicitly, so it could not run
on the ~690 pages holding only machine output — and a dropped folio matters most
exactly there, because `tei context` turns the folio into the page's `<pb n>`
witness and nothing infers a page number. Its full route (adopt → review →
restore) was a whole-page adjudication cycle bought to key one marginal numeral.
And it was used **once**, on three pages, in its entire life: the orchestration
doc that should have invoked it never mentioned it, so the route depended on a
human remembering this file.

What replaces it is a store and an editor. `gt/lines/` holds boxes a human drew
over ink the segmenter left unboxed, in raster coordinates, folded into every
page's lines by `lines.page_lines` — so a correction is reachable whichever store
answers for the page. `harness ocr edit` is where a human draws them, or rules
that a band is not a line at all; it draws and never keys, because the text of a
recovered line is adjudicated in `ocr review` and written by `restore` like any
other line's. The three lines `adopt-gap` did create stay exactly as they are:
ratified, adjudicated ALTO. The mechanism died; the data stands.

The same census forced the two ink checks apart. `zones check --ink` asks whether
ink is inside any zone; `ocr gaps` asks whether *in-zone* ink is inside any line.
They had been sharing one exemption file, so a band ruled "scanner smudge" while
zoning — a claim about what the zoning need not cover — also stopped the line
check from ever reporting that strip again. A folio dropped inside a
`RunningTitleZone` is what that hid. One file each now, overlaid and never
merged; `harness/corrections.py` carries the argument.

## A detector census over "the 20 GT pages" was really a census over two

**Consequence worth stating because it reads as success: a detector census over
"the 20 GT pages" was really a census over two.** At the start of the rebuild, 17
of the 20 were empty shells (11 still are), so they reported zero flags because
there was nothing to flag, not because they were clean. Any baseline taken before
a page's own rebuild is worthless for the same reason — `1-074` went from 0 flags
to 15 `inventory_glyph` the moment it was restored.

## The error class that survives review

The error class that survives review is the one with no internal signal. A dropped mark
inside an otherwise plausible form reads as correct in the TEI, so nothing flags it and
only re-collation against the page finds it. `1-074` is the measurement: two dropped U+0323
under a `g`, neither caught by my own re-read, both caught by the editor. "Don't normalize"
therefore means *read harder*, not *worry less* — an unexpected form sends you back to the
raster to settle what is on the paper, never to file the oddity as authorial and move on.

## What the detectors learned

**The cut is shared and happens once, at the tokenizer.** `detect_all` used to
publish the raw whitespace-delimited token and strip `EDGE_PUNCT` only inside
the one check that needed it, so a flag reached the collation payload as
`"mêˊmêl),"` — the printer's parentheses glommed onto a Tier-1 form in the one
field a reader acts on. It sent `proposal codepoints` and a raster look after
characters that are not in the word, and it meant the string did not compare
equal to the *same form* in `tier1_terms`, which is what let one page's evidence
reach the pass twice in two spellings. U+0027 survives the cut deliberately: it
is the spirant mark, not punctuation.

**`tei context` then suppresses a flag on a token that page has already
ratified**, on the `(line, token)` pair rather than the token alone, so
`detector_flags` is the *residue* — Tier-1 material with no adjudicated reading
behind it, plus the ordinary English triage. `1-151` goes 4 flags → 0. What
survives on a ground-truth page is the floor's own blind spot, which is the
right thing for a triage list to hold.

**That exposed `apostrophe_adjacency` as almost pure noise**, and the fix is the
shape of every filter here. With Tier-1 forms no longer flagged, all 31 surviving
hits over the ground-truth corpus were ordinary English possessives — `wife’s`,
`Krause’s`, `reindeer’s`. But **position cannot decide it**: `keˊlet` mis-keyed as
`ke’let` puts U+2019 between two lowercase ASCII letters, exactly where a
possessive sits. So `english_genitive` requires the shape *and* a stem the lexicon
**positively knows** — not `not _unknown_word(...)`, which passes anything under
four characters and would clear `ke’let` and `kun’s` alike. It fails closed with
no lexicon, and it declines the possessive on an unknown proper noun rather than
guessing. The corpus now reports **one** such flag, `2-045`'s `kun’s`, the tail of
a broken `Kereˊtkun’s` — a Tier-1 stem taking an English genitive, which is
precisely what a shape-only rule would have thrown away.

**The payload's flags now read the joined text**, which both `lexicon` arms have
done since 2026-08-03; this arm builds its own draft and was simply never
included, so it went on reporting `Chuk`/`chee`, `Penin`/`sula`, `direc`/`tions`
as words no dictionary knows — 82 flags → 44 over the ground-truth corpus. **The
draft itself stays line-per-line**: the model reads the raster beside it, and a
draft that silently reflowed would stop being checkable against the page. Safe
only because `index` is carried alongside rather than being a position in either
list. Emptied lines drop with their index, which also keeps `_balance` seeing one
paragraph per page.

**And that surfaced a live hazard in `tier1_terms`: a half of a broken word was
being offered as a form.** `1-101` prints `Torwaˊwaq` as `(Tor-` / `waˊwaq)`, so
the list held `waˊwaq` — a whole token on its line, ratified, and half the word.
A pass naming it gets a truncated form filled in and stamped `#gt`, and every
guard passes, because it really is a token in this page's ground truth: the same
boundary the whole-token check protects at one end (`Qeˊñ` ⊂ `Qeˊñu`), broken at
the other by the compositor's measure. A term is now offered only if it survives
the join as a whole token. **The rejoined form is not offered in its place** —
`Tor-waˊwaq` is a string no line holds, and whether that hyphen is the word's or
the printer's is the ambiguity the join preserves rather than decides. So a
broken form gets no handle and arrives as a flag on the joined text, which is
the correct answer: read the page. Eight forms across the store are in this
state.

## Licence and bibliographic witnesses

**Licence: two, because this is not one work.** The transcribed text is **CC0** —
a faithful transcription of a 1904 book carries no fresh copyright (EU DSM Art. 14;
US law has never protected slavish reproduction), so licensing it CC BY would assert
a right the edition does not hold, which is the provenance overclaim pointed at the
law instead of at the glyphs. The apparatus — `loi.json`, `toc.json`,
`authorities.json` and their research, the TEI structure, the adjudications, the
annotation layer — is original editorial work and is **CC BY 4.0**. Scopes are
stated on each `<licence>`; where a reuse cannot separate them, treat it as CC BY.
`harness tei header` errors on a settled `@status` granting no `<licence>` at all, that
being the one licence state that reads as finished while saying nothing.

**Bibliographic detail in the header was read off the rasters, and the witnesses
disagree.** The title page (`1-005`) gives the Jesup series as Volume VII and names
no Memoirs volume; "Volume XI" comes off the parts' archival sheets and off the AMNH
catalogue. Both series statements are recorded, since dropping either makes a
citation in it unresolvable. `@source` in the header points at the catalogue record,
`@resp` only ever at a model's reading of a raster — the rank machinery is about
reading pages and says nothing about a catalogue's authority.

## The reading-discipline record (the reader contract's R-items, formerly keying_spec.md §5)

The `§5.n` numbers below are the spec's old reading-discipline classes. On
2026-08-21 that section left the spec for the reader contract, as R1–R10, and §5
became the priors; the map is §5.1 → §5.1/R2, §5.2 → §5.2/R2, §5.5 → R4,
§5.9 → R5, §5.11/§5.12 → R7. Moved here 2026-08-05, when §5 was compressed to
rule → instrument → record per class. The reason for the move is itself a finding: the 1-039…1-044 reader batch
showed that a class restated at length in the system prompt is not thereby
checked — one reader quoted §5.1's 93.9% prior *and* named `vaˊɪrg̣ɪn/vaˊɪrg̣ɪt`
as the documented trap in its own note, then bare-keyed the suffix twice on the
page it was writing about. Emphasis had demonstrably failed; the spec now names
each class's *instrument* instead, and the narratives that established each
class live here, intact, because they are the evidence the compressed register
lines point at.

**§5.1, the bare `g` (five occurrences and counting).** `1-074` is above ("The
error class that survives review"): two dropped U+0323, caught only by the
editor. `3-004` restated it at scale: `-g̣ɪ`/`-g̣ɪn`/`-g̣ɪt` are common
noun-forming suffixes, not merely a kinship-vocabulary pattern (`va'ɪrg̣ɪn`,
"spirit"), and that proposal bare-keyed the suffix across nearly every headword
— the single largest error class on the page. `3-005`, the fourth occurrence,
read several `-mgɪn`/`-mgälqäl` clusters as bare `g` after a genuine 4× look
that seemed to show no dot — and was still wrong on more than one, per the
human reviewer: the 90% figure is a real prior to weight against your own
raster impression, and a "no dot" reading must clear a higher bar than a "dot"
reading precisely because the base rate runs the other way. The fifth
occurrence was the 2026-08 five-reader batch: five drops across three pages
(`2-033`: `Attɪˊg̣ɪtkɪ` ×2 and `vaˊɪrg̣ɪt` ×2; `2-035`: `Čig̣eiˊ-veˊem`),
including the prior-quoting reader above. What finally worked was the contrast
method — both `2-033` and `2-035` corrections came from holding the doubtful
`g` against a plain English `g` on the same line (`danger`/`ger.`,
`representing`) after their readers had looked hard and got it wrong. A sixth
instance, `1-042`'s `Nɪg̣čɪˊen`, was caught at adjudication in 2026-08 by
`proposal marks`' distributional arm (g-dot at 0.0% across 3 types against the
corpus prior) after four clean mechanical gates had passed the page.

**The corrections themselves, 2026-08 onward.** Moved out of `keying_spec.md`
2026-08-21, when §5.1 had accreted sixty lines of case history for a rule with
two clauses. The rule is a count; these are what the count was built from.

*Record.* The most-corrected class in the project's history: `1-074` ×2,
`3-004` (nearly every headword — the page's largest error class), `3-005`,
`2-033` ×4, `2-035`, and `1-042` at adjudication — five restatements
survived, including a reader that quoted the prior and the trap word, then
bare-keyed it on the page it was writing about. Both `2-033` and `2-035`
were corrected to dotted after 4× stares had failed; `1-042`'s was caught by
`proposal marks` after four clean mechanical gates. Then `2-104`
(`vaˊɪrgɪn`) and `2-117` (`vaˊɪrgɪn`, `ɪˊê-mñêˊɪrg̣ɪn`) in the chapter-XIV
pass, all three overturned the same way. Each of those corrections was
credited at the time to a contrast crop; §5.13 says why that credit was
unearned — every one of them moved toward the prior, which is the only
direction the method has ever been right in. Those
readers did everything else right — refused the ratified handle, flagged the
line — which is why the rule above is now a count and not an exhortation:
the disciplined disposition still produced the wrong character. Fifteen more
followed across five part-3 batches (`3-004` ×2, `3-005` ×3, `3-011`,
`3-017` ×3, `3-018`, `3-023`, `3-042`, `3-050`, `3-062`, `3-076`), **none of them
word-final** and none caught by a crop: fourteen were named by `proposal marks`
before a scan was opened, and the fifteenth fell inside the same crop as one that
was. `3-042`'s reader wrote in its own note that *both* `g` in the gloss carried
the dot and then keyed only the second — the class survives even a reader that
has already seen it. `3-005`'s reader argued
the dot away from morphology — "not the `-gɪn` suffix, it is a bare root
`gêl`" — a glyph inferred from what the system ought to contain, which the
ink refused twice on one page. The same
adjudication ran the other way once, and that is the more useful half:
`2-118` had keyed `naˊrg̣ɪn-` dotted, and the dot came off. A rule stated as
"always" would have made that correction unwriteable, which is why §5.1's count
is scoped to word-final and says where it stops.

The suffix-frequency snapshot that §5.1 used to carry (recompute with `harness
lexicon suffixes` / `lexicon digraphs` before citing — 11/20 pilot pages
restored):

| Suffix | Weighted count | | Digraph | Count | | Trigraph | Count |
|---|---|---|---|---|---|---|---|
| `-ɪn` | 89 | | `ne` | 34 | | `gɪn` | 10 |
| `-hɪn` | 28 | | `ɪn` | 32 | | `ini` | 9 |
| `-en` | 27 | | `en` | 31 | | `ute` | 9 |
| `-gɪn` | 21 | | `na` | 29 | | `Nut` | 8 |
| `-lɪn` | 21 | | `an` | 27 | | `erg` | 8 |
| `-lhɪn` | 20 | | `el` | 27 | | `enu` | 7 |
| `-rgɪn` | 16 | | `in` | 26 | | `m-g` | 7 |
| `-ak` | 15 | | `et` | 25 | | `nel` | 7 |
| `-an` | 12 | | `te` | 24 | | | |
| `-un` / `-ut` | 11 | | `ɪt` | 24 | | | |
| `-ɪrgɪn` | 11 | | | | | | |

`-hɪn`/`-lɪn`/`-lhɪn` together are comparably common to the mark-stripped
`-g̣ɪn` family — a second noun-forming family worth the same "assume it, don't
bare-key it" discipline — and `g̣` itself (marks kept for this one figure) is
corpus-wide the 6th most common digraph.

**§5.2, `ɪ`/`i`/`r`.** Word-initial: `1-101`'s `Iᵋplɪˊlɪ` twice on one page,
both corrected at adjudication to `ɪᵋplɪˊlɪ` — and word-initially the corpus
genuinely splits (63 ASCII capitals against 55 small caps), which is exactly
why `detectors.MEDIAL_CAPS`, sharp on medial position (2:509), was blind to the
pair. From the recognizer: a 2026-08 reader keyed `2-033`'s `Attɪˊg̣ɪtkɪ` as
`Attrˊgɪtkɪ`, taking CATMuS's `r` — and the standing "CATMuS is not a witness
to any *non-ASCII* glyph" rule did not reach it, because the recognizer's error
*is* ASCII; the rule was rescoped to "not a witness to what any character is
wherever an inventory glyph could stand". The residual class: four instances
over two 2026-08 batches survived into adjudication (`2-047` lines 15 and 17,
`empeiˊkɪn`/`hɪshoˊlan`; `2-031` line 33, `Uˊnpɪñe`; `2-035` line 14,
`velerkileˊlɪt`), and every one was on a line whose reader had explicitly
narrated the check — `2-031`'s wrote "checked closely against the ɪ elsewhere
on the page and read as plain ASCII i (x-height, dotted)" and was wrong. A
confident negative here carries no more weight than an unexamined one.

**§5.5, stress reasoned in `resolved` and not typed in `text`.** `3-004`'s
proposal reasoned "post-vowel, not-in-b/p/d/t/g/k, not V_V → stress U+02CA, not
apostrophe" correctly in `resolved` on line after line — and `text` kept the
literal `'` anyway, on 33 of 71 lines. `proposal check` reported the exact
signature (`resolved/text mismatch`, `in resolved not text: U+02CA`) on nearly
every affected line, and the reader dismissed it as narrative-formatting noise.
The same diff class repeating across many lines is the tool reporting something
systematic; and after writing `resolved`, `text` must be re-read character by
character against it, because reasoning about a mark and typing it are two
different acts and nothing enforces that the second followed the first.

**§5.9, the convenient smudge (two rulings).** `1-048` prints
`reindeér-breeding`, and at 4× the mark over the second `e` is a solid tapered
wedge at type weight and slant — categorically unlike the round artifact dots
littering the page, and so read as ink from the forme. The editor's ruling: a
serendipitously shaped smudge. The lesson is not that the observation was
careless; it is that *shape quality at magnification cannot by itself separate
a sort from a smudge*, so it is never evidence enough to adopt an uncatalogued
codepoint on. What worked was suspending judgement: the proposal keyed the
letter as printed and said in `note` that U+0301 is catalogued nowhere in the
inventory and would be the corpus's first combining acute — which put the call
in front of a human instead of into the corpus. `1-060` made it a class: CATMuS
read a combining acute over the `e` of `“Chief of the Chaun Chukchee”`; at 4×
the mark is an irregular blob touching the `f`'s ascender, and the same page
supplies a control in the clean tapered ˊ of `tɪkêˊ-vaˊg̣lɪñɪn`. Keyed `Chief`,
flagged, ruled: another conveniently diacritic-shaped smudge. The disposition
is the same whichever way the shape argument points, because the codepoint
being uncatalogued is what decides it, not the ink — and it was the *second
witness* that made `1-060` cheap: recognizer saw a mark, reading pass did not,
and the disagreement surfaced itself, which is an argument for reading against
`mz/ocr/` rather than alone.

**§5.11, the note that argues correct text wrong.** `2-031` keyed its three
footnote openers correctly as `¹ ² ³` and attached notes claiming plain ASCII
digits had been keyed, "per the precedent recorded for 2-034 in keying_spec.md
§2.10", predicting the half-open-pairing check would flag the page and that
this was expected. Almost certainly the text was repaired mid-pass and the note
never re-read; left standing, an adjudicator reading a confident rationale
beside correct text is being argued into breaking it. The first diagnosis of
this blamed the reader, and was wrong: §2.10 then named `2-034` and printed its
defective opener as a worked example, so a *record of the error* read as a
*statement of the convention*, and both readers of that batch cited the section
in full for opposite conclusions. The passage was rewritten, and the standing
caution came out of it: **when a reader misapplies a rule, read the rule before
concluding it was ignored.** The quotation requirement (§5.11) is the check
that "I read it" is not — neither reader could have quoted a sentence
supporting a plain-digit opener, because there is none.

**§5.12, the invented second witness (two in one batch, different readers).**
`1-022` keyed `Plates V` — correct — and wrote that the first numeral
"measured against the V of VII in the same strip the two are the same height";
they are not (the `v` sits at plain x-height, `VII`/`XIV` are visibly taller
small caps). `1-021` ruled a speck over the `t` of `list` to be dirt — correct
— and wrote that "CATMuS read it as an apostrophe (`list'`)"; the machine text
reads `1 See list of authorities quoted, p. 3.` and contains no apostrophe.
Both claims were one command from being checked and neither was. An invented
corroboration is worse than no note, because it is exactly the thing that
stops the next reader looking — and it will be believed, since the text beside
it is right.

**§2.10, the worked example that read as a convention.** `2-034` printed body
reference `dances.¹` against opener `1 See Chapter XIV.` — the defect the
half-open-pairing check was written against, since repaired
(`gt/ocr/chukchi-2-034.xml` keys `¹ See Chapter XIV.`). While §2.10 recorded
that history with the defective opener printed inline, a 2026-08 reader keyed
a page's openers as plain ASCII and justified them as "the precedent recorded
for 2-034" — the §5.11 story above. The spec's statement is now scoped flat:
no plain-digit convention for footnote markers exists anywhere in the corpus,
no page is a precedent for one, and a detector firing on your output is the
rule working, never a convention you have joined.

**The spec was consolidated on 2026-08-21, and why.** It had grown to 1063
lines, half of them case history, with the same rule patched in two or three
places at different scopes as exceptions were met — and the transcriber error
rate rose as it grew. The specific mechanism, in the editor's words: a narrated
one-off exception teaches the model that exceptions exist, and it starts finding
them. The spec had said word-final `-gɪn` was never bare; a bare one turned up
*compound-medially* (`2-118` L25, `naˊrgɪn-mñêˊɪrg̣ɪn` — a root that happens to
end in those letters, dotted at the true word end); it was written up as an
exception in two places, and readers read the patch as licence and began
undotting blatant word-final `-gɪn` across two part-3 batches. The rule's
*scope* was what needed correcting — "word-final" means the last letters of
the word — and the spec now says that and nothing about the case. The general
rule the rewrite follows: an exception is either a scope correction to the
rule or it is not spec material; one `Attested:` line per rule, and the
narratives live here. The reading-discipline items left the spec altogether
(a reader's instruments are not character inventory) and became R1–R10 in the
contract, which was deduplicated in the same pass: the reader's system prompt
went from ~124 KB to ~72 KB.

**Spirant and pause left the inventory in the same pass.** The p. 10 key (scan
`1-030`) prints them as two distinct sorts — the spirant row `b‘ p‘ d‘ “ g‘ k‘`
with a raised *turned* comma, the pause row `yiñe’a` with a raised comma — and
the spec had encoded both as U+0027 on the ASCII-policy argument that their
environments are disjoint. Neither has ever been seen in the corpus: every
raised comma-shaped mark examined in either environment was stress on
adjudication, and `3-004` alone mistyped stress as `'` on 33 lines while the
detector passed a `'` after b/p/d/t/g/k in silence as "licensed spirant". The
one legitimate apostrophe in the whole book is an ordinary curly one in an
Iñupiaq form quoted from another author in that author's notation. So the spec
no longer assigns the two marks a codepoint or a row; U+0027 joined §3's
forbidden list inside Tier-1 spans with stress as what it traps, and
`detectors.apostrophe_licensing` now reports every straight apostrophe in a
Tier-1 token as unlicensed. The key's rows remain the record of what Bogoras
*declared*; the corpus is the record of what he set. The ᵉi row of the same key
prints its onglide with a mark that resembles the spirant's turned comma more
than a superscript *e* — noted, not acted on; U+1D49 is settled.

## Collation moved behind ground truth, and the generator that made it possible

The collation pass used to run on "whatever draft is current" — `ocr/`, the view,
resolving to `gt/ocr/` where a human had been and `mz/ocr/` otherwise. That was
written down as a feature: ground truth was **a better input rather than a
disqualifying one**, the inverse of the reading loop's rule, and it meant collation
did not have to wait.

What it cost was a pass that could not see the rank of its own input. The same bytes
arrived whether an editor had adjudicated every mark at the raster or CATMuS had read
the page once at ~91% on the ASCII and **0% on the inventory**, and nothing in the
payload distinguished them — an empty `tier1_terms` meant "no ground truth" on 802
pages and "ground truth with no marked forms" on `3-063`, which call for opposite
work. So `page_state` existed to say which, and the contract carried a section headed
"the tautology hazard" telling the model that what reached it under a machine label
was usually a careful human's reading, and that treating it as confirmation compared
a file against something already agreeing with it.

All of that was defence. **A comparison whose witnesses may be one witness must say
so** — and the honest response, once the ground-truth loop had run far enough, was to
stop having two rather than to keep describing the hazard. `tei queue` now refuses a
page without `gt/ocr/`, and `page_state` and `catmus_draft` are both gone from the
collation payload: the first could only ever report one value, and the second was a
lower-ranked second copy of the page's text sitting beside the file under review.

The second half is what made the reversal worth making rather than merely safe.
`gt/zones/` records, on all 832 pages and keyed by a human, **where every paragraph
begins** — `MainZone-P` against `MainZone-Continued` — plus which blocks are
apparatus, which is the footnote apparatus, and which is a block quote. A collator
was re-deriving all of it by eye from the raster. A second derivation of an
adjudicated fact can disagree with the first, nothing downstream can tell which is
right, and the disagreement is invisible because both readings look like prose.

So `harness tei generate` builds the page by rule into `mz/tei/` and the pass reviews
it. Three consequences worth recording:

- **The pass acquired a baseline.** `harness tei diff` compares the generated file
  against the collated one, which makes "did the collator invent this structure?" a
  question with an answer for the first time. It was unanswerable for every page the
  authoring pass produced.
- **`claim` copies the baseline into `tei/`,** because the collator's Bash surface is
  an allowlist with no `cp` in it and must stay that way: a copy it could perform is
  one it could perform in the wrong direction, back over the baseline. The guard hook
  refuses writes to `mz/tei/` outright — its existing `*/tei/chukchi-*.xml` allow
  matched that path exactly as well, which is the over-broad-arm failure
  `test_reader_guards.py` was written against, found in the act.
- **`reconcile` grew a fourth state.** Once claiming creates the deliverable, the
  deliverable's presence stops meaning the agent came back — a collator that died on
  its first turn leaves a file that a presence check reports as finished work.
  `CLAIMED, unedited` is byte equality against the baseline saying otherwise.

**What the generator will not do is the load-bearing part.** Headings, tables, verse
and captions all fall into `MainZone-Other`, whose `rank: null` is the store
declining to tell them apart; note anchoring, figure placement and language identity
are readings. Each leaves a comment naming itself, and `tei diff`'s `gen_comments`
counts the ones still standing — so an unfinished page is detectable rather than
merely unfinished.

The sharpest case is the last. Every ratified Tier-1 token is lifted into an empty
`<foreign index="N"/>` carrying **no `xml:lang`**, and `validate` errors on a
lang-less `<foreign>` — which turns each into a question with exactly two answers:
name the language and let `tei expand` write the adjudicated glyphs in, or unwrap,
because it was never a foreign form. `tier1_terms` is a floor over inventory marks
with no language awareness, and U+0308 combining diaeresis *is* an inventory mark
(`ë`, `ä`), so it fires on `Döring` — ordinary German in English prose — exactly as
on a Chukchee form. A generator that named a language there would be inferring one
from the shape of a word, which is the firewall's failure mode one category over from
glyphs. The gate closes a hole that predates all of this besides: a hand-written
`<foreign>` with text and no language used to pass in silence.

## The request models were rewritten from memory, and two of three failures were silent

Splitting `webui.py` into `harness/web/` moved each editor's routes into its own
module and gave each POST a Pydantic model. The zones save model was written from
recollection of the payload rather than from the file that builds it, and got
three fields wrong at once: `exempt` declared a `bool` where the client sends the
list of exempted order rules, `anchor` where it sends `nudge`, and `figures` where
it sends `figs`.

**Only the first was loud.** A type mismatch is a 422, so `Enter` saved nothing and
the editor was visibly broken — annoying, immediately noticed, fixed in a line.
The other two are the shape worth recording: **Pydantic drops undeclared fields
silently**, so once the type error was gone the save would have returned 200,
printed its usual `saved gt/zones/…: 5 zones` line, and written neither the column
nudge nor anything at all from the figure track. A save that reports success and
stores less than it was handed is this project's defining failure in miniature.

Two things made it possible and both are now closed.

**Nothing tested the route.** Every existing zones test calls `save_payload`
directly with a hand-built dict — the right shape for testing the store writer, and
it means the model was in no test's path. `test_web_contracts.py` goes through the
router, against a `tmp_path` root because `gt/zones/` is tracked and somebody may
have the page open while the suite runs.

**The contract is written twice in files that do not import each other**, so
agreement was nobody's property. The same file now holds each endpoint's real
client body beside its model and asserts in three directions: the model accepts
what the client sends, drops none of it, and declares every field the server-side
consumer reads. The third direction found a second live bug on its first run —
the edition server's entity-creation route reads `triggers` and `since` off a
model that declared neither, so an entry created with either would have been
written with the placeholder trigger row and no `since:`, and would have looked
complete.

**A default is not always harmless, and `figs` is the case.** `save_payload` asks
`"figs" not in payload` to decide whether the figure store is touched at all,
because `zones blot` keys the segmenter's training rasters off `gt/fig/`'s mtimes
and rewriting 252 identical files during ordinary zone keying would stale every one
of them. A `list[dict] = []` default puts the key in *every* dump, which on a
figure-less page trips the store's deliberate refusal to write an empty figure file
and fails the save outright. The field defaults to `None` and the route dumps with
`exclude_unset=True`; both halves are pinned, since either alone restores the bug.

The same refactor left `nav()` and `navStore()` navigating to a bare `/` while the
editors are mounted under `/zones` — so the arrow keys walked to the shell's front
door and read as dead keys. Every other URL in every editor's JS was already built
from `B`, which is what made the two exceptions easy to miss and easy to find once
looked for.

## An empty list meant "delete everything", in six places

A probe of the editors' HTTP endpoints posted `{"ref": "1-097", "lines": []}` to
`/lines/save` against the working tree. `lines_ui.save_payload` writes before it
reaches the call that then raised, so the request deleted
`gt/lines/chukchi-1-097.xml` — a box a human had drawn over the folio "71", ink
the segmenter missed — and the unrelated `OSError` that followed read as a
session-state problem. Nothing was lost: `.prev` is written before the unlink and
the file was committed. The `.prev` and `_ink_exempt.json` mtimes, both 19:14, are
what identified it, after the cause was first reported as unknown and the user
went looking for a bug in their editor.

**The defect is a collapse of two different things into one value**, and it was
in six places. `corrections.save_lines` deleted the file on an empty list.
`corrections.set_ink_exempt`, `zones.set_ink_exempt`, `zones.set_exempt` and
`figures.set_rule_exempt` all pop the page's entry and rewrite their JSON on one —
with no `.prev` and no journal, so they are *less* protected than the thing that
actually broke. `review.save_decisions({})` replaces a page's whole adjudication
with nothing, in the store this project has already lost work in once.

**This is the `figs` presence rule with its siblings unlooked-for.** One commit
earlier, `/zones/save` learned to send `exclude_unset=True` precisely because an
always-present `figs: []` would have meant "the figure track was emptied". The
same reasoning was never carried to the neighbouring keys, and it could not have
worked there anyway: `payload.get("ink_exempt") or []` turns an absent key back
into an empty one on the very next line. A guard at the model that the consumer
undoes is not a guard.

**The rule that replaced it has two layers, chosen by what the destruction
costs.** A *route* may never manufacture an intention: absent is not empty,
enforced with `if "k" in payload` rather than `or []`. A *store* that destroys an
authored artifact demands explicit intent: `save_lines` and `save_decisions` take
`withdraw=`, and refuse an unstated empty save naming what it would have taken.
The four exemption sidecars get only the first layer, and that asymmetry is
deliberate rather than an oversight — an exemption is a ruling that can be
re-asserted by making it again, while a box drawn over unrecognised ink exists
nowhere else.

The two existing precedents were already right and were not generalised in time.
`figures.save_figs` refuses an empty page and names `harness fig delete`;
`zones.save_zones` refuses one and names three verbs that say different things.
Both could refuse outright because both stores have a withdrawal verb.
`gt/lines/` has none — the editor *is* how a correction is withdrawn — so the
intent travels with the call instead, and the browser asks before sending it.

**A refusal that cannot be read is a refusal that did not happen.** None of this
would have reached a human: `errors.install` answers in JSON only for endpoints
marked `@fetched`, and every write endpoint was unmarked, so a raised `ValueError`
came back as an HTML page. `lines.js` parsed the body before checking the status
and `zones.js` parsed it on the error path, so both turned the message into a JSON
parse error. Two carefully worded refusals — "no zoning", "boxes lie in no zone" —
had been unreadable since they were written. The write endpoints are marked now
and both clients check the status first.

The message bar moved with it. It was a `<span>` in a `white-space:nowrap` top bar
with `margin-left:auto`, so a sentence was clipped to whatever room the counts
left, and on a crowded bar to nothing. It is a full-width strip at the foot now,
absent until there is something to say, dismissed by a click, with the issue strip
riding above it on a measured offset rather than under it.

**And the process lesson, which is mine.** The probe should never have run against
the working tree. `gt/` is tracked, a page was open in a browser, and I had
refused this exact call for the zones store in the same script one case earlier —
the reasoning was available and applied too narrowly. Endpoint probing belongs
against a temp root, or in a test, or not at all.

## The double-duty toponym, and the alias that swallowed its own link

This book names a bay, a cape and an island off the village on it. `Kuluˊči` is
the village; `Kuluˊči Bay` is the bay, eight times over; `Čeˊčin Bay` is the bay
at `Čeˊčin`, `Karagha Bay` the bay opposite the island `Karagha`, `Kanchalan
Hills` the hills above the `Kanchalan`. There are eleven of them. Until this
sweep the store held only the inland member of each pair, so every one of those
spans linked the wrong referent — and the reading view showed the reader an
encyclopedia entry for a village where the sentence said a bay.

Adding the bay looked like it would fix it and did the opposite. `match` is
non-overlapping and longest-first, so `Kuluˊči Bay` claimed the span; and
`_entity_spans` refused any hit that overlapped a Tier-1 handle without exactly
coinciding with it, so the claim was then dropped. The refusal was correct on the
rule as written. It was also silent: the page lost the bay's link, lost the
village's link along with it, and said nothing about either. **A rule that
refuses has to say so, or an editor reads the absence as "no name here".**

Two changes, and they are different in kind.

**Containment now encloses.** The old rule admitted only coincidence, on the
argument that it is the only relation needing no opinion about where the form
ends. Containment needs none either — *both* of the handle's ends are inside the
alias — and it is what every one of these eleven looks like: an English feature
word wrapped around a native form. What is written is the coincide case one step
out:

    <rs ref="water:kolyuchin-bay" resp="#mz"
      ><foreign index="2">Kuluˊči</foreign> Bay</rs>

with the alias's remaining text required to be ASCII, so the `#mz` element still
carries no glyph a rule would be originating, and the inner `<foreign>` untouched
and keeping its own rank. `_emit` learned to nest for it, and nests only on
containment — a partial overlap is still first-one-wins.

**A partial overlap is still refused, and now leaves a comment.** It is
reachable: `_AFTER` forbids a following letter or combining mark but not a
hyphen, so an alias can cover the first half of a hyphenated handle and stop
inside it. Nothing may pick the extent there. What changed is that the reader
hears about it.

Alongside them, a smaller instance of the same failure. `auto_forms` withholds a
link for three reasons — contested form, `auto: no`, unratified entry — and the
generator's comment named the second whatever the reason was. Forty-two entries
scaffolded in one afternoon are all `proposed`, so the ordinary message was
telling an editor to raise an `auto:` field that already read `yes`. Each reason
now says itself, and the unratified one prints the verb that settles it.

The same afternoon turned up a third: `map_context` read `data/geo/`'s `absent`
block as strings when its rows are records, so `.lower()` raised on every entity
with no extent. It had been latent since the block widened, because almost every
entry had a shape; a batch of bays and capes with neither `area:` nor `geo:` made
it the common path, and the map view 500'd. `geo.absent_row` was already the
flattener and already tolerated both forms — it simply had one caller too few.

## The atlas drew a box nobody could have declared

`land:russian-far-east` has no shape, so its map's viewBox came from the union
of every descendant's extent. Two of them set three of its four sides: the
[[river:lena]] reaching 103°E and 72.9°N, the [[river:amur]] reaching 41.7°N —
rivers Bogoras names ten times between them, as distant comparanda. The map was
a quarter of the northern hemisphere, bent round the pole, with Alaska in shot,
and every one of the sixty-odd entries under it inherited that frame.

**Three separate defects, found one behind the other, each hiding the next.**

**A frame that could be declared.** New optional `frame:` on an entity — four
degrees, west south east north — overriding whichever frame would otherwise have
been derived and nothing else. `extent_of` is untouched, so an ancestor still
sizes itself on the real geometry and `member_shapes` still draws everything
beneath: *where to look*, not *what is there*. Both defaults have a case they get
wrong, and one field answers both — a shapeless container sized by whichever
descendant strayed farthest, and a shape framed on its parent, which is what
makes a shape mean something until the shape is `land:chukchi-peninsula` and
Chukotka's box packs thirty-four villages into a corner. A parent's declared
frame is what its children frame on, or the field would fix one page and leave
every page under it drawn to the box just declared wrong.

**A viewBox that was always square.** With the frame declared, the map barely
changed. `Frame` scaled to `max(width, height)` and emitted a 1000-unit square,
so a wide frame was zoomed to its width and padded with empty sea: measured, the
Northeast Siberia box filled 89% of the square horizontally and 42% vertically.
More than half the picture was margin, and the map came out at very nearly the
zoom of the thing it was drawn to improve on. The viewBox takes the frame's
aspect now; `svg.map` is `width:100%; height:auto`, so that is simply a shorter
map. `CULL` had to learn the same lesson — culling y against the width would
keep half a coastline nothing can see.

**And the projection, which is why no declared frame could have worked.**
Lambert azimuthal equal-area, centred per map. Meridians converge toward the
pole, so a latitude/longitude box is a curved trapezoid: on the Northeast
Siberia box the west bound projected **twice as far out at its southern end as
at its northern one**. A viewBox is a rectangle and had to be fitted to the
bounding box of that, so it was sized by the southern corners — which is how a
frame declared from the Yana to Cape Prince of Wales reached Manchuria. The box
was not what got drawn, and no number a human wrote in it would have been.

It is equidistant cylindrical now, standard parallel per map: meridians parallel,
parallels horizontal, **a latitude/longitude box a rectangle**. The cost is equal
area, which was the old projection's second argument — comparing this basin
against that one inside one frame. It is real and bounded: scale error is
`cos(lat0)/cos(lat)`, so across the 21° of the widest frame in the store a shape
is at worst about a third too wide at the north edge, and the ordinary case — one
basin, one village — is a zoom at which every projection agrees. The old
projection's *first* argument was never load-bearing: the antimeridian is safe
because `tools/build_geo.py` normalizes longitudes into one continuous window and
welds across 180 before anything is drawn. `project` wraps the longitude
difference into (−180, 180] anyway, so 185 and −175 still land on one point
whatever window a caller holds.

**Then the map became legible and turned out not to be.** Land regions,
watersheds, open water and settlements all drew in one accent, which on a narrow
frame is one or two shapes and on a wide one is fourteen watersheds, five regions
and three stretches of sea in a single field of outlines. The shape kind is
declared in `data/geo/` and now travels on the path as `data-kind`, one hue each.
Deliberately **not** the prose vocabulary, which then grouped `place:` and
`water:` into one hue because in a sentence "place or person" is the question —
and on a map that was the wrong axis twice over, `place:` covering a peninsula
and a mountain range alike. The pins took `--pin`, a theme token that had been
declared and never used.

**That "wrong axis twice over" was the first statement of the defect, and it was
about the classes and not about the map.** Colouring by shape kind was correct
and remains so, but it had been *forced*: the entity class could not tell a
coastline from a drainage divide because two classes were carrying four kinds of
thing. Splitting them into `place:`/`land:`/`river:`/`water:` — a point, a
region, a basin, a body of water — put the class 1:1 against the shape kind it is
drawn from, so `geomap.css` keys off `data-kind` by choice now rather than for
want of an alternative, and `edition.css` can separate land from water in prose
with the map already agreeing. Fixing that also uncovered a plain CSS defect the
palette had been hiding: `a.node` declared its own `--link` fallback at the same
specificity as the family rules and two hundred lines below them, so every node
in the atlas tree came out accent-coloured whatever its class. A default that
ties with the rule overriding it is not a default; the default moved to `:root`
and no consumer declares `--link` at all any more.

**What this cost, and the lesson.** Four rounds, each fix revealing that the
previous symptom had a second cause underneath it, and each round I reported the
thing fixed rather than checking whether the picture had actually changed. The
frame and the aspect were both real defects and neither was *the* defect; a
render compared against the previous render, rather than against the
description of what should happen, would have found the projection two rounds
earlier. `harness/tests/test_geomap.py` now holds the box-is-a-rectangle
property directly, which is the assertion none of the three rounds could have
been argued past.

## Part 3 was read below source resolution for twenty months

`scans/` was `pdftoppm -r 300` over `pdfs/`, and nobody had read what was inside
the PDFs. They are MRC-layered: a 1-bit JBIG2 master per page, plus separate
embedded JPEGs for the photographs. **Every master is placed at scale 1.0 and is
exactly 300 dpi.** The parts differ only in the arbitrary paper size each scan was
wrapped in, and rendering the *page box* resampled a master that could have been
copied.

What that cost, per part:

- **Part 1** — the master sits centred in a box 43 px wider, so the extra is white
  padding. Harmless in itself, but the offset is *fractional*: 5.13 pt is 21.375 px,
  so poppler resampled every pixel of every page for a shift of three-eighths of one.
- **Part 2** — the box already was the master's size, and poppler smeared it anyway.
  247 grey values out of a 2-value source, 550 KB where the master is 125 KB, 10.2 %
  RMSE against it with the letterforms perfectly aligned. All of that difference is
  fabricated edge antialiasing.
- **Part 3** — part 2's layout jammed onto A4, so the render is **cropped, not
  squeezed**: ~35 px off each side. Every part 3 page was segmented and OCR'd on a
  raster missing 2.7 % of its width. Those pixels are verified blank on all 202
  pages, so nothing was lost — but that was luck, and nothing had checked.

**The doc had the number and the number was wrong.** `docs/rasters.md` said part 1
was "295.5 dpi" and part 3 "308.4 against an A4 page box". Both came from dividing
the master's pixel count by the *mediabox* rather than by the image's own placed
width. It is the arithmetic that made the corpus look like three different scans
needing a per-page ratio, when it was one uniform scan needing a per-part
translation. A figure derived from the wrong denominator is worse than no figure: it
had been sitting there, precise and quotable, for as long as the tree existed.

The correction is `tools/extract_scans.py`, which cuts the rasters from the layers
instead of rendering them, and `harness/migrate.py`, which translates every stored
coordinate rather than scaling it. Two things worth keeping from how it went:

**The idempotence guard could not be the dimensions.** Part 2 is 2550×3525 before
and after. A size check cannot distinguish "correctly untouched" from "not yet
reached", so a partial run would have looked complete — which is why there is a
receipt at `data/_migrated.json` instead.

**The integrity gate that came for free was the vacuous one.** The existing
migration hashed `String/@CONTENT` before and after. `gt/zones/`, `gt/fig/` and
`mz/zones/` carry no `String` at all, so that digest would have passed on 1,450 of
the ~2,000 files it touched while checking nothing. What actually holds is a
structural digest — ids, labels, and every box's extent — and it holds *because* the
operation is a translation: an extent that moved would mean the code had stopped
doing what it says. The first version of it also hashed `Page` and `PrintSpace`,
which are supposed to change, and duly aborted all 832 pages. A gate whose first run
fails everything is either a real finding or a wrong gate, and the way to tell is to
name what it should be blind to *before* looking at the count.

## Six spellings of "what made this", and the one that let a report name a model it never loaded

Every `mz/` store already recorded something about its producer and no two
recorded it alike. `mz/zones/` and `mz/ocr/` wrote a `<Processing>` block from
four hand-built places; `mz/fig/` wrote a bare
`f"{model_path} sha256:{sha[:16]} device:{dev}"` from a fifth and a rule
description from a sixth; `mz/tei/` wrote an XML comment, which no XPath reaches,
no schema constrains and `tei validate` could not see.

**The cost was not the duplication.** It was that `mz/fig/` held two kinds of
claim — a segmenter's guess from `fig predict`, and the scanner's own MRC
segmentation from `fig propose` — as two free-text strings no reader could tell
apart without matching prose. `figures.score` took a `model_path`, used it only in
the returned dict and always compared `mz/fig/` against `gt/fig/`. So
`train score fig --model M` named a checkpoint it never opened, over a store that might
hold no model's work at all: a diagnostic answering a question it had not asked,
in the store's own report. Fluent nonsense inside the instrument built to detect it.

The correction is one record with a **`kind`** field (`harness/provenance.py`) and
one writer behind all six sites. A rule's output and a model's guess are both
`#mz` and neither outranks a human; they are not the same witness, and the store
now says which it holds.

**A machine-readable block declares itself, and legacy free text reads as
unwitnessed.** This is the part worth keeping. `read_producer` could have scraped
`model:` out of the old prose — it is right there, and the parse is four lines.
Then `corpus provenance` would have reported every store fully witnessed before a
single file was rewritten, the backfill would have been indistinguishable from a
no-op, and the one instrument built to prove the change would have been the thing
that concealed it. A census whose number cannot move is not a census. The marker
is a leading `harness: 1`; the number moved 0 → 236, 0 → 717, 0 → 749 as each
store was rebuilt, which is what proved the rebuild.

**Moving `mz/tei/`'s stamp into `<appInfo>` nearly broke `tei diff`, and the test
that should have caught it was the test that hid it.**
`test_diff_says_it_cannot_tell_rather_than_saying_no` built its "page with no
stamp" by regex-stripping the XML comment. Once the stamp was an element, that
setup produced a page that still carried one, so the test asserted nothing about
the case it names. It failed loudly here only because the *assertion* happened to
still bite; a differently-worded assertion would have gone green and stayed green.
A test whose setup constructs its precondition by removing a specific encoding
decays silently the day the encoding changes. `_producer_stamp` reads both forms —
every page collated before the move carries the comment, and `SURVIVING` still
lists `generated:` for that reason — and the fallback is pinned by a test that was
mutation-checked by deleting it.

## A ruling that did not clear what it made false, and a docstring that outlived its mechanism

Ruling a leaf `plate` or `blank` in the editor saved the ruling *and* whatever
zones were on the canvas, and never touched `mz/zones/` at all. So 32 leaves kept
a segmenter's guess at a text column they do not have — 98 zones against 1 in
ground truth, 57 of them `MainZone-P`, several on paper with no ink on it — and
two kept a human's. `1-325`, a plate, carried eleven paragraphs decoded out of a
photograph's tonal bands. Nothing read any of it, because `gt/` outranks `mz/` in
the view; that is a fact about today's consumers rather than a property of the
store, and it is the reason the residue survived a year without a symptom.

The rule is `exempt => no zones`: a leaf has no text column, so there is nothing
for a zone to be, and the kind in the split lists is the whole record that a human
looked. Ruling one now clears both stores, after a confirmation that fires only
when there is something to lose.

**The empty ALTO was the older spelling of that record, and a docstring still said
so.** `has_zones` read: *"A plate carries no text column, so its correct
segmentation is zero zones; an empty file is that record… Only the file's
existence separates 'looked at, holds nothing' from 'not looked at'."* That was
true before the leaf kinds existed and false after — the kinds took over both jobs
— but the prose stayed, and it was cited here as the reason the files had to be
kept. **Prose in this repo carries a date it does not print.** A comment that
describes a mechanism is evidence about the mechanism *as it was*, and the
question to ask of one is not "is this well argued" but "is what it describes
still what happens". The cost of not asking was an argument for preserving 115
files whose whole justification had been superseded.

What replaced it is two predicates, and keeping them apart is the point.
`has_zones` is a **file** question — the editor's store selector and its
paragraph pill ask it, and gating those on the other one drew `gt — 0` for a page
whose ALTO had just been deleted, the old convention coming back as a live-looking
number. `keyed` is "has a human been through", which a ruling answers as fully as
keying does; the Done button, the progress count and the itinerary's resume ask
it, and reading them off the file reported every plate in the corpus as unfinished
and sent the resume back to the same plate every session. `settled_refs` is the
same distinction one level up, for the sweep and the page list.

**Reading the ink is not the same as reading the policy.** `1-245` is a plate
carrying a real running title — "BOGORAS, THE CHUKCHEE." and folio 189 — with a
`RunningTitleZone` sitting exactly on it. Looking at the raster, that zone is
correct, and it was defended here as correct human work the rule would destroy.
It is not: most plates carry a running title, they are deliberately ignored, and
the folio propagates through the seam ledger instead. Zoning one records nothing
the corpus reads and leaves a text-page label on a leaf that is not a text page.
The ink was evidence about the ink and about nothing else; the store's rule was
the question, and it is not answerable from the page.

The counterpart failure is on the same two leaves. `1-316` is blank — no ink at
all bar two specks of scanner dust — and its keyed `MainZone-P` was read here as
"a folio number or a signature mark, and the human keyed exactly it". A
justification was invented for a mark that has nothing under it, in the middle of
a report about other instances of exactly that. Look at the page.

## The geometry change was a transaction nobody had written down

"Part 3 was read below source resolution for twenty months" ends with the
correction: cut the rasters from the layers, translate every stored coordinate.
What it does not say is how that correction was *performed*, and the answer is a
PEP 723 script, a hand `mv`, and a receipt written afterwards.

The script could not be tested. `tools/extract_scans.py` declared `pymupdf` inline so
that it ran in an environment with no harness in it, and the isolation was argued for
here as a firewall: a script that cannot import the package cannot drift into being
part of a loop. That argument was about a hazard nobody had met. What the isolation
actually cost was the assertion that mattered — no test could say that a master placed
at a known offset came back at that offset — and it cost it for the whole twenty months
the wrong rasters were in use. **A firewall around the one piece of code with no second
witness is not a firewall.** The cut is `harness/scans.py` now and
`harness/tests/test_scans.py` holds the arithmetic: the placement, the snap, the
integral paste, and each of the six refusals firing.

**The manifest had no reader, so its numbers went unchecked.** `data/pdf_images.json`
was written by the script and read by `figures.py` for one check; nothing printed it,
so nothing compared it to what the docs said. Two errors sat in it undisturbed. The
first is the one the entry above is about — "295.5 dpi", divided by the mediabox. The
second is smaller and was still there when this group was built: the comment claiming
`1-303`'s master is 2824×3866, among neighbours at 2781×3866. It is 2824×3897, which
`scans census` prints in a table of five rows. Both numbers were precise, quotable and
never read back off the thing they described.

**The swap was the missing verb.** `--rasters DIR` wrote a sibling tree and a human
was expected to move it into place; the coordinate migration was a second command; the
farms were rebuilt by a third, if anyone remembered. Those are one operation — every
box in six stores, two band ledgers, a cache, the painted farms and the review images
describe pixels in a particular master's space — and performing it in three steps means
each step can be the last one that ran. `scans swap` is the transaction: stage, verify,
move, receipt.

Three things fell out of writing it down that were not visible while it was three
commands.

**The shift is manifest-to-manifest, and `offset` is not it.** `offset` records where
a master sat inside the legacy pdftoppm space. It is spent — the stores left that space
— and a re-cut needs `new placement − old placement`, per page. Reaching for the field
that is already in the file would re-apply a shift that had been applied once. The
legacy migration is now that same function with its arguments defaulted, which is what
keeps the tested path and the path that will actually run next from being two paths.

**Part 2's hazard has a second form, and it aborts.** "No size check can distinguish
'correctly untouched' from 'not yet reached'" was recorded above as a reason for the
receipt. It is also a reason to refuse: where two manifests give the same page-box size
and a *non-zero* shift, nothing in the file says which side of the shift it is on, and
both available guesses corrupt something. The render→master migration never met this
because every page that moved also changed size. The generalisation met it in its first
test run, as a page that quietly reported "already".

**The dependency set had to be composed, not listed.** A hand-written list of what a
geometry change invalidates is a list that goes stale the day a farm is added. It is
built from `migrate.STORES` and from the farms whose own `reads` names `scans/` — and
that rule is doing work: it excludes the `select` leaf farms, which are links by
filename and do not move under a shift, where a filter on `kind` would have thrown them
away. The one thing it must *not* touch it also names: `ed/page-img/` and `ed/fig-img/`
are a human's touch-ups cut from a raster, so a shift makes them stale, and nothing
mechanical may rewrite an authored image. They are reported as work a human owes.

**And `scans/` now says what made it.** Each PNG carries a `tEXt` chunk in
`provenance.py`'s vocabulary naming the PDF it was cut from and that file's sha256, and
the manifest digests the three sources; `scans audit` re-reads them. The sources live
outside the repository behind a symlink and can be replaced with nothing noticing,
which is the same class of thing as the wrong render: not a disaster, but a fact that
must not be discovered afterwards. The chunk carries no timestamp and no absolute path,
so two cuts of the same PDFs are byte-identical — which is what let the port be checked
by cutting all 832 pages and diffing them against the tree in use. They matched exactly,
as did every page entry of the regenerated manifest.

## A pool rule that was measured on the wrong axis

`parallel.py` carries a bench table and a rule drawn from it: a page has to be
doing something that *releases* the GIL before a thread pool can help, and the
cheap sweeps were measured and deliberately left serial. Both halves were true and
the rule was still wrong twice.

**It read as "threads or nothing".** `harness scans extract` was documented as
unpoolable, on the grounds that a `pymupdf.Document` is not thread-safe. That is
true of *sharing* one and beside the point — a worker can open its own — and it
was never the real obstacle. The real one is that the page read holds the GIL, so
threads lose outright:

    serial       20.6 s        4 processes   5.8 s
    4 threads    22.6 s        8 processes   2.9 s
    8 threads    25.0 s

Over the corpus that is 133 s at 101 % CPU — one core saturated on a sixteen-core
machine — against ~20 s. The docstring had stated a real constraint, checked
nothing against it, and used it to close the question. **When the answer to "do
threads help" is no, the next question is processes, not resignation.**

**And "is it slow here" is not the criterion.** The four `scans` read sweeps are
0.5–1.8 s locally, almost all of it the interpreter starting, so the measured rule
excluded them correctly *for this machine*. The corpus is going to be read on a
VPS with the store on NFS, where the per-page cost is not CPU at all — it is a
`stat` and a header read, two network round trips, and the sweep is latency-bound.
Threads absorb latency whatever the GIL is doing, because a syscall releases it.
The bench table measured CPU on a local SSD and the rule inherited that scope
without saying so.

That is recorded in `VERBS.md` as **reasoning rather than measurement**: no NFS
mount was benchmarked here, so the honest claim is a predicted win. What the
prediction did buy was a real fix. Counting the round trips to argue about them
showed `info` touching each raster five times — `exists()`, an open for the size,
a `stat` for the bytes, then a second open for the provenance chunk — where two
do. Measured: 3062 `openat` to 2224 over 832 pages, and no threads involved.
**The optimisation that survives a slow disk was found by asking what the slow
disk would charge for, not by adding workers.**

One thing the pool broke on its way in, worth keeping because it is a class.
`pchunks` hands the caller's `tick` the work-item, and a chunk here is a tuple of
a PDF path, sixteen page numbers and the source record with its sha256 — which
`rich` rendered with `str()` into the bar's item field, eight times a second. The
bar also counted 52 where the report counted 832. **A progress bar's unit is the
one the human asked in, and its label is a name, not the object.** Three of the
four threaded sweeps had the same fault for the same reason, since their items are
`(ref, entry)` and `(store, path)` pairs; `scans._labelled` is the one wrapper and
`test_scans.py` holds every bar to a ref-shaped label.

## The hyphen the corpus could account for all along

`join_broken_words` rejoined a word the compositor broke across a line end and
kept the hyphen it broke across. That was deliberate and had a measurement behind
it: dropping the hyphen is what a modern de-hyphenator does, and doing it here
manufactured nine words the book does not contain — `reindeerowner`, `treetrunk`,
`beaconlamp`, `Shootingstars` — because a real compound hyphen falling at a line
end is indistinguishable from a break. The docstring closed with *nothing in the
ALTO can separate the two*, and for the flag arms that was the right answer:
`lexicon_miss` resolves `Chuk-chee` by **testing** the concatenation, which reads
the token rather than editing it, and needs the token to keep saying where it was
cut.

The generated TEI inherited the same text, and there it was not a preserved
ambiguity but a defect a reader met: `of the Chuk-chee people`, `con-sidered`,
`some-times`, set in the middle of sentences the edition asks people to read.

**Nothing in the ALTO had to separate them.** `gt/ocr/` sets these same words
*away from a line end* on other pages, where the measure does not account for a
hyphen and the spelling is therefore the book's own. That is a second witness, and
it was sitting in the store the whole time. `sometimes` 316 times mid-line and
`some-times` never; `seal-skin` 81 and `sealskin` never. So the claim was not
weak, it was **an evidence problem asserted as an ambiguity** — the same failure
`docs/edition.md` records one section earlier, where the position of the hyphen
turned out to be in the ALTO and the generator was throwing it away. Twice now, in
the same paragraph of the same book, the answer to "nothing can tell these apart"
has been *something already in the record can*.

The rule: offer each joined token to the index twice, as it stands and with the
cut closed, and take the spelling ground truth sets mid-line **on some other
page**. Measured over 717 pages and 1,350 breaks — 958 closed, 219 confirmed as
the book's own hyphen, 173 asked about, 30 refused as Tier-1. 87% decided.

**The dictionary was the obvious witness and is the wrong one.** It was the first
proposal — drop the hyphen where the halves form a common word — and against the
corpus's own spelling it agrees 97.4% of the time. The 2.6% is not noise; it is a
class, and it is the class this book is made of. `newborn`, `sealskin`,
`summertime`, `earrings`, `everyday`, `crosspiece` are all words of modern
English, and this is a book of 1904 that sets every one of them with the hyphen,
81 times in the case of `seal-skin`, against zero witnesses for the closed form. A
plain `/usr/share/dict` is worse again — 89.8%, its 99 misses every one a proper
name it has never heard of, `Chuk-chee` at the head of them with 2,931 mid-line
witnesses to `Chukchee`. **A general dictionary is a statement about the language;
the corpus is a statement about the book.**

**A ratio would decide 12 more of them and is deliberately not used.** `sea-coast`
is set once mid-line against 17 `seacoast`, and a rule reading "ten to one is
decisive" would close it. That number would be a threshold nobody measured,
tippable by one mis-keyed page, and the whole of what this rule has over the
dictionary is that it asserts nothing it cannot point at. Twelve reader questions
is not a cost worth buying it with.

Three things the rule needed that the idea did not come with.

**The cut has to be recorded, not re-found.** `Chuk-chee` and `so-called` are the
same string shape and a different hyphen, and the only thing that separates them
is the offset the join knew and discarded. `joined_words` returns it now and
`join_broken_words` is its text-only face, kept because six callers want exactly
that. A word broken twice carries two offsets, and they follow the text through
both splices — which is also what lets the multi-hyphen cases resolve, `rein-` /
`deer-breeding` closing to the `reindeer-breeding` the corpus sets 93 times rather
than being refused for having a hyphen the rule could not place.

**The two witnesses can be one file.** `gt/ocr/` is both the text being set and
the corpus deciding it, so a page that broke `Chuk-chee` would attest `Chuk-chee`
mid-line and confirm every break in itself. Two guards, and they are different:
the index refuses any token *carrying a cut* as a witness at all, and a form is
consulted only where some page **other than this one** sets it. The index keeps
two refs per form because two is exactly what answers that question. This is the
hazard `CLAUDE.md` names — a comparison whose witnesses may be one witness — found
in a new place, which is where it keeps being found.

**`mz/ocr/` is not in it, and the reason is a measurement rather than a rank
argument.** English prose spelling is not what the firewall governs, so the
recognizer's pages were admissible; adding all 717 of them moved not one verdict
of 1,350, because the recognizer's pages are the keyed pages. A witness that
changes nothing is not worth the rank question it raises.

What did not change: **a token bearing an inventory glyph is refused before any
count is consulted.** Inside the notation U+002D is a licensed sort
(`keying_spec.md` §1), a line-end hyphen in a form is an anomaly to reproduce and
comment, and an index reading `Torwaˊwaq` ninety times would not make closing one
a reading a rule may originate. The refusal is `bears_inventory`, the project's one
definition of a token carrying the notation, and the verdict records zero counts
rather than a losing tally — refused, not outvoted.

## The views were a second name for one store, and a default was their last defender

`ocr/` and `zones/` were symlink farms over the paired stores, the human file
winning. They were built for a real state of the corpus: collation could run ahead
of the reading loop, a machine-read page was workable, and a reader wanted "whatever
this page's OCR currently is" without asking who produced it. The entry above on
the tautology hazard records the reversal of that premise — `tei queue` came to
refuse a page without `gt/ocr/`, and `dispatch.collate_build` says **`gt/` by name,
never the view** — but the reversal stopped at the collation gate. Everything below
it kept the view: `lines.DEFAULT_STORE = "ocr"` was the default for the entire
correction and review layer, `context.build_context` opened the view directly, and
`paths.all_refs` defaulted to it on a docstring arguing for the blend.

**The corpus showed the blend no longer fired.** All 832 leaves settled, 717 text
pages at `gt` for zones and OCR, zero mz-only refs in either pair, and every one
of the 1,434 view links resolving into `gt/` — not one into `mz/`. The views were an
exact second name for `gt/ocr/` and `gt/zones/`, carrying a semantics that had
nothing left to resolve, in front of the one layer whose subject is rank. And the
hazard was live where it was quietest: `proposal_check`'s punctuation arm read the
view for "the recognizer's draft", and on a finished corpus that was this
proposal's own restored text, so the check compared a reading with itself and went
silent — the shape `ocr diff` refuses outright, one verb over.

**The default was sized to the census, and that was the wrong measure.** The first
replacement put `gt/ocr` where the view had been, because every page was restored.
But the `ocr` group's verbs are used while a page has *only* a machine reading — a
fresh book has no `gt/ocr/` when `lines`, `crops`, `review` and `restore` are
running, and `restore` needs `mz/ocr/` as its skeleton. So the group defaults to
`mz`, the library takes no default at all, and the readers of the loop's output
name `gt/ocr/`. A default follows the lifecycle stage a verb runs at, not what the
finished corpus happens to hold; the census is evidence that a blend has stopped
firing, never for what a default should be.

**The baked line→zone association was the same defect in the ALTO.** `ocr predict`
wrote the keyed zones in as labelled regions, and `restore` copied that skeleton
into `gt/ocr/` — so the ratified store held 717 pages of `TAGREFS` while two
docstrings said it held none. Every consumer had already gone back to geometry for
the reason `generate._assign` records: the bands may have been cut since the
blocks were written. Measured before the labels were removed: 30,026 lines agreed
with containment and 16 did not, on two pages, every one a band re-labelled or
added since prediction — the staleness exactly. `page_lines` derives `zone` by
containment for every record now, `ocr predict` writes bare lines, and
`tools/flatten_ocr.py` gave every earlier page the same shape, refusing on any
drift in line ids, boxes or text.

**And a worklist read off an input store made a mixed output store silent.**
`predict_all` took its worklist from the zone view and skipped any page with a
file; a store written by two recognizers looked finished. The worklist is every
page that exists, and `predict_skip` skips a page whose `mz/ocr/` file records
*this* recognizer by sha — so a mixed store *is* the non-empty worklist.

What survived, in the open: the zones editor still opens an unkeyed page on its
prediction and a keyed one on ground truth, because that is the editor's modal use.
It reports the store it chose and that it was not pinned; there is no third name
for the choice, and no reader anywhere else makes it.
