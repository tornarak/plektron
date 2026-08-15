"""Figure and plate cross-references in the prose, found and resolved.

The book points at its own pictures constantly — `(Plate XXVII, Fig. 3)`,
`(see Plate XXIII, Fig. 2; also Fig. 177)`, `Fig. 87 represents a knife` — and
every one of those is a picture the figure store already holds. This finds them
and says which.

**Two halves, kept apart on purpose.** `scan` reads a string and reports what the
*page* prints; `resolve` takes those spans plus the stores and says where each
one points. The renderer calls the first and never the second, because
`stores.render` is cached on the TEI's bytes alone: a `ref/key` baked into that
HTML would go on being served after `gt/fig/` moved the box, with nothing to
signal it. Same division, and the same reason, as `<figure>` and
`web/edition._figure_state`.

**Nothing here is a reading.** A cross-reference is set in ASCII by the printer
and names a number the book assigned; matching one is not a judgement about a
glyph, and the resolution is a lookup in two stores a human keyed. Where the
lookup does not come back with exactly one answer the reference stays plain
text, which is the rule the List of Illustrations already follows for the same
collisions.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from .figures import zone_suffix

#: A printed figure reference: `Fig. 87`, `Figs. 214, 215, 216`, `Figs. 2-4`.
#: The head is matched here and the numerals are consumed by `_numerals`, because
#: a run names several pictures and **each numeral is its own link** — the List
#: of Illustrations' rule, and for its reason: one link for `Figs. 214, 215, 216`
#: would have to pick one of three.
_FIG_HEAD = re.compile(r"\bFigs?\.\s*(?=\d)")

#: A printed plate reference: `Plate XIV`, `Plates XVII and XVIII`, `Plate V.`.
_PLATE_HEAD = re.compile(r"\bPlates?\.?\s+(?=[IVXLC])")

#: One numeral in a run, and the sub-letter that may follow it. **The sub-letter
#: is consumed and never linked**: `Fig. 190, a` names a part of one picture, and
#: the store keys pictures, not parts. Its superscript variant (`a¹`, `c¹`) is
#: consumed with it — a superscript here distinguishes two details of one figure
#: and changes nothing about which picture is meant.
_NUM = re.compile(r"(\d+)(\s*,?\s*[a-z][¹²³⁴⁵⁶⁷⁸⁹0-9]?\b)?")
_ROMAN = re.compile(r"([IVXLC]+)\b")

#: What may stand between two members of one run. A `,` that is followed by
#: anything but another member ends it, which is what keeps `Fig. 74, k, p. 156`
#: from reading `156` as a third figure.
_SEP = re.compile(r"\s*(?:,|and|&|[-–—])\s*")

#: What may stand between a plate and a figure number that belongs to it.
#: **Punctuation only.** `Plate XXVII, Fig. 3` and `Plates V (Fig. 1` are one
#: reference; `Plate XXIII, Fig. 2; also Fig. 177` is two, and the `;` is what
#: says so. Getting this wrong is not cosmetic — the book restarts figure
#: numbering at 1 on every plate, so a plate-scoped number and a text-figure
#: number of the same value are different pictures.
_ATTACHED = re.compile(r"^[\s,(]*$")


def scan(text: str) -> list[dict]:
    """Every figure and plate reference one string prints, in order.

    Returns `{start, end, kind, number, plate}` per **linkable numeral**:
    `kind` is `"plate"` or `"figure"`, `number` is what the page prints, and
    `plate` is the roman of the plate a figure number is scoped to, or `""`.

    `start`/`end` bound the numeral alone, never the `Fig.` before it. The word
    is the printer's furniture and the numeral is the handle; underlining
    `Fig. 87` entire would also mean that `Figs. 214, 215, 216` had to be one
    link or four overlapping ones.
    """
    out: list[dict] = []
    plates: list[tuple[int, int, str]] = []  # (start, end, roman)

    for m in _PLATE_HEAD.finditer(text):
        pos = m.end()
        while (r := _ROMAN.match(text, pos)) is not None:
            out.append({"start": r.start(1), "end": r.end(1), "kind": "plate",
                        "number": r.group(1), "plate": ""})
            plates.append((r.start(1), r.end(1), r.group(1)))
            pos = r.end()
            if (s := _SEP.match(text, pos)) is None:
                break
            pos = s.end()

    for m in _FIG_HEAD.finditer(text):
        # The plate this run hangs off, if any: the last one to end before the
        # run begins, with nothing but punctuation between.
        scope = ""
        for _, p_end, roman in reversed(plates):
            if p_end > m.start():
                continue
            if _ATTACHED.match(text[p_end:m.start()]):
                scope = roman
            break
        pos = m.end()
        while (n := _NUM.match(text, pos)) is not None:
            out.append({"start": n.start(1), "end": n.end(1), "kind": "figure",
                        "number": n.group(1), "plate": scope})
            pos = n.end()
            if (s := _SEP.match(text, pos)) is None:
                break
            pos = s.end()

    out.sort(key=lambda s: s["start"])
    return out


def authority_names(authorities: Iterable[dict]) -> set[str]:
    """The citation names and short titles of the works Bogoras quotes.

    Passed to `foreign_citation` rather than read here, so this module keeps its
    back to the apparatus stores exactly as `figures.by_plate` does.
    """
    out: set[str] = set()
    for a in authorities:
        for c in a.get("cited_as") or ():
            for k in ("name", "short_title"):
                if c.get(k):
                    out.add(c[k])
    return out


def foreign_citation(before: str, names: set[str]) -> str:
    """The authority whose plate this is, if the reference is not to this book.

    **The hazard this exists for is a correct-looking link to the wrong
    picture.** Bogoras cites other people's plates in his footnotes, in the same
    words he uses for his own: `Sauer, Plate XIV, p. 321` is Sauer's fourteenth
    plate, and this book also has a Plate XIV. Nothing in the reference itself
    tells them apart. What does is the name in front of it, and `Authorities
    Quoted` is a store of exactly those names, keyed by a human — so the check
    is a lookup, not a guess.

    `before` is the prose already rendered in this block, so an authority set in
    its own element (`<bibl>Sauer</bibl>, Plate XIV`) is still seen: the
    renderer accumulates the block's plain text and hands it over whole.

    Between the name and the reference only citation furniture may stand — a
    comma, a short title, `in`, an opening bracket. A sentence's worth of prose
    ends the citation, so `Nordenskiöld wintered here. Fig. 88 shows the ship`
    is this book's figure and is left alone.

    Returns the name, or `""`. Refusing is the safe direction and the reference
    simply prints plain.
    """
    if not names:
        return ""
    tail = before[-160:]
    for name in names:
        for m in re.finditer(rf"(?:^|[^\w]){re.escape(name)}\b", tail):
            rest = tail[m.end():]
            if re.fullmatch(
                r"[\s,.]*(?:(?:in|op\.\s*cit\.|l\.\s*c\.)[\s,]*"
                r"|[A-Z][\w’']*[\s,.]*|[(\[])*",
                rest,
            ):
                return name
    return ""


def resolve(span: dict, by_number: dict, by_plate: dict,
            figures_on: callable) -> dict:
    """Where one scanned reference points: `{pairs, why}`.

    `pairs` is a list of `ref/key`, the same handle a stack card is built from
    and the same one the List of Illustrations hands to `openFigure`. Empty
    means nothing linked, and `why` says which store declined.

    Three cases, and the middle one is the reason this function is worth having:

    - **a plate** — every picture on its leaf, as the printed list links it.
    - **a plate's figure** — the leaf from `by_plate`, then the picture on that
      leaf whose caption prints that number. **This is a join the List of
      Illustrations cannot make and prose needs.** Plate figures restart at 1 on
      every plate, so `Fig. 1` on its own names 31 different pictures and the
      list has to print it plain; `Plate XXI, Fig. 1` names exactly one, because
      the plate scopes it. Matching the number against the leaf's own captions
      rather than counting into a list keeps it a lookup: a plate missing a
      numbered caption resolves to nothing instead of to its neighbour.
    - **a text figure** — `by_number`, and only where it holds exactly one
      *after the plate leaves come out*. A number on a plate is only a number
      within that plate, so it is never cited without it; a bare `Fig. 2` is
      therefore the text-figure series and nothing else. Which leaves are plates
      is `by_plate`'s answer, not a guess — and the filter is what turns the
      collision the List of Illustrations has to print plain into a link, since
      the list names its numbers with no sentence around them and prose does
      not. `Fig. 1` still refuses: 31 pictures print it and none is on a text
      page, the fold-out map having no box in `gt/fig/`.
    """
    if span["kind"] == "plate":
        hit = by_plate.get(span["number"])
        if not hit:
            return {"pairs": [], "why": "no plate of that number is located"}
        return {"pairs": [f"{hit['ref']}/{k}" for k in hit["keys"]], "why": ""}

    if span["plate"]:
        hit = by_plate.get(span["plate"])
        if not hit:
            return {"pairs": [], "why": f"Plate {span['plate']} is not located"}
        found = [f for f in figures_on(hit["ref"])
                 if str(f.get("n")) == span["number"]]
        if len(found) != 1:
            return {"pairs": [],
                    "why": f"{len(found)} figures numbered {span['number']} on "
                           f"Plate {span['plate']}"}
        # One figure, but a figure is not one box: the parts of a lettered
        # figure hang under its single caption, and a reference to it names all
        # of them, as the plate case above does for the leaf.
        return {"pairs": [f"{hit['ref']}/{zone_suffix(z)}"
                          for z in found[0]["zone_ids"]], "why": ""}

    on_plates = {h["ref"] for h in by_plate.values()}
    hits = [h for h in by_number.get(span["number"]) or []
            if h["ref"] not in on_plates]
    if len(hits) != 1:
        return {"pairs": [],
                "why": f"{len(hits)} text figures print the number "
                       f"{span['number']}"}
    # Every box, not the first: `1-276`'s Fig. 140 is two, lettered a and b under
    # its one caption. `figures.crop_keys` is the rule and the plate cases above
    # go through it too.
    return {"pairs": [f"{hits[0]['ref']}/{k}"
                      for k in hits[0].get("keys") or [hits[0]["key"]]],
            "why": ""}
