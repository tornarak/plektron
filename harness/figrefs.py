"""The book's cross-references to itself — figure, plate and page.

The book points at its own pictures constantly — `(Plate XXVII, Fig. 3)`,
`(see Plate XXIII, Fig. 2; also Fig. 177)`, `Fig. 87 represents a knife` — and
every one of those is a picture the figure store already holds. This finds them
and says which. It points at its own leaves too — `See p. 15.`, `Compare
pp. 33, 161.` — and those resolve through the folio index instead, `_PAGE_HEAD`
and `KINDS` carrying why the two are not found on the same terms.

**Two halves, kept apart on purpose.** `scan` reads a string and reports what the
*page* prints; `resolve` takes those spans plus the stores and says where each
one points. Nothing calls the first and then the second in one place, because
`stores.render`'s key names the page and the ToC, and not `gt/fig/`: a `ref/key`
baked into that HTML would go on being served after the box moved, with nothing
to signal it. Same division, and the same reason, as `<figure>` and
`web/edition._figure_state`.

**The scan is written into the page; the resolution never is.** `tei generate`
marks each reference it finds — `<ref type="figure" n="44" resp="#mz">44</ref>`,
`mark` below — and the renderer reads those marks instead of re-scanning the
served text. The two halves fall either side of that line for the reason they
were split in the first place: which numerals the page *prints* as a reference is
a fact about a string that no store can invalidate, and where each one *points*
is a join over `gt/fig/` that a moved box invalidates at once.

**Which is what makes a cross-reference auditable.** It used to be found in the
renderer, so it existed only in served HTML: the collator reviewing the page
never saw it, `tei validate` had nothing to say about it, and a reference scoped
to the wrong plate — a working link to a picture on another leaf, with a caption
that reads correctly under it — had no witness but a reader who clicked. In the
page it is an `#mz` claim like an entity link, re-derived from the printed text
on every validation run and deletable by the collator who can see it is wrong.

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

#: A chapter reference: `See Chapter XII.`, `Compare Chapter XI.`, `They will be
#: discussed at length, in Chapter XIII.`
#:
#: **Scanned permissively, on the plate's terms and not the page's.** `Chapter`
#: is the printer's furniture and the roman is the handle, so the name in front
#: of it is once again the whole discriminator — `Compare Bogdanovitch,
#: Chapter V.` is Bogdanovitch's fifth chapter, and `foreign_citation` catches it
#: standing right where it stands in front of a plate. That is the difference
#: from `_PAGE_HEAD` in one line: a page locator has no furniture for a name to
#: govern, and this has.
#:
#: Measured over the corpus: 19 printed, 1 behind an authority, and **every one
#: of the remaining 18 names a roman `edition/toc.json` holds as a chapter.**
#:
#: `Chapters?\.?` tolerates the stop `2-004` sets in `Compare Chapter. XIII.` —
#: adjudicated ground truth, so it is what the leaf prints. The mark covers the
#: roman alone and a stop before it changes nothing about which chapter is meant.
#:
#: **What is deliberately not matched is a chapter named by its title** — `See
#: chapter on shamanism.` and `See chapter on charms.`, one page each. The first
#: would resolve: `Shamanism` is a level-1 title and nothing else. The second
#: would have to choose among six entries whose titles carry *Charms*, of which
#: `Charms and Sacred Objects` is merely the one that happens to be a chapter. A
#: rule that resolves one and guesses the other is worse than a rule that leaves
#: both as worklist lines, and two attestations do not pay for the machinery.
_CHAP_HEAD = re.compile(r"\bChapters?\.?\s+(?=[IVXLC])")

#: A page reference to **this book**: `See p. 15.`, `Compare pp. 33, 161.`,
#: `(cf. p. 30)`, `. Compare also p. 312, Footnote 4.`
#:
#: **The deictic is inside the pattern, and that is the whole design.** A page
#: locator is the commonest thing in these footnotes and it is nearly always
#: somebody else's: 268 are printed across the 325 generated pages, and only
#: about a quarter point at this book. The rest close a citation — `Nelson,
#: Fig. 93, p. 271`, `Ibid., p. 115`, `See Vol. VI, The Koryak, p. 123`, and a
#: `p. 1275` that is Middendorff's. A plate reference could be scanned
#: permissively and filtered afterwards by `foreign_citation`, because the plate
#: is the printer's furniture and the name in front of it is the discriminator.
#: A page locator has no furniture at all: `p. 24` is `p. 24` whoever's page it
#: is, so a permissive scan would hand the guard 268 spans of which it correctly
#: judged **113**, and the residue is not noise but working links into the wrong
#: book.
#:
#: So the *construction* is matched instead of the locator. The reference has to
#: open its own clause and reach the number with nothing between: a cue verb,
#: optionally `also`, then the locator. That is a sentence pointing at this book
#: and it is not book-specific — it is how a cross-reference is set in any
#: monograph. Anything richer than the cue is a citation and prints plain,
#: including several that *are* this book's (`See Fig. 110, p. 190`,
#: `Compare the Oˊnmɪlɪn Group, p. 26`). **Refusing them is the safe direction**
#: and the same one the List of Illustrations takes on a collision: an unmarked
#: reference is a worklist line a collator can add, and a wrongly marked one is a
#: link that opens a real leaf and reads correctly under it.
#:
#: Measured: 69 marked, and reading all 69 against the printed text found no
#: foreign citation among them. The two that a bare-deictic rule *would* have
#: caught are what fixed the "nothing between" clause — `He even asserts
#: (p. 77)` on `1-066`, where the *He* is Maydell, and `one of the texts
#: published in my “Chukchee Materials” (p. 52)` on `1-068`, which is Bogoras's
#: other book. Both print a bare `(p. N)` and both are excluded because no cue
#: opens them.
_PAGE_HEAD = re.compile(
    r"(?:^|[.;:—]|\()\s*[¹²³⁴⁵⁶⁷⁸⁹]?\s*"
    r"(?:[Ss]ee|[Cc]ompare|[Cc]f\.)\s+(?:also\s+)?"
    r"pp?\.\s*(?=\d)")

#: One numeral in a run, and the sub-letter that may follow it. **The sub-letter
#: is consumed and never linked**: `Fig. 190, a` names a part of one picture, and
#: the store keys pictures, not parts. Its superscript variant (`a¹`, `c¹`) is
#: consumed with it — a superscript here distinguishes two details of one figure
#: and changes nothing about which picture is meant.
#:
#: **Several of them may follow one numeral**: `Figs. 188, a, i; 190, b` (1-334)
#: cites two details of the same picture, and consuming only the first left `i`
#: standing where the next member should be, which ended the run one member
#: early. The repeat cannot run away into the prose — `Fig. 53, a, a narwhal`
#: stops at the second `a`, the word after it failing the `\b`.
#:
#: **Exported as its own pattern, because a second reader needs it.** A raised
#: numeral inside this tail is a *locant* and never a footnote marker, and the
#: note-anchoring pass in `generate.py` has to know that or it reads `d²` in
#: `(Fig. 155, d², e¹)` as a reference to note 2. `keying_spec.md` §2.10 states
#: the exclusion in prose and bounds it textually — "a lone letter carries the
#: superscript and a close-paren follows" — which catches the last locant of a
#: run and misses every earlier one. This is the same fact structurally, and one
#: definition rather than two.
_LOCANTS = r"(?:\s*,?\s*[a-z][¹²³⁴⁵⁶⁷⁸⁹0-9]?\b)*"
LOCANTS = re.compile(_LOCANTS)
_NUM = re.compile(r"(\d+)" + _LOCANTS)
_ROMAN = re.compile(r"([IVXLC]+)\b")

#: What may stand between two members of one run. A `,` that is followed by
#: anything but another member ends it, which is what keeps `Fig. 74, k, p. 156`
#: from reading `156` as a third figure.
_SEP = re.compile(r"\s*(?:,|and|&|[-–—])\s*")

#: The same between two numerals of one **figure** run, plus the semicolon.
#: `(Figs. 44, a¹; 46, a¹; 46, b)` (1-171) and `(Figs. 188, a, i; 190, b; also
#: Plate XXVIII)` (1-334) are single runs, and the printer raises the separator a
#: rank because the comma is already spoken for *inside* a member: `188, a, i` is
#: one picture and its two details, so a comma between members could not be told
#: from the one before a sub-letter. Without this the run stopped at its first
#: member and the rest of it printed plain.
#:
#: **Figures only, on the evidence.** Both attestations are numeral runs, and the
#: roman loop carries a hazard the numeral loop does not: `I` is a roman, so
#: `Plate II; I have seen` would read a second plate out of a pronoun.
#:
#: It does not disturb `_ATTACHED`, which is what makes a `;` end a plate's
#: scope. A member is a numeral or the run is over — `; also Plate`, `; see also
#: Fig. 177` and `Fig. 69; b` all end it, the last because a sub-letter with no
#: number before it is not a member.
_FIG_SEP = re.compile(r"\s*(?:[,;]|and|&|[-–—])\s*")

#: What may stand between a plate and a figure number that belongs to it.
#: **Punctuation only.** `Plate XXVII, Fig. 3` and `Plates V (Fig. 1` are one
#: reference; `Plate XXIII, Fig. 2; also Fig. 177` is two, and the `;` is what
#: says so. Getting this wrong is not cosmetic — the book restarts figure
#: numbering at 1 on every plate, so a plate-scoped number and a text-figure
#: number of the same value are different pictures.
_ATTACHED = re.compile(r"^[\s,(]*$")


#: One page in a locator's run. No locants — a folio has no sub-parts — and no
#: roman, this index being the arabic folio `apparatus.folio_index` is keyed by.
_FOLIO = re.compile(r"(\d+)")


def scan(text: str) -> list[dict]:
    """Every figure, plate and page reference one string prints, in order.

    Returns `{start, end, kind, number, plate}` per **linkable numeral**:
    `kind` is `"plate"`, `"figure"` or `"page"`, `number` is what the page
    prints, and `plate` is the roman of the plate a figure number is scoped to,
    or `""` — always `""` on a page, a folio being scoped to nothing.

    `start`/`end` bound the numeral alone, never the `Fig.` or the `See p.`
    before it. The word is the printer's furniture and the numeral is the
    handle; underlining `Fig. 87` entire would also mean that
    `Figs. 214, 215, 216` had to be one link or four overlapping ones.

    **The three kinds are not found on equal terms**, and `_PAGE_HEAD` carries
    why: a figure reference is scanned permissively and disqualified afterwards
    by the name in front of it, and a page reference has to prove itself here
    because there is nothing about `p. 24` for a guard downstream to read.
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
            if (s := _FIG_SEP.match(text, pos)) is None:
                break
            pos = s.end()

    for m in _CHAP_HEAD.finditer(text):
        pos = m.end()
        while (r := _ROMAN.match(text, pos)) is not None:
            out.append({"start": r.start(1), "end": r.end(1), "kind": "chapter",
                        "number": r.group(1), "plate": ""})
            pos = r.end()
            if (s := _SEP.match(text, pos)) is None:
                break
            pos = s.end()

    for m in _PAGE_HEAD.finditer(text):
        pos = m.end()
        while (n := _FOLIO.match(text, pos)) is not None:
            out.append({"start": n.start(1), "end": n.end(1), "kind": "page",
                        "number": n.group(1), "plate": ""})
            pos = n.end()
            # `_SEP` and not `_FIG_SEP`: a semicolon does not continue a page
            # run, and a comma only does where a numeral follows it. That is
            # what keeps `See p. 141, footnote.` and `Compare p. 19, Footnote 2`
            # to the one folio each prints — the matter after the comma is a
            # place *on* that page and not a second one.
            if (s := _SEP.match(text, pos)) is None:
                break
            pos = s.end()

    out.sort(key=lambda s: s["start"])
    return out


#: The plate a scoped figure number hangs off, as the mark spells it. Written
#: the way the page writes it, so the attribute reads as the citation it records
#: rather than as a code — and matched strictly, because a `@cRef` this cannot
#: parse is a mark nothing can re-derive and `validate` says so.
_CREF = re.compile(r"^Plate ([IVXLC]+)$")

#: What a `<ref>` may be. `figure` and `plate` are the two things the printer
#: cites by picture; `page` is the book pointing at its own leaf. A fourth value
#: would be a kind of thing this book does not cross-refer to.
#:
#: **A page is not resolved through `resolve` and that is deliberate.** A figure
#: handle is a join over `gt/fig/` and can point at a box somebody has moved; a
#: folio is an address, and `apparatus.folio_index` already answers it for every
#: other folio link the edition draws. So the renderer sends it to `/folio/{n}`
#: directly, as it does a note marker, and the route's own refusal page is what
#: an unwitnessed folio meets — 280 of the book's 732 have a witness today, so
#: that path is the common one and not an edge.
#: `chapter` resolves through `edition/toc.json` and the same folio index behind it,
#: and it refuses at serve time rather than at scan time — a roman the ToC does
#: not hold is a question about the store, which is the answer `resolve` already
#: gives for a plate with no leaf.
KINDS = ("figure", "plate", "page", "chapter")


def mark(span: dict) -> str:
    """The attributes one scanned reference is written into the page with.

    `<ref type="figure" n="44" resp="#mz">44</ref>`, and for a plate-scoped
    number `<ref type="figure" n="2" cRef="Plate XXI" resp="#mz">2</ref>`. The
    element wraps the numeral alone, as `scan` bounds it — `Fig.` is the
    printer's furniture, and a run of three numerals is three marks.

    **Three atomic attributes and no fourth.** `@type` and `@n` are what the page
    prints; `@cRef` is the plate that scopes the number, which is the one part of
    a reference that is not in the numeral itself and the one that goes silently
    wrong — the book restarts its figure numbering at 1 on every plate, so a
    scope dropped here points a reader at a different leaf. Nothing about *which
    picture* is written: that is `resolve`'s, over a store this file cannot see
    from here.
    """
    out = f' type="{span["kind"]}" n="{span["number"]}"'
    if span["plate"]:
        out += f' cRef="Plate {span["plate"]}"'
    return out


def unmark(kind: str | None, n: str | None, cref: str | None) -> dict | None:
    """One marked reference read back as a scan span, or `None` if it is not one.

    The inverse of `mark`, and the reader for both callers that meet a marked
    page: the renderer, which turns it into a handle, and `validate`, which
    re-derives it against the text. `None` means the attributes do not spell a
    reference — a `@type` outside `KINDS`, a missing `@n`, a `@cRef` that is not
    a plate — and every caller treats that as an error rather than as an absence,
    because a mark nobody can read is indistinguishable from one nobody checked.
    """
    if kind not in KINDS or not n:
        return None
    plate = ""
    if cref is not None:
        m = _CREF.match(cref)
        if m is None:
            return None
        plate = m.group(1)
    if kind in ("plate", "page", "chapter") and plate:
        return None                 # none of the three is scoped to a plate
    return {"kind": kind, "number": n, "plate": plate}


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
            # `Kroeber’s Fig. 52` is Kroeber's figure, and the possessive is the
            # word that says so. Two instances, both on `1-358`, and both were
            # linked to this book's Fig. 52 until the mark went into the page
            # where somebody could see it.
            if rest[:2] in ("’s", "'s"):
                rest = rest[2:]
            if re.fullmatch(
                r"[\s,.]*(?:(?:in|op\.\s*cit\.|l\.\s*c\.)[\s,]*"
                r"|[A-Z][\w’']*[\s,.]*|[(\[])*",
                rest,
            ):
                return name
    return ""


def resolve(span: dict, by_number: dict, by_plate: dict,
            figures_on: callable) -> dict:
    """Where one scanned reference points: `{pairs, why, caption}`.

    `pairs` is a list of `ref/key`, the same handle a stack card is built from
    and the same one the List of Illustrations hands to `openFigure`. Empty
    means nothing linked, and `why` says which store declined.

    **`caption` is the printed caption under the picture**, which is the line
    that tells a reader what they are looking at — a card headed `Fig. 87` and
    nothing else names a number, not a thing. It comes from the same store the
    picture does, and it is the caption of the *one* figure that matched: a whole
    plate has several pictures and so several captions, none of them the plate's,
    so a plate resolves with `caption: ""` and its caller supplies the printed
    list's own, which is where a plate's caption is set. Decoration in every
    case — a card is built from `pairs` alone and a missing caption costs a line.

    Three cases, and the middle one is the reason this function is worth having:

    - **a plate** — every picture on its leaf, as the printed list links it.
    - **a plate's figure** — the leaf from `by_plate`, then the picture on that
      leaf whose caption prints that number. **This is a join the List of
      Illustrations cannot make and prose needs.** Plate figures restart at 1 on
      every plate, so `Fig. 1` on its own names 31 different pictures;
      `Plate XXI, Fig. 1` names exactly one, because the plate scopes it. Matching the number against the leaf's own captions
      rather than counting into a list keeps it a lookup: a plate missing a
      numbered caption resolves to nothing instead of to its neighbour.
    - **a text figure** — `by_number`, and only where it holds exactly one
      *after the plate leaves come out*. A number on a plate is only a number
      within that plate, so it is never cited without it; a bare `Fig. 2` is
      therefore the text-figure series and nothing else. Which leaves are plates
      is `by_plate`'s answer, not a guess, and the same filter is what makes the
      List of Illustrations' own first entries resolve — that list enumerates the
      text series and the plates as wholes, so its `Fig. 2` is scoped exactly as
      a bare one in prose is. `Fig. 1` resolves only because a human keyed it:
      31 pictures print it, and the map on `1-037` that is the text series' own
      carries its number after the title where no caption parses it, so
      `edition/figure_numbers.json` names the zone instead.
    """
    if span["kind"] == "plate":
        hit = by_plate.get(span["number"])
        if not hit:
            return {"pairs": [], "why": "no plate of that number is located",
                    "caption": ""}
        return {"pairs": [f"{hit['ref']}/{k}" for k in hit["keys"]], "why": "",
                "caption": ""}

    if span["plate"]:
        hit = by_plate.get(span["plate"])
        if not hit:
            return {"pairs": [], "why": f"Plate {span['plate']} is not located",
                    "caption": ""}
        found = [f for f in figures_on(hit["ref"]) or ()
                 if str(f.get("n")) == span["number"]]
        if len(found) != 1:
            return {"pairs": [],
                    "why": f"{len(found)} figures numbered {span['number']} on "
                           f"Plate {span['plate']}",
                    "caption": ""}
        # One figure, but a figure is not one box: the parts of a lettered
        # figure hang under its single caption, and a reference to it names all
        # of them, as the plate case above does for the leaf.
        return {"pairs": [f"{hit['ref']}/{zone_suffix(z)}"
                          for z in found[0]["zone_ids"]], "why": "",
                "caption": found[0].get("caption") or ""}

    on_plates = {h["ref"] for h in by_plate.values()}
    hits = [h for h in by_number.get(span["number"]) or []
            if h["ref"] not in on_plates]
    if len(hits) != 1:
        return {"pairs": [],
                "why": f"{len(hits)} text figures print the number "
                       f"{span['number']}",
                "caption": ""}
    # Every box, not the first: `1-276`'s Fig. 140 is two, lettered a and b under
    # its one caption. `figures.crop_keys` is the rule and the plate cases above
    # go through it too.
    # The caption is read back off the leaf rather than carried in `by_number`,
    # which indexes numbers to zones and holds no text. Matched on `key`, the
    # store's own foreign key: a figure `edition/figure_numbers.json` numbered by
    # hand may name a zone no folded record keys, and an absent caption is the
    # right answer there rather than the neighbouring figure's.
    caption = next((f.get("caption") or "" for f in figures_on(hits[0]["ref"]) or ()
                    if f.get("key") == hits[0]["key"]), "")
    return {"pairs": [f"{hits[0]['ref']}/{k}"
                      for k in hits[0].get("keys") or [hits[0]["key"]]],
            "why": "", "caption": caption}
