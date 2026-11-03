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

## `edition/` is a layer, not a rank

The store holds what is served to a reader, and that is the whole of its
membership test. It is **not** the set of files carrying `#ed`.

The two look identical until they diverge, and they diverge in one direction
only: an editor's ruling that never reaches a reader. `config/marks_exempt.json`
rules a keying ambiguity real, `config/lexicon_extra.txt` accounts for a coinage no
dictionary carries — both are a human's own act, both are `#ed`, and neither is
anything a reader is shown. They sit with the pass they rule on.

So the rank stays in `@resp`, where a rank belongs and where `validate`
re-derives it, and the folder is named for what the folder is for. Everything
under it is authored — `gt/`'s files reproduce the artifact and these do not,
which is the older `ed/` argument (`docs/apparatus.md`) and is unchanged by the
rename. What the rename fixes is a folder that answered a question about
provenance when the question a reader of the repo root actually asks is *where
does the edition live*.

The corollary is the useful one: **a file belongs here if removing it would
change what a reader sees.** An amended ToC entry does; a suppressed detector
finding does not.


**A citation in the shared store names its book.** Entities live in the workspace, so a page cited in a gloss or an alias note is `chukchi-1-044`, the text's stem and then the ref, and `entity check` refuses a bare one and a stem no text declares. The reader of that text sees `1-044`, since to them it is this book; a reader of another sees it whole. A text's own stores (`annotations/`, the apparatus) stay bare.

## Why an entity store at all

`@ref` was refused outright until this milestone — `validate` errored on
`@ref`, `@key` and `@nymRef` on any `<name>`, because there was nothing to
resolve them against and **a pointer to nothing is worse than no pointer: it
reads as resolved**. The deferral was recorded in `docs/open-questions.md` under
"Corpus-stable identity", along with the shape the answer would have to take.

So the store came first and the lifting followed. `edition/entities/` is the referent,
`validate` checks every pointer into it on every run, and the refusal survives
in narrowed form: `@key` and `@nymRef` are still errors, because identity gets
one spelling here or "is this name linked" becomes a question with three places
to look.

## An identity is `class:slug`

Always, and the class is half the name rather than a prefix on it.
`person:jochelson` is the man; `source:jochelson-yukaghir` is the book he wrote;
the same string names both, on the same page, and the book cites him by surname
alone. A scheme without the class resolves one to the other silently.

**The slug is an opaque label, never a spelling.** `being:kaleli-tairgin` drops
the `ɪ` and `ˊ` of Kalêˊlɪ-taˊɪrg̣ɪn on purpose, and nothing may read it back as
the form. Unlike a lexicon entry, whose identity *is* its form and whose URL
therefore carries that form whole, an entity has many aliases and no one
spelling to encode; the slug stays put while the canonical name in the heading
is corrected under it.

The class lives twice, deliberately. On disk it is the directory —
`edition/entities/person/jochelson.md`, because a colon in a filename is a portability
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
`wikipedia:` link whose article is titled differently, or a `geo:` member naming a
shape whose slug carries both names — `watershed:maliy-anyuy-or-dry` is
the geo store's own adjudication of the same question, made when it was built.
**Modern name first, book name second**, uniformly: seven slugs ran the other
way and were renamed, since a convention that holds four times in five is not
one, and the half a reader wants is not the half the book already gives them.
Twelve entries moved on that evidence and one, `people:inupiat`, took the title
alone because a slug cannot hold `ñ`.

Everything else stayed at first, including cases where the modern name is not in
doubt — `Gilyak`/Nivkh, `Lamut`/Even, `Kamchadal`/Itelmen, `Tungus`/Evenki. The
stated reason was that nothing in the repo attested those, so the witness would
have been a model's recall, which is the one thing this store does not accept
for an identity.

**That reason stopped being true, and it is worth being exact about when.** The
moment those peoples were filed against their `langarea:` shapes, the
repo did attest the mapping: `edition/geo/` names its own shape *Even (Lamut)*, and
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
    sky, taxon, institution, source → (none)

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

**Which class a thing earns, its alias modes and its gloss are
`.claude/skills/curate-entities/`'s** — the entry contract, loaded by whoever
writes one. One consequence of its per-class rule is recorded here because it is
the view's: an entry per class (`river:anadyr`, `place:anadyr`) is what ended the
shadowing in the reading view, where the town and the river had shared the head
token `anadyr` and only one of them could be reached.

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
outright and has no member for an institution or a work. Those are exactly
the entities an alias table finds reliably, and linking them says "this string
refers to that entity", not "the page marked a proper noun".

### A geographic rule link is a `<name>`; every other one is an `<rs>`

`entities.link_tags` is the one place the tag is chosen, because two writers emit
rule links — `generate._entity_spans` on a fresh page, `relink` on a collated one —
and a page disagreeing with the generator about its own markup is the drift `#mz`
exists to make impossible.

**The cut is what the element asserts, not confidence in the alias.** `<rs>` says
only that this string refers to that entity, which is all a rule can say about *the
Expedition* or *the Reindeer people*: those are common-noun aliases, and a `<name>`
around a common noun invents an entity the book does not have. The four
`GEO_CLASSES`' aliases are named things by construction — a settlement, a range, a
bay, a river — so the stronger claim holds for exactly them, and `validate` errors
on `#mz` at a `<name>` in any other class. A *human* may still mark a `<name>`
anywhere the page shows a proper noun; the refusal is about the rank.

**It does not make one witness of two.** The worry that stalled this — that a
generated `@type` would leave `validate`'s type-against-class check comparing the
store with itself — mistakes what the two witnesses are. That check adjudicates a
*reader's* `@type` against the store; a rule link is not a second reading but the
store's own ruling applied, re-derived on every run like every other `#mz` claim.
And the ambiguous case cannot arise: a rule links only a form one entity claims,
so nothing chooses between `river:anadyr` and `water:anadyr-bay` — the alias table
did, and `entity check`'s collision gate is what holds it to that.

**Enclosing a span the page already marked `<name>` stays an `<rs>`**, whatever the
class. Not to dodge a nesting the schema permits: the inner element is the page's
own witness that a proper noun stands here, read by a human at `#llm` or above, and
a `#mz` `<name>` around it would state that same thing a second time out of the
store, where the two could then differ. A `<foreign>` or a `<term>` asserts no such
thing, so those take the typed `<name>` like bare prose.

What it buys the reader is a toponym index that sees the links: `ids.py` filters on
`<name>`, so 1,710 geographic references that were invisible to it now are not.

### `taxon:` — no name-type, so `<rs>`

`animal:`'s name-type is `zoonym`, which `validate.py` defines as *an individual
animal's name* — the reindeer a herder calls by name, 1-101 being a whole paragraph
on the practice — so a link to it emits `<name type="zoonym">`, and `validate.py`
forbids that around a common noun: "a `<name>` around a common noun invents a whole
entity that is not there". `taxon:` has no name-type and links through `<rs>`, which
asserts only that this string refers to that entity. That is why the folk groups
(*eagle*, *seaweed*, [[taxon:pisces]], [[taxon:lichenes]]) live here and not there;
where on the tree they hang, and when a rank earns an entry at all, is the
curate-entities skill's.

### `sky:` — stars, constellations, the Milky Way

Bogoras names some fourteen, each with a Chukchee name beside the classical one,
and narrates several as persons. `being:` would be the obvious home if the class
did not then assert `mythonym` on every `<name @ref>` pointing at it — which is
wrong wherever the page means the star, and "Orion" in a sentence about when to
expect the frost is an asterism and nothing else. Only the sentence says which,
so the class says *where the thing is* and declines to say what a page meant by
it. That is what `<rs>` is for, and what the classes with no name-type have in
common.

Not a `GEO_CLASS`. A `within:` chain is about the earth and the atlas draws
nothing here.

### There is no `language:`, and retiring it is the largest single saving

There was one, with ten entries, and it earned nothing three separate ways.

**Geographically inert.** Nine of the ten held one `geo:` member and it was the
very `langarea:` polygon their `people:` counterpart already claimed — chukchi,
koryak, evenki, even, itelmen, yakut, yukaghir and yupik twice over. `geo.py`
had grown explicit handling for that co-claiming, machinery built to *tolerate*
a redundancy rather than to express anything with it. The tenth, `language:aleut`,
was a polygon's only claimant purely because no `people:aleut` had been written.

**Unread by the code that matters.** `harness/langs.py` is the language table —
it binds `xml:lang`, `entity check`'s alias-language refusal and the lexicon
index — and it names its witnesses as a `people:` entry, a `langarea:` shape or
an authority's `lang`. The class was not among them, and nothing imported it.
The lexicon is the language's encyclopedia here in the way that counts: `/lexicon`
serves every attested form and derives each one's language from committed TEI,
resolved through `langs.py`. Nine of the ten glosses were `(unwritten)`.

**And it was the single largest cost in the collation pass.** The
`people:chukchi` / `language:chukchi` split made "Chukchee" ambiguous *by
construction*, generating **423 of 1363 entity candidates — 31% of the whole
inbox**, 1.5 judgements a page, every one asking a reader to choose between two
entries that drew the identical map and one of which had nothing on its card.

The distinction was the edition's and not the book's: **every language Bogoras
names is its people's**, coextensive with the ethnicity, and an edition that
splits them invents a question the source does not pose. So the class is gone,
each `X language` alias moved onto the people it names, and `people:aleut` and
`people:russians` written — both `proposed`, because ratifying is a human act
and neither has been read against its pages. `people:aleut` carries
`langarea:aleu1260`, which would otherwise have gone unclaimed.

What genuinely goes with it: a sentence meaning the language and not the people
now links to the people. That is the cost, it is small, and the alternative was
paying 423 questions for it.

## The file

    # event:jesup-expedition — Jesup North Pacific Expedition

    - status: ratified chukchi
    - link: wikidata:Q1683389
    - geo: 66.05 -169.6
    - within: land:chukotka
    - authority: jochelson1900

    ## aliases

    | form | lang | auto | note |
    |---|---|---|---|
    | Jesup North Pacific Expedition | en | yes | the full printed title |
    | Jesup | | no | also Morris K. Jesup the man |
    | the Expedition | en | once | set on nearly every page of part 1 |

    ## gloss

    Free markdown, authored English, CC BY.

Parsed on the caption store's precedent: heading-sliced, **NFD on read**,
absence is `{}`. NFD matters more here than tidiness — an alias the store holds
precomposed silently fails to match a page that holds it decomposed, and a
silent miss is the failure class the project is organised against.

**There is no `since:`.** Both this store and the lexicon carried one — the page
whose reading prompted the entry — required on the argument that an apparatus
store which cannot be traced back to a page is unauditable. `edition/toc.json` is
still the standing case for that, and the argument was right. Its answer got
better: the card now derives *every* page the entry is attested on, from the
corpus, on every load.

**A `since:` is satisfied by typing a plausible ref; a derived attestation list
is not.** So the field was the weaker of the two witnesses, and the cost of
keeping it was real — it kept out entries the book plainly contains whose
attesting page happens to be among the 558 not yet transcribed, which is how the
sprachraum and unclaimed-watershed seeding stalled. `entity occurrences --all`
is where an unwitnessed entry shows up now, as a row reading 0 and 0, and that
row cannot be answered by writing a number in a file.

- **`status:`** is `proposed` or `ratified`, and only a human moves it.
- **`within:` is where a thing is**, and the atlas is one reader of it. It must
  resolve and the chain must be acyclic — a cycle would hang a tree walk rather
  than fail it. `entities.children` and `entities.relatives` walk it and read no
  geometry; they lived in `geo.py` while the tree was the geography's alone,
  which made a caller wanting `people:maritime-chukchi` under `people:chukchi`
  import the atlas to get it. `geo` re-exports both, since it is still the
  heaviest caller and the map's own reasoning is written there.
- **`part-of:` is what a thing belongs to**, and nothing drawing a map reads it.
  Same gates as `within:` — it must resolve, its chain must be acyclic, and
  `entity rename` re-points it — plus two of its own: an entry may not be part
  of itself, and a `part-of:` naming a `place:`/`land:`/`water:`/`river:` from a
  non-geographic class is reported, that being a `within:` typed into the wrong
  field.
- **The two were one field, and the Naukans made the conflation visible.** They
  are a Yupik people who lived in a single village, so `within: people:yupik`
  inherited the whole Central-plus-Pacific Yupik language area for one
  settlement — an extent two orders of magnitude too large, drawn with the
  confidence of a measurement — while `within: place:naukan` bought the extent
  by dropping the fact that they are Yupik at all. Neither answer was wrong
  about its own half, which is the tell that the question was two questions.
  Now the village supplies the box and `part-of:` keeps the ethnicity.

  It is the same defect as the `geo:`/`area:` rule below, inverted — and both
  are now settled the same way, by counting the questions. There, two fields
  said one thing and the second could only drift, so they became one field;
  here, one field said two things and no reader could tell which it meant, so it
  became two.

  **`entities.tree_parent` states the fallback once** — `within:` if there is
  one, else `part-of:`, and the second half scoped to `people:` — because five
  callers must agree exactly: `children`, `geo.extent_of`, `geo.unlocated`, the
  atlas tree and the encyclopedia's class listing. Every one of them read
  `rec["within"]` directly before the split and every one of them orphaned the
  four ethnic subgroups the moment the field moved. The scope is the honesty: a
  subgroup lives inside its ethnicity's area by what the word means, so the
  parent's box bounds it truthfully, whereas a `source:` that is part of a
  larger work is not *somewhere* because of it — letting that edge into the tree
  would put a bibliography on the map.
- **`geo:` is the atlas's**, below, and it is **repeatable**: the field is the
  union of its members, each of them a point, a shape in `edition/geo/`, or another
  entity whose extent this one takes. Every member must resolve, and a shape
  *kind* may never be an entity class — which is the invariant that lets one
  field hold all three. It was two fields, `geo:` for a point and `area:` for a
  shape, with a rule refusing a record that carried both; the rule was right
  about two fields and the answer was one.

  A point member's card row **opens on OpenStreetMap and on Google Maps**
  (`edition_ui.MAP_SERVICES`, addresses there and coordinates in the store, as
  `LINK_KINDS` does for `link:`). OSM leads because it is the witness these
  coordinates were derived against — the place glosses say so — and the link
  drops a marker rather than centring a view, at z10: these are vanished
  settlements fixed from a 1900s gazetteer against charts, and opening at street
  level would dress a ±1 km reading as a doorstep. The point is checkability. A
  coordinate is the most falsifiable thing in the store — it lands on the right
  headland or it does not — and until the row was clickable, checking one meant
  copying twelve digits into another tab, which is to say nobody did.
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
- **`authority:`** may cross-link `edition/authorities.json`. Resolving a `<bibl>`
  to that key is still deferred; `BIBL_IDENTITY_ATTRS` is untouched.
- **`link:`** holds an *identifier*, never a URL — `wikipedia:Chukchi_people`,
  not the address. `edition_ui.LINK_KINDS` maps the prefix to the address and to
  the site's mark, so a site that moves its paths costs one line there rather
  than an edit to every record. Repeatable.
- **`image:`** is an editor's choice of picture: `commons:<file title>` — the
  title, no `File:`, never a URL — or `none`. It overrides the picture the entry
  would otherwise take from its item's Wikidata P18, and `none` refuses one.
  Only on the classes `pictures.IMAGE_CLASSES` names; `entity check` errors
  elsewhere. "Pictures" below has the rest.
- No `canonical:` field — the heading carries it, so there is one place for it.

### An alias says what language it is a name in

The column is `lang`, from the vocabulary in `harness/langs.py`: shortest
BCP-47, so `ru` and never `rus`, `ckt` where no two-letter code exists. It is
the same string a collated page writes in `xml:lang` and the same one
`edition/authorities.json` already carries, and that is the whole reason the
spelling is not free — a fourth spelling of one code is how two stores stop
agreeing without anyone finding out.

**It was already there, in prose.** Seven entries wrote `lang:ckt` and
`lang:rus` into the *note* column: an entity's Russian and Chukchi names are
exactly what a reader of an ethnography wants, the authors knew it, and the only
place to put the fact was a free-text field nothing could read or check. Thirteen
rows moved into the column. `people:chukchi` is the one worth looking at — it
now says in a column that Чукча is Russian and oraˊwêʟ̣at is the autonym.

- **Blank means unstated**, and most of the store is blank — the book's own
  English, where saying so adds nothing. Requiring the column would have made an
  editorial pass out of a schema change. The vernacular rows a taxon pass adds
  are the one place `en` is worth stating outright, because there the column is
  what separates the book's word from the binomial beside it.
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
only argument any of them needs: `edition/entities/people/eskimo.md` was written with a
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
   construction*, whatever either file says. `people:eskimo`, `people:inupiat`
   and `people:yupik` all claim "Eskimo" and all three are right; only the
   sentence decides, and no author can see the others' claims. This is why
   the rule reads the whole store and not the entry.
2. **That claim is not `auto: no`** — the author's declaration that the form
   means this entity wherever it appears. Bare "Jesup" does not qualify even
   though one entity claims it, because the man it is named after is in the book.
3. **The entity is ratified.** A link resting on an unaudited entry would let
   the store's unread half into committed TEI.

Everything failing any of the three is still surfaced — as an `<!-- entity
candidate -->` comment in the generated page and a row in `tei context` — because
a suggestion a reader disposes of is the point. What is refused is the *silent*
link.

### The compositor's hyphen is not the word's, and the position says which

`join_broken_words` rejoins a word the printer broke and keeps the hyphen it
broke across, so `Chuk-` / `chee` arrives as `Chuk-chee` — a spelling the store
does not have. `match` still finds the entity, through a dehyphenated lookup,
and for a long time it refused to link one on the ground that **nothing can tell
that hyphen from the word's own**.

Nothing had looked at *where the hyphen was*. The compositor's is the last thing
before the measure ran out; the word's own is anywhere else in the line. The
ALTO had that all along and the generator was throwing it away — asserting an
ambiguity rather than an evidence problem, which is the failure this project
names most often and is least good at seeing in itself.

Measured over the 325 generated pages the claim was not merely weak, it was
empty: **54 candidates, and not one sat anywhere but a line end** — `Rus-sians`,
`Kam-chatka`, `Chukchee Penin-sula`, `Asiatic Es-kimo`, `Ameri-can Eskimo`.
Every one was a reader's question with a single mechanical answer, put 54 times.
Clearing it wrote 31 links by rule and left 4 candidates, which are the forms
that were ambiguous for their own reasons all along (`Rein-deer people`,
`Rus-sianized natives`) and now ask about that instead of about the hyphen.

`entities._explained_by_break` is the one definition, because **six call sites
read this field** and the rule has to hold across all of them or the placer and
the re-deriver disagree. It is deliberately caller-dependent in one direction
only: it reads the page as the generator joins a block, printed line breaks
intact, and a caller that has flattened them gets `False` — the conservative
answer, and the one every hit got before the test existed. `occurrences` was
exactly that caller, collapsing the body to a single line before matching, and
so reported as an open hyphen question the same word the generator had linked.
Two rules agreeing on a page neither could see is what the single definition is
for.

**The genuinely undecidable case never reaches it.** A word carrying its own
hyphen that also broke there — `Sredne-` / `Kolymsk` — comes back from the join
spelled exactly as the store spells it, so the exact form matches and the
dehyphenated lookup is never consulted. What stays a question is a hyphen the
store lacks sitting *mid-line*, where the measure does not account for it: either
the page really sets it, or the lines are out of reading order and the join never
saw the break, which is a defect in `gt/zones/`. The comment says both.

This is scoped to entity forms in English prose and does not reach Tier-1 (see
"A form broken across a printed line has no handle, and so no link"): there the
hyphens are the notation's own throughout, position separates nothing, and the
firewall forbids a rule to originate the reading regardless.

**The hyphen itself is now closed where the corpus can account for it**, which
narrows what this section is about rather than replacing it. `Chuk-chee` reaches
`match` spelled `Chukchee` and matches exactly, so the dehyphenated lookup and
`_explained_by_break` are consulted only for what the counts could not settle —
and for the mid-line hyphen, which was always the real question here. The rule and
its measurement are `harness/VERBS.md`'s `tei generate` and `docs/decisions.md`,
"The hyphen the corpus could account for all along"; the short of it is that the
same move works twice. Both times the record already held the witness — first the
position of the hyphen, then the spelling the book sets away from a line end — and
both times it had been written off as something nothing could tell apart.

### `auto: once`, and the third state the column needed

The column has three values, not two: `yes` links every occurrence, `no` links
none and asks on each, and **`once` links the first occurrence on a page and
leaves the rest bare and silent.**

The two-state column made the store say things its authors did not mean.
`Chukchee` is not doubtful — it means one people wherever the book sets it —
but the book sets it some five thousand times, and a link on every instance is
a page the reader cannot see the prose through. The only way to keep the text
readable was `auto: no`, which says the form *needs a reader*; the generator
believed it and asked, 423 times over the drafts, a third of the entire
collation inbox, every one of them re-putting a question nobody had. Seven
ethnonyms accounted for 730 of 1363 candidates on that footing alone.

The reader's convention answers it, and answers it *mechanically*, which is
what lets the link stay `#mz`: **first mention on the page carries it.** The
page is the unit because the page is what a reader has in front of them, and
because it is the unit `tei generate` already works in.

`auto` stays the boolean "a rule may link this at all", true for `yes` and
`once` alike, and the scope is a second key on the parsed row. Eight call sites
test `claim["auto"]` for truthiness and a tri-valued string in that key would
make `"no"` true in all eight at once, silently — which is the class of defect
this store is organised against.

**`once` contests a form exactly as `yes` does.** Two entities both claiming one
form is `entity check`'s error whichever of the two they say: `once` narrows how
many links a page gets, never which entity the form means.

**One predicate, four callers.** `tei generate` places these links, `tei
validate` re-derives the ones a page has, `relink` writes the ones an entry
ratified after collation adds, and `relink.missing` reports them. Three of the
four had no notion of position before `once`, and each computing "is this the
first occurrence" for itself would let them drift — a disagreement between the
placer and the re-deriver surfaces as a stale-stamp error on a page nobody
edited. So the rule is `entities.rule_links` and they all go through it.

**The count is over the links a page already has, not over the text a pass can
see.** This is `relink`'s trap specifically: everything else there works on
unlinked text, because linked text is by definition done, and counting a `once`
form that way finds the second occurrence with the first one hidden inside an
`<rs>`, reads it as the first, and links it — turning once per page into twice,
on exactly the pages that module exists to fix.

`tei validate` checks the *count* and not the position. That the link sits on
the page's first occurrence rather than its third is `tei diff` against a fresh
baseline, which is where a placement disagreement belongs and where a reader can
see it; what the gate catches is the failure that is otherwise silent, two `#mz`
links on one form.

### The one thing that resolves an ambiguity, because the printer wrote it down

`Wrangell` is a man and a book, and the store says so: `person:wrangell` and
`source:wrangell-1840` both claim the form, so condition 1 fails and the
generator asks. It asked 250 times over the corpus (`Nelson` was the commonest
question, before a read of all 65 hits found three lines about the man against
sixty about the book and collapsed the person into the source), and most of
those questions have the same answer — **a page locator attached to a name is
what a citation is.** `Wrangell, p. 338` is the book. `In conversation with
Wrangell` (1-036) is the man.

A `person:` entry is earned by the book narrating the man, not by citing him
(the curate-entities skill's rule), so an author the book only ever quotes has
no person entry, and the bare surname is then one entry's alone and links by
the ordinary rule.

So `harness/citations.py` resolves that case and nothing else. Two human-keyed
tables have to agree: `Authorities Quoted`'s printed sigla resolve
`(name, volume, short title)` to one work — that list *is* a resolution table —
and the `authority:` field on a `source:` entry says which work it is. Where
either lookup returns other than exactly one answer, the citation stays unlinked
and the question stands.

**It chooses among the store's claims and never adds one.** The work must
already be an entity claiming the printed form, so the alias table stays the gate
on what a string may name and the citation form only says which claimant the
sentence means. Every siglum in the store is claimed by its own `source:` entry,
so the requirement costs nothing today and keeps the licence narrow.

What separates a citation from a sentence is what may stand in the gap: citation
punctuation, a possessive (`Boas’s Central Eskimo, p. 569`), `op. cit.`, and the
volume or short title the store itself records. **Not a full stop** — that is the
whole of `Nelson. Fig. 22` — and not a lower-case word, which is what refuses
`Boas and Kroeber; for instance, compare Fig. 199`.

### The siglum is a name, so it belongs in the alias table

`Maydell 1893` is a string printed nowhere in the volume. Every footnote citing
that work sets `Maydell, I`, and the entry was titled and aliased in a currency
the book does not use — so a reader holding a footnote had nothing in the
encyclopedia to match, and the generator, matching on the bare surname alone, put
the mark on half the siglum: `<rs>Maydell</rs> I, p. 331.`

`harness entity sigla` carries `Authorities Quoted`'s `cited_as` onto the
`source:` entries, as the entry's name and as alias rows. The name is what
`[Cited, MAYDELL, I, II.]` prints — a two-volume work is one work — and the
aliases split the volumes, because a footnote cites one at a time. Each volume
yields two rows, comma and no comma: `Maydell I, p. 331.` and `Maydell, I,
pp. 627-680.` sit in the same apparatus, which is the fact `parse_citation` was
built around, so the comma carries no information and both spellings are the
store's.

**A bare surname is a form like the others, on the same condition.** Where a
`person:` claims it too — `person:maydell`, `person:wrangell` — the *alias
table* cannot decide, an alias being a context-free string match, and the row
stays `auto: no`. **That is not undecidable, and saying so would be the
overstatement this whole apparatus is against.** `Wrangell, p. 338` names the
book and nothing else, which is what `citations.py` links on. Where the book
only ever *quotes* the man there is no person entry (the rule above), the
surname is the work's alone, and `entity sigla` raises the row it already holds
to `auto: yes` — a row with a note in it is a ruling and stands. It used to
leave every bare surname alone, on the ground that a person might claim it;
once the persons who were only ever cited were dropped, that ground was gone
for most of the store. What the sigla add besides is the half the alias table
could always take: `Boas, Central Eskimo` is claimed by one entry, so it links
by the ordinary rule with no citation evidence needed, and the mark covers the
siglum whole. `auto: yes` only where nothing else in the store claims the form,
which is condition 1 applied before the row is written.

**The rename follows from what a siglum is worth as a heading, not from
ambiguity.** `Maydell, I` earns it because it says *which work*; `Steller` names
the man as readily as the book and costs the heading the year that told them
apart. `siglum_forms` already returned nothing for a bare surname, but the guard
was written on that half only, so 17 entries came out titled `Steller`, `Nelson`,
`Murdoch` before both halves were made to mean the same thing.
`source:steller-1774 — Steller 1774` stands.

Measured over the 274 generated pages: **130 `#mz` links to a `source:` entry, 66
of them the alias table's and 64 the citation rule's** — every one of the 64 a
bare surname, `Nelson` alone 26 of them. Six citations refuse, and each is a
worklist line for the *store* rather than the sentence: `Hough, Armor` four times
against the store's `Armour`, a `Boas, Indianische Sagen` in no authority entry,
and a `Bogoras, American Anthropologist` whose siglum the list does not carry.

Matching is whole-word, NFD, longest-first, **cased up the ladder**, and
**whitespace-flexible across printed line breaks**: `1-021` sets "the Jesup
North / Pacific Expedition" across two lines, and a matcher that stopped at a
line end would miss exactly the multi-word aliases reliable enough to link.

### The case ladder, applied to the store instead of to a handle

A row is reached by its own case and by every case above it and by no case
below — the rule `lookup._resolve_cased` climbs for a lexicon handle, turned
around, and sharing its definition (`lookup.case_variants`) rather than agreeing
with it by hand. `sables` reaches `Sables` at the head of a sentence and `SABLES`
in a run-in heading; `Chukchee` reaches `CHUKCHEE` and never `chukchee`, because
the corpus capitalizes a proper name for a reason.

Strict case cost **122 links across 119 pages**, every one of them a form the
store already held, and the store had begun to pay for it in vocabulary: rows
like `Brown bears` and `Black bears` beside their lower-case twins, recording
where a sentence happened to start as though it were something about the bear.
That is the compositor's line breaks entering the encyclopedia, and it does not
converge — every page a reader keys can start a sentence with any word in the
book.

Two things the ladder does not do. **It never descends**, so no lower-case page
is reached from a capitalized row: doing so would edit a ratified identity by a
keystroke nobody reviewed. And **a shape it cannot rank gets only itself** —
`Brown Bear` is neither the capitalization of `brown bear` nor its uppercase, so
`_case_rank` returns `None` and `taxon:ursus-arctos` can still say that the
`Brown Bear` at 1-184 is the river Keiˊñu-weˊem and not the animal.

**Sentence-initial is ambiguous, and the exact spelling does not resolve it.** A
`being:raven` claiming `Raven` and `taxon:corvus-corax`'s `raven` both reach the
`Raven` that opens a sentence, and the capital there is the compositor's: it
says nothing about which word was meant. Preferring the row spelled at that case
would be adjudicating at exactly the position where the evidence runs out. Both
claims ride, the hit has two claimants — this store's word for ambiguous — and it
arrives as a candidate. Mid-sentence the question never arises, because only one
of the two spellings is on the page.

`entity check`'s collision census climbs the ladder for the same reason, so a
store whose two rows meet only one rung up is not reported coherent right until
the page where it is not — and two `auto` claims meeting at a variant are the
same error they are at a form. It reports **once, at the rung where the claimants
first meet**: a variant re-spelling a collision the store already has is not a
second collision, and 34 of those would bury the few the ladder makes. Where two
rows of *one* entity meet, that is one claimant and no collision at all; the
store's own spelling is ordered first so its `auto` and `scope` are the ones that
hold.

**One matcher, three callers.** `entities.match` is what `tei generate` links
with, what `tei context` reports to the reviewer, and what `validate` re-derives
`#mz` against. Three implementations would be three witnesses that are one, and
they would drift in the direction that hides the drift. `generate.page_blocks`
exists for the same reason: the generator and the context field must join the
page's lines into blocks *identically*, or the table and the file disagree about
which questions are still open.

## `#mz`, and why it is admissible

The mechanical rank's one surface in the TEI, admitted on exactly the terms
`#gt` was and nothing
more. It says: a human wrote an alias row and ratified the entry; a rule applied
it here. No model chose it, so `#llm` is false; no human read this page, so `#ed`
is false. The responsible act happened one artifact upstream.

**It is not taken on trust, and that is its whole licence.** Every `#mz` link is
re-derived on every validation run — entry present, still ratified, alias
intact, still uncontested, element text still matching; and for a link the
citation rule made, that the page still prints a locator after the name, that
the sigla still resolve it to one work, and that the entry still says it is that
work. Weaken the entry, delete
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

### The third thing it carries: a heading

`<milestone resp="#mz">` says the book opens a ToC heading here, and it was
admitted on the same terms and against the same test. The store is
`edition/toc.json`, which is **book-internal apparatus** — the firewall exempts that
outright, because it is evidence rather than a model's reading — and the join is
the ToC's printed `page_start` against the folio the *page* prints, never the
seam ledger's predicted one. It re-derives on every run from those two printed
facts, so a milestone that ends up on a page whose `<pb n>` says otherwise fails
rather than going stale, and a human who places one the rule would not make drops
the `@resp` rather than borrowing it.

**The heading has no words in the page file, and that is deliberate.** A page file
is div-less — a chapter spans a hundred of them and a `<div>` cannot be opened on
one and closed on another — so `<milestone>` is TEI's answer here and it holds an
id. The title lives in the ToC, once, and the reading view resolves it, which is
why `stores.render`'s cache names `edition/toc.json` among its inputs alongside the
page. Where the compositor ran the head into its paragraph instead of setting it
on its own line, the words *are* on the page, the generator marks that much as
`<label>`, and the milestone renders as a bare anchor beside it. Which of the two
happened is in the markup rather than inferred from the level; the level governs
only how each sets, which is `edition.css`'s and not the page's. The four are the
book's own: a numbered centred chapter, an unnumbered centred section, and two
run-in depths in small caps and italics.

## Who writes what

| act | who | how |
|---|---|---|
| propose an entry | a collator, or the coordinator | `entity new` — always `proposed` |
| ratify one | a human | `entity ratify --commit`, or the browser |
| amend an existing entry | a human | by hand, or the browser |
| link a form by rule | `tei generate` | `resp="#mz"`, re-derived every run |
| link one by reading | a collator | `resp="#llm"` |

**A ratification names its texts.** `status: ratified chukchi` licenses the rule on that text's pages alone, because an alias says what a form means *in this book*. To any other text the entry reads as `proposed`: `entities.for_text` does that, so `auto_forms` and its callers do not change, a new text starts with no licensed links, and the generator asks a human about each form until `entity ratify` is run from that text.

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

### The mentions took the explaining off the gloss

Until the mentions block existed, a gloss was the only thing on the card that
said anything, so the glosses grew to carry the explaining — which is how an
apparatus store starts editorializing. The card now lists where the entity
occurs, with the prose either side, out of the corpus itself, and what a gloss
is for once that is true is the curate-entities skill's §3.

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
with the page count and the occurrence count beside it — a silent truncation reads
as coverage. `entity occurrences` prints the rest.

### The store is also the corpus's proper-noun dictionary

`config/lexicon_extra.txt` used to hold the book's proper nouns — authors,
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
Authorities Quoted, and `edition/authorities.json` had adjudicated every one of
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

**What that arrangement cannot find is a name English already spells.** A
dictionary accounts for `Wolf`, `Frost`, `Bering` and a man called `Ten`
regardless of what they are on the page, so the miss list — which is how this
store gets populated — is blindest to exactly the entity it exists to surface.
The blind spot is a property of asking a dictionary, not a defect to be fixed
inside one, so it is answered by asking a different question rather than by
loosening the first: `lexicon misses --common N` drops the dictionary entirely
and reports every token the corpus prints, less the corpus's own N commonest
word forms and less what this store already accounts for. It is a worklist and
not a finding — most of what comes back is ordinary English — and the flag's
mechanics are `harness/VERBS.md`'s.

Status is deliberately not consulted. `auto_forms` demands `ratified` because a
machine link into committed TEI is at stake; suppression writes nothing and only
removes a triage flag, so the higher bar would be that reason cargo-culted
without the stake. What makes it safe is the other half — the dictionary is
re-derived from the store on every load, so deleting an entry starts its token
missing again on the same run.

### A figure's parts keep their own widths

`figures.layout` gives each figure its placement against the text column, and it
used to give one width to the whole figure. That is wrong wherever the book letters
a figure *a, b, c*: the store spells it as several boxes under one caption,
`write_crops` cuts one image per box — deliberately, since "a bounding box over
boxes a human drew separately is a region no human drew" — and a renderer stacking
those images under the group's single width scales every one of them to the union.

Measured over this store: **16 multi-part groups, 32 parts, 24 of which would be
stretched**, worst `2-085`'s fig. 253 at **×3.95** — a 304 px woodcut drawn 1202 px
wide. So the sizing moved down one level and the grouping stayed where it was.
A figure carries the group's identity and **one `side`**, because it is one block in
the flow and floats as one; each part carries its own `left_frac`, `width_frac` and
`overflows`, taken from its own box. The union survives for ordering and for the
float decision, and is not a size. The crop and the space it is drawn in now come
from the same rectangle, which is the property that was missing.

## The reading view

`harness edition serve` (port 8734). Committed `tei/` only: `mz/tei/` has not had
its collation, so by default it stays out of an end-user preview.

**`--drafts` shows it anyway, and turns the same server into a workstation over
the generator's output.** The flag exists because `tei generate` is being fixed
and the fastest way to judge what it emits is to read it as a page rather than as
XML. What it does not do is blur the two: the draft is marked in the listing, on
the page itself and beside every search hit — on the page because a URL typed
straight in skips the listing that would otherwise carry the warning — and it is
read-only, since a store that can be edited here is a store that needs an
adjudication story this does not have.

**What a reader is shown says nothing about how it was made.** No path, verb, field
or rank name reaches a reader's page, on either mode; the draft and proposed marks
stay, since unfinished work must look unfinished, and say so in plain words.
**The one process word a reader sees is *uncollated*, with *collated* its opposite.**
It is the ordinary word for this stage of a scholarly edition, and the page's note
says in plain words what the stage still has to do: the text of such a page is
ground truth, so calling it unchecked would understate it. A static site (`app.state.static`) also leaves out the working furniture `edition
serve` keeps: the comment flags on a page, an alias's mode, the linked/unlinked
split on a mention, the `class:slug` and shape and authority keys, and an authority's
`note`. The ratified pill is gone from both, a settled entry being the quiet state.
**`entity check`'s `apparatus_mentions` is the store's half of this**, a worklist that
never gates, and an `**Open:` paragraph is the one place a gloss may name the tooling:
it is a question for an editor that has not been answered.

### Pages that will never be prose

115 pages carry a **leaf kind** in `gt/zones/` — a human ruled them not text
pages, and said what each one is — and `dispatch.py` refuses them for both the
ground-truth and the collation tracks. **No amount of transcription will ever
produce a `tei/` page for one**, so leaving them to the "not collated" 404 would
drop every plate, foldout and piece of front matter out of the book silently.
They are shown as what they are, threaded into the same scan-ordered listing as
the prose so prev/next crosses them; a reader walking the book would otherwise
fall off it at every plate.

**The kind decides the shape**, and the vocabulary is `zones.LEAF_KINDS`:

| kind | leaves | what the reader gets |
|---|---|---|
| `plate` | 44 | its figures, in the order the book numbers them |
| `blank` | 42 | the leaf at thumbnail size, labelled blank |
| `cover` | 7 | the whole leaf — a title or wrapper page |
| `map` | 1 | the whole leaf, through the Mixed Raster pair |
| `apparatus` | 21 | nothing: the leaf redirects into its run |

**One rule used to decide it — figures if the figure store had boxes, the whole
leaf if not — and that rule read a different store to answer this question.**
Whether somebody drew figure boxes is a fact, but it is a fact about `gt/fig/`,
and under it a blank verso and the volume's folding tribal-distribution map were
the same page: 113 of the 115 hold zero zones, so a full-page map nobody boxed
was indistinguishable from an empty sheet. `1-361` reached the reader as a bare
raster captioned "a human ruled scan 1-361 out of the transcription tracks", and
the index listed it as `1-361` with no tag.

The objection that rule answered was to *inference* — deciding what a page is
from evidence no store carries, which on this book would mean reading the
plate/text-figure split out of prose in a caption's adjudication note. That objection
stands and the kinds do not violate it. A kind is **declared**, not derived: it
is written by a human in `zones edit` at the moment they are looking at the
raster, which is the only authority entitled to make the call. Nothing proposes
one, nothing infers one from figure boxes or from a neighbouring leaf, and a page
in no kind list is not a leaf at all — it renders as it always did.

What the page says is exactly what the store holds and no more. A `blank` is
still *served* — the ruling is a claim, and a reader who wants to check it
against the paper can — but at thumbnail size, because a blank verso at plate
size is a screenful of empty paper between two pictures somebody was paging
through. `plate` covers the 35 numbered Plates I–XXXV and 9 full-page text-figure
sheets together; that finer split is recoverable from the List of Illustrations
if it is ever wanted, and is not asserted here.

**Figures run in the order the book numbers them, not down the sheet.** A
rotated plate numbers as the *turned* page reads: `1-049` runs 3, 1, 2 down the
paper and `1-227` runs 2, 4, 1, 3, and 20 of the ruled leaves present their
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

### The index is the Contents, with the rest of the binding between

The listing at `/edition/` was scan numbers with a word beside each — `1-031
I. Names and Habitat`, `1-361 map` — and the book's own shape was invisible in
it. It is now the printed Contents in the binding's order, under a heading per
part: a chapter's row links to its run and carries its sections nested as the
Contents nests them, and every leaf outside a chapter stands between the chapters:
the front matter as rows, the covers as a wrapping row of small pictures, the map
as a larger one. `edition._outline` builds it. Scan numbers float right, as folios
do, with a row's tags before them.

**A blank has no row, and nothing else changes for it.** It stays in the listing,
so prev/next walk it and the build reaches it. A blank with a division placed on it
keeps its row, so no Contents entry is lost.

**A page with no division of its own joins the division before it**, which is how
`1-022` sits under *Introductory*. It is `chapters.py`'s arithmetic and carries its
limit: the leaf must follow directly, and the next Contents entry must be placed or
absent, since an unplaced one might open on that leaf. This groups the row and does
not make a run: each page is still its own document.

**A thumbnail is made on request, at `/thumb/{ref}.jpg`**, because the leaves
themselves would put about 7 MB on the index. `edition_ui.THUMBS` says which kinds
have one and how wide. It is downscaled and nothing else, from the editor's leaf
where there is one, and it is never read as evidence.

**Two overlays, each declared on an ordinary link whose `href` still works with no
script.** `data-lightbox` names a picture (with `data-lightbox-under`, `data-full`
and `data-caption`) and `data-modal` a fragment to show in a `<dialog>`. The bar's
*Map* and the map's thumbnail open the leaf a human ruled `map`, which is the book's
own map and not the footer's *atlas*. The bar's *Key* opens `/partial/alphabet`, on
every page but the Key's own. `build._derived` restates both attributes.

**One script, for every page of every edition.** `base.html` loads `edition.js` and
a page adds nothing of the reader's own: the head of that file lists the attributes
it acts on, which is the contract a later edition follows. A page with no stack
leaves the links that would open a card to their hrefs. The map is the one thing kept
out, since it is about as large again and most pages have none: `data-atlas` on the
pane is what imports `map.js`. `ratify.js` is the editor's and stays its own file.

**Two orders, and a division sits in both only where something places it.** The
scan order is the binding's; the Contents' order is the book's. A division is
placed by a run that declares it — a chapter run's `toc_id` is its milestone; a
declared run's is the editor's own word in `edition/runs.json`, which is how
*Authorities Quoted* and *Alphabet* merge with the stores that render them, and
`edition runs` fails on a `toc_id` that names no entry or that two runs claim —
or, where no run does, by the one leaf a milestone opens it on, or else by the
folio index: the served leaf that prints its `page_start`, which is what puts
*Introductory* on `1-021`. Nothing is matched
by title. A division nothing places is listed where the Contents puts it, just
before the next placed one, marked *not located* and linking nowhere: the nearest
chapter would be a guess indistinguishable from knowledge.

**A chapter the listing dropped is still in the outline.** Without `--drafts` a
chapter with no collated page has no leaf for prev/next to stand it on and
`in_reading_order` leaves it out; the Contents still has it, so its row stays,
saying *0 of 22 collated* and sending a reader to the run, where every leaf is a
gap that says why. The count is what replaced the draft tag on these rows:
`draft` over twenty-four leaves of which twenty are signed is the wrong word,
and the flat list had put it on covers and on the Contents itself, neither of
which can be collated at all. The tag now belongs to a text page alone.

### Runs: a span of leaves served as one document

Twenty-one of those leaves are ruled **`apparatus`**, and that kind is the one
that names a second store. They are the book's own lists — the printed Contents,
the List of Illustrations, Authorities Quoted and the Alphabet key — and the
repository already holds every one of them parsed, with the folio each entry
names and the scan it was printed on. A reader who opened `1-014` got a
photograph of a list this project could have rendered.

**So the two declarations check each other, in both directions.** A run's leaves
must be ruled `apparatus` and not merely be out of the tracks (`not-apparatus`):
a plate in a run would render as a list of entries it does not have, and the
looser test could not say so, a plate being out of the tracks exactly as the
Contents is. And a leaf ruled `apparatus` that no run names is an error too
(`apparatus-not-in-run`) — the kind promises the content is held parsed
somewhere, the run is what says which store, and without one the promise has no
reading behind it and the page falls back to a bare scan.

Six scans of List of Illustrations are **one printed list**, so the unit the view
serves is the **run**: an ordered contiguous span of scans presented as one
document. `edition/runs.json` declares them — `{id, kind, title, refs, source}` —
`harness/apparatus.py` reads them, and `edition runs` is the gate.

**Every leaf of a run redirects into it**, the first included, so a run has one
canonical URL rather than a head that renders and interior leaves that bounce.
`in_reading_order` drops the non-head refs, keeping its `list[str]` shape and the
`refs.index(ref)` arithmetic every caller does on it; prev/next then crosses the
list in one step instead of six. The leaves are not lost in the process: each
keeps its anchor, its folio where one is known, and a link to its own raster.

**A run is one list, and the leaf breaks sit in its margin.** Rendering a `<ul>`
per scan would close and reopen the list at seven places that are facts about the
binding rather than about the list, breaking the indentation and the reader's eye
at each. So `_run_items` flattens the leaves into one stream and marks where each
opens: a small grey **printed folio** in the left margin, linking to *itself* —
a permalink to that point in the run, which is what a reader wants from a page
break. A leaf the store records nothing on still gets a row, because the anchor
has to exist for the redirect to land on.

The folio shown there is the **printed** one, out of `source.printed_folios`,
which is a different field from the one the folio index keys on: the front matter
is numbered in roman (Contents v–xi, List of Illustrations xii–xvii) and that is
what the leaf carries and what a reader recognises, while the index and every
`page_start` in the ToC are arabic. `printed_folios` is positional against
`source.refs` and is read only where the two agree in length — pairing them off
anyway when they disagree would attach a folio to the wrong leaf.

**Each leaf mark carries its own scan.** A run is one document whose scans are
several, and a reader consulting one is at one leaf of it, so the 🗗 beside each
mark opens that leaf's scan in a card, and the bar has no button for the span. Page numbers are set hard right, as the book sets them, and
**without dot leaders**: those are typesetting rather than text — the printer
carrying the eye across a gap this layout does not have — and reproducing them
would put marks on the page that are in no store.

**`kind` is a closed vocabulary** and an unknown one is a gate failure, not a
silent fall back to the bare leaf — `figures`' `unknown-exemption` rule, for the
same reason. Adding a kind costs a template and an entry in `apparatus.KINDS`;
the next book declares the runs it has and no others.

**A leaf shows the entries the store records as printed on it, and there is no
fallback.** A store that cannot say which leaf an entry belongs to is reported
unrenderable rather than having its whole list attributed to one leaf. That is
why `edition/toc.json` had to gain provenance before the Contents could be served —
it was the one apparatus store not auditable back to a page, and
`tools/toc_provenance.py` records the reading that closed it.

**The span is stated three times and the three are checked against each other**:
`runs.json`'s `refs`, the store's own `source.refs`, and the set of per-entry
`ref` fields inside it. All three were already in the tree, so this costs a
comparison rather than a second pass, and a disagreement is a finding rather than
something to merge.

### The alphabet run: what replaced 1-030

Scan 1-030 is the p. 10 key, and it is the page a reader turns to on meeting
`taˊn˙ñɪtan`. It answers badly — fifty lines of "as in English", in no order,
with the structure of the system nowhere on it. Everything needed to answer well
was already in the repository, in four places that had never been in one room, so
the run's page is a **join** and `harness/alphabet.py` is the joiner:

| | |
|---|---|
| `edition/alphabet.json` | both printed accounts transcribed, and Mythology's arrangement of the sorts into grids |
| `ipa.RULES` | what each sort is worth on Bogoras's own account, with its grade and its hedge |
| `ipa.MODERN` | what a current description calls the same sound |
| `lookup.index` | how many keyed forms actually carry the sort |

**The grids are reproduced because the arrangement is the analysis.** Mythology
sets the vowels in three rows and five columns, and that shows at a glance what
p. 10's flat list hides completely: ä, ê and ɵ sit *over* a, e and o as their
long counterparts, and ŭ sits *under* u with the obscure short series rather than
beside it. **Its columns are unlabelled in the print and stay unlabelled here** —
naming them stop/affricate/fricative/nasal would put an analysis on the page that
Bogoras did not write.

**His place names are one step back from modern usage, and saying so is the most
useful thing on the page.** `k` and `ñ` are on his Palatal row while `q`, `g̣` and
`h` are on his Velar row, so his "velar" is what a modern description calls
uvular and his "palatal" what it calls velar. Reading that row label as a place
claim is exactly what made an audit of `ipa.py` argue `g̣` was uvular, which the
modern inventory does not support.

**Three things are shown rather than smoothed.** The four sorts with a gloss and
no IPA value (ë, ḷ, ṛ, š) keep their rows and say why — an omission would read as
the key not having them. The hedges are marked. And every gloss carries the key
it came from, because the two accounts are not one notation.

**The store and `keying_spec.md` state every codepoint twice**, and `edition
runs` compares them rather than merging. The spec owns the inventory (CLAUDE.md's
precedence table) and a chart needs machine-readable data; neither is derived
from the other, so the comparison is the only thing keeping them honest — 18
sorts cross-checked, the same idiom as a run's three statements of one span.
`alphabet.spec_codepoints` parses §2.2 and §2.3 **by column header and scoped to
those sections**, because §3's table has the identical shape and the opposite
meaning: a forbidden lookalike beside the codepoint that should have been keyed
instead.

Declaring the run also closed a hole. Folio 10 was the single gap between the
Authorities run's folio 9 and the body's folio 11, so `/edition/toc/front.alphabet`
refused; every sort is printed on that leaf and carries its folio, so the store
is now the witness and the ToC's own link resolves.

**The printed key is still the record.** It is binding apparatus — the firewall
names it — so the leaf is one click away on 🗗, exactly as for the other runs.

### The anchors, and the chapter pages they are for

A chapter page is a run too, with its span derived rather than declared (the next
section). **Nothing downstream may care which kind it
got**, which is why the addressing was settled before the three renderers were
written. `apparatus.anchor(kind, key)` mints all of it, one function because the
template that emits an id and the locator that builds a URL at it live in
different modules and only this stops them drifting:

    leaf-PP-NNN   one per ref in a run, emitted whether or not the store holds an
                  entry printed on that leaf — a redirect must always land
    folio-N       where that leaf's folio is known
    toc-ID        on every heading carrying a `toc.json` id, which is what makes
                  a chapter link resolve before chapters have pages

`apparatus.locate(ref=| folio=| toc_id=)` is the single resolver, and every
redirect route goes through it: `/edition/page/{ref}`, `/edition/folio/{n}`,
`/edition/toc/{id}`. A heading link now resolves through the milestone first —
the anchor is the heading's own fragment (below), inside whichever run holds it —
and through its folio only where no page has opened it yet.

### A chapter's address is its name

A chapter is served at `/chapter/xii/religious-ideas`: `chapters.slug`, the roman
and then the title as two segments, so `/chapter/xii` is the chapter by number.
`apparatus.run_url` is the one place a run's URL is built. A heading carries a
fragment by the same rule, `#animals-as-men` (`chapters.fragments`), and a
chapter's heading fragment is the two segments hyphenated, `#xii-religious-ideas`
(`chapters.heading`). **One rule
for both**, `chapters.slugify`: NFD, lowercase, combining marks, spacing modifiers
and apostrophes deleted, every other run of non-letters one `-`, and a base letter
outside ASCII kept — `Taˊn˙ñɪn Wars` is `tannɪn-wars`. **An address, not a
reading:** a Tier-1 form stripped of its marks is not a form, so a slug is never
displayed.

**The roman is the segment that does not move.** `toc.json` is amended, so a title
can change under a link. `/chapter/{roman}/{title}` matches the roman
case-insensitively and renders only the derived chapter's own slug; every other
spelling — the number alone, `XII` as the prose prints it, a title from before an
amendment — goes through `locate`, which answers with the slug, or the head's leaf
for a chapter whose span is underived. It cannot loop: `locate` names a slug only
for a chapter that renders at it. `/run/{id}`, a chapter's address before it had a
name, redirects with no fragment of its own, so the reader's survives.
`edition build` writes `/run/{id}`, `/chapter/XII` and `/chapter/xii` as stubs
(`build._retired`), since nothing links to them and the crawl alone would never
reach them. A disk that folds case cannot hold both romans and refuses the second;
the hosts are case-sensitive.

**A section title twice in the Contents is told apart by what holds it, never by
order.** Uniqueness is over the whole ToC, because a chapter page renders its
neighbour's tail and `/page/` renders whatever heads a leaf holds. A colliding
group climbs one ancestor together, prefixing its title slug — `reindeer-races`
and `maritime-races` — and a chapter's slug carries its roman, so twins in two
chapters always part: `iii-trade-anui-fair` and `trade-anui-fair`, whose parents
are both titled *Trade*. What no ancestor parts keeps its toc id and is an
`edition runs` error, `fragment-collision`. The real ToC has none.

**An old fragment still lands.** A fragment never reaches the server, so no
redirect can carry it; instead each heading is preceded by an empty
`<span class="milestone legacy" id="chXII.3">`. The chapter split and the contents
tracker in `edition.js` still find a heading by that toc id. Amending a section
title moves its fragment, and old links still land, on the toc id.

### Chapter runs: the span is the milestones'

`harness/chapters.py` derives one run per chapter, and **the witness is the
milestone, not the folio index**. The milestone is already re-derived on every
`tei generate` from the ToC's `page_start` and the folio the page prints, and it
answers for all 23 chapters where the folio index answers for about a third of the
book. A span is then arithmetic over scan indices: from the leaf a chapter's
milestone stands on to the leaf before the next one's, so a plate or blank between
them is in the chapter because the binding put it there. The last chapter of a part
ends at the part's last text leaf, and no chapter crosses a part.

**Read from the page the edition would render, whatever a sitting shows** — the
signed page, else the draft. Where a chapter is, is a fact about the text; whether
a reader may see a leaf of it is the view's question, and the view answers it
leaf by leaf: a leaf it cannot show is a **gap**, said in place with its scan
linked, never closed over and never a reason to refuse the chapter.

**Nothing is derived past a hole.** An opener missing or found twice leaves that
chapter underived and the one before it too, since its end is the missing start;
`edition runs` reports both, and their leaves stay served one at a time. A span
that guessed its end would put one chapter's text under another's title.

**A leaf with text above the head belongs to both chapters.** Each shows it whole,
the other chapter's part greyed under a link to it, and the leaf redirects into the
chapter it opens, which is the one the listing stands it for — redirecting into the
earlier one sent *next* straight back. Bogoras never does this: every chapter opens
a fresh leaf, so here the case is held by tests alone.

**A paragraph the leaf break cut is one paragraph again.** Whether a leaf continues
the paragraph before it is what that leaf already says — `tei_html.page_opens`, off
`@part` where the seam is written, else the collator's `opens:`, else the keyed zone
label — and that is the whole test. Whatever stood between the halves, a figure, a
flag or a plate on a leaf of its own, moves to the top of the joined paragraph:
`tei generate`'s rule for a figure the prose runs past, one level up. A gap leaf
never joins, since nothing says what its text did. **A word the page turn cut is
decided by the line-end rule**, `resolve_break_hyphens`, unchanged: offered to the
corpus closed and as it stands, the spelling ground truth sets mid-line elsewhere
wins, both-or-neither keeps the hyphen, and a form bearing the notation is refused
outright. The word is then set whole and the page mark goes after it. A half
inside an element (an entity link) is left as it was, since closing it would move
text across an element boundary. **The page number is set where
the leaf turns, inside the sentence if that is where it turned, and drawn in the
right margin** — Project Gutenberg's convention — which is why the chapter body is
assembled in `edition._chapter_body` rather than looped in the template.

**Notices, footnotes and supplements are pooled per chapter**: notices once at the
head, footnotes then supplements at the foot. A section's notice attaches to every
leaf in the section and pools to one. **Footnotes are grouped by leaf and keep their
printed numbers** under the page they were printed on. The marker in the text is the
printed superscript, adjudicated inventory, and the book numbers from 1 on every
page, so a running number would either rewrite the glyph or have the text say ¹
where the list says 14. The leaf's ref is folded into each note's ids, which is
what keeps two note 1s apart in one document.

### The folio index, and its three witnesses

A scan index is not a folio and neither is derivable from the other, so a folio is
known only where a page said what page it is. Three witnesses say so, ranked, and
the index is re-derived on every call and never persisted — which is what makes
the two lower ranks admissible at all: they assert nothing on their own authority
and fail rather than go stale.

| rank | witness | what it is | today |
|---|---|---|---|
| 1 | `tei` | the committed `<pb n>` | a human collated the page |
| 2 | `apparatus` | a store's own `ref`/`folio` pair | 7 leaves, from `authorities.json` |
| 3 | `running-title` | `context._running_title` over `gt/ocr/` | 273 pages |

**Rank resolves; it does not silence.** The redirect follows the strongest
witness; two refs claiming one folio *at the same rank* is a refusal showing both,
not a tie to break; a weaker witness contradicting a stronger one is reported by
`edition runs` rather than dropped, since that is usually a misread running title
and is worth seeing. Measured over this corpus: **280 of 732 folios witnessed, 0
disagreements, 0 same-rank collisions**, built in 0.32 s.

**Which witness a store supplies had to be declared and could not be guessed, and
this is the correction worth keeping.** All three apparatus stores carry a `folio`
beside a `ref`, and in only one do the two describe the same leaf. An
`authorities.json` entry says "this entry was printed on `1-023`, which is folio
3" — the entry *is* the thing on that page. An `loi.json` entry says "this figure
appears on folio 17" while its `ref` is the List-of-Illustrations leaf the caption
was *read from*: the folio is about the subject, the ref about the description,
and they are pages apart. Counted as a witness it placed `1-014` at folio 17 at a
rank above the running titles that had it right, and every folio in the book
resolved to the List of Illustrations. `KINDS[…]["folio_of_leaf"]` is that
distinction and a test holds it.

**280 of 732 means the refusal is the ordinary answer**, so `/edition/folio/{n}`
renders a page naming the nearest recorded folios either side and reads as an
answer rather than an error. Nothing interpolates: a redirect is a resolution, and
a guessed one would be indistinguishable from a witnessed one at the URL.

### What a run links, and what it declines to link

Every link on a run page is a store already in the tree answering a question the
printed list poses, and each is **omitted rather than guessed** where it cannot.

- The ToC's `page_start` and the LoI's folio go through the folio index. 121 of
  the Contents' 316 entries link today; the rest print plain.
- **A plate's number is not its folio**, and the printed list says so: it heads
  that column *"Opp. page"*. A plate is an inserted leaf carrying no folio of
  its own, so the number is the page it faces, and the page prints `opp. 29`
  rather than a bare number in the same column a figure's own folio sits in.
  This was rendered as a folio at first, which sent a reader clicking Plate I's
  "29" to the page the plate faces as though the plate were on it.
- **A plate links through its caption**, since it has no number to resolve on:
  `figures.by_plate` matches the list's abbreviated segments against the keyed
  under-figure captions and names the leaf. All 35 resolve, and a test pins
  that. **Every segment must be found and exactly one leaf must qualify** — an
  earlier matcher took the best-scoring page and bound `1-227` and `1-231` to
  each other's plates on a shared word, and a picture under the wrong plate is
  worse than a plate with no picture. The comparison folds combining marks,
  because the list sets `Nuˊnligren` where the caption has `Nuˊnlig̣ren`; the
  fold lives inside one comparison and reaches no store. What it then links is
  **every picture zone on the leaf, not every figure**: two of the photographs
  under one caption are one folded figure keyed on the topmost box, so linking
  by figure showed the upper picture of Plate V and dropped the lower.
- An LoI figure number goes through `figures.by_number`, a corpus-wide fold of
  `figure_boxes`. **One link per printed number, not per entry** — two entries
  name several figures at once ("Figs. 214, 215, 216") and each numeral is a
  different picture. **The plate leaves come out of the pool first**, as
  `figrefs.resolve` takes them out for a reference in prose: the book restarts
  figure numbering on every plate, so 31 pictures print `Fig. 1`, and none of
  them is in the series this list enumerates. Leaving them in made 1–4 collide
  with a series they are not in, and the list's first four entries were dead
  links for it. A number resolving to more than one zone still prints plain,
  since choosing among a collision's candidates would invent the answer the
  collision is reporting. **All 302 resolve** — three of them through
  `edition/figure_numbers.json`, the hand-keyed patch table `docs/apparatus.md`
  describes, because the leaves that defeat the derivation are the printer's
  oddities and not rules waiting to be widened. This is emphatically **not** the LoI reconciliation
  `docs/open-questions.md` defers — it links, and it gates nothing.
- An authority's siglum goes to `edition/entities/source/…` through the entity record's
  own `authority` field, never a match on the printed name: 52 sigla over 34
  names would make that a guess. All 74 resolve.

**Printed is the record**, `find authority`'s own rule: the Authorities run shows
the block the store copied off the page, and the parsed fields ride beneath it
rather than replacing it.

**A transcluded store is still a store, so the no-invisible-fields rule reaches
it.** A `source:` card printed two fields of its bibliography record — the key
and the title — and the casualty that mattered was `cited_as`, the field that
says how the *book* names the work and so the only one a reader holding a
footnote can match against; it appeared nowhere in the encyclopedia at all. The
whole record is on the card now, `printed` blocks first and the parsed fields
beneath, `AUTHORITY_FIELDS` and `AUTHORITY_SOURCED` naming which is which and
`test_edition.py` holding both against the live bibliography. Four fields are not
plain strings and none of them is flattened: `doi` and `url` are `{url,
provenance}` and **render with their rank**, since a scan a model found must not
look like one somebody opened; `author_printed` and `year_printed` qualify the
field above them, so an author the list carried down from the entry above says
so, and Lütke's printed `1834, 1835, 1836` is shown beside the `1834` the store
sorts on.

### An editor's own leaf

`edition/page-img/chukchi-PP-NNN.{svg,png,jpg}`, resolved by
`edition_ui.leaf_source` — `edition/fig-img/`'s doctrine (`docs/apparatus.md`) one
level up, for a whole leaf rather than a crop, with the rank travelling with the
answer as `crop_source` and `page_source` both do. **Vector before raster**,
because `1-361`, part 1's foldout map, is the leaf this exists for and may become
one; a resolver that assumed a raster would need rewriting the day it did.

Two boundaries, and both are the point. It is **reading view only**:
`zones.scan_for` is what the segmenters, the ink checks and `fig crops` resolve
through, and it never consults this, because a sharpened or upscaled leaf is
manufactured evidence and must not reach anything that measures ink. And it is
**ruled-leaf only** — a file for a page the pipeline still owns is ignored and
reported, rather than being honoured quietly the day somebody adds a branch. Any
kind qualifies, not `map` alone: what licenses a hand-worked leaf is that the
page left the transcription tracks, not which sort of leaf it turned out to be,
and narrowing it to today's single user would refuse a touched-up plate for no
reason the doctrine gives.
`/edition/page/{ref}.png` keeps serving the real scan; the made artefact has its
own route and the page says which it is showing.

The store is **gitignored for now**, with the reason in `.gitignore`: the artefact
for `1-361` is undecided, a vectorization is being attempted, and committing a
22 MB raster about to be superseded would put the wrong thing in git permanently.
Drop a file in and the route serves it. Tracking is a separate act, and when it is
taken this ignore comes out — a vouched-for artefact a clone does not get is not
vouched for.

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
`<title>` unescaped. What is marked safe is a renderer's output that escapes its
own inputs — `tei_html`'s page HTML and the gloss markup `edition_ui.gloss_html`
builds among them.

**The stores are read through a cache keyed on their contents**
(`harness/web/cache.py`). Every request re-walked and re-parsed the whole
encyclopedia — `entity_index` did it twice, once for `load` and once for
`check` — and `search` re-rendered every collated page per query. Contents and
not mtime, because these stores are edited underneath the running server and a
timestamp key is not fine-grained enough to notice; the measurements are in that
module.

**Two columns, and the second one has two tabs.** The text, and beside it a
sidebar holding **entities** — the map pane over the card stack described below —
and **contents**, the printed table of contents as a locator. One partial,
`harness/web/templates/edition/_sidebar.html`, because four views carry that
column and an idle rule that has to agree with the stylesheet's is not a thing to
write four times.

### The contents tab answers *where am I*

The printed Contents was a full-page run and nothing else, reached by a link that
opened another tab. So a reader who wanted to know which chapter they were in left
the book to find out, and came back to a page that had never said. The tab puts
the same store in the column — **the whole outline, all five levels and all 316
rows, served collapsed** as the tree its levels describe.

Collapsed, because 316 rows in a 20rem column is a thing you have to read rather
than a thing that tells you where you are. Whole, because a locator has to show
what is *around* you: a panel holding only the divisions it could place would
answer a different question on every page, and depth is what the sidebar's rows
have instead of `.run .toc`'s four hand-set gutters — the markup nests, so one
indent compounds.

**The division you are in is unrolled whole**, not merely opened along the path
down to the row that matched. A chapter opened to that one row shows you the row
you already had and hides its neighbours, which is the opposite of a locator; so
every `<details>` inside it opens, siblings included, and the divisions around it
stay shut. It applies where the page has a position and not to an entity's
mentions: those are spread over twenty chapters, and unrolling all of them would
serve the outline open.

**What is marked, and by which witness.** `state.toc_containing` folds
`edition/toc.json` over its own ordering: the list is ordered, `page_start` is
monotonic across all 316 entries, so the divisions containing a folio are the
open chain of the entries that start at or before it, an entry at level L closing
everything at L and deeper. Level 0 is folded as level 1 — front matter emits no
milestone and so is absent from `MILESTONE_UNITS`, but it is a top-level division
all the same, and left at its own depth the Alphabet would stay open under every
chapter after it.

**A folio can be in two places at once, and both are marked.** The chain is where
the page *is*; the entries whose `page_start` is this folio are the heads the page
actually *prints*, and a page can print several — 1-249 sets both "Animal Food"
and "Methods of Cooking". A chain holds one entry per level by construction, so on
its own it named the second of them and said nothing about the first, which is a
locator telling a reader they are in one section of two.

This is **a different answer from `entry_state`'s `believed_open`**, and the two
must not be run together. That one folds committed `<milestone>`s out of the TEI
and says what the corpus witnesses; this one reads the book's own table of
contents and says what the printed list implies. It is admissible here for the
firewall's own reason — book-internal apparatus is evidence and it binds — and it
is a navigation aid: it asserts nothing about any page and nothing writes it to a
store.

**An unwitnessed folio marks nothing, and says so.** 452 of the book's 732 folios
have no witness, so the panel refuses more often than it answers, and an unmarked
panel is indistinguishable on screen from one that could not place the page —
which is why the refusal is a sentence and not a silence. Nothing interpolates a
nearest chapter.

**On an entity's page the same panel says where the entry is talked about**, by
division and with a count, which is what forty page refs sorted by scan number
could not say. The fold is over the *untruncated* mention list: `_mentions` keeps
eight rows for the card, and a chapter is not reached by an entity's first eight
pages — a chapter left unmarked for that reason would read exactly like a chapter
the entity is absent from. `stores.folio_by_ref` inverts the folio index once for
it, since `apparatus.folio_of` is a scan of the whole index per ref; `_by_folio`
tallies a ref list onto folios, and a ref the index cannot place drops out, which
is the rule the marks follow everywhere else.

**And it holds only those rows** (`edition._sparse`): each one with a count, and
what holds it, in the printed order with its folio. The question here is not "where
am I", and a passing name's panel was twenty-five chapter titles around the one that
held it. A row gone now reads as "not in this chapter", so what could not be placed
is counted under the tree: *2 mentions of 380 not placed in the printed Contents*.
An entry with no placed mention keeps the whole outline, since there is nothing to
thin. A form's card does the same in pages.

**A form's card is marked the same way, by attestation**, and it needs no further
warrant than the entity's: the lexicon's identity *is* the form, so no alias table
stands between the word and the pages. There is nothing to be wrong about, and the
number moves only when a page it was read off is corrected.

**Out of `gt/ocr/`, and `tei/` only in addition** — this card does not wait on
collation and neither may its marks. Sourced from `attestations` alone, which
sweeps committed TEI, every card in the lexicon carried "nothing places this form"
because 0 pages are collated: the *store's* state reported as the Contents'
failure, which is the one thing a locator must not do. The keyed corpus is the
witness that exists — 1562 forms, each carrying the refs a human keyed it on — and
the two are unioned rather than chosen between, because a collated page `gt/ocr/`
has not reached is a page the form is on all the same. `keˊlet` lands in nine
chapters, 24 of its 73 pages in *Religious Ideas* and 21 in *Shamanism*.

**Pages, not occurrences.** Both stores record which leaves carry a form and
neither records how often on one, so a folio contributes 1 and a division's number
is the count of attested pages under it. `count` in the keyed store is per corpus,
which is not a fact about any division.

**The refusal is about placement, so it fires only where there was something to
place.** A form no store attests has not failed to be placed in the printed
Contents — it is not in the book, which the card's own rows say. Same guard on the
entity card, and `_mentions`' own reasoning for it: a bare zero cannot be told from
"never mentioned". The sentence itself is the caller's (`absent`), because a leaf
has a position, an entry has mentions and a form has attestations, and one sentence
covering all three would name none of them.

**The tab is per sitting**, in `sessionStorage`, on the rule the map selection
already follows: a Contents you opened to find your place is not a setting you
chose. It is read in the head script before the stylesheet, because the contents
tab holds the column open against the idle rule and reading it later would
collapse the column and then shove the text sideways on every page load. The
header's **ToC** link opens it and keeps its href, so the printed Contents is
still what a click reaches with no JS.

**The column still collapses when it is idle** — no cards, the pane shut, and the
contents tab not asked for. A tab bar is furniture, and furniture is not a reason
to hold a column open across a book nobody has clicked anything in. The atlas
keeps its own column and gets no tab bar: that `#secondary` is the map paired
with the location tree, never idle, and not this sidebar.

**The stack, unchanged.** Clicking an entity link or "consult the scan" pushes a
card to the top; the stack keeps what you opened, in the order you opened it, and
a pinned card stays above the rest.
It is what makes an annotated edition readable: what you consulted stays
consulted, and a footnote never costs you your place. Pins persist per page in
`localStorage`, because a pin is a deliberate act and losing it to a refresh
teaches you not to bother.

**A map is not a card — it is a pane above the stack.** There is only ever one
*here*, and a map that was a card like any other could sit in the stack twice
saying different things about where you are, or be pushed out of sight by the
next three. So: one pane, at the top. An entity's own page renders it filled;
the page view and the atlas ship it shut, and the sitting's selection or the
first click on a located entity opens it. The atlas's tree links to the entries,
as every place link does — the click is the map act, the href the fallback. Dismissal is "not this one" rather than a setting — nothing is
written down, and the next such click brings it back. An entity the atlas cannot
draw leaves the pane alone: swapping a map you were reading for a sentence about
an absence loses more than it says, and the card's own rows already say it.

### A footnote read where it is cited

**Nothing is fetched and nothing is re-rendered.** `page.html` already puts every
note into `#foot`, server-side, from `doc.notes`; `edition.js` floats that note's own
body beside the marker citing it. A popup with its own renderer would be a second
spelling of text the server has already sent.

**The marker is a switch, and the jump is in the note.** Hovering a `.noteref`
gives a look, gone when the pointer leaves; clicking keeps it; clicking again
closes it. That means the anchor's own jump — `.noteref` is an `<a
href="#note-N">` and travels with no script at all, which is what this degrades
to — is taken away, so it is offered back at the note's own foot as `jump ↓`,
under a dashed rule. A marker that opened on one click and travelled on the next
was two acts on one target, distinguished by nothing a reader can see.

**One shape, hovered or kept.** `show` takes no is-it-kept flag. Rendering the
jump row on the click alone made the popup grow under the pointer — the same note
in two shapes, the second arriving as a jolt at the moment of clicking. And the
row sits left, with the note's text: the popup is `width:max-content`, so a row
set against its right edge lands somewhere different for every note.

**A kept note is a place.** It is something you *read*, and a note routinely
holds an entity link of its own, so the price is the guard in the outside-click handler,
which spares clicks landing inside it. `edition.js` publishes its `place` on
`window.CARDS` so the two things that float beside a link in this text are put
there by one piece of arithmetic.

A hovered note can be reached the way the preview can: leaving the marker starts
the same `GRACE_MS`, published on `window.CARDS`, and the pointer arriving in the
note — or in a preview floated off one of its links — cancels it.

A kept note follows its marker as the page scrolls and goes when the marker
leaves the window: it is `position:fixed`, and `place` would otherwise peg it to
an edge, pointing at nothing.

### The map is a selection, and the tree is its legend

**A click on a place toggles it on the map.** Wherever the name is: in the
running text, in the tree, or on the shape itself. Clicking used to open a card
as well, which meant every name in the running text cost an entry whether or not
a reader wanted to read one; the map is the cheap answer to "where is this" and
the entry is the expensive answer to "what is this". Reading the entry is the `¶`
beside the name in the tree — the atlas's own spelling, and a separate mark for a
separate act rather than a second meaning loaded onto the same click. An entity
the atlas cannot draw has no map act to perform, so its click opens the card at
once; the composed map says which is which (`drawn`), off the store's own
answer to whether the entity has an extent.

**The map is composed in the page** (`harness/web/static/js/geomap.js`), so a static host
draws the same maps a live server does. What the store can answer about one
entity on its own — how big it is, what lies beneath it with a shape, what holds
it, how well founded its outline is — is computed in Python by the function that
owns each rule and served once as `/geo/atlas.json` (`edition_ui.atlas_data`);
the shapes are served by id. What depends on the selection — which members join
it, the frame, the layers, the pins, the tree, the projection — is the script's,
in one copy. The split is the line between a rule about the store and a
composition over it, and no store-walking rule is written twice. The port was
checked byte for byte against the Python it replaced over every entity and a set
of multi-selections before that was deleted.

**A second place joins the first rather than replacing it.** The question a
reader has after looking up two villages is where they are with respect to each
other, and a map that holds one place cannot be asked it. The selection is a
sitting's, kept in `sessionStorage`: it survives paging through the book, which
is the whole point of being able to build one up, and dies with the tab rather
than greeting you tomorrow with yesterday's map. Pins are `localStorage` for the
opposite reason.

### Context is selected, never assumed

**The frame is the box that holds what is selected, and nothing else.** It was
briefly the first common ancestor's extent, on the old argument that a shape
shown inside its container says where it *is*. That argument still holds and the
selection is now what carries it: a reader who wants a place in its parent's
context puts the parent on the map too — one click, visible in the tree, and the
frame widens to hold both. Framing on the ancestor by default meant every map of
a village was a map of the peninsula with a dot on it: most of the picture spent
on a question nobody had asked, and no way to ask the tighter one at all.

A declared `frame:` still wins for the one entity selected, that field existing
to say "look at this box" about exactly this map. **It no longer reaches a
child's map**, which it did while children framed on their parents — a frame is a
viewport authored for one subject, and the subject is now always what was
chosen.

**A pin is drawn for a place that was chosen, and for no other.** The same rule
again. `pins_under` plotted two levels down, so selecting the Chukchee Peninsula
put thirty-four village dots and thirty-four labels over the outline and named
all thirty-four in the tree — none of them asked for. Member *shapes* are still
drawn, because a region with nothing inside it is an empty outline and the nine
basins under Chukotka are the picture the hierarchy was authored for.

### The tree is the map's legend

**It runs from the first common ancestor down through every record the map
drew** — the members and the extents nothing else can identify — and it is built
from the layer construction itself rather than from a second walk of the store,
because the two would agree today and diverge on the first change to either. A
shape on the map with no name under it is a shape a reader cannot ask about. Its
links light shapes exactly as the running text's do, and clicking one toggles
that place exactly as the running text's does.

**And it lists what a chosen node offers, which is not the same set.** Since a
pin is drawn only for a chosen place, selecting the Chukchee Peninsula gives its
outline and no villages — and with the tree holding only what was drawn there was
nowhere left to find one. So the direct children of a selected node are listed
whether or not the map drew any of them: select a region, read what is in it,
choose one. Direct children and no deeper, and only under a node the reader
chose, or the tree would be the whole atlas with the map buried in it.

**Open is the legend; the fold is the offer.** A flat list makes the pane taller
than the map it explains — you scroll past the names to reach the picture — and
the peninsula's forty villages are exactly that list. Keying the fold on whether
a row is *drawn*, rather than on whose child it is, answers both at once: what is
on the picture is open, what is merely available is behind a count, and chosen
rows sort to the top. A node carrying a selection is never folded whatever else
is true of it, or a place the reader chose could be buried in a closed summary,
drawn on the map with no name anywhere to light it.

The fold is `<details>`, which opens without JavaScript and is keyboard-reachable
and screen-reader-announced for free. Which folds are open *is* remembered, in
the pane and not on disk: choosing a place from inside one repaints the tree, and
a fold that came back shut every time meant opening the same list once per
village. It is where you are in a list rather than a decision, so it does not
outlive the page any more than a scroll position does.

The one control left on a node is **hide** — do not paint this. It used to move
the frame as well, which is the selection's job now.

**Hiding re-composes nothing, and that is what the sheet is for.** The map is
drawn into the union of the per-entity boxes with the `viewBox` opened on the
frame inside it, and each entity's rectangle travels already in the sheet's
units. Choosing a frame is then writing one of them into the `viewBox`: nothing
is re-projected, and the framing rule stays in `compose` in one copy — what
`map.js` reads is its answer. Since the frame is a union of those same boxes,
hiding can only tighten it, so a re-frame never wants a ring that was culled as
off-sheet. Adding and removing compose again, because they change what is drawn
and not only what is seen.

**Every path on that map carries the entity it belongs to**, so resting on a
name anywhere — a `contains` row, a node in the atlas tree, a word in the
running text — lights up its shape. That identity has to be carried because
nothing about a path recovers it: a drawn member is the nearest descendant
*with* a shape, found by descending through those without, so it is not reliably
the child whose name you are on; and two entities may share one polygon outright
— a people and a subgroup inside it may both name one Asher shape — so the
shape could not name the member even in principle. `geo.member_shapes` and
`geo.pins_under` return the entity beside the thing to draw for this reason, and
`geomap.js`'s `owned` is what attaches it. The coastline claims nothing, which is
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

**An inherited extent draws the outline it came from, dashed.** A subgroup with
no shape and no village — the Reindeer Chukchi, the Kavraˊlɪt — is framed on its
people's extent, reached by `part-of:`. The containing outline is the tree's
root, which climbs `within:` alone and never reached it, so the map framed the
right box and drew nothing inside it, under a caption naming an extent that was
not there. The people's shapes are drawn in the context layer, not as the
subject: they bound the subgroup without being a boundary anyone claimed for it.

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
ancestor and descendant at any depth — rides in the pane (`.warm`), and it warms
that union with its own `data-ent`s when it loads. That is the whole of "an entry
preloads its ancestors and descendants".

**Resting on a link fetches its card, and resting longer floats it**
(`static/js/edition.js`). Two behaviours over one fetch, memoised by URL — the one
string this and the stack both already hold, so a card rested on before it was
clicked opens with nothing to wait for. The preview renders the *same*
`/partial/` fragment the stack renders; there is one template per kind of card
and this adds no second one. A figure link — `a.fig`, in the prose or on the
List of Illustrations — has no fragment to fetch: its card is built in the script
from the link's own attributes (`figureCard`), and the preview floats that card's
body, so resting on `Fig. 87` shows the crop before any click and the look and
the card cannot name two different pictures. Building the card sets the crops'
`src`, which is what the prefetch timer warms there in place of a fetch.

A floating preview used to be argued against here, and the argument was that a
tooltip which vanishes is no substitute for a stack. It is not, and the preview
does not try to be one: it never replaces the click on the link, and it holds
nothing the card would not. It answers the question you have *before* clicking —
is this the one I mean? — and the stack answers everything after.

**The preview can be reached**, because its own links are what a reader wants
from it. Leaving the link starts a grace period (`GRACE_MS`), entering
the preview cancels it, and a click inside lands on what was clicked. A link inside
a preview opens no preview of its own — one float at a time — which is what keeps
it safe on a page that is itself a card. **On touch the first tap is the hover**:
it shows the preview and is swallowed, and a second tap on the same link is the
click. Which it was is read off each tap's `pointerType`, not a media query, since
a touch-screen laptop has a mouse too.

**That fragment deliberately carries no map**, which is why an entity's page
composes the entry and the pane rather than putting the map inside the card.
Both a preview and a card in the stack are read *while* the pane is showing the
geography, and the same hover that floats the preview is lighting the shape up
over there — a second copy inside the card would answer a question nothing was
asking, at a map render per hover. A `map` link floats no preview at all: its
answer is the pane.

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

**The encyclopedia index is a tree over the class**, and then over
`entities.kin_parent` inside it — `part-of:` first, `within:` after, and only
where the parent is in the same class. Following the field across classes would
file the rivers under *place* and leave *water* a list of orphans; such an entry
sits at the top of its own class and its card names the parent. Every class
appears, including the ones nothing is filed under: a list of only the populated
ones would show half the vocabulary while looking complete.

**And a card carries the same tree, narrowed to one entry** —
`edition_ui.kin_tree`, rendered by `_kin.html` between the property rows and the
forms. The `part-of:` row above it names the parent and can say nothing about the
grandparent or about one sibling, which is the question a bare parent row raises:
a genus card said *Salmonidæ* and left a reader to guess whether the family sat
under anything and what else was in the genus. It is a **spine, not a subtree** —
every ancestor to the top of the class, each holding only the child on the path,
then the entry, then its direct children and no deeper, with what a node holds
below that said as a count. The map tree earns its breadth by being a legend for
a picture; a card that opened onto the whole of *animalia* would bury the entry it
is about, and a branch is one click away on the node that owns it. An entry that
belongs to nothing and holds nothing gets no tree at all, rather than its own
heading back in smaller type.

**Two hierarchies, drawn as one shape.** The card's tree is the encyclopedia's
edge and the pane's is the atlas's (`kin_parent` against `tree_parent`, kept
apart for the reason at `part-of:` above), so a located entry can show both at
once and they will disagree — `people:naukans` under a village on the map and
under `people:yupik` on the card, each right about its own question. They share
`.ent-tree` in `edition.css` and nothing else: the shape, the rails and the fold
are one rule because a reader who has read one of these lists has read the other,
while `.map-tree` in `geomap.css` holds only what a map means — the paint toggle
and the struck-through hidden row. A card's node has no controls, so its name is
the link rather than a toggle with `¶` beside it.

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

### The static build is the served output, written down

`harness edition build OUT` writes the reading view as files a static host can
serve under `/jesup/bogoras-chukchi`, the prefix its folders give it (`--base`
overrides). `OUT` is that prefix's directory, so two texts can sit side by side (`harness/web/build.py`; flags in `VERBS.md`). **There is
no second renderer.** The build mounts the same router `edition serve` does,
asks it for each page through a `TestClient`, and writes the bytes it gets.

Three changes to the live view are what make that possible, and all three hold
for the live server too, so the two cannot drift into two URL schemes:

- **One mount prefix, passed as a string.** `edition_ui.BASE` is the default and
  the only definition. Every function that writes a link takes `base`, and the
  routes read it off `app.state`. That is how an app mounted at `/bogoras` gets
  links that agree with its routes. The static files' prefix, `assets`, follows
  the same rule.
- **An address is a file's address.** A card's bare fragment is `/partial/…`, not
  `?partial=1`, because a host ignores the query. An image or a sound carries its
  file's own extension (`/leaf/1-361.png`, `/leaf/1-361/colour.jpg`,
  `/tts/….wav`), because a host types a file by its name.
- **`app.state.static` drops what only a server answers**: the search form and
  the ratify button. Search is a lacuna for now. The map is not among them: it
  is composed in the page, so the build writes `/geo/atlas.json` and every shape
  it names (found by reading that file), and no map at all.

**It crawls from the index; the stores do not seed it.** A page's hrefs are
followed, along with the URLs its scripts build out of `data-` attributes.
`build._derived` restates each of those rules beside the script that owns it, so
a script asking for a new URL fails the build until the rule is restated. The
stores are read afterwards, to name what exists and was *not* reached. The
annotations index had no link from anywhere for its whole life, and the first
build is what said so.

A redirect becomes a stub that forwards, keeping its fragment. A locator's
refusal, such as a folio no witness places, is a page, and is written as one.
Two builds of one tree are byte-identical, so a refactor can be checked by
rebuilding and diffing.

**A build holds the stores still** (`cache.frozen`). The live view digests every
file it reads on every request, which is right under an editor and was most of
a build's time. A build is one snapshot whatever the cache does, so inside it
each file is read and hashed once. **The crawl is pooled over processes**
(`--jobs`): each breadth-first level fans out to forked workers, which inherit
the parent's warmed corpus caches. The parent takes their results in the order
it handed them out, so the crawl follows links, refuses and writes exactly as
the serial one does. `--jobs 1` is that serial crawl, and the two build the
same bytes.

### The public site is those builds under one page

`harness site build OUT` writes `OUT/index.html` and runs that build for each text
whose `project.json` declares `publish`. Going public is a declared act, per text
and tracked, so a text can publish its drafts or only what is collated, and a text
saying nothing stays off. `harness/web/site.py` holds the rule that decides what
to rebuild, and `VERBS.md` the flags and marks.

**A text's picture is an editor's choice**, so `project.json` declares it, as a
figure and a caption, and nothing picks one by rule. The landing page shows a
downscaled copy linking to the text. In the licence text, `<hi rend="bold">` in the
header is what shows bold, so the header stays the one statement of it.

**A rebuild is decided by timestamps, and the rule leans towards rebuilding.** A
false rebuild costs a minute; a false skip publishes a stale page that nothing
marks. So upstream is everything but what is shown to be unread, code included.
`test_every_store_a_build_reads_is_upstream` holds the set against what a build
reads through the cache. `cache.py` rejects mtimes as a cache key because a stale
hit there is silent; here they are tolerable only because a tie rebuilds and
`--force` exists, and the rule's blind spots are listed in `harness/web/site.py`.

**A withdrawn text comes down.** A folder this verb built that no text publishes
now is deleted, since leaving it would keep serving what the manifest took back.

## The prose points at itself, and now the pointing works

The book cross-references constantly — `(Plate XXVII, Fig. 3)`, `(see Plate
XXIII, Fig. 2; also Fig. 177)`, `Fig. 87 represents a knife used for` — and every
one of those names a picture the figure store already holds. `harness/figrefs.py`
finds them and `web/edition.figref_rows` says which. A resolved reference
becomes `a.fig`, which is the List of Illustrations' own class, so it opens a
stack card through `openFigure` and the behaviour is not written twice.

It points at its own **leaves** and its own **chapters** too — `See p. 15.`,
`Compare pp. 33, 161.`, `See Chapter XII.` — and those go through the folio index
rather than through `gt/fig/`. Four kinds of `<ref>` and one scan; the page is
the one not found on the same terms as the other three, and the section below is
about why.

### The mark is in the page, because a link nobody reviews is not an assertion

**`tei generate` writes the reference into the TEI and the collator sees it**, as
`<ref type="figure" n="3" cRef="Plate XXVII" resp="#mz">3</ref>` — the same rank,
the same licence and the same re-derivation as an entity link. `validate` scans
each block's own text on every run and checks both directions: a mark the text no
longer supports is an error, and a printed reference carrying no mark is a
worklist line, since deleting one is exactly what the collator is shown it for.

It was found in the renderer until then, and the asymmetry was not principled.
The link existed only in served HTML: no collator met one, `tei validate` had
nothing to say about it, and the failure it can produce is not a dead link but a
*working* one — a number scoped to the wrong plate opens a real leaf whose
caption reads correctly under the wrong picture. The only witness was a reader
who clicked.

**What is in the page is the scan; what is not is the resolution.** Which
numerals the page prints as a reference is a fact about a string that no store
can invalidate. Which picture each names is a join over `gt/fig/` that a moved
box invalidates at once, and `stores.render` caches on the TEI's bytes alone — so
a `ref/key` written into the page would go on being served after the box moved.
The two halves of `figrefs` fall either side of that line, and the same cut
already governs `<figure>` and `_figures`. **It is a cache boundary and not a
no-script one**: `_hang_pictures` splices both joins into the served page per
request, off `harness/web/templates/edition/_figure.html`. They were assembled
on the client once, and
the pictures were then the one part of the edition a reader without JavaScript
never saw — an adjudicated caption over a blank space.

The authority guard moved with the scan, for the same reason in the other
direction: `tei generate` refuses to mark another author's plate at all, rather
than marking one the edition is bound to decline and putting a question to the
collator that `Authorities Quoted` had already answered. `apparatus.authority_names`
is the one home of that lookup now — the generator, the validator and the
resolver ask it the same question.

**The guard reads what stands in front of a reference, and that is a real
limit.** `Kroeber’s Fig. 52` is caught — the possessive is the printed evidence
and the store holds the name, and both instances of it were marked as this book's
until the mark went where somebody could read it. `Fig. 525, a, in Boas’s Central
Eskimo` is not: the name comes *after* the number, and nothing in front of it
says whose figure it is. That one is now a `<ref>` in the page rather than a link
in the HTML, which is the point — a collator with the sentence open can delete
it, and before this there was nothing to delete.

**The stack, not the lightbox**, which inverts the rule everywhere else and for
that rule's own reason: a picture goes to the lightbox because it is already on
the page, and a cross-reference is precisely a picture that is *not* here. The
card stays open beside the sentence that sent for it.

### Plate scoping is the whole of the difficulty

**The book restarts figure numbering at 1 on every plate.** So `Fig. 1` names 31
different pictures and the List of Illustrations has to print it plain — but
`Plate XXI, Fig. 1` names exactly one, because the plate scopes it. The prose has
the scope the list does not, and this is a join the list cannot make:
`by_plate` gives the leaf, and the picture is the one on that leaf whose caption
prints that number. Matched against the captions, never counted into a list — a
plate whose caption prints no number resolves to nothing rather than to its
neighbour, which is `in_printed_order`'s discipline one level up.

Scope ends at punctuation, and only punctuation. `Plate XXIII, Fig. 2; also Fig.
177` is two references: the `;` is what says the second is a text figure. Getting
this wrong is not cosmetic — it points a reader at a different leaf, with a
caption that reads correctly under the wrong picture.

**The same `;` also joins, inside one run**, and the two are not in tension: it
separates *members* and ends a *scope*, and what tells them apart is whether a
numeral follows it. `Figs. 44, a¹; 46, a¹; 46, b` (1-171) and `Figs. 188, a, i;
190, b; also Plate XXVIII` (1-334) are runs whose members carry sub-letters, so
the comma is spoken for inside a member and the printer raises the separator a
rank; `; also`, `; see also Fig. 177` and `Fig. 69; b` are not runs, and each
ends where it stops naming numbers. The licence is the figure run's alone — a
semicolon in the roman loop would read `Plate II; I have seen` as two plates,
`I` being a numeral.

The same fact runs the other way for a *bare* number. A plate's figure number
means nothing away from its plate, so it is never cited alone; a bare `Fig. 2` is
therefore the text-figure series, and dropping the plate leaves from `by_number`'s
answer turns ten of the list's unresolvable collisions into links. `Fig. 1` still
refuses — 31 pictures print it and none is on a text page, the fold-out map
having no box in `gt/fig/`.

### Another author's plate is not a link

Bogoras cites other people's plates in his footnotes in the same words he uses
for his own, and **`Sauer, Plate XIV` collides with this book's Plate XIV
outright**. Nothing in the reference tells them apart; the name in front of it
does, and `Authorities Quoted` is a store of exactly those names, keyed by a
human. Between the name and the reference only citation furniture may stand — a
comma, a short title, `in`, a page locator, an opening bracket, a reference the
same citation already governs — so a sentence's worth of prose ends the citation
and `Nordenskiöld wintered here. Fig. 88 shows the ship` links normally.

**A second guard stands beside it, and reads the number instead of the
sentence.** `figrefs.outside_the_book` asks whether the book prints a picture of
that number at all: the printed List of Illustrations carries plates I–XXXV and
figures 1–302, each complete with no gap, so `Schrenck, Plate XXXVI` and Boas's
`Fig. 525` are refused whatever the prose around them looks like. The numbers
come from the book's own apparatus and not from `gt/fig/` — taking the range off
the boxes would have made every unkeyed figure foreign. The two are independent
witnesses and both must pass: the first is silent on `Fig. 525`, which names its
author *after* the numeral, and the second is silent on every foreign citation
whose number happens to fall in range. `docs/decisions.md` has the sweep that
found the second one needed, and the seven fabricated links it turned up.

The prose guard is asked in three places on the same terms — `tei generate`
refuses to *mark* another author's plate, `tei validate` re-derives that refusal
as an `#mz` claim, and the reading view refuses to *link* one a collator wrote by
hand. **The range guard is the reading view's alone**, because what it asks is
not a fact about the string the page prints: which numerals are set as a
reference cannot be invalidated by any store, and whether the book prints a
picture of that number is a join over an amendable List of Illustrations. It
falls on the resolution side of the cut for the reason the whole of `figrefs` is
cut that way.

So the two guards are not measured in one place. Over the generated corpus
after a regeneration: **779 of 794 marks link, 14 refuse because a store
declined, and 1 is outside the book's numbers** — Boas's `Fig. 525`, which names
its author after the numeral and so reaches the reading view for the range guard
to catch. None refuses as another author's, and that is the generator working
rather than the guard idling: the fourteen it would have caught are no longer
marked. It stays because a mark a collator wrote by hand is not bound by what the
generator would have done. Every refusal names what declined and shows it on
hover: a reader has to be able to tell a gap in `gt/fig/` from an edition that
does not link.

**`edition figrefs` is the census**, one row per mark with what became of it, and
`--refused` is the worklist. It goes through the same join the view serves rather
than asking the stores again, because two answers to one question are free to
disagree and to go on disagreeing unnoticed — which is the thing a census is for.
It exists because the seven fabricated links above were found by hand, by five
scripts that did not agree on what to count, after being servable for as long as
the marks existed.

### A page reference proves itself in the scan, because the guard cannot save it

`See p. 15.` is the same act as `Fig. 87` — the book pointing at itself — and it
carries the same mark, `<ref type="page" n="15" resp="#mz">15</ref>`, re-derived
by `validate` on the same terms. What differs is **where the discrimination
happens**, and it had to move.

A plate reference can be scanned permissively and disqualified afterwards,
because `Plate XIV` is the printer's furniture and the name in front of it is the
whole question. A page locator has no furniture at all. `p. 24` is `p. 24`
whoever's page it is, and in these footnotes it is usually not this book's: **268
page locators are printed across the generated corpus and only about a quarter
point here.** The rest close a citation — `Nelson, Fig. 93, p. 271`, `Ibid.,
p. 115`, `See Vol. VI, The Koryak, p. 123`, a `p. 1275` that is Middendorff's.

Handing those to the authority guard was measured rather than assumed, and it
does not hold: **155 of the 268 survive it.** The guard was built for plates,
where the author stands immediately in front; a page locator stands at the *end*
of the citation with `Plate LXXVI, Fig. 1,` in between, and the gap pattern
stops at the first full stop. Widening the gap to admit a figure run recovered
some of it and never all — and the residue is not noise. It is the failure this
whole apparatus is organised against: a mark on `Nelson, …, p. 271` opens leaf
271 **of this book**, under prose that reads perfectly well there, with no error
signal anywhere.

So the *construction* is matched instead of the locator. A cue — `See`,
`Compare`, `cf.` — opening its own clause, optionally `also`, and reaching the
locator with nothing between. That is a sentence pointing at this book, and it is
not a fact about Bogoras: it is how a self-reference is set in any monograph,
which is the part worth having. Anything richer is a citation and prints plain.

**71 marked, and the whole 71 were read against the printed text: no foreign
citation among them.** The cost is about fifteen page references that *are* this
book's and stay unmarked — `See Fig. 110, p. 190`, `Compare the Oˊnmɪlɪn Group,
p. 26` — which is the direction the List of Illustrations already takes on a
collision, and for its reason. An unmarked reference is a worklist line a
collator can add by hand. A wrongly marked one is a working link nobody can see
is wrong.

Two near-misses fixed the "nothing between" clause and are pinned as tests,
because both print a bare parenthesised locator that a looser rule would have
taken: `1-066`'s *He even asserts (p. 77)*, where the *He* is Maydell and the
sentence before it named his volume; and `1-068`'s *one of the texts published in
my “Chukchee Materials” (p. 52)*, which is Bogoras's other book.

**Resolution is an address, not a join**, which is why the renderer links it
directly to `/folio/{n}` — the route every other folio link in the edition goes
through — instead of building a handle for `figref_rows`. Nothing about it is
invalidated by a moved box, because no box is involved. 70 of the 71 reach a
witnessed folio today; the one that does not, `2-070`'s *Compare p. 339*, lands
on the folio route's own refusal page, which names 337 and 344 as the nearest
leaves that have a witness. That is the same reason there is no `unresolved`
state on `a.pageref` and there is one on `a.figref`: a figure handle can come
back empty, and a folio always leads somewhere.

### A chapter reference is scanned on the plate's terms, not the page's

`See Chapter XII.` is the fourth kind, and it goes back to the permissive scan:
`Chapter` is the printer's furniture, the roman is the handle, and the name in
front of it is once again the whole discriminator. `Compare Bogdanovitch,
Chapter V.` is Bogdanovitch's fifth chapter and `foreign_citation` catches it
standing exactly where it stands in front of a plate. **That is the difference
from a page locator in one sentence:** a plate and a chapter have furniture for a
name to govern, and `p. 24` has none.

19 chapter references printed across the generated corpus, 1 behind an authority,
and **every one of the remaining 18 names a roman `edition/toc.json` holds as a
chapter** — no misses, and no ambiguity to resolve.

Resolution is `/chapter/{roman}`, which looks the id up rather than building it.
`chXII` is the ToC's own spelling and concatenating `ch` with the roman would be
the route asserting the store's key scheme from outside it; the entry whose
`chapter` is that roman at the chapter level is what the store *says*. A roman
the ToC does not hold refuses at serve time rather than at scan time — the
reference is a fact about the printed page and where it points is a fact about a
store that can be incomplete, which is the division `figrefs` is built on
throughout. It inherits the locator's precursor property with it: the link
resolves today wherever a witness places the chapter's first folio, and keeps
resolving unchanged the day that chapter becomes a run with a page of its own —
which is the chapter's name, `/chapter/xii/religious-ideas`.

**A chapter named by its title is deliberately not matched.** `See chapter on
shamanism.` would resolve — `Shamanism` is a level-1 title and nothing else — but
`See chapter on charms.` would have to choose among six entries carrying
*Charms*, of which `Charms and Sacred Objects` is merely the one that happens to
be a chapter. A rule that resolves the first and guesses the second is worse than
one that leaves both as worklist lines, and two attestations do not pay for the
machinery.

### A figure is not a box

16 figures are drawn in two — the print letters them *a* and *b* under one
caption, and `1-123`'s Plate V sets two pictures with one caption and no number
at all. `key` is the first of those boxes and is the figure's identity, which is
right for keying a reading and wrong for showing the thing: every path that built
a card from `key` alone drew the upper picture and silently dropped the lower,
the List of Illustrations' own links included. `figures.crop_keys` is the one
rule now, and `by_number`, `by_plate` and `resolve` all go through it.

## The editor's annotations: notices and supplements

Everything above is either the book or a handle on the book. `edition/annotations/`
is the one store where the editor speaks **as the editor**, and it has two classes
because the two things an editor needs to say want opposite placement:

    notice      retrospective context, or a correction. Renders **above** what it
                attaches to, in front of the reader before they meet the text.
    supplement  further material, mostly on the web. Renders **below**, offered
                after the reader is done.

**The class is the placement.** `annotations.ANNOTATION_CLASSES` maps one to the
other once, so no file and no template can disagree with the directory a file
sits in, and an author cannot put a block in the wrong half of the page by
typing a field. There is deliberately no `placement:` — the same ruling `auto`
makes for an alias, a closed vocabulary whose consequence is derived rather than
restated.

**Attachment is declared on the annotation and never on the target.** One file
carries the whole join, so adding a notice touches no page, no entity and no
`toc.json` entry, and the authored order of `attaches:` survives to become the
"attached to" list on the annotation's own page. The alternative — a `notices:`
field on each of fifteen pages — would state one fact fifteen times and give the
gate fifteen places to find it stale.

A target is namespaced, and there are three: `page:3-060`, `toc:chII.1`,
`entity:people:mongoloids`. One ordered list rather than three fields, because
`check`, `coverage` and every resolver want exactly that list; three fields
would be merged back into it at parse time, which is three spellings of one
structure. The entity form's second colon is harmless — the split is on the
first.

### `status:` gates attachment, not the annotation's own page

A `proposed` annotation is served at its own URL, with its pill, and attaches to
nothing. The asymmetry against the entity store is the point. An entity card is
reached by a click; **a notice is the editor's voice inserted at the top of the
artifact, unasked**, and rendering an unratified one there would be the edition
asserting something no human signed. Reviewing it before ratifying is exactly
what the standalone page is for, and a store whose unratified entries were
unreachable would have no review step at all.

### The prose points into the links table by alias

A `## links` row is `alias | url | title | note`, and `[[melodiya-1974]]` in the
summary or the long text resolves to it. This is the entity store's own
arrangement — a table of forms, and prose that points into it — applied to URLs,
and it beats both alternatives: a bare table asserts nothing about why a link is
worth an hour, and bare prose links put one URL in two places with nothing
holding them together.

**An alias never holds a colon and `entities.WIKILINK` requires one**, so
`[[people:mongoloids]]` is an entity and `[[melodiya-1974]]` is a link,
decidable by shape with no rule having to guess.

**`edition_ui` needed no change for this, and that is deliberate.**
`inline_html` resolves wikilinks through `_entity_link`, whose whole safety
argument is that its rule set is closed — it knows one store and escapes
everything else. `annotations.expand_links` rewrites the alias into an ordinary
`[title](url)` *before* `gloss_html` sees the text, so the result goes through
the `_LINK` rule and the `LINK_SCHEMES` allowlist that were already there. No
new markup path, and no fourth thing marked safe.

The table earns its place by being checkable, which is what prose links could
not answer. `check` refuses a non-`http(s)` URL, a duplicate alias, a duplicate
URL, a `]` in a title, whitespace or parens in a URL — the last two because
`_LINK` would then fail to match and leave raw brackets in a reader's prose —
and an alias the prose reaches for that no row defines. A row nothing references
is reported and never gated: a shelf may hold more than the summary discusses.

**`[[notice:…]]` is refused**, with a markdown link to `/edition/annotation/<id>`
named as the alternative. It looks exactly like an entity reference and
`_entity_link` would render it as a dangling one, silently, in the reader's
prose. Teaching that function a second store is a change of its own.

### Reaching a section's pages, and the refusal that has to be spoken

A notice on `chII.1` must surface on that section's pages, and there is no
stored page→section map: `state.toc_containing` answers from a **folio**, and
its docstring forbids writing that to a store. So the chain is
`ref → folio → toc ids`, and the middle step can refuse.

**`annotations.for_page` takes the chain and never computes it**, and never
touches the filesystem. If the lookup lived there, an empty list would mean two
things at once — *nothing attaches here*, and *we cannot say whether anything
does*. Only the route holds the folio, so only the route can tell the template
which happened; where it cannot, `page.html` prints a sentence saying so, on the
same ruling the contents panel follows. Guarded by `has_toc_attachments`, so a
corpus holding no section attachment does not grow a banner about a kind of
annotation nobody has written.

`annotation coverage` is the report, and its `unwitnessed` column is **a bound,
not a miss**: without a witnessed folio a leaf cannot be shown to fall inside
the attached section *or* outside it, so the set a section attachment misses is
not computable at all — only its size is. Nothing interpolates a range between
two `page_start`s, either; a notice appearing on a page nothing placed would be
indistinguishable from one appearing on a page that was.

The workflow this implies is the right one, and it matches the rest of the
project: **the section attachment is enrichment over an explicit page list**, not
the mechanism relied on. The author names the pages they care about, and
`coverage` says what the section adds on top — for
`notice:physical-anthropology` today, nothing, because both pages `chII.1`
reaches are already named. That is the honest answer and the verb exists to give
it.

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
real ambiguity in `config/marks_exempt.json` — where a headword scheme would have
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

**A file exists only where somebody wrote a note.** `edition/entities/` holds a hundred
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

`/lexicon` is a tree over the eight Tier-1 codes plus an **unassigned** branch,
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
account of his notation in the front matter to *Chukchee Mythology* (1910),
described by the man who devised it — vowel and consonant grids on folio 3, a
gloss per sort on folio 4. `key` is the p. 10 key, already binding apparatus
here, and it supplies the unmarked ASCII sorts that account does not reach (`c`
is English *sh*, `j` is French *jour*, `x` is *Bach*) plus the seventh member of
the palatalization series. Where a source gives two values — `ʟ` is ɬʲ ≈ ɬ — the
**first** is emitted and the row is reported `hedged`; choosing per row by which
value looked better would be judgement dressed as a table. Where a sort has only
a *gloss* — "like *a* in *make*", "velar r" — there is **no row at all**, because
turning a gloss into a symbol is a judgement and not a lookup. Same for U+0027,
which is both the spirant and the pause mark and which `keying_spec.md` says not
to propose.

**The two grades are not two spellings of one notation**, which this said and
`ipa.py` said with it. Mythology's is the *reduced* notation of a text volume:
p. 10 has `g x x˙ š c j ë ḷ ṛ` and the six-member spirant series, none of which
Mythology carries, and p. 10 has four laterals where Mythology has three. `myth`
means Bogoras described this sort, not that this volume sets it.

### Reconciled against the modern phonology

`ipa.MODERN` maps each sort to what current descriptions call the same sound
(/m n ŋ/, /p t t͡ʃ k q ʔ/, /β s ɣ ɬ/, /ɻ j/; /i u e₁ e₂ o a ə/ under
dominant/recessive harmony). **A second table and not a column, because the two
disagree systematically** — over length on nearly every form, over a whole
palatalization series, and over every voiced obstruent — and folding them
together would make one of them invisible. It is a witness about *value* with no
standing over the printed key about *glyph identity*, which is what the firewall
governs; it is a tertiary source; and Bogoras recorded c. 1900 speech across
dialects it does not separate, so a contrast he heard that it does not list is
not thereby his error. Its empties are findings rather than gaps: no native
voiced obstruents, so `b d g ǰ j z` are loanword sorts; no palatalization series;
and several of his contrasts are one phoneme — three rhotics to /ɻ/, four
laterals to /ɬ/, `v` and `w` to /β/.

**Length is kept where the two part hardest.** Bogoras says a, e, i, u are
"always long" and every one of them is emitted with `ː` — 567 of 606 attested
forms — where modern descriptions give Chukchi no phonemic length. The ruling is
that this table renders what Bogoras said his letters sound like; `MODERN` is
where the other reading is written down.

**Six things the audit against those three pages changed**, each of which had
been a plausible-looking row: plain `g` had no row at all, so every form
carrying one came back partial — `g̣iˊrgol` resolved its dotted g and choked on
the bare one two letters later; `g̣`'s `ɡ` alternative is withdrawn, since there
are no native voiced stops and ɡ is the value that belonged to the missing `g`;
ᴀ ᴇ ɪ are one vowel, ə, where they had been rendered three ways on a joint
gloss; `ᵉi` keeps the laryngeal Mythology says it *always* has and takes its
prominence on the closing element, as `keying_spec.md` §2.5 already said; `oi`
is ɔi̯, matching the same table's own `o`; and `ʟ`'s hedge was inverted — the
modern lateral led as the afterthought. `h` is aspiration on the preceding
segment rather than a segment (editor's ruling), which is what "used after č, t,
l" describes and where 74 of its 108 corpus occurrences sit.

Stress is dropped: U+02CA follows the stressed vowel where IPA's `ˈ` precedes the
stressed *syllable*, and placing it needs syllabification. It still earns its
keep on the way out — `au` is one diphthong and `aˊu` is two vowels, because
longest match sees the mark standing between them.

**587 of the corpus's 610 native forms resolve completely** (`lexicon ipa --all`),
where before the audit it was 580 — the six that plain `g` was failing came back
with its row. The 23 that do not are a worklist, not noise: 19 want a row for a
sort that has only a gloss (9 `ṛ`/`ḷ`, 8 `ë`, 2 `š`), 2 carry a curly apostrophe
the Tier-1 ASCII policy forbids — a ground-truth defect the imputation happened
to surface — and 2 are a stray `z` and a `□` placeholder.

Two losses on the way to the speaker are worth naming, since neither is a gap in
the rule table: the connector hyphen and the short `ĭ` have no `speech.TABLE`
row, so 193 and 4 forms respectively reach espeak with a symbol dropped. The
hyphen is silent anyway; `ĭ` is not.

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

`/tts/<ipa>.wav` is a **pure function of the string in the URL** and deliberately does
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

**It writes `edition/entities/`, and the click is the human act** — the `zones edit`
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

### The store: `edition/geo/`, compiled and tracked

Three sources, none of them in the repository: 24 watershed delineations and a
53 MB world language atlas in `scratch/` (gitignored, one of them a symlink into
a download directory), and Natural Earth for the coastline. `tools/build_geo.py`
compiles them to `edition/geo/`, which **is** tracked — a clone can neither rebuild
this nor be told why the atlas is empty. The same split `scans/` has: a `tools/`
script builds from what only one machine holds, the harness reads what is
committed. `shapely` is a build-time dependency declared inline (PEP 723);
`edition serve` reads plain JSON and imports nothing new for it.

### Locating an entity: `tools/gazetteer.py`

`edition/geo/` answers "what shape is this drawn as". It does not answer "where is
this village", and for most of the store nothing does: 73 geographical entries
carry no `geo:` and no `frame:`. The gazetteer cannot help — Natural
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

**`--pairs` states the acceptance rule instead of leaving it to whoever reads
the report.** It prints the candidates the entry's own coordinate corroborates —
within `--near` kilometres, and reading as the entry's class — spelled as the
`ID=Q… # why` lines `identify.py set --from` takes. Two witnesses, neither of
them the name that was searched. It lists nothing for an *unlocated* entry, and
that is the point rather than a gap: an entry with no point of its own has no
second witness by construction, so its one plausible candidate is worked from
the report by a human and never from a worklist. The rule is still only as good
as `class_match`, which over a Wikidata description is a grep over free text: it
offered `place:st-michael` the village's **power station**, 0.1 km away and
carrying "in Nome Borough, Alaska" in its description, and only a human opening
the item caught it.

It is a `tools/` script rather than a harness verb because Wikidata is live:
the harness is offline and deterministic over what is committed, which is the
same split `build_geo.py` sits on.

### Identifying an entity: `tools/identify.py`

The gazetteer's sibling, for the classes with no geometry to check against. It
asks the other half of the question — *which item is this* rather than *where is
it* — for `taxon:`, `person:`, `people:`, `institution:`, `source:`, `being:` and
`event:`, and it is the same two-verb split for the same reason: `propose`
reports, a human adopts, `set` writes the `link: wikidata:Q…` and derives the
`link: wikipedia:…` beside it from that QID's `enwiki` sitelink. The article
title is never searched for separately, because a second identification is
exactly a thing that can disagree with the first.

**Every class carries a type gate, because a name match is not an
identification.** A bare label query for `Parry` returns six painters and a
cricketer. So the query says what the answer has to *be* — `person:` an instance
of human, `people:` an ethnic group or a people, `institution:` an organisation,
`source:` a written work — and `taxon:` is not matched on a label at all but on
`P225`, the scientific name, a field whose only purpose is to hold exactly that
binomial. That is why the taxa answered almost entirely by rule where the people
did not: 82 of 109 came back with one candidate each, obsolete binomials
included, since Wikidata holds a synonym item for `Agaricus muscarius` and
`Strix nyctea` and returns nothing where it does not.

**The canonical is asked first and alone; the aliases only answer for an entry it
left blank.** They were peers to begin with, and that was the same defect in
miniature: an entry's canonical is the entity's name and its aliases are what the
*page prints*, which for a `person:` is very often a bare surname. Asked
together, `Franz Boas` and `Boas` came back as one list with a Danish zoologist
in it. Fourteen of the first sweep's twenty-one ambiguous `person:` rows were
that and nothing else. Rows reached through an alias print `[alias]`, and rows
reached through the prefix-search fallback print `[search]`, because each
corroborates less than an exact hit on the canonical.

**A gate can say the answer is a written work; it cannot say the question was
worth asking.** `source:` is the case that proved it. A source entry's canonical
is the *siglum* — `Krause, I`, `Sauer 1802` — and its aliases are other spellings
of the siglum; none of them names anything in the world, and the first sweep duly
matched `Kyber, I` to a post-quantum key-encapsulation scheme and `Sauer` to a
2004 video game, both of which cleared the written-work gate. The title is not in
the entity file at all: it is in `edition/authorities.json`, behind the entry's
`authority:` key, and that is where the terms now come from. The yield fell to
almost nothing, which is the honest answer — most of this bibliography is a
19th-century monograph nobody has made an item for.

**`fill` is the third verb and makes no identification at all.** Where an entry
already carries a `link: wikipedia:…` a human chose, the QID behind that article
is not a second opinion about which item is meant — it is the same
identification, read off the sitelink backwards. The `being:` entries are why it
exists: `taˊɪrg̣ɪn` is filed at *Addison's disease* and `Kalêˊlɪ-taˊɪrg̣ɪn` at
*Vitiligo*, editorial readings no query would have made, and the QIDs follow
from them mechanically.

`animal:` is not searched — a reindeer its herder called by name is not in
Wikidata and never will be — and the four geographical classes are not either,
those being the gazetteer's, with a second witness this file cannot offer.

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

`edition/geo/SOURCES.md` is authored by hand and is a **precondition of the build**,
not a by-product. Asher 2007 is CC BY 4.0, so its citation goes in the corpus
`teiHeader`'s rights statement as well — this file ships with the repository and
the reading view does not.

**One source's licence is heavier than its content and is not settled.** The
basins come from Global Watersheds (mghydro.com) over MERIT-Hydro, which is
dual-licensed **CC BY-NC 4.0 or ODbL 1.0**: the first forbids commercial use by
anyone who clones this, and the second is share-alike on the *database*, which
`edition/geo/watershed/` is. Which branch this edition takes, and whether those
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

### Pictures: `tools/entity_images.py`

A card for a `taxon:`, `person:`, `people:`, `place:`, `land:`, `water:` or
`river:` entry shows a picture, **hotlinked from Wikimedia Commons**. The
repository holds no image bytes. It holds `edition/entity-images.json`, the
ledger of what the offline card cannot fetch: which file, its thumbnail
address and size, its sha1, and what the reader is owed — author, licence and
the file's page. Derived but tracked, beside `edition/geo/`, for `geo/`'s
reason: the source is outside the repo. The scope, the licence pattern, the
lookup and the gate are `harness/pictures.py`'s, and the tool imports them.

**Which picture is a rule, and the card says so.** It is Wikidata's P18 for
the item the entry's own `link: wikidata:` names — no search, so the
identification is whatever a human already made. A preferred claim beats a
normal one, a deprecated one is never taken, and among equals the first wins
and the report says `of N`. Nobody has looked at the result, so it is `#mz`,
and the figcaption reads "via Wikidata". An editor who has looked writes
`image: commons:…` (an editor's pick, captioned without the mark) or
`image: none`.

**The ledger is keyed by QID and by file title, never by entity.** `entity
rename` and a class move therefore touch nothing here, and the class is read at
render, so an entry moved out of scope drops its picture by itself. Titles are
stored NFD, since `edition/*.json` is under `corpus normalize`; they go to the
API as NFC, and the answer is mapped back through the API's own `normalized`
and `redirects` lists.

**Five licence families and no others**: public domain, CC0, CC BY and
CC BY-SA at any version or port, and "Copyrighted free use", which grants any
use. Everything on Commons is free, so this is narrower than Commons on
purpose. A caption naming the author and linking the licence is known to
satisfy these five; it is not known to satisfy GFDL's full
text or a bespoke attribution template. A refused file is reported and left
off, together with its P18. `entity check` re-applies the pattern to every row,
**but that is one witness, not two**: the tool refused by the same pattern, so
the check catches a hand-edited row or a narrowed pattern and nothing else.

**A failed lookup keeps the row it had.** This is the gazetteer's lesson
again: an outage read as "no picture" deletes a true row on the strength of a
timeout. Rows are `+` new, `~` changed (file, sha1 or licence moved), `-`
dropped, `=` unchanged and `!` failed. `retrieved` moves only with its row, so
a re-run over an unchanged Commons leaves the file unchanged.

**What no check here can see** is Commons changing under the hotlink. A file
overwritten after the fetch is served new, under the old attribution, until
the tool re-runs and reports `~`. A hotlink cannot pin a version. That is the
price of carrying no bytes, and it is stated rather than gated.

The report also counts in-scope entries that have a Wikipedia article but no
P18. That number is what would justify a second source: the article's page
image. That is MediaWiki's heuristic pick and can land on a map or a logo, so
it is a weaker witness than P18. It waits on the number.

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

### One location field, and its three kinds of member

`geo:` is **repeatable**, and the field is the union of its members. A member is
one of three things, told apart by its own spelling and by nothing else:

| written | is | resolved by |
|---|---|---|
| `64.4051 -172.2409` | a point | `geo.point_box` |
| `langarea:chuk1273` | a shape in `edition/geo/` | `geo.shape` |
| `place:naukan` | another entity, whose extent this one takes | `geo.extent_of` |

**Human-authored, and that is the point** — identifying a toponym Bogoras wrote
in 1904 with a polygon a modern delineation service returned is an assertion
about the world, and a rule that matched them by name would be the confident
guess this project is arranged against. `watershed:main` and the English word
are one keystroke apart in that file listing.

**It is decidable because a shape kind is held disjoint from `ENTITY_CLASSES`**
— `langarea:`, never any live entity class. That invariant is older than this field and
used to be enforced *negatively*: an `area:` naming an entity class was refused
outright, because it looked like a reference and resolved to nothing. It is read
positively now — it *is* one — which is the same fact doing more work.
`geo bounds` has told the two apart by prefix alone since it was written, with
no flag and no wrong guess available to it.

`entity check` gates exactly this: that a member resolves, as a shape in
`edition/geo/` or as an entity in the store. That is a fact about names, like
`within:` resolving. Everything geometric is `geo verify`'s and **reports**.

### There were two location fields, and the second could only drift

`geo:` held a point and `area:` held a shape, and `parse` carried a rule
refusing a record that had both: `extent_of` read the shape and would never look
at a point beside it, so the point was unreachable by construction and could
only be a second, weaker statement of the same fact that nothing kept in step.
Every word of that was true — of *two* fields. **A rule against a store
contradicting itself is a rule that should not have been needed**, and the
answer was one field.

The `area:` half brought a whole apparatus with it, because a single-valued
field that sometimes had to hold two shapes needed one: a comma split, a
canonical sort so a union could not exist under two spellings, a synthesized
index row corresponding to nothing the build wrote, and a `dict` subclass whose
`.get()` resolved a composite while iteration refused to admit it existed. None
of it survives. `index()["shapes"]` is a plain dict of what the build wrote;
`geo.shape` takes one id; several shapes are several lines.

What is kept is the *reporting*. `geo list` still has a `composites` block,
because "these two polygons are one speaker area" — `langarea:chuk1273` with
`base:chukotka-east-of-meridian`, the Alaskan Yupik pair — is a human's
assertion about `edition/entities/` and earns a row. It claims nothing and resolves to
nothing; its key is sorted so two entities that named the same pair in either
order land together, which is all that is left of the canonical spelling.

**A claim is one hop.** An entity reaching a shape only through another entity's
`geo:` does not claim it, or `unclaimed` would go quiet about shapes nobody has
actually pointed at.

### Transclusion, and the `within:` it replaced

`geo: place:naukan` is the member kind the store could not express, and its
absence had been paid for in the wrong field. `people:naukans` was filed
`within: place:naukan` — a people inside a village — for one reason: `within:`
was the only field that would fetch a box. It worked, and it cost the thing it
was borrowed for. A people hanging from a village hung there in the *tree* too,
so its extent never rolled up to its ethnicity, and the map of the Yupik
excluded two Yupik peoples.

So `within:` is now **reserved for the four geographical classes at both ends**
and `entity check` gates it. It answers one question again — what terrestrial
thing contains this one — which `geo.NESTING` can check and the atlas can walk.
What a thing *belongs to* is `part-of:`; whose extent it *takes* is a `geo:`
member; where it *is* is `within:`. Three relations, three fields, and the store
had three relations all along.

### Item 7: the land east of the meridian is land, and the claim is a human's

Asher's Chukchi polygon stops at 180° and this edition does not move it. What it
adds is `base:chukotka-east-of-meridian` — Natural Earth land, cut by a declared
topological rule (`edition/geo/SOURCES.md` has the rule and why a longitude box
cannot express it), asserting **nothing whatever about speech**.

The join is then one human act, in the entity file, where a reader can see whose
it is:

    harness entity locate people:chukchi \
        --geo langarea:chuk1273 --geo base:chukotka-east-of-meridian --commit

That separation is the design. Sourced geometry in the store; the inference in
an entity, under a `status:`, with a name on it. A shape kind that meant "this
edition inferred it" would have put the inference back in `edition/geo/`, where
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
its own shape and reported with a distance, not as a defect: a river's natural
point is its **mouth**, which sits on the very boundary the basin was delineated
from, and `river:anadyr` was 0.59° out at the estuary. That tolerance was the
width of the thing being measured rather than slack — and the whole arrangement
was an accommodation for a record saying two things about one location. A
basin plus a mouth is two *things*, and if the mouth is worth naming it is worth
an entry; `place:anadyr` is that entry. So `entity check` now refuses a record
carrying both, the check has nothing left to measure, and the section is gone
rather than left as a row that can never fire.

A shape two entities claim is legal — a people and a subgroup inside it may
both point at one Asher polygon, and forcing a choice would be this edition
deciding something the source does not. Nothing in the store shares one today:
every case was a `language:` entry duplicating its people's claim, and that
class is retired.

### The map: server-rendered SVG, no tiles, ever

The server is loopback and the edition is meant to be self-contained, so there is
no map library and no tile fetch. (The one outside fetch anywhere in the reading
view is an entity card's picture, for the reason "Pictures" gives; the map has
no such reason.) One `<svg>`, shapes as `<path>`, every
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
subject's outline goes dark red when its `geo:` names a watershed, which is why
`render` takes a `mark` it does not compute: it sees paths and cannot tell a
basin from a coastline, and inferring one from the shape of a ring is the kind of
guess this project is arranged against. The predicate is the *shape's* type —
a shape member is typed, and `watershed:anadyr` says where the polygon came
from. Every
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
people nests in neither: it has an extent and no parent. So once every
ethnicity carried its sprachraum, the peoples landed flat at the top beside the
one `place` root — and, while a `language:` class still held a second entry per
people, **in pairs drawing the same polygon**, which read as a duplicate when
the two sat adjacent with nothing saying why. That class is retired; the
flattening was never its fault and is still here. The class heading is what says
these are overlays rather than another rung of the tree.

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
tree structure, not shapes. So a node with no shape of its own gets the padded union of
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
a subtree the atlas can draw whose `geo:` puts nothing on it, so they ride
on a parent's frame and put nothing on it. Scoped by the tree rather than by
class, because every person and source in the store is unlocated and always will
be, and a worklist mostly made of rows nobody will act on is one nobody reads.
Its `wants` column separates an entity that needs a coordinate from one already
framed by its members: asking for a boundary for Chukotka is the one thing this
atlas refuses to invent.

`harness entity locate ID` answers a row of it, setting `geo:` or `frame:`.
`--geo` repeats and **replaces rather than appends** — a flag that only added
could never take a member off. It re-parses the file before writing, as
`entity new` does, and refuses a member naming a shape `edition/geo/` does not hold
or an entity the store does not. That is the whole of the
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
