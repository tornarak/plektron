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

# A run-on list could in principle chain across a whole chapter. The cap is a
# runaway guard, not a limit anyone should hit: it also terminates a corpus whose
# @prev pointers form a cycle, which validate cannot see because it only ever
# checks one hop.
SCOPE_HOPS = 16


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


def text_of(el) -> str:
    """The element's running text, with `<note>` subtrees removed.

    A footnote is anchored *inside* the text it belongs to but is not part of it,
    so a bare `itertext()` walks into it: `1-100`'s `<gloss>` for `Ilhɪ-lileˊ`
    came back as `“white-eyed” [albino]` followed by the whole note on albino
    reindeer, which in a glossary reads as the definition.

    Removing the element is not enough — lxml's `remove()` takes its `.tail` with
    it, and a note is anchored mid-text far more often than at the end, so the
    naive version silently truncates everything after the marker. Both halves of
    this were learned once already, on `seam.tail`, which is why there is one
    implementation and two callers.
    """
    # with_tail=False, or the serialization carries the text *following* the
    # element and re-parsing it fails as "extra content at the end of the
    # document". Every <gloss> in a gloss list is followed by `).`, so this is the
    # normal case on a real page and the absent one in a hand-written fixture.
    copy = etree.fromstring(etree.tostring(el, with_tail=False))
    for note in list(copy.iter(f"{{{TEI_NS}}}note")):
        parent = note.getparent()
        if note.tail:
            prev = note.getprevious()
            if prev is not None:
                prev.tail = (prev.tail or "") + note.tail
            else:
                parent.text = (parent.text or "") + note.tail
        parent.remove(note)
    return " ".join("".join(copy.itertext()).split())


def _head_of(list_el) -> tuple[str, bool] | None:
    """A list's `<head>` as (text, wholly_supplied), or None if it has none.

    "Wholly supplied" means no non-whitespace text anywhere in the head outside a
    `<supplied>` — which is why this checks `head.text` and every child's `.tail`
    and not merely that the children are all `<supplied>`. A head reading
    `<supplied>of a reindeer</supplied>, roughly` is part editorial and part
    something else, and reporting it as wholly supplied would misstate provenance
    in the one field that exists to state it.
    """
    for ch in list_el:
        if not isinstance(ch.tag, str) or ch.tag != f"{{{TEI_NS}}}head":
            continue
        loose = (ch.text or "") + "".join(g.tail or "" for g in ch)
        supplied = (not loose.strip()
                    and len(ch) > 0
                    and all(isinstance(g.tag, str)
                            and g.tag == f"{{{TEI_NS}}}supplied" for g in ch))
        return text_of(ch), supplied
    return None


def list_scope(el, ref: str, root: Path = Path("."),
               cache: dict | None = None) -> tuple[str, bool]:
    """The frame a glossed term inherits from the list it sits in.

    A gloss list whose entries share a frame does not repeat it per entry — the
    frame is stated once by the prose introducing the list, and `Qeˊñu` glossed
    "white mixed with brown" means nothing without it. So the frame is written once
    as a supplied `<head>` and resolved here, rather than duplicated into every
    gloss. See the collation skill, "Glosses, and linking them to their terms".

    Two resolutions, in order:

    - **Up the ancestor lists, innermost first.** A sub-entry list nested in an
      `<item>` normally carries no head of its own and inherits its parent's.
    - **Across the seam, via `@prev`.** A list running onto the next page is the
      same list and carries no second head, so the continuation resolves back
      through the link `harness seam` wrote. This is the only place in the harness
      that *traverses* those pointers rather than checking one hop of them.

    The target page comes from the id itself (`parse_id(prev)["ref"]`) rather than
    from `prev_ref(ref)`. The two must agree and `validate` enforces it, so reading
    the id means a corpus that has drifted resolves to nothing instead of quietly
    resolving to the wrong page.

    Returns `("", False)` when nothing supplies a frame, which is the ordinary case
    for a self-sufficient list.
    """
    from .seam import tei_path

    cache = {} if cache is None else cache
    lists, node = [], el
    while node is not None:
        if isinstance(node.tag, str) and localname(node) == "list":
            lists.append(node)
        node = node.getparent()
    if not lists:
        return "", False

    for lst in lists:                      # innermost first
        got = _head_of(lst)
        if got is not None:
            return got

    seen, cur, hops = set(), lists[-1], 0
    while hops < SCOPE_HOPS:
        hops += 1
        prev = (cur.get("prev") or "").lstrip("#")
        if not prev or prev in seen:
            break
        seen.add(prev)
        parsed = parse_id(prev)
        if parsed is None:
            break
        pref = parsed["ref"]
        if pref not in cache:
            path = tei_path(pref, root)
            try:
                cache[pref] = etree.parse(str(path)).getroot()
            except (etree.XMLSyntaxError, OSError):
                cache[pref] = None
        if cache[pref] is None:
            break
        cur = ids_in(cache[pref]).get(prev)
        if cur is None:
            break
        got = _head_of(cur)
        if got is not None:
            return got
    return "", False


def page_glossary(root_el, ref: str, root: Path = Path("."),
                  cache: dict | None = None) -> dict:
    """Resolved term↔gloss pairs on one page, plus what is *not* resolved.

    Pairs come from `@target` and from nothing else. Falling back to containment
    here would re-introduce the inference `pair_glosses` refuses — and worse,
    silently, in a report someone would read as the corpus's dictionary.

    So unlinked terms are counted rather than guessed at. A page collated before
    the scheme, or an item whose pairing a human has not written yet, shows up as
    a number instead of vanishing: the gap in the dictionary is visible in the
    dictionary, which is the only place anyone would look for it.
    """
    by_id = ids_in(root_el)
    linked, seen_terms = [], set()
    for gl in root_el.iter(f"{{{TEI_NS}}}gloss"):
        target = (gl.get("target") or "").lstrip("#")
        term = by_id.get(target)
        if term is None or localname(term) != "term":
            continue
        seen_terms.add(target)
        scope, scope_supplied = list_scope(gl, ref, root, cache)
        linked.append({
            "term": text_of(term),
            "lang": term.get("{http://www.w3.org/XML/1998/namespace}lang") or "",
            "gloss": text_of(gl),
            "supplied": gl.get("type") == "supplied",
            "scope": scope,
            "scope_supplied": scope_supplied,
            "ref": norm_ref(ref),
        })
    unlinked = sum(1 for t in root_el.iter(f"{{{TEI_NS}}}term")
                   if t.get(XML_ID) not in seen_terms)
    return {"pairs": linked, "unlinked_terms": unlinked}


def glossary(root: Path = Path(".")) -> dict:
    """Every resolved term↔gloss pair in the committed TEI, corpus-wide."""
    from .context import all_refs, norm_ref as _n
    from .seam import tei_path

    # One cache across the whole sweep, so a run-on list resolving its scope back
    # through @prev reuses the page this loop has already parsed rather than
    # reading it again per gloss.
    pairs, unlinked, pages, cache = [], 0, 0, {}
    for p in sorted((root / "tei").glob("chukchi-*.xml")):
        try:
            ref = _n(p.stem)
        except ValueError:
            continue
        try:
            tree = etree.parse(str(p))
        except (etree.XMLSyntaxError, OSError):
            continue
        cache[ref] = tree.getroot()
        got = page_glossary(tree.getroot(), ref, root, cache)
        pairs += got["pairs"]
        unlinked += got["unlinked_terms"]
        pages += 1
    return {"pages": pages, "pairs": pairs,
            # Not a defect on its own — a page may simply carry no gloss list —
            # but a rising count means terms are being written without their
            # glosses being linked, which is invisible in any per-page view.
            "unlinked_terms": unlinked}


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
