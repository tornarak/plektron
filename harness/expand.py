"""Verify a collated page's Tier-1 forms against ground truth and stamp the rank.

A ratified term arrives as `<foreign xml:lang="ckt" index="7">Uweˊlen</foreign>`:
the generator put the adjudicated string there, straight out of `gt/ocr/`, and the
reviewer added the language. This checks the string still is what `tier1_terms`
says and rewrites `@resp` to `#gt`. The model's judgement is *which* token and
what language; the glyphs are never its to originate.

**It used to fill an empty handle**, and refused one that already held text. That
was right when the collation pass authored the page from a plaintext draft — a
model that never typed the glyphs could not corrupt them. Once the generator
began writing the file, the copy was already being made by a rule, and the
emptiness bought nothing while costing the reviewer a lookup from `index="7"` to
`tier1_terms[7]` before it could judge the language of a word it could not see.
So the text comes in with the file and this became the check rather than the
copy. An empty handle is still accepted and still filled: a page authored under
the old contract, or a span a reviewer wrapped by hand, both land here.

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

import unicodedata
from pathlib import Path

from lxml import etree

from .context import norm_ref, tier1_terms
from .ns import XML_LANG
from .validate import ADOPTED, TIER1


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

    # `keys=False`: `index` and `text` are what this reads. The `key` column
    # costs a walk of every keyed page and nothing here would look at it.
    terms = {str(t["index"]): t for t in tier1_terms(ref, root, keys=False)}
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
        elif held and unicodedata.normalize("NFD", held) != \
                unicodedata.normalize("NFD", got["text"]):
            # The span says one thing and the ground truth says another. Never a
            # thing to fix silently: either the reviewer edited glyphs it may not
            # edit, or the wrap moved and `@index` now points at a different
            # token. Both want a reader, and overwriting would erase the evidence
            # of which it was.
            reason = (f"holds {held[:24]!r} but term {idx} is "
                      f"{got['text'][:24]!r} — the span was edited, or @index "
                      f"points at the wrong token")
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
