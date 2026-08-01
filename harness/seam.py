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
    """The element's text with <note> subtrees removed.

    A footnote is anchored inside the running text but is not part of it, so
    including it would put the note's last sentence at the end of the tail and
    make `ends_sentence` describe the wrong thing entirely.
    """
    copy = etree.fromstring(etree.tostring(el))
    for note in list(copy.iter(_q("note"))):
        parent = note.getparent()
        # lxml's remove() takes the element's tail with it, and a note is anchored
        # mid-paragraph far more often than at the end — dropping the tail would
        # silently truncate the paragraph at the marker, so the reported tail and
        # `ends_sentence` would both describe a sentence that is not the last one.
        if note.tail:
            prev = note.getprevious()
            if prev is not None:
                prev.tail = (prev.tail or "") + note.tail
            else:
                parent.text = (parent.text or "") + note.tail
        parent.remove(note)
    return " ".join("".join(copy.itertext()).split())


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
        # A verdict already recorded for this gap, if `harness seam` has run.
        "part": el.get("part"),
        "ends_sentence": bool(stripped) and stripped[-1] in ".!?",
        "elided_children": elided,
        "xml": xml,
    }


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
           "changes": [], "refused": []}

    htree = _load(here)
    ttree = _load(there)
    hels = body_elements(htree.getroot())
    tels = body_elements(ttree.getroot())
    if not hels:
        raise ValueError(f"{ref} has no top-level body element to mark")
    if not tels:
        raise ValueError(f"{pref} has no top-level body element to mark")

    for label, tree, path, el, kwargs in (
            ("prev-last", ttree, there, tels[-1], {"runs_past": open_gap}),
            ("this-first", htree, here, hels[0], {"begins_before": open_gap})):
        name = etree.QName(el).localname
        before = el.get("part")
        if name not in FRAGMENTABLE:
            out["refused"].append({
                "side": label, "ref": pref if label == "prev-last" else ref,
                "element": name, "part": before,
                "why": f"<{name}> is not in TEI att.fragmentable and cannot carry "
                       "@part; a run-on list or table needs prev/next pointers, "
                       "which needs the unsettled xml:id scheme"})
            continue
        after = _apply(el, **kwargs)
        out["changes"].append({
            "side": label, "ref": pref if label == "prev-last" else ref,
            "element": name, "from": before, "to": after})
        if commit and before != after:
            _save(tree, path)

    return out
