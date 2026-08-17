"""`harness entity` — the encyclopedia store, and the gate over it.

The store is human-authored and tracked, so it takes the `--commit` discipline
`gt/` and `tei/` take: report what would change, write only when told. What is
new here is `check`, which is the store's *internal* gate — that every identity
resolves and no form is claimed unconditionally by two entities — as against
`tei validate`, which gates every pointer *into* the store from a page. The two
run over different files and neither implies the other: a coherent store can be
pointed at by a `@ref` that resolves to nothing, and a dangling `within:` breaks
nothing in any page.

`occurrences` is measurement and never gates. It answers "where does this
entity appear", by two routes at once — the links already written, and the
alias hits nobody has linked — which is the question an editor asks when
deciding whether an entry earns its keep.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from ..entities import (
    _SECTION,
    ALIASES,
    ENTITY_CLASSES,
    Malformed,
    check,
    load,
    occurrences,
    path_for,
    spell_geo,
    split_id,
)
from ..geo import index as geo_index
from ._common import (
    action,
    add_all,
    arg,
    group,
    opt,
    out,
    require_any,
    verdict,
)

#: The row `entity new` writes so the alias table has a body — no form, no
#: language, no note. `parse` reads it as nothing at all; `entity alias`
#: replaces it rather than writing under it.
_EMPTY_ROW = re.compile(r"^\|\s*\|\s*\|\s*(?:yes|no)?\s*\|\s*\|\s*$")


def register(cli):
    g = group(cli, "entity",
              "the encyclopedia: one markdown file per entity, keyed "
              "`class:slug`. The referent of every @ref in the corpus and the "
              "source of the alias vocabulary the TEI generator applies by "
              "rule",
              section="Apparatus and reports")

    p = action(g, "new", run_new,
               help="scaffold an entry at `status: proposed`. Nothing mints an "
               "entry ratified: an entity a rule may link has to have been "
               "looked at by a human, and `entity ratify` is that act"
               "\n\nID: `class:slug`, e.g. `person:bogoras`")
    arg(p, "ident", metavar="ID")
    opt(p, "--canonical", required=True, metavar="NAME",
        help="the display name, written into the heading. Not an alias unless "
             "you also pass it as one — how a thing is titled and how the book "
             "spells it in running prose are different questions")
    opt(p, "--alias", "aliases", multiple=True, metavar="FORM",
        help="a form that means this entity, added at `auto: no`. Raising one "
             "to `auto: yes` is a separate act, done in the file or the browser, "
             "because it licenses a link nobody will be asked about. A native "
             "form is the NFD surface spelling, never a lexicon handle key — "
             "the key is a fold and collides on purpose")
    opt(p, "--lang", metavar="CODE",
        help="the language every `--alias` on this run is a name in, e.g. `ckt` "
             "or `ru`. Shortest BCP-47, the same string a page writes in "
             "`xml:lang`. Left off, the aliases are filed with the language "
             "unstated, which `entity check` counts rather than refuses")
    opt(p, "--within", metavar="ID",
        help="the entity that contains this one, `class:slug`. The atlas's "
             "whole structure, and the only thing that puts a location "
             "somewhere rather than merely on a map — a tributary inside its "
             "trunk, a village inside its basin")
    opt(p, "--part-of", metavar="ID",
        help="what this entity *belongs to*, `class:slug`, where `--within` "
             "says where it *is*. A subgroup of a people, a work inside a "
             "larger work. Nothing drawing a map reads it; a people with no "
             "geography of its own falls back along it for a bound, which is "
             "the one place the two meet")
    opt(p, "--geo", "geos", multiple=True, metavar="MEMBER",
        help="where this entity is: a point `LAT LON`, a shape in data/geo/ "
             "`kind:slug`, or another entity `class:slug` whose extent it "
             "takes. Repeatable, and the field is the union of its members. "
             "**Identifying a name Bogoras wrote in 1904 with a polygon a "
             "modern service returned is a human's act**, which is why a shape "
             "is typed here and never matched by name: `watershed:main` and the "
             "English word are one keystroke apart. `harness geo list` names "
             "every shape")
    opt(p, "--authority", metavar="KEY",
        help="the entry in data/authorities.json this entity is the work of, "
             "e.g. `steller1774`. What puts the full printed title on the card "
             "without the entry restating it — the title lives in the "
             "authorities store, which read it off the Authorities Quoted "
             "pages, and a copy here would be the one that goes stale")
    opt(p, "--commit", is_flag=True,
        help="write it. Without this the file is reported and not created")

    p = action(g, "alias", run_alias,
               help="add one alias row to an entry that exists. **For the "
               "form's fidelity, and for nothing else** — a `link:` or a "
               "`within:` is a line of ASCII a text editor sets as well as a "
               "flag would, but an alias is a native form, and typing one by "
               "hand is where this store gets hurt: a precomposed `й` against "
               "an NFD store, an `i` for an `ɪ`, an apostrophe for `ˊ`. None of "
               "them shows in the file afterwards. So the form may be a "
               "**lexicon handle in braces** — `{Kulu'c^i}` — which `lookup "
               "expand` replaces with the form the corpus prints; a key the "
               "book spells two ways resolves to nothing, and nothing "
               "half-expands. A literal form is normalized to NFD and "
               "otherwise trusted, since Cyrillic and English aliases have no "
               "handle to resolve"
               "\n\nID: `class:slug`   FORM: a form, or `{key}` to expand")
    arg(p, "ident", metavar="ID")
    arg(p, "form", metavar="FORM")
    opt(p, "--lang", metavar="CODE",
        help="the language the form is a name in, from `harness/langs.py`. "
             "Omitted means *unstated*, which most of the store says and which "
             "is a different claim from a wrong code")
    opt(p, "--auto", is_flag=True,
        help="the form is safe to link out of context. **No default and no "
             "inverse**: `auto` is the author's declaration, so the flag's "
             "absence is `no` and says so in the file. Where the entry is "
             "already ratified this licenses a link, so the pages it licenses "
             "it over are brought up to date — collated pages relinked, drafts "
             "regenerated, exactly as `entity ratify` does")
    opt(p, "--note", metavar="TEXT",
        help="the note cell — where the form is attested, or why it is `no`")
    opt(p, "--commit", is_flag=True,
        help="write it. Without this the row is reported and not added")

    p = action(g, "sigla", run_sigla,
               help="carry `Authorities Quoted`'s printed sigla onto the "
               "`source:` entries as their name and their aliases. **The "
               "siglum is how the book names a work** — `Maydell, I` and not "
               "`Maydell 1893` — so it is what a reader meets in a footnote "
               "and what the alias table needs in order to link one. A bare "
               "surname is left alone: it is already the entry's alias and it "
               "is the ambiguous case, since `person:maydell` claims it too. "
               "Adds and renames; never removes a row a human wrote, and never "
               "touches an entry whose authority lists no siglum")
    opt(p, "--commit", is_flag=True,
        help="write them. Without this every change is reported and none made")

    p = action(g, "locate", run_locate,
               help="set or replace an existing entry's `geo:` members, its "
               "`frame:` box, or both. **The act that puts a name on the "
               "map**, and it is a human's: a coordinate for a toponym Bogoras "
               "wrote in 1904, or the judgement that two sourced polygons are "
               "one speaker area, is an assertion about the world that no rule "
               "may make. `geo verify`'s `unlocated` report is the worklist "
               "this answers a row of. One ID, because the flags name one "
               "entity's fields"
               "\n\nID: `class:slug`, e.g. `place:chukchi-peninsula`",
               constraints=(require_any("geos", "frame"),))
    arg(p, "ident", metavar="ID")
    opt(p, "--geo", "geos", multiple=True, metavar="MEMBER",
        help="a point `LAT LON` — two WGS84 decimal degrees, latitude then "
             "longitude, `66.05 -169.6`, negative longitudes west as the "
             "store's sources write them; or a shape in data/geo/ `kind:slug`; "
             "or another entity `class:slug`, whose extent this one takes. "
             "**Repeatable, and it replaces rather than appends** — every "
             "`--geo` on one run is the complete new member list, because a "
             "flag that only added would have no way to take a member off. The "
             "field is the union of what it holds")
    opt(p, "--frame", metavar="W S E N",
        help="four WGS84 decimal degrees — west south east north — saying where "
             "the map should *look*, which is a different question from where "
             "the entity *is*. Longitude first, unlike `--geo`, because this is "
             "a box; east may exceed 180, the atlas's frame being continuous "
             "across the antimeridian. Two cases earn one: a container with no "
             "shape, whose viewBox is otherwise the union of everything beneath "
             "it and so is set by whichever descendant strays farthest; and a "
             "shape dense with members, which frames on its parent by default "
             "and so draws its settlements on top of each other")
    opt(p, "--commit", is_flag=True,
        help="write it. Without this the change is reported and not made")

    action(g, "check", run_check,
           help="the store gate: every file parses, every class is known, every "
           "heading agrees with its directory, every `within:` resolves and the "
           "chain is acyclic, and no form is `auto: yes` for two entities at "
           "once — which would be a rule licensed to link a string that is "
           "genuinely ambiguous. Exit 1 on any of it. Collisions that are not "
           "errors are still reported: an ambiguous form is the normal state and "
           "the generator surfaces it as a question")

    action(g, "list", run_list,
           help="every entry: id, status, canonical name, alias count, and "
           "the page that prompted it. Proposed entries first — they are the "
           "audit queue")

    p = action(g, "show", run_show,
               help="whole records, aliases and gloss included"
               "\n\nID: `class:slug`; several are allowed")
    arg(p, "idents", nargs=-1, required=True, metavar="ID")

    p = action(g, "rename", run_rename,
               help="move an entity to a new identity, re-pointing every "
               "`within:` and `[[wikilink]]` in the store. **The identity is "
               "what every @ref holds**, so this is cheap only while the corpus "
               "holds few of them: a committed page is re-pointed in place — a "
               "@ref asserts that a string names an entity, and a rename moves "
               "neither side of that, only the pointer's spelling — and a "
               "generated draft is rebuilt from the moved store"
               "\n\nOLD and NEW are both `class:slug`; the class may change "
               "only where the `<name @type>` does not",
               constraints=())
    arg(p, "old", metavar="OLD")
    arg(p, "new", metavar="NEW")
    opt(p, "--canonical", metavar="NAME",
        help="the new display name. **The old one is filed as an alias**, "
             "because `detectors.entity_forms` splits canonicals into the "
             "corpus's proper-noun dictionary — retitling without it would "
             "drop the book's own spelling out of the dictionary silently. "
             "Skipped where the entry already lists the form")
    opt(p, "--commit", is_flag=True,
        help="write it. Without this every edit is reported and none is made")

    p = action(g, "ratify", run_ratify,
               help="proposed -> ratified. **The human act**, and the only thing "
               "that lets a rule link the entry's forms without asking — so it "
               "means the entry has been read against the pages it claims, not "
               "that it looks plausible"
               "\n\nID: `class:slug`; several are allowed")
    arg(p, "idents", nargs=-1, required=True, metavar="ID")
    opt(p, "--commit", is_flag=True, help="write the change")

    p = action(g, "occurrences", run_occurrences,
               help="where an entity appears, by two routes: the @ref links "
               "already written into committed TEI, and the alias hits nobody "
               "has linked. The second is the interesting one — a large unlinked "
               "count on a ratified entity means pages collated before the entry "
               "existed, and `tei generate` will link them on the next run. "
               "Measurement; never gates"
               "\n\nID: `class:slug`; several are allowed")
    arg(p, "idents", nargs=-1, metavar="ID")
    add_all(p, "every entity in the store")


def _store(a) -> dict:
    return load(a.root)


def _resolve(a, store: dict) -> list[str]:
    """The ids named on the command line, refused up front if any is unknown.

    Before any work, as the multi-ref convention has it: a sweep that half-runs
    and then refuses leaves the caller reading two outputs to find out what
    happened.
    """
    if getattr(a, "all", False):
        if a.idents:
            raise ValueError("--all with named ids: name them or sweep, not both")
        return sorted(store)
    if not a.idents:
        raise ValueError("name at least one id, or --all for the whole store")
    ids = [str(i) for i in a.idents]
    for i in ids:
        split_id(i)               # form first, so `bogoras` is a clear message
    missing = [i for i in ids if i not in store]
    if missing:
        raise ValueError(f"no such entity: {', '.join(missing)}")
    return ids


TEMPLATE = """# {ident} — {canonical}

- status: proposed
{extra}
## aliases

| form | lang | auto | note |
|---|---|---|---|
{rows}

## gloss

(unwritten)
"""


def run_new(a) -> int:
    ident = str(a.ident)
    split_id(ident)
    p = path_for(ident, a.root)
    if p.exists():
        out(a, {"id": ident, "path": str(p), "wrote": False,
                "means": "already exists"})
        return 1
    # An empty `lang` cell is `| |` and never `|  |`: two spaces are §2.9 sentence
    # spacing to `corpus normalize`, so the naive f-string made every scaffolded
    # entry fail the NFD gate on the run after it was written.
    cell = f" {(a.lang or '').strip()} ".replace("  ", " ")
    rows = "\n".join(f"| {unicodedata.normalize('NFD', t)} |{cell}| no | |"
                     for t in a.aliases) or f"| |{cell}| no | |"
    # In `FIELD_ORDER`, and `geo` is the one that may repeat — one line per
    # member, since the field is the union of what it holds.
    extra = "".join(f"- {k}: {v}\n" for k, v in
                    [("within", a.within), ("part-of", a.part_of)]
                    + [("geo", g) for g in a.geos]
                    + [("authority", a.authority)] if v)
    text = TEMPLATE.format(ident=ident, canonical=a.canonical,
                           extra=extra, rows=rows)
    # Parsed before it is written, so a bad `--within`, an unknown `--lang` or
    # an empty `--alias` fails as a message rather than as a file the next
    # `check` complains about.
    from ..entities import parse
    parse(text, where=str(p))
    if a.commit:
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            # `x`, not `w`: a dispatched batch has several collators proposing
            # into one store at once, and the exists() check above is a courtesy
            # rather than a guarantee. Two agents reaching the same slug is a
            # real outcome — the same man met on two pages — and the loser
            # should be told, not silently overwrite the winner.
            with open(p, "x", encoding="utf-8") as fh:
                fh.write(text)
        except FileExistsError:
            out(a, {"id": ident, "path": str(p), "wrote": False,
                    "means": "already exists — written while this ran"})
            return 1
    out(a, {"id": ident, "path": str(p), "wrote": bool(a.commit),
            "means": "written, status proposed" if a.commit
                     else "would write — pass --commit"})
    return 0


#: The order a scaffolded entry writes its fields in. A field this verb adds
#: goes where `entity new` would have put it, so a file a human later reads is
#: not visibly divided into what was typed and what was set by a command.
FIELD_ORDER = ("status", "within", "part-of", "geo", "area", "frame", "link",
               "authority")


def _set_field(text: str, key: str, value: str) -> str:
    """`- key: value` replaced in place, or inserted in `FIELD_ORDER`.

    In place matters: a field that moved on every edit would make every diff of
    an entity file a reordering with a change somewhere inside it, which is the
    diff nobody reads. Insertion is only for a key the file does not have yet.
    """
    # **Everything here is scoped to the field block** — the text above the
    # first `##`. A `- authority: …` inside a gloss is prose, `entities.parse`
    # draws that line the same way, and an unscoped substitution would silently
    # rewrite a sentence instead of a field.
    sect = _SECTION.search(text)
    head_end = sect.start() if sect else len(text)
    head, rest = text[:head_end], text[head_end:]

    pat = re.compile(rf"^-\s+{re.escape(key)}:.*$", re.M)
    if pat.search(head):
        return pat.sub(lambda _m: f"- {key}: {value}", head, count=1) + rest

    rank = FIELD_ORDER.index(key) if key in FIELD_ORDER else len(FIELD_ORDER)
    # `[a-z][a-z-]*`, matching `entities._FIELD`. Under `[a-z]+` the one
    # hyphenated field in the store did not match, so `part-of:` was invisible
    # to this scan and ranked as unknown — the same shape of miss that once made
    # the *parser* discard the field silently, and the reason that pattern
    # carries the note it does. Here it only mislocated an insertion, which is
    # why nothing caught it.
    fields = list(re.finditer(r"^-\s+([a-z][a-z-]*):.*$", head, re.M))
    if not fields:
        raise ValueError("the entry has no field block to add to")
    for m in fields:
        k = m.group(1)
        r = FIELD_ORDER.index(k) if k in FIELD_ORDER else len(FIELD_ORDER)
        if r > rank:
            return head[:m.start()] + f"- {key}: {value}\n" + head[m.start():] + rest
    at = fields[-1].end() + 1
    return head[:at] + f"- {key}: {value}\n" + head[at:] + rest


def _set_lines(text: str, key: str, values) -> str:
    """`- key: …` — the whole run of them replaced by one line per value.

    `_set_field`'s sibling for a repeatable field, and it has to be a sibling
    rather than a loop over it: that function replaces *one* line and would
    overwrite the first member of a union while leaving the rest, which is the
    silent half-write this store is organised against.

    The run is replaced **where it starts**, so a field does not migrate down
    the block on every edit — `_set_field`'s reason, and the same scoping to the
    text above the first `##`.
    """
    values = list(values)
    sect = _SECTION.search(text)
    head_end = sect.start() if sect else len(text)
    head, rest = text[:head_end], text[head_end:]

    pat = re.compile(rf"^-\s+{re.escape(key)}:.*(?:\n-\s+{re.escape(key)}:.*)*$",
                     re.M)
    block = "\n".join(f"- {key}: {v}" for v in values)
    m = pat.search(head)
    if m:
        # An empty list removes the field outright, newline and all.
        if not values:
            return head[:m.start()] + head[m.end() + 1:] + rest
        return head[:m.start()] + block + head[m.end():] + rest
    if not values:
        return text
    # Absent: insert the whole block at the key's `FIELD_ORDER` slot, which is
    # `_set_field`'s insertion with N lines instead of one.
    return _set_field(head, key, values[0]).replace(
        f"- {key}: {values[0]}", block, 1) + rest


def run_locate(a) -> int:
    store = _store(a)
    ident = str(a.ident)
    split_id(ident)
    rec = store.get(ident)
    if rec is None:
        out(a, {"id": ident, "wrote": False, "means": "no such entity"})
        return 1

    p = Path(rec["path"])
    text = p.read_text(encoding="utf-8")
    rows = []
    if a.geos:
        # **Replaces the whole member list**, which is why the "was" column
        # joins every member rather than printing one: an author reading the row
        # has to be able to see what is going away.
        members = [" ".join(str(v).split()) for v in a.geos]
        rows.append({"id": ident, "field": "geo",
                     "was": ", ".join(spell_geo(rec)) or "—",
                     "now": ", ".join(members), "wrote": bool(a.commit)})
        text = _set_lines(text, "geo", members)
    if a.frame:
        value = " ".join(str(a.frame).split())
        rows.append({"id": ident, "field": "frame",
                     "was": " ".join(f"{v:g}" for v in rec["frame"])
                     if rec["frame"] else "—",
                     "now": value, "wrote": bool(a.commit)})
        text = _set_field(text, "frame", value)

    # Parsed before it is written, as `entity new` does: a malformed coordinate
    # or a member that is none of the three things fails as a message here,
    # rather than as a file the next `check` has to explain.
    from ..entities import geo_refs, geo_shapes, parse
    got = parse(text, where=str(p))
    unknown = [m for m in geo_shapes(got)
               if m not in geo_index(a.root)["shapes"]]
    if unknown:
        raise ValueError(
            f"{ident}: {', '.join(unknown)} names nothing in data/geo/. "
            f"`harness geo list` names every shape")
    dangling = [m for m in geo_refs(got) if m not in store]
    if dangling:
        raise ValueError(
            f"{ident}: {', '.join(dangling)} names no entity. A `geo:` member "
            f"whose kind is an entity class is a reference, and this one "
            f"resolves to nothing")
    if a.commit:
        p.write_text(text, encoding="utf-8")
    out(a, rows)
    return 0


def run_check(a) -> int:
    try:
        r = check(a.root)
    except (Malformed, ValueError) as e:
        out(a, [{"error": str(e)}], "errors", heading=True)
        return verdict(a, 1, "the store does not parse")
    out(a, {k: v for k, v in r.items()
            if k not in ("collisions", "errors", "ok")})
    if r["collisions"]:
        out(a, r["collisions"], "collisions", heading=True)
    if r["errors"]:
        out(a, [{"error": e} for e in r["errors"]], "errors", heading=True)
    return verdict(a, 0 if r["ok"] else 1,
                   "the store is coherent" if r["ok"]
                   else "the store has defects; nothing was written")


def run_list(a) -> int:
    store = _store(a)
    rows = [{"id": r["id"], "status": r["status"], "canonical": r["canonical"],
             "aliases": len(r["aliases"]),
             "auto": sum(1 for t in r["aliases"] if t["auto"])}
            for r in store.values()]
    # Proposed first: the list is read as a worklist more often than as a census,
    # and what wants doing should not be sorted in among what is done.
    rows.sort(key=lambda r: (r["status"] != "proposed", r["id"]))
    out(a, rows)
    return 0


def run_show(a) -> int:
    store = _store(a)
    ids = _resolve(a, store)
    for i in ids:
        r = store[i]
        out(a, {k: v for k, v in r.items()
                if k not in ("aliases", "gloss", "dir_class", "stem")},
            name=i, heading=True)
        out(a, r["aliases"], name=f"{i} aliases", heading=True)
    return 0


def _refs_to(ident: str, root: Path) -> list[dict]:
    """Every `@ref` naming this identity, by store and page.

    Both stores, and the row says which — `mz/tei/` is derived and regenerates,
    committed `tei/` is a page a human signed. The two are the same string in
    the same attribute and only the directory tells them apart, which is exactly
    why the caller is handed the distinction rather than left to infer it.
    """
    out_rows = []
    for store, d in (("tei", root / "tei"), ("mz/tei", root / "mz" / "tei")):
        for p in sorted(d.glob("chukchi-*.xml")) if d.is_dir() else []:
            n = p.read_text(encoding="utf-8").count(f'ref="{ident}"')
            if n:
                out_rows.append({"store": store,
                                 "ref": p.stem.replace("chukchi-", ""),
                                 "links": n})
    return out_rows


def run_alias(a) -> int:
    """Add one alias row to an entry that exists.

    **The verb is here for the form's fidelity and nothing else.** A `link:` or a
    `within:` is a line of ASCII that a text editor sets as well as a flag would;
    an alias is a *native form*, and typing one by hand is where this store gets
    hurt. Three ways, all of which happened during the pass that prompted this:
    a precomposed `й` where the store is NFD and nothing matches; a guessed `ɪ`
    for an `i`, the corpus's largest correction family; an `ˊ` typed as an
    apostrophe. None of them is visible in the file afterwards.

    So the form may be given as a **lexicon handle in braces** — `{Kulu'c^i}` —
    and `lookup.expand` substitutes the ratified form the corpus actually
    prints. That is transcription rather than typing, and it inherits two
    properties worth more than the convenience: a key the book spells more than
    one way resolves to nothing at all, and **nothing half-expands**, so a line
    with one bad handle is not written rather than written wrong.

    A form given literally is normalized to NFD and otherwise trusted, because
    Cyrillic and English aliases have no handle to resolve and refusing them
    would leave the verb useless for most of the store.
    """
    from ..langs import ALIAS_LANGS
    from ..lookup import expand

    store = _store(a)
    ident = str(a.ident)
    rec = store.get(ident)
    if rec is None:
        raise ValueError(f"no such entity: {ident}")

    # **Only a braced form goes near the lexicon.** `expand` builds the handle
    # index off the corpus and the marks config, which a literal form has no use
    # for — and asking for them anyway made this verb refuse to run in a tree
    # that has none, for an alias that never needed resolving.
    form = str(a.form)
    if "{" in form or "}" in form:
        form, refusals = expand(form, a.root, min_pages=1)
        if refusals:
            raise ValueError(f"{ident}: {refusals[0]}")
    form = unicodedata.normalize("NFD", form).strip()
    if not form:
        raise ValueError(f"{ident}: the form is empty")

    lang = (a.lang or "").strip()
    if lang and lang not in ALIAS_LANGS:
        raise ValueError(
            f"{ident}: `{lang}` is not in the alias vocabulary. One of: "
            f"{', '.join(sorted(ALIAS_LANGS))}. A blank language is legal and "
            f"means unstated, which is a different claim from a wrong one")
    if form in {t["form"] for t in rec["aliases"]}:
        raise ValueError(f"{ident}: already lists {form!r}. `parse` refuses a "
                         f"form twice, so this would break the file it wrote")

    p = Path(rec["path"])
    text = p.read_text(encoding="utf-8")
    start, end = _alias_rows(text)
    # `| |` and never `|  |`: two spaces are §2.9 sentence spacing to the
    # normalizer, which `entity new` learned the same way.
    # **Every cell, not just the language one.** The rule was applied to `lang`
    # and not to `note`, so an alias added without one wrote `|  |` and the file
    # failed `corpus normalize` from the moment it was written — a gate the
    # author of the alias never ran, on a defect invisible in any rendering of
    # the table. Building both the same way is what stops that recurring: a rule
    # stated once and applied in one place cannot be applied to one of two.
    cells = " | ".join(str(v) for v in
                       (form, lang, "yes" if a.auto else "no", a.note or ""))
    row = f"| {cells} |".replace("|  |", "| |")
    # **The scaffold's placeholder row goes when a real one arrives.**
    # `entity new` writes `| | | no | |` so the table has a body, and `parse`
    # drops it on the floor — a row with no form is not an alias. Left in place
    # under a form that *is* one, it reads as an alias whose form went missing,
    # which is a different and worse claim than the empty table it stood for.
    # Matched on the whole shape, `auto` apart, which is safe because it is the
    # only empty-form row the store tolerates: put a note in one and `parse`
    # refuses the file. So nothing dropped here was ever written by a human.
    body = "\n".join(ln for ln in text[start:end].split("\n")
                     if not _EMPTY_ROW.match(ln)).rstrip("\n")
    text = text[:start] + body + f"\n{row}\n\n" + text[end:]

    from ..entities import alias_index, auto_forms, parse
    after_rec = parse(text, where=str(p))
    if a.commit:
        p.write_text(text, encoding="utf-8")

    # **An auto form is a licence, and the pages it licenses are brought up to
    # date here.** `ratify` already does this, on the argument that the rule
    # links what the store held *when the generator ran* — and adding a form at
    # `auto: yes` to an entry already ratified is the same licensing event in
    # miniature. It was not wired, so the new form linked on no collated page
    # and appeared in no draft until something unrelated regenerated, and
    # nothing said so: `tei validate` re-derives the links a page *has* and has
    # nothing to say about the ones it lacks.
    #
    # **The trigger is `auto_forms`' own answer, not the three conditions
    # restated.** A form is rule-linkable when exactly one entity claims it,
    # that claim says `auto: yes`, and the entity is ratified; asking whether
    # the form came out the other side of `auto_forms` tests all three at once
    # and cannot drift from them. A form that fails any — a collision, an entry
    # still proposed — changes nothing on any page, so the pass is skipped
    # rather than run for no rows.
    after = {**store, ident: {**rec, **after_rec}}
    licensed = auto_forms(alias_index(after)).get(form) == ident
    out(a, {"id": ident, "form": form, "lang": lang or "—",
            "auto": bool(a.auto), "expanded": form != str(a.form),
            "licensed": licensed, "wrote": bool(a.commit)})
    if licensed:
        from ..relink import apply_to_corpus, refresh_drafts

        # The store is re-read after a write, so what is applied is what the
        # file now says; the report-only branch runs against the record `parse`
        # returned, which is the same entry as it would be.
        pass_store = _store(a) if a.commit else after
        links, notes, _undo = apply_to_corpus(
            a.root, pass_store, write=bool(a.commit))
        drafts = refresh_drafts(a.root, pass_store, [ident],
                                write=bool(a.commit))
        if links:
            out(a, links, "links applied to collated pages", heading=True)
        if drafts:
            # Named without a verb, so the heading reads true in both modes.
            out(a, [{"ref": r} for r in drafts],
                "draft pages out of date", heading=True)
        if notes:
            out(a, notes, "not applied", heading=True)
    return 0


def _alias_rows(text: str) -> tuple[int, int]:
    """Where the alias table's rows start and end in `text`."""
    marks = list(_SECTION.finditer(text))
    for i, m in enumerate(marks):
        if m.group(1) != ALIASES:
            continue
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        return m.end(), end
    raise ValueError("the entry has no `## aliases` section")


def run_rename(a) -> int:
    old, new = str(a.old), str(a.new)
    store = _store(a)
    if old not in store:
        raise ValueError(f"no such entity: {old}")
    old_cls, _ = split_id(old)
    new_cls, _ = split_id(new)
    # **A class change is permitted exactly where the `<name @type>` does not
    # move.** The refusal used to be flat, on "every @ref would mean a different
    # thing afterwards" — true of `place:` → `event:`, and false of the pair the
    # geographical split is made of. What a page asserts is its `@type`: a reader
    # wrote `<name type="toponym">`, meaning they saw a place-name. Whether that
    # name denotes a point (`place:`) or a region (`land:`) is a fact about the
    # store, and no page ever recorded it. Where the two classes map to one type
    # the page is untouched by the move; where they do not — `place:` → `water:`,
    # toponym to hydronym — the ref would contradict the type beside it, and that
    # is a re-reading of the page, which is a human's and not a verb's.
    if old_cls != new_cls:
        want, got = ENTITY_CLASSES[old_cls], ENTITY_CLASSES[new_cls]
        if want is None or want != got:
            raise ValueError(
                f"{old} → {new} changes the class from one <name @type> to "
                f"another ({want or 'none'} → {got or 'none'}). That is a delete "
                f"and a create, not a rename: a page's @type records what a "
                f"reader saw, and the ref would contradict it afterwards")
    if new in store:
        raise ValueError(f"{new} already exists at {store[new]['path']}")

    # **The committed pages are rewritten too, and that is not the firewall
    # bending.** This used to refuse outright, on "a rule may not rewrite a page
    # a human signed" — which conflated two different things. The rule protects
    # what a page *asserts*; an `@ref` asserts "this string names that entity",
    # and a rename changes neither side of it. Only the spelling of the pointer
    # moves, and leaving it behind is what would break the assertion: the ref
    # would resolve to nothing, which `validate` calls worse than no ref at all.
    #
    # `mz/tei/` is derived and comes back from `tei generate`, so it is not
    # rewritten — editing a file the generator is about to replace would only
    # race it. **What it does instead is run the generator**, below, once the
    # store has moved. Naming the pages and stopping there was a hand-off with
    # no receiver: nothing ran the regeneration the table implied, so until
    # somebody happened to, those drafts carried a `@ref` resolving to an
    # identity that no longer existed — and `edition serve --drafts` renders
    # them.
    links = _refs_to(old, a.root)
    signed = [r for r in links if r["store"] == "tei"]
    stale = [r for r in links if r["store"] != "tei"]

    rec = store[old]
    src = Path(rec["path"])
    dst = path_for(new, a.root)
    text = src.read_text(encoding="utf-8")

    canonical = a.canonical or rec["canonical"]
    text = re.sub(r"^#\s+.*$", f"# {new} — {canonical}", text, count=1, flags=re.M)

    # The book's own spelling has to survive the retitling. `entity_forms`
    # splits canonicals into the corpus's proper-noun dictionary, so a rename
    # that only moved the heading would take the old name out of the dictionary
    # and start reporting it as a transcription candidate on every page it is
    # printed on. Skipped where the entry already lists it — `parse` refuses a
    # form listed twice, so the naive append would break the file just written.
    filed = ""
    if a.canonical and a.canonical != rec["canonical"]:
        if rec["canonical"] not in {t["form"] for t in rec["aliases"]}:
            start, end = _alias_rows(text)
            rows = text[start:end].rstrip("\n")
            text = (text[:start] + rows + f"\n| {rec['canonical']} |  | no | "
                    f"the book's spelling |\n\n" + text[end:])
            filed = rec["canonical"]

    # Every other file that names the old identity. `within:`, `part-of:` and
    # `[[…]]` are the three ways one entry points at another, and `entity check`
    # gates all three, so a rename that missed one would fail the gate rather
    # than go quiet.
    others = []
    for other in store.values():
        if other["id"] == old:
            continue
        t0 = Path(other["path"]).read_text(encoding="utf-8")
        t1 = t0.replace(f"[[{old}]]", f"[[{new}]]")
        # `[^\S\n]*`, not `\s*`: `\s` eats newlines, so a greedy trailing run
        # swallows the blank line before `## aliases` and the field block runs
        # into the section heading.
        # **`geo:` too, now that a member may name an entity.** Safe without
        # testing what kind of member it is: a point line's value is two numbers
        # and can never equal an identity, and a shape id can never equal one
        # either — shape kinds are held disjoint from the entity classes, which
        # is the same invariant that lets the field mix the three at all.
        t1 = re.sub(rf"^(-[^\S\n]+(?:within|part-of|geo):[^\S\n]*)"
                    rf"{re.escape(old)}[^\S\n]*$",
                    rf"\g<1>{new}", t1, flags=re.M)
        if t1 != t0:
            others.append((Path(other["path"]), t1, other["id"]))

    from ..entities import parse
    parse(text, where=str(dst))

    # Committed pages only. The whole-word `ref="…"` match is exact: an identity
    # is never a prefix of another inside those quotes.
    pages = []
    for r in signed:
        p = a.root / "tei" / f"chukchi-{r['ref']}.xml"
        t0 = p.read_text(encoding="utf-8")
        pages.append((p, t0.replace(f'ref="{old}"', f'ref="{new}"'), r["ref"]))

    if a.commit:
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "x", encoding="utf-8") as fh:
            fh.write(text)
        src.unlink()
        for p, t1, _i in others:
            p.write_text(t1, encoding="utf-8")
        for p, t1, _i in pages:
            p.write_text(t1, encoding="utf-8")

    # **After the store has moved, never before.** The generator reads the
    # entity store to build its links, so a draft rebuilt while the old file
    # was still on disk would come back with the old ref in it.
    #
    # Scoped to the refs already found, and not through `refresh_drafts`: that
    # one asks `occurrences` which pages hold an *unlinked mention*, which is
    # the right question after a ratify and the wrong one here. The pages are
    # known by name — they are the ones holding `ref="old"` — and a mention
    # that was already linked is exactly what a rename has to reach.
    regenerated = []
    if a.commit and stale:
        from ..generate import Unready, generate

        for r in stale:
            try:
                generate(r["ref"], a.root, force=True)
            except Unready as e:
                # Same refusal `refresh_drafts` makes: renaming an entity is a
                # judgement about the store, and a draft whose ground truth was
                # withdrawn is a fact about another one. The row says the page
                # is still out of date rather than the rename failing.
                regenerated.append({**r, "regenerated": False, "why": str(e)})
            else:
                regenerated.append({**r, "regenerated": True, "why": ""})

    out(a, {"old": old, "new": new, "canonical": canonical,
            "filed_as_alias": filed, "repointed": len(others),
            "pages": sum(r["links"] for r in signed),
            "stale_refs": sum(r["links"] for r in stale),
            "regenerated": sum(1 for r in regenerated if r["regenerated"]),
            "wrote": bool(a.commit),
            "means": "renamed" if a.commit else "would rename — pass --commit"})
    if pages:
        out(a, [{"ref": i, "path": str(p)} for p, _t, i in pages],
            "collated pages rewritten", heading=True)
    if others:
        out(a, [{"id": i, "path": str(p)} for p, _t, i in others],
            "repointed", heading=True)
    # The heading has to read true in both modes: a report-only run regenerates
    # nothing, and the rows say per page whether the rebuild happened.
    if stale:
        out(a, regenerated or [{**r, "regenerated": False, "why": ""}
                               for r in stale],
            "drafts holding the old ref", heading=True)
    return 0


def run_sigla(a) -> int:
    """`Authorities Quoted`'s printed sigla, carried onto the `source:` entries.

    **The siglum is the name the book uses, and the store was not saying it.**
    `source:maydell-1893` was titled `Maydell 1893` — a name printed nowhere,
    while every footnote citing the work sets `Maydell, I`. A reader who met the
    siglum on a page had nothing in the encyclopedia to match it against, and
    `tei generate` had only the bare surname to match on, so the mark stopped
    short of the half that says *which* work: `<rs>Maydell</rs> I, p. 331.`

    Both halves come from the same field. The name is what `[Cited, MAYDELL, I,
    II.]` prints, a two-volume work being one work; the aliases are its
    spellings, comma and no comma, because the book sets both in one apparatus.

    **It adds and it renames.** A row a human wrote is never removed, and an
    entry whose authority lists no siglum, or whose siglum is a bare surname, is
    not touched at all. `auto` is `yes` only where nothing else in the store
    claims the form, which is `entity check`'s rule applied ahead of it rather
    than a judgement made here.

    **A bare surname is not unlinkable, and saying so was the overstatement
    that let the guard be written on half of this.** `Steller, p. 123` names the
    book and nothing else; `citations.py` links exactly that, by rule, on the
    locator — 64 of the 130 `source:` links, every one a bare surname. What
    cannot reach it is the *alias table*, because an alias is a context-free
    string match and `person:steller` claims the same string. So the bare
    surname yields no row here, and it needs none.

    The rename follows from that and not from ambiguity. A siglum earns the
    heading because it says *which work* — `Maydell, I` does, `Steller` does
    not, naming the man as readily as the book while costing the heading the
    year that told them apart. `siglum_forms` already returned nothing for a
    bare surname; the rename ran anyway, and 17 entries came out titled
    `Steller`, `Nelson`, `Murdoch`. Both halves now mean the same thing.
    """
    from .. import authorities
    from ..entities import alias_index, parse

    store = _store(a)
    works = {w["key"]: w for w in authorities.load(a.root)}
    idx = alias_index(store)
    #: Forms this run has already written. `idx` is a snapshot taken before the
    #: first write, so two entries whose sigla collide would both be told
    #: nothing else claims the form and both come out `auto: yes` — which
    #: `entity check` refuses outright, one commit too late to be cheap.
    added: dict[str, str] = {}
    rows, renamed = [], []
    for ident in sorted(store):
        rec = store[ident]
        work = works.get(rec.get("authority") or "")
        if not work or not work["cited_as"]:
            continue
        forms = authorities.siglum_forms(work["cited_as"])
        name = authorities.siglum_name(work["cited_as"])
        if not forms:
            continue
        have = {t["form"] for t in rec["aliases"]}
        want = [f for f in forms if f not in have]
        if not want and rec["canonical"] == name:
            continue
        p = Path(rec["path"])
        text = p.read_text(encoding="utf-8")
        if rec["canonical"] != name:
            renamed.append({"id": ident, "was": rec["canonical"], "now": name,
                            "wrote": bool(a.commit)})
            text = text.replace(f"— {rec['canonical']}\n", f"— {name}\n", 1)
        if want:
            start, end = _alias_rows(text)
            body = "\n".join(ln for ln in text[start:end].split("\n")
                             if not _EMPTY_ROW.match(ln)).rstrip("\n")
            new = []
            for f in want:
                # Contested here means contested in the file afterwards, which
                # `entity check` gates and this must not walk into: a form two
                # entries claim is a question for a human, not a licence.
                claimed = (any(c["id"] != ident for c in idx.get(f, []))
                           or added.get(f, ident) != ident)
                auto = "no" if claimed else "yes"
                note = "" if auto == "yes" else "auto: no — another entry claims it"
                added.setdefault(f, ident)
                new.append(f"| {f} | | {auto} | {note} |".replace("|  |", "| |"))
                rows.append({"id": ident, "form": f, "auto": auto == "yes",
                             "wrote": bool(a.commit)})
            text = text[:start] + body + "\n" + "\n".join(new) + "\n\n" + text[end:]
        parse(text, where=str(p))
        if a.commit:
            p.write_text(text, encoding="utf-8")
    out(a, rows, "aliases added")
    out(a, renamed, "entries renamed", heading=True)
    if not a.commit:
        return verdict(a, 0, "reported; --commit writes")
    # An added `auto` form is a licence, and `entity alias` brings the pages it
    # licenses up to date for exactly this reason — the same event, in bulk.
    from ..relink import apply_to_corpus, refresh_drafts

    after = _store(a)
    touched = sorted({r["id"] for r in rows if r["auto"]})
    links, notes, _undo = apply_to_corpus(a.root, after, write=True)
    drafts = refresh_drafts(a.root, after, touched, write=True)
    if links:
        out(a, links, "links applied to collated pages", heading=True)
    if drafts:
        out(a, [{"ref": r} for r in drafts], "drafts regenerated", heading=True)
    if notes:
        out(a, notes, "not applied", heading=True)
    return 0


def run_ratify(a) -> int:
    store = _store(a)
    ids = _resolve(a, store)
    rows = []
    for i in ids:
        r = store[i]
        was = r["status"]
        if was == "ratified":
            rows.append({"id": i, "was": was, "now": was, "wrote": False})
            continue
        p = Path(r["path"])
        text = p.read_text(encoding="utf-8")
        new = text.replace("- status: proposed", "- status: ratified", 1)
        if new == text:
            raise ValueError(f"{p}: no `- status: proposed` line to change")
        if a.commit:
            p.write_text(new, encoding="utf-8")
        rows.append({"id": i, "was": was, "now": "ratified",
                     "wrote": bool(a.commit)})
    out(a, rows)

    # **Ratifying is what licenses the rule, so the pages it licenses it over
    # are brought up to date here.** `tei generate` links every auto form the
    # store held when it ran, and collation follows generation: an entry
    # ratified afterwards leaves plain text on every page already collated,
    # invisibly — `validate` re-derives the links a page *has* and has nothing
    # to say about the ones it lacks. The store is re-read rather than mutated
    # in place, so what gets applied is what the files now say.
    from ..relink import apply_to_corpus, refresh_drafts

    after = _store(a) if a.commit else {
        **store, **{i: {**store[i], "status": "ratified"} for i in ids}}
    links, notes, _undo = apply_to_corpus(a.root, after, write=bool(a.commit))
    # The drafts are regenerated rather than relinked: a draft carries the
    # generator's own questions beside its text, and answering the link while
    # leaving the comment would put two halves of one file in contradiction.
    drafts = refresh_drafts(a.root, after, ids, write=bool(a.commit))
    if links:
        out(a, links, "links applied to collated pages", heading=True)
    if drafts:
        # Named without a verb, because the heading has to read true in both
        # modes: `--commit` regenerates these and a report-only run does not.
        out(a, [{"ref": r} for r in drafts], "draft pages out of date", heading=True)
    if notes:
        out(a, notes, "not applied", heading=True)
    return 0


def run_occurrences(a) -> int:
    from ..tei_html import collated

    store = _store(a)
    ids = _resolve(a, store)
    # **Committed `tei/` alone**, which is what this action has always audited
    # and what `VERBS.md` documents. `entities.occurrences` takes its corpus
    # from its caller precisely so that the reading view's wider one — which
    # includes the generated drafts under `--drafts` — does not leak in here.
    got = occurrences(ids, collated(a.root), store, a.root)

    out(a, [{"id": i, "linked": len(got[i]["linked"]),
             "unlinked": len(got[i]["unlinked"]),
             "status": store[i]["status"]} for i in ids])
    for kind in ("linked", "unlinked"):
        rows = [r for i in ids for r in got[i][kind]]
        if rows:
            out(a, rows, kind, heading=True)
    return 0
