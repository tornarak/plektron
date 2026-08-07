"""Page seams: which element runs across the gap, recorded in the TEI itself.

A gap has one fact — is the element spanning it open or not — and that fact lands
on two elements, one on each side. The page *after* the gap is the only place both
witnesses are available: it carries the previous page's tail in its context, it can
see its own first line's indent, and it holds the text that either opens
mid-sentence or does not. So it writes both ends, and nothing else ever does.

**There is no seam sidecar.** The committed TEI is the record. `@part` on the two
elements *is* the stored fact, not a materialization of one kept elsewhere, and the
I/M/F arithmetic reads back out of the files it wrote to. A second store would be a
second thing to drift.

`@part` is two independent bits — does this element begin before this page, does it
end after it — and TEI spells the four combinations as nothing / I / M / F:

    begins here, ends here      no @part
    begins here, runs past      I   (initial fragment)
    began earlier, ends here    F   (final fragment)
    began earlier, runs past    M   (medial fragment)

Declaring a gap open sets one bit on each side: the following page's first element
gains "began earlier", the preceding page's last element gains "runs past". Each
leaves the other bit alone, which is what makes the operation order-independent —
a page whose first element already carries `I` (its own successor having declared
the next gap open) becomes `M` rather than being overwritten to `F`. The same
mechanism handles a verdict that changes later: flip the bit back and the element
returns to exactly the state the other gap left it in.
"""
from __future__ import annotations

from pathlib import Path

from lxml import etree

from .context import parse_ref, stem_for

TEI_NS = "http://www.tei-c.org/ns/1.0"


def tei_path(ref: str, root: Path = Path(".")) -> Path:
    return root / "tei" / f"{stem_for(ref, root)}.xml"

# TEI att.fragmentable — the elements @part is defined on. <list> and <table> are
# deliberately absent from TEI's class and so cannot carry it: a list running across
# a page break needs prev/next pointers and therefore xml:ids, which is a separate
# unsettled decision. Reported rather than guessed at.
FRAGMENTABLE = {"p", "quote", "ab", "l", "lg", "sp"}

# The elements TEI leaves out of att.fragmentable but which do run across a page
# break in this book. They carry the same single fact as `@part`, spelled as a
# `@prev`/`@next` pair — which needs ids, which is why the id scheme and this
# branch landed together.
LINKABLE = {"list", "table"}

# bit pair -> @part value. (begins_before, runs_past)
PART_OF_BITS = {(False, False): None, (True, False): "F",
                (False, True): "I", (True, True): "M"}
BITS_OF_PART = {v: k for k, v in PART_OF_BITS.items() if v}


def _q(tag: str) -> str:
    return f"{{{TEI_NS}}}{tag}"


def body_elements(root) -> list:
    """Top-level content elements of <body>, in document order.

    <pb> and <milestone> are excluded: they are points in the text, not containers,
    so nothing spans a page boundary *as* one of them. Comments and PIs likewise.
    """
    body = root.find(f".//{_q('body')}")
    if body is None:
        return []
    skip = {_q("pb"), _q("milestone")}
    return [el for el in body
            if isinstance(el.tag, str) and el.tag not in skip]


def bits(el) -> tuple[bool, bool]:
    return BITS_OF_PART.get(el.get("part"), (False, False))


def _apply(el, *, begins_before=None, runs_past=None) -> str | None:
    b, r = bits(el)
    if begins_before is not None:
        b = begins_before
    if runs_past is not None:
        r = runs_past
    value = PART_OF_BITS[(b, r)]
    if value is None:
        el.attrib.pop("part", None)
    else:
        el.set("part", value)
    return value


def prev_ref(ref: str) -> str | None:
    """The preceding scan in the same part. Gaps never cross a part boundary."""
    part, idx = parse_ref(ref)
    return f"{part}-{idx - 1:03d}" if idx > 1 else None


def next_ref(ref: str) -> str:
    """The following scan in the same part.

    No upper bound is checked here: a part's last scan has no successor *file*,
    which every caller discovers by the path not existing. Encoding the per-part
    maxima (362/268/202) in a second place would be one more fact to drift.
    """
    part, idx = parse_ref(ref)
    return f"{part}-{idx + 1:03d}"


def _load(path: Path):
    return etree.parse(str(path))


def _save(tree, path: Path) -> None:
    text = etree.tostring(tree, encoding="unicode", xml_declaration=False)
    head = '<?xml version="1.0" encoding="UTF-8"?>\n'
    path.write_text(head + text.rstrip("\n") + "\n", encoding="utf-8")


# Soft cap on the serialized tail. Elision drops whole leading children, so the
# fragment stays well-formed and a single oversized trailing child may exceed it.
TAIL_CHARS = 600


def _running_text(el) -> str:
    """The element's text with `<note>` subtrees removed — see `ids.text_of`.

    A footnote is anchored inside the running text but is not part of it, so
    leaving it in would put the note's last sentence at the end of the tail and
    make `ends_sentence` describe the wrong thing entirely.
    """
    from .ids import text_of
    return text_of(el)


def _ser(el) -> str:
    return etree.tostring(el, encoding="unicode")


def _fragment(el, cap: int = TAIL_CHARS) -> tuple[str, int]:
    """The element as XML, trimmed from the front, still well-formed.

    Markup, not a text excerpt, because the markup carries the witnesses. A
    flattened tail loses `<item n="14">` — which is precisely what settles whether
    the list resuming at 15 on the next page is the same list — along with every
    `xml:lang`/`@resp` on the Tier-1 spans in play at the seam, and any `@part`
    already recorded on a nested element.

    Trimming drops whole leading children rather than slicing characters, so the
    result is always parseable and the elision is stated rather than implied. A
    single oversized trailing child can therefore exceed the cap; that is the
    right trade, since a fragment cut mid-element would have to be repaired by
    whatever read it.
    """
    copy = etree.fromstring(etree.tostring(el))
    copy.tail = None
    elided = 0
    while len(copy) and len(_ser(copy)) > cap:
        copy.text = None
        copy.remove(copy[0])
        elided += 1
    # No children left to drop and still long: the element is one text run, so
    # trim that from the front instead. Marked, for the same reason.
    if len(_ser(copy)) > cap and copy.text and len(copy.text) > cap:
        copy.text = "… " + copy.text[-cap:]
    if elided:
        copy.insert(0, etree.Comment(
            f" {elided} earlier child element(s) elided "))
    return _ser(copy), elided


def tail(ref: str, root: Path = Path(".")) -> dict | None:
    """The end of the previous page, for deciding whether this page continues it.

    `None` when the predecessor is not collated (or there is none) — the honest
    answer, and the one `set_seam` gives for the same case, rather than a record
    with empty fields that reads like an observation.

    `ends_sentence` is a hint and never a verdict. A paragraph can end on a full
    stop and still run on, and the live case says so: `1-100` closes its numbered
    list at item 14 with a stop, and `1-101` resumes it at 15. Absence of a
    terminal stop is positive evidence; presence of one is only the lack of it.
    """
    pref = prev_ref(ref)
    if pref is None:
        return None
    path = tei_path(pref, root)
    if not path.exists():
        return None
    els = body_elements(etree.parse(str(path)).getroot())
    if not els:
        return None
    el = els[-1]
    # Computed on note-stripped text: a footnote is anchored in the running text
    # but is not part of it, so its closing sentence must not decide this.
    stripped = _running_text(el).rstrip("”’\")] ")
    xml, elided = _fragment(el)
    return {
        "ref": pref,
        "element": etree.QName(el).localname,
        # A verdict already recorded for this gap, if `harness tei seam` has run.
        "part": el.get("part"),
        "ends_sentence": bool(stripped) and stripped[-1] in ".!?",
        "elided_children": elided,
        "xml": xml,
    }


#: What each `opens:` value implies about the gap, and what each `zone-opens:` value
#: does. `no witness` maps to nothing: a page opening on a heading has no measure to
#: judge, which is a third answer rather than a missing one.
_OPENS_MEANS = {"indented": "fresh", "flush to the measure": "continued"}


def _witnesses(page: Path) -> str:
    """The two independent statements about how this page opens, compared.

    `opens:` is a reader's, off the raster — whether the first line is indented.
    `zone-opens:` is the generator's, off the keyed zone label — whether the page's
    first body zone is `MainZone-Continued`. They are genuinely independent: one is
    a measurement of ink, the other a human's segmentation act recorded months
    earlier, and neither is derived from the other.

    **Reported, never enforced.** Both are human-rank, so a disagreement is not a
    fault in either — it is an editorial question about the page, and this verb has
    no standing to decide it. Silence when either is absent, and silence for `no
    witness`, because a comparison with one witness is the thing this project keeps
    finding in new costumes.
    """
    from lxml import etree
    try:
        root_el = etree.parse(str(page)).getroot()
    except Exception:
        return ""
    reader = zones = ""
    for c in root_el.iter(etree.Comment):
        t = (c.text or "").strip()
        if t.startswith("opens:") and not reader:
            reader = t[len("opens:"):].strip()
        elif t.startswith("zone-opens:") and not zones:
            zones = t[len("zone-opens:"):].split("(")[0].strip()
    if not reader or not zones:
        return ""
    implied = _OPENS_MEANS.get(reader)
    if implied is None:
        return f"opens:{reader} / zone-opens:{zones} — not comparable"
    if implied == zones:
        return f"agree ({zones})"
    return (f"DISAGREE: the raster says {reader!r} (so {implied}) and the keyed "
            f"zone says {zones!r} — read the page before writing the seam")


def set_seam(ref: str, open_gap: bool, root: Path = Path("."),
             commit: bool = False) -> dict:
    """Record whether the gap *before* `ref` carries an element across it.

    Writes `@part` on this page's first top-level element and on the previous
    page's last one. Preview unless `commit`.
    """
    part, idx = parse_ref(ref)
    here = tei_path(ref, root)
    if not here.exists():
        raise ValueError(f"no TEI for {ref} at {here} — collate the page first")
    pref = prev_ref(ref)
    if pref is None:
        raise ValueError(
            f"{ref} is the first scan of part {part} — there is no gap before it")
    there = tei_path(pref, root)
    if not there.exists():
        raise ValueError(
            f"no TEI for {pref} at {there}. The seam is written by the page after "
            "the gap because that is where the evidence is, so its predecessor "
            "must already be collated — work in scan order, or within a chapter.")

    out = {"ref": ref, "prev": pref, "open": open_gap, "committed": commit,
           "witnesses": _witnesses(here), "changes": [], "refused": []}

    htree = _load(here)
    ttree = _load(there)
    hels = body_elements(htree.getroot())
    tels = body_elements(ttree.getroot())
    if not hels:
        raise ValueError(f"{ref} has no top-level body element to mark")
    if not tels:
        raise ValueError(f"{pref} has no top-level body element to mark")

    earlier, later = tels[-1], hels[0]
    ename, lname = etree.QName(earlier).localname, etree.QName(later).localname

    # Non-fragmentable elements are linked rather than parted, and the link is a
    # pair — so both sides must be the same kind before anything is written.
    if open_gap and {ename, lname} & LINKABLE and ename != lname:
        out["refused"].append({
            "side": "both", "ref": ref, "element": f"{pref}:{ename} / {ref}:{lname}",
            "part": None,
            "why": f"the gap is declared open but <{ename}> ends {pref} while "
                   f"<{lname}> opens {ref} — two different elements cannot be one "
                   "element carrying across. This is an editorial question, not a "
                   "branch to pick"})
        return out

    if open_gap and ename == lname and ename in LINKABLE:
        return _link(out, ref, pref, htree, ttree, here, there,
                     earlier, later, commit)
    if not open_gap and ename in LINKABLE and lname in LINKABLE:
        return _unlink(out, ref, pref, htree, ttree, here, there,
                       earlier, later, root, commit)

    for label, tree, path, el, kwargs in (
            ("prev-last", ttree, there, earlier, {"runs_past": open_gap}),
            ("this-first", htree, here, later, {"begins_before": open_gap})):
        name = etree.QName(el).localname
        before = el.get("part")
        if name not in FRAGMENTABLE:
            out["refused"].append({
                "side": label, "ref": pref if label == "prev-last" else ref,
                "element": name, "part": before,
                "why": f"<{name}> is not in TEI att.fragmentable and cannot carry "
                       f"@part, and <{name}> is not linkable either — only "
                       f"{sorted(LINKABLE)} are"})
            continue
        after = _apply(el, **kwargs)
        out["changes"].append({
            "side": label, "ref": pref if label == "prev-last" else ref,
            "element": name, "from": before, "to": after})
        if commit and before != after:
            _save(tree, path)

    return out


def _link(out, ref, pref, htree, ttree, here, there, earlier, later, commit):
    """Join two same-kind non-fragmentable elements across a gap.

    Same single fact as `@part`, spelled differently only because TEI's
    att.fragmentable omits <list> and <table>. Ids are minted from the canonical
    position so they are recomputable, never invented.
    """
    from .ids import XML_ID, canonical_map

    eid = canonical_map(ttree.getroot(), pref)[earlier]
    lid = canonical_map(htree.getroot(), ref)[later]
    earlier.set(XML_ID, eid)
    later.set(XML_ID, lid)
    earlier.set("next", f"#{lid}")
    later.set("prev", f"#{eid}")
    out["changes"] += [
        {"side": "prev-last", "ref": pref, "element": etree.QName(earlier).localname,
         "from": None, "to": f'xml:id={eid} next=#{lid}'},
        {"side": "this-first", "ref": ref, "element": etree.QName(later).localname,
         "from": None, "to": f'xml:id={lid} prev=#{eid}'}]
    if commit:
        _save(ttree, there)
        _save(htree, here)
    return out


def _unlink(out, ref, pref, htree, ttree, here, there, earlier, later, root, commit):
    """Clear a link, and drop each id that no longer has anything pointing at it.

    The sweep reads **both** of an element's gaps, not just the one being edited.
    A list spanning three pages leaves the middle element carrying `@prev` *and*
    `@next`; clearing the earlier gap must not delete an id the later gap still
    names. Same reason `@part` sets one bit and leaves the other alone.
    """
    from .ids import XML_ID

    earlier.attrib.pop("next", None)
    later.attrib.pop("prev", None)
    for el, tree, path, side, eref in (
            (earlier, ttree, there, "prev-last", pref),
            (later, htree, here, "this-first", ref)):
        dropped = None
        if el.get(XML_ID) and not _referenced(el, eref, root):
            dropped = el.get(XML_ID)
            el.attrib.pop(XML_ID, None)
        out["changes"].append({
            "side": side, "ref": eref, "element": etree.QName(el).localname,
            "from": "linked", "to": f"unlinked, id {dropped} dropped" if dropped
                                    else "unlinked, id kept (still referenced)"})
        if commit:
            _save(tree, path)
    return out


def _referenced(el, ref: str, root: Path) -> bool:
    """Does anything still point at this element's id — here or in either neighbour?"""
    from .ids import XML_ID, pointers_in

    ident = el.get(XML_ID)
    if not ident:
        return False
    for cand in (ref, prev_ref(ref), next_ref(ref)):
        if not cand:
            continue
        path = tei_path(cand, root)
        if not path.exists():
            continue
        for p in pointers_in(etree.parse(str(path)).getroot()):
            if p["id"] == ident and p["el"] is not el:
                return True
    return False
