"""Citations of other people's work, and which work each one names.

The footnotes are dense with them — `Resin, p. 156.`, `Maydell I, p. 331.`,
`Bogoras, Chukchee Materials, p. 350.`, `Hooper, Ten Months among the Tents of
the Tuski, p. 100.` — and every one is a work `Authorities Quoted` already holds,
under a siglum a human keyed. This says which.

**The problem it solves is an ambiguity the alias table cannot.** `Nelson` is a
man and a book, and the entity store says exactly that: `person:nelson` and
`source:nelson-1899` both claim the form, so no rule may link it and the
generator leaves a question instead. Which of the two a sentence means is not
decidable from the name — but the *printed citation form* decides it, because a
page locator after a name is what a citation is. `Nelson, pp. 27, 28` is the
book; `Nelson. Fig. 22, b, shows a sled` is the man, and this refuses the second.

**It never introduces a claim, only chooses among the store's own.** The caller
requires the work it resolves to be one of the entities already claiming the
form, so the alias table stays the gate on "this string may name this entity" and
the printed form only disambiguates. Every siglum in `Authorities Quoted` is
claimed by its `source:` entry today, so the requirement costs nothing and keeps
the licence narrow.

**Two human-keyed tables and no third witness.** `authorities.sigla` maps
`(name, volume, short title)` to a work — the resolution table the printed list
*is* — and each `source:` entry names the work it is with `authority:`. Where
either lookup does not come back with exactly one answer, the citation stays
unlinked and the generator's question stands, which is the rule the rest of this
apparatus follows for the same reason.

**Its remit narrowed when the sigla became aliases, and that is the right
direction.** `entity sigla` carries `Authorities Quoted`'s printed sigla onto the
`source:` entries, so `Boas, Central Eskimo` and `Maydell, I` are now forms one
entry claims and the ordinary alias rule links them — with the whole siglum
inside the mark, which this could never do. What is left here is the case no
alias can reach: the **bare surname**, which the man and the book share.

Measured over the 274 generated pages: 130 `#mz` links to a `source:` entry, of
which **66 are the alias table's and 64 are this rule's** — every one of the 64 a
bare surname, `Nelson` alone accounting for 26. Six citations refuse, and each is
a question about the store rather than about the sentence: `Hough, Armor` four
times, against the store's `Armour`; a `Boas, Indianische Sagen` in no authority
entry; a `Bogoras, American Anthropologist` whose siglum the list does not carry.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

#: What says "a place inside a work", and so what says the name in front of it is
#: cited rather than mentioned. Pages, plates and figures alike — the book cites
#: other people's illustrations as readily as their pages, and a plate number is
#: arabic in some of those books and roman in others.
_LOCATOR = r"(?:pp?\.\s*\d|Plates?\s+[IVXLC0-9]|Figs?\.\s*\d)"

#: What may stand between the name and the locator without being part of either:
#: citation punctuation, a possessive (`Boas’s Central Eskimo, p. 569`), and the
#: `op. cit.` the book uses for a work already named. **A full stop is not here**,
#: and that is the whole of what separates a citation from a sentence: `Nelson.
#: Fig. 22, b, shows a sled` ends one statement and begins another, and the
#: figure it then names is this book's own.
_GAP = r"(?:[\s,;()]|’s|'s|op\.\s*cit\.)*"

#: A title or volume standing between the name and the locator, where the work is
#: already decided. Roman or `Vol. IV`, a `Part 2`, or a capitalised run — which
#: is what a short title looks like and what a sentence does not: `Boas and
#: Kroeber; for instance, compare Fig. 199` fails on the lower-case `and`, and
#: `Bogoras, Chukchee Material Life. Plate XII` on the full stop.
_RUN = r"(?:(?:Vol\.\s*)?[IVXLC]+\b|Part\s+\d+|[A-Z][^.;()]{2,48}?)[\s,]*"

_BARE = re.compile(_GAP + f"(?:{_RUN})" + "{0,3}" + _LOCATOR)


def _fits(after: str, row: dict) -> bool:
    """Does this row's own discriminator stand between the name and the locator?

    The volume and the short title come from the store, not from a pattern, so
    what is asked of the page is "does it print *this* work's siglum" and never
    "what might this text be". Two of the book's authors are cited both ways —
    `Hough, Lamp` and `Adler, II` — and the table is what tells them apart.
    """
    pat = _GAP
    if row.get("volume"):
        pat += rf"(?:Vol\.\s*)?{re.escape(row['volume'])}\b{_GAP}"
    if row.get("short_title"):
        pat += rf"{re.escape(row['short_title'])}\b{_GAP}"
    return re.match(pat + _LOCATOR, after) is not None


def cited(name: str, after: str, rows: Iterable[dict]) -> str:
    """The `authorities.json` key this printed siglum names, or `""`.

    `after` is the text that follows the name, and it is the whole of the
    evidence: a locator attached to a name makes it a citation, and nothing else
    here is a judgement about the sentence.

    Where the siglum names one work, any citation-shaped run may stand between —
    an unlisted short title cannot change an answer that is already decided.
    Where it names several, exactly one of them must print its own discriminator;
    `Hough, Armor` names three works and matches none of their sigla, so it comes
    back empty and the reader is asked.
    """
    cand = [r for r in rows if r.get("name") == name]
    keys = {r["key"] for r in cand}
    if not keys:
        return ""
    if len(keys) == 1:
        return keys.pop() if _BARE.match(after) else ""
    fits = {r["key"] for r in cand if _fits(after, r)}
    return fits.pop() if len(fits) == 1 else ""


def work_of(key: str, store: dict) -> str:
    """The single ratified `source:` entry that *is* that work, or `""`.

    The second of the two lookups, and it fails the same way: an authority no
    entry claims, or two entries claiming one, resolves to nothing rather than to
    whichever came first. `entity new --authority` is where the field is written,
    and 73 of the store's 74 sources carry one.
    """
    hits = [eid for eid, rec in store.items()
            if rec.get("authority") == key and rec.get("status") == "ratified"]
    return hits[0] if len(hits) == 1 else ""
