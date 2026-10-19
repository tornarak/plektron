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

from pathlib import Path

from lxml import etree

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


def derive(root: Path = Path(".")) -> tuple[list[dict], list[dict]]:
    """`(runs, problems)` — one run per chapter whose span the text settles.

    Each run is shaped as a declared one (`id`, `kind`, `title`, `refs`) and
    carries what only a chapter has:

        toc_id        the ToC entry it is, which is also its id
        head_shared   its first leaf opens with the previous chapter's tail
        tail_shared   its last leaf goes on into the next chapter

    `problems` is one row per chapter left underived, and why. It is the gate's
    to report; the view serves those pages one at a time.
    """
    root = Path(root)
    chapters = [e for e in load_toc(root) if e.get("level") == LEVEL and e.get("id")]
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
        number = e.get("number") or ""
        runs.append({
            "id": e["id"],
            "kind": KIND,
            "title": f"{number}. {e.get('title') or ''}" if number else e.get("title", ""),
            "refs": [f"{part}-{i:03d}" for i in range(start, end + 1)],
            "toc_id": e["id"],
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
            + sorted((root / "tei").glob("chukchi-*.xml"))
            + sorted((root / "mz" / "tei").glob("chukchi-*.xml")))
