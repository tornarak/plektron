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

Repairing one is `harness ocr adopt-gap` — the one tool besides `restore` that
writes into `gt/ocr/`, geometry only, never `CONTENT`; its full contract and the
image-cost ladder are `.claude/skills/rebuild-groundtruth/`'s (`SKILL.md` and
`dispatch.md`).

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
