# The encyclopedia, and the reading view over it

Two things that arrived together because neither is much use alone: a store of
entities the corpus can point at, and a browser that shows a collated page with
those entities beside it. This document owns the store's format, the rule that
decides when a machine may link a form, and the design of the view.

## Why an entity store at all

`@ref` was refused outright until this milestone — `validate` errored on
`@ref`, `@key` and `@nymRef` on any `<name>`, because there was nothing to
resolve them against and **a pointer to nothing is worse than no pointer: it
reads as resolved**. The deferral was recorded in `docs/open-questions.md` under
"Corpus-stable identity", along with the shape the answer would have to take.

So the store came first and the lifting followed. `entities/` is the referent,
`validate` checks every pointer into it on every run, and the refusal survives
in narrowed form: `@key` and `@nymRef` are still errors, because identity gets
one spelling here or "is this name linked" becomes a question with three places
to look.

## An identity is `class:slug`

Always, and the class is half the name rather than a prefix on it.
`person:jochelson` is the man; `source:jochelson-yukaghir` is the book he wrote;
the same string names both, on the same page, and the book cites him by surname
alone. A scheme without the class resolves one to the other silently.

The class lives twice, deliberately. On disk it is the directory —
`entities/person/jochelson.md`, because a colon in a filename is a portability
trap. Inside the file it is the first half of the `#` heading. `entity check`
compares them, and the reason is the ground-truth loss: **a file's role must not
live only in its directory name**, or nothing can tell what a file is once the
directory is gone.

In TEI the class is a private-URI prefix, one `<prefixDef>` per class in the
corpus header's `<encodingDesc>`, so `ref="place:markova"` resolves to the file
on disk by machinery TEI already defines. `harness tei header` checks that the
declared set is exactly `entities.ENTITY_CLASSES` — the same two-files-one-fact
gate the provenance ranks get, for the same reason.

### The classes

`ENTITY_CLASSES` maps each class to the `<name @type>` it corresponds to, or to
`None`:

    person → anthroponym    people → ethnonym     place → toponym
    water  → hydronym       animal → zoonym       being → mythonym
    event  → event
    language, taxon, institution, source → (none)

The vocabulary is its own rather than `NAME_TYPES` verbatim, because a class is
written into every `@ref` in the corpus and wants to be `person:`, not
`anthroponym:`. The mapping is what holds the two together, and `validate` uses
it to refuse a `<name type="toponym" ref="event:…">`.

**The four with no name-type are why `<rs>` exists here.** `NAME_TYPES` is
scoped to what a reader of a page can see and record; it excludes `taxon`
outright and has no member for a language or an institution. Those are exactly
the entities a trigger table finds reliably, and linking them says "this string
refers to that entity", not "the page marked a proper noun".

## The file

    # event:jesup-expedition — Jesup North Pacific Expedition

    - status: ratified
    - since: 1-021
    - link: wikidata:Q1683389
    - geo: 66.05 -169.6
    - within: place:chukotka
    - authority: jochelson1900

    ## triggers

    | form | auto | note |
    |---|---|---|
    | Jesup North Pacific Expedition | yes | the full printed title |
    | Jesup | no | also Morris K. Jesup the man |

    ## gloss

    Free markdown, authored English, CC BY.

Parsed on the `data/readings.md` precedent: heading-sliced, **NFD on read**,
absence is `{}`. NFD matters more here than tidiness — a trigger the store holds
precomposed silently fails to match a page that holds it decomposed, and a
silent miss is the failure class the project is organised against.

- **`since:` is required.** The page whose reading prompted the entry. Every
  apparatus store that skipped this is now unauditable; `data/toc.json` is the
  standing case and a logged defect.
- **`status:`** is `proposed` or `ratified`, and only a human moves it.
- **`geo:`, `within:` and `area:`** are the atlas's, below. `within:` must
  resolve and the chain must be acyclic — a cycle would hang a tree walk rather
  than fail it. `area:` names a shape in `data/geo/` and must resolve there; a
  shape *kind* may never be an entity class, for a reason worth reading before
  adding either.
- **`authority:`** may cross-link `data/authorities.json`. Resolving a `<bibl>`
  to that key is still deferred; `BIBL_IDENTITY_ATTRS` is untouched.
- **`link:`** holds an *identifier*, never a URL — `wikipedia:Chukchi_people`,
  not the address. `edition_ui.LINK_KINDS` maps the prefix to the address and to
  the site's mark, so a site that moves its paths costs one line there rather
  than an edit to every record. Repeatable.
- No `canonical:` field — the heading carries it, so there is one place for it.

**One entry names another in double brackets**: `[[people:chukchee]]`, in a gloss
or in a trigger note. A bare `class:slug` in prose was unclickable and, worse,
indistinguishable from prose that merely mentions the shape of an identity — the
brackets say "this is a reference", and `entity check` then **refuses one that
resolves to nothing**, on the same argument as a dangling `within:`. A gloss is
escaped before anything else and gets `*em*` and `` `code` `` besides, because
the records already use them.

## When a rule may link a form, and when it must ask

`entities.auto_forms` decides, from the store alone, and all three conditions
are mechanical:

1. **Exactly one entity claims the form.** Two claims make it ambiguous *by
   construction*, whatever either file says. `people:chukchee` and
   `language:chukchee` both claim "Chukchee" and both are right; only the
   sentence decides, and neither author can see the other's claim. This is why
   the rule reads the whole store and not the entry.
2. **That claim says `auto: yes`** — the author's declaration that the form
   means this entity wherever it appears. Bare "Jesup" does not qualify even
   though one entity claims it, because the man it is named after is in the book.
3. **The entity is ratified.** A link resting on an unaudited entry would let
   the store's unread half into committed TEI.

Everything failing any of the three is still surfaced — as an `<!-- entity
candidate -->` comment in the generated page and a row in `tei context` — because
a suggestion a reader disposes of is the point. What is refused is the *silent*
link.

Matching is whole-word, case-sensitive, NFD, longest-first, and
**whitespace-flexible across printed line breaks**: `1-021` sets "the Jesup
North / Pacific Expedition" across two lines, and a matcher that stopped at a
line end would miss exactly the multi-word triggers reliable enough to link.

**One matcher, three callers.** `entities.match` is what `tei generate` links
with, what `tei context` reports to the reviewer, and what `validate` re-derives
`#mz` against. Three implementations would be three witnesses that are one, and
they would drift in the direction that hides the drift. `generate.page_blocks`
exists for the same reason: the generator and the context field must join the
page's lines into blocks *identically*, or the table and the file disagree about
which questions are still open.

## `#mz`, and why it is admissible

The fifth provenance rank, on exactly the terms `#gt` was admitted and nothing
more. It says: a human wrote a trigger row and ratified the entry; a rule applied
it here. No model chose it, so `#llm` is false; no human read this page, so `#ed`
is false. The responsible act happened one artifact upstream.

**It is not taken on trust, and that is its whole licence.** Every `#mz` link is
re-derived on every validation run — entry present, still ratified, trigger
intact, still uncontested, element text still matching. Weaken the entry, delete
the trigger, or let a second entity claim the form, and every link resting on it
fails. `harness/tests/test_entity_links.py` pins each of those failure modes,
because a rank that quietly stopped being checked would look exactly like one
that was.

It is confined to `@ref` on `<rs>`. A Tier-1 span claiming `#mz` is refused in
both validation modes: a rule may say what a string refers to and may never
originate a reading of a glyph.

## Who writes what

| act | who | how |
|---|---|---|
| propose an entry | a collator, or the coordinator | `entity new` — always `proposed` |
| ratify one | a human | `entity ratify --commit`, or the browser |
| amend an existing entry | a human | by hand, or the browser |
| link a form by rule | `tei generate` | `resp="#mz"`, re-derived every run |
| link one by reading | a collator | `resp="#llm"` |

**Collators propose, and that is safe because a proposal is inert.** `entity new`
writes `status: proposed`; `auto_forms` links only ratified entries; `ratify` is
not on the collator's surface. So nothing a model mints can reach another page by
itself. What a collator may not do is hand-edit the store or touch an entry that
exists — a trigger added to a ratified entity changes what gets linked on every
other page, and one page is the wrong vantage for that. The guard hook enforces
both: reads allowed, file writes refused, `entity new|list|show` on the Bash
surface and `ratify` off it.

After a batch, the coordinator reads the proposals **against each other**: two
collators meeting the same man on two pages mint two slugs for him, and only the
coordinator sees both. Merge before ratifying, never after — a ratified id is one
other pages' `@ref` may already point at.

## The reading view

`harness edition serve` (port 8734). Committed `tei/` only: `mz/tei/` is a draft
nobody has read, and an end-user preview is the last place it belongs.

**`--drafts` shows it anyway, and turns the same server into a workstation over
the generator's output.** The flag exists because `tei generate` is being fixed
and the fastest way to judge what it emits is to read it as a page rather than as
XML. What it does not do is blur the two: the draft is marked in the listing, on
the page itself and beside every search hit — on the page because a URL typed
straight in skips the listing that would otherwise carry the warning — and it is
read-only, since a store that can be edited here is a store that needs an
adjudication story this does not have.

**It reaches `mz/tei/` by naming it.** There is no view over the tei pair, and a
symlink farm here is a defect rather than a convenience: nine callers read "a file
is in `tei/`" as "somebody collated this" — `_collated`, the folio fold, the seam,
`validate`, `dispatch`, `pipeline`, `tei diff` — and to every one of them a link
is indistinguishable from a signature. One such farm existed, of 274 links, and it
made every draft a collated predecessor: `expected_folio` then predicted a folio
for a page with nothing collated before it, which is precisely the manufactured
second witness CLAUDE.md's firewall rule forbids. `tei_html.page_source` is the
shape that replaced it — it hands back the rank *with* the path, so a caller
cannot hold one without the other.

**Attestations stay signed-only regardless.** An attestation says a form was read
in a language on a page; a generated page has read nothing, and this is not the
server's call to make — `_attestations` sweeps `collated`, never `readable`.

**Served by the shared web layer**, with the three editors: one FastAPI app in
one process listening on four ports, mounted at `/edition`. Its routes are
`harness/web/edition.py` and its markup the templates beside them;
`harness/edition_ui.py` keeps what a different front end would still need — the
little markup a gloss may use, what an imputed pronunciation may claim, which
fields of a record must reach a reader, and the two guarded writes.

**The templates autoescape, and that is a correctness property rather than a
tidiness one.** The page was built by concatenating f-strings, where a value was
escaped if whoever wrote that line remembered: `entity_card` escaped `canonical`
and `entity_index` interpolated the same field raw two functions later, so an
apostrophe in a gloss broke the encyclopedia index — and the search query reached
`<title>` unescaped. Exactly three things are marked safe, each a renderer that
escapes its own inputs: `tei_html`'s page HTML, `geomap`'s SVG, and the gloss
markup `edition_ui.gloss_html` builds.

**The stores are read through a cache keyed on their contents**
(`harness/web/cache.py`). Every request re-walked and re-parsed the whole
encyclopedia — `entity_index` did it twice, once for `load` and once for
`check` — and `search` re-rendered every collated page per query. Contents and
not mtime, because these stores are edited underneath the running server and a
timestamp key is not fine-grained enough to notice; the measurements are in that
module.

**Two columns.** The text, and beside it a map pane over a **stack** of cards.
Clicking an entity link or "consult the scan" pushes a card to the top; the stack
keeps what you opened, in the order you opened it, and a pinned card stays above
the rest.
It is what makes an annotated edition readable: what you consulted stays
consulted, and a footnote never costs you your place. Pins persist per page in
`localStorage`, because a pin is a deliberate act and losing it to a refresh
teaches you not to bother.

**A map is not a card — it is a pane above the stack.** There is only ever one
*here*, and a map that was a card like any other could sit in the stack twice
saying different things about where you are, or be pushed out of sight by the
next three. So: one pane, at the top, and clicking a place moves it rather than
adding to it. An entity's own page and `/atlas?at=` render it filled; the page
view ships it shut and the first click on a located entity opens it. Dismissal
is "not this one" rather than a setting — nothing is written down, and the next
such click brings it back. An entity the atlas cannot draw leaves the pane
alone: swapping a map you were reading for a sentence about an absence loses
more than it says, and the card's own rows already say it.

**Every path on that map carries the entity it belongs to**, so resting on a
name anywhere — a `contains` row, a node in the atlas tree, a word in the
running text — lights up its shape. That identity has to be carried because
nothing about a path recovers it: a drawn member is the nearest descendant
*with* a shape, found by descending through those without, so it is not reliably
the child whose name you are on; and two entities may share one polygon outright
(`people:chukchee` and `language:chukchee` point at the one Asher shape), so the
shape could not name the member even in principle. `geo.member_shapes` and
`geo.pins_under` return the entity beside the thing to draw for this reason, and
`geomap.owned` is what attaches it. The coastline claims nothing, which is
correct: no record owns it.

**A descendant with nothing to draw is on the map anyway, unpainted.** A node
with neither a shape nor a point is skipped by that same descent — so Chukotka
appeared nowhere on the Russian Far East's map and its name lit up nothing. Its
extent is what there is to offer, and offering it is legal where inferring a
*boundary* would not be: computed from what lies beneath, and a rectangle, which
nothing mistakes for a coastline. The layer is drawn transparent and only the
highlight paints it, because a box on every such node at once is a field of
rectangles over the thing you were reading. The answer is there when the question
is asked and not before. What remains unanswerable is a node with no located
issue either — Kamchatka, Chaun Bay — which has no extent to draw and so lights
up nowhere. That is the absence `geo verify` already reports, and there is no
honest box to invent for it.

**A framed place is drawn to itself.** A map frames on its parent's extent —
that is what makes a shape mean something, the Small Anui saying where it is
only with the Kolyma around it. But a node that *is* its extent has nothing to
gain from it, and Chukotka and the Russian Far East came out pixel for pixel
identical: the RFE has no parent, so both fell back to the RFE's own box. So the
parent frames a shape or a point, and a framed node frames itself — at the cost,
still open, of no longer showing where it sits.

**What gets prefetched is wider than what is drawn**, and the fragment says so
rather than the drawing implying it. Being on the map is a strong condition: the
Omolon has a shape of its own and is still on no layer of the RFE's, because the
descent stopped at the Kolyma above it, and Markova is a point three levels down
past `pins_under`'s depth. Both are a click away. So `geo.relatives` — every
ancestor and descendant at any depth — rides in `_map.html`, and the pane warms
that union with its own `data-ent`s when it loads. That is the whole of "an entry
preloads its ancestors and descendants".

**Resting on a link fetches its card, and resting longer floats it**
(`static/js/hover.js`). Two behaviours over one fetch, memoised by URL — the one
string this and the stack both already hold, so a card rested on before it was
clicked opens with nothing to wait for. The preview renders the *same*
`?partial=1` fragment the stack renders; there is one template per kind of card
and this adds no second one.

A floating preview used to be argued against here, and the argument was that a
tooltip which vanishes is no substitute for a stack. It is not, and the preview
does not try to be one: it never replaces the click, it holds nothing the card
would not, and it is `pointer-events:none` — the click lands on the link
underneath, and nothing can be *done* in a preview. It answers the question you
have *before* clicking — is this the one I mean? — and the stack answers
everything after. Being pointer-inert is also what stops a preview opening a
preview, which is why it loads safely on a page that is itself a card.

**That fragment deliberately carries no map**, which is why an entity's page
composes the entry and the pane rather than putting the map inside the card.
Both a preview and a card in the stack are read *while* the pane is showing the
geography, and the same hover that floats the preview is lighting the shape up
over there — a second copy inside the card would answer a question nothing was
asking, at a map render per hover.

None of it is apparatus: reader view hides `.flag` and flattens `.unsettled`,
because those are the edition talking about itself, and a preview, a highlight
and a link's colour are the edition's own content.

**Prev/next at both ends of a page**, and the arrow keys. Neither anchor claims a
`tabindex`: they held 1 and 2 while `tei_html` numbered the text's links from 3,
one number in three files — and `edition.js` counted the anchors and then
addressed them by attribute value, so the first and last page of any listing,
which have only one neighbour, left a gap that put the last link on the page out
of reach. The up/down walk now indexes the list by position and the neighbours
have left it, which is what makes two copies of the block free.

**A link's colour says what class it points at**, in five families over the
eleven — geographic, natural, human, abstract, and the lexicon's own orange.
Eleven hues would be several pairs nobody could tell apart, twice over for dark
mode. Nothing new is emitted for it: the class is the prefix of `data-ref`, which
is the identity verbatim, so `edition.css` reads what the corpus already carries.
That makes the stylesheet a *third* copy of `ENTITY_CLASSES` — the corpus
header's `prefixDef` set is the second, held by `harness tei header` — so it gets
the same treatment, and `test_edition.py` fails on a class with no rule or with
two. The abstract family is deliberately not `--mark`: that is the apparatus
colour, and an event link drawn in it would read as an editorial mark on the
word.

**The encyclopedia index is a tree over the class**, two levels and no deeper.
`within:` exists and the atlas draws the forest over it, but that is the
*geography* tree — nothing yet makes a people a child of a people — so this
groups and stops rather than claiming a hierarchy the store does not hold. Every
class appears, including the four nothing is filed under: a list of only the
populated ones would show half the vocabulary while looking complete.

**Two audiences, one renderer, one toggle.** The apparatus is visible by default
— an unratified span is marked, an editorial comment is a flag that opens —
because the people reading this now are auditing it. **Reader view** hides all of
it. Both are the same HTML with a class on `<html>`, set before first paint so it
never flashes, so the audit view cannot drift into showing something the reading
view lacks.

**A comment in the file renders as a flag rather than as nothing.** A collator's
unanswered question is the honest state of the page, and an edition that tidied
it away would present a draft as finished — the failure this project is arranged
against, appearing at the last possible moment.

**A Tier-1 form is a link too**, into `/lexicon/<lang>:<form>` — `ckt:Uweˊlen`,
url-encoded, the key NFD like everything else so the same word reached from two
pages opens one card. What it opens is **deliberately almost empty**: the form,
its language, the committed pages it is attested on, and a line saying no entry
stands behind it yet. There is no lexicon store — `harness lexicon lookup`
recomputes an index per run and is a reader's instrument rather than a published
object — and an empty card that admits it is empty is worth more than a link that
goes nowhere. It is also the shape an entry will fill.

Attestation is whole-element equality, not a substring search: `Qeˊñ` inside
`Qeˊñu` is the boundary the Tier-1 machinery protects everywhere else.

## The pronunciation on that card, and why it may be there

The card also carries `/uːweːleːn/` and a speaker. Both are **imputed**, labelled
so, and the label is the load-bearing part.

**The firewall is not what this answers to.** `harness/ipa.py` reads no scan and
proposes no glyph identity: it is a rule table applied to a form a human already
keyed and ratified, so nothing here can adopt a reading or promote one. What it
answers to is the other governing concern — fluent nonsense — because IPA *looks*
like a finding. Hence: the pill says imputed on every card, a character with no
row makes the whole form `partial` and is named rather than skipped, and the
speaker's tooltip says outright that espeak is reading the phonemes with no
Chukchi voice behind it. The sketch is two guesses deep and says which two.

**The table has two grades and one abstention rule.** `myth` is Bogoras's own
account of his notation in the front matter to *Chukchee Mythology* (1910) — the
same notation this volume sets, described by the man who devised it. `key` is the
p. 10 key, already binding apparatus here, and it supplies the unmarked ASCII
sorts that account does not reach (`c` is English *sh*, `j` is French *jour*, `x`
is *Bach*) plus the seventh member of the palatalization series. Where a source
gives two values — `g̣` is ɣ ~ ɡ, `ʟ` is ʎ̥˔ ≈ ɬʲ — the **first** is emitted and
the row is reported `hedged`; choosing per row by which value looked better would
be judgement dressed as a table. Where a sort has only a *gloss* — "like *a* in
*make*", "velar r" — there is **no row at all**, because turning a gloss into a
symbol is a judgement and not a lookup. Same for U+0027, which is both the
spirant and the pause mark and which `keying_spec.md` says not to propose.

Stress is dropped: U+02CA follows the stressed vowel where IPA's `ˈ` precedes the
stressed *syllable*, and placing it needs syllabification. It still earns its
keep on the way out — `au` is one diphthong and `aˊu` is two vowels, because
longest match sees the mark standing between them.

**580 of the corpus's 609 native forms resolve completely** (`lexicon ipa --all`).
The 29 that do not are a worklist, not noise: 6 want a row for plain `g`, 15 carry
`ṛ`/`ḷ`/`š`, 6 are European names sitting inside a Tier-1 span, and 2 carry a
curly apostrophe the Tier-1 ASCII policy forbids — a ground-truth defect the
imputation happened to surface.

**The audio's phoneme table carries its own witness.** `harness/speech.py` is the
Moll reader's `tts.py` with a new table, and the one thing added to it is that
each row records *what espeak read that mnemonic back as*, measured in a frame,
with the test comparing the table against the installed binary rather than against
a symbol someone hoped it matched. The Moll pass found `gruut-ipa`'s truncation by
timing the audio, which is a symptom; asking espeak to say what it thinks a string
is shows the missing segments outright. It caught two rows here — a bare `r`
becomes the English approximant ɹ before any vowel, and `r^` renders while
swallowing whatever follows — and one sandhi, an English linking ɹ inserted
between a schwa and a following vowel, which five `-qäi`/`-qäu` forms hit and a
zero-length pause suppresses.

Speech needs **no Python dependency** — it shells out to the system `espeak-ng`,
which `edition serve` probes once at startup and reports on its banner. Without
it the speaker buttons disable themselves on the first press and everything else
works; that is a supported state, not a broken one.

`/tts/<ipa>` is a **pure function of the string in the URL** and deliberately does
not check that the IPA is one this edition imputed, which is what makes it
cacheable on the string alone. Nothing from the URL reaches a command line: the
phoneme string handed to espeak is assembled only from table values.

**Crops are computed, never cut.** A figure or a line is the whole page raster,
scaled and offset inside a clipping box, in percentages (`tei_html.crop_style`).
The browser fetches one image per page however many crops the stack holds, and
nothing on disk has to be kept in step with the ALTO. Learned from the Moll
dictionary's reader in `scratch/`, which had a pixel-scaled version first and
lost the right-hand end of every crop to a panel that was never the assumed
width.

**It writes `entities/`, and the click is the human act** — the `zones edit`
precedent, not a new licence: a loopback server, a tracked store, git as the
witness. Ratifying in the browser is the same act as `entity ratify --commit`,
done where the evidence is. Every write runs `entity check` on the result and
**rolls back** one that would leave the store incoherent, because every `@ref` in
the corpus resolves against it and a broken store breaks pages nobody is looking
at.

## The atlas

`within:` was always going to carry it, which is why `entity check` refused a
dangling parent and a cycle long before anything read the store that way. What
this section adds is the shapes, the authored link to them, and the view.

### The store: `data/geo/`, compiled and tracked

Three sources, none of them in the repository: 24 watershed delineations and a
53 MB world language atlas in `scratch/` (gitignored, one of them a symlink into
a download directory), and Natural Earth for the coastline. `tools/build_geo.py`
compiles them to `data/geo/`, which **is** tracked — a clone can neither rebuild
this nor be told why the atlas is empty. The same split `scans/` has: a `tools/`
script builds from what only one machine holds, the harness reads what is
committed. `shapely` is a build-time dependency declared inline (PEP 723);
`edition serve` reads plain JSON and imports nothing new for it.

`data/geo/SOURCES.md` is authored by hand and is a **precondition of the build**,
not a by-product. Asher 2007 is CC BY 4.0, so its citation goes in the corpus
`teiHeader`'s rights statement as well — this file ships with the repository and
the reading view does not.

**One source's licence is heavier than its content and is not settled.** The
basins come from Global Watersheds (mghydro.com) over MERIT-Hydro, which is
dual-licensed **CC BY-NC 4.0 or ODbL 1.0**: the first forbids commercial use by
anyone who clones this, and the second is share-alike on the *database*, which
`data/geo/watershed/` is. Which branch this edition takes, and whether those
files must therefore carry ODbL rather than the corpus's CC BY, is a human's
decision recorded as open in `SOURCES.md`. Nothing is blocked meanwhile — the
server is loopback and a repository is not a distribution — but a rights
statement quietly saying "CC BY" over those files would be a claim with nothing
behind it.

The compilation is roughly 10:1 (9.8 MB of watersheds to ~1 MB): the top two
Strahler orders of each river network, simplified at 0.01°, rounded to 3
decimals, and the properties every feature repeated hoisted to the collection.
Base layers are simplified an order harder — a coastline is context, always seen
at whole-region scale, and carrying it at subject resolution put 70 KB of
Eurasia into a card showing a 2,800 km² basin.

### The antimeridian is a build problem before it is a rendering problem

Chukotka spans 180°, where a ring stepping 179.9 → −179.9 is a self-crossing
horror in any planar library. Two shapes of the hazard: a regional shape *cut*
at the meridian into two halves (RFC 7946 says to do that), and a global base
layer whose Eurasia polygon runs from −10° to 190°, which a naive "add 360 to the
negatives" pass tears in half.

One recipe for both — clip in **native** coordinates against two boxes either
side of the meridian, shift the western result by +360, union. A cut shape's
halves meet at exactly 180 and the union welds them; a global polygon is clipped
before anything is shifted, so nothing tears. Everything downstream lives in one
continuous window (`[60, 420)`, so >180 is west of the meridian) and containment,
extents and culling are all ordinary planar arithmetic.

**What it will not do is close a shape up.** Asher's Chukchi polygon has ten
vertices on 180° and no counterpart west of it: East Cape and Uelen, Chukchi-
speaking by every account including this book's, are outside it. The build
reports that on every run and draws it as it is. Extending a speaker area past
where its publisher drew it would be inventing evidence in the one place a reader
would never check.

### `area:`, and why it is typed rather than matched

A new optional entity field naming a shape: `area: watershed:anadyr`.
**Human-authored, and that is the point** — identifying a toponym Bogoras wrote
in 1904 with a polygon a modern delineation service returned is an assertion
about the world, and a rule that matched them by name would be the confident
guess this project is arranged against. `watershed:main` and the English word are
one keystroke apart in that file listing.

A shape kind is held **disjoint from `ENTITY_CLASSES`** — `langarea:`, never
`language:` — because an entity file carries `within: place:chukotka` two lines
from `area: langarea:chuk1273`, and a reader who cannot tell them apart by
looking is one keystroke from an `area:` that resolves as an entity reference.
`entities.parse` refuses a colliding kind outright.

`entity check` gates exactly one thing here: that the id resolves. That is a
fact about names, like `within:` resolving. Everything geometric is
`geo verify`'s and **reports**.

### A composite `area:`, resolved at lookup and never materialized

Several shapes, comma-separated — `area: langarea:chuk1273,
base:chukotka-east-of-meridian` — because no source draws together what a human
can see belongs together. The identity of a composite **is** its canonical
member list, sorted and comma-joined, so nothing mints a name and two spellings
of one union cannot exist.

**It is not a row in the store.** `index()["shapes"]` still enumerates precisely
what the build wrote — `geo list` and `verify`'s `unclaimed` census
`data/geo/`, not `entities/` — and only `.get()` and `in` resolve a composite,
and only when *every* member is a real row. So a union is re-derived on every
run and fails rather than goes stale, which is the same property that lets `#gt`
and `#mz` exist at all; and `entity check` still refuses one naming a shape that
does not exist, with the message naming the member rather than the whole field.
A composite counts as a claim on **each** of its members, or the members would
read as unclaimed while the union read as a shape `data/geo/` does not hold —
two wrong answers out of one right authored field.

`geo.shape()` returns the members' features **concatenated**, not unioned: this
module imports no geometry library on purpose and every operation downstream is
per-polygon. That concatenation is what turned up a latent bug in `in_shape`,
which counted ray-crossing parity across every ring in a collection — the same
arithmetic as per-polygon parity only while no two polygons overlap, and a hole
punched exactly where two shapes agree otherwise.

### Item 7: the land east of the meridian is land, and the claim is a human's

Asher's Chukchi polygon stops at 180° and this edition does not move it. What it
adds is `base:chukotka-east-of-meridian` — Natural Earth land, cut by a declared
topological rule (`data/geo/SOURCES.md` has the rule and why a longitude box
cannot express it), asserting **nothing whatever about speech**.

The join is then one human act, in the entity file, where a reader can see whose
it is:

    harness entity locate language:chukchee \
        --area langarea:chuk1273,base:chukotka-east-of-meridian --commit

That separation is the design. Sourced geometry in the store; the inference in
an entity, under a `status:`, with a name on it. A shape kind that meant "this
edition inferred it" would have put the inference back in `data/geo/`, where
every consumer treats a row as a thing a source drew.

### The witness inside the river chain

A basin delineated from a tributary's outlet is contained in its trunk's *by
construction*, so `within:` on a `water:` entity can be checked against the
geometry — the Wolverine inside the Small Anui inside the Kolyma. It is a real
second witness, and it is the reason the river hierarchy was worth authoring in
the store rather than inferring from the shapes.

Three things keep it honest.

**It names the pair, never a culprit.** A disagreement says one of two authored
facts is wrong and the geometry cannot say which.

**It respects the source's declaration of precision.** The delineator reverts to
a coarse DEM above 50,000 km² and says so in the file it returns. Every
containment pair in the store today has such a member, and a true tributary
measured against a coarse parent lands at 0.70–0.87 rather than 1.00 — the Small
Anui visibly pokes outside the Kolyma outline on its own map. Reading that as
"disagrees" would make the check a machine for rejecting true rows on the
strength of a limitation the source announced in advance.

**The floor sits in a measured gap, not near either side.** Relations the book
and the map both support land at 0.68–0.82; a river paired with a basin it has
nothing to do with lands at 0.00–0.11. Kanchalan and Tumanskaya came back at 11%
and 0% against the Anadyr, which is how they ended up as its siblings rather than
its tributaries.

A `geo:` point outside its own shape is likewise reported with a distance and is
not a defect: a river's natural point is its **mouth**, which sits on the very
boundary the basin was delineated from. `water:anadyr` is 0.59° out, at the
estuary. And a shape two entities claim is legal — `people:chukchee` and
`language:chukchee` both point at the one Asher polygon, and forcing a choice
would be this edition deciding something the source does not.

### The map: server-rendered SVG, no tiles, ever

The server is loopback and the edition is meant to be self-contained, so there is
no map library and no tile fetch. One `<svg>`, shapes as `<path>`, every
coordinate projected on the server. It suits the material: the polygons *are* the
content and there is no imagery to want.

**Lambert azimuthal equal-area, centred per map on its own subject.** Not taste.
It goes through `sin`/`cos` of longitude, which are periodic, so 185° and −175°
project to the same point and no window convention can leak into the picture —
the antimeridian is closed for good rather than merely handled. Equal-area makes
the one comparison a reader actually makes, this basin against that one inside
the same frame, mean what it looks like. Per-map because the store spans 137° of
longitude and a single centre would visibly shear the Amur; nothing compares two
separately-framed maps, so there is nothing to lose.

**A drainage divide is not drawn in the colour of the rivers inside it.** The
subject's outline goes dark red when its `area:` names a watershed, which is why
`render` takes a `mark` it does not compute: it sees paths and cannot tell a
basin from a coastline, and inferring one from the shape of a ring is the kind of
guess this project is arranged against. The predicate is the *shape's* type —
`area:` is typed, and `watershed:anadyr` says where the polygon came from. Every
watershed in the store happens to sit on a `water:` entity today, so the entity's
class would answer the same; it is a different question, and only this one says
why the boundary must not be blue. The members are left in the accent: they are
the nearest descendants that have a shape, chosen without reference to what drew
them.

Every map's `viewBox` is the same 1000-unit square and the element carries no
width or height — `tei_html.crop_style`'s discipline, and normalizing the frame
is also what lets one decimal place be enough at every zoom. Emitting projected
radians at fixed precision gives a continental frame more resolution than any
screen and a small basin about two hundred visibly-faceted steps across.

A frame is measured **along** its box's edges rather than at its four corners: at
70°N the top edge bows well past them, and a frame taken from the corners clips
the shape it was computed for.

### The tree

`/atlas` is the `within:` forest, each node's map beside it, **scoped to located
subtrees** — a root is an entity with no `within:` that has somewhere to put on a
map, itself or below it. Without that scope every person and source in the store
is an atlas root, and the atlas becomes a second encyclopedia index with a map
stapled to it — the same names, grouped by nothing, beside a panel that has
nothing to draw for most of them. The two views answer different questions: the
index is the whole store by class, this is the located part by containment.

**A shapeless node is framed by its members, and the map says so.** No source
holds a polygon for Chukotka or the Russian Far East, and none should: they are
tree structure, not shapes. So a node without `area:` gets the padded union of
the extents beneath it and is captioned as framed by its members rather than by
an authored boundary. A frame is a viewport, not a claim — which is why computing
one is legal where inferring a *boundary* for Chukotka would not be.

**A node draws what lies beneath it**, back to front: land, siblings, members,
the parent's outline, the subject, its rivers. The members are the nearest
descendants that *have* a shape, descending through those that do not — one
level down is right for the Kolyma, whose children are basins, and wrong at the
top of the tree, whose children are structure: the Russian Far East's are
Chukotka and Kamchatka, which no source draws, so a one-level rule left its map
showing an arbitrary half of the country.

The extent union always includes the children, even where the node has an extent
of its own. Stopping at the first source found was a bug invisible in every number and
obvious on the first map: a parent with a `geo:` point framed on that point
alone, and Uelen — inside the Chukchee Peninsula by the store's own `within:` —
fell outside its own parent's map.

An entity with no shape, no point and no located descendant says so rather than
rendering an empty frame. Chuvan, Kerek, Siberian Yupik and Tundra Yukaghir are
the live instances: `index.json` carries them as `absent` rows with the reason,
because an entity pointing at nothing and an entity nobody has got to yet look
identical from outside, and only one of them is finished.

### Providing a coordinate or a boundary

`geo verify` reports the worklist from both ends. `unclaimed` is what the atlas
holds that no entity points at; **`unlocated`** is its inverse — entities inside
a subtree the atlas can draw that carry neither `geo:` nor `area:`, so they ride
on a parent's frame and put nothing on it. Scoped by the tree rather than by
class, because every person and source in the store is unlocated and always will
be, and a worklist mostly made of rows nobody will act on is one nobody reads.
Its `wants` column separates an entity that needs a coordinate from one already
framed by its members: asking for a boundary for Chukotka is the one thing this
atlas refuses to invent.

`harness entity locate ID` answers a row of it, setting `geo:`, `area:`, or
both. It re-parses the file before writing, as `entity new` does, and refuses an
`area:` naming a shape `data/geo/` does not hold. That is the whole of the
workflow, and it ends the hand-edit: item 11 alone was four of them.

**Where a bound comes from is still a provenance question**, and there are only
two answers so far. Either a source draws it — the three Natural Earth 1:10m
gazetteer features are that case — or nothing in hand does, and the entity gets
a point and says so in its gloss, as `water:bering-strait` does. Tracing a shape
by hand over a georeferenced plate of the book's own maps is the third answer
and is **not built**; it is deferred with the rest of the land-painting work.

### What is still open

Eleven shapes are unclaimed (`geo verify`), most of them basins the book names
in passing — the Oloi is the interesting one, measuring 80% inside the Kolyma and
68% inside the Omolon, which is exactly the case the two-witness rule forbids
settling from the geometry alone. The watershed delineation **service is not
named** in the files it returned and is the one provenance row weaker than its
content. And `place:paren`, from the original sketch, is unauthored: the book
names it, and no coordinate for it is in hand that is not a guess.
