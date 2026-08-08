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
trigger hits nobody has linked — which is the question an editor asks when
deciding whether an entry earns its keep.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

from ..entities import (
    Malformed,
    check,
    load,
    match,
    path_for,
    split_id,
    trigger_index,
)
from ._common import action, add_all, arg, group, opt, out, verdict


def register(cli):
    g = group(cli, "entity",
              "the encyclopedia: one markdown file per entity, keyed "
              "`class:slug`. The referent of every @ref in the corpus and the "
              "source of the trigger vocabulary the TEI generator applies by "
              "rule",
              section="Apparatus and reports")

    p = action(g, "new", run_new,
               help="scaffold an entry at `status: proposed`. Nothing mints an "
               "entry ratified: an entity a rule may link has to have been "
               "looked at by a human, and `entity ratify` is that act"
               "\n\nID: `class:slug`, e.g. `person:bogoras`")
    arg(p, "ident", metavar="ID")
    opt(p, "--canonical", required=True, metavar="NAME",
        help="the display name, written into the heading. Not a trigger unless "
             "you also pass it as one — how a thing is titled and how the book "
             "spells it in running prose are different questions")
    opt(p, "--since", required=True, metavar="PP-NNN",
        help="the page whose reading prompted the entry. Required, because an "
             "apparatus store that cannot be traced back to a page is one "
             "nobody can audit — data/toc.json is the standing case")
    opt(p, "--trigger", "triggers", multiple=True, metavar="FORM",
        help="a form that means this entity, added at `auto: no`. Raising one "
             "to `auto: yes` is a separate act, done in the file or the browser, "
             "because it licenses a link nobody will be asked about")
    opt(p, "--commit", is_flag=True,
        help="write it. Without this the file is reported and not created")

    action(g, "check", run_check,
           help="the store gate: every file parses, every class is known, every "
           "heading agrees with its directory, every `within:` resolves and the "
           "chain is acyclic, and no form is `auto: yes` for two entities at "
           "once — which would be a rule licensed to link a string that is "
           "genuinely ambiguous. Exit 1 on any of it. Collisions that are not "
           "errors are still reported: an ambiguous form is the normal state and "
           "the generator surfaces it as a question")

    action(g, "list", run_list,
           help="every entry: id, status, canonical name, trigger count, and "
           "the page that prompted it. Proposed entries first — they are the "
           "audit queue")

    p = action(g, "show", run_show,
               help="whole records, triggers and gloss included"
               "\n\nID: `class:slug`; several are allowed")
    arg(p, "idents", nargs=-1, required=True, metavar="ID")

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
               "already written into committed TEI, and the trigger hits nobody "
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

## triggers

| form | auto | note |
|---|---|---|
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
    rows = "\n".join(f"| {unicodedata.normalize('NFD', t)} | no | |"
                     for t in a.triggers) or "| | no | |"
    text = TEMPLATE.format(ident=ident, canonical=a.canonical, since=a.since,
                           rows=rows)
    # Parsed before it is written, so a bad `--since` or an empty `--trigger`
    # fails as a message rather than as a file the next `check` complains about.
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
             "triggers": len(r["triggers"]),
             "auto": sum(1 for t in r["triggers"] if t["auto"]),
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
                if k not in ("triggers", "gloss", "dir_class", "stem")},
            name=i, heading=True)
        out(a, r["triggers"], name=f"{i} triggers", heading=True)
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
    idx = trigger_index(store)
    # Only the named entities' forms, so a sweep over one entity does not pay for
    # the whole store's trigger alternation.
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
                    unlinked[i].append({"id": i, "ref": ref, "form": h["form"],
                                        "ambiguous": len(h["ids"]) > 1})
    out(a, [{"id": i, "linked": len(linked[i]), "unlinked": len(unlinked[i]),
             "status": store[i]["status"]} for i in ids])
    rows = [r for i in ids for r in linked[i]]
    if rows:
        out(a, rows, "linked", heading=True)
    rows = [r for i in ids for r in unlinked[i]]
    if rows:
        out(a, rows, "unlinked", heading=True)
    return 0
