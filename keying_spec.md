# Keying spec — Bogoras notation → Unicode

**Authority.** The printed key (Part 1, p. 10, scan `1-030` — book-internal
apparatus, firewall-clean, binds) as corrected by the editor's corpus-scale
collation. `CLAUDE.md` outranks this file on project invariants. This file is
normative for the character inventory and binds the ground-truth pass, the
collation pass and the human keying track. How a page is *read* — the image
ladder, the instruments, what a `note` may claim — is the reader's contract,
`.claude/agents/groundtruth-reader.md`, which cites this file and never restates it.

---

## 1. Doctrine

- **Firewall.** A model reads a scan and proposes; the proposal carries its
  rank (`#llm`) and only a human act raises it (`#ed`, `#gt`) — the four ranks
  are `README.md`'s and `@resp` names one on every Tier-1 span. What no reading
  may do is infer a glyph from what the system "should" contain, from a
  neighbouring page, or from a corpus-wide pattern: a glyph is read from its own
  ink, and where the ink will not answer the line is flagged, not filled. The p.
  10 key is evidence and binds.
- **NFD, corpus-wide.** `harness corpus normalize` is the gate.
- **ASCII policy, scoped to Tier-1.** Inside `ckt`/`kpy`/`ypk`/`xcv`/`eve`/`ipk`/
  `itl`/`yux`, U+002D is the only hyphen and the §3 lookalike greps run. English
  prose reproduces the print, **curly quotes included** — the book sets them and
  a straight quote is never on the paper. `validate.FORBIDDEN_PROSE` and the
  scoped greps enforce it.
- **Keying reproduces print**, the book's own errors included (§2.14), with
  exactly two overrides: spacing (§2.9) and the press's diacritics on English
  loanwords (§2.15). Pre-reform Russian is keyed as printed (§2.7). A species
  epithet is keyed as set, never the modern binomial.
  *Attested:* `Oncorhynchus horbusha`, `niarka`.
- **Two-tier settlement.** SETTLED rows are law, stated flat. PROPOSED rows are
  the best available disposition awaiting the editor's stamp; they enter force
  via changelog, not by ceasing to be questioned.

## 2. Inventory

### 2.1 Marks (SETTLED)

| Mark | Codepoint | Licence |
|---|---|---|
| word stress, postposed to the stressed vowel | **U+02CA** ˊ | ≤1 per word (culminative, §5.5). Absent from the p. 10 key; corpus-attested |
| laryngeal superscript | **U+1D4B** ᵋ | glottalization of the stressed vowel |
| rising-diphthong onglide | **U+1D49** ᵉ | only immediately before `i`; extends on attestation, never on symmetry |
| velar g, dot below | **g + U+0323** g̣ | q : k :: g̣ : g |
| long rounded mid vowel | **U+0275** ɵ | key: "between *o* and *u*, long" |
| palatalization mark, postposed | **U+02D9** ˙ | after n x d t s č ǰ |
| connector hyphen | **U+002D** - | forms essentially never break across lines; a line-end join is a human's call |
| length marks | **U+0304** ◌̄ , **U+0306** ◌̆ | combining, NFD; bases per §2.6 |
| increased articulation stress | **U+0021** ! | rare; word-internal or form-adjacent |

**A raised comma-shaped mark inside a Tier-1 span is stress, U+02CA.** U+0027
has no use in Tier-1 text (§3).

**ᵉ and ᵋ are mutually confusable and both licensed**; their environments are
disjoint (ᵉ only pre-`i`, ᵋ never). U+1D49 not immediately followed by `i` is
an error; U+1D4B immediately before `i` is a review flag.

**§2.2 and §2.3 are also held machine-readably in `edition/alphabet.json`**, which
this file owns and `harness edition runs` checks against it.

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
shape family. Glyph identities are settled; the base codepoints await the
editor's stamp, because the small caps are where lookalike drift threatens:

| Glyph | Codepoint | Drift hazard |
|---|---|---|
| ᴀ | U+1D00 | |
| ᴇ | U+1D07 | |
| ɪ | U+026A | IPA block, not the "Latin Letter Small Capital" run — invites later "fixing" to a lookalike |
| ʟ | U+029F | same hazard |
| ʟ̣ | U+029F + U+0323 | inherits the ʟ question |

**These four are the whole small-cap inventory, and only inside Tier-1 forms.**
There is no small-cap `o`, `v`, `x` or any other letter; roman numerals (§2.12)
and run-in headings (§2.13) are ASCII.

### 2.4 Letters — unmarked ASCII with non-obvious values

`c` = English *sh*; `j` = French *jour*; `x` = *Bach*; plain `s`; `h` (a
licensed sort in native words). All invisible to any glyph-pattern detector by
construction.

### 2.5 Series structure (key doctrine)

Four laterals **l ḷ ʟ ʟ̣**; three rhotics **r ř ṛ**; proportional velar pair
**q : k :: g̣ : g**; seven-member palatalization series **n x d t s č ǰ + ˙**;
diphthongs compose productively from any vowel + i/u, the ᵉi row adding the
rising case — prominence on the closing element, opening element cast superscript.

### 2.6 Mark–base licensing (SETTLED, editor-supplied)

`i` loses its dot under any above-diacritic, so printed **ĭ** is the same
letterform a small-cap **ɪ** with a breve would present. No magnification
separates them; only the licence does.

| Mark | Licensed on | Never on |
|---|---|---|
| breve **U+0306** | `u` (ŭ); `i` (ĭ) | everything else — the obscure-vowel series **ᴀ ᴇ ɪ ä** already encodes length (§2.3), and `j` because the marked sort is **ǰ**, j+U+030C |

**The list is closed and enforced as such.** `detectors.MARK_LICENSE` holds it;
`harness corpus normalize` exits 1, `tei validate` raises an ERROR and `ocr
restore` refuses to write on a violation. No tool rewrites one — choosing the
intended glyph is the editor's act. So a breve above a dotless i-form is **ĭ**,
never ɪ̆; further bases are licensed only on attestation the editor has stamped.
*Attested:* `1-074` `Am-g̣roˊkĭ`; `1-073` `Neǰ-` ×3 (caron, not breve).

### 2.7 Pre-reform Russian sorts (SETTLED)

The book is 1904–1909, its Russian pre-1918 orthography throughout. Four letters
the reform abolished and one position it changed are keyed **as printed**:

| Printed | Codepoints (lc / UC) | Name | Reform sent it to | Confusable with |
|---|---|---|---|---|
| **і** | U+0456 / U+0406 | decimal i | и U+0438 | **Latin `i` U+0069** — identical letterform. Inside a Cyrillic word it is U+0456, never Latin |
| **ѣ** | U+0463 / U+0462 | yat | е U+0435 | ь U+044C, ъ U+044A — ѣ adds the crossbar. Common: хлѣбъ, бѣлый |
| **ѳ** | U+0473 / U+0472 | fita | ф U+0444 | Latin `o`/`0`, Greek θ. Greek loans only |
| **ѵ** | U+0475 / U+0474 | izhitsa | и U+0438 | **Latin `v` U+0076**, Cyrillic у. Church-Greek words only; rare |
| **ъ** *word-final* | U+044A / U+042A | hard sign | dropped in this position only | ь U+044C — the ascender alone |

The hard sign is live modern Russian as a separator; only its *word-final*
occurrence after a consonant is the pre-reform marker, which is why its row says
"word-final" and a grep for the bare character is not a detector. Nothing
mechanical catches a Latin `i` or `v` inside a Cyrillic word: Russian is Tier-2
and outside the §3 greps. Pre-reform spellings (**-аго/-яго**, **-ыя/-ія**) are
orthography, not sorts, and raise no keying question.
*Attested:* `1-151` `лахтакъ`.

### 2.8 Museum catalogue numbers (SETTLED)

Figure captions carry AMNH accession numbers set as stacked fractions. **Neither
pass reads them: key the fixed literal `(??/????)`**, whatever the digits. The
catalogue is a live external resource an annotation pass can query, where the
number is checkable; a digit transcribed off a raster looks resolved and never
gets looked up. *Attested:* `1-151` L37 — the denominator clips below the line box.

### 2.9 Spacing before punctuation — English, not French (SETTLED, editor ruling)

The book sets a thin space before `;` `:` `,` `!` `?` and a double space after a
sentence-ending period. **Key English spacing**: no space before any of those
five, one space after a period. Interword spacing is otherwise **as printed** —
a space present is keyed and one absent is not (`i. e.,` keeps its space).

Gate: `harness corpus normalize` strips a space before any of the five and
collapses a run of spaces, corpus-wide; this list and the one in
`harness/normalize.py` are the same list, neither free to narrow without the
other. *Attested:* `1-073` `purpose ; but` → `purpose; but`.

### 2.10 Footnote markers — the superscript sort, never the ASCII digit (SETTLED)

A footnote marker is printed twice, at the body reference and opening the note.
**Key the Unicode superscript** — `¹` U+00B9, `²` U+00B2, `³` U+00B3, `⁴`–`⁹`
U+2074–U+2079 — at both. A marker keyed `1` is the right number and reads as
correct in every view; counting is the only mechanical witness.

Gate: `detectors.footnote_report`, reported by `harness corpus normalize` and
`harness proposal check`, **report-only** (a note straddling a page seam breaks
the pairing with nothing miskeyed). Numbering restarts on every page, so:

1. the marker values present form a continuous run 1..N;
2. each value occurs at least twice;
3. a line opening with a bare digit and a space is flagged **once a superscript
   has appeared earlier on the page** — digit + period (a list item) is not matched.

A plain digit anywhere else is ordinary: a quantity, a list item, a folio, a
catalogue number. A page keying *every* marker as ASCII passes clean — that is
what a freshly recognized page looks like — and closing that gap needs a witness
this check does not have.

**A figure sub-part locant is not a marker** — `(Fig. 17, f¹)`, a raised numeral
picking out one labelled detail. Key it as printed. On a keyed line the
exclusion is a **lone letter** carrying the superscript with a close-paren
following (`detectors.FIGURE_LOCANT`); in the TEI it is whatever
`figrefs.LOCANTS` consumes after a marked figure reference, so a comma list is
no harder than a single letter.

**Spacing**: a body reference sets **tight** against what precedes it (`mouth.¹`,
`Steller,¹`); a note opener sets **marker, space, text** (`¹ See`). `harness
corpus normalize` reports both and `--convert` writes them.

**An opener printing no marker, where the body reference is marked, has been
abraded: supply it**, and say in `note` that it was supplied. Both witnesses are
on the page. Where the body reference is missing too, report the page; nothing
attests a value. The licence is the apparatus's alone — §2.14 is unchanged for
letters. *Attested:* `1-279`.

### 2.11 The dash — em, U+2014, and only that (SETTLED, measured)

The book sets one dash, `—` U+2014 — no en dash, no `--`. Never `-` U+002D for
a dash: inside Tier-1 the hyphen is load-bearing (§2.1). Spacing reproduces the
print; three settings occur:

| setting | form | example |
|---|---|---|
| run-in heading | spaced both sides | `LANGUAGE. — The Chukchee language` (§2.13) |
| list introduction | spaced left, line-final | `are as follows: —` |
| quire mark / signature line | unspaced | `82—JESUP NORTH PACIFIC EXPED., VOL. VII.` — the number is the signature, read by `tei context` |

### 2.12 Roman numerals and folio slots — plain ASCII, always (SETTLED, editor ruling)

**Every roman numeral is keyed in plain ASCII capitals**, however set: `Plates V,
VII, XIV`, `VOL. VII.`. The book's small-capital setting is an English-register
display convention, and §2.3 licenses no small-cap `V` or `X`. Two folio slots:

- a **bracketed folio at the foot of a chapter opening** — `[1]`, `[115]` —
  plain ASCII digits in brackets (`QuireMarksZone`; `context.APPARATUS_ZONES`
  drops it from the collation draft);
- the **signature line's leading number** — `82—JESUP …` — plain ASCII digits.

**`1` and `I` are homographs in this face** and no zoom separates them, so the
numbering scheme decides: **plates** take an uppercase roman number, their
subdivisions arabic (`Plate XXVI, Fig. 1`); **figures** take an arabic number,
subdivisions a lowercase letter, a point of interest an arabic numeral (`Fig.
148, a, b`; `Fig. 17, f¹`). A numeral after `Fig.` is arabic at every level. A
plate cited out of another book carries that book's scheme: flag it for a human.
*Attested:* `1-328` `Fig. 188`, four words from the `ɪ`s of `xxɪx`.

### 2.13 Run-in section headings — key the setting (SETTLED, editor ruling)

| printed as | level | key it as |
|---|---|---|
| small capitals — `Aɴᴄɪᴇɴᴛ Hᴀʙɪᴛᴀᴛ. —` | second | **plain ASCII capitals**, `ANCIENT HABITAT.` |
| italic title case — `System of Winds. —` | third | **title case as printed**, `System of Winds.` |

A small-cap setting has a full-height initial and reads as a capitalized word
until the second letter is held against the first, on the line being keyed.
**The printed ToC is not a witness to a heading's existence**: a heading absent
from it is keyed as set and never retitled or demoted; `edition/toc.json` records
the book's omissions under `editorial`. *Attested:* `2-046` `System of Winds`,
absent from the contents at `1-009`.

### 2.14 The printer's errors — key them, with one exception (SETTLED, editor ruling)

**A printer's error is keyed as printed; `gt/ocr` never repairs the book.** It is
a letter or a word, never a mark of punctuation — a stray mark is a blot, keyed
as nothing, class `artifact`. The store is line images paired with their text,
so a repaired character teaches a recognizer something false; the collation pass
corrects visibly, with the print beside the correction.
*Attested:* `1-087` L17 `spririts`.

**Wear is not a letter.** A sort that printed thin, broke or abraded is keyed as
the letter the compositor set, never the lookalike the residue resembles — an
`r` worn to a stem is `r`, not `ı`. Substituting the lookalike mints a glyph
identity out of damage. Note the wear, class `artifact`. In English prose an
ambiguous `f`/`t` is settled by the sense — `the wolt` has one reading — and
wear concentrates at line ends. *Attested:* `2-154` L16 `of`.

**The one exception is a contextually Tier-1 form — a gloss, a native proper
name, a vocabulary entry — carrying what the notation does not contain at all.**
Exactly three shapes:

- a mark outside the §2.1 set (an acute over a vowel, `a` + U+0301);
- a §2.1 mark on a base §2.6 does not license (`e` + U+0306);
- a plainly polysyllabic form with no stress mark anywhere (§5.5).

The notation is a closed set, so a form inside it that merely surprises is
evidence, and a form outside it is a compositor's slip with no reading to
preserve. Tier-1 glyphs are not only training data: `proposal marks` and
`concordance.md` measure every later reader against the store, so keying the
slip would enter it into the evidence. **A reader keys what is set and puts the
provision it falls outside in `note`; the correction is the adjudicator's**, a
human act ranked `#ed`, licensed by occurrences already in `gt/ocr` and nothing
else. Nothing catches the first shape mechanically — `unlicensed_marks` inspects
only marks that have a licence entry — so the reader's flag is the detector. The
second shape is the one it does catch, for that same reason: the mark carries a
licence and the base is not on it, so `corpus normalize` reports the line before
any reader's flag has to.
*Attested:* `1-099` L13 `Kuvár` → `Kuvaˊr`; `3-095` L16 `eˊrmĕčɪn` → `eˊrmečɪn`.

### 2.15 Diacritics on English loanwords — strip them (SETTLED, editor ruling)

**A mark on a common English word is not keyed**: `rôle` → `role`, `naïve` →
`naive`, `vice versâ` → `vice versa`, `séance` → `seance`. Every such mark is a
member of `INVENTORY_CHARS` under NFD, so kept it reads as Tier-1 to every
detector and measurement, corpus-wide; stripped it costs one training pair.

**The test is only whether the word is common or a name.** Whether English also
sets the word accented does not enter it. A proper name keeps its marks
(`Nordenskiöld`): the entity store keys on the spelling. Gate: none.
*Attested:* `2-124` L7 `rôle`; `2-158` L5 `séance`.

### 2.16 The lexicon key — how a ratified form is addressed (SETTLED, derived)

**A key is not a spelling and must never be read back as one.** `lexicon lookup`
prints one beside every ratified form; `{key}` in a reading is replaced by the
corpus's own characters. ASCII passes through unchanged — `'` and `-` included,
and case is significant — while every other character leaves a visible marker, so
that a key cannot be mistaken for the glyphs it names. `marks.HANDLE_MARKERS` is
the table, and this is it:

| marker | the glyph it marks |
|---|---|
| `'` | `ˊ` U+02CA stress |
| `.` | `˙` U+02D9 palatalization **and** `◌̣` U+0323 dot below |
| `^` | `◌̌` U+030C caron **and** `◌̂` U+0302 circumflex |
| `~` | `◌̃` U+0303 tilde |
| `:` | `◌̈` U+0308 diaeresis |
| `)` | `◌̆` U+0306 breve |
| `=` | `◌̄` U+0304 macron |
| `_` | the letter before it is the small cap: `i_` ɪ, `e_` ᴇ, `a_` ᴀ, `l_` ʟ, `o_` ɵ |
| `e^` | `ᵋ` U+1D4B **and** `ᵉ` U+1D49, whole |

    Kuluˊči             kulu'c^i
    Kavraˊlɪt           kavra'li_t
    Notaˊs˙qa-vaˊɪrg̣ɪn  nota's.qa-va'i_rg.i_n

**Three markers are many-to-one**, marked above: a key names a form, never a
reading, which is the same reason §2.6's licences and not the key decide what a
mark may sit on.

**Query in the key alphabet, not in the printed glyphs.** `Taˊn˙ñɪn` typed as
Unicode returns nothing while `Tannin` and `Ta'n.n~i_n` both reach it, and the
empty result reads exactly like a word the corpus lacks. **A miss is a fact about
the query, never about the corpus** — and the two that have cost this pass real
readings are the printed form, and a hyphenated compound the corpus holds only as
its elements (`Aˊtal-Taˊn˙ñɪn` misses; `Tannin` does not). Query each element.
*Attested:* `3-125` L25, `Taˊn˙ñɪn` hand-keyed against ten ratified occurrences on
six pages, one miss generalized across four lines.

## 3. Forbidden lookalikes

Codepoints that are always an error in the scope named. The four marked
*corpus-wide* are `validate.FORBIDDEN_PROSE`; the rest are greps inside Tier-1
spans, where the licensed sort is the one in the right-hand column.

| Codepoint(s) | Scope | Trap for |
|---|---|---|
| U+00B4 ´ | corpus-wide | U+02CA |
| U+02BC ʼ, U+02BB ʻ | corpus-wide | U+02CA |
| U+2010 ‐ | corpus-wide | U+002D |
| U+0027 ' , U+2019 ’ , U+2018 ‘ | Tier-1 | U+02CA (§2.1) |
| U+00B7 · (middle dot) | Tier-1 | U+02D9 |
| U+0121 ġ, g + U+0307 | Tier-1 | g + U+0323 |
| U+02E2 ˢ | Tier-1 | U+1D4B, U+1D49 |
| U+2091 ₑ | Tier-1 | U+1D49 |
| U+04E9 ө (Cyrillic) | Tier-1 | U+0275 |

Any `ġ` surviving in working documents is the dot-above transmission stand-in
for g̣: annotate in working docs, correct in normative ones.

## 4. Validation (print-compliance, never inference)

1. Stress culminativity: ≤1 U+02CA per root (§5.5). Unimplemented.
2. U+1D49 not immediately before `i`: error.
3. U+1D4B immediately before `i`: review flag.
4. The §3 greps, each in its scope.
5. §2.6 mark licences: error.
6. NFD conformance.
7. Per-language frequency table of the seven lateral/rhotic sorts — the
   mechanical F4 resolution.

Ground truth: zero tolerance. Collation output reproduces Tier-1 draft text
verbatim, so its hits inside those spans are the to-key worklist, not a defect.

## 5. Priors (measured; cite the verb, never a number)

The store is overwhelmingly Chukchee and mid-rebuild, so every share here moves
and none is written down: the claim is a direction plus the verb that recomputes
it. **Where the text glosses a form as another language — Koryak, Chuvan,
Eskimo — no prior applies**: key what is printed and say so in `note`. How a
prior is applied at the raster is the reader's contract (R-items); this section
says only what the count says.

1. **Dot below `g`.** **Word-final `-gɪn`/`-gɪt` — the last letters of the
   word — is dotted, a closed count with no bare instance**: key `-g̣ɪn`/`-g̣ɪt`
   whether or not the dot is visible, and do not note that you could not see
   it. In every other position the dot is a large majority and not a constant:
   a bare `g` there is a reading to make, never a default. `detectors.SUFFIX_MARK_DROPS`
   flags a bare token ending `-gɪ`/`-gɪn`/`-gɪt` in `proposal check`, report-only.
   Recompute: `harness ocr grep 'g̣ɪ[nt]' --all --store gt` against `'gɪ[nt]'`
   (under NFD the second matches only the undotted form); `harness lexicon marks`
   for the overall share. *Attested:* `3-006` L19 `yaraˊ-tɵˊmg̣ɪt`.
2. **`ɪ` over `i`.** Tier-1 `ɪ` outnumbers plain `i`, and `-ɪn`/`-ɪt` are the
   commonest suffixes; plain `-in` is rare and chiefly in proper nouns and loans.
   A suffixal dotted `i` is the reading that needs a reason. Recompute:
   `harness lexicon suffixes`.
3. **`ä` is a minority of Tier-1 `a`**, so the prior runs against the mark; a
   bare `a` is still a candidate, because the diaeresis is small. Recompute:
   `harness lexicon marks`.
4. **Capital vs small-cap is decided by position, not height.** Word-medially
   an ASCII capital is never right — `detectors.MEDIAL_CAPS` refuses it. Word-
   initially both are ordinary and **the store supports no prior in either
   direction**; `harness proposal marks` says so in its `outside` column.
5. **Stress is culminative per root.** Every polysyllabic Tier-1 root carries
   exactly one U+02CA (§2.1); one with none is not a plausible reading but a flag
   (§2.14). **A hyphen bounds a root here**, so a hyphenated compound carries one
   mark per element — `vinreˊt-tuˊmg̣ɪn` (`2-067`, `3-086`), `tŭmñeˊ-leiˊwulɪt`
   (`3-091`). It bounds nothing for §2.3's medial capitals, where a compound's
   second element is medial (`detectors.MEDIAL_CAPS`); the two scopes differ and
   neither follows from the other. Nothing counts the marks — this one is the
   reader's to apply, and no gate implements it.
