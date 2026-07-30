# Keying spec — Bogoras notation → Unicode

**Authority.** The printed key (Part 1, p. 10 — book-internal apparatus,
firewall-clean, binds) as corrected by the editor's corpus-scale collation
from hand-corrected OCR. The charter outranks this file; the transcriber
harness (rev 2) governs the collation pass.

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
| spirant mark | **U+0027** ' | After b p d t g k only. |
| pause mark | **U+0027** ' | V_V only; key specimen *yiñe'a*. |
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
glyph-pattern detector by construction (charter, detector section).

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

**One residual shape judgement** the scripts cannot make: in V_V position both
stress and pause are licensed, and there the keyer decides U+02CA vs U+0027 by
printed shape alone (greyscale fallback per F11).

## 5. Open questions, keying-side

- **F4** — lateral/rhotic deployment. The key gives four laterals and three
  rhotics; corpus-scale hand-correction has produced no confident sighting of
  the four-way lateral contrast in running Chukchi text — informative about
  the print, not the reader: these distinctions live in letter bodies at
  running-text size, the least legible stratum, unlike the self-announcing
  added marks. Standing hypothesis, tested not assumed: the key describes the
  full Jesup phonetic apparatus while Chukchi running text deploys a subset,
  the extra sorts earning their keep in Koryak/Itelmen material. Resolution is
  validation script 7; zero Chukchi tokens for ḷ and ʟ̣ closes F4 as "key ≠
  deployed inventory." Downstream analysis depends on this; that dependency is
  not this file's concern.
- **F10** — the spirant series prints as `b' p' d' ' g' k'` on the p. 10 scan
  (the printed mark is turned-comma-shaped; it keys U+0027 per §2.1): the
  fourth member is a floating mark where `t'` should sit. Completeness rests
  on Sievers and stop-inventory symmetry, not legible print. Closable cheaply
  if `t'` appears legible anywhere in the hand-corrected corpus; otherwise
  greyscale master.
- **F11** — mark legibility, the standing print-vs-scan file. Load-bearing:
  (a) does the print obey its own licensing (compliance greps over drafts and
  GT); (b) stress vs U+0027 distinguishability at working zoom, especially
  V_V; (c) ᵉ/ᵋ bowl-closure and crossbar legibility. Two confirmed
  casualties: the ᵉi key row collated as "ᵋiᵋ" at working zoom (string
  retired); the `s˙` sort read as apostrophe-shaped from the scan. Greyscale
  fallback whenever bitonal fails.
- **Ģ (U+0122)** — inherited-unverified: reported inventory candidate from a
  p. 669 incantation, transmitted through lost documents. Verify against the
  page before admitting a row; do not key on report.

## 7. Changelog

- **Rev 2.7 (2026-07-29):** §2.6's breve licence made a **closed** allow-list and
  enforced in code (`detectors.MARK_LICENSE`; `normalize --check` exits 1, `validate`
  errors, `restore` refuses). `j` added to the never-on column: the marked sort is
  **ǰ** = j+U+030C, already in §2.2. Prompted by a reading pass on `1-073` keying all
  three of its ǰ as breves, on the reasoning that the mark looked rounder than the
  page's č — a real observation, an invalid inference, and then defended on firewall
  grounds, which inverts the rule: the firewall forbids *adopting* a glyph on a
  model's authority, not proposing one the inventory has never attested. Review
  corrected two of the three and missed the third, so the gate exists to catch what a
  human pass can miss rather than what it never saw. No tool rewrites an offender —
  naming it is mechanical, choosing the glyph is the editor's.
- **Rev 2.6 (2026-07-29):** §2.9 added — the book's French spacing before `;` and
  `:` is **not** reproduced; key English spacing. Editor's ruling, prompted by a
  reading pass on `1-073` confirming the thin space at 2× on three lines and then
  asking whether to key it. Stated as an explicit, bounded override of "English
  prose reproduces the print", with the reason (no lexical content, and it would put
  a space inside a token for every downstream consumer) and the limit (an interword
  space that is present is still keyed; `i. e.,` does not close up).
- **Rev 2.5 (2026-07-29):** §2.8 added — museum catalogue numbers are keyed as
  the literal `(??/????)` by the keying and collation passes, and never read.
  Editor's ruling, prompted by a reading pass on `1-151` starting to resolve the
  digits off the raster. The convention was already universal in
  `data/readings.md` and had a keyboard binding, but appeared in no normative
  document — practice without a rule. Framed as *deferral*: the AMNH catalogue is
  live, so a later pass may resolve these by querying it, which is a lookup rather
  than a transcription. First draft of this section said the numbers resolve
  against nothing and were unfalsifiable — wrong on both counts, and it would have
  licensed dropping them permanently.
- **Rev 2.4 (2026-07-29):** §2.7 added — the closed list of pre-reform Russian
  sorts, with codepoints, what each was reformed to, and what each is confusable
  with. §1 had named only two of the five. Prompted by `1-151`'s **лахтакъ**,
  whose word-final ъ the committed TEI had modernized away (licensed, since the
  word is glossed) but which ground truth keys as printed. The list cannot come
  from a corpus census — the recognizer is Latin-only and lost all Cyrillic, so
  every instance in the book is currently unwitnessed, and a character nobody
  looked for is a character silently dropped. Records that ъ is *not* an
  abolished sort and only its word-final position is the marker, and that
  і/ѵ/ѳ are cross-script lookalikes outside §3's Tier-1 scope.
- **Rev 2.3 (2026-07-29):** §1 ASCII policy narrowed from corpus-wide to
  Tier-1, and the greps with it. This had been decided, implemented in
  `validate.py` (`FORBIDDEN_PROSE` minus the four curly quotes) and written into
  `CLAUDE.md` at rev 2.2, but never landed here — so the normative spec said
  "forbidden everywhere" while the gate accepted them, and `CLAUDE.md` cited a
  §1 revision that did not exist. The doctrine is the scoped one; this entry is
  the spec catching up to its own enforcement.
- **Rev 2.2 (2026-07-29):** §2.6 added — mark–base licensing, editor-supplied.
  Breve licensed on `u` and `i`, never on the obscure-vowel series ᴀ ᴇ ɪ ä,
  since the p. 10 key already glosses that series as short. Prompted by a real
  ambiguity: `1-074`'s *Am-g̣roˊkĭ* is unresolvable from the raster because `i`
  drops its dot under an above-mark, so ĭ and ɪ̆ are the same letterform. The
  same page also cost a missed U+0323 on the `g`, which the rule does not help
  with — that one is a looking failure, not a licensing question.
- **Rev 2.1 (2026-07-29):** U+2018 added to the U+0027 lookalike row — surfaced by validator testing; the printed spirant mark's turned-comma shape (F10) makes it the likeliest OCR emission, and A.0 had omitted it.
- **Rev 2 (2026-07-29):** Part II (comparanda) excised to `concordance.md`.
  The firewall is context hygiene, not just provenance: interpretation loaded
  into a keying session primes the keyer. Detector notes returned to the
  charter's remit; concordance-side flags (F2, F3, F9) and the closed-flag
  register travel with the concordance. F10 gains a prose record of the
  printed mark's shape (this file must pass its own §3 greps, so the shape is
  described, never keyed).
- **Rev 1 (2026-07-29):** document created as sole successor to Appendix A
  rev 6 and the propagation payload. A.0 table entered as §2.1; p. 10
  collation rows as §2.2/§2.5; ˢ→ᵋ correction absorbed; Q1/Q2 closures
  absorbed (§2.1, §4); stress-mark-absent note recorded; small-cap base
  codepoints entered as PROPOSED (§2.3); Ģ demoted to inherited-unverified
  (§6). **Nothing blocks p. 10 hand-keying** except the §2.3 stamp, which
  blocks only the small-cap rows' citability, not the keying itself.
