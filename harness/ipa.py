"""Imputed IPA, from a keyed Bogoras form.

NOTHING HERE IS EVIDENCE, and nothing here reads a scan. This is a rule table
applied mechanically to a form some human already keyed and ratified; it
settles no glyph and proposes none, so the firewall is not what is at stake.
What is at stake is the other failure mode: a pronunciation that looks
authoritative because it is spelled in IPA. So every display of this output is
labelled imputed, and `Imputed.complete` goes False the moment a character
falls through -- a transliteration that passed an unknown glyph along silently
would look exactly like one that handled it.

TWO GRADES OF ROW, marked because they are not equally good:

  MYTH  Bogoras's own account of his notation, in the front matter to
        *Chukchee Mythology* (1910) -- the same notation this volume sets,
        described by the man who devised it.
  KEY   the printed key at Part 1, p. 10, which this edition already treats as
        binding apparatus (`keying_spec.md` §2.4). It is what supplies the
        unmarked ASCII sorts the mythology table does not reach -- `c` is
        English *sh*, `j` is French *jour*, `x` is *Bach* -- and the seventh
        member of the palatalization series (§2.5), `x˙`, whose value follows
        from the same series rule the other six are given by.

A HEDGED ROW IS STILL A ROW. Where the source offers two values (`g̣` is
ɣ ~ ɡ, `ʟ` is ʎ̥˔ ≈ ɬʲ) the first is emitted and the second is carried in
`alt`, reported as `hedged` rather than folded away. Choosing per row by which
value looked better would be judgement dressed as a table.

WHAT THIS DOES NOT DO.

**Stress is dropped.** U+02CA is postposed to the stressed vowel and IPA's ˈ
precedes the stressed *syllable*, so placing it needs syllabification --
maximal onset or anything else is a guess, and one wrong guess per word is a
high price for a mark the reader can already see in the form itself.

**The spirant and pause marks are not resolved.** U+0027 is both, disjoint by
environment (`keying_spec.md` §2.1), and both have zero confirmed instances
corpus-wide; the spec says outright not to propose one. So a form containing
one comes back `complete=False` rather than asserting either -- the same
discipline the Moll reader applies to its own undecided `с`.

**Five sorts have no row**: `š`, `ë`, `ṛ`, `ḷ` and `ʟ̣`'s neighbours are not
all here. Each has a *gloss* in the p. 10 key -- "~ German z [sic]", "like a
in make", "velar r" -- and turning a gloss into an IPA symbol is a judgement,
not a lookup. They fall through and mark the form partial.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

MYTH = "myth"
KEY = "key"

#: U+02CA, postposed to the stressed vowel. Dropped -- see the module docstring.
STRESS = "ˊ"
#: U+0021, "increased articulation stress" (`keying_spec.md` §2.1). Rare, and
#: it modifies delivery rather than naming a segment. Dropped, not flagged.
EMPHATIC = "!"
#: U+0304 macron / U+0306 breve: extra length and extra shortness.
LONG = "̄"
SHORT = "̆"
#: IPA's own extra-short is the combining breve, so that half is a straight
#: carry-over. Length is `ː`, appended -- the plain vowels are already long, so
#: a macron over one gives `ːː`, which is what extra-long means.
IPA_LONG = "ː"

#: Spirant and pause both key here, and neither is resolvable. Kept out of the
#: table so it lands in `unresolved` and marks the form partial.
UNDECIDED = {"'"}

# Ordered by length at load, longest match wins. Sequences are NFD, which is
# what the corpus is: `č` is c + U+030C, `g̣` is g + U+0323, `ä` is a + U+0308.
# Each row is (NFD sequence, IPA, grade, alternative-or-empty).
RULES: list[tuple[str, str, str, str]] = [
    # -- vowels ------------------------------------------------------------
    # The plain five are long; `o` alone is not, and is the one asymmetry in
    # the vowel table rather than an oversight here.
    ("a", "aː", MYTH, ""),
    ("e", "eː", MYTH, ""),
    ("i", "iː", MYTH, ""),
    ("u", "uː", MYTH, ""),
    ("o", "ɔ", MYTH, ""),
    ("ä", "əː", MYTH, ""),          # ä, the long obscure vowel
    ("ê", "ɛː", MYTH, ""),          # ê
    ("ɵ", "o̝ː", MYTH, ""),          # ɵ, "between o and u, long"
    ("ŭ", "ʉ̆", MYTH, ""),          # ŭ, before the generic breve
    # the short obscure series, glossed jointly in the p. 10 key
    ("ᴀ", "ə̆", MYTH, ""),           # ᴀ
    ("ᴇ", "ə̆", MYTH, "ɛ̆"),  # ᴇ, ə̆ ~ ɛ̆
    ("ɪ", "ɪ̆", MYTH, ""),           # ɪ
    # -- diphthongs --------------------------------------------------------
    # These beat the single vowels by length, so `au` is a diphthong and
    # `aˊu` -- stress intervening -- is two vowels. The print distinguishes
    # them and so, mechanically, does this.
    ("ai", "ai̯", MYTH, ""),
    ("ei", "ei̯", MYTH, ""),
    ("oi", "oi̯", MYTH, ""),
    ("au", "au̯", MYTH, ""),
    ("ᵉiᵋ", "ei̯ˀ", MYTH, ""),  # ᵉiᵋ, before the bare ᵉi
    ("ᵉi", "ei̯", MYTH, ""),              # ᵉi, the rising diphthong
    # -- consonants --------------------------------------------------------
    ("ᵋ", "ʔ", MYTH, ""),                 # ᵋ laryngeal
    ("g̣", "ɣ", MYTH, "ɡ"),          # g̣, ɣ ~ ɡ
    ("q", "q", MYTH, ""),
    ("k", "k", MYTH, ""),
    ("h", "h", MYTH, ""),
    ("ñ", "ŋ", MYTH, ""),                # ñ
    # the palatalization series, seven members (`keying_spec.md` §2.5). Six
    # are the mythology table's; `x˙` is the seventh and takes the same rule.
    ("d˙", "dʲ", MYTH, ""),
    ("t˙", "tʲ", MYTH, ""),
    ("s˙", "sʲ", MYTH, ""),
    ("n˙", "nʲ", MYTH, ""),
    ("x˙", "xʲ", KEY, ""),                # the *ich* of the key
    ("č˙", "t͡ɕ", MYTH, ""),   # č˙, before č
    ("ǰ˙", "d͡ʑ", MYTH, ""),   # ǰ˙, before ǰ
    ("č", "t͡ʃ", MYTH, ""),         # č
    ("ǰ", "d͡ʒ", MYTH, ""),         # ǰ
    ("d", "d", MYTH, ""),
    ("t", "t", MYTH, ""),
    ("s", "s", MYTH, ""),
    ("n", "n", MYTH, ""),
    ("ř", "r̪", MYTH, ""),               # ř, dental, before r
    ("r", "r", MYTH, ""),
    ("b", "b", MYTH, ""),
    ("p", "p", MYTH, ""),
    ("m", "m", MYTH, ""),
    ("v", "β", MYTH, ""),
    ("l", "l", MYTH, ""),
    ("ʟ̣", "ʎ", MYTH, "lʲ"),    # ʟ̣, before ʟ
    ("ʟ", "ʎ̥˔", MYTH, "ɬʲ"),  # ʟ
    ("w", "w", MYTH, ""),
    ("y", "j", MYTH, ""),
    # the p. 10 key's unmarked ASCII sorts, invisible to every glyph detector
    ("c", "ʃ", KEY, ""),                       # English *sh*
    ("j", "ʒ", KEY, ""),                       # French *jour*
    ("x", "x", KEY, ""),                            # *Bach*
    ("-", "-", KEY, ""),                            # the connector hyphen
]

# NFD the table's own sequences before matching. They are written above as
# whatever the editor's keyboard emitted, and half of them -- `ä`, `č`, `ñ` --
# compose in a source file while the corpus never does. A table that matched
# only the composed form would silently resolve nothing and report every word
# partial, which is the loud failure; one that matched only some of them is
# the quiet one.
_BY_LEN = sorted(
    ((unicodedata.normalize("NFD", seq), unicodedata.normalize("NFD", out),
      grade, alt) for seq, out, grade, alt in RULES),
    key=lambda r: -len(r[0]))
_DROPPED = {STRESS, EMPHATIC}


@dataclass(frozen=True)
class Imputed:
    """One keyed form's imputed pronunciation.

    `complete` is False when anything fell through, which is the only honest
    default: the reader is told the sketch is partial rather than shown a
    string that silently skipped a letter.
    """

    form: str
    ipa: str
    complete: bool
    unresolved: tuple[str, ...] = ()
    hedged: tuple[str, ...] = ()
    grades: frozenset[str] = field(default_factory=frozenset)


def impute(form: str) -> Imputed:
    """A keyed Bogoras form to imputed IPA.

    Case is folded first: an initial capital is orthography, and `Uweˊlen` and
    a mid-sentence `uweˊlen` are the same word said the same way.
    """
    src = form
    w = unicodedata.normalize("NFD", form).lower()
    ipa: list[str] = []
    unresolved: list[str] = []
    hedged: list[str] = []
    grades: set[str] = set()
    complete = True
    i = 0

    while i < len(w):
        c = w[i]

        if c in _DROPPED:
            i += 1
            continue

        # The length marks apply to what was just emitted rather than standing
        # on their own, so they are handled here and not in the table.
        if c == LONG:
            ipa.append(IPA_LONG)
            i += 1
            continue
        if c == SHORT:
            # Extra-short over a vowel the table already made long is a
            # contradiction on the page's terms, not a stacking: `ĭ` is a
            # short i. So the length comes off rather than both being kept.
            if ipa and ipa[-1].endswith(IPA_LONG):
                ipa[-1] = ipa[-1][:-1]
            ipa.append(SHORT)
            i += 1
            continue

        if c in UNDECIDED:
            unresolved.append(c)
            complete = False
            i += 1
            continue

        for seq, out, grade, alt in _BY_LEN:
            if w.startswith(seq, i):
                ipa.append(out)
                grades.add(grade)
                if alt:
                    hedged.append(seq)
                i += len(seq)
                break
        else:
            # Something the notation does not account for, or one of the five
            # sorts deliberately left without a row. Carried across so the
            # reader sees the whole word, and flagged.
            ipa.append(c)
            if not c.isspace():
                unresolved.append(c)
                complete = False
            i += 1

    return Imputed(
        form=src,
        ipa="".join(ipa),
        complete=complete,
        unresolved=tuple(dict.fromkeys(unresolved)),
        hedged=tuple(dict.fromkeys(hedged)),
        grades=frozenset(grades),
    )


def rows(forms: list[str]) -> list[dict]:
    """One report row per form, in the order given.

    Uniform keys, because several forms pool into one table and a row that
    dropped its empty columns would collapse the whole thing into the nested
    rendering.
    """
    out = []
    for f in forms:
        r = impute(f)
        out.append({
            "form": r.form,
            "ipa": r.ipa,
            "state": "complete" if r.complete else "partial",
            "unresolved": " ".join(r.unresolved),
            "hedged": " ".join(r.hedged),
            "grades": " ".join(sorted(r.grades)),
        })
    return out
