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
        *Chukchee Mythology* (1910), described by the man who devised it --
        vowel and consonant grids on folio 3, a gloss per sort on folio 4.
  KEY   the printed key at Part 1, p. 10, which this edition already treats as
        binding apparatus (`keying_spec.md` §2.4).

**The two keys are not the same notation**, and an earlier version of this
docstring said they were. Mythology's is the *reduced* notation of a text
volume: p. 10 has `g x x˙ š c j ë ḷ ṛ` and the six-member spirant series, none
of which Mythology carries, and p. 10 has four laterals where Mythology has
three. So `MYTH` does not mean "attested in the volume this edition sets"; it
means Bogoras described this sort while describing this system.

A HEDGED ROW IS STILL A ROW. Where a source offers two values the first is
emitted and the second carried in `alt`, reported as `hedged` rather than
folded away. Choosing per row by which value looked better would be judgement
dressed as a table.

RECONCILED AGAINST THE MODERN PHONOLOGY, in `MODERN` below -- the inventory
current descriptions give Chukchi (/m n ŋ/, /p t t͡ʃ k q ʔ/, /β s ɣ ɬ/, /ɻ j/;
/i u e₁ e₂ o a ə/ under dominant/recessive harmony). **That is a second witness
about value and has no standing over the printed key about glyph identity**,
which is what the firewall governs; it is also a tertiary source, and Bogoras
recorded c. 1900 speech across dialects it does not separate, so a contrast he
heard that modern phonemics does not list is not thereby his error. It is kept
in its own table for exactly that reason: the emitted IPA stays his, and the
correspondence sits beside it where a reader can see the two disagree.

Four things it settled, each recorded where it bites:

  - `g̣` is ɣ and the old `ɡ` alternative is withdrawn. Modern Chukchi has no
    native voiced stops, so ɡ was never available; and the missing `g` row
    below is where that value actually belonged.
  - The three "obscure vowels (short)" are one thing. ᴀ ᴇ ɪ are all ə, which
    is what the joint gloss said and what a pervasive epenthetic schwa
    predicts. Rendering them three ways was a distinction with no source.
  - `x` is right and now has a reason: [x] is an allophone of /ɣ/ after
    voiceless stops rather than a phoneme, which is what "German *Bach*" was
    describing.
  - `r` is r, and the "as in French" worry dissolves: /ɻ/ "is mostly heard as
    an alveolar trill [r] between vowels", which is where it sits in most of
    the corpus's forms.

WHAT THIS DOES NOT DO.

**Length is kept, deliberately, and it is the largest place the two witnesses
part.** Bogoras says a, e, i, u are "always long" and this emits `ː` on every
one -- 567 of the corpus's 606 attested forms -- where modern descriptions give
Chukchi no phonemic length. The editor's ruling is that this table renders
*what Bogoras said his letters sound like*, so the mark stays; `MODERN` is
where the other reading is written down.

**Stress is dropped.** U+02CA is postposed to the stressed vowel and IPA's ˈ
precedes the stressed *syllable*, so placing it needs syllabification --
maximal onset or anything else is a guess, and one wrong guess per word is a
high price for a mark the reader can already see in the form itself.

**A straight apostrophe is not resolved.** U+0027 has no licensed position
inside a Tier-1 form (`keying_spec.md` §2.1, §3): the p. 10 key's spirant and
pause marks have never been seen in the corpus, and a raised comma-shaped mark
is stress. A form still carrying one is therefore a keying error awaiting
repair, not a sound, and comes back `complete=False` -- the same
discipline the Moll reader applies to its own undecided `с`.

**Four sorts have no row**: `š` (~ German *z* [sic]), `ë` (like *a* in *make*),
`ṛ` (velar) and `ḷ` (tongue-tip above the alveoli, back free). Each has a
*gloss* in the p. 10 key and nothing more, and turning a gloss into an IPA
symbol is a judgement rather than a lookup. They fall through and mark the form
partial. This said "five" while listing four and omitting `g`, which had no row
at all; `g` now has one.

WHAT THIS DOES NOT DO.

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

#: U+0068, and **aspiration on what precedes rather than a segment of its own**
#: (editor's ruling: a-semantic aspiration). Mythology glosses it "as in
#: English (used after č, t, l)" -- a digraph element, not a free consonant --
#: and modern Chukchi has no /h/ at all. Measured over the corpus's 606
#: attested forms: 108 occurrences, 74 of them after č, t or l exactly as
#: described, 6 word-initial, the rest after a vowel, where a breathed offset
#: is the same thing the p. 10 key's own spirant series calls *gehauchter
#: Absatz*. Word-initially there is nothing to attach to and the `h` row in
#: the table gives p. 10's plain "as in English" instead.
ASPIRATE = "h"
IPA_ASPIRATED = "ʰ"

#: No licensed reading inside a Tier-1 form (§2.1) — a keying error, not a
#: sound. Kept out of the table so it lands in `unresolved` and marks the form
#: partial rather than being silently dropped or mapped.
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
    ("ŭ", "ʉ", MYTH, ""),          # ŭ, before the generic breve
    # **The obscure series is one vowel, not three.** The key glosses these
    # jointly as "obscure vowels (short)" and offers nothing to tell them
    # apart; modern Chukchi's schwa is pervasive and epenthetic, the same
    # distribution. They were rendered three ways -- a split with no source,
    # and the third read its glyph as its own IPA value, which this table does
    # not do anywhere else.
    #
    # **All four short sorts are emitted unmarked**, here and at `ŭ` above, and
    # the breve is left to the *mark*. Both sources distinguish "short" -- what
    # these are -- from "very short", which is what a breve written over a
    # vowel means. Spending U+0306 on the sorts left the mark nothing to say
    # and would stack two breves. The contrast is carried by the length the
    # plain vowels get instead.
    ("ᴀ", "ə", MYTH, ""),           # ᴀ
    ("ᴇ", "ə", MYTH, ""),           # ᴇ
    ("ɪ", "ə", MYTH, ""),           # ɪ
    # -- diphthongs --------------------------------------------------------
    # These beat the single vowels by length, so `au` is a diphthong and
    # `aˊu` -- stress intervening -- is two vowels. The print distinguishes
    # them and so, mechanically, does this.
    ("ai", "ai̯", MYTH, ""),
    ("ei", "ei̯", MYTH, ""),
    # `ɔi̯`, not `oi̯`: the gloss is "like *oi* in *choice*", and the table's own
    # `o` row is ɔ. It read one vowel two ways in two adjacent rows.
    ("oi", "ɔi̯", MYTH, ""),
    ("au", "au̯", MYTH, ""),
    # **One thing spelled two ways, and the prominence is on the closing
    # element.** Mythology: "a diphtong with an accent on *i*. It always has a
    # laryngeal intonation, ᵉiᵋ" -- so the bare spelling is not a plain
    # diphthong, and both rows emit the glottal. And `keying_spec.md` §2.5 has
    # "prominence on the closing element, opening element cast superscript",
    # which is `e̯i`: `ei̯` marked the *i* non-syllabic and so put the accent on
    # the wrong half of the one diphthong the notation spells asymmetrically.
    ("ᵉiᵋ", "e̯iˀ", MYTH, ""),  # ᵉiᵋ, before the bare ᵉi
    ("ᵉi", "e̯iˀ", MYTH, ""),             # ᵉi, the rising diphthong
    # -- consonants --------------------------------------------------------
    ("ᵋ", "ʔ", MYTH, ""),                 # ᵋ laryngeal
    # **The `ɡ` alternative is withdrawn**, and this is the row the modern
    # inventory settled: Chukchi has /ɣ/ and no native voiced stops -- "these
    # are only found in loanwords" -- so ɡ was never available for the sort
    # Bogoras glosses "velar *g*". It is also the value that belongs to plain
    # `g` below, which had no row at all while this one offered its value away.
    #
    # Not read off Mythology's grid, which puts `g̣ h q` on one "Velar" row and
    # `k ñ` on "Palatal". That row is his back-consonant row and lumps velar
    # with uvular; taking its label as a place claim argues `g̣` is uvular,
    # which the modern inventory does not support.
    ("g̣", "ɣ", MYTH, ""),
    ("q", "q", MYTH, ""),
    ("k", "k", MYTH, ""),
    # "like *g* in *good*" (p. 10). Absent from Mythology, which is a reduced
    # notation, and absent from this table until the audit -- so every form
    # carrying a plain `g` came back partial, `g̣iˊrgol` resolving its dotted g
    # and choking on the bare one two letters later.
    ("g", "ɡ", KEY, ""),
    # Word-initial only: everywhere else `h` is aspiration on what precedes and
    # is handled in `impute`. Mythology says it is "used after č, t, l", which
    # is 74 of its 108 occurrences in the corpus; 6 are word-initial with
    # nothing to attach to, and those take p. 10's plain "as in English".
    ("h", "h", KEY, ""),
    ("ñ", "ŋ", MYTH, ""),                # ñ
    # the palatalization series, seven members (`keying_spec.md` §2.5). Six
    # are the mythology table's; `x˙` is the seventh and takes the same rule.
    ("d˙", "dʲ", MYTH, ""),
    ("t˙", "tʲ", MYTH, ""),
    ("s˙", "sʲ", MYTH, ""),
    ("n˙", "nʲ", MYTH, ""),
    # The key's gloss is *ich*, which is ç; xʲ is what the series rule gives.
    # The two are near-identical phonetically and the row is hedged rather than
    # switched, because the series is the reason this member exists at all.
    ("x˙", "xʲ", KEY, "ç"),
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
    # **Lateral fricatives, not palatal laterals, and the hedge was inverted.**
    # Modern Chukchi's one lateral is /ɬ/; Bogoras's gloss is more specific --
    # "posterior palatal *l*, surd and exploded, the tip of the tongue touching
    # the alveoli of the upper jaw, and the back of the tongue pressed against
    # the hard palate" -- which is that lateral fricative with a palatal
    # component. So `ɬʲ` leads and plain `ɬ` is the alternative, where before
    # the palatal reading led and the modern phoneme was the afterthought.
    # `ʟ̣` is "like ʟ, but sonant", so it is the voiced counterpart of whatever
    # `ʟ` is, and follows it.
    ("ʟ̣", "ɮʲ", MYTH, "l"),    # ʟ̣, before ʟ
    ("ʟ", "ɬʲ", MYTH, "ɬ"),   # ʟ
    ("w", "w", MYTH, ""),
    ("y", "j", MYTH, ""),
    # the p. 10 key's unmarked ASCII sorts, invisible to every glyph detector
    ("c", "ʃ", KEY, ""),                       # English *sh*
    ("j", "ʒ", KEY, ""),                       # French *jour*
    ("x", "x", KEY, ""),                            # *Bach*
    ("-", "-", KEY, ""),                            # the connector hyphen
]

#: Bogoras's sort -> `(modern phoneme, note)`, where the phoneme is `""` when
#: current descriptions have no counterpart for it.
#:
#: **A separate table, not a column of `RULES`, and that is the point.** What
#: `impute` emits is Bogoras's own account of his notation; this is what a
#: modern reader would call the same sound, and the two disagree systematically
#: -- over length on nearly every form, over a whole palatalization series, and
#: over every voiced obstruent. Folding them together would make one of the two
#: invisible. Kept in one place so a chart can set them side by side and so a
#: test can check that no row is missing an opinion.
#:
#: The empties are not gaps in the research. They are three real findings:
#: modern Chukchi has no native voiced obstruents, so `b d g ǰ j z` are
#: loanword sorts; it lists no palatalization series, so the seven `˙` members
#: have nowhere to go; and several of Bogoras's contrasts are one phoneme --
#: three rhotics to /ɻ/, four laterals to /ɬ/, `v` and `w` to /β/.
MODERN: dict[str, tuple[str, str]] = {
    # -- vowels. Modern: /i u e₁ e₂ o a ə/, dominant/recessive harmony.
    "a": ("a", ""),
    "e": ("e", "modern distinguishes a recessive e₁ from a dominant e₂; "
               "the notation does not"),
    "i": ("i", ""),
    "u": ("u", ""),
    "o": ("o", ""),
    "ä": ("ə", "the long member of the obscure series"),
    "ê": ("e", "which of the two modern e's is unsettled"),
    "ɵ": ("", "\"between o and u, long\"; o and u are harmony partners, so "
              "whether this is one of them or a third quality is unsettled"),
    "ŭ": ("", "no counterpart listed"),
    "ᴀ": ("ə", ""),
    "ᴇ": ("ə", ""),
    "ɪ": ("ə", ""),
    # -- diphthongs
    "ai": ("", "not listed as a unit in the modern inventory"),
    "ei": ("", "not listed as a unit in the modern inventory"),
    "oi": ("", "not listed as a unit in the modern inventory"),
    "au": ("", "not listed as a unit in the modern inventory"),
    "ᵉi": ("", "not listed as a unit; the laryngeal is /ʔ/"),
    "ᵉiᵋ": ("", "not listed as a unit; the laryngeal is /ʔ/"),
    # -- consonants
    "ᵋ": ("ʔ", ""),
    "g̣": ("ɣ", ""),
    "q": ("q", ""),
    "k": ("k", ""),
    "g": ("", "no native voiced stops; loanwords only"),
    "h": ("", "no /h/; aspiration on the preceding segment"),
    "ñ": ("ŋ", ""),
    "d˙": ("", "no palatalization series in modern descriptions"),
    "t˙": ("", "no palatalization series in modern descriptions"),
    "s˙": ("", "no palatalization series in modern descriptions"),
    "n˙": ("", "no palatalization series in modern descriptions"),
    "x˙": ("", "no palatalization series in modern descriptions"),
    "č˙": ("", "no palatalization series in modern descriptions"),
    "ǰ˙": ("", "no palatalization series in modern descriptions"),
    "č": ("t͡ʃ", ""),
    "ǰ": ("", "no voiced affricate; loanwords only"),
    "d": ("", "no native voiced stops; loanwords only"),
    "t": ("t", ""),
    "s": ("s", ""),
    "n": ("n", ""),
    "ř": ("ɻ", "one of three rhotics the modern inventory has as one phoneme"),
    "r": ("ɻ", "\"mostly heard as an alveolar trill [r] between vowels\", "
               "which is where most of the corpus's forms put it"),
    "b": ("", "no native voiced stops; loanwords only"),
    "p": ("p", ""),
    "m": ("m", ""),
    "v": ("β", ""),
    "w": ("β", "the same phoneme as v"),
    "l": ("", "modern lists only the voiceless lateral"),
    "ʟ": ("ɬ", "the one modern lateral; Bogoras's four collapse here"),
    "ʟ̣": ("", "the voiced counterpart, not a modern phoneme"),
    "y": ("j", ""),
    "c": ("", "no /ʃ/; what Bogoras heard here is unsettled"),
    "j": ("", "no /ʒ/; loanwords only"),
    "x": ("", "an allophone of /ɣ/ after voiceless stops, not a phoneme -- "
              "which is what \"German Bach\" was describing"),
    "-": ("", "orthographic"),
}


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

        # Aspiration attaches to what was just emitted, like the length marks
        # and for the same reason: it is a property of the preceding segment
        # rather than a segment. With nothing before it the table's `h` row
        # answers instead -- see `ASPIRATE`.
        if c == ASPIRATE and ipa:
            ipa.append(IPA_ASPIRATED)
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
