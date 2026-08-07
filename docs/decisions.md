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
and rendering the result as a verified PASS. Removed from `validate.py`,
`validate.py` and the collation skill; the comment at the old check's site records why.

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

What that page settled is worth more than its six corrections: **`gt/ocr/` and
`data/readings.md` are not independent witnesses on a figure page.** This
ground truth was hand-corrected from CATMuS and the caption block descends from
the same recognizer pass, so three commas the machine invented sat in both files
corroborating each other, and only a fresh raster read separated them. Nothing
in either file records the shared ancestor. Same fault as the verbatim firewall,
`review`'s span diff and `zones score`'s `unseen` row — two inputs that turn out
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

## The reading-discipline record (keying_spec.md §5's case files)

Moved here 2026-08-05, when §5 was compressed to rule → instrument → record per
class. The reason for the move is itself a finding: the 1-039…1-044 reader batch
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
