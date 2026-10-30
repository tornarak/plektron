---
name: curate-entities
description: Write or amend an entity — whether a thing earns an entry and in which class, its alias rows and their modes, and its gloss. Use before `entity new`, `entity alias`, or any edit under edition/entities/, or on /curate-entities. Not the link rule or the card — that is docs/edition.md.
---

**Cite a page with its book: `chukchi-1-044`, never a bare `1-044`.** The store is shared across a workspace, and `entity check` refuses a bare ref.

# Curate entities

**This is the entry contract.** The file format, the rule that links a form, and the
card that renders one are `docs/edition.md`'s; what follows is the judgement that
document does not make: what earns an entry, which class, which alias mode, and what a
gloss is for. The reader is the client throughout. Every rule below is the guard
against one way an entry goes wrong, and each has gone wrong at least once.

# 1. What earns an entry, and where

**A name that does double duty gets an entry per class**, not one entry stretched over
both: `river:anadyr`, `place:anadyr`, `water:anadyr-bay`, `land:chukotka`. The page
decides which a given sentence means.

**Geography has four classes and the cut is by shape, not by importance.** `place:` a
point on the ground — a village, a camp, a cape, a single peak. `land:` a terrestrial
*region* — a peninsula, a range, an upland, an island, a district. `river:` a
watercourse and the basin it drains. `water:` a body of standing or open water — a
sea, a bay, a strait, a lake. Picking the wrong one is a rename later
(`entity rename`), not a re-reading of the page.

**`taxon:` — the binomial is the entry; the book's own word rides on it as an alias.**
`taxon:gulo-gulo` is the entry and *wolverene* is the alias, because *wolverene* is what
chukchi-1-252 prints and *Gulo gulo* is what the animal is. The identification is a judgement
and lands at `status: proposed` like every other.

- **Where the vernacular maps to no modern taxon it is an alias, never an entry.**
  *Eagle* is polyphyletic within Accipitridae, *mice* is paraphyletic, *seaweed* spans
  three lineages sharing no clade — so the form goes on the coarsest rank that is honest
  (`taxon:aves`, `taxon:mammalia`, `taxon:algae`) and the gloss says the English word
  names no clade. `taxon:pisces` and `taxon:lichenes` are the precedent: folk buckets.
- **Where the referent is undetermined the entry stops at the genus.** chukchi-1-252's "black
  bear" cannot be a black bear — none inhabits Chukotka — so the entry is `taxon:ursus`
  and the gloss says why, rather than asserting *U. arctos* on an inference about the
  fauna. Same for *fox* and *sweet-brier*. `taxon:oedemagena-tarandi` is the model: it
  refuses outright to reconcile the print against modern usage.
- **`animal:` is not the vernacular class.** Its name-type is `zoonym`, *an individual
  animal's name* — the reindeer a herder calls by name (chukchi-1-101). A common noun linked to
  it would emit `<name type="zoonym">` around a common noun, which `validate.py` forbids;
  `taxon:` has no name-type and links through `<rs>`. Folk groups go to `taxon:`.
- **A binomial the book never prints gets no alias row.** An alias asserts that the
  corpus prints a form; a row for a string appearing nowhere is a claim about the book
  rather than a handle on it. It is why the ranks above genus mostly have an empty table.
- **A rank above species earns an entry** only where it groups two or more entries the
  store holds, or the book names the group itself. `taxon:animalia`'s gloss works the
  case list. **A genus with one species is the same case**: a genus printed only inside
  its binomial (`Anser albifrons`, `Strix nyctea`) is not a grouping the book gives, and
  the species hangs from the family or the kingdom directly. What keeps a one-species
  genus is the book printing the genus as a group of its own — `Gadi` ("various species
  of Gadi", chukchi-1-191) — or a vernacular that names the genus and not the species: *poplar*
  is `taxon:populus` and *aspen* its one species; *toadstools* is `taxon:fungi` and
  fly-agaric its one entry.

**A `person:` entry is earned by the book narrating the man, not by the book citing
him.** Travelled, collected, held office, conversed → `person:`; says, mentions, figures,
describes, or governs a page locator → `source:`. `Wrangell, p. 338` is the book; `In
conversation with Wrangell` (chukchi-1-036) is the man. An author the book only ever quotes has
no person entry.

# 2. Alias modes, chosen mechanically

The `auto` column has three values and each is a ruling about the *form*, never about
how much the entity matters. Decide in this order:

| mode | when | examples |
|---|---|---|
| `yes` | the corpus uses the form for this entity and nothing else. **Every hapax legomenon and every binomial is `yes`** | `Gulo gulo`, `Uweˊlen`, `carrion-flies` |
| `once` | a generic, oft-set term with one referent in the store; links the first occurrence per page and leaves the rest bare | *reindeer*, *fungus*, *seaweed*, *moss* |
| `no` | **genuine ambiguity only**: the form names two entities and only the sentence decides. It costs a `<!-- entity candidate -->` a collator must dispose of on every page; spend it where no rule can decide, never as a default | *black bear* on `taxon:ursus`; a bare surname a `person:` and a `source:` both claim |

**Prefer the parent to a conflict.** Where a hierarchy exists — `part-of:` in `taxon:`,
`within:` in geography — a form that covers several entries goes on the *parent* as
`yes` or `once`, and the parent's gloss names the children and the distinction.
*reindeer-fly* names either of chukchi-1-108's two flies and the page does not say which: it
sits on `taxon:diptera`, whence both are one click away. Do not alias it to both species
and kick the can to the collator — two claimants is `entity check`'s error, not a way to
defer. Where there is no common parent (`person:maydell` / `source:maydell`), `no` is
the honest mode, and `docs/edition.md` §"The siglum is a name" rules that case.

**The form is what the page sets**, NFD, never a lexicon handle key; `lang` is the
shortest BCP-47 code or blank for unstated, and a guess is worse than a blank
(`docs/edition.md` §"An alias says what language it is a name in").

# 3. The gloss

**A gloss disambiguates; the mentions explain.** The card lists every passage the entity
occurs in, with the prose either side, out of the corpus itself. So a gloss that
summarises what Bogoras says is about to be outdone by Bogoras, on the same card, with a
page number. What belongs in it is what the passages cannot give:

- which of two entities this is (`people:eskimo`: three groups stand behind one word,
  and which one usually)
- what the book's term covers that the modern one does not (`taxon:lichenes`: seven
  Chukchee kinds, two with a Latin name)
- why an identification was made, or refused (`taxon:ursus`: genus only, and why)
- what the entry deliberately does *not* claim

**`(unwritten)` beats a précis.** `entity new` leaves the gloss unwritten and that is a
fine state to leave it in.

**Reader-facing only.** No provenance history ("it had no entry until"), no seeding
story, no `entity check`, `auto_forms` or any harness mechanism, no rationale for a
ruling the reader never sees. The one exception is a **fact of filing a reader would
trip on**: `taxon:lichenes` standing parentless between two centuries of botany, a
genus entry where the reader expected a species. Say the fact and what it means for
navigating; not how it came to be decided.

The anti-pattern, as it stood on `taxon:rangifer-tarandus`:

> The animal the book is largely about — the herds of chapter IV, the meat that opens
> chapter VIII … **It had no entry until now, and the reason is worth keeping.** The
> corpus never prints `Rangifer` … The store was seeded from the binomials the book
> sets … A store built from what a text spells will always be blindest to what that
> text takes for granted.

Every sentence is either the mentions block or the project's diary. What survives:

> Wild and domesticated reindeer are one species; the book treats them as two
> conditions of it, and nothing here splits them. The binomial is never printed — the
> book says *reindeer* and no more.

**`[[class:slug]]` must resolve** — `entity check` refuses a dangling one. A
`<!-- entity note: … -->` on a page is not a gloss: it is a report for the coordinator.

# 4. Before writing

1. `uv run harness entity list` — does it already exist, under another slug or class?
2. Choose the class by §1, the mode of every alias by §2.
3. Write the gloss, then reread it against §3: strike every sentence the card will say
   better, and every sentence about the project rather than the thing.
4. `uv run harness entity check` exits 0.
