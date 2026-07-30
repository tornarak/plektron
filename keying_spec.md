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
- **ASCII policy, corpus-wide.** U+0027 and U+002D are the only apostrophe and
  hyphen; English prose keys them like everything else. U+2019 and friends are
  forbidden everywhere; the lookalike greps run unscoped. Rationale: ASCII is
  what every keyboard emits, hence drift-proof; a modifier-letter codepoint
  invites corpus-wide conflation with true apostrophes at every entry point.
- **Keying reproduces print.** The collation pass may modernize glossed Russian
  (harness rev 2); ground truth does not — pre-reform Cyrillic sorts
  (і U+0456, ѣ U+0463) are keyed as printed.
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
