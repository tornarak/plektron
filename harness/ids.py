"""Structural ids for page files: `{kind}-{PP-NNN}-{ordinal}`.

`term-1-100-4`, `list-1-100-1`. Three properties, each load-bearing:

- **The kind prefix is required**, not decorative. An XML Name cannot begin with
  a digit, so a bare `1-100-4` is illegal.
- **The ref is embedded and zero-padded to three.** Ref-scoping makes collision
  impossible when 832 pages assemble into one document, and the mandatory padding
  is what lets the hyphenated form be parsed back apart unambiguously — so it is a
  gate rule rather than a convention.
- **All-ASCII by construction**, so corpus-wide NFD never touches an id. Worth
  saying out loud in a project where every other string carries an encoding rule.

**The ordinal is a position, not a counter.** It is the element's 1-based index
among *all* same-kind elements on the page in document order, whether or not that
element carries an id. Ids are therefore sparse, and that is deliberate: under a
counter, minting an id for the second `<term>` would renumber the seventh and move
an id something already points at. As a position, every id is verifiable by
counting the tree and by nothing else — a total function of the file, checkable
against no other file.

Consequence to state wherever this is documented, because a real page walks into
it: **the ordinal is not the printed item number.** `1-100`'s item 4 holds two
`<term>`s, so its terms are `term-1-100-4` and `term-1-100-5` and item 5's term is
`term-1-100-6`.

**The kind set is exactly the elements something can point at** — `term` (by a
`<gloss target>`), `list` and `table` (by a seam's `@prev`/`@next`). Not `gloss`:
nothing references one. Not `note`, until a note running across a page seam is
actually attested. A kind no referrer can name is dead surface in the gate, so
this is "no id without a referrer" applied one level up, to the kinds themselves.

**Scope.** These ids are stable within a page file's current version and nothing
outside the corpus may cite one: ordinals move when content is inserted, so any
pointer held externally would break silently. Intra-page pointers (gloss→term) and
seam pointers (list↔list across one gap) are safe because pointer and target move
together, inside one file or one adjacent pair. Corpus-stable identity for an
external index is a separate scheme and is not this one.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from lxml import etree

from .context import norm_ref

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"

KINDS = ("term", "list", "table")
ID_RE = re.compile(r"^(term|list|table)-(\d+)-(\d{3})-(\d+)$")
# Attributes that name an id. `target` resolves inside the page; `prev`/`next`
# resolve into the adjacent one.
IN_FILE_POINTERS = ("target",)
CROSS_FILE_POINTERS = ("prev", "next")


def localname(el) -> str:
    return etree.QName(el).localname


def parse_id(value: str) -> dict | None:
    """`term-1-100-4` -> {kind, ref, ordinal}, or None if it is not of the scheme."""
    m = ID_RE.match(value or "")
    if not m:
        return None
    kind, part, idx, ordinal = m.groups()
    return {"kind": kind, "ref": f"{int(part)}-{idx}", "ordinal": int(ordinal)}


def canonical_map(root_el, ref: str) -> dict:
    """Every id-bearing-capable element on the page -> the id it must have.

    Keyed by the element object. Covers elements whether or not they carry an id,
    because the ordinal is a position among all of them.
    """
    ref = norm_ref(ref)
    seen = Counter()
    out = {}
    for el in root_el.iter():
        if not isinstance(el.tag, str):
            continue
        name = localname(el)
        if name in KINDS:
            seen[name] += 1
            out[el] = f"{name}-{ref}-{seen[name]}"
    return out


def ids_in(root_el) -> dict:
    """Every `xml:id` on the page -> its element."""
    return {el.get(XML_ID): el for el in root_el.iter()
            if isinstance(el.tag, str) and el.get(XML_ID)}


def pointers_in(root_el, attrs=IN_FILE_POINTERS + CROSS_FILE_POINTERS) -> list:
    """Every id-naming attribute on the page, as {element, attr, id}.

    `@target` and friends are space-separated URI lists in TEI, so a single
    attribute can name several ids and each is reported separately.
    """
    out = []
    for el in root_el.iter():
        if not isinstance(el.tag, str):
            continue
        for attr in attrs:
            value = el.get(attr)
            if value is None:
                continue
            for tok in value.split():
                out.append({"el": el, "attr": attr, "id": tok.lstrip("#")})
    return out


def referenced_ids(root_el, attrs=IN_FILE_POINTERS + CROSS_FILE_POINTERS) -> set:
    return {p["id"] for p in pointers_in(root_el, attrs)}


def renumber(root_el, ref: str) -> dict:
    """Rewrite this page's ids to canonical form. Returns {old: new}, changed only.

    Mutates the tree: every `xml:id` that is not what its position says it should
    be, plus every in-file pointer at one. Cross-file pointers into this page are
    *not* handled here — they live in another file, and silently leaving one
    dangling is the failure this whole scheme is checked against, so the caller
    (`fix_page`) resolves them explicitly.
    """
    canonical = canonical_map(root_el, ref)
    moves = {}
    for el, want in canonical.items():
        have = el.get(XML_ID)
        if have and have != want:
            moves[have] = want
    if not moves:
        return {}
    for el, want in canonical.items():
        if el.get(XML_ID):
            el.set(XML_ID, want)
    for p in pointers_in(root_el):
        if p["id"] in moves:
            el, attr = p["el"], p["attr"]
            el.set(attr, " ".join(
                f"#{moves.get(t.lstrip('#'), t.lstrip('#'))}"
                for t in el.get(attr).split()))
    return moves


def pair_glosses(ref: str, root: Path = Path("."), commit: bool = False) -> dict:
    """Link each `<gloss>` to the `<term>` it glosses, where containment decides.

    Containment is the association *only* where a container holds exactly one of
    each. `1-100`'s item 4 holds two `<term>`/`<gloss>` pairs, and choosing which
    gloss belongs to which term there would be inference — the thing this project
    refuses — so those are reported for a human and nothing is written. Same shape
    as `proposal-check --fix`: repair the unambiguous case, report the rest.

    Which is also why this is a convenience and not the authority. The collating
    pass writes `@target` as it goes, because it knows the pairing from the page;
    this exists to retrofit pages written before the scheme, and to save 30 hand
    edits on a file whose Tier-1 spans must not be retyped.
    """
    from .seam import tei_path, _save

    ref = norm_ref(ref)
    path = tei_path(ref, root)
    if not path.exists():
        raise ValueError(f"no TEI for {ref} at {path}")
    tree = etree.parse(str(path))
    canonical = canonical_map(tree.getroot(), ref)
    out = {"ref": ref, "paired": [], "ambiguous": [], "committed": commit}

    # Keyed by the element, never by `id(element)`. lxml builds proxy objects on
    # demand and frees them when nothing holds a reference, so an integer id is
    # reused by a later element and a set of them silently collapses distinct
    # nodes. That is not hypothetical: the first version of this loop paired 5 of
    # 14 items and reported success. A dict keyed by the element both hashes by
    # identity and keeps the proxy alive.
    seen = {}
    for gloss in tree.getroot().iter(f"{{{TEI_NS}}}gloss"):
        parent = gloss.getparent()
        if parent is None or parent in seen:
            continue
        seen[parent] = True
        terms = [e for e in parent.iter(f"{{{TEI_NS}}}term")]
        glosses = [e for e in parent.iter(f"{{{TEI_NS}}}gloss")]
        where = parent.get("n") or localname(parent)
        if len(terms) != 1 or len(glosses) != 1:
            out["ambiguous"].append({
                "container": localname(parent), "n": where,
                "terms": len(terms), "glosses": len(glosses),
                "why": "containment does not decide which gloss belongs to which "
                       "term; the collating pass writes @target here by hand"})
            continue
        term, gl = terms[0], glosses[0]
        ident = canonical[term]
        term.set(XML_ID, ident)
        gl.set("target", f"#{ident}")
        out["paired"].append({"n": where, "id": ident})

    if commit and out["paired"]:
        _save(tree, path)
    return out


def fix_page(ref: str, root: Path = Path("."), commit: bool = False) -> dict:
    """Renumber one page, repairing inbound pointers from its neighbours.

    A `list-1-100-1` may be the target of `1-101`'s `@prev`. Renumbering within one
    file would leave that pointer naming an id that no longer exists — a dangling
    reference with no error signal, which is precisely what this project is
    organised against. So both neighbours are read, and either repaired in the same
    write or named in `blocked` if this is a preview.
    """
    from .seam import tei_path, prev_ref, next_ref, _save

    ref = norm_ref(ref)
    path = tei_path(ref, root)
    if not path.exists():
        raise ValueError(f"no TEI for {ref} at {path}")
    tree = etree.parse(str(path))
    moves = renumber(tree.getroot(), ref)
    out = {"ref": ref, "moves": [{"from": k, "to": v} for k, v in moves.items()],
           "neighbours": [], "committed": commit}
    if not moves:
        return out

    for nref in (prev_ref(ref), next_ref(ref)):
        if not nref:
            continue
        npath = tei_path(nref, root)
        if not npath.exists():
            continue
        ntree = etree.parse(str(npath))
        touched = 0
        for p in pointers_in(ntree.getroot(), CROSS_FILE_POINTERS):
            if p["id"] in moves:
                el, attr = p["el"], p["attr"]
                el.set(attr, " ".join(
                    f"#{moves.get(t.lstrip('#'), t.lstrip('#'))}"
                    for t in el.get(attr).split()))
                touched += 1
        if touched:
            out["neighbours"].append({"ref": nref, "pointers": touched})
            if commit:
                _save(ntree, npath)
    if commit:
        _save(tree, path)
    return out
