# Keying spec — Bogoras notation → Unicode

**Authority.** The printed key (Part 1, p. 10 — book-internal apparatus,
firewall-clean, binds) as corrected by the editor's corpus-scale collation
from hand-corrected OCR. `CLAUDE.md` outranks this file on project invariants;
`.claude/skills/transcribe-page/SKILL.md` governs the collation pass. This file is normative for
the character inventory, and binds both passes and the human keying track.

---

## 1. Doctrine

- **Firewall.** No non-English glyph identification originates from a model's
  reading of a scan or from inference about what the system "should" contain.
  Shape decides only at keying, by a human. The p. 10 key is evidence and
  binds.
- **NFD, corpus-wide.** One conversion point; verified at export:
  `python3 -c "import unicodedata,sys; print(unicodedata.is_normalized('NFD', open(sys.argv[1]).read()))"`
- **ASCII policy, scoped to Tier-1.** Inside
  `ckt`/`kpy`/`ypk`/`xcv`/`eve`/`ipk`/`itl`, U+0027 and U+002D are the only
  apostrophe and hyphen, and the lookalike greps (§3) run there.
  Rationale: ASCII is what every keyboard emits, hence drift-proof; a
  modifier-letter codepoint invites conflation with a true apostrophe at every
  entry point — and inside a Tier-1 span the apostrophe is phonetically
  load-bearing, since U+0027 *is* the spirant and pause mark rather than a
  lookalike for one. English prose reproduces the print, **curly quotes
  included**: the book sets them, nothing there is load-bearing, and forbidding
  them would reject correct text. `validate.py`'s `FORBIDDEN_PROSE` and its
  scoped greps are the enforcement.
- **Keying reproduces print**, the book's own errors included. The collation pass
  may modernize glossed Russian (harness rev 2); ground truth does not —
  pre-reform Cyrillic sorts are keyed as printed. See §2.7 for the closed list and
  what each is confusable with, and §2.14 for the typo rule and its one exception.
  **Species names go the same way**: `Oncorhynchus horbusha`, `niarka` — key the
  epithet as set, never the modern binomial it corresponds to. Mapping obsolete
  names onto current ones is a post-collation pass with its own record. These two
  attest in Bogoras and Jochelson and nowhere else, so "correcting" one to the
  expected Russian yields a form with no attestation anywhere — inference about
  what the name *should* be, which is the firewall's subject in another costume.
- **Two-tier settlement.** SETTLED rows carry the editor's stamp or the key's
  authority and are law, stated flat. PROPOSED rows are the best available
  disposition, awaiting the stamp; they enter force via changelog, not by
  ceasing to be questioned.

## 2. Inventory

### 2.1 Marks (SETTLED)

| Mark | Codepoint | License / notes |
|---|---|---|
| word stress, postposed to the stressed vowel | **U+02CA** ˊ | ≤1 per word (validation). Absent from the p. 10 key; corpus-attested only — the one inventory member the calibration page will not corroborate. |
| laryngeal superscript | **U+1D4B** ᵋ | Glottalization of the stressed vowel. Confirmed at corpus scale; citable. |
| rising-diphthong onglide | **U+1D49** ᵉ | Key: "a diphthong with an accent on *i*." Licensed only immediately before `i`; the key's any-V + i/u doctrine predicts siblings, but the license extends on attestation, never on symmetry. |
| velar g, dot below | **g + U+0323** g̣ | Pairs proportionally with q (q : k :: g̣ : g). |
| long rounded mid vowel | **U+0275** ɵ | Key: "between *o* and *u*, long." |
| spirant mark | **U+0027** ' | After b p d t g k only. **Zero confirmed instances corpus-wide as of 11/20 pilot pages restored** — every candidate examined so far has turned out to be stress (U+02CA) on closer reading. Documented in the p. 10 key, licensed, and not to be ruled out by fiat — but it has never once been the right call in practice. Do not propose it. |
| pause mark | **U+0027** ' | V_V only; key specimen *yiñe'a*. **Zero confirmed instances corpus-wide** — same status as spirant, above: real per the key, unattested in restored text, and every V_V-position candidate found so far was stress. Do not propose it. |
| palatalization mark, postposed | **U+02D9** ˙ | After the full seven-member series n x d t s č ǰ. |
| connector hyphen | **U+002D** - | Forms essentially never break across lines; residual line-end joins go to LLM triage in context, human-confirmed — a join question, not a glyph identity. |
| length marks | **U+0304** ◌̄ , **U+0306** ◌̆ | Combining, NFD; both productive. Breve doubles as the ŭ sort's mark — one shape, two functions; interpretation is downstream, not a keying problem. |
| increased articulation stress | **U+0021** ! | Rare. Collides with prose exclamation; environment (word-internal / form-adjacent) disambiguates — keyer discretion, comment on doubt. |

**Shared-codepoint design.** Spirant and pause both key U+0027: their licensing
environments are disjoint (post-consonantal-by-list vs. intervocalic), so
function is mechanically recoverable from position, and shape contrast between
the printed sorts is deliberately not preserved. U+0027 in any other
environment inside a form is unconditionally an error.

**ᵉ and ᵋ are mutually confusable and both licensed** — unlike the lookalike
pairs, where one member is always an error. Environments are disjoint (ᵉ only
pre-`i`; ᵋ never), so: U+1D49 not immediately followed by `i` is
unconditionally an error; U+1D4B immediately before `i` is a review-flag —
that position is where a keyer's ᵉ/ᵋ misclick would hide. Shape decides only
at keying, and the sorts differ exactly where bitonal scans fail (bowl
closure, crossbar): a named F11 client.

### 2.2 Letters — marked sorts (SETTLED)

| Sort | Key gloss | NFD | Note |
|---|---|---|---|
| ñ | — | n + U+0303 | corpus-attested |
| č | like English *ch* | c + U+030C | |
| š | ~ German *z* [sic] | s + U+030C | gloss as printed |
| ř | dental, slight trill | r + U+030C | third rhotic (F4) |
| ǰ | English *joy* | j + U+030C | pairs with plain j (French *jour*) |
| ê | — | e + U+0302 | corpus-attested |
| ë | like *a* in *make* | e + U+0308 | |
| ä | obscure vowel (long) | a + U+0308 | long counterpart of the ᴀ ᴇ ɪ series |
| ŭ | mouth in *i* position, lips in *u* | u + U+0306 | breve double duty (§2.1) |
| ṛ | velar r | r + U+0323 | calibration class (F4) |
| ḷ | tongue-tip above alveoli, back free | l + U+0323 | calibration class (F4) |
| ɵ | between *o* and *u*, long | U+0275 | atomic |
| x˙ | *ich* (vs. x = *Bach*) | x + U+02D9 | palatalization series member |

### 2.3 Letters — small-cap sorts (base codepoints PROPOSED)

The key glosses ᴀ ᴇ ɪ jointly as "obscure vowels (short)"; ʟ merely shares the
shape family. Glyph identities are settled; the **base codepoints below await
the editor's stamp**, because the small caps are where lookalike drift
genuinely threatens:

| Glyph | Codepoint | Drift hazard |
|---|---|---|
| ᴀ | U+1D00 | |
| ᴇ | U+1D07 | |
| ɪ | U+026A | IPA block, not the "Latin Letter Small Capital" run — invites later "fixing" to a lookalike |
| ʟ | U+029F | same hazard |
| ʟ̣ | U+029F + U+0323 | inherits the ʟ question |

### 2.4 Letters — unmarked ASCII with non-obvious values

`c` = English *sh*; `j` = French *jour*; `x` = *Bach*; plain `s`; `h` (a
licensed sort in native words — editor, corpus scale). All invisible to any
glyph-pattern detector by construction (`CLAUDE.md`, "Transcription Detection").

### 2.5 Series structure (key doctrine, stated outright)

Four laterals **l ḷ ʟ ʟ̣**; three rhotics **r ř ṛ**; proportional velar pair
**q : k :: g̣ : g**; seven-member palatalization series **n x d t s č ǰ + ˙**;
six-member spirant series **b p d t g k + '** (fourth member's print damaged —
F10); diphthongs compose productively from any vowel + i/u, the ᵉi row adding
the rising case — prominence on the closing element, opening element cast
superscript.

### 2.6 Mark–base licensing (editor-supplied)

Which bases a mark may sit on. Recorded because these decide cases the raster
cannot: `i` loses its dot under any above-diacritic, so printed **ĭ** is a dotless
i with a breve — the same letterform a small-cap **ɪ** carrying a breve would
present. No magnification separates them; only the constraint does.

| Mark | Licensed on | Never on |
|---|---|---|
| breve **U+0306** | `u` (ŭ, §2.2); `i` (ĭ — editor-confirmed on `1-074`, "Am-g̣roˊkĭ", and on `1-067` L15, "Ñĭroˊn") | **everything else.** The obscure-vowel series **ᴀ ᴇ ɪ ä** for the reason below; `j` because the marked sort is **ǰ**, j+U+030C (§2.2), and a breve there is a misread caron |

**The list is closed, and enforced as such.** `detectors.MARK_LICENSE` holds the
allow-list, `harness corpus normalize` exits 1 on a violation, `harness tei validate`
raises it as an ERROR, and `harness ocr restore` refuses to write. Not a worklist item:
an unlicensed mark is a sequence the notation does not contain, so unlike a lookalike
there is no reading for a human to weigh, and nothing is pre-empted by refusing it.
No tool rewrites one, though — choosing the intended glyph is adopting a glyph
identity, which is the editor's act.

`j` is why this is code and not just a table. `1-073` sets ǰ three times, in `Neǰ-`,
`Ñeˊrg̣eǰ-` and `Quˊuleǰ-`; a reading pass took the mark for a breve on the grounds
that it looked rounder than the č on the same page, and review corrected two of the
three and missed the third. One page, one form, three occurrences, and the
inconsistency survived a human pass because nothing compared them to each other.

The exclusion is not arbitrary, and the reason is book-internal: the p. 10 key
glosses ᴀ ᴇ ɪ jointly as "obscure vowels (**short**)" (§2.3) and ä as their long
counterpart (§2.2). The series already encodes length, so a length mark on any
member would be either redundant or contradictory. In the editor's phrasing,
**none of the schwas are shortened**.

Consequence for keying and for triage: a breve above a dotless i-form is **ĭ**,
never ɪ̆, and `ɪ` + U+0306 anywhere in the corpus is an error rather than a
reading. Note this is a *licensing* rule about the notation, not a rule for
interpreting the text — nothing here may be extended by analogy. The breve is
"productive" as a length mark (§2.1), so further bases may be licensed, but only
on attestation the editor has stamped, never on symmetry.

### 2.7 Pre-reform Russian sorts (SETTLED)

The book is 1904–1909, so its Russian is pre-1918 orthography throughout. Four
letters were abolished by the reform and one position of a surviving letter
changed; all five are keyed **as printed** in ground truth. The closed list, so
that nothing is dropped by not having been looked for:

| Printed | Codepoints (lc / UC) | Name | Reform sent it to | Watch for |
|---|---|---|---|---|
| **і** | U+0456 / U+0406 | decimal i | и U+0438 | **Latin `i` U+0069.** Identical letterform in a serif face — this is the one real trap, and no magnification resolves it. Position decides: pre-reform і appears before another vowel or before й (сіянie, Россія), so і inside a Cyrillic word is U+0456, never Latin. |
| **ѣ** | U+0463 / U+0462 | yat | е U+0435 | ь U+044C and ъ U+044A — same ascender-plus-bowl skeleton, ѣ adding the crossbar. Common, so expect it: хлѣбъ, бѣлый, дѣло, сѣверъ. |
| **ѳ** | U+0473 / U+0472 | fita | ф U+0444 | Latin `o`/`0` and Greek θ. Greek loans only, so rare here: ариѳметика, Ѳеодоръ. The hazard is reflex, not eyesight — reading it and keying the modern ф. |
| **ѵ** | U+0475 / U+0474 | izhitsa | и U+0438 | **Latin `v` U+0076**, and Cyrillic у. Nearly extinct by 1900 and confined to church-Greek words (мѵро, сѵнодъ), so any ѵ-shape wants a second look before it is keyed as one. |
| **ъ** *word-final* | U+044A / U+042A | hard sign | dropped in this position only | ь U+044C. Distinguished by the ascender alone. |

Two consequences the table exists to prevent.

**The hard sign is not an abolished character** and must not be treated as one.
U+044A is live modern Russian as a separator (объектъ → объект); only its
*word-final* occurrence after a consonant is the pre-reform marker. So a grep for
the bare character is not a pre-reform detector — the position is the signal, which
is why this row reads "word-final" and the others do not. `1-151` prints **лахтакъ**
(glossed "ground-seal" / "thong-seal"), keyed with the ъ.

**Three of the five are cross-script lookalikes**, і and ѵ against Latin `i` and
`v` and ѳ against `o`. §3's table traps Latin-for-notation confusions inside Tier-1
spans; this is the same hazard one script over, and it is *not* covered there, since
Russian is Tier-2 and outside those greps. Nothing mechanical catches a Latin `i`
sitting in a Cyrillic word today.

Orthographic, not glyphic, and therefore outside this table but worth knowing when
reading: pre-reform adjectival genitives in **-аго / -яго** (русскаго), and
**-ыя / -ія** where modern Russian has -ые / -ие. These are spellings rather than
sorts, so they raise no keying question — they only stop a correct reading from
looking like a misreading.

### 2.8 Museum catalogue numbers — deferred, not discarded (SETTLED)

Figure captions carry AMNH accession numbers set as stacked fractions
(`70/7867`, `70/7749`). **The keying and collation passes never read them. They
are keyed as the fixed literal `(??/????)`**, whatever the printed digits.

This is a statement about *which pass* does the work, not about the numbers being
unimportant. The AMNH catalogue is a live external resource, and an annotation
pass may well resolve figures against accession records — in which case the right
way to obtain the number is to query the catalogue, where it is authoritative and
checkable, rather than to transcribe digits off a raster and hope. Transcribing
here would produce an unverified string that *looks* resolved and so never gets
looked up.

The raster argues for deferral on its own. The denominator sits below the line's
segmentation box in small type, so a line crop clips it: `1-151` line 37 reads
`1887`/`1749` off the crop against `7867`/`7749` off the full page. Two readings
of the same digits, from the same page, differing in the first digit — and the
first reading would have been unfalsifiable within the corpus.

So `(??/????)` is not a gap in the reading; it *is* the reading, and it is the
marker that makes the deferred work findable later. The token is already in the
notation keyboard (`?`) and universal in `data/readings.md`. It was, until this
revision, in no normative document — practice without a rule, which is how a pass
talks itself into reading them.

### 2.9 Spacing before punctuation — English, not French (SETTLED, editor ruling)

**The book sets French spacing and the corpus does not reproduce it.** Brill puts a
thin space before `;` and `:` — `purpose ; but`, `substance ;”`, `solstices ; but`
on `1-073` alone, and the gap is unambiguous at 2× and consistent across every
occurrence. Key **English spacing**: `purpose; but`, no space.

This is the one place the "reproduce the print" rule for English prose is
deliberately overridden, so it needs saying plainly rather than being left to each
pass to rediscover. The reason it is not a loss: a thin space before a semicolon is
a *typesetting* convention with no lexical content, it survives nowhere in the
book's own meaning, and reproducing it would put a space inside every affected token
for every downstream consumer — tokenizers, the lexicon check, search — in exchange
for information a reader can recover from the facsimile at any time. Curly quotes
are reproduced because conflating `’` with a true apostrophe destroys a distinction
the notation uses; a thin space destroys nothing.

It is also not a licence to normalize spacing generally. Word spacing in justified
setting varies wildly on these pages and is likewise not reproduced, but **an
interword space that is present is keyed and one that is absent is not** — `i. e.,`
keeps its space because the print has one, and nothing here permits closing it up
to `i.e.,`.

**Sentence spacing is the same case as the semicolon, not the general one.** The
book sets a double space after a sentence-ending period (period-space-space), a
typesetting convention exactly as lexically empty as the thin space before
`;`/`:`/`,` — it survives nowhere in the book's meaning, and unlike interword
justification gaps it is not variable page-to-page evidence of anything, just a
fixed compositor habit. Key single-space, same reasoning as the semicolon rule.
French spacing before a comma is the same case again wherever it turns up. All of
this is mechanical and print-invariant, so none of it is left to per-page
judgement: `harness corpus normalize` collapses a run of 2+ spaces between two non-space
characters to one and strips any space immediately before `;`/`:`/`,`,
corpus-wide, and `--check` exits 1 on drift — the same enforcement tier as NFD, not
the lookalike worklist, because there is no reading to adjudicate.

### 2.10 Footnote markers — the superscript sort, never the ASCII digit (SETTLED)

The book anchors footnotes with a raised digit, printed twice: once at the
reference in the body, once opening the note at the foot. **Key the actual
Unicode superscript** — `¹` U+00B9, `²` U+00B2, `³` U+00B3, `⁴`–`⁹`
U+2074–U+2079 — never the plain ASCII digit.

This is the nastiest shape of error the project has, and it is worth saying why
rather than just stating the rule. A marker keyed `1` instead of `¹` is the
*right number*. It reads as correct in every view, and no check in §3, no
lexicon lookup and no mark licence can see it: the character is ASCII, it is not
a lookalike for anything, and it sits in a legitimate position. Nothing flags it.

**Counting is the only mechanical witness**, and two invariants hold with no
reading required, because numbering restarts on every page (confirmed across all
20 restored pages — each begins again at 1):

1. the marker values present form a **continuous run 1..N**, no gaps;
2. each value occurs **at least twice** (reference + opener).

`detectors.footnote_report` implements both, `harness corpus normalize` reports them
corpus-wide, and `harness proposal check` reports them per proposal. **Report-only
in both**, at the `lookalikes` tier rather than the blocking one: a note whose
reference and text straddle a page seam breaks the pairing with nothing miskeyed,
so a hit is a page to look at. A proposal that fails either invariant carries a
page-level `footnotes` explanation instead.

A third check catches the **half-open pairing** — one marker keyed as a
superscript, another on the same page as a plain digit. A line opening with a
bare digit then a space is flagged, **but only once a superscript has already
appeared earlier in reading order**. The superscript is what establishes the
page's own convention; against it a bare digit is an inconsistency rather than a
guess.

Stated once and scoped precisely: **there is no plain-digit convention for
footnote markers anywhere in this corpus, and no page is a precedent for one.** A
marker is the superscript sort, at the reference and at the opener alike, and **a
detector firing on your output is the rule working, never a convention you have
joined.** (A reader once cited this section's own worked example of the defect —
`2-034`, since repaired — as a sanctioned precedent; the story is
`docs/decisions.md`, "The reading-discipline record".)

That is a rule about **markers**, and it must not be read as a rule about digits.
A plain ASCII digit is entirely ordinary wherever it is not a footnote marker —
a quantity in running prose (`1-053`'s "…Nordquist, / 2 houses)."), a numbered
list item (`2. Čačanloˊrg̣ɪn` — digit + **period**, which the check deliberately
does not match), a folio, a cross-reference, a catalogue number. **A line
beginning with a plain digit is not by itself anything**, which is exactly why
the third check waits for a superscript to appear first: without that condition
it would fire forever on `1-053`'s wrapped "…Nordquist, / 2 houses)." — a page
printing no footnote 2 at all — and a permanent known-false hit is precisely the
noise that buries real signal.

**A figure sub-part locant is not a marker** — `(Fig. 17, f¹)`, a raised numeral
picking out one labelled detail of a plate. Key it as printed; it anchors no
note, so it is printed once, and the counting excludes it rather than reading it
as an unpaired marker. The exclusion is narrow, and taken from what `gt/ocr/`
attests: a **lone letter** carries the superscript and a close-paren follows.
Both halves are load-bearing — the same store holds real markers on a
multi-letter word before a paren (`Ciˊṛluk⁶)`) and spaced off the word
(`Nelson ¹)`), and either half of the rule alone would swallow one of them. The
locant is still *reported*, at the advisory tier: an exclusion that says nothing
is indistinguishable from a check that never ran.

**Spacing, and it runs opposite ways at the two ends.** A body reference sets
**tight** against whatever precedes it — `mouth.¹`, `tales¹`, `Steller,¹`,
`“alien food.”²` — and a note opener sets **marker, space, text**: `¹ See, for
instance`. Measured over `gt/ocr/`: 225 tight against 13 spaced in the body, 208
spaced against 1 tight in openers. Both leans are the print's.

Mechanical, so it is not a reader's judgement: `harness corpus normalize` reports
both and `--convert` writes them, the same standing as §2.9. Key it right anyway —
a rule the tool repairs silently is one nobody learns.

**The draft is not a witness to a locant.** Over the fifty-page run of 2026-08-07
the recognizer garbled them in three directions: an italic letter read as a digit
(`b` → `6`, sixteen times across eleven pages, four of them on `1-258` alone), and
a raised numeral read as punctuation (`a¹` as `a’)` and as `a°)`, both on `1-241`).
Two of those directions produce something that still parses as a locant, so nothing
downstream can flag them. Read a locant off the raster. A digit interrupting a
letter series — `(Fig. 118, a, 6)` — is the draft's error until the page says
otherwise.

**Position on the page is not used by the checks, and must not be** — the scan
is not consistent enough for the *detectors* to carry geometric judgement, and
a half-footnote page would defeat any fixed cut. That is a constraint on the
tooling, not on a reader: someone looking at the whole page may of course use
where the ink sits — the opener block is still below the body wherever the
boundary falls, and a raised digit mid-sentence is a reference.

**Known limit.** A page keying *every* marker as ASCII has no superscript to
establish a convention, so it has no gaps, no singletons and no flagged opener,
and passes clean. That was `1-073` and `1-151` before repair, and it is what a
freshly recognized page looks like, since CATMuS emits plain digits. Catching
that case needs a witness this check does not have; do not close it by dropping
the prior-superscript condition.

**Found by the check, in restored ground truth**: `1-048` (6 markers, one of them
absent altogether), `1-053`, `1-073` (3), `1-151`, `2-034`. Four of those five
were invisible to the counting invariants alone.

### 2.11 The dash — em, U+2014, and only that (SETTLED, measured)

The book sets **one dash: `—` U+2014**. Measured over `gt/ocr/`: **36
occurrences across 18 pages, zero U+2013 en dashes, and zero double-hyphen `--`
sequences.** There is no second dash to choose between, so this is a lookup and
not a judgement.

It is written down because it was not, and the cost showed up immediately. A
reader keying `2-035`'s signature line had no rule to reach for and went hunting
through the ground-truth store for precedent, settling it against
`gt/ocr/chukchi-3-119.xml` and `chukchi-3-135.xml`. The reading it arrived at was
correct and the two files do attest it — but **a reader who must derive a
convention from other pages is doing corpus archaeology in the middle of a
single-page pass**, and the next one may sample two pages that disagree, or one
that was wrong. A settled sort belongs in this file, where it costs one look.

Do not key `-` U+002D or `--` for a dash: inside Tier-1 the hyphen is
load-bearing (§2.1) and a dash spelled as one is unrecoverable.

**Spacing reproduces the print** and is not normalized, the same position §2.9
takes. Three forms occur, and all three are as-set:

- **Run-in section heading** — `LANGUAGE. — The Chukchee language is rich…`,
  `VI. — HUNTING AND FISHING; WAR.` Spaced both sides. This is how the book marks
  a heading that shares its line with the text, so the dash is structural and a
  collation pass reads a heading off it.
- **List introduction** — `The villages on the Arctic coast are as follows: —`,
  trailing at the line end. Spaced left, nothing right.
- **Quire mark / signature line** — `82—JESUP NORTH PACIFIC EXPED., VOL. VII.`
  **Unspaced**, unlike the other two. Attested on `3-119` and `3-135`; the number
  is the signature, not a folio, and `harness tei context` reads that zone for
  the printed folio, so a mis-keyed dash there is not merely cosmetic.

### 2.12 Roman numerals and folio slots — plain ASCII, always (SETTLED, editor ruling)

**Every roman numeral in the book is keyed in plain ASCII capitals**, whatever
the setting. `Plates V, VII, XIV`, `VOL. VII.`, `Fig. 2`, a folio, a signature
number — all ASCII. The book sets roman numerals as typographic small capitals
routinely, and that is an English-register display convention with no bearing on
the notation. §2.3's small-cap sorts are licensed **only for `ᴀ ᴇ ɪ ʟ` inside
Tier-1 forms**, and there is no small-cap `V` or `X` in the inventory at all, so
the question of whether a given numeral "looks small-cap-ish" cannot change what
is keyed. Do not measure letter heights to settle it; there is nothing to settle.

**The two folio-bearing slots are equally mechanical**, and readers keep treating
them as puzzles:

- **A bracketed folio at the foot of a chapter opening** — `[1]`, `[115]` — is
  the book's regular form and appears throughout. Key it as **plain ASCII digits
  in brackets**. The segmenter classes it `QuireMarksZone`, `tei context` reads
  that zone for the printed folio, and `context.APPARATUS_ZONES` drops it from
  the collation draft, so it is apparatus rather than text.
- **The signature line's leading number** — `82—JESUP NORTH PACIFIC EXPED., VOL.
  VII.` — likewise, plain ASCII digits. It is practically identical on every page
  that carries one and is dropped from everything downstream.

**One case is genuinely ambiguous and it is page 1**, where the arabic `1` is set
as a bare serifed stem indistinguishable from a roman `I`. It is a digit, on the
same rule as everything above. Nowhere else does the question arise, and a reader
spending a 4× look on either slot is spending it in the wrong place.

### 2.13 Run-in section headings — key the setting (SETTLED, editor ruling)

The book sets a run-in heading (§2.11's `HEADING. — text`) two ways, and the
difference is structural rather than decorative:

| printed as | level | key it as |
|---|---|---|
| small capitals — `Aɴᴄɪᴇɴᴛ Hᴀʙɪᴛᴀᴛ. —` | second | **plain ASCII capitals**, `ANCIENT HABITAT.` |
| italic title case — `System of Winds. —` | third | **title case as printed**, `System of Winds.` |

Neither is a Tier-1 question. §2.3's small-cap sorts are `ᴀ ᴇ ɪ ʟ` inside Tier-1
forms only; there is no small-cap sort for the other letters, so nothing here ever
licenses a small-cap codepoint in English text — the same ruling §2.12 makes for
roman numerals, reached the same way.

**The error runs one way, and it is a shape error.** Four second-level headings
were keyed in title case — `1-043`, `1-062` twice, `1-073` — because a small-cap
setting has a full-height initial and reads as an ordinary capitalized word until
the rest of the letters are compared against it. No heading has ever been keyed
the other way. So the check is the same contrast discipline §5.2 asks for: hold
the second letter against the first on the line you are already keying. One look,
no zoom.

**The printed ToC is not a witness to a heading's existence.** `System of Winds`
is set on `2-046` at folio 320 and appears nowhere in the printed contents (p. vii,
scan `1-009`), which runs `Other “Beings”` 314 straight to `Monsters` 323. The
omission is the book's. It is carried in `data/toc.json` as `chXII.11a` with an
`editorial` field recording that, so that an entry added on an editor's ruling is
never indistinguishable from one the book printed. A heading absent from the ToC
is therefore not suspect and is never to be retitled, demoted or dropped to make
it match one: key what is set, and say in your report that you found no entry.

### 2.14 The printer's errors — key them, with one exception (SETTLED, editor ruling)

**A printer's error is keyed as printed, and `gt/ocr` never repairs the book.**
**It is a letter or a word — never a mark of punctuation**, which is a blot and is
keyed as nothing, class `artifact`.
Three stand in `gt/ocr` today, each re-read out of the store: `1-087` L17
`spririts`, `1-090` L38 `Government, to wishing breed reindeer`, `1-094` L5
`fawns-kins`. Note the setting on the line and go on. The collation pass corrects
it visibly, where the print survives beside the correction; a silent repair here
would leave neither.

The reason is what the store *is*. `gt/ocr` is line images paired with their text,
so every character that disagrees with the raster teaches a recognizer something
false — and a near-miss like `spririts` is exactly the shape a model will learn.

**Wear is not a letter (SETTLED, editor ruling).** A sort that printed thin, broke,
or abraded is keyed as **the letter the compositor set**, never as whatever the
surviving shape resembles. An `r` worn to a bare stem is an `r`, not `ı`. This is
not an exception to keying what is printed — it is what keying what is printed
*means*, because the compositor set a
letter and the wear happened to the impression of it. Substituting the lookalike
mints a glyph identity out of damage, which is the firewall's whole subject, and in
`gt/ocr` it does the exact harm the paragraph above describes: it teaches a
recognizer that a damaged `r` is a different character.

Note the wear on the line, class `artifact`, and key the letter.

The register above carried a fourth entry, `1-100` L53 `eaıly`, described as
verified against the raster. **It never was.** `gt/ocr/chukchi-1-100.xml` reads
`early` and contains no dotless i anywhere: the entry wrote up a reading the
adjudicator had already corrected, as though it had been ratified. It then did
what a false register entry does — `1-107` L36 was keyed `aıe` on its authority,
and the same correction had to be made a second time.

So a register here is checkable against `gt/ocr` or it is not evidence, and the
three entries above were re-read out of the store, not recalled.

**The one exception is a form that is contextually Tier-1 — a gloss, a native
proper name, a word in a numbered vocabulary — carrying something the keying spec
does not contain at all.** A diacritic outside the §2.1 mark set. A plainly
polysyllabic form with no stress mark anywhere. A base the inventory has no sort
for. This is narrower than "looks wrong": the notation is a closed set, so a form
inside it that merely surprises you is evidence, and a form carrying a mark the set
does not have is a compositor's slip with no reading to preserve.

`1-099` L13 prints `Kuvár` — an acute over the vowel, in a personal name. §2.1 has
no acute. §3 already lists the spacing acute U+00B4 as a trap for U+02CA; this is
that trap in the form NFD leaves behind, `a` + U+0301, which the table does not
name. The store holds `Kuvaˊr`.

**The reason the asymmetry exists is that Tier-1 glyphs are not only training
data.** `proposal marks` computes its corpus percentages from `gt/ocr` and
`concordance.md` treats it as the attestation set, so keying the slip would enter
"acute over a vowel" into the evidence as a real occurrence and every later reader
would be measured against a distribution containing it. An English typo enters no
such table and costs one wrong training pair.

**If you are reading a page, this is a `note`, not a correction.** You can see that
the mark is outside the set — that is a fact about the spec in front of you. You
cannot see what the form should be instead: `gt/ocr` is closed to you by the guard,
which refuses it saying that deriving a convention from a neighbouring page is what
the firewall forbids. So key what is set, and say in the line's `note` which
provision it falls outside and what you think it stands for. That is a complete
piece of work, and it is what `1-099`'s reader did.

**The correction is the adjudicator's**, made at the review server where the other
occurrences can actually be counted, and licensed by occurrences already in
`gt/ocr` and nothing else — not by expectation of what the notation should contain,
not by a neighbouring page's unratified reading, not by a single other attestation.
A form the corpus holds once is keyed as printed.

**Nothing catches this mechanically, and the reader's flag is the whole detector.**
`a` + U+0301 appears in no table — not `INVENTORY_CHARS`, not `LOOKALIKES`, not
`MARK_LICENSE` — and `unlicensed_marks` inspects only marks that *have* a licence
entry, so it reports a licensed mark on a wrong base and says nothing about a mark
it has never heard of. `corpus normalize` exits 0 on the proposal carrying `Kuvár`.
A raised or overset mark you cannot place in §2.1 is therefore a `note`, every time,
whatever the gates say.

## 3. Forbidden lookalikes — unconditional corpus-wide greps

| Codepoint(s) | Trap for |
|---|---|
| U+00B4 ´ | U+02CA |
| U+2019 ' , U+2018 ' , U+02BC ʼ, U+02BB ʻ | U+0027 (U+2018 esp.: turned-comma spirant shape, F10) |
| U+00B7 · (middle dot) | U+02D9 |
| U+0121 ġ, g + U+0307 | g + U+0323 |
| U+02E2 ˢ | U+1D4B, U+1D49 |
| U+2091 ₑ | U+1D49 |
| U+04E9 ө (Cyrillic) | U+0275 |
| U+2010 ‐ | U+002D |

Any `ġ` surviving in working documents is the dot-above transmission stand-in
for g̣: **annotate in working docs, correct in normative ones**, changelog
either way.

## 4. Validation scripts (all print-compliance, never inference)

1. Stress culminativity: ≤1 U+02CA per word.
2. U+0027 licensing: post-{b p d t g k} or V_V only; any other in-form
   position is unconditionally an error.
3. U+1D49 not immediately before `i`: unconditional error.
4. U+1D4B immediately before `i`: review-flag.
5. The §3 lookalike greps, corpus-wide, unscoped.
6. NFD conformance at export.
7. Per-language frequency table of the seven lateral/rhotic sorts, once
   keying runs — the mechanical F4 resolution.

**Two-scope dashboards.** Collation-stage TEI reproduces Tier-1 draft text
verbatim (harness rev 2) and will trip scripts 2 and 5 inside those spans *by
design*. GT: zero tolerance. Collation output: that noise **is the to-key
worklist**, not a defect.

**U+0027 (spirant or pause) is not a live candidate in practice.** Both are licensed
by the printed key, both are named in §2.1, and neither has ever once been the correct
reading anywhere in the restored corpus — every raised mark examined in a licensing
environment that superficially fits spirant or pause has turned out, on adjudication,
to be stress. Do not propose U+0027 in a Tier-1 span. Read every raised mark as stress
(U+02CA) by default, full stop, including in V_V position, including immediately after
b/p/d/t/g/k. This is not a 99%-vs-1% weighing exercise to perform per instance — it is
the working assumption, and a proposal should default to it without restating the
V_V-or-post-consonant environment check as if it were live evidence for apostrophe.
The check for the environment still matters for *validation* (script 2, below) — an
`U+0027` that turns up unlicensed is still a real error to catch — but that is a
different question from what a *model* should ever propose from a raster reading.
If an apostrophe is ever genuinely confirmed by a human against the raster, that
page is the corpus's first attested instance and the note should say so explicitly,
because it would be a surprising, citable finding — not a routine call.

## 5. Reading discipline — recurring misreading classes

Shared by both passes: collation keys Tier-1 spans character-by-character off
the raster exactly as the ground-truth rebuild does (transcriber harness rev
2), so a misreading class caught in one is worth guarding against in the other.
Every item is a record of an error that actually happened, most more than once,
and each has one fixed shape — **the rule, the instrument, the record** —
because the batch history shows that restating a class more loudly changes
nothing: readers have quoted an item verbatim, named its trap word, and
committed the error on the same page. What works is running the item's
*instrument*, so that is what each item leads with after the rule. The full
case files behind every record line are `docs/decisions.md`, "The
reading-discipline record".

**Run this list as a per-line pass over every Tier-1 span, zoomed or not** —
never as background awareness. `harness ocr corrections` is the standing way to
ask which classes are still live, with two cautions: unscoped it reports
classes later rules made impossible (use `--since` a date after the rule you
care about), and it undercounts by construction, since a repair made with
`proposal set`/`replace` before adjudication leaves no diff. As of 2026-08-02,
scoped past 2026-07-31, the only class recurring across pages is §5.2's `i`→`ɪ`.

**Every frequency below is Chukchee's.** The numbers are pooled over a store
that is overwhelmingly Chukchee, so where the text explicitly glosses a form as
another language — Koryak, Chuvan, Eskimo — **the priors do not apply. Transcribe
what is printed, with extra care, and say in `note` that the form is glossed as
that language.** Such forms are rare, which is the hazard: a Chukchee-looking
suffix on one invites a correction toward a distribution it was never drawn
from.

**And every one of them moves.** The store is mid-rebuild — pages leave it to be
re-read and come back — so any absolute count written here is a snapshot that has
already drifted, and one was quietly wrong for a while by being labelled a
word-initial split when it was a total. So the shape of a claim in this section is
the *direction* of a lean plus the verb that recomputes it: `harness lexicon
marks` for bare-vs-marked per base letter, `lexicon suffixes` and `lexicon
digraphs` for affixes, `harness proposal marks` for a page against the store.
**Cite the verb, not a remembered number**, and read `band_n` before believing a
band: a prior backed by one page is a prior backed by one page.

0. **Where a reading and this file disagree, the spec wins and the
   disagreement is flagged for a human — never resolved by further zooming.**
   Magnification cannot settle a question that isn't optical, and a detailed,
   self-consistent note citing its own close reading is exactly what a
   confident guess looks like. Citing the firewall to justify a novel sort
   inverts it — the firewall forbids *adopting* a glyph on a model's
   authority; it does not forbid the printed key or an editor ruling from
   binding.
1. **Dropped dot below `g`: a bare Tier-1 `g`/`G` is the exception that needs a
   reason, never the resting state.** `g̣` (g + U+0323) is **the large majority
   of Tier-1 `g`** — around 87% as the store stands and never yet a minority at
   any size it has been; run `harness lexicon marks` for today's share rather
   than quoting this sentence. And `-g̣ɪ`/`-g̣ɪn`/`-g̣ɪt` are common **noun-forming suffixes** in
   every register (`va'ɪrg̣ɪn`, "spirit") — so a word ending plain
   `-git`/`-gin`/`-gɪn` is presumptively wrong before the raster is even open.
   The dotted and undotted sorts are the same letterform, so **absence is not
   observable in isolation**: a "no dot" reading at any magnification is
   answering a question the image cannot answer, and must clear a higher bar
   than a "dot" reading, because the base rate runs the other way. "Confirmed
   at 4×" is what both wrong readings said.

   *Instrument.* Don't inspect a `g` — **contrast** it against a plain English
   `g` on the same line where one exists, and name the contrast word in `note`
   (a technique, not a requirement: many lines offer none; then read, flag,
   move on — and the same goes for every absence-shaped call here, §5.2, §5.3).
   The systematic net needs no raster: `harness proposal marks` — its `rare`
   arm names every occurrence of a form the corpus almost never sets, its
   `conflict` arm finds one word spelled two ways against ground truth; pass a
   whole batch's refs at once, since one page is rarely a sample worth a
   verdict and the pooled `ALL` row separates one reader's slip from a
   systemic lean. `detectors.SUFFIX_MARK_DROPS` (a data table — new measured
   skews are rows to add) flags any bare-`g` token ending `-gɪ`/`-gɪn`/`-gɪt`,
   runs unconditionally inside `proposal check`, report-only. The
   `-hɪn`/`-lɪn`/`-lhɪn` family is comparably common and takes the same
   "assume it, don't bare-key it" discipline; `harness lexicon suffixes` /
   `lexicon digraphs` measure such claims rather than asserting them.

   *Record.* The most-corrected class in the project's history: `1-074` ×2,
   `3-004` (nearly every headword — the page's largest error class), `3-005`,
   `2-033` ×4, `2-035`, and `1-042` at adjudication — five restatements
   survived, including a reader that quoted the prior and the trap word, then
   bare-keyed it on the page it was writing about. Both `2-033` and `2-035`
   were finally settled by the contrast method (`danger`, `representing`)
   after 4× stares had failed; `1-042`'s was caught by `proposal marks` after
   four clean mechanical gates.
2. **`ɪ` (U+026A) vs `i` vs `r` — the leading residual class, and the tell is
   that the reader reports checking it.** The base rate runs against plain `i`
   — Tier-1 `ɪ` outnumbers it across the store, and `-ɪn` / `-ɪt` are by a long
   shot the commonest suffixes in Bogoras's forms, `-ɪn` topping the suffix
   table outright, while plain `-in` is attested but rare and chiefly in proper
   nouns and words of foreign origin. So a suffixal dotted `i` is the reading
   that needs a reason, and a page keying mostly `i` wants a second look before
   anyone opens a scan. Three sub-cases, none caught by shape alone:
   - **`ɪ` vs `ĭ`** is a §2.6 licensing fact, not a shape call: the breve is
     licensed on `i` and never on the obscure-vowel series, so a dotless vowel
     carrying a genuine breve is `ĭ`, full stop — a rule lookup, not a look.
   - **Word-initial capital-shape vs small-cap `ɪ` — read it, and do not argue
     it from a frequency in either direction.** Position splits this in two, and
     only one half is settled. Word-*medially* an ASCII capital is essentially
     never right, by a margin wide enough that `detectors.MEDIAL_CAPS` refuses
     one outright rather than flagging it. Word-*initially* both are ordinary
     and **the store does not hold enough initials of either kind to support a
     prior**: `proposal marks` says so in its own output, where the word-initial
     bands rest on one ground-truth page for `ɪ`/`I` and on none at all for
     `ᴇ`/`E` — which is what the `?` in its `outside` column means. A page-level
     lean on this contrast is therefore not evidence, and reporting one as if it
     were has already sent two batches chasing a word-initial `E` that was
     correct as keyed.
   - **`ɪ` keyed as `r`, arriving from the recognizer.** CATMuS substitutes
     `i`, `I` and **`r`** for `ɪ`, and `r` is the one that gets through — its
     error *is* ASCII, which is why the rule reads "CATMuS is not a witness to
     what any character is wherever an inventory glyph could stand", not
     "…to any non-ASCII glyph".

   *Instrument.* Contrast, as §5.1: `r` carries a shoulder, `ɪ` is a bare stem
   with serifs top and bottom, `i` is x-height and dotted, and English prose
   on the same line supplies a real `r` or `i` to hold the letter against.
   The 2:1 prior and the suffix table are the no-raster net. A confident
   negative settles nothing: absence claims about a small feature are not
   settled by having looked once.

   *Record.* `1-101`'s `Iᵋplɪˊlɪ` ×2 (word-initial, corrected to `ɪᵋplɪˊlɪ`);
   `2-033`'s `Attɪˊg̣ɪtkɪ` keyed as `Attrˊgɪtkɪ` off the machine text; four
   residuals over two 2026-08 batches caught only by the human (`2-047` ×2,
   `2-031`, `2-035`) — **every one on a line whose reader had explicitly
   narrated the check**, one writing "checked closely against the ɪ elsewhere
   on the page" and being wrong.
3. **`ä` (a + U+0308) vs. plain `a`: any bare `a` in a Tier-1 form is a
   candidate for `ä`, not a default reading.** `ä` runs under a tenth of Tier-1
   `a` (`harness lexicon marks` for today's share) — so unlike §5.1 the prior
   here is *against* the mark, and the reason to look anyway is that the
   diaeresis is small, easy to read past on a contact sheet, and has been
   missed more than once on one page. A minority sort is still a sort.
   *Instrument:* the same absence-shaped discipline as §5.1 — contrast where
   the line offers one, and the distributional arms of `proposal marks`.
   *Record:* missed more than once on the same page, off sheets rather than
   zooms.
4. **Old-style figures: the numeral `1` is x-height and dotless — easy to
   take for `ɪ` — and `0` is small and round.** CATMuS reads `20th` as `zoth`
   — evidence of how easily the class slips past a plausible-looking read,
   not evidence for any glyph, since a recognizer is not a witness to Tier-1
   identity at all.
5. **Every multisyllabic Chukchi/Koryak/Yupik word carries exactly one stress
   mark (culminative, ≤1 per word, §2.1) — a multisyllabic Tier-1 word with
   no stress mark anywhere in it is not a plausible reading, it is a red
   flag.** Not "usually", every one: before accepting such a word, ask
   explicitly where its stress mark is. If the only raised mark in it is
   keyed `'`, that is `ˊ` misread (§4 — apostrophe has never once been the
   right call).
   *Instrument:* run the "where is its stress mark" question as a real
   per-word gate, and — after writing `resolved` — **re-read `text` character
   by character against what `resolved` just concluded**: reasoning about a
   mark and typing it are two different acts, and nothing enforces that the
   second followed the first. A `resolved/text mismatch` repeating down the
   page is the tool reporting something systematic, never
   narrative-formatting noise.
   *Record:* wrong at whole-page scale once, and at single-word scale on two
   hand-keyed pages; `3-004` added the worse mode — every `resolved` field
   reasoned "→ stress U+02CA" correctly and `text` kept the literal `'` on 33
   of 71 lines, with `proposal check` reporting the exact signature
   (`in resolved not text: U+02CA`) line after line and the reader dismissing
   it.
6. **Straight quotes for English glosses.** The book sets curly `“…”`
   throughout, never straight `"..."` (§1) — so **never, ever zoom to confirm
   whether a quote is straight or curly: it is always curly**, a straight one
   in machine text is an encoding artifact, and there is nothing on the paper
   to adjudicate. Slipped through in bulk more than once, including in
   hand-keyed pages assumed authoritative for years.
   *Instrument:* `harness corpus normalize` flags a straight quote as a
   worklist lookalike; it does not auto-fix, since pairing an open quote to
   its close can require reading across lines.
7. **Medial ASCII capital where a small-cap was meant** — plain `A`/`E`/`I`/`L`
   mid-word instead of `ᴀ`/`ᴇ`/`ɪ`/`ʟ` (§2.3). `detectors.MEDIAL_CAPS` flags
   it inside `proposal check` and never auto-corrects, even when it looks like
   the one clean swap on the line: *which* small-cap an ASCII capital was
   meant to be is a reading judgement, so it only ever surfaces as a flag for
   a human.
8. **Any raised mark defaults to stress (U+02CA), never apostrophe (U+0027)**
   — §4's closing paragraph is the rule in full; don't reason about the
   licensing environment as if it were live evidence for apostrophe, and
   don't re-litigate it per page.
   *Record:* `3-005` flagged half a dozen marks as open "human calls" between
   stress and apostrophe; all were stress.
9. **Never key a codepoint the inventory doesn't catalogue: if the candidate
   isn't in §2.1–2.4, the reading is wrong far more often than the inventory
   is incomplete** (item 0). *Shape quality at magnification cannot by itself
   separate a sort from a smudge* — the argument has now been good and wrong
   (`1-048`) and bad and wrong (`1-060`), with the same ruling both times: a
   conveniently diacritic-shaped smudge.
   *Instrument:* the disposition is fixed whichever way the shape argument
   points — **key the letter as printed, put the unlicensed mark in `note`
   naming its would-be codepoint as uncatalogued, and let a human rule** —
   because the codepoint being uncatalogued is what decides it, not the ink.
   Reading against `mz/ocr/` helps here: `1-060` surfaced itself as a
   recognizer/reader disagreement instead of depending on anyone remembering
   to look.
   *Record:* `3-005` proposed U+025B in two ordinary English words (plain `e`
   printed); `1-048` `reindeér-breeding` (a type-weight tapered wedge, ruled
   smudge); `1-060` `“Chief”` (ruled smudge, with the control ˊ of
   `tɪkêˊ-vaˊg̣lɪñɪn` on the same page).
10. **No small-caps "o" exists in this notation** — §2.3 licenses small-cap
    bases only for ᴀ ᴇ ɪ ʟ. A lowercase `o` beside a small-cap ᴇ or ʟ can read
    as small-cap height at 4× purely from kerning; that is a rendering
    artifact, not a second sort.
    *Record:* `3-005` proposed the distinction inside one word (`ᴇʟO'o`);
    plain lowercase `o` throughout.

11. **A note that describes a keying decision the text does not show** — the
    inverse of §5.5's failure, and worse, because the text is *right* and the
    note argues the adjudicator into breaking it.
    *Instrument:* two cheap rules. **Before the proposal is final, re-read
    every `note` against its own `text`** — a note describing a decision the
    text does not exhibit is a defect whichever one is right, because they
    cannot both be. And **a note citing a section of this file must quote the
    sentence it relies on** — quotation is the check that "I read it" is not.
    *Record:* `2-031` keyed its footnote openers correctly as `¹ ² ³` and
    attached notes claiming ASCII digits had been keyed "per the precedent
    recorded for 2-034" — text repaired mid-pass, note never re-read. The
    first diagnosis blamed the reader and was wrong: §2.10 then printed the
    defect as a worked example, and a record of an error read as a statement
    of a convention. **When a reader misapplies a rule, read the rule before
    concluding it was ignored.**

12. **A note may state what you saw; it may not state what another witness
    said unless that witness was actually consulted.** The other half of
    §5.11 and harder to catch: the reading is correct, the check passes, and
    the note supplies a *checkable* corroboration that turns out to be false
    — which is exactly the thing that stops the next reader looking, and it
    will be believed, since the text beside it is right.
    *Instrument:* the witnesses are one command away — `harness ocr lines REF
    --store mz` for what the machine actually read, a zoom for a measurement
    — so consult before quoting, or don't quote. And **write notes in
    codepoints, not glyphs** (`U+0323 COMBINING DOT BELOW`, not the
    character; describe a spacing rather than exhibiting one): reproducing a
    glyph in prose is probabilistic the same way keying it is, and `corpus
    normalize` runs over `note` like any other field — intentionally, not as
    a trap to route around — so an exhibited example can be silently
    rewritten into its own counterexample.
    *Record:* two instances in one batch, different readers — `1-022`'s
    height "measurement" for `Plates V` (false: the `v` is x-height, the
    small caps visibly taller), `1-021`'s "CATMuS read it as an apostrophe"
    (false: the machine text contains none).
