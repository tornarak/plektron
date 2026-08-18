"""The languages the edition can name, in one table.

**This module exists to delete a duplication, not to add a layer.** The Tier-1
codes were stated twice — as a bare set in `validate.TIER1`, and again as
a code-to-name map in `edition_ui.LANG_NAMES` — and the alias column wanted to
state them a third time alongside the handful of European languages the book
cites in. Three hand-maintained copies of one closed set is the shape this
project is organised against, so the set lives here and everything else derives.

It also has to live *low*: `validate` imports `entities`, so `entities` cannot
import `validate`, and the alias vocabulary has to be reachable from both.
Nothing here imports anything, which is what makes that possible.

**Codes are BCP-47 shortest.** `ru`, not `rus`; `la`, not `lat`; `ckt`, because
no two-letter code exists for Chukchi. The reason is not tidiness — this is the
string a collator writes into `xml:lang` on a page, and the string
`data/authorities.json` already carries in its own `lang` field. A vocabulary
that disagreed with either would be a fourth spelling of the same fact.

**`tier1` is the firewall's question, not a linguistic one.** It marks the
languages the book renders in the same ambiguous Americanist notation, so that a
glyph inside one carries the inventory and the ASCII policy. Where the source
does not distinguish members of a family, neither does this: `ypk` and `ipk` are
a family and a macrolanguage code on purpose.

**A language is listed here when something in the corpus already names it** — a
`people:` entry, a `langarea:` shape in `data/geo/`, or an authority's `lang`.
Adding one is a line, but it is a line a human writes with the evidence in view,
because `entity check` refuses an alias whose language is not in this table and
a table padded with plausible codes would refuse nothing.
"""
from __future__ import annotations

#: code → (the name a reader wants, is it Tier-1)
#:
#: The Tier-1 names carry the book's own term where it differs, because the
#: lexicon index is read by someone holding the book: "Yupik" alone would not
#: tell them these are the pages printed "Eskimo".
LANGS: dict[str, tuple[str, bool]] = {
    # Tier-1: the closed set the firewall covers.
    "ckt": ("Chukchi", True),
    "kpy": ("Koryak", True),
    "ypk": ("Yupik (the book's “Eskimo”)", True),
    "xcv": ("Chuvan", True),
    "eve": ("Lamut (Even)", True),
    "ipk": ("Inupiat", True),
    "itl": ("Itelmen (the book's “Kamchadal”)", True),
    # Southern (Kolyma) Yukaghir, which is the variety `data/geo/` draws for the
    # people: `people:yukaghir` takes its extent from `langarea:sout2750`, and
    # Asher 2007 has no Tundra polygon at all (`geo list`'s `yukaghir-tundra`
    # row). **The code is the Southern one and that is a claim, not a default** —
    # if a keyed form turns out to be Tundra Yukaghir it belongs under `ykg`, and
    # nothing here would catch the difference, the two being separate languages
    # with one English name between them in this book.
    "yux": ("Southern Yukaghir", True),
    # The neighbouring languages the book names peoples by. Each is witnessed by
    # an entry under `entities/people/` or a shape in `data/geo/`, or both.
    "ale": ("Aleut", False),
    "evn": ("Evenki (the book's “Tungus”)", False),
    "niv": ("Nivkh (the book's “Gilyak”)", False),
    "sah": ("Sakha (Yakut)", False),
    # The languages the book itself is written and cited in.
    # `data/authorities.json` attests ru, en, de and sv; `la` is the binomials.
    "de": ("German", False),
    "en": ("English", False),
    "la": ("Latin", False),
    "ru": ("Russian", False),
    "sv": ("Swedish", False),
}

#: Every code an alias may declare. Blank is not in here and is not meant to be
#: — an alias with no language is unstated, which is a different claim from one
#: whose language is not in the vocabulary.
ALIAS_LANGS = frozenset(LANGS)

#: The Tier-1 subset, which is what `xml:lang` on a `<foreign>` may hold and what
#: the lexicon is keyed over. Derived, so a code cannot be Tier-1 in one file and
#: not in another.
TIER1 = frozenset(c for c, (_, t) in LANGS.items() if t)

#: Reader-facing names, all of them.
NAMES = {c: n for c, (n, _) in LANGS.items()}

#: The lexicon index's branches, in the declared order rather than alphabetically
#: — they are a fixed vocabulary a reader learns, not a list to sort.
TIER1_NAMES = {c: n for c, (n, t) in LANGS.items() if t}


def name(code: str) -> str:
    """A code as a reader should see it, falling back to the code itself.

    Never raises: this is display, and a card that 500s because a store holds a
    code the table forgot is worse than one that shows the code.
    """
    return NAMES.get(code, code)
