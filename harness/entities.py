"""The entity store — the encyclopedia, one markdown file per entity.

**An identity is `class:slug`, always.** `person:jochelson` and
`source:jochelson` are two entities: the man and the book he wrote are cited on
the same page by the same string, and an identity scheme that cannot hold them
apart would resolve one to the other silently. The class is not decoration on
the slug; it is half the name.

It lives twice, and that is deliberate. On disk the class is the directory
(`entities/person/jochelson.md`), because a colon in a filename is a
portability trap; inside the file it is the first half of the `#` heading. The
ground-truth loss happened because a file's role lived *only* in its directory
name, so nothing could tell an export shell from a hand-keyed page once the
directory was gone. Here the file says what it is, `check` compares the two, and
a moved file is an error rather than a reclassification.

**What the store is for.** It is the referent of every `@ref` in the corpus,
and the source of the alias vocabulary that the generator applies by rule. It
is human-authored: a model may propose an entry in its report and the
coordinator runs `entity new`, but nothing mints one unreviewed — the same
remit that keeps a model from originating a glyph.

**The aliases are the mechanical half, and their firewall is structural.** An
alias table says "this form, in this book, means this entity", which is a
judgement a human makes once with the corpus in view. Applying it is a rule.
The bar for applying it *without* asking is deliberately high and mechanical,
not disciplinary — see `auto_forms`: a form two entities claim is ambiguous by
construction, whatever either file says about it, and no amount of care by the
author of one of them can make it unambiguous.

**An alias carries the language it is a name in**, from `langs.ALIAS_LANGS`.
Seven entries used to write `lang:ckt` and `lang:rus` into the *note* column,
where the fact was real, unreadable and uncheckable — an entity's Russian and
Chukchi names are exactly what a reader of an ethnography wants and exactly what
no free-text column can be asked for. It is optional, because requiring it would
make an editorial pass out of a schema change; blank means **unstated**, which
`check` counts as a worklist and never gates on. A code outside the vocabulary
*is* an error: that is a typo, not a gap.

The column deliberately buys nothing mechanical yet. In particular it does
**not** narrow `detectors.entity_forms` — an alias suppresses `lexicon_miss`
whatever language it is in, exactly as before — so the one case no mechanical
test separates, an unmarked romanized native form, is still suppressed and still
open. The field records the fact; nothing infers from it.

**There is no `since:`.** The store carried one — the page whose reading
prompted the entry — required on the argument that an apparatus store which
cannot be traced back to a page is unauditable. That argument was right and its
answer is now better: the card derives *every* page the entity is mentioned on,
from the corpus, on every load. **A `since:` is satisfied by typing a plausible
ref; an empty mentions list is not**, so the field was the weaker witness of the
two, and requiring it kept out entries the book plainly contains whose attesting
page happens to be among the 558 not yet transcribed. `entity occurrences --all`
is where an unwitnessed entry shows up now, as a row reading 0 and 0.

**This store is also the corpus's proper-noun dictionary**, and the direction of
that is worth being exact about. `data/lexicon_extra.txt` suppresses
`lexicon_miss` and nothing else because it *structurally cannot* reach anything
else; the entity store can, so `detectors.entity_forms` reads only the one thing
out of it that a spellcheck can use — the components of every canonical and
alias form — and `lexicon_miss` tests only ASCII components of length > 3, so
a native alias in an alias table is inert there by construction. The proper
nouns that used to be listed in both files now live here alone, one entry each,
each naming the page that first attested it.

**One matcher, three callers.** `harness tei generate` links what clears the
bar, `harness tei context` shows the reviewer every hit including the ones that
did not, and `harness tei validate` re-derives each `#mz` link on every run.
Three implementations of one rule would be three witnesses that are one, and
they would drift in the direction that hides the drift.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .geo import index as geo_index
from .langs import ALIAS_LANGS

ENTDIR = "entities"

#: The classes an entity may have, mapped to the `<name @type>` each corresponds
#: to — or to None where the class has no name-type at all.
#:
#: The vocabulary is its own, deliberately, rather than reusing `NAME_TYPES`
#: verbatim: a class is written into every `@ref` in the corpus, so it wants
#: `person:`, not `anthroponym:`. The mapping is what holds the two together, and
#: `tei validate` uses it to refuse a `<name type="toponym" ref="event:…">`.
#:
#: The four with no name-type are the reason `<rs>` exists here. `NAME_TYPES` is
#: scoped to what a reader of a page can see and record — it excludes `taxon`
#: outright ("the binomials are Latin in English prose and out of scope") and has
#: no member for an institution or a work. Those are exactly the entities
#: an alias table can find reliably, and linking them says "this string refers to
#: that entity", not "the page marked a proper noun here".
#:
#: **`sky:` is stars, constellations and the Milky Way**, and it has no
#: name-type on purpose. Bogoras names some fourteen of them, each with a
#: Chukchee name beside the classical one, and narrates several as persons — the
#: Sun is a man, and `being:` would be the obvious home if the class did not
#: then assert `mythonym` on every `<name @ref>` pointing at it. It would be
#: wrong wherever the page means the star: "Orion" in a sentence about when to
#: expect the frost is an asterism and nothing else, and only the sentence says
#: which. So the class says where the thing is and declines to say what a page
#: meant by it, which is what `<rs>` is for and what the four None classes have
#: in common. Not a `GEO_CLASS`: a `within:` chain is about the earth, and the
#: atlas draws nothing here.
#:
#: **There is no `language:`.** There was, and it earned nothing: nine of its ten
#: entries claimed the very polygon their `people:` counterpart already claimed,
#: nine of ten glosses were unwritten, and nothing in the code path that matters
#: consulted it — `langs.py` is the language table that binds `xml:lang` and the
#: lexicon index, and it names its witnesses as a `people:` entry, a `langarea:`
#: shape or an authority's `lang`. What it did do was make "Chukchee" ambiguous
#: by construction, which cost 423 candidate comments, a third of the whole
#: collation inbox, over a distinction this book does not draw: every language in
#: it is its people's. The lexicon is the language's encyclopedia here.
#:
#: **Four geographical classes, not two, and the cut is by what a map draws.**
#: `place:` used to hold a village and a peninsula alike and `water:` a river and
#: an ocean, which made the class useless for the two things a class is for: an
#: atlas that shows a settlement, a land region, a drainage and a body of open
#: water in one hue is a field of overlapping outlines, and a `within:` chain
#: that cannot tell a point from a region cannot say that a town inside a bay is
#: an error. So: `place:` a terrestrial **point**, `land:` a terrestrial
#: **region**, `river:` a watercourse and the basin it drains, `water:` a body of
#: standing or open water. `geo`'s four shape kinds — `region`, `watershed`,
#: `marine`, and a bare `geo:` point — are what each one is drawn from, so the
#: class and the shape are one fact stated once.
#:
#: **`land:` and `river:` carry the same `@type` as the class they split from**,
#: which is not a convenience: a page's `<name type="toponym">` records that a
#: reader saw a place-name, and whether that name denotes a point or a region is
#: the store's business and never the page's. That equality is exactly what
#: licenses `entity rename` to move an entry between them (`cli/_entity.py`)
#: while it still refuses `place:` → `water:`, which would contradict the page.
ENTITY_CLASSES = {
    "person": "anthroponym",
    "people": "ethnonym",
    "place": "toponym",
    "land": "toponym",
    "water": "hydronym",
    "river": "hydronym",
    "animal": "zoonym",
    "being": "mythonym",
    "event": "event",
    "sky": None,
    "taxon": None,
    "institution": None,
    "source": None,
}

#: The classes that name somewhere on the earth, and so the ones a `within:`
#: chain is *about*. Named here rather than inferred from `ENTITY_CLASSES`'
#: values, which are onomastic categories and split `place`/`land` from
#: `water`/`river` on a distinction — toponym against hydronym — that has
#: nothing to do with whether a thing can contain another.
GEO_CLASSES = ("place", "land", "water", "river")

#: The alias column's three values → how widely a rule may apply the form.
#:
#: **`once` is what most of the store's ethnonyms want and neither of the other
#: two gives them.** `Chukchee` is not doubtful — it means one people wherever
#: the book sets it — but it is set some five thousand times, and a link on
#: every instance is a page the reader cannot see the prose through. Marking it
#: `no` to keep the text readable made the store say the opposite of what its
#: author meant, and cost 423 candidate comments, a third of the whole
#: collation inbox, asking a reader to re-decide a question nobody had.
#:
#: The reader's convention answers it: link the **first occurrence on the page**
#: and leave the rest bare. That is mechanical, so it stays `#mz` and
#: re-derives; the page is the unit because the page is what a reader has in
#: front of them, and because it is the unit `generate` already works in.
#:
#: **Once per *form*, not per entity**, which is worth stating because the name
#: reads the other way. The alias table is keyed on forms and `once` is a
#: property of a row, so a page setting both `Chukchee` and `Chukchee tribe`
#: links each. Measured: 204 pages take one link, four take two, and one takes
#: seven — `1-031`, where Bogoras enumerates the people's names in five
#: languages and every one of them is exactly the form a reader would follow.
#: Per entity would also make a row's meaning depend on its neighbours, a `once`
#: form then competing with some other row's `yes`.
#:
#: `auto` stays the boolean "a rule may link this at all" — true for `yes` and
#: `once` alike — and the scope is a second key, because eight call sites test
#: `claim["auto"]` for truthiness and a tri-valued string would make `"no"`
#: true in all eight at once, silently.
AUTO_VALUES = {"yes": "all", "once": "first", "no": ""}

#: `proposed` is what `entity new` writes and what a browser audit clears.
#: Only a human moves an entry to `ratified`, and only a ratified entry may be
#: linked by rule — a machine link resting on an unaudited entry would be the
#: pass promoting its own proposal, one artifact removed.
STATUSES = ("proposed", "ratified")

#: The section an entity's alias table lives under. Named as a constant because
#: the parser refuses the *old* spelling by name, and the two must not drift.
ALIASES = "aliases"

#: How one entry names another, in a gloss or an alias note. Brackets rather
#: than a bare `class:slug`, so a reference is distinguishable from prose that
#: merely mentions the shape of one, and so `check` can refuse a dangling target.
WIKILINK = re.compile(r"\[\[([a-z]+:[a-z0-9][a-z0-9-]*)\]\]")

_HDR = re.compile(r"^#\s+([a-z]+):([a-z0-9][a-z0-9-]*)\s+—\s+(.+?)\s*$", re.M)
#: `[a-z-]`, not `[a-z]`: `part-of:` is the first field with a hyphen in its
#: name, and under the old pattern its line simply did not match — so the field
#: was **silently discarded**, the record carried an empty value, and every gate
#: passed. A store whose parser drops what it does not recognise is the shape
#: this repository has already been hurt by once.
_FIELD = re.compile(r"^-\s+([a-z][a-z-]*):\s*(.*?)\s*$", re.M)

#: Every key `parse` reads. Held as a set so an unrecognised one can be refused
#: rather than ignored — the second half of the fix above, and the half that
#: makes the first unnecessary next time. A typo'd `- withn:` used to parse
#: cleanly into nothing.
KNOWN_FIELDS = frozenset({
    "status", "within", "part-of", "geo", "frame", "link", "authority",
})

#: Fields this store used to have. **Tolerated and inert**, never an error: a
#: `since:` left in a file carries nothing and renders nowhere, and refusing it
#: would turn removing a field into a migration of every record that ever had
#: one. Named here rather than passed over silently, so the difference between
#: "we dropped this" and "you typed it wrong" is written down.
#:
#: `area:` named a shape while `geo:` held a point, and the two answered one
#: question — which is why `parse` used to refuse a record carrying both. It is
#: a `geo:` member now. Inert rather than refused for the reason above, and the
#: reason has teeth here: 66 records carried one, `tools/migrate_geo_field.py`
#: rewrote every one, and a copy of this store from before that run should read
#: as out of date rather than as broken.
RETIRED_FIELDS = frozenset({"since", "area"})
_SECTION = re.compile(r"^##\s+(\S+)\s*$", re.M)
_ROW = re.compile(r"^\|(.*)\|\s*$", re.M)
#: An alias boundary. `\w` alone is not enough on NFD text: a combining mark is
#: not a word character to Python, so `\bJesup\b` would happily match the first
#: five characters of a Tier-1 form whose sixth is a combining diaeresis.
#: Spelled with `chr()` rather than as literal characters: a combining mark
#: written next to a `w` in this file's own source composes with it under the
#: NFD/NFC round trip an editor may apply, and `[\ẁ-ͯ]` is a silently invalid
#: range rather than a syntax error at import.
_MARKS = "\\w" + chr(0x300) + "-" + chr(0x36F)

#: The footnote sort, which `\w` matches and which is **not part of the word in
#: front of it**. `keying_spec.md` §2.10 settles this corpus-wide: a marker is
#: always the Unicode superscript and a superscript digit is never anything else,
#: so no reading is being made here — the spec already made it.
#:
#: **The failure it fixes was silent in both directions.** `Ciˊṛluk⁶` on 1-051
#: put the alias in front of a marker, `\w` matched the marker, the right
#: boundary failed, and `match` returned no hit — so the generator neither linked
#: the form nor raised it as a candidate, and nothing anywhere said a name had
#: been passed over. Measured over the keyed corpus: 69 lines set a word against
#: a marker, and about twenty of those words are entity forms — `Nelson` six
#: times, `Nordenskiöld` and `Schrenck` twice each, `Kiˊhi`, `Karbaschan`,
#: `Shoudon`, `Хатырка`. A footnote is what an author hangs on the names that
#: needed a source, which is why this lands on exactly the wrong words.
#:
#: Right side only. A marker sits after its reference, and at the opener it is
#: followed by a space (§2.10), so nothing is gained by widening the left
#: boundary and a lookbehind holding a lookbehind is worth avoiding.
_SUP = "²³¹⁰⁴⁵⁶⁷⁸⁹"
_BEFORE = f"(?<![{_MARKS}])"
_AFTER = f"(?!(?![{_SUP}])[{_MARKS}])"


class Malformed(Exception):
    """A file the parser will not guess at. The message names the file and the line."""


def ent_dir(root: Path = Path(".")) -> Path:
    return root / ENTDIR


def split_id(ent_id: str) -> tuple[str, str]:
    """`"person:bogoras"` → `("person", "bogoras")`. Raises on anything else.

    Every caller that accepts an identity from outside — a CLI argument, a
    `@ref`, a `within:` field — goes through here, so "what is a well-formed
    identity" has one answer and the error message is the same wherever it is
    wrong.
    """
    cls, sep, slug = ent_id.partition(":")
    if not sep or not cls or not slug:
        raise ValueError(
            f"{ent_id!r}: an identity is `class:slug` — `person:bogoras`, not a "
            f"bare slug. The class is half the name, not a prefix on it")
    if cls not in ENTITY_CLASSES:
        raise ValueError(
            f"{ent_id!r}: unknown class {cls!r}. One of: "
            f"{', '.join(sorted(ENTITY_CLASSES))}")
    return cls, slug


def path_for(ent_id: str, root: Path = Path(".")) -> Path:
    cls, slug = split_id(ent_id)
    return ent_dir(root) / cls / f"{slug}.md"


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _geo_member(raw: str, at: str = "") -> dict:
    """One `- geo:` line → a typed member. Raises `Malformed` on anything else.

    Three forms, told apart by the line's own spelling and by nothing else:

        - geo: 64.4051 -172.2409          a point
        - geo: langarea:chuk1273          a shape in `data/geo/`
        - geo: place:naukan               another entity, extent transcluded

    **The disjointness of shape kinds from `ENTITY_CLASSES` is what makes this
    decidable**, and that invariant is older than this field: a shape kind is
    `langarea:` and never any live entity class, held apart on purpose so that
    an entity file carrying two ids two lines from each other cannot be misread. It used
    to be enforced negatively — an `area:` naming an entity class was refused
    outright, because it *looked* like a reference — and here the same fact is
    read positively: it *is* one. `geo bounds` has told the two apart by prefix
    alone since it was written, with no flag and no wrong guess available to it,
    and this is the same rule doing the same work one store lower down.

    Typed here rather than left as a string because `parse` is the one place
    that raises `Malformed`. A member whose floats are re-parsed at each of
    forty call sites is a member whose error message depends on who read it.
    """
    parts = raw.split()
    if len(parts) == 2:
        try:
            return {"kind": "point", "lat": float(parts[0]), "lon": float(parts[1])}
        except ValueError:
            raise Malformed(
                f"{at}`geo: {raw}` — two tokens, so this reads as a coordinate, "
                f"but they are not two WGS84 decimal degrees, latitude then "
                f"longitude. A shape or an entity is one token, `kind:slug`"
            ) from None
    kind, sep, name = raw.partition(":")
    if sep and kind and name and len(parts) == 1:
        if kind in ENTITY_CLASSES:
            split_id(raw)     # raises with the same message as everywhere else
            return {"kind": "entity", "id": raw}
        return {"kind": "shape", "id": raw}
    raise Malformed(
        f"{at}`geo: {raw}` — a member is one of three things: a point, as two "
        f"decimal degrees `64.4051 -172.2409`; a shape in `data/geo/`, as "
        f"`kind:slug` (`harness geo list` names them); or another entity, as "
        f"`class:slug`, whose extent this one takes. Repeat the field for "
        f"several; the field is the union of its members")


#: The three readings of `geo:`, each as a list. **Accessors and not record
#: keys**: a key restating a field is an invisible field, which is the rule
#: `property_rows` exists to keep, so the record holds the members once and
#: every caller asks for the reading it wants.
#:
#: They live here rather than in `geo.py` because classification needs
#: `ENTITY_CLASSES`, and because `entities` imports `geo` at module top while
#: `geo` imports `entities` lazily inside functions — a classifier over there
#: would invert that. `geo.py` re-exports all four, as it re-exports `children`,
#: for the reason written there: the atlas is the heaviest caller and should not
#: have to import the encyclopedia to read a field.
def geo_points(rec: dict) -> list[tuple[float, float]]:
    """Every point member, as `(lat, lon)` — the spelling `geo:` always had."""
    return [(m["lat"], m["lon"]) for m in rec["geo"] if m["kind"] == "point"]


def geo_shapes(rec: dict) -> list[str]:
    """Every shape member, as a `data/geo/` id."""
    return [m["id"] for m in rec["geo"] if m["kind"] == "shape"]


def geo_refs(rec: dict) -> list[str]:
    """Every entity member, as an identity. What `extent_of` transcludes."""
    return [m["id"] for m in rec["geo"] if m["kind"] == "entity"]


def spell_geo(rec: dict) -> list[str]:
    """The members back as authored, one string per line the file holds.

    For anything that reports the field rather than resolving it — the CLI's
    "was" column, a migration's diff — so that no caller has to know how a point
    is spelled in order to print one.
    """
    return [f"{m['lat']} {m['lon']}" if m["kind"] == "point" else m["id"]
            for m in rec["geo"]]


def parse(text: str, where: str = "") -> dict:
    """One entity file's text → its record. Raises `Malformed` on anything unclear.

    NFD on read, as `figures.readings` does and for the same reason: the file is
    hand-maintained, it can drift between edits, and an alias's normal form must
    not depend on which session keyed it. An alias that fails to match because
    the store holds a precomposed `ö` and the page holds a decomposed one is a
    silent miss, which is the failure class this project is organised against.
    """
    text = unicodedata.normalize("NFD", text)
    at = f"{where}: " if where else ""
    m = _HDR.search(text)
    if not m:
        raise Malformed(
            f"{at}no heading. The first line is `# class:slug — Canonical Name`, "
            f"and it is where the identity and the display name live")
    cls, slug, canonical = m.group(1), m.group(2), m.group(3)
    if cls not in ENTITY_CLASSES:
        raise Malformed(f"{at}unknown class {cls!r} in the heading. One of: "
                        f"{', '.join(sorted(ENTITY_CLASSES))}")

    # Fields are the lines above the first `##`; a `- foo: bar` inside the gloss
    # is prose, not a field.
    first = _SECTION.search(text)
    head = text[:first.start()] if first else text
    fields: dict[str, list[str]] = {}
    for f in _FIELD.finditer(head):
        fields.setdefault(f.group(1), []).append(f.group(2))

    unknown = sorted(set(fields) - KNOWN_FIELDS - RETIRED_FIELDS)
    if unknown:
        raise Malformed(
            f"{at}unknown field{'s' if len(unknown) > 1 else ''} "
            f"{', '.join(f'`{u}:`' for u in unknown)} — "
            f"one of {', '.join(sorted(KNOWN_FIELDS))}. A field this store does "
            f"not read is a fact nothing carries, and it used to pass quietly")

    def one(key: str) -> str:
        v = fields.get(key, [])
        if len(v) > 1:
            raise Malformed(f"{at}`{key}:` given {len(v)} times; it takes one value")
        return v[0] if v else ""

    status = one("status")
    if status not in STATUSES:
        raise Malformed(f"{at}status {status!r} — one of {', '.join(STATUSES)}")
    within = one("within")
    if within:
        split_id(within)          # raises with the same message as everywhere else

    # `part-of:` is **where `within:` is not**, and the split is the whole point
    # of having two fields. `within:` says where a thing *is* and is what the
    # atlas walks; this says what it *belongs to* and is read by nobody drawing
    # a map. One field carried both until the Naukans made the conflation
    # visible: they are a Yupik people who lived in one village, so `within:
    # people:yupik` inherited the entire Central-plus-Pacific Yupik language
    # area for a single settlement, and moving them to `within: place:naukan`
    # bought the extent by dropping the fact that they are Yupik at all.
    # Neither answer was wrong about its own half, which is the tell that the
    # question was two questions.
    #
    # Same shape as the `geo:`/`area:` rule one section down, inverted: there,
    # two fields said one thing and the second could only drift; here, one field
    # said two things and no reader could tell which it meant.
    part_of = one("part-of")
    if part_of:
        split_id(part_of)

    sections: dict[str, str] = {}
    marks = list(_SECTION.finditer(text))
    for i, s in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        sections[s.group(1)] = text[s.end():end].strip("\n")

    if "triggers" in sections and ALIASES not in sections:
        raise Malformed(
            f"{at}`## triggers` is now `## aliases`, and the table has gained a "
            f"`lang` column between `form` and `auto`: "
            f"`| form | lang | auto | note |`. Leave `lang` blank where the "
            f"language is unstated; a code goes in the column and never in the "
            f"note")

    aliases = []
    seen = set()
    for row in _ROW.finditer(sections.get(ALIASES, "")):
        cells = _cells(row.group(1))
        if len(cells) < 3 or set("".join(cells)) <= set("-: "):
            continue              # the header rule, or the header row's own labels
        if cells[0].lower() == "form":
            continue
        form = " ".join(cells[0].split())
        if not form:
            raise Malformed(f"{at}an alias row with an empty form")
        if form in seen:
            raise Malformed(f"{at}alias {form!r} listed twice in one file")
        seen.add(form)
        # Blank is unstated, which is a claim the store is allowed to make. A
        # code that is not in the vocabulary is a typo, and the message names
        # what is on offer rather than leaving the author to find the table.
        lang = cells[1].strip()
        if lang and lang not in ALIAS_LANGS:
            raise Malformed(
                f"{at}alias {form!r}: unknown language {lang!r}. One of: "
                f"{', '.join(sorted(ALIAS_LANGS))} — or blank, which says the "
                f"language is unstated. Codes are the shortest BCP-47 form, the "
                f"same string a collator writes in `xml:lang`, so it is `ru` "
                f"and never `rus`")
        auto = cells[2].lower()
        if auto not in AUTO_VALUES:
            raise Malformed(
                f"{at}alias {form!r}: `auto` is `yes`, `once` or `no` (got "
                f"{auto!r}). It is the author's declaration that the form is "
                f"safe out of context, so there is no default for it")
        aliases.append({"form": form, "lang": lang, "auto": auto != "no",
                        "scope": AUTO_VALUES[auto],
                        "note": cells[3] if len(cells) > 3 else ""})

    # **One location field, repeatable, and the field is the union of its
    # members.** It held exactly one point until it absorbed `area:`, and the
    # two had been one question with two spellings for as long as both existed —
    # which is why `parse` used to carry a rule refusing a record that answered
    # it twice. A field that needs a rule against contradicting itself is a
    # field that should not have been two.
    #
    # Deliberately **not** put through `one()`: several members is the ordinary
    # case now, not a defect.
    geo = [_geo_member(raw, at) for raw in fields.get("geo", [])]

    # **A frame is not an extent.** It says where the map should *look*, which is
    # a different question from where the entity *is*, and the default answer is
    # wrong at both ends of the store. A container with no shape takes the union
    # of everything beneath it: `place:russian-far-east` reached 103°E and 41.7°N
    # on the strength of the Lena and the Amur, two rivers named ten times
    # between them — a quarter of the northern hemisphere, curving round the
    # pole, with Alaska in shot. A *shape* frames on its parent, which is what
    # makes it mean something; but `place:chukchi-peninsula` is dense with
    # villages and Chukotka's box packs them into a corner.
    #
    # So it overrides whichever frame would have been derived, and nothing else:
    # `extent_of` is untouched, so an entity that contains this one still sizes
    # itself on the real geometry, and `member_shapes` still draws everything
    # beneath. Where to look, not what is there.
    #
    # West south east north, the order `index.json`'s `window` is written in and
    # the order `geo.extent_of` returns — a frame is a box, and `geo:`'s
    # latitude-first order is for a point. East may exceed 180: the atlas's frame
    # is continuous across the antimeridian and the Chukchi Peninsula sits at 190.
    frame = one("frame")
    box = None
    if frame:
        parts = frame.split()
        try:
            if len(parts) != 4:
                raise ValueError
            box = tuple(float(p) for p in parts)
        except ValueError:
            raise Malformed(
                f"{at}`frame: {frame}` — four WGS84 decimal degrees, west south "
                f"east north, space-separated. A box, so longitude comes first, "
                f"unlike `geo:`") from None
        if box[0] >= box[2] or box[1] >= box[3]:
            raise Malformed(
                f"{at}`frame: {frame}` — west must be less than east and south "
                f"less than north. East may exceed 180 in the atlas's continuous "
                f"frame; west may not wrap past it")

    # **The rule against a record answering "where is it" twice is gone**, and
    # it is gone because the question now has one field. It read: `geo:` and
    # `area:` are mutually exclusive and the shape wins, since `extent_of` would
    # read the shape and never look at a point beside it, so the point was
    # unreachable by construction and could only be a second, weaker statement
    # of the same fact that nothing kept in step.
    #
    # Every word of that was true of *two* fields. With one, a point beside a
    # shape is not a contradiction to adjudicate but two members of a union, and
    # `extent_of` reads both. What the old rule was protecting — that a record
    # says where one thing is, once — is now protected by there being one field
    # to say it in.
    return {
        "id": f"{cls}:{slug}",
        "class": cls,
        "slug": slug,
        "canonical": canonical,
        "status": status,
        "within": within,
        "part_of": part_of,
        "geo": geo,
        "frame": box,
        "links": fields.get("link", []),
        "authority": one("authority"),
        "aliases": aliases,
        "gloss": sections.get("gloss", "").strip(),
    }


def load(root: Path = Path(".")) -> dict[str, dict]:
    """The whole store, keyed by identity. Absence is `{}`, not an exception.

    Each record carries `dir_class` — the directory it was found in — so `check`
    can compare it against the class the file claims. Everything else reads
    `class`, which is the file's own word.
    """
    out: dict[str, dict] = {}
    d = ent_dir(root)
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*/*.md")):
        rec = parse(p.read_text(encoding="utf-8"), where=str(p))
        rec["dir_class"] = p.parent.name
        rec["stem"] = p.stem
        rec["path"] = str(p)
        out[rec["id"]] = rec
    return out


def tree_parent(rec: dict) -> str:
    """Where this entity hangs: `within:` if it has one, else `part-of:`.

    **One function because three callers must agree exactly** — `children`,
    `geo.extent_of` and the card's *inherited* row — and a tree that disagreed
    with the extent would draw a node in one place and frame it on another.

    The fallback is scoped to `people:` and that scope is the whole of its
    honesty. A subgroup of an ethnicity lives inside that ethnicity's area by
    what the word means, so its parent's box is a true bound on it even where
    nobody has drawn the child; the Reindeer and Maritime Chukchi, the Kavraˊlɪt
    and the Chuvans have no shape and no village and would otherwise be absent
    from an atlas largely about them. Nothing else inherits: a `source:` that is
    `part-of:` a larger work is not *somewhere* because of it, and letting that
    edge into the tree would put a bibliography on the map.
    """
    if rec["within"]:
        return rec["within"]
    return rec["part_of"] if rec["class"] == "people" else ""


def kin_parent(rec: dict, store: dict) -> str:
    """The parent of this entity **within its own class** — `part-of:` first.

    The encyclopedia's counterpart to `tree_parent`, and the two must stay
    separate: **there are two hierarchies and collapsing them is what the
    `part-of:` split was for.** The atlas asks where a thing *is*, so it takes
    `within:` first; a class listing asks what a thing *belongs to*, so it takes
    `part-of:` first. `people:naukans` is `within: place:naukan` and `part-of:
    people:yupik` — under the atlas's edge it hangs from a village, which is
    right on a map and leaves `people:yupik` childless on a page about peoples.

    Returns nothing where neither parent is in the same class, which is what
    makes such an entry a top-level row of its own class rather than one the
    page silently drops.
    """
    for cand in (rec["part_of"], rec["within"]):
        if cand and store.get(cand, {}).get("class") == rec["class"]:
            return cand
    return ""


def children(store: dict) -> dict[str, list[str]]:
    """The tree inverted — parent id to the ids directly under it.

    **`within:` is containment in general, and the atlas is one reader of it.**
    This lived in `geo.py` while the tree was the geography's alone, which made
    a caller wanting `people:chuvans` under `people:yukaghir` import the
    geography to get it. It reads no coordinate and no shape — only the field —
    so it belongs beside the field. `geo.children` re-exports it, since the
    atlas is still the heaviest caller and its own reasoning is written there.

    Edges come from `tree_parent`, so a people with no geography of its own
    still hangs from its ethnicity. `within:` alone would have dropped exactly
    the four subgroups the split moved to `part-of:` — off the tree entirely,
    and out of `geo verify`'s worklist with them, which scopes to what the atlas
    can draw. A field split that made four records *less* visible would have
    been a bad trade.
    """
    kids: dict[str, list[str]] = {}
    for rec in store.values():
        up = tree_parent(rec)
        if up:
            kids.setdefault(up, []).append(rec["id"])
    for v in kids.values():
        v.sort()
    return kids


def relatives(ent_id: str, store: dict) -> list[str]:
    """Every ancestor and every descendant, at any depth.

    **Not the same set as what a map draws**, and that is the point of it
    existing. `geo.member_shapes` stops at the nearest descendant *with* a
    shape, so Chukotka is skipped on the Russian Far East's map and the Chukchi
    Peninsula below it never appears at all — yet both are one click from where
    a reader is standing, and both are what the pane exists to make cheap to
    reach.

    Cycle-safe by the same `seen` discipline as `geo.extent_of`: `check` gates
    acyclicity, but this runs inside a page render, where a hang is worse than a
    wrong answer.
    """
    kids = children(store)
    out, seen = [], {ent_id}

    def down(ident: str) -> None:
        for k in kids.get(ident, []):
            if k in seen:
                continue
            seen.add(k)
            out.append(k)
            down(k)

    down(ent_id)
    up = store.get(ent_id, {}).get("within") or ""
    while up and up not in seen:
        seen.add(up)
        out.append(up)
        up = store.get(up, {}).get("within") or ""
    return sorted(out)


def ancestors(ent_id: str, store: dict) -> list[str]:
    """Every entity above this one, **nearest first** and never itself.

    `relatives` returns the same nodes sorted by id, mixed in with the
    descendants, which answers "what is one click away" and not "what contains
    this". The order is the whole of the difference: a map framed on the first
    ancestor that will hold its subjects has to walk outward, and a tree that
    ends at a common ancestor has to know which of two candidates is nearer.

    Cycle-safe by the same `seen` discipline as the rest of this module.
    """
    out: list[str] = []
    seen = {ent_id}
    up = store.get(ent_id, {}).get("within") or ""
    while up and up not in seen:
        seen.add(up)
        out.append(up)
        up = store.get(up, {}).get("within") or ""
    return out


def common_ancestors(idents, store: dict) -> list[str]:
    """What contains every one of `idents`, **strictly and nearest first**.

    Strictly: a selection is never its own frame. Selecting the Kolyma and one
    of its tributaries frames on what holds the Kolyma, not on the Kolyma — the
    same argument the single-subject map has always made, that a shape shown
    alone says what it looks like and a shape shown inside its container says
    where it is.

    Nearest-first over the *first* ident's chain, which is what makes "the first
    common ancestor" a well-defined node rather than a set. An empty selection
    has no container and gets no chain; two selections in unrelated trees get
    none either, and the caller falls back to the box that holds them both.
    """
    idents = list(idents)
    if not idents:
        return []
    chains = [set(ancestors(i, store)) for i in idents]
    return [a for a in ancestors(idents[0], store)
            if all(a in c for c in chains[1:])]


def roots(store: dict) -> list[str]:
    """Every entity with no parent, in id order.

    The tops of the forest, whatever their class. `/atlas` takes this and then
    narrows to the *located* ones, because a map of an unplaceable thing is a
    blank; the encyclopedia takes it whole, because an entry with no coordinate
    still has somewhere it belongs.
    """
    return sorted(i for i, r in store.items() if not r["within"])


def alias_index(store: dict[str, dict]) -> dict[str, list[dict]]:
    """`{form: [{id, lang, auto, scope, status}, …]}` — every claim on every form.

    A form appears once whoever claims it, so a collision is visible here and
    nowhere else: no single entity file can see that another one claims its
    alias.
    """
    idx: dict[str, list[dict]] = {}
    for rec in store.values():
        for t in rec["aliases"]:
            idx.setdefault(t["form"], []).append(
                {"id": rec["id"], "lang": t["lang"], "auto": t["auto"],
                 "scope": t["scope"], "status": rec["status"]})
    return idx


def auto_forms(idx: dict[str, list[dict]]) -> dict[str, str]:
    """The forms a rule may link without asking → the identity each resolves to.

    Three conditions, all mechanical, all checkable from the store alone:

    - **exactly one entity claims the form.** Two claims make it ambiguous *by
      construction* — "Eskimo" is `people:eskimo`, `people:inupiat` and
      `people:yupik`, and only the sentence around it decides which.
      Neither author can fix that from their own file, which is why the rule
      reads the whole store and not the entry.
    - **that claim is not `auto: no`.** The author's declaration that the form
      means this entity wherever it appears. Bare "Jesup" does not qualify even
      though one entity claims it, because the man it is named after is in the
      book too. `yes` and `once` both qualify: they differ in how many of a
      page's occurrences get the link, which is `rule_links`' business and not
      this function's — the identity a form resolves to is the same either way.
    - **the entity is ratified.** A machine link resting on a proposed entry
      would let the store's unaudited half into committed TEI.

    Everything failing any of the three is still surfaced — as a candidate
    comment in the generated page and a row in `tei context` — because a
    suggestion a reader disposes of is the point of the whole arrangement. What
    is refused is the *silent* link.
    """
    out = {}
    for form, claims in idx.items():
        if len(claims) != 1:
            continue
        c = claims[0]
        if c["auto"] and c["status"] == "ratified":
            out[form] = c["id"]
    return out


def _pattern(forms) -> re.Pattern | None:
    """One alternation over every alias form, longest first.

    Longest-first is what makes "Jesup North Pacific Expedition" win over the
    "Jesup" that is inside it — Python's alternation takes the first branch that
    matches, not the longest, so the order *is* the rule.

    Whitespace in a form matches any run of whitespace, so a title broken across
    two printed lines still matches. The generated page keeps the printed line
    breaks, so without this the longest and most reliable aliases — the multi-word
    ones — would be exactly the ones that failed at a line end.

    **A hyphen may stand between any two characters**, because
    `join_broken_words` keeps the compositor's line-break hyphen: `Maritime Chuk-`
    / `chee` rejoins as `Maritime Chuk-chee`, and whether that hyphen belongs to
    the word is not decidable from the ALTO, so nothing removes it. Without the
    tolerance the store cannot see 39 occurrences across the corpus at 13
    entities — a form that is present and invisible, which is the silent miss this
    project is organised against. What it buys is a *question*: `match` marks such
    a hit `hyphenated`, and no rule may link one.
    """
    forms = sorted(forms, key=len, reverse=True)
    if not forms:
        return None
    alts = [r"\s+".join("-?".join(re.escape(c) for c in w) for w in f.split())
            for f in forms]
    return re.compile(_BEFORE + "(?:" + "|".join(alts) + ")" + _AFTER)


def match(text: str, idx: dict[str, list[dict]]) -> list[dict]:
    """Every alias hit in `text`, non-overlapping, longest-first.

    Returns `{start, end, text, form, ids, auto, hyphenated, status}` per hit,
    where `form` is the alias as the store spells it and `text` is what the page
    spells — the two differ wherever a line break fell inside the match. `ids` is
    every entity claiming the form, so a caller can tell an unambiguous hit from a
    contested one without going back to the index.

    **`hyphenated` says the page spells the form with a hyphen the store does
    not**, which is what a compositor's line-break hyphen looks like after
    `join_broken_words` rejoins the two halves. Such a hit is never `auto`, no
    matter how safe the alias: deciding that a hyphen is the printer's and not
    the word's is a reading, and `Rein-deer` being obvious does not make it
    mechanical. It arrives as a candidate, the reader settles it, and the
    generator's comment says which kind of question it is.

    Case-sensitive. These are proper nouns in running prose, and a
    case-insensitive match on a short form would fire on ordinary words.
    """
    text = unicodedata.normalize("NFD", text)
    pat = _pattern(idx)
    if pat is None:
        return []
    # Only consulted when the exact spelling is not in the index, so an alias
    # that legitimately carries a hyphen (`Sredne-Kolymsk`) still resolves as
    # itself rather than through this.
    dehyphenated = {f.replace("-", ""): f for f in idx}
    out = []
    for m in pat.finditer(text):
        got = " ".join(m.group(0).split())
        form, hyphenated = got, False
        if form not in idx:
            form = dehyphenated.get(got.replace("-", ""), "")
            hyphenated = True
        claims = idx.get(form, [])
        if not claims:
            continue
        out.append({
            "start": m.start(), "end": m.end(), "text": m.group(0), "form": form,
            "ids": [c["id"] for c in claims],
            "auto": (not hyphenated and len(claims) == 1 and claims[0]["auto"]),
            "scope": claims[0]["scope"] if len(claims) == 1 else "",
            "hyphenated": hyphenated,
            "status": claims[0]["status"] if len(claims) == 1 else "",
        })
    return out


def rule_links(hits: list[dict], autos: dict[str, str],
               seen: set[str] | None = None) -> list[dict]:
    """The hits a rule may actually link, `scope: first` reduced to the first one.

    **One predicate, four callers, and that is the whole reason it exists.**
    `generate` places these links, `validate` re-derives the ones a page has,
    `relink` writes the ones an entry ratified after collation adds, and
    `relink.missing` reports them. Three of the four had no notion of position
    before `once`; each computing "is this the first occurrence" for itself
    would let them disagree, and a disagreement between the placer and the
    re-deriver surfaces as a stale-stamp error on a page nobody edited.

    `hits` must be in document order — `match` returns them that way — and
    `seen` is the forms already linked earlier *on this page*. `generate` marks
    up one block at a time and passes a set it owns for the length of the page;
    a caller holding the whole body at once can leave it out.

    **`seen` is keyed on the store's form, not the page's spelling**, so
    `Chukchee` and a line-broken `Chuk-chee` are one form for the count. A
    hyphenated hit is never `auto` in the first place, so it neither takes the
    one link nor consumes it.
    """
    seen = set() if seen is None else seen
    out = []
    for h in hits:
        if not h["auto"] or autos.get(h["form"]) is None:
            continue
        if h["scope"] == "first":
            if h["form"] in seen:
                continue
            seen.add(h["form"])
        out.append(h)
    return out


#: How much prose to keep either side of a mention. The same window `/search`
#: shows for a query hit, because a reader sizing up "does this entry earn its
#: keep" is doing the same thing they do with a search result — reading enough
#: to tell whether the sentence is about the entity or merely contains its name.
WINDOW = 60


def window(text: str, start: int, end: int) -> tuple[str, str, str]:
    """`(before, match, after)` around a span, with `WINDOW` characters either side."""
    return (text[max(0, start - WINDOW):start], text[start:end],
            text[end:end + WINDOW])


def _unlinked_text(el) -> str:
    """An element's text with every already-referring subtree elided.

    A tail is kept where its element's body is dropped: the words on either side
    of a link are still adjacent prose, and joining them would be inventing a
    phrase the page does not set.
    """
    out = [el.text or ""]
    for kid in el:
        if not isinstance(kid.tag, str):
            out.append(kid.tail or "")
            continue
        out.append(" " if kid.get("ref") else _unlinked_text(kid))
        out.append(kid.tail or "")
    return "".join(out)


def occurrences(ids, refs, store: dict, root: Path = Path(".")) -> dict:
    """Where these entities appear across `refs`: `{id: {linked, unlinked}}`.

    **The corpus is the caller's and not this function's opinion.** `entity
    occurrences` passes `tei_html.collated`, because it is an audit of what is
    committed; the reading view passes the page list it is actually serving,
    which is collated-only by default and includes the generated drafts under
    `--drafts`. Neither inherits the other's scope, and a mentions list that
    named pages the view would 404 was the trap this shape exists to avoid.

    A row's `rank` comes from `tei_html.page_source`, which hands it back with
    the path rather than leaving it to be read off the directory — the property
    the symlink farm destroyed. `mz/tei/` is not a second witness against the
    page: it is `generate.page_blocks`' output written down, so a mention and
    the page's own `<rs>` are one derivation, and reading it costs a second
    where re-sweeping the ALTO costs twenty.

    **Linked and unlinked are counted apart**, and the unlinked pass runs over
    the body with the already-referring subtrees elided. Matching the whole body
    counted every link twice and inverted what the column is for: an unlinked
    hit means work outstanding, and a page where every instance was linked
    reported the same number as a page where none was.
    """
    from lxml import etree

    from .ids import TEI_NS
    from .tei_html import page_source

    ids = list(ids)
    idx = alias_index(store)
    # Only the named entities' forms, so a sweep over one entity does not pay
    # for the whole store's alias alternation.
    wanted = {f: c for f, c in idx.items() if any(x["id"] in set(ids) for x in c)}
    out: dict[str, dict] = {i: {"linked": [], "unlinked": []} for i in ids}

    for ref in refs:
        path, rank = page_source(ref, root)
        if path is None:
            continue
        try:
            doc = etree.parse(str(path)).getroot()
        except (OSError, etree.XMLSyntaxError):
            continue
        for el in doc.iter():
            r = el.get("ref")
            if r in out:
                out[r]["linked"].append({
                    "id": r, "ref": ref, "rank": rank,
                    "element": etree.QName(el).localname,
                    "resp": el.get("resp") or "",
                    "text": " ".join("".join(el.itertext()).split())})
        body = doc.find(f".//{{{TEI_NS}}}body")
        if body is None:
            continue
        text = " ".join(_unlinked_text(body).split())
        for h in match(text, wanted):
            before, got, after = window(text, h["start"], h["end"])
            for i in h["ids"]:
                if i in out:
                    out[i]["unlinked"].append({
                        "id": i, "ref": ref, "rank": rank, "form": h["form"],
                        "as_printed": " ".join(h["text"].split()),
                        "before": before, "match": got, "after": after,
                        "ambiguous": len(h["ids"]) > 1,
                        "hyphenated": h["hyphenated"]})
    return out


def check(root: Path = Path(".")) -> dict:
    """The store gate. Errors are defects; rows are what a reader should see.

    What it cannot check is whether an entry is *true* — that is what `status`
    and a human are for. What it does check is that every identity resolves,
    every class is known, the file agrees with its directory, and no form is
    auto-linked by two entities at once.
    """
    errors: list[str] = []
    store: dict[str, dict] = {}
    d = ent_dir(root)
    if d.is_dir():
        for p in sorted(d.glob("*/*.md")):
            try:
                rec = parse(p.read_text(encoding="utf-8"), where=str(p))
            except (Malformed, ValueError) as e:
                errors.append(str(e))
                continue
            rec["dir_class"] = p.parent.name
            rec["stem"] = p.stem
            rec["path"] = str(p)
            if rec["class"] != rec["dir_class"]:
                errors.append(
                    f"{p}: the heading says `{rec['class']}:` and the directory "
                    f"says `{rec['dir_class']}/`. A file's class is its identity, "
                    f"so moving it between directories renames the entity — if "
                    f"that is the intent, change both and re-point every @ref")
            if rec["slug"] != rec["stem"]:
                errors.append(f"{p}: the heading's slug is {rec['slug']!r}, "
                              f"the filename's is {rec['stem']!r}")
            if rec["id"] in store:
                errors.append(f"{p}: {rec['id']} is already defined at "
                              f"{store[rec['id']]['path']}")
                continue
            store[rec["id"]] = rec
        # Stray files outside a class directory are silently invisible to
        # `glob("*/*.md")`, so name them rather than let one sit unread.
        for p in sorted(d.glob("*.md")):
            errors.append(f"{p}: sits outside a class directory. An entity lives "
                          f"at entities/<class>/<slug>.md")

    # The shape store, read once. `area:` resolving is the same kind of claim
    # as `within:` resolving — a named thing either exists or it does not — and
    # `data/geo/` is tracked, so it is always there to check against. Anything
    # *geometric* is `harness geo verify`'s and reports rather than gates.
    shapes = geo_index(root).get("shapes", {})
    for rec in store.values():
        w = rec["within"]
        if w and w not in store:
            errors.append(f"{rec['path']}: `within: {w}` resolves to nothing")
        p = rec["part_of"]
        if p and p not in store:
            errors.append(f"{rec['path']}: `part-of: {p}` resolves to nothing")
        # **A thing is not part of itself**, and this is the one-step case of the
        # cycle check below — worth its own message because it is the mistake a
        # copied file makes, and "cycle: people:x → people:x" reads as a puzzle.
        if p and p == rec["id"]:
            errors.append(f"{rec['path']}: `part-of: {p}` names its own entry")
        # Across classes it is almost always a `within:` in the wrong field: a
        # people is not part of a river. Not refused outright — a `source:` being
        # part of a larger work is legitimate and crosses nothing — but a
        # geographical parent is the specific confusion this split exists to end,
        # so it is named.
        if p and p in store and store[p]["class"] in GEO_CLASSES \
                and rec["class"] not in GEO_CLASSES:
            errors.append(
                f"{rec['path']}: `part-of: {p}` points at a place. `part-of:` is "
                f"what a thing belongs to; where it *is* goes in `within:`")
        # **`within:` is geography's and nothing else's.** It answers "what
        # terrestrial thing contains this one", which `geo.NESTING` can check
        # and the atlas walks; on anything else it was the encyclopedia's
        # hierarchy wearing the atlas's field, and the store's three instances
        # were exactly that — two peoples filed inside a village to borrow its
        # extent, and a tale filed inside the collection that prints it. The
        # first is a `geo:` member now and the second is what `part-of:` is for.
        #
        # It also cost the thing it was borrowed for: a people hanging from a
        # village hung there in the atlas tree too, so its extent never rolled
        # up to its ethnicity and the Yupik map excluded two Yupik peoples.
        if w and w in store and (rec["class"] not in GEO_CLASSES
                                 or store[w]["class"] not in GEO_CLASSES):
            errors.append(
                f"{rec['path']}: `within: {w}` — `within:` is containment among "
                f"the four geographical classes ({', '.join(GEO_CLASSES)}), and "
                f"one end of this is not one. What a thing belongs to is "
                f"`part-of:`; whose extent it takes is a `geo:` member")
        # Per member, so the message names the one that failed: "langarea:a,
        # marine:b resolves to nothing" sends a reader to check the one that
        # was fine. Written for a composite `area:` and now simply the ordinary
        # case, since a record may name as many members as it likes.
        for m in geo_shapes(rec):
            if m not in shapes:
                errors.append(
                    f"{rec['path']}: `geo: {m}` resolves to nothing in "
                    f"data/geo/. `harness geo list` names every shape; if the "
                    f"source has no polygon for it, leave the member off and "
                    f"say so in the gloss rather than pointing at an "
                    f"approximation")
        for m in geo_refs(rec):
            if m == rec["id"]:
                errors.append(
                    f"{rec['path']}: `geo: {m}` names its own entry")
            elif m not in store:
                errors.append(
                    f"{rec['path']}: `geo: {m}` resolves to nothing")
        # `[[class:slug]]` in a gloss or an alias note is a reference, and a
        # reference to nothing is the failure this whole store exists to stop —
        # it renders as a link and goes nowhere. Checked here rather than at
        # render time because a reader should never be the one to find it.
        for target in sorted(set(WIKILINK.findall(rec["gloss"]))
                             | {m for t in rec["aliases"]
                                for m in WIKILINK.findall(t["note"])}):
            if target not in store:
                errors.append(f"{rec['path']}: [[{target}]] resolves to nothing")
    # Acyclic, so a containment chain terminates. A cycle would hang the
    # geography sprint's tree walk rather than fail it, which is the worse
    # outcome of the two. **Three edge kinds, walked separately** — `extent_of`
    # follows all of them, so a cycle in any hangs the same walk, and keeping
    # them apart is what lets the message name the field a reader has to go and
    # edit.
    #
    # A depth-first walk with a path stack rather than the linear chase this
    # was, because `geo:` is a *many*-valued edge: a record naming three
    # entities has three chains out of it and a `cur = store[cur][field]` can
    # only follow one.
    #
    # **The cycle that crosses two fields is deliberately not gated.** `A geo:
    # B` with `B within: A` is invisible to all three passes and stays that way:
    # `extent_of`'s path guard makes it terminate rather than hang, and an error
    # reading "cycle across two fields" names no single line for anybody to go
    # and fix. A message a reader cannot act on is worse than a shape that
    # resolves to a smaller box.
    def _cycles(edges, label: str) -> None:
        def walk(ident: str, path: list[str], seen: set[str]) -> None:
            for nxt in edges(store[ident]) if ident in store else ():
                if nxt not in store:
                    continue
                if nxt in path:
                    errors.append(
                        f"`{label}:` cycle: {' → '.join(path + [nxt])}")
                    continue
                if nxt in seen:
                    continue
                seen.add(nxt)
                walk(nxt, path + [nxt], seen)

        for rec in store.values():
            walk(rec["id"], [rec["id"]], set())

    _cycles(lambda r: [r["within"]] if r["within"] else [], "within")
    _cycles(lambda r: [r["part_of"]] if r["part_of"] else [], "part-of")
    _cycles(geo_refs, "geo")

    idx = alias_index(store)
    collisions = []
    for form in sorted(idx):
        claims = idx[form]
        if len(claims) < 2:
            continue
        ids = sorted(c["id"] for c in claims)
        autos = [c["id"] for c in claims if c["auto"]]
        collisions.append({"form": form, "claimed_by": " ".join(ids),
                           "auto": len(autos)})
        if len(autos) > 1:
            errors.append(
                f"alias {form!r} is rule-linked for "
                f"{' and '.join(sorted(autos))}. Two entities cannot both own a "
                f"form unconditionally — set all but one to `auto: no` and let "
                f"the reader choose, or narrow the forms until they no longer "
                f"collide. `once` collides exactly as `yes` does: it narrows how "
                f"many links a page gets, not which entity the form means")

    # **A worklist, never a gate.** An alias whose language nobody has stated is
    # not a defect — most of the store's forms are the book's own English and
    # saying so adds nothing — but "every foreign name is in the table, tagged"
    # is the standing editorial job, and a number nobody prints is a job nobody
    # does. Counted here, reported by `entity check`, gating nothing: measurement
    # never gates, and a gate here would be answered by deleting the alias.
    untagged = sum(1 for r in store.values() for t in r["aliases"] if not t["lang"])

    auto = auto_forms(idx)
    return {
        "entities": len(store),
        "proposed": sum(1 for r in store.values() if r["status"] == "proposed"),
        "aliases": len(idx),
        "auto_aliases": len(auto),
        "aliases_untagged": untagged,
        "collisions": collisions,
        "errors": errors,
        "ok": not errors,
    }
