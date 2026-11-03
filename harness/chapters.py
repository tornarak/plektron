"""Chapter runs: the spans `apparatus.runs()` serves a chapter as, derived.

A declared run names its leaves in `edition/runs.json` because nothing else can:
the printed Contents is six leaves because a human ruled them apparatus. A
chapter's leaves are already said, twice over, by the book — the ToC orders the
chapters, and each chapter's `<milestone unit="chapter">` says on which leaf it
opens — so declaring them as well would be a third statement of one fact, and the
first to go stale.

**The milestone is the witness, not the folio index.** It is already re-derived
on every `tei generate` from two printed facts (the ToC's `page_start` and the
folio the page prints), and the generator refuses rather than guesses where the
head is not found. The folio index answers for 280 folios of 732; the milestones
answer for all 23 chapters. A span is then pure arithmetic over scan indices:
from a chapter's opening leaf to the leaf before the next one opens, and a leaf
between them that holds no text — a plate, a blank — is in the chapter because
the binding put it there, with nothing inferred about what it is.

**Read from whichever page the edition would render**, the signed page over the
draft (`tei_html.page_source`), and regardless of whether this sitting shows
drafts. Where a chapter *is* is a fact about the text; whether a reader may see a
leaf of it is the view's question, and answering the first from the second would
make the edition's chapters vanish whenever drafts were hidden.

**Nothing is derived past a gap.** A chapter whose opener is missing, or found
twice, gets no run — and neither does the chapter before it, whose end is the
missing one's start. The pages stay served one at a time, which is what they were
before chapters existed; a span that guessed its end would put one chapter's text
under another's title, and look exactly like one that had not.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from lxml import etree

from .layout import page_files
from .ns import TEI_NS
from .refs import norm_ref, parse_ref
from .state import load_toc

#: The run kind a chapter is served as. Not one of `apparatus.KINDS`: those name a
#: store a renderer reads entries from, and a chapter's content is its pages.
KIND = "chapter"

#: The ToC level a chapter is. `state.MILESTONE_UNITS[1]`.
LEVEL = 1

_MS = f"{{{TEI_NS}}}milestone"
#: Text before a milestone *on its own leaf*, in the body. The teiHeader is on the
#: `preceding::` axis too and has to be cut off, and a comment's text is not a
#: text node, so the generator's own notes never count.
_BEFORE = etree.XPath("preceding::text()[normalize-space()][ancestor::t:body]",
                      namespaces={"t": TEI_NS})


def _sources(root: Path) -> dict[str, Path]:
    """`{ref: page file}` — the signed page where there is one, else the draft."""
    from .tei_html import page_source, readable
    out = {}
    for ref in readable(root):
        path, _rank = page_source(ref, root)
        if path is not None:
            out[ref] = path
    return out


def milestones(root: Path = Path("."), sources: dict[str, Path] | None = None
               ) -> dict[str, list[dict]]:
    """`{toc id: [{"ref", "shared"}, …]}` for every milestone in the text.

    A list, because the gate's question is whether there is exactly one. `shared`
    says the leaf carries text *before* the milestone — the previous division's
    tail — which is what makes a leaf belong to two chapters.
    """
    root = Path(root)
    out: dict[str, list[dict]] = {}
    for ref, path in (sources if sources is not None else _sources(root)).items():
        try:
            tree = etree.parse(str(path))
        except (etree.XMLSyntaxError, OSError):
            continue        # `tei validate`'s finding, not this index's
        for ms in tree.iter(_MS):
            if ms.get("n"):
                out.setdefault(ms.get("n"), []).append(
                    {"ref": norm_ref(ref), "shared": bool(_BEFORE(ms))})
    return out


def _in_toc(root: Path) -> list[dict]:
    """The ToC's chapters, in the ToC's order."""
    return [e for e in load_toc(root) if e.get("level") == LEVEL and e.get("id")]


def _title(e: dict) -> str:
    number = e.get("number") or ""
    return f"{number}. {e.get('title') or ''}" if number else e.get("title", "")


# ------------------------------------------------------------ readable addresses

#: Deleted outright rather than turned into a separator: combining marks, spacing
#: modifiers, and the two apostrophes. `Ke'let` is one word, and `Taˊn˙ñɪn` too.
_DROP_CATS = frozenset({"Mn", "Lm", "Sk"})
_DROP_CHARS = frozenset({"'", "’"})
_WORD = re.compile(r"[^\W_]+")


def slugify(text: str) -> str:
    """A title as an address: `Taˊn˙ñɪn Wars` -> `tannɪn-wars`.

    NFD and lowercase, the marks and apostrophes deleted, and every run of what is
    not a letter or a digit one `-`. A base letter outside ASCII survives.

    **An address, not a reading.** It asserts no glyph, and a Tier-1 form with its
    marks stripped is not a form, so a slug is never displayed as text. It is one
    rule for every readable address, the chapter's path and a heading's fragment
    alike, so the two cannot drift apart.
    """
    s = unicodedata.normalize("NFD", text).lower()
    s = "".join(c for c in s
                if c not in _DROP_CHARS and unicodedata.category(c) not in _DROP_CATS)
    return "-".join(_WORD.findall(s))


def _parts(entry: dict) -> tuple[str, ...]:
    return tuple(p for p in ((entry.get("chapter") or "").lower(),
                             slugify(entry.get("title") or "")) if p)


def slug(entry: dict) -> str:
    """A chapter's path under `/chapter/`, `xii/religious-ideas`: its roman, then
    its title.

    **The roman is a segment of its own**, so `/chapter/xii` is the chapter by
    number, and the half that does not move: `toc.json` is amended apparatus, so
    the title can change under a link, and the route resolves on the roman and
    sends any other spelling to this one.
    """
    return "/".join(_parts(entry))


def heading(entry: dict) -> str:
    """A chapter heading's fragment, `xii-religious-ideas`: the path's two
    segments, joined as a fragment joins them. The roman keeps it apart from
    every section's."""
    return "-".join(_parts(entry))


def url(entry: dict) -> str:
    """Where a chapter is served, under the reading view's mount. A path, as
    `apparatus.locate`'s are; the caller prefixes the mount."""
    return f"/chapter/{slug(entry)}"


def _parents(toc: list[dict]) -> dict[str, str]:
    """`{id: parent id}`: the nearest preceding entry at a lower level, with level
    0 folded as 1 — the outline's own fold, as `_toc_tree` and `toc_containing`
    do it. Top-level entries have no row."""
    out: dict[str, str] = {}
    stack: list[tuple[int, str]] = []
    for e in toc:
        if not e.get("id"):
            continue
        depth = max(e.get("level") or 0, 1)
        while stack and stack[-1][0] >= depth:
            stack.pop()
        if stack:
            out[e["id"]] = stack[-1][1]
        stack.append((depth, e["id"]))
    return out


def fragments(toc: list[dict]) -> tuple[dict[str, str], list[dict]]:
    """`({toc id: fragment}, collisions)` — the id each heading carries in the HTML.

    A chapter's fragment is its `heading`, and anything else's is its title's. **Unique
    across the whole ToC**, because a chapter page renders its neighbour's tail and
    `/page/` renders whatever heads a leaf holds, so any two of them can share a
    document.

    **A collision is resolved by structure, never by order.** Every entry of a
    colliding group climbs one ancestor together, prefixing that ancestor's own
    title slug — and a chapter's carries its roman, so twins in two chapters always
    part. The rounds repeat over the whole map, so a qualified fragment that lands
    on another entry's is a collision too. What still collides once it has no
    ancestor left keeps its toc id, which no slug can equal, and is reported: two
    headings given one address by a tie-break would look exactly like one that
    had a single home.
    """
    entries = [e for e in toc if e.get("id")]
    parents = _parents(entries)
    base = {e["id"]: (heading(e) if e.get("level") == LEVEL
                      else slugify(e.get("title") or "")) for e in entries}
    climbed = {i: i for i in base}     # the furthest ancestor prefixed so far
    frag = {i: b for i, b in base.items() if b}
    stuck: set[str] = set(base) - set(frag)
    # Terminates: every round that goes on moves at least one entry one level up.
    while True:
        groups: dict[str, list[str]] = {}
        for i, f in frag.items():
            groups.setdefault(f, []).append(i)
        clash = [ids for ids in groups.values() if len(ids) > 1]
        moved = False
        for ids in clash:
            for i in ids:
                up = parents.get(climbed[i])
                if up is not None:
                    climbed[i] = up
                    frag[i] = "-".join(p for p in (base[up], frag[i]) if p)
                    moved = True
        if not moved:
            stuck |= {i for ids in clash for i in ids}
            break
    collisions = []
    for i in sorted(stuck, key=list(base).index):
        frag[i] = i
        collisions.append({
            "toc_id": i,
            "detail": (f"title {base[i]!r} is also another heading's, with every "
                       "ancestor prefixed" if base[i] else "no title to slug")})
    return frag, collisions


def neighbours(root: Path, cid: str) -> tuple[dict | None, dict | None]:
    """The chapters the ToC sets either side of this one, each `{id, title, url,
    heading}`, the last its heading's fragment.

    **The ToC's and not the next run's**, and a neighbour may have no run: the list
    of derived chapters closes over a gap, so its neighbour would be a chapter
    further off, and its title would go on text that is not its own.
    """
    order = [{"id": e["id"], "title": _title(e), "url": url(e), "heading": heading(e)}
             for e in _in_toc(Path(root))]
    at = next(i for i, e in enumerate(order) if e["id"] == cid)
    return (order[at - 1] if at > 0 else None,
            order[at + 1] if at + 1 < len(order) else None)


def derive(root: Path = Path(".")) -> tuple[list[dict], list[dict]]:
    """`(runs, problems)` — one run per chapter whose span the text settles.

    Each run is shaped as a declared one (`id`, `kind`, `title`, `refs`) and
    carries what only a chapter has:

        toc_id        the ToC entry it is, which is also its id
        slug          its path under `/chapter/` (`slug`), `xii/religious-ideas`
        head_shared   its first leaf opens with the previous chapter's tail
        tail_shared   its last leaf goes on into the next chapter

    `problems` is one row per chapter left underived, and why. It is the gate's
    to report; the view serves those pages one at a time.
    """
    root = Path(root)
    chapters = _in_toc(root)
    sources = _sources(root)
    found = milestones(root, sources)
    # The last leaf of each part that holds any text. The last chapter of a part
    # ends there: what follows it is the binding's (blanks, the back cover), and a
    # chapter claiming those would be claiming leaves nothing places in it.
    last: dict[int, int] = {}
    for ref in sources:
        part, idx = parse_ref(ref)
        last[part] = max(last.get(part, 0), idx)

    def one(e: dict) -> tuple[dict | None, str]:
        occ = found.get(e["id"]) or []
        if not occ:
            return None, "no milestone opens it anywhere in the text"
        if len(occ) > 1:
            return None, ("opened on " + ", ".join(o["ref"] for o in occ)
                          + "; a chapter opens once")
        return occ[0], ""

    runs: list[dict] = []
    problems: list[dict] = []
    for k, e in enumerate(chapters):
        head, why = one(e)
        if head is None:
            problems.append({"chapter": e["id"], "rule": "no-opener", "detail": why})
            continue
        part, start = parse_ref(head["ref"])
        end, tail_shared = last.get(part, start), False
        nxt = chapters[k + 1] if k + 1 < len(chapters) else None
        if nxt is not None:
            succ, why = one(nxt)
            if succ is None:
                problems.append({
                    "chapter": e["id"], "rule": "no-end",
                    "detail": f"ends where {nxt['id']} opens, and {nxt['id']} {why}"})
                continue
            npart, nidx = parse_ref(succ["ref"])
            if (npart, nidx) < (part, start):
                problems.append({
                    "chapter": e["id"], "rule": "out-of-order",
                    "detail": f"opens on {head['ref']}, after {nxt['id']} on "
                              f"{succ['ref']}, which the ToC sets after it"})
                continue
            if npart == part:
                tail_shared = succ["shared"]
                end = nidx if tail_shared else nidx - 1
                if end < start:
                    problems.append({
                        "chapter": e["id"], "rule": "no-text",
                        "detail": f"opens on {head['ref']} with {nxt['id']} straight "
                                  "after it, so no text is this chapter's"})
                    continue
        runs.append({
            "id": e["id"],
            "kind": KIND,
            "title": _title(e),
            "refs": [f"{part}-{i:03d}" for i in range(start, end + 1)],
            "toc_id": e["id"],
            "slug": slug(e),
            "head_shared": head["shared"],
            "tail_shared": tail_shared,
        })
    return runs, problems


def runs(root: Path = Path(".")) -> list[dict]:
    """The derived chapter runs, without the problems."""
    return derive(root)[0]


def watched(root: Path = Path(".")) -> list[Path]:
    """The files a chapter span is a function of, for a cache key: the ToC and
    every page the edition could render."""
    root = Path(root)
    return ([root / "edition" / "toc.json"]
            + sorted(page_files(root / "tei", ".xml", root))
            + sorted(page_files(root / "mz" / "tei", ".xml", root)))
