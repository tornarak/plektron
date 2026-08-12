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
    Malformed,
    alias_index,
    check,
    load,
    match,
    path_for,
    split_id,
)
from ..geo import canonical_area, split_area
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
    opt(p, "--since", required=True, metavar="PP-NNN",
        help="the page whose reading prompted the entry. Required, because an "
             "apparatus store that cannot be traced back to a page is one "
             "nobody can audit — data/toc.json is the standing case")
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
    opt(p, "--area", metavar="KIND:SLUG",
        help="the shape in data/geo/ this entity is drawn as, e.g. "
             "`watershed:anadyr`. **Identifying a name Bogoras wrote in 1904 "
             "with a polygon a modern service returned is a human's act**, "
             "which is why it is typed here and never matched by name: "
             "`watershed:main` and the English word are one keystroke apart. "
             "Several, comma-separated, is a composite — the union of shapes "
             "no single source draws together, and the assertion that they "
             "belong together is likewise the human's. `harness geo list` "
             "names every shape")
    opt(p, "--commit", is_flag=True,
        help="write it. Without this the file is reported and not created")

    p = action(g, "locate", run_locate,
               help="set or replace an existing entry's `geo:` point, its "
               "`area:` shape, or both. **The act that puts a name on the "
               "map**, and it is a human's: a coordinate for a toponym Bogoras "
               "wrote in 1904, or the judgement that two sourced polygons are "
               "one speaker area, is an assertion about the world that no rule "
               "may make. `geo verify`'s `unlocated` report is the worklist "
               "this answers a row of. One ID, because the flags name one "
               "entity's fields"
               "\n\nID: `class:slug`, e.g. `place:chukchi-peninsula`",
               constraints=(require_any("geo", "area"),))
    arg(p, "ident", metavar="ID")
    opt(p, "--geo", metavar="LAT LON",
        help="two WGS84 decimal degrees, latitude then longitude, "
             "space-separated — `66.05 -169.6`. Negative longitudes are west, "
             "as the store's sources write them; the shift into the atlas's "
             "continuous window is the reader's, not the author's")
    opt(p, "--area", metavar="KIND:SLUG",
        help="the shape this entity is drawn as, or several comma-separated "
             "for a composite. **A composite is not a shape the store holds** "
             "— it is resolved from its members on every run, so the union "
             "cannot go stale, and the claim that the members belong together "
             "lives here in the entity file where a reader can see whose it is")
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
               "holds few of them — it reports every @ref it finds and refuses "
               "outright if one is in committed `tei/`, where a rule may not "
               "rewrite a page a human signed"
               "\n\nOLD and NEW are both `class:slug`; the class may not change",
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
- since: {since}
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
    lang = (a.lang or "").strip()
    rows = "\n".join(f"| {unicodedata.normalize('NFD', t)} | {lang} | no | |"
                     for t in a.aliases) or f"| | {lang} | no | |"
    extra = "".join(f"- {k}: {v}\n" for k, v in
                    (("within", a.within), ("area", a.area)) if v)
    text = TEMPLATE.format(ident=ident, canonical=a.canonical, since=a.since,
                           extra=extra, rows=rows)
    # Parsed before it is written, so a bad `--since`, an unknown `--lang` or an
    # empty `--alias` fails as a message rather than as a file the next `check`
    # complains about.
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
FIELD_ORDER = ("status", "since", "within", "geo", "area", "link", "authority")


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
    fields = list(re.finditer(r"^-\s+([a-z]+):.*$", head, re.M))
    if not fields:
        raise ValueError("the entry has no field block to add to")
    for m in fields:
        k = m.group(1)
        r = FIELD_ORDER.index(k) if k in FIELD_ORDER else len(FIELD_ORDER)
        if r > rank:
            return head[:m.start()] + f"- {key}: {value}\n" + head[m.start():] + rest
    at = fields[-1].end() + 1
    return head[:at] + f"- {key}: {value}\n" + head[at:] + rest


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
    for key, given, before in (
            ("geo", a.geo, " ".join(f"{v:g}" for v in rec["geo"]) if rec["geo"] else ""),
            ("area", a.area, rec["area"])):
        if not given:
            continue
        # Normalized on the way in so the file holds one spelling of a union
        # and `geo verify` cannot see the same composite as two.
        value = canonical_area(given) if key == "area" else " ".join(str(given).split())
        text = _set_field(text, key, value)
        rows.append({"id": ident, "field": key, "was": before or "—",
                     "now": value, "wrote": bool(a.commit)})

    # Parsed before it is written, as `entity new` does: a malformed coordinate
    # or a shape kind that collides with an entity class fails as a message
    # here, rather than as a file the next `check` has to explain.
    from ..entities import parse
    got = parse(text, where=str(p))
    unknown = [m for m in split_area(got["area"])
               if m not in geo_index(a.root)["shapes"]]
    if unknown:
        raise ValueError(
            f"{ident}: {', '.join(unknown)} names nothing in data/geo/. "
            f"`harness geo list` names every shape — and a composite resolves "
            f"only when every member does")
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
             "auto": sum(1 for t in r["aliases"] if t["auto"]),
             "since": r["since"]}
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
    if old_cls != new_cls:
        raise ValueError(
            f"{old} → {new} changes the class. That is a delete and a create, "
            f"not a rename: the class is half the identity, so every @ref "
            f"pointing at it would mean a different thing afterwards")
    if new in store:
        raise ValueError(f"{new} already exists at {store[new]['path']}")

    # **Refused before anything is written**, not reported after. A rule may not
    # rewrite a page a human signed, so if the old identity is live in committed
    # `tei/` the rename is not this verb's to make — the pages have to be
    # amended first, by whoever collated them. `mz/tei/` is derived and comes
    # back from `tei generate`, so it only wants naming.
    links = _refs_to(old, a.root)
    signed = [r for r in links if r["store"] == "tei"]

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

    # Every other file that names the old identity. `within:` and `[[…]]` are
    # the two ways one entry points at another, and `entity check` gates both,
    # so a rename that missed one would fail the gate rather than go quiet.
    others = []
    for other in store.values():
        if other["id"] == old:
            continue
        t0 = Path(other["path"]).read_text(encoding="utf-8")
        t1 = t0.replace(f"[[{old}]]", f"[[{new}]]")
        # `[^\S\n]*`, not `\s*`: `\s` eats newlines, so a greedy trailing run
        # swallows the blank line before `## aliases` and the field block runs
        # into the section heading.
        t1 = re.sub(rf"^(-[^\S\n]+within:[^\S\n]*){re.escape(old)}[^\S\n]*$",
                    rf"\g<1>{new}", t1, flags=re.M)
        if t1 != t0:
            others.append((Path(other["path"]), t1, other["id"]))

    from ..entities import parse
    parse(text, where=str(dst))

    if signed:
        out(a, {"old": old, "new": new, "wrote": False,
                "means": f"refused — {sum(r['links'] for r in signed)} @ref(s) "
                         f"in committed tei/ name it"})
        out(a, links, "links", heading=True)
        return 1

    if a.commit:
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "x", encoding="utf-8") as fh:
            fh.write(text)
        src.unlink()
        for p, t1, _i in others:
            p.write_text(t1, encoding="utf-8")

    out(a, {"old": old, "new": new, "canonical": canonical,
            "filed_as_alias": filed, "repointed": len(others),
            "stale_refs": sum(r["links"] for r in links),
            "wrote": bool(a.commit),
            "means": "renamed" if a.commit else "would rename — pass --commit"})
    if others:
        out(a, [{"id": i, "path": str(p)} for p, _t, i in others],
            "repointed", heading=True)
    if links:
        out(a, links, "stale refs", heading=True)
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
    return 0


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


def run_occurrences(a) -> int:
    from lxml import etree

    from ..ids import TEI_NS

    store = _store(a)
    ids = _resolve(a, store)
    idx = alias_index(store)
    # Only the named entities' forms, so a sweep over one entity does not pay for
    # the whole store's alias alternation.
    wanted = {f: c for f, c in idx.items()
              if any(x["id"] in set(ids) for x in c)}

    linked: dict[str, list[dict]] = {i: [] for i in ids}
    unlinked: dict[str, list[dict]] = {i: [] for i in ids}
    tei = a.root / "tei"
    for p in sorted(tei.glob("chukchi-*.xml")) if tei.is_dir() else []:
        ref = p.stem.replace("chukchi-", "")
        try:
            root = etree.parse(str(p)).getroot()
        except etree.XMLSyntaxError:
            continue
        for el in root.iter():
            r = el.get("ref")
            if r in linked:
                linked[r].append({"id": r, "ref": ref,
                                  "element": etree.QName(el).localname,
                                  "resp": el.get("resp") or "",
                                  "text": " ".join("".join(el.itertext()).split())})
        body = root.find(f".//{{{TEI_NS}}}body")
        if body is None:
            continue
        # **The text with the already-linked spans taken out.** Matching over the
        # whole body counted every link twice — once as linked, once as unlinked —
        # which inverts what the column is for: an unlinked hit is supposed to mean
        # work outstanding, and a page where every instance was linked reported the
        # same number as a page where none was.
        for h in match(_unlinked_text(body), wanted):
            for i in h["ids"]:
                if i in unlinked:
                    unlinked[i].append({
                        "id": i, "ref": ref, "form": h["form"],
                        "as_printed": " ".join(h["text"].split()),
                        "ambiguous": len(h["ids"]) > 1,
                        "hyphenated": h["hyphenated"]})
    out(a, [{"id": i, "linked": len(linked[i]), "unlinked": len(unlinked[i]),
             "status": store[i]["status"]} for i in ids])
    rows = [r for i in ids for r in linked[i]]
    if rows:
        out(a, rows, "linked", heading=True)
    rows = [r for i in ids for r in unlinked[i]]
    if rows:
        out(a, rows, "unlinked", heading=True)
    return 0
