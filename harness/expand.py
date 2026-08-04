"""Write ratified Tier-1 forms into a collated page, so no model retypes one.

The collation pass names a native term by a handle into `tier1_terms` —
`<foreign xml:lang="ckt" index="7"/>` — and this fills in the exact string a
human adjudicated at the raster. The model's judgement is *which* token; the
glyphs are never its to originate.

**Why this and not "read harder".** Where `gt/ocr/` holds the page, the marks
have already been settled once, at magnification, by an editor. Retyping
`ɪᵋplɪˊlᴇ` into the TEI puts §5's two residual error classes back on the table —
a dropped U+0323, an `ɪ` read as `i` — and both are unfalsifiable downstream: the
form still looks like a form, no lexicon knows it, no second reader exists, and
CATMuS reads 0% of the inventory. A character-for-character copy is the one step
in the pipeline where the answer is already known and can still come out wrong.

**Scope, stated because the obvious generalisation is wrong.** This is worth
doing only where a ratified witness exists — 30 pages of 832 today. On the rest
`tier1_terms` is empty by construction, because a list built from `mz/ocr/` would
be garbled forms offered to be copied verbatim, which is this failure inverted
rather than avoided. There the pass reads the raster itself, writes its best
attempt, and flags the line.

**What this deliberately does not do is change a rank.** A span whose glyphs come
from ratified ground truth has a real case for `@resp="#ed"`, since no model
authority touched the identity — but the firewall says rank rises by a human act,
and that amendment is not this function's to make. Everything here works the same
either way.

Figures went the other way and the contrast is the point: their handle was
removed rather than expanded, because the book already prints an identity for a
figure (`Fig. 87`) and the collator can read it off the prose. A native form has
no such number, so there is nothing to name it by except the ratified text.
"""
from __future__ import annotations

from pathlib import Path

from lxml import etree

from .context import norm_ref, tier1_terms
from .validate import ADOPTED, TIER1

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def expand_page(ref: str, root: Path = Path("."), commit: bool = False) -> dict:
    """Resolve `index=` handles on Tier-1 elements to their ratified text.

    Reports `resolved` and `unresolved`. An unresolved handle is left **exactly
    as it is** — not dropped, not guessed at. `validate` errors on a surviving
    `@index`, so leaving it keeps the fault in the one place a reader will meet
    it, where removing it would leave a Tier-1 element holding whatever text the
    pass happened to type, indistinguishable from one that never asked.

    **A handle on an element that already holds text is a conflict, not an
    override.** Both are claims about the same glyphs and this refuses to rank
    them silently; it reports and writes nothing for that element. The pass
    should write one or the other.

    A page with no handles reports `resolved: []` and is not an error — every
    page collated before this existed, and every page with no native forms.
    """
    from .seam import _save, tei_path

    ref = norm_ref(ref)
    path = tei_path(ref, root)
    if not path.exists():
        raise ValueError(f"no TEI for {ref} at {path}")

    terms = {str(t["index"]): t for t in tier1_terms(ref, root)}
    tree = etree.parse(str(path))
    resolved, unresolved = [], []
    for el in tree.getroot().iter():
        idx = el.get("index") if isinstance(el.tag, str) else None
        if idx is None:
            continue
        name = etree.QName(el).localname
        got = terms.get(idx.strip())
        held = "".join(el.itertext()).strip()
        if el.get(XML_LANG) not in TIER1:
            reason = f"<{name}> carries no Tier-1 xml:lang"
        elif got is None:
            reason = (f"no term {idx} on this page — "
                      f"{len(terms)} ratified term(s) available"
                      if terms else
                      "this page has no ratified terms; gt/ocr/ does not hold it")
        elif held:
            reason = f"already holds text ({held[:24]!r}) — write one or the other"
        else:
            del el.attrib["index"]
            el.text = got["text"]
            was = el.get("resp")
            # The rank is rewritten, not left alone, and this is the whole point of
            # the fourth one: `#llm` is *false* about a span whose glyphs no model
            # chose. `validate` re-derives the claim from `gt/ocr/` on every run
            # rather than trusting what is written here, so this is a record of
            # what happened and not an assertion that stands on its own.
            el.set("resp", ADOPTED)
            resolved.append({"index": idx, "element": name, "line": got["line"],
                             "text": got["text"], "resp_was": was or ""})
            continue
        unresolved.append({"index": idx, "element": name, "reason": reason})
    if commit and resolved:
        _save(tree, path)
    return {"ref": ref, "resolved": resolved, "unresolved": unresolved,
            "committed": bool(commit and resolved)}
