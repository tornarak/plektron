# The encyclopedia, the lexicon, and the reading view over them

Things that arrived together because none is much use alone: a store of entities
the corpus can point at, a second store of what an editor has written about a
native word, and a browser that shows a collated page with both beside it. This
document owns both stores' formats, the rule that decides when a machine may link
a form, and the design of the view.

The two stores are shaped by the same question answered twice. An entity entry is
mostly authored, because who Nordenskiöld was is not derivable from the page; a
lexicon entry is almost entirely derived, because a form's sound, its pages and
its printed gloss all are. What each file holds is what nothing else could say.

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
corpus header's `<encodingDesc>`, so `ref="place:markovo"` resolves to the file
on disk by machinery TEI already defines. `harness tei header` checks that the
declared set is exactly `entities.ENTITY_CLASSES` — the same two-files-one-fact
gate the provenance ranks get, for the same reason.

### Renaming one, and why the entries carry modern titles

An identity is what every `@ref` holds, so moving one is cheap exactly as long
as the corpus holds few of them. It held **none**: `tei/` had no collated page
when this was done, and the 684 refs in `mz/tei/` are derived and come back from
`tei generate`. That is the whole reason `harness entity rename` exists and the
whole reason it was used when it was — the same pass a year later would mean
amending signed pages.

`entity rename OLD NEW --canonical NAME` moves the file, rewrites the heading,
and re-points every `within:` and `[[wikilink]]` in the store. Three rules in it
are load-bearing:

- **It refuses when committed `tei/` names the old identity**, and only reports
  for `mz/tei/`. A rule may not rewrite a page a human signed; a derived one it
  need not rewrite at all. The `links` table says which store each stale ref is
  in, because the two are the same string in the same attribute and only the
  directory tells them apart.
- **The old canonical is filed as an alias.** Not politeness:
  `detectors.entity_forms` splits canonicals into the corpus's proper-noun
  dictionary, so a rename that only moved the heading would take the book's own
  spelling *out* of the dictionary and start reporting it as a transcription
  candidate on every page that prints it. Skipped where the entry already lists
  the form, since `parse` refuses a form listed twice.
- **The class may not change.** That is a delete and a create — the class is
  half the identity, so every `@ref` would mean a different thing afterwards.

**The titles that moved were the ones the repo could already witness.** The
brief was "what gets the most results today", which is a judgement, so the pass
was scoped to entries where a second witness was already committed: a
`wikipedia:` link whose article is titled differently, or an `area:` naming a
shape whose slug carries both names — `watershed:dry-or-maliy-anyuy` is
the geo store's own adjudication of the same question, made when it was built.
Twelve entries moved on that evidence and one, `people:inupiat`, took the title
alone because a slug cannot hold `ñ`.

Everything else stayed at first, including cases where the modern name is not in
doubt — `Gilyak`/Nivkh, `Lamut`/Even, `Kamchadal`/Itelmen, `Tungus`/Evenki. The
stated reason was that nothing in the repo attested those, so the witness would
have been a model's recall, which is the one thing this store does not accept
for an identity.

**That reason stopped being true, and it is worth being exact about when.** The
moment the `language:` entries were filed against their `langarea:` shapes, the
repo did attest the mapping: `data/geo/` names its own shape *Even (Lamut)*, and
`langarea:itel1242` is West Itelmen. The four moved on the editor's word, with
the shape store agreeing. `Indighirka`/Indigirka still has no witness and still
has not moved — a river's spelling is not settled by a langarea.

`person:bogoras` is the deliberate refusal. Wikipedia files him as *Vladimir
Bogoraz*; the book prints *Waldemar Bogoras* on its own title page and the
English literature cites him that way. The witness and the brief disagree, so
the entry did not move.

**The miss list is identical before and after** — 361 tokens either side. That
is the check that matters: the dictionary gained the modern spellings and lost
none of the book's, which is precisely what the alias rule is for.

### The classes

`ENTITY_CLASSES` maps each class to the `<name @type>` it corresponds to, or to
`None`:

    person → anthroponym    people → ethnonym     place → toponym
    land   → toponym        water  → hydronym     river → hydronym
    animal → zoonym         being  → mythonym     event → event
    language, taxon, institution, source → (none)

The vocabulary is its own rather than `NAME_TYPES` verbatim, because a class is
written into every `@ref` in the corpus and wants to be `person:`, not
`anthroponym:`. The mapping is what holds the two together, and `validate` uses
it to refuse a `<name type="toponym" ref="event:…">`.

### The four geographical classes

`place:` a terrestrial **point** — a village, a camp, a cape, a single peak.
`land:` a terrestrial **region** — a peninsula, a range, an upland, an island, a
district. `river:` a watercourse and the **basin** it drains. `water:` a body of
standing or open **water** — a sea, a bay, a strait, a lake.

It used to be two, `place:` and `water:`, and each held two unlike things: a
village and a peninsula under one, the Anadyr river and the Bering Sea under the
other. That cost two things a class is for.

- **The atlas could not colour what it drew.** `geomap.css` had been colouring by
  *shape kind* — `region`, `watershed`, `marine` — precisely because the entity
  class could not tell them apart, and the prose beside it drew all four in one
  blue. The classes now stand 1:1 against the shape kinds they are drawn from, so
  the two views agree without either copying the other's table.
- **`within:` could not be checked at all.** "X is inside Y" says nothing
  testable while every parent might be a region; with the split, two
  impossibilities fall straight out — a *point* contains nothing, and open
  *water* holds no settlement and no drainage basin. That is `geo.NESTING`, run
  by `geo verify`, and it needs no geometry, so it speaks about every pair in the
  store rather than the dozen both of whose members somebody drew. It found one:
  Kamenskoye filed under Penzhina Bay, the village standing on the river above
  it. It deliberately does **not** flag `land:` inside `water:` — an island in a
  strait is exactly that, and has nowhere else to go.

**A name that does double duty gets an entry per class**, not one entry stretched
over both: `river:anadyr`, `place:anadyr`, `water:anadyr-bay`, `land:chukotka`.
That is also what ended the shadowing in the reading view, where the town and the
river had shared the head token `anadyr` and only one of them could be reached.

**Both toponym classes carry `type="toponym"` and both hydronym classes
`type="hydronym"`**, which is not tidiness. What a page asserts is its `@type` —
a reader saw a place-name — and whether that name denotes a point or a region is
the store's business and was never recorded on the page. That equality is what
lets `entity rename` move an entry between `place:` and `land:` while still
refusing `place:` → `water:`; the 54 entries were migrated through the verb, with
their `within:` chains, wikilinks and collated `@ref`s carried along, rather than
by a pass over the files.

**The four with no name-type are why `<rs>` exists here.** `NAME_TYPES` is
scoped to what a reader of a page can see and record; it excludes `taxon`
outright and has no member for a language or an institution. Those are exactly
the entities an alias table finds reliably, and linking them says "this string
refers to that entity", not "the page marked a proper noun".

## The file

    # event:jesup-expedition — Jesup North Pacific Expedition

    - status: ratified
    - link: wikidata:Q1683389
    - geo: 66.05 -169.6
    - within: land:chukotka
    - authority: jochelson1900

    ## aliases

    | form | lang | auto | note |
    |---|---|---|---|
    | Jesup North Pacific Expedition | en | yes | the full printed title |
    | Jesup | | no | also Morris K. Jesup the man |

    ## gloss

    Free markdown, authored English, CC BY.

Parsed on the `data/readings.md` precedent: heading-sliced, **NFD on read**,
absence is `{}`. NFD matters more here than tidiness — an alias the store holds
precomposed silently fails to match a page that holds it decomposed, and a
silent miss is the failure class the project is organised against.

**There is no `since:`.** Both this store and the lexicon carried one — the page
whose reading prompted the entry — required on the argument that an apparatus
store which cannot be traced back to a page is unauditable. `data/toc.json` is
still the standing case for that, and the argument was right. Its answer got
better: the card now derives *every* page the entry is attested on, from the
corpus, on every load.

**A `since:` is satisfied by typing a plausible ref; a derived attestation list
is not.** So the field was the weaker of the two witnesses, and the cost of
keeping it was real — it kept out entries the book plainly contains whose
attesting page happens to be among the 558 not yet transcribed, which is how the
`language:` and unclaimed-watershed seeding stalled. `entity occurrences --all`
is where an unwitnessed entry shows up now, as a row reading 0 and 0, and that
row cannot be answered by writing a number in a file.

- **`status:`** is `proposed` or `ratified`, and only a human moves it.
- **`within:` is containment in general**, and the atlas is one reader of it.
  It must resolve and the chain must be acyclic — a cycle would hang a tree walk
  rather than fail it. `entities.children` and `entities.relatives` walk it and
  read no geometry; they lived in `geo.py` while the tree was the geography's
  alone, which made a caller wanting `people:maritime-chukchi` under
  `people:chukchi` import the atlas to get it. `geo` re-exports both, since it
  is still the heaviest caller and the map's own reasoning is written there.
- **`geo:` and `area:`** are the atlas's, below, and **a record may carry one or
  the other and never both** — `entity check` refuses it. A shape *is* the
  location: `extent_of` reads it and would never look at a point beside it, so
  the point could only be a second, weaker statement of the same fact, kept in
  step by nothing. Where a point names a *different* thing — a river's mouth, a
  settlement on a bay — that thing gets its own entry, which is what
  `place:anadyr` is. `area:` names a shape in `data/geo/` and must resolve
  there; a shape *kind* may never be an entity class, for a reason worth reading
  before adding either.
- **`frame:` is where the map looks**, which is a different question from where
  the thing is: four degrees, west south east north — longitude first, unlike
  `geo:`, because it is a box, and east may exceed 180 in the atlas's continuous
  window. It overrides whichever frame would otherwise have been *derived* and
  nothing else, so `extent_of` still measures the real geometry and every member
  is still drawn. The entries that carry one are all a default getting it wrong:
  `land:northeast-siberia`, a container with no shape, whose viewBox was
  otherwise the union of everything beneath it; `land:chukchi-peninsula`, which
  frames on Chukotka by default and had thirty-four villages in a corner;
  `land:russian-far-east`, whose derived box reached 103°E on the strength of
  the Amur and stopped at 72.9°N, short of the Arctic the book is about, and
  which this edition simply declares as Baikal eastward; `water:bering-strait`;
  and `land:chukotka`, whose derived box *was* right and is frozen so it stays
  so. A parent's frame is what its children frame on. `docs/decisions.md` has
  why no frame worked at all until the projection changed with it.

  **A frame counts as a location and `extent_of` still ignores it**, which is
  not a contradiction: they answer different questions. `extent_of` says how big
  a thing is, and a *parent* sizes itself on that, so unioning a viewport into
  an ancestor's box would inflate it with padding chosen for another map.
  `geo.located` says whether the atlas can draw this at all, and a frame answers
  that by itself — it *is* the viewBox. Until they were separated, the Russian
  Far East and the Bering Strait counted as unlocated and as framed-by-their-
  members, when their frames had been written by hand precisely because neither
  was true.
- **`authority:`** may cross-link `data/authorities.json`. Resolving a `<bibl>`
  to that key is still deferred; `BIBL_IDENTITY_ATTRS` is untouched.
- **`link:`** holds an *identifier*, never a URL — `wikipedia:Chukchi_people`,
  not the address. `edition_ui.LINK_KINDS` maps the prefix to the address and to
  the site's mark, so a site that moves its paths costs one line there rather
  than an edit to every record. Repeatable.
- No `canonical:` field — the heading carries it, so there is one place for it.

### An alias says what language it is a name in

The column is `lang`, from the vocabulary in `harness/langs.py`: shortest
BCP-47, so `ru` and never `rus`, `ckt` where no two-letter code exists. It is
the same string a collated page writes in `xml:lang` and the same one
`data/authorities.json` already carries, and that is the whole reason the
spelling is not free — a fourth spelling of one code is how two stores stop
agreeing without anyone finding out.

**It was already there, in prose.** Seven entries wrote `lang:ckt` and
`lang:rus` into the *note* column: an entity's Russian and Chukchi names are
exactly what a reader of an ethnography wants, the authors knew it, and the only
place to put the fact was a free-text field nothing could read or check. Thirteen
rows moved into the column. `people:chukchi` is the one worth looking at — it
now says in a column that Чукча is Russian and oraˊwêʟ̣at is the autonym.

- **Blank means unstated**, and most of the store is blank: 128 of 141 rows are
  the book's own English, where saying so adds nothing. Requiring the column
  would have made an editorial pass out of a schema change.
- **A code outside the vocabulary is an error.** That is a typo, not a gap, and
  the two want opposite treatment.
- `entity check` reports `aliases_untagged`. A worklist, never a gate: "every
  foreign name is in the table and tagged" is a standing editorial job, and a
  gate on it would be answered by deleting the alias.

**And it buys nothing mechanical, deliberately.** It does *not* narrow
`detectors.entity_forms`: an alias suppresses `lexicon_miss` whatever language
it is in, exactly as before. So the case sprint C left open — an unmarked
romanized native form, which no mechanical test separates from an English proper
noun — is still suppressed and still open. `Tjutzchi` is now declared Latin and
still absent from the miss list. The field records the fact; nothing infers from
it, and a reader who assumed tagging one had changed the detector would be wrong.

### The entity link wins over the lexicon link, and it had to

`tei generate` encloses a Tier-1 handle in `<rs>` rather than reaching into it,
and `tei_html` renders a Tier-1 handle as a link into the lexicon. Both are
right and together they emitted **an anchor inside an anchor**, which HTML has
no such thing as: the parser closes the outer one, so the *entity* link was
discarded by the browser and every linked native toponym read as a lexicon
entry. Nothing in the markup said so — it validated, it rendered, and only a
reader clicking `Uweˊlen` and landing on a word rather than a village would find
it.

So a Tier-1 handle inside a referring element renders as a `<span>`, keeping its
class and `data-key` — still styled as Tier-1, still previewable, still counted
in the page's form census. Outside one it is a link as before.

**The lexicon entry moves to the card**, which is the better place for it
anyway: an alias whose `lang` is Tier-1 is a lexicon headword, and the alias row
is the one spot that says "this entity is called that, in Chukchi". A reader on
a linked toponym wants the place; a reader who wants the word is one click away
and now has a row that says which word.

**One entry names another in double brackets**: `[[people:chukchi]]`, in a gloss
or in an alias note. A bare `class:slug` in prose was unclickable and, worse,
indistinguishable from prose that merely mentions the shape of an identity — the
brackets say "this is a reference", and `entity check` then **refuses one that
resolves to nothing**, on the same argument as a dangling `within:`.

### What else a gloss may be written in

`*em*`, `**strong**`, `` `code` ``, `- ` bullet lists and `[text](url)`.
**Every one of them is there because a record already used it**, which is the
only argument any of them needs: `entities/people/eskimo.md` was written with a
list and an external link before either rendered, so its card showed a paragraph
of literal `- ` lines and a bare `[…](…)`. An author writing markdown in a
markdown file is not a mistake to be trained out.

No markdown library. **Escape first, then a closed set of rules** — that
ordering is the whole safety argument, and it is why a store value cannot reach
the page as markup and why each rule adds exactly the element it names. Two
details follow from it and are easy to get wrong:

- **The scheme allowlist.** `escape()` fixes the *text* of an attribute and says
  nothing about what it means, so `javascript:` in an `href` walks straight past
  it. Only `http` and `https` become anchors; anything else renders as the
  literal `[text](url)` the author wrote — visible, and therefore fixed, where a
  silently dropped link is neither.
- **`**strong**` is tried before `*em*`**, or the em rule eats the leading
  asterisk of each pair and leaves a stray one either side.

A block is a list when its *first* line is a bullet, not per line: deciding per
line would open a `<ul>` around a paragraph that happened to wrap onto a dash,
and would split every bullet the records hard-wrap. A continuation line joins
the item above it, as markdown reads a wrapped bullet.

`inline_html` — an alias note, a caption — takes the same inline rules and no
block ones, since a `<p>` or a `<ul>` inside a table cell would be wrong.

## When a rule may link a form, and when it must ask

`entities.auto_forms` decides, from the store alone, and all three conditions
are mechanical:

1. **Exactly one entity claims the form.** Two claims make it ambiguous *by
   construction*, whatever either file says. `people:chukchi` and
   `language:chukchi` both claim "Chukchee" and both are right; only the
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
line end would miss exactly the multi-word aliases reliable enough to link.

**One matcher, three callers.** `entities.match` is what `tei generate` links
with, what `tei context` reports to the reviewer, and what `validate` re-derives
`#mz` against. Three implementations would be three witnesses that are one, and
they would drift in the direction that hides the drift. `generate.page_blocks`
exists for the same reason: the generator and the context field must join the
page's lines into blocks *identically*, or the table and the file disagree about
which questions are still open.

## `#mz`, and why it is admissible

The fifth provenance rank, on exactly the terms `#gt` was admitted and nothing
more. It says: a human wrote an alias row and ratified the entry; a rule applied
it here. No model chose it, so `#llm` is false; no human read this page, so `#ed`
is false. The responsible act happened one artifact upstream.

**It is not taken on trust, and that is its whole licence.** Every `#mz` link is
re-derived on every validation run — entry present, still ratified, alias
intact, still uncontested, element text still matching. Weaken the entry, delete
the alias, or let a second entity claim the form, and every link resting on it
fails. `harness/tests/test_entity_links.py` pins each of those failure modes,
because a rank that quietly stopped being checked would look exactly like one
that was.

It is confined to `@ref` on `<rs>`. A Tier-1 span claiming `#mz` is refused in
both validation modes: a rule may say what a string refers to and may never
originate a reading of a glyph.

### A Tier-1 alias is linked by enclosing the handle, never by reaching into it

The generator used to drop every alias hit that touched a Tier-1 handle,
reasoning that a rule resolving an identity for a string whose glyphs it may not
name is the firewall's failure shape. The reasoning is right about *reaching
inside* a handle and wrong about *enclosing* one — and the store had already
made the judgement anyway: `place:anadyr` carries `Veᵋñ` as an alias, written by
a human with the corpus in view.

```xml
<rs ref="place:anadyr" resp="#mz"><foreign index="4">Veᵋñ</foreign></rs>
```

Each `@resp` is a claim about its own element. The outer says which entity this
string names; the inner says a ratified token sits here, still carrying no
`xml:lang`, so the collator's question is untouched and `tei expand` still stamps
`#gt` on the element holding the glyphs. The rule that `#mz` never carries a
glyph is honoured **literally**: the element carrying it has no text of its own.
All four nestings validate against `data/tei_all.rng`, and `tei expand` walks
elements rather than positions, so it needed no change at all.

**Only exact coincidence fires.** A hit whose span is byte-identical to a
handle's is wrapped; one that merely overlaps is dropped, as before. Coincidence
is the one relation that needs no opinion about where the form ends — an overlap
would mean the store and the detector disagree about the extent of the token, and
picking a side there is the inference this refuses.

The `<rs>` stays an `<rs>`, never a typed `<name>`: a rule may say *this string
refers to that record* and not *this is a toponym*. That is why the unglossed
gate below accepts a bare `@ref` alongside a typed name — the rule-applied link
has no `@type` to offer, by design.

A collator that later unwraps the `<foreign>` — deciding it was never a foreign
span — **leaves the `<rs>` standing**. That a word names Anadyr does not depend on
what language it is in.

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
exists — an alias added to a ratified entity changes what gets linked on every
other page, and one page is the wrong vantage for that. The guard hook enforces
both: reads allowed, file writes refused, `entity new|list|show` on the Bash
surface and `ratify` off it.

After a batch, the coordinator reads the proposals **against each other**: two
collators meeting the same man on two pages mint two slugs for him, and only the
coordinator sees both. Merge before ratifying, never after — a ratified id is one
other pages' `@ref` may already point at.

### What a gloss is for, now that the card carries the mentions

Until the mentions block existed, a gloss was the only thing on the card that
said anything, so the glosses grew to carry the explaining — which is how an
apparatus store starts editorializing. The card now lists where the entity
occurs, with the prose either side, out of the corpus itself. So:

**A gloss disambiguates; the mentions explain.** What belongs in it is what a
reader cannot get from the passages: which of two entities this is, what the
book's term covers that the modern one does not, why an identification was made,
and what the entry deliberately does *not* claim. `people:eskimo` is the model —
it exists to say that the book's word is a grouping over three entries and which
one usually stands behind it.

What does not belong is a précis of the passages. If the gloss is telling you
what Bogoras says about the Chukchi, the card is about to tell you in his own
words, twice as well and with a page number.

**A `<!-- entity note: … -->` is not a gloss.** A collator meeting a fact worth
recording reports it; the coordinator decides whether it disambiguates anything.

### Mentions on the card

Every occurrence across the pages the view is serving, linked and unlinked apart:
a linked one already carries an `@ref`, an unlinked one is an alias hit nobody has
resolved and so is the work outstanding. `entities.occurrences` is the one
implementation — `entity occurrences` passes committed `tei/` because it audits
what is committed, and the reading view passes the list it is actually serving.

**The corpus is the caller's, and that is the whole design.** Without `--drafts`
the view serves collated pages only and 404s a generated one, so a mentions row
naming a draft would send a reader nowhere. The sweep is over everything, cached
on both stores' stamps — the pages and the alias table, either of which can change
the answer — and the narrowing is a filter at the route. Keying the cache on the
mode instead would double it to answer what a filter answers.

**The source is `tei/` where a page is collated and `mz/tei/` otherwise**, which
`tei_html.page_source` resolves, handing back the rank with the path rather than
leaving it to be read off the directory — the property the symlink farm
destroyed, and why a draft row is captioned as one. `mz/tei/` is not a second
witness against the page: it is `generate.page_blocks`' output written down, so a
mention row and the page's own `<rs>` are one derivation. It is also what makes
this affordable — 3,746 rows over 105 entities and 274 pages in under a second,
where re-sweeping the ALTO through `page_blocks` costs twenty.

**One row per page, not per occurrence**, with the counts on it. "Where does
this appear" is a page question, and the per-occurrence list answered it badly:
`place:markovo` is linked four times on 1-045 alone, so the first eight rows
were four pages with the same word in them and said less than a count would have
in a quarter of the space. The snippet prefers an *unlinked* hit, because a
linked one's text is the form itself and a row reading "Markova: Markova" has
said nothing.

**An empty list names how many pages it looked at.** A bare zero cannot be told
from "never mentioned", and today it means one of two other things: nothing is
collated, or `mz/tei/` was never generated in this clone. The cap is eight pages,
with the page count, the occurrence count and the verb that prints the rest all
beside it — a silent truncation reads as coverage.

### The store is also the corpus's proper-noun dictionary

`data/lexicon_extra.txt` used to hold the book's proper nouns — authors,
ethnicities, toponyms — so that `lexicon_miss` reported transcription candidates
rather than vocabulary. **Twenty of its lines were already an entity's canonical
or an alias**: one fact in two hand-maintained files, each able to go stale
against the other, which is the defect this project is organised against showing
up inside the apparatus that guards against it.

So the proper nouns moved. 98 whitelist lines and 9 taxonomic ones became entity
files, and `detectors.entity_forms` reads the store's canonicals and alias
forms back into the dictionary, split the way `lexicon_miss` splits them so
`Sredne-Kolymsk` contributes both halves. The trim cost nothing measurable — the
miss list is 361 tokens before and after — and it bought the thing a list of bare
words cannot have: every name now says which page first attested it, and variant
spellings that were two unrelated lines (`Krasheninnikoff`, `Krasheninnikov`) are
two aliases on one man.

**Eleven names did not move, and at the time that was the field working.** No
adjudicated page attested Almquist, Kotzebue or Sarychev, so `--since` had no
witness to name and the entry could not honestly exist. They stayed in the
whitelist under a heading that says why — and that heading is now the record of
why `since:` went: the eleven are authors of works the book cites, listed in
Authorities Quoted, and `data/authorities.json` had adjudicated every one of
them. The gate was refusing entries on the strength of a field, not of the
evidence.

Two properties keep this from being a hole in the firewall. `lexicon_miss` tests
only ASCII components of length > 3, so a Tier-1 form in an alias table is inert
there **by construction** — which is what lets an entity carry a native alias
without the alias table becoming a way to blind the one detector that could
catch an unmarked romanized form. And `harness lexicon misses` reports what the
store suppressed, under `suppressed`, so the second source is never a silent one:
detection runs against the dictionary and the whitelist alone, and each hit is
re-tested against the store.

Status is deliberately not consulted. `auto_forms` demands `ratified` because a
machine link into committed TEI is at stake; suppression writes nothing and only
removes a triage flag, so the higher bar would be that reason cargo-culted
without the stake. What makes it safe is the other half — the dictionary is
re-derived from the store on every load, so deleting an entry starts its token
missing again on the same run.

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

### Pages that will never be prose

115 pages are on `gt/zones/_exempt.lst` — a human ruled them not text pages —
and `dispatch.py` refuses them for both the ground-truth and the collation
tracks. **No amount of transcription will ever produce a `tei/` page for one**,
so leaving them to the "not collated" 404 would drop every plate, foldout and
piece of front matter out of the book silently. They are shown as what they are,
threaded into the same scan-ordered listing as the prose so prev/next crosses
them; a reader walking the book would otherwise fall off it at every plate.

**One rule decides the shape: figures if the figure store has boxes on the page,
the whole leaf if it has none.** That is the entire classification and it is
meant to be. Sorting these into plates, maps, half-titles and blanks would mean
deciding what a page *is* from evidence no store carries — on this book the
plate/text-figure split is recoverable only from prose in a `readings.md`
`@note`, and on the next book it may not be recoverable at all. Whether somebody
drew figure boxes here is a fact, and it is the only one needed.

A page with no boxes therefore shows its scan rather than nothing, which is also
the honest rendering of a blank leaf: the reader sees the leaf and can see that
it is blank. Nothing asserts that it is — 113 of the 115 exempt pages hold zero
zones, and a full-page map nobody boxed is indistinguishable from an empty sheet
at that level. The page says only what the store says, "not a text page", and
names neither plate nor blank.

**Figures run in the order the book numbers them, not down the sheet.** A
rotated plate numbers as the *turned* page reads: `1-049` runs 3, 1, 2 down the
paper and `1-227` runs 2, 4, 1, 3, and 20 of the exempt pages present their
figures in an order the book does not use. `figures.in_printed_order` sorts by
the printed number and only when every figure on the page has one — `1-215` has
a caption reading "Fig 2." without the point, which does not parse as a number,
so that page keeps its geometric order rather than having its odd one placed by
guess.

**A picture opens in the lightbox, never in the stack.** The stack is for what a
reader has to fetch and then read *beside* the text — an entity, a lexicon form,
the raster. A figure is already on the page and the only thing wanted from it is
to see it bigger.

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
(`people:chukchi` and `language:chukchi` point at the one Asher shape), so the
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

**A Tier-1 form is a link too**, into the lexicon — the next section is what it
opens. **The key is the bare form**, not `lang:form` as it was at first, and that
is what lets a *generated* page link: the generator's handle is deliberately
lang-less, because which language a form is in is the collator's judgement, so a
key holding a language linked nothing until a page had been collated. The
handle's glyphs came off adjudicated ground truth and are as settled as a
collated page's; the only thing missing is the language, which the lexicon does
not key on. So the same word opens the same card from either — which matters for
a while yet, since almost every page is a draft.

The discriminator for an unjudged span is **`@index`, not "has no language"**.
`<foreign xml:lang="de">Döring</foreign>` is a foreign span this edition does not
key, and the detector fires on a combining diaeresis exactly as on a Chukchee
form, so "link every lang-less `<foreign>`" would reach ordinary German the
moment one arrived unmarked. `lang` is emitted only where one is known: an empty
`lang=""` is a claim that an element has no language, which is a different and
wrong thing to say about a word nobody has judged yet.

Attestation is whole-element equality, not a substring search: `Qeˊñ` inside
`Qeˊñu` is the boundary the Tier-1 machinery protects everywhere else.

### Linking the handles found a disagreement about what Tier-1 is

Two arms select Tier-1 tokens out of `gt/ocr/`: `detectors.native_corpus`, which
builds every frequency table, and `context.tier1_terms`, which builds the handles
the generator wraps. They disagreed about Russian.

Pre-1918 Russian sets `й`, which is `и` + U+0306 under NFD, and U+0306 is an
inventory member — so the selection fires on `Чукотскій` exactly as on a Chukchee
form. `native_corpus` excludes it, and the argument is written out in
`detectors.cyrillic`: Russian is Tier-2, the ASCII policy does not reach it, and
no Cyrillic string is evidence about Bogoras's notation. `tier1_terms` never
applied that exclusion.

**It was invisible from both sides.** The corpus arm looked right because the
word was absent from its tables; the generator arm looked right because the word
genuinely does carry an inventory glyph. What made it visible was linking the
handles: the page offered a link into a lexicon that correctly held nothing for
it. `cyrillic` is public now and both arms call it — one rule, two callers, the
shape `entities.match` is held to for the same reason.

### A form broken across a printed line has no handle, and so no link

`1-033` sets `(Lhê-qoˊya-` at the end of one line and `yo-yêˊᵋḷhɪn).` at the
start of the next. The form is in the lexicon, citing that page, and the page
does not mark it. Both are correct and the asymmetry is deliberate.

`tier1_terms` offers a token only if it survives `join_broken_words` **as a whole
token**, and does not offer the rejoined form in its place. A handle is what `tei
expand` fills and stamps `#gt`, and `Lhê-qoˊya-yo-yêˊᵋḷhɪn` is a string no line
holds — whether that last hyphen is the word's or the compositor's is an
ambiguity the store preserved rather than decided, and a rule picking one would
write a form nobody read. The lexicon's population comes from
`native_corpus_context`, which reads the *joined* text, so the word is there with
its page.

It is "not yet", not "never": the collator gets it as a `detector_flags` row
naming the joined form and its line, reads the page, and wraps the span across
the break — `_emit` keeps printed line breaks *inside* an element for exactly
this. After collation it links like anything else.

## The lexicon, which does not wait on collation

The card behind a Tier-1 form used to say, in as many words, that there was no
lexicon store. There is one now, and the interesting thing about it is how
little it holds.

**Americanist notation is phonetic.** A form's sound follows from the notation by
rule, without anyone knowing what language it is in — which is why `ipa.impute`
takes a form and no language, and why the lexicon could be stood up on ground
truth years before collation reaches most of the book. `gt/ocr/` holds **609
adjudicated Tier-1 forms** with the pages and printed lines they occur on;
`tei/` held no collated page at all when the store was built, and holds one now.
A store keyed on anything only collation produces would have been an empty room
with a sign on it.

**So the identity is the exact surface form, NFD, and carries no language.** Two
things follow, both wanted. A form only becomes `ckt` when a collator judges it,
so an id holding a language would leave every unjudged form unaddressable. And
the book sets one word two ways — `Čeˊwɪn` on 1-042, `Čeˊwin` on 1-052, ruled a
real ambiguity in `data/marks_exempt.json` — where a headword scheme would have
to pick a side, which is exactly what that ruling says not to do. Here they are
two entries, and `see:` may point one at the other without claiming they are one
word. The inverse of `see:` is derived at render time, as `contains` is: a
hand-maintained pair of pointers is two facts that will disagree.

**An entry holds an editor's note and nothing else.** Everything else on the card
— the imputed pronunciation, the pages and printed lines from `gt/ocr/`, the
language and the printed gloss from committed TEI — is derived on every load and
never copied in. A stored copy would go stale in the direction that hides it: the
entry would still read as an entry. `## glosses` and `## attestations` are
refused at the parser so they cannot be written by accident, not merely left
unused. What is left is the one thing nothing derives — the extra-textual
clarification the book cannot make, because it was written in 1904 and the reader
is not.

**A file exists only where somebody wrote a note.** `entities/` holds a hundred
files against thousands of proper nouns; it is not a census, it is where somebody
had something to say. A form with no file is not missing from the lexicon — its
card renders in full from the derived half, and says which part of it is absent.

**The population is every attested form, not every addressable one.** That
distinction cost three forms before it was noticed. `lookup.index` buckets what
`handle_key` can spell and files the rest under `unkeyable`, which is right for
an instrument whose product *is* the key and wrong for a lexicon, whose question
is what the corpus contains — and `lookup.py`'s own docstring says why: "a caller
that reports 'not found' without saying so has converted a gap into a corpus-wide
negative." Building the index from the buckets alone did exactly that to `□ña`,
whose first character is a reader's mark for an unread glyph, and to
`Kereˊt-kun’s` / `Kereˊtkun’s`, a Tier-1 stem taking an English possessive in
U+2019. All three are real forms. `unkeyable` now carries the same record a
bucket's form does, so a caller wanting every attested form can union the two
without going back to the corpus, and the index prints `—` in the key column
rather than leaving it blank: the missing address is a limitation of the
instrument, not a gap in the row.

### The address, and why it is not the filename

The canonical URL is the **handle key**: `/lexicon/Kulu'c^i`. Measured over all
609 forms, `handle_key`'s alphabet is `)-.:=^_~'` plus ASCII alphanumerics, every
character of which is RFC 3986 path-safe except `^` — 305 keys carry one, from
`č` → `c^`. Mean URL length is **14.6 against 31.7** for the form itself, max
**42 against 85**: `Kulu%27c%5Ei` against `ckt%3AKulu%CB%8Ac%CC%8Ci`. The exact
form still resolves, because that is what `data-key` holds and what the reading
view's own links send, and so does `lang:form`, because a URL somebody wrote down
should not stop resolving.

A key naming two forms **refuses and names both**. `handle_key` is non-injective
by design — `marks.py` says the marker classes collide on purpose — and the pair
is real: `ᵋ` U+1D4B and `ᵉ` U+1D49 both key to `e^`, and both are inventory
glyphs. Resolution scans every bucket rather than going through `lookup`'s
`by_key`, which holds one bucket per key and would drop the second silently.

**The same key is unusable as a filename**, and that is not a contradiction: URLs
are case-sensitive and filesystems are not reliably. Over the 609 forms the key
yields **23 pairs differing only in case** — `Aiˊwan` and `aiˊwan` both reduce to
`ai'wan` — which a case-insensitive filesystem collapses to one file, and **34
keys containing `:`**, the portability trap `entities.py` says the
class-as-directory layout exists to avoid. Worse, the obvious check cannot see
it: "the heading's form re-keys to the filename" passes on *both* of a colliding
pair while only one file can exist. So the slug is authored, `lexicon new` prints
the reduced key as a suggestion, and `check` refuses two slugs a filesystem might
not tell apart.

### The index is the collation worklist

`/lexicon` is a tree over the seven Tier-1 codes plus an **unassigned** branch,
every code shown whether or not it holds anything — the class tree's reasoning,
that a vocabulary listing only its populated half misrepresents its own size.
Today essentially everything sits under *unassigned*, because a form's language
is a judgement made during collation and collation has not started. That is the
honest picture and it doubles as the worklist; a tree over only the assigned
forms would have shown an encouraging empty list.

A form two collated pages read as two different languages is listed under
neither, and carries a pill saying so. The corpus disagreeing with itself is a
finding, not something for the index to settle.

### The gate that sends a reader here

`tei validate` warns when a Tier-1 span is **neither glossed nor identified** —
no `<gloss target>` points at its `xml:id`, no `<name>` with a declared `@type`
covers it, no entity `@ref` stands over it. The reader has nowhere to go, which
is the same condition this store exists to answer.

It is deliberately **not** satisfied by a lexicon entry. What the gate asks is
whether *this page* says anything about the form; an entry written elsewhere is
not that, and a gate coupled to the store would go quiet exactly as the store
filled — failing in the direction nobody would notice.

Glossed is decided by `xml:id` membership and nothing else. A span with no id is
unglossed *exactly* rather than approximately, because the id scheme's own rule
is that an id exists iff something points at it — so there is no containment
fallback to write, and writing one would be the inference `ids.pair_glosses`
refuses in writing. A form the same page glosses elsewhere does not warn twice.

A warning and not an error: the book prints bare forms, and clearing the warning
by writing English the page does not say is worse than leaving it standing.

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

### Locating an entity: `tools/gazetteer.py`

`data/geo/` answers "what shape is this drawn as". It does not answer "where is
this village", and for most of the store nothing does: 73 geographical entries
carry no `geo:`, no `area:` and no `frame:`. The gazetteer cannot help — Natural
Earth's 10m layers hold eight features in this window and every one is already
claimed — so the remaining work is identification, and identification off a name
is exactly where a confident guess is cheapest to make. Natural Earth's
`King I.` is King Island, **Tasmania**.

So the pass is two steps and they are deliberately not one verb.

- **`propose` reports and writes nothing.** It searches Wikidata on the entry's
  own canonical and aliases — both scripts, because the Russian alias is very
  often the only modern identification the store holds, `Хатырка` finding what
  `Vatɪˊrkan` never will — and then tests every candidate coordinate against
  the shapes already committed.
- **`fill` derives `geo:` from an authored `link: wikidata:Q…` and from nothing
  else.** The human's act is choosing the identity; the coordinate follows from
  it mechanically, is re-derivable, and carries its provenance in the entry
  beside it. That is the same argument `#gt` and `#mz` rest on in the TEI — a
  fact re-derived from its store on every run fails rather than goes stale.

**Two mechanical disambiguators, and the second is new.** Geometry first: is the
candidate in the edition's window, is it inside the shape of the entity's
nearest `within:` ancestor that has one, and which store shapes contain it at
all. That alone reduces eleven King Islands to one. But it cannot separate
Khatyrka the village from Khatyrka the river, which are in the same place — and
that is precisely the shape this edition is full of, the Anadyr and the Gishiga
and the Kolyuchin all naming a river, a settlement and a bay at once. **The
four-class split is what settles those**: `CLASS_WORDS` scores a candidate's
description against the entity's own class, so `river:vatirkan` ranks the one
described as a river first and `place:ilpi` ranks the settlement first. A miss
ranks a candidate lower and never drops it — a description is free text written
by a stranger.

**A third check, and the only one that applies to an entity already located:**
the kilometres between the entry's own `geo:` and the candidate's. Thirty-odd
points in this store were read off Operational Navigation Charts by hand and had
never been checked against anything — the chart and Wikidata share no ancestor,
so agreement is a real corroboration. `place:anadyr` and `place:chaplino` both
come in at **0.5 km**, and `place:kolyuchin` at 0.4. Reported in kilometres and
not degrees, unlike every other distance here: those measure a point against a
polygon in the polygon's units, this measures two points, and a degree of
longitude at 65°N is 47 km against a degree of latitude's 111. It is a finding
for a `place:` only — a `land:` or `water:` point is a nominal centre, and the
Chukchi Peninsula reads 45.2 km out while saying nothing about either source.
So `fill` over a located entry is an audit rather than a no-op, and its rows are
marked `+` would write, `~` would replace, `=` compared only.

It is a `tools/` script rather than a harness verb because Wikidata is live:
the harness is offline and deterministic over what is committed, which is the
same split `build_geo.py` sits on.

**Two gazetteers, because neither has what the other has.** Wikidata is live,
rich and uneven — it knows Khatyrka is both a village and a river, and it has
never heard of Пусторецк. GeoNames is a flat file, offline, and carries the small
Siberian features the book is full of: inside this window alone **2,636 bays,
2,764 capes, 60,831 streams and 2,102 *abandoned* populated places**, against
Natural Earth's eleven features total. It also ships alternate names, so the
Russian an editor keyed off the page is a key into it.

Its feature code makes the class check **typed** rather than textual. `BAY` under
a `water:` is agreement from a controlled vocabulary the source maintains; a
Wikidata description containing the word "bay" is a grep over a sentence somebody
wrote. Same field in the report, and the row prints the code so the difference is
visible.

Two folds get the stores to meet, and both are rules rather than guesses. The
**1918 orthographic reform** (`ѣ`→`е`, terminal `ъ` dropped, `і`→`и`), because
Bogoras prints pre-reform and every gazetteer is post-reform — that is what turns
`Пусторѣцкъ` into `Пусторецк`. And **stripping the generic term**, because the
gazetteer puts it on one side of the name and the editor on the other:
`Tkachen Bay` against `Bukhta Tkachen`, `Kresta Bay` against `Zaliv Kresta`. The
stripped form is a *secondary* key with a four-character floor — `Big River`
reduces to `big` and `Red River` to `red`, and a key that matches half of Siberia
costs a human every hit it returns.

**What is deliberately not folded** is transliteration variance: `Gishiga`
against `Gizhiginskaya`, `Nishne-Kolymsk` against `Nizhnekolymsk`, `Cape
Olutorsky` against `Mys Olyutorskiy` — Bogoras's German-influenced romanization
against BGN/PCGN. It accounts for most of the 22 entries the sweep still misses,
and it is exactly where a fuzzy rule would start returning plausible wrong
matches. The cheap fix is a human adding the modern name as an alias, after
which the sweep finds it for free.

**Two Wikidata lookups, and the report says which ran.** The per-name search API does
prefix matching, which is how `Kolyuchin` reaches Kolyuchin Island — but it is a
round trip per name, and asked three hundred times it takes an immediate `429`
with no `Retry-After`, so the retry falls back to its own backoff and each entry
costs forty seconds. That is not a throttle to tune around; it is the wrong
shape of request. One SPARQL query with a `VALUES` block asks every name at
once, against labels *and* aliases in any language: **73 entries in 3.1 seconds,
42 of them with candidates.** The trade is exact matching — `Тилечики` will not
reach Тиличики where a prefix search would — so a small run does both and a
sweep does SPARQL alone, and the header states which, because an entry with no
candidates means something different under each.

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
`language:` — because an entity file carries `within: land:chukotka` two lines
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

    harness entity locate language:chukchi \
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

**There was a third check and it is gone.** A `geo:` point was measured against
its own `area:` and reported with a distance, not as a defect: a river's natural
point is its **mouth**, which sits on the very boundary the basin was delineated
from, and `river:anadyr` was 0.59° out at the estuary. That tolerance was the
width of the thing being measured rather than slack — and the whole arrangement
was an accommodation for a record saying two things about one location. A
basin plus a mouth is two *things*, and if the mouth is worth naming it is worth
an entry; `place:anadyr` is that entry. So `entity check` now refuses a record
carrying both, the check has nothing left to measure, and the section is gone
rather than left as a row that can never fire.

A shape two entities claim is legal — `people:chukchi` and
`language:chukchi` both point at the one Asher polygon, and forcing a choice
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

**It is grouped by class, because two relations were sharing one level.**
`place` and `water` nest — a tributary inside its trunk, a village inside its
basin — and that containment forest is what the atlas was built to walk. A
people or a language nests in neither: it has an extent and no parent. So once
every ethnicity carried its sprachraum, all nine peoples and all nine languages
landed flat at the top beside the one `place` root, **in pairs drawing the same
polygon** — `people:koryak` and `language:koryak` both point at
`langarea:kory1246`, which the store allows on purpose and which reads as a
duplicate when the two sit adjacent with nothing saying why. The class heading
is what says those are overlays rather than another rung of the tree.

The encyclopedia index nests too, now that `within:` is not read as the
geography's. Inside a class an entry sits under its parent — the Maritime and
Reindeer Chukchi under the Chukchi — and **only where the parent is in the same
class**. Following the field across classes would put `river:anadyr` under
`land:chukotka` and leave the *river* branch a list of orphans; such a child
stays at the top of its own class, and its card is where the cross-class chain
is legible. So the index nests within a class and the atlas nests across them,
which is the one place the two trees are allowed to differ.

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
