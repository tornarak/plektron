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
- **`geo:` and `within:`** are the geography sprint's, shaped now and consumed
  later. `within:` must resolve and the chain must be acyclic — a cycle would
  hang a tree walk rather than fail it.
- **`authority:`** may cross-link `data/authorities.json`. Resolving a `<bibl>`
  to that key is still deferred; `BIBL_IDENTITY_ATTRS` is untouched.
- No `canonical:` field — the heading carries it, so there is one place for it.

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

`harness edition serve` (port 8734), on the `webui` shell like the other
editors. Committed `tei/` only: `mz/tei/` is a draft nobody has read, and an
end-user preview is the last place it belongs.

**Two columns.** The text, and a **stack** of cards beside it. Clicking an
entity link, a footnote marker or "consult the scan" pushes a card to the top;
the stack keeps what you opened, in the order you opened it, and a pinned card
stays above the rest. That is the whole interaction, and it is what makes an
annotated edition readable — the alternative is a tooltip that vanishes, or a
footnote that costs you your place. Pins persist per page in `localStorage`,
because a pin is a deliberate act and losing it to a refresh teaches you not to
bother.

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

## The geography view is a sprint of its own

Deferred deliberately, not forgotten. Entity files already carry `geo:` and
`within:`; what is missing is the design, and it is more than a map. The shape
wanted is a **hierarchy of locations** — russian far east → chukotka → chukchi
peninsula → uelen, and anadyr basin → markova, and kamchatka → paren — where each
location appears in its parent's map and the selected chain is navigable as a
tree. There is dumped GeoJSON for watersheds and language regions in `scratch/`
to build it from. No external tiles, ever: the server is loopback and the edition
is meant to be self-contained.

`within:` is the field that will carry it, which is why `entity check` already
refuses a dangling parent and a cycle — the store can be populated correctly
before anything reads it that way.
