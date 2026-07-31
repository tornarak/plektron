# Keying spec — Bogoras notation → Unicode

**Authority.** The printed key (Part 1, p. 10 — book-internal apparatus,
firewall-clean, binds) as corrected by the editor's corpus-scale collation
from hand-corrected OCR. `CLAUDE.md` outranks this file on project invariants;
`transcriber_harness.md` governs the collation pass. This file is normative for
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
allow-list, `harness normalize --check` exits 1 on a violation, `harness validate`
raises it as an ERROR, and `harness restore` refuses to write. Not a worklist item:
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
judgement: `harness normalize` collapses a run of 2+ spaces between two non-space
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

`detectors.footnote_report` implements both, `harness normalize` reports them
corpus-wide, and `harness proposal-check` reports them per proposal. **Report-only
in both**, at the `lookalikes` tier rather than the blocking one: a note whose
reference and text straddle a page seam breaks the pairing with nothing miskeyed,
so a hit is a page to look at. A proposal that fails either invariant carries a
page-level `footnotes` explanation instead.

A third check closes a hole the two invariants cannot see. They count
superscripts, so a page that keys *every* marker as ASCII has none, hence no gaps
and no singletons, and passes vacuously. So a line opening with a **bare digit
then a space** is flagged too. Numbered lists do not collide — the book sets
those as digit + **period** (`2. Čačanloˊrg̣ɪn`), which the rule deliberately
does not match. Measured over the restored corpus: 9 lines match, 8 are this
defect and 1 is a wrapped body line beginning with a numeral (`1-053`,
`"2 houses)."`).

**Found by the check, in restored ground truth**: `1-048` (6 markers, one of them
absent altogether), `1-053`, `1-073` (3), `1-151`, `2-034`. Four of those five
were invisible to the counting invariants alone.

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
   suspect by default rather than as the resting state: `harness lexicon
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

   **Now enforced mechanically, not just measured.** `detectors.SUFFIX_MARK_DROPS`
   (a table, not a one-off regex, so a newly measured skew for a different
   base+mark+suffix combination is a data row to add) flags any token ending in
   `-gɪ`/`-gɪn`/`-gɪt` with a bare `g` — covering `-rgɪn`, `-ɪrgɪn`, `-mgɪn`, and
   every other consonant-before-g variant uniformly, since the check is on `g`
   itself and never on what precedes it. `harness proposal-check PP-NNN` runs it
   unconditionally (same tier as the apostrophe checks — not gated on `resolved`),
   and it also feeds `harness context`'s detector flags for the collation pass.
   Report-only: a hit names a dot-prone shape, not a certain error.

   **Measured, not asserted.** `harness lexicon --suffixes` (weighted suffix
   frequency, length 2-8) and `harness lexicon --digraphs` (weighted
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
     letter opening a Tier-1 word is not automatically ASCII `I`. It needs
     the same scrutiny as a medial occurrence, and has been misread as plain
     `I` at word-initial position specifically, more than once.
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
   71 lines. `proposal-check` reported the exact signature of this
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
   mechanical check caught it. `harness normalize` flags a straight quote
   left in text as a worklist lookalike; it does not auto-fix, since pairing
   an open quote to its close can require reading across lines.
7. **Medial ASCII capital where a small-cap was meant.** Typing a plain
   `A`/`E`/`I`/`L` mid-word instead of the small-cap `ᴀ`/`ᴇ`/`ɪ`/`ʟ` (§2.3).
   `harness proposal-check` folds this into its consistency check
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
10. **No small-caps "o" exists in this notation.** §2.3 licenses small-cap base
    codepoints only for ᴀ ᴇ ɪ ʟ. A lowercase "o" sitting immediately beside a
    small-cap ᴇ or ʟ can read as small-cap height at 4x zoom purely from kerning —
    that is a rendering artifact, not a second sort. `3-005` proposed a
    small-cap-vs-lowercase-o distinction inside a single word (`ᴇʟO'o`) on this
    basis; there is no such distinction to make — it is plain lowercase `o`
    throughout.

**On repetition.** More than one of the classes above has been named as "the
one to check hardest" and then missed again on a later page, sometimes in the
very same session that had just re-stated the rule. The lesson is not that
the checklist is wrong; it's that stating a class once is not the same as
checking for it on every line, every time — treat this list as a per-line
pass over any Tier-1 span, not as background awareness to keep in mind.
