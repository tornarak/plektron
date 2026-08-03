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
- **ASCII policy, scoped to Tier-1.** Inside `ckt`/`kpy`/`ypk`, U+0027 and U+002D
  are the only apostrophe and hyphen, and the lookalike greps (§3) run there.
  Rationale: ASCII is what every keyboard emits, hence drift-proof; a
  modifier-letter codepoint invites conflation with a true apostrophe at every
  entry point — and inside a Tier-1 span the apostrophe is phonetically
  load-bearing, since U+0027 *is* the spirant and pause mark rather than a
  lookalike for one. English prose reproduces the print, **curly quotes
  included**: the book sets them, nothing there is load-bearing, and forbidding
  them would reject correct text. `validate.py`'s `FORBIDDEN_PROSE` and its
  scoped greps are the enforcement.
- **Keying reproduces print.** The collation pass may modernize glossed Russian
  (harness rev 2); ground truth does not — pre-reform Cyrillic sorts are keyed as
  printed. See §2.7 for the closed list and what each is confusable with.
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
| breve **U+0306** | `u` (ŭ, §2.2); `i` (ĭ — editor-confirmed on `1-074`, "Am-g̣roˊkĭ") | **everything else.** The obscure-vowel series **ᴀ ᴇ ɪ ä** for the reason below; `j` because the marked sort is **ǰ**, j+U+030C (§2.2), and a breve there is a misread caron |

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

`2-034` was **the defect this check was written against, and it has since been
repaired**: it printed body reference `dances.¹` against opener `1 See Chapter
XIV.`, and `gt/ocr/chukchi-2-034.xml` now keys `¹ See Chapter XIV.` like every
other opener in the store. Both halves of that sentence are here because the
first half alone misled a reader. In a 2026-08 batch a page was keyed with plain
ASCII openers and the proposal justified them as "the precedent recorded for
2-034 in keying_spec.md §2.10" — reading a *worked example of the error* as a
*sanctioned convention*, and predicting that the detector would flag its own
output and that this would be correct behaviour. **A detector firing on your
output is the rule working, never a convention you have joined.**

So, stated once and scoped precisely: **there is no plain-digit convention for
footnote markers anywhere in this corpus, and no page is a precedent for one.** A
marker is the superscript sort, at the reference and at the opener alike.

That is a rule about **markers**, and it must not be read as a rule about digits.
A plain ASCII digit is entirely ordinary wherever it is not a footnote marker —
a quantity in running prose (`1-053`'s "…Nordquist, / 2 houses)."), a numbered
list item (`2. Čačanloˊrg̣ɪn`), a folio, a page cross-reference, a catalogue
number. **A line beginning with a plain digit is not by itself anything**, which
is exactly why the third check above waits for a superscript to appear first;
without that condition it would fire forever on the settlement lists it was
found on. The error in the batch above was not keying a digit — it was keying a
*footnote opener* as one and calling that sanctioned.

The condition is not a softening. Without it the rule fires on ordinary prose —
`1-053` wraps "…Nordquist, / 2 houses)." onto its own line mid-gazetteer, on a
page that prints no footnote 2 at all, and that hit would report forever. A
permanent known-false hit is precisely the noise that buries real signal.

Numbered lists do not collide either way: the book sets those as digit +
**period** (`2. Čačanloˊrg̣ɪn`, 27 in the restored corpus), which the rule
deliberately does not match.

**Position on the page is not used, and must not be.** "Openers sit at the foot"
is tempting and wrong — some pages are half footnotes, and the scan is not
consistent enough to carry that kind of geometric judgement.

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
2), so a misreading class caught in one is worth guarding against in the
other. Below is the checklist form; each has been the *actual, corrected*
error at least once, more than once for several — this is not a hypothetical
list of things that could go wrong, it is a record of things that did, kept
general on purpose rather than tied to a specific page, because the class is
what recurs, not the instance.

**`harness ocr corrections` is the standing way to ask which of these are still
live**, aggregating what adjudicators actually changed across every reviewed
page. Two cautions before believing a number out of it. It spans this project's
own history, so an unscoped run reports classes later rules made impossible —
its top entry is 117 straight apostrophes on two pages keyed before a bare one
became an unconditional error; use `--since` a date after the rule you care
about. And it undercounts by construction: a repair made with `proposal
set`/`replace` before adjudication leaves no diff at all, so it measures what
reached the adjudicator, not what the reader wrote. As of 2026-08-02, scoped
past 2026-07-31, the only class recurring across pages is §5.2's `i`→`ɪ`.

0. **Prefer the spec over a confident-sounding raster impression.** A reading
   that contradicts this file is not evidence the inventory is incomplete —
   magnification cannot settle a question that isn't optical, and a detailed,
   self-consistent note citing its own close reading is exactly what a
   confident guess looks like. If a reading and the spec disagree, the spec
   wins and the disagreement gets flagged for a human, not resolved by
   further zooming. Citing the firewall to justify a novel sort inverts it —
   the firewall forbids *adopting* a glyph on a model's authority; it does not
   forbid the printed key or an editor ruling from binding.
1. **Dropped marks below the baseline.** `g̣` / `G̣` (g + U+0323) is the
   single most repeated miss in this project's keying history — corrected
   after the fact more than once, on more than one page, including at least
   one case where the same session had already flagged the class as
   "check hardest" and missed it anyway. Treat any bare Tier-1 `g`/`G` as
   suspect by default rather than as the resting state: `harness lexicon misses
   --marks` gives a live bare-vs-marked frequency count per base letter from
   restored ground truth, and **roughly 90% of `g`'s in the corpus carry the
   dot** — the dotted form is the a priori assumption for any Tier-1 `g`, bare
   is the exception that needs a reason. A number is not a licence to guess
   *which* a given instance is — shape still decides — but it is reason
   enough to look hard at every `g` before accepting a line, independent of
   whether that line otherwise seemed to need zooming. `3-004` restated this
   at scale: `-g̣ɪ`/`-g̣ɪn`/`-g̣ɪt` are common **noun-forming suffixes**, not
   merely a kinship-vocabulary pattern — they turn up equally outside that
   register (`va'ɪrg̣ɪn`, "spirit") — so a reading that ends a word in plain
   `-git`/`-gin`/`-gɪn` should be treated as presumptively wrong on the
   suffix's own strength, before even looking at the raster, whatever the
   word means. On `3-004` the proposal bare-keyed the suffix across nearly every
   headword on it, the single largest error class on the page.

   **Fourth occurrence, `3-005`:** a dense kinship-terms page read several `-mgɪn`/
   `-mgälqäl` clusters as bare `g` after a genuine 4x look that seemed to show no
   dot — and was still wrong, per the human reviewer, on more than one of them. The
   lesson isn't "look harder," it's that **the 90% figure is a real prior to weight
   against your own raster impression**, not a nudge to double-check once and then
   trust what you saw. A "no dot" reading at ordinary magnification should be held
   to a higher bar of confidence than a "dot" reading, precisely because the base
   rate runs the other way.

   **Fifth occurrence — and the method, because emphasis has now demonstrably
   failed.** A 2026-08 batch of five parallel readers dropped the dot **five
   times across three of the five pages** (`2-033`: `Attɪˊg̣ɪtkɪ` ×2 and
   `vaˊɪrg̣ɪt` ×2; `2-035`: `Čig̣eiˊ-veˊem`). One of those readers quoted the 90%
   prior *and* named `vaˊɪrg̣ɪn/vaˊɪrg̣ɪt` as the documented trap in its own note,
   then keyed bare twice on the page it was writing about. Everything above was
   read and restated correctly and changed nothing, so the defect is not in how
   loudly this is stated.

   **The reason is optical, and it is the whole point: the dotted and undotted
   sorts are the same letterform.** Both close their tail; they differ by the dot
   and by nothing else. So there is no "shape of an undotted `g`" to recognize —
   *absence is not observable in isolation*, and a reader inspecting one `g`, at
   any magnification, is asking a question the image cannot answer. That is why
   "look hard at every `g`" has now failed five times: it names the target and
   omits the instrument.

   **So where you can, don't inspect a `g` — contrast it.** A plain `g` in the
   English prose of the *same line* settles in seconds what a 4x stare does not:
   both corrections above went that way after their readers had looked hard and
   got it wrong (`danger`/`ger.` on `2-033`, `representing` on `2-035`). Same
   line where possible, since inking varies down a page. Naming the contrast word
   in `note` costs nothing and makes the reading checkable, where "confirmed at
   4x" — what both wrong readings said — is not.

   **This is a technique, not a requirement.** Plenty of lines offer no
   neighbouring `g`, and a pass that demanded one would stall or invent one. Use
   it when it is there and say so; otherwise read and flag as usual. The same
   applies to every absence-shaped call here — `ä` vs `a` (§5.3), `ɪ` vs `i` vs
   `r` (§5.2).

   **The systematic net is distributional, and it needs no raster.** `harness
   lexicon marks` reports bare-vs-marked share per base letter over the ground
   truth: `g̣` is **93.9%** of Tier-1 `g` (123 dotted, 8 bare corpus-wide), `ñ`
   25.9% of `n`, `ä` 14.0% of `a`. A page whose own distribution departs sharply
   from those is worth re-reading before it is accepted, whatever its notes say —
   `2-033`'s reader produced **four bare `g` and no dotted one**, which against a
   93.9% base rate is visible without opening a scan. Unlike every check above it
   does not depend on the reader having remembered anything.

   **`harness proposal marks` is that comparison computed**, and it is what to
   run rather than reading the table by eye. Its `rare` arm names every
   occurrence of a form whose character the corpus almost never sets — bare `g`
   at 6.1% of the `g` axis qualifies, and which contrasts qualify is derived from
   the store at run time rather than declared. Its `conflict` arm catches the
   same class from the other side, by finding one word spelled two ways against
   adjudicated ground truth; that is how `2-040`'s `vaˊɪrgɪt` shows against
   `2-033`'s `vaˊɪrg̣ɪt`. Both also run inside `harness proposal check`, so a
   reader meets them on its own page before anyone else sees it.

   Pass a whole pass's refs at once. Most pages carry only a handful of Tier-1
   terms, so one page is rarely a sample worth a verdict, and the pooled `ALL`
   row against the per-page rows separates one reader's slip from a lean shared
   by every job — which is the prompt or this spec, not a reading.

   **Now enforced mechanically, not just measured.** `detectors.SUFFIX_MARK_DROPS`
   (a table, not a one-off regex, so a newly measured skew for a different
   base+mark+suffix combination is a data row to add) flags any token ending in
   `-gɪ`/`-gɪn`/`-gɪt` with a bare `g` — covering `-rgɪn`, `-ɪrgɪn`, `-mgɪn`, and
   every other consonant-before-g variant uniformly, since the check is on `g`
   itself and never on what precedes it. `harness proposal check PP-NNN` runs it
   unconditionally (same tier as the apostrophe checks — not gated on `resolved`),
   and it also feeds `harness tei context`'s detector flags for the collation pass.
   Report-only: a hit names a dot-prone shape, not a certain error.

   **Measured, not asserted.** `harness lexicon suffixes` (weighted suffix
   frequency, length 2-8) and `harness lexicon digraphs` (weighted
   digraph/trigraph frequency, the corpus's own top 12 suffixes additionally
   stripped so the count reflects stems rather than the suffix family
   re-appearing under every rank) exist to check a claim like this one
   against the actual restored corpus rather than an impression from the
   pages read most recently. Both strip diacritics and the stress mark
   first, so a circumflex or `ˊ` sitting at a boundary doesn't fracture one
   real affix into several accidental variants (mark-stripped, so the `g̣`
   dot is folded into the plain `gɪn` row below rather than hidden in a
   separate one). **Snapshot at 11/20 pilot pages restored — recompute
   before citing, same floor caveat as `--marks`/`--native`; do not treat
   this table as final:**

   | Suffix | Weighted count | | Digraph | Count | | Trigraph | Count |
   |---|---|---|---|---|---|---|---|
   | `-ɪn` | 89 | | `ne` | 34 | | `gɪn` | 10 |
   | `-hɪn` | 28 | | `ɪn` | 32 | | `ini` | 9 |
   | `-en` | 27 | | `en` | 31 | | `ute` | 9 |
   | `-gɪn` | 21 | | `na` | 29 | | `Nut` | 8 |
   | `-lɪn` | 21 | | `an` | 27 | | `erg` | 8 |
   | `-lhɪn` | 20 | | `el` | 27 | | `enu` | 7 |
   | `-rgɪn` | 16 | | `in` | 26 | | `m-g` | 7 |
   | `-ak` | 15 | | `et` | 25 | | `nel` | 7 |
   | `-an` | 12 | | `te` | 24 | | | |
   | `-un` / `-ut` | 11 | | `ɪt` | 24 | | | |
   | `-ɪrgɪn` | 11 | | | | | | |

   `-hɪn`/`-lɪn`/`-lhɪn` together are comparably common to the `-g̣ɪn` family
   (`-gɪn`/`-rgɪn`/`-ɪrgɪn`, mark-stripped so the dot doesn't split the row)
   — a second noun-forming suffix family worth the same "assume it, don't
   bare-key it" discipline as `-g̣ɪn`. `g̣` itself (marks *not* stripped for
   this one figure) is corpus-wide the 6th most common digraph.
2. **`ɪ` (U+026A) vs `i`, two sub-cases, neither caught by shape alone.**
   - `ɪ` vs `ĭ` (dotless i + breve) is a §2.6 licensing fact, not a shape
     call: the breve is licensed on `i` and never on the obscure-vowel series
     (`ɪ` included), so a dotless vowel carrying a genuine breve is `ĭ`, full
     stop. Check §2.6 as a rule lookup whenever a breve is in play, not by
     eye — this has been keyed wrong in both directions.
   - Word-initial capital-shaped letter vs. small-cap ɪ: a capital-looking
     letter opening a Tier-1 word is not automatically ASCII `I`. It has been
     misread as plain `I` at word-initial position specifically, more than
     once — `1-101`'s `Iᵋplɪˊlɪ` twice on one page, both corrected at
     adjudication to `ɪᵋplɪˊlɪ`.

     **Position decides whether the question is contentious, and it decides it
     the opposite way from the medial case.** Measured over the ground truth:
     word-*medially* an ASCII capital is essentially never right — **2**
     occurrences against **509** medial small caps — and
     `detectors.MEDIAL_CAPS` already refuses one with a sharper claim than any
     frequency could. Word-*initially* both are ordinary: **63** ASCII capitals
     (`Alaˊyon`, `Ilhiˊnin`, `Enuˊrmin`, `Luˊᵋren`) against **55** small caps
     (`ɪnp-luˊwleñ-yiˊᵋlhɪn`, `ᴇnmɪtaˊhɪn`). So nothing mechanical settles a
     word-initial one; it is a reading, and the frequency arms of `harness
     proposal marks` are the only handle there is. That is exactly why
     `MEDIAL_CAPS` was blind to `1-101`'s pair.

     Note this holds for `ᴇ`/`E` too (12 initial `E` against 31 initial `ᴇ`),
     and that `ᴀ` and `ʟ` are attested word-initially **only** as ASCII in the
     store so far — 28 `A` and 7 `L` against none of either small cap. That is
     the corpus speaking rather than a rule, and it is thin enough that a
     genuine word-initial `ᴀ` should be read, not argued away.
   - **`ɪ` keyed as `r`, arriving from the recognizer.** CATMuS substitutes
     `i`, `I` and **`r`** for `ɪ`, and `r` is the one that gets through: a
     2026-08 reader keyed `2-033`'s `Attɪˊg̣ɪtkɪ` as `Attrˊgɪtkɪ`, taking the
     machine's letter. **The standing "CATMuS is not a witness to any non-ASCII
     glyph" rule does not reach this, and that scoping is the hole** — the
     recognizer's error *is* ASCII, so a prohibition worded around non-ASCII
     characters reads as licensing exactly the substitution that bites. The rule
     wanted is: CATMuS is not a witness to what any character is wherever an
     inventory glyph could stand. Optically the two are easy once contrasted
     (§5.1): `r` carries a shoulder, `ɪ` is a bare stem with serifs top and
     bottom, and English prose on the same line supplies a real `r` to hold it
     against.

   **This is now the leading residual class, and the tell is that the reader
   reports checking it.** Four instances over two 2026-08 batches survived into
   adjudication and were caught by the human, not by the pass: `2-047` lines 15
   and 17 (`empeiˊkɪn`, `hɪshoˊlan`), `2-031` line 33 (`Uˊnpɪñe`), `2-035` line
   14 (`velerkileˊlɪt`). **Every one was on a line whose reader had explicitly
   narrated the check** — `2-031`'s wrote "checked closely against the ɪ
   elsewhere on the page and read as plain ASCII i (x-height, dotted)" and was
   wrong. A confident negative here carries no more weight than an unexamined
   one, exactly as §5.1's bare-`g` reading does; both are absence claims about a
   small feature, and neither is settled by having looked once.

   **The distributional prior runs against `i`.** Over the ground truth, Tier-1
   `ɪ` outnumbers `i` **470 to 247**, near 2:1 — so in a Tier-1 form `ɪ` is the
   likelier sort, and a page keying mostly `i` is the case wanting a second look.
   Same instrument as §5.1: cheap, needs no raster, and does not depend on the
   reader having remembered anything.
3. **`ä` (a + U+0308) vs. plain `a`.** The long counterpart of the
   obscure-vowel series (§2.2). Any bare `a` in a Tier-1 form is a candidate
   for `ä`, not a default reading just because plain `a` is the more common
   letter generally — the diaeresis is small and easy to read past on a
   contact sheet rather than a close zoom, and has been missed that way more
   than once on the same page.
4. **Old-style figures.** The numeral `1` is x-height and dotless and is easy
   to take for `ɪ`; `0` is small and round. A recognizer witness (CATMuS)
   reads `20th` as `zoth` — evidence of how easily this class slips past a
   plausible-looking read, not evidence for the glyph itself, since a
   recognizer is not a witness to Tier-1 identity at all.
5. **Word stress (U+02CA ˊ) keyed as a plain apostrophe (U+0027 ').** These
   are visually distinct printed symbols — read which one is actually on the
   page rather than defaulting to habit. **Every multisyllabic Chukchi/Koryak/
   Yupik word carries a stress mark, full stop** (culminative, ≤1 per word,
   §2.1) — not "usually," not "often," every one. Treat this as load-bearing
   enough to check by itself, independent of every other class in this list:
   **a multisyllabic Tier-1 word with no stress mark anywhere in it is not a
   plausible reading, it is a red flag.** Before accepting one, ask explicitly
   where its stress mark is. If the only raised mark in the word is currently
   keyed as `'`, that apostrophe is far more likely `ˊ` misread than a genuine
   spirant or pause — check the environment (§2.1: spirant is only after
   b/p/d/t/g/k, pause is only V_V) and if neither licenses it, it is not
   apostrophe. This has been gotten wrong at the scale of a whole page in one
   pass, and separately, on two different hand-keyed pages, at the scale of a
   single missed word each — different failure modes, same root cause: the
   check not being run as a real per-word gate.

   **A new failure mode on `3-004`, worse than not running the check: running
   it correctly in `resolved` and then not applying it to `text`.** Every
   `resolved` field on that page's proposal reasoned out "post-vowel,
   pre-consonant-not-in-b/p/d/t/g/k, not V_V → this is stress U+02CA, not
   apostrophe" correctly — and `text` kept the literal `'` anyway, on 33 of
   71 lines. `proposal check` reported the exact signature of this
   (`in_resolved_not_text: U+02CA` — resolved names the codepoint, text
   doesn't contain it) on nearly every affected line, and it was dismissed as
   narrative-formatting noise rather than treated as what it was: the same
   diff class repeating across many lines is the tool reporting something
   systematic, not a prose-style mismatch. **After writing `resolved`, re-read
   `text` character by character against what `resolved` just concluded —
   reasoning about a mark and typing that mark are two different acts, and
   nothing enforces that the second followed the first.**
6. **Straight quotes for English glosses.** The book sets curly `“…”`
   throughout, never straight `"..."` (§1) — print reproduction, not a
   stylistic option. This has slipped through in bulk more than once,
   including in hand-keyed pages assumed authoritative for years before a
   mechanical check caught it. `harness corpus normalize` flags a straight quote
   left in text as a worklist lookalike; it does not auto-fix, since pairing
   an open quote to its close can require reading across lines.
7. **Medial ASCII capital where a small-cap was meant.** Typing a plain
   `A`/`E`/`I`/`L` mid-word instead of the small-cap `ᴀ`/`ᴇ`/`ɪ`/`ʟ` (§2.3).
   `harness proposal check` folds this into its consistency check
   (`detectors.MEDIAL_CAPS`) but never auto-corrects it, even when it looks
   like the one clean unambiguous swap on a line — which small-cap an ASCII
   capital was meant to be is a reading judgement, not a shape slip, so it
   only ever surfaces as a flag for a human to resolve.
8. **Any raised mark defaults to stress (U+02CA), never apostrophe (U+0027) —
   see §4.** `3-005` (a kinship-terms page) flagged half a dozen marks — in V_V
   position, and once after a bare consonant — as open "human calls" between stress
   and apostrophe. All were stress. Apostrophe is licensed by the printed key and has
   never once been the right reading anywhere in the restored corpus; don't reason
   about the licensing environment as if it were live evidence for apostrophe, and
   don't re-litigate this per page. Read the mark as stress and move on.
9. **Inventing a codepoint the inventory doesn't catalogue.** A mark that looks
   unusual at 4x is not licence to reach for whatever Unicode Latin/IPA letter
   resembles it — check §2.1-2.4 first. `3-005` proposed U+025B (full-size LATIN
   SMALL LETTER OPEN E, "ɛ") in two ordinary English-register words where the
   printed letter was plain "e"; ɛ appears nowhere in this file's inventory. If a
   candidate codepoint isn't already catalogued (proposed or settled), the reading
   is wrong far more often than the inventory is incomplete — see item 0.

   **`1-048` adds the case where the shape argument is good and still wrong.** The
   page prints `reindeér-breeding`, and at 4x the mark over the second `e` is a
   solid tapered wedge at type weight and slant — categorically unlike the round
   artifact dots littering that page, and so read as ink from the forme rather than
   dirt. The editor's ruling: **a serendipitously shaped smudge.** The lesson is not
   that the observation was careless, it is that *shape quality at magnification
   cannot by itself separate a sort from a smudge*, so it is not evidence strong
   enough to adopt an uncatalogued codepoint on. What worked was suspending
   judgement: the proposal keyed it as printed but said in `note` that U+0301 is
   catalogued nowhere here and would be the corpus's first combining acute, which
   is what put the call in front of a human instead of into the corpus. Where a
   mark makes no lexical sense **and** its codepoint is uncatalogued, the disposition
   is to flag loudly, whatever the raster seems to show.

   **`1-060` is the second instance, and it makes this a class rather than an
   anecdote.** The page prints `“Chief of the Chaun Chukchee”` and CATMuS read a
   combining acute over the `e`; at 4x the mark is an irregular blob touching the
   `f`'s ascender with a stray dot below it — unlike `1-048`'s, the shape argument
   here runs *against* the mark, and the same page supplies a control in the clean
   tapered ˊ of `tɪkêˊ-vaˊg̣lɪñɪn` on line 23. Keyed `Chief`, flagged in `note`,
   and the editor's ruling was the same: **another conveniently diacritic-shaped
   smudge.**

   Two things worth carrying forward. The disposition is the same whichever way the
   shape argument points — key the letter, flag the mark, let a human rule — because
   the codepoint being uncatalogued is what decides it, not the ink. And it is the
   *second witness* that made this one cheap: the recognizer saw a mark and the
   reading pass did not, so the span diff surfaced it as a disagreement instead of
   the pass having to remember to look. A page with no second witness gets no such
   prompt, which is an argument for reading against `mz/ocr/` rather than alone.
10. **No small-caps "o" exists in this notation.** §2.3 licenses small-cap base
    codepoints only for ᴀ ᴇ ɪ ʟ. A lowercase "o" sitting immediately beside a
    small-cap ᴇ or ʟ can read as small-cap height at 4x zoom purely from kerning —
    that is a rendering artifact, not a second sort. `3-005` proposed a
    small-cap-vs-lowercase-o distinction inside a single word (`ᴇʟO'o`) on this
    basis; there is no such distinction to make — it is plain lowercase `o`
    throughout.

11. **A note that describes a keying decision the text does not show.** The
    inverse of §5.5's failure, and worse, because the text is *right* and the note
    argues it wrong. `2-031` keyed its three footnote openers correctly as `¹ ² ³`
    and attached notes claiming plain ASCII digits had been keyed, justified "per
    the precedent recorded for 2-034 in keying_spec.md §2.10", and predicting the
    half-open-pairing check would flag the page and that this was expected. Almost
    certainly the text was repaired mid-pass and the note never re-read. Left
    standing it is worse than a wrong character: **an adjudicator reading a
    confident rationale beside correct text is being argued into breaking it**, and
    the note is the more persuasive of the two.

    Two rules follow, both cheap. **Before the proposal is final, re-read every
    `note` against its own `text`** — a note describing a decision the text does
    not exhibit is a defect regardless of which one is right, because they cannot
    both be. And **a note citing a section of this file must quote the sentence it
    relies on.** Both readers in that batch cited §2.10 and reached opposite
    conclusions after reading it in full; neither could have quoted a sentence
    supporting a plain-digit opener, because there is none. Quotation is the check
    that "I read it" is not.

    A caution on where the blame sat, since the first diagnosis was wrong: that
    reader was not inventing the precedent. §2.10 named `2-034` and printed its
    defective opener as a worked example, so a *record of the error* read as a
    *statement of the convention* — the passage has since been rewritten. **When a
    reader misapplies a rule, read the rule before concluding it was ignored.**

12. **A note that invents a second witness for text that is already right.** The
    other half of §5.11 and harder to catch, because nothing downstream disagrees
    with anything: the reading is correct, the check passes, and the note supplies
    a *checkable* corroboration that turns out to be false. Two instances in one
    two-page batch, from different readers.

    `1-022` keyed `Plates V` — correct — and wrote that the first numeral
    "measured against the V of VII in the same strip the two are the same height".
    They are not: at 4× the `v` sits at plain x-height and `VII`/`XIV` are small
    caps, visibly taller. `1-021` ruled a speck over the `t` of `list` to be dirt
    — correct — and wrote that "CATMuS read it as an apostrophe (`list'`)". CATMuS
    read `1 See list of authorities quoted, p. 3.`; there is no apostrophe in the
    machine text at all.

    **The rule: a note may state what the reader saw, and may not state what
    another witness said unless that witness was actually consulted.** The machine
    text is one command away (`harness ocr lines REF --store mz`) and a measured
    comparison is one zoom away, so both claims were cheap to check and neither
    was. An invented corroboration is worse than no note, because it is exactly
    the thing that stops the next reader looking — and it will be believed, since
    the text beside it is right.

    **Write notes in codepoints, not in glyphs**, which removes the commonest way
    a note goes wrong on its own. Name the character — `U+0323 COMBINING DOT
    BELOW`, `U+02CA MODIFIER LETTER ACUTE ACCENT` — rather than reproducing it, and
    describe a spacing or a shape rather than exhibiting it. Reproducing a glyph in
    prose is probabilistic in exactly the way keying it is, so a note can acquire
    its own typo and then argue from it; and `corpus normalize` runs over `note`
    text like any other field, so a quoted French space or a precomposed letter is
    silently rewritten and the example becomes its counterexample. **That
    normalization is intentional and is not a trap to work around** — it is the
    reason the convention exists.

**On repetition.** More than one of the classes above has been named as "the
one to check hardest" and then missed again on a later page, sometimes in the
very same session that had just re-stated the rule. The lesson is not that
the checklist is wrong; it's that stating a class once is not the same as
checking for it on every line, every time — treat this list as a per-line
pass over any Tier-1 span, not as background awareness to keep in mind.
