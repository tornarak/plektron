"""`harness annotation` — the editor's notices and supplements over the book.

The store is `new` / `attach` / `check` / `list` / `show` / `ratify`, over
`edition/annotations/`, taking the `--commit` discipline every authored store
takes. `coverage` is the one report, and it exists because the store's hardest
question is not whether a file parses but **which leaves an attachment actually
reaches** — a `page:` target reaches its leaf always, a `toc:` target reaches
only the leaves something places in that section, and the difference is
invisible from the file. See `harness/annotations.py`.
"""
from __future__ import annotations

import re

import click

from .. import annotations as ann
from ._common import action, arg, group, opt, out, verdict

_SECTION = re.compile(r"^##\s+\S+\s*$", re.M)

TEMPLATE = """# {ident} — {title}

- status: proposed
{attaches}
## summary

(unwritten)

## full

(unwritten)
"""


def register(cli):
    g = group(cli, "annotation",
              "the editor's own voice over the book — a `notice` above what it "
              "attaches to, a `supplement` below — each attached to pages, ToC "
              "sections or entities. The class is the placement, and `status` "
              "gates whether an annotation attaches to anything at all",
              section="Apparatus and reports")

    p = action(g, "new", run_new,
               help="scaffold an annotation at status: proposed. Nothing mints "
               "one ratified, and until it is ratified it attaches to nothing — "
               "a notice is the editor's voice inserted at the top of the "
               "artifact, unasked, so a human signs it first"
               "\n\nID: class:slug, e.g. notice:physical-anthropology")
    arg(p, "ident", metavar="ID")
    opt(p, "--title", metavar="NAME", required=True,
        help="the display title, written into the heading")
    opt(p, "--attach", "attach", metavar="TARGET", multiple=True,
        help="what this annotates: `page:PP-NNN`, `toc:ID` or "
             "`entity:class:slug`. Repeatable")
    opt(p, "--commit", is_flag=True,
        help="write it. Without this the file is reported and not created")

    p = action(g, "attach", run_attach,
               help="add one target to an annotation, or drop one with "
               "`--remove`. **One target per call, deliberately**: a flag that "
               "replaced the whole list would let a typo drop nine attachments "
               "of ten with only git as the witness"
               "\n\nID: class:slug.  TARGET: `page:PP-NNN`, `toc:ID` or "
               "`entity:class:slug`")
    arg(p, "ident", metavar="ID")
    arg(p, "target", metavar="TARGET")
    opt(p, "--remove", is_flag=True, help="drop the target instead of adding it")
    opt(p, "--commit", is_flag=True, help="write the change")

    action(g, "check", run_check,
           help="the store gate: every file parses, every heading agrees with "
           "its directory and its filename, every `attaches:` resolves — an id "
           "in edition/toc.json for `toc:`, an entry the entity store holds for "
           "`entity:` — every annotation attaches to at least one thing, every "
           "`## summary` is present, every links row can render, and every "
           "`[[wikilink]]` resolves. Exit 1 on any of it. **A `page:` ref is "
           "gated for shape and not for existence**: there is no leaf universe "
           "a clone can read, and `coverage` is where that question is asked")

    p = action(g, "list", run_list, help="every annotation, with its class, "
               "status and how many things it attaches to")
    # The param keeps click's derived name, `class`, rather than a Python-safe
    # alias: `test_every_closed_set_matches_its_fence` keys a fence's choices off
    # the flag's own spelling, so a param renamed to `cls` would document a set
    # under a name the parser does not have. `a` is a `SimpleNamespace`, which
    # holds a keyword-named attribute perfectly well — it is only the dotted
    # *literal* that Python refuses, and `getattr` is the read.
    opt(p, "--class", type=click.Choice(sorted(ann.ANNOTATION_CLASSES)),
        default=None, help="one class only")

    p = action(g, "show", run_show,
               help="whole records, the summary and long text included"
               "\n\nID: class:slug; several are allowed")
    arg(p, "idents", nargs=-1, required=True, metavar="ID")

    p = action(g, "ratify", run_ratify,
               help="proposed -> ratified, and **this is what makes an "
               "annotation attach to anything**. The human act: it means the "
               "text has been read against what it will appear over"
               "\n\nID: several are allowed")
    arg(p, "idents", nargs=-1, required=True, metavar="ID")
    opt(p, "--commit", is_flag=True, help="write the change")

    p = action(g, "coverage", run_coverage,
               help="which leaves each annotation actually reaches: named "
               "directly by a `page:` target, or reached through a `toc:` one. "
               "**`unwitnessed` is a bound and not a miss** — without a "
               "witnessed folio a leaf cannot be shown to fall inside a section "
               "or outside it, so the set a section attachment misses is not "
               "computable and only its size is. Reports; never gates")
    opt(p, "--id", "ids", metavar="ID", multiple=True,
        help="one annotation. Repeatable; omitted means every one in the store")
    opt(p, "--refs", is_flag=True,
        help="list the refs each annotation reaches instead of counting them, "
             "so a row is a worklist rather than a notification")
    opt(p, "--universe", metavar="STORE", default="mz/ocr", show_default=True,
        help="the store whose refs are the denominator. Named rather than "
             "implied: every count here is against one store, and a number "
             "whose denominator is unstated describes nothing")


def _set_attaches(text: str, values) -> str:
    """The whole run of `- attaches:` lines replaced by one line per value.

    A sibling of `cli/_entity._set_lines` and not a loop over a one-line writer,
    for that function's reason: replacing a single line would overwrite the
    first member and leave the rest, which is a silent half-write. Scoped to the
    text above the first `##`, so an `- attaches:` written inside the prose is
    prose.
    """
    values = list(values)
    sect = _SECTION.search(text)
    head_end = sect.start() if sect else len(text)
    head, rest = text[:head_end], text[head_end:]
    block = "\n".join(f"- attaches: {v}" for v in values)
    pat = re.compile(r"^-\s+attaches:.*(?:\n-\s+attaches:.*)*$", re.M)
    m = pat.search(head)
    if m:
        if not values:
            return head[:m.start()] + head[m.end() + 1:] + rest
        return head[:m.start()] + block + head[m.end():] + rest
    if not values:
        return text
    # Absent: the field goes directly under `- status:`, where `new` puts it.
    st = re.search(r"^-\s+status:.*$", head, re.M)
    if not st:
        raise ValueError("no `- status:` line to write the field after")
    return head[:st.end()] + "\n" + block + head[st.end():] + rest


def _resolve(a, store: dict) -> list[str]:
    idents = [str(i) for i in a.idents]
    for i in idents:
        ann.split_id(i)
    missing = [i for i in idents if i not in store]
    if missing:
        raise ValueError(f"no such annotation: {', '.join(missing)}")
    return idents


def run_new(a) -> int:
    ident = str(a.ident)
    ann.split_id(ident)
    p = ann.path_for(ident, a.root)
    if p.exists():
        out(a, {"id": ident, "path": str(p), "wrote": False,
                "means": "already exists"})
        return 1
    targets = [ann.parse_attach(t, at=f"{ident}: ")["raw"] for t in a.attach]
    attaches = "".join(f"- attaches: {t}\n" for t in targets)
    text = TEMPLATE.format(ident=ident, title=a.title, attaches=attaches)
    if targets:
        # Parsed before it is written, as `entity new` and `lexicon new` do: a
        # bad `--attach` fails as a message, not as a file the next `check` has
        # to explain. Skipped where there are no targets, since the scaffold
        # legitimately attaches to nothing until one is added and `parse`
        # refuses that state only at `check` time.
        ann.parse(text, where=str(p))
    if a.commit:
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(p, "x", encoding="utf-8") as fh:
                fh.write(text)
        except FileExistsError:
            out(a, {"id": ident, "path": str(p), "wrote": False,
                    "means": "already exists — written while this ran"})
            return 1
    out(a, {"id": ident, "path": str(p), "attaches": targets,
            "wrote": bool(a.commit),
            "means": "written, status proposed" if a.commit
                     else "would write — pass --commit"})
    return 0


def run_attach(a) -> int:
    ident = str(a.ident)
    store = ann.load(a.root)
    if ident not in store:
        raise ValueError(f"no such annotation: {ident}")
    rec = store[ident]
    target = ann.parse_attach(str(a.target), at=f"{ident}: ")["raw"]
    was = [t["raw"] for t in rec["attaches"]]

    if a.remove:
        if target not in was:
            out(a, {"id": ident, "target": target, "was": was, "now": was,
                    "wrote": False, "means": "not attached; nothing to remove"})
            return 1
        now = [t for t in was if t != target]
    else:
        if target in was:
            out(a, {"id": ident, "target": target, "was": was, "now": was,
                    "wrote": False, "means": "already attached"})
            return 0
        now = was + [target]

    path = rec["path"]
    text = path.read_text(encoding="utf-8")
    new = _set_attaches(text, now)
    ann.parse(new, where=str(path))       # re-parsed before it is written
    if a.commit:
        path.write_text(new, encoding="utf-8")
    out(a, {"id": ident, "target": target, "was": was, "now": now,
            "wrote": bool(a.commit),
            "means": ("removed" if a.remove else "attached") if a.commit
                     else "would write — pass --commit"})
    return 0


def run_check(a) -> int:
    try:
        r = ann.check(a.root)
    except (ann.Malformed, ValueError) as e:
        out(a, [{"error": str(e)}], "errors", heading=True)
        return verdict(a, 1, "the store does not parse")
    out(a, {k: v for k, v in r.items()
            if k not in ("errors", "ok", "proposed", "unused_links")})
    if r["proposed"]:
        out(a, [{"id": i} for i in r["proposed"]], "proposed", heading=True)
    if r["unused_links"]:
        out(a, [{"link": u} for u in r["unused_links"]], "unused links",
            heading=True)
    if r["errors"]:
        out(a, [{"error": e} for e in r["errors"]], "errors", heading=True)
    return verdict(a, 0 if r["ok"] else 1,
                   "the store is coherent" if r["ok"]
                   else "the store has defects; nothing was written")


def run_list(a) -> int:
    store = ann.load(a.root)
    want = getattr(a, "class")            # see the comment at the flag
    rows = [{"id": k, "class": v["class"], "status": v["status"],
             "placement": v["placement"], "title": v["title"],
             "attaches": len(v["attaches"]), "links": len(v["links"])}
            for k, v in sorted(store.items())
            if not want or v["class"] == want]
    out(a, rows, "annotations", heading=True)
    return 0


def run_show(a) -> int:
    store = ann.load(a.root)
    for ident in _resolve(a, store):
        rec = dict(store[ident])
        rec["path"] = str(rec["path"])
        rec["attaches"] = [t["raw"] for t in rec["attaches"]]
        out(a, rec, name=ident, heading=True)
    return 0


def run_ratify(a) -> int:
    store = ann.load(a.root)
    rows = []
    for ident in _resolve(a, store):
        rec = store[ident]
        if rec["status"] == "ratified":
            rows.append({"id": ident, "was": "ratified", "now": "ratified",
                         "wrote": False})
            continue
        path = rec["path"]
        text = path.read_text(encoding="utf-8")
        # Through the store's own field writer, never a substring replace: the
        # parser accepts `- status:proposed` with no space and reads fields only
        # above the first `##`, so a literal search could land in the long text
        # and report a ratification that never happened.
        new = ann.set_status(text, "ratified", where=str(path))
        if a.commit:
            path.write_text(new, encoding="utf-8")
        rows.append({"id": ident, "was": rec["status"], "now": "ratified",
                     "wrote": bool(a.commit)})
    out(a, rows, "ratified", heading=True)
    if not a.commit:
        out(a, {"means": "would write — pass --commit"})
    return 0


def run_coverage(a) -> int:
    store = ann.load(a.root)
    if a.ids:
        wanted = [str(i) for i in a.ids]
        for i in wanted:
            ann.split_id(i)
        missing = [i for i in wanted if i not in store]
        if missing:
            raise ValueError(f"no such annotation: {', '.join(missing)}")
        store = {k: v for k, v in store.items() if k in wanted}
    r = ann.reach(store, a.root, a.universe)
    out(a, {"universe": r["universe"], "leaves": r["leaves"],
            "witnessed": r["witnessed"]})
    rows = []
    for row in r["rows"]:
        base = {"id": row["id"], "class": row["class"], "status": row["status"]}
        if a.refs:
            base |= {"pages": " ".join(row["pages"]),
                     "via_section": " ".join(row["via_section"])}
        else:
            base |= {"pages": len(row["pages"]),
                     "via_section": len(row["via_section"])}
        base |= {"sections": " ".join(row["sections"]),
                 "entities": " ".join(row["entities"]),
                 "unwitnessed": row["unwitnessed"]}
        if row["unknown"]:
            base["unknown"] = " ".join(row["unknown"])
        rows.append(base)
    out(a, rows, "coverage", heading=True)
    return 0
